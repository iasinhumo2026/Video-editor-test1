#!/usr/bin/env bash
# render the text animations -> renders/<id>-alpha.mov (ProRes 4444, STRAIGHT alpha)
# usage: render.sh [id ...]          (no args = every entry in text.json)
#        VER=b render.sh p1          (-> renders/p1-alpha-b.mov)
#        FPS=24000/1001 render.sh    (the TIMELINE's exact rate: the render AND build.py --fps)
#        SCALE=2 render.sh           (build.py --scale: 2 = 3840x2160, the 1080 layout on a scale(2) stage)
#        JOB=<job_dir> render.sh     (override the job auto-derived from folder position)
#        STEP_FPS=12 render.sh       (animate at 12 fps, held back up to FPS: the mov is at the timeline rate)
#
# Every run REBUILDS the comps it renders, so the builder's rate and scale come from here, never from a
# hand `build.py` run (render.sh overwrote one: a 4K job's text renders all came out 1920x1080 and were
# laid at Scale 200, and their frame margins were solved at 29.97 on a 23.976 job; 2026-09-28).
# SCALE unset = the job's first raw video as a whole multiple of 1920x1080 (the preset:
# resolution follows the footage), else 1 with a warning.
# FPS unset = the job's graphics-plan.json "fps", else the first video in its raw/, else 30000/1001 with a warning
# (fullscreen-render.sh's order). A value that is not a rate like 24000/1001 or 25 is refused.
#
# VER: NEVER re-render onto a path an editing app has already placed. Overwriting
# a placed file half-stales Premiere's frame index and random frames come back
# transparent. Version the filename and import it fresh.
#
# Alpha is STRAIGHT. A lane that composites premultiplied converts on its own
# side — LANES.md § step 5.
#
# Pin: 0.8.105 — the validated new-job pin (2026-10-01). Bump deliberately.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p renders

HF="hyperframes@0.8.105"
# THE NPM FREEZE (reference/fullscreen-render.sh owns the why): npm takes only the versions published by the pin's
# validation day, so a fresh npx cache rebuilds the tree the pin was validated on. A full timestamp, never a bare date.
HF_BEFORE="2026-10-01T23:59:59Z"
hf() { npm_config_before="$HF_BEFORE" npx "$HF" "$@"; }

PY=python3; "$PY" -c '' 2>/dev/null || PY=python
# The builder needs Pillow, so it runs through uv on its PEP 723 header and build.py.lock: a bare python3 has no
# Pillow the day Homebrew moves python3 to a new minor (3.15 did, 2026-10-13). "$PY" only when uv is missing.
if command -v uv >/dev/null 2>&1; then BUILD=(uv run build.py); else BUILD=("$PY" build.py); fi
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8   # Windows pipes default to cp1252, which cannot encode the ⚠ status glyphs
# The timeline rate comes from the JOB, never a hardcoded default (fullscreen-render.sh's resolution): a 23.976 job's
# margins were solved at 29.97 whenever FPS was not passed (2026-09-28). The plan names the SEQUENCE rate, the raw is
# the fallback; an explicit FPS wins.
FPS_SRC="FPS"
if [ -z "${FPS:-}" ] && [ -f "${JOB:-../..}/graphics-plan.json" ]; then
  FPS=$("$PY" -c 'import json, sys; p = json.load(open(sys.argv[1], encoding="utf-8")).get("fps"); sys.stdout.write("" if p is None else str(p))' "${JOB:-../..}/graphics-plan.json")
  FPS_SRC="graphics-plan.json"
fi
if [ -z "${FPS:-}" ]; then
  for _r in "${JOB:-../..}"/raw/*; do
    [ -f "$_r" ] || continue
    _rf=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$_r" 2>/dev/null | sed -n 1p | tr -d ',\r' || true)
    case "$_rf" in ''|0/0) continue ;; esac   # not a video (a wav, a txt)
    FPS="$_rf"; FPS_SRC="raw/${_r##*/}"; break
  done
fi
if [ -z "${FPS:-}" ]; then
  FPS="30000/1001"; FPS_SRC="default"
  echo "⚠️  no fps in ${JOB:-../..}/graphics-plan.json and no video in ${JOB:-../..}/raw/: rendering at $FPS. Pass FPS=<the timeline's rate> if that is wrong." >&2
