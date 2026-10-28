---
name: rough-cut
description: "Rough-cuts raw clips, every format (step 2): transcribes with WhisperX (large-v3 + wav2vec2 word alignment), kills filler and dead air, keeps only the essential lines, splices with FFmpeg. No captions, no B-roll. Triggers: rough cut, cut this video, trim this, chop this up, rough-cut, make a rough cut, tighten this cut. (Whole-edit phrasings like 'edit this video', 'do the whole edit', 'edit the latest project' belong to `edit-video`.)"
---

# Rough Cut — Transcript-Driven Edits

Raw talking-head clips into a tight rough cut: you transcribe, you decide the cuts, FFmpeg stitches. The goal is the **shortest reel that still delivers the value.**

## How to Trigger
- **"rough cut [job name]"** → that job folder; **"rough cut"** / **"cut this reel"** with no job named → the newest job folder (a path picks that folder)

---

## Folder Contract

**This skill starts at transcription.** Creating the job folder, copying the raw into `projects/<job>/raw/` (never moving it) and naming the job are step 1, Intake, owned by `edit-video` (layout + naming: CLAUDE.md § Folder Structure and § Job naming). No job folder yet → do intake first; if the content isn't obvious before transcribing, use a provisional folder and rename it before the splice.

Three durable paths get written under `projects/<job>/`: `transcript/words.json` (the canonical transcript), `transcript/cuts.json` (the EDL), `outputs/<job>.transcript.json` (the cut-aligned caption transcript). Scratch lives in `/tmp/video-editor/<job-name>/`, which macOS clears — never depend on anything living solely in `/tmp`.

**Intent is derived, never asked.** If `intent.md` exists, read it. Otherwise read the FULL transcript first and work out the hook (the strongest curiosity/tension line, often filmed mid-take and re-orderable to the front) and the takeaway (the one thing the viewer should leave with), then cut to serve those. No usable dialogue? Sample frames (`ffmpeg -ss <t> -i <clip> -frames:v 1 <out.png>`) and infer the subject + arc from what's on screen. State your read in one line of the report.

---

## The Edit Philosophy (non-negotiable)

**Short and snappy, max value per second.**

Every cut decision runs through this filter: **does this line deliver value?** (if not, kill it) · **is this the tightest version?** (if not, use the shorter take) · **would a viewer skip past this?** (if yes, it's dead).

**RELEVANT IS NOT NECESSARY — the #1 filter (2026-08-28, after a first cut ran
3:32 that should have been 2:00):** "just because it's relevant doesn't mean that it's
necessary... stuff that's like okay, cool, good to know, instead of need to know right now,
is fluff." A line survives only if the viewer NEEDS it right now, for understanding or for the
flow of the script; good-to-know context, how-I'll-do-it teases, second statements of a point
already made and warm-up framing are all relevant and all dead, and a prerequisite aside that sends
the viewer off to do a step the video is about to show anyway — when the two lines around it join
cleanly without it, it goes. (This is not the same as a preamble that sets context or a setup clause
its own next line depends on: those stay.) **The kill rate is an OUTCOME,
never a target (2026-09-04):** emphasis-heavy multi-take footage has landed at 60-75%
killed, a take where the speaker nailed the script might lose 20-30%, and whatever total the
necessity question produces is the right cut. The red flag is a kept line that fails that
question, never "kept more than half". An intro especially is pure momentum
(claim → problem → rules → stakes → go) — every beat that doesn't advance it goes.

**Format is auto-detected from the raw footage, never asked** — resolved at `edit-video` Step 0 and written into RUN.md (on the Talking Head Explainer, read its [`story-and-cut.md`](../../../presets/instagram/talking-head-explainer/story-and-cut.md) before the kill pass); probe every clip only when this skill runs alone (`ffprobe -v error -select_streams v:0 -show_entries stream=width,height:stream_side_data=rotation -of default=nw=1 <clip>`): **vertical** (height > width) → short-form, **horizontal** → long-form YouTube. **A rotation of ±90 swaps the two:** an iPhone portrait take CODED 1920x1080 with `rotation=-90` decodes (and plays everywhere) 1080x1920, so width and height alone read it as horizontal (2026-10-13). State the detected format in the report.

**Target length depends on that format:**
- **Short-form** (9:16 Reels/TikTok/Shorts) → aim **1–2 minutes**, the target *after* ruthless cutting, not permission to ramble. If the value fits in 40s, ship 40s.
- **Long-form** (16:9 YouTube) → **no length cap**, but no cap is not license: the necessity filter still governs. Cut for retention and structure, not to hit a number.

---

## Auto-Kill Rules (always apply)

When building `cuts.json`, automatically remove:

