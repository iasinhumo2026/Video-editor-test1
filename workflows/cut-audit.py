#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy>=1.24", "matplotlib>=3.7"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""cut-audit.py: measure every EDL boundary on the RAW waveform and repair the ones that land in speech.

  uv run workflows/cut-audit.py projects/<job>                       # audit transcript/cuts.json, print verdicts
  uv run workflows/cut-audit.py projects/<job> --grid 24000/1001     # the FINISH SURFACE's frame rate: pick every
                                                                     #   boundary ON that grid (Premiere floors in/out
                                                                     #   points to the sequence grid; 2026-09-13)
  uv run workflows/cut-audit.py projects/<job> --live live.json      # judge the LIVE in/out points (a lane readback:
                                                                     #   [[src_in, src_out], ...] in EDL order) instead
  uv run workflows/cut-audit.py projects/<job> --write <out.json> --sheet <out.png>
                                                                     # write the repaired EDL (pinned) + a waveform
                                                                     #   contact sheet of every changed boundary. REFUSES
                                                                     #   (exit 2) a target that holds pin_in/pin_out the
                                                                     #   input lacks: pin the input, or --edl <target>
  uv run workflows/cut-audit.py projects/<job> --promote             # back transcript/cuts.json up as
                                                                     #   cuts.pre-audit-<stamp>.json, write the audited EDL
                                                                     #   there, print the export-transcript command
  uv run workflows/cut-audit.py projects/<job> --coverage            # BEFORE any cut is authored: every inter-word
                                                                     #   gap in words.json that still holds sound —
                                                                     #   the windows WhisperX's VAD dropped and the
                                                                     #   aligner then fills with fiction (2026-09-18);
                                                                     #   a flagged gap the ASR hears no word in drops to
                                                                     #   "· sound, no speech heard"
  uv run workflows/cut-audit.py projects/<job> --ack 122.4 158.8 --note "phone ringing"
                                                                     # acknowledge a coverage gap (transcript/
                                                                     #   coverage-ack.json): it prints, never counts
  uv run workflows/cut-audit.py projects/<job> --say 924.9 927.3     # what an independent ASR hears in that RAW span
                                                                     #   (the hardened slice transcription, by hand);
                                                                     #   no times = the whole clip, in <= 30 s windows;
                                                                     #   --boost lifts a phone voice about 10 dB under first;
                                                                     #   --spans-out <f> drafts a realign-spans.py file

WHY: the refiner and polish-boundaries.py measure boundaries once, off WhisperX anchors, and the app
lane then quantizes them to ITS frame grid. Both leave cuts inside speech on a real job (the outro
screen-recording outro on a 23.976 sequence: every out point floored up to 41 ms early = clipped tails, every
in point floored early = the killed word bleeding in). This tool trusts only the waveform: a 5 ms
RMS envelope, a local noise floor, speech runs, and for every boundary the onset / decay it must
respect. Verdicts: OK · CLIP (cut inside speech: a clipped attack/decay, repaired to the run's edge; at an OUT
that edge includes the kept word's quiet final consonant, carried through the high band by polish-boundaries.py's
consonant_end, so a cut 70 ms after the vowel of "advantage" is CLIP and every tail is measured from that end) ·
FUSED (a killed word runs straight into the kept one: the cut sits on the last prominent dip before
the kept word's attack, never the run's edge; the content gate never extends it past the next killed
word's aligner edge, the first word past the segment's own last / first word) · BREATH (a low-level
inhale at the head, kept whole; at an OUT, a run past the kept word that the ASR hears no word in, kept
where it is with a ⚠ verify) · LONG (a tail over 70 + 80 ms, or a beat tail over 250 ms, trimmed to
decay + 70 / 250 ms) · HAND (a --live readback more than a frame off the EDL: the creator's own trim,
reported and never moved — a hand edit that is ALSO a defect keeps the defect verdict and prints
`CLIP*`, so nothing a human touched can hide one). Only defects, leads < 40 ms / tails < 70 ms and LONG
tails move, and a boundary carrying "pin_in" / "pin_out" is reported with what it would have done, never
moved. A CLIP at a word the aligner's midpoint and the transcript put on different sides is measured on
the transcript's reading and, when that would move it, HELD the same way: left where it is, still CLIP,
"would have moved" with a ⚠ verify, and counted as held in the summary. At a --live hand edit the
transcript is stale (the readback is paired with the unchanged EDL), so there the split is the words the
live span plays: a clean trim on a dip reads HAND, never HELD.
A segment carrying "media" (laid from a substitute file, e.g. a lip-sync re-record) is not the raw's
audio: it is printed as not audited, left as it is, and still counts on the timeline. The proposed
EDL is then run through dead-air-qa.py's own quiet-run gate, so a joint whose tail + next lead reach
0.65 s is flagged here instead of failing dead-air-qa afterwards.

The WHAT (uniform tails, decay + 70 ms, onset − 40 ms) is the rough-cut skill's; this tool measures
and snaps. Read-only unless --write, --promote or --ack. Exits 3, UNVERIFIED, when a check needed the slice ASR
and no engine could run (workflows/asr_cli.py): those boundaries were judged on the envelope alone.

