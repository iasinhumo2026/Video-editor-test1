#!/usr/bin/env bash
# setup-premiere.sh: one-command setup for the OPTIONAL Premiere Pro finishing lane.
# Installs the Premiere MCP engine (pinned build), the MCP Bridge panel, and
# wires .mcp.json. Safe to re-run; it verifies each piece and skips what's done.
#
#   macOS:            fully supported.
#   Windows (native): supported — run from Git Bash (the shell Claude Code uses
#                     on Windows). Panel installs under %APPDATA%, CEP debug
#                     mode via the registry, bridge folder under %TEMP%.
#   Linux:            no Premiere exists; use the default chat-only pipeline.
#
# After it finishes: restart Premiere (the panel is patched to start the bridge
# itself; nothing to click), then restart Claude Code once so it picks up
# .mcp.json (answer YES when it asks to enable this project's MCP servers).
# Verify with: node lanes/premiere/premiere-bridge.mjs ping. Only if the
# autostart patch reported that it did not apply: Window > Extensions >
# MCP Bridge (CEP) > Start Bridge, by hand, each session.
set -euo pipefail
# Resolve the PROJECT root. In the shipped package this script sits at the root;
# in the source repo it lives under packaging/overlay/. The marker file decides.
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HERE/lanes/premiere/premiere-bridge.mjs" ]]; then
  ROOT="$HERE"
elif [[ -f "$HERE/../../lanes/premiere/premiere-bridge.mjs" ]]; then
  ROOT="$(cd "$HERE/../.." && pwd)"
else
  printf 'ERROR: cannot locate the project root (lanes/premiere/premiere-bridge.mjs not found)\n' >&2
  exit 1
fi
cd "$ROOT"

REPO_URL="https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP.git"
PIN="12684e37297a702265985dffa7d33629d28074f4"   # v1.2.3, verified 2026-08-28 on Premiere 26.3.2 (was cc57eb4, 2026-07-18)
VENDOR="$ROOT/vendor/premiere-mcp"

say()  { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
# Windows stops a path at 259 characters and this lane installs files up to 145 characters deep inside the project
# folder: a folder deeper than 100 characters is refused before anything installs (setup.sh's rule; a 155-character
# folder broke the vendor clone with "Filename too long", the Windows re-test, 2026-09-27).
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*)
  _w="$(cygpath -w "$ROOT" 2>/dev/null || printf '%s' "$ROOT")"
  [[ "${#_w}" -le 100 ]] || fail "this folder's path is ${#_w} characters long ($_w): Windows stops a path at 259 characters and this lane installs files up to 145 characters deep inside it. Move the whole folder to a path of at most 100 characters (e.g. C:\\Users\\<you>\\video-editor), open it there and run this again. Nothing was installed." ;;
esac

# ---- OS detection ----------------------------------------------------------
OS="$(uname -s)"
IS_WINDOWS=0
case "$OS" in MINGW*|MSYS*) IS_WINDOWS=1 ;; esac
if [[ "$OS" == "Linux" ]] && grep -qi microsoft /proc/version 2>/dev/null; then
  fail "WSL is not a supported path anymore — run this natively on Windows from Git Bash (see SETUP.md \"Windows\")."
elif [[ "$OS" == "Linux" ]]; then
  fail "Premiere Pro does not run on Linux. Use the default chat-only pipeline instead."
elif [[ "$OS" != "Darwin" && "$IS_WINDOWS" -eq 0 ]]; then
  fail "unsupported OS: $OS (on Windows, run this from Git Bash — see SETUP.md)"
fi

# ---- prerequisites ---------------------------------------------------------
command -v git  >/dev/null 2>&1 || fail "git is required. Install it and re-run."
command -v node >/dev/null 2>&1 || fail "Node.js 18+ is required. Install it (see SETUP.md) and re-run."
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
[[ "$NODE_MAJOR" -ge 18 ]] || fail "Node.js 18+ required, found $(node -v)."

# ---- engine: clone at the pin + build --------------------------------------
# A clone that was interrupted leaves a .git with no commit in it: every re-run then skipped the clone (the .git
# exists) and died on `git rev-parse HEAD` (found in setup-resolve.sh on the Windows re-test, 2026-09-27; the same
# code). A vendor folder whose HEAD does not resolve is removed and cloned again. --git-dir, never -C: vendor/ sits
# inside the project's own repo, so -C on a folder with no .git of its own would read the PROJECT's HEAD and pass.
if [[ -e "$VENDOR" ]] && ! git --git-dir="$VENDOR/.git" rev-parse --verify --quiet 'HEAD^{commit}' >/dev/null 2>&1; then
  say "[engine] vendor/premiere-mcp is an unfinished clone: removing it and cloning again..."
  rm -rf "$VENDOR"