| Kill | Why |
|------|-----|
| Filler words: *um, uh, like, you know, so yeah, basically* — at a run's edge or in dead air | Dead weight. **Inside a flowing phrase a one-word filler STAYS (your 2026-09-13 hand pass):** you put back every mid-phrase filler kill ("I said, *uh*, I was like", "*you know*, when it came to *like* the pricing") and kept "finally, *uh*, before we wrap up" whole. Each mid-phrase kill costs a joint, and the joint is the bigger defect. A search PHRASE that carries its own pause ("let's see", "it seems to me", "how do I put this") is not a filler: it goes (rows below). |
| Stutters + false starts: *"I- I was gonna-"*, and a token that is a prefix or near-spelling of the NEXT word (a product name started, then said in full: *"Prem… Premiere Pro on max"*, 2026-09-13) | Breaks flow. `cut-audit.py` prints `⚠ possible false start` on the prefix case (2 hits in a 2,000-word section, one real). |
| Restarted takes | Keep the **last** take, kill the rest — you always want the latest take of a repeated line (warmest delivery). Don't compare takes. **The one exception is the HOOK:** among its complete, clean reads keep the most EXPRESSIVE one, heard, with the loudest kept speech and the widest pitch movement as the first read (a stand-in for "expressive": loudness also tracks mic distance), and name the pick and the runner-up in the report (2026-10-14: "I sounded a little dead in the first one... use a different take where I'm a little bit more expressive"). |
| Emphasis echoes: the same claim re-stated for punch (*"one prompt, one shot, one go... it was literally one prompt..."*) | Keep the STRONGEST single statement of each claim; every echo after it is fluff. A hook montage of restatements collapses to one claim + at most one punch ("One shot."). **The weaker line right BEFORE its stronger restatement is the echo** ("honestly, that part's a small thing. I'd much rather pay for the upgrade…" → the first dies, 2026-09-13). **Two things are NOT echoes (2026-09-13 hand pass):** the LANDING restatement that closes an argument — thesis ("I just prefer where this tool is going"), evidence, then "so overall I still prefer this one, and my gut says the same": the second is the payoff, keep the bookend — and a deliberate back-to-back repeat for emphasis ("it stopped right away. I hit the wall right away."), which is delivery.· the engineering archive. |
| A rhetorical question the speaker answers with no new claim: *"Is it perfect? I really don't think so."* | Filler in the shape of an argument (2026-09-13 hand pass). |
| A second hedge opening the sentence after a hedged one: *"To me, I feel like this one is overrated. It seems to me, there are two real options here…"* → kill "it seems to me" | A restart in different words; the thought already has its hedge. |
| A wrong connective: *"plug and play, but I also wrote the docs"* → kill "but" | The line stays, the hinge pointing the wrong way goes. |
| Reading-aloud searches on a screen recording: *"totaled about, let's see, 1,200 credits"* → kill "let's see" and the pause it sits in | The speaker is looking, not talking. |
| A second CTA in the outro: *"hope to see you in the next one if you want to stick around. If not, that's all good too."* | One CTA per video; the hedged repeat weakens the real one (2026-09-13 hand pass). The closure rule below still protects the sign-off around it. |
| Silences ≥ 0.65s (MEASURED on the envelope, AND read off the aligner's gaps then verified by ASR) | Dead air. `polish-boundaries.py` splits any interior quiet run ≥ 0.65s whatever the timestamps say (the aligner can stretch a low-probability word across a pause). Author the transcript-gap split anyway; the polish is the net. **A pin protects a segment's boundaries, not its interior (2026-09-13):** pinned segments are split too; `"keep_pauses": true` opts out for a deliberate pause. **On a screen recording the envelope cannot see the pause** (breath and room noise sit above floor + 10 dB: a 940 ms pause after "So" and 1.4 s inside a read-off-the-screen line shipped until razored by hand), so `cut-audit.py` also transcribes every aligner gap ≥ 0.9 s between two kept words (0.9 on paper is about 0.65 heard; the hand pass left eight 660–800 ms paper gaps alone), pinned segments included (`keep_pauses` opts out), and splits only when nothing is heard: a gap with a skipped word in it stays, flagged `⚠ holds speech the aligner skipped` (a hidden false start or filler to kill by hand). **Known miss:** a pause with no aligner words around it is found by neither pass, so a passage where the speaker reads the screen is checked by ear on the bounce.§ mechanism (8) · the engineering archive. |
| Tangents + asides that don't serve the hook/takeaway | Viewer time |
| Throat-clears, "okay let me start over" | Production noise |
| Orphan low-prob word before a kept take | A lone low-confidence word (prob ≲ 0.3) with a ≥1s gap right before a kept take is a false start WhisperX half-missed. Kill the fragment and start the segment at the real take; never keep the orphan as its own segment. |
| Preamble before the hook lands | Every reel opens ON the hook |
| Trailing verbal tics after a landed point: *"...5X more usage, okay?"* → cut at "usage" | The point landed; the tic is a ~0.5s tax. Mid-sentence tics are rhythm — keep those. A trailing tag directly before the section's landing line stays too ("…still the best option. Right." → the landing line, 2026-09-13): it is the beat before the payoff. |
| Meta-signposts about the video's own structure: *"so now what I'm going to do is cover..."*, *"you can skip to the next section"*, and how-I'll-do-it teases: *"my plan is to build a preset"* | The content announces itself. All three die: preview, skip-ahead courtesy, AND method tease (2026-08-28: "obviously I'm gonna explain how I do it later in the video"). **A signpost that turns a corner STAYS (2026-09-13 hand pass):** a section close ("that's my final thoughts on this") or a numbered step ("firstly, let's start with the numbers", "finally, before we wrap up") carries the viewer across the cut. What dies is the announcement that moves nothing. |
| Self-referential flexes: *"personally, I'm on the $200 a month plan"* | Status talk, not information. |

**The closing beat is content.** The VIDEO's own filmed closure and handoff — the sign-off, the goodbye, the handoff into whatever comes next — is not a disposable meta-signpost (the goodbyes inside an embedded demo call are not it: rule (c) below): keep it complete unless the user explicitly asks to remove it, and never reduce the closing passage to its final sign-off. Inside that passage the normal rules still apply: pauses, tics, false starts and retakes go, and a repeated sign-off collapses to the last take.

**Preserve the creator's cadence.** Don't surgical-kill every "like" — some are rhythm, some filler. Taste call.

**The keep/kill line (your 2026-07-29 hand pass): persuasion and personality are CONTENT — meta-narration is not.** Objection-handling ("can I do this on the free plan?"), the pitch, the value stretch, the walk-back for budget viewers, section preambles that set context — all of it stays, even in an "essentials only" cut. What dies is talk *about the video*, talk *about the creator's status*, and tics. Cut harder = tighten inside lines before deleting persuasion beats.

**A follow-along tutorial keeps what the viewer needs to keep their place (your 2026-09-19 hand pass on a walkthrough, where you put back 9 of my kills).** The viewer is DOING the build alongside, so these read like talk but are content: the step transition that says where we go next (*"So what we can do now is go to our…"*); the location answer inside a search (*"go to settings, I believe it's in, yeah, Settings and then API keys"*: the reading-aloud kill above is for a filler search phrase that locates nothing, never for the one that tells them where the thing is); the practical instruction even when it restates a line (*"so if you just click that link down in the description, it will be there for you"*); a short reaction that proves a claim about the tool (*"export, okay cool, that was really quick"*); the agent's reply read aloud as proof the setup took (*"53 tools, API key, default voice, Jarvis clone"*); the line that says WHY a step is done (*"that's like a clean voice sample"*). On a LIVE CALL inside a follow-along tutorial (the viewer is setting the call up alongside) the wait for the phone and about a second before and after the AI speaks stay: a call that snaps line to line reads staged. A demo call embedded in an explainer is the other case, cut to its proof beats: rule (c) below. What still goes on a walkthrough: a repeated *"there we go"*, a mid-phrase *"we're going to"* restart.

**Four more keep/kill rules, universal (the Talking Head Explainer's hand passes, 2026-09-20..22; its [`story-and-cut.md`](../../../presets/instagram/talking-head-explainer/story-and-cut.md) § 4.11-4.13 and § 5.6 carry the evidence):**

- **(a) Prosody decides a tail.** Never end a kept line on a rising mid-breath comma: the ear hears a sentence cut off, however clean the joint. A list tail said in the same breath ("et cetera", "and so on", "you name it") carries the sentence's falling melody, so it belongs to the sentence: keep it to where the voice falls and `pin_out` that OUT. Cut a tag only after a pause of 200 ms or more AND a terminal fall on the word before it. This is decided before the trailing-tic row above, which is for a point that has landed; a rising comma has not.
- **(b) Specific examples stay; a generic capability list goes.** A concrete use the viewer can picture is evidence and stays whole. A generic capability list tacked onto a claim after the proof ("…that can handle calls, tasks, anything, you name it") restates what was shown and dilutes the claim: it goes, the claim ends on its landing noun, and its graphic goes with it (a line is never kept to save a graphic).
- **(c) An embedded demo call (not the follow-along live call above) is cut to its proof beats:** the announcement, the other party's substantive lines, one reaction. The ring, the pickup, the greeting, direction asides to the agent and the goodbyes go: they are the mechanics of a phone call, the viewer needs the payoff, and the call ends the moment its proof lands. A call that IS the cold open keeps its greeting (without it the viewer is dropped into nothing).
- **(d) The other party's confirmation of an action is proof, not an echo:** keep it whole, to its own last word, with the question that set it up. The emphasis-echo row is for a speaker restating your own claim; a second party saying back what it will do is the beat where it is seen to understand and act.

**Seven more, universal (a long-form hand pass, 2026-09-28):**

- **(e) A hedge run before a hard admission is delivery, not filler:** *"I would say, like, I hate to say this guys, and I really try, I'm not trying to like replace or take anyone's job"* ships as ONE segment with only its pauses removed. Killing "like" and "and I really try" cost two joints and you put both back. The mid-phrase filler rule above, applied to the whole run: never split a confession to shave its hedges.
- **(f) A run-up into a verdict stays, and the half-sentence that the next line says in full goes:** *"but I think for— I think, look, here's the truth, guys. For a lot of solo content creators out there…"* keeps "I think, look," (and its pause); what dies is the unfinished *"a lot of the solo creators out there,"* that the verdict's next sentence repeats whole.
- **(g) An aside that needs more than one graft to be sayable goes whole.** The engineers analogy took three grafts to read fluently and you deleted all three: when a line only survives as stitched fragments, it is a tangent, not a point.
- **(h) A segment starts on the filler that flows into its first kept word** (*"basically, you know, we've got to the point"*): with no pause between them, an IN after the filler is a cut inside speech. And *"All right."* that opens the next step after a wait is a turn signpost: it stays.
- **(i) Take choice is per clause:** prefer-last-take governs the new clause, but when the retake re-opens with a hedge (*"Okay, so it looks like, yeah,"*) graft take 1's clean opener onto it (*"Okay, guys, so it looks like that got done. The whole entire video got edited."*).
- **(j) The sign-off can bookend the CTA:** *"that's gonna be it for this video. Again, if you wanna join… link below. That's gonna be it for this video, guys. See you in the next one."* keeps both wraps; the repeated-sign-off rule collapses adjacent repeats, not a wrap that frames the CTA. An engagement ask to a subset (*"if you're a customer, comment below…"*) is a second CTA and goes.
- **(k) A live demo keeps its operator lines:** the creator's spoken instructions to the agent (*"Sorry, continue. Just re-prompt it so that it gets this new effort level."*) are the demo, and the line that hands the screen over to the wait (*"And yeah, I'm just going to leave this."*) is the lead-in a timelapse needs.

Two craft notes from the same pass. A dead-air split right after a landed claim leaves the claim its beat (about 0.4–0.5 s, under the 0.65 s gate), never 70 ms: mark the piece before the split `beat` (you restored about 0.5 s after *"…by a lot."*). And a hand pin must hold the decay the tools would have measured: at a fused joint put the IN on the kept word's own onset even if its first frames are soft (the *"changing.|I've"* IN you moved 170 ms later), and give a pinned OUT its full measured decay plus 70 ms, never the ASR word end (two of mine clipped 0.12–0.14 s). Special cases you named, not rules: a demo that ends by playing back the video it made keeps the whole playback as its proof, and a deliberate pause inside a run-up can outlast the gate.

---

## The Pipeline

### Transcribe

Find the job folder, then:

```bash
bash .claude/skills/rough-cut/scripts/transcribe.sh <job_dir>
```

WhisperX (large-v3 ASR + wav2vec2 forced alignment) writes true word-level timestamps to the canonical `projects/<job>/transcript/words.json` (plus a scratch mirror under `/tmp`). **Accuracy over speed (recorded 2026-08-07):** every cut is made off these word timings, so the engine stays large-v3 + wav2vec2 however long a run takes, never a smaller or faster model, and no later step rewrites `words.json` or a word's `start`/`end` (corrections swap text only).

**First run builds the venv** at `~/.cache/video-editor/whisperx-venv` (several GB, several minutes) plus the large-v3 + wav2vec2 weights, from the committed lock beside the script, `scripts/whisperx-requirements.txt` (whisperx 3.8.6 and everything under it; its header holds the command that regenerates it, never edit it by hand). The venv must import before its `.deps-ok` sentinel is written, and the sentinel holds the lock's checksum: an interrupted install rebuilds cleanly, and a changed lock rebuilds every older venv once (2026-10-13: an unpinned `whisperx` had moved its API under every fresh client). Later runs start in seconds.

**A clip with no audio stream in `raw/`** (a screen recording made without a mic, a silent cutaway) is recorded in `words.json` with no words and a `⚠ … no audio stream` line, and the rest of the job is transcribed as usual; a job where no clip has audio stops before any model loads (read the footage instead: § Folder Contract, "No usable dialogue").

**Hardware is auto-detected:** an NVIDIA GPU (Windows/Linux) runs CUDA float16 behind a fallback ladder (cuda float16 → cuda int8_float16 → cpu int8), so a broken CUDA stack warns and degrades instead of blocking; Apple Silicon stays CPU int8 (locked — GPU torch is flaky there). `WHISPERX_DEVICE=cpu|cuda` overrides. Details: the engineering archive.

**Batch transcription runs one at a time, on every machine (2026-10-14).** Each run loads its own large-v3 + wav2vec2: a batch started at once (a member's fifty sales calls) held every core of a Mac and took Premiere down, a second run on a smaller CUDA card runs out of memory (the ladder drops it to the CPU), and two runs anywhere race the venv build. So `transcribe.sh` takes a per-machine lock (`<venv>.lock`, a folder beside the venv) before it builds or runs anything: a batch launched in a loop or all at once queues itself, a waiting run prints `waiting: one transcription runs at a time on this machine, and pid N is transcribing <job>` once and starts within 2 s of the previous run finishing, a lock whose pid is gone is taken over (`took over the lock of a transcription that is gone`), and a reuse of the canonical transcript never waits. Regression: `workflows/test_transcribe_args.py` (OneAtATimeTests).

**This is the ONE transcription for the entire pipeline — rough cut AND finishing captions.** The canonical `words.json` is **reused forever**: re-running `transcribe.sh` skips WhisperX (`--force` to redo). Nothing downstream transcribes this footage again — the locked caption presets and `graphics-plan` consume the derived `outputs/<job>.transcript.json` instead (see Splice + Handoff).

**Add `--diarize`** to label each word with a speaker: needs `HUGGINGFACE_TOKEN` (in env, or `HUGGINGFACE_TOKEN=...` in the repo-root `.env`) and the gated model whisperx 3.8 loads, `pyannote/speaker-diarization-community-1`, accepted on Hugging Face. The diarizer is built before the ASR models, so a missing token or an unaccepted model fails in seconds.

**One file that is not a job's raw (a pickup re-record, a spliced audio): `bash .claude/skills/rough-cut/scripts/transcribe.sh --file <audio|video> --out <words.json>`.** Same venv, same CUDA/CPU ladder, same `words.json` shape (`{clips: [{clip, path, duration, words: [{w, start, end, prob}]}]}`), written to `--out`. It never reads or writes any job's `transcript/` and never reuses a transcript. Never word-align with an inline whisperx heredoc against the venv.

**A call on a phone speaker: transcribe with the defaults, then let `--coverage` find the drops (2026-09-23).** Whisper loses a second voice 8–10 dB under you inside its 30 s decode window (the VAD scored those lines 0.76–1.0 on the reference phone-call jobs), and wav2vec2 then fits your reply over that voice's audio. `--chunk-size N` and `--vad-onset X --vad-offset Y` only move WHERE the drop lands (on a 53-minute take `--chunk-size 20` fixed two windows and dropped about ten lines the default kept; `--vad-onset 0.3 --vad-offset 0.2` restored four and lost four; windows under 20 s invented "Thank you." in room tone), so neither is a default or a whole-job fix. The repair is `cut-audit.py --coverage` → `--say <t0> <t1> --boost --spans-out` → `realign-spans.py` (§ Gotchas). A second opinion on one flagged window: cut the slice, `transcribe.sh --file <slice.wav> --out <scratch.json> --chunk-size 20`, and add the slice's start to every time.

**Engine experiment (2026-09-13, not the default):** `scripts/transcribe-scribe.py <job>` (ElevenLabs Scribe v2, `ELEVENLABS_API_KEY` in `.env`) writes `words.scribe.json` in the same shape; `scripts/compare-transcripts.py` diffs it against WhisperX on text and per-word timing and cuts listen-and-judge snippets; `--canonical` swaps it in for a real A/B. Measured on a 9.1 min job: Scribe wins the WORDS (keyterms, no low-prob words, numerals land on the audio) and loses the word ENDS (every clause-final `end` runs to the next token: 13 of 85 pauses > 0.5 s swallowed); ElevenLabs Forced Alignment on its text still swallowed 12. **WhisperX stays the lock;** the viable hybrid is Scribe text + ends re-derived from the audio (last speech frame inside the span).

**Then check the transcript's COVERAGE, before a single cut is authored:**

```bash
uv run workflows/cut-audit.py <job_dir> --coverage
```

WhisperX drops a quiet passage (above), and wav2vec2 force-fits the neighbouring text over that
window: no hole, INVENTED dialogue (§ Gotchas), which no boundary check downstream can see. This reads
the transcript against the raw waveform: every inter-word gap that still holds sustained sound, and
`⚠ VAD DROP` where the words beside it are untrusted too (a cluster of p ≤ 0.35, or a numeral squeezed
into a time nobody could read it in). A gap alone is noise (202 on one 53-minute take), so only that
compound tell is flagged. Each ⚠ gap is slice-transcribed: nothing heard prints `· sound, no speech
heard` and is not counted (a voice far under the speaker can hide from a plain pass: check a suspect
gap with `--say <t0> <t1> --boost`). Repair a real drop at the source with `scripts/realign-spans.py`
(§ Gotchas) before authoring anything over it. Exit 1 means ⚠ lines to read, not a bad take.
**A ⚠-free run is not a covered transcript:** a drop whose neighbours score high prints as a plain `·`
line, so on a take with a second voice, a phone speaker or a live call read the `·` lines too; the only
complete net is the bounce proof (§ The proof), after the cut is laid. A gap checked by ear is
acknowledged with `uv run workflows/cut-audit.py <job_dir> --ack <t0> <t1> --note "phone ringing"`
(into `transcript/coverage-ack.json`): it then prints `· acknowledged: <note>` and is never counted
again (2026-09-20).

**A job with a second voice records its spans once the repair is verified:** `transcript/voices.json`,
`{"spans": [{"clip": "<raw file>", "start": <raw s>, "end": <raw s>, "voice": "phone"}]}`, on the RAW clock
(so it survives every re-cut), each span widened to the WHOLE reply the cut keeps (a reply kept longer in a
hand cut widens its span). The Talking Head Explainer's captions colour those lines from it, and the step-3
lift reads it (`workflows/voice-gain.py --second-voice`, Premiere `audio-polish.py --lift`).

**A long, mostly silent recording (an unattended screen capture of an agent working) is transcribed on its speech only (your-job, 2026-09-28).** A 1 h 56 min demo held 7.5 min of talk: map the speech with a 50 ms RMS envelope (threshold about −45 dBFS on that capture; check the quieter stretches with `cut-audit.py --coverage` and `--say`, where Whisper answers pure room tone with "thank you"), concatenate each speech window ±1.5 s with 2 s gaps, run `transcribe.sh --file <condensed.wav> --out <json>`, and map every word back to raw time through the window table into the job's `transcript/words.json`. The condensed pass took 12 min on CPU instead of hours, and the silent stretches are read off a keyframe contact sheet (`-skip_frame nokey`, one frame per 5 s) instead of a transcript.

**Run in background** over 3min of total clip length. Claude Code: `run_in_background: true` + Monitor. CPU timings: ~30s of clip = ~10-20s wall (first run slower, model downloads), ~5min = ~2min; CUDA is several times faster.

### Lip sync at intake (every camera take, before the replay; 2026-10-05)

A camera whose audio runs early or late is found HERE, never at review (the 2026-10-02 OBS takes ran 140-190 ms
early and surfaced only when the creator watched the finished draft). Every camera raw is measured once, the mouth
crop on your mouth (this rig's horizontal 4K framing: `640:480:1680:880`; measure a new framing off a frame, since
the default centre band answers UNMEASURED on a wide shot):

```bash
uv run workflows/lip-sync.py projects/<job>/raw/<take>.mp4 --audio projects/<job>/raw/<take>.mp4 \
  --mouth-crop 640:480:1680:880 --slip-out projects/<job>/transcript/av-slip.json
```

(`--audio` is the mic source; OBS records it into the same file.) It writes `{"v1_frames": N}`: 0 on PASS, the median
window's lag on FAIL, rounded so the sound never leads the lips by more than 0.3 frame (sound that leads is what
viewers catch: about 45 ms, against about 125 ms for sound that trails). The EDL stays the AUDIO cut; the Premiere replay lays every V1 clip N frames later than A1,
`live-edl.py` and `diff-edl` subtract it on the read-back, and the corner cam (`lay-pip.py`) carries it. Nothing is
written on UNMEASURED or on a take whose windows spread more than 1.5 frames (it drifts: the screen-recorder facecam
case in § Gotchas). A section sub-job writes its own `sections/<s>/transcript/av-slip.json`. Say the number in the
report and in RUN.md; a non-zero slip also means the recording rig needs its clap test before the next session.

### A re-take of an approved cut (a re-record; 2026-10-05)

When the creator re-records a video whose edit you already approved (a flaw on camera, not in the script), the APPROVED
cut is the brief: `reference/<label>/<section>/transcript.json` (frozen before the new raw lands, `edit-video` § A
re-record) is the script the new cut keeps, line for line, and the editorial calls listed in the frozen RUN.md are made
again (the tangents, teases and hedges cut there are cut here; a line the approved cut kept is kept). Cut the new take
with the usual rules, then read the two scripts side by side: a kept line that has no counterpart in the new take, or a
new line with none in the old, is named in the report, never silently resolved. Your hand trims on the approved cut
(a tighter in, a longer tail) are taste to repeat at the same words. Every downstream layer is then re-timed by the words,
`workflows/ripple-cut.py --retake` (`edit-video` § A re-record).

### Author the cuts

Read `projects/<job>/transcript/words.json`. Each clip has a `words` array of `{w, start, end, prob}` (plus `speaker` under `--diarize`).

Apply the auto-kill rules and the edit philosophy. Output `/tmp/video-editor/<job-name>/cuts.json` (on Windows Git Bash maps this to `%TEMP%\video-editor`; write `cuts.json` through the Bash tool with a heredoc, since a file tool may resolve `/tmp` to `C:\tmp`) — the path `splice.sh` reads, overwriting the job copy from it (see Gotchas) — in this shape:

```json
{
  "segments": [
    { "clip": "clip-02.mov", "start": 1.24, "end": 4.60, "transcript": "Are you still paying a VA three grand a month" },
    { "clip": "clip-01.mov", "start": 12.20, "end": 18.80, "transcript": "..." }
  ]
}
```

**Timestamp rules:**
- Trust WhisperX timestamps for WHICH words to keep, not for edges: word STARTS run ~50-100 ms late vs the real acoustic attack, word ENDS run early vs the decay. Exact boundaries are dialed by the refiner (below), not by you.
- **A low-probability boundary tail means the TIMESTAMP is fiction, not just soft (your-job, 2026-08-28).** When a boundary word or its 1-2 neighbors carry prob < 0.3, measure the real edge on the raw envelope with a WIDE window — up to the next raw word, NOT `word.end + 300 ms` — and require a sustained drop before cutting; a capped search lands mid-word and chops the line. Related: a mid-speech "graft" is only legitimate when the adjacent word is KEPT, so a graft against a KILLED region means the measurement failed. **Both are enforced by `polish-boundaries.py` — run it every job; its ⚠ lines are these cases surfacing.**
- **Merged repeats: an immediately repeated word ("However... However,") can collapse into ONE transcript entry spanning every utterance**, so a cut keeping it keeps the stutter. `transcribe.sh` flags long-span words (> 1.0s, and > 0.5s at p < 0.5); the refiner snaps a segment starting on one to the LAST utterance, trims one ending on it to the first, and warns on mid-segment ones (split the range at that word). **On screen-recording footage (OBS) the auto-fix fails SILENTLY** (1 caught of 4 real), so treat every ⚠ long-span word on a boundary as unverified there: measure the raw with a 10 ms RMS envelope, then pin the boundary as explicit start/end + `"no_refine": true`, or the refiner searches from the bogus word end and undoes it. Interior ⚠ words and quiet runs under ~0.3s are fine.§ mechanism (5).
- Start on the first word you want, usually `word.start - 0.03` to `0.08`; end after the last, usually `word.end + 0.04` to `0.10`.
- **Segments must never overlap in the source: a continuous split shares ONE boundary time.** Pads that point at each other (`word.end + 0.08` out, `next_word.start - 0.04` in) put the same frames in both segments, a 1-15 frame stutter: write `"end": T` on one and `"start": T` on the other, one value in the inter-word gap. Padding is for a real cut, where the pads open into different silences. `refine-cuts.py` repairs overlaps and `splice.sh` hard-aborts on survivors, naming YOUR segment numbers. **Adjacency in the word list is not continuity (your-job, 2026-09-18):** neighbouring kept words with a silence of 0.65 s or more between them (a hold on a call, a wait for a render) are a dead-air KILL with two padded edges (`w.end + tail` / `w.start − lead`); share one boundary only under 0.65 s, or the whole pause ships (51 s on one job). `refine-cuts.py` and `polish-boundaries.py` gate continuity on that gap, print `⚠ adjacent words but N s of silence between them`, measure both edges, and waive the refiner's distance cap on that boundary: a warning must not name a repair the file did not get.· the engineering archive.
- Don't cut mid-word; a clipped transition means adjust `cuts.json` and rerender. Segments CAN cross clips in any order.
- **The graft — splice restarts mid-sentence, don't cut at sentence boundaries.** When the speaker restarts a thought ("...we need Claude Code. Okay, we need Claude Code for it to..."), end segment A *through* the repeated phrase in take 1 and start segment B in take 2 *right after* the restated words (at "for it to..."): one continuous sentence, zero duplication. Prefer-last-take governs *full retakes*, the graft governs *mid-thought restarts*.
- **Orphaned connectives — when you kill a line, kill the words that answered it (you caught this on your-job, 2026-08-28).** Rebuttal/contrast frames ("But the reality is...", "That's why...", "So instead...") answer the PREVIOUS sentence, so keeping the counter while cutting the claim leaves a "but" contradicting whatever now sits before it. Re-read the cut sheet as one continuous script and check every segment's FIRST few words: does the connective still refer to something that survived? If not, start the segment after it. Same check on deictics. **And the reverse: a beat that only makes sense WITH its framing clause dies whole when the clause dies.** **The framing clause of a KEPT beat is part of the beat (2026-09-07):** "and after receiving a ton of feedback from my customers, my audience, my community" was killed as good-to-know credibility, and the next line, "I noticed one huge problem...", is its ANSWER, so "I noticed" hung off nothing. Before killing any "after / because / from my ..." setup, read the line that follows: if it opens with noticed / found / realized / learned / saw, the setup stays. The necessity filter is for echoes, teases and warm-up, never for the cause half of a cause-and-effect sentence.
- **Tails are uniform (measured decay + 70 ms) EXCEPT at a landed line, which carries `"beat": true` and keeps up to 250 ms of the speaker's OWN pause (2026-09-13 hand pass).** INVENTED air (`"air": 0.4` pads, retired 2026-08-31) stays inert. In that hand pass 11 of 74 tails were lengthened to 130–390 ms, every one at a verdict, a comparison set-up before its verdict, a section close or the section's last line ("Peace."); the other 63, every mid-argument sentence end among them, stayed at 70 ms. So mark exactly those segments `beat` (the last segment of a section always is), never a sentence end inside an argument; `polish-boundaries.py` and `cut-audit.py` cap the beat at the next word's onset, never manufacture silence, and a split part inherits the beat only on its last piece. If a later hand pass trims beats back, this bullet goes.§ mechanism (7) · the engineering archive.
- **The antecedent of a surviving connective is content, and so is the connective (2026-09-13 hand pass).** The reverse of the orphaned-connectives rule: "So I think you would need to be on a $100 per month plan" was killed as an echo of the next line, "because if you're on a $100 a month plan, you could probably do five of these a week", and the surviving "because" then answered nothing, so you put the line back. Before killing a line, read the NEXT surviving line's first words: *because / so / which is why / that's why / and also* point backwards. Sentence-initial *But / And / So* that answer the previous surviving line stay ("…about $92 in API cost. **But** I was on the $20 a month plan"), and a list marker survives even when the sentence restarts after it ("Claude output better. **And I also,** the video editor system is built on Claude conventions": the "also" tells the viewer a second reason is coming).
- **A reason for an earlier claim moves up next to the claim (the move).** "I think I was also running the edit on medium or maybe high… part of the reason why the edit didn't come out perfect" was filmed four minutes after "the project is more optimized for Claude… it probably could do a better job" and belongs beside it, before "I actually did run a second version"; it was moved in the authored cut and survived the hand pass untouched. Segments can cross the raw in any order: when a later passage answers an earlier point, move it, then check the connectives on both sides of the hole it leaves.
- **At a fused joint the dip's frame belongs to the killed word (2026-09-13 hand pass).** Where a killed word runs straight into a kept one, the boundary sits on the frame boundary at/before the envelope minimum for an OUT and at/after it for an IN; the outward frame plays the first 10–40 ms of the killed word ("benchmarks|okay": −31 dB on the outward frame against a −55 dB dip). `cut-audit.py --grid` snaps inward now; you had moved five OUTs and two INs by hand to exactly those frames.
- These pads are a starting point: `splice.sh` runs `refine-cuts.py` first, which measures each boundary word's acoustic onset/offset on the raw and nudges the cut just outside it (in = onset − 40 ms, out = offset + 50 ms), clamped inside the local gap and capped relative to its own word (250 ms lead, 300 ms tail); continuous splits get one shared boundary, joints resolve PAIRWISE. Watch the `[refine]` report — `cut was N ms INTO "word"` lines are clipped attacks it saved. `REFINE=0` disables the pass; `"no_refine": true` pins a segment (an overlap against a pinned side moves the UNPINNED side only). Mechanics: the engineering archive § mechanisms (4) and (6).
- **Refinement is NOT idempotent — repair a shipped EDL with `refine-cuts.py --repair-only`, never a second full pass.** The refiner measures from the authored cut, so a second pass re-measures from the moved boundaries and drifts tails further out (+0.4s observed). `--repair-only` runs ONLY the pairwise joint resolution with zero re-measurement, so only overlapping joints move.

Include the `transcript` field on every segment so the cut sheet reads on its own.

### Splice (EDL-only by default)

**The editing-app finish IS the default (2026-08-28): a bare "rough cut" with no lane named means EDL-only mode + automatic Premiere handoff — NEVER render:**

```bash
RENDER=0 bash .claude/skills/rough-cut/scripts/splice.sh <job_dir>
```

~8 seconds: boundary refine + frame-snap + persisted EDL + corrected canonical transcript, no ffmpeg encode. Nothing on an editing-app path reads the flat MP4. Go straight to the timeline (clients: `capcut` / `davinci-resolve`), then the **audio polish** (step 3, the house chain as clip effects — see `premiere-pro`). The full render below is **only** for the chat-only/HyperFrames lane, never inferred: it runs when a client with no editing app has explicitly said to do it in chat.

```bash
bash .claude/skills/rough-cut/scripts/splice.sh <job_dir>
```

Dials every boundary against the raw audio (`refine-cuts.py` — see Timestamp rules), then writes `outputs/<job-name>.mp4` in a **single FFmpeg filtergraph**: one `trim`/`atrim` per kept segment → `concat` → static gain → limiter, encoded once. Audio rides through **lossless (PCM in-graph)** and is polished **once** on the assembled track (measured amplify from `workflows/voice-gain.py`, kept speech → −17 LUFS pre-limiter → −6 dBFS hard limiter → AAC 256k), **never** per-segment (boundary click-pops). Video and audio trim from the same in/out, so A/V stay locked by construction.

**`splice.sh` runs `scripts/audio-qa.py` after every splice** (joint clicks, ambience continuity, silence gaps, limiter pressure) and never fails on it (`|| true`), so its ⚠ lines are easy to miss: read them. A limiter-pressure warning is acted on only when it is audible, and never by naming a gain (the measured-gain lock).

It also writes **`outputs/<job-name>.transcript.json`** — the cut-aligned caption transcript, the kept words remapped through `cuts.json` by `export-transcript.py`: timestamps rebased to the edited timeline, **zero re-transcription.** This is what finishing/captions/graphics consume.

**Spelling/brand fixes happen HERE, once.** `export-transcript.py` applies [`transcript-corrections.json`](../../../transcript-corrections.json) as it writes the canonical transcript: `auto` entries (non-word mishears + brand/name casing) swap silently, `flag` entries (real words that might be mishears, e.g. `cloud`) print for eyeballing. Because this is the one source of truth downstream reads, the fix propagates everywhere. The raw `words.json` is untouched; per-video one-offs go in `projects/<job>/corrections.local.json` (same `{auto,flag}` shape, merged on top). Watch the splice log for `auto-fixed:` and `⚠ REVIEW`. Rationale: the engineering archive.

**The full render (`RENDER=1`) puts every segment on the MAIN take's canvas and frame grid (2026-10-13).** The main take is the clip carrying the most kept time, its size read as it decodes (rotation applied); a clip of another size is letterboxed onto it (scale down + pad, never cropped, a ⚠ line names each), every boundary snaps to the main take's rate so the output is constant-rate, and the persisted snapped EDL records that grid. **It also stops on an HLG or PQ (HDR) raw** before anything is measured or encoded, naming each clip: finish that job in an editing app, convert the raw to Rec.709 SDR once in `raw/`, or film with iPhone HDR Video off. `RENDER=0` does neither: each clip keeps its own grid, so an app-lane EDL is unchanged. Regressions: `workflows/test_splice_guard.py`.

**The full render runs 15-45s per 60s of output — background it.** `RENDER=0` is ~8s, foreground.

### Polish the boundaries (ALWAYS, every job — added 2026-08-28)

```bash
uv run .claude/skills/rough-cut/scripts/polish-boundaries.py <job_dir>
bash .claude/skills/rough-cut/scripts/splice.sh <job_dir>     # RENDER=0 on app-finish jobs
```

The refiner measures each boundary against its own word and its absolute thresholds clip soft decays
or count breaths as tails. (It no longer skips a dead-air kill between adjacent transcript words: it
names the joint, measures both edges and cuts the silence — § Author the cuts.) This
re-derives EVERY boundary peak-relative (local floor, threshold
`max(floor+10dB, peak−28dB)`, decay capped at word.end+300ms, uniform out = decay+70ms /
in = onset−40ms on every segment), widens the search on low-probability boundary words, sweeps every
segment's interior and splits any quiet run ≥ 0.65s, and pins everything. Run the FIRST splice with
`RENDER=0` on every lane, chat-only included — the real render belongs AFTER this step. Already
hand-pinned (`no_refine`) segments are left untouched, which makes the step idempotent. **Heed its ⚠
lines** — clipped words, merged repeats, possible flubbed takes; each gets verified (slice-ASR the
span — see § Fresh-eyes second pass — or fix the boundary by hand) before the cut ships. Then re-run
splice.sh to consume the pinned EDL.

**A quiet final consonant is still the word (2026-10-14).** A final /s/, /dʒ/, /f/, /θ/ or a released
/t/ /k/ is high-band noise under the broadband threshold, or behind a stop closure longer than the
100 ms quiet terminator, so the decay ended at the vowel and decay + 70 ms cut it off (a member: "it
cuts off the ends of words … like advantage"; "effects," lost its whole /ts/, 220 ms). When the boundary word is SPELT to end on
a fricative, affricate or stop (a silent e dropped first, so "advantage" ends -g; never -ng),
`polish-boundaries.py` carries the decay on through the high band (the second difference: hum and vowel
bodies drop out), over every hop at or above max(high-band floor + 15 dB, the word's own high-band peak −
30 dB), across a dip of up to 100 ms only when what follows is back within 20 dB of that peak inside
30 ms (a release is; an inhale ramps up under it). Same caps as the decay (word end + 300 ms, the next
killed word); the dead-air split's OUT gets it too, and the status line reads `out:soft+Nms decay+70ms`.
Open endings (vowels, -l, -r, -m, -n, -ng) keep their broadband decay. `cut-audit.py` imports the same
function (`consonant_end`), so the two tools place the word's end identically. Regressions:
`workflows/test_polish_split.py` and `test_cut_audit_verdicts.py` (QuietFinalConsonantTests).

**Three of its lines each mean a word to slice-ASR before the cut ships (2026-09-23).** `out:⚠ CLAMPED`
with "OUT: the next killed word '<w>' starts before '<kept>' decays: speech runs through the cut (fused
joint), verify / pin" means the OUT was clamped at the next killed word's start with less than one 5 ms
hop of tail: the kept word is still loud where the cut falls, so the cut is inside speech (before
2026-09-23 this showed only as `decay+-Nms`). It is not cut-audit's FUSED verdict, which is a clean cut on
the dip: slice-ASR the joint, then pin the OUT by hand or re-author the kill. When the interior dead-air
pass splits a segment, each part's `transcript` is rebuilt from the words the parent plays (every word
inside its final boundaries, or overlapping them by 30 ms or half the word), each word going to exactly
one part, so the parts always join to the parent's text (a part may carry empty text when the aligner
stretched its only word across the pause). "'<w>' ends N ms past the split OUT: the dead-air split may
clip it" means the text keeps the word, so cut-proof can no longer see a clipped tail; "'<w>' … lies
inside the removed dead air" means the aligner puts a word where the envelope hears quiet, and names the
part whose text now holds it.
§ mechanisms (7) and (8).

