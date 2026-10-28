# Backgrounds — the two standard full-screen fields

The go-to backdrops for full-screen graphics on the youtube-default preset. Locked
2026-08-29 (the creator dialed both live against the Premiere monitor). Anything else is
opt-in by name.

- **`bg-light`** — light-gray radial field (`#f2f3f6` → `#dde0e7`), a feathered
  navy-tinted vignette (7 eased stops, corners land ~45% darker than center, no visible
  onset ring), and **film grain baked in** (luma-only temporal noise, strength 7 — real
  moving grain, added as an ffmpeg post-pass in render.sh).
- **`bg-dark`** — **an earlier short's approved dark field, on every dark full-screen (2026-10-06: *"I
  adjusted it in our last short form video... we need to take all those adjustments into
  here... darker, and the grid a little lighter, and added some grain"*).** Fill `#010102`; a 1 px grid
  (`rgba(74,124,255,0.17)`) every 90 px on the 1920 stage; a super-slight blue centre light (a 1600 px disc,
  `radial-gradient(circle at 50% 50%, rgba(40,84,255,0.07), rgba(40,84,255,0.024) 38%, rgba(40,84,255,0) 68%)`);
  the DRIFT on the main timeline (grid + light together: x +38 and scale 1.06 over 5.5 s, y +22 over 3.7 s,
  `sine.inOut` yoyo); the vignette `radial-gradient(120% 100% at 50% 50%, rgba(0,0,0,0) 55%, rgba(2,5,16,0.38) 100%)`;
  the glow pass over the WHOLE frame (`GLOW_FULL=0.26`, below), which is also what lifts the black; and grain 5 made at the 1080 frame's scale (`GRAIN_1080=5` on the render: per-pixel noise on a 4K render averages
  away). The working CSS + drift: `projects/your-job/sections/intro/hf-graphics/gfx/compositions/g5.html`
  (`#bg`, `#drift`). **Match that short's FINAL, not its spec (2026-10-06: *"The grid needs to be much lighter. Are you sure that's
  the same one?"*):** the short's glow pass ran over its WHOLE panel, which lifted its black from luma 1 to about 8 and
  its grid lines to about 21 (phase-averaged over the empty panel), so the spec values under a content-only bloom rendered
  the lines at half that. The short's own bloom over the whole frame (`GLOW_FULL`) and the grid at 0.17 (the 4K line is
  anti-aliased over 3 px) put it back: measured at the 1080 scale, black 8.8 and lines 21.3 against the short's 8.2 and
  20.8. Re-measure after any change.
  The values came from `presets/instagram/talking-head-explainer/graphics.md` § 8, where every step
  of your dial-in is recorded. Retired: the navy `#0d1a3a` → `#050b20` field with a 100 px grid at 9 % (2026-09-18 → 10-06).
  **Blue is the field's underlying tone and nothing more (2026-10-06: *"way too blue... Blue is just the subtle
  underlying brand color for our backgrounds"*):** what sits ON the field takes its own colours (§ BORROWED PALETTES
  and § COLOUR VARIETY in `../default-overlay-style.md`).

🔒 **THIS IS THE HOME OF THE FIELD/FLAGS PAIRING. Any full-screen comp built ON bg-dark carries
the GLOW pass AND renders 12 fps style** (`STEP_FPS=12`) — the two travel together as the
dark-field treatment, and **bg-light full-screens get neither** (2026-08-31). A dark full-screen renders
`STEP_FPS=12 GLOW_FULL=0.26 GRAIN_1080=5 ./render.sh <id> full`. **THE GLOW IS THE RENDERER'S, IN FLOAT (2026-10-06:
*"why can't it just be a smooth gradient the whole way?"*):** `GLOW_FULL` runs the short's bloom (gblur sigma 30 at the 1080
scale, eq brightness 0.12 contrast 1.12, curves 0/0 0.5/0.62 1/1, screened at 0.26) over the whole frame in float and
dithers it with the grain. The comp carries NO CSS `#bloom` clone, no lift layer and no stacked blurred copies of a prop:
those composited a wide near-black blur in 8-bit and showed contour rings round the panels and visible steps in every halo. Pick the field and the flags follow.
The grid is a SIBLING layer in these comps — any dim/blur tween on the content must
name it too (`'.wall, #grid'`), or it stays sharp while everything else recedes.

## Rendering

```
./render.sh              # both → renders/bg-{light,dark}.mp4  (6s, 1920×1080)
./render.sh bg-light     # one
VER=b ./render.sh bg-light   # versioned — NEVER re-render onto a placed path
GRAIN=0 ./render.sh          # skip the grain pass; GRAIN_STRENGTH=7 is the knob
FPS=30000/1001               # default; match the timeline when it matters
```

**What a full-screen comp actually consumes is the CSS field, not these mp4s** — it bakes the
gradient + vignette into the comp (`../creative-moves.md` move 2), so `renders/` is a
preview/bed artifact: look at it, loop it behind something, ignore it otherwise.

**Renders are regenerable cache, not committed** — the grain makes bg-light ~88MB
(temporal noise defeats the encoder), so the comps + this script are the source of
truth; rebuild in ~90s per asset. For a longer bed than 6s, loop the clip in the
editor or bump `data-duration` and re-render.

## The vignette lesson (2026-08-29, cost three flat iterations)

Vignette intensity lives in the PIXELS, not the alpha values: with a big gradient
ellipse (105%+) the far stops land OUTSIDE the frame, so raising the corner alpha does
nearly nothing on screen — three "more intense" bumps moved the measured corner 5 luma
total while looking identical. Keep the ellipse small enough that the full ramp lands
inside the frame (78% 72% here), and verify a change by SAMPLING the render's corner
pixels against the previous version, not by re-reading the CSS.
