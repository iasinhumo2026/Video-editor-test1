---
name: davinci-resolve
description: "The DaVinci Resolve finishing lane, counterpart to premiere-pro for Resolve users. Replays the rough-cut EDL (cuts.json) as separate trimmable clips on a real Resolve timeline via Blackmagic's own davinci-resolve MCP (ResolveMCP, Resolve Studio 21.1+), then keeps working through Resolve's official scripting API: AI subtitles, Fusion node graphs, custom DCTL color shaders, in-app Python, native renders. Triggers: send to resolve, open in resolve, finish in resolve, davinci, edit this in resolve, resolve timeline."
---

# To DaVinci Resolve: Rough Cut Handoff + API Editing

The Resolve counterpart to the `premiere-pro` skill. Same job: get the cut **onto a Resolve timeline as separate, trimmable clips** by replaying the EDL (`transcript/cuts.json`) against the raw footage, then keep working there. Unlike Premiere there is **no bridge panel**: the `davinci-resolve` MCP talks to Resolve's official first-party scripting API in-process, which reaches four apps in one (Edit, Fusion, Color, Fairlight). Resolve must be RUNNING; `launch_resolve` starts it (then `get_resolve_status`); several AI features are GUI-only, noted below. The engine is Blackmagic's own `ResolveMCP` (Studio 21.1+, § Wiring); § The call map lists how each operation is reached.

## 🔒 STEP INDEX — what this lane does at each pipeline step

**This skill carries HOW, never WHAT.** The look, the numbers and the definition of done for every
step live in the format's preset ([`presets/youtube/default/README.md`](../../../presets/youtube/default/README.md)
for long-form). Read the preset for the target, then the row below for the mechanics.
Cross-lane status: [`LANES.md`](../../../LANES.md).

