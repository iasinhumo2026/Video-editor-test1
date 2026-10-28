#!/usr/bin/env python
"""asr_cli.py: the slice-ASR engine behind cut-audit.py and cut-proof.py, on every OS.

Both tools shell out to an `mlx_whisper`-shaped CLI and read its JSON back. mlx-whisper runs only
on Apple Silicon, so on Windows and Linux every slice-ASR check silently degraded to envelope
heuristics ("ASR unavailable (needs uvx + mlx-whisper on macOS)", measured on a Windows RTX 5070
box 2026-09-27): no content gate, no --say, no gap verification, and no cut-proof at all.

`argv()` is what a caller runs:
  - Apple Silicon: `uvx --python cpython-3.12-macos-aarch64-none --exclude-newer "14 days" --from mlx-whisper==0.4.3
    mlx_whisper` (the calibrated engine; pinned to 3.12 because mlx ships no wheel for a fresh Mac's python3, which
    Homebrew made 3.15 on 2026-10-13, by its arm64 key so an x86_64 uv under Rosetta cannot pick an Intel
    interpreter, and held to releases two weeks old like every PEP 723 header)
  - elsewhere, an Intel Mac included (mlx has no macOS x86_64 wheel): THIS file under the WhisperX venv's python
    (transcribe.sh builds it; CUDA when the venv was verified for it), running faster-whisper large-v3-turbo, the
    same weights mlx uses.

`run(args)` is how a caller runs it: ONE engine process per caller, fed every slice in turn, so the model loads once
(a process per slice loaded large-v3-turbo every time: 8-22 s a slice on Windows, a 37-segment audit took 24 min,
2026-10-13). Each slice still writes exactly the file `[*argv(), *args]` writes.

As a script it takes the mlx_whisper flags the callers pass (--model, --word-timestamps,
--condition-on-previous-text, --output-format json, --output-dir, one audio file) and writes
mlx_whisper's JSON shape, {"text", "segments": [{"start", "end", "text", "words": [{"word",
"start", "end", "probability"}]}]}, named by the input's basename up to its FIRST dot, exactly as
mlx_whisper names it (both callers rely on that). `--serve mlx|faster-whisper` is the engine process `run()` starts.
"""
import atexit
import io
import json
import os
import platform
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

FW_MODEL = "large-v3-turbo"
MLX = ["uvx", "--python", "cpython-3.12-macos-aarch64-none", "--exclude-newer", "14 days",
       "--from", "mlx-whisper==0.4.3", "mlx_whisper"]
SERVE = "--serve"
TAG = "@@asr_cli "        # a reply line from the engine process; nothing a library prints starts with it


def venv_python():
    # transcribe.sh's venv, by its own name (the client package renames both in one scrub)
    v = Path(os.environ.get("VIDEO_EDITOR_WHISPERX_VENV") or Path.home() / ".cache/video-editor/whisperx-venv")
    for p in (v / "Scripts" / "python.exe", v / "bin" / "python"):
        if p.exists():
            return str(p)
    return None


_arm = {}


def apple_silicon():
    """Apple Silicon hardware, also when this process is an x86_64 build under Rosetta (platform.machine() then
    says x86_64, the sysctl still says arm64). An Intel Mac answers no: mlx has no wheel there."""
    if sys.platform != "darwin":
        return False
    if "darwin" not in _arm:                                # asked once per slice: the sysctl runs once
        try:
            r = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True)
            _arm["darwin"] = r.stdout.strip() == "1"
        except OSError:
            _arm["darwin"] = platform.machine() == "arm64"
    return _arm["darwin"]


def argv():
    """The command prefix for one mlx_whisper-shaped call, or None when no engine exists here."""
    if apple_silicon():
        return list(MLX)
    py = venv_python()
    return [py, str(Path(__file__).resolve())] if py else None


def unavailable_reason():
    if apple_silicon():
        return "needs uvx + mlx-whisper"
    return "needs the WhisperX venv (run transcribe.sh once to build it)"


