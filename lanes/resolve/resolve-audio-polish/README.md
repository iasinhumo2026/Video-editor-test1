# Audio polish in DaVinci Resolve — the default pass

**This is pipeline step 3, the audio polish, on any Resolve-finish job.** Validated end to end
2026-08-06 on `your-job` (9 sections, 210 timeline clips): section loudness
spread collapsed from **4.7 LU to 1.1 LU**, every true peak moved under −0.6 dBFS (two were
over full scale), and **not one clip on the timeline moved**.

**Runs at pipeline step 3 — see `CLAUDE.md` § The Pipeline for when and why (2026-08-28).**
The one lane-specific consequence of that slot: this pass swaps MEDIA, not clips, so every later
hand edit rides on the normalized files — but a timeline REBUILD from re-imported raw does not
survive it. After any re-replay, run `replace-clips.py` again before saving.

Companion files: [`workflows/normalize-sections.sh`](../../../workflows/normalize-sections.sh) (measure + render the
normalized copies; shared with the Final Cut lane) and, here, [`replace-clips.py`](replace-clips.py) (swap them in,
verify, revert).

## Why not do it in Resolve

**Resolve's scripting API cannot build the house chain: it has no limiter** (through 21.0.3 it had no
audio-gain surface at all; story in the archive). **Resolve 21.1 added a clip level**
(`SetProperty('AudioVolume', dB)`, −100..+30, reads back) plus pan and `SetFades`, proven 2026-09-25 on
103 SFX levels and a music bed. That is a GAIN, not the chain: the house pass is measured gain INTO a
−6 dBFS hard limiter, and a +12 dB `AudioVolume` with nothing behind it clips the peaks. There is still
no limiter, no FX insertion and no normalize method at timeline or project level, so the voice chain is
baked into the media below on every version.

Resolve's own **Normalize Audio Levels** dialog is the manual equivalent and it is fine —
if you use it, pick **ITU-R BS.1770-4** (the gated algorithm; BS.1770-1 has no relative gate
and silence between takes drags the reading down), target **−17 LUFS** (the house number), and **Relative** mode
per section (Independent flattens delivery by normalizing every clip separately). The
broadcast presets — EBU R128, ATSC A/85, OP-59, TR-B32 — are locked around −23 to −24 LUFS,
about 8 dB under what YouTube wants. **Never True Peak / Sample Peak**: those normalize to
the loudest sample, not perceived loudness, which is exactly the failure mode this pass
exists to fix.

## The method

Measure → static gain → limiter → **verify no drift** → `ReplaceClip`.

### 1. Measure the KEPT speech, once per job

The gain is the house measurement, not a per-file reading: `workflows/voice-gain.py <job>` runs
`ebur128` over the kept ranges (`transcript/cuts.json` against `raw/`) and returns the whole-dB
gain that puts them at **−17 LUFS integrated, pre-limiter** (`LANES.md` § step 3 owns the target).
`workflows/normalize-sections.sh` calls it for you, once per job dir — a section sub-job with its own
transcript gets its own number. Kept ranges, never the whole take: dead air and the slate drag
the integrated reading down and over-gain the speech. `AMPLIFY_DB=<n>` overrides it.

Per **file**, not per clip, when rendering: the timeline references media pool clips, so one
normalized copy per source recording covers every cut made from it.

**`LRA` is the tell for whether one gain is enough.** 6–10 LU is normal talking head.
A recording reading 20+ genuinely varies clip to clip and will still need hand attention after
this pass — a static gain matches recordings to each other, it does not fix dynamics inside one.

### 2. Gain + limit, one static chain

```bash
GAIN=$(uv run workflows/voice-gain.py projects/<job> --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["gain_db"])')
ffmpeg -nostdin -v error -y -i "$SRC" -c:v copy \
  -af "volume=${GAIN}dB,alimiter=level_in=1:level_out=1:limit=0.501:attack=5:release=50:level=disabled:latency=1" \
  -c:a aac -b:a 320k "$OUT"
```

- **`-c:v copy`** — video is stream-copied, so the picture stays bit-identical and the render
  is seconds, not minutes. Only audio is rebuilt.
