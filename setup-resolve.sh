#!/usr/bin/env bash
# setup-resolve.sh: one-command setup for the OPTIONAL DaVinci Resolve lane.
# Wires Blackmagic's own MCP server (ResolveMCP, shipped inside DaVinci Resolve Studio 21.1 and newer)
# into .mcp.json. Nothing is downloaded or built. Safe to re-run.
#
#   macOS, Windows (native, run from Git Bash: the shell Claude Code uses there) and Linux (/opt/resolve).
#   WSL2: NOT supported. Run this natively on Windows instead.
#
# Requirements: DaVinci Resolve STUDIO 21.1 or newer, and python (for the .mcp.json merge).
#   Older than 21.1: refused with nothing changed. Update Resolve first, then re-run this.
#   Free edition: refused. Blackmagic's MCP ships only in Studio, and 21.1 took scripting out of the
#   free edition, so nothing can drive it. Upgrade to Studio, or finish in another app.
#
#   ./setup-resolve.sh            detect, verify, wire
#   ./setup-resolve.sh --studio   skip the edition check (an activated Studio detected as free)
#
# The community engine (samuelgursky/davinci-resolve-mcp, vendor/davinci-resolve-mcp) this script installed
# before 2026-10-05 is retired: a re-run replaces its .mcp.json entry and removes its folder.
#
# After it finishes: restart Claude Code once so it picks up .mcp.json, then
# verify by asking Claude to get the Resolve version.
set -euo pipefail

# Windows consoles default to cp1252; every python this script runs prints UTF-8.
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

# Resolve the PROJECT root. In the shipped package this script sits at the root;
# in the source repo it lives under packaging/overlay/. The marker file decides.
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HERE/check-setup.sh" ]]; then
  ROOT="$HERE"
elif [[ -f "$HERE/../../check-setup.sh" ]]; then
  ROOT="$(cd "$HERE/../.." && pwd)"
else
  printf 'ERROR: cannot locate the project root (check-setup.sh not found)\n' >&2
  exit 1
fi
cd "$ROOT"

say()  { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# ---- arguments -------------------------------------------------------------
FORCE_STUDIO=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --studio)  FORCE_STUDIO=1 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) fail "unknown option: $1 (usage: ./setup-resolve.sh [--studio])" ;;
  esac
  shift
done

# ---- OS detection ----------------------------------------------------------
OS="$(uname -s)"
IS_WINDOWS=0
if [[ "$OS" == "Linux" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  fail "WSL2 can't drive a Windows-side Resolve. Run this natively on Windows instead: Git for Windows + Claude Code on Windows, then re-run from Git Bash (see SETUP.md \"Windows\")."
fi

case "$OS" in
  Darwin)
    # Direct download installs into its own folder; the App Store builds sit flat in
    # /Applications (free = "DaVinci Resolve.app", Studio = "DaVinci Resolve Studio.app").
    APP_PATH="/Applications/DaVinci Resolve/DaVinci Resolve.app"
    for cand in "/Applications/DaVinci Resolve Studio.app" "/Applications/DaVinci Resolve.app"; do
      if [[ ! -e "$APP_PATH" && -d "$cand" ]]; then APP_PATH="$cand"; fi
    done
    MCP_BIN="$APP_PATH/Contents/Applications/ResolveMCP"
    ;;
  Linux)
    APP_PATH="/opt/resolve"
    # Proven on macOS and Windows; on Linux the binary's folder is looked up, not assumed.
    MCP_BIN="$(find /opt/resolve -maxdepth 3 -name ResolveMCP -type f 2>/dev/null | head -n 1 || true)"
    [[ -n "$MCP_BIN" ]] || MCP_BIN="/opt/resolve/bin/ResolveMCP"
    ;;
  MINGW*|MSYS*)
    IS_WINDOWS=1
    SYSDRV="$(cygpath -u "${SYSTEMDRIVE:-C:}")"
    APP_PATH="$SYSDRV/Program Files/Blackmagic Design/DaVinci Resolve/Resolve.exe"
    MCP_BIN="$(dirname "$APP_PATH")/ResolveMCP.exe"
    ;;
  *)
    fail "unsupported OS: $OS (on Windows, run this from Git Bash — see SETUP.md)"
    ;;
esac
[[ -e "$APP_PATH" ]] \
  || fail "DaVinci Resolve not found at $APP_PATH. Install DaVinci Resolve Studio 21.1 or newer, then re-run ./setup-resolve.sh. Nothing was changed."

