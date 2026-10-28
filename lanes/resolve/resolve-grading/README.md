# Color grading in DaVinci Resolve, from the API

Validated end to end 2026-08-06 on `your-job` (Resolve Studio 21.0.3.7): a custom
DCTL shader authored from scratch, applied to **9 timeline clips at once** through a color group,
verified by real render. Read this before any Resolve grading work — most of it is gotchas that
cost real time.

Companion files here: [`pastel_studio.dctl`](pastel_studio.dctl) (a working reference shader that
compiles on this machine — **a retired job look, kept only as a compile-clean DCTL dialect
reference**, not the house grade) and [`sim-grade.py`](sim-grade.py) (numpy port for previewing a
look without rendering; its constants have drifted from the shader, resync before trusting a
preview).

**The house look is a `.cube`, not this shader.** What the preset asks for on this lane and what is
validated: the `davinci-resolve` skill § Step 4. This file is the mechanism playbook underneath that,
including [the folded house cube](#the-house-look-folded-into-one-cube).

## The house look, folded into one cube

Lumetri's Look Intensity and Creative Saturation have no API equivalent, so they are baked into the
cube with [`workflows/fold-look.py`](../../../workflows/fold-look.py) (stdlib, either engine, any OS; the Final
Cut lane folds its Custom LUT with it too):

```bash
uv run workflows/fold-look.py assets/luts/rec709/Autumn-Rec709.cube --install autumn80-sat120 \
  --intensity 0.80 --saturation 1.20
```

`--install` finds Resolve's master LUT folder for the OS and writes `MCP/autumn80-sat120.cube` into it (parents
made; a folder you cannot write is named in the error), then prints the `MCP/autumn80-sat120.cube` path `SetLUT`
takes. macOS `/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT`, Linux `/opt/resolve/LUT`,
Windows `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\LUT` (writable by a standard user; proven on
Studio 21.1 2026-09-27: `SetLUT(1, 'MCP/autumn80-sat120.cube')` reads back `MCP\autumn80-sat120.cube`).

The numbers are the preset's (`presets/youtube/default/README.md` § Grade); the script's docstring holds
the math. Then, in-process: `project.RefreshLUTList()`, a colour group over the footage clips, and
`grp.GetPostClipNodeGraph().SetLUT(1, 'MCP/autumn80-sat120.cube')` (skill § Step 4 has the block).
Validated 2026-09-25 on a 2872-frame short: the render's footage mean RGB sat within 1–2 / 255 of the
Premiere master's Lumetri 80 / 120 on four frames. The official engine's `generate_lut` produced the same
file (max difference 1e-6), but it is sandboxed (no `open`, no `globals`), so evaluating an existing cube
means sending the whole cube inline in the call: fine from a script, impractical as a tool call. Keep
`generate_lut` for looks that are pure math.

**Official engine (`ResolveMCP`, Studio 21.1+):** `update_dctl` writes a DCTL straight into `LUT/MCP/`
and compiles it before writing; `SetLUT(1, 'MCP/<file>')` and the in-process `GetLUT(1)` readback run in
`run_script`.

## The shape of the job

1. **Measure the footage first.** Pull 4–5 frames spanning the range, compute mean RGB, shadow
   mean (darkest 10%), highlight mean, a face patch, median luma. Grade against numbers, not vibes
   — "it looks magenta" becomes "mean R .38 / G .30 / B .36, green .08 low, skin reads B above G."
2. **Design the look in numpy first** (`sim-grade.py`). A render round-trip is ~1 min; the sim is
   ~1 s and produces the same numbers if the math matches. Iterate there, lock the constants, then
   port to DCTL. On the reference job the sim predicted the rendered result within .01 on every
   channel.
3. **Author the DCTL** (`update_dctl`), apply it to a color group's post-clip node.
4. **Verify with a real render.** Never trust a readback.

## Grading many clips at once = a COLOR GROUP (this is Resolve's adjustment layer)

There is no "adjustment clip" in the scripting API, and you don't need one. A color group gives
every member clip one shared node graph.

```python
project.AddColorGroup('Intro Pastel')                     # project-level, not media pool
grp = [g for g in project.GetColorGroupsList() if g.GetName() == 'Intro Pastel'][0]
for it in intro_items:
    it.AssignToColorGroup(grp)                            # returns True per clip
grp.GetPostClipNodeGraph().SetLUT(1, 'MCP/pastel_studio_v3.dctl')
```

**The group API lives on `project`, NOT on the media pool** — `MediaPool` has zero color/group
methods; a `dir()` sweep for `olor|roup` on MediaPool returns `[]`. The group object exposes only:
`GetClipsInTimeline`, `GetName`, `SetName`, `GetPreClipNodeGraph`, `GetPostClipNodeGraph`.
There is no "remove all members" call — clear membership per clip.

Four grading levels, and picking the right one is the whole game:

| Level | Scope | Use for |
|---|---|---|
| **Clip** | that one clip | per-shot fixes |
| **Group Pre-Clip** | all members, BEFORE each clip's own grade | normalizing, input transforms, shot matching |
| **Group Post-Clip** | all members, AFTER each clip's grade | **the shared look — put the DCTL here** |
| **Timeline** | everything on the timeline, above all groups | a look over footage AND graphics tracks |

Note the last row: a group only covers its member clips. Graphics on V2 are NOT in the group and
stay ungraded. If a look should cover the whole program, that's the **Timeline** graph, a
deliberate choice to confirm rather than assume.

