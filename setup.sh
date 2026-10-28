#!/usr/bin/env bash
# setup.sh — ONE-COMMAND auto-setup. Detects your OS (macOS, Windows or Linux), installs
# everything the pipeline needs, bootstraps the render engine, verifies with
# check-setup.sh, then auto-detects your editing app (Premiere / Resolve / CapCut)
# and wires its lane. Safe to re-run any time: it skips what's already done and
# picks up where it left off (e.g. after a restart that refreshed PATH).
#
#   ./setup.sh
#   ./setup.sh --lane premiere|resolve|capcut|finalcut|chat-only
#       records the user's editing-app pick (asked only when several apps are
#       installed) and, for premiere/resolve/finalcut, runs that lane's installer.
#       Final Cut is macOS only, CapCut macOS and Windows; Linux: resolve or chat-only.
#   ./setup.sh --new-install
#       this folder is a second, separate install (not a new version of one already set up)
#
# macOS:   installs via Homebrew (if Homebrew itself is missing, you run its one-liner
#          once (it needs your password), then re-run this; it finds the new Homebrew in
#          /opt/homebrew or /usr/local on its own and adds it to your shell profile).
# Windows: run from Git Bash (the shell Claude Code uses on Windows); installs via
#          winget. Newly installed tools sometimes need a new terminal before they're
#          on PATH; this script pulls in their well-known install dirs so most setups
#          finish in ONE run; if anything is still pending it says exactly what to do.
# Linux:   tools are not auto-installed (./check-setup.sh prints the apt command
#          for each missing one), but everything else runs: verify, render-engine
#          bootstrap, Resolve lane detection (/opt/resolve), the done marker.
#
# Exit codes (Claude reads these; each prints exactly what to do):
#   0  done (output may carry an ACTION FOR CLAUDE line: the which-app question)
#   1  something needs fixing before continuing; the output says what (Homebrew
#      missing on macOS, brew/apt installs that did not land, a lane installer that failed)
#   2  restart needed: freshly installed tools (or Homebrew's PATH) aren't visible to
#      this session yet. Restart Claude Code, then re-run ./setup.sh; it finishes the rest.
#   3  an editing-app MCP lane was just wired into .mcp.json. Restart Claude Code
#      so it loads the new MCP (answer YES when it asks to enable this project's
#      .mcp.json servers), then verify the lane.
#
# State: .setup-complete (written once every core tool verifies and the self-test passes) carries
#   lane=<premiere|resolve|capcut|finalcut|chat-only|pending>
# so a later session knows which finish surface this machine uses. "pending" means the
# which-app question is still open; the SessionStart hook keeps reminding Claude until
# ./setup.sh --lane <pick> records the answer. Below it, the toolchain the self-test passed on
# (ffmpeg=, uv=, node=, python=, platform=, selftest=<VERSION>): support reads it, and the hook asks
# for ./setup.sh again when one of those versions changes (a `brew upgrade` after setup).
#
# Supported: macOS on Apple Silicon, macOS 15 or newer (anything else stops before installing;
# VE_UNSUPPORTED_PLATFORM=1 tries anyway), Windows 10/11 through Git Bash, Linux.
#
# This handles tools + the editing-app lane. Personalization (brand-kit.md) is
# OPTIONAL and separate: the editor works out of the box with the neutral bundled
# look; fill the brand kit in whenever (or never).
set -uo pipefail

# Resolve the PROJECT root. In the shipped package this script sits at the root;
# in the source repo it lives under packaging/overlay/. The marker file decides.
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/check-setup.sh" ]; then
  ROOT="$HERE"
elif [ -f "$HERE/../../check-setup.sh" ]; then
  ROOT="$(cd "$HERE/../.." && pwd)"
else
  printf 'ERROR: cannot locate the project root (check-setup.sh not found)\n' >&2
  exit 1
fi
# The folder Claude Code has open. When it is not ROOT (Windows' Extract All nests the package one level
# deeper, and a client opens the outer folder), setup still runs, but CLAUDE.md, the hooks and the skills
# only load in ROOT: the end of this script says so instead of claiming it is done.
CALLER_P="$(pwd -P)"
cd "$ROOT"
ROOT_P="$(pwd -P)"
WRONG_FOLDER=0
case "$CALLER_P/" in "$ROOT_P"/*) ;; *) WRONG_FOLDER=1 ;; esac
ROOT_SHOW="$ROOT"
command -v cygpath >/dev/null 2>&1 && ROOT_SHOW="$(cygpath -w "$ROOT")"
# The PATH Claude Code's session gave this run, before this script adds anything to its own: a tool the
# script can see but the session cannot means Claude Code still needs a restart, whatever ran before.
ORIG_PATH="$PATH"
session_sees() { ( PATH="$ORIG_PATH"; command -v "$1" >/dev/null 2>&1 ); }

HF_PIN="0.8.105"   # keep in sync with the pin in CLAUDE.md / SETUP.md
HF_BEFORE="2026-10-01T23:59:59Z"   # the pin's npm freeze (presets/youtube/default/reference/fullscreen-render.sh § THE NPM FREEZE): the end of its validation day, a full UTC timestamp, never a bare date; moves with HF_PIN
# The toolchain floors. check-setup.sh holds the same three and update.py the uv one (packaging/test_setup_preflight.py
# keeps them equal); ffmpeg's is workflows/ffmpeg-vocab.json's `floor`, the oldest ffmpeg the shipped code runs on.
UV_FLOOR="0.9.17"    # relative exclude-newer ("14 days"): every tool's package cooldown, transcribe.sh and asr_cli
NODE_FLOOR="22.12"   # the render engine's puppeteer-core declares node >=22.12
PY_FLOOR="3.10"      # the Command Line Tools' python3 is 3.9, past its end of life (2025-10): Homebrew's is the one used
FF_FLOOR="$(sed -n 's/^ *"floor": *"\([0-9.]*\)".*/\1/p' "$ROOT/workflows/ffmpeg-vocab.json" 2>/dev/null | head -n 1)"
FF_FLOOR="${FF_FLOOR:-5.1}"

