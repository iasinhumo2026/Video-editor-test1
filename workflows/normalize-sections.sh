#!/usr/bin/env bash
# normalize-sections.sh — apply the HOUSE audio chain to every source recording in a job, as
# normalized copies, and verify nothing shifted in time. The baked step-3 chain for the Resolve and
# Final Cut lanes: Resolve lays its timeline from audio-normalized/ (lanes/resolve/resolve-audio-polish/replace-clips.py
# swaps them under a clip ingested at its nominal rate only), Final Cut's lanes/finalcut/replay.py lays them itself.
#
#   usage: workflows/normalize-sections.sh <job_dir>
#          DRY=1 workflows/normalize-sections.sh <job_dir>            measure only, render nothing
#          AMPLIFY_DB=12 workflows/normalize-sections.sh <job_dir>    override the measured gain
#
# The chain is the same one every lane runs (LANES.md § step 3; unified 2026-09-04, the user's call):
#   gain = whatever puts the KEPT speech at -17 LUFS integrated, measured by workflows/voice-gain.py
#   from transcript/cuts.json against raw/  →  hard limiter at -6 dBFS  →  320k AAC.
# One gain per job dir (a section sub-job with its own transcript gets its own measurement).
#
# Writes normalized copies to <job_dir>/audio-normalized/. NEVER touches the raws. A copy that fails
# the drift gate is renamed <file>.DRIFT, so neither replace-clips.py nor replay.py picks it up.
# Exit 0 = every matched raw rendered and passed; 1 = a DRIFT, an error, a clip a cut names that no raw matched
# (raws: mp4/mov/mkv/m4v, transcribe.sh's list), or no raw matched any cut.
#
# Locks (full rationale in lanes/resolve/resolve-audio-polish/README.md):
#   · -c:v copy          video is stream-copied, so the picture stays bit-identical
#   · level=disabled     alimiter auto-level otherwise defeats the measured static gain
#   · latency=1          compensates the limiter's own lookahead so nothing moves in time
#   · 320k AAC           downstream-bitrate lock: never re-encode voice below 256k
#   · NEVER loudnorm     dynamic normalization pumps
#
# Bash 3.2 clean (stock macOS) and Linux clean — no mapfile, no associative arrays.
set -euo pipefail
PY=python3; "$PY" -c '' 2>/dev/null || PY=python   # Git Bash / some Linux ship only `python`
export PYTHONUTF8=1

JOB="${1:?usage: normalize-sections.sh <job_dir>}"
OUT="$JOB/audio-normalized"
CEIL="0.501"             # -6.0 dBFS, the house limiter ceiling (splice.sh uses the same value)
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VOICE_GAIN="$REPO/workflows/voice-gain.py"

[ -d "$JOB" ] || { echo "no such job dir: $JOB" >&2; exit 1; }
mkdir -p "$OUT"

