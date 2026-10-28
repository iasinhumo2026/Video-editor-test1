# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""bake.py: the YELLOW HIGHLIGHTER, baked from the recording under it: a yellow marker band whose text reads dark, wiped
on left to right and locked to a registration track, rendered as an alpha overlay that is laid with a NORMAL blend.

  uv run presets/youtube/default/highlight/bake.py <recording render.mp4> <track.json> --from <frame> --to <frame> --out <overlay.mov>
      [--color #FFE14D]   the marker's yellow
      [--ref <frame>]     the frame whose band area decides the page polarity (default: --to)

2026-10-06: "it should be yellow and then invert the colors so it's like a proper highlight" (after the white
Difference band of 2026-10-05). Inside the band every pixel becomes yellow x the page's light: on a dark page the
recording's luma is inverted first (dark page -> bright, light text -> dark) and stretched so the bare page lands on the
full yellow; on a light page the luma is used as it is (a marker on paper). The text keeps its shapes and reads dark on
yellow either way. Because the overlay carries the finished pixels it needs no blend mode in the editor (one clip, any
lane), but it is FRAME-LOCKED to the recording render it was baked from: comp frame k = render frame from + k, so its
plan cell starts exactly at the recording's start + from/fps, and a re-render of the recording means a re-bake.

The band: the track's box (1920 frame, x2 at 4K), corners rounded min(10, 0.15 h) px for the marker's ends, wiped on over
the registry's DRAW (9) frames, power2.out, the leading edge the marker tip; it holds locked to the track and fades out
over 6 frames that complete 2 frames before the end (graphics-qa's exit). Anti-aliased edges, ProRes 4444.
"""
import argparse, json, subprocess, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'workflows'))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

W, H, DRAW, FPS = 3840, 2160, 9, '24000/1001'


def hexrgb(h):
    h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def band_alpha(box, p, s=2.0):
    """Anti-aliased rounded-rect coverage for a band of the box's full height, wiped to fraction p of its width."""
    x0, y0, x1, y1 = (v * s for v in box)
    w = (x1 - x0) * p
    if w <= 0.5: return None, None
    r = min(10.0, 0.15 * (y1 - y0) / s) * s
    xa, xb, ya, yb = int(np.floor(x0)) - 2, int(np.ceil(x0 + w)) + 2, int(np.floor(y0)) - 2, int(np.ceil(y1)) + 2
    xa, ya, xb, yb = max(0, xa), max(0, ya), min(W, xb), min(H, yb)
    xs = np.arange(xa, xb, dtype=np.float32) + 0.5; ys = np.arange(ya, yb, dtype=np.float32) + 0.5
    X, Y = np.meshgrid(xs, ys)
    cx0, cx1, cy0, cy1 = x0 + r, x0 + w - min(r, w / 2), y0 + r, y1 - r          # the rounded-rect's inner core
    rr = min(r, w / 2)
    dx = np.maximum(np.maximum(cx0 - X, X - cx1), 0); dy = np.maximum(np.maximum(cy0 - Y, Y - cy1), 0)
    d = np.sqrt(dx * dx + dy * dy) - rr                                          # signed distance to the edge
    a = np.clip(0.5 - d, 0, 1)
    return (slice(ya, yb), slice(xa, xb)), a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('render'); ap.add_argument('track')
    ap.add_argument('--from', dest='f0', type=int, required=True); ap.add_argument('--to', dest='f1', type=int, required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--color', default='#FFE14D'); ap.add_argument('--ref', type=int)
    a = ap.parse_args()
    tr = {int(k): v for k, v in json.load(open(a.track))['frames'].items()}
    n = a.f1 - a.f0 + 1
    Ycol = hexrgb(a.color)
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', a.render, '-vf', f'select=between(n\\,{a.f0}\\,{a.f1}),scale={W}:{H},format=rgb24',
                            *passthrough(), '-frames:v', str(n), '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', FPS, '-i', '-',
                            '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p12le', '-alpha_bits', '16', a.out],
                           stdin=subprocess.PIPE)
    frames = []
    for k in range(n):
        buf = dec.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: sys.exit(f'the render ran out at frame {a.f0 + k}')
        frames.append(np.frombuffer(buf, np.uint8).reshape(H, W, 3))
    dec.wait()
    # the page's polarity and level, off the band area of the reference frame (its median luma is the bare page)
    ref = a.ref if a.ref is not None else a.f1
    bx = [int(v * 2) for v in tr[ref]]
    patch = frames[ref - a.f0][bx[1]:bx[3], bx[0]:bx[2]].astype(np.float32) / 255
    luma = patch @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    page = float(np.median(luma)); dark = page < 0.5
    print(f'page luma {page:.3f}: {"dark page, luma inverted" if dark else "light page"}')
    fade0 = n - 8                                                                # fade frames fade0 .. fade0+5, gone 2 before the end
    for k in range(n):
        rgba = np.zeros((H, W, 4), np.uint8)
        p = min(1.0, k / DRAW); p = 1 - (1 - p) * (1 - p)                       # power2.out, width 0 on frame 0
        op = 1.0 if k < fade0 else max(0.0, 1 - ((k - fade0 + 1) / 6) ** 2) if k < fade0 + 6 else 0.0
        sl, al = band_alpha(tr[a.f0 + k], p)
        if sl is not None and op > 0:
            src = frames[k][sl].astype(np.float32) / 255
            L = src @ np.array([0.2126, 0.7152, 0.0722], np.float32)
            t = np.clip((1 - L) / max(1e-3, 1 - page), 0, 1) if dark else np.clip(L / max(1e-3, page), 0, 1)
            col = t[..., None] * Ycol
            rgba[sl][..., :3] = np.round(col * 255).astype(np.uint8)
            rgba[sl][..., 3] = np.round(al * op * 255).astype(np.uint8)
        enc.stdin.write(rgba.tobytes())
    enc.stdin.close(); enc.wait()
    print(f'{n} frames ({a.f0}-{a.f1}), {round(n * 1001 / 24000, 4)} s -> {a.out}')


if __name__ == '__main__':
    main()
