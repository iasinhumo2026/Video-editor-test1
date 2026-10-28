#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["numpy", "opencv-python-headless"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""object-track.py — per-frame rigid track of a face or object a detector cannot hold, for pinning a graphic to it.

    uv run workflows/object-track.py <video> --regions regions.json [--out track.json]
                                     [--downscale N] [--dup-thresh 0.5] [--preview dir]

For the subject hand-track.py or a face landmarker drops: a film or CGI character, a stylised face,
a prop, a subject through a flash. Each REGION is a polygon drawn on one REFERENCE frame, the frame
where the graphic's anchors were MEASURED (a landmark pass on the one frame the detector does hold,
a colour blob, or by eye off a still). The region is tracked as a similarity (translate + rotate +
uniform scale): KLT features inside the polygon, forward-backward checked (< 1 px), a RANSAC fit
(1.5 px), chained frame to frame forward AND back from the reference across the region's span.
The tracking frame is the source scaled to about 1920 wide (--downscale, auto), the size the
parameters were tuned at; every number in and out is SOURCE px.

regions.json (frames are 0-based decoded frame indices):

    {"head": {"ref": 44, "span": [34, 100], "poly": [[2150, 420], [2600, 380], [2500, 880], [2140, 760]]},
     "prop": {"ref": 0, "span": [0, 21], "poly": [[1280, 1140], [2533, 1500], [1280, 1600]],
              "blind": {"span": [22, 33], "from": 21, "patch": [1450, 850, 500, 380],
                        "radius": 300, "min_score": 0.2}}}

  - One region per POSE. A similarity cannot follow a head that turns or throws back: give each pose
    its own region and reference frame, and switch the graphic between them on the fastest frame of
    the move, where motion blur hides the jump.
  - Draw the polygon on rigid, textured parts; leave out anything that changes every frame
    (lightning, a talking mouth, a screen, hair in wind): it drags the fit.
  - `blind` is a span KLT cannot see (a white flash, a flare), outside `span`: the high-passed
    `patch` (x, y, w, h on frame `from`, the last clean frame of the chain) is template-matched in
    each blind frame within `radius` px. A score >= `min_score` is a translation added to `from`'s
    matrix; a frame under it is interpolated between matches, and held past the last one. A doubled
    frame takes the shift of the picture it repeats.
  - A doubled frame (12 fps motion on a 24 fps plate: mean luma difference under --dup-thresh)
    holds the previous pose instead of fitting noise.
  - A chain that loses the region (under 8 consistent points) STOPS there and reports it. A tracked
    graphic spans only the frames its chain reached (hand-track.py's RAW-run rule): never
    interpolate across a loss.

Output (default <video>.objtrack.json):

    {"video", "fps", "width", "height", "downscale",
     "regions": {name: {"ref", "span", "poly", "runs": [[first, last], ...],
                        "lost": [{"at": f, "to": f±1, "points": n}],
                        "frames": {"<f>": {"m": [[a, b, tx], [c, d, ty]], "inliers": n}}}}}

`m` maps a SOURCE px point measured on the region's reference frame to SOURCE px on frame f:
[x', y'] = m @ [x, y, 1]. `inliers`: >= 0 the RANSAC inliers of that step, -1 the reference frame,
-2 a doubled frame (held), -3 a blind frame matched, -4 a blind frame inferred (interpolated or held).
The renderer carries each anchor through `m` on every frame and BAKES the path into the render,
never editor keyframes (graphics-build § Stage 2). --preview writes every tracked frame with each
region's polygon drawn on it: look at it before building on the track.
"""
import argparse, json, subprocess, sys
# Windows consoles/pipes default to cp1252, which can't encode the ⚠ in this script's status
# lines: a cosmetic print must never kill a pipeline step. Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)
from cv2_io import imwrite  # noqa: E402  (never cv2.imwrite: it fails silently on a non-ASCII Windows path)

import cv2
import numpy as np

REF, DOUBLED, MATCHED, INFERRED = -1, -2, -3, -4
MIN_POINTS = 8
LK = dict(winSize=(31, 31), maxLevel=4, criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, 0.01))
HOLD = np.array([[1.0, 0, 0], [0, 1.0, 0]])


def probe(video):
    """(width, height, fps) of the decoded picture: a rotated phone clip decodes upright."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate:stream_tags=rotate:stream_side_data=rotation",
                          "-of", "json", str(video)], capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    w, h = int(s["width"]), int(s["height"])
    rot = [d["rotation"] for d in s.get("side_data_list", []) if "rotation" in d] or [s.get("tags", {}).get("rotate", 0)]
    if int(float(rot[0])) % 180:
        w, h = h, w
    num, _, den = str(s.get("r_frame_rate", "0/1")).rstrip(",").partition("/")
    fps = float(num) / float(den) if den and float(den) else float(num or 0)
    return w, h, fps


