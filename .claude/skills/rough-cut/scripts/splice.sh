#!/usr/bin/env bash
# splice.sh — cuts + concatenates clips per cuts.json
# usage: splice.sh <job_dir>
# reads:  /tmp/video-editor/<job-name>/cuts.json
# writes: projects/<job-name>/outputs/<job-name>.mp4

set -euo pipefail

# Python launcher, probed by RUNNING it: macOS/Linux have `python3`; Windows installs it
# as `python` (and ships a fake `python3` Store stub that only opens the Microsoft Store,
# which `command -v` can't see through).
PY=python3; "$PY" -c '' 2>/dev/null || PY=python
# Windows pipes default python stdio to cp1252, which can't encode the ⚠/→/✓ glyphs the
# pipeline's status lines use; export-transcript.py died mid-splice on a real job
# (2026-08-13). UTF-8 mode fixes stdio AND default open() encoding; no-op on macOS/Linux.
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

JOB_DIR="${1:?usage: splice.sh <job_dir>}"
JOB_DIR="$(cd "$JOB_DIR" && pwd)"
JOB_NAME="$(basename "$JOB_DIR")"
WORK="/tmp/video-editor/$JOB_NAME"
MEDIA_DIR="$JOB_DIR"
[ -d "$JOB_DIR/raw" ] && MEDIA_DIR="$JOB_DIR/raw"
OUT="$JOB_DIR/outputs"
CUTS="$WORK/cuts.json"
mkdir -p "$WORK" "$OUT"

[ -f "$CUTS" ] || { echo "missing $CUTS" >&2; exit 1; }

# SCRATCH OWNER. $WORK is keyed by the job folder's NAME, so every job with that name shares it (section sub-jobs:
# sections/intro exists in several jobs) and its cuts.json can be ANOTHER job's EDL, spliced over this job's raw and
# copied over its transcript/cuts.json (2026-10-02). $WORK/.job-path names the job last spliced from it; a cuts.json
# not written since that job's splice is that job's EDL. Resolved by $PY so polish-boundaries.py reads the same form.
JOB_REAL="$("$PY" -c 'import os,sys; sys.stdout.write(os.path.realpath(sys.argv[1]))' "$JOB_DIR")"
OWNER="$WORK/.job-path"
if [ -f "$OWNER" ] && [ "$(cat "$OWNER")" != "$JOB_REAL" ]; then
  if [ ! "$CUTS" -nt "$OWNER" ]; then
    echo "[splice] ✗ $WORK is shared by every job named $JOB_NAME. It was last spliced for $(cat "$OWNER")" >&2
    echo "    and its cuts.json is unchanged since: that job's EDL. cp THIS job's EDL to $CUTS first." >&2
    exit 2
  fi
  echo "[splice] ⚠ $WORK was last spliced for $(cat "$OWNER"); its cuts.json was written since and is spliced" >&2
  echo "    as THIS job's EDL ($JOB_REAL). If it is not, stop and cp this job's EDL to $CUTS." >&2
fi

# EDL OVERWRITE GUARD. This splice ends by copying the EDL it spliced over transcript/cuts.json. When that file
# changed after the last splice (cut-audit.py --promote, live-edl.py --write, a hand edit) and the /tmp EDL is not
# that file, the copy would silently replace the newer cut with a stale one. The stamp lives in the job folder
# (transcript/cuts.splice.sha1), never in /tmp: polish-boundaries.py deletes cuts.snapped.json.
sha1_of() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 1 "$1" | cut -d' ' -f1
  else "$PY" -c 'import hashlib,sys; print(hashlib.sha1(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; fi
}
JOB_EDL="$JOB_DIR/transcript/cuts.json"; STAMP="$JOB_DIR/transcript/cuts.splice.sha1"
if [ -f "$JOB_EDL" ] && [ -f "$STAMP" ] && [ "$(sha1_of "$JOB_EDL")" != "$(cat "$STAMP")" ] \
   && ! cmp -s "$WORK/cuts.json" "$JOB_EDL"; then
  echo "[splice] ✗ transcript/cuts.json was written after the last splice (cut-audit --promote, live-edl --write or a" >&2
  echo "    hand edit): cp it to $WORK/cuts.json first, or this splice would overwrite it." >&2
  echo "    job EDL: $JOB_EDL" >&2
  echo "    /tmp EDL: $WORK/cuts.json" >&2
  exit 2
