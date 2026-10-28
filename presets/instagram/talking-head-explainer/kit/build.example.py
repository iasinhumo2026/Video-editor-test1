#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""build.py: this job's graphics on the talking-head explainer look, written as DATA.

`kit/engine.py init projects/<job>` copied this file here from presets/instagram/talking-head-explainer/kit/
build.example.py. From now on it is the JOB'S OWN build.py: a re-run of init never overwrites it.

  uv run hf-graphics/gfx/build.py            # every STORYBOARD entry: its comp and its kit SFX rows, then how to render
  uv run hf-graphics/gfx/build.py g5 g8      # only these

EDIT ONLY THE STORYBOARD section: the job's measured facts and one entry per plan cell. Everything above it is a
COOKBOOK, the same on every job: one recipe per device of this look, grouped by kind, in no reel order. Every recipe is
optional and knows nothing about any video: it is handed its words (phrases said inside its own cell) and its media's
measured facts. Which device a line gets is graphics.md § 3's call (first match wins), never this file's: a video uses
the few recipes its lines earn, and a line none of them fits gets its own scene in the STORYBOARD section, written on
the same pattern (a component call, or K.authored / K.capture). Every recurring number and hygiene rule lives in the
kit (kit/engine.py, kit/components.py) and the WHAT in the preset's docs; comments point at the section that owns a rule.

THE ONE RULE: no timeline second is ever typed. A time is a word (ctx.find, through said(): a miss or an ambiguity
raises) or a plan cell (its start, end, shot_cuts, crown), so a re-cut is a re-run of this file after the steps
story-and-cut.md § 6.1 owns (the live read, the ripple). What IS typed is measured off the job's own
media: a take's size and chat column, the source rectangle a shot must hold whole (captures.md § 3), a fill sampled off
a RENDERED frame (K.sample_fill). A take's own moments (the typing, a send, a reply landing, a page's own motion) are
read by workflows/change-events.py (measured() below), never guessed. All of it is per shoot and never becomes a rule.

Read first: graphics.md § 3 (which graphic a line gets) and § 15 (building with the kit), captures.md (every real
screen), layout.md § 12 (the plan contract the cells follow), sfx.md § 2 (the sounds the kit writes for you).

As shipped the STORYBOARD is empty, and a run lists every plan cell still without an entry. The binding at the very end
belongs to the kit's smoke test: `engine.py smoke` builds a synthetic job (an invented reel about a placeholder
product, "Acme Assistant", its captures placeholders under assets/captures/) and runs this file on it, and only there
does that binding apply. It shows the call shapes and nothing else: its words are that invented script's, and its
cells are whatever the fixture needed to exercise every recipe, so never copy it as a storyboard or an order (2026-09-10: an example illustrates a principle and is never a template).
"""
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

GFX = Path(__file__).resolve().parent                  # projects/<job>/hf-graphics/gfx
sys.path.insert(0, str(GFX / "kit"))
import engine as K        # noqa: E402  the clock and the words, capture geometry, the emitters, write + write_events
import components as C    # noqa: E402  the recurring authored pieces, each timed from words, each carrying its sounds

ctx = K.Ctx(GFX.parent.parent)                         # the plan (its fps is the grid), the canonical words, voices.json
AD = (ctx.plan.get("variants") or {}).get("ad")         # a sponsored piece's second deliverable (README § Deliverables)


# ══ THE KIT'S HELPERS: the same on every job, never edited here ═══════════════════════════════════════════════════
FRAME_OF = {"S": "split", "F": "full"}                 # the panel a graphic fills; O is the overlay's; T and W carry none


def V(key):
    """a graphics.md / captures.md § Values number, read from the kit's mirror (one home)"""
    return float(K.VALUES[key])


def row(r):
    """a layout row, dict or list form (layout.md § 12) -> (start, end, mode, caption_y), resolved by layout.py itself
    (engine.layout_row): an F row's `ui_bottom` gives its line, an F row a seam_clear cell keeps clear stays on the seam"""
    return K.layout_row(r, ctx.plan, (AD or {}).get("cells") or ())


def cell(gid):
    """a plan cell by id: the ad variant's (they replace every cell from its `from`), else the organic plan's"""
    return next((c for c in (AD or {}).get("cells") or [] if c.get("id") == gid), None) or ctx.cell(gid)


def span(gid):
    """(start, end) of a plan cell on the grid: a graphic starts and ends exactly where the plan says (layout.md § 4)"""
    c = cell(gid)
    return K.sn(c["start"]), K.sn(c["end"])


def mode_of(gid, *allowed):
    """(mode, caption_y) of the ONE layout mode under the cell (the ad's own layout for an ad cell). A cell straddling
    two modes, or on a mode its graphic cannot fill, is a plan error caught before a render (a split comp on an F span
    shows the wrong zone)."""
    a, b = span(gid)
    rows = [row(r) for r in (AD["layout"] if AD and cell(gid) in AD.get("cells", []) else ctx.layout)]
    got = {(m, cy) for s, e, m, cy in rows if float(s) < b - 1e-6 and float(e) > a + 1e-6}
    if len(got) != 1 or next(iter(got))[0] not in allowed:
        raise K.BuildError(f"{gid}: the layout under it is {sorted(got, key=str)}; this graphic fills "
                           f"{'/'.join(allowed)} (layout.md § 2): fix the plan's `layout` or the storyboard")
    return next(iter(got))


def said(gid, phrase):
    """A word of this cell's own line: ctx.find inside the cell (its first frame to its end), so a phrase said earlier
    or later in the reel (a callback repeating the pain words) never matches. A (phrase, n) pair takes the n-th hit when
    the line itself says it twice; a miss or an ambiguity inside the cell still raises."""
    p, n = phrase if isinstance(phrase, tuple) else (phrase, None)
    a, b = span(gid)
    return ctx.find(p, nth=n, after=a, before=b)


def lands_on(t, phrase=None, gid=None):
    """A picture change the PLAN placed mid-sentence (a cell's start, a shot cut) lands 0-2 frames before a word's onset
    (layout.md § 4), so the picture, the caption break and the sound arrive with the word. With a phrase, that word;
    without, the next word said (the plan chose it). Returns the Word; anything else is a stale plan after a re-cut."""
    if phrase is not None:
        w = said(gid, phrase) if gid else ctx.find(phrase, after=t - K.fsec(1))
    else:
        nxt = next((x for x in ctx.words if K.frames(x["start"]) >= K.frames(t)), None)
        if nxt is None:
            raise K.BuildError(f"the cut at {t:.3f} has no word after it")
        w = K.Word(nxt["start"], nxt["end"], nxt["text"])
    lead = K.frames(w.start) - K.frames(t)
    if not 0 <= lead <= 2:
        raise K.BuildError(f"the cut at {t:.3f} is {lead} frames before {w.text!r} ({w.start:.3f}), not 0-2: a stale "
                           "plan after a re-cut? Run workflows/ripple-cut.py, then this file")
    return w


