#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""build.py — kinetic section-title cards (the youtube-default preset).
Inter, per-letter rise left to right on an exponential curve, stepped to
12 fps with real motion blur.

Promoted from the shipped job this preset was locked on
(the shipped implementation) 2026-08-27. Two changes from the original: titles
come from a titles.json next to this file instead of a hardcoded dict, and the
font + grid backdrop resolve themselves (font copied up from the repo's shared
assets/fonts; missing grid-bg.mp4 falls back to the solid navy field).

Usage: copy this whole folder into projects/<job>/hf-graphics/titles/, write
titles.json ({"t-setup": {"lines": ["the setup"], "dur": 3.0}, ...}), ./render.sh.

Emits two comps per title:
  compositions/<id>.html         opaque card, grid-bg.mp4 baked in behind the type
  compositions/<id>-alpha.html   type only, transparent (ProRes 4444 overlay)

The look — the four things that define it, each a knob at the top of this file —
is written up in titles-style.md beside this script.

renders/grid-bg.mp4 is a committed brand SOURCE asset with no generator: it is
exempt from the renders-are-regenerable-cache rule, and it does not ship to
clients (the card falls back to the solid navy field without it).
"""
import json
import shutil
import sys
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path

HERE = Path(__file__).parent
W, H = 1920, 1080
FPS = 30                      # the render fps: the TIMELINE's, set by render.sh (--fps, e.g. 30000/1001); each card
                              # lasts whole frames of it, so a 3.0 s card is 90 frames at 29.97 (3.003 s) and 72 at 23.976

# ── the four knobs ───────────────────────────────────────────────────────────
STEP_FPS = 12                 # motion quantized to this; render stays at FPS
# Exponential steepness. This is the single most sensitive number in the file:
# it decides how many 12 fps steps the letter is actually in motion for, and a
# letter that is not moving has nothing to blur. The textbook expo.out (10) puts
# 65% of the travel in the first step and lands inside two — the blur had almost
# no frames to live on. At 6 the curve spends ~5 steps decaying (43/24/14/8/5%),
# which is what makes it read as a smooth rise AND gives the smear somewhere to be.
EASE_POW = 6
# More samples than feels necessary, and only enough gaussian to hide the gaps
# between them. The gaussian is symmetric, so any sigma large enough to fuse a
# coarse sample set also bleeds the topmost ghost UP over the core — which stops
# reading as a trail and starts reading as a bloom around the letter.
GHOSTS = 16                   # motion-blur samples trailing the core
SHUTTER = 0.85                # how much of one step the ghosts span (0..1)
# False: letters rise free and fade in, nothing clips them (2026-07-31 —
# the masked version read as type sliding out of a cutoff line). True restores
# the baseline mask, in which case the fade is skipped: the mask does the hiding.
MASKED = False
# False: the letters rise in and HOLD at rest until the clip ends (2026-08-02 —
# he did not want them sliding back up and out before the cut). True restores the exit,
# which brings FALL_DUR / STAGGER_OUT / TAIL / FADE_OUT back into play.
EXIT = False

# ── type ─────────────────────────────────────────────────────────────────────
FONT = "Inter-Bold.otf"
FONT_SIZE = 168
TITLE_CASE = True             # "the setup" -> "The Setup". Not all-caps.
TRACKING = -3                 # px
LINE_H = round(FONT_SIZE * 1.16)
MAX_W = 1680                  # widest a line may draw; longer copy is scaled to fit
INK = "#eef4ff"               # cool-tinted white — never #fff
GHOST_ALPHA = 0.45
SMEAR_SIGMA = 4               # vertical gaussian fusing the ghost samples

# ── timing ───────────────────────────────────────────────────────────────────
IN_T = 0.10                   # first letter starts here
RISE_DUR = 0.62               # one letter's travel
STAGGER = 0.035               # per letter, left to right
LINE_DELAY = 0.16             # line 2 behind line 1
FALL_DUR = 0.50               # exit travel
STAGGER_OUT = 0.022
TAIL = 0.05                   # gap between the last exit and the clip end
# The fade runs on its own clock, faster than the travel. Tying opacity to
# POSITION instead would leave the letter nearly invisible through its first two
# steps, which are the fast, heavily-smeared ones — the fade would eat the blur.
FADE_IN = 0.30                # fraction of RISE_DUR to reach full opacity
FADE_OUT = 0.75               # fraction of FALL_DUR to fade back out

# ── the cards ────────────────────────────────────────────────────────────────
# Per-job copy lives in titles.json next to this file:
#   {"t-setup": {"lines": ["the setup"], "dur": 3.0}, ...}
# ids feed render.sh; 1 or 2 lines per card; dur 3.0 is the preset standard.
GRID_BG = HERE / "renders" / "grid-bg.mp4"


def load_titles():
    p = HERE / "titles.json"
    if not p.exists():
        sys.exit("no titles.json next to build.py — copy titles.json.example "
                 "and put this job's card ids + copy in it")
    return json.loads(p.read_text(encoding="utf-8"))


def ensure_font():
    """The comps and fit() both need the TTF at assets/fonts/ inside this folder.
    A job copy of the folder starts without it; pull it from the repo's shared
    assets/fonts (this folder always lives somewhere under the repo root)."""
    dst = HERE / "assets" / "fonts" / FONT
    if dst.exists():
        return
    for up in HERE.resolve().parents:
        src = up / "assets" / "fonts" / FONT
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print(f"copied {FONT} from {src}")
            return
    sys.exit(f"{FONT} not found in any parent assets/fonts/ — "
             f"copy it to {dst} by hand")


def titlecase(text):
    """First letter of each word up, everything else left exactly as typed.
    str.title() is not equivalent — it lowercases the rest of every word, so it
    mangles an apostrophe ("don't" -> "Don'T") and flattens deliberate casing."""
    return " ".join(w[:1].upper() + w[1:] for w in text.split(" "))


def fit(text):
    """Scale factor keeping this line inside MAX_W. Measured at BUILD time off the
    real TTF rather than in the browser: a runtime measure races the webfont load
    and would silently size against a fallback face on the frames captured first."""
    from PIL import ImageFont
    f = ImageFont.truetype(str(HERE / "assets" / "fonts" / FONT), FONT_SIZE)
    w = f.getlength(text) + max(0, len(text) - 1) * TRACKING
    return min(1.0, MAX_W / w) if w > 0 else 1.0


def letters(lines):
    """Flatten to [(line_index, char, stagger_slot)]. Spaces keep their slot so a
    word break reads as a beat of air instead of a jump cut between words."""
    out = []
    for li, text in enumerate(lines):
        for si, ch in enumerate(text):
            out.append((li, ch, si))
    return out


def exit_start(lines, dur):
    """Latest moment the exit can begin and still finish TAIL before the end. With
    EXIT off there is no exit at all, so park it past the clip end — the JS reads a
    single OUT_T and its exit branch simply never fires inside the card."""
    if not EXIT:
        return dur + 10.0
    last = max(LINE_DELAY * li + STAGGER_OUT * si for li, _, si in letters(lines))
    return dur - FALL_DUR - last - TAIL


def build(cid, lines, dur, alpha):
    ls = letters(lines)
    out_t = exit_start(lines, dur)
    settle = (IN_T + LINE_DELAY * (len(lines) - 1)
              + STAGGER * max(si for _, _, si in ls) + RISE_DUR)
    # with no exit the letters hold until the clip ends, so the clip end is the deadline
    hold = (out_t if EXIT else dur) - settle
    if hold < 0.15:
        print(f"  ! {cid}: only {hold:.2f}s of hold — raise dur or shorten the copy")

    rows = []
    for li, text in enumerate(lines):
        cells = []
        for si, ch in enumerate(text):
            glyph = "&nbsp;" if ch == " " else (
                ch.replace("&", "&amp;").replace("<", "&lt;"))
            gh = "".join(f'<span class="gh">{glyph}</span>' for _ in range(GHOSTS))
            cells.append(
                f'<span class="cell" data-l="{li}" data-s="{si}">'
                f'<span class="ghosts">{gh}</span>'
                f'<span class="core">{glyph}</span></span>')
        k = fit(text)
        style = "" if k >= 1 else f' style="transform:scale({k:.4f})"'
        rows.append(f'<div class="line"{style}>{"".join(cells)}</div>')

    # The backdrop is a real video element, so it sits DIRECTLY under #root and
    # carries its own data-start — a timed <video> nested inside a timed <section>
    # renders frozen (the 0.7.42 contract). The type block stays untimed and is
    # driven entirely by the JS timeline.
    # Asset paths are ROOT-relative, not relative to compositions/. Compositions are
    # served with the project root as their base URL; a "../" path happens to work
    # in a render (which rewrites it) and 404s everywhere else.
    # No grid-bg.mp4 on disk -> solid navy field (the body bg) instead of the video.
    backdrop = "" if (alpha or not GRID_BG.exists()) else (
        f'<video id="bg" src="renders/grid-bg.mp4" data-start="0" '
        f'data-duration="{dur:.4f}" muted></video>')
    body_bg = "transparent" if alpha else "#050f24"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width={W}, height={H}"/>
<title>{cid}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<style>
@font-face{{font-family:'Inter';src:url('assets/fonts/{FONT}') format('opentype');
  font-weight:700;font-style:normal;font-display:block;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:{body_bg};}}
#bg{{position:absolute;inset:0;width:{W}px;height:{H}px;object-fit:cover;}}

#type{{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;}}

/* MASKED: exactly one line-height tall, so a letter parked one line-height down
   is hidden behind the baseline. Unmasked, the box is the same size but nothing
   clips — the letters travel the same distance and fade instead. */
.line{{position:relative;height:{LINE_H}px;overflow:{'hidden' if MASKED else 'visible'};
  white-space:nowrap;transform-origin:50% 50%;}}

.cell{{position:relative;display:inline-block;
  font-family:'Inter';font-weight:700;font-size:{FONT_SIZE}px;
  line-height:{LINE_H}px;letter-spacing:{TRACKING}px;color:{INK};}}
.core{{position:relative;z-index:1;display:inline-block;will-change:transform;}}
/* ghosts sit behind the core and get the vertical-only smear */
.ghosts{{position:absolute;left:0;top:0;z-index:0;
  filter:url(#vsmear);pointer-events:none;}}
.gh{{position:absolute;left:0;top:0;display:inline-block;opacity:0;
  will-change:transform,opacity;}}
</style></head>
<body style="margin:0;background:{'transparent' if alpha else '#000'};">
<svg width="0" height="0" style="position:absolute">
  <filter id="vsmear" x="-30%" y="-80%" width="160%" height="260%"
          color-interpolation-filters="sRGB">
    <feGaussianBlur stdDeviation="0 {SMEAR_SIGMA}"/>
  </filter>
</svg>
<div id="root" data-composition-id="main" data-width="{W}" data-height="{H}"
     data-start="0" data-duration="{dur:.4f}">
{backdrop}
<div id="type">
{chr(10).join(rows)}
</div>
</div>
<script>
window.__timelines = window.__timelines || {{}};
const DUR={dur:.6f}, STEP={STEP_FPS}, K={GHOSTS}, SHUTTER={SHUTTER};
const RISE={LINE_H}, IN_T={IN_T}, RISE_DUR={RISE_DUR}, STAGGER={STAGGER},
      LINE_DELAY={LINE_DELAY}, OUT_T={out_t:.6f}, FALL_DUR={FALL_DUR},
      STAGGER_OUT={STAGGER_OUT}, GA={GHOST_ALPHA}, MASKED={str(MASKED).lower()},
      FADE_IN={FADE_IN}, FADE_OUT={FADE_OUT};

// exponential out — the whole feel of the piece lives in this line. Normalized
// by its own endpoint: at EASE_POW 6 the raw curve stops 1.6% short of 1, and
// on a full line-height of travel that is a ~3px snap on the landing frame.
const EN = 1 - Math.pow(2, -{EASE_POW});
const ease = p => p <= 0 ? 0 : p >= 1 ? 1 : (1 - Math.pow(2, -{EASE_POW} * p)) / EN;
const clamp01 = v => v < 0 ? 0 : v > 1 ? 1 : v;

// y in px, positive = below the rest position. Entrance and exit are the same
// direction of travel, so the letter never reverses.
function yAt(li, si, t){{
  const t0 = IN_T + LINE_DELAY * li + STAGGER * si;
  let y = (1 - ease(clamp01((t - t0) / RISE_DUR))) * RISE;
  const t1 = OUT_T + LINE_DELAY * li + STAGGER_OUT * si;
  if (t > t1) y -= ease(clamp01((t - t1) / FALL_DUR)) * RISE;
  return y;
}}

// opacity on its own clock — linear, and quicker than the travel, so the letter
// is solid while it is still moving fast enough to smear
function aAt(li, si, t){{
  if (MASKED) return 1;
  const t0 = IN_T + LINE_DELAY * li + STAGGER * si;
  let a = clamp01((t - t0) / (RISE_DUR * FADE_IN));
  const t1 = OUT_T + LINE_DELAY * li + STAGGER_OUT * si;
  if (t > t1) a = Math.min(a, 1 - clamp01((t - t1) / (FALL_DUR * FADE_OUT)));
  return a;
}}

const CELLS = [...document.querySelectorAll('.cell')].map(c => ({{
  li: +c.dataset.l, si: +c.dataset.s,
  core: c.querySelector('.core'),
  gh: [...c.querySelectorAll('.gh')],
}}));
const ghostY = new Float64Array(K);

function apply(t){{
  // quantize to STEP fps: the letters only ever occupy step positions, while the
  // file still renders every frame at {FPS}
  const ts = Math.floor(t * STEP + 1e-6) / STEP;
  const back = SHUTTER / STEP;
  for (const c of CELLS){{
    const y0 = yAt(c.li, c.si, ts);
    const a0 = aAt(c.li, c.si, ts);
    c.core.style.transform = 'translate3d(0,' + y0.toFixed(2) + 'px,0)';
    c.core.style.opacity = a0.toFixed(3);

    // sample backwards across the shutter — trailing smear, densest where the
    // curve is slowest
    let spread = 0;
    for (let j = 0; j < K; j++){{
      const yj = yAt(c.li, c.si, ts - back * (j + 1) / K);
      ghostY[j] = yj;
      const d = Math.abs(yj - y0);
      if (d > spread) spread = d;
    }}
    // fade the whole ghost stack out as the letter comes to rest, or a still
    // letter would carry a permanent halo
    // ...and carry the letter's own fade, or a barely-visible letter would drag
    // a full-strength trail behind it
    const live = Math.min(1, spread / 8) * a0;
    for (let j = 0; j < K; j++){{
      const g = c.gh[j];
      g.style.transform = 'translate3d(0,' + ghostY[j].toFixed(2) + 'px,0)';
      g.style.opacity = live === 0 ? '0'
        : (GA * Math.pow(1 - j / K, 1.3) * live).toFixed(3);
    }}
  }}
}}

const state = {{t: 0}};
const tl = gsap.timeline({{paused: true}});
tl.to(state, {{t: DUR, duration: DUR, ease: 'none', onUpdate: () => apply(state.t)}}, 0);
apply(0);
window.__timelines["main"] = tl;
</script></body></html>
"""


