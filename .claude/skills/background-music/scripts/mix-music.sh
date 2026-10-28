#!/usr/bin/env bash
# mix-music.sh — lay a music bed UNDER the voice on a near-final cut.
#
# DEFAULT (flat bed): the music sits at ONE constant level for the whole video —
# NO sidechain ducking, NO fade-in, just a short tail fade-out. A peak limiter
# guards the sum; NO loudnorm (single-pass loudnorm on a finished mix pumps and
# re-introduces the level variation we're trying to avoid). The voice arrives
# peak-limited at -6 dBFS (~-21 dB mean) from the static rough-cut chain, so the
# bed rides quietly under it at a fixed gain.
#
# OPT-IN (duck=on): sidechain auto-duck — music dips under the voice and breathes
# back up in the gaps — then the whole mix is re-normalized to -14 LUFS.
#
# Video stream is copied untouched (-c:v copy) — pure audio pass, no re-encode.
#
# Usage:
#   mix-music.sh <video.mp4> <music.(mp3|wav|m4a)> <out.mp4> [bed_db] [duck] [fadein] [source_in]
#
#   bed_db  music gain. Default -20 (quiet, clearly background). MORE negative =
#           quieter. Adjust after listening; recording loudness varies.
#           Stay negative — this is a BED, not a duet.
#   duck    off (default) = FLAT constant bed, no ducking. on = sidechain
#           auto-duck (music dips under voice, swells in gaps) + loudnorm.
#   fadein  music fade-in seconds at the start. Default 0 = no fade-in (hard in).
set -euo pipefail

VIDEO="${1:?usage: mix-music.sh <video> <music> <out> [bed_db] [duck] [fadein] [source_in]}"
MUSIC="${2:?need a music track}"
OUT="${3:?need an output path}"
BED_DB="${4:--20}"
DUCK="${5:-off}"
FADEIN="${6:-0}"
# a word ("off", "none") passed awk's >0 test as a string and died inside ffmpeg (2026-09-27): seconds or nothing
case "$FADEIN" in off|none|no) FADEIN=0 ;; esac
[[ "$FADEIN" =~ ^[0-9]*\.?[0-9]+$ ]] || { echo "[mix-music] fadein must be seconds (e.g. 0 or 1.5), got '$FADEIN'" >&2; exit 2; }

[ -f "$VIDEO" ] || { echo "[mix-music] no video: $VIDEO" >&2; exit 1; }
[ -f "$MUSIC" ] || { echo "[mix-music] no music: $MUSIC" >&2; exit 1; }

# Use the same sustained-entrance detector as the app lane. An explicit source-in
# is the reviewed musical choice, in seconds; otherwise review the candidate.
MUSIC_HELPER="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../workflows" && pwd)/music-onset.py"
# tr: a native Windows Python ends its print with \r\n, and the \r failed the number check below on every run
if [ -n "${7:-}" ]; then
  onset="$(uv run "$MUSIC_HELPER" "$MUSIC" --source-in "$7" | tr -d '\r')"
else
  onset="$(uv run "$MUSIC_HELPER" "$MUSIC" | tr -d '\r')"
fi
case "$onset" in
  ''|*[!0-9.]*) echo "[mix-music] no usable song entrance from music-onset.py ('$onset'); pass source_in explicitly" >&2; exit 1;;
esac

# Fade the music tail out over the last 2s for a clean ending (2026-09-04: 1.2 was too abrupt).
dur="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$VIDEO")"
fade_st="$(awk -v d="$dur" 'BEGIN{ s=d-2.0; if (s<0) s=0; printf "%.3f", s }')"

# Fade-in is OPT-IN: only add afade=t=in when FADEIN>0 (default 0 = hard in).
fadein_filt=""
if awk -v f="$FADEIN" 'BEGIN{exit !(f>0)}'; then
  fadein_filt=",afade=t=in:st=0:d=${FADEIN}"
fi

bed="[1:a]atrim=start=${onset},asetpts=N/SR/TB,aresample=48000,aloop=loop=-1:size=2147483647,volume=${BED_DB}dB${fadein_filt},afade=t=out:st=${fade_st}:d=2.0[mus]"

if [ "$DUCK" = "on" ]; then
  # OPT-IN duck: split the voice — one copy to the mix, one as the sidechain key
  # that ducks the music — then re-normalize the whole mix to -14 LUFS.
  chain="${bed};\
[0:a]asplit=2[voc][key];\
[mus][key]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350:makeup=1[ducked];\
[voc][ducked]amix=inputs=2:duration=first:normalize=0[mix]"
  post="loudnorm=I=-14:TP=-1.5:LRA=11"
else
  # DEFAULT flat bed: constant ${BED_DB}dB music + voice, peak-limited, NO loudnorm
  # (loudnorm on a finished mix pumps — that's exactly the variation we're avoiding).
  chain="${bed};[0:a][mus]amix=inputs=2:duration=first:normalize=0[mix]"
  post="alimiter=limit=-1dB:level=disabled"
fi

ffmpeg -nostdin -hide_banner -loglevel error -y \
  -i "$VIDEO" -i "$MUSIC" \
  -filter_complex "${chain};[mix]${post},asetpts=PTS-STARTPTS[outa]" \
  -map 0:v -map "[outa]" \
  -c:v copy -c:a aac -b:a 320k -ar 48000 -ac 2 \
  -movflags +faststart \
  -shortest \
  "$OUT"

echo "[mix-music] wrote $OUT  (bed ${BED_DB}dB, duck ${DUCK}, fadein ${FADEIN}s, song starts at ${onset}s of the track)" >&2
ffprobe -hide_banner -loglevel error -show_entries format=duration -of default=nw=1:nk=1 "$OUT" >&2