say()  { printf '%s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
# ver_ge <have> <want>: dotted numbers, a missing part is 0 (22.12 = 22.12.0); an empty <have> is never enough
ver_ge() {
  [ -n "$1" ] && awk -v a="$1" -v b="$2" 'BEGIN { na = split(a, x, "."); nb = split(b, y, "."); n = (na > nb) ? na : nb
    for (i = 1; i <= n; i++) { if (x[i] + 0 > y[i] + 0) exit 0; if (x[i] + 0 < y[i] + 0) exit 1 }; exit 0 }'
}
ffmpeg_ver() { ffmpeg -version 2>/dev/null | head -n 1 | awk '{print $3}'; }   # 9.0.2 · 9.0.2-full_build-www.gyan.dev · N-121234-g…
ffmpeg_old() {   # a version was read and it is below the floor (a git master build, N-…, is newer than any release)
  local v; v="$(ffmpeg_ver)"
  case "$v" in N-*|git-*|"") return 1 ;; n[0-9]*) v="${v#n}" ;; esac
  v="$(printf '%s' "$v" | sed -n 's/^\([0-9][0-9]*\(\.[0-9][0-9]*\)*\).*/\1/p')"
  [ -n "$v" ] && ! ver_ge "$v" "$FF_FLOOR"
}
uv_ver()   { uv --version 2>/dev/null | awk '{print $2}'; }
uv_old()   { local v; v="$(uv_ver)"; [ -n "$v" ] && ! ver_ge "$v" "$UV_FLOOR"; }
node_ver() { node -p 'process.versions.node' 2>/dev/null; }
# uv_route: the command that upgrades the uv on PATH the way it was installed (check-setup.sh prints the same).
# `uv self update` only works on the standalone installer's uv, and brew/winget each own theirs.
uv_route() {
  local p; p="$(command -v uv 2>/dev/null)"
  case "$p" in
    "$HOME/.local/bin/"*|"$HOME/.cargo/bin/"*) echo "uv self update" ;;
    *[Ww]in[Gg]et*) echo "winget upgrade --id astral-sh.uv -e" ;;
    /opt/homebrew/*|/usr/local/*|/home/linuxbrew/*)
      if have brew && brew list uv >/dev/null 2>&1; then echo "brew upgrade uv"; else echo "uv self update"; fi ;;
    *) echo "pip install -U uv (with the pip that installed it)" ;;
  esac
}
uv_upgrade() {   # a uv below UV_FLOOR, upgraded by its own route (a pip install is named, never guessed at)
  local route; route="$(uv_route)"
  case "$route" in pip*)
    say "  ⚠ uv $(uv_ver) at $(command -v uv) is older than $UV_FLOOR, which every tool's package cooldown needs:"
    say "    upgrade it with $route, then re-run ./setup.sh"
    return 0 ;;
  esac
  say "  ▸ uv $(uv_ver) is older than $UV_FLOOR, which every tool's package cooldown needs; upgrading ($route)…"
  case "$route" in
    "brew upgrade uv") brew upgrade uv || true ;;
    winget*) winget upgrade --exact --id astral-sh.uv --accept-source-agreements --accept-package-agreements \
               --disable-interactivity >> "$ROOT/.setup-install.log" 2>&1 || true ;;
    "uv self update") uv self update || true ;;
  esac
  hash -r 2>/dev/null
  uv_old && say "  ⚠ uv is still $(uv_ver) at $(command -v uv): upgrade it with: $route, then re-run ./setup.sh"
  return 0
}

# ─── arguments ───────────────────────────────────────────────────────────────
LANE_PICK=""; NEW_INSTALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --new-install) NEW_INSTALL=1 ;;
    --lane)
      shift
      case "${1:-}" in
        premiere|resolve|capcut|finalcut|chat-only) LANE_PICK="$1" ;;
        *) say "usage: ./setup.sh [--lane premiere|resolve|capcut|finalcut|chat-only]"; exit 1 ;;
      esac ;;
    --lane=*)
      case "${1#--lane=}" in
        premiere|resolve|capcut|finalcut|chat-only) LANE_PICK="${1#--lane=}" ;;
        *) say "usage: ./setup.sh [--lane premiere|resolve|capcut|finalcut|chat-only]"; exit 1 ;;
      esac ;;
    -h|--help) sed -n '2,50p' "$0"; exit 0 ;;
    *) say "unknown option: $1"; say "usage: ./setup.sh [--lane premiere|resolve|capcut|finalcut|chat-only] [--new-install]"; exit 1 ;;
  esac
  shift
done

MARKER="$ROOT/.setup-complete"
record_lane() { printf 'lane=%s\n' "$1" > "$MARKER"; }
recorded_lane() { sed -n 's/^lane=//p' "$MARKER" 2>/dev/null | head -n 1; }

UNAME="$(uname -s 2>/dev/null || echo unknown)"
case "$UNAME" in
  Darwin)               OS=mac ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  Linux)                OS=linux ;;
  *)                    OS=other ;;
esac

# A lane pick this OS cannot run is refused before anything is recorded (never silently chat-only).
if [ -n "$LANE_PICK" ]; then
  case "$OS:$LANE_PICK" in
    windows:finalcut|linux:capcut|linux:finalcut|linux:premiere|other:capcut|other:finalcut|other:premiere)
      if [ "$OS" = windows ]; then VALID="premiere, resolve, capcut, chat-only"; else VALID="resolve, chat-only"; fi
      say "  ✗ the $LANE_PICK lane does not run on this OS. Valid here: $VALID"
      exit 1 ;;
  esac
fi

# Python probe: Windows installs Python as `python` (its `python3` is a fake
# Microsoft Store stub), so probe by RUNNING it, never by `command -v`.
pybin() {
  if python3 -c '' >/dev/null 2>&1; then echo python3
  elif python -c '' >/dev/null 2>&1; then echo python
  else echo ""; fi
}
py_ver() { local P; P="$(pybin)"; [ -n "$P" ] && "$P" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null; }
py_ok()  { ver_ge "$(py_ver)" "$PY_FLOOR"; }   # pybin() alone takes any python; the tools' python is $PY_FLOOR+

# ─────────────────────────────────────────────────────────────────────────────
if [ "$OS" = other ]; then
  say "Unrecognized shell/OS ($UNAME)."
  say "On Windows, run this from Git Bash (installed with Git for Windows: winget install Git.Git)."
  exit 1
fi

case "$OS" in mac) OSLBL="macOS" ;; windows) OSLBL="Windows · Git Bash" ;; *) OSLBL="Linux" ;; esac
say "== video-editor auto-setup ($OSLBL) =="
say ""
if [ "$OS" = linux ]; then
  say "Linux: tools are not auto-installed here. If the verify below finds anything"
  say "missing, run the exact apt commands it prints, then re-run ./setup.sh."
  say ""
fi

# ─── macOS: Apple Silicon on macOS 15 or newer, before anything is touched ───
# Homebrew builds its bottles (ready-made binaries) of ffmpeg, node, uv and python only for Apple Silicon on macOS 15+
# (its Tier 1 since 2026-09). Anywhere else every `brew install` below compiles from source for hours and usually fails,
# and an Intel Mac's WhisperX resolves a stack that cannot import (the 2026-10-13 audit). check-setup.sh reports the same.
if [ "$OS" = mac ]; then
  ARCH="$(uname -m 2>/dev/null)"; MACOS="$(sw_vers -productVersion 2>/dev/null)"
  if [ "$ARCH" != arm64 ] || ! ver_ge "$MACOS" 15; then
    if [ "$ARCH" = arm64 ]; then CHIP="Apple Silicon"; else CHIP="an Intel processor ($ARCH)"; fi
    if [ "${VE_UNSUPPORTED_PLATFORM:-}" = 1 ]; then
      say "  ⚠ unsupported: macOS ${MACOS:-?} on $CHIP. Continuing because VE_UNSUPPORTED_PLATFORM=1 is set: Homebrew may"
      say "    compile the tools from source for hours, and on an Intel Mac transcription does not work."
      say ""
    else
      say "✗ This Mac runs macOS ${MACOS:-?} on $CHIP. The editor needs Apple Silicon (M1 or later) on macOS 15 or newer:"
      say "  Homebrew, which installs its tools, ships ready-made builds only there, and anywhere else it compiles"
      say "  ffmpeg, Node, uv and Python from source for hours and usually fails. Nothing was installed."
      [ "$ARCH" = arm64 ] && say "  Update macOS (System Settings › General › Software Update), then re-run ./setup.sh."
      say "  ACTION FOR CLAUDE: tell the user this in plain words. Only if they insist on trying anyway (unsupported,"
      say "  hours of compiling, and no transcription on an Intel Mac): VE_UNSUPPORTED_PLATFORM=1 ./setup.sh"
      exit 1
    fi
  fi
fi

# ─── Writability preflight (all OSes, before anything installs) ──────────────
# Every later step writes here (vendor/, the markers, and projects/<job>/ on every edit),
# and on Windows a blocked write does NOT say "permission denied": Controlled Folder Access
# (Windows Security › Ransomware protection) hides Documents, Desktop, Pictures, Videos,
# Music and OneDrive from every app not on its allow-list (Git Bash, git, node and python
# all count), and the failures read "No such file or directory" for a folder that plainly
# exists. A client read that as a path bug and burned real time; this script kept going
# past three of them into the lane installer (2026-09-07). Prove one write, name the cause.
CFA=""   # Windows: 0 off · 1 on · 2 audit · empty = not readable (no Defender, no PowerShell)
if [ "$OS" = windows ]; then
  CFA="$(powershell.exe -NoProfile -NonInteractive -Command '(Get-MpPreference).EnableControlledFolderAccess' 2>/dev/null | tr -d '[:space:]')"
fi
cfa_fixes() {
  say "  Windows Security's Controlled Folder Access is ON (EnableControlledFolderAccess=$CFA). It blocks writes"
  say "  to Documents, Desktop, Pictures, Videos, Music and OneDrive for every app not on its allow-list, Git"
  say "  Bash, git, node and python included, and the errors read 'No such file or directory', not 'permission"
  say "  denied'. Pick one fix, then re-run ./setup.sh:"
  say "    • RECOMMENDED: move this whole folder outside those locations, e.g. C:\\Users\\<you>\\video-editor,"
  say "      and reopen it in Claude Code."
  say "    • or allow the four apps: Windows Security → Virus & threat protection → Ransomware protection →"
  say "      Allow an app through Controlled folder access (bash.exe, git.exe, node.exe, python.exe)."
}
PROBE="$ROOT/.ve-write-probe"
if { : > "$PROBE"; } 2>/dev/null; then
  rm -f "$PROBE"
  if [ "$OS" = windows ]; then
    case "$CFA:$ROOT" in
      1:*/Documents/*|1:*/Desktop/*|1:*/Pictures/*|1:*/Videos/*|1:*/Music/*|1:*/OneDrive/*)
        say "  ⚠ this folder sits inside a location Controlled Folder Access protects, and it is ON. Git Bash"
        say "    can write here (so it is allow-listed), but git, node and python are separate entries: if a render,"
        say "    an update or an edit fails with 'No such file or directory', move the folder to C:\\Users\\<you>\\video-editor."
        say "" ;;
      *:*/OneDrive*)
        say "  ⚠ this folder is inside OneDrive, so raw footage and renders would upload to the cloud and can be"
        say "    offloaded from this PC mid-edit. ACTION FOR CLAUDE: offer to move it to C:\\Users\\<you>\\video-editor"
        say "    (copy it there yourself, then the user reopens that folder)."
        say "" ;;
    esac
  fi
else
  say "✗ This folder is not writable: $ROOT"
  case "$OS:$CFA" in
    windows:1|windows:2) cfa_fixes ;;
    windows:*) say "  Move the folder somewhere you own (e.g. C:\\Users\\<you>\\video-editor) or fix its permissions,"
               say "  then re-run ./setup.sh." ;;
    *)         say "  Fix its permissions (or move it somewhere you own), then re-run ./setup.sh." ;;
  esac
  exit 1
fi

