# /// script
# requires-python = ">=3.10"
# dependencies = ["requests>=2.31"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""
transcribe-scribe.py — EXPERIMENT (2026-09-13): transcribe a job's raw clips with
ElevenLabs Scribe v2 and write the SAME words.json shape transcribe.sh writes, so the
rest of the rough-cut line (scan-transcript, refine-cuts, polish-boundaries, splice)
can run on it unchanged.

    uv run .claude/skills/rough-cut/scripts/transcribe-scribe.py projects/<job> [--keyterms] [--canonical]

Writes  <job>/transcript/words.scribe.json   (never the canonical words.json unless --canonical)
        <job>/transcript/scribe-raw/<clip>.json  (the untouched API response, for inspection)

Auth:   ELEVENLABS_API_KEY in the environment or the repo-root .env.
Cost:   Scribe v2 is $0.22 per audio hour (+ $0.05/hr with --keyterms), billed in USD
        from a pay-as-you-go balance. A 10-minute clip is under 4 cents.

--keyterms feeds every target spelling from transcript-corrections.json (`auto` values,
deduped: Claude, Anthropic, HyperFrames, ...) as keyterm bias, the one Scribe feature WhisperX
has no answer to. --canonical overwrites transcript/words.json (backs up the old one first).

Compare against WhisperX with compare-transcripts.py.
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[4]
API = "https://api.elevenlabs.io/v1/speech-to-text"
MODEL = "scribe_v2"
PUNCT_ONLY = re.compile(r"^[^\w]+$")


def load_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        env = REPO / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("ELEVENLABS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("[scribe] no ELEVENLABS_API_KEY in env or .env — create one at "
                 "elevenlabs.io → Developers → API keys, then add ELEVENLABS_API_KEY=... to .env")
    return key


def keyterms_from_corrections() -> list[str]:
    path = REPO / "transcript-corrections.json"
    if not path.exists():
        return []
    auto = json.loads(path.read_text(encoding="utf-8")).get("auto", {})
    seen, out = set(), []
    for target in auto.values():
        t = target.strip().rstrip("'s").strip()
        if t and t.lower() not in seen and len(t) <= 50:
            seen.add(t.lower())
            out.append(t)
    return out[:1000]


def extract_audio(clip: Path, tmp: Path) -> Path:
    """Mono 48 kHz FLAC — lossless, small enough to upload, no resample guesswork."""
    out = tmp / (clip.stem + ".flac")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ac", "1", "-ar", "48000",
         "-c:a", "flac", str(out)],
        check=True,
    )
    return out


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def call_scribe(audio: Path, key: str, keyterms: list[str]) -> dict:
    data = [
        ("model_id", MODEL),
        ("language_code", "en"),
        ("timestamps_granularity", "word"),
        ("diarize", "false"),
        ("tag_audio_events", "false"),
    ]
    for k in keyterms:
        data.append(("keyterms", k))
    with audio.open("rb") as fh:
        r = requests.post(
            API, headers={"xi-api-key": key}, data=data,
            files={"file": (audio.name, fh, "audio/flac")}, timeout=1800,
        )
    if r.status_code != 200:
        sys.exit(f"[scribe] HTTP {r.status_code}: {r.text[:800]}")
    return r.json()


def to_words(resp: dict) -> list[dict]:
    """Scribe → {w,start,end,prob}. Spacing/audio-event tokens are dropped; a token that is
    pure punctuation is glued onto the previous word (Scribe usually attaches it already).
    prob = exp(logprob) so the 0..1 scale matches WhisperX's alignment score."""
    words: list[dict] = []
    for tok in resp.get("words", []):
        if tok.get("type") != "word":
            continue
        text = str(tok.get("text", "")).strip()
        if not text:
            continue
        if PUNCT_ONLY.match(text) and words:
            words[-1]["w"] += text
            continue
        if tok.get("start") is None or tok.get("end") is None:
            continue
        lp = tok.get("logprob")
        prob = math.exp(lp) if isinstance(lp, (int, float)) and lp <= 0 else 1.0
        words.append({
            "w": text,
            "start": round(float(tok["start"]), 3),
            "end": round(float(tok["end"]), 3),
            "prob": round(min(prob, 1.0), 3),
        })
    return words


def main() -> None:
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    keyterms_on = "--keyterms" in args
    canonical = "--canonical" in args
    job = Path([a for a in args if not a.startswith("--")][0]).resolve()
    media = job / "raw" if (job / "raw").is_dir() else job
    clips = sorted(p for p in media.iterdir()
                   if p.suffix.lower() in {".mov", ".mp4", ".mkv", ".m4v"})
    if not clips:
        sys.exit(f"[scribe] no clips in {media}")

    key = load_key()
    keyterms = keyterms_from_corrections() if keyterms_on else []
    if keyterms:
        print(f"[scribe] keyterms ({len(keyterms)}): {', '.join(keyterms[:12])}"
              f"{' …' if len(keyterms) > 12 else ''}", file=sys.stderr)

    tdir = job / "transcript"
    raw_dir = tdir / "scribe-raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    result = {"clips": []}
    total_min = 0.0

    with tempfile.TemporaryDirectory() as tmp:
        for clip in clips:
            print(f"[scribe] extracting audio ← {clip.name}", file=sys.stderr)
            audio = extract_audio(clip, Path(tmp))
            dur = probe_duration(audio)
            total_min += dur / 60
            print(f"[scribe] uploading {audio.stat().st_size / 1e6:.1f} MB "
                  f"({dur / 60:.1f} min) to {MODEL} …", file=sys.stderr)
            resp = call_scribe(audio, key, keyterms)
            (raw_dir / f"{clip.stem}.json").write_text(json.dumps(resp, indent=2), encoding="utf-8")
            words = to_words(resp)
            result["clips"].append({
                "clip": clip.name, "path": str(clip),
                "duration": round(dur, 3), "words": words,
            })
            print(f"[scribe] {clip.name}: {len(words)} words, "
                  f"lang {resp.get('language_code')} p{resp.get('language_probability', 0):.2f}",
                  file=sys.stderr)

    out = tdir / "words.json" if canonical else tdir / "words.scribe.json"
    if canonical and out.exists():
        bak = tdir / "words.whisperx.json"
        if not bak.exists():
            out.rename(bak)
            print(f"[scribe] kept the WhisperX transcript as {bak.name}", file=sys.stderr)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    # Same long-span heuristic transcribe.sh prints, so the two engines are judged alike.
    for c in result["clips"]:
        for w in c["words"]:
            span = w["end"] - w["start"]
            if span > 1.0 or (span > 0.5 and w["prob"] < 0.5):
                print(f"[scribe] ⚠ long-span word {w['w']!r} {w['start']:.2f}→{w['end']:.2f} "
                      f"({span:.2f}s, p{w['prob']:.2f})", file=sys.stderr)

    rate = 0.22 + (0.05 if keyterms else 0.0)
    print(f"[scribe] wrote {out}  (≈ ${total_min / 60 * rate:.3f} at ${rate:.2f}/hr)",
          file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
