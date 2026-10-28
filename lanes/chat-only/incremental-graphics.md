# Chat-Only Assemble Lane — ffmpeg composite for no-app finishes

**The graphics lane for jobs finished WITHOUT an editing app** (clients with no Premiere / Resolve /
CapCut). Graphics render as parts and an ffmpeg pass composites them onto the base cut — a tweak
re-renders one part (seconds) and recomposites (~5s), never the whole video. **Not the primary
path** — app finishes place parts as timeline clips and never need this sheet. Everything
lane-agnostic (harness, part-splitting, probing, render gotchas) lives in the **`graphics-build`**
skill; this sheet is only the ffmpeg-composite mechanics.

## The architecture

Three layer types, composited by ffmpeg over the **base** (the rough cut — rendered ZERO times by graphics):

| Layer | What | Rendered as |
|-------|------|-------------|
| **base** | the rough cut (`outputs/<job>.mp4`) | already done — never re-rendered |
| **overlay** | a card/panel floating OVER the footage | standalone comp → transparent `.mov` (`--format mov`) |
| **segment** | a part that *modifies the footage itself* (reframe takeover, full-screen cutaway, speed ramp) | standalone comp **with its own base slice** → opaque `.mp4` |
| **ffseg** | a footage move expressible in pure ffmpeg (zoom / push-in / pan) | `zoompan` on the base slice — **prefer this over a browser segment every time** |

**Overlay vs segment, one question:** does the part change the underlying footage? → segment.
Floats on top? → overlay. **And prefer ffseg over segment** wherever the move is pure geometry —
zero browser round-trip, zero brightness shift.