# ─── Windows: a folder too deep for its own files ────────────────────────────
# Windows stops a path at 259 characters, and this editor makes files up to 145 characters deep inside
# its folder (the Resolve server's venv; the Premiere engine's node_modules reach 138). A folder about
# 155 characters deep broke the Resolve server's clone ("Filename too long", the Windows re-test,
# 2026-09-27), and past that git, pip and npm fail one after another. Refuse it before anything installs
# (the user's call): 100 characters leaves room for a deeper dependency later.
ROOT_MAX=100
if [ "$OS" = windows ]; then
  ROOT_WIN="$(cygpath -w "$ROOT" 2>/dev/null || printf '%s' "$ROOT")"
  if [ "${#ROOT_WIN}" -gt "$ROOT_MAX" ]; then
    say "✗ This folder's path is ${#ROOT_WIN} characters long: $ROOT_WIN"
    say "  Windows stops a path at 259 characters and this editor puts files up to 145 characters deep inside"
    say "  its folder, so an install here breaks (git, pip and npm fail with 'Filename too long'). Nothing was"
    say "  installed. Move this whole folder somewhere with a path of at most $ROOT_MAX characters, e.g."
    say "  C:\\Users\\<you>\\video-editor, open it in Claude Code, and run ./setup.sh there."
    exit 1
  fi
fi

# ─── A fresh folder next to an install already set up? ───────────────────────
# A new version unzipped into its own folder and set up would make a second, unconnected install (and the
# user's changes stay in the old one). Ask first, once: update that install, or keep a separate one.
if [ ! -f "$MARKER" ] && [ -f "$ROOT/update.py" ] && [ "$NEW_INSTALL" -eq 0 ] && [ ! -f "$ROOT/.setup-second-install" ]; then
  FOUND=""
  if have uv; then FOUND="$(uv run -q update.py --find-installs 2>/dev/null | head -n 1)"
  elif [ -n "$(pybin)" ]; then FOUND="$("$(pybin)" update.py --find-installs 2>/dev/null | head -n 1)"
  fi
  if [ -n "$FOUND" ]; then
    say "ACTION FOR CLAUDE: this folder looks like a NEW VERSION of the editor already installed at $FOUND. Ask the"
    say "user in one line: update that install (run uv run update.py here), or make a second, separate install"
    say "(./setup.sh --new-install)?"
    exit 1
  fi
fi
[ "$NEW_INSTALL" -eq 1 ] && : > "$ROOT/.setup-second-install"

PENDING=0        # 1 when something needs a restart/new terminal before it's usable
PENDING_WHY=""   # one line saying what

# ─── macOS: Homebrew installs ────────────────────────────────────────────────
if [ "$OS" = mac ]; then
  # Homebrew installs to /opt/homebrew (Apple Silicon) or /usr/local (Intel), and neither
  # is on the default PATH: right after its installer finishes, `brew` is invisible to the
  # shell that ran it. Find it there, put it on THIS process's PATH so the run can finish,
  # and add Homebrew's own shellenv line to the login profile so every later shell sees it.
  BREW_OFF_PATH=""
  if ! have brew; then
    for b in /opt/homebrew/bin /usr/local/bin; do
      if [ -x "$b/brew" ]; then BREW_OFF_PATH="$b"; PATH="$b:$PATH"; export PATH; break; fi
    done
  fi
  if ! have brew; then
    say "Homebrew is missing: it's the one step that needs YOUR password, so run this"
    say "in your terminal, then re-run ./setup.sh (it finds the new Homebrew on its own"
    say "and adds it to your shell PATH; nothing else to do):"
    say ''
    say '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
  fi
  if [ -n "$BREW_OFF_PATH" ]; then
    case "$(basename "${SHELL:-/bin/zsh}")" in
      bash) PROFILE="$HOME/.bash_profile" ;;
      zsh)  PROFILE="$HOME/.zprofile" ;;
      *)    PROFILE="$HOME/.profile" ;;
    esac
    say "  ▸ Homebrew is installed at $BREW_OFF_PATH but not on this shell's PATH; adding it to $PROFILE…"
    if ! grep -qsF "$BREW_OFF_PATH/brew shellenv" "$PROFILE"; then
      printf '\n# Homebrew on PATH (added by video-editor setup.sh)\neval "$(%s/brew shellenv)"\n' "$BREW_OFF_PATH" >> "$PROFILE"
    fi
    eval "$("$BREW_OFF_PATH/brew" shellenv)"
    PENDING=1; PENDING_WHY="Homebrew's PATH was added to $PROFILE, which only new sessions read."
  fi
  # yt-dlp is OPTIONAL (reference clips + YouTube research; nothing in the pipeline calls it).
  # It rides the same loop because the install is free, but check-setup.sh reports it in
  # the optional tier, so a failed install never blocks .setup-complete.
  for pkg in ffmpeg uv node python yt-dlp; do
    case "$pkg" in
      ffmpeg) probe=ffmpeg ;;
      uv)     probe=uv ;;
      node)   probe=node ;;
      yt-dlp) probe=yt-dlp ;;
      python) probe="" ;;   # probed via py_ok below
    esac
    if [ "$pkg" = python ]; then
      py_ok && { say "  ✓ python present"; continue; }
      [ -n "$(pybin)" ] && say "  · $(pybin) is $(py_ver) at $(command -v "$(pybin)"): the editor runs on $PY_FLOOR or newer"
    elif have "$probe"; then
      say "  ✓ $pkg present"; continue
    fi
    say "  ▸ installing $pkg (brew)…"
    if ! brew install "$pkg"; then
      if [ "$pkg" = yt-dlp ]; then
        say "  ⚠ brew install yt-dlp failed; optional (reference-clip downloads only), setup continues"
      else
        say "  ⚠ brew install $pkg failed; re-run ./setup.sh after fixing the error above"
      fi
    fi
  done
  # Present is not enough: each tool at its floor (check-setup.sh counts one below it missing). Upgraded the way it was
  # installed, then re-probed: a copy earlier on PATH (nvm, a manual install) still wins over Homebrew's.
  if have node && ! ver_ge "$(node_ver)" "$NODE_FLOOR"; then
    say "  ▸ node v$(node_ver) is older than the render engine's $NODE_FLOOR; upgrading (brew)…"
    if brew list node >/dev/null 2>&1; then brew upgrade node || true; else brew install node || true; fi
    hash -r 2>/dev/null
    if ! ver_ge "$(node_ver)" "$NODE_FLOOR"; then
      say "  ⚠ node is still v$(node_ver) at $(command -v node): an older node earlier on PATH (nvm, a manual"
      say "    install) wins over Homebrew's. Switch it to the current LTS (e.g. nvm install --lts && nvm alias default"
      say "    lts/*) or remove it, then re-run ./setup.sh"
    fi
  fi
  if have ffmpeg && ffmpeg_old; then
    say "  ▸ ffmpeg $(ffmpeg_ver) is older than $FF_FLOOR, the oldest the editor runs on; upgrading (brew)…"
    if brew list ffmpeg >/dev/null 2>&1; then brew upgrade ffmpeg || true; else brew install ffmpeg || true; fi
    hash -r 2>/dev/null
    ffmpeg_old && say "  ⚠ ffmpeg is still $(ffmpeg_ver) at $(command -v ffmpeg): an older ffmpeg earlier on PATH wins over Homebrew's; remove it, then re-run ./setup.sh"
  fi
  if have uv && uv_old; then uv_upgrade; fi
fi

