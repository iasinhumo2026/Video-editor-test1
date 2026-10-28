#!/bin/bash
# window-grab.sh — screenshot an app's window WITHOUT bringing it to the front.
#
#   ./workflows/window-grab.sh Premiere /tmp/pr.png     # biggest Premiere window
#   ./workflows/window-grab.sh Premiere /tmp/pr.png 3   # 3rd-biggest (panels, dialogs)
#   ./workflows/window-grab.sh --list Premiere          # just enumerate windows
#
# Why: the user works in other apps while Claude drives Premiere. `open -a` steals
# focus and interrupts them; `screencapture -D <display>` only sees whatever is
# on top. `screencapture -l<windowID>` captures the window's OWN buffer, so an
# occluded (or fully covered) window still grabs correctly.
#
# Window IDs come from CGWindowListCopyWindowInfo via a tiny inline Swift
# program — no pip installs, no pyobjc (system python3 has no Quartz module).
# Needs Screen Recording permission, which is already granted for screencapture.
#
# Caveat: a MINIMIZED window has no live buffer and grabs blank/stale. Windows
# on another macOS Space are still captured (we do not use optionOnScreenOnly).

set -u
case "$(uname -s)" in
  Darwin) ;;
  MINGW*|MSYS*|CYGWIN*)
    # Windows: workflows/wincap.py does the same job (PrintWindow reads a COVERED window's own buffer; 2026-09-27)
    HERE="$(cd "$(dirname "$0")" && pwd)"
    if [ "${1:-}" = "--list" ]; then shift; exec uv run -q "$HERE/wincap.py" list "${1:-Premiere}"; fi
    exec uv run -q "$HERE/wincap.py" grab "${1:-Premiere}" "${2:-window-grab.png}" "${3:-1}" ;;
  *) echo "[window-grab.sh] macOS and Windows only" >&2; exit 3 ;;
esac

LIST_ONLY=0
if [ "${1:-}" = "--list" ]; then LIST_ONLY=1; shift; fi

APP="${1:-Premiere}"
OUT="${2:-/tmp/window-grab.png}"
INDEX="${3:-1}"

# BSD mktemp requires the X run at the end; Swift accepts this extensionless source.
SWIFT_SRC="$(mktemp /tmp/wingrab-XXXXXX)"
trap 'rm -f "$SWIFT_SRC"' EXIT

cat > "$SWIFT_SRC" <<'SWIFT'
import CoreGraphics
import Foundation

let needle = CommandLine.arguments.count > 1 ? CommandLine.arguments[1].lowercased() : ""
// Deliberately NOT .optionOnScreenOnly: we want windows that are occluded or
// parked on another Space, which is the whole point of this tool.
let opts = CGWindowListOption(arrayLiteral: .excludeDesktopElements)
guard let list = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else {
    FileHandle.standardError.write("cannot read window list (Screen Recording permission?)\n".data(using: .utf8)!)
    exit(1)
}
var rows: [(Int, Int, Int, String, String)] = []
for w in list {
    let owner = (w[kCGWindowOwnerName as String] as? String) ?? ""
    if !needle.isEmpty && !owner.lowercased().contains(needle) { continue }
    let layer = (w[kCGWindowLayer as String] as? Int) ?? 0
    if layer != 0 { continue }                     // 0 = normal app window
    let num = (w[kCGWindowNumber as String] as? Int) ?? 0
    let name = (w[kCGWindowName as String] as? String) ?? ""
    let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
    let wd = Int((b["Width"] as? Double) ?? 0)
    let ht = Int((b["Height"] as? Double) ?? 0)
    if wd < 200 || ht < 200 { continue }            // skip tooltips//shadows
    rows.append((wd * ht, num, wd * 100000 + ht, owner, name))
}
rows.sort { $0.0 > $1.0 }                           // biggest window first
for r in rows {
    let wd = r.2 / 100000, ht = r.2 % 100000
    print("\(r.1)\t\(wd)x\(ht)\t\(r.3)\t\(r.4)")
}
SWIFT

ROWS="$(swift "$SWIFT_SRC" "$APP" 2>/dev/null)"
if [ -z "$ROWS" ] && [ "${APP#* }" != "$APP" ]; then
  # CGWindow OWNER names are not process names: Premiere's owner is "Adobe Premiere", not
  # "Adobe Premiere Pro 2026". A multi-word needle that matched nothing reported "app not running"
  # and hid a live modal for three minutes (2026-09-02). Retry on the first word before saying so.
  FIRST="${APP%% *}"
  ROWS="$(swift "$SWIFT_SRC" "$FIRST" 2>/dev/null)"
  [ -n "$ROWS" ] && echo "[window-grab] no window owner contains '$APP'; matched '$FIRST' instead" >&2
fi
if [ -z "$ROWS" ]; then
  echo "[window-grab] no window owner contains '$APP'" >&2
  OWNERS="$(swift "$SWIFT_SRC" "" 2>/dev/null | cut -f3 | sort -u | paste -sd, - | sed 's/,/, /g')"
  echo "[window-grab]   owners with a window right now: ${OWNERS:-none (Screen Recording permission?)}" >&2
  echo "[window-grab]   the app listed under another name = wrong needle, not a dead app; absent = not running or minimized (no buffer)" >&2
  exit 1
fi

if [ "$LIST_ONLY" -eq 1 ]; then
  echo "$ROWS" | awk -F'\t' 'BEGIN{printf "%-10s %-12s %-28s %s\n","WINDOWID","SIZE","APP","TITLE"}
                             {printf "%-10s %-12s %-28s %s\n",$1,$2,$3,$4}'
  exit 0
fi

WID="$(echo "$ROWS" | sed -n "${INDEX}p" | cut -f1)"
if [ -z "$WID" ]; then
  echo "[window-grab] no window at index $INDEX (have $(echo "$ROWS" | wc -l | tr -d ' '))" >&2
  exit 1
fi

# -o drops the drop-shadow, -x kills the capture sound.
screencapture -x -o -l"$WID" "$OUT" || { echo "[window-grab] capture failed for id $WID" >&2; exit 1; }
[ -s "$OUT" ] || { echo "[window-grab] wrote an EMPTY file (window likely minimized)" >&2; exit 1; }
echo "[window-grab] $(echo "$ROWS" | sed -n "${INDEX}p" | cut -f2,3,4 | tr '\t' ' ') -> $OUT"
