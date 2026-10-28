#!/bin/bash
# screen-record.sh — record ONE app window to an mp4 for a `screen-rec` graphic (step 5b, Stage 2).
#
#   ./workflows/screen-record.sh Chrome projects/<job>/assets/captures/g4.mp4 5      # biggest Chrome window, 5 s
#   ./workflows/screen-record.sh Finder out.mp4 4 2                                  # 2nd-biggest window
#   ./workflows/screen-record.sh --clicks Chrome out.mp4 5                           # show click rings
#   ./workflows/screen-record.sh --force Chrome out.mp4 5                            # overwrite an existing out (default: refuse)
#   ./workflows/screen-record.sh --list Chrome                                       # enumerate windows (+ bounds)
#   FPS=24000/1001 ./workflows/screen-record.sh Finder out.mp4 4                      # conform to the job's rate (default 30000/1001)
#   VE_CAPTURE_FRONTED=1 ./workflows/screen-record.sh Chrome out.mp4 5               # app already raised with computer-use tools; skip AppleScript
#   ./workflows/screen-record.sh --preflight projects/<job>/pii.json Chrome out.mp4 5  # OCR the window first, refuse the take on a hit
#   ./workflows/screen-record.sh --bounds 1280,800 Chrome out.mp4 5                   # size the window for the take, put it back after
#   ./workflows/screen-record.sh --bounds 1280,800,0,40 --settle 1500 --preflight … # size AND place it; settle 1.5 s before each grab
#
# --preflight <file>  THE GATE BEFORE A TAKE (2026-09-21: five takes were thrown out after the fact for staging prompts
#                     and a churn figure on screen). Two grabs, each run through `pii-scan.py --still <grab> --pii
#                     <file>`; a hit in either refuses the take with exit 4 naming the hits. First the window's own
#                     buffer (window-grab.sh), before anything is fronted; then, once the app is fronted and settled,
#                     the exact screen rect the take records (screencapture -R). Only the second sees a dialog, a
#                     notification banner or another window drawn OVER the window (2026-09-23: a permission dialog
#                     passed the window grab and sat in every frame of the take). <file> is a pii.json ({"needles",
#                     "phrases", "any_number"}) or a phrases file, one per line. A grab that fails or reads no text is
#                     refused too: a gate that cannot see the window passes nothing.
#                     It checks the window as the take STARTS; what the take then shows is swept afterwards with
#                     `uv run workflows/pii-scan.py projects/<job> --raw assets/captures/<take>.mp4 --all` (a relative
#                     --raw is read from the job folder), which writes the take's own
#                     review/pii-scan-<take>.json and never the raw's hit map. A phrase matches from the start of a
#                     word, so a stem catches every ending ('cancell': cancelled, cancelling).
# --settle MS         wait before each preflight grab (default 800; the rect grab waits at least the 0.4 s a fronted
#                     app gets): an early grab raced the UI once.
# --bounds W,H[,X,Y]  set the window's size (and position) through System Events for the take, and restore the
#                     original bounds afterwards, on failure too (trap); both are printed. Points, not pixels. A window
#                     that will not take the size (the app clamps it) refuses the take rather than record the wrong
#                     layout (2026-09-23: "size it" shipped a full-window take). Needs Accessibility for the terminal.
#
# The still counterpart is window-grab.sh (captures a COVERED window's own buffer, never fronts
# anything). Video cannot do that: `screencapture -v` ignores -l<windowid> and records the whole
# display (measured 2026-09-11), so this records the window's screen RECT and must bring the app
# to the front for the take. That is deliberate and brief: a capture is production footage, not a
# verification frame — say so in the report, and run it in the background so the session can
# drive the action (a scroll, a click, a timeline filling) while the clock runs:
#
#   Bash(run_in_background): ./workflows/screen-record.sh Chrome …/g4.mp4 6
#   ~1 s later: scroll / click via the browser or computer-use tools
#   the recording stops by itself at <seconds>
#
# Output: H.264 mp4 at a CONSTANT rate (FPS=30000/1001 default: pass the timeline's), native pixels (a Retina
# window records at 2x its point size — the printed WxH is what the comp scales), exactly <seconds> long (a window
# that stops changing holds its last frame to the end). No audio. macOS here; Windows through workflows/wincap.py (same flags).
# A TERM or INT stops the take at once, puts a --bounds window back and leaves no .rec.mov behind.
# Exit 0 = recorded. 1 = could not record. 2 = usage. 3 = neither macOS nor Windows. 4 = the preflight refused the take.

