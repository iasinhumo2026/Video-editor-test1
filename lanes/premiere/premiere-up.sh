#!/bin/bash
# premiere-up.sh — bring Premiere Pro + the MCP bridge up with no human clicks.
#
#   ./lanes/premiere/premiere-up.sh                          # launch, wait for bridge
#   ./lanes/premiere/premiere-up.sh projects/<job>/premiere/<job>.prproj
#   ./lanes/premiere/premiere-up.sh --restart [project]      # quit first, then relaunch
#   ./lanes/premiere/premiere-up.sh --quit                   # save + graceful quit, no relaunch
#   ./lanes/premiere/premiere-up.sh -h                       # this usage
#
# --quit is the "project CLOSED" half of a headless .prproj write (grade-lut.py apply):
#   premiere-up.sh --quit  →  grade-lut.py apply <job>.prproj  →  premiere-up.sh <job>.prproj
# Closing only the project instead is no faster: with no project open Premiere drops the CEP
# panel, so the bridge dies either way and the relaunch is what brings it back.
#
# With a PROJECT and a bridge ALREADY up, this REFUSES rather than pretending: launching
# cannot switch the open project, so use --restart <project> to swap.
#
# Relies on the autostart patch in the CEP panel (bridge-cep.js, marked
# "REPO-PATCH: autostart") plus <StartOn> in CSXS/manifest.xml, which together
# load the panel and start the bridge when Premiere activates. If the panel is
# ever re-copied from vendor/premiere-mcp/cep-plugin/ those patches ride along,
# because the vendored copy carries them too.
#
# Exits 0 once `ping` answers, non-zero on timeout. bash 3.2 clean.

set -u

REPO="$(cd "$(dirname "$0")/../.." && pwd)"

# macOS and Windows (Git Bash). Windows (2026-09-27, the author's Windows test): the same flow with its own
# primitives, every one proven by hand first: the exe under %ProgramFiles%\Adobe, `tasklist` for the pid, `cmd start`
# to launch WITH the project (launching with none, then open_project, dropped the CEP panel: PR8), the bridge's
# app.quit() for a graceful quit (there is no AppleEvent fallback), the CEP panel under %APPDATA%.
case "$(uname -s)" in
  Darwin) OS=mac ;;
  MINGW*|MSYS*|CYGWIN*) OS=win ;;
  *) echo "[premiere-up] Premiere Pro runs on macOS and Windows only." >&2; exit 2 ;;
esac

# The app bundle is year-branded and Creative Cloud moves clients onto a new one every year,
# so NEVER hardcode it: discover what is actually installed (newest wins), and let PREMIERE_APP
# override. A stale name made pid_of() match nothing, which reads as "Premiere is not running"
# and silently turns every quit into a no-op (audit, 2026-09-02).
premiere_apps() {   # installed app NAMES (Windows: exe PATHS), newest last, Beta builds excluded
  if [ "$OS" = win ]; then
    ls -d "${PROGRAMFILES:-/c/Program Files}"/Adobe/Adobe\ Premiere\ Pro*/Adobe\ Premiere\ Pro.exe 2>/dev/null \
      | grep -v '(Beta)' | sort -V
    return
  fi
  ls -d /Applications/Adobe\ Premiere\ Pro*/Adobe\ Premiere\ Pro*.app \
        /Applications/Adobe\ Premiere\ Pro*.app 2>/dev/null \
    | sed 's|.*/||; s|\.app$||' | grep -v '(Beta)' | sort -u -V
}
if [ -n "${PREMIERE_APP:-}" ]; then
  APP="$PREMIERE_APP"
else
  # A RUNNING Premiere wins over a newer installed one: this script's whole job is to talk to
  # the instance holding the project, and a machine with both a release and a Beta build (or two
  # release years) would otherwise be driven to the wrong one.
  if [ "$OS" = mac ]; then
    APP="$(pgrep -l -f '/Adobe Premiere Pro[^/]*\.app/Contents/MacOS/' 2>/dev/null \
           | sed -n 's|.*/\(Adobe Premiere Pro[^/]*\)\.app/Contents/MacOS/.*|\1|p' | head -1)"
  else
    APP=""
  fi
  [ -n "$APP" ] || APP="$(premiere_apps | tail -1)"
fi
if [ -z "$APP" ]; then
  echo "[premiere-up] ERROR: no Adobe Premiere Pro found (macOS: /Applications; Windows: %ProgramFiles%\\Adobe)." >&2
  echo "[premiere-up] Set PREMIERE_APP to its application name (Windows: the exe's path) if it lives elsewhere." >&2
  exit 1
