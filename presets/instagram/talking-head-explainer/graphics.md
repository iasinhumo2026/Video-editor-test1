<!-- ⚠️  BRAND VALUES BELOW ARE PLACEHOLDERS — replace with your own.
     Fill in brand-kit.md and tell Claude "apply my brand kit", or edit the values here directly. -->

# Graphics: what the panel shows and how

This doc owns what goes in the graphic panel of a talking-head explainer and how it looks and moves: the two laws, real
vs authored, which graphic a line gets, the hook and the CTA, the four families and their finish, the house backdrop,
colour, type, UI primitives, motion and its hygiene, how the kit builds it, and the density it lands at.

Neighbours own the rest, and nothing here restates them: the frame, the bands, the layout rotation and where a switch
lands are [`layout.md`](layout.md); real-screen proof (taking, framing and filling a capture) is
[`captures.md`](captures.md); the caption layer is [`captions-style.md`](captions-style.md); sound is
[`sfx.md`](sfx.md); the story the graphics serve is [`story-and-cut.md`](story-and-cut.md); the definition of done and how
to work with the creator are the [`README.md`](README.md). The kit ([`kit/engine.py`](kit/engine.py),
[`kit/components.py`](kit/components.py)) mirrors the § Values block at the end: a number changes there first, then in the
kit, never in a comp.

**Every section opens with its WHY.** A rejected line names the anti-pattern that earned the rule. An "e.g." is an
illustration of a principle, never a spec to copy onto another video. Markers: **[CREATOR]** the creator's own instruction,
correction or hand edit · **[ADOPTED]** shipped through the creator's review rounds and approved ("Yo, that's fire... I
think the organic one is done", 2026-09-23) · **[CLAUDE]** found and fixed in Claude's own review loop, never a choice
the creator reviewed ·
**[DERIVED]** the laws applied to a kind of line the benchmark never had: unproven, so its first use is named in the
report as a new device (§ 15).

**Units.** An authored scene is laid out on a 1080x960 panel that the kit fits into the safe band (y≈202-960) at 0.79
about the seam centre. Type and UI sizes below are **panel px** (what a comp types); on the 1080x1920 deliverable they
read at 0.79x (the 126 px hero name reads about 100 px). The hero icon is quoted in **frame px**. Capture geometry is
[`captures.md`](captures.md)'s; the bands are [`layout.md`](layout.md)'s.

---

## 1. The two laws [CREATOR]

WHY: the caption already says every word. A graphic that says it again is the same information twice, splits the eye,
and loses to the caption; a graphic that SHOWS the thing adds what the audio cannot: what it looks like, and that it
works. Your correction of the first pass (2026-09-21): it was "telling, not showing... we usually want to go more with a
visual to illustrate the word rather than just putting up the word as a graphic."

