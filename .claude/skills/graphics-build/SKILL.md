---
name: graphics-build
description: "Owns the graphics BUILD (step 5b): from the job's graphics-plan.json through harness setup, asset prep and captures, one comp per cell, browser probe, part renders, placement on the finish surface (Premiere / Resolve / CapCut / Final Cut / chat-only) and first-pass QA, ending with every planned graphic placed. Carries the render gotchas and the part-split SOP. Does NOT decide graphics (graphics-plan) or do music/export; the short-form caption layer IS one of its graphics. Triggers: build the graphics, build the planned graphics, execute the graphics plan, graphics build, run the build, composite the graphics, place the graphics on the timeline."
---

# Graphics Build — from plan to placed graphics, one owner

**Step 5b of the pipeline.** `graphics-plan` decided everything; this skill EXECUTES it: every
`graphic:true` beat built exactly as storyboarded, rendered, and placed on the target surface.
Done = all planned graphics on the timeline (or composited, chat-only lane), a build report, and
nothing left for you but to watch it and call adjustments.

**The bar: one-shot fidelity.** The plan is the contract — build what it says, at the times it
says, with the copy it says, verbatim. A better idea at build time is a NOTE in the report, never
a silent change (same rule as the tier gate: escalation and deviation are your calls). If a
cell is unbuildable exactly as written (a timing that will not fit, a prop or effect that will not
render), build the closest faithful version and flag it `⚠️` in the report — don't stall, don't
redesign. A missing REQUIRED SOURCE is the exception: keep building the independent cells and
report that specific unresolved source, never a generic stand-in and never 'complete'. If a cell
conflicts with the original request or the preset, that is a plan defect — fix it in
`graphics-plan` before building; a plan cannot waive a requirement it forgot.

**Style comes from the plan's `preset` doc, and only that preset's docs.** Presets are independent;
never pull style from another preset's folder.

## The build loop — one graphic at a time, converged before the next (2026-08-29)

Stages 3–6 below run **PER GRAPHIC, in plan order**: author → probe → render → place → check the
real composite (program monitor / lane readback) → judge it against the plan cell, the preset
locks, and the Definition of Done → fix and re-render **until THAT graphic is right**, then move
to the next. Never park a known defect "for the review loop" — nothing broken moves forward.

**Effort scales with complexity.** A simple text animation: build, verify sync + layout, done —
minutes. A full-screen / punch-cut / multi-element graphic: expect multiple rounds (~10 min is
the working budget; the first generation of a complex graphic is usually NOT right — layout,
hierarchy, and arrow/prop craft take passes). Judge each round the way you would: placement,
sizing, balance, sync, readability — from the actual composite, not the comp render.

When every graphic has individually converged, Stage 7 runs the all-up QA and hands the draft to
the **final `edit-review` pass: the gate, ONE review round, the fixes, the gate again** —
it catches what only the full sequence shows (cross-graphic rhythm, boundary bleeds, variation
collisions); it is not a substitute for per-graphic convergence.

## Stage 0 — preconditions

- `projects/<job>/graphics-plan.json` exists. If not → stop, run `graphics-plan` first.
- The rough cut ran (canonical transcript + EDL exist). Frame-snapped splice ⇒ **plan times ARE
  timeline times** — anchor comps and placements to them directly, no offset hunting.
- If dialogue was cut, restored or appended after planning, reconcile the plan against the final transcript first. Rebuild coverage through the actual outro; previous QA applies only to unchanged windows.
- **Target surface** = the plan's `"compositor"` (`premiere` · `resolve` · `capcut` · `finalcut` · absent =
  chat-only HyperFrames finish). App lanes need their bridge/app available — ping first, per the
  app skill.

## Stage 1 — harness

