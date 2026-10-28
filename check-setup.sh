#!/usr/bin/env bash
# check-setup.sh — verify the tools the VIDEO-EDITOR pipeline needs (raw → exported cut).
#
# Report-only: checks what's installed and prints the install command for anything
# missing. Installs NOTHING and touches nothing. Run it once before editing.
#
#   ./check-setup.sh
#
# Cross-platform: macOS, Windows (native — runs in Git Bash, the shell Claude Code uses on
# Windows; see SETUP.md "Windows"), or plain Linux. The Python side (WhisperX large-v3 + torch)
# is NOT installed here — the rough-cut skill builds its own isolated venv on first run
# (~3–5 GB, several minutes).
set -uo pipefail

# ── platform detection ──────────────────────────────────────────────────────
UNAME="$(uname -s 2>/dev/null || echo unknown)"
case "$UNAME" in
  Darwin)               OS=mac;     OSLABEL="macOS" ;;
  Linux)                OS=linux;   OSLABEL="Linux" ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows; OSLABEL="Windows (Git Bash)" ;;
  *)                    OS=other;   OSLABEL="$UNAME" ;;
esac
IS_WSL=0
if [ "$OS" = linux ] && grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL=1; OSLABEL="Windows · WSL2 (works, but native Windows is the supported path — see SETUP.md)"
fi

# install-command hint for a given tool, per platform (bash 3.2-safe: case, no assoc arrays)
hint() {  # hint <tool-key>
  case "$OS:$1" in
    mac:ffmpeg)    echo "brew install ffmpeg" ;;
    mac:uv)        echo "brew install uv" ;;
    mac:node)      echo "brew install node" ;;
    mac:python3)   echo "brew install python" ;;
    mac:git)       echo "xcode-select --install" ;;
    linux:ffmpeg)  echo "sudo apt install -y ffmpeg" ;;
    linux:uv)      echo "curl -LsSf https://astral.sh/uv/install.sh | sh" ;;
    linux:node)    echo "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt install -y nodejs" ;;
    linux:python3) echo "sudo apt install -y python3 python3-pip" ;;
    linux:unzip)   echo "sudo apt install -y unzip" ;;
    linux:git)     echo "sudo apt install -y git" ;;
    windows:ffmpeg)  echo "winget install Gyan.FFmpeg          (then restart Claude Code)" ;;
    windows:uv)      echo "winget install astral-sh.uv         (then restart Claude Code)" ;;
    windows:node)    echo "winget install OpenJS.NodeJS.LTS    (then restart Claude Code)" ;;
    windows:python3) echo "winget install Python.Python.3.12   (then restart Claude Code)" ;;
    windows:git)     echo "winget install Git.Git             (then restart Claude Code)" ;;
    mac:ffmpeg-old)     if brew list ffmpeg >/dev/null 2>&1; then echo "brew upgrade ffmpeg"; else echo "brew install ffmpeg, and take the older one off PATH"; fi ;;
    windows:ffmpeg-old) echo "winget upgrade --id Gyan.FFmpeg -e   (or winget install Gyan.FFmpeg; then restart Claude Code)" ;;
    linux:ffmpeg-old)   echo "Ubuntu 22.04 and Debian 11 ship nothing newer: unpack BtbN's static ffmpeg-n7.1-latest-linux64-gpl-7.1.tar.xz (linuxarm64 on ARM) from https://github.com/BtbN/FFmpeg-Builds/releases and put its bin/ ahead of /usr/bin on PATH" ;;
    mac:mono-font)     echo "Menlo ships with macOS: restore /System/Library/Fonts/Menlo.ttc" ;;
    linux:mono-font)   echo "sudo apt install -y fonts-dejavu-core" ;;
    windows:mono-font) echo "Consolas ships with Windows: restore consolab.ttf in your Windows Fonts folder" ;;
    *:higgsfield)  echo "curl -fsSL https://raw.githubusercontent.com/higgsfield-ai/cli/main/install.sh | sh" ;;
    mac:yt-dlp)     echo "brew install yt-dlp" ;;
    linux:yt-dlp)   echo "uv tool install yt-dlp        (apt's build is too old for YouTube)" ;;
    windows:yt-dlp) echo "winget install yt-dlp.yt-dlp        (then restart Claude Code)" ;;
    *)             echo "install $1" ;;
  esac
}

if [ -t 1 ]; then
  G=$(tput setaf 2); R=$(tput setaf 1); Y=$(tput setaf 3); D=$(tput setaf 8); B=$(tput bold); N=$(tput sgr0)
else
  G=; R=; Y=; D=; B=; N=
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
missing=0