**Every `seg N` polish prints indexes the `cuts.json` that same run writes**, `@T` the boundary the
line is about: the interior dead-air pass renumbers, so a number off an older log is fiction.
A status line whose segment that pass split prints `segN/M` (the `in:` note is N's, the `out:` note
M's); `seg??` is a resolver bug, never an index to act on. **A hand pin is addressed by (clip, time)
AND asserted on the segment's transcript text:** `scripts/pin-boundary.py` — `pin(seg(S, clip, 656.9,
expect="MP3"), start=657.15)` — refuses and names both candidates instead of picking (a nearest-time
match lands on the neighbour 0.3-0.5 s away, and a fix on the wrong edit costs a full author → splice
→ polish → pin cycle; your-job, 2026-09-18).

<a id="audit-the-cut-on-the-finish-surfaces-grid-app-finishes-required-when-the-source-and-sequence-rates-differ"></a>

### Audit the cut on the finish surface's grid (every app-finish job; the grid matters most when source and sequence rates differ)

```bash
uv run workflows/cut-audit.py <job_dir> --grid 24000/1001 --promote --sheet <job_dir>/review/cut-audit-sheet.png
```

`polish-boundaries.py` measures once, off WhisperX anchors, and the app then quantizes every boundary
to ITS frame grid: a 30 fps screen-recording outro on a 23.976 sequence landed every in and out up to
41 ms early (2026-09-13: 21 cuts inside speech, 22 tails under the house 70 ms, and the creator heard it).
`cut-audit.py` trusts only the waveform (a 5 ms RMS envelope, a local floor, speech runs). Per boundary:

- **OK** · **CLIP** (inside the kept word; at an OUT that includes its quiet final consonant, measured as
  in § Polish the boundaries, so a cut 70 ms after the vowel of "advantage" is CLIP and a tail is measured
  from the consonant's end, never called LONG for keeping it) · **FUSED** (a killed word running into the
  kept one: the cut goes on the last prominent dip before the kept word's attack, never the run's edge,
  which would resurrect the killed word) · **BREATH** at an IN (a low-level inhale at the head, kept).
- **LONG:** a tail over 70 + 80 ms, or a `beat` tail over 250 ms, is trimmed on the grid to decay + 70 /
  250 ms (a 390 ms tail passed as "ok" and then failed dead-air-qa at the joint, 2026-09-20).
- **BREATH at an OUT:** a run reaching more than 250 ms past the kept word's ALIGNER end in which the
  slice ASR hears no word, whichever branch proposed the move (the run's end, or the last dip of a tail
  the ASR calls non-speech). The cut stays, with a ⚠ verify (an OUT was once moved +667 ms into breath
  and room tone). A cut INSIDE the kept word is never BREATH: capped at the aligner's end + TAIL, it stays
  CLIP and counted, with a ⚠ verify. Gate and cap are measured from the aligner's end, never the slice
  ASR's, whose word ends stretch into the breath (+617 ms once).
- It moves ONLY defects and leads < 40 ms / tails < 70 ms, every value on the sequence grid (`--grid`), so
  the lane's replay lands it exactly. `--sheet` writes the waveform contact sheet (red = current cut,
  green = repaired): that is the proof, look at it.

**Content comes from a slice ASR; position never does.** Every cut inside a continuous run has that run
re-transcribed independently (mlx-whisper on Apple Silicon, the WhisperX venv's faster-whisper elsewhere,
an Intel Mac included, through `workflows/asr_cli.py`; word timestamps, one engine process for the whole
audit; `--asr off` skips): the run IS the kept word (a clipped attack: WhisperX had "I would like" 380 ms
late) or a killed word runs into it (fused, cut on the dip). Both engines are ±100 ms on word edges
(anchoring on them pulled cuts into "usage", "to" and "it"); the dip inside the WhisperX-bounded window
matched every hand-verified joint. **Where no engine runs, the audit falls back to the envelope heuristics
and exits 3, `UNVERIFIED`,** with the reason: fix the engine and re-run, or record the cut in RUN.md as
unverified, never as clean (2026-10-13: on a Mac whose `python3` became Homebrew's 3.15 it printed one ⚠
and a clean summary).

**The content gate runs on EVERY boundary, not only inside a run (a "53" that shipped as "50",
2026-09-13):** a cut between two runs looks clean to a waveform when the next run is the kept word's own
next syllable after a quiet fricative ("fif|ty-three", "click|bait"). So the kept side is transcribed up
to the cut and again extended 400 ms across it (slices padded with silence on the cut side, or the decoder
mis-hears a word it meets mid-attack): a boundary word that CHANGES means the cut is inside it and the
true edge is bisected (CONTENT); a word merely added means clean. **It never extends into a killed word
(2026-09-20):** the extension stops at the SEGMENT's killed neighbour (the first word past its own last
word by aligner start; at an IN, the word before its first, by aligner end), and when that bound sits at
or before the cut the envelope's verdict stands (a fused joint read as CONTENT once wanted +1043 ms into a
deliberately killed "et cetera, et cetera"). A kept word the cut chops is in the segment, so it is still
restored. **A CLIP at a word the WhisperX midpoint and the transcript put on different sides is HELD:**
measured on the transcript's reading, and when that repair would move the cut it stays CLIP, prints
`⚠ HELD … would have moved to X` and is counted as held: check it by ear, then pin or move it (each reading
alone moved real cuts the wrong way). After the verdicts the proposed EDL runs through `dead-air-qa.py`'s
own quiet-run gate (imported, not re-typed), so a joint whose tail plus the next lead reach 0.65 s prints
`⚠ segNN/segMM joint` before the replay.

After a re-lay, run it again with `--live <readback json>` and expect `0 boundaries in speech`. It reads
`--edl` (default `transcript/cuts.json`) and says so first (`[cut-audit] reading <path>`). `--promote`
backs `transcript/cuts.json` up as `cuts.pre-audit-<YYYYmmdd-HHMMSS>.json`, writes the audited EDL there
and prints the `export-transcript.py` command to run next (never `splice.sh`, whose frame-snap is to the
SOURCE grid and would undo the placement); `--write <file>` writes elsewhere. Both REFUSE (exit 2) a target
that holds `pin_in` / `pin_out` the input lacks (a pin set only in the target was overwritten in silence,
2026-09-20): pin the input, or pass `--edl <target>`. Same-rate jobs still benefit (the "-bait" of
clickbait, a "$92" payoff WhisperX had mis-aligned). The Premiere replay's own grid math: `premiere-pro`
§ Step 2.

**A boundary a human decided is pinned for the AUDIT with `"pin_in"` / `"pin_out": true`, not with
`no_refine`.** `no_refine` holds BOTH of a segment's boundaries against the refiner and the polish, and
`cut-audit.py --write` stamps it on every segment it writes, so the audit ignores it by design. `pin_in` /
`pin_out` hold ONE edge, in the audit and, since 2026-09-27, in `refine-cuts.py` and `polish-boundaries.py`
too, which measure the other edge as usual (the clipper pins only the edge on its parent job's cut).
Unpinned, a hand-trimmed stutter or killed false start is re-derived from the envelope and quietly undone
(a "we're going to use, use this custom voice" trim came back twice; your-job, 2026-09-18). A pinned
boundary reports `pinned, would have moved to X` and is left alone. **A `--live` readback more than a frame
off the EDL is the creator's hand edit, never a lane quantization:** reported `HAND edit ±N ms off the EDL,
left alone` and never moved (root `CLAUDE.md` § live state that disagrees with RUN.md). **A hand edit that is
ALSO a cut inside speech keeps its verdict:** `CLIP*` / `CONTENT*`, counted in `boundaries in speech`, given
its `--sheet` panel, and the summary counts the hand edits in speech, so nothing a human touched can hide a
defect. Nothing moves either way: the repair is the creator's, by hand or by dropping the trim. At a `--live`
hand edit the EDL transcript is stale, so kept and killed are split by the words the live span plays. A
clean trim on a dip reads HAND, never HELD or CLIP*; a trim inside a word reads CLIP*. Story:
the engineering archive.

### The proof: the laid cut is transcribed and diffed against the script (Premiere, the definition of done)

```bash
uv run lanes/premiere/cut-proof.py projects/<job>[/sections/<s>] [--from <start>] [--to <end>]
```

WhisperX is the map the cut was authored from, not the territory: on a screen-recording outro it collapsed
three stutters into one word each ("half as, half as"), skipped a mumbled "like, the other one" inside what
`dead-air-qa.py` called a 0.96 s pause, and stretched a sentence-final word over a killed phrase. No
boundary check can see that; only the assembled audio can. The proof bounces the section's dialogue off the
LIVE timeline (other tracks muted), transcribes the bounce independently and diffs it word by word against
the EDL's script: every stutter, doubled joint, chopped syllable or leaked killed word is a line with its
timeline position; notation ("$100" / "100 dollars"), spellings and contractions ("i am" / "im") are tagged
and ignored. **A rough cut on Premiere is done when this exits 0** (Resolve and CapCut have no bounce proof
yet: `LANES.md` § step 2), after the replay and the audio polish, and again after any hand edit. A stutter it
finds is killed at the EDL (split the segment, first take dies) and the whole chain runs again: audit →
persist → re-lay → polish → proof.

- **Both sides are canonicalised through [`transcript-corrections.json`](../../../transcript-corrections.json)
  + the job's `corrections.local.json` (2026-09-19):** a brand the two engines spell differently is never a
  defect, a mishear not yet in the dictionary belongs in it (the fix `scan-transcript.py` asks for), and a
  NUMBER is never a spelling ("53" heard as "50" stays a defect).
- **The window.** On a section with no flags, `--from` defaults to the EDL's first frame on the timeline and
  `--to` to its last (the EDL's `_timeline` end, else edl_start + the EDL's length; the sequence end when that
  is within 0.5 s past it, or short of it), so a middle section never bounces the later ones (proven live
  2026-09-23). A proof of part of a section needs only `--from` / `--to`: the script is windowed to the
  segments the bounce covers, and the EDL's first frame is read from the job (the `_timeline` readback, else
  the section's `graphics-plan.json` `timeline_offset`, else 0 for a top-level `projects/<job>`). A section
  sub-job at step 2 has none of these: pass `--edl-start` (it warns ⚠ and assumes `--from`). Every run prints
  `[cut-proof] script window: EDL a-b s (edl_start x, from …)` before the bounce: read it, and abort if it is
  wrong. Words of a partly covered boundary segment are tagged `edge`.
- **Read the gate's exit code directly, never through `| tail`:** a pipe reports tail's status (an argparse
  error once read as exit 0; in zsh, `${pipestatus[1]}`).
- `--triage` re-transcribes a ±1.5 s slice of the bounce under every defect, so a transcription slip
  identifies itself; each run prints the defects it INTRODUCED first (`NEW`), the rest counted as carried,
  keyed on the words, never a timeline position every re-lay moves. A proof after a hand edit means something
  only once the EDL is re-derived from the live timeline.
- **Before every bounce it checks each segment's `transcript` against words.json** (`--check-text` runs that
  alone, offline): text that omits a word wholly inside its segment, or carries one no word there holds, is a
  false DEFECT, so fix the text to the kept audio first (2026-09-27).
- **A defect `--triage` proves is an ASR false positive** (a reduced "with" every engine, the raw included,
  hears as "for") is accepted in `review/cut-proof.accepted.json` as `{script, heard, t, cut_rev, reason}`:
  same words, within ±0.5 s of `t` (timeline seconds, as printed), on the `cut_rev` the summary prints. It is
  then reported `accepted` and no longer fails the gate; a row without a reason is refused, and one from
  another cut_rev is ignored, so a re-cut re-opens it. Regression: `workflows/test_cut_proof.py`.

### Final dialogue dead-air gate (required before handoff and after EDL changes)

Run `uv run workflows/dead-air-qa.py <job_dir> --json <job_dir>/transcript/dead-air-qa.json` against the final
saved EDL, pinned segments included. Read-only, on the original dialogue audio (music and SFX cannot hide a
pause), bridging brief room-noise spikes and measuring across joints. Every flagged ≥0.65s run is checked
acoustically and corrected if it is dead air.

**The repair:** split the containing segment at `[source_start + 0.07, resume_source − 0.035]` in the `/tmp`
EDL (when `transcript/cuts.json` was written after the last splice, by `cut-audit.py --promote`,
`live-edl.py --write` or a hand edit, copy it to the `/tmp` EDL first: `splice.sh` refuses to overwrite it
otherwise), both halves `"no_refine": true` and each half's `transcript` cut to the words IT plays (a copied
parent text reads as phantom deleted words in `cut-proof.py --check-text`, 2026-09-28); re-run
`RENDER=0 splice.sh`, then this gate until it passes. **The split's IN is `resume_source`, never the run's end
(3 of 8 splits, 2026-10-13):** the gate bridges a burst under 40 ms as a spike, and a soft "it's" onset is one,
so the run's end (`source_start + duration`) is the next word's vowel, and an IN there cut "It's" away ("It's
not very cheaply made" came back as "not very cheaply made"). Every finding carries `resume` /
`resume_source`, where speech comes back, a bridged onset burst included: pin that IN (`pin_in`) and keep the
word in that half's `transcript`. `no_refine` protects a measured boundary; it does not prove a pause was
reviewed or intentionally retained. A segment carrying `media` (laid from a substitute file such as a
lip-sync re-record) is not audited on the raw by `dead-air-qa.py` or `cut-audit.py`: each prints
`segNN laid from <media>: not audited on the raw`, keeps its EDL times, still counts its duration and never
joins a quiet run across it (`not_audited` in the JSON). Check its audio by ear or on the bounce proof.

Also inspect transcript gaps ≥0.65s as independent review candidates. A quiet detector passing, timeline clips being contiguous, and an export decoding successfully are separate checks; none is a substitute for reviewing the actual pacing. After a repair, rerun this gate and verify live V1/A1 source ranges match the audited EDL. Never declare the rough cut clean from timeline contiguity alone.

### Transcript QA (auto, every run)

The static dictionary only fixes mishears it knows. This catches the **new** ones — names/brands WhisperX mangled. **Run it every job, right after splice:**

```bash
uv run .claude/skills/rough-cut/scripts/scan-transcript.py <job_dir>
```

(Windows has no system wordlist: there `uv run` installs the `english-words` package, the same web2 list macOS ships, so the scan runs there too. A minimal Linux without one reports nothing until `sudo apt install -y wamerican`, as `check-setup.sh` says. A one-off fixed in the job's `corrections.local.json` is no longer listed.)

It compares every word against a 235k-word English wordlist (+ inflection stripping) and the dictionary, printing only the **suspects**. Clean transcript → empty; otherwise a short list with context: `higsfield  ×1  …built it on higsfield and pushed to…`.

**Judge each suspect in context:** single token, recurring name/brand (`higsfield → Higgsfield`) → [`transcript-corrections.json`](../../../transcript-corrections.json) `auto`, fixed everywhere forever · one-off → `projects/<job>/corrections.local.json` · **multi-token mishear** ("higs field" → "Higgsfield") → **never** auto-apply (it changes word count and breaks per-word timestamps), flag it · already-correct proper noun → skip.

Then re-apply (instant, timings + cuts untouched):

```bash
bash .claude/skills/rough-cut/scripts/reapply-corrections.sh <job_dir>
```

**Hard rule:** only auto-apply **single-token, whole-word** swaps — the dictionary mechanism enforces this, which is why it can never shift a timestamp or alter a cut. Unsure? Flag it.

### Fresh-eyes second pass (ALWAYS, every job — 2026-08-28)

The author grading their own cut is why first cuts ship flaws. Before reporting (and before the
timeline replay on app-finish jobs), fan out **two subagents on the chat's own model**
(no model passed: `edit-review` § Token efficiency), one pass:

1. **Script-flow reviewer.** Input: the cut sheet's transcript column as ONE continuous prose
   script (+ this skill's taste rules, self-contained in the prompt). Finds only: orphaned
   connectives, dead deictic antecedents, echoes kept more than once, fluff (good-to-know vs
   need-to-know-NOW), a beat stripped of its framing clause, meta-signposts / method teases (excluding the protected closure/handoff
   and the corner-turning section closes), momentum breaks, and a missing or chopped ending against the raw closing passage;
   plus the 2026-09-13 classes: a weak line right before its stronger restatement, a rhetorical Q&A with no claim, a second
   hedge after a hedged sentence, a wrong connective, a reading-aloud search, a second CTA in the outro, a killed line that a
   surviving *because / so / and also* still answers, a mid-phrase one-word filler cut out (a joint bought for nothing), and
   an argument's landing restatement killed as an echo. Findings must quote the exact lines.
2. **Mechanical reviewer.** Input: the polish-boundaries ⚠ list, the transcript, the words.json
   probabilities. Verifies every ⚠ by slice re-ASR — `uv run workflows/cut-audit.py <job_dir> --say
   <t0> <t1> [--clip <name>]` prints what an independent engine hears in that raw span (±4s around
   the boundary) — and diffs what was said against what the cut keeps. Use that command, never a
   hand-rolled `mlx_whisper` shell-out: it names its output file by the basename up to the FIRST
   dot, so a slice called `b0082.88.wav` silently overwrites `b0082`'s transcript and three batches
   come back wrong (your-job 2026-09-18). Catches
   fictional tails, missing sentence completions, and flubbed takes (an alignment-collapse cluster
   + an untranscribed speech burst nearby = a bad take to kill, not a boundary to fix).

Launch both in the background and do not poll for them (the harness notifies on completion; a grep
loop never matches and burns its whole timeout). Main session adjudicates: mechanical defects get
fixed (boundary moved, take killed, graft moved), flow findings are judgment calls decided against
the taste rules, and only the CHANGED segments get re-checked. Then report. Why this pass exists: the engineering archive.

### Report back

Show the creator: the detected format + the hook/takeaway you inferred (one line, where a wrong read
gets corrected), final duration vs raw total, and the cut sheet. On the default (`RENDER=0`) lane
report the segment count, `transcript/cuts.json`, `outputs/<job>.transcript.json` and the timeline
the EDL was replayed onto — **there is no flat MP4, do not report one.** Only the chat-only /
HyperFrames lane reports `outputs/<job>.mp4`.

```
✂️ ROUGH CUT DONE

