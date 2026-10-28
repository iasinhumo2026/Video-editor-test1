# Motion Craft: the anti-slop layer

Distilled 2026-07-19 from a breakdown of Vox's documentary motion-graphics style (an After Effects tutorial breakdown). They are the difference between high-end, tactile motion design and clean-but-dead "AI slop", and they apply to the vox-collage look only (§ Scope below).

**The core insight: nothing real is purely digital.** Every element has a material (paper feels like paper, screens feel like screens), and the high-end feel comes from MANY SMALL, RESTRAINED analog decisions layered on top of clean design, never one big effect. Slop is what you get when everything is pure white, razor-edged, buttery-smooth, and texture-free.

**Scope: VOX-COLLAGE ONLY (corrected 2026-08-27).** This is the vox preset's craft layer — read it alongside `vox-collage-style.md` when that look is invoked by name, and apply it to that job's beats, graphics, footage treatments, and AI b-roll. It applies to NOTHING else, never a default graphics pass (steps 5a/5b) or a default b-roll style block: wiring these principles into default passes is exactly what made default graphics drift Vox. Other presets carry their own craft rules in their own docs.

## The nine principles

1. **No pure white, ever.** Every room has a light temperature and paper absorbs it: tint backgrounds a few percent warm or cool. Bonus reason: overlay textures are invisible on `#fff`, so pure white also defeats principle 3. (The signature sky `#ddf4ff` already complies; keep new looks compliant too.)

2. **Perfect edges look computerized.** Roughen hairlines, rules, and shape borders slightly so they read printed, not plotted. Ours: SVG `feTurbulence` + `feDisplacementMap` at low scale (2 to 3), or pre-textured PNG assets. The dial: printed, not wobbly. Overdone roughening makes elements vanish.

3. **Texture gives material.** One texture per comp does most of the work: halftone grunge for a newspaper-cutout feel, paper fiber for cards, a light leak for organic discoloration. 50%-gray textures composite with `mix-blend-mode: overlay`; black-backed light leaks with `screen` / `plus-lighter`. Source: [texturelabs.org](https://texturelabs.org) (free, high-res, commercial-safe). Scale oversized textures down and let them interact with the tinted background.

4. **Restraint is the skill.** Chromatic aberration is the canonical example: a hair of RGB split sells lens realism, a heavy split screams amateur. The intensity ladder from the source: whole comps lightest, screen treatments medium, archival/homogenized footage heaviest. When an effect looks exciting, pull it back about 40%. This applies to every effect in this file.

5. **Steer the eye.** A soft vignette (radial darkening, or edge blur behind a feathered inverted radial mask) pulls attention to the focal point. Every busy comp gets one, dialed subtle.

6. **Cut on twos.** Smooth interpolation reads sterile (the hand-drawn-era lesson Spiderverse re-taught: animators drew every 2 frames and the choppiness feels handcrafted). Quantize graphic MOTION to 12 fps (twos) or 8 fps (threes, extra collage-y) while the part still RENDERS at base fps: GSAP `SteppedEase` / `"steps(n)"`, or a progress quantizer on the timeline. Never drop the render fps itself (the `incremental-graphics.md` lock stands). Best on collage / paper / cutout motion; leave the talking head and slow camera drifts smooth.

7. **Screens are physical objects.** Never park a raw screenshot or screen recording. The screen treatment: thin horizontal scanlines (repeating-linear-gradient, about 8 px pitch at 1080p, low opacity, softly feathered; duplicate rotated 90° when a pixel-grid laptop feel fits), medium chromatic aberration, vignette, and a subtle refresh flicker (exposure ripple at about 24 Hz, 2 to 5% amplitude, built from layered sines or a precomputed per-frame array: NEVER `Math.random`, it must stay seek-safe and deterministic). Then drift a slow camera across the screen as the line is spoken: the move is what makes the viewer feel they're discovering the artifact with the narration instead of being shown a slide.

8. **Homogenize mixed footage.** Archival / scraped / phone / stock / AI clips never match each other, and raw cuts between mismatched sources jar the viewer out of the story. Run everything external through ONE shared finishing treatment per job: consistent edge blur (feathered inverted radial mask), a pixelation or CRT hint, chromatic aberration (heavy end of the ladder), the 24 Hz flicker, and film grain on top. It can be as simple as forced B&W plus heavy grain: consistency across clips matters more than which effects. Ours: one ffmpeg chain applied to every external and generated clip, e.g. `rgbashift` (1 px) + `vignette` + `noise=alls=8:allf=t+u`, tuned per job. **This is the single biggest de-slop lever for AI-generated b-roll output: grain + subtle aberration + vignette instantly kill the synthetic sheen.**

9. **Icons and cutout props are SOLID FILL — never stroked outlines.** This one is house-wide, not vox-only; its home is [`presets/youtube/default/default-overlay-style.md`](../default/default-overlay-style.md) § PROPS ARE SOLID FILL (the quote, the paper-cutout reasoning, the structural-line exemption). Vox adds only the hard offset shadow as the depth cue.

## AI-b-roll style blocks

Bake the material language INTO the prompt so the model generates analog instead of synthetic: film grain, halftone print texture, tactile paper, subtle lens imperfection, handmade feel (concept words only, no CSS/unit jargon). Then finish the clip with the principle-8 chain so the whole set matches.

## Pre-ship checklist

- No `#fff` anywhere in the frame.
- At least one texture with a blend mode on tactile comps.
- Eye guidance present (vignette or masked blur).
- Every effect at roughly half of what first looked exciting.
- Screens treated + drifting; all external/AI clips through the job's shared chain.
- Motion check: does buttery tweening serve this beat, or should it step on twos?
