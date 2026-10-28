# Premiere grading lane — pipeline step 4 mechanics

**HOW, not WHAT.** The look and the numbers live in the preset
([`presets/youtube/default/README.md`](../../presets/youtube/default/README.md) § Grade); the Resolve
counterpart is [`resolve-grading/`](../resolve/resolve-grading/README.md); per-lane status is
[`LANES.md`](../../LANES.md). Read this before grading on the Premiere lane: everything below was
measured on Premiere 26.3.2, and several traps produce a file that opens fine and renders nothing.

## The lane, end to end — four steps, two of them one command each

### 1. The layer — ONE command (2026-09-02)

```bash
node lanes/premiere/premiere-bridge.mjs grade-layer '{"job":"projects/<job>"}'
```

With the job's sequence active. No UI; the one required argument is the job folder, and the command refuses,
naming both projects, when the active project is not that job's. It mints an adjustment layer **at the frame size
it reads off the sequence**, imports it, provisions the V1/V2/V3/V4 track map, lays ONE instance on
**V2** spanning V1's full extent, names the clip `GRADE`, adds Lumetri via QE (`apply_effect` is
broken on 26.3), reports any track whose output is off, and saves. Opts:
`{"job":"projects/<job>","track":2,"minTracks":4,"lumetri":true}`. Idempotent both ways: it refuses if that track already
holds a `GRADE` clip, and reuses a same-size layer already in the project. **The size is READ, never
typed** — the donor template is a fixed 3840×2160, which on a VERTICAL timeline would scale to fit and
leave the top and bottom ungraded, silently.

**A later screen-recording section stays off the grade (2026-09-14).** The layer spans V1's full
extent and the command cannot tell camera footage from a screen capture. On a job whose later section is a
screen recording, trim the `GRADE` clip's end back to the camera footage's last frame right after it lands,
and never re-extend it on a later pass: a `GRADE` clip that ends early on a live timeline is that trim. WHAT:
[preset README](../../presets/youtube/default/README.md) § Grade.

**A job whose camera footage comes in WINDOWS is ONE clip razored in place, never copies (2026-09-19).**
When camera and non-camera sections alternate down the timeline, the single trim above cannot express it.
Let `grade-layer` lay its one `GRADE` clip, extend that SAME clip across all the windows (`c.end = T(end)`),
razor V2 at every window boundary in ASCENDING order, then remove the pieces sitting over the non-camera
windows. Every survivor is a razor child of the original, so each one still carries the Look that the
scripting API cannot write (§ "Why the LUT needs a file write"), and the track's item list stays in time
order. ☠️ **Never razor pieces off and `trackItem.move()` them onto the windows**: the moved pieces end up
out of order on the track, later razors on it silently stop taking, and the renderer intermittently skips
them — the "grade disappearing and reappearing" failure. Why QE does that, and the story:
[`lab-notes.md`](lab-notes.md), the razor-then-move lock.

The sequence, in one ExtendScript pass (no job-local driver needed):

1. Remove every V2 clip but the one `grade-layer` laid, back to front, and assert one is left.
2. `clip.end = <sequence end>` — the survivor now spans every window and every gap between them.
3. `app.enableQE()`, then `getVideoTrackAt(<grade track − 1>).razor(<timecode>)` at every window boundary
   in ASCENDING order. QE's track index is 0-BASED, so it is the preset's grade track minus one (V2 → `1`
   on `youtube/default`); read it off the map rather than typing a literal, the way `grade-layer`'s own
   `track` opt does. The timecode is nominal non-drop off the sequence rate, the same
   builder the bridge's `frame` command uses — a fractional rate formatted naively cuts frames late.
4. Assert every razor TOOK: read the DOM clip starts back and check each boundary is now the start of a
   clip. A razor that silently did nothing is the failure this whole procedure exists to avoid.
5. Remove, back to front, every piece whose start does not fall inside a kept window, then save.