- **Enact, never tell.** A graphic builds the thing its line is about and makes it DO what you say, on the word you say
  it: UI, objects, state changes. Type inside a graphic is at most a label on an object (a status line, a tile caption,
  an app's own copy). Big type is rationed to CONCEPT LOCKUPS (§ 5): the hook's, and the two-or-three-word name of the
  thing the video sells or teaches (its niche, its offer, its category), each landing with ONE object that performs it.
  A lockup names; it never carries a sentence, a list or a clause the caption is saying anyway. [CREATOR, 2026-10-15: you
  asked for three in one 97 s short, each by name: "AI WORKFLOWS" with the major AI apps' icons popping up from under it,
  "DFY AI AUTOMATION" with a gear behind it, "HIGH-TICKET OFFER" over a stove cooking the doc. A cold open has none.]
- **Nothing restates the caption.** No word cards, no adjective stacks, no "FREE" or "COMMENT X" cards, no name chips, no
  headline over a scene. Text that names UI (an agent's name in an app header) is the UI, not a restatement. A concept
  lockup is the one titled exception, and only because its object does the work: type alone is still a word card.

Rejected: stamped keyword cards and a three-adjective stack over an ease claim; a text list of errands; a "FREE" card and a
"comment KEYWORD" card at the CTA; a name chip pinned on a capture; a headline chip in the hook that "competes for
attention with the caption text... should have never been there" (2026-09-22).

## 2. Real vs authored [CREATOR]

WHY: this format sells a real, working system. The real app on screen is proof; an illustration can only explain. You
asked for it from the start (2026-09-20: "very screen recording heavy... show exactly what I'm talking about"), and the
repo rule is the same idea: document, don't manufacture.

- **Capture the real thing for anything the product does** ([`captures.md`](captures.md)): a chat with an agent, a board
  updating, a site, a dashboard, a page the viewer will visit.
- **Author an enactment only for what has no screen:** a phone call, a metaphor, a feeling, an ease claim, a pain.
- **An authored scene never invents specifics that read as evidence:** no business names, times, figures or amounts. It
  illustrates; it does not testify. A rebuild in a real product's own skin (your prompt in the AI's composer, your
  payments as the platform's notifications) is allowed because it shows only HIS words and the amounts HE says; the cell
  names it as authored, and it never shows an amount, a name or a date you did not say. A figure spoken on camera may label an object (§ 3.6): it is your claim in your words, and the
  caption says it anyway. Only an invented one is banned.
- **No stock or lifestyle b-roll, no actor cutaways, no glitch transitions,** even when a reference reel the creator
  points at uses them. Every non-face picture is either your real screen or an enactment of the line. [CLAUDE]
- **No B-roll in this preset, the creator's own included.** A cutaway here is a layout F row (layout.md § 2, the F cap)
  or a panel graphic, planned through the layout map by hand; `workflows/broll-place.py` refuses this preset. [CLAUDE]
- **The depiction matches the literal verb.** "He CALLS me every morning" over a text thread is a defect: add the call
  card. Read what is on screen against the exact words under it. [CLAUDE, the fix survived your review]
- **The plan says when an element is an illustration rather than a capture** (e.g. a call waveform built from the real
  voice's envelope), in the cell's own words, so a reviewer never mistakes it for a recording.

## 3. Picking the graphic for a line (per clause, first match wins)

WHY: the graphic is chosen by what the LINE does, never by what is easy to build. Each device below is the generalised
answer that survived your review on a line of that kind, or ([DERIVED]) the same laws applied to a kind of line the
benchmark never had; the specifics are illustrations.

- **Match per CLAUSE, not per sentence.** One sentence often does several jobs. A sentence that introduces a company and
  then explains it by analogy gets the brand page on the name, then the metaphor's object on the analogy, then the
  literal payoff on its words, each turning over on its clause's first word with the caption breaking on the same frame
  (§ 13). A clause too short to hold a device of its own (under about 1 s) rides its neighbour's graphic instead of
  flashing one. **One cell per thing:** a passage that moves through several things (your prompt, the agent at work, the
  site it built) is that many cells, each its own render, cut on its phrase start, never one long cell with the others
  folded inside it (2026-10-15: "I don't know why G10 includes three other graphics. We should probably separate
  those out").
- **The hook's line and the CTA's lines are taken by role first:** § 5 and § 6. Every other clause takes the first entry
  below that matches, and the fallback at the end when none does.
- **A device is built once per passage.** A later clause that would repeat it (the same badges landing on the same
  characters) extends the earlier graphic or takes the face. The one repeat that earns its place is a callback (§ 4).
  [CLAUDE: a blind first pass landed the same call-and-text badges twice within 8 s]

1. **The product doing a thing** → a real capture of exactly that, whole and readable, playing with its own motion, the
   event on the word ([`captures.md`](captures.md)). Two kinds of line that look like something else are this entry:
   - **The definition of the video's own product** ("X is basically a Y that you can Z") → the real product doing Z,
     each part landing on its word (e.g. a multi-agent thread where each agent's intro lands on "team", "agents",
     "text"). The analogy word does not make it a metaphor (entry 7): the line describes the product itself, and the
     product has a screen. The brand page (entry 12) never applies here. [ADOPTED]
   - **Introducing the product's agents or objects** ("here's my crew", "my lead bot does X", "his name is Y") → the
     real app showing them. A list or sidebar is a still with a slow push; each agent is its own chat with the app's
     header pinned, opening with your prompt being typed (never an empty chat, [`captures.md`](captures.md) § 6); a
     private artifact the demo needs becomes a same-shape placeholder inside the real app
     ([`captures.md`](captures.md) § 11). No name chip, and no redrawn avatar where the real app exists (§ 10). [ADOPTED]
   - **Your own artifact named** ("I put together this offer sheet", "my website", "the payment link") → HIS real one,
     captured: a document as a slow scroll, a site with its own load, a checkout or payment link as the real page or the
     platform's own phone preview of it ([`captures.md`](captures.md) § 2 and § 3). Never a random example of the kind
     (§ 2, [`captures.md`](captures.md) § 1). [CREATOR, 2026-10-15]
   - **An AI agent doing work in your browser or apps** ("have Claude take control of your browser and go set it up") →
     the real agent recorded doing it, with its own in-control chrome (the glow, its cursor), as ONE continuous shot
     ([`captures.md`](captures.md) § 5). [CREATOR, 2026-10-15: "the actual Claude cursor taking over"]
   - **Your prompt to an AI product** ("plug it into Claude") → the product's composer rebuilt as an authored scene in
     the product's OWN skin (§ 8: its page colour as the field, its fonts, palette and real mark), the prompt typing
     across your words, laid out for the panel (broken onto two lines, centred), an attached file landing as the app's
     own chip on its noun, sent on the verb. A capture of a composer frames badly in the 9:16 panel, and a prompt is
     rebuilt anyway ([`captures.md`](captures.md) § 1, the house gate). [CREATOR, 2026-10-15: "create our own graphic that
     sort of mimics what the Claude input box looks like... so it fits really nicely"]
   - **Full height (F) is for a capture that is tall and IS the story:** the concept shown working (the definition line
     above) and the escalation payoff (the system working on its own, e.g. several agents delegating in one thread).
     Those two jobs only, rationed by [`layout.md`](layout.md) § 2 F; everything else stays in the split. [ADOPTED: the
     approved cut ran exactly these two]
2. **Ongoing background work** ("he's constantly checking X, Y, doing Z") → the montage of the real screens that work
   watches, one shot per named item in spoken order ([`captures.md`](captures.md) § 7, read vs feel), then cut back for
   the line that names the concrete output. When that line names no artifact ("so that I can keep improving the
   product"), the return is the chat, with the product's real reply landing on the payoff word. [CREATOR, 2026-09-22:
   asked for it, then "the same exact concept" for a second agent; the return ADOPTED]
3. **A line about what came back** → the reply-only reveal: only the reply, one fixed framing, the real message sliding
   up into an empty chat ([`captures.md`](captures.md) § 6). Never replay your prompt first and zoom out to fit.
   [CREATOR, 2026-09-22: "you shouldn't try to fit in my message first... I don't like how it pops in"]
4. **A call** (someone calls you, you are on a call, a line describes a call) → the call card (`components.call_card`), an
   OS-style incoming-call card: avatar, name, a mono status line, decline/accept discs. How it plays follows the words:
   - **A live call on camera** (the phone rings in your hand): over the wide face ([`layout.md`](layout.md) places it
     above your head); it rings, and accept is pressed on the cut where the other voice starts; then a live timer and a
     waveform built from the REAL audio envelope of the other voice, resting flat while you talk.
   - **A described call** ("he calls me every morning and gives me a brief"): dropped over the chat if a chat is up; it
     rings on the call verb, is accepted on the next verb, then goes live under the rest of the line. An envelope reused
     from a real call is an illustration: the plan says so (§ 2).
   - **A call already in progress** opens live: no ring, no accept.
   - **A call that is the result of an ease beat** (one tap, and the phone rings: entry 9) rises with its ring pulses
     and stays unanswered: no ring sound, no accept ([`sfx.md`](sfx.md) § 4, rule 8). It is the only card that does.
   - A call that is MISSED as part of a pain is entry 13, not this one.
   - **A call that was recorded** (a sales call you ran, a meeting: "you get on the call, you pitch them") → your real
     recording is the proof (entry 1's logic, not the card): the clip at the moment the line describes, the whole call
     frame kept, on the call app's own black, the other party anonymized ([`captures.md`](captures.md) § 11), its audio
     dropped under your voice. The call card is for a call with no recording. [CREATOR, 2026-10-15]

   Reused wherever the agent calls, so it becomes a motif. WHY: the footage is the proof (the phone is in your hand), the card
   adds the UI without taking your face away, a call that is described plays out because the verb is "calls", and a real
   envelope reads as someone speaking where canned bars read fake. [ADOPTED]
5. **A list of errands or items** → one object per item, landing on its word; if the items are actions, each resolves
   (e.g. a row lands "calling" with ring pulses and flips to a green BOOKED check). A set-up object (e.g. the agent placing
   an outgoing call, with the items popping around it on dotted call lines) exits in place as the first row lands. A
   trailing "et cetera" or "and more" adds no element and no sound: the resolved list holds to the cut. [ADOPTED]
6. **A single claim or stat** → an object that PERFORMS it, with the figure as a label on the object, never the figure
   alone: a duration is a timer that runs to it; a count is a counter ticking up or a stack filling; a price or fee is a
   row landing on an invoice or a tag flipping; a rate is a gauge or bar moving to its mark; a claim without a number
   is the object doing what is claimed. It lands whole early in its sentence and holds 2-3 s so it can be read. A
   spoken figure may label it; the object carries nothing else that reads as a record (no client name, number or
   date, § 2). A real result with a source (a dashboard, a count in the product) is entry 1: capture the source, the
   figure whole. **The cut never moves for a hold:** when the next cut (a V1 cut, the CTA's hand-off) leaves less than
   the readable hold, the object lands sooner (on the clause's first noun, with fewer beats); if it still cannot hold
   about 2 s, it is a beat rather than a read, and the caption carries the figure. [DERIVED from § 1 and entry 5; the
   hold ADOPTED]
   - **Money arriving** ("you get your first client", "rinse and repeat", payments coming in) → the payment platform's
     own notification on a phone lock screen: its real app icon, its notification copy shape, the amounts you say. The
     first lands on its word; repeats come rapid-fire as one gesture (about 6 frames apart), clear glass cards
     (§ 12) set well below the lock screen's clock, each landing on a cha-ching that the next one cuts off and the last
     rings out ([`sfx.md`](sfx.md) rung 14). [CREATOR, 2026-10-15: "liquid glass... instead of just being white", "too
     close to the time", "a lot quicker, one after the other"]
7. **A metaphor** ("X is like a phone carrier for agents") → build the metaphor's own object and let it act (e.g. a SIM
   slides in and docks, the signal bars light one by one), then the literal payoff on its words (e.g. a call badge and a
   text badge pop onto each agent). A brand named only AS the metaphor gets no mark and no colour: the object is generic,
   and may carry the real subject's mark instead (the partner's icon on the SIM). A verb metaphor ("cook up an offer")
   acts the verb on the real subject: e.g. a lit stove with the real Google Docs mark dropping into its pan on "cook",
   steam coming off it, the concept's name in hero type above (§ 5's concept lockup). [ADOPTED; the stove CREATOR,
   2026-10-15]
8. **A pain built on escalating adjectives** ("technical, complicated, overwhelming") → ONE scene that gets worse on each
   word: calm, then a flood, a stack, a swarm, the stage shaking, a red wash; it dissolves before the caption band, and
   the red wash (the verdict) arrives after the last element. The spill may run off the panel's SIDES; it never reaches
   the caption. A pain made of chores rather than adjectives is entry 13. [ADOPTED; the band rule CLAUDE]
9. **An ease claim** ("the easiest, simplest, best way") → the smallest possible interaction, one beat per word: e.g. one
   message rises, its send is pressed and it turns SENT (a completion), then the phone rings (entry 4's unanswered card).
   Draw the press on the device the scene depicts (a desktop send is clicked, a phone button is tapped), because the
   sound follows the drawn device ([`sfx.md`](sfx.md) § 1, law 1). [ADOPTED]
10. **A negation of an earlier pain** ("no code") → call back that scene and undo it (every line struck through, the
    window collapsing), leaving one simple object big and centred as one composed row. [ADOPTED]
11. **A combination "X + Y"** → the two real icons slide in from their own sides on their names, the plus snaps in (a
    glyph, so [`sfx.md`](sfx.md) sounds it as a snap, never a pop), and they lock together (a squeeze, the plus absorbed,
    one ring): bare, equal-sized. [CREATOR on the icons; the move ADOPTED]
12. **A partner or company introduced by name** ("I paired that up with X") → its site hero with the official lockup big
    above it ([`captures.md`](captures.md) § 8; the lockup is `components.brand_lockup`). Never the hook's subject, which
    the lockup already showed, and never the video's own product's definition line (entry 1). [CREATOR]
13. **A pain made of chores or missed moments** ("you miss calls, you're never at the desk, you're booking appointments
    when you could be working") → ONE scene of the pain's own world that turns over per chore, each landing on its word
    and piling onto the last (e.g. missed-call badges counting up, a phone ringing to nobody, an appointment book staying
    empty). It builds like entry 8: every pain ends on its verdict, the danger wash (§ 10) after the last chore, so the
    solution that follows has something to undo (§ 4), and it dissolves before the caption band. [DERIVED from entry 8]
14. **Who it is for** ("if you run a local shop...", "if you're an agency, you could sell this") → the audience's own
    object (their shop, their phone, their client list), then the product arriving into it and doing its job there on
    the payoff words (the call answered, the booking landing, the build delivered to three shops). A pricing clause
    after it takes entry 6's object with your spoken figures; an audience line that is itself a pain is entry 13, and the
    product's arrival then undoes it (entry 10's logic). [DERIVED]
15. **How it works** ("it picks up, checks the calendar, books the slot, texts the confirmation") → the real system doing
    it wherever it has a screen (entry 1: e.g. the workflow canvas lighting node by node, one per verb); authored only
    when nothing has a screen: ONE object passing through stages, each stage lighting on its verb and the output landing
    at the end. Never a numbered diagram of labels. [DERIVED]
16. **Steps or instructions** ("copy this, paste it here, hit deploy") → the real UI performing each step on its word
    (the copy, the paste, the click), one beat or one shot per step on its phrase start; steps the viewer will take are
    shown from the viewer's side (§ 6). A step your customer takes on your page ("they book in") is your real page with
    the cursor travelling to the button and clicking on the verb (2026-10-15). Never a numbered text list.
    [DERIVED; the cursor on the verb CREATOR]
17. **A comparison or before/after** ("instead of X, now Y", "most people do X, I do Y") → two states of ONE object, the
    change landing on the pivot word (the pile clears, the red rows flip green, the ringing phone is answered); never two
    text columns or a versus card. When the "before" was already on screen, call it back and change it (§ 4). [DERIVED
    from entry 10]
18. **A quote, post, headline or article** → rebuilt verbatim from its written source in the shape it lives in (a post
    card with its author row, a headline in its page's masthead), the passage read on camera marked on its words; never a
    free-floating quote in big type. Where the point is that a real outlet published it, the real page is captured as
    evidence, flat and whole ([`captures.md`](captures.md) § 1 holds the house gate on captured text). [DERIVED]
19. **A prediction** ("soon every shop will have one") → the claim's own object in its predicted state, built on the
    words (e.g. a street of shop icons each gaining the product's badge, one per beat). Nothing styled as data: no
    invented chart, percentage or date, because a forecast is not evidence (§ 2). [DERIVED]
20. **The name of the thing the video sells or teaches** ("is done-for-you AI automation", "from selling AI
    workflows"), when it has no screen of its own to show → it may take a concept lockup (§ 5): the name in hero type,
    rising as one block on the cut, and ONE object that performs it popping in on the concept's word and acting to the
    end (a gear that turns; the category's real app icons popping up left to right under the name). Rarely more than two
    beyond the hook's in a video; each is named in the plan summary as a concept lockup, so you can strike it. [CREATOR,
    2026-10-15: each asked for by name]
21. **Connective tissue** ("So guys", "for the everyday person") → no graphic: a wide breather or a punch-in
    ([`layout.md`](layout.md)).

**No entry matches** → the object of the clause's nearest concrete noun (real if it has a screen, authored if not) doing
what the verb says; a clause with no concrete noun takes a face beat (T or W, [`layout.md`](layout.md) § 3). Never a word
card (§ 1). Name the device in the report as new (§ 15).

Rejected: a capability-list hub (the product icon with a solid tile popping out per named word, a burst on "anything") was
built once and its line was cut before you reviewed it. It is unproven: never default to it.

## 4. Story in reel order [ADOPTED]

WHY: a graphic that is right on its own line can still be wrong in the reel: it can spoil a later payoff, open on an
exchange the viewer has no context for, or put the wrong agent's words under a line naming another. Read the graphics
the way the viewer meets them.

- **Read every scene in order for what the viewer learns** from it, before the build and again on the draft.
- **No scene opens mid-exchange or shows a later payoff early.** A chat scene opens on the exchange the line is about
  ([`captures.md`](captures.md) § 6). [CLAUDE]
- **Build callbacks.** The problem visual returns as the solution (the pain scene is undone by the negation line, § 3.10);
  the item an agent pitched is the one that lands on the board; the call card returns wherever a call does.
- **The strongest set piece may return, escalated, as the re-hook payoff** (e.g. the one-agent chat returns as the whole
  crew delegating full screen).

## 5. The hook lockup [CREATOR]

WHY: the hook is the first place the reference style uses big type, and its lockup sets the grammar every later concept
lockup follows (below), so it has to name the subject and perform the premise at once without fighting the caption for
the eye. It was rebuilt twice (2026-09-21, 2026-09-22) to reach this. Built by `components.hook_stack`.

- **One centred vertical stack in the split content zone:**
  1. the subject's real icon, bare, about 236 px on the frame, a little above the zone's centre;
  2. its NAME in hero type (§ 11), rising (§ 13);
  3. ONE object that literally performs the hook claim, each part landing on its spoken word (e.g. a masked value filling
     dot by dot, then signal bars lighting, then a badge landing on the payoff word: `components.masked_value` is the
     stock object for a value; a different premise builds its own).
- **A two-clause hook** ("I gave it X and turned it into Y"): the object performs the CONCRETE clause, the one with a
  showable object (e.g. "its own phone number" → the number being assigned); the payoff badge lands on the first word of
  the result clause's noun phrase (e.g. "the ULTIMATE personal assistant"); the second clause gets no second object.
  WHY: one object is what the zone holds without crowding the caption, and the result is felt as the badge landing, not
  read. The exception is a hook that cuts once inside its sentence (the proof hook below): each clause then has its own
  cell. [ADOPTED; the wording is the generalisation]
- **Nothing restates the caption.** No chip, no subtitle, no premise sentence.
- **The caption stays on the seam: lift or shrink the visual instead** ([`captions-style.md`](captions-style.md) § 2, 2026-09-22).
- **Every element sits inside its container, measured, not assumed.** (2026-09-21, on the icon row hanging
  outside its pill:
  "Is that an error, or did you mean to do that?")
- **Anything real inside the object is masked in the right grouping** (e.g. a phone number as `+• (•••) •••-••••`: one
  dot after the plus reads as a country code, two did not). Never digits: nothing on screen can be dialled.
- **The first element is visible on frame 0.** The hook has no empty plate.

Rejected: a title card over the hook (type with no object: a concept lockup carries its performing object); a stamped
text chip ("competes for attention with the caption text... should have
never been there"); the caption parked under a title instead of the visual lifting; an icon row overflowing its pill.

### The proof hook: a real result, then the vehicle [CREATOR]

WHY: when the hook's first clause states a result that has a screen ("I've made over $375,000 online"), the real screen
IS the strongest possible first second: a number on your own dashboard is proof, a lockup of it is a claim. You asked for
exactly this on 2026-10-14 ("an aesthetic little highlighted intro from my Monarch account... show the whole page and
then zoom in to the number") and tuned it over four notes.
- **Frame 0 is the real page, whole and filling the panel** ([`captures.md`](captures.md) § 4), already moving: the
  zoom onto the figure starts within the first frames ([`captures.md`](captures.md) § 5 owns the zoom), and the figure
  is marked (a highlighter stroke) as you say it ("it should be highlighting 375 pretty much when I say it"), with the
  cha-ching starting on the mark ([`sfx.md`](sfx.md) rung 14).
- **The vehicle clause may get the lockup, on its own cut** ("from selling AI workflows"): the clause's name in hero type
  rising as one block, and its object performing it. For a CATEGORY the object is a row of the category's leading real
  marks (the major AI apps' App Store icons), popping up from under the name left to right, a few frames apart. The
  caption breaks on that cut.
- Everything else in § 5 holds: nothing restates the caption, the caption keeps the seam, every element inside its
  container. A hook with no screenable result keeps the product lockup above.

### Concept lockups after the hook [CREATOR]

WHY: a how-to short turns on one or two names (the niche, the offer, the category it sells into). Said once in passing,
a name is gone; landing it as a title with an object that acts it gives the viewer the one thing to remember, and the
object keeps it from being a word card. You asked for each one by name on 2026-10-15 (three in 97 s) and approved them.
- **Only for a NAME the video turns on,** two or three words, on the line that names it. Never a sentence, a claim, a
  list or a feeling: those take § 3's devices. Rare: a few per video, each on a different name (the 97 s short carried
  three), and never in place of a real screen the line could show.
- **The name in hero type (§ 11), centred, rising as one block on the cut** (§ 13), broken onto two lines when it
  needs them ("DFY AI" over "AUTOMATION"), sized by its longest word.
- **ONE object that performs it, landing on the concept's own word and acting until the cut:** a solid gear popping in
  behind the block's corner and turning (automation), the category's real marks popping up in a row under the name
  (AI workflows), a stove cooking the real subject's mark under the name (cooking up an offer: § 3.7). Real marks are the
  real files (§ 12).
- **It sounds as its entrance and its object:** opening from the face, the layout's cut-in is the rise's sound (the
  block rises silently under it); cutting in from another graphic, the rise takes its snip; the object takes its pop
  ([`sfx.md`](sfx.md) law 4 and rung 12). A bed for an object that keeps working (a faint sizzle under the stove) only
  where you have asked for one.

### Cold open on live proof [DERIVED]

WHY: when the video opens inside the proof (a call already running, a demo mid-flight), the proof IS the hook. It says
what the video is and that it is real in the first second, which is the whole job of the lockup, and a title lockup
added later would be a title card in the middle of the video. The frame is [`layout.md`](layout.md)'s (O, § 2); this is
the graphics half.

- **Frame 0 is O with the call card already live** (§ 3.4, "already in progress"), visible on frame 0 over the wide
  shot, recorded as the `L-OPEN` deviation ([`layout.md`](layout.md) § 12; without it, § 6 makes frame 0 S).
- **No lockup.** The big type stays unspent. The subject is named where you name it, with that clause's § 3 device (a
  partner's brand page, the combination "X + Y", the stat object for "it took 30 minutes").
- **The first voice may be the other speaker's.** The waveform rests flat until the other voice's first word and moves on it; the
  caption runs from the first word, whoever says it, in that voice's colour ([`captions-style.md`](captions-style.md)).
  The call's greeting is kept from its real start ([`story-and-cut.md`](story-and-cut.md) § 4.11), so that first word may
  land later than a talking hook's 0.1 s; the live card on frame 0 is what keeps the panel from being an empty plate.

## 6. The CTA enactments [CREATOR]

WHY: the CTA exists so the viewer recognises exactly what they are getting and sees themselves doing the action. A named
action is a word card; a performed one is recognised instantly because everyone knows the UI. Anything added beyond your
words is a promise you never made. Three rounds of corrections on 2026-09-23 set this.

- **Show only what you say, in your order.** Each promise gets the REAL thing on its noun ([`captures.md`](captures.md)
  § 9, CTA captures): flat, static, whole.
- **The lead-in before the first named promise** ("if you want this whole build for free, copy and paste, I built...")
  shows the deliverable in general, the whole build (e.g. the real system or workflow running, captured), with shot
  cuts on its phrase starts, until the first promise's noun. One page held over a long lead-in goes stale
  ([`layout.md`](layout.md) § 13, L-STALE). [DERIVED]
- **Picture cuts fall on phrase boundaries, with the caption breaks on the same frames** (the cell's `shot_cuts`), so
  each promise's shot and its words are one unit. Promises named closer together than a readable hold (a page "with a
  full walkthrough video") share ONE shot that contains both (the page with its embedded video), never two
  half-second shots. [DERIVED]
- **A comment ask becomes a platform DM thread seen from the VIEWER's side** (`components.thread_cta`):
  - the platform is the one the brief names first, else Instagram, recorded in RUN.md: the thread depicts where the
    viewer will actually comment (a platform the kit does not carry passes its own sent colours as `platform`);
  - a composer low in the zone that never moves, landing on "comment" ("I like how the message box stays where it is and
    the text comes above it");
  - your spoken keyword typed letter by letter across the spoken word;
  - the send on the next beat;
  - the viewer's bubble and the send button in the platform's sent colour (§ 10: "I meant my message");
  - typing dots;
  - your grey reply on the left, carrying the promised thing as an object, a folder attachment with a title and a one-line
    subtitle ("do something visual to show an actual workflow, or maybe a folder"). The reply hands over your promise in
    your own nouns (you say "I'll send you the full workflow"; the reply delivers "the full workflow"); its sentence and
    the attachment's title and subtitle are the editor's copy, flagged to you;
  - earlier bubbles scroll up as each new one arrives;
  - the finished thread centred in the zone, with clear air above the caption ([`layout.md`](layout.md) § 8).
- **A click ask (the ad) becomes `components.click_cta`:** the push in from the last graphic ([`layout.md`](layout.md)
  keeps it split); the brand lockup from its real files (`components.brand_lockup`); a button in HIS words; a cursor that
  taps it on "link" (it turns green); a down arrow that drops on "below" and bobs to the last frame.
- **A promise with no page becomes the attachment object.** An ask with no fitting UI becomes a button carrying your
  exact words, never a slogan you did not say.
- **Never word cards, drawn stand-ins or emoji.** A drawn template tile or a video tile with a progress bar is invented;
  the real page replaced it.
- **The CTA's first graphic starts on the previous graphic's last frame, and its last graphic never exits** (how each
  arrives, split unbroken: [`layout.md`](layout.md) § 7). The final frame is what a paused or looping viewer sees, so
  the ask is still on it. (2026-09-22, on the first short's ad card: "get rid of the rise out animation, just
  leave the last one with no out animation.")

Rejected: a comment bar with two icons; a thread that sat off-centre with a blue sent bubble; the gradient on HIS reply
instead of the viewer's message; the deliverable as a text-only bubble; a card with an emoji and the brand word in a
colour (the first short); a content graphic hanging into the ask.

## 7. Families and finish [CREATOR]

WHY: stepped motion plus bloom reads as designed; smooth motion plus scan lines reads as a real screen. Keeping the two
textures apart tells the viewer at a glance which is an illustration and which is the real thing. Your split
(2026-09-21): the grid motion graphics get "our glow and our 12 FPS", screen recordings "a very subtle glow plus the scan
lines effect, so it looks kind of like a real computer screen... Both of them should be very, very subtle, but barely
noticeable."

**Sort every graphic into a family BEFORE building it:** `authored`, `capture`, `montage` or `overlay`. The cell's `family`
records the choice ([`layout.md`](layout.md) § 12 holds the plan contract), and the kit renders from it (the `FLAGS_*`
values; a capture whose fill is light takes `FLAGS_CAPTURE_WHITE`, picked by the kit from the fill).

| family | backdrop | rate | GLOW | SCAN | GRAIN |
|---|---|---|---|---|---|
| **authored** (an enactment, the hook, the CTA cards) | the house backdrop (§ 8) | STEP_FPS 12, held to the timeline rate | 0.26 | none | 5 |
| **capture** (the real app or page) | none: the fill is the capture's own colour as rendered ([`captures.md`](captures.md)) | timeline rate | 0.12 | 6 px sine at 10 % | none |
| **capture** on a white or light page (the cell's family stays `capture`) | as capture | timeline rate | 0.12 | as capture, SCAN_AMP 0.06 | none |
| **montage** (tilted macro b-roll of real screens) | the capture's fill inside the tilted plane | timeline rate | 0.18 | drawn in the plane at `INPLANE_SCAN` ([`captures.md`](captures.md)), period 6 / mean zoom | none |
| **authored** in a real product's skin (your prompt in its composer, its notifications) | the product's own field, sampled off a real recording of it (§ 8), no grid or seam fade | STEP_FPS 12 | 0.26 | none | 5 |
| **overlay** on live footage (the call card) | none | timeline rate, never stepped: it is synced to live audio | none by default | none | none |

The recipes (the kit's render wrapper applies them; nobody types them):
- **bloom** = split → `gblur sigma=30` → `eq brightness=0.12 contrast=1.12` → `curves 0/0 0.5/0.62 1/1` → screen on
  R, G, B at the GLOW opacity, alpha kept from the render, so the bloom never leaves the graphic and lights its type too.
- **scan** = `RGB × (1 − A·(0.5 + 0.5·cos(2πY/6)))`, alpha untouched. A = 0.10 on a dark capture, 0.06 on white, where the
  same dip reads far stronger. On a montage it is drawn IN the plane (a stripe on the capture and its fill), so it tilts
  and foreshortens with the screen (2026-09-22: "The background should be part of the 3D movement").
- **grain** = luma noise `c0s=5 c0f=t`, applied AFTER the 12 fps expansion so it is fresh on every timeline frame
  (stepped grain reads as a compression bug), in a 16-bit planar format with the alpha untouched.
- **Never MBLUR with STEP_FPS**: the stepped look does not blur. **Always render at the sequence's exact rational rate**
  (the raw's, e.g. 24000/1001); render.sh reads it from graphics-plan.json `fps` (else the first raw, else 29.97 with a
  warning), and the kit's wrapper passes the plan's rate explicitly, so a render never falls back. The bloom and scan
  numbers below are the ones render.sh runs (`workflows/test_fullscreen_render.py` holds them equal).

Rejected: smooth timeline-rate authored graphics (the first pass; you wanted 12 fps and glow); stepping a capture or
putting grain on it (captures are real screen motion and stay smooth and clean); stepping an overlay whose waveform
follows live audio (it breaks the sync); scan lines on the grid backdrop; the house backdrop, a rim, a card edge, a
shadow or a colour filter around a capture; 3D tilt or in-plane scan on anything the viewer must read (that is the
montage's alone).

## 8. The house backdrop (authored only) [CREATOR]

WHY: authored scenes and dark app captures alternate every few seconds, so they must feel like one dark world; the
content and the captures carry the colour and the backdrop stays out of their way. Your ask (2026-09-21): the background
"should just flow with the color scheme of our screen recordings more. It's basically very dark." Every one of your
passes moved it darker, dimmed the light and made the grid slightly more visible, and the final values were approved off
a bare-background preview (2026-09-22: "Yes, yes. Now that's what I want to see.").

The numbers are the `BG_*` values below.
- **Fill** `#010102`; a **grid** of 1 px lines every 90 px on both axes.
- **Centre light** (`BG_LIGHT`, a disc at (−200, −200)): "a slight, super slight, soft blue glow from the middle".
- **Drift**, on the main timeline so every copy of the panel (a header mask is a copy) moves in step: x and scale over
  5.5 s, y over 3.7 s, both `sine.inOut` yoyo. No rotation, no wobble. (A y on the 5.5 s loop never rendered: the 3.7 s
  tween on the same property overrode it, § 14.)
- **Vignette** (`BG_VIGNETTE`) and a **split seam**, 70 px at the panel's foot fading to `BG_SEAM_TO` (split layouts
  only).
- **Grain 5** from the family flags keeps a very dark field alive without competing.
- **The drift's phase continues across a push join** (the incoming comp starts its drift where the outgoing one ended),
  so the backdrop never jumps.
- **A scene that depicts a real product's own UI takes the product's field, not the grid** (2026-10-15: "the
  background should be like the Claude background, not our normal dark grid background, because it's like a Claude
  graphic"): the product's page colour sampled off a real recording of it, full bleed, no grid, light, vignette or seam
  fade; the product's own fonts, palette and mark (staged from the product, never approximated). The grid is the house
  world for ideas; a product's screen is the product's world, the same reason a capture has no backdrop
  ([`captures.md`](captures.md) § 4).
- **"Make the background darker" means the base and the centre light, never the bloom.** Your distinction (2026-09-22): the
  panel went darker with the GLOW pass untouched.

Rejected: a navy `#060d24` field with a strong royal radial (it fought the near-black captures); the `#07080c` and
`#040508` steps on the way down (each still too bright); grain 7 ("slightly too intense"); a wave warp (your own call: "I
think that would just be too much"); scan lines on the grid; the light "Spotlight" sky-grid background of the old
signature look (off-world next to dark app captures).

## 9. Barely there, judged at phone size [CREATOR]

WHY: the texture sells the look only when nobody consciously notices it, and the phone is where it is judged, not a
zoomed crop. Bloom, grain, scan lines, the backdrop light and type glow were each turned DOWN after the first pass on both
talking-head shorts: "very, very subtle, but barely noticeable"; the light "super slight"; grain 7 "slightly too
intense".

- **The final levels in § 7 and § 8 are ceilings.** A new effect starts lower than you think.
- **An effect that averages away at phone size or at the editor's Fit view is a defect, not subtlety: raise its period or
  thickness, never its opacity.** (1 px scan lines every 3 px at 9 % were invisible at Fit and on a phone; the 6 px sine
  at 10 % reads.)
- **A global change** (the backdrop, a family's finish) is previewed first, current beside proposed, and approved before
  the timeline changes ([`README.md`](README.md#working-with-the-creator) § Working with the creator).

## 10. Palette and colour roles

WHY: colour carries meaning, never decoration. In a 1.5-second beat a colour has to do work: a green check says "done"
before the word is read. Every hex below is authored; a captured UI always keeps its own colours.

- **royal `#1e48ff`**: sent, the solution, the action button (a message turning royal as it sends, the down arrow).
- **sky `#57c9f0`**: live: waveforms, pulse rings, a dotted call line, the dots filling a masked value. The sky
  waveform is approved as-is [CREATOR] (2026-09-24).
- **txt `#e8f0ff`**: authored text on the dark field; type on a UI surface is pure white `#ffffff`.
- **muted `#8fa6d4`**: meta labels ("INCOMING CALL").
- **green `#2ff58a`**: success: booked, sent, signal up. Green on every success is approved as-is [CREATOR] (2026-09-24).
- **red `#ff4d5e`**: decline, error, negation.
- **OS accept `#30d158`, decline `#ff3b30`**: call buttons, a check disc, a tapped button, exactly as the phone draws them.
- **Received bubble `#2a2b31`, attachment `#1d1e23`, typing dots `#9a9daa`**: a DM thread's neutral side.
- **Danger wash** (`DANGER_WASH`, an escalation's verdict): a red radial from the edges. Approved as-is [CREATOR]
  (2026-09-24).

**Platform colours appear only where that platform is depicted, and from the VIEWER's side:** the viewer's own message is
the one the platform brands, so the viewer sees themselves (e.g. an Instagram sent bubble and send button in `IG_SENT`;
your reply stays grey: "I meant my message", 2026-09-23). **Captured UI keeps its real colours, with no filter** (no brightness, contrast or saturation lift). **A
recurring app character** (a bot's avatar) is redrawn as a crisp vector in the app's own shapes and colours, so it
matches the captures at any size, and it appears ONLY in authored scenes of things with no screen (a call, a metaphor,
an errand list). Introducing the agent is the real app (§ 3.1): a redrawn crew where the app lists them is a stand-in
for a screen that exists. [CLAUDE] Caption colours live in [`captions-style.md`](captions-style.md).

## 11. Type

WHY: one phone-native type system makes drawn UI sit naturally beside real app captures, and mono labels echo the mono
captions, so the frame reads as one system. Big type is rationed to the concept lockups (§ 1, § 5).

- **Inter** (panel px, § Units):
  - **Black 126 px, −3 tracking, caps, line-height 1**: a concept lockup's name (the hook's, the offer's), on one or two
    lines; a longer name shrinks to fit its longest word, never past the zone's sides.
  - **Bold 52-58 px, −1 tracking**: object names (a row's title, a caller's name).
  - **Black 70 px**: button labels.
  - **Regular**: body and UI copy.
- **SF Mono Bold labels: 25-30 px, caps, tracking 2-3 px**, in muted, sky or green by role (§ 10).
- **Embedded with `@font-face`**; the kit stages the files into the job, because a system font name falls back silently
  in the headless render.
- **Where the fonts come from:** `kit/engine.py init` stages Apple's SF Pro display face when it is installed, else the bundled Inter
  (a client machine without SF Pro gets Inter with no step of its own); SF Mono is the system font on every Mac; off
  macOS the kit's labels and the caption builder both draw the bundled stand-in, IBM Plex Mono Bold (`assets/fonts/`,
  OFL), so labels and captions share one face on every OS; only without it do the labels take DejaVu Sans Mono or
  Consolas (the captions' own fallback: [`captions-style.md`](captions-style.md) § 6).
- **Re-measure the longest word before sizing** (PIL `getlength`), never trust a size that fitted a shorter word.

## 12. UI primitives and brand marks

WHY: authored objects must look like real, current UI in one dark family, so they sit on the near-black backdrop and
beside dark captures without a seam. The alternative (frosted navy template cards with a royal rim) read as template
chrome. A real brand mark is recognised instantly, and so is anything wrong with it.

- **Surface** `rgba(18,20,28,0.92-0.96)`; inset rim 2 px `rgba(255,255,255,0.09-0.12)`; shadow `0 24px 60px
  rgba(0,0,0,0.5)`. Radius: pills height/2, list rows 44 px, cards 34-68 px. An avatar disc is `#0b0c11`.
- **Icons are solid-fill Material paths, never outlines.**
- **A real brand mark is the real file, bare** (the app bundle, the brand's own files), with only a drop shadow that
  follows its alpha, `drop-shadow(0 26px 40px rgba(0,0,0,0.55))`. No tile, ring, glass border or backing (2026-09-22: "Why wouldn't it just be literally the same, just the icon as it is?"). A dark wordmark is made legible on
  the dark panel (e.g. inverted to white). A brand named only as a metaphor gets no mark and no colour (§ 3.7).
- **Size a mark by its SOLID body (alpha > 128)**, never the padded canvas or a baked shadow (`components.bare_icon` does
  it); **paired marks are equal on the render, within 2 px, measured.** (2026-09-22: "why are they not the same size... I feel like that would go
  without saying"; sizing by the canvas left one 7 % small.)
- **Terminal:** body `#0d0f14`; title bar `#1a1d25`, 64 px, lights `#ff5f57` / `#febc2e` / `#28c840`; radius 26 px; mono
  27 px on a 42 px line in `#aab3c8`, errors `#ff5d6c`, passes green, warnings `#febc2e`, the prompt white bold.
- **No `backdrop-filter`**: an alpha render has nothing behind it, so a blur-the-background panel renders transparent.
  Opacity lives in the fill.
- **Inside an authored scene, a card over a picture is clear glass, never a white slab** (a notification on a lock
  screen): a thin white-tinted pane, an inner rim highlight along its top edge, white type, the picture's colour and
  soft glows reading through it. The call card over your face keeps its dark surface (§ 3.4). With no `backdrop-filter` the glass lives in the fill and the
  rim. (2026-10-15: "a little liquid glass effect instead of just being white"; long-form's
  [`default-overlay-style.md`](../../youtube/default/default-overlay-style.md) § COLOUR VARIETY says the same of a card
  over footage.)
- **Glow is stacked blurred duplicates, never `text-shadow`**, and type glow is off by default (it is for a subject that
  emits light).
- **Fake code is generic dev noise:** no vendor or competitor names (a sponsored reel names no competitor), no key-shaped
  lines even masked, no real paths or names. Grep the comps before rendering. [CLAUDE]
- **Numbers are masked dots in the right grouping**, never digits (§ 5).

## 13. Motion [CREATOR] [ADOPTED]

WHY: motion carries meaning. A word arriving and an object appearing are different events, so they move differently;
contrast in motion should track a difference in meaning. And picture, caption and sound landing together hit the line
through three channels at once.

**Every change lands on its word:** event = frame-snap(word − 0.06 s), about 1.5 frames early, on the grid. The tolerance
is about 2 frames (the tool's default ±0.10 s), proven on the render with `uv run workflows/change-events.py --sync
projects/<job>`, never by reasoning (a 0.9 s clock error once looked right on every still). The 12 fps step quantises
an authored event by up to 83 ms: check what must land exactly (a send on its verb). A picture cut inside an authored
scene (its cell's `shot_cuts`) never quantises late: the kit's `Clock.cut` puts it on the 12 fps sample its frame shows,
so it changes with the caption break, and `graphics-qa-short.py`'s `cut` check holds every `shot_cuts` frame on the
render (2026-10-14: an offer sheet set on its grid time changed 2 frames after the break). A send lands on the verb, a
reply just after the word it answers, each list item on its own word.

The registry (a shipped variant outside its § Values band is named by role):
- **Words rise:** the house `riseIn` from [`hf-anim.js`](../../youtube/default/reference/hf-anim.js); its numbers live in
  [`animations.md`](../../youtube/default/animations.md). **Type never pops.** (2026-09-22, on the first short:
  "our default text rise in... from our YouTube default preset".) The benchmark's hook name was a hand-typed rise (40 px
  over 8 frames `power3.out`, from frame 3); `components.hook_stack` rises it through the house `riseIn` instead (about
  31 px at 126 px, 0.55 s, the same ease) by design, so every word in the preset rises one way.
- **Objects pop:** scale 0.3-0.6 → 1, `back.out(1.4-2.6)`, 7-10 frames. A badge or glyph snapping onto an object already
  on screen (a call badge, the plus between two icons) pops from nothing: scale 0 → 1 in 6-7 frames at
  `back.out(2.4-2.6)`. A fast run of peers (windows multiplying) pops from 0.4 in 5 frames.
- **Rows and cards rise with a small scale-up:** y +60-110, scale 0.90-0.94 → 1, 8 frames (a row's default: y +60 from
  0.94). The shipped extremes: a bubble sent up from a composer travels furthest and starts smallest (y +120 from 0.80,
  8 frames); a pill arriving under the hook name travels least (y +50 in 7 frames).
- **Logos slide in from their own side on their names:** x ±420, rotation ±14°, 9 frames `back.out(1.4)`.
- **Buttons press:** to 0.74-0.80 over 2-3 frames `power2.in`, then to 1.0-1.12 over 3-4 frames `back.out(2.4)`, and
  recolour. A big button presses shallower (a 740 px button to 0.94 over 2 frames, as `components.click_cta` does), and
  an OS call's accept disc overshoots on `power2.out` (0.80 → 1.12, 3 frames each way), the way the phone draws it.
- **An interrupting card drops from above:** 11 frames `power3.out`, scale 0.92 → 1, its first frame already inside the
  safe band.
- **A concept lockup's type rises as ONE block on the graphic's first frame; its object pops on the concept's word
  and keeps acting** (a gear turning to the end, icons popping up in a row). (2026-10-15: "the entire text can
  do our rise-in animation, and then the gear pops in and starts turning".) Per-word rises across a three-word name read
  as a sentence being typed, not a title landing.
- **Peers share one entrance; the payoff is the one that differs** (e.g. three rows land alike and each flips to a green
  check).
- **In-scene exits:** 5-8 frames `power2.in`. **The last graphic never exits** (§ 6).
- **A static page or brand gets no pop and no push-in: the cut is the entrance** ([`captures.md`](captures.md) § 8
  owns it, § 5 its two exceptions: a rendered zoom onto a named figure, a document's scroll).

Pace:
- **One beat per key noun or verb.** A graphic meant to be READ (a claim, a stat, a reply) holds 2-3 s once whole, so it
  can be read. **A lone element that is not being read (one avatar, one icon) holds no more than about 1-2 s**: add a
  beat per noun, or let the layout cut to the face. [CLAUDE: a lone avatar held 4 s read thin]
- **The panel turns over per named item, and the picture cut and the caption break are the same frame.** (2026-09-22: "break up the captions like 'he's constantly' and then let's cut there, move into a new graphic".)
- **A beat in the panel (a new element, a state change, a cut) about every second.**

Named devices:
- **Ring pulse:** a ring scales 0.6-1 → 1.5-1.9 and fades over 0.5-0.9 s `power2.out`; bursts of two or three rings
  repeat while the thing rings or calls.
- **A pulse on an element still entering** waits for max(its word, 2 frames after the entrance ends), so the two
  tweens never share its scale (§ 14).
- **Escalation:** the stage scales to 0.86, shakes x ±7 px / rotation ±0.5° every 0.05 s, a red wash builds over 1.2 s,
  and the logs scroll in steps (14-18 per second), never smoothly.
- **Push** (the lateral hand-off, graphic to graphic inside split, `components.push`): [`layout.md`](layout.md) § 5
  owns when it is allowed. It runs `PUSH_FRAMES` on `PUSH_EASE` (10 frames `power3.inOut`, the same number layout.md
  holds); the outgoing graphic's final state exits left as the incoming enters from the right, one screen apart on one
  ease, and the backdrop's drift continues across the join (§ 8). The kit pushes an authored scene in; a capture arrives
  on its cut.
- **Down arrow:** a 150 px royal disc drops on "below" and bobs 16 px every 0.22 s to the last frame.

## 14. Motion hygiene

WHY: every rule here shipped once as a defect: a blank or doubled frame reads as a glitch at full speed even when every
still looks fine. GSAP does not overwrite by default (last writer wins), and browsers lag a frame decoding an incoming
clip. The kit enforces each of these; a hand comp must too.

- **The first element is visible on comp frame 0.** (An empty plate once held 38 frames before its first icon.)
- **Same-slot swaps are sequenced to the exact frame:** the exit ends on the frame the incoming starts, no overlap, no gap.
  (A 2-frame overlap added once to quiet a checker was itself a flash.)
- **A cluster exits in place**, never through the incoming element's slot. (A bare panel sat 14 frames between phases.)
- **A fade whose last frame is near-empty becomes a shrink-out cut** on the landing frame.
- **Staggered elements stay hidden until their own pop.** (Turning a group on at once showed two members at full size
  for a few frames before they popped.)
- **Never two tweens on one property of one element at overlapping times.** (A pulse on a lockup snapped it back to
  full size mid-move.) A repeating ring's cycle is longer than its tween; a denser pulse uses a second ring element.
- **An incoming clip pre-rolls hidden, and the outgoing shot leaves ON the cut frame** ([`captures.md`](captures.md) § 12).
- **Every time is on the frame grid** (author in frames; a time printed a hair after its frame misses it).
- **One slot holds one graphic.**
- **No `onUpdate`-driven content:** it does not fire when the renderer seeks a paused timeline, so a counter renders frozen
  on its first value. Emit `tl.set` steps. One paused timeline, absolute times, no `Math.random`.
- **A render never overwrites a placed file:** version every re-render (overwriting a placed path half-stales the editor's
  frame index).

## 15. Building with the kit (5b)

WHY: every recurring number and hygiene rule lives in the kit once, so a job's build is data, the first pass comes out in
this look, and a re-cut is a re-run instead of a re-typing.

1. `uv run presets/instagram/talking-head-explainer/kit/engine.py init projects/<job>` stages the kit, the fonts and a
   starter `hf-graphics/gfx/build.py`.
2. **Captures first** ([`captures.md`](captures.md)): the real screens decide what the authored scenes around them need.
   Stage each take with `uv run presets/instagram/talking-head-explainer/kit/engine.py stage projects/<job> <id> <take>`:
   it keeps the original at `assets/captures/<id>.<ext>` (what `validate-plan.py` checks) and writes the all-intra render
   base the kit reads under `hf-graphics/gfx/assets/captures/` (`--name` picks its file name), records beside the base
   in `<name>.stage.json` the original it was made from, and prints the cell's `"asset"` value to paste into the plan.
   The product's brand marks (its logo, its wordmark) are staged the same way with `--mark [--name X]` into
   `hf-graphics/gfx/assets/logos/`, and a component takes one as `"assets/logos/<name>"`: they are the product's own
   files, fetched for the job, never in the repo's `assets/logos/`.
   - **Staging is idempotent, atomic and never overwrites** (2026-09-24; the contract is `engine.stage`'s docstring): a
     different file at the original, the mark or the base, or a second original for one id, is refused before anything
     is written. To replace a rejected take, move its original, base and `<name>.stage.json` aside by hand and stage
     again, or stage it under another id or `--name` (a video's ends `.mp4`, `.mov` or `.m4v`).
3. **Pilot only what is new; build the rest straight through.** A new LOOK (a backdrop, a family's finish, the type or
   the palette) is piloted on ONE scene and shown to you first ([`README.md`](README.md#working-with-the-creator)). A
   locked device (every [CREATOR] or [ADOPTED] entry, every kit component) is built without a stop, gated by the tools
   (§ 14, the kit's build asserts, `graphics-qa-short.py`). A new device (a [DERIVED] entry's first use, or one invented
   for a line § 3 does not cover) is built in the pass and named in the report as new, so your review looks at it first;
   it never holds the pass. Self-review runs on the first scene of each family before the rest of it, and graphics are
   built one at a time, each finished before the next (2026-09-21: "get each one of them perfectly correct before
   you move on to the next one").
4. **The job's `hf-graphics/gfx/build.py` is DATA:** every time comes from a word (`ctx.find`, which refuses a missing or
   ambiguous word) or a plan cell, never a typed second; every recurring piece is a component call. A storyboard word
   goes through build.py's `said()`, which searches only inside its cell (the cell's first frame to its end), so a word
   the reel repeats in a LATER line (the § 3.10 callback) never makes the cell's own word ambiguous. A miss or a double
   inside the cell still raises, and `(phrase, n)` takes the n-th hit.
4b. **Real pages and written docs have recipes** in `kit/build.example.py`'s cookbook. `page`: one shot per plan
   shot, each `(media, t0, frame, crop, fill)`, the frame a source rect, a framing, or a `(from, to)` pair for a slow
   push; each shot on its own sampled fill; crop edges inside the panel feathered; the band cleared at the source unless
   the cell carries `under_caption`; the shutter on a cut between pages, a skip inside one take at one framing silent.
   `doc_scroll`: one stitched still of the doc's own column, panned on a sine ease from one row to another at the
   content zone's top, run to the seam (its cell carries `under_caption`). Both take the shutter when they cut in over a
   graphic and ride the cut-in from the face ([`captures.md`](captures.md) § 2, § 4 and § 5).
5. `uv run projects/<job>/hf-graphics/gfx/build.py` writes the comps and the kit's SFX rows (the components carry their
   own sound events in [`sfx.md`](sfx.md)'s vocabulary).
6. `uv run projects/<job>/hf-graphics/gfx/kit/engine.py render <id>` renders each comp with its family's flags (§ 7),
   never flags typed by hand.
6b. **The sync anchors of a kit component** (L5, proven by `workflows/change-events.py --sync`; 2026-09-24): a kit
   cell (family `authored` or `overlay`) whose component wrote its beats (the `"src": "kit"` rows of
   `hf-graphics/sfx-hand.json`) has its `change` anchors held to those beats, not to pixel differencing, which merges
   small dots into a pill's rise and holds a scrolling scene open as one event. How runs, `"first change"` (the render's
   ENTRANCE, read on its pixels on every cell) and `"source"` are read is `change-events.py`'s docstring.
   - **The one designed lead the kit writes:** masked_value's dots start keying `components.VALUE_KEY_LEAD_S` ahead of
     the value word's beat (0.12 s, about 4 frames before the word, past L5's 2), so the value is visibly entered as it
     is said; the approved hook rendered it that way. It is recorded, never implied: the first tap's sfx-hand row carries
     it AS BUILT as `"sync_offset"` (shorter when the pill lands late), and `--sync` applies it exactly, so the value
     word's anchor needs no `"offset"`; one that names an `"offset"` must equal the row's, or it FAILS.
   - **The words each component expects,** one anchor per beat that sounds: `masked_value` its value word (its lead read
     off the row) and its live word; `hook_stack` its first word as a `first change` (the icon's pop on frame 0),
     then its claim's words; the `escalation` recipe (build.example.py) its pain words, one anchor each (the pour, each
     stack, the swarm); `call_card` the ring word and the answer (the accept tap on the cut where the other voice
     starts); `thread_cta` the keyword and the reply; `click_cta` its try, just and link words (the bump, the button, the
     tap). A silent beat (click_cta's ring on the name, its cursor on "click", its arrow) writes no row and takes no kit
     anchor. A capture or a montage keeps the pixel check (its events are the app's own motion).
7. **Probe in the browser before rendering** (the `graphics-build` skill's recipe). **Version every re-render. Copy
   nothing from another job** (comps, renders, captures): a new video is built fresh.
8. **A re-cut:** [`story-and-cut.md`](story-and-cut.md) § 6.1 owns the procedure. Nothing is re-timed by hand, because
   every time came from a word.

## 16. Density outcomes (calibration)

WHY: these are what the approved benchmark landed at, measured, so a first pass can check it is in the right world. They
are outcomes of enacting every line, never quotas to hit.

About 11-12 graphics a minute; about 85 % of the runtime under a graphic; graphics 1.2-12 s long, median about 3.9 s.
The second short (2026-10-15, 97 s, a step-by-step "how I'd do it" with no live call) came out denser and more real:
24 graphics (about 15 a minute), 15 of them real screens, about 82 % of the runtime under a graphic, 1.3-7.6 s long,
median about 3.1 s. A walkthrough turns over faster than a demo with a live call.
Far fewer means lines are going unshown; a graphic far longer than the median has probably stopped turning over per
named item (§ 13).

## 17. Illustrations only

WHY: a specific that worked once is the most tempting thing to copy and the least likely to fit the next video. These
are the benchmark's specifics; each is an "e.g." of a rule above and is never copied onto another video.

- **The cast and its colours:** three agents redrawn as vectors off their app avatars, e.g. an amber cloud `#F5A11C`, a
  pink pill `#EC2D8C`, a green circle `#22A35A`, eyes `#161616`. The rule is § 10's "the app's own shapes and colours".
- **Sampled capture fills:** e.g. a dark chat `#050505`, a white page `#fefefe`, a dark notes app whose `#161616` take
  rendered at `#090909`, a dark dashboard `#212121`, a still `#0f0f0f`. The rule is "sample the render"
  ([`captures.md`](captures.md)).
- **Per-brand lockup sizes:** e.g. icon 205 px + wordmark 104 px tall over a site hero (frame px: a capture scene is not
  scaled), icon 230 px + wordmark 116 px on the ad card (panel px inside the 0.79 fit, about 182 / 92 on the frame). The
  rule is "big but not dominating, the pair equal, re-sized by eye per brand".
- **Per-scene shot lists, crops, timings and cut points** (which dashboards, which seconds): this script's.
- **The hook object** (a masked phone number being assigned), **the metaphor object** (a SIM and signal bars), **the pain
  scene** (terminals flooding with errors) and **the negation** (the same terminal struck through): this script's premise,
  pain and payoff. The rules are § 3's.
- **The keyword and the folder's title and subtitle** in the CTA thread: this video's copy (the folder copy is Claude's
  wording, flagged to you as such).
- **Scale 200 on every graphic:** this shoot's 2160x3840 sequence (the placer fits the scale per sequence).
- **The second short's (2026-10-15) specifics:** the Monarch cash-flow report and its $375,006.28 (the proof hook);
  six major AI apps' App Store icons as the category row; DFY AI / AUTOMATION with a royal gear; a
  stove and the Google Docs mark; a $0 → $10,000 / mo meter; claude.ai's composer on `#111111` in Anthropic Sans; Whop
  payment notifications on an iPhone lock screen; a Whop lockup at 250/127 px over a page filled `#fcf1ed`; fills
  `#181818`, `#0d0d0d`, `#fbf8f7`; the notification glass at about 10-16 % white; the hook zoom 12 frames at 23.976.
  Each is that script's; the rules are § 3, § 5, § 8 and § 12.

---

## Values

The kit mirrors this block ([`kit/engine.py`](kit/engine.py), [`kit/components.py`](kit/components.py));
`workflows/test_talking_head_kit.py` holds them equal. One `KEY value` per line: the value is everything after the first
space, taken literally (CSS included); `a-b` is a range, `a,b,c` a list. Sizes are panel px except `HERO_ICON_PX` (frame
px); `*_S` in seconds, `*_FRAMES` in timeline frames, `*_MS` in milliseconds, angles in degrees, scales as factors.
`FLAGS_*` are the render wrapper's flags per family, exactly as it passes them. The motion bands (`POP_*`,
`RISE_CARD_*`, `PRESS_*`) are the kit's defaults; § 13 names the shipped variants outside them by role. `HOLD_READABLE_S`'s low end is
also `validate-plan.py`'s `TH_READ_HOLD`, the WARN threshold for a `readable` cell on this preset, held equal by
`workflows/test_plan_artifacts.py`: changing the value means changing the constant too. Capture geometry, the montage's plane and its in-plane scan are
[`captures.md`](captures.md)'s values; the bands are [`layout.md`](layout.md)'s.

```values
PANEL_TO_FRAME 0.79
HERO_ICON_PX 236
ROYAL #1e48ff
SKY #57c9f0
TXT #e8f0ff
MUTED #8fa6d4
GREEN #2ff58a
RED #ff4d5e
UI_TEXT #ffffff
OS_ACCEPT #30d158
OS_DECLINE #ff3b30
BUBBLE_IN #2a2b31
ATTACHMENT #1d1e23
TYPING_DOTS #9a9daa
AVATAR_DISC #0b0c11
DANGER_WASH radial-gradient(90% 80% at 50% 50%, rgba(255,40,60,0) 30%, rgba(255,40,60,0.55) 100%)
IG_SENT linear-gradient(120deg, #8a3ffc 0%, #b537d8 50%, #e0307e 100%)
BG_FILL #010102
BG_GRID rgba(74,124,255,0.11)
BG_GRID_LINE_PX 1
BG_GRID_PX 90
BG_LIGHT_PX 1480
BG_LIGHT_AT -200
BG_LIGHT radial-gradient(circle at 50% 50%, rgba(40,84,255,0.07), rgba(40,84,255,0.024) 38%, rgba(40,84,255,0) 68%)
BG_DRIFT_X 38
BG_DRIFT_SCALE 1.06
BG_DRIFT_S 5.5
BG_DRIFT2_Y 22
BG_DRIFT2_S 3.7
BG_DRIFT_EASE sine.inOut
BG_VIGNETTE radial-gradient(120% 100% at 50% 50%, rgba(0,0,0,0) 55%, rgba(2,5,16,0.38) 100%)
BG_SEAM_PX 70
BG_SEAM_TO rgba(2,5,16,0.85)
FLAGS_AUTHORED STEP_FPS=12 GLOW=0.26 GRAIN=5
FLAGS_CAPTURE GLOW=0.12 SCAN=1
FLAGS_CAPTURE_WHITE GLOW=0.12 SCAN=1 SCAN_AMP=0.06
FLAGS_MONTAGE GLOW=0.18
FLAGS_OVERLAY none
BLOOM_SIGMA 30
BLOOM_BRIGHTNESS 0.12
BLOOM_CONTRAST 1.12
BLOOM_CURVES 0/0 0.5/0.62 1/1
SCAN_PERIOD_PX 6
SCAN_AMP 0.10
SCAN_AMP_WHITE 0.06
FONT_DISPLAY Inter
FONT_MONO SF Mono
HERO_PX 126
HERO_WEIGHT 900
HERO_TRACK -3
NAME_PX 52-58
NAME_TRACK -1
BUTTON_PX 70
LABEL_PX 25-30
LABEL_TRACK 2-3
SURFACE_RGB 18,20,28
SURFACE_ALPHA 0.92-0.96
RIM_PX 2
RIM_ALPHA 0.09-0.12
UI_SHADOW 0 24px 60px rgba(0,0,0,0.5)
RADIUS_ROW 44
RADIUS_CARD 34-68
MARK_SHADOW drop-shadow(0 26px 40px rgba(0,0,0,0.55))
MARK_SOLID_ALPHA 128
MARK_PAIR_TOL_PX 2
TERM_BODY #0d0f14
TERM_BAR #1a1d25
TERM_BAR_PX 64
TERM_LIGHTS #ff5f57,#febc2e,#28c840
TERM_RADIUS 26
TERM_MONO_PX 27
TERM_LINE_PX 42
TERM_TEXT #aab3c8
TERM_ERROR #ff5d6c
TERM_WARN #febc2e
EVENT_LEAD_S 0.06
SYNC_TOL_FRAMES 2
STEP_QUANTUM_MS 83
POP_FROM 0.3-0.6
POP_BACK 1.4-2.6
POP_FRAMES 7-10
RISE_CARD_Y 60-110
RISE_CARD_FROM 0.90-0.94
RISE_CARD_FRAMES 8
LOGO_X 420
LOGO_ROT 14
LOGO_FRAMES 9
LOGO_EASE back.out(1.4)
PRESS_DOWN 0.74-0.80
PRESS_DOWN_FRAMES 2-3
PRESS_UP 1.0-1.12
PRESS_UP_FRAMES 3-4
PRESS_UP_EASE back.out(2.4)
DROP_FRAMES 11
DROP_FROM 0.92
DROP_EASE power3.out
EXIT_FRAMES 5-8
EXIT_EASE power2.in
HOLD_READABLE_S 2-3
LONE_HOLD_MAX_S 1-2
RING_FROM 0.6-1
RING_TO 1.5-1.9
RING_S 0.5-0.9
ESC_STAGE 0.86
ESC_SHAKE_X 7
ESC_SHAKE_ROT 0.5
ESC_SHAKE_S 0.05
ESC_WASH_S 1.2
ESC_SCROLL_STEPS 14-18
PUSH_FRAMES 10
PUSH_EASE power3.inOut
ARROW_PX 150
ARROW_BOB_PX 16
ARROW_BOB_S 0.22
GFX_PER_MIN 11-12
GFX_COVERAGE 0.85
GFX_S 1.2-12
GFX_MEDIAN_S 3.9
NEW_EVERY_S 1
```
