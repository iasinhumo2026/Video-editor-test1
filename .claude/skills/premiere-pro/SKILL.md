---
name: premiere-pro
description: "The PRIMARY finishing path — hand the rough cut to Adobe Premiere Pro, where you do the real editing and project work. Rebuilds the rough cut AS separate, trimmable clips on the Premiere timeline — it replays the edit decision list (cuts.json) against the raw footage, NOT a single flattened export — so every cut is a real edit point you can ripple/slip/slide. Triggers: send to premiere, open in premiere, finish in premiere, hand off to premiere, add the rough cut to premiere, edit this in premiere, take it into premiere."
---

# To Premiere — Rough Cut Handoff

**The primary path (2026-07-27) — and the zero-instruction DEFAULT (2026-08-28).** Edits happen inside an editing app, Premiere by default: a bare "do a rough cut" brings the job here after the cut (step 2), and **the chat-only lane is never inferred** from a job's content. Clients finish in their own app (`capcut` / `davinci-resolve`); a client with no app gets asked first. HyperFrames stays the graphics engine feeding this timeline.

**This skill's job is the HANDOFF** — the cut onto a Premiere timeline as real, trimmable edit points, plus the step-3 audio polish and the step-4 grade — not the whole edit. **On a long-form `youtube/default` job the graphics pass (step 5) then runs here as the DEFAULT next step, unprompted.** Captions are short-form only; the final render stays your. **Colour is no longer your by default (2026-08-31):** the grade is step 4, one adjustment layer on V2 under the graphics, scripted, look locked (Autumn-Rec709 as a Creative Look at Intensity 80 / Saturation 120, 2026-09-14).

**The cut is rebuilt AS cuts — not dropped in as one flat clip.** `rough-cut` already decided every edit and saved it as an EDL (`cuts.json`); this skill *replays* that EDL against the **raw footage**, so each kept segment becomes its own V1 clip at the exact edit points the rough cut produced and every boundary is real — rippable, slippable, re-trimmable against the original takes. Importing the flattened `outputs/<job>.mp4` is the *fallback* (§ Fallback).

## 🔒 STEP INDEX: what this lane does at each pipeline step

**This skill carries HOW, never WHAT.** The look, the numbers and the definition of done live in the
format's preset ([`presets/youtube/default/README.md`](../../../presets/youtube/default/README.md) for
long-form): read it for the target, the row below for the mechanics. Cross-lane:
[`LANES.md`](../../../LANES.md).

| # | Step | On this lane (mechanics in the § of the same number below) |
|---|------|--------------|
| 1 | Intake | universal, no Premiere involvement (CLAUDE.md § Pipeline) |
| 2 | Rough cut → replay | ✅ scripted, EDL replayed as separate trimmable clips on V1; section colour labels set on the items before the lay |
| 3 | Audio polish | ✅ scripted: `audio-polish.py --apply`, the measured gain + Hard Limiter as clip effects, readback-verified; ⚠️ `--lift auto` for the Talking Head Explainer's second voice |
| 4 | Color grade | ✅ scripted: `grade-layer` then `grade-lut.py apply`, hands-off → [`lanes/premiere/premiere-grading.md`](../../../lanes/premiere/premiere-grading.md) |
| 5 | Graphics | ✅ scripted: place alpha movs on the graphics track, bake footage moves; ⚠️ `layout-keys.py` for the Talking Head Explainer's footage layout |
| 6 | SFX | ✅ scripted: `place-sfx.py` puts the universal plan on A2–A4, readback-verified (validated on two reference jobs, 2026-09-03) |
| 7 | Review | ✋ the creator's. The run pauses here. |
| 8 | Export | ✅ scripted on the creator's go: `uv run lanes/premiere/export.py projects/<job>` (the format's preset picked from the sequence, lsof-waited, ffprobe-verified, no AME); by default the run stops at step 7 and you say when |

Captions are a step-5 overlay on the short-form presets, placed by `place-graphics.py` like any
graphic (long-form takes YouTube CC); background music is opt-in and scripted: `lanes/premiere/place-music.py` (§ Background music below).

## When to use