# The toolchain floors, as setup.sh holds them (packaging/test_setup_preflight.py keeps the two equal). ffmpeg's is the
# vocabulary manifest's `floor`: the oldest ffmpeg the shipped code runs on (aresample's ochl, alimiter's latency, 5.1).
UV_FLOOR="0.9.17"    # relative exclude-newer ("14 days"): every tool's package cooldown
NODE_FLOOR="22.12"   # the render engine's puppeteer-core declares node >=22.12
PY_FLOOR="3.10"      # the Command Line Tools' python3 is 3.9, past its end of life (2025-10)
FF_FLOOR="$(sed -n 's/^ *"floor": *"\([0-9.]*\)".*/\1/p' "$REPO/workflows/ffmpeg-vocab.json" 2>/dev/null | head -n 1)"
FF_FLOOR="${FF_FLOOR:-5.1}"
ver_ge() {   # ver_ge <have> <want>: dotted numbers, a missing part is 0; an empty <have> is never enough
  [ -n "$1" ] && awk -v a="$1" -v b="$2" 'BEGIN { na = split(a, x, "."); nb = split(b, y, "."); n = (na > nb) ? na : nb
    for (i = 1; i <= n; i++) { if (x[i] + 0 > y[i] + 0) exit 0; if (x[i] + 0 < y[i] + 0) exit 1 }; exit 0 }'
}
uv_route() {   # the command that upgrades the uv on PATH the way it was installed (setup.sh runs the same)
  local p; p="$(command -v uv 2>/dev/null)"
  case "$p" in
    "$HOME/.local/bin/"*|"$HOME/.cargo/bin/"*) echo "uv self update" ;;
    *[Ww]in[Gg]et*) echo "winget upgrade --id astral-sh.uv -e" ;;
    /opt/homebrew/*|/usr/local/*|/home/linuxbrew/*)
      if command -v brew >/dev/null 2>&1 && brew list uv >/dev/null 2>&1; then echo "brew upgrade uv"; else echo "uv self update"; fi ;;
    *) echo "pip install -U uv (with the pip that installed it)" ;;
  esac
}

check() {  # check <cmd> <label> <tool-key> <used-by>
  local cmd="$1" label="$2" key="$3" used="$4"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf "  ${G}✓${N} %-12s ${D}%s${N}\n" "$label" "$used"
  else
    printf "  ${R}✗${N} %-12s ${Y}%s${N}  ${D}(needed by %s)${N}\n" "$label" "$(hint "$key")" "$used"
    missing=$((missing + 1))
  fi
}

note() { printf "  ${Y}!${N} %-12s ${D}%s${N}\n" "$1" "$2"; }
ok()   { printf "  ${G}✓${N} %-12s ${D}%s${N}\n" "$1" "$2"; }
info() { printf "  ${D}·${N} %-12s ${D}%s${N}\n" "$1" "$2"; }

printf "\n${B}video-editor — prerequisites${N}  ${D}(%s)${N}\n\n" "$OSLABEL"

if [ "$OS" = other ]; then
  printf "  ${R}Unsupported shell/OS detected ($UNAME).${N}\n"
  printf "  ${Y}On Windows, run this from Git Bash (installed with Git for Windows), not PowerShell/cmd. See SETUP.md \"Windows\".${N}\n\n"
fi

# Package-manager preamble
if [ "$OS" = mac ] && ! command -v brew >/dev/null 2>&1; then
  # Homebrew lands in /opt/homebrew (Apple Silicon) or /usr/local (Intel), neither on the
  # default PATH — so "not on PATH" and "not installed" are different situations.
  BREW_OFF=""
  for b in /opt/homebrew/bin /usr/local/bin; do [ -x "$b/brew" ] && { BREW_OFF="$b"; break; }; done
  if [ -n "$BREW_OFF" ]; then
    printf "  ${Y}Homebrew is installed at %s but not on this shell's PATH${N} — ./setup.sh fixes that\n" "$BREW_OFF"
    printf "  ${D}(it adds Homebrew's shellenv line to your login profile); or run once:${N}  ${B}eval \"\$(%s/brew shellenv)\"${N}\n\n" "$BREW_OFF"
  else
    printf "  ${Y}Homebrew not found${N} — most installs below use it. Install it first, then re-run ./setup.sh (it finds the new Homebrew and puts it on PATH):\n"
    printf "    ${B}/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${N}\n\n"
  fi
elif [ "$OS" = linux ] && ! { command -v ffmpeg && command -v node && command -v uv; } >/dev/null 2>&1; then
  printf "  ${D}Installs below use apt. Refresh the index once first:${N}  ${B}sudo apt update${N}\n\n"
elif [ "$OS" = windows ] && ! { command -v ffmpeg && command -v node && command -v uv; } >/dev/null 2>&1; then
  printf "  ${D}Installs below use winget (built into Windows 11 / App Installer). After the installs,${N}\n"
  printf "  ${D}restart Claude Code once so it sees the new tools.${N}\n\n"
fi

printf "${B}Core${N} (the raw → exported pipeline — every job needs these):\n"
# The platform, read off uname -m, never assumed. A Mac needs Apple Silicon on macOS 15+: the only Macs Homebrew still
# builds its tools for (setup.sh stops before installing anywhere else), and an Intel Mac's WhisperX cannot import.
ARCH="$(uname -m 2>/dev/null)"
if [ "$OS" = mac ]; then
  MACOS="$(sw_vers -productVersion 2>/dev/null)"
  if [ "$ARCH" = arm64 ] && ver_ge "$MACOS" 15; then
    ok "platform" "macOS $MACOS · Apple Silicon ($ARCH)"
  elif [ "${VE_UNSUPPORTED_PLATFORM:-}" = 1 ]; then
    note "platform" "macOS ${MACOS:-?} · $ARCH: unsupported (Apple Silicon on macOS 15+ is); counted as a note only because VE_UNSUPPORTED_PLATFORM=1"
  else
    printf "  ${R}✗${N} %-12s ${Y}%s${N}\n" platform "macOS ${MACOS:-?} · $ARCH: the editor needs Apple Silicon on macOS 15 or newer (Homebrew builds its tools for nothing else; Apple Silicon: update macOS)"
    missing=$((missing + 1))
  fi
else
  info "platform" "$OSLABEL · $ARCH"
fi
# ffmpeg: present AND at the floor, named with its version, build and path (a second ffmpeg on PATH, winget's
# yt-dlp.FFmpeg git build beside Gyan's, is otherwise invisible). A git master build (N-…) is newer than any release.
if command -v ffmpeg >/dev/null 2>&1; then
  FF_RAW="$(ffmpeg -version 2>/dev/null | head -n 1 | awk '{print $3}')"
  case "$FF_RAW" in
    N-*|git-*) FF_NUM=""; FF_BUILD="a git master build" ;;
    *) FF_V="${FF_RAW#n}"; FF_NUM="$(printf '%s' "$FF_V" | sed -n 's/^\([0-9][0-9]*\(\.[0-9][0-9]*\)*\).*/\1/p')"
       FF_BUILD="${FF_V#"$FF_NUM"}"; FF_BUILD="${FF_BUILD#-}"; [ -n "$FF_NUM" ] || FF_BUILD="" ;;
  esac
  FF_SHOW="ffmpeg ${FF_NUM:-${FF_RAW:-?}}${FF_BUILD:+ ($FF_BUILD)} at $(command -v ffmpeg)"
  if [ -n "$FF_NUM" ] && ! ver_ge "$FF_NUM" "$FF_FLOOR"; then
    printf "  ${R}✗${N} %-12s ${Y}%s${N}\n" ffmpeg "$FF_SHOW is older than $FF_FLOOR, the oldest the editor runs on: $(hint ffmpeg-old)"
    missing=$((missing + 1))
  elif [ -z "$FF_NUM" ] && [ -z "$FF_BUILD" ]; then
    note "ffmpeg" "$FF_SHOW: its version could not be read (the editor needs $FF_FLOOR or newer)"
  else
    ok "ffmpeg" "$FF_SHOW — every audio/video pass: rough-cut, captions, music"
  fi
