# lanes/finalcut — the Final Cut Pro lane (SpliceKit)

Final Cut has no scripting surface of its own that can edit a timeline. This lane runs a **patched copy** of Final
Cut with [SpliceKit](https://github.com/elliotttate/SpliceKit) (MIT, v3.3.9) loaded into it: a JSON-RPC bridge on
`127.0.0.1:9876` inside the app, plus an MCP server over it. The timeline itself is built as **FCPXML** and imported
through Final Cut's own importer; the bridge opens, reads back, drives menus and dialogs, and exports. A fresh job
runs the whole line here from its pipeline files (`replay.py` → `import.py` → `export.py`), validated 2026-09-25 on a
Talking Head Explainer and a long-form job with a section, each held clip for clip against its Premiere project and
frame by frame against its Premiere master; a finished Premiere edit ports over too (`port-premiere.py`). Locks: [`lab-notes.md`](lab-notes.md).

## Install (once per machine, and again after every Final Cut update)

`./setup-finalcut.sh` (or `./setup.sh --lane finalcut`, which runs it) does all of it and is safe to re-run:

1. Final Cut 12.0 or later from the App Store, the one-time purchase (`com.apple.FinalCut`) or Apple Creator Studio
   (`com.apple.FinalCutApp`), opened once. 11.x is refused: it cannot import the FCPXML 1.14 the lane writes. On an
   Intel Mac, `doctor.py` warns every time: SpliceKit 3.3.9 crashes Final Cut when the timeline is skimmed with
   snapping on (the fix, SpliceKit PR #92, is unreleased), so snapping stays OFF there; and its Smooth Scroll crashes
   it the moment the timeline plays, so `doctor.py` saves Smooth Scroll off in the copy (lab-notes § 22).
2. SpliceKit 3.3.9 into `/Applications/SpliceKit.app`: the release DMG from GitHub, checked against its SHA-256.
3. The patch: SpliceKit's patcher is an app, so the installer quits Final Cut, opens it and the USER clicks
   **Continue** once (exit 4 until then). It copies Final Cut to `~/Applications/SpliceKit/`, loads its bridge into the
   copy and re-signs the COPY; the App Store app is never touched and libraries stay compatible with it. A Final Cut
   update means patching again: the installer compares the two versions and asks for the click again. `doctor.py`
   decides which App Store Final Cut the lane drives (two installed: the newer, said out loud) and keeps exactly ONE
   copy, at its version and build; any other copy goes to the Trash (lab-notes § 21).
4. The house look as Final Cut's Custom LUT: `workflows/fold-look.py` folds Autumn-Rec709 at 80/120 into
   `~/Library/Application Support/ProApps/Custom LUTs/house-Autumn-Rec709-80-120.cube` (the template names it).
5. The `splicekit` MCP: a venv in `vendor/splicekit-mcp` and its entry in `.mcp.json`, pre-approved by `setup.sh`
   (`/Applications/SpliceKit.app/Contents/Resources/mcp/server.py`, 231 tools, for live driving; every script here
   talks to the bridge through `sk.py` and needs no MCP).

Then `uv run lanes/finalcut/doctor.py --repair` starts it, the only way Final Cut is ever started (the rule: lab-notes
§ 21; the procedure: the `final-cut-pro` skill § Procedure 1).

## A fresh job, end to end

    workflows/normalize-sections.sh projects/<job>      # step 3's bake (once cuts.json is final, before the replay)
    uv run workflows/placement.py projects/<job> --write                          # step 5: the graphics rows (renders built)
    uv run workflows/music-onset.py <track> --write-plan projects/<job>            # the opt-in bed: music-plan.json
    uv run lanes/finalcut/replay.py projects/<job> [--steps 2,3,4,5,6,music]     # the timeline, as far as the run has got
    uv run lanes/finalcut/import.py projects/<job>/finalcut/<name>.fcpxml         # into Final Cut, proven clip by clip
    uv run lanes/finalcut/export.py projects/<job>                                # on the creator's go: master + deliverable
    ./finalize.sh <job> --apply

`replay.py` reads what the pipeline wrote and nothing else, so what it builds is what the Premiere placers would lay
from the same files (the Talking Head Explainer test: every clip equal to its Premiere project, sound within 0.7 ms). Each run writes a NEW
library and project (`<job>`, `<job>-v2`, ...): a rebuild never overwrites one the creator has edited by hand, and a
hand edit made in Final Cut is live state (read it with `sk.py fcpxml.export` or `verify.py`), never re-laid over.
What the files do not carry it cannot rebuild, and a job that has them says so: a patch laid by a job-local script
(a tracked blur laid by a one-off script), a hand Motion, a crossfade. The lane builds the ORGANIC cut only: there is
no ad variant (`--variant` is Premiere-only); `export.py --variant NAME` only files an export under `outputs/NAME/`.

## The steps (the preset says WHAT; this is HOW)

| # | Step | Status | How |
|---|---|---|---|
| 2 | Replay | ✅ | `replay.py`: `transcript/cuts.json` of the job, then each `sections/<s>/` at its `_timeline`, one spine clip per segment carrying its own dialogue, in/out on the timeline's frame grid as Premiere's replay snaps them; a `media` segment plays its file from 0; an `audio_lead` is a split edit (`audioStart` / `audioDuration`). The timeline: 1080×1920 for a short, the raw's own size for long-form, the plan's frame rate. |
| 3 | Audio polish | ✅ baked | `normalize-sections.sh` bakes the measured gain and the −6 dBFS limiter into `audio-normalized/` (each section's raw with its own cut's gain), and `replay.py` lays those copies (the picture stream is copied bit for bit). A mono clip gets back the 6 dB Final Cut's mono split takes (lab-notes § 16). The second-voice lift (the Talking Head Explainer) is volume keys on the dialogue from `transcript/voices.json`, sized by `voice-gain.py --second-voice`. There is no in-app chain: no FCPXML effect IDs have been captured for Final Cut's own audio FX. |
| 4 | Grade | ✅ | The house look folded into ONE cube (`workflows/fold-look.py Autumn-Rec709 --intensity 0.80 --saturation 1.20`) installed as `~/Library/Application Support/ProApps/Custom LUTs/house-Autumn-Rec709-80-120.cube`. Every camera-footage clip (the plan's `graphics_scope` ranges, or `--grade-ranges`) carries Final Cut's Custom LUT effect pointing at it, from `templates/house-lut-filter.xml` (the LUT choice captured once from the inspector). Final Cut has no adjustment layer: the footage carries the effect, the graphics lanes carry none. |
| 5 | Graphics | ✅ | `uv run workflows/placement.py projects/<job> --write` writes `hf-graphics/placement.json` (and each section's, at its `timeline_offset`) as connected clips on lanes 1.. (V3 graphics, V4 patches, V5 captions), straight-alpha ProRes 4444 as rendered, conform "fit" (a 2160×3840 render in a 1080×1920 project = scale 1), a full-screen mp4's own sound muted. A stale `cut_rev` or an orphaned row is refused; graphic cells with no `placement.json` are a ⚠ (a refusal under `--steps` naming 5). ⚠️ Organic only: no ad variant (`--variant` is Premiere-only). |
| 5′ | Footage moves | ✅ | The Talking Head Explainer: the plan's `layout` map through `face-frame.json` `modes`, a static transform per clip or a 1-frame linear key pair at a switch inside one (Premiere's hold), V1 never razored. Position is percent of the frame height from the centre (+y up), scale relative to the fitted media. Long-form: the opening zoom-out and each `push_in` beat as linear scale keys matched to how Premiere RENDERS its `zoom` (half a frame on, a 360° shutter), Final Cut's Zoom blur keyed to the move (lab-notes § 15). A raw a hair narrower than the frame (3836 on 3840) is scaled to fill it. |
| 6 | SFX | ✅ | `hf-graphics/sfx-plan.json` on connected audio lanes −1.. (plan track 1 = A2), each slice to the sample, cut where the next sound on its track starts, `level_db` as `adjust-volume` dB, `fade_out_s` as a fade. Every file's embedded timecode is honoured (lab-notes § 4). For hand placing, `uv run lanes/finalcut/sfx-pack.py projects/<job> [--import]` makes the whole pack a NEW library `finalcut/SFX Pack.fcpbundle` (event `sfx`, every clip keyworded `sfx`, from its file's timecode) to drag from; ⚠️ the FCPXML is DTD-valid and offline-proven, the import not yet run live. |
| + | Music | ✅ | `hf-graphics/music-plan.json` (`workflows/music-onset.py <track> --write-plan projects/<job>` writes it; a track in `audio/` without one is a ⚠): one connected clip from 0 at `source_in`, `bed_db` then a −96 dB key over the `tail`, to the end of the job's own timeline (sections excluded unless the plan names an `end`). |
| 8 | Export | ✅ | `export.py projects/<job>` on the creator's go: `share.py` has Final Cut render the project through its own share sheet (Export File, ProRes 422, Save only) into `finalcut/renders/<name>-master.mov` with no clicks, its settings set and its save panel completed from inside Final Cut (lab-notes § 14, § 20), and proves the frame count; then it encodes the format's deliverable with `workflows/deliver.py` (the presets' § Export, 2026-09-26: vertical 1080×1920 CBR 14, less past 2:48; long-form 3840×2160 from a 1080 or 4K master, CBR 50, CBR 80 above 30 fps; `--shorts` on a 2160×3840 master the 4K Shorts file into `outputs/shorts/`) and proves it. Proven live 2026-09-26 on every cell. Then `./finalize.sh <job> --apply`. ⚠️ Organic only: `--variant NAME` writes `outputs/NAME/<job>.NAME.mp4` for `./finalize.sh <job> --variant NAME --apply`, and a `--project` named `… AD` is refused without it. |

**Proof on every build:** `import.py` refuses an existing library, waits for the project, clears Final Cut's
notification sheet, then `verify.py` exports the LIVE project and diffs it clip by clip against the built FCPXML
(media as the resolved file, source in, duration, split-edit audio range, transform + keys, volume + keys + fade,
filters with their keyed and static params: a dropped Custom LUT choice fails). Exit 0 is the
definition of done for the build. `verify.py <built> --live <other.fcpxml>` diffs any two FCPXMLs the same way, which
is how a replay is held against a Premiere project (`prproj-read.py` → `port-premiere.py`). The export is proven by
`export.py`, then `workflows/flash-scan.py`, and against an earlier master by a per-frame PSNR and an audio null test.

## Files

The file inventory is [`lanes/README.md`](../README.md) (the `finalcut/` row).