Any trigger phrase above, or a rough cut exists and you want it finished in Premiere. With no rough cut yet, run `rough-cut` **with `RENDER=0` on the splice** — the EDL + canonical transcript generate in ~8 seconds and this skill needs nothing else. **Never render a flat MP4 for a Premiere-finish job** (2026-07-22): [`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md).

## What it needs first — the bridge must be live

**And the job's project must be the ACTIVE project.** Every lane script acts on `app.project.activeSequence`, whatever
project you last clicked, and Premiere keeps several open (a v2 placer laid 37 graphics over v1's timeline,
2026-09-13). So `place-graphics.py`, `place-sfx.py`, `place-music.py`, `audio-polish.py`, `review-frames.py` and the
bridge's `replay`, `zoom`, `grade-layer`, `lay`, `labels`, `clear-previews` and `es` run `lanes/premiere/job_guard.py`
before their first readback and exit, naming both projects, when the active project or sequence is not this job's;
they never switch projects (that is your click). Bridge commands take the job as `"job":"projects/<job>"` in their
opts; `es` takes `--job <dir>` or `--no-guard` (a read deliberately not about a job) and refuses without one; on
`labels` and `clear-previews` the job is optional and leaving it off skips the check, so pass it. The rule:
[`lab-notes.md`](../../../lanes/premiere/lab-notes.md) § The active project is checked before every write.

This skill drives Premiere through the **`premiere-pro` MCP server** (`.mcp.json`), which does nothing unless Premiere is open with the bridge panel running.

**Engine: `vendor/premiere-mcp/`, a pinned local clone of [hetpatel-11/Adobe_Premiere_Pro_MCP](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP), pinned at commit `12684e3` = v1.2.3, 283 tools.** Confirm the running engine IS the pin before trusting a tool: `git -C vendor/premiere-mcp rev-parse --short HEAD` must print `12684e3`, and `get_capabilities` must report 283 tools.

⚠️ **Never install the `premiere-pro-mcp` npm package** — a republish carrying a broken hand-rolled CEP `CSInterface` shim (the all-null bridge failure of 2026-07-09). Update only via deliberate `git pull` + a re-run verification pass + the new hash recorded here, then `npm install && npm run build`, re-apply `lanes/premiere/premiere-templates/cep-bridge-autostart.patch`, re-copy `cep-plugin/`, restart Premiere. **Upstream telemetry is OFF two ways** and must stay off: `"telemetry": false` in `~/.premiere-mcp-bridge/config.json` + `PREMIERE_MCP_TELEMETRY=0` in `.mcp.json` env.

1. **MCP tools available?** Discover the `premiere-pro` tools under the current harness's actual names. Claude Code reads `.mcp.json`. Refresh MCP connections if setup changed mid-session. **Tools absent this turn?** Continue through `node lanes/premiere/premiere-bridge.mjs <tool> '<json>'`: the same handlers through the file bridge, same panel requirement, no MCP session. Inspect `--list` and `--desc <tool>` before using an unfamiliar command; missing MCP tools alone do not require stopping the edit.
2. **Bridge connected?** Call `ping` first; if it errors or times out the panel isn't running. **"Is Premiere running?" is answered ONLY by `lanes/premiere/premiere-pid.sh`** (`--name` prints the process name), never a hand-typed `pgrep` — the process is year-suffixed (`Adobe Premiere Pro 2026`), so `pgrep -x "Adobe Premiere Pro"` says "not running" with the app on screen (2026-09-02) and `pgrep -f` over-matches crashpad and AdobeIPCBroker. A running app with a dead panel is still unreachable: the pid answers "running", only `ping` answers "drivable". `premiere-pid.sh`, `premiere-up.sh` and `premiere-dismiss.sh` run on macOS and Windows with the same flags (on Windows they delegate to `lanes/premiere/premiere_win.py`: the pid from `tasklist`, a modal detected as a disabled main window, the dialog being the window it OWNS, answered with Return or Escape; proven on Premiere's real save dialog, 2026-09-27). **An ExtendScript edit never dirties a project**, so a quit after one raises no save dialog and drops the edit: every lane write saves. **Try the scripted launch FIRST:** `./lanes/premiere/premiere-up.sh [projects/<job>/premiere/<job>.prproj]` launches Premiere with the CEP autostart patch so the bridge comes up on its own (`--restart` never force-kills — a non-graceful exit reads as a crash, and the crash dialog blocks the panel). Only if that fails, tell you in one line:
   > Open Premiere Pro → **Window → Extensions → MCP Bridge (CEP)** → click **Start Bridge** (temp dir defaults to `/tmp/premiere-mcp-bridge`).

   Then retry `ping`, and don't proceed until it returns ok.

The temp dir in the panel **must match** `PREMIERE_TEMP_DIR` in `.mcp.json` (`/tmp/premiere-mcp-bridge`) — that shared folder *is* the bridge. Protocol is `command-<id>.json`/`response-<id>.json` files, and a panel and a server on different protocols cannot interoperate, so re-copy `cep-plugin/` (to `~/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP/`) after any engine bump. The clone is gitignored like `.mcp.json`: restore it with `git clone` + checkout the pinned hash + `npm install && npm run build`.

## Step 2: the EDL replay (the handoff itself)

1. **Resolve the job** — newest folder under `projects/` unless you named one.
2. **Locate the EDL + raw footage.** `projects/<job>/transcript/cuts.json` (or `/tmp/video-editor/<job>/cuts.json` on an older job) plus `projects/<job>/raw/`. **Both must exist**; if the EDL is gone from both spots take the **Fallback** path at the end and tell you why. `cuts.json` is `{ "segments": [ { "clip": …, "start": 1.24, "end": 4.60, "transcript": … } ] }` — segment order = timeline order, and `start`/`end` are seconds **in the raw clip**, exactly what Source Monitor in/out points take.
3. **Preflight** the bridge (`ping`).
4. **Create the project** at `projects/<job>/premiere/<job>.prproj` (`create_project`); if it exists, `open_project` instead of clobbering your in-progress work. **Windows:** `create_project` keeps the CEP panel alive, but `open_project` after a bare launch drops it: to open an existing project, launch WITH it (`./lanes/premiere/premiere-up.sh --restart projects/<job>/premiere/<job>.prproj`, 2026-09-27).
5. **Import the raw clips** (`import_media`) — every distinct `clip` in `cuts.json`, from `projects/<job>/raw/`, never the flattened `outputs/<job>.mp4`. **`import_media` takes `filePath`, a single string — one call per file.**
6. **Build a matching sequence.** `create_sequence` without a preset is broken on 26.x ("Not Enough Parameters"); use `create_sequence_from_clips` with an imported raw clip (or ES `createNewSequenceFromClips(name, [item])` + `app.project.activeSequence = seq`) so it inherits the footage's exact dimensions and framerate, then empty the timeline before the replay. **`remove_selected_clips` returns `available:false`** — clear via ES: loop every track backwards, `track.clips[i].remove(false, false)`. Confirm with `get_sequence_settings`. **Then put the empty sequence on the raw's NOMINAL rate** (`ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate` on the raw): `node lanes/premiere/premiere-bridge.mjs seq-rate '{"job":"projects/<job>","fps":"30000/1001"}'`: a variable-rate phone clip (every iPhone take) builds a sequence at its AVERAGE rate, a frame off every graphic, and `replay` refuses a sequence off the standard rates ([`lab-notes.md`](../../../lanes/premiere/lab-notes.md) § Step 2, 2026-09-27).
7. **Label the sections BEFORE the replay — long-form always, and any multi-section job.** `item.setColorLabel(n)` on each section's project item, the colour picked by RGB distance out of Premiere's Prefs, never by name. A clip stamps its label from the project item at insert time, so a timeline laid unlabelled can only be fixed by remove-and-re-lay — § Colour labels.
8. **Replay the EDL onto V1 — ONE command:**
   ```
   node lanes/premiere/premiere-bridge.mjs replay projects/<job>/transcript/cuts.json <clipName>
   ```
   One ExtendScript for the whole EDL — per segment `setInPoint`/`setOutPoint` on the project item then `overwriteClip` onto V1 — saving when it finishes. V1 and A1 must be empty: a replay onto clips is refused (`--clear` empties them first, the re-cut's re-lay; `--append` lays after them, the next section of a per-section replay). **Result:** N separate clips on V1, each a real edit point, with the original heads and tails still in the source. Every boundary is laid on the NEAREST sequence frame, so before anything is laid the replay names each EDL boundary more than 1 ms off that grid and how far the laid cut then runs from `cuts.json` (`⚠ replay: … off the sequence's frame grid`). splice.sh writes every boundary on the grid; a hand EDL edit after it leaves one off, and a full-screen planned to the EDL's end landed a frame short of the real cut (2026-09-27). Put those boundaries on the grid in `cuts.json` and re-export the transcript before a plan is timed from it (the CapCut `replay` says the same).
9. **Verify** with `uv run lanes/premiere/live-edl.py projects/<job>`: pass = exit 0 and `cuts.json is IN SYNC with the timeline`. It checks that V1 has no gaps and that the durations add up to its end, and compares each clip's `inPoint` and DERIVED source out, `inPoint + (end − start)`, with the EDL, never `outPointSeconds`, which reads stale after a `clip.end` write (proven live 2026-09-23: outPoint 10.010 on a clip whose picture runs to 10.886; `premiere-bridge.mjs diff-edl` prints the same disagreement as STALE-OUTPOINT). Then `save_project` and report the `.prproj` path and the segment count on V1.

Four facts the `replay` command encodes, for any NEW ExtendScript that lays clips from an EDL:

- **Land every boundary ON the sequence grid: nearest sequence frame, then the first SOURCE frame at or above it, then `+1e-4s`.** Premiere floors a requested in/out to the source frame grid and AGAIN to the sequence grid; same-rate footage hides it, and a 30 fps screen recording on a 23.976 sequence landed every cut 41.7 ms early (2026-09-13, [`lab-notes.md`](../../../lanes/premiere/lab-notes.md) § Step 2). `replay` does the snap itself; the `+1e-4` nudge stays because tick conversion floors (a grid time serialised a hair low drops a frame, measured 2026-07-18). Mixed-rate footage still gets the cut MEASURED on that grid before the replay: `uv run workflows/cut-audit.py <job> --grid <sequence rate> --write <edl>` (and after any re-lay, `--live` with the readback) — see `rough-cut` § Audit the cut on the finish surface's grid.
- **The append position is READ BACK** off the last laid clip's `end.seconds` after every overwrite, never accumulated — Premiere quantizes each boundary, so a running sum drifts.
- **Clear the items' in/out afterward** (`clearInPoint(4)`/`clearOutPoint(4)`) or your next source-monitor insert is silently trimmed to the last segment.
- **Only on the MCP `overwrite_from_source` route:** the playhead does NOT auto-advance on 26.3, so each overwrite lands on top of the last (symptom: final duration = the longest segment). That route needs `set_playhead_position` + a `get_playhead_position` read-back before every edit. `replay` does not use it.

### Lip-sync a re-recorded line (sync.so)

When a line is re-recorded after the cut (a CTA keyword swap, for example), sync.so re-syncs the picture to the new audio.

1. **Source:** cut the video from the RAW at full camera geometry, frame-exact to the clip it replaces. Prove the first frame by PSNR against the raw at ±1 frame: the right frame stands clear (53 dB against 36–37). Never cut it from a crop or a program render.
2. **Audio:** the raw up to the room-tone dip before the changed words, then the re-record, gain-matched to the original's LUFS, with one 15 ms equal-power joint, trimmed to exactly the video's length in samples. Convert `.aifc` recordings to `.wav`.
3. **Generate:** `uv run workflows/sync-so.py <source.mp4> <audio.wav> --out projects/<job>/assets/lipsync/<name>-sync3.mp4 --source-note "raw <file> frame N+ for K frames, crop/scale …" --dry-run`, then again without `--dry-run` (defaults: sync-3, cut_off; `SYNC_API_KEY` in the repo-root `.env`). `<out>.provenance.json` is written the moment the generation is submitted (both inputs' sha1 + ffprobe, asset ids, generation id, cost, the source note), and the tool never overwrites a take. A run that stops after the submit (a failed download, the 60-minute poll limit, an interrupt) keeps the paid generation in the provenance: `uv run workflows/sync-so.py --fetch <id> --out <same out>` finishes it without generating again. Always the API, never the browser upload: the browser caps a source at 10 MB, the API takes up to 5 GB, so the source can be a full-4K near-lossless cut. sync-3 regenerates a box around the lower face (a mic windscreen's top comes out slightly softer); lipsync-2-pro edits only the mouth and jaw. Check the output's audio lag is 0 before laying it.
4. **Lay:** back at raw geometry with `node lanes/premiere/premiere-bridge.mjs lay`, carrying the replaced clip's Motion values and its section's colour label. Re-apply the A1 chain on that range; `cut-proof.py` over the range must exit 0. Give the EDL segment `media` + `note` keys so it is never re-replayed from raw (`replay` refuses a `media` segment), and replace the canonical transcript's words from the changed line on.
5. **Prove the framing on the picture:** a Motion Scale/Position readback does not prove a substituted clip (its crop, frame size or source offset can differ while those values match). Export a draft (`lanes/premiere/export.py --draft`) and run `workflows/framing-continuity.py` on the clip's two cuts: `edit-video` § A SUBSTITUTED CLIP IS PROVEN ON THE PICTURE.

### A declared re-cut: the order on this lane

A cut change after step 3 (`edit-video` § A cut change after step 3 is a declared RE-CUT) runs in this order here,
every line read back before the next (whop-first-10k's hook swapped to another take, 2026-10-14):

1. **Freeze** the approved state into `projects/<job>/reference/<label>/` (copied, never moved): `cuts.json`,
   `words.json`, the canonical transcript, `graphics-plan.json`, `placement.json`, the `sfx-*.json`, `layout-keys.json`,
   `face-frame.json`. Its `cuts.json` is the `--from` below.
2. **Re-time the files, nothing on the timeline yet:** `uv run workflows/ripple-cut.py projects/<job> --from
   reference/<label>/cuts.json` (dry run, then `--apply`; through the words with `--retake
   reference/<label>/<job>.transcript.json` when you re-recorded the line). Decide every ORPHANED, STRADDLING and DEAD
   EDGE row before going on.
3. **Re-lay V1/A1:** `node lanes/premiere/premiere-bridge.mjs replay projects/<job>/transcript/cuts.json <clipName>
   --clear` (saves first, empties V1 and A1, lays from 0; a replay onto an occupied V1 is refused), then
   `uv run lanes/premiere/live-edl.py projects/<job>` reads IN SYNC.
4. **Audio polish:** `uv run lanes/premiere/audio-polish.py projects/<job> --apply` (the clear took the chain and any
   lift with the clips), then `--verify`.
5. **The GRADE clip's end** to the new duration ripple-cut printed (§ Step 4: frame 0 to the last frame), proven on a
   program grab at the last frame.
6. **Layout keys** (the Talking Head Explainer): `uv run lanes/premiere/layout-keys.py projects/<job> --apply`, then `--verify`.
7. **Rebuild what changed**, each as a NEW version (a placed path is never overwritten): every comp ripple-cut
   names RE-RENDER or COPY (`engine.py render <id> --ver <v>` on the kit, `VER=<v> render.sh <id>` elsewhere), and the
   caption layer, which ends on the new duration (`captions.py … --ver <v>`).
8. **Graphics:** `uv run lanes/premiere/place-graphics.py projects/<job> --plan --write`, then `--apply` (re-lays every
   row the re-cut moved and swaps the new versions), then `--verify` ALL PLACED.
9. **SFX:** `uv run workflows/sfx-plan.py projects/<job> --merge <the rebuilt ids>`, then
   `uv run lanes/premiere/place-sfx.py projects/<job> --remove-extra --dry` and without `--dry` (the cues the re-cut
   left at their old times, past the new end included), `--apply` (re-lays every cue the plan moved) and `--verify`.
   A laid bed: `place-music.py --apply --refit` (a bed you razored: only its last clip is trimmed).
10. **Prove the cut:** `live-edl.py --live-out live.json`, `uv run workflows/cut-audit.py projects/<job> --grid <sequence
    rate> --live live.json`, then `uv run lanes/premiere/cut-proof.py projects/<job>`: exit 0 on both.
11. **Export** on your go (§ Step 8), then `./finalize.sh <job> --apply`.

## Step 3: audio polish, immediately after the replay verifies

**Run it now (2026-08-28), not at picture lock.** Target: the preset § Audio polish.

```
uv run lanes/premiere/audio-polish.py projects/<job> --apply     # measured gain (voice-gain.py) + limiter on every A1 clip, read back, save
uv run lanes/premiere/audio-polish.py projects/<job> --verify    # exit 1 on any clip off the gain --apply recorded over it (premiere/audio-polish.json); --gain N holds every clip to N instead
uv run lanes/premiere/audio-polish.py projects/<job> --apply --gain 15   # a named gain, ONLY when you call one
```

⚠️ **`--gain` is a DEVIATION from the locked measurement, never a workaround for a measurement you
dislike** ([`LANES.md`](../../../LANES.md) § step 3): state it in the report and RUN.md. It is recorded with the apply
(`premiere/audio-polish.json`, source `named`), so the plain `--verify` checks it without retyping. A job polished
before the records existed has no file: re-run its `--apply` (idempotent) once, or verify with `--gain N`.

**The second-voice lift (the Talking Head Explainer; WHAT: its [README](../../../presets/instagram/talking-head-explainer/README.md) § Audio).**
A second voice on a speaker (an AI on a call, a phone) is lifted after the chain when the gap is over 3 dB, and
announced:

```
uv run lanes/premiere/audio-polish.py projects/<job> --lift auto   # voice-gain.py --second-voice decides at the recorded gain; a lift Amplify AFTER the Hard Limiter, keyed on the transcript/voices.json spans, 50 ms ramps inside the spans, capped at -1 dBTP
uv run lanes/premiere/audio-polish.py projects/<job> --verify      # the chain AND each A1 clip's latest lift record (a readback)
uv run lanes/premiere/audio-polish.py projects/<job> --bounce      # A1 alone bounced twice (exportAsMediaDirect, no AME): lift bypassed, then on; the lift read on its plateaus, the ceiling judged: the proof
uv run lanes/premiere/audio-polish.py projects/<job> --lift 0      # drop the lift (the keys this tool recorded come off)
```

A section runs its own lift from its own folder (`projects/<job>/sections/<s> --lift auto [--range FROM TO]`): the
record carries its scope, so it never touches another section's clips. A named lift over the headroom cap, or one
whose headroom cannot be measured, is refused without `--force`; `auto` refuses an unmeasurable gap (under 3 s of kept
second voice). Re-apply it after any rebuild (a re-replay, a re-cut drops the lift Amplify like it drops the chain). A
lift Amplify carrying keys the tool did not record is the creator's: named and skipped. `--bounce` is the proof,
never the key readback alone (proven live on stereo and mono, 2026-09-24; the lock:
[`lab-notes.md`](../../../lanes/premiere/lab-notes.md) § Step 3).

Validated 2026-09-03 (35/35 clips on a real job, plus the effect-ADD path on a scratch sequence):

- **No per-section audio work during the cut itself (2026-07-30):** measuring is fine, acting on it is not.
- **The chain, as clip audio effects on every A1 clip:** the gain from `workflows/voice-gain.py`
  (kept speech to −17 LUFS pre-limiter), then QE `addAudioEffect("Amplify")` +
  `addAudioEffect("Hard Limiter")` and DOM property writes, every value read back (validated 2026-08-28, 31/31
  clips); one pass over the timeline, effects stay hand-tweakable. **ES audio effect params are normalized 0..1 over
  the slider range (2026-07-30):** Amplify Left/Right `v = (dB+96)/144` (range −96..+48; +10 → 0.73611), Hard
  Limiter "Maximum Amplitude" `v = (dB+100)/100` (range −100..0; −6 → 0.940; Input Boost/Look-Ahead/Release at
  defaults).
- **A timeline rebuild (clear + re-replay) discards clip effects.** After ANY re-replay, re-apply the
  chain to every A1 clip and re-verify, or the recut ships unpolished audio silently.
- **Then the proof, before the cut is called done:** `uv run lanes/premiere/cut-proof.py projects/<job>` (the whole
  timeline; add `--from`/`--to` for a window, and `--edl-start` only when it warns ⚠) bounces the dialogue off the live timeline, transcribes it and diffs it against the EDL's script (exit 0 = no chopped,
  doubled or leaked word). WHAT and why: `rough-cut` § The proof.
- ⚠️ **A CLIP's own Volume > Level is NOT an effect param and NOT the Amplify range** —
  it has its own encoding, whose ONE home is
  [`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md) (the Volume > Level bullet).
  `lanes/premiere/clip_level.py`'s `lvl_v` / `v_lvl` are the canonical pair in code: a hand or job-local
  ES placement imports them and never re-derives the formula (re-deriving it put a −29 dB riser on the
  timeline at +8.4 dB, 2026-09-19). ⚠️ **Two candidate ranges can agree at one point, and a readback through your own
  inverse cannot tell you which one you are on** — it lies with the same formula, which is how that
  riser self-certified while the creator was hearing it. Prove a NEW param against the Effect Controls
  UI or a solo bounce (every other audio track muted), never a readback, before batch-applying. And a
  CALIBRATION write never lands on a live clip — the calibration-probe rule is in the same lab-notes bullet.

## Step 4: the grade, BEFORE graphics and underneath them

**Full lane recipe and every trap: [`lanes/premiere/premiere-grading.md`](../../../lanes/premiere/premiere-grading.md)**
— read it first, because three separate failures here all present as "the grade does nothing" and
none of them is visible in a readback. The step is two commands' worth of work:

1. `node lanes/premiere/premiere-bridge.mjs grade-layer '{"job":"projects/<job>"}'`, sequence active: provisions V1/V2/V3/V4,
   mints an adjustment layer **at the frame size it reads off the sequence**, lays one instance on
   **V2** spanning V1, names it `GRADE`, adds Lumetri, saves. Idempotent.
2. `./lanes/premiere/premiere-up.sh --quit` → `uv run lanes/premiere/grade-lut.py apply <job>.graded.prproj`
   (a COPY) → `./lanes/premiere/premiere-up.sh <job>.graded.prproj` → frame delta with the layer
   toggled → quit → swap the copy over the job file. **The file must be CLOSED while the tool writes
   it**, and writing into a copy means a refused open is a file that did not open, not a modal.

**The Talking Head Explainer's sequences take the grade too** (camera footage only; its README § Grade).
`grade-layer` already mints at the vertical sequence's own size; re-fit the layer on every end change and on
every variant sequence (an AD clone ends elsewhere), so it runs frame 0 to the last frame.

**Do it before a single graphic is placed** — the track is free at setup and expensive to insert
later, and the graphics QA measures contrast and glow against the shipping picture. Verify from a
bridge `frame` grab with the layer toggled, never the effect readback, and read every track's mute
state first. ☠️ **Never use the MCP's `apply_lut` tool:** a measured no-op that reports
success, and on a clip that already carries a Lumetri (every GRADE layer does) it writes into the
wrong instance and resets it.

## Step 5: graphics on the timeline (validated 2026-07-18, `your-job`)

**The preset you are on IS the architecture — read it first and treat its track map as authoritative.** Long-form default → [`presets/youtube/default/README.md`](../../../presets/youtube/default/README.md) (V1 footage / V2 grade / V3 graphics / V4 accents, at source resolution); the lane-agnostic Premiere craft is below. **Every preset-specific timeline architecture lives in its own preset folder**, including the vox-collage 4K / adjustment-layers-on-top stack ([`presets/youtube/vox-collage/premiere-lane.md`](../../../presets/youtube/vox-collage/premiere-lane.md)): opt-in by name, its grade placement the inverse of the default's, never read on a default job.

**On a long-form `youtube/default` job the graphics pass is part of the DEFAULT edit**, so after the replay, the audio polish and the grade it runs WITHOUT being asked — plan → build → place → bake → converge, every graphic left hand-editable (separate graphics-track clips + real keyframes):

1. **Plan** with `graphics-plan`, which resolves the preset itself (horizontal long-form → `presets/youtube/default/`; other looks are opt-in BY NAME). Anchor beat times to the refined EDL / canonical transcript word timestamps.
2. **Author comps** in `projects/<job>/hf-graphics/gfx/compositions/` and render with the job's `render.sh` (copied from `presets/youtube/default/reference/fullscreen-render.sh`): **`render.sh <id> alpha`** for overlays (ProRes 4444 straight alpha), **`render.sh <id> full`** for full-screen graphics (opaque mp4, film grain baked; bg-dark adds `STEP_FPS=12`). Comp gotchas and the QA gates belong to the **`graphics-build`** skill, which owns the build; `lanes/chat-only/incremental-graphics.md` is the CHAT-ONLY lane and does not apply here. (Universal comp rule: ALL CSS inline, no `<link>`.)
3. **Place overlays on the GRAPHICS track** with **`uv run lanes/premiere/place-graphics.py projects/<job> --plan --write` then `--apply`** (2026-09-02: owns `hf-graphics/placement.json`, derives rows from the plan + newest render version, places what is missing, swaps stale versions, re-lays a row whose clip sits off it, reads every write back; also `--verify` / `--sync-plan` / `--remove <ids>`). Underneath: `importFiles` + `seq.videoTracks[N].overwriteClip(item, startSeconds + 1e-4)` (the tick-floor nudge) + `clip.end = t`. ⚠️ **N is 2 (V3) on the youtube/default map** — read the preset track map, never hardcode from memory. Alpha composites natively, no keying. Two traps, each paid for: **a re-render is a NEW filename + a fresh import** (overwriting a placed path half-stales Premiere's frame index), and **a same-track overwrite then trim leaves a crater** (trimming back does NOT restore the neighbour; re-lay it, then read the track back, which `--verify` does). Program grabs come from the bridge `frame` command, never by fronting the app.
   **A second sequence (an AD cut, a clone of the organic one):** `uv run lanes/premiere/place-graphics.py projects/<job> --variant <name> --sequence "<sequence name>" --plan --write | --verify | --apply | --reconcile [--apply]`. It reads `graphics-plan.<name>.json` and keeps its rows in `hf-graphics/placement.<name>.json`; its caption layer is `hf-graphics/captions/renders/captions-<name>-alpha*.mov`; its `cut_rev` is checked against `transcript/cuts.<name>.json` when that exists, else `cuts.json`. The variant plan lists EVERY graphic on that sequence: the clone carries the organic ones, and anything unlisted reads as extra, which `--reconcile --apply` would remove. It refuses without `--sequence` (or `VE_SEQUENCE`), refuses the job-named organic sequence, and every bridge call also refuses when the active sequence is not the named one (proven live 2026-09-23). `--sequence` alone works on an organic run too. `validate-plan.py` stamps only `graphics-plan.json`, so a variant plan's `cut_rev` is stamped by hand.
4. **Bake footage moves on V1** (they mirror the comp's motion): the `zoom` command for punch-ins, custom ES for reframe pushes — per-frame keys on Transform Scale H+W and Position (normalized [x,y] arrays), all key times in **source-clip time** (`clip.inPoint.seconds + offset`). A move crossing a V1 edit is split: the first clip pushes in and HOLDS to its tail, the next starts held and releases. **The `zoom` command** takes the preset's numbers straight:
   ```
   node lanes/premiere/premiere-bridge.mjs zoom '{"job":"projects/<job>","clip":0,"from":115,"to":100,"frames":18,"ease":"quart","fps":"30000/1001"}'          # opening zoom-out, starts at the in point
   node lanes/premiere/premiere-bridge.mjs zoom '{"job":"projects/<job>","clip":8,"from":100,"to":115,"frames":18,"ease":"inout","fps":"30000/1001","at":28.3}' # emphasis push-in, starts at a word
   ```
   `fps` = the sequence's exact rational rate; a wrong rate stretches the ramp. `at` is a **sequence**
   time in seconds (feed it the word timestamp minus ~2 frames); `offset` takes frames past the clip's
   in point instead; omit both and the ramp starts at the in point. Three things it handles that a
   hand-rolled bake gets wrong: **keys BEFORE the ramp survive**, so re-baking a push-in cannot
   destroy an opening zoom-out in the same property track; **it refuses rather than half-writes** when
   a ramp would start before the clip or run past its end; and **Motion and Transform are different
   effects** — the bake is on Transform's `Scale Height` and `Scale Width`, so querying `Motion/Scale`
   reports zero keyframes and reads as "no push-ins here". Verify by reading back: on the 18-frame `inout`
   push-in frame 9 must read **107.50**, frame 4 **100.66** and frame 14 **114.34** (a linear bake reads
   107.50 at frame 9 too, so frame 9 alone does not discriminate); on the 18-frame `quart` zoom-out
   frame 9 reads **100.94**. The numbers are the preset's
   ([`presets/youtube/default/README.md`](../../../presets/youtube/default/README.md) § Emphasis push-in).
5. **QA every graphic from the real program render**: `node lanes/premiere/premiere-bridge.mjs frame '{"time":<sec>,"out":"/abs/path-no-ext","job":"projects/<job>"}'` — full composite (keyframes, alpha overlays, unsaved state), zero AME. The `"job"` checks the active project and sequence first; to grab a cut other than the job-named one, add `"sequence"` (only together with `"job"`) or set env `VE_SEQUENCE`. The grab is the frame Premiere SHOWS at `time` (the floor), and the output names the sequence it grabbed. Iterate: edit comp → `VER=<v> render.sh <id>` (new filename, never overwrite a placed path) → `uv run lanes/premiere/place-graphics.py projects/<job> --plan --write` (the newest version wins) → `… --apply` (swaps the stale clip) → re-grab. **A watchable preview goes through Premiere itself, NEVER AME (2026-07-20)**, § Step 8.
5b. **The Talking Head Explainer's footage layout keys** (after the replay and the grade, and again after any
   re-cut or V1 rebuild): `uv run lanes/premiere/layout-keys.py projects/<job> --apply`, then `--verify` (`--dry`,
   the default, prints the keys offline; `--variant ad --sequence "<job> AD"` for the second deliverable). HOLD keys
   on V1's own Motion from face-frame.json `modes`, one frame apart at each switch, V1 never razored; a hand-set
   Motion is HAND, reported and left alone (`--force-clip` only after reading it). A graphic's Scale stays
   `place-graphics.py`'s fit_scale: the keys move the footage, never a graphic. The lock:
   [`lab-notes.md`](../../../lanes/premiere/lab-notes.md).
6. **Converge with `edit-review` — step 5c, part of the graphics step, not an optional extra.** The build's first-pass QA is the builder grading itself; this is fresh eyes. Run the loop until a full round comes back clean, fixing part-by-part, then move to step 6. **Objective defects must never reach your review (step 7)** — that pass is taste, and only taste.

### Keyframe & effect laws (hard-won, lane-agnostic, do not relearn)

These hold on every Premiere job regardless of preset; none is a look choice.

- Clip keyframes live in **source time**: `inPoint + offset`. Synthetic media (adjustment layers) has inPoint ≈ 3600 s, and it RISES when the head is trimmed.
- **Baked keys are the standard** for any scripted motion: one key per frame (or per 2) sampled off the curve, all linear. Scripted eases are broken/limited; bake the shape.
- Point params (Position/Anchor) are **normalized** (0.5,0.5 = center; for offsets divide px by frame dims); scalars read/write in display units. Always read back.
- Effects apply via QE: `qe.project.getVideoEffectByName` + `qclip.addVideoEffect`; **walk `getItemAt(i)` for `type === "Clip"`** — gaps are items, so a clip that doesn't start at 0 is not item 0.
- **Adjustment layers: intrinsic Motion is inert on the image**, it moves only the layer's bounds (caught 2026-07-22). Image moves = the **Transform effect**; set Scale Height AND Width explicitly (the uniform toggle is untrusted). Prove any new transform assumption with an exaggerated offset + frame grab BEFORE baking hundreds of keys. (Minting the layer: [`lanes/premiere/premiere-grading.md`](../../../lanes/premiere/premiere-grading.md) § 1.)
- **Rendered preview files DROP AI-masked layers (Premiere 26.x)** — green-bar playback lies, yellow is truth. Clear the render files (`node lanes/premiere/premiere-bridge.mjs clear-previews '{"job":"projects/<job>"}'` — pass the job so the active-project guard runs; the one-argument `deletePreviewFiles` throws) and never tick "Use Previews" on export; real renders composite correctly. A stale cache lies the other way too — a phantom graphic where no clip exists after a scripted move: [`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md).

### Graphics clip lifecycle (also lane-agnostic)

- **Laying onto a track that ALREADY has clips goes through `node lanes/premiere/premiere-bridge.mjs lay`, never a hand `overwriteClip`** — it takes `{"job":"projects/<job>","item":…,"track":"A1","in":…,"out":…,"at":…}` (`job` required, it runs the active-project guard), derives the subclip flags from the track's kind (an audio track takes an audio-only hard-boundary subclip, a video track a video-only one) and aborts on a drop in the track's clip count. An AV item `overwriteClip`-ed onto an audio track wipes that track to the end of the sequence, and a scripted mutation never enters Premiere's undo stack, so the last save is the only rollback: [`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md). ⚠️ `lay` on a 24 or 30 fps source under a 23.976 sequence, and `labels` on a real multi-hundred-clip timeline, are still unproven live (`lay` same-rate and on a 29.97 source, `clear-previews` and `es` are proven) — **treat the first live use of each as a TEST**: save first, run ONE row, read it back ([`lab-notes.md`](../../../lanes/premiere/lab-notes.md) § UNPROVEN LIVE, which is where an entry gets struck off once it has run).

- **Iterate** — re-render the ONE affected part as a NEW version (`VER=<v> render.sh <id>`) and let the placer swap it (item 5 above); never overwrite a placed path (2026-08-01): a same-path rewrite half-stales Premiere's frame index and specific frames come back transparent. Never re-render the whole family for one tweak.
- **Anchor beats to MEASURED audio, not raw WhisperX** — word starts run ~50-100 ms late; scan a 5 ms RMS envelope of the base cut around the WhisperX time and land on the acoustic attack, frame-snapped.
- **The editor re-trims between sessions** — read the LIVE timeline before computing anything against it, never docs or memory for clip spans.
- **Re-timing or swapping a graphic orphans its SFX silently** — SFX are aligned to graphic beats, so check the SFX tracks in that window and reconcile affected cues using the step-6 incremental revision procedure, preserving approved unaffected sound design (which is why SFX is step 6, after the graphics defect loop).
- **Generated b-roll:** `videoTracks[n].overwriteClip` + `audioTracks[n].overwriteClip` at the same time so the voice on A1 stays untouched. Track depends on the preset's map and whether the clip should take the grade (above the grade layer = ungraded, usually right for a generated clip).

Three engine facts a graphics pass needs: **⚠ `export_frame`'s TIME argument is broken** (QE reads the string as a FRAMES timecode, so `time: 18` exports frame 18) — always grab through the bridge `frame` command, which converts seconds off the sequence fps; **`remove_effect` is absent** and no-arg QE `removeEffects()` returns true while removing nothing, so strip effects with QE `item.getComponentAt(i).remove()`, matching `comp.name` and iterating indices BACKWARDS; and **`add_keyframe` writes raw SOURCE time**, so keep computing `inPoint + offset` (the `zoom` command does). Other per-tool arg quirks: read the zod schema in `vendor/premiere-mcp/src/tools/index.ts`, never `--desc`; the measured status map is in the archive (§ Notes).

## Step 6: SFX on the timeline (built 2026-09-03; placed and readback-verified on two reference jobs (120/120 and 122/122 rows, the second reviewed and hand-tuned by ear the same day))

WHAT: [`presets/youtube/default/sfx.md`](../../../presets/youtube/default/sfx.md). The plan is
universal and already written (`uv run workflows/sfx-plan.py projects/<job>` →
`hf-graphics/sfx-plan.{json,md}`); this lane only places it.

```
uv run lanes/premiere/place-sfx.py projects/<job> --apply     # place, re-lay a cue the plan moved (start held to half a frame), set levels, read back, save
uv run lanes/premiere/place-sfx.py projects/<job> --verify    # readback vs the plan (exit 1 on drift)
uv run lanes/premiere/place-sfx.py projects/<job> --diff      # the creator's hand edits vs the plan (MOVED / REMOVED / LEVEL / SLICE / ADDED): the input for the next rule
uv run lanes/premiere/place-sfx.py projects/<job> --remove    # clear ALL library SFX clips, only for a deliberate full replacement
uv run lanes/premiere/place-sfx.py projects/<job> --remove s004,s017 s020 [--dry]   # those ids only (commas and/or spaces); an EMPTY list is refused, never the full clear
uv run lanes/premiere/place-sfx.py projects/<job> --remove-extra [--dry]            # clear exactly the clips --verify calls extra
uv run lanes/premiere/place-sfx.py projects/<job> --adopt [--dry]                   # the creator's accepted timeline becomes the plan (backed up first)
uv run workflows/sfx-plan.py projects/<job> --merge g7,g9                          # re-plan only those graphics into the approved plan
uv run workflows/sfx-plan.py projects/<job> --record [--plan <file>]               # record a plan's placement (staleness check), no row changed
```

Options on `place-sfx.py`:
- `--plan <file>`: a variant's cut sheet.
- `--sequence NAME` (or `VE_SEQUENCE`): the guard and every script are held to that sequence.
- `--until T`: the copy window. T is the first frame where the two sequences differ, at or before the target's own first cue. `--adopt` records it in the variant plan's `.meta.json`, every later command on that plan holds it, and `--adopt --until none` clears it. It is never allowed on the job's own sfx-plan.json.

**An AD cut's SFX are copied from the organic, never hand-synced:** the organic → AD recipe is in [`lab-notes.md`](../../../lanes/premiere/lab-notes.md) (the adopt / copy bullet).

**Graphics revisions:** follow [`sfx.md`](../../../presets/youtube/default/sfx.md)'s incremental revision procedure. Diff first; fold hand edits upstream; re-plan only the affected graphics with `sfx-plan.py --merge <gids>` (a bare re-run rewrites the whole plan and names the changed IDs; `--candidate` parks a whole-plan comparison); remove exact stale affected clips; apply and verify zero missing/extra/drifting cues. `--remove` with no ids clears the whole library score and is not the incremental path.

**Before your sound pass, every library sound is one drag away:** `uv run lanes/premiere/load-sfx-pack.py projects/<job>`
(⚠️ offline-proven 2026-10-14) imports the whole `assets/sfx/` library into the `sfx` bin, sub-folders as sub-bins;
the rest of the tidy (the root holding only bins, superseded renders in `old versions` sub-bins, every timeline's
clip counts identical before and after) is by hand: the Talking Head Explainer's
[`sfx.md`](../../../presets/instagram/talking-head-explainer/sfx.md) § 7. **A calling bed's fade** (`fade_out_s` on the
cut sheet) is a Constant Power audio transition of that length on the clip's tail, laid by hand after `--apply` and
named in the report.

