---
name: graphics-plan
description: "Storyboards the graphics BEFORE any are built (step 5a, between the graded cut and the build): reads the finished-script transcript, builds a beat sheet, probes the footage, storyboards every graphic (exact copy, placement, timing, motion) and self-reviews the plan so the first pass ships at review quality. Outputs graphics-plan.{json,md}. Does NOT create graphics. Triggers: plan the graphics, graphics plan, where should graphics go, ideate graphics, what graphics for this, graphic direction, storyboard the graphics, beat sheet, plan visuals for this reel."
---

# Graphics Plan — beat sheet → storyboard → self-review

**Step 5a of the pipeline.** Rough-cut already produced the finished script (the cut-aligned
transcript). This skill turns that script into a **storyboard**: a beat-by-beat plan of
graphic-or-not, what exactly appears, where, when, and how it moves — *before anything is built*.
The creation step (5b) builds from this plan, captions included on short-form (see § The captions cell). The colour grade is step 4 and
is already on the timeline before this plan is written.

**The bar: one-shot quality.** The plan must be good enough that the build needs no
back-and-forth — every correction the creator would make on a review pass, this skill makes on itself
in Step 4 before you ever sees the plan. A plan that needs "you should have made this a graphic"
afterward is a failed plan, not a draft.

**This skill decides graphics. It does not create them.** No rendering, no HyperFrames, no HTML.

---

## 🔒 STEP 0 — resolve the preset + the tier (before any planning)

**The preset is decided by format, automatically.** The format is resolved at `edit-video` Step 0
(horizontal raw → long-form YouTube; vertical, or a landscape raw the ask calls a short → short-form,
Talking Head Explainer vs TikTok/raw read from the content) and written into RUN.md: read it there.
Each format has exactly one default preset, and presets are fully independent — read ONLY the
chosen preset's own docs, never another preset's:

| Format | Default preset | Read |
|---|---|---|
| long-form YouTube | `presets/youtube/default/` | its `README.md` + `default-overlay-style.md` + **`creative-moves.md` (the default vocabulary AND § THE DENSITY NUMBERS — the per-minute cadence you plan to)** |
| Talking Head Explainer | `presets/instagram/talking-head-explainer/` | `README.md`, then `layout.md`, `graphics.md`, `captures.md`, `captions-style.md` |
| TikTok/raw | `presets/tiktok/raw/` | its style doc — **hook card only, plan nothing else** |

**A named preset overrides the default** — "edit this in the Vox style" → `presets/youtube/vox-collage/`
(and its `motion-craft.md` craft layer), "liquid-glass" → `presets/youtube/liquid-glass/`. Only an
explicit name switches presets; nothing else does.

> **"Do a graphics pass" = the BASIC tier. Always. Assume nothing bigger.**

| Tier | Trigger | What it is |
|---|---|---|
| **Basic** ← DEFAULT | "edit this video", "do the graphics", "graphics pass" | the preset's `default-overlay-style.md`: face-clear cards plus its default scenes, captures and prompt demonstrations; 4–7 is the card ceiling, not the whole graphics pass. |
| **Full** | asked for **by name** — "go all out", "full graphics pass", names a look | takeovers, bespoke art, higher density, whatever the named preset's doc says |

**The Talking Head Explainer has ONE tier: its whole vocabulary IS the default** (its README § What this
preset changes, (f)). The layout rotation, real captures, the montage, the call card and full-screens
within [`layout.md`](../../../presets/instagram/talking-head-explainer/layout.md)'s caps are default work:
state their seconds in the plan summary, never ask. Beyond those caps, ask as below.

**A tier is never inferred from how good the footage is.** An exciting script is not permission to
escalate. When a beat genuinely wants more than the tier allows, note it in the plan in one line
and plan within the tier anyway — upgrading is your call.

**Two things require an explicit ask (one line, at plan time, never mid-build):**
1. **Decorative extended full-frame coverage** — takeovers outside the preset's default vocabulary,
   bespoke art, background replacement. State the total second-count and get a yes unless already
   authorized. Short punch-cuts, real evidence captures and full-screen prompt walkthroughs are
   long-form DEFAULT work: plan them without asking. Required demonstrations last for their spoken
   explanation; track those seconds separately from the decorative coverage budget.
2. **A non-default look** you didn't already name.

---

## Step 1 — the BEAT SHEET (understand the video before decorating it)

```bash
uv run .claude/skills/graphics-plan/scripts/segment-script.py projects/<job> /tmp/video-editor/<job>/beats.json
```

That gives the mechanical grid (sentence beats + timestamps). The beat sheet is what you ADD to it —
read the whole script first and answer, in order:

1. **The arc.** What is this video actually about, in one sentence? What are its 2–3 biggest
   moments (the hook, the core reveal/demo, the payoff)? The storyboard is built around these;
   everything else supports them.
2. **Per beat, its narrative role:** `hook` · `promise` · `setup` · `point` · `evidence` ·
   `demo` · `payoff` · `punchline` · `transition` · `aside`. Merge or split the mechanical beats
   freely when the story says so — the grid is a starting point, not a contract.
3. **Per beat, the showables:** every concrete noun the line contains — a number, a name, a
   product, a process, a before/after, a list. These are the graphic candidates. A beat with no
   showable almost never earns a graphic.

**Read the original request and all later corrections alongside the script.** A transcript cannot
tell you the exact written prompt, which of your own pages or accounts a line points at, or whether
the closing lines hand off into another video. Resolve those sources before assigning visuals. Put
each required demonstration and its source in the relevant cell's `content`/`capture`; unresolved
source access is a recorded gap, never silent permission for a generic substitute. Re-run this
mapping after cuts restore or add footage, through the final kept sentence.

