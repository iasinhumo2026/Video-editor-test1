<!-- ⚠️  BRAND VALUES BELOW ARE PLACEHOLDERS — replace with your own.
     Fill in brand-kit.md and tell Claude "apply my brand kit", or edit the values here directly. -->

# Default Overlay Style — THE default graphics pass

**This is the CARD language of the default graphics pass.** Modern, blue, clean UI cards that pop
up **over** the footage for informational beats — nothing bespoke, ~30 minutes for the card pass.
The default pass as a whole ALSO carries the creative-moves vocabulary (pops, punch cut-to-graphic
beats, push-ins — [`creative-moves.md`](creative-moves.md), 2026-08-29); this doc governs the cards.

Locked 2026-08-05 after a real job overran (1h40m of full-frame illustrated
collage scenes when the ask was "a couple of overlays, maybe some text").

- Build mechanics + render gotchas: the `graphics-build` skill.
- This doc is the **visual language + the scope contract**. The scope half is the important half.

---

## 🔒 SCOPE — the part that was missing

| | Default (this doc) | Only when you say so |
|---|---|---|
| **Coverage** | face-clear overlays, short full-screen scenes, and full-screen evidence/prompt demonstrations | decorative extended takeovers, background replacement |
| **Count** | **up to 4–7 cards** for an intro/section — a CEILING, not a quota: cards go only on beats with a showable the frame isn't already showing, so a tight intro may want fewer (the shipped your-job intro used 5 card-class graphics across 121s). On a single continuous raw (one section by definition) scope the ceiling to each intro/section-LENGTH stretch of roughly two minutes rather than to the whole runtime — past that the per-minute cadence in `creative-moves.md` § THE DENSITY NUMBERS governs, and it counts text animations, punch cuts and scenes separately. Those ride on top UNCOUNTED here, and the RHYTHM LAW (a visual event every ~10s) governs how many of those there are, so a dense section is not scope creep | 15+ |
| **Art** | the 6 card templates + the creative-moves vocabulary (heroes, vector props) | bespoke illustrated scenes, characters beyond the mascot |
| **Motion** | one in/out per card | per-graphic custom motion systems, tracked/baked paths |
| **Look** | this doc | the `vox-collage` or `liquid-glass` preset, named explicitly |
| **Budget** | **~30 min** for the CARD pass. The moves layer (text animations, punch cuts, push-ins) is separate and iterates to the Definition of Done — on a full-length video that is hours, not minutes, and that is expected | as long as it takes |

**Overlays never hide your face.** Cards live in a callout zone beside/below you — if an overlay would
cover your face, it's the wrong graphic. **AMENDED 2026-08-29 (baked off the your-job
intro): short PUNCH-CUT full-screen graphics are part of the default** ([`creative-moves.md`](creative-moves.md)
move 2). **The threshold for decorative punch-cuts is ~6s per graphic and ~25% of runtime in total. Required demonstrations are exempt from it** ([`creative-moves.md`](creative-moves.md) § 4d; `graphics-plan` § THE CAPTURE GATE): record their seconds separately in the plan, and do not shorten the evidence or replace it with a card to satisfy the decorative budget. What STAYS opt-in by name: decorative extended full-frame takeovers, bespoke
illustrated scenes, background replacement, and any non-default look — those still get a
plan-time yes with the second-count stated.

**Choose the default format that carries the beat:** a label gets a card, an action gets a scene,
and a real destination gets its actual capture (`graphics-plan` § THE CAPTURE GATE). These are
default editorial work, not a tier upgrade. A different look or bespoke illustration remains opt-in.

---

## 🔒 CONSTANTS

