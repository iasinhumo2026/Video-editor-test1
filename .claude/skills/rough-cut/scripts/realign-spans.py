#!/usr/bin/env python3
"""realign-spans.py — repair a transcript at the source where WhisperX's VAD dropped speech.

A second voice on a phone speaker (or any passage ~10 dB under the main speaker) falls under
WhisperX's VAD, and with that text missing wav2vec2 force-fits the neighbouring words over the
window: it does not leave a hole, it INVENTS dialogue there (two reference jobs, 2026-09-17 and 2026-09-18, where "Okay, so it should call me" landed over a phone number read aloud). No boundary
check can see that; the tells are in `cut-audit.py --coverage`, and the fix is here.

The method, and the only one that has worked: hand-write what is really said in the broken spans
(cross-checked against an independent ASR pass — `cut-audit.py --say <t0> <t1>`), force-align THOSE
spans with the same wav2vec2 aligner, and keep WhisperX's words everywhere else.

  uv run .claude/skills/rough-cut/scripts/realign-spans.py            # usage + the spans file shape
  <venv>/bin/python \
      .claude/skills/rough-cut/scripts/realign-spans.py <job_dir> <spans.json> [--dry-run]
  (Windows: <venv>/Scripts/python.exe; <venv> = $VIDEO_EDITOR_WHISPERX_VENV, else ~/.cache/video-editor/whisperx-venv)

It runs inside the WhisperX venv `transcribe.sh` builds (whisperx is not a uv dependency), backs the
current transcript up as `transcript/words.whisperx-vad.json` (once — a second run keeps the first,
pre-repair backup) and rewrites `transcript/words.json`.

spans.json — every span is (start, end, text) on ONE clip, in source seconds:

  {"clip": "walkthrough.mp4",
   "spans": [[1805.6, 1807.9, "One sec. Working on that now."],
             [1808.7, 1813.1, "Done. It's on your calendar for two p.m. Anything else?"]]}

  · a list of spans alone is accepted when the job has exactly one clip, or with --clip
  · spans may be [start, end, text] or {"start":, "end":, "text":}
  · spans may not overlap each other (they are the windows being replaced); merge them instead
  · every WhisperX word that OVERLAPS a span's window is REPLACED; everything outside is untouched
  · wav2vec2 cannot align numerals — a digit string comes back squeezed into a few hundred ms, so
    check the per-span table this prints and set those word times from the envelope by hand
    (`cut-audit.py --say` gives the real edges) before authoring a cut over them.
"""
import argparse
import json
import os
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def load_spans(path, clips, want_clip):
    """(clip record, [(start, end, text), ...]) from the spans file."""
    doc = json.load(open(path, encoding="utf-8"))
    raw = doc if isinstance(doc, list) else doc.get("spans", [])
    name = want_clip or (doc.get("clip") if isinstance(doc, dict) else None)
    if name is None:
        if len(clips) != 1:
            sys.exit(f"spans file names no clip and the job has {len(clips)}: "
                     f"add \"clip\" or pass --clip ({', '.join(os.path.basename(c['clip']) for c in clips)})")
        name = clips[0]["clip"]
    name = os.path.basename(name)
    clip = next((c for c in clips if os.path.basename(c["clip"]) == name), None)
    if clip is None:
        sys.exit(f"clip {name!r} is not in words.json")
    spans = []
    for s in raw:
        if isinstance(s, dict):
            spans.append((float(s["start"]), float(s["end"]), str(s["text"]).strip()))
        else:
            spans.append((float(s[0]), float(s[1]), str(s[2]).strip()))
    if not spans:
        sys.exit(f"{path} holds no spans")
    spans.sort()
    # EVERY span's own length, in its own loop: pairing it with the overlap test below left the LAST
    # span — and a one-span file, the common shape — unchecked, so a transposed pair went straight
    # into whisperx.align and its output was written over the canonical transcript.
    for a, b, _ in spans:
        if b <= a:
            sys.exit(f"span {a:.2f}-{b:.2f} ends at/before it starts")
    for (a, b, _), (c, d, _) in zip(spans, spans[1:]):
        # ANY overlap, not just nesting: two windows over the same audio align the same seconds twice
        # and both word sets land in words.json, so the transcript comes back with overlapping words
        # and every boundary measured off it is fiction. Merge them into one span with one text.
        if c < b:
            kind = "contains" if d <= b else "overlaps"
            sys.exit(f"spans {kind}: {a:.2f}-{b:.2f} / {c:.2f}-{d:.2f} — merge them into one span")
    return clip, spans