else
  check ffmpeg ffmpeg ffmpeg "every audio/video pass: rough-cut, captions, music"
fi
check ffprobe ffprobe ffmpeg  "duration/format probing"
if command -v uv >/dev/null 2>&1; then
  UV_V="$(uv --version 2>/dev/null | awk '{print $2}')"
  if [ -n "$UV_V" ] && ! ver_ge "$UV_V" "$UV_FLOOR"; then
    printf "  ${R}✗${N} %-12s ${Y}%s${N}\n" uv "uv $UV_V at $(command -v uv) is older than $UV_FLOOR, which every tool's package cooldown needs: $(uv_route)"
    missing=$((missing + 1))
  else
    ok "uv" "${UV_V:+$UV_V — }rough-cut builds the WhisperX transcribe venv; every tool runs through it (also gives uvx)"
  fi
else
  check uv uv uv "rough-cut — builds the WhisperX transcribe venv (also gives uvx)"
fi
check node    node    node    "graphics render engine — npx hyperframes"
check npx     npx     node    "runs the hyperframes CLI"
# git is probed by RUNNING it: on a Mac whose Command Line Tools are missing or broken (common after a macOS
# upgrade), /usr/bin/git is a stub that exists and fails.
if git --version >/dev/null 2>&1; then
  printf "  ${G}✓${N} %-12s ${D}%s${N}\n" git "updates — update.py merges each new version in without touching your changes"
else
  printf "  ${R}✗${N} %-12s ${Y}%s${N}  ${D}(needed by %s)${N}\n" git "$(hint git)" "updates (update.py)"
  missing=$((missing + 1))
fi

