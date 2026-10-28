# Vox Print-Collage (Blue-Led): LOCKED

The long-form motion-graphics look: editorial print collage in the style of the Vox reference sheets, translated into your blue-led palette. Locked 2026-07-20 on the shipped `your-job` intro after v1's glossy 3D "casino" look was rejected ("style sucks ass"). Everything here is flat ink, aged paper, and print artifacts: **no gradients-as-lighting, no gloss, no glow, no blur shadows, no pure white. Ever.**

**Required reading first:** [`motion-craft.md`](motion-craft.md) (the craft principles this look implements). **Building it in Premiere:** [`premiere-lane.md`](premiere-lane.md) — this look's own timeline architecture (4K over 1080p at Motion Scale 200, adjustment layers ABOVE the graphics, film-feel chain, grain on V5). It moved here from `workflows/` on 2026-08-31 because it is a look, not a lane: **its grade sits over the graphics and runs after them, the exact inverse of `youtube/default`**, and living in a shared workflows folder made that the single most likely thing to leak into a default job. The lane-agnostic Premiere craft (keyframe laws, clip lifecycle, b-roll placement) stayed behind in the `premiere-pro` skill. **Visual reference:** the reference pack does not ship — the written spec below is self-contained; follow it exactly.

---

## 🔒 Palette

| Token | Hex | Use |
|-------|-----|-----|
| `--cobalt` | `#3a5be6` | the field: flat full-frame background (lightened from `#1e43e0`, 2026-07-23) |
| `--paper` | `#f3ead8` | cream paper cutouts, plates, light text on cobalt |
| `--paper2` | `#efe3cc` | secondary paper tone |
| `--ink` | `#101b3a` | navy ink: pictograms, rules, text on paper, all shadows |
| `--cyan` | `#57c9f0` | fills + misregistration offsets (e.g. the shadow color under ink text on paper) |
| `--yellow` | `#ffd534` | hand-drawn accents ONLY (asterisks, squiggles, the arrow), and only on a genuine peak land moment, never per-graphic garnish |
| red | `#d8342c` | rare hard accent: paintbrush X's, the mascot cape |

## 🔒 Materials & surfaces

- **The field**: flat cobalt + halftone dot screen + corner shading + vignette (from `build.py` `FULL_BG`):
  - dots: `radial-gradient(circle, rgba(16,27,58,0.5) 1.6px, transparent 1.9px)` on an `11px` grid at `opacity:0.5`
  - two soft ink corner radials + a `radial-gradient` edge vignette (`rgba(8,12,32,0.45)` at the rim)
- **Paper plates**: cream rectangles with **rough torn edges** via the seeded `roughClip(ids, W, H, seed)` clip-path helper (13 jitter points per side, LCG-seeded so renders are deterministic). Never a crisp CSS rectangle, never `border-radius` as the "softener."
- **Shadows are HARD offset ink, zero blur**: text `text-shadow: 7px 6px 0 rgba(16,27,58,0.85)` (scale offset with size: 5px 4px for ~50px type, 12px 9px for 300px type); photos/SVG `drop-shadow(7px 6px 0 rgba(16,27,58,0.4))` or a duplicate path translated `(≈10,≈8)` at 0.35–0.5 opacity. Ink text on paper takes a **cyan** shadow (`6px 5px 0 rgba(87,201,240,0.7)`) = print misregistration.
- **Halftone goes INSIDE fills, not on top as sheen**: SVG `<pattern>` of ink dots (r ≈ 1.5–1.9 on a 5.5px cell) laid over yellow/cyan fills (sun, stars, glows).
- **Film grain, animated**: two 220px `feTurbulence` tiles (baseFrequency 0.9, different seeds), `mix-blend-mode:overlay`, alternated every 0.125s at `opacity:0.26`. Full-frame comps also get the `#vignette` layer.

## 🔒 Type

Impact / 'Arial Black', ALL CAPS, tight `line-height:1`, letter-spacing 3–12px scaling with size. Cream on cobalt (ink shadow) or ink on paper (cyan shadow). **Per-word rotations ±1–2°** so nothing sits laser-straight: it's a collage, words are stamped on.

## 🔒 Icons & props

- **Pictograms/symbols = SOLID ink fill, never stroked outlines** — the house rule ([`default-overlay-style.md`](../default/default-overlay-style.md) § PROPS ARE SOLID FILL); here the inner detail is a paper-colored fill inside the ink shape.
- **Hero objects = real B&W newspaper photo cutouts**, not vector: nano_banana_2 product shot on white (into the job's `assets/icons-src/`) → ImageMagick: corner flood-fill cutout (interior whites survive, that's the newspaper look) → `-ordered-dither h6x6a,5` at ~360–560px → point-filter upscale ~172% for chunky visible dots → black→`#101b3a`, white→`#f3ead8` → dilated+spread ragged paper rim. (Photo variant, e.g. the artist: gray → normalize → `-level 8%,92%` first.) The ImageMagick chain above is the complete recipe.
- Mascot: optional — add your own sticker asset (about 560px canvas, side-fixed) to the job's `assets/icons/`.

### Halftone cutouts: two mappings, pick by what's behind them

