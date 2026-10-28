#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""kit/components.py: the RECURRING authored components of the talking-head explainer look.

WHY this file exists: on the benchmark job every one of these pieces was hand-typed into that job's own scripts, and each
review round fixed a number the next job would have had to re-discover: a drop-in whose first frame sat above the safe
band, a masked-number row hanging outside its pill, a paired icon 7 % small (sized by its padded canvas), a thread typed
after its own send, a reply the scroll made no room for, a lone pop with nothing under its sound. A component is written
ONCE here, timed from WORD times, and it carries its own SFX events, so:
  - nothing about a component is retyped per job (the job's build.py is data: which component, on which words);
  - the first automatic sound pass comes out in the creator's vocabulary (every event is a name in ../sfx.json, and
    engine.write_events writes them as `src: kit` rows);
  - a re-cut is a re-run (every time is a word through engine.beat, never a typed second).
What a component depicts is a PATTERN (graphics.md § 3, § 5, § 6). The benchmark's own metaphors stay out of this file:
they illustrated a principle once and are never templates.

    import engine as K, components as C
    ctx = K.Ctx(JOB)
    claim = C.masked_value([3, 4], {"value": ctx.find("its own address"), "live": ctx.find("reachable")})
    s = C.hook_stack(ctx, "assets/logos/subject.png", "Subject", claim, id="g1", start=0.0, end=ctx.find("and you"))
    K.write(s, ctx.gfx); K.write_events(ctx.hf, s.id, s.events)

  (a Clock may stand in for ctx + id/start/end: C.hook_stack(C.Clock(ctx, "g1", 0.0, t_end), icon, name, claim);
   a phone number being assigned is the named preset: C.masked_value([1, 3, 3, 4], beats, **C.PHONE_NUMBER))

The components, and the sounds each writes (sfx.json names; sfx.md says why each is that sound):
  bare_icon(png, box_px)                   a real mark, bare, sized by its solid body         none
  masked(groups, glyph, seps)              a real value as mask glyphs in its grouping        none
  masked_value(groups, beats)              a value being ASSIGNED: a pill that fills on its   riseIn, ~5 tap, blip (bars,
                                           word (bars, lead glyph and badge only when asked)  opt-in), live (badge, opt-in)
  hook_stack(ctx, icon, name, claim)       the hook lockup: icon, name, claim                 pop-hero (the name rides it),
                                                                                              then the claim's
  call_card(ctx, name, avatar, crown_y,    a call over the wide face, driven by the real      riseIn (unless enter=False);
            ring_from, answer_at, ...)     voice; incoming or outgoing, continued across a    incoming: ring -> tap;
                                           layout break, ended                                outgoing: calling; end silent
  audio_envelope(job, raw_spans)           that voice per timeline frame, through the EDL     -
  thread_cta(ctx, words, keyword, reply,   the comment ask as a DM thread                     riseIn, typing, payoff, riseIn
             attachment, platform)
  click_cta(ctx, lockup, label, words)     the click ask: lockup, button, tap, arrow          pop-hero, riseIn, click
  brand_lockup(icon, wordmark)             the official lockup over a site hero               none
  push(prev_render, scene)                 graphic to graphic inside split                    cut-in
Motion's helpers (pop_in, rise_in, row_in, logo_slide, press, ring_pulse, drop_in, exit_in_place, bump, down_arrow,
bars) are the registry for a job's own authored scene: the same numbers, the same sounds.