# Python — probed by RUNNING it, not command -v: Windows installs Python as `python`
# (no python3 name), and ships a fake `python3` Store stub that only opens the Microsoft
# Store. Every pipeline script uses this same python3-then-python probe.
PYBIN=""
if python3 -c '' >/dev/null 2>&1; then PYBIN=python3
elif python -c '' >/dev/null 2>&1; then PYBIN=python; fi
if [ -n "$PYBIN" ]; then
  PY_V="$("$PYBIN" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null)"
  if ver_ge "$PY_V" "$PY_FLOOR"; then
    ok "python" "$PY_V — the pipeline scripts (runs as \`$PYBIN\`)"
  else
    printf "  ${R}✗${N} %-12s ${Y}%s${N}  ${D}(needed by %s)${N}\n" "python" "$PYBIN is ${PY_V:-?} at $(command -v "$PYBIN"), the editor runs on $PY_FLOOR or newer: $(hint python3)$( [ "$OS" = mac ] && echo " (Homebrew's python3 must come before /usr/bin on PATH)")" "the pipeline scripts"
    missing=$((missing + 1))
  fi
else
  printf "  ${R}✗${N} %-12s ${Y}%s${N}  ${D}(needed by %s)${N}\n" "python" "$(hint python3)" "the pipeline scripts"
  missing=$((missing + 1))
fi

# node version: the render engine's packages declare node >= NODE_FLOOR. Below 22 it is a core miss; 22.0 to just
# under the floor still renders today, so it is a note, not a miss.
if command -v node >/dev/null 2>&1; then
  NODE_V="$(node -p 'process.versions.node' 2>/dev/null)"
  if [ "$OS" = mac ]; then
    if brew list node >/dev/null 2>&1; then up="brew upgrade node"; else up="brew install node"; fi
  else up="$(hint node)"; fi
  if ! ver_ge "$NODE_V" 22; then
    note "node version" "found v${NODE_V:-?} — HyperFrames wants node ≥ $NODE_FLOOR ($up)"
    missing=$((missing + 1))
  elif ! ver_ge "$NODE_V" "$NODE_FLOOR"; then
    note "node version" "found v$NODE_V — the render engine's packages declare node ≥ $NODE_FLOOR; it renders today, upgrade soon ($up)"
  fi
fi

# Linux: the render engine at the pin unzips its headless browser with the system `unzip` and has no
# fallback (a fresh WSL Ubuntu has none), so setup's one-time bootstrap fails without it.
[ "$OS" = linux ] && check unzip unzip unzip "the render engine's one-time browser download"

# The ffmpeg vocabulary (workflows/selftest.py): every option, filter, encoder and format the shipped code passes,
# probed on this ffmpeg. One ✗ there is one core miss here: a version string alone never caught a deleted option.
if [ -n "$PYBIN" ] && command -v ffmpeg >/dev/null 2>&1 && [ -f "$REPO/workflows/selftest.py" ]; then
  "$PYBIN" "$REPO/workflows/selftest.py" || missing=$((missing + 1))
fi

# Hardware is informational only: the pipeline auto-picks the fastest reliable
# path per machine (rough-cut's transcribe.sh does the same probe at run time,
# with a full runtime fallback to CPU), so nothing here can count as "missing".
printf "\n${B}Hardware${N}  ${D}(auto-detected; transcription picks the fastest reliable path)${N}:\n"
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  GPUNAME="$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n1)"
  # An existing WhisperX venv says what it was VERIFIED for (.mode, written from a torch
  # probe by transcribe.sh). A venv built CPU-only before this GPU was set up used to pass
  # as "runs CUDA" here while every transcription ran on CPU (2026-09-27).
  WXV="${VIDEO_EDITOR_WHISPERX_VENV:-$HOME/.cache/video-editor/whisperx-venv}"
  if [ -e "$WXV/.deps-ok" ] && [ "$(cat "$WXV/.mode" 2>/dev/null || echo cpu)" != cuda ]; then
    if [ -e "$WXV/.cuda-tried" ]; then
      note "GPU" "NVIDIA${GPUNAME:+ · $GPUNAME}, but CUDA torch did not take in the WhisperX venv: CPU (update the driver, then rm \"$WXV/.cuda-tried\")"
    else
      note "GPU" "NVIDIA${GPUNAME:+ · $GPUNAME}; the WhisperX venv is CPU-only: the next transcription upgrades it to CUDA in place (~3 GB, once)"
    fi
  else
    ok "GPU" "NVIDIA${GPUNAME:+ · $GPUNAME}: WhisperX runs CUDA float16 (automatic, with CPU fallback)"
  fi
elif [ "$OS" = mac ] && [ "$ARCH" = arm64 ]; then
  ok "GPU" "Apple Silicon: WhisperX runs CPU int8 (the reliable path; GPU torch is still flaky here)"
elif [ "$OS" = mac ]; then
  note "GPU" "an Intel Mac ($ARCH): WhisperX does not run here (see platform above)"
else
  ok "GPU" "no NVIDIA GPU: WhisperX runs CPU int8 (works everywhere, just slower)"
fi
# Smart App Control (Windows 11) checks a native file online the first time it loads and blocks a release too new
# to have reputation (numpy 2.5.4, 2026-10-13). Read only: the setting is the user's, never changed here.
if [ "$OS" = windows ]; then
  SAC_PRE="setup pre-checks the tools' files (workflows/sac-warm.py)"
  [ "$(cat .setup-sac-ok 2>/dev/null)" = "$(cat VERSION 2>/dev/null)" ] \
    || SAC_PRE="the tools' files are not pre-checked for this version yet: run ./setup.sh (or: uv run workflows/sac-warm.py)"
  case "$(MSYS2_ARG_CONV_EXCL='*' reg query 'HKLM\SYSTEM\CurrentControlSet\Control\CI\Policy' /v VerifiedAndReputablePolicyState 2>/dev/null | awk '/VerifiedAndReputablePolicyState/ {print $3}')" in
    0x1) info "SAC" "Smart App Control on: Python packages are locked to releases 14+ days old; $SAC_PRE" ;;
    0x2) info "SAC" "Smart App Control in evaluation (it may turn itself on): $SAC_PRE" ;;
    0x0) info "SAC" "Smart App Control off" ;;
  esac
fi

printf "\n${B}Fonts${N}  ${D}(bundled, plus one system font)${N}:\n"
# the Talking Head Explainer's caption mono (presets/instagram/talking-head-explainer/captions.py): probed in
# load_font()'s own order (SF Mono, then the bundled stand-in, then FALLBACK_MONO). A fallback is reported, not counted: captions.py draws
# in it and says so. NO mono at all is counted missing: captions.py then exits 2 ("no caption font") at step 5.
WINFONTS="${WINDIR:-C:/Windows}"; WINFONTS="${WINFONTS//\\//}/Fonts"
CAPMONO=""
for f in /System/Library/Fonts/Menlo.ttc "$WINFONTS/consolab.ttf" \
         /usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf /usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf; do
  if [ -f "$f" ]; then CAPMONO="$f"; break; fi
done
if [ -f /System/Library/Fonts/SFNSMono.ttf ]; then
  ok "caption mono" "SF Mono (/System/Library/Fonts/SFNSMono.ttf) — Talking Head Explainer captions"
