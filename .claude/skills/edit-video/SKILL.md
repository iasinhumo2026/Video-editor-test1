---
name: edit-video
description: "Runs the WHOLE edit end to end: the eight-step pipeline in order, raw clip to exported file, with a durable per-job RUN.md so a run survives compaction and resumes cold. Owns the ORDER, the STATE and the GATES only (each step's how-to stays in its skill or preset): step N is done to its definition before N+1 starts, and a step that cannot run is announced as skipped. Triggers: edit this video, do the whole edit, run the whole pipeline, full edit, edit this end to end, take this from raw to export, run the pipeline, edit the latest project, resume the edit, where were we on this job, continue the edit."
---

# Edit Video — the whole run

**This skill owns the LINE, never the STEP.** It knows what order things happen in, what "done"
means for each one, and where the run is up to. It knows nothing about how to cut a word, author a
comp, or bake a zoom — that lives in each step's own skill or preset, and this skill routes there.

It exists so a compaction never loses the place, no step starts before the last is finished, and no step
that cannot run is passed over unnoticed.

## 🔒 THE FIRST THING, ALWAYS: read `RUN.md`

Before anything else, look for **`projects/<job>/RUN.md`**.

- **It exists** → this job is already underway. Read it, report where the run is in one line, and
  resume at the first step that is not `done`. **Never restart an unchanged step marked `done`**, and never
  re-replay a timeline the creator has hand-edited since.
- **Live state that disagrees with RUN.md is the creator's hand edit, never a failed write (the user,
  2026-09-14).** A layer shorter than recorded or a clip moved since the last pass: report the
  difference, record it in RUN.md, leave it. Re-apply a write only when its own readback right after
  the write proved it failed (a grade layer trimmed back on purpose was once "restored" over a screen
  recording you had left ungraded). **Never ask what a hand edit was for (2026-09-28): every change the
  creator makes is intentional.** Read it, sync the files to it (`lanes/premiere/live-edl.py --write`,
  then `workflows/ripple-cut.py`) and keep going. Name a place in the video by its TIMELINE time (M:SS
  into the cut), never a raw-footage timecode.
- **It does not exist** → this is a fresh run. Create it (template below) after resolving the job.

This is unconditional. A fresh context that starts cutting because it did not look is exactly the
bug this skill exists to kill.

## The line

Eight steps, in order, every job. The full spec is CLAUDE.md § The Pipeline; this table is the
gate list — what has to be TRUE before the next step starts.

