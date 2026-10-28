#!/usr/bin/env bash
# REFERENCE full-screen graphics renderer — copy into projects/<job>/hf-graphics/gfx/
# alongside compositions/. Carries the locked chains: full = mp4 + film-grain pass,
# alpha = ProRes 4444 straight, MBLUR=1 MBLUR_SS=8 MBLUR_SHUTTER=5 on any timeline-rate comp that slides or
# moves its camera (the lock since 2026-09-10; 8x is the renderer's ceiling), STEP_FPS=12 (THE default for bg-DARK full-screens ONLY;
# bg-light full-screens render at the timeline rate, no 12 fps — grain is
# applied AFTER the frame-hold expansion, at the timeline rate), optional MBLUR
# (never together with STEP_FPS — see creative-moves.md 4c).
# usage: render.sh <id> full   -> renders/<id>[-VER].mp4      (full-screen: grain pass baked)
#        render.sh <id> alpha  -> renders/<id>-alpha[-VER].mov (overlay: ProRes 4444 straight)
#        MBLUR=1 MBLUR_SS=8 MBLUR_SHUTTER=5 render.sh <id> full   (timeline-rate comps that slide or move the camera)
#        VER=b render.sh <id> full     (NEVER overwrite a placed file — version it)
#        FPS=24000/1001 — the timeline's exact rational rate. Unset, it is the job's graphics-plan.json "fps"
#          (../../ from this folder), else the first video in ../../raw/, else 30000/1001 with a warning.
#        THE ALPHA POST PASS (opt-in, alpha renders only; unset = the command is exactly what it was without it).
#        The values per family live in presets/instagram/talking-head-explainer/graphics.md § 7:
#          GLOW=<opacity>  bloom on the colour planes, the alpha kept from the render so it never leaves the panel:
#                          split -> gblur sigma 30 -> eq brightness 0.12 contrast 1.12 -> curves 0/0 0.5/0.62 1/1 -> screen
#          SCAN=1          scan lines, a real screen's texture: a 6 px sine on R, G and B, alpha untouched;
#                          SCAN_AMP=<depth> overrides its 0.10 (a white capture takes less)
#        GLOW_FULL=<opacity> (full renders): the float bloom over the whole frame (full_glow below); bg-dark = STEP_FPS=12 GLOW_FULL=0.26 GRAIN_1080=5
#        GRAIN_1080=<n> (full renders): the grain made at the 1080 frame's scale (full_grain below); bg-dark = STEP_FPS=12 GRAIN_1080=5
#          GRAIN=<n>       luma film grain (noise c0s=n c0f=t, yuva444p16le), fresh every frame AFTER the STEP_FPS
#                          expansion: stepped grain reads as a compression bug
#          All four are alpha-only (a full render warns, ignores them and records none), 0 is off, SCAN_AMP needs SCAN.
#          The pass runs in gbrapf32le (ffmpeg 8 breaks 16-bit blend opacity), writes yuva444p12le, and a STEP_FPS render stays capped at step_frames().
#          e.g. STEP_FPS=12 GLOW=0.26 GRAIN=5 render.sh g3 alpha   ·   GLOW=0.12 SCAN=1 render.sh g4 alpha
# Every render writes renders/<file>.render.json beside it: the flags that made it and the command that
# re-renders it, run from this folder.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p renders
# This file's own name, whichever separator $0 came in with: a Windows caller's `bash C:\...\render.sh` passes
# backslashes, which ${0##*/} alone leaves whole (the record then named ./C:\Users\...\render.sh).
SELF="${0##*/}"; SELF="${SELF##*\\}"

ID="$1"; MODE="${2:-full}"
HF="hyperframes@0.8.105"
# THE NPM FREEZE (2026-10-13): the pin is exact but its npm dependencies are ranges (puppeteer-core ^25.10.0), so a
# fresh npx cache resolved whatever had shipped since (puppeteer-core 25.13.0 where the pin was validated on 25.12.0).
# npm then only takes versions published by HF_BEFORE, the pin's validation day, which rebuilds the validated tree
# exactly. A FULL timestamp, never a bare date: npm reads 2026-10-01 as that day's midnight UTC, before the pin itself
# was published (ETARGET on every render). An npx cache that already holds the pin keeps the tree it resolved then:
# setup.sh removes that tree once per freeze and rebuilds it frozen (.setup-npx-frozen).
# Bumped with the pin (workflows/test_hyperframes_pin.py holds the two to setup.sh's).
HF_BEFORE="2026-10-01T23:59:59Z"
hf() { npm_config_before="$HF_BEFORE" npx "$HF" "$@"; }
# The timeline rate comes from the JOB, never a hardcoded default: a 23.976 job rendered at 29.97 every time
# FPS was not passed (2026-09-23). The plan names the SEQUENCE rate, the raw is the fallback.
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
SUF=""
[ -n "${VER:-}" ] && SUF="-$VER"

