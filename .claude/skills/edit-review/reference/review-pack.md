# Review pack: the step-5c reviewer brief (TEMPLATE)

Copy this file to `<JOB>/hf-graphics/review/PACK.md`, fill `<JOB>`, `<ROUND>`, `<FPS>` and `<BAND>`
once per job, and hand that copy to every reviewer. **Nothing here restates a rule.** Every list
lives in one file already; this pack points at it. A brief retyped by hand drops half a class
sooner or later, which is the whole reason this template exists.

## 0. Ground rules

READ-ONLY: never edit a job file, never render, never place. Job root: `<JOB>`.

## 1. Inputs

- The contract (fill in the graphic count): `<JOB>/graphics-plan.json`
- Word times on the finished timeline: `<JOB>/outputs/<job>.transcript.json`
- What is actually on the timeline: `<JOB>/hf-graphics/placement.json`
- PROVEN and off-limits as findings: `<JOB>/hf-graphics/qa-report.json` plus `<JOB>/hf-graphics/qa-waivers.json`
- Comp source: `<JOB>/hf-graphics/*/compositions/`
- Preset docs, the spec you check conformance against (long-form): `presets/youtube/default/default-overlay-style.md` ·
  `presets/youtube/default/creative-moves.md` · `presets/youtube/default/animations.md`.
  Short-form: the format's own style doc, named in `CLAUDE.md` § Format variants. Open the ones your
  dimension needs; the figures are not restated here.

## 2. Evidence

- Frames for this round: `<JOB>/hf-graphics/review/round<ROUND>/`
- Frame N is at N/`<FPS>` seconds.
- Per-graphic contact sheet: `sheets/<id>.png` inside that round dir.
- What was grabbed and why: the round's `INDEX.md`.

All of it is written by `uv run lanes/premiere/review-frames.py` on the Premiere lane. No other lane
has an evidence tool yet: grab the same frames in that app and keep the same file names.

## 3. What `graphics-qa.py` owns

Run `sed -n '1,/^"""$/p' workflows/graphics-qa.py` and treat every check in its `Checks` block as proven.
A graphic you believe is wrong in a class that script owns is reported as a **MISSING ASSERTION**
with its evidence, never as a per-graphic finding.

## 4. The valid finding classes

Open `.claude/skills/edit-review/SKILL.md` § Defect classes and use that list verbatim. It is not
copied here.

**Job specializations.** A job may NARROW a class; it never restates one.

- Classes tagged `[script]` in that list are the script's on every job, not reviewer findings.
- Long-form: class 2 is copy at the very edge of the frame, or the outro's right side and bottom
  blocked for end-screen cards. Long-form has no platform bands.
- Long-form: class 5 does not apply (captions are YouTube CC).
- Add any further narrowing this job needs, one line each, by class number.

## 5. Banned findings

Same file, same section, its **Banned findings** paragraph. Findings in those categories are
discarded unadjudicated.

## 6. This job's measured numbers

- Low band, from `uv run workflows/chin-line.py`: `<BAND>`
- Callout boxes: fill in from the plan.
- Anything else measured for this shoot goes here, so no reviewer guesses a number.

## 7. Finding format

One per line, no prose around it:

`<id> · <class number> · <frame file or timestamp> · expected: … · actual: … · fix: <one concrete sentence>`

End with: `CLEAN: <ids you checked and found nothing on>`
