#!/usr/bin/env python3
"""Write a tracked RED BOX comp: a rounded rectangle that DRAWS ITSELF clockwise around a target on a recording, with a
subtle glow in its own red, locked to a registration track (workflows/track-region.py) through the recording's zooms.

  uv run presets/youtube/default/highlight/box.py <job-or-section dir> <id> <track.json> --from <render frame> --to <render frame>
      [--color #FF3B3B] [--draw 12]   the stroke colour, the frames the clockwise draw takes
      [--out <path>]

you, 2026-10-06, on the 47.3x outlier: "a line that animates around in a circle... in a clockwise motion... the square
line... a red, slight subtle glow line. And then we're gonna use the glow sound effect for that instead of the pencil."
The marker (bake.py) is for a phrase inside running text; the box is for a stat, a tile or a badge group that stands
on its own. The comp is <dir>/hf-graphics/gfx/compositions/<id>.html, comp time 0 = render frame --from; render it
`./render.sh <id> alpha` and lay it with a NORMAL blend over the recording (no "blend" on its plan cell).

The draw: one stroke from the top-left corner's end, clockwise round the box, `--draw` frames, power2.inOut, round caps;
it holds locked to the track and fades out over 6 frames that complete 2 frames before the end (graphics-qa's exit).
The glow is two blurred copies of the stroke (SVG feGaussianBlur, never a filter string tween): 5 px at 0.55 and 12 px
at 0.25, the same red.
"""
import argparse, json
from pathlib import Path

FPS = 24000 / 1001

TPL = r'''<!doctype html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=3840, height=2160"/>
<title>__ID__: tracked red box, drawn clockwise</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script src="hf-anim.js"></script>
<style>
/* __ID__ · written by presets/youtube/default/highlight/box.py from __TRACK__ (render frames __F0__-__F1__). A rounded red
   rectangle drawn clockwise round the tracked box over __DRAW__ frames, a subtle own-colour glow, held on the target, a
   6-frame fade out. Alpha overlay over the recording, NORMAL blend. */
*{margin:0;padding:0;box-sizing:border-box;}
#root{position:relative;width:3840px;height:2160px;overflow:hidden;background:transparent;}
#stage{position:absolute;left:0;top:0;width:1920px;height:1080px;transform:scale(2);transform-origin:0 0;}
svg.bx{position:absolute;left:0;top:0;width:1920px;height:1080px;overflow:visible;opacity:0;}
.bx path{fill:none;stroke:__COLOR__;stroke-linecap:round;stroke-linejoin:round;}
.bx .main{stroke-width:4;}
.bx .g1{stroke-width:6;opacity:0.55;filter:url(#gl1);}
.bx .g2{stroke-width:10;opacity:0.25;filter:url(#gl2);}
</style></head>
<body style="margin:0;background:transparent;">
<div id="root" data-composition-id="main" data-width="3840" data-height="2160" data-start="0" data-duration="__DUR__">
<div id="stage">
<svg class="bx" viewBox="0 0 1920 1080"><defs>
  <filter id="gl1" filterUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080"><feGaussianBlur stdDeviation="5"/></filter>
  <filter id="gl2" filterUnits="userSpaceOnUse" x="0" y="0" width="1920" height="1080"><feGaussianBlur stdDeviation="12"/></filter></defs>
  <path class="g2" pathLength="1"/><path class="g1" pathLength="1"/><path class="main" pathLength="1"/></svg>
</div></div>
<script>
const DUR = __DUR__, DRAWN = __DRAW__;
const TRACK = __FRAMES__;          // comp frame -> [x0, y0, x1, y1] in the 1920 frame
const H = HF.init({fps: 24000/1001, dur: DUR});
const {tl, F} = H;
const ease = x => x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;   // power2.inOut
// clockwise from the top-left corner's end: top edge, right, bottom, left, back round the top-left corner
const D = ([x0, y0, x1, y1]) => { const r = Math.min(14, 0.18 * (y1 - y0), 0.18 * (x1 - x0));
  return `M${x0 + r} ${y0}H${x1 - r}A${r} ${r} 0 0 1 ${x1} ${y0 + r}V${y1 - r}A${r} ${r} 0 0 1 ${x1 - r} ${y1}` +
         `H${x0 + r}A${r} ${r} 0 0 1 ${x0} ${y1 - r}V${y0 + r}A${r} ${r} 0 0 1 ${x0 + r} ${y0}`; };
tl.set('.bx path', {attr: {'stroke-dasharray': '1 1'}}, 0);
tl.set('.bx', {opacity: 1}, F);                                   // frame 0 is an empty stroke: nothing (no round-cap dot)
for (const [n, b] of TRACK) {
  const p = ease(Math.min(1, n / DRAWN));
  tl.set('.bx path', {attr: {d: D(b), 'stroke-dashoffset': 1 - p}}, n * F);
}
const OUT = DUR - 8 * F;
tl.to('.bx', {opacity: 0, duration: 6 * F, ease: 'power2.in'}, OUT);
H.finish();
</script></body></html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('id'); ap.add_argument('track')
    ap.add_argument('--from', dest='f0', type=int, required=True); ap.add_argument('--to', dest='f1', type=int, required=True)
    ap.add_argument('--color', default='#FF3B3B'); ap.add_argument('--draw', type=int, default=12)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    tr = {int(k): v for k, v in json.load(open(a.track, encoding='utf-8'))['frames'].items()}
    lo, hi = min(tr), max(tr)
    frames = [[n - a.f0, [round(v, 1) for v in (tr.get(n) or tr[lo if n < lo else hi])]] for n in range(a.f0, a.f1 + 1)]
    dur = round((a.f1 - a.f0 + 1) / FPS, 4)
    html = (TPL.replace('__ID__', a.id).replace('__TRACK__', Path(a.track).name).replace('__F0__', str(a.f0))
            .replace('__F1__', str(a.f1)).replace('__COLOR__', a.color).replace('__DRAW__', str(a.draw)).replace('__DUR__', str(dur))
            .replace('__FRAMES__', json.dumps(frames, separators=(',', ':'))))
    out = Path(a.out) if a.out else Path(a.dir) / f'hf-graphics/gfx/compositions/{a.id}.html'
    out.write_text(html, encoding='utf-8')
    print(f'{a.id}: {len(frames)} frames, draw {a.draw}, {dur} s -> {out}')


if __name__ == '__main__':
    main()