set -u
case "$(uname -s)" in
  Darwin) ;;
  MINGW*|MSYS*|CYGWIN*)
    # Windows: workflows/wincap.py record takes the same flags and exit codes (gdigrab over the fronted window's rect,
    # the preflight through pii-scan.py --still on the window buffer and the screen rect; 2026-09-27)
    exec uv run -q "$(cd "$(dirname "$0")" && pwd)/wincap.py" record "$@" ;;
  *) echo "[screen-record] macOS and Windows only" >&2; exit 3 ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
LIST_ONLY=0; CLICKS=""; FORCE=0; PREFLIGHT=""; SETTLE=800; BOUNDS=""
need_value() { [ $# -ge 2 ] && [ -n "$2" ] || { echo "[screen-record] $1 needs a value" >&2; exit 2; }; }
while [ $# -gt 0 ]; do
  case "$1" in
    --list) LIST_ONLY=1; shift ;;
    --clicks) CLICKS="-k"; shift ;;
    -h|--help) awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 0 ;;
    --force) FORCE=1; shift ;;
    --preflight) need_value "$@"; PREFLIGHT="$2"; shift 2 ;;
    --settle) need_value "$@"; SETTLE="$2"; shift 2 ;;
    --bounds) need_value "$@"; BOUNDS="$2"; shift 2 ;;
    *) break ;;
  esac
done
case "$SETTLE" in ''|*[!0-9]*) echo "[screen-record] --settle takes whole milliseconds, got '$SETTLE'" >&2; exit 2 ;; esac
if [ -n "$PREFLIGHT" ] && [ ! -f "$PREFLIGHT" ]; then echo "[screen-record] --preflight: no file at $PREFLIGHT" >&2; exit 2; fi
if [ -n "$BOUNDS" ]; then
  IFS=, read -r BW BH BX BY EXTRA <<< "$BOUNDS"
  case "$BW,$BH" in *[!0-9,]*|,*|*,) echo "[screen-record] --bounds is W,H[,X,Y] in points, got '$BOUNDS'" >&2; exit 2 ;; esac
  if [ -n "$EXTRA" ] || { [ -n "$BX" ] && [ -z "$BY" ]; } || { [ -n "$BX" ] && ! [[ "$BX" =~ ^-?[0-9]+$ && "$BY" =~ ^-?[0-9]+$ ]]; }; then
    echo "[screen-record] --bounds is W,H[,X,Y] in points, got '$BOUNDS'" >&2; exit 2
  fi
  BW=$((10#$BW)); BH=$((10#$BH))              # base 10: a leading zero is not octal (040 is 40, not 32)
  [ -n "$BX" ] && { BX=$(( ${BX%%[0-9]*}10#${BX#-} )); BY=$(( ${BY%%[0-9]*}10#${BY#-} )); }
  # the window list skips anything under 200 pt: a smaller window could not be found again to record or restore
  if [ "$BW" -lt 200 ] || [ "$BH" -lt 200 ]; then echo "[screen-record] --bounds: at least 200x200 points, got ${BW}x${BH}" >&2; exit 2; fi
fi

APP="${1:-}"
OUT="${2:-}"
SECS="${3:-5}"
INDEX="${4:-1}"
[ -n "$APP" ] || { echo "usage: screen-record.sh [--clicks] [--force] [--preflight <file>] [--settle MS] [--bounds W,H[,X,Y]] <App> <out.mp4> [seconds] [index]   |   --list <App>" >&2; exit 2; }
case "$APP" in -*) echo "[screen-record] flags go BEFORE the app name: $APP" >&2; exit 2 ;; esac
command -v swift >/dev/null || { echo "[screen-record] needs swift (Xcode command line tools: xcode-select --install) to read the window list" >&2; exit 2; }
if [ "$LIST_ONLY" -eq 0 ]; then
  [ -n "$OUT" ] || { echo "[screen-record] missing output path" >&2; exit 2; }
  case "$OUT" in -*) echo "[screen-record] flags go BEFORE the app name: $OUT" >&2; exit 2 ;; *.rec.mov) echo "[screen-record] .rec.mov is the scratch name" >&2; exit 2 ;; esac
  case "$SECS" in ''|*[!0-9.]*|.|*.*.*) echo "[screen-record] seconds must be a number, got '$SECS'" >&2; exit 2 ;; esac
  case "$INDEX" in ''|*[!0-9]*|0) echo "[screen-record] index must be a positive integer, got '$INDEX'" >&2; exit 2 ;; esac
  if [ -e "$OUT" ] && [ "$FORCE" -eq 0 ]; then echo "[screen-record] $OUT exists — a capture already in a comp keeps its name; write a new one or pass --force" >&2; exit 2; fi
  for t in screencapture ffmpeg ffprobe osascript; do command -v "$t" >/dev/null || { echo "[screen-record] needs $t" >&2; exit 2; }; done
  if [ -n "$PREFLIGHT" ]; then command -v uv >/dev/null || { echo "[screen-record] --preflight needs uv (it runs workflows/pii-scan.py)" >&2; exit 2; }; fi