- **`level=disabled`** is non-negotiable: the limiter's auto-level defeats the static gain you
  just measured. **`latency=1`** compensates its own lookahead so nothing shifts in time.
  Both are the house `alimiter` locks from `splice.sh`, and so is the whole filter string.
- **`limit=0.501`** = −6.0 dBFS, the house ceiling. Peaks land several dB over it, so the
  limiter works every stressed syllable — that saturation is the point (2026-09-03).
- **320k AAC** — the downstream-bitrate lock: any re-encode after splice must match or exceed
  256k, and a quiet bed starves below that.
- **NEVER `loudnorm`.** Dynamic normalization pumps; your call, and it is a repo lock.

### 3. Verify no timing drift BEFORE committing

**This is the step that protects the whole edit.** An AAC re-encode can shift audio by a
frame through encoder priming, which would silently break lip sync across every cut. Run one
file first and compare four things against the source:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 <f>
ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames -of csv=p=0 <f>
ffprobe -v error -select_streams a:0 -show_entries stream=nb_frames,start_time -of csv=p=0 <f>
```

Duration, video frame count, audio frame count and audio `start_time` must all match exactly.
On the reference job all nine matched to the sample. If any differ, stop — do not replace.
An `.mkv` reads `N/A` for the frame counts and stream durations: `normalize-sections.sh` counts its video packets and
ends its audio at the last packet instead, and a reading missing on either side fails the gate.

### 4. Swap the media, do not re-edit

```python
mediaPoolItem.ReplaceClip('/abs/path/to/normalized.mp4')
```

[`replace-clips.py`](replace-clips.py) does the whole swap. Run it through the davinci-resolve MCP's `run_script_unsafe`
(it reads the filesystem; `run_script` cannot), `timeout: 60`, with the script
`import io; JOB='<abs job>'; exec(io.open('<abs>/lanes/resolve/resolve-audio-polish/replace-clips.py', encoding='utf-8').read())`.

The timeline references **clips**, not files, so repointing the media pool item leaves every
cut, trim, slip and hand edit exactly where it is. This is the whole reason the pass is safe
to run on a locked timeline.

Snapshot every track's `(name, start, duration, source start, source end)` before and after and diff
them — the pass is only correct if the answer is UNCHANGED on every track. Write a `REVERT.json` mapping each
clip name back to its original path as you go, so undoing it is one scripted loop.

⛔ **Never swap under a clip whose FPS property was set (every iPhone take, 2026-10-13).** `ReplaceClip`
re-ingests the new file at its native rate, so the clip's 29.97 comes back 30.0 and every V1 item reads its
source 0.1 % further in: the picture ran 2–20 frames off its sound across an 11-minute take while every start
and duration stayed equal, which the old `(name, start, duration)` snapshot called clean. `replace-clips.py`
now puts the FPS back, prints each item whose source start moved and says MOVED; putting the FPS back does
not restore the V1 source times. On such a clip, lay the timeline from `audio-normalized/` instead (the
`davinci-resolve` skill § Step 3).

**Never overwrite the raws.** Normalized copies live in `projects/<job>/audio-normalized/`.

**Version the output filename, never overwrite a path Resolve already has linked.** Same
reasoning as the Premiere and CapCut lanes: an app holding a linked file can keep serving the
cached old one. `rough-cut-use-case.mp4` → `-v2.mp4` → `-v3.mp4` across the reference job.

### 4a. Two things ReplaceClip does that break other scripts

**It RENAMES the media pool item to the new filename.** Every name-keyed lookup downstream
silently stops matching — on the reference job this broke a retime audit (which reported "no
retimed clips" when all five were intact) and would have broken the section colour/marker pass,
which keys on `rough-cut-use-case.mp4` and suddenly saw `rough-cut-use-case-v3.mp4`. Strip a
trailing `-v<N>` before matching, in every name-keyed pass that follows a swap:

```python
_VER = re.compile(r"-v\d+(?=\.[A-Za-z0-9]+$)")
def base(name): return _VER.sub("", name)
```

**It CLEARS the clip colour label.** Re-run the colour pass after any swap or the clip comes
back unlabelled. (Seen on a title card, not just audio — this applies to any `ReplaceClip`.)

### 5. RETIMED CLIPS: derive protected ranges from the AUDIO items, not the video

**The single most expensive mistake on the reference job — three rounds to find.**

Resolve's audio time-stretch breaks down on extreme speed changes. On a 16.95x clip it emitted
a wall of **full-scale clipped samples for the first 1.1 seconds** (RMS −2.1 dB, 61% of samples
past 0.985) before recovering. Normalized, hard-limited audio makes it dramatically worse,
because the stretch is being driven into overload. So a retimed clip wants its **original**
level, not the section gain.

Since `ReplaceClip` is per source FILE, you cannot exempt one clip — you exempt the source
RANGES that clip consumes, with a time-varying gain:

```bash
R=0.25   # ramp seconds, INSIDE the protected range
P="clip(min((t-<a>)/$R\,(<b>-t)/$R)\,0\,1)"
-af "volume=volume='pow(<G>\,1-max($P1\,$P2))':eval=frame,alimiter=..."
```

`pow(G, 1-p)` interpolates in dB; `p` ramps 0→1 over `R` seconds inside each range so the
transition happens in material only the retimed clip uses (at 17x, 0.25s is 15ms on screen).
Ramp INSIDE, never outside — outside dips material other clips may share.

**Get the ranges from the audio items.** A retimed clip's audio is a SEPARATE timeline item
with its own source range, and they do not match. On the reference job the video read
`src 3474-5983` while the audio read `src 3474-6424`, and that one audio item covered BOTH
video clips (the second had no audio item at all). Deriving from video left **14.7 seconds of
source unprotected** — still at +9.7 dB under a 17x compression. That was the whole bug.

```python
for c in tl.GetItemListInTrack('audio', 1):
    ss, se, d = c.GetSourceStartFrame(), c.GetSourceEndFrame(), c.GetDuration()
    if not d or ss is None or se is None:      # audio items return None on some clips
        continue
    if abs(float(se - ss) / d - 1.0) > 0.02:
        ...                                     # protect ss..se