Set up the durable generated build under **`projects/<job>/hf-graphics/`** (never `/tmp` — a full
day of build source was wiped by macOS's overnight `/tmp` clear once).

**Copy the harness the job's preset ships.** `presets/youtube/default` names the files and the
locked chains in its § Build (`default-overlay-style.md`) — copy those in rather than re-deriving
them. **On the Talking Head Explainer, `uv run presets/instagram/talking-head-explainer/kit/engine.py init
projects/<job>` replaces the hand copy:** it stages the reference `render.sh`, the kit, the fonts and a
`build.py` started from `kit/build.example.py` (the editor edits only its storyboard). On a preset that ships
neither, author `render.sh` from
[`presets/youtube/default/reference/fullscreen-render.sh`](../../../presets/youtube/default/reference/fullscreen-render.sh).
Copy the reference fresh at the start of every build. A job copy that has drifted is refreshed from the
reference (its FPS resolution, STEP_FPS expansion, placed guard and render record). **The alpha post pass
(GLOW / SCAN / SCAN_AMP / GRAIN) lives in the shared renderer as opt-in flags** (its header; the values per
family: [`talking-head-explainer/graphics.md`](../../../presets/instagram/talking-head-explainer/graphics.md)
§ 7), so a job no longer merges one, and the render record carries every flag in its `"env"` and its
re-render line. The old TRIM flag is retired: a re-cut rebuilds a scene from its word anchors.
Add `PROJECT.md` (the resume doc: write it now, update as you go, so any fresh session can pick up
mid-build). **Symlink `compositions/assets → ../assets` and `compositions/hf-anim.js → ../hf-anim.js`** (and
`compositions/hf-motion-blur.js → ../hf-motion-blur.js` when a comp loads the motion-blur component)**:**
every comp refers to `hf-anim.js` and `assets/…` by the bare names the renderer resolves against the
gfx root, and without the links the Stage-4 localhost probe 404s them from `compositions/` (fonts
fall back silently, the registry throws). Never a COPY there: a real file beside the comp loads ahead of the
gfx root's, so a fix to the root's never reaches the render (round 9's `hf-motion-blur.js` copies did that, 2026-10-06). **On Windows, Git Bash `ln -s` silently COPIES** (no symlink privilege, exit 0), so assets added later never reach `compositions/`: instead, from inside `compositions/`, run exactly `cmd //c "mklink /J assets ..\assets"` (a junction) and `cmd //c "mklink /H hf-anim.js ..\hf-anim.js"` (a hard link). The `//c`, the double quotes and the backslashes are all load-bearing: a single `/c` opens an idle cmd and exits 0 having made nothing, unquoted `/H` becomes a path, `../` is refused. mklink refuses a name that exists, so `rm -rf assets hf-anim.js` first (it removes a link, never its target). `stat -c %h hf-anim.js` must print 2: refresh the gfx-root `hf-anim.js` with `cp` (it writes through the link), since a Write-tool or `sed -i` rewrite splits the link silently and needs a re-link (2026-09-27). A job folder that is MOVED or COPIED needs both links made again: a junction keeps its absolute target and a copy turns it into a real folder and splits the hard link (the Talking Head Explainer kit's `init` re-links them itself, L32).

**THE REGISTRY AS CODE, non-negotiable:** every comp starts as a copy of
[`reference/comp-scaffold.html`](../../../presets/youtube/default/reference/comp-scaffold.html) and
loads **`hf-anim.js`** (copied into `hf-graphics/gfx/` from
[`presets/youtube/default/reference/hf-anim.js`](../../../presets/youtube/default/reference/hf-anim.js));
it declares its rate (`HF.init({fps, dur[, stepFps: 12]})`) and CALLS `pop`/`slam`/`riseIn`/`exit`/
`slideIn`/`slideOut`/`camera`/`float`/`arrow`/`countUp`/`reveal`. Helper blocks are NEVER re-typed
into a comp (2026-09-02: eleven
comps each re-typed them and each got a different subset wrong — nine of ten motion defects).
**A full-screen / punch-cut cell starts from the preset's shipped reference implementation instead of
the bare scaffold** — [`reference/punch-cut-text-light.html`](../../../presets/youtube/default/reference/punch-cut-text-light.html)
for a bg-light TEXT punch-cut, [`reference/punch-cut-reference.html`](../../../presets/youtube/default/reference/punch-cut-reference.html)
for a bg-dark artifact: the scaffold is the OVERLAY shape and carries none of the scene / `#racked` /
`camera()` structure `creative-moves.md` move 2 requires (and `graphics-qa.py`'s `dynamics` and `rack`
checks measure). The
presets that own it: `presets/youtube/default/animations.md` § The canonical block; enforced by
`workflows/graphics-qa.py`.

- On the long-form (youtube/default) **basic tier** (4–7 short cards) each card is its **own
  independent comp** — no shared timelines, no part-splitting; a tweak re-renders one ~2s comp.
  **A hand-written `build.py` emitter is for the split-part case only** (a long multi-scene graphic,
  below) — do not build one for a set of short independent cards. **The Talking Head Explainer is
  the exception:** its kit `build.py` is its data-driven emitter for every graphic, still one comp
  each, staged by `kit/engine.py init`
  ([`graphics.md`](../../../presets/instagram/talking-head-explainer/graphics.md) § 15).
- **Stale tracking (split-part builds only):** stamp `renders/<id>.sha` with the hash of the comp
  each render came from and give the emitter a `--stale` mode that diffs comp-hash vs stamp. On a
  set of independent card comps there is nothing to track — one comp, one render.
  Parts of a shared-timeline chain embed the whole timeline, so touching one shared element marks
  every part of the chain stale — the seam-coupling rule, enforced instead of memorized.

## Stage 2 — assets

Everything a cell needs, gathered before any comp is authored:

- **Generated motion clips** (`b-roll` / `motion-graphic` cells with no real footage) →
  generated with your AI-video tool of choice, into `projects/<job>/broll/`. Its style block comes from THIS preset only.
- **Own B-roll cells** (`broll_source`) are rendered already by `workflows/broll-place.py apply` (an
  opaque mp4 per cell, no comp): skip them in Stages 3-5; after a re-time run
  `uv run workflows/broll-place.py projects/<job> render`.
- **Screenshots / screen-recs** → a cell with `asset` names a file already in the job folder (a
  missing one is a `⚠️` in the report, not a guess). A cell with `capture` is RECORDED here, into
  `projects/<job>/assets/captures/<id>.{mp4,png}`, by source:
  · Public `url` → `node workflows/page-record.mjs <url> <out.mp4>
    --seconds N --scroll <px> --fps <the job's rate> [--dark] [--hide "<css>"]
    [--ready "<css>"] [--ready-gone "<css>"]` (a `.png` out = a still),
    a separate clean headless Chrome at 1920×1080@2x. **Pass `--ready` / `--ready-gone` whenever the
    cell's `capture` carries `ready` / `ready_gone`** (the two fields are the plan's, `graphics-plan`
    § THE CAPTURE GATE): readiness is asserted before anything is recorded, so a half-loaded page
    can never become a file. Verify the rendered page is the intended
    destination; a login or sales-page redirect is not evidence of a private community or lesson.
    **Any annotation over a capture** (a circle, an underline, a marker, the cited sentence marked as
    you say it, 2026-09-14) has its target rect MEASURED, never eyeballed, and the capture under it
    holds still: take the still with `--find "passage||passage" --rects <id>.json`:
    the passages' line boxes land in capture px, exact to the DOM, and the comp draws its marker over
    them; a passage the tool reports as not on the page is quoted from a summary, not the page — take
    the wording off the page text. A news page with sidebars reflows to one column at `--width 1100`
    (the comp reads the capture's viewport from the json); what will not hide, zoom past.
  · A page behind a login → an `app` capture of the signed-in browser: `FPS=<the job's rate>
    ./workflows/screen-record.sh <Browser> <out.mp4> <seconds>` in the background (a still =
    `window-grab.sh`), driving the plan's `action` during the take. Full-screen the window (or
    frame the chrome out in the comp) so tabs and toolbars stay out of shot; verify the recorded
    page is the real destination — a login or sales-page redirect is not evidence. If the page
    cannot be reached, report that exact gap; never capture the redirect.
  · `app` → a still = `./workflows/window-grab.sh <App> <out.png>` (reads a covered window's own
    buffer, never fronts anything); a recording = `FPS=<the job's rate> ./workflows/screen-record.sh <App> <out.mp4>
    <seconds> [index]` **run in the background** — video cannot read a covered window (`screencapture -v`
    ignores the window id, measured 2026-09-11; on Windows ffmpeg's gdigrab reads the screen, the same
    limit), so it fronts the app for the take: start it, wait ~1 s, drive the plan's `action` (a click,
    the timeline filling) with the computer-use tools, let it stop by itself, and say in the report that
    the app was fronted. Both scripts run on macOS and Windows with the same flags and exit codes (the
    Windows backend is `workflows/wincap.py`, 2026-09-27).
  · **The Screen Studio route** (`VE_SCREEN_RECORDER=screen-studio` in the repo-root `.env`; `graphics-plan`
    § THE CAPTURE GATE): a recording cell is a TAKE FILE, `assets/captures/<id>.take.json`, run from the job folder
    by `node workflows/screen-studio-take.mjs assets/captures/<id>.take.json assets/captures/<id>.mp4 --fps <the
    job's rate> --height <the master's height> --preflight pii.json`. Its schema is the script's header: the
    `window` a `setup` staged (its size unique among that app's windows, or the take refuses; a public page is a
    `url` opened in a clean chromeless Chrome on a throwaway profile), `steps` (`workflows/glide.swift` cursor
    moves at coordinates MEASURED off a grab of the staged window, plus `run:` commands and `mark:` names), and
    `zooms` between marks (in on the approach, out on the reveal). The steps run as long as the cell and a
    trailing `wait` holds the last frame; a cursor that holds still rests on a neutral area (parked on a link it
    pops the page's hover tooltip and a URL bar into the shot). The tool records through Screen Studio's
    deeplinks, edits the project and exports with no save panel, and refuses an unknown or duplicated window.
    - **Chrome takes.** An agent driving Chrome (Claude in Chrome) works in its OWN tab, in the background: a take
      of the front tab records a still page for its whole length (2026-10-15), so the take's `setup` fronts the
      agent's tab (`set active tab index`), and a `display` window records it without resizing anything the agent
      is using. A setup that opens its own Chrome window holds its reference (`set w to make new window`, then
      `set URL of active tab of w`, `set bounds of w`), never `front window`: right after `make new window` the
      front window can still be the user's own, which the teardown then moves, resizes and closes (your 9-tab
      window, 2026-10-15). A teardown closes by its own bounds AND tab count, never by position alone. On Screen
      Studio 4.0.4 the window picker failed four takes running (`url` and `app` windows alike) while `display`
      mode with a `crop` on the window's rect recorded first time: prefer it there.
    - **A zoom onto a figure is never Screen Studio's own** (it clamps its camera at the window's edge and swings,
      and 4.0.4 renders its motion-blurred zoom frames about 10 luma levels brighter than the settled ones): export
      the take with NO zoom at full resolution, bake any highlighter on that export, and render the push with
      `uv run workflows/zoom-to-rect.py <no-zoom take> --page <the page's rect> --target <the figure's rect> --margin <the
      captures.md § 3 margin> --src-start <the shot's first frame> --frames <the shot's length> -o assets/captures/<id>-panel.mp4`
      (the page fills the panel on frame 0, then a straight, geometric, motion-blurred push from frame 1 over 12
      frames; a ⚠ that the view runs past the page means another target, zoom or anchor, never a clamp). Stage the
      output like any take (2026-10-15).
    - **A document whose editor steps its own scroll** (Google Docs moves a smooth scroll every few frames, so a
      recorded scroll stutters): record still holds (`pscroll` steps), stitch them into one tall page (each hold's
      viewport below the toolbar and above any floating button, the shifts measured between holds), and let the
      kit's doc-scroll recipe pan it. Open it in a NEW window of its own and close that window after (2026-10-15).
    - **A window with something floating over it that is not ours to close** (a meeting recorder's widget, a
      dictation bar): capture that window's own pixels as a still, `screencapture -l <window id> -o <file>.png`
      (nothing fronted, moved or overlaid), and loop it into an mp4 for the kit's fill sampler (2026-10-15).
    - **The output.** `<id>.provenance.json` lands beside the mp4 and the Screen Studio project stays for a hand
      tweak. The mp4 IS the cell's finished render: copy it to `hf-graphics/gfx/renders/<id>.mp4`, the full-screen
      render the placer picks; no comp is authored around it. A take TRIMMED into a cell (a source in-point, or a
      cell longer than the take) plays only up to its LAST SETTLED frame and holds that: every take ends on Screen
      Studio's automatic zoom-out, which EASES in (its first frame moves about a fifth as much as the later ones),
      so the take's own last frame is ghosted and a cut back to camera inside the zoom-out doubles the text. Find
      the settled end by frame differencing with a low threshold and a frame of margin, and prove the held frame is
      sharp against the take (a 0.6 threshold on a 240 px grey diff held the first ghosted frame on seven cells,
      2026-10-02). Start a trimmed cell past anything the take opens on before its zoom lands: Claude's Sessions
      row (a GitHub handle and repo), Chrome's page-zoom bubble.
    - **The take is live.** The cursor moves and the app is fronted, so say so in the report; anything dictated
      during the take types into the recorded app. A page that needs a zoom or a find before the trim runs those
      keys as `prelude`; anything private that must cross the frame is blurred by `masks` (screen rects between two
      marks). A take in the Claude desktop app collapses its sidebar first (session titles), never presses Return
      in the composer, and empties it afterwards.
    - **A take zooms only when it has something to show (2026-10-04: "too much unnecessary movement is just
      unnecessary").** It opens STATIC, at level 1 or an `instant` framing of the page, and makes ONE zoom straight
      to the thing the line is about: never stepping there (the row, then the item), never drifting toward the
      centre with no target (the 1.2x "push" on a doc), never starting in the last second before its cut (hold the
      static frame) nor in its FIRST second (the viewer reads the whole page for about a second first: i04's take
      source in moved so about 1 s of the static page plays and the zoom lands on its word, you 2026-10-04). A
      second zoom is for a second thing: a cursor walking a list, a prompt typed after a page is shown. **Never open
      on an `instant` zoom that another zoom follows:** Screen Studio then SNAPS into the next zoom as well, a hard
      cut (six recordings, 2026-10-04); to open on a framing the first zoom starts 2 s before the clip (the tool
      converts an `instant` opening zoom itself), settles before frame 0, and the next zoom eases. Prove it by frame
      differencing across the zoom: an eased zoom changes over 15–20 frames, a cut in one.
    - **Aiming a zoom** (`rect` / `focus` / `x`,`y`; `level` or `fill`; `follow`; `instant` + `lead_in`: the header):
      a typed prompt is a `fill` 0.65–0.7 on the composer with `"padding": 0.4` (the camera clamps near the
      recording's edges, and the wider margin lets a bottom-edge composer centre). `--reexport <old provenance>
      <zooms.json> <out>` re-renders a take with new zooms and no re-recording: reach for it whenever only the
      framing changes.
    - **A DISPLAY crop**, `"window": {"display": 1, "crop": [...], "front": "App"}`, records a take that spans
      several windows or an app that draws translucent (the Claude app showed the wallpaper through a window take).
      A page that needs the creator's SIGNED-IN browser or its extensions (a members-only community post, vidIQ's
      outlier score on YouTube: the throwaway profile shows neither) is a display crop over your own Chrome
      (2026-10-04), staged by Claude in Chrome first:
      - navigate, scroll, collapse YouTube's guide (your subscriptions), mute the video and turn its captions off;
      - read the viewport's screen rect off the page (x `screenX`, y `screenY + outerHeight - innerHeight`, w × h
        `innerWidth` × `innerHeight`) and crop to exactly that, so your other tabs and bookmarks stay out of the shot.
        That reading INCLUDES Claude in Chrome's "debugging this browser" bar (about 55 pt), which usually goes once
        its tools detach, before the take runs: the page then sits about 55 pt higher than measured (four zooms aimed
        off the measurement landed low, 2026-10-04);
      - `setup` fronts that tab with an osascript `set active tab index`;
      - aim the zooms by `rect` from `getBoundingClientRect()` plus that offset, then PROVE the aim on the export: OCR
        the final frame, put the target's centre within about 60 px of the frame's (character share for a phrase
        inside a line), and correct with `--reexport` (about 4–6 px per point at a `fill` around 0.4 on a 400 pt
        rect). A target near the page edge needs `"padding": 0.4` before the camera can centre it;
      - park the cursor off every tile, because a hovered YouTube thumbnail plays its preview.
  **After EVERY capture — recorded now, or an `asset` reused out of existing footage — grab a mid
  frame and read it against the cell's `shows` BEFORE authoring the comp, and say so in the report.**
  A spinner over a blank page shipped as a graphic because nothing ever looked at the frame; the take
  is redone, never cropped around (`graphics-plan` § THE CAPTURE GATE; `edit-review` class 1k reads it
  again on the render).
  All recordings must finish as a CONSTANT-rate mp4 at the rate you pass (default 29.97; a 24/25 fps job MUST pass
  its own, `FPS=` / `--fps`). Copy the file into `hf-graphics/gfx/assets/captures/` (the render
  base, reachable from `compositions/` through the Stage-1 symlinks). A page records at 2x
  (3840×2160) and a Retina window at 2x its point size, which is what a screen-recording-heavy job's
  4K master wants (preset README § Resolution). The capture is scaled and framed INSIDE the comp
  to `default-overlay-style.md` § SCREEN-REC SCENES (straight frame, the label and arrow on the
  label's side, bg-light), never parked full-frame. Text is never captured: a prompt, command or
  quote is rebuilt verbatim from its written source (`graphics-plan` § THE CAPTURE GATE; a narrated
  prompt walkthrough: `creative-moves.md` 4d).
- **Fonts** → copy the font files the comps' `@font-face` names into the render root's `assets/`
  (`hf-graphics/gfx/assets/<file>`, where `comp-scaffold.html`'s `src` points; text-animation keeps its own
  root) and `@font-face` them (headless render needs the file; a system name silently falls back).
  `graphics-qa.py`'s `font` check FAILs a `src` that is not there. Locate a font by
  listing the font dirs BY NAME — macOS `~/Library/Fonts`, `/Library/Fonts`, `/System/Library/Fonts`
  (Adobe Fonts under `~/Library/Application Support/Adobe/CoreSync/plugins/livetype/`); Windows
  `C:/Windows/Fonts`; Linux `/usr/share/fonts`, `~/.local/share/fonts` — never a recursive glob
  over the whole library folder. On macOS that walk crosses every app's sandbox container and the
  OS answers with the "access data from other apps" modal, which stalls an unattended run until
  someone clicks it (2026-09-13).
- **The Talking Head Explainer's footage framing:** `uv run workflows/face-frame.py projects/<job> --modes
  --collar --plan projects/<job>` (EDL mode: the raw's kept spans only, the collar read on the layout's W/O/T spans;
  on a multi-clip job once per `raw/<clip>` it names), then
  `--crown A B` per O span, then the lane's layout keys ([`LANES.md`](../../../LANES.md) § step 5′; Premiere
  `uv run lanes/premiere/layout-keys.py projects/<job> --apply`, then `--verify`). The transforms and why they
  are measured: [`layout.md`](../../../presets/instagram/talking-head-explainer/layout.md) § 2 and § 9. The split
  spans are proven on the program with `face-frame.py --verify <program> --plan projects/<job>`.
- **Staging a live take (every preset; the Talking Head Explainer's
  [`captures.md`](../../../presets/instagram/talking-head-explainer/captures.md) § 11 carries the story).** A take on
  the creator's own accounts is real, so before it:
  · confirm with you that a real send or call is fine, on those accounts, before the first one;
  · pre-roll only public-fact questions or bare acknowledgements until the staging leaves the WINDOW, and never type a
    stage direction or an actionable sentence into a filmed chat (the agent acts on it);
  · read every reply for side effects, and record every artifact the take created (a booking, a task, a sent
    message) with its undo, in RUN.md;
  · restore your window, zoom and tab afterwards; decline every sign-in prompt;
  · crop or mask sensitive rows in the asset FILE, never only in the comp; a placeholder is the same shape as what
    it replaces, and every placeholder is listed at handoff;
  · remove a rejected take from the render base (a rejected file that a comp can still find ships), and make
    all-intra copies for the render base (a long-GOP capture seeks slow and can decode late at a jump cut). On the
    Talking Head Explainer the copy is `uv run presets/instagram/talking-head-explainer/kit/engine.py stage
    projects/<job> <id> <take>` (its graphics.md § 15 step 2). It refuses to overwrite, so a rejected take is moved
    aside by hand (the original, its base and `<base>.stage.json`) before the new one is staged.
- **A highlight on a recording render** (2026-10-06: the yellow highlighter on a phrase, the red box drawn
  clockwise round a stat): TRACK it by registration, never OCR, off the PLACED render: measure the box on one settled
  frame, then `uv run workflows/track-region.py <render.mp4> --ref <frame> --box x0,y0,x1,y1 --from <frame> --to <frame> --out <track.json>`
  (the recording's own scale + offset, so the box never changes shape). The marker is BAKED from the render
  (`presets/youtube/default/highlight/bake.py`, frame-locked to it); the box is a comp (`highlight/box.py`, rendered
  alpha). Both lay with a NORMAL blend. A recording that is re-rendered (a new source in, a re-timed span) is re-tracked
  and the marker re-baked. The looks and the steps: [`presets/youtube/default/highlight/`](../../../presets/youtube/default/highlight/README.md).
- **A graphic that tracks a HAND:** `uv run workflows/hand-track.py <video> [--out track.json]` —
  it follows the PALM CENTROID, never a fingertip. A tracked graphic may span only a continuous RAW
  run of the track (no interpolating across a dropout), and the path is **baked into the render**,
  never authored as editor keyframes. Smooth twice (the tracker's `--smooth 7`, then again in the
  build), and re-time a tracked graphic by changing its frame range and re-rendering, never by
  sliding the clip: the render is pinned to its footage window.
- **A graphic that tracks a FACE or OBJECT a detector cannot hold (a film/CGI character, a prop through
  a flash; 2026-09-28):** `uv run workflows/object-track.py <plate> --regions regions.json --preview <dir>`
  (its docstring holds the method, the regions format and the output: one region per pose, `blind`
  spans, a chain that loses its region stops and the graphic spans only what it reached). MediaPipe
  held Thanos's face on 4 of 67 frames, the chains on every one. Look at the preview before building
  on the track. The rest of that build stays job-local; its method:
  - **Anchors** are measured on each region's reference frame (landmarks on the one frame the detector
    holds, a colour blob, or by eye off a still) and carried to every frame through the region's `m`.
    A small glowing object moving on its own (a stone in fingers) is not a region: its path is the
    centroid of its bright hue blob, searched in a window round the last position.
  - **The render** bakes the plate's timeline Motion (at Scale 135 about the centre, every source
    position maps to `c + 1.35 (x − c)`) and is laid at Scale 100, frame-exact to the plate clip,
    straight-alpha ProRes 4444. Motion blur samples between the previous and the current UNIQUE pose
    (a doubled frame repeats one), and through a flash each element is washed toward warm white by
    the plate's local luma rise over its clean baseline, so it burns out with the plate.
  - **The creator's face on the subject** is a die-cut head sticker from a remove-background cutout,
    cut with face landmarks: along the jawline, running out sideways at ear-lobe height past each
    jaw angle (the ears stay, a collar or chair rail goes); on a turned head the far cheek follows
    the matte's own edge, since the landmarks guess the far jaw inside the face. Light wall left
    between hair strands (above the brows, bright and neutral) is cut, the matte's soft edge is
    refilled from the solid head just inside it, and a second photo is colour-matched to the first
    on skin LAB mean and spread (face oval, eyes and mouth out). Flip it to face the way the
    subject's head faces, normalise eye-to-chin, place it by mapping its eye-mid and chin onto the
    subject's, then tune scale, drop and turn by eye.
- **A still of the creator inside a graphic (a player window, a thumbnail, a footage still):** the
  plan cell's `hero_frame` file, cast by `uv run workflows/hero-frame.py projects/<job> --id <id>`
  (the sheet, picked BY EYE) and `--pick <t>` (the full-res extract + `review/hero-frames/<id>.pick.json`),
  copied into `hf-graphics/gfx/assets/` under the same name. Never `ffmpeg -ss` at a word, never a
  `plan-frames/` grab: a frame taken where a beat starts is a mid-word face (`graphics-plan` § THE
  HERO-FRAME GATE, 2026-09-13). `graphics-qa.py`'s `hero` check holds the comp's `<img>` to the cast file.
- **Long-form, any overlay that shares the frame with your face:** measure the chin line first —
  `uv run workflows/chin-line.py <base-cut>` — and build every under-the-face comp inside the
  band it prints (`presets/youtube/default/default-overlay-style.md` § THE LOW BAND). The
  text-animation builder takes it as `TOP_MIN`; hand-authored comps put it in a header comment. A
  stack too tall for the band scales down WHOLE — never push past the floor to keep type big.
  On an app-finish job (`RENDER=0`, no flat cut exists), point `chin-line.py` at the RAW main
  take — it samples frames, so killed regions only add samples and the floor stays conservative.
- **Motion blur (2026-09-10): a timeline-rate comp that slides, moves its camera or pops something large renders with `MBLUR=1 MBLUR_SS=8 MBLUR_SHUTTER=5`** (the registry's smear is already in the comp; the supersample is the other half — `creative-moves.md` 4b). Never on a `STEP_FPS=12` render.
- **A side callout is built to the zone `chin-line.py --edl` prints for ITS window** (x80 → head−60
  on the left, head+60 → x1840 on the right, `--step 0.1` so the worst frame is in the sweep): the
  card is as wide as the room (cap 620) and its inner widths follow, never the fixed 620 box; the
  plan cell's `head` is the number `graphics-qa.py`'s `face` check holds the render to (preset
  § SIDE CALLOUTS, you 2026-09-10).

## Stage 3 — author the comps

- **Name the sound the situation wants while you author (2026-09-10).** The SFX map is the default; when an element SHOWS something the map's mechanical sound does not tell — a recording starting, a message landing, a finished state, a sale — put `data-sfx="<event>"` on that element, naming an event DOCUMENTED in `sfx.json` and nothing else (`presets/youtube/default/sfx.md` § Sound follows MEANING: an undocumented file cannot be heard, so it is never placed), and step 6 hears it. A green completion state rings the bell on its own.

One comp per storyboard cell, straight from the plan: the cell's `template` from the preset doc
(an older plan may carry only `kind` + `content` — derive the template from those and note it),
its `copy` **verbatim** (never paraphrase on-screen words), its `region`/side, its motion note.
Timing: comp durations and placement times come from the cell's `start`/`end` — word-snapped
already, don't re-time. The preset doc's CSS/tokens are the lock; design freedom lives INSIDE the
template, not around it. HyperFrames authoring detail → the `hyperframes-core` / `-animation` /
`-keyframes` skills.

- **Edit comp and `build.py` source with exact-anchor edits, never shell-heredoc string surgery.**
  One `python3 - <<'PYEOF'` pass over a builder wrote a literal backspace byte where `\b` was meant
  (its new build guard matched nothing and **passed everything silently**), deleted a whole definition
  between two splice anchors, and no-op'd two replaces an earlier pass had already moved. An anchored
  edit fails loudly when its anchor is gone. A genuinely bulk pass is a real script file that `assert`s
  every anchor, then a **grep for survivors of the old pattern before rendering** (a regex that cannot
  span nested parens converts only the easy cases: a "fixed" pivot bug survived a render cycle so).

**The four authoring traps that cost a whole extra build round (2026-09-19, five parallel builders,
every one of them shipping at least one).** They all render *silently* — no error, no lint, and the
comp probe only catches them if you are already looking:

- **An element that must paint OUTSIDE a box is a SIBLING of that box, never a child, and a wrapper
  holding a negative-inset overdraw (scrim, dim, glow, vignette) never carries `overflow:hidden`** —
  the clip is silent, so the element renders at opacity 1 and is simply not there (a FREE stamp
  meant to hang off a window corner, clipped away inside it), and a starved `inset:-60px` overdraw
  leaves the frame edges undarkened. The glow case and how to measure it:
  [`default-overlay-style.md`](../../../presets/youtube/default/default-overlay-style.md) § THE PROP GLOW.
  Gate: `graphics-qa.py`'s `source:clip` fails the fully-clipped case.
- **Under `white-space:pre` the newlines and indentation BETWEEN sibling rows are text nodes** that
  take a line box each: author the rows on ONE source line, or the container triples in height and
  its last rows clip away invisibly (a terminal lost 3 of its 8 lines that way). Gate: `source:pre-rows`.
- **A reserved slot is `visibility:hidden` or an absolutely-positioned box, never an inline
  `opacity:0` element** — invisible still takes its line box and breaks the line it sits in.
- **Every element starting at CSS `opacity:0` needs an entrance call, and a `slideIn` with no
  explicit `dist` travels the element WHOLE off frame** (`hf-anim.js` § `extent`): on a
  near-full-frame first element that IS the blank-lead-frames defect. Gate: `source:unlit` fails an
  `opacity:0` element no script ever names. Pass a short explicit `dist`
  or rise it — [`animations.md`](../../../presets/youtube/default/animations.md) § A full-screen
  graphic's entrance starts on FRAME 0.

### Long graphics ship as split part clips (LOCKED SOP — 2026-07-21)

Render time is **linear in comp duration** and a tweak re-renders the whole comp, so a long
multi-scene graphic (one grew to 19s ≈ 85s + 1.5 GB per tweak) ships as **short part clips,
butt-joined** — adjacent clips on the app timeline, or adjacent segments in the chat-only
composite. Split even when scenes flow continuously; split on a transition if that's where the
cut wants to be — the seam just has to frame-match.

- **Persistent state belongs in the initial CSS.** A carried prompt highlight or other settled
  state must exist before GSAP runs; a zero-time `tl.set` can rewind during seek-render and flash
  the unhighlighted baseline. Keep initial CSS and timeline state consistent.
- **Frame-match by construction:** ONE shared timeline for the whole graphic in `build.py`; emit
  each part with a start offset — `emit("g2", durA, ...)` + `emit("g2b", durB, ..., t0=durA)`.
  The emit template wraps `tl` in a shim that shifts every position by `−t0` and collapses any
  set/tween ending before the seam into its END state at time 0 — part N+1's first frame IS part
  N's last frame, pixel-identical. (GSAP note: `master.add(tl, -t0)` does NOT work — negative
  positions get clamped; the shim is the way.)
- **Cut on exact frame counts:** part durations = `k * 1001/24000` (23.976) so clips butt-join on
  the frame grid with no gap or overlap.
- **Coupling rule:** a change visible at the seam = re-render BOTH adjacent parts; a change
  contained inside one part = that part only (`--stale` enforces this).
- **Motion THROUGH a seam = per-frame `tl.set`s on FRAME-INTEGER times** — a `.to()` straddling
  the seam gets clamped by the shim. Compute each set's time as `frameIndex * 1001/24000 - 0.0005`
  (the guard keeps every set safely before its frame sample in BOTH parts; a rounded decimal base
  lands one part a frame late → a double-step stutter exactly at the seam). Verify a mid-motion
  seam by measuring the moving element across the 4 frames spanning the join (smooth easing
  steps), never by diffing the two seam frames (adjacent real-motion frames SHOULD differ).
- **Grain is free at seams:** grain flicker alternates every few frames anyway, so the grain-phase
  flip at a seam is invisible (and defeats the renderer's static-frame dedup).
- **Native seam proof:** after placement inspect the last outgoing frame and the first THREE
  incoming frames at every split, plus the motion samples above. Check persistent highlights,
  background and text continuity; a midpoint frame or contiguous clip bounds cannot prove this.
- **Premiere side:** each part = its own project item + clip (per-part `refreshMedia`); baked
  Transform keys live on the part that plays them.

## Stage 4 — probe before render

**Rendering to find out whether a comp works is the most expensive habit in this pipeline** — a
part render is 1.5–3.5 min; seeking the paused timeline in the Browser pane is one tool call.
**Serve over localhost, never `file://` (2026-08-29):** the Browser pane pins a `file://` comp to a
static `data:` snapshot — relative assets (images, fonts) 404 silently and rect coordinates come
back scaled/garbage, which reads as a layout bug that isn't there. Start the repo's `probe`
server (Claude Code: `.claude/launch.json`, `preview_start {name: "probe"}`, a static server on
8123 rooted at the repo). Claude opens
`http://localhost:8123/projects/<job>/hf-graphics/<folder>/compositions/<id>.html`. Use the browser's documented viewport API
(`resize_window` in Claude) to capture the native 1920×1080 composition. Then measure MECHANICS: positions, pivots, whether a
tween fired, whether frame 0 is the settled seam state, and on a full-screen the COMPOSED row's centre
(the union rect of a line's words AND the prop beside them at the fullest frame, against x 960 —
`creative-moves.md` move 2 § CENTRED MEANS THE COMPOSED ROW; `graphics-qa.py`'s `centre` check
repeats it on the render):

```js
(() => { const t = window.__timelines.main, o = {};
  [8, 24, 50, 80].forEach(f => { t.seek(f * 1001 / 30000);          // fps of THIS job
    const e = document.getElementById('gear1'), b = e.getBoundingClientRect();
    o['f'+f] = [Math.round(b.x + b.width/2), Math.round(b.y + b.height/2), e.getAttribute('transform')];
  }); return o; })()
```

The failures this catches are invisible in a contact sheet: a wrongly-pivoted element still
animates, it just orbits, so the sheet reads as "odd design" rather than "bug". Two traps:
**`seek(0)` when the timeline is already at 0 is a no-op** (seek away and back), and
`location.reload()` inside a probe kills the execution context (re-`navigate` with `force: true`).
When seeking through `page.evaluate`, use a block returning no value: `t => { window.__timelines.main.seek(t); }`. Returning a paused GSAP timeline returns a thenable and can hang the probe.

**Shape the probe so it RULES CANDIDATES OUT.** When something comes out wrong, the next action is
ONE measurement that discriminates between the candidate causes — never a patch based on the
likeliest one. Run every candidate in the SAME call, on the same element, and compare the readbacks
(`svgOrigin` vs `transformOrigin` vs the untouched attribute, each read back through
`getBoundingClientRect()`); three guessed pivot fixes with a render between each burned ~15 min on a
bug one three-line probe settled in a single call. The same shape holds off the comps: a readback
that cannot separate two causes is not a check — frame 9 alone does not tell an `inout` bake from a
linear one (§ Stage 7, 3f). **And when a check passes while the symptom persists, suspect the
check** — print what actually ran (`inspect.getsource`, `repr()` of the generated string, `grep` the
emitted file) before touching the subject again.

**Scope: mechanics on new or structural work.** Second-pass nudges skip self-QA (Stage 7, item 4).

## Stage 5 — render

Part-by-part via the harness scripts, at the base footage's fps, `-q standard` (the part render
IS final quality — no separate "final render" step):

- **Overlays** (cards, text animations, enacting overlays — anything that composites over
  footage) → **alpha ProRes 4444, straight alpha** on every app lane; never premultiply.
- **Full-screen GRAPHICS** (punch-cut graphics — anything that REPLACES the frame) → **opaque mp4
  with the film-grain pass baked**, via `render.sh <id> full` (the reference renderer's `full`
  mode does grain + libx264 crf 14 in one chain). bg-DARK full-screens add `STEP_FPS=12` AND the
  glow pass; bg-LIGHT gets neither.
- **Section title cards** → the preset's own `titles/render.sh` **unmodified** (its signature is
  `render.sh [id ...]` — there is no mode argument, and it bakes NO grain, by design). Don't route
  them through the full-screen chain.
