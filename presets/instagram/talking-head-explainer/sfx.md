# SFX: the Talking Head Explainer's sound design (step 6)

**WHAT only, for this format.** Which sound a 9:16 talking-head explainer puts on which visible event, how it
is sliced, how loud, how early, and why. The house law (layer roles, the density cap, the documented palette,
the revision procedure, the definition of done) lives in
[`presets/youtube/default/sfx.md`](../../youtube/default/sfx.md) and is linked here, never restated: this file
is the delta. The machine-readable copy is [`sfx.json`](sfx.json); [`workflows/sfx-plan.py`](../../../workflows/sfx-plan.py)
reads it because the plan's `preset` is this folder, and § 3 mirrors it row for row
(`workflows/test_talking_head_kit.py` fails when they drift; change both in one edit). Placing a clip is a lane
mechanic: [`LANES.md`](../../../LANES.md) § step 6.

Every timing rule is in frames. Milliseconds depend on the job's fps.

## 0. The bar

Claude laid a complete, event-driven first pass on the benchmark short. you then sound-designed the reel by hand
over two nights ("dialed them in so that they're actually good"; "our current timeline is the source of truth", 2026-09-23). 44 of the plan's rows survived untouched, and about 55 of the 103 final clips were yours: swaps
and whole textures added (most of them), re-levels, a few moves; the rest were plan rows retimed onto a rebuilt
graphic. Few of your edits changed WHERE a sound sat. Nearly all of them changed WHICH sound and HOW LOUD. This file
and [`sfx.json`](sfx.json) encode your pass, so the next automatic pass starts where your ended. A first pass you have to
re-design is a failed first pass, however complete.