| # | Step | Owned by | Definition of done (all must be true) |
|---|------|----------|----------------------------------------|
| 1 | Intake | _(copy)_ | Raw is **copied** (never moved) into `projects/<job>/raw/`; the original is untouched; the job is named after the content, not the camera file or a date. |
| 2 | Rough cut | `rough-cut` | every CAMERA raw's A/V offset measured at intake into `transcript/av-slip.json` (`rough-cut` § Lip sync at intake; the replay lays V1 with it); `transcript/words.json` + `transcript/cuts.json` persisted; canonical `outputs/<job>.transcript.json` written; boundary polish run; the fresh-eyes second pass run; final dialogue-only dead-air gate passes on the final EDL, including protected boundaries; complete outro/handoff retained unless explicitly removed. **App lane:** splice ran `RENDER=0` (no flat MP4) and the EDL is replayed onto the timeline with the clip count read back and matching. Every cut is proven on the finish surface: `workflows/cut-audit.py` clean on the sequence's grid (exit 0; exit 3 = UNVERIFIED, the slice ASR could not run, is never read as clean) and, on Premiere, `lanes/premiere/cut-proof.py` exiting 0 (`rough-cut` § Audit the cut on the finish surface's grid · § The proof); on a lane with no cut proof in [`LANES.md`](../../../LANES.md) § step 2, the laid cut is checked by ear and recorded in RUN.md as unverified. |
| 3 | Audio polish | `premiere-pro` / `davinci-resolve` / `final-cut-pro` (normalize bake) / `capcut` / baked by splice | Gain measured by `workflows/voice-gain.py` (kept speech → −17 LUFS pre-limiter), never a fixed number; the house chain applied to **every** voice clip; **every value read back**; the clip count reported. **The cut locks here.** A whole-edit ask does NOT wait for the creator (2026-09-26): record `cut locked` as `run through (whole-edit ask)` and carry on, and cut notes that come back at step 7 are a declared RE-CUT (§ Where the run STOPS). A narrower ask ("rough cut") ends after this step anyway, and the next step (4 on long-form and the Talking Head Explainer, 5 on TikTok/raw) starts only once the creator has watched the laid, polished cut and said the cut is good. Either way a cut change after step 5 rebuilds every downstream layer. Record `cut locked` in RUN.md with the segment count and the `cuts.json` hash (`shasum -a 1 projects/<job>/transcript/cuts.json | cut -c1-12` — the same stamp `ripple-cut.py` reads). |
| 4 | Color grade | the format's preset § Grade | **Every preset with a § Grade (long-form, the Talking Head Explainer).** Grade layer exists **under** the graphics track and **over** the footage, one layer spanning the timeline, **sized to the sequence**; the look verified by measuring a program render, never a readback. Run it where [`LANES.md`](../../../LANES.md) § step 4 has a recipe; on a ⛔ lane do it by hand from the preset's numbers or record it as skipped, in words. |
| 5 | Graphics | `graphics-plan` → `graphics-build` → `edit-review` | `graphics-plan.{json,md}` written; every `capture` cell recorded into `assets/captures/` (an app fronted for a take is SAID in RUN.md); every required evidence beat (including exact prompt walkthroughs, named destinations and restored outro passages) planned, built and placed; **placement FRAME-EXACT**: every row whose end is a V1 cut lands ON it, not a frame short (`graphics-qa.py`'s `cut` check, green); `edit-review` ran its ONE review round, every verified finding fixed and the gate green on the changed graphics. **On the Talking Head Explainer also:** `presets/instagram/talking-head-explainer/layout.py projects/<job> --check` 0 FAIL, the `captions.py` gate exit 0, and the lane's layout keys verified where [`LANES.md`](../../../LANES.md) § step 5′ lists a readback (on a ⛔ or ⚠️ lane without one, done by hand, checked on a program render and recorded in RUN.md as unverified; its README § Definition of done). Not done when the last comp lands — done when that pass has run. |
| 6 | SFX | `workflows/sfx-plan.py` → the lane's placer | Every format with graphics. Runs AFTER the step-5c review pass. `hf-graphics/sfx-plan.{json,md}` written from the PLACED graphics and reviewed as a cut sheet; every planned row placed on the lane's SFX tracks at its frame and level, **read back with zero missing, extra, or drifting cues**. Run the placer where [`LANES.md`](../../../LANES.md) § step 6 has one; a lane without one hand-places from the cut sheet and says so. After graphics change, review the candidate score and update affected cues while preserving approved unaffected rows/levels; then apply and verify. |
| 7 | Review | _(the creator)_ | Handed over with the draft ready to watch. **The run pauses here** — this step completes when you say it does. Each change you call is made INLINE by the main session (§ Where the run STOPS). |
| 8 | Export | lane exporter → `finalize.sh` | A real final file exists in `outputs/`; `finalize.sh --apply` run (`--apply --keep-drafts` when the run may not hard-delete; each extra deliverable, such as the ad cut, via `--variant ad`; a non-zero exit with the base-name warning means rename the export and re-run); the `~/Downloads` copy present. **Never render one just to satisfy the step** (the export runs only on the creator's go). **A "final, ready to post" ask is the go for ONE export, never a standing one (2026-10-14):** the step-7 changes you call after it stay on the timeline, unexported, until you say export again ("you don't need to re-export every time... I'm probably going to make a lot of changes"). |

**One conditional pass** slots in without being numbered: **Background music** (opt-in, after 6,
before 7). It either runs or is stated as skipped, same rule as a step. Captions are not a pass: on
a short-form preset they are the `captions` cell of the step-5 plan, built and placed with the
other graphics (2026-09-04); long-form has none.

## 🔒 THE RUN IS AS LONG AS THE ASK (2026-09-19)

"Do the whole edit" / "edit this end to end" runs the line through SFX to the step-7 handoff, and
nothing on the way waits for the creator, the step-3 cut lock included (2026-09-26): the edit
is finished to everything but the export, which stays the creator's go. A
request that names a step runs THAT step and stops: "rough cut" ends after steps 2–3, "do the
graphics" ends when 5c is clean. Never continue into a step you did not ask for (SFX included), and
never treat stopping there as a skip: RUN.md shows the later steps as not started, and the report
says which step is next.

## Step 0 — resolve the job, before step 1

Do all of this once, up front, and write it into RUN.md so no later step re-derives it:

1. **The job folder.** Newest under `projects/` unless you named one.
2. **Format — probe it, never ask (2026-08-13).** `ffprobe` the raw: height > width means
   short-form, width > height means long-form YouTube, read as it DECODES: a rotation of ±90
   (`stream_side_data=rotation`) swaps the two, so an iPhone portrait take coded 1920x1080 with
   `rotation=-90` is vertical (the probe line is `rough-cut` § The Edit Philosophy). A mixed folder is decided by the clips
   carrying the dialogue — the main takes vote, b-roll and inserts do not. Talking Head Explainer vs
   TikTok/raw is resolved HERE from the content ([`presets/instagram/talking-head-explainer/README.md`](../../../presets/instagram/talking-head-explainer/README.md)
   § Where each step lives), not at step 5, because that preset shapes steps 2, 3, 4 and 6; a raw shot
   landscape for a short is that preset too. Resolve it ONCE here, write it into RUN.md, and
   state it in the report so one word can override it. **Read the transfer in the same probe**
   (`-show_entries stream=color_transfer -of json`): `arib-std-b67` (HLG) or `smpte2084` (PQ) is an HDR
   raw, an iPhone's HDR Video. Record HDR in RUN.md and decide the route HERE: the chat-only and clipper
   renders refuse it (`splice.sh` stops before it measures or encodes), so the finish goes to an
   editing app, or the raw is converted to Rec.709 SDR once in `raw/` before step 2.
3. **The lane.** The one setup recorded, when `.setup-complete` carries a `lane=` line (a client
   package writes `premiere`, `resolve`, `capcut`, `finalcut` or `chat-only` there); otherwise Premiere by
   default with nothing named. A recorded `chat-only` is never re-asked. Never infer ANY lane from a
   job's content: on a machine with an app, only an explicit yes gets chat-only, and a video ABOUT
   an app is not an ask to finish in it (2026-09-28: a video about Final Cut built there cost a full
   rebuild in Premiere).
4. **The preset**, which follows from format. **On the Talking Head Explainer:** read its README
   before step 2, and find the brief ([`story-and-cut.md`](../../../presets/instagram/talking-head-explainer/story-and-cut.md)
   § 1): the cut is judged against it.
5. **The lane's coverage.** Read [`LANES.md`](../../../LANES.md) once, top to bottom, for the column
   you are on. Write the ⚠️ and ⛔ cells into RUN.md up front, so a gap is a known cost at the start
   of the run rather than a surprise at the step. It also decides what to say in the opening report.
6. **Source fps and duration**, read once.
7. **Request coverage**, captured in RUN.md before planning: asked-for beats and omissions, verbatim artifacts with their source paths, real destinations to capture, music choice (a track given? none means no bed), finish instruction, sponsored? (a second, ad deliverable only when asked for). Map each to its owner and its eventual evidence; a plan that omits a requirement cannot be its own proof of completion.
8. **Whether the video's own claim constrains the run.** A piece that asserts it was edited in one
   pass may not be seeded from an earlier job: no copied `hf-graphics/` comps, renders,
   `graphics-plan.json`, harness files or assets out of another job folder. Only the format's preset
   and its reference files, the repo's `assets/` and system fonts are fair game, and every capture
   and asset is fetched fresh for this job. Reading an earlier job to learn the craft is fine right
   up to the moment it becomes a copied file. Record it as a constraint in RUN.md so a resumed
   session keeps it.
9. **What must never appear on screen** (2026-10-05: skipped on your OWN videos unless you ask; client jobs keep it). A job with screen-recording or live-call footage carries
   literal strings it must not show: a phone number (the creator's own or anyone else's), an API key, an
   account id. Capture them here as a constraint in RUN.md and list them in `projects/<job>/pii.json`:
   `needles` (numbers and keys, matched by their digits), `phrases` (words such as staging prompts, a churn
   line or a label; literal, so a grep pattern like `\$[0-9]` does not port, and the sweep says what it
   became) and `any_number` (7: any phone-shaped number nobody named). What each key matches: `workflows/pii-scan.py`'s
   docstring (not counted: digits glued to letters on both sides, a UUID, dates, clocks, and a camera or
   screenshot date-time stamp inside a file name with an extension; a bare stamp still flags). Sweep with
   `uv run workflows/pii-scan.py projects/<job>` (a `--needle "<string>"` adds one on the command line) once
   the cut is laid, again before the draft is handed over, and again after any re-cut. It sweeps the kept
   spans of EVERY raw the EDL plays into `review/pii-scan.json`, which `place-blur.py` reads (a job that plays
   several raws gets one `review/pii-scan-<stem>.json` per raw, each laid with `place-blur.py --hits <map>`);
   `--raw <take|draft> --all` sweeps any other video into its own map. Its hits are confirmed off
   `review/pii-hits/sheet.jpg` by eye before anything is blurred. A clean sweep only means Vision read
   nothing: a phone or screen held up to the camera is checked by eye too (frame stacking recovered text OCR
   had read as nothing, 2026-09-22), and any screen visible in the CAMERA footage (a phone on a live call, a
   laptop behind you) is swept like a capture. Never eyeballed from scratch, never left to the creator.

## A RE-RECORD of an approved edit (2026-10-05)

The creator films an approved video AGAIN (a flaw on camera, not in the edit) and wants the new take to come out
looking exactly like the approved one, first try. The approved edit is the spec, so it is frozen BEFORE the new raw
lands, and the new run re-uses everything that does not depend on your delivery:

1. **Freeze** into `projects/<job>/reference/<label>/` (small files, copied, never moved): RUN.md, `pip.json`, the
   recording-render manifests and box tracks, and per section the canonical transcript (`transcript.json`), `cuts.json`,
   `words.json`, `av-slip.json`, `graphics-plan.json`, `placement.json`, the `sfx-*.json`, `qa-waivers.json`,
   `text-animation/text.json`; the approved `.prproj` copied into `premiere/archive/<job>.<label>-approved.prproj`.
   Captures, comps and renders stay where they are: the new run makes new VERSIONS beside them, never overwrites.
2. **Intake** the new takes under NEW file names (`raw/<section>-take2.mp4`), and each section's `raw/` holds only its new
   take's link, so its transcribe sees one take. The old `raw/<section>.mp4` files stay: the approved project plays them
   (it references the job's `raw/` file, never the section link: check its media paths before removing a link).
3. **Steps 2-4 as usual**, with `--force` on the transcribe (the old `words.json` is frozen), the lip sync measured at
   intake (`rough-cut` § Lip sync at intake), and the cut made TO the approved script (`rough-cut` § A re-take of an
   approved cut). A fresh project from the lane's template, the grade and the audio chain re-applied.
4. **Re-time every layer by the words, per section, once its cut is laid and read back** (`live-edl.py --write`
   stamps the new `_timeline`, which carries the section's new offset):
   `uv run workflows/ripple-cut.py <section> --from <reference>/<section>/cuts.json --retake <reference>/<section>/transcript.json`
   (dry run, then `--apply`). Every ORPHANED row is a line the new take does not say: re-anchor or drop it by hand.
   Every COPY row is a text animation whose words you changed: rewrite the copy to what you say. Every RE-RENDER row
   follows the new delivery.
5. **Rebuild only what moved:** the text animations from the new transcript (their builder finds each phrase), the
   recordings re-fitted to the new spans (their source in moves so the moment a highlight marks still lands on its
   word, and the highlight's track moves with it), the hand comps whose internal times ride words (checked, re-timed),
   the push-ins re-baked at their re-mapped `push_at`, the corner cam laid fresh (`lay-pip.py`, face re-measured on the
   new raws), the SFX re-planned from the placed graphics. Then the usual gates, the bin organized, and step 7.

The approved edit's step-7 notes are already in the presets and skills, so nothing you asked for is asked for twice.

**The order is what makes it fast (take 2 of your-job took 2 h, about 40 min of it re-work):** both fresh-eyes reviewers' cut fixes land BEFORE the replay (a fix after the lay re-lays V1, the audio chain, the push-ins, the corner cam and every recording render); every recording and comp window is snapped to the frame grid and to a V1 cut within 6 frames BEFORE the first render (`graphics-qa.py` `cut` fails anything a frame off, and the corner cam's shadow lays on frames); the Look is written ONCE, after the corner cam is final (a re-laid PiP piece's Lumetri is empty again). An ad-libbed re-take is a re-plan, not a retime: `ripple-cut.py --retake` orphans most rows, so the plan is rebuilt from phrase anchors on the new transcript, reusing the take-1 cells' content.

## Running a step

Each step, in this order, no exceptions:

1. **Announce** which step is starting, in one line.
2. **Route — WHAT first, then HOW.** Two reads, the same shape every time:
   - **WHAT** = the format's preset, § this step. The target, the numbers, the definition of done.
     App-independent by construction.
   - **HOW** = [`LANES.md`](../../../LANES.md), the row for this step, which names the lane's status
     and points at the section in that lane's app skill (`premiere-pro` / `davinci-resolve` /
     `capcut` / `final-cut-pro`), or at the chat-only sheet.

   Do not re-derive either here. **Never read another lane's mechanics** — an adjustment layer on a
   lane whose equivalent is a color group, a premultiplied alpha mov on a lane that wants straight,
   and a hand-scaled 1080 asset on a timeline that already conformed have each shipped damage.
3. **Handle a ⚠️ or ⛔ cell explicitly.** An unvalidated recipe is a test: run it, then verify by
   measurement and say the result. A gap means do the step by hand from the preset's numbers and
   **say so** — it goes in the report and in RUN.md, same as a skipped step. A step done by hand is
   a normal outcome; a step quietly done differently from the preset is not.
4. **Verify** against the definition-of-done column above. Verification means reading state back
   or measuring an artifact, never assuming a write landed.
5. **Write RUN.md** — current status, verified facts, paths to evidence, and any flag. Keep historical revisions separate from the current clip/graphic/SFX counts. An appended/restored passage — or any structural timeline edit (ripple, reorder, re-lay, range sweep) — reopens its rough-cut, graphics, SFX and ending checks; an old `done` flag does not cover new footage.
6. **Only then** start the next step.

**A step that cannot run is announced out loud and recorded as `skipped`, with the reason.** It
gets said in words and written down; it never silently disappears.

**A blocked step does not block independent work.** Record it and continue where dependencies allow; a missing required capture or failed verification remains unfinished. Do not label the draft complete while a required gate is failed or skipped; a gate [`LANES.md`](../../../LANES.md) marks ⛔ for the lane counts as done-by-hand when recorded as such.

## Where the run STOPS on its own

- **Step 7 is the creator's.** Hand off the draft and stop. Do not proceed to export on your own.
  **A step-7 change runs INLINE in the chat (2026-10-14).** "Change this caption", "move that
  graphic", one graphic or one caption: the main session edits, re-renders the one part, re-places
  and shows it. Never a spawned agent and never `edit-review` for it: a subagent starts cold, re-reads
  the job and costs minutes and usage for a one-line fix (a client's caption change through one "took
  forever", 2026-10-13). Write each round's notes into RUN.md § Step 7 notes, in the creator's own
  words, with what changed: the record `bake-preset` reads at the end.
  **Read the notes that come back for the PRINCIPLE, not the wording (2026-09-10).** A note
  given as an example — "maybe it slides out to the right and something slides in from the left" —
  names what you want more of, on any format; say that principle back in one line, then design to it
  with whatever fits the beat. Executed verbatim instead: numbers you dictates (frames, sizes,
  curves), a look or preset you name by name, every locked preset value, and anything you flags as
  exact. Building the example literally ships the letter of the note and misses the taste behind it.
  **A note is MADE and PLACED, not previewed (2026-10-04: "when I tell you to make an edit, I just
  want you to make the edit").** A preview comes only when you ask for one, typically before a change that
  lands on 10+ clips. Then mock it from the real frames (the program frame, the graded footage), send it,
  and change the finish surface once you pick. Without that ask, make the change on the timeline and show
  the result.
- **Feedback that points at live app state is READ from the app before it is interpreted, on every
  lane.** "the in and out points I set", "the highlighted clip", "this section", "at the playhead" —
  query the finish surface's marks, selection and playhead first (the calls are the lane's, in its
  app skill), read the content back, and only then analyse. Inferring the target from the
  conversation instead once got the wrong segment diagnosed AND deleted (2026-08-28). Nothing marked
  or selected: say so and ask for a timecode. After acting on marks, clear them so they cannot go
  stale over shifted content.
- **A check never exports a draft (2026-09-28).** A visual check is a program-frame grab off the
  live timeline (Premiere: `node lanes/premiere/premiere-bridge.mjs frame`, every track composited), and
  the audio proofs have their own bounces (`cut-proof.py`, `place-music.py --bounce`, `audio-polish.py
  --verify`). A render is made only on the creator's ask, at step 8, or where a proof tool reads a
  rendered file (`framing-continuity.py` on a substituted clip, a whole-mix true peak): a 4K draft ties
  the app up for minutes and shows nothing a frame grab does not.
- **On the Premiere lane the run pauses at step 7;** on the creator's go step 8 runs
  `uv run lanes/premiere/export.py projects/<job>` then `./finalize.sh <job> --apply`; never export unasked, AME
  stays banned.
- **`edit-review` runs ONE review round** inside step 5, never a second. A finding it cannot fix is
  reported open, never looped on.
- **A cut change after step 3 is a declared RE-CUT, never an ad-hoc script.** Freeze the approved
  files into `reference/<label>/` and back up the project, then run
  `uv run workflows/ripple-cut.py projects/<job> --from <old EDL>` (dry run first, then `--apply`)
  before anything on the timeline is touched: it re-times the transcript clock, the plan rows,
  the placement, the SFX cues and the text metas through the SOURCE. Then the lane re-lays V1/A1,
  re-applies step 3 and its placers re-place, in the lane's order (Premiere: `premiere-pro` § A
  declared re-cut), and every row it reports as ORPHANED, STRADDLING or needing a RE-BAKE is decided by
  hand. A SECTION sub-job that a creator's ripple earlier in the sequence only MOVED is the same
  recovery: `lanes/premiere/live-edl.py <section> --write`, then `ripple-cut.py <section> --from
  <that backup> --apply`, which moves the plan's `timeline_offset` and the SFX cues with it; the
  Premiere placers refuse a moved section until it has run (`lanes/premiere/lab-notes.md` § Step 5).
- **A SUBSTITUTED CLIP IS PROVEN ON THE PICTURE (2026-09-23).** After any clip replaces the raw on V1
  (a lip-sync render, a re-take, a re-rendered segment): export a draft, with the graphics tracks off
  when the lane allows it, and run `uv run workflows/framing-continuity.py <draft> --cuts <clip in>,<clip out>`
  (once `live-edl.py` has written `_timeline`, `--cuts projects/<job>/transcript/cuts.json`). Exit 0 is
  the definition of done. Exit 1 names the jump in export px: fix the clip's geometry at source, lay it
  again, re-run. Exit 2 is UNMEASURED and never a pass: a cut where the layout changes on purpose (split
  to full frame, a punch-in, a full-screen graphic) reads it by design, so prove the clip at its other
  cut or on a draft exported with that reframe off, and say so in the report; a lone mover dragging
  footage round it is re-run with `--patch` on bare background away from it. How each verdict is read,
  and the one case left to the eye: the tool's docstring. A fix rendered but not laid is not a fix:
  re-export and re-run after the new clip is on the timeline, and record the exit codes in RUN.md (a
  lip-sync CTA 33 px off reached review twice, the second time rendered and never laid).

## Final handoff gate

Before the run is reported done, reconcile every row of RUN.md § Request coverage against the actual saved sequence, never against `graphics-plan.json` — a plan is not evidence that the thing shipped. Each step's own definition of done carries its proofs; the render- and timeline-side checks are `edit-review` § Final gate.

## `RUN.md` — the state file

Lives at `projects/<job>/RUN.md`. Rewrite the whole file at each step boundary; it is small.

```markdown
# RUN — <job>

**Next action:** <the single next thing, in one line>

| | | |
|---|---|---|
| format | long-form YouTube | probed: 1920x1080 |
| lane | Premiere | `projects/<job>/premiere/<job>.prproj` |
| preset | `presets/youtube/default/` | |
| lane gaps | none | from LANES.md — list every ⚠️/⛔ step for this lane, or "none" |
| source | 30000/1001 fps · 121.02s | |
| constraints | none | or "fresh build — nothing reused from an earlier job"; the strings that must never reach the screen live here |
| cut locked | 35 segments · cut_rev 2a4e4a463c6f | the creator said the cut is good on <date>, `run through (whole-edit ask)`, or "not yet" |
| started | 2026-09-01 | |

## Steps

| # | Step | Status | What it produced / why not |
|---|------|--------|----------------------------|
| 1 | Intake | done | `raw/clip-01.mov`, original untouched |
| 2 | Rough cut | done | 35 segments · cuts.json + canonical transcript · replayed, 35/35 verified |
| 3 | Audio polish | done | measured +12 dB (voice-gain.py) → −6 dBFS limiter on 35/35 A1 clips, readback verified |
| 4 | Color grade | done | GRADE layer on V2, Autumn Look @80/120 via `grade-lut.py apply`; frame grab moved 105.9/87.6/90.7 → 99.2/83.5/85.2 |
| 5 | Graphics | done | 25 graphics placed; edit-review: 4 found → 4 fixed, gate green on the 3 changed |
| 6 | SFX | done | 124 rows planned, 124/124 placed on A2–A4, readback verified |
| 7 | Review | — | |
| 8 | Export | — | |

## Request coverage
- Asked-for beats / omissions: <request → kept source/timeline evidence>
- Verbatim artifacts / real destinations: <source path → planned beat → native proof>
- Music / finish instruction: <track, reviewed entrance/level; saved timeline or authorized export>

## Flags to report
- g19 typed prompt holds 2.50s (retimed from 0.60s)
- timeline 326.6–330.4 · source 1861.1: the on-screen timer reads 29:54–29:57 against a spoken "29:53"

## Skipped, and why
- Background music: not asked for.

## Step 7 notes
- Round 1 (2026-09-03): "the lower third sits on my chin, lift it" → lower thirds raised 40 px, g4–g9 re-placed

Baked: 2026-09-04 · 2 rules → presets/youtube/default/creative-moves.md
```

**A flag about something VISIBLE in the footage carries WHERE, never just what it says:** the
timeline window (start–end seconds) and the raw source time. "the timer reads 29:53" is a
conclusion; "timeline 326.6–330.4, source 1861.1, reads 29:54–29:57" is a flag someone can act on
cold. Same for a number, a name, a key, a face or anything else that has to be covered, blurred or
cut later — without the location, step 5 re-samples the whole cut to find a four-second window.

Keep it short. It is a resume doc, not a log: what is true now and what happens next, never a
transcript of how you got here.

## Compaction — write state always, compact rarely

**Write RUN.md at every step boundary, so that whenever a compaction happens, it is safe. This
skill never triggers one — the user types `/compact`.** Never compact inside step 5: the plan feeds
the build feeds the review. **Two boundaries where one genuinely pays**, because the context behind
them is dead weight for everything after: **after step 2** (per-word cut decisions are finished,
only `cuts.json` and the canonical transcript matter downstream) and **after step 5** (comp
authoring, renders and QA measurements are done; steps 6 to 8 need none of it). At each, say in one
line that RUN.md is current and this is a clean place to `/compact`.

## The report, at the end

One block, tight: the format and lane detected, per-step status, **everything skipped and why**,
**every step done by hand because the lane had no recipe**, any flags standing, and the deliverable
path. If the run stopped at step 7 for your review, say that plainly rather than implying the job is
finished. After a finished export, end the report with the one-line `bake-preset` offer that
`finalize.sh --apply` prints as its `Next:` line; the bake runs only on the creator's yes.

Link every render in chat by its full repo-root path (`projects/<job>/outputs/<file>`), never a subfolder-relative one, so it opens inline; never open it in QuickTime or another app for the creator.

## Not this skill

How to cut a word (`rough-cut`) · how to author or place a graphic (`graphics-plan`,
`graphics-build`) · how to converge defects (`edit-review`) · app mechanics (`premiere-pro`,
`davinci-resolve`, `capcut`, `final-cut-pro`) · look decisions (the presets) · the clipper entry path, which is a
different flow entirely (a finished long-form in, short clips out). This skill only ever decides
**what happens next, and whether the last thing is actually finished.**