def measured(media, region=None, fine=False, whole=False):
    """A take's own change events in MEDIA seconds, in order: [{seconds, end_seconds, magnitude, ...}] from
    workflows/change-events.py on `region` (x, y, w, h, source px), cached beside the take and re-measured when the take
    is newer. fine=True reads typing: a letter is a small change a few frames from the next, so a low threshold and an
    8-frame gap turn the keystrokes into bursts. whole=True returns the tool's whole record (its `frames` and `fps`
    too). Run the tool by hand once to see the list (captures.md § 6)."""
    p = GFX / "assets" / "captures" / media
    out = p.with_name(p.stem + (".%d-%d-%d-%d" % tuple(region) if region else "") + (".fine" if fine else "")
                      + ".events.json")
    if not out.exists() or out.stat().st_mtime < p.stat().st_mtime:
        cmd = ["uv", "run", "-q", str(K.REPO / "workflows" / "change-events.py"), str(p), "--json", str(out)]
        cmd += ["--region", ",".join(str(int(v)) for v in region)] if region else []
        cmd += ["--threshold", "0.5", "--min-gap-frames", "8"] if fine else []
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise K.BuildError(f"change-events.py on {media} failed: {(r.stderr or r.stdout).strip()[-400:]}")
    rec = json.loads(out.read_text(encoding="utf-8"))
    return rec if whole else rec["events"]


def page_in(changes, dur, take_s):
    """The in-point (media s) of a page shot `dur` s long, from the page's measured `changes` and the take's length: the
    shot holds the FIRST change that fits whole inside it, a third of the way in (a headline swap, read as the line is
    said), or as near a third as the take allows but never under a sixth: the page is seen at rest before it moves. A
    change it cannot hold that way is passed over, and the shot never opens inside it: the page loading in at the
    take's head (2026-10-14: taken as the in-point, its fade at 0.04 s opened the shot and left the headline swap out of
    it) and one running past the shot or the take. With none, the first stretch no change crosses (the page at rest);
    with no such stretch either, BuildError."""
    lo = 0.0
    for e in changes:
        t0 = max(lo, e["seconds"] - dur / 3)
        if e["seconds"] - t0 >= dur / 6 and e["end_seconds"] <= t0 + dur - K.fsec(1) and t0 + dur <= take_s:
            return t0
        lo = max(lo, e["end_seconds"] + K.fsec(1))
    for t0 in [0.0] + [e["end_seconds"] + K.fsec(1) for e in changes]:
        if t0 + dur <= take_s and not any(e["seconds"] < t0 + dur and e["end_seconds"] >= t0 for e in changes):
            return t0
    raise K.BuildError(f"no in-point holds a page change whole, or the page at rest, for {dur:.2f} s of the "
                       f"{take_s:.2f} s take (changes at {[round(e['seconds'], 2) for e in changes]}): pass t0= after "
                       "looking at the take, or re-take it longer")


def voice_cut(a, b):
    """The timeline second where the OTHER voice starts inside [a, b): its first span in transcript/voices.json (the
    raw clock, written at step 2) mapped through the EDL. A call is answered on this cut (graphics.md § 3.4)."""
    spans = (ctx.voices or {}).get("spans") or []
    t = 0.0
    for s in json.loads((ctx.job / "transcript" / "cuts.json").read_text(encoding="utf-8"))["segments"]:
        for v in spans:
            same = not v.get("clip") or os.path.basename(v["clip"]) == os.path.basename(s["clip"])
            if same and v["start"] < s["end"] and v["end"] > s["start"]:
                at = K.sn(t + max(v["start"], s["start"]) - s["start"])
                if a <= at < b:
                    return at
        t += s["end"] - s["start"]
    raise K.BuildError(f"no second-voice span of transcript/voices.json starts in {a:.3f}-{b:.3f} (step 2 writes it, "
                       "README § Audio)")


def fit_in(rect, top, bottom, margin=1.0):
    """K.fit() into the band y[top, bottom] of the split zone instead of the whole zone: the SOURCE rect whole and
    centred there, the zoom derived from it (a page under its lockup, captures.md § 8)."""
    x0, y0, x1, y1 = (float(v) for v in rect)
    z = min(K.FRAME_W * margin / (x1 - x0), (bottom - top) * margin / (y1 - y0))
    mid = sum(K.zone("split")) / 2
    return ((x0 + x1) / 2, round((y0 + y1) / 2 - ((top + bottom) / 2 - mid) / z, 1)), round(z, 4)


def pushed(scene):
    """`scene` arriving by the lateral PUSH from the graphic whose last frame it starts on (graphics.md § 13, layout.md
    § 7: split stays split, no face beat before the ask). The push carries that graphic's RENDER, so a first pass cuts
    in and says so: render the one before, then re-run this file for the scene."""
    before = [c["id"] for c in ctx.cells.values() if c.get("graphic") and c.get("kind") != "captions"
              and abs(K.sn(c["end"]) - scene.start) < 1e-4]
    if len(before) != 1:
        raise K.BuildError(f"{scene.id}: no graphic ends on its first frame ({scene.start:.3f}): it pushes in from the "
                           "one before it, never after a gap or a face beat (layout.md § 7)")
    have = sorted((GFX / "renders").glob(f"{before[0]}-alpha*.mov"), key=lambda p: p.stat().st_mtime)
    if not have:
        print(f"  {scene.id}: {before[0]} is not rendered yet, so this pass cuts in; render {before[0]}, then re-run "
              f"`build.py {scene.id}` and it pushes in from that render's last frame")
        return scene
    return C.push(have[-1], scene)


def ad_find(word, after):
    """the first word of the AD's own transcript (outputs/<job>.ad.transcript.json: its ask was recorded for it) at or
    after `after`, as a K.Word; one word, case and punctuation ignored"""
    p = ctx.job / "outputs" / f"{ctx.name}.ad.transcript.json"
    for w in json.loads(p.read_text(encoding="utf-8"))["words"]:
        if w.get("start") is not None and w["start"] >= after - 1e-6 and \
                "".join(ch for ch in w["text"].lower() if ch.isalnum()) == word.lower():
            return K.Word(w["start"], w["end"], w["text"])
    raise K.BuildError(f"{word!r} is not in {p.name} after {after:.3f}")