fi
case "$FPS" in ''|/*|*/|*/*/*|*[!0-9/]*)
  echo "refusing: FPS=$FPS (from $FPS_SRC) is not a frame rate like 24000/1001, 30000/1001 or 25." >&2; exit 2 ;; esac

if [ $# -gt 0 ]; then
  IDS="$*"
else
  IDS=$("${BUILD[@]}" --ids | tr -d '\r')   # a native Windows Python ends its print with \r\n: the last id kept the \r
fi

SCALE_SRC="SCALE"
if [ -z "${SCALE:-}" ]; then
  SCALE=1; SCALE_SRC="default"
  for _r in "${JOB:-../..}"/raw/*; do
    [ -f "$_r" ] || continue
    _wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$_r" 2>/dev/null | sed -n 1p | tr -d '\r' || true)
    _w="${_wh%%,*}"; _h="${_wh#*,}"; _h="${_h%%,*}"
    case "$_w,$_h" in ,*|*,|*[!0-9,]*) continue ;; esac   # not a video (a wav, a txt)
    SCALE_SRC="raw/${_r##*/}"
    if [ $((_w % 1920)) -eq 0 ] && [ $((_h % 1080)) -eq 0 ] && [ $((_w / 1920)) -eq $((_h / 1080)) ] && [ "$_w" -gt 0 ]; then
      SCALE=$((_w / 1920))
    else
      echo "⚠️  $SCALE_SRC is ${_w}x${_h}, not a whole multiple of 1920x1080: rendering at 1920x1080. Pass SCALE=<n> for a bigger timeline." >&2
    fi
    break
  done
  [ "$SCALE_SRC" != "default" ] || echo "⚠️  no video in ${JOB:-../..}/raw/: rendering at 1920x1080. Pass SCALE=2 for a 4K timeline." >&2
fi
case "$SCALE" in ''|0*|*[!0-9]*)
  echo "refusing: SCALE=$SCALE (from $SCALE_SRC) is not a whole number like 1 or 2." >&2; exit 2 ;; esac
echo "scale $SCALE ($((1920 * SCALE))x$((1080 * SCALE)), from $SCALE_SRC), fps $FPS (from $FPS_SRC)"

BUILD_ARGS=(--fps "$FPS" --scale "$SCALE")
[ -z "${JOB:-}" ] || BUILD_ARGS+=(--job "$JOB")
"${BUILD[@]}" "${BUILD_ARGS[@]}" $IDS

SUF=""
[ -n "${VER:-}" ] && SUF="-$VER"

# THE VER RULE ABOVE, ENFORCED: refuse an output path the placer has already laid (a builder
# overwrote one anyway on 2026-09-19). The job's placement.json sits one level up; no file = nothing
# placed yet, so this is a no-op before the first `place-graphics.py --plan --write`.
placed_guard() {   # $1 = the file this run is about to write
  _pj="../placement.json"; [ -f "$_pj" ] || return 0
  _b="${1##*/}"
  grep -q "[/\\]$_b\"" "$_pj" || return 0
  echo "refusing: renders/$_b is PLACED on the timeline (../placement.json)." >&2
  echo "          Re-render it as a new version instead: VER=<next unused letter> $0 ${_b%%-alpha*}" >&2
  exit 2
}

# MBLUR=1 -> TRUE motion blur: render at MBLUR_SS x the target rate, then average
# MBLUR_SHUTTER consecutive frames and decimate back. Averaging must happen on
# PREMULTIPLIED pixels (straight alpha averages wrong at soft edges), so the chain
# premultiplies, mixes, then unpremultiplies back to the straight alpha Premiere
# and Resolve expect. SS 5 / shutter 3 ~= a 216-degree shutter.
#
# STEP_FPS=12 -> "12 fps style": ANIMATE at 12 fps and hold each frame, then expand
# back to the timeline rate by frame duplication (the on-2s / stop-motion look).
# NEVER with MBLUR: the 12 fps look steps, it does not blur (creative-moves.md 4c).
SS="${MBLUR_SS:-5}"; SHUT="${MBLUR_SHUTTER:-3}"
FPS_NUM="${FPS%%/*}"; FPS_DEN="${FPS##*/}"
[ "$FPS_NUM" = "$FPS_DEN" ] && FPS_DEN=1
if [ -n "${STEP_FPS:-}" ]; then
  ANIM_NUM="$STEP_FPS"; ANIM_DEN=1
  EXPAND=",fps=$FPS"
else
  ANIM_NUM="$FPS_NUM"; ANIM_DEN="$FPS_DEN"
  EXPAND=""
fi
ANIM_FPS="$ANIM_NUM/$ANIM_DEN"
SS_FPS="$((ANIM_NUM * SS))/$ANIM_DEN"
WEIGHTS=""; _i=0
while [ "$_i" -lt "$SHUT" ]; do WEIGHTS="$WEIGHTS 1"; _i=$((_i + 1)); done
WEIGHTS="${WEIGHTS# }"   # NOT `yes 1 | head` — SIGPIPE + pipefail kills the script
# tmix emits at every input index with a TRAILING window: out[j] = mean(j-SHUT+1..j).
# So the shutter centred on output frame m is j = m*SS + (SHUT-1)/2. The supersampled
# stream ends mid-group (both rates ceil() independently), so clone-pad the tail by SS
# or the last output frame is silently dropped. Verified against a no-blur render:
# same frame count, same onset.
PHASE=$(( (SHUT - 1) / 2 ))
# The tail pad guarantees the last group exists. The supersampled and base renders
# round their frame counts independently, so derive the cap as ceil(ss_frames / SS):
# it can run ONE frame long but never short. Long is harmless (placement pins the
# out point); short would leave a one-frame gap at the graphic's tail.
mb_frames() { # $1 = supersampled file -> exact target frame count
  _L=$(ffprobe -v error -select_streams v:0 -count_frames \
       -show_entries stream=nb_read_frames -of csv=p=0 "$1" | sed -n 1p)
  echo $(( (_L + SS - 1) / SS ))
}

