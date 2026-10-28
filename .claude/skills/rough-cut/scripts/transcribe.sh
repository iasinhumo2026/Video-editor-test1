#!/usr/bin/env bash
# transcribe.sh — runs WhisperX (large-v3 + wav2vec2 forced alignment) on every clip in a job folder
# usage: transcribe.sh <job_dir> [--diarize] [--force] [--chunk-size N] [--vad-onset X --vad-offset Y]
# output: <job_dir>/transcript/words.json  (durable canonical — transcribe ONCE, reuse forever;
#         /tmp/video-editor/<job-name>/ is just render scratch)
#
# standalone: transcribe.sh --file <audio|video> --out <words.json> [--diarize] [--chunk-size N] [--vad-...]
#   One file in (a pickup re-record, a spliced audio), the same words.json shape out at --out.
#   It never reads or writes a job's transcript/: no canonical, no reuse, always transcribes.
#
# One transcription runs at a time per machine: a second run (a batch launched all at once) waits its turn and
# says for whom (take_run_lock, below).
#
# --diarize adds speaker labels per word (requires HUGGINGFACE_TOKEN in env or in the repo-root .env;
# pyannote/speaker-diarization-community-1, the model whisperx 3.8 loads, must be accepted on Hugging Face).
#
# A second voice on a phone speaker (about 10 dB under the host) goes missing from the text, and
# wav2vec2 then force-fits the host's next words over its window. Two knobs, both unset = WhisperX's
# own defaults, both apply only to a fresh transcription (a reuse of the canonical refuses them),
# and neither is a fix (measured on the three reference phone-call jobs, 2026-09-23): each moves WHERE Whisper
# drops the quiet voice, so `cut-audit.py --coverage` still gates and realign-spans.py still repairs.
#   --chunk-size N (env WHISPERX_CHUNK_SIZE; 1-30 s, default 30) caps how much VAD-merged speech
#     Whisper decodes as one window. Where the VAD FOUND the AI's lines and Whisper dropped them
#     inside a 30 s window shared with the louder host, 20 recovered them; on a whole 53-minute
#     call it dropped other AI lines the default had kept. Below 20 it invented words in room tone.
#   --vad-onset X --vad-offset Y (env VAD_ONSET / VAD_OFFSET) set the pyannote speech thresholds,
#     together, offset <= onset (defaults 0.500 / 0.363), for a voice the VAD itself scores low.
# The flags win over the env.

set -euo pipefail
ORIG_ARGS=("$@")   # a Smart App Control retry re-runs this script with them (sac_reresolve, below)

# Windows pipes default python stdio to cp1252, which can't encode the ⚠/→ glyphs in the
# long-span warnings (or huggingface's progress output), so force UTF-8 everywhere.
# Windows without Developer Mode also denies os.symlink (WinError 1314): a real first-run
# large-v3 download crashed on that (2026-08-13). HF_HUB_DISABLE_SYMLINKS makes
# huggingface_hub copy instead of symlink, but treat it as belt-and-suspenders, NOT the
# proven fix: whisperx pins huggingface-hub <1.0, which never reads this var (only hub
# >=1.0 does). 1314 recurred on a fresh no-Developer-Mode box (2026-10-13) and the traceback
# found the real site: hub <1.0's symlink-support check races the large-v3 snapshot's parallel
# downloads, so the copy-degrade never engages for the first files. The cure is in the Python
# block below (it answers "no symlinks" up front). Windows-only; costs disk, never
# correctness. No-ops on macOS/Linux.
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) export HF_HUB_DISABLE_SYMLINKS=1 ;; esac

# ─ Hardware auto-detect: an NVIDIA GPU (Windows/Linux) runs WhisperX on CUDA,
# several times faster than CPU. Apple Silicon stays CPU int8 (the lock: MPS
# torch is still flaky for some ops; CPU is slower but never silently wrong).
# WHISPERX_DEVICE=cpu|cuda overrides the auto-pick. The python side runs a full
# fallback ladder (cuda float16 → cuda int8_float16 → cpu int8), so a broken
# CUDA stack degrades to CPU with a warning; it can never block an edit.
GPU=0
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then GPU=1; fi
DEVICE="${WHISPERX_DEVICE:-}"
if [ -z "$DEVICE" ]; then
  if [ "$GPU" -eq 1 ]; then DEVICE=cuda; else DEVICE=cpu; fi
fi

USAGE="usage: transcribe.sh <job_dir> [--diarize] [--force] [--chunk-size N] [--vad-onset X --vad-offset Y]
       transcribe.sh --file <audio|video> --out <words.json> [--diarize] [--chunk-size N] [--vad-onset X --vad-offset Y]"
