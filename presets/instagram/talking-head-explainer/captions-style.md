# Captions: the Talking Head Explainer's locked caption layer

**Quiet, editorial, always on, verbatim.** Small white mono caps in a see-through black box, one short line at a time,
cut on and off with the picture, from the first spoken word to the last. The builder is [`captions.py`](captions.py),
run from this folder and never copied into a job. This look replaces the retired Coolvetica word-pop look wholesale
(2026-09-21; the old look's story is in the
the engineering archive).

**The thesis.** On this format the graphics carry the motion and the emphasis. The caption has one job: to be read
with the sound off. So it never moves, never emphasises and never competes. A line that animates or highlights a word
is a second emphasis system fighting the graphic for the eye, and a gap in the captions reads to a sound-off viewer as
a bug. The look came from a reference reel you named as "the style that I wanna go for" (2026-09-20). It was then
tuned note by note over four review passes, and every value below carries the note that set it.

**What this doc does not restate.** The layouts (S split, T tight, W wide, O wide with an overlay card, F full frame),
their footage transforms and the platform bands are [`layout.md`](layout.md). Its executable twin,
[`layout.py`](layout.py), resolves every frame's caption y and every forced line break from the rules in § 2 and § 5.
What goes in the panel, and the rule that a graphic never repeats the caption, are [`graphics.md`](graphics.md). The
index and the definition of done are in [`README.md`](README.md). How the caption cell is planned is `graphics-plan`
§ The captions cell ([skill](../../../.claude/skills/graphics-plan/SKILL.md)).

---

## 1. THE LOOK (locked)

- **Type: SF Mono Bold, 44 px, tracking 3 px, ALL CAPS, punctuation kept** ("NOW, IF YOU"). The font is
  `/System/Library/Fonts/SFNSMono.ttf` at its `Bold` named instance. Each character is drawn on its own so the
  tracking is exact: at 44 px every character advances 30 px including the tracking, and a word ends on its last
  glyph (no tracking after it), so a line is `30 × n − 3 × w` px wide (n counts every character and space, w the
  words). WHY: mono caps give every line the same typeset rhythm, and they echo the mono labels in the
  graphics, so the frame reads as one system. The caps ARE the default, exactly as shipped (2026-09-24: "that's
  exactly how I want them"); the brand kit's "lowercase-casual" is the wording, never the case (a lowercase switch
  was made on that misreading and reverted the same day).
- **Colour marks the speaker and nothing else.** The creator's lines are white `(255,255,255)`. A second voice (an AI
  on speakerphone, a caller, a clip's own audio) gets its WHOLE lines in yellow `(255,214,10)`. A speaker change always
  starts a new line, so a line never mixes two voices. WHY: with the sound off, the viewer knows who is talking without
  a label, so a live AI demo reads as a conversation.
- **The box: black at 90 % (alpha 230), padded 26 px left and right and 14 px top and bottom, radius 16.** It hugs its
  own line: at 44 px it is 73 px tall, running from 38.5 px above the line's y to 34.5 px below it, and it is the text
  width + 52 px wide. It stays fixed for the line's whole life. WHY: the box keeps the line legible on any background
  (the face, a white web page, a dark chat window), and being see-through stops it sitting on the picture like a slab.
  The approved density is that 90 % as Premiere composites it, in LINEAR light: over a white page it reads gray 89
  (about 65 % effective; 80 % read gray 123, about 50 %, which is why 80 % looked lighter than its number). A compositor
  that blends straight alpha in gamma space (the chat-only ffmpeg assemble) reads the same box at gray 25, visibly
  heavier; there the layer is built with `captions.py --straight-alpha` (a box alpha of 166, the straight blend that
  matches). Over dark footage the difference is negligible.
- **The whole line cuts on and off.** There is no word pop, karaoke, box grow or fade.
- **A sponsor's brand stays white too, whatever the brief asks** (2026-10-15: "Whop should never be highlighted
  orange anywhere during the captions", overriding a brief that asked for it). A brief that wants its brand coloured in
  the captions is answered in the step-5 report ("captions stay white: his call"), never built. The builder still reads
  the `highlight` key a past job's plan may carry, so that job rebuilds as it shipped; a new plan never writes one.
- **Never emphasise a word.** No colour chip, highlight or recolour: "we don't want to do that blue highlight thing
  ever" (2026-09-21). The emphasis on a word comes from the graphic beat that lands on it.
