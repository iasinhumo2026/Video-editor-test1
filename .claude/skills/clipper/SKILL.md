---
name: clipper
description: "Harvests short-form clips from a FINISHED long-form video: the reverse entry path (a published video in, a batch of 9:16 captioned clips out). Transcribes the long-form once, selects self-contained moments with a hook and a payoff, writes a clips plan for review, then builds each approved clip through the existing engine (rough-cut splice, face-centered 9:16 reframe, locked TikTok/raw captions). Does NOT edit the long-form itself. Triggers: clip this up, clip the long-form, make clips from this, cut shorts from this video, harvest clips, clip it into shorts, turn this into shorts, chop this into clips."
---

# Clipper: harvest short-form clips from a finished long-form

**A second entry path, not a pipeline step.** The main pipeline runs raw footage forward to one
finished video. This skill runs the other direction: one FINISHED long-form video comes in, several
short-form clips come out. Selection is the craft here; the build reuses the locked engine end to end
(rough-cut splice, face-frame reframe, tiktok-raw captions), so a clip is a real job folder with the
full audio chain, not a dumb trim.

**This skill selects and builds clips. It does not edit the long-form.** No re-cutting of the source,
no graphics passes, no thumbnails.

> **Craft principle.** A clip is not an excerpt, it is a standalone video that happens to be quarried
> from a longer one. If it needs the long-form's context to land, it is not a clip. Cold-open on the
> strongest sentence, never on wind-up.

---

## Inputs

1. **The source video**: the PUBLISHED long-form (the file people actually saw), or any long talking
   video. Intake it like any job: create `projects/<video-name>-clips/` and put the source in `raw/`
   (hardlink when the file already lives in this repo, copy when external; never move the original).
   Always AUTHOR the clips on the published file (its transcript is the timeline people saw). **When the long-form
   was edited in this repo, also name that job in the plan's `parent_job`**: `make-clips.py` then maps every segment
   through the parent's `transcript/cuts.json` to its RAW spans (split at the parent's cuts, those joints pinned) and
   cuts the clip from the raw footage. A published long-form made here carries its text animations and punch-cuts
   burned in, and the 9:16 face-centred reframe cut them to fragments ("ling", "ally important", 2026-09-27). An
   external video has no parent job: clip the published file, and in the plan step look at a few frames of each
   candidate and mark ⚠ any whose centre carries burned-in text or graphics the crop would slice.
2. **Clip count and targets**, if given. Default: 3 to 6 candidates per 10 minutes of source,
   15 to 60 seconds each (90s hard cap).

## Step 1: transcribe the source (once)

```bash
bash .claude/skills/rough-cut/scripts/transcribe.sh projects/<parent>
```

Skips automatically when `transcript/words.json` already exists (`--force` to redo). A long video
takes a while on WhisperX large-v3: that is fine, accuracy over speed, and it only happens once.

## Step 2: select the clips (the actual work)

Read the transcript and hunt for moments that stand alone. For each candidate, judge:

a. **The hook.** The first spoken line must grab cold, with zero context. If the strongest line sits
   mid-moment, open there and let the explanation follow it.
b. **Self-containment.** Kill or cut around anything that leans on the long-form: "as I said
   earlier", "in this video", "back in step two". If the reference is load-bearing, drop the
   candidate.
c. **One idea, one payoff.** A clip earns its length by paying off the hook. No payoff, no clip.
d. **Internal tightening.** A clip's segments do not have to be contiguous: splice out filler,
   dead air, and detours inside the span exactly like a rough cut. Repeated line across takes:
   keep the LAST take.

Write two artifacts in the parent job folder (reviewed artifacts, not scratch):

- `projects/<parent>/clips-plan.json`: the machine plan `make-clips.py` builds from.
- `projects/<parent>/clips-plan.md`: the cut sheet for review, a table of
  `# · name · source time · dur · hook line · why it stands alone`, with ⚠️ on any candidate
  you are unsure about.

Report back tight: source duration, candidates found, and the 2 or 3 strongest hooks. Then stop:
**the plan gets reviewed before anything renders.** Adjustments happen on the plan, then build.

### clips-plan.json schema

```json
{
  "job": "my-video-clips",
  "source": "raw/my-video.mp4",
  "parent_job": "projects/my-video",
  "clips": [
    {
      "id": 1,
      "name": "agents-run-while-you-sleep",
      "why": "strongest claim in the video, stands alone, natural 40s arc",
      "hook_text": "your editor works\nwhile you sleep",
      "hook_end": 2.8,
      "duration": 41.3,
      "segments": [
        { "start": 312.44, "end": 331.10, "transcript": "the hook and setup words kept here" },
        { "start": 338.72, "end": 361.40, "transcript": "the payoff, filler between spans cut" }
      ]
    }
  ]
}
```

Rules: `segments` use the exact cuts.json contract (SOURCE-file seconds, `xfade` and `no_refine`
overrides allowed; `clip` is filled in automatically). `parent_job` is optional (above): with it the SOURCE seconds are
still the published file's, and each segment becomes the parent's raw span(s) at scaffold time, the clip's
`transcript/words.json` the parent's own (the raw clock). `hook_end` is in CLIP-timeline seconds (sum
segment durations up to the hook's last word). `hook_text` is the on-screen card in the creator's
voice, punchy and lowercase-casual, 2 lines max; omit it (or leave empty) for no card, captions
still run. `name` is a kebab content title, unique across the whole repo (§ Gotchas).