elif [ -f "$REPO/assets/fonts/IBMPlexMono-Bold.ttf" ]; then
  ok "caption mono" "bundled stand-in: IBM Plex Mono Bold (assets/fonts/), drawn at SF Mono's advance and box, so every line and box is the locked size"
elif [ -n "$CAPMONO" ]; then
  ok "caption mono" "fallback: $(basename "$CAPMONO") — no SF Mono here, so captions.py draws in $CAPMONO and names it (not the locked look)"
else
  note "caption mono" "no SF Mono and no fallback mono (Menlo, Consolas or DejaVu Sans Mono Bold): Talking Head Explainer captions will fail. $(hint mono-font)"
  missing=$((missing + 1))
fi
if [ -f "$REPO/assets/fonts/Inter-Regular.otf" ]; then
  ok "Inter" "bundled in assets/fonts/ — the display fallback for every PIL/HTML builder"
else
  note "Inter" "missing from assets/fonts/ — graphics display font. Re-download from https://rsms.me/inter"
  missing=$((missing + 1))
fi
if [ "$OS" = mac ]; then
  if ls /Library/Fonts/SF-Pro-Display-*.otf >/dev/null 2>&1 || [ -f /System/Library/Fonts/SFNS.ttf ]; then
    ok "SF Pro (system)" "installed — used wherever a preset names it; bundled Inter stands in everywhere else"
  else
    note "SF Pro (system)" "not installed (optional) — bundled Inter stands in. Prefer SF Pro? https://developer.apple.com/fonts"
  fi
else
  ok "display font" "bundled Inter is the display font on $OSLABEL (SF Pro is macOS-only, not needed)"
fi

printf "\n${B}Bundled assets${N}  ${D}(shipped with the repo — nothing to download)${N}:\n"
# YuNet face detection — a HARD dep of chin-line.py (the low-band floor every long-form job
# measures) and face-frame.py (the Talking Head Explainer framing), so a miss counts against `missing`.
if [ -f "$REPO/assets/models/face_detection_yunet_2023mar.onnx" ]; then
  ok "face model" "assets/models/ — chin-line.py (low-band floor) + face-frame.py (Talking Head Explainer framing)"
else
  note "face model" "missing from assets/models/ — chin-line.py and face-frame.py need face_detection_yunet_2023mar.onnx"
  missing=$((missing + 1))
fi
# SFX + LUT libraries: advisory only. A job can be finished without either (hand-place the cut
# sheet, skip the Look), so neither may ever fail the core count.
if [ -d "$REPO/assets/sfx" ] && [ -n "$(ls "$REPO/assets/sfx" 2>/dev/null)" ]; then
  ok "SFX library" "assets/sfx/ — step 6 sound design"
else
  note "SFX library" "assets/sfx/ empty or absent — step 6 has nothing to place (hand-place, or restore the library)"
fi
# The grade Look is a Premiere-lane mechanic (grade-lut.py replays the .lookparams), so only
# mention it on a Premiere install — the lane is recorded in .setup-complete as `lane=`.
LANE=""
[ -f "$REPO/.setup-complete" ] && LANE="$(sed -n 's/^lane=//p' "$REPO/.setup-complete" | head -n1)"
if [ "$LANE" = premiere ] || [ -z "$LANE" ]; then
  if [ -f "$REPO/assets/luts/rec709/Autumn-Rec709.lookparams" ]; then
    ok "house Look" "assets/luts/rec709/Autumn-Rec709.lookparams — step 4 grade (Premiere lane)"
  else
    note "house Look" "Autumn-Rec709.lookparams absent — grade-lut.py cannot replay the house Look; apply it by hand"
  fi
fi

printf "\n${B}Optional${N} (only if you use the feature):\n"
# Optional items report with ok/note, NEVER with check(): check() increments the CORE
# missing counter, which made an all-green install report "1 core item(s) missing" and
# exit non-zero (breaking setup.sh's verify step) over a b-roll-only tool.
if [ ! -d "$REPO/.claude/skills/broll-gen" ]; then
  :   # AI b-roll (broll-gen) does not ship in this package: nothing to install for it
elif command -v higgsfield >/dev/null 2>&1; then
  ok "higgsfield" "AI b-roll (step 5b)"
else
  note "higgsfield" "not installed; only needed for AI b-roll: $(hint higgsfield)"
fi
# yt-dlp: pulling reference clips / YouTube research (creative-moves.md, Premiere lab-notes).
# Nothing in the pipeline calls it — it's a hand tool for sourcing edit material.
if command -v yt-dlp >/dev/null 2>&1; then
  ok "yt-dlp" "downloading reference clips + YouTube research"
else
  note "yt-dlp" "not installed; only needed to download reference clips: $(hint yt-dlp)"
fi
# Premiere finishing lane: the pinned vendored engine, installed by ./setup-premiere.sh.
# NEVER suggest the retired premiere-pro-mcp npm package (knockoff republish, broken CEP shim).
# Inside ./setup.sh (VE_SETUP_RUNNING=1) this check runs BEFORE the lane installer, so a
# missing engine is expected there and the note must not send the user to run it by hand.
# Inside ./setup.sh the lane block right after this check reports the lanes itself, and on a machine whose
# lane is recorded, another app's engine is not a to-do.
if [ -d "$(dirname "$0")/vendor/premiere-mcp" ]; then
  ok "premiere-mcp" "vendored engine present (Premiere finishing lane)"
elif [ -n "${VE_SETUP_RUNNING:-}" ]; then
  :
