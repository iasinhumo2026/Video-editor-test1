# Captures: the real screens that prove it

The real-screen half of this format's graphic panel: what gets recorded, how the source is laid out before the take,
how a shot is framed and moves, and when a capture is READ flat or FELT as a montage. `graphics-plan` reads it at 5a
whenever a line names a product, an app, an agent or a result; `graphics-build` reads it at 5b when the take is recorded
and the scene is emitted through the [kit](kit/engine.py).

**What this doc does not restate.** The universal capture machinery has one home each: the `capture` cell, `shows`,
readiness, `bounds`, `pii.json`, the pre-take gate and the take sweeps are
[`graphics-plan` § THE CAPTURE GATE](../../../.claude/skills/graphics-plan/SKILL.md#step-3--storyboard-the-graphics-the-creative-core);
the recording tools, the mid-frame read against `shows` and the render-base copy are
[`graphics-build` § Stage 2](../../../.claude/skills/graphics-build/SKILL.md#stage-2--assets). The finish each picture
family carries (glow, scan lines) and the authored scenes around a capture are [`graphics.md`](graphics.md); the panel,
the bands, the caption band and the layout letters (S split, F full frame) are [`layout.md`](layout.md); where the caption
breaks is [`captions-style.md`](captions-style.md); what a capture sounds like (the shutter on its cut, the typing, the
send) is [`sfx.md`](sfx.md).

**The thesis.** On this format the capture IS the proof. The creator's niche is real, deployed systems, so a claim is
credible only when the viewer sees the product doing it at the moment you say it, readable on a phone in one glance.
Every rule below serves one of two jobs: make it REAL (the actual thing, happening, with its own motion) and make it READ
(whole, centred, big, one screen). A capture that is real but unreadable failed; a capture that reads but is staged
failed harder.

## 1. Act as the film studio

**When the script names a product, an app action, an agent or a result, the graphic is a fresh, real capture of exactly
that (2026-09-20: "think of yourself like a whole film studio on this computer").** Set up what the script
describes (the agent, the board, the workspace), send the real prompts, let the real reply land, drop the item onto the
board, click the thing that draws the chart, and record all of it as it happens. An older job's recording, stock footage
or a mocked-up UI never stands in: a staged screen undercuts the whole premise. Confirm each real send or call on your
accounts with you first; every side effect is your to see and undo, so list what the take created and how to undo it.

**Real means HIS.** When the line is about something you made or did (your doc, your site, your checkout, your payment
link, your call, your dashboard, your revenue), the capture is your own, on your account, never a random example of the kind:
another creator's site, a generic checkout or a template page proves nothing about you (2026-10-15: "G11 is bad.
I don't want to use that one because it's a random other website"; "use the actual website that we're cooking up right
now"; "the actual Google Doc"). When it does not exist yet, it is made for real first
([`README.md`](README.md#working-with-the-creator)).

**The route to the real thing, in order; take the first that works and name any fallback in the report:**

1. **Inside accounts you already has, with your go:** build the agent or the workspace there and film it. Creating an
   account, signing in, and anything that takes a credential or a payment is your to do: ask, and continue once it exists.
2. **Your own recording of the named moment**, when it is a product Claude cannot operate (someone else's tool, a paid
   tier, hardware, a login you have not opened): ask for it with the § 2 layout spec attached (the window size and zoom, or
   the phone route, and the rectangle that must be whole), so it arrives laid out for the panel.
3. **The product's public page or official demo**, captured as itself. It proves the product does it, not that your
   system does, and the cell says which.
4. **An authored enactment**, flagged in the cell as illustration and built to [`graphics.md`](graphics.md), never styled
   as a real screen (below), except a rebuild in a real product's own skin that shows only your words and the amounts you
   says (your prompt in the AI's composer, your payments as the platform's notifications: [`graphics.md`](graphics.md) § 2).

**On this format a live chat with the product IS evidence.** The house gate says text is never captured, because a
screenshot of words gets none of the graphic's type, highlights or readable hold. The exception here is deliberate: the
product's own reply landing on screen, in its own app, is the proof that it works, and no rebuilt card can prove that.
The gate still holds for words shown only as words: a quote, a command or a prompt the line merely cites is rebuilt as a
graphic from its written source.

**Whatever is typed into a filmed chat is on screen, and a live agent acts on it.** Pre-roll the chat only with questions
whose answers are public facts, or bare acknowledgements, until everything staged or sensitive has left the WINDOW (not
just the crop); never type a stage direction, a rule or an actionable sentence (keep, watch, send, set, remind, schedule,
post, add) into a chat that is filmed. One filler line made an agent create a real recurring routine on your account. Read
the replies for side effects after the take; the sweep machinery is the capture gate's.

**Authored illustration is for ideas with no screen, and it never invents evidence** (no fake business names, times or
figures on a thing styled as real). When the capture cannot show the modality the line claims ("he calls me" over a text
thread), an authored element for that modality (an incoming-call card, [`graphics.md`](graphics.md)) lands over the
capture on that word.

## 2. Lay the source out for the panel BEFORE the take

**"Resize the window" always means a layout change, never a crop of a default page (2026-09-21; 2026-09-23: "I
literally said, size it, get it right", after you had to send your own screenshot of the framing).** Text reads on a phone
only if it was laid out for a phone. A default desktop window cropped or zoomed afterwards came out small, clipped and
off-centre every time. Derive the setup per source; never carry one app's numbers to another.

- **A desktop chat app:** raise the app's zoom and narrow the window until the sidebar collapses and the content is one
  phone-width column, with text about caption size once the column fills the 1080 frame (`TEXT_PX`). Size the window
  for the take through the capture gate's `bounds`.
- **A web page:** either record at the band's own shape headlessly (`workflows/page-record.mjs` with `--width`,
  `--height` and `--scale` set to the panel's aspect), or resize the browser until the page's OWN responsive layout
  composes the shot (a player, its title and its channel row in one column), then crop that composed block.
- **A page that changes under automation** (a fallback button after a failed app handoff): take a still at 3x with a
  normal desktop user agent, grabbed before the fallback appears. The CTA shows what the viewer gets when they click, so
  capture the state a real viewer sees; prefer a still when the page will not hold its state.
- **A page visible only on your account:** record it in your signed-in browser, in a tab of its own (the account chosen by
  URL, never by switching your session), cropped to the subject; then restore your window size and your active tab.
- **A document you wrote** (a Google Doc offer sheet, a script): in a window of its own, never your main window, sized so
  the page column fills the panel at a readable size. The shot is a slow scroll from the title to the part the line is
  about, stopping before anything the line does not show (a price, a client name), panned on a sine ease by the kit
  template's `doc_scroll` recipe. The HOW (the window, the stepped scroll stitched into one tall page) is
  [`graphics-build` § Stage 2](../../../.claude/skills/graphics-build/SKILL.md#stage-2--assets).
- **A site you built:** reload it inside the take, so its own load animation plays in the shot; never cut in on a
  half-loaded page.
- **A page in its dark mode wherever the product ships one** (2026-10-15: you asked whether the brand page could
  be dark, and re-sent the checkout take because it had come out light: "pretty sure that you just recorded light mode,
  but try again"). Dark pages sit in the format's dark world beside the authored scenes; a page with no dark mode stays
  light (§ 8).
- **A page with something floating over it that is not your to close** (a meeting recorder's widget, a dictation bar):
  that window alone, as a still, nothing fronted or moved ([`graphics-build` § Stage 2](../../../.claude/skills/graphics-build/SKILL.md#stage-2--assets)).
- **A phone's own screen** (a text or a call landing on your phone): mirror the phone to the Mac and record the mirror
  window as an `app` capture (macOS iPhone Mirroring), or record the phone over USB in QuickTime Player (New Movie
  Recording, the phone as the camera). Neither is proven on this format yet: take a short test first and read a frame.
  The phone is already a portrait column, so frame the thread's rectangle (§ 3) and crop the status bar off; the phone is
  silenced before the take so no banner lands in it. A thread shows numbers: the other side's in the header, your own
  wherever a message carries it. Crop or mask both in the asset FILE (§ 11), and list both in the job's `pii.json` as
  `needles` with `any_number` set, so the capture gate's checks hold the take to them.

## 3. Frame by the rectangle that must be whole

**Name the source rectangle that must be fully on screen (the whole reply, the whole card, two whole columns) and let
the kit's `fit()` derive zoom and focus inside the panel's content zone. Never hand-type a zoom (2026-09-21: the
first captures were "cut off, not centred, not readable").** A hand-typed zoom clipped bubbles and pushed the input bar
off the bottom; a named rectangle cannot be clipped by construction.

- **Margins, by what the rectangle is:** a page `FIT_PAGE`, a video on its watch page `FIT_VIDEO`, a still list or
  sidebar `FIT_LIST`, a board `FIT_BOARD`, a montage macro `FIT_MONTAGE` (the screen is meant to run off the edges).
- **Readable means text at about `TEXT_PX` on the 1080 frame**, never under `TEXT_FLOOR` even on the tallest reply.
  Captions are the size reference: a capture's text sits just under caption size.
- **Frame edges fall in gutters, never through a card, an icon or a line of text.** Measure the gaps off the take (a
  board's card rows, a list's row boundaries); never estimate them. Estimated rows put the caption on card text twice
  before a measured framing worked.
- **When unsure: bigger, more centred, tighter.** That is exactly what you did when you fixed one capture by hand
  (2026-09-22: "bigger, more centred, cropped better"), and every framing note on the second short asked for more of the
  panel, never less (2026-10-15: "zoom in more"; "make the whole graphic bigger"; "expanded a little bit so it takes up
  more of the screen"; "have that phone section take up the whole screen"). Frame the key rectangle at the largest size
  that keeps it whole in the zone, and let the rest of the page run off the panel's edges. A platform's own phone preview
  of a page (a checkout's mobile view, the device in its hand) is often the biggest readable frame of a price: fill the
  panel with the device, not the desktop page around it.
- **Anything half-visible is a defect:** a numbered list that starts at item 2, a sliced title bar, an icon sliver at the
  edge. The one allowed partial element is the oldest chat bubble scrolling under the pinned header's fade, because that
  is how the app itself looks.

## 4. One screen

**A capture scene has no backdrop: the whole panel is the capture's own background colour, so the top half reads as one
screen (2026-09-21: "the top half should just be one cohesive scene that's all the same color").** A capture
floating on the house backdrop reads as two things stacked. No grid, glow backdrop, vignette, seam gradient, rim, drop
shadow, corner radius or colour filter; the house backdrop belongs to authored scenes only ([`graphics.md`](graphics.md)).

- **The page fills the panel, edge to edge and down to the seam (2026-10-15: "the graphics are cropped when they
  should realistically take up the whole screen... or the background color needs to at least match").** Frame the key
  rectangle whole in y200-845 as § 3 says, then let the page itself run on to the panel's top, its sides and its
  bottom: under the caption box, to the seam. Choose that rectangle (a column of a grid, the hero under its nav, the
  zoomed state of a take) so it covers the panel at a readable size; a strip of page on a flat band reads as cropped.
- **The caption box goes over the page; the page is never cut, banded or faded short to make room for it** (2026-10-15: "why can we just have the screen recording meet up cleanly with the bottom edge... That's why we have the
  background behind the captions. They should be readable even if we let it overlap with the graphics"; again for a
  phone, "we don't need to crop to make room for the captions"). The box is 90 % black, so the line reads over any page.
  What must be READ stays in the zone above the box (§ 3); what runs under it is page. The cell carries
  `"under_caption": true` (what it changes in the QA gate: [`layout.md`](layout.md) § 12; in the kit's recipes:
  [`graphics.md`](graphics.md) § 15 4b); authored ink in the band still fails. A chat keeps its own floor (§ 6) and a
  montage plane its own end (§ 7): those are composed rows, not a page running on.
- **Where a crop must cut** (a nav, another product's name, a claim kept out), that edge is feathered into the fill,
  sampled off the page's own edge on a rendered frame (`K.sample_fill`), so the panel reads as the page continuing. On a SCROLL (a `from`/`to` pan down a
  page) never raise the source crop to clear something: a crop row chosen off one framing rides up the panel as it pans,
  and the page goes blank under it (a doc white below its third heading, 2026-10-15).
- **Every shot of a multi-shot scene gets its own fill** (2026-10-15: a checkout on a websites page's black read
  as a mismatch): the shot's own `bg` in the kit, sampled off a rendered frame, which lays one full-panel layer per
  distinct fill under the windows and switches it on the cut frame (§ 12). Never hand-rolled layers; a montage keeps its
  one in-plane fill (§ 7).
- **Sample the fill off a RENDERED frame, never the source file (2026-09-22: the board's "color on the background
  does not match").** A pin before hyperframes 0.8.81 renders video captures 11-13 levels darker on dark greys
  (0.8.105 renders within 1-3; PNG stills never shift); the rendered frame is right on every pin.
- **An uneven page edge** (an ambient glow off a player, a gradient) is feathered `FEATHER` px into the fill.
- **Crop edges are clean:** trim the window's own border, the sidebar rail's separator column and the rounded-corner
  arcs. A 2 px hairline where the capture meets its fill reads as a sloppy crop at phone size, and only program frames
  show it.

## 5. Natural movement

**The app's own motion is the proof that it is live; never cut between its states (2026-09-21: "show the natural
movement, don't cut"; 2026-09-22: "it should be one smooth recording").** Jump cuts and re-crops between message states
look edited, change the card's size and flashed old history for a frame or two at the joins.

- **Typing, the send and each reply land inside the shot with the app's own animation, at 1x.** Only dead waits are
  fast-forwarded, and only across frames proven static (a composing avatar is the only thing allowed to move there).
- **A reframe at a landing is a camera drift**, `LANDING_DRIFT_FRAMES` frames on a fast-out ease (`power2.out`), in step
  with the app's own scroll; the history mask slides with it over at most `MASK_MAX_S`, so the bubble sliding up is
  never clipped (a linear mask lagged it by about 5 frames).
- **A conversation that owns the frame** (several messages landing in a row, usually a full-frame payoff) is ONE
  continuous take at a FIXED frame, chosen so the END state fits whole, with only a slow push (at most
  `CONTINUOUS_PUSH_MAX`). The app scrolls, the camera does not, and the chat grows upward exactly as it does in the app.
  The mask over older history tracks a fixed row the app draws (a date divider) frame by frame. Reference numbers for its
  time remap (no repo tool yet): 1x from 34 frames before a landing to 8
  frames after it (about 1.4 s and 0.33 s at 23.976), fast-forward only where under about 0.1 % of the take frame's
  pixels change from one frame to the next (a jump point counts as static under about 0.13 %).
- **Every landing keeps its word:** retiming a take never moves a landing off the word it was placed on, so the sounds
  already cut to those frames stay in sync.
- **One scoped exception to "don't cut": a stretch of HIS OWN input that the line has moved past** (you filling in a
  form field the line skips): fast-forwarded when it is static, otherwise ONE silent cut inside the take on a phrase
  start (no shutter: it is the same screen), the caption breaking on it, named in the report (2026-10-15, on a
  checkout being filled in: "cut the in-between"). The app's own responses (a reply, a load, a result) still play
  whole at 1x.
- **A zoom onto a figure or a field is rendered, never an app's auto zoom.** It starts within the first frames of the
  shot, runs fast, goes STRAIGHT to its target (the target's centre on a straight line to the zone
  centre, the scale growing at an even rate on one ease) and is motion-blurred, then holds still (2026-10-15:
  "faster and start almost immediately"; "not smooth at all"; "zooming to the right and then to the left... just zoom
  straight to the point"). An app's own zoom swings and a sped-up one jumps, so the take is exported with no zoom and
  the push is rendered by `workflows/zoom-to-rect.py` off the figure's rectangle (§ 3), the HOW in
  [`graphics-build` § Stage 2](../../../.claude/skills/graphics-build/SKILL.md#stage-2--assets).
- **An agent's or a cursor's long action is ONE continuous shot, no cuts between framings, moving at most by the slow
  continuous push above** (`CONTINUOUS_PUSH_MAX`) on a sine ease, wide enough that the whole page stays readable, starting after the app's own chrome has
  settled (a browser's "is being controlled" bar landing) so the page never jumps (2026-10-15: "a little wider
  out... it doesn't look that smooth"). Cuts between framings of one action read as a camera hunting.

## 6. Chat framing

The shot follows what the line is about, one beat at a time. **One framing plus a reveal per beat:** several reframings
inside a 3-4 s slot read as a camera hunting.

- **Two numbers at the bottom of a chat, never one.** The window's plain bottom EDGE (its border, the fill under the
  input bar) docks at `DOCK_SPLIT` y880 on split. Its CONTENT (the input bar's text, every bubble, the reply) stays on
  the split content floor y845, 75 px above the seam caption's box ([`layout.md`](layout.md) § 8). The kit holds both:
  `thread()` fits the reply's last row to the floor at the shot's LAST push (the drift's 1.008, so the drift still moves)
  and `chat_ok()` refuses one past it (an ink run to y880-886 crowded
  the caption). On F both are the zone's bottom, 20 px above the full-frame caption box.
- **While typing and sending, dock the window:** the chat column fills the panel width, the window's bottom edge at
  `DOCK_SPLIT` on split so the input bar and send button sit whole, ending about y840, clear of the seam caption. On F
  the window bottom sits above the full-frame caption box ([`layout.md`](layout.md) places it).
- **Once the reply lands, frame it whole** under the pinned header. The input bar may leave; the crop ends just under the
  reply, so the bot's trailing avatar or "thinking" row never sits on the caption band. A short reply that fits with the
  input bar stays docked. Never shrink a long reply off-centre to fit everything: crop tighter and drop what does not
  belong to this beat.
- **Reply-only reveal**, for a line about what came back rather than what was asked (2026-09-22: "just her sending
  me the scripts, and way smoother"; the app's one-frame landing "pops in"): a fixed frame (the final reply framing from
  the first frame, a slow push), the chat empty under the header, and the real bubble lifted off a settled frame of the
  take slides up `REVEAL_DY` px to 0 with opacity 0 to 1 over `REVEAL_S` on `power3.out`, starting `REVEAL_AT_FRAMES`
  frames after the cut, inside the window so it rides the push. No replay of your prompt, no zoom-out to fit a long reply.
- **Open on the exchange the line is about.** Older history is masked in the chat's own colour, INSIDE the window, riding
  the scroll. Unrelated history mislabels the shot, and once it pre-showed a later scene's payoff: the viewer's first look
  at a group chat was the tail of a different conversation. No sweep catches that; reading the scenes in reel order does.
- **Pin the app's real header** when the column crop removes it: a `HDR_SRC` px source crop (a shorter one shaved the
  avatar) shown as an `HDR_PX` px bar with its top at `HDR_TOP_SPLIT` on split and `HDR_TOP_FULL` on F, a `HDR_FADE` px
  fade under it, and the chat scrolling beneath. The app's own avatar and name answer "who is this?"; no invented name
  cards, no enlarged name labels. A list or a page gets no header.
- **Timing, measured, never assumed:** typing is visible within `TYPING_WITHIN_S` of the scene opening (never an empty
  chat), the fully typed prompt holds long enough to read, the send lands on its verb, and the reply lands about
  `REPLY_AFTER_S` after the word it answers. Run `uv run workflows/change-events.py <take>` on the take before placing
  anything, and `--sync` on the placed renders against the plan's `sync` anchors (a designed lag is an `offset`). A clock
  0.9 s off made every scene feel wrong and passed every framing check until picture was compared to words.

## 7. Read vs feel

**The fork for every capture: is the viewer meant to READ it or to FEEL it? (2026-09-22 and 2026-09-23.)**
Readability wins when the content is the point; energy wins when the content is atmosphere. You corrected both directions
on the same video.

**READ** (a reply, a page, a deliverable): flat, whole, centred, straight on. The push depends on what the capture is:
a chat drifts through `CHAT_PUSH_SHOT` shot by shot (0.3-1.8 % a shot), never past `DRIFT_MAX` over the scene; a still
with no motion of its own (a list, a sidebar, a board) takes a slow push between its two fit margins so it is not a
frozen frame; a page, a brand card and a CTA capture hold their fit, push 0, except the rendered zoom onto a figure the
line names and a document's scroll (§ 5). Only the flat capture finish
([`graphics.md`](graphics.md)).

**FEEL** (a line about ongoing activity: "he's constantly monitoring...", "she's constantly checking..."): the montage.
A spoken list of activities is abstract; the real screens prove the agent does it, and the fast cuts lift the pace
mid-demo.

- **The cut lands on the first word of the activity clause** (its "so", its "he's"), or at the latest on its first
  activity verb when the shot before still needs its read time (a typed prompt that has not yet held long enough to
  read). The caption breaks on that same frame ([`captions-style.md`](captions-style.md); 2026-09-22:
  "break up the captions like 'he's constantly' and then let's cut there"; for the next clause, "start on 'so'").
- **The shots follow the clause:** macro close-ups of the real screens it names, in spoken order, each `MONTAGE_SHOT_S`
  long, so the clause's length sets the count and each named item is on screen while it is spoken. That usually comes out
  at `MONTAGE_SHOTS`: a clause naming one or two things gets several close-ups of different parts of those screens; a
  clause naming more gets one shot per item, and two items on one screen share a shot rather than cut shorter than
  `MONTAGE_SHOT_S`'s floor.
- **The first shot is the first named item's screen from the cut**, even when its noun lands later; if the noun is more
  than `MONTAGE_SHOT_S`'s ceiling away, split the wait into two close-ups of that screen, never a filler from elsewhere.
- **A named item that may not be shown** (§ 11: a revenue or churn figure) becomes the nearest showable screen of the
  same product (the dashboard's other metrics, the forbidden card cut out of the FILE), or is dropped with the previous
  shot held through its words.
- Each shot is one full flat screen, cut off at the edges (2026-09-22: "one big flat screen, super zoomed-in
  close-ups, things can be cut off"). Cropping is the point here; nobody reads it whole.
- The plane tilts `MONTAGE_RX` degrees in x and `MONTAGE_RY` in y, the y sign alternating shot to shot, swings
  `MONTAGE_SWING` degrees linear across the shot, under a `PERSPECTIVE` px perspective, and pushes 1.00 to
  `MONTAGE_PUSH` linear.
- The fill is part of the plane, padded `PLANE_PAD` px inside it, so wherever the crop does not reach the screen just
  continues (2026-09-22: "the background should be part of the 3D movement"). Scan lines are drawn IN the plane
  at `INPLANE_SCAN`, period 6 px divided by the shot's mean zoom, so they rotate and foreshorten with it; a notch more
  glow than a flat capture (the montage finish, [`graphics.md`](graphics.md)).
- No depth-of-field band, no vignette, no rim.
- Every plane ends above the caption band, so the seam caption sits on plain fill ([`layout.md`](layout.md)).
- The last shot carries real UI motion if the take has any (a click that draws a chart).
- Then return to the chat for the line that names the concrete output.

## 8. Brand page

**A line that introduces a company gets its site's hero, static from the cut, with the official lockup big above it
(2026-09-22: a pop and a push "zooms in and looks corny").** No push, no pop: on this format the cut is a static
page's or a brand's entrance, and this section is that rule's one home.

- Crop the site's own nav off: the small nav wordmark under a big lockup is a duplicate.
- The official lockup (icon plus wordmark), big and centred above the hero: about a 205 px icon beside a wordmark about
  104 px tall in frame px (a capture scene is not scaled), re-sized by eye per brand. Big enough to register the brand in a glance, never dominating the
  page.
- **Big, and composed as one stack:** the lockup sits close above the hero it names, the pair centred in the zone, the
  hero as big as the zone allows; the fill matched exactly where the crop meets the page (2026-10-15: "make the
  whole graphic bigger", the lockup "a little bit downwards, so it's closer to the bottom stuff", the background "more
  like off-white"). A lockup floating at the top of the zone with air under it reads as two things.
- **A page with no dark mode stays light.** Forcing a dark theme onto a page that does not ship one renders it wrong;
  say so and keep the real page (you asked "if not, it's fine").
- The page's own motion (a rotating headline word) is the only movement: choose the in-point so it happens INSIDE the
  shot. A shot shortened to fall between two headline swaps looked frozen. The kit's `brand_page` measures that motion
  on the hero it keeps and takes the first change the shot holds whole, about a third of the way in and after the
  page has sat at rest for at least a sixth of the shot (`page_in`): the page loading in at the take's head is never
  the in-point (2026-10-14: it pushed the headline swap out of the shot).

## 9. CTA captures

**Each promise in the ask gets the REAL thing on the words that name it, and it is shot for recognition, not style
(2026-09-23: "you don't need to do the 3D... just a clear shot of the whole template").** The shot's only job is
that the viewer recognises exactly what they are getting; drawn stand-ins for a template or a video were replaced.

- The real page, or the real video on its watch page playing from the chapter that matches the promise, with its title
  and channel row.
- Flat, static, whole: `FIT_PAGE` for a page, `FIT_VIDEO` for a video; the standard capture finish only. No tilt, no
  push, no in-plane scan, no montage treatment.
- Resize the window until the page's own layout fits the band (§ 2); never crop a player out of a default-width page.
- Links come from the brief; else from the published piece the promise names (its own description lists what the DM
  delivers; the platform's creator dashboard when it is unlisted or scheduled); else ask you. The promise and the shot
  must point at the same asset the DM will deliver, so a link is never guessed.
- Owner-only chrome stays out (a visibility label, analytics or edit buttons, revenue). Record a video once it is
  public; a scheduled one shows owner chrome.

## 10. Glitches

- **A glitch in the featured area** (a tooltip or hover state flashing over the thing the line is about) becomes a held
  clean frame of the same take, and the camera move carries the motion so it never reads as a freeze (2026-09-22:
  a pop-up is "not smooth and clear").
- **Normal app behaviour is never painted out** (the next agent's composing avatar, a count that refreshes late): reframe,
  trim a frame, or leave it and flag it by name. A doctored capture is no longer evidence ("document, don't manufacture").

## 11. Privacy and staging on this format

The universal machinery stays where it lives and is not restated: `pii.json`, the pre-take gate and the take and draft
sweeps are [`graphics-plan` § THE CAPTURE GATE](../../../.claude/skills/graphics-plan/SKILL.md#step-3--storyboard-the-graphics-the-creative-core),
the recording tools are [`graphics-build` § Stage 2](../../../.claude/skills/graphics-build/SKILL.md#stage-2--assets),
and the step-0 don't-show list is [`edit-video` § Step 0](../../../.claude/skills/edit-video/SKILL.md#step-0--resolve-the-job-before-step-1),
item 9. This format adds:

- **A screen held up to the camera is on the step-0 list from the start.** Item 9 already has a held-up screen
  checked by eye; on this format that is the norm, not the exception: the product is held up to the lens (a phone
  showing an agent's number, a laptop), so the camera footage is a screen recording too, and it is read frame by frame
  like a capture take. On the job this preset came from, a held-up phone was found only on the last lap.
- **Crop a sensitive region out of the asset FILE, not the camera.** A montage tilt, a push or a crop change reveals what
  is only framed out. Trim OS dialogs from the take; delete full-window grabs once the crops exist. Revenue, recurring
  revenue, churn, calendar and inbox contents, credentials, call ids, sign-in cards and platform notices never show
  (2026-09-23: "I don't want to show anything crazy, like the MRR"). A number the story needs is authored,
  masked ([`graphics.md`](graphics.md) owns it). The one exception is a figure that IS the video's own claim and that you
  asks to show (your lifetime revenue in a proof hook, 2026-10-14: "show the whole page and then zoom in to the number"):
  that figure is the point, the page shows only as far as you asked, and the rest of it is read at phone size for
  anything else you would not want out (an account name, another income line) before it ships.
- **A dirty capture take is re-shot, not patched:** clean the window and take it again, and rename and remove the dirty
  take from the render base (§ 12). A patched take is doctored footage, and a patch on a moving take is one missed frame
  from shipping the thing. Only your camera footage, which cannot be re-shot, gets a patch (below).
- **The sensitive string is written nowhere but the job's `pii.json`,** which the sweeps need: never in chat, RUN.md, a
  sweep log, a commit message or a file name. Locate it by timecode and frame coordinates.
- **Every sweep is proven on a known-bad frame first** (the dirty take, or a control word that is on screen) before its
  clean is believed. Several checks on the job this came from said clean while blind on their first run.
- **A sensitive detail on a moving object in your footage gets a TRACKED blur** of only the sensitive row, cut from the
  graded, reframed program so framing and colour match by construction (2026-09-22: "blur it"). A static box does
  not follow a phone swinging in and out. Any reframe, regrade or recut over that span makes the patch stale: rebuild it
  under a new filename. Every draft exported before the blur is quarantined, never shared. The lanes' region-blur
  tools cover a still region of screen-recording media ([`LANES.md`](../../../LANES.md) § step 5), never a tracked patch
  on reframed, graded camera footage. Until a repo tool exists, the patch is rebuilt from this recipe (the one you
  approved):

  ```text
  track    SIFT features + a RANSAC homography of the object's screen, from its steadiest frame outward
  blur     Gaussian, sigma 12 px on the 1080-wide frame, inside the tracked quad only
  mask     the quad dilated 14 px (26 px on the fast entry and exit frames), 4 px feather
  source   the graded, reframed program over those frames, never the raw
  output   straight-alpha ProRes 4444 at the timeline rate, only as long as the affected frames
  lay      its own track, above the graphics and below the captions
  prove    program vs an offline composite over the span (mean abs diff about 2/255 on the job);
           the frame-stack attack below, run on the blurred result, returns a smooth blob
  ```

- **A third party in your footage is anonymized WHOLE, and the footage keeps its frame.** On a recorded call (a sales
  call, a testimonial), the other person's entire tile is mosaicked, face, name label and background together, never the
  face alone, and the call's full frame is kept, never cropped to your tile to dodge it (2026-10-15: "if he sees it,
  he might be like, that's too easily recognizable as me... blur the whole square... keep the frame as is"). The clip's
  own audio is dropped under your voice. Recognisable is judged as the person themself would judge it, not as a stranger
  would. A framing change inside a call clip that traces to the call app re-tiling (a participant leaves, a 5-up gallery
  becomes a 2x2) is in the recording: say so in one line and keep the full frame like the rest of the set; any crop or
  reframe of a call clip needs your yes first (2026-10-15, rejecting a speaker-tile crop: "just keep it like
  regular default framing where you can see all the people").
- **The take's screen is clean before the take:** notifications off, floating widgets (a dictation bar, a meeting
  recorder) moved off the recorded region, the window your take needs fronted on its own display. A take a banner or a
  widget landed in is re-taken, never patched (twice on 2026-10-15). A page that does not need your session (a public
  checkout link) is recorded in a private window, so your signed-in account (your email in a corner) is not on it: a take in
  a new window of your main profile showed it once.
- **Engagement-type numbers** (a percentage on a dashboard, a public count) may appear, flagged to you once.
- **A private artifact the demo needs becomes a same-shape placeholder** (a morning brief, an inbox), read word for word,
  listed at handoff with any third party's real data that is on screen.
- **OCR reading nothing is not a safety test** (item 9 says the same of a clean sweep). The verdict is two-part, on the
  file viewers get: a casual viewer at phone size, and a determined one who steps frames, stacks, aligns and deconvolves
  them (that partly recovered a number OCR read as nothing on every variant). Recommend by what the data would unlock;
  the call is yours.

## 12. Render base

- **Capture copies used for rendering are re-encoded all-intra,** staged by `kit/engine.py stage projects/<job> <id>
  <take>` ([`graphics.md`](graphics.md) § 15 step 2), so every seek lands on a keyframe; the original is kept at
  `assets/captures/<id>.<ext>`. Long-GOP captures starved the renderer on seeks (blank frames, aborted renders).
- **Joins inside a capture scene are the kit's:** an incoming clip pre-rolls hidden (at most `PREROLL_MAX_FRAMES`), and
  the outgoing shot is hidden ON the cut frame, never held under the incoming, so every frame shows exactly one shot.
  Never re-author those by hand. A shot's own fill (its `bg`, § 4) is the kit's too: its layer switches on that
  same frame, so no frame shows a page on another page's colour; a job never hand-rolls fill layers through
  `extra_html`/`extra_js`. WHY: a held outgoing frame showed the old page round an incoming window smaller than the
  panel, a flash-scan DOUBLE CUT on a final export (2026-10-15); the renderer pre-extracts every frame, so a clip draws
  on its first frame with no hold. Regression: `workflows/test_talking_head_kit.py` (Capture).
- **Rejected media is removed from the render base, not just noted.** A note is not a guard; a rejected take left in the
  base is one path edit from shipping. `stage` never overwrites, so the rejected take is moved aside by hand first
  ([`graphics.md`](graphics.md) § 15 step 2).

## 13. Illustrations only (never rules)

These were right for one video's screens; the rule each illustrates is in the section named.

- The window sizes and zooms (an 820x1040 pt window at about 176 % for one desktop chat app; a 1650x1050 pt browser for
  one watch page; a 640x570 @2x viewport for one site's hero): § 2, derive per source.
- Every fill hex (a dark chat at #050505, a watch page at #111113, a dark page at #0a0a0a, a white page at #fefefe): § 4,
  sample the render.
- Every in-point, landing word and montage cut (a send on "checking", a reply after "retention", one montage cut on the
  verb after "he's constantly" and the next on its clause's "so"): § 5-7, "on the word".
- The tracked blur's frame span, coordinates and track data on one hook: baked from that cut's frames, stale after any
  reframe or recut there. Only the recipe in § 11 carries over.
- The montage's per-shot tilt pairs and the screens it used (one creator's community and video dashboards): § 7.
- The lockup's exact size and its y band on one page: § 8, big and re-sized by eye per brand.
- The divider row a continuous take's mask tracked: § 5, the tracked row is whatever the app draws.
- The owner-only label baked into one CTA shot (the video was still scheduled): § 9, record once public.
- The engagement figures that shipped and the placeholder brief: § 11, per-video calls, not defaults.
- The second short's screens (2026-10-15): your Monarch report zoomed onto one figure; your Whop dashboard, checkout and
  Ads pages; your site on a 1000x949 window on display 2; your offer sheet and ad script stitched into tall pages; your
  dark checkout captured as a window still; a Fathom call with the prospect's tile mosaicked in 24x14 blocks. Each is
  that video's; the rules are § 1-5, § 8 and § 11.

## Values

The kit mirrors this block ([`kit/engine.py`](kit/engine.py)); `workflows/test_talking_head_kit.py` holds the two equal.
Pixels are on the 1080x1920 authoring frame except `HDR_SRC` (source px) and `PLANE_PAD` (plane px); `*_S` in
seconds, `*_FRAMES` in timeline frames, angles in degrees, `FIT_*` and pushes as scale factors; `a-b` is a range.

```values
TEXT_PX 36-40
TEXT_FLOOR 31
FIT_PAGE 0.92
FIT_VIDEO 0.96
FIT_LIST 0.82-0.86
FIT_BOARD 0.84-0.87
FIT_MONTAGE 1.00
HDR_SRC 140
HDR_PX 112
HDR_FADE 46
HDR_TOP_SPLIT 200
HDR_TOP_FULL 260
DOCK_SPLIT 880
FEATHER 14
CHAT_PUSH_SHOT 1.003-1.018
DRIFT_MAX 1.02
LANDING_DRIFT_FRAMES 6
MASK_MAX_S 0.17
REVEAL_DY 60
REVEAL_S 0.42
REVEAL_AT_FRAMES 3
PREROLL_MAX_FRAMES 6
TYPING_WITHIN_S 0.3
REPLY_AFTER_S 0.2
MONTAGE_SHOTS 3-4
MONTAGE_SHOT_S 0.6-1.3
MONTAGE_RX 5-9
MONTAGE_RY 10-14
MONTAGE_SWING 2-3
PERSPECTIVE 1500
MONTAGE_PUSH 1.06-1.08
PLANE_PAD 1400
INPLANE_SCAN 0.32
CONTINUOUS_PUSH_MAX 1.015
```