@dataclass
class Chat:
    """One chat take's measured facts, all in THAT take's source px (captures.md § 6): per shoot, never rules."""
    media: str            # the take, under assets/captures/
    take: object          # K.Take(size, column=...): its size and the chat column (the app's rail cropped off)
    header: str           # the app's real header strip, pinned while the column crop removes it
    fill: str             # the chat's colour AS RENDERED (K.sample_fill)
    input_text: tuple     # x, y, w, h: the input bar's text, where the keystrokes show
    thread: tuple         # x, y, w, h: the thread, between the header and the input bar
    exchange_top: int     # the gap row above the exchange this line is about (older history is masked above it)
    reply_end: int        # the reply's last row: the crop ends just under it
    bubbles_x: tuple      # the source columns every bubble lies in (chat_ok proves them whole)


# ══ THE COOKBOOK: one recipe per device, each optional, in no reel order ═════════════════════════════════════════
# A recipe takes its plan cell's id, the phrases it is timed on (said inside the cell) and its media's facts, and
# returns a Scene. graphics.md § 3 matches a line to a device; the recipe only builds it.

# ── real screens: a capture of the product doing the thing (captures.md) ────────────────────────────────────────
def chat_typing(gid, chat):
    """The prompt typed live (captures.md § 5-6), for a line about what he asks for. The window docked so the input
    bar sits whole above the caption, the header pinned, the keystrokes read off the take's own input bar at 1x: the shot
    opens on the typing (never an empty chat), mid-typing when the prompt outlasts the shot, and the finished prompt
    holds to be read. It ends before the send, which belongs to chat_reply."""
    a, b = span(gid)
    mode, cy = mode_of(gid, "S", "F")
    lay = FRAME_OF[mode]
    sent = measured(chat.media, chat.thread)[0]           # the thread's first change: the sent bubble
    keys = [e for e in measured(chat.media, chat.input_text, fine=True) if e["seconds"] < sent["seconds"] - K.fsec(2)]
    if not keys:
        raise K.BuildError(f"{gid}: change-events sees no typing in {chat.media}'s input bar before the send: check "
                           "chat.input_text against the take")
    typed = (keys[0]["seconds"], keys[-1]["end_seconds"])  # every change in the input text before the send is typing
    t0 = max(0.0, typed[0] - K.fsec(2), typed[1] + 0.5 - (b - a))
    if t0 + (b - a) >= sent["seconds"]:
        raise K.BuildError(f"{gid}: the take sends at {sent['seconds']:.2f} s, inside this shot: re-take with a pause "
                           "before the send, or end the shot earlier")
    return K.capture({
        "id": gid, "start": a, "layout": lay, "caption_y": cy, "bg": chat.fill, "header": {"img": chat.header},
        "shots": [{"media": chat.media, "t0": t0, "dur": b - a, "crop": chat.take.crop(),
                   "from": K.dock(chat.take, 1.0, lay, cy), "to": K.dock(chat.take, 1.003, lay, cy),
                   "events": [{"event": "typing", "media_t": max(t0, typed[0]), "dur": typed[1] - max(t0, typed[0]),
                               "note": "the prompt typed live"}]}]})


def chat_reply(gid, chat, answer):
    """The send and the reply landing (captures.md § 6), for a line that names what came back after the ask was seen.
    The send plays out at 1x; only a dead wait is skipped, over frames change-events proves static; the reply lands
    REPLY_AFTER_S after `answer` (the word it answers) inside a short drift to its whole framing under the pinned header,
    the crop ending under the reply. chat_ok proves at BUILD time that the reply clears the caption and every bubble is
    whole. A line about the reply alone, with no ask worth replaying, is the reply-only reveal instead (captures.md § 6)."""
    a, b = span(gid)
    mode, cy = mode_of(gid, "S", "F")
    lay = FRAME_OF[mode]
    lands_on(a)
    ev = measured(chat.media, chat.thread)
    sent, landed = ev[:2]                                 # the thread's changes, in order: the sent bubble, the reply
    land = K.sn(said(gid, answer) + V("REPLY_AFTER_S"))
    drift = K.fsec(int(V("LANDING_DRIFT_FRAMES")))
    s0 = sent["seconds"] - K.fsec(3)                      # the send lands 3 frames after the cut...
    settle = K.sn(sent["end_seconds"] - s0 + K.fsec(3))   # ...and plays out before any jump
    wait = land - (a + settle)                            # the shot that ends ON the landing
    skip = (s0 + settle, landed["seconds"] - wait)        # the media the jump leaves out: it must be dead
    if wait <= 0 or skip[1] < skip[0]:
        raise K.BuildError(f"{gid}: the take's reply comes too soon for {answer!r}: land it on a later word, or re-take")
    moving = [e for e in ev if skip[0] < e["seconds"] < skip[1]]
    if moving:
        raise K.BuildError(f"{gid}: the jump would skip a change at {moving[0]['seconds']:.2f} s of the take: the app's "
                           "own motion is never cut (a composing avatar may move: measure chat.thread without its row)")
    crop = chat.take.crop(chat.reply_end + 20)

    def frame(push):                                      # the exchange whole under the header, proven by chat_ok;
        # the reply is fitted to the content floor at the drift's LAST push, so frame(1.008) still keeps it
        return K.chat_ok(K.thread(chat.take, chat.exchange_top, push, lay, chat.reply_end + 20, cy, content_src=chat.reply_end,
                                  fit_push=1.008),
                         chat.reply_end,
                         take=chat.take, size=(chat.take.w, chat.reply_end + 20), x_whole=chat.bubbles_x, layout=lay,
                         caption_y=cy)
    dock = [K.dock(chat.take, z, lay, cy) for z in (1.003, 1.004, 1.005)]
    return K.capture({
        "id": gid, "start": a, "layout": lay, "caption_y": cy, "bg": chat.fill, "header": {"img": chat.header},
        "shots": [
            {"media": chat.media, "t0": s0, "dur": settle, "from": dock[0], "to": dock[1], "crop": chat.take.crop(),
             "events": [{"event": "send", "media_t": sent["seconds"], "note": "the prompt sends"}]},
            {"media": chat.media, "t0": landed["seconds"] - wait, "dur": wait, "from": dock[1], "to": dock[2],
             "crop": chat.take.crop()},
            {"media": chat.media, "t0": landed["seconds"], "dur": drift, "from": dock[2], "to": frame(1.0), "crop": crop,
             "hide_above": chat.exchange_top, "ease": "power2.out",
             "events": [{"event": "send", "at": 0, "note": "the reply lands inside the drift"}]},
            {"media": chat.media, "t0": landed["seconds"] + drift, "dur": b - land - drift, "from": frame(1.0),
             "to": frame(1.008), "crop": crop, "hide_above": chat.exchange_top}]})