Prove it with QE's item list sorted by time against the window list, the Look's component present on every
survivor, AND a per-window frame grab with V2 on vs muted (§ 4) — never a DOM readback alone.

**Under it — the minting mechanic.** Scripting cannot CONSTRUCT an adjustment layer, so one is MINTED
from the tracked donor project by `app.project.importSequences()`, which lands an ONLINE "Adjustment
Layer" item plus a junk sequence — delete the sequence, keep the item.
`uv run lanes/premiere/premiere-templates/mint-adjustment-layer.py <W>x<H>` prints the sized template
and the UUID to hand it; minting a size twice is byte-identical, so re-importing is idempotent (sized
templates gitignored, donor tracked). Placement is `overwriteClip`, trim via `c.end`, QE
`addVideoEffect`, property writes in display units, read back; `inPoint` sits at ~3600s, so clip
keyframes go at `inPoint + offset`.

**Retrofitting the track onto a timeline that already has graphics is one call, not a re-lay.** QE
`addTracks(1, 1, 0, 0, 0, 0, 0)` INSERTS a video track at index 1, so the old V2 shifts up to V3 with
every effect, keyframe and trim intact (verified 2026-09-01). Never move graphics by
re-`overwriteClip`-ing them — that drops their clip effects.

### 2. The Look, hands-off — three commands

```bash
./lanes/premiere/premiere-up.sh --quit                                    # saves through the bridge, graceful app.quit(), waits
uv run lanes/premiere/grade-lut.py apply projects/<job>/premiere/<job>.prproj
./lanes/premiere/premiere-up.sh projects/<job>/premiere/<job>.prproj      # relaunch, bridge back
```

That replays the default (Autumn); `--lut <Name>` replays any other captured cube under
`assets/luts`, `grade-lut.py luts` lists them, `strip --slot look` removes it. The pipeline sets no
dials: whatever was dialed at capture comes back with the params, pixel-identical to a hand-applied
grade, and stays editable afterwards.

**The project must be CLOSED while the tool writes it, and SAVED with the fresh Lumetri before the
quit** — or the on-disk file has no Lumetri to write into (`apply` exits "Lumetri #0 not found");
`--quit` saves it. Quitting the app rather than the project costs nothing: with no project open
Premiere drops the CEP panel anyway, and the relaunch is what restores the bridge.

**Write into a COPY, cold-open the copy, swap only once it is proven.** A refused open on the job's
own path is a modal on the user's screen and a wedged bridge; on a copy it is just a file.

```bash
P=projects/<job>/premiere/<job>
cp $P.prproj projects/<job>/premiere/archive/<job>.pre-lut.prproj   # the backup, always
cp $P.prproj $P.graded.prproj                                       # the working copy
uv run lanes/premiere/grade-lut.py apply $P.graded.prproj           # selfcheck runs first
./lanes/premiere/premiere-up.sh $P.graded.prproj                    # cold-open THE COPY
node lanes/premiere/premiere-bridge.mjs frame ...   # delta with GRADE toggled: must move
./lanes/premiere/premiere-up.sh --quit
mv $P.graded.prproj $P.prproj                                       # swap only now
./lanes/premiere/premiere-up.sh $P.prproj
```

