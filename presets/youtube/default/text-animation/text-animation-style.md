# Text Animations — the animated emphasis-text default

Word-synced emphasis text for long-form YouTube: emphasize a phrase, punch a claim, or fill a
dead stretch with some editing. Each word rises in and settles into place,
timed to the spoken word. Locked 2026-08-29 on the your-job intro — the creator dialed
every value live against the timeline. **Text animations are the default sprinkle-in:
when a stretch needs something and nothing else is called for, reach for a text animation.**

**The preset IS the animation + the fonts + the layout law.** Color, glow, and position
flex per animation; the motion, the type, and the spacing rules never do.

## 🔒 THE LOCK

- **Font:** Helvetica Bold (system), lowercase, tight tracking — letters almost touching
  with a hair of space (−4.4% of size). Ink `#eef4ff` off-white. All px metrics
  (tracking, word gap, glow blur, rise) are ratios of the line's font size.
  **Real Helvetica, never the renderer's stand-in (2026-09-27).** hyperframes maps the
  family names `helvetica`, `helvetica neue` and `arial` to its bundled Inter on every OS, so a
  plain `font-family: Helvetica` renders Inter (1–4.6 % wider than the width solve, which is how it
  was found). `build.py` therefore writes the sans as its own `@font-face` family (`VE Helvetica`):
  `local('Helvetica Bold')` first, the system face on every Mac, then the bundled TeX Gyre Heros
  Bold (`assets/fonts/texgyreheros-bold.otf`, GUST licence), a Helvetica clone with identical
  advances (0.00 % on every test string), where Helvetica is not installed (Windows, Linux). The
  width solve reads the same file the render draws. Proven on macOS: the render differs from a
  forced-Heros render (so the system Helvetica drew it) and from the old Inter one.
- **Size & layout = THE LAYOUT LAW (2026-08-29; band re-measured 2026-08-31):**
  the block lives in **THE LOW BAND** (`TOP_MIN`/`BOTTOM_MAX` — the numbers are
  MEASURED per shoot, authoritative spec + re-derivation via `chin-line.py`:
  `default-overlay-style.md` § THE LOW BAND), centered
  on **cy 850** inside it. Line-height 1.05, descender allowance below the last line.
  Each line is SOLVED to a target width (**default 1250px**) so the type fills the
  screen — sizes are derived, never picked. **Lines balance to the same width**: a short
  last line automatically gets bigger type (capped at 2× its sibling — past that reads
  broken), so a multi-line block is a clean rectangle. ⚠ The one-big-word treatment is
  for a genuinely SHORT standalone last line ("one big word in the emphasis font");
  splitting a normal phrase to force it "looks bad" — regular phrases break into
  near-equal lines at near-equal sizes. **The band is the hard frame and size is what gives**, which
  is why a two-liner comes out smaller and lower than a one-liner.
- **Emphasis sprinkling:** mark 0-2 power words with `*asterisks*` in the text.json
  phrase → they set in Playfair Italic w700 at x-height parity. Adds variation and
  styling; if it's not needed, don't do it. Display text renders AS TYPED (a capitalized
  proper noun stays capitalized); transcript matching ignores case.
- **Entrance:** small rise easing to rest (**22px at 90px type**, ratio-scaled) —
  `power3.out`, 0.55s: fast off the mark, curves, slowly rests into place. **No
  fade-in** — the word cuts to full opacity the instant it starts. Nothing else moves.
- **Sync:** word start times come from the canonical transcript
  (`outputs/<job>.transcript.json` — never re-transcribe), each led **80 ms early** so
  the settle lands on the audio. This lead is what makes it feel on time; without it the
  rise reads late.
- **Glow (default on):** a faint black glow behind each word for pop + readability —
  **stacked blurred duplicates of the word, never text-shadow** (the house glow rule):
  wide layer blur 24/90 of size @ 1.0 + tight layer 9/90 @ 0.80, both black (2026-08-29).
- **Exit:** the registry's `riseOut` on the whole block ([`../animations.md`](../animations.md)),
  ~0.7s after the last word lands (`hold` knob). Tighten the hold when the next spoken beat needs
  the frame clear.

## The two-font system (2026-08-29)

**Helvetica Bold is the standard text font. Playfair Display Italic at weight 700 is
the emphasis font** (locked 2026-08-29 after A/B-ing Instrument Serif and DM Serif
against your reference sample) — for the one power word / proper noun in a phrase
("edited by *Claude*"). Emphasis can also be an underline or a highlight animation; the
font swap is the go-to. The exact recipe, all four locked:

- **File:** `PlayfairDisplay-Italic-VF.ttf` from `assets/fonts/` (variable font — copy
  into the job and `@font-face` it with `font-weight:400 900; font-style:italic`, then
  use `font-weight:700`; a system name silently falls back).
- **Size = X-HEIGHT PARITY, measured not guessed:** Playfair sits large on its body, so
  it runs at nominal **×1.033** next to Helvetica (126px beside 122px Helvetica). Verify
  by lowercase ink height (PIL on the TTFs), never by eye — the old "+15-20%" rule was
  an Instrument Serif artifact and oversized Playfair by 16%.
