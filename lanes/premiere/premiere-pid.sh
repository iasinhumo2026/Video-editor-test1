#!/bin/bash
# premiere-pid.sh: print the pid of the RUNNING Adobe Premiere Pro app binary, exit 1 if none.
#
# The process is NOT called "Adobe Premiere Pro". It carries the year: the binary is
# ".../Adobe Premiere Pro 2026.app/Contents/MacOS/Adobe Premiere Pro 2026", so
# `pgrep -x "Adobe Premiere Pro"` matches nothing while the app is plainly up (2026-09-02,
# reported "not running" to the user with the bridge panel live on screen). And `pgrep -f` on the
# path over-matches: crashpad_handler, dynamiclinkmanager, the CEP helpers and AdobeIPCBroker
# (whose pid is usually LOWER, so `| head -1` picked it) all carry the app path on their
# command lines. Match the executable path itself (ps `comm`, no args) anchored on the
# MacOS/Adobe Premiere Pro<anything> tail, which only the app binary has.
#
# Usage:  lanes/premiere/premiere-pid.sh            -> "92235" / exit 1
#         lanes/premiere/premiere-pid.sh --name     -> "Adobe Premiere Pro 2026" (the process name)
# "Is Premiere running?" = this script. "Can I drive it?" = `premiere-bridge.mjs ping`, which is
# the one that matters for any bridge work; a running app with no panel is still unreachable.
set -u
case "$(uname -s)" in
  Darwin) ;;
  MINGW*|MSYS*|CYGWIN*) PY=python3; "$PY" -c '' 2>/dev/null || PY=python
    exec "$PY" "$(cd "$(dirname "$0")" && pwd)/premiere_win.py" pid "$@" ;;     # Windows backend (2026-09-27)
  *) echo "[premiere-pid.sh] macOS and Windows only" >&2; exit 3 ;;
esac
MODE="${1:-pid}"
LINE="$(ps -axo pid=,comm= | grep -E '/Contents/MacOS/Adobe Premiere Pro[^/]*$' | grep -v '(Beta)' | head -1)"
[ -n "$LINE" ] || { echo "[premiere-pid] Premiere is not running" >&2; exit 1; }
PID="$(printf '%s' "$LINE" | awk '{print $1}')"
case "$MODE" in
  --name) printf '%s\n' "$LINE" | sed 's|^ *[0-9]* ||; s|.*/||' ;;
  *) printf '%s\n' "$PID" ;;
esac