## Step 3: build the approved clips

```bash
uv run .claude/skills/clipper/scripts/make-clips.py projects/<parent> --build
```

(`--only <name>` rebuilds one clip; no `--build` scaffolds the folders without rendering.)

Per clip this scaffolds a standard job folder `projects/<parent>/clips/<name>/` (hardlinked source
in `raw/`, parent words.json, authored cuts durable in `transcript/cuts.authored.json` plus the
`/tmp` copy splice reads) and then runs the locked lane:

1. **Splice**: the real rough-cut engine, so refine, frame-snap, the static audio chain, and
   `audio-qa.py` all apply. Heed audio-qa's ⚠ lines: report audible limiter pressure; `AMPLIFY_DB=<n> ... --only
   <name>` is the creator's override, never picked by the agent, and is recorded as a deviation (the gain is
   normally measured by `workflows/voice-gain.py`). The first splice is `RENDER=0`, then **`cut-audit.py --grid <the
   source's rate> --promote`** proves every cut on the waveform (sheet: the clip's `review/cut-audit-sheet.png`; read
   its ⚠ and HELD lines), and the render splices exactly the audited EDL. Without it a clip shipped a cut 146 ms into
   its "And" and a tail one frame into the published file's next shot (2026-10-13). The plan's `hook_end` follows the
   edges the build moved (printed when it does).
   A parent's `corrections.local.json` (the clips job's, else the `parent_job`'s) is merged into each clip folder at
   scaffold, since `export-transcript.py` reads only the clip folder's: put a sponsor's spelling there once.
2. **Reframe**: `face-frame.py` measures the face and produces the face-centered 1080x1920 crop
   (center crop fallback when no face is detectable, e.g. screencast sections). The 16:9 splice is
   kept as `outputs/<name>-169.mp4`; the 9:16 crop becomes the clean base `outputs/<name>.mp4`
   (audio stream-copied, never re-encoded). The Talking Head Explainer's `--verify` standard does not apply
   here: that check is for its split-frame seam layout, not full-frame clips.
3. **Captions**: the LOCKED tiktok-raw preset (captions always on, hook card only when the plan
   gives `hook_text`) writes the deliverable `outputs/<name>.final.mp4` directly, and once item 4
   passes, an export copy in `~/Downloads/` (`VE_EXPORT_DIR` overrides). `finalize.sh` is NOT used: it does not
   support nested job paths, and the builder already produces the canonical deliverable.
4. **The gate**: `flash-scan.py` on the deliverable, the clip's joints expected (`review/flash-scan.json`). The published
   file's own cuts inside a span print as warnings; a flash or double cut fails the clip, and no export copy is made.
   So does a first or last shot of 2 frames or fewer: flash-scan has no neighbour to call it a flash, and lists it only
   as an unexpected cut (an IN refined back a word opened a clip on a frame of the previous shot, 2026-10-13).
   A published long-form has picture cuts the audio-only tools never see, so an edge a frame past one is a one-frame
   shot: move that edge onto the source's cut in the plan (`pin_in` / `pin_out`) and rebuild `--only` that clip.

Then review like a second pass: watch the clips, adjust the plan (segments, hook text, drop a
clip), and rebuild only what changed with `--only`.

**A finished `--build` ends on the bake offer**, the same `Next:` line `finalize.sh --apply` prints on every
finished export (the clipper never runs finalize.sh): offer `bake-preset` in one line, on the parent job, and run it
only on the creator's yes. A scaffold or a build with a failed clip never offers it.

## Format note

Clips default to the TikTok/raw look, which is what a talking-head pull-quote wants. For a clip
that deserves the Talking Head Explainer treatment ([`presets/instagram/talking-head-explainer/README.md`](../../../presets/instagram/talking-head-explainer/README.md): the layout rotation, real captures, its captions), treat its clip
folder as a normal job and run pipeline steps 3 to 7 on it instead of step 3 above; it is a
standard job folder, so every downstream skill works on it unchanged.

## Gotchas

- **Clip names must be repo-unique.** The `/tmp/video-editor/<name>/` scratch (on Windows Git Bash maps this to
  `%TEMP%\video-editor`; write `cuts.json` through the Bash tool with a heredoc, since a file tool may resolve
  `/tmp` to `C:\tmp`) and the `~/Downloads` export are keyed by basename alone, shared with top-level jobs: a
  clip named like an existing job collides.
- **Plan times are SOURCE seconds; `hook_end` is CLIP seconds.** Mixing the two puts the hook card
  over the wrong words.
- **A rebuild regenerates the clip from the plan.** Hand edits inside a clip folder do not survive
  `--build` for that clip; fold changes into clips-plan.json instead.
- **Screencast-heavy clips get a center crop.** If the interesting pixels sit off-center, add a
  `"crop_x"` note to the plan's `why` and adjust after the draft, or give the clip the Talking Head Explainer
  treatment (presets/instagram/talking-head-explainer/README.md) instead.

## Handoff

Each clip is a standard job folder. `background-music`, `graphics-plan`, or a Premiere/CapCut/Resolve
replay can run on `projects/<parent>/clips/<name>/` exactly as on any job. Posting is out
of scope, as everywhere in this repo.

This skill does ONE thing: turn a finished long-form into reviewed, built short-form clips. It
never edits the source video.
