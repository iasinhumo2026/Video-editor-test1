---
name: capcut
description: "Finish a job inside CapCut — the CapCut-user counterpart to premiere-pro (editing apps are the primary path; Premiere is your default, CapCut is for CapCut-user clients). Builds a real CapCut draft from the EDL (one trimmable clip per cut), then drives the running app live to place graphics, edit, and export — CapCut has no API, so this is the only way to script it. Triggers: send to capcut, open in capcut, finish in capcut, hand off to capcut, edit this in capcut, build a capcut draft, export from capcut, take it into capcut."
---

# To CapCut — Rough Cut Handoff + Live Driving

The CapCut twin of the Premiere lane (§ Relationship to the rest of the repo). **Editing apps are the primary finishing path — this is not an "off-ramp."** After the rough cut (pipeline step 2), rebuild the cut on a CapCut timeline and do the work there — this skill can carry it all the way to an exported file.

Everything runs through one script: **`lanes/capcut/capcut-bridge.py`** (macOS and Windows, self-contained `uv` header — no venv; on Windows its live lane runs on `lanes/capcut/capcut_win.py`, § Windows below). Run `uv run lanes/capcut/capcut-bridge.py` with no args to print the full command list.

## 🔒 STEP INDEX — what this lane does at each pipeline step

**This skill carries HOW, never WHAT.** The look, the numbers and the definition of done for every
step live in the format's preset ([`presets/youtube/default/README.md`](../../../presets/youtube/default/README.md)
for long-form). Read the preset for the target, then the row below for the mechanics.
Cross-lane status: [`LANES.md`](../../../LANES.md).

| # | Step | On this lane | Where |
|---|------|--------------|-------|
| 1 | Intake | — universal, no CapCut involvement | CLAUDE.md § Pipeline |
| 2 | Rough cut → replay | ✅ scripted — `replay` writes a whole draft from the EDL | Procedure 2 below |
| 3 | Audio polish | ✅ baked into the SOURCE before `replay` (`normalize-sections.sh` → `replay --media`) | § Step 3 below |
| 4 | Color grade | ⛔ no LUT surface in the bridge | § Step 4 below |
| 5 | Graphics | ✅ scripted — `graphics` lays `placement.json` (premultiplied for you); `add-overlay` / `add-text` / `keyframe` for one-offs (PREMULTIPLY alpha first) | Procedure 4-6 below |
| 5' | Footage layout (Talking Head Explainer) | ✅ scripted — `layout <draft> <job>` lays the plan's S/T/W modes as static values or hold-key pairs | Procedure 4 below |
| 6 | SFX | ⛔ plan only (placing); `capcut-bridge.py sfx-pack <draft>` loads the whole pack into the Media panel for hand placing (⚠️ unproven live) — [`LANES.md`](../../../LANES.md) § step 6 | [`presets/youtube/default/sfx.md`](../../../presets/youtube/default/sfx.md) |
| 7 | Review | ✋ the creator's. The run pauses here. | — |
| 8 | Export | ⚠️ scripted — drives the real export dialog and verifies the file against the draft; the dialog's settings are set by hand | Procedure 8 below |

⚠️ **The one habit that must NOT cross from the other lanes: alpha.** CapCut composites ProRes 4444 as
**PREMULTIPLIED**: convert every CapCut-bound alpha mov first (Procedure 4), the short-form caption layer
(`hf-graphics/captions/renders/captions-alpha.mov`) included, which goes on the top layer for the whole cut.

## Why this is different from every CapCut MCP

CapCut has **no API of any kind** (researched exhaustively 2026-07-27 — see [`lanes/capcut/lab-notes.md`](../../../lanes/capcut/lab-notes.md)). Every "CapCut MCP" on the market blind-writes a draft file and stops there. This bridge does both halves for real:

