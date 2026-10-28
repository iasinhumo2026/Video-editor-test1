# Exporting from DaVinci Resolve — what the API can and cannot set

Measured 2026-08-06 on `your-job` (19 min, 3840x2160/30, Resolve Studio 21.0.3.7), and
re-measured 2026-09-25 on Resolve Studio 21.1 (`your-job-resolve`, 120 s
1080x1920/23.976). Read this before scripting a delivery render; most of it is the API lying about
settings it accepted and then ignored. The lane is Studio 21.1+ only (2026-10-05), where **`VideoQuality` is a
bitrate** (§ below); the dict runs through `run_script` (`davinci-resolve` skill § Step 8).

## The short version (21.1+)

The numbers are the presets' § Export (researched and set 2026-09-26): `FormatWidth`/`FormatHeight` are the FILE's
frame, not the timeline's, so a 1080 long-form timeline renders at 3840×2160 and a 4K vertical one at 1080×1920
(its YouTube Shorts file is a second job at 2160×3840).

**Set the keys ONE CALL EACH and read every return (2026-09-27).** `SetRenderSettings` with a dict is all-or-nothing:
Resolve Studio 21.1 on Windows refused `VideoQuality` for every value (14000, "14000", 0, "Automatic", "Best", on H264
and H264_NVIDIA) while the Mac's 21.1 took 14000, and a dict holding it dropped EVERY key with it: the render came out
H.264 Main at 52.6 Mbps, which breaks the 300 MB Reels cap by two minutes. When the bitrate cannot be set, the lane
renders a ProRes 422 HQ master (DNxHR HQ where the build has no ProRes encoder) and `workflows/deliver.py` encodes the
deliverable to the preset's numbers, the Final Cut lane's master → deliverable shape.

```python
def set_each(proj, d):
    """One key per call; the keys the build refused (a dict with one refused key drops them all)."""
    return [k for k, v in d.items() if not proj.SetRenderSettings({k: v})]

proj.SetCurrentRenderFormatAndCodec('mp4', 'H264')
refused = set_each(proj, {
    'TargetDir': OUT, 'CustomName': '<job>-final',
    'SelectAllFrames': True, 'FormatWidth': 3840, 'FormatHeight': 2160, 'FrameRate': 23.976,
    'VideoQuality': 50000,        # 21.1: kb/s, a CEILING. 50000 long-form (80000 above 30 fps), 14000 a vertical file
    'MultiPassEncode': True,      # what makes the ceiling the bitrate: 32.6 -> 50.00 Mbps measured
    'EncodingProfile': 'High',
    'AudioCodec': 'aac', 'AudioSampleRate': 48000,
    'ExportVideo': True, 'ExportAudio': True, 'NetworkOptimization': True,
})
if refused:                       # no bitrate on this build: a master, then workflows/deliver.py
    codecs = proj.GetRenderCodecs('mov')
    codec = 'ProRes422HQ' if 'ProRes422HQ' in codecs.values() else next(v for k, v in codecs.items() if 'DNxHR HQ' in k)
    proj.SetCurrentRenderFormatAndCodec('mov', codec)
    assert not set_each(proj, {'TargetDir': OUT, 'CustomName': '<job>-master', 'SelectAllFrames': True,
                               'FormatWidth': TL_W, 'FormatHeight': TL_H,   # the TIMELINE's frame: deliver.py scales
                               'ExportVideo': True, 'ExportAudio': True,
                               'AudioCodec': 'lpcm', 'AudioBitDepth': 24, 'AudioSampleRate': 48000})
proj.StartRendering([proj.AddRenderJob()])
```

After a master: `uv run workflows/deliver.py <OUT>/<job>-master.mov <OUT>/<job>-final.mp4` (the frame picks the numbers:
landscape → 3840×2160 CBR 50, vertical → 1080×1920 CBR 14 or the Reels rule past 2:48; `--shorts` for a 4K vertical's
second file), prove the file (§ Confirm the file), then delete the master. Proven on macOS 21.1 2026-09-27: a
1080×1920 ProRes 422 HQ master of a 29.97 timeline encoded to H.264 High, 13.95 Mbps, bt709 on all three tags, 159 of
159 frames, each frame the raw frame the EDL names. The refusal itself is Windows-only so far: that branch is on the
Windows re-test list.

