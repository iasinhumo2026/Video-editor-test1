# Resolve project templates

Empty DaVinci Resolve projects, one per frame rate, used to create every new Resolve job.

**Why these exist:** `timelinePlaybackFrameRate` (Project Settings → Master Settings → Playback frame rate) is a *separate* setting from `timelineFrameRate`, and the scripting API cannot write it: `SetSetting` returns False for every value and type tried. A new project defaults to 24 fps playback, so a 30 fps timeline built the naive way plays back at 24 and the audio comes out chopped and glitchy. Importing a `.drp` restores the frame rate and resolution wholesale, which is the only API path to that setting.

## Using one

Match the template to the **source footage frame rate**: `ffprobe` the raw first, always. See the `davinci-resolve` skill, "Project setup".

```python
pm.ImportProject('lanes/resolve/resolve-templates/<template>.drp', '<Project Name>')
pm.LoadProject('<Project Name>')
# then strip the inherited (empty) media pool + timelines, import media, replay the EDL
```

Read `timelinePlaybackFrameRate` and `timelineFrameRate` back before building anything.

## Available

| File | Timeline | Playback | Resolution |
|---|---|---|---|
| `1080p30.drp` | 30 fps | 30 fps | 1920x1080 |
| `1080p2997.drp` | 29.97 fps | 29.97 fps | 1920x1080 |

**24 fps needs no template**: a stock `CreateProject` is already 24/24; just set the resolution (resolution IS API-writable).

## Minting a new one: scripted, no UI click (2026-08-04)

```bash
uv run lanes/resolve/resolve-templates/mint-template.py \
  lanes/resolve/resolve-templates/1080p30.drp <fps> \
  lanes/resolve/resolve-templates/<out>.drp
```

Both paths are taken as given, so run it from the repo root with full repo-relative paths (a bare
filename only resolves if you happen to be standing in this folder).

The settings blob was reverse-engineered: `project.xml → CommonConfig → SM_Config → FieldsBlob` is a big-endian keyed-dict (same layout upstream davinci-resolve-mcp's `keyed-dict.js` round-trips) whose `SetupBA` value wraps a **zstd** frame containing a **protobuf** message. Two fields carry the frame rate:

- `f15` (varint): timeline frame rate enum = `floor(fps) × 2`; exactly 24 fps = field absent. Verified against Resolve's own exports at 18 rates (16→32 … 23.976→46, 29.97→58, 30→60, 119.88→238, 120→240).
- `f248` (float32): **playback frame rate**, the API-unwritable setting; absent at 24.

Everything else (resolution, color science, gallery config) rides along untouched, so any-rate templates derive from `1080p30.drp`. The script patches, recompresses, and rewrites the zip; needs Python 3.14+ (stdlib zstd) or `pip install zstandard`.

**Always verify a fresh mint before trusting it:** `pm.ImportProject` + read back BOTH `timelineFrameRate` and `timelinePlaybackFrameRate`, build nothing until they match, then delete the scratch project. (29.97 and 23.976 mints verified against Resolve Studio 21.0.3 on 2026-08-04.)

The manual route (set both rates in Project Settings by hand, strip, `ExportProject`) still works and is the fallback if a Resolve update changes the blob format: the script fails loudly (`unexpected SetupBA wrapper`) rather than writing garbage.

## Anonymity / leak check

**Keep templates empty and anonymous**: strip all media and timelines before exporting. But know the limits of a plain check: `unzip` + `grep -r "Users/"` only sees plaintext XML, and **the SetupBA blob is compressed — it carries absolute paths (e.g. `/Users/<name>/Movies/.gallery`, cache dirs) that a plain grep can NEVER find.** Both current templates were sanitized 2026-08-07 (same-length byte replacement inside the decompressed payload, re-verified by import + fps readback in Resolve; the local machine's cache prefs re-localize on import, so neutral paths cost nothing). Any NEW template minted from a fresh Resolve export starts dirty again: sanitize it the same way before sharing it (decode the blob, replace the username/job strings at equal length, recompress).