fi
printf '%s' "$JOB_REAL" > "$OWNER"

# BOUNDARY REFINE — measured onset/offset dial-in (refine-cuts.py). WhisperX word
# START timestamps run ~50-100 ms late vs the real acoustic attack, so cuts authored
# at word.start-minus-pad still land INSIDE the word and clip its onset (a real job
# shipped a sentence-opening word with its first 48 ms missing); word ENDS run
# early the same way and clip decays. The refiner measures each chosen word's
# acoustic edge on the raw audio (5 ms RMS envelope) and moves the cut just outside
# it — in = onset−40 ms, out = offset+50 ms — clamped inside the local gap so it can
# never cross an adjacent word. Cut CHOICE stays Claude's; this only dials the
# boundary of the word already chosen (never snapping a cut to the nearest silence —
# the "don't auto-snap to silence" gotcha still stands). REFINE=0 skips the pass;
# "no_refine": true on a segment skips just that segment.
WORDS_SRC="$JOB_DIR/transcript/words.json"; [ -f "$WORDS_SRC" ] || WORDS_SRC="$WORK/words.json"
if [ "${REFINE:-1}" != "0" ] && [ -f "$WORDS_SRC" ]; then
  if "$PY" "$(dirname "$0")/refine-cuts.py" "$MEDIA_DIR" "$WORDS_SRC" "$CUTS" "$WORK/cuts.refined.json"; then
    CUTS="$WORK/cuts.refined.json"
  else
    echo "[splice] ⚠ refine-cuts failed — splicing authored cuts.json unrefined" >&2
  fi
fi

# cuts.json schema:
# { "segments": [ { "clip": "clip-01.mov", "start": 1.2, "end": 4.8 }, ... ] }

# SINGLE-PASS CLEAN SPLICE — cut + concat happen in ONE ffmpeg filtergraph, and the audio
# polish (static gain → hard limiter) is applied exactly ONCE to the assembled track, then
# encoded to AAC exactly ONCE. This is the "cut from raw, master once at the end" order:
#   • Audio rides through the cut LOSSLESS (PCM in the filtergraph) — NEVER encoded per-segment.
#     The old approach encoded each segment to AAC, copy-concatenated those AAC chunks (each join
#     splices in ~1024+ samples of AAC encoder priming = a tiny CLICK at every cut), then encoded
#     AAC a 2nd time. Two lossy generations + a click per boundary on pristine PCM source audio.
#     Processing per-segment before assembly is the bug; processing once after assembly is the fix.
#   • A/V stay LOCKED by construction: video and audio are trimmed from the SAME in/out points in
#     the same graph and concatenated together — no independent rebuild that could drift.
#   • trim/setpts rebases the first frame to pts 0 (no empty edit / QuickTime black-flash), verified.
#
# Audio chain — STATIC gain + hard limiter (your Premiere move). NOT loudnorm: single-pass
#   loudnorm runs DYNAMIC (rides gain over time) and PUMPS. This is static + transparent: constant
#   +AMPLIFY_DB gain, peaks brickwalled at −6 dBFS, zero time-varying leveling. Raw record level is
#   ~−30 dB mean, which is what the gain is calibrated against. `level=disabled` is REQUIRED —
#   alimiter's auto-level defaults ON and re-normalizes loud (clips to +TP / crushes LRA);
#   limit=0.501 = −6 dBFS. AMPLIFY_DB is the only loudness knob and, unset, it is MEASURED:
#   workflows/voice-gain.py puts the raw's kept speech at −17 LUFS integrated pre-limiter (locked
#   2026-09-03 off your-job, where +15 was perfect — you like the limiter working hard,
#   which reverses the 2026-06-28 "+15 too hard" call). AMPLIFY_DB overrides it, which is a DEVIATION
#   from the locked measurement: stated in the report and written into RUN.md, never a way round a
#   failed measurement (LANES.md § step 3 owns the rule).
"$PY" - "$MEDIA_DIR" "$CUTS" "$OUT/${JOB_NAME}.mp4" "$JOB_DIR" "$(cd "$(dirname "$0")/../../../.." && pwd)" <<'PY'
import json, os, sys, subprocess, platform
media_dir, cuts_path, out_path, job_dir, repo = sys.argv[1:]
render = os.environ.get("RENDER", "1") != "0"
with open(cuts_path) as f:
    segs = json.load(f)["segments"]
