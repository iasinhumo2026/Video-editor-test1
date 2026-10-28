#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""framing-continuity.py: catch a framing jump at a cut, the background moving or scaling between the last frame
before a cut and the first frame after it.

  uv run workflows/framing-continuity.py <export.mp4> --cuts projects/<job>/transcript/cuts.json
  uv run workflows/framing-continuity.py <export.mp4> --cuts 127.169,131.02 [--patch x,y,w,h ...] [--max-px 4]

  --cuts C          an EDL (its `_timeline` readback when every segment carries one, else the cumulative kept
                    durations) or cut times in seconds, comma- or space-separated
  --offset S        seconds subtracted from every cut time: where the export's first frame sits on the cut clock
                    (default 0, an export of the whole sequence)
  --patch x,y,w,h   measure on these patches (export pixels) instead of the ring; repeatable. You vouch they
                    are bare background, so any one of them that moves FAILs the cut
  --max-px N        the largest background move a cut may carry, in export pixels (default 4)
  --max-scale F     the largest scale change a cut may carry (default 0.01 = 1%)
  --quiet           one line per cut (it still names the patches it measured on)

At each cut the last frame before it and the first frame after it are decoded frame-exact, with the two frames
beside each (three per side). The move is measured on BACKGROUND patches: a ring of 12 round the frame's border
(corners and edges, never the centre, where the speaker is). A patch counts only when it has detail on both sides
of the cut (a flat wall or a ceiling's shading matches itself at any shift), holds still inside each side (a patch
that changes within three frames is a moving speaker, an animating graphic or a camera move), and still matches
itself once the shift is taken out (correlation of the detail after alignment). The shift is phase correlation
(numpy FFT, sub-pixel); the scale comes from how the moves vary across the frame, because a zoom moves every patch
away from its centre in proportion to the distance: d = (s - 1)(p - centre) + t.

