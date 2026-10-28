# Story and cut: the Talking Head Explainer

The story and cut taste of this format: which filmed lines survive, in what shape, in what order, and how tightly they
join. The thesis in one line: **a talking-head explainer sells a claim by proving it, so the cut keeps the claim, the
proof and the ask, plays them in the order they were filmed, and joins them tight enough that the proof lands the
moment the claim is made.** Everything below serves that.

Calibrated on one approved two-minute sponsored explainer and on the creator's two hand passes over it
(2026-09-20..23), with an earlier approved short of the same kind as the second, demo-first shape (§ 2.5). The FINAL
state wins: an early call the creator later corrected is in § 7, never a rule. Tags on each rule: **[CREATOR]** = the
creator's own instruction, correction or hand edit; **[ADOPTED]** = in the cut the creator approved, or it survived both
of the creator's hand passes untouched;
**[DERIVED]** = reasoned from tagged rules, not yet seen on a shipped cut. Every example is an illustration, marked
"e.g."; the principle is the rule (2026-09-10).

Every rule is written the same way: the rule in bold, then WHY, then how to tell.

## 0. Scope

- **Read at step 2 before the kill pass, and again at 5a for the beat sheet.** At 5a
  [`graphics-plan`](../../../.claude/skills/graphics-plan/SKILL.md#step-1--the-beat-sheet-understand-the-video-before-decorating-it)
  takes four things from here: each beat's slot and role (the brief's own map, else § 2 or § 2.5), the promise →
  payoff map (§ 2.4), the specific evidence lines that survived (§ 4.4, § 4.13), each of which earns its own on-screen
  beat, and which telling of a repeated list carries its item beats (§ 4.12).
