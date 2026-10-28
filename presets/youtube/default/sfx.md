# SFX — the youtube/default sound design (pipeline step 6)

**WHAT only.** Which sound lands on which motion event, how it is sliced, how loud, and how the
layers stack. Every number here is app-independent. Placing a clip on a timeline is a lane
mechanic: [`LANES.md`](../../../LANES.md) § step 6 (Premiere: `lanes/premiere/place-sfx.py`).

Measured off the one shipped sound design, a hand-placed reference intro: 65 clips, 51
onsets, every one frame-grabbed and level-measured. The machine-readable copy is
[`sfx.json`](sfx.json); [`workflows/sfx-plan.py`](../../../workflows/sfx-plan.py) reads it and
turns the placed graphics into `projects/<job>/hf-graphics/sfx-plan.{json,md}`.

## The law

1. **Events come from the graphics, not from the transcript.** Every registry call a comp makes
   (`pop`, `slam`, `riseIn`, `slideIn`, `slideOut`, `drawOn`, `countUp`, `reveal`), every word of a
   text animation rising in, and every hard cut INTO a full-screen is an event. Cuts back to the
   face are not. Exits (`riseOut`, `exit`) are not. Talking-head stretches with no graphic get
   nothing.
2. **One sound per motion class, the same one every time.** Variation comes from slicing the file
   differently on a run, never from swapping sounds. The WOW is the singleton sting: not in the map, a plan-time
   call, one per piece at most. The bell (`payoff`) and the Impact (slam text, `emphasis`) ARE mapped
   events now — see § Sound follows MEANING.
3. **One-shots are sub-slices of the library file.** Each event class carries its slices in
   `sfx.json`; a run rotates through them so no two adjacent hits play the identical sample.
   Sustained classes (`countUp`, `reveal`) are cut to the event's duration.
4. **Timing is on the element's own onset**, snapped to the frame grid. A slide whoosh starts ON
   the slide start. A cut-in whoosh leads the cut by 2 frames; a riser ends 0.45s before it.
   Layers on one hit land on the same frame.