**The short-form caption layer is an overlay too** (`hf-graphics/captions/renders/captions-alpha.mov`,
the preset's caption builder, spanning the whole cut): it goes LAST in the overlay stack so it sits on
top of every card, with the same `:eof_action=pass` as any other overlay. On the Talking Head Explainer build it with
`captions.py projects/<job> --straight-alpha --ver sa` (→ `captions-alpha-sa.mov`, which `assemble.py` lays in place of
the placed `captions-alpha.mov`): ffmpeg's `overlay` blends straight alpha in gamma space, so the locked
90 % box (approved as Premiere composites it, in linear light, about 65 % effective over white) would read heavier;
the flag draws the box at the matching straight alpha (its captions-style.md § 1). Without `--ver sa` the straight build
lands on `captions-alpha.mov` itself, nothing on disk tells the two apart, and `assemble.py` warns that it has none (the
Windows lane test, 2026-10-13).

The harness is the standard `graphics-build` Stage-1 setup (the job's `hf-graphics/gfx/render.sh` copied from the
preset's reference, or the Talking Head Explainer's `kit/engine.py init`), and the composite is ONE script:
**`uv run lanes/chat-only/assemble.py projects/<job>`**, one ffmpeg pass, the base + every row of
`hf-graphics/placement.json` → `hf-graphics/renders/final.mp4`. Each part comp's GSAP timeline is rebased to start at
0, and `assemble.py` places each render at its row's time, frame-exact (the mechanics below; never `-itsoffset`). The
loop: edit the comp → probe → re-render the changed part (`render.sh <id> alpha|full` from `hf-graphics/gfx/`, a new
`VER` for a placed file) → `uv run workflows/placement.py projects/<job> --write` → `assemble.py` → review. "Render
everything" at the end is just the assemble.

## The assemble script (steps 5′ and 5) and the SFX mix (step 6)

A Talking Head Explainer or any placed-graphics job composites with **`uv run lanes/chat-only/assemble.py projects/<job>`**
(→ `hf-graphics/renders/final.mp4`): the base cut, laid out per the plan's `layout` map (cut FRAME-exact at every edge,
each span at its footage transform: a row's own `frame` over its mode's face-frame.json transform, through the preset's
`layout.footage_spans()`; F and O keep W's footage; a plan with no `layout` keeps the footage as it is), then every row
of `hf-graphics/placement.json` placed frame-exact, the caption layer last (its `captions.py --straight-alpha` build
when one exists). It runs the stutter guardrail itself. Then the sounds: **`uv run lanes/chat-only/mix-sfx.py
projects/<job> projects/<job>/hf-graphics/renders/final.mp4 projects/<job>/outputs/<job>-final.mp4`** (every
`sfx-plan.json` row at its level, its `fade_out_s`, its second; AAC 320k 48 kHz; with a bed to follow it writes
`outputs/<job>-sfx.mp4` instead), then `mix-music.sh` if the job has a bed. Both were job-local prototypes on the Windows
test job, each mechanic forced by a flash-scan FAIL, and are proven on demo-project (macOS, 2026-09-27).

**The assemble render is the deliverable's picture, so it is encoded at the export numbers (step 8).** `assemble.py` encodes ONCE
with `workflows/deliver.py`'s numbers for the base's frame (a vertical base → 1080×1920 H.264 High 4.2 CBR 14, less past
2:48; a landscape base → 3840×2160 CBR 50, 80 above 30 fps; `--shorts` on a 2160×3840 base → the YouTube Shorts file),
bt709 on the frames, closed GOP of half the frame rate, moov first, the base's audio copied; `mix-sfx.py` and
`mix-music.sh` copy that video and re-encode only the audio (AAC 320k 48 kHz) (since 2026-10-13). **Every job
runs `mix-sfx.py`, a job with no cue too** (an empty `sfx-plan.json`, `[]`: it mixes nothing and still encodes the
audio), so the file carries the export numbers' AAC 320k rather than the splice's 256k the assemble copies. Only the
LAST pass writes the deliverable, and nothing before it takes a final name (finalize.sh promotes a final-named file
over a newer one): no bed → `mix-sfx.py` writes `outputs/<job>-final.mp4`; a bed → `mix-sfx.py` writes
`outputs/<job>-sfx.mp4` and `mix-music.sh` writes `outputs/<job>-music.mp4` (background-music § Run it), the newest,
which finalize promotes. Prove it (ffprobe, `workflows/flash-scan.py <file> --expect projects/<job>`), then
`./finalize.sh <job> --apply --keep-drafts` promotes it to `outputs/<job>.final.mp4` with the Downloads copy. A 4K
vertical job's Shorts file is the same chain from a second composite, `assemble.py projects/<job> --shorts --out
projects/<job>/hf-graphics/renders/final-shorts.mp4`, its last pass writing `outputs/shorts/<job>.shorts.mp4` (an
earlier one `outputs/shorts/<job>.shorts-sfx.mp4`), finalized with `--variant shorts`.

The mechanics the script keeps, and why (each one was a FAIL):
- **Layout edges cut by FRAME** (`trim=start_frame/end_frame`), never float seconds: 14.8148 s is frame 443.998, which
  rounded a frame early and put every layout switch a frame before its graphic.
- **Overlays placed by frame** (`setpts=(N+f0)/fps`), never `-itsoffset`: the float offset ran each overlay a frame
  early, and `eof_action=pass` then showed the bare footage for that frame.
- **A one-frame `tpad` on every overlay**: with `eof_action=pass` ffmpeg never shows an overlay's LAST frame.
- **The enable window half a frame inside the grid**: `between(t, start, end)` on float seconds missed the first frame
  whenever `t` and `start` differed in the last digit (two double cuts on the test job).

## ffmpeg-composite gotchas (learned, don't relearn)

- ⭐ **Every overlay needs `:eof_action=pass`, or ffmpeg silently duplicates ~1-in-4 output frames
  (the stutter trap — cost six rounds).** `overlay` defaults ended inputs to `repeat`; several
  ended-but-repeating inputs make the scheduler duplicate output frames on a periodic cadence.
  The output is dead-even CFR so ffprobe/PTS read perfectly fine — content just changes ~18×/sec
  in a 24fps costume, and every input measures clean in isolation. The single exception is a
  deliberately-held final frame (a push-in that holds to the end): that one part gets
  `eof_action=repeat` — never `tpad=stop_mode=clone` after `zoompan`, which never EOFs and
  ballooned a 4s clip past 1 GB. **Detect:** `signalstats` YDIF=0 tally (clean ~0–3%, the bug
  ~25%), read on the composite BEFORE the lossy encode: an encoder re-codes a repeated frame with a
  residual, so a tally of the encoded file read 0.0 % on a 25 % cadence (2026-10-13). `assemble.py`
  tallies the composite and the base in its own pass and **exits 1 when the composite adds ≥8 %
  frames repeating the previous on a cadence (runs of one or two) to the base's own — do not remove
  the guardrail.** A longer run of identical frames is a hold (a still full-screen, a still page), never
  the stutter. A plan `fps` other than the base's rate makes the same cadence (a 24 fps base under
  a 30 fps plan repeats every 4th frame): the guard names it. Never mask stutter with `-r`/`fps=`
  (already CFR; it just re-times the dups). The `fps=` in `assemble.py` is the plan-rate conversion
  the encoder's `-r` made after the graph, moved in front of the tally so the guard sees it.
- **Segments carry their own base slice**, cut at the **PLACED time, not the build time.** If the
  base was re-spliced and graphics slide via a `PLACE_SHIFT`, a slice cut at the raw build time
  makes the segment's footage jump at the seam and run out of sync with the audio for its whole
  window — a base re-splice means re-cut the slice at the placed time AND re-render the segment.
  Verify: the slice's frame 0 luma matches `ffmpeg -ss <placed_start> -i base`.
- **The segment brightness dip — fix at the ROOT.** A browser segment round-trips footage through
  headless Chrome (decode→RGB→re-encode) and darkens it ~3% vs the passthrough base, visible at
  every seam. (1) Prefer **ffseg**: `zoompan` never enters the browser → zero shift. (2) If it
  MUST be a browser segment (rounded-card takeover revealing graphics behind the face): render
  with `--video-frame-format png` (halves the dip — the default lossy JPG extraction is most of
  it), then close the remainder with a residual **gamma** lutyuv on that segment in assemble
  (`G≈1.03` measured; re-derive by comparing `signalstats` YAVG of segment frame 0 vs its slice).
- **A browser segment reframes via the WRAPPER's layout box** — GSAP-transforming the `<video>`
  silently drops it from the render. `<video>` (`object-fit:cover`) sits in an `overflow:hidden`
  wrapper div; GSAP animates the wrapper's `left/top/width/height` (+ borderRadius/boxShadow) —
  the parent shrinks/slides and crops the untransformed video.
- **`zoompan` on a mid-video slice needs `trim=start=S:end=E,setpts=PTS-STARTPTS` in the
  filtergraph** (never `-ss` alone) — zoompan's frame counter `on` counts from the filtergraph
  input's start, so a mid-video part sees `on` already huge at frame 0 and any `on`-based ramp
  pins at its end value → a constant zoom that reads as a hard cut (invisible on a part starting
  at 0). More zoompan: crop w/h can't animate (only x/y); upscale 2× first
  (`scale=3840:2160`) so the zoom doesn't quantization-jitter; ease on output time with a cosine
  so zoom=1.0 at both seams; set `fps=` to the base.
- **Frame-snapped splices make EDL == rendered timeline**, so plan times anchor directly. A base rendered before
  the 2026-07-09 frame-snap fix drifts about 0.4 s by the end: measure its real cut with `scdet=threshold=0` (the max
  score in the gap) and cut slices with `-ss` AFTER `-i` (decode-accurate; before `-i` is keyframe-only).

## Broken audio on a finished render

The base cut's audio rides through the assemble untouched, so `hf-graphics/renders/final.mp4` carries the
in-sync track: re-promote it (re-run `uv run lanes/chat-only/assemble.py projects/<job>` if it is gone, then the
audio passes on top of it). Prove it with the decoded-audio md5,
`ffmpeg -i FILE -map 0:a -f md5 -`, against `outputs/<job>.mp4`. Never realign or reconstruct a finished track.

## Reference implementation

No sample projects ship — author the harness fresh from `graphics-build` + this sheet. The composite is `assemble.py`, never a new `assemble.sh`.