# THE VER RULE, ENFORCED: never write onto a path the placer has already laid. Overwriting a placed
# file half-stales Premiere's frame index and random frames come back transparent — and a builder did
# it anyway (2026-09-19), caught only by diffing render mtimes against placement.json. The job's
# placement.json sits one level up; no file = nothing placed yet, so this is a no-op before the first
# `place-graphics.py --plan --write`.
placed_guard() {   # $1 = the file this run is about to write
  _pj="../placement.json"; [ -f "$_pj" ] || return 0
  _b="${1##*/}"
  grep -q "[/\\]$_b\"" "$_pj" || return 0
  echo "refusing: renders/$_b is PLACED on the timeline (../placement.json)." >&2
  echo "          Re-render it as a new version instead: VER=<next unused letter> $0 $ID $MODE" >&2
  exit 2
}
# THE FULL-RENDER GRAIN. Default: luma noise 7 per pixel of the render. GRAIN_1080=<n> (the bg-DARK full-screens:
# STEP_FPS=12 GRAIN_1080=5) makes the grain at the 1080 frame's scale instead, noise <n> on a flat plate at 1920 wide,
# blown up pixel for pixel and grain-merged into the luma: the your-job Talking Head Explainer's approved "grain 5" read
# at the same size on a 4K render, where per-pixel noise averages away (2026-10-06).
# THE FULL-RENDER GLOW. GLOW_FULL=<opacity> (bg-dark: 0.26) blooms the WHOLE frame the way the your-job short's authored
# graphics were bloomed (graphics.md § 7: gblur sigma 30 at the 1080 scale, eq brightness 0.12 contrast 1.12, curves
# 0/0 0.5/0.62 1/1, screened at the opacity), in FLOAT, then down to 8-bit with the grain on top as the dither. It
# replaces the comp's CSS #bloom clone: that one composited a wide, near-black blur in 8-bit and banded it into contour
# rings and visible steps (2026-10-06: "why can't it just be a smooth gradient the whole way?").
full_glow() {   # $1 = the clean render, for its size
  [ -n "${GLOW_FULL:-}" ] || return 0
  _w=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$1" | sed -n 1p | tr -d '\r')
  _sig=$(awk -v w="$_w" 'BEGIN{printf "%.1f", 30*w/1920}')
  printf "format=gbrpf32le,split[ga][gb];[gb]gblur=sigma=%s,eq=brightness=0.12:contrast=1.12,curves=all='0/0 0.5/0.62 1/1'[gl];[ga][gl]blend=all_mode=screen:all_opacity=%s,format=yuv444p," "$_sig" "$GLOW_FULL"
}
full_grain() {   # $1 = the clean render, for its size
  if [ -z "${GRAIN_1080:-}" ]; then printf 'noise=c0s=7:c0f=t'; return; fi
  _wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$1" | sed -n 1p | tr -d '\r')
  printf 'split[gv][gn];[gn]scale=1920:-2:flags=area,lutyuv=y=128:u=128:v=128,noise=c0s=%s:c0f=t,scale=%s:flags=neighbor[gp];[gv][gp]blend=c0_mode=grainmerge:c1_expr=A:c2_expr=A' "$GRAIN_1080" "${_wh/x/:}"
}
if [ "$MODE" = "alpha" ]; then placed_guard "renders/$ID-alpha$SUF.mov"; else placed_guard "renders/$ID$SUF.mp4"; fi