resolve_version() {   # the installed app's own version string, best effort ("" when unreadable)
  case "$OS" in
    Darwin) /usr/bin/defaults read "$APP_PATH/Contents/Info" CFBundleShortVersionString 2>/dev/null || true ;;
    MINGW*|MSYS*)
      powershell.exe -NoProfile -NonInteractive -Command "(Get-Item '$(cygpath -w "$APP_PATH")').VersionInfo.ProductVersion" 2>/dev/null \
        | tr -d '\r' || true ;;
    *) true ;;
  esac
}
VER="$(resolve_version)"

# ---- edition: Studio only --------------------------------------------------
# Blackmagic's MCP ships only in Studio, and 21.1 moved scripting out of the free edition, so the free edition has
# no route at all (on Windows its scriptapp("Resolve") HANGS rather than refusing: a client sat on a first call for
# Claude Code's 30-minute idle timeout, 2026-09-07). Signals: the Studio activation files (.license/
# .davinciresolvestudio_*, every OS), the App Store "DaVinci Resolve Studio.app" bundle, and on Windows the uninstall
# registry DisplayName and Resolve's own log. An activated Studio detected as free re-runs with --studio.
detect_edition() {
  local lic_dir names
  case "$OS" in
    Darwin)
      [[ -d "/Applications/DaVinci Resolve Studio.app" ]] && { echo studio; return; }
      lic_dir="/Library/Application Support/Blackmagic Design/DaVinci Resolve/.license" ;;
    Linux)
      lic_dir="/opt/resolve/.license" ;;
    *)
      lic_dir="$SYSDRV/ProgramData/Blackmagic Design/DaVinci Resolve/.license"
      names="$(powershell.exe -NoProfile -NonInteractive -Command "Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*' -ErrorAction SilentlyContinue | Where-Object { \$_.DisplayName -like 'DaVinci Resolve*' } | ForEach-Object { \$_.DisplayName }" 2>/dev/null | tr -d '\r' | sed 's/[[:space:]]*$//' || true)"
      if printf '%s\n' "$names" | grep -qx 'DaVinci Resolve Studio'; then echo studio; return; fi
      # Studio 21 on Windows registers as plain "DaVinci Resolve" and writes no .license folder (2026-09-27: an
      # activated Studio was read as free). Resolve's OWN log names the running edition on every start
      # ("Running DaVinci Resolve Studio v21.0.4..." vs "Running DaVinci Resolve v..."): once it has run, it decides.
      local rlog="${APPDATA:-$HOME/AppData/Roaming}/Blackmagic Design/DaVinci Resolve/Support/logs/davinci_resolve.log"
      if [[ -f "$rlog" ]]; then
        local ran; ran="$(grep -a 'Running DaVinci Resolve' "$rlog" 2>/dev/null | tail -1)"
        case "$ran" in
          *"Running DaVinci Resolve Studio"*) echo studio; return ;;
          *"Running DaVinci Resolve v"*)      echo free; return ;;
        esac
      fi
      if printf '%s\n' "$names" | grep -qx 'DaVinci Resolve'; then echo free; return; fi ;;
  esac
  if compgen -G "$lic_dir/.davinciresolvestudio*" >/dev/null 2>&1; then echo studio; else echo free; fi
}
if [[ "$FORCE_STUDIO" -eq 1 ]]; then
  say "[edition] studio (forced by --studio)"
elif [[ "$(detect_edition)" == free ]]; then
  fail "this is the FREE edition of DaVinci Resolve${VER:+ ($VER)}. The Resolve lane runs on Blackmagic's own MCP server, which ships only in DaVinci Resolve Studio 21.1 and newer (21.1 also took scripting out of the free edition, so nothing can drive it). Upgrade to Studio and re-run ./setup-resolve.sh, or finish in another app: ./setup.sh --lane capcut, or ./setup.sh --lane chat-only. An activated Studio read wrongly as free: ./setup-resolve.sh --studio. Nothing was changed."
else
  say "[edition] studio detected"
fi

# ---- version: 21.1 or newer ------------------------------------------------
# ResolveMCP ships inside the app from 21.1 on: no binary = an older Resolve.
[[ -f "$MCP_BIN" ]] \
  || fail "DaVinci Resolve Studio${VER:+ $VER} is older than 21.1: Blackmagic's MCP server ships with Studio 21.1 and newer. Update Resolve first (DaVinci Resolve > Check for Updates, or blackmagicdesign.com/support), then re-run ./setup-resolve.sh. Nothing was changed."

# python on Windows is `python` (python3 there is a fake Store stub): probe by RUNNING it.
PY=python3; "$PY" -c '' 2>/dev/null || PY=python
"$PY" -c '' 2>/dev/null || fail "python is required. Install it (see SETUP.md) and re-run."