- **Tracking:** −2.8% of font size (−3.5px at 126px) — the tightest before the serifs
  collide. The surrounding Helvetica keeps its own −4.4% lock.
- **Style:** italic always; the weight-700 axis is the bold, no stroke hacks.

## Variety-law knobs (added 2026-08-29, your-job rest-of-intro)

- **`~tildes~` mark a RED word** (`#ff4d5e`, the negation/danger accent): "i ~didn't~ have
  to babysit", "~defeats~ the purpose". One red treatment per animation, never stacked with serif
  on the same word.
- **`"entrance": "slam"`** — the heavier stamp (with the Impact), for beats like "one shot." The
  default is the rise (`riseIn`, scissors). **`"pop"` / `"punch"` are REFUSED** — type never pops:
  [`../animations.md`](../animations.md) § TEXT NEVER POPS (`build.py` exits, `validate-plan.py`
  fails the cell).
- **`"entrance": "flicker"`** — the builder's spec name for the registry's `flash`: the whole
  block strobes in on the locked 7-frame pulse pattern (for stakes/legal-vibe beats). Default
  stays the rise (`riseIn`).
- **`"tilt": -2`** — rotates the block (the air-quotes skeptic treatment: "\"fully automated\"").
- **`"display": "..."`** — render different words than were spoken, 1:1 token map ("*never*
  been built before" over the spoken "ever been built before"). The caption is the MEANING;
  use when the spoken fragment reads broken out of context.
- **`"place": <t>`** — clamp the animation's timeline place to a clip-head V1 cut so it can't
  bleed backward across the edit; word 1 just loses part of its 80 ms lead.

**Since 2026-10-06 every text animation carries HyperFrames' motion-blur component (*"the new motion blur does
work pretty smoothly. What if we just apply that to pretty much all of our graphics that would benefit from it"*).**
`build.py` loads `hf-motion-blur.js` (beside it) and marks every word `data-hf-motion-blur`, the first one included,
so each rise, slam and rise-out integrates over a real 720° shutter in the page; render WITHOUT `MBLUR` (the MBLUR
lines below are the route it replaced). The rise-out's travel rides the words and its fade the block, because the
component only sees an element's own transform. A cell opts out with `"shutter": false`; the flicker entrance moves
nothing and carries none. Prove a render with `uv run workflows/motion-blur-ab.py projects/<job>/hf-graphics/text-animation <id>...`
(every moving frame of every word must differ from the same comp rendered without the component;
[`creative-moves.md`](../creative-moves.md) 4b item 3).

## The slam (2026-08-31)

The scale entrance a text spec can reach is **`slam`**, and its shape lives in the registry:
[`../animations.md`](../animations.md) § The presets (why the pop and the slam are different shapes
too). The builder holds the scale shapes in `SCALE_PRESETS`; the slam is opt-in per spec, since the
default is the RISE (`riseIn`). `pop` and `punch` are the OBJECT vocabulary and are refused here
(§ TEXT NEVER POPS). Per-slam overrides keep their historical `pop_` names, which is what `build.py`
reads: `pop_from` / `pop_over` / `pop_frames` / `pop_ease` (`pop_over: 0` = settle shape).

**The MBLUR route** is what the motion-blur component above replaced, and what a cell that opts out
(`"shutter": false`) renders with when it needs blur — never with the component on (one blur, not two),
never on 12 fps:

```bash
MBLUR=1 MBLUR_SS=8 MBLUR_SHUTTER=5 ./render.sh <id>   # the lock (8x is the renderer's ceiling)
```

It is TRUE motion blur, not a blur filter: the renderer supersamples at `MBLUR_SS` (8 at the lock; the
script's bare default is 5) x the target rate, averages `MBLUR_SHUTTER` (5 at the lock; bare default 3)
consecutive frames into each output frame, then decimates back — about a 225-degree shutter at the lock.
Its three traps, each a real bug first, are documented in `render.sh`'s header: average PREMULTIPLIED
pixels (straight alpha fringes every soft glyph edge), `tmix`'s window is TRAILING (the shutter centred on
output frame `m` is sample `m*SS + (SHUT-1)/2`), and the supersampled stream ends mid-group (`tpad=stop=SS`
or the last output frame vanishes). Verify any change to that chain against a no-blur render of the same
comp: same frame count, same onset frame (a shifted onset means the text no longer lands on its word).

**Verify STRUCTURE, not bit-equality — the renderer is not reproducible on motion frames (measured
2026-08-31).** Two runs of a byte-identical command differed on 8 of 45 frames, every one a moving frame,
up to 108/255 on glyph edges (about 0.27% of pixels; sub-pixel sampling jitter). Static frames come back
bit-identical and most run pairs match exactly, so a clean A/B proves nothing and a dirty one is not
evidence of a regression. Compare frame count, onset frame and measured positions; to prove a script
change is a no-op, diff the RESOLVED commands (`bash -x`), which is deterministic.

## Flex per animation (the "sometimes" knobs)

- **Placement:** `center` is the default and follows the layout law (low block, cy 850);
  `left`/`right` — beside the face, x120 from the edge, default y300, on the side away from his
  head as measured over the window (`default-overlay-style.md` § SIDE CALLOUTS). `width` widens/narrows the fill target;
  `cy`/`y` shift the block; `size` forces a fixed size and disables the solving.
- **A text animation never bleeds across a V1 cut (2026-08-29), and the builder enforces
  it (2026-09-02).** The text belongs to its shot. `build.py` reads `transcript/cuts.json` and
  ends every comp ON the next V1 cut by itself (`"until"` overrides: a number, or `null` to
  disable). Two exits are then possible and it picks: if the last word can settle and hold
  ≥ 0.25s before the cut, the rise-out plays (two frames before the end, hard-killed on the last
  frame); if not, **the cut IS the exit**, no fade, the picture cut carries it, exactly as a hard
  cut to a full-screen is its entrance. `<id>.meta.json` says which (`"exit": "riseOut" | "cut"`)
  and nothing is trimmed by hand any more. A cut that falls INSIDE the phrase is a ⚠ (split the
  phrase).
- **Color:** black variant (`"color": "#111"`) for bright backgrounds.
- **Glow off** (`"glow": false`) when the text already contrasts hard with what's behind it.
- **Line breaks:** `lines` splits the phrase; default is one line. Break so no line
  crowds the 1920 frame (~100px breathing room each side).
- Never cover the face; during the outro keep the right side + bottom clear (end screens).

## Usage

```
cp -R presets/youtube/default/text-animation projects/<job>/hf-graphics/text-animation
cd projects/<job>/hf-graphics/text-animation
cp text.json.example text.json   # phrase per animation; knobs optional
./render.sh                      # → renders/<id>-alpha.mov + the PLACE TIME per animation
```

- Build reads the job's canonical transcript automatically (folder position derives the
  job; `--job <dir>` overrides). It prints where each animation goes on the timeline (also in
  `compositions/<id>.meta.json`) — place the alpha mov on the graphics track (V3 on this preset's
  Premiere/Resolve track map) at exactly that time.