Contract (every component):
  - seek-safe: ONE paused timeline (the comp's `tl`) of absolute tl.set / tl.to / tl.fromTo(..., immediateRender:false)
    calls; no onUpdate, timers or randomness (the renderer SEEKS a paused timeline, it never plays it);
  - every time is a word through engine.beat (frame-snap(word - 0.06 s)) or a cut through the scene clock, and every
    position is written ON the frame grid (engine.t6: floored at 6 dp, so it can never land a hair after its frame);
    a set and its entrance tween always share one frame;
  - never two tweens on one property of one element at overlapping times (engine.audit_js refuses it when the comp is
    written; a ring's cycle is longer than its tween, a pulse on an entering element waits for the entrance);
  - returns an engine Scene (engine.authored / engine.overlay) carrying events (engine.ev dicts), visible0 (what is on
    screen on comp frame 0, proven by a set at 0), bbox (the content extent in FRAME px, checked against the split
    content zone) and meta {kind, role, line, copy} (copy = the on-screen words, for the OCR copy check).

Units: an AUTHORED split component is laid out on the 1080x960 PANEL (units="panel": the engine scales it 0.79 into
the safe band, graphics.md § Units); the OVERLAY call card is laid out in FRAME px. The numbers are graphics.md § Values
through engine.VALUES; a value changes in the doc first, then in the engine, never here and never in a comp.
"""
import functools
import html as htmlmod
import json
import math
import os
import re
import subprocess
import sys
from array import array
from pathlib import Path

KIT = Path(__file__).resolve().parent
if str(KIT) not in sys.path:
    sys.path.insert(0, str(KIT))
import engine  # noqa: E402  (the kit's engine: the clock, the Scene builders, the hygiene audit, the SFX rows)

BuildError = engine.BuildError
V = engine.VALUES


def _v(key):
    return float(V[key])


# ------------------------------------------------------------------------------------------------------------------
# values (graphics.md § Values, read through the engine's mirror: one home)
# ------------------------------------------------------------------------------------------------------------------
PANEL_TO_FRAME = _v("PANEL_TO_FRAME")
HERO_ICON_PX = _v("HERO_ICON_PX")                   # frame px: the hook's icon
ROYAL, SKY, MUTED, GREEN, RED = V["ROYAL"], V["SKY"], V["MUTED"], V["GREEN"], V["RED"]
OS_ACCEPT, OS_DECLINE = V["OS_ACCEPT"], V["OS_DECLINE"]
BUBBLE_IN, ATTACHMENT, TYPING_DOTS, AVATAR_DISC = V["BUBBLE_IN"], V["ATTACHMENT"], V["TYPING_DOTS"], V["AVATAR_DISC"]
IG_SENT = V["IG_SENT"]
HERO_PX, HERO_WEIGHT, HERO_TRACK = _v("HERO_PX"), int(_v("HERO_WEIGHT")), _v("HERO_TRACK")
BUTTON_PX = _v("BUTTON_PX")
MARK_SHADOW = V["MARK_SHADOW"]
MARK_SOLID_ALPHA = int(_v("MARK_SOLID_ALPHA"))
LOGO_X, LOGO_ROT, LOGO_FRAMES, LOGO_EASE = _v("LOGO_X"), _v("LOGO_ROT"), int(_v("LOGO_FRAMES")), V["LOGO_EASE"]
PRESS_UP_EASE = V["PRESS_UP_EASE"]
DROP_FRAMES, DROP_FROM, DROP_EASE = int(_v("DROP_FRAMES")), _v("DROP_FROM"), V["DROP_EASE"]
EXIT_EASE = V["EXIT_EASE"]
RISE_CARD_FRAMES = int(_v("RISE_CARD_FRAMES"))
PUSH_FRAMES, PUSH_EASE = int(_v("PUSH_FRAMES")), V["PUSH_EASE"]
ARROW_PX, ARROW_BOB_PX, ARROW_BOB_S = _v("ARROW_PX"), _v("ARROW_BOB_PX"), _v("ARROW_BOB_S")

# the frame bands (layout.md's, through the engine) and the components' own approved geometry
SEAM = engine.SEAM                                   # the .safe scale's origin is (540, SEAM)
ZONE_TOP, ZONE_BOTTOM = engine.SPLIT_ZONE            # frame px: split key content lives in y200-845
CALL_TOP_MIN = engine.SAFE[0] + 4                    # frame px: a dropped card's FIRST frame is already inside the safe band
CALL_CROWN_GAP = 25                                  # frame px: the call card's bottom sits this far above the measured crown
HOOK_LIFT = 60                                       # frame px: the hook stack lifts so the caption keeps the seam (2026-09-22)
FD, FM = "'SFD'", "'SFM'"                            # the engine's @font-face families (display, mono)

# the SFX vocabulary the components speak: every name is an event in ../sfx.json (the kit test holds it)
POP = {"hero": "pop-hero", "sibling": "pop", "cascade": "pop-cascade", "run": "pop-run"}
EVENTS = frozenset(set(POP.values()) | {"riseIn", "slideIn", "tap", "click", "typing", "ring", "calling", "payoff",
                                        "blip", "status-keys", "status-chime", "live", "bump", "cut-in"})
BADGE_HOLD_MIN_S = 1.5                               # a live badge needs this long on screen to be read, ringing
VALUE_KEY_LEAD_S = 0.12                              # a DESIGNED lead (the approved hook, rendered and approved that
                                                     # way): masked_value's dots start keying this far ahead of the value
                                                     # word's beat (about 4 frames before the word, past L5's 2), so the
                                                     # value is visibly being entered as it is said. Recorded, never
                                                     # implied: the first tap's sfx-hand row carries the lead as built
                                                     # as "sync_offset" (-0.12, shorter when the pill lands late), and
                                                     # change-events.py --sync reads it off that row, so the value
                                                     # word's anchor need not repeat it; a named "offset" must equal it
                                                     # (graphics.md § 15 6b, L5's named offset)

# solid-fill glyphs (Material paths: icons are solid, never outlines)
PHONE = ("M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 "
         "1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 "
         "1.02l-2.2 2.2z")
ARROW_UP = "M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8-8 8z"
PERSON = "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"
LINK = ("M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v"
        "2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z")
POINTER = ('<svg viewBox="0 0 28 40" width="84" height="120" style="display:block;filter:drop-shadow(0 10px 18px '
           'rgba(0,0,0,0.6))"><path d="M2 2 L2 31 L9.5 24 L14.5 36 L19.5 34 L14.5 22.5 L25 22.5 Z" fill="#fff" '
           'stroke="#111" stroke-width="2" stroke-linejoin="round"/></svg>')
FOLDER = ('<svg viewBox="0 0 120 96" width="120" height="96" style="display:block"><path d="M8 14a8 8 0 0 1 8-8h30l10 '
          '12h48a8 8 0 0 1 8 8v56a8 8 0 0 1-8 8H16a8 8 0 0 1-8-8z" fill="#3d7bff"/><path d="M8 32h104v50a8 8 0 0 1-8 8H16a8 '
          '8 0 0 1-8-8z" fill="#62a2ff"/></svg>')
# the attachment's file-TYPE icon (a DM shows the kind of thing sent, never a drawn preview of it), one solid family
VIDEO_FILE = ('<svg viewBox="0 0 120 96" width="120" height="96" style="display:block"><rect x="8" y="8" width="104" '
              'height="80" rx="16" fill="#3d7bff"/><path d="M8 24a16 16 0 0 1 16-16h72a16 16 0 0 1 16 16v4H8z" '
              'fill="#62a2ff"/><path d="M50 38v34l28-17z" fill="#fff"/></svg>')
DOC_FILE = ('<svg viewBox="0 0 120 96" width="120" height="96" style="display:block"><path d="M34 4h38l28 28v52a8 8 0 0 '
            '1-8 8H34a8 8 0 0 1-8-8V12a8 8 0 0 1 8-8z" fill="#3d7bff"/><path d="M72 4v20a8 8 0 0 0 8 8h20z" fill="#62a2ff"/>'
            '<rect x="38" y="48" width="48" height="7" rx="3.5" fill="#62a2ff"/><rect x="38" y="62" width="48" height="7" '
            'rx="3.5" fill="#62a2ff"/><rect x="38" y="76" width="30" height="7" rx="3.5" fill="#62a2ff"/></svg>')
ATTACH_GLYPHS = {"folder": FOLDER, "video": VIDEO_FILE, "doc": DOC_FILE}
LIVE_DOT = '<svg viewBox="0 0 24 24" width="{px}" height="{px}" style="display:block"><circle cx="12" cy="12" r="7" fill="#fff"/></svg>'
GLYPHS = {"phone": PHONE, "link": LINK}              # named solid glyphs a claim's lead or badge may carry


def glyph_svg(name, px, fill="#fff"):
    """a named glyph ("phone", "link", or "dot": the plain live dot), or inline SVG/HTML passed through"""
    if str(name).lstrip().startswith("<"):
        return str(name)
    if name == "dot":
        return LIVE_DOT.replace("{px}", str(px)).replace('fill="#fff"', f'fill="{fill}"')
    if name not in GLYPHS:
        raise BuildError(f"no glyph {name!r}: use one of {sorted(GLYPHS) + ['dot']}, or pass inline SVG")
    return icon_svg(GLYPHS[name], px, fill)

# a DM thread's platform: (the VIEWER's sent colour, on the sent bubble and the send button; the caret accent). Only a
# platform whose real sent colour was checked goes here; any other is passed as a (fill, accent) tuple.
PLATFORMS = {"instagram": (IG_SENT, "#e0307e")}


def icon_svg(path, px, fill="#fff", rot=0):
    """a solid 24-unit Material glyph as inline SVG"""
    tr = f"transform:rotate({rot}deg);" if rot else ""
    return (f'<svg viewBox="0 0 24 24" width="{px}" height="{px}" style="display:block;{tr}">'
            f'<path d="{path}" fill="{fill}"/></svg>')


# ------------------------------------------------------------------------------------------------------------------
# the scene clock and the timeline writer
# ------------------------------------------------------------------------------------------------------------------
class Clock:
    """One scene on the job's frame grid (engine.Ctx sets the grid from the plan). start/end are TIMELINE seconds (a
    Word or a float); beat() anchors a spoken word, cut() anchors a picture cut (no lead: a cut already is its frame).
    family = the scene's (engine.FAMILIES): an authored scene renders at its STEP_FPS and is held up to the grid, so its
    cut() lands on the 12 fps sample its frame shows (engine.step_cut), the frame the caption breaks on; an overlay's is
    the grid itself."""

    def __init__(self, ctx, id, start, end=None, dur=None, family="authored"):
        if not id:
            raise BuildError("a component needs id=")
        if start is None:
            raise BuildError(f"{id}: a component needs start= (its timeline in-point)")
        if end is None and dur is None:
            raise BuildError(f"{id}: a component needs end= (or dur=)")
        if family not in engine.FAMILIES:
            raise BuildError(f"{id}: family {family!r}: one of {engine.FAMILIES}")
        self.ctx, self.id, self.family = ctx, id, family
        self.step = int(engine.FAMILY_FLAGS[family].get("STEP_FPS") or 0) or None
        self.start = engine.sn(float(start))
        self.n = engine.frames(float(dur) if dur is not None else float(end) - self.start)
        if self.n < 1:
            raise BuildError(f"{id}: shorter than one frame")
        self.dur = engine.fsec(self.n)
        self.fps = float(engine.FPS)

    def beat(self, word):
        return engine.beat(float(word), self.start)

    def cut(self, t):
        return max(0.0, engine.step_cut(max(0.0, float(t) - self.start), self.step))

    @property
    def job(self):
        return getattr(self.ctx, "job", None)


def _Clock(start, end, fps=None, id="kit", job=None, family="authored"):
    """a job-less scene clock (the self-check's and the tests'); fps sets the grid when given"""
    if fps is not None:
        engine.use_fps(fps)
    return Clock(None if job is None else type("JobRef", (), {"job": job})(), id, start, end, family=family)


def _clock(ctx, id, start, end, dur, family="authored"):
    """a component's clock: ctx is an engine.Ctx (or None) plus id/start/end, or already a Clock (re-made on the
    component's own family, so an authored Clock handed to the call card never steps its cuts)"""
    if isinstance(ctx, Clock) and start is None:
        return ctx if ctx.family == family else Clock(ctx.ctx, ctx.id, ctx.start, dur=ctx.dur, family=family)
    return Clock(ctx.ctx if isinstance(ctx, Clock) else ctx, id or getattr(ctx, "id", None), start, end, dur, family)


def _num(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _js(v):
    """a Python value as a JS literal (dict keys are identifiers)"""
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if isinstance(v, (bool, int, float)):
        return _num(v)
    if isinstance(v, dict):
        return "{" + ",".join(f"{k}:{_js(x)}" for k, x in v.items()) + "}"
    if isinstance(v, (list, tuple)):
        return "[" + ",".join(_js(x) for x in v) + "]"
    raise TypeError(f"no JS literal for {v!r}")


class Motion:
    """One component's slice of the comp's ONE paused timeline, plus the SFX events its motion implies. Every position
    is snapped to the frame grid and printed floored (engine.t6), so an element's set and its entrance tween always
    share one frame (a set a frame earlier than its tween shows the element un-entered for a frame).

    Each helper writes GSAP from the graphics.md § 13 numbers and appends its own event, except rise_in: a riseIn on
    TYPE goes through the registry (H.riseIn), where sfx-plan finds the call and snips it (sfx.json)."""

    def __init__(self):
        self.js, self.events = [], []

    @staticmethod
    def F(n=1):
        return n / float(engine.FPS)

    @staticmethod
    def snap(t):
        return engine.fsec(engine.frames(max(0.0, float(t))))

    @staticmethod
    def pos(t):
        return engine.t6(engine.frames(max(0.0, float(t))))

    # -- raw timeline calls --
    def set(self, sel, props, t):
        self.js.append(f"tl.set({_js(sel)},{_js(props)},{self.pos(t)});")

    def to(self, sel, props, t, dur, ease="none", **extra):
        self.js.append(f"tl.to({_js(sel)},{_js({**props, 'duration': round(dur, 6), 'ease': ease, **extra})},{self.pos(t)});")

    def fromto(self, sel, a, b, t, dur, ease="none", **extra):
        b = {**b, "duration": round(dur, 6), "ease": ease, **extra, "immediateRender": False}
        self.js.append(f"tl.fromTo({_js(sel)},{_js(a)},{_js(b)},{self.pos(t)});")

    def event(self, t, name, dur=None, note="", sync_offset=None):
        """sync_offset: a DESIGNED offset of this beat from its word's beat (s, negative = ahead), written on its row"""
        if name not in EVENTS:
            raise BuildError(f"{name!r} is not in the components' SFX vocabulary (EVENTS, documented in sfx.json)")
        self.events.append(engine.ev(name, self.snap(t), note, None if dur is None else max(0.0, dur), sync_offset))

    # -- the registry (graphics.md § 13) --
    def show(self, sel, t):
        self.set(sel, {"opacity": 1}, t)

    def hide(self, sel, t):
        self.set(sel, {"opacity": 0}, t)

    def pop_in(self, sel, t, role="hero", frm=0.5, rot=0, frames=8, back=1.7, note="", sound=True):
        """OBJECTS pop: scale frm -> 1 with overshoot. role = hero | sibling | cascade | run picks the pop's level (the
        hero is the fullest; a cascade's later members and a fast run are quieter, because the pattern is already heard)."""
        self.show(sel, t)
        a = {"scale": frm, **({"rotation": rot} if rot else {})}
        b = {"scale": 1, **({"rotation": 0} if rot else {})}
        self.fromto(sel, a, b, t, self.F(frames), f"back.out({back})")
        if sound:
            self.event(t, POP[role], note=note or f"{sel} pops in")

    def rise_in(self, sel, t, px=None, dist=None):
        """TYPE rises, never pops: the house registry riseIn (hf-anim.js, bound to tl as H), 22 px at 90 px type,
        ratio-scaled to px. No event here: sfx-plan finds the registry call and gives type its snip."""
        d = dist if dist is not None else round(22 * (px or 90) / 90, 1)
        self.js.append(f"H.riseIn({_js(sel)},{self.pos(t)},{_num(d)});")

    def row_in(self, sel, t, dy=60, frm=0.94, frames=RISE_CARD_FRAMES, ease="power3.out", sound="riseIn", note=""):
        """rows, cards, panels and pills rise with a small scale-up; the soft rise whoosh"""
        self.show(sel, t)
        self.fromto(sel, {"y": dy, "scale": frm}, {"y": 0, "scale": 1}, t, self.F(frames), ease)
        if sound:
            self.event(t, sound, note=note or f"{sel} rises in")

    def logo_slide(self, sel, t, side="left", note=""):
        """a logo slides in from its own side on its name; the slide whoosh"""
        s = -1 if side == "left" else 1
        self.show(sel, t)
        self.fromto(sel, {"x": s * LOGO_X, "rotation": s * LOGO_ROT}, {"x": 0, "rotation": 0}, t, self.F(LOGO_FRAMES), LOGO_EASE)
        self.event(t, "slideIn", note=note or f"{sel} slides in")

    def press(self, sel, t, colour_to=None, down=0.78, down_frames=3, up=1.0, up_frames=4, up_ease=PRESS_UP_EASE,
              sound="tap", note=""):
        """a button is pressed: squash, spring back, recolour. A phone TAP sounds on the finger's RELEASE; a desktop
        CLICK on the press frame (sfx.md). Returns the release time."""
        t = self.snap(t)
        self.to(sel, {"scale": down}, t, self.F(down_frames), "power2.in")
        rel = t + self.F(down_frames)
        self.to(sel, {"scale": up, **({"backgroundColor": colour_to} if colour_to else {})}, rel, self.F(up_frames), up_ease)
        if sound == "tap":
            self.event(rel, "tap", note=note or f"{sel} tapped (on the release)")
        elif sound == "click":
            self.event(t, "click", note=note or f"{sel} clicked")
        return rel

    def ring_pulse(self, sels, t, every, until=None, gap=0.2, frm=1.0, to=1.75, dur=0.62, op=0.85):
        """bursts of rings from t, one burst every `every` s while before `until` (None = one burst), one ring element per
        ring in the burst, `gap` s apart. Silent: the sound belongs to the call or the badge. A ring's cycle is longer
        than its tween, so one ring never overlaps itself (a denser pulse uses another ring element)."""
        sels = [sels] if isinstance(sels, str) else list(sels)
        if every <= dur:
            raise BuildError("ring_pulse: a ring's cycle must be longer than its tween (graphics.md § 14)")
        t1 = t + 1e-6 if until is None else until
        n = 0
        while t < t1:
            for k, s in enumerate(sels):
                self.fromto(s, {"scale": frm, "opacity": op}, {"scale": to, "opacity": 0}, t + k * gap, dur, "power2.out")
            t += every
            n += 1
        return n

    def buzz(self, sel, t, amp=5, step=0.045, reps=5):
        """the phone's vibrate: x +-amp, then home once the shake is done"""
        t = self.snap(t)
        self.fromto(sel, {"x": -amp}, {"x": amp}, t, step, "none", repeat=reps, yoyo=True)
        self.set(sel, {"x": 0}, t + step * (reps + 1) + 0.03)

    def drop_in(self, sel, t, travel, frames=DROP_FRAMES, frm=DROP_FROM, note=""):
        """an interrupting card drops from above (the caller sizes `travel` so its first frame is inside the safe band);
        the soft rise whoosh"""
        self.show(sel, t)
        self.fromto(sel, {"y": -travel, "scale": frm}, {"y": 0, "scale": 1}, t, self.F(frames), DROP_EASE)
        self.event(t, "riseIn", note=note or f"{sel} drops in")

    def exit_in_place(self, sels, t, frames=8, to=0.3):
        """an in-scene exit: shrink IN PLACE and cut on the landing frame (never a fade whose last frame is a near-empty
        panel, never out through the incoming element's slot). Silent."""
        t = self.snap(t)
        for s in ([sels] if isinstance(sels, str) else sels):
            self.to(s, {"scale": to}, t, self.F(frames), EXIT_EASE)
            self.hide(s, t + self.F(frames))

    def bump(self, sel, t, to=1.1, frames=3, sound="bump", note=""):
        """a scale beat on a word, 1 -> to -> 1 (the punchline's last beat; or the thing a sound lands on)"""
        self.fromto(sel, {"scale": 1}, {"scale": to}, t, self.F(frames), "power2.out", yoyo=True, repeat=1)
        if sound:
            self.event(t, sound, note=note or f"{sel} bumps")

    def down_arrow(self, sel, t_on, until_end, drop=60, frm=0.6, frames=7):
        """a down arrow drops on 'below' and bobs to the last frame. Silent (a bob is a micro-motion)."""
        t_on = self.snap(t_on)
        self.show(sel, t_on)
        self.fromto(sel, {"y": -drop, "scale": frm}, {"y": 0, "scale": 1}, t_on, self.F(frames), "back.out(2)")
        half = self.F(max(1, round(ARROW_BOB_S * float(engine.FPS))))      # whole frames, so the two legs never overlap
        t = t_on + self.F(frames + 1)
        while t < until_end - 0.05:                                       # a last bob cut by the comp's end simply holds
            self.to(sel, {"y": ARROW_BOB_PX}, t, half, "sine.inOut")
            self.to(sel, {"y": 0}, t + half, half, "sine.inOut")
            t += 2 * half

    def bars(self, sels, t, gap=0.07, colour=GREEN, sound="blip", note=""):
        """signal bars (or any status row) light one by one, `gap` s apart. The sound says WHAT lit (sfx.md § 4 rung 4):
        a VALUE or connection lighting up = ONE `blip` on the first bar (the hook's bars: his own swap on the
        benchmark, the planned stamp out, one short cut of the working-bed file in); a DEVICE docking or connecting =
        `status-keys` on the first bar layered with `status-chime` on the one that completes the signal (his pair on a
        device joining the network mid-reel). sound=None for bars that ride another sound."""
        sels = [sels] if isinstance(sels, str) else list(sels)
        for i, s in enumerate(sels):
            self.to(s, {"backgroundColor": colour}, t + i * gap, self.F(2))
        if sound == "blip":
            self.event(t, "blip", note=note or "the bars light: a value / connection lighting up")
        elif sound == "device":
            self.event(t, "status-keys", note=note or "the bars light: a device connecting")
            self.event(t + max(0, len(sels) - 2) * gap, "status-chime", note="the signal is up (the chime on the keys)")
        elif sound is not None:
            raise BuildError(f"bars: sound is 'blip', 'device' or None, not {sound!r}")

    def blink(self, sel, t0, t1, period=0.44):
        """a caret's blink, as absolute sets"""
        t = t0
        while t < t1:
            self.hide(sel, t)
            if t + period / 2 < t1:
                self.show(sel, t + period / 2)
            t += period


def _authored(clock, html, css, m, *, bbox, visible0, kind, role, line, copy):
    """an authored split component through the engine (house backdrop, the 0.79 panel fit, 12 fps held, bloom, grain);
    bbox comes in panel px and goes to the engine in frame px, where the content zone is checked"""
    (x0, y0), (x1, y1) = to_frame(bbox[0], bbox[1]), to_frame(bbox[2], bbox[3])
    s = engine.authored(html, "\n".join(m.js), css, "split", id=clock.id, start=clock.start, dur=clock.dur,
                        events=sorted(m.events, key=lambda e: e["at"]), visible0=visible0,
                        bbox=(round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)), units="panel")
    s.meta.update(kind=kind, role=role, line=line, copy=list(copy), component=True)
    return s


# ------------------------------------------------------------------------------------------------------------------
# measuring: type and marks are measured, never assumed (graphics.md § 5, § 11, § 12)
# ------------------------------------------------------------------------------------------------------------------
# the fonts the comp renders with first (a job's gfx/assets/fonts after `engine.py init`, where the client package has
# Inter in SF's place), then the repo's and the system's
_FONT_DIRS = ([KIT.parent / "assets" / "fonts", KIT / "assets" / "fonts"] + [p / "assets" / "fonts" for p in KIT.parents]
              + [Path("/Library/Fonts"), Path("/System/Library/Fonts"), Path.home() / "Library/Fonts"])
_FONT_FILES = {900: ("Display-Black.otf", "SF-Pro-Display-Black.otf", "Inter-Black.otf"),
               700: ("Display-Bold.otf", "SF-Pro-Display-Bold.otf", "Inter-Bold.otf"),
               400: ("Display-Regular.otf", "SF-Pro-Display-Regular.otf", "Inter-Regular.otf"),
               "mono": ("Mono.ttf", "SFNSMono.ttf")}


@functools.lru_cache(maxsize=None)
def _font(weight, px):
    from PIL import ImageFont
    names = _FONT_FILES["mono"] if weight == "mono" else _FONT_FILES[min((900, 700, 400), key=lambda w: (abs(w - weight), -w))]
    for name in names:
        for d in _FONT_DIRS:
            if (d / name).exists():
                return ImageFont.truetype(str(d / name), px)
    return None


def text_w(text, px, weight=700, tracking=0.0, mono=False):
    """a line's rendered width in px: PIL getlength on the font the comp renders with (the comp embeds Black / Bold /
    Regular only, so a 600 renders Bold), else a conservative per-character estimate. Re-measure the LONGEST copy."""
    f = _font("mono" if mono else weight, int(round(px)))
    if f is not None:
        w = f.getlength(text)
    elif mono:
        w = 0.6 * px * len(text)
    else:
        w = sum(px * (0.30 if c in " .,:;!|'il1" else 0.86 if c in "MWmw@" else 0.70 if c.isupper() else 0.56) for c in text)
    return w + tracking * len(text)


def fit_px(text, px, max_w, weight=700, tracking=0.0, mono=False, floor=0.6):
    """the largest size <= px at which the line fits max_w (tracking scales with the size); never below floor x px"""
    size = float(px)
    while text_w(text, size, weight, tracking * size / px, mono) > max_w:
        size -= 1
        if size < px * floor:
            raise BuildError(f"{text!r} cannot fit {max_w:.0f} px above {floor:.0%} of {px:g} px: shorten the copy")
    return int(size)


def _asset(path):
    """(filesystem path, the src a comp references). A comp resolves "assets/..." against the job's gfx/ (engine.init
    links compositions/assets there): pass a mark as "assets/logos/x.png", or as a file under gfx/assets."""
    p = str(path)
    gfx = getattr(engine, "_GFX", None)
    if p.startswith("assets/"):
        fs = Path(gfx) / p if gfx else Path(p)
        return fs, p
    fs = Path(p).resolve()
    if gfx:
        try:
            return fs, fs.relative_to(Path(gfx).resolve()).as_posix()
        except ValueError:
            pass
    return fs, p


@functools.lru_cache(maxsize=None)
def _body(fs):
    """(canvas_w, canvas_h, solid body (x0, y0, x1, y1), full_bleed): the SOLID body (alpha > MARK_SOLID_ALPHA)"""
    from PIL import Image
    bb = engine.solid_body(fs)
    if bb is None:
        raise BuildError(f"{fs}: no solid pixels (alpha > {MARK_SOLID_ALPHA})")
    with Image.open(fs) as im:
        w, h = im.size
        a = im.convert("RGBA").getchannel("A")
        corners = [a.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    return w, h, tuple(bb), tuple(bb) == (0, 0, w, h) and min(corners) > MARK_SOLID_ALPHA


class Icon(str):
    """bare_icon's HTML (a str) plus its geometry: .box (px), .scale, .body (the solid body's rect inside the box)"""


def bare_icon(png, box_px, ident="", shadow=MARK_SHADOW, radius=None, style=""):
    """A real brand mark, BARE (graphics.md § 12): its solid body (alpha > 128, measured with PIL) is scaled to EXACTLY
    box_px on its longer side and centred in a box_px square; the only addition is a drop shadow that follows its alpha.
    Two marks given one box_px come out equal on the render however each file is padded or shadowed. A full-bleed square
    app icon (opaque to its corners) gets the app-icon rounding (0.23 x box), never a tile, ring or glass border."""
    fs, src = _asset(png)
    w, h, (x0, y0, x1, y1), full = _body(str(fs))
    bw, bh = x1 - x0, y1 - y0
    s = box_px / max(bw, bh)
    left, top = (box_px - bw * s) / 2 - x0 * s, (box_px - bh * s) / 2 - y0 * s
    r = radius if radius is not None else (0.23 * box_px if full else 0)
    img = (f'<img src="{src}" alt="" style="position:absolute;left:{left:.1f}px;top:{top:.1f}px;width:{w * s:.1f}px;'
           f'height:{h * s:.1f}px;display:block;max-width:none;{f"border-radius:{r:.0f}px;" if r else ""}'
           f'{f"filter:{shadow};" if shadow else ""}"/>')
    idattr = f' id="{ident}"' if ident else ""
    out = Icon(f'<div class="kit-mark"{idattr} style="position:absolute;width:{box_px}px;height:{box_px}px;{style}">{img}</div>')
    out.box, out.scale = box_px, s
    out.body = ((box_px - bw * s) / 2, (box_px - bh * s) / 2, (box_px + bw * s) / 2, (box_px + bh * s) / 2)
    return out


def _is_dark_mark(fs):
    """does this mark read dark (so it needs inverting on a dark panel)? PNG: the mean luminance of its solid pixels;
    SVG: its declared fills (none declared = black, the SVG default)"""
    p = str(fs)
    if p.lower().endswith(".svg"):
        fills = re.findall(r'fill\s*[:=]\s*"?\s*#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b', Path(p).read_text(errors="ignore", encoding="utf-8"))
        if not fills:
            return True
        lum = []
        for f in fills:
            f = "".join(c * 2 for c in f) if len(f) == 3 else f
            r, g, b = (int(f[i:i + 2], 16) / 255 for i in (0, 2, 4))
            lum.append(0.2126 * r + 0.7152 * g + 0.0722 * b)
        return sum(lum) / len(lum) < 0.4
    from PIL import Image
    with Image.open(p) as im:   # tobytes, never getdata(): Pillow 14 (2027-10-15) removes it, on every Pillow this runs
        b = im.convert("RGBA").tobytes()
    px = [(b[i], b[i + 1], b[i + 2]) for i in range(0, len(b), 4) if b[i + 3] > MARK_SOLID_ALPHA]
    return bool(px) and sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px) / len(px) / 255 < 0.4


def _mark_aspect(fs):
    """w / h of a wordmark: an SVG's viewBox (or width/height), a PNG's solid body"""
    p = str(fs)
    if p.lower().endswith(".svg"):
        txt = Path(p).read_text(errors="ignore", encoding="utf-8")
        vb = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', txt)
        if vb:
            return float(vb.group(1)) / float(vb.group(2))
        w, h = (re.search(rf'\b{k}="([\d.]+)', txt) for k in ("width", "height"))
        if w and h:
            return float(w.group(1)) / float(h.group(1))
        raise BuildError(f"{p}: no viewBox or width/height to size the wordmark by")
    _, _, (x0, y0, x1, y1), _ = _body(p)
    return (x1 - x0) / (y1 - y0)


def to_frame(x, y):
    """a panel point -> frame px (the engine's 0.79 fit about the seam centre)"""
    return 540 + (x - 540) * PANEL_TO_FRAME, SEAM + (y - SEAM) * PANEL_TO_FRAME


def panel_y(frame_y):
    """a frame y -> the panel y that lands there"""
    return SEAM + (frame_y - SEAM) / PANEL_TO_FRAME


# ------------------------------------------------------------------------------------------------------------------
# masked values: never digits (graphics.md § 5, § 12)
# ------------------------------------------------------------------------------------------------------------------
# named groupings: the value's REAL shape, so it reads as what it is without a digit on screen. A phone number is
# `+• (•••) •••-••••`: ONE dot after the plus reads as a country code, two did not (graphics.md § 5).
SEPS = {"phone": ["+", " (", ") ", "-", ""]}


def _seps(groups, seps):
    """None = the groups spaced apart; a SEPS name; or len(groups) + 1 separators (before, between..., after)"""
    if seps is None:
        return [""] + [" "] * (len(groups) - 1) + [""]
    if isinstance(seps, str):
        if seps not in SEPS:
            raise BuildError(f"masked: no grouping {seps!r} (named: {sorted(SEPS)}); pass the separators as a list")
        seps = SEPS[seps]
    seps = list(seps)
    if len(seps) != len(groups) + 1:
        raise BuildError("masked: seps must have len(groups) + 1 entries")
    return seps


def masked(groups, glyph="dot", seps=None):
    """A real value shown as MASK GLYPHS in its real grouping, never digits: nothing on screen can be dialled or read as a
    real number (the don't-show list applies to what the editor draws as much as to what it records). groups = the
    digit count per group (e.g. [1, 3, 3, 4] for a phone number); glyph = "dot" (a round mark the claim pops one by one)
    or one non-digit character; seps = a SEPS name ("phone"), len(groups) + 1 separators, or None (spaced groups).
    Returns HTML with NO digit anywhere in it (no ids, no inline sizes): the claim targets the dots by position."""
    seps = _seps(groups, seps)
    if any(re.search(r"\d", s) for s in seps) or (glyph != "dot" and (re.search(r"\d", glyph) or len(glyph) != 1)):
        raise BuildError("masked: a masked value never carries a digit")
    dot = "<s></s>" if glyph == "dot" else f'<s class="ch">{htmlmod.escape(glyph)}</s>'
    out = []
    for i, g in enumerate(groups):
        if seps[i].strip():
            out.append(f"<b>{htmlmod.escape(seps[i].strip())}</b>")
        elif seps[i]:
            out.append('<i class="gap"></i>')
        out.append(dot * g)
    if seps[-1].strip():
        out.append(f"<b>{htmlmod.escape(seps[-1].strip())}</b>")
    return "".join(out)


def masked_text(groups, seps=None, glyph="•"):
    """the same mask as plain TEXT, for a line that is type (a caller shown by number on the call card):
    masked_text([1, 3, 3, 4], "phone") = "+• (•••) •••-••••" """
    seps = _seps(groups, seps)
    if re.search(r"\d", "".join(seps) + glyph):
        raise BuildError("masked_text: a masked value never carries a digit")
    return "".join(s + glyph * g for s, g in zip(seps, groups)) + seps[-1]


class Part:
    """A piece a container places (the claim object under the hook): size (panel px), body, css, its own Motion, the
    on-screen copy, the measured inner row width, and `docks`: HTML the container positions on an anchor it owns
    (dock(cx, cy, box) -> (under, over): e.g. rings under the hero icon and a badge over it)."""

    def __init__(self, w, h, body, css, m, copy=(), cls="", ident="", docks=(), inner_w=0):
        self.w, self.h, self.body, self.css, self.m = w, h, body, css, m
        self.copy, self.cls, self.ident, self.docks, self.inner_w = list(copy), cls, ident, list(docks), inner_w

    def place(self, x, y):
        return (f'<div class="{self.cls}" id="{self.ident}" style="left:{x:.0f}px;top:{y:.0f}px;width:{self.w}px;'
                f'height:{self.h}px;">{self.body}</div>')


MV_CSS = """
.kv-pill{position:absolute;border-radius:78px;background:rgba(18,20,28,0.95);display:flex;align-items:center;justify-content:center;
  gap:7px;padding:0 40px;opacity:0;box-shadow:0 24px 60px rgba(0,0,0,0.5),0 0 0 2px rgba(255,255,255,0.10) inset;}
.kv-pill b{font-family:@FM@;font-weight:700;font-size:60px;color:#fff;letter-spacing:0;margin:0 5px;line-height:1;}
.kv-pill s{display:block;width:30px;height:30px;border-radius:50%;background:@SKY@;text-decoration:none;transform:scale(0);flex:none;}
.kv-pill s.ch{width:auto;height:auto;border-radius:0;background:none;font-family:@FM@;font-weight:700;font-size:60px;line-height:1;color:@SKY@;}
.kv-pill i.gap{display:block;width:12px;flex:none;}
.kv-pill .kv-lead{flex:none;}
.kv-pill .kv-sig{display:flex;align-items:flex-end;gap:7px;height:72px;margin-left:22px;flex:none;}
.kv-pill .kv-sig:empty{display:none;}
.kv-pill .kv-sig i{display:block;width:17px;border-radius:5px;background:rgba(255,255,255,0.22);}
.kv-pill .kv-sig i:nth-child(1){height:27px;} .kv-pill .kv-sig i:nth-child(2){height:46px;}
.kv-pill .kv-sig i:nth-child(3){height:65px;} .kv-pill .kv-sig i:nth-child(4){height:84px;}
.kv-pill .kv-pill-mask{display:contents;}
.kv-badge{position:absolute;width:112px;height:112px;border-radius:50%;background:@OK@;display:flex;align-items:center;justify-content:center;
  opacity:0;box-shadow:0 14px 34px rgba(0,0,0,0.5);}
.kv-ring{position:absolute;border-radius:50%;border:6px solid rgba(47,245,138,0.9);opacity:0;}
""".replace("@FM@", FM).replace("@SKY@", SKY).replace("@OK@", OS_ACCEPT)


class Claim:
    """masked_value's spec: built on the host scene's clock by the container (hook_stack), since its beats are words"""

    def __init__(self, fn):
        self.build = fn


PHONE_NUMBER = dict(seps="phone", lead="phone", bars=True, badge="phone")   # a number assigned: grouping, lead, signal, badge


def masked_value(*args, bars=False, glyph="dot", seps=None, lead=None, badge="dot", w=940, h=156, uid="kv"):
    """A VALUE BEING ASSIGNED, performed: a pill (w x h, radius h/2) holding the value masked in its real grouping, which
    FILLS on the spoken word. It is the claim object for a hook whose premise is "X got its own <value>"; any other
    premise builds its own object (graphics.md § 5). The defaults carry no premise: spaced groups, no lead glyph, no
    bars, no badge. A phone number is one named preset: masked_value(groups, beats, **PHONE_NUMBER).

    beats (timeline word starts): value = the word the value is named on: the dots pop across it, a tap run of about five
    taps (a digit keyed is a phone touch, never keyboard typing), starting VALUE_KEY_LEAD_S ahead of the word's beat (a
    designed lead, written on the first tap's sfx-hand row as `sync_offset`: the lead as built, shorter when the pill
    lands late and its first dot waits for it); live = optional, the FIRST word of the
    payoff phrase: a green badge lands on the hero icon and rings every 0.72 s (`live`: a UI chime, green is not completion, never the
    bell), and it warns under BADGE_HOLD_MIN_S of ringing left to read; enter = optional (default the pill rises 0.45 s
    before the value word). bars = signal bars light 0.07 s apart once the value is in, with ONE `blip` (a value lighting
    up: his sound on the benchmark hook; keys + chime are a DEVICE connecting, Motion.bars(sound="device")).
    lead = None, a glyph name ("phone") or HTML, 56 px in sky before the dots. badge = the badge's glyph ("dot", a
    glyph name, or HTML). seps = a SEPS name, separators, or None (masked()).
    masked_value(groups, beats) returns a Claim that hook_stack builds on its own clock (and docks the badge on the hero
    icon); masked_value(clock, groups, beats) returns the Part built on that clock."""
    clock0 = args[0] if args and isinstance(args[0], Clock) else None
    groups, beats = args[1:3] if clock0 else args[:2]

    def build(clock):
        m = Motion()
        n = sum(groups)
        seps_ = _seps(groups, seps)
        dots = masked(groups, glyph, seps_)
        lead_html = f'<div class="kv-lead">{glyph_svg(lead, 56, SKY)}</div>' if lead else ""
        # [lead][mask][status slot]: the slot holds the bars when asked and collapses when empty (.kv-sig:empty)
        body = (lead_html + f'<span class="kv-pill-mask">{dots}</span>'
                + f'<div class="kv-sig" id="{uid}-sig">{"<i></i>" * 4 if bars else ""}</div>')
        # the row sits INSIDE the pill, measured (an icon row once hung outside its pill: "Is that an error, or did you
        # mean to do that?", you 2026-09-21)
        kids = (1 if lead else 0) + sum(1 for s in seps_ if s) + n + (1 if bars else 0)
        inner = ((56 if lead else 0) + n * 30
                 + sum(text_w(s.strip(), 60, 700, mono=True) + 10 for s in seps_ if s.strip())
                 + sum(12 for s in seps_ if s and not s.strip()) + (22 + 4 * 17 + 3 * 7 if bars else 0) + 7 * max(0, kids - 1))
        if inner > w - 80:
            raise BuildError(f"masked_value: the row is {inner:.0f} px, the pill holds {w - 80}: fewer groups or a wider pill")
        nu = clock.beat(beats["value"])
        enter = clock.beat(beats["enter"]) if beats.get("enter") is not None else max(0.2, nu - 0.45)
        pill = f"#{uid}"
        m.row_in(pill, enter, dy=50, frm=0.92, frames=7, ease="back.out(1.5)", note="the claim object rises in")
        d0 = max(nu - VALUE_KEY_LEAD_S, m.snap(enter) + m.F(7))         # the pill has landed before its first dot
        dot_t = [d0 + i * 0.05 for i in range(n)]
        for i, t in enumerate(dot_t):
            m.to(f"{pill} s:nth-of-type({i + 1})", {"scale": 1}, t, m.F(3), "back.out(3)")
        taps = max(1, round(n / 2.2))                                  # a texture of taps, not one per digit
        key_lead = round(d0 - nu, 4)                                   # -VALUE_KEY_LEAD_S, less if the pill lands late
        # the row records the lead as BUILT: a late pill's first dot waits for it, so its lead is shorter and the note
        # says so (it once still named VALUE_KEY_LEAD_S over the shorter number)
        why = ("VALUE_KEY_LEAD_S" if abs(-key_lead - VALUE_KEY_LEAD_S) < 1e-3 else
               f"shorter than VALUE_KEY_LEAD_S, {VALUE_KEY_LEAD_S:g} s: the pill lands late and its first dot waits for it")
        for k in range(taps):
            first = k == 0 and key_lead < 0                            # the tap that answers the value word
            m.event(dot_t[0] + (dot_t[-1] - dot_t[0]) * (k / (taps - 1) if taps > 1 else 0), "tap",
                    note=(f"the value keyed in (a tap run), a designed lead of {-key_lead:g} s on the value word's "
                          f"beat ({why})" if first else "the value keyed in (a tap run)"),
                    sync_offset=key_lead if first else None)
        done = dot_t[-1] + 0.13
        if bars:
            m.bars([f"#{uid}-sig i:nth-child({s + 1})" for s in range(4)], done, 0.07, GREEN, "blip",
                   note="the signal bars light: the value is live")
        docks = []
        if beats.get("live") is not None:
            live = max(clock.beat(beats["live"]), done + (0.28 if bars else 0.0))
            if clock.dur - live < BADGE_HOLD_MIN_S:
                print(f"⚠ {clock.id}: the live badge lands {clock.dur - live:.2f} s before the graphic ends (under "
                      f"{BADGE_HOLD_MIN_S} s to read it ringing): land it on the FIRST word of the payoff phrase")
            badge_id = f"#{uid}-badge"
            m.show(badge_id, live)
            m.fromto(badge_id, {"scale": 0}, {"scale": 1}, live, m.F(7), "back.out(2.4)")
            m.ring_pulse([f"#{uid}-r1", f"#{uid}-r2"], m.snap(live) + 0.1, 0.72, clock.dur - 0.3, gap=0.2, frm=0.8, to=1.5,
                         dur=0.6, op=0.9)
            m.event(live, "live", note="the live badge lands: reachable / live now")

            def dock(cx, cy, box):                                     # the badge on the anchor's lower right, rings round it
                d = round(box * 4 / 3)
                ring = (f'left:{cx - d / 2:.0f}px;top:{cy - d / 2:.0f}px;width:{d}px;height:{d}px;')
                under = (f'<div class="kv-ring" id="{uid}-r1" style="{ring}"></div>'
                         f'<div class="kv-ring" id="{uid}-r2" style="{ring}"></div>')
                over = (f'<div class="kv-badge" id="{uid}-badge" style="left:{cx + 0.46 * box - 56:.0f}px;'
                        f'top:{cy + 0.4267 * box - 56:.0f}px;">{glyph_svg(badge, 62)}</div>')
                return under, over
            docks.append(dock)
        return Part(w, h, body, MV_CSS, m, copy=[], cls="kv-pill", ident=uid, docks=docks, inner_w=inner)
    return build(clock0) if clock0 else Claim(build)


def _pop_tail():
    """how long the hero pop sounds (its sfx.json slice): a beat inside it is already carried by the pop"""
    a, b = engine.sfx_events()[0]["pop-hero"]["slices"][0]
    return float(b) - float(a)


# ------------------------------------------------------------------------------------------------------------------
# THE HOOK: the one title lockup of the video (graphics.md § 5)
# ------------------------------------------------------------------------------------------------------------------
HOOK_CSS = """
.kh-name{position:absolute;left:0;width:1080px;text-align:center;}
.kh-name b{display:inline-block;font-family:@FD@;font-weight:900;line-height:1;color:#fff;opacity:0;white-space:nowrap;}
""".replace("@FD@", FD)


def hook_stack(ctx, icon, name, claim, beats=None, *, id=None, start=None, end=None, dur=None, box=300, uid="kh", line=""):
    """THE HOOK LOCKUP: one centred vertical stack in the split zone, the reel's first concept lockup (graphics.md § 5).
    The subject's REAL icon, bare (bare_icon), pops on frame 0 (the hook has no empty plate); its NAME in hero type
    rises 3 frames in through the registry; the CLAIM object sits beneath and performs the premise on its own words (masked_value for a
    value being assigned; any Part for another premise: its own w/h/body/css/Motion, placed and asserted the same). Nothing
    restates the caption: no chip, no subtitle (a headline chip "competes with the caption", you 2026-09-22). The stack
    is lifted HOOK_LIFT so the caption keeps the seam ("move the hook visual up too so they don't collide").
    Asserts every child inside its container (the name inside the panel, the claim's row inside its pill) and the stack
    inside the split content zone. icon = "assets/logos/<mark>.png" (or a file under gfx/assets). beats: optional
    {"name": word} to land the name on a word instead of frame 3.
    Sound: pop-hero on the icon, then the claim's own. The NAME is silent while it rises inside the hero pop's tail
    (data-sfx="none"): the pop already carries that beat, and a word snip 3 frames after it is a second accent on one
    beat (sfx.md law 11; his approved hook leaves the name silent). A name landed on its own later word keeps the house
    word snip."""
    clock = _clock(ctx, id, start, end, dur)
    beats = beats or {}
    part = claim.build(clock) if isinstance(claim, Claim) else claim
    m = Motion()
    word = name.upper()
    t_name = clock.beat(beats["name"]) if beats.get("name") is not None else m.F(3)
    quiet = ' data-sfx="none"' if t_name < _pop_tail() else ""   # the name rides the hero pop: one accent, one beat
    px = fit_px(word, HERO_PX, 1080 - 2 * 60, HERO_WEIGHT, HERO_TRACK)
    lift = HOOK_LIFT / PANEL_TO_FRAME                                   # frame px -> panel px
    top = 215 - lift                                                     # the approved stack: icon 215, name 552, claim 712 (+lift)
    y_name = top + box + 37
    y_claim = y_name + px + 34
    ix, cx0 = (1080 - box) / 2, (1080 - part.w) / 2
    if text_w(word, px, HERO_WEIGHT, HERO_TRACK) > 1080 - 2 * 60:
        raise BuildError(f"{id}: the hook name overflows the panel")
    if part.inner_w > part.w - 80 or cx0 < 0:
        raise BuildError(f"{id}: the claim's row overflows its pill, or the pill the panel")
    fy0, fy1 = to_frame(0, top)[1], to_frame(0, y_claim + part.h)[1]
    if fy0 < ZONE_TOP or fy1 > ZONE_BOTTOM:
        raise BuildError(f"{id}: the hook stack spans frame y{fy0:.0f}-{fy1:.0f}, outside the zone y{ZONE_TOP}-{ZONE_BOTTOM}: "
                         "a shorter claim, or a smaller icon")
    cx, cy = 540, top + box / 2
    docked = [d(cx, cy, box) for d in part.docks]
    ic = bare_icon(icon, box, ident=f"{uid}-icon", style=f"left:{ix:.0f}px;top:{top:.1f}px;opacity:0;")
    html = ("".join(u for u, _ in docked) + ic + "".join(o for _, o in docked)
            + f'<div class="kh-name" style="top:{y_name:.1f}px;"><b id="{uid}-name"{quiet} '
              f'style="font-size:{px}px;letter-spacing:{HERO_TRACK * px / HERO_PX:g}px;">{htmlmod.escape(word)}</b></div>'
            + part.place(cx0, y_claim))
    m.pop_in(f"#{uid}-icon", 0.0, "hero", frm=0.5, rot=-10, frames=8, back=1.7, note="the subject's icon: the hook opens on it")
    m.rise_in(f"#{uid}-name", t_name, px=px)
    m.js += part.m.js
    m.events += part.m.events
    ring_d = round(box * 4 / 3) if part.docks else 0
    bbox = (min(ix, cx0), min(top, cy - ring_d / 2), max(ix + box, cx0 + part.w), y_claim + part.h)
    return _authored(clock, html, HOOK_CSS + part.css, m, bbox=bbox, visible0=[f"#{uid}-icon"], kind="ui-enactment",
                     role="hook", line=line, copy=[word] + part.copy)


# ------------------------------------------------------------------------------------------------------------------
# THE CALL CARD: an OS-style call over the wide face, driven by the REAL voice (graphics.md § 3)
# ------------------------------------------------------------------------------------------------------------------
CALL_CSS = """
.kc-card{position:absolute;left:70px;width:940px;border-radius:64px;background:rgba(18,20,28,0.92);opacity:0;
  box-shadow:0 30px 70px rgba(0,0,0,0.55),0 0 0 2px rgba(255,255,255,0.10) inset;display:flex;align-items:center;padding:0 34px;gap:26px;}
.kc-card .kc-av{position:relative;width:132px;height:132px;border-radius:50%;background:@DISC@;display:flex;align-items:center;justify-content:center;flex:none;}
.kc-card .kc-ring{position:absolute;left:0;top:0;width:132px;height:132px;border-radius:50%;border:4px solid rgba(47,245,138,0.9);opacity:0;}
.kc-card .kc-ini{font-family:@FD@;font-weight:700;font-size:58px;color:#fff;}
.kc-card .kc-who{flex:1;min-width:0;}
.kc-card .kc-who b{display:block;font-family:@FD@;font-weight:700;line-height:1.05;color:#fff;white-space:nowrap;}
.kc-card .kc-sub{position:relative;height:40px;margin-top:6px;font-family:@FM@;font-weight:700;font-size:28px;letter-spacing:2px;text-transform:uppercase;}
.kc-card .kc-sub span{position:absolute;left:0;top:0;white-space:nowrap;}
.kc-card .kc-in{color:@MUTED@;} .kc-card .kc-live{color:@SKY@;opacity:0;} .kc-card .kc-end{color:@MUTED@;opacity:0;}
.kc-card .kc-btns{display:flex;gap:22px;flex:none;}
.kc-card .kc-bt{width:112px;height:112px;border-radius:50%;display:flex;align-items:center;justify-content:center;}
.kc-card .kc-no{background:@NO@;} .kc-card .kc-yes{background:@OK@;}
.kc-card .kc-wave{position:absolute;right:40px;top:50%;height:120px;margin-top:-60px;display:flex;align-items:center;gap:7px;opacity:0;}
.kc-card .kc-wave i{display:block;width:9px;height:120px;border-radius:5px;background:@SKY@;transform:scaleY(0.07);transform-origin:50% 50%;}
""".replace("@DISC@", AVATAR_DISC).replace("@FD@", FD).replace("@FM@", FM).replace("@MUTED@", MUTED) \
   .replace("@SKY@", SKY).replace("@NO@", OS_DECLINE).replace("@OK@", OS_ACCEPT)
WAVE_BARS = 26


def call_card(ctx, name, avatar, crown_y, ring_from=None, answer_at=None, voice_spans_raw=None, h=212, *, id=None,
              start=None, end=None, dur=None, app=None, envelope=None, outgoing=False, enter=True, timer_from=0.0,
              ended_at=None, exit=True, uid="kc", line=""):
    """A CALL CARD over the wide face (family overlay: timeline rate, never stepped, because its waveform is locked to
    live audio). Frame px. The footage under it is never punched in: the card is placed against the wide shot's measured
    crown, so the face is never covered. The same card is reused wherever a line says the agent calls, so it becomes a
    motif, and ONE call is one card however many layout breaks cut through it.

    crown_y: the measured hair top on the wide shot (frame px): the card's bottom sits CALL_CROWN_GAP above it and its
      drop starts inside the safe band (never above y204); a crown too high for the card raises.
    answer_at: the CUT where the other voice starts (timeline s). Until then it rings (a burst of two rings every 0.78 s);
      then the buttons fade and the live timer and the waveform take over. None = the call is already live when the card
      lands (no rings, no ring sound).
      - INCOMING (default): the card buzzes +-5 px with each burst, the sub line reads INCOMING CALL, and the accept is
        pressed so its release lands on the cut.
      - outgoing=True (he or the agent places the call): the sub line reads CALLING..., one red end disc, no buzz and no
        press: the other side picks up on the cut.
    ring_from: the WORD where the speech or the picture says it rings or starts calling (it may lead the card; default
      the card's start): the ring (incoming, hard-cut at the answer tap, the tap following it) or the soft calling bed
      (outgoing, resolving on the pick-up) runs from there.
    A call CONTINUED across a layout break (a second cell of the same call): enter=False (the card is simply there on
      the cut: no second drop, no second whoosh) and timer_from = the seconds the call has already run, so the timer
      carries on instead of restarting at 00:00. The cell before it passes exit=False, so the break is the only change.
    ended_at: the timeline s he hangs up (the other voice's last word, or the picture): the timer stops, the sub line
      reads CALL ENDED, the waveform fades; the card holds that state to its exit, so a wordless reaction after the call
      never shows a live timer. Silent: the hang-up is his gesture in the footage, and the call's real audio carries it.
    voice_spans_raw: [(raw_start, raw_end)] of the OTHER voice on the RAW clock; None = transcript/voices.json. The
      waveform is that audio's envelope through the EDL (audio_envelope), 26 bars scrolling right to left, and it rests
      flat while the host talks. envelope = a precomputed {timeline frame: level} instead.
    name: what the other party IS on the call: the name it answers with (heard in the audio, so it is evidence, not an
      invented business name), or the number masked (masked_text(groups, "phone")); never made up. avatar = inline SVG,
      a mark's asset path, or None (its initial; a person glyph for a number). app: an optional product name for the
      ringing sub line ("<app> · incoming call").
    Sound: riseIn on the drop (none when enter=False); incoming: ring (dur = to the answer tap) and the tap on the
    release; outgoing: the calling bed to the pick-up. Nothing else while the other voice talks: the call is the proof
    (sfx.md)."""
    clock = _clock(ctx, id, start, end, dur, family="overlay")
    m = Motion()
    fps, dur_ = clock.fps, clock.dur
    nfr = clock.n
    bottom = float(crown_y) - CALL_CROWN_GAP
    top = bottom - h
    if top < CALL_TOP_MIN:
        raise BuildError(f"{id}: the crown y{crown_y} leaves no room above it (the card would start at y{top:.0f}, above "
                         f"y{CALL_TOP_MIN}): place it over a wider framing, or a shorter card")
    trav = top - CALL_TOP_MIN
    live0 = 0.0 if answer_at is None else clock.cut(answer_at)
    if live0 >= dur_:
        raise BuildError(f"{id}: the answer lands after the card ends: end the card later, or build the call as two cells")
    off = None if ended_at is None else clock.cut(ended_at)
    if off is not None and not live0 + 0.5 <= off <= dur_ - m.F(1):
        raise BuildError(f"{id}: ended_at must fall at least 0.5 s after the call goes live and inside the card")
    # the text columns, measured: while it rings the text runs to the buttons; once live, to the waveform that takes
    # their place, so the name is sized for the narrower live column
    text_left = 34 + 132 + 26
    wave_left = 940 - 40 - (WAVE_BARS * 9 + (WAVE_BARS - 1) * 7)
    n_btn = 1 if outgoing else 2
    col_live, col_ring = wave_left - 12 - text_left, 940 - 34 - (n_btn * 112 + (n_btn - 1) * 22) - 26 - text_left
    npx = fit_px(name, 58, col_live, 700, -1)
    state = "calling…" if outgoing else "incoming call"
    sub_in = f"{app} · {state}" if app else state
    if answer_at is not None and text_w(sub_in.upper(), 28, 700, 2, mono=True) > col_ring:
        raise BuildError(f"{id}: {sub_in!r} overflows the {col_ring} px text column")
    if avatar is None:
        ini = next((c for c in name if c.isalpha()), "")
        av = f'<div class="kc-ini">{htmlmod.escape(ini.upper())}</div>' if ini else icon_svg(PERSON, 84)
    elif str(avatar).lstrip().startswith("<"):
        av = str(avatar)
    else:
        av = bare_icon(avatar, 104, style="position:relative;")
    # the call timer, one span per shown second: second k shows once the call has run k s (timer_from carries a call on)
    t_stop = dur_ if off is None else off
    timer, k = [], int(math.floor(timer_from + 1e-9))
    while not timer or live0 + (k - timer_from) < t_stop - 1e-9:
        timer.append((k, live0 + max(0.0, k - timer_from), live0 + (k + 1 - timer_from)))
        k += 1
    sub = (f'<span class="kc-in" id="{uid}-in">{htmlmod.escape(sub_in)}</span>'
           + "".join(f'<span class="kc-live" id="{uid}-t{k}">on call · {k // 60:02d}:{k % 60:02d}</span>' for k, _, _ in timer)
           + (f'<span class="kc-end" id="{uid}-end">call ended</span>' if off is not None else ""))
    btns = (f'<div class="kc-bt kc-no">{icon_svg(PHONE, 58, rot=135)}</div>'
            + ("" if outgoing else f'<div class="kc-bt kc-yes" id="{uid}-yes">{icon_svg(PHONE, 58)}</div>'))
    html = (f'<div class="kc-card" id="{uid}" style="top:{top:.0f}px;height:{h}px;"><div class="kc-av">'
            f'<div class="kc-ring" id="{uid}-r1"></div><div class="kc-ring" id="{uid}-r2"></div>{av}</div>'
            f'<div class="kc-who"><b style="font-size:{npx}px;letter-spacing:{-npx / 58:.2f}px;">{htmlmod.escape(name)}</b>'
            f'<div class="kc-sub">{sub}</div></div>'
            f'<div class="kc-btns" id="{uid}-btns">{btns}</div>'
            f'<div class="kc-wave" id="{uid}-wave">' + "<i></i>" * WAVE_BARS + "</div></div>")
    card = f"#{uid}"
    if enter:
        m.drop_in(card, 0.0, trav, note="the call card drops in")
    else:
        m.show(card, 0.0)                                               # the same call after a layout break: no entrance
    if answer_at is not None:
        if live0 < (0.5 if enter else m.F(2)):
            raise BuildError(f"{id}: the answer lands {live0:.2f} s in, before the card has rung (answer_at too close)")
        t = 0.30 if enter else 0.0
        while t < live0 - 0.25:                                         # rings (+ the buzz on an incoming call) until answered
            for k, r in enumerate((f"#{uid}-r1", f"#{uid}-r2")):
                m.fromto(r, {"scale": 1, "opacity": 0.85}, {"scale": 1.75, "opacity": 0}, t + k * 0.2, 0.62, "power2.out")
            if not outgoing:
                m.buzz(card, t)
            t += 0.78
        r0 = 0.0 if ring_from is None else clock.beat(ring_from) if float(ring_from) >= clock.start else \
            -(clock.start - float(ring_from) + engine.EVENT_LEAD_S)
        lead = f" (the speech says it {'calls' if outgoing else 'rings'} {-r0:.2f} s before the card: a kit row cannot " \
               "start before its graphic, nudge it by hand)" if r0 < 0 else ""
        if outgoing:
            m.event(max(0.0, r0), "calling", dur=live0 - max(0.0, r0), note="calling until the other side picks up" + lead)
        else:
            rel = m.press(f"#{uid}-yes", max(0.0, live0 - 0.16), down=0.80, down_frames=3, up=1.12, up_frames=3,
                          up_ease="power2.out", sound="tap", note="the accept is tapped: the call connects")
            m.event(max(0.0, r0), "ring", dur=rel - max(0.0, r0), note="the phone rings until the answer" + lead)
        m.to(f"#{uid}-btns", {"opacity": 0, "x": 40}, live0, m.F(5), "power2.in")
        m.hide(f"#{uid}-in", live0)
        wave_in = live0 + 0.22                                          # after the buttons have faded (5 frames)
    else:
        m.set(f"#{uid}-btns", {"opacity": 0}, 0.0)
        m.hide(f"#{uid}-in", 0.0)
        wave_in = 0.12 if enter else 0.0
    if wave_in:
        m.to(f"#{uid}-wave", {"opacity": 1}, wave_in, m.F(4))
    else:
        m.set(f"#{uid}-wave", {"opacity": 1}, 0.0)
    for k, on, nxt in timer:
        m.show(f"#{uid}-t{k}", on)
        if nxt < t_stop - 1e-9:
            m.hide(f"#{uid}-t{k}", nxt)
        elif off is not None:
            m.hide(f"#{uid}-t{k}", off)                                  # the timer stops where he hangs up
    if off is not None:
        m.show(f"#{uid}-end", off)
        m.to(f"#{uid}-wave", {"opacity": 0}, off, m.F(4))
    if envelope is None:
        job = clock.job
        envelope = audio_envelope(job, voice_spans_raw, fps) if job is not None else {}
    f0 = engine.frames(clock.start)
    lvl = [float(envelope.get(f0 + k, 0.0)) for k in range(nfr + WAVE_BARS + 2)]
    last = [None] * WAVE_BARS
    for f in range(engine.frames(live0), nfr if off is None else engine.frames(off)):   # bar j = the level (NB-1-j) frames ago
        for j in range(WAVE_BARS):
            back = f - (WAVE_BARS - 1 - j)
            v = lvl[back] if back >= 0 else 0.0
            shape = 0.55 + 0.45 * (1 - abs((j - (WAVE_BARS - 1) / 2) / ((WAVE_BARS - 1) / 2)) ** 1.6)
            sy = round(max(0.07, min(1.0, v * shape * (0.82 + 0.18 * ((j * 7 + f * 3) % 5) / 4))), 3)
            if sy != last[j]:
                m.set(f"#{uid}-wave i:nth-child({j + 1})", {"scaleY": sy}, engine.fsec(f))
                last[j] = sy
    if exit:
        m.to(card, {"y": -trav, "opacity": 0}, dur_ - m.F(7), m.F(7), EXIT_EASE)
    s = engine.overlay(html, "\n".join(m.js), CALL_CSS, id=clock.id, start=clock.start, dur=clock.dur,
                       events=sorted(m.events, key=lambda e: e["at"]), visible0=[card], bbox=(70, round(top), 1010, round(bottom)))
    copy = [name] + ([sub_in.upper()] if answer_at is not None else []) + ["ON CALL"] + (["CALL ENDED"] if off is not None else [])
    s.meta.update(kind="call-ui", role="demo", line=line, copy=copy, component=True)
    return s


def audio_envelope(job, raw_spans=None, fps=None, gamma=0.65, release=0.7, pct=97, sr=16000):
    """The REAL voice's envelope per TIMELINE frame: {frame: level 0..1}. raw_spans = [(raw_start, raw_end)] or
    [(clip, raw_start, raw_end)] on the RAW clock (None = every span in transcript/voices.json); each is mapped through the
    job's EDL (transcript/cuts.json) onto the timeline. Per frame: the RMS of that frame's audio (ffmpeg, mono), raised to
    `gamma`, fast attack / slow release (level = x on a rise, else release x prev + (1 - release) x x), normalised to the
    pct-th percentile and clipped. Calibrated on the benchmark's approved waveform (mean error 0.012 over 126 frames).
    Frames the cut removed are simply absent: the card rests flat there."""
    job = Path(job)
    fps = float(fps or engine.FPS)
    if raw_spans is None:
        vp = job / "transcript" / "voices.json"
        if not vp.exists():
            return {}
        raw_spans = [(s.get("clip"), float(s["start"]), float(s["end"])) for s in json.loads(vp.read_text(encoding="utf-8")).get("spans", [])]
    segs = json.loads((job / "transcript" / "cuts.json").read_text(encoding="utf-8"))["segments"]
    rows, t = [], 0.0
    for s in segs:
        rows.append((t, s))
        t += s["end"] - s["start"]
    rms = {}
    for span in raw_spans:
        clip, a, b = (span if len(span) == 3 else (None, *span))
        for t0, s in rows:
            if clip and s.get("clip") and os.path.basename(str(clip)) != os.path.basename(s["clip"]):
                continue
            lo, hi = max(float(a), s["start"]), min(float(b), s["end"])
            if hi - lo <= 1.0 / fps:
                continue
            media = job / "raw" / s["clip"] if s.get("clip") else None
            if media is None or not media.exists():
                cands = sorted(p for p in (job / "raw").glob("*") if p.is_file())
                if not cands:
                    raise BuildError(f"{job}/raw: no media to read the voice from")
                media = cands[0]
            pcm = _pcm(media, lo, hi - lo, sr)
            fa = math.ceil((t0 + lo - s["start"]) * fps - 1e-6)
            fb = math.floor((t0 + hi - s["start"]) * fps + 1e-6)
            for f in range(fa, fb):
                src = s["start"] + f / fps - t0                        # this frame's source time
                i0, i1 = int(round((src - lo) * sr)), int(round((src - lo + 1.0 / fps) * sr))
                seg = pcm[max(0, i0):max(0, min(len(pcm), i1))]
                rms[f] = math.sqrt(sum(x * x for x in seg) / len(seg)) if len(seg) else 0.0
    if not rms:
        return {}
    out, prev, pf = {}, 0.0, None
    for f in sorted(rms):
        x = rms[f] ** gamma
        if pf is None or f != pf + 1:
            prev = 0.0                                                  # a new run: no release carried across a gap
        prev = x if x >= prev else release * prev + (1 - release) * x
        out[f], pf = prev, f
    vals = sorted(out.values())
    ref = vals[min(len(vals) - 1, int(round(pct / 100 * (len(vals) - 1))))] or 1.0
    return {f: round(min(1.0, v / ref), 3) for f, v in out.items()}


def _pcm(media, t0, dur, sr):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.4f}", "-t", f"{dur + 0.05:.4f}", "-i", str(media), "-vn",
                        "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True)
    if r.returncode:
        raise BuildError(f"audio_envelope: ffmpeg could not read {media}")
    a = array("f")
    a.frombytes(r.stdout[: len(r.stdout) // 4 * 4])
    if sys.byteorder != "little":
        a.byteswap()
    return a


# ------------------------------------------------------------------------------------------------------------------
# THE COMMENT CTA: a platform DM thread, seen from the VIEWER's side (graphics.md § 6)
# ------------------------------------------------------------------------------------------------------------------
THREAD_CSS = """
.kt-cmp{position:absolute;left:90px;bottom:157px;width:900px;height:128px;border-radius:64px;background:rgba(18,20,28,0.96);display:flex;
  align-items:center;padding:0 18px 0 22px;gap:22px;opacity:0;box-shadow:0 14px 34px rgba(0,0,0,0.45),0 0 0 2px rgba(255,255,255,0.10) inset;}
.kt-cmp .kt-pl{position:relative;width:84px;height:84px;border-radius:50%;background:@IN@;flex:none;display:flex;align-items:center;justify-content:center;}
.kt-cmp .kt-pl i{position:absolute;display:block;background:#b9bcc8;border-radius:3px;}
.kt-cmp .kt-ty{position:relative;flex:1;height:80px;display:flex;align-items:center;font-family:@FD@;font-weight:700;font-size:64px;letter-spacing:3px;color:#fff;}
.kt-cmp .kt-ty span{opacity:0;}
.kt-cmp .kt-ty u{position:absolute;left:0;top:8px;display:block;width:5px;height:64px;background:@ACC@;text-decoration:none;}
.kt-cmp .kt-ph{position:absolute;left:0;top:0;height:80px;display:flex;align-items:center;font-weight:400;font-size:52px;color:rgba(255,255,255,0.32);letter-spacing:0;}
.kt-cmp .kt-post{width:92px;height:92px;border-radius:50%;background:@SENT@;display:flex;align-items:center;justify-content:center;flex:none;}
.kt-bub{position:absolute;bottom:307px;display:flex;opacity:0;box-shadow:0 16px 40px rgba(0,0,0,0.45);font-family:@FD@;}
.kt-bub.kt-me{right:90px;height:118px;align-items:center;padding:0 44px;border-radius:52px 52px 14px 52px;background:@SENT@;font-weight:700;font-size:62px;
  letter-spacing:3px;color:#fff;transform-origin:100% 100%;white-space:nowrap;}
.kt-bub.kt-dots{left:90px;height:118px;width:196px;align-items:center;padding:0 38px;border-radius:52px 52px 52px 14px;background:@IN@;
  justify-content:space-between;transform-origin:0% 100%;}
.kt-bub.kt-dots i{display:block;width:26px;height:26px;border-radius:50%;background:@DOTS@;}
.kt-bub.kt-him{left:90px;flex-direction:column;padding:26px 30px;border-radius:52px 52px 52px 14px;background:@IN@;transform-origin:0% 100%;}
.kt-bub.kt-him .kt-att{height:150px;display:flex;align-items:center;gap:26px;padding:0 34px 0 26px;border-radius:32px;background:@ATT@;}
.kt-bub.kt-him .kt-fn{font-weight:700;font-size:48px;color:#fff;line-height:1.1;white-space:nowrap;}
.kt-bub.kt-him .kt-fm{font-weight:400;font-size:34px;color:@DOTS@;margin-top:6px;white-space:nowrap;}
.kt-bub.kt-him .kt-tx{margin-top:16px;height:64px;display:flex;align-items:center;padding-left:8px;font-weight:600;font-size:50px;color:#fff;white-space:nowrap;}
"""
THREAD_GAP = 22                                   # panel px between stacked bubbles: each scroll-up makes exactly this room


def thread_cta(ctx, words, keyword, reply_text, attachment=None, platform="instagram", *, attach_as="folder", id=None,
               start=None, end=None, dur=None, uid="kt", line=""):
    """The comment ask ENACTED as a DM thread in the destination platform's look (2026-09-23, three rounds, then
    "Yo, that's fire"): the composer lands low in the zone on "comment" and NEVER moves again ("I like how the message box
    stays where it is and the text comes above it"); his spoken keyword types letter by letter across the spoken keyword,
    done before the send; on "below" the send button presses, and 3 frames later the VIEWER's bubble lands on the right in
    the platform's sent colour ("I meant MY message": the colour marks "you"); typing dots; then the creator's GREY reply
    on the left carrying the promised thing as an OBJECT, an attachment (its file-type icon, title + one-line meta) above his line; each
    arrival scrolls the earlier bubble up by the arriving element's height over 6 frames (the reply's scroll starts 3
    frames early, so it pops into room already made). No exit: the final frame is what a looping viewer sees.
    Start the scene on the comment word: within 8 frames of it the composer enters on frame 0 (the cut is its entrance,
    so the panel is never an empty plate and the cut has one sound); later than that, the engine warns of the plate.
    words = {comment, keyword, send, reply}: timeline word starts. attachment = (title, meta) or None; attach_as = what
    KIND of thing he promised, as the file-type icon a DM shows: "folder" (a bundle, a workflow, a set of files: the
    approved one), "video" (a recording, a walkthrough), "doc" (a guide, a template, a checklist), or inline SVG. It is a
    type icon, never a drawn preview of the thing (a drawn video tile was rejected, graphics.md § 6). The attachment copy
    and the reply line are the editor's words unless he said them: flag them in the plan so he can change them.
    Sound: riseIn on the composer, typing across the typed span, payoff (the bell: sent is done) as the bubble lands, and
    the soft rise on the reply (the sound he kept on it). The dots and the scrolls are silent on purpose."""
    clock = _clock(ctx, id, start, end, dur)
    m = Motion()
    sent_fill, accent = PLATFORMS[platform] if isinstance(platform, str) else platform
    css = (THREAD_CSS.replace("@SENT@", sent_fill).replace("@ACC@", accent).replace("@IN@", BUBBLE_IN)
           .replace("@ATT@", ATTACHMENT).replace("@DOTS@", TYPING_DOTS).replace("@FD@", FD))
    word = keyword.upper()
    c, bl, be, se = (clock.beat(words[k]) for k in ("comment", "keyword", "send", "reply"))
    if not c <= bl < be < se:
        raise BuildError(f"{id}: the words must run comment <= keyword < send < reply")
    # measured: the typed keyword inside the composer, the sent bubble and the reply inside the panel
    if text_w(word, 64, 700, 3) > 900 - 22 - 84 - 22 - 22 - 92 - 18 - 11:
        raise BuildError(f"{id}: {word!r} overflows the composer")
    if text_w(word, 62, 700, 3) + 88 > 1080 - 180:
        raise BuildError(f"{id}: {word!r} overflows the sent bubble")
    att_w = (26 + 120 + 26 + max(text_w(attachment[0], 48, 700), text_w(attachment[1], 34, 400)) + 34) if attachment else 0
    if max(text_w(reply_text, 50, 600) + 8 if reply_text else 0, att_w) + 60 > 1080 - 180:
        raise BuildError(f"{id}: the reply is wider than the panel: shorten the line or the attachment copy")
    reply_h = 52 + (150 if attachment else 0) + (16 if attachment and reply_text else 0) + (64 if reply_text else 0)
    letters = "".join(f"<span>{htmlmod.escape(ch)}</span>" for ch in word)
    icon = attach_as if str(attach_as).lstrip().startswith("<") else ATTACH_GLYPHS.get(attach_as)
    if attachment and icon is None:
        raise BuildError(f"{id}: attach_as={attach_as!r}: use one of {sorted(ATTACH_GLYPHS)}, or inline SVG (120x96, solid)")
    att = (f'<div class="kt-att">{icon}<div><div class="kt-fn">{htmlmod.escape(attachment[0])}</div>'
           f'<div class="kt-fm">{htmlmod.escape(attachment[1])}</div></div></div>') if attachment else ""
    html = (f'<div class="kt-bub kt-me" id="{uid}-me">{htmlmod.escape(word)}</div>'
            f'<div class="kt-bub kt-dots" id="{uid}-dots"><i></i><i></i><i></i></div>'
            f'<div class="kt-bub kt-him" id="{uid}-him" style="height:{reply_h}px;">{att}'
            + (f'<div class="kt-tx">{htmlmod.escape(reply_text)}</div>' if reply_text else "") + "</div>"
            f'<div class="kt-cmp" id="{uid}-cmp"><div class="kt-pl"><i style="width:34px;height:6px;"></i>'
            f'<i style="width:6px;height:34px;"></i></div><div class="kt-ty" id="{uid}-ty"><div class="kt-ph" id="{uid}-ph">'
            f'Message</div>{letters}<u id="{uid}-car"></u></div><div class="kt-post" id="{uid}-post">{icon_svg(ARROW_UP, 56)}</div></div>')
    cmp_ = f"#{uid}-cmp"
    if m.snap(c) <= m.F(8):
        c = 0.0             # the scene opens on "comment": the cut IS the composer's entrance (no empty plate, one sound)
    m.row_in(cmp_, c, dy=80, frm=0.92, frames=8, ease="back.out(1.5)", note="the composer lands, and stays put")
    m.hide(f"#{uid}-ph", bl)
    n = len(word)
    step = (be - bl - 0.10) / n                                          # letters spread across the spoken keyword
    if step < m.F(0.5):
        raise BuildError(f"{id}: the send comes too soon after the keyword to type it (under half a frame a letter)")
    typed = [m.snap(bl + i * step) for i in range(n)]
    if typed[-1] >= m.snap(be):
        raise BuildError(f"{id}: the keyword is not fully typed before the send")
    car = f"#{uid}-car"
    m.set(car, {"x": -9}, 0.0)                                           # an empty field: the caret sits before the placeholder
    for i, t in enumerate(typed):                                      # each letter, and the caret after it (the typed width, measured)
        m.show(f"#{uid}-ty span:nth-of-type({i + 1})", t)
        m.set(car, {"x": round(text_w(word[:i + 1], 64, 700, 3) + 6, 1)}, t)
    m.event(typed[0], "typing", dur=typed[-1] - typed[0], note="the keyword typed letter by letter")
    m.blink(f"#{uid}-car", c + 0.1, be)
    m.hide(f"#{uid}-car", be)
    sent = m.snap(be) + m.F(3)
    m.press(f"#{uid}-post", be, down=0.78, down_frames=3, up=1.0, up_frames=4, sound=None)
    for i in range(n):
        m.hide(f"#{uid}-ty span:nth-of-type({i + 1})", sent)
    m.show(f"#{uid}-ph", sent)
    me = f"#{uid}-me"
    m.show(me, sent)
    m.fromto(me, {"y": 120, "scale": 0.8}, {"y": 0, "scale": 1}, sent, m.F(8), "back.out(1.6)")
    m.event(sent, "payoff", note="sent: the viewer's comment is posted")
    se = m.snap(se)
    if se - m.F(3) < sent + m.F(8):
        raise BuildError(f"{id}: the reply lands before the sent bubble has settled (the reply word is too close to the send)")
    dots_at = m.snap(max(sent + 0.35, se - 0.50))
    if dots_at + m.F(6) <= se - m.F(3):                                 # room for the typing indicator before the reply
        m.show(f"#{uid}-dots", dots_at)
        m.fromto(f"#{uid}-dots", {"scale": 0.6}, {"scale": 1}, dots_at, m.F(6), "back.out(2)")
        m.to(me, {"y": -(118 + THREAD_GAP)}, dots_at, m.F(6), "power3.out")
        for k in range(3):
            m.fromto(f"#{uid}-dots i:nth-child({k + 1})", {"y": 0}, {"y": -12}, dots_at + 0.08 + k * 0.09, 0.18,
                     "sine.inOut", yoyo=True, repeat=3)
        m.hide(f"#{uid}-dots", se)
    him = f"#{uid}-him"
    m.show(him, se)
    m.fromto(him, {"scale": 0.7, "y": 30}, {"scale": 1, "y": 0}, se, m.F(8), "back.out(1.7)")
    m.to(me, {"y": -(reply_h + THREAD_GAP)}, se - m.F(3), m.F(6), "power3.out")
    m.event(se, "riseIn", note="his reply lands with the promised thing")
    top = 960 - 307 - (reply_h + THREAD_GAP) - 118                      # the finished thread: the sent bubble's top...
    copy = [word, "Message"] + (list(attachment) if attachment else []) + ([reply_text] if reply_text else [])
    return _authored(clock, html, css, m, bbox=(90, top, 990, 960 - 157), visible0=[cmp_] if c == 0 else [],
                     kind="ui-enactment", role="cta", line=line, copy=copy)


# ------------------------------------------------------------------------------------------------------------------
# THE BRAND LOCKUP and THE CLICK CTA
# ------------------------------------------------------------------------------------------------------------------
class Lockup:
    """brand_lockup's result: .html/.css (drop them into a capture spec's extra_html / extra_css, or a component's body),
    the icon's selector and centre, and the row's extent, in the host's px"""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def spec(self):
        return {"extra_html": self.html, "extra_css": self.css}


def brand_lockup(icon, wordmark, icon_px=205, wordmark_px=104, gap=52, top=268, on_dark=True, uid="kl"):
    """The OFFICIAL lockup (the real app icon + the real wordmark) BIG, for laying over a site-hero capture whose own nav
    is cropped off: the lockup IS the logo, and a tiny nav wordmark under it would be a duplicate (graphics.md § 3; you,
    2026-09-22: "much, much bigger to take up that real estate", then "a slight tad bit smaller"). Static: the cut is its
    entrance ("it zooms in and looks corny"). The icon is bare (bare_icon: alpha-following shadow only, a lighter one on
    a light page); a DARK wordmark on a dark panel is inverted to white, on a light page it stays as it is. No events.
    Sizes are the host's px: frame px over a capture (the defaults), panel px inside an authored scene."""
    wfs, wsrc = _asset(wordmark)
    wm_w = wordmark_px * _mark_aspect(wfs)
    row_w = icon_px + gap + wm_w
    if row_w > 1080 - 2 * 40:
        raise BuildError(f"brand_lockup: the row is {row_w:.0f} px, wider than the panel: smaller marks")
    shadow = MARK_SHADOW if on_dark else "drop-shadow(0 16px 44px rgba(0,0,0,0.14))"
    ic = bare_icon(icon, icon_px, ident=f"{uid}-icon", shadow=shadow, style="position:relative;flex:none;")
    inv = "filter:brightness(0) invert(1);" if on_dark and _is_dark_mark(wfs) else ""
    html = (f'<div class="kl-row" id="{uid}" style="position:absolute;left:0;top:{top}px;width:1080px;height:{icon_px}px;'
            f'display:flex;align-items:center;justify-content:center;gap:{gap}px;">{ic}'
            f'<img class="kl-wm" id="{uid}-wm" src="{wsrc}" alt="" style="height:{wordmark_px}px;width:{wm_w:.1f}px;'
            f'display:block;flex:none;{inv}"/></div>')
    x0 = (1080 - row_w) / 2
    return Lockup(html=html, css="", uid=uid, sel=f"#{uid}", icon_sel=f"#{uid}-icon", icon_px=icon_px, top=top,
                  icon_cx=x0 + icon_px / 2, icon_cy=top + icon_px / 2, row=(x0, top, x0 + row_w, top + icon_px))


CLICK_CSS = """
.kk-ring{position:absolute;border-radius:50%;border:6px solid rgba(255,77,94,0.85);opacity:0;}
.kk-btn{position:absolute;left:170px;width:740px;height:150px;border-radius:75px;background:rgba(18,20,28,0.95);display:flex;
  align-items:center;justify-content:center;gap:28px;opacity:0;box-shadow:0 24px 60px rgba(0,0,0,0.5),0 0 0 2px rgba(255,255,255,0.12) inset;}
.kk-btn b{font-family:@FD@;font-weight:900;color:#fff;line-height:1;white-space:nowrap;}
.kk-ptr{position:absolute;left:640px;width:84px;height:120px;opacity:0;}
.kk-dn{position:absolute;left:465px;width:150px;height:150px;border-radius:50%;background:@ROYAL@;display:flex;align-items:center;
  justify-content:center;opacity:0;box-shadow:0 18px 44px rgba(0,0,0,0.5);}
""".replace("@FD@", FD).replace("@ROYAL@", ROYAL)
CLICK_UP = 45     # panel px: the whole card sits this much higher than the approved ad card (see click_cta)


def click_cta(ctx, lockup, label, words, *, id=None, start=None, end=None, dur=None, uid="kk", line=""):
    """The click ask (the ad) ENACTED: his words only, the sponsor's real lockup, the click performed, no exit
    (graphics.md § 6). Beats (timeline word starts): try = the icon bumps 1 -> 1.1 (a pop lands on it: the bump exists so
    the sound has something under it); name = a ring goes out from the icon; just = a 740x150 button carrying HIS exact
    words rises; click = a cursor glides in from the lower right; link = ONE tap (the button squashes and turns OS green);
    below = a down arrow drops under it and bobs to the last frame. The lockup is on screen from frame 0: arrive from the
    previous graphic with push() (split stays split, you 2026-09-23), never through a bare-face beat.
    lockup = a brand_lockup built in panel px, or (icon, wordmark) asset paths (built at the ad size: 230 / 116 / gap 56).
    label = the button's words, from his line (e.g. "try <product>").
    Geometry: the approved card's stack (lockup 170, button 500, cursor 600, arrow 690 panel px), lifted CLICK_UP (45
    panel px, about 36 on the frame). On the approved card the arrow's bottom plus its bob reached frame y~878, 43 px
    above the caption box and past the split content zone (y845); lifted, it ends ~y842, inside the zone with the
    caption's air kept. A deliberate change to approved geometry, made so the content-zone gate holds it.
    Sound: pop-hero on the bump, riseIn on the button, click on the tap. The ring, the cursor and the arrow are silent."""
    clock = _clock(ctx, id, start, end, dur)
    m = Motion()
    lk = lockup if isinstance(lockup, Lockup) else brand_lockup(*lockup, icon_px=230, wordmark_px=116, gap=56, top=170 - CLICK_UP)
    tr, nm, ju, cl, li, be = (clock.beat(words[k]) for k in ("try", "name", "just", "click", "link", "below"))
    if not (tr <= nm and ju <= cl <= li <= be):
        raise BuildError(f"{id}: the words must run try <= name, just <= click <= link <= below")
    lab = label.upper()
    px = fit_px(lab, BUTTON_PX, 740 - 2 * 44 - 64 - 28, 900, 1)
    y_btn, y_ptr, y_dn = 500 - CLICK_UP, 600 - CLICK_UP, 690 - CLICK_UP
    d = round(lk.icon_px * 330 / 230)                                     # the ring, centred on the ICON (the name's mark)
    html = (f'<div class="kk-ring" id="{uid}-ring" style="left:{lk.icon_cx - d / 2:.0f}px;top:{lk.icon_cy - d / 2:.0f}px;'
            f'width:{d}px;height:{d}px;"></div>' + lk.html
            + f'<div class="kk-btn" id="{uid}-btn" style="top:{y_btn}px;">{icon_svg(LINK, 64)}'
              f'<b style="font-size:{px}px;letter-spacing:{px / BUTTON_PX:.2f}px;">{htmlmod.escape(lab)}</b></div>'
              f'<div class="kk-ptr" id="{uid}-ptr" style="top:{y_ptr}px;">{POINTER}</div>'
              f'<div class="kk-dn" id="{uid}-dn" style="top:{y_dn}px;"><div style="transform:rotate(180deg)">{icon_svg(ARROW_UP, 92)}</div></div>')
    m.set(lk.sel, {"opacity": 1}, 0.0)                                   # the lockup is the frame-0 content
    m.bump(lk.icon_sel, tr, to=1.1, frames=3, sound="pop-hero", note="the brand icon bumps on the try word")
    m.fromto(f"#{uid}-ring", {"scale": 0.6, "opacity": 0.9}, {"scale": 1.5, "opacity": 0}, nm, 0.5, "power2.out")
    m.row_in(f"#{uid}-btn", ju, dy=70, frm=0.92, frames=8, ease="back.out(1.5)", note="the button, in his words")
    ptr = f"#{uid}-ptr"
    tap = max(m.snap(li), m.snap(ju) + m.F(8))                             # the press waits for the button's entrance
    m.show(ptr, cl)
    m.fromto(ptr, {"x": 260, "y": 220}, {"x": 0, "y": 0}, cl, max(m.F(4), tap - m.snap(cl) - m.F(2)), "power3.out")
    m.to(ptr, {"scale": 0.86}, tap, m.F(2), "power2.in")
    m.to(ptr, {"scale": 1}, tap + m.F(2), m.F(3), "power2.out")
    m.press(f"#{uid}-btn", tap, colour_to=OS_ACCEPT, down=0.94, down_frames=2, up=1.0, up_frames=4, sound="click",
            note="the tap on 'link': the button turns green")
    m.down_arrow(f"#{uid}-dn", max(be, tap + m.F(6)), clock.dur)
    bbox = (min(lk.row[0], 170), min(lk.row[1], lk.icon_cy - d / 2), max(lk.row[2], 910), y_dn + 150 + ARROW_BOB_PX)
    return _authored(clock, html, CLICK_CSS + lk.css, m, bbox=bbox, visible0=[lk.sel], kind="ui-enactment", role="cta",
                     line=line, copy=[lab])


# ------------------------------------------------------------------------------------------------------------------
# THE PUSH: graphic to graphic inside split, with no face beat between (graphics.md § 13, layout.md)
# ------------------------------------------------------------------------------------------------------------------
def push(prev_render, scene, uid="kp"):
    """The incoming AUTHORED split scene arrives by a PUSH: the previous graphic's LAST FRAME (engine.last_frame) slides
    0 -> -1080 while the scene's content enters from +1080, exactly one screen apart on one ease (PUSH_FRAMES,
    PUSH_EASE), so they never overlap and the split framing never breaks (2026-09-23: "the graphic just slides out
    to the left, and the new graphic slides in from the right"). The incoming backdrop's glow drift starts at the previous
    comp's phase (its duration), so the join differs by grain only. Sound: the cut-in whoosh at the push (sfx.json leads
    it 2 frames). prev_render = the outgoing graphic's render in gfx/renders/. Returns the scene, modified."""
    if scene.family != "authored" or scene.layout != "split":
        raise BuildError(f"{scene.id}: push() takes an authored split scene (a capture arrives on its cut)")
    prev = Path(prev_render).resolve()
    gfx = prev.parent.parent if prev.parent.name == "renders" else Path(getattr(engine, "_GFX", None) or prev.parent)
    png = gfx / "assets" / "push" / f"{prev.stem}-last.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    engine.last_frame(prev, png)
    src = png.relative_to(gfx).as_posix()
    n_prev = engine.frame_count(prev)
    m = Motion()
    d = m.F(PUSH_FRAMES)
    inner = '<div class="safe">' in scene.html                           # units="panel": the content sits in the 0.79 fit
    dist = round(1080 / PANEL_TO_FRAME, 1) if inner else 1080             # one SCREEN, in the content's own px
    wrap = f'<div id="{uid}-in" style="position:absolute;left:0;top:0;width:1080px;height:960px;">'
    head, seam = ('<div class="safe">', '</div><div class="seam"></div>') if inner else ('<div class="vig"></div>', '<div class="seam"></div>')
    k = scene.html.rfind(seam)
    if head not in scene.html or k < 0 or not scene.html.rstrip().endswith("</div>"):
        raise BuildError(f"{scene.id}: push() cannot find the panel's content (not an engine.authored split scene)")
    html = scene.html[:k] + "</div>" + scene.html[k:]                     # close the wrapper just inside the content's end
    html = html.replace(head, head + wrap, 1)
    shot = (f'<img id="{uid}-prev" src="{src}" alt="" style="position:absolute;left:0;top:0;width:1080px;display:block;'
            'max-width:none;"/>')
    k = html.rstrip().rfind("</div>")                                     # the outgoing frame rides OVER the panel, unscaled
    scene.html = html[:k] + shot + html[k:]
    m.set(f"#{uid}-prev", {"opacity": 1}, 0.0)
    m.fromto(f"#{uid}-prev", {"x": 0}, {"x": -1080}, 0.0, d, PUSH_EASE)
    m.fromto(f"#{uid}-in", {"x": dist}, {"x": 0}, 0.0, d, PUSH_EASE)
    m.event(0.0, "cut-in", note="the push from the previous graphic")
    scene.js = "\n".join(m.js) + "\n" + scene.js
    scene.events = sorted(list(scene.events) + m.events, key=lambda e: e["at"])
    scene.visible0 = sorted(set(scene.visible0) | {f"#{uid}-prev"})
    scene.glow_phase = engine.fsec(n_prev)
    return scene


# ------------------------------------------------------------------------------------------------------------------
# the self-check: every component case on synthetic inputs (no job, no media), through the engine's own comp gate
# ------------------------------------------------------------------------------------------------------------------
def _crowded(events, cap=3, win=1.0):
    """the first time where more than `cap` DIFFERENT sounds start inside a rolling `win` s (a run of one sound counts
    once: the house density cap), else None"""
    ev = sorted((e["at"], e["event"]) for e in events)
    for t, _ in ev:
        if len({n for u, n in ev if t <= u < t + win}) > cap:
            return t
    return None


def selfcheck(tmp=None):
    """[failures] for the component cases, each built and then passed through engine.comp() (the build-time gate:
    frame-grid positions, no overlapping tweens, visible0 proven by a set at 0, the split content zone):
    masked holds no digit; the hook's children fit and the stack stays in the zone; the call card's drop never starts
    above y204 and its bottom = crown - 25; the thread's keyword is typed before the send and the composer is static after
    it lands; the click card has no tween after its last beat but the arrow bob; bare_icon sizes two differently padded,
    shadowed marks to equal solid bodies within 1 px; every event is in the preset's sfx.json; push hands over cleanly.
    And the repairs: the default claim carries no phone premise; the phone preset's bars sound ONE blip and the hook name
    rides the hero pop (at most 3 sounds a second); an outgoing call has no accept; a continued call does not re-drop or
    restart its timer; an ended call shows CALL ENDED, not a live timer; the attachment icon is the one named."""
    import tempfile
    from PIL import Image, ImageDraw, ImageFilter
    engine.use_fps(engine.FPS)
    tmp = Path(tmp or tempfile.mkdtemp(prefix="kit-components-"))
    bad = []

    def mark(name, canvas, body, px, py, shadow=True, full=False):
        im = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
        if shadow:
            sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle([px + 6, py + 14, px + body + 6, py + body + 14], 40, fill=(0, 0, 0, 110))
            im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(12)))
        d = ImageDraw.Draw(im)
        if full:
            d.rectangle([0, 0, canvas - 1, canvas - 1], fill=(220, 40, 50, 255))
        else:
            d.rounded_rectangle([px, py, px + body - 1, py + body - 1], 40, fill=(235, 235, 240, 255))
        im.save(tmp / name)
        return str(tmp / name)

    a, b = mark("mark-a.png", 512, 412, 50, 50), mark("mark-b.png", 300, 190, 22, 74)
    sq = mark("mark-sq.png", 256, 256, 0, 0, shadow=False, full=True)
    wm = tmp / "wordmark.svg"
    wm.write_text('<svg viewBox="0 0 110 28" xmlns="http://www.w3.org/2000/svg"><rect width="110" height="28" fill="#151515"/></svg>', encoding="utf-8")

    def case(name, fn):
        try:
            return fn()
        except (BuildError, AssertionError, ValueError) as e:
            bad.append(f"{name}: {e}")
            return None

    for ic in (bare_icon(a, 260), bare_icon(b, 260)):
        if abs((ic.body[2] - ic.body[0]) - 260) > 1 or abs((ic.body[3] - ic.body[1]) - 260) > 1:
            bad.append(f"bare_icon: solid body {ic.body} is not the 260 px box")
    if "border-radius" not in bare_icon(sq, 200):
        bad.append("bare_icon: a full-bleed square app icon lost its app-icon rounding")
    if re.search(r"\d", masked([1, 3, 3, 4])) or re.search(r"\d", masked([4, 4, 4, 4], "*")):
        bad.append("masked: a digit reached the output")
    try:
        masked([3], "7")
        bad.append("masked: a digit glyph was accepted")
    except BuildError:
        pass

    scenes = {}
    claim = masked_value([1, 3, 3, 4], {"value": 1.25, "live": 2.95})
    scenes["hook"] = case("hook_stack", lambda: hook_stack(None, a, "Subject", claim, id="hook", start=0.0, end=4.63))
    if case("hook_stack refuses an overfull pill",
            lambda: hook_stack(None, a, "Subject", masked_value([4, 4, 4, 4, 4, 4], {"value": 1.25}), id="x", start=0, end=4)):
        bad.append("hook_stack: a claim row wider than its pill was accepted")
    else:
        bad.pop()
    if scenes["hook"] and {"blip", "status-keys", "status-chime"} & {e["event"] for e in scenes["hook"].events}:
        bad.append("masked_value: the defaults carry signal bars (a phone number's premise, not a value's)")
    ph = case("hook_stack (PHONE_NUMBER)", lambda: hook_stack(
        None, a, "Subject", masked_value([1, 3, 3, 4], {"value": 1.25, "live": 2.95}, **PHONE_NUMBER), id="hookph",
        start=0.0, end=4.63))
    if ph:
        scenes["hook-phone"] = ph
        names = [e["event"] for e in ph.events]
        if names.count("blip") != 1 or {"status-keys", "status-chime"} & set(names):
            bad.append(f"hook: the bars must sound ONE blip (his hook's sound), not {names}")
        if 'id="kh-name" data-sfx="none"' not in ph.html:
            bad.append("hook: the name rising inside the hero pop is not silenced (a second accent on one beat)")
        if _crowded(ph.events):
            bad.append(f"hook: more than 3 different sounds inside a rolling second at {_crowded(ph.events):.2f} s")
    if masked_text([1, 3, 3, 4], "phone") != "+• (•••) •••-••••" or re.search(r"\d", masked_text([4, 4, 4, 4])):
        bad.append(f"masked_text: {masked_text([1, 3, 3, 4], 'phone')!r}")

    env = {engine.frames(10.0) + f: round(0.3 + 0.6 * abs(math.sin(f / 3)), 3) for f in range(40, 150)}
    cc = case("call_card", lambda: call_card(None, "Caller", None, 625, ring_from=9.9, answer_at=11.75, envelope=env,
                                             id="call", start=10.0, end=18.2))
    if cc:
        scenes["call"] = cc
        drop = re.search(r"tl\.fromTo\('#kc',\{y:-([\d.]+),scale:", cc.js)
        if cc.bbox[3] != 600 or not drop or cc.bbox[1] - float(drop.group(1)) < CALL_TOP_MIN:
            bad.append(f"call_card: bottom {cc.bbox[3]} (want crown 625 - 25 = 600), or the drop starts above y{CALL_TOP_MIN}")
    if case("call_card refuses a crown too high", lambda: call_card(None, "Caller", None, 400, envelope={}, id="x", start=0, end=5)):
        bad.append("call_card: a crown too high for the card was accepted")
    else:
        bad.pop()
    out = case("call_card outgoing", lambda: call_card(None, "Caller", None, 625, ring_from=10.2, answer_at=12.0,
                                                       envelope=env, outgoing=True, id="callout", start=10.0, end=14.0))
    if out:
        scenes["call-out"] = out
        names = {e["event"] for e in out.events}
        if "calling" not in names or names & {"ring", "tap"} or "kc-yes" in out.html or "calling…" not in out.html:
            bad.append(f"call_card outgoing: want CALLING... and the calling bed, no accept, ring or tap; got {sorted(names)}")
    cont = case("call_card continued + ended", lambda: call_card(None, "Caller", None, 625, envelope=env, enter=False,
                                                                 timer_from=7.4, ended_at=16.0, id="callcont", start=12.0,
                                                                 end=18.2))
    if cont:
        scenes["call-cont"] = cont
        if any(e["event"] == "riseIn" for e in cont.events) or "tl.fromTo('#kc',{y:" in cont.js:
            bad.append("call_card enter=False: the continued call re-drops")
        if 'id="kc-t7"' not in cont.html or 'id="kc-t0"' in cont.html:
            bad.append("call_card timer_from: the timer restarts instead of carrying on at 00:07")
        end_on = re.search(r"tl\.set\('#kc-end',\{opacity:1\},([\d.]+)\)", cont.js)
        shows = [float(x) for x in re.findall(r"tl\.set\('#kc-t\d+',\{opacity:1\},([\d.]+)\)", cont.js)]
        if not end_on or abs(float(end_on.group(1)) - 4.0) > 1.0 / float(engine.FPS) or max(shows) >= float(end_on.group(1)):
            bad.append("call_card ended_at: CALL ENDED does not replace the timer where he hangs up")
        hides = {re.search(r"#kc-t(\d+)", ln).group(1) for ln in cont.js.splitlines()
                 if ln.startswith("tl.set('#kc-t") and "{opacity:0}" in ln}
        if len(hides) != len(shows):
            bad.append("call_card ended_at: a timer second is still on screen after the call ends")

    th = case("thread_cta", lambda: thread_cta(None, {"comment": 50.19, "keyword": 50.51, "send": 51.13, "reply": 52.12},
                                               "keyword", "Here it is", ("Title", "One-line meta"), id="thread", start=50.0,
                                               end=53.4))
    if th:
        scenes["thread"] = th
        letters = [float(x) for x in re.findall(r"tl\.set\('#kt-ty span:nth-of-type\(\d+\)',\{opacity:1\},([\d.]+)\)", th.js)]
        press = float(re.search(r"tl\.to\('#kt-post',\{scale:0\.78,[^}]*\},([\d.]+)\)", th.js).group(1))
        if not letters or max(letters) >= press:
            bad.append("thread_cta: the keyword is not fully typed before the send")
        if len(re.findall(r"tl\.(?:to|fromTo)\('#kt-cmp'", th.js)) != 1:
            bad.append("thread_cta: the composer moves after it lands")

    tv = case("thread_cta attach_as", lambda: thread_cta(None, {"comment": 50.19, "keyword": 50.51, "send": 51.13,
                                                                 "reply": 52.12}, "keyword", "Here it is",
                                                           ("Title", "One-line meta"), attach_as="video", id="thread-v",
                                                           start=50.0, end=53.4))
    if tv and (VIDEO_FILE not in tv.html or FOLDER in tv.html):
        bad.append("thread_cta attach_as: the attachment is not the named file-type icon")
    w = {"try": 81.12, "name": 81.38, "just": 81.94, "click": 82.12, "link": 82.44, "below": 82.6}
    ck = case("click_cta", lambda: click_cta(None, (sq, str(wm)), "Try it", w, id="click", start=80.0, end=83.09))
    if ck:
        scenes["click"] = ck
        end = engine.beat(w["below"], ck.start) + 7 / float(engine.FPS) + 1e-3
        late = [l for l in ck.js.splitlines() if l.startswith(("tl.to", "tl.fromTo")) and "#kk-dn" not in l
                and float(re.findall(r",([\d.]+)\);$", l)[0]) > end]
        if late:
            bad.append(f"click_cta: tweens after its last beat: {late[:2]}")
        prev = tmp / "renders" / "prev-alpha.mov"
        prev.parent.mkdir(exist_ok=True)
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x1e48ff:s=1080x1920:r={engine.rate_str()}:d=0.5",
                            "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", str(prev)], capture_output=True)
        if r.returncode == 0:
            pushed = case("push", lambda: push(prev, click_cta(None, (sq, str(wm)), "Try it", w, id="pushed", start=80.0,
                                                                 end=83.09)))
            if pushed:
                scenes["push"] = pushed
                if abs(pushed.glow_phase - engine.fsec(engine.frame_count(prev))) > 1e-6 or "kp-prev" not in pushed.html:
                    bad.append("push: the outgoing frame or the glow phase did not carry over")
        else:
            bad.append("push: ffmpeg could not make the outgoing render for the check")

    known = {k for k, v in engine.sfx_events()[0].items() if isinstance(v, dict)}
    if not EVENTS <= known:
        bad.append(f"EVENTS not in sfx.json: {sorted(EVENTS - known)}")
    for k, s in scenes.items():
        if s is None:
            continue
        miss = sorted({e["event"] for e in s.events} - known)
        if miss:
            bad.append(f"{k}: events not in sfx.json: {miss}")
        case(f"{k}: engine.comp (the build-time gate)", lambda s=s: engine.comp(s))
    return bad


if __name__ == "__main__":
    fails = selfcheck()
    print("\n".join(f"FAIL {f}" for f in fails) or "components selfcheck: every case passes")
    sys.exit(1 if fails else 0)
