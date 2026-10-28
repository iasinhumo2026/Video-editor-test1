# CLAUDE.md — Video Editor

Your **video production & editing department** — and **only** that. Raw filmed footage comes in, a
finished exported cut goes out: point it at a raw clip and it takes that clip from **raw → fully
edited → exported.** What happens afterward (posting, scheduling) is out of scope. Not a traditional
code repo — a content system where **Claude IS the editor**, one skill per stage in `.claude/skills/`.

> **Updating an editor the user already has? Start here.** If this folder is a new version the user
> just downloaded or unzipped, and they already work in another video-editor folder: do not copy or
> unzip anything into that folder, and do not run setup here. Your session is IN this download → run
> `uv run update.py` here: it finds their project and updates it from this folder (if it lists several,
> ask which, then `uv run update.py --project "<their folder>"`). Your session is in THEIR folder → run
> `uv run update.py "<this folder>"` (a folder from before updates has no update.py: then
> `uv run "<this folder>/update.py" "<this folder>"`). Either way it sets their folder up for updates if
> it never was and merges this version in; their presets, brand kit, rules, jobs and app wiring stay
> theirs. Then § Updating, and afterwards they work in their own folder.

---

## 🪟 On Windows? One check first

This system runs natively on **macOS, Windows, and Linux** — no virtual machine. On Windows the
`.sh` scripts run through **Git Bash** (installed with **Git for Windows**), the same shell Claude
Code itself uses. Run `uname -s`: `Darwin` / `Linux` / `MINGW…` / `MSYS…` → you're set, go to **FIRST
RUN**. A command-not-found or PowerShell-looking answer (`C:\…` paths) → Git for Windows is missing:
run `winget install --exact --id Git.Git` yourself if you have a PowerShell tool (else the user runs it
in PowerShell), restart Claude Code, re-check.

