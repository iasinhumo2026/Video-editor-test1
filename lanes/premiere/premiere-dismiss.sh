#!/bin/bash
# premiere-dismiss.sh: find and dismiss a native Premiere modal you cannot see.
#
#   ./lanes/premiere/premiere-dismiss.sh            # if a modal is up, post Return to Premiere until it is gone
#   ./lanes/premiere/premiere-dismiss.sh --check    # report only: exit 0 = no modal, 2 = a modal is up
#   ./lanes/premiere/premiere-dismiss.sh --key 53   # post another virtual keycode (53 = Escape) instead of Return (36)
#   ./lanes/premiere/premiere-dismiss.sh --key 2    # Windows: D, which answers a save dialog's Don't Save (proven 2026-10-13)
#
# Exit: 0 = no modal (or dismissed), 1 = Premiere not running / tooling failed, 2 = modal still up.
#
# Why this exists (2026-09-02, your-job): with the Mac password-locked, a "project appears to
# be damaged" alert was invisible to every tool, AX saw no windows, menu presses and Cmd+Q posted to
# the process were ignored, `open -a` was ignored, and window-grab captured blank. Three primitives
# worked and were re-invented mid-incident; they live here so nobody invents them a fourth time:
#
#   1. DETECT: `sample <pid> 1 -mayDie` shows a `UI_MessageBox::RunModal` frame while a native alert
#      is up. Zero such frames = no modal. (Nothing else reports it under a locked screen.)
#   2. DISMISS: a bare Return key posted straight to Premiere's pid via CGEvent.postToPid lands on the
#      alert's default button. Session-tap posts and AX presses do not.
#   3. OPEN: once DETECT reports zero, an AppleEvent opens a project where `open -a` and AX are ignored:
#      osascript -e 'tell application "Adobe Premiere Pro 2026" to open POSIX file "<path>"'
#      (not scripted here: it is the one open allowed once the hard gate below is clear).
#
# The hard gate that goes with it (lanes/premiere/premiere-grading.md § 2): after ANY refused open, no
# second open until this reports zero. Five opens queued behind one modal wedged Premiere until it
# could not quit by any means. One failed open is data; five is a wedge.

set -u
case "$(uname -s)" in
  Darwin) ;;
  MINGW*|MSYS*|CYGWIN*) PY=python3; "$PY" -c '' 2>/dev/null || PY=python
    exec "$PY" "$(cd "$(dirname "$0")" && pwd)/premiere_win.py" dismiss "$@" ;;   # Windows backend (2026-09-27)
  *) echo "[premiere-dismiss.sh] macOS and Windows only" >&2; exit 3 ;;
esac
KEY=36; MODE=dismiss; TRIES=8
while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE=check ;;
    --key) KEY="$2"; shift ;;
    --tries) TRIES="$2"; shift ;;
    *) echo "unknown arg $1" >&2; exit 1 ;;
  esac
  shift
done

# The app binary only, via the shared resolver: helper processes AND AdobeIPCBroker carry the
# app path on their command lines, and a bare `pgrep -f ... | head -1` picked IPCBroker (lower
# pid) on 2026-09-02, so keys would have gone to the wrong process.
HERE="$(cd "$(dirname "$0")" && pwd)"
PID="$("$HERE/premiere-pid.sh")" || { echo "[premiere-dismiss] Premiere is not running" >&2; exit 1; }

modal_frames() {
  # `sample` needs about a second; -mayDie keeps it from hanging on a process mid-quit.
  sample "$PID" 1 -mayDie 2>/dev/null | grep -c 'RunModal'
}

KEYPID_SRC="$HERE/premiere-templates/locked-screen/keypid.swift"
KEYPID_BIN="/tmp/video-editor/keypid"
post_key() {
  if [ ! -x "$KEYPID_BIN" ] || [ "$KEYPID_SRC" -nt "$KEYPID_BIN" ]; then
    mkdir -p "$(dirname "$KEYPID_BIN")"
    swiftc -O -o "$KEYPID_BIN" "$KEYPID_SRC" 2>/dev/null || { swift "$KEYPID_SRC" "$PID" "$KEY" pid >/dev/null; return; }
  fi
  "$KEYPID_BIN" "$PID" "$KEY" pid >/dev/null
}

N="$(modal_frames)"
if [ "$N" -eq 0 ]; then
  echo "[premiere-dismiss] pid $PID: no modal (0 RunModal frames)"
  exit 0
fi
echo "[premiere-dismiss] pid $PID: a native modal is up ($N RunModal frame(s))"
[ "$MODE" = check ] && exit 2

i=0
while [ "$i" -lt "$TRIES" ]; do
  i=$((i + 1))
  post_key
  sleep 1
  N="$(modal_frames)"
  echo "[premiere-dismiss]   posted key $KEY to pid $PID (try $i): $N RunModal frame(s) left"
  [ "$N" -eq 0 ] && { echo "[premiere-dismiss] dismissed"; exit 0; }
done
echo "[premiere-dismiss] modal still up after $TRIES tries, STOP. Do not open anything else; tell the user." >&2
exit 2
