#!/usr/bin/env bash
# render the section-title cards -> renders/<id>.mp4  (opaque card, grid bg baked in)
#                                -> renders/<id>-alpha.mov (ProRes 4444, type only)
# usage: render.sh [id ...]          (no args = every title in titles.json)
#        ALPHA_ONLY=1  render.sh t-setup   (skip the opaque card)
#        OPAQUE_ONLY=1 render.sh           (skip the alpha overlays — the V1
#                                           timeline only ever places the opaque card)
#        VER=b         render.sh           (-> renders/<id>-b.mp4)
#
# VER: NEVER re-render onto a path an editing app has already placed. Overwriting a
# placed file half-stales Premiere's frame index and random frames come back
# transparent. Version the filename and import it fresh.
#
# Alpha is STRAIGHT. A lane that composites premultiplied converts on its own side — see LANES.md § step 5.
#
# Pin: 0.8.105 — the validated new-job pin (2026-10-01, PNG-sequence A/B vs 0.8.16 on this very builder:
# alpha 415 px of glyph AA total; the opaque card's grid-bg.mp4 now renders at the file's own colour,
# 4,24,54 against the file's 4,22,52, where 0.8.16 crushed it to 0,11,43). Bump deliberately.
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

# The timeline rate comes from the JOB (reference/fullscreen-render.sh's resolution, word for word): FPS, else the
# job's graphics-plan.json "fps", else the first raw's rate. A hardcoded --fps 30 gave a 29.97 or 23.976 job 30 fps
# cards the NLE had to conform (2026-09-27).
FPS_SRC="FPS"
if [ -z "${FPS:-}" ] && [ -f ../../graphics-plan.json ]; then
  FPS=$(node -e 'const p = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")); process.stdout.write(p.fps == null ? "" : String(p.fps))' ../../graphics-plan.json)
  FPS_SRC="graphics-plan.json"
fi
if [ -z "${FPS:-}" ]; then
  for _r in ../../raw/*; do
    [ -f "$_r" ] || continue
    _rf=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$_r" 2>/dev/null | sed -n 1p | tr -d ',\r' || true)
    case "$_rf" in ''|0/0) continue ;; esac
    FPS="$_rf"; FPS_SRC="raw/${_r##*/}"; break
  done
fi
if [ -z "${FPS:-}" ]; then
  FPS="30000/1001"; FPS_SRC="default"
  echo "⚠️  no fps in ../../graphics-plan.json and no video in ../../raw/: rendering at $FPS. Pass FPS=<the timeline's rate> if that is wrong." >&2
fi
case "$FPS" in ''|/*|*/|*/*/*|*[!0-9/]*)
  echo "refusing: FPS=$FPS (from $FPS_SRC) is not a frame rate like 24000/1001, 30000/1001 or 25." >&2; exit 2 ;; esac
echo "fps $FPS (from $FPS_SRC)"

if [ $# -gt 0 ]; then
  IDS="$*"
else
  IDS=$("${BUILD[@]}" --ids | tr -d '\r')   # a native Windows Python ends its print with \r\n: the last id kept the \r
fi

"${BUILD[@]}" --fps "$FPS" $IDS

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
  echo "          Re-render it as a new version instead: VER=<next unused letter> $0 $ID" >&2
  exit 2
}

# THE COLOUR TAIL, on every alpha mov (2026-10-13; fullscreen-render.sh owns the why): hyperframes 0.8.105 writes its
# ProRes with the BT.601 matrix and no colour tags, which the editing apps read as Rec.709, so every saturated colour
# landed off its hex. The tail decodes once to float RGB (ffmpeg reads an untagged file as 601, the matrix it was
# encoded with) and encodes 709, tagged. The opaque mp4 needs none: hyperframes encodes and tags it 709 itself.
TO709="format=gbrapf32le,scale=out_color_matrix=bt709:out_range=tv,format=yuva444p12le,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"

for ID in $IDS; do
  if [ "${ALPHA_ONLY:-0}" != "1" ]; then
    placed_guard "renders/$ID$SUF.mp4"
    echo "==> $ID (opaque card)"
    hf render . -c "compositions/$ID.html" --fps "$FPS" --quality standard \
      --video-frame-format png --format mp4 --output "renders/$ID$SUF.mp4"
  fi

  if [ "${OPAQUE_ONLY:-0}" = "1" ]; then
    continue
  fi

  placed_guard "renders/$ID-alpha$SUF.mov"
  echo "==> $ID (alpha overlay)"
  hf render . -c "compositions/$ID-alpha.html" --fps "$FPS" --quality standard \
    --video-frame-format png --format mov --output "renders/$ID-hf$SUF.mov"
  ffmpeg -y -v error -i "renders/$ID-hf$SUF.mov" -vf "$TO709" -c:v prores_ks -profile:v 4444 "renders/$ID-alpha$SUF.mov"
  rm "renders/$ID-hf$SUF.mov"
done
