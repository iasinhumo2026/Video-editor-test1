# /// script
# requires-python = ">=3.10,<3.15"
# dependencies = ["rapidocr>=3,<3.9", "numpy", "pillow", "onnxruntime; sys_platform != 'win32'",
#                 "onnxruntime-directml; sys_platform == 'win32'"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""ocr_shim.py: the non-macOS OCR shim, speaking the Swift Vision shim's protocol exactly (pii-scan.py SWIFT_OCR).

  printf '%s\n' a.jpg b.jpg | uv run -q workflows/ocr_shim.py            # pii-scan.py's protocol (boxes)
  printf '%s\n' a.jpg b.jpg | uv run -q workflows/ocr_shim.py --joined   # graphics-qa-short.py's: path \t all the text

One image path per line on stdin. One TSV row per text block, then one "-" row per file so an image with no text is
still recorded as read:   path \t x0 \t y0 \t x1 \t y1 \t text   (image pixels, origin top-left, like the shim's).

The engine is RapidOCR (PaddleOCR models on ONNX Runtime: pip, offline after the first model fetch, no admin), the one
proven on this Windows machine (2026-09-27): Windows' own OCR (Windows.Media.Ocr) never read small monospace digits,
RapidOCR read them at 0.97. It is the `rapidocr` package, held below 3.9 (2026-10-13): 3.0-3.8 bundle the very PP-OCRv4
mobile models rapidocr-onnxruntime 1.4.4 shipped (the package that proof ran on, frozen upstream and capped at Python
3.12), and read 26 of 26 proof frames to the same text and boxes; 3.9 bundles PP-OCRv6 instead, which reads 9 of
those 26 differently, so moving to it is a new proof, never a re-lock. Python stays below 3.15: onnxruntime and
onnxruntime-directml publish no 3.15 wheels. Two settings are load-bearing:
  Det.limit_type "max": the default ("min", 736) UPSCALES every image until its short side is 736 px, so a thin strip
                        is detected at ~20x its size (2 s a read instead of 0.1 s); "max" only ever shrinks
  use_cls False:        no angle classifier (frames are upright), two thirds of the time on a busy frame
And one more, found on the Windows re-test (2026-09-27): OpenCV runs on ONE thread (cv2.setNumThreads(1), before the
engine starts). With its thread pool on, a process holding the ONNX Runtime sessions intermittently could not start that
pool while another ONNX Runtime process was busy (a sweep beside a QA run): every cv2 call, even cv2.getNumThreads(),
raised "Unknown C++ exception", so every image in that process was "ocr failed" (8 of 10 processes under that load, on
OpenCV 5.0 and 4.14 alike; 0 of 10 on one thread, at the same speed, since the ONNX inference is the cost).
A file that cannot be decoded is named on stderr and still gets its "-" row, never a silent skip.

On Windows the engine runs on the GPU through DirectML (the user's call, 2026-09-27): onnxruntime-directml INSTEAD of the
CPU onnxruntime (the two ship the same `onnxruntime` module and cannot both be installed; rapidocr 3.x depends on
neither, so the header names one per platform), and every RapidOCR stage on it (EngineConfig.onnxruntime.use_dml).
Measured on the RTX 5070, 60 frames of 1080p, these exact settings (on 1.4.4; 3.x is a Windows re-test item): 0.12 s a
frame against 1.1-1.3 s on the CPU, the text IDENTICAL on all 60 (CUDA was as fast but read one frame differently, and
is a far bigger install); DirectML runs on any DirectX 12 GPU, NVIDIA, AMD or Intel. The CPU stays the fallback, never a
failure: VE_OCR_CPU=1 forces it; ONNX Runtime falls back by itself when a DirectML session cannot be created, and PRINTS
that to stdout, the protocol, so the engine is built with stdout on stderr; and a DirectML failure on a read rebuilds
the engine on the CPU once and reads that image again, so a GPU problem never becomes an unread frame (which pii-scan
counts as no verdict). macOS and Linux keep the plain CPU onnxruntime (macOS uses the Swift Vision shim anyway).
"""
import contextlib
import os
import sys


def no_text(record):
    """False for RapidOCR's "The text detection result is empty": 3.x logs it as a warning (the exception itself is the
    message) on every frame with no text, where 1.4.4 said nothing, and pii-scan would print each one as a ⚠."""
    return not isinstance(record.msg, Exception)


def engine(dml):
    """RapidOCR with the load-bearing settings above; `dml`: every stage on DirectML. Built with stdout on stderr: ONNX
    Runtime's own fallback and the model download print there, and stdout is the protocol."""
    from rapidocr import RapidOCR
    try:   # RapidOCR logs at INFO, in colour, to stderr ("try to use DirectML..."), and pii-scan relays each stderr line
        import logging                                   # as a ⚠: warnings only (Global.log_level below), plain text
        from rapidocr.utils.log import logger
        logger.addFilter(no_text)
        for h in logger.handlers:
            h.setFormatter(logging.Formatter("[RapidOCR] %(levelname)s: %(message)s"))
    except ImportError:
        pass
    kw = {"Global.log_level": "warning", "Det.limit_type": "max", "Det.limit_side_len": 4000}
    if dml:
        kw["EngineConfig.onnxruntime.use_dml"] = True    # one switch: detector, classifier and recogniser alike
    with contextlib.redirect_stdout(sys.stderr):
        return RapidOCR(params=kw)


def main(joined=False):
    import cv2
    import numpy as np
    from PIL import Image
    cv2.setNumThreads(1)                             # before the engine: see the docstring (the Windows re-test)
    dml = sys.platform == "win32" and os.environ.get("VE_OCR_CPU") != "1"
    try:
        eng = engine(dml)
    except Exception as e:
        if not dml:
            raise
        print(f"[ocr_shim] DirectML engine failed ({e}): reading on the CPU", file=sys.stderr)
        dml, eng = False, engine(False)
    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        try:
            img = np.asarray(Image.open(path).convert("RGB"))
        except Exception as e:                       # never swallow: a silent failure reads as "no hits"
            print(f"cannot decode {path}: {e}", file=sys.stderr)
            if not joined:                           # --joined: stderr only, exactly as graphics-qa-short's Swift shim
                print(f"{path}\t-\t-\t-\t-\t", flush=True)
            continue
        try:
            try:
                res = eng(img, use_cls=False)
            except Exception as e:
                if not dml:
                    raise
                print(f"[ocr_shim] DirectML read failed on {path} ({e}): the engine moves to the CPU", file=sys.stderr)
                dml, eng = False, engine(False)
                res = eng(img, use_cls=False)
            rows = list(zip(res.boxes, res.txts)) if res.txts else []   # nothing read: boxes and txts are None
        except Exception as e:
            print(f"ocr failed {path}: {e}", file=sys.stderr)
            if not joined:
                print(f"{path}\t-\t-\t-\t-\t", flush=True)
            continue
        if joined:                                   # one "path \t text" row per image read, even an empty one
            t = " ".join(str(text) for _box, text in rows).replace("\t", " ").replace("\n", " ")
            print(f"{path}\t{t}", flush=True)
            continue
        for box, text in rows:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            t = str(text).replace("\t", " ").replace("\n", " ")
            print(f"{path}\t{int(min(xs))}\t{int(min(ys))}\t{int(max(xs))}\t{int(max(ys))}\t{t}")
        print(f"{path}\t-\t-\t-\t-\t", flush=True)


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):              # Windows pipes default to cp1252; OCR text is any script
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    main(joined="--joined" in sys.argv)