fi
if [[ ! -d "$VENDOR" ]]; then
  say "[engine] cloning premiere-mcp..."
  # LF on every OS: Git for Windows' global core.autocrlf=true checked the engine out CRLF (the Windows test PC,
  # 2026-10-13). `clone -c` keeps the setting in the clone, so a later pin checkout stays LF too.
  git clone -c core.autocrlf=false "$REPO_URL" "$VENDOR"
fi
HEAD="$(git -C "$VENDOR" rev-parse HEAD)"
CHECKED_OUT=0
if [[ "$HEAD" != "$PIN" ]]; then
  say "[engine] checking out pinned build ${PIN:0:7}..."
  git -C "$VENDOR" fetch --quiet origin
  # -f: the autostart patch below edits cep-plugin/ in place, so a re-run after a PIN bump
  # meets a dirty tree and a plain checkout aborts under set -e. Discarding is safe — the
  # patch step re-applies idempotently a few lines down.
  git -C "$VENDOR" -c advice.detachedHead=false checkout --quiet -f "$PIN"
  CHECKED_OUT=1
fi
# A build is only as current as the source it was built from: after a PIN bump the old dist/ would
# otherwise keep running. vendor/premiere-mcp/.built-from (untracked, so checkout -f keeps it) names that pin.
if [[ "$CHECKED_OUT" -eq 1 || ! -f "$VENDOR/dist/index.js" || ! -d "$VENDOR/node_modules" \
      || "$(cat "$VENDOR/.built-from" 2>/dev/null)" != "$PIN" ]]; then
  say "[engine] installing dependencies + building (one time, a minute or two)..."
  (cd "$VENDOR" && npm install --no-fund --no-audit && npm run build)
  printf '%s\n' "$PIN" > "$VENDOR/.built-from"
fi
[[ -f "$VENDOR/dist/index.js" ]] || fail "engine build did not produce dist/index.js"
say "[engine] ready at vendor/premiere-mcp (pinned ${PIN:0:7})"

# ---- autostart patch: the panel must start ITSELF ---------------------------
# Stock, the panel needs a human to open Window > Extensions > MCP Bridge (CEP) and click
# "Start Bridge" before any scripted work can run — every session. Two content edits remove
# that (a <StartOn> in the manifest, a start shim in bridge-cep.js). Patch the CLONE, before
# it is copied into the CEP extensions dir, so the vendor copy and the installed panel agree.
# Idempotent, so a re-run or an engine bump is safe. Verified byte-identical to the reference
# panel that this repo has been driving.
PY=python3; "$PY" -c '' 2>/dev/null || PY=python
AUTOSTART_OK=0
if "$PY" "$ROOT/lanes/premiere/premiere-templates/apply-autostart-patch.py" "$VENDOR/cep-plugin"; then
  AUTOSTART_OK=1
  say "[panel] autostart patch applied — no need to click Start Bridge"
else
  say "  ⚠ autostart patch did not apply; the bridge will need Window > Extensions >"
  say "    MCP Bridge (CEP) > Start Bridge by hand each session."
fi

# ---- materialise the LUT library at the path baked into the captured params ----
# ☠️ Premiere RE-RESOLVES a LUT on save: a project written with an embedded cube comes back from
# the next Premiere save as a LINK to the path baked in the params, with the embedded copy
# dropped (measured 2026-09-02 on a real project). On the capture machine that path exists, so
# nothing breaks and the swap is invisible. Elsewhere it is a dangling reference the moment the
# user saves. The params are hash-sealed, so the path cannot be rewritten — the fix is to make
# the path TRUE on this machine. /Users/Shared has no username in it and exists on every Mac,
# which is exactly why captures are taken from there.
if [[ "$OS" == "Darwin" && -d "$ROOT/assets/luts" ]]; then
  SHARED_LUTS="/Users/Shared/video-editor-luts"
  if mkdir -p "$SHARED_LUTS" 2>/dev/null; then
    # compare-then-copy, never cp -n: a cube updated in a new version must replace the old mirror
    find "$ROOT/assets/luts" -name '*.cube' -print0 2>/dev/null | while IFS= read -r -d '' src; do
      dst="$SHARED_LUTS/$(basename "$src")"; cmp -s "$src" "$dst" || cp "$src" "$dst"
    done || true
    say "[luts] library mirrored to $SHARED_LUTS (the path the captured looks reference)"
  else
    say "  ⚠ could not write $SHARED_LUTS — the shipped look still applies, but if Premiere"
    say "    re-saves the project it may drop the embedded cube and leave a dangling link."
  fi