fi

# BSD mktemp requires the X run at the end; a .swift suffix can become a literal shared filename.
SWIFT_SRC="$(mktemp /tmp/screc-XXXXXX)"
GRAB=""; RECT=""; KEEP=""; MOVED=0; ORIG=""; CUR=""; PID=""; REC=""; TMP=""; KEEP_TMP=0
cleanup() {
  # a killed take stops its recorder FIRST: left running, it held the window at the take bounds for its whole clock
  if [ -n "$REC" ]; then kill "$REC" 2>/dev/null; wait "$REC" 2>/dev/null; fi
  [ "$MOVED" -eq 1 ] && restore_bounds       # defined below, and only ever armed after it is
  for g in "$GRAB" "$RECT"; do [ -n "$g" ] && [ "$g" != "$KEEP" ] && rm -f "$g"; done
  [ -n "$TMP" ] && [ "$KEEP_TMP" -eq 0 ] && rm -f "$TMP"    # a take that never became an mp4 leaves no scratch
  rm -f "$SWIFT_SRC"
}
trap cleanup EXIT
trap 'exit 129' HUP; trap 'exit 130' INT; trap 'exit 143' TERM   # a killed take still runs the EXIT trap: bounds go back
cat > "$SWIFT_SRC" <<'SWIFT'
import CoreGraphics
import Foundation
let needle = CommandLine.arguments.count > 1 ? CommandLine.arguments[1].lowercased() : ""
// on-screen only: a window on another Space or minimized cannot be in front of the rect we record
let opts = CGWindowListOption(arrayLiteral: .excludeDesktopElements, .optionOnScreenOnly)
guard let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else {
    FileHandle.standardError.write("cannot read window list (Screen Recording permission?)\n".data(using: .utf8)!)
    exit(1)
}
var rows: [(Int, String)] = []
for w in list {
    let owner = (w[kCGWindowOwnerName as String] as? String) ?? ""
    if !needle.isEmpty && !owner.lowercased().contains(needle) { continue }
    if ((w[kCGWindowLayer as String] as? Int) ?? 0) != 0 { continue }
    let num = (w[kCGWindowNumber as String] as? Int) ?? 0
    let pid = (w[kCGWindowOwnerPID as String] as? Int) ?? 0
    let name = (w[kCGWindowName as String] as? String) ?? ""
    let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
    let x = Int((b["X"] as? Double) ?? 0), y = Int((b["Y"] as? Double) ?? 0)
    let wd = Int((b["Width"] as? Double) ?? 0), ht = Int((b["Height"] as? Double) ?? 0)
    if wd < 200 || ht < 200 { continue }
    rows.append((wd * ht, "\(num)\t\(pid)\t\(x)\t\(y)\t\(wd)\t\(ht)\t\(owner)\t\(name)"))
}
rows.sort { $0.0 > $1.0 }
for r in rows { print(r.1) }
SWIFT

