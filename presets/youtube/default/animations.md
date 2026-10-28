# In / Out Animations — THE REGISTRY

🔒 **Every entrance and every exit in a youtube/default graphic is one of the presets below.
Never author a bespoke in/out (2026-08-31).** If a beat seems to want a move that isn't
here, that is a signal to add a preset deliberately — not to improvise one in a comp. Improvised
entrances are why the same job ended up with a stepped slide, a flicker, a rise and a punch all
meaning "this appeared."

This supersedes the old "overlay CARDS keep their own stepped one-in-one-out language" boundary:
**cards use the registry like everything else.**

The step-5c review checks conformance to this list (`edit-review` 1d) and `workflows/graphics-qa.py`
fails an inline copy whose numbers drift — change a preset here and update both with it.

## The presets

**Scale family** — the element does not travel.

| preset | what it is | numbers |
|---|---|---|
| **`pop`** | The default entrance **for a free-standing OBJECT** — a prop, an icon, a picture, the mascot, a flow node. Comes in under size, grows past, snaps back on one frame. Type, cards and panels RISE instead (below); **type NEVER pops** (§ TEXT NEVER POPS). | scale `0.90 → 1.10` over **3 frames** `power2.out`, then `1.00` on frame 4 (a one-frame linear settle, never a `set`: under MBLUR a set double-exposes the element) |
| **`slam`** | Heavier. Starts over size and settles. Use sparingly — it is a stamp. | scale `1.16 → 1.00` over **7 frames** `power2.out` |
| **`flash`** | The strobe. Three ghost pulses easing themselves in. **Timeline-rate comps only — never at 12 fps** (below). The text-animation builder's historical spec name for this preset is `flicker`; `flash` is accepted as an alias. | **7 frames**, opacity `[0.2, 0, 0.2, 0, 0.2, 1]` on frames 0,1,3,4,5,6 |

🔒 **The overshoot has to CLEAR the neighbours: an element is 10% bigger for three frames (16% on a
`slam`), so lay it out with that room around it and, when it collides, grow it AWAY from the
neighbour (`transform-origin` on the far edge) or shift or shrink the NEIGHBOUR, never the pop.**
`workflows/graphics-qa.py` asserts it from the comp's static CSS boxes (g16's payoff
node slid 17 px over the chip beside it for 4 frames and three review rounds missed it) and again
on the RENDERED INK of every overshoot frame, type and SVG-wrapped neighbours included (g9's
controller covered the "r" of a box-less "or" for two frames, 2026-09-28). A slammed
word beside another word is the common case: the stamp grows out of the line, not into its neighbour.

**The pop's beat is the SNAP BACK, not the growth.** Coming in under size is the wind-up; overshooting
past 1.0 and correcting on a single frame is the hit. The grow eases out rather than running linear, so it
leans into 1.10 and hangs there a beat before the correction, which makes the snap hit harder (tested both
ways, 2026-08-31). Starting big and settling down reads as a landing instead, heavier: that is the slam,
which is why both are kept.

### 🔒 No `flash` on a 12 fps graphic (2026-08-31)

**One 12 fps step is 83ms — 2.5 timeline frames — so any state change shorter than that is
dropped, and `flash` is built entirely out of single-frame gaps.** Measured on the g14 render:
the authored six states (`0.2 · 0 · 0.2 · 0 · 0.2 · 1`) came out as **two** — a dim hold at
luma 17.8 for seven frames, then full at 52.1. Both ghost gaps vanished and the three pulses
collapsed into one. What ships is a two-step fade-up, not a strobe. *"the flash animation
doesn't really even work with our 12 fps."*

So: bg-DARK full-screens render 12 fps style ([`creative-moves.md`](creative-moves.md) 4c) and
take **`pop`** or **`slam`** for the entrance that would otherwise flash. `flash` stays live on
overlays and bg-light full-screens, which run at the timeline rate.