def serve_argv():
    """The engine process `run()` starts: the same interpreter and packages as argv(), this file in --serve mode."""
    eng = argv()
    if eng is None:
        return None
    if eng[0] == "uvx":                                     # mlx: the same uvx environment, its python running this file
        return [*eng[:-1], "python", str(Path(__file__).resolve()), SERVE, "mlx"]
    return [*eng, SERVE, "faster-whisper"]


class Worker:
    """One engine process, many slices. call(args) answers like subprocess.run([*argv(), *args], capture_output=True,
    text=True): returncode 0 and the JSON written, or non-zero with the engine's last words in stderr. A dead engine
    is started again on the next call."""

    def __init__(self):
        self.p = self.log = None

    def start(self):
        cmd = serve_argv()
        if cmd is None:
            return unavailable_reason()
        self.log = tempfile.TemporaryFile()                 # never a pipe: a full stderr pipe would stall the engine
        try:
            self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                                      text=True, encoding="utf-8")
        except OSError as e:
            self.p = None
            return f"{cmd[0]}: {e}"
        return None

    def tail(self):
        if self.log is None:
            return ""
        self.log.seek(0, 2)
        self.log.seek(max(0, self.log.tell() - 2000))
        return self.log.read().decode("utf-8", "replace")

    def call(self, args):
        args = [str(x) for x in args]
        if self.p is not None and self.p.poll() is not None:
            self.close()
        if self.p is None:
            err = self.start()
            if err:
                return subprocess.CompletedProcess(args, 1, "", err)
        try:
            self.p.stdin.write(json.dumps({"args": args}) + "\n")
            self.p.stdin.flush()
            for line in self.p.stdout:
                if line.startswith(TAG):
                    rep = json.loads(line[len(TAG):])
                    for w in rep.get("warn", []):                # a CUDA failure moved the engine to the CPU: say so
                        print(w, file=sys.stderr, flush=True)
                    err = rep.get("err", "") or (self.tail() if rep["rc"] else "")
                    return subprocess.CompletedProcess(args, rep["rc"], rep.get("out", ""), err)
        except (OSError, ValueError):
            pass
        tail = self.tail()
        self.close()
        return subprocess.CompletedProcess(args, 1, "", tail or "the ASR engine exited")

    def close(self):
        if self.p is not None:
            try:
                self.p.stdin.close()
                self.p.wait(timeout=30)
            except Exception:
                self.p.kill()
                self.p.wait()
            self.p.stdout.close()
            self.p = None
        if self.log is not None:
            self.log.close()
            self.log = None


_worker = Worker()
atexit.register(_worker.close)


def run(args):
    """One slice through this process's engine: what subprocess.run([*argv(), *args], ...) returns."""
    return _worker.call(args)


def cuda_dll_dir():
    """Windows: put the CUDA torch wheel's torch/lib on the DLL search path, without importing torch.

    ctranslate2 resolves cuBLAS by name from the DLL search path and its Windows wheels stopped shipping it (4.8.2
    carries only cuDNN), so every CUDA slice failed with "Library cublas64_12.dll is not found or cannot be loaded"
    (2026-10-13). The venv's CUDA torch bundles cublas64_12.dll in torch/lib; transcribe.sh adds that folder the same
    way. find_spec, never `import torch`: the import costs seconds on every slice."""
    import importlib.util
    try:
        spec = importlib.util.find_spec("torch")
    except Exception:
        return
    lib = Path(spec.origin).parent / "lib" if spec and spec.origin else None
    if lib and lib.is_dir():
        os.add_dll_directory(str(lib))
        os.environ["PATH"] = str(lib) + os.pathsep + os.environ.get("PATH", "")


_models = {}       # (device, compute_type) -> WhisperModel: loaded once per process
_device = []       # [device, compute_type], decided once; a CUDA failure moves it to the CPU for the process's life
_warned = []       # the engine's own ⚠ lines since the last reply: --serve hands them to the caller's stderr


def engine_device():
    if not _device:
        device, ctype = "cpu", "int8"
        mode = Path(venv_python() or "").parents[1] / ".mode" if venv_python() else None
        if mode and mode.exists() and mode.read_text(encoding="utf-8").strip() == "cuda":
            device, ctype = "cuda", "float16"
        if device == "cuda" and os.name == "nt":
            cuda_dll_dir()                                 # before faster_whisper (ctranslate2) loads
        _device[:] = [device, ctype]
    return _device


