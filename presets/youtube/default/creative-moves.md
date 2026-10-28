# Creative Moves — the default editing vocabulary

**This is what "edit this video" produces, unprompted.** Locked 2026-08-29 off the
your-job intro — the creator dialed every move live, and the finished first clip IS the
quality bar (see the README's Definition of Done). These moves are the DEFAULT for
youtube/default: reach for them on your own; don't wait for instructions.

Read with [`animations.md`](animations.md) (entrance vocabulary),
[`text-animation/text-animation-style.md`](text-animation/text-animation-style.md) (type system + layout law),
[`backgrounds/README.md`](backgrounds/README.md) (the two locked fields).

## The moves

### 1. Text animation — the default sprinkle (use liberally)
Word-synced animated text on the A-roll for emphasized phrases or dead stretches.
**When nothing else is called for, a text animation is the move.** Built by
`text-animation/build.py` (copy the folder in, write text.json); the builder carries the whole
layout law. Emphasis font on 0-2 power words via `*asterisks*`. A text animation NEVER
bleeds across a V1 cut — trim the placed clip to the edit.

**It lives in THE LOW BAND like every other under-the-face overlay** —
the builder enforces it, so a two-line block comes out smaller and lower than a one-liner
by construction. Full spec + how to re-derive the band per shoot:
[`default-overlay-style.md`](default-overlay-style.md) § THE LOW BAND.

### 2. Cut-to-graphic — the punch cut (key claims)
On a power phrase, hard-cut the footage to a **full-screen graphic on a locked
background** — **bg-dark is the default field; bg-light is the accent, for the visual that
reads better on it (2026-09-10)** — and hard-cut back — no fades, ever.
**Pick the field; the locked render flags follow from it** —
[`backgrounds/README.md`](backgrounds/README.md) is the home for that pairing.
**A full-screen has no face to clear, so THE LOW BAND does not apply: it sits DEAD CENTRE,
a tad smaller (2026-09-10: a full-screen graphic is always centred unless there is a
specific reason otherwise).** One transform on the content layer does it —
`transform:scale(0.92); transform-origin:50% 50%` on `#content` —
with the content's own box centred in the 1080 frame first (equal top and bottom margins:
a 10 px bias in the box is a 9 px bias on screen). (The first lock's `translateY(40px)`, "a touch
low", was retired 2026-09-10.) Child GSAP transforms compose with it, so entrances and floats need no rework.
**CENTRED MEANS THE COMPOSED ROW, NEVER THE TYPE ALONE (2026-09-13).** A prop beside a
line is part of that line: the row (words + gap + prop) is what sits on the frame's centre line,
so the words themselves land off-centre by half the prop's footprint. Let the browser do it — the
prop is an `inline-block` INSIDE the centred `.line`, after (or before) its words, with its slot
reserved from frame 0 (`opacity:0` holds the box), so the row is centred as one unit and nothing
re-flows when the prop pops. Never `position:absolute; left:<n>px` a prop next to centred type. The same holds for the composed GROUP: everything on a
full-screen, measured as one box, sits on the frame's centre in both axes. `graphics-qa.py`'s
`centre` check measures both on the render's fullest frame: the whole box's horizontal centre and,
on a text punch-cut, every ink row FAIL past 40 px in the 1080 frame; a scene's rows (a window's
title bar, the chip row under one side of a diagram) and the vertical centre warn for a read. It
then holds every state the graphic SETTLES in after a camera or scale move (or a scene change) to
40 px on BOTH axes and inside the frame, FAIL: a late push that parked a panel off the top edge
passed on a pre-push fullest frame (2026-10-06). Its `margin` check fails full-screen copy that
holds still within 100 px of the top or bottom or 80 px of a side; a scene passing through the edge
is exempt. The
Stage-4 probe reads the same union rect before the render; a full-screen with a specific reason to
sit off-centre carries a `centre:row` / `centre:box` / `centre:settled` waiver with that reason, never a sentence.
**Two reference implementations ship in this preset.** Both ship on bg-LIGHT. The OBJECT one,
"edited by Claude"
([`reference/punch-cut-reference.html`](reference/punch-cut-reference.html), your-job),
is the model for an ARTIFACT or a process — hero, caption, draw-on arrow, scene-slide. No bg-dark
comp ships as a reference: build a dark full-screen from either file on the dark field and render
it with the dark-field flags ([`backgrounds/README.md`](backgrounds/README.md)); that file's baked
grain is a bg-light property and does not carry over. The light one, "one prompt / i didn't
touch it" ([`reference/punch-cut-text-light.html`](reference/punch-cut-text-light.html),
your-job, 2026-09-10), is **the bg-light TEXT punch-cut — emphasized text with light
visuals**: one centred line per spoken beat, each stamped on its word (surfaces rise, the
payoff line pops word by word), the emphasis word in Playfair italic at x-height parity in the red
accent with an underline drawn on under it, and the props kept light — a prompt chip with a
blinking caret, flat paper-cutout chips with a hard offset shadow (no glow on a light field). It is
the default full-screen for a payoff LINE. Anatomy of a full-screen (+ what bg-dark adds):

- **Background:** the locked field baked into the comp (gradient + vignette CSS),
  film grain added by the same ffmpeg post-pass as the background asset
  (`noise=c0s=7:c0f=t`, libx264 crf 14).
- **The glow pass a bg-dark full-screen carries is the RENDERER'S since 2026-10-06** (`GLOW_FULL`,
  a float bloom over the whole frame; level and flags: [`backgrounds/README.md`](backgrounds/README.md)). The comp
  carries no CSS `#bloom` clone: that retired recipe banded into rings and steps (*"three visible, different
  layers, from brighter to darker... why can't it just be a smooth gradient"*). bg-light gets NO glow (light bleeding
  needs a dark field to bleed into). Overlays get their light from THE PROP GLOW (`default-overlay-style.md`).