**Proven 2026-09-26 on Resolve Studio 21.1** (a synthetic 23.976 job, 16:9 at 4K and 1080, 9:16 at 4K): every file
H.264 High, the preset's frame, bt709 on all three tags, limited range, AAC 320 kb/s, moov first, 480 of 480 frames.
**Without `MultiPassEncode` the `VideoQuality` number is only a cap** (like VideoToolbox VBR): 50000 landed at 43.8
Mbps on 4K, 32.6 on a 1080→2160 upscale, 14000 at 10.9 on the vertical file. With it, the upscale read 50.00 Mbps
(per second 47–53). Resolve writes a 12–24 frame GOP (YouTube asks half the frame rate) and level 4.0 on the
1080×1920 file (legal for 1080p30).
Pick the vertical number from the preset: CBR 14, or `video ≤ 2350 / seconds − 0.32` Mbps past 2:48.

## `VideoQuality`: a bitrate on 21.1, a dropdown INDEX before it

**Resolve 21.1:** the API stub documents `VideoQuality` as `0 = automatic, int > 0 = bit rate, or
'Least'/'Low'/'Medium'/'High'/'Best'`, and it does what it says: `14000` rendered **13.96 Mbps**
(2026-09-25). The UI's "Restrict to N Kb/s" is therefore scriptable now. `GetRenderSettings` does not
exist (it answers `None`, like several proxy methods: § `hasattr` below), so settings never read back: verify
the finished file with `ffprobe`, always (§ Confirm the file).

**Before 21.1 (history: the lane refuses those builds since 2026-10-05)** `VideoQuality` was a dropdown INDEX that
`SetRenderSettings` accepted and ignored (50000 rendered 18.8 Mbps, 100 rendered 1.1), no bitrate key existed, and
`MultiPassEncode` with `VideoQuality: 0` (Automatic) was the only lever (35.0 Mbps on a 4K screen recording; 36.8 on the
19-minute reference job).

## Codec choice

**H.264** is the deliverable (the presets' § Export; the safest YouTube ingest). H.265 is more efficient per bit
but license/plugin dependent. The stock **`YouTube - 2160p` preset** leaves multi-pass off and landed at 19.4 Mbps
(21.0.3): never the delivery route.

## Multi-pass renders look FROZEN — do not judge progress by file size

The analysis pass writes almost nothing. On the reference job the output sat at **44 MB for
four minutes** while the job was actually at **60%**, and a render was cancelled on that
misreading. File size is a valid *completion* signal (grew, then stable, then `lsof` released)
but a useless *progress* signal.

Poll the job instead:

```python
st = proj.GetRenderJobStatus(job_id)      # {'JobStatus': 'Rendering', 'CompletionPercentage': 60}
```

Note `CompletionPercentage` is laggy and `TimeTakenToRenderInMs` reads `0` mid-render — poll it
several times over a minute before concluding anything is wedged. Multi-pass roughly doubles
render time: ~20 min for 19 min of 4K on this machine.

## `hasattr` is meaningless on Resolve objects

They are dynamic proxies that answer `hasattr` for **any** name. `GetTrackVolume`,
`GetTrackFader` and `GetTrackGain` all returned `True` — three different naming conventions
that cannot all be real — and all three resolve to `None` and are not callable. Same for
`GetRenderSettings` and `TimelineItem.GetRetime`.

**Always `getattr(obj, name, None)` and check `callable()`, or just call it and catch.**

## Confirm the file, never the settings

```bash
ffprobe -v error -show_entries stream=codec_name,profile,width,height,r_frame_rate,pix_fmt \
        -show_entries format=duration,size -of default=noprint_wrappers=1 <out>
ffmpeg -nostdin -hide_banner -i <out> -af ebur128=peak=true -f null - 2>&1 | sed -n '/Summary:/,$p'
```

Check resolution, frame rate, pix_fmt, duration (against the timeline frame count), average
bitrate (size×8÷duration — the container's `bit_rate` field can disagree) and programme
loudness. On the reference job the delivered programme read **−16.3 LUFS / 5.7 LU / −2.2 dBFS**.

**Predicting programme loudness from the source files does not work.** Averaging the section
files' integrated loudness and applying the fader offset was off by 3.5 LU, because the cut
weights sections differently than their raw durations do. Measure the actual export.