JOB_DIR=""
case "${1:-}" in
  --file|--out) ;;
  *) JOB_DIR="${1:?$USAGE}"; shift ;;
esac

DIARIZE=0
FORCE=0
FILE=""
OUT=""
CHUNK_SIZE="${WHISPERX_CHUNK_SIZE:-}"
VAD_ONSET="${VAD_ONSET:-}"
VAD_OFFSET="${VAD_OFFSET:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --diarize) DIARIZE=1 ;;
    --force)   FORCE=1 ;;
    --file)       FILE="${2:?--file needs a path}"; shift ;;
    --out)        OUT="${2:?--out needs a path}"; shift ;;
    --chunk-size) CHUNK_SIZE="${2:?--chunk-size needs a value}"; shift ;;
    --vad-onset)  VAD_ONSET="${2:?--vad-onset needs a value}"; shift ;;
    --vad-offset) VAD_OFFSET="${2:?--vad-offset needs a value}"; shift ;;
    *) echo "unknown flag: $1" >&2; exit 1 ;;
  esac
  shift
done

# Whisper hears 30 s at a time: a longer window would be cut short, so 30 is the ceiling.
if [ -n "$CHUNK_SIZE" ]; then
  if ! [[ "$CHUNK_SIZE" =~ ^[0-9]+$ ]] || [ "$CHUNK_SIZE" -lt 1 ] || [ "$CHUNK_SIZE" -gt 30 ]; then
    echo "--chunk-size is whole seconds from 1 to 30, got '$CHUNK_SIZE'" >&2; exit 1
  fi
fi

# The two thresholds go together: an onset lowered alone under the default offset (0.363)
# would close every speech region on the frame after it opens.
if [ -n "$VAD_ONSET$VAD_OFFSET" ]; then
  if [ -z "$VAD_ONSET" ] || [ -z "$VAD_OFFSET" ]; then
    echo "--vad-onset and --vad-offset (VAD_ONSET / VAD_OFFSET) are set together" >&2; exit 1
  fi
  for v in "$VAD_ONSET" "$VAD_OFFSET"; do
    [[ "$v" =~ ^0?\.[0-9]+$ ]] || { echo "a VAD threshold is a fraction like 0.3, got '$v'" >&2; exit 1; }
  done
  awk -v on="$VAD_ONSET" -v off="$VAD_OFFSET" 'BEGIN { exit !(off + 0 <= on + 0) }' \
    || { echo "--vad-offset ($VAD_OFFSET) must not exceed --vad-onset ($VAD_ONSET)" >&2; exit 1; }
fi

if [ -n "$FILE$OUT" ]; then
  # Standalone form: never a job folder's transcript/, so nothing canonical is read or replaced.
  if [ -n "$JOB_DIR" ] || [ -z "$FILE" ] || [ -z "$OUT" ]; then echo "$USAGE" >&2; exit 1; fi
  [ -f "$FILE" ] || { echo "no such file: $FILE" >&2; exit 1; }
  FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"
  mkdir -p "$(dirname "$OUT")"
  OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
  WORK="/tmp/video-editor/transcribe-file"
  mkdir -p "$WORK"
  CLIPS=("$FILE")
  PY_OUT="$OUT"