MATCHED="$APP"
ROWS="$(swift "$SWIFT_SRC" "$APP" 2>/dev/null)"
if [ -z "$ROWS" ] && [ "${APP#* }" != "$APP" ]; then
  FIRST="${APP%% *}"; ROWS="$(swift "$SWIFT_SRC" "$FIRST" 2>/dev/null)"
  [ -n "$ROWS" ] && { MATCHED="$FIRST"; echo "[screen-record] no window owner contains '$APP'; matched '$FIRST' instead" >&2; }
fi
if [ -z "$ROWS" ]; then
  echo "[screen-record] no ON-SCREEN window owner contains '$APP' (minimized / other Space / not running)" >&2
  OWNERS="$(swift "$SWIFT_SRC" "" 2>/dev/null | cut -f7 | sort -u | paste -sd, - | sed 's/,/, /g')"
  echo "[screen-record]   owners on screen right now: ${OWNERS:-none (Screen Recording permission?)}" >&2
  exit 1
fi

if [ "$LIST_ONLY" -eq 1 ]; then
  echo "$ROWS" | awk -F'\t' 'BEGIN{printf "%-8s %-7s %-18s %-28s %s\n","WINDOWID","PID","RECT(x,y,w,h)","APP","TITLE"}
                             {printf "%-8s %-7s %-18s %-28s %s\n",$1,$2,$3","$4","$5","$6,$7,$8}'
  exit 0
fi

ROW="$(echo "$ROWS" | sed -n "${INDEX}p")"
[ -n "$ROW" ] || { echo "[screen-record] no window at index $INDEX (have $(echo "$ROWS" | wc -l | tr -d ' '))" >&2; exit 1; }
WID="$(echo "$ROW" | cut -f1)"; PID="$(echo "$ROW" | cut -f2)"; X="$(echo "$ROW" | cut -f3)"; Y="$(echo "$ROW" | cut -f4)"
W="$(echo "$ROW" | cut -f5)"; H="$(echo "$ROW" | cut -f6)"; OWNER="$(echo "$ROW" | cut -f7)"; TITLE="$(echo "$ROW" | cut -f8)"

# --bounds: System Events finds the window by the rect CGWindow reported (within 2 pt), optionally sets new bounds,
# and prints what the window reports AFTER — so every call re-finds it and nothing trusts a window index, which
# changes whenever the app raises another of its windows.
#   osascript -e "$AX_BOUNDS" <pid> <x> <y> <w> <h> [<new x> <new y> <new w> <new h>]  ->  x,y,w,h
AX_BOUNDS='on run argv
	set pid to (item 1 of argv) as integer
	set m to {(item 2 of argv) as integer, (item 3 of argv) as integer, (item 4 of argv) as integer, (item 5 of argv) as integer}
	tell application "System Events"
		tell (first process whose unix id is pid)
			repeat with w in windows
				set {px, py} to position of w
				set {sw, sh} to size of w
				if my near(px, item 1 of m) and my near(py, item 2 of m) and my near(sw, item 3 of m) and my near(sh, item 4 of m) then
					if (count of argv) is 9 then
						try
							set position of w to {(item 6 of argv) as integer, (item 7 of argv) as integer}
							set size of w to {(item 8 of argv) as integer, (item 9 of argv) as integer}
						on error msg
							-- half applied (moved, then refused the size): put it back before saying so, or the
							-- restore looks for the window where it was and finds nothing there
							try
								set position of w to {px, py}
								set size of w to {sw, sh}
							end try
							error msg
						end try
						delay 0.3
						set {px, py} to position of w
						set {sw, sh} to size of w
					end if
					return (px as integer as text) & "," & (py as integer as text) & "," & (sw as integer as text) & "," & (sh as integer as text)
				end if
			end repeat
		end tell
	end tell
	error "no window of pid " & pid & " at " & (item 2 of argv) & "," & (item 3 of argv) & " " & (item 4 of argv) & "x" & (item 5 of argv)
end run

on near(a, b)
	return (a - b) ≤ 2 and (b - a) ≤ 2