# ─── Windows: winget installs + same-session PATH pickup ─────────────────────
if [ "$OS" = windows ]; then
  if ! have winget && ! have winget.exe; then
    say "winget is missing. Install 'App Installer' from the Microsoft Store, then re-run ./setup.sh."
    exit 1
  fi
  # wg <winget-id>: quiet, license-accepted, exact-id install. Its output goes to .setup-install.log and
  # a real failure is named (a declined or unseen admin prompt, no rights, no network, a company policy),
  # never mistaken for "not on PATH yet", which only ever asked for another restart (found 2026-09-25).
  : > "$ROOT/.setup-install.log"
  WG_FAILED=""
  wg() {   # wg <winget-id> core|optional
    local out rc
    if [ -z "${UAC_SAID:-}" ]; then
      say "  (Windows may ask \"Do you want to allow this app to make changes?\" during an install: click Yes. The"
      say "   prompt can open behind other windows, so check the taskbar if an install seems stuck.)"
      UAC_SAID=1
    fi
    out="$(winget install --exact --id "$1" --accept-source-agreements --accept-package-agreements \
      --disable-interactivity 2>&1)"; rc=$?
    printf '== winget install %s (exit %s)\n%s\n' "$1" "$rc" "$out" >> "$ROOT/.setup-install.log"
    if printf '%s' "$out" | grep -qiE 'already installed|no (available|applicable) upgrade|no newer package'; then
      return 0
    elif [ "$rc" -eq 0 ]; then
      [ "$2" = core ] && INSTALLED_NOW=1
    elif [ "$2" = core ]; then
      WG_FAILED="$WG_FAILED $1"
    else
      say "  ⚠ $1 could not be installed (optional, only for downloading reference clips): see .setup-install.log"
      : > "$ROOT/.setup-optional-failed"
    fi
    return 0
  }
  # Pull freshly installed tools into THIS session's PATH (winget updates the user PATH,
  # but only new terminals see that). Best-effort: well-known install dirs + winget's
  # portable-package folders (Links/ is where portable packages like uv get their shims).
  # Makes one-run setup possible.
  refresh_path() {
    local d
    for d in "/c/Program Files/nodejs" \
             "$(cygpath -u "${LOCALAPPDATA:-}" 2>/dev/null)/Programs/Python/Python312" \
             "$(cygpath -u "${LOCALAPPDATA:-}" 2>/dev/null)/Programs/Python/Python312/Scripts" \
             "$(cygpath -u "${LOCALAPPDATA:-}" 2>/dev/null)/Microsoft/WinGet/Links" \
             "$(cygpath -u "${USERPROFILE:-}" 2>/dev/null)/.local/bin"; do
      [ -d "$d" ] && PATH="$d:$PATH"
    done
    # Gyan.FFmpeg is a winget "portable" package; its bin lands under WinGet/Packages
    for d in "$(cygpath -u "${LOCALAPPDATA:-}" 2>/dev/null)/Microsoft/WinGet/Packages"/Gyan.FFmpeg*/ffmpeg-*/bin; do
      [ -d "$d" ] && PATH="$d:$PATH"
    done
    export PATH
  }

  # wg_up <winget-id>: a present tool below its floor. `winget install` of a package winget already holds answers
  # "already installed" and upgrades nothing, so it is upgraded; one winget never installed is installed beside it.
  wg_up() {
    local out rc
    out="$(winget upgrade --exact --id "$1" --accept-source-agreements --accept-package-agreements \
      --disable-interactivity 2>&1)"; rc=$?
    printf '== winget upgrade %s (exit %s)\n%s\n' "$1" "$rc" "$out" >> "$ROOT/.setup-install.log"
    [ "$rc" -ne 0 ] && printf '%s' "$out" | grep -qi 'no installed package' && wg "$1" core
    return 0
  }

  refresh_path     # what an earlier run installed is found, not installed again
  if ! have ffmpeg; then say "  ▸ installing ffmpeg (winget)…";  wg Gyan.FFmpeg core
  elif ffmpeg_old; then
    say "  ▸ ffmpeg $(ffmpeg_ver) at $(command -v ffmpeg) is older than $FF_FLOOR, the oldest the editor runs on; installing the current one (winget)…"
    wg_up Gyan.FFmpeg; refresh_path
  else say "  ✓ ffmpeg present"; fi
  if have node; then
    if ! ver_ge "$(node_ver)" "$NODE_FLOOR"; then
      say "  ▸ node v$(node_ver) is older than the render engine's $NODE_FLOOR; installing the LTS (winget)…"
      wg_up OpenJS.NodeJS.LTS; refresh_path
    else
      say "  ✓ node present"
    fi
  else say "  ▸ installing node (winget)…";    wg OpenJS.NodeJS.LTS core; fi
  if ! have uv; then say "  ▸ installing uv (winget)…";      wg astral-sh.uv core
  elif uv_old; then uv_upgrade; refresh_path
  else say "  ✓ uv present"; fi
  if py_ok; then say "  ✓ python present"
  else
    [ -n "$(pybin)" ] && say "  · $(pybin) is $(py_ver): the editor runs on $PY_FLOOR or newer"
    say "  ▸ installing python (winget)…"; wg Python.Python.3.12 core
  fi
  # optional (reference-clip downloads); a portable package, its shim lands in WinGet/Links.
  # Deliberately NOT in the PENDING loop below: an invisible yt-dlp must never force a restart.
  if have yt-dlp; then say "  ✓ yt-dlp present"; else say "  ▸ installing yt-dlp (winget, optional)…"; [ -f "$ROOT/.setup-optional-failed" ] || wg yt-dlp.yt-dlp optional; fi

  refresh_path

  if [ -z "$(pybin)" ]; then
    say "  ⚠ python not visible yet in this session"
    PENDING=1; PENDING_WHY="Just-installed tools are not on this session's PATH yet."
  fi
  for t in ffmpeg node uv; do
    have "$t" || { say "  ⚠ $t not visible yet in this session"; PENDING=1; PENDING_WHY="Just-installed tools are not on this session's PATH yet."; }
  done
  if [ -n "$WG_FAILED" ] && [ "$PENDING" -eq 1 ]; then
    say ""
    say "✗ winget could not install:$WG_FAILED. Its own words (all of it is in .setup-install.log):"
    for id in $WG_FAILED; do
      awk -v id="$id" '/^== winget install /{on = ($4 == id)} on' "$ROOT/.setup-install.log" | tail -n 4 | sed 's/^/    /'
    done
    say "  Usual causes: the \"allow this app to make changes?\" prompt answered No or never seen, no admin"
    say "  rights on this PC, no network, or a company policy. Fix that, then re-run ./setup.sh."
    exit 1
  fi
fi

# ─── Render-engine bootstrap (all OSes) ──────────────────────────────────────
# ensure_watched: the bootstrap, watched. The pin's `browser ensure` prints its error and then never exits, its spinner
# never stopped (a dropped network, a read-only ~/.cache, no `unzip` on Linux; fixed upstream in 0.8.144, the pin held
# below it on purpose), so a failure froze setup with nothing on screen and its ✗ branch could never run (the 2026-10-13
# audit). Its own error line, or VE_ENSURE_MAX_S (30 minutes) with no exit, ends it: the WHOLE process tree goes, since
# killing npx alone leaves its node child spinning and appending to the log.
tree_of() {   # tree_of <pid>: the pid and every process under it, by ps parent links (macOS, Linux)
  local k; echo "$1"
  for k in $(ps -A -o pid= -o ppid= 2>/dev/null | awk -v p="$1" '$2 == p {print $1}'); do tree_of "$k"; done
}
kill_tree() {
  local pids
  if [ "$OS" = windows ]; then   # Git Bash: npx's node.exe is a Windows child, which only taskkill's tree walk reaches
    taskkill //T //F //PID "$(cat "/proc/$1/winpid" 2>/dev/null || echo "$1")" >/dev/null 2>&1
    kill "$1" 2>/dev/null; return 0
  fi
  pids="$(tree_of "$1")"
  kill -TERM $pids 2>/dev/null; sleep 2; kill -KILL $pids 2>/dev/null; return 0
}
ensure_watched() {
  local log="$ROOT/.setup-install.log" from pid t=0 hit=-1 max="${VE_ENSURE_MAX_S:-1800}"
  : >> "$log"; from=$(( $(wc -c < "$log") + 1 ))
  npm_config_before="$HF_BEFORE" npx -y "hyperframes@$HF_PIN" browser ensure >> "$log" 2>&1 < /dev/null &
  pid=$!
  while kill -0 "$pid" 2>/dev/null; do
    if [ "$hit" -lt 0 ] && tail -c "+$from" "$log" 2>/dev/null | grep -qE \
         'Failed to download|All providers failed|Extraction failed|Browser not available|EACCES|EPERM|ENOSPC|ENOTFOUND|EAI_AGAIN|ECONNREFUSED|ECONNRESET|ETIMEDOUT'; then
      hit=$t
    fi
    if { [ "$hit" -ge 0 ] && [ $((t - hit)) -ge 10 ]; } || [ "$t" -ge "$max" ]; then
      kill_tree "$pid"; wait "$pid" 2>/dev/null
      if [ "$hit" -ge 0 ]; then printf '\n== setup.sh: browser ensure failed and did not exit; its process tree was stopped\n' >> "$log"
      else printf '\n== setup.sh: browser ensure ran %s s without finishing; its process tree was stopped\n' "$max" >> "$log"; fi
      return 124
    fi
    sleep 1; t=$((t + 1))
  done
  wait "$pid"
}
# `browser ensure` finds or downloads the headless Chrome the renderer uses and exits
# non-zero if it cannot (`doctor` only REPORTS, always exits 0, and downloads nothing,
# so it could never gate the marker). One time; the download is about 270 MB (the render engine
# package plus its headless browser).
say ""
if have npx; then
  # The marker carries the pin, so a version bump re-runs the bootstrap instead of trusting an old one.
  HAVE_PIN="$(cat .setup-hyperframes-ok 2>/dev/null | tr -cd '0-9.')"
  [ -f .setup-hyperframes-ok ] && [ -z "$HAVE_PIN" ] && HAVE_PIN=0.8.16   # every setup before 2026.09.25.3
  # THE NPM FREEZE never reaches a tree npx already holds: npx keys it by the spec alone (_npx/<the first 16 hex of the
  # sha512 of "hyperframes@<pin>">, every call site's key) and reuses it whatever npm_config_before says, so a cache
  # filled before the freeze kept puppeteer-core 25.13.0 (the Windows re-test, 2026-10-13). Once per freeze that tree
  # is removed and the bootstrap below rebuilds it frozen; .setup-npx-frozen records it. The npm cache is
  # npm_config_cache, else ~/.npm (%LOCALAPPDATA%\npm-cache on Windows): npm 11 refuses `npm config get cache`.
  NPX_FROZEN="hyperframes@$HF_PIN $HF_BEFORE"
  if [ "$(cat .setup-npx-frozen 2>/dev/null)" != "$NPX_FROZEN" ]; then
    NPX_KEY="$(printf '%s' "hyperframes@$HF_PIN" | { if have sha512sum; then sha512sum; else shasum -a 512; fi; } 2>/dev/null | cut -c1-16)"
    case "$NPX_KEY" in *[!0-9a-f]*) NPX_KEY="" ;; esac
    for c in "${npm_config_cache:-}" "$HOME/.npm" "${LOCALAPPDATA:+$LOCALAPPDATA/npm-cache}" \
             "$(npm config get cache 2>/dev/null | tr -d '\r')"; do
      [ -n "$c" ] && have cygpath && c="$(cygpath -u "$c")"
      [ "${#NPX_KEY}" -eq 16 ] && [ -n "$c" ] && [ -d "$c/_npx/$NPX_KEY" ] && rm -rf "$c/_npx/$NPX_KEY"
    done
    HAVE_PIN=""
  fi
  if [ "$HAVE_PIN" = "$HF_PIN" ]; then
    say "  ✓ render engine already bootstrapped (npx hyperframes@$HF_PIN)"
  else
    say "  ▸ bootstrapping the render engine (npx hyperframes@$HF_PIN browser ensure; one time,"
    say "    downloads the render engine and its headless browser, about 270 MB; nothing prints while it runs)…"
    # usage telemetry off FIRST, as the Premiere engine's is (setup-premiere.sh): nothing here needs it.
    # The download's spinner redraws on one line for as long as it runs, so its output goes to the log.
    npm_config_before="$HF_BEFORE" npx -y "hyperframes@$HF_PIN" telemetry disable >/dev/null 2>&1 || true
    if ensure_watched; then
      printf '%s\n' "$HF_PIN" > ".setup-hyperframes-ok"
      printf '%s\n' "$NPX_FROZEN" > ".setup-npx-frozen"
      say "  ✓ render engine ready (pinned to hyperframes@$HF_PIN on purpose; never run 'hyperframes upgrade')"
    else
      RENDER_FAILED=1
      say "  ✗ the render engine could not fetch its headless browser (usually the network). Its last words:"
      tail -c 6000 "$ROOT/.setup-install.log" | tr '\r' '\n' | sed 's/\x1b\[[0-9;?]*[A-Za-z]//g' \
        | grep -v -e '^[[:space:]]*$' -e 'Downloading' -e 'Looking for an existing browser' | tail -n 6 | sed 's/^/    /'
    fi
  fi
