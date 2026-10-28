# Talking Head Explainer (instagram/talking-head-explainer)

One creator talks to one locked-off camera for a 9:16 short, usually 60 to 150 s, explaining a real tool or system (or, with no product, a real claim) and proving it on screen while you name it. The promise of this preset: hand over any new raw of that kind and the first pass reaches the approved bar, with nothing re-explained and nothing fixed by hand afterwards. It was reverse-engineered on 2026-09-23 from a two-minute sponsored explainer that the creator approved after 7 review rounds and two hand passes by the creator. Evidence is weighed in one order, your hand edits first, then what you approved, then Claude's unreviewed calls, and the FINAL state wins: an early choice you later corrected is written down as an anti-pattern, never as a rule. Every example in these docs illustrates a principle and is never a template (2026-09-10).

**Re-baked on 2026-10-15 from a second short** (a 97 s sponsored how-to, landscape raw, Premiere): about twenty step-7
notes, nearly all on the real screens (crop, fill, size, your own artifacts), your face's framing, three line cuts and
three concept graphics asked for by name. What they had in common is now the default; that video's specifics sit in
each doc's closing illustrations section.

## Read order

This README first: the ten laws, then your step's row in [§ Where each step lives](#where-each-step-lives). Then the doc that owns your step, then that doc's values block. Nothing is copied from another job, not a comp, a render, a plan, a sheet or a capture: the build kit is copied from this folder only (`kit/engine.py init`), and every capture is shot fresh for the job.

## The format on one screen: ten laws

Each law is the rule, the one reason it holds, and the section that owns it. The numbers live in the owner, never here.