def frame_dur(dur, fps):
    """A card's length on the timeline's grid: the nearest whole frame count at `fps`, in seconds."""
    return round(dur * fps) / fps


def main():
    global FPS
    titles = load_titles()
    if "--ids" in sys.argv:
        print(" ".join(titles))
        return
    if "--fps" in sys.argv:
        v = sys.argv[sys.argv.index("--fps") + 1]
        n, _, d = v.partition("/")
        FPS = float(n) / float(d or 1)
        del sys.argv[sys.argv.index("--fps"):sys.argv.index("--fps") + 2]
    ensure_font()
    if not GRID_BG.exists():
        # GRID_BG is THIS copy's file (the job's titles folder); the preset's
        # renders/ only reaches the jobs copied after a loop lands there
        print(f"note: {GRID_BG.resolve()} missing — opaque cards get the solid "
              "navy field. Drop a backdrop loop there for this job (and at "
              "presets/youtube/default/titles/renders/grid-bg.mp4 for every "
              "job copied after)")
    want = [a for a in sys.argv[1:] if not a.startswith("-")] or list(titles)
    comps = HERE / "compositions"
    comps.mkdir(parents=True, exist_ok=True)
    for cid in want:
        if cid not in titles:
            sys.exit(f"unknown title {cid!r} — have: {' '.join(titles)}")
        spec = dict(titles[cid])
        spec["dur"] = frame_dur(float(spec["dur"]), FPS)
        lines = [titlecase(l) for l in spec["lines"]] if TITLE_CASE else spec["lines"]
        for suffix, alpha in ((".html", False), ("-alpha.html", True)):
            (comps / f"{cid}{suffix}").write_text(
                build(cid, lines, spec["dur"], alpha), encoding="utf-8")
        n = sum(len(l) for l in lines)
        scales = [fit(l) for l in lines]
        note = "" if min(scales) >= 1 else f"  fit {min(scales):.2f}x"
        ls = letters(lines)
        settle = (IN_T + LINE_DELAY * (len(lines) - 1)
                  + STAGGER * max(si for _, _, si in ls) + RISE_DUR)
        when = (f"exit @{exit_start(lines, spec['dur']):.2f}s" if EXIT
                else f"settled @{settle:.2f}s, holds {spec['dur'] - settle:.2f}s")
        print(f"wrote {cid}: {' / '.join(lines)!r}  {spec['dur']:.4f}s ({round(spec['dur'] * FPS)} frames at {FPS:.3f})  "
              f"{n} letters  {when}{note}")


if __name__ == "__main__":
    main()