if not segs:
    raise SystemExit("cuts.json has no segments")

# One -i per unique clip; segments reference the right input index.
inputs, idx = [], {}
def input_index(clip):
    p = clip if os.path.isabs(clip) else os.path.join(media_dir, clip)
    if not os.path.exists(p):
        raise SystemExit(f"clip not found: {p}")
    if p not in idx:
        idx[p] = len(inputs); inputs.append(p)
    return idx[p]

kept = {}
for seg in segs:                     # every clip found before anything is measured; the main take carries the most
    k = input_index(seg["clip"])
    kept[k] = kept.get(k, 0.0) + float(seg["end"]) - float(seg["start"])
main = max(range(len(inputs)), key=lambda k: kept[k])


def video_stream(path):
    # json: ffprobe 9 prints a timecoded file's video row twice in the text formats
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,color_transfer:stream_side_data=rotation", "-of", "json", path],
                         capture_output=True, text=True).stdout
    return (json.loads(out or "{}").get("streams") or [{}])[0]


def decoded_size(st):
    """(width, height) as ffmpeg DECODES the clip: it autorotates, so a rotation of ±90 swaps the coded pair."""
    rot = next((int(d["rotation"]) for d in st.get("side_data_list") or [] if "rotation" in d), 0)
    return (st["height"], st["width"]) if abs(rot) % 180 == 90 else (st["width"], st["height"])


def audio_channels(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels",
                          "-of", "json", path], capture_output=True, text=True).stdout
    try:
        return int(json.loads(out or "{}")["streams"][0]["channels"])
    except (ValueError, KeyError, IndexError, TypeError):
        return 2


# HDR IS NEVER RENDERED HERE. An iPhone records HLG (10-bit, BT.2020) by default; this 8-bit encode kept those tags
# with no tone map, so the deliverable shipped 8-bit "HDR" with SDR graphics over it, against the presets' Rec.709
# export (2026-10-13 audit). The stock ffmpeg builds carry no tone mapper that reads HLG (no zscale, no libplacebo),
# so the render stops and names the clip. RENDER=0 (the EDL every app finish replays) is unaffected: an app's colour
# management maps HDR onto its Rec.709 sequence.
streams = [video_stream(p) for p in inputs] if render else []
hdr = [(p, s["color_transfer"]) for p, s in zip(inputs, streams)
       if s.get("color_transfer") in ("arib-std-b67", "smpte2084")]
if hdr:
    raise SystemExit(
        "[splice] ✗ HDR footage: "
        + ", ".join(f"{os.path.basename(p)} ({'HLG' if t == 'arib-std-b67' else 'PQ'})" for p, t in hdr)
        + ".\n    This render is 8-bit Rec.709 only, and it would ship the HDR tags with no tone map (banding, wrong"
        "\n    colour, SDR graphics over HDR pixels). Finish the job in an editing app (its colour management maps HDR"
        "\n    onto a Rec.709 sequence), or convert the clip to Rec.709 SDR once, as a new file in raw/, and point"
        "\n    cuts.json at it. On an iPhone, Settings > Camera > Record Video > HDR Video off records SDR.")

amp = os.environ.get("AMPLIFY_DB")
if not amp and not render:
    amp = "0"   # EDL-only mode never renders, so the gain is never applied here; step 3 measures its own