def read_frames(video, size, keep=None, color=False):
    """{index: frame} of the decoded frames in `keep` (None = all) at `size`, and the frames read."""
    w, h = size
    shape = (h, w, 3) if color else (h, w)
    nbytes = int(np.prod(shape))
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "bgr24" if color else "gray", *passthrough(), "-"], stdout=subprocess.PIPE)
    out, n, last = {}, 0, max(keep) if keep else None
    while last is None or n <= last:
        buf = p.stdout.read(nbytes)
        if len(buf) < nbytes:
            break
        if keep is None or n in keep:
            out[n] = np.frombuffer(buf, np.uint8).reshape(shape)
        n += 1
    killed = last is not None and n > last
    if killed:
        p.kill()
    p.stdout.close()
    if p.wait() and not killed and not out:
        sys.exit(f"ffmpeg could not decode {video}")
    return out, n


def step(g0, g1, poly):
    """Similarity (2x3) carrying g0's pixels inside `poly` onto g1, and its inlier count; None when lost."""
    mask = np.zeros_like(g0)
    cv2.fillPoly(mask, [np.round(poly).astype(np.int32)], 255)
    p0 = cv2.goodFeaturesToTrack(g0, 500, 0.005, 5, mask=mask, blockSize=7)
    if p0 is None or len(p0) < MIN_POINTS:
        return None, 0 if p0 is None else len(p0)
    p1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, p0, None, **LK)
    pb, st2, _ = cv2.calcOpticalFlowPyrLK(g1, g0, p1, None, **LK)
    ok = (st[:, 0] == 1) & (st2[:, 0] == 1) & (np.linalg.norm(p0 - pb, axis=2)[:, 0] < 1.0)
    if ok.sum() < MIN_POINTS:
        return None, int(ok.sum())
    T, inl = cv2.estimateAffinePartial2D(p0[ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=1.5,
                                         maxIters=4000, confidence=0.999)
    if T is None:
        return None, 0
    return T, int(inl.sum())


def chain(gray, ref, span, poly, ds=1, dup_thresh=0.5):
    """Chain one region from `ref` to every frame of `span` it can reach, forward and back.
    gray: {index: frame at 1/ds of the source}; poly: SOURCE px on the ref frame.
    Returns ({f: (3x3 ref -> f in SOURCE px, inliers)}, [{"at", "to", "points"} per loss])."""
    poly_ds = np.asarray(poly, float) / ds
    out, lost = {ref: (np.eye(3), REF)}, []
    for d in (1, -1):
        M, f = np.eye(3), ref
        while span[0] <= f + d <= span[1] and f + d in gray:
            g0, g1 = gray[f], gray[f + d]
            if np.abs(g0.astype(np.int16) - g1).mean() < dup_thresh:  # a doubled frame: same picture, same pose
                T, n = HOLD, DOUBLED
            else:
                T, n = step(g0, g1, cv2.transform(poly_ds[None], M[:2])[0])
                if T is None:
                    lost.append({"at": f, "to": f + d, "points": n})
                    break
            M = np.vstack([T, [0, 0, 1]]) @ M
            f += d
            out[f] = (M.copy(), n)
    S = np.diag([ds, ds, 1.0])
    Si = np.linalg.inv(S)
    return {f: (S @ m @ Si, n) for f, (m, n) in sorted(out.items())}, lost


def highpass(gray):
    """Luma minus its blur, over its local contrast: a flash's lift and wash drop out, edges stay."""
    g = gray.astype(np.float32)
    h = g - cv2.GaussianBlur(g, (0, 0), 12)
    return h / (cv2.GaussianBlur(np.abs(h), (0, 0), 25) + 2)


def blind_fill(full, src, frames, patch, radius=300, min_score=0.2, dup_thresh=0.5):
    """Shift of `patch` (x, y, w, h on frame `src`, SOURCE px) in each blind frame, by high-pass template match.
    full: {index: full-res gray}. A frame that doubles the one before it takes that frame's shift, so the
    interpolation between matches runs over the plate's real poses, never its repeats.
    Returns ({f: (dx, dy, measured)}, {f: score})."""
    x0, y0, w, h = (int(v) for v in patch)
    H, W = full[src].shape
    tpl = highpass(full[src])[y0:y0 + h, x0:x0 + w]
    sx0, sy0, sx1, sy1 = max(x0 - radius, 0), max(y0 - radius, 0), min(x0 + w + radius, W), min(y0 + h + radius, H)
    first = {}  # blind frame -> the first frame of the picture it repeats (itself when it moved)
    for f in frames:
        g = f
        while g - 1 in full and np.abs(full[g].astype(np.int16) - full[g - 1]).mean() < dup_thresh:
            g -= 1
        first[f] = g
    poses = sorted(set(first.values()) - {src})
    keys, scores = {src: (0.0, 0.0)}, {}
    for f in poses:
        res = cv2.matchTemplate(highpass(full[f])[sy0:sy1, sx0:sx1], tpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, loc = cv2.minMaxLoc(res)
        scores[f] = float(score)
        if score >= min_score:
            keys[f] = (float(loc[0] + sx0 - x0), float(loc[1] + sy0 - y0))
    at, ks = {src: (0.0, 0.0, True)}, sorted(keys)
    for f in poses:
        if f in keys:
            at[f] = (*keys[f], True)
            continue
        lo, hi = [k for k in ks if k < f], [k for k in ks if k > f]
        if lo and hi:  # a pose between two matches: interpolated
            a, b = lo[-1], hi[0]
            t = (f - a) / (b - a)
            at[f] = (keys[a][0] + t * (keys[b][0] - keys[a][0]), keys[a][1] + t * (keys[b][1] - keys[a][1]), False)
        else:  # past the last match: held
            at[f] = (*keys[lo[-1] if lo else hi[0]], False)
    return {f: at[first[f]] for f in frames}, {f: scores.get(first[f], 1.0) for f in frames}


def runs(frames):
    out = []
    for f in sorted(frames):
        if out and f == out[-1][1] + 1:
            out[-1][1] = f
        else:
            out.append([f, f])
    return out


def load_regions(path):
    regions = json.loads(Path(path).read_text(encoding="utf-8"))
    for name, r in regions.items():
        a, b = r["span"]
        if not a <= r["ref"] <= b:
            sys.exit(f"{name}: ref {r['ref']} is outside its span {a}..{b}")
        if len(r["poly"]) < 3:
            sys.exit(f"{name}: poly needs at least 3 points")
        bl = r.get("blind")
        if bl:
            if not (bl["span"][1] < a or bl["span"][0] > b):
                sys.exit(f"{name}: blind span {bl['span']} overlaps the KLT span {a}..{b}: blind frames sit outside it")
    return regions


def main():
    ap = argparse.ArgumentParser(description="Rigid KLT track of regions a detector cannot hold.")
    ap.add_argument("video")
    ap.add_argument("--regions", required=True, help="regions.json: {name: {ref, span, poly, blind?}}")
    ap.add_argument("--out", default=None)
    ap.add_argument("--downscale", type=int, default=0, help="tracking scale divisor (0 = auto, about 1920 wide)")
    ap.add_argument("--dup-thresh", type=float, default=0.5, help="mean luma diff under which a frame is a double")
    ap.add_argument("--preview", default=None, help="write annotated tracked frames here")
    a = ap.parse_args()

    regions = load_regions(a.regions)
    W, H, fps = probe(a.video)
    ds = a.downscale or max(1, round(W / 1920))
    size = (W // ds, H // ds)
    need = {f for r in regions.values() for f in range(r["span"][0], r["span"][1] + 1)}
    gray, got = read_frames(a.video, size, need)
    if got <= max(need):
        print(f"⚠ the video has {got} frames (0..{got - 1}): every span past that is cut short")

    blind_need = {f for r in regions.values() if r.get("blind")
                  for f in [r["blind"]["from"], *range(r["blind"]["span"][0], r["blind"]["span"][1] + 1)]}
    full = read_frames(a.video, (W, H), blind_need)[0] if blind_need else {}

    res = {}
    for name, r in regions.items():
        c, lost = chain(gray, r["ref"], r["span"], r["poly"], ds, a.dup_thresh)
        bl = r.get("blind")
        if bl:
            src = bl["from"]
            frames = [f for f in range(bl["span"][0], bl["span"][1] + 1) if f in full]
            if src not in c or src not in full:
                print(f"⚠ {name}: blind 'from' frame {src} is not on the chain ({min(c)}..{max(c)}): blind span skipped")
            else:
                shifts, scores = blind_fill(full, src, frames, bl["patch"], bl.get("radius", 300),
                                            bl.get("min_score", 0.2), a.dup_thresh)
                for f, (dx, dy, measured) in shifts.items():
                    m = c[src][0].copy()
                    m[0, 2] += dx
                    m[1, 2] += dy
                    c[f] = (m, MATCHED if measured else INFERRED)
                    print(f"  {name} blind {f}: score {scores[f]:.3f} shift {dx:+.1f},{dy:+.1f}"
                          f"{'' if measured else ' (inferred)'}")
        c = dict(sorted(c.items()))
        res[name] = {"ref": r["ref"], "span": r["span"], "poly": r["poly"], "runs": runs(c), "lost": lost,
                     "frames": {str(f): {"m": np.round(m[:2], 6).tolist(), "inliers": n} for f, (m, n) in c.items()}}
        fitted = [n for _, n in c.values() if n >= 0]
        print(f"{name}: frames {min(c)}..{max(c)} ({len(c)}; KLT span {r['span'][0]}..{r['span'][1]}), "
              f"min inliers {min(fitted) if fitted else '-'}")
        for L in lost:
            print(f"⚠ {name}: lost at {L['at']}->{L['to']} ({L['points']} consistent points): the chain stops there")

    dest = Path(a.out) if a.out else Path(a.video).with_suffix(".objtrack.json")
    dest.write_text(json.dumps({"video": str(Path(a.video).resolve()), "fps": fps, "width": W, "height": H,
                                "downscale": ds, "regions": res}, indent=1), encoding="utf-8")
    print(f"[object-track] {len(res)} region(s) @ {fps:g}fps, tracked at 1/{ds} -> {dest}")

    if a.preview:
        pv = Path(a.preview)
        pv.mkdir(parents=True, exist_ok=True)
        tracked = {int(f) for r in res.values() for f in r["frames"]}
        colors = [(0, 255, 140), (255, 160, 0), (60, 60, 255), (255, 0, 255), (0, 220, 255)]
        for f, img in read_frames(a.video, size, tracked, color=True)[0].items():
            img = img.copy()
            for i, (name, r) in enumerate(res.items()):
                v = r["frames"].get(str(f))
                if not v:
                    continue
                pts = cv2.transform(np.asarray(r["poly"], float)[None], np.asarray(v["m"]))[0] / ds
                col = colors[i % len(colors)]
                cv2.polylines(img, [np.round(pts).astype(np.int32)], True, col, 2)
                cv2.putText(img, f"{name} {v['inliers']}", tuple(int(q) for q in pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
            imwrite(pv / f"{f:04d}.jpg", img)
        print(f"  preview frames -> {pv}")


if __name__ == "__main__":
    main()