elif [ -n "$LANE" ] && [ "$LANE" != premiere ] && [ "$LANE" != pending ]; then
  info "premiere-mcp" "not installed; not needed on this machine (its lane is $LANE)"
elif [ -f "$REPO/setup.sh" ]; then
  info "premiere-mcp" "not installed; ./setup.sh --lane premiere installs it once Premiere is the pick"
else
  note "premiere-mcp" "not installed — the Premiere finishing lane needs it. Run: ./setup-premiere.sh"
fi
# Resolve finishing lane: Blackmagic's own ResolveMCP (inside Resolve Studio 21.1+) as .mcp.json's davinci-resolve
# entry, wired by ./setup-resolve.sh. A lane still on the retired community engine is reported by the drift check below.
if grep -q 'ResolveMCP' "$(dirname "$0")/.mcp.json" 2>/dev/null; then
  ok "davinci-resolve" "Blackmagic's ResolveMCP wired (Resolve finishing lane)"
elif [ -n "${VE_SETUP_RUNNING:-}" ] || [ "$LANE" = resolve ]; then
  :
elif [ -n "$LANE" ] && [ "$LANE" != pending ]; then
  info "davinci-resolve" "not wired; not needed on this machine (its lane is $LANE)"
elif [ -f "$REPO/setup.sh" ]; then
  info "davinci-resolve" "not wired; ./setup.sh --lane resolve wires it once Resolve is the pick (needs Studio 21.1+)"
else
  note "davinci-resolve" "not wired — the Resolve finishing lane needs Resolve Studio 21.1+. Run: ./setup-resolve.sh"
fi
# Final Cut finishing lane (macOS): SpliceKit's patched copy of Final Cut, the house-look cube and the splicekit
# MCP, installed by ./setup-finalcut.sh (the patch itself is one click in SpliceKit). Which copy is the lane's, and
# whether a stale copy or a Final Cut that is not the lane's copy is in the way, is lanes/finalcut/doctor.py's call
# (lab-notes § 21); its last line is the verdict.
if [ "$OS" = mac ] && [ -d "$(dirname "$0")/lanes/finalcut" ]; then
  if compgen -G "$HOME/Applications/SpliceKit/*.app" >/dev/null 2>&1 && grep -qs '"splicekit"' "$(dirname "$0")/.mcp.json" \
     && [ -f "$HOME/Library/Application Support/ProApps/Custom LUTs/house-Autumn-Rec709-80-120.cube" ]; then
    FC_RC=0
    FC_OUT="$(uv run --quiet "$(dirname "$0")/lanes/finalcut/doctor.py" 2>&1)" || FC_RC=$?
    FC_LINE="$(printf '%s\n' "$FC_OUT" | tail -n 1)"
    if [ "$FC_RC" -eq 0 ]; then
      ok "splicekit" "patched Final Cut + house LUT + MCP present (Final Cut finishing lane): ${FC_LINE#✓ Final Cut lane: }"
    else
      note "splicekit" "${FC_LINE#⚠ }"
      printf '%s\n' "$FC_OUT" | grep '^⚠' | sed '$d' | sed 's/^/                 /'
    fi
  elif [ "${VE_SETUP_RUNNING:-}" = 1 ]; then
    :
  elif [ -n "$LANE" ] && [ "$LANE" != finalcut ] && [ "$LANE" != pending ]; then
    info "splicekit" "not installed; not needed on this machine (its lane is $LANE)"
  elif [ "$LANE" = pending ] || ! compgen -G "/Applications/Final Cut Pro*.app" >/dev/null 2>&1; then
    info "splicekit" "not installed; ./setup.sh --lane finalcut installs it once Final Cut is the pick"
  elif [ -f "$REPO/setup.sh" ]; then
    info "splicekit" "not installed; ./setup.sh --lane finalcut installs it once Final Cut is the pick"
  else
    note "splicekit" "not installed — the Final Cut finishing lane needs it. Run: ./setup-finalcut.sh"
  fi
fi
# transcript-QA wordlist (the suspect scan in rough-cut). macOS ships one; minimal Ubuntu doesn't;
# Windows has no system wordlist, and scan-transcript.py brings its own there: the `english-words` package, a win32
# inline dependency uv installs on first use, carries the same web2 list (L23; this line said "skips" until 2026-09-27).
if [ -f /usr/share/dict/words ] || [ -f /usr/share/dict/web2 ] || [ -f /usr/share/dict/american-english ]; then
  ok "wordlist" "present — rough-cut transcript-QA suspect scan"
elif [ "$OS" = linux ]; then
  note "wordlist" "absent — transcript-QA scan will skip. Enable it: sudo apt install -y wamerican"
elif [ "$OS" = windows ]; then
  ok "wordlist" "bundled for Windows — the english-words package (web2), installed by uv on the first transcript-QA scan"
fi
# On macOS swift drives workflows/window-grab.sh (screenshot an editor window without fronting it), screen-record.sh
# and pii-scan.py (an inline Apple Vision OCR shim). On Windows the same three run through uv alone (wincap.py for
# the window, ocr_shim.py's RapidOCR for the text; 2026-09-27), so there is nothing to probe beyond uv.
if [ "$OS" = mac ]; then
  if command -v swift >/dev/null 2>&1; then
    ok "swift" "present — workflows/window-grab.sh + screen-record.sh (window capture / recording) + pii-scan.py (on-screen secret sweep)"
  else
    note "swift" "not installed — window-grab.sh, screen-record.sh and pii-scan.py need it. Install Xcode command line tools: xcode-select --install"
  fi