- **The universal cut rules live in the [`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md) skill. They are
  linked here, never restated:**
  - [the last complete take](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply) of every line
  - [grafting a mid-sentence restart](../../../.claude/skills/rough-cut/SKILL.md#author-the-cuts)
  - [relevant is not necessary](../../../.claude/skills/rough-cut/SKILL.md#the-edit-philosophy-non-negotiable)
  - [the closing beat is content](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply)
  - [the coverage audit](../../../.claude/skills/rough-cut/SKILL.md#transcribe) before a single cut is authored,
    on any take with a second voice through a speaker
  - [four more keep/kill rules this format taught](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply), universal
    since: (a) prosody decides a list tail, (b) specific examples stay and a generic capability list goes, (c) a demo
    call is cut to its proof beats, (d) the other party's confirmation is proof. § 4.11-4.13 and § 5.6 keep only this
    format's evidence and what each adds at 5a.
- **[`layout.md`](layout.md) decides each line's layout. This doc decides which lines survive and in what shape.**
  What goes in the panel is [`graphics.md`](graphics.md), the real screens are [`captures.md`](captures.md), the
  sound is [`sfx.md`](sfx.md), the captions are [`captions-style.md`](captions-style.md) (its builder reads
  `transcript/voices.json`, which step 2 writes when a second voice is heard), and the deliverables, the ad variant and
  a changed CTA word are the [README](README.md#deliverables).

## 1. The brief is the spine [CREATOR]

**1.1 Before transcribing a scripted explainer, find its brief.** The brief is the video's own page (its beat sheet)
wherever the creator keeps your pre-production: where RUN.md or your ask says it lives, else the pre-production project
the repo-root [`CLAUDE.md`](../../../CLAUDE.md) names, whose own schema note says how to query it.
- Match on one distinctive word of the video's title, or on the filming date. Several plausible hits: list them and
  ask which.
- Write the found page's URL into RUN.md.
- The CTA links come from the brief, or else from the matching long-form's published description, where the creator
  keeps it (as [`captures.md`](captures.md#9-cta-captures) says).
- Nothing found: ask once, in one sentence, for the brief and the CTA links together, and say so in RUN.md. Meanwhile
  the [universal intent read](../../../.claude/skills/rough-cut/SKILL.md#folder-contract) carries the cut, so nothing
  stalls on the answer.

WHY: "find the … brief on this one first so you have a general idea of what we're going for" (2026-09-20). The
hook, the framing and the ask are decided before the shoot, so a cut made without the brief is guessing what the video
is for. A run that skipped the lookup guessed the CTA links, the platform and the spelling of a name.
How to tell: RUN.md carries the brief's URL, or says none was found and that the one-line question was asked.

**1.2 Take five things from the brief:**
- the hook
- the beat map
- the CTA keyword and the promised deliverables, with their real URLs ([`captures.md`](captures.md#9-cta-captures)
  shoots them)
- the production style (on the benchmark, the brief's split-screen style is what picked this preset:
  [README § Step 0](README.md#step-0-this-preset-is-resolved-here))
- the spelling of every name the video says, which beats the ASR's
  ([`captions-style.md`](captions-style.md#4-what-is-written))

WHY: each one is a decision the creator already made. Re-deciding any of them in the edit overrides you in silence.
How to tell: all five are written into RUN.md before the first cut is authored.

**1.3 Map every filmed beat onto a brief beat before authoring a cut.** A brief beat may be carried by a line filmed
for another slot (e.g. the contrast line also says who the video is for); map it there rather than calling it missing.
WHY: the map is how the cut knows what each line is FOR, and it is what makes a gap visible.
How to tell: RUN.md's Request coverage has one line per brief beat: its kept take, or PICKUP, or cut with the reason.

**1.4 A brief beat with no take is a PICKUP in RUN.md. Never invent it, and never drop it in silence.**
WHY: document, don't manufacture ([`CLAUDE.md`](../../../CLAUDE.md#rules)). On the benchmark the brief's two-second
sign-off had no take anywhere in the raw; the cut ended on the CTA, the closer was reported as a pickup, and that
ending was approved.
How to tell: every brief beat without a take appears in RUN.md's flags as a pickup, in the report, in one line.

## 2. The skeleton: two attention peaks, proof before thesis

**The brief's beat map wins.** The skeleton below is the fallback when no brief exists, and a reading aid for what each
slot is for when one does. A brief with another arc (contrast-first, a list, a tutorial, story-led, demo-first) is cut
to its own map. It is never pushed toward this order, and no line its arc needs is killed because this table would put
something else there.
WHY: the beat map is the creator's decision (§ 1.2). This table is one approved video's order, which its brief happened
to design; treating it as a template would override the next brief in silence.
How to tell: RUN.md names which map the beat sheet follows: the brief's, this skeleton (no brief), or § 2.5.

The benchmark's order, in proportional slots. The calibration column is what the approved cut measured, never a quota.

| Slot | Its job | WHY | Calibration (approved cut) |
|---|---|---|---|
| **HOOK** | One sentence: what was done and what came of it. The video opens on its first word. | The first second has to say what the video is and that it is real. | about 4 % (one sentence) |
| **PROMISE** | An open loop about the payoff (e.g. "you're not gonna believe how easy this was"). | It buys the explainer: the viewer stays to see the loop closed. | about 3 % |
| **EXPLAINER** | One sentence per tool, framed as an everyday analogy, with a benefit clause that sets up the next beat. The conversational bridge into it stays (e.g. "now, if you haven't heard already"). | "Human analogy over features" (the brief): nobody has to understand the tech to get it, and the benefit clause hands the viewer to the proof. | about 12 % |
| **EARLY LIVE PROOF** | The premise working, on camera. It doubles as the pattern interrupt (e.g. the agent calls mid-sentence). | Proof earns the rest of the watch, and the interrupt resets the retention curve where a short starts to bleed. | lands by about 20 % (18 %), about 7 % long |
| **WALKTHROUGH** | Each component gets one concrete job, with its purpose clause. | A specific job is evidence; a component with no job is only a name. | about 25–30 % |
| **RE-HOOK + SECOND PROOF** | A turn line (e.g. "but here's where it gets crazy"), then a bigger proof of a new capability. | The second reset of the curve, where a short bleeds again; the escalation is what the turn promised. | starts near 50 % (53 %), about 20 % long |
| **CONTRAST / WHO IT'S FOR** | The harder alternative, and who struggles with it. | It gives the claim its reason to exist and names the viewer, right where the claim needs it. | about 9 % |
| **BIG CLAIM + OBJECTION-KILLER** | The thesis in one line, then the objection answered (e.g. "no code and no technical knowledge required"). | The thesis lands only once the demos have earned it; the objection-killer pays off the promise. | about 11 % |
| **CTA** | The ask, and the video ends on it. | The ask is the conversion moment; anything after it is runtime past the payoff. | about 7 % |

At 5a the slots carry these beat-sheet roles (the approved plan's): HOOK `hook` · PROMISE `promise` · EXPLAINER
`setup` · EARLY LIVE PROOF `demo` · WALKTHROUGH a `setup` signpost, then `demo` per component · RE-HOOK `payoff` (the
turn's own reveal), then `demo` and `evidence` · CONTRAST `point` · BIG CLAIM `payoff` · OBJECTION-KILLER `punchline` ·
CTA `cta`.

**2.1 The principle, on any arc: proof before thesis, and a second attention reset near the middle if one was
filmed.** [CREATOR via the brief · ADOPTED in the cut]
WHY: the early proof and the re-hook each reset the retention curve where a short usually bleeds, and a thesis stated
before the demos is only an assertion. The slots scale from 60 s to 2 min: a shorter piece shrinks every slot, it
does not drop the peaks.
How to tell: the beat sheet names the proof beats, the thesis and (if filmed) the reset by line, and the thesis's
first full statement comes after the first proof. A cut with no early proof or no reset says why in RUN.md (nothing
like it was filmed); neither is ever invented.

**2.2 Where the first proof lands, and how much of the runtime is proof, are REPORTED, never enforced.** [ADOPTED]
The step-2 report carries the first proof's start as a share of runtime, against PROOF_BY_SHARE, and the proof share.
The approved cut measured 18 % and 54 % (the early proof, the walkthrough and the second proof).
WHY: the numbers describe how one arc worked, not what the next must be. As a trigger they would kill setup lines
another brief needs. The cut plays in filmed order (§ 4.1), so a proof that lands late is the creator's to weigh, and
moving it up is your call, never the editor's.
How to tell: the report reads as an observation (e.g. "first proof at 26 %, reference ≤ 20 %"), and no line was killed
or moved because of it.

**2.3 The re-hook's position is REPORTED against REHOOK_NEAR_SHARE, never enforced.** [ADOPTED]
WHY: the midpoint is where the second bleed starts, so a turn line there is the one sentence that restarts the watch;
but where it falls is the brief's and the take's, not the editor's.
How to tell: the report gives the re-hook's start share, or says none was filmed. No line was killed to pull it
earlier, and no turn line was manufactured.

**2.4 Every promise opened in the first 8 s is paid off on screen.** [ADOPTED]
WHY: an unpaid promise reads as clickbait, and a paid one is what makes the ending land (e.g. the promise "how easy
this was" is paid by the big claim and the objection-killer). On a demo-first piece the open loop is what the cold open
leaves unanswered (who is on the line, and is it real?), and the reveal pays it (§ 2.5).
How to tell: the beat sheet lists each promise the opening makes, with the beat that pays it off. A promise with no
payoff is a flag, never covered by a graphic that claims it.

**2.5 The demo-first variant: a cold-open call.** [ADOPTED on an earlier approved short · the roles DERIVED]
Some pieces open straight on the proof: a live call plays from the first frame and runs most of the video, a twist
lands inside it, then the reveal and the claim, who it is for, and the CTA. No promise and no explainer line are
filmed, and none is assembled. The role map:

| Slot | What it is | 5a role |
|---|---|---|
| **COLD-OPEN CALL** | The hook and the early live proof in one. Its opening exchange is the hook from frame 0, and its greeting stays (§ 4.11). | `hook` on the opening exchange, then `demo`; a confirmation is `evidence` (§ 4.12) |
| **TWIST** | A turn inside the call that changes what the viewer thinks they are hearing (e.g. the agent is asked whether it is an AI and says yes). | the re-hook: `payoff` |
| **REVEAL + CLAIM** | The sentence that says what the viewer just watched and what it took (e.g. "this took me half an hour to build"). It pays the cold open's loop and does the explainer's job. | `payoff` |
| **WHO IT'S FOR** | Who needs it, and what it is worth to them. | `point` |
| **CTA** | The ask, and the video ends on it. | `cta` |

WHY: the call is the attention peak, proof-before-thesis taken to its limit; the twist is the second reset; the reveal
re-frames everything the viewer just heard, which is exactly what a big claim does. Re-casting the reveal as the hook to
give the hook frame a home would put the hook at 70 % of the runtime.
How to tell: RUN.md names the variant; the beat sheet tags the call's opening `hook` and the reveal `payoff`, and no
later line is re-cast as the hook. The § 2.2 and § 2.3 report lines read the call's start and the twist.

## 3. Length is what the necessity filter leaves [ADOPTED]

**3.1 The brief's duration is not a target.** Cut everything the viewer does not need right now
([relevant is not necessary](../../../.claude/skills/rough-cut/SKILL.md#the-edit-philosophy-non-negotiable)), keep
every beat that proves the claim, and offer borderline keeps as a list in the
[report](../../../.claude/skills/rough-cut/SKILL.md#report-back) instead of cutting them.
WHY: a brief of about 70 s became an approved 120 s, because every proof beat stayed. The creator hand-tightened twice
and never pushed toward the brief's number: you removed air, a goodbye and one generic list, and put one line back.
How to tell: every kept line answers "does the viewer need this now?" on its own. "The cut is longer than the brief"
is never a reason to kill a line; "this line proves nothing new" is.

## 4. What the cut keeps and kills on this format

**4.1 The cut subtracts, in filmed order.** [ADOPTED]
The creator films from the brief's beat sheet, so the arc arrives designed. The cut decides which lines survive, never
where they go. The universal [move rule](../../../.claude/skills/rough-cut/SKILL.md#author-the-cuts) still exists, but
on a scripted explainer it almost never fires, and a move is named in the report.
WHY: both of your hand passes were trims, kills and restores, never a move, and every segment of the approved cut runs
in source order. Reordering a talking head also orphans connectives and breaks the continuity of look and energy.
How to tell: every segment's source start is later than the one before it; anything else is a named deviation.

**4.2 A claim lands directly against its proof.** [ADOPTED · the join tightened by CREATOR]
Two kinds of line go:
- a benefit line stated BEFORE any proof: it echoes the hook. Say the plain benefit once, after the proof, at the
  claim (e.g. "when you combine these two, it's like having a team that runs your whole life", before any demo: cut).
- narration that previews the next demo: the demo enters cold off the claim before it
  (e.g. "so they get all this done while I'm away, and he calls to report", right before the call that shows it: cut).

WHY: telling before showing spends the reveal. The brief's own reading of its reference was "the benefit said plainly
after the proof, not before it". Your hand pass then shortened the claim-to-demo join from 527 to 277 ms (2026-09-22),
so the demo lands even faster.
How to tell: read the cut sheet as prose and mark every line that says what something does or feels like before the
viewer has seen it do anything. Each one is cut.

**4.3 A second demo earns its slot only with a new capability.** [ADOPTED]
WHY: repetition reads as filler; escalation is what the re-hook promised. The creator lengthened the second demo by
hand (+3.7 s, 2026-09-21) rather than trimming it.
How to tell: name each demo's capability in two words. Two with the same name: the one that proves less goes.
e.g. the first demo shows an agent reporting in; the second shows agents delegating to each other while the creator
redirects them live.

**4.4 Parallel items get equal weight: each keeps its role plus its purpose clause.** [ADOPTED]
When the video introduces a set (team members, tools, steps), a thin item gets its trimmed purpose clause back.
WHY: a thin item reads as a pace dip, and the purpose clause is the reason the item exists. A list of SPECIFIC uses
inside an item is evidence and stays whole (§ 4.13).
How to tell: line the items up. Each has a role and a "so that I can…" clause, and none reads visibly thinner than its
siblings.
e.g. "Then I have my product lead … checking the metrics, so that I can keep improving the product."

**4.5 The contrast turn before the claim stays whole, signpost and all.** [ADOPTED]
WHY: naming the harder alternative and who struggles with it gives the claim its reason and does the who-it's-for job
exactly where the claim needs it. It is persuasion, not meta-narration
([the keep/kill line](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply)). You kept the whole
block through both passes and trimmed only its edges. Inside it the usual rules still run: a doubled clause goes.
How to tell: the lines just before the big claim name an alternative, its pain and a person who feels it, and the
signpost that turns into them ("now here's the thing") is still there.
e.g. "Now here's the thing, guys. Normally I'm a huge fan of X, but it can get really technical, and it's a bit
overwhelming for someone new."

**4.6 Off-script audio goes without asking.** [ADOPTED]
Phone tests, rehearsal, direction to a live agent, setup talk, a previous project's voice answering the phone. On a
staged demo the agent's delivered line stays and the direction around it goes (e.g. "can you just repeat this line
back", "stay on the line": cut; the line the agent then says: kept).
WHY: the viewer hears noise and the fiction breaks. The brief shows it is not a beat, so there is nothing to ask
([questions are a last resort](../../../.claude/skills/rough-cut/SKILL.md#gotchas)).
How to tell: the line maps to no brief beat, and it addresses the crew, the tool or the setup instead of the viewer.

**4.7 No mid-phrase surgery to fix a wording nit, and a short framing clause that carries the subject stays.**
[ADOPTED]
WHY: a joint is the bigger defect (the same finding as the rough-cut's mid-phrase filler row), and without the framing
clause the verbs after it hang off nothing. Both kinds survived both of your passes; reviewer "fixes" that did
otherwise were rejected.
How to tell: a proposed cut inside a phrase that removes one loose word is rejected. A clause that names who does the
verbs that follow is kept.
e.g. "So he calls for me, makes a dinner reservation, makes a car-shop appointment…": the first clause stays.

**4.8 A V1 shot of LONG_SHOT_FLAG_S or more flags the LINE first: "is all of it necessary?"** [CREATOR]
Ask that before anyone proposes a visual fix. Only a line that survives the question goes to [`layout.md`](layout.md)
to be broken up by framing.
WHY: the step-2 report flagged the longest shot (13 s, the big claim). Your answer in your hand pass was to cut the
generic half of the line (§ 4.13), not to decorate it (2026-09-22).
How to tell: every segment of 10 s or more is listed in the step-2 report with its verdict.

**4.9 If no closer was filmed, end on the CTA and say so. Never manufacture a sign-off.** [ADOPTED]
The CTA's last word gets a short tail (e.g. about 0.3 s) and the final graphic holds to the last frame
([`graphics.md`](graphics.md)). A closer that was filmed is
[content](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply) and stays.
WHY: document, don't manufacture; a sign-off assembled from other words is audible. Ending cold on the ask is a
legitimate short-form ending, and the ask is the conversion moment.
How to tell: the EDL's last segment ends on the CTA's last word, and RUN.md names the missing closer as a pickup
(§ 1.4).

**4.10 The ask is the creator's.** [CREATOR]
- The keyword is your spoken word. The editor never changes it on its own authority.
- Asked to pick one, propose one short, typable noun that names the payoff (what the viewer gets, usually the thing
  built in the video), never the sponsor's brand.
- Remind you the DM trigger must equal the keyword. Setting that up is posting work, outside this repo.
- A keyword changed after the shoot follows [README § Deliverables](README.md#deliverables) (a changed CTA word).

WHY: the sponsor did not want its brand as the keyword ("they don't want to use that for this video", 2026-09-22). A word that names the value reads as a resource, not an ad, and one short word means more comments and
fewer typos slipping past the trigger (proposed on that reasoning and accepted, 2026-09-22). A word that differs from
the trigger breaks the funnel silently.
How to tell: the keyword is one token, a noun, spelled one obvious way, and the report carries the trigger reminder.

**4.11 A demo call is cut to its proof beats.** [ADOPTED · CREATOR on the goodbyes] The rule is universal:
[`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply) keep/kill rule (c) (the
announcement, e.g. "hold on, that's literally him calling me right now", is kept; a cold-open call keeps its
greeting). On this format the call card and a ring sound sell the ring and the accept
([`graphics.md`](graphics.md), [`sfx.md`](sfx.md)), and the turn timing is § 5.5.
WHY (this format's evidence): you cut the goodbye by hand (2026-09-21): the call ends the moment its proof lands.
How to tell: read the call's kept span as a transcript; nothing plays after the last proof line.

**4.12 The other party's confirmation of an action is proof, never an echo. Keep it whole.** [CREATOR] The rule is
universal: [`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply) keep/kill rule (d). What this format
adds, at 5a: **when the other party repeats a whole list back** (the creator's request, then the agent's recap), both
tellings stay in the cut and the item-by-item beats go on the confirmation; the first telling carries the ask, not the
items. [DERIVED from this rule and [`graphics.md`](graphics.md#4-story-in-reel-order-adopted)'s no-early-payoff rule]
WHY (this format's evidence): you restored the full confirmation (+3.67 s) after it had been trimmed to "Got it."
(2026-09-21); itemizing the first telling on screen would show the payoff before the proof arrives.
How to tell: every second-party confirmation in a kept call runs to its own last word; on a repeated list, one beat per
item on the confirmation and none on the request.

**4.13 Specific examples stay; a generic capability list goes.** [CREATOR] The rule is universal:
[`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply) keep/kill rule (b). What this format adds, at
5a: each item of a kept list of concrete uses earns its own on-screen beat (e.g. "a dinner reservation, a car-shop
appointment, a dentist appointment"), and a cut generic list takes its graphic with it.
WHY (this format's evidence): you cut exactly this by hand (2026-09-22): "…their own AI personal assistant" stayed and
"that can handle meetings, calendars, tasks, calls, texts, anything, you name it" went. It restated the demos, diluted
the claim and made the video's longest shot (§ 4.8). The brief's own principle: "specific use beats generic capability
every time".
How to tell: one beat per concrete item; category words after the point is proven are cut to the landing noun.

**4.14 The hook take is the most EXPRESSIVE complete read, not the last one.** [CREATOR; the measure DERIVED] The rule is
universal: [`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply)'s restarted-takes row,
its one exception. What this format adds: the hook is the line a short lives or dies on in its first second, so the pick
is heard against the hook graphic's timing too (a livelier read can be longer or shorter: the hook cell lives exactly
its sentence, [`layout.md`](layout.md) § 6).
WHY (this format's evidence): "I sounded a little dead in the first one" (2026-10-14); WhisperX had dropped most of the
hook's takes on that raw, so the coverage audit's slice ASR is what found the livelier one.
How to tell: the step-2 report names the hook's complete takes, the pick and the runner-up.

**4.15 Recaps, optional asides and hype lines go.** [CREATOR]
Three kinds of line pass the necessity filter on a first read and come out at review, so cut them on the first pass:
- **a progress recap between steps** ("cool, so now that we have a website and we can take payments,"): the next step
  enters cold, its own graphic says where we are;
- **an optional aside off the main path** ("you can edit the ad using AI if you know how to do that"): a side road the
  viewer does not need to follow the steps; it also outranked the plainer "you can edit it using Claude" under the
  last-take rule, and both went;
- **a hype or guilt line before the closer** ("if you don't take action with this super saucy information"): the
  closer ("it's never been easier to make money online") lands harder on its own.
WHY: each cost a declared re-cut at step 7 on 2026-10-15 (a frozen reference, a replay, the audio chain, every graphic
and sound re-laid), the most expensive way to remove two seconds. "That's really not necessary for the script."
How to tell: read the cut sheet as prose; a sentence that only says where we are, offers an optional alternative, or
urges the viewer without giving them anything new is cut and named in the report as cut, so you can put it back.

## 5. Joins and pace [CREATOR]

**The machine cut must already land here.** The creator's hand pass is taste, not a join repair.

**5.1 Joins run tight, tightest inside a running sequence.** Total silence at a join is the outgoing segment's tail
plus the next segment's lead, read off the EDL against the aligner's word edges (`words.json`), the basis these were
calibrated on:
- into the next item of a running list or sequence (it opens on a sequence marker: "then I have", "next"): at most
  JOIN_RUN_MAX_S (about 150 ms)
- claim → its demo, or claim → its objection-killer: at most JOIN_CLAIM_DEMO_MAX_S (about 280 ms)
- after a landed line, inside an item or at a section change: JOIN_LANDED_S (about 280–390 ms)
- [inside an in-sentence graft](../../../.claude/skills/rough-cut/SKILL.md#author-the-cuts): as near zero as the
  envelope allows
- turn gaps inside a demo call: compressed to conversational timing (about 180–340 ms on the approved cut), never the
  real 1–3 s latency

The last line of an item whose next item follows on a sequence marker, and a claim its demo answers, never carry a
[beat tail](../../../.claude/skills/rough-cut/SKILL.md#author-the-cuts), and the next item's head starts on its
word's attack, with no quiet or breath kept in front of it: the marker already says "more is coming", so a pause
there only stalls.
WHY: "tightening up the cut because there's some extra space" (2026-09-22). You razored every join over 300 ms
that ran into a continuation: 329 → 79 and 318 → 151 ms between two component intros, 527 → 277 ms on the claim →
demo turn, 383 → 270 ms into the objection-killer. What you took out was silence the machine had kept as a `beat` on an
item's end or on a claim, and a quarter second of low-level sound before the next item's first word. Every join after
a landed line you left alone: between the explainer's two tools (359 ms), between two lines about one component
(390 ms) and at every section change (325–388 ms). The approved cut's joins run median 277 ms, max 390 ms.
How to tell: compute every join on the EDL before the replay and label each one run / claim → demo / landed. A join
over its ceiling is fixed at the EDL boundary, never with an authored pad.

**5.2 No breath at tails. Refuse an audit extension into breath.** [ADOPTED]
WHY: a short is pure momentum. On the benchmark the audit wanted to move the promise line's OUT +667 ms; the waveform
showed room tone past the cut, the move was refused and the OUT pinned (`pin_out`).
How to tell: every BREATH or ⚠ verify line at an OUT in the
[audit](../../../.claude/skills/rough-cut/SKILL.md#audit-the-cut-on-the-finish-surfaces-grid-every-app-finish-job-the-grid-matters-most-when-source-and-sequence-rates-differ)
is checked on its sheet panel, and a refused move is pinned.

**5.3 A JCUT_FRAMES-frame J-cut out of the hook or promise into the first explainer line is available.** [CREATOR,
seen once: a taste signal, never a mandate]
Your hand pass started the explainer's first line 2 frames (83 ms at 23.976) under the promise's picture.
WHY (a reading of your edit): it carries momentum across the one join where the video changes gear from claim to
explanation, the place a visible pause invites a swipe.
How to tell: offer it in the report. No repo tool replays an audio lead yet, so it is laid by hand on the finish
surface and recorded in RUN.md.

**5.4 Segments stay whole sentences. Picture pace comes from step 5, never from chopping audio.** [ADOPTED]
WHY: every audio joint is a defect risk, while framing switches and graphic turnover add visual cuts for free. The
reference reel's short shots (about 1.3 s) were adopted as a grammar, never as a cut rate. The approved segments ran
5.4 s on average, 1.2 to 10.7 s.
How to tell: no segment boundary falls inside a sentence except a
[graft of a restart](../../../.claude/skills/rough-cut/SKILL.md#author-the-cuts) or a killed doubled clause.

**5.5 Demonstrations play in real time. A call's dead latency is cut.** [CREATOR]
A demonstration the viewer must follow plays continuously, with no jump cuts between its events
([`captures.md`](captures.md#5-natural-movement) owns the picture side). The wait between a call's turns is not a
demonstration: it is dead air, compressed as in § 5.1, and the ring and the accept cost no audio time (§ 4.11). This is
where the format differs from a long-form follow-along, where the wait for the phone
[stays](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply): there the viewer is doing the steps
alongside; here the call is one proof beat inside two minutes.
WHY: "The screen recording should show exactly what I'm talking about happening in real time" and "I don't know why
it cuts and looks like it cuts" (2026-09-21). You never restored a turn gap in either hand pass.
How to tell: a demonstration's span holds no cut between its events; a call's turn gaps sit inside the § 5.1 range.

**5.6 Prosody decides a list tail.** [CREATOR] The rule is universal:
[`rough-cut`](../../../.claude/skills/rough-cut/SKILL.md#auto-kill-rules-always-apply) keep/kill rule (a), with this format's pause
floor `TAIL_PAUSE_MIN_S` (§ Values) (e.g. "…scripts to post, [240 ms] et cetera.": cut); a mid-phrase "et cetera"
stays as rhythm.
WHY (this format's evidence): "that part like got cut off … mid sentence" (2026-09-20). The only gap at the
rejected cut was a 40 ms dip on a rising comma; the OUT was moved +0.876 s to the envelope floor, pinned, and survived
both of your hand passes, and your 2026-09-21 pass extended another clipped list comma by 0.25 s.
How to tell: at every OUT before a list tag, measure the gap to the tag and listen to whether the kept word falls.

## 6. After your hand cut

**6.1 Your hand cut is the cut: a hand re-cut is a RE-RUN, never a re-author.** [CREATOR] In this order:
1. **Read the live timeline into the EDL first,** with the lane's live read
   ([`LANES.md`](../../../LANES.md) § step 2; Premiere: `lanes/premiere/live-edl.py … --write`). The HOW is
   [`rough-cut` § Learn from the hand pass](../../../.claude/skills/rough-cut/SKILL.md#learn-from-the-hand-pass-premiere-finish-jobs);
   the EDL is never re-replayed over your cut. Why first: every later step maps through this EDL.
2. **Hold it to two asserts:** every V1 clip's timeline duration equals its source span, and the EDL total equals the
   timeline's. Where the lane's read does not assert both, assert them by hand. Why: once, a stale readback of a clip
   the editor had extended in place was logged as your trim, the transcript ran 0.876 s early after it, and six scenes
   were synced to the wrong clock. The mismatch (125.000 against 125.876 s) was there to see.
3. **Run `uv run workflows/ripple-cut.py projects/<job> --from <the EDL the layers were authored on>`**, dry run then
   `--apply`. It maps the transcript clock, the plan, the placement and the SFX cues through the source and names
   every row that orphaned or straddles a cut; then the build re-runs from words (the kit, the captions as one layer,
   the lane's layout keys), and the bed and grade are re-fit to the new end ([README](README.md#music-opt-in)).
   [`edit-video`](../../../.claude/skills/edit-video/SKILL.md#where-the-run-stops-on-its-own) owns the gate. Why: a
   layer re-timed by hand is where drift and dropped cues come from.
4. **Drop the graphics of lines you removed, and never restore anything.** A line, a graphic, a sound or a level you took
   out stays out; a sound of your whose graphic moved is reported with its shift, never moved
   ([README](README.md#working-with-the-creator)). Why: a line is never kept to save a graphic, and your edit is the
   strongest taste evidence there is.

WHY: "I adjusted the rough cut, so make sure you view the timeline and see the cut that I actually want. That's the new
cut." (2026-09-21); "when I'm done, I need you to retime everything and replace everything to make sure
everything is cohesive and flows nicely" (2026-09-22).
How to tell: the live read reports that V1 adds up; the ripple's ORPHANED rows are exactly the graphics of the removed
lines and each is gone; V1/A1 read back identical to your cut; the lane's cut proof passes on it.

**6.2 Every hand cut teaches this doc.** [CREATOR]
Diff it against the EDL it replaced
([`rough-cut` § Learn from the hand pass](../../../.claude/skills/rough-cut/SKILL.md#learn-from-the-hand-pass-premiere-finish-jobs)
owns the diff). A delta that recurs on this format becomes a rule here; a delta true of every format goes to
`rough-cut`.
WHY: your trims are the ground truth this doc approximates. § 4 and § 5 came from exactly two such diffs.
How to tell: RUN.md records what your pass changed and where each recurring change was written down.

## 7. Rejected

Each was tried or proposed on the benchmark and reversed, by the creator or by measurement.
- Killing a one-breath list tag ("et cetera, et cetera") as a filler tic, then pinning the cut against the audit that
  wanted it back: "that part like got cut off … mid sentence" (2026-09-20). § 5.6.
- Trimming the other party's confirmation of an action to its first two words as an echo of the instruction. You
  restored the whole confirmation (2026-09-21). § 4.12.
- Keeping goodbyes and pleasantries inside a demo call. You cut them (2026-09-21). § 4.11.
- Keeping a generic capability list after the demos, and building a graphic for it. You cut the line and the graphic
  went with it (2026-09-22). § 4.13.
- `beat` on an item's end inside a running list and on a claim right before its demo: joins of 300–530 ms, razored
  by hand (2026-09-22).
- Accepting an audit extension into breath or room tone after a line.
- Reviewer "fixes" that cut inside a phrase to repair one word, or kill a subject-carrying framing clause as an echo.
- Aiming the cut at the brief's duration.
- Chopping sentences, or jump-cutting a demonstration, to chase a reference reel's shot length.
- The sponsor's brand as the comment keyword, or a vague keyword that names no payoff.
- Treating a stale app readback as the creator's trim: a transcript clock 0.876 s early and six scenes out of sync.
- Re-replaying the EDL over your hand cut, or restoring anything you removed.
- The last take of the hook kept when it sounded flat (2026-10-14). § 4.14.
- A progress recap, an optional "you can also" aside and a hype line before the closer, kept on the first pass and cut
  by you at step 7 (2026-10-15). § 4.15.

## 8. Illustrations, never rules

- **The cast** (three named agents, a group chat as the re-hook): one product's story. The rule is a re-hook plus an
  escalated second proof (§ 2.1).
- **The premise object** (an agent with its own phone number, so the proof was the phone ringing mid-sentence): that
  video's premise. The rule is an early on-camera proof, if one was filmed.
- **The benchmark's slot order and shares:** one brief's arc, the fallback map only (§ 2).
- **The earlier short's cold-open call:** the illustration behind § 2.5. The benchmark's arc is claim-first; neither is
  the default over a brief.
- **The contrast's alternative** (a coding tool): that video's contrast. The rule is § 4.5.
- **The CTA shot list** (a template page, a setup video, then the comment thread): those deliverables.
  [`captures.md`](captures.md#9-cta-captures) and [`graphics.md`](graphics.md) own the pattern.
- **The kill rate** (about 81 %): an outcome of two to nine takes per beat, never a target.
- **The about-70 s target, the 120 s runtime, the 22 segments and the slot shares:** a reference reel's length and
  one cut's calibration, never quotas.
- **The ad line** ("click the link below"): a sponsor deliverable made on request
  ([README § Deliverables](README.md#deliverables)).
- **The keyword that shipped:** the rule is how a keyword is picked (§ 4.10), not the word.
- **The J-cut at the promise:** seen once (§ 5.3).
- **"No sign-off filmed":** a gap in that raw. A filmed closer is content.
- **The second short's arc** (2026-10-15): a proof hook (your revenue), a promise, the niche, the platform, the offer,
  your documents, the price, the steps, the payments, the claim, the ask, with a mid-video comment ask: a how-to's own
  map, the brief's. Its three cut lines are § 4.15's examples, not a list to grep for.

## Values

Seconds unless the name says frames; `*_SHARE` is a fraction of the final runtime; `a-b` is a range. Joins are tail
plus next lead on the aligner's word edges (§ 5.1). `PROOF_BY_SHARE` and `REHOOK_NEAR_SHARE` are reference lines for
the step-2 report (§ 2.2, § 2.3), never kill triggers.

```values
JOIN_RUN_MAX_S 0.150
JOIN_CLAIM_DEMO_MAX_S 0.280
JOIN_LANDED_S 0.280-0.390
PROOF_BY_SHARE 0.20
REHOOK_NEAR_SHARE 0.50
JCUT_FRAMES 2
LONG_SHOT_FLAG_S 10
TAIL_PAUSE_MIN_S 0.200
```