### Colors — DARK blue tech UI
Locked 2026-08-05 on your call ("modern tech UI look, dark blue palette, our dark blue grid
background"). This is the brand's signature grid **inverted to navy** — not the bright frosted
panels of the old short-form signature look (retired 2026-09-23).

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#010102` | the near-black field (full-frame comps only; the your-job field, `backgrounds/README.md`, 2026-10-06) |
| `--line` | `rgba(74,124,255,0.17)` | grid lines, 1 px, 90 px cells, under the lift (`backgrounds/README.md`) |
| `--royal` | `#1e48ff` | hero accent, meter fills |
| `--sky` | `#57c9f0` | secondary accent, status furniture |
| `--txt` | `#e8f0ff` | primary text — **off-white, never pure `#fff`** |
| `--muted` | `#8fa6d4` | eyebrows, labels, subs |
| `--green` | `#2ff58a` | **reserved** — a genuine "free"/unlocked payoff, nothing else |
| `--red` | `#ff4d5e` | the strike-through / negation accent |

One accent per card. Green is not decoration: it marks the single beat where something is free or
unlocked, the same way yellow is rationed in the collage preset.

#### 🔒 BORROWED PALETTES — depict the thing in ITS colours (2026-08-31)

**The token table above is the default, not a cage. When a graphic depicts a real, recognisable
thing, dress it in that thing's own colours.** A terminal gets terminal chrome — neutral
near-black, not the navy panel — and a Claude session gets Claude's orange on the prompt
furniture. *"we don't have to be so strictly locked into our brand colors for graphics. in
fact throwing in other colors where applicable or appropriate actually helps to add some variety
so that everything isn't so basic."*

This is the same instinct as CARDS NAME, SCENES ENACT one level down: a scene that depicts a
product but paints it in house blue is still narrating instead of showing. The macOS traffic
lights were always `#ff5f57 / #febc2e / #28c840` for exactly this reason — nobody would have
accepted three royal dots.

Three rules keep it from becoming a free-for-all:

1. **The colour must be SAMPLED, never guessed.** Pull the hex off the real asset or a real
   screenshot — `#d97757` for Claude came out of the real logo file (159,770 px
   of it), not from memory. A guessed brand colour is wrong in a way viewers notice.
2. **Borrow only where the thing is depicted.** The terminal window is neutral-and-orange; the
   card sitting next to it stays on the tokens. One graphic can hold both — what it must not do
   is drift house furniture toward a borrowed hue.
3. **All the other locks still apply.** THE PROP GLOW glows the borrowed colour (the cursor block
   takes its own orange), type still defaults to no glow on the basic text animations, glow is still never
   `text-shadow`, and `--green` stays reserved for the free/unlocked beat.

Cases this covers: a terminal or code editor, another product's UI, a platform's brand (YouTube
red, a chat app's bubbles), a real screenshot's own palette. Cases it does not: "this card would
look nicer in purple."

**Sampled references (2026-10-06), so nobody re-guesses them:**
- **A Claude chat** (2026-10-06: *"it should look like an actual Claude code chat... the same colors, the same
  fonts... instead of using our white liquid glass thing"*): the Claude desktop app's Code tab, dark mode, off a window
  grab: window `#151515`, sidebar `#111111`, user bubble `#212121` (radius 14), composer `#20201f` with a 1 px white-10 %
  ring, text `#f0efec`, muted `#898782`, hairlines white 6-10 %, the spark `#d97757`; the typeface is **Anthropic Sans**,
  the variable font inside Claude.app (`/Applications/Claude.app/Contents/Resources/fonts/AnthropicSans-Romans-Variable-25x258.ttf`,
  wght 300-800): copy it into the job's `assets/fonts/`. Real behaviour sells it: the user's lines in bubbles on the
  right, Claude's on the left with no bubble, muted tool rows (`Ran 48 commands ›`), a spinning spark while it works,
  the thread scrolling up. Model: `your-job` intro g4.
- **A GitHub contribution graph** (2026-10-06: *"should look like an actual GitHub heat map"*): canvas `#0d1117`,
  border `#3d444d`, the five levels `#151b23` / `#033a16` / `#196c2e` / `#2ea043` / `#56d364`, labels `#9198a1`,
  Mon / Wed / Fri and the Less-More legend; a lines-added figure in the diff green `#3fb950` (`+86,000`). Model: intro g15.
- **An editing app's timeline**: a neutral dark panel (`#1b1b1f` → `#131316`, white 10 % rim), clips coloured by kind
  (graphics pink `#ff7fb6`, footage violet `#8f80ff`, voice green `#3ccf8e`, music teal `#2fb7c9`), never the navy panel.

#### 🔒 COLOUR VARIETY: blue is the underlay, never the whole graphic (2026-10-06)

*"A lot of times, some of these graphics are like way too blue, and some nice variety would be better with colors
and stuff like that, especially even when I say work, sleep, play games, like those should be like different colors. Not
everything has to be blue all the time. Blue is just like the subtle underlying brand color that we're using
for like our backgrounds."* The house blue lives in the dark field's grid and light. **Peers in a set take DISTINCT
colours** (g5's Work / Sleep / Play Games = amber `#ffa12e`, lavender `#a58fff`, pink `#f2478f`; g17's row chips =
violet, coral, teal), a depicted thing takes its own (above), and type on a dark field is off-white, not muted blue.
A graphic whose every coloured element is royal / sky is the defect this names.

### Font — Inter
`assets/fonts/Inter-{Black,Bold,Regular}.otf` → copy into the render root's `assets/`
(`hf-graphics/gfx/assets/<file>`, where `reference/comp-scaffold.html`'s `@font-face` `src` points) and
`@font-face` (the headless render needs the file embedded, a system name silently falls back; `graphics-qa.py`'s
`font` check FAILs a `src` that is not there).
Headline = Black, mixed case, `letter-spacing:-1.5px`. Eyebrow label = Bold, uppercase, 23px tracking
`+3.4px`, `--muted` (the `.eyebrow` CSS below is the lock). Body = Regular, `--muted`.

### THE panel — one primitive, everything is built from it

🔒 **A CARD OVER FOOTAGE IS CLEAR LIQUID GLASS (2026-10-06: *"way more transparent and way more liquid glassy,
like a lot like the Apple style is. Right now they're just kind of basically like solid white"*; it replaced the
near-opaque frosted card of 2026-09-18).** Every overlay card that floats over your footage (callouts, lists, compare
pairs, labels, lower-thirds) is glass the footage reads THROUGH: white at 3-20 % over a 20 % dark tint, drawn by its
LIGHT (a specular rim brightest at the top-left and bottom-right corners, a sheen across the top half, a faint inner
glow), with WHITE type on it carrying a soft dark legibility shadow. The navy `.panel` below stays the primitive INSIDE a
dark full-screen scene. Models: `your-job` intro g9, g17.
```css
#card{isolation:isolate;border-radius:28px;
  background:linear-gradient(150deg,rgba(255,255,255,0.20) 0%,rgba(255,255,255,0.07) 38%,rgba(255,255,255,0.03) 62%,rgba(255,255,255,0.11) 100%),rgba(14,16,24,0.20);
  box-shadow:0 24px 60px rgba(0,0,0,0.26),inset 0 1.5px 0 rgba(255,255,255,0.50),inset 0 -1px 0 rgba(255,255,255,0.16),inset 0 0 26px rgba(255,255,255,0.07);}
#card::before{content:'';position:absolute;inset:0;border-radius:inherit;padding:1.5px;pointer-events:none;   /* the specular rim */
  background:linear-gradient(135deg,rgba(255,255,255,0.90) 0%,rgba(255,255,255,0.22) 20%,rgba(255,255,255,0.05) 50%,rgba(255,255,255,0.22) 80%,rgba(255,255,255,0.70) 100%);
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;}
#card::after{content:'';position:absolute;z-index:-1;left:1.5px;top:1.5px;right:1.5px;height:46%;border-radius:26px 26px 0 0;   /* the sheen */
  pointer-events:none;background:linear-gradient(180deg,rgba(255,255,255,0.12) 0%,rgba(255,255,255,0) 100%);}
/* on glass: type #ffffff with text-shadow 0 1px 2px rgba(0,0,0,0.40), 0 0 14px rgba(0,0,0,0.28) (a legibility shadow,
   not a glow); eyebrow white 74 %; hairline rules white 16 %; a logo chip stays an opaque white app-icon tile */
```
The `.panel` is a **solid UI surface** with a royal rim + drop shadow, so it sits *on* the field.
```css
.panel{position:absolute;background:linear-gradient(160deg,#12224e 0%,#0a1435 100%);
  border:2px solid rgba(96,146,255,0.42);border-radius:22px;
  box-shadow:0 26px 60px rgba(2,7,24,0.72), 0 0 0 1px rgba(6,13,36,0.85),
             inset 0 2px 0 rgba(140,180,255,0.22);}
.panel.hi{border-color:rgba(47,245,138,0.55);      /* the payoff state */
  box-shadow:0 26px 60px rgba(2,7,24,0.72), 0 0 44px rgba(47,245,138,0.30);}
.eyebrow{font-weight:700;font-size:23px;letter-spacing:3.4px;text-transform:uppercase;color:var(--muted);}
.head{font-weight:900;letter-spacing:-1.6px;color:var(--txt);line-height:1;}
```
Plus the small furniture that sells "tech panel" rather than "text box": a glowing status `.dot`,
a hairline `.rule`, segmented meters, bar charts. Use one or two, never all of them.

⚠️ **Glass card and panel alike read on their OWN fill — `backdrop-filter` does nothing here.** These render as
isolated alpha `.mov`s with no backdrop behind them, so a blur-the-background panel comes out
transparent and reads as a floating text ghost over the footage. Opacity in the gradient, never
`backdrop-filter`.

⚠️ **Glow = stacked blurred duplicates, never `text-shadow`.** Four copies of the same text at
falling blur/opacity (56px → 22px → 7px → sharp) is what spills real light onto the frame;
`text-shadow` at any strength stays a flat sticker halo.

⚠️ **A dot texture on type is clipped to the glyphs and kept FINE: pitch is what separates print from an LED sign.** Clip the grid with `background-clip: text`; on a ~130 px glyph a 4 px cell at 0.16 opacity reads as printed material, while 7 px at 0.34 reads as a cheap dot-matrix scoreboard. Judge the glow and the texture zoomed in AND at full frame: a texture that looks subtle at 1x can be a visible matrix at 2x, and a glow that reads strong zoomed can vanish in the frame.

#### 🔒 THE PROP GLOW — accent furniture glows, type is default-off (2026-08-31)

**Every accent-coloured prop in an overlay graphic spills light.** A progress bar, a status
dot, a lit meter segment, a list chip, a REC dot, and every solid-fill icon or glyph inside a card,
node or bubble — anything that is furniture rather than words
— carries a soft bloom in **its own colour**, the same light-spill the bg-dark full-screens get
from the glow pass. A glowing bar reads as a UI that is switched on.

**Type is the DEFAULT-OFF case, not a ban (2026-08-31).** The basic text animations, card
headlines, eyebrows and captions keep the black legibility stack and nothing else;
a glowing headline there reads as a 2012 sticker. But *"sometimes type can glow! just not on our
basic text animations. If it fits or if it's applicable then text is allowed to glow."* A neon
sign, an LED readout, a terminal's own accent glyphs, a word that IS the light source in its
scene — those may glow, and should, when the graphic's subject calls for it. The test is whether
the glow belongs to the thing being depicted or is decoration sprayed on a label. When type does
glow it still obeys the FORM rules: stacked blurred duplicates, never `text-shadow`.

Three forms of the same blurred-duplicate law, picked by the prop's size and whether it is masked:

```css
/* free-standing prop (dot, chip, meter segment, rec dot) — two rings, falling blur.
   Radii scale with the prop and cap around 24/48: a 10px dot takes 20/40. */
.dot{box-shadow:0 0 20px rgba(87,201,240,0.62), 0 0 40px rgba(87,201,240,0.30);}
.chip, .seg.on{box-shadow:0 0 24px rgba(30,72,255,0.60), 0 0 48px rgba(30,72,255,0.28);}

/* MASKED prop (a progress fill inside a rounded track) — the glow is a sibling CLONE
   outside the mask, because a box-shadow on the fill renders ZERO pixels. */
.track{position:relative;background:rgba(0,0,0,0.68);}          /* the dark bed, see below */
.barGlow{position:absolute;inset:0 auto 0 0;width:<fill %>;border-radius:inherit;
  background:<the fill's gradient>;transform:scaleX(0);transform-origin:0 50%;
  filter:blur(<0.8x the bar height>);opacity:0.6;pointer-events:none;}
.clip{position:absolute;inset:0;border-radius:inherit;overflow:hidden;}  /* the fill lives here */
```
The clone and the fill are tweened **together** (`tl.to(['#fill','#barGlow'], {scaleX: …})`) or
the glow desyncs from the bar it belongs to.

```css
/* LARGE accent surface (a chat bubble, a panel state) — the two-ring recipe floods at
   this size. One wide ring, low alpha, layered over the depth shadow. A royal surface
   glows in its OWN colour; a dark navy card glows in its RIM blue, which is the only
   light a dark surface emits. */
.bub.user{box-shadow:0 16px 40px rgba(2,7,24,0.55), 0 0 44px rgba(42,82,255,0.42);}
.bub.ai  {box-shadow:0 16px 40px rgba(2,7,24,0.55), 0 0 44px rgba(96,146,255,0.34);}
```

**Sweep the WHOLE comp, not just the obvious prop.** The rule is per-element: every accent
element in the graphic glows, so a comp with a bar AND royal bubbles needs both. Doing only
the one that was named leaves the graphic half-lit and it reads as inconsistent rather than
restrained. **An icon inside a card is the case that gets missed:** it reads as artwork rather
than furniture, so it ships flat (g16's three node icons, 2026-09-07, cleared by a whole review
round). It is a prop. And on an `<svg>` or `<img>` the glow can only be stacked blurred
duplicates behind the sharp copy, in the icon's own colour: `box-shadow` paints around the
element BOX, not the glyph, so it renders a rectangle halo or nothing at all.

⚠️ **The trap this rule exists to kill: `overflow:hidden` eats the glow silently.** Three bars
shipped with `box-shadow:0 0 15-20px royal` written on the fill and every one of them rendered
zero glow pixels, because the fill sat inside the track's own mask. It looks like a styling
choice that just isn't strong enough, so it survives review. Clip the FILL, never the glow —
and when a bar looks flat, check for an ancestor mask before touching the blur radius.

⚠️ **An icon glow beside TYPE is measured on the lane's blend, never in the browser (2026-09-28, your-job g2).** Premiere composites a straight-alpha overlay in linear light: a glow's lone faint tail (above and below an inline icon) comes out several times brighter than the browser shows, while at its sides the neighbouring words' black legibility halo flattens the glow into a dark colour the blend barely lights. g2's icons read as a tall disc, lit top and bottom and dark at the sides (ratio 2.2). What held: a tighter, weaker ring (`blur` 22→9 px at 0.36, 9→3.5 px at 0.28) spread wider than tall per icon (`scaleX` 1.24 / 1.12 on the Claude mark, 1.05 / 1.03 on a flat-sided app tile). Measure the ring's top/bottom vs left/right light on the render blended over a program frame the way the lane does. Even means within 10 %.

**The bed under a bar is `rgba(0,0,0,0.68)`,** not 0.48. The unfilled remainder has to read as
an empty track over busy footage; at 0.48 it washes out and the bar loses its shape.

**Neutral furniture keeps its depth shadow, no glow, and carries a DARK OUTLINE where it can land on a bright area (2026-09-04)** — white corner brackets, hairline rules,
avatar rings, and any light bar standing in for TEXT. Glow is for the accent colours (royal,
cyan, the red REC dot, a dark card's rim blue); a white halo reads as a render artifact. A soft drop shadow is not enough: g15's top-right viewfinder bracket sat on the blown-out key light at 1:1 stroke-vs-background and vanished; the fix that held was a 15px `rgba(0,0,0,0.88)` stroke painted UNDER the 7px white one (a real outline, legible on the light and on the dark wall alike). Measure legibility as stroke luma vs the luma immediately adjacent to the stroke, never as the window's max-minus-min (a shadow inflates that and passed a fix that had not worked).

#### 🔒 PROPS ARE SOLID FILL

**Icons and cutout props are SOLID FILL — never stroked outlines (2026-07-21: "outlines = corny").** A paper-cutout shape IS the cut paper: it gets its edge from the fill geometry and its depth from a hard offset shadow, never from a drawn border. No `stroke` around filled icons, glyphs, arrows, or props; if a shape needs an inner detail (gear hub, half-disc, bell rim), cut it as another solid fill in the second color — the rim emerges from geometry. Structural LINE elements are exempt (they are lines, not outlined fills): wires, sound arcs, brush strokes, tripod legs, register marks.

### Placement — 16:9, 1920×1080

| Zone | Box | Use |
|---|---|---|
| **Callout L** | x 80 → head_left − 60 · y 150 · max-h 560 | MEASURED per window (§ SIDE CALLOUTS); the usual side on the reference framing (the speaker sits right of centre) |
| **Callout R** | x head_right + 60 → 1840 · y 150 · max-h 560 | MEASURED per window; only when the right has more room |
| **Lower-third** | x 120 · y 780 · w 900 · h 170 | names, labels, one-line context |
| **THE LOW BAND** | **y 765 → y 1030** | anything CENTERED under your face |

Pick the side **away from your head** — measured over the whole window, never guessed from one frame
(§ SIDE CALLOUTS). Long-form has no platform safe bands — the rules are simpler: never cover your
face or important on-screen content (a demo, a screen recording, whatever you're pointing at), and
keep copy off the very edge of the frame (80 px of breathing room, you 2026-09-10; was ~100). The top edge keeps 100 px: only the sides moved to 80 (`workflows/graphics-qa.py` measures `EDGE` 80, `TOP_EDGE` 100). Those margins bound the element's EXTREME position, not its rest box (§ THE LOW BAND).
During the outro, leave the right side + bottom clear — YouTube end-screen cards snap there.

#### 🔒 SIDE CALLOUTS ARE MEASURED OFF THE HEAD, NEVER PICKED (2026-09-10)

**A side card never covers your ear, your face, or the subject, and it keeps a real margin off them:
60 px off the head (ears included), 80 px off the frame edge.** Per graphic window, measure:

```bash
uv run workflows/chin-line.py <raw> --edl projects/<job>/transcript/cuts.json --from <start> --to <end> --step 0.1
```

It prints the head's horizontal extent (the YuNet face box plus a 20 % ear allowance, on the worst
frame of the window) and the two zones that respect it, and names the side with more room. The card
goes on that side and is **as wide as the room (cap 620)** — measured as INK, so the CSS box is the
room minus its border, ring and glow (about 8–10 px: g30's 600-px box on a 602-px zone failed the
check by 2 px of border ring, 2026-09-10); the type scales with the card, the margin never gives. The plan
cell records `region` (`callout-L` / `callout-R`) and the measured `head` (`{left, right, frame}` —
copy chin-line's own `frame`, so a head measured on a 4K raw is normalised into the 1920×1080
authoring frame before the check);
`validate-plan.py` fails a callout cell without one, and `graphics-qa.py`'s `face` check fails any
hold frame whose ink comes closer than 60 px. Some cards go left, some right — that is fine; a card
on the ear is not. **The retired way** (a fixed x 1180 · w 620 box "for when you're framed left of
centre", picked from one frame) put g7, g12 and g30 on your ear for a whole shipped video
(your-job, 2026-09-07): the head spanned x 745–1250 in every window, the box started at
1180, and even the old left box (x 120–740) came within 4–50 px of the other ear. "Check one frame"
was the failure — the worst frame of the window decides, and only a sweep finds it — and the worst
frame has to be one more than a single detector call believes in (§ THE LOW BAND, ONE SAMPLE IS
NEVER THE FLOOR): the head extents are measured off the surviving samples, so read the tool's
`dropped` line before trusting a zone. you:
*"graphics just not being placed correctly relative to where my face is, where my head is — this was
honestly my biggest issue with this whole entire edit."*

#### 🔒 THE LOW BAND — y765 → y1030 (2026-08-31)

**Every overlay that shares the frame with your face lives inside it, and NOTHING is allowed
out.** Text animations, stat callouts, captions-in-graphics, a lower-third — if it sits centered
under your head, its whole stack fits between y765 and y1030. Side callouts keep their own
zones (they're beside the head, not under it); a full-screen graphic has no face to clear
and ignores the band entirely.

**The band and the edge margins bound the element's EXTREME position, not its rest position.**
Budget the registry's own travel into the rest box before authoring it: `riseOut` lifts 18 px, the
float drifts 6 px RIGHT and 8 px UP (`subtle`) or 10/16 (`medium`) — out and back from the authored
rest, never straddling it ([`creative-moves.md`](creative-moves.md) move 2) — a pop overshoots 5 % of
the box on each side and a slam 8 % ([`animations.md`](animations.md)). Checked at rest, a block
resting at y798 ships ink at y780 and a card whose right edge rests at x1840 drifts to x1846.
`graphics-qa.py` warns on it from the comp's own CSS before the render (`source:clearance`) and fails
it on the alpha sweep after.

**The band is ONE slot:** two plan cells in the same region may never overlap in time, and
`validate-plan.py` fails the pair (the rule's home is `graphics-plan` § Step 3). Merge them or let
one breathe.

**The band is the frame; SIZE is what gives.** A stack too tall for the 265px scales down
whole until it fits. That is the mechanism behind the rule that keeps coming back — **a
two-line block is smaller and lower than a one-line block.** Two lines in the band means
~115px type where one line gets ~150px, and that reads correct: two lines of 115 still
carry more ink than one line of 150. Do not widen the band to keep a big block big.
2026-08-31: *"when the text animation is just one line those are pretty much already
fine as is, but mostly for the two liners they need to be smaller and further down — they're
too close to my chin."*

**The numbers are MEASURED per shoot, not inherited.** 765 came from a 242-frame sweep of
the shipped cut: the lowest jaw line in the whole video sits at **y694**, and 765 is the
top of the one-line block range that already read clean (766–786), i.e. the chin + ~70px of
air. 1030 leaves a 50px margin off the frame edge. A tighter or wider camera framing moves
the chin by 100px+, so re-derive it:

```bash
uv run workflows/chin-line.py projects/<job>/outputs/<job>.mp4
```

It prints the lowest chin, the suggested floor, and `--annotate` draws both on the worst
frame. Feed the floor to the text-animation builder's `TOP_MIN`, to any hand-authored overlay, and
into the plan's `low_band` so the QA gate measures the same band.

**ONE SAMPLE IS NEVER THE FLOOR (2026-09-19).** The worst frame still decides — it just has to be a
frame more than one detector call believes in, and proving that is `chin-line.py`'s job, by two rules
written against measured failures (the WHY of each is in its `subject()` and `recheck()` docstrings).
Don't loosen either by eye.

- **The subject is the biggest CONFIDENT face:** every box within 0.10 of the best score, then the
  largest of those — never the plain largest box and never the top score alone (a poster or a screen
  in the room wins on score, a YuNet phantom over a shoulder on area). The plain largest box
  manufactured five chins 300px+ below the median over a 53-minute take, where this rule produced one.
- **An uncorroborated chin is re-sampled before it is believed, never just dropped:** a chin more than
  6 MADs off the window's median with no other sample within the gap is re-measured on the source
  frames either side, and dropped and NAMED with its time and score only when those frames disagree
  too. Dropping on the statistics alone threw away a real lean toward the mic (floor `y1579` against a
  true `y1746`: a band sitting on your chin with nothing saying so).

So: read the printed `dropped` line, and read how the `LOWEST chin` line justifies itself — either a
count of corroborating samples, or "proven a real lean on the source frames either side". Re-run
that second with `--step 0.1 --annotate` whenever the floor decides a layout. The sweep detects on a
960-px copy and reports SOURCE pixels (`--full-res` keeps the old per-frame path; within 5px of it at
4K, and 25x faster).

**The one exception is a DOWN arrow.** A graphic pointing at the description or the
comments has to reach the floor to mean anything — its lowest bounce frame sits ON y1030
and nothing is below it: very close to the bottom of the screen, obviously not touching it.
Shrink the arrow to make room rather than pushing past 1030.

Long-form only; the short-form Talking Head Explainer has its own look
(`presets/instagram/talking-head-explainer/graphics.md`).

---

## Copy case — labels are NOT captions (2026-08-31)

**Lowercase-casual is the CAPTION voice, and it does not extend to graphics.** Captions
and text animations stand in for speech, so they carry your lowercase register. Copy that
labels a thing inside a graphic — a card title, a nameplate, an eyebrow, an axis label —
is not speech, it is a label, and it takes **title case**.

The viewer is already inside the graphic — the copy does not need to match caption
styling to feel like it belongs.

**A leading article drops only when the label NAMES a thing.** "the claude video editor"
reads as a sentence fragment that got cut off; **"Claude Video Editor"** reads as the
name of the thing, which is what a card title is for. But in a short descriptive label
the article is part of the phrase and stays — **"The Goal"**, and the shipped eyebrows
**THE BUILD** / **THE RULES**. Test: if the label answers "what is this thing called?",
drop it; if it answers "what is this number/row?", keep it.

Diagram and node labels are labels: **"Raw Footage → One Prompt → Finished Video"**, even
when they echo the spoken line. A sentence fragment that COMPLETES an adjacent element is
not a label and keeps the caption register — "60%" over "of the way there" stays lowercase,
because it is one sentence split across two type sizes.

Eyebrows stay ALL-CAPS as specified in the templates below. Body copy inside a card
follows the sentence it is: a phrase of dialogue keeps the caption register, a label
does not.

## 🔒 CARDS NAME, SCENES ENACT — pick by what the line is DOING (2026-08-31)

Before reaching for a template, ask what kind of sentence this is:

- **A fact, a number, a name, a label** → a CARD. That content is inherently textual; a card
  presents it faster than any animation.
- **An action, a process, a back-and-forth, a thing being built** → a SCENE that shows it
  happening. A card here just restates the sentence in a box.
- **A line about the footage itself — how it was shot, captured, recorded, made** → an OVERLAY
  THAT ENACTS. Add elements that make the untouched footage read as the thing being described,
  and let a text animation carry the words alongside it.

The shipped model is the chat-thread graphic on `your-job`: the line is "prompting back
and forth," and the graphic *is* messages going back and forth with a completion bar climbing.
The retired counter-example sat two beats earlier on "I built my own editor and I've been
iterating" — a label card reading THE BUILD / my own editor / iterating for months. Same tier,
same budget, but it *narrated* an action instead of showing it. **The rule was earned on that
card (2026-08-31):** *"kinda a lazy graphic... what I really like about [the other one]
is it's an interactive visual literally showing what is actually being spoken."*
It was rebuilt as the editor itself: an app
window, clips landing on a timeline, a cursor making a cut, the tail rippling away, the mascot
at the desk.

### The overlay that enacts — the cheapest strong graphic there is

**g20 is the model, and it was praised by name in review.**

The line is "I recorded the entire process." The graphic adds four viewfinder corner brackets at
the frame's edges and a pulsing red REC dot with a REC label in the top-left, then runs the text
animation *recorded the **entire** process* in the low band. The shot now reads as a recording.

**Nothing happens to the footage — this is purely additive.** It is one alpha overlay clip on
the graphics track. The image never changes; what changes is how the viewer reads it, because
of where the elements sit — brackets on the frame's corners, a REC dot where a camera would put one.

That is why this move is worth reaching for: it enacts like a scene but costs like a card.

- **Your face is never covered** — the elements live at the edges and in the low band.
- **One overlay clip**, no takeover, no full-screen, no transform work on V1.
- **The two halves split the job:** the added elements carry the IDEA, the text animation carries
  the WORDS. Neither is doing the other's work, so neither has to over-explain.

Reach for it whenever the line is about how the footage came to exist — recorded, filmed, shot,
captured, streamed, screen-grabbed, live. The vocabulary is real capture UI: viewfinder brackets,
a REC dot, a timecode, a battery or level meter, focus marks, a rec-light border. Keep it sparse —
two or three elements is the graphic; a full fake camera HUD is a costume.

⚠️ **The tell that you picked wrong is DECORATION SHAPED LIKE DATA.** The retired card carried
a five-segment meter that stamped one segment per beat — no scale, no metric, measuring
nothing. A meter with no quantity, a progress bar with no percentage, a chart with invented
values: all worse than nothing, because they read as information and say none. If you find
yourself adding furniture to make a card feel less bare, the card is the wrong move.

**Depict with the house vocabulary, not with footage.** "I built X" becomes the product in
use, drawn from the panel primitive and self-made vector props — an app window, a timeline, a
terminal, the mascot operating it. A real-footage b-roll compilation (old clips, film grain,
scan lines, desaturation, quick cuts) is often the strongest version of such a beat, and it
stays a **manual call** — never assembled in a default pass unless you ask for it by name.

## 🎨 THE SIX TEMPLATES — compose, never invent

Every CARD is one of these (punch-cut graphics follow creative-moves.md instead). If a beat doesn't fit one, it probably doesn't need a card.

1. **Label card** — eyebrow + 2–5 word headline, one word in `--royal`. The workhorse.
2. **Stat card** — big number (Black, 96px, `--royal`) + a `--muted` label under it.
3. **List card** — eyebrow + **max 3** rows, each a small royal chip/check + 2–4 words. Rows stamp in
   sequence, 4 frames apart.
4. **Compare pair** — two stacked mini-cards, the second with a `--royal` border = the winner.
5. **Lower-third** — a name/label bar in the lower-third box. A genuine `slideIn('left')`: it
   enters from off the left edge, one of the few default cards that really slides.
6. **Annotation** — a royal arrow/underline/circle drawn onto something already on screen.
   Arrows use `arrow()` + `drawOn()` from `animations.md` § The arrow — the head is computed
   from the path's end tangent, never typed as `points`.

**And the SEVENTH thing, which is not a card at all: the SCENE.** CARDS NAME, SCENES ENACT (below)
sends every action/process/back-and-forth beat to a scene, so it needs a definition here: **a
scene is built from THE panel primitive plus self-made vector props, depicting the thing in use** —
an app window with clips on a timeline, a terminal, a chat thread with messages arriving, the
mascot operating it. It is not a template you fill in; it is composed. The shipped examples are
the chat ping-pong graphic and the editor graphic. A scene runs as long as the process it depicts,
and it lives full-screen or as a large overlay — the six templates above are for beats that NAME.

Within CARDS: no mascots, no characters, no illustrated scenes, no props, no paper/halftone/collage
texture, no gloss, no 3D, and no glow on a card's TYPE (§ THE PROP GLOW: type glow belongs to a subject
that emits light) — the card's own accent furniture (dot, meter, chips) still glows. (The punch-cut
lane has its own hero/prop rules in creative-moves.md; other looks are other presets.)

## Motion — one move in, one move out, both FROM THE REGISTRY

🔒 **In and out come from THE REGISTRY in [`animations.md`](animations.md) — `pop` · `slam` ·
`flash` · `riseIn` · `riseOut` · `slideIn(from)` · `slideOut(to)` — and nothing else (2026-08-31).** Cards used to carry their own stepped one-in-one-out language; that exemption is
retired, and a card now animates like every other element.

- **In:** one registry preset, chosen by ROLE — peers in a graphic share one entrance, the
  element whose job differs takes the contrasting one (the variation principle). Never `flash`
  on a 12 fps graphic.
- **Hold:** static apart from THE FLOAT, which runs the element's whole on-screen life with the
  in/out composing on top. Sequenced elements stamp 2–6 frames apart, entrance only.
- **Out:** `riseOut` unless there is a reason to leave another way. The `slide` family is for
  off-screen departures only, never a bigger version of the rise.
- Hard-kill every element at its end (`tl.set('#id',{opacity:0}, end)`) or it pops / lints red.
- One paused GSAP timeline, absolute times, no `Math.random` — deterministic so seeks are frame-exact.
- **Author in frames** (`F(n) = n*1001/30000` at 29.97), so stamps land on the real frame grid.

⚠️ **Never drive text from a tween's `onUpdate`.** The renderer advances by seeking frame to
frame, and whether a seek fires it depends on the pin: measured 2026-08-05 it never ran (an onUpdate
counter rendered **frozen on its first value** while looking perfect in a scrub); measured 2026-10-06
on hyperframes 0.8.105 it runs on every frame whose seek moves the playhead, but never on frame 0,
where the seek lands on the time the timeline already holds. Emit counts as discrete
`tl.set(sel,{innerText:...})` calls on the step grid instead, which is the posterized look anyway.

That's the whole CARD motion vocabulary — one move in, one move out, plus THE FLOAT for hold life.
No tracked paths, no physics — that effort belongs to other presets.

---

## 🔒 SCREEN-REC SCENES — a recording is framed, never parked (2026-09-11)

(The one exception: a page the line SENDS the viewer to may run edge to edge as full-screen b-roll with the
screen look, `creative-moves.md` move 8. A take recorded through the opt-in Screen Studio route is not
framed either: it lands full-frame in Screen Studio's own look, `graphics-plan` § THE CAPTURE GATE.)

A `screen-rec` cell (the real thing on your screen: a page, a folder, an app state, a click — the
capture rule itself is `graphics-plan` § THE CAPTURE GATE) is a full-screen SCENE built to this look,
measured on the your-job:

- **The frame is STRAIGHT and UNOBSTRUCTED.** The recording sits in a drawn window frame (a 48 px
  bar, the three dots, a URL pill naming the page) on the locked field, no tilt, nothing drawn over
  it; the prop glow behind it. It arrives with `slideIn` (the smear) and the camera pushes the whole
  hold (`camera`, 1.00 → 1.06).
- **The label and the arrow live on the label's side.** Eyebrow + headline (+ an italic sub line) at
  x120 where the room is; the arrow is SMALL and CURVED, starts BELOW the label, and swoops in to
  arrive LEVEL at the window's edge so the computed head sits perpendicular to the window side —
  never across the recording, never up to a target inside it (a head on the dark page vanishes).
- **`bg: "light"`, timeline rate.** The bg-dark chain steps at 12 fps and would step the live scroll.
- **The capture's pixels are 2x** (a page at 3840×2160, a Retina window at 2x its points): scaled in
  the comp, and exactly what a screen-recording-heavy job's 4K master wants (README § Resolution).

## Build

Same composition mechanics as every other look — comps under `projects/<job>/hf-graphics/`, one
per card, rendered to alpha ProRes 4444 and placed on the editing app's graphics track, above the grade layer so cards never take the footage grade (the track and the mechanics per app: `LANES.md` § step 5). At 4–7 short overlay cards there are **no shared-timeline chains and
no part-splitting**: each card is its own independent comp, so a tweak re-renders one ~2s comp.

**The harness ships IN this preset** — copy `reference/fullscreen-render.sh` into the job's
`hf-graphics/gfx/` as `render.sh` and author one `compositions/<id>.html` per card. That renderer
carries every locked chain (`full` = mp4 + film grain, `alpha` = ProRes 4444 straight, `STEP_FPS`,
`MBLUR`, `VER=` versioning), which is all a 4–7 card pass needs. The two *generated* builders come
in whole when the job wants them: `text-animation/` and `titles/`.

Reach for a `build.py` EMITTER only on a split-part build, authored fresh from the `graphics-build`
SOP. **Probe the comp in the browser before spending a render** — recipe in the `graphics-build` skill.
