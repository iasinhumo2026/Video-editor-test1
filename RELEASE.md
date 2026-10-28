# Release notes — Claude Video Editor client package

What changed in each version, newest first. To update, download the new zip and tell Claude "update" (SETUP.md § 4).

## 2026.10.16

The Talking Head Explainer comes out much closer to final on the first pass, setup proves your computer can run every tool before the first edit, the fixes asked for on the October 13 office hours are in, and Claude's instructions are lighter.

- Talking Head Explainer, rebuilt from a second finished short: real screens fill the whole top half on their own color instead of sitting cropped on a band, and run under the captions. The caption box is darker so every line reads over any screen
- Split-screen framing keeps a little space above your hair and centres on your shoulders and neck, even when you lean your head
- New first-pass graphics: a hook that opens on your real result, zoomed and marked as you say it; short title cards for the names your video is about, each with an object that acts them out; an app's screen rebuilt in its own look when a recording would not fit; payment notifications on a phone
- A zoom onto a number on a page is now fast, smooth and straight, never the recording app's wobbly auto zoom
- Money moments get a cha-ching on the first pass: your revenue figure as it is revealed, and payments landing, a quick run where the last one rings out
- The first cut takes your most energetic read of the hook, not just the last one, and drops recaps, side tangents and hype lines before you have to ask
- A sponsor's brand stays white in the captions, whatever the brief asks
- Cutting a line at review is safer: every graphic, sound and the music bed move with the cut, and copies left behind from before the cut are found and removed
- A screen recording cutting to a smaller one no longer flashes the old page for a frame
- If you record with Screen Studio, version 4.0.4 now works with Claude's scripted recordings
- Claude's instructions are about a third shorter, so each session starts with less to read and uses less of your plan
- Setup checks that every tool is new enough and runs a quick test edit before it says you are ready. A Mac needs Apple Silicon (M1 or later) on macOS 15 or newer
- When a tool on your computer updates later, Claude asks to re-run setup, so nothing breaks in the middle of an edit
- Graphic colors now land exactly on your brand colors in every editing app. They were slightly off before (white, grey and black never moved)
- Footage from cameras that record timecode, and iPhone portrait videos, are read correctly on the newest video engine. iPhone HDR video is caught at the start, with clear options
- On a Mac, chat-only edits now export on the Mac's video chip too, like Final Cut: up to three times faster, and your computer stays usable while it runs
- Every tool package is now a tested release at least two weeks old, so a brand-new release can never break your setup. On Windows, Smart App Control no longer blocks tools on first use
- Transcription runs on a tested, pinned version. The first one after this update rebuilds its tools once (a few minutes). Speaker labels need the new model's terms accepted (SETUP.md)
- The privacy sweep checks every recording in a video for numbers and keys, not just the first one
- Cut checks run about three times faster, and a check that could not run says so instead of passing
- Chat-only renders: a mono microphone is as loud as a stereo one, and a camera mixed with a screen recording of another size renders instead of stopping
- Final Cut: the one-time purchase works as well as Creator Studio (Final Cut 12 or later)
- Graphics review is one round now: the automatic check, one fresh look, the fixes, the check again. Much faster, far less usage. Small changes at review (one caption, one graphic) happen right in the chat
- SETUP.md shows how to stop the "allow once" prompts, and the editor pre-approves more of its own commands (four of its rules never matched before)
- The rough cut no longer clips quiet word endings (the end of "advantage", a soft s, t or k)
- Transcribing a batch of videos no longer maxes out your computer: they run one at a time, in a queue
- A graphic that blanks or jumps for a single frame mid-animation is caught automatically before you watch it, and captions can no longer appear before the word is spoken
- You can now build a preset that places your own B-roll clips (the shipped presets use none)
- Sound effects: Claude can now place them on a DaVinci Resolve timeline, every editing app can load the whole sound pack into a bin for hand placing, and a repeated sound no longer plays the exact same hit twice in a row
- When an edit is finished, Claude offers to bake what you taught it into your preset, so your next video like it comes out right the first time. Baked rules stay through every update

## 2026.10.13.2

On a Mac, the final export runs on the Mac's video chip: up to three times faster, and your computer stays usable.