The general form is worth carrying: **at 12 fps a move only gets `duration × 12` distinct
states.** Anything authored in single frames — a strobe, a 1-frame stamp, a 2-frame dim — has
to be re-expressed in whole 83ms steps or it will not survive the grid.

**A slide travels until the element's WHOLE SUBTREE clears the frame (2026-09-10).** `slideIn` / `slideOut` measure the slid element's descendants from their offsets and travel that far, never a bare frame width; an explicit `dist` still wins. The g16 filmstrip, 480 px wider than the frame, hung at the left edge for five frames on a 1920 px slide-out and was hidden with an opacity cut — a patch, not a fix; the registry now gets it right by construction.

**THE SMEAR (2026-09-10).** Every `slideIn` / `slideOut` carries a directional blur sized from its speed, every `pop` / `slam` a small isotropic one, both decaying with the move and both off on a 12 fps graphic. Numbers, the renderer's half and how it steps aside for HyperFrames' motion-blur component: [`creative-moves.md`](creative-moves.md) 4b.

**THE CAMERA (a full-screen's scene, you 2026-09-10).** `camera(sel, t0, t1, from, to)` moves the
SCENE wrapper of a punch-cut over its span — the push preset `1.00 → 1.05`, or a pan of 24 px —
`power1.inOut`, on top of THE FLOAT (its own wrapper inside the float wrapper: GSAP hands x/y to the
last tween added, so the two never share an element). Scenes inside a full-screen change hands with
the off-screen family below, and THE FLOW READS RIGHTWARD: the outgoing scene `slideOut('left')` as the
incoming `slideIn('right')`, elements inside a scene arriving left to right, or the scene racks out under type (creative-moves.md move 2 § THE RACK FOCUS).
The rule that demands them: [`creative-moves.md`](creative-moves.md) move 2 § A FULL-SCREEN IS A SCENE.

**Nudge family — THE RISE.** The element is already where it belongs and travels a few px into
place. This is the standard on text animations, cards and panels — the everyday in and out.

| preset | travel | duration | ease |
|---|---|---|---|
| **`riseIn`** | up 22px, ratio-scaled to type size (a 122px line rises 30px) | 0.55s | `power3.out` |
| **`riseOut`** | up 18px **+ fade** | 0.35s | `power2.in` |

**Slide family — OFF SCREEN.** The element travels across a frame edge: it starts (or ends)
outside the frame entirely. Four directions each — `bottom` · `top` · `left` · `right` — named
for where it comes FROM (in) or goes TO (out).

| preset | travel | duration | ease |
|---|---|---|---|
| **`slideIn(from)`** | from outside the frame edge (defaults to the full frame extent) | 0.75s | `power2.out` |
| **`slideOut(to)`** | out past the frame edge | 0.38s | `power3.inOut` |

> 🔒 **TEXT ANIMATIONS RISE (2026-08-31), AND TEXT NEVER POPS (2026-09-10).** The
> word-synced emphasis text in [`text-animation/`](text-animation/) enters on **`riseIn`** and exits
> on **`riseOut`** — that is `build.py`'s default (`entrance = spec.get("entrance", "rise")`),
> ratio-scaled to type size (22px at a 90px font) over 0.55s `power3.out`, and it carries the
> scissors. The one other entrance type may take is **`slam`** by name — the stamp, with the Impact —
> for the punchline that has to hit. **`pop` is not a text entrance, anywhere:** the pop and its Pop
> sound belong to visual elements (an icon, a picture, an actual item), never to words. you,
> 2026-09-10: *"we should never use pops for text animations … text is almost always going to be
> the scissor sound and normal rise in; only case otherwise is when we're doing the slam animation
> with the impact sound."* `build.py` refuses `entrance: pop`, `validate-plan.py` fails the cell,
> `graphics-qa.py` fails a hand comp that pops an element whose own text is words, and
> `sfx-plan.py` gives type in a hand comp the text sounds (rise → scissors, slam → Impact) from the
> markup alone. `flash` (the strobe, paired with the Neon Flicker) is untouched by this rule.

> 🔒 **A rise is NOT a slide (2026-08-31).** These were briefly ONE primitive with a
> distance argument and a `far` flag, so `slideIn('bottom')` at the default distance *was* the
> rise-in. That is a naming bug: it made "slide in from the bottom" describe a 22px nudge, when a
> slide means the thing comes in from off screen. Every shipped comp was calling the nudge under
> the slide name. **If the element never leaves the frame, it is a rise.**

- **Neither entrance fades in** — opacity CUTS to 1 on the first frame and the travel carries the
  entrance. A fade-in on top reads mushy.
- **`riseOut` fades while it travels**, because 18px alone would not read as leaving. `slideOut`
  does NOT fade — it exits the frame, which is departure enough.
- **The two eases differ because the distances do, and it is measured.** An element crossing a
  frame edge covers real distance, and `power3.out` dumps half of it into step one — at 12 fps
  that reads as a teleport followed by a crawl. So the slide takes `power2.out` over 0.75s, which
  spreads the travel evenly (measured on the g6 hero: 508 → 428 → 376 → 348 → 336 → 332 is a real
  deceleration, where power3.out gave 384 → 344 → 336 → 332). Over a 22px rise there is no such
  problem, so the rise keeps `power3.out` and its snappier 0.55s.

### 🔒 The default entrance and exit

**Out: `riseOut` — up 18px plus fade, over 0.35s `power2.in`.** That is the exit for everything,
unless a graphic has a specific reason to leave another way. It is already the lock in the
text-animation builder (`OUT_RISE = -18`, `OUT_DUR = 0.35`), so the rest of the vocabulary matches
what that builder always did.

🔒 **A SWAP IN THE SAME SLOT IS SEQUENCED: the out COMPLETES before the in starts (2026-09-04).**
When one element replaces another in the same place (a second line of type in the low band, a card
swapping its copy, a label changing), `riseOut(A, t)` then `riseIn(B, t + 0.35)` — the in begins the
frame the out finishes, never on the same time. g19 on your-job had both at `1.082` and shipped
"link in the description" fully on over a still-fading "go watch that video" for 11 frames; you caught
it, three review rounds did not (the overlap sat between the sampled evidence frames, and no rule named
it). If the in must land on a word, start the out 0.35s BEFORE that word instead of delaying the in.
Elements in DIFFERENT slots (a card leaving on the left while a chip pops on the right) may overlap.

**In, it depends what you are animating.** **Type, cards and panels RISE** (`riseIn`) — that is
the text-animation builder's default, and it is your shipped call on the editor graphic ("the
card should do our default rise in animation and then the claude mascot can do our default pop").
**Free-standing OBJECTS pop** — a prop, a chip, an icon, the mascot, a flow node. Two defaults
for two different things, not a contradiction: surfaces and words rise, objects snap; the
variation principle then decides contrast per graphic. **The slide family is the exception, not
the default** — reach
for it only when the element genuinely comes from or goes off screen (a scene change, a takeover
panel), never as a variation on the rise.

## The canonical block: it ships as CODE: `reference/hf-anim.js` (2026-09-02)

**Load it, never retype it.** Every hand OVERLAY comp starts from
[`reference/comp-scaffold.html`](reference/comp-scaffold.html), which loads
[`reference/hf-anim.js`](reference/hf-anim.js) (copied into the job's `hf-graphics/gfx/`) and calls
`HF.init({fps, dur[, stepFps: 12]})` for `pop` / `slam` / `flash` / `riseIn` / `riseOut` / `exit`
/ `slideIn` / `slideOut` / `float` / `arrow` / `drawOn` / `countUp` / `reveal`. A full-screen /
punch-cut starts from the preset's shipped reference instead (`reference/punch-cut-reference.html` or
`reference/punch-cut-text-light.html`): the scaffold is the OVERLAY shape and carries none of the
scene / `#racked` / `camera()` structure (graphics-build § Stage 3). On a 12 fps comp the
scale family re-expresses itself in 83 ms states and `flash` refuses. The "paste this block" rule
below produced eleven comps with eleven different subsets wrong; the block is kept here as the
SPEC the file implements, and `graphics-qa.py` fails any inline copy whose numbers drift.
`F` is one frame at the timeline rate (`1001/30000` at 29.97).

```js
// TWO families. rise* = a few px into place, the element never leaves the frame (the
// default). slide* = across a frame edge, the element starts or ends off screen.
const ANIM = {
  rise:  {in: {dist: 22, dur: 0.55, ease: 'power3.out'},
          out:{dist: 18, dur: 0.35, ease: 'power2.in'}},
  slide: {in: {dur: 0.75, ease: 'power2.out'},
          out:{dur: 0.38, ease: 'power3.inOut'}},
};
// one table serves both: slideIn('left') enters FROM the left, slideOut('left') exits TO it.
const AXIS = {bottom: ['y', 1], top: ['y', -1], left: ['x', -1], right: ['x', 1]};
// dist defaults to extent(el, side): how far the element's WHOLE SUBTREE must travel to clear
// that edge, measured from offsets (hf-anim.js extent()). Never a bare frame width — see § A slide travels.

const pop = (el, at, extra) => {                    // OBJECTS (type/cards/panels use riseIn)
  tl.set(el, Object.assign({opacity: 1, scale: 0.90}, extra || {}), at);
  tl.to(el, {scale: 1.10, duration: 3*F, ease: 'power2.out'}, at);
  tl.set(el, {scale: 1}, at + 4*F);
};
const slam = (el, at) => {                          // heavier, sparingly
  tl.set(el, {opacity: 1, scale: 1.16}, at);
  tl.to(el, {scale: 1, duration: 7*F, ease: 'power2.out'}, at);
};
const flash = (el, at) => {                         // the strobe variation entrance
  for (const [f, o] of [[0,0.2],[1,0],[3,0.2],[4,0],[5,0.2],[6,1]])
    tl.set(el, {opacity: o}, at + f*F);
};
const riseIn = (el, at, dist = ANIM.rise.in.dist) => {   // THE default for type/cards/panels
  const c = ANIM.rise.in;
  tl.set(el, {opacity: 1}, at);                     // opacity CUTS in, never fades
  tl.fromTo(el, {y: dist}, {y: 0, duration: c.dur, ease: c.ease}, at);
};
const riseOut = (el, at, dist = ANIM.rise.out.dist) => { // THE default exit
  const c = ANIM.rise.out;
  // RELATIVE, never absolute: an element resting at y:-22 (a bounce rest, a float leg)
  // would EXIT DOWNWARD to y:-18 (g18's arrow did, measured +3.17px). '-=' rises from wherever it is.
  tl.to(el, {y: '-=' + dist, opacity: 0, duration: c.dur, ease: c.ease}, at);
};
// OFF SCREEN only. Every slide carries THE SMEAR (hf-anim.js smear(); numbers: creative-moves.md 4b).
const slideIn = (el, at, from, dist) => {
  const [ax, sg] = AXIS[from], c = ANIM.slide.in, d = dist || extent(el, from);
  tl.set(el, {opacity: 1}, at);
  tl.fromTo(el, {[ax]: sg * d}, {[ax]: 0, duration: c.dur, ease: c.ease}, at);
  smear(el, at, ax, d, c.dur, 'in');
};
const slideOut = (el, at, to, dist) => {
  const [ax, sg] = AXIS[to], c = ANIM.slide.out, d = dist || extent(el, to);
  tl.to(el, {[ax]: sg * d, duration: c.dur, ease: c.ease}, at);
  smear(el, at, ax, d, c.dur, 'out');
};
```

**The block is the NUMBERS, not the whole file:** `extent`, `smear`, `camera`, the 12 fps re-expressions and `exit` live only in [`reference/hf-anim.js`](reference/hf-anim.js), which is the authority for their internals.

Elements start at CSS `opacity:0`; every preset above turns them on. Hard-kill anything that
must not linger (`tl.set(el, {opacity:0}, end)`) or it pops and lints red.

## 🔒 A full-screen graphic's entrance starts on FRAME 0 (2026-08-31)

**The cut IS the entrance.** A hard cut to a full-screen graphic is already a visual event; if
the content then animates in after a lead-in, the viewer gets TWO events — cut to an empty field,
then the content arrives. you on g19: *"we're already cutting to a full screen blank, and then
there's a giant terminal animating in so it's like two big cuts almost."*

So the first element of a full-screen graphic enters at `t = 0`, with no empty frames ahead of
it. Measured by heavy-downscale structural diff on the render (grain averaged away), g19 held
**2 blank frames** before the terminal appeared; it now starts on frame 0.

**It bites in proportion to how BIG the arriving element is** — calibrated against your own
calls on the same timeline, which look contradictory until you see that:

| graphic | blank lead | arriving element | verdict |
|---|---|---|---|
| g19-prompt | 2 frames | the terminal, 1400×600, near-full-frame | **wrong** — "two big cuts almost" |
| g14-flow | 14 frames | node 1 of 3, one card in a row | fine as is |
| g6-wall | 5 frames | the first of many wall cards | fine as is |

g19 had the *shortest* lead of the three and was the only one that read badly, because the thing
arriving was frame-scale: its arrival is itself a second frame-scale event. A small element
appearing after a beat is just a graphic starting. So the rule is sharpest for a
**near-full-frame** first element (the same threshold as the rise-not-pop rule below) and relaxes
as the element gets smaller — a short establishing beat before a card or a progressive build is
legitimate.

Two more caveats:

- **A word-synced entrance is a placement problem, not a timing one.** If the first element is
  anchored to a spoken word, do NOT drag it to `t = 0` and break the sync — trim the render's
  head and start the CLIP later instead, so the cut and the entrance coincide at the word. That
  changes a cut point on the timeline, so it is the creator's call.
- The rule is about the FIRST element. Later elements keep their own anchors.

Overlay cards are exempt — they animate over live footage, so there is no blank field and no
double event.

## 🔒 A near-full-frame element RISES, it does not pop (2026-08-31)

**`pop` scales 0.90 → 1.10 → 1.00. On a small chip that reads as a snap; on something the size
of the frame the whole picture lurches.** So an element large enough to dominate the frame — g19's
terminal is 1400×600, over 40% of a 1920×1080 frame — takes `riseIn` instead. This is a SIZE
rule layered on the type rule above: `pop` stays the default for free-standing OBJECTS at normal
scale (a prop, a chip, an icon, the mascot, a flow node), while type, cards and panels rise at
any size.

*"that is why the rise reads better there is because it's so big that the pop animation is
kinda a bit much."* Rough line: once an element passes about a third of the frame's area, reach
for the rise.

## 🔒 The arrow — `draw-on`

An arrow is a **path plus a computed head**. The stroke reveals with a
`stroke-dasharray`/`-dashoffset` tween and the head stamps on as the stroke arrives. **The head is
HIDDEN by `arrow()` itself and lands on the draw's last frame** (`drawOn`): a head that is merely
inside an opacity-0 group appears the moment the group turns on, before a pixel of line exists
(your-job, 2026-09-11, fixed in the registry). An arrow revealed by anything other than `drawOn`
must land its own head (`tl.set(sel + ' .head', {opacity: 1}, at)`), or it ships headless.

**The head is COMPUTED from the path's measured end tangent, sized off the path's stroke
width. Never hand-author `points` on an arrowhead (2026-08-31).** A `<polygon
points="…">` typed by eye is the defect — it is the path of least resistance inside an SVG,
which is exactly why it keeps happening. On a *straight* arrow eyeballing survives, so the bug
hides; on a **curve** it cannot, because a cubic's end tangent is `P3 − P2`, not the direction
the arrow looks like it is travelling. Measured on the shipped g14: one head pointed dead flat
(0.0°) while its shaft arrived at +21.4°, the other was 12.6° out, and both floated ~14px clear
of the end of their stroke.

The three constants are the shipped-and-approved arrow's own proportions, re-expressed as
multiples of stroke width so any arrow inherits the look: head **2.27×sw** long past the end,
**1.33×sw** half-width, base sunk **0.27×sw** back so the round cap buries inside it.

```js
const DRAW = 9;                                    // frames the stroke takes to arrive
const arrow = (sel) => {                           // call ONCE per comp, before the timeline
  for (const svg of document.querySelectorAll(sel)) {
    const p = svg.querySelector('path'), head = svg.querySelector('.head');
    const L = p.getTotalLength();
    const sw = parseFloat(getComputedStyle(p).strokeWidth) || 10;
    const p1 = p.getPointAtLength(L), p0 = p.getPointAtLength(Math.max(0, L - 8));
    let tx = p1.x - p0.x, ty = p1.y - p0.y;
    const n = Math.hypot(tx, ty) || 1; tx /= n; ty /= n;      // unit tangent
    const px = -ty, py = tx;                                  // unit normal
    const tip = {x: p1.x + tx * 2.27 * sw, y: p1.y + ty * 2.27 * sw};
    const b = {x: p1.x - tx * 0.27 * sw, y: p1.y - ty * 0.27 * sw};
    const h = 1.33 * sw;
    head.setAttribute('points', [[tip.x, tip.y],
      [b.x + px * h, b.y + py * h], [b.x - px * h, b.y - py * h]]
      .map(c => c[0].toFixed(1) + ',' + c[1].toFixed(1)).join(' '));
    p.style.strokeDasharray = L; p.style.strokeDashoffset = L;
  }
};
const drawOn = (sel, at) => {                      // the REVEAL: stroke arrives, head stamps
  tl.set(sel, {opacity: 1}, at);
  tl.to(sel + ' path', {strokeDashoffset: 0, duration: DRAW*F, ease: 'power2.out'}, at);
  tl.set(sel + ' .head', {opacity: 1}, at + (DRAW - 1)*F);
};
```

Markup: the head ships **empty** — `<polygon class="head"/>` — so a stale hand-typed value can
never survive. CSS gives `.head` `opacity:0` and the path its `stroke-width` /
`stroke-linecap:round`.

Four things to get right at authoring time:

- **Call `arrow()` for every arrow in one selector list** (`arrow('.a1, .a2')`) and call it
  **after** any glow/bloom clone is populated, so both layers get computed heads. A comp that
  clones `#content` into `#bloom` by `innerHTML` clones the *empty* polygon — if `arrow()` ran
  first, the clone ships headless.
- **Leave viewBox room past the path end.** The head extends `2.27×sw` beyond the last point,
  so a path ending at the edge puts the tip outside the box and SVG clips it silently. End the
  path about 3×sw short of the edge (g14's paths end at x150 in a 180-wide box: 6.6px of tip
  margin; one ending 15 units short on a 12-px stroke shipped a flat-clipped tip, 2026-09-13), and on
  a screen-rec scene let that tip land ON the window's edge.
- **The head's size comes from `stroke-width`, so the SVG must be 1:1** — `width`/`height`
  equal to the `viewBox` extent. A scaled viewBox makes `getComputedStyle` disagree with user
  units and the head comes out the wrong size.
- **A straight arrow drawn as ONE solid polygon** (no path, no separate head — g21's down
  arrow) is a different, legal thing: nothing to align, nothing to draw on. This rule governs
  the path+head form only.

Verify by measuring, never by looking: the head's axis (tip minus base-midpoint) must sit within
**1°** of the path's end tangent, and its base within **0.5×sw** of the path end.

⚠️ **`.head` is the arrowhead's class and nothing else's in a comp (2026-09-13).** A
label headline styled `.head` beside a curved arrow made `riseIn('.head', …)` match the polygon too, so
the head lit and rose before its stroke drew, on two screen-rec scenes, through two review rounds. Name
the headline `.hd`.

## 🔒 The variation principle — vary by ROLE, not by count (2026-08-31)

**Elements that do the SAME job in a graphic share ONE entrance. The element whose role is
different gets the different entrance.** That contrast is what carries meaning; a different move
on every element is variety that says nothing.

The rule this replaces was "elements in one graphic never share an entrance," and it produced
exactly the failure it was meant to prevent. g14 is three flow nodes — *raw footage → one prompt
→ finished video.* Two of them are inputs doing the same job; the third is the payoff, the one
that lights up and sparkles. The old rule forced three different entrances, so the graphic
announced a distinction between node 1 and node 2 that does not exist, and spent the contrast it
needed for node 3. *"having different animations for all three of them is kind of just
variety that doesn't really make any sense."*

So the shipped version is **`riseIn` on nodes 1 and 2, `pop` on node 3** — peers matched, payoff
singled out.

Read the graphic before picking: which elements are peers (list rows, steps in a flow, a pair
being compared, items in a set) and which one is the hero, the answer, the result, the odd one
out? Peers take one preset. The odd one takes another. **If everything in a graphic is a peer,
one entrance for all of them is correct** — a three-row list where all three rows stamp the same
way is right, not lazy. And a graphic with genuinely three distinct roles can legitimately use
three presets; the test is whether the difference in motion tracks a difference in meaning.

Exits do NOT vary at all: everything leaves the same way unless there is a reason.

## 🔒 State changes ANIMATE (2026-08-30)

**Any visible state change on screen rides a tween — never a single-frame switch.** A background
darkening, a blur arriving, a panel lighting up, a colour shifting: each one animates over the
window of the move that motivates it. you, on the first g6 dim: *"when you darken the
background, there's literally no animation. It just changes to dark in one frame, which is not
smooth."*

- Tie the state change to its motivating move's window (the g6 dim + defocus ride the hero's
  whole slide-in, not a frame of it).
