#!/usr/bin/env bash
# CapCut reads ProRes 4444 alpha as PREMULTIPLIED; HyperFrames writes it STRAIGHT.
# Where alpha is 255 the two are identical, so solid type looks fine — but every
# semi-transparent pixel (motion blur, glows, fades) composites as RGB + (1-a)*bg
# instead of a*RGB + (1-a)*bg and blows out to white. Convert here, on this lane only.
#
# usage: premultiply.sh <in.mov> [out.mov]     (default out: <in>-premult.mov beside the input)
set -euo pipefail

IN="${1:-}"
if [ -z "$IN" ]; then
  echo "usage: premultiply.sh <in.mov> [out.mov]" >&2
  exit 2
fi
if [ ! -f "$IN" ]; then
  echo "premultiply.sh: no such file: $IN" >&2
  exit 1
fi

OUT="${2:-}"
if [ -z "$OUT" ]; then
  DIR=$(dirname "$IN")
  BASE=$(basename "$IN")
  STEM="${BASE%.*}"
  EXT="${BASE##*.}"
  [ "$STEM" = "$BASE" ] && EXT="mov"
  OUT="$DIR/$STEM-premult.$EXT"
fi

# via rgba64 so the 12-bit source does not round through 8-bit on the way; back to YUV through the BT.709 matrix,
# tagged: ffmpeg's default RGB->YUV is BT.601 untagged, which every editing app reads as 709 (green G -21), and the
# overlays arrive 709-tagged (presets/youtube/default/reference/fullscreen-render.sh § THE COLOUR TAIL, 2026-10-13)
TO709="scale=out_color_matrix=bt709:out_range=tv,format=yuva444p10le,setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv"
if ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$IN" | grep -q .; then
  ffmpeg -y -v error -i "$IN" \
    -vf "format=rgba64le,premultiply=inplace=1,$TO709" \
    -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -c:a copy "$OUT"
else
  ffmpeg -y -v error -i "$IN" \
    -vf "format=rgba64le,premultiply=inplace=1,$TO709" \
    -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le "$OUT"
fi

echo "$OUT"