- Straight alpha, correct for Premiere/Resolve (drop it on an overlay track in any other app
  the same way). A lane that composites premultiplied converts on its own side — see
  `LANES.md` § step 5.
- **`render.sh` rebuilds every comp it renders, so its knobs are the builder's (2026-09-28).** A hand
  `build.py` run is overwritten by the next render: on a 4K job a hand `--scale 2` build came
  back 1920x1080 and all seven text renders were laid at Scale 200. It runs the builder through
  `uv run build.py` (Pillow from its PEP 723 header and `build.py.lock`), never a bare `python3`, which
  loses Pillow whenever Homebrew moves python3 to a new minor (2026-10-13).
  - **`FPS`**, the **timeline's** exact rate: the render runs at it and `render.sh` passes it to
    `build.py --fps`, which computes the two-frame exit margin and the hard-kill frame from it.
    Unset, it is the job's `graphics-plan.json` `"fps"`, else the first video in `raw/`, else
    `30000/1001` with a warning (the full-screen renderer's order); the printed line names where
    it came from. Pass `FPS=` when the timeline runs at another rate than both.
  - **`SCALE`**, the render size in 1080 frames, passed to `build.py --scale`: `2` renders the
    SAME 1080 layout at 3840x2160 on a `scale(2)` stage for a 4K timeline. Unset, it is the job's
    first raw video as a whole multiple of 1920x1080 (resolution follows the footage:
    [preset README](../README.md#project-setup)), else 1 with a warning; the line `render.sh`
    prints names the scale and where it came from. Pass `SCALE=` when the timeline is not the
    raw's size.
  - **`STEP_FPS=12`** animates at 12 fps and holds each frame back up to `FPS`, capped at the
    comp's own span (the full-screen renderer's expansion), so the mov is always at the timeline
    rate; a bare 12 fps mov drifted off the grid. Never with `MBLUR`.

  ```bash
  SCALE=2 FPS=24000/1001 ./render.sh g3a   # a 4K 23.976 timeline, whatever the raw says
  ```
- **Phrase = the words as SPOKEN; markers are punctuation-aware** (`*official*.` and
  `*official.*` both show "official." in emphasis). A filler the copy leaves out ("well over,
  you know, six months") is skipped automatically, up to three; a paraphrase is not: on a miss
  the builder prints the closest transcript run with timestamps. `display` renders different
  words over the spoken timing (1:1 token map).
- The band fit accounts for the rise-in travel: a block is sized so its ENTRY frames (22px
  below rest, ratio-scaled) stay above y1030, not just its rest position.
- **Re-renders get a new filename** (`VER=b ./render.sh p1`) and a fresh import — never
  overwrite a mov an editing app has placed.

When to reach for a text animation and how it combines with the other moves:
[`../creative-moves.md`](../creative-moves.md).