fi
# workflows/page-record.mjs (headless page captures for screen-rec cells) drives an installed Chrome or Chromium, else
# the renderer's own chrome-headless-shell (setup's `browser ensure` always installs it), else Edge on Windows.
if [ -n "${CHROME_PATH:-}" ] && [ -x "${CHROME_PATH}" ]; then
  ok "chrome" "CHROME_PATH set — workflows/page-record.mjs (headless page capture)"
elif [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ] || [ -x "/Applications/Chromium.app/Contents/MacOS/Chromium" ] \
  || [ -x "C:/Program Files/Google/Chrome/Application/chrome.exe" ] || command -v google-chrome >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1; then
  ok "chrome" "present — workflows/page-record.mjs (headless page capture)"
else
  ok "chrome" "no Google Chrome: page-record.mjs uses the renderer's headless shell"
fi

# Screen Studio (macOS) drives the OPT-IN capture route, workflows/screen-studio-take.mjs, when .env sets
# VE_SCREEN_RECORDER=screen-studio; reported when present, never counted missing (graphics-plan § THE CAPTURE GATE).
if [ "$OS" = mac ] && [ -d "/Applications/Screen Studio.app" ]; then
  if grep -qs '^VE_SCREEN_RECORDER=screen-studio' "$REPO/.env"; then
    ok "screen studio" "present, the capture route — workflows/screen-studio-take.mjs (VE_SCREEN_RECORDER=screen-studio in .env)"
  else
    ok "screen studio" "present — opt in to its capture route with VE_SCREEN_RECORDER=screen-studio in .env"
  fi
fi

# A skill in the user's own skills folder overrides the project's copy of the same name in every Claude Code session,
# and `npx hyperframes skills update` installs there, never into .claude/skills: one run shadows the pinned HyperFrames
# docs this version ships with whatever upstream had that day (D12, 2026-10-13). A note, never a miss.
SK_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
SHADOWED=""
if [ -f "$REPO/skills-lock.json" ] && [ -d "$SK_HOME" ]; then
  for sk in $(sed -n 's/^    "\([A-Za-z0-9._-]*\)": {$/\1/p' "$REPO/skills-lock.json" | tr -d '\r'); do
    [ -e "$SK_HOME/$sk" ] && SHADOWED="$SHADOWED $sk"
  done
fi
[ -z "$SHADOWED" ] || note "skills" "$SK_HOME holds personal copies of the pinned HyperFrames skills ($(printf '%s' "${SHADOWED# }" | sed 's/ /, /g')): they override .claude/skills/ in every session. Ask the user before moving them aside (never delete them)."

# ── version drift: checked BEFORE the verdict, so the verdict and the exit code agree ──
HF_WANT="$(grep -o 'HF_PIN="[0-9.]*"' "$REPO/setup.sh" 2>/dev/null | head -n 1 | tr -cd '0-9.')"
HF_BEFORE_WANT="$(sed -n 's/^HF_BEFORE="\([^"]*\)".*/\1/p' "$REPO/setup.sh" 2>/dev/null | head -n 1)"
HF_HAVE="$(cat "$REPO/.setup-hyperframes-ok" 2>/dev/null | tr -cd '0-9.')"
[ -f "$REPO/.setup-hyperframes-ok" ] && [ -z "$HF_HAVE" ] && HF_HAVE=0.8.16   # every setup before 2026.09.25.3
HF_DRIFT=0
if [ -f "$REPO/.setup-hyperframes-ok" ] && [ -n "$HF_WANT" ] && [ "$HF_HAVE" != "$HF_WANT" ]; then
  HF_DRIFT=1
  printf "  ${R}✗${N} ${B}Render engine${N} — set up for hyperframes@%s, this version needs %s: run ./setup.sh.\n" "$HF_HAVE" "$HF_WANT"
  missing=$((missing + 1))
fi
# The recorded lane's engine against this version's installer pin (client package only: the installers sit at
# its root). A missing build stamp counts as current, so an install from before the stamps is not told to reinstall.
pin_of() { grep -o 'PIN="[0-9a-f]*"' "$1" 2>/dev/null | head -n 1 | tr -cd '0-9a-f'; }
engine_drift() {   # engine_drift <label> <installer> <clone> <build stamp>
  local want head stamp have
  want="$(pin_of "$2")"; [ -n "$want" ] && [ -d "$3/.git" ] || return 0
  head="$(git -C "$3" rev-parse HEAD 2>/dev/null)"; stamp="$(cat "$4" 2>/dev/null)"
  have=""
  [ -n "$head" ] && [ "$head" != "$want" ] && have="$head"
  [ -z "$have" ] && [ -n "$stamp" ] && [ "$stamp" != "$want" ] && have="$stamp"
  if [ -n "$have" ]; then
    printf "  ${R}✗${N} ${B}%s${N} — %s, this version needs %s: run ./setup.sh\n" "$1" "$(printf '%s' "$have" | cut -c1-7)" "$(printf '%s' "$want" | cut -c1-7)"
    missing=$((missing + 1))
  fi
}
case "$LANE" in
  premiere)
    [ -f "$REPO/setup-premiere.sh" ] && engine_drift "Premiere engine is" "$REPO/setup-premiere.sh" \
      "$REPO/vendor/premiere-mcp" "$REPO/vendor/premiere-mcp/.built-from" ;;
  resolve)
    if [ -f "$REPO/setup-resolve.sh" ] && ! grep -qs 'ResolveMCP' "$REPO/.mcp.json"; then
      printf "  ${R}✗${N} ${B}Resolve engine${N} — not Blackmagic's ResolveMCP (the community engine is retired): run ./setup.sh\n"
      missing=$((missing + 1))
    fi ;;
  finalcut)
    SK_WANT="$(sed -n 's/^SK_VERSION="\([0-9.]*\)".*/\1/p' "$REPO/setup-finalcut.sh" 2>/dev/null | head -n 1)"
    SK_HAVE="$(/usr/bin/defaults read /Applications/SpliceKit.app/Contents/Info CFBundleShortVersionString 2>/dev/null)"
    if [ -n "$SK_WANT" ] && [ -n "$SK_HAVE" ] && [ "$SK_HAVE" != "$SK_WANT" ]; then
      if [ "$(printf '%s\n%s\n' "$SK_HAVE" "$SK_WANT" | sort -t. -k1,1n -k2,2n -k3,3n -k4,4n | head -n 1)" = "$SK_HAVE" ]; then
        printf "  ${R}✗${N} ${B}SpliceKit${N} — %s, this version needs %s: run ./setup.sh\n" "$SK_HAVE" "$SK_WANT"
        missing=$((missing + 1))
      else
        note "SpliceKit" "$SK_HAVE is newer than the $SK_WANT the lane was proven on (fine; not downgraded)"
      fi
    fi ;;