def montage(gid, screens, fill, items=None):
    """Ongoing background work FELT, not read (graphics.md § 3.2, captures.md § 7): macro close-ups of the real screens
    the clause names, one shot per plan cut (the cell's start, then its `shot_cuts`; the captions run across them).
    screens = [(media, rect, crop)] in spoken order: the macro rect a shot frames and the plane's own section (both
    source px, so each plane ends under its section); a video shot plays its own first change inside the shot. items =
    optional phrases, one per shot after the first, to prove each cut lands on its item's word; without them each cut
    is proven on a word onset. The kit tilts, pushes and pads the fill into the plane."""
    a, b = span(gid)
    mode_of(gid, "S")
    cuts = [a] + [K.sn(t) for t in cell(gid).get("shot_cuts", [])] + [b]
    if len(cuts) != len(screens) + 1:
        raise K.BuildError(f"{gid}: {len(screens)} screens, but the plan cuts {len(cuts) - 1} shots: one per shot")
    if items is not None and len(items) != len(screens) - 1:
        raise K.BuildError(f"{gid}: {len(items)} items for {len(screens) - 1} cuts after the first")
    shots = []
    for i, (media, rect, crop) in enumerate(screens):
        lands_on(cuts[i], items[i - 1] if items and i else None, gid)
        t0 = max(0.0, measured(media)[0]["seconds"] - K.fsec(3)) if media.endswith(K.VIDEO_EXT) else 0.0
        shots.append({"media": media, "t0": t0, "dur": cuts[i + 1] - cuts[i], "rect": rect, "crop": crop})
    return K.capture({"id": gid, "start": a, "layout": "split", "bg": fill, "look": "montage", "readable": False,
                      "follows": "graphic", "shots": shots})


def brand_page(gid, media, marks, hero, fill, on_dark=False, t0=None):
    """Introducing a company (graphics.md § 3.12, captures.md § 8): its site's hero, static from the cut, the site's own
    nav cropped off (hero = the source rect kept), the official lockup (marks = its icon and wordmark files) big above
    it. The page's own motion is the only motion, so the in-point holds its first change whole (page_in, measured on
    the hero the shot keeps: a change outside the crop is never seen); t0 = a media second picked off the take instead.
    on_dark=False keeps a dark wordmark as it is on a white page. Silent by design: a brand page opening from the face
    rides the layout's cut-in alone (sfx.md law 4, ladder rung 2); `camera-under` is the CTA's promised page's."""
    a, b = span(gid)
    mode_of(gid, "S")
    lock = C.brand_lockup(*marks, on_dark=on_dark)
    if t0 is None and media.endswith(K.VIDEO_EXT):
        rec = measured(media, (hero[0], hero[1], hero[2] - hero[0], hero[3] - hero[1]), whole=True)
        t0 = page_in(rec["events"], b - a, rec["frames"] / float(Fraction(rec["fps"])))
    frm = fit_in(hero, lock.row[3] + 40, K.SPLIT_ZONE[1], V("FIT_PAGE"))
    s = K.capture({"id": gid, "start": a, "layout": "split", "bg": fill, **lock.spec(), "shots": [
        {"media": media, "t0": t0 or 0.0, "dur": b - a, "from": frm, "crop": hero}]})
    s.meta["silent"] = "a brand page opening from the face: the layout's cut-in is its sound (sfx.md law 4, rung 2)"
    return s


FROM_FACE = "a page opening from the face: the layout's cut-in is its sound (sfx.md law 4, rung 2)"


def entry(gid):
    """A real page's opening sound: the shutter when it cuts in over the graphic before it (a cut onto a captured page,
    sfx.md § 1); none from the face, where the layout's cut-in is its sound (sfx.md law 4, rung 2)."""
    a, _ = span(gid)
    over = any(c.get("graphic") and c.get("kind") != "captions" and c.get("id") != gid and abs(K.sn(c["end"]) - a) < 1e-4
               for c in list(ctx.cells.values()) + list((AD or {}).get("cells") or []))
    return [{"event": "camera", "at": 0, "note": "the page cuts in over the graphic before it: the shutter"}] if over else []


def framings(sh):
    """Every framing a capture shot passes through, as ((fx, fy), z): its fitted rect, or its from and its to."""
    fr = [K.fit(sh["rect"], "split", sh["margin"])] if "rect" in sh else [sh["from"], sh["to"]]
    return [((float(fx), float(fy)), float(z)) for (fx, fy), z in fr]


def frame_y(sh, y):
    """The frame y each framing of a split shot puts the source row y on."""
    top, bot = K.zone("split")
    return [(top + bot) / 2 + (y - fy) * z for (_, fy), z in framings(sh)]


def clear_band(run):
    """Raise the crop bottom of a run of shots on one window (one shot, or a take skipping its dead waits) until its ink
    ends by SPILL_DISSOLVE_Y on every framing of the run: the page fades into its own fill above the caption band
    (layout.md § 8), and the fade never moves at a seamless cut. Only on shots that hold or drift: a SCROLL is
    doc_scroll's."""
    top, bot = K.zone("split")
    lim = math.floor(min(fy + (K.SPILL_DISSOLVE_Y - (top + bot) / 2) / z for sh in run for (_, fy), z in framings(sh)))
    for sh in run:
        if lim <= sh["crop"][1]:
            raise K.BuildError(f"{sh['media']}: framed so its crop's top already sits below y{K.SPILL_DISSOLVE_Y}: "
                               "frame it higher")
        sh["crop"][3] = min(sh["crop"][3], lim)


def edges_in_panel(sh):
    """The sides of the shot's crop that land inside the panel (by more than a pixel) on any framing: there the window
    shows an edge, so it is feathered into the fill and reads as the page continuing (captures.md § 4)."""
    x0, y0, x1, y1 = sh["crop"]
    out = set()
    for ((fx, _), z), ty, by in zip(framings(sh), frame_y(sh, y0), frame_y(sh, y1)):
        out |= {side for side, inside in (("left", K.FRAME_W / 2 + (x0 - fx) * z > 1), ("top", ty > 1),
                                          ("right", K.FRAME_W / 2 + (x1 - fx) * z < K.FRAME_W - 1),
                                          ("bottom", by < K.SEAM - 1)) if inside}
    return sorted(out)