end near'
restore_bounds() {
  MOVED=0
  local back
  # shellcheck disable=SC2046  # the x,y,w,h lists split into four arguments each, deliberately
  if back="$(osascript -e "$AX_BOUNDS" "$PID" $(echo "$CUR" | tr , ' ') $(echo "$ORIG" | tr , ' ') 2>&1)"; then
    echo "[screen-record] bounds restored: $back (the take ran at $CUR)"
  else
    echo "[screen-record] ✗ could NOT restore the window's bounds ($back): put it back to x,y,w,h = $ORIG by hand" >&2
  fi
}
off() { [ $(( $1 - $2 )) -le 2 ] && [ $(( $2 - $1 )) -le 2 ]; }   # within 2 pt, the same tolerance the finder uses

if [ -n "$BOUNDS" ]; then
  ORIG="$(osascript -e "$AX_BOUNDS" "$PID" "$X" "$Y" "$W" "$H" 2>&1)" \
    || { echo "[screen-record] --bounds: System Events cannot read the window at ${X},${Y} ${W}x${H} ($ORIG) — Accessibility permission for this terminal?" >&2; exit 1; }
  [ -n "$BX" ] || { BX="$(echo "$ORIG" | cut -d, -f1)"; BY="$(echo "$ORIG" | cut -d, -f2)"; }
  CUR="$ORIG"; MOVED=1                       # from here on the EXIT trap puts the window back, whatever happens
  # shellcheck disable=SC2046
  NOW="$(osascript -e "$AX_BOUNDS" "$PID" $(echo "$ORIG" | tr , ' ') "$BX" "$BY" "$BW" "$BH" 2>&1)" \
    || { echo "[screen-record] --bounds: could not set ${BW}x${BH} at ${BX},${BY} ($NOW)" >&2; exit 1; }
  CUR="$NOW"
  echo "[screen-record] bounds ${ORIG} -> ${NOW}  (asked ${BX},${BY},${BW},${BH}; restored after the take)"
  IFS=, read -r X Y W H <<< "$NOW"
  if ! off "$W" "$BW" || ! off "$H" "$BH"; then
    echo "[screen-record] --bounds: the window took ${W}x${H}, not ${BW}x${BH} (the app clamps its size): refusing to record the wrong layout" >&2
    exit 1
  fi
  off "$X" "$BX" && off "$Y" "$BY" || echo "[screen-record] --bounds: the window sits at ${X},${Y}, not ${BX},${BY} (macOS keeps windows on screen); recording where it is" >&2
fi

# one preflight grab through pii-scan.py --still: PASS, or refuse the take with exit 4 and keep the grab for a look
preflight_sweep() {   # <png> <what the grab shows>
  local verdict rc
  verdict="$(uv run "$HERE/pii-scan.py" --still "$1" --pii "$PREFLIGHT" 2>&1)"; rc=$?
  echo "$verdict" | sed 's/^/[preflight] /'
  case "$rc" in
    0) echo "[screen-record] PREFLIGHT PASS: $2" ;;
    1) KEEP="$1"
       echo "[screen-record] PREFLIGHT FAIL: $2 shows text that must not ship (the ✗ lines above; grab kept at $1) — clear it, then take again" >&2
       exit 4 ;;
    *) KEEP="$1"
       echo "[screen-record] PREFLIGHT could not vouch for $2 (pii-scan exit $rc, above; grab kept at $1): refusing the take" >&2
       exit 4 ;;
  esac
}

if [ -n "$PREFLIGHT" ]; then
  sleep "$(awk -v ms="$SETTLE" 'BEGIN { printf "%.3f", ms / 1000 }')"
  GRAB="$(mktemp /tmp/screc-grab-XXXXXX)" && mv "$GRAB" "$GRAB.png" && GRAB="$GRAB.png"   # a kept grab opens as an image
  # window-grab.sh ranks EVERY window of the app (other Spaces too) by area, so its index is not this script's:
  # find this window's id in its own list and grab that row
  GIDX="$("$HERE/window-grab.sh" --list "$MATCHED" 2>/dev/null | awk -v id="$WID" 'NR > 1 && $1 == id { print NR - 1; exit }')"
  if [ -z "$GIDX" ] || ! "$HERE/window-grab.sh" "$MATCHED" "$GRAB" "$GIDX" >/dev/null 2>&1 || [ ! -s "$GRAB" ]; then
    echo "[screen-record] PREFLIGHT could not grab window $WID ($OWNER): refusing the take — a gate that cannot see the window passes nothing" >&2
    exit 4
  fi
  preflight_sweep "$GRAB" "the window"