📊 3:47 → 0:48 (79% cut)  ·  33 segments
📁 projects/<job-name>/transcript/cuts.json  →  replayed onto <timeline>
   (chat-only lane instead: projects/<job-name>/outputs/<job-name>.mp4)

CUT SHEET:
1. [clip-02 @ 1.24-4.60] "Are you still paying a VA three grand a month"
2. [clip-02 @ 4.95-8.10] "to do shit Claude Code can do for free"
...
```

Flag a weak segment: **"⚠️ segment 3 is borderline — consider killing."**

### Learn from the hand pass (Premiere-finish jobs)

When the creator hand-adjusts the cut on the Premiere timeline, **diff their edit against the EDL and fold the delta back into taste** — their trims ARE the ground truth this skill approximates:

```bash
node lanes/premiere/premiere-bridge.mjs diff-edl projects/<job>/transcript/cuts.json [more cuts.json...]
```

It matches every timeline clip to its EDL segment by source overlap and prints deletions, boundary trims/extensions (with the words at each moved boundary), grafts, and new material. Recurring pattern → a new Auto-Kill row or timestamp rule here; one-off → the job's notes. The 2026-07-29 rules came from exactly this diff. A clip's source out is derived from its own length (`inPoint + (end − start)`), never read from `outPoint`: a `STALE-OUTPOINT` line is a stale readback left by an earlier `clip.end` write, reported for information and never the creator's trim.

After a hand pass the **timeline is the source of truth**: never re-replay the EDL over it. Sync it with `uv run lanes/premiere/live-edl.py projects/<job> --write`, which backs the old EDL up as `transcript/cuts.pre-live-<stamp>.json`, derives every source out as `inPoint + (end − start)`, pins each boundary that moved (`pin_in` / `pin_out`, so the audit never undoes it), re-derives those segments' words with the polish's own `plays` rule (a grazed neighbour stays out, an aligner end past a hand OUT stays in, a word across a razor is promised once) and writes `_timeline`. Then run the two commands it prints: `ripple-cut.py --from <backup> --apply` first (it re-derives the canonical transcript and backs up the old one), then `export-transcript.py` only if there was no canonical transcript yet. A sequence that carries another EDL (an AD clone) is synced into its own file with `--sequence "<job> AD" --edl transcript/cuts.ad.json`; without `--edl` the tool refuses to write it into the organic's EDL. `--live-out live.json` feeds `cut-audit.py --live`. Exit 1 = V1 does not add up (a gap, a deleted clip); exit 2 = refused or failed. Never hand-build this from a dump script (proven live 2026-09-23, your-job's own stale clip reproduced to the digit).

**The worked example** of reading a hand pass back (live readback, EDL, `cut-proof.py` so every ambiguous joint is HEARD, `cut-audit.py` on both EDLs, the surviving-pause distribution) and turning its delta into rows, bullets and tool changes: the engineering archive.

---

## Gotchas

- **`-c copy` alone desyncs A/V on arbitrary cut points** — `splice.sh` trims and concats in one filtergraph, encoding once. Never "optimize" to stream copy.
- **Don't auto-snap cuts to silence.** WhisperX word alignment is the unlock; silencedetect snapping moves chosen boundaries into filler words or awkward pauses. (The refiner and `polish-boundaries.py` are NOT this: they keep the chosen word fixed and only dial the cut against its measured acoustic edge, clamped inside the local gap.)
- **Whisper can mishear.** Cross-check before killing a line — "Claude" becomes "cloud" and the line looks wrong when it's fine.
- **`splice.sh` reads `/tmp/video-editor/<job>/cuts.json`, NOT `transcript/cuts.json`** (on Windows, `%TEMP%\video-editor\<job>`, Git Bash's `/tmp`: write it through the Bash tool, since a file tool may resolve `/tmp` to `C:\tmp`), then overwrites the job copy with what it spliced. It stamps that copy (`transcript/cuts.splice.sha1`) and exits 2 when `transcript/cuts.json` changed since (`cut-audit.py --promote`, `live-edl.py --write`, a hand edit) and the `/tmp` EDL is not that file: when `transcript/cuts.json` is newer than the last splice, copy it to the `/tmp` path (deleting `cuts.refined.json` + `cuts.snapped.json` beside it) first. **That folder is keyed by the job folder's NAME, so jobs that share one (`sections/intro` in two parent jobs) share it (2026-10-02):** `splice.sh` records the job it spliced in `.job-path` there and exits 2 when that names another job and `cuts.json` was not written since (copy THIS job's EDL there first), with a ⚠ when it was; `polish-boundaries.py` refuses another job's `cuts.refined.json` the same way; `cut-audit.py`'s slice-ASR cache is keyed by the job's path and the clip itself. Regressions: `workflows/test_splice_guard.py`, `test_cut_audit_cache.py`.
- **Transcribe.sh auto-skips** when `projects/<job-name>/transcript/words.json` exists. Use `--force` only if the raw footage actually changed.
- **Multi-section jobs: each newly filmed section runs as its own sub-job under `projects/<job>/sections/<name>/`** (raw symlinked from the parent's `raw/`; Windows refuses a symlink without Developer Mode, so there copy the raw into the section's `raw/` instead, its own `transcript/` + `outputs/`). This exists because of the auto-skip above: point a new section's transcribe at the main job dir and it silently reuses the WRONG `words.json`/`cuts.json`. (Same nesting the clipper uses.)
- **The authoring pad can pull the NEXT killed word into a segment (astra final-thoughts, 2026-09-14).** `refine-cuts.py` and `polish-boundaries.py` take a segment's words by OVERLAP, so an authored `end = word.end + 0.07` that touches the next word's WhisperX start makes that killed word the segment's last word: its decay gets measured and it ships ("then", "And", a stranded "My", a filler "like" on one job). When the word after the last kept one is killed and starts within ~100 ms, author `end` just under its start and read the polish's per-segment `…word` column: it names the word each boundary was measured on. **The IN side is the mirror (2026-10-13, Windows pass):** an authored `start = word.start − 0.04` that overlaps the killed word ending just before it makes THAT word the segment's first ("with my favorite part": start 228.70 against "with" ending 228.72), the polish measures its onset and the IN ships it; `cut-audit.py` read the new IN as a clean lead (it sits in the gap before "with") and only `cut-proof.py --check-text` named it. When the word before the first kept one is killed and ends within ~100 ms, author `start` just past its end. **And when two independent ASR passes agree on a word at a joint that the envelope cannot label, the ASR's word ORDER wins** ("And here's… [pause] the, so that's" — the envelope read the post-pause burst as "So"; the bounce proof caught the stranded "the").
- **The per-section colour replay on Premiere:** one `premiere-bridge.mjs replay` per section (`--append` from the second on: a replay onto an occupied V1 is refused), with that section's colour label set first (`premiere-pro` § Colour labels), then `cut-audit.py --live`, then `polish-boundaries.py` on the section's own sub-job, then `cut-proof.py --from <the section's start>`.
- **A second voice on a phone speaker goes missing from WhisperX's text, and the aligner then misplaces the MAIN speaker (2026-09-17).** No `transcribe.sh` setting prevents it (§ Transcribe). On a live call demo the AI's lines (about 10 dB under the creator) were dropped whole and wav2vec2 forced the next lines into the wrong windows (one 6 s early), so every cut authored there would have been fiction. Tell: gaps of several seconds inside a conversation, then a run of p < 0.3 words. Fix at the source: `uv run workflows/cut-audit.py <job_dir> --coverage` finds the windows (§ Transcribe); `--say <t0> <t1> --boost --spans-out <spans.json>` tells you what is really in them and drafts the spans file, one span per ASR segment (`--boost` compresses and normalises the slice for a voice about 10 dB under; every pass runs with `--condition-on-previous-text False`, and `--say` with no times covers the whole clip in windows of 30 s or less, because one long pass locked into repeating a sentence, 2026-09-20). Check every line of the draft by ear and fix numeral times (never hand-roll `mlx_whisper`); then `~/.cache/video-editor/whisperx-venv/bin/python .claude/skills/rough-cut/scripts/realign-spans.py <job_dir> <spans.json>` (Windows: `…/whisperx-venv/Scripts/python.exe`; the venv `transcribe.sh` builds) force-aligns THOSE spans with `whisperx.align`, keeps WhisperX's words everywhere else and backs the old transcript up as `words.whisperx-vad.json`. **A span is a WINDOW:** spans may never overlap (it refuses an overlapping pair and says to merge them) and every word that touches one is replaced (it counts the words dropped for grazing an edge); either left in, `words.json` carries two words over the same seconds and every boundary measured off it inherits them. Numerals come back squeezed into a few hundred ms (each flagged): set those word times from the envelope. **The same drift INVENTS words (2026-09-18):** WhisperX laid "Okay, so it should call me" over the creator reading a phone number aloud, and only the bounce proof heard the digits. Any segment beside spoken digits or on a call is slice-ASR'd on the raw before it ships.
- **`transcript/cuts.json` is splice's own by-product, not an authored EDL.** `splice.sh` copies it from `cuts.snapped.json` AFTER the frame-snap, which takes ~10 s on a 208-segment EDL, so it is always newer than `cuts.refined.json` and the 5 s mtime slack false-aborted every long-form job with "the refined EDL is stale". `polish-boundaries.py` now skips it on byte-equality with the snapped file and only refuses on a real hand edit. Never clear a stale-EDL abort by `touch`ing the refined file — re-run `splice.sh` so the refiner measures the EDL you edited.
- **A SPOKEN CLAIM WHOSE TRUTH IS ON SCREEN IS CHECKED AGAINST THE FRAMES, AND THE PICTURE WINS (2026-09-19).** Reading the assembled cut sheet, list every claimed quantity the footage can itself display (elapsed time, a timer, a clock, a counter, a price, a version, a count of items, a progress bar), sample the kept spans (`ffmpeg -ss <t> -i <raw> -frames:v 1`, about every 4 s across the kept window) and read what is visible. A kept frame that contradicts the claim kills the CLAIM, and every kept span still showing the contradiction is recorded in RUN.md with its **timeline window and raw source time**, so step 5 can cover, blur, crop or cut it without re-sampling the whole cut (an intro promised "under 10 minutes" over a visible Clock reading 29:53; finding the surviving 4-second window the next day cost six contact sheets).
- **Clip order in `cuts.json` = final order in the reel.**
- **A screen recorder's facecam is NOT lip-synced to its mic, and the offset drifts (your-job, 2026-09-19):** +1.9 frames at the start of a 53-min take, +8.3 by the end, hidden by a bubble until the cut goes full-frame. Before laying a facecam export as its own angle, `uv run workflows/lip-sync.py <cam> --audio <mic-source> --mouth-crop <w:h:x:y>` measures mouth motion against the voice across the take and fits the drift; each camera clip's in-point slips later by its own lag, timeline start/end unchanged, proved on a timeline export. **Pass the crop:** without it the generic band catches head and background motion on a wide framing and the tool exits 2 UNMEASURED. Pick it once per shoot off one frame (`ffmpeg -ss <t> -i <cam> -frames:v 1 mouth.png`), as fractions of the frame, `w:h:x:y` (a 3836-wide facecam: `iw*0.14:ih*0.16:iw*0.44:ih*0.53`): tight on the mouth, wide enough to survive the head moving. Exit 0 PASS, 1 FAIL with the slip formula, 2 UNMEASURED (the crop, not the footage).
- **Questions are a last resort, not a step.** Intent comes from the transcript (or sampled frames on a visual-only edit), format from the clips' aspect ratios. Never ask for those; infer, state your read in the report, let the creator correct it. Ask only when something is genuinely undecidable, and then one question, one sentence.

---

## Handoff

A restored or appended passage changes the final transcript and duration: refresh the canonical cut-aligned transcript, then send the affected window back through graphics planning/build, SFX, and final verification. A dialogue repair is not a finished passage while its required visuals or sounds are missing.

A cut change after step 3 re-times what is already PLACED as well: run `uv run workflows/ripple-cut.py projects/<job> --from <the EDL the graphics were authored against>` before re-placing anything — `edit-video` § Running a step owns the gate that reopens the downstream steps.

The cut lands on the finish surface; the line continues in `edit-video` (repo-root `CLAUDE.md` has the eight-step flow).

**Transcribe-once is a contract, not a convenience.** Everything downstream reads the canonical `outputs/<job>.transcript.json` — including the locked caption builders ([Talking Head Explainer](../../../presets/instagram/talking-head-explainer/captions-style.md), built by its [`captions.py`](../../../presets/instagram/talking-head-explainer/captions.py); [tiktok/raw](../../../presets/tiktok/raw/tiktok-raw-style.md)), which never re-transcribe.

This skill does ONE thing: cut the reel to the essential lines (audio is normalized as part of the cut). No captions, B-roll, zoom effects, or vertical reframing.