def page(gid, shots):
    """Real pages as the evidence (captures.md § 3-4, § 8 for a company's own hero): one shot per plan shot (the cell's
    start, its `shot_cuts`, its end), the page filling the panel. shots = [(media, t0, frame, crop, fill)] in spoken
    order, a 6th item optional: the shot's own measured events ([{event, media_t | at, note}]: a click, typing).
      t0     the media second the shot opens on; None: a still opens on 0, a take on page_in() (its first change held
             whole, measured on what the shot frames)
      frame  the source rect that must be whole ([x0, y0, x1, y1], fitted at FIT_PAGE), a framing ((fx, fy), z), or a
             (from, to) pair of framings: a gentle push across the shot (the kit caps a flat push at DRIFT_MAX)
      crop   the window: the page around the frame as far as it runs clean, so the page fills the panel, never a strip
             of page on a flat band
      fill   THIS shot's page colour off a rendered frame (K.sample_fill): the kit lays it under the shot for its frames
             only, switched on the cut, so a dark checkout after a white page sits on its own dark (captures.md § 4)
    Every crop edge that lands inside the panel is feathered into the fill. A cell carrying "under_caption": true (a
    real capture the caption's own box may sit over, captures.md § 4) runs its pages on to the seam; without it the crop's
    bottom is raised so the ink ends by SPILL_DISSOLVE_Y and fades into the fill above the caption band. A cut between
    pages takes the shutter; a cut inside one take at one framing skips a dead wait (captures.md § 5, proven static on a
    take) and is seamless and silent; the opening sound is entry()'s."""
    a, b = span(gid)
    mode_of(gid, "S")
    cuts = [a] + [K.sn(t) for t in cell(gid).get("shot_cuts") or []] + [b]
    if len(cuts) - 1 != len(shots):
        raise K.BuildError(f"{gid}: {len(shots)} shots for the plan's {len(cuts) - 1}: one per shot")
    out, runs = [], []
    for i, (media, t0, frame, crop, fill, *own) in enumerate(shots):
        if i:
            lands_on(cuts[i])
        dur = cuts[i + 1] - cuts[i]
        sh = {"media": media, "dur": dur, "crop": list(crop), "bg": fill, "events": list(own[0] if own else [])}
        if len(frame) == 4:
            sh.update(rect=list(frame), margin=V("FIT_PAGE"))
        elif isinstance(frame[1], (int, float)):
            sh.update({"from": frame, "to": frame})
        else:
            sh.update({"from": frame[0], "to": frame[1], "ease": "sine.inOut"})
        video = media.endswith(K.VIDEO_EXT)
        if t0 is None and video:
            x0, y0, x1, y1 = sh.get("rect") or crop
            rec = measured(media, (x0, y0, x1 - x0, y1 - y0), whole=True)
            t0 = page_in(rec["events"], dur, rec["frames"] / float(Fraction(rec["fps"])))
        sh["t0"] = t0 or 0.0
        prev = out[-1] if out else None
        if prev and prev["media"] == media and prev["crop"] == sh["crop"] and framings(prev)[-1] == framings(sh)[0]:
            gone = (prev["t0"] + prev["dur"], sh["t0"])           # one take at one framing: a dead wait skipped
            x0, y0, x1, y1 = sh["crop"]
            moving = [e for e in measured(media, (x0, y0, x1 - x0, y1 - y0)) if gone[0] < e["seconds"] < gone[1]] if video else []
            if moving:
                raise K.BuildError(f"{gid}: the skip at shot {i} would cut the page's own motion at {moving[0]['seconds']:.2f} s "
                                   "of the take (captures.md § 5): play it, or cut to another page")
            runs[-1].append(sh)
        else:
            if prev:
                sh["events"].insert(0, {"event": "camera", "at": 0, "note": "a cut between captured pages: the shutter"})
            runs.append([sh])
        out.append(sh)
    for run in runs if not cell(gid).get("under_caption") else ():
        clear_band(run)
    for sh in out:
        edges = edges_in_panel(sh)
        if edges:
            sh["feather"] = edges
    out[0]["events"][:0] = entry(gid)
    s = K.capture({"id": gid, "start": a, "layout": "split", "bg": out[0]["bg"], "shots": out})
    if not s.events:
        s.meta["silent"] = FROM_FACE
    return s


def doc_scroll(gid, media, rows, fill):
    """A written artifact read down its page (a doc, a spec, a sheet: the thing he wrote IS the proof), for a line about
    what it says: ONE still of the page's own column, stitched from a scroll take's sharp holds (an app that steps its own
    scroll every few frames stutters at 1x, so the scroll is a pan over the real page, never a re-typed one), filling the
    panel's width and panned on a sine ease across the whole cell. rows = (first, last): the source rows (px of the still)
    at the top of the content zone (y200) on the cell's first frame and on its last. It runs on to the seam under the
    caption's own box, so its cell carries "under_caption": true (captures.md § 4): a raised source crop would ride up the
    panel as it pans and leave it blank under the page. fill = the page's colour off a rendered frame (K.sample_fill)."""
    a, b = span(gid)
    mode_of(gid, "S")
    if not cell(gid).get("under_caption"):
        raise K.BuildError(f'{gid}: a scroll runs on to the seam under the caption\'s own box: mark its plan cell '
                           '"under_caption": true (captures.md § 4). A raised source crop rides up the panel as it pans')
    from PIL import Image
    with Image.open(GFX / "assets" / "captures" / media) as im:
        w, h = im.size
    z = round(K.FRAME_W / w, 4)
    top, bot = K.zone("split")
    f0, f1 = (((w / 2, round(r + ((top + bot) / 2 - top) / z, 1)), z) for r in rows)
    need = rows[1] + (K.SEAM - top) / z                        # the source row on the seam on the last frame
    if need > h:
        raise K.BuildError(f"{gid}: scrolled to row {rows[1]}, the panel reaches source y{need:.0f} but {media} ends at "
                           f"y{h}: stitch more of the page, or stop the scroll higher")
    s = K.capture({"id": gid, "start": a, "layout": "split", "bg": fill, "shots": [
        {"media": media, "size": (w, h), "t0": 0.0, "dur": b - a, "from": f0, "to": f1, "ease": "sine.inOut",
         "events": entry(gid)}]})
    if not s.events:
        s.meta["silent"] = FROM_FACE
    return s