- **Legibility comes from the dark box, never from an outline stroke or a glow.**
- **Always on, from the first word to the last, as ONE layer above everything:** every graphic, the hook, full-screens,
  montages, overlay cards and the CTA. A graphic that lands inside the caption window goes UNDER the running captions
  and never replaces them. No spoken frame is ever uncaptioned, and two lines never blink apart (§ 5); the only bare
  frames inside the cut are a pause longer than the hold and a V1 shot's silent lead-in before its first word.

Why each value is where it is:
- **52 → 44 px:** "a little bit smaller" (2026-09-21). Small type leaves the frame to the visuals.
- **Box opacity:** there was no box at first, only a blurred shadow. It went to an opaque box ("like the original" reel),
  then to 50 % ("the background for the caption text has got to be transparent"), then 70 % (2026-09-21), then
  80 % (2026-09-22), darker but still see-through, then 90 % (2026-10-15: "it looks too light"; Premiere's
  linear-light blend had 80 % reading about 50 % over a white page).
- **Yellow second voice, not sky blue** (2026-09-22): blue got lost against the blue-led graphics and the blue
  room light.
- **Client builds:** SF Mono is Apple's system font, present on every Mac, so a macOS client draws the locked look. Off
  macOS the builder draws the bundled stand-in, IBM Plex Mono Bold (`assets/fonts/`, OFL): its cap height is SF Mono
  Bold's and it is drawn 62/60 larger so every character advances SF Mono's 30 px, and its box is sized from SF Mono's
  metrics, so every line and every box is the locked size (measured 2026-09-27: widths 0.00 % off, box identical).
  The glyph shapes differ slightly; the named system monos are the last resort (§ 6).

## 2. WHERE each line sits

The rule, in your own words: "by default it should be in the middle, in between the line that separates the top
half from the bottom half … when it's me talking, it should rest just below the collar of my shirt, so it's on the
black on my shirt … as close to the center as possible while still placing them correctly" (2026-09-21). The
thinking: in a 9:16 reel the eye sits near the frame centre, so the caption goes as close to centre as the layout
allows, on a flat area where it covers nothing that matters. It never goes on the face or on a graphic's content.

Each height below is the line's centre y in the 1080×1920 frame:

- **S (split): y960, centred on the seam, and that includes the hook.** The eye already rests between the graphic and
  the face, and the box covers neither. If a visual crowds the caption, lift or shrink the visual. The caption never
  leaves the seam: "move the hook text captions up to center position and then maybe slightly move the hook visual up
  too so they don't collide" (2026-09-22).
- **W (wide) and O (wide with an overlay card above the head): the box top sits 40 px under the point where the collar
  meets the skin, so the line is at collar + 78.5.** The shirt just under the chin is the flat area closest to centre
  that touches neither the chin nor the mouth. The 40 px was set on still tests (2026-09-22): 20 px was too
  tight, 55 px too low, and 40 px was "perfect".
  - **Measuring the collar:** once the layout map exists, `uv run workflows/face-frame.py projects/<job> --collar --plan
    projects/<job>` reads it on 8 stills spread over the layout's W, O and T spans (the takes whose caption actually sits
    on the collar; an S-only take, such as a CTA delivered on split, never pulls it down), and writes the upper third of
    the agreeing readings (by y) into `face-frame.json` `collar`. A W, O or T layout row that carries its own
    `caption_y` (or `ui_bottom`) is left out too, because its line sits there and not on the collar (2026-09-24). Run
    without `--plan` (only before the layout map exists), the tool prints a ⚠ and reads the 12 face stills over every
    kept span, S-only takes included. WHY the upper third, not the single lowest (which moves lower as stills are added
    and put every W/O line 20 px low) or the median (a turned head reads 12–28 px high): on the benchmark it wrote
    y1236 against the approved y1239.5 (the measurements: `face-frame.py`'s `COLLAR_QUANTILE`). Only when the tool
    answers UNMEASURED is the collar read by eye off its
    annotated sheet. Then it is recorded in the captions cell `y.wide` (the line: collar + 78.5), with a `measured` note
    giving the still times and the reading.
  - **One precedence for the heights:** the measured `collar` wins. The captions cell's `y.wide` / `y.tight` (a by-eye
    read, a tight-still correction, or an approved nudge from the still test, § 3) win over it only when they carry
    their `measured` note and a `measured_at` (ISO date-time) not older than the collar's `collar_read.at`; with no
    measured collar they stand as written. So a stale override never silently beats a fresh measurement, and an
    approved change is recorded with its date. `layout.py` resolves it; nothing else re-derives it.
  - **The collar is wherever the garment meets the skin:** a shirt collar, a crew neck, a T-shirt or a hoodie neckline.
    A light shirt changes nothing: the box carries the legibility, and the rule is about position, not colour.
  - **No neckline to read** (bare shoulders, a turtleneck or a zip up to the jaw, a beard over it), **or one that would
    put the box far from where the rule means it** (a deep V or an open shirt that drops it onto the chest): anchor on the
    chin. `uv run workflows/chin-line.py <raw> --edl projects/<job>/transcript/cuts.json --from <a> --to <b>` over the
    wide spans gives the lowest chin in raw pixels. Map it into the frame through the W transform (on an untouched wide,
    raw y × 1920 / raw height). The box top goes about a third of a face width under it. That is where collar + 40 landed
    on the approved short: 163 px under the lowest chin, on a face box about 500 px wide. Record the line in `y.wide` with
    its `measured` note, and approve it on the still test (§ 3) before the layer is built. This anchor was derived from
    the benchmark, not set by you.
  - **A held prop over the collar spot** (the phone on speaker during a live call, a product held at chest height): read
    the collar on stills where the prop is down, never on a frame where it hides the neckline. Then look at program
    frames of that stretch. The box may overlap the hand, the mic arm or the prop's edge: on the approved short the
    phone was held just above the line and the box cleared it by a few pixels. If the box would hide something the
    viewer has to read, show the still to the creator before building (§ 3).