- On a Mac, Final Cut exports, clips and the 4K Shorts file are made on the Mac's video chip: up to three times faster on a fraction of the processor, same quality and settings

## 2026.10.13.1

Final Cut on an Intel Mac: pressing play no longer crashes Claude's copy of Final Cut.

- Final Cut on an Intel Mac: SpliceKit's Smooth Scroll crashed Claude's copy of Final Cut the moment you pressed play. Claude now keeps it off in that copy (your regular Final Cut is not changed)

## 2026.10.13

Fixes a crash on fresh installs.

- Setup now installs ffmpeg 9 (the video engine), which dropped an old setting a few tools still used. The flash check, the framing check, picking your still and placing graphics under your face crashed the first time they ran; they now work on every ffmpeg version
- If Claude already patched one of those on your machine, the update stops on that one file: keep the new version

## 2026.10.12

Final Cut users: the connection can no longer get stuck because of a second copy of Final Cut.

- Final Cut: with two Final Cuts installed (the one-time purchase and Creator Studio), or an old copy left behind after an update, Claude now picks the right one, says which, and moves the extra copy to the Trash
- Final Cut: if your regular Final Cut is open when Claude needs its own copy, Claude closes it and starts the right one itself. No more quitting and reopening apps by hand; the only thing it ever asks of you are the one click in SpliceKit
- Using Codex instead of Claude Code? The folder now includes an AGENTS.md that points Codex at the same instructions
- Fast moving graphics now get real motion blur in the finished video, not just in the preview
- Full-screen graphics stay centred and on screen after a late zoom or move

## 2026.10.05

DaVinci Resolve moves to Blackmagic's own connector, and sound effects, re-cuts and videos edited in sections are more careful.

- DaVinci Resolve now runs on Blackmagic's own connector, built into Resolve Studio 21.1 and newer: nothing to download. Setup asks an older Resolve to update first, and the free version (no scripting since 21.1) finishes in CapCut or in chat
- Sound effects are now leveled with the background music under them, in every section of a long video too, so a busy moment never peaks too hot
- A popping graphic can no longer cover the word beside it: the graphics check now looks at the rendered picture, not just the layout, and no longer fails two drawings whose boxes overlap while the shapes never touch
- On 4K footage, text animations render at 4K and at your timeline's exact frame rate
- Cut a pause out of the middle of a line by hand? The graphics and sound effects after it stay on their words, and a cold open that reuses a line's footage never takes that line's graphics
- In Premiere, a later section that a hand edit moved is re-timed before anything is placed, never laid a second time at its old spot. Sped-up clips read correctly too
- A reel or intro clip cut from your finished video and left beside it can no longer replace the final at export: finalize keeps them apart and says to give it its own folder
- Voice levels: an inserted clip, like a meme, no longer skews the measurement, and a demo that plays a finished video through the speakers is leveled in two parts
- Rough cuts keep more of how you really talk (a hedge before an admission, the run-up to a point, your spoken instructions in a live demo), and a mostly silent screen recording transcribes in minutes
- Graphics can follow a face or object the tracker loses, like a film character or a prop through a flash
- Have Content OS on the same computer? Setup and updates no longer mistake its folder for your editor folder
- Long videos where screen recordings carry the picture keep you on screen in a small rounded window in the corner, graded like the rest, with graphics on the recordings themselves

## 2026.09.28

Windows is fully supported now, and every editing app got more precise.

- Windows: Premiere, DaVinci Resolve, CapCut and the chat-only option all run start to finish. CapCut for Windows is new, and setup finds it
- iPhone footage: cuts, graphics and captions land on the exact frame in every editing app, and the picture stays in sync with the sound through long takes
- Text animations now use real Helvetica on a Mac and a matching free font on Windows. Captions on Windows use a matching font at the exact same size
- Exports come out at the same quality in every app, CapCut on Windows included, with the right color labels on Premiere files
- Stacked sound effects no longer clip, and clips cut from a finished long video no longer show half of its on-screen text
- On Windows, setup stops and tells you if the folder you picked is too deep, and a moved project folder repairs its own links
- On version 2026.09.25.2 or earlier? Tell Claude, one time: "unzip the newest video-editor zip from my Downloads into a NEW empty temporary folder (never over my editor folder), then run that folder's update.py on this folder." After that, "update" is all it takes
- A new version unzipped over your editor folder by mistake is now caught, and the update tells you how to recover

