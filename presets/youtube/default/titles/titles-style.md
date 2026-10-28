# Section Title Cards — the look

The kinetic section-title card of the youtube/default preset: Inter, a per-letter rise left
to right on an exponential curve, stepped to 12 fps with real sampled motion blur. Four things
define it, and each is a knob at the top of [`build.py`](build.py) (which carries the usage, the
provenance and every other mechanic).

**MOTION IS STEPPED, THE RENDER IS NOT.** The letters read their position off a progress value
quantized to `STEP_FPS` while the file still renders at the TIMELINE's rate (`render.sh` reads it from `FPS`, the
job's graphics-plan.json `fps`, else the raw; a card lasts whole frames of it, 90 at 29.97) — dropping the render fps instead would break the timeline (the incremental-graphics lock). 12 does not
divide 30, so steps alternate 2 and 3 frames; that judder is inherent to twelves on a thirty grid, not a bug, and the
blur covers it.
`STEP_FPS = 15` is the clean-twos alternative if it ever reads wrong.

**MOTION BLUR IS SAMPLED, NOT A BLUR FILTER.** Each letter draws a solid core plus `GHOSTS`
trailing copies at sub-step times behind it. A plain gaussian smears a glyph symmetrically, which
reads as "out of focus"; sampling the easing curve puts the density where the letter actually spent
time, so a decelerating letter piles up light at its landing point the way a real shutter does. A
small vertical-only gaussian (`feGaussianBlur stdDeviation="0 n"` — never an isotropic CSS
`blur()`, that would smear sideways too) fuses the discrete samples.

**THE CURVE IS EXPONENTIAL.** `1 - 2^(-10p)`: near-instant off the mark, then a long smooth settle.
It is what makes the entrance feel fast without feeling snappy, and it is what gives the blur its
taper. `EASE_POW` is the single most sensitive number in the builder — it decides how many 12 fps
steps the letter is actually in motion for, and a letter that is not moving has nothing to blur.

**THE RISE IS MASKED.** Each line is an overflow-hidden box exactly one line-height tall, and
letters travel a full line-height, so they emerge from behind the baseline instead of sliding in
from nowhere. Exit continues the same direction — up and out through the top. Set `MASKED = False`
for a free-floating fade instead (which is the shipped default: the masked version read as type
sliding out of a cutoff line).

The opaque card sits on the navy brand-grid backdrop, `renders/grid-bg.mp4` — a committed brand
SOURCE asset with no generator, exempt from the renders-are-regenerable-cache rule, and deliberately
not shipped to clients. Without it the card falls back to the solid navy field.