Write the roles into the plan (`role` field). The beat sheet IS the first deliverable — a wrong
beat sheet makes every downstream choice wrong.

## Step 2 — look at the footage (never storyboard blind)

```bash
uv run .claude/skills/graphics-plan/scripts/probe-frames.py projects/<job> /tmp/video-editor/<job>/beats.json
```

One frame per beat lands in `projects/<job>/plan-frames/` (regenerable scratch — re-runnable at any
time. Works from the flat render or, on app-finish jobs, straight from
the raw via the EDL). Actually look at them. **They are planning evidence, never assets** (§ THE
HERO-FRAME GATE): a beat frame is grabbed on the word the beat starts on, so it is a mid-word face by
construction. They decide:

- **Screen-recording beats already show the thing** — a demo that's on screen needs an annotation
  or nothing, never a card summarizing what's visible. This is the #1 wasted-graphic mistake.
- **Placement** comes from where you actually is in frame (side to place a card, where your head is),
  not from a guess. **A side callout's zone is MEASURED over the beat's whole window**, never read off
  one frame: `uv run workflows/chin-line.py <raw> --edl <cuts.json> --from <start> --to <end> --step 0.1`
  prints the head's extent (ears included, worst frame), the two zones and the side with more room
  (preset § SIDE CALLOUTS). The cell records what it measured as `head`.
- **Gestures** — a point/hold toward one side is an anchor for that beat's graphic.
- **Energy** — a big delivery moment on camera may land harder plain.

## Step 3 — STORYBOARD the graphics (the creative core)

Walk the beat sheet in story order and decide each beat. **Big moves must earn their slot** — a
full graphic gets planned only when:

- it's the **hook** (the hook always gets the strongest visual in the video),
- it's a **payoff/punchline** worth underlining,
- it has a **showable** the frame isn't already showing (stat, name, list, process, artifact),
- it's a **structure beat** a diagram/flow would make instantly clearer.

**Density and rhythm are the preset's (2026-08-29; the spread 2026-09-10)** — long-form (youtube/default): `creative-moves.md` § THE DENSITY
NUMBERS owns every figure (the per-minute cadence, the full-screen SPREAD of never 40 s without one, the
bare-stretch bound: **plan to 6 s**), and § Rhythm owns the law (a visual every ~10 s floor, continuous
coverage while the script describes something visual, text animations filling every gap); a payoff LINE
gets the bg-light TEXT punch-cut, an artifact or process the dark one (move 2). `validate-plan.py` and
`graphics-qa.py` warn on them. The 4–7 card budget still scopes the CARD count per intro/section; pops and
creative moves ride on top, uncounted. The Talking Head Explainer plans its layout rotation instead
([`layout.md`](../../../presets/instagram/talking-head-explainer/layout.md) § 15, no card budget; a
full-screen is layout mode F, never a punch-cut kind, at most 2 per 120 s, § 2 and § 12; outcome density:
[`graphics.md`](../../../presets/instagram/talking-head-explainer/graphics.md) § 16); TikTok/raw: exactly the
hook card. Full-tier densities live in the chosen preset's own doc.

Leave BIG moves off connective tissue, transitions, asides, emotional delivery and rhetorical setup:
those land harder on your face (on long-form a bare stretch still gets its text animation). **Never let
two graphics collide on adjacent short beats**: merge them or let one breathe. **Two cells in the SAME
`region` may never overlap in time** — a region is ONE slot, so the second clamps the first mid-shot
(`validate-plan.py` FAILS the pair; a collision across two different regions still only warns, and is
stated in `content`).

**Own B-roll cutaways** (cells carrying `broll_source`, written by `workflows/broll-place.py apply`: the
`broll-own` skill) are kept as they are and planned around: nothing but the caption layer overlaps one
(`validate-plan.py` FAILs it). They exist only on a preset built for B-roll (its `broll.json`; the shipped
presets carry none): there, place them right after Steps 1-2, before the storyboard.

**When part of the video is off-limits to graphics** — by default every stretch of screen-recording
FOOTAGE (raw walkthrough/demo footage; a screen-recording GRAPHIC you capture is a normal cell:
`presets/youtube/default/README.md` § Screen-recording footage stays bare) — the
plan says so MACHINE-READABLY, or the cadence is measured against runtime it may never fill:
`"graphics_scope": {"ranges": [[0, 46.92], [618.95, 765.1]], "why": "no graphics over the screen
recording"}`. Both gates measure density, the bare stretch and the full-screen spread over those ranges
only (`creative-moves.md` § THE DENSITY NUMBERS owns the numbers), so a barred stretch is not a hole and
the cadence INSIDE the sections you do decorate is held to the real figures.

**Spend the creativity where it counts.** For the hook and each major payoff, draft **2–3 distinct
options** and keep the strongest (say why in one clause). Ordinary beats get one good idea, not a
brainstorm. Visuals over text everywhere: the motion/footage/data carries the point; words are a
label, a number, or a hook line. Reserve text-forward cards for hook + punchlines, and remember
**captions are the top layer of this same step** (short-form) — don't fill the frame with text a caption will collide with.

**Every `graphic:true` beat is a complete storyboard cell** — the build must need zero guesses:

- **`kind`** — from the vocabulary below, **`template`** — which of the preset's templates it uses (long-form
  youtube/default, basic tier; the Talking Head Explainer has no templates: its `family` and its layout row decide).