☠️ **The hard gate after a refused open: no second open of anything until the modal is provably
gone.** Premiere queues every open behind the alert, and five queued opens once wedged the app past
any quit (2026-09-02). `./lanes/premiere/premiere-dismiss.sh --check` is the check (exit 2 = a
`UI_MessageBox::RunModal` frame on the stack, the only signal that survives a locked screen); without
`--check` it posts Return to the pid until it clears — a native alert waits for that Return, not for a
human. Only when it reports zero, and `./workflows/window-grab.sh --list Adobe` shows no alert-sized
window, may the next open be issued. Under a locked screen a running Premiere ignores `open -a`: the open
that lands is the AppleEvent `osascript -e 'tell application "Adobe Premiere Pro 2026" to open POSIX file "<path>"'`
(the third primitive in `premiere-dismiss.sh`'s header).

**Then flush the bridge dir before that open** (`$PREMIERE_TEMP_DIR`, `/tmp/premiere-mcp-bridge`
here):

```bash
rm -f /tmp/premiere-mcp-bridge/command-*.json /tmp/premiere-mcp-bridge/response-*.json
```

Every call issued while the alert was up is still sitting in that folder and executes the instant the
alert clears, so one of them can raise a second alert with no new call from you (three in one
afternoon, 2026-09-01). `premiere-up.sh` clears the dir only on its own `--quit` path, after Premiere
is down; `premiere-dismiss.sh` does not touch it.

**Trying a different cube is one hand step, then scripted forever.** Apply it by hand on a scratch
project's GRADE Lumetri (Creative > Look > Browse > the cube under `assets/luts/`, set the dials),
save, then `grade-lut.py capture <scratch>.prproj --slot look` writes `<Name>.lookparams` beside the
cube and `apply --lut <Name>` replays it forever; the default moves only with `DEFAULT_LUT`. ⚠️ The
browsed path is baked into the hashed payloads: browse from `assets/luts`, never a Downloads copy.

**A params file is proven before it is trusted: `grade-lut.py selfcheck` (2026-09-02)** — offline, no
Premiere, over every shipped `.lookparams`/`.lutparams` (`--lut <Name>` or a path checks one). It
proves element shapes — **every arb pid an open/close `<StartKeyframeValue>`, never self-closing, and
pid 4 the explicit empty sentinel in the look slot, which is the damaged-project signature** — plus
the BinaryHash length words, the embedded cube against its `.cube`, the dials, the 128-byte struct,
and sha256 drift against `assets/luts/README.md` § Checksums. `capture` runs it on what it wrote;
`apply` runs it first and REFUSES a failing file.

### 3. Check track output BEFORE measuring anything

☠️ **A muted track makes every grade test read ZERO and is indistinguishable from a dead effect
(2026-09-02)** — **Toggle Track Output** (the eyeball on the track header) drops the track from the
composite and silences `Exposure` with it, so that control cannot separate the two cases. Read
`videoTracks[i].isMuted()` on every track before measuring anything, and restore what the creator had
set (they mute grade and graphics tracks to see raw footage); `setMute(0|1)` writes. The tell that the
harness is fine: move something on **V1** (Motion `Scale` to 50) — if the frame changes, grabs are
live and the silence is upstream.

### 4. Verify from a program render, never from a readback

Grab one frame with the layer disabled and one enabled (the bridge `frame` command) and confirm the
footage moved and the graphics track did not. Absolutes differ per frame; **the tell is a max channel
delta in the tens** (measured 59 and 61 on two jobs; read the max or the p99, never the mean, which depends on
the footage: 6–8 per channel on a dim purple set whose max was 73, 2026-09-27). A 0 means the LUT silently did not land or the
track's output is off. On a fresh project this runs before any graphic exists, so the graphics half of
the check waits for the first placement.

⚠️ The **opposite** stack — V4 adjustment layers over everything, per-section Lumetri, film-feel
effects — is the vox-era architecture, and since 2026-08-31 lives only in its own opt-in preset
([`presets/youtube/vox-collage/premiere-lane.md`](../../presets/youtube/vox-collage/premiere-lane.md)).
Never read it on a `youtube/default` job.

## Why the LUT needs a file write, and the Look slot

**The LUT is NOT reachable through the scripting API** — six Lumetri properties look like it, and each
accepts a write, reads it straight back, and moves the render by not one pixel. **The numeric dials
ARE scriptable.** So the split is: dials scripted, LUT by file write.
☠️ **Never use the MCP's `apply_lut`: a MEASURED no-op that reports success** (tested 2026-09-02, not
inferred), and on a clip that already carries a Lumetri — which every GRADE layer does — it writes
into the wrong instance and resets it. A trap, never a route.