# MBLUR=1 -> TRUE motion blur: render at MBLUR_SS x the target rate, average
# MBLUR_SHUTTER consecutive frames, decimate back (~216-degree shutter). Same chain
# as text-animation/render.sh — see that file + text-animation-style.md for the three gotchas
# (trailing tmix window, mid-group tail, premultiply before averaging alpha).
#
# STEP_FPS=12 -> "12 fps style": ANIMATE at 12 fps and hold each frame, then expand
# back to the timeline rate by frame duplication (the on-2s / stop-motion look).
# MBLUR is never passed with STEP_FPS — the stepped look does not blur
# (creative-moves.md 4b/4c; tried and undone 2026-09-10).
# Grain is applied AFTER the expansion, at the full timeline rate: film
# grain is a camera artifact, not animation, and stepping it reads as a compression
# bug. Word-synced events quantize to the 12 fps grid (up to ~83 ms of shift), which
# is inherent to the look — check anything that must land exactly on a word.
SS="${MBLUR_SS:-5}"; SHUT="${MBLUR_SHUTTER:-3}"
FPS_NUM="${FPS%%/*}"; FPS_DEN="${FPS##*/}"
[ "$FPS_NUM" = "$FPS_DEN" ] && FPS_DEN=1
if [ -n "${STEP_FPS:-}" ]; then
  ANIM_NUM="$STEP_FPS"; ANIM_DEN=1
  EXPAND=",fps=$FPS"            # duplicate the held frames up to the timeline rate
else
  ANIM_NUM="$FPS_NUM"; ANIM_DEN="$FPS_DEN"
  EXPAND=""
fi
ANIM_FPS="$ANIM_NUM/$ANIM_DEN"
SS_FPS="$((ANIM_NUM * SS))/$ANIM_DEN"
WEIGHTS=""; _i=0
while [ "$_i" -lt "$SHUT" ]; do WEIGHTS="$WEIGHTS 1"; _i=$((_i + 1)); done
WEIGHTS="${WEIGHTS# }"
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
MB_CORE="tmix=frames=$SHUT:weights=$WEIGHTS,tpad=stop=$SS:stop_mode=clone,select='eq(mod(n\,$SS)\,$PHASE)'"
RFPS="$ANIM_NUM/$ANIM_DEN"

# THE ALPHA POST PASS (header): POST_PRE runs before the STEP_FPS expansion (glow, scan lines), POST_GRAIN after it.
# Both are empty with the flags unset, so every command below is then exactly the one without a post pass.
# 0 is OFF (GLOW=0, SCAN=0, GRAIN=0 turn their pass off, they never run it at zero), and the pass is ALPHA-ONLY:
# a full render bakes its own grain 7 and ignores all four, so it says so and never records them (a record naming
# a flag that had no effect rebuilt nothing it claimed).
_off() { case "${1:-}" in ""|0|0.|0.0|0.00|0.000) return 0 ;; esac; return 1; }
POST_KEYS="GLOW SCAN SCAN_AMP GRAIN"
if [ "$MODE" != "alpha" ]; then
  for _k in $POST_KEYS; do
    _v=$(printenv "$_k" || true)
    [ -z "$_v" ] || echo "⚠ $_k=$_v ignored: the post pass (GLOW, SCAN, SCAN_AMP, GRAIN) is alpha-only; a full render bakes grain 7" >&2
  done
  GLOW=""; SCAN=""; SCAN_AMP=""; GRAIN=""
fi
! _off "${GLOW:-}" || GLOW=""
! _off "${SCAN:-}" || SCAN=""
! _off "${GRAIN:-}" || GRAIN=""
if [ -n "${SCAN_AMP:-}" ] && [ -z "${SCAN:-}" ]; then
  echo "⚠ SCAN_AMP=$SCAN_AMP does nothing without SCAN=1: no scan lines" >&2
fi
POST_PRE=""; POST_GRAIN=""
if [ -n "${GLOW:-}" ] || [ -n "${SCAN:-}" ]; then
  # FLOAT, not gbrap16le: ffmpeg 8's blend screen at a fractional opacity is broken on 16-bit planes (black under
  # GLOW=0.26 came out RGB 72, at 0.5 RGB 138; 8-bit and float give 5), which lit every authored backdrop grey
  # (ffmpeg 8.0.1, 2026-09-27). Float matches the 8-bit reference and keeps the precision.
  POST_PRE="format=gbrapf32le,"
  [ -z "${GLOW:-}" ] || POST_PRE="${POST_PRE}split[a][b];[b]gblur=sigma=30,eq=brightness=0.12:contrast=1.12,curves=all='0/0 0.5/0.62 1/1'[bl];[a][bl]blend=c0_mode=screen:c1_mode=screen:c2_mode=screen:c3_mode=normal:c0_opacity=$GLOW:c1_opacity=$GLOW:c2_opacity=$GLOW:c3_opacity=1,"
  if [ -n "${SCAN:-}" ]; then
    _sl="(1-${SCAN_AMP:-0.10}*(0.5+0.5*cos(2*PI*Y/6)))"
    POST_PRE="${POST_PRE}geq=r='r(X,Y)*$_sl':g='g(X,Y)*$_sl':b='b(X,Y)*$_sl':a='alpha(X,Y)',"
  fi