- **Hero visual front and center** — big (640px on the mascot), horizontally centered,
  face-height. The graphic's subject is THE thing; caption below it.
- **Hero glow** on a bg-dark full-screen = the renderer's glow pass alone (no duplicate at all since 2026-10-06). Elsewhere: ONE tight, weak blurred duplicate of the prop behind the sharp copy, in its own colour
  (never drop-shadow, never a disc): blur 14px @ 0.30 (2026-10-06: *"the glow is way too strong... perfectly
  glowing circles... needs to be more subtle"*, on g5's 46 px @ 0.55 + 16 px @ 0.50 over a radial halo disc). The old
  90 px @ 0.38 + 34 px @ 0.30 is retired.
- **Caption** under the hero: Helvetica Bold lowercase + Playfair Italic on the power
  word, x-height parity.
- **Annotation arrow** where it helps: tail starts AT the caption, draws up to the hero
  (draw-on spec in animations.md — tangent-computed head, never eyeballed).
- **Entrances follow the variation principle (vary by ROLE)** — here the hero, the arrow and
  the caption each do a different job, so each takes a different move: hero flicker-in, arrow
  draw-on, caption rise-in. Where a graphic has PEERS instead (steps in a flow, rows in a list),
  they share one entrance and only the odd element out contrasts. ⚠️ On a bg-DARK punch-cut the
  hero cannot flicker — that graphic renders 12 fps style, which drops the strobe (`pop` or
  `slam` instead; see 4c and [`animations.md`](animations.md) § No `flash` on a 12 fps graphic).
- 🔒 **Hold life = THE FLOAT — TWO presets, `subtle` and `medium` (2026-08-31;
  replaces the retired ±2° wiggle). ZERO rotation.** A slow x/y drift with x and y on
  DIFFERENT periods, so the path traces a shallow ellipse instead of a straight diagonal —
  that period mismatch is what reads as floating rather than sliding. The element **rests at
  its authored position and drifts out and back (0 → A → 0)**; it never straddles it.

  🔒 **The float spans the element's ENTIRE on-screen life — entrance and exit compose ON TOP
  of it (2026-08-31).** It does not wait for the entrance to finish and then begin:
  the mascot floats *through* its flicker-in, the g6 hero floats *while* it rises. A graphic
  that holds still and then starts moving reads as two separate animations bolted together.
  In practice: `float(target, 0, DUR, preset)` — the whole composition, every time. Drift
  while the element is still invisible costs nothing and means it is already alive the
  instant it appears.

  | Preset | Travel | Periods | Max step @29.97 | Use on |
  |---|---|---|---|---|
  | **`subtle`** | 6px x · 8px y | 1.25s · 0.95s | 0.25 · 0.44 px/f | a WHOLE graphic — a card, a chat thread, a panel and its furniture |
  | **`medium`** | 10px x · 16px y | 1.35s · 1.05s | 0.39 · 0.80 px/f | ONE big hero element — the mascot, a hero card, a single node |

  **Which one is decided by what is moving, not by how big the frame is.** A whole graphic
  drifting reads as the panel being alive; the same amount on a lone hero reads as dead.
  Medium is derived from the mascot in the `edited` punch-cut, the reference implementation
  shipped in this preset: [`reference/punch-cut-reference.html`](reference/punch-cut-reference.html).

  **Values are TRAVEL in px, and neither preset scales with element size.** Two presets with
  fixed numbers is the whole point — "scale amplitude with element size" is what let graphics
  drift off the standard one at a time.

  ```js
  const FLOAT = {subtle: [6, 8, 1.25, 0.95], medium: [10, 16, 1.35, 1.05]};
  const float = (target, t0, t1, preset) => {
    const [AX, AY, PX, PY] = FLOAT[preset];
    const leg = (prop, A, p) => {
      let cur = 0, out = true;
      for (let t = t0; t < t1 - 0.02; t += p) {
        const rem = Math.min(p, t1 - t);
        cur += ((out ? A : 0) - cur) * (rem / p);   // partial last leg, SAME speed
        tl.to(target, {[prop]: cur, duration: rem, ease: 'sine.inOut'}, t);
        out = !out;
      }
    };
    leg('x', AX, PX); leg('y', -AY, PY);   // y drifts UP first
  };
  float('#floatWrap', t0, t1, 'subtle');
  ```

  ⚠️ **Specify TRAVEL, never amplitude.** That ambiguity shipped one pass at double intensity:
  `±10` reads as "amplitude 10" but the element moves 20.

  ⚠️ **Never let the final leg be truncated.** Giving it a short duration but the full travel
  makes the graphic cover its whole excursion in a fraction of the time, so the float visibly
  ACCELERATES into the exit — measured 0.82 px/frame in the last 0.4s against 0.44 everywhere
  else, which reads as the graphic getting agitated right before it leaves. Scale the last
  leg's travel by the time remaining (above) so the speed stays flat.

  ⚠️ **Measure at the TIMELINE rate.** A 12 fps-style render steps 2.5× further per rendered
  frame by definition; probing at the animation rate will make you "correct" a float that is
  already right.

  **A hold shorter than one period gets a partial leg, and that is correct** — g6's hero and
  g14's node both hold ~0.92s, so on `medium` they trace ~14px of y instead of 16. If a
  graphic needs more life, give it a longer hold, never a hotter float.

  ⚠️ **Which is why the float ALWAYS goes on a WRAPPER — no exceptions.** Once it runs the
  whole composition it necessarily overlaps the entrance and the exit, so any x/y they touch
  would fight it (GSAP gives the property to whichever tween was added last, silently). The
  wrapper is `position:absolute; inset:0`, so the child's own `left`/`top` still resolve
  against the full frame once the transform makes the wrapper a containing block; the child
  keeps the entrance, the exit, opacity, className, everything. Where a layer is duplicated
  (the rack's clones), the wrapper goes in every copy; a clone built in JS from `innerHTML`
  carries it already.

  Author it as explicit alternating tweens — never `repeat: -1`, which makes the timeline
  duration infinite and breaks the paused-seek render.
- 🔒 **THE RACK FOCUS — a law, not an option (2026-09-10; first shipped on the g6 wall
  2026-08-31).** *"As soon as the text comes up, we need to rack the focus and darken the
  background so that we can clearly read the text."* Whenever TYPE lands over a scene — a wall,
  an artifact, a diagram, anything busier than the bare field — the scene racks OUT under it:
  blurred and darkened, everything including its own annotations, so the words alone are sharp.
  **THE RECIPE — A BLUR LADDER + A DIM, LEADING THE TYPE (2026-09-19).** The scene lives in
  `#scene` inside the scaled `#content`; `#racked` is a FRAME-level sibling holding **four
  full-frame opaque clones** of the same template — `.lvl` layers at `opacity: 0`, each one a
  `.bgcopy` of the field with a `.blurwrap` at blur **2.5 / 5 / 7.5 / 10 px** (`saturate(0.92)` and
  `saturate(0.85)` on the last two) around an `.inner{transform:scale(0.92)}` clone — plus ONE
  `#dim{inset:-60px;background:#05070d}` above them. Twelve frames BEFORE the type's entrance
  (`const RACK = <word> - 12 * F`) the four levels fade in over each other (8 frames each,
  staggered 4, `sine.inOut`), `#dim` ramps `0 → 0.72` over 20 frames `sine.inOut`, and the sharp
  `#content` is retired once the top level is opaque (`tl.set('#content', {opacity: 0}, RACK + 21 * F)`).
  Model: [`reference/punch-cut-text-light.html`](reference/punch-cut-text-light.html), the file every
  bg-light punch-cut starts from.

  Why it is built exactly that way — four ways it shipped wrong first:
  - **Never a `filter` tween** (the ban in `graphics-qa.py` stands; the g10 wall blinked to black on one).
  - **Never ONE dark clone faded over the bright scene:** every in-between frame is a 50/50 mix,
    which lifts to a flat gray before it darkens (measured on g5: contrast fell 62 → 18 while the
    mean held ~95 — *"it gets like gray first before it gets dark, it gets washed out"*). Opaque
    levels make each in-between frame a mix of two nearly identical images, so brightness and
    contrast fall together.
  - **Never a clone laid over a sharp scene left visible:** the sharp copy shows through beside its
    own blurred twin as a ghosted duplicate (g1 and g5, you 2026-09-18: *"they get duplicated, and
    it's weird"*). The opaque ladder covers it; the `tl.set('#content', {opacity: 0})` only retires it.
  - **Blur + darken and NOTHING ELSE:** every clone's `.inner` carries `#content`'s exact
    `scale(0.92)`. A clone left at 1.0 is 8.7 % bigger and the rack reads as a jump-zoom (g5, you
    2026-09-19: *"why are we doing the zoom?"*).
  - **The rack LEADS the type by 12 frames,** never starting on the type's own entrance, so the scene
    is already soft and dark when the words land (2026-09-19: *"why does the text come in
    before the focus rack?"*).

  Every level's `.inner` is animated by the same class selectors as `#scene`, so all four racked
  copies are frame-exact with the sharp one; the type sits in its own layer ABOVE `#racked`.
  **`#racked` lives at FRAME level — a sibling of the scaled `#content`, never inside it — and the
  dim bleeds past the frame at `inset:-60px`:** a racked layer inside the 0.92
  content box stops 4 % short of every edge and leaves a bright, sharp border around the darkened
  scene (g10 and g22 shipped that way for an hour, 2026-09-10: *"that shouldn't even have to hit
  the QA"*). `graphics-qa.py`'s `rack` check holds the frame edges to within 15 points of the centre's
  darkening, read on the dim's settled frame (how it measures: its own comments). On an already-dark
  field the rack is its blur ladder alone, which the gate cannot tell from a rack never wired, so it
  WARNS and names which field it measured; a wired blur-ladder rack on a dark field is answered with a
  `rack` waiver. Traps that stay: every `.lvl` is `position:absolute; inset:0` (a filter makes it
  a containing block), the dim's bleed past the frame is what keeps the blur from rimming it, and
  nothing BETWEEN `#racked` and `#root` carries `overflow:hidden` — that starves the overdraw and the
  frame edges never darken (`#root`'s own clip IS the frame and stays).
  The hero-entrance form (the hero **`slideIn('bottom')`** — off screen, so a SLIDE, 0.75s
  power2.out, ~0.45s before its word — while the scene racks over the same window) is one
  use of it; type over a scene is the other, and the mandatory one.

- 🔒 **A FULL-SCREEN IS A SCENE, NOT A CARD (2026-09-10).** *"We need more moving
  parts, more visuals, and more visually stimulating stuff … maybe we slide up to a scene, and
  then that scene slides completely out to the right, and something slides in from the left to a
  different scene. There's camera movement, there are different items and different pictures
  going in and out."* The bar every punch-cut clears, and the plan cell states each before a comp
  is built (`validate-plan.py` fails a punch-cut cell without them; `graphics-qa.py`'s `dynamics`
  check measures the render):
  ⚠️ **your examples are illustrations, never the spec (2026-09-10):** *"when I'm giving you
  editing advice, that's more of a 'for example' type thing … I took that so literally."* The
  slides, the camera, the scene changes below are WAYS a full-screen gets more going on; the
  brief is "more dynamic, more stuff happening," and the right way is whatever the beat calls
  for. Read every example he gives for the principle behind it, then design to the principle.
  1. **Phases — at least two.** Two visual beats that change what is on screen: a scene arriving
     and leaving, a rack focus, a reveal, a prop or picture coming in, a prop changing state. A
     single layout that only accretes elements is one phase. The cell lists them:
     `"phases": [{"at": 0, "what": "…"}, …]`.
  2. **Visuals — at least one that is not type.** A picture, an artifact, a prop, a diagram, a UI.
     Words on a field are a text animation, not a full-screen ("really just the text, kind of
     boring": g22 as first built). The cell lists them: `"visuals": ["…"]`.
  3. **The set is framed WHOLE (2026-09-19).** A wall, a grid or a row of items sits inside
     the frame with margin around it and gutters between the items. If the camera has to travel to
     show all of it, the set is too big for the frame: shrink the items, never pan across content
     that overflows.
  4. **Camera.** The scene wrapper moves over the span — the registry's `camera()` (a slow push
     1.00 → 1.05, or a pan) on top of THE FLOAT, so the composition is never a locked-off frame.
  5. **Transitions between phases** are one way to make a phase — a scene change from the
     registry's off-screen family, a rack focus handing the frame to the type, a prop changing
     state in place, a reveal — not a quota of slides. When scenes DO slide, **THE FLOW READS
     RIGHTWARD (2026-09-10):** the outgoing scene `slideOut('left')` as the incoming
     `slideIn('right')`, and the elements inside a scene arrive left to right — one direction the
     whole way. Never a scene that leaves right while the next scene's elements build left to
     right: *"← then → looks bad; it should look like → then →."*
  6. **Annotations are thesis statements, and they are DRAWN over the thing, never a chip on
     top of it.** A strike, a circle, an arrow over a scene draws at the START of its phase, as
     the point of showing the scene — never mid-graphic, where it reads as an accent to whatever
     word is being spoken. A word's accent belongs to the word (its slam, its underline, its
     colour). Crossing a prop out is a marker X drawn across it with the prop still visible; a
     red chip stamped over it hides the very thing being crossed out (g22's first build: *"it
     really gets covered by the X, the icon looks like nothing, random and ambiguous"*). One
     prop says one thing: "work" is a cog, "tune-ups" is a wrench — the literal, obvious icon,
     not a cluster.
  7. **Reuse keeps the field.** A scene brought back from an earlier full-screen (the thumbnail
     wall in g10 after g6) returns on the same background and at the same rate, then does
     something new to it (racks out under type, gets struck, slides away).
  Earned on your-job (2026-09-10): g10 (type over an un-racked wall, a strike timed to a
  word), g16 (three nodes on a field, "super bare-bones, plain Jane") and g22 (four lines of type, "no
  visual elements") were all rebuilt to this bar.
  **The one carve-out: an EVIDENCE scene (2026-09-14).** A full-screen whose job is to show a
  captured article, statement or essay passage he is quoting gets *"very basic cuts. We really just need
  to show the article, highlight the part that I'm talking about, and cite the source … the readable
  quote from the article, clear, front and center, and easily readable."* So: every page change and
  passage change inside the graphic is a hard cut; the cited passage is zoomed to fill the window
  (0.86 × the view width, capped 2.2× on a 2x capture) and centred; the marker highlight still sweeps
  the cited lines on their spoken anchors (that is the pointing); the citation block is there from
  frame 0; the dark field, drawn window and glow clone stay. No slide, rise, pan, camera push or float
  (the v1 build of those scenes had all five and he cut them). `graphics-qa.py` fails `source` and warns
  `dynamics` on such a scene: waive both in `qa-waivers.json` with this direction as the reason. Build
  one comp per scene, generated by a job-local script; see move 2's rules above.

**Timing craft:** cut TO the graphic a hair before the trigger word lands (~30ms early;
the word's own 80ms-led caption pops right after the cut). Cut BACK just before the next
spoken beat you want on camera. Trigger word "edited" at 2.067 → cut at 2.035; cut back
at 6.306 with "fully" at 6.436.

### 3. Scene slide — second beat inside a graphic
When the spoken content moves while the graphic holds, don't cut — **slide**: current
content group `slideOut('left')` as the next `slideIn('right')`, over the STATIC background
(the field never moves), on the registry's slide numbers, never bespoke ([`animations.md`](animations.md)
slide family; its `scene-slide` note carries the GSAP gotcha). Text on the incoming panel rides in
pre-set; later words appear word-synced after it lands.

### 4a. Vector props (self-made VFX)
Literal-word moments (shot/break/boom) get **self-generated vector art in the comp** —
NEVER YouTube green-screen pulls (2026-08-29 lock: stock quality is a lottery and
choosing clips is a human call; if real footage is truly needed, flag it for your
manual pass). The shipped bullet holes: irregular dark core polygon + thin radiating
crack triangles (solid fills — [`default-overlay-style.md`](default-overlay-style.md)
§ PROPS ARE SOLID FILL), three distinct shapes, varied
rotation/scale. **Entrance = the house pop (see below).** Stagger multiple hits a few frames apart
(4.85 / 5.03 / 5.16 against "shot" at 4.773). SFX sells these later at the SFX step.

### 4b. THE SCALE ENTRANCES + motion blur (2026-08-31)
**Free-standing OBJECTS scale in** — a prop, a chip, an icon, the mascot, a flow node — with `pop` (the default
object entrance) or `slam` (the occasional heavier stamp, for a punchline like the shipped "one shot." card);
**type, cards and panels RISE instead** (`riseIn`). Numbers: [`animations.md`](animations.md) § The presets.

🔒 **Motion blur is ON for slides and large movements (2026-09-10; reverses the
2026-08-31 "adds too much complexity" call: *"it really helps when we do the slides and large
movements"*).** Two halves, both needed, neither on a 12 fps graphic (4c stands — that look steps; the creator watched g16 with blur on the stepped frames on 2026-09-10 and undid it):
1. **THE SMEAR, in the registry.** Every `slideIn` / `slideOut` carries an SVG `feGaussianBlur`
   along its axis whose sigma follows the slide's velocity (`REG.smear.k` × the peak px per frame,
   capped at `REG.smear.max`: a frame-wide slide-in reads 34 px at its start and decays to 0 as it
   lands); every `pop` / `slam` carries a small isotropic one (`REG.smear.scale`, 6 px) that decays
   over the move. Tweened as an SVG attribute, never a CSS filter string; off under `stepFps`.
2. **The supersample, in the renderer:** `MBLUR=1 MBLUR_SS=8 MBLUR_SHUTTER=5 ./render.sh <id>` —
   8x is the ceiling (hyperframes refuses a frame rate over 240), a 225° shutter. On its own it
   leaves ghost copies 16 px apart at 4K on a frame-wide slide (measured on g22: 5x showed three
   copies, 8x five); with THE SMEAR under it the copies blend into a true smear.
   Use it on any timeline-rate comp that slides, moves its camera or pops something large; a
   comp of rises alone renders without it. Cost: 8x the frames (g22, 4.6 s at 4K: 48 s instead of 10).
3. **HyperFrames' motion-blur component, per element (2026-10-06, you asked for it):** the real shutter
   (N+1 additive copies along the element's sampled trajectory, a 720° shutter measured off After Effects), in
   the page instead of the renderer. Load `hf-motion-blur.js` after `hf-anim.js` (the snippet of hyperframes'
   registry `motion-blur` component, in `reference/`), mark the element that MOVES
   `data-hf-motion-blur='{"fps": 23.976023976}'`, init the registry with `HF.init({..., shutter: true})` (THE SMEAR
   steps aside: one blur, not two) and render WITHOUT `MBLUR` (no 8x supersample: the render costs the plain one).
   THE DEFAULT on every timeline-rate graphic that moves (2026-10-06: *"the new motion blur does work pretty
   smoothly... apply that to pretty much all of our graphics that would benefit from it"*): the text animations carry
   it from their builder, a hand comp marks its moving elements (pops, slams, slides, a spinner). Never under
   `STEP_FPS` (4c; re-confirmed 2026-10-07 on G5 with this component working at 12 fps: dark 12 fps scenes get no
   motion blur). A comp already rendered with
   `MBLUR=1` has true blur and keeps it. Mark the element that moves, a handful per comp: each costs N+1 copies.
   THE SMEAR steps aside only on an element the component blurs (marked, and the mark parses); every other mover in a
   `shutter: true` comp keeps it.
   **It is proven on the RENDER, never on a browser seek:** `uv run workflows/motion-blur-ab.py <hf-dir> <id>...`
   renders the comp with the component and without it on the job's pin and fails any frame where an element's own
   transform moves and the two are pixel-identical (exit 0 = proven). The first round (2026-10-06) shipped 36 text
   animations, g4, g9 and g17 with no blur at all while a browser seek and a still by eye both looked fine; the
   faults were fixed in `reference/hf-motion-blur.js`, whose comments carry them. Write the mark in
   plain single quotes: `data-hf-motion-blur=\'{...}\'` with a literal backslash is not JSON and the component
   refuses it (the A/B lists a refused mark by name).
   **The component sees only the element's OWN transform.** A container that moves (a card's rise-out, the float, a
   camera) carries its marked children sharp, by design, and the A/B reports those frames as carried. So a move that
   must blur goes on the marked element: the text builder puts the rise-out's travel on the words (the fade stays on
   the block). Every word is marked, the one moving on frame 0 included.
   **`compositions/hf-motion-blur.js` is a symlink to `../hf-motion-blur.js`, as `hf-anim.js` is** (`graphics-build`
   § the links): a real copy beside the comp loads ahead of the root's, so a fix to the root's never reaches the render.
   **Strip a dark shadow off the copies:** each copy carries the element's `::before` / `::after`, so a word's black
   legibility shadow, copied 17 times, summed into a pale haze round every rising word (you caught it on every text
   animation, 2026-10-06). The builder hides them inside the copy group:
   `[data-hf-motion-blur-group] .w::before, [data-hf-motion-blur-group] .w::after {content:none; display:none}`; the
   real word, painted on top, keeps its shadow. Compare a moving frame against the pre-blur render before shipping.

### 4c. 12 fps style — stepped animation (2026-08-31)
**THE DEFAULT for full-screen graphics on a DARK background, and only those**
(2026-08-31). The stepped motion reads as motion graphics against the navy
field. Everything else runs at the timeline rate: bg-LIGHT full-screens, overlay
cards, stat callouts, and text animations on the A-roll. The scope pairs with the glow —
a bg-dark full-screen gets 12 fps + glow; a bg-light one gets neither.
`STEP_FPS=12 ./render.sh <id>` animates at 12 fps and holds each frame, then expands
back to the timeline rate by duplication — the on-2s / stop-motion look.

🔒 **No `flash` on a 12 fps graphic (2026-08-31)** — use `pop` or `slam`; the measurement
and the general 83 ms-step form live in [`animations.md`](animations.md) § No `flash` on a 12 fps
graphic. The working renderer ships in this preset: [`reference/fullscreen-render.sh`](reference/fullscreen-render.sh)
(copy into the job's `hf-graphics/gfx/`; the text-animation `render.sh` carries the same
flags for alpha overlays). It is NEVER combined
with `MBLUR` (4b, and the measurement below).
Grain is applied AFTER the expansion at full rate: grain is a camera artifact, not
animation, and stepping it reads as a compression bug.

🔒 **A word-synced beat inside a 12 fps scene is a BIG change (2026-09-27).** A beat tweened over
8 timeline frames is three held steps of a third of the change each, and a small one (a label
brightening, a nudge in scale) moves the picture about 2 against a film-grain floor near 0.9, under
`change-events.py --sync`'s threshold, so its anchor cannot be checked; snapping it to one frame to
be seen breaks [State changes ANIMATE](animations.md#-state-changes-animate-2026-08-30). Give
each word-synced beat a large visible change over its tween, such as a wash of the zone's colour
across its region on its word: both rules pass (21 of 21 anchors, worst 0.096 s, on the Windows
long-form test job).

**Do NOT combine 12 fps style with MBLUR.** An instant appearance (`opacity 0 -> 1`)
landing inside a shutter makes that frame average empty-plus-present, and at 12 fps
that partial-opacity frame is HELD for ~3 timeline frames — so every element reads as
FADING IN. Measured on the g6 wall: a card went 7.8 -> 18.9 (held 3 frames) -> 83.4
with blur, versus a clean 7.8 -> 83.2 without. Fixing it means snapping every
appearance to the step grid minus half a shutter, which is more machinery than the
look is worth. Render 12 fps style unblurred; the stepping already reads as motion.

**At 12 fps the EASE is the smoothness** — prefer `power2.out` at ~0.75s for big travels, and when
a stepped move looks wrong measure the per-step positions off the render before touching anything
else (the per-step measurement is in [`animations.md`](animations.md), under the slide family).

Two other things to watch: word-synced events quantize to the 12 fps grid (up to
~83 ms of shift, so re-check anything that must land exactly on a word), and the
expansion makes the output a few frames long — harmless, placement pins the out point.

### 4-sync. EVERY GRAPHIC LANDS ON ITS WORD (2026-09-19)

Timing is read off the canonical transcript's word times, never the phrase's end. Each word of a
spoken-line text animation enters on its OWN spoken word; a graphic that answers a phrase (a rack,
a punch cut, a prop) starts on the first word of that phrase, so nothing reads as late. When another
graphic follows within about a second, the full-screen HOLDS up to that graphic's in-point and hard
cuts into it: never a fraction of a second of talking head between two graphics.

### 4d. READABLE graphics — the HOLD is the deliverable (2026-08-31)

**When a graphic exists so the viewer can READ something — a prompt, a command, a code block, a
config, a quote, a DM, a list of specifics — the complete content must sit still for 2-3
seconds.** People pause and screenshot this kind of graphic. If the reveal is still running when
the clip cuts, they never get a frame worth pausing on.

**A written artifact — a prompt, a command, a config, a quote — is shown COMPLETE and verbatim
from its written source, full-screen for as long as the line explains it, with the highlight
moving to the clause being spoken (2026-09-12).** A paraphrase, an ellipsis or a summary
label is not the artifact.

*"If we're showing a prompt, we should probably have the full prompt on screen longer so the
viewer has time to screenshot it or pause and look at it... the typing animation probably needs
to be a lot faster or it needs to come in earlier."*

**So budget the slot backwards from the hold, not forwards from the reveal.** The hold is the
point; the type-on, draw-on or stagger is garnish, and it gets whatever time is left:

```
reveal_end = clip_duration − HOLD        (HOLD = 2.5s for anything text-heavy)
```

g19 is the worked example. In a 4.50s slot it typed a 316-character prompt until 3.90 and held
the complete text for **0.60s** — unreadable, and unpausable in practice. Retimed to type
0.25 → 2.00, it now holds for **2.50s** in the identical slot: same graphic, same duration,
4× the readable time. Measured on the render by counting neutral-bright text pixels per frame
(exclude the accent cursor — its luma sits right at a naive threshold and the blink then makes
half the hold frames read as incomplete).

#### The reveal itself: BURSTS, never a linear wipe

**Revealing N characters every frame is a progress bar wearing a monospace font.** It has one
constant rate and no rhythm, and it reads as robotic however fast you run it. *"it just
looks a little stiff... split it up into chunks of words appearing at a time, that way it looks
more like mimicking real typing instead of just robotically revealing at a linear speed."*

Three things make it read as typing, and all three are cheap:

1. **Reveal by WORD BURST, not by character** — 2–6 words at a time.
2. **Hold each burst about a 12 fps beat** (~2 timeline frames at 29.97). The stepping is what
   kills the wipe feel; it does NOT require rendering the comp at 12 fps.
3. **Double the hold on a burst that ends in punctuation.** That hesitation is most of the
   realism — it is the only cue that says a mind is behind the keys.

**Everything must be DETERMINISTIC — never `Math.random`,** or the headless render seeks to
different text on every pass. And use a fixed irregular PATTERN rather than a modulo: `(i*5+2)%3`
looks varied and collapsed to 21 of 23 bursts being exactly 3 words, which is uniform in the one
dimension that matters. The pattern itself is a cycled list of burst sizes, and it ships as code —
`REG.burst` in [`reference/hf-anim.js`](reference/hf-anim.js), which `reveal()` reads: call the
helper rather than retyping an array, and change `REG.burst` if the cadence ever moves.

Measured on g19's render: **25 discrete steps held 1–4 frames each**, the 4s being the
punctuation pauses, against a new state every single frame before.

🔒 **PIN THE ZERO FRAME, or the reveal opens half-done.** A positioned `tl.set(el, {innerText})`
does not reliably revert when the renderer seeks back to the start — GSAP records whatever was
last applied as the "from" value — so g19 shipped a pass whose frame 0 already read
*"All right, go"*. `tl.set(el, {innerText: ''}, 0)` fixes it. This is the same law as every
element starting at CSS `opacity:0`: **never rely on the DOM's initial value surviving a seek,
state the zero frame explicitly.** It applies to any content-mutating reveal — text, counters,
list rows, a progress label.

Practical notes:

- **A faster type-on does not look wrong.** g19 already ran at ~89 chars/sec, far past human
  typing; at ~180 it reads as a fast paste or a stream, which is what an agent doing the typing
  should look like anyway.
- **Starting earlier is the cheaper lever.** The reveal can begin during the entrance — g19 starts
  typing at 0.25 while the terminal is still rising, and the two do not fight because the rise is
  nearly settled by then.
- **A blinking cursor keeps a static hold alive.** Solid while typing (a real terminal does not
  blink mid-keystroke), then a steady 0.30s blink through the hold.
- **If the content genuinely cannot be read in the slot, say so at plan time** — the fix is a
  longer clip or less text on screen, and both are the creator's call. Do not silently shrink the
  hold to fit the animation.

### 5. Emphasis push-in + text animation (A-roll emphasis)
When you vocally emphasize a phrase on camera, the footage pushes in on him. It is the
A-roll counterpart to move 1: **always paired with a text animation of the phrase**, so the
delivery, the picture and the type land on the same word. Reach for it wherever the read leans
on a phrase — it needs no instruction — and never as decoration on a flat line.

Numbers and the verify: [README § Emphasis push-in](README.md#emphasis-push-in--the-default-zoom-in-2026-08-31).

### 6. Opening zoom-out
Every video's first clip, numbers in [README § Opening zoom-out](README.md#opening-zoom-out--every-video-starts-with-it-2026-08-29-re-dialled-2026-09-10).
Don't ask, just bake it.

### 7. Real artifacts beat drawn ones (2026-08-30)
When the script points at something that **actually exists and is findable** — other
people's videos, a tweet, a repo, a product page, a comment — go get the real thing.
A drawn stand-in for a real artifact (a vector "video card" with a play triangle where
a thumbnail belongs, fake title bars, a made-up duration) reads as placeholder even
when it's well drawn. This is the counterpart to move 4a, not a contradiction: **invent
vector art for abstract/literal-word VFX, fetch the real asset for real things.**

- **YouTube thumbnails:** `yt-dlp "ytsearch12:<topic>" --skip-download --flat-playlist
  --print "%(id)s | %(view_count)s | %(channel)s | %(title)s"` to find them, then
  `https://i.ytimg.com/vi/<id>/maxresdefault.jpg` (fall back to `hqdefault.jpg`).
  Real durations via `yt-dlp --skip-download --print "%(duration_string)s"`. Store under
  the job's `assets/thumbs/<videoId>.jpg` and hardcode id + duration in the comp so the
  render stays deterministic.
- **Pick for VISUAL variety, not just relevance.** Any hot topic has thumbnail clone
  clusters (the your-job wall's first pass had three identical "CLAUDE + VIDEO"
  layouts and two identical "Claude Video Is Insane" layouts). Two near-identical
  thumbnails on one wall read as a rendering bug. Build a contact sheet, look at it,
  then swap duplicates for alternates. Spread light/dark/warm/cool and faces/non-faces.
- **Put one of your own in** when he's genuinely part of the set — a quiet easter egg,
  never the hero.
- **Layout note:** real thumbnails carry their own baked-in text, so don't add title
  lines under them — that's two layers of type fighting. A thin frame + the real
  duration chip is enough to read as "video". And when a card bleeds off the right
  frame edge, flip its chip to the card's left, or it renders visibly clipped.
- **CSS trap:** the thumbnail rule (`height:100%; object-fit:cover`) will also match
  any hero/mascot image sharing the class — an override must reset `height` AND
  `object-fit`, not just width, or the hero gets silently cover-cropped at the sides
  (this clipped the mascot's edge nubs once before it was caught).

### 8. Full-screen screen-recording b-roll — the page IS the frame (2026-09-18)

*"Sometimes we do full-screen B-roll where it's just the B-roll or screen recording that takes up the entire
screen … scan lines, glow, and a little bit of grain … 12 FPS … very subtle."* When a line hands the viewer
somewhere real (his community, a product page) and a framed card would shrink the page to a thumbnail, the
recording takes the WHOLE frame instead: a page recorded to fill 16:9 (`page-record.mjs --width 1280 --height 720
--scale 3` keeps a centred-column site from floating in white margins), a slow scroll inside the take, a camera
push 1.00 → 1.04, and the screen look in three quiet layers: a screen-blended blurred clone of the same video
(blur 14px, brightness 1.25, opacity 0.16), scan lines (a 1 px dark line every 3 px at 0.08), a soft edge
vignette; grain from `render.sh`'s post-pass; `STEP_FPS=12`. No window frame, no label, no entrance: a hard cut in
and out. It is the exception to § SCREEN-REC SCENES' window frame (`default-overlay-style.md`), not a
replacement for it: an app state or a click still gets the framed scene. Model: g39 on your-job.

## Rhythm — the retention law (2026-08-29)

### 🔒 THE DENSITY NUMBERS — measured off the shipped intro (2026-08-31)

The rhythm law gives a FLOOR ("something every ~10s") and the scope contract gives a card
CEILING, but nothing told you the actual cadence — so a conformant plan could ship at half the
reference density and still pass every rule. These are the shipped `your-job` intro's
real numbers. **Plan to them, per MINUTE of runtime** (the old "per section" scoping is
meaningless on a single continuous raw, which is one section by definition):

| per minute of finished runtime | target | shipped intro (121.0s, 25 graphics) |
|---|---|---|
| **graphic events, all kinds** | **11–13** | 25 events = **12.4/min** |
| of which **text animations** | 6–7 | 13 = 6.4/min |
| of which **full-screen graphics** | 2–3 | 5 = 2.5/min |
| of which **scenes** (the enacting kind) | ~1 | 2 = 1.0/min |
| of which **cards / stat callouts / annotations** | 2–3 | 5 = 2.5/min |
| **emphasis push-ins** (on V1) | **2–3**, spread | 4 = 2.0/min (2026-09-10: "a couple more … a little bit more camera movement, at points that need it, don't overdo it": your-job went from 3 to 6 over 2:16, none closer than 7 s, no 30 s stretch without one) |
| **longest bare stretch** | **≤ 6s** | 5.44s |
| **decorative full-screen share of runtime** | **≤ 25%** (required demonstrations tracked separately) | 21.4s = 17.7% |

Read that as a cadence, not a quota: the beats still decide WHICH graphic goes where, and a
stretch with nothing to show stays bare. But a plan landing at 5 events/minute is not "restrained",
it is under the reference look, and a plan at 20 is over it.

**THE GRAPHICS SCOPE — the numbers are measured over it, never over the runtime.** A stretch that
takes no graphics is not a density hole, and screen-recording FOOTAGE takes none by default (README
§ Screen-recording footage stays bare; a screen-recording GRAPHIC is a normal cell). When
part of a video is off-limits the plan carries `"graphics_scope": {"ranges": [[a, b], ...], "why":
"..."}` and `validate-plan.py` and `graphics-qa.py` hold the cadence to those ranges alone — measured
against the full runtime instead, a 12-minute walkthrough produced four permanent warns nobody could
satisfy and masked the real density hole inside the sections that do carry graphics.

**These are the long-form numbers.** A short-form plan is not held to them: each short-form preset
carries its own look, and the gates print the block for reference without warning on it.

**SPREAD, not just count (2026-09-10).** The full-screens are spaced across the whole
runtime: **never more than 40 s of runtime without one** (the first inside the first 40 s, the last
inside the last 40 s, no gap over 40 s between two). your-job shipped 3 full-screens in
its first 41 s and none in the remaining 95 s, passed every number above, and read front-loaded;
the fix was two more (a flow beat at 71 s, a text beat at 102 s) and this rule. A beat that carries
a payoff LINE gets the bg-light TEXT punch-cut (move 2, second reference); one that carries an
artifact or a process gets the dark one. `validate-plan.py` and `graphics-qa.py` warn on a gap over
40 s and on fewer than 2 full-screens per minute.

Apply this through the final kept sentence, including restored or added footage. Review dark
scene coverage across the opening, middle and closing beats; several light capture scenes or one
long prompt walkthrough do not replace the dark scene vocabulary elsewhere.

**The field (2026-09-10): bg-dark by default, bg-light as the accent.** *"I think the dark
background we should use as the default for most graphics. The light background should really
only be an accent one that we use if it calls for it."* Reach for the light field when the visual
reads better on it — dark ink and paper-cutout props, a real artifact shot on white, the thumbnail
wall; bright, glowy, UI-style art stays dark — not on a rotation (the 2026-08-31 strict alternation
is retired; two darks in a row are fine). The choice still drives locked render flags
([`backgrounds/README.md`](backgrounds/README.md)).

- **Something visual happens at least every ~10 seconds** — more when it flows. No stretch
  of nothing, ever; rhythm beats perfection.
- **A visual-content stretch gets continuous coverage**: when the script is describing
  something visual, graphics run for its WHOLE length — 30 seconds of visual storytelling
  means 30 straight seconds of visuals telling it.
- **The ladder:** beat clearly visual → a visual move (punch cut, chart, prop, card).
  Nothing obvious → a text animation. Never bare.

## Variety — the anti-stale law (2026-08-29)

Variety IS retention: new things keep happening, so it never feels flat.

- **Text animations are EXEMPT from this law** — they are the connective tissue that carries the
  density floor and legitimately run back to back (the shipped intro does). For the big moves:
  **never the same FULL-SCREEN treatment or card template twice in a row.** Rotate moves, rotate entrances (the
  variation principle), rotate looks.
- **Word-level treatments inside pops**, when the content calls for one: a **red
  highlight** sweeping a negation word ("that's *not* it" → `#ff4d5e` family); an
  **inline mini data-viz** behind a quantity word ("100% into discipline, 20% into
  structure" → a bar fills behind each word to its number); an underline; the emphasis
  font. When nothing calls for one, a plain pop is right — don't force it.
- **The field is NOT a variety axis** — `bg-dark` is the default, `bg-light` the accent; see
  § THE DENSITY NUMBERS, The field.

## Placement mechanics (how these reach the timeline)

**Universal:** graphics render as **mp4** (full-screen, grain baked) or **ProRes 4444
straight-alpha mov** (overlays), then land on the graphics track at the plan's times. Two rules
hold in every app:

- **Every full-screen graphic gets the film-grain pass** — `fullscreen-render.sh`'s `full` mode
  bakes it (`noise=c0s=7:c0f=t`, or `GRAIN_1080=5` on bg-dark). Alpha overlays ship clean.
- **Verify composites from the app's own program output**, never from the comp render — the
  composite over real footage is what the viewer sees.

- **A re-render is a NEW filename**, never an overwrite of a placed file: every editing app
  caches something about a placed path, and the failure is silent on all of them.
- **After any placement, read the track back** (start/end per clip) before trusting it.

**Which track, which command, and which alpha convention each app wants is the app skill's,
not this preset's: [`LANES.md`](../../../LANES.md) § step 5** points at the recipe per lane
(`premiere-pro`, `davinci-resolve`, `capcut`). On any app without one, drag the movs onto an
overlay track above the grade at the printed times; nothing above is required to get the look,
only to script it.
