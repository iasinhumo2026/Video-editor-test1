# Premiere lane templates

Tracked assets the Premiere lane's scripts consume. Nothing here is a look — the apply mechanics
live in [`../premiere-grading.md`](../premiere-grading.md), the numbers in the preset.

## `adjustment-layer.prproj` — the adjustment-layer donor

**Why it exists:** Premiere's scripting surface has no way to CONSTRUCT an adjustment layer. The
only route is `app.project.importSequences(<this file>, [<its sequence uuid>])`, which lands a
working online "Adjustment Layer" item at project root (plus a junk `adj-template` sequence to
delete). The donor is a fixed **3840×2160**.

`mint-adjustment-layer.py <W>x<H>` patches a copy of it to the sequence's own frame size and prints
the template path + the uuid to import. Those `adjustment-layer-<W>x<H>.prproj` children are
**gitignored and regenerable** (a size mints byte-identically every time, so re-importing is
idempotent); only the donor is tracked.

**Re-cutting the donor**, if Premiere's `.prproj` format ever changes: place a UI-born adjustment
layer on a scratch sequence and call `sequence.exportAsProject(path)` via ExtendScript (the ES
method works; the MCP tool of the same name is a stub). Only the very first donor ever needed the
UI. The tracked file is path-sanitized to `/Users/creator` — sanitize any re-cut the same way before
committing, and remember `packaging/package-for-client.sh`'s leak-check gunzips staged `.prproj`
blobs precisely because a plain `grep` cannot see inside one.

Placing, spanning and grading the layer: [`../premiere-grading.md`](../premiere-grading.md) § 1.

## `youtube-2160p-h264-cbr50.epr` — the locked YouTube export preset

H.264, 3840×2160, **CBR** (`ADBEVideoBitrateEncoding` = 0) with target = max = **50 Mbps**, AAC
320k. VideoToolbox's VBR treats the target as a ceiling, which is the whole reason for the lock; the
measurement behind it is in [`../lab-notes.md`](../lab-notes.md) § Step 8.

## `mint-export-preset.py` — the presets the numbers need beyond the tracked three

`uv run lanes/premiere/premiere-templates/mint-export-preset.py <WxH> [--mbps N] [--2997] [--reels]` copies a
tracked preset beside itself, changing only the frame size (`ADBEVideoWidth`/`Height`) and the bitrate
(`ADBEVideoTargetBitrate`/`MaxBitrate`, target = max so it stays CBR), each asserted found once; AAC 320k and
everything else stay the tracked preset's. `lanes/premiere/export.py` mints what it picks on first use:
`youtube-2160p-h264-cbr80.epr` above 30 fps and `instagram-1080x1920-h264-cbr<N>-23976.epr` for a Reel past 2:48
(the numbers: the presets' § Export, 2026-09-26). `1920x1080` still mints a native 1080 file's preset for a
`--preset` export; nothing picks it by default (a 1080 long-form goes up at 2160p). It never mints 2160×3840:
Premiere's H.264 caps the frame at 4096×2304 (`../lab-notes.md` § Step 8). Minted files are regenerable and
gitignored. Proven live 2026-09-26 through `export.py`: the CBR 80 twin at 59.94 read 79.7 Mbps, 3840×2160 High,
bt709, AAC 320k, moov first, 1200 of 1200 frames.

## `cep-bridge-autostart.patch` + `apply-autostart-patch.py`

The CEP panel patch that makes the MCP bridge start on its own instead of needing a click. Applied
by the **script**, never by hand and never by `patch(1)`: it edits by content, so it is idempotent,
needs only python3 (Git Bash has no `patch` binary), and survives upstream line drift. **Re-run it
after any engine re-clone, version bump, or `cep-plugin/` re-copy**, or the panel silently reverts
to click-to-start.

## `locked-screen/`

`keypid.swift`, how `../premiere-dismiss.sh` posts Return to Premiere's pid under a locked screen; the folder's
README records the approaches that did not work there.