else
  if [ "$OS" = windows ]; then
    say "  ⚠ npx not available yet; the render-engine bootstrap runs on the next ./setup.sh"
    PENDING=1; PENDING_WHY="Just-installed tools are not on this session's PATH yet."
  else
    # macOS/Linux: node is genuinely missing (nothing installed it this run, or the brew
    # install failed). Fall through so check-setup.sh prints the real install command.
    say "  ⚠ node/npx missing: the check below prints the install command; the render-engine"
    say "    bootstrap runs on the next ./setup.sh"
  fi
fi

# ─── Windows: Smart App Control's first look at the tools' files ─────────────
# Smart App Control checks a native file online the first time it loads (tens of seconds a file) and, under load,
# fails that check as a block that a second load passes; a release too new to have reputation stays blocked
# (2026-10-13). One sequential pass here pays the first look before an edit needs it, and names a block that stays.
# It builds every tool's Python environment from its lock (the first time: minutes). Report only, never a gate.
if [ "$OS" = windows ] && have uv && [ "$(cat .setup-sac-ok 2>/dev/null)" != "$(cat VERSION 2>/dev/null)" ]; then
  say ""
  say "  ▸ pre-checking the tools' files with Smart App Control (once per version)…"
  SAC_RC=0; uv run workflows/sac-warm.py || SAC_RC=$?
  if [ "$SAC_RC" -eq 0 ]; then cat VERSION > .setup-sac-ok 2>/dev/null || true
  else say "  ⚠ a tool's file is blocked, or its environment did not build (named above): the rest of the editor works; report it"; fi
fi

# ─── Restart gate ────────────────────────────────────────────────────────────
say ""
if [ "$PENDING" -eq 1 ]; then
  RESTARTS="$(sed -n 1p .setup-restarts 2>/dev/null)"; RESTARTS=$(( ${RESTARTS:-0} + 1 ))
  printf '%s\n' "$RESTARTS" > .setup-restarts
  if [ "$RESTARTS" -ge 3 ]; then
    GONE=""
    for t in ffmpeg node uv npx; do have "$t" || GONE="$GONE $t"; done
    [ -n "$(pybin)" ] || GONE="$GONE python"
    [ -n "${BREW_OFF_PATH:-}" ] && GONE=" brew (Homebrew itself)$GONE"
    say "✗ Installed, but still not visible after $((RESTARTS - 1)) restarts:${GONE:- (see above)}. Restarting again will not help."
    [ "$OS" = windows ] && [ -s .setup-install.log ] && { say "  The installer's own words (.setup-install.log):"; tail -n 8 .setup-install.log | sed 's/^/    /'; }
    if [ "$OS" = windows ]; then
      say "  ACTION FOR CLAUDE: find where each one landed (look under \"C:\\Program Files\" and"
      say "  %LOCALAPPDATA%\\Microsoft\\WinGet\\Packages), add that folder to the user's PATH (or reinstall it by the"
      say "  command ./check-setup.sh prints), then have the user restart Claude Code once and re-run ./setup.sh."
    else
      say "  ACTION FOR CLAUDE: add  eval \"\$(${BREW_OFF_PATH:-/opt/homebrew/bin}/brew shellenv)\"  to ~/.zshrc as well as"
      say "  ~/.zprofile (Claude Code may read either), run 'brew doctor', then have the user restart Claude Code"
      say "  once and re-run ./setup.sh."
    fi
    printf '1\n' > .setup-restarts     # one more restart is allowed after the fix
    exit 1
  fi
  say "== Almost done: this session needs a fresh environment =="
  say "$PENDING_WHY"
  say "One step for you: RESTART Claude Code (quit it fully, then reopen the folder $ROOT_SHOW)"
  say "and say \"continue setup\"; it re-runs ./setup.sh, which skips everything"
  say "already done and finishes the rest."
  exit 2
fi

rm -f .setup-restarts
say "== Verifying with check-setup.sh =="
# VE_SETUP_RUNNING: the lane engines are installed by the block AFTER this check, so their
# "not installed, run ./setup-<app>.sh" notes would send the user to do by hand what happens
# next (a client saw "davinci-resolve-mcp not installed" in the run that installed it).
VE_SETUP_RUNNING=1 ./check-setup.sh || { say ""; say "Fix the items above, then re-run ./setup.sh"; exit 1; }

# A below-floor copy EARLIER on Claude Code's own PATH passed the check above: refresh_path put winget's current one
# first for this run, but every edit runs the session's (a System PATH folder, choco or C:\ffmpeg\bin, always precedes
# winget's User PATH entry; the Windows re-test, 2026-10-13: setup ran ffmpeg 9.0.2, the marker recorded 4.4.2).
# Only ANOTHER copy than this run's, and only when this run's passes its floor: the same copy on both PATHs is the
# check's to judge (node 22.0 to 22.11 is a note there), never a PATH order to fix.
session_other() { local s; s="$( PATH="$ORIG_PATH"; command -v "$1" 2>/dev/null )"; [ -n "$s" ] && [ "$s" != "$(command -v "$1" 2>/dev/null)" ]; }
SESSION_OLD=""
session_other ffmpeg && ! ffmpeg_old && ( PATH="$ORIG_PATH"; ffmpeg_old ) && SESSION_OLD="$SESSION_OLD; ffmpeg $( PATH="$ORIG_PATH"; ffmpeg_ver ) at $( PATH="$ORIG_PATH"; command -v ffmpeg )"
session_other node && ver_ge "$(node_ver)" "$NODE_FLOOR" && ! ( PATH="$ORIG_PATH"; ver_ge "$(node_ver)" "$NODE_FLOOR" ) && SESSION_OLD="$SESSION_OLD; node v$( PATH="$ORIG_PATH"; node_ver ) at $( PATH="$ORIG_PATH"; command -v node )"
session_other uv && ! uv_old && ( PATH="$ORIG_PATH"; uv_old ) && SESSION_OLD="$SESSION_OLD; uv $( PATH="$ORIG_PATH"; uv_ver ) at $( PATH="$ORIG_PATH"; command -v uv )"
if [ -n "$SESSION_OLD" ]; then
  say "✗ Claude Code's own PATH finds an older copy first (this run used the current one): ${SESSION_OLD#; }"
  say "  ACTION FOR CLAUDE: remove that copy, or move its folder after the current one's on PATH (on Windows a System"
  say "  PATH folder comes before every User PATH folder), then have the user restart Claude Code and re-run ./setup.sh."
  exit 1
fi