- **T (tight punch-in): derived, never picked.** Map the wide collar through the tight transform in
  [`layout.md`](layout.md): `collar_T = T.y + T.scale × (collar_W − 960)`. Here `T.y` is where the tight transform
  lands the source's centre line, and `T.scale` is its scale (per shoot: 400 / the wide face-box height, layout.md § 2). The formula is for an untouched wide;
  [`layout.py`](layout.py) also carries a reframed one. Then line = collar_T + 78.5. Verify it on a still. On the
  approved short the tight line was set by eye and sat on the neck, above the collar. That was a defect, not a value to
  copy.
  - **`y.tight` is a measured correction, never a pick.** `layout.py` prefers the captions cell's `y.tight` over the
    derivation (under the precedence above), so it is written only when a tight still shows the derived line off the
    fabric just under the collar.
    That happens when the creator's posture on the tight takes differs from the wide ones (leaning in or turning). Then
    the collar is measured on the tight stills themselves, because the wide and each punch-in are separate
    measurements. `y.tight` = that collar + 78.5, with its `measured` note, approved on the still test. A derived line
    that leaves the safe box is never a case for `y.tight`: the punch-in is too tight, and the layout gets fixed
    (below).
- **F (full-frame graphic) with UI at its bottom** (a chat's input bar, an app's controls): the box top sits at least
  20 px under the UI's bottom element, on the capture's own fill, never on the controls. This is the F layout entry's
  `caption_y`: line = ui_bottom + 58.5. The capture is framed so that its content ends above that box
  ([`captures.md`](captures.md)).
- **F with no bottom UI** (a montage, a typographic scene): as near centre as the content allows, and on the seam by
  default whenever the seam is clear.
- **Every layout:** the line is centred horizontally, with at most 940 px of type (31 characters), which keeps every
  glyph out of the 60 px platform side bands. The box stays inside the platform-safe box y200–1620
  ([`layout.md`](layout.md)). If a framing would push the collar line past it, the framing is wrong (the punch-in is too
  tight). Fix that in the layout, and never move the caption onto the face instead.

**The y follows the picture frame by frame.** Every frame takes the y of its own layout, so the caption moves on the
same frame the footage reframes. WHY: when the y was chosen once per line, a line stayed in the old band for up to
13 frames after a reframe. `layout.py` resolves the y for each frame, and `captions.py` never re-derives it.

## 3. How a height is set or changed

- **Measure on stills.** Never judge a height from a thumbnail or from memory.
- **Render the still test first:** `captions.py --stills t1,t2,…` at about three representative shots of each layout it
  touches, plus one full frame, with the current height beside the proposed one. Iterate on the still test, not on the
  timeline.
- **Get a yes, then rebuild the layer.** "render a quick test first so I can approve before you change all of them"
  (2026-09-22).