# ── authored on the house backdrop (graphics.md § 8) ────────────────────────────────────────────────────────────
def hook(gid, icon, name, value, groups, live=None, **claim):
    """The hook lockup (graphics.md § 5), S from frame 0: the subject's real icon (bare), its name, and ONE object that
    performs the premise on its words. This recipe's object is the stock one for a VALUE (components.masked_value):
    masked dots fill across `value`, the word the value is named on, and the live badge lands on `live`, the payoff
    word. groups is the value's own masked grouping (graphics.md § 5) and **claim goes to masked_value (lead, bars,
    glyph, seps). A premise that is not a value builds its own object and hands it to C.hook_stack; nothing restates
    the caption."""
    a, b = span(gid)
    mode_of(gid, "S")
    beats = {"value": said(gid, value), **({"live": said(gid, live)} if live else {})}
    return C.hook_stack(ctx, icon, name, C.masked_value(list(groups), beats, **claim), id=gid, start=a, end=b)


DEV_LOG = ["$ ./setup", "Resolving dependencies...", "Fetching 214 packages", "warning: peer dependency mismatch",
           "Compiling project (38 files)", "error: cannot find module 'config'", "Retrying (2/5)...", "Starting server",
           "error: address already in use", "Migrating database", "error: connection refused",
           "Traceback (most recent call last):", '  File "setup/run.py", line 41', "ImportError: missing dependency",
           "permission denied: ./deploy.sh", "Build failed with 3 errors", "Rolling back changes...",
           "fatal: not a repository", "Segmentation fault", "Out of memory"]   # generic noise: no vendor, path or key
DEV_TITLES = ["watch", "logs", "install", "deploy", "rebase", "tests", "bundle", "ssh", "db", "build", "lint", "cache"]
STACK, SWARM = 3, 6                                     # windows per middle beat (a stack), on the last beat (the swarm)


def pile(n):
    """n window slots for escalation(), in stage px (1080 x 960): a sunflower spiral round (540, 460), so any count
    covers the stage evenly from the middle out and each window lands far from the one before (the golden angle),
    tilted alternately 2-9 degrees. The outer ones run off the SIDES, which the look allows; none rises past the stage's
    top (the platform's top band). -> [(x, y, w, h, deg)]"""
    out = []
    for i in range(n):
        r, ang = math.sqrt((i + 0.5) / n), 0.6 + i * 2.39996
        w, h = 440 + (i * 3 % 5) * 50, 330 + (i * 5 % 4) * 36
        cx, cy = 540 + 430 * r * math.cos(ang), 460 + 290 * r * math.sin(ang)
        out.append((round(cx - w / 2), max(10, round(cy - h / 2)), w, h, (-1) ** i * (2 + i * 5 % 8)))
    return out


