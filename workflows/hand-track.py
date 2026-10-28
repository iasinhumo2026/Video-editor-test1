#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["mediapipe==0.10.14", "opencv-python-headless", "numpy", "requests"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""hand-track.py — per-frame hand position from a video, for anchoring a graphic to a hand.

    uv run workflows/hand-track.py <video> [--out track.json] [--which left|right|any]
                                  [--anchor palm|index|wrist] [--smooth 7] [--preview dir]

Emits one record per frame: timeline seconds + the anchor point in PIXELS and in
CapCut's canvas-normalized units, ready to become position keyframes.

MediaPipe reports a hand only when it is confidently visible, so gaps are normal
(hands leave frame, turn edge-on, blur through a fast gesture). Runs are reported
off RAW detections, and each record keeps `detected` — smoothing fills a dropout
shorter than its window from the neighbours either side, which is what you want
for a 1-3 frame blur, but those frames are inferred, not measured. Pick a window
whose RAW run is continuous; never stretch a graphic across a long gap, because a
graphic pinned to a guessed position slides off the hand and reads worse than a
graphic that simply isn't there.

Coordinate note: CapCut normalizes position to the canvas so that 1.0 is a FULL
frame width/height and +y is DOWN, matching capcut-bridge's `transform --y`.
"""
import argparse, json, math, sys, urllib.request
# Windows consoles/pipes default to cp1252, which can't encode the {glyphs} glyphs in this
# script's status lines: a cosmetic print must never kill a pipeline step (it did once,
# 2026-08-13, mid-splice on a real Windows job). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cv2_io import imwrite  # noqa: E402  (never cv2.imwrite: it fails silently on a non-ASCII Windows path)
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")
MODEL_PATH = Path.home() / ".cache" / "video-editor" / "hand_landmarker.task"

# MediaPipe hand landmark indices
WRIST, THUMB_TIP, INDEX_MCP, INDEX_TIP, MIDDLE_MCP, PINKY_MCP = 0, 4, 5, 8, 9, 17


def ensure_model():
    if not MODEL_PATH.exists():
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"[hand-track] fetching hand_landmarker model → {MODEL_PATH}", file=sys.stderr)
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return str(MODEL_PATH)


def anchor_point(lm, kind):
    """Anchor in normalized image coords. `palm` is the centroid of the palm
    knuckles + wrist — far steadier than any fingertip, which whips around
    during a gesture and would make the graphic jitter."""
    if kind == "wrist":
        return lm[WRIST].x, lm[WRIST].y
    if kind == "index":
        return lm[INDEX_TIP].x, lm[INDEX_TIP].y
    pts = [lm[i] for i in (WRIST, INDEX_MCP, MIDDLE_MCP, PINKY_MCP)]
    return sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts)


def hand_span(lm, w, h):
    """Rough on-screen hand size in px (wrist → middle knuckle), a usable proxy
    for depth — lets a tracked graphic scale with the hand instead of sliding
    across it."""
    dx, dy = (lm[MIDDLE_MCP].x - lm[WRIST].x) * w, (lm[MIDDLE_MCP].y - lm[WRIST].y) * h
    return math.hypot(dx, dy)


def smooth(vals, window):
    """Centered moving average over present values only. Tracking noise is a few
    px frame to frame; unsmoothed it reads as a buzz on a glowing graphic."""
    if window <= 1:
        return vals
    out, half = [], window // 2
    for i in range(len(vals)):
        near = [v for v in vals[max(0, i - half): i + half + 1] if v is not None]
        out.append(sum(near) / len(near) if near else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default=None)
    ap.add_argument("--which", default="any", choices=["left", "right", "any"])
    ap.add_argument("--anchor", default="palm", choices=["palm", "index", "wrist"])
    ap.add_argument("--smooth", type=int, default=7)
    ap.add_argument("--min-conf", type=float, default=0.4)
    ap.add_argument("--preview", default=None, help="write annotated frames here")
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    if not cap.isOpened():
        sys.exit(f"cannot open {a.video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    opts = vision.HandLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=ensure_model()),
        running_mode=vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=a.min_conf,
        min_hand_presence_confidence=a.min_conf, min_tracking_confidence=a.min_conf)

    raw, n = [], 0
    with vision.HandLandmarker.create_from_options(opts) as det:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = n / fps
            img = mp.Image(image_format=mp.ImageFormat.SRGB,
                           data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            res = det.detect_for_video(img, int(t * 1000))
            pick = None
            for lm, handed in zip(res.hand_landmarks, res.handedness):
                label = handed[0].category_name.lower()
                if a.which != "any" and label != a.which:
                    continue
                score = handed[0].score
                if pick is None or score > pick[2]:
                    pick = (lm, label, score)
            if pick:
                lm, label, score = pick
                x, y = anchor_point(lm, a.anchor)
                raw.append(dict(frame=n, t=round(t, 4), px=x * w, py=y * h,
                                span=round(hand_span(lm, w, h), 1),
                                hand=label, score=round(score, 3)))
            else:
                raw.append(dict(frame=n, t=round(t, 4), px=None, py=None,
                                span=None, hand=None, score=0.0))
            n += 1
    cap.release()

    for r in raw:
        r["detected"] = r["px"] is not None
    for key in ("px", "py", "span"):
        for rec, val in zip(raw, smooth([r[key] for r in raw], a.smooth)):
            rec[key] = None if val is None else round(val, 2)

    for r in raw:
        if r["px"] is None:
            r["x"], r["y"] = None, None
        else:
            # CapCut canvas-normalized: 1.0 == a full frame width/height, +y down.
            r["x"] = round((r["px"] - w / 2) / w, 5)
            r["y"] = round((r["py"] - h / 2) / h, 5)

    covered = [r for r in raw if r["detected"]]
    runs, cur = [], None
    for r in raw:
        if r["detected"]:
            cur = cur or [r["t"], r["t"]]
            cur[1] = r["t"]
        elif cur:
            runs.append(cur); cur = None
    if cur:
        runs.append(cur)

    out = dict(video=str(Path(a.video).resolve()), fps=fps, width=w, height=h,
               anchor=a.anchor, which=a.which, smooth=a.smooth,
               frames=len(raw), tracked=len(covered),
               runs=[dict(start=round(s, 3), end=round(e, 3), dur=round(e - s, 3))
                     for s, e in runs],
               track=raw)
    dest = Path(a.out) if a.out else Path(a.video).with_suffix(".handtrack.json")
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"[hand-track] {len(covered)}/{len(raw)} frames tracked @ {fps:g}fps  → {dest}")
    for r in out["runs"]:
        print(f"  continuous {r['start']:.2f}s → {r['end']:.2f}s  ({r['dur']:.2f}s)")
    if covered:
        xs = [r["px"] for r in covered]; ys = [r["py"] for r in covered]
        sp = [r["span"] for r in covered]
        print(f"  px range  x {min(xs):.0f}→{max(xs):.0f}   y {min(ys):.0f}→{max(ys):.0f}"
              f"   span {min(sp):.0f}→{max(sp):.0f}")

    if a.preview:
        pv = Path(a.preview); pv.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(a.video)
        by_frame = {r["frame"]: r for r in raw}
        i = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            r = by_frame.get(i)
            if r and r["px"] is not None:
                cv2.circle(frame, (int(r["px"]), int(r["py"])), 18, (0, 255, 140), 3)
                cv2.putText(frame, f"{r['t']:.2f}s {r['hand']}", (int(r["px"]) + 26, int(r["py"])),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 140), 2)
            imwrite(pv / f"{i:04d}.png", frame)
            i += 1
        cap.release()
        print(f"  preview frames → {pv}")


if __name__ == "__main__":
    main()