esac

printf "\n"
if [ "$missing" -eq 0 ]; then
  printf "${G}${B}Core tools present.${N} You're ready to edit.\n"
else
  printf "${R}${B}%d core item(s) missing.${N} Run the commands shown above, then re-run this script.\n" "$missing"
fi

printf "\n${B}One-time, on first use${N} (happens automatically / once):\n"
WXV="${VIDEO_EDITOR_WHISPERX_VENV:-$HOME/.cache/video-editor/whisperx-venv}"
WX_LOCK="$REPO/.claude/skills/rough-cut/scripts/whisperx-requirements.txt"
if [ -e "$WXV/.deps-ok" ] && [ -f "$WX_LOCK" ] \
   && [ "$(cat "$WXV/.deps-ok" 2>/dev/null)" != "lock $(cksum < "$WX_LOCK" | awk '{print $1, $2}')" ]; then
  # transcribe.sh stamps .deps-ok with the lock it built from; a new lock rebuilds the venv once, on the next transcription
  printf "  ${D}•${N} ${B}WhisperX transcription${N} — the next transcription rebuilds its venv from this version's lock (several minutes, several GB; on Windows the CUDA torch download follows). Once.\n"
elif [ -e "$WXV/.deps-ok" ] && [ -f "$WX_LOCK" ]; then
  # stamped from this lock: built and import-proven by transcribe.sh, nothing left to do once
  printf "  ${G}✓${N} ${B}WhisperX transcription${N} — its venv is built from this version's lock and ready.\n"
else
  printf "  ${D}•${N} ${B}WhisperX transcription${N} — rough-cut builds its venv + downloads large-v3 (~3–5 GB) on the first edit. Needs network + a few minutes. One time.\n"
fi
if [ "$HF_DRIFT" -eq 1 ]; then
  :   # named above, before the verdict
elif [ -f "$REPO/.setup-hyperframes-ok" ]; then
  printf "  ${G}✓${N} ${B}Render engine${N} — bootstrapped (hyperframes@${HF_HAVE:-0.8.105}, pinned to the version the locked presets were built against).\n"
else
  # setup.sh only exists in a client package (packaging/overlay/ writes it) — in the source
  # repo the bare command IS the bootstrap, so don't point at a script that isn't here.
  if [ -f "$REPO/setup.sh" ]; then BOOT="./setup.sh does it; by hand, once from the project root:"; else BOOT="run once from the project root:"; fi
  printf "  ${D}•${N} ${B}Render engine bootstrap${N} — %s  ${B}npm_config_before=${HF_BEFORE_WANT:-2026-10-01T23:59:59Z} npx -y hyperframes@${HF_WANT:-0.8.105} browser ensure${N}  (downloads the headless browser the graphics renderer uses; pinned to the version the locked presets were built against).\n" "$BOOT"
  if [ "$OS" = linux ]; then
    printf "      ${D}On Linux and WSL, if it stops on 'no zip archiver' or a missing shared library, install unzip and the headless-Chrome deps it names, e.g.:${N}\n"
    printf "      ${B}sudo apt install -y unzip libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2t64${N}\n"
  fi
fi
if [ -f "$REPO/brand-kit.md" ] && ! grep -q '<<YOUR_NAME>>' "$REPO/brand-kit.md"; then
  printf "  ${G}✓${N} ${B}Brand${N}: brand-kit.md is filled in (after a change to it or to a preset, say \"apply my brand kit\").\n\n"
elif [ -f "$REPO/brand-kit.md" ]; then
  printf "  ${D}•${N} ${B}Brand${N} (optional): the editor works out of the box with the bundled neutral look. Whenever you want captions and graphics to carry YOUR brand, fill in ${B}brand-kit.md${N} (see SETUP.md).\n\n"
else
  printf "  ${D}•${N} ${B}Brand${N} (optional): client packages ship a ${B}brand-kit.md${N} to fill in; in this tree the brand lives in CLAUDE.md and the presets.\n\n"
fi

[ "$missing" -eq 0 ]
