#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""motion-blur-ab.py: proves HyperFrames' motion-blur component reaches the RENDER, by an A/B on the real renderer.

  uv run workflows/motion-blur-ab.py <hf-dir> <comp.html> [<comp.html> ...]   # e.g. .../hf-graphics/text-animation u04
  ... --fps 24000/1001        the render rate (default: the component's own "fps" mark, else 30000/1001)
  ... --hf 0.8.105            the hyperframes pin (default: the one the job's render.sh names, else 0.8.105), run under
                              the npm freeze that render.sh names beside it (HF_BEFORE; the new-job pin's own when it names none)
  ... --keep DIR              keep the on/off renders in DIR
  ... --keep DIR --reuse      score the renders already in DIR again, rendering only what is missing

WHY. The component blurred in a browser seek and rendered sharp: every copy froze the page's pre-ready
`visibility:hidden` when it snapshotted the element's style, frame 0 was never re-sampled after the fonts laid the page
out, and a block's rise-out was a transform the component never sees. 36 text animations shipped with neither the
component's blur nor THE SMEAR (2026-10-06), and a still compared by eye did not catch it. So the claim is measured.

HOW. Each comp renders twice with the job's pinned hyperframes: as written (ON) and with its hf-motion-blur.js script
tag removed (OFF, written beside it as a temporary <id>.mbab-off.html and deleted after). Then, frame by frame:
  WORDS (a text-animation comp, from build.py): every word's trajectory is read from the comp itself (data-t, the rise,
    the slam, the rise-out on the words, the block fade and hard kill) and sampled over the component's own shutter
    (720 deg, centred, 16 sub-intervals). A frame MOVES for a word when a sample leaves the frame's pose by more than
    the component's deadband (half a layout pixel, 0.001 of scale) while the word is visible. Each word is located in
    the OFF render's settled frame (its bright ink, line by line, left to right; the count must match the comp). PASS
    needs ON to differ from OFF inside that word's columns and line on EVERY moving frame, and every word to carry the
    mark. A frame on which nothing moves must not differ (the copies are hidden there). A rise-out's last frames, where
    the block's fade leaves under 20 % of the word, are judged neither way.
  TARGETS (a hand comp): every mark must parse as the component reads it (an attribute the browser parses differently,
    like g9's backslash-quoted marks, is refused by the component and listed here). Each marked element also renders
    ALONE (everything else hidden, no blur) with a probe that samples the element's OWN transform over the same
    shutter each frame and lights an 8x8 flag at the root's corner. A frame MOVES when the flag is lit and the element
    shows; PASS needs ON to differ from OFF inside the element's swept ink (its alone ink on that frame and the two
    beside it) on every moving frame. A container's move (a card's rise-out, a scene's float) carries the element
    without its own transform changing, and the component never sees an ancestor, so those frames are counted as
    carried, not failed. OFF also turns THE SMEAR off (HF.REG.smear.k = 0), so it is the render with no blur at all.
"Differ" is at least 16 pixels more than 2 levels apart: encoder noise is a pixel or two, a dark pill's smear 3-7 levels.
Exit 0 = proven, 1 = a moving frame rendered sharp (each one listed), 2 = could not measure.
"""
import argparse
import html as htmlmod
from html.parser import HTMLParser
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_TAG = re.compile(r'<script src="hf-motion-blur\.js"></script>')
SHUTTER = dict(angle=720.0, phase=-360.0, samples=16)
DEADBAND_PX, DEADBAND_LIN = 0.5, 0.001
HIT_PX = 16      # pixels more than 2 levels apart = the copies' ink (encoder noise: a pixel or two; a dark pill's smear: 3-7 levels)
EASES = {                                                      # GSAP's powerN is degree N+1 (power2 = cubic)
    "none": lambda p: p,
    "power2.in": lambda p: p ** 3,
    "power2.out": lambda p: 1 - (1 - p) ** 3,
    "power3.out": lambda p: 1 - (1 - p) ** 4,
}


def rate(text):
    num, _, den = str(text).partition("/")
    return float(num) / float(den or 1)


def num(src, name):
    m = re.search(r"\b" + name + r"\s*=\s*(null|-?[\d.]+)", src)
    if not m:
        raise SystemExit(f"cannot read {name} from the comp")
    return None if m.group(1) == "null" else float(m.group(1))


def strs(src, name):
    m = re.search(r"\b" + name + r'\s*=\s*"([^"]*)"', src)
    return m.group(1) if m else None


def parse_words(src):
    """The builder's own markup: lines of word spans, the timing constants of its script."""
    words = []
    for li, line in enumerate(re.findall(r'<div class="line l\d+">(.*?)</div>', src, re.S)):
        for m in re.finditer(r'<span class="([^"]*)" data-t="([\d.]+)" data-rise="(\d+)" data-w="([^"]*)"([^>]*)>', line):
            words.append(dict(line=li, cls=m.group(1), t0=float(m.group(2)), rise=float(m.group(3)),
                              text=htmlmod.unescape(m.group(4)), marked="data-hf-motion-blur" in m.group(5)))
    if not words:
        return None
    ease = re.search(r"\{y: 0, duration: RISE_DUR, ease: '([^']+)'\}", src)
    out_rise = re.search(r"tl\.to\(els, \{y: '-=([\d.]+)'", src)
    c = dict(DUR=num(src, "DUR"), RISE_DUR=num(src, "RISE_DUR"), F=num(src, "F"), OUT_T=num(src, "OUT_T"),
             OUT_DUR=num(src, "OUT_DUR"), ENTRANCE=strs(src, "ENTRANCE"), POP_FROM=num(src, "POP_FROM"),
             POP_OVER=num(src, "POP_OVER"), POP_F=num(src, "POP_F"), POP_EASE=strs(src, "POP_EASE"),
             RISE_EASE=ease.group(1) if ease else "power3.out", OUT_RISE=float(out_rise.group(1)) if out_rise else 0.0,
             block_exit=bool(re.search(r"tl\.to\('#block', \{opacity: 0, y:", src)))
    return words, c


def pose(w, c, t):
    """(y, scale) of the word's OWN transform at t, as the comp's timeline sets it; None when it is not visible."""
    F, y, s = c["F"], 0.0, 1.0
    if c["ENTRANCE"] == "punch":
        if t >= w["t0"] - 1e-9:
            s = c["POP_FROM"]
            if c["POP_OVER"] and c["POP_OVER"] > 0:
                p = min(1.0, max(0.0, (t - w["t0"]) / (c["POP_F"] * F)))
                s = c["POP_FROM"] + (c["POP_OVER"] - c["POP_FROM"]) * EASES[c["POP_EASE"]](p)
                if t >= w["t0"] + (c["POP_F"] + 1) * F - 1e-9:
                    s = 1.0
            elif c["POP_F"] > 0:
                p = min(1.0, max(0.0, (t - w["t0"]) / (c["POP_F"] * F)))
                s = c["POP_FROM"] + (1 - c["POP_FROM"]) * EASES[c["POP_EASE"]](p)
            elif t >= w["t0"] + F - 1e-9:
                s = 1.0
    elif c["ENTRANCE"] == "rise":
        p = min(1.0, max(0.0, (t - w["t0"]) / c["RISE_DUR"]))
        y = w["rise"] * (1 - EASES[c["RISE_EASE"]](p))
    if c["OUT_T"] is not None and c["OUT_RISE"]:
        q = min(1.0, max(0.0, (t - c["OUT_T"]) / c["OUT_DUR"]))
        y -= c["OUT_RISE"] * EASES["power2.in"](q)
    return y, s


def visible(w, c, t):
    """1 = the word shows: after its opacity cut, before the block's hard kill (only a rise-out has one; a phrase whose
    exit is the V1 cut runs to DUR). 0.5 = FAINT: the block's fade leaves under 20 % of it, and the copies fade with
    it, so their ink may or may not clear the noise; such a frame is judged neither way. 0 = not shown."""
    if t < w["t0"] - 1e-9:
        return 0
    if c["OUT_T"] is not None:
        if t >= c["DUR"] - c["F"] - 1e-9:
            return 0
        q = min(1.0, max(0.0, (t - c["OUT_T"]) / c["OUT_DUR"]))
        if 1 - EASES["power2.in"](q) < 0.2:
            return 0.5
    return 1


def moves(w, c, t, fps):
    """The component's own test: any shutter sample off the frame's pose by more than the deadband."""
    shut = SHUTTER["angle"] / 360 / fps
    start = t + SHUTTER["phase"] / 360 / fps
    y0, s0 = pose(w, c, t)
    for k in range(SHUTTER["samples"] + 1):
        tk = min(c["DUR"], max(0.0, start + k / SHUTTER["samples"] * shut))
        y, s = pose(w, c, tk)
        if abs(y - y0) > DEADBAND_PX or abs(s - s0) > DEADBAND_LIN:
            return True
    return False


PIN, PIN_BEFORE = "0.8.105", "2026-10-01T23:59:59Z"   # the new-job pin and its npm freeze (fullscreen-render.sh)


def render(hf_dir, comp, fps_text, pin, out, before=None):
    cmd = [shutil.which("npx") or "npx", f"hyperframes@{pin}", "render", ".", "-c", comp, "--fps", fps_text, "--quality", "standard",
           "--video-frame-format", "png", "--format", "mov", "--output", str(out)]
    env = {**os.environ, "npm_config_before": before} if before else None
    r = subprocess.run(cmd, cwd=hf_dir, capture_output=True, text=True, env=env)
    if r.returncode != 0 or not out.exists():
        sys.stderr.write(r.stdout[-2000:] + r.stderr[-2000:])
        raise SystemExit(f"render failed: {' '.join(cmd)}")


def frames(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    # the first row only: ffprobe 9 prints a timecoded file's video row twice (its tmcd stream group, then the stream)
    wh = next((l for l in out.splitlines() if l.strip()), "").strip().split(",")
    W, H = int(wh[0]), int(wh[1])
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), *passthrough(), "-f", "rawvideo", "-pix_fmt",
                          "rgba", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)   # a reader that stops early
    size = W * H * 4                                                                          # is a broken pipe, expected
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(H, W, 4)
    finally:
        p.stdout.close()
        p.kill()
        p.wait()


def runs(mask1d, merge):
    """[lo, hi) runs of True, gaps narrower than `merge` closed."""
    idx = np.flatnonzero(mask1d)
    if idx.size == 0:
        return []
    out, lo, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - prev > merge:
            out.append([lo, prev + 1])
            lo = i
        prev = i
    out.append([lo, prev + 1])
    return out


def bright(fr):
    """The glyphs' own ink, never the black glow behind them."""
    a = fr[..., 3].astype(np.float32) / 255
    return (a * fr[..., :3].max(axis=2)) > 128


def locate(off, settled_n, words, fps):
    """Each line's row band [y0, y1) from the settled OFF frame, and each word's columns [x0, x1) from the frame it
    appears on: the builder cuts every word in at its own data-t, so the COLUMNS of the line that hold ink on that
    frame and held none on the one before are that word (a word already rising only moves within its own columns; a
    gap in the ink cannot tell words apart, as an italic's side-bearing leaves a word gap narrower than a letter gap)."""
    nlines = 1 + max(w["line"] for w in words)
    first = {}
    for w in words:
        first.setdefault(int(math.ceil(w["t0"] * fps - 1e-6)), []).append(w)
    last = max(max(first), settled_n)
    shots = {}
    for n, fr in enumerate(frames(off)):
        if n in first or n + 1 in first or n == settled_n:          # each entrance and the frame before it
            shots[n] = bright(fr)
        if n >= last:
            break
    if settled_n not in shots:
        raise ValueError(f"the OFF render has no frame {settled_n}")
    ink = shots[settled_n]
    rows = runs(ink.any(axis=1), 2)
    while len(rows) > nlines:                                     # an i's dot, an accent: close the narrowest gaps
        i = min(range(len(rows) - 1), key=lambda k: rows[k + 1][0] - rows[k][1])
        rows[i:i + 2] = [[rows[i][0], rows[i + 1][1]]]
    if len(rows) != nlines:
        raise ValueError(f"found {len(rows)} lines of ink in the settled frame, the comp has {nlines}")
    cents = [(lo + hi) / 2 for lo, hi in rows]
    bands = [[0 if li == 0 else int((cents[li - 1] + cents[li]) / 2),
              ink.shape[0] if li == nlines - 1 else int((cents[li] + cents[li + 1]) / 2)] for li in range(nlines)]
    for n, ws in first.items():
        for li in sorted({w["line"] for w in ws}):
            y0, y1 = bands[li]
            mine = [w for w in ws if w["line"] == li]                 # document order = left to right
            now = shots[n][y0:y1].any(axis=0)
            before = shots[n - 1][y0:y1].any(axis=0) if n - 1 in shots else np.zeros_like(now)
            got = [r for r in runs(now & ~before, 2) if r[1] - r[0] >= 4]   # a word still rising flickers an edge column
            if len(got) < len(mine):
                raise ValueError(f"no new ink for {' '.join(w['text'] for w in mine)} on frame {n}")
            cut = sorted(sorted(range(len(got) - 1), key=lambda i: got[i + 1][0] - got[i][1])[len(got) - len(mine):])
            lo = 0                                                     # cut in on one frame: split at the widest gaps
            for w, i in zip(mine, cut + [len(got) - 1]):
                w["x0"], w["x1"] = int(got[lo][0]), int(got[i][1])
                lo = i + 1
    for li in range(nlines):
        mine = sorted((w for w in words if w["line"] == li), key=lambda w: w["x0"])
        for i, w in enumerate(mine):
            x0, x1 = w["x0"], w["x1"]
            pad = int(0.12 * (x1 - x0))                          # a slam's overshoot widens it
            left = mine[i - 1]["x1"] if i else 0
            right = mine[i + 1]["x0"] if i + 1 < len(mine) else ink.shape[1]
            w["x"] = [max(left + (x0 - left) // 2, x0 - pad), min(x1 + (right - x1) // 2, x1 + pad)]
            w["y"] = bands[li]


def prove_words(on, off, words, c, fps):
    n_frames = int(math.ceil(c["DUR"] * fps)) + 1                # every frame the render can hold
    for w in words:
        w["moving"] = [n for n in range(n_frames) if visible(w, c, n / fps) == 1 and moves(w, c, n / fps, fps)]
        w["faint"] = {n for n in range(n_frames) if visible(w, c, n / fps) == 0.5}
    settle = max(w["t0"] for w in words) + (c["RISE_DUR"] if c["ENTRANCE"] == "rise" else (c["POP_F"] + 2) * c["F"])
    settle_n = min(int(math.ceil(settle * fps)) + 1, n_frames - 3)
    if c["OUT_T"] is not None:
        settle_n = min(settle_n, int(c["OUT_T"] * fps) - 1)
    locate(off, settle_n, words, fps)
    for w in words:
        w["sharp"], w["blurred"], w["stray"] = [], 0, []
    for n, (fa, fb) in enumerate(zip(frames(on), frames(off))):
        d = np.abs(fa.astype(np.int16) - fb.astype(np.int16)).max(axis=2) > 2
        for w in words:
            (y0, y1), (x0, x1) = w["y"], w["x"]
            ink = int(d[y0:y1, x0:x1].sum())
            hit = ink >= HIT_PX
            if n in w["moving"]:
                w["weakest"] = min(w.get("weakest", 10 ** 9), ink)
            if n in w["moving"]:
                if hit:
                    w["blurred"] += 1
                else:
                    w["sharp"].append(n)
            elif hit and n not in w["faint"] and not any(n in o["moving"] for o in words if o is not w):
                # a neighbour's smear reaches across (a rise's trailing copies sit below it, over the next line): only
                # a difference while NOTHING else moves is the word's own ghost
                w["stray"].append(n)
    ok = True
    for w in words:
        mv = len(w["moving"])
        bad = [] if w["marked"] else ["NOT MARKED"]
        if w["sharp"]:
            bad.append(f"sharp on {len(w['sharp'])} moving frame(s): {w['sharp']}")
        if w["stray"]:
            bad.append(f"differs on {len(w['stray'])} frame(s) it does not move: {w['stray']}")
        ok &= not bad
        span = f"{w['moving'][0]}-{w['moving'][-1]}" if mv else "-"
        print(f"   {'PASS' if not bad else 'FAIL'}  {w['text']!r:<16} moves on {mv:3d} frame(s) ({span}), "
              f"blurred on {w['blurred']} (weakest {w.get('weakest', 0)} px)" + ("" if not bad else "  <- " + "; ".join(bad)))
    return ok


class Marks(HTMLParser):
    """Every data-hf-motion-blur value as a browser's tokenizer reads it, in document order."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.marks = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k == "data-hf-motion-blur":
                self.marks.append((tag, dict(attrs).get("id") or dict(attrs).get("class") or tag, v or ""))


def refused(value):
    """The component's own sweepOptions test: why it would skip this mark, or None."""
    v = value.strip()
    if v == "":
        return None
    try:
        p = json.loads(v)
    except ValueError:
        return f"is not JSON: {v!r}"
    if not isinstance(p, dict):
        return "is not a JSON object"
    for k, x in p.items():
        if k not in ("shutterAngle", "shutterPhase", "samplesPerFrame", "fps"):
            return f"names no such option: {k}"
        if not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x):
            return f"needs a number for {k}"
    return None


ALONE_CSS = ("<style>[data-composition-id] *{visibility:hidden !important;}[data-composition-id] [data-mbab-target],"
             "[data-composition-id] [data-mbab-target] *{visibility:visible !important;}</style>")
# The ground truth for "the element's OWN transform moves on this frame": the component's own test (any sample over a
# 720 deg centred shutter off the frame's pose by more than half a pixel or 0.001), run by independent code in the same
# renderer, painted as an 8x8 flag at the root's corner (white = moving). Re-run after the fonts settle: the renderer's
# frame-0 seek moves nothing, so no tween fires on it.
PROBE_JS = """<script>(function () {
  var el = document.querySelector('[data-mbab-target]'), root = document.querySelector('[data-composition-id]');
  var box = document.createElement('div'); box.setAttribute('data-mbab-target', '');
  box.style.cssText = 'position:absolute;left:0;top:0;width:8px;height:8px;background:#000;z-index:2147483647;';
  root.appendChild(box);
  function m(t) { var v = getComputedStyle(el).transform; if (!v || v === 'none') return [1, 0, 0, 1, 0, 0];
    return v.slice(v.indexOf('(') + 1, -1).split(',').map(parseFloat); }
  function off(a, b) { if (a.length !== b.length) return true; var n = a.length === 16 ? [12, 13, 14] : [4, 5];
    for (var i = 0; i < a.length; i++) { if (Math.abs(a[i] - b[i]) > (n.indexOf(i) >= 0 ? 0.5 : 0.001)) return true; }
    return false; }
  var tl = window.__timelines && window.__timelines.main, busy = false, FPS = %FPS%;
  if (!tl || !el) return;
  function pass() { busy = false; var t0 = tl.time(), d = tl.duration(), now = m(), moved = false;
    try { for (var k = 0; k <= 16; k++) { tl.time(Math.min(d, Math.max(0, t0 - 1 / FPS + k / 8 / FPS)), true);
      if (off(m(), now)) moved = true; } } finally { tl.time(t0, true); }
    box.style.background = moved ? '#fff' : '#000'; }
  function go() { if (busy) return; busy = true; Promise.resolve().then(pass); }
  tl.to({p: 0}, {p: 1, duration: Math.max(tl.duration(), 0.1), ease: 'none', onUpdate: go}, 0);
  if (document.fonts) document.fonts.ready.then(go);
  window.addEventListener('load', go);
})();</script>"""


def alone_variant(off_src, k, fps):
    """OFF with only the k-th marked element painted (its ancestors' transforms and opacity still apply), plus the
    own-motion probe."""
    spots = [m.start() for m in re.finditer(r"data-hf-motion-blur=", off_src)]
    i = spots[k]
    out = (off_src[:i] + "data-mbab-target " + off_src[i:]).replace("</head>", ALONE_CSS + "</head>", 1)
    j = out.rindex("</body>")
    return out[:j] + PROBE_JS.replace("%FPS%", repr(fps)) + out[j:]


def shape(fr):
    a = fr[..., 3]
    peak = int(a.max())
    return (a > peak // 2) if peak > 16 else None


def grow(mask, r):
    """mask dilated by r px (a square), no scipy."""
    out = mask.copy()
    for ax in (0, 1):
        acc = out.copy()
        for k in range(1, r + 1):
            acc |= np.roll(out, k, axis=ax) | np.roll(out, -k, axis=ax)
        out = acc
    return out


def displacement(a, b):
    """How far the ink moved between two shapes, in px: the area that changed over the length of the edge."""
    edge = a & ~(np.roll(a, 1, 0) & np.roll(a, -1, 0) & np.roll(a, 1, 1) & np.roll(a, -1, 1))
    return float((a ^ b).sum()) / max(1, int(edge.sum()))


def windowed(on, off, alone):
    """(n, ON, OFF, flag, alone n-1, alone n, alone n+1) in lockstep: the probe's flag read, its corner cleared."""
    def al_frames():
        for f in frames(alone):
            flag = int(f[2:6, 2:6, :3].mean()) > 127
            f = f.copy()
            f[:10, :10] = 0                                   # the probe's flag is not the element's ink
            yield flag, f
    prev = cur = None
    pending = []
    for n, (fa, fb, (flag, fal)) in enumerate(zip(frames(on), frames(off), al_frames())):
        pending.append((n, fa, fb, flag, fal))
        if len(pending) == 2:
            m, ma, mb, mflag, mal = pending.pop(0)
            yield m, ma, mb, mflag, prev, mal, pending[0][4]
            prev = mal
    for m, ma, mb, mflag, mal in pending:
        yield m, ma, mb, mflag, prev, mal, None


def prove_targets(on, off, alones, names):
    ok = True
    for name, alone in zip(names, alones):
        moving, sharp, blurred, carried = [], [], 0, 0
        for n, fon, foff, flag, p0, pn, p1 in windowed(on, off, alone):
            now = shape(pn)
            a0 = shape(p0) if p0 is not None else None
            a1 = shape(p1) if p1 is not None else None
            if now is None:
                continue                                      # not visible on this frame
            if not flag:
                if a0 is not None and a1 is not None and displacement(a0, a1) >= 1.5 * pn.shape[1] / 1920:
                    carried += 1                              # moved by a container, never by its own transform
                continue
            a0 = now if a0 is None else a0
            a1 = now if a1 is None else a1
            moving.append(n)
            ys, xs = np.nonzero(a0 | a1 | now)
            pad = 8
            y0, y1, x0, x1 = max(0, ys.min() - pad), ys.max() + pad + 1, max(0, xs.min() - pad), xs.max() + pad + 1
            region = grow((a0 | a1 | now)[y0:y1, x0:x1], pad // 2)
            d = np.abs(fon[y0:y1, x0:x1].astype(np.int16) - foff[y0:y1, x0:x1].astype(np.int16)).max(axis=2) > 2
            if int(d[region].sum()) >= HIT_PX:
                blurred += 1
            else:
                sharp.append(n)
        bad = bool(sharp) or not moving
        ok &= not bad
        span = f"{moving[0]}-{moving[-1]}" if moving else "-"
        why = (f"  <- sharp on {len(sharp)} moving frame(s): {sharp}" if sharp else
               "  <- never moves alone (mark the element that moves)" if not moving else "")
        print(f"   {'PASS' if not bad else 'FAIL'}  {name!r:<16} moves on {len(moving):3d} frame(s) ({span}), "
              f"blurred on {blurred}" + (f"; carried by a container on {carried} (sharp by design)" if carried else "")
              + why)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("hf_dir")
    ap.add_argument("comps", nargs="+")
    ap.add_argument("--fps")
    ap.add_argument("--hf")
    ap.add_argument("--keep")
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    hf_dir = Path(a.hf_dir).resolve()
    pin, before = a.hf, None
    if not pin and (hf_dir / "render.sh").exists():
        sh = (hf_dir / "render.sh").read_text(encoding="utf-8")
        m = re.search(r"hyperframes@([\d.]+)", sh)
        pin = m.group(1) if m else None
        m = re.search(r'^HF_BEFORE="([^"]+)"', sh, re.M)
        before = m.group(1) if m else None
    pin = pin or PIN
    before = before or (PIN_BEFORE if pin == PIN else None)   # an older pin's job renders as it always did
    work = Path(a.keep) if a.keep else Path(tempfile.mkdtemp(prefix="mbab-"))
    work.mkdir(parents=True, exist_ok=True)
    all_ok, unmeasured = True, False
    try:
        for comp in a.comps:
            path = Path(comp)
            if not path.suffix:
                path = Path("compositions") / f"{comp}.html"
            src_path = path if path.is_absolute() else hf_dir / path
            src = src_path.read_text(encoding="utf-8")
            if not SCRIPT_TAG.search(src):
                print(f"✗ {src_path.name}: does not load hf-motion-blur.js, nothing to prove")
                all_ok = False
                continue
            fps_text = a.fps
            if not fps_text:
                m = re.search(r'"fps":\s*([\d.]+)', src)
                f = float(m.group(1)) if m else 30000 / 1001
                fps_text = min(("24000/1001", "30000/1001", "60000/1001", "24", "25", "30", "50", "60"),
                               key=lambda r: abs(rate(r) - f))
            fps = rate(fps_text)
            stem = src_path.stem
            parsed = parse_words(src)
            off_src = SCRIPT_TAG.sub("", src)
            if not parsed and "HF.init(" in off_src:              # OFF has no blur at all: THE SMEAR off too
                off_src = re.sub(r"(<script>\s*)", r"\1HF.REG.smear.k = 0;\n", off_src, count=1)
            variants = {"off": off_src}
            names = []
            if not parsed:
                mp = Marks()
                mp.feed(src)
                names = [nm for _, nm, _ in mp.marks]
                bad = [(nm, refused(v)) for _, nm, v in mp.marks if refused(v)]
                print(f"{stem} (targets, {fps_text}, hyperframes@{pin}): {len(mp.marks)} mark(s)")
                for nm, why in bad:
                    print(f"   FAIL  {nm!r:<16} the component refuses it: the attribute {why}")
                all_ok &= not bad
                for k in range(len(names)):
                    variants[f"alone{k}"] = alone_variant(off_src, k, fps)
            temps = []
            try:
                for key, text in variants.items():
                    t = src_path.with_name(f"{stem}.mbab-{key}.html")
                    t.write_text(text, encoding="utf-8")
                    temps.append(t)
                rel = src_path.relative_to(hf_dir)
                movs = {"on": work / f"{stem}-on.mov"}
                if not (a.reuse and movs["on"].exists()):
                    render(hf_dir, str(rel), fps_text, pin, movs["on"], before)
                for t, key in zip(temps, variants):
                    movs[key] = work / f"{stem}-{key}.mov"
                    if not (a.reuse and movs[key].exists()):
                        render(hf_dir, str(t.relative_to(hf_dir)), fps_text, pin, movs[key], before)
            finally:
                for t in temps:
                    t.unlink(missing_ok=True)
            if parsed:
                print(f"{stem} (words, {fps_text}, hyperframes@{pin})")
                words, c = parsed
                if c["block_exit"]:
                    print("   ⚠ the rise-out moves #block: the component cannot see it (rebuild with the current build.py)")
                try:
                    ok = prove_words(movs["on"], movs["off"], words, c, fps)
                except ValueError as e:
                    print(f"   ? could not measure: {e}")
                    unmeasured = True
                    continue
            else:
                ok = prove_targets(movs["on"], movs["off"], [movs[f"alone{k}"] for k in range(len(names))], names)
            print(f"{'✓' if ok else '✗'} {stem}")
            all_ok &= ok
    finally:
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)
    sys.exit(1 if not all_ok else 2 if unmeasured else 0)


if __name__ == "__main__":
    main()