fi
[ -z "${GRAIN:-}" ] || POST_GRAIN="format=yuva444p16le,noise=c0s=$GRAIN:c0f=t,"
# THE COLOUR TAIL, on every alpha mov (2026-10-13): hyperframes 0.8.105 writes its ProRes with the BT.601 matrix and no
# colour tags, and Premiere, Final Cut and Resolve read untagged HD as Rec.709, so every saturated colour landed off its
# hex (green G -21; white, grey and black never moved). The tail decodes to float RGB with ffmpeg's matrix for an untagged
# file, 601 (the one hyperframes encoded with), and its one scale encodes 709, tagged: proven on every alpha path below
# on ffmpeg 9.0.2 and 7.1.5 (workflows/test_fullscreen_render.py reads it back through a hand 709 decode). 0.8.151+
# encodes 709 itself, but the pin stays 0.8.105 (0.8.112+ fringes text on Windows). The CapCut lane's premultiplied
# copy carries the same tail. A job's already-staged render.sh keeps its old tail, so an in-flight job stays
# self-consistent: never patch one mid-job.
TO709="format=gbrapf32le,scale=out_color_matrix=bt709:out_range=tv,format=yuva444p12le,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"

# A versioned re-render that is BYTE-IDENTICAL to an earlier render means the comp did not change
# (the renderer and encoder are deterministic): g2-b.mp4 == g2.mp4 on your-job, so a
# 3-minute render and a placement swap were both no-ops and nobody noticed. Say so, loudly.
same_as_previous() { # $1 = the file just written
  _new="$1"; _base="${_new##*/}"; _fam="${_base%%-*}"; _ext="${_new##*.}"
  for _old in renders/"$_fam"*."$_ext"; do
    [ -f "$_old" ] && [ "$_old" != "$_new" ] || continue
    if cmp -s "$_old" "$_new"; then
      echo "⚠️  $_new is BYTE-IDENTICAL to $_old, the comp did not change. A render without an edit is a no-op;" >&2
      echo "    placing this file changes nothing on the timeline. Check the edit actually landed in compositions/$ID.html." >&2
    fi
  done
}

# The STEP_FPS expansion is capped at the comp's own span on the timeline grid: the frame count hyperframes
# renders the same comp to at $FPS (its durationToFrameCount: the nearest frame within 1e-3, else ceil). The
# 12 fps render rounds its OWN count up (a 100-frame 23.976 comp, 4.1708 s, renders 51 frames = 4.25 s), so the
# bare expansion ran 2 frames long; the tpad clone before the cap keeps it from ever running one short. A comp
# whose root carries no data-duration falls back to the render's own span, round(frames / STEP_FPS * FPS).
step_frames() { # $1 = the STEP_FPS render -> its frame count at the timeline rate
  # the root tag may span lines (the shipped punch-cut-reference.html breaks it after data-height): read it as one line,
  # or the line-based grep finds no data-duration and the fallback below runs 2 frames long (128 -> 130, 2026-10-13)
  _d=$(tr '\r\n' '  ' < "compositions/$ID.html" | grep -o '<[^>]*data-composition-id=[^>]*>' | head -1 | sed -n 's/.*data-duration="\([0-9.]*\)".*/\1/p' || true)
  if [ -n "$_d" ]; then
    awk -v d="$_d" -v n="$FPS_NUM" -v m="$FPS_DEN" \
      'BEGIN { r = d * n / m; k = int(r + 0.5); if (r - k <= 0.001 && k - r <= 0.001) print k; else print int(r) + 1 }'
  else
    _n=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$1" | sed -n 1p | tr -dc '0-9')
    echo $(( (2 * _n * FPS_NUM + STEP_FPS * FPS_DEN) / (2 * STEP_FPS * FPS_DEN) ))
  fi
}

