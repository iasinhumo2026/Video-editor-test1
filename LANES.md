# LANES — which app can do which step, and where the recipe lives

**The law this file enforces: the PRESET says WHAT, the APP SKILL says HOW.**

A preset is a LOOK: every number in it (a frame count, a scale %, a hex, a dB, a duration) means the same in every
editor, and every graphic it specifies is a HyperFrames render any NLE can take. So the preset never carries app
mechanics and an app skill never carries look decisions, which is what makes ONE preset produce the SAME video on any
lane. Placing an alpha mov at a timecode is identical on every preset, so written once in the app skill it serves every
preset, and a new preset inherits every lane for free.

**This file is the index that connects them.** At step N on lane L, read the preset's § step N for the target, then
this file's row N for where lane L's mechanics are.

## Where the lanes live

**Every app-specific file is under [`lanes/`](lanes/README.md), one folder per finish surface** (`premiere/`, `resolve/`, `capcut/`, `chat-only/`, `finalcut/`; since 2026-09-03, Final Cut 2026-09-25): scripts, templates, lane sheets and each lane's `lab-notes.md` (the locks true only on that app). The app skill in `.claude/skills/` is the lane's HOW doc; `workflows/` holds only universal utilities. "Is step N defined and done" is answered by `CLAUDE.md` § The Pipeline and `projects/<job>/RUN.md`; "does app X have a recipe for step N" here and in `lanes/<app>/`. Never let the second leak into the first (chat-only having no grade stage is a lane fact, not a pipeline fact).

## How to read a cell

| | |
|---|---|
| ✅ | **Scripted and validated.** A command or an API call exists and has been run on a real job. |
| ✋ | **Manual, by design.** Nothing to script, or the creator owns it. Do it by hand from the preset's numbers. |
| ⚠️ | **Unvalidated recipe.** The mechanism is documented and consistent with what is known, but no job has run it. Treat the first run as a test: verify by measurement, then upgrade this cell. |
| ⛔ | **Gap.** No recipe. Do it by hand from the preset's numbers and **say so out loud** — see below. |
| — | **Nothing lane-specific.** The step is universal; the lane changes nothing about it. |

**If an app skill's STEP INDEX disagrees with this matrix, this matrix wins.**

**TikTok/raw carries only step 5, captions included:** a LOOK for the graphics step (the hook card and
its caption layer); every other step takes the universal target stated in this file's step rows. **The
Talking Head Explainer (`instagram/talking-head-explainer`) reaches further**, and its
[README](presets/instagram/talking-head-explainer/README.md) § Where each step lives is the index: step 2
taste ([`story-and-cut.md`](presets/instagram/talking-head-explainer/story-and-cut.md)), a step-3 addendum
(the second-voice lift), step 4 (the grade on its camera footage), the step-5 footage layout keys (row 5′
below), its own step-6 map ([`sfx.json`](presets/instagram/talking-head-explainer/sfx.json)) and a music
level. Its WHAT stays in the preset; the HOW per lane stays here.

## The matrix