# The server's own self-test: an MCP initialize + tools/list over stdio, answered with Resolve closed. It proves the
# binary runs here and reports the version it serves.
MCP_RUN="$MCP_BIN"; [[ "$IS_WINDOWS" -eq 1 ]] && MCP_RUN="$(cygpath -w "$MCP_BIN")"
MCP_VER="$("$PY" - "$MCP_RUN" <<'PY'
import json, subprocess, sys
try:
    run = subprocess.run([sys.argv[1], "--test"], capture_output=True, text=True, timeout=60)
except (OSError, subprocess.TimeoutExpired) as exc:
    print("self-test failed: %s" % exc, file=sys.stderr)
    sys.exit(1)
out = run.stdout + run.stderr
for line in run.stdout.splitlines():
    if line.startswith("Server:") and '"serverInfo"' in line:
        version = json.loads(line[len("Server:"):])["result"]["serverInfo"].get("version", "")
        parts = []
        for p in version.split(".")[:2]:
            parts.append(int(p) if p.isdigit() else 0)
        if tuple(parts) < (21, 1):
            print("ResolveMCP serves %s, older than 21.1" % version, file=sys.stderr)
            sys.exit(2)
        print(version)
        sys.exit(0)
print(out[-2000:], file=sys.stderr)
sys.exit(1)
PY
)" || fail "Blackmagic's ResolveMCP ($MCP_BIN) did not pass its self-test (output above). Update DaVinci Resolve Studio to the newest 21.x, then re-run ./setup-resolve.sh. Nothing was changed."
say "[server] Blackmagic's ResolveMCP $MCP_VER passed its self-test ($MCP_BIN)"

# ---- .mcp.json: merge the davinci-resolve entry in place -------------------
# On Windows the path is written in C:/ form: Claude Code launches the server natively, not through Git Bash.
J_MCP="$MCP_BIN"; [[ "$IS_WINDOWS" -eq 1 ]] && J_MCP="$(cygpath -m "$MCP_BIN")"
MCP_JSON="$ROOT/.mcp.json"
"$PY" - "$MCP_JSON" "$J_MCP" <<'PY'
import json, os, sys
path, command = sys.argv[1:3]
cfg = {"mcpServers": {}}
if os.path.exists(path):
    with open(path, encoding="utf-8-sig") as fh:
        cfg = json.load(fh)
was = cfg.setdefault("mcpServers", {}).get("davinci-resolve", {}).get("command", "")
cfg["mcpServers"]["davinci-resolve"] = {
    "command": command,
    "args": [],
    # Per-call wall-clock cap in ms (Claude Code >= 2.1.203; older builds ignore it). The default is ~28 h with a
    # 30-minute idle abort; ten minutes ends a hang inside the same session.
    "timeout": 600000,
}
with open(path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")
if was and "ResolveMCP" not in was:
    print("[config] davinci-resolve: the retired community engine replaced by Blackmagic's ResolveMCP")
else:
    print("[config] davinci-resolve -> Blackmagic's ResolveMCP in .mcp.json (other servers untouched)")
PY

# The retired community engine's clone (and its venv) is dead weight once the entry above points elsewhere.
if [[ -d "$ROOT/vendor/davinci-resolve-mcp" ]]; then
  rm -rf "$ROOT/vendor/davinci-resolve-mcp"
  say "[cleanup] removed vendor/davinci-resolve-mcp (the retired community engine)"
fi

# Record the lane for setup.sh / the SessionStart hook (only once the tools marker exists;
# this script can also run standalone before ./setup.sh, and then setup.sh records it).
[[ -f "$ROOT/.setup-complete" ]] && printf 'lane=resolve\n' > "$ROOT/.setup-complete"

# ---- done ------------------------------------------------------------------
say ""
say "Setup complete (DaVinci Resolve Studio${VER:+ $VER}, Blackmagic's MCP). One step left:"
say "  Restart Claude Code (quit it fully, reopen this project) so it loads the new"
say "  davinci-resolve MCP; answer YES when it asks to enable this project's .mcp.json"
say "  servers (a no is remembered: 'claude mcp reset-project-choices' clears it), then"
say "  say \"continue setup\"."
say "Verify after the restart: ask Claude to \"get the Resolve version\"; Resolve must"
say "be running (Claude can launch it)."
say "Troubleshooting (only if that fails): check Resolve Preferences > System > General >"
say "External scripting = Local. That IS the shipped default, so don't change it up front."