# THE RENDER RECORD: renders/<file>.render.json names the flags that made the file and the command that
# re-renders it from this folder. Re-renders used to be rebuilt by grepping old session transcripts for
# FPS/STEP_FPS/VER, and one was redone with the wrong flags (2026-09-23). The post pass (GLOW, SCAN, SCAN_AMP,
# GRAIN) is recorded too: every other upper-case NAME this file reads with a :- default that came in through the
# ENVIRONMENT lands in "env" and in the re-render line, so a new flag needs no edit here.
_js() { if [ -n "$1" ]; then printf '"%s"' "$(printf '%s' "$1" | sed 's/[\\"]/\\&/g')"; else printf null; fi; }
_sq() { case "$1" in *[!A-Za-z0-9._/:,+=-]*) printf "'%s'" "$(printf '%s' "$1" | sed "s/'/'\\\\''/g")" ;; *) printf '%s' "$1" ;; esac; }
write_record() { # $1 = the render just written
  _mb="${MBLUR:-}"; _ss=""; _sh=""; _cmd="FPS=$FPS"; _env=""
  [ -z "$_mb" ] || { _ss="$SS"; _sh="$SHUT"; }
  [ -z "${STEP_FPS:-}" ] || _cmd="$_cmd STEP_FPS=$STEP_FPS"
  [ -z "$_mb" ] || _cmd="$_cmd MBLUR=$_mb MBLUR_SS=$SS MBLUR_SHUTTER=$SHUT"
  for _v in $(grep -o '\${[A-Z][A-Z0-9_]*:-' "$SELF" | sed 's/^..//; s/:-$//' | sort -u); do
    case "$_v" in FPS|STEP_FPS|MBLUR|MBLUR_SS|MBLUR_SHUTTER|VER) continue ;; esac
    case " $POST_KEYS " in *" $_v "*) [ "$MODE" = "alpha" ] || continue ;; esac   # a full render ignores the post pass
    _val=$(printenv "$_v" || true)   # the environment only: a variable the script set itself is no flag
    [ -n "$_val" ] || continue
    _env="$_env${_env:+, }$(_js "$_v"): $(_js "$_val")"
    _cmd="$_cmd $_v=$(_sq "$_val")"
  done
  [ -z "${VER:-}" ] || _cmd="$_cmd VER=$VER"
  _cmd="$_cmd ./$SELF $ID $MODE"
  {
    printf '{\n  "file": %s,\n  "id": %s,\n  "mode": %s,\n' "$(_js "${1##*/}")" "$(_js "$ID")" "$(_js "$MODE")"
    printf '  "FPS": %s,\n  "fps_source": %s,\n  "STEP_FPS": %s,\n' "$(_js "$FPS")" "$(_js "$FPS_SRC")" "$(_js "${STEP_FPS:-}")"
    printf '  "MBLUR": %s,\n  "MBLUR_SS": %s,\n  "MBLUR_SHUTTER": %s,\n' "$(_js "$_mb")" "$(_js "$_ss")" "$(_js "$_sh")"
    printf '  "env": {%s},\n' "$_env"
    printf '  "VER": %s,\n  "hyperframes": %s,\n  "date": %s,\n  "re-render": %s\n}\n' "$(_js "${VER:-}")" "$(_js "$HF")" \
      "$(_js "$(date -u +%Y-%m-%dT%H:%M:%SZ)")" "$(_js "$_cmd")"
  } > "$1.render.json"
  echo "-> $1.render.json"
}