# The STEP_FPS expansion is capped at the comp's own span on the timeline grid, as fullscreen-render.sh does (its
# step_frames, word for word): the 12 fps render rounds its own frame count up, so the bare expansion ran long.
step_frames() { # $1 = the STEP_FPS render -> its frame count at the timeline rate
  _d=$(tr '\r\n' '  ' < "compositions/$ID.html" | grep -o '<[^>]*data-composition-id=[^>]*>' | head -1 | sed -n 's/.*data-duration="\([0-9.]*\)".*/\1/p' || true)
  if [ -n "$_d" ]; then
    awk -v d="$_d" -v n="$FPS_NUM" -v m="$FPS_DEN" \
      'BEGIN { r = d * n / m; k = int(r + 0.5); if (r - k <= 0.001 && k - r <= 0.001) print k; else print int(r) + 1 }'
  else
    _n=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$1" | sed -n 1p | tr -dc '0-9')
    echo $(( (2 * _n * FPS_NUM + STEP_FPS * FPS_DEN) / (2 * STEP_FPS * FPS_DEN) ))
  fi
}

# THE COLOUR TAIL, on every alpha mov (2026-10-13; fullscreen-render.sh owns the why): hyperframes 0.8.105 writes its
# ProRes with the BT.601 matrix and no colour tags, which the editing apps read as Rec.709, so every saturated colour
# landed off its hex. The tail decodes once to float RGB (ffmpeg reads an untagged file as 601, the matrix it was
# encoded with) and encodes 709, tagged.
TO709="format=gbrapf32le,scale=out_color_matrix=bt709:out_range=tv,format=yuva444p12le,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"

for ID in $IDS; do
  OUT="renders/$ID-alpha$SUF.mov"
  placed_guard "$OUT"
  if [ -n "${MBLUR:-}" ]; then
    echo "==> $ID (alpha overlay, motion blur ${SS}x/${SHUT}f)"
    hf render . -c "compositions/$ID.html" --fps "$SS_FPS" --quality standard \
      --video-frame-format png --format mov --output "renders/$ID-ss.mov"
    NB=$(mb_frames "renders/$ID-ss.mov")
    [ -z "${STEP_FPS:-}" ] || NB=""   # `&& NB=` would exit under set -e
    ffmpeg -y -v error -i "renders/$ID-ss.mov" ${NB:+-frames:v "$NB"} -vf \
      "format=rgba64le,premultiply=inplace=1,tmix=frames=$SHUT:weights=$WEIGHTS,tpad=stop=$SS:stop_mode=clone,select='eq(mod(n\,$SS)\,$PHASE)',unpremultiply=inplace=1,setpts=N/($ANIM_NUM/$ANIM_DEN)/TB$EXPAND,$TO709" \
      -c:v prores_ks -profile:v 4444 -r "$FPS" "$OUT"
    rm "renders/$ID-ss.mov"
    echo "-> $OUT (motion blur baked)"
  else
    echo "==> $ID (alpha overlay)"
    hf render . -c "compositions/$ID.html" --fps "$ANIM_FPS" --quality standard \
      --video-frame-format png --format mov --output "renders/$ID-hf$SUF.mov"
    if [ -n "${STEP_FPS:-}" ]; then
      # hyperframes writes a STEP_FPS render AT 12 fps: held up to the timeline rate (left at 12 the mov is half the
      # frames and its holds drift off the grid), frame duplication only, the alpha stays straight
      NF=$(step_frames "renders/$ID-hf$SUF.mov")
      ffmpeg -y -v error -i "renders/$ID-hf$SUF.mov" -frames:v "$NF" -vf "fps=$FPS,tpad=stop=2:stop_mode=clone,$TO709" \
        -c:v prores_ks -profile:v 4444 -r "$FPS" "$OUT"
      echo "-> $OUT ($STEP_FPS fps held to $FPS, $NF frames)"
    else
      ffmpeg -y -v error -i "renders/$ID-hf$SUF.mov" -vf "$TO709" -c:v prores_ks -profile:v 4444 "$OUT"
    fi
    rm "renders/$ID-hf$SUF.mov"
  fi
done