**Apply as Creative > Look, never Basic Correction > Input LUT** — the Look slot renders AFTER the
correction dials, so both fit in ONE Lumetri and the panel shows them; the Input slot forces a second
instance and hides the LUT. Params files sit beside their cubes:
`assets/luts/rec709/Autumn-Rec709.lookparams` (THE house look) and `London-Rec709.lutparams` (input
slot, retired). The `.lookparams` also snapshots all 105 dials, which is how Intensity 80 and
Saturation 120 come back on a fresh job — ⚠️ **the Blob does NOT carry dials**, so a blob-only capture
silently replays at defaults. Re-`capture --slot look` if the LUT changes; a dial-only change is an edit of the `num` block in place (2026-09-14: 70/115 → 80/120 that way, then the sha256 line in `assets/luts/README.md`).

## The five pieces a LUT is made of, and the fifth one

Four serialized Lumetri params (Blob shader stack, `.cube` path, enum, and pid 98 `Embedded LUTs` —
the whole cube in binary) plus one struct on the component. All must be present, and **only the
payload's 16-byte leading hash is underivable, which is what forces capture-and-replay.**

☠️ **THE FIFTH PIECE — the component's own `PremiereFilterPrivateData` — is the cause of every
"project appears to be damaged" on 2026-09-01.** The `VideoFilterComponent`
carries a 128-byte `tmul` struct of its own, **and Premiere also rewrites the Input-LUT path param
(pid 4) as an explicit sentinel instead of a self-closing tag**. A write that sets the params and
leaves that struct fresh parses as valid XML, and Premiere refuses it on open.
`grade-lut.py` captures `component_pfpd`, refuses a params file lacking it, and writes the verified
fresh-instance struct (`PFPD_FRESH_LUT`) rather than a donor's, warning when they differ.

⚠️ **VERSION-BOUND.** The captured params were minted on Premiere 26.3.2 and nothing checks the
running version. If an update changes the struct's layout, `apply` still reports success and the
project still opens while the grade renders NOTHING — the same silent signature as a poisoned Lumetri
or a muted track. On a new build, if a frame grab with the layer toggled does not move, suspect
`PFPD_FRESH_LUT` first and re-mint by hand-applying + `capture` there.

## The traps that make a write look like it worked

☠️ **Object IDs are NOT unique in a `.prproj`, and that will corrupt a project silently.** The tool
disambiguates every lookup by `ParameterID`, transplants only the `<StartKeyframeValue>` (never its
container), and refuses to write if the ObjectID/ObjectRef sets or component count change. **The
regression test is a byte-compare:** `strip` then `apply` on a copy must reproduce the file exactly.
**Never run it on a job project without a copy of the `.prproj` beside it.**

⚠️ **An EMPTY arb param is written self-closing** (`<StartKeyframeValue …/>`), a populated one as a
pair — and a freshly-added Lumetri is exactly the state you apply a LUT into. Match both forms.

☠️ **`BinaryHash` is VALIDATED, and a wrong one is discarded SILENTLY.** Two lines are all there is:
the low 32 bits are payload length + 12 (8 of 8 samples), and the 96-bit half is a proprietary digest
two exhaustive sweeps failed to identify —
**do not spend another session on it.** A stale, zeroed or absent hash makes Premiere discard the
value without a word: the effect loads, the UI shows `[Custom]`, nothing renders. Hence captured and
replayed verbatim, and hence one hand-application per new LUT.

☠️ **Do NOT write the Blob param through ExtendScript — it POISONS the instance.** The write reads
back byte-perfect and the effect then renders **nothing at all, not even `Exposure`**, so every later
test on it is a false negative (ES writes UTF-16; the blob must be UTF-8). Recovery: delete and
re-place the clip.

⚠️ **Always re-run a control before trusting a negative result: `Exposure` +2 must move mean RGB ~46
points.** A dead control means poisoned effect OR muted track — read the mute state first (step 3).