- **File lane** — writes/edits the plaintext draft JSON CapCut stores under `~/Movies/CapCut/User Data/Projects/com.lveditor.draft/` (Windows: `%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft\`, or the custom draft path in `Config/globalSetting`). Structural, batchable, exact. Requires the app be **quit** during the write (it rewrites its draft registry on exit); the bridge quits + relaunches around each write.
- **Live lane** — drives the *running* app through ByteDance's own internal automation IDs, exposed in the macOS accessibility tree. Find element by name → click its center with a synthesized event → **read state back**. A true locate-act-verify loop, no restart.

**This drives the real desktop app: it takes over mouse, keyboard, and window focus for a few seconds per live action.** Warn before starting a live-lane run if the machine is in use (file-lane writes only need the app quit, no screen takeover). AX ids are internal test hooks, **not a contract** — if anything stops responding after a CapCut update, re-map with `dump` before assuming the bridge broke.

⚠️ **The ruler has a dead strip about 90px wide at its left edge** that silently eats clicks (measured at two zoom levels, fixed in screen space), so the first few seconds of the timeline can't be clicked to directly. `seek` handles it — it lands where it can, then closes the gap with arrow-key frame steps. Those steps must be **paced**: sent back to back CapCut drops most of them (195 sent, 28 applied). `key <k> --times N` paces them for you. Two other focus rules: synthesized input only reaches CapCut when it's frontmost (the bridge activates it before every click and key — when it wasn't, the *first* click was consumed activating the window, which is what made `calibrate` fit garbage), and arrow keys only reach the timeline after something in the timeline has been clicked.

⚠️ **Check for a coach-mark before trusting any live action.** CapCut pops yellow onboarding tooltips ("Right-click the keyframe to create variable speed animations", etc.) that sit *over* the UI and silently swallow clicks in that region — they do **not** appear in the AX tree, so `dump` looks clean and every command reports success while doing nothing. One parked over the left end of the ruler broke `seek` for half an hour: clicks near t=0 vanished, `calibrate` fitted garbage from the one point that did land, and the playhead ended up 40s from target. **If a live action reports success but the state didn't change, `shot` the window and look for a yellow bubble**, then dismiss it with an offset click on its OK. Worth a `shot` at the top of any live session.

## Windows — the live lane (`capcut_win.py`, proven 2026-09-27 on CapCut for Windows, Qt 6.2)

CapCut on Windows exposes NO accessibility tree below its top-level windows (UIA sees `HomeWindow`, `MainWindow`, splash and update dialogs by automation id; no QML child, no MSAA). So the live lane there is **the app's own keyboard shortcuts + OCR read-back** (RapidOCR, offline, pip; Windows' own OCR never read the player timecode), with clicks at positions fitted from what OCR reads (the ruler's labels, the track's `Cover` button, the dialog's buttons). Every command above works the same by name; the differences that matter:

- **Shortcuts come from the ACTIVE keymap** (`Config/keymapSettings currentKeymapIndex`; 0 = CapCut's built-in, whose split is **Ctrl+B** and export **Ctrl+E**, the same bindings as the shipped `Final Cut Pro X.json`). `Custom1.json`'s Ctrl+K did nothing. `capcut_win.shortcut(<action>)` resolves every live key; never hardcode one.
- **Toasts and tours are painted INSIDE the editor** and swallow clicks under them (the shortcut-conflict toast, the EditPilot tour, "Auto optimization is on"): `dismiss_tips()` closes them once per command.
- **The player readout is the read-back.** A 29.97 draft reads drop-frame (`00:00:32;10`) and its ruler labels become full timecodes; `parse_tc` converts drop-frame to real time.
- **Export**: the dialog and the share screen are both painted in the editor; the share screen holds the file OPEN (a move fails "resource busy") and swallows the export shortcut while it is up, so the bridge closes it by the **Close** beside Share (never Share) before and after. An overwritten export keeps its old mtime, so files are compared by (size, mtime, birth), and only files named after the dialog's own Name count. A short draft renders in seconds and CapCut then shows the export dialog AGAIN: a click is taken when the render's file changes, never by the dialog closing, and the re-shown dialog is cancelled after. CapCut's "File already exists … replace it?" is never answered OK (the file may be the creator's own export): its Cancel, the dialog's Cancel, exit naming the file.
- **Quitting** closes the editor back to the Home window, which needs its own close: `quit_app` re-closes until the process is gone.
- **Save**: there is no save shortcut; `save` returns to the drafts page (CapCut saves on the way) and reopens.
- **Speed**: about 2 s a seek, one OCR pass a read (RapidOCR's detector must not upscale small crops: `params={"Det.limit_type": "max"}`).
- **Text templates** carry macOS font and animation paths; CapCut re-resolves both by resource id and rewrites them to the local cache on open, so they work unchanged.

## When to use
- Any trigger phrase above, OR a rough cut exists and the job should finish/export in CapCut rather than HyperFrames or Premiere, OR it's a deliverable for a client who edits in CapCut.

If there's no rough cut yet, run `rough-cut` first **with `RENDER=0` on the splice** — same as the Premiere path, the EDL + canonical transcript generate in ~8s with no flat render, and `replay` consumes nothing else. Never render a flat MP4 for a CapCut-finish job.

## The two lanes — pick per action, don't mode-switch up front

| Need | Lane | Restart? |
|---|---|---|
| Build the rough cut from the EDL | file (`replay`) | no — a fresh draft has no cache yet |
| Place graphics / text / transforms in bulk | file (`add-overlay`, `add-text`, `transform`, `remove`, `graphics`) | yes — quits + relaunches (the bridge does it) |
| Interactive trim / split / delete / seek | live (`seek`, `split`, `delete`, `undo`, …) | no |
| Export the finished video | live (`export`) | no |

**Golden rule (learned the hard way, 2026-07-27):** once a draft has been hand-edited in the app, file-lane commands **additive-edit the current `draft_info.json`** — those edits are saved into it on quit. Never regenerate from the EDL over that work; a rebuild clobbered a hand-extended segment. `replay` is for a *fresh* draft only; `add-*`/`transform`/`remove` build on whatever's there.

## Procedure — build → edit → export

1. **Resolve the job.** Newest folder under `projects/` unless one was named. The EDL is `projects/<job>/transcript/cuts.json`; the raw clips are in `projects/<job>/raw/`. Both must exist (same requirement as the Premiere replay).

2. **Build the rough cut:**
   ```
   uv run lanes/capcut/capcut-bridge.py replay <job> [--name <draft>]
   ```
   Writes a whole draft from the EDL — one timeline segment per cut, source times in microseconds, butt-joined so each cut lands where the EDL says (verified 10/10 exact on the intro, zero drift). Draft name defaults to the job name. The raw is **hardlinked** into `<draft>/Resources/` because CapCut's sandbox (`assets.movies.read-write` only) can't read repo paths — a path outside `~/Movies` opens as a red "File not accessible" timeline. `replay` relaunches CapCut when done.

   **The draft is built at the FOOTAGE's frame rate, every cut on that grid** (2026-09-27). CapCut stores the rate as `fps` plus `is_drop_frame_timecode`, 29.97 as the EXACT `30000/1001` with drop-frame on; a rounded 29.97 without the flag came back 30.0 after CapCut's own save. Every earlier draft was written at a hardcoded 30.0, so a 29.97 take landed every cut a frame late and exported at 30. Changing the rate afterwards in Project settings keeps each clip's FRAME COUNT and slides every cut, so it has to be right at `replay`: the rate is read off the media (`r_frame_rate` when it is on CapCut's list: 24, 25, 29.97, 30, 50, 59.94, 60). Proven: a 29.97 replay exports 970 frames with every cut on the same frame as the Premiere final of the same job.

3. **Open it and confirm:**
   ```
   uv run lanes/capcut/capcut-bridge.py open <draft>
   uv run lanes/capcut/capcut-bridge.py state --draft <draft>   # JSON snapshot: tracks, exact seg times, unsaved-edit flag
   ```
   `state` reads exact times from disk and compares the live clip count against the saved draft, so it flags unsaved changes.

4. **Place graphics (file lane, batched).** Alpha HyperFrames movs and text both work:
   ```
   uv run lanes/capcut/capcut-bridge.py add-overlay <draft> <path/to/graphic.mov> --at 1.0 [--layer 1] [--dur 3]
   uv run lanes/capcut/capcut-bridge.py add-text   <draft> "built by claude" --at 20 --dur 3
   uv run lanes/capcut/capcut-bridge.py transform  <draft> --track overlay --index 0 --scale 0.6 --y -0.25
   uv run lanes/capcut/capcut-bridge.py remove     <draft> --track text --index 1
   ```
   - **Overlay** = a second video track (`flag: 2`, `render_index` 1). ProRes 4444 alpha composites with true transparency (validated on `g1txt.mov`). `--layer N` stacks higher.
   - **PREMULTIPLY every CapCut-bound alpha mov first.** CapCut composites ProRes 4444 assuming PREMULTIPLIED alpha; hyperframes renders STRAIGHT. Where alpha is 255 the two are identical, which is why solid type (the `g1txt` validation) looked perfect, but every semi-transparent pixel (motion blur, glows, soft shadows, letter fades) composites as `RGB + (1-a)*bg` and blows out to white; motion-blur trails become fat white blobs. Convert before `add-overlay`: `bash lanes/capcut/premultiply.sh <in.mov>` (writes `<in>-premult.mov` beside the input and prints its path). Premiere AND Resolve both assume STRAIGHT (Resolve auto-detects it), so never premultiply a render bound for either — this fix is CapCut-only.
   - **Text** = a text track (`flag: 1`), built from a template lifted from a real draft (`lanes/capcut/capcut-templates/`). The style run is re-pointed at the new string automatically.
   - **transform** — exact scale/position/rotation/opacity written straight into the draft. **Position runs over the HALF canvas (±1 is an edge) and +y is UP** (measured 2026-09-27: `--y -0.5` moved the picture DOWN a quarter frame; the older note here had both the unit and the sign wrong). This is file-lane on purpose: the inspector's on-screen fields take focus but **ignore synthesized keystrokes**, so the JSON is both the precise and the only reliable path.
   - **graphics** `<draft> <job>` lays the job's `hf-graphics/placement.json` (write it first: `uv run workflows/placement.py projects/<job> --write`) in one cache cycle: each row at its `start` for `end − start` on the draft's frame grid, its placement track mapped to a layer (graphics 1, overlaps and patches 2, the caption layer one above the highest), each alpha mov **premultiplied automatically** into `hf-graphics/capcut-premult/` (reused while newer than its render; never beside the render, where the placer's version glob would read it as a new version), a full-screen mp4's own sound muted, a row already at its start left as it is. Layers are created lowest first (queued the other way, a caption row became layer 1 and CapCut pushed every later graphic past its end, 2026-09-27). `<job>` is a job name or a job folder path.
   - **layout** `<draft> <job> [--hand a-b:MODE=scale,cx,cy]` lays the Talking Head Explainer's footage modes on the main track the way `lanes/premiere/layout-keys.py` does: spans from the preset's `layout.py`, modes from `face-frame.json`, a clip with no switch gets STATIC values, a switch inside a clip is a key pair (outgoing one frame before, incoming on the switch) so the framing cuts hard. `--hand` carries a job's recorded framing deviation (e.g. `0-14.8148:S=1.0,0.5,0.7526` for standing takes). Mode to CapCut: `x = 2(cx - 0.5)`, `y = -2(cy - 0.5)`, scale as is. Proven 2026-09-27 on Windows against the Premiere final of the same job: every switch on the same frame, the framing identical by eye. `--force` on `add-*` allows a deliberate duplicate (there's a guard against an interrupted run double-applying).
   - Batch related edits into **one** invocation where you can — each file-lane command is one quit+relaunch cycle (~15s).

   **Z-order is TRACK stacking, not segment `render_index`.** A segment's `render_index` only orders it *within* its track; what composites is the track's position (`track_render_index` / array order). So `--layer N` is the real z control, and a **text track can't be pushed below a video layer** — CapCut keeps text on top. Type that has to sit *behind* something gets baked to an alpha mov and placed as a video overlay.

5. **Background removal (text-behind-subject, validated 2026-07-27).** Cutout is a live-lane click; the matte itself is CapCut's own AI (needs Pro). The layered build, bottom to top:

   | Layer | What | How |
   |---|---|---|
   | main | the cut, untouched | already there |
   | 1 | black clip, opacity = "background darkness" | `add-overlay <black.mp4> --layer 1` + `transform --opacity 0.3` |
   | 2 | the title, baked alpha ProRes | bake it with `uv run workflows/behind-text.py "line one\|line two" --out projects/<job>/assets/behind-text.mov`, premultiply it with `bash lanes/capcut/premultiply.sh projects/<job>/assets/behind-text.mov` (writes `behind-text-premult.mov`), then `add-overlay projects/<job>/assets/behind-text-premult.mov --layer 2` |
   | 3 | duplicate of the same footage, background removed | `add-overlay <raw> --layer 3 --src <source in-point> --mute --force` |

   `--src` re-lays a slice of the raw above the main track; `--mute` is **mandatory** on that duplicate or its audio doubles the voice. Then enable the matte on the top clip:
   ```
   uv run lanes/capcut/capcut-bridge.py select 0
   uv run lanes/capcut/capcut-bridge.py click "VESettingPanelSubTabControl:Remove BG"
   uv run lanes/capcut/capcut-bridge.py clickxy 2976 286      # the Auto removal checkbox
   ```
   The checkbox is the left edge of `automationaiMattingGroup` — an offset click, like the export dialog (the row exposes no AX child). It writes `matting.flag: 3` plus a mask cache under `<draft>/matting/<hash>/`, keyed on the media, so a second clip off the same raw computes fast. Give it ~20s, then `seek` somewhere else and back to force the preview to re-render.

   **QA gotcha that costs an hour if you miss it:** the top layer is the *same footage* as the main track, so before the matte lands it covers the whole frame — the dim and the title below look like they aren't rendering at all. Don't debug the lower layers off that; confirm with `matting.flag == 3` in the draft JSON, or `delete` the top clip and look.

6. **Motion keyframes — zooms, pushes, moves (validated 2026-07-27).** Same expressive range as Premiere's Effect Controls, and easier to hit exactly, because the values are written rather than typed into a UI:
   ```
   uv run lanes/capcut/capcut-bridge.py keyframe <draft> --track overlay --index 2 --at 0   --scale 1.0
   uv run lanes/capcut/capcut-bridge.py keyframe <draft> --track overlay --index 2 --at 2.0 --scale 1.09
   uv run lanes/capcut/capcut-bridge.py clear-keyframes <draft> --track overlay --index 2
   ```
   Animatable: `--scale` (writes ScaleX+ScaleY together), `--x`, `--y` (half-canvas units, +y up, as `transform`), `--rotate`, `--opacity`. Two calls = a ramp; more calls = a multi-beat move. `--at` is **timeline** seconds and must land inside the segment (the bridge converts to the segment-relative `time_offset` CapCut stores). Re-keying the same time replaces that point.

   Under the hood it's `common_keyframes` on the segment: one entry per `property_type` (`KFTypeScaleX`, `KFTypePositionY`, `KFTypeRotation`, `KFTypeAlpha`, …), each holding a `keyframe_list` of `{time_offset µs, values: [v], curveType}`.

   ⚠️ **`time_offset` is in the SOURCE time domain, not segment-relative** — a point is `source_timerange.start + (t − target start)`. This is the single thing to get right, and it fails silently: segment-relative offsets fall outside a cut's source window and CapCut collapses the whole animation to **one static value** rather than erroring, so the clip looks zoomed but never moves. It also hides during testing — probe on a clip whose source in-point is 0 and the two domains are identical. Verify on a real cut, and verify by parking the playhead *between* two keyframes and reading the inspector: an interpolated value (100 → **112** → 122) is proof; matching the last keyframe means it flattened.

   **Only `curveType: "Line"` (linear) is verified** — `--curve` passes a value through, but the app's ease-curve names haven't been probed, so anything else is a guess. For an eased move, stack extra keyframes instead.

   **An unknown draft field is learned by making ONE instance by hand in CapCut and reading the JSON back** (how this keyframe schema was found), never guessed from its name.

   Keyframing the cutout layer *alone* pushes the subject while the background holds still — a real parallax move, and the reason to keep the cutout as its own layer.

7. **Interactive edits (live lane, no restart)** — for the surgical stuff:
   ```
   uv run lanes/capcut/capcut-bridge.py seek 42.0 --draft <draft>   # frame-exact, closed-loop
   uv run lanes/capcut/capcut-bridge.py split 30.0                  # razor at a time (or at the playhead)
   uv run lanes/capcut/capcut-bridge.py delete 3                    # select clip 3 + delete
   uv run lanes/capcut/capcut-bridge.py undo | redo | marker | zoomfit | play | playhead | clips
   ```
   `seek` clicks the mapped ruler point then nudges with arrow keys until the app's own `currentProgress` readout hits the exact frame — it **self-calibrates** from that readout, so it survives any zoom/scroll state.

8. **Export (validated end-to-end 2026-07-27):**
   ```
   uv run lanes/capcut/capcut-bridge.py export [--to <dir>] [--timeout 400] [--draft <name>]
   ```
   Drives CapCut's real export dialog and **verifies the file that lands** (dialog defaults: 1080p HEVC mp4 into
   `~/Downloads`, the draft name; Windows: `%LOCALAPPDATA%\CapCut\Videos`, a folder no config file records).
   **On macOS the dialog's encode settings are the creator's, by hand:** H.264 (not the default HEVC), the sequence's
   frame rate, and the format's resolution and bitrate (the presets' § Export, 2026-09-26: long-form 4K at 50 Mbps,
   a 1080 draft too; every vertical file 1080p at 14 Mbps or the Reels rule's lower number past 2:48; a 4K vertical
   draft's YouTube Shorts file a second export at 4K). **On Windows the bridge sets every one and delivers the
   presets' numbers itself** (your call, 2026-09-27): H.264, the TIMELINE's own frame rate (`--fps` overrides,
   knowingly: the dialog defaults to 30, and another rate relabels the frames), Bit rate = Custom at 50,000 Kbps and
   the Audio section ticked with Format = WAV, each read back by OCR (`capcut_win.set_export_*`); then
   `workflows/deliver.py` encodes the deliverable from CapCut's MASTER and WAV (`<Export to>\<name>\`) into `--to`
   (else beside the master) as `<name>.mp4`, refused BEFORE the render when that file exists, and every check passing
   deletes the master, the WAV and their folder (a miss keeps them, named). Why and the proof (High, 14.0 Mbps, 970
   frames, 2026-09-28): [`lab-notes.md`](../../../lanes/capcut/lab-notes.md) § Windows. After the file lands the
   bridge holds it to the draft (`--draft`, else the most recently saved draft): H.264, the format's frame for the
   draft's canvas, the frame rate, the frame count within one of the draft's duration, and ≤ 300 MB on a 1080×1920
   canvas; each check prints, and a miss exits non-zero with the file kept. **On a pipeline job pass `--to projects/<job>/outputs`, then rename the landed file to `<job>-final.mp4`** before `./finalize.sh <job> --apply`: finalize only reads `outputs/`, and it treats a bare `<job>.mp4` (the draft's default name) as the base cut and never promotes it. The bridge cannot type into the dialog's Export to, so the file lands at the dialog's own destination (`~/Downloads` by default) and `--to` MOVES it from there into `<dir>`, refusing to overwrite a file already at that name (on Windows `--to` is where deliver.py writes). **Only the first export of a CapCut launch completes** (a second freezes at 30%, on macOS and on Windows alike): `export` relaunches CapCut and reopens `--draft` before a second one from the same process, so always pass `--draft`. A frozen export is stopped with the dialog's Cancel, then OK on the confirm; no kill needed (on Windows the Exporting screen's Cancel beside "Back to home", then OK on "Stop exporting your video?", read by OCR: an earlier "OK" on screen belonged to a tooltip). Proven raw EDL → alpha overlay + programmatic text → rendered file with both graphics baked in (confirmed by frame-grab). Leaves cloud-sync off. Screen is controlled for ~10s (escape stale modal → Export → confirm), then it's pure file-polling while CapCut renders — the machine is free during the render.

   **A wedged export** (the encoder freezing mid-render, always a `source_timerange: null` on some segment) needs `kill -9` — the modal blocks a graceful quit — plus a `Timelines/` delete before relaunch.

## Step 3 — audio polish (baked into the source, then `replay --media`)

✅ **Validated on Windows 2026-09-27** (the export measured −17.8 LUFS, peak −5.5). The bridge has no
audio-effects surface — the draft JSON carries clip volume but nothing resembling the house Amplify + Hard
Limiter chain, and the live lane cannot type into the inspector's numeric fields (they take focus and ignore
synthesized keystrokes, which is why `transform` is file-lane on purpose). So the chain goes into the SOURCE
**before** `replay`, the Resolve and Final Cut lanes' route, and the draft is built against polished media:

```bash
bash workflows/normalize-sections.sh projects/<job>
uv run lanes/capcut/capcut-bridge.py replay <job> --media projects/<job>/audio-normalized
```

`normalize-sections.sh` takes each kept raw's `voice-gain.py` gain (kept speech → −17 LUFS) into the house
limiter at −6 dBFS, stream-copies the video so the EDL stays frame-exact, writes `audio-normalized/<clip>`
(never `raw/`), and fails the run on any copy that drifts. `--media` given a folder stands in for every raw by
name; a file stands in for the one raw of a single-raw EDL.

**Doing it after the draft exists means swapping media under a draft, which is the one thing this
lane must not do** — a media swap under an existing draft raced CapCut's async shutdown save and
zeroed a `draft_info.json` once. If a draft already exists and its audio needs work, delete the
draft plus its registry row and `replay` fresh against the fixed media.

## Step 4 — color grade (a gap on this lane)

⛔ **No recipe.** The bridge exposes no LUT or colour surface, and nothing has been probed. The
preset's contract still stands (footage graded, graphics untouched, before graphics are placed), so:

- Hand-apply a filter or LUT in CapCut before the graphics go on, **or**
- Ship the cut ungraded.

Either way **say which, out loud**, and record it in `projects/<job>/RUN.md`. A quietly ungraded cut
is the failure mode this line exists to prevent.

## Lab-Notes locks — read before trusting any step

The locks live in [`lanes/capcut/lab-notes.md`](../../../lanes/capcut/lab-notes.md); the war stories behind them are in the engineering archive. The five that bite most often, one line each:

- **`Timelines/` cache** — JSON edits after a draft's first open are silently ignored.
- **`source_timerange: null` WEDGES the encoder** mid-render; `edit_draft` backfills them.
- **The post-export share screen is MODAL** and publishes if you click through it.
- **Keystrokes only reach CapCut when it's frontmost** — the bridge calls `ensure_front` before any key; clicks are positional and don't need it.
- **No real API is buildable** — CDP reaches no timeline state, dylib injection means reversing a stripped 655 MB engine; the live AX lane is the answer.

## Relationship to the rest of the repo
- **Premiere** stays your default finishing surface (the `premiere-pro` skill, in a package that ships it). Route to CapCut only on an explicit CapCut ask or a CapCut-user client deliverable.
- The bridge consumes the same `transcript/cuts.json` EDL the Premiere replay does — one rough cut feeds either app.
- Ships in the client package as the CapCut-user client lane, on macOS and Windows (Linux has no CapCut desktop).