## 2026.09.25.4

Final Cut Pro is now a supported editing app on Mac, start to finish.

- Edit in Final Cut? Setup now finds it. It needs one click from you: a small helper app called SpliceKit makes a separate copy of Final Cut that Claude can drive. Your normal Final Cut is not changed
- Already set up and want to switch? Tell Claude "switch my editing app to Final Cut"
- In Final Cut, Claude builds the whole edit (cuts, audio, color, graphics, captions, sound effects, music) and exports the finished video with no clicks from you
- DaVinci Resolve: the audio polish now covers a section filmed separately, at its own level
- Talking Head Explainer: a layout switch can no longer land one frame beside a cut (it showed as a one-frame flash)
- Clearing out old projects: ask Claude to clear one out and the whole folder moves to your external drive when one is connected, otherwise to the Trash (Recycle Bin on Windows). The old cleanup script is gone

## 2026.09.25.3

Updating and first-time setup are smoother: say "update" and Claude finds the new download itself.

- To update, download the new zip and tell Claude "update". Claude finds the newest download itself. Downloads are now named with their version, so a new one never lands as "(1).zip" next to an old one
- Changed your mind after an update? Tell Claude "undo the update". Anything you did since stays
- Folders from before updating was built in now update far more cleanly: each file you changed is merged with the version it came from
- First update on a folder from before 2026.09.25.2? Tell Claude: "run the update.py from the newest video-editor zip in my Downloads on this folder"
- Installed 2026.09.25.2? This one time, tell Claude: "run update.py with the newest video-editor zip in my Downloads"
- Setup on Windows now says exactly what failed instead of asking for another restart, and setup no longer asks you to approve your editing app's connection
- Setup now finds DaVinci Resolve installed from the Mac App Store
- Your brand name, handles and voice now live in my-rules.md, which updates never touch. Anything you or Claude added to CLAUDE.md moves there on this update, so it never clashes with a new version again

## 2026.09.25.2

Updating is built in now: a new version merges into the folder you already use, and your own changes stay yours.

- To update, download the new zip, open the folder you already use in Claude Code and say "update from ~/Downloads/video-editor-client.zip". Your presets, rules, brand kit and jobs stay yours
- First update on a folder from before this version: say "unzip ~/Downloads/video-editor-client.zip to a temporary folder and run its update.py on this project". After that, the short version works
- Your own rules for Claude now have a home no update touches: my-rules.md

## 2026.09.25

Resolve users: the Resolve instructions now cover DaVinci Resolve 21.1. Nothing to re-run; the next edit just picks it up.

- On Resolve 21.1, sound effects and background music go on with their levels and fades already set, no more placing them by hand
- Resolve exports on 21.1 now come out at the quality setting the preset asks for (older versions ignored it)
- The house color look in Resolve now carries its strength and saturation too, checked against the same edit made in Premiere
- If you run Resolve Studio 21.1, its own built-in AI connection works with this folder as well, and the setup check recognises it

## 2026.09.24

A new short-form look, the Talking Head Explainer, plus fixes. Nothing to re-run; the next edit just picks it up.

- New short-form preset for talking-head explainers: the framing switches per sentence between split screen, tight, wide and full-screen graphics, on hard cuts
- It replaces the old short-form explainer preset (presets/instagram/explainer/): say "apply my brand kit" to carry your colours over to the new one (presets/instagram/talking-head-explainer/)
- Its captions are small mono caps in a see-through box, sitting on the split line or on your shirt, never on your face, and never dropping a word
- Your face is measured and framed the same way on every shot, with your hair kept clear of the graphics
- Real screen recordings of your app are planned in as proof, and every graphic acts out the line it sits on
- A voice through a speaker (an AI on a call, a phone) is brought up to sit just under yours when it is clearly quieter, and checked on a real bounce
- Sound effects play the actual object on screen (a ring, a send, typing) right on the word, from a ready-made sound map, and a phone ring sound is now in the library
- Recordings made in mono now come out at the same loudness as stereo (they were about 3 dB too loud)
- Checking the audio of a 4K clip no longer uses huge amounts of memory