if [ "$MODE" = "alpha" ]; then
  if [ -n "${MBLUR:-}" ]; then
    hf render . -c "compositions/$ID.html" --fps "$SS_FPS" --quality standard \
      --video-frame-format png --format mov --output "renders/$ID-ss.mov"
    NB=$(mb_frames "renders/$ID-ss.mov")
    [ -z "${STEP_FPS:-}" ] || NB=""   # `&& NB=` would exit under set -e
    ffmpeg -y -v error -i "renders/$ID-ss.mov" ${NB:+-frames:v "$NB"} -vf \
      "format=rgba64le,premultiply=inplace=1,$MB_CORE,unpremultiply=inplace=1,${POST_PRE}setpts=N/($RFPS)/TB$EXPAND,${POST_GRAIN}$TO709" \
      -c:v prores_ks -profile:v 4444 -r "$FPS" "renders/$ID-alpha$SUF.mov"
    rm "renders/$ID-ss.mov"
    echo "-> renders/$ID-alpha$SUF.mov (motion blur baked)"
  elif [ -n "${STEP_FPS:-}" ]; then
    hf render . -c "compositions/$ID.html" --fps "$ANIM_FPS" --quality standard \
      --video-frame-format png --format mov --output "renders/$ID-step$SUF.mov"
    # hyperframes writes the STEP_FPS render AT 12 fps: hold each frame up to the timeline rate (left at 12 the
    # mov is half the frames and its holds drift off the grid). Frame duplication only, the alpha stays straight.
    NF=$(step_frames "renders/$ID-step$SUF.mov")
    ffmpeg -y -v error -i "renders/$ID-step$SUF.mov" -frames:v "$NF" -vf \
      "${POST_PRE}fps=$FPS,tpad=stop=2:stop_mode=clone,${POST_GRAIN}$TO709" \
      -c:v prores_ks -profile:v 4444 -r "$FPS" "renders/$ID-alpha$SUF.mov"
    rm "renders/$ID-step$SUF.mov"
    echo "-> renders/$ID-alpha$SUF.mov ($STEP_FPS fps held to $FPS, $NF frames)"
  elif [ -n "$POST_PRE$POST_GRAIN" ]; then
    hf render . -c "compositions/$ID.html" --fps "$ANIM_FPS" --quality standard \
      --video-frame-format png --format mov --output "renders/$ID-pre$SUF.mov"
    ffmpeg -y -v error -i "renders/$ID-pre$SUF.mov" -vf "${POST_PRE}${POST_GRAIN}$TO709" \
      -c:v prores_ks -profile:v 4444 -r "$FPS" "renders/$ID-alpha$SUF.mov"
    rm "renders/$ID-pre$SUF.mov"
    echo "-> renders/$ID-alpha$SUF.mov (post: ${GLOW:+glow $GLOW }${SCAN:+scanlines ${SCAN_AMP:-0.10} }${GRAIN:+grain $GRAIN})"
  else
    hf render . -c "compositions/$ID.html" --fps "$ANIM_FPS" --quality standard \
      --video-frame-format png --format mov --output "renders/$ID-hf$SUF.mov"
    ffmpeg -y -v error -i "renders/$ID-hf$SUF.mov" -vf "$TO709" -c:v prores_ks -profile:v 4444 "renders/$ID-alpha$SUF.mov"
    rm "renders/$ID-hf$SUF.mov"
  fi
  same_as_previous "renders/$ID-alpha$SUF.mov"
  write_record "renders/$ID-alpha$SUF.mov"
else
  if [ -n "${MBLUR:-}" ]; then
    hf render . -c "compositions/$ID.html" --fps "$SS_FPS" --quality standard \
      --output "renders/$ID-ss$SUF.mp4"
    # opaque full-screen: no premultiply needed, and the grain rides in the same pass
    NB=$(mb_frames "renders/$ID-ss$SUF.mp4")
    [ -z "${STEP_FPS:-}" ] || NB=""   # `&& NB=` would exit under set -e
    ffmpeg -y -v error -i "renders/$ID-ss$SUF.mp4" ${NB:+-frames:v "$NB"} -vf \
      "$MB_CORE,setpts=N/($RFPS)/TB$EXPAND,$(full_grain "renders/$ID-ss$SUF.mp4")" \
      -c:v libx264 -crf 14 -pix_fmt yuv420p -an -r "$FPS" "renders/$ID$SUF.mp4"
    rm "renders/$ID-ss$SUF.mp4"
    echo "-> renders/$ID$SUF.mp4 (motion blur + grain baked)"
  else
    hf render . -c "compositions/$ID.html" --fps "$ANIM_FPS" --quality standard \
      --output "renders/$ID-clean$SUF.mp4"
    NF=""
    [ -z "${STEP_FPS:-}" ] || NF=$(step_frames "renders/$ID-clean$SUF.mp4")   # the same cap as the alpha expansion
    # the standing film-grain pass (same recipe as bg-light) — full-screens only
    ffmpeg -y -v error -i "renders/$ID-clean$SUF.mp4" ${NF:+-frames:v "$NF"} \
      -vf "${EXPAND#,}${EXPAND:+,tpad=stop=2:stop_mode=clone,}$(full_glow "renders/$ID-clean$SUF.mp4")$(full_grain "renders/$ID-clean$SUF.mp4")" \
      -c:v libx264 -crf 14 -pix_fmt yuv420p -an "renders/$ID$SUF.mp4"
    rm "renders/$ID-clean$SUF.mp4"
    echo "-> renders/$ID$SUF.mp4 (grain baked)"
  fi
  same_as_previous "renders/$ID$SUF.mp4"
  write_record "renders/$ID$SUF.mp4"
fi