- **L1. The face persuades, the top half proves.** Why: the creator is the brand, and the proof has to be on screen while you name it. Owner: [`layout.md`](layout.md) § 1, Why.
- **L2. The layout is the pacing engine: rotate split / tight / wide / full / card on hard cuts, with split as home.** Why: one locked-off camera has no second angle, so a layout change is the new angle. Owner: [`layout.md`](layout.md) § 2 and § 3.
- **L3. Show, never tell: a graphic enacts its line on the word, and the caption carries the words. Big type is rationed to a few concept lockups (the hook's, and the name of the thing the video sells), each with an object that performs it.** Why: the same words twice split the eye and neither gets read; a name the video turns on, landing with its own object, is a title the viewer remembers (2026-10-15). Owner: [`graphics.md`](graphics.md) § 1, The two laws, and § 5.
- **L4. Real before authored, and real means HIS: capture what the product does (or what the claim stands on) on your own accounts, docs, site, checkout and calls, author only what has no screen, never invent evidence.** Why: the real thing on screen is proof, an illustration can only explain, and a random third-party example proves nothing about you (2026-10-15). Owners: [`graphics.md`](graphics.md) § 2, Real vs authored, and [`captures.md`](captures.md) § 1.
- **L5. On the word, measured: the picture, the caption break and the sound land within 2 frames of the word, proven on the render; the one designed lead the kit writes (masked_value's key run) is named in code and on its sound row, never an unexplained offset.** Why: a 0.9 s clock error passed every still and was wrong everywhere. Owner: [`graphics.md`](graphics.md) § 13, Motion.
- **L6. Readable means whole, flat, big, centred and still; only glanced activity may tilt. A real page FILLS the top half on its own colour: big, edge to edge, down to the seam.** Why: a clipped or tilted screen proves nothing at phone size, and a small screen on a band of other colour reads as cropped (2026-10-15: "take up basically the whole top half"). Owners: [`captures.md`](captures.md) § 3, § 4 and § 7.
- **L7. The face and the caption are sacred: nothing on the face or hair, no authored ink in the caption band. The graphic moves, never the face or the caption.** A real screen's page may run on under the caption box to the seam ([`captures.md`](captures.md) § 4). Why: a card on the hair reads as a mistake, and a caption that loses to a graphic stops being read. Owner: [`layout.md`](layout.md) § 8, The frame and its bands.
- **L8. Two textures: authored graphics are stepped 12 fps with bloom and grain on the near-black grid (or, when they depict a real product's UI, on that product's own field); real screens are smooth with a faint glow and scan lines. Every effect is barely there and judged at phone size.** Why: the texture tells "designed" from "real" at a glance. Owner: [`graphics.md`](graphics.md) § 7, Families and finish.
- **L9. Sound is the literal object on a visible event. The face, captions and exits are silent, and nothing plays over proof audio.** Why: a generic sound says "an animation happened", the literal one says "a phone was answered". Owner: [`sfx.md`](sfx.md) § 1, The law.
- **L10. The creator's hand is the truth and your pass is taste only: every objective defect is Claude's to find first.** Why: every defect you point at costs you a watch and a message, and every hand edit is the strongest taste evidence there is. Owner: [§ Working with the creator](#working-with-the-creator).

## Where each step lives

The preset says WHAT, [`LANES.md`](../../../LANES.md) says HOW per app, exactly as on long-form. Unlike the house's other short-form looks this preset reaches past step 5: it changes steps 2, 3, 4 and 6, which is why it is resolved at Step 0 and not at the graphics step.

### Step 0: this preset is resolved here

- **Which preset.** A single speaker explaining something to camera, for a short, with graphics asked for (a bare "edit this" on such a raw counts): this preset. A tool or system being demoed is the benchmark case; a concept, opinion, news or how-to explainer with no product gets the same preset with [§ No product on screen](#no-product-on-screen). "Hook card then raw", or a story with no graphics ask, gets [TikTok/raw](../../tiktok/raw/tiktok-raw-style.md).
- **Which raw.** A vertical raw, or a raw shot landscape for a short (the brief or the ask says short, reel or 9:16): the first short of this format was shot horizontal and cropped vertical (2026-09-17). The landscape frame is FILLED to 1080x1920 once for the whole take, centred on your shoulders and neck (the face where none are seen: [`layout.md`](layout.md) § 2), with no per-clip centring (same call), and that crop is the untouched W of [`layout.md`](layout.md) § 2. This overrides the house's auto-detect from the raw's aspect, so say it. A FINISHED long-form cut into shorts is still [`clipper`](../../../.claude/skills/clipper/SKILL.md), never this.
- **Write the call into RUN.md and state it in the report:** one word from the creator overrides it.
- **Then, before step 1:**
  - Find the brief: [`story-and-cut.md`](story-and-cut.md) § 1, the brief as spine.
  - Read from the brief (or your ask) whether an ad version is wanted. Sponsorship alone changes nothing: the second deliverable is made only when asked for ([§ Deliverables](#deliverables)). Ask once only when the brief names a sponsor and says nothing about deliverables.
  - Check whether you gave a music track ([§ Music](#music-opt-in)).
  - Check for a second voice through a speaker (an AI on a call, a phone, a played clip): it changes steps 2, 3 and the captions.
  - Write `projects/<job>/pii.json` before any take, camera-held screens included: [`edit-video`](../../../.claude/skills/edit-video/SKILL.md) § Step 0 item 9, [`captures.md`](captures.md) § 11, Privacy and staging.

| # | Step | WHAT (read this) | Tools | Lane HOW |
|---|---|---|---|---|
| 0 | Resolve | [§ Step 0](#step-0-this-preset-is-resolved-here) above | — | — |
| 1 | Intake | universal ([`CLAUDE.md`](../../../CLAUDE.md) § The Pipeline) | — | — |
| 2 | Rough cut | [`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md) + [`story-and-cut.md`](story-and-cut.md); write `transcript/voices.json` when a second voice is heard | `workflows/cut-audit.py --grid`, the lane's cut-proof | [`LANES.md`](../../../LANES.md) § step 2 |
| 3 | Audio | [`LANES.md`](../../../LANES.md) § step 3 + [§ Audio](#audio-step-3-addendum-what) below | `workflows/voice-gain.py`; its `--second-voice` for the gap and the lift (§ Audio) | [`LANES.md`](../../../LANES.md) § step 3 (the chain and the second-voice lift) |
| 4 | Grade | [§ Grade](#grade-step-4-default-on-this-format) below | — | [`LANES.md`](../../../LANES.md) § step 4 |
| 5a | Plan | [`graphics-plan`](../../../.claude/skills/graphics-plan/SKILL.md) + [`layout.md`](layout.md) (the layout map, first), [`graphics.md`](graphics.md), [`captures.md`](captures.md) (the capture list), [`captions-style.md`](captions-style.md) (the captions cell) | `validate-plan.py`, then [`layout.py`](layout.py) `projects/<job> --check` as its own gate | — |
| 5b | Build | [`graphics-build`](../../../.claude/skills/graphics-build/SKILL.md) + `kit/`: `kit/engine.py init`, `kit/engine.py stage` for every capture and brand mark ([`graphics.md`](graphics.md) § 15), then the job's `build.py` started from `kit/build.example.py` | `kit/engine.py`, `workflows/face-frame.py` (the measurements [`layout.md`](layout.md) § 2 and § 9 name), [`captions.py`](captions.py), the lane's layout keys | [`LANES.md`](../../../LANES.md) § step 5 (the layout keys, the placer) |
| 5c | Review loop | [`edit-review`](../../../.claude/skills/edit-review/SKILL.md); its reviewers read [§ First-pass ledger](#first-pass-ledger) as their conformance list | `workflows/graphics-qa-short.py`, `workflows/change-events.py --sync`, `workflows/pii-scan.py` | [`LANES.md`](../../../LANES.md) § step 5 |
| 6 | SFX | [`sfx.md`](sfx.md) + [`sfx.json`](sfx.json) | `workflows/sfx-plan.py` | [`LANES.md`](../../../LANES.md) § step 6 |
| + | Music | [§ Music](#music-opt-in) | [`background-music`](../../../.claude/skills/background-music/SKILL.md), with this preset's level | [`LANES.md`](../../../LANES.md) § Background music |
| 7 | Review | the live timeline, [§ Working with the creator](#working-with-the-creator) | — | — |
| 8 | Export | [§ Export](#export-step-8--what-app-independent) + [§ Deliverables](#deliverables) | the lane's export, `./finalize.sh <job> --apply --keep-drafts`, `workflows/flash-scan.py` on every exported file | [`LANES.md`](../../../LANES.md) § step 8 |

## What this preset changes in the house line

- **(a) The preset is resolved at Step 0, not at step 5.** It changes the cut, the audio, the grade and the SFX, so a step-5 decision would come three steps too late.
- **(b) `graphics-plan.json` carries a top-level `layout` array,** the one home of the footage framing ([`layout.md`](layout.md) § 12, The plan contract, which also fixes `preset` and `format`).
- **(c) Step 4 runs, on the camera footage** ([§ Grade](#grade-step-4-default-on-this-format)). The house calls the grade long-form-only; on this format the creator asked for it on both shorts.
- **(d) Step 3 adds the second-voice lift: applied when the gap is over 3 dB, and announced** ([§ Audio](#audio-step-3-addendum-what)).
- **(e) Step 6 reads this folder's [`sfx.json`](sfx.json)** (`sfx-plan.py` follows the plan's `preset`). The face-to-graphic cut-ins follow the layout map's switches and each kit component writes its own cues ([`sfx.md`](sfx.md) § 2 owns how both are written), so the first pass comes out in the creator's vocabulary instead of as hand rows.
- **(f) There is one tier.** "Do the graphics" on this format means this whole vocabulary: the layout rotation, real captures, the montage, the call card and full-screens within [`layout.md`](layout.md)'s caps. The full-screen seconds are stated in the plan summary, not asked for. There is no time budget (2026-09-21: "I don't care how long it takes"). Named looks elsewhere in the repo stay opt-in by name.
- **(g) Captions are built by [`captions.py`](captions.py), run from this folder**, never copied into a job.
- **(h) Live chat captures count as evidence here.** The house gate "text is never captured" yields where the product's own reply IS the proof: an agent answering is captured, not retyped ([`captures.md`](captures.md) § 1, Act as the film studio).
- **(i) A short with an ad version asked for ships two deliverables** from one edit ([§ Deliverables](#deliverables)).
- **(j) The format is the ask's, not only the raw's aspect:** a raw shot landscape for a short is this format ([§ Step 0](#step-0-this-preset-is-resolved-here)).

## No product on screen

The benchmark sold a product, so these docs speak in demos. A concept, opinion, news or how-to explainer keeps every law, the layouts, the captions, the textures, the sound, the grade and the deliverables; three things change. This variant is extrapolated from the principles and has not shipped yet: name it in the first report.
- **The proof is what the claim stands on, captured real:** the source page, a real result, a public artifact (a filing, a published chart, a post), your own screen. L4 holds as written: never an invented figure, chart or quote. A page quoted on camera is captured as the page it lives on, the cited passage whole, big and centred in the panel, hard cuts between passages and the source on screen, which is the house evidence-scene rule ([`creative-moves.md`](../../youtube/default/creative-moves.md) move 2, the evidence carve-out) inside the split panel. A quote with no page behind it is rebuilt word for word as a graphic (the house capture gate).
- **The hook lockup names the subject by its own mark** when it has one (a logo, an emblem, a flag). With none, the claim's object alone performs the claim: still one stack, still nothing that restates the caption ([`graphics.md`](graphics.md) § 5). `components.hook_stack` requires an icon today, so a mark-less hook is built as a job component with the kit ([`graphics.md`](graphics.md) § 15).
- **The skeleton is claim → reasons or steps → payoff → ask,** one beat per reason or step, each with its own proof. The demo slots of [`story-and-cut.md`](story-and-cut.md) § 2 keep their jobs where they fit: the first real evidence lands as early as the early live proof would, and the strongest reason takes the re-hook's place near the midpoint.

## Audio (step 3 addendum, WHAT)

The house chain is unchanged ([`LANES.md`](../../../LANES.md) § step 3: the measured gain onto −17 LUFS, into the −6 dBFS limiter, once, on every dialogue clip). The voice is never re-levelled by hand after it: the creator's final had zero dialogue level edits while you rode the music and every SFX by hand, which says the chain's voice is the voice you want.

**(a) A second voice through a speaker** (an AI on a call, a phone, a played clip) is lifted by default. Apply it and announce it; never ask first and never park it.
- Its spans are written on the RAW clock in `transcript/voices.json` at step 2, covering the whole reply the cut keeps. If a later hand cut keeps more of a reply, widen the span. The same file colours the captions.
- After the chain, measure the gap: the loudness of those spans against the host's kept speech. `uv run workflows/voice-gain.py projects/<job> --second-voice` simulates the chain offline on the kept spans (at the gain the lane recorded) and prints the gap, the lift and the headroom; the chained-dialogue bounce cut-proof already makes is the cross-check. Under about 3 s of kept second voice there is no measurement: the gap is unmeasurable, the lift is named by ear or not made, and RUN.md says which.
- If the gap is over 3 dB, lift those spans only: a level move AFTER the limiter (the limiter never sees it, so the phone is not squashed), 50 ms ramps inside the spans (the host is never lifted), the smallest whole dB that lands it within 1.5 dB of the host, no EQ, so it still sounds like a phone. The static chain itself is untouched: this is a level ride on top of it, never an effect inside it.
- Being after the limiter, the lift raises the spans' peaks by the same dB: it is capped where their true peak reaches −1 dBTP, and a capped lift is named in the report with where the phone lands. A named lift over that cap is the creator's call, never a default.
- HOW per lane, the proof included: [`LANES.md`](../../../LANES.md) § step 3 (the second-voice lift).
- Say it in one RUN.md line and one report line with the measured gap ("say drop the lift to revert").
- A timeline rebuild drops the lift: re-apply it and read it back, like the chain.
- WHY: in a demo the other side of the call IS the proof, and after the chain a small, far speaker sits about 5 dB or more under the close mic (4.8 on the benchmark). A viewer who strains to hear the other voice does not believe the demo.
- Provenance: proposed on the first short of this format and approved there ("go ahead"). On the benchmark it was offered three times, never answered, and the final shipped unlifted: an offered-and-parked lift is the anti-pattern this default exists to stop. The lift is computed from the CHAINED dialogue, never the raw or the final: the benchmark's gap read 6.1 dB on the raw, 4.8 after the chain (the limiter takes 1.3 dB off the host, nothing off the phone) and 4.3 on the final (the bed and SFX sit more under the phone); `--second-voice` gave +4 on the 4.8, landing 0.8 dB under the host (cap +5, lifted true peak −2.3 dBTP). Its RUN.md's "6 to 7 dB" was a mean-volume reading on the cut-proof bounce, not loudness: expect the tool's number.

**(b) A replaced line** (a re-record or a lip-synced pickup) must be inaudible as a replacement:
- Loudness-match it to the original sentence within 0.5 LU before any processing. Leave it alone if it is already within 0.3 dB.
- Join it in the room-tone dip before the first new word, with a 15 ms equal-power crossfade.
- Make the audio exactly the picture clip's length.
- Put the chain over its range, then require cut-proof exit 0.

**(c) Mix hierarchy:**
- Voice first. SFX transients may peak above the voice's −6 dBFS ceiling, up to about −0.3 dBTP, as long as nothing clips: that punch is what your hand-set SFX levels shipped with.
- No master limiter, no loudnorm, no reference-reel loudness target. The chain outranks any reference.
- Before shipping, locate every hot peak and confirm it is an SFX. A voice peak up there means a clip lost its chain: re-apply and verify.
- Shorts run at the house −17 LUFS, the same as long-form, never hotter (2026-09-24: Short 2 and the long-form are the standard; Short 1 shipped slightly louder and is not the reference).

## Grade (step 4, default on this format)

WHY: your face should look the same on your long-form and your shorts. You asked for the grade on both shorts of this format.

WHAT: exactly the house Look in [`presets/youtube/default/README.md` § Grade](../../youtube/default/README.md#-grade-pipeline-step-4--before-graphics-and-underneath-them). That section is the one home of the cube, the dials and the program-render proof; no number is restated here. This format adds four things:
- The grade layer is the SEQUENCE's own vertical size and runs from frame 0 to the last frame. Re-fit it on every end change and for every deliverable (a landscape donor layer does not cover a vertical frame).
- It sits under every graphic, patch and caption.
- It covers camera footage only: screen-recording FOOTAGE stays bare (the house lock).
- A patch laid above it (a privacy blur) is cut from the GRADED program, so its colour and framing match by construction. It goes stale on any re-grade, re-frame or re-cut underneath.

HOW: [`LANES.md`](../../../LANES.md) § step 4.

## Music (opt-in)

- **Only a track from the creator.** Never choose or generate one; with none given, write "Background music: not asked for" in RUN.md. The song sets the tone of the piece, so the creator picks it.
- **It is the house flat bed** ([`background-music`](../../../.claude/skills/background-music/SKILL.md)): it starts on the song's sustained entrance so the piece opens at full energy, no fade-in, no ducking, and a 2 s tail that ends on the last frame. It runs under everything, proof audio included: on the benchmark it played under the live call at the same level (L9's "nothing plays over proof audio" is about sound events; a flat bed is not one), which is one more reason the second-voice lift is on by default.
- **The level is set by the relationship, never by a copied dB:** the bed alone sits about 12 LU under the finished program. On a track, `bed_db = −29.5 − (the track's integrated LUFS over the used span)`, rounded to a whole dB. This number overrides the skill's house default (−20): pass it as the skill's `bed_db`, so `music-plan.json` carries it from the first lay.
- **Proof, in the right units:** −29.5 is a STEREO measurement of the bed alone. A lane's music-only bounce may fold down to mono and read lower (the Premiere lane's does: [`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md), next to the music bed), so compare a bounce only with a bounce in its own units.
- **The benchmark's worked result: −21 dB,** on a hot master (the used span at −8.3 LUFS). It is your hand level (2026-09-22; never reverted): you pulled the bed a notch under the house −20 once the dense SFX layer was on, so the bed is felt, not heard.
- **Where you name a point for the track's drop, the drop lands there,** with the bed still starting on frame 0: the
  in-point is the drop's attack (measured on the track's low band, where the bass jumps; no repo tool finds it yet)
  minus the cut's time, frame snapped, passed as `--source-in`, proven on the lane's music-only bounce (2026-10-15: "have the beat drop right at the point where I start going into it", the hook's hand-off into the body).
  A track with a drop and no point named: lay the sustained entrance above and offer that hand-off once in the report,
  naming the line and the in-point it would take.
- **Your hand ride of a dropped bed is a direction, not a number to copy** (2026-10-15: the intro lifted to −14 dB under
  the hook, the body at −23 against the formula's −21, a small ramp keyed). Lay the flat formula level; once you have
  ridden it, keep your clips and keys through every re-cut (trim only the tail and move its fade), and lean a notch
  under the formula when the body carries a dense SFX layer.
- **No evidence yet for a video that opens on proof audio instead of a talking hook, or that carries few SFX.** Keep the formula and the frame-0 start; any change (a later start, another level) is a named deviation in RUN.md for you to call.
- **Re-fit on every length change** and for each deliverable, keeping the level and the in-point. A bed is not rippled with the cut: left alone after a re-cut it runs past the new end and exports a black tail.
- **A laid level that differs from the plan is your edit.** Write it into `music-plan.json`, mention it once, never restore the house number over it.
- **Judging a track:** instrumental, driving, bass-forward, quiet from 300 Hz to 3 kHz (the speech band), with a clear drop to start on.

## Export (step 8) — WHAT, app-independent

**A short-form deliverable is ONE 1080×1920 file for Reels, TikTok and YouTube Shorts: H.264 High 4.2, CBR 14,
AAC-LC 320k 48 kHz, at the SEQUENCE frame rate** (researched and set by Claude on your delegation, 2026-09-26;
sources and proof: the engineering archive).
4:2:0, progressive, BT.709 tagged, limited range, closed GOP, moov at the front.

- **The ceiling is Meta's publishing API** (what schedulers and API posting use): at most 1920 columns, "VBR, 25
  Mbps maximum", **300 MB**. An in-app upload is not held to that spec, but Instagram re-encodes every upload, so a
  bigger file buys nothing and one file that fits both routes is the deliverable (2026-09-22). CBR 14 sits
  inside the 25 Mbps maximum; CBR, because VideoToolbox VBR undershoots its target.
- **So the bitrate is set by the DURATION, not by "quality":** CBR 14 until 14 would break 300 MB (about 2:48),
  then `video Mbps ≤ 2350 / seconds − 0.32` in whole Mbps (300 MB less 2 % for the container, less the AAC): 171 s
  → 13, 300 s → 7. The lanes pick it for you.
- **TikTok and Shorts take the same file:** TikTok accepts up to 4096 px and 4 GB but plays 1080×1920 H.265 at
  about 0.4 Mbps, so nothing above 1080 helps there.
- **A 4K vertical timeline (2160×3840) has a SECOND file, for YouTube Shorts only:** 2160×3840 at the long-form
  4K numbers ([`presets/youtube/default/README.md`](../../youtube/default/README.md) § Export: H.264 High 5.1, CBR
  50, CBR 80 above 30 fps). YouTube keeps 2160p and 1440p renditions of a 4K Short (measured); Meta's API refuses
  more than 1920 columns, so this file never goes to Reels or TikTok. It lands in `outputs/shorts/` and is finalized
  with `./finalize.sh <job> --variant shorts --apply`. A 1080×1920 timeline has the one file.
- **Audio stays AAC 320k** although Meta's API spec says 128 kbps: the repo never drops a voice below 256k, and an
  over-spec audio rate was not seen to fail (unproven on API posting: if a scheduler refuses one, that is the cause).
- **Frame rate: never resampled.** Meta's API takes 23–60 fps; its Help Center states a 30 fps minimum, which
  contradicts it; the API's range is the one the house holds to, and a 23.976 sequence is inside it.
- **"Full quality" on a short means THIS, never a landscape or YouTube preset** — the 2026-09-22 slip: a "full
  quality" draft went out through the landscape 2160p preset and came back pillarboxed.

A draft and the final use the same settings; a draft is just not `finalize.sh`'d.

Verified on the finished file with ffprobe (1080×1920, the frame count of the timeline, ≤ 300 MB), never from
the app's dialog. This section is the one home of these numbers; the HOW per lane (the export tool, its preset file) is [`LANES.md`](../../../LANES.md) § step 8.

- **TikTok/raw shares this section.**
- **Export only on your go.** The saved timeline is the review surface until then.
- **Export the organic first, then the ad, then make the organic sequence active again**, because lane scripts act on the active sequence.
- **Done means the FILE is proven:** released by the app, its size stable, its frame count equal to the timeline's, loudness and true peak read with every hot peak attributed, and its last frame looked at (a wrong-sequence export shows there first).
- **Then `uv run workflows/flash-scan.py <file> --expect projects/<job>` must exit 0 on every deliverable** (`--variant ad` on the ad): no single-frame flash, no double cut, every hard cut at an expected boundary.

## Deliverables

**No ad version asked for: the organic only.** No second keyword, sponsored or not.

**An ad version asked for: two deliverables from one edit.** They are the same video with a different ask: a paid ad carries a clickable link, so it ends on "click the link below"; the organic has no link, so a comment keyword converts.
- The AD is a clone sequence, identical to the organic up to the first word of the CTA sentence.
- Only the last V1/A1 clip, the CTA graphic, the CTA caption lines and the CTA sounds differ.
- It has its own EDL, transcript and caption render (`captions.py --variant ad`; the plan's `variants.ad`).
- The bed and the grade are trimmed to its end, with the music fade moved there.
- Parity is proven by readback before export, never assumed. The lane's mechanics: [`LANES.md`](../../../LANES.md) § step 8 and [`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md) (the Organic → AD copy).
- Any change before the CTA (your sound pass, a caption, a figure) goes onto both, and both re-export. An AD cloned before your sound pass and left alone would have shipped 9 stale sounds.
- The AD master lives in `outputs/ad/` (`./finalize.sh <job> --variant ad --apply --keep-drafts`), never loose in `outputs/`, where the finalizer would promote it over the organic.

**For every deliverable:**
- Every promote is `./finalize.sh <job> --apply --keep-drafts` (without `--apply` it only dry-runs): deleting drafts is your call. A draft made before a privacy fix is never shared.
- **Delivery, when you ask for it, is a script, never a browser upload:** copy each master (`cp`) into the delivery folder you name through its desktop sync mount (e.g. Drive for desktop), then `cmp` the copy against its master. The browser and a drive connector both cap around 10 MB and cannot carry a master (2026-09-22: "Just do it through code, through a script"). A preview you ask for goes the same way, at the § Export settings.
- The folder and file names are the client's convention, read from RUN.md or asked once, never invented (see [§ What never becomes a rule](#what-never-becomes-a-rule)).
- A revision overwrites the same filename, so shared links keep working. Any timeline change after export makes every final stale: say so.

**A changed CTA word** (a new keyword, a new ad line):
- Never a voice clone, never a one-word splice: either sounds pasted into the punchiest slot of the video.
- Search the raw for a stressed instance of the word in a matching context first. If there is none, you re-records the whole sentence at the same distance and energy.
- Lip-sync it from the full-resolution raw, starting on the original clip's own first frame (`workflows/sync-so.py`), and lay it at raw geometry with the replaced clip's own framing keys. A lip-sync made from a pre-cropped window jumps at the cut.
- **The source is near-lossless:** libx264 at CRF 10 to 12, the exact frame count, its first frame proven by PSNR against the raw at ±1 frame (2026-09-22: "give me the highest quality possible file").
- **QA the mouth before it is laid** (2026-09-22: "check frames for mouth artifacts"): a mouth contact sheet across the changed words; a source-vs-output difference map read on the lower face, where a faint generator watermark shows and nowhere else; any occluder near the mouth (e.g. a mic arm) compared against a control region; output audio lag 0 ms. WHY: the generator only redraws the mouth, so every artifact it can make lives there, and a sheet of whole frames at thumbnail size hides it.
- Hold the new-word graphic and captions until that audio is laid, so the picture never says one word while the voice says another.
- Rebuild everything keyed to the word from source: the transcript, the captions, the typed keyword, the SFX anchor, and the grade and music extents.
- Prove it with cut-proof, and with `workflows/framing-continuity.py` exit 0 at both cuts.

## Definition of done

The objective bar before step 7. Each item names its proof; "looks fine" is not one.

1. **Cut:** `cut-audit.py --grid` clean; the lane's cut proof exits 0 where LANES.md § step 2 lists one (on a lane without one, checked by ear and recorded in RUN.md as unverified); every brief beat mapped to a take; missing beats flagged as pickups.
2. **Audio:** the chain read back on every A1 clip; the second-voice gap and decision written in RUN.md; the lift read back.
3. **Grade:** verified on a program render at several points, not from an effect readback.
4. **Plan:** `validate-plan.py` green (it runs the layout gate on the organic and on every `variants.<name>`); `layout.py projects/<job> --check` 0 FAIL, and `--variant ad --check` 0 FAIL when there is an ad; every WARN answered in the plan summary.
5. **Framing:** the S/T/W transforms, the collar and every card's crown measured on this shoot as [`layout.md`](layout.md) § 2 and § 9 say, never typed from another job; the split spans proven on the render (`face-frame.py --verify`); the lane's layout keys verified where LANES.md § step 5′ lists a readback (on a ⛔ or ⚠️ lane without one, done by hand, checked on a program render and recorded in RUN.md as unverified); `framing-continuity.py` exit 0 on every substituted clip; every lip-synced clip passed the source and mouth QA in [§ Deliverables](#deliverables).
6. **Graphics:** `graphics-qa-short.py` green, and `--variant ad` on the ad's placement; `change-events.py --sync` within its ±0.10 s tolerance (2.4 frames at 23.976, 3 at 29.97), or the kit's one designed lead (`VALUE_KEY_LEAD_S`) recorded as `sync_offset` on its sfx-hand row, never an unexplained offset (how kit anchors are read: [`graphics.md`](graphics.md) § 15 6b); every capture passes the three tests (whole, centred, readable) plus the story test (it shows what the line says, in reel order); containers contain their contents; paired marks are equal on the render; no in-graphic text restates the caption; `pii-scan.py` sweeps clean on every take and every render.
7. **Captions:** the [`captions.py`](captions.py) gate exits 0, and a few program frames per layout have been looked at.
8. **SFX:** planned from the placed graphics with no unanswered warning; placed and read back with zero missing, extra or drifting cues.
9. **Review loop:** `edit-review` ran its one review round, every verified finding fixed and the gate green on the changed graphics. Say so if a finding was left open.
10. **Request:** every request line in RUN.md has its evidence.

## Working with the creator

This process is part of the quality: each rule below exists because skipping it cost a round.
- **Pilot a new look on ONE scene and show it.** Then build one graphic at a time, each finished before the next. A class of defect shows up once in a pilot instead of twenty times across a finished pass.
- **A change that touches every instance** (the backdrop, grain, glow, the caption height or box) **is previewed first, current beside proposed, and approved before the timeline changes.** For a backdrop: a bare backdrop mp4 (grain and drift only show in motion), a still and a phone-size copy. For captions: the still test ([`captions-style.md`](captions-style.md) § 3). A still costs seconds; a wrong global change costs a re-render of every scene.
- **State offsets from the physical reference, never from the last test** ("box top 40 px under where the collar meets the skin"). A relative note read against the wrong baseline cost a round.
- **"Slightly" is one notch, about 15 to 20 %.** A placement note is never a redesign.
- **A note on one graphic's crop, fill or size is a note on every graphic of that kind** (2026-10-15: "for all
  of the crops, really"). Re-check every capture in the reel against it before showing the fix.
- **An authored scene keeps its composed size, even when the captures around it fill the panel.** A tile field taken
  full bleed was reverted ("looks kind of bad... go back to how it was before", 2026-10-15) and had broken the push into
  the next graphic. Filling the panel is the real screens' rule (L6).
- **"Go back to how it was before" is the approved version exactly,** re-rendered from its own source and proven
  identical, with every sound it carried put back at its old frame; never a third version.
- **When the proof needs an artifact you do not have yet** (the site the video says you set up, the checkout, the doc),
  it is made for real, on your accounts and with your go, before its capture; a parallel session can build it while the
  edit goes on. Until it exists the cell is a named placeholder in RUN.md, never a stand-in that ships.
- **The saved timeline is the review surface.** No draft exports unless you ask: a draft is stale the moment you edit, clutters `outputs/`, and can carry content later redacted. A QA-only draft that a tool needs (e.g. the framing proof of a substituted clip) is exported with the graphics off and never shown or shared.
- **Your hand edits are kept and reported once, never restored.** When a graphic that one of your sounds sits on moves, report the measured shift and let you move the sound.
- **Before your sound pass, every library sound is one drag away** ([`sfx.md`](sfx.md) § 7, Library hygiene).
- **Each fix of a recurring defect class adds an assertion,** proven failing on the old render first. A check believed on its first "clean" was blind five times on the benchmark.
- **Say which on-screen words are Claude's** (a folder title, a button label) so you can change them.
- **Parallel sessions split tracks, serialise every write, and stop messaging once the shared work is done.**
- **Three defaults go past what you ruled on: apply each and name it in the first report, so one word reverts it.**
  - The second-voice lift ([§ Audio](#audio-step-3-addendum-what) (a)).
  - The organic staying split into the CTA ([`layout.md`](layout.md) § 7): you said it about the ad, in the same message that approved an organic still carrying a 0.9 s wide hop on its lead-in.
  - The no-product variant ([§ No product on screen](#no-product-on-screen)).

## First-pass ledger

What this preset exists to stop, and the ONE list of it: each doc keeps its in-section "Rejected" lines, and this ledger gathers them (the per-doc anti-pattern sections were folded in here on 2026-09-23). [`edit-review`](../../../.claude/skills/edit-review/SKILL.md) class 8 reads this list as its conformance check. One line each: the defect, the fix, the owner.

- **Word cards** restating the line → enact it with an object, UI or a state change; the caption carries the words. [`graphics.md`](graphics.md) § 1, The two laws.
- **A hook chip restating the caption** → the hook lockup only: the real mark, the name, the claim's object. [`graphics.md`](graphics.md) § 5, The hook lockup.
- **Captures small, cut off or off-centre** → lay the source out for the panel before the take, frame by the rectangle that must be whole. [`captures.md`](captures.md) § 2 and § 3.
- **Captures floating on the backdrop** → no backdrop behind a capture: the panel is the capture's own colour, sampled off the render. [`captures.md`](captures.md) § 4, One screen.
- **Jump-cut recordings** → the app's own motion at 1x; only proven-static waits and your own input the line has passed are skipped. [`captures.md`](captures.md) § 5, Natural movement.
- **A pop or push on a static page** → the cut is its entrance; only the page's own motion, a rendered zoom onto a named figure or a doc's scroll moves. [`captures.md`](captures.md) § 5 and § 8.
- **3D on anything the viewer must read** → flat, whole, static; tilt belongs to the glance montage only. [`captures.md`](captures.md) § 7, Read vs feel.
- **The caption moved to make room for a graphic** → lift, shrink or reframe the graphic; the caption keeps its band. [`layout.md`](layout.md) § 8.
- **5 s of bare wide face after the hook** → the promise line punches in tight; bare wide stays short. [`layout.md`](layout.md) § 3 and § 6.
- **An empty panel before its first element** → hold the lead-in on the face and cut to split on the word the first element lands. [`layout.md`](layout.md) § 4, Where a switch lands.
- **A card sitting on the hair** → its bottom edge above the tallest crown across its whole span, entrance included. [`layout.md`](layout.md) § 9, Card clearance.
- **Headers in the top 200 px** → key content inside the safe band, first frame of every entrance included. [`layout.md`](layout.md) § 8.
- **Generic class sounds instead of the literal object** → sound the device, material or action on screen. [`sfx.md`](sfx.md) § 1, The law.
- **A silent graphic in a sounded reel** → a new graphic ships sounded, in the reel's own vocabulary. [`sfx.md`](sfx.md) § 1, law 17.
- **The SFX plan re-applied over your sound pass** → diff first; your timeline is the truth; snapshot the audio around every write. [`sfx.md`](sfx.md) § 6.
- **A wide hop into the CTA** → stay split and push from the last graphic into the CTA. [`layout.md`](layout.md) § 7, The CTA stays split.
- **An exit on the last graphic** → the last graphic holds through the final frame. [`graphics.md`](graphics.md) § 6, The CTA enactments.
- **Smooth-rate authored graphics** → authored scenes step at 12 fps with bloom and grain; captures stay smooth. [`graphics.md`](graphics.md) § 7.
- **The navy backdrop** → the near-black grid backdrop. [`graphics.md`](graphics.md) § 8, The house backdrop.
- **The old 4-7 card basic tier** → one tier, the whole vocabulary, the layout rotation included. [§ What this preset changes](#what-this-preset-changes-in-the-house-line) (f).
- **A review draft exported every round** → the saved timeline is the review surface; export on your go. [§ Working with the creator](#working-with-the-creator).
- **A caption word dropped** → captions equal the transcript word for word, asserted by the gate; a one-word sliver is re-homed, never deleted. [`captions-style.md`](captions-style.md) § 4 and § 5.
- **A caption line crossing a picture cut** → break at every V1 cut, framing change and graphics cut, on the cut frame (a montage's own shots excepted). [`captions-style.md`](captions-style.md) § 5.
- **A lip-sync made from a pre-cropped window** → generate from the full raw from the original clip's first frame, lay at raw geometry, prove with framing-continuity. [§ Deliverables](#deliverables).
- **A lip-synced clip laid without looking at the mouth** → the source and mouth QA before it is laid. [§ Deliverables](#deliverables).
- **A chat scene opening on older, unrelated history** → open on the exchange the line is about; hide the history above it. [`captures.md`](captures.md) § 6, Chat framing.
- **The grade skipped as "long-form only"** → the grade runs on this format's camera footage. [§ Grade](#grade-step-4-default-on-this-format).
- **A bed or grade layer left running past a new end** → re-fit both on every length change and per deliverable. [§ Music](#music-opt-in).
- **A bed level copied from another track** → set it from the track's own loudness, proven in the right units. [§ Music](#music-opt-in).
- **A second-voice gap flagged and parked** → apply the lift when over 3 dB, and announce it. [§ Audio](#audio-step-3-addendum-what).
- **A video with no product forced into the demo skeleton** → the no-product variant. [§ No product on screen](#no-product-on-screen).
- **A random example page standing in for your own** → your real one, built first if it does not exist yet. [`captures.md`](captures.md) § 1.
- **A capture small on another colour's band, cut short of the caption, or one fill for every shot** → the page fills the panel to the seam (`under_caption`), each shot on its own `bg`. [`captures.md`](captures.md) § 4.
- **An app's auto zoom on a figure** → a rendered zoom, straight, fast and blurred, from the first frames. [`captures.md`](captures.md) § 5.
- **The hook take kept by the last-take rule when it sounds flat** → the most expressive complete take. [`story-and-cut.md`](story-and-cut.md) § 4.14.
- **Progress recaps, optional asides and hype lines kept** → cut. [`story-and-cut.md`](story-and-cut.md) § 4.15.
- **A sponsor's brand coloured in the captions** → white, whatever the brief asks. [`captions-style.md`](captions-style.md) § 1.
- **A money moment left silent, or sounded as a chime** → the cha-ching, a run of them cutting each other off. [`sfx.md`](sfx.md) § 4, rung 14.
- **The split face raised to keep the chin up, or centred on a leaning head** → the hair 100 px under the seam, the shoulders and neck on the centre line. [`layout.md`](layout.md) § 2.

The frame ([`layout.md`](layout.md)):
- **Overlays stacked on long face shots** → add picture changes, not overlays. § 1.
- **T punch-ins on list and naming lines** → naming lines are split graphics; T is for opinion and emphasis. § 3.
- **A face flash under 0.6 s between two graphics, or a W lead-in on a sentence whose subject is the graphic** → § 3, rules 7 and 10.
- **A live call held on its card past the screen its result lands on** → cut to that screen (§ 3, rule 3a).
- **A 2-frame overlap at a same-slot swap, a graphic over the lead-in words, a switch on the bare noun (a one-word caption sliver)** → hand off on one frame, on the subject's first word. § 4.
- **Ramped framing between modes, or the long-form zoom-out and push-ins** → hard cuts only. § 5.
- **A spill into the caption band waived as "the look"** → the sides may spill, the band never. § 8.
- **The hair top 50 px under the seam** → 100 px: the caption box sat on the hair. § 2.
- **The hook caption parked under the hook title** → lift the visual; the caption keeps the seam. § 6.
- **A tight punch-in under an overlay card** → never T under a card. § 9.
- **A content graphic held over the ask's first words, or the promised page slid in** → § 7, § 5.

The panel ([`graphics.md`](graphics.md)):
- **An invented frame around a real mark, or marks sized by canvas** → the mark bare, sized by its solid body. § 12.
- **Scan lines on the grid, or a backdrop brighter than the dark apps beside it** → § 7, § 8.
- **An effect so subtle it averages away, or one past the ceilings** → § 9.
- **A content graphic hanging into the CTA** → § 6.
- **Drawn stand-ins for real deliverables, platform colour on the creator's side of a thread, authoring what the product can show** → § 2, § 10.
- **An element outside its container "measured" by eye; empty plates, doubled or orphan frames, overlapping tweens; hand-placed scatter positions** → § 14.
- **A lone element held for seconds, or one graphic held 10–15 s through several named things** → § 13, § 16.
- **A scene that spoils a later payoff or opens mid-exchange** → § 4.
- **Key-shaped lines, vendor names or real paths in fake code** → § 12.
- **One device built twice in a passage, a burst of ghost elements on "et cetera", a described call left as a silent UI beat** → § 3.
- **Everything lifted from a reference reel** (its stock b-roll, actor cutaways, glitch transitions) → only its layouts, cadence and one-title-card rule were adopted. § 1.

The captures ([`captures.md`](captures.md)):
- **Hand-typed or clamped zooms; crops keeping a window border, a corner or a too-short header; estimated board rows** → frame by the measured rectangle. § 3.
- **A fill sampled from the source file** → sample the render. § 4.
- **A card re-cropped at every reply, a reply shot starting before its landing, a tooltip flash played through, normal app behaviour painted out** → § 5, § 6.
- **Empty chat before the first keystroke, your prompt replayed and zoomed out to fit a long reply, invented name cards** → § 6.
- **Montage shots as tilted cards on the grid** → one big flat screen, fill inside the plane. § 7.
- **A shot that falls between a page's own motion** → § 8.
- **Staging text typed into a filmed chat; a sensitive card framed out while it stays in the asset; a static blur over a moving phone; "OCR reads nothing, so leave it"** → § 11.
- **A headless recording that shows the page's automation fallback** → § 2.

## What never becomes a rule

- **Per-shoot measurements** (the face, the collar and crown lines, fill colours, window sizes, caption heights) are re-measured on every job.
- **The cast, brands, keywords and deliverables** are per video. The editor never picks a keyword on its own authority.
- **Delivery names and folders** are one client's convention (e.g. one numbered folder per piece, an "Organic Post" and an "Ad Version" file), never a house scheme.
- **Counts, timestamps and shares are outcomes, not targets:** the benchmark's number of graphics, cues, rounds, its runtime, its kill rate and its −21 dB bed describe one video.
- **A device seen once** (a J-cut, a cash register on a price, a capability hub) is a taste signal to consider, never a mandate.
- **The benchmark's own specifics** sit in one closing section per doc, each a calibration the rules above cite, never a value to copy: [`layout.md`](layout.md) § 16 (the calibration face and its per-shoot Motion values), [`graphics.md`](graphics.md) § 17 (the cast, fills, lockup sizes), [`captures.md`](captures.md) § 13 (the shoot's captures), [`story-and-cut.md`](story-and-cut.md) § 8 (the script's lines).

## Files here

- [`story-and-cut.md`](story-and-cut.md): the story and cut taste of this format (the brief as spine, the skeleton, keeps and kills, joins, your hand cut, the ending and the ask). Steps 2 and 5a.
- [`layout.md`](layout.md): the frame (the five layouts, picking one per sentence, where a switch lands, bands, card clearance, the plan's `layout` contract, cadence).
- [`graphics.md`](graphics.md): what goes in the panel and how it looks and moves (families, backdrop, palette, type, motion, the hook and CTA, density).
- [`captures.md`](captures.md): the real-screen proof (shooting for the 9:16 panel, framing, fills, natural movement, chats, the montage, privacy and staging).
- [`captions-style.md`](captions-style.md): the locked caption layer (look, heights per layout, breaks and holds, the gate).
- [`sfx.md`](sfx.md): this format's sound design, written so the first pass starts where your hand pass ended.
- [`sfx.json`](sfx.json): the planner's sound map for this format, read by `sfx-plan.py`.
- [`layout.py`](layout.py): the executable twin of `layout.md`; its `--check` is the 5a layout gate, and `captions.py` and the lane's layout keys import it.
- [`captions.py`](captions.py): the caption builder and its gate, run from this folder.
- [`kit/engine.py`](kit/engine.py): job init, the frame-grid clock and word anchors, capture geometry, the scene emitters, comp writing with asserts, SFX rows, the render wrapper.
- [`kit/components.py`](kit/components.py): the recurring authored components, each timed from words and carrying its own SFX events.
- [`kit/build.example.py`](kit/build.example.py): the job `build.py` template; the editor edits only its storyboard list.

Retired on 2026-09-23 and never planned or built from: the word-pop caption builder `build.py` and the overlay-tier docs `default-overlay-style.md` and `signature-style.md` (replaced by `captions.py`, `layout.md` and `graphics.md`).