- **At 12 fps, budget in 83ms steps:** a 4-frame tween is barely ONE stepped frame — author the
  change long enough to get several distinct states, or it is still a switch.
- The exceptions are things DEFINED as cuts: a hard punch-cut, and registry entrances whose
  opacity CUTS to 1 by design (the travel or scale carries those — authored, not a missing tween).

## Not entrances — the neighbours

- **`draw-on`** (arrows / annotation strokes) is a REVEAL, not a move — it has its own
  section and its own helper above: [§ The arrow — `draw-on`](#-the-arrow--draw-on).
  Never hand-author a head. Working comp:
  [`reference/punch-cut-reference.html`](reference/punch-cut-reference.html).
- **`scene-slide`** — the second beat inside a full-screen graphic — is just a paired slide, and
  it is the one place the slide family is genuinely right: the current content group
  `slideOut('left')` as the next `slideIn('right')`,
  over the STATIC background (the field never moves, only content). GSAP gotcha: `x` is
  ABSOLUTE — an off-screen panel at `translate3d(1920px)` tweens to `x: 0`, not `x: -1920`.
- **Hold life is THE FLOAT**, not an entrance — two presets, spanning the element's whole
  on-screen life, with these in/out moves composing on top. See
  [`creative-moves.md`](creative-moves.md) move 2.
- **Glow on images** follows [`creative-moves.md`](creative-moves.md) move 2's hero glow: where an
  image takes one, it is a blurred duplicate `<img>` behind the sharp one, never a drop-shadow
  filter, and the duplicate rides the wrapper so the glow follows every move.

## Retired

- **`scale-punch` (instant 1.45×, snapped to 1× next frame)** — replaced by `pop` / `slam`
  2026-08-31. you on the original: "meh." It survived in 7 places across 6 comps before the
  conformance sweep; if you find it in an old comp, it is a defect, not a variant.
- **`wiggle` (±2° rotation yoyo)** — replaced by THE FLOAT. **Zero ANIMATED rotation anywhere**
  now. A deliberate STATIC tilt is fine (a card's authored tilt, the text-animation builder's
  `tilt` knob) — it never moves.