# ─── Self-test: the tools RUN the pipeline (workflows/selftest.py --smoke, under 30 s) ───
# check-setup.sh proved the versions and the ffmpeg vocabulary; this proves they work end to end: a timecoded clip read
# the way every tool reads one, a frame-exact read through ffmpeg_compat and a two-segment splice rendered. A client's
# first edit died on ffmpeg 9's deleted -vsync (2026-10-13); here setup stops on it, naming the cause, and writes no
# marker. A toolchain the marker records as already passed (the same versions, this VERSION) is not re-run.
toolchain() {   # what Claude Code's session runs (its own PATH, ORIG_PATH), one key=value a line, for the marker
  ( PATH="$ORIG_PATH"
    printf 'ffmpeg=%s\n' "$(ffmpeg_ver)"
    printf 'uv=%s\n' "$(uv_ver)"
    printf 'node=%s\n' "$(node_ver)"
    printf 'python=%s\n' "$(py_ver)"
    if [ "$OS" = mac ]; then printf 'platform=macOS %s %s\n' "$(sw_vers -productVersion 2>/dev/null)" "$(uname -m)"
    else printf 'platform=%s %s\n' "$UNAME" "$(uname -m)"; fi
    printf 'selftest=%s\n' "$(tr -d '\r' < "$ROOT/VERSION" 2>/dev/null)" )
}
TOOLCHAIN="$(toolchain)"
TESTED=1
while IFS= read -r line; do grep -qxF "$line" "$MARKER" 2>/dev/null || TESTED=0; done <<EOF
$TOOLCHAIN
EOF
if [ ! -f "$ROOT/workflows/selftest.py" ]; then
  :
elif [ "$TESTED" -eq 1 ]; then
  say ""; say "  ✓ self-test passed on this toolchain before ($(printf '%s' "$TOOLCHAIN" | grep -E '^(ffmpeg|uv|node)=' | tr '\n' ' '))"
else
  say ""; say "== Self-test (under 30 s) =="
  if ! "$(pybin)" "$ROOT/workflows/selftest.py" --smoke; then
    say ""
    say "✗ The tools are installed but the pipeline does not run on them (the ✗ lines above, in ffmpeg's own words)."
    say "  ACTION FOR CLAUDE: fix what they name: usually an old or lean ffmpeg build (brew upgrade ffmpeg · winget"
    say "  upgrade --id Gyan.FFmpeg -e · Linux: a current static build), then re-run ./setup.sh. If the cause is not clear,"
    say "  tell the user to send the output to support."
    exit 1
  fi
fi

# Core tools verified: record it so the fresh-install reminder stops firing. The lane line
# is filled in by the block below (a re-run keeps whatever was recorded before).
# (The editing-app lane below and the brand kit are optional layers on top.)
[ -f "$MARKER" ] || record_lane pending
REC_LANE="$(recorded_lane)"

# ─── Editing-app lane (auto-detected, optional) ──────────────────────────────
# If an editing app is installed, settle the lane now so rough cuts can land on a
# real timeline: exactly one app → wire it without asking; several → Claude asks
# the user which they edit in (a script can't) and records the answer with
# ./setup.sh --lane <pick>; none → chat-only finish, done.
say ""
say "== Editing apps =="
DET_PREMIERE=0; DET_RESOLVE=0; DET_CAPCUT=0; DET_FINALCUT=0
if [ "$OS" = mac ]; then
  compgen -G "/Applications/Adobe Premiere Pro*" >/dev/null 2>&1 && DET_PREMIERE=1
  # Blackmagic's installer nests the app in its own folder; the App Store builds sit flat
  # (the same three paths setup-resolve.sh resolves).
  for app in "/Applications/DaVinci Resolve/DaVinci Resolve.app" "/Applications/DaVinci Resolve.app" \
             "/Applications/DaVinci Resolve Studio.app"; do
    [ -d "$app" ] && DET_RESOLVE=1
  done
  [ -d "/Applications/CapCut.app" ] && DET_CAPCUT=1
  # the App Store's one-time purchase ("Final Cut Pro.app") or Apple Creator Studio's edition
  compgen -G "/Applications/Final Cut Pro*.app" >/dev/null 2>&1 && DET_FINALCUT=1
elif [ "$OS" = windows ]; then
  compgen -G "/c/Program Files/Adobe/Adobe Premiere Pro*" >/dev/null 2>&1 && DET_PREMIERE=1
  [ -e "/c/Program Files/Blackmagic Design/DaVinci Resolve/Resolve.exe" ] && DET_RESOLVE=1
  # CapCut for Windows installs per user (its bridge's live lane there: lanes/capcut/capcut_win.py, 2026-09-27)
  [ -e "$(cygpath -u "${LOCALAPPDATA:-}" 2>/dev/null)/CapCut/Apps/CapCut.exe" ] && DET_CAPCUT=1
else
  # Linux: Resolve is the only app lane here (native install at /opt/resolve)
  [ -d /opt/resolve ] && DET_RESOLVE=1
fi
# A lane this package does not SHIP (built with package-for-client.sh --lane <app>) is
# never offered, whatever is installed: its installer and skill are not here. The SKILL decides,
# since lanes/ folders can outlive a prune or come with an older version.
lane_ships() { local s; case "$1" in premiere) s=premiere-pro;; resolve) s=davinci-resolve;; capcut) s=capcut;; finalcut) s=final-cut-pro;; *) return 1;; esac; [ -d "$ROOT/.claude/skills/$s" ]; }
if [ "$DET_PREMIERE" -eq 1 ] && ! lane_ships premiere; then
  say "  · Premiere Pro detected, but this package does not include the Premiere lane"; DET_PREMIERE=0
fi
if [ "$DET_RESOLVE" -eq 1 ] && ! lane_ships resolve; then
  say "  · DaVinci Resolve detected, but this package does not include the Resolve lane"; DET_RESOLVE=0
fi
if [ "$DET_CAPCUT" -eq 1 ] && ! lane_ships capcut; then
  say "  · CapCut detected, but this package does not include the CapCut lane"; DET_CAPCUT=0
fi
if [ "$DET_FINALCUT" -eq 1 ] && ! lane_ships finalcut; then
  say "  · Final Cut Pro detected, but this package does not include the Final Cut lane"; DET_FINALCUT=0
fi
# The which-app question counts EVERY installed lane app, CapCut included: a CapCut editor
# with Premiere also installed must be asked, never handed a Premiere lane they never use.
N_APPS=$((DET_PREMIERE + DET_RESOLVE + DET_CAPCUT + DET_FINALCUT))
APPS=""
[ "$DET_PREMIERE" -eq 1 ] && APPS="$APPS premiere"
[ "$DET_RESOLVE"  -eq 1 ] && APPS="$APPS resolve"
[ "$DET_CAPCUT"   -eq 1 ] && APPS="$APPS capcut"
[ "$DET_FINALCUT" -eq 1 ] && APPS="$APPS finalcut"
APPS="${APPS# }"

# Find the lane installers (package root, or packaging/overlay/ in the source repo)
lane_script() { if [ -f "$ROOT/$1" ]; then echo "$ROOT/$1"; else echo "$HERE/$1"; fi; }

# Already wired? (engine built + entry present in .mcp.json)
WIRED_PREMIERE=0; WIRED_RESOLVE=0; WIRED_FINALCUT=0
[ -f "$ROOT/vendor/premiere-mcp/dist/index.js" ] && grep -qs '"premiere-pro"' "$ROOT/.mcp.json" && WIRED_PREMIERE=1
# Resolve = Blackmagic's own ResolveMCP (Studio 21.1+) as .mcp.json's davinci-resolve entry. An entry pointing anywhere
# else is the community engine retired 2026-10-05: not wired, so a recorded Resolve lane is rewired below.
if [ -f "$ROOT/.mcp.json" ] && [ -n "$(pybin)" ]; then
  RC="$("$(pybin)" -c 'import json,sys;print(json.load(open(sys.argv[1],encoding="utf-8-sig")).get("mcpServers",{}).get("davinci-resolve",{}).get("command",""))' "$ROOT/.mcp.json" 2>/dev/null)"
  case "$RC" in *ResolveMCP|*ResolveMCP.exe)
    { [ -x "$RC" ] || [ -x "$(cygpath -u "$RC" 2>/dev/null)" ]; } && WIRED_RESOLVE=1 ;;
  esac
fi
# Final Cut: the patched copy, the house-look cube and the splicekit MCP (setup-finalcut.sh). Which copy is the lane's
# is lanes/finalcut/doctor.py's call (never a glob's first match, lab-notes § 21): its exit 4 = no copy at the App
# Store Final Cut's version (an update came in), NOT wired: it needs the one click again.
fc_stale() {
  local rc=0
  have uv && [ -f "$ROOT/lanes/finalcut/doctor.py" ] || return 1
  uv run --quiet "$ROOT/lanes/finalcut/doctor.py" >/dev/null 2>&1 || rc=$?
  [ "$rc" -eq 4 ]
}
FC_STALE=0
if compgen -G "$HOME/Applications/SpliceKit/*.app" >/dev/null 2>&1 \
  && [ -f "$HOME/Library/Application Support/ProApps/Custom LUTs/house-Autumn-Rec709-80-120.cube" ] \
  && grep -qs '"splicekit"' "$ROOT/.mcp.json"; then
  if fc_stale; then FC_STALE=1; else WIRED_FINALCUT=1; fi