- **CapCut lane only** → premultiply every alpha mov (CapCut reads 4444 as premultiplied; straight
  renders blow out soft pixels).
- **Re-renders get a NEW versioned filename** — overwriting a placed file half-stales Premiere's
  frame index (random transparent frames) and CapCut silently serves the old file. **The render
  scripts enforce it:** each one refuses an output path that appears in `../placement.json` and
  exits 2, so a refusal means that file is already on the timeline — re-run with `VER=<next letter>`.
  (A builder re-rendered over a placed file anyway in 2026-09-19; it was caught only by diffing
  render mtimes against `placement.json`.) The placer ranks versions WITHIN a name series by name
  (bare < b < … < z; v2 < v2a < v3 …) and BETWEEN the letter series and the v series by render time, so
  stay on `VER=<next unused letter>`; a v series is fine, but it ranks against letters by when it was
  rendered. Never clone a render to another version name: two series tops written under a minute apart
  are treated as a copy and ranked by name, with a ⚠. Copy renders only with their mtimes kept
  (`rsync -a`, `cp -p`, Finder). `place-graphics.py --plan` names every pick, and `--verify` prints
  `⚠ STALE PICK` when a placed file is not the newest version on disk.

### Render gotchas (learned, don't relearn)

- **Pin the CLI version in every render script.** A bare `npx hyperframes` floats to whatever
  shipped last (the 0.7.42 contract break landed mid-job exactly this way). Every render script —
  the copied `render.sh`, and any emitter — calls `npx hyperframes@<tested version>`: currently `0.8.105` for new jobs
  (validated 2026-10-01; HELD there: 0.8.112+ draws colour-fringed LCD-subpixel text on Windows and keeps an alpha comp
  root's own background, and 0.8.153 prints a red "No composition found" on every render; every bump: the engineering archive).
  Jobs already rendering on an older pin keep it. Bump deliberately: edit, re-render one part, review, adopt.
  **Every other hyperframes command runs on that pin too** (`check`, `lint`, `snapshot`, `timeline`, `preview`): the
  vendored skills' bare `npx hyperframes` means `npx -y hyperframes@<the pin in the job's render.sh>`, or the check
  runs on another engine than the render (and downloads it mid-job). Never add a `package.json` to `hf-graphics/`: it
  arms the vendored `hyperframes upgrade`, which rewrites every `render.sh` pin to latest.
- **The npm side is frozen with the pin (2026-10-13).** The pin is exact but its npm dependencies are ranges, so a
  fresh npx cache resolved whatever had shipped since (puppeteer-core 25.13.0 where the pin was validated on
  25.12.0). Every render script runs npx with `npm_config_before="$HF_BEFORE"`, set beside the pin, which rebuilds
  the validated tree exactly; a hand command does the same:
  `npm_config_before=2026-10-01T23:59:59Z npx -y hyperframes@0.8.105 check`. A full timestamp, never a bare date (npm
  reads a bare date as its midnight UTC, before the pin itself was published: ETARGET). An npx cache that already holds
  the pin keeps the tree it resolved then (npx never re-resolves an exact pin), so `setup.sh` removes that tree once
  per freeze and rebuilds it frozen (`.setup-npx-frozen`). A bump moves the pin and HF_BEFORE
  together (the validation day); `workflows/test_hyperframes_pin.py` holds every spelling to `setup.sh`'s.
- **Reproduce a render from its record, never from session transcripts.** Every `render.sh` render
  writes `renders/<file>.render.json` beside the file: FPS and where it came from, STEP_FPS,
  MBLUR / MBLUR_SS / MBLUR_SHUTTER, VER, the hyperframes pin, the date, and a `re-render` line that
  reproduces it when run from the gfx folder. Re-rendering a PLACED file: run that line with the next
  unused VER (the placed guard refuses the old name).
- **Panels must read on their OWN fill.** An isolated alpha render has nothing behind it, so
  `backdrop-filter` does nothing — design opaque-bright surfaces, never live backdrop blur.
- **Match fps to the base** (`--fps 24000/1001` for 23.976 footage) or overlays drift. `render.sh` takes
  it from the job when FPS is unset: `graphics-plan.json` `"fps"` (the sequence rate), else the first raw
  video, else 30000/1001 with a ⚠; `FPS=` still overrides, and a rate that is not an integer or N/D is
  refused before rendering. A `STEP_FPS=12` render is held back up to that rate and capped at the comp's
  own span, so a stepped overlay lands on the same frame count as a timeline-rate render of that comp.
- **Size an icon PNG by its SOLID body, and measure paired icons IN THE RENDER (2026-09-22).** An app icon's alpha bbox includes
  its baked soft shadow: one app icon's reached 444 of 512 px but its body (alpha > 128) was 412, so scaling by the bbox rendered it
  7 % smaller than the partner's icon beside it, and the creator saw it at once. Two icons that sit side by side are the same size on
  the rendered frame, checked with a guide box, before anything is placed.
- **Sample a panel colour that sits beside a capture off a RENDERED frame** (before any post pass), never off the source,
  on every pin: before 0.8.81 (an older in-flight job's pin) a `<video>` renders DARKER than the file (a second tv→pc range
  expansion: #161616 came out ≈#090909, mid-greys moving most; 0.8.105 renders within 1-3 levels) (2026-09-22).
- **No raw emoji glyphs — they HANG the headless render** (Chrome spins at 100% CPU resolving the
  system color-emoji font; never errors, never times out — a 5s part burned 5+ min before being
  killed). Fake the look in the brand font, or bake the glyph to a PNG with
  `uv run workflows/bake-emoji.py rocket=🚀 --out projects/<job>/hf-graphics/assets/emoji`.
  Smell test: a render at ~3× its siblings' time on a same-length part = kill it, look for a glyph.
- **An exit tween must finish INSIDE the clip's `data-duration`, plus a hard-kill**
  (`tl.set("#id",{opacity:0}, <next-clip-start>)`) — HyperFrames hard-hides a clip at its window
  end, so a mid-dissolve exit POPS. Lint catches only the missing hard-kill half; the
  too-short-duration half passes lint and pops in the video.
- **A fixed-pivot rotate/scale on an SVG element goes in the SVG `transform` ATTRIBUTE** —
  `rotate(deg cx cy)`, per-frame `gsap.set` of the attribute string is fine. GSAP `rotation` +
  `transformOrigin`/`svgOrigin` on SVG displaces the pivot (measured on 3.14.2), and a later bare
  `{rotation:N}` tween silently reverts it — the element still animates, it just orbits, which is
  exactly what the Stage-4 probe exists to catch.
- **Never pre-position a GSAP-tweened element with CSS `transform`** — the stylesheet transform
  gets absorbed into GSAP's cache and a later `x`/`xPercent` tween nets the wrong end position.
  GSAP owns position; set initial poses via `tl.set(...)`.
- **ALL CSS inline in the comp** — a `<link rel="stylesheet">` silently does not load in the
  headless render (zero error, zero lint; fonts fall back to serif, classes vanish). Smell test:
  brand font rendering as Times.
- **A staggered `fromTo` whose from-pose changes glyph geometry needs `immediateRender:false`** —
  GSAP applies from-poses at build time by default, so pre-scaled glyph boxes eat the margins and
  un-revealed text renders packed together.
- **Benign lint noise — don't "fix":** `duplicate_media_discovery_risk` (warning),
  `missing_local_asset: <id>-base.mp4` (clears when the slice is cut),
  `timeline_track_too_dense` (warning), `missing_three_script` (false positive on `+esm` imports).
- **Never tween a CSS `filter` string for a state change: dim with a black scrim's opacity instead (your-job g10, 2026-09-07).** `tl.to('.wall', {filter: 'grayscale(0.7) brightness(0.30)'})` from a CSS-declared `brightness(0.55)` interpolated from brightness(0) on the seek-render (an explicit `fromTo` did not help), so the wall blinked near-black for three 12 fps frames; both reviewers caught it on the composite. A numeric opacity tween on an overlay element cannot misparse; `graphics-qa.py`'s `source` lint fails a `filter` tween (`tl.set` is the discrete escape hatch).
- **A 4K render of a 1080 comp = the 1080 layout on a `#stage{width:1920px;height:1080px;transform:scale(2);transform-origin:0 0}` inside a 3840x2160 `#root`, never `#root{zoom:2}` (your-job, 2026-09-07).** Under CSS zoom Chrome double-resolves the percentages inside a `transform-origin` and a gradient position: the three punch-cuts' centred `scale(0.92)` pivoted on the corner (77x43 px off) and the vignette landed on the bottom-right corner, while the 24 overlays, carrying no such percentage, came out pixel-identical and hid the fault. Prove any resolution change with `uv run workflows/render-diff.py <new> <old>` (the previous render downscaled, exit 1 on a difference), never by reading a layout back; `graphics-qa.py` repeats that proof as its `parity` check.
- **A comp that embeds a captured `<video>` renders WITHOUT the MBLUR supersample (a demo run's scroll
  capture, 2026-09-13).** A page-record scroll holds each scroll position for one frame, and `tmix` averages two of
  them into one output frame: the page text ships as a 50/50 double exposure (17 of 57 scroll-span frames
  under half the median ink). The registry's SVG smear still rides the scene slides; the supersample is
  the half that has to go. `graphics-qa.py` warns on every comp with a `<video>` as the reminder.
- **Never GSAP-`transform` a `<video>` element — it silently drops from the render** (the face
  vanishes, no error). Footage moves on app lanes are baked in-app (Transform keys / Fusion);
  on the chat-only lane use the wrapper-box / ffseg recipes in
  [`lanes/chat-only/incremental-graphics.md`](../../../lanes/chat-only/incremental-graphics.md).

## Stage 6 — place

Route to the lane's own doc — this skill orders the work, the lane doc carries the mechanics:

| Compositor | Recipe |
|---|---|
| `resolve` | **`uv run workflows/placement.py projects/<job> --write` first** (the same rows and the same half-frame plan sync as Premiere's `--plan --write`), then the `davinci-resolve` skill § Step 5 ([`LANES.md`](../../../LANES.md) § step 5) — a per-job `hf-graphics/place.py` laying those rows, idempotent + readback-verified |
| `premiere` | **`uv run lanes/premiere/place-graphics.py projects/<job> --plan --write` then `--apply`**, one owner for `hf-graphics/placement.json` and the graphics tracks: derives every row from the plan + the newest render version, places what is not yet on the timeline, swaps stale versions, reads every write back; `--verify` is the readback, and `--plan --write` syncs the frame-snapped times straight back into the plan so plan-fidelity never argues over a rounding (`--sync-plan` is the standalone escape hatch, for a row placed by hand; 2026-09-02: eight hand ES batches + two reconciliations). Mechanics underneath: the `premiere-pro` skill § Step 5 (V3 on youtube/default: V1 footage, V2 grade, V3 graphics; baked footage moves on V1 via the bridge `zoom`; AME banned) |
| `capcut` | **`uv run workflows/placement.py projects/<job> --write` first**, then the `capcut` skill § Procedure 4 — `lanes/capcut/capcut-bridge.py graphics <draft> <job>` lays those rows (each alpha mov premultiplied first); `add-overlay` (+ `--force` rules) for a one-off |
| `finalcut` | **`uv run workflows/placement.py projects/<job> --write`**, then `uv run lanes/finalcut/replay.py projects/<job>` (lays `placement.json` as connected clips) and `uv run lanes/finalcut/import.py <the .fcpxml it names>`, per the `final-cut-pro` skill |
| chat-only | [`lanes/chat-only/incremental-graphics.md`](../../../lanes/chat-only/incremental-graphics.md) — the ffmpeg assemble lane (kept for no-app clients; not the primary path) |

**The plan's frame-snap ROUNDINGS are reconciled to the placement before the gate, and nothing else
is.** Placed times are snapped to the sequence grid, so authored and placed times always differ by a
fraction of a frame (unsynced, a fresh job's first gate run is a wall of that noise: 62 values,
2026-09-19). `workflows/placement.py --write` (every lane) and Premiere's `place-graphics.py --plan
--write` (the same derivation) write it back in the same command, **bounded to half a frame.** A bigger gap
is the plan and the build disagreeing (a stale text-animation `meta.json` 8 frames off its cell, an
overlay render that no longer fills its span): the writeback prints it as `NOT synced` and leaves it,
`graphics-qa.py`'s `plan` check FAILs on it, and a human decides which side is right. **Never widen that
bound to make the gate green:** an overlay's plan `end` is the BOUND `derive()` clamps the render to, so
writing a short render's end back silently clips every later, longer re-render to it (proved offline
2026-09-19). `--sync-plan` alone is the unbounded escape hatch, for a row placed by hand. Any lane that hand-writes `placement.json` rows reconciles `graphics-plan.json` the same way.

**The caption layer (short-form presets, on by default — 2026-09-04)** is built and placed
here like any other graphic: `uv run presets/tiktok/raw/build.py projects/<job> --alpha` (TikTok/raw)
or `uv run presets/instagram/talking-head-explainer/captions.py projects/<job>` (the Talking Head Explainer,
run from the preset and never copied; its gate runs on every build and fails on a dropped word, a line across a
boundary or an off-band frame) writes `hf-graphics/captions/renders/captions-alpha.mov`; the plan's `captions` cell makes `place-graphics.py`
derive its row onto the top graphics track (V5 on Premiere, above every other overlay), and the
chat-only assemble takes it as one more overlay. Long-form has no caption layer.

**Replacement consistency:** after a new render, prove the chain from active comp/spec → versioned
render → placement row → live clip media path, source in/out and timeline bounds. Confirm media
is online, the clip enabled, its track visible/unmuted, and the new frame visible in the native
composite before saving; a JSON row alone is not placement proof. If an ID changes template
(e.g. caption → real capture), retire its old comp AND builder spec from scanned folders so the
SFX scanner cannot choose the obsolete animation. Keep archived source outside those folders.
Reconcile SFX for affected IDs: merge reviewed new cues into the existing plan while preserving
approved cues/levels elsewhere, then place and verify missing, duplicate, orphaned and shifted
cues, including after an interruption.

Long-form structure (section title cards, SFX whoosh, track map) is the **preset README's**
territory (e.g. `presets/youtube/default/`) — place graphics onto that architecture, don't invent
tracks.

## Stage 7 — first-pass QA + report

**The gate first (2026-09-02):**

```bash
uv run workflows/graphics-qa.py projects/<job> --json projects/<job>/hf-graphics/qa-report.json
```

9:16: `uv run workflows/graphics-qa-short.py projects/<job>`. It QAs the render `place-graphics.py --plan`
would lay now, not the placed file, and names a stale placement. On the Talking Head Explainer the 9:16 gates are
four, all green: `graphics-qa-short.py`, the `captions.py` gate, `presets/instagram/talking-head-explainer/layout.py
projects/<job> --check`, and `workflows/change-events.py --sync projects/<job>`.

Non-zero exit = not done; fix and re-run until it is green. **What it owns mechanically is its own
`Checks` / `Not here` docstring block — read that, not a copy of it** (`sed -n '1,/^"""$/p'
workflows/graphics-qa.py`). **A deliberate deviation is a line in
`hf-graphics/qa-waivers.json`** (`{"g18": {"band": "DOWN arrow reaches the floor by design"}}`),
never a sentence in the report: the review loop reads the JSON and treats prose as no evidence.
Items 1–3g below are what the script cannot check — plus, in one line each, the ones it does, kept
only as a pointer to what to look at when a check fails.

Verify, then report — never hand over unverified work:

1. **Render format + duration per ROLE** — the gate owns this (`render`, `duration`, `grain`
   fields in the qa-report; section title cards are exempt from grain by design).
2. **Placement readback:** every overlay at its planned time on the right track (each lane doc's
   readback method). Timeline count == plan's `graphic:true` count. The gate cross-checks this
   against the plan (`plan`, `holes`); the readback itself is yours.
2b. **Picture on its words:** `uv run workflows/change-events.py --sync projects/<job>` finds when each
   placed render visibly changes on screen (its entrance, a send, a reply, a card pop) and prints each
   change's delta to its anchor word in the canonical transcript. Only changes before the row's
   out-point count, because the placer trims a longer render there. Exit 1 = a picture more than
   0.10 s off its word; exit 2 = an anchor could not be checked (unknown or ambiguous word, bad `nth`,
   missing render) or nothing was checked. A word-synced cell carries `sync` anchors (`graphics-plan`
   schema); a cell without them is checked only for its entrance on its start word, which cannot catch a
   clock error inside a render (a render set 0.876 s early passed every other check). Never time or
   re-check sync with a job-local tblend / signalstats script.
3. **Composite spot-check:** 2–3 real composite frames at the strongest cells (Resolve: a real
   render, never `get_thumbnail_image`; Premiere: the bridge `frame` command / `window-grab.sh`,
   never fronting the app; chat-only: ffmpeg frame of the assembled file). Verify against the
   plan's cell: right copy, right side, face clear.
3b. **Band + edge sweep (long-form)** — the gate owns this (`band` field, every frame of every
   render). When it fails, look at the comp's box geometry in the browser probe rather than
   eyeballing a composite.
3c. **Prop-glow check (long-form):** for every accent prop
   (icons and glyphs inside cards and nodes included), measure its own colour's light
   OUTSIDE the prop's box on the finished render (a masked fill's `box-shadow` renders nothing
   — `default-overlay-style.md` § THE PROP GLOW). A comparison against the previous render is
   the fastest form: zero accent pixels outside the box means the glow never existed.
3d. **Registry + float conformance (long-form) — AUTHORED graphic comps only.** The mechanical
   half (registry constants, relative `riseOut`, `float()` on a wrapper over `0 → DUR`, helper
   integrity, the 12 fps form, no `flash` at 12 fps) is the gate's `source` check; the preset's
   generated builders (`text-animation/`, `titles/`) are exempt from conformance — their motion is
   locked in the builder, so "conformant" there means the builder was used unmodified. **Three
   judgments the script cannot make, and you must:** (a) the entrance split against ROLE — peers
   share one preset, the odd element out carries the contrast; (b) the RENDER FLAGS against the
   `bg` field — a bg-DARK full-screen renders `STEP_FPS=12` AND carries the glow pass (the pair
   travels together), a bg-LIGHT one gets NEITHER; (c) a full-screen's FIRST element entering on
   frame 0 with zero blank lead when that element is near-full-frame, and rising rather than
   popping — **measure it on the render with a heavy-downscale structural diff, not an edge count,
   or grain swamps it** (the defect scales with the element's size). The registry itself:
   `presets/youtube/default/animations.md`.
3d-1. **Zero-frame pins** — the gate owns this (`source`: content reveals pin the zero frame, no
   `onUpdate`-driven content). When measuring text on a render by hand, crop the WHOLE content
   box: a crop that starts below line 1 reads grain as "empty" and hid exactly this bug.
3d-2. **Readable-hold check (long-form):** for any graphic built to be READ (prompt, command,
   code, config, quote), count the render's frames carrying the COMPLETE content (neutral-bright
   TEXT pixels only, the accent cursor excluded): **2-3s**. Count the reveal's discrete steps (a new
   state every frame is the linear-wipe defect) and grep the comp for `Math.random`. The hold, the
   bursts and determinism: `creative-moves.md` 4d.
3e. **Arrow GEOMETRY (long-form):** that heads are computed rather than typed is the gate's
   `source` check; whether they POINT correctly is yours. In the browser probe, read every `.head`
   back — including the clones inside a `#bloom` glow layer — and measure: the head's axis (tip
   minus base-midpoint) within **1°** of the path's end tangent, its base within **0.5×stroke-width**
   of the path end, every head vertex inside the SVG's viewBox. Straight arrows hide this bug — a
   hand-drawn head only reads broken on a curve — so measure the curved ones even when they look
   fine. Spec: `animations.md` § The arrow.
3f. **Footage-moves check (long-form):** the opening zoom-out is baked on clip 1 and every
   plan-marked emphasis beat has its push-in (`creative-moves.md` moves 5 and 6 carry the
   numbers). Read the **Transform** keys back — NOT Motion; a `Motion/Scale` query reports zero
   keys and reads as "no push-ins here". The verify frames (frame 9 alone does not tell an `inout`
   bake from a linear one): [preset README](../../../presets/youtube/default/README.md) § Emphasis
   push-in and § Opening zoom-out.
3g. **Borrowed-palette check:** any colour borrowed from a depicted product or brand must match a
   SAMPLE off the real asset (measure the render against the source logo/screenshot — e.g. Claude
   orange `#d97757` from the real logo file). A guessed brand hex is a defect
   (`default-overlay-style.md` § BORROWED PALETTES).
4. **Report:** built/placed counts, the `graphics-qa.py` summary line (green), the waivers with
   their reasons, the 2–3 frames as proof. Then step 5c: hand the draft to the **`edit-review`**
   pass (the gate, then ONE two-dimension review round, its verified defects fixed, the gate re-run
   on what changed) BEFORE presenting for review. The **live second
   pass** starts after that, inline in the chat (never a spawned agent) — iterate part-by-part (edit → re-render the one part →
   re-place/re-assemble), and on those tweak rounds skip the self-QA frame grabs: just edit,
   render, show — the fixes get called live from the review (a re-placed split part still gets
   § part splits' native seam proof). Respect a request to leave the timeline without exporting.

## Not this skill

Deciding graphics (step 5a: `graphics-plan`) · the color grade (pipeline step 4 — it runs BEFORE
this step and lives on the track UNDER the graphics; never fold it into the build) · background
music (the one conditional pass, not a numbered step) · SFX (pipeline step 6, after this
step and its defect loop: `workflows/sfx-plan.py` then the lane's placer) · audio of any kind (the polish is **pipeline step 3**, run right after the
cut lands on its finish surface, never during the build) · export (step 8, `finalize.sh`).
