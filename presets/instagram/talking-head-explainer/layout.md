# Layout: the frame and its rotation

This doc owns the frame of a talking-head explainer: which of five layouts is on screen at every frame, where it
changes, and where everything sits inside it. It is read at 5a, where [`graphics-plan`](../../../.claude/skills/graphics-plan/SKILL.md)
writes the plan's `layout` map BEFORE choosing a single graphic, because the layout is chosen from what each sentence
does and the graphic follows from the layout. [`layout.py`](layout.py) is its executable twin: the checks in § 13, the
mode at every frame, the caption height at every frame and the forced caption breaks. `validate-plan.py`,
[`captions.py`](captions.py) and the lane's layout keys ([`lanes/premiere/layout-keys.py`](../../../lanes/premiere/layout-keys.py)
on Premiere) all import it, so the framing has one implementation. What goes inside the panel is
[`graphics.md`](graphics.md), the real screens are [`captures.md`](captures.md), the caption layer is
[`captions-style.md`](captions-style.md).

Provenance: `(date)` is the creator's own instruction, correction or hand edit. `(approved, 2026-09-23)` is in
the cut the creator approved ("the organic one is done") without a note on it. The creator watched that cut through 7
review rounds and never touched a framing key, which makes the shipped layout the evidence. `(inferred)` marks a rule generalised past anything the
benchmark showed, so a planner cold on a new shape still has an answer: apply it, and say in the plan summary that it
was applied, so you can overrule it. Every benchmark number and example illustrates a principle; the per-shoot
measurements are in § 16 so they are never mistaken for rules.

## 1. Why

- **One locked-off camera and one take give no second angle. A layout change resets the eye the way a new angle would,
  at no cost.** No second camera, no b-roll shoot: the same take framed five ways is five angles.
