# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "opencv-python-headless"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""track-region.py: lock a box to a region of a screen recording through its zooms by REGISTRATION, not OCR.

  uv run workflows/track-region.py <render.mp4> --ref <frame> --box x0,y0,x1,y1 --from <frame> --to <frame> --out <track.json>
      --ref     a render frame where the target is settled and legible; --box is measured ON it, in the 1920x1080 frame
      --from / --to   the render frames to track (inclusive)
      --roi x0,y0,x1,y1   (optional) only match features inside this rect of the REFERENCE frame (default: the whole frame)

A Screen Studio take's zoom is a pure scale + offset of the recorded screen, so every frame is the reference frame under
one similarity transform. Per frame: ORB features matched to the reference, a RANSAC partial-affine fit (rotation dropped,
scale kept uniform), the box mapped through it, then a light 3-tap smooth. The box can only scale and move together, so
it never changes shape, and a zoom in or out is followed continuously. A frame that cannot be matched (motion blur mid-zoom,
a cut) is interpolated from its neighbours in log scale, and named.

Why (2026-10-06, on the OCR-tracked highlighter): "I don't know why it's moving around so much... It's not even
smooth... glitches out, changes shape for one frame." track-text.py reads the text's box off every frame by OCR: each read
boxes the words a little differently, a dropout mid-zoom was bridged linearly between two differently sized boxes, and the
band breathed and jumped. The output is track-text.py's format ({"fps", "render", "frames": {n: [x0, y0, x1, y1]}}), so
presets/youtube/default/highlight/build.py and bake.py read it unchanged.
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np, cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

W, H = 1920, 1080


def frames(path, f0, f1):
    """Gray 1920x1080 frames f0..f1 of the render, decoded once, every frame (passthrough: no duplicates)."""
    n = f1 - f0 + 1
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vf', f'select=between(n\\,{f0}\\,{f1}),scale={W}:{H}:flags=area,format=gray',
           *passthrough(), '-frames:v', str(n), '-f', 'rawvideo', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    arr = np.frombuffer(raw, np.uint8)
    got = arr.size // (W * H)
    if got != n: sys.exit(f'read {got} frames of {n} ({f0}-{f1}): is the range inside the render?')
    return arr.reshape(n, H, W)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('render'); ap.add_argument('--ref', type=int, required=True)
    ap.add_argument('--box', required=True); ap.add_argument('--from', dest='f0', type=int, required=True)
    ap.add_argument('--to', dest='f1', type=int, required=True); ap.add_argument('--roi', default=None)
    ap.add_argument('--out', required=True); ap.add_argument('--fps', default='24000/1001')
    a = ap.parse_args()
    box = [float(v) for v in a.box.split(',')]
    lo, hi = min(a.f0, a.ref), max(a.f1, a.ref)
    fr = frames(a.render, lo, hi)
    ref = fr[a.ref - lo]
    orb = cv2.ORB_create(nfeatures=6000, scaleFactor=1.2, nlevels=10, fastThreshold=12)
    mask = None
    if a.roi:
        x0, y0, x1, y1 = (int(float(v)) for v in a.roi.split(','))
        mask = np.zeros_like(ref); mask[y0:y1, x0:x1] = 255
    kr, dr = orb.detectAndCompute(ref, mask)
    if dr is None or len(kr) < 30: sys.exit(f'only {0 if dr is None else len(kr)} features on the reference frame {a.ref}: pick another')
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    S = {}                                   # frame -> (s, tx, ty, inliers)
    for n in range(a.f0, a.f1 + 1):
        if n == a.ref: S[n] = (1.0, 0.0, 0.0, len(kr)); continue
        k, d = orb.detectAndCompute(fr[n - lo], None)
        if d is None or len(k) < 30: continue
        good = [m for m, m2 in (p for p in bf.knnMatch(dr, d, k=2) if len(p) == 2) if m.distance < 0.75 * m2.distance]
        if len(good) < 20: continue
        src = np.float32([kr[m.queryIdx].pt for m in good]); dst = np.float32([k[m.trainIdx].pt for m in good])
        M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0, maxIters=4000, confidence=0.999)
        if M is None or int(inl.sum()) < 15: continue
        s = float(np.hypot(M[0, 0], M[1, 0]))
        S[n] = (s, float(M[0, 2]), float(M[1, 2]), int(inl.sum()))
    ns = list(range(a.f0, a.f1 + 1))
    missing = [n for n in ns if n not in S]
    have = sorted(S)
    if len(have) < 2: sys.exit('fewer than two frames registered: nothing to track')
    ls = np.interp(ns, have, [np.log(S[n][0]) for n in have])
    tx = np.interp(ns, have, [S[n][1] for n in have]); ty = np.interp(ns, have, [S[n][2] for n in have])
    # a light 3-tap smooth (1-2-1) on the transform, ends held: RANSAC is sub-pixel, this only takes the last shimmer out
    def sm(v):
        v = np.asarray(v, float); o = v.copy(); o[1:-1] = (v[:-2] + 2 * v[1:-1] + v[2:]) / 4; return o
    ls, tx, ty = sm(ls), sm(tx), sm(ty)
    out = {}
    for i, n in enumerate(ns):
        s = float(np.exp(ls[i]))
        out[str(n)] = [round(s * box[0] + tx[i], 1), round(s * box[1] + ty[i], 1), round(s * box[2] + tx[i], 1), round(s * box[3] + ty[i], 1)]
    json.dump({'fps': a.fps, 'render': a.render, 'method': 'registration', 'ref': a.ref, 'box': box, 'missing': missing,
               'frames': out}, open(a.out, 'w'), indent=1)
    sc = [float(np.exp(v)) for v in ls]
    print(f'{len(ns)} frames, {len(missing)} interpolated{(" " + str(missing)) if missing else ""}; scale {min(sc):.3f} -> {max(sc):.3f}; '
          f'inliers min {min(S[n][3] for n in have)} -> {a.out}')


if __name__ == '__main__':
    main()