- **`copy`** — the EXACT on-screen words/numbers. Not "a stat card about the revenue" — `"$4,700 / mo"`.
  A stage direction inside `copy` goes in  or < > and must contain a lowercase word (`(masked dots)`,
  `<rotating word>`): `graphics-qa-short.py` only warns when those words are missing. A parenthetical
  whose every word is capitalised (`(Full Guide)`) is treated as on-screen copy and FAILs when it is not
  read. A word that exists on screen only as a logo goes in the cell's
  `copy_ocr_skip` list; any other `copy` word of 4+ letters that OCR cannot read FAILs
  `graphics-qa-short.py`.
- **`region` + side** — from the Step-2 frame, inside the format's safe zones. **On long-form,
  anything CENTERED under your head goes in THE LOW BAND** (`presets/youtube/default/default-overlay-style.md`
  § THE LOW BAND): the whole stack fits between the measured chin floor and the bottom margin,
  and a two-line block is therefore SMALLER and LOWER than a one-liner. Record the measured band in
  the plan as `low_band {top, bottom, chin_measured}` — it is what `graphics-qa.py` holds every
  under-the-face overlay to; omitted, the gate falls back to the 2026-08-31 shoot's 765/1030. A
  `callout-L` / `callout-R`
  cell carries `head` (`{left, right, frame}` from `chin-line.py --edl` over ITS window — copy
  chin-line's own `frame`, which normalises a 4K measurement into the authoring frame), sits on the
  side with more room, and is as wide as that room (cap 620); `validate-plan.py` fails a callout cell
  without a measured head. Full-screens have no face to clear.
- **`start` / `end`** — snapped to word timestamps: in ON the word that names the showable (not the
  sentence start), out before the next thought begins. 2–5s on screen for a CARD; a card that overstays reads as a mistake.
  A SCENE that depicts an unfolding process runs as long as the process does (the shipped chat
  ping-pong graphic holds 8.6s) — the limit there is the beat, not the clock. **Name the anchor
  word and its transcript time in `content` for every cut-in and word-synced entrance** ("cut in
  ~30 ms before 'one' 4.41"): the hook on your-job was first computed off "shot," because the
  phrase was read as a unit; the validator WARNS on a cut-in that leads no spoken word and sits on no
  V1 cut, and `"anchor": "none"` + the reason in `content` is how the plan answers it. **A READABLE graphic needs more:** if the beat shows something the
  viewer is meant to read or screenshot (a prompt, a command, code, a config, a quote), the slot
  must fit a **2–3s hold of the COMPLETE content** on top of its reveal — say so in `content` and
  size the slot for it, or flag `⚠️` that the text is too long for the beat. For a prompt walkthrough,
  `source_artifact` names a job-relative UTF-8 file containing the complete original written artifact — copy
  the original text into the job folder (`assets/`) when it lives outside it; `copy` matches that file in
  full, and any readable cell whose words come from a written artifact names it (the validator checks both).
  `content` names the source provenance and maps spoken anchors to the actual highlighted
  clauses. Its full-screen slot covers the entire explanation, not merely the minimum hold
  (`creative-moves.md` § 4d).
- **`content`** — one tight paragraph: what's on screen, the hierarchy, the hero element, and the
  motion (what animates, in what order). Written so the build step can build it without asking.
- **`reason`** — why this beat earns it (the second pass reads these).
- **`phases` + `visuals`** (full-screen / punch-cut cells only) — a full-screen is a SCENE
  (`creative-moves.md` move 2 § A FULL-SCREEN IS A SCENE, you 2026-09-10): `"phases"` lists at least
  two visual beats with comp-relative times (`[{"at": 0, "what": "the wall is back, struck through"},
  {"at": 1.83, "what": "racks out under the type"}]`), `"visuals"` names at least one element that
  is not type (a picture, an artifact, a prop, a diagram, a UI), and `content` names the camera move
  and, when type lands over the scene, the rack focus. `validate-plan.py` fails the cell without them.
- **`hero_frame`** (any cell that shows a real frame of this video: a player window, a thumbnail
  card, a footage still) — `{"t": <raw seconds>, "file": "assets/<id>-frame.jpg"}`, both written by
  `workflows/hero-frame.py --pick` after the pick is made BY EYE off its contact sheet (§ THE
  HERO-FRAME GATE). Never a `plan-frames/` file, never a hand `ffmpeg -ss` at a word.
- **`bg`** (full-screen / punch-cut cells only) — ALWAYS written on a full-screen cell
  (`validate-plan.py` fails it otherwise); `"dark"` unless the visual reads better light (2026-09-10; no rotation). It is not decoration: it
  drives locked render flags (**bg-dark = `STEP_FPS=12` + the glow pass; bg-light = neither**).
- **`push_in`** (long-form A-roll beats) — `true` where the footage should push in on the
  emphasized phrase (numbers: the preset README § Emphasis push-in; when to reach for it: `creative-moves.md` move 5). This is a
  DEFAULT move, so plan it rather than waiting to be asked, but ration it: **2–3 per minute of
  runtime, spread** — none closer than ~7 s, no long stretch without one, on the beats carrying the
  strongest claims (`creative-moves.md` § THE DENSITY NUMBERS owns the figure; `validate-plan.py` prints the rate).
  Pick them from the SCRIPT — the line that lands the claim, the reveal, the stakes — and pair each
  with the text animation of that phrase. Everything else stays still; a push-in on every emphasis
  reads as a wobble.
- **`entrance`** (`text-animation` cells only) — omit for the default rise; `"slam"` by name for the
  punchline that has to hit. **Never `pop`/`punch`: type never pops**
  (`presets/youtube/default/animations.md` § TEXT NEVER POPS); `validate-plan.py` fails the cell.

| Kind | Use it for |
|------|-----------|
| `screen-rec` | the thing actually working — a demo, the agent running, a folder, an app state, a click (real footage with real continuous motion — a scroll, a navigation, a UI action — not a card and not a still given a move). No file yet → the cell carries `capture` and the BUILD records it (§ THE CAPTURE GATE below) |
| `b-roll` | illustrative motion footage over a claim (generate one with your AI-video tool if none exists); the creator's OWN footage goes through `broll-own`, which writes these cells itself (`broll_source`) |
| `screenshot` | the real artifact — a post, a report, a DM (zoom/pan/annotate it, never park it). No file yet → `capture` with `"still": true` (a covered-window grab, the app is never fronted) |
| `diagram` / `flow` | how it works — steps/pipeline, drawn ON as you talk |
| `data-viz` | numbers in motion — a chart drawing in, a count-up, a ranking |
| `stat-callout` | a single number as a beat — counted up / popped, never static |
| `icon-row` / `list` | a set of things, revealed in sequence |
| `quote` / `comment` | a comment, tweet, DM, testimonial |
| `lower-third` | a name / title / label (long-form) |
| `kinetic-title` | hook + punchlines only — the words ARE the payoff |
| `text-animation` | long-form's default sprinkle — word-synced emphasis text in the low band (the rhythm-law filler; uncounted against the card budget) |
| `punch-cut` | long-form default: hard cut to a short full-screen graphic on a locked background at a power phrase, hard cut back (creative-moves move 2) |
| `annotation` | arrow/highlight/circle pointing at something already on screen |
| `enacting-overlay` | the line is about the FOOTAGE itself (recorded, filmed, captured, live) — add capture UI (viewfinder brackets, a REC dot, a timecode) so the untouched shot reads as that thing, plus a text animation for the words. Purely additive, face never covered, no transform on the footage. Model: g20 |

**🔒 THE CAPTURE GATE (2026-09-11) — a screen capture is PLANNED, never improvised, and TEXT IS NEVER
CAPTURED.** A beat gets a `screen-rec` / `screenshot` cell with `capture` when the line points at a real
thing on your screen that IS the evidence and cannot be re-typed: a folder tree, an app's state, a click
you describes making, a timeline filling up, a page that exists. The build records exactly that (Stage 2)
and the comp builds it as a scene to the preset's look (each preset's own doc: long-form
`default-overlay-style.md` § SCREEN-REC SCENES, straight frame, label and arrow on the label's side,
bg-light; the Talking Head Explainer
[`captures.md`](../../../presets/instagram/talking-head-explainer/captures.md)) — never parked full-frame. It does
NOT apply when the content is words: a prompt, a command, a config, a quote is REBUILT word for word from
the exact written source as a graphic (house type, highlight phases, the readable hold), because a screenshot of a
chat window gets none of that. A list of tool NAMES is a card, not four screen grabs. And a beat whose
footage already IS a screen recording needs an annotation or nothing (Step 2). When a line names a
specific real destination — a page, an account, a product, a place something is downloaded from — the
capture is THAT destination itself; a generic badge, a stock icon or a public marketing page for the
same brand is not it. **One exception, on the Talking Head Explainer:** a live product chat whose REPLY is
the evidence (an agent answering, a bot confirming what it did) is captured, not rebuilt, because the
product's own answer is the proof ([`captures.md`](../../../presets/instagram/talking-head-explainer/captures.md) § 1).
**On long-form, a recording SECTION is planned as mostly recordings, the mouse doing the pointing, files in Finder list
view and never opened, every process shown whole, every name-check the real page, takes as long as their line, and no
camera shot under a second between two recordings** ([`presets/youtube/default/README.md`](../../../presets/youtube/default/README.md)
§ Recording sections SHOW it, you 2026-10-05). The camera keeps only the side comments, opinions and punchlines.
The cell says what to capture and what happens during the take:

```json
"capture": {"source": "url", "target": "https://github.com/heygen-com/hyperframes", "action": "the repo landing page, the README scrolling slowly through the take", "scroll": 900, "dark": true, "seconds": 6}
"capture": {"source": "app", "target": "Finder", "action": "the repo root in list view, presets/ expanded", "still": true}
```

`source` is `url` (a page: recorded HEADLESSLY by `workflows/page-record.mjs`,
never through your live browser — a `scroll` in px and `dark` ride in the cell) or `app` (a running app's
biggest window, `index` for another, recorded on screen by `workflows/screen-record.sh`); `seconds` is the
take (recordings only); `still` makes it a screenshot cell's grab.

**The Screen Studio route is opt-in PER MACHINE (2026-10-02).** Where the repo-root `.env` sets
`VE_SCREEN_RECORDER=screen-studio` (a machine that owns Screen Studio; a client opts in with the same key,
everyone else keeps the default route above), a RECORDING capture, `app` or `url`, is taken through Screen
Studio and lands as a FULL-FRAME B-roll scene in Screen Studio's own look: its default preset's wallpaper,
rounded window and shadow, the smooth cursor, and the zooms the take scripts. The SCREEN-REC scene (drawn
frame, label, arrow) does not apply to it. Plan it like any capture cell, with a full-screen layout. Its
`action` is written as the moves the take makes, and it names the push-in: what the zoom lands on, and when it
pulls back to reveal. Stills keep `window-grab.sh` / `page-record.mjs`. How: `graphics-build` § Stage 2.

**Every live-app take runs behind the preflight:** `./workflows/screen-record.sh --preflight
projects/<job>/pii.json [--bounds W,H] <App> <out.mp4> <secs>`. The `pii.json` carries `phrases` (the
session's own staging prompts, and any figure or label that must not ship: a stem catches every ending),
`needles` (numbers and keys) and `any_number: 7` wherever a phone could be on screen (how each matches:
`workflows/pii-scan.py`'s docstring; the job's list: `edit-video` § Step 0, item 9). The preflight makes two grabs: the window's own buffer before anything is fronted, then, after
the app is fronted, the screen rect the take records, which is the grab that sees a dialog, a banner or
another window drawn over the window. Exit 4 = one of them shows forbidden text: clear it and take again,
never record around it. The gate only sees the screen as the take starts, so sweep each take afterwards
with `uv run workflows/pii-scan.py projects/<job> --raw assets/captures/<take>.mp4 --all` (its own
`review/pii-scan-<take>.json`). A take is exactly the seconds asked (a window that stops changing holds
its last frame). A cell that names a window size carries `bounds`, and the take passes
`--bounds W,H[,X,Y]`: `screen-record.sh` sets that size for the take, refuses it if the app will not take
the size, and puts the window back afterwards, even if the take is killed.
A page behind a login is planned as `source: "app"` with the browser as `target` and the real URL
stated in `action`; the build records it (`graphics-build` § Stage 2). A redirect to a sign-in or
sales page is not evidence of the real thing.
`validate-plan.py` fails a `screen-rec` / `screenshot` cell that has neither an `asset` already in the job
folder nor a `capture`. **An `asset` is job-relative and a capture lives at
`assets/captures/<id>.{mp4,png}`** — the copy under `hf-graphics/gfx/assets/captures/` is the render
base's working copy, never the original (owner: `graphics-build` § Stage 2).

Three things every capture cell answers (2026-09-19 — all three shipped wrong on one video):

- **A capture is proved to SHOW the thing.** The cell carries `"shows"`: one line naming what must be
  visible in the frame for it to be evidence (the panel open with the row it is about in it, the
  command's output on screen, the list populated). A spinner, a
  skeleton, a blank page, a half-loaded list or a mid-transition state is NOT that thing: the take is
  redone, never cropped around. This holds just as hard for a cell reusing an `asset` cut out of
  existing walkthrough footage — a dashboard full-screen shipped as a loading spinner over a blank page
  from exactly that route. A `url` capture states its readiness as `"ready"` (a CSS selector that must
  exist) and/or `"ready_gone"` (the spinner that must not), which `page-record.mjs` asserts before it
  records anything (`graphics-build` § Stage 2 passes them as `--ready` / `--ready-gone`).
  `validate-plan.py` warns on a capture cell with no `shows`; what the frame actually shows is read by
  the build and by `edit-review` class 1k.
- **A `url` capture is a PAGE, never a browser window** — no tabs, address bar or bookmarks in the
  frame. When the only route is `source: "app"` through the signed-in browser, the window is
  full-screened for the take and the cell SAYS the frame carries chrome; the comp is not the place that
  gets discovered (a 273 px chrome height was measured and cropped in CSS after the fact).
- **An annotation over a capture is REGISTERED, never authored by eye, and its capture HOLDS STILL.**
  The target's rect comes from `page-record.mjs --find "<text>" --rects <id>.json` (or a measured frame
  for an app capture), and a capture that scrolls under a circle, underline or marker drifts off its
  target: `validate-plan.py` fails a cell that puts one over a `capture` with `scroll` > 0. Either the
  take holds still, or the annotation goes.

### THE HERO-FRAME GATE — a still of the creator is CAST, never grabbed (2026-09-13)

A graphic that shows a REAL frame of this video (a player window, a thumbnail card, a "this is the
footage" still) is a cell with `hero_frame`, and the frame is chosen by MEASUREMENT, never pulled at a
word: a frame grabbed where a beat starts is a mid-word face by construction, eyes half shut, the mouth
caught between two sounds (a demo run's hook shipped one past three review rounds and the gate:
the engineering archive).
`plan-frames/` are planning evidence (composition, where your head is), NEVER assets, and the validator fails
any cell that names one.

```bash
uv run workflows/hero-frame.py projects/<job> --id g1                 # scores every KEPT frame → review/hero-frames/g1.sheet.jpg + g1.candidates.json
uv run workflows/hero-frame.py projects/<job> --id g1 --pick 45.337   # the chosen frame → assets/g1-frame.jpg + review/hero-frames/g1.pick.json
```

The picker decodes the raw and scores ONLY the EDL's kept spans (so the still is a frame of the EDITED
video) with MediaPipe face mesh: eyes open (eye aspect ratio ≥ 0.20), mouth closed (mouth aspect ratio
≤ 0.06), iris centred (≤ 0.06 off), frontal (yaw ≤ 0.25), a hint of smile rewarded; the top candidates
go on a labelled contact sheet. **Look at the sheet and pick BY EYE** — the score RANKS, it does not
choose (a grimace scores fine); check the neighbouring frames at full rate when the winner is close.
`--pick` re-measures that exact frame, refuses one that fails a threshold, extracts it at full
resolution and writes the proof. The cell carries `"hero_frame": {"t": 45.337, "file":
"assets/g1-frame.jpg"}`; `validate-plan.py` requires the proof to exist, pass and match, `graphics-qa.py`
holds the comp's `<img>` to that file, and `edit-review` class 1f reads the render for what no
threshold catches. Either a cast frame or a different visual entirely; a "good enough" grab is neither.

**Long-form structure beats** are part of the plan too: the section title cards, the cold-open, and
chapter boundaries come from `presets/youtube/default/README.md` — the storyboard places graphics
AROUND that structure (a section's cards cluster early in the section where its claim lands).

**Safe zones (short-form, never break):** open the preset you are on — the bands are its own doc's
(the Talking Head Explainer [`layout.md`](../../../presets/instagram/talking-head-explainer/layout.md) § 8;
TikTok/raw § THE LOOK), not restated here. **Long-form has NO
platform safe bands (retired 2026-08-27):** the rules are never cover the face or important
on-screen content, 80 px breathing room at the frame edge, 60 px between a side callout and the
head (ears included, measured per window — preset § SIDE CALLOUTS), right side + bottom clear
during an actual end-screen window, and every under-the-face overlay inside THE LOW BAND (measured per
shoot with `workflows/chin-line.py` — spec in the preset's `default-overlay-style.md`).

## Step 4 — SELF-REVIEW (run the review pass the creator would otherwise run)

Re-read the finished storyboard top to bottom as a reviewer, not the author. Fix everything below
BEFORE writing the plan — these are the exact corrections past first passes needed:

1. **Missed requirements/showables** — compare the original request, later corrections and full
   kept script to the storyboard, not merely the storyboard to itself. Every required prompt,
   real named destination and closing beat has the right content and full time coverage?
   Any number, name, list or artifact got no graphic and no `reason` for staying plain?
2. **Wasted graphics** — any card restating what the frame already shows (screen recordings!), or
   summarizing instead of showing?
2c. **A line about the footage itself given a CARD?** "I recorded this", "I filmed the whole
   thing", "this is live" — those want an `enacting-overlay` (capture UI over the untouched
   shot + a text animation), which enacts like a scene at a card's cost. See
   `default-overlay-style.md` § the overlay that enacts.
2b. **Card where a SCENE was needed** — for every `graphic:true` beat, does the line state a
   fact/number/name (card) or describe an action/process/back-and-forth (scene that shows it
   happening)? A card on an action beat narrates instead of depicting. The tell is decoration
   shaped like data — a meter with no scale, a bar with no metric. See
   `presets/youtube/default/default-overlay-style.md` § CARDS NAME, SCENES ENACT.
2d. **A real thing on your screen given a drawn stand-in, or words given a screenshot?** A folder, an
   app state, a click, a page that exists wants a `capture` cell (§ THE CAPTURE GATE); a prompt,
   command or quote is rebuilt verbatim from its written source as a graphic. For a prompt
   walkthrough, verify complete text, continuous full-screen coverage and spoken-clause highlights.
3. **Rhythm** — graphics evenly clumped or breathing with the story? A payoff needs a beat of air
   after it, not a new CARD on top of it, and no two cards butt end-to-end. **Text animations are
   exempt** — they are the connective tissue that keeps the ~10s floor, and they legitimately run
   back to back. Check the plan against `creative-moves.md` § THE DENSITY NUMBERS — that table is
   the one home of the figures, and `graphics-qa.py` and `validate-plan.py` enforce it. Review
   dark full-screen scenes across the whole runtime, including new/restored outro footage; a
   cluster of light recordings does not replace the preset's dark scene vocabulary.
4. **Variety** — three of the same template in a row reads as a stamp. Vary template, side, and
   scale across neighbors.
5. **Timing** — does each `start` sit on the word that earns it? Does anything overstay? A visible
   change INSIDE a graphic that must land on a word (a send, a reply, a card) names that word in the
   cell's `sync` list (schema below), which `workflows/change-events.py --sync` checks on the render.
6. **Copy** — labels are short and in your voice (no marketing speak, no em dashes in authored
   copy); source artifacts retain their complete text, punctuation and case. **Case depends on what the copy IS:** captions and
   text animations stand in for speech and keep the lowercase-casual register; a LABEL inside
   a graphic (card title, nameplate, eyebrow, axis) is not speech and takes title case.
   A leading article drops only when the label NAMES a thing ("Claude Video Editor", never
   "the claude video editor") — in a short descriptive label the article is part of the
   phrase and stays ("The Goal", the eyebrows THE BUILD / THE RULES). Test: answers "what
   is this thing called?" → drop it; answers "what is this number/row?" → keep it
   (default-overlay-style.md § Copy case, you 2026-08-31).
7. **Scope** — long-form (youtube/default): count per section within tier, zero unplanned full-frame; every format:
   overlays never cover the face, captions zone clear (short-form). The Talking Head Explainer's scope is its layout
   gate (`layout.py --check`: the F caps, the face share, the card clearance).
7b. **The band** (long-form) — every under-the-face cell sits inside the low band, and no cell
   is sized as if it had the whole frame. If a beat's copy needs two lines, the plan says two
   lines and expects smaller type; it does not ask for big type AND two lines.
8. **The two asks** — full-frame seconds + non-default look, each stated in one line if present.

Revise the plan, then output. If a beat is genuinely 50/50, keep your call and flag it `⚠️` — one
flag you can answer beats a timid plan.

## Step 5 — write the plan + report

**The gate (2026-09-02): a plan that fails this is not PRESENTED.** The order is: write
`projects/<job>/graphics-plan.json` → run the validator → fix and re-run until it exits 0 → then
write `graphics-plan.md` and report.

```bash
uv run .claude/skills/graphics-plan/scripts/validate-plan.py projects/<job>
```

What it asserts is its own docstring (`sed -n '1,/^"""$/p'` on it): text-animation anchors, full-screen edges
on the cut to the frame, readable holds and `source_artifact`, copy (no em dash, the lowercase register for text
animations), shape (one cell per `region` at a time), the list-card and callout-crop caps, captures, hero frames,
the density block and, on the Talking Head Explainer, `layout.py`. A text-animation cell longer than 8.0 s FAILS
(a start anchored to the wrong occurrence of its first word, g11, 2026-09-04). Two things it cannot check are
yours: **a full-screen edge far from any cut passes**, so when the graphic's own line runs on to an edit within
about a second, end on that edit, never on a word-time estimate (f06 cut back mid-"Sonnet 5.5" 0.68 s short and
passed, 2026-10-06); and **text-animation copy is written AS IT WILL BE SPOKEN** (the builder matches the
transcript verbatim; a filler mid-phrase is skipped automatically, a paraphrase is not).

The two reviewed artifacts in the job folder:

- **`projects/<job>/graphics-plan.json`** — machine-readable, consumed by the build (schema below).
- **`projects/<job>/graphics-plan.md`** — the storyboard for your review, and what the second pass
  edits: the arc line, the beat sheet, then per-graphic cells (`# · time · line · role · template ·
  copy · placement · motion · why`), plain beats listed with their reasons.

Report tight: **the preset + tier**, the arc in one line, beats total / graphics count,
**face-covered seconds**, the 2–3 strongest cells, any `⚠️` flags, and the explicit asks if any.

### `graphics-plan.json` schema

The example below is a LONG-FORM plan (youtube/default): `tier`, `template`, `region`, `bg`, `push_in`, `low_band`
and the chip in its hook are long-form fields and looks. The Talking Head Explainer's plan follows
[`layout.md`](../../../presets/instagram/talking-head-explainer/layout.md) § 12 and its own example (§ The Talking Head
Explainer plan below); the shared fields (`id`, `start`, `end`, `line`, `role`, `graphic`, `kind`, `copy`, `readable`,
`capture` / `asset`, `shows`, `sync`) mean the same on both.

```json
{
  "job": "your-job",
  "format": "long-form",
  "tier": "basic",
  "preset": "presets/youtube/default",   // the chosen preset's folder (or its style doc)
  "compositor": "premiere",   // the app finish; "resolve" | "capcut" | "finalcut" | omit = chat-only
  "duration": 136.56,
  "graphics_scope": {"ranges": [[0, 46.92], [618.95, 765.1]], "why": "you: no graphics over the screen recording"},   // only when part of the video is off-limits: both gates measure the cadence over these ranges, never the runtime

  "timeline_offset": 152.694208,   // a SECTION sub-job only: where its clips start on the sequence; plan times stay section-relative, the lane's placer and SFX tools add it at the app boundary (2026-09-14)
  "fps": "24000/1001",             // a section whose raw runs at another rate than the sequence (a 30 fps screen recording on 23.976): the tools snap to THIS grid, never the raw's
  "arc": "one sentence: what the video is and its biggest moment",
  "face_covered_seconds": 0,
  "low_band": {"top": 773, "bottom": 1030, "chin_measured": 703, "note": "chin-line.py sweep of the raw: lowest jaw y703, floor = chin + 70"},   // long-form: the MEASURED band, what graphics-qa.py holds every under-face overlay to; omit on short-form
  "beats": [
    {
      "id": 1, "start": 0.05, "end": 5.03,
      "line": "I just built this Claude skill that can predict exactly what you need to post to go viral.",
      "role": "hook",
      "graphic": true,
      "kind": "kinetic-title",
      "template": "label card",
      "region": "top-half",
      "copy": "predict what goes VIRAL",
      "content": "Hook title, hero word 'VIRAL' in a royal boxed chip that stamps in last; two-line stack, stepped entrance.",
      "phases": [{"at": 0, "what": "the two-line stack rises in"}, {"at": 1.2, "what": "'VIRAL' stamps into its chip, stack racks back"}],
      "visuals": ["the royal chip prop behind the hero word"],   // full-screen/punch-cut cells: ≥2 phases, ≥1 non-type visual
      "bg": "dark",            // full-screen/punch-cut cells (long-form); omit on short-form
      "entrance": "slam",      // text-animation cells only; omit = rise. never "pop"
      "push_in": false,        // long-form A-roll only; omit on short-form
      "part_of": "g8",         // continuation cells only: a graphic split for BUILD reasons is planned as part cells, the stem cell carrying the scene fields and each continuation carrying "part_of", validated as ONE graphic
      "source_artifact": "assets/original-prompt.txt", // required on any readable cell whose words are a written artifact; omit only for authored labels and captured files, copy must match this complete file
      "readable": false,       // true when the viewer is meant to READ it (prompt, code, quote): the slot must hold ≥ 3.0s on long-form and every other preset; on the Talking Head Explainer the read holds about 2 s once whole, a WARN never a FAIL (talking-head-explainer/graphics.md § 13)
      "capture": {"source": "url"|"app", "target": "https://…"|"Finder", "action": "what happens during the take", "seconds": 5, "scroll": 900, "dark": true, "index": 1, "still": false, "ready": ".list-row", "ready_gone": ".spinner"},   // screen-rec / screenshot cells with no file yet: the build records it (§ THE CAPTURE GATE); "ready"/"ready_gone" are the CSS selectors page-record.mjs asserts before it records; or "asset": "assets/captures/g20.mp4" for a file already in the job
      "shows": "the list populated, the row this beat names in it",   // every capture cell: what must be visible in the frame for it to be evidence (a spinner or a blank page is not it)
      "crop": {"w": 1200, "h": 900},   // a side callout carrying a capture/still: the framing is a plan decision, and it fills the 620x560 slot
      "anchor": "none",        // a full-screen cut-in that leads no spoken word and sits on no cut: say so here and why in content, or the validator warns
      "sync": [{"word": "sent"}, {"word": "retention", "offset": 0.25}, {"word": "add", "expect": "first change", "nth": 1}],   // the words a visible change inside this graphic must land on (a send, a reply, a card); `word` can be a phrase; `expect` "change" (nearest shown event, default) or "first change" (the entrance); `offset` a DESIGNED lag in s (a lead is negative); on a kit cell leave it out to use the met kit row's recorded sync_offset, and a named one must equal it; `nth` a whole number from 1 picking among repeats inside the row's span; `source` "kit" | "render", the clock the anchor is checked on: default kit on a kit cell (family authored/overlay with `src: kit` rows in hf-graphics/sfx-hand.json) for "change" anchors, render on captures and montages and for every "first change" (the entrance); any other value is a BAD ANCHOR. Checked by workflows/change-events.py --sync
      "hero_frame": {"t": 45.337, "file": "assets/g1-frame.jpg"},   // any cell showing a real frame of this video: cast by workflows/hero-frame.py --pick, picked by eye off its sheet (§ THE HERO-FRAME GATE); never a plan-frames/ file
      "reason": "the hook — must open on the strongest visual in the video"
    },
    {
      "id": 2, "start": 5.17, "end": 6.49,
      "line": "And yeah, it works.",
      "role": "punchline",
      "graphic": false,
      "reason": "delivery beat — lands harder on your face, air after the hook"
    }
  ]
}
```

Keep `graphic:false` beats in the array (with `role` + `reason`) so the plan is a complete map of
the script — the second pass needs the plain beats too.

---

### The captions cell (short-form presets, on by default — 2026-09-04)

Captions are a graphic of this step, not a pass. On `instagram/talking-head-explainer` and `tiktok/raw` the plan
carries ONE extra cell spanning the whole cut, and the build lays it on the top graphics track like
any other overlay (long-form never has one — YouTube CC):

```json
{ "id": "captions", "start": 0, "end": <plan.duration>, "graphic": true, "kind": "captions",
  "region": "captions", "content": "the preset's locked caption layer (Talking Head Explainer: on the seam in split, collar + 40 on the face · tiktok/raw: low under the face), built by the preset's caption builder (tiktok/raw: build.py --alpha; Talking Head Explainer: `uv run presets/instagram/talking-head-explainer/captions.py projects/<job>`, which reads transcript/voices.json for a second voice)" }
```

On the Talking Head Explainer the cell may also carry `"join": ["et cetera", …]` (a spoken phrase kept on one
caption line) and `"y": {"wide": px, "tight": px}` (a measured, approved height): [`captions-style.md`](../../../presets/instagram/talking-head-explainer/captions-style.md).

`validate-plan.py` keeps it out of the density, overlap and anti-stale maths; the lane's placer derives
its row from `hf-graphics/captions/renders/captions-alpha.mov` onto a track above every other overlay
(which track is the lane's business: [`LANES.md`](../../../LANES.md) § step 5); `sfx-plan.py` ignores
it (captions are silent). Every other cell still plans AROUND the caption zone — that rule did not move.

### The Talking Head Explainer plan

The layout map is the plan's spine: [`layout.md`](../../../presets/instagram/talking-head-explainer/layout.md)
§ 12 owns the contract, § 15 the method, sentence by sentence.

- **Measure first:** `uv run workflows/face-frame.py projects/<job> --modes` before the map (the layout gate reads
  `modes`), then `--collar --plan projects/<job>` once the map exists (the collar is read on its W/O/T spans, and
  that run re-derives the stored `modes` so T is capped by it), and `--crown A B` for each O span once the map places
  it.
- **A top-level `layout`** array tiling 0 → duration on the frame grid: `{start, end, mode, why}` rows, mode one of
  S (split) · T (tight) · W (wide) · F (full-screen) · O (card over wide), plus `caption_y` / `ui_bottom` on an F.
- **Every graphic cell carries** `family` (authored | capture | montage | overlay), `readable`, `shows` (what the
  capture must show, § THE CAPTURE GATE), `capture` or `asset` on a capture, `copy` (the words the graphic itself
  shows, for the OCR check), `shot_cuts` (timeline seconds of the picture cuts inside it), `sync` (the words its
  changes land on); an overlay card its `card` box and `crown`; the ask's cells `role: "cta"`. No `region`, no
  `content`, no `template`: the layout map places every graphic. Start from layout.md § 12's example, never the
  long-form schema above.
- **Kinds are never** `punch-cut`, `full-screen` or `scene`, and no cell has a `bg`: full-screen is a LAYOUT mode (F),
  not a kind, and every graphic is an alpha overlay on this preset.
- **`layout_deviations`** `[{rule, why, at?}]` turns a named FAIL into a WARN carrying its reason; **`variants.ad`**
  `{from, layout, cells}` is the second deliverable, only when one was asked for.
- **`validate-plan.py` runs `layout.py`** whenever the plan's `preset` or `format` names this preset, on the organic
  and on every `variants.<name>`: its FAILs fail the plan, and every WARN is answered in the summary.
- **The plan summary reports:** the layout shares (S / T / W / O / F and bare W), face-visible %, the F seconds (stated,
  not asked), the capture list with what each must show, the hook object, the CTA enactment, and any pickups the
  brief needs that the takes do not have.

## Handoff

The plan feeds **step 5b: the `graphics-build` skill owns the whole build** — it builds each
`graphic:true` beat at its `start`/`end` in its `region` per `template` + `copy` + `content`,
renders, places, and QAs. **On an app finish** set
`"compositor"` so the build knows the target: `"premiere"` (alpha overlays on the preset's graphics track + baked
footage moves, per the `premiere-pro` skill), `"capcut"` (`lanes/capcut/capcut-bridge.py`), `"resolve"`
(the `davinci-resolve` skill § Step 5), or `"finalcut"` (`lanes/finalcut/replay.py` lays `placement.json`, per the
`final-cut-pro` skill). `b-roll`/`motion-graphic` beats with no real
footage go through your AI-video tool, then composite like any part. Then the **second pass** adjusts.

This skill does ONE thing: decide the graphics. It never renders.