**After the creator's hand pass, `--diff` runs BEFORE any re-place:** `--apply` overwrites hand
edits, and the diff is how they become the next rules in `sfx.json`.

Mechanics, each read back before it is believed: the library file is imported ONCE into an `sfx` bin
and found by media path afterwards; audio tracks come from QE
`addTracks(0, 0, 1, 1, numAudioTracks, 0, 0)` (appends, nothing placed moves); the slice is the
project item's in/out (`setInPoint(t, 4)`) + `audioTracks[n].overwriteClip(item, at + 1e-4)` (the
replay's floor nudge), then in/out cleared; the level is the clip's Volume > Level through
`lanes/premiere/clip_level.py`'s `lvl_v`, never a re-derived formula (§ Step 3, and the encoding's home in
[`lab-notes.md`](../../../lanes/premiere/lab-notes.md)). A laid audio clip's in-point is also floored to
the sequence grid, so `place-sfx.py` writes it back and reads it back per clip — a run that finds a
floored row FINISHES the batch, names every affected row and refuses to save (the write-back is proven
live, 2026-09-23; source-in is held to half a frame, and a cue laid before the write-back existed is re-placed: `lab-notes.md`,
the audio in-point bullet) — and
a timeline rebuild drops these clips like the A1 chain: re-run `--apply`.

