#!/usr/bin/env bash
# setup-finalcut.sh: one-command setup for the Final Cut Pro lane (macOS only). ./setup.sh runs it when Final Cut is
# the pick (./setup.sh --lane finalcut); it can also run on its own. Safe to re-run: it checks each piece and skips
# what is done.
#
# Final Cut has no scripting surface that can edit a timeline, so this lane runs a PATCHED COPY of it: SpliceKit
# (MIT, github.com/elliotttate/SpliceKit) copies Final Cut to ~/Applications/SpliceKit/, loads a bridge into the copy
# and re-signs it; the App Store app is never touched and libraries stay compatible with it. The lane then builds
# every timeline as FCPXML through Final Cut's own importer (lanes/finalcut/README.md).
#
#   1. SpliceKit.app in /Applications: the pinned release, downloaded and checked against its SHA-256
#   2. the patched copy: SpliceKit's patcher is an app, so the USER clicks Continue in it ONCE (exit 4 until then),
#      and again after every Final Cut update (the copy is a copy). lanes/finalcut/doctor.py decides which App Store
#      Final Cut the lane drives and which ONE copy is its own; any other copy goes to the Trash (lab-notes § 21)
#   3. the house look as Final Cut's Custom LUT: the folded cube in ~/Library/Application Support/ProApps/Custom LUTs
#   4. the splicekit MCP: a venv in vendor/splicekit-mcp and its entry in .mcp.json
#
# Exit: 0 wired · 1 failed (the message says why) · 4 waiting on the user's one click in SpliceKit, then re-run.
set -euo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

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

SK_VERSION="3.3.9"   # the release the lane was proven on (2026-09-25); bump deliberately, with a lane re-test
SK_SHA256="d6e25b8182bb4367deb56400c154b9f07792f983f53e20d36292d159e7fc9750"
SK_URL="https://github.com/elliotttate/SpliceKit/releases/download/v$SK_VERSION/SpliceKit-v$SK_VERSION.dmg"
SK_APP="/Applications/SpliceKit.app"
LUT_NAME="house-Autumn-Rec709-80-120.cube"   # lanes/finalcut/templates/house-lut-filter.xml names the cube by THIS name
LUT_DIR="$HOME/Library/Application Support/ProApps/Custom LUTs"
VENV="$ROOT/vendor/splicekit-mcp"