## 2026.09.23

A big round of fixes from two short-form edits. Nothing to re-run; the next edit just picks them up.

- On Premiere, a script can no longer write onto the wrong project or the wrong timeline when you have several open
- Re-placed graphics come in at the right size on 4K timelines, and swapping one keeps any position you nudged by hand
- Sound effects land on the exact frame, and an ad version of a video can copy the original's sound design without touching its own ending
- The music bed starts on the exact beat you picked, and it can be refitted in one command after you trim the timeline
- Exporting a short from Premiere picks the right Instagram settings and checks the finished file before calling it done
- Hand trims you make on the timeline are read back correctly and carried into the next pass, even on footage shot at a different frame rate
- The cut checker no longer pushes a cut into a breath or flags a clean hand trim as a mistake
- The on-screen number check catches numbers with spaces in them and numbers inside file names
- New checks for short-form graphics, and for a jump in framing where a re-take or lip-synced clip was swapped in
- A lip-sync tool for sync.so is included, for re-voicing a line without re-filming

## 2026.09.20

Fixes and a few new defaults from a long tutorial edit. Nothing to re-run; the next edit just picks them up.

- Footage of you walking through your screen stays clean: no graphics and no colour look over it unless you ask
- Ask for one step and only that step runs; ask for the whole edit and it runs the whole line
- On long videos the main sections come colour-labelled on the timeline, so you can see the structure at a glance
- Text graphics land on the exact word you say, and a full-screen graphic holds until the next one instead of flashing back to your face
- A grid or wall of items is framed whole with room around it, instead of the camera panning across it
- The rough cut now spots where the transcript missed or made up words, like a phone call on speaker, before anything gets cut
- On a follow-along tutorial the rough cut keeps the steps, where things live and the proof it worked, and still drops recaps and side chatter
- On Premiere, the playback check no longer flags brand names or contractions as mistakes
- If you change the cut after graphics are placed, the graphics and sounds can be moved with it instead of rebuilt
- A new check finds a phone number everywhere it shows on screen so it can be blurred
- Measuring loudness no longer fails on long videos
- Several commands in the guides had lost a space and would not run when pasted; they copy and paste correctly now

## 2026.09.15

A round of fixes from two real edits. Nothing to re-run; the next edit just picks them up.

- On Premiere, the finished cut is played back, transcribed and checked against your script, so a doubled word or clipped syllable gets caught before you watch it
- The rough cut keeps small fillers inside a sentence and the lines that close a section, and still drops second hedges and repeated calls to action
- When a graphic shows a still of you, it picks a frame with your eyes open and your mouth closed
- Text with an icon beside it is centred as one unit, so it no longer hangs off to one side
- The house colour look is a little stronger, and it stays off screen recordings so apps and web pages keep their real colours
- A quoted article or headline uses simple cuts, with the quote big, centred and highlighted as you say it
- If you change something on the timeline between steps, the edit keeps your change instead of undoing it
- On Premiere, nothing runs while a different project is the active one, so another open project is never touched
- On CapCut, text placed behind you no longer glows white at the edges, and exports land where the final step looks for them
- On Windows, filming a second section works without turning on Developer Mode

## 2026.09.13

A round of fixes from a real edit review. Nothing to re-run; the next edit just picks them up.

- A prompt, command or quote you show on screen now stays full-screen for its whole explanation, complete and word for word, with the part you're saying highlighted as you say it.
- When a beat is about something on your screen (a folder, an app, a page), the plan calls for a real screen recording of it instead of a generic card.
- Dark full-screen scenes are spread across the whole video, so no long stretch goes without one.
- The closing of your video is kept whole: pauses and retakes still go, the sign-off never gets chopped.
- A new dead-air check runs on the final cut, so long pauses hidden under room noise no longer slip through.
- Background music starts where the song actually comes in and sits quieter by default.
- Highlights on long, split graphics no longer blink at the join.
- Sound effects: re-running the plan after a graphic moves tells you which rows changed, and placement refuses to save if any cue is missing, extra or drifted.
- Guardrails that used to live only in the author's private notes are now in the docs you get, so your edits follow the same rules.

