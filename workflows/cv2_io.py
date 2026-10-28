#!/usr/bin/env python
"""cv2_io.py: OpenCV's image and model FILE reads and writes, on any path.

OpenCV opens files with a narrow fopen(), so on Windows a path outside the ANSI code page (a user named José, a
OneDrive 'Área de Trabalho', a Cyrillic or CJK folder) cannot be opened, and it fails SILENTLY: cv2.imread returns
None, cv2.imwrite returns False, and the YuNet model does not load. face-frame.py read every sample frame back from
%TEMP% (under the user profile) and would drop them all; hero-frame.py printed `sheet ->` over a sheet it never wrote
(OpenCV issue #4292, closed 2020 unfixed; the audit, 2026-10-13). So the bytes move through Python's own file I/O, which
takes any path, and OpenCV only encodes and decodes them in memory. workflows/test_cv2_io.py fails on a raw
cv2.imread / cv2.imwrite / by-path FaceDetectorYN anywhere else in workflows/.

Imported by the scripts that already depend on opencv-python-headless and numpy; it has no PEP 723 header of its own.
"""
import sys
from pathlib import Path

import cv2
import numpy as np


def imread(path, flags=None):
    """The image at `path` (IMREAD_COLOR unless `flags` say otherwise), or None when it is missing or does not decode:
    cv2.imread's own contract, which callers already test (a frame grab ffmpeg could not write is skipped)."""
    try:
        buf = np.fromfile(str(path), np.uint8)
    except OSError:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR if flags is None else flags) if buf.size else None


def imwrite(path, img, params=()):
    """Write `img` as the format its extension names. A write that fails exits non-zero and says so: cv2.imwrite
    returns False with no word, and the caller went on to print the path as written."""
    try:
        ok, buf = cv2.imencode(Path(path).suffix, img, list(params))
    except cv2.error as e:                     # no encoder for that extension
        sys.exit(f'✗ could not encode {path}: {e}')
    if not ok:
        sys.exit(f'✗ could not encode {path}')
    try:
        Path(path).write_bytes(buf.tobytes())
    except OSError as e:
        sys.exit(f'✗ could not write {path}: {e}')
    return True


def face_detector(model, input_size, *args, **kwargs):
    """cv2.FaceDetectorYN from the model's BYTES (the bufferModel overload): the by-path loader opens the .onnx with
    the same narrow fopen. Same detections, byte for byte (OpenCV 5.0.0, 2026-10-13)."""
    return cv2.FaceDetectorYN.create('onnx', np.fromfile(str(model), np.uint8), np.array([], np.uint8), input_size,
                                     *args, **kwargs)