| # | Step | On this lane | Where |
|---|------|--------------|-------|
| 1 | Intake | — universal, no Resolve involvement | CLAUDE.md § Pipeline |
| 2 | Rough cut → replay | ✅ scripted — ONE call rebuilds the EDL as trimmable clips | § Step 2 below |
| 3 | Audio polish | ✅ scripted — ffmpeg per source file + `ReplaceClip` (the API has no limiter and no FX insertion; 21.1 adds a clip level and fades, nothing more); ⛔ no swap under an iPhone take (an FPS-set clip): it is laid from `audio-normalized/` instead | § Step 3 below → [`lanes/resolve/resolve-audio-polish/`](../../../lanes/resolve/resolve-audio-polish/README.md) (the bake: `workflows/normalize-sections.sh`) |
| 4 | Color grade | ⚠️ colour group + the house look folded into ONE `.cube`, frame-measured against Lumetri on the lane test (2026-09-25); ✅ after its first real job — read the section before assuming | § Step 4 below → [`lanes/resolve/resolve-grading/`](../../../lanes/resolve/resolve-grading/README.md) |
| 5 | Graphics | ✅ scripted — `AppendToTimeline` + Fusion Transform for moves (the Talking Head Explainer's layout keys: ✅ Fusion hold keys per V1 item, proven on the lane test 2026-10-13, § Step 5) | § Step 5 below |
| 6 | SFX | ⚠️ Resolve 21.1+: `lanes/resolve/place-sfx.py` places `sfx-plan.json` (audio-only `AppendToTimeline` + `AudioVolume` + `SetFades`, every clip read back, `--verify`); the mechanics proven on the lane tests (2026-09-25 by hand, 2026-10-13 from `sfx-plan.json`), the script offline only (2026-10-14); `load-sfx-pack.py` puts the whole pack in the `sfx` bin | § Step 6 below · [`LANES.md`](../../../LANES.md) § step 6 |
| 7 | Review | ✋ the creator's. The run pauses here. | — |
| 8 | Export | ✅ scripted — the native render queue | § Step 8 below → [`lanes/resolve/resolve-export.md`](../../../lanes/resolve/resolve-export.md) |

⚠️ **Never carry a Premiere habit across.** The three that have actually shipped damage here:
hand-scaling a 1080 asset on a 4K timeline (Resolve already conformed it — Motion Scale 200 doubles
it to 400% and crops), premultiplying an alpha mov (Resolve wants STRAIGHT and auto-detects it), and
reaching for an adjustment layer (a color group is this lane's equivalent and needs no track shuffle).

## Wiring

- **The engine is Blackmagic's own `ResolveMCP`, shipped inside DaVinci Resolve Studio 21.1+, on every OS (2026-10-05).** `.mcp.json`'s `davinci-resolve` entry is the binary itself, no args, `"timeout": 600000`: macOS `/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolveMCP` (the same command Resolve's File > Setup AI Assistants writes into `~/.claude.json`), Windows `C:/Program Files/Blackmagic Design/DaVinci Resolve/ResolveMCP.exe` (proven 2026-09-27), Linux looked up under `/opt/resolve`. Plus `"enabledMcpjsonServers": ["davinci-resolve"]` in `.claude/settings.local.json` so the terminal CLI does not hold it pending (`setup.sh --lane resolve` writes it); restart Claude Code after. What it can and cannot do: [`lanes/resolve/lab-notes.md`](../../../lanes/resolve/lab-notes.md).
- `./setup-resolve.sh` (the client package root; `packaging/overlay/` in the author's repo) checks the edition and the binary, runs `ResolveMCP --test` (an offline MCP handshake: it answers with Resolve closed and reports the version it serves), then writes the entry. **A Resolve older than 21.1 is refused with "update Resolve first"; the free edition is refused outright**: the MCP ships only in Studio, and 21.1 took Python scripting out of the free edition, which also ended the community engine's in-app bridge. A refusal changes nothing. `--studio` skips the edition check for an activated Studio detected as free.
- **The community engine (samuelgursky/davinci-resolve-mcp, `vendor/davinci-resolve-mcp/`) is retired, never a fallback (2026-10-05).** A re-run of the installer replaces its entry and deletes the clone; `setup.sh` rewires a recorded Resolve lane still on it, and `check-setup.sh` fails until it does.
- Resolve side: nothing to configure in the normal case: **External scripting = Local is Resolve's shipped default** (verified on multiple installs, 2026-08-13; don't tell users to go set it). Only if the MCP can't connect after a Claude Code restart, verify Preferences → System → General → External scripting = Local as a troubleshooting step.

## The call map

Every recipe below is the RAW scripting API, reached through `run_script` (the community engine's wrappers were
retired 2026-10-05 and are never a route). Proven end to end on the official engine by the Resolve lane test of 2026-09-25
(a delivered short rebuilt, 42.9 dB mean PSNR against its Premiere master; record in
[`lanes/resolve/lab-notes.md`](../../../lanes/resolve/lab-notes.md)).

| Operation | Call |
|---|---|
| start Resolve | `launch_resolve` · `get_resolve_status` |
| arbitrary API Python | `run_script` (`resolve`/`project` bound; no `os`/`open`) · `run_script_unsafe` (full OS access) |
| replay the EDL | `mp.CreateEmptyTimeline` + `mp.AppendToTimeline([clipInfo…])` (§ Step 2) |
| read items back | `tl.GetItemListInTrack(kind, i)` → `GetStart`/`GetDuration`/`GetLeftOffset` |
| save | `resolve.GetProjectManager().SaveProject()` |
| DCTL / LUT files | `update_dctl` (compiles first) · `generate_lut` · then `SetLUT(1, 'MCP/<file>')` |
| render | `SetRenderSettings` + `AddRenderJob` + `StartRendering`, poll `GetRenderJobStatus` (§ Step 8) |
| API reference | `search_scripting_api` · `get_scripting_api` · `get_scripting_docs` · `get_whats_new` |

**Windows (2026-09-27): trust no launch call's word, prove it** (`launch_resolve` once answered "running" with no Resolve.exe up, three orphaned ResolveMCP.exe servers resident). Call `launch_resolve` (or start `C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe` directly, PowerShell `Start-Process`), then poll `get_resolve_status` until it reads `running: true` (about 20-25 s on the test PC) before the first call, and confirm Resolve.exe in `tasklist`. The 'Running DaVinci Resolve' line in `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\logs\davinci_resolve.log` lands about 2 s after the start, well before scripting answers: it proves the launch, not readiness.
**`running: true` is not write-ready either (2026-10-13).** Resolve can open a modal over the Project Manager at launch (here: Software Update's "Update Available: 21.1.1", Skip / Download; not on every launch: a later one logged "Failed to get auto update information" and showed none). While it is up every READ answers and every WRITE fails quietly: `ImportProject` returned None, `LoadProject` False, `SetSetting` and `SaveProject` None, nothing changed. So check every write's return (the § Project setup block does), and on a None look for the modal: on Windows a visible `Resolve.exe` top-level window other than "Project Manager" or the main window, with the Project Manager disabled. The creator answers it (Skip, Download or its close); a WM_CLOSE posted to it closed it like its window button here, then the same import returned True. Never pass a None on as done.

Official-engine rules, each learned on the proof job:
- **60 s hard cap per call** (`timeout` max 60): split a build into per-track scripts; start a render in one call and poll it in the next.
- `run_script` cannot read files, so **embed job data as a JSON literal** in the script (a 180-item plan ran as one 40 KB script), or read it in `run_script_unsafe`. Pass Resolve ABSOLUTE paths.
- Look media pool items up by `GetClipProperty('File Path')`, never by name.
- In-process readbacks (`GetLUT`, `GetProperty`, `GetLeftOffset`) are Resolve's own state, not a wrapper record; the verify-from-a-render rules below still stand.

## Project setup: MATCH THE SOURCE FPS, and never ask for a click

**Step zero of every Resolve job: `ffprobe` the raw and read its real frame rate.** The project must match the footage: 24 fps source gets a 24 fps project, 30 gets 30. Do not assume, and do not default to whatever the last job used.

**After import, put every clip on the raw's NOMINAL rate: `SetClipProperty('FPS', '29.97')` (the iPhone VFR trap, measured 2026-08-13; fixed 2026-09-27).** iPhone `.MOV` footage is variable frame rate: ffprobe's `r_frame_rate` reports `30000/1001` (29.97) while Resolve ingests the same clip at **30.00 native** (macOS and Windows, 21.1), and built at 30 a Resolve finish never shares a frame grid with the 29.97 plan, renders and Premiere lane (a 195-frame graphic ended a frame before its V1 cut). So: ffprobe the raw, clone the template at THAT rate (`1080p2997.drp` for a 30000/1001 take), import, and on every clip whose `GetClipProperty('FPS')` differs from it by more than 0.01 (Resolve reports a float: a 23.976 camera clip is already on its rate), `SetClipProperty('FPS', '<nominal>')` and read it back BEFORE the clip goes on a timeline (proven on macOS 21.1: frame count unchanged, 159 of 159 rendered frames on the raw frames Premiere's export shows). If a build ever refuses the property, the plan for a Resolve finish carries Resolve's rate instead (render the graphics at it). **Read `GetClipProperty('FPS')` BEFORE setting it and keep it: that NATIVE rate stays the picture's time base (the Windows re-test, 2026-09-27).** After the change Resolve lays the clip's SOUND by the nominal rate but still decodes source frame f as the picture at f / native, so a V1 laid from `round(start x 29.97)` showed the picture 1 frame early 34 s into a 150 s take and 3-4 frames early at 127 s, behind its own sound. The replay therefore lays V1 from `round(start x native)` and A1 from `round(start x nominal)`, each V1 item at native/nominal speed (§ Step 2's recipe and measurements). A clip already set with no native rate recorded: re-import it. **Diagnostic signature:** a uniform ÷1.001 (or ×1.001) pattern across every item's duration/left-offset readback means the fps model is wrong: rebuild, never nudge individual frames. (`splice.sh` conforms the flat render to the same nominal grid, `fps=` before each trim.)

**Then clone a template `.drp` at that fps. Do NOT use `create_project` + `set_setting`.** A new project defaults to 3840x2160 / **24 fps**, and `timelinePlaybackFrameRate` (a *separate* setting from `timelineFrameRate`) cannot be written by the API at all (re-tested on 21.1, 2026-09-25: `SetSetting` still returns False and it reads back 24). A 30 fps timeline left playing back at 24 produces **chopped, glitchy audio**. Importing a `.drp` restores fps + resolution wholesale, bypassing `SetSetting` entirely (verified 2026-08-04).

The block below runs as-is in `run_script`; give `ImportProject` an ABSOLUTE path. **Never `SaveProject()` while the current project is "Untitled Project"**: Resolve opens its Save Current Project name dialog and the script hangs to its cap (2026-09-25). Check `GetName()` first and skip the save for an untitled one. Resolution is writable after the import (`timelineResolutionWidth` / `Height` → a 2160x3840 vertical read back exact).

```python
pm = resolve.GetProjectManager()
cur = pm.GetCurrentProject()
if cur and cur.GetName() != 'Untitled Project':
    pm.SaveProject()                                 # outgoing project, or a GUI modal blocks everything
assert '<Project Name>' not in pm.GetProjectListInCurrentFolder()  # never import over (or next to) an existing name
assert pm.ImportProject('<abs>/lanes/resolve/resolve-templates/1080p30.drp', '<Project Name>'), 'refused: a Resolve modal is up?'
assert pm.LoadProject('<Project Name>') and pm.GetCurrentProject().GetName() == '<Project Name>'
p = pm.GetCurrentProject(); mp = p.GetMediaPool(); root = mp.GetRootFolder()
mp.SetCurrentFolder(root)
tls = [p.GetTimelineByIndex(i) for i in range(1, p.GetTimelineCount()+1)]
if tls: mp.DeleteTimelines(tls)                      # strip inherited content
if root.GetClipList(): mp.DeleteClips(root.GetClipList())
```

**Always read `timelinePlaybackFrameRate` AND `timelineFrameRate` back** before building the timeline.

**One template per frame rate: a template cannot be re-pitched** (once a project carries a playback fps, `timelineFrameRate` goes read-only too). But minting a template at ANY rate is **fully scripted, zero clicks** (2026-08-04) — paths are taken as given, so pass them repo-relative:

```bash
uv run lanes/resolve/resolve-templates/mint-template.py \
  lanes/resolve/resolve-templates/1080p30.drp <fps> \
  lanes/resolve/resolve-templates/<out>.drp
```

Available now: 1080p30, 1080p2997 (both in [`lanes/resolve/resolve-templates/`](../../../lanes/resolve/resolve-templates/) — how the settings blob is patched, the verified rate-enum table and the anonymity check live in its README). Always import + read back both fps keys before trusting a fresh mint (a 23.976 mint read back 23.976 / 23.976 on 21.1, 2026-09-25). 24 fps needs no template (a stock `create_project` is already 24/24, just set the resolution).

## Vertical (9:16) framing

A clip dropped on a 1080×1920 timeline arrives LETTERBOXED (project Input Scaling defaults to fit, and that setting is UI-only from the API). The fix is one property write, resolution-agnostic, no math:

```
item.SetProperty('Scaling', 3)   # 3 = scale full frame with crop = FILL at Zoom 1.0
```

Values: 0 = fit, 1 = center-crop-at-native, 2 = fit, 3 = FILL. Zoom math (`tl_h / (tl_w * src_h / src_w)`) is quality-identical (Resolve concatenates sizing transforms and resamples once), so prefer Scaling=3 for simplicity. 16:9 → 9:16 is a ~1.78x upscale from a 1080p source, inherent to the crop; shoot 4K for vertical (downscale instead). `SetClipProperty('Super Scale', N)` takes **bare ints only** (1=off, 2=2x, 3=3x); every string form returns False.

**Mixed-resolution assets: let Resolve conform, NEVER hand-scale (2026-08-05).** The project setting `timelineInputResMismatchBehavior` defaults to `scaleToFit`, so a 1080p asset (title card, alpha overlay, older footage) already fills a 4K frame on drop. The Premiere habit (Motion Scale 200) doubles that to 400% and crops the middle out, plausibly enough to ship: a title card lost its first and last letters. Leave `ZoomX`/`ZoomY` at 1.0, check the setting before scaling anything, and verify with a real render (clip-level readback reports whatever zoom it was told and hides the crop). Upside of the same conform: mixed fps lands frame-for-frame (a 29.97 clip on a 30.000 timeline keeps its frame count), so frame-indexed graphics and same-rate overlays stay in sync with no re-render.

## Step 2 — EDL replay: one call

Run the splice `RENDER=0` first (same rule as the Premiere path: never render the flat cut for an app finish). Then the whole rebuild is a single call:

1. **Create the project from a matching template (see § Project setup above). Never `create_project` + `set_setting`.** Match the template to the raw's `r_frame_rate`, and after import put any clip Resolve ingested at another rate (every iPhone take: 30.0 for 29.97) back on it with `SetClipProperty('FPS', …)` (trap in § Project setup above).
2. **`run_script`, the EDL embedded as a JSON literal:** clip infos in **SOURCE frames** (the two rates in the block below, § Project setup's iPhone VFR trap), `endFrame` **EXCLUSIVE** (dur = end − start), `recordFrame` **ABSOLUTE** (`tl.GetStartFrame()` + the timeline-relative frame) and `mediaType` picks the half: `1` video-only, `2` audio-only, omitted = linked A/V. A J-cut (audio edit point ≠ video edit point) therefore replays as separate video-only and audio-only items. Proven 2026-09-25: 22 V1 + 22 A1 (a J-cut included) + 136 more items in one call per track, 180/180 exact on start, duration and source in.
   ```python
   mp = project.GetMediaPool()
   def walk(f): return (f.GetClipList() or []) + [c for s in (f.GetSubFolderList() or []) for c in walk(s)]
   by = {c.GetClipProperty('File Path'): c for c in walk(mp.GetRootFolder())}   # root too: ImportMedia lands in the current folder, root after § Project setup
   tl = mp.CreateEmptyTimeline('<name>'); project.SetCurrentTimeline(tl)
   while tl.GetTrackCount('audio') < 2: tl.AddTrack('audio', 'stereo')
   T0 = tl.GetStartFrame()
   # SEGS: src0/src1 = round(seconds x NOMINAL), the sound and every duration; v0 = round(start x NATIVE), NATIVE = the
   # FPS Resolve reported for the clip BEFORE SetClipProperty('FPS') (§ Project setup): the picture stays on that time base.
   # Each SEGS row also carries 'native' and 'nominal', that clip's two rates as floats (30.0 and 30000/1001 on an iPhone take)
   mp.AppendToTimeline([{'mediaPoolItem': by[s['path']], 'startFrame': s['v0'], 'endFrame': s['v0'] + s['src1'] - s['src0'],
                         'recordFrame': T0 + s['rec'], 'trackIndex': 1, 'mediaType': 1} for s in SEGS])   # V1
   mp.AppendToTimeline([{'mediaPoolItem': by[s['path']], 'startFrame': s['src0'], 'endFrame': s['src1'],
                         'recordFrame': T0 + s['rec'], 'trackIndex': 1, 'mediaType': 2} for s in SEGS])   # A1
   # A clip whose NATIVE rate differs from its NOMINAL one plays one native frame per timeline frame, 0.1% slow against
   # its sound: each V1 item runs at native/nominal speed (100.1%) so a long segment never slides. Without ripple the
   # item keeps its duration and reads further into the source; nearest-frame retime, never a blend.
   for vi, s in zip(sorted(tl.GetItemListInTrack('video', 1), key=lambda i: i.GetStart()), SEGS):
       if abs(s['native'] - s['nominal']) > 0.01:   # never ==: a 23.976 camera clip reads 23.976 against 24000/1001
           vi.SetProperty('RetimeProcess', resolve.RETIME_NEAREST)
           assert vi.SetSpeed({'Percentage': 100.0 * s['native'] / s['nominal'], 'RippleTimeline': False})
   ```
   On a clip Resolve ingested at its nominal rate, `v0 == src0` and no speed is set: the two calls lay the same frames.
   **The speed step is what holds a LONG segment (macOS 21.1, 2026-09-27).** Without it the picture of one continuous
   segment slides a frame behind its sound about every 33 s (0 → −2 frames across a 60 s segment, on a 29.977 and a
   30.004 average take alike), because frame f is the picture at f / native while the timeline steps at the nominal rate.
   With it: every V1 duration exact (42 of 42 segments, and the 60 s one), no gap frame, the picture within one frame of
   the splice on every segment (28 of 42 exact; the rest the beat between the 30 and 29.97 grids), the sound exact.
   Leaving the clip at its native rate instead is NOT an option: Resolve rounds each segment down, 38 of 42 came out a
   frame short (a black frame at nearly every cut). `SetSpeed` runs in the same `run_script`.
3. Verify with a readback (`tl.GetItemListInTrack` → `GetStart() - T0`, `GetDuration()`, `GetLeftOffset()`): starts sit on the timeline's start-frame offset (108000 = 01:00:00:00 at 30 fps, 86400 at 24 and 23.976).
   Read the source in-point as `GetSourceStartTime()` x the rate, never `GetSourceStartFrame()`: the int TRUNCATES a time
   that sits a hair under its frame (15755 read back 15754 on both halves of one item in 16, its time exact; Windows
   21.1, 2026-10-13). On an R7 clip a V1 item's source time reads on the clip's NEW rate (v0 / 29.97), its picture is
   still frame v0 at v0 / native: compare frames, not seconds.
   **When clip fps ≠ timeline fps, `GetLeftOffset()` reads back in CONFORMED (timeline) frames while `start_frame` is consumed as NATIVE source frames**: a 29.97 clip on a 30 fps timeline reads back `native × 1.001`, which looks like a growing drift (up to 4 frames over 2.5 min) and is NOT one. Durations and `record_frame` read back exact, so verify those and don't "fix" the offsets. Resolve conforms by TIME, not 1:1 frames (measured: a 4612-native-frame span occupies 4616 timeline frames at 30 fps); that one probe settles the domain question in a single call.
4. Save **immediately** (`pm.SaveProject()` in the same script; never on an "Untitled Project", § Project setup). GUI mode + unsaved project = a modal no script can dismiss.

### Do we still need WhisperX?

Yes, for the rough cut. Measured on the same clip: Resolve gives phrase-level cues (median ~1.9s / 6 words, timing only at cue edges, ~6x fewer anchors than WhisperX's per-word timestamps), and cue starts sit inside the very error band `refine-cuts.py` exists to fix. Keep the locked WhisperX rough-cut for cutting; Resolve's transcription is useful for long-form CC and machines without the venv.

## Step 3 — audio polish: ffmpeg on the source files + `ReplaceClip`, NOT the API

**The scripting API cannot build the house chain: no limiter, no EQ, no track fader, no bus access, no FX insertion, on any version to date (don't re-litigate that half).** What 21.1 DID add is a clip-level `AudioVolume` (−100..+30 dB), `AudioPan` and `SetFades`/`GetFades` (frames), used for SFX and music levels (§ Step 6), never for the voice chain: a gain with no limiter behind it clips. So this lane polishes the SOURCE FILES with ffmpeg and swaps the media under the locked timeline, rather than applying effects. The four independent corroborations and the ruled-out routes: the engineering archive.

**Run it immediately after the replay verifies — pipeline step 3 (2026-08-28), never per-section during the cut.** The pass is [`lanes/resolve/resolve-audio-polish/`](../../../lanes/resolve/resolve-audio-polish/README.md) (`workflows/normalize-sections.sh` then `replace-clips.py`), validated 2026-08-06 on 9 sections / 210 clips with zero clips moved. **Read that README before running one** — the chain, the drift gate and the `ReplaceClip` traps all live there. It swaps media, not clips, so every later hand edit rides on it; only a timeline REBUILD from re-imported raw needs the swap re-run.

`replace-clips.py` runs through `run_script_unsafe` (it needs the filesystem) with `import io; JOB='<abs job>'; exec(io.open('<abs>/lanes/resolve/resolve-audio-polish/replace-clips.py', encoding='utf-8').read())` (proven 2026-09-25: every track UNCHANGED). On a timeline built fresh, importing the normalized copies AS the footage media before the replay is equivalent and skips the swap (the proof job did that).

⛔ **Never swap under a clip whose FPS property was set (§ Project setup: every iPhone take), lay the timeline from
`audio-normalized/` instead (Windows 21.1, 2026-10-13, reproduced twice).** `ReplaceClip` re-ingests the new file at ITS
native rate, so the clip's `FPS` comes back 30.0 for the 29.97 the replay was built on. A1 keeps its source time (the sound
stays exact), but every V1 item now reads source frames 0.1 % of its source time too far in, so the picture runs AHEAD of
its sound: 2-4 frames at 83-137 s of source, 10-15 at 412-534 s, 17-18 at 554-653 s (an 11-minute take, measured on a
render against the splice), while `replace-clips.py`, then comparing name, start and duration only, called it clean (it
now puts the FPS back and says MOVED). Putting the FPS back restores A1
exactly but leaves every V1 source in-point 0.4-0.9 frame under the replay's, so the picture sits a frame behind (54 of 93
samples, 2 frames on two segments). So on such a clip, step 3 runs BEFORE the replay: `workflows/normalize-sections.sh`,
import `audio-normalized/<raw>` as the footage (it keeps the raw's rotation and frames: the video is stream-copied; import
it into its own bin, Resolve makes a new clip even when the path is already in the pool), read its native FPS and set the
nominal one (§ Project setup), then replay from it. Proven: its readback matched the raw replay on all 32 items, its render
the raw replay's render frame for frame (framemd5, 2257 frames), its sound the splice to 0.042 ms and its loudness the
splice's (−18.1 LUFS). The pass then rides on the media as before; a rebuild re-lays from the same copy. The swap stays
for a clip Resolve ingested at its nominal rate (the 2026-09-25 proofs).

Normalized files go in `audio/` or `audio-normalized/`, never `raw/`: `transcribe.sh` globs `raw/*.mov` and would transcribe them as extra clips on a `--force` re-run.

**To READ an audio pass someone made by hand, bounce and measure; the mix state is unreadable.** 21.1's `GetProperty('AudioVolume')` reads back a clip's level, but nothing reads a Fairlight FX chain, a fader or a bus, and a `.drp` export hides mix state in opaque zstd blobs (per-item `EffectFiltersBA` are byte-identical defaults regardless of the mix). Instead render (the § Step 8 recipe at a small size) a throwaway 480x270 mp4 (a 55s timeline rendered in 2.2s) and `volumedetect` each segment against the same source range in the raw: a uniform peak ceiling across every segment plus a gain delta that shrinks as the source gets louder = gain-into-limiter, and the numbers tell you the settings. Gotcha: `ExportVideo: false` produces a job with an empty VideoCodec and `StartRendering` then just returns False: render tiny video, not none. Clean up with `project.DeleteAllRenderJobs()` + re-set format/codec (`GetRenderSettings` does not exist in the API, 21.1 stub included, so nothing can snapshot "before"; track what you changed yourself).

## Step 4 — color grade (mechanism validated 2026-08-06: 9 clips, one shader; the house look folded 2026-09-25)

**The mechanics are [`lanes/resolve/resolve-grading/`](../../../lanes/resolve/resolve-grading/README.md) — how a colour group is built and assigned, the DCTL dialect that compiles, the `install` vs `set_lut` staging trap, the teardown sweep, plus a reference shader and a numpy previewer. Read it before any grading work on this lane.** What follows is only what the preset asks for and which half of it is proven here.

### What the preset asks for, and what is proven here

**The universal contract is the SEPARATION: the footage carries the look, the graphics carry none of
it, established before a single graphic is placed.** On this lane that half is free and validated —
a colour group covers only its members. **The other half, the house look, is reached by FOLDING it
into one node** (validated once, 2026-09-25).

| Half of the step | Status here |
|---|---|
| Footage graded, graphics untouched | ✅ a color group covers only its members. Join the footage clips; leave the graphics track out. No track shuffle, no adjustment layer, no reordering. |
| A shared look across every footage clip | ✅ one node on the group's **post-clip** graph, `SetLUT(1, …)`. Proven with a DCTL (2026-08-06) and with a generated `.cube` (2026-09-25). |
| Autumn + Look Intensity 80 + Creative Saturation 120 | ⚠️ **folded into ONE `.cube`** (proven on the lane test; ✅ after its first real job): `out = sat(lerp(x, Autumn(x), 0.80), 1.20)`, saturation about Rec709 luma, clamped. Lumetri's dials have no API equivalent (`Graph` exposes LUT, label, enable and cache mode, no colour parameters), so the blend and the lift are baked into the cube. Measured against the Premiere master of the same cut: footage mean RGB within 1–2 / 255 on four frames. |

**How to build and apply the folded cube, on either engine: [`lanes/resolve/resolve-grading/`](../../../lanes/resolve/resolve-grading/README.md#the-house-look-folded-into-one-cube).** `uv run workflows/fold-look.py assets/luts/rec709/Autumn-Rec709.cube --install autumn80-sat120` writes it straight
into Resolve's master `LUT/MCP/` for the OS (Windows: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\MCP\`, proven 2026-09-27 and 2026-10-13) and prints the path `SetLUT` takes. When the cube is already there, fold to a scratch file and compare the rows before writing over it (2026-10-13: 35,937 of 35,937 identical); then, in-process (`run_script`):

```python
project.RefreshLUTList()
grp = project.AddColorGroup('Footage Look')
for it in tl.GetItemListInTrack('video', 1): it.AssignToColorGroup(grp)
grp.GetPostClipNodeGraph().SetLUT(1, 'MCP/autumn80-sat120.cube')    # GetLUT(1) reads it back
```

The fallback if a fold ever misbehaves: **cube on the node, dials by hand** in the Color page, once,
then saved as a group grade.

Measured again on Windows 21.1 (2026-10-13, a 75 s Talking Head Explainer): `GetLUT(1)` read `MCP\autumn80-sat120.cube`,
16 of 16 V1 items in the group, the render's footage within 0.7-1.5 / 255 (mean per channel) of the cube applied to the
ungraded render on 7 frames, and within 0.6-1.9 / 255 of Premiere's Lumetri 80 / 120 (7 W frames, a background region);
the program render frame-identical after a save, `CloseProject` and `LoadProject`.

**Whichever route: verify with a real render, and say in the run report that the grade was
established by a different mechanism than the preset's Premiere recipe** ("Autumn folded at 0.80 / 1.20,
measured"). Never report "Autumn at 80/120 applied" on this lane unless you measured a frame — the
numbers are Lumetri's, and a `.cube` on a Resolve node is not the same signal chain.

⚠️ **A readback proves nothing on its own: verify from a real render.** `GetLUT(1)` is Resolve's own answer, but a node that compile-fails still passes
the picture through ungraded.

## Step 5 — graphics on the timeline (validated 2026-08-05, 9 overlays on V2)

On a short-form preset the caption layer (`hf-graphics/captions/renders/captions-alpha.mov`, the
plan's `captions` cell) is one more straight-alpha overlay: append it on the highest video track,
spanning the whole cut, above every card ([`LANES.md`](../../../LANES.md) § step 5).

- **HyperFrames alpha ProRes 4444 drops in with ZERO alpha config: Resolve auto-detects `Alpha mode: Straight`**, exactly what hyperframes writes. **NEVER premultiply a Resolve-bound render.** Premultiply is the CapCut lane's fix; here it would blow out every soft pixel (motion blur, glows, fades).
- Placement is `AppendToTimeline` with `clipInfo` `{mediaPoolItem, startFrame: 0, endFrame: <frame count>, recordFrame: 108000 + start, trackIndex: 2, mediaType: 1}`. `endFrame` is **EXCLUSIVE**, `recordFrame` is **ABSOLUTE**. Script it idempotent and readback-verified. It is the raw API, so it runs as-is in the official engine's `run_script` (2026-09-25: 23 graphics + the privacy patch + the caption layer, frame counts = slots, on a 2160x3840 timeline with 1080x1920 renders conformed by `scaleToFit`).
- **The Talking Head Explainer's layout keys** ([`LANES.md`](../../../LANES.md) § Step 5′; the target is HOLD keys, V1 never razored, because a razor costs the creator his trim points). The transform numbers: `SetProperty('Pan'|'Tilt'|'ZoomX'|'ZoomY', v)` reads back exact, and from Premiere-normalised Motion values (`face-frame.py --modes`, or a .prproj's Position (x, y) and Scale) `Pan = (x − 0.5) · W`, `Tilt = −(y − 0.5) · H`, `Zoom = Scale / 100`, W × H the timeline size. `TimelineItem` has no keyframe API, so the target-conformant route is a Fusion Transform with hold keys on each V1 clip: **proven on the official engine (Windows 21.1, 2026-10-13)**, recipe below. The older route (2026-09-25): split V1 at every layout change and give each piece its own static transform (22 hold-keyed Premiere clips → 29 pieces, the framing identical to the Premiere master by frame); it razors V1, so it is a DEVIATION from the target: announce it and record it in RUN.md.
- **The layout keys as Fusion hold keys (2026-10-13).** The modes come from `presets/instagram/talking-head-explainer/layout.py` exactly as `layout-keys.py` reads them (`modes(face)`, `footage_spans(plan, md, fps)`, `footage_at((f + 0.5) / fps, fsp)` per timeline frame f; a row's own `frame` is its own key). One comp per V1 item, raw Fusion API in `run_script`:
  ```python
  comp = item.AddFusionComp()          # comp time 0 = the item's first frame (render range 0 .. duration-1)
  mi, mo = comp.FindTool('MediaIn1'), comp.FindTool('MediaOut1')
  tr = comp.AddTool('Transform', -32768, -32768)
  tr.ConnectInput('Input', mi); mo.ConnectInput('Input', tr)
  # Size = the mode's scale (about the image centre); Center = where the image centre lands, origin BOTTOM-left:
  # (x, 1 - y) for a Premiere Position (x, y). A static item: tr.SetInput('Size', s); tr.SetInput('Center', {1: x, 2: 1 - y, 3: 0.0})
  tr.AddModifier('Size', 'BezierSpline'); tr.AddModifier('Center', 'XYPath')   # each KEYS the default (1.0, centre) on frame 0
  for k, s, x, y in keys:              # the opening mode ON 0 (or a non-W opening ramps from the default), then per switch
      tr.SetInput('Size', s, k); tr.SetInput('Center', {1: x, 2: 1 - y, 3: 0.0}, k)   # the outgoing at k-1, the incoming at k
  ```
  The keys are `lanes/premiere/layout-keys.py`'s own `plan_keys` (media time − in-point → item frame), so both lanes key
  the same frames. Fusion's default handles make each segment a straight line, so equal-valued neighbours hold flat (no
  overshoot) and every rendered frame sits on a key's value.
  ⚠️ **A retimed item's comp runs on the SOURCE clock (2026-10-13).** At 100.1 % (§ Step 2) item frame k reads comp frame k
  only up to frame 997; from 998 it reads one ahead (a ramp render, two source phases, measured to frame 1059; step keys
  at 1000 and 1400 landed on frames 999 and 1399). So an item under 998 frames (33 s) keys as above; on a longer one, key
  the pair at the comp frames those item frames read and prove every switch on a V1-only render.
  ⛔ **Never `comp.Lock()` / `comp.Unlock()` around it:** a clip comp edited inside a lock read back every tool, key and
  connection right and RENDERED UNTOUCHED (seen on one run, 2026-10-13; not re-run since). Proven on a 75 s short
  (16 V1 items: 17 key pairs on 9 items, 7 static, the opening mode keyed on 0): a V1-only render classified frame by frame
  against the modes warped from the untransformed render, 2257 of 2257 on the plan's framing (W, S, T and a row's own T),
  no in-between frame; the program frame-identical after a save and reopen; `face-frame.py --verify` PASS (−17 px; the
  Premiere master of the same plan −16), `flash-scan.py --expect` PASS (32 of 32). V1 is never razored. A static-only job
  can use `SetProperty('Pan'|'Tilt'|'ZoomX'|'ZoomY')` above instead.
- **`TimelineItem` has NO keyframe API** (only static `SetProperty` plus the Fusion methods), so any animated footage move is a Fusion comp on the clip, as above (a linear `Size` ramp across a retimed item rendered on its comp frames: 1.29 at 100 of 340, 1.50 at 170).
- Resolve's embedded Python opens files as **ASCII**: `io.open(..., encoding='utf-8')` everywhere, and keep em dashes out of timeline names (either one kills the script).
- Verify compositing from a real render.

## Step 6 — SFX and the music bed (Resolve 21.1+)

WHAT to place: the preset's `sfx.md` and `workflows/sfx-plan.py`'s reviewed cut sheet; the music bed:
`background-music`. HOW: **`lanes/resolve/place-sfx.py`** (2026-10-14). It runs INSIDE Resolve through
`run_script_unsafe` (timeout 60), like `replace-clips.py`; from a shell it checks the plan offline and prints that call
with this machine's absolute paths, so the call is never typed by hand:

```bash
uv run lanes/resolve/place-sfx.py projects/<job> --apply        # then paste the printed call into run_script_unsafe
uv run lanes/resolve/place-sfx.py projects/<job> --verify       # every missing, extra or drifting cue named; ALL PLACED or DRIFT
uv run lanes/resolve/place-sfx.py projects/<job> --remove-extra [--dry]       # exactly the clips --verify calls extra
uv run lanes/resolve/place-sfx.py projects/<job> --remove s004,s017 [--dry]   # those rows' clips; bare --remove = the full clear
#   --timeline NAME (default: the timeline named after the job, a section's parent, or the project's only one); --plan FILE
```

Read the script's docstring for the whole contract (it is the Premiere placer's: tracks by role, the repeat cut where
the next cue starts, levels and fades read back, a span another clip holds never laid over, a moved graphic named).
An `--apply` that reaches 45 s stops and says PARTIAL: run the same call again, it lays only what is missing. A
`DRIFT` after a hand pass is the creator's edit (`--diff` and `--adopt` are Premiere-only): report it, never re-apply
over it. The mechanics it scripts, each measured on 21.1:

- Each sound is laid audio-only: `AppendToTimeline` with `mediaType: 2` and `trackIndex` = the plan's `track + 1` (A2
  for 1; missing stereo tracks appended first with `tl.AddTrack('audio', 'stereo')`). An imported audio file ingests at
  the PROJECT frame rate, so `startFrame` / `endFrame` are the source in/out in timeline frames.
  A fractional `recordFrame` is kept (`GetStart(True)` reads it back: 18 of 18 cues within 0.1 ms of their time), while
  the source in and out land on whole source frames (within half a frame: 13 / 15 ms worst on 18 cues) (2026-10-13):
  the placer passes whole source frames and carries the in-point's rounding in the record frame, so the sound plays
  at its planned second.
  Read a sound's in-point back as `GetSourceStartTime()` minus the file's own start: a BWF wav's `time_reference`
  (ffprobe `format_tags=time_reference` / sample rate: 3600 s on `Pop 1.wav`; the pack's `bext` chunk sits AFTER the
  samples) is in the time, while `GetSourceStartFrame()` leaves it out AND truncates (a 0.467 s in-point read 13
  frames for 14; an aiff's 3.837 s read a frame low).
- Level: the item's `AudioVolume` (−100..+30 dB); only non-zero levels are written, every one read back. A fade or a
  one-sided crossfade: `item.SetFades({'FadeOut': <frames>})`, read back with `GetFades()`. 21.1's canonical forms
  are `GetProperties()` / `SetProperties({...})` and `GetClipProperty()` (a dict); the single-key calls the lane
  tests used are deprecated but answer, and the placer falls back to them.
  Music: the bed's dB as `AudioVolume`, its tail as `FadeOut` (scripted per job from `music-plan.json`: no music placer ships).
- Reading levels out of a Premiere project (rebuilding a Premiere job here): the .prproj stores the clip
  Volume Level as linear gain with 0 dB at 0.177828, so `dB = 20·log10(v) + 15`; a clip with no volume
  component is 0 dB.
- Proven by hand 2026-09-25: 103 hand-placed sounds on three tracks plus the bed (−21 dB, 48-frame fade), every
  level read back; the render landed −17.5 LUFS against the Premiere master's −17.7. Scripted from `sfx-plan.json`
  on Windows 2026-10-13 (track 1 → A2, track 2 → A3): 18 of 18 placed, 0 extra, 0 drifting, every level read back;
  the program −18.0 LUFS, peak −1.6 dBFS (the Premiere master of the same plan: −18.3 LUFS). `place-sfx.py` is that
  script made general, proven offline on a fake Resolve (`workflows/test_resolve_place_sfx.py`); ✅ after its first
  live job.
- ⚠️ Nothing limits the master here: Resolve's sum ran about 0.3 dB hotter than Premiere's on the loudest
  hits of the same levels (sample peak +0.03 vs −0.27 dBFS). Check the render's peak and report a hit;
  the levels are the creator's call.

**The whole pack in the bin, for hand placing:** `uv run lanes/resolve/load-sfx-pack.py [--dry]` prints the
`run_script_unsafe` call that imports every file of `assets/sfx/` (`workflows/sfx-plan.py` `pack_files()`) into the
open project's `sfx` bin, sub-folders as sub-bins, a file already in the pool skipped, every file read back, saved.
No timeline is touched. Offline-proven (`workflows/test_sfx_pack.py`), ⚠️ until a live run.

## Step 8 — export: the native render queue

**Read [`lanes/resolve/resolve-export.md`](../../../lanes/resolve/resolve-export.md) before scripting a
DELIVERY render** — it owns the settings truth table. Target (the presets' § Export, 2026-09-26): H.264 MP4 at
the FILE's frame (3840×2160 for any long-form, a 1080 timeline too; 1080×1920 for any vertical file; a 4K vertical
timeline's Shorts file a second job at 2160×3840), `VideoQuality` = the preset's bitrate in kb/s WITH
`MultiPassEncode: True` (without it the number is only a cap), AAC 48 kHz, straight to `projects/<job>/outputs/`.

**Set the render keys one call each and read every return** (the export doc's `set_each`): Resolve 21.1 on Windows
refuses `VideoQuality` for every value, and a dict holding it drops every other key too (2026-09-27; unchanged on
21.1.0.17, 2026-10-13). A refused bitrate means a ProRes 422 HQ master and `uv run workflows/deliver.py` for the
deliverable (proven 2026-10-13: High 4.2, 14.00 Mbps, bt709, moov first). The master's 01:00:00:00 timecode rides into
the mp4 as a `tmcd` data track (ffmpeg's mp4 muxer writes one for a timecoded input).

Three facts to have before you open it: `SelectAllFrames` must be a real bool; MarkIn/MarkOut are
ABSOLUTE timeline frames (a 01:00:00:00 start means frame 86400 at 24 fps, not 0); and
`GetRenderSettings` does not exist in the API, so **verify the finished file with ffprobe**,
never a settings readback.

`run_script`, two calls because of the 60 s cap, the proof job's short-form delivery:

```python
project.SetCurrentTimeline(tl)                       # the timeline found BY NAME
project.SetCurrentRenderFormatAndCodec('mp4', 'H264')
project.SetRenderSettings({'TargetDir': '<abs>/projects/<job>/outputs', 'CustomName': '<job>-render',
    'SelectAllFrames': True, 'FormatWidth': 1080, 'FormatHeight': 1920, 'FrameRate': 23.976,
    'VideoQuality': 14000, 'MultiPassEncode': True, 'EncodingProfile': 'High', 'AudioCodec': 'aac', 'AudioSampleRate': 48000,
    'ExportVideo': True, 'ExportAudio': True, 'NetworkOptimization': True})
project.DeleteAllRenderJobs(); jid = project.AddRenderJob(); project.StartRendering([jid])
# next call: project.GetRenderJobStatus(jid) until JobStatus == 'Complete'
```

That rendered 2872 frames of 1080x1920 in 19 s at 13.96 Mbps with AAC at 320 kb/s (without multi-pass; on easier
footage the same cap landed at 10.9, so multi-pass is on since 2026-09-26). On 21.1 `VideoQuality: <int>` is a
bitrate in kb/s (the export doc has the version split).

Then `./finalize.sh <job> --apply` for promotion + the `~/Downloads` copy (lane-agnostic).

## What the API can do (all readback-verified)

Everything here is the raw API through `run_script` under the name given.

- **Text-based editing, read half:** `tl.CreateSubtitlesFromAudio()` (GUI only, about 57 s for 9 min).
- **Fusion node graphs:** `item.AddFusionComp()` and the Fusion comp API (`fusion_api.pyi` via `get_scripting_api`): add tools, connect, set inputs, key them (§ Step 5).
- **Custom GPU color shaders + multi-clip grading:** author a DCTL (`update_dctl`, compiled before it is written), put it on a **color group's post-clip node**, and every member clip inherits it. Playbook: [`lanes/resolve/resolve-grading/`](../../../lanes/resolve/resolve-grading/README.md); short version § Step 4 above.
- **Arbitrary Python inside Resolve:** `run_script` (sandboxed) and `run_script_unsafe` (filesystem, subprocess) with `resolve` / `project`. Hard 60 s timeout on both; split a long op across calls.
- **A backup before anything destructive:** `tl.DuplicateTimeline('<name> backup')` by hand.
- **Voice Isolation** writes at the TRACK level (`tl.SetVoiceIsolationState`); the item version returns false.
- **Frame QA per clip only:** `tl.GetCurrentClipThumbnailImage()` returns the CURRENT CLIP's graded frame (GUI + Color page only), NOT the program composite: over a graphics track it shows the overlay on black and proves nothing. Compositing and multi-track grades need a real render.
- Bin organization, markers, color groups, layout + keyboard presets, project settings: all live.

## Broken or dangerous: do not build on these

- **`SmartReframe`: the feature works, the API call does not.** The Inspector button fills the frame; the API call returns `success: true` and changes nothing, and there is no getter to even verify a UI reframe. Keep using `workflows/face-frame.py` for the measured 9:16 crop.
- `create_magic_mask` / `RegenerateMagicMask` return False in every mode, GUI included.
- `Stabilize` returns True but exposes no property to verify. Unverifiable through the API.
- Stills: `tl.GrabStill()`, then the album's `ExportStills(...)` (also drops a `.drx` of the grade).
- `Graph` has no AddNode: you can set LUTs/labels/enable on existing nodes but cannot create serial nodes. Workarounds: `ApplyGradeFromDRX` (a .drx carries a whole node tree, built once by hand or grabbed off a graded clip), a Fusion comp (`AddFusionComp`, where node creation IS exposed), or fold the look into one node (a DCTL or the folded cube).
- Page switching is `resolve.OpenPage('edit')`; the LUT list refresh is `project.RefreshLUTList()` (no `resolve.` form).
- **`pm.SaveProject()` on "Untitled Project" opens the GUI's Save Current Project dialog** and the script hangs to its cap (official engine, 2026-09-25; § Project setup has the guard). The dialog is a hand-click or a background accessibility click on Cancel.
- **`tl.SetTrackEnable(type, n, ...)` returns True and changes nothing unless the Edit page is open** (2026-10-13: a render
  can leave Resolve on the Deliver page (one did, after five had left it on Edit), and there the call returned True with
  both tracks still off). `resolve.OpenPage('edit')` first, then read `GetIsTrackEnabled` back (it took at once).
- The scripting API cannot switch the Color page's node-graph level (Clip / Group Pre / Group Post / Timeline). Its whole UI surface is page switching + layout presets, so a session can build a group grade but cannot show it on screen — that dropdown is a hand-click.
- Resolve's own subtitle engine is the working transcription path; slate-clap sync detection false-positives on speech.

## Discipline

- **Target timelines by NAME, never `GetCurrentTimeline`,** whenever the user has the GUI open. They switch timelines while you work, and two writes have landed on the wrong timeline that way. Loop `GetTimelineByIndex` and match `GetName()`.
- **Read back after every write** (same rule as the Premiere bridge): property writes return success generously; the readback is the truth.
- Getting the cut onto the timeline is where the handoff ends unless asked for more. The user's own editing happens in the app.