def main(args):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--model", default=FW_MODEL)            # an mlx repo id is mapped to the same weights
    ap.add_argument("--word-timestamps", default="True")
    ap.add_argument("--condition-on-previous-text", default="True")
    ap.add_argument("--output-format", default="json")
    ap.add_argument("--output-dir", default=".")
    a = ap.parse_args(args)
    device, ctype = engine_device()
    from faster_whisper import WhisperModel

    def run_on(dev, ct):
        if (dev, ct) not in _models:
            _models[(dev, ct)] = WhisperModel(FW_MODEL, device=dev, compute_type=ct)
        segs, _ = _models[(dev, ct)].transcribe(a.audio, word_timestamps=a.word_timestamps == "True",
                                                condition_on_previous_text=a.condition_on_previous_text == "True",
                                                vad_filter=False)
        # the segments are a generator: CUDA's cuBLAS loads lazily, on the first encode, so a missing DLL
        # raises HERE, never at WhisperModel() (Windows, ctranslate2 4.8.2: "cublas64_12.dll is not found")
        return [{"start": s.start, "end": s.end, "text": s.text,
                 "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                           for w in (s.words or [])]} for s in segs]
    out = {"text": "", "segments": []}
    try:
        out["segments"] = run_on(device, ctype)
    except Exception as e:                                   # a broken CUDA stack degrades, never blocks
        if device == "cpu":
            raise
        msg = f"[asr_cli] ⚠ {device}/{ctype} failed ({type(e).__name__}: {e}); running on the CPU (int8)"
        print(msg, file=sys.stderr)
        _warned.append(msg)          # --serve's stderr is a log file nobody reads: the reply carries it to the caller
        _models.pop((device, ctype), None)
        _device[:] = ["cpu", "int8"]
        out["segments"] = run_on("cpu", "int8")
    out["text"] = "".join(s["text"] for s in out["segments"])
    od = Path(a.output_dir)
    od.mkdir(parents=True, exist_ok=True)
    (od / (Path(a.audio).name.split(".")[0] + ".json")).write_text(json.dumps(out), encoding="utf-8")


def mlx_main(args):
    """mlx_whisper's own CLI, in this process: the model it loads stays loaded for the next slice."""
    from mlx_whisper import cli
    old = sys.argv
    sys.argv = ["mlx_whisper", *args]
    try:
        cli.main()
    finally:
        sys.argv = old


def serve(engine):
    """The engine process: one JSON request per line on stdin ({"args": [...the mlx_whisper flags + audio]}), one
    TAG reply per request on stdout ({"rc", "out", "err", "warn"}). Everything else either engine prints goes to stderr."""
    try:
        sys.stderr.reconfigure(encoding="utf-8")            # the ⚠ lines, into a Windows stderr that defaults to cp1252
    except AttributeError:
        pass
    proto = os.fdopen(os.dup(1), "w", encoding="utf-8")
    os.dup2(2, 1)                                            # a library's print (or a C write to fd 1) is never a reply
    one = mlx_main if engine == "mlx" else main
    for line in sys.stdin:
        if not line.strip():
            continue
        printed = io.StringIO()
        rc, err = 0, ""
        try:
            with redirect_stdout(printed):
                one(json.loads(line)["args"])
        except SystemExit as e:                            # argparse's 2, a sys.exit("message"), as a process would end
            rc, err = (0, "") if e.code is None else (e.code, "") if isinstance(e.code, int) else (1, str(e.code))
        except Exception as e:
            rc, err = 1, f"{type(e).__name__}: {e}"
        warn, _warned[:] = list(_warned), []
        proto.write(TAG + json.dumps({"rc": rc, "out": printed.getvalue()[-2000:], "err": err, "warn": warn}) + "\n")
        proto.flush()


if __name__ == "__main__":
    if sys.argv[1:2] == [SERVE]:
        serve(sys.argv[2])
    else:
        main(sys.argv[1:])