Steps are CLAUDE.md § The Pipeline; lanes are the five finish surfaces. **Premiere and CapCut run on macOS and Windows** (every lane script and helper, since the Windows port of 2026-09-27; backends `lanes/premiere/premiere_win.py` and `lanes/capcut/capcut_win.py`), **Resolve and chat-only on macOS, Windows and Linux**, and **Final Cut on macOS** through SpliceKit (`./setup-finalcut.sh`; in the author's repo `packaging/overlay/setup-finalcut.sh`): `lanes/finalcut/replay.py` builds a fresh job's whole timeline from its pipeline files (proven 2026-09-25 on a Talking Head Explainer and a long-form with a section, clip for clip against their Premiere projects); what the files do not carry (a hand-laid patch, a hand Motion) it cannot rebuild, so the run says so.

| # | Step | Premiere | Resolve | CapCut | chat-only | Final Cut |
|---|------|----------|---------|--------|-----------|-----------|
| 1 | Intake | — | — | — | — | — |
| 2 | Rough cut → replay | ✅ | ✅ | ✅ | — | ✅ |
| 3 | Audio polish | ✅ | ✅ | ✅ baked | — baked by splice | ✅ baked |
| 4 | Color grade (long-form + Talking Head Explainer) | ✅ | ⚠️ | ⛔ | ⛔ | ✅ |
| 5 | Graphics | ✅ | ✅ | ✅ | ✅ | ✅ |
| 5′ | Footage layout keys (Talking Head Explainer) | ⚠️ | ✅ | ✅ | ⚠️ | ✅ |
| 5″ | Own B-roll cutaways (a preset with a `broll.json` only, `broll-own`) | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ |
| 6 | SFX | ✅ | ⚠️ 21.1+ | ⛔ plan only | ⚠️ | ✅ |
| 7 | Review | ✋ | ✋ | ✋ | ✋ | ✋ |
| 8 | Export | ✅ on the creator's go | ✅ | ⚠️ | — the render IS the file | ✅ |
| + | Background music (opt-in) | ✅ | ⚠️ 21.1+ | ✋ audio track | ✅ | ✅ |

### Where each cell's recipe lives

**Step 1 — Intake.** Universal: copy (never move) into `projects/<job>/raw/`. No lane involvement.

**Step 2 — Rough cut, then the EDL replay.** The cut itself is universal (`rough-cut`: WhisperX,
kill, splice `RENDER=0`). Only the replay is per-lane, and all four apps rebuild the same
`transcript/cuts.json` as separate trimmable clips. **On long-form the main sections are
colour-labelled at the replay, every time (2026-09-19)** (intro, each body section, outro),
and every clip laid later carries its section's colour: the labels are how he reads the timeline.
Premiere mechanics: `premiere-pro` § Colour labels.

- Premiere ✅ `node lanes/premiere/premiere-bridge.mjs replay …` — `premiere-pro` § Step 2. Every cut gets `uv run workflows/cut-audit.py <job> --grid <sequence rate>` BEFORE the replay and `--live` after it (a mixed-rate source, e.g. a 30 fps screen recording on 23.976, is why: Premiere floors twice), and the cut is done only when `uv run lanes/premiere/cut-proof.py <job>` exits 0 (the bounced timeline transcribes to the script) — `rough-cut` § Audit the cut on the finish surface's grid · § The proof
- Resolve ✅ `uv run workflows/cut-audit.py <job> --grid <timeline rate>` before the replay, then `AppendToTimeline` in `run_script` (Blackmagic's `ResolveMCP`), one call per track — `davinci-resolve` § Step 2
- CapCut ✅ `uv run workflows/cut-audit.py <job> --grid <draft rate>` before the replay, then `uv run lanes/capcut/capcut-bridge.py replay <job>` — `capcut` § Procedure 2
- Final Cut ✅ `uv run workflows/cut-audit.py <job> --grid <timeline rate>` before the replay, then `uv run lanes/finalcut/replay.py projects/<job>` (the whole timeline from the job's and its sections' files as FCPXML, a NEW library per rebuild so a hand edit in the old one stays) → `import.py` (proven clip by clip) — `final-cut-pro` § Procedure. A finished Premiere sequence ports instead with `lanes/finalcut/prproj-read.py` → `port-premiere.py`
- chat-only — no replay; `splice.sh` renders the flat cut, on the SECOND splice after `polish-boundaries.py` (the first runs `RENDER=0` on every lane) — `rough-cut` § Polish the boundaries

**Step 3 — Audio polish. This section is the ONE home of the universal audio target.** One static
pass over the whole timeline, never dynamic loudnorm, never per-segment gain, re-applied after any
timeline rebuild (a rebuild discards clip effects). The house chain:

    gain = round(−17 − measured)  →  hard limiter at −6 dBFS

`uv run workflows/voice-gain.py projects/<job>` measures the raw's KEPT speech ranges
(`transcript/cuts.json`, ebur128 — never the whole take, dead air drags the number down) and returns
the whole-dB gain onto **−17 LUFS integrated pre-limiter**; a quiet shoot gets more, a hot shoot
less. The limiter is FIXED at **−6 dBFS**, so peaks land about 8 dB over the ceiling and it works
every stressed syllable — that saturation is the point (2026-09-03, calibrated on
`your-job`).

**A NAMED gain is the user's call and nothing else (2026-09-19).** `--gain` on `audio-polish.py` and
`AMPLIFY_DB` on `splice.sh` override the locked measurement, so a measurement that FAILS is fixed at
`voice-gain.py`, never worked around with a number — and any named gain is stated in the report and
written into RUN.md as a deviation.

**A section that plays back an already-mixed video is measured in two parts (your-job, 2026-09-28).** A
live demo that ends by playing its finished result through the speakers kept 92 s of that mix, and the section's
measurement fell from +8 to +3 dB: the mix is 7 dB hotter than the host's voice and outweighs it. So the host's
kept speech and the playback are each measured on their own sub-EDL (`voice-gain.py <section> --edl <speech-only
cuts.json>` and `--edl <playback-only cuts.json>`), and each measured gain goes on its own clips with
`audio-polish.py --gain N --range FROM TO` (+10 on the voice, +1 on the playback there). The record says `named`,
but the number is voice-gain's own measurement on that part, so RUN.md records the sub-EDL rather than a deviation.

- Premiere ✅ `uv run lanes/premiere/audio-polish.py projects/<job> --apply`: the measured Amplify + Hard Limiter as clip effects on every A1 clip; a bare `--verify` holds each clip to the latest gain an `--apply` recorded over it (`premiere/audio-polish.json`: named and per-section `--range` gains included) — `premiere-pro` § Step 3
- Resolve ✅ the same chain, baked into the media (its API has no limiter): `workflows/normalize-sections.sh` takes the `voice-gain.py` gain and the −6 dBFS limiter to each source file, and the timeline is LAID from `audio-normalized/` (proven frame-identical to the raw replay, 2026-10-13). ⛔ Never `ReplaceClip` under a clip whose FPS was set (every iPhone take); `replace-clips.py` is only for a clip Resolve ingested at its nominal rate — `davinci-resolve` § Step 3 → [`lanes/resolve/resolve-audio-polish/`](lanes/resolve/resolve-audio-polish/README.md) (house numbers since 2026-09-04, the user's call)
- CapCut ✅ baked into the SOURCE, the Resolve route: `workflows/normalize-sections.sh projects/<job>` (the measured gain into the house limiter, video stream-copied, its drift gate), then `replay <job> --media projects/<job>/audio-normalized` (a folder stands in for every raw by name; a file for a single-raw EDL). Proven on Windows 2026-09-27 (export −17.8 LUFS, peak −5.5) — `capcut` § Step 3
- Final Cut ✅ baked, the Resolve route: `workflows/normalize-sections.sh` → `audio-normalized/`, which `replay.py` lays (a mono clip given back Final Cut's 6 dB split, `lanes/finalcut/lab-notes.md` § 16); the Talking Head Explainer's second-voice lift as dialogue volume keys after the baked limiter (`--lift N` names it) — [`lanes/finalcut/README.md`](lanes/finalcut/README.md) § The steps
- chat-only — `splice.sh` already bakes the identical chain into the render

**The second-voice lift (the Talking Head Explainer's step-3 addendum; WHAT: its [README](presets/instagram/talking-head-explainer/README.md) § Audio).** Premiere ⚠️ `uv run lanes/premiere/audio-polish.py projects/<job> --lift auto` (after `--apply`; `voice-gain.py --second-voice` decides at the recorded gain, capped at −1 dBTP; the lift is a second Amplify AFTER the Hard Limiter, never Volume > Level, which Premiere runs before the limiter; a bare `--verify` reads the keys back, `--bounce` proves the level); Resolve / CapCut / chat-only ✋ by hand, a level ride AFTER the limiter on the `transcript/voices.json` spans. The Premiere lift is proven live on a stereo and a mono clip in a throwaway project, the ramps, their 20 ms lead and `--bounce`'s two-bounce proof included (2026-09-24); it becomes ✅ after its first real job. A timeline rebuild drops the lift: re-apply and prove it.

**Step 4 — Color grade (long-form and the Talking Head Explainer's camera footage).** Target (universal): the footage carries the look and **the
graphics carry none of it**, established before a single graphic is placed. The cube and the dial
values are the preset's: [`presets/youtube/default/README.md`](presets/youtube/default/README.md)
§ Grade. Only WHERE the separation lives is per-lane — a track on one app, a grouping on another.

- Premiere ✅ [`lanes/premiere/premiere-grading.md`](lanes/premiere/premiere-grading.md) — `grade-layer` builds the V2 adjustment layer, `grade-lut.py apply` writes the Look. Fully hands-off, except that a later screen-recording section needs the `GRADE` clip trimmed back to the camera footage (`premiere-grading.md` § 1).
- Resolve ⚠️ the SEPARATION needs no track shuffle (a color group covers only its members, so the footage joins it and the graphics track does not), and the house look goes on the group's post-clip node as ONE cube with the two Lumetri dials folded in (`fold-look.py`; measured within 1–2 / 255 of Lumetri on the Resolve lane test, 2026-09-25, ✅ after its first real job) — `davinci-resolve` § Step 4, mechanism playbook in [`lanes/resolve/resolve-grading/`](lanes/resolve/resolve-grading/README.md)
- CapCut ⛔ no LUT surface in the bridge. Hand-apply a filter in the app, or accept an ungraded cut and say so.
- Final Cut ✅ no adjustment layer exists: every camera-footage clip carries Custom LUT → the folded house cube (a captured template, `lanes/finalcut/lab-notes.md` § 6), the graphics lanes nothing; `replay.py` grades the plan's `graphics_scope` ranges, or `--grade-ranges`, else all of V1
- chat-only ⛔ the ffmpeg assemble lane has no grade stage.

**Step 5 — Graphics.** The graphics themselves are universal in the strongest sense: they are
rendered by HyperFrames into files (alpha ProRes 4444 for overlays, opaque mp4 for full-screens)
before any lane is involved. Plan with `graphics-plan`, build with `graphics-build`, converge with
`edit-review` — none of those three is lane-aware. Only PLACING a file and BAKING a footage move
are per-lane.

**The caption layer is part of this step (2026-09-04).** On the short-form presets the plan carries a `captions` cell and the preset's caption builder emits a straight-alpha ProRes 4444 (`hf-graphics/captions/renders/captions-alpha.mov`, no flat render needed); the lane's placer lays it on the top graphics track like any other overlay, spanning the whole cut (Premiere: V5, provisioned by `place-graphics.py`; Resolve: the highest video track, `AppendToTimeline` like any overlay; CapCut: `add-overlay` on the top layer, **premultiplied first** like every CapCut-bound alpha mov; chat-only: the last overlay in the assemble). Nothing burns captions after the render, on any lane. Long-form has no caption layer. **The short-form track map on Premiere:** V1 footage (the Talking Head Explainer's layout keys ride its Motion) · V2 grade (the Talking Head Explainer; empty on TikTok/raw) · V3 graphics · V4 overlaps and privacy patches · V5 captions.

**Own B-roll cutaways (`broll-own`, only on a preset built for B-roll: its folder holds a `broll.json`; no shipped preset carries one).** Universal: `workflows/broll-place.py apply` writes each as a `b-roll` cell with `broll_source` and conforms it to an opaque mp4 at `hf-graphics/gfx/renders/<id>.mp4`; `workflows/placement.py` derives it as a `full` row, so every lane lays it with its step-5 placer exactly like a full-screen render, on the graphics track above the grade (it stays ungraded). ⚠️ on every lane until a real job proves it live.

- Premiere ✅ `uv run lanes/premiere/place-graphics.py projects/<job> --apply` (`--plan --write` first, which also syncs the plan; then `--verify` / `--remove <ids>` / `--reconcile [--apply]` / `--sync-plan`) + the bridge `zoom` command for baked footage moves; 5c evidence: `uv run lanes/premiere/review-frames.py projects/<job> --round <N>` — `premiere-pro` § Step 5. A second deliverable: `--variant ad --sequence "<job> AD"` (its plan is `graphics-plan.ad.json`, else graphics-plan.json's `variants.ad` composed by the preset's `layout.py`; QA it with `workflows/graphics-qa-short.py projects/<job> --variant ad`). A still region blur over screen-recording media: `lanes/premiere/place-blur.py` (never a tracked patch on reframed, graded camera footage: the Talking Head Explainer's `captures.md` § 11 recipe).
- Resolve ✅ `uv run workflows/placement.py projects/<job> --write` (the rows, and the plan's half-frame snap sync), then `AppendToTimeline` with `clipInfo` from those rows + a Fusion Transform comp for moves (`TimelineItem` has no keyframe API) — `davinci-resolve` § Step 5
- CapCut ✅ `uv run workflows/placement.py projects/<job> --write`, then `capcut-bridge.py graphics <draft> <job>` lays those rows, premultiplying each alpha mov first (`add-overlay` + `keyframe` for a one-off) — ⚠️ **every CapCut-bound alpha mov is premultiplied**; Premiere and Resolve both want STRAIGHT alpha — `capcut` § Procedure 4-6
- chat-only ✅ ffmpeg overlay assemble — [`lanes/chat-only/incremental-graphics.md`](lanes/chat-only/incremental-graphics.md)
- Final Cut ✅ `uv run workflows/placement.py projects/<job> --write`, then `replay.py` lays `placement.json` as connected clips on lanes 1.. (straight alpha as rendered; a stale `cut_rev` or an orphaned row refused), and the long-form zoom-out and push-ins as linear scale keys matched to how Premiere RENDERS its `zoom` (`lanes/finalcut/lab-notes.md` § 15). ⚠️ organic only: no ad variant (`--variant` is Premiere-only)

**Step 5′ — Footage layout keys (the Talking Head Explainer).** Target (universal): the plan's `layout` map
(S split / T tight / W wide; F and O keep W's footage) as HOLD keys on the footage, one hard switch per
layout change, V1 never razored, a hand-set Motion never overwritten. The transforms are face-frame.json
`modes`, lane-neutral ([`layout.md`](presets/instagram/talking-head-explainer/layout.md) § 2). Run after the
replay and the grade, and again after any re-cut or V1 rebuild.

- Premiere ⚠️ `uv run lanes/premiere/layout-keys.py projects/<job> --apply`, then `--verify` (`--dry` is the offline default; `--variant ad --sequence "<job> AD"` for the second deliverable) — `premiere-pro` § Step 5. Proven live on a throwaway project (2026-09-24: every planned mode on its program grab, a re-apply writes nothing; `lanes/premiere/lab-notes.md` § UNPROVEN LIVE); becomes ✅ after its first real job.
- Resolve ✅ Fusion hold keys (a timeline item has no keyframe API): one Fusion Transform comp per V1 item, keyed from face-frame.json `modes` on `lanes/premiere/layout-keys.py`'s own `plan_keys` frames, V1 never razored; proven on the Windows lane test (2026-10-13, a 75 s short: 2257 of 2257 frames on the plan's framing) — `davinci-resolve` § Step 5, with its 100.1 % retime and `comp.Lock()` traps. The older route (V1 pieces with static Pan/Tilt/Zoom) razors V1, a deviation to announce.
- CapCut ✅ `uv run lanes/capcut/capcut-bridge.py layout <draft> <job> [--hand a-b:MODE=scale,cx,cy]`: the plan's spans (the preset's `layout.py`) and `face-frame.json` modes as static values or hold-key pairs on the main track. Proven on Windows 2026-09-27: every switch on the same frame as the Premiere final — `capcut` § Procedure 4
- chat-only ⚠️ `uv run lanes/chat-only/assemble.py projects/<job>`: the base cut is cut FRAME-exact at the layout edges, each span laid at its footage transform (a row's own `frame` over its mode's, through the preset's `layout.footage_spans()`), then every overlay and the caption layer on top — [`lanes/chat-only/incremental-graphics.md`](lanes/chat-only/incremental-graphics.md) § The assemble script. Proven on the Windows test job and on demo-project (macOS, 2026-09-27: flash-scan PASS, 0.0 % duplicate frames); becomes ✅ after its first real job.
- Final Cut ✅ `replay.py` reads the plan's `layout` map through face-frame.json `modes`: a clip with no switch inside it gets its mode as a static transform, a switch inside one a 1-frame linear key pair (Premiere's hold), V1 never razored

**Step 6 — SFX.** Target (universal): [`presets/youtube/default/sfx.md`](presets/youtube/default/sfx.md).
The plan is universal: `uv run workflows/sfx-plan.py projects/<job>` reads the placed graphics and
writes `hf-graphics/sfx-plan.{json,md}` on the first run (one row per sound: timeline time, library file, source
slice, clip level in dB, track). Only PLACING the rows is per-lane. Built 2026-09-03 from a hand-placed reference intro, validated on two jobs. **Every format (2026-09-04):** any
job whose graphics carry motion events gets its sounds. `sfx-plan.py` reads the map of the plan's
`preset`: the Talking Head Explainer ships its own ([`sfx.md`](presets/instagram/talking-head-explainer/sfx.md)
+ `sfx.json`), and its face-to-graphic cut-ins come from the plan's layout map; any other preset without
one reads the `youtube/default` map and the report says so. A `fade_out_s` event (the calling bed) reaches
the cut sheet; the Final Cut, chat-only and Resolve placers lay its fade, and on Premiere and CapCut it is laid BY
HAND (⚠️: Premiere, a Constant Power transition on the clip's tail).

- Premiere ✅ `uv run lanes/premiere/place-sfx.py projects/<job> --apply` (`--verify`, `--remove`, `--remove-extra`, `--diff`, `--adopt`; `--plan` / `--sequence` / `--until` for a variant cut): imports each file once into an `sfx` bin, provisions A2–A4 with QE `addTracks`, sets the item in/out to the slice, `overwriteClip` at the row's frame, writes Volume > Level, reads everything back; `--diff` reports the creator's hand edits (moved / removed / re-leveled / re-sliced / added) against the plan, which is how they become rules, and `--adopt` makes the creator's accepted timeline the plan — `premiere-pro` § Step 6
- Resolve ⚠️ `uv run lanes/resolve/place-sfx.py projects/<job> --apply` prints the `run_script_unsafe` call that places the plan inside Resolve (`--verify`, `--remove-extra`, `--remove [ids]`, `--dry`; `--timeline NAME`, `--plan FILE`): audio-only `AppendToTimeline` on A`track + 1`, `AudioVolume` and a `fade_out_s` row's `SetFades` read back, a re-run finishing what the 60 s cap stopped; `--verify` fails any missing, extra or drifting cue (start and source in to half a frame, level 0.2 dB). Built 2026-10-14 from the lane tests (103 sounds by hand 2026-09-25; 18 of 18 from `sfx-plan.json` 2026-10-13), proven offline (`workflows/test_resolve_place_sfx.py`); ✅ after its first live job — `davinci-resolve` § Step 6. Not ported: `--diff`, `--adopt`, the `--until` copy window.
- CapCut ⛔ plan only: the universal plan is written; no audio-clip surface in the bridge. Hand-place its rows from `hf-graphics/sfx-plan.md` and say so.
- chat-only ⚠️ `uv run lanes/chat-only/mix-sfx.py projects/<job> <assemble.mp4> <out.mp4>`: every row of `sfx-plan.json` cut to its slice, levelled, its `fade_out_s` applied, delayed to its second and summed onto the dialogue (`amix normalize=0`), video copied, AAC 320k; it refuses an orphaned row and a plan whose graphic moved since it was derived while its cues did not (`sfx-plan.py`'s staleness check, 2026-10-13). Proven on the Windows test job and on demo-project (macOS: every single cue within 0.2 ms of its planned second).
- Final Cut ✅ `replay.py` lays `hf-graphics/sfx-plan.json` on connected audio lanes −1.. (plan track 1 = A2), each slice to the sample, levels and fades, each file's embedded timecode honoured (`lanes/finalcut/lab-notes.md` § 4); a stale plan or an orphaned row is refused (exit 2, 2026-10-13)

**The whole pack, one drag away, on every lane with a bin (2026-10-14, the Office Hours ask: "throw in all of the sound effects into the media bin so that I can custom place some myself").** The pack is `workflows/sfx-plan.py`'s `pack_files()` (every audio file under `assets/sfx/`, a sub-folder kept as a sub-bin), loaded into the `sfx` bin the placers use, a file already in the project never loaded twice, every timeline untouched, every file read back. All four are proven offline only (⚠️ until a live run; each tool's docstring has its mechanics): Premiere `uv run lanes/premiere/load-sfx-pack.py projects/<job> [--dry]` (every sequence's clip count identical before and after, else not saved) · Resolve `uv run lanes/resolve/load-sfx-pack.py [--dry]` prints the `run_script_unsafe` call · Final Cut `uv run lanes/finalcut/sfx-pack.py projects/<job> [--import]`: a NEW library `finalcut/SFX Pack.fcpbundle` to drag from · CapCut `uv run lanes/capcut/capcut-bridge.py sfx-pack <draft> [--dry]` (if the Media panel does not show the files, Import the folder by hand) · chat-only — no bin.

**Step 7 — Review.** The creator's, on every lane. The run pauses here.

**Step 8 — Export.** Target (universal): one clip into `projects/<job>/outputs/<job>.final.mp4`,
**verified with ffprobe on the finished file** rather than the app's own reported settings. The
encode numbers are per format: long-form = [`presets/youtube/default/README.md`](presets/youtube/default/README.md)
§ Export; short-form = [`presets/instagram/talking-head-explainer/README.md`](presets/instagram/talking-head-explainer/README.md) § Export (the one home of
the Reels numbers; captions are already on the timeline as a step-5 overlay, so nothing burns after the render). Only the encoder
dialog that reaches them is per-lane. A lane whose own encoder cannot reach a number renders a ProRes master and encodes it
with `uv run workflows/deliver.py <master> <out.mp4> [--shorts]` (the numbers, lane-neutral; Final Cut always, Premiere
for the 4K Shorts file). A 4K vertical job has a second file, the 2160×3840 one for YouTube Shorts, in `outputs/shorts/`,
finalized with `--variant shorts`. Then
`./finalize.sh <job> --apply`, which is lane-agnostic (it only reads `outputs/`). Flags: `--keep-drafts` is the agent-safe form (promote plus export copy, nothing in `outputs/` deleted; the previous final is kept as `<job>.draft-prev.mp4`). `--variant NAME` handles a second deliverable in `outputs/NAME/`, e.g. the ad cut: deliverable `outputs/ad/<job>.ad.final.mp4`, export copy `<job>.ad.final.mp4`, family `<job>.ad*` / `<job>-ad*`, drafts such as `<job>.ad-draft-N.mp4` retired. An app export written onto `outputs/<job>.mp4` (the base cut's name) is never promoted: finalize warns and `--apply` refuses while it is the newest file, so export to `outputs/<job>-final.mp4` (or `outputs/ad/<job>.ad.mp4` for the ad).

- Premiere ✅ scripted on the creator's go: `uv run lanes/premiere/export.py projects/<job>` → `outputs/<job>-final.mp4`, never `outputs/<job>.mp4` (`--draft` a numbered draft finalize never promotes; `--sequence "<job> AD"` → `outputs/<variant>/<job>.<variant>.mp4`; `--shorts` on a 2160×3840 sequence → `outputs/shorts/<job>.shorts.mp4`, through a ProRes master and `workflows/deliver.py`). It picks the FORMAT's preset from the sequence (any portrait → `instagram-1080x1920-h264-cbr14-23976.epr`, a short NEVER through a landscape preset, 2026-09-22; 3840×2160 and 1920×1080 → `youtube-2160p-h264-cbr50[-2997].epr`, the CBR 80 twin above 30 fps; any other size refuses, naming `--preset`), waits for `lsof` to show the file closed, ffprobes it against the preset and the timeline's frame count, and exits non-zero on a miss with the file kept. AME stays banned — `premiere-pro` § Step 8. Proven live 2026-09-26 on every cell (16:9 at 23.976 / 29.97 / 59.94 and 1080→2160, 9:16 at 1080 and 4K, and the Shorts file).
- Resolve ✅ the native render queue — [`lanes/resolve/resolve-export.md`](lanes/resolve/resolve-export.md) (21.1: `VideoQuality` is the bitrate in kb/s and lands only with `MultiPassEncode`, `FormatWidth`/`Height` the preset's frame, so a 1080 long-form renders at 3840×2160 and a 4K vertical at 1080×1920; the Shorts file is a second render at 2160×3840). Proven live 2026-09-26.
- CapCut ⚠️ `uv run lanes/capcut/capcut-bridge.py export --to projects/<job>/outputs --draft <draft>` drives the real dialog, then holds the file to the draft (H.264, the format's frame, the draft's rate, the frame count, ≤ 300 MB at 1080×1920; non-zero exit on a miss, the file kept). On macOS the creator sets the dialog's encode settings by hand (⚠️ the 2026-09-26 numbers are unproven on a macOS CapCut export); on Windows the bridge sets them and `workflows/deliver.py` encodes the presets' numbers from CapCut's master and its WAV (proven 2026-09-28). Rename the file `<job>-final.mp4` so finalize promotes it — `capcut` § Procedure 8
- chat-only — no export step: the render chain writes the file. `assemble.py` encodes the picture once at the export numbers, `mix-sfx.py` runs on EVERY job, one with no cue too (its AAC 320k 48 kHz replaces the splice's 256k the assemble copies), then `mix-music.sh` on a job with a bed; only the LAST pass takes the final name (`outputs/<job>-final.mp4`, or `outputs/<job>-music.mp4` after a bed), which finalize promotes — [`lanes/chat-only/incremental-graphics.md`](lanes/chat-only/incremental-graphics.md) § The assemble script
- Final Cut ✅ scripted on the creator's go: `uv run lanes/finalcut/export.py projects/<job>`: Final Cut renders a ProRes master with no clicks (`share.py`, `lanes/finalcut/lab-notes.md` § 14), its frame count proven, then `workflows/deliver.py` encodes and proves the format's deliverable (`--shorts` the 4K Shorts file) — `final-cut-pro` § Procedure. Proven live 2026-09-26 on every cell. ⚠️ organic only: `export.py --variant NAME` only files an export under `outputs/NAME/` for `finalize.sh --variant`

**Background music (conditional, opt-in).** WHAT (the bed level, the onset rule, the tail, the
opt-in ducking): the `background-music` skill. Only placing the track is per-lane.

- chat-only ✅ `mix-music.sh` on the near-final render (onset + tail built in)
- Premiere ✅ `uv run lanes/premiere/place-music.py projects/<job> --apply`, then `--bounce` for the proof (a music-only WAV bounce, no AME): the newest file in `audio/` onto A5, onset-trimmed, level written through the keyframe, 2 s tail — `premiere-pro` § Background music
- Resolve ⚠️ audio-only `AppendToTimeline` at the measured onset, `AudioVolume` = the preset's level, `SetFades` for the 2 s tail (proven on the Resolve lane test, 2026-09-25) — `davinci-resolve` § Step 6
- Final Cut ✅ `uv run workflows/music-onset.py <track> --write-plan projects/<job>` writes `hf-graphics/music-plan.json`, and `replay.py` reads it: one connected clip from 0 at `source_in`, `bed_db` held to a −96 dB key over the tail, to the end of the job's own timeline (its sections excluded unless the plan names an `end`)
- CapCut ✋ place the track on the music track (A5 on the `youtube/default` map) by hand: source in-point at the measured onset, the preset's level (house −20 dB; the Talking Head Explainer sets it from the track's own loudness, its README § Music), 2 s tail fade

## When you hit a ⛔ or a ⚠️

**An undocumented lane is not a blocked lane.** Every step's target is a set of numbers in the
preset, and the numbers are executable by hand in any editor. So:

1. **Do the step by hand** from the preset's spec. A footage move is two keyframes and an ease. A
   graphic is a file to drop on an overlay track.
2. **Say so out loud** in the run report, and record it in `projects/<job>/RUN.md` — same rule as a
   skipped step. A step done by hand on a lane that has no recipe is a normal outcome; a step
   quietly done differently from the preset is not.
3. **If it becomes routine, write the recipe into that app's skill** under its step heading, and
   flip this cell. Never write it into the preset.

**Never substitute another lane's mechanics.** The failure this file exists to prevent is a Resolve
job running the Premiere recipe: an adjustment layer where a color group belongs, Motion Scale 200
on a timeline that already auto-conformed, a premultiplied alpha mov on a lane that wants straight.
Each of those looks plausible and ships broken.

## Adding a lane

Three touchpoints, no new machinery:

1. A column in the matrix above, honest about what is ⛔ on day one.
2. A skill for the app, headed by the same step numbers as every other app skill, carrying only
   HOW.
3. Nothing in any preset. If a preset needs to change to support a new app, the split above has
   been broken somewhere. **One deliberate exception:**
   [`presets/youtube/vox-collage/premiere-lane.md`](presets/youtube/vox-collage/premiere-lane.md)
   is app mechanics kept inside its look's folder on purpose, so that look's inverted stack (grade
   ABOVE the graphics) cannot leak into a default job — 2026-08-31.