The line above is the **opaque duotone plate** (both ends of the dither map to solid colors, so it sits ON the cobalt field). A cutout that has to let a **paper field read through the dots** is a different mapping, and the two are not interchangeable. Locked 2026-07-31 on `your-job`. No sample project ships: author the two-mapping ImageMagick chain fresh per the spec above.

| | Opaque duotone plate | Transparent dot screen |
|---|---|---|
| Sits on | flat cobalt | paper / any live background |
| Dither | `-ordered-dither h6x6a,5` (5 levels fine) | `-ordered-dither h6x6a` **bilevel, no levels arg** |
| Ends map to | black→`#101b3a`, white→`#f3ead8` | dot→ink, white→**transparent** |

⭐ **The levels arg is what breaks the transparent variant.** Alpha is effectively binary here, so every intermediate gray a multi-level dither produces gets flattened into solid ink by the colorize, and the cutout ships as a **silhouette with no dot structure at all**. Bilevel is mandatory the moment the background shows through.

⭐ **Carry the subject MASK separately and re-apply it after the dither.** Studio white is *near* white, not white, so it dithers into a faint dot field across the whole bounding box and the white-to-transparent step misses it. Every cutout then ships with a visible grey rectangle around it. Take the alpha from the corner flood-fill, resize it alongside the dots, and set final alpha = `invert(dots) × mask`.

⭐ **PRE-DITHER WIDTH is the fineness knob, not the upscale %.** The `h6x6a` cell is a fixed 6px, so what decides how fine the screen reads is how many cells span the subject. Two independent dials:

- **Fineness** = pre-dither width. `520px + 172% upscale` reads as chunky dot-matrix; **`900px + 100%` is the lock** (printed dot read, with real crumb and knuckle detail surviving). Past about `1200px` the dots dissolve and it is just a grainy photo with the halftone identity gone.
- **Coverage** = gamma, applied before the dither. `2.4` is the lock. Lower is heavier and darker, higher washes out.

your calibration, 2026-07-31: the first pass at 520/172% was "too chunky", and hero objects want "a little bit more detail, less intense halftone."

## 🔒 Motion language

- **Stamps, not tweens.** The 2-phase stepped pop (from `build.py POP_JS`): hidden `{scale:0.3, rotation:rot-10}` → `{opacity:1, scale:1.16, rotation:rot+3}` at t → settle `{scale:1, rotation:rot}` at t+0.125. Exit `popOut`: two stepped drops (+140px/0.55, +380px/0.18, gone at t+0.25).
- **Collage moves animate on twos** (steps every 2 frames), including paint-stroke dash reveals (main stroke + dry-brush bristles + splat dots) and grain flicker. Continuous easing is reserved for camera/scene moves.
- **Frame rate**: everything lives on the 23.976 base grid (`k·1001/24000`). Render graphics at the base fps, never resampled; "twos" means every 2 frames of that grid (~0.083s steps).
- **Scenes slide** (conveyor: full 1920×1080 cells sliding up/left), and full-frame comps exit via the **two-surface push** at a real V1 cut (comp slides out while the footage rises in, baked Transform keys both sides: [`premiere-lane.md`](premiere-lane.md)).
- **Camera follows on a spring, never hard-locked** (underdamped hunt, overshoot on direction changes): hard tracking reads robotic.
- Beat anchors = **measured acoustic onsets**, frame-snapped (`k·1001/24000`), never raw WhisperX starts.

## 🔒 The homogenize pass (ONE adjustment layer over everything)

On the Premiere timeline, a single adjustment layer (V4) spans the whole graphics section and fuses every graphic, footage move, and AI clip into one filmed surface. Exact shipped values (read live off the your-job layer, 2026-07-22), effect order top to bottom:

1. **Transform** (the constant film wiggle): Position = 489 baked keys on twos, random-walk ±5px x / ±4px y at 4K (LCG-seeded, deterministic; bake recipe in [`premiere-lane.md`](premiere-lane.md)); Uniform Scale OFF, Scale Height 101 + Scale Width 101 to hide the shifted edges. Intrinsic Motion stays static: it's inert on the image under an adjustment layer.
2. **VR Glow**: Luma Threshold 0.5, Glow Radius 200, Glow Brightness 0.2, Glow Saturation 1. This is the ONE glow in the look: a global analog lens bloom on the whole frame, never per-element.
3. **Lens Distortion**: Curvature −7, Fill Alpha ON, all decentering/prism at 0.
4. **VR Chromatic Aberrations**: Red −5 / Green 0 / Blue +5, Falloff Distance 25, Point of Interest centered.
5. **Lumetri Color**: your grade. Hands off.

Above it, V5 carries the real grain footage (`heavygrain`) across everything. the editor dials CA/glow/lens taste by hand; leave those dials alone and never re-add effects they removed (Wave Warp was tried and cut).

## Never do

Gloss, glow, or bloom on any ELEMENT (the only glow is the global finishing-pass VR Glow above), blurred shadows, gradients as lighting, pure white, crisp vector edges on paper elements, outlined icons, yellow as default garnish, dead-straight text, hard-locked camera tracking, mid-flight fades on flying objects (fully opaque or gone).

## Notes

- **AI clips in this style have NO locked broll block yet.** The source job's broll.json carried the rejected v1 casino block (fisheye, navy/gold glow): do not resurrect it from history. Write a fresh style block in the language above with your AI-video tool, and homogenize per motion-craft.