- **The reference reel you named cut about every 1.5 s** (2026-09-20: "notice how the video is put together.
  that's kinda the style"). The first plan held one framing and stacked overlays on it, 23 cuts in 122 s, and it read
  as a long-form edit squeezed into 9:16. The pace does NOT come from chopping sentences: the cut stays line by line
  ([`story-and-cut.md`](story-and-cut.md) § 5.4), because every audio joint is a defect risk. It comes from the layout
  rotation, the graphic turnover, and an event inside the panel about every second.
- **Split is home, because it shows the thing and the person at once.** The proof (the app, the page, the scene) is on
  screen at a readable size while you name it, and you never leaves the frame.
- **The face stays on screen about 90 % of the time, because the creator is the brand.** Only a full-screen hides you,
  and full-screens are rationed (§ 2, F).
- **Hard cuts, never ramps: a ramp reads as a camera operator, a hard switch reads as an edit.** Every layout change goes
  from one frame to the next. Motion lives inside the shot (the panel's own events), never in the framing.

The consequence that runs through the whole doc: **the layout is chosen from what the LINE does, never from what is
convenient to build** (§ 3). Graphics illustrate nouns; the face carries persuasion. A bare face then always means
something (a reset, or "look at me, this matters") and never reads as a hole in the graphics.

## 2. The five layouts

| Code | On screen | What it is for | Typical length | Outcome share | Footage transform |
|---|---|---|---|---|---|
| **S** split | an opaque panel y0-960 with a clean edge and no divider; the face below it | a line that names or shows a thing | a graphic 1.2-12 s; the block runs as long as the nouns keep coming | about 60 % | W's scale, slid down until the median hair top sits on y1060, the neck on x540 (**S** below) |
| **T** tight | the face punched in, no graphic | a promise, an opinion, conviction, emphasis | 1.5-4.5 s | about 8 % | a punch-in to a face box about 400 px tall, centred on y866, the neck on x540 (**T** below) |
| **W** wide | the untouched shot | a signpost, a connective, a "guys" address with no noun | a breather of 0.6-1.7 s, never more than about 2 s bare | about 6 % bare | scale 1.00: a 9:16 raw untouched, a landscape raw its one fixed 9:16 crop with the neck on x540 (below) |
| **F** full-screen | an opaque full-frame graphic | the screen IS the story and needs full height | one sentence, 5-7 s | about 10 % | W, untouched, underneath |
| **O** card over W | a compact card above the head, the wide shot around it | something real happening to you on camera | the whole live beat | about 17 % | W; the card is placed against it |

**The transforms are measured, never eyeballed.** They are expressed in the 1080x1920 authoring frame and are
lane-neutral: face-frame.json `modes` carries them (the contract below), `layout.py` and the lane read them, and each
lane converts them to its own units (Premiere Motion Position, Resolve zoom and position, a transform on chat-only).
Proof after laying: [`face-frame.py`](../../../workflows/face-frame.py) `--verify` on the split spans, and the lane's layout
keys `--verify`.

**The footage half is a layer, not a cut.** S, T and W are hold keys on the footage track, driven by the layout map.
The creator's edit points are never razored: you re-cuts by hand, and a razor would cost you your trim points. A mode
change inside a clip is a hold from one frame to the next, never interpolated. The keys never overwrite a Motion edit you
made himself (the house lock: live state that disagrees with the plan is your hand edit, reported and left alone).

**S, split.** The footage keeps W's scale and slides down; the panel covers the top half. WHY W's scale: the speaker stays at a
natural talking-head size, the mic and hands stay in shot, and no zoom softens the face. **WHY the hair top at y1060,
100 px under the seam, and not the old 50 px:** the caption box straddles the seam (y921.5-994.5 at the locked caption
size), so the head needs clearance under the BOX, not under the seam. 100 px leaves about 65 px of air under the box
bottom. The old 50 px lock left about 15 px, and the caption sat on your hair (approved, 2026-09-23: the anchor that
shipped). The fallback (a hood, a hat, a hair read that fails) puts the face-box centre on y1385, the same framing
measured from the other end.
- **The hair gap is the rule that holds; the chin follows** (2026-10-14, twice). On a big face (a close camera,
  a head taller than the 560 px between y1060 and y1620, hair top to chin) the chin then passes y1620, the top of the platform's bottom
  band. That is accepted: you moved your face DOWN twice when the tool had raised it to keep the chin up ("my face is a
  little too high up... there should be a tiny bit of space between my hair and the top", 45 px in all), and shipped
  the chin at about y1657. Nothing raises the face for the chin; the tool prints the chin's line as a note. The SIZE you
  approved stays: on a landscape raw S still scales down in 0.05 steps, while the footage covers the bottom half edge
  to edge, until the face spans at most 600 px from hair top to chin (`CHIN_MAX_Y` − `HAIR_GAP_MIN_Y`, the old
  y1020-1620 window), and only then is the hair placed on y1060 (on your shoot: 0.85x, the chin about 40 px past
  y1620). A 9:16 raw cannot scale below its fit.
- **Centred on the shoulders and neck, never on a leaning head** (2026-10-14: "keep my shoulder and my neck
  centered. We more so want my shoulder and my neck centered"). A creator who leans or tilts your head puts the face
  off your body's centre line; the frame is centred on the body, so the shoulders sit level in the panel and the face
  may sit a little off centre. `face-frame.py --modes` measures the shoulder midpoint (MediaPipe pose) on the same frames
  as the face and puts it on x540 in W, S and T, falling back to the old centring (W as measured, T on the face) with a
  printed note when the shoulders are seen on under half the stills. T keeps the face's scale and height and takes the
  neck's x: T is still a head-and-shoulders shot (at 1.15x your shoulders sit about y1440), and the clip you singled out
  ("especially in the second clip") opens on T. The slide stops where the footage would bare a side: a 9:16 raw fills
  the frame at W's scale, so its W and S stay as shot and only T slides. On your shoot the shoulders sat 40-90 px left
  of the face's centring and every framing moved 40 px right (60 on the second clip).

**T, tight.** A punch-in about the face, no graphic. WHY: the face carries persuasion, and a punch-in is a picture change
for free. It is the bridge whenever the face has to carry a line longer than a breather: a bare W over about 2 s reads
as dead air, a T reads as "look at me, this matters". The face sits a little above frame centre so the chest stays free
for the caption line.
- **T is defined by the face, not by a ratio.** The target is a face box about 400 px tall on the frame: the benchmark's
  face box was 284 px on the wide shot (its calibration, § 16), and its 1.40x punch-in (`T_SCALE`) made it 398. On
  another camera distance the scale is 400 / the wide face-box height, so every shoot gets the same tight shot.
- **Two clamps.** Never tighter than keeps the derived T caption box inside the platform-safe box (the collar mapped
  through T, § 10: line at most y1585.5); never looser than 1.15x, below which a punch-in reads as a wobble, not a new
  angle. (inferred)
- **Resolution.** A 4K 9:16 source keeps a 4K sequence, so 1.40x stays sharper than the 1080 deliverable. Any mode whose
  effective magnification of the source's own pixels passes 1.0 upscales: allowed, flagged once in RUN.md.
- Never T under a card (§ 9).

**W, wide.** The untouched shot, for a signpost, a connective or a "guys" address with no noun of its own ("Now, here's
the thing.", "So,", "Now, if you haven't heard of this yet,"). WHY: the connective is where the eye rests before the
next reveal, and that rest makes the reveal land harder. It stays a breather, 0.6-1.7 s (the approved cut's breathers
averaged 1.2 s). A longer bare W becomes T.

**F, full-screen.** An opaque full-frame graphic; the footage stays W underneath, untouched, so the cut back out lands on
a clean frame. Only when the screen IS the story and needs full height: the concept shown working, or the escalation
payoff (several speakers in one thread). WHY full height: a tall multi-speaker thread cannot be read in the split's
645 px zone. WHY rationed: rarity is what makes the payoff land, and every F second is a second without the face. One
sentence (5-7 s), at most 2 per 120 s and about 12 % of runtime. The benchmark ran two: the concept line (entering on
the product's name after a signpost lead-in) and the escalation (entering on the V1 cut at the escalation line).

**O, card over W.** For something real happening to you on camera: the phone rings in your hand, an AI talks on speaker,
the object held up to the lens. WHY: your reaction and the physical prop ARE the evidence. A split would crop them, and a cutaway
would hide the one moment that proves it is real. Jump cuts underneath are fine; the card holds across them. The framing
never changes under a card, and never T under a card (§ 9).
- **The O card, generically:** one compact card above the crown that shows the DEVICE's own state, never a sentence:
  who or what (an avatar or the product's mark, and a name as the product shows it), a live status (incoming, on call
  with a running timer, a notification, recording), and at most one live element synced to the proof (a waveform built
  from the other voice's real envelope, a counter). Timeline rate, never stepped: it follows live audio.
- **The call card (`components.call_card`, [`graphics.md`](graphics.md) § 3.4) is the one instance built so far.** A
  notification, a timer or a status card for another live moment is built to the same rules, never a call card faked
  onto a moment that is not a call.
- **When the prop itself is the whole proof** (the finished object held to the lens, and any card would only label
  it), the O span may run with no card: name it in `layout_deviations` as `L-OVERLAY` with that reason (§ 12).
- **Its edges** (approved, 2026-09-23):
  - The reaction word stays on the bare wide face ("Hold on."), and the card drops on the clause that names the event
    ("that's him calling me right now"): the O span starts there.
  - A ring starts as the reaction word ends, about 6 frames ahead of the card ([`sfx.md`](sfx.md) law 6); how the card
    plays (accept, already live) is [`graphics.md`](graphics.md) § 3.4.
  - The card's exit ends on the switch frame out of O; it never hangs into the next layout.

### face-frame.json: the transforms on disk

`uv run workflows/face-frame.py projects/<job>` measures the raw inside the EDL's kept spans (a killed take never moves
the median): the face box (`face.cx`, `cy`, `w`, `h`, source px; on each still the largest box within 0.10 of its best
score, as chin-line.py picks, and a still whose box sits apart from every other is dropped and named, so a mic or a
background face never stands in for yours) and the median hair top (`hair_top`, frame px). Its
`--modes` form writes the fields below from that measurement, and its `--crown A B` form reads the tallest crown over a
span. Where a job has only the plain measurement, the fields are written by hand with these formulas, and nothing
downstream can tell the difference. All numbers are on the 1080x1920 frame the wide shot shows: `f` is the face-box
centre and `h` its height there, `c` W's centre in px (the frame centre (540, 960) on a 9:16 raw), and a mode's `centre`
is where the source's centre lands, in frame fractions.

- `modes.W` = `{"scale": 1.0, "centre": [0.5, 0.5]}` on a 9:16 raw; a landscape raw's fixed crop is below.
- `modes.S`: scale `s` = the largest of 1.0, 0.95, 0.90… at which s × (chin − hair_top) ≤ 600 on a landscape raw (the
  face-box top stands in for the hair in the fallback), stopping where the footage would no longer cover the bottom
  half; 1.0 on a 9:16 raw. Centre y = (1060 − s × (hair_top − 960)) / 1920, or (1385 − s × (f.y − 960)) / 1920 in the
  fallback; centre x = (540 − s × (n − c.x)) / 1080 (f.x − s × (f.x − c.x) when the shoulders are unseen). A chin past
  y1620 is printed as a note and changes nothing (§ 2: the hair gap holds).
- **Once you have reviewed the framing, `modes` are yours.** A later `--modes` run on that job (after a re-cut, say) is
  written with `--out` to a scratch file and compared, never over the reviewed ones unasked: the 0.05 size step sits
  on a threshold a re-sampled median can cross (your shoot measured 0.85 on its first stills and 0.90 after three
  re-cuts moved the samples), and you approved the size you saw.
- `modes.T`: scale `k` = 400 / h, at least 1.15 and at most (1507 − 866) / (collar − f.y) (the caption clamp: the
  derived T line stays on or above y1585.5); centre x = (540 − k × (n − c.x)) / 1080, n the median shoulder midpoint's
  x on the wide shot (f.x when the shoulders are unseen), kept where the footage still covers the frame; centre y =
  (866 − k × (f.y − 960)) / 1920.
- `collar`: the y where the collar meets the skin on the wide shot, the upper third of the readings on 8 stills over
  the layout's W, O and T spans (a row with its own `caption_y` left out), the spans whose caption sits at the collar:
  read with `--collar --plan projects/<job>` once the layout map exists ([`captions-style.md`](captions-style.md) § 2
  owns the reading and the height precedence). A `--modes` run caps T with a collar an earlier `--collar` run stored, and a
  `--collar` run after `--modes` re-derives the stored modes with its collar: either order writes one joint run's T.
- `crowns`: `[{start, end, y, edl_sig}]`, the tallest crown (the smallest hair-top y) over each card span, read on its
  own stills, the tallest pose included (§ 9). `edl_sig` fingerprints the EDL it was read through: after a re-cut a
  crown stamped with another cut is ignored by `layout.py` and named for a re-read.
- `span_modes`: `[{start, end, modes, edl_sig}]`, the W/S/T transforms fitted to ONE timeline span alone
  (`face-frame.py projects/<job> --span A B --modes`, repeatable). They never replace `modes`; the layout rows over that
  span carry the fitted transform as their own `frame` (§ 12). A job whose takes change posture needs it: one median S
  put a standing creator's face under the opaque panel for the whole hook (the Windows test job, 2026-09-27), and a run
  whose face drifts past 150 px and splits into two framings names the EDL spans of the smaller one to fit this way.

A bare `face-frame.py projects/<job>` re-measures the face and keeps every field above.

On the benchmark's measurement those formulas give S centre y 0.726 and T centre (0.501, 0.466). The values that shipped
(0.7271 and (0.4896, 0.4662), § 16) came from an earlier read of the same face, within 13 px of them.

### A 16:9 raw finished vertical

A landscape recording (a desk setup, a screen-capture rig's camera) can still be a talking-head explainer. The frame
is the same; only W changes. (Premiere lane, 2026-09-17; the S and T derivations are inferred.)

- **The sequence is 1080x1920 at the source's own rate,** never the landscape size.
- **W is the source fitted by HEIGHT** (scale 1920 / source height: a 2160-tall source is 0.889) **with one constant
  horizontal offset that puts the shoulders' median midpoint on x540 (the face median where no shoulders are seen), on
  every clip.** Never per-clip centring (2026-09-17: the framing stays constant across cuts). Where the shoot
  has several sections, one value is chosen between their face-frame medians. In `modes.W` that is scale 1.0 (1.0 =
  this crop) and centre x = (540 + (source width / 2 − n) × fit) / 1080, n the shoulders' median midpoint in source px
  (the face cx where no shoulders are seen).
- **S and T are that W plus their own transform,** by the same formulas, measured on the crop's frame (face-frame.py
  measures a landscape raw on its face-centred crop).
- **The effective magnification of the source's own pixels** is the mode's scale × 1920 / source height. A 2160-tall
  source: W 0.89, T 1.24 (an upscale). A 1080-tall landscape source is upscaled 1.78x already at W and about 2.5x in T.
  Anything over 1.0 is flagged once in RUN.md, and a 1080-tall landscape source is flagged at intake.
- **The HOW is the lane's** ([`LANES.md`](../../../LANES.md) § step 5): the sequence and preview size, W's Scale and
  one Position per clip, then S and T from `modes`.

### Screen-recording footage on V1

A walkthrough the creator recorded as footage (not a capture the editor takes) stays bare: no graphic, no grade, unasked
(the house lock, [`presets/youtube/default/README.md`](../../youtube/default/README.md) § Screen-recording footage stays
bare). On the map it is a **W row carrying its own `caption_y`** (the lowest flat area of the recording clear of its
content, inside the safe box, read on its frames) and a `why` naming it as screen-recording footage. The switch into it
is a hard cut. L-BAREW and L-FACE count it as a bare face, so their WARNs over it are answered in the plan summary by
naming the span. (inferred)

## 3. Picking the layout, sentence by sentence (first match wins)

Read the finished script sentence by sentence and give each sentence (or each clause, where one sentence carries two
jobs) its layout. The rules are phrased by the sentence's JOB, never by its wording or by what came before it; a quoted
line is one way of saying that job. They run most specific first, so the first one that matches is the answer.

1. **The hook → S from frame 0.** WHY: the first second has to say what the video is AND show it is real; the face proves
   a person, the panel proves the thing. Never a bare face, never a full-screen title card (§ 6). When the cold open IS a
   live moment (the video starts on the call), it opens O instead, named in `layout_deviations` as `L-OPEN`
   ([`story-and-cut.md`](story-and-cut.md) § 4.11 keeps that call's greeting).
2. **From the last content graphic through the end → S.** This beats every rule below it, the signpost breather
   included. WHY: § 7.
3. **A live moment on camera → O,** the live beat's home: from the clause that names the event (the reaction word before
   it stays on the bare wide face) through your last reaction. WHY: § 2, O. Inside the beat, first match:
   - a. **A line that names a result a screen can show** (the destination the agent was told to use, the booking it
     made, the text it sent, the card it moved), whoever says it → **cut to that screen on the first word of its noun
     phrase**: S, or F when the screen is tall and the F caps allow. The result lands on its confirming verb, even under
     the other voice ([`sfx.md`](sfx.md) owns what sounds there). If the beat goes on after it (your reaction, the next
     turn), cut back to O with the card already live. WHY: the call promises the result; the screen proves it, on the
     word. On the benchmark the call cut to the real board on the noun of the destination you named, and the card landed
     in its column on the agent's "add" (approved, 2026-09-23). The cut back to O is (inferred). **Not when the result has
     no capture of its own, or was already shown in this passage** (a device is built once, [`graphics.md`](graphics.md)
     § 3): O holds (on the benchmark "I've just sent the invoice to the client", with no capture, and a second mention
     of scripts already shown 8 s earlier both stayed on O).
   - b. **Everything else in the beat** (your turns, the other voice with nothing showable, the reveal of who is on the
     line) → O holds. The card and the jump cuts under it carry the cadence.
4. **A promise or direct-address line straight after the hook** ("you're not going to believe how easy this was") →
   T. WHY: the promise is said TO the viewer, eye to eye, and the punch-in is a picture change in the second the viewer
   decides whether to stay. 5 s of bare wide face there read as dead (fixed in the approved cut). L-POSTHOOK only warns:
   a post-hook line that names its own showable thing may go S.
5. **A line that shows the product working as one tall screen → F:** the concept line that defines the product by
   showing it working, or the re-hook that escalates it ("here's where it gets crazy" is one wording of that job). The
   screen must need full height (a thread of several speakers, a full board). It enters on a hard cut: the escalation on
   its line's first word, so the layout itself says "it gets bigger"; the concept line on its subject's noun after its
   lead-in (rule 7). WHY: full height is the only way to read it. Past the F caps (§ 2), the next tall screen goes S,
   framed on the part that proves the line.
6. **A thesis wrapping a named claim → T / S / T:** the opinion words on the face, the claim on its graphic, the payoff
   clause back on the face. WHY: conviction belongs to the person and the claim to its picture; ending on the face lands
   the conviction on you. A taste signal seen once (the approved cut's longest shot, a 10.7 s claim, ran T → S → T):
   use it on a long thesis, never force it on a short one.
7. **The line names or shows a thing → S.** Where it enters:
   - **When the sentence's subject IS the graphic** (a pointing signpost: "check this out", "here's my X"; the next item
     of a running list: "next I have X"; a sentence whose first words name the thing), the graphic cuts in at the
     sentence start (its V1 cut, or its first word's onset when the sentence starts mid-clip), its first element up on
     frame 0. No face flash in front of it. (approved, 2026-09-23: the crew list on "So, check this out", the next
     agent's chat on "Next I have", the terminal on "Normally,")
   - **A turn between two blocks of a running list may take a W breather instead** (the list's rhythm needs a rest
     after a dense block): a taste call, both shipped approved ("Then I have my product lead." on W, "Next I have X"
     straight into S). Choose it here, since rule 8 never reaches a list item; say which in the plan's `why`.
   - **Otherwise the face holds the lead-in** and the graphic enters on the first word of the noun phrase (§ 4). The
     lead-in takes the layout of its own job: a signpost clause with no noun ("Now, if you haven't heard already,") → W
     at any length up to 2.0 s; an opinion or thesis clause → T when it runs 1.5 s or more (shorter: W); any other
     lead-in → W under 1.7 s, T from 1.7 s. A lead-in under 0.6 s gets no face beat of its own: the graphic takes the sentence from its
     start (a face flash under 0.6 s between two graphics reads as a flicker).
   - WHY: graphics illustrate nouns, the viewer sees what they hear, and a panel opened before its first element is an
     empty plate (§ 4). But a sentence whose subject is the thing on screen has no lead-in to hold: a face beat there is
     a flicker, not a breath.
8. **A signpost, connective, section turn or "guys" address standing on its own, with no noun → a W breather, then S on
   the next noun.** WHY: § 2, W. (A list-block turn's breather is chosen at rule 7.) The CTA lead-in is never one of
   these (rule 2).

Then three passes over the whole map:

9. **A planned bare W over about 2 s → T.** WHY: long bare wide is dead air; the punch-in is the same face with a new
   angle.
10. **A W or T under 0.6 s between two graphics (S or F on both sides) → give its words to the graphic after it
    (starting it at the sentence start) or to the one before.** WHY: it reads as a flicker, not a beat. A short W between
    a graphic and an O card is not one: the wide framing continues under the card. (layout.py has no check for it yet;
    read the switch list.)
11. **A single V1 shot far past the cadence (10 s or more) → first ask whether the whole line is necessary**
    ([`story-and-cut.md`](story-and-cut.md) § 4.8: on the benchmark a 13 s shot was answered by the creator cutting the
    generic half of the line, not by decorating it). If it stays: a T switch or a graphic beat at a phrase boundary,
    flagged for taste. Inside O, rule 3a's cut to the next showable result; a live turn that names nothing showable
    stays O, and its L-LONGSHOT is answered in the plan summary ("a live turn: the reaction is the evidence").

Underneath every rule: **graphics illustrate nouns; the face carries persuasion.** The first plan put six T punch-ins on
list and naming lines; each became a split graphic, and T was kept for opinion and emphasis.

**When the live beat IS the video** (a call-dominant demo, the call as the cold open and most of the runtime), rule 3
still holds, and its intercuts carry the pace: every agent line that names a showable thing (a slot booked, a recap, a
text it sends) cuts to that screen and back, your own lines, reactions and the reveal stay O, and the card's own state
changes (ringing, answered, the timer, the waveform) are the in-panel events. The approved cut's 17 % O is no ceiling
there; the numbers to hold are the switch rate and the picture-change cadence (§ 14). (inferred)

## 4. Where a switch lands

- **Two legal places, and nowhere else.**
  - (a) **On a V1 cut in the pause between sentences.** The cut is the rough cut's: most of the pause stays as the
    outgoing tail, with a short lead into the next word (the approved cut's median was 147 ms of tail and 71 ms of
    lead). The switch sits ON the cut's frame, never beside it: 1-2 frames off, the new clip plays that long in the
    old layout (or the old clip in the new one), a double cut on the program, and every lane keys the edge where the
    plan puts it. A phrase-start switch (b) whose word begins 1-2 frames after a cut goes on the cut, which is then
    the legal 0-2 frames early. The same holds for every layout edge, a same-mode row edge included (it breaks the
    caption line).
  - (b) **Mid-clip, on the onset of the first word of the NOUN PHRASE that names the thing shown** (its article,
    possessive or connective: "a team", "my drafts", "so that"), 0-2 frames early and never late.
  - WHY: picture and word arrive together, so the viewer sees what they hear, and a late switch feels laggy. The phrase
    start, not the bare noun: a switch on the noun left the article behind as a one-word caption sliver ("LIKE A", "I
    CAN"), and the phrase start fixed it. On the approved cut, 12 of 21 switches rode V1 cuts and 9 landed mid-clip,
    0-0.10 s before the onset (approved, 2026-09-23).
- **A graphic's boundary and its framing switch are the same frame.** One frame of offset shows the slid-down footage
  with no panel above it, or a panel over the wide face: both read as a glitch.
- **Back-to-back graphics hand off on the same frame:** no overlap, no bare frame.
- **Never an empty panel waiting for its first element:** hold the face and cut on the word (§ 3, rule 7). The first
  element is visible on the graphic's own frame 0.
- **A graphic never starts over unrelated lead-in words.** Its subject is named, and then it is there.
- **Every switch, every graphic boundary and every `shot_cuts` time is a forced caption break, except a montage's own
  shots.** layout.py hands those frames to captions.py, so no caption line straddles a change in what is on screen, and
  a graphic that changes mid-sentence cuts on a phrase boundary with the caption break on the same frame. A montage's
  shots cut on a steady beat, mid-word, inside one S span, so its lines run across them (only its entrance and exit
  break); a cell's `caption_breaks` overrides ([`captions-style.md`](captions-style.md) § 5).
- The overlap and empty-plate defects these rules stop are [`graphics.md`](graphics.md) § 14's.

## 5. Transitions

- **Between layouts: hard cuts only.** No dissolve, no zoom transition, no ramp. Not the long-form opening zoom-out or
  its push-ins either ([`presets/youtube/default/README.md`](../../youtube/default/README.md)): they belong to another
  visual language, and here the switch IS the move.
- **Two moves share a word elsewhere; here they are named apart.** The **slide hand-off** is the lateral move below
  (`components.push`, `PUSH_FRAMES`). A **push-in** is a slow zoom on a capture ([`captures.md`](captures.md) owns where
  one is allowed); a static page or brand takes neither: its cut is its entrance ([`captures.md`](captures.md) § 8).
- **The slide hand-off is allowed only from graphic to AUTHORED graphic inside S, with no layout change,** for the CTA
  hand-off (§ 7) or for one continuous thought. It runs `PUSH_FRAMES` (the motion is [`graphics.md`](graphics.md) § 13,
  Push; its whoosh [`sfx.md`](sfx.md)). The footage half never moves. WHY: a slide reads as "next" and keeps the eye where it already is (2026-09-23, on the
  ad's ask: "the text graphic just slides out to the left, and then the new graphic... slide[s] in"). **A capture never
  arrives by the slide:** it arrives on its cut, with its shutter ([`sfx.md`](sfx.md)); the kit refuses the slide for it.
  Two S graphics with a new subject hand off on a hard cut.
- **A face beat separates graphic blocks,** except where the story escalates into a bigger screen, the proof continues
  across the switch (whatever the two layouts: a thread into the call it set off, a call into the screen its result lands
  on), or the next line names the next item of a running set. WHY: the face beat is the pause between ideas. Skipping it
  says "this continues", which is exactly what an escalation, a running proof or a list means; anywhere else the graphics
  blur into one slideshow. On the approved cut, 17 of 21 switches passed through a face beat.

## 6. The hook frame

- **Frame 0 is S, with the hook visual already moving:** its first element pops on frame 0 (a proof hook's real page is
  whole on frame 0 and its zoom starts within the first frames, [`graphics.md`](graphics.md) § 5), the first word lands
  about 0.1 s in, and the caption is up by frame 2. No preamble, no bare face, no title card.
- **A two-clause hook may cut once inside the hook sentence,** on the second clause's first word, with the caption
  breaking on the same frame: the proof on the result clause, the concept lockup on the vehicle clause ("I've made over
  $375,000 online | from selling AI workflows", 2026-10-15). Both cells are the hook; the hook still ends on the
  first V1 cut.
- **The hook graphic lives exactly the hook sentence and ends on the first V1 cut** (as two cells when the hook cuts
  once inside it, above).
- **The promise cuts to T** (§ 3, rule 4).
- **The caption stays on the seam.** When the hook stack crowds it, the stack lifts or shrinks; the caption never moves
  ([`graphics.md`](graphics.md) § 5 owns the stack and its lift).
- The lockup itself (the real icon, the name, the claim's object performing the claim): [`graphics.md`](graphics.md)
  § 5, the hook lockup. The hook's words: [`story-and-cut.md`](story-and-cut.md) § 2.

## 7. The CTA stays split

You said it on the ad's ask (2026-09-23: "we should never actually exit the top-half/bottom-half framing" between
the last graphic and the CTA), in the same message that approved the organic, which still carries a 0.9 s wide hop on
"So guys,". Applying it to the organic too is an inference, because nothing in its reason is specific to the ad:
confirm it with you on the first organic that follows this rule. layout.py enforces it on both (L-CTA), so a creator
who keeps the organic hop names it in `layout_deviations`. A video with no CTA cells (role `cta`) has no ask, and none of
this applies.

- **From the last content graphic through the end, the layout stays S.** No wide hop on "So guys,". The last content
  graphic is the last cell before the CTA's own cells (role `cta`), usually the claim or the objection-killer.
- **The ask's first cell starts on the ask's first word, on the last content graphic's last frame.** No content graphic
  hangs into the ask ([`README.md`](README.md#first-pass-ledger), the first-pass ledger), so for the ask's FIRST promise "the real thing on its noun"
  yields to "from the ask's first word" (graphics.md § 6).
- **How it arrives depends on what it is.** An authored first cell (a click card, the thread) arrives by the slide
  hand-off (§ 5). A capture (the promised page) arrives on a hard cut on that word, with its shutter.
- **Between the cells inside the ask: hard cuts on phrase boundaries,** each sounding its own element
  ([`sfx.md`](sfx.md)), with the caption breaks on the same frames.
- **The last graphic holds through the final frame,** with no exit. Its length is re-derived from the live sequence end
  after any trim; a tail trim otherwise leaves a graphic running past the end or a bare last frame.
- **End cold on the ask:** the CTA's last word plus a short tail. A sign-off that was never filmed is flagged as a pickup,
  never assembled from other words ([`story-and-cut.md`](story-and-cut.md) § 4.9).

WHY: the ask is the conversion moment. A sub-second hop to the wide face right before it reads as a layout flicker, and a
three-second ask cannot spend a third of itself on a bare-face breather. Graphic to graphic keeps the eye where it
already is.

## 8. The frame and its bands

- **Authoring frame 1080x1920; the seam is y960.** Every number in this doc is frame px on the 1080x1920 deliverable.
  An authored scene's own type and UI sizes are [`graphics.md`](graphics.md) § Units' panel px (the kit's components lay
  a 1080x960 panel out and fit it into y≈202-960 at 0.79): that is the kit's locked authoring convention, not an
  artefact, and the fitted result is what these bands and the checks measure.
- **Platform-safe box y200-1620: nothing identifying in the top 200 px or the bottom 300 px, entrances included.** The
  first frame of a drop-in counts. WHY: the platform's UI covers those bands on every phone. The first layout pass pinned
  app headers at y0-112 on 11 of 18 scenes and dropped a card whose first frame sat at y127.
- **Split content zone y200-845.** Key ink ends at least 75 px above the seam caption's box top (y921.5). A composed
  stack (a hook, a thread, a lockup) is centred in the zone, its hero a little above centre. Plain fill (a capture's own
  colour, a window's empty bottom edge, docked at y880: [`captures.md`](captures.md) § 6) may run lower, and a real
  page may run on under the caption box to the seam (`under_caption`, below); authored ink and whatever must be read
  never do. WHY: the caption must read as the only
  text at the seam (2026-09-23: "give a little bit of space between the captions in the middle and what's going on
  with the graphics"; on a thread, "we have to center it on the top half of the screen").
- **The panel is opaque y0-960 on every frame.** A half-transparent frame shows the slid-down footage's top edge.
- **HARD GATE: zero AUTHORED ink in y908-960 on S.** No text, avatars, UI rows or spill from an authored scene, and no
  "it's part of the look" waiver: a spill waived as the look once put red log text on the caption's cap-tops. The caption
  owns the seam; an authored graphic that collides is lifted, scaled or reframed inside its slot, and the caption keeps
  its band. **A real screen is the one exception:** a capture's page runs on under the caption box down to the seam, its
  cell says so with `"under_caption": true` (§ 12), and what must be read on it stays in the content zone above
  ([`captures.md`](captures.md) § 4 owns it). The numbers are
  owned by [`captions-style.md`](captions-style.md) § Values (`GATE_BAND`); [`graphics-qa-short.py`](../../../workflows/graphics-qa-short.py)
  reads the band from captions.py.
- **Side spill is allowed, but it dissolves by y900.** An effect may run off the panel's sides (an overwhelm pile, a
  burst); its mask is transparent before the gate band.
- **F content runs from the top of the safe box to its caption box top minus 20.** A docked capture's header sits at
  `FULL_TOP` y260 by default and may rise to y205 when the content needs the height (the two approved F scenes pinned
  theirs at y260 and at y205 at full push; both clear the platform UI). The content ends above its own caption line.
- **The top half is one cohesive screen:** the fills and the families are [`graphics.md`](graphics.md) § 7 and
  [`captures.md`](captures.md) § 4, One screen.
- **The sequence is the source's own size and rate on a 9:16 raw** (a 16:9 raw: 1080x1920, § 2). Graphics are authored
  at 1080x1920 and fitted by the lane placer (a 4K sequence takes them at 200 %). Every readability and privacy judgement
  is made on the 1080 deliverable, never on the 4K timeline: 4K is headroom for the punch-in, 1080 is what the platform
  shows.

## 9. Card clearance: cards over W (O)

- **The card's bottom edge sits at least 25 px above the TALLEST crown anywhere in its span, entrance travel included.**
  Measure it per shoot (`uv run workflows/face-frame.py projects/<job> --crown A B`, the span's timeline seconds, or the
  `crowns` reading in § 2), never from a thumbnail. WHY: a card on the hair reads as a mistake. On the benchmark, three
  reviewers found the card over your hair on the second call, where you sat taller; the first call's thumbnails had hidden
  it.
- **One shared height per card kind, set by the tallest pose** across every span of that kind, so the card never jumps
  between beats.
- **No entrance frame above y204.** The drop starts inside the safe band, never above it.
- **The framing never changes under a card.** No T: a punch-in pushes your forehead into the card. Jump cuts underneath
  are fine. Leaving the live beat for a screen (§ 3, rule 3a) ends the card first: its exit ends on the switch frame.
- **A card inside a graphic is not an O.** A call that arrives while a chat is up drops over the chat inside that S
  graphic, as part of it ([`graphics.md`](graphics.md) § 3.4); O is only the card over the wide face.
- The caption over O sits where it sits on W (§ 10).

## 10. Caption heights follow the layout

A pointer: the rule and its measurement live in [`captions-style.md`](captions-style.md) § 2.

- **S:** on the seam.
- **W and O:** the box top 40 px under the collar, where the collar meets the skin, measured per shoot.
- **T:** derived through the T transform (the measured collar mapped through the punch-in), never set by eye: the
  benchmark's tight line was set by eye and sat on the neck.
- **F:** under the graphic's bottom UI on its own fill: the F row's `ui_bottom` (layout.py derives the line as
  `ui_bottom` + 58.5) or a typed `caption_y`; on the seam when the F graphic keeps the seam clear (`seam_clear`).

The same layout map drives the footage keys and the caption y, so the footage and the caption move on the same frame.

## 11. Substituted clips

A lip-synced or re-taken clip inherits its neighbours' framing exactly. It is generated from the full raw frame, starting
on the exact raw frame the replaced clip starts on, and laid at raw geometry with the replaced clip's own framing keys;
the layout keys are never re-run blindly over it. The proof is on the picture: [`framing-continuity.py`](../../../workflows/framing-continuity.py)
exits 0 at both cuts. Owner: the [`CLAUDE.md`](../../../CLAUDE.md) lock "A SUBSTITUTED CLIP IS PROVEN ON THE PICTURE".
WHY: on a static background even a 30 px shift reads as a jump (2026-09-22: "You see how the background moves...
now it looks like it jumps").

## 12. The plan contract (graphics-plan.json)

On this format the plan carries the layout. This section is the one home of the fields; the house schema is
[`graphics-plan`](../../../.claude/skills/graphics-plan/SKILL.md) § `graphics-plan.json` schema, and this format adds:

- **A top-level `layout`:** `[{start, end, mode, why, ...}]`, `mode` one of `S T W F O`. On the timeline clock,
  frame-snapped to the plan's `fps`, tiling 0 to `duration` with no gap and no overlap. It is the one home of the footage
  framing: the footage keys, the caption heights, the forced caption breaks and the SFX cut-ins all read it.
  - `why` names the sentence's job (§ 3), so a reviewer can argue with the choice.
  - **`frame`** (optional, any mode): `{"scale": s, "centre": [x, y]}` in the units of face-frame.json `modes`, the
    row's own footage transform over its mode's: a span framed apart from the median (§ 2, `span_modes`). Every lane
    reads it through `layout.footage_spans()`: `lanes/premiere/layout-keys.py` keys it (and a hand Motion equal to it
    reads MATCH), the CapCut `layout` command lays it, `lanes/chat-only/assemble.py` cuts it. Two adjacent rows of one
    mode with different frames are a switch on the footage; F and O rows frame W's footage. A malformed one is an
    L-TILE FAIL.
  - **On an F row, one of three:** `ui_bottom` (the F graphic's lowest UI edge, frame px: the caption line is derived as
    `ui_bottom` + 58.5); a typed `caption_y` (the line centre, which wins over `ui_bottom`); or neither, when a cell over
    the span carries `seam_clear: true` (its ink stays out of the seam caption's box and the gate band, so the line stays
    on the seam). Anything else is an L-CAPY FAIL: an F left on the default would put the caption over its content.
  - On W, T and O, `caption_y` is only an override; the heights come from face-frame.json `collar` (§ 2). The captions
    cell's approved `y.wide` / `y.tight` win over it only as [`captions-style.md`](captions-style.md) § 2 says (the one
    home of the precedence): with their `measured` note and not older than the collar, or where no tool has measured one.
- **`preset`:** this folder, `presets/instagram/talking-head-explainer`. **`format`:** `short-talking-head-explainer`.
- **Every graphic cell carries:**
  - `family`: `authored` | `capture` | `montage` | `overlay` ([`graphics.md`](graphics.md) § 7, families and finish).
    `overlay` is the O card; it is the only family that may sit over W.
  - `readable`: true when the viewer must read it. A montage is glanced, never read. The house 3.0 s readable hold does
    not apply here: `validate-plan.py` holds this format to [`graphics.md`](graphics.md) § 13's own rule (whole for
    about 2 s, a WARN to check on the render; the cut never moves for a hold).
  - `shows`: on a capture, what must be visible in the frame for it to be evidence.
  - On a capture (`kind` `screen-rec` or `screenshot`): `capture` (`{source, target, action, seconds | still}`, what the
    build records) or `asset` (the take already at `assets/captures/<id>.<ext>`, staged by `kit/engine.py stage`): the
    house capture gate ([`graphics-plan`](../../../.claude/skills/graphics-plan/SKILL.md) § THE CAPTURE GATE).
  - `copy`: the words the graphic itself puts on screen (a name, a figure, a keyword), for the OCR copy check in
    `graphics-qa-short.py`; empty when it shows none. Never the caption's words.
  - Not `region` and not `content`: the layout map places every graphic, so those long-form fields are optional here.
  - `shot_cuts`: the timeline seconds of the picture cuts inside the graphic; each forces a caption break (a
    montage's do not: § 4), and each montage shot between them holds [`captures.md`](captures.md)'s `MONTAGE_SHOT_S`.
  - `sync`: the word anchors its events land on (the house `sync` syntax).
  - `role`: the house role; `hook` on the hook, `cta` on every cell of the ask (L-CTA finds the last content graphic by
    it).
  - `visuals`: what is on screen, one entry per element; L-WORDCARD reads it.
- **On an F graphic:** `seam_clear: true` when it keeps the seam clear (above).
- **On a capture:** `under_caption: true` when its page runs on under the caption box to the seam, the default for a
  page capture ([`captures.md`](captures.md) § 4). `graphics-qa-short.py`'s `band` then prints its band ink as an `ok`
  line, by design, never a FAIL and never a per-cell waiver; the flag on an authored, montage or overlay cell FAILs
  ("applies only to a real capture"), and a capture without it is held to the band. Per-shot fills are the build's (a
  capture shot's own `bg` in the kit), never a cell key: no cell carries `bg` (below). A cut inside one take
  with no shutter (a dead stretch removed, [`captures.md`](captures.md) § 5) is a `shot_cuts` time like any other: it
  breaks the caption.
- **On an overlay (O card) cell:** `card: {top, bottom, enter_top}` (the card's box on the frame, and the highest y its
  entrance reaches) and `crown` (the tallest crown over its span, § 9), or the span's entry in face-frame.json `crowns`.
- **A cell's `kind` is never `punch-cut`, `full-screen` or `scene`, and no cell carries a `bg` key.** Every render on
  this format is an alpha overlay, and the lane placer ([`place-graphics.py`](../../../lanes/premiere/place-graphics.py))
  sends those kinds, and any cell with `bg`, down the full-screen mp4 path. A full-screen is expressed by the layout map
  (mode F), never by the kind.
- **`variants.ad`:** `{from, layout, cells}` for a second deliverable. `from` is the timeline second where the variant's
  cut diverges (the first word of the alternate CTA sentence); its `layout` tiles `from` to the variant's own end (its
  last `end`, or an explicit `duration`), its `cells` replace every cell from there, and everything before `from` is
  inherited. § 7 holds on the variant too, and `validate-plan.py` gates it. There is no separate plan file: the
  captions, the lane's placer (`--variant ad`) and `graphics-qa-short.py --variant ad` all compose it with
  `layout.compose_variant`, and a re-cut ahead of `from` moves it whole (`workflows/ripple-cut.py`).
- **`layout_deviations`:** `[{rule, why, at}]` names a deliberate deviation (`at`, optional, pins it to the finding
  within 0.5 s of that second). It turns that FAIL into a printed WARN carrying the reason, so the deviation is a
  decision on the record, not a silent pass.

A generic example: the invented video walked through in § 15, on a 30 fps grid so the arithmetic stays readable (a
`//` line is a note, not JSON):

```json
{
  "job": "<job>",
  "format": "short-talking-head-explainer",
  "preset": "presets/instagram/talking-head-explainer",
  "compositor": "premiere",
  "duration": 43.8,
  "fps": "30",
  "layout": [
    {"start": 0.0,  "end": 3.6,  "mode": "S", "why": "the hook: the lockup from frame 0"},
    {"start": 3.6,  "end": 5.9,  "mode": "T", "why": "the promise: direct address"},
    {"start": 5.9,  "end": 7.0,  "mode": "W", "why": "a signpost with no noun: a breather"},
    {"start": 7.0,  "end": 13.8, "mode": "S", "why": "names the app in its first words, then the agent"},
    {"start": 13.8, "end": 18.2, "mode": "F", "ui_bottom": 1362, "why": "the escalation: a tall reply thread"},
    {"start": 18.2, "end": 18.7, "mode": "W", "why": "the reaction word stays on the bare face"},
    {"start": 18.7, "end": 25.9, "mode": "O", "why": "live proof: the card drops on the clause that names the call"},
    {"start": 25.9, "end": 29.6, "mode": "S", "why": "the call names a result a screen shows: the drafts folder"},
    {"start": 29.6, "end": 31.2, "mode": "T", "why": "thesis: the opinion words"},
    {"start": 31.2, "end": 33.1, "mode": "S", "why": "thesis: the named claim"},
    {"start": 33.1, "end": 34.8, "mode": "T", "why": "thesis: the payoff clause"},
    {"start": 34.8, "end": 43.8, "mode": "S", "why": "the last content graphic, then the ask: split to the end"}
  ],
  "beats": [
    {"id": "captions", "start": 0, "end": 43.8, "graphic": true, "kind": "captions", "region": "captions",
     "content": "the locked caption layer, built by captions.py from the canonical transcript"},
    {"id": "g1", "start": 0.0, "end": 3.6, "role": "hook", "graphic": true, "kind": "ui-enactment",
     "family": "authored", "readable": false, "sync": [{"word": "voice memos"}, {"word": "newsletter"}],
     "visuals": ["the memo app's icon", "a waveform folding into a page"],
     "line": "I built an AI that turns my voice memos into a finished newsletter every Friday."},
    {"id": "g2", "start": 7.0, "end": 10.3, "role": "setup", "graphic": true, "kind": "screen-rec",
     "family": "capture", "readable": true, "shows": "the memo app recording, its waveform moving",
     "capture": {"source": "app", "target": "Voice Memos", "action": "a memo recording", "seconds": 5},
     "shot_cuts": [], "sync": [{"word": "voice-memo", "expect": "first change"}]},
    {"id": "g4", "start": 13.8, "end": 18.2, "role": "payoff", "graphic": true, "kind": "screen-rec",
     "family": "capture", "readable": true, "shows": "the thread, the agent's replies landing one by one",
     "asset": "assets/captures/g4.mp4", "copy": "Friday Digest",
     "shot_cuts": [], "sync": [{"word": "replies"}]},
    {"id": "g5", "start": 18.7, "end": 25.9, "role": "demo", "graphic": true, "kind": "call-ui",
     "family": "overlay", "readable": false, "card": {"top": 388, "bottom": 600, "enter_top": 204}, "crown": 625,
     "sync": [{"word": "calling", "expect": "first change"}]},
    {"id": "g6", "start": 25.9, "end": 29.6, "role": "evidence", "graphic": true, "kind": "screen-rec",
     "family": "capture", "readable": true, "shows": "the drafts folder, three replies landing in it on 'Done'",
     "capture": {"source": "app", "target": "Mail", "action": "three drafts arrive in the folder", "seconds": 6},
     "shot_cuts": [], "sync": [{"word": "Done", "expect": "first change"}]}
    // g3 and g7-g11 follow the same shape; g9-g11 carry "role": "cta"
  ],
  "variants": {"ad": {"from": 36.5,
    "layout": [{"start": 36.5, "end": 40.1, "mode": "S", "why": "the ad's ask: split to the end"}],
    "cells": [{"id": "g9ad", "start": 36.5, "end": 40.1, "role": "cta", "graphic": true, "kind": "ui-enactment",
               "family": "authored", "readable": true, "sync": [{"word": "click"}, {"word": "below"}]}]}},
  "layout_deviations": []
  // e.g. {"rule": "L-OPEN", "why": "cold open on the live call: the call IS the hook"}
}
```

## 13. The checks

[`layout.py`](layout.py) runs them, called by `validate-plan.py` whenever the plan's `preset` is this folder, and on its
own with `uv run presets/instagram/talking-head-explainer/layout.py projects/<job> --check`. A FAIL blocks the plan. A
WARN prints with its number and is answered in the plan summary. A `layout_deviations` entry turns a named FAIL into a
WARN carrying its reason. This table is identical to `layout.RULES`, plus L-ALIGN (`layout.PLACEMENT_RULES`), which runs
only once `hf-graphics/placement.json` exists, after 5b placed the graphics: it cannot be judged on a plan.

| Code | Level | Meaning |
|---|---|---|
| L-TILE | FAIL | gaps, overlaps, or an edge off the frame grid |
| L-OPEN | FAIL | span 0 is not S at t=0 |
| L-EMPTY | FAIL | an S or F span not fully covered by graphic cells |
| L-CROSS | FAIL | a non-overlay cell reaching into T or W |
| L-OVERLAY | FAIL | an O span without an overlay cell |
| L-CARD-T | FAIL | T under a card |
| L-CARD-CLEAR | FAIL | a card over the measured crown, or entering above y204 |
| L-CTA | FAIL | any W or T from the last content graphic to the end |
| L-SWITCH | FAIL | a switch neither on a V1 cut nor 0-2 frames before a word onset |
| L-NEARCUT | FAIL | a layout edge 1-2 frames off a V1 cut instead of on it |
| L-FAMILY | FAIL | a cell without a valid `family` |
| L-READ-MONTAGE | FAIL | `readable: true` on a montage |
| L-MONTAGE-SLOW | FAIL | a montage shot over 1.3 s, cell edge or shot cut to the next |
| L-KIND | FAIL | a forbidden kind or a `bg` key |
| L-CAPY | FAIL | an F span without `caption_y` whose graphic does not keep the seam clear, or a W/T/O span with no measured collar and no plan override |
| L-ALIGN | FAIL | a placed graphic edge off its framing switch frame, or a gap or overlap between back-to-back rows |
| L-POSTHOOK | WARN | the span after the hook is not T |
| L-BAREW | WARN | bare W over 2.0 s |
| L-TIGHT | WARN | T outside 1.5-4.5 s |
| L-FULL-COUNT | WARN | more than 2 F per 120 s |
| L-FULL-SHARE | WARN | F over 12 % |
| L-FULL-LEN | WARN | an F span outside 4-8 s |
| L-FACE | WARN | face visible under 85 % |
| L-COVER | WARN | graphics under 75 % |
| L-LONGSHOT | WARN | a V1 segment of 10 s or more with no switch inside |
| L-STALE | WARN | more than 4.5 s with no switch or cell boundary, outside O |
| L-WORDCARD | WARN | a non-hook cell whose visuals are type only |
| L-MONTAGE-FAST | WARN | a montage shot under 0.6 s |

The WHY behind each FAIL is the section it enforces: L-TILE, L-SWITCH, L-NEARCUT and L-ALIGN § 4, L-OPEN § 6, L-EMPTY § 4 (the
empty plate), L-CROSS and L-OVERLAY § 2, L-CARD-T and L-CARD-CLEAR § 9, L-CTA § 7, L-FAMILY and L-KIND § 12,
L-READ-MONTAGE and L-MONTAGE-SLOW [`captures.md`](captures.md) § 7 (a montage is felt, one short shot per named item, never
read), L-CAPY § 10. L-WORDCARD enforces the show-don't-tell law in [`graphics.md`](graphics.md) § 1: a word card
restating the line fights the caption for the eye. An F row's `caption_y` counts as present when it is derived from
`ui_bottom`.

**The standard answers to WARNs the preset itself produces.** Each is expected on its shape; name the span and give
this answer in the plan summary. Any other instance of these WARNs is a real question to the plan.
- **L-STALE on a compliant F** (one continuous take at a fixed frame, [`captures.md`](captures.md) § 5), **on a hook
  sentence over 4.5 s** (the hook graphic lives exactly its sentence, § 6), **and on one scene that builds on its words**
  (an escalation, a list whose items land on their words, [`graphics.md`](graphics.md) § 3): the check counts switches,
  cell edges and shot cuts, not the events inside the panel. Answer: the cell's `sync` anchors land about one a second.
  A span with no in-panel event for 4.5 s is stale, whatever its shape.
- **L-LONGSHOT inside O on a live turn that names nothing showable:** "a live turn: the reaction is the evidence"
  (§ 3, rule 11).
- **L-BAREW and L-FACE over screen-recording footage:** name the span (§ 2).
- **L-POSTHOOK when the promise names its own showable thing** and went S (§ 3, rule 4).

## 14. Cadence outcomes (calibration, never quotas)

layout.py prints these beside the new video's own numbers. They are what the approved two-minute cut came out at, so a
big gap is a question to ask the plan, never a target to hit.

- **Shares:** S about 60 %, W+card 17 %, F 10 %, T 8 %, bare W 6 %.
- **Face visible about 90 %; graphics on screen about 85 %.**
- **About 20 layout switches per 2 minutes.**
- **A picture change about every 3 s** (V1 cuts, graphic ins and outs, framing switches), **plus an in-panel event about
  every second** (a message lands, a tile pops, a badge lands on a key word).
- **W breathers average about 1.2 s; T spans about 3 s; graphics 4.5 s** (range 1.2-12 s).

## 15. Planning a new video, sentence by sentence

A worked pass over 8 invented lines (a creator explaining an agent that turns voice memos into a newsletter). It is an
illustration of the method, not a template for any video.

1. **Mark each sentence's job:** names a thing / signpost / opinion / reveal / live moment / CTA.
2. **Assign the mode** by § 3.
3. **Pick the graphic** by [`graphics.md`](graphics.md) § 3, picking the graphic for a line.
4. **Set the switch points** (§ 4), with the caption breaks on the same frames.

| # | Line (invented) | Its job | Mode | Graphic | Switch lands on |
|---|---|---|---|---|---|
| 1 | "I built an AI that turns my voice memos into a finished newsletter every Friday." | hook | S from frame 0 | the hook lockup, the claim enacted (authored) | frame 0; ends on the first V1 cut |
| 2 | "And it took me one afternoon." | promise | T | none | the V1 cut |
| 3 | "So here's how it works." | signpost | W | none | the V1 cut |
| 4 | "I talk into a voice-memo app on my walk, and an agent drafts the whole issue in my voice." | names two things | S | the memo app recording (capture), then the memo becoming a draft (authored) | the V1 cut at the sentence start (its lead-in "I talk into a" runs 0.5 s: no face beat); the second graphic on "an agent", a hard cut (a new subject) |
| 5 | "But here's where it gets crazy: it answers the replies too." | escalation: the screen is the story | F | the reply thread, tall, playing in real time (capture) | the V1 cut; S → F with no face beat, because the story escalates |
| 6 | "Hold on, that's the agent calling me now." (on speaker) "Three readers replied overnight. Answer them, or add them to your drafts?" "Add them to my drafts." "Done, they're in your drafts folder." | live moment, then a result a screen can show | W, O, then S | a compact call card above the crown; then the drafts folder (capture), the replies landing on "Done" | "Hold on," bare; the card on "that's"; the drafts folder on "my drafts" (the noun phrase naming the destination) |
| 7 | "Honestly, I think a writing agent is the easiest AI win there is." | opinion wrapping a named claim | T / S / T | the claim's graphic on "a writing agent" | the V1 cut; "a"; "is" |
| 8 | "And you don't have to code a single thing. So if you want my template and the setup video, comment MEMO and I'll send it over." | objection-killer, then the CTA | S to the end | the problem visual struck through; the real template page from "So"; the setup video on "and the setup video"; the comment thread on "comment", MEMO typed as spoken | the V1 cut; the template page on "So", a hard cut with its shutter (a capture never slides); hard cuts on the phrase starts after it |

Line 4 shows the flicker rule: its lead-in is under 0.6 s, so the sentence opens on its graphic instead of a face flash
between line 3's breather and the app. Line 6 is rule 3 whole: the reaction word stays bare, the card lands on the clause
that names the call, and the call hands to the screen on the noun phrase that names the result; the call ends there, so
there is no cut back to O. Line 8's "So" is the CTA lead-in and stays S (§ 7); the ad variant's ask is an authored click
card, so there the hand-off from the struck-through problem visual is the slide.

5. **Run** `uv run presets/instagram/talking-head-explainer/layout.py projects/<job> --check` (the map is the § 12
   example). On this map it returns 0 FAIL and 0 WARN and prints these numbers beside § 14's: S 57 %, O 16 %, T 13 %,
   F 10 %, bare W 4 %; face 90 %, graphics 84 %; 11 switches in 44 s. The F span is 4.4 s, under the 5-7 s target and
   inside the 4-8 s band: one sentence is one sentence, and a longer F would have pushed the share past 12 % on a video
   this short. `--variant ad` returns the same.
6. **Check the shape:** hook S, promise T, proof by about 20 % (here the first real capture at 16 %), re-hook about 50 %
   (here 32 %: early, because a 44 s piece compresses the skeleton; flag it only if the re-hook came before the first
   proof), at most 2 F (here 1), the ask on S from its first word (here yes). Answer every WARN in the plan summary.

## 16. Illustrations only

Measured on one shoot; re-measure every job, never copy.

- **The calibration face** (the wide shot of a 2160x3840 raw, on the 1080 frame): face box 250x284 px, centre (539,
  940), hair top y626, collar y1225-1240. In S the chin sat at y1516; in T the face box was 398 px tall. These define
  T's target (§ 2), nothing else.
- **The per-shoot Motion values.** On a 2160x3840 Premiere sequence: S Position y 0.7271 (a face centre at y949 on the
  wide frame moved to y1385) and T Scale 140, Position (0.4896, 0.4662). They are what the § 2 transforms came out at on
  that face.
- **The card height:** y388-600 (212 px), fitted to that shoot's crown at about y625. The rule is § 9.
- **The full-screen header and dock heights:** headers at y260 and y205, docked window bottoms at y1362-1400, and the F
  caption near y1420, fitted to that chat app's chrome and captures ([`captures.md`](captures.md)).
- **The tight caption at y1260,** set by eye and sitting on the neck: not a value. Derive it through T (§ 10).
- **The organic cut's 0.9 s W on "So guys,":** shipped before the CTA rule was said (§ 7).
- **The second short's face** (2026-10-14, a 3840x2160 landscape OBS take fitted by height): a face box 482x527
  source px, S at scale 0.85 with its centre y moved +45 px by your two notes (hair top y1062 on the verify), every
  framing 40 px right (60 on one clip) for your shoulders, the collar at y1355. Re-measure every shoot.
- **The exact layout sequence, the 23 graphics, two O beats and two F beats:** that script had two calls, one concept
  line shown as a whole thread and one escalation into a group thread. Another script gets the layouts its sentences ask
  for.

## Values

[`layout.py`](layout.py) mirrors this block, and [`face-frame.py`](../../../workflows/face-frame.py) carries the same
framing numbers (`HAIR_GAP`, `FACE_CY_FALLBACK`, `HAIR_GAP_MIN_Y`, `CHIN_MAX_Y`, `T_FACE`, `T_FACE_H`, `T_MIN`) and
derives its caption clamps from captions-style.md's box; `workflows/test_talking_head_layout.py` holds them all equal.
Pixels are on the 1080x1920 authoring frame; `*_S` in seconds; `*_FRAMES` in timeline frames; `a-b` is a range; `x,y` a
point. `HAIR_GAP` is the median hair top's distance under the seam in S (so the hair sits on y1060). `HAIR_GAP_MIN_Y` and
`CHIN_MAX_Y` no longer move the hair (it holds, § 2): together they set S's largest face span on a landscape raw (600 px
hair to chin), `HAIR_GAP_MIN_Y` is also the highest hair top `face-frame.py --verify` passes (y1060 less its 40 px
tolerance), and `CHIN_MAX_Y` is the line past which the tool prints the chin as a note. `T_FACE_H` is the tight face-box height and
`T_MIN` the loosest punch-in. `T_SCALE` is calibration only, read by no code: the benchmark's punch-in at its face
height; on another camera distance `T_FACE_H` / the wide face-box height sets the scale.
`FULL_TOP` is a docked F header's default top (§ 8). `PUSH_FRAMES` is the slide hand-off (§ 5).

```values
SEAM_Y 960
SAFE 200-1620
SPLIT_ZONE 200-845
SPILL_DISSOLVE_Y 900
FULL_TOP 260
HAIR_GAP 100
FACE_CY_FALLBACK 1385
HAIR_GAP_MIN_Y 1020
CHIN_MAX_Y 1620
T_SCALE 1.40
T_FACE 540,866
T_FACE_H 400
T_MIN 1.15
W_BREATH_S 0.6-1.7
BARE_W_MAX_S 2.0
T_SPAN_S 1.5-4.5
F_SPAN_S 5-7 (warn outside 4-8)
F_PER_120 2
F_SHARE_MAX 0.12
FACE_MIN 0.85
COVER_MIN 0.75
STALE_MAX_S 4.5
LONG_SHOT_S 10
CARD_CROWN_AIR 25
CARD_TOP_MIN 204
SWITCH_EARLY_MAX_FRAMES 2
NEAR_CUT_FRAMES 2
PUSH_FRAMES 10
```