fi
# mcp-3: the recorded lane's ENGINE is behind this version's installer pin (a new version bumped it): re-run the
# installer (idempotent: it rebuilds only what changed). A missing build stamp counts as current, so an install
# from before the stamps is never told to reinstall.
stamp_behind() {    # stamp_behind <pin> <clone> <build stamp>: the checkout, or a build stamp that exists, is not the pin
  local head stamp
  [ -n "$1" ] || return 1
  head="$(git -C "$2" rev-parse HEAD 2>/dev/null)"; stamp="$(cat "$3" 2>/dev/null)"
  { [ -n "$head" ] && [ "$head" != "$1" ]; } || { [ -n "$stamp" ] && [ "$stamp" != "$1" ]; }
}
engine_behind() {   # engine_behind premiere|finalcut (Resolve's engine ships inside Resolve: nothing to pin)
  local want have
  case "$1" in
    premiere)
      want="$(grep -o 'PIN="[0-9a-f]*"' "$(lane_script setup-premiere.sh)" 2>/dev/null | head -n 1 | tr -cd '0-9a-f')"
      stamp_behind "$want" "$ROOT/vendor/premiere-mcp" "$ROOT/vendor/premiere-mcp/.built-from" ;;
    finalcut)
      want="$(sed -n 's/^SK_VERSION="\([0-9.]*\)".*/\1/p' "$(lane_script setup-finalcut.sh)" 2>/dev/null | head -n 1)"
      have="$(/usr/bin/defaults read /Applications/SpliceKit.app/Contents/Info CFBundleShortVersionString 2>/dev/null)"
      [ -n "$want" ] && [ -n "$have" ] && [ "$have" != "$want" ] \
        && [ "$(printf '%s\n%s\n' "$have" "$want" | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | head -n 1)" = "$have" ] ;;
    *) return 1 ;;
  esac
}

# approve_mcp <server>: pre-approve this project's own .mcp.json server in the machine-local settings, so the
# restart after wiring asks nothing (a "no" there is remembered and needed a reset). A settings file that
# does not parse is left alone.
approve_mcp() {
  local P; P="$(pybin)"; [ -n "$P" ] || return 0
  "$P" - "$ROOT/.claude/settings.local.json" "$1" <<'PY' || true
import json, os, sys
path, name = sys.argv[1], sys.argv[2]
d = {}
if os.path.exists(path):
    try:
        d = json.load(open(path, encoding='utf-8-sig'))
    except ValueError:
        sys.exit(0)
if not isinstance(d, dict):
    sys.exit(0)
on, off = d.get('enabledMcpjsonServers', []), d.get('disabledMcpjsonServers', [])
if not isinstance(on, list) or not isinstance(off, list):
    sys.exit(0)
if name in on and name not in off:
    sys.exit(0)
d['enabledMcpjsonServers'] = on + ([name] if name not in on else [])
if name in off:
    d['disabledMcpjsonServers'] = [x for x in off if x != name]
with open(path, 'w', encoding='utf-8') as fh:
    fh.write(json.dumps(d, indent=2) + '\n')
PY
}
wire() {  # wire premiere|resolve|finalcut → sets WIRED_NOW, WIRE_WAIT (the user's one click) or WIRE_FAILED
  case "$1" in
    premiere) label="Premiere Pro";    script=setup-premiere.sh ;;
    finalcut) label="Final Cut Pro";   script=setup-finalcut.sh ;;
    *)        label="DaVinci Resolve"; script=setup-resolve.sh ;;
  esac
  say "  ▸ wiring the $label lane (./$script)…"
  local rc=0
  bash "$(lane_script "$script")" || rc=$?
  if [ "$rc" -eq 0 ]; then WIRED_NOW="$1"
    case "$1" in premiere) approve_mcp premiere-pro ;; finalcut) approve_mcp splicekit ;; *) approve_mcp davinci-resolve ;; esac
  elif [ "$rc" -eq 4 ]; then WIRE_WAIT="$1"
  else say "  ⚠ $script failed; read its output above"; WIRE_FAILED="$1"; fi
}

WIRED_NOW=""; WIRE_FAILED=""; WIRE_WAIT=""; ASK_APP=0; LANE=""
if [ -z "$LANE_PICK" ]; then
  case "$REC_LANE" in
    premiere) [ "$WIRED_PREMIERE" -eq 1 ] && engine_behind premiere \
                && { say "  · the Premiere engine is behind this version's pin: rebuilding it"; wire premiere; } ;;
    finalcut) [ "$WIRED_FINALCUT" -eq 1 ] && engine_behind finalcut \
                && { say "  · SpliceKit is older than this version's: updating it"; wire finalcut; } ;;
  esac
fi
[ "$DET_CAPCUT" -eq 1 ] && say "  ✓ CapCut detected: nothing to install for it (its lane works out of the box)"
[ "$DET_PREMIERE" -eq 1 ] && [ "$WIRED_PREMIERE" -eq 1 ] && say "  ✓ Premiere Pro detected, lane already wired"
[ "$DET_RESOLVE"  -eq 1 ] && [ "$WIRED_RESOLVE"  -eq 1 ] && say "  ✓ DaVinci Resolve detected, lane already wired"
[ "$DET_FINALCUT" -eq 1 ] && [ "$WIRED_FINALCUT" -eq 1 ] && say "  ✓ Final Cut Pro detected, lane already wired"

if [ -n "$LANE_PICK" ]; then
  # The user's answer to the which-app question (or an explicit switch). Final.
  case "$LANE_PICK" in
    premiere|resolve|finalcut)
      if ! lane_ships "$LANE_PICK"; then
        say "  ✗ this package does not include the $LANE_PICK lane"; exit 1
      fi
      if { [ "$LANE_PICK" = premiere ] && [ "$WIRED_PREMIERE" -eq 1 ]; } || { [ "$LANE_PICK" = resolve ] && [ "$WIRED_RESOLVE" -eq 1 ]; } \
         || { [ "$LANE_PICK" = finalcut ] && [ "$WIRED_FINALCUT" -eq 1 ]; }; then
        say "  ✓ $LANE_PICK lane already wired; recorded as this machine's lane"
      else
        wire "$LANE_PICK"
      fi
      LANE="$LANE_PICK" ;;
    capcut)
      lane_ships capcut || { say "  ✗ this package does not include the capcut lane"; exit 1; }
      [ "$DET_CAPCUT" -eq 1 ] || say "  · CapCut is not installed (recording the pick anyway; install it before the first edit)"
      say "  ✓ CapCut recorded as this machine's lane (nothing to install)"
      LANE=capcut ;;
    chat-only)
      say "  ✓ chat-only finish recorded as this machine's lane (no editing app will be driven)"
      LANE=chat-only ;;
  esac
elif [ "$REC_LANE" = resolve ] && [ "$WIRED_RESOLVE" -eq 0 ] && [ "$DET_RESOLVE" -eq 1 ]; then
  # Recorded on the community engine retired 2026-10-05 (or unwired since): Blackmagic's own MCP takes over, or its
  # installer says why it cannot (a free edition, a Resolve older than 21.1).
  say "  · the Resolve lane now runs on Blackmagic's own MCP (Studio 21.1+): rewiring it"
  wire resolve; LANE=resolve
elif [ "$WIRED_PREMIERE" -eq 1 ] || [ "$WIRED_RESOLVE" -eq 1 ] || [ "$WIRED_FINALCUT" -eq 1 ]; then
  # A lane is wired: that is the lane. (Several wired: keep the recorded one, else Premiere, Resolve, Final Cut.)
  WIRED_LANES=""
  [ "$WIRED_PREMIERE" -eq 1 ] && WIRED_LANES="$WIRED_LANES premiere"
  [ "$WIRED_RESOLVE"  -eq 1 ] && WIRED_LANES="$WIRED_LANES resolve"
  [ "$WIRED_FINALCUT" -eq 1 ] && WIRED_LANES="$WIRED_LANES finalcut"
  case " $WIRED_LANES " in *" $REC_LANE "*) LANE="$REC_LANE" ;; *) set -- $WIRED_LANES; LANE="$1" ;; esac
  for a in $APPS; do
    case "$a" in
      premiere) [ "$WIRED_PREMIERE" -eq 0 ] && lane_ships premiere && say "  · Premiere Pro is also installed but not wired. That's fine; ./setup.sh --lane premiere switches to it (only if the user asks)." ;;
      resolve)  [ "$WIRED_RESOLVE"  -eq 0 ] && lane_ships resolve && say "  · DaVinci Resolve is also installed but not wired. That's fine; ./setup.sh --lane resolve switches to it (only if the user asks)." ;;
      finalcut) [ "$WIRED_FINALCUT" -eq 0 ] && lane_ships finalcut && say "  · Final Cut Pro is also installed but not wired. That's fine; ./setup.sh --lane finalcut switches to it (only if the user asks)." ;;
    esac
  done
elif [ "$REC_LANE" = capcut ] || [ "$REC_LANE" = chat-only ]; then
  # A pick that wires nothing, recorded on an earlier run: still the answer.
  say "  ✓ lane recorded earlier: $REC_LANE (./setup.sh --lane <app> switches, only if the user asks)"
  LANE="$REC_LANE"