2026-09-13, reverse-engineered from the user's hand pass on the same outro (74 clips vs the 66 laid): at a
FUSED joint the dip's own frame belongs to the killed word, so the cut snaps INWARD (every fused OUT he
touched sits on the frame boundary at/before the dip, every fused IN one frame after); a landed line ("beat": true)
keeps up to 250 ms of the speaker's own pause; interior pauses the envelope cannot see on a screen
recording (breath + room noise above floor + 10 dB) are found from the aligner's inter-word gaps and
verified by a slice transcription before they split a segment; a token that is a prefix of the next
word ("gpt's" → "gpt6") is flagged as a possible false start.
"""
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys, time
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asr_cli  # noqa: E402  (the slice-ASR engine per OS)

# dead-air-qa.py's quiet-run gate, imported rather than re-typed: the joint check below must fail
# exactly what that gate will fail (a tail that passed here failed there, 2026-09-20)
_spec = importlib.util.spec_from_file_location("dead_air_qa", Path(__file__).with_name("dead-air-qa.py"))
dq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dq)
# polish-boundaries.py's consonant_end, imported for the same reason: the polish and this audit must place the end of a
# word's quiet final consonant identically, or the audit calls every polished tail after one LONG (2026-10-14)
_spec = importlib.util.spec_from_file_location(
    "polish_boundaries", Path(__file__).resolve().parent.parent / ".claude" / "skills" / "rough-cut" / "scripts" / "polish-boundaries.py")
polish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(polish)

for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

SR = 16000
HOP = 0.005          # envelope frame (s)
LEAD = 0.040         # air before an onset
TAIL = 0.070         # air after a decay
BEAT_TAIL = 0.250    # a LANDED line ("beat": true) keeps up to this much of the speaker's own pause (2026-09-13 hand pass)
LONG_OVER = 0.080    # a plain tail more than this over TAIL is LONG and trimmed (a beat tail: anything over BEAT_TAIL).
                     # A 390 ms tail passed as "ok" and then failed dead-air-qa with the next lead (2026-09-20).
ALIGNER_GAP = 0.900  # an aligner gap this long between two kept words is dead air once the ASR hears nothing in it.
                     # 0.9 on paper is about 0.65 heard: WhisperX ends words early and starts them late, and the user's
                     # 2026-09-13 hand pass left eight 660-800 ms aligner gaps alone (heard pauses cap at 645 ms).
MIN_RUN = 0.030      # shorter runs are clicks
MERGE_GAP = 0.045    # intra-word dips shorter than this stay one run
THR_ABOVE_FLOOR = 10 # dB
NUDGE = 1e-4

# ---- --coverage: the windows the VAD dropped (two reference jobs, 2026-09-18) ----
COV_GAP = 1.500      # an inter-word gap this long is a candidate: the VAD may have dropped what is in it
COV_RUN = 0.400      # a sustained sound this long inside the gap is material, not a click or a keystroke
COV_MERGE = 0.150    # syllable-scale dips inside one utterance
COV_SPEECH = 1.000   # total sustained sound in a gap before it is worth a line
COV_LOWPROB = 0.35   # an alignment score at/below this is an untrusted word
COV_LOWRUN = 3       # this many untrusted words in the six beside a gap is a run, not one soft word
COV_PER_DIGIT = 0.12 # seconds per digit: nobody reads a numeral faster, so a token under this is
                     # wav2vec2 squeezing one (a 10-digit phone number read aloud came back as one
                     # 0.28 s token — 28 ms a digit — with six invented words behind it, your-job
                     # 2026-09-18). Never write the real string into this file: it is the kind of
                     # thing --coverage exists to keep off the screen, and workflows/ ships.


def decode(path, t0=None, t1=None):
    span = ["-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}"] if t0 is not None else []
    r = subprocess.run(["ffmpeg", "-v", "error", *span, "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode:
        sys.exit(r.stderr.decode(errors="replace"))
    return np.frombuffer(r.stdout, dtype=np.float32)


def dq_levels(x):
    """dead-air-qa.py's own envelope and floor (`dq.levels`: 10 ms RMS of the s16 decode, floor = its 10th
    percentile), computed from this tool's float decode. ffmpeg converts float to s16 as
    clip(lrint(x * 32768)), so on a MONO raw the two agree to float rounding. On a stereo raw ffmpeg's
    float downmix runs 3.01 dB hotter than its s16 one: every level (and the floor) is offset by that
    constant, and the quiet MASK, whose threshold sits relative to the peak and the floor, is identical
    (both in test_cut_audit_coverage)."""
    s16 = lambda v: np.clip(np.rint(v.astype(np.float64) * 32768.0), -32768, 32767)
    hop = int(SR * dq.HOP)
    m = len(x) // hop
    fr = x[: m * hop].reshape(m, hop)
    ms = np.empty(m + (1 if len(x) % hop else 0))
    for k in range(0, m, 16384):          # in blocks: a long take in float64 at once is gigabytes
        blk = s16(fr[k:k + 16384])
        ms[k:k + len(blk)] = (blk * blk).mean(axis=1)
    if len(x) % hop:
        tail = s16(x[m * hop:])
        ms[-1] = (tail * tail).mean()
    env = 20 * np.log10(np.sqrt(ms) / 32768 + 1e-9)
    return env, float(np.sort(env)[len(env) // 10]) if len(env) else -180.0


def hf_envelope(x):
    """polish-boundaries.py's high band (Env.hf) for the whole clip: per 5 ms hop, the RMS of the second difference on
    the s16 scale, in dB. Computed in blocks: a long take in float64 at once is gigabytes."""
    n = int(SR * HOP)
    m = len(x) // n
    out = np.empty(m)
    for k in range(0, m, 16384):
        a, b = k * n, min(m, k + 16384) * n
        p = x[max(0, a - 2):b].astype(np.float64) * 32768.0
        d = p[2:] - 2 * p[1:-1] + p[:-2]
        if a == 0:
            d = np.concatenate([np.zeros(2), d])      # samples 0 and 1 have no second difference (Env.hf skips them)
        out[k:k + (b - a) // n] = 20 * np.log10(np.sqrt((d.reshape(-1, n) ** 2).sum(axis=1) / n) + 1.0)
    return out


def envelope(x):
    n = int(SR * HOP)
    m = len(x) // n
    fr = x[: m * n].reshape(m, n)
    rms = np.sqrt((fr * fr).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    # 3-frame median: kills single-frame spikes without moving edges
    med = db.copy()
    med[1:-1] = np.median(np.stack([db[:-2], db[1:-1], db[2:]]), axis=0)
    return med


def runs_in(env, t0, t1, thr):
    """Speech runs (start, end) in seconds inside [t0, t1] above thr, merged and de-clicked."""
    i0, i1 = max(0, int(t0 / HOP)), min(len(env), int(t1 / HOP))
    above = env[i0:i1] > thr
    out = []
    start = None
    for k, a in enumerate(above):
        if a and start is None:
            start = k
        elif not a and start is not None:
            out.append([start, k]); start = None
    if start is not None:
        out.append([start, len(above)])
    merged = []
    for r in out:
        if merged and (r[0] - merged[-1][1]) * HOP < MERGE_GAP:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [((i0 + a) * HOP, (i0 + b) * HOP) for a, b in merged if (b - a) * HOP >= MIN_RUN]


def local_threshold(env, t):
    i0, i1 = max(0, int((t - 2.0) / HOP)), min(len(env), int((t + 2.0) / HOP))
    w = env[i0:i1]
    floor = np.percentile(w, 10)
    peak = np.percentile(w, 99)
    return max(floor + THR_ABOVE_FLOOR, peak - 30), floor


def minimum_between(env, a, b):
    i0, i1 = int(a / HOP), max(int(a / HOP) + 1, int(b / HOP))
    k = int(np.argmin(env[i0:i1]))
    return (i0 + k) * HOP + HOP / 2


def gap_energy(env, t0, t1):
    """Sustained sound inside an inter-word gap: (total seconds, longest run, runs).

    The threshold is the GAP's own median + 8 dB, floored at its 10th percentile + 12 dB: a gap is
    mostly silence, so its median IS the room tone there, and that holds on a screen recording whose
    room tone sits 15 dB above the file's global floor. Runs are merged at syllable scale and the
    short ones dropped, so a keystroke or a mouse click is not a voice."""
    i0, i1 = max(0, int(t0 / HOP)), min(len(env), int(t1 / HOP))
    w = env[i0:i1]
    if len(w) < 20:
        return 0.0, 0.0, []
    thr = max(float(np.percentile(w, 50)) + 8.0, float(np.percentile(w, 10)) + 12.0)
    merged = []
    for r in runs_in(env, t0 + 0.05, t1 - 0.05, thr):
        if merged and r[0] - merged[-1][1] < COV_MERGE:
            merged[-1][1] = r[1]
        else:
            merged.append([r[0], r[1]])
    rs = [(a, b) for a, b in merged if b - a >= COV_RUN]
    return sum(b - a for a, b in rs), max((b - a for a, b in rs), default=0.0), rs


ASR_MODEL = "mlx-community/whisper-large-v3-turbo"
_asr_cache = {}
_asr_dead = [False]   # why the slice ASR could not run, once it could not: the audit then exits 3, UNVERIFIED


def norm(w):
    import re
    return re.sub(r"[^a-z0-9]", "", w.lower())


def tok_match(a, b):
    return bool(a) and bool(b) and (a == b or (len(a) >= 3 and len(b) >= 3 and (a.startswith(b[:3]) or b.startswith(a[:3]))))


PAD = 0.20   # digital silence added on the cut side of a content-gate slice (s)

DEFECTS = ("CLIP", "CONTENT")   # a boundary that lands in speech, whatever else is true of it


def hand_edit(v, d, cur, edl, tol):
    """A --live boundary more than one frame off the EDL is the creator's own trim. Returns
    (verdict, detail, is_hand) and NEVER moves anything — the caller pins the boundary to `cur`.

    The verdict a measurement already reached SURVIVES the hand tag: a boundary can be both a hand
    trim and a cut inside speech, and reporting only "HAND" dropped the clipped word out of
    "boundaries in speech" and out of the --sheet, i.e. the tool hid a real defect on exactly the
    boundaries a human had touched. Leaving it unmoved is the repo law (root CLAUDE.md § live state
    that disagrees); erasing it is not. The detail line carries both, and the flag prints `CLIP*`."""
    if abs(cur - edl) <= tol:
        return v, d, False
    d += f"; HAND edit {1000 * (cur - edl):+.0f} ms off the EDL, left alone"
    return (v if v in DEFECTS else "HAND"), d, True


def pinned_boundary(pin, cur, new, d):
    """A boundary bisected by content ("pin_in"/"pin_out" on the segment, the rough-cut skill's
    stutter repair) is reported with what it WOULD have done and never moved: the envelope cannot
    out-judge a word-by-word scan. Returns (boundary, detail)."""
    if pin and abs(new - cur) > 0.004:
        return cur, d + f"; pinned, would have moved to {new:.3f}"
    return new, d


ASR_WINDOW = 30.0    # the longest slice one ASR pass gets: a whole-take pass locked into repeating one sentence (2026-09-20)
# a phone voice about 10 dB under the speaker: compress, lift, then normalise the SLICE before the ASR
# hears it (never the delivered audio). It used to be built by hand, and a first hand-rolled run wrote nothing.
BOOST_AF = "acompressor=threshold=-40dB:ratio=6:attack=5:release=120:makeup=12dB,loudnorm=I=-18:TP=-2:LRA=11"


def scratch_dir(job):
    """The slice-ASR cache, one folder per job PATH: /tmp/video-editor/<name> is shared by every job with that
    basename (sections/intro exists in several jobs), and a window cached there was served as another job's
    words (2026-10-02)."""
    j = Path(job).resolve()
    tag = hashlib.sha1(str(j).encode("utf-8")).hexdigest()[:10]
    return Path(tempfile.gettempdir() if os.name == "nt" else "/tmp") / "video-editor" / j.name / "cut-audit-asr" / tag


def media_key(media, af, engine):
    """What a cached slice depends on besides its window: the file (resolved path, size, mtime), the filters it
    went through and the engine + model that heard it. A window-only name served clip A's words to a --say on
    clip B (2026-10-02)."""
    p = Path(media).resolve()
    try:
        st = p.stat()
        ident = f"{st.st_size}:{st.st_mtime_ns}"
    except OSError:
        ident = "missing"
    return hashlib.sha1("|".join([str(p), ident, ",".join(af), " ".join(engine), ASR_MODEL]).encode("utf-8")).hexdigest()[:12]


def asr_json(media, t0, t1, scratch, pad=None, boost=False):
    """mlx-whisper's own JSON for raw [t0, t1] and the shift to subtract from its times (counted from the t0 asked
    for), or None. Every pass runs with --condition-on-previous-text False: with it on, a long pass repeated one
    sentence for a whole file (2026-09-20)."""
    if _asr_dead[0]:
        return None
    # a window that starts before the raw (a check 2 s back from a cut near the head) is cut from 0: ffmpeg reads
    # `-ss -0.4 -t 2.4` as the first 2.0 s, so every word mapped back from the t0 asked for landed 0.4 s early
    # (cache s-400_2000, the Windows pass 2026-10-13)
    early = max(0.0, -t0)
    t0 = max(0.0, t0)
    engine = asr_cli.argv()    # mlx-whisper on Apple Silicon, the WhisperX venv's faster-whisper elsewhere (workflows/asr_cli.py)
    if engine is None or shutil.which(engine[0]) is None and not Path(engine[0]).exists():
        _asr_dead[0] = asr_cli.unavailable_reason()
        print(f"[cut-audit] ⚠ ASR unavailable ({_asr_dead[0]}); falling back to envelope heuristics", file=sys.stderr)
        return None
    scratch.mkdir(parents=True, exist_ok=True)
    # the filters run BEFORE -ac 1 downmixes, so the delay must cover every channel: a bare adelay=200 delays
    # only the first, and a stereo raw's "silent" lead-in carried the other channel at half level, then its
    # echo (a pre-padded content_in slice, measured 2026-09-23)
    af = ([BOOST_AF] if boost else []) + \
         ([f"adelay={int(PAD * 1000)}:all=1"] if pad == "pre" else ([f"apad=pad_dur={PAD}"] if pad == "post" else []))
    # mlx_whisper names its output by the basename up to the FIRST dot. A pre-padded slice is tagged "preall":
    # the ones tagged "pre" were delayed on the FIRST channel only (above), and are never reused
    tag = {"pre": "_preall", "post": "_post"}.get(pad, "")
    name = f"s{int(round(t0 * 1000))}_{int(round(t1 * 1000))}{tag}{'_boost' if boost else ''}_{media_key(media, af, engine)}"
    wav = scratch / f"{name}.wav"
    j = scratch / f"{name}.json"
    shift = (PAD if pad == "pre" else 0.0) - early
    if j.exists():
        return json.loads(j.read_text(encoding="utf-8")), shift
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(media),
                    "-ac", "1", *(["-af", ",".join(af)] if af else []), "-ar", "16000", "-y", str(wav)], capture_output=True)
    # one engine process for the whole audit, the model loaded once (asr_cli.run); the slice and its JSON are the same
    r = asr_cli.run(["--model", ASR_MODEL, "--word-timestamps", "True", "--condition-on-previous-text", "False",
                     "--output-format", "json", "--output-dir", str(scratch), str(wav)])
    if r.returncode or not j.exists():
        _asr_dead[0] = str((r.stderr or r.stdout).strip().splitlines()[-1:] or 'no output')
        print(f"[cut-audit] ⚠ ASR unavailable ({_asr_dead[0]}); falling back to envelope heuristics", file=sys.stderr)
        return None
    return json.loads(j.read_text(encoding="utf-8")), shift


def asr_words(media, t0, t1, scratch, pad=None, boost=False):
    """Independent word-timed transcription of raw [t0, t1] (large-v3-turbo through workflows/asr_cli.py).
    pad="pre" prepends PAD s of silence (a slice that starts ON a cut), pad="post" appends it (a slice
    that ends on one): the decoder mis-hears a word it meets mid-attack without any lead-in ("So" read
    as "oh" at a clean cut, 2026-09-13). boost=True lifts a quiet second voice first (BOOST_AF).
    Returns [(token, abs_start, abs_end)] in RAW time, or None."""
    key = (str(media), round(t0, 3), round(t1, 3), pad, boost)
    if key in _asr_cache:
        return _asr_cache[key]
    got = asr_json(media, t0, t1, scratch, pad, boost)
    if got is None:
        return None
    d, shift = got
    out = [(norm(w["word"]), t0 + w["start"] - shift, t0 + w["end"] - shift) for s in d.get("segments", []) for w in s.get("words", [])]
    _asr_cache[key] = out
    return out


def asr_segments(media, t0, t1, scratch, boost=False):
    """[(start, end, text)] per ASR segment of raw [t0, t1], in RAW time, or None. A segment's span is
    its own words' (first start to last end) when it has them: that is the window realign-spans.py
    replaces, so it must hold the whole line."""
    got = asr_json(media, t0, t1, scratch, None, boost)
    if got is None:
        return None
    d, shift = got
    out = []
    for s in d.get("segments", []):
        text = (s.get("text") or "").strip()
        if not text:
            continue
        ws = [w for w in s.get("words", []) if w.get("start") is not None and w.get("end") is not None]
        a_, b_ = (ws[0]["start"], ws[-1]["end"]) if ws else (s["start"], s["end"])
        out.append((t0 + a_ - shift, t0 + b_ - shift, text))
    return out


def asr_windows(media, t0, t1, width=ASR_WINDOW):
    """[t0, t1] as consecutive windows no longer than `width`, each ended on the quietest 5 ms of its last
    5 s so no word is cut in half at a window edge. One window when the span already fits."""
    if t1 - t0 <= width:
        return [(t0, t1)]
    env = envelope(decode(media, t0, t1))
    out, a_ = [], t0
    while t1 - a_ > width:
        i0 = int((a_ + width - 5.0 - t0) / HOP)
        i1 = min(len(env), int((a_ + width - t0) / HOP))
        b_ = t0 + (i0 + int(np.argmin(env[i0:i1]))) * HOP if i1 > i0 else a_ + width
        b_ = min(max(b_, a_ + 1.0), a_ + width)
        out.append((a_, b_))
        a_ = b_
    out.append((a_, t1))
    return out


def asr_span_words(media, t0, t1, scratch, boost=False):
    """asr_words over a span of any length, one <= ASR_WINDOW pass per window; None when the ASR is unavailable."""
    out = []
    for w0, w1 in asr_windows(media, t0, t1):
        h = asr_words(media, w0, w1, scratch, boost=boost)
        if h is None:
            return None
        out += h
    return out


def spans_draft(segments):
    """ASR segments -> realign-spans.py spans ([t0, t1, text], sorted, never overlapping: that tool
    refuses an overlapping pair), rounded to the millisecond."""
    out = []
    for s0, s1, text in sorted(segments):
        s0, s1 = round(s0, 3), round(s1, 3)
        if out and s0 < out[-1][1]:
            s0 = out[-1][1]
        if s1 <= s0:
            if out:
                out[-1][1] = max(out[-1][1], s1)
                out[-1][2] += " " + text
            continue
        out.append([s0, s1, text])
    return out


def heard_past(media, t, t_end, scratch):
    """Does an independent ASR hear a word past an OUT at t, up to t_end? The kept side up to the cut
    (padded) against the same slice run on to t_end: any change to its words (one added, or the last one
    completed) is speech past the cut; the same words mean the run past it is breath or room tone.
    None when the ASR is unavailable."""
    t0 = max(0.0, t - 2.0)
    a_ = asr_words(media, t0, t, scratch, pad="post")
    b_ = asr_words(media, t0, t_end, scratch)
    if a_ is None or b_ is None:
        return None
    return [w[0] for w in b_] != [w[0] for w in a_]


def pins_lacking(target, source):
    """Every pin_in / pin_out in `target` whose segment (same clip, overlapping range) carries no such
    pin in `source`: what writing the audit of `source` over `target` would silently erase."""
    out = []
    for k, t in enumerate(target):
        for key in ("pin_in", "pin_out"):
            if not t.get(key):
                continue
            same = [s for s in source if os.path.basename(s["clip"]) == os.path.basename(t["clip"])
                    and float(s["start"]) < float(t["end"]) and float(t["start"]) < float(s["end"])]
            if not any(s.get(key) for s in same):
                out.append(f"seg{k:02d} {key} ({float(t['start']):.3f}-{float(t['end']):.3f})")
    return out


def content_out(media, t, scratch, ext=0.40):
    """Does extending a kept-side slice PAST an OUT cut change its last word? Then the cut is inside
    that word ("a 50" -> "a 53", "click" -> "clickbait"). Returns (status, est_word_end):
    CLEAN / CONTENT / SILENT / UNSTABLE."""
    a = asr_words(media, t - 2.0, t, scratch, pad="post")
    b = asr_words(media, t - 2.0, t + ext, scratch)
    if a is None or b is None:
        return "UNAVAILABLE", None
    ta, tb = [w[0] for w in a], [w[0] for w in b]
    if not ta:
        return "SILENT", None
    if tb[:len(ta)] == ta:
        return "CLEAN", None
    k = len(ta) - 1
    if k < len(tb) and tb[:k] == ta[:k] and tb[k] != ta[k]:
        # bisect the extension: the smallest e whose last word already reads like the full word
        target = tb[k]
        est = None
        for e in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60):
            c = asr_words(media, t - 2.0, t + e, scratch, pad="post")
            tc = [w[0] for w in c] if c else []
            if k < len(tc) and tc[k] == target:
                est = t + e
                break
        if est is not None and est - t < 0.25:
            # the decoder mis-hears a word it meets at a slice edge ("also" as "all", "So" as "oh") and settles
            # only with the next word's context: below a quarter second this is tolerance, not a chop. Flag it.
            return "WARN", est
        return "CONTENT", (est if est is not None else t + ext)
    return "UNSTABLE", None


def content_in(media, t, scratch, ext=0.40):
    """Does extending a kept-side slice BEFORE an IN cut change its first word? Then the kept word
    starts before the cut ("ree" -> "three", a clipped "I")."""
    a = asr_words(media, t, t + 2.0, scratch, pad="pre")
    b = asr_words(media, t - ext, t + 2.0, scratch)
    if a is None or b is None:
        return "UNAVAILABLE", None
    ta, tb = [w[0] for w in a], [w[0] for w in b]
    if not ta:
        return "SILENT", None
    if len(tb) >= len(ta) and tb[len(tb) - len(ta):] == ta:
        return "CLEAN", None
    j = len(tb) - len(ta)
    if 0 <= j < len(tb) and tb[j + 1:] == ta[1:] and tb[j] != ta[0]:
        target = tb[j]
        est = None
        for e in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60):
            c = asr_words(media, t - e, t + 2.0, scratch, pad="pre")
            tc = [w[0] for w in c] if c else []
            jj = len(tc) - len(ta)
            if 0 <= jj < len(tc) and tc[jj] == target:
                est = t - e
                break
        if est is not None and t - est < 0.25:
            return "WARN", est
        return "CONTENT", (est if est is not None else t - ext)
    return "UNSTABLE", None


def untrusted(ws):
    """Why this run of words cannot be trusted (the aligner's own tell), or ''.

    WhisperX drops a span its VAD calls silence and wav2vec2 then force-fits the neighbouring text
    over whatever is really there, so the fiction announces itself two ways: a cluster of low
    alignment scores, and a numeral squeezed into a time nobody could read it in. Either one beside
    a gap that still holds sound is the drop. (A plain word's chars-per-second is NOT a tell: on a
    53-minute take 'something' and 'straight' land as tight as the squeezed phone number did.)"""
    if not ws:
        return ""
    why = []
    for w in ws:
        n = sum(ch.isdigit() for ch in w["w"])
        if n >= 3 and (w["end"] - w["start"]) < n * COV_PER_DIGIT:
            why.append(f"{w['w']!r} read in {1000*(w['end']-w['start']):.0f} ms")
            break
    lo = [w for w in ws if w.get("prob", 1.0) <= COV_LOWPROB]
    if len(lo) >= COV_LOWRUN:
        why.append(f"{len(lo)} of {len(ws)} words p<={COV_LOWPROB}")
    elif sum(w.get("prob", 1.0) for w in ws) / len(ws) < 0.45:
        why.append(f"mean p {sum(w.get('prob', 1.0) for w in ws) / len(ws):.2f}")
    return ", ".join(why)


def acked(acks, name, t0, t1):
    """The acknowledgement (transcript/coverage-ack.json: [{clip, t0, t1, note}]) covering at least half
    of this gap on this clip, else None. Half, not all: a realign moves the gap's edges a little."""
    for k in acks or ():
        if k.get("clip") and os.path.basename(k["clip"]) != name:
            continue
        if min(t1, float(k["t1"])) - max(t0, float(k["t0"])) >= 0.5 * (t1 - t0):
            return k
    return None


def coverage(clips, media_dir, gap_min, scratch=None, acks=(), asr=True):
    """Every inter-word gap that still holds sound — read BEFORE a cut is authored.

    A gap alone is noise (202 of them on one 53-minute job); a gap that still holds sustained sound
    is a window with no words over it, and a gap whose neighbouring words are untrusted on top of
    that is the drop that invents dialogue. Reports both, loudest first, and never edits anything.
    A ⚠ gap is then heard by the independent ASR (asr=True, a scratch dir): no word in it drops it to
    "· sound, no speech heard" (a phone ringing kept re-flagging on every run after its repair,
    2026-09-20), and a gap acknowledged in `acks` prints "· acknowledged: <note>". Neither counts.
    Returns the number of ⚠ lines."""
    rows = []
    for cl in clips:
        name = os.path.basename(cl["clip"])
        p = cl.get("path") or str(media_dir / name)
        if not os.path.exists(p):
            p = str(media_dir / name)
        env = envelope(decode(p))
        ws = cl.get("words", [])
        for k in range(len(ws) - 1):
            a_, b_ = ws[k], ws[k + 1]
            gap = b_["start"] - a_["end"]
            if gap < gap_min:
                continue
            tot, longest, _ = gap_energy(env, a_["end"], b_["start"])
            why = untrusted(ws[k + 1:k + 7]) or untrusted(ws[max(0, k - 5):k + 1])
            rows.append((tot, name, a_["end"], b_["start"], gap, longest, why,
                         ws[k + 1:k + 9], p, norm(a_["w"]), norm(b_["w"])))
    rows.sort(key=lambda r: -r[0])
    bad = n_ack = n_quiet = 0
    for tot, name, t0, t1, gap, longest, why, nxt, p, an, bn in rows:
        if tot < COV_SPEECH:
            continue
        head = f"{name} {t0:8.2f}-{t1:8.2f} ({gap:5.1f} s gap, {tot:4.1f} s of sound, longest {longest:.2f} s)"
        ack = acked(acks, name, t0, t1)
        if ack is not None:
            n_ack += 1
            print(f"· acknowledged: {ack.get('note', '')} {head}")
            continue
        if why and asr and scratch is not None:
            heard = asr_span_words(p, t0, t1, scratch)
            if heard is None:
                why += "; unverified (ASR unavailable)"
            else:
                # the edges are the neighbouring words' own: a slice cut on them half-hears them, and the
                # decoder stretches a neighbour it meets at the edge back across the silence (the next
                # line's "And" heard from 1.4 s before its onset, over a phone ringing, 2026-09-20)
                inside = [w for w in heard if t0 + 0.10 < (w[1] + w[2]) / 2 < t1 - 0.10
                          and not (tok_match(w[0], bn) and w[2] >= t1 - 0.30)
                          and not (tok_match(w[0], an) and w[1] <= t0 + 0.30)]
                if not inside:
                    n_quiet += 1
                    print(f"· sound, no speech heard {head} (a voice far under the speaker can hide from a plain pass: "
                          f"--say {t0:.2f} {t1:.2f} --boost)")
                    continue
                why += f"; the ASR hears '{' '.join(w[0] for w in inside[:12])}'"
        if why:
            bad += 1
            print(f"⚠ VAD DROP {head}\n            untrusted beside it: {why}\n"
                  f"            next words: " + " ".join(f"{w['w']}({w.get('prob', 1.0):.2f})" for w in nxt))
        else:
            print(f"· sound in the gap {head}")
    print(f"[cut-audit] coverage: {len(rows)} gaps >= {gap_min:.1f} s, "
          f"{sum(1 for r in rows if r[0] >= COV_SPEECH)} still hold sound "
          f"({n_ack} acknowledged, {n_quiet} with no speech heard), {bad} ⚠ VAD DROP")
    print("[cut-audit] hear any window with --say <t0> <t1>; repair with "
          ".claude/skills/rough-cut/scripts/realign-spans.py; acknowledge a checked one with --ack <t0> <t1> --note <why>")
    return bad


def audit_in(env, t, thr):
    """Return (onset, prev_end, ideal, verdict, detail) for a segment IN at t."""
    rs = runs_in(env, t - 1.5, t + 1.0, thr)
    inside = [r for r in rs if r[0] < t < r[1]]
    after = [r for r in rs if r[0] >= t]
    before = [r for r in rs if r[1] <= t]
    if inside:
        r = inside[0]
        # cut inside a run: attack clipped (run started before the cut) or a fused joint
        onset = r[0]
        prev_end = before[-1][1] if before else None
        return onset, prev_end, r, "CLIP", f"cut {1000*(t-onset):.0f} ms INTO the run"
    if not after:
        return None, None, None, "SILENT", "no speech within 1 s after the cut"
    onset = after[0][0]
    prev_end = before[-1][1] if before else None
    return onset, prev_end, after[0], "OK", f"lead {1000*(onset-t):.0f} ms"


def audit_out(env, t, thr):
    rs = runs_in(env, t - 1.0, t + 1.5, thr)
    inside = [r for r in rs if r[0] < t < r[1]]
    before = [r for r in rs if r[1] <= t]
    after = [r for r in rs if r[0] >= t]
    if inside:
        r = inside[0]
        decay = r[1]
        next_on = after[0][0] if after else None
        return decay, next_on, r, "CLIP", f"cut {1000*(decay-t):.0f} ms BEFORE the run ends"
    if not before:
        return None, None, None, "SILENT", "no speech within 1 s before the cut"
    decay = before[-1][1]
    next_on = after[0][0] if after else None
    return decay, next_on, before[-1], "OK", f"tail {1000*(t-decay):.0f} ms"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--edl", default=None)
    ap.add_argument("--grid", default=None, help="finish-surface frame rate, e.g. 24000/1001 or 30")
    ap.add_argument("--live", default=None, help="json [[src_in, src_out], ...] read back from the timeline")
    wr = ap.add_mutually_exclusive_group()
    wr.add_argument("--write", default=None)
    wr.add_argument("--promote", action="store_true",
                    help="back transcript/cuts.json up as cuts.pre-audit-<stamp>.json and write the audited EDL there")
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--all", action="store_true", help="sheet every boundary, not only the changed ones")
    ap.add_argument("--asr", default="auto", choices=["auto", "off"], help="re-transcribe every run a cut sits inside (default auto)")
    ap.add_argument("--words", default=None, help="transcript to read instead of transcript/words.json")
    ap.add_argument("--coverage", action="store_true",
                    help="no EDL: report every inter-word gap that still holds sound (VAD drops)")
    ap.add_argument("--gap", type=float, default=COV_GAP, help=f"--coverage gap threshold (default {COV_GAP})")
    ap.add_argument("--say", nargs="*", type=float, metavar="T",
                    help="no EDL: print what an independent ASR hears in the RAW span T0 T1 (no times: the whole clip, "
                         f"in <= {ASR_WINDOW:.0f} s windows)")
    ap.add_argument("--boost", action="store_true", help="--say: compress + normalise the slice first (a phone voice about 10 dB under)")
    ap.add_argument("--spans-out", default=None, help="--say: write a realign-spans.py spans draft, one span per ASR segment")
    ap.add_argument("--ack", nargs=2, type=float, metavar=("T0", "T1"),
                    help="acknowledge a --coverage gap (with --note): appended to transcript/coverage-ack.json")
    ap.add_argument("--note", default=None, help="--ack: why the window holds no speech to recover")
    ap.add_argument("--clip", default=None, help="--say / --ack: which clip (default: the only one)")
    a = ap.parse_args()
    if (a.boost or a.spans_out) and a.say is None:
        ap.error("--boost / --spans-out go with --say")

    job = Path(a.job)
    media_dir = job / "raw" if (job / "raw").is_dir() else job
    scratch = scratch_dir(job)
    words_path = Path(a.words) if a.words else job / "transcript" / "words.json"
    ack_path = job / "transcript" / "coverage-ack.json"

    # ---- the EDL-less modes: run BEFORE a cut is authored, on the transcript alone ----
    if a.coverage or a.say is not None or a.ack:
        clips = json.load(open(words_path, encoding="utf-8")).get("clips", [])
        if a.coverage:
            acks = json.loads(ack_path.read_text(encoding="utf-8")) if ack_path.exists() else []
            sys.exit(0 if coverage(clips, media_dir, a.gap, scratch, acks, a.asr != "off") == 0 else 1)
        names = [os.path.basename(c["clip"]) for c in clips]
        name = a.clip or (names[0] if len(names) == 1 else None)
        if name is None:
            sys.exit(f"--{'ack' if a.ack else 'say'} needs --clip: {', '.join(names)}")
        name = os.path.basename(name)
        if a.ack:
            if not (a.note or "").strip():
                sys.exit("--ack needs --note TEXT: what is in the window, and why there is no speech to recover")
            t0, t1 = a.ack
            if t1 <= t0:
                sys.exit(f"--ack {t0} {t1}: ends at/before it starts")
            acks = json.loads(ack_path.read_text(encoding="utf-8")) if ack_path.exists() else []
            acks.append({"clip": name, "t0": round(t0, 3), "t1": round(t1, 3), "note": a.note.strip()})
            ack_path.parent.mkdir(parents=True, exist_ok=True)
            ack_path.write_text(json.dumps(acks, indent=1), encoding="utf-8")
            print(f"[cut-audit] acknowledged {name} {t0:.2f}-{t1:.2f}: {a.note.strip()} -> {ack_path}")
            return
        if len(a.say) not in (0, 2):
            sys.exit("--say takes T0 T1, or no times for the whole clip")
        cl = next((c for c in clips if os.path.basename(c["clip"]) == name), None)
        p = (cl.get("path") if cl else None) or str(media_dir / name)
        if not os.path.exists(p):
            p = str(media_dir / name)
        if a.say:
            t0, t1 = a.say
        else:
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
            t0, t1 = 0.0, float(r.stdout.strip() or 0)
            if t1 <= 0:
                sys.exit(f"[cut-audit] could not read the duration of {p}")
        heard, segments = [], []
        for w0, w1 in asr_windows(p, t0, t1):
            h = asr_words(p, w0, w1, scratch, boost=a.boost)
            if h is None:
                sys.exit(f"[cut-audit] ASR unavailable ({asr_cli.unavailable_reason()})")
            heard += h
            if a.spans_out:
                segments += asr_segments(p, w0, w1, scratch, boost=a.boost) or []
        for w, w0, w1 in heard:
            print(f"{w0:9.2f}-{w1:8.2f}  {w}")
        print(f"[cut-audit] {len(heard)} words heard in {name} {t0:.2f}-{t1:.2f}" + (" (boosted)" if a.boost else ""))
        if a.spans_out:
            spans = spans_draft(segments)
            Path(a.spans_out).write_text(json.dumps({"clip": name, "spans": spans}, indent=1), encoding="utf-8")
            print(f"[cut-audit] spans draft -> {a.spans_out} ({len(spans)} spans, one per ASR segment). CHECK every "
                  f"line by ear before .claude/skills/rough-cut/scripts/realign-spans.py {job} {a.spans_out}")
        return

    edl_path = Path(a.edl) if a.edl else job / "transcript" / "cuts.json"
    print(f"[cut-audit] reading {edl_path}")
    edl = json.load(open(edl_path, encoding="utf-8"))
    segs = edl["segments"]
    # --write / --promote never silently erase a pin: a pin_out written into the --write target was lost
    # because the audit reads transcript/cuts.json and then overwrote the target (2026-09-20)
    target = (job / "transcript" / "cuts.json") if a.promote else (Path(a.write) if a.write else None)
    if target is not None and target.exists() and target.resolve() != edl_path.resolve():
        lost = pins_lacking(json.loads(target.read_text(encoding="utf-8")).get("segments", []), segs)
        if lost:
            print(f"[cut-audit] REFUSED: {target} holds pins the input {edl_path} lacks: {'; '.join(lost)}. "
                  f"Writing would erase them: pin the input, or pass --edl {target} to audit that file.", file=sys.stderr)
            sys.exit(2)
    grid = None
    if a.grid:
        num, _, den = a.grid.partition("/")
        grid = float(den or 1) / float(num)
    live = json.load(open(a.live, encoding="utf-8")) if a.live else None
    if live and len(live) != len(segs):
        sys.exit(f"--live has {len(live)} rows, EDL has {len(segs)} segments")

    envs, dqlev, hfs = {}, {}, {}
    for s in segs:
        if s.get("media"):
            continue            # laid from a substitute file: the raw is not what plays there
        c = os.path.basename(s["clip"])
        if c not in envs:
            p = media_dir / c
            x = decode(p.resolve())
            envs[c], dqlev[c], hfs[c] = envelope(x), dq_levels(x), hf_envelope(x)
    # WhisperX words per clip: only to tell a FUSED joint (killed word running straight into the kept
    # word, cut at the minimum between them) from a clipped attack/decay (move to the run's edge)
    words = {}
    wp = words_path
    if wp.exists():
        for cl in json.load(open(wp, encoding="utf-8")).get("clips", []):
            words[os.path.basename(cl["clip"])] = cl.get("words", [])

    def timed(c):
        return [w for w in words.get(c, []) if w.get("start") is not None and w.get("end") is not None]

    def kept_word(ws, k_mid, s, side):
        """Index of the segment's KEPT boundary word by its own transcript: of the midpoint's answer
        `k_mid` and its two neighbours, the one whose token matches the transcript's boundary token (and
        its neighbour token too, when there is one), the midpoint's answer first on a tie; `k_mid` when
        nothing matches (a corrected or re-spelled word). May return -1 / len(ws): no such word."""
        toks = [x for x in (norm(y) for y in s.get("transcript", "").split()) if x]
        if side == "OUT":
            toks, step = toks[::-1], -1      # the last token, then the one before it
        else:
            step = 1                         # the first token, then the one after it
        tok, tok2 = (toks + ["", ""])[:2]
        cands = [k for k in (k_mid, k_mid - 1, k_mid + 1) if 0 <= k < len(ws)] if tok else []
        one = [k for k in cands if tok_match(norm(ws[k]["w"]), tok)]
        two = [k for k in one if tok2 and 0 <= k + step < len(ws) and tok_match(norm(ws[k + step]["w"]), tok2)]
        return (two or one or [k_mid])[0]

    # THE KEPT/KILLED SPLIT at a boundary is the SEGMENT's: its own transcript names its first / last kept word
    # (kept_word), and the killed neighbour is the first word past it that is NOT in the segment. The WhisperX
    # midpoint (a word whose centre is on the far side of the cut is killed) is a second reading; where the two
    # disagree, the word straddles the cut. The content gate is bounded by the segment's killed neighbour: by
    # midpoint a 60 ms killed "et" whose centre was already past the cut read as kept and the gate went straight
    # through it (2026-09-20 review), and a kept "53" the cut chops before its centre read as killed and stopped
    # the gate on its own motivating case (2026-09-23 review). The ENVELOPE repair is not trusted on a disputed
    # word: on three jobs' EDLs each reading moved a real cut the wrong way (a text re-derived from the cut
    # picks up a killed word it grazes, "my emails, et", or drops a kept word it chops; the midpoint cut away a
    # kept "Okay,"). There the repair is measured on the segment's reading and, when it would move the cut,
    # the cut is HELD like a pin: verdict CLIP (it is in speech), "would have moved", ⚠ verify by ear.
    def neighbours_in(c, t, s):
        """(killed word before the cut, first kept word, disputed word or None), split by the segment's own
        transcript; `disputed` is the word the aligner's midpoint puts on the other side of the cut."""
        ws = timed(c)
        k_mid = next((j for j, w in enumerate(ws) if (w["start"] + w["end"]) / 2 > t), len(ws))
        k = kept_word(ws, k_mid, s, "IN")
        disputed = ws[min(k_mid, k)] if k != k_mid and 0 <= min(k_mid, k) < len(ws) else None
        if k >= len(ws):
            return None, None, disputed
        return (ws[k - 1] if k > 0 else None), ws[k], disputed

    def neighbours_out(c, t, s):
        """(last kept word, killed word after the cut, disputed word or None), split by the segment's own
        transcript; `disputed` is the word the aligner's midpoint puts on the other side of the cut."""
        ws = timed(c)
        k_mid = max((j for j, w in enumerate(ws) if (w["start"] + w["end"]) / 2 < t), default=-1)
        k = kept_word(ws, k_mid, s, "OUT")
        disputed = ws[max(k_mid, k)] if k != k_mid and 0 <= max(k_mid, k) < len(ws) else None
        if k < 0:
            return None, None, disputed
        return ws[k], (ws[k + 1] if k + 1 < len(ws) else None), disputed

    def held(w, side, new):
        return (f"; ⚠ HELD: the aligner and the transcript disagree on '{w['w']}' ({w['start']:.3f}-{w['end']:.3f}) "
                f"at the {side} (which side of the cut it belongs on): would have moved to {new:.3f}, verify by ear")

    def env_at(env, t):
        k = min(len(env) - 1, max(0, int(t / HOP)))
        return float(env[k])

    def pick(ideal, lo, hi, cur):
        """Best of {current, floor, ceil on the grid} inside [lo, hi], nearest the ideal; least violation otherwise."""
        cands = [cur] + ([np.floor(ideal / grid) * grid, np.ceil(ideal / grid) * grid] if grid else [ideal])
        ok = [x for x in cands if lo - 1e-6 <= x <= hi + 1e-6]
        if ok:
            return float(min(ok, key=lambda x: abs(x - ideal)))
        return float(min(cands, key=lambda x: max(lo - x, x - hi, 0)))

    def pick_min(env, tmin, cur, side, wa=-1e9, wb=1e9):
        """A dip between two sounds IS the boundary, and the dip's own frame belongs to the KILLED word:
        snap INWARD from it (the frame boundary at/before the dip for an OUT, at/after it for an IN)
        while that boundary is within 10 dB of the dip (a decay or a lead is quiet, an attack is not),
        and outward only when the outward boundary is as quiet as the dip (a real gap, not a fused
        joint); else the quietest candidate. A cut already inward within a frame stays (no churn).
        Measured off the user's 2026-09-13 outro hand pass: the five fused OUTs he touched
        all sit on the frame boundary at/before the envelope minimum (this tool's old OUTWARD snap had
        put four of them on the frame that plays the killed word's first 10-40 ms: "numbers|okay" at
        -31 dB against a -55 dB dip), and both fused INs he touched moved one frame later, past the dip.
        Candidates outside [wa, wb] are last resorts."""
        if not grid:
            return tmin
        level = lambda x: env_at(env, x + (0.0 if side == "IN" else -HOP))
        fl, ce = np.floor(tmin / grid) * grid, np.ceil(tmin / grid) * grid
        inward = [ce] if side == "IN" else [fl]
        outward = [fl] if side == "IN" else [ce]
        on_inward_side = (cur >= tmin - 0.005) if side == "IN" else (cur <= tmin + 0.005)
        order = ([cur] if abs(cur - tmin) <= grid and on_inward_side else []) + inward + outward
        order = [round(float(x), 6) for x in order]
        out_set = {round(float(x), 6) for x in outward}
        base = level(tmin)
        for x in order:
            tol = 3.0 if x in out_set else 10.0
            if wa <= x <= wb and level(x) <= base + tol:
                return x
        return min(order, key=level)

    def attack_after(env, a, b, thr):
        """The first steep rise (>= 8 dB over 20 ms, ending above the speech threshold) in [a, b]: a word's
        attack, the natural far bound for the gap that precedes it. None when nothing that steep is there."""
        i0, i1 = max(2, int(a / HOP)), min(len(env) - 3, int(b / HOP))
        for k in range(i0, i1):
            if env[k + 2] - env[k - 2] >= 8.0 and env[k + 2] > thr - 3.0:
                return (k - 2) * HOP
        return None

    def deepest_local_min(env, a, b, prom=4.0):
        """The lowest prominent local minimum in [a, b] (the real gap between two words is the deepest dip
        near their ASR boundary; a fricative tail or a plosive's post-burst dip is shallower), else None."""
        i0, i1 = int(a / HOP), int(b / HOP)
        best = None
        for k in range(i0 + 3, i1 - 3):
            v = env[k]
            if v > min(env[k - 3:k]) or v > min(env[k + 1:k + 4]):
                continue
            if max(env[max(0, k - 12):k]) - v < prom or max(env[k + 1:k + 13]) - v < prom:
                continue
            if best is None or v < env[int(best / HOP)]:
                best = (k + 0.5) * HOP
        return best

    def first_local_min(env, a, b, prom=4.0):
        """The first prominent local minimum in [a, b] (the gap right after a word), else None."""
        i0, i1 = int(a / HOP), int(b / HOP)
        for k in range(i0 + 3, i1 - 3):
            v = env[k]
            if v > min(env[k - 3:k]) or v > min(env[k + 1:k + 4]):
                continue
            if max(env[max(0, k - 12):k]) - v < prom or max(env[k + 1:k + 13]) - v < prom:
                continue
            return (k + 0.5) * HOP
        return None

    def last_local_min(env, a, b, prom=4.0):
        """The last prominent local minimum in [a, b]: lower than its ±15 ms neighbours and at least
        `prom` dB under the peaks 60 ms either side. None when the window holds no such dip."""
        i0, i1 = int(a / HOP), int(b / HOP)
        best = None
        for k in range(i0 + 3, i1 - 3):
            v = env[k]
            if v > min(env[k - 3:k]) or v > min(env[k + 1:k + 4]):
                continue
            if max(env[max(0, k - 12):k]) - v < prom or max(env[k + 1:k + 13]) - v < prom:
                continue
            best = (k + 0.5) * HOP
        return best

    # ---- interior pauses and false starts: the aligner proposes, a slice transcription judges (2026-09-13) ----
    # The polish pass splits interior dead air it can SEE on the envelope; on a screen recording the breath
    # and room noise inside a pause sit above floor + 10 dB, so a 940 ms pause after "So" and 1.4 s inside
    # "in API [ ] equivalent cost" never registered (and every segment was pinned, which used to skip the
    # pass). Here the aligner's inter-word gap between two KEPT words is the candidate: a gap >= ALIGNER_GAP
    # in which the ASR hears no word is split (out = word end + TAIL, in = next start − LEAD, then audited
    # below like any boundary); a gap the ASR hears a word in is a mumbled word the aligner skipped
    # ("like, Pro or" inside a 0.96 s "pause") and stays, with a warning. "keep_pauses": true opts out.
    if not live:
        split_segs = []
        parts_of = {}      # parent segment -> the part(s) it becomes; [itself] when it is not split
        notes = []         # (parent, boundary time, message): numbered AFTER the split, never before
        for i, s in enumerate(segs):
            if s.get("media"):
                # words.json is not this segment's transcript (its audio is the substitute file's)
                split_segs.append(s); parts_of[id(s)] = [s]; continue
            c = os.path.basename(s["clip"])
            ws_ = [w for w in words.get(c, []) if w.get("start") is not None and w["start"] >= s["start"] - 0.02 and w["end"] <= s["end"] + 0.02]
            cuts = []
            for k in range(len(ws_) - 1):
                a_, b_ = ws_[k], ws_[k + 1]
                an, bn = norm(a_["w"]), norm(b_["w"])
                gap = b_["start"] - a_["end"]
                if len(an) >= 3 and len(bn) >= 3 and an != bn and gap >= 0.10 and \
                        (bn.startswith(an) or an.startswith(bn) or (an[:3] == bn[:3] and abs(len(an) - len(bn)) <= 2)):
                    notes.append((s, a_["start"], f"⚠ possible false start '{a_['w']}' → '{b_['w']}' @{a_['start']:.2f}: a prefix / near-spelling of the next word; kill it if it is a restart"))
                if gap < ALIGNER_GAP or s.get("keep_pauses") or a_["end"] - s["start"] < 0.15 or s["end"] - b_["start"] < 0.15:
                    continue
                if a.asr == "off":
                    notes.append((s, a_["end"], f"⚠ {1000*gap:.0f} ms aligner gap '{a_['w']}' | '{b_['w']}' @{a_['end']:.2f}: unverified (--asr off), left whole"))
                    continue
                heard = asr_words(media_dir / c, a_["end"] - 0.30, b_["start"] + 0.30, scratch)
                if heard is None:
                    notes.append((s, a_["end"], f"⚠ {1000*gap:.0f} ms aligner gap '{a_['w']}' | '{b_['w']}' @{a_['end']:.2f}: unverified (ASR unavailable), left whole"))
                    continue
                inside = [w for w in heard if a_["end"] + 0.05 < (w[1] + w[2]) / 2 < b_["start"] - 0.05
                          and not tok_match(w[0], an) and not tok_match(w[0], bn)]
                if inside:
                    notes.append((s, a_["end"], f"⚠ {1000*gap:.0f} ms aligner gap '{a_['w']}' | '{b_['w']}' @{a_['end']:.2f} holds speech the aligner skipped ('{' '.join(w[0] for w in inside)}'): not dead air, left whole"))
                    continue
                cuts.append((a_["end"] + TAIL, b_["start"] - LEAD, a_, b_, gap))
            if not cuts:
                split_segs.append(s); parts_of[id(s)] = [s]; continue
            bounds = [s["start"]] + [t for cc in cuts for t in cc[:2]] + [s["end"]]
            parts = [(bounds[j], bounds[j + 1]) for j in range(0, len(bounds), 2)]
            parts_of[id(s)] = []
            for (pa, pb) in parts:
                ns = dict(s); ns["start"], ns["end"] = round(float(pa), 5), round(float(pb), 5)
                pw = [w for w in ws_ if pa - 0.02 <= w["end"] <= pb + 0.02]
                ns["transcript"] = " ".join(w["w"] for w in pw) or s.get("transcript", "")
                if pa != s["start"]: ns.pop("pin_in", None)
                if pb != s["end"]: ns.pop("pin_out", None); ns.pop("beat", None)
                split_segs.append(ns); parts_of[id(s)].append(ns)
            for (o_t, i_t, a_, b_, gap) in cuts:
                notes.append((s, a_["end"], f"[split] {1000*gap:.0f} ms of dead air '{a_['w']}' | '{b_['w']}' (aligner gap, the ASR hears nothing in it) → cut {o_t:.3f} | {i_t:.3f}"))
        if len(split_segs) != len(segs):
            print(f"[cut-audit] interior pauses: {len(segs)} → {len(split_segs)} segments")
        segs = split_segs
        # EVERY seg N this run prints is an index into the FINAL array it audits and writes. The sweep
        # above numbers segments in the PRE-split space and the split renumbers everything after it, so
        # the warnings are collected against their segment and numbered here instead (polish printed one
        # boundary as both seg17 and seg19 in a single file, your-job 2026-09-18). A split parent resolves
        # to the part that holds the warning's own boundary time.
        pos = {id(x): k for k, x in enumerate(segs)}
        for parent, t_, msg in notes:
            ps = parts_of.get(id(parent)) or [parent]
            hit = next((p for p in ps if float(p["start"]) - 0.02 <= t_ <= float(p["end"]) + 0.02),
                       min(ps, key=lambda p: abs(float(p["start"]) - t_)))
            # a miss is a BUG in the buffering above, and a silent default of 0 would send a reviewer
            # to the wrong segment — the exact failure this renumbering exists to end. Say so instead.
            if id(hit) not in pos:
                print(f"[cut-audit] ⚠ BUG: the line at {t_:.3f}s is keyed to no written segment — "
                      f"index unavailable, DO NOT trust a seg number on it", file=sys.stderr)
            print(f"seg{pos[id(hit)]:02d} {msg}" if id(hit) in pos else f"seg?? {msg}")

    changed = []
    rows = []
    for i, s in enumerate(segs):
        c = os.path.basename(s["clip"])
        if s.get("media"):
            # laid from a substitute file (a lip-sync re-record): the raw's waveform is not what plays, so
            # nothing is measured and nothing moves; its EDL times stand (a --live readback there is the
            # substitute file's own clock) and it still counts on the timeline
            t_in, t_out = float(s["start"]), float(s["end"])
            rows.append(dict(i=i, clip=c, cur_in=t_in, cur_out=t_out, new_in=t_in, new_out=t_out, v_in="MEDIA", d_in="",
                             v_out="MEDIA", d_out="", onset=None, prev_end=None, decay=None, next_on=None,
                             thr_in=None, thr_out=None, h_in=False, h_out=False, held_in=False, held_out=False,
                             media=s["media"]))
            print(f"seg{i:02d} laid from {s['media']}: not audited on the raw")
            continue
        env = envs[c]
        cur_in, cur_out = (live[i] if live else (s["start"], s["end"]))
        # a --live boundary the creator trimmed by hand (hand_edit's own test, below) is paired with the
        # UNCHANGED EDL, so the segment transcript still names the word the trim removed: at that boundary the
        # kept words are the ones the live span plays (by aligner midpoint), never the stale text. Read off
        # the stale text, a clean one-word trim on a fused joint read HELD and CLIP*, "drop the trim".
        s_in = s_out = s
        if live:
            tol_h = (grid or 0.042) + 1e-6
            live_text = " ".join(w["w"] for w in timed(c) if cur_in < (w["start"] + w["end"]) / 2 < cur_out)
            if abs(cur_in - float(s["start"])) > tol_h:
                s_in = dict(s, transcript=live_text)
            if abs(cur_out - float(s["end"])) > tol_h:
                s_out = dict(s, transcript=live_text)
        thr_in, _ = local_threshold(env, cur_in)
        thr_out, _ = local_threshold(env, cur_out)
        onset, prev_end, run_in, v_in, d_in = audit_in(env, cur_in, thr_in)
        decay, next_on, run_out, v_out, d_out = audit_out(env, cur_out, thr_out)
        # A QUIET FINAL CONSONANT is still the word (2026-10-14: "advantage", "effects," lost their last 3-4 frames).
        # Its noise sits under the broadband threshold or past a stop closure, so the run ends at the vowel and a cut
        # 70 ms later read "ok". The kept word's decay is carried through the high band by polish-boundaries.py's own
        # consonant_end: a cut before it is a CLIP repaired to it + TAIL, and a polished tail after it is not LONG.
        kept_o, next_o, _ = neighbours_out(c, cur_out, s_out)
        if decay is not None and kept_o is not None and v_out in ("OK", "CLIP"):
            soft = polish.consonant_end(lambda k0, k1: hfs[c][max(0, k0):max(0, k1)].tolist(), HOP, kept_o, decay,
                                        (next_o["start"] - 0.015) if next_o is not None else decay + 1.0)
            if soft > decay + 1e-6:
                later = [r for r in runs_in(env, soft, soft + 1.5, thr_out) if r[0] >= soft]
                next_on = later[0][0] if later else None
                if v_out == "OK" and cur_out < soft - 0.005:
                    v_out = "CLIP"
                    d_out = f"cut {1000*(soft-cur_out):.0f} ms before '{kept_o['w']}' ends: its final consonant runs to {soft:.3f} (high band)"
                elif v_out == "OK":
                    d_out = f"tail {1000*(cur_out-soft):.0f} ms past the final consonant of '{kept_o['w']}' (high band, {soft:.3f})"
                run_out = (run_out[0], max(run_out[1], soft))
                decay = soft
        # THE CONTENT GATE, every boundary: the waveform cannot tell a syllable after a quiet fricative
        # ("fif|ty-three", "click|bait") from the next killed word; an independent transcription can.
        c_in_new = c_out_new = None
        if a.asr != "off":
            st, est = content_in(media_dir / c, cur_in, scratch)
            d_env = d_in
            if st == "CONTENT":
                # the kept first word starts at/before est: its acoustic onset is the run holding est
                # the word begins between est-0.05 and est (bisection step): cut at the last dip before that,
                # else LEAD before est; never inside the run that precedes it
                rs = runs_in(env, est - 0.6, cur_in + 0.3, thr_in)
                dip = last_local_min(env, est - 0.25, est + 0.03)
                on = dip if dip is not None else est - 0.05
                before = [r for r in rs if r[1] <= on]
                lo = (before[-1][1] + 0.010) if before else -1e9
                c_in_new = (pick_min(env, on, cur_in, "IN", on - 0.05, on + 0.05) if dip is not None else pick(on - LEAD, lo, on - 0.005, cur_in)) if grid else on - LEAD
                d_in = f"CONTENT: the kept first word begins before the cut (ASR, reads whole from {est:.3f}), cut {c_in_new:.3f}"
                # never back into the killed word before (the mirror of the OUT bound below)
                pk = neighbours_in(c, cur_in, s_in)[0]
                if pk is not None:
                    cap = float(np.ceil(pk["end"] / grid - 1e-9) * grid) if grid else float(pk["end"])
                    if cap >= cur_in - 0.004:
                        d_in = d_env + (f"; content gate wanted {c_in_new:.3f} ({1000*(c_in_new-cur_in):+.0f} ms) but the killed word "
                                        f"'{pk['w']}' ends {pk['end']:.3f} (aligner), at/after the cut: not moved, ⚠ verify by ear")
                        c_in_new = None
                    elif c_in_new < cap:
                        c_in_new = cap
                        d_in += f"; ⚠ stopped at the killed word '{pk['w']}' (aligner end {pk['end']:.3f}): verify by ear"
            elif st == "WARN":
                d_in += f"; ⚠ ASR reads the first word whole only from {est:.3f} ({1000*(cur_in-est):.0f} ms earlier): verify by ear / the proof"
            elif st == "UNSTABLE":
                d_in += "; ⚠ ASR unstable across this cut, verify by ear"
            st, est = content_out(media_dir / c, cur_out, scratch)
            d_env = d_out
            if st == "CONTENT":
                rs = runs_in(env, cur_out - 0.3, est + 0.6, thr_out)
                hold = [r for r in rs if r[0] <= est - 0.02 <= r[1]] or [r for r in rs if r[1] >= cur_out]
                dec = hold[0][1] if hold else est
                after = [r for r in rs if r[0] >= dec]
                hi = (after[0][0] - 0.010) if after else 1e9
                c_out_new = pick(dec + (BEAT_TAIL if s.get("beat") else TAIL), dec + 0.020, hi, cur_out) if grid else dec + (BEAT_TAIL if s.get("beat") else TAIL)
                d_out = f"CONTENT: the kept last word runs past the cut (ASR), decay {dec:.3f}"
                # the extension never runs into the next KILLED word (the first word past the segment's own last
                # word, neighbours_out): bounded by its aligner start, and when that sits at/before the cut the
                # envelope's verdict stands (a fused joint read as CONTENT wanted +1043 ms and would have shipped
                # a deliberately killed "et cetera, et cetera", 2026-09-20)
                nk = neighbours_out(c, cur_out, s_out)[1]
                if nk is not None:
                    cap = float(np.floor(nk["start"] / grid + 1e-9) * grid) if grid else float(nk["start"])
                    if cap <= cur_out + 0.004:
                        d_out = d_env + (f"; content gate wanted {c_out_new:.3f} ({1000*(c_out_new-cur_out):+.0f} ms) but the next killed "
                                         f"word '{nk['w']}' starts {nk['start']:.3f} (aligner), at/before the cut: not extended, ⚠ verify by ear")
                        c_out_new = None
                    elif c_out_new > cap:
                        c_out_new = cap
                        d_out += f"; ⚠ stopped at the next killed word '{nk['w']}' (aligner start {nk['start']:.3f}): verify by ear"
            elif st == "WARN":
                d_out += f"; ⚠ ASR reads the last word whole only to {est:.3f} ({1000*(est-cur_out):.0f} ms later): verify by ear / the proof"
            elif st == "UNSTABLE":
                d_out += "; ⚠ ASR unstable across this cut, verify by ear"

        # IN: only a defect moves the boundary (cut in speech, killed word audible, lead < LEAD)
        new_in = cur_in
        held_in = held_out = False
        if v_in == "CLIP":
            prev_w, kept_w, disp_in = neighbours_in(c, cur_in, s_in)
            k_start = kept_w["start"] if kept_w else cur_in + 0.05
            asr_done = False
            if a.asr != "off":
                # what is actually said in this run decides: the kept segment's first word is either the
                # run's first word (a clipped attack, or a breath then the word) or it follows a killed
                # word inside the run (fused: cut on the dip between them)
                toks = [x for x in (norm(y) for y in s_in.get("transcript", "").split()) if x]
                kt, kt2 = (toks[0] if toks else ""), (toks[1] if len(toks) > 1 else "")
                ws = asr_words(media_dir / c, run_in[0] - 0.05, min(run_in[1], cur_in + 1.5) + 0.05, scratch)
                if ws and kt:
                    # the kept segment's first TWO words locate it inside the run (a repeated word, "I ... I think",
                    # or a stutter "to, to" would otherwise match the wrong occurrence); one word when that is all there is
                    cands = [k for k, w in enumerate(ws) if tok_match(w[0], kt) and w[1] >= run_in[0] - 0.15]
                    two = [k for k in cands if k + 1 < len(ws) and tok_match(ws[k + 1][0], kt2)] if kt2 else []
                    pool = two or cands
                    idx = min(pool, key=lambda k: abs(ws[k][1] - cur_in)) if pool else None
                    if idx is not None:
                        onset_asr = ws[idx][1]
                        prev_asr = ws[idx - 1] if idx > 0 and ws[idx - 1][2] > run_in[0] - 0.05 else None
                        heard = " ".join(w[0] for w in ws[max(0, idx - 2):idx + 3])
                        if prev_asr is not None:
                            # both ASRs are +-100 ms on word edges, so the window spans both estimates of the killed
                            # word's end and the kept word's start; the envelope's DEEPEST prominent dip inside it is
                            # the gap (a fricative tail or a post-burst dip is shallower)
                            # WhisperX word starts run LATE and ends run EARLY, so [killed.end, kept.start] always
                            # contains the gap; the gap is the last prominent dip in it (the ASR above only decided
                            # that a killed word IS inside this run; its own timestamps are +-100 ms and unusable here)
                            wa = max(run_in[0] + 0.01, cur_in - 0.35, (prev_w["end"] if prev_w else prev_asr[2] - 0.10))
                            wb = min(cur_in + 0.35, (kept_w["start"] - 0.01 if kept_w else onset_asr + 0.02), run_in[1] - 0.01)
                            if wb <= wa + 0.02: wa, wb = min(wa, wb) - 0.03, max(wa, wb) + 0.03
                            dip = last_local_min(env, wa, wb); tmin = dip if dip is not None else minimum_between(env, wa, wb)
                            new_in = pick_min(env, tmin, cur_in, "IN", wa - 0.02, wb + 0.02)
                            d_in += f"; ASR '{heard}': '{prev_asr[0]}' ends {prev_asr[2]:.2f}, '{ws[idx][0]}' starts {onset_asr:.2f}, cut on the dip {tmin:.3f}"
                        elif onset_asr - run_in[0] > 0.25:
                            wa, wb = run_in[0] + 0.02, min(onset_asr + 0.02, run_in[1] - 0.01)
                            dip = last_local_min(env, wa, wb); tmin = dip if dip is not None else minimum_between(env, wa, wb)
                            new_in = pick_min(env, tmin, cur_in, "IN", wa - 0.02, wb + 0.02)
                            d_in += f"; ASR '{heard}': non-speech head, '{ws[idx][0]}' starts {onset_asr:.2f}, cut at {tmin:.3f}"
                        elif prev_w is not None and prev_w["end"] > run_in[0] + 0.02:
                            # the slice ASR heard no killed word, but the aligner ends one INSIDE this run (and WhisperX
                            # ends words early): a word's tail at the head of a slice often goes unheard, and the run's
                            # start is that tail. "people.|No" (2026-10-13, Windows faster-whisper): "the run IS 'no'"
                            # moved the IN -534 ms onto 83.317, and --say of 83.317-84.6 heard "people no longer do".
                            # Fused: cut on the DEEPEST point between the aligner's two words, never the last dip, which
                            # there sat inside the kept word's nasal onset (83.828 against the gap's -56 dB at 83.685).
                            wa = max(run_in[0] + 0.01, cur_in - 0.35, prev_w["end"])
                            wb = min(cur_in + 0.35, k_start - 0.01, run_in[1] - 0.01)
                            if wb <= wa + 0.02: wa, wb = min(wa, wb) - 0.03, max(wa, wb) + 0.03
                            tmin = minimum_between(env, wa, wb)
                            new_in = pick_min(env, tmin, cur_in, "IN", wa - 0.02, wb + 0.02)
                            d_in += (f"; ASR '{heard}' hears no killed word, but the aligner ends '{prev_w['w']}' at "
                                     f"{prev_w['end']:.2f}, inside the run: cut on the dip {tmin:.3f}")
                        else:
                            lo = (prev_end + 0.010) if prev_end is not None else -1e9
                            new_in = pick(run_in[0] - LEAD, lo, run_in[0] - 0.005, cur_in)
                            d_in += f"; ASR '{heard}': the run IS '{ws[idx][0]}' (starts {onset_asr:.2f}), cut {LEAD*1000:.0f} ms before the run"
                        asr_done = True
            if asr_done:
                pass
            elif k_start - run_in[0] <= 0.15 and (prev_w is None or prev_w["end"] <= run_in[0] + 0.02):
                # the run IS the kept word (nothing killed inside it): a clipped attack, cut LEAD before the run
                lo = (prev_end + 0.010) if prev_end is not None else -1e9
                new_in = pick(run_in[0] - LEAD, lo, run_in[0] - 0.005, cur_in)
                d_in += "; attack at the run start"
            elif cur_in <= run_in[0] + 0.03:
                # the run begins well before the word and the cut sits at its head: a breath, kept whole
                v_in = "BREATH"; d_in += "; low-level breath at the head, kept"
            else:
                # something (a killed word, a breath) runs into the kept word: the quietest point between
                # them, preferably a prominent dip, else the global minimum. WhisperX ends run early (the
                # killed word is over at or after prev.end) and starts run late (the attack is at or
                # before kept.start).
                wa = max(run_in[0] + 0.01, cur_in - 0.35, (prev_w["end"] if prev_w else -1e9))
                wb = min(cur_in + 0.35, k_start - 0.01)
                if wb <= wa + 0.02:
                    wa, wb = min(wa, wb) - 0.03, max(wa, wb) + 0.03
                dip = last_local_min(env, wa, wb)
                tmin = dip if dip is not None else minimum_between(env, wa, wb)
                new_in = pick_min(env, tmin, cur_in, "IN", wa - 0.02, wb + 0.02)
                who = f"'{prev_w['w']}'|'{kept_w['w']}'" if prev_w and kept_w else "run"
                d_in += f"; {'dip' if dip is not None else 'minimum'} {who} at {tmin:.3f}"
            if disp_in is not None and c_in_new is None and abs(new_in - cur_in) > 0.004:
                # a disputed word at the cut: the segment's reading was measured, never applied (see neighbours_in)
                d_in += held(disp_in, "IN", new_in)
                new_in, v_in, held_in = cur_in, "CLIP", True
        elif v_in == "OK" and onset is not None and onset - cur_in < LEAD - 0.005:
            lo = (prev_end + 0.010) if prev_end is not None else -1e9
            ideal = onset - LEAD
            if ideal < lo:
                # the full lead does not fit before the previous run: only a bleed or a near-zero lead moves
                # (a 20-40 ms lead in a tight gap is what the speaker left; churning it a frame is not a repair)
                if onset - cur_in < 0.020:
                    tmin = minimum_between(env, prev_end - 0.02, onset + 0.02)
                    new_in = pick_min(env, tmin, cur_in, "IN", prev_end - 0.03, onset)
            else:
                new_in = pick(ideal, lo, onset - 0.005, cur_in)
        # OUT: same policy (cut in speech, next word audible, tail < TAIL); a landed line keeps up to BEAT_TAIL
        new_out = cur_out
        tail_t = BEAT_TAIL if s.get("beat") else TAIL
        cont_next = i + 1 < len(segs) and os.path.basename(segs[i + 1]["clip"]) == c and abs(segs[i + 1]["start"] - s["end"]) < 0.002

        def past_kept_word(new, kept_w, v, d):
            """A move to the run's end is only a repair when the run IS the kept word. Past BEAT_TAIL beyond
            the kept word's aligner end it must be HEARD: an OUT was moved +667 ms into breath and room tone
            past the beat cap and pinned by hand (2026-09-20). Heard (heard_past) -> the move stands; else the
            cut stays, verdict BREATH, with a ⚠. A cut INSIDE the kept word (before its aligner end) is
            neither: heard_past cannot tell the word's own completion from speech past it, and staying keeps
            a cut in speech out of the count. It is CAPPED at the word's end + tail, still CLIP, with a ⚠.
            Always the ALIGNER's end, never the slice ASR's: its word ends are loose and stretch into the
            breath (an ASR end of 1.84 on a word the aligner ends at 1.45 moved the OUT +617 ms, 2026-09-23)."""
            k_end = kept_w["end"] if kept_w else cur_out - 0.05
            w_end = k_end
            if new - w_end <= BEAT_TAIL + 1e-6:
                return new, v, d
            if cur_out < w_end - 0.005:
                capped = pick(w_end + tail_t, w_end + 0.020, new, cur_out)
                return capped, v, d + (f"; ⚠ the cut is inside the kept word: capped at its end {w_end:.2f} + "
                                       f"{1000*tail_t:.0f} ms, the run past it looks like breath/room tone: verify "
                                       f"(would have moved {1000*(new-cur_out):+.0f} ms, {1000*(new-w_end):.0f} ms past its end)")
            heard = heard_past(media_dir / c, cur_out, new, scratch) if a.asr != "off" else None
            if heard:
                return new, v, d + f"; the ASR hears a word past the kept word ({1000*(new-k_end):.0f} ms past its aligner end)"
            why = "ASR off" if a.asr == "off" else ("ASR unavailable" if heard is None else "the ASR hears no word in it")
            return cur_out, "BREATH", d + (f"; ⚠ run past the kept word looks like breath/room tone: verify ({why}; "
                                           f"would have moved {1000*(new-cur_out):+.0f} ms, {1000*(new-k_end):.0f} ms past its aligner end)")

        if v_out == "CLIP":
            kept_w, next_w, disp_out = neighbours_out(c, cur_out, s_out)
            k_end = kept_w["end"] if kept_w else cur_out - 0.05
            asr_done = False
            if a.asr != "off":
                toks = [x for x in (norm(y) for y in s_out.get("transcript", "").split()) if x]
                kt, kt0 = (toks[-1] if toks else ""), (toks[-2] if len(toks) > 1 else "")
                ws = asr_words(media_dir / c, max(run_out[0], cur_out - 1.5) - 0.05, run_out[1] + 0.05, scratch)
                if ws and kt:
                    cands = [k for k in range(len(ws) - 1, -1, -1) if tok_match(ws[k][0], kt) and ws[k][2] <= run_out[1] + 0.15]
                    two = [k for k in cands if k > 0 and tok_match(ws[k - 1][0], kt0)] if kt0 else []
                    pool = two or cands
                    idx = min(pool, key=lambda k: abs(ws[k][2] - cur_out)) if pool else None
                    if idx is not None:
                        decay_asr = ws[idx][2]
                        next_asr = ws[idx + 1] if idx + 1 < len(ws) and ws[idx + 1][1] < run_out[1] + 0.05 else None
                        heard = " ".join(w[0] for w in ws[max(0, idx - 2):idx + 3])
                        if next_asr is not None:
                            wa = max(run_out[0] + 0.01, cur_out - 0.35, (kept_w["end"] if kept_w else decay_asr - 0.02))
                            wb = min(run_out[1] - 0.01, cur_out + 0.35, (next_w["start"] + 0.03 if next_w else next_asr[1] + 0.10))
                            if wb <= wa + 0.02: wa, wb = min(wa, wb) - 0.03, max(wa, wb) + 0.03
                            dip = last_local_min(env, wa, wb); tmin = dip if dip is not None else minimum_between(env, wa, wb)
                            new_out = pick_min(env, tmin, cur_out, "OUT", wa - 0.02, wb + 0.02)
                            d_out += f"; ASR '{heard}': '{ws[idx][0]}' ends {decay_asr:.2f}, '{next_asr[0]}' starts {next_asr[1]:.2f}, cut on the dip {tmin:.3f}"
                        elif run_out[1] - decay_asr > 0.25:
                            wa, wb = max(decay_asr - 0.02, run_out[0] + 0.01), run_out[1] - 0.01
                            dip = last_local_min(env, wa, wb); tmin = dip if dip is not None else minimum_between(env, wa, wb)
                            new_out = pick_min(env, tmin, cur_out, "OUT", wa - 0.02, wb + 0.02)
                            d_out += f"; ASR '{heard}': non-speech tail after '{ws[idx][0]}' (ends {decay_asr:.2f}), cut at {tmin:.3f}"
                            if disp_out is None:        # the run's last dip can sit deep in breath/room tone: capped the same way
                                new_out, v_out, d_out = past_kept_word(new_out, kept_w, v_out, d_out)
                        else:
                            hi = (next_on - 0.010) if next_on is not None else 1e9
                            new_out = pick(run_out[1] + tail_t, run_out[1] + 0.020, hi, cur_out)
                            d_out += f"; ASR '{heard}': the run ends with '{ws[idx][0]}' ({decay_asr:.2f}), cut {tail_t*1000:.0f} ms after the run"
                            if disp_out is None:        # a disputed cut is held below, whatever the run holds
                                new_out, v_out, d_out = past_kept_word(new_out, kept_w, v_out, d_out)
                        asr_done = True
            if asr_done:
                pass
            elif next_w is None or next_w["start"] >= run_out[1]:
                # the run ends with the kept word (the killed word starts after it): a clipped decay, cut TAIL after the run
                hi = (next_on - 0.010) if next_on is not None else 1e9
                new_out = pick(run_out[1] + tail_t, run_out[1] + 0.020, hi, cur_out)
                d_out += "; decay at the run end"
                if disp_out is None:                    # a disputed cut is held below, whatever the run holds
                    new_out, v_out, d_out = past_kept_word(new_out, kept_w, v_out, d_out)
            else:
                wa = max(cur_out - 0.35, k_end)
                wb = min(run_out[1] - 0.01, cur_out + 0.35, next_w["start"] + 0.03)
                if wb <= wa + 0.02:
                    wa, wb = min(wa, wb) - 0.03, max(wa, wb) + 0.03
                dip = last_local_min(env, wa, wb)
                tmin = dip if dip is not None else minimum_between(env, wa, wb)
                new_out = pick_min(env, tmin, cur_out, "OUT", wa - 0.02, wb + 0.02)
                who = f"'{kept_w['w']}'|'{next_w['w']}'" if kept_w and next_w else "run"
                d_out += f"; {'dip' if dip is not None else 'minimum'} {who} at {tmin:.3f}"
            if disp_out is not None and c_out_new is None and abs(new_out - cur_out) > 0.004:
                # a disputed word at the cut: the segment's reading was measured, never applied (see neighbours_in)
                d_out += held(disp_out, "OUT", new_out)
                new_out, v_out, held_out = cur_out, "CLIP", True
        elif v_out == "OK" and decay is not None and cur_out - decay < tail_t - 0.005:
            hi = (next_on - 0.010) if next_on is not None else 1e9
            ideal = decay + tail_t
            if ideal > hi:
                if cur_out - decay < 0.030:
                    tmin = minimum_between(env, decay - 0.02, next_on + 0.02)
                    new_out = pick_min(env, tmin, cur_out, "OUT", decay, next_on + 0.03)
            else:
                new_out = pick(ideal, decay + 0.020, hi, cur_out)
        elif v_out == "OK" and decay is not None and not cont_next and \
                cur_out - decay > (BEAT_TAIL if s.get("beat") else TAIL + LONG_OVER) + 0.001:
            # a LONG tail is dead air the next lead adds to: "ok tail 390 ms" passed here and failed
            # dead-air-qa at the joint (2026-09-20). Trimmed to decay + TAIL / BEAT_TAIL on the grid; a tail
            # already on the grid frame nearest that ideal does not move (and is not LONG), so no churn.
            cand = pick(decay + tail_t, decay + 0.020, cur_out, cur_out)
            if abs(cand - cur_out) > 0.004:
                cap = BEAT_TAIL if s.get("beat") else TAIL + LONG_OVER
                new_out, v_out = cand, "LONG"
                d_out += f", over the {1000*cap:.0f} ms cap: trimmed to decay + {1000*tail_t:.0f} ms"
        # a CLIP whose repair leaves the cut where it is sits on the dip: FUSED. A HELD one was never repaired:
        # it stays CLIP, in the count, the touched set and the sheet
        if v_in == "CLIP" and not held_in and abs(new_in - cur_in) < 0.004:
            v_in = "FUSED"
        if v_out == "CLIP" and not held_out and abs(new_out - cur_out) < 0.004:
            v_out = "FUSED"
        if c_in_new is not None:
            new_in, v_in = c_in_new, "CONTENT"
        if c_out_new is not None:
            new_out, v_out = c_out_new, "CONTENT"
        new_in, d_in = pinned_boundary(s.get("pin_in"), cur_in, new_in, d_in)
        new_out, d_out = pinned_boundary(s.get("pin_out"), cur_out, new_out, d_out)
        # a continuous split (next segment starts where this one ends) shares one boundary: keep the pair together
        if i + 1 < len(segs) and os.path.basename(segs[i + 1]["clip"]) == c and abs(segs[i + 1]["start"] - s["end"]) < 0.002:
            new_out = s["end"]
        if i > 0 and os.path.basename(segs[i - 1]["clip"]) == c and abs(segs[i - 1]["end"] - s["start"]) < 0.002:
            new_in = s["start"]
        # A --live readback that disagrees with the EDL by more than a frame is the creator's HAND EDIT
        # (a stutter trimmed out, a false start killed), never a lane quantization: report the delta and
        # leave it alone — the repo law, CLAUDE.md § live state that disagrees. This tool re-derives every
        # boundary from the envelope, so without it a hand trim is re-extended on every pass (a "use, use"
        # stutter came back twice, 769.686 -> 770.603, your-job 2026-09-18). Pin it in the EDL to make it
        # stick without a readback: "pin_in" / "pin_out" above. A verdict already reached survives the
        # tag (hand_edit): a hand-trimmed boundary can ALSO be a cut inside speech, and both are reported.
        h_in = h_out = False
        if live:
            tol = (grid or 0.042) + 1e-6
            v_in, d_in, h_in = hand_edit(v_in, d_in, cur_in, float(s["start"]), tol)
            v_out, d_out, h_out = hand_edit(v_out, d_out, cur_out, float(s["end"]), tol)
            if h_in:
                new_in = cur_in
            if h_out:
                new_out = cur_out
        moved_in = abs(new_in - cur_in) > 0.004
        moved_out = abs(new_out - cur_out) > 0.004
        rows.append(dict(i=i, clip=c, cur_in=cur_in, cur_out=cur_out, new_in=new_in, new_out=new_out,
                         v_in=v_in, d_in=d_in, v_out=v_out, d_out=d_out, onset=onset, prev_end=prev_end,
                         decay=decay, next_on=next_on, thr_in=thr_in, thr_out=thr_out, h_in=h_in, h_out=h_out,
                         held_in=held_in, held_out=held_out))
        # `CLIP*` = the creator also trimmed this boundary by hand: the defect stands, nothing moves
        flag_in = (v_in + "*" if h_in and v_in in DEFECTS else v_in) if v_in != "OK" else ("moved" if moved_in else "ok")
        flag_out = (v_out + "*" if h_out and v_out in DEFECTS else v_out) if v_out != "OK" else ("moved" if moved_out else "ok")
        print(f"seg{i:02d} IN  {cur_in:9.3f} {flag_in:6s} {d_in:55s} -> {new_in:9.3f} ({1000*(new_in-cur_in):+5.0f} ms)")
        print(f"      OUT {cur_out:9.3f} {flag_out:6s} {d_out:55s} -> {new_out:9.3f} ({1000*(new_out-cur_out):+5.0f} ms)")
        if moved_in or moved_out or v_in not in ("OK", "FUSED", "BREATH", "HAND") or v_out not in ("OK", "FUSED", "BREATH", "HAND"):
            changed.append(i)

    # a repair may push one segment's in before its source-neighbour's out (the same frames would play
    # twice): the pair then shares ONE boundary, the later segment's in-point
    for k in range(len(rows) - 1):
        p, q = rows[k], rows[k + 1]
        if p.get("media") or q.get("media"):
            continue
        if p["clip"] == q["clip"] and q["new_in"] < p["new_out"] and q["new_in"] > p["new_in"]:
            print(f"seg{k:02d}/seg{k + 1:02d} overlap {1000 * (p['new_out'] - q['new_in']):.0f} ms -> shared boundary {q['new_in']:.3f}")
            p["new_out"] = q["new_in"]
            if k not in changed: changed.append(k)

    # THE JOINT GATE: the proposed EDL through dead-air-qa.py's own quiet-run test (its envelope, floor,
    # threshold, spike bridging and 0.65 s, imported), so a joint whose tail plus the next lead reach
    # 0.65 s of quiet on the timeline is named HERE, before the replay, not by dead-air-qa after it
    prop = [dict(clip=r["clip"], start=float(r["new_in"]), end=float(r["new_out"]), media=r.get("media")) for r in rows]
    quiet, _, _ = dq.scan(prop, lambda cut: dqlev[cut["clip"]], say=lambda m: None)
    tl0, t_ = [], 0.0
    for cut in prop:
        tl0.append(t_); t_ += cut["end"] - cut["start"]
    n_joint = 0
    for f in quiet:
        i, j = f["segment"], f["end_segment"]
        if i != j:
            n_joint += 1
            tail, lead = tl0[j] - f["start"], f["end"] - tl0[j]
            print(f"⚠ seg{i:02d}/seg{j:02d} joint: {1000*f['duration']:.0f} ms quiet across it on the timeline (tail "
                  f"{1000*tail:.0f} ms + lead {1000*lead:.0f} ms): dead-air-qa fails it, trim one side")
        else:
            where = "at its tail" if f["end"] >= tl0[i] + prop[i]["end"] - prop[i]["start"] - 2 * dq.HOP else \
                    ("at its head" if f["start"] <= tl0[i] + 2 * dq.HOP else "inside it")
            print(f"⚠ seg{i:02d}: {1000*f['duration']:.0f} ms quiet {where} (source {f['source_start']:.3f}): dead-air-qa fails it")

    n_bad = sum(1 for r in rows if r["v_in"] in DEFECTS) + sum(1 for r in rows if r["v_out"] in DEFECTS)
    n_hand = sum(1 for r in rows if r["h_in"]) + sum(1 for r in rows if r["h_out"])
    n_hand_bad = sum(1 for r in rows if r["h_in"] and r["v_in"] in DEFECTS) + sum(1 for r in rows if r["h_out"] and r["v_out"] in DEFECTS)
    n_short = sum(1 for r in rows if r["v_in"] == "OK" and abs(r["new_in"] - r["cur_in"]) > 0.004) + \
              sum(1 for r in rows if r["v_out"] == "OK" and abs(r["new_out"] - r["cur_out"]) > 0.004)
    n_long = sum(1 for r in rows if r["v_out"] == "LONG" and abs(r["new_out"] - r["cur_out"]) > 0.004)
    n_breath = sum(1 for r in rows if r["v_out"] == "BREATH")
    n_held = sum(1 for r in rows if r["held_in"]) + sum(1 for r in rows if r["held_out"])
    n_media = sum(1 for r in rows if r.get("media"))
    print(f"[cut-audit] {len(segs)} segments · {n_bad} boundaries in speech"
          + (f" ({n_held} held: the aligner and the transcript disagree on a word at the cut, verify by ear)" if n_held else "")
          + f" · {n_short} leads/tails widened · "
          f"{n_long} long tails trimmed · {len(changed)} segments touched"
          + (f" · {n_breath} OUTs past the kept word left in place (⚠ verify: breath/room tone?)" if n_breath else "")
          + (f" · {len(quiet)} quiet runs >= 0.65 s ({n_joint} across joints): dead-air-qa will fail them" if quiet else "")
          + (f" · {n_media} laid from substitute media, not audited" if n_media else "")
          + (f" · {n_hand} hand edits left alone ({n_hand_bad} of them in speech: re-cut by hand or drop the trim)" if n_hand else ""))
    # a content check the slice ASR could not run is a cut nobody verified, never a clean one: say so, exit 3
    status = 0
    if _asr_dead[0]:
        status = 3
        print(f"[cut-audit] UNVERIFIED: the slice ASR could not run ({_asr_dead[0]}), so the content gate and the "
              "aligner-gap splits fell back to the envelope. Fix the engine (workflows/asr_cli.py) and re-run, or "
              "record this cut as unverified")

    if a.write or a.promote:
        out = {"segments": []}
        for r, s in zip(rows, segs):
            ns = dict(s)
            ns["start"] = round(float(r["new_in"]), 5)
            ns["end"] = round(float(r["new_out"]), 5)
            ns["no_refine"] = True
            out["segments"].append(ns)
        # a shared boundary stays shared after snapping
        for k in range(len(out["segments"]) - 1):
            p, q = out["segments"][k], out["segments"][k + 1]
            if p.get("media") or q.get("media"):
                continue
            if p["clip"] == q["clip"] and abs(segs[k + 1]["start"] - segs[k]["end"]) < 0.002:
                q["start"] = p["end"]
        if a.promote and target.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            bak = target.with_name(f"cuts.pre-audit-{stamp}.json")
            n = 2
            while bak.exists():
                bak = target.with_name(f"cuts.pre-audit-{stamp}-{n}.json"); n += 1
            shutil.copy2(target, bak)
            print(f"[cut-audit] backed up {target} -> {bak}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"[cut-audit] wrote {target}")
        if a.promote:
            # the canonical transcript follows the promoted EDL; never splice.sh here, whose frame-snap is to
            # the SOURCE grid and would undo a --grid placement (rough-cut § Audit the cut)
            print("[cut-audit] next, re-derive the canonical transcript from it:\n"
                  f"  uv run .claude/skills/rough-cut/scripts/export-transcript.py {Path(words_path).as_posix()} "
                  f"{Path(target).as_posix()} {(job / 'outputs' / (job.resolve().name + '.transcript.json')).as_posix()}")
            # (as_posix: the line is pasted into a shell, and Git Bash drops the separators of a backslashed path)

    if a.sheet:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        items = []
        for r in rows:
            if (a.all or r["i"] in changed) and not r.get("media"):
                items.append((r, "IN")); items.append((r, "OUT"))
        if not items:
            print("[cut-audit] nothing to sheet"); return status
        cols = 4
        nrows = (len(items) + cols - 1) // cols
        fig, axes = plt.subplots(nrows, cols, figsize=(cols * 4.2, nrows * 1.9), squeeze=False)
        for ax, (r, side) in zip(axes.flat, items):
            env = envs[r["clip"]]
            t = r["cur_in"] if side == "IN" else r["cur_out"]
            t2 = r["new_in"] if side == "IN" else r["new_out"]
            w0, w1 = t - 0.6, t + 0.6
            i0, i1 = max(0, int(w0 / HOP)), min(len(env), int(w1 / HOP))
            xs = np.arange(i0, i1) * HOP
            ax.fill_between(xs, -70, env[i0:i1], color="#5b8def", lw=0)
            ax.axhline(r["thr_in"] if side == "IN" else r["thr_out"], color="#999", lw=0.6, ls=":")
            ax.axvline(t, color="#e0443e", lw=1.2)
            ax.axvline(t2, color="#2fb35a", lw=1.2, ls="--")
            keep = (t2, w1) if side == "IN" else (w0, t2)
            ax.axvspan(*keep, color="#2fb35a", alpha=0.08)
            v = (r["v_in"] if side == "IN" else r["v_out"]) + ("*" if (r["h_in"] if side == "IN" else r["h_out"]) else "")
            ax.set_title(f"seg{r['i']:02d} {side} {t:.3f}→{t2:.3f} {v}", fontsize=8)
            ax.set_ylim(-70, -10); ax.set_xlim(w0, w1); ax.tick_params(labelsize=6)
        for ax in list(axes.flat)[len(items):]:
            ax.axis("off")
        fig.tight_layout()
        fig.savefig(a.sheet, dpi=110)
        print(f"[cut-audit] sheet {a.sheet} ({len(items)} panels; red = current cut, green = repaired, shaded = kept)")
    return status


if __name__ == "__main__":
    sys.exit(main())