fi

mkdir -p "$(dirname "$OUT")"

# front the owning process (by pid — CGWindow owner names are not always AppleScript app names)
if [ "${VE_CAPTURE_FRONTED:-0}" != 1 ]; then
  osascript -e "tell application \"System Events\" to set frontmost of (first process whose unix id is $PID) to true" >/dev/null 2>&1 \
    || echo "[screen-record] could not front pid $PID — recording whatever is on top of the rect" >&2
fi
if [ -n "$PREFLIGHT" ]; then
  # The take records the screen RECT, not the window's own buffer: a dialog, a banner or another window drawn over
  # the window is in every frame of the take and invisible to the window grab (2026-09-23). Grab that rect too.
  sleep "$(awk -v ms="$SETTLE" 'BEGIN { printf "%.3f", (ms < 400 ? 400 : ms) / 1000 }')"
  RECT="$(mktemp /tmp/screc-rect-XXXXXX)" && mv "$RECT" "$RECT.png" && RECT="$RECT.png"
  if ! screencapture -x -R"${X},${Y},${W},${H}" "$RECT" >/dev/null 2>&1 || [ ! -s "$RECT" ]; then
    echo "[screen-record] PREFLIGHT could not grab the screen rect ${X},${Y} ${W}x${H}: refusing the take — a gate that cannot see what the take records passes nothing" >&2
    exit 4
  fi
  preflight_sweep "$RECT" "the screen rect the take records"
else
  sleep 0.4
fi

TMP="${OUT%.*}.rec.mov"
echo "[screen-record] REC $OWNER — $TITLE  rect ${X},${Y} ${W}x${H}  ${SECS}s -> $OUT"
# In the background and waited on: bash runs a trap only between commands, so a TERM to this script alone sat out
# the recorder's whole clock with the window still at the take bounds (2026-09-23); `wait` returns to the trap at
# once. <&0 keeps the script's own stdin, which an async command would otherwise swap for /dev/null.
screencapture -x $CLICKS -v -V"$SECS" -R"${X},${Y},${W},${H}" "$TMP" <&0 &
REC=$!
wait "$REC" || { REC=""; echo "[screen-record] screencapture failed" >&2; exit 1; }
REC=""
[ -s "$TMP" ] || { echo "[screen-record] wrote an EMPTY file" >&2; exit 1; }

# screencapture writes a VARIABLE-rate H.264 .mov (measured 19200/1 timebase, ~50 fps effective): a frame
# extractor fed VFR drifts, so conform to a constant rate (FPS=, default the house 29.97), drop any audio.
# It also writes a frame only when the screen CHANGES, and a conform ends where its frames do: a static window came
# out 0.067 s long for a 2 s take, and a take that holds on a finished result lost the hold (2026-09-23). So the
# last frame is held out (tpad) and the take cut at the seconds asked (-t); the .mov's own last-frame duration is
# not the clock (a 6 s take with one change conformed to 8.1 s).
FPS="${FPS:-30000/1001}"
ffmpeg -v error -y -i "$TMP" -an -vf "fps=$FPS,tpad=stop_mode=clone:stop_duration=$SECS" -t "$SECS" \
  -c:v libx264 -crf 14 -pix_fmt yuv420p -movflags +faststart "$OUT" \
  || { KEEP_TMP=1; echo "[screen-record] conform failed, keeping $TMP" >&2; exit 1; }
rm -f "$TMP"
echo "[screen-record] $(ffprobe -v error -select_streams v:0 -show_entries stream=width,height:format=duration -of csv=p=0 "$OUT" | tr '\n' ' ' | sed 's/,/x/; s/ *$//') -> $OUT"