if not amp:
    # the measured gain (kept speech -> -17 LUFS pre-limiter); a failure here is loud, never a silent +10.
    # Resolved from the REPO root, not the cuts path: cuts live in /tmp/video-editor/<job>/ (2026-09-03 fix).
    # Measured on the EDL this splice renders (--edl: the refined one when refine ran), never on a
    # transcript/cuts.json from an earlier splice, or missing on a first one (a fresh clipper clip).
    vg = os.path.join(repo, "workflows", "voice-gain.py")
    r = subprocess.run(["uv", "run", vg, job_dir, "--json", "--edl", cuts_path], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("voice-gain.py failed - FIX it; AMPLIFY_DB overrides the locked measurement "
                         "and must be announced:\n" + (r.stderr or r.stdout))
    vg_res = json.loads(r.stdout)
    amp = str(vg_res["gain_db"])
    print(f"[splice] AMPLIFY_DB measured: {amp} dB (voice-gain.py)")
    if vg_res.get("warn"):      # a raw far off a normal shoot: the measurement's own caveat reaches the log
        print(f"[splice] ⚠ voice-gain: {vg_res['warn']}")

# FRAME-GRID SNAP — the silence-gap fix. Video trim keeps whole frames while atrim cuts
# sample-exact, so un-snapped fractional cut times give every segment a video duration up
# to ±1 frame different from its audio duration. concat (v=1:a=1) then pads the shorter
# audio with DIGITAL ZEROS at each joint — measured +120 ms of inserted silence across one
# real 16-segment job: audible room-tone dropouts, extra click edges, and a progressive
# timeline stretch that desyncs the transcript/captions (the long-standing "render cut
# drift"). Snapping every boundary to the video frame grid makes video and audio durations
# IDENTICAL per segment: concat pads nothing, joints are pure (faded) butt-joins, and the
# output timeline equals the snapped cuts.json exactly.
STD_RATES = ((24000, 1001), (24, 1), (25, 1), (30000, 1001), (30, 1), (48000, 1001), (48, 1), (50, 1), (60000, 1001),
             (60, 1), (100, 1), (120000, 1001), (120, 1))


def video_fps(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=r_frame_rate,avg_frame_rate", "-of", "json", path],
                         capture_output=True, text=True).stdout
    # json, not csv: iPhone .MOV footage carries stream side data, which the csv writer emits as extra
    # elements/rows ("30000/1001," with a trailing comma crashed int() once, 2026-08-13, real job)
    st = json.loads(out or "{}").get("streams", [{}])[0]
    num, den = (int(x) for x in st["r_frame_rate"].split("/"))
    try:
        an, ad = (int(x) for x in st.get("avg_frame_rate", "0/0").split("/"))
        avg = an / ad
    except (ValueError, ZeroDivisionError):
        avg = 0.0
    # The grid below snaps every boundary AND conforms the stream to it (fps=), so a nonsense r_frame_rate would
    # multiply frames: a heavily jittered test file read r 30000/1 and a 0.3 s segment rendered 9000 frames
    # (2026-09-27). Only a nominal rate that is BOTH off every standard rate and not backed by the average (off by more
    # than 2%) gives way to the standard rate nearest the average: a QuickTime screen recording at r 60/1 whose static
    # stretches write fewer frames (avg 30) keeps its 60 grid, a 15 fps capture keeps 15, and a phone take's r
    # 30000/1001 against avg 29.977 stays as it is.
    std = any(abs(num / den - a / b) < 1e-3 for a, b in STD_RATES)
    if avg > 0 and not std and abs(num / den - avg) / avg > 0.02:
        sn, sd = min(STD_RATES, key=lambda r: abs(r[0] / r[1] - avg))
        print(f"[splice] ⚠ {os.path.basename(path)}: r_frame_rate {num}/{den} is not backed by its average "
              f"{avg:.3f} fps: the grid is {sn}/{sd}", file=sys.stderr)
        return sn, sd
    return num, den

# ONE CANVAS, ONE GRID. concat takes one frame size, and a facecam beside a screen recording (or an A and a B camera)
# killed the render at the concat after RENDER=0 and the polish had passed (2026-10-13 audit); a clip at another rate
# rendered on its own grid left the stream VFR and the cut a frame off its EDL. So the render puts every segment on the
# main take's canvas (the clip carrying the most kept time), letterboxed, never cropped, and snaps every boundary to
# the main take's grid, which the snapped EDL then records. RENDER=0 keeps each clip on its own grid.
grid, fit = None, ""
if render:
    grid = video_fps(inputs[main])
    sizes = [decoded_size(s) for s in streams]
    W, H = sizes[main]
    rates = {video_fps(p) for p in inputs}
    if len(set(sizes)) > 1 or len(rates) > 1:
        fit = (f",scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1"
               if len(set(sizes)) > 1 else "")
        print(f"[splice] ⚠ the clips differ in " + " and ".join(x for x, d in (("size", len(set(sizes)) > 1),
              ("rate", len(rates) > 1)) if d) + f": every segment renders on {os.path.basename(inputs[main])}'s "
              f"{W}x{H} at {grid[0]}/{grid[1]} (the clip carrying the most kept time)"
              + "".join(f"; {os.path.basename(p)} {w}x{h} letterboxed" for p, (w, h) in zip(inputs, sizes)
                        if (w, h) != (W, H)), file=sys.stderr)
chans = [audio_channels(p) for p in inputs]

parts, vlabels = [], []
# Joint treatment: J-CUT CROSSFADES, not fades-to-zero. A butt-splice clicks whenever a
# joint misses a zero crossing (measured 1-sample jumps up to ~80x local signal), but
# fading each edge down to silence trades the click for a ~20 ms ROOM-TONE HOLE at every
# joint — measured 8-13 dB ambience dips, still audible on headphones. The editorial fix:
# each segment's AUDIO runs XF seconds PAST its video cut (real continuing room tone from
# the raw) and equal-power crossfades into the next segment's head. Ambience never dips,
# a step discontinuity is impossible, and the chain arithmetic keeps timing exact:
# sum((dur_i + XF)) - (n-1)*XF == sum(dur_i) == video duration. The rising head gain also
# softens mouth/lip transients that sit a few ms after cut-ins (word starts run late vs
# acoustic onsets). This is part of the CUT (a DAW's auto-crossfade), NOT per-segment
# mastering — the gain->limiter->encode chain still runs exactly once on the whole track.
XF = 0.015          # default crossfade at each joint (min word padding ~31 ms, speech untouched)
EDGE = 0.005        # tiny fade from/to silence at the very start and end of the file
# Per-joint override: a segment may carry "xfade": <seconds> in cuts.json — the crossfade
# INTO that segment uses it instead of XF. Use when a cut-in clips an already-in-progress
# acoustic onset (word attacks often start tens of ms before the word timestamp): a longer
# ramp (e.g. 0.06) rebuilds a natural attack without moving the timeline.
def xf_into(i):
    return float(segs[i].get("xfade", XF)) if 0 < i < len(segs) else 0.0
max_shift = 0.0
n = len(segs)
for i, seg in enumerate(segs):
    a, b = float(seg["start"]), float(seg["end"])
    if b <= a:
        raise SystemExit(f"segment {i} has end <= start: {seg}")
    k = input_index(seg["clip"])
    fn, fd = grid or video_fps(inputs[k])
    sa = round(a * fn / fd) * fd / fn
    sb = round(b * fn / fd) * fd / fn
    if sb <= sa:
        sb = sa + fd / fn
    max_shift = max(max_shift, abs(sa - a), abs(sb - b))
    seg["start"], seg["end"] = a, b = sa, sb
    # CONFORM to the nominal grid BEFORE the trim: an iPhone .MOV is variable frame rate (avg 29.988 against a
    # 30000/1001 r_frame_rate), so a time trim straight off the stream kept one frame too many or too few at some
    # joints and the flat cut's V1 cuts landed a frame off the EDL (2 of 6 on a real job, 2026-09-27; the flash scan
    # of the chat-only composite caught it). fps= puts every frame on the grid the boundaries were snapped to.
    parts.append(f"[{k}:v]fps={fn}/{fd},trim={a}:{b},setpts=PTS-STARTPTS{fit}[v{i}]")
    ext = xf_into(i + 1) if i < n - 1 else 0.0   # tail extension feeds the next joint's crossfade
    edge = ""
    if i == 0:
        edge += f",afade=t=in:st=0:d={EDGE}"
    if i == n - 1:
        edge += f",afade=t=out:st={max(0.0, (b - a) - EDGE):.6f}:d={EDGE}"
    # A MONO raw plays as DUAL MONO, full level on both channels: voice-gain.py measures it that way (ebur128
    # dualmono), and aresample's own upmix put it 3 dB down a channel, so a mono mic rendered 3 LU under the -17 target
    # on the same measured gain (2026-10-13 audit). pan, aformat and aresample read the same on ffmpeg 4.4 to 9;
    # aresample's own output-layout option was renamed in 5.1 and its old name dropped in 7.0, so no one spelling of it
    # runs on Ubuntu 22.04's 4.4 and on 9 (test_splice_guard.py bans both).
    up = "pan=stereo|c0=c0|c1=c0" if chans[k] == 1 else "aformat=channel_layouts=stereo"
    parts.append(f"[{k}:a]atrim={a}:{b + ext},asetpts=PTS-STARTPTS,{up},aresample=48000{edge}[a{i}]")
    vlabels.append(f"[v{i}]")
parts.append("".join(vlabels) + f"concat=n={n}:v=1:a=0[vc]")
cur = "a0"
for i in range(1, n):
    nxt = "ac" if i == n - 1 else f"ax{i}"
    parts.append(f"[{cur}][a{i}]acrossfade=d={xf_into(i)}:c1=qsin:c2=qsin[{nxt}]")
    cur = nxt
if n == 1:
    parts.append("[a0]anull[ac]")
# latency=1: alimiter's 5 ms lookahead otherwise delays the audio 239 samples relative
# to video (measured) — compensation keeps A/V aligned by construction.
parts.append(f"[ac]volume={amp}dB,"
             "alimiter=level_in=1:level_out=1:limit=0.501:attack=5:release=50:level=disabled:latency=1[ao]")
fc = ";".join(parts)

# Video encoder, cross-platform: Apple's hardware encoder (videotoolbox) on macOS for speed;
# libx264 everywhere else (Windows/Linux) — always present in any ffmpeg build, no GPU needed.
# CRF 18 is visually ≈ the 8 Mbps videotoolbox target for a talking-head source.
if platform.system() == "Darwin":
    venc = ["-c:v", "h264_videotoolbox", "-b:v", "8M"]
else:
    venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]