def escalation(gid, words, calm="$ setup", log=DEV_LOG, titles=DEV_TITLES):
    """A pain built on escalating words (graphics.md § 3.8): ONE scene that gets worse on each of `words` (2 or more,
    in spoken order). Calm first (one window, `calm` at a blinking cursor); the first word pours `log` through it;
    each middle word stacks STACK more windows; the last multiplies a SWARM while the stage shrinks and shakes; the
    danger wash (the verdict) builds after the last window lands. The spill runs off the panel's sides and has
    dissolved before the caption band. Sound: the working bed under the build, cut by the error after the last element
    (sfx.md § 1). This recipe's object is the terminal pile of a dev-setup pain; another pain piles up its own object
    (tabs, forms, notifications) on the same ladder."""
    a, b = span(gid)
    mode_of(gid, "S")
    if len(words) < 2:
        raise K.BuildError(f"{gid}: an escalation needs two or more words to climb; one word is a claim (graphics.md § 3)")
    clock = C.Clock(ctx, gid, a, b)
    beats = [clock.beat(said(gid, w)) for w in words]
    if any(y <= x for x, y in zip(beats, beats[1:])):
        raise K.BuildError(f"{gid}: {words} are not said in that order")
    VAL, line, dur = K.VALUES, V("TERM_LINE_PX"), clock.dur
    lo, hi = (int(x) for x in VAL["ESC_SCROLL_STEPS"].split("-"))        # log scroll steps a second: stack, swarm
    waves = [STACK] * (len(beats) - 2) + [SWARM]

    def win(i, x, y, w, h, rot, title, extra=""):
        k = i * 7 % len(log)
        rows = "".join(f'<div class="{"e" if any(x_ in t for x_ in ("error", "fatal", "denied", "fault")) else ""}">'
                       f"{t.replace('<', '&lt;')}</div>" for t in (log * 4)[k:k + 60])
        return (f'<div class="tw" id="w{i}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
                f'transform:rotate({rot}deg);"><div class="tb"><i></i><i></i><i></i><span>{title}</span></div>'
                f'<div class="tv"><div class="ts" id="s{i}">{rows}</div>{extra}</div></div>')
    slots = pile(sum(waves))
    calm_win = win(0, 70, 96, 940, 700, 0, "~/project",
                   f'<div class="calm" id="calm">{calm.replace("<", "&lt;")}<u id="cur"></u></div>')
    # .pile is the frame's whole panel in panel px (-144,-255 to 1224,960 through the 0.79 fit), so the spill and the
    # wash reach the frame's edges; its mask has faded everything by frame y900, above the caption band (layout.md § 8)
    css = (".pile{position:absolute;left:-144px;top:-255px;width:1368px;height:1215px;"
           "-webkit-mask-image:linear-gradient(#000 1088px,transparent 1139px);"
           "mask-image:linear-gradient(#000 1088px,transparent 1139px);}"
           ".stage{position:absolute;left:144px;top:255px;width:1080px;height:960px;transform-origin:540px 450px;}"
           f".tw{{position:absolute;border-radius:{VAL['TERM_RADIUS']}px;background:{VAL['TERM_BODY']};"
           "overflow:hidden;opacity:0;box-shadow:0 34px 80px rgba(0,0,0,0.6),0 0 0 2px rgba(255,255,255,0.10);}"
           f".tb{{height:{VAL['TERM_BAR_PX']}px;background:{VAL['TERM_BAR']};display:flex;align-items:center;"
           "padding:0 24px;gap:12px;}.tb i{display:block;width:20px;height:20px;border-radius:50%;}"
           + "".join(f".tb i:nth-child({k + 1}){{background:{c};}}" for k, c in enumerate(VAL["TERM_LIGHTS"].split(",")))
           + ".tb span{margin-left:16px;font-family:'SFM';font-weight:700;font-size:24px;color:#8b93a7;letter-spacing:1px;}"
           f".tv{{position:absolute;left:0;top:{VAL['TERM_BAR_PX']}px;right:0;bottom:0;overflow:hidden;}}"
           f".ts{{position:absolute;left:28px;top:22px;right:20px;font-family:'SFM';font-weight:500;"
           f"font-size:{VAL['TERM_MONO_PX']}px;line-height:{line:g}px;color:{VAL['TERM_TEXT']};white-space:nowrap;}}"
           f".ts .e{{color:{VAL['TERM_ERROR']};}}"
           f".calm{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:14px;"
           f"background:{VAL['TERM_BODY']};font-family:'SFM';font-weight:700;font-size:44px;color:#fff;}}"
           ".calm u{display:block;width:22px;height:48px;background:#fff;text-decoration:none;}"
           f".wash{{position:absolute;inset:0;opacity:0;background:{VAL['DANGER_WASH']};}}")
    html = ('<div class="pile"><div class="stage" id="stage">' + calm_win
            + "".join(win(i + 1, *s, titles[i % len(titles)]) for i, s in enumerate(slots))
            + '</div><div class="wash" id="wash"></div></div>')
    m, pour = C.Motion(), beats[0]
    m.row_in("#w0", 0.0, dy=70, frm=0.94, frames=9, note="the calm window rises in")
    m.blink("#cur", 0.3, pour)
    m.hide("#calm", pour)                                  # the first word: the calm screen is gone, the log pours
    m.fromto("#s0", {"y": 0}, {"y": -line * 50}, pour, dur - pour, f"steps({int((dur - pour) * (lo + hi) / 2)})")
    n, last = 1, 0.0
    for wave, (at0, size) in enumerate(zip(beats[1:], waves)):
        swarm = wave == len(waves) - 1
        for k in range(size):                             # a middle word stacks a few; the last word swarms
            at = at0 + k * (K.fsec(3) if swarm else 0.22)
            role = "run" if swarm else ("sibling" if k == 0 else "cascade")
            m.pop_in(f"#w{n}", at, role, frm=0.4 if swarm else 0.5, frames=5 if swarm else 6, back=2.0 if swarm else 1.8,
                     note="the swarm multiplies" if swarm else "a window stacks")
            rate = hi if swarm else lo
            m.fromto(f"#s{n}", {"y": 0}, {"y": -line * 30}, at, dur - at, f"steps({int((dur - at) * rate)})")
            n, last = n + 1, at
    landed = m.snap(last) + K.fsec(5)                     # the last window has landed: the verdict
    if landed > dur - 0.4:
        raise K.BuildError(f"{gid}: the swarm lands {landed:.2f} s in, too close to the end ({dur:.2f} s): a longer "
                           "cell, or fewer words")
    swarm_at = beats[-1]
    m.to("#stage", {"scale": V("ESC_STAGE")}, swarm_at, dur - swarm_at, "power1.inOut")
    shake = m.snap(swarm_at + 0.4)
    m.fromto("#stage", {"x": -V("ESC_SHAKE_X"), "rotation": -V("ESC_SHAKE_ROT")},
             {"x": V("ESC_SHAKE_X"), "rotation": V("ESC_SHAKE_ROT")}, shake, V("ESC_SHAKE_S"), "none",
             repeat=int((dur - shake) / V("ESC_SHAKE_S")) - 1, yoyo=True)
    m.to("#wash", {"opacity": 1}, landed, min(V("ESC_WASH_S"), dur - landed), "power1.in")
    events = m.events + [K.ev("processing", pour, "the work pours out: the bed runs to the verdict", dur=landed - pour),
                         K.ev("error", landed, "the verdict: after the last window lands, as the bed cuts")]
    (x0, y0), (x1, y1) = K.to_frame(70, 96), K.to_frame(1010, 796)
    return K.authored(html, "\n".join(m.js), css, "split", id=gid, start=a, dur=dur, events=events,
                      visible0=["#w0"], bbox=(x0, y0, x1, y1), units="panel")


# ── over the face (layout.md § 2, mode O) ────────────────────────────────────────────────────────────────────────
def call(gid, name, avatar=None, ring=None, already_live=False):
    """A call happening on camera (graphics.md § 3.4): the wide shot stays (the footage is the proof) and the OS call
    card sits above the speaker's head, clear of the crown the plan's cell measured. It rings from `ring` (the word that says it
    rings; default the card's first frame), accept is pressed on the cut where the other voice starts (voice_cut), then a
    live timer and a waveform from that voice's REAL envelope. already_live=True: the call was answered before the card
    lands, so it opens live."""
    a, b = span(gid)
    mode_of(gid, "O")
    return C.call_card(ctx, name, avatar, cell(gid)["crown"], ring_from=said(gid, ring) if ring else None,
                       answer_at=None if already_live else voice_cut(a, b), id=gid, start=a, end=b)


# ── the ask (graphics.md § 6): it pushes in from the graphic before it and never exits ───────────────────────────
def comment_ask(gid, comment, keyword, send, reply, reply_text, attachment=None):
    """A comment ask, enacted as a DM thread from the VIEWER's side (components.thread_cta): the composer lands on
    `comment`, HIS spoken `keyword` types across its word, the send lands on `send`, and his reply on `reply` carries the
    promised thing as an object (attachment = (title, one-line meta)). reply_text and the attachment copy are the
    editor's words unless he said them: flag them in the plan so he can change them."""
    a, b = span(gid)
    mode_of(gid, "S")
    words = {"comment": said(gid, comment), "keyword": said(gid, keyword), "send": said(gid, send),
             "reply": said(gid, reply)}
    return pushed(C.thread_cta(ctx, words, keyword, reply_text, attachment, id=gid, start=a, end=b))


def click_ask(gid, marks, label, words):
    """A click ask (the ad's, only when the plan carries variants.ad; README § Deliverables): components.click_cta, timed
    from the AD's own transcript. marks = the sponsor's icon and wordmark files; label = the button, in HIS words; words =
    {try, name, just, click, link, below}: each beat's one word as he says it. Its id is the organic ask's plus "ad"
    with no hyphen (<id>ad, never <id>-ad: the lane's placer reads <id>-<word>-alpha.mov as a version of <id>)."""
    a, b = span(gid)
    mode_of(gid, "S")
    return pushed(C.click_cta(ctx, marks, label, {k: ad_find(w, a) for k, w in words.items()}, id=gid, start=a, end=b))


