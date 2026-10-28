#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""render-diff.py: prove two renders of the SAME graphic are the same picture.

  uv run workflows/render-diff.py <render-a> <render-b> [--frames 5] [--max-mean 8] [--max-hot 0.01] [--quiet]

Samples N evenly spaced frames from both files, scales the larger render down to the smaller one's frame
(a resolution change must not change the picture), composites alpha on mid-grey, and prints per sample the
mean absolute RGB difference and the share of "hot" pixels (off by more than 40/255). Exit 0 = PARITY OK,
exit 1 = PARITY FAIL on any sample, exit 2 = unreadable input.

Why (2026-09-07, your-job): the intro's 27 graphics were re-rendered at 3840x2160 for a 4K master
with `#root{zoom:2}` and reported "pixel-identical" from the mechanism, unmeasured. The three punch-cuts had
shipped 77x43 px off-centre with the vignette on the corner (Chrome double-resolves percentage
transform-origins and gradient positions under CSS zoom); the 24 overlays, carrying no such percentage,
really were identical and hid the fault. Measured, the broken renders sat at mean 14/64/27 with 6–48 %
hot pixels; a correct re-render sits at mean 4–5 (the film-grain pass is random per render) with under
0.5 % hot. The thresholds sit between those two populations. `workflows/graphics-qa.py` runs this as its
`parity` check against the newest other-resolution sibling of every placed render.
"""
import json, subprocess, sys
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
import numpy as np

HOT = 40  # per-pixel mean RGB difference that counts as "wrong", well above grain (≤ 26 at p99)


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,duration,nb_frames', '-of', 'json', path], capture_output=True, text=True)
    if r.returncode:
        return None
    s = json.loads(r.stdout)['streams'][0]
    return dict(w=int(s['width']), h=int(s['height']), dur=float(s.get('duration') or 0), frames=int(s.get('nb_frames') or 0))


def frame(path, t, w, h):
    """One frame at t, scaled to w x h, composited on mid-grey -> float RGB array."""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.4f}', '-i', path, '-frames:v', '1',
                        '-vf', f'scale={w}:{h}:flags=lanczos,format=rgba', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'],
                       capture_output=True)
    if len(r.stdout) < w * h * 4:
        return None
    im = np.frombuffer(r.stdout[:w * h * 4], np.uint8).reshape(h, w, 4).astype(np.float32)
    a = im[..., 3:4] / 255.0
    return im[..., :3] * a + 128.0 * (1 - a)


def compare(a, b, n=5, max_mean=8.0, max_hot=0.01, quiet=False):
    pa, pb = probe(a), probe(b)
    if not pa or not pb:
        print(f'cannot read {a if not pa else b}'); return 2
    w, h = min(pa['w'], pb['w']), min(pa['h'], pb['h'])
    dur = min(pa['dur'], pb['dur'])
    if not quiet:
        print(f"A {pa['w']}x{pa['h']} {pa['frames']}f {pa['dur']:.3f}s  {a}")
        print(f"B {pb['w']}x{pb['h']} {pb['frames']}f {pb['dur']:.3f}s  {b}")
        if pa['frames'] and pb['frames'] and pa['frames'] != pb['frames']:
            print(f"⚠ frame counts differ ({pa['frames']} vs {pb['frames']}): comparing the common {dur:.3f}s")
        print(f'measured at {w}x{h}, {n} samples; limits mean ≤ {max_mean}, hot(>{HOT}) ≤ {max_hot * 100:.1f}%')
    worst = []
    for i in range(n):
        t = min(dur * (i + 0.5) / n, max(dur - 0.05, 0))
        fa, fb = frame(a, t, w, h), frame(b, t, w, h)
        if fa is None or fb is None:
            print(f'cannot decode a frame at {t:.2f}s'); return 2
        d = np.abs(fa - fb).mean(axis=2)
        mean, hot = float(d.mean()), float((d > HOT).mean())
        ok = mean <= max_mean and hot <= max_hot
        worst.append((ok, t, mean, hot))
        if not quiet:
            print(f"  {'✓' if ok else '✗'} {t:6.2f}s  mean {mean:5.1f}  p99 {np.percentile(d, 99):5.1f}  hot {hot * 100:5.2f}%")
    bad = [x for x in worst if not x[0]]
    if bad:
        t, mean, hot = max(bad, key=lambda x: x[2])[1:]
        print(f'PARITY FAIL: {len(bad)}/{n} samples differ, worst at {t:.2f}s mean {mean:.1f} hot {hot * 100:.1f}% '
              f'(limits {max_mean} / {max_hot * 100:.1f}%)')
        return 1
    m = max(x[2] for x in worst)
    print(f'PARITY OK: {n} samples, worst mean {m:.1f}')
    return 0


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0].startswith('-'):
        sys.exit(__doc__)

    def opt(flag, default, cast=float):
        return cast(a[a.index(flag) + 1]) if flag in a else default

    sys.exit(compare(a[0], a[1], n=opt('--frames', 5, int), max_mean=opt('--max-mean', 8.0),
                     max_hot=opt('--max-hot', 0.01), quiet='--quiet' in a))


if __name__ == '__main__':
    main()