else
  JOB_DIR="$(cd "$JOB_DIR" && pwd)"
  JOB_NAME="$(basename "$JOB_DIR")"
  MEDIA_DIR="$JOB_DIR"
  [ -d "$JOB_DIR/raw" ] && MEDIA_DIR="$JOB_DIR/raw"
  WORK="/tmp/video-editor/$JOB_NAME"
  CANON="$JOB_DIR/transcript/words.json"   # persisted canonical transcript — transcribe ONCE, reuse forever
  mkdir -p "$WORK" "$JOB_DIR/transcript"

  # Transcribe ONCE. WhisperX large-v3 is slow + deterministic, so a persisted canonical
  # transcript wins unless --force. This is the single source of truth for the whole
  # pipeline (rough cut AND finishing captions) — nothing else transcribes this footage.
  if [ "$FORCE" -eq 0 ] && [ -f "$CANON" ]; then
    if [ -n "$VAD_ONSET$CHUNK_SIZE" ]; then
      # A reuse would silently drop the settings the caller asked for.
      echo "[transcribe] $CANON exists: --chunk-size / the VAD thresholds apply only to a fresh transcription;" >&2
      echo "[transcribe]   add --force to re-transcribe with them, or unset them to reuse it" >&2
      exit 1
    fi
    echo "[transcribe] reusing canonical transcript $CANON (pass --force to re-transcribe)" >&2
    cp "$CANON" "$WORK/words.json"
    echo "$WORK/words.json"
    exit 0
  fi

  shopt -s nullglob nocaseglob
  CLIPS=("$MEDIA_DIR"/*.mov "$MEDIA_DIR"/*.mp4 "$MEDIA_DIR"/*.mkv "$MEDIA_DIR"/*.m4v)
  shopt -u nocaseglob
  if [ ${#CLIPS[@]} -eq 0 ]; then
    echo "no clips found in $MEDIA_DIR" >&2
    exit 1
  fi
  PY_OUT="$WORK/words.json"
fi

# Persistent venv: built once, reused every run. whisperx pulls torch, so it
# gets its own box — it can't share the faster-whisper venv (different deps).
VENV="${VIDEO_EDITOR_WHISPERX_VENV:-$HOME/.cache/video-editor/whisperx-venv}"
# venv layout differs by OS: bin/python (macOS/Linux) vs Scripts/python.exe (Windows)
venv_py() { if [ -e "$VENV/Scripts/python.exe" ]; then echo "$VENV/Scripts/python.exe"; else echo "$VENV/bin/python"; fi; }

# ONE TRANSCRIPTION AT A TIME per WhisperX venv, on every machine (2026-10-14). On Apple Silicon WhisperX runs on the
# CPU, and a batch started in parallel (a member's fifty sales calls) held every core until Premiere fell over; on any
# OS two runs would also race the venv build below (rm -rf, then rebuild). A CUDA box waits too: one large-v3 run at
# batch 16 already keeps the GPU busy, and a second on a smaller card runs out of memory, where the ladder drops it to
# the CPU. The lock is a directory (mkdir is atomic on every OS) holding its owner's pid and what it transcribes. A
# run killed before its EXIT trap leaves it behind, and the next run takes it over once that pid is gone (kill -0);
# a lock with no owner written is stale after a minute. Breaking one goes through a second mkdir, so two waiters never
# both break it (the slower one would delete the faster one's fresh lock). A reuse of the canonical never gets here.
RUN_LOCK="${VENV}.lock"
lock_owner() { cat "$RUN_LOCK/owner" 2>/dev/null || true; }
drop_run_lock() { rm -f "$RUN_LOCK/owner"; rmdir "$RUN_LOCK" 2>/dev/null || true; }   # it only ever holds `owner`
take_run_lock() {
  local owner pid seen=""
  mkdir -p "$(dirname "$RUN_LOCK")"
  while ! mkdir "$RUN_LOCK" 2>/dev/null; do
    owner="$(lock_owner)"; pid="${owner%% *}"
    # this run itself, re-executed after a Smart App Control block (exec keeps the pid)
    if [ -n "$pid" ] && [ "$pid" = "$$" ]; then return 0; fi
    if { [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; } || \
       { [ -z "$owner" ] && [ -n "$(find "$RUN_LOCK" -maxdepth 0 -mmin +1 2>/dev/null)" ]; }; then
      if mkdir "$RUN_LOCK.break" 2>/dev/null; then
        if [ "$(lock_owner)" = "$owner" ]; then
          drop_run_lock
          echo "[transcribe] · took over the lock of a transcription that is gone (${owner:-no owner written})" >&2
        fi
        rmdir "$RUN_LOCK.break" 2>/dev/null || true
        continue
      fi
      find "$RUN_LOCK.break" -maxdepth 0 -mmin +1 -exec rmdir {} \; 2>/dev/null || true   # a breaker killed mid-break
    fi
    if [ -n "$owner" ] && [ "$owner" != "$seen" ]; then
      echo "[transcribe] waiting: one transcription runs at a time on this machine, and pid $pid is transcribing" \
           "${owner#* } (lock: $RUN_LOCK)" >&2
      seen="$owner"
    fi
    sleep 2
  done
  printf '%s %s\n' "$$" "${FILE:-$JOB_DIR}" > "$RUN_LOCK/owner"
}
release_run_lock() { if [ "$(lock_owner)" = "$$ ${FILE:-$JOB_DIR}" ]; then drop_run_lock; fi; }
take_run_lock
trap release_run_lock EXIT
# The venv is EXACTLY whisperx-requirements.txt, beside this script: whisperx==3.8.6 and everything under it, compiled
# for Python 3.11 on macOS arm64, Windows x64 and Linux x64 (its header holds the command that regenerates it;
# onnxruntime is held under 1.24, whose wheels skip macOS 13, a Mac an unpinned resolve had simply stepped around).
# An unpinned `whisperx` moved its API under every fresh client (3.8 dropped the top-level DiarizationPipeline and
# use_auth_token, so --diarize crashed), and .deps-ok meant an older venv never moved at all (2026-10-13).
LOCK="$(cd "$(dirname "$0")" && pwd)/whisperx-requirements.txt"
STAMP="lock $(cksum < "$LOCK" | awk '{print $1, $2}')"
# .deps-ok holds the lock's checksum and is written only after the venv is installed AND imports: a half-built venv
# (install interrupted once) self-heals on the next run, and a venv built from another lock (or before one) is
# rebuilt once
if [ "$(cat "$VENV/.deps-ok" 2>/dev/null)" != "$STAMP" ]; then
  if [ -e "$VENV/.deps-ok" ]; then
    echo "[transcribe] whisperx-requirements.txt changed since this venv was built: rebuilding it from the lock (once, ~minutes)" >&2
  else
    echo "[transcribe] first-run: building whisperx venv at $VENV (pulls torch, ~minutes)" >&2
  fi
  rm -rf "$VENV"
  # Windows: materialize the managed interpreter BEFORE creating the venv. `uv venv
  # --python 3.11` can trigger a just-in-time CPython download whose junction/trampoline
  # finalization races the venv creation and yields a broken venv (hit on a real machine,
  # 2026-08-13). A separate install step is idempotent and instant when already present.
  # Its output goes to a log: on a healthy box it still prints "Missing expected target
  # directory for Python minor version link" (a client box, 2026-09-07), which reads as an
  # error to someone watching the first run and is nothing; the venv step is the real check.
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*)
    echo "[transcribe] ensuring a managed Python 3.11 (uv; log: $WORK/uv-python-install.log)" >&2
    uv python install 3.11 >"$WORK/uv-python-install.log" 2>&1 \
      || echo "[transcribe] · uv python install 3.11 reported a problem (see the log); the venv step below is the real check" >&2
    ;;
  esac
  if ! uv venv "$VENV" --python 3.11 >&2; then
    echo "[transcribe] venv creation failed; retrying once from clean" >&2
    rm -rf "$VENV"
    uv venv "$VENV" --python 3.11 >&2
  fi
  # the lock was compiled from releases at least two weeks old, like every PEP 723 header: Windows Smart App Control
  # blocks a binary too new to have reputation (numpy 2.5.4 three days after release, 2026-10-13)
  uv pip sync --python "$(venv_py)" "$LOCK" >&2
  # PROVE it imports before .deps-ok says so (numpy against the torch it was built for, too). Twice: Smart App
  # Control's first look at a new native file can fail as a block that the second load passes (below)
  PROBE='import whisperx, torch, numpy; torch.from_numpy(numpy.zeros(1))'
  if ! "$(venv_py)" -c "$PROBE" >&2 && ! "$(venv_py)" -c "$PROBE" >&2; then
    echo "[transcribe] ✗ the new WhisperX venv at $VENV does not import (above); it is rebuilt on the next run" >&2
    exit 1
  fi
  # record what this venv was VERIFIED for; the CUDA step below upgrades it in place
  echo cpu > "$VENV/.mode"
  echo "$STAMP" > "$VENV/.deps-ok"
fi

# cuda_torch: make this venv's torch a CUDA build and PROVE it, writing .mode from the
# probe. Used on a fresh build AND to repair a venv that exists but is CPU-only on a GPU
# machine (a venv built before GPU support, or while no GPU was visible): that case used
# to print "rm -rf the venv and re-run" and carry on at CPU speed, so an RTX 5070 box
# with an August venv transcribed on CPU with the GPU reported ready by check-setup
# (2026-09-27). The repair keeps the venv, whisperx and the downloaded models; only
# torch/torchaudio are swapped (~3 GB). A repair that fails leaves .cuda-tried so it is
# not re-attempted (and re-downloaded) on every run; delete that file to retry.
cuda_torch() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      # PyPI torch on Windows is CPU-only; swap in the CUDA build (Linux PyPI
      # wheels already ship CUDA, so only Windows needs this). cu128 wheels
      # want a current NVIDIA driver (and are the first to run Blackwell, RTX 50xx);
      # if this install or the runtime probe fails, everything falls back to CPU
      # and the edit still runs.
      #
      # whisperx installed the CPU torch, and a plain `uv pip install torch
      # --index-url <cu128>` on top is a NO-OP: the requirement is already satisfied,
      # so uv never consults the CUDA index, exits 0 ("Checked 2 packages"), and the
      # venv keeps CPU torch while .mode said cuda (a client RTX 3060 ran CPU-only for
      # exactly that, 2026-09-07). Force the reinstall, pinned to the versions whisperx
      # resolved so torchvision/torchcodec, ABI-matched to that torch, keep working.
      echo "[transcribe] NVIDIA GPU detected: installing CUDA torch (~3 GB, once)" >&2
      read -r -a TORCH_PINS <<< "$("$(venv_py)" -c 'import torch, torchaudio; print("torch==" + torch.__version__.split("+")[0], "torchaudio==" + torchaudio.__version__.split("+")[0])' 2>/dev/null || echo "torch torchaudio")"
      uv pip install --python "$(venv_py)" \
          --reinstall-package torch --reinstall-package torchaudio "${TORCH_PINS[@]}" \
          --index-url https://download.pytorch.org/whl/cu128 >&2 \
        || echo "[transcribe] ⚠ CUDA torch install failed (read the uv output above)" >&2
      ;;
  esac
  # .mode is written from a PROBE, never from intent: the install's exit code proves
  # nothing (above). A venv that says cuda but holds CPU torch would request CUDA and
  # the python ladder would quietly drop to CPU on every run.
  if "$(venv_py)" -c 'import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)' 2>/dev/null; then
    echo "[transcribe] ✓ CUDA verified: $("$(venv_py)" -c 'import torch; print(torch.__version__, "on", torch.cuda.get_device_name(0))' 2>/dev/null)" >&2
    echo cuda > "$VENV/.mode"
    rm -f "$VENV/.cuda-tried"
    return 0
  fi
  echo "[transcribe] ⚠ CUDA did not take (torch.cuda.is_available() is False); this venv stays CPU-only." >&2
  echo "[transcribe]   Transcription works, several times slower. GPU retry: rm \"$VENV/.cuda-tried\" and re-run" >&2
  echo "[transcribe]   (an NVIDIA driver too old for cu128 is the usual cause; update it first)." >&2
  echo cpu > "$VENV/.mode"
  touch "$VENV/.cuda-tried"
  return 1
}
if [ "$DEVICE" = cuda ] && [ "$(cat "$VENV/.mode" 2>/dev/null || echo cpu)" != "cuda" ]; then
  if [ -e "$VENV/.cuda-tried" ]; then
    echo "[transcribe] · CUDA requested, but this venv's CUDA torch did not take on an earlier try: CPU." >&2
    echo "[transcribe]   GPU retry: rm \"$VENV/.cuda-tried\" and re-run." >&2
    DEVICE=cpu
  else
    echo "[transcribe] · this WhisperX venv is CPU-only on a GPU machine: upgrading it to CUDA in place" >&2
    cuda_torch || DEVICE=cpu
  fi
fi
PYBIN="$(venv_py)"

# Windows Smart App Control (2026-10-13). A native file it has not seen before is checked online
# on its first load (36 s for one fresh venv here), and under load that check fails as a block a
# second load passes; a release too new to have reputation stays blocked (numpy 2.5.4's
# numpy.random, three days after release). The build's 14-day cooldown keeps a new venv clear of
# the second, but .deps-ok means a venv built before it is never rebuilt. So a run that dies on a
# block is retried once as it is, then once more on the venv re-resolved to releases at least 14
# days old. The torch family stays as cuda_torch() laid it (PyPI's Windows torch is CPU-only; the
# CUDA index carries no upload dates to cool), pinned in the resolve so the rest still fits it.
SAC_BLOCK="An Application Control policy has blocked this file"
SAC_LOG="$WORK/whisperx-run.stderr"
sac_reresolve() {
  echo "[transcribe] · Smart App Control still blocks a file in the WhisperX venv: re-resolving it to releases at least 14 days old (once)" >&2
  "$(venv_py)" -c 'import importlib.metadata as m
for d in ("torch", "torchaudio"):
    try: print(d + "==" + m.version(d).split("+")[0])
    except m.PackageNotFoundError: pass' > "$WORK/whisperx-cooldown.in" 2>/dev/null || : > "$WORK/whisperx-cooldown.in"
  echo whisperx >> "$WORK/whisperx-cooldown.in"
  # constrained to the lock: a cooled resolve may step back from it, never past it
  uv pip compile --python "$(venv_py)" --exclude-newer "14 days" --no-header --no-annotate -c "$LOCK" \
      "$WORK/whisperx-cooldown.in" -o "$WORK/whisperx-cooldown.txt" >&2 || return 1
  # The WHOLE cooled set goes in, never just the packages newer than it: stepping back part of a family
  # (opentelemetry's exporters without its api) broke whisperx's import on a real venv (2026-10-13).
  grep -v -i -E '^(torch|nvidia-)' "$WORK/whisperx-cooldown.txt" > "$WORK/whisperx-cooldown.keep.txt" || return 1
  local moved
  moved="$("$(venv_py)" - "$WORK/whisperx-cooldown.keep.txt" <<'PYK'
import importlib.metadata as m, sys
for line in open(sys.argv[1], encoding="utf-8"):
    name, _, ver = line.strip().partition("==")
    try:
        have = m.version(name)
    except m.PackageNotFoundError:
        have = None
    if ver and have != ver:
        print(f"{name} {have or '-'} -> {ver}")
PYK
)" || return 1
  if [ -z "$moved" ]; then
    echo "[transcribe]   the venv already matches releases at least 14 days old: the block is not a too-new release" >&2
    return 1
  fi
  echo "[transcribe]   moving: $(echo "$moved" | tr '\n' ';')" >&2
  uv pip install --python "$(venv_py)" --exclude-newer "14 days" -r "$WORK/whisperx-cooldown.keep.txt" >&2
}

set +e
# --diarize's token falls back to the repo-root .env (four folders up from this script), as sync-so.py's key does
export TRANSCRIBE_DOTENV="$(cd "$(dirname "$0")/../../../.." && pwd)/.env"
"$PYBIN" - "$PY_OUT" "$DIARIZE" "$DEVICE" "$CHUNK_SIZE" "$VAD_ONSET" "$VAD_OFFSET" "${CLIPS[@]}" 2> >(tee "$SAC_LOG" >&2) <<'PY'
import inspect, json, os, subprocess, sys, warnings
# pyannote warns on import when torchcodec's shared libraries do not load (Windows: winget's static ffmpeg ships no
# FFmpeg DLLs, 2026-09-27 S5). WhisperX decodes through the ffmpeg CLI and hands pyannote a waveform, so the warning is
# noise; anything that really needs torchcodec still raises its own RuntimeError.
warnings.filterwarnings("ignore", message=r"\s*torchcodec is not installed correctly")
import whisperx
# Windows without Developer Mode (WinError 1314 on os.symlink): huggingface_hub <1.0, the one whisperx pins, marks a
# cache folder symlink-capable BEFORE it tests it, so the large-v3 snapshot download's parallel workers race that test
# and the loser's os.symlink raises out of load_model. Only a fresh model cache meets it: a new PC's first
# transcription failed outright on CPU and dropped from cuda/float16 to int8_float16 on a GPU (2026-10-13). Answering
# "no symlinks" up front is the hub's own fallback (the file is moved into the snapshot) without the race.
if os.name == "nt":
    try:
        import huggingface_hub.file_download as _hf_fd
        _hf_fd.are_symlinks_supported = lambda cache_dir=None: False
    except Exception:
        pass

out_path = sys.argv[1]
diarize_flag = sys.argv[2] == "1"
want_device = sys.argv[3]      # "cuda" or "cpu", decided by transcribe.sh
# Validated by transcribe.sh; empty = WhisperX's own defaults (no chunk_size, vad_options None).
chunk_kw = {"chunk_size": int(sys.argv[4])} if sys.argv[4] else {}
vad_options = ({"vad_onset": float(sys.argv[5]), "vad_offset": float(sys.argv[6])}
               if sys.argv[5] else None)
clip_paths = sys.argv[7:]
if chunk_kw:
    print(f"[transcribe] Whisper window (chunk size) {chunk_kw['chunk_size']} s (WhisperX default 30)",
          file=sys.stderr)
if vad_options:
    print(f"[transcribe] VAD onset {vad_options['vad_onset']} / offset {vad_options['vad_offset']} "
          "(WhisperX defaults 0.500 / 0.363)", file=sys.stderr)

# A clip with no audio stream (a screen recording made without a mic, a silent cutaway) has nothing to transcribe,
# and whisperx.load_audio raised on it AFTER the other clips were done, so the whole job's words were lost on every
# run (2026-10-13). ffprobe decides before any model loads: a file it READ and found no audio in is recorded with no
# words; a file it cannot read is left to whisperx, which says why.
def no_audio(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                            "-of", "csv=p=0", path], capture_output=True, text=True)
    except OSError:
        return False
    return r.returncode == 0 and not r.stdout.strip()

def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return round(float(r.stdout.strip().splitlines()[0]), 3)
    except (ValueError, IndexError):
        return 0.0

silent = {p for p in clip_paths if no_audio(p)}
for p in clip_paths:
    if p in silent:
        print(f"[transcribe] ⚠ {os.path.basename(p)}: no audio stream, not transcribed (recorded with no words)",
              file=sys.stderr)
if silent and len(silent) == len(clip_paths):
    print("[transcribe] ✗ no clip here has an audio stream, so there is nothing to transcribe. A no-dialogue edit "
          "reads the footage instead: rough-cut SKILL.md § Folder Contract (\"No usable dialogue? Sample frames\")",
          file=sys.stderr)
    sys.exit(1)

# Device ladder. CPU int8 is the always-works floor (and the Apple Silicon
# lock: MPS torch is still spotty for some ops; CPU is slower but never
# silently wrong). With an NVIDIA GPU the ladder tries float16 first, then
# int8_float16 (fits ~4 GB cards), then drops to CPU: a broken CUDA stack
# (old driver, missing cuDNN, OOM) must never block an edit.
tiers = [("cpu", "int8", 8)]
if want_device == "cuda":
    tiers = [("cuda", "float16", 16), ("cuda", "int8_float16", 16)] + tiers
    try:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError(
                "torch.cuda.is_available() is False (CPU-only torch build, or the "
                "NVIDIA driver is too old for this CUDA runtime; a driver update "
                "usually fixes it)")
        # Windows: ctranslate2 resolves cublas/cudnn DLLs by name from the DLL
        # search path, and the CUDA torch wheel bundles them in torch/lib.
        if os.name == "nt":
            _lib = os.path.join(os.path.dirname(torch.__file__), "lib")
            if os.path.isdir(_lib):
                os.add_dll_directory(_lib)
                os.environ["PATH"] = _lib + os.pathsep + os.environ.get("PATH", "")
        print(f"[transcribe] NVIDIA GPU: {torch.cuda.get_device_name(0)}", file=sys.stderr)
    except Exception as e:
        # Loud on purpose: a correct transcript at several times the cost is the failure
        # mode nobody reports (the trap a client RTX 3060 sat in, 2026-09-07).
        print("[transcribe] " + "!" * 66, file=sys.stderr)
        print(f"[transcribe] ⚠ SLOW PATH: CUDA unavailable ({e}); using CPU int8.", file=sys.stderr)
        print("[transcribe]   This venv was verified for CUDA when built, and the GPU is not reachable now.", file=sys.stderr)
        print("[transcribe]   Fix the NVIDIA driver, or rm -rf the venv and re-run so the rebuild re-verifies CUDA.", file=sys.stderr)
        print("[transcribe] " + "!" * 66, file=sys.stderr)
        tiers = [("cpu", "int8", 8)]

def load_diarize(device):
    # whisperx 3.8 keeps the class in whisperx.diarize only and takes `token`; 3.3 took `use_auth_token`. Each
    # version's own default model (pyannote/speaker-diarization-community-1 on pyannote 4)
    hf_token = os.environ.get("HUGGINGFACE_TOKEN", "").strip()
    dotenv = os.environ.get("TRANSCRIBE_DOTENV", "")
    if not hf_token and dotenv and os.path.isfile(dotenv):
        for line in open(dotenv, encoding="utf-8"):
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            k, sep, v = line.partition("=")
            if sep and k.strip() == "HUGGINGFACE_TOKEN":
                v = v.strip()
                hf_token = v[1:-1] if len(v) > 1 and v[0] in "\"'" and v.endswith(v[0]) else v.split(" #", 1)[0].strip()
    if not hf_token:
        print("[transcribe] --diarize requires HUGGINGFACE_TOKEN (in env, or HUGGINGFACE_TOKEN=... in the repo-root .env)",
              file=sys.stderr)
        sys.exit(1)
    print("[transcribe] loading pyannote diarization pipeline", file=sys.stderr)
    from whisperx.diarize import DiarizationPipeline
    kw = "token" if "token" in inspect.signature(DiarizationPipeline).parameters else "use_auth_token"
    return DiarizationPipeline(device=device, **{kw: hf_token})

# built BEFORE the ASR stack, so a missing token or an unaccepted gated model fails in seconds, not after a model load
diarize_model = load_diarize(tiers[0][0]) if diarize_flag else None
diarize_device = tiers[0][0]

def load_stack(device, compute_type):
    print(f"[transcribe] loading whisperx large-v3 ({device}, {compute_type})", file=sys.stderr)
    asr = whisperx.load_model("large-v3", device, compute_type=compute_type, language="en",
                              vad_options=vad_options)
    print("[transcribe] loading wav2vec2 alignment model", file=sys.stderr)
    align, meta = whisperx.load_align_model(language_code="en", device=device)
    return asr, align, meta

for i, (device, compute_type, batch_size) in enumerate(tiers):
    try:
        asr_model, align_model, align_metadata = load_stack(device, compute_type)
        break
    except Exception as e:
        if i == len(tiers) - 1:
            raise
        nd, nc, _ = tiers[i + 1]
        print(f"[transcribe] ⚠ {device}/{compute_type} failed to load "
              f"({type(e).__name__}: {e}); trying {nd}/{nc}", file=sys.stderr)

if diarize_flag and device != diarize_device:          # the ladder settled lower than the diarizer was built for
    diarize_model = load_diarize(device)

def process(path):
    audio = whisperx.load_audio(path)
    tr = asr_model.transcribe(audio, batch_size=batch_size, language="en", **chunk_kw)
    al = whisperx.align(
        tr["segments"], align_model, align_metadata, audio, device,
        return_char_alignments=False)
    if diarize_model is not None:
        al = whisperx.assign_word_speakers(diarize_model(audio), al)
    return audio, al

result = {"clips": []}
for path in clip_paths:
    name = os.path.basename(path)
    if path in silent:
        result["clips"].append({"clip": name, "path": path, "duration": probe_duration(path), "words": []})
        continue
    print(f"[transcribe] {name}", file=sys.stderr)
    try:
        audio, aligned = process(path)
    except Exception as e:
        # CUDA can also die mid-run (OOM on a long clip, a cuDNN kernel error):
        # rebuild the whole stack on CPU once and redo this clip. CPU errors
        # are real errors and still raise.
        if device == "cpu":
            raise
        print(f"[transcribe] ⚠ CUDA failed mid-run on {name} "
              f"({type(e).__name__}: {e}); falling back to CPU int8", file=sys.stderr)
        device, compute_type, batch_size = "cpu", "int8", 8
        asr_model, align_model, align_metadata = load_stack(device, compute_type)
        if diarize_flag:
            diarize_model = load_diarize(device)
        audio, aligned = process(path)
    duration = len(audio) / 16000.0

    words = []
    for seg in aligned.get("segments", []):
        for w in seg.get("words", []):
            # wav2vec2 sometimes can't align unspeakable tokens (numerals, punctuation).
            # Skip words missing timestamps so cuts.json builders don't crash.
            if "start" not in w or "end" not in w:
                continue
            entry = {
                "w": str(w.get("word", "")).strip(),
                "start": round(float(w["start"]), 3),
                "end": round(float(w["end"]), 3),
                "prob": round(float(w.get("score", 1.0)), 3),
            }
            if "speaker" in w:
                entry["speaker"] = w["speaker"]
            words.append(entry)

    result["clips"].append({
        "clip": name,
        "path": path,
        "duration": round(duration, 3),
        "words": words,
    })

with open(out_path, "w") as f:
    json.dump(result, f, indent=2)
print(f"[transcribe] wrote {out_path}", file=sys.stderr)

# WhisperX collapses an immediately repeated word into ONE long-span entry —
# the transcript shows a single word but the audio has every utterance. Flag
# them so cut authoring doesn't trust the span (splice's refiner auto-snaps
# these at segment boundaries; MID-segment ones need an authored split).
# A LOW-PROBABILITY word is flagged at half the span: the aligner stretches an uncertain word
# across the silence next to it (your-job 2026-09-04: a p0.35 "the" spanned 0.94 s over a
# 0.9 s pause, under the 1.0 s flag, and the pause shipped inside a segment).
for c in result["clips"]:
    for w in c["words"]:
        span = w["end"] - w["start"]
        if span > 1.0 or (span > 0.5 and w["prob"] < 0.5):
            why = ("possible merged repeat" if span > 1.0
                   else f"low-prob (p{w['prob']:.2f}) word stretched over a pause")
            print(f"[transcribe] ⚠ long-span word {w['w']!r} "
                  f"{w['start']:.2f}-{w['end']:.2f} ({span:.2f}s) "
                  f"— {why}, check the audio before keeping",
                  file=sys.stderr)
PY
RC=$?
set -e
set +u; TEE_PID="$!"; set -u   # macOS bash 3.2 reads ${!:-} as a bad indirect substitution and exits
{ [ -n "$TEE_PID" ] && wait "$TEE_PID"; } 2>/dev/null || true   # the tee: its log is whole before it is read
if [ "$RC" -ne 0 ]; then
  if grep -q "$SAC_BLOCK" "$SAC_LOG" 2>/dev/null; then
    case "${VE_SAC_RETRY:-0}" in
      0) echo "[transcribe] · Smart App Control blocked a file on its first look (a first load is checked online): retrying once" >&2
         export VE_SAC_RETRY=1; exec bash "$0" "${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}" ;;
      1) if sac_reresolve; then
           echo "[transcribe] · retrying on the re-resolved venv" >&2
           export VE_SAC_RETRY=2; exec bash "$0" "${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}"
         fi ;;
    esac
    echo "[transcribe] ✗ Smart App Control still blocks the WhisperX venv after a retry and a re-resolve to releases" >&2
    echo "[transcribe]   at least 14 days old. The blocked import: $(grep -m1 "$SAC_BLOCK" "$SAC_LOG")" >&2
  fi
  exit "$RC"
fi

if [ -n "$FILE" ]; then
  echo "$OUT"
  exit 0
fi

# Persist the canonical copy so we never transcribe this footage again.
cp "$WORK/words.json" "$CANON"
echo "[transcribe] persisted canonical transcript → $CANON" >&2
echo "$WORK/words.json"