elif [ "$FC_STALE" = 1 ] && [ "$REC_LANE" = finalcut ]; then
  say "  · Final Cut was updated: the patched copy needs the one click again"; wire finalcut; LANE=finalcut
elif [ "$N_APPS" -eq 0 ]; then
  say "  · no editing app detected: the chat-only pipeline is the finish (nothing to set up)"
  LANE=chat-only
elif [ "$N_APPS" -eq 1 ]; then
  case "$APPS" in
    capcut) LANE=capcut ;;
    *) say "  · $APPS is the only editing app installed, wiring it without asking"; wire "$APPS"; LANE="$APPS" ;;
  esac
else
  ASK_APP=1; LANE=pending
  say "  ? MULTIPLE editing apps detected: $APPS"
  if [ "$WRONG_FOLDER" -eq 0 ]; then
    PICKS="$(printf '%s' "$APPS" | sed 's/ / | /g')"
    say "    ACTION FOR CLAUDE: ask the user in ONE line which of these they edit in, then run"
    say "    ./setup.sh --lane <their pick>  ($PICKS; or chat-only if"
    say "    they would rather finish in chat). premiere/resolve/finalcut install that app's lane and"
    say "    end with a restart-Claude-Code step (finalcut first asks the user for one click in"
    say "    SpliceKit); capcut needs no install."
  fi
fi
[ -n "$WIRE_FAILED" ] && LANE=pending
[ -n "$WIRE_WAIT" ] && LANE=pending
[ "$LANE" = premiere ] && [ "$WIRED_PREMIERE" -eq 1 ] && approve_mcp premiere-pro
[ "$LANE" = resolve ] && [ "$WIRED_RESOLVE" -eq 1 ] && approve_mcp davinci-resolve
[ "$LANE" = finalcut ] && [ "$WIRED_FINALCUT" -eq 1 ] && approve_mcp splicekit
record_lane "$LANE"
[ -n "$WIRE_FAILED" ] && printf 'failed=%s\n' "$WIRE_FAILED" >> "$MARKER"
[ -n "$WIRE_WAIT" ] && printf 'wait=%s\n' "$WIRE_WAIT" >> "$MARKER"
# the toolchain the self-test passed on, for support and for the SessionStart hook (a version that changes since asks
# for ./setup.sh again); a lane installer's own rewrite of the marker drops it, and the next ./setup.sh writes it back
[ -f "$ROOT/workflows/selftest.py" ] && printf '%s\n' "$TOOLCHAIN" >> "$MARKER"

# ─── Updates: baseline this install in git (once; a re-run is a no-op) ───────
# update.py merges each new version into this folder without touching the user's changes; it needs to
# know the version installed, so record it now, before anything is customized. Never fatal: a folder
# that misses this is baselined by its first update instead. (Only in the package: the source repo has
# no update.py at its root.)
say ""
if [ -f "$ROOT/update.py" ]; then
  if have uv; then uv run update.py --init || say "  ⚠ updates not set up yet (read the line above); the first update does it"
  elif [ -n "$(pybin)" ]; then "$(pybin)" update.py --init || say "  ⚠ updates not set up yet (read the line above); the first update does it"
  fi
fi

# ─── Done ────────────────────────────────────────────────────────────────────
say ""
if [ -n "$WIRE_FAILED" ]; then
  say "== Tools done, but the $WIRE_FAILED lane FAILED to wire =="
  say "ACTION FOR CLAUDE: read the installer error above, fix it, then re-run"
  say "./setup.sh --lane $WIRE_FAILED (tools stay installed; the re-run skips them and retries the lane)."
  exit 1
fi
if [ -n "$WIRE_WAIT" ]; then
  say "== Tools done; the $WIRE_WAIT lane is waiting on ONE click from the user =="
  say "ACTION FOR CLAUDE: follow the installer's ACTION line above, and once the user says it is done,"
  say "re-run ./setup.sh --lane $WIRE_WAIT (tools stay installed; the re-run picks up where it stopped)."
  exit 1
fi
if [ -n "$WIRED_NOW" ]; then
  say "== Tools done + $WIRED_NOW lane wired (lane=$WIRED_NOW recorded in .setup-complete) =="
  [ "$WIRED_NOW" = premiere ] && say "First: quit Premiere Pro if it is open (it loads the new panel only when it launches)."
  say "Then RESTART Claude Code (quit it fully) and reopen the folder $ROOT_SHOW"
  say "so it loads the new MCP (already approved for this project; if Claude Code still asks"
  say "about the MCP servers, answer YES). Then say \"continue setup\"; Claude verifies"
  say "the $WIRED_NOW lane with you."
  say ""
  say "Optional, whenever you like: personalize the look/voice via brand-kit.md"
  say "(tell Claude \"apply my brand kit\"). The editor already works without it."
  exit 3
fi

if [ "$WRONG_FOLDER" -eq 1 ]; then
  say "== Setup done, but Claude Code is open on the wrong folder =="
  say "It has $CALLER_P open; the editor is $ROOT_SHOW, and its instructions and skills only load"
  say "there. ACTION FOR CLAUDE: tell the user to open that folder in Claude Code (File → Open Folder),"
  say "then say \"continue setup\"."
  exit 2
fi
if [ "${RENDER_FAILED:-0}" -eq 1 ]; then
  say "== Tools done, but the render engine is not ready =="
  say "ACTION FOR CLAUDE: it is usually the network: when it is back, re-run ./setup.sh (it skips everything"
  say "already done). Graphics cannot render until this passes."
  exit 1
fi
UNSEEN=""
for t in ffmpeg node uv; do have "$t" && ! session_sees "$t" && UNSEEN="$UNSEEN $t"; done
if [ -n "$UNSEEN" ]; then
  FP="$(printf '%s' "$ORIG_PATH" | cksum | cut -d' ' -f1)"
  ASKED="$(sed -n 1p .setup-restarted 2>/dev/null)"; LAST_FP="$(sed -n 2p .setup-restarted 2>/dev/null)"
  SAME="$(sed -n 3p .setup-restarted 2>/dev/null)"
  if [ "$FP" = "$LAST_FP" ]; then SAME=$(( ${SAME:-0} + 1 )); else SAME=0; ASKED=$(( ${ASKED:-0} + 1 )); fi
  printf '%s\n%s\n%s\n' "${ASKED:-1}" "$FP" "$SAME" > .setup-restarted
  if [ "$SAME" -ge 1 ] && [ "$SAME" -lt 2 ]; then
    say "== Claude Code has not been restarted yet (same environment as the last run) =="
    say "One step for you: QUIT Claude Code fully (Cmd+Q on a Mac, close it on Windows; a new chat is not"
    say "enough), reopen the folder $ROOT_SHOW and say \"continue setup\"."
    exit 2
  fi
  if [ "${ASKED:-1}" -ge 3 ] || [ "$SAME" -ge 2 ]; then
    say "✗ Claude Code still cannot see:$UNSEEN. They are installed; Claude Code's PATH lacks their folders:"
    for t in $UNSEEN; do
      d="$(dirname "$(command -v "$t")")"; command -v cygpath >/dev/null 2>&1 && d="$(cygpath -w "$d")"
      say "    $t → $d"
    done
    say "  ACTION FOR CLAUDE: add those folders to the user's PATH (Windows: the user PATH in Environment"
    say "  Variables; Mac: the shell profile Claude Code reads, ~/.zprofile and ~/.zshrc), then one more restart."
    printf '1\n\n0\n' > .setup-restarted
    exit 1
  fi
  say "== Setup done; one restart so Claude Code sees the tools it just installed:$UNSEEN =="
  say "One step for you: QUIT Claude Code fully (a new chat is not enough), reopen the folder $ROOT_SHOW"
  say "and say \"continue setup\". The re-run takes seconds; then drop a clip and say edit it."
  exit 2
fi
rm -f .setup-restarted .setup-restarts
if [ "$ASK_APP" -eq 1 ]; then
  say "== Tools done; one question left (the app pick above, Claude asks it) =="
else
  say "== Setup done (lane=$LANE) =="
  say "Drop a raw clip and tell Claude to edit it. First edit also downloads the"
  say "WhisperX speech model (~3-5 GB, one time)."
fi
say "Optional, whenever you like: personalize the look/voice via brand-kit.md"
say "(tell Claude \"apply my brand kit\"). The editor already works without it."
say "The editor folder is $ROOT_SHOW: if Claude Code's session folder is not exactly this one, tell the"
say "user to open this folder in Claude Code (File → Open Folder) before anything else."
if [ "$(ls -A "$ROOT/.." 2>/dev/null | grep -vxE '__MACOSX|\.DS_Store|desktop\.ini' | wc -l | tr -d ' ')" = 1 ] \
    && [ ! -f "$ROOT/../CLAUDE.md" ]; then
  PARENT_SHOW="$(cd "$ROOT/.." && pwd)"; command -v cygpath >/dev/null 2>&1 && PARENT_SHOW="$(cygpath -w "$PARENT_SHOW")"
  say "ACTION FOR CLAUDE: this folder sits alone inside $PARENT_SHOW, the way Windows' Extract All nests"
  say "it: if your session is open on that outer folder, the user must open $ROOT_SHOW itself now."
fi