fi
TIMEOUT="${TIMEOUT:-180}"
PROJECT=""
RESTART=0
QUIT_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --restart) RESTART=1 ;;
    --quit)    RESTART=1; QUIT_ONLY=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) PROJECT="$arg" ;;
  esac
done

log() { echo "[premiere-up] $*"; }

bridge_ping() {
  node "$REPO/lanes/premiere/premiere-bridge.mjs" ping '{}' 2>/dev/null \
    | grep -q '"connected": *true'
}

# --- 0. already up? -----------------------------------------------------------
# With a PROJECT argument this used to LIE (found 2026-09-02): it reported "nothing to do"
# and exited 0 while whatever was already open stayed open, so a caller asking for job B got
# job A and no warning. `open -a` cannot switch the front project either. So: compare, refuse.
if [ "$RESTART" -eq 0 ] && bridge_ping; then
  PING="$(node "$REPO/lanes/premiere/premiere-bridge.mjs" ping '{}' 2>/dev/null | grep -v '^\[')"
  OPEN="$(printf '%s\n' "$PING" | sed -n 's/.*"projectName": *"\([^"]*\)".*/\1/p' | head -1)"
  if [ -n "$PROJECT" ] && [ -n "$OPEN" ] && [ "$OPEN" != "$(basename "$PROJECT")" ]; then
    log "REFUSING: bridge is up with $OPEN open, not $(basename "$PROJECT")"
    log "  launching cannot switch the open project. To swap:"
    log "    $0 --restart $PROJECT"
    exit 1
  fi
  log "bridge already connected — nothing to do"
  printf '%s\n' "$PING" | tail -12
  exit 0
fi

# --- 1. quit if restarting ----------------------------------------------------
# A bare `tell application ... to quit` is NOT reliable here: Premiere can accept
# the AppleEvent, fail to complete it (-1712 timeout), and leave its ExtendScript
# thread WEDGED (the CEP panel keeps rendering "Connected" from its own CEF
# process while every bridge command times out). So: save through the bridge
# first (while it still answers), then a graceful quit, then WAIT. NEVER
# SIGTERM/SIGKILL (see the block below): Premiere logs any non-graceful exit as
# a crash, the crash dialog blocks the CEP panel next launch, and timeline state
# comes back subtly wrong. If it will not quit, stop and hand it to the user.
# Exact process NAME, not a path match: crashpad_handler and AdobeIPCBroker both carry the
# app path on their command lines and OUTLIVE a quit, so `pgrep -f <path>` kept reporting
# "still running" after Premiere was long gone and every graceful quit read as a failure
# (2026-09-02: the quit had worked, the save had landed, the script said it had not).
pid_of() {
  if [ "$OS" = win ]; then
    tasklist //FI "IMAGENAME eq Adobe Premiere Pro.exe" //FO CSV //NH 2>/dev/null \
      | tr -d '\r' | awk -F'","' '/Adobe Premiere Pro.exe/ {print $2; exit}'
  else
    pgrep -x "$APP" 2>/dev/null | head -1
  fi
}

if [ "$RESTART" -eq 1 ] && [ -n "$(pid_of)" ]; then
  if bridge_ping; then
    log "saving project through the bridge before quit"
    node "$REPO/lanes/premiere/premiere-bridge.mjs" save_project '{}' >/dev/null 2>&1 || \
      log "  WARN: save_project failed — continuing (unsaved work may be lost)"
  else
    log "WARN: bridge not answering — cannot save first; quitting anyway"
  fi

  # Premiere refuses AppleEvents on this machine: `tell application ... to quit`
  # answers -600 "Application isn't running" while the process is plainly up
  # (measured 2026-09-01), so the osascript route below has never actually
  # quit anything. The one that works is ExtendScript `app.quit()` through the
  # bridge — same graceful shutdown, no AppleEvent. Shutdown takes 60-90s on a
  # big project and the WINDOWS disappear long before the process does, so wait
  # on the pid, never on the window list.
  log "quitting Premiere (graceful, via the bridge)"
  if bridge_ping; then
    node "$REPO/lanes/premiere/premiere-bridge.mjs" execute_extendscript \
      '{"script":"(function(){ app.project.save(); app.quit(); return \"quit\"; })()"}' \
      >/dev/null 2>&1 || true
  elif [ "$OS" = mac ]; then
    osascript -e "with timeout of 15 seconds
      tell application \"$APP\" to quit
    end timeout" >/dev/null 2>&1 || true
  else
    log "  the bridge is down and Windows has no scripted quit: close Premiere by hand (File > Exit)"
  fi

  waited=0
  while [ -n "$(pid_of)" ] && [ "$waited" -lt 150 ]; do sleep 5; waited=$((waited + 5)); done

  # NEVER escalate to kill/kill -9. Premiere treats any non-graceful exit as a
  # CRASH and greets the next launch with a modal "Sorry, an error occurred"
  # report dialog — which then blocks the CEP panel from loading and defeats the
  # whole point of this script. A wedged Premiere is the user's to quit by hand.
  if [ -n "$(pid_of)" ]; then
    log "  graceful quit did NOT take (Premiere's scripting thread may be wedged)."
    log "  Quit it by hand (macOS: Cmd-Q or Force Quit; Windows: File > Exit), then re-run this script."
    log "  Not force-killing: an unclean exit makes Premiere show a crash dialog on next launch."
    exit 1
  fi
  log "  Premiere down"
  rm -f /tmp/premiere-mcp-bridge/command-*.json /tmp/premiere-mcp-bridge/response-*.json 2>/dev/null || true
fi

if [ "$QUIT_ONLY" -eq 1 ]; then
  [ -n "$(pid_of)" ] && exit 1
  log "Premiere is down — safe to write a .prproj now; relaunch with: $0 <project.prproj>"
  exit 0
fi

# --- 2. verify the autostart patches are in place -----------------------------
if [ "$OS" = win ]; then CEP="${APPDATA:-$HOME/AppData/Roaming}/Adobe/CEP/extensions/MCPBridgeCEP"
else CEP="$HOME/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP"; fi
if [ ! -d "$CEP" ]; then
  log "ERROR: CEP panel not installed at $CEP"
  log "  fix: cp -R '$REPO/vendor/premiere-mcp/cep-plugin/' '$CEP'"
  exit 1
fi
grep -q "REPO-PATCH: autostart" "$CEP/bridge-cep.js" \
  || log "WARN: autostart patch missing from installed panel — you may have to click Start Bridge. Fix: uv run lanes/premiere/premiere-templates/apply-autostart-patch.py \"$CEP\" (idempotent)"
grep -q "StartOn" "$CEP/CSXS/manifest.xml" \
  || log "WARN: <StartOn> missing from manifest — panel may not auto-open. Fix: uv run lanes/premiere/premiere-templates/apply-autostart-patch.py \"$CEP\" (idempotent)"

# --- 3. launch ----------------------------------------------------------------
if [ -n "$PROJECT" ]; then
  case "$PROJECT" in /*|[A-Za-z]:*) ABS="$PROJECT" ;; *) ABS="$REPO/$PROJECT" ;; esac
  [ -f "$ABS" ] || { log "ERROR: no such project: $ABS"; exit 1; }
  log "launching $APP with $(basename "$ABS")"
  # </dev/null >/dev/null: a launched Premiere INHERITS the pipes, so `premiere-up.sh | tail` never returned (2026-09-27)
  if [ "$OS" = win ]; then cmd //c start "" "$(cygpath -w "$APP")" "$(cygpath -w "$ABS")" </dev/null >/dev/null 2>&1
  else open -a "$APP" "$ABS"; fi
else
  log "launching $APP"
  if [ "$OS" = win ]; then
    log "  WARN: on Windows open the project by LAUNCHING with it: open_project after a bare launch drops the panel"
    cmd //c start "" "$(cygpath -w "$APP")" </dev/null >/dev/null 2>&1
  else open -a "$APP"; fi
fi

# --- 4. wait for the bridge ---------------------------------------------------
# NOTE: bridge_ping itself BLOCKS (it writes a command file and waits for the
# panel to answer), so elapsed time is measured off the wall clock, not off the
# sleep counter — otherwise a boot spent inside the first ping reports as 0s.
log "waiting for bridge (timeout ${TIMEOUT}s)..."
START=$SECONDS
waited=0
while [ "$waited" -lt "$TIMEOUT" ]; do
  if bridge_ping; then
    log "bridge UP after $((SECONDS - START))s"
    node "$REPO/lanes/premiere/premiere-bridge.mjs" ping '{}' 2>/dev/null | grep -v '^\[' | tail -12
    exit 0
  fi
  sleep 3
  waited=$((SECONDS - START))
  [ $((waited % 30)) -lt 3 ] && log "  still waiting (${waited}s)..."
done

log "TIMED OUT after $((SECONDS - START))s"
log "  Premiere may be sitting on the Home screen (no project open = no panel host),"
log "  or waiting on a dialog. Open a project, then re-run this script."
exit 1