⚠️ **On a project holding more than one Lumetri, `grade-lut.py` needs the right `--which N`.**
Instances are indexed across the WHOLE file: resolve the index by walking the component to its
MasterClip name, never by guessing.

## Portability — the params travel, the path is a label

- **A `.lookparams` replays on any machine and `apply` never reads the cube** (2026-09-02): pid 98
  carries the whole cube, so a client ships a turnkey grade with no hand step.
- ☠️ **Premiere RE-RESOLVES the LUT on save and DROPS the embed**, rewriting the instance as a LINK to
  the baked path — dangling on any machine but the capture one. The params are hash-sealed, so the fix
  is to make the path TRUE: mint captures from `/Users/Shared/`, which `setup-premiere.sh` mirrors the
  cube library into on a client's first run.
- ☠️ **A hand-apply does not always EMBED the cube** and the Blob says `__Embed "1"` either way, so
  check pid 98 or let `capture` fail on its guard. Not a dead end: **pid 98 is a property of the CUBE,
  not of where it was browsed from**, so a valid one grafts in from an earlier capture.
- ☠️ **The path cannot be removed, redirected or looked up dynamically** — hash-sealed in pid 1 and
  pid 24, and the Blob is STRUCTURALLY REQUIRED (pid 98 is inert without it). The ONLY lever is where
  the cube is browsed from at mint time.
-

### Adjacent traps

- **`remove_effect_by_name` addresses the wrong clip.** Strip effects by deleting and re-placing it.
  Presets have no scripting entry point either (`applyPreset`/`attachPreset`/`importPresets` exist on
  nothing).
- **Premiere refuses the quit AppleEvent on this machine** (the locked-screen `open POSIX file` in § 2 still lands), so `--restart`/`--quit` quit through the bridge's
  ExtendScript `app.quit()` (~60-90s). Confirm with `lanes/premiere/premiere-pid.sh`, never a
  hand-typed `pgrep` (2026-09-02).
- **`Auto` cannot be pressed by script, but its result can be READ**: `Auto Tone Analytics Data` (ES
  prop 126) is a live JSON record of what Auto last computed, and every dial it drives is scriptable.
  ⚠️ Meaningful only when Auto was pressed on a footage CLIP.
- **Premiere is never the test harness for a new project-file write.** Opening a suspect `.prproj` pops a
  modal on the creator's screen and wedges the CEP bridge until it is clicked away. Diagnose offline: have
  the creator make the identical edit by hand once, diff Premiere's own save against the tool's write byte
  for byte, and open a suspect file at most once per hypothesis, saying first that a modal may appear.
-

## Verification discipline, in one list

Three failures present as "the grade does nothing", none distinguishable from a readback:

1. **Muted track** — read `videoTracks[i].isMuted()` FIRST; confirm grabs are live by moving V1.
2. **Poisoned Lumetri** (a Blob written through ES) — `Exposure` +2 fails to move the frame on an
   unmuted track. Recovery is delete and re-place the clip.
3. **Discarded payload** (stale `BinaryHash`, missing pid 98 or PFPD struct) — the project opens, the
   UI may show `[Custom]`, the frame does not move.

Never trust a readback or the effect panel, and never trust a negative result until Exposure has been
re-run on a track confirmed unmuted. Verify only from a program render with the layer toggled.

## There is no correction step, and Auto on the layer is noise (2026-09-01)

The rule belongs to the preset ([`presets/youtube/default/README.md`](../../presets/youtube/default/README.md)
§ Grade): the grade is the layer plus the Look, and nothing measures or corrects the footage first.
The Premiere fact behind it is above — `Auto Tone Analytics Data` is meaningless on an adjustment
layer, which has no pixels of its own, so Auto analyses its own blank synthetic media. Press Auto on a
footage CLIP if you want its opinion; on the layer it is noise.
