<!-- ⚠️  BRAND VALUES BELOW ARE PLACEHOLDERS — replace with your own.
     Fill in brand-kit.md and tell Claude "apply my brand kit", or edit the values here directly. -->

# TikTok/Raw Style — your LOCKED preset (hook card + line captions)

The standard graphics + caption treatment for **short-form TikTok/raw talking-head** videos
(the "front hook card only, then raw" format). Locked 2026-06-24 (`your-job`).
Apply verbatim every time.

Two overlays, dead simple, **no animation**:
1. **HOOK CARD** — one static white box / black text, pinned top, shown only over the spoken hook line.
2. **CAPTIONS** — line-by-line, parked low under the face, **always on** for the whole video.

Builder: [`presets/tiktok/raw/build.py`](build.py) · Corrections: [`transcript-corrections.json`](../../../transcript-corrections.json)

Engine = PIL PNG overlays + ffmpeg `overlay` (enable-timing). This ffmpeg has **no** `drawtext`/`libass`,
and PIL gives exact control over the Inter weight + stroke + box — it's the house pattern.

---

## 🔒 THE LOOK — locked

**Hook card** (top)
- **Font:** Inter **Bold** (`assets/fonts/Inter-Bold.otf`).
- **Size:** `64px`, black text `#000` on a solid **white** box `#fff`.
- **Box:** radius `22px`, sized to the **actual ink extents** (not font metrics) + padding `32px` x / `20px` y —
  it hugs the text, never balloons. Max width `940px`, centered. No animation — hard cut on/off.
- **Position:** box top at `y250` (just under the 200px top safe band).
- **When:** only over the spoken hook — auto-ends on the first sentence break, override with
  `--hook-end SECONDS`.
- **Copy:** styled, not necessarily verbatim. Lowercase-casual brand voice. Set with `--hook-text "..."`.

**Captions** (bottom)
- **Font:** Inter **Bold**.
- **Size:** `42px`. **Text:** white `#fff` with a `4px` **black stroke** (`stroke_fill`), **no box**.
- **Position:** horizontally centered, vertical center `y1500` — low, under the face, above the 300px bottom band.
- **Phrasing:** ~3–4 words per line (`MAX_WORDS=4` / `MAX_CHARS=20`), broken on clause/sentence punctuation.
- **Animation:** none. Each line is a hard cut and **holds until the next line begins** (no flicker, no gaps).
- **Always on:** captions run from the first word to the last, the whole video. The hook card just overlays
  on top during its window — it does NOT replace the captions underneath.

**Safe zones:** every key visual stays inside `y200 → y1620`. Hook card sits below 200; captions sit above 1620.

**No B-roll in this preset.** The raw take, the hook card and the captions are the look; a creator's own footage goes on a preset built for it (`broll-own` § Give a preset B-roll).

## 🔒 THE TIMING RULE — this is the lock

**Always build from the canonical transcribe-once transcript:** `projects/<job>/outputs/<job>.transcript.json`
(WhisperX large-v3 word timings remapped through `cuts.json` — the SAME timeline as the audio that ships, so
captions are on-beat with zero manual nudging). **Caption over the render that SHIPS** (the final cut). Never
re-transcribe; never time off an ad-hoc subset transcript.

## 🔧 AUTO-FIX mis-transcribed words

Every word runs through [`transcript-corrections.json`](../../../transcript-corrections.json) (`auto` map) — add your brand and product-name fixes there — before captioning (display text only; the source transcript is never touched). Grow the corrections file whenever a new
mistake shows up.

The builder **never drops a word, and asserts captions == transcript**. A sub-0.2 s one-word sliver merges
into the line it continues (a gap of 0.30 s or less); otherwise it opens the NEXT line, which starts earlier
to carry it, and it merges back when no line follows. The build compares the caption words with the
canonical transcript's words in order, as lowercase alphanumerics with the spelling fixes applied on both
sides, and on any mismatch exits non-zero and prints a unified diff. A clipped false-start tail that
surfaces as a caption is a cut defect: nudge that segment in `cuts.json` and re-splice, never hide it in the
captions. Regression: `workflows/test_caption_builders.py`.