```

**Then verify by rendering the timeline range and measuring it — not by measuring the file.**
The file can be perfect while Resolve still mangles it. Per-100ms RMS, peak and percent-clipped
across the retimed span is the check; a clean file plus a broken render points at the stretch,
not the gain. And measure the SPECIFIC source window the stretch consumes — a broad mean around
it averages away the loud material that is actually causing the overload.

**If it still misbehaves, the fix is level, not muting.** Lowering the clip's Inspector gain
(which the API cannot reach) fixed it where three rounds of file surgery did not.

## Targets

**The house chain, no lane exception (2026-09-04):** kept speech → **−17 LUFS integrated
pre-limiter** (gain measured by `voice-gain.py`) → **−6 dBFS hard limiter**. `LANES.md` § step 3 is
the target's home; this lane only changes WHERE the chain is applied (baked into the media, because
the API cannot apply it as an effect). The 2026-08-06 validation numbers above were measured on the
lane's old −16 LUFS / −1 dBFS whole-file target; the drift gate and the `ReplaceClip` mechanics are unchanged.

The script's `OUT_LUFS` column measures the WHOLE normalized file, dead air included, so it reads
under −17; the kept speech is on target. `OUT_PEAK` is a TRUE peak (dBTP, `ebur128=peak=true`), so it reads a
little over the −6.0 dBFS limit on every file: −5.8 on the Final Cut lane job, about −5 on the Windows iPhone takes
(the AAC encode and the peaks between samples overshoot what the limiter capped). It is not a limiter miss.

## What this pass cannot fix

**Clipping already recorded into the source.** On the reference job two sections measured
`+0.1` and `+0.2` dBFS true peak *before* any gain — already over full scale in the recording.
The limiter stops it getting worse and brings the section to target, but the distortion
baked into those takes stays. If it is audible, that is a re-record, not a mix fix.

**Dynamics inside a single section** — see the `LRA` note above.

## Afterwards

One limiter on the **Master bus** at −1 dBTP is a reasonable safety net, and it should barely
engage. Do not put limiters on individual clips: that is the move this pass replaces, and it
is what fails when some clips are already hot and others are 12 dB down.