**UI equivalents** (the API cannot drive these — its entire UI surface is page switching plus
layout presets): create/assign groups by selecting clips in the Color page thumbnail strip →
right-click → *Add Into New Group* / *Add Into Current Group* / *Remove From Group*. Switch
grading level with the dropdown at the **top-right of the Node Editor** (reads `Clip` by default).
That dropdown is a hand-click; there is no scripting equivalent, so a session can set up a group
grade but cannot show it on screen.

## DCTL: what actually compiles

`Graph` has **no AddNode** — you cannot create serial nodes from the API (confirmed against the
live `graph_methods` list). So a multi-step look goes into ONE node, which means a DCTL. That is
not a real constraint: a single DCTL can hold curves, split-tone, rolloff, hue-selective work and
a vignette.

**Resolve's DCTL error is a bare modal — `Error Processing DaVinci CTL || <file>` — with NO
compiler diagnostic anywhere.** `ResolveDebug.txt` logs only the same one-line urgent message.
There is no line number, no message, nothing. Budget for that: it is a pass/fail signal only.

The MCP's `dctl validate` is a **stub** (`"checker": "minimal"`) and returns `valid: true` for
code Resolve rejects. Do not trust it.

Two checks that ARE worth running before touching Resolve, both instant:

```bash
# 1. syntax, via a clang shim that defines the DCTL macros (catches ordinary C errors)
clang -fsyntax-only -Wall -I. check.c

# 2. non-ASCII bytes in comments, which break the parser silently
LC_ALL=C grep -n '[^ -~]' the.dctl
```

Neither caught the real failure on the reference job, but both are free and rule out whole classes.

**Write DCTLs against Blackmagic's own samples, not from general GPU knowledge.** They ship at
`/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/DaVinciCTL/` on macOS
(`/opt/resolve/Developer/DaVinciCTL/` on a standard Linux install), with
`README.txt` carrying the authoritative supported-function list. `AlphaCircularWindow.dctl` and
`Matrix.dctl` are the two most useful references. The house style that compiles:

- `const float` locals **inside** `transform`, not file-scope `__CONSTANT__` scalars
- `_saturatef(x)` over `_clampf(x, 0.0f, 1.0f)`
- `_hypotf(dx, dy)` over `_sqrtf(dx*dx + dy*dy)`
- implicit int→float (`0.5f * p_Width`) over C-style casts
- no early `return` inside helpers — blend with `_mix` instead
- no scientific notation (`0.000001f`, not `1e-6f`)
- every float literal suffixed `f` (the README says this explicitly)

**Honest limit: which of the seven constructs Resolve actually rejected is UNKNOWN** (the rewrite that
compiled changed all seven at once; story in the archive). If the answer ever matters, bisect one construct at a
time; otherwise write in the house style above and move on.

`DEFINE_UI_PARAMS` sliders only exist when a DCTL runs as the **ResolveFX DCTL plugin**. Applied as
a node LUT there is no UI to feed them, so hardcode the constants. (`ClaudeSplitTone.dctl` proves
UI params don't by themselves break a node-LUT DCTL — but they buy nothing there either.)

## The retired community engine's traps (before 2026-10-05)

Its `dctl install` wrote the USER LUT dir and `graph set_lut` staged a COPY into `LUT/MCP/` that a re-install never
updated, so Resolve compiled the old file while every readback reported the new name; and its wrappers reported
their own record, not Resolve's (`graph get_lut` named a LUT where `GetLUT(1)` read `None`; `render start` returned
false on a render that ran). The official engine's `update_dctl` writes and compiles straight into `LUT/MCP/`, and
every readback goes through `run_script` against the real API objects. **Rule either way: confirm the look with a
rendered frame.** A grade that "reads correct" and renders ungraded is the default failure mode here.

## Verifying a grade

Render a 2-second range and measure it — that is the only proof.

```python
project.SetCurrentRenderFormatAndCodec('mp4', 'H264')
project.SetRenderSettings({'TargetDir': out, 'CustomName': 'check',
                           'MarkIn': 108100, 'MarkOut': 108160,   # ABSOLUTE timeline frames
                           'SelectAllFrames': False,
                           'FormatWidth': 1920, 'FormatHeight': 1080})
project.StartRendering([project.AddRenderJob()])
```

Then compare mean/shadow/median-luma against the ungraded source and against the numpy prediction
(on the reference job every number landed within .01 of the sim).

**Do not verify with `timeline_markers get_thumbnail_image`** — it returns the current clip's
frame, not the program composite, so it proves nothing about compositing. And when sampling a
finished render, check what's actually on screen at that timecode first: on the reference job a
45s sample read as "wildly wrong" because it landed on a full-frame graphic on V2, not footage.

## Teardown

Removing a group grade completely:

```python
grp.GetPostClipNodeGraph().SetLUT(1, '')     # '' clears; readback should be ''
grp.GetPreClipNodeGraph().SetLUT(1, '')      # diagnostics leave junk here — check it
for it in members: it.RemoveFromColorGroup()
project.DeleteColorGroup('Intro Pastel')
```

Then delete the DCTL copies under `LUT/MCP/` and clear the render queue.

**Probing leaves grades behind.** Diagnosing "is the LUT landing?" by calling `SetLUT` on the
pre-clip graph, the post-clip graph and an item's own node leaves the broken LUT on all three.
They compile-fail and pass through, so renders look correct and nothing flags it. Sweep every
level afterward, not just the one you meant to use.