# NO-DUPLICATE-FRAMES GUARD. Two boundaries of one joint are measured independently
# (refine-cuts.py) and can cross, which lays the same source frames down twice — a
# 1-15 frame stutter that is invisible in every per-segment check (each segment is
# individually fine; only the PAIR is wrong) and that propagates into the flat render
# AND every EDL replay downstream. refine-cuts.py resolves joints pairwise now, but the
# EDL can also be hand-authored or come in with REFINE=0, so the invariant is asserted
# HERE, on the exact times that ship, after the snap. Fail loud: a stutter that reaches
# a timeline costs a rebuild, and on a hand-edited timeline there is no clean rebuild.
bad = []
for i in range(len(segs) - 1):
    x, y = segs[i], segs[i + 1]
    if os.path.basename(x["clip"]) != os.path.basename(y["clip"]):
        continue
    if x["start"] < y["start"] < x["end"]:
        xn, xd = video_fps(inputs[input_index(x["clip"])])
        bad.append((i, x["end"], y["start"], xn / xd))
if bad:
    lines = "\n".join(
        f"    seg{i} ends {e:.3f} but seg{i + 1} starts {s:.3f} "
        f"— {(e - s) * 1000:.0f} ms ({(e - s) * r:.1f} frames) played twice"
        for i, e, s, r in bad)
    raise SystemExit(
        f"[splice] ABORT — {len(bad)} joint(s) reuse the same source frames:\n{lines}\n"
        "    Overlapping segments duplicate footage at the cut and read as a stutter.\n"
        "    A continuous split (nothing removed between two segments) must share ONE\n"
        "    boundary time, not a padded end AND a padded start. Fix cuts.json, or let\n"
        "    refine-cuts.py resolve it (this ran with REFINE=0, or BOTH sides of the\n"
        "    joint are no_refine-pinned — joint resolution never moves a pinned boundary).")