5. **Levels are class bands on the on-timeline peak**, so the clip level is target minus the
   measured slice peak, whole dB, never above +6. The seven bands and their targets are
   `targets_dbfs` in [`sfx.json`](sfx.json); transient sits at the voice ceiling and everything
   else is placed against it. The slice peak is the SLICE's alone; a plan made before 2026-09-23 (`71ed7f5`)
   levelled a slice against the loudest point from its file's start (the `drawOn` slice 11.18–11.93 at −8 dB; its own peak puts it at +2),
   so a LEVEL drift `place-sfx.py --verify` reports on exactly those rows after a re-plan is the fix, not a
   regression, and a `--merge` on an old plan can leave the same sound at both levels until the whole plan is re-planned.
   **The mix is held to −1 dBTP where sounds stack (2026-09-27).** The bands level each cue on its own, so a cut-in
   whoosh + a slam + a loud word reached −0.007 dBFS on a long-form, and the shipped your-job mix measured
   +0.3 dBTP. After the layers are assigned, `sfx-plan.py` mixes every cluster of overlapping cues (and, when it can
   rebuild the voice from the raw at the job's gain into the −6 dBFS limiter, every lone cue) with the voice under it
   and reads the TRUE peak; over −1 dBTP the deepest layer comes down first (A4, then A3, then A2), whole dB, at
   most 12 dB a cue, and a hand row keeps its level. Each change is listed in the cut sheet; a moment that stays
   under the ceiling is never touched. Proven on your-job: one pop down 4 dB, the whole mix +0.3 → −1.0
   dBTP with integrated loudness unchanged (−18.7 LUFS). **The music bed is under every stack too (2026-09-28):** with
   `hf-graphics/music-plan.json` on file the check decodes its track from `source_in` at `bed_db`, and since the bed is
   laid after the SFX, `sfx-plan.py --restack` re-levels the approved plan against it by the same rule (levels only);
   unheard, the bed took your-job from −1.0 to −0.7 dBTP.
6. **Three SFX tracks by layer depth** (the roles `primary` / `layer2` / `layer3`, which are A2 /
   A3 / A4 on this preset's track map and map by role on a lane laid out differently)**:** the
   primary track carries the first sound of every event; a sound
   that would OVERLAP a different sound still ringing on a track goes a layer down (layer 2, then
   layer 3) so both play out, while the same sound repeating on top of itself stays on one track and truncates
   (the reference's machine-gun pops). An identical sound within 2 frames is a doubling and is
   dropped. Music takes the `music` role's own track (A5 here), opt-in. No fades on any SFX clip, every clip hard-trimmed to its slice.
7. **Density follows the graphics.** The reference intro ran 1.25 events/s inside the graphics
   span. A plan that sounds every registry event lands near that on its own; it never needs
   padding, and it is then thinned by the two rules in § Density before it is laid; step 7 is taste
   on top of that.

## The map

**Event → sound → why. The level, the slice and any frame offset for every row live in
[`sfx.json`](sfx.json)** — that file is what the planner reads, so read it there rather than
keeping a second copy in sync here.

| event | sound | why |
|---|---|---|
| `pop` (a free-standing object appears) | Pop 1 | the object's own snap |
| `slam` (an object stamps) | Metal Pop | heavier landing, so a heavier transient |
| `riseIn` (a card, panel, row or label rises) | **Simple Whoosh 1, the SECONDARY whoosh** | the whoosh for anything that RISES into place |
| `slideIn` / `slideOut` and any scene move | **Simple Whoosh 2, THE PRIMARY whoosh** | the whoosh for anything that MOVES across the frame |
| `drawOn` (a strike, an arrow, an underline) | Pencils & Markers | a real marker on paper is the stroke's sound |
| `highlighter` (the yellow highlighter wiping onto a phrase in running text on a screen recording, `highlight/bake.py`, a hand row at the wipe start) | **Pencils & Markers**, one felt-tip swipe sized to the wipe, at a fixed −16 dB | a real highlighter stroke is its sound; subtle (2026-10-05) |
| `glow` (the red box drawn clockwise round a stat or a badge on a screen recording, `highlight/box.py`, a hand row at the draw start) | **Mac SFX 08**, the whole file at −10 dB | a glowing line, not a hand-drawn stroke; very subtle (2026-10-04; back for the box 2026-10-06) |
| `countUp` (a number stepping) | UI Data Loading | a bed under a machine counting |
| `reveal` (text typing on) | Keyboard Typing | real typing at a real level, not a texture |
| `flash` (spelled `flicker` in older specs) | **Neon Flicker** (paired) | the sound IS the strobe: one at its START, nothing on the landing |
| word on a RISE text animation | Scissors | the snip carries the word without a transient per line |
| a RED word (negation) | **Error Buzz** (paired) | a negative beat sounds negative |
| ~~word on a POP text animation~~ | ~~Pop 1~~ | RETIRED 2026-09-10: type never pops (animations.md § TEXT NEVER POPS); the Pop is an object sound |
| word on a SLAM text animation | **Impact** | it lands on the settle; the run truncates itself and the last word rings |
| TYPE in a hand comp (an element whose OWN text is words) | rise → Scissors · slam → **Impact** | the text sounds follow the words into full-screens and cards, read off the markup; a label inside a node/row/chip stays with its surface (whoosh) |
| `emphasis` (a script-critical word, named in the comp or a hand row) | Impact | the word that has to hit; it loses its scissors |
| `row-tick` (a `pop` inside a list/card graphic) | Lighter | a switch clicking on, not an object |
| `payoff` (a COMPLETION state: the finished node, a check, 100 %, the green state — read off the markup, or a hand entry) | Bell Ding | the reward; replaces the pop / slam / row-tick the element would have made |
| `rec` (a RECORDING STARTS: the REC badge of a camera UI, named `data-sfx="rec"` in the comp) | Camera Beep & Shutter, the beep at 5.33 | approved by ear on g24 (2026-09-10); replaces the badge's pop |
| `camera` (a CAMERA prop or a camera UI LANDING: viewfinder brackets, a shutter frame — named `data-sfx="camera"` or a hand row) | Camera Clicks, src 0–0.42 at −2 dB | your pick over Analogue Camera Snap (your-job g11, 2026-09-19); replaces the prop's pop |
| `gunshot` (NAMED: a literal shot, bullet holes) | Gunshot | the literal prop |
| `processing` (NAMED: software working) | UI Data Loading | the bed under a scrub / render / think span |
| `click` (NAMED: a cursor action in a software scene) | Mouse Click | the cursor arriving on its target |
| cut INTO a full-screen | Whoosh Short 2 | the cut's own sound; **dropped when a flash opens the full-screen** |
| the FIRST full-screen of the job | + Riser 2 | the piece's one build-up, whoosh or not |
| title card (section boundary) | Genius Intro Sound | the section's signature |
| `riseOut`, `exit`, cut back to face, push-in, an annotation's arrow | silent | nothing leaves with a sound |

### 🔒 Sound follows MEANING before mechanism (2026-09-10)

The event map above is the default, not a law. When a graphic SHOWS something — completion,
success, the green state, a check, 100 % — the sound represents that, and the mechanical entrance
sound steps aside. you, on the 'Postable Edit' node that popped: *"why isn't the postable edit
card a ding sound? … the reason you went with the pop is because that's the standard default sfx
for a pop animation … sfx aren't always so hard and fast like that."* `sfx-plan.py` reads the
completion signal off the comp (a completion class — `hi`, `done`, `check`, `success` —, completion
words in the element's own text, a green fill or stroke on it or inside it, a green CSS rule it
satisfies, or an explicit `data-sfx="payoff"`) and rings the bell instead; `data-sfx="pop"` opts
an element out. `pop` and `none` are the two OPT-OUTS: an element carrying either keeps its default
sound or goes silent, and its ancestors are not marked complete by it. Only `none` is also silent in
the REPORT, though (2026-09-19): `pop` is a real placeable event in the map below as well as the
opt-out, so an element marked `pop` that rode no registry call still shows under ⚠ as riding
nothing — the planner cannot tell a deliberate opt-out on hand-tweened motion from a cue the author
expected and never got, and losing a cue in silence is the failure this warning exists to catch. A
hand row in `sfx-hand.json` naming that event answers the line either way. **The palette is the DOCUMENTED map, and only that (2026-09-10, after the
chat-bubble blips: "so fucking heinous … you shouldn't try to go out and find sound effects
yourself because you really don't have the ability to actually listen to what it sounds like").**
The freedom is in WHERE a documented sound goes, not in which files exist: a pop that shows
completion takes the bell, a slam takes the Impact, a negation the Error Buzz, a software scene its
processing bed and clicks — every one of them named in this table with where it belongs and how it
is sliced, and approved by ear. Nothing outside the table is ever placed, however apt the filename:
`assets/sfx/` holds 130 files and the map documents the ones that have been heard. Name a
documented event where the element is authored — `data-sfx="<event>"` swaps the element's
mechanical sound for any event in `sfx.json` (`emphasis`, `gunshot`, `processing`, `click`
included); `data-sfx="none"` silences an element — or in a hand row for a timing the parser cannot
bind. The planner refuses `data-sfx-file` and a hand row's `file` with a warning. **A new sound
enters the palette one way, in order: you listens, it gets a row here, an entry in `sfx.json` and
its file in `assets/sfx/`, then it is named where the element is authored (`data-sfx` or a hand
row), and only then placed.** A cue that lives only in a job's `sfx-plan.json` or only on the
timeline is invisible to the planner and the next rebuild silently loses it (2026-09-19: a
hand-placed camera click and a job-local phone ring both would have gone). `sfx-plan.py`
names any event it does not find in `sfx.json` under ⚠ instead of dropping it in silence; an event
mapped to `null` there is deliberate silence and says nothing.
A marker rides a REGISTRY event on that same element (its `pop`, `riseIn`, `slam`, `slideIn`…): a
prop that moves on a plain tween or a node that arrives inside a scene's slide takes a hand row
instead — g16's processing bed and bell did (2026-09-10).

### 🔒 Density (2026-09-10)

Every event makes a sound, but not every sound survives. Two rules thin the plan, both in
`sfx.json` (`stamp_owns_beat_s`, `max_per_second`) and applied by `sfx-plan.py` before layering; a
third drop — the hand row that owns its frame — is the lock at the end of this section.

1. **The stamp owns its beat.** A slam / Impact carries the beat alone: the same graphic's other
   transients within ±0.6 s of it — the scissors of the words around the stamped word, the marker
   stroke of an underline under it, a pop — are dropped. The cut-in and the scene changes
   (`slideIn` / `slideOut`, structure rather than accent) stay; beds and hand entries stay.
2. **Three sounds a second, no more,** across all graphics in a rolling second — where a RUN of one
   sound from one graphic (the scissors of a text animation's words, a wall's machine-gun pops)
   counts once: the pile-up is different sounds from different graphics landing together. The
   lowest-priority source in an over-full second goes (the newcomer on a tie): marker < word <
   rise/slide < pop < slam < cut-in < Impact / character stings. Beds (typing, loading) are textures
   and are not counted; a source with a hand entry in it is never dropped.

**Under a second voice (a call, a phone) this map sounds as usual.** Silencing every automatic row
while `transcript/voices.json`'s other voice plays is a preset's rule, switched on by its own
`sfx.json` (`"second_voice": {"silence": true}`, the Talking Head Explainer's law 3); this map
does not carry it, so `sfx-plan.py` never reads voices.json on a job using it.

Earned on your-job: a 2 s stretch at 1:45 carried seven sounds — a 1.6 s Impact under
three scissors, a pencil scratch, the REC furniture's pop on the cut back and the next line's snip —
and the creator called it ("there's too many, it's too much going on"). After the rules: the Impact, the
pop, the snip. `sfx-plan.md` lists every drop under *dropped by the density rules*.

**The whoosh roles (2026-09-03)** are the map's: Simple Whoosh 2 moves, Simple Whoosh 1
rises, Whoosh Short 2 is the cut-in only. Other whooshes in the library are for other animation
types as they come up, one whoosh per type.

**Paired sounds (a sound that IS an animation's sound, never swapped):** `flash` (`flicker` in an older spec) ↔ Neon Flicker,
red word ↔ Error Buzz, list row ↔ Lighter, slam text ↔ Impact. `assets/sfx/Mac SFX 01–24.wav` are
the individual pieces of the old "Mac & Computer Sound Effects" file (index beside them); Neon
Flicker was 10, Error Buzz was 02; the rest are unassigned until they get used.

**Named calls (in the comp with `data-sfx`, or a hand entry):** an emphasis Impact on an especially
important word (styling alone, serif or italic, does NOT trigger it: scissors is fine on most
emphasis words), a payoff bell, a gunshot, a software scene's processing bed and clicks. They go
in `projects/<job>/hf-graphics/sfx-hand.json` as `{gid, event, at | word, dur?, level_db?, drop?}` (a graphic that deliberately makes no sound answers its "needs a hand entry" or "no comp found" ⚠ with `{"gid": "<id>", "silent": true}`);
`drop` removes the automatic events the hand entry replaces (the pops under a gunshot or a bell),
named as the PLAN names them: a pop the rules turned into a `row-tick`, a `riseIn` on type turned
into a `word`, or the registry call the comp actually wrote — either spelling drops the row. It drops a
preset kit's `"src": "kit"` rows of that event too (the kit's rows are the automatic first pass:
`workflows/sfx-plan.py`'s docstring), never a hand row.

**A hand entry OUTRANKS the automatic row it doubles, and a hand entry written to STAND IN for a
call the parser could not bind has to be retired once it can (2026-09-19).** Same sound, same
instant: the hand row is the one that survives, with its note, level and slice. A *different* sound
on the same frame of the same graphic is two accents on one beat, and the hand row owns that frame
too: `sfx-plan.py` DROPS the automatic row and names the pair under ⚠ — teaching the parser to read
a comp's times turns yesterday's stand-in into a double cue, and a warning alone still ships both
sounds. Retire the row, or give it `"drop": ["<the automatic event>"]` so the plan says so rather
than the tool inferring it every run. A cut-in, a riser or a bed under an entrance is the layer
stacking working as designed and is never flagged.

**Read off the timeline, not guessed (your-job, 2026-09-03):** every fixed level and frame
offset in `sfx.json` is the value placed by hand on the reference job. Reading the shipped
timeline back against the plan is how the next batch of hand edits becomes the next batch of rules
(the readback is per lane: [`LANES.md`](../../../LANES.md) § step 6). **Order matters: after the
creator's hand pass, read the diff BEFORE any re-place** — re-placing overwrites the hand edits the
diff exists to capture.

Sounds still unmapped, and when to reach for them: `Japanese WOW` on the one reveal of a piece;
`Slap` on a physical bump; `Deep Whoosh 4` + `Deep Whoosh 3` a second later on a big
drop-out-and-launch; `Paper Turn` when the surface IS paper (the vox look, not this one). Each one
enters the palette the one way above (§ Sound follows MEANING) before it is placed.

**Graphics revisions:** run the lane's `--diff` first and fold every approved hand edit upstream (`sfx.json` / `sfx-hand.json`) so a rescore reproduces it. A bare re-run of `sfx-plan.py` REWRITES `sfx-plan.{json,md}` and prints the graphic IDs whose rows changed; when the approved plan carries edits that live nowhere upstream, run `sfx-plan.py <job> --merge <gids>` instead: it re-plans only those graphics against the current placement and swaps their rows into the approved plan (every other row byte-identical, ids stable, the plan backed up first, a cue adopted off the timeline kept and named; a repeat of an approved sound stays on its layer, and a graphic that left `placement.json` is merged out). `--merge` makes every cross-graphic decision (the repeat's cut, the doubling, three sounds a second) against the APPROVED rows, never against a fresh row of another graphic that the merge does not keep; the merged graphics' own adopted (event `hand`) rows count as approved context. A merge also keeps a variant plan's recorded copy window (`--until`, the Premiere lane's adopt/copy bullet). `--candidate` (parks `sfx-plan.candidate.{json,md}` beside it) stays for a whole-plan comparison. When the creator's timeline is the truth, the lane's adopt (Premiere: `place-sfx.py --adopt`) writes it into the plan instead. The lane placer warns and names a graphic that moved after the plan was derived (`sfx-plan.meta.json` records each graphic and its cue times); a re-cut that moved a graphic together with its cues (`ripple-cut.py`) is not stale, and a plan with no record (an older job's, an AD cut's) is recorded with `sfx-plan.py <job> --record [--plan <file>]`, which changes no row. To re-time a cue onto a graphic's event, measure it: `uv run workflows/change-events.py <placed render> [--alpha] [--region x,y,w,h]` prints each change's frame and seconds on the render's clock (row start + seconds = timeline; `--alpha` says whether ink appeared or disappeared), and a change at or after the row's out-point is trimmed off the timeline and gets no cue. Never hand-run tblend / signalstats or frame differencing. Remove the exact stale affected timeline clips, then apply and verify. After an interruption, read back all SFX before resuming: completion requires zero missing, extra or drifting cues, even when apply adds nothing.

## Definition of done

`sfx-plan.json` written and reviewed as a cut sheet (`sfx-plan.md`), unresolved parser/source warnings resolved with source fixes or explicit hand entries, every row placed on the
lane's SFX tracks at its planned frame with its planned level, **read back with zero missing, extra or drifting cues**, and a frame grab at
a sample of onsets showing the event the sound sits on (the event's own time comes from `workflows/change-events.py`, above). Runs AFTER the step-5c defect loop dries
(a graphic retimed later orphans its sound); follow the incremental revision procedure above after any graphic moves.
A cue the creator placed by hand out of the job's own `audio/sfx-src` is NOT drift: the lane's readback
names it so it cannot go missing in silence, and leaves it where it is (its answer is the two steps
above — a library file and a preset entry, so the next rescore owns it), never a failed gate and never
a sweep's target.

**"Drifting" is the LANE's tolerance, not a preset number.** Each lane holds one source-in tolerance for
its readback and its diff, so the rows the gate fails are the rows the diff names; Premiere's value and
why it tightens are in [`lanes/premiere/lab-notes.md`](../../../lanes/premiere/lab-notes.md) (the audio `overwriteClip` in-point bullet).

**Any STRUCTURAL timeline edit after step 6 reopens it** — a ripple, a reorder, a re-lay, a range
sweep, a restore: cues sit on their own tracks and a sweep or a shift takes them silently (your-job,
2026-09-19: a preview moved to the front swept two whooshes off A2/A3 and the creator caught it by
ear). Run the lane's `--diff`, then `--verify`; zero missing, extra or drifting is the gate, and a
cue the edit legitimately moved is followed by shifting its plan row, never left as drift.