# ══ STORYBOARD: the one section you edit ══════════════════════════════════════════════════════════════════════════
# First the job's measured facts (per shoot, never rules), then one entry per plan cell, in any order (the plan owns
# the reel): {cell id: (recipe, its arguments)}. Words are phrases said inside the cell; media are file names under
# assets/captures/, marks paths under assets/logos/, both put there by `kit/engine.py stage projects/<job> <id> <file>`
# (a mark with --mark; graphics.md § 15 step 2), never copied by hand. A cell no recipe fits gets its own function here,
# on the same pattern. A few shapes, for reading only:
#     "g2": (montage, dict(screens=[("<screen>.png", [x0, y0, x1, y1], [x0, y0, x1, y1]), ...], fill="<sampled>")),
#     "g5": (call, dict(name="<the caller as the product shows it>", avatar="assets/logos/<mark>.png")),
#     "g6": (page, dict(shots=[("<take>.mp4", None, [x0, y0, x1, y1], [x0, y0, x1, y1], "<its sampled fill>"),
#                              ("<still>.png", None, ((fx, fy), z), [x0, y0, x1, y1], "<its sampled fill>")])),
#     "g7": (doc_scroll, dict(media="<the stitched page>.png", rows=(<first row>, <last row>), fill="<sampled>")),
#     "g9": (comment_ask, dict(comment="comment", keyword="<his word>", send="<his word>", reply="<his words>",
#                              reply_text="<flagged in the plan>", attachment=("<title>", "<meta>"))),
STORYBOARD = {
}
# ══ end of STORYBOARD ════════════════════════════════════════════════════════════════════════════════════════════


def _smoke_binding():
    """The kit smoke's binding (engine.py smoke), applied only on its synthetic job: every recipe except the ad's
    exercised once on the invented reel's cells, so a kit change that breaks a recipe fails the smoke. The words are
    that invented script's and the facts its synthetic media's. Never a storyboard to copy."""
    chat = Chat(media="chat.mp4", take=K.Take((1640, 2080), column=(280, 1640)), header="chat-header.png", fill="#050505",
                input_text=(340, 1900, 900, 80), thread=(280, 140, 1360, 1720), exchange_top=1150, reply_end=1780,
                bubbles_x=(330, 1600))
    icon = "assets/logos/acme-assistant.png"
    return {                                            # keyed by the fixture's cells, grouped as the cookbook is
        "g3": (chat_typing, dict(chat=chat)),
        "g5": (chat_reply, dict(chat=chat, answer="plan")),
        "g4": (montage, dict(fill="#1b1d22", screens=[
            ("dash-inbox.png", [100, 150, 960, 610], [0, 0, 1440, 610]),
            ("dash-calendar.png", [60, 180, 900, 620], [0, 0, 1440, 620]),
            ("dash-analytics.png", [300, 260, 1400, 830], [0, 0, 1440, 830]),
            ("dash-tasks.mp4", [60, 170, 1000, 800], [0, 0, 1440, 800])])),
        "g2": (brand_page, dict(media="site.mp4", marks=("assets/logos/acme-voice.png",
                                                         "assets/logos/acme-voice-wordmark.svg"),
                                hero=[0, 150, 1280, 560], fill="#fefefe")),
        "g9": (page, dict(shots=[("site.mp4", None, [0, 150, 1280, 560], [0, 120, 1280, 1140], "#fefefe"),
                                 ("checkout.png", None, [260, 120, 940, 880], [0, 0, 1200, 1000], "#16171c")])),
        "g10": (doc_scroll, dict(media="guide.png", rows=(0, 600), fill="#ffffff")),
        "g1": (hook, dict(icon=icon, name="Acme Assistant", value="number", groups=(1, 3, 3, 4), live="runs")),
        "g7": (escalation, dict(words=["technical", "complicated", "overwhelming"])),
        "g6": (call, dict(name="Acme Assistant", avatar=icon)),
        "g8": (comment_ask, dict(comment="comment", keyword="agent", send="below", reply="send you",
                                 reply_text="Here's the setup", attachment=("Assistant setup", "Folder · 3 files"))),
    }


def _is_smoke():
    """the synthetic job engine.py smoke builds: its folder name, or its transcript's engine field"""
    try:
        marker = json.loads(ctx.transcript_path.read_text(encoding="utf-8")).get("engine", "")
    except (OSError, ValueError):
        marker = ""
    return ctx.name == "kit-smoke" or "kit smoke" in str(marker)


def main(argv):
    board = STORYBOARD or (_smoke_binding() if _is_smoke() else {})
    if set(argv) - set(board):
        sys.exit(f"not in the STORYBOARD: {sorted(set(argv) - set(board))} (it has {sorted(board)})")
    cells = [c for c in list(ctx.cells.values()) + list((AD or {}).get("cells") or [])
             if c.get("graphic") and c.get("kind") != "captions"]
    for c in cells:
        if c["id"] not in board:
            print(f"⚠ plan cell {c['id']} ({c.get('family')}, {c.get('kind')}) has no STORYBOARD entry, so it is not "
                  "built: pick its device (graphics.md § 3) and bind its words")
    face = [row(r) for r in ctx.layout if row(r)[2] in ("T", "W")]    # T and W carry the face alone: a card over it is O
    for c in cells:
        if any(float(c["start"]) < float(e) - 1e-6 and float(s) < float(c["end"]) - 1e-6 for s, e, _, _ in face):
            raise K.BuildError(f"{c['id']} sits on a T/W row of the layout: a graphic over the face is an O card "
                               "(layout.md § 2)")
    built = []
    for gid, (make, args) in sorted(board.items(), key=lambda kv: K.sn(cell(kv[0])["start"])):
        if argv and gid not in argv:
            continue
        s = make(gid, **args)
        fam = cell(gid).get("family")
        if fam and fam != s.family.replace("capture-white", "capture"):
            raise K.BuildError(f"{gid}: the plan says family {fam!r}, the build made {s.family!r} (graphics.md § 7)")
        K.write(s, ctx.gfx)
        K.write_events(ctx.hf, s.id, s.events, s.meta.get("silent"))
        built.append(s)
    if not built:
        print("\n0 comp(s) written: bind each plan cell to its recipe in the STORYBOARD (graphics.md § 15)")
        return
    print(f"\n{len(built)} comp(s) written, their sounds as `src: kit` rows in hf-graphics/sfx-hand.json. Probe each in "
          f"the browser (graphics-build), then render it with its family's flags, from {ctx.gfx}:")
    print("  " + "\n  ".join(f"uv run kit/engine.py render {s.id}" for s in built))


if __name__ == "__main__":
    main(sys.argv[1:])