# persist the SNAPPED cut times — the canonical EDL and the caption transcript must
# describe the timeline that actually shipped, not the pre-snap request.
snapped = os.path.join(os.path.dirname(cuts_path), "cuts.snapped.json")
with open(snapped, "w") as f:
    json.dump({"segments": segs}, f, indent=1)
print(f"[splice] frame-grid snap: max boundary shift {max_shift*1000:.1f} ms -> {snapped}",
      file=sys.stderr)

# RENDER=0 — EDL-only mode (every app finish: Premiere, Resolve, CapCut — and the FIRST
# splice on any lane, chat-only included): the timeline replay + canonical transcript need
# only the refined/snapped EDL, so skip the flat render entirely.
if os.environ.get("RENDER", "1") == "0":
    print("[splice] RENDER=0 — EDL-only: skipping the flat render", file=sys.stderr)
    sys.exit(0)

cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
for p in inputs:
    cmd += ["-i", p]
# Windows caps a command line at 32,767 characters, and the graph grows ~250 a segment: past ~140 segments the
# render died with WinError 206 before the EDL was persisted (2026-10-13). There the graph goes in a file, read with
# the option this ffmpeg has (ffmpeg_compat.graph_file(): -/filter_complex from 7.0, -filter_complex_script on 5.1 to
# 6.1; 9.0 removed the latter). macOS/Linux keep the argv.
fc_file = None
if os.name == "nt" and len(fc) > 8000:
    sys.path.insert(0, os.path.join(repo, "workflows"))
    from ffmpeg_compat import graph_file
    fc_file = os.path.join(os.path.dirname(cuts_path), "splice.filter_complex.txt")
    with open(fc_file, "w", encoding="utf-8") as f:
        f.write(fc)
