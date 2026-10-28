---
name: bake-preset
description: "Bakes what an edit taught into its preset so the next video like it comes out right first time: reads the job's RUN.md, review rounds, the creator's own words from every session on the job and their hand edits, turns each creative call that should hold into one rule, shows the short list, and on a yes writes each rule into its one home (the job's preset docs, or my-rules.md for a personal rule; never CLAUDE.md, never twice). Offered after finalize.sh --apply; runs whenever asked. Triggers: bake this into the preset, bake it in, lock this into my preset, take everything you learned from this edit, remember this for next time, make this stick, update the preset from this edit."
---

# Bake Preset: make the edit stay learned

A preset only gets better when what each edit taught is written into it. Every note, re-do and hand edit in a
review round is a creative call; left alone it lives in one session's context and is gone by the next video. This
is the loop that built the default presets, the one thing to do after every edit (2026-10-13): "take
everything that you learned while we were doing this edit and bake it into the preset so that the next time I do a
video like this, it comes out ready first try."

## When it runs

- **Offered on every finished export, never run unasked.** `./finalize.sh <job> --apply` ends with a `Next:` line
  once the deliverable is in place, re-runs included, and so does a finished `make-clips.py --build` (the `clipper`
  writes its finals itself; bake on the parent job): offer the bake in one line. It also runs on any trigger phrase,
  at any point after a review round ("lock this into my preset" mid-job bakes that one call).
- **One bake per stretch of work.** The `Baked:` line it leaves in RUN.md (§ 4) says what is already in; a re-run
  proposes only what came after it.

## 1. Gather what the edit taught

Read, never ask:

- **The creator's own words.** This conversation, plus every earlier session on the job:
  `uv run .claude/skills/bake-preset/scripts/session-notes.py <job>` prints only what the creator typed, from every
  Claude Code session that names the job, oldest first. After a compaction it is the only record of the early
  rounds. (On Codex it does not apply: the conversation, RUN.md and `review/` are the record.)
- **The job's state.** `projects/<job>/RUN.md`: the `preset` row, Request coverage, Flags, every deviation and every
  step-7 notes section; the notes under `projects/<job>/review/`. A `.pre-*` backup beside a pipeline file
  (`transcript/cuts.pre-*.json`, `hf-graphics/placement.pre-*.json`, a plan's own `.pre-*` copy) diffed against the
  current file is what a round changed.
- **The creator's hand edits.** RUN.md records them (`edit-video` § THE FIRST THING: live state that disagrees is
  their edit). On Premiere, with the job's project active, `uv run lanes/premiere/live-edl.py projects/<job>` diffs
  the live cut against `cuts.json` and `uv run lanes/premiere/place-sfx.py projects/<job> --diff` the sound; another
  lane's readbacks are in its app skill. A level written back into `hf-graphics/music-plan.json` is one too.
- **The rules already in force:** `my-rules.md` and the job's preset folder, read before anything is proposed.

**Evidence weighs in one order: hand edits, then what the creator asked for and approved, then Claude's own calls
(only where the creator approved the result). The FINAL state wins:** a call the creator later reversed is an
anti-pattern worth writing down, never a rule (the order the
[Talking Head Explainer](../../../presets/instagram/talking-head-explainer/README.md) was built in).

Notes too long to read here go to ONE subagent that returns each candidate call with the creator's words (the
chat's own model: `edit-review` § Token efficiency); the main session judges every rule.

## 2. Keep only what should hold next time

A rule is a creative call that should hold on the NEXT video of this kind. Write the principle behind the note, not
its wording: a note given as an example names what the creator wants more of (`edit-video` § Where the run STOPS).
Numbers they dictated, a look named by name and anything flagged as exact go in verbatim.

Never a rule (drop it, or list it once as not baked):

- **This video's content:** its lines, names, copy, cast, a per-shoot measurement (the face, the chin line, a sampled
  colour), and counts or timings that describe one video. The worked list is the Talking Head Explainer README
  § What never becomes a rule.
- **A device used once** is a taste signal, not a mandate, unless the creator said "always", "every time" or "from
  now on".
- **A tool defect or its workaround:** name it as a defect to fix (CLAUDE.md § Rules: fix the source). A workaround
  baked into a preset outlives the fix.
- **An app quirk:** a preset is identical in every app, so it belongs to that lane's `lanes/<app>/lab-notes.md`.

## 3. One home per rule, found by grep

- **About one format** (its look, motion, sound, cut, captions, music, export) → the job's preset, RUN.md's `preset`
  row, in the doc that already owns the topic: the preset README's step index names the doc, then grep it for the
  section. A number goes where the preset keeps it (`sfx.json`, a doc's § Values block, and whatever mirrors that
  block: the Talking Head Explainer's kit mirrors `graphics.md` § Values).
- **The creator's own rule for every video, whatever the preset** (how takes are picked, words never cut, their
  voice) → one line in `my-rules.md`. A folder with no `my-rules.md` (the author's own repo): the skill or doc that
  owns that step.
- **Grep before writing.** The same rule already there: skip it. A rule that changes one: edit that line in place,
  never add a second line that contradicts it. A locked value (a 🔒 section, both caption presets) changes only on a
  yes to that line, shown as `changes the lock: A → B`.
- **Never CLAUDE.md** (an update moves a creator's own lines out of it into `my-rules.md`), and never auto-memory
  alone.

**A baked rule survives every update.** On a client install `update.py` keeps each version as shipped on `upstream`
and three-way merges it into the creator's branch: a preset line only they changed keeps their version, and a spot
both sides changed stops as a conflict Claude resolves keeping both (CLAUDE.md § Updating to a new version).
`my-rules.md` and a preset folder of the creator's own are never touched by an update, so a creator who wants their
style kept apart from the shipped one makes their own preset folder once; the bake writes into whichever preset the
job ran on.

## 4. Show the list, write on the yes

One short list, one line per rule: the rule, where it lands, and its evidence (the round or date, a few of the
creator's words). Then what is not baked, one line each. The shape (the lines are illustrations, not rules):

    Into presets/youtube/default/:
    1. A price said out loud gets a punch cut, never a side card → creative-moves.md § 2   (round 2: "make the price hit")
    2. One sound per screen recording, on its first click → sfx.md § Density   (hand edit: 9 deleted)
    Into my-rules.md:
    3. A line said twice across takes: keep the last take
    Not baked: the sponsor's name card (this video only) · the export crash (a tool defect, reported)

Write only what the creator approves, as all, some or edited, each rule in the target doc's own style (its markers,
its WHY first where the doc opens every section with one) and dated. Then:

- Re-read every spot written. In the author's repo also run its link check and the test suites that read a touched
  doc (found by grepping the suites for the doc's name); both commands are in its CLAUDE.md § Folder Structure.
- Add one line to RUN.md: `Baked: <date> · <n> rules → <files>`.
- Report each rule and where it landed, one line each.