The house law still applies unchanged: tracks are layer roles; at most 3 different sounds in a rolling second; a
run of one sound from one graphic counts once; a stamp owns ±0.6 s of its own graphic
([house § Density](../../youtube/default/sfx.md#-density-2026-09-10)); and only documented sounds play
([house § Sound follows MEANING](../../youtube/default/sfx.md#-sound-follows-meaning-before-mechanism-2026-09-10)).

## 1. The law

Each rule, then its WHY. The numbers live in § 3 and [`sfx.json`](sfx.json).

1. **Sound the literal thing on screen: the device, the material, the action. Never the animation verb.** Ask
   what the object would really sound like where it lives, not what a pop tween "gets".
   - a phone or messaging affordance (an accept button, a keyed digit, a text badge) gets a touchscreen tap (`tap`)
   - a desktop cursor gets a mouse click (`click`)
   - typed words get keyboard typing (`typing`)
   - a snapshot (a montage close-up) or a cut between captured pages gets a camera shutter (`camera`, `camera-under`)
   - round bubbles get a bubbly pop (`bubble`)
   - a device changing state gets a UI/OS sound (`live`, `status-chime`, `status-keys`, `blip`)
   - movement gets a whoosh (`riseIn`, `slideIn`, `slideOut`, `travel`, `send`, `reply`)
   - completion gets the bell (`payoff`)
   - a strike gets a marker (`strike`)

   WHY: every one of your swaps replaced a generic sound with the diegetic one: a mouse click on a phone's accept
   button became a tap, keyboard typing under digits keyed on a phone became taps, a slam on a docking object became
   a whoosh, the bell on a status became an OS chime. A generic sound tells the ear "an animation happened"; the
   literal one tells it "a phone was answered". The house rule "sound follows MEANING before mechanism"
   (2026-09-10) picked which event fires; this extends it to which object is on screen.
2. **Every sound sits on a visible event inside a graphic.** The face, the captions, exits and cuts back to the face
   are silent. WHY: a sound makes a visual event land; under plain talking it only competes with the voice, and the
   caption layer runs the whole clip, so sounding it would sound every word. In your final every cue maps to an
   event inside a graphic, and the bare-face stretches carry only the music bed.
3. **Nothing over proof audio, and this outranks every other rule.** While another voice plays (an agent on a live
   call, a played clip), only the call UI's own beats sound: the ring while it rings, the answer tap, the card's
   entrance. Then nothing, even for 10 s or more: a layout switch (no cut-in), a completion (no bell) and a real
   message landing stay silent until the voice ends. WHY: that voice is the content and the evidence. A whoosh or a
   bell on top of it competes with the proof and makes it feel produced. Your longest silences in the reel are
   exactly these spans. This map switches it on (`sfx.json` `second_voice.silence`), so the planner drops every
   automatic row inside `transcript/voices.json`'s spans; the house map does not carry the key.
4. **A layout switch always gets the same whoosh; a sibling cut sounds itself, except the push.** A cut from the
   face into a graphic (W, T or O into S or F; the layouts are [`layout.md`](layout.md)'s) and a switch between S
   and F take `cut-in`, 2 frames early, identical every time. The lateral push
   ([`layout.md` § 5](layout.md#5-transitions)), graphic to graphic inside S, is the one sibling transition that
   takes it too: the whole panel travels, so it reads as the frame changing (the CTA hand-off, shipped on your go); a
   push into the CTA's promised page adds `camera-under`, as a face cut into it would. Every other sibling cut
   inside the split takes the incoming element's own sound (its slide, its pop) or a context sound (the shutter of
   a montage or a cut between the CTA's pages, the typing of a recording that opens mid-typing), never the cut-in.
   While another voice speaks, a switch is silent (law 3). WHY: one fixed sound for "the frame changed layout"
   teaches the ear the grammar and hides the seam; sibling cuts are content moving, and a second structural whoosh
   there blurs the grammar. You kept every cut-in untouched, and when you cut a whole line you dragged the orphaned
   cut-in onto the new face-to-graphic join rather than dropping it. A still page opening from the face (a brand
   page, a product still) rides the cut-in alone: you added a shutter under a cut-in only on the CTA's promised
   page, where the page itself is what is being handed over.
5. **Align the audible ATTACK to the event, 0 to 2 frames after it.** The clip starts ahead by the file's own
   pre-roll, so the lead is per file (§ 3). Phone taps land on the release (the moment the call connects), not the
   press-in. A multi-hit texture (taps, typing, a strike) starts with its first element and ends within a frame of
   its last. WHY: that is how you hear sync by ear, with your attacks a median of about 1 frame after the picture. A
   single class offset put the typing 7 to 8 frames late and the strike too early, and you moved both.
6. **Anticipation leads; impacts sit on the frame.** A ring starts where the speech or the picture says the phone is
   ringing, before the card when the speaker reacts to it ringing, and is hard-cut at the answer tap. An impact
   lands on its frame. WHY: a ring is heard before it is seen and stops when it is picked up; an impact that arrives
   early reads as a mistake (you nudged one a frame later onto its hit).
7. **The bell means COMPLETION only.** Booked, sent, posted, landed in its column: `payoff`. Available, connected,
   reachable, live, signal bars lighting: a UI/OS chime (`live`, `status-chime`), key ticks (`status-keys`) or a
   data `blip`, even on a green badge. WHY: the bell is the reward for something finished; a status coming online is
   the system talking, so it sounds like the system. You replaced the automatic bell on a green "reachable" badge, and
   Lighter ticks on signal bars (the Lighter is off this format).
   The planner's completion read rings the bell on anything green, so a green status element carries
   `data-sfx="live"` (or another documented event) where it is authored; a named event outranks the read.
8. **A run of one thing is one gesture.** One track, back-to-back slices of one file each truncating the last,
   in-points rotated, one clip level, a notch quieter than a single hit (`pop-run`, `payoff-run`, `char-run`
   closed by `char-last`). WHY: repetition reads as a pattern, so each repeat needs less; a run is rhythm, not six
   accents, and overlapping full tails smear into noise. You flattened a +2/0/−6 pop run to one level and pulled
   three bells in a row 3 dB under a single bell. A run of payments is the same gesture: cha-chings on one layer, one
   per landing, each cut off by the next and the last left to ring (2026-10-15: "uniform in rhythm... they sort of
   cut each other off, and then the last one goes all the way through"; your own spacing was 6 frames: `money-run`
   then `money`).
9. **The negative verdict comes at the END of a build, loud, as the working bed cuts.** When a graphic builds into
   overwhelm, `error` lands after the last element arrives, on the bed's cut, at 0 dB. WHY: the buzz judges the
   pile-up, so it waits until the pile-up is complete. On the first red frame at −7 it competed with the pops and
   said nothing; you moved it most of a second later and 7 dB up.
10. **A process lasting seconds gets a quiet bed that ends on its payoff.** Software working: `processing`, from the
    moment the work starts, cut hard where it resolves. A calling or waiting bed may fade instead: `calling`, and
    your one fade in the reel is about 2.2 s Constant Power on it. WHY: a texture makes the process audible without
    adding accents, and beds are not counted toward density. One-shots never fade.
11. **Sound the actions, not every state change.** Drop an accent that lands inside a sound already carrying the
    beat. Typing dots, a sent bubble stepping up, scroll-ups, bobbing arrows and badges landing under a run's
    ring-out are silent (`data-sfx="none"`). WHY: every event is a candidate, but two accents on one beat is clutter,
    the house density lesson applied on shorts. You removed a slam inside a slide whoosh's tail and the badge pops
    under a run's ring-out, and left the typing dots and the scroll-ups silent. What decided the badges was the
    ring-out, not the spoken word: the next badges, landing on their own word once the run had rung out, got taps.
12. **Movement is a whoosh, never a stamp; in a chat, who sends decides.** Rise or drop-in: `riseIn`. Slide,
    collapse, leave: `slideIn` / `slideOut`. Fly or dock: `travel`. In a chat, split by the sender, not by whether
    the app scrolls:
    - other people's or agents' messages landing in a thread are objects: one `pop` per landing, the level
      stepping down as they keep coming (`pop-hero`, `pop`, `pop-cascade`), even while the app scrolls
    - your own send, and the reply to it in a one-to-one chat, are `send` (a trimmed light whoosh) when the framing
      moves with them, and a `click` on the send plus a `pop` on the message when the framing holds still
    - a reply sliding up into an empty chat (the reply-only reveal): `reply`

    WHY: the visible thing is travel, even when it seats at the end. You replaced a docking slam with the travel
    whoosh, and a send click + reply pop with two short whooshes where the framing drifted with your send and the
    reply; the agents' messages landing in both group chats kept their pops, and a still desktop chat kept its
    click + pop.
13. **Type and hard snaps are snips; objects pop; only slammed type gets the Impact.** Rising words: `word`, the
    house per-word scissors ("our default text rise in with the scissor sound effects", 2026-09-23). A
    glyph snapping in, or a hard snap-cut inside a graphic: one loud `snap`. A keyword or CTA card landing is an
    object: `pop-hero`. Only type that SLAMS (a figure, a claim word) takes `word-slam`. WHY: type never pops
    (house); a snip carries a word without a heavy transient, and the Impact stays rare so it keeps its weight ("a
    pop, not the Impact", on a CTA keyword card).
14. **Density follows the graphic, and the animated hook is sounded on every beat from frame 0.** The per-passage
    bands are § 5; the hook sits at the top of them, with the busiest enactments. WHY: the first seconds must grab,
    and sound is a large part of pace. Your pass was denser in hits than the plan but not in sources: single generic
    hits became multi-hit literal textures. Density is an outcome of what moves, never a quota: a static hook ahead
    of a demo stays quiet, and a cold open that IS proof (another voice speaking from the first frames) is sounded as
    a call overlay, the card's entrance and the call UI's own beats only (law 3). The hook band is for an authored
    hook.
15. **Layer by depth: tracks are roles. Two overlapping cues never share a track.** `primary` carries every cut-in
    and most entrances; a different sound still ringing sends the next one to `layer2`, then `layer3`; beds take the
    lowest free layer; a repeating sound stays on its own track and truncates. WHY: both sounds of an overlap must
    play out, and on an editor a clip laid over an occupied span replaces the one under it: a strike was lost that
    way under a moved whoosh.
16. **Levels by role, read as the peak on the timeline:** close accents hot (taps, snips, bubble and single pops:
    about −1 to −6 dBFS; typing hotter still, its +2 clip level putting its slice's own peak near +0.6 on the clip,
    which the mix held under the README's −0.3 dBTP ceiling), structure about
    −4, soft motion −5 to −10, chimes, clicks, rings and bells −8 to −17, beds −23 to −26. The fixed clip levels
    that produce them are § 3. WHY: the accent IS the event and the texture must not mask the voice; every level you
    changed pushed a literal action sound up or a repeat or a bed down. Hot accents ride above the voice's −6 dBFS
    limiter by design, and your finished master still read −0.3 dBFS true peak with nothing clipped; the mix check
    is the README's [§ Audio](README.md#audio-step-3-addendum-what).
17. **A graphic added to a reel whose sound is designed ships sounded, in that reel's vocabulary.** Take its sounds
    from the ones you already used there, at your levels, slices and leads, picked by the ladder (§ 4). Where a
    redesign removes the motion under one of your sounds, move the sound to the equivalent new event at its old
    lead, or give the picture a small event there (a 1 to 1.1 bump on the word). A graphics-only ASK on a fresh
    job still stops before step 6 ("if I say just do the graphics then just do the graphics", 2026-09-19).
    A graphic that plays under another voice is silent by design (law 3), never a defect. WHY: a new card shipped
    silent "since you only asked for the graphic", and a minute later you asked for the rise and the scissors. In a
    finished reel a silent graphic is a defect, and a sound with nothing under it reads as a mistake.

## 2. Where the first pass's cues come from

The target is a first pass with no hand rows, every source automatic, so the planner sees the whole reel:

- **Face-to-graphic cut-ins come from the plan's layout map.** `workflows/sfx-plan.py` reads the plan's top-level
  `layout` and writes one `cut-in` at every switch into S or F from W, T or O and at every switch between S and F
  ([`layout.md`](layout.md) owns the map; `layout.py`'s `switches()` lists them), on the switch frame with the
  map's 2 f lead, filed under the graphic the switch opens. None at a sibling cut (S to S) and none into O. A
  placed full-screen under an F span takes no second cut-in of its own. Check the cut sheet's cut-in count against
  the switches. Where the kit also writes one (a montage entered from the face), the planner keeps one copy (the
  doubling rule); the push into the CTA is a sibling cut, so its cut-in is the kit's alone.
- **Type comes from the registry.** A house `riseIn` on type in a kit comp becomes per-word `word` snips through
  sfx-plan's own type remap; a `slam` on type becomes `word-slam`.
- **Every kit component writes its own cues** into `hf-graphics/sfx-hand.json`, as rows tagged `"src": "kit"`
  ([`kit/components.py`](kit/components.py), written through [`kit/engine.py`](kit/engine.py)), each timed from
  the words and frames the component already anchors to:
  - call card: the drop-in `riseIn`, a `ring` fitted to the answer (where the speech says it rings, cut at the
    tap), the `tap` on the release
  - thread CTA: the composer's `riseIn`, `typing` across the keyword, `payoff` on the send, the reply's whoosh
  - click CTA: the push `cut-in`, `pop-hero` on the icon bump, `riseIn` on the button, `click` on the tap
  - captures: `camera` at each montage cut, `typing`, a `pop` per message landing in a thread, `send` and `reply`
    whooshes, `payoff` on a card landing in its board, `click` on a cursor, each from the shot's measured events
    ([`captures.md`](captures.md) owns the shots)

  These are automatic rows, under the density law, not your calls: the kit composes them inside the cap, a rebuild
  rewrites them, and a row without `src` (a real hand row) outranks them ([`sfx.json`](sfx.json)
  `hand_entries`). A hand_only event is never written by the kit or inferred by the planner. `money` and
  `money-run` are laid by Claude as hand rows on the first pass, on the two moments rung 14 names, each row's note
  saying so; `sizzle` and `riser` are laid only on your ask
  or your yes, the step-6 report offering each once where it fits.

  A kit row may also carry `sync_offset`, a designed lead from its word (seconds, negative = ahead: masked_value's
  first tap, [`graphics.md`](graphics.md) § 15 6b). sfx-plan ignores it; `change-events.py --sync` reads it.
- **Registry calls on a comp's own elements** (`pop`, `riseIn`, `slideIn`, `slideOut`, `drawOn`, `countUp`,
  `reveal`) map straight through [`sfx.json`](sfx.json). Where the markup's default is the wrong object, the
  element names the right one: `data-sfx="tap"` on a phone button, `data-sfx="live"` on a green status badge,
  `data-sfx="none"` on a micro-motion.
- **Only events documented in sfx.json may be used.** The planner refuses a file name in a hand row or a
  `data-sfx-file`. A new sound enters the library and sfx.json after you have listened
  ([house rule](../../youtube/default/sfx.md#-sound-follows-meaning-before-mechanism-2026-09-10); § 7).

## 3. The map

The rows of [`sfx.json`](sfx.json), one per event. **Clip dB** is the fixed Volume level set on the clip, not a
peak. **Slice** is seconds into the library file; `whole` places the file whole; `fit` means the slice is an upper
bound cut to the row's `dur`. **Lead** is where the clip starts against its event: `N f early` (sfx.json
`lead_frames`), `N f late` (`offset_frames`), or `0`, on the anchor named in the WHY. Library:
`assets/sfx/`. Levels and leads are your hand pass read off the finished timeline (2026-09-23).

| event | file | slice | clip dB | lead | WHY |
|---|---|---|---|---|---|
| `cut-in` | Whoosh Short 2.mp3 | whole (0–0.693) | −4 | 2 f early | the layout changing (W, T or O into S or F; S and F switching) and the lateral push: one fixed sound teaches the grammar |
| `riseIn` | Simple Whoosh 1.wav | whole (0–0.467) | −2 | 0 | a card, row, composer, bubble or call card rising or dropping in, on its first frame |
| `slideIn` | Simple Whoosh 2.wav | whole (0–0.312) | −2 | 0 | a slide in: movement is a whoosh, never a stamp |
| `slideOut` | Simple Whoosh 2.wav | whole (0–0.312) | −2 | 0 | a slide out, a collapse, an element leaving across the frame (a plain exit is silent) |
| `travel` | Fast Whoosh.wav | whole (0–0.79) | −8 | 2 f early | an object flying or docking to a new place, even when it seats at the end |
| `send` | Simple Whoosh 1.wav | 0–0.25 | 0 | 0 | your own send, or the reply to it in a one-to-one chat, while the framing moves with it: a trimmed whoosh, not click + pop |
| `reply` | Simple Whoosh 2.wav | whole (0–0.312) | 0 | 0 | a reply sliding up into an empty chat (the reply-only reveal), nothing else on the beat |
| `pop-hero` | Pop 1.wav | 0–0.25 · 0.08–0.33 | +2 | 0 | the graphic's hero object, and a CTA keyword, card or icon landing: an object pops, never the Impact |
| `pop` | Pop 1.wav | 0.46–0.71 | 0 | 0 | a sibling object (an icon, an avatar), and another sender's message landing in a thread; the attack sits on the back.out landing |
| `pop-cascade` | Pop 1.wav | 0.88–1.08 · 1.17–1.25 | −6 | 0 | the later objects of a cascade: the pattern is heard, each repeat needs less |
| `pop-run` | Pop 1.wav | 0–0.29 · 0.46–0.71 · 0.88–1.08 · 1.17–1.38 · 0.08–0.33 | −7 | 0 | a fast burst, 3 to 4 f apart: one gesture, one track, one flat level, slices rotating |
| `row-tick` | Pop 1.wav | 0.88–1.08 · 1.17–1.25 | −6 | 0 | a list row ticking on (the planner's pop-in-a-list remap): the cascade pop, never the Lighter |
| `bubble` | Bubble Pop.wav | 2.336–2.545 | −4 | 0 | a round orb or bubble appearing: the literal bubbly pop |
| `char-run` | Metal Pop.wav | 0.5–0.583 | −3 | 0 | characters or avatars in quick succession: 2-frame metal slices back to back, each on its landing |
| `char-last` | Metal Pop.wav | 0.5–0.79 | −3 | 0 | the run's last character: the same hit left to ring, which closes the gesture |
| `bump` | Metal Pop.wav | 0.5–0.83 | −7 | 0 | the punchline's scale bump on its last word, on the layer below |
| `word` | Scissors.wav | 0.63–0.75 · 1.21–1.42 · 2.25–2.46 · 4.55–4.67 · 5.55–5.67 | −7 | 0 | every word of a rise text animation, on its onset: type never pops |
| `snap` | Scissors.wav | 0.542–0.834 | 0 | 2 f early | a glyph snapping in, or a hard snap-cut inside a graphic: one loud snip |
| `word-slam` | Impact.wav | 0.93–2.5 | −10 | 2 f late | a slammed figure or claim word, on the settle; the run truncates and the last word rings |
| `slam` | Impact.wav | 0.93–2.5 | −10 | 2 f late | a registry slam: only type slams on this format, and a dock is `travel` |
| `tap` | Texting On Phone.mp3 | 0.417–0.583 · 0.792–0.917 · 1.168–1.335 · 1.376–1.501 · 1.96–2.169 · 2.794–3.169 · 4.963–5.297 | 0 | 0 | a phone or messaging affordance pressed or landing, anywhere (an accept button, a keyed digit, a text badge on an avatar), on the finger's release; a run is a texture of taps |
| `click` | Mouse Click - Computer Clicking.aiff | 2.44–2.9 | −10 | 0 | a desktop cursor pressing, on the press frame (the attack sits about 2 f in); never on a phone |
| `typing` | Keyboard Typing.aiff | fit 3.84–37.44 | +2 | 0 | words typed on screen, from the first letter, cut to the typed span: real typing at a real level |
| `reveal` | Keyboard Typing.aiff | fit 3.84–37.44 | +2 | 0 | a registry reveal: the `typing` spec, cut to the reveal |
| `ring` | Phone Dial Ring.wav | fit 4.588–13.003 | −8 | 0 | ringing that is the point of the line (answered, reacted to, or unanswered as the pain), from where the speech says it rings, fit to the ringing, hard-cut at an answer tap |
| `camera` | Camera Clicks.mp3 | 0–0.334 | 0 | 2 f early | a montage cut (close-ups snapped in to rhythm, its entry from a graphic included): the shutter IS that cut's sound |
| `camera-under` | Camera Clicks.mp3 | 0–0.334 | −2 | 2 f early | the CTA's promised page: under the cut-in that opens it, and alone on a cut between the CTA's pages (also under a montage's entry from the face); a brand page or a still from the face takes the cut-in alone |
| `status-keys` | Keys Up and Down.wav | 0.334–0.667 | −5 | 0 | a device changing state (going live, connecting, bars lighting): key ticks, layered with `status-chime` |
| `status-chime` | Mac SFX 16.wav | whole (0–0.727) | −4 | 0 | the UI chime of that state change, on the next layer (and a notification banner landing on a phone): the system talking, never the bell |
| `live` | Mac SFX 08.wav | whole (0–0.668) | −2 | 0 | a reachable / live / online badge, on its frame: green is not completion |
| `blip` | UI Data Loading Sound Effect - 128.mp3 | 0.209–0.584 | −5 | 0 | a connection lighting up: a short, louder cut of the working-bed file |
| `error` | Error Buzz.wav | whole (0–0.24) | 0 | 0 | the negative verdict at the end of a build, on the working bed's cut, loud |
| `processing` | UI Data Loading Sound Effect - 128.mp3 | fit 0.57–2.4 | −17 | 0 | software working for seconds, from the work's start, cut hard on its payoff |
| `countUp` | UI Data Loading Sound Effect - 128.mp3 | fit 0.57–2.4 | −17 | 0 | a number stepping: the machine working, the `processing` bed fit to the count |
| `calling` | UI Data Loading Sound Effect - 128.mp3 | fit 0.167–4.338 | −14 | 0 | a calling or waiting state that resolves softly: a louder bed with a 2.2 s Constant Power fade-out: sfx-plan carries `fade_out_s` into the row and the cut sheet, and the lane lays it by hand (no placer lays it yet) |
| `payoff` | Bell Ding Sound Effect.wav | 0–1.46 | −10 | 4 f early | COMPLETION only: booked, sent, posted, landed in its board |
| `payoff-run` | Bell Ding Sound Effect.wav | 0–1.46 | −13 | 4 f early | the bell repeating in a row: each 3 dB under a single bell |
| `strike` | Pencils & Markers.mp3 | fit 11.303–12.054 | −3 | 2 f late | a strike-through or stroke run: one continuous scribble spanning the run, hot, on the layer below its whoosh, on the first visible stroke |
| `drawOn` | Pencils & Markers.mp3 | fit 11.303–12.054 | −3 | 2 f late | a registry draw-on: the strike scribble, a marker being the stroke's own sound |
| `money` | Cash Register Cha-Ching  Sound Effect - 128.mp3 | 0.35–1.53 | −12 | 0 | hand_only, laid by Claude on the first pass: the headline money figure revealed on screen and a payment landing; the row sits so the CHA's attack (src about 0.54) hits the highlight's first frame or the landing, the ching following; a run's last landing, left to ring (2026-10-15) |
| `money-run` | Cash Register Cha-Ching  Sound Effect - 128.mp3 | 0.542–0.792 | −12 | 0 | hand_only: every landing of a payment run but the last, the cha alone, cut off by the next on the same layer (your hand pass, 2026-10-15: 6 frames apart) |
| `riser` | Riser.wav | 0.0–1.29 | −12 | 0 | hand_only: your own hand edit, a riser ending 2 frames before the first face-to-graphic switch after the hook's promise, the switch's cut-in on it; offered once in the step-6 report (2026-10-15) |
| `sizzle` | Hot Sizzling - Sound Effect HD.mp3 | 0.0–2.6, 0.4 s fade | −26 | 0 | hand_only: something cooking on screen, a very faint bed from the moment it hits the heat (2026-10-15, the stove) |

**Documented silence** (mapped to `null` in sfx.json, so a registry call never falls through to "unknown"):
`riseOut`, `exit`, `cut-out` (exits, cuts back to the face and push-ins), `flash`, `word-flicker` (no strobe entrance in this look), `title-card` (no section cards on a
short), `word-pop` (type never pops), `word-negative` (a red word is not a verdict; the negative hit is the error
buzz at the end of a build), `emphasis` (a word that must hit is a slam or a bump), `gunshot`, `rec`, `highlighter` (not in
this format's vocabulary until you have heard one here), `glow` (long-form's red box round a stat; a figure
highlighted on this format sounds as its money cha-ching).

## 4. The decision ladder (first match wins)

1. **Another voice speaking** (an agent on a call, a played clip)? Only the call UI's own beats: its `ring`, the
   answer `tap`, the card's `riseIn`. Nothing else until the voice ends. This rung outranks every rung below, the
   cut-in and the bell included (law 3).
2. **A cut from the face into a graphic, S and F switching, or the lateral push?** `cut-in`. The graphic's first
   element still takes its own entrance on the next layer (a slide, a rise; `typing` when a recording opens
   mid-typing). A still page adds nothing, the cut-in is its sound, except the CTA's promised page, which adds
   `camera-under`; a montage entered from the face adds `camera-under` for its first snap.
3. **A completion** (done, booked, sent, posted, landed in its board)? `payoff`; repeated in a row, `payoff-run`.
4. **A state becoming available** (reachable, live, connected, bars lighting)? `live` on a badge, `status-keys` +
   `status-chime` on a device connecting, `blip` on a connection lighting up. Never the bell, even on green. **A
   notification banner landing on a phone** (a missed call, a new message) is the OS talking too: `status-chime` on
   the banner's frame, and a stack arriving together is one gesture, the chime on the first. Not yet on one of your
   timelines: name it in the step-6 report. **A PAYMENT notification is money, not the OS:** rung 14 (you swapped the
   chime for the cha-ching on 2026-10-15).
5. **A phone or messaging affordance pressed or landing** (an accept button, a digit keyed, a text badge, on a phone
   or on an avatar)? `tap`, on the release. A run of digits or badges is a texture of taps across the run on one
   track, not one per element. Any other badge (a status dot, a count) is an object (rung 11).
6. **A desktop click?** `click`, on the press.
7. **Words typed?** `typing` (a registry reveal is `reveal`, the same spec), from the first letter, cut to the typed
   span. When the typing starts at a sibling cut, it IS the cut's sound: start it 1 to 2 f before the cut, no
   whoosh.
8. **A phone ringing?** When the ringing is the point of the line (the call is answered on camera, the speaker
   reacts to it ringing, or calls ringing out unanswered are the pain): `ring` from where the speech or the picture
   says it rings, fit to the ringing, hard-cut at the answer `tap` when there is one. The unanswered case is law 1
   read forward, not yet on one of your timelines. A call card that arrives as one UI beat of an enactment (an ease
   claim's "the phone rings") or opens already live: no ring, just its `riseIn`, as you left one.
9. **A snapshot?** A montage of close-ups: `camera` on every cut, its entry from a graphic included, no whoosh
   between shots. The CTA's pages: `camera-under` on each page cut, under the cut-in when one opens the panel from
   the face.
10. **Movement?** Rise or drop-in `riseIn`; slide, collapse or leave `slideIn` / `slideOut`; fly or dock `travel`;
    your own send, or the reply to it, while the framing moves with it `send` (with the framing still: `click` on the
    send, `pop` on the message); a reply sliding up into an empty chat `reply`.
11. **An object appearing?**
    - the graphic's hero, or a CTA card, keyword or icon: `pop-hero`
    - a sibling: `pop`
    - another sender's message landing in a thread: one pop per landing, stepping down as they keep coming
      (`pop-hero`, `pop`, `pop-cascade`)
    - the later ones of a cascade: `pop-cascade`
    - a fast burst of one kind, 3 to 4 f apart: `pop-run`
    - round orbs or bubbles: `bubble`
    - characters or avatars in quick succession: `char-run`, the last one `char-last`
    - a row ticking on inside a list: `row-tick` (the planner remaps it itself)
12. **Type?** Rising words `word`; a glyph snapping in or a hard snap inside a graphic `snap`; a slammed figure or
    claim `word-slam` (a registry `slam` resolves to the same). Never a pop on type.
13. **A strike or a drawing?** `strike`, one continuous slice fit to the whole stroke run, on the layer below any
    whoosh on that beat; a registry draw-on is `drawOn`, the same sound.
14. **Money?** Laid by Claude on the first pass on two moments only, each row's note saying it is Claude's first-pass
    call (so your own pass can be told from it), and named in the step-6 report:
    - the headline money figure revealed on screen (the proof hook's revenue): `money`, the cha's attack on the
      highlight's first frame, the ching following ("the cha-ching needs to come in later, like when it starts
      highlighting");
    - payments landing (a payment notification, a completed checkout): `money` on a single landing; a run is law 8's
      gesture, `money-run` on every landing but the last and `money` on the last, ringing out.

    Never on every number: a price on a page, a meter filling or a figure in a caption stays silent or takes its own
    object's sound. (2026-10-15: both moments asked for on one short, and your hand pass laid exactly this.)
15. **A build into overwhelm?** `processing` under the build, `error` after the last element lands, as the bed cuts.
16. **A process running for seconds?** `processing` (a count, `countUp`), cut hard on its payoff; a calling or
    waiting state, `calling`, which may fade.
17. **A punchline bump?** `bump`, on the layer below.
18. **A micro-motion, or a beat a sound already carries?** Silent (`data-sfx="none"` on the element).
19. **An exit, a push-in, a cut back to the face, a caption?** Silent (the documented nulls).

**Then the level.** Start from § 3. A repeat drops (`pop-cascade`, `pop-run`, `payoff-run`). A sound that must cut
through a busy beat gets +3 dB and the next track, as a row `level_db` (you raised one answer tap this way).

**Then the frame.** Put the attack 0 to 2 f after the event (law 5); § 3's lead is the file's pre-roll that does it:
- bells 4 f early
- the cut-in, travel, snap and the shutters 2 f early
- pops, simple whooshes, bubbles, metal pops, taps, clicks, key ticks, the UI chimes, blips, the buzz and the beds
  on their anchor: an entrance's first frame, a pop's element start, a metal pop's landing, a tap's release, a
  badge's frame, the bed's cut
- the Impact and the strike 2 f late: the Impact on the settle, the strike on the first stroke the render shows
- a ring where the speech says it rings; typing from its first letter; the money ching on the word

## 5. Density per passage

Counted as every clip on the timeline inside the passage, per second of it: each slice of a run and each bed
included, because that is how busy the passage sounds. This is not the house cap's count (at most 3 different sounds
in a rolling second, a run once, beds out), which is a ceiling on clutter; counted the cap's way every band below
sits lower.

- **The animated hook:** about 2 per second, every beat sounded from frame 0 (about 1.1 counted the cap's way). It
  shares the top of the range with the busiest enactments.
- **A cold open that IS proof** (another voice speaking from the first frames): not the hook band. It is a call
  overlay (law 3).
- **Enactments** (an authored scene acting the line): 1.3 to 2.3 per second; the lower end where a bed or a long
  hold carries part of the scene.
- **Screen recordings:** 0.4 to 1.3 per second; a montage (a shutter per cut) at the top, a single typed prompt or a
  card landing in its board at the bottom.
- **Call overlays under another voice:** 0.1 to 0.4 per second (law 3).
- **Outside graphics:** 0.

Calibration, never a quota: the benchmark finished at about 0.86 clips per second overall and about 1.0 inside the
graphics (about 0.72 and 0.83 counted the cap's way; the long-form reference ran 1.25 events a second inside its
graphics). Read the planner's cut sheet against these bands: a passage far above its band usually means two sources
doubled on one beat (law 11); far below means a kit component or a capture did not emit its events, or a
face-to-graphic cut-in is missing (§ 2).

## 6. Once you have touched the sound

Your timeline is the truth from the first clip you move. The house revision procedure still runs
([house § The map, Graphics revisions](../../youtube/default/sfx.md#the-map)); on this format these hold on top:

- **Run the lane's diff first** ([`LANES.md`](../../../LANES.md) § step 6). Every difference (moved, removed,
  re-levelled, re-sliced, added) is your edit and your taste; fold the PATTERN, not the instance, into § 1, § 3 and
  sfx.json. Your late additions often sit on `layer2` with `primary` free: that is how you keep the structure track
  readable, not drift.
- **Snapshot every audio clip before and after any timeline write, and require IDENTICAL:** every track, with start,
  end, in-point, file, level and transitions. A write that should not touch audio (a graphic re-lay, a caption
  swap, a grade extent) proves it did not.
- **Never re-apply the plan, and never restore a cue.** A cue that differs from the plan is yours; `--apply` or a
  `--remove-extra` over your pass erases the strongest taste evidence there is.
- **When a graphic moves, report and let you move it.** Measure the new event frames on the placed render with
  [`workflows/change-events.py`](../../../workflows/change-events.py), then report each of your sounds on it: the
  sound, its old time, the new event time and the MEASURED offset. An estimated offset was wrong once by nearly half
  a second.
- **Propagate your design to another cut by copying your clips raw:** same files, start, end and in-point to the tick,
  your levels, your one fade (the lane's adopt-and-copy recipe: [`LANES.md`](../../../LANES.md) § step 6). Only the variant's own
  ending gets new sounds, in your grammar (the click CTA in § 2). A variant cloned before your pass and left alone
  would have shipped stale sounds.

## 7. Library hygiene

- **A sound used on a job becomes a library file plus an sfx.json entry before it is reused.** The phone ring lived
  only in one job's folder, "import all SFX" missed it, and you had to ask where it went (2026-09-23). It is
  now `assets/sfx/Phone Dial Ring.wav`: dialing first, the ring burst from 4.588 s, which is where the `ring` slice
  starts. Once its entry says what it is and when it plays, a new sound ships in the client package with the rest of
  the library, no clearance asked (2026-09-24; [`assets/sfx/README.md`](../../../assets/sfx/README.md)).
- **A slice pulled from a compilation maps to its split file.** `Mac & Computer Sound Effects.mp3` is split into
  `Mac SFX NN.wav` and `Error Buzz.wav` beside it (`Mac SFX.index.json` names each piece's source span). The split
  file carries the same samples at the same level, so the clip level transfers; its lead does not, because the
  compilation slice carried its own pre-roll: re-derive the lead from the attack (law 5).
- **Before your hand pass, every library sound is one drag away:** the whole `assets/sfx/` library in the project,
  sorted into category bins, nothing on the timeline changed ("import all the SFX", 2026-09-19). A swap then
  costs you a drag, not a download. The mechanics are the lane's ([`LANES.md`](../../../LANES.md) § step 6).
- **A cue you laid from a job's own `audio/sfx-src/` is named by the lane's readback and left where it is:** its
  answer is the first bullet, never a failed gate and never a sweep's target
  ([house § Definition of done](../../youtube/default/sfx.md#definition-of-done)).