cmd += [*([graph_file(), fc_file] if fc_file else ["-filter_complex", fc]), "-map", "[vc]", "-map", "[ao]",
        *venc,
        "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-ac", "2",
        "-video_track_timescale", "90000", "-movflags", "+faststart",
        out_path]
rc = subprocess.run(cmd).returncode
if fc_file:
    os.remove(fc_file)
sys.exit(rc)
PY

if [ "${RENDER:-1}" != "0" ]; then
  echo "[splice] wrote $OUT/${JOB_NAME}.mp4" >&2
  ffprobe -hide_banner -loglevel error -show_entries format=duration -of default=nw=1:nk=1 "$OUT/${JOB_NAME}.mp4"
fi

# Persist the EDL durably alongside the canonical raw-timeline transcript.
# cuts.json otherwise lives only in /tmp (macOS clears it). The `premiere-pro`
# app-finish replay rebuilds the cut as separate timeline clips FROM this EDL, so it must
# survive past this session — same raw-timeline domain as transcript/words.json.
mkdir -p "$JOB_DIR/transcript"
# the frame-snapped EDL is the canonical one — it describes the timeline that shipped
EDL="$WORK/cuts.snapped.json"; [ -f "$EDL" ] || EDL="$CUTS"
cp "$EDL" "$JOB_DIR/transcript/cuts.json" \
  && echo "[splice] persisted EDL (frame-snapped) → $JOB_DIR/transcript/cuts.json" >&2
sha1_of "$JOB_DIR/transcript/cuts.json" > "$STAMP"     # the EDL this splice wrote: the guard above reads it

# Derive the cut-aligned caption transcript from the SAME large-v3 words — no re-transcription.
# The locked caption presets + graphics-plan consume this instead of running their own whisper.
WORDS="$JOB_DIR/transcript/words.json"; [ -f "$WORDS" ] || WORDS="$WORK/words.json"
if [ -f "$WORDS" ]; then
  "$PY" "$(dirname "$0")/export-transcript.py" "$WORDS" "$EDL" "$OUT/${JOB_NAME}.transcript.json" >&2 \
    && echo "[splice] derived caption transcript → $OUT/${JOB_NAME}.transcript.json" >&2
fi

# Audio self-check: joint declick verification + limiter-pressure report (advisory).
# Needs the rendered file — skipped in EDL-only mode.
if [ "${RENDER:-1}" != "0" ]; then
  "$PY" "$(dirname "$0")/audio-qa.py" "$JOB_DIR" >&2 || true
fi
