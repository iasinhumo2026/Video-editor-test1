---
name: final-cut-pro
description: "Finish a job inside Final Cut Pro, the Final Cut counterpart to premiere-pro, through SpliceKit (a patched copy of Final Cut with a JSON-RPC bridge and MCP server inside it). Builds a fresh job's whole timeline from its pipeline files as FCPXML (every cut a real clip, J/L cuts as split edits, layout keys or push-ins, the house LUT on the footage, graphics, captions, SFX, music), imports it through Final Cut's own importer, proves the live project clip by clip, and exports with no clicks: Final Cut renders the ProRes master, then the format's deliverable. Also ports a finished Premiere sequence into Final Cut. Triggers: send to final cut, open in final cut, finish in final cut, edit this in final cut, fcp, final cut timeline, port this premiere edit to final cut, rebuild in final cut."
---

# Final Cut Pro — the SpliceKit lane

Everything app-specific lives in [`lanes/finalcut/`](../../../lanes/finalcut/README.md): the install, the per-step
table, the scripts. **Read its [`lab-notes.md`](../../../lanes/finalcut/lab-notes.md) before touching the lane**: the
locks, nearly every one a silent failure that cost a rebuild on the lane tests (2026-09-25).

## 🔒 STEP INDEX — what this lane does at each pipeline step

The preset says WHAT; each row here says HOW on Final Cut. `LANES.md` wins if they disagree. One script reads every
pipeline file: `uv run lanes/finalcut/replay.py projects/<job>` (`--steps` stops it where the run has got).

| # | Step | How on Final Cut |
|---|---|---|
| 1 | Intake | universal |
| 2 | Replay | `replay.py` (cuts.json, sections included) → `import.py` (a Premiere port instead: `lanes/finalcut/prproj-read.py` → `port-premiere.py`) |
| 3 | Audio polish | baked into the media: `workflows/normalize-sections.sh projects/<job>`, then `replay.py` lays `audio-normalized/`; the second-voice lift as dialogue volume keys |
| 4 | Grade | Custom LUT → the folded house cube on every camera-footage clip (`templates/house-lut-filter.xml`) |
| 5 | Graphics / captions | `workflows/placement.py --write`, then `placement.json` as connected clips on lanes 1.., straight alpha as rendered (organic only: no ad variant, `--variant` is Premiere-only) |
| 5′ | Footage moves | the `layout` map through face-frame.json `modes` (1-frame key pairs at a switch); long-form: the zoom-out and push-ins as 19 linear keys |
| 6 | SFX | `sfx-plan.json` on lanes −1.., levels as `adjust-volume`, embedded timecode honoured; `sfx-pack.py` makes the whole pack a library to drag from (⚠️ import unproven live) |
| + | Music | `workflows/music-onset.py <track> --write-plan`, then `music-plan.json`: the bed at `source_in`, keyed to −96 dB over the tail |
| 7 | Review | the creator's |
| 8 | Export | `export.py projects/<job>`: Final Cut renders the ProRes master with no clicks (`share.py`), then the deliverable, then `finalize.sh` (organic only: `--variant NAME` just files a second export under `outputs/NAME/`) |

## Procedure

1. **Bridge up: `uv run lanes/finalcut/doctor.py --repair`.** It is the ONLY way Final Cut is started: it quits a
   Final Cut that is not the lane's copy (the App Store app swallows every launch of the copy while it runs), moves
   stale patched copies to the Trash, launches the ONE copy by its path and proves the bridge (lab-notes § 13, § 21).
   Never start, quit or attach to Final Cut by name, bundle id, the Dock or computer use, and never use the MCP's
   `deploy_and_restart`. **Two failed bridge connects (`sk.py` exit 2, an MCP call timing out) → run the repair
   yourself; never send the user to quit and reopen Final Cut, SpliceKit or the agent.** Its exit 4 is the one thing
   the user does: the click in SpliceKit it printed (Final Cut is already quit), then the repair again. A ⚠ that Final
   Cut was updated past its copy means `./setup.sh --lane finalcut` is due (one click); the old copy runs until then.
   `uv run lanes/finalcut/sk.py --dismiss` clears the notification sheet if it is up. `import.py` and `share.py`
   attach through the same check (`doctor.ensure()`).