- **Once the height is right, only nudge it** ("I don't want you to change too much … Just make a few small
  adjustments", 2026-09-21), and state every offset from the physical reference: "slightly" and the physical
  reference are the README's [§ Working with the creator](README.md#working-with-the-creator).

## 4. WHAT is written

- **The canonical `outputs/<job>.transcript.json`, word for word, remapped through the EDL onto the timeline.** That file
  runs on the same clock as the shipped audio, so nothing needs nudging. A word is never dropped, rewritten, re-timed or
  hand-typed. WHY: a dropped word is invisible in visual review. Two real words shipped through five review rounds
  because nothing yet compared the captions against the script.
- **A spoken unit stays whole on one line.** Examples: "et cetera", a time ("11:30"), a number with its unit, or a brand
  name the ASR split into two tokens. The captions cell's `join` names these units. A phrase is joined on a non-breaking
  space, and a brand split in two is fused back into its one spelling. Break the line before the unit, never inside it.
  **The CTA's ask gets the same care:** put its fixed phrase ("down below", "link below") and any multi-word keyword
  in `join`, so the viewer reads what to do and the word to type as whole units. Left alone, the builder split one ask
  as "COMMENT AGENT DOWN / BELOW AND I'LL" on a trial run.
- **Names are fixed UPSTREAM, never in the builder.** A recurring mishear goes in
  [`transcript-corrections.json`](../../../transcript-corrections.json). A call that depends on context goes in the job's
  `corrections.local.json`. Then `.claude/skills/rough-cut/scripts/reapply-corrections.sh projects/<job>` re-derives the
  transcript. On a name, the creator's own spelling (from your brief or your prompts) beats the ASR's. A flagged common
  word that is, in context, your product's name is fixed in the job's local corrections. The builder never re-spells.
  WHY: the captions should read as your own words, and a misspelled teammate or brand looks careless.
- **Second-voice spans come from `transcript/voices.json`.** They are on the RAW source clock (per clip), so they
  survive every re-cut. Each span covers the WHOLE reply the creator kept, not just its first words. When you kept a
  longer reply in your hand cut and the span wasn't widened, the tail of the reply went white and read as if you were
  saying it.
- **A second voice the ASR dropped is repaired at step 2, never typed into the captions.** Phone audio that sits
  8–10 dB under the creator often goes missing. `workflows/cut-audit.py --coverage` finds the drop, and
  `scripts/realign-spans.py` repairs it ([`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md) § Transcribe).

## 5. WHEN: line building and timing

**Building the lines** (the values are in § Values):
- **A line flushes at 3 words or 16 characters, and always on `. ? !`.** The 3 words / 16 characters is a trigger, not
  a cap. WHY: fast 2–3-word beats match a hard-cut edit, and a sentence end reads as closure.
- **No widows.** If the next word ends a sentence, has 6 characters or fewer, is in the same voice and starts under
  0.4 s after, it joins the line before it instead of standing alone. The exception: the 940 px guard refuses the join.
  Staying inside the safe band beats avoiding a widow. An unguarded join once produced a 970 px line.
- **A new line starts at every speaker change and every picture change:** a V1 cut, a layout edge, a graphic's in or
  out, and every `shot_cuts` entry in a cell (a cut inside a multi-shot scene). WHY: when the picture and the phrase
  change together, each shot reads as one thought. A line that crosses a change either jumps band while on screen, or
  strands a word that vanishes as it is spoken. The rule came from a montage cut: break the caption at the
  half-sentence where the picture cuts INTO the montage, and open the new shot on the next word (2026-09-22).
- **Except a montage's own shots.** Inside a montage the shots cut on a steady beat of about 1 s, mid-word by design
  ([`captures.md`](captures.md) § 7), and the band stays S throughout, so a line crossing them jumps nowhere and no
  word vanishes. The approved short ran its lines straight across those cuts; breaking on them stranded spoken frames
  with no caption and left 3-frame lines. Only the montage's entrance and exit break. `layout.py` applies it (a cell's
  `caption_breaks: true` or `false` overrides the default for its family).
- **The line after a break starts ON the break frame.** A first word within one frame of a V1 cut, on either side,
  opens the incoming shot's line. After a graphic or layout cut (which lands 0–2 frames before its word,
  [`layout.md`](layout.md) § 4) the reach is wider: a first word starting up to 0.2 s after it (the larger of that
  lead plus a frame, and the handover) opens its line ON the cut. WHY: a line that started a frame or two late left the
  incoming shot's first frames bare (a montage's, then a graphic's at each mid-sentence cut).
- **A one-word sliver under 0.20 s is re-homed, never deleted.** It joins the previous line, unless that line closed a
  sentence or the width guard refuses; otherwise it joins the next line. It never moves across a break or a speaker
  change. WHY: deleting slivers as "stutters" deleted real words.

**Timing:**
- A line appears on its first word's start.
- It holds until the next line if that line starts within 1.0 s. Otherwise it holds 0.45 s past its own last word. The
  result is continuous reading with no flicker between lines.
- It never holds past a break.
- **A line cut short by a break while its last word is still being spoken hands over at the break.** The next line
  starts on the break frame if it would otherwise start within 0.2 s, so no spoken frame goes uncaptioned.
- Line ends snap DOWN to the frame grid, so an old line never lands on the incoming shot's first frame.
- **A line held to the next ends exactly on that line's first frame, so two lines never blink apart.** The approved
  short's builder snapped the held end down but rounded the next start, so its layer went blank for a frame or more
  at 80 joins inside continuous speech: 104 frames in all, 68 of them single frames. Nobody caught it at playback
  speed. `captions.py` closes it by construction, and `workflows/test_talking_head_captions.py` holds it.

**The corollary for the plan (5a):** put a mid-sentence graphic cut on the start of a clause. That clause's first word
then opens the new line on the cut frame. A cut in the middle of a phrase splits the caption mid-thought.

**The outcome, not a target:** the approved two-minute short ran about 150 lines, mostly 3 words each, and a line
stayed on screen 0.75 s on average (range 0.24–1.84 s). A first pass far from that shape, with many one-word lines or
2-second holds, points to a defect in the builder or its inputs.

## 6. The builder

```bash
uv run presets/instagram/talking-head-explainer/captions.py projects/<job> [--variant ad] [--ver b] [--stills t1,t2] [--check <mov>]
```

**Inputs** (all in the job folder; the exact field shapes are in `captions.py`'s header):
- `graphics-plan.json`: its `fps`, the `layout` map (an F entry carries its `caption_y`), the graphic cells (each
  cell's in and out points and its `shot_cuts`), and the `captions` cell with `join`, `y` (the measured heights and
  their `measured` notes) and `variants`.
- the EDL, `transcript/cuts.json` (a variant uses its own EDL).
- the canonical `outputs/<job>.transcript.json` (a variant uses `outputs/<job>.<variant>.transcript.json`).
- `transcript/voices.json`.
- `face-frame.json`: the measured `collar` (§ 2) and the layout transforms (`modes`) that `layout.py` maps it through.

**Outputs:**
- `hf-graphics/captions/renders/captions[-<variant>]-alpha[-<ver>].mov`: ProRes 4444 `yuva444p10le` at the plan fps,
  with straight alpha and one frame per timeline frame.
- `hf-graphics/captions/caption-sheet[.<variant>].json`: every line with its start, end, voice, text and y.

**Rules it keeps:**
- **It never overwrites a placed render.** A rebuild goes out under a new `--ver`, and the lane swaps it in. The reason
  is in `graphics-build` § Render gotchas ([skill](../../../.claude/skills/graphics-build/SKILL.md)): a file overwritten
  in place leaves Premiere's frame index half-stale.
- **Font resolution:** SF Mono Bold first. Next, the bundled stand-in (IBM Plex Mono Bold at 62/60, SF Mono's box;
  § 1 Client builds), with a printed note. Last, a named system mono
  (Menlo, Consolas or DejaVu Sans Mono) with a loud warning, which is also written into the sheet so a fallback can
  never pass silently. The 940 px guard and the box are measured with the font actually resolved.
- **After a hand re-cut, the layer is REBUILT from the new EDL as one clip, never rippled.** A rippled caption layer is
  chopped into pieces that can still show words that were cut.
- **A variant** (`--variant ad`, the second deliverable with its own CTA) builds from its own transcript and EDL, and
  follows the layout that actually SHIPS in that variant. Its layer must be frame-identical to the organic layer up to
  the frame where the variant diverges (framemd5), and that is proven before export. A caption re-keyed to a
  re-recorded word waits until that audio is laid, so the picture and the sound never disagree.

**Placement** is a step-5 overlay on the top graphics track and spans the whole cut. HOW per lane (the track, the fit
to a larger sequence): [`LANES.md`](../../../LANES.md) § step 5.

## 7. The gate

The gate runs after every build and exits 1 on any failure. `--check <mov>` re-runs it on any render. It checks six
things:
- **captions == transcript,** word for word and in order. Joins are free: a joined or fused unit is compared as its
  tokens.
- **0 lines span a break.**
- **0 lines lit before their first word is spoken (2026-10-14).** A word's frame is the first whose midpoint is at or
  after its start, the rule a line is lit by; a line's first lit frame may not be earlier, 0 frames of lead. The one
  exception is § 5's: a line opened ON a break or a V1 cut, within the reach it snaps by (and the frame the word's own
  rounding takes). WHY: a word on screen before it is said reads as wrong ("the word is already highlighted and he
  hasn't spoken yet", the 2026-10-13 office hours); this look highlights no word, so the line's first frame is the one
  place it can happen.
- **Every frame's ink centre is within 45 px of the y that frame's layout requires.** This is read per frame from the
  rendered alpha, never once per line.
- **Every line is 940 px or less.**
- **No frame inside a spoken word is uncaptioned.** A blink between two held lines falls between words, where this
  check does not look. The builder closes that by construction (§ 5), and its unit test holds it.

WHY: caption defects slipped through four review rounds while the only proof sampled once per line and nothing compared
the captions to the script.

Before calling the captions done, also look at a few program frames per layout, near full size (the graphic over the
graded footage, under the caption), including the frames either side of a cut. Defects cluster at cuts, and a caption
sitting on card text only exists in the composite.

## 8. Graphics leave the caption room

- **On S, no authored ink at all in the gate band y908–960.** That band is the box's upper half (the box top is at
  y921.5) plus 13.5 px of air above it. `workflows/graphics-qa-short.py` reads the band from `captions.py` and FAILs on
  ink there. A real screen's page may run on under the box to the seam (its cell's `under_caption`,
  [`captures.md`](captures.md) § 4): the 90 % box is what lets the line read over it (2026-10-15).
- **The band is the floor, not the target. Leave visible air above the box** for an authored graphic and for whatever
  on a capture must be read (a capture's page itself may run on under the box, above). On the approved short, the gap
  between a graphic's lowest element and the box was about 75–120 px. The number, its WHY and the card clearance belong
  to [`layout.md`](layout.md) § 8 and § 9.
- **No graphic carries a text label that competes with the caption;** a concept lockup's name, with the object that
  performs it, is the one titled exception. The rule belongs to [`graphics.md`](graphics.md) § 1 and § 5.

## 9. Rejected: never again

Every other rejected look is the WHY of its rule above (§ 1 to § 6). These have no other home:
- **The retired look:** Coolvetica in natural case in a solid box, word-pop karaoke, always at y960, rendered as a
  HyperFrames comp.
- **A full-frame caption low on the chest.** Each note moved it up toward the collar: y1490, then 1470, then 1420,
  then the collar rule.
- **An outline stroke, or a glow at 0.9,** as the legibility layer.
- **A builder copied from another short:** it still carries the sliver filter that deleted real words, one reason the
  builder runs from this preset and is never copied.
- **A re-rendered caption layer laid at the wrong scale** (Scale 100 on a 4K sequence). This is a lane trap: the
  placer computes the scale, and a hand swap is checked on a program frame.

## Values

Mirrored by [`captions.py`](captions.py). The parity test in `workflows/test_talking_head_captions.py` fails if this
block and the code drift apart. Pixel values are in the 1080×1920 frame, times are in seconds, and the box offsets are
measured from the line's y.

```values
SIZE 44
TRACK 3
WHITE 255,255,255
SECOND 255,214,10
BOX_ALPHA 230
PAD_X 26
PAD_Y 14
RADIUS 16
BOX_ABOVE 38.5
BOX_BELOW 34.5
MAX_WORDS 3
MAX_CHARS 16
MAX_W 940
WIDOW_CHARS 6
WIDOW_GAP_S 0.4
SLIVER_S 0.20
GAP_CAP_S 1.0
HOLD_PAD_S 0.45
HANDOVER_S 0.2
Y_SPLIT 960
COLLAR_BOX_GAP 40
UI_BOX_GAP 20
BAND_TOL 45
GATE_BAND 908-960
```

`COLLAR_BOX_GAP` gives line = collar + 78.5 (40 + `BOX_ABOVE`). `UI_BOX_GAP` gives line = ui_bottom + 58.5.
