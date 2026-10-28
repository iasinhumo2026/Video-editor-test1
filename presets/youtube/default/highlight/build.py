#!/usr/bin/env python3
"""Write a tracked HIGHLIGHTER overlay comp: a solid white band that wipes on left to right like a real highlighter stroke,
holds locked to the text it marks through the recording's zooms, and fades out, from a box track written by
workflows/track-text.py (2026-10-05: "an actual highlighter animation, as if we were to highlight it, but it's a
difference blend mode so that it kind of inverts the color, so it's easily readable").

  uv run presets/youtube/default/highlight/build.py <job-or-section dir> <id> <track.json> --from <render frame> --to <render frame>
      [--pad X,Y]         grow every box by X,Y px (1920 frame) each side: the track's own --pad already frames the
                          text, so only where the band must cover more (a whole pill whose text the track boxed)
      [--out <path>]      write the comp here instead (a proof, a scratch build)

The comp is <dir>/hf-graphics/gfx/compositions/<id>.html, comp time 0 = render frame --from (the cell starts there on
the timeline: its plan cell carries start = recording start + from/fps). Render it as an alpha overlay
(`./render.sh <id> alpha`); the placer lays it on V4 over the recording on V3 and sets the clip's blend to DIFFERENCE
(the plan cell's "blend": "difference"), which is what turns the white band into an inverted, readable stroke.

A track frame is one box [x0, y0, x1, y1] (track-text.py writes one, unioned), or a list of boxes, one per text LINE:
then each line is its own stroke, wiped in turn top to bottom.
"""
import argparse, json
from pathlib import Path

FPS = 24000 / 1001
WHITE = '#FFFFFF'

TPL = r'''<!doctype html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=3840, height=2160"/>
<title>__ID__: tracked highlighter (white band, Difference in the editor)</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script src="hf-anim.js"></script>
<style>
/* __ID__ · written by presets/youtube/default/highlight/build.py from __TRACK__ (render frames __F0__-__F1__). A solid white band
   on the tracked box: wipes on left to right over the registry's DRAW frames per line, holds on the text, fades out over
   6 frames. Alpha overlay over the recording, no background; the editor blends it DIFFERENCE (white page -> black,
   dark text -> light), so the band must stay pure white and fully opaque: no glow, no outline, no tint. */
*{margin:0;padding:0;box-sizing:border-box;}
#root{position:relative;width:3840px;height:2160px;overflow:hidden;background:transparent;}
#stage{position:absolute;left:0;top:0;width:1920px;height:1080px;transform:scale(2);transform-origin:0 0;}
svg.hl{position:absolute;left:0;top:0;width:1920px;height:1080px;overflow:visible;opacity:0;}
.hl rect{fill:__WHITE__;stroke:none;}
</style></head>
<body style="margin:0;background:transparent;">
<div id="root" data-composition-id="main" data-width="3840" data-height="2160" data-start="0" data-duration="__DUR__">
<div id="stage">
<svg class="hl" viewBox="0 0 1920 1080">__RECTS__</svg>
</div></div>
<script>
const DUR = __DUR__;
const TRACK = __FRAMES__;          // comp frame -> [[x0, y0, x1, y1], ...] one box per line, in the 1920 frame
const H = HF.init({fps: 24000/1001, dur: DUR});
const {tl, F, DRAW} = H;
const ease = x => 1 - (1 - x) * (1 - x);              // power2.out, the registry's stroke ease
const RX = h => Math.min(10, 0.15 * h);               // slightly rounded marker ends
// one discrete state per frame (a seek render sets each frame exactly): the box follows the track, and line k wipes
// left to right over DRAW frames starting at frame k * DRAW (one line = one stroke, in reading order). Frame 0 is
// width 0, so the stroke has no cap or sliver before it starts.
tl.set('.hl', {opacity: 1}, 0);
for (const [n, rows] of TRACK) rows.forEach((b, k) => {
  const w = b[2] - b[0], h = b[3] - b[1];
  const p = ease(Math.min(1, Math.max(0, (n - k * DRAW) / DRAW)));
  tl.set('.hl .r' + k, {attr: {x: b[0], y: b[1], width: Math.max(0, p * w), height: h, rx: RX(h), ry: RX(h)}}, n * F);
});
// out: a 6-frame fade that completes 2 frames before the end (graphics-qa exit)
const OUT = DUR - 8 * F;
tl.to('.hl', {opacity: 0, duration: 6 * F, ease: 'power2.in'}, OUT);
H.finish();
</script></body></html>
'''


def rows_of(v):
    """A track value as a list of line boxes: [x0, y0, x1, y1] is one line, [[...], [...]] is one per line."""
    return [v] if v and isinstance(v[0], (int, float)) else list(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir', help='the job folder, or a section sub-job (projects/<job>/sections/<s>)')
    ap.add_argument('id'); ap.add_argument('track')
    ap.add_argument('--from', dest='f0', type=int, required=True); ap.add_argument('--to', dest='f1', type=int, required=True)
    ap.add_argument('--pad', default='0,0', help='X,Y px (1920 frame) added to each side of every box')
    ap.add_argument('--out', default=None, help='write the comp here instead of <dir>/hf-graphics/gfx/compositions/<id>.html')
    a = ap.parse_args()
    px, py = (float(v) for v in a.pad.split(','))
    grow = lambda r: [r[0] - px, r[1] - py, r[2] + px, r[3] + py]
    tr = {int(k): [grow(r) for r in rows_of(v)] for k, v in json.load(open(a.track, encoding='utf-8'))['frames'].items()}
    lo, hi = min(tr), max(tr)
    frames = []
    for n in range(a.f0, a.f1 + 1):
        b = tr.get(n) or tr[lo if n < lo else hi]          # outside the read span: hold the nearest read box
        frames.append([n - a.f0, [[round(v, 1) for v in r] for r in b]])
    lines = max(len(b) for _, b in frames)
    for _, b in frames:                                     # a frame that read fewer lines holds the rest at width 0
        b += [[b[-1][0], b[-1][1], b[-1][0], b[-1][3]]] * (lines - len(b))
    dur = round((a.f1 - a.f0 + 1) / FPS, 4)
    rects = ''.join(f'<rect class="r{k}" width="0" height="0"/>' for k in range(lines))
    src = Path(a.track).name + (f', pad {a.pad}' if (px, py) != (0, 0) else '')
    html = (TPL.replace('__ID__', a.id).replace('__TRACK__', src).replace('__F0__', str(a.f0))
            .replace('__F1__', str(a.f1)).replace('__WHITE__', WHITE).replace('__DUR__', str(dur)).replace('__RECTS__', rects)
            .replace('__FRAMES__', json.dumps(frames, separators=(',', ':'))))
    out = Path(a.out) if a.out else Path(a.dir) / f'hf-graphics/gfx/compositions/{a.id}.html'
    if a.out: out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    print(f'{a.id}: {len(frames)} frames, {lines} line(s), {dur} s -> {out}')


if __name__ == '__main__':
    main()