2. **Step 3 first, as soon as step 2's polished `cuts.json` is final, before the replay:** `workflows/normalize-sections.sh projects/<job>`
   (every raw, each section's with its own gain; `DRY=1` measures only).
3. **Build:** first the two files other tools write: `uv run workflows/placement.py projects/<job> --write` (the
   graphics rows, once the renders exist) and, when there is a bed, `uv run workflows/music-onset.py <track>
   --write-plan projects/<job>`. Then `uv run lanes/finalcut/replay.py projects/<job>` writes `projects/<job>/finalcut/<name>.fcpxml` for a new
   library `<name>.fcpbundle` (`<job>`, then `<job>-v2`, ...). Read every ⚠ it prints: each is something laid
   differently from Premiere or not at all (no baked audio, a partly graded clip, a graphic at native pixels, music
   short of the bed, graphic cells with no `placement.json`, a song with no `music-plan.json`). `--steps 2` lays the
   cut only, `--grade-ranges A-B` grades the camera footage only when the plan has no `graphics_scope` ranges
   (screen-recording footage stays bare), `--lift N|0` overrides the lift, and `--format
   long-form|short-talking-head-explainer|tiktok-raw` names the format for a job with no graphics-plan.json yet (else
   RUN.md's preset / format row; with step 4 asked and neither, it refuses). The lane builds the organic cut only: no
   ad variant (`--variant` is Premiere-only). A Premiere
   port instead: `uv run lanes/finalcut/prproj-read.py <job>/premiere/<job>.prproj --sequence "<name>" --out
   timeline.json`, then `uv run lanes/finalcut/port-premiere.py timeline.json --out … --library … --media-map
   <raw>=<audio-normalized copy>`. The Final Cut project takes the sequence's size, except that a portrait sequence
   becomes 1080x1920 (a 2160x3840 short's deliverable); `--width`/`--height` override.
4. **Import and prove:** `uv run lanes/finalcut/import.py <fcpxml>`: exit 0 means the live project equals the build.
   Every later step re-runs 3 and 4 into a new library; the creator's hand edits live in the library they made them
   in, so read them before a rebuild (`verify.py <new build> --live <sk.py fcpxml.export of the old one>`).
5. **Export on the creator's go:** `uv run lanes/finalcut/export.py projects/<job>` (`--project "<name>"` for another
   than the newest build). Final Cut renders the project through its own share sheet (Export File, ProRes 422, Save
   only: set once in the destination's Settings) into `finalcut/renders/<name>-master.mov`, the save panel completed
   from inside Final Cut, no clicks (lab-notes § 14); the master's frame count is held to the timeline, then the
   format's deliverable is encoded by `workflows/deliver.py` to the preset's numbers (a 1080 landscape master goes up
   at 3840×2160; a 2160×3840 one gives the 1080×1920 file, and `--shorts` then its 4K YouTube Shorts file into
   `outputs/shorts/`, finalized with `--variant shorts`) and proven into `outputs/<job>-final.mp4`. The render is a background task:
   `share.py` opens Final Cut's Background Tasks window (⌘9) for its progress bar, with no save panel or other sheet
   left up. Then `uv run workflows/flash-scan.py <file> --expect projects/<job>` and `./finalize.sh <job> --apply`.
   A `--project` named `… AD` is refused without `--variant ad` (it would be filed as the organic deliverable).
6. **Prove the picture and the sound** when a reference master exists: per-frame PSNR (the port test: 44.5 dB mean,
   39.6 worst), an aligned audio null test (lab-notes § 12).

## Live driving

The `splicekit` MCP server (`.mcp.json`) exposes 231 tools for anything past the build: `get_timeline_clips`,
`blade_at_times`, `apply_effect`, `set_inspector_property`, `capture_viewer`, `export_xml`, the dialog tools. Scripts
use `lanes/finalcut/sk.py` (the same bridge, no MCP client needed). Read live state before a deictic ("the clip I
selected" → `get_selected_clips`), and never `fcpxml.import` / `import_fcpxml` (lab-notes § 1).
