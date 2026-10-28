# Highlight — the tracked marker and the tracked box over a screen recording

What we're pointing at, on a recording. Two looks, picked by what the target IS (2026-10-06), both locked to the
target through the recording's own zooms by REGISTRATION, the default on every job. An annotation cell, never a card.
Shipped on `your-job` (intro hi02-hi04).

| Target | Look | Builder | Sound |
|---|---|---|---|
| a phrase inside running text (a line of a post, a sentence) | **the yellow highlighter**: a yellow marker band wiped on, the text reading dark on it | `bake.py` | `highlighter` (the marker stroke) |
| a stat, a tile, a badge group that stands on its own (vidIQ's Outlier 47.3x, a views + score pair) | **the red box**: a rounded red rectangle drawn clockwise round it, a subtle own-red glow | `box.py` | `glow` (the glow chime) |

## Tracking: registration, never OCR (`workflows/track-region.py`)

you, 2026-10-06, on the OCR-tracked band: *"I don't know why it's moving around so much... It's not even smooth...
glitches out, changes shape for one frame."* OCR boxes the words a little differently every frame and bridged its
dropouts mid-zoom linearly between two differently sized boxes. A Screen Studio zoom is a pure scale + offset of the
screen, so the tracker measures THAT: ORB features on every frame matched to one settled reference frame, a RANSAC
similarity fit, the box mapped through it, a light 3-tap smooth. The box can only scale and move as one, so it never
changes shape, and it follows a zoom (motion blur included) continuously.

1. Measure the box ON a settled, legible reference frame of the PLACED recording render, in the 1920 frame (an OCR read
   of that one frame with `workflows/track-text.py` gives the text box; widen by eye to the whole tile or badge group).
2. `uv run workflows/track-region.py <dir>/hf-graphics/gfx/renders/<rec>.mp4 --ref <frame> --box x0,y0,x1,y1 --from <frame> --to <frame> --out projects/<job>/review/tracks/<name>.json`
   Check it by drawing the box on a few frames across the zoom before building.

## The yellow highlighter (`bake.py`)

2026-10-06: *"it should be yellow and then invert the colors so it's like a proper highlight."* Inside the band
every pixel becomes yellow `#FFE14D` x the page's light: on a dark page the recording's luma is inverted (dark page →
bright, light text → dark) and stretched so the bare page lands on full yellow; on a light page it is used as it is.
The text keeps its shapes and reads dark on yellow. The band: the track's box, ends rounded `min(10, 0.15 × h)` px,
wiped on left to right over the registry's DRAW (9) frames, power2.out; it holds on the track and fades out over 6
frames that complete 2 frames before the end.

**Baked, so it is FRAME-LOCKED to the render it was baked from**: the overlay carries the finished pixels, is laid with
a NORMAL blend (no `blend` on the cell: any lane), and its comp frame k is render frame `--from` + k, so the cell starts
exactly at the recording's start + from/fps and never runs past the recording's own end. A re-render of the recording
is a re-bake.

`uv run presets/youtube/default/highlight/bake.py <rec render.mp4> <track.json> --from <f> --to <f> --ref <settled f> --out <dir>/hf-graphics/gfx/renders/<id>-alpha-<ver>.mov`

## The red box (`box.py`)

you, 2026-10-06, on the 47.3x outlier: *"a line that animates around... in a clockwise motion... the square line... a
red, slight subtle glow line."* A rounded `#FF3B3B` rectangle, 4 px on the 1920 stage, drawn clockwise from the
top-left corner's end over 12 frames (power2.inOut, round caps), held on the track, a 6-frame fade before the end. The
glow: two blurred copies of the stroke (SVG `feGaussianBlur` 5 px at 0.55, 12 px at 0.25), never `drop-shadow`. Cut in a
frame or two before the word that names the stat. NORMAL blend.

`uv run presets/youtube/default/highlight/box.py <dir> <id> <track.json> --from <f> --to <f>`, then from
`<dir>/hf-graphics/gfx`: `VER=<v> ./render.sh <id> alpha`.

## Placing either one

Plan cell: `kind: annotation`, no `blend`, `start` = recording start + from/fps, `end` = start + frames/fps, never past
the recording's end. The placer lays it on V4 over the recording on V3 (state the overlap in `content`); the sound is a
hand row at comp time 0 (the box's draw starts on frame 1: 0.0417) in `hf-graphics/sfx-hand.json`. No float (it would
pull the mark off its target): graphics-qa's float check is waived per id in `qa-waivers.json` ("a tracked annotation").

Retired: the white Difference band (2026-10-05 → 10-06; `build.py` still writes it), the OCR track as the band's driver,
and the red glowing box of 2026-10-03/04 drawn on a plain OCR box.