# every raw recording in the job: the top-level raw/ plus each section's raw/ (-L: a section's raw is a symlink to
# the job's, and it is measured with the SECTION's own cut). The extensions rough-cut's transcribe.sh takes: an OBS
# .mkv the cut used was skipped here, exit 0, its clips left un-gained (2026-10-13 audit).
SRCS=$({ find -L "$JOB/raw" "$JOB/sections" -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.m4v' \) -path '*/raw/*' 2>/dev/null || true; } | sort)   # sections/ may not exist; under set -e that must not abort
[ -n "$SRCS" ] || { echo "no raws found under $JOB" >&2; exit 1; }

measure() {   # $1=file -> "I LRA PEAK"  (whole file, for the readback columns only)
  # -vn: decoding a 4K raw into the null muxer filled RAM and crashed the Mac (2026-09-23)
  ffmpeg -nostdin -hide_banner -i "$1" -vn -sn -dn -af ebur128=peak=true -f null - 2>&1 \
    | sed -n '/Summary:/,$p' \
    | awk '/^ *I:/{i=$2} /^ *LRA:/{l=$2} /^ *Peak:/{p=$2} END{print i, l, p}'
}

row() {       # stdin: one ffprobe csv answer -> its first non-empty row
  # tr: ffprobe's csv on Windows carries a trailing \r (and a stray comma on some fields, 2026-09-27)
  # awk: ffprobe 9 puts a timecoded file's tmcd track and its video in a stream group, which prints the video row
  # twice and a blank row before an audio answer; the line breaks that left in these fields emptied the audio
  # columns, so the gate passed a 129 ms audio offset on a timecoded raw (2026-10-13)
  tr -d ',\r' | awk 'NF && !n { print; n = 1 }'   # reads to the end: an early exit could SIGPIPE tr under pipefail
}

probe() {     # $1=file -> "dur vframes astart adur arate"
  d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" | row)
  v=$(ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 "$1" | row)
  s=$(ffprobe -v error -select_streams a:0 -show_entries stream=start_time -of csv=p=0 "$1" | row)
  ad=$(ffprobe -v error -select_streams a:0 -show_entries stream=duration -of csv=p=0 "$1" | row)
  r=$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate -of csv=p=0 "$1" | row)
  # MKV records no per-stream frame count or duration (N/A): count the video packets (stream-copied, one a frame) and
  # end the audio at its last packet. N/A compared as text read equal, and awk read it as 0, so the gate was blind there.
  case "$v" in ''|N/A) v=$(ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets \
                           -of csv=p=0 "$1" | row) ;; esac
  case "$ad" in ''|N/A) ad=$(ffprobe -v error -select_streams a:0 -show_entries packet=pts_time,duration_time -of csv=p=0 "$1" \
                             | tr -d '\r' | awk -F, -v s="$s" '$1 != "N/A" && $2 != "N/A" && $1 != "" { e = $1 + $2; if (!n++ || e > m) m = e }
                                                              END { if (n) printf "%.6f\n", m - s; else print "N/A" }') ;; esac
  echo "$d $v $s $ad $r"
}

# 0 when the rendered copy $2 sits exactly on the source $1 in time; a reading either side lacks is a FAIL, never a match
same_time() {
  probe "$1" | { read -r d1 v1 s1 a1 r1; probe "$2" | { read -r d2 v2 s2 a2 r2
    na=0; for x in "$d1" "$v1" "$s1" "$a1" "$d2" "$v2" "$s2" "$a2"; do case "$x" in ''|N/A) na=1 ;; esac; done
    # video frames exactly (the picture is stream-copied); audio start and audio stream duration within one
    # AAC frame (1024 samples: PCM counts samples and AAC counts packets, so nb_frames never compares); the
    # container duration within 0.02 s (a stream-copied HEVC's last-frame duration moves below a frame:
    # 648.105 -> 648.105792 on both lane tests, 2026-09-25, with nothing shifted)
    [ "$na" = 0 ] && [ "$v1" = "$v2" ] && awk -v d1="$d1" -v d2="$d2" -v s1="$s1" -v s2="$s2" -v a1="$a1" -v a2="$a2" -v r="$r1" '
      function ab(x) { return x < 0 ? -x : x }
      BEGIN { f = (r > 0) ? 1024 / r : 0.0214
              exit !(ab(d1 - d2) < 0.02 && ab(s1 - s2) <= f && ab(a1 - a2) <= f) }'; }; }
}

# gain for one job dir: voice-gain.py on the kept ranges, or the AMPLIFY_DB override.
# Prints "GAIN KEPT_LUFS".
job_gain() {  # $1=job dir (the one holding raw/ + transcript/cuts.json)
  if [ -n "${AMPLIFY_DB:-}" ]; then echo "$AMPLIFY_DB override"; return; fi
  [ -f "$1/transcript/cuts.json" ] || { echo "no transcript/cuts.json under $1 — run rough-cut first, or set AMPLIFY_DB" >&2; exit 1; }
  if command -v uv >/dev/null 2>&1; then j=$(uv run "$VOICE_GAIN" "$1" --json); else j=$("$PY" "$VOICE_GAIN" "$1" --json); fi
  printf '%s' "$j" | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(d["gain_db"], d["lufs"])'
}

# exit 0 = the cut uses this raw, 1 = it does not (another section's raw), 2 = the cut could not be read
USES_CLIP='import json,sys
try:
    segs = json.load(open(sys.argv[1], encoding="utf-8"))["segments"]
except Exception as e:
    sys.stderr.write("%s: %s\n" % (sys.argv[1], e)); sys.exit(2)
sys.exit(0 if any(s.get("clip", "").lower() == sys.argv[2].lower() for s in segs) else 1)'

echo "house chain: measured gain -> kept speech -17 LUFS pre-limiter, hard limiter -6 dBFS   out: $OUT"
printf "\n%-26s %9s %7s %9s %8s  %s\n" SECTION KEPT_LUFS GAIN OUT_LUFS OUT_PEAK CHECK
fail=0; done_n=0
last_dir=""; GAIN=""; KEPT=""
SEEN=""      # "<job dir>|<raw, lowercase>", one a line, for every raw a cut uses that this loop took up
while read -r src; do
  [ -n "$src" ] || continue
  file=$(basename "$src"); name="${file%.*}"
  jobdir=$(cd "$(dirname "$src")/.." && pwd)
  # a job dir with no cut of its own (a multi-section job's top level) is measured by its sections
  [ -f "$jobdir/transcript/cuts.json" ] || continue
  # a raw this job dir's cut never uses is another section's: its own cut measures and bakes it
  rc=0; "$PY" -c "$USES_CLIP" "$jobdir/transcript/cuts.json" "$file" </dev/null || rc=$?
  if [ "$rc" = 1 ]; then continue; fi
  if [ "$rc" != 0 ]; then echo "✗ $name: could not read $jobdir/transcript/cuts.json (exit $rc)" >&2; fail=1; continue; fi
  SEEN="$SEEN
$jobdir|$(printf '%s' "$file" | tr '[:upper:]' '[:lower:]')"
  if [ "$jobdir" != "$last_dir" ]; then
    set -- $(job_gain "$jobdir" </dev/null); GAIN="${1:-}"; KEPT="${2:-}"; last_dir="$jobdir"   # its ffmpeg would eat the loop's input
  fi
  if [ -z "$GAIN" ]; then echo "✗ $name: no gain measured for $jobdir" >&2; fail=1; last_dir=""; continue; fi
  done_n=$((done_n + 1))

  if [ "${DRY:-0}" = "1" ]; then
    printf "%-26s %9s %+7s %9s %8s  %s\n" "$name" "$KEPT" "$GAIN" - - "dry-run"
    continue
  fi

  dst="$OUT/$file"
  ffmpeg -nostdin -v error -y -i "$src" -c:v copy \
    -af "volume=${GAIN}dB,alimiter=level_in=1:level_out=1:limit=${CEIL}:attack=5:release=50:level=disabled:latency=1" \
    -c:a aac -b:a 320k "$dst"

  # DRIFT GATE. An AAC re-encode can shift audio a frame via encoder priming; that would break sync
  # across every cut, and it is invisible until someone watches the whole video.
  set -- $(measure "$dst")
  if same_time "$src" "$dst"; then chk="OK"
  else mv "$dst" "$dst.DRIFT"; chk="*** DRIFT *** -> $dst.DRIFT"; fail=1; fi
  printf "%-26s %9s %+7s %9s %8s  %s\n" "$name" "$KEPT" "$GAIN" "${1:-}" "${3:-}" "$chk"
done <<EOF
$SRCS
EOF

# COVERAGE. Every clip a cut names was taken up above: a clip no raw matched (an extension this pass skipped, a missing
# file) kept its raw audio behind an exit 0, with nothing on the lane to say so (2026-10-13 audit). An inserted media
# segment (a meme or b-roll laid from its own file, `media` outside raw/) is no raw: voice-gain.py's rule skips it.
CLIPS_OF='import json,os,sys
try:
    segs = json.load(open(sys.argv[1], encoding="utf-8"))["segments"]
except Exception:
    sys.exit(0)                                  # an unreadable cut is reported by the loop above
try:
    raws = set(n.lower() for n in os.listdir(os.path.join(os.path.dirname(os.path.dirname(sys.argv[1])), "raw")))
except OSError:
    raws = set()
for c in sorted(set(s.get("clip", "").lower() for s in segs if not (s.get("media") and s.get("clip", "").lower() not in raws))):
    print(c)'
for cuts in "$JOB/transcript/cuts.json" "$JOB"/sections/*/transcript/cuts.json; do
  [ -f "$cuts" ] || continue
  dir=$(cd "$(dirname "$cuts")/.." && pwd)
  while IFS= read -r clip; do
    [ -n "$clip" ] || continue
    case "$SEEN
" in *"
$dir|$clip
"*) ;;
      *) echo "✗ $clip: $cuts uses it, but no raw under $dir/raw matched it (missing, or not mp4/mov/mkv/m4v)" >&2; fail=1 ;;
    esac
  done <<EOF
$("$PY" -c "$CLIPS_OF" "$cuts" </dev/null | tr -d '\r')
EOF
done

echo
if [ "${DRY:-0}" = "1" ]; then
  echo "dry run — nothing written. Re-run without DRY=1 to render."
else
  echo "OUT_LUFS is the whole file (dead air included); the kept speech sits at -17. OUT_PEAK is a TRUE peak (dBTP):"
  echo "it reads a little over the -6.0 dBFS limit, about -5.8 to -5 (the AAC encode and the peaks between samples overshoot it)."
  echo "A *** DRIFT *** copy was renamed <file>.DRIFT so nothing lays it: investigate before re-running."
  echo "Next: Resolve: lay the timeline from audio-normalized/ (replace-clips.py only under a clip ingested at its nominal"
  echo "rate, never an iPhone take whose FPS was set); Final Cut: replay.py lays audio-normalized/ by itself."
fi
[ "$done_n" -gt 0 ] || { echo 'no raw matched any cut in transcript/cuts.json' >&2; exit 1; }
exit $fail