## 2026.09.10

A round of polish on how long-form graphics look and sound. Nothing to re-run; the next edit just picks them up.

- Graphics beside your face are measured off your head now instead of placed by eye, so they never crowd you or drift off the edge
- A full-screen graphic is a short scene with a few moments and a camera move, not one static card you stare at
- Full-screen moments are spread through the video, so you never go a long stretch without one
- Text never pops onto screen. It rises in, or slams in with the bold look
- Every video opens on a slow zoom-out, and the zoom-in used for emphasis has smoother timing
- Sound effects follow what a graphic actually means, so a finished or successful moment rings instead of popping
- Fewer sounds stack on the same beat, so a busy graphic no longer sounds cluttered
- Slides and big moves get motion blur, so fast movement looks smooth instead of jumpy

## 2026.09.08

Fixes from a full end-to-end edit. Nothing to re-run; the next edit just picks them up.

- A graphic could end one frame before its cut and flash the last frame of the shot underneath. The placement tool now snaps every graphic to the frame and the checks catch a miss
- The graphics checker catches two more mistakes on its own: a fade that flashes black for a few frames, and a pop that lands on top of the element next to it
- Re-checking one graphic no longer wipes the full check report
- The review step has its own frame grabber, so the review evidence lands in the right folder every time and reviewers get the same brief on every job
- The prompt reviewer and the build notes now spell out that icons inside cards glow like every other accent prop
- Small things: the chin-line tool can save its measurement to a file, and the sound-effects planner tells you the exact file to fill in when it can't read a graphic on its own

## 2026.09.07

First Windows user found some bugs. All fixed. Already set up on Windows? Run `./setup.sh` again. On the free version of Resolve, also run `./setup-resolve.sh` once. If you have an NVIDIA graphics card and transcribing felt slow, delete the folder `~/.cache/video-editor/whisperx-venv` and it rebuilds right on the next edit.

- Windows + NVIDIA card: transcription actually uses your graphics card now. Before, it quietly ran on the CPU and took about 5x longer
- Setup checks it can write to your project folder before it does anything. On Windows, keep the folder out of Documents and Desktop, Windows blocks writes there. Setup tells you if you're in the wrong spot
- The free version of DaVinci Resolve works now. Setup figures out which version you have. One habit on the free version: after you open Resolve and your project, click Workspace → Scripts → resolve_bridge
- Resolve can't freeze Claude for 30 minutes anymore. If something's off, you find out right away
- Premiere export is one command: the final 4K file renders inside Premiere, no Media Encoder
- 4K videos: every graphic renders at real 4K now
- yt-dlp installs with the other tools, for pulling reference clips off YouTube

## 2026.09.05

- Captions are built with the graphics now, not burned on at the end. Re-render a video and the captions stay
- Sound effects run on short videos too, not just long-form
- Resolve audio polish uses the same loudness numbers as Premiere
- Background music is a normal add-on: flat bed, starts when the song actually starts, fades out at the end
- The docs got cut in half. Every rule lives in one place, so Claude opens fewer files per job
- The thumbnail maker left the package. This system stops at the exported video
- Cleanup: dead tools and one-off setup files removed

## 2026.09.03.2

- The one-shot edit: say "edit this video" once and the draft that comes back is finished. Every step run, every objective mistake already caught. You only watch for taste
- Every job runs the same 8 steps in order and keeps a RUN.md, so it picks up where it left off
- Rough cut: cuts land on the real audio edges, then two fresh reviewers check flow and slices before you see it
- Audio: gain measured per shoot, then the limiter. One command in Premiere
- Colour grade: one command puts the house look under the graphics
- Graphics: the default long-form pass includes word-synced text animations, punch cuts, slides, props and push-ins, about 12 beats a minute, all from one animation rulebook
- Two gates before you see anything: the plan is checked before rendering, every frame is checked after
- Sound design: every graphic beat gets a sound, placed on the Premiere timeline in one command. The full library ships in the package
- Setup is one sentence: open the folder in Claude Code and say "run the setup". At most one question and two restarts
- Works on Mac, Windows and Linux. The package is 84 MB smaller