say()  { printf '%s\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
version_of() { /usr/bin/defaults read "$1/Contents/Info" CFBundleShortVersionString 2>/dev/null || true; }
ver_lt() {  # 0 when dotted version $1 is older than $2
  [[ "$1" != "$2" ]] && [[ "$(printf '%s\n%s\n' "$1" "$2" | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | head -n 1)" == "$1" ]]
}

[[ "$(uname -s)" == Darwin ]] || fail "Final Cut Pro runs on macOS only."
[[ -d "$ROOT/lanes/finalcut" ]] || fail "this package does not include the Final Cut lane (lanes/finalcut/)."
have uv || fail "uv is missing: run ./setup.sh first (it installs the core tools)."

# ---- Final Cut itself -------------------------------------------------------
# Which one, when two are installed, is doctor.py's call in step 2 (never a glob's first match: lab-notes § 21).
DOCTOR="$ROOT/lanes/finalcut/doctor.py"
compgen -G "/Applications/Final Cut Pro*.app" >/dev/null 2>&1 || fail "Final Cut Pro is not installed in /Applications. Install it from the App Store (the one-time purchase or Apple Creator Studio), open it once, then re-run ./setup.sh --lane finalcut."
# doctor.py's exit 1 = no App Store Final Cut it can drive (11.x cannot import the FCPXML 1.14 the lane writes): said
# before SpliceKit is downloaded for nothing
rc=0; FC_SAID="$(uv run "$DOCTOR" 2>&1)" || rc=$?
[[ "$rc" -ne 1 ]] || fail "$(printf '%s\n' "$FC_SAID" | tail -n 1 | sed 's/^✗ //')"

# ---- 1. SpliceKit -----------------------------------------------------------
# An installed SpliceKit OLDER than the lane's pin is updated (then the copy is patched again with it); a newer one
# is left alone, never downgraded.
SK_UPDATED=0
SK_HAVE=""; [[ -d "$SK_APP" ]] && SK_HAVE="$(version_of "$SK_APP")"
if [[ -d "$SK_APP" ]] && ! { [[ -n "$SK_HAVE" ]] && ver_lt "$SK_HAVE" "$SK_VERSION"; }; then
  say "[splicekit] present: $SK_APP $SK_HAVE"
else
  [[ -d "$SK_APP" ]] && { say "[splicekit] $SK_HAVE is older than the lane's $SK_VERSION: updating it"; SK_UPDATED=1; }
  say "[splicekit] downloading SpliceKit $SK_VERSION (about 22 MB) from its GitHub release..."
  TMP="$(mktemp -d)"
  trap 'hdiutil detach "$TMP/mnt" -quiet >/dev/null 2>&1 || true; rm -rf "$TMP"' EXIT
  curl -fL --retry 3 -o "$TMP/sk.dmg" "$SK_URL" || fail "could not download $SK_URL"
  got="$(shasum -a 256 "$TMP/sk.dmg" | cut -d' ' -f1)"
  [[ "$got" == "$SK_SHA256" ]] || fail "the SpliceKit download does not match its published SHA-256 ($got): not installing it."
  hdiutil attach "$TMP/sk.dmg" -nobrowse -readonly -mountpoint "$TMP/mnt" -quiet || fail "could not open the SpliceKit disk image"
  [[ -d "$TMP/mnt/SpliceKit.app" ]] || fail "no SpliceKit.app inside the disk image"
  if [[ "$SK_UPDATED" -eq 1 ]]; then
    osascript -e 'tell application "SpliceKit" to quit' >/dev/null 2>&1 || true
    rm -rf "$SK_APP" 2>/dev/null || fail "could not remove the old $SK_APP to update it (an administrator account can)"
  fi
  ditto "$TMP/mnt/SpliceKit.app" "$SK_APP" 2>/dev/null \
    || fail "could not copy SpliceKit.app into /Applications (an administrator account can; or drag it there from $SK_URL)"
  hdiutil detach "$TMP/mnt" -quiet || true
  say "[splicekit] installed: $SK_APP"
fi

# ---- 2. the patched copy (the user's one click) ------------------------------
# doctor.py: no copy at the App Store app's version and build (never patched, or Final Cut updated), or SpliceKit just
# updated → it quits Final Cut itself, opens SpliceKit and prints the one click to relay (exit 4). Otherwise every
# copy but the lane's goes to the Trash, so nothing can launch or attach to the wrong one.
rc=0
if [[ "$SK_UPDATED" -eq 1 ]]; then
  say "[splicekit] SpliceKit was updated to $SK_VERSION: the copy needs patching again with it"
  uv run "$DOCTOR" --patch || rc=$?
else
  uv run "$DOCTOR" --repair --no-launch || rc=$?
fi
[[ "$rc" -eq 4 ]] && exit 4
[[ "$rc" -eq 0 ]] || fail "lanes/finalcut/doctor.py could not settle the patched copy (its lines above say why)"

# ---- 3. the house look as a Custom LUT --------------------------------------
if [[ -f "$LUT_DIR/$LUT_NAME" ]]; then
  say "[lut] present: $LUT_DIR/$LUT_NAME"
else
  FOLD="$ROOT/workflows/fold-look.py"
  LOOK="$ROOT/assets/luts/rec709/Autumn-Rec709.cube"
  [[ -f "$FOLD" && -f "$LOOK" ]] || fail "the house look needs $FOLD and $LOOK"
  mkdir -p "$LUT_DIR"
  uv run "$FOLD" assets/luts/rec709/Autumn-Rec709.cube "$LUT_DIR/$LUT_NAME" --intensity 0.80 --saturation 1.20 >/dev/null \
    || fail "could not build the house look cube"
  say "[lut] the house look folded into $LUT_DIR/$LUT_NAME (Final Cut's Custom LUT reads it by name)"
fi

# ---- 4. the splicekit MCP ---------------------------------------------------
SERVER="$SK_APP/Contents/Resources/mcp/server.py"
[[ -f "$SERVER" ]] || fail "SpliceKit's MCP server is missing ($SERVER): reinstall SpliceKit"
if [[ -x "$VENV/bin/python" ]] && "$VENV/bin/python" -c 'import mcp' 2>/dev/null; then
  say "[mcp] venv present: $VENV"
else
  # --clear: a venv a failed install left behind (no mcp in it) is rebuilt; uv 0.10+ refuses a bare `uv venv` onto it
  uv venv --clear --python 3.12 "$VENV" >/dev/null 2>&1 || fail "could not create $VENV (run: uv venv --clear --python 3.12 $VENV)"
  uv pip install --python "$VENV/bin/python" --exclude-newer "14 days" "mcp>=1.27,<2" >/dev/null 2>&1 \
    || fail "could not install the MCP library into $VENV (run: uv pip install --python $VENV/bin/python --exclude-newer '14 days' 'mcp>=1.27,<2')"
  say "[mcp] venv built: $VENV"
fi
uv run python - "$ROOT/.mcp.json" "$VENV/bin/python" "$SERVER" <<'PY'
import json, os, sys
path, py, server = sys.argv[1:4]
cfg = {"mcpServers": {}}
if os.path.exists(path):
    with open(path) as fh:
        cfg = json.load(fh)
cfg.setdefault("mcpServers", {})["splicekit"] = {"command": py, "args": [server]}
with open(path, "w") as fh:
    json.dump(cfg, fh, indent=2)
    fh.write("\n")
print("[config] splicekit entry written to .mcp.json (other servers untouched)")
PY

[[ -f "$ROOT/.setup-complete" ]] && printf 'lane=finalcut\n' > "$ROOT/.setup-complete"

say ""
say "Final Cut lane wired. Start Final Cut with:  uv run lanes/finalcut/doctor.py --repair"
say "(it quits a Final Cut that is not the lane's copy, launches the copy by its path and proves the bridge; never"
say "start Final Cut from the Dock, by name or by bundle id: that is the App Store app, which has no bridge)"
exit 0