THE PATCHES MEASURE THE COMPOSITE, so a HOLD PROVES NOTHING ON ITS OWN. A graphic that spans the cut is the same on
both sides: a patch under it reads 0 px however far the footage behind it moved (a hand-picked patch did exactly
that on the incident below, and on that frame two of the ring's patches sit under a card). So holds never outvote a
move: two or more patches that moved together (the same shift, or for three or more one zoom + shift, each within
2 px) FAIL the cut however many held. One patch that moved alone is read on the RING of footage round it (half a
patch wide, the patch left out), tile by tile:
  - most of the ring's tiles move with it and none holds: the jump is the framing, the patches that held are under
    a graphic, and the cut FAILs;
  - 4 or more tiles move with it and some hold: an object bigger than the patch (a shoulder, a chair back, a panel
    scrolling in a screen recording) and the framing seen through a gap in a graphic look the same from the
    composite, so the cut is UNMEASURED (exit 2), never a pass. Look at it, or re-run with --patch on bare
    background away from the mover. On real talking-head shorts a shoulder crossing a bottom patch does this;
  - fewer tiles move (the mover stays inside its patch, a hand, a waveform's bars), or the ring is flat: it is local
    motion, named under the verdict and not failed.
THE ONE CASE LEFT TO THE EYE: footage that shows through a gap in a graphic no wider than about a tenth of a patch
round the patch looks exactly like something moving inside the patch, and is only named. Read any "moved alone"
line. Every patch's box and read is printed. The cleanest input is a draft exported with the graphics tracks off.

Exit 0 = every cut PASS. Exit 1 = a cut FAILs: patches moved together more than --max-px (or any one --patch
patch did, or one patch did with the footage round it), or the patches that held fit a scale change beyond
--max-scale. Exit 2 = unreadable input, or a cut UNMEASURED: no patch passed the gates, every counted patch moved
and no two agree, or a lone mover took part of the footage round it along. A deliberate reframe (split to full frame, a punch-in, a full-screen
graphic) reads UNMEASURED, and so does a jump wider than about a third of a patch (90 px on a 1080-wide frame): the
patches stop matching. Neither is ever reported as a pass.

Calibrated on a shipped short's 47 real cuts (two exports of the same talking-head job, graphics and captions on):
0 false fails, the background patches reading 0.0-0.3 px. The frames either side of the incident's cut read 32.9 px
on four agreeing patches while two patches under a card held at 0.0. A second short that reframes on purpose at
most cuts (split to full frame, punch-ins) read 9 PASS, 12 UNMEASURED, 0 FAIL: run it there on the cuts either side
of the substituted clip (--cuts <in>,<out>).

Why this exists (2026-09-22/23): a short's ad CTA was laid from a lip-sync clip generated on a 9:16 crop that sat
36 source px right of the timeline's framing, so the static wall jumped 33 px sideways at the cut. It shipped to
review twice, the second time because the 4K re-sync that fixed it was rendered and never laid. A four-frame look
called the framing fine both times; the creator caught it on playback. Run this on a draft export after laying any
substituted clip (a lip-sync render, a re-take, a re-rendered segment).
"""
import argparse, json, re, subprocess, sys
from itertools import combinations
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
import numpy as np

SIDE = 3             # frames decoded on each side of a cut: the one next to it, and two more to prove it holds still
PATCH_FRAC = 0.25    # auto patch side, as a share of the frame's short side (270 px on 1080)
MARGIN_FRAC = 0.03   # auto patch inset from the frame edge
TEX_MIN = 1.0        # mean abs `detail` (luma); below it the patch is flat: a plain wall, a black shirt, a ceiling's shading
MOTION_MAX = 4.0     # mean abs luma change between neighbouring frames of one side; above it the patch is moving
NCC_MIN = 0.5        # correlation of the detail once the shift is taken out; below it the patch does not match itself across the cut
HP_RADIUS = 4        # half-res px: the box blur `detail` subtracts, so structure finer than 16 px is what counts
LOWPASS = 0.1        # cycles/px: the cross-power spectrum is tapered above this, so noise and grain cannot place the peak
SPREAD_FRAC = 0.25   # patches that decide a cut must span this share of the short side (a zoom needs a lever arm)
AGREE_PX = 2.0       # a moved patch agrees with a zoom + shift when the model predicts its move within this (px)
RING_MARGIN = 0.25   # a ring tile moved with a lone mover (or held) when it matches this much better moved than held (or the reverse)
RING_TILE = 0.125    # ring tile side, as a share of the patch side: small enough that a big object's spill leaves tiles clear
RING_UNCLEAR = 4     # a lone mover with this many ring tiles moving with it, and some holding, cannot be read: UNMEASURED


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,avg_frame_rate,r_frame_rate,start_time,duration:format=start_time,duration',
                        '-of', 'json', str(path)], capture_output=True, text=True)
    if r.returncode:
        return None
    j = json.loads(r.stdout)
    if not j.get('streams'):
        return None
    s, f = j['streams'][0], j.get('format') or {}
    fps = None
    for key in ('avg_frame_rate', 'r_frame_rate'):
        try:
            v = Fraction(s.get(key) or '0/0')
        except (ValueError, ZeroDivisionError):
            continue
        if v > 0:
            fps = float(v)
            break
    lead = float(s.get('start_time') or 0) - float(f.get('start_time') or 0)  # -ss counts from the container start
    return dict(w=int(s['width']), h=int(s['height']), fps=fps, lead=lead,
                dur=float(s.get('duration') or f.get('duration') or 0))


def read_frames(path, first, count, info):
    """Frames first .. first+count-1 of the video, decoded frame-exact, as float32 luma (h, w)."""
    first = max(0, first)
    if count <= 0:
        return []
    w, h = info['w'], info['h']
    # half a frame early: a timestamp a few microseconds under the frame grid (a 90 kHz timescale) is still read
    t = max(0.0, info['lead'] + (first - 0.5) / info['fps'])
    pre = max(0.0, t - 2.0)  # a fast input seek to near the frame, then the exact output seek (-ss after -i) the rest of the way
    # passthrough sync is load-bearing: the first frame lands half a frame into the output, and the default
    # constant-rate sync fills that gap by DUPLICATING it whenever the file carries audio (every real export), so a
    # read of k-3..k-1 came back [k-3, k-3, k-2] and the last frame before the cut was never read. The flag is
    # probed (ffmpeg_compat.py): ffmpeg older than 5.1 (Ubuntu 22.04 ships 4.4) has no -fps_mode, 9.0 has no -vsync
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{pre:.6f}', '-i', str(path), '-ss', f'{t - pre:.6f}',
                        '-frames:v', str(count), *passthrough(), '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                       capture_output=True)
    if r.returncode and not r.stdout:  # an ffmpeg that cannot run the read says so
        err = r.stderr.decode(errors='replace').strip().splitlines()
        raise RuntimeError(f'ffmpeg could not read frames from {path}: {err[-1] if err else f"exit {r.returncode}"}')
    n = len(r.stdout) // (w * h)
    return [np.frombuffer(r.stdout[i * w * h:(i + 1) * w * h], np.uint8).reshape(h, w).astype(np.float32)
            for i in range(n)]


def load_cuts(spec, offset=0.0):
    """([(t_out, t_in, label)], source): where the outgoing shot ends and the incoming one starts, on the export's clock."""
    p = Path(spec)
    if p.is_file():
        segs = json.loads(p.read_text(encoding='utf-8'))['segments']
        name = lambda s: Path(s.get('media') or s.get('clip') or '?').name  # `media` = the substituted render laid in its place
        if segs and all(isinstance(s.get('_timeline'), list) and len(s['_timeline']) == 2 for s in segs):
            segs = sorted(segs, key=lambda s: float(s['_timeline'][0]))
            return [(float(a['_timeline'][1]) - offset, float(b['_timeline'][0]) - offset, f'{name(a)} → {name(b)}')
                    for a, b in zip(segs, segs[1:])], 'the EDL\'s _timeline'
        out, t = [], 0.0
        for a, b in zip(segs, segs[1:]):
            t += float(a['end']) - float(a['start'])
            out.append((t - offset, t - offset, f'{name(a)} → {name(b)}'))
        return out, 'the EDL\'s cumulative kept durations'
    try:
        ts = [float(x) for x in re.split(r'[,\s]+', spec.strip()) if x]
    except ValueError:
        raise ValueError(f'--cuts {spec!r} is neither a file nor a list of seconds')
    return [(t - offset, t - offset, '') for t in ts], 'the list'


def auto_patches(w, h):
    """The ring of patches round the frame's border, about 1.5 patches apart: 12 on a 9:16 or a 16:9 frame."""
    s = int(round(PATCH_FRAC * min(w, h)))
    m = int(round(MARGIN_FRAC * min(w, h)))

    def stops(span):
        n = max(2, int(round((span - 2 * m - s) / (1.5 * s))) + 1)
        return [int(round(m + i * (span - 2 * m - s) / (n - 1))) for i in range(n)]
    xs, ys = stops(w), stops(h)
    nx, ny = len(xs), len(ys)
    out = [('top-left', (xs[0], ys[0], s, s)), ('top-right', (xs[-1], ys[0], s, s)),
           ('bottom-left', (xs[0], ys[-1], s, s)), ('bottom-right', (xs[-1], ys[-1], s, s))]
    out += [(f'top {i + 1}/{nx}', (xs[i], ys[0], s, s)) for i in range(1, nx - 1)]
    out += [(f'bottom {i + 1}/{nx}', (xs[i], ys[-1], s, s)) for i in range(1, nx - 1)]
    out += [(f'left {j + 1}/{ny}', (xs[0], ys[j], s, s)) for j in range(1, ny - 1)]
    out += [(f'right {j + 1}/{ny}', (xs[-1], ys[j], s, s)) for j in range(1, ny - 1)]
    return out


def detail(p):
    """The patch's structure at 2-16 px: a 2x2 average (sensor noise is not texture) minus a box blur (a smooth
    shading gradient is not texture either: it correlates with itself at every shift)."""
    q = p[:p.shape[0] // 2 * 2, :p.shape[1] // 2 * 2]
    q = q.reshape(q.shape[0] // 2, 2, q.shape[1] // 2, 2).mean(axis=(1, 3))
    r = HP_RADIUS
    k = 2 * r + 1
    c = np.pad(q, r, mode='edge').cumsum(axis=0)
    c = (np.vstack([np.zeros((1, c.shape[1])), c])[k:] - np.vstack([np.zeros((1, c.shape[1])), c])[:-k]) / k
    c = c.cumsum(axis=1)
    c = (np.hstack([np.zeros((c.shape[0], 1)), c])[:, k:] - np.hstack([np.zeros((c.shape[0], 1)), c])[:, :-k]) / k
    return q - c


def texture(p):
    return float(np.abs(detail(p)).mean())


def shift(b, a):
    """(dx, dy): how far the picture in patch b moved to become patch a (+x right, +y down), sub-pixel."""
    h, w = b.shape
    win = np.outer(np.hanning(h), np.hanning(w))
    fb = np.fft.fft2((b - b.mean()) * win)
    fa = np.fft.fft2((a - a.mean()) * win)
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-9
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.fftfreq(w)[None, :]
    r *= np.exp(-(fx ** 2 + fy ** 2) / (2 * LOWPASS ** 2))
    c = np.fft.ifft2(r).real
    iy, ix = np.unravel_index(int(np.argmax(c)), c.shape)

    def sub(cm, c0, cp):  # parabola through the peak and its two neighbours
        d = cm - 2 * c0 + cp
        return 0.5 * (cm - cp) / d if d < 0 else 0.0
    dy = iy + sub(c[(iy - 1) % h, ix], c[iy, ix], c[(iy + 1) % h, ix])
    dx = ix + sub(c[iy, (ix - 1) % w], c[iy, ix], c[iy, (ix + 1) % w])
    return (dx - w if dx > w / 2 else dx), (dy - h if dy > h / 2 else dy)


def match(b, a, dx, dy):
    """Normalised cross-correlation of b's and a's detail over their overlap once a is moved back by (dx, dy)."""
    h, w = b.shape
    if abs(dx) >= w or abs(dy) >= h:
        return 0.0
    u = detail(b[max(0, -dy):h - max(0, dy), max(0, -dx):w - max(0, dx)])
    v = detail(a[max(0, dy):h - max(0, -dy), max(0, dx):w - max(0, -dx)])
    u, v = u - u.mean(), v - v.mean()
    den = float(np.sqrt((u * u).sum() * (v * v).sum()))
    return float((u * v).sum() / den) if den > 0 else 0.0


def centroid(p):
    """Where a patch's texture sits (its gradient-energy centroid): the point its shift is measured at."""
    gy, gx = np.gradient(p)
    e = gx * gx + gy * gy
    tot = float(e.sum())
    if tot <= 0:
        return (p.shape[1] - 1) / 2, (p.shape[0] - 1) / 2
    ys, xs = np.indices(p.shape)
    return float((xs * e).sum() / tot), float((ys * e).sum() / tot)


def measure(before, after, name, box):
    x, y, pw, ph = box
    bs = [f[y:y + ph, x:x + pw] for f in before]
    as_ = [f[y:y + ph, x:x + pw] for f in after]
    b, a = bs[-1], as_[0]
    tex = min(texture(b), texture(a))
    motion = max([float(np.abs(p - q).mean()) for side in (bs, as_) for p, q in zip(side, side[1:])] + [0.0])
    dx, dy = shift(b, a)
    x2, y2 = x + int(round(dx)), y + int(round(dy))
    H, W = after[0].shape
    if (x2, y2) != (x, y) and 0 <= x2 and x2 + pw <= W and 0 <= y2 and y2 + ph <= H:
        # re-cut the after patch where the picture went and measure what is left: the window pulls a large shift
        # toward 0 (33 px read as 32), a small one it measures true
        a2 = after[0][y2:y2 + ph, x2:x2 + pw]
        rx, ry = shift(b, a2)
        dx, dy = x2 - x + rx, y2 - y + ry
        ncc = match(b, a2, int(round(rx)), int(round(ry)))
    else:
        ncc = match(b, a, int(round(dx)), int(round(dy)))
    cx, cy = centroid(b)
    why = (f'flat (texture {tex:.1f} < {TEX_MIN})' if tex < TEX_MIN else
           f'moving (motion {motion:.1f} > {MOTION_MAX})' if motion > MOTION_MAX else
           f'no match (ncc {ncc:.2f} < {NCC_MIN})' if ncc < NCC_MIN else None)
    return dict(name=name, box=box, dx=dx, dy=dy, ncc=ncc, tex=tex, motion=motion, at=(x + cx, y + cy), why=why)


def surround(before, after, m):
    """(tiles that moved with the patch, tiles that held, tiles read) on the ring of footage round a patch, half a
    patch wide, the patch itself left out, cut into tiles RING_TILE of a patch across; None when no tile has the
    detail to say. A tile moved when it matches clearly better at the patch's move than at 0, held when the reverse.
    A framing jump moves every tile it can see; an object bigger than the patch spills into some tiles, but the
    tiles past its edge (the ring's corners first) are background, and they hold."""
    x, y, pw, ph = m['box']
    H, W = before.shape
    e = max(pw, ph) // 2
    ix, iy = int(round(m['dx'])), int(round(m['dy']))
    # the ring's box, clipped so both it and its copy moved by (ix, iy) stay in the frame
    x0, y0 = max(0, x - e, -ix), max(0, y - e, -iy)
    x1, y1 = min(W, x + pw + e, W - ix), min(H, y + ph + e, H - iy)
    if x1 - x0 < 32 or y1 - y0 < 32:
        return None
    b = detail(before[y0:y1, x0:x1])
    moved, held = detail(after[y0 + iy:y1 + iy, x0 + ix:x1 + ix]), detail(after[y0:y1, x0:x1])
    ring = np.ones(b.shape, bool)
    ring[max(0, (y - y0) // 2):max(0, (y + ph - y0 + 1) // 2), max(0, (x - x0) // 2):max(0, (x + pw - x0 + 1) // 2)] = False
    t = max(8, int(max(pw, ph) * RING_TILE) // 2)  # the tile side in detail (half-res) px, on a grid anchored at the patch
    gx, gy = ((x - x0) // 2) % t, ((y - y0) // 2) % t
    tiles = [(slice(max(0, ty), ty + t), slice(max(0, tx), tx + t))
             for ty in range(gy - t, b.shape[0], t) for tx in range(gx - t, b.shape[1], t)]

    def ncc(u, v):
        u, v = u - u.mean(), v - v.mean()
        den = float(np.sqrt((u * u).sum() * (v * v).sum()))
        return float((u * v).sum() / den) if den > 0 else 0.0
    n_moved = n_held = n = 0
    for sy, sx in tiles:
        k = ring[sy, sx]
        if k.sum() < t * t // 2:
            continue
        bb, mm, hh = b[sy, sx][k], moved[sy, sx][k], held[sy, sx][k]
        if min(np.abs(bb).mean(), np.abs(mm).mean()) < TEX_MIN:
            continue
        cm, ch = ncc(bb, mm), ncc(bb, hh)
        n += 1
        n_moved += cm >= NCC_MIN and cm - ch >= RING_MARGIN
        n_held += ch >= NCC_MIN and ch - cm >= RING_MARGIN
    return (n_moved, n_held, n) if n else None


def fit(ms, w, h):
    """One zoom + shift through the patches' moves, least squares: d = (s - 1)(p - centre) + t. A zoom moves every
    patch away from its centre in proportion to the distance, so the patches' moves ARE the scale."""
    rows, rhs = [], []
    for m in ms:
        px, py = m['at'][0] - w / 2, m['at'][1] - h / 2
        rows += [[px, 1.0, 0.0], [py, 0.0, 1.0]]
        rhs += [m['dx'], m['dy']]
    a, v = np.array(rows), np.array(rhs)
    sol = np.linalg.lstsq(a, v, rcond=None)[0]
    return dict(scale=1.0 + float(sol[0]), tx=float(sol[1]), ty=float(sol[2]))


def miss(model, m, w, h):
    """How far one patch's move is from what the model predicts there (px)."""
    k = model['scale'] - 1.0
    return float(np.hypot(k * (m['at'][0] - w / 2) + model['tx'] - m['dx'], k * (m['at'][1] - h / 2) + model['ty'] - m['dy']))


def spread(ms, w, h):
    pts = [m['at'] for m in ms]
    return len(ms) >= 2 and max(float(np.hypot(p[0] - q[0], p[1] - q[1])) for p in pts for q in pts) >= SPREAD_FRAC * min(w, h)


def agreeing(movers, w, h):
    """The largest set of moved patches one move explains, each within AGREE_PX of it. Two patches must agree on a
    plain shift; a zoom (three parameters) is only claimed by three or more, because two patches always nearly fit
    one (on a real short a hand and an animating waveform, 5 px apart, did)."""
    best = []
    seeds = [(c, 2) for c in combinations(movers, 2)] + [(c, 3) for c in combinations(movers, 3)]
    for seed, need in seeds:
        inl = list(seed)
        for _ in range(2):  # fit the seed, then refit on everything it explains
            model = (fit(inl, w, h) if need == 3 else
                     dict(scale=1.0, tx=float(np.mean([m['dx'] for m in inl])), ty=float(np.mean([m['dy'] for m in inl]))))
            inl = [m for m in movers if miss(model, m, w, h) <= AGREE_PX]
            if len(inl) < need:
                break
        if len(inl) >= need and len(inl) > len(best) and spread(inl, w, h):
            best = inl
    return best


def check_cut(path, info, t_out, t_in, patches, max_px=4.0, max_scale=0.01, vouched=False):
    """One cut -> a result dict: verdict PASS / FAIL / UNMEASURED, the per-patch reads, the shift and the scale.

    A patch that HOLDS proves nothing on its own (a graphic spanning the cut holds too), so holds never outvote a
    move: two or more patches that moved together, one zoom + shift explaining them all, FAIL the cut however many
    patches held. A patch that moved alone is read on the ring of footage round it: most of the ring's tiles moved
    with it and none held FAILs the cut; RING_UNCLEAR or more moved and some held is UNMEASURED (an object bigger
    than the patch, or the framing through a gap in a graphic); fewer is local motion, named, not failed. Patches
    `vouched` for as bare background (--patch) FAIL on any one that moved. A cut with nothing holding and nothing
    agreeing is UNMEASURED."""
    w, h, fps = info['w'], info['h'], info['fps']
    k_out, k_in = int(round(t_out * fps)), int(round(t_in * fps))
    res = dict(t=t_in, frame=k_in, patches=[], verdict='UNMEASURED', why='', dx=None, dy=None, scale=None,
               decided=[], alone=[], unclear=[])
    before = read_frames(path, k_out - SIDE, min(SIDE, k_out), info)
    after = read_frames(path, k_in, SIDE, info)
    if not before or not after:
        res['why'] = 'no frame decoded on one side of the cut (at the very start or past the end of the export?)'
        return res
    ms = [measure(before, after, name, box) for name, box in patches]
    res['patches'] = ms
    kept = [m for m in ms if not m['why']]
    if not kept:
        stuck = [m for m in ms if m['why'].startswith('no match')]
        res['why'] = ('no patch matches itself across the cut: a different picture on each side (a layout change, '
                      'a punch-in, a full-screen graphic) or a jump wider than the patches reach' if stuck else
                      'no textured, still background patch to measure on')
        return res
    movers = [m for m in kept if np.hypot(m['dx'], m['dy']) > max_px]
    holders = [m for m in kept if m not in movers]
    moved = movers if vouched else agreeing(movers, w, h)
    unclear, by_ring = [], not vouched and not moved
    if by_ring:
        # a patch that moved alone is read on the footage round it: when most of the ring's tiles moved with it and
        # none held, the jump is the framing and the patches that held are under a graphic (B82 with one bare patch).
        # When several moved and some held, the edge between them is an object's (a shoulder, a scrolling panel) or a
        # graphic's round a gap the footage shows through, and the composite cannot say which: never a pass
        for m in movers:
            s = surround(before[-1], after[0], m)
            m['ring'] = s
            if s and s[0] >= 2 and 2 * s[0] > s[2] and not s[1]:
                moved.append(m)
            elif s and s[0] >= RING_UNCLEAR:
                unclear.append(m)
    decided = moved or holders
    res['decided'] = [m['name'] for m in decided]
    res['alone'] = [m['name'] for m in movers if m not in moved and m not in unclear]
    res['unclear'] = [m['name'] for m in unclear]
    res['dx'] = float(np.median([m['dx'] for m in decided])) if decided else None
    res['dy'] = float(np.median([m['dy'] for m in decided])) if decided else None
    res['scale'] = fit(decided, w, h)['scale'] if len(decided) >= 3 and spread(decided, w, h) else None
    if moved:
        worst = max(moved, key=lambda m: np.hypot(m['dx'], m['dy']))
        res['verdict'] = 'FAIL'
        n = len(moved)
        who = (f"{n} of the patches you picked {'moves' if n == 1 else 'move'}" if vouched else
               f"{n} patches move together" if not by_ring else
               f"{moved[0]['name']} moves and the footage round it moves with it (so the patches that held are under a graphic)"
               if n == 1 else
               f"{n} patches ({', '.join(m['name'] for m in moved)}) each move with the footage round them, not by one "
               f"shift (so the patches that held are under a graphic)")
        res['why'] = (f"{who} at the cut, up to {np.hypot(worst['dx'], worst['dy']):.1f} px ({worst['name']})"
                      + (f", scale {(res['scale'] - 1) * 100:+.2f}%" if res['scale'] else ''))
    elif res['scale'] is not None and abs(res['scale'] - 1) > max_scale:
        res['verdict'] = 'FAIL'
        res['why'] = f"the scale changes {(res['scale'] - 1) * 100:+.2f}% at the cut"
    elif unclear:
        res['why'] = '; '.join(
            f"{m['name']} moved {np.hypot(m['dx'], m['dy']):.1f} px and {m['ring'][0]} of {m['ring'][2]} tiles of the "
            f"footage round it moved with it, {m['ring'][1]} held" for m in unclear) + (
            ': an object bigger than the patch, or the framing seen through a gap in a graphic, and the export cannot '
            'say which. Look at the cut, or re-run with --patch on bare background away from it')
    elif holders:
        res['verdict'] = 'PASS'
    else:
        res['why'] = 'every patch that counts moved, and no two of them agree: no framing to read'
    return res


def parse_patch(s):
    try:
        x, y, w, h = (int(round(float(v))) for v in s.split(','))
    except ValueError:
        raise ValueError(f'--patch {s!r}: want x,y,w,h in export pixels')
    return x, y, w, h


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('export', help='the draft export (the whole sequence, or pass --offset)')
    ap.add_argument('--cuts', required=True, help='cuts.json, or cut times in seconds (comma- or space-separated)')
    ap.add_argument('--offset', type=float, default=0.0, help='the export\'s first frame on the cut clock (s)')
    ap.add_argument('--patch', action='extend', nargs='+', default=[], metavar='x,y,w,h',
                    help='background patches to measure on, in export pixels (default: a ring of 12 round the border)')
    ap.add_argument('--max-px', type=float, default=4.0)
    ap.add_argument('--max-scale', type=float, default=0.01)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)

    info = probe(a.export)
    if not info or not info['fps']:
        print(f'✗ cannot read a video stream and frame rate from {a.export}')
        return 2
    w, h = info['w'], info['h']
    try:
        cuts, source = load_cuts(a.cuts, a.offset)
        boxes = [parse_patch(s) for s in a.patch]
    except (ValueError, KeyError, TypeError) as e:  # a bad list, a bad box, or a JSON file that is not an EDL
        print(f'✗ {e}' if isinstance(e, ValueError) else f'✗ {a.cuts} is not an EDL (no segments with start/end)')
        return 2
    if a.patch:
        patches = []
        for i, (s, (x, y, pw, ph)) in enumerate(zip(a.patch, boxes), 1):
            if x < 0 or y < 0 or pw < 16 or ph < 16 or x + pw > w or y + ph > h:
                print(f'✗ --patch {s} does not fit a {w}x{h} frame (min 16x16)')
                return 2
            patches.append((f'patch{i}', (x, y, pw, ph)))
    else:
        patches = auto_patches(w, h)
    print(f'{a.export}: {w}x{h} at {info["fps"]:.3f} fps; {len(cuts)} cut(s) from {source}; '
          f'limits {a.max_px:g} px, {a.max_scale * 100:g}% scale')
    if not cuts:
        print('✗ no cuts to check')
        return 2
    counts = dict(PASS=0, FAIL=0, UNMEASURED=0)
    for i, (t_out, t_in, label) in enumerate(cuts, 1):
        if t_in <= 0 or (info['dur'] and t_in >= info['dur']):
            print(f'⚠ cut {i} at {t_in:.3f}s is outside the export (0 to {info["dur"]:.3f}s): skipped. Wrong --offset?')
            counts['UNMEASURED'] += 1
            continue
        try:
            r = check_cut(a.export, info, t_out, t_in, patches, a.max_px, a.max_scale, vouched=bool(a.patch))
        except RuntimeError as e:
            print(f'✗ {e}')
            return 2
        counts[r['verdict']] += 1
        glyph = dict(PASS='✓', FAIL='✗', UNMEASURED='⚠')[r['verdict']]
        head = f"{glyph} {r['verdict']:<10} cut {i:<3} {t_in:9.3f}s (frame {r['frame']})" + (f'  {label}' if label else '')
        if r['decided']:
            head += (f"  shift dx {r['dx']:+.1f} dy {r['dy']:+.1f} px  scale "
                     + (f"{r['scale']:.4f}" if r['scale'] is not None else 'n/a')
                     + '  on ' + ', '.join(r['decided']))
        print(head)
        if r['why']:
            print(f"    {r['why']}")
        if r['alone']:
            print(f"    moved alone, the footage round it held or could not be read, so read as local motion (the "
                  f"speaker, a prop): {', '.join(r['alone'])}. If one of those is bare background, the patches "
                  f"that held are under a graphic: look at them.")
        if a.quiet:
            continue
        for m in r['patches']:
            x, y, pw, ph = m['box']
            box = f'x{x} y{y} {pw}x{ph}'
            if m['why']:
                print(f"      · {m['name']:<13} {box:<22} not used: {m['why']}")
            else:
                print(f"      {'✗' if np.hypot(m['dx'], m['dy']) > a.max_px else '✓'} {m['name']:<13} {box:<22} "
                      f"dx {m['dx']:+7.2f} dy {m['dy']:+7.2f}  ncc {m['ncc']:.2f}  texture {m['tex']:.1f}  "
                      f"motion {m['motion']:.1f}"
                      + (f"  ring {m['ring'][0]} of {m['ring'][2]} tiles moved, {m['ring'][1]} held" if m.get('ring') else ''))
    print(f"{counts['PASS']} pass, {counts['FAIL']} fail, {counts['UNMEASURED']} unmeasured")
    return 1 if counts['FAIL'] else 2 if counts['UNMEASURED'] else 0


if __name__ == '__main__':
    sys.exit(main())