def main():
    ap = argparse.ArgumentParser(usage=__doc__.split("\n\n")[0])
    ap.add_argument("job")
    ap.add_argument("spans")
    ap.add_argument("--clip", default=None, help="which clip the spans are on (default: the only one)")
    ap.add_argument("--dry-run", action="store_true", help="align and report, write nothing")
    a = ap.parse_args()

    job = os.path.abspath(a.job)
    words_path = os.path.join(job, "transcript", "words.json")
    backup = os.path.join(job, "transcript", "words.whisperx-vad.json")
    if not os.path.exists(words_path):
        sys.exit(f"no transcript at {words_path} — run transcribe.sh first")
    doc = json.load(open(words_path, encoding="utf-8"))
    clip, spans = load_spans(a.spans, doc["clips"], a.clip)

    try:
        import whisperx
    except ImportError:
        venv = os.environ.get("VIDEO_EDITOR_WHISPERX_VENV") or os.path.expanduser("~/.cache/video-editor/whisperx-venv")
        py = os.path.join(venv, "Scripts", "python.exe") if os.name == "nt" else os.path.join(venv, "bin", "python")
        sys.exit("whisperx is missing: run this with the venv transcribe.sh builds, e.g.\n"
                 f"  {py} .claude/skills/rough-cut/scripts/realign-spans.py <job_dir> <spans.json>")

    path = clip.get("path") or os.path.join(job, "raw", os.path.basename(clip["clip"]))
    if not os.path.exists(path):
        path = os.path.join(job, "raw", os.path.basename(clip["clip"]))
    print(f"[realign] {os.path.basename(path)}: {len(spans)} spans, "
          f"{spans[0][0]:.1f}–{spans[-1][1]:.1f} s")
    audio = whisperx.load_audio(path)
    model, meta = whisperx.load_align_model(language_code="en", device="cpu")
    al = whisperx.align([{"start": s, "end": e, "text": t} for s, e, t in spans],
                        model, meta, audio, "cpu", return_char_alignments=False)

    new = [{"w": w["word"].strip(), "start": round(float(w["start"]), 3),
            "end": round(float(w["end"]), 3), "prob": round(float(w.get("score", 1.0)), 3)}
           for seg in al["segments"] for w in seg.get("words", [])
           if "start" in w and "end" in w]
    # every WhisperX word that TOUCHES a repaired window goes; the rest of the take is untouched.
    # Dropping by `start` alone left a word that began before the window and ran into it sitting on
    # top of the newly aligned words — and the invented text is exactly a neighbour force-fitted
    # across the window's edge, so it is the fiction being repaired, not a real word.
    def hit(w):
        return any(w["end"] > s and w["start"] < e for s, e, _ in spans)
    kept = [w for w in clip["words"] if not hit(w)]
    edge = sum(1 for w in clip["words"] if hit(w) and not any(s <= w["start"] < e for s, e, _ in spans))
    print(f"[realign] {len(clip['words']) - len(kept)} WhisperX words replaced by {len(new)} aligned words"
          + (f" ({edge} of them only overlapped a span edge — widen the span's text if one was real)" if edge else ""))
    for seg in al["segments"]:
        ws = [w for w in seg.get("words", []) if "start" in w]
        if not ws:
            print(f"[realign]   ⚠ NOTHING ALIGNED: {seg['text'][:70]!r} — check the span's times")
            continue
        digits = [w for w in ws if sum(ch.isdigit() for ch in w["word"]) >= 3]
        print(f"{ws[0]['start']:8.2f}-{ws[-1]['end']:7.2f}  minp {min(w.get('score', 1) for w in ws):.2f}"
              f"  {seg['text'][:66]}"
              + (f"\n          ⚠ numerals squeezed, set by hand: "
                 + ", ".join(f"{w['word']} {1000*(w['end']-w['start']):.0f} ms" for w in digits) if digits else ""))

    clip["words"] = sorted(new + kept, key=lambda w: w["start"])
    if a.dry_run:
        print("[realign] --dry-run: nothing written")
        return
    if not os.path.exists(backup):
        shutil.copy2(words_path, backup)
        print(f"[realign] backed the pre-repair transcript up as {backup}")
    else:
        print(f"[realign] {backup} already holds the pre-repair transcript, kept")
    json.dump(doc, open(words_path, "w", encoding="utf-8"), indent=2)
    print(f"[realign] wrote {words_path} — re-derive anything built off it "
          f"(splice.sh / export-transcript.py), and re-run cut-audit.py --coverage")


if __name__ == "__main__":
    main()