elif [[ "$IS_WINDOWS" -eq 1 && -d "$ROOT/assets/luts" ]]; then
  # Windows resolves a rooted forward-slash path against the current drive, so the baked
  # /Users/Shared/video-editor-luts/<cube> becomes C:\Users\Shared\video-editor-luts\<cube>
  # once that folder exists. Same intent as the Mac branch; UNVALIDATED on a real Windows box.
  SHARED_LUTS="$(cygpath -u "${SYSTEMDRIVE:-C:}")/Users/Shared/video-editor-luts"
  if mkdir -p "$SHARED_LUTS" 2>/dev/null; then
    # compare-then-copy, never cp -n: a cube updated in a new version must replace the old mirror
    find "$ROOT/assets/luts" -name '*.cube' -print0 2>/dev/null | while IFS= read -r -d '' src; do
      dst="$SHARED_LUTS/$(basename "$src")"; cmp -s "$src" "$dst" || cp "$src" "$dst"
    done || true
    say "[luts] library mirrored to $(cygpath -m "$SHARED_LUTS") (the path the captured looks reference; unvalidated on Windows)"
  else
    say "  ⚠ could not write $SHARED_LUTS — the shipped look still applies, but if Premiere"
    say "    re-saves the project it may drop the embedded cube and leave a dangling link."
  fi
fi

# ---- panel install + bridge temp dir (per OS) ------------------------------
if [[ "$OS" == "Darwin" ]]; then
  EXT_DIR="$HOME/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP"
  mkdir -p "$(dirname "$EXT_DIR")"
  rm -rf "$EXT_DIR"
  cp -R "$VENDOR/cep-plugin" "$EXT_DIR"
  say "[panel] installed to CEP extensions"
  for v in 10 11 12; do defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1; done
  say "[panel] CEP debug mode enabled"
  BRIDGE_DIR_SERVER="/tmp/premiere-mcp-bridge"
  TIMEOUT_MS=60000
  mkdir -p "$BRIDGE_DIR_SERVER"
else
  # Native Windows (Git Bash): panel under %APPDATA%, CEP debug mode via the
  # registry, bridge folder = the panel's Windows default %TEMP%\premiere-mcp-bridge.
  [[ -n "${APPDATA:-}" ]] || fail "APPDATA is not set — run this from Git Bash on Windows."
  [[ -n "${LOCALAPPDATA:-}" ]] || fail "LOCALAPPDATA is not set — run this from Git Bash on Windows."
  EXT_DIR="$(cygpath -u "$APPDATA")/Adobe/CEP/extensions/MCPBridgeCEP"
  mkdir -p "$(dirname "$EXT_DIR")"
  rm -rf "$EXT_DIR"
  cp -R "$VENDOR/cep-plugin" "$EXT_DIR"
  say "[panel] installed to CEP extensions (%APPDATA%\\Adobe\\CEP\\extensions)"
  # MSYS_NO_PATHCONV: stop Git Bash rewriting /v /t /d /f into filesystem paths.
  for v in 10 11 12; do
    MSYS_NO_PATHCONV=1 reg.exe add "HKCU\\Software\\Adobe\\CSXS.$v" /v PlayerDebugMode /t REG_SZ /d 1 /f >/dev/null
  done
  say "[panel] CEP debug mode enabled (registry)"
  # .mcp.json needs the WINDOWS spelling of the bridge dir — Claude Code spawns the
  # node server natively, not through Git Bash. %TEMP% defaults to %LOCALAPPDATA%\Temp.
  BRIDGE_DIR_SERVER="$(cygpath -m "$LOCALAPPDATA")/Temp/premiere-mcp-bridge"
  TIMEOUT_MS=60000
  mkdir -p "$(cygpath -u "$BRIDGE_DIR_SERVER")"
  say "[bridge] folder: $BRIDGE_DIR_SERVER"
fi