> Windows notes: `./setup.sh` installs through **winget** (an install may raise a "Do you want to allow
> this app to make changes?" prompt the user clicks Yes on, sometimes behind other windows), then one
> Claude Code restart so PATH updates. Python there is `python`, never `python3` (a fake Store stub; the
> scripts handle it). Windows and Linux encode in software (same result); an NVIDIA GPU is auto-detected
> for transcription. Keep the project folder OUT of Documents, Desktop, Pictures, Videos, Music and
> OneDrive (Controlled Folder Access blocks writes there, and the error reads "No such file or
> directory") and its path at most 100 characters (e.g. `C:\Users\<you>\video-editor`: Windows stops a
> path at 259 and the editor installs files up to 145 deep); `./setup.sh` checks both before installing.
> **Smart App Control** can stop a tool with "DLL load failed … An Application Control policy has
> blocked this file": re-run the command once; blocked again means a release too new to have
> reputation, and `uv run workflows/sac-warm.py` names the package and version: report it. Never ask the
> user to turn Smart App Control off.

---

## 🚦 FIRST RUN — onboarding gate (read this before doing anything else)

**The first thing to handle when the project opens.** A SessionStart hook
(`.claude/hooks/setup-check.sh`) nags while setup is incomplete, and says when this folder is a NEW
DOWNLOAD of an editor the machine already has (the user wants an update: the box at the top) or an
update stopped on conflicts. Run this flow on **"set this up (on my machine)"** / **"run the setup"** /
**"install this"** / **"continue setup"**, or on any edit request while the tools are missing.

**Is setup done?** The marker file **`.setup-complete`**, one line,
`lane=<premiere|resolve|capcut|finalcut|chat-only|pending>`, written by `./setup.sh` once every core tool
verifies. **Missing** ⇒ run the flow below. **`lane=pending`** ⇒ ask the which-app question, then record
it with `./setup.sh --lane <pick>`. **A real lane** ⇒ done (on "continue setup": re-run `./setup.sh` once,
verify the lane, make step 3's offer). Every edit reads that `lane=` line for its finish surface.

**The goal: core editing working, fast, with near-zero effort from the user.** A Mac needs Apple
Silicon (M1 or later) on macOS 15 or newer. Personalization is OPTIONAL and comes last: the presets
ship a neutral look (Inter fonts, a generic starter palette, no handles).

1. **Tools: run `./setup.sh` yourself.** Don't ask first and don't hand over a command list; say
   what it's doing as it goes. It installs every missing core tool (macOS → Homebrew, Windows →
   winget), bootstraps the render engine (`npx hyperframes@0.8.105 browser ensure`, pinned and
   frozen; its npm and telemetry chatter is noise, and never run `hyperframes upgrade`), verifies with
   `./check-setup.sh`, then probes for editing apps. **Bash timeout at its maximum (600000 ms) or run
   it in the background:** a fresh machine can take 10-20 minutes. **Idempotent: re-run it after any
   interruption.** Its exits:
   - **exit 0:** done → step 3, after following every `ACTION FOR CLAUDE` line it printed (several
     editing apps → step 2; a folder in OneDrive → offer to move it). If your session's folder is not
     exactly the editor folder it names, the user opens that one (Windows' Extract All nests it).
   - **exit 2:** a restart is needed (something just installed is invisible to this session, or Claude
     Code is open on the wrong folder: the output names the right one). Restart, re-run `./setup.sh`; a
     third restart for the same thing gives up and says what failed. **exit 3:** a lane was wired into
     `.mcp.json`: restart, then verify the lane.
   - **exit 1:** read the output. Homebrew missing → open Terminal with its installer already running
     yourself (`osascript -e 'tell application "Terminal" to do script "/bin/bash -c \"$(curl -fsSL
     https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""' -e 'tell application
     "Terminal" to activate'`), then tell the user: type your Mac password in that window (nothing
     shows as you type; the account must be an administrator), press Return when asked, and say when
     it finishes; then re-run `./setup.sh`. Tools still missing → run the brew and winget commands
     `check-setup.sh` printed yourself; only `apt install` (sudo) goes to the user; a failed winget
     install is named, with its own words in `.setup-install.log`. A lane installer failed → fix it,
     then `./setup.sh --lane <that app>`. An unsupported Mac (Intel, or macOS below 15) → say so in
     plain words; `VE_UNSUPPORTED_PLATFORM=1 ./setup.sh` only if they insist. A tool below its floor
     that setup could not upgrade → the route `check-setup.sh` names (a pip-installed uv:
     `pip install -U uv` with that pip). The self-test failed → fix what its ✗ lines name (mostly an
     old or lean ffmpeg), re-run. **This folder looks like a NEW VERSION of an install already set up**
     (the ACTION line names it): ask in one line whether to update that install (`uv run update.py`
     here) or make a second, separate one (`./setup.sh --new-install`, then carry on).
   Loop until `./check-setup.sh` shows every core item ✓. (Manual per-OS list: `SETUP.md`.)
2. **Editing app lane: auto-detected, at most one question.** `setup.sh` probes for Premiere Pro,
   DaVinci Resolve, CapCut and Final Cut Pro (Final Cut macOS only, CapCut macOS and Windows; Linux:
   resolve or chat-only) and records the `lane=` line. **One app** → settled: Premiere/Resolve/Final
   Cut ran their installer (`./setup-premiere.sh` / `./setup-resolve.sh` / `./setup-finalcut.sh`) and
   exited 3. **Final Cut** needs ONE click first: its installer opens SpliceKit, which makes a separate,
   patched copy of Final Cut Claude can drive (the App Store app is never changed), and setup exits 1
   with an ACTION line to relay (click Continue in SpliceKit; setup already quit Final Cut); when they
   say it is done, re-run `./setup.sh --lane finalcut`. The click comes back after every Final Cut
   update. **Several** → ask ONE line ("Premiere, Resolve and CapCut are all here: which do you edit
   in?"), then run **`./setup.sh --lane <pick>`** yourself (`premiere` | `resolve` | `capcut` |
   `finalcut`); the pick is final unless they ask. **None** → `lane=chat-only`: say so in one line,
   never re-ask at edit time. **CapCut** needs no install, but macOS asks once, the first time Claude
   drives it, to let Claude Code control the computer (System Settings → Privacy & Security →
   Accessibility): say so when the first CapCut edit starts.

   **Verify a wired lane after the restart.** First the MCP: its tools must be in the session.
   `setup.sh` pre-approves the lane's server in `.claude/settings.local.json`; if Claude Code still
   asks, the user answers **yes**, and a remembered "no" is undone with
   `claude mcp reset-project-choices` (run it yourself), one more restart, and a yes. Then the app:
   **Premiere** → run `./lanes/premiere/premiere-up.sh` and confirm `node lanes/premiere/premiere-bridge.mjs ping`
   answers (only if it fails: **Window → Extensions → MCP Bridge (CEP) → Start Bridge**).
   **Resolve** → ask the `davinci-resolve` MCP for the version with Resolve running (External
   scripting = Local is its shipped default: send nobody into Preferences). The lane needs **Resolve
   Studio 21.1+** (Blackmagic's own `ResolveMCP`): `./setup-resolve.sh` refuses an older Resolve (the
   user updates it, then re-runs) and the free edition (upgrade to Studio, or pick CapCut /
   chat-only), changing nothing either way. **Final Cut** → run `uv run lanes/finalcut/doctor.py --repair`:
   it quits a Final Cut that is not the lane's patched copy, trashes stale copies, launches the ONE
   copy by its path and proves the bridge (`sk.py system.version` answers). It is the only way Final
   Cut is started (never the Dock, a name, a bundle id or computer use: all reach the App Store app,
   with no bridge). **Two failed bridge connects later on → run the repair yourself, never ask the
   user to quit and reopen anything;** its exit 4 is the one SpliceKit click to relay.
   `uv run lanes/finalcut/sk.py --dismiss` closes Final Cut's "notifications" sheet (it returns until
   the user answers macOS's notification question for that copy once).
3. **Brand kit: OPTIONAL. Offer once, never block.** Say the editor already works with the neutral
   bundled look, and that whenever they want captions and graphics to sound and look like them they
   can fill in [`brand-kit.md`](brand-kit.md) and say **"apply my brand kit"** (you then follow the
   file-by-file map in its Part B and render one test). Don't walk them through it unless asked.

**Restart walkthrough (be exact and friendly):** *"Quit Claude Code completely (Cmd+Q on Mac / close
the app on Windows), reopen it, open this same folder, and say **continue setup**."* After the Premiere
lane was wired, first: *"Quit Premiere Pro too if it's open; it loads the new panel when it starts."*
Never assume a restart loaded anything — verify it.

**Permission prompts ("Allow once / Always allow" on every command).** This folder's
`.claude/settings.json` pre-approves the editor's routine commands once the user has trusted the
folder and Claude Code is open on this folder itself. For no prompts at all, the user switches the
permission mode next to the send button (`Cmd+Shift+M` / `Ctrl+Shift+M`): **Bypass permissions** on a
Pro or Max plan, after turning on Settings → Claude Code → "Allow bypass permissions mode" (a new chat
if it does not show); **Auto** on a Team or Enterprise account, where the organization's policy
decides. You cannot change the mode for them: point them at SETUP.md § Permissions, in one line, the
first time the prompts get in the way.

---

## 🔄 Updating to a new version

When the user says **"update"** (or "I downloaded the new version"), run it yourself from THIS folder,
the one they already work in, with the Bash timeout at 600000 ms:

    uv run update.py

It finds the newest `video-editor*` download in Downloads by the version inside it (never the file
name: a second download is `video-editor-client (1).zip`), runs that download's own updater and merges
it in. Give it a path only when the user names one. No newer download → say so and ask them to
download the new zip. On Windows, first ask the user to close any file from this folder open in
another app (one held open stops the update, which then puts everything back).

This folder is a git repository: `upstream` holds every version exactly as shipped, the user's branch
their project. The update commits what they changed, lays the new version on `upstream` and merges it
in: a file only the new version changed is updated, a file only they changed keeps their version, a
spot both changed stops as a conflict. `projects/`, `.env`, `.mcp.json`, `vendor/` and large media are
never touched. **Never copy files over from a download by hand, never delete `.git`, and never pass
`--force` unless the user asked to go back to an older version.**

- **exit 0:** done. Relay the "What is new" lines in one short list, and any line about files it kept
  or moved aside, then do what its `Next:` line says: `./setup.sh` once when this version's self-test
  has not run here yet, otherwise `./check-setup.sh` (only a ✗ line needs `./setup.sh`). Then tell the
  user to start a fresh Claude Code session (/clear, or quit and reopen) so the new instructions load.
- **exit 3:** stopped on conflicts (it printed how to read them). Resolve every block, keeping both the
  user's deliberate changes and the new version's fixes; ask about any block you cannot call; then
  `uv run update.py --continue`. `uv run update.py --abort` puts every file back.
- **exit 1:** nothing changed; the line says why (no newer download, a damaged or half-downloaded zip,
  a Downloads folder macOS would not let it read, a file open in another app). Fix it and run again,
  or take the zip's path from the user: `uv run update.py "<the zip>"`.
- **A conflict on a file with no markers** (a binary, or a file one side deleted):
  `uv run update.py --keep-mine <file>` (the project's copy) or `--take-new <file>`, then `--continue`.
- **A brand-kit line after an update:** fill each new `<<…>>` field from what the user already gave for
  the same role, then "apply my brand kit".
- **"Undo the update":** `uv run update.py --undo` takes the last update back out and keeps everything
  done since. Never `git reset`.

**Where the user's own work goes, so no update ever fights it:** their standing rules and brand
identity in [`my-rules.md`](my-rules.md) (loaded below, never changed by an update), a new preset in its
own folder under `presets/<platform>/<name>/`, a new skill in its own `.claude/skills/<name>/`. Edits to
shipped files merge too; a separate file just never conflicts. What an edit taught gets there through
`bake-preset`.

---

## Brand Kit

The editor's voice and look come **entirely from [`brand-kit.md`](brand-kit.md)** and the presets it
feeds ("apply my brand kit" writes the identity and voice into [`my-rules.md`](my-rules.md)); the
short-form look (palette, type, backdrop) is locked in
[`presets/instagram/talking-head-explainer/graphics.md`](presets/instagram/talking-head-explainer/graphics.md),
the long-form one in the [`presets/youtube/default/`](presets/youtube/default/README.md) docs. Apply
them verbatim. Filling the kit in is optional — editing works before any personalization.

---

## The Pipeline — one linear flow, every time

Every job runs the **same eight steps, in order**, raw → done, each finished to its own definition of
done before the next starts. The **`edit-video`** skill owns the run and keeps `projects/<job>/RUN.md`,
so it survives a context compaction and resumes cold.

**The finish surface is your editing app by default:** a bare "rough cut" means the lane recorded in
`.setup-complete`. A machine recorded as `lane=chat-only` is already on the chat finish (never re-ask);
on a machine WITH an app, chat-only runs only on an explicit yes to "want this done straight in chat?",
never inferred from a job's content. Lanes change only WHERE a step happens; format changes only how
**Graphics (step 5)** behaves (captions included), and the Talking Head Explainer also reaches steps 2,
3, 4 and 6 through its own preset README.

🔒 **At every step the route is the same two reads: the PRESET for WHAT (the numbers, identical in
every editor), then [`LANES.md`](LANES.md) for HOW.** A step your app has no recipe for is done by
hand from the preset's numbers and **said out loud**, never with another app's mechanics.

| # | Step | Skill | What happens |
|---|------|-------|--------------|
| 1 | **Intake** | _(copy)_ | **Copy** the raw file into `projects/<job>/raw/`: never move, never touch the original. Name `<job>` after the content (see Job naming). |
| 2 | **Rough cut** | `rough-cut` | Every format. `transcribe.sh` (WhisperX large-v3 + word alignment) → kill filler and dead air (**relevant ≠ necessary: only need-to-know-NOW survives**) → `splice.sh` stitches it frame-snapped, `polish-boundaries.py` sets every word edge → **fresh-eyes second pass** (§ Rules). Produces the cut **and the finished script**, the source of truth downstream. On an app finish it runs `RENDER=0` and replays the EDL onto the timeline, and **every cut is proven**: `workflows/cut-audit.py` on the finish surface's frame grid (zero boundaries in speech; exit 3 = UNVERIFIED, never clean), and on Premiere `lanes/premiere/cut-proof.py` (bounce, transcribe, diff against the script) exits 0. |
| 3 | **Audio polish** | _(in-app / baked by splice)_ | **Every job, immediately after the cut lands on its finish surface:** the gain `workflows/voice-gain.py` measures (kept speech → −17 LUFS pre-limiter) into a −6 dBFS limiter. Premiere: `uv run lanes/premiere/audio-polish.py projects/<job> --apply`, and **a timeline rebuild discards it: re-apply after every re-replay**; other lanes: [`LANES.md`](LANES.md) § step 3. **The cut locks here:** asked for the whole edit, the run goes on to the export and later cut notes are a re-cut; asked for just the rough cut, it stops here until you have watched the polished cut. |
| 4 | **Color grade** | _(in-app)_ | **Long-form and the Talking Head Explainer (camera footage only), before graphics and UNDER them:** one adjustment layer above the footage and below the graphics (Premiere: V1 footage → V2 grade → V3 graphics), because the graphics QA measures off the shipping picture. **The look is locked: Autumn-Rec709, Look Intensity 80, Creative Saturation 120**; Premiere replays it with `uv run lanes/premiere/grade-lut.py apply <job>.prproj`. No colour-correction step. Numbers: [`presets/youtube/default/README.md`](presets/youtube/default/README.md) § Grade. |
| 5 | **Graphics** | `graphics-plan` → `graphics-build` → `edit-review` | **Default = the preset's own vocabulary** (long-form: the BASIC tier of [`default-overlay-style.md`](presets/youtube/default/default-overlay-style.md) plus the [creative-moves vocabulary](presets/youtube/default/creative-moves.md) unprompted, required real captures and walkthroughs included; the Talking Head Explainer: its [README](presets/instagram/talking-head-explainer/README.md), one tier; TikTok/raw: the hook card only); named looks are opt-in. **(a)** `graphics-plan` storyboards and self-reviews (`validate-plan.py`). **(b)** `graphics-build` owns comps, renders and placement (`workflows/placement.py`; Premiere `lanes/premiere/place-graphics.py`); on the Talking Head Explainer it measures the framing first, `uv run workflows/face-frame.py projects/<job> --modes --collar --plan projects/<job>` (locked: hair top 100 px below the y960 seam in split). **(c)** `edit-review`: `uv run workflows/graphics-qa.py projects/<job>` (9:16: `graphics-qa-short.py`) green, then ONE review round, every verified finding fixed, the gate re-run on what changed: the draft reaches you with zero objective defects, never a second round. **The mistakes the system can find, the system fixes.** |
| 6 | **SFX** | `workflows/sfx-plan.py` → lane placer | WHAT: [`presets/youtube/default/sfx.md`](presets/youtube/default/sfx.md) + `sfx.json` (the Talking Head Explainer has its own [`sfx.md`](presets/instagram/talking-head-explainer/sfx.md)). `uv run workflows/sfx-plan.py projects/<job>` reads the PLACED graphics into a cut sheet with a measured level per slice; Premiere places it with `uv run lanes/premiere/place-sfx.py projects/<job> --apply` (`--diff` reports your hand edits first), other lanes per [`LANES.md`](LANES.md) § step 6. **After any graphic moves, read the timeline diff, re-run the plan and re-place, verifying zero missing/extra/drifting cues.** |
| 7 | **Review** | _(manual)_ | You watch and call adjustments: **taste only** (the draft already has zero objective defects). **Each change runs INLINE in the chat** ("change this caption", "move that graphic"): Claude makes it, re-renders ONLY the changed part and shows it, never through a spawned agent or `edit-review`. |
| 8 | **Export** | _(lane render → `finalize.sh`)_ | The lane renders the final (Premiere: `uv run lanes/premiere/export.py projects/<job>` on your go, never Adobe Media Encoder; Final Cut: `lanes/finalcut/export.py projects/<job>`; Resolve and CapCut natively), then `./finalize.sh <job>` (dry-run; `--apply` to act) promotes it to the one canonical `outputs/<job>.final.mp4`, retires drafts and **drops an export copy in `~/Downloads/`** (`VE_EXPORT_DIR` overrides), keeping what reopens the job; its header owns `--keep-drafts` and `--variant` (an ad cut in `outputs/ad/`, a 4K vertical's 2160×3840 Shorts file in `outputs/shorts/`). A finished `--apply` ends on a `Next:` line: offer `bake-preset` once. Never export onto `outputs/<job>.mp4`, the base cut's name. Export numbers: the presets' § Export. |

**One CONDITIONAL pass, opt-in (not a numbered step), after 6 and before 7:** **background music**
(skip unless asked). `background-music` lays a **flat constant bed**: −20 dB from the song's reviewed
sustained entrance, a 2 s tail fade-out only; ducking and fade-in are **opt-in**. Per lane:
[`LANES.md`](LANES.md) § Background music. Once a bed is planned (or its level, entrance or track
changes), `uv run workflows/sfx-plan.py projects/<job> --restack` re-levels the SFX against it and
names the rows to re-lay. (Captions are not a pass: on the short-form presets they are the top layer of
step 5, placed like any other graphic.)

### Your finish surface

On an app finish, steps 3 through 7 happen on that app's timeline. The rough cut is **not** imported
as a flattened export: each lane **rebuilds it as separate, trimmable clips** by replaying the EDL
(`transcript/cuts.json`) against the raw footage, so every cut is a real edit point you can
ripple/slip/slide.

**Switching apps** ("switch my editing app to X"): run `./setup.sh --lane <premiere|resolve|capcut|finalcut|chat-only>`
yourself, relay any ACTION line (Final Cut: the one SpliceKit click, then the same command again), then
do the restart and the lane verify from FIRST RUN step 2.

- **Premiere Pro** (`premiere-pro` skill) — `node lanes/premiere/premiere-bridge.mjs replay
  <cuts.json> <clipName>`, the headless bridge; from there Claude works ON the timeline (graphics,
  footage moves, audio chains, the export via `exportAsMediaDirect`). Install: `./setup-premiere.sh`.
- **CapCut** (`capcut` skill, macOS and Windows) — no API, so `uv run lanes/capcut/capcut-bridge.py`
  writes a whole draft from the EDL and drives the running app for edits and its own verified export;
  the locks that keep it working live in the skill.
- **DaVinci Resolve** (`davinci-resolve` skill, Resolve Studio 21.1+) — `./setup-resolve.sh` wires
  Blackmagic's own MCP (`ResolveMCP`) onto the official scripting API: the EDL replay is one call, then
  silence ripple, AI subtitles, Fusion graphs, DCTL shaders, native renders.
- **Final Cut Pro** (`final-cut-pro` skill, macOS) — a patched copy of Final Cut with a bridge inside
  (SpliceKit, installed by `./setup-finalcut.sh`). `uv run lanes/finalcut/replay.py projects/<job>` builds
  the whole timeline from the job's files, `lanes/finalcut/import.py` brings it in and proves it clip by
  clip, `lanes/finalcut/export.py projects/<job>` renders with no clicks. Every rebuild is a new library,
  so hand edits in Final Cut are never overwritten.

**Second entry path: long-form → clips (`clipper`).** A finished long-form in, short-form clips out:
self-contained hook-and-payoff moments into a reviewed `clips-plan.json`, then `make-clips.py --build`
runs each through the locked engine (`.final.mp4` + a `~/Downloads/` copy), each clip a job folder
under `projects/<parent>/clips/<name>/`.

### Format variants

**Format is AUTO-DETECTED from the raw footage, never asked:** **vertical** → short-form, **horizontal**
→ long-form YouTube, read off the DECODED (displayed) size (an iPhone portrait take coded 1920×1080 is
vertical); a landscape raw the ask calls a short is the Talking Head Explainer, filled to 9:16 once.
Talking Head Explainer vs TikTok/raw is inferred from content. State the detected format, the hook and
the takeaway in the report so a word can correct them, never ask up front.

| Format | Aspect | Graphics (5) | Captions |
|---|---|---|---|
| **Short · Talking Head Explainer** (Reels · TikTok · Shorts) | 9:16 · 1080×1920 | the layout rotation (split / tight / wide / full / card) planned per sentence into graphics-plan.json `layout`; `face-frame.py --modes` first (`presets/instagram/talking-head-explainer/layout.md`, `graphics.md`; one tier) | mono caps in a 90 % box, on the seam in split, collar + 40 on the face — **locked** (`captions-style.md`) |
| **Short · TikTok/raw** (Reels · TikTok · Shorts) | 9:16 · 1080×1920 | **front hook card only** (`presets/tiktok/raw/tiktok-raw-style.md`), then raw | low, under face — **locked** |
| **Long-form** (YouTube) | 16:9 · 1920×1080 (no reframe) | `presets/youtube/default/` cards + creative moves (`youtube/liquid-glass/` and `youtube/vox-collage/` are opt-in by name) | none (YouTube CC) |

Safe zones and layout live in each preset's own docs: read the preset you're on before building.
Long-form has no platform safe bands: never cover the face or important content, keep copy off the very
edge, and leave the outro's right side and bottom clear for end-screen cards.

**Short-form safe zones (always, never break):** no key visuals in the **top 200 px** or **bottom
300 px** — face, captions and every key graphic stay inside y `200 → 1620`. Those two bands are
background only (platform UI and device chrome sit there).

## Skills

- **`edit-video`** — **the orchestrator: the whole line, end to end.** "Edit this video" / "do the
  whole edit" routes here. It owns the ORDER, the STATE (`RUN.md`, read before assuming a fresh start)
  and the GATES only; a step that cannot run is **announced as skipped, never passed over in silence**.
- **Core editing:** `rough-cut`, `graphics-plan`, `graphics-build`, `edit-review`, the locked caption
  presets (`captions-style.md` + `captions.py`, `tiktok-raw-style.md` + `build.py`), `background-music`.
- **Your own B-roll:** `broll-own`, on a preset you give a `broll.json` (`broll-own` § Give a preset
  B-roll; the shipped presets carry none). It indexes your B-roll folder once (an external SSD is fine;
  nothing is written to the drive) and places full-frame cutaways at that preset's density. Pre-trim
  each clip to its best 2 to 8 seconds and name the file by what is on screen.
- **`bake-preset`** — after every finished export (`./finalize.sh --apply` and `make-clips.py --build`
  end on a `Next:` line, so offer it in one line): writes what the edit taught, on a yes, into the job's
  preset (a rule for every video: `my-rules.md`). Never into CLAUDE.md.
- **Finish lanes:** `premiere-pro`, `davinci-resolve`, `capcut`, `final-cut-pro`; [`LANES.md`](LANES.md)
  is the per-step index across them. **`clipper`** is the reverse entry path.
- **HyperFrames (the render engine, vendored):** `hyperframes` (+ `-core`, `-cli`, `-animation`,
  `-audio`, `-creative`, `-registry`, `-keyframes`, `-studio`) and `media-use`, plus optional task
  workflows (`faceless-explainer`, `general-video`, `talking-head-recut`, `motion-graphics`,
  `pr-to-video`, `product-launch-video`, `remotion-to-hyperframes`, `slideshow`). It runs as
  **`npx -y hyperframes@0.8.105`** (the pin, `skills-lock.json` pins the skills) under its npm freeze
  (`npm_config_before`, the date setup.sh names beside the pin); every hyperframes command runs that
  way, and a bare `npx hyperframes` in the vendored docs means that. **Never refresh the vendored
  skills** (§ Rules).

## Folder Structure

The project root **is** the editing workspace — job folders live directly in `projects/`.

| Path | What's In It |
|------|--------------|
| `.claude/skills/` | The editing skills + the vendored HyperFrames toolkit. |
| `.claude/settings.json` | The allow rules for the editor's routine commands and the setup-check hook. Machine-local approvals go in `.claude/settings.local.json`, never here. |
| [`LANES.md`](LANES.md) | **The routing index: one row per pipeline step, one column per app**, each cell scripted / manual / unvalidated / gap with a pointer to the recipe. Read your step's row before any app-specific work. |
| `lanes/` | Everything app-specific, one folder per finish surface, each with its own `lab-notes.md`. Start at [`lanes/README.md`](lanes/README.md). |
| `presets/` | **The looks — the WHAT half of every step, app-independent**, one folder per preset: `youtube/default/` (long-form: its `README.md` at the top of a long-form job, its `default-overlay-style.md` before any graphics pass), `instagram/talking-head-explainer/` (its `README.md` is the index), `tiktok/raw/`, and `youtube/liquid-glass/` / `youtube/vox-collage/` (opt-in by name). A command or an app quirk belongs in `lanes/`. |
| `workflows/` | The universal utilities, identical whichever app you finish in; each script's header says what it does and how to run it. The gates and proofs the pipeline names: `voice-gain.py`, `cut-audit.py`, `graphics-qa.py` / `graphics-qa-short.py` (+ `render-diff.py` for any re-render), `sfx-plan.py`, `face-frame.py`, `pii-scan.py`, `ripple-cut.py`, `selftest.py` (the toolchain self-test). A file whose whole job is one app's mechanics lives in `lanes/<app>/`. The `workflows/test_*.py` suites some docs name are the author's regression tests, not in this package: such a pointer says the value is held, never asks you to run it. |
| `projects/<job>/RUN.md` | **The run's state file**, written by `edit-video` at every step boundary: format, lane, preset, per-step status, and every skip with its reason. Read it first on a job in progress. |
| `projects/<job>/` | One folder per content piece: `raw/`, `audio/`, `assets/`, `broll/`, finals in `outputs/`. The graphics build lives **durably** in `hf-graphics/` (comps + `render.sh` + a `PROJECT.md` resume doc — never delete it); only its regenerable cache is disposable, and **nothing lives solely in `/tmp`**. A section filmed later nests under `sections/<name>/` with its own transcript. |
| `finalize.sh` | Step 8. Dry-run by default. A render much shorter or longer than the final (a reel cut from it) is never promoted over it: keep it in `outputs/<name>/` and finalize it with `--variant <name>`. A finished job leaves `projects/` whole: § Rules, clearing out an old job. |
| `assets/` | `fonts/`, `logos/`, `sfx/` (the library step 6 draws from), `luts/` (incl. the captured house look, Autumn-Rec709), `models/`. **Personalize:** drop your own brand marks in `logos/`. |
| [`brand-kit.md`](brand-kit.md) | The one file you fill in — identity, voice, colours, fonts, hook style. Optional. |
| `transcript-corrections.json` | Brand/product names and recurring mishears, applied ONCE at step 2 so everything downstream inherits them. Per-job overrides: `projects/<job>/corrections.local.json`. |
| `skills-lock.json` · `check-setup.sh` | The pins for the vendored HyperFrames skills · the report-only check of the system tools. |
| `RELEASE.md` + `VERSION` | What changed in this build, and which build you have. Check `VERSION` against the download page before reporting a problem. |
| `update.py` · `.shipped-blobs.json` · `.git/` | Updating (§ Updating to a new version): the updater, the fingerprints of every shipped file, and the repository it merges through. |
| [`my-rules.md`](my-rules.md) | The user's own standing rules, loaded with this file every session, never changed by an update. |
| `AGENTS.md` | For Codex users: points Codex at this file, plus the inline step-7 rule and the Final Cut repair rule. |

**Job naming:** name `<job>` after the video's content — a short kebab-case title (e.g.
`my-first-video`, `cold-dm-teardown`), **never** the camera file (`C1840.MP4`), a date, or a stage
suffix.

## Rules

- **One job: edit the best video possible.** Raw → fully edited → exported. No business or CTA logic
  lives here — captions and end screens carry no sales asks.
- **Surgical changes only.** Touch what's asked; don't "improve" adjacent renders or refactor working
  skills.
- **Subagents only where a skill calls for them, never for a step-7 change, and on the chat's own
  model.** The step-2 fresh-eyes pass and the step-5 review round spawn reviewers; everything else runs
  in the chat (a subagent starts cold and re-reads the job). Never pass a model to a subagent call: one
  that names none runs on the chat's own model. Another model only when the user explicitly asks.
- **Fix the source, never stack a correction on a broken artifact.** A step's output is wrong →
  re-run that step from its durable inputs (`transcript/words.json`, `transcript/cuts.json`, the
  `hf-graphics/` comp source), never compensate downstream: a layered correction accumulates error and
  hides the cause.
- **The PRESET says WHAT; the APP SKILL says HOW; [`LANES.md`](LANES.md) is the index between them.**
  A preset is a look, identical in every editor: no command, argument quirk or track index in one.
- **The vendored HyperFrames skills are the pinned set: never refresh them.** Never run `npx hyperframes
  skills update` or `skills add`, `hyperframes upgrade` in any form, `npx hyperframes usage`, or `init`
  without `HYPERFRAMES_SKIP_SKILLS=1`, and skip the vendored router's § 4 and every "keep this skill
  fresh" preamble: `skills update` installs into the user's own skills folder, which Claude Code runs
  over this project's copies, replacing the pinned docs on that machine for good. `check-setup.sh`
  names any personal copies: ask the user before moving them aside, never delete them. New versions of
  the skills arrive with an update of this editor.
- **Document, don't manufacture.** Authenticity outperforms.
- **Motion craft is the VOX craft layer, not a global one:**
  [`presets/youtube/vox-collage/motion-craft.md`](presets/youtube/vox-collage/motion-craft.md) is
  read ONLY when that look is invoked by name.
- **Repeated line across takes → use the LAST take.** Don't ask.
- **Clearing out an old job: an external drive first, the Trash second.** A job leaves `projects/`
  whole, never thinned in place, and is closed in the editing app first. A connected external drive
  (Mac: a volume under `/Volumes/` other than the system disk; Windows: another drive letter; Linux:
  `/media/` or `/mnt/`) is the default: copy `projects/<job>/` into a folder on it, prove the copy
  (every file present at the same size), then delete the local folder; ask which drive when there is
  more than one. No drive: move the whole job to the Trash and say it stays recoverable, and frees no
  disk space, until the Trash is emptied. On Windows that is the Recycle Bin, reached only through
  `bash workflows/recycle-bin.sh projects/<job>` (a dry run: can the bin take the job whole?), then the
  same with `--apply`, which proves the job landed there. Never a move into a `~/.Trash` folder
  (Windows never empties it) and never another delete command: the others delete permanently when the
  job is too big for the bin or outside a desktop session.
- **Captions run the whole short-form video by default** — never suppress them under a hook or
  graphic unless told.

## Lab Notes — the locks

One lock per line, pointing at the doc that OWNS the rule. Read the owner before re-working a locked
area; every one of these was found the hard way.

- **Transcribe ONCE per video, one transcription at a time per machine.** WhisperX large-v3 →
  `transcript/words.json`, reused forever (`--force` to redo); `splice.sh` derives the canonical
  `outputs/<job>.transcript.json` with `transcript-corrections.json` applied, and nothing downstream
  re-transcribes. Owner: `rough-cut` § Transcribe.
- **A voice the VAD drops is not a hole, it is INVENTED dialogue:** a second speaker well under the
  main one (a phone, a call demo) can fall out of the transcript while the aligner slides the main
  speaker's words into its windows. `cut-audit.py --coverage` finds them, `--say <t0> <t1>` reads them,
  `scripts/realign-spans.py` repairs them. Owner: `rough-cut` § Gotchas.
- **The WhisperX venv is built from a lock** (`.claude/skills/rough-cut/scripts/whisperx-requirements.txt`):
  a new lock rebuilds it once on the next transcription (several minutes, several GB). Owner: `rough-cut`.
- **Audio = STATIC chain, processed ONCE:** the measured gain into a −6 dBFS limiter, then AAC 256k;
  never dynamic loudnorm (it pumps), never per-segment effects (they click); later re-encodes request
  ≥ 256k (a requested rate: AAC spends fewer bits on near-mono speech, so a lower measured bitrate is
  not a defect). Owner: [`LANES.md`](LANES.md) § step 3.
- **A named gain never replaces a broken measurement:** a measurement that FAILS is fixed at
  `voice-gain.py`, never worked around with `AMPLIFY_DB` / `--gain`, and a named gain the user asks for
  is reported and written into RUN.md as a deviation. Owner: [`LANES.md`](LANES.md) § step 3.
- **Splice = frame-snapped, J-cut joints, MEASURED boundaries:** equal-power crossfades, never fades to
  zero; segments never overlap in source (a continuous split shares ONE boundary). Owner: `rough-cut`.
- **A second camera is lip-sync-MEASURED before it is laid** (`workflows/lip-sync.py` with
  `--mouth-crop`; no crop = UNMEASURED, exit 2), **and every camera raw's sync is measured at intake**
  (`--slip-out projects/<job>/transcript/av-slip.json`, laid by the replay). Owner: `rough-cut` § Gotchas
  · § Lip sync at intake.
- **A cut change after step 3 is a declared RE-CUT:** `uv run workflows/ripple-cut.py projects/<job> --from <old EDL>`
  re-times every downstream layer through the source; **a re-record of an approved edit** is frozen into
  `projects/<job>/reference/<label>/` first and re-timed by the words (`--retake`). Owner: `edit-video`.
- **Live state that disagrees with RUN.md is your hand edit, never a failed write:** reported and left
  alone. Owner: `edit-video` § THE FIRST THING, ALWAYS.
- **Live app state is READ before a deictic is interpreted** ("the section I marked", "at the
  playhead"): query the marks, selection and playhead first; clear marks after acting. Owner: `edit-video`.
- **Broken audio on a finished chat-only render = re-promote the assemble render, never realign.**
  Owner: [`lanes/chat-only/incremental-graphics.md`](lanes/chat-only/incremental-graphics.md) § Broken audio on a finished render.
- **Both caption presets are LOCKED** and built ONLY from the canonical transcript, as a step-5 alpha
  layer the lane places like any overlay; each builder fails a dropped word or a line lit before its
  first word. PIL + ffmpeg (this ffmpeg has no drawtext, don't install one). Owners:
  [`captions-style.md`](presets/instagram/talking-head-explainer/captions-style.md) ·
  [`tiktok-raw-style.md`](presets/tiktok/raw/tiktok-raw-style.md).
- **Talking Head Explainer face framing = LOCKED, measured** (hair top 100 px under the y960 seam in
  split); `face-frame.py --verify` on the split spans must PASS before review. Owner:
  `presets/instagram/talking-head-explainer/layout.md` § 2.
- **The Talking Head Explainer is a LAYOUT ROTATION ON HARD CUTS**, planned per sentence into the
  plan's `layout` map; graphics enact, captures are real, the call to action never leaves split; its
  sound pass starts where a hand pass ends; a second voice over 3 dB under is lifted and announced.
  Owner: `presets/instagram/talking-head-explainer/README.md` (+ its `sfx.md`).
- **Graphics builds: one comp per graphic** (long-form: an emitter only for split-part builds; the
  Talking Head Explainer's kit `build.py` emits every graphic). The base rough cut is NEVER
  re-rendered. Gotchas: `graphics-build`.
- **THE GRADE GOES UNDER THE GRAPHICS, AND THEREFORE BEFORE THEM**, look locked to Autumn-Rec709 at
  80/120. WHAT: [`presets/youtube/default/README.md`](presets/youtube/default/README.md) § Grade. HOW:
  [`LANES.md`](LANES.md) § step 4.
- **Screen-recording FOOTAGE stays bare: no graphics, no grade, unasked;** a screen-recording GRAPHIC
  the editor captures is a normal step-5 cell. **Recording sections SHOW it: the mouse points, nothing
  is read.** Owner: `presets/youtube/default/README.md`.
- **The run is as long as the ask.** A named step runs that step and stops. Owner: `edit-video`.
- **Blue is the underlay; what sits on it takes its own colours** (a depicted product wears its real
  UI, a card over footage is clear glass). Owners: `presets/youtube/default/backgrounds/README.md` ·
  `default-overlay-style.md` § COLOUR VARIETY.
- **A mark on a recording is tracked by registration, never OCR, and laid on a normal blend.** Owner:
  [`presets/youtube/default/highlight/README.md`](presets/youtube/default/highlight/README.md).
- **A screen capture is a PLANNED cell, never improvised, and text is never captured** (a prompt, a
  command or a quote is rebuilt verbatim as a graphic). Owner: `graphics-plan` § THE CAPTURE GATE.
- **A still of the creator inside a graphic is CAST, never grabbed** (`workflows/hero-frame.py`, picked
  by eye). Owner: `graphics-plan` § THE HERO-FRAME GATE.
- **Centred means the COMPOSED row, never the type alone.** Owner: `presets/youtube/default/creative-moves.md` move 2.
- **The craft rules are measured, not eyeballed:** density, entrances and exits from the registry
  (type NEVER pops), overshoot, motion blur, full-screens as SCENES, the low band and side callouts
  (`workflows/chin-line.py`), prop glow, the 2–3 s readable hold, computed arrowheads. Owners:
  [`creative-moves.md`](presets/youtube/default/creative-moves.md),
  [`animations.md`](presets/youtube/default/animations.md),
  [`default-overlay-style.md`](presets/youtube/default/default-overlay-style.md); the Talking Head
  Explainer's own (hard cuts, at most 2 full-screens per 120 s): its `graphics.md` and `layout.md`.
- **Completion is checked against your ORIGINAL REQUEST, not just the graphics plan.** Owner:
  `edit-video` § Request coverage.
- **On-screen secrets are SWEPT, never spotted by eye:** list what must not show in
  `projects/<job>/pii.json`, sweep with `uv run workflows/pii-scan.py projects/<job>`, record app windows
  behind `workflows/screen-record.sh --preflight`, confirm hits by eye before blurring. Owner:
  `edit-video` § Step 0, item 9.
- **A video that claims it was edited in one pass is BUILT that way:** nothing copied in from an
  earlier job. Owner: `edit-video` § Step 0, item 8.
- **Final Cut runs ONE patched copy, started by its path through `uv run lanes/finalcut/doctor.py --repair`;**
  after two failed bridge connects, run the repair yourself. Owner: `lanes/finalcut/lab-notes.md` § 21.
- **Per-app locks live with the app**, in `lanes/<app>/lab-notes.md`. Read the one for your lane
  (Premiere's: its § Every step plus the section for your step); nothing in it applies to another app.
- **hyperframes is PINNED and bumped deliberately** (`hyperframes@0.8.105`, matching `setup.sh` and
  `SETUP.md`, its npm tree frozen by `npm_config_before` = setup.sh's `HF_BEFORE`), held on purpose:
  later releases draw colour-fringed text on Windows. Never `hyperframes upgrade`.
- **Alpha overlays are BT.709, tagged:** keep the explicit 709 tail on any encoder you add. Owner:
  `presets/youtube/default/reference/fullscreen-render.sh` § THE COLOUR TAIL.
- **Every Python package a tool runs is at least two weeks old, and locked:** a script with
  dependencies carries `# [tool.uv]` + `# exclude-newer = "14 days"` and ships a `<script>.py.lock`
  (`uv lock --script <file>` in the same change as any header edit); never `pip install` into a tool's
  environment.
- **A text-format ffprobe read of a video stream takes its first row, or reads JSON** (ffprobe 9 prints a
  timecoded file's video row twice).
- **Three optional HyperFrames extras need a workaround:** `motion-graphics`' grounding `locate.mjs`
  needs `drawtext` (take its `grounding/PROTOCOL.md` degradation path), `media-use`'s `dither.mjs`
  cannot write `.webp` (write `.png`), `hyperframes-creative`'s `extract-audio-data.py` needs numpy
  (`uv run --exclude-newer "14 days" --with numpy <its path>`).

## Your rules

The user's own standing instructions, from [`my-rules.md`](my-rules.md) (an update never changes that
file). Where one conflicts with a rule above, theirs wins for their videos.

@my-rules.md
