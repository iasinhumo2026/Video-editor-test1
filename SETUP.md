# 🛠️ Setup — read this first

This is a **video editing system you run with [Claude Code](https://claude.com/claude-code).** You
drop in raw footage, and Claude takes it from **raw → fully edited → exported.** It does short-form
explainers, TikTok/raw-style verticals, and long-form YouTube intros, with locked, on-brand captions,
graphics, colour and sound design.

**Runs natively on macOS, Windows, and Linux.** On a Mac it uses Apple's hardware video encoder; on
Windows/Linux it uses software encoding — same output, just a bit slower. **A Mac needs Apple Silicon (M1 or later) on
macOS 15 or newer:** Homebrew, which installs the tools, ships ready-made builds only there, so `./setup.sh` stops on
an Intel Mac or an older macOS before installing anything.

The fastest path: unzip, open this folder in Claude Code (the one named `video-editor`, with `setup.sh`
and `CLAUDE.md` in it; Windows' Extract All puts it one level down), and say **"Set this up on my
machine"**. Claude detects your OS, runs the one-command auto-installer (**`./setup.sh`**: installs every
tool via Homebrew on macOS / winget on Windows, bootstraps the render engine, verifies itself,
**auto-detects your editing app** (Premiere Pro / DaVinci Resolve / CapCut / Final Cut Pro) and wires its lane, and
is safe to re-run), and walks you through the one or two restarts along the way. If you have several
editing apps installed it asks one question: which one you edit in. That's the whole setup.
Personalizing the look/voice (your brand kit) is **optional** and can happen any time later, or
never. Everything below is the same setup by hand, if you prefer to see each step.

### 🪟 On Windows — one install first

No WSL, no virtual machine — the system runs natively. Its scripts run through **Git Bash**, the
Unix shell that ships with **Git for Windows** (it's also the shell Claude Code itself uses on
Windows), so that's the one thing to install first:

1. Install **Git for Windows**: `winget install Git.Git` (in PowerShell), then restart Claude Code
   so it finds Git Bash.
2. Unzip the project **outside Documents, Desktop, Pictures, Videos, Music and OneDrive**, e.g.
   `C:\Users\<you>\video-editor` (Windows Explorer's Extract All is fine), and open that folder in
   Claude Code. Those folders are guarded by Windows Security's Controlled Folder Access on many
   machines, which silently blocks Git Bash, node and python from writing there, and the error
   reads "No such file or directory", not "permission denied". `./setup.sh` checks for this first
   and says what to do.
3. That's it. Everything below runs unchanged; wherever a command says `brew`, use the
   **Windows (winget)** version below. After any `winget install`, open a **new** terminal
   (and restart Claude Code once) so PATH picks the tool up.

---

## 1. Install the prerequisites

**The automatic way** (recommended; auto-installs on macOS + Windows, prints the exact apt
commands on Linux and finishes the rest there too):

```bash
./setup.sh
```

It detects your OS, installs everything missing (and upgrades a tool older than the editor needs),
bootstraps the render engine, verifies (the versions, then a 30-second self-test that runs a short test cut
through the pipeline), then auto-detects your editing app and wires its lane (one app: wired automatically; several: it asks
which you edit in). Re-run it after any restart: it skips what's done and finishes the rest. (The
one manual step it can ask of you: installing Homebrew itself on a fresh Mac, which needs your
password; after that it finds Homebrew and puts it on your PATH itself.) It tells you exactly when a
Claude Code restart is needed; at most two once setup starts (once when just-installed tools or
Homebrew's PATH need a fresh session, once after an editing-app MCP is wired), plus the one-off
Git for Windows restart above if you needed that. Setup pre-approves the editing app's connection, so
after the MCP restart there should be nothing to click; if Claude Code does ask whether to enable this
project's `.mcp.json` servers, answer yes. (Clicked no? Claude clears it with `claude mcp
reset-project-choices`, then one more restart.)

**The manual way** — run the report-only checker and follow what it prints:

```bash
./check-setup.sh
```

### Core (required — the raw → exported pipeline)

`./check-setup.sh` prints the right command for whichever OS you're on — run it and follow what it shows.

**macOS:**

```bash
# Homebrew (skip if you already have it)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew install ffmpeg          # every audio/video pass (cut, captions, music, render)
brew install uv              # builds the WhisperX transcription engine on first run
brew install node            # the graphics render engine (npx hyperframes)
brew install python          # the pipeline scripts (the Command Line Tools' python3 3.9 is too old)
brew install yt-dlp          # optional: downloading reference clips + YouTube research
```

**Windows (winget — built into Windows 11 / App Installer):**

```bash
winget install Gyan.FFmpeg           # every audio/video pass (cut, captions, music, render)
winget install OpenJS.NodeJS.LTS     # the graphics render engine (npx hyperframes)
winget install Python.Python.3.12    # the pipeline scripts
winget install astral-sh.uv          # builds the WhisperX transcription engine on first run
winget install yt-dlp.yt-dlp         # optional: downloading reference clips + YouTube research
```

> Open a **new terminal** after the winget installs (and restart Claude Code once) so PATH updates.
> Note: on Windows, Python is `python`, not `python3` — the `python3` name there is a fake
> Microsoft Store stub. The pipeline scripts handle this automatically.

**Linux (Ubuntu / Debian):**

```bash
sudo apt update
sudo apt install -y ffmpeg unzip python3 python3-pip fonts-dejavu-core   # video passes + the render engine's unzip + the caption mono
# ffmpeg must be 5.1 or newer: Ubuntu 22.04 and Debian 11 ship 4.x, so there unpack BtbN's static build
# (ffmpeg-n7.1-latest-linux64-gpl-7.1.tar.xz, https://github.com/BtbN/FFmpeg-Builds/releases) and put its bin/ first on PATH.

# Node ≥22.12 (the render engine) — Ubuntu's apt node is too old, so use NodeSource's current LTS:
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt install -y nodejs

# uv (builds the WhisperX transcription engine on first run):
curl -LsSf https://astral.sh/uv/install.sh | sh

sudo apt install -y wamerican   # optional: enables the transcript-QA word scan
uv tool install yt-dlp          # optional: reference clips + YouTube research (apt's build is too old for YouTube)
```

Then bootstrap the render engine **once**:

```bash
npm_config_before=2026-10-01T23:59:59Z npx -y hyperframes@0.8.105 browser ensure   # one time, about 270 MB: the render engine and its headless browser
```

> **Minimum versions** (`./check-setup.sh` checks each and names the upgrade): ffmpeg 5.1, uv 0.9.17, Node 22.12,
> Python 3.10.
>
> Pinned to `@0.8.105` — the version the locked caption/graphics presets were validated against, and frozen to the
> npm packages it was validated with (npm_config_before, the end of the pin's validation day; in PowerShell set
> `$env:npm_config_before="2026-10-01T23:59:59Z"` first).
> Using the same version for the one-time bootstrap means it's cached once and every render uses it.
> Its npm and telemetry notices are noise; ignore any "newer version available" line and never run
> `hyperframes upgrade`.
>
> **On Linux,** if the bootstrap (or a render) stops on "no zip archiver" or a missing shared library, install
> unzip and the headless-Chrome deps it names, e.g.
> `sudo apt install -y unzip libnss3 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libasound2t64`.

**First edit is slow, once.** The first time you run a job, the rough-cut step downloads the WhisperX
`large-v3` speech model (~3–5 GB) and builds its environment. That takes several minutes and needs
internet — but only the first time. Every job after is fast. **Your hardware is auto-detected:** an
NVIDIA GPU (Windows/Linux) transcribes on CUDA, several times faster than CPU (the first build adds
the ~3 GB CUDA stack), and if the GPU path ever fails it falls back to CPU automatically, so
transcription always works. The GPU build is verified, not assumed: the transcriber probes CUDA
after installing it and records what actually works, and if it ever has to fall back it prints a
loud SLOW PATH banner rather than quietly taking several times longer. Macs and GPU-less machines
run the reliable CPU path. **If that first build
is interrupted** (a closed laptop, a dropped connection), nothing is left half-broken: the transcriber
records a `.deps-ok` sentinel only once the environment is complete, so on the next run it sees the
incomplete state, wipes `~/.cache/video-editor/whisperx-venv` and rebuilds cleanly. (Same idea, much smaller: the face-framing
tool `workflows/face-frame.py` auto-installs its OpenCV dependency via `uv` on first use, ~50 MB.)

### Fonts — bundled, plus one system font

- **Inter** — bundled in `assets/fonts/` (free, Open Font License). The display font for the Talking Head
  Explainer graphics and liquid-glass. Nothing to install — and it's the cross-platform default. *(macOS only:
  prefer Apple's SF Pro?* Install the free "San Francisco Pro" pack from <https://developer.apple.com/fonts>
  and set it in `brand-kit.md`. On Windows/Linux, stay on the bundled Inter.)
- **The caption mono** (the Talking Head Explainer's captions) is the one system font, and one of these
  must exist: SF Mono or Menlo (macOS, both already there), Consolas Bold (Windows, already there) or
  DejaVu Sans Mono Bold (Linux: `sudo apt install -y fonts-dejavu-core`, in the apt line above).
  `captions.py` names the font it used. With none of them, `./check-setup.sh` counts it missing and
  prints that fix, since the captions step cannot run without one.
- **SF Pro (system)** — *optional.* The TikTok/raw overlays render from bundled **Inter** by default; SF Pro is not required.

### Optional (only if you use the feature)

- **Premiere lane** (the recommended finish if you edit in Premiere — the rough cut
  lands on your timeline as **separate, trimmable clips**, and Claude can build graphics, apply
  effects, recolor sections, and run the final export in there too): one command,
  ```bash
  ./setup-premiere.sh
  ```
  It installs the pinned Premiere MCP engine (`vendor/premiere-mcp`, built from source at a verified
  commit), installs the **MCP Bridge (CEP)** panel into Premiere, and writes `.mcp.json`. Safe to
  re-run; it skips what's already done. Requires **Adobe Premiere Pro** (validated on Premiere Pro 2026, 26.x) on
  **macOS or Windows** — plain Linux has no Premiere, use the default chat-only pipeline.
  Afterward: restart Premiere (setup patches the panel to start the bridge itself, so there is
  nothing to click) → restart Claude Code once (through `./setup.sh --lane premiere` the connection is
  pre-approved; run directly, answer yes when Claude Code asks) → verify with `node lanes/premiere/premiere-bridge.mjs ping`.
- **DaVinci Resolve lane** (the same finish, in Resolve on macOS, Windows, or Linux; needs
  **DaVinci Resolve Studio 21.1 or newer**): one command,
  ```bash
  ./setup-resolve.sh
  ```
  It wires Blackmagic's own MCP server (`ResolveMCP`, which ships inside Resolve Studio 21.1+) as the
  `davinci-resolve` entry in `.mcp.json` (other servers are left untouched). Nothing is downloaded or
  built, and it is safe to re-run. **Older Resolve:** setup stops and changes nothing; update Resolve
  (DaVinci Resolve → Check for Updates), then run it again. **Free edition:** not supported. Blackmagic's
  MCP is Studio-only, and 21.1 took scripting out of the free edition, so nothing can drive it: upgrade
  to Studio, or finish in CapCut or in chat. (An activated Studio detected as free:
  `./setup-resolve.sh --studio`.) Resolve just has to be running (Claude can launch it), and there's
  nothing to change inside it: **External scripting = Local is its default** (only if the connection
  fails, check **Preferences → System → General → External scripting = Local**). Afterward: restart
  Claude Code once (through `./setup.sh --lane resolve` the connection is pre-approved; run directly,
  answer yes when Claude Code asks) → verify by asking Claude to get the Resolve version. The
  `davinci-resolve` skill documents everything the lane can do, plus the API calls to avoid.
- **CapCut lane** (the same, in the CapCut desktop app — macOS and Windows): nothing to
  install beyond CapCut itself. `uv run lanes/capcut/capcut-bridge.py replay <job>` writes the rough cut
  as a native CapCut draft, one trimmable clip per cut. **Quit CapCut fully before running it** (it
  clobbers new drafts on exit otherwise). Full lane rules + live-editing commands: the `capcut` skill and
  `lanes/capcut/lab-notes.md`.
- **Final Cut Pro lane** (the same finish, in Final Cut Pro on macOS; the App Store's one-time purchase or
  Apple Creator Studio, 12.0 or later): one command,
  ```bash
  ./setup-finalcut.sh
  ```
  It installs **SpliceKit** (an open-source tool, MIT; the pinned release, checked against its published
  checksum), which makes a **separate, patched copy** of Final Cut in `~/Applications/SpliceKit/` with a bridge
  inside that Claude drives. Your App Store Final Cut is never changed, and libraries work in both. **One click
  from you:** setup quits Final Cut and opens SpliceKit, you click **Continue**, and it tells you when it's done (the
  same click again after every Final Cut update). Setup also puts the house look into Final Cut's Custom LUTs
  and writes the `splicekit` entry into `.mcp.json`. Safe to re-run. Afterward: restart Claude Code once. Claude
  starts the PATCHED copy itself when it edits for you (it closes your App Store Final Cut first if that one is
  open, because only one Final Cut can run at a time); you never need to open it. Claude builds each
  timeline from your job's files, brings it in through Final Cut's own importer, and exports with no clicks;
  the `final-cut-pro` skill documents the lane.
- **Speaker labels** (`rough-cut --diarize`): accept the terms of `pyannote/speaker-diarization-community-1` on
  Hugging Face and set `HUGGINGFACE_TOKEN`, in the environment or in this folder's `.env`, which the transcriber
  reads (see `.env.example`). The normal single-speaker flow does **not** need this.
- **On-screen secret sweep** (`workflows/pii-scan.py`, for screen-recording or live-call footage):
  macOS reads the frames with the system's own OCR through a small Swift shim (needs the Xcode command
  line tools, `xcode-select --install`); Windows and Linux use `workflows/ocr_shim.py` (RapidOCR, which
  `uv run` installs on first use, offline after its models download; on Windows it runs on the GPU through
  DirectML, about 0.12 s a frame, any DirectX 12 GPU, with the CPU, about 1 s a frame, as its fallback). The slice-ASR checks, `cut-audit.py`'s content gate (with `--say` and
  `--spans-out`) and the Premiere lane's `cut-proof.py`, run mlx-whisper on macOS and the WhisperX venv's
  faster-whisper everywhere else (`workflows/asr_cli.py`; CUDA when the venv has it), so they need one
  transcription first to build that venv.
- **yt-dlp** (downloading reference clips and YouTube research for graphics): nothing in the pipeline
  calls it, it's a hand tool. `./setup.sh` installs it for you on macOS and Windows; on Linux run
  `uv tool install yt-dlp` (apt's build is too old for YouTube). Clips headed into Premiere must be
  H.264 (the format string is in `lanes/premiere/lab-notes.md`).

---

## Permissions: fewer prompts, or none

Claude Code asks before it runs a command ("Allow once" / "Always allow"). Two things cut that down.

**This folder's own rules (nothing to do).** The editor ships `.claude/settings.json`, which
pre-approves its routine commands (setup, update, `uv run`, ffmpeg, the render engine, the
editing-app scripts) and sets Accept edits (file changes without asking) as the starting mode. The
rules apply once you trust the folder (Claude Code asks the first time you open it), and only when
Claude Code is opened on this folder itself, the one with `CLAUDE.md` in it. Anything else still asks.

**The permission mode, for no prompts at all** (an edit left running overnight, say). The mode
selector sits next to the send button; `Cmd+Shift+M` on a Mac (`Ctrl+Shift+M` on Windows) opens it.
What you pick there applies to that chat.

- **Pro or Max plan:** open Settings (`Cmd+,` on a Mac, or click your name, then Settings), go to
  **Claude Code**, search "bypass" and turn on **Allow bypass permissions mode**. Then pick **Bypass
  permissions** in the mode selector; if it does not show there, start a new chat. Bypass skips every
  check, so turn it on only on a machine where you are fine with Claude running anything in this
  folder unasked (Anthropic's docs recommend it only inside a container or a VM).
- **Team or Enterprise (an organization account):** there is no bypass toggle for you; the
  organization's policy decides. Pick **Auto** instead: a reviewer model checks each action, and it is
  on by default for Team and Enterprise unless the admin turned it off. If the selector shows no Bypass
  at all, that is the policy, and `/status` lists organization settings under "Setting sources". If
  picking Auto says the mode could not be changed, start a new chat and pick it again; if it is still
  refused, the admin turned Auto off, and Accept edits plus this folder's rules is what is left. If you
  own the organization, its Claude Code policy is in the admin console under Organization settings →
  Claude Code → Managed settings.

In the terminal version of Claude Code, Shift+Tab cycles the modes instead.

---

## 2. Make it yours (optional: any time, or never)

The editor works out of the box with a neutral bundled look (Inter fonts, a generic starter
palette). Personalization only makes captions and graphics sound and look like *you*.
Whenever you want that:

1. **Fill in `brand-kit.md`** — your name, niche, handles, voice/tone, brand colors, fonts, hook style,
   and brand wordlist. This is the one file that drives how every caption and graphic sounds and looks.
   (Part A is the fill-in form; **Part B** spells out exactly which file and token each value changes, if
   you want to do it by hand or verify Claude's work.)
2. *(Optional)* **Add your logos** to `assets/logos/` — any brand marks you want available for graphics.

Then tell Claude **"apply my brand kit"** and it writes those values into the presets and `my-rules.md`
(which no update ever changes) for you (the exact map is Part B of `brand-kit.md`), and renders a quick test so you can see the look
took.

---

## 3. Edit your first video

1. Put a raw clip somewhere handy (e.g. `~/Downloads`).
2. In Claude Code, say: **"edit this video: ~/Downloads/yourclip.mp4"**.
3. Claude copies it into `projects/<job>/raw/`, runs the rough cut, plans graphics, and walks the rest
   of the pipeline with you. It auto-detects the format from the footage (vertical = short-form,
   horizontal = long-form YouTube) and states the hook + takeaway it read from your transcript;
   correct it in a word if it read wrong.
4. The finished deliverable is `projects/<job>/outputs/<job>.final.mp4` (promoted by `./finalize.sh
   <job> --apply`, which also drops an export copy in `~/Downloads/`, ready to upload).

That's it. The whole pipeline and how each step works is documented in `CLAUDE.md`.

---

## 4. Update to a new version

New versions ship often. Download the new zip, keep working in the folder you already have, and tell
Claude **"update"**. It finds the newest download in your Downloads folder (by its version, so a second
download named `video-editor-client (1).zip` is fine) and merges it in without touching your changes:
your presets, skills, brand kit, rules and jobs stay yours, and anything you and the new version both
changed is sorted out with you. Your own standing instructions for Claude go in `my-rules.md`, which no
update ever changes. Changed your mind? Tell Claude **"undo the update"**.

**Installed any version up to 2026.09.25.2?** The first time, tell Claude instead: **"unzip the newest
video-editor zip from my Downloads into a NEW empty temporary folder (never over my editor folder), then run
that folder's update.py on this folder."** After that, "update" is all it takes.

---

## What's in the box

| Path | What it is |
|------|-----------|
| `CLAUDE.md` | The editor's brain — the pipeline, the rules, the format variants. |
| `brand-kit.md` | Optional personalization: fill it in whenever you want the output to carry your brand. |
| `setup.sh` | One-command auto-setup: detects macOS/Windows, installs everything, bootstraps the renderer, wires your editing app's lane. |
| `check-setup.sh` | Prerequisite checker (report-only). |
| `update.py` | Brings in a new version without touching your changes (§ 4). |
| `my-rules.md` | Your own standing instructions for Claude; updates never change it. |
| `.claude/skills/` | The editing skills + the HyperFrames render toolkit. |
| `presets/` | The locked looks, one folder per preset — **`youtube/default/` (THE long-form default: the overlay cards + the creative-moves vocabulary)**, the Talking Head Explainer (short-form: layout rotation, graphics, captures, captions, sound), TikTok/raw, liquid-glass, the vox print-collage long-form look (which carries `motion-craft.md`, its own craft rules — vox-only, never the default). |
| `workflows/` | Universal utilities (`voice-gain.py` for step 3, `sfx-plan.py` for step 6, face framing, chin line, the graphics QA gate, hand tracking, window capture and recording, the on-screen secret sweep, the second-camera lip-sync measurement, and the re-cut ripple). Nothing app-specific. |
| `lanes/` | Everything app-specific, one folder per editing app: `premiere/` (bridge, launch, grade, placement scripts + templates), `resolve/` (`resolve-templates/` fps-matched project templates, `resolve-grading/` the color playbook, `resolve-export.md` delivery-render settings, `resolve-audio-polish/` the final audio pass), `capcut/` (the bridge + schema templates), `finalcut/` (the FCPXML replay, the export and `setup-finalcut.sh`'s patched copy of Final Cut, macOS only), `chat-only/` (the ffmpeg assemble sheet). Each carries a `lab-notes.md` with that app's own gotchas. `LANES.md` at the root says, per pipeline step, which app has a scripted recipe and where it lives. |
| `assets/` | Fonts (bundled) + the face-detection model + `luts/` (30 cubes, with the house **Autumn-Rec709** look captured and ready so step 4 grades itself) + `sfx/` (the full SFX library the presets were tuned on, 149 clips, so step 6 runs with nothing else to download) + `logos/` for your own brand marks (you supply). |
| `projects/` | Your job folders land here (one per video). A finished job you no longer need moves off whole: to an external drive when one is connected, otherwise to the Trash (Recycle Bin on Windows). Ask Claude to clear it out. |
| `finalize.sh` | The export step — promotes the final render to `outputs/<job>.final.mp4` and copies it to `~/Downloads/` (dry-run by default). |