### Background music (the opt-in pass, after SFX)

The WHAT is the `background-music` skill; on this lane the bed goes on **A5** (the `music` role) by
`place-music.py`, validated on your-job 2026-09-04 (remove → apply → verify → bounce, twice):

```bash
uv run lanes/premiere/place-music.py projects/<job> --apply     # newest audio/ track → A5 at 0, source in at the reviewed sustained entrance, the house bed level written through the keyframe, 2s tail, read back, saved
uv run lanes/premiere/place-music.py projects/<job> --bounce    # music-only WAV via exportAsMediaDirect (no AME): LUFS + "plays from the first frame"
uv run lanes/premiere/place-music.py projects/<job> --verify    # readback vs the numbers
uv run lanes/premiere/place-music.py projects/<job> --remove    # off the track (before a re-place or a level change)
uv run lanes/premiere/place-music.py projects/<job> --apply --refit   # after any ripple: remove the bed, re-lay from hf-graphics/music-plan.json (flags override), verify, save once. A laid value that disagrees with the plan is refused as a hand edit, and both commands are printed. A bed razored by hand is trimmed in place instead: its last clip to the end, its tail keys moved, every clip recorded in the plan
```

The bed's Level uses the same encoding as SFX and is time-varying (the 2 s tail), so it is written
through `setValueAtKey` on the first key, never `setValue` — the readback-lies trap in
[`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md).

## Step 8: export (on the creator's go — scripted, never AME)

**Two deliverables (an organic and an AD):** export the organic, then the AD (`--sequence "<job> AD"`), then make
the organic sequence active again, because every lane script acts on the ACTIVE sequence. The organic → AD copy
recipe is in [`lab-notes.md`](../../../lanes/premiere/lab-notes.md).

**Where the automated work ends by default:** the graphics pass and its defect loop finish at *placed +
verified*, the run pauses at step 7, and the export runs when you say so (you did on your-job,
2026-09-07). **AME is banned** (2026-07-20) for everything — full exports, QA bounces, audio checks
alike — and `export_sequence` queues into it, so the ONLY render route is
`sequence.exportAsMediaDirect(outPath, presetPath, workAreaType)` via `execute_extendscript`: synchronous,
in-Premiere, no AME. `workAreaType` 0 = the whole sequence, 1 = in/out (clear the marks first).

**THE PRESETS (the WHAT and its reasons are the preset README § Export, 2026-09-26):**
`lanes/premiere/premiere-templates/youtube-2160p-h264-cbr50.epr` (3840×2160, H.264 High, **CBR** target = max = 50 Mbps
via `ADBEVideoBitrateEncoding` 0, AAC 320k, BT.709, moov first) takes a 4K AND a 1080 timeline;
`youtube-2160p-h264-cbr50-2997.epr` on a 29.97 sequence (the exporter matched the sequence rate even from the 30.00
file, but say it explicitly); above 30 fps `export.py` mints `youtube-2160p-h264-cbr80.epr`. A vertical sequence of
either size exports through `instagram-1080x1920-h264-cbr14-23976.epr`, past 2:48 through a minted lower-bitrate twin,
so the file always fits Meta's 300 MB. Max Render Quality is off and moot (GPU scaling is already maximum quality).

**Colour tags and the delivered bitrate are read off the file (2026-09-27).** The Mac's hardware encoder writes bt709 on
primaries, transfer and matrix; Premiere on Windows wrote none (every tracked `.epr` has `ADBE_H264_ColorPrimaries`
false and disabled), so `export.py` stamps bt709 onto an untagged H.264 file losslessly (a stream copy through
`h264_metadata`) and then fails anything that still reads otherwise. It prints the delivered video bitrate and warns
under 90% of the preset's CBR target: the Windows encoder delivered 41.2 Mbps from CBR 50, inside YouTube's own
35–45 Mbps row for 4K at 24–30 fps, and these templates' exporter has no hardware/software encoder switch to force it.

⚠️ **Premiere's H.264 exporter caps the frame at 4096×2304** (live 2026-09-26: a 2160×3840 preset wrote a 1296×2304
file with no error), and its HEVC exporter (the `4A454646_48455643` system presets) answers `exportAsMediaDirect`
with −1. So the 4K vertical file for YouTube Shorts (`--shorts`, a 2160×3840 sequence only) is a ProRes 422 HQ master
through the installed Premiere's own `Apple ProRes 422 HQ.epr` system preset, encoded by `workflows/deliver.py` to
the preset's numbers; the master is deleted once the file is proven. Proven live 2026-09-26: 2160×3840 H.264 High 5.1,
CBR 50, bt709. The hardware H.264 writes a 1 s GOP whatever the `.epr`'s keyframe value says (YouTube asks half
the frame rate; harmless).

`mint-export-preset.py` still mints a native `youtube-1080p-h264-cbr50[-2997].epr` for a `--preset` export when a
1080 FILE is genuinely wanted; nothing picks it by default any more.

```bash
uv run lanes/premiere/export.py projects/<job>                        # -> outputs/<job>-final.mp4, then ./finalize.sh <job> --apply
uv run lanes/premiere/export.py projects/<job> --draft                # -> outputs/<job>-draft-<n>.mp4 (never promoted; only for a proof that reads a render, edit-video § A check never exports a draft)
uv run lanes/premiere/export.py projects/<job> --sequence "<job> AD"  # -> outputs/ad/<job>.ad.mp4 (the AD sequence must be the active one)
uv run lanes/premiere/export.py projects/<job> --shorts               # 2160x3840 only -> outputs/shorts/<job>.shorts.mp4, then finalize --variant shorts
```

The tool owns everything the hand call used to get wrong: the active-project guard plus the
`VE_SEQUENCE` sequence rule; the preset picked from the sequence's size and rate; absolute paths
(Premiere resolves a relative one against its own cwd); a `--timeout-min` (default 60) that outlives the
panel's 45 s watchdog; the wait (the file closed per `lsof` and the same size across 3 checks 2 s apart,
never ffprobe mid-write, where Premiere's file has no moov yet — a call that RETURNS while Premiere still
writes is waited on to the close); and the ffprobe proof: moov present, the preset's frame size, the
sequence's rate, a frame count equal to the timeline's (the later of `seq.end` and the latest clip end,
±1 noted) and ≤ 300 MB on the Reels preset. A call that returns with no file on disk fails within
seconds, naming what Premiere returned; a bridge that gives up mid-export ('not running', a timeout) is
not the verdict, the file is. A failed check exits non-zero, names itself and keeps the file.
`--preset <epr>` overrides the pick (a preset of another SHAPE is refused: it would pillarbox), and
`--force` replaces an existing output, deleting the old file before the export so it can never pass for
the new one (after a timeout, wait for Premiere to close the file first). Never hand-type
`exportAsMediaDirect` for a deliverable again. Proven live 2026-09-23 on a throwaway, a 7200-frame
export included. Then `./finalize.sh <job> --apply` promotes it + drops the `~/Downloads` copy. VMAF measurements and the
`.epr` patching recipe: the engineering archive.

## Fallback — flat clip import

Only when the EDL is unavailable (old job, `cuts.json` lost from both spots) or you ask for "just the flat cut as a reference":

1. `import_media` the `outputs/<job>.mp4`.
2. `create_sequence_from_clips` with it — the sequence inherits its dimensions/framerate AND the clip lands on V1, so no `add_to_timeline` is needed.
3. Save and tell you it's the **flattened** cut: the individual edit points aren't recoverable, so re-trims mean razoring by eye. For real edit points, re-run `rough-cut` to persist a fresh `cuts.json` and hand off again.

## Notes
- **When you references live timeline state — "the in and out points I set", "the highlighted clip", "what I selected", "at the playhead" — QUERY PREMIERE FIRST, before any interpretation (2026-08-28, you had to demand it).** Your marks and selection are one call away: `seq.getInPoint()`/`getOutPoint()`, `clip.isSelected()` across tracks, `get_playhead_position`. Inferring the target from conversation once got a wrong segment diagnosed AND deleted. Your timeline state IS the instruction. Clear marks (`setInPoint(0)`/`setOutPoint(0)`) after acting on them.
- Keep the HANDOFF surgical: import raw + matching sequence + the EDL replayed onto V1.
- **Job projects live at `projects/<job>/premiere/<job>.prproj`, always.** Never let one be born from Premiere's own save dialog — its default is the rotating Auto-Save folder, which Premiere prunes (two job projects were rescued from there 2026-07-17). Superseded drafts go in `premiere/archive/`. A project in the WRONG job folder relocates in ONE call: ES `app.project.save(); app.project.saveAs(newPath)` — verified 2026-07-29 with the project open and a live timeline; delete the stale copy afterward. The DOM `saveAs` is NOT the untested `save_project_as` MCP tool.
- **Adjustment layers: scripting can't CONSTRUCT one, it MINTS one from the tracked donor project (solved 2026-07-22), at the SEQUENCE'S size, always (2026-09-02).** The mechanic lives in [`lanes/premiere/premiere-grading.md`](../../../lanes/premiere/premiere-grading.md) § 1; the bridge `grade-layer` command runs it for you.
- `.prfpset` presets and curve-handle geometry are NOT scriptable — bake instead (§ Step 5 keyframe laws). The MCP otherwise exposes the full DOM/QE surface; `get_project_info` discovers state. The measured per-tool status map on the pinned clone — what works, what is broken or absent, what is untested — is in the engineering archive.

### Colour labels

- **THE COLOUR LABELS ARE THE CREATOR'S MAP OF THE SECTIONS, AND EVERY CLIP LAID LATER MUST CARRY ITS SECTION'S COLOUR (2026-09-19).** "That's the whole reason that I have you label the clips in different colors: so that I can visually see the different sections." It is not decoration and not a multi-section-job nicety: it is how you reads the timeline, and how the sections' boundaries are answered later (asked for the five sections, the labels ARE the answer — read them off the items, never re-derive from the transcript). A clip inserted afterwards — a re-lay, an alternate angle, a revert, a repair, an audio-only or video-only subclip — inherits the label of the PROJECT ITEM it came from, so it must be laid from that section's item; a new subclip gets `setColorLabel(n)` to match before it is laid, and an uncoloured clip in the middle of a section is a defect to fix. **A section that shares its source FILE with a neighbour gets its OWN project item (2026-09-18)**, or labelling one section recolours the other: re-import the same raw (`importFiles` duplicates it), rename the copy, label it, point that section's EDL rows at the new name in a copy of `cuts.json`, and re-lay V1/A1 only — positions come back identical to the frame, so the grade, graphics and placements stay put (re-apply the audio polish and re-bake the zooms). Verify after any structural edit: `node lanes/premiere/premiere-bridge.mjs labels` walks V1/A1 and exits 1 on a label-0 clip INSIDE a labelled timeline (an all-grey timeline is a job that never used sections, not a defect) or on a colour that re-opens a run already closed; it reads the ITEM, though, and a clip laid before a relabel still DISPLAYS the old colour, so the confirmation is looking — `./workflows/window-grab.sh "Adobe Premiere" out.png`, then read the V1/A1 strip. (Item names once "proved" five clean runs on a visibly wrong timeline: [`lab-notes.md`](../../../lanes/premiere/lab-notes.md) § Step 2.)
- **Section color-coding (every long-form, and any multi-section job): set the project item's label BEFORE the replay** (`item.setColorLabel(idx)`, 0–15) — timeline clips stamp the label at insert time, so relabelling later never recolors laid clips. **Label NAMES lie about rendered color (2026-07-31)**: pick a candidate by RGB distance against the sections already laid, never by name — and never with a throwaway clip on the timeline any more, because the palette is readable straight out of Premiere's own Prefs file ([`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md), the BGR-packed `BE.Prefs.LabelColors.N`). The 16 names and the original on-timeline