**No line lights before its first word is spoken (2026-10-14).** A word's frame is the first whose midpoint is at or
after its start; a line's first lit frame is the first whose time is at or after its start as the overlay writes it (to
the millisecond). The first may never be later than the second: 0 frames of lead, no exceptions in this look. The
build exits non-zero naming any line that would (`check_onsets`). WHY: a word on screen before it is said reads as
wrong ("the word is already highlighted and you hasn't spoken yet", the 2026-10-13 office hours).

---

## ▶️ Per-job workflow (step 5: the hook card + the caption layer, on by default)

**Captions are a step-5 graphic (2026-09-04), not a pass.** With `--alpha` the builder emits
the ALPHA overlay that IS the step-5 output; the lane's placer lays it on the top graphics track like
any other graphic:

```bash
uv run presets/tiktok/raw/build.py projects/<job> --alpha --hook-text ""                                   # → projects/<job>/hf-graphics/captions/renders/captions-alpha.mov (captions only)
uv run presets/tiktok/raw/build.py projects/<job> --alpha --hook-only --hook-end <V1 cut> --hook-text "…" \
    --out projects/<job>/hf-graphics/gfx/renders/<hook-cell-id>-alpha.mov                                   # → the hook card as its OWN overlay
```

**Two layers, two clips (2026-09-08, `your-job`).** The plan carries the hook
card as its own cell and the captions as the `captions` cell, so the build emits them as two alpha
movs: the placer lays the hook on the graphics track and the captions on the top track, each a
trimmable clip. `--hook-end` takes the plan cell's end, which `validate-plan.py` has already pinned
ON the V1 cut. (One combined mov, the pre-2026-09-08 behaviour, is still what you get with
`--alpha --hook-text "…"` and no `--hook-only`; `clipper` uses the burn path.)

It needs no flat render (works at `RENDER=0`): duration comes from `transcript/cuts.json`, fps from
`raw/`, words from the canonical transcript. **The layout is authored at 1080×1920 and rendered at
the base's size:** `--scale` defaults to the raw's upright width over 1080 (a 4K rotated raw makes a
2160×3840 sequence, so the same look renders at 2×; every pixel figure above doubles on the frame).
Never scale the finished mov in the editor instead. The plan carries the `captions` cell
(`graphics-plan` § The captions cell); placing the layer is a lane mechanic —
[`LANES.md`](../../../LANES.md) § step 5 (Premiere: `lanes/premiere/place-graphics.py --plan --write`;
chat-only: one more overlay in the assemble). The flat burn below is the PREVIEW path (and what
`clipper` ships, because a clip has no timeline); it stream-copies the audio, so a burn never re-encodes the voice.

Preconditions: the rough cut + derived transcript exist (`outputs/<job>.mp4` + `outputs/<job>.transcript.json`).

1. **Preview** the first 30s while you dial the hook copy:
   `uv run presets/tiktok/raw/build.py projects/<job> --until 30 --hook-text "your hook"`
   → writes `/tmp/video-editor/<job>/tiktok-raw/preview.mp4` and prints the caption sheet + detected `hook_end`.
2. **Whole-video preview** — drop `--until` for a full burned look-check (still a preview: the
   deliverable is the alpha layer placed at step 5 and the lane's own render; only `clipper` ships a
   burned file, and `finalize.sh` owns `outputs/<job>.final.mp4`):
   `uv run presets/tiktok/raw/build.py projects/<job> --hook-text "your hook"`

On the burn path the rough cut at `outputs/<job>.mp4` stays the clean base the builder reads from
(don't overwrite it, or a re-run would caption an already-captioned video); on the alpha path there is
nothing to overwrite.

## Knobs (only if asked to tweak)

Captions: `CAP_SIZE` · `CAP_WEIGHT` (`Semibold`/`Regular`/…) · `CAP_STROKE` · `CAP_CENTER_Y` (height) ·
`CAP_MAX_WORDS`/`CAP_MAX_CHARS` (phrase length) · uppercase = map `.upper()` in `render_caption`.
Hook card: `--hook-text`, `--hook-end`, `HOOK_SIZE`/`HOOK_PAD_*`/`HOOK_RADIUS`/`HOOK_TOP_Y`/`HOOK_WEIGHT`.