# Engine path for .mcp.json — Windows spelling on Windows (see above).
ENGINE_JS="$VENDOR/dist/index.js"
[[ "$IS_WINDOWS" -eq 1 ]] && ENGINE_JS="$(cygpath -m "$ENGINE_JS")"

# ---- .mcp.json: merge the premiere-pro entry in place ----------------------
# A JSON merge (via node, already a hard prereq above), NOT an overwrite and NOT
# a skip: the old "already exists, leaving it alone" behavior silently dropped
# the premiere-pro entry when another lane (e.g. setup-resolve.sh) had created
# .mcp.json first. Other servers are left untouched.
MCP_JSON="$ROOT/.mcp.json"
node -e '
const fs = require("fs");
const [path, engine, bridgeDir, timeoutMs] = process.argv.slice(1);
let cfg = { mcpServers: {} };
if (fs.existsSync(path)) cfg = JSON.parse(fs.readFileSync(path, "utf8"));
cfg.mcpServers = cfg.mcpServers || {};
cfg.mcpServers["premiere-pro"] = {
  command: "node",
  args: [engine],
  // PREMIERE_MCP_TELEMETRY=0: the engine (v1.2.x) phones home tool-call telemetry
  // unless told not to. Off for every install; nothing here needs it.
  env: { PREMIERE_TEMP_DIR: bridgeDir, PREMIERE_TIMEOUT_MS: String(timeoutMs), PREMIERE_MCP_TELEMETRY: "0" }
};
fs.writeFileSync(path, JSON.stringify(cfg, null, 2) + "\n");
console.log("[config] premiere-pro entry written to .mcp.json (other servers untouched)");
// The engine also reads ~/.premiere-mcp-bridge/config.json; keep telemetry off there
// too (merge, never clobber a file the user already has).
const os = require("os"), p = require("path");
const cdir = p.join(os.homedir(), ".premiere-mcp-bridge"), cfile = p.join(cdir, "config.json");
let c = {};
try { c = JSON.parse(fs.readFileSync(cfile, "utf8")); } catch (e) {}
c.tempDirectory = c.tempDirectory || bridgeDir;
c.telemetry = false;
fs.mkdirSync(cdir, { recursive: true });
fs.writeFileSync(cfile, JSON.stringify(c, null, 2) + "\n");
console.log("[config] telemetry off in " + cfile);
' "$MCP_JSON" "$ENGINE_JS" "$BRIDGE_DIR_SERVER" "$TIMEOUT_MS"

# Record the lane for setup.sh / the SessionStart hook (only once the tools marker exists;
# this script can also run standalone before ./setup.sh, and then setup.sh records it).
[[ -f "$ROOT/.setup-complete" ]] && printf 'lane=premiere\n' > "$ROOT/.setup-complete"

# ---- done ------------------------------------------------------------------
say ""
if [[ "$AUTOSTART_OK" -eq 1 ]]; then
  say "Setup complete. Finish with these two steps:"
  say "  1. Restart Premiere Pro (the panel is discovered at launch, and starts the bridge itself)."
  say "  2. Restart Claude Code (quit it fully, then reopen this project folder) so it"
  say "     loads the new premiere-pro MCP; answer YES when it asks to enable this project's"
  say "     .mcp.json servers (a no is remembered: 'claude mcp reset-project-choices' clears"
  say "     it), then say \"continue setup\"."
else
  say "Setup complete. Finish with these three steps:"
  say "  1. Restart Premiere Pro (the panel is discovered at launch)."
  say "  2. In Premiere: Window > Extensions > MCP Bridge (CEP) > Start Bridge."
  say "     (the autostart patch did not apply, so this one is manual each session)"
  say "  3. Restart Claude Code (quit it fully, then reopen this project folder) so it"
  say "     loads the new premiere-pro MCP; answer YES when it asks to enable this project's"
  say "     .mcp.json servers (a no is remembered: 'claude mcp reset-project-choices' clears"
  say "     it), then say \"continue setup\"."
fi
say "Verify after the restart:  node lanes/premiere/premiere-bridge.mjs ping"
say "(./lanes/premiere/premiere-up.sh launches or relaunches Premiere and waits for that ping, on macOS and Windows.)"
if [[ "$IS_WINDOWS" -eq 1 ]]; then
  say ""
  say "Windows note:"
  say "  - If the panel shows a different Temp Directory than $BRIDGE_DIR_SERVER,"
  say "    set it to match and click Start Bridge again."
fi
