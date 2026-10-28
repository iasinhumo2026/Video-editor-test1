#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""kit/engine.py: the talking-head explainer kit's engine. Every recurring number and every motion-hygiene rule of this
look lives here ONCE, so a job's `hf-graphics/gfx/build.py` is data (a storyboard of word anchors and component calls), the
first pass comes out in the approved look, and a re-cut is a re-run instead of a re-typing.

WHY it exists: the benchmark short was built from a hand-rolled emitter whose every hygiene rule was learned from a
shipped defect: a blank frame at a jump cut (an incoming clip not yet decoded), a set printed a hair after its frame, a
pulse fighting an entrance, a held window growing on its one frame, a 0.9 s clock error that looked right on every still.
Those rules are code below and are asserted when a comp is written, not remembered. The WHAT is owned by the preset's
docs: graphics.md and captures.md § Values are mirrored in VALUES (workflows/test_talking_head_kit.py holds them equal),
layout.md owns the bands. A number changes in its doc first, then here, never in a comp.

  uv run presets/instagram/talking-head-explainer/kit/engine.py init projects/<job>     # stage the kit into the job
  uv run presets/instagram/talking-head-explainer/kit/engine.py drift projects/<job>    # the job's copies vs the preset
  uv run presets/instagram/talking-head-explainer/kit/engine.py stage projects/<job> <id> <take> [--name X]
                                                  # a capture: original + all-intra render base (--mark: a brand mark)
  uv run projects/<job>/hf-graphics/gfx/kit/engine.py render <id> [--ver X]              # one comp, its family's flags
  uv run presets/instagram/talking-head-explainer/kit/engine.py smoke /tmp/video-editor/kit-smoke

As a library (the job's build.py puts gfx/kit on sys.path; components.py builds on the same calls):
  import engine as K
  ctx = K.Ctx(JOB)                       # the plan's fps (the grid), cells, layout; the canonical words; voices.json
  w = ctx.find("checking")               # a Word: a float (its start) with .end .text; a miss or an ambiguity raises
  s = K.capture({...})                   # a real screen: flat and readable, or the tilted macro montage
  s = K.authored(html, js, css, "split", id=..., start=..., dur=..., visible0=[...], bbox=(x0, y0, x1, y1))
  s = K.overlay(html, js, css, id=..., start=..., dur=...)          # over the wide face (the call card)
  K.layer(s, card, at=...)               # an overlay nested in a scene (a call card over a chat that cannot show the call)
  K.write(s, ctx.gfx); K.write_events(ctx.hf, s.id, s.events)

TIME: every time is a frame of the plan's grid. sn() snaps, beat(word, scene_start) puts an event about 1.5 frames
before its word, t6() prints a frame's time floored at 6 dp (a time printed a hair AFTER its frame misses it), and
step_cut() puts a picture cut on a STEPPED comp where its frame's 12 fps sample shows it (components.Clock.cut). Events are
dicts {event, at (comp s), note, dur} (ev()), and every name must be a live event in the preset's sfx.json.

FAMILIES (graphics.md § 7): authored (the house backdrop, 12 fps held, bloom, grain) · capture / capture-white (no
backdrop, the capture's own fill, timeline rate, faint bloom + scan lines) · montage (tilted macro b-roll, fill and scan
IN the plane) · overlay (over live footage, timeline rate, never stepped). `render` applies FAMILY_FLAGS, so nobody
types them. The reference render.sh carries the bloom/scan/grain post pass as opt-in flags (GLOW, SCAN, SCAN_AMP, GRAIN),
so `render` hands the family's flags to it; post_pass() below runs only on a job copy of render.sh that predates them.

UNITS: authored html is frame px inside the split content zone (y200-845) by default; units="panel" lays a 1080x960
panel out and fits it 0.79 about the seam centre (graphics.md § Units, what components.py writes). bbox is FRAME px
either way.

THE COMP CONTRACT: a comp script sees FPS, FR (one timeline frame), DUR, tl (THE paused main timeline) and H
(presets/youtube/default/reference/hf-anim.js bound to tl: H.riseIn for type, whose call sfx-plan snips; its slides
measure a 1920x1080 frame, so pass `dist` on 9:16). Positions are absolute seconds on the grid. comp() refuses:
backdrop-filter, text-shadow, onUpdate, Math.random or timers; a position off the grid, relative or missing; two tweens
(registry calls included) on one property of one target at overlapping times, both named (audit_tweens); a visible0
selector with no set at 0; authored split content whose bbox leaves y200-845. A literal position within a 4-dp print of
its frame is rewritten to that frame's floored time.
"""
import argparse, dataclasses, difflib, hashlib, importlib.util, json, math, os, re, shutil, subprocess, sys, unicodedata
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent


def _repo_root():
    for p in (HERE, *HERE.parents):
        if (p / "presets").is_dir() and (p / "workflows").is_dir():
            return p
    try:                                  # a job's copy outside the repo (a scratch job): init recorded where it came from
        p = Path(json.loads((HERE / "KIT.json").read_text(encoding="utf-8"))["repo"])
        return p if (p / "presets").is_dir() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


REPO = _repo_root()
PRESET_REL = "presets/instagram/talking-head-explainer"
PRESET = REPO / PRESET_REL if REPO else None
REFERENCE_REL = "presets/youtube/default/reference"


class BuildError(ValueError):
    """A comp that would ship a known defect. Raised at BUILD time, before anything renders."""


# ── § Values: the mirror of graphics.md and captures.md § Values (strings exactly as the docs write them) ─────────
# workflows/test_talking_head_kit.py holds these equal to the docs. The typed constants below are parsed from them.
VALUES = {
    # graphics.md § Values
    "PANEL_TO_FRAME": "0.79", "HERO_ICON_PX": "236",
    "ROYAL": "#1e48ff", "SKY": "#57c9f0", "TXT": "#e8f0ff", "MUTED": "#8fa6d4", "GREEN": "#2ff58a", "RED": "#ff4d5e",
    "UI_TEXT": "#ffffff", "OS_ACCEPT": "#30d158", "OS_DECLINE": "#ff3b30", "BUBBLE_IN": "#2a2b31",
    "ATTACHMENT": "#1d1e23", "TYPING_DOTS": "#9a9daa", "AVATAR_DISC": "#0b0c11",
    "DANGER_WASH": "radial-gradient(90% 80% at 50% 50%, rgba(255,40,60,0) 30%, rgba(255,40,60,0.55) 100%)",
    "IG_SENT": "linear-gradient(120deg, #8a3ffc 0%, #b537d8 50%, #e0307e 100%)",
    "BG_FILL": "#010102", "BG_GRID": "rgba(74,124,255,0.11)", "BG_GRID_LINE_PX": "1", "BG_GRID_PX": "90",
    "BG_LIGHT_PX": "1480", "BG_LIGHT_AT": "-200",
    "BG_LIGHT": "radial-gradient(circle at 50% 50%, rgba(40,84,255,0.07), rgba(40,84,255,0.024) 38%, rgba(40,84,255,0) 68%)",
    "BG_DRIFT_X": "38", "BG_DRIFT_SCALE": "1.06", "BG_DRIFT_S": "5.5", "BG_DRIFT2_Y": "22",
    "BG_DRIFT2_S": "3.7", "BG_DRIFT_EASE": "sine.inOut",
    "BG_VIGNETTE": "radial-gradient(120% 100% at 50% 50%, rgba(0,0,0,0) 55%, rgba(2,5,16,0.38) 100%)",
    "BG_SEAM_PX": "70", "BG_SEAM_TO": "rgba(2,5,16,0.85)",
    "FLAGS_AUTHORED": "STEP_FPS=12 GLOW=0.26 GRAIN=5", "FLAGS_CAPTURE": "GLOW=0.12 SCAN=1",
    "FLAGS_CAPTURE_WHITE": "GLOW=0.12 SCAN=1 SCAN_AMP=0.06", "FLAGS_MONTAGE": "GLOW=0.18", "FLAGS_OVERLAY": "none",
    "BLOOM_SIGMA": "30", "BLOOM_BRIGHTNESS": "0.12", "BLOOM_CONTRAST": "1.12", "BLOOM_CURVES": "0/0 0.5/0.62 1/1",
    "SCAN_PERIOD_PX": "6", "SCAN_AMP": "0.10", "SCAN_AMP_WHITE": "0.06",
    "FONT_DISPLAY": "SF Pro Display", "FONT_MONO": "SF Mono",
    "HERO_PX": "126", "HERO_WEIGHT": "900", "HERO_TRACK": "-3", "NAME_PX": "52-58", "NAME_TRACK": "-1",
    "BUTTON_PX": "70", "LABEL_PX": "25-30", "LABEL_TRACK": "2-3",
    "SURFACE_RGB": "18,20,28", "SURFACE_ALPHA": "0.92-0.96", "RIM_PX": "2", "RIM_ALPHA": "0.09-0.12",
    "UI_SHADOW": "0 24px 60px rgba(0,0,0,0.5)", "RADIUS_ROW": "44", "RADIUS_CARD": "34-68",
    "MARK_SHADOW": "drop-shadow(0 26px 40px rgba(0,0,0,0.55))", "MARK_SOLID_ALPHA": "128", "MARK_PAIR_TOL_PX": "2",
    "TERM_BODY": "#0d0f14", "TERM_BAR": "#1a1d25", "TERM_BAR_PX": "64", "TERM_LIGHTS": "#ff5f57,#febc2e,#28c840",
    "TERM_RADIUS": "26", "TERM_MONO_PX": "27", "TERM_LINE_PX": "42", "TERM_TEXT": "#aab3c8", "TERM_ERROR": "#ff5d6c",
    "TERM_WARN": "#febc2e",
    "EVENT_LEAD_S": "0.06", "SYNC_TOL_FRAMES": "2", "STEP_QUANTUM_MS": "83",
    "POP_FROM": "0.3-0.6", "POP_BACK": "1.4-2.6", "POP_FRAMES": "7-10",
    "RISE_CARD_Y": "60-110", "RISE_CARD_FROM": "0.90-0.94", "RISE_CARD_FRAMES": "8",
    "LOGO_X": "420", "LOGO_ROT": "14", "LOGO_FRAMES": "9", "LOGO_EASE": "back.out(1.4)",
    "PRESS_DOWN": "0.74-0.80", "PRESS_DOWN_FRAMES": "2-3", "PRESS_UP": "1.0-1.12", "PRESS_UP_FRAMES": "3-4",
    "PRESS_UP_EASE": "back.out(2.4)", "DROP_FRAMES": "11", "DROP_FROM": "0.92", "DROP_EASE": "power3.out",
    "EXIT_FRAMES": "5-8", "EXIT_EASE": "power2.in", "HOLD_READABLE_S": "2-3", "LONE_HOLD_MAX_S": "1-2",
    "RING_FROM": "0.6-1", "RING_TO": "1.5-1.9", "RING_S": "0.5-0.9",
    "ESC_STAGE": "0.86", "ESC_SHAKE_X": "7", "ESC_SHAKE_ROT": "0.5", "ESC_SHAKE_S": "0.05", "ESC_WASH_S": "1.2",
    "ESC_SCROLL_STEPS": "14-18", "PUSH_FRAMES": "10", "PUSH_EASE": "power3.inOut",
    "ARROW_PX": "150", "ARROW_BOB_PX": "16", "ARROW_BOB_S": "0.22",
    "GFX_PER_MIN": "11-12", "GFX_COVERAGE": "0.85", "GFX_S": "1.2-12", "GFX_MEDIAN_S": "3.9", "NEW_EVERY_S": "1",
    # captures.md § Values
    "TEXT_PX": "36-40", "TEXT_FLOOR": "31",
    "FIT_PAGE": "0.92", "FIT_VIDEO": "0.96", "FIT_LIST": "0.82-0.86", "FIT_BOARD": "0.84-0.87", "FIT_MONTAGE": "1.00",
    "HDR_SRC": "140", "HDR_PX": "112", "HDR_FADE": "46", "HDR_TOP_SPLIT": "200", "HDR_TOP_FULL": "260",
    "DOCK_SPLIT": "880", "FEATHER": "14", "CHAT_PUSH_SHOT": "1.003-1.018", "DRIFT_MAX": "1.02",
    "LANDING_DRIFT_FRAMES": "6", "MASK_MAX_S": "0.17", "REVEAL_DY": "60", "REVEAL_S": "0.42", "REVEAL_AT_FRAMES": "3",
    "PREROLL_MAX_FRAMES": "6", "TYPING_WITHIN_S": "0.3", "REPLY_AFTER_S": "0.2",
    "MONTAGE_SHOTS": "3-4", "MONTAGE_SHOT_S": "0.6-1.3", "MONTAGE_RX": "5-9", "MONTAGE_RY": "10-14",
    "MONTAGE_SWING": "2-3", "PERSPECTIVE": "1500", "MONTAGE_PUSH": "1.06-1.08", "PLANE_PAD": "1400",
    "INPLANE_SCAN": "0.32", "CONTINUOUS_PUSH_MAX": "1.015",
}


def _f(key):
    return float(VALUES[key])


def _rng(key):
    a, _, b = VALUES[key].partition("-") if not VALUES[key].startswith("-") else (VALUES[key], "", "")
    return (float(a), float(b or a))


def _flags(key):
    v = VALUES[key].strip()
    return {} if v == "none" else dict(kv.split("=", 1) for kv in v.split())


# ── the frame and its bands (layout.md § Values: SEAM_Y, SAFE, SPLIT_ZONE, FULL_TOP, SPILL_DISSOLVE_Y) ─────────────
FRAME_W, FRAME_H = 1080, 1920
FRAME = (FRAME_W, FRAME_H)
SEAM = 960                          # the split seam: the panel is y0-960, the caption centre sits on it
SAFE = (200, 1620)                  # the platform-safe box: nothing that matters above 200 or below 1620
SPLIT_ZONE = (200, 845)             # split key content; ink ends >= 75 px above the seam caption's box top (y921.5)
FULL_TOP = 260                      # a full-screen's content starts under the platform's top UI
SPILL_DISSOLVE_Y = 900              # a spill effect has dissolved by here
GATE_BAND = (908, 960)              # zero graphic ink on any split frame (graphics-qa-short --band): the caption owns it
CAPTION_BOX_ABOVE = 38.5            # caption line centre -> box top (layout.py), for a full-screen's zone bottom
FULL_AIR = 20                       # a full-screen's content ends this far above its caption box
PANEL_H = {"split": SEAM, "full": FRAME_H}
PANEL_TO_FRAME = _f("PANEL_TO_FRAME")   # units="panel": a 1080x960 layout scaled into y~202-960 (graphics.md § Units)

TOKENS = {
    "royal": VALUES["ROYAL"], "sky": VALUES["SKY"], "txt": VALUES["TXT"], "muted": VALUES["MUTED"],
    "green": VALUES["GREEN"], "red": VALUES["RED"], "ui": VALUES["UI_TEXT"], "accept": VALUES["OS_ACCEPT"],
    "decline": VALUES["OS_DECLINE"], "bubble-in": VALUES["BUBBLE_IN"], "attachment": VALUES["ATTACHMENT"],
    "dots": VALUES["TYPING_DOTS"], "avatar": VALUES["AVATAR_DISC"],
    "surface": f"rgba({VALUES['SURFACE_RGB']},{_rng('SURFACE_ALPHA')[0]})",
    "rim": "rgba(255,255,255,0.10)", "ui-shadow": VALUES["UI_SHADOW"],
    "ig-sent": VALUES["IG_SENT"], "danger": VALUES["DANGER_WASH"],
}

BACKDROP = {
    "fill": VALUES["BG_FILL"], "grid": VALUES["BG_GRID"], "grid_px": int(_f("BG_GRID_PX")),
    "line_px": int(_f("BG_GRID_LINE_PX")), "light_px": int(_f("BG_LIGHT_PX")), "light_at": int(_f("BG_LIGHT_AT")),
    "light": VALUES["BG_LIGHT"], "drift_x": _f("BG_DRIFT_X"),
    "drift_scale": _f("BG_DRIFT_SCALE"), "drift_s": _f("BG_DRIFT_S"), "drift2_y": _f("BG_DRIFT2_Y"),
    "drift2_s": _f("BG_DRIFT2_S"), "ease": VALUES["BG_DRIFT_EASE"], "vignette": VALUES["BG_VIGNETTE"],
    "seam_px": int(_f("BG_SEAM_PX")), "seam_to": VALUES["BG_SEAM_TO"],
}

FAMILIES = ("authored", "capture", "capture-white", "montage", "overlay")
FAMILY_FLAGS = {
    "authored": _flags("FLAGS_AUTHORED"), "capture": _flags("FLAGS_CAPTURE"),
    "capture-white": _flags("FLAGS_CAPTURE_WHITE"), "montage": _flags("FLAGS_MONTAGE"), "overlay": _flags("FLAGS_OVERLAY"),
}
POST_KEYS = ("GLOW", "SCAN", "SCAN_AMP", "GRAIN")     # the post chain; STEP_FPS goes to render.sh itself
BLOOM = {"sigma": _f("BLOOM_SIGMA"), "brightness": _f("BLOOM_BRIGHTNESS"), "contrast": _f("BLOOM_CONTRAST"),
         "curves": VALUES["BLOOM_CURVES"]}
SCAN_PERIOD = _f("SCAN_PERIOD_PX")
SCAN_AMP = _f("SCAN_AMP")

MONTAGE = {
    # the approved tilts [rx, ry], alternating the ry sign shot to shot; swing = |deg| over the shot, back toward flat
    "tilts": [(8, -14), (6, 12), (9, -10), (5, 11)], "swing": [3, 3, 2, 3], "push": [1.07, 1.07, 1.06, 1.08],
    "perspective": int(_f("PERSPECTIVE")), "pad": int(_f("PLANE_PAD")), "scan": _f("INPLANE_SCAN"),
    "warn_s": _rng("MONTAGE_SHOT_S"),   # a shot outside captures.md's band warns (the benchmark's ran 0.6-1.3 s)
}
CAPTURE = {
    "fit": {"page": _f("FIT_PAGE"), "video": _f("FIT_VIDEO"), "list": _rng("FIT_LIST"), "board": _rng("FIT_BOARD"),
            "montage": _f("FIT_MONTAGE")},
    "drift_max": _f("DRIFT_MAX"), "continuous_push_max": _f("CONTINUOUS_PUSH_MAX"),
    "landing_drift_frames": int(_f("LANDING_DRIFT_FRAMES")), "mask_max_s": _f("MASK_MAX_S"),
    "feather": int(_f("FEATHER")), "drift_ease": "power2.out",
}
HEADER = {"src": int(_f("HDR_SRC")), "px": int(_f("HDR_PX")), "fade": int(_f("HDR_FADE")),
          "top": {"split": int(_f("HDR_TOP_SPLIT")), "full": int(_f("HDR_TOP_FULL"))}, "gap": 16,
          "border": "rgba(255,255,255,0.10)"}
DOCK = {"split": int(_f("DOCK_SPLIT"))}       # full: the zone's bottom (20 px above the caption box)
REVEAL = {"dy": _f("REVEAL_DY"), "s": _f("REVEAL_S"), "at_frames": int(_f("REVEAL_AT_FRAMES")), "ease": "power3.out"}
PREROLL = int(_f("PREROLL_MAX_FRAMES"))
EVENT_LEAD_S = _f("EVENT_LEAD_S")
PUSH = {"frames": int(_f("PUSH_FRAMES")), "ease": VALUES["PUSH_EASE"], "dist": FRAME_W}
MARK_SOLID_ALPHA = int(_f("MARK_SOLID_ALPHA"))

GSAP_URL = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
FONT_FILES = {"Display-Black.otf": 900, "Display-Bold.otf": 700, "Display-Regular.otf": 400}
MONO_FILE = "Mono.ttf"
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm")
BASE_VIDEO_EXT = (".mp4", ".mov", ".m4v")     # a video capture's render base is H.264 (all_intra): no .webm, no bare name


# ── the clock: every time is a frame of the job's grid ────────────────────────────────────────────────────────────
FPS = Fraction(24000, 1001)          # Ctx(job) sets it from graphics-plan.json `fps`
_GFX = None                          # Ctx(job) sets it: where capture media is probed


def parse_rate(v):
    if isinstance(v, Fraction):
        return v
    s = str(v).strip()
    try:
        r = Fraction(s)
    except (ValueError, ZeroDivisionError):
        raise BuildError(f"fps {v!r} is not a rate (24000/1001, 30000/1001, 25)")
    if r <= 0:
        raise BuildError(f"fps {v!r} is not a rate")
    return r


def use_fps(rate):
    """Set the build's frame grid (Ctx does it from the plan). Returns the Fraction."""
    global FPS
    FPS = parse_rate(rate)
    return FPS


def rate_str(r=None):
    r = r or FPS
    return f"{r.numerator}/{r.denominator}" if r.denominator != 1 else str(r.numerator)


def frames(t):
    """seconds -> the nearest frame index on the grid."""
    return int(round(Fraction(t).limit_denominator(10 ** 9) * FPS)) if not isinstance(t, int) else int(round(t * FPS))


def fsec(k):
    """frame index -> seconds (exact grid time as a float)."""
    return float(Fraction(k) / FPS)


def sn(t):
    """t snapped onto the frame grid (seconds, 6 dp)."""
    return round(fsec(frames(float(t))), 6)


def beat(word_t, scene_start):
    """A comp-relative event time for a spoken word: about 1.5 frames before the word, on the grid, never negative."""
    return max(0.0, sn(float(word_t) - float(scene_start) - EVENT_LEAD_S))


def _floor(x, dp):
    q = 10 ** dp
    return math.floor(Fraction(x) * q) / q


def t6(k):
    """frame k as a JS/HTML time: floored at 6 dp, so a set can never land a hair AFTER its own frame and miss it."""
    return "0" if k == 0 else f"{_floor(Fraction(k) / FPS, 6):.6f}"


def d6(n):
    """n frames as a tween duration."""
    return f"{float(Fraction(n) / FPS):.6f}"


def d4(n):
    """n frames as the root's data-duration: 4 dp, floored, so the renderer's frame count is exactly n."""
    return f"{_floor(Fraction(n) / FPS, 4):.4f}"


def step_sample(k, step, rate=None):
    """The sample of a STEP_FPS render (its index at `step` fps) that grid frame k SHOWS. render.sh holds the step render
    up to the grid through ffmpeg's fps filter, which puts sample j on frame floor(j x rate / step + 1/2) and repeats it
    forward, so frame k shows the last sample landed at or before it."""
    rate = Fraction(rate or FPS)
    on = lambda j: math.floor(Fraction(j) * rate / step + Fraction(1, 2))
    j = math.floor(Fraction(k) * step / rate) + 1
    while j > 0 and on(j) > k:
        j -= 1
    return j


def step_cut(t, step):
    """A picture cut at comp time t on a STEPPED comp (rendered at `step` fps and held up to the grid): the position that
    shows the change ON t's frame. A set on the frame's own grid time misses the sample that frame shows whenever the
    sample is earlier (at 23.976 frame 120 shows sample 60, t 5.000; a set at 5.005 lands in sample 61, 2 frames late:
    the 2026-10-14 offer sheet), so the cut goes on the last grid frame at or before that sample, and the change shows
    from the frame the sample lands on: t's own or the one before, never after. step None = the grid itself (sn)."""
    if not step or step >= FPS:
        return sn(t)
    j = step_sample(frames(max(0.0, float(t))), step)
    return fsec(math.floor(Fraction(j) * FPS / step))


class Word(float):
    """A matched phrase: the float value is its first word's start; .start .end .text .index ride along."""

    def __new__(cls, start, end=None, text="", index=-1):
        o = super().__new__(cls, float(start))
        o.start, o.end, o.text, o.index = float(start), float(start if end is None else end), text, index
        return o

    def __repr__(self):
        return f"Word({self.text!r} {self.start:.3f}-{self.end:.3f})"


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).lower()
    return "".join(ch for ch in s if ch.isalnum())


class Ctx:
    """One job: its plan (fps, cells, layout), the canonical transcript words and transcript/voices.json. Creating it
    sets the build's frame grid and the gfx folder the capture emitter probes media in."""

    def __init__(self, job):
        global _GFX
        self.job = Path(job).resolve()
        self.name = self.job.name
        self.hf = self.job / "hf-graphics"
        self.gfx = self.hf / "gfx"
        pp = self.job / "graphics-plan.json"
        if not pp.exists():
            raise BuildError(f"no graphics-plan.json in {self.job}")
        self.plan = json.loads(pp.read_text(encoding="utf-8"))
        if self.plan.get("fps") in (None, ""):
            raise BuildError("graphics-plan.json has no `fps`: the grid every time snaps to (the sequence's rate, e.g. 24000/1001)")
        self.fps = use_fps(self.plan["fps"])
        _GFX = self.gfx
        self.cells = {c["id"]: c for c in self.plan.get("beats") or [] if c.get("id")}
        self.layout = self.plan.get("layout") or []
        tp = self.job / "outputs" / f"{self.name}.transcript.json"
        self.transcript_path = tp
        raw = json.loads(tp.read_text(encoding="utf-8")).get("words", []) if tp.exists() else []
        self.words = [w for w in raw if w.get("type", "word") == "word" and w.get("start") is not None]
        self._n = [_norm(w.get("text", "")) for w in self.words]
        vp = self.job / "transcript" / "voices.json"
        self.voices = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else None

    def sn(self, t):
        return sn(t)

    def beat(self, word_t, scene_start):
        return beat(word_t, scene_start)

    def cell(self, gid):
        if gid not in self.cells:
            raise BuildError(f"no plan cell {gid!r}: the plan has {sorted(self.cells)}")
        return self.cells[gid]

    def mode_at(self, t):
        """(mode, caption_y) of the plan's layout row holding t (layout.md § 12), or (None, None). The caption line is
        layout_row()'s: an F row's `ui_bottom` gives ui_bottom + 58.5, and an F row kept clear by a seam_clear cell
        takes the seam."""
        for r in self.layout:
            a, b, m, cy = layout_row(r, self.plan)
            if a is not None and float(a) - 1e-6 <= t < float(b) - 1e-6:
                return m, cy
        return None, None

    def find(self, phrase, nth=None, after=None, before=None):
        """The phrase's first word as a Word (start; .end = the phrase's last word's end). Tokens match normalized
        (case, punctuation and hyphens ignored, so "wi-fi" finds "Wi-Fi"). A miss raises with the nearest words; a
        phrase said more than once raises listing every hit unless `nth` (1-based) or `after` (s) picks one. `before`
        (s) bounds the search: a phrase starting at or after it is not a hit (build.py's said() passes the cell's end,
        so a word the reel says again in a LATER line, a callback, never makes the cell's own word ambiguous)."""
        if not self.words:
            raise BuildError(f"no words: {self.transcript_path} is missing or empty (step 2 writes it)")
        target = "".join(_norm(t) for t in str(phrase).split())
        if not target:
            raise BuildError(f"find({phrase!r}): nothing to match")
        hits = []
        for i, n0 in enumerate(self._n):
            if not n0 or (after is not None and self.words[i]["start"] < float(after) - 1e-6) \
                    or (before is not None and self.words[i]["start"] >= float(before) - 1e-6):
                continue
            acc, j = "", i
            while j < len(self._n) and len(acc) < len(target):
                acc += self._n[j]
                j += 1
                if not target.startswith(acc):
                    break
            if acc == target:
                hits.append((i, j - 1))
        ctx = lambda i, j: " ".join(w["text"] for w in self.words[max(0, i - 3):j + 4])
        if not hits:
            first = _norm(str(phrase).split()[0])
            near = difflib.get_close_matches(first, sorted(set(self._n)), n=5, cutoff=0.6)
            cands = [f"{self.words[i]['text']!r} @{self.words[i]['start']:.3f}" for i, n in enumerate(self._n) if n in near][:10]
            raise BuildError(f"find({phrase!r}{', after=%s' % after if after is not None else ''}"
                             f"{', before=%s' % before if before is not None else ''}): not in the transcript. "
                             f"Nearest: {cands or 'none'}")
        if nth is None and len(hits) > 1:
            listed = "; ".join(f"#{k + 1} @{self.words[i]['start']:.3f} ...{ctx(i, j)}..." for k, (i, j) in enumerate(hits))
            raise BuildError(f"find({phrase!r}) is said {len(hits)} times: pick one with nth= or after=. {listed}")
        k = (nth or 1) - 1
        if not 0 <= k < len(hits):
            raise BuildError(f"find({phrase!r}, nth={nth}): only {len(hits)} hit(s)")
        i, j = hits[k]
        return Word(self.words[i]["start"], self.words[j]["end"], " ".join(w["text"] for w in self.words[i:j + 1]), i)


# ── the layout rows: ONE resolution of a row's caption line, layout.py's (layout.md § 12) ───────────────────────────
_LAYOUT = None


def _layout_py():
    """presets/instagram/talking-head-explainer/layout.py, imported by path (the kit never re-derives its rules)."""
    global _LAYOUT
    if _LAYOUT is None:
        path = PRESET / "layout.py" if PRESET else None
        if not path or not path.exists():
            raise BuildError("layout.py not found: the kit resolves caption lines through the preset's own layout.py "
                             "(re-run `engine.py init` from the repo so KIT.json records it)")
        spec = importlib.util.spec_from_file_location("th_layout_kit", path)
        _LAYOUT = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_LAYOUT)
    return _LAYOUT


def layout_row(r, plan=None, extra_cells=()):
    """(start, end, mode, caption_y) of a `layout` row, dict or list form, resolved exactly as layout.py resolves it: an
    F row's `ui_bottom` gives its line (ui_bottom + 58.5, captions-style.md § 2); an F row with neither caption_y nor
    ui_bottom that a `seam_clear` cell covers keeps its caption on the seam (caption_y = SEAM, zone() then ends above
    the gate band). Anything else keeps caption_y None, and a full-screen zone refuses it."""
    a, b, m, cy = _layout_py()._row(r)
    if m == "F" and cy is None and a is not None:
        cells = list((plan or {}).get("beats") or []) + list(extra_cells or [])
        if any(c.get("seam_clear") and float(c.get("start", 0)) < float(b) - 1e-6 and float(c.get("end", 0)) > float(a) + 1e-6
               for c in cells):
            cy = SEAM
    return a, b, m, cy


# ── capture geometry: frame by the rectangle that must be whole (captures.md § 3, § 6) ─────────────────────────────
def zone(layout="split", caption_y=None):
    """(top, bottom) of the content zone on the 1080x1920 frame. Split y200-845; full y260 to 20 px above its caption
    box (the plan's F row carries caption_y or ui_bottom); a full-screen whose caption stays on the seam (a seam_clear
    graphic, caption_y = SEAM) ends 20 px above the gate band."""
    if layout == "split":
        return SPLIT_ZONE
    if layout == "full":
        if caption_y is None:
            raise BuildError("a full-screen needs its caption line: the F row's caption_y or ui_bottom (layout.md § 12), "
                             "or a seam_clear cell over it; the zone ends 20 px above the caption box")
        if abs(float(caption_y) - SEAM) < 0.5:
            return (FULL_TOP, GATE_BAND[0] - FULL_AIR)
        return (FULL_TOP, float(caption_y) - CAPTION_BOX_ABOVE - FULL_AIR)
    raise BuildError(f"layout {layout!r}: split or full")


def _cy(layout, caption_y=None):
    a, b = zone(layout, caption_y)
    return (a + b) / 2


def fit(rect, layout="split", margin=1.0, caption_y=None):
    """((fx, fy), zoom) that puts the SOURCE rectangle [x0, y0, x1, y1] whole and centred in the content zone; margin < 1
    leaves air around it. The zoom is derived, never typed: a named rectangle cannot be clipped."""
    x0, y0, x1, y1 = (float(v) for v in rect)
    if x1 <= x0 or y1 <= y0:
        raise BuildError(f"fit({rect}): not a rectangle")
    top, bot = zone(layout, caption_y)
    z = min(FRAME_W * margin / (x1 - x0), (bot - top) * margin / (y1 - y0))
    return (round((x0 + x1) / 2, 1), round((y0 + y1) / 2, 1)), round(z, 4)


@dataclasses.dataclass
class Take:
    """A capture's source frame. `column` = (x0, x1) of a chat column in source px (the chat helpers fill the panel width
    with it)."""
    size: tuple
    column: tuple = None

    @property
    def w(self):
        return self.size[0]

    @property
    def h(self):
        return self.size[1]

    @property
    def cx(self):
        return (self.column[0] + self.column[1]) / 2 if self.column else self.w / 2

    @property
    def colz(self):
        if not self.column:
            raise BuildError("this Take has no chat column: pass Take(size, column=(x0, x1))")
        return FRAME_W / (self.column[1] - self.column[0])

    def crop(self, bottom=None):
        """The window rectangle: the column, skipping the rail separator (+4) and the window's bottom border (-4), so
        no hairline shows where the capture meets its fill. `bottom` = a reply crop ending just under the reply."""
        if not self.column:
            return [0, 0, self.w, bottom or self.h]
        return [self.column[0] + 4, 0, self.column[1], bottom if bottom is not None else self.h - 4]


def _hdr_top(layout):
    return HEADER["top"][layout]


def _first_row(layout):
    return _hdr_top(layout) + HEADER["px"] + HEADER["gap"]


def _dock_y(layout, caption_y=None):
    return DOCK["split"] if layout == "split" else zone("full", caption_y)[1]


def dock(take, zoom_mul=1.0, layout="split", caption_y=None):
    """The column fills the width and the window's bottom edge docks at DOCK: input bar and send button whole, above the
    caption. It shows whatever history is above, so use it only where that history belongs on screen (or mask it)."""
    z = take.colz * zoom_mul
    return (take.cx, round(take.h - (_dock_y(layout, caption_y) - _cy(layout, caption_y)) / z, 1)), round(z, 4)


def under_header(take, top_src, zoom_mul=1.0, layout="split", caption_y=None):
    """Source row top_src sits just under the pinned header; everything above it is behind the header and its mask."""
    z = take.colz * zoom_mul
    return (take.cx, round(top_src + (_cy(layout, caption_y) - _first_row(layout)) / z, 1)), round(z, 4)


def content_floor(layout="split", caption_y=None):
    """The lowest frame y a chat's CONTENT (bubbles, reply text) may reach: the content zone's bottom (split y845, 75 px
    above the seam caption's box). The window's plain bottom edge may run lower, to the dock (split y880): two numbers,
    captures.md § 6 and layout.md § 8."""
    return zone(layout, caption_y)[1]


def thread(take, top_src, zoom_mul=1.0, layout="split", bottom_src=None, caption_y=None, content_src=None, fit_push=None):
    """The visible thread starts at top_src (a gap row above the first bubble that belongs on screen) AND the window's
    bottom edge is docked AND its last content row (content_src, the reply's end) stays on the content floor: the
    largest zoom that fits all three, capped at the column fit. zoom_mul pushes the column and dock fit; the content
    floor is a hard ceiling at every push. fit_push = the largest push the shot reaches (a drift from 1.0 to 1.008):
    the content is fitted at THAT push, so every frame of the drift keeps the floor and the drift still moves (capping
    each push on its own would flatten a push whose content fit binds)."""
    bottom_src = take.h if bottom_src is None else bottom_src
    z = min(take.colz, (_dock_y(layout, caption_y) - _first_row(layout)) / (bottom_src - top_src))
    if content_src is not None:
        fit = (content_floor(layout, caption_y) - _first_row(layout)) / (content_src - top_src)
        top = max(zoom_mul, fit_push or zoom_mul)
        z = min(z, fit / top)
    z *= zoom_mul
    return (take.cx, round(top_src + (_cy(layout, caption_y) - _first_row(layout)) / z, 1)), round(z, 4)


def reply(take, top_src, z, fx=None, layout="split", top_px=None, caption_y=None):
    """A tall reply framed WHOLE with the input bar out of frame, at an explicit zoom (above the column fit only when the
    bot's left-aligned bubbles alone are in view: fx slides so they stay whole). Always pair it with chat_ok()."""
    fx = take.cx if fx is None else fx
    return (fx, round(top_src + (_cy(layout, caption_y) - (top_px or _first_row(layout))) / z, 1)), round(z, 4)


def chat_ok(framing, content_end, empty=None, x_whole=None, layout="split", take=None, caption_y=None, size=None):
    """Raise at BUILD time when a reply would end in the caption band, the panel edge cuts a bubble, or the bubbles are
    not whole in x. empty = (y0, y1) source rows of empty chat the panel edge may fall in; x_whole = (x0, x1) source
    columns that must be in view. Returns the framing."""
    (fx, fy), z = framing
    cy = _cy(layout, caption_y)
    end_px = cy + (content_end - fy) * z
    floor = content_floor(layout, caption_y)
    if end_px > floor + 1:
        raise BuildError(f"chat_ok: the reply ends at panel y{end_px:.0f}, past the content floor y{floor:.0f} (key ink "
                         f"stays 75 px above the seam caption's box; only the window's plain edge may reach the dock "
                         f"y{_dock_y(layout, caption_y):.0f}): crop tighter or frame it smaller")
    h = (size or (take.size if take else (None, None)))[1]
    edge = PANEL_H[layout] if layout == "split" else FRAME_H
    bottom_src = fy + (edge - cy) / z
    if h is not None:
        whole = bottom_src >= h - 2
        in_gap = empty is not None and empty[0] <= bottom_src <= empty[1]
        if not (whole or in_gap):
            raise BuildError(f"chat_ok: the panel edge cuts source y{bottom_src:.0f}, not empty chat {empty} and not below "
                             f"the window (h {h}): it slices a bubble")
    if x_whole is not None:
        x0, x1 = fx - FRAME_W / 2 / z, fx + FRAME_W / 2 / z
        if x0 > x_whole[0] or x1 < x_whole[1]:
            raise BuildError(f"chat_ok: bubbles x{tuple(x_whole)} are not whole in view x{x0:.0f}-{x1:.0f}")
    return framing


# ── scenes ─────────────────────────────────────────────────────────────────────────────────────────────────────────
@dataclasses.dataclass
class Scene:
    """One graphic, ready for comp(): its html (the emitters build the panel, the capture windows, the backdrop), its js
    on the comp's one paused timeline, the SFX events it implies, what must be on screen on frame 0 and its content's
    extent. Build it through authored() / overlay() / capture() (components.py does); comp() asserts the rest."""
    id: str
    start: float
    dur: float
    layout: str                      # split | full | overlay
    family: str                      # authored | capture | capture-white | montage | overlay
    html: str
    js: str
    css: str = ""
    events: list = dataclasses.field(default_factory=list)      # [{event, at (comp s), note?, dur?}]
    visible0: list = dataclasses.field(default_factory=list)    # selectors that must be on screen on comp frame 0
    bbox: tuple = None                                          # the content's extent (x0, y0, x1, y1), FRAME px
    units: str = "frame"                                        # authored html: "frame" px, or "panel" (the 0.79 fit)
    glow_phase: float = 0.0          # authored: where the backdrop drift starts (a push join continues the outgoing comp's)
    meta: dict = dataclasses.field(default_factory=dict)

    @property
    def frames(self):
        return frames(self.dur)

    @property
    def end(self):
        return self.start + self.dur


def ev(event, at, note="", dur=None, sync_offset=None):
    """One SFX event row: a documented sfx.json event at a comp-relative time on the grid (dur: a sound fitted to a span,
    a ring to its answer, typing to its text). write_events() writes them as `src: kit` rows. sync_offset = a DESIGNED
    offset of this beat from its word's beat, in seconds (negative = ahead: masked_value's VALUE_KEY_LEAD_S), recorded
    on the row so `change-events.py --sync` and a reader see the lead is designed, never an unexplained one."""
    r = {"event": event, "at": sn(at)}
    if note:
        r["note"] = note
    if dur is not None:
        r["dur"] = round(float(dur), 4)
    if sync_offset is not None:
        r["sync_offset"] = round(float(sync_offset), 4)
    return r


def _sels(v):
    return [v] if isinstance(v, str) else list(v or [])


def _span(dur, what):
    n = frames(float(dur))
    if n < 1:
        raise BuildError(f"{what}: {dur} s is under one frame")
    return n


def authored(html, js, css="", layout="split", *, id=None, start=0.0, dur=None, events=None, visible0=None, bbox=None,
             units="frame", glow_phase=0.0):
    """An AUTHORED motion graphic: the opaque panel (split y0-960, or full) with the house backdrop (fill, grid, the
    drifting centre light on the main timeline, vignette, the split seam). `html` is the content, authored in FRAME
    coordinates inside the zone (split y200-845), no scale wrapper; units="panel" instead wraps a 1080x960 panel layout
    scaled 0.79 about the seam centre (graphics.md § Units: what components.py writes). bbox is FRAME px either way."""
    if id is None or dur is None:
        raise BuildError("authored() needs id= and dur=")
    if layout not in ("split", "full"):
        raise BuildError(f"{id}: authored layout {layout!r}: split or full")
    if units not in ("frame", "panel") or (units == "panel" and layout != "split"):
        raise BuildError(f"{id}: units={units!r}: frame, or panel on a split")
    n = _span(dur, id)
    inner = f'<div class="safe">{html}</div>' if units == "panel" else html
    seam = '<div class="seam"></div>' if layout == "split" else ""
    body = (f'<div class="panel" id="panel" style="height:{PANEL_H[layout]}px;"><div class="glow"></div><div class="vig"></div>'
            f"{inner}{seam}</div>")
    return Scene(id, sn(start), fsec(n), layout, "authored", body, js, css, list(events or []), _sels(visible0), bbox,
                 units, glow_phase)


def overlay(html, js, css="", *, id=None, start=0.0, dur=None, events=None, visible0=None, bbox=None):
    """An OVERLAY on live footage (the call card over the wide face): no panel, no backdrop, timeline rate, never stepped
    (its motion is synced to live audio)."""
    if id is None or dur is None:
        raise BuildError("overlay() needs id= and dur=")
    n = _span(dur, id)
    return Scene(id, sn(start), fsec(n), "overlay", "overlay", html, js, css, list(events or []), _sels(visible0), bbox)


def layer(scene, child, at=0.0):
    """Nest `child` (usually an overlay Scene: a call card dropped over a chat because the chat cannot show the call the
    line names) inside `scene` from `at` (scene-relative s), on top of the panel and outside any 0.79 fit (frame px). The
    child's script runs on its own sub-timeline added at `at`, with `tl` and `DUR` bound to its own (so it writes tl.*
    calls; an H.* registry call would land on the parent's clock); its events shift by `at`. Returns `scene`."""
    k = frames(at)
    if k + child.frames > scene.frames + 1:
        raise BuildError(f"layer({child.id} into {scene.id}): it runs {child.frames} frames from frame {k}, past the scene's {scene.frames}")
    close = scene.html.rfind("</div>") if scene.layout != "overlay" else len(scene.html)
    scene.html = scene.html[:close] + child.html + scene.html[close:]
    scene.css += "\n" + child.css
    scene.js += ("\n(function(){ const main = tl; const sub = gsap.timeline(); (function(tl, DUR){\n" + child.js +
                 f"\n}})(sub, {d4(child.frames)}); main.add(sub, {t6(k)}); }})();")
    scene.events += [dict(e, at=sn(fsec(k) + float(e["at"]))) for e in child.events]
    return scene


def _media_src(media):
    m = str(media)
    return m if m.startswith("assets/") else f"assets/captures/{m}"


_SIZES = {}


def _media_size(media, size=None):
    if size:
        return int(size[0]), int(size[1])
    if _GFX is None:
        raise BuildError(f"{media}: no size given and no Ctx(job) to find the file under gfx/assets")
    p = Path(_GFX) / _media_src(media)
    if p in _SIZES:
        return _SIZES[p]
    if not p.exists():
        raise BuildError(f"{media}: not found at {p} (captures live in hf-graphics/gfx/assets/captures)")
    if p.suffix.lower() in VIDEO_EXT:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0:s=x", str(p)], capture_output=True, text=True)
        w, h = (int(v) for v in r.stdout.strip().split("\n")[0].strip("x").split("x")[:2])
    else:
        from PIL import Image
        with Image.open(p) as im:
            w, h = im.size
    _SIZES[p] = (w, h)
    return w, h


def _rgb(c):
    c = c.strip()
    if c.startswith("#") and len(c) in (4, 7):
        h = c[1:] if len(c) == 7 else "".join(ch * 2 for ch in c[1:])
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", c)
    if m:
        return tuple(int(v) for v in m.groups())
    raise BuildError(f"bg {c!r}: a hex or rgb() colour sampled off a rendered frame")


def _is_light(bg):
    r, g, b = _rgb(bg)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.6


def _transparent(bg):
    r, g, b = _rgb(bg)
    return f"rgba({r},{g},{b},0)"


def _framing(v, what):
    if isinstance(v, dict):
        return (float(v["f"][0]), float(v["f"][1])), float(v["z"])
    try:
        (fx, fy), z = v
        return (float(fx), float(fy)), float(z)
    except (TypeError, ValueError):
        raise BuildError(f"{what}: a framing is ((fx, fy), z) or {{f: [x, y], z}}, got {v!r}")


def capture(spec):
    """A SCREEN-RECORDING scene: the whole panel is the capture's own fill (`bg`, REQUIRED, sampled off a RENDERED frame),
    no rim, filter, depth of field or backdrop. Shots butt-cut inside one comp:

      spec = {id, start, layout split|full, bg, look flat|montage, readable, follows face|graphic, caption_y (full),
              header {img, top} (the app's own header, pinned, 46 px fade), extra_html / extra_css / extra_js,
              shots: [{media, t0 (media s), dur, rect (+ margin, push) | from / to (((fx, fy), z) or {f, z}, SOURCE px),
                       crop [x0,y0,x1,y1], hide_above int|[a, b], mask_ease, ease, tilt, swing, size, bg (this shot's
                       own fill), reveal {media, rect, at, dy, dur, size, ease}, events [{event, at (shot s) | media_t}]}]}

    Per-shot fills (captures.md § 4: every shot of a multi-shot scene sits on its own page colour): a shot's `bg`, sampled
    off a rendered frame like the scene's, gets a full-panel fill layer under the windows (one per distinct fill), shown
    for exactly that shot's frames and switched ON its cut frame, the frame the outgoing shot leaves; its history mask and
    the top mask take it too. A shot naming none sits on the scene's `bg`, which also names the family (capture or
    capture-white). A montage keeps its one in-plane fill and a pinned header its one app's: both refuse a shot's own bg.

    Built in: flat = no tilt and a total push of at most DRIFT_MAX; montage = never readable, tilt alternating sign,
    fill padded into the plane (PLANE_PAD), scan drawn in the plane at INPLANE_SCAN with period 6 / mean zoom, shots
    outside 0.5-1.4 s warn; every clip after the first pre-rolls hidden (at most PREROLL_MAX_FRAMES), the outgoing shot
    is hidden ON the cut frame (never held under the incoming); the history mask is painted in the shot's fill inside
    the window so it rides the plane; the top of the frame is masked above the header (and above FULL_TOP on a full-screen).
    Events: a montage writes `camera` at every cut (its entry from a graphic too) and, entering from the face,
    `camera-under` + `cut-in`; each shot's own measured events ride along."""
    sid = spec.get("id")
    if not sid:
        raise BuildError("capture: id is required")
    layout = spec.get("layout", "split")
    if layout not in ("split", "full"):
        raise BuildError(f"{sid}: capture layout {layout!r}: split or full")
    bg = spec.get("bg")
    if not bg:
        raise BuildError(f"{sid}: bg is REQUIRED: the capture's own colour sampled off a RENDERED frame (sample_fill); "
                         "renderers before hyperframes 0.8.81 draw video captures darker than their source, so a source-sampled fill shows the card edge")
    _rgb(bg)
    look = spec.get("look", "flat")
    if look not in ("flat", "montage"):
        raise BuildError(f"{sid}: look {look!r}: flat or montage")
    montage = look == "montage"
    readable = spec.get("readable", not montage)
    if readable and montage:
        raise BuildError(f"{sid}: a montage is glanced texture, never read: anything the viewer must read is flat (captures.md § 7)")
    shots = spec.get("shots") or []
    if not shots:
        raise BuildError(f"{sid}: no shots")
    caption_y = spec.get("caption_y")
    top, bot = zone(layout, caption_y)
    cx, cy = FRAME_W / 2, (top + bot) / 2
    H = PANEL_H[layout]
    bounds, k = [], 0
    for i, sh in enumerate(shots):
        n = _span(sh.get("dur", 0), f"{sid} shot {i}")
        bounds.append((k, k + n))
        k += n
    total = k
    if montage:
        lo, hi = MONTAGE["warn_s"]
        lo_f, hi_f = math.floor(lo * float(FPS) + 1e-6), math.ceil(hi * float(FPS) - 1e-6)   # layout.py's frame band
        for i, (a, b) in enumerate(bounds):
            if not lo_f <= b - a <= hi_f:
                print(f"⚠ {sid} montage shot {i}: {fsec(b - a):.2f} s, outside {lo}-{hi} s (a macro shot is a glance)")
    tilts = _montage_tilts(sid, shots) if montage else None
    fam = "montage" if montage else ("capture-white" if _is_light(bg) else "capture")
    # each shot's own fill (its `bg`, else the scene's): a cut page sits on ITS page colour, never the scene's (captures.md
    # § 4; 2026-10-15: a dark checkout cut in after a black page "needs to at least match the background color of
    # whatever you're cropping"). One full-panel layer per distinct fill other than the scene's, under the windows.
    fills = [sh.get("bg") or bg for sh in shots]
    for i, f in enumerate(fills):
        try:
            _rgb(f)
        except BuildError:
            raise BuildError(f"{sid} shot {i}: bg {f!r}: a hex or rgb() colour sampled off a RENDERED frame (sample_fill)")
    layers, lay = [], []
    for f in fills:
        if _rgb(f) == _rgb(bg):
            lay.append(None)
            continue
        if _rgb(f) not in [_rgb(x) for x in layers]:
            layers.append(f)
        lay.append([_rgb(x) for x in layers].index(_rgb(f)))
    if layers and montage:
        raise BuildError(f"{sid}: a montage keeps ONE fill, padded into every tilted plane (captures.md § 7); a per-shot bg "
                         "is a flat capture's")
    if layers and spec.get("header"):
        raise BuildError(f"{sid}: a pinned header is one app's chrome on one fill: its shots share the scene's bg")
    body = [f'<div class="panel solid" id="panel" style="height:{H}px;background:{bg};">']
    body += [f'<div class="xfill el" id="xf{j}" style="position:absolute;left:0;top:0;width:100%;height:100%;background:{f};">'
             "</div>" for j, f in enumerate(layers)]
    js, events, push = [], [], 1.0
    for i, sh in enumerate(shots):
        k0, k1 = bounds[i]
        n, last = k1 - k0, i == len(shots) - 1
        media = sh.get("media")
        if not media:
            raise BuildError(f"{sid} shot {i}: no media")
        W, Hs = _media_size(media, sh.get("size") or spec.get("size"))
        crop = sh.get("crop")
        ox, oy = (crop[0], crop[1]) if crop else (0, 0)
        mw, mh = (crop[2] - crop[0], crop[3] - crop[1]) if crop else (W, Hs)
        place = f"left:{-ox}px;top:{-oy}px;width:{W}px;height:{Hs}px;" if crop else ""
        t0 = float(sh.get("t0", 0))
        if str(media).lower().endswith(VIDEO_EXT):
            pre = min(PREROLL, int(math.floor(t0 * float(FPS) + 1e-6)), k0) if i > 0 else 0
            tag = (f'<video id="xm{i}" class="clip" style="{place}" src="{_media_src(media)}" data-start="{t6(k0 - pre)}" '
                   f'data-media-start="{max(0.0, t0 - pre / float(FPS)):.6f}" data-duration="{d6(n + pre)}" '
                   f'data-track-index="{i}" muted playsinline></video>')
        else:
            tag = f'<img style="{place}" src="{_media_src(media)}"/>'
        ha = sh.get("hide_above")
        if ha is not None:
            a_, b_ = (ha if isinstance(ha, (list, tuple)) else (ha, ha))
            tag += f'<div id="xh{i}" style="position:absolute;left:0;top:0;width:100%;height:{a_ - oy}px;background:{fills[i]};"></div>'
            if a_ != b_:
                md = max(1, min(n, frames(CAPTURE["mask_max_s"])))
                js.append(f"tl.fromTo('#xh{i}',{{height:{a_ - oy}}},{{height:{b_ - oy},duration:{d6(md)},"
                          f"ease:'{sh.get('mask_ease', CAPTURE['drift_ease'])}',immediateRender:false}},{t6(k0)});")
        rv = sh.get("reveal")
        if rv:
            rx0, ry0, rx1, ry1 = rv["rect"]
            fw, fh = _media_size(rv["media"], rv.get("size") or (W, Hs))
            tag += (f'<div id="xr{i}" style="position:absolute;left:{rx0 - ox}px;top:{ry0 - oy}px;width:{rx1 - rx0}px;'
                    f'height:{ry1 - ry0}px;overflow:hidden;opacity:0;"><img src="{_media_src(rv["media"])}" '
                    f'style="position:absolute;left:{-rx0}px;top:{-ry0}px;width:{fw}px;height:{fh}px;"/></div>')
            at_k = k0 + (frames(rv["at"]) if "at" in rv else REVEAL["at_frames"])
            js.append(f"tl.fromTo('#xr{i}',{{y:{rv.get('dy', REVEAL['dy']):g},opacity:0}},{{y:0,opacity:1,"
                      f"duration:{d6(max(1, frames(rv.get('dur', REVEAL['s']))))},ease:'{rv.get('ease', REVEAL['ease'])}',"
                      f"immediateRender:false}},{t6(at_k)});")
        fa, fb = _shot_framing(sid, sh, i, layout, caption_y, montage)
        pad = MONTAGE["pad"] if montage else 0
        if pad:
            tag = f'<div style="position:absolute;left:{pad}px;top:{pad}px;width:{mw}px;height:{mh}px;overflow:hidden;">{tag}</div>'
            per = SCAN_PERIOD / ((fa[1] + fb[1]) / 2)
            amp = MONTAGE["scan"]
            tag += (f'<div style="position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(rgba(0,0,0,{amp}),'
                    f'rgba(0,0,0,0) 50%,rgba(0,0,0,{amp}));background-size:100% {per:.3f}px;background-repeat:repeat;"></div>')
        win = (f"width:{mw + 2 * pad}px;height:{mh + 2 * pad}px;box-shadow:none;border-radius:0;"
               f"background:{bg if pad else 'transparent'};filter:none;")
        fe = sh.get("feather")
        if fe:
            # an uneven page edge (a hero gradient ending hard) fades FEATHER frame px into the fill (captures.md,
            # the background paragraph after § 3). The value was defined in CAPTURE and never applied: a page hero
            # read as a lit rectangle on black (edit-review round 3, 2026-09-27). The window is in SOURCE px, scaled by
            # the shot's zoom, so the ramp is FEATHER / zoom there. feather = True (every edge) or a list of edges.
            edges = ("top", "bottom", "left", "right") if fe is True else tuple(fe)
            ramp = CAPTURE["feather"] / max(1e-6, min(fa[1], fb[1]))
            grads = [f"linear-gradient(to {dict(top='bottom', bottom='top', left='right', right='left')[e]},"
                     f" transparent 0, #000 {ramp:.1f}px)" for e in edges]
            m_ = ",".join(grads)
            win += (f"-webkit-mask-image:{m_};mask-image:{m_};"
                    f"-webkit-mask-composite:source-in;mask-composite:intersect;")
        body.append(f'<div class="cam el" id="xc{i}"><div class="tilt" id="xt{i}"><div class="plane" id="xp{i}">'
                    f'<div class="win" id="xw{i}" style="{win}">{tag}</div></div></div></div>')
        if not montage:
            if any(sh.get("tilt") or ()):
                raise BuildError(f"{sid} shot {i}: a flat capture has no tilt (tilt is the montage's alone: captures.md § 7)")
            if fb[1] > fa[1]:
                push *= fb[1] / fa[1]
        # the outgoing shot leaves ON the cut frame: a held frame showed it round any incoming window smaller than the
        # panel, a flash-scan DOUBLE CUT (captures.md § 12)
        js.append(f"tl.set('#xc{i}',{{opacity:1}},{t6(k0)});" + ("" if last else f" tl.set('#xc{i}',{{opacity:0}},{t6(k1)});"))
        if layers and (i == 0 or lay[i] != lay[i - 1]):
            # the shot's fill switches ON its cut frame, the frame the outgoing shot leaves: no frame shows a page on
            # another page's colour
            if i and lay[i - 1] is not None:
                js.append(f"tl.set('#xf{lay[i - 1]}',{{opacity:0}},{t6(k0)});")
            if lay[i] is not None:
                js.append(f"tl.set('#xf{lay[i]}',{{opacity:1}},{t6(k0)});")
        if montage:
            rx, ry, sw = tilts[i]
            js.append(f"tl.set('#xt{i}',{{rotationX:{rx:g},rotationY:{ry:g},transformOrigin:'{cx:g}px {cy:g}px'}},0);")
            js.append(f"tl.fromTo('#xt{i}',{{rotationY:{ry:g}}},{{rotationY:{ry + sw:g},duration:{d6(n)},ease:'none',"
                      f"immediateRender:false}},{t6(k0)});")
        (ax, ay), (bx, by) = [(cx - (f[0][0] - ox + pad) * f[1], cy - (f[0][1] - oy + pad) * f[1]) for f in (fa, fb)]
        js.append(f"tl.fromTo('#xp{i}',{{x:{ax:.1f},y:{ay:.1f},scale:{fa[1]:g}}},{{x:{bx:.1f},y:{by:.1f},scale:{fb[1]:g},"
                  f"duration:{d6(n)},ease:'{sh.get('ease', 'none')}',immediateRender:false}},{t6(k0)});")
        if montage and i > 0:
            events.append(ev("camera", fsec(k0), f"montage cut {i}"))
        for e in sh.get("events") or []:
            ek = k0 + (frames(e["at"]) if "at" in e else frames(float(e["media_t"]) - t0))
            if not k0 <= ek < k1:
                raise BuildError(f"{sid} shot {i}: event {e.get('event')} at frame {ek} is outside the shot ({k0}-{k1})")
            events.append(ev(e["event"], fsec(ek), e.get("note", f"shot {i}"), e.get("dur")))
    if not montage and push > CAPTURE["drift_max"] + 1e-6:
        raise BuildError(f"{sid}: a flat capture pushes {push:.3f}x in total; a readable capture holds or drifts at most "
                         f"{CAPTURE['drift_max']} (captures.md § 7: a push on a page 'zooms in and looks corny')")
    if montage:
        if spec.get("follows") == "face":
            events[:0] = [ev("cut-in", 0, "hard cut from the face into the montage"), ev("camera-under", 0, "the shutter names what arrived")]
        else:
            events.insert(0, ev("camera", 0, "cut into the montage"))
    hdr = spec.get("header")
    hy = None
    if hdr:
        img, hy = (hdr.get("img"), hdr.get("top", _hdr_top(layout))) if isinstance(hdr, dict) else (hdr, _hdr_top(layout))
    mask = spec.get("top_mask", hy if hdr else (FULL_TOP if layout == "full" else 0))
    if mask and layers:                              # the top mask is the shot's page too, switched on the same cut frames
        body.append(f'<div id="xtm" class="tmask" style="height:{mask}px;background:{fills[0]};"></div>')
        js += [f"tl.set('#xtm',{{backgroundColor:'{fills[i]}'}},{t6(bounds[i][0])});" for i in range(1, len(shots))
               if _rgb(fills[i]) != _rgb(fills[i - 1])]
    elif mask:
        body.append(f'<div class="tmask" style="height:{mask}px;background:{bg};"></div>')
    if hdr:
        body.append(f'<div class="hdr" style="top:{hy}px;background:{bg};"><img src="{_media_src(img)}"/></div>'
                    f'<div class="hdrfade" style="top:{hy + HEADER["px"]}px;background:linear-gradient({bg},{_transparent(bg)});"></div>')
    body.append(spec.get("extra_html", ""))
    body.append("</div>")
    if spec.get("extra_js"):
        js.append(spec["extra_js"])
    return Scene(sid, sn(spec.get("start", 0.0)), fsec(total), layout, fam, "\n".join(body), "\n".join(js),
                 spec.get("extra_css", ""), events, ["#xc0"] + ([f"#xf{lay[0]}"] if lay[0] is not None else []),
                 (0, top, FRAME_W, bot),
                 meta={"look": look, "readable": readable, "bg": bg, "shots": len(shots)})


def _shot_framing(sid, sh, i, layout, caption_y, montage):
    if "rect" in sh:
        m = float(sh.get("margin", CAPTURE["fit"]["montage"] if montage else CAPTURE["fit"]["page"]))
        f0 = fit(sh["rect"], layout, m, caption_y)
        p = float(sh.get("push", MONTAGE["push"][i % 4] if montage else 1.0))
        return f0, (f0[0], round(f0[1] * p, 4))
    if "from" not in sh:
        raise BuildError(f"{sid} shot {i}: frame it by `rect` (the source rectangle that must be whole) or from/to")
    fa = _framing(sh["from"], f"{sid} shot {i} from")
    return fa, _framing(sh.get("to", sh["from"]), f"{sid} shot {i} to")


def _montage_tilts(sid, shots):
    out, prev = [], None
    for i, sh in enumerate(shots):
        given = sh.get("tilt")
        rx, ry = given if given else MONTAGE["tilts"][i % 4]
        if prev is not None and (ry > 0) == (prev > 0):
            if given:
                raise BuildError(f"{sid} montage shot {i}: tilt ry {ry} has the sign of shot {i - 1} ({prev}): the tilt alternates shot to shot")
            ry = -ry
        sw = sh.get("swing", -math.copysign(MONTAGE["swing"][i % 4], ry))
        out.append((float(rx), float(ry), float(sw)))
        prev = ry
    return out


# ── comp writing and its asserts ───────────────────────────────────────────────────────────────────────────────────
_FORBIDDEN = [(re.compile(r"backdrop-filter", re.I), "backdrop-filter (the renderer's blur differs from the browser's; the look is flat)"),
              (re.compile(r"text-shadow", re.I), "text-shadow (a glow is stacked blurred duplicates; captions carry no shadow)"),
              (re.compile(r"\bonUpdate\b"), "onUpdate (it does not fire when the renderer seeks a paused timeline: content renders frozen)"),
              (re.compile(r"Math\.random"), "Math.random (a render must be deterministic)"),
              (re.compile(r"\b(setTimeout|setInterval|requestAnimationFrame)\s*\("), "a timer (only the paused timeline moves anything)")]
_CALL = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\.(set|to|from|fromTo|add|call)\s*\(")
_SPECIAL = {"duration", "ease", "delay", "repeat", "yoyo", "repeatDelay", "immediateRender", "overwrite", "stagger",
            "onComplete", "onStart", "onUpdate", "onRepeat", "paused", "id", "callbackScope", "runBackwards", "yoyoEase",
            "keyframes", "lazy", "inherit", "data", "startAt", "onCompleteParams", "onStartParams", "force3D",
            "transformOrigin", "clearProps"}
_POS_ARG = {"set": 2, "to": 2, "from": 2, "fromTo": 3, "add": 1, "call": 2}
_NUM = re.compile(r"^\s*-?(\d+\.?\d*|\.\d+)(e-?\d+)?\s*$")
GRID_TOL = 1.2e-4                    # a time printed at 4 dp (rounded or floored) is still its frame


def _split_args(s, i):
    """Top-level comma-split of the call whose '(' is at s[i]. Returns ([(a, b, text)], index of the ')')."""
    depth, q, out, start, j = 0, None, [], i + 1, i + 1
    while j < len(s):
        c = s[j]
        if q:
            if c == "\\":
                j += 2
                continue
            if c == q:
                q = None
        elif c in "'\"`":
            q = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                if s[start:j].strip():
                    out.append((start, j, s[start:j]))
                return out, j
            depth -= 1
        elif c == "," and depth == 0:
            out.append((start, j, s[start:j]))
            start = j + 1
        j += 1
    return out, j


def _obj(text):
    """{key: value-text} of an object literal's top level, or None when it is not one."""
    t = text.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    parts, _ = _split_args("(" + t[1:-1] + ")", 0)
    out = {}
    for _, _, p in parts:
        k, sep, v = p.partition(":")
        if sep:
            out[k.strip().strip("'\"")] = v.strip()
    return out


def _targets(text):
    t = text.strip()
    m = re.fullmatch(r"(['\"])(.*)\1", t, re.S)
    if m:
        return [m.group(2)]
    if t.startswith("[") and t.endswith("]"):
        items = [x.strip() for x in t[1:-1].split(",") if x.strip()]
        sel = [re.fullmatch(r"(['\"])(.*)\1", x) for x in items]
        return [s.group(2) for s in sel] if sel and all(sel) else None
    return None


def _eval(expr, names):
    e = expr.strip()
    if _NUM.match(e):
        return float(e)
    if not re.fullmatch(r"[\w\s.+\-*/()]+", e) or not set(re.findall(r"[A-Za-z_]\w*", e)) <= set(names):
        return None
    try:
        return float(eval(e, {"__builtins__": {}}, dict(names)))
    except Exception:
        return None


# the registry calls a comp makes through H (hf-anim.js): what each one tweens, for how long (animations.md's numbers)
_REG = re.compile(r"(?<![\w$.])H\.(riseIn|riseOut|pop|slam|slideIn|slideOut|exit)\s*\(")
_REG_SPAN = {"riseIn": (("y",), 0.55), "riseOut": (("y", "opacity"), 0.35), "pop": (("scale",), "4F"),
             "slam": (("scale",), "7F"), "slideIn": ((), 0.75), "slideOut": ((), 0.38), "exit": (("y", "opacity"), 0.35)}


def _names(dur):
    f = 1 / float(FPS)
    return {"FR": f, "F": f, "FPS": float(FPS), **({"DUR": float(dur)} if dur is not None else {})}


def _scan(js, dur=None):
    """Every timeline call in a comp script: (kind, text span of its position, position text, position s or None, the
    tweens it makes [(target, prop, t0, t1)], a short quote). One parse feeds the grid check and the overlap audit."""
    names, out = _names(dur), []
    for m in _CALL.finditer(js):
        recv, meth = m.group(1), m.group(2)
        args, close = _split_args(js, m.end() - 1)
        call = js[m.start():close + 1]
        short = (call[:110] + "...") if len(call) > 110 else call
        pi = _POS_ARG[meth]
        if len(args) <= pi:
            out.append(("nopos" if recv == "tl" and meth in ("set", "to", "from", "fromTo") else "skip", None, "", None, [], short))
            continue
        a, b, ptxt = args[pi]
        pos = None if re.match(r"\s*['\"`]", ptxt) else _eval(ptxt, names)
        kind = "rel" if re.match(r"\s*['\"`]", ptxt) else "pos"
        tw = []
        tg = _targets(args[0][2]) if recv == "tl" and meth in ("set", "to", "from", "fromTo") else None
        vs = _obj(args[1][2]) if tg and len(args) > 1 else None
        if pos is not None and tg and vs is not None:
            props = set(vs) - _SPECIAL
            if meth == "fromTo" and len(args) > 2:
                to = _obj(args[2][2]) or {}
                props |= set(to) - _SPECIAL
                vs = to
            d = 0.0
            if meth != "set":
                d = _eval(vs.get("duration", "0.5"), names)
                rp = _eval(vs.get("repeat", "0"), names)
                d = None if d is None or rp is None else (math.inf if rp < 0 else d * (rp + 1) + (_eval(vs.get("repeatDelay", "0"), names) or 0) * rp)
            if d is not None:
                dl = _eval(vs.get("delay", "0"), names) or 0.0
                tw = [(sel, p, pos + dl, pos + dl + d) for sel in tg for p in props]
        out.append((kind, (a, b), ptxt, pos, tw, short))
    for m in _REG.finditer(js):
        fn = m.group(1)
        args, close = _split_args(js, m.end() - 1)
        call = js[m.start():close + 1]
        short = (call[:110] + "...") if len(call) > 110 else call
        tg = _targets(args[0][2]) if args else None
        if fn == "exit" and len(args) < 2:
            pos = None if dur is None else float(dur) - 0.35 - 2 / float(FPS)
            span, ptxt = None, ""
        elif len(args) < 2:
            out.append(("skip", None, "", None, [], short))
            continue
        else:
            span, ptxt = (args[1][0], args[1][1]), args[1][2]
            pos = _eval(ptxt, names)
        props, d = _REG_SPAN[fn]
        d = int(d[0]) / float(FPS) if isinstance(d, str) else d
        if fn in ("slideIn", "slideOut") and len(args) > 2:
            side = args[2][2].strip().strip("'\"")
            props = ("x",) if side in ("left", "right") else ("y",)
        tw = [(sel, p, pos, pos + d) for sel in (tg or []) for p in props] if pos is not None else []
        out.append(("pos" if span else "skip", span, ptxt, pos, tw, short))
    return out


def audit_tweens(js, dur=None):
    """Two tweens driving one property of one target at overlapping times, each named: GSAP does not overwrite by
    default, so the last writer wins mid-move (a pulse on an entering lockup snapped it back to full size). Registry calls
    (H.riseIn, H.pop, ...) count with their own spans. Returns a list of problems, empty when clean."""
    by = {}
    for kind, _, _, _, tws, short in _scan(js, dur):
        for sel, p, t0, t1 in tws:
            by.setdefault((sel, p), []).append((t0, t1, short))
    probs = []
    for (sel, p), lst in by.items():
        lst.sort(key=lambda x: x[0])
        for x in range(len(lst)):
            for y in range(x + 1, len(lst)):
                a1, b1, q1 = lst[x]
                a2, b2, q2 = lst[y]
                if a2 >= b1 - 1e-6:
                    break
                if b1 - a1 < 1e-9 and b2 - a2 < 1e-9:
                    continue
                if a1 < b2 - 1e-6 and a2 < b1 - 1e-6:
                    probs.append(f"{sel} {p}: two tweens overlap ({a1:.4f}-{b1:.4f} and {a2:.4f}-{b2:.4f}), the last writer "
                                 f"wins mid-move:\n      {q1}\n      {q2}")
    return probs


def audit_js(js, dur, what="comp"):
    """The static half of the hygiene gate. Returns (js with every literal position rewritten to its frame's floored
    time, report). Raises BuildError on: a position off the frame grid, a relative, label or missing position on tl,
    and audit_tweens' overlaps."""
    errs, edits, unchecked = [], [], 0
    scanned = _scan(js, dur)
    for kind, span, ptxt, pos, _, short in scanned:
        if kind == "nopos":
            errs.append(f"no position (every tween sits at an absolute time): {short}")
        elif kind == "rel":
            errs.append(f"a relative or label position (every tween sits at an absolute time): {short}")
        elif kind == "pos" and pos is None:
            unchecked += 1
        elif kind == "pos":
            k = round(pos * float(FPS))
            if abs(pos - fsec(k)) > GRID_TOL:
                errs.append(f"position {pos:.6f} is off the frame grid (frame {pos * float(FPS):.3f}): {short}")
            elif _NUM.match(ptxt) and ptxt.strip() != t6(k):
                edits.append((span[0], span[1], t6(k)))
    errs += audit_tweens(js, dur)
    if errs:
        raise BuildError(f"{what}: {len(errs)} hygiene defect(s)\n  - " + "\n  - ".join(errs))
    for a, b, new in sorted(edits, reverse=True):
        js = js[:a] + new + js[b:]
    return js, {"snapped": len(edits), "unchecked": unchecked, "calls": len(scanned)}


def _sets_at_zero(js):
    """Selectors put on screen at comp time 0: a tl.set at 0, or a registry entrance (it sets opacity 1) at 0."""
    out = set()
    for kind, _, _, pos, tws, short in _scan(js, 0.0):
        if pos is not None and abs(pos) < 1e-9:
            if short.startswith("tl.set("):
                out |= {t[0] for t in tws}
            elif re.match(r"H\.(riseIn|pop|slam|slideIn)\(", short):
                out |= {t[0] for t in tws}
    return out


def to_frame(x, y):
    """A panel point (units="panel": the 1080x960 layout) -> frame px, through the 0.79 fit about the seam centre."""
    return 540 + (x - 540) * PANEL_TO_FRAME, SEAM + (y - SEAM) * PANEL_TO_FRAME


def _glow_js(phase_frames, n):
    b = BACKDROP
    d1, d2 = max(1, frames(b["drift_s"])), max(1, frames(b["drift2_s"]))
    r1, r2 = (max(0, math.ceil((phase_frames + n) / d) - 1) for d in (d1, d2))   # finite: the renderer clips repeat:-1 anyway
    # the shipped chain tweened y in both loops; GSAP's last writer won, so only the 3.7 s loop ever moved y. The same
    # pixels, written without the fight: x + scale on the long loop, y on the short one.
    loops = (f".set('.glow',{{x:0,y:0,scale:1}},0); @.to('.glow',{{x:{b['drift_x']:g},scale:{b['drift_scale']:g},duration:{d6(d1)},"
             f"ease:'{b['ease']}',yoyo:true,repeat:{r1}}},0); @.to('.glow',{{y:{b['drift2_y']:g},duration:{d6(d2)},ease:'{b['ease']}',"
             f"yoyo:true,repeat:{r2}}},0);")
    if not phase_frames:
        return "tl" + loops.replace("@", "tl") + "\n"
    return ("const gtl = gsap.timeline({paused:true}); gtl" + loops.replace("@", "gtl") +
            f" tl.add(gtl.tweenFromTo({t6(phase_frames)}, {d6(phase_frames)} + DUR, {{ease:'none'}}), 0);\n")


_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=1080, height=1920"/>
<title>@ID@</title>
<script src="@GSAP@"></script>
<script src="hf-anim.js"></script>
<style>
/* @ID@ · @FAMILY@ · @LAYOUT@ · timeline @START@ -> @END@ (@N@ frames at @RATE@) · WRITTEN BY kit/engine.py: edit the build, never this file */
@FONTS@
*{margin:0;padding:0;box-sizing:border-box;}
:root{@TOKENS@}
#root{position:relative;width:1080px;height:1920px;overflow:hidden;background:transparent;font-family:'SFD';color:var(--txt);}
.el{opacity:0;}
.panel{position:absolute;left:0;top:0;width:1080px;overflow:hidden;background:linear-gradient(@GRID@ @LINE@px, transparent @LINE@px) 0 0 / @CELL@px @CELL@px, linear-gradient(90deg, @GRID@ @LINE@px, transparent @LINE@px) 0 0 / @CELL@px @CELL@px, @FILL@;}
.glow{position:absolute;left:@LAT@px;top:@LAT@px;width:@LPX@px;height:@LPX@px;pointer-events:none;border-radius:50%;background:@LIGHT@;}
.vig{position:absolute;inset:0;pointer-events:none;background:@VIG@;}
.seam{position:absolute;left:0;bottom:0;width:100%;height:@SEAMPX@px;pointer-events:none;background:linear-gradient(transparent,@SEAMTO@);}
.safe{position:absolute;left:0;top:0;width:1080px;height:960px;transform-origin:540px 960px;transform:scale(@P2F@);}
.cam{position:absolute;left:0;top:0;width:100%;height:100%;perspective:@PERSP@px;perspective-origin:50% 50%;}
.tilt{position:absolute;left:0;top:0;width:100%;height:100%;transform-style:preserve-3d;}
.plane{position:absolute;left:0;top:0;transform-origin:0 0;}
.win{position:relative;overflow:hidden;}
.win video,.win img{position:absolute;left:0;top:0;width:100%;height:100%;display:block;}
.tmask{position:absolute;left:0;top:0;width:1080px;}
.hdr{position:absolute;left:0;width:1080px;height:@HPX@px;border-bottom:1px solid @HBORDER@;display:flex;align-items:center;overflow:hidden;}
.hdr img{position:static;display:block;width:1080px;height:auto;}
.hdrfade{position:absolute;left:0;width:1080px;height:@HFADE@px;pointer-events:none;}
.surface{background:var(--surface);border-radius:44px;box-shadow:var(--ui-shadow),0 0 0 2px var(--rim) inset;}
.label{font-family:'SFM';font-weight:700;font-size:28px;letter-spacing:2px;text-transform:uppercase;color:var(--muted);}
.bare{display:block;filter:@MARKSHADOW@;}
@CSS@
</style></head>
<body style="margin:0;background:transparent;">
<div id="root" data-composition-id="main" data-width="1080" data-height="1920" data-start="0" data-duration="@DUR@">
@BODY@
</div>
<script>
const FPS = @FPS@, FR = 1/FPS, DUR = @DUR@;
const H = HF.init({fps: FPS, dur: DUR@STEP@});
const tl = H.tl;
@JS@
H.finish();
</script></body></html>
"""


def _fonts_css():
    rows = [f"@font-face{{font-family:'SFD';src:url('assets/fonts/{f}');font-weight:{w};}}" for f, w in FONT_FILES.items()]
    rows.append(f"@font-face{{font-family:'SFM';src:url('assets/fonts/{MONO_FILE}');font-weight:100 900;}}")
    return "\n".join(rows)


def comp(scene, glow_phase=None):
    """The comp HTML for a Scene, after the build-time asserts. glow_phase (s) = where an authored backdrop's drift
    starts: a push join passes the outgoing comp's duration, so the light never jumps at the join."""
    if scene.family not in FAMILIES:
        raise BuildError(f"{scene.id}: family {scene.family!r}: one of {FAMILIES}")
    n = scene.frames
    if n < 1:
        raise BuildError(f"{scene.id}: shorter than one frame")
    what = f"{scene.id} ({scene.family})"
    blob = "\n".join((scene.html, scene.css, scene.js))
    bad = [msg for rx, msg in _FORBIDDEN if rx.search(blob)]
    if bad:
        raise BuildError(f"{what}: " + "; ".join(bad))
    phase = frames(scene.glow_phase if glow_phase is None else glow_phase)
    js = (_glow_js(phase, n) if scene.family == "authored" else "") + scene.js
    js, _ = audit_js(js, fsec(n), what)
    zero = _sets_at_zero(js)
    vis0 = _sels(scene.visible0)
    missing = [s for s in vis0 if s not in zero]
    if missing:
        raise BuildError(f"{what}: {missing} must be visible on comp frame 0 (no empty plate) but have no tl.set(..., 0)")
    if not vis0 and scene.family in ("authored", "overlay"):
        print(f"⚠ {scene.id}: no visible0 declared, so nothing proves the first element is on screen on frame 0")
    if scene.family == "authored" and scene.layout == "split":
        if scene.bbox is None:
            print(f"⚠ {scene.id}: no bbox declared, so the content zone y{SPLIT_ZONE[0]}-{SPLIT_ZONE[1]} is not checked")
        else:
            x0, y0, x1, y1 = scene.bbox
            if y1 > SPLIT_ZONE[1] + 0.5 or y0 < SPLIT_ZONE[0] - 0.5:
                raise BuildError(f"{what}: content bbox y{y0:.0f}-{y1:.0f} leaves the split content zone "
                                 f"y{SPLIT_ZONE[0]}-{SPLIT_ZONE[1]} (under the platform UI, or onto the caption's air)")
    step = FAMILY_FLAGS[scene.family].get("STEP_FPS")
    tok = ";".join(f"--{k}:{v}" for k, v in TOKENS.items())
    rep = {
        "@ID@": scene.id, "@FAMILY@": scene.family, "@LAYOUT@": scene.layout, "@START@": f"{scene.start:.4f}",
        "@END@": f"{scene.start + fsec(n):.4f}", "@N@": str(n), "@RATE@": rate_str(), "@GSAP@": GSAP_URL,
        "@FONTS@": _fonts_css(), "@TOKENS@": tok, "@GRID@": BACKDROP["grid"], "@LINE@": str(BACKDROP["line_px"]),
        "@CELL@": str(BACKDROP["grid_px"]), "@FILL@": BACKDROP["fill"], "@LAT@": str(BACKDROP["light_at"]),
        "@LPX@": str(BACKDROP["light_px"]), "@LIGHT@": BACKDROP["light"], "@VIG@": BACKDROP["vignette"],
        "@SEAMPX@": str(BACKDROP["seam_px"]), "@SEAMTO@": BACKDROP["seam_to"], "@P2F@": f"{PANEL_TO_FRAME:g}",
        "@PERSP@": str(MONTAGE["perspective"]), "@HPX@": str(HEADER["px"]), "@HBORDER@": HEADER["border"],
        "@HFADE@": str(HEADER["fade"]), "@MARKSHADOW@": VALUES["MARK_SHADOW"], "@DUR@": d4(n),
        "@FPS@": f"{FPS.numerator}/{FPS.denominator}", "@STEP@": f", stepFps: {step}" if step else "",
    }
    out = _HEAD
    for k in ("@CSS@", "@BODY@", "@JS@"):
        out = out.replace(k, "\x00" + k + "\x00")
    for k, v in rep.items():
        out = out.replace(k, v)
    return out.replace("\x00@CSS@\x00", scene.css).replace("\x00@BODY@\x00", scene.html).replace("\x00@JS@\x00", js)


def write(scene, gfx_dir):
    """compositions/<id>.html and <id>.family.json (the render wrapper reads the family from it). Returns the comp path."""
    gfx = Path(gfx_dir)
    (gfx / "compositions").mkdir(parents=True, exist_ok=True)
    html = comp(scene)
    p = gfx / "compositions" / f"{scene.id}.html"
    p.write_text(html, encoding="utf-8")
    fam = {"id": scene.id, "family": scene.family, "layout": scene.layout, "start": round(scene.start, 6),
           "dur": round(scene.dur, 6), "frames": scene.frames, "fps": rate_str(), "flags": FAMILY_FLAGS[scene.family],
           "units": scene.units, "events": len(scene.events),
           **{k: v for k, v in scene.meta.items() if k in ("look", "readable", "bg", "kind", "role", "copy")}}
    (gfx / "compositions" / f"{scene.id}.family.json").write_text(json.dumps(fam, indent=1) + "\n", encoding="utf-8")
    print(f"{scene.id:<8} {scene.family:<13} {scene.layout:<7} {scene.start:9.3f} -> {scene.end:9.3f}  {scene.frames:4d}f  "
          f"{len(scene.events)} sfx")
    return p


def sfx_events():
    """{event: spec} of the preset's sfx.json (the house map when the preset has none, as sfx-plan.py does)."""
    for p in (PRESET / "sfx.json" if PRESET else None, REPO / "presets/youtube/default/sfx.json" if REPO else None):
        if p and p.exists():
            return json.loads(p.read_text(encoding="utf-8")).get("events", {}), p
    raise BuildError("no sfx.json found (the preset's, or presets/youtube/default's)")


def write_events(hf_dir, gid, events, silent=None):
    """Merge this graphic's kit rows into hf-graphics/sfx-hand.json: only the `"src": "kit"` rows of `gid` are replaced,
    so his hand rows and every other graphic's rows stay byte-for-byte. Every event must be documented in the preset's
    sfx.json (not silence, not hand_only). `at` is comp-relative seconds, as sfx-plan.py reads hand rows. silent = why a
    graphic with no events of its own is silent BY DESIGN (a brand page rides the layout's cut-in): one
    {"gid", "silent": true, "src": "kit", "note"} row, which answers sfx-plan's "needs a hand entry" for it."""
    known, src = sfx_events()
    rows = [] if events or not silent else [{"gid": gid, "silent": True, "src": "kit", "note": str(silent)}]
    for e in events or []:
        name = e.get("event")
        if name not in known:
            raise BuildError(f"{gid}: sfx event {name!r} is not in {src.name} ({src.parent.name}): document it there first. "
                             f"Known: {sorted(k for k in known if not k.startswith('_'))}")
        spec = known[name]
        if not isinstance(spec, dict):
            raise BuildError(f"{gid}: sfx event {name!r} is documented silence in {src.name}: the kit never writes it")
        if spec.get("hand_only"):
            raise BuildError(f"{gid}: sfx event {name!r} is hand_only: his call, never the kit's")
        r = {"gid": gid, "event": name, "at": round(sn(e["at"]), 4), "src": "kit"}
        if e.get("note"):
            r["note"] = e["note"]
        if e.get("dur") is not None:
            r["dur"] = round(float(e["dur"]), 4)
        if e.get("sync_offset") is not None:
            r["sync_offset"] = round(float(e["sync_offset"]), 4)
        rows.append(r)
    p = Path(hf_dir) / "sfx-hand.json"
    old = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    keep = [r for r in old if not (r.get("gid") == gid and r.get("src") == "kit")]
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(keep + sorted(rows, key=lambda r: r.get("at", 0)), indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return len(rows)


# ── utilities ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError(f"{' '.join(str(c) for c in cmd[:6])} ... failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-600:]}")
    return r


def all_intra(src, dst):
    """The render-base copy of a capture: every frame a keyframe, so every seek lands exactly (long-GOP captures starved
    the renderer on seeks: blank frames, aborted renders). The original is kept."""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:v", "libx264", "-g", "1", "-keyint_min", "1", "-crf", "14",
          "-preset", "fast", "-pix_fmt", "yuv420p", "-an", str(dst)])
    return Path(dst)


def sample_fill(png, xy, r=4):
    """The capture's fill as '#rrggbb', sampled off a RENDERED frame (the median of a (2r+1)^2 patch, so scan lines and
    grain do not skew it). Never sample the source file: the renderer draws video captures darker."""
    from PIL import Image
    with Image.open(png) as im:
        im = im.convert("RGB")
        x, y = int(xy[0]), int(xy[1])
        px = [im.getpixel((min(im.width - 1, max(0, x + dx)), min(im.height - 1, max(0, y + dy))))
              for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
    med = [sorted(c[i] for c in px)[len(px) // 2] for i in range(3)]
    return "#%02x%02x%02x" % tuple(med)


def frame_count(video):
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
              "stream=nb_read_packets", "-of", "csv=p=0", str(video)])
    # the first row only: ffprobe 9 prints a timecoded file's video row twice (5959 for 59 frames)
    row = next((l for l in r.stdout.splitlines() if l.strip()), "")
    return int(re.sub(r"\D", "", row) or 0)


HF = "hyperframes@0.8.105"             # the renderer the reference render.sh pins
HF_BEFORE = "2026-10-01T23:59:59Z"     # and its npm freeze (fullscreen-render.sh § THE NPM FREEZE): never a bare date


def last_frame(render, png=None):
    """The outgoing graphic's FINAL STATE for a push handover, as an RGBA png (default gfx/assets/push/<stem>-last.png).
    For an authored or overlay comp it is the content ALONE on transparency, rendered from the comp at its last frame
    with no panel fill, grid, glow, vignette or seam and no post pass: the incoming comp's own backdrop continues the
    drift behind it and its finish lands once, so the join differs by grain only (a finished frame here was bloomed twice
    and carried its own backdrop in as a lighter slab). A capture, or a render with no comp beside it, gives the render's
    last frame. Returns the png's path."""
    render = Path(render).resolve()
    gfx = render.parent.parent if render.parent.name == "renders" else None
    gid = render.stem.rpartition("-alpha")[0] or render.stem
    comp_p = gfx / "compositions" / f"{gid}.html" if gfx else None
    png = Path(png) if png else (gfx or render.parent) / "assets" / "push" / f"{render.stem}-last.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    fam = {}
    if comp_p and comp_p.exists() and (gfx / "compositions" / f"{gid}.family.json").exists():
        fam = json.loads((gfx / "compositions" / f"{gid}.family.json").read_text(encoding="utf-8"))
    if fam.get("family") not in ("authored", "overlay"):
        n = frame_count(render)
        sys.path.insert(0, str(REPO / "workflows"))
        from ffmpeg_compat import passthrough  # -fps_mode or -vsync 0, whichever this ffmpeg has
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(render), "-vf", f"select=eq(n\\,{n - 1})", *passthrough(),
              "-frames:v", "1", "-pix_fmt", "rgba", str(png)])
        return png
    rate = parse_rate(fam.get("fps") or rate_str())
    n = int(fam["frames"])
    t_end = t6(n - 1) if n > 1 else "0"
    step = (fam.get("flags") or {}).get("STEP_FPS")
    if step:   # a stepped render's last frame is a HELD sample: ffmpeg's fps filter puts sample j on frame round(j x rate / sf)
        sf, dur = int(step), float(_floor(Fraction(n) / rate, 4))       # and repeats it forward, so frame n-1 shows the last j
        on = lambda j: math.floor(Fraction(j) * rate / sf + Fraction(1, 2))   # whose frame is <= n-1
        j = min(int((n - 1 + 0.5) * sf / float(rate)) + 1, math.ceil(dur * sf - 1e-3) - 1)
        while j > 0 and on(j) > n - 1:
            j -= 1
        t_end = f"{_floor(Fraction(j, sf), 6):.6f}"
    one = f"{_floor(Fraction(1) / rate, 4):.4f}"
    h = comp_p.read_text(encoding="utf-8")
    h = h.replace("</style>", ".panel{background:transparent !important}.glow,.vig,.seam{display:none !important}\n</style>", 1)
    h = re.sub(r'(id="root"[^>]*data-duration=")[\d.]+(")', rf"\g<1>{one}\g<2>", h, count=1)
    hold = ("\n(function(){ const orig = window.__timelines.main; const hold = gsap.timeline({paused:true}); "
            f"hold.add(orig.tweenFromTo({t_end}, {t_end} + 0.0001, {{ease:'none'}}), 0); hold.set({{}}, {{}}, {one}); "
            "hold.progress(0); window.__timelines.main = hold; })();\n")
    i = h.rindex("H.finish();") + len("H.finish();")
    h = h[:i] + hold + h[i:]
    tmp_c = gfx / "compositions" / f"_last-{gid}.html"
    tmp_r = gfx / "renders" / f"_last-{gid}.mov"
    tmp_c.write_text(h, encoding="utf-8")
    try:
        _run([shutil.which("npx") or "npx", HF, "render", ".", "-c", f"compositions/{tmp_c.name}", "--fps", rate_str(rate), "--quality", "standard",
              "--video-frame-format", "png", "--format", "mov", "--output", f"renders/{tmp_r.name}"], cwd=str(gfx),
             env={**os.environ, "npm_config_before": HF_BEFORE})
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp_r), "-frames:v", "1", "-pix_fmt", "rgba", str(png)])
    finally:
        for f in (tmp_c, tmp_r):
            if f.exists():
                f.unlink()
    return png


def solid_body(png, alpha=MARK_SOLID_ALPHA):
    """(x0, y0, x1, y1) of a brand mark's SOLID body (alpha > MARK_SOLID_ALPHA): size marks by this, never by the padded
    canvas or a baked shadow (one logo came out 7 % smaller than its pair)."""
    from PIL import Image
    with Image.open(png) as im:
        a = im.convert("RGBA").getchannel("A").point(lambda v: 255 if v > alpha else 0)
        return a.getbbox()


# ── init / drift ───────────────────────────────────────────────────────────────────────────────────────────────────
def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _copies():
    return [(f"{PRESET_REL}/kit/engine.py", "kit/engine.py"), (f"{PRESET_REL}/kit/components.py", "kit/components.py"),
            (f"{REFERENCE_REL}/fullscreen-render.sh", "render.sh"), (f"{REFERENCE_REL}/hf-anim.js", "hf-anim.js")]


def _font_sources():
    sf = {"Display-Black.otf": "/Library/Fonts/SF-Pro-Display-Black.otf",
          "Display-Bold.otf": "/Library/Fonts/SF-Pro-Display-Bold.otf",
          "Display-Regular.otf": "/Library/Fonts/SF-Pro-Display-Regular.otf"}
    inter = {k: str(REPO / "assets/fonts" / v) for k, v in
             {"Display-Black.otf": "Inter-Black.otf", "Display-Bold.otf": "Inter-Bold.otf",
              "Display-Regular.otf": "Inter-Regular.otf"}.items()}
    display = sf if all(os.path.exists(v) for v in sf.values()) else inter
    # off a Mac, the bundled IBM Plex Mono Bold: captions.py's own SF Mono stand-in, so labels and captions share one face
    # on every OS (Consolas and Debian's DejaVu were two other faces, and a non-Debian Linux found none at all)
    mono = next((m for m in ("/System/Library/Fonts/SFNSMono.ttf", str(REPO / "assets/fonts/IBMPlexMono-Bold.ttf"),
                             "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                             "C:/Windows/Fonts/consolab.ttf") if os.path.exists(m)), None)
    return display, mono


def _git_commit():
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True)
        d = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", PRESET_REL, REFERENCE_REL],
                           capture_output=True, text=True)
        return (r.stdout.strip() or None), bool(d.stdout.strip())
    except OSError:
        return None, None


PROJECT_MD = """# {job}: graphics build (talking-head explainer kit)

The resume doc: what is built, rendered and placed, and what is next. Update it as you go.

- Kit: `gfx/kit/` (staged by `engine.py init`; `KIT.json` names the preset commit). `engine.py drift` shows edits.
- Storyboard: `gfx/build.py` (DATA: every time is a word or a plan cell). Run it, then `kit/engine.py render <id>`.
- Families and finish: presets/instagram/talking-head-explainer/graphics.md § 7. Captures: captures.md.

| id | family | built | rendered | placed | notes |
|---|---|---|---|---|---|
"""


def init(job):
    """Stage the kit into projects/<job>/hf-graphics/gfx: the folders, the engine and components, the reference render.sh
    and hf-anim.js, a starter build.py (only when there is none), the fonts, the renderer's links, PROJECT.md and
    kit/KIT.json. A copy edited in the job since the last init is KEPT and named (merge by hand; `drift` shows it)."""
    if REPO is None:
        sys.exit("init: cannot find the repo (presets/ and workflows/) above this file")
    job = Path(job).resolve()
    if not job.is_dir():
        sys.exit(f"init: no job folder {job}")
    gfx = job / "hf-graphics" / "gfx"
    for d in ("compositions", "renders", "assets/fonts", "assets/captures", "kit"):
        (gfx / d).mkdir(parents=True, exist_ok=True)
    kj = gfx / "kit" / "KIT.json"
    old = json.loads(kj.read_text(encoding="utf-8")).get("files", {}) if kj.exists() else {}
    files = {}
    for src_rel, dst_rel in _copies():
        src, dst = REPO / src_rel, gfx / dst_rel
        if not src.exists():
            print(f"⚠ {src_rel} is missing from the preset: not staged")
            continue
        if dst.exists() and dst_rel in old and _sha(dst) != old[dst_rel]["sha256"] and _sha(dst) != _sha(src):
            print(f"⚠ kept {dst_rel}: edited in this job since init (merge the preset's version by hand; `drift` shows it)")
            files[dst_rel] = old[dst_rel]
            continue
        shutil.copy2(src, dst)
        files[dst_rel] = {"src": src_rel, "sha256": _sha(dst)}
        print(f"  staged {dst_rel:<20} <- {src_rel}")
    rsh = gfx / "render.sh"
    if rsh.exists():
        rsh.chmod(rsh.stat().st_mode | 0o111)
    ex, bp = REPO / PRESET_REL / "kit" / "build.example.py", gfx / "build.py"
    if not bp.exists() and ex.exists():
        shutil.copy2(ex, bp)
        print(f"  staged build.py            <- {PRESET_REL}/kit/build.example.py (the storyboard: edit only its list)")
    elif bp.exists():
        print("  kept   build.py (the job's storyboard)")
    display, mono = _font_sources()
    fonts = {}
    for name, src in display.items():
        if os.path.exists(src):
            shutil.copyfile(src, gfx / "assets/fonts" / name)     # content only: system font files carry flags copystat cannot set
            fonts[name] = src
    which = "SF Pro Display" if display[next(iter(display))].startswith("/Library/") else "Inter (bundled; no SF Pro Display in /Library/Fonts)"
    if mono:
        shutil.copyfile(mono, gfx / "assets/fonts" / MONO_FILE)
        fonts[MONO_FILE] = mono
    print(f"  fonts  display: {which} · mono: {mono or '⚠ none found (SFNSMono / IBM Plex Mono / DejaVu Sans Mono / Consolas): labels fall back'}")
    for name, target in (("assets", "../assets"), ("hf-anim.js", "../hf-anim.js")):
        link = gfx / "compositions" / name
        if os.name == "nt" and os.path.lexists(link) and not link.is_symlink():
            _repair_windows_link(link, (link.parent / target).resolve(), name)
        if not link.exists() and not link.is_symlink():
            try:
                link.symlink_to(target)
            except OSError as e:
                # Windows without Developer Mode refuses symlinks (WinError 1314), and init then left out
                # compositions/assets, so every build and render after it failed (the kit smoke, 2026-09-27). A
                # directory junction needs no privilege; a file is hard-linked (same volume) or copied.
                src = (link.parent / target).resolve()
                try:
                    if os.name == "nt" and src.is_dir():
                        import _winapi
                        _winapi.CreateJunction(str(src), str(link))
                    elif src.is_file():
                        try:
                            os.link(src, link)
                        except OSError:
                            shutil.copyfile(src, link)
                    else:
                        raise e
                except OSError as e2:
                    print(f"⚠ compositions/{name} -> {target}: {e2} (the browser probe will 404 assets)")
    pm = gfx.parent / "PROJECT.md"
    if not pm.exists():
        pm.write_text(PROJECT_MD.format(job=job.name), encoding="utf-8")
    commit, dirty = _git_commit()
    kj.write_text(json.dumps({"preset": PRESET_REL, "repo": str(REPO), "commit": commit, "dirty": dirty,
                              "staged": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "files": files, "fonts": fonts}, indent=1) + "\n", encoding="utf-8")
    print(f"✓ kit staged in {gfx} (preset {commit[:10] if commit else 'no git'}{' + local edits' if dirty else ''})")
    return gfx


def _is_junction(p):
    f = getattr(os.path, "isjunction", None)                  # Python 3.12+
    if f:
        return f(p)
    try:
        return bool(os.readlink(p)) and not os.path.islink(p)  # 3.8+ on Windows reads a junction's target
    except (OSError, ValueError, AttributeError):
        return False


def _repair_windows_link(link, src, name):
    """Windows only: compositions/assets and hf-anim.js are a junction and a hard link there (no symlink privilege), and
    neither survives the job being moved or copied (L32, the Windows re-test 2026-09-27): a junction keeps its ABSOLUTE
    target, so a moved job's points at the old folder or at nothing, and a copy (cp -r, Explorer, archive.sh's restore)
    turns it into a real folder and splits the hard link into a copy, so an asset added later never reaches
    compositions/ and the browser probe 404s it (L6, silently: a font falls back). A link that no longer reaches its own
    source is taken away here so init makes it again: a junction is removed (only the link), a copied folder is moved
    aside (never deleted: something may have been added into it), a copied file is removed (hf-anim.js is staged).
    A macOS or Linux symlink (relative, it survives both) is never touched."""
    try:
        ok = (os.path.realpath(link) == os.path.realpath(src)) if src.is_dir() else os.path.samefile(link, src)
    except OSError:
        ok = False
    if ok:
        return
    if _is_junction(link):
        try:
            old = os.readlink(link)
        except OSError:
            old = "an unreadable place"
        os.rmdir(link)                                        # removes the junction, never its target
        print(f"  relink compositions/{name}: its junction pointed at {old}, not {src}")
    elif link.is_dir():
        aside = link.with_name(f"{name}.stale-copy-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        link.rename(aside)
        print(f"  relink compositions/{name}: it was a copied folder (moved aside to {aside.name}; delete it once "
              f"nothing in it is needed)")
    else:
        link.unlink()
        print(f"  relink compositions/{name}: it was a copy, not a link to {src.name}")


def _same_or_refuse(sha, dst, job, what):
    """True when dst already holds these bytes, False when nothing is there; a DIFFERENT file is refused, never
    overwritten."""
    if not dst.exists():
        return False
    if _sha(dst) == sha:
        return True
    raise BuildError(f"stage: {dst.relative_to(job)} already holds a DIFFERENT file: a staged {what} is never "
                     "overwritten. Stage the new one under another id (or --name), or move the old one aside by hand "
                     "if it is truly replaced")


def _copy_in(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".staging-{dst.name}")
    shutil.copyfile(src, tmp)
    os.replace(tmp, dst)


def stage(job, gid, source, name=None, mark=False):
    """Stage one capture (or a brand mark) for the build, both halves: the ORIGINAL at projects/<job>/assets/captures/
    <id>.<ext> (what validate-plan.py checks: the cell's `asset`, never edited) and the render base the kit reads,
    hf-graphics/gfx/assets/captures/<name> (a video re-encoded all-intra, so every seek lands; a still copied). mark=True
    stages a brand mark into hf-graphics/gfx/assets/logos/<name> instead (marks are the product's own files, fetched for
    the job, never in the repo's assets/logos; a component takes them as "assets/logos/<name>").
    IDEMPOTENT: a re-run with the same file changes nothing and re-encodes nothing. A DIFFERENT file already at the
    original, the mark or the render base is refused (BuildError) before anything is written, never overwritten, and
    so is a second original for one cell (a still staged as g4, then a video as g4: <id>.<ext> would name two files).
    The base records the original it was made from beside it (<name>.stage.json: the id, the original and both
    sha256), which is how a re-run knows a video base is this original's, and a base edited since is refused.
    ATOMIC: a stage that fails part-way (a take ffmpeg cannot read) removes the original it wrote and raises
    BuildError, so the corrected take stages under the same id; the first version left the original behind and refused
    the retry as a different file."""
    job, src = Path(job).resolve(), Path(source).resolve()
    if not src.is_file():
        raise BuildError(f"stage: no file {src}")
    gfx = job / "hf-graphics" / "gfx"
    if not gfx.is_dir():
        raise BuildError(f"stage: no {gfx}: run `engine.py init {job}` first")
    sha = _sha(src)
    if mark:
        dst = gfx / "assets" / "logos" / (name or src.name)
        if _same_or_refuse(sha, dst, job, "mark"):
            print(f"  kept   mark {dst.relative_to(job)} (already staged, the same file)")
        else:
            _copy_in(src, dst)
            print(f"  staged mark {dst.relative_to(job)} <- {src}")
        print(f"  a component takes it as \"assets/logos/{dst.name}\"")
        return dst
    ext = src.suffix.lower()
    video = ext in VIDEO_EXT
    caps = job / "assets" / "captures"
    orig = caps / f"{gid}{ext}"
    base = gfx / "assets" / "captures" / (name or f"{gid}{'.mp4' if video else ext}")
    rec = base.with_name(base.name + ".stage.json")
    want = {"id": gid, "original": orig.relative_to(job).as_posix(), "sha256": sha}
    # every refusal comes before any write
    others = sorted(p.name for p in caps.iterdir() if p.is_file() and p.stem == gid and p.suffix.lower() != ext) \
        if caps.is_dir() else []
    if others:
        raise BuildError(f"stage: {gid} already has an original, assets/captures/{', '.join(others)}: one cell never has "
                         f"two originals (its plan cell's \"asset\" names one file). Stage this take under another id, or "
                         f"move the old original and its render base aside by hand if this one replaces it")
    if video and base.suffix.lower() not in BASE_VIDEO_EXT:
        raise BuildError(f"stage: a video's render base is H.264: name it {' / '.join(BASE_VIDEO_EXT)}, not {base.name!r}")
    orig_ok = _same_or_refuse(sha, orig, job, "original")
    base_ok = base.exists()
    if base_ok:
        have = json.loads(rec.read_text(encoding="utf-8")) if rec.exists() else None
        if have is not None:
            same = {k: have.get(k) for k in want} == want and have.get("base_sha256") == _sha(base)
        else:                                       # a still's base is a byte copy; a video base with no record is unproven
            same = not video and _sha(base) == sha
        if not same:
            why = (f"{rec.name} records {have.get('original')} for {have.get('id')}, or the base changed since" if have
                   else "nothing records which original it was made from")
            raise BuildError(f"stage: the render base {base.relative_to(job)} already exists and is not this original's "
                             f"({why}): never overwritten. Pick another --name, or move the old base aside by hand")
    wrote = []                                      # what this run wrote, removed again if it fails part-way
    try:
        if orig_ok:
            print(f"  kept   original {orig.relative_to(job)} (already staged, the same file)")
        else:
            _copy_in(src, orig)
            wrote.append(orig)
            print(f"  staged original {orig.relative_to(job)} <- {src}")
        if base_ok:
            print(f"  kept   render base {base.relative_to(job)} (made from this original)")
        else:
            tmp = base.with_name(f".staging-{base.name}")
            try:
                if video:
                    all_intra(orig, tmp)
                else:
                    base.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(orig, tmp)
                rec.write_text(json.dumps(dict(want, base_sha256=_sha(tmp)), indent=1) + "\n", encoding="utf-8")
                wrote.append(rec)                   # the record first: a base never lands without one
                os.replace(tmp, base)
                wrote.append(base)
            finally:
                if tmp.exists():
                    tmp.unlink()
            print(f"  staged render base {base.relative_to(job)} ({'all-intra' if video else 'a copy'} of {orig.relative_to(job)})")
    except BaseException as e:
        for p in reversed(wrote):
            p.unlink(missing_ok=True)
        if isinstance(e, BuildError) or not isinstance(e, Exception):
            raise
        undone = ", ".join(p.relative_to(job).as_posix() for p in wrote) or "nothing had been written"
        raise BuildError(f"stage: {gid} from {src.name} failed, nothing is staged (removed: {undone}), so the corrected "
                         f"take stages under the same id: {e}") from e
    print(f"  capture {gid}: the plan cell's \"asset\": \"{want['original']}\" · the kit reads \"{base.name}\"")
    return base


def drift(job):
    """Every staged copy against the preset: EDITED in the job, the preset MOVED ON since init, or in step. Exit 1 on any
    difference."""
    gfx = Path(job).resolve() / "hf-graphics" / "gfx"
    kj = gfx / "kit" / "KIT.json"
    if not kj.exists():
        print(f"no {kj}: run init first")
        return 1
    rec = json.loads(kj.read_text(encoding="utf-8"))
    bad = 0
    for dst_rel, f in sorted(rec.get("files", {}).items()):
        here, src = gfx / dst_rel, (REPO / f["src"]) if REPO else None
        mine = _sha(here) if here.exists() else None
        theirs = _sha(src) if src and src.exists() else None
        notes = []
        if mine is None:
            notes.append("MISSING in the job")
        elif mine != f["sha256"]:
            notes.append("EDITED in the job since init")
        if theirs is None:
            notes.append("gone from the preset")
        elif theirs != f["sha256"]:
            notes.append("the preset MOVED ON since init (re-run init to refresh an unedited copy)")
        bad += bool(notes)
        print(f"{'✗' if notes else '✓'} {dst_rel:<20} {'; '.join(notes) or 'in step with ' + f['src']}")
    print(f"{bad} of {len(rec.get('files', {}))} staged file(s) differ (kit staged {rec.get('staged')}, commit {str(rec.get('commit'))[:10]})")
    return 1 if bad else 0


# ── render: the family-flag wrapper ────────────────────────────────────────────────────────────────────────────────
def _gfx_dir(job=None):
    if job:
        return Path(job).resolve() / "hf-graphics" / "gfx"
    if HERE.name == "kit" and (HERE.parent / "compositions").is_dir():
        return HERE.parent
    cwd = Path.cwd()
    if (cwd / "compositions").is_dir() and (cwd / "render.sh").exists():
        return cwd
    sys.exit("render: run the job's own copy (projects/<job>/hf-graphics/gfx/kit/engine.py), or pass --job projects/<job>")


def _placed(hf):
    out = set()
    for p in hf.glob("placement*.json"):
        try:
            out |= {os.path.basename(r.get("file") or "") for r in json.loads(p.read_text(encoding="utf-8"))}
        except (ValueError, AttributeError):
            pass
    return out


def pick_ver(gfx, gid, ver=None):
    """The VER a render writes. None -> bare on the first render, else the letter after the newest (a re-render never
    overwrites, so the placer's newest-version pick lands on it); a named VER that is PLACED moves to the next free."""
    ren, placed = Path(gfx) / "renders", _placed(Path(gfx).parent)
    have = []
    for f in ren.glob(f"{gid}-alpha*.mov"):
        m = re.fullmatch(rf"{re.escape(gid)}-alpha(?:-([a-z]))?\.mov", f.name)
        if m:
            have.append(m.group(1) or "")
    nxt = lambda: chr(ord(max(have)) + 1) if max(have, default="") else "a"
    if ver is None:
        if not have:
            return None
        v = nxt()
    else:
        name = f"{gid}-alpha{'-' + ver if ver else ''}.mov"
        if name not in placed:
            return ver
        v = nxt()
        print(f"  {name} is PLACED (placement*.json): rendering VER={v} instead (never overwrite a placed file)")
    if v > "z":
        raise BuildError(f"{gid}: the letter versions ran out (…-z): retire old renders first")
    return v


def post_pass(path, flags, fps):
    """The family finish on a rendered alpha mov, in place: bloom (screen on R,G,B, alpha kept), scan (6 px sine), grain
    (after the 12 fps expansion, luma, fresh each timeline frame, alpha untouched). Frame count is proven unchanged."""
    vf = "format=gbrapf32le"   # float: ffmpeg 8's blend screen at a fractional opacity is broken on 16-bit planes
    if flags.get("GLOW"):
        g = flags["GLOW"]
        vf += (f",split[a][b];[b]gblur=sigma={BLOOM['sigma']:g},eq=brightness={BLOOM['brightness']:g}:contrast={BLOOM['contrast']:g},"
               f"curves=all='{BLOOM['curves']}'[bl];[a][bl]blend=c0_mode=screen:c1_mode=screen:c2_mode=screen:c3_mode=normal:"
               f"c0_opacity={g}:c1_opacity={g}:c2_opacity={g}:c3_opacity=1")
    if flags.get("SCAN"):
        sl = f"(1-{flags.get('SCAN_AMP', SCAN_AMP)}*(0.5+0.5*cos(2*PI*Y/{SCAN_PERIOD:g})))"
        vf += f",geq=r='r(X,Y)*{sl}':g='g(X,Y)*{sl}':b='b(X,Y)*{sl}':a='alpha(X,Y)'"
    if flags.get("GRAIN"):
        vf += f",format=yuva444p16le,noise=c0s={flags['GRAIN']}:c0f=t"
    vf += ",format=yuva444p12le"
    path = Path(path)
    tmp = path.with_name(path.stem + ".post.mov")
    n0 = frame_count(path)
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vf", vf, "-c:v", "prores_ks", "-profile:v", "4444", "-r", fps, str(tmp)])
    n1 = frame_count(tmp)
    if n1 != n0:
        tmp.unlink()
        raise RuntimeError(f"post pass changed {path.name} from {n0} to {n1} frames")
    os.replace(tmp, path)
    return vf


def sh_argv():
    """How to run a shell script: nothing on macOS/Linux (the shebang runs it), Git Bash on Windows, where
    CreateProcess cannot execute a .sh (WinError 2 on every kit render, 2026-09-27). System32's bash.exe is WSL's,
    never the one the pipeline was set up in, so it is skipped for Git's own."""
    if os.name != "nt":
        return []
    cands = [shutil.which("bash")] + [os.path.join(os.environ.get(v, ""), "Git", "bin", "bash.exe")
                                      for v in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")]
    for c in cands:
        if c and os.path.exists(c) and "system32" not in c.lower():
            return [c]
    raise RuntimeError("no Git Bash found to run render.sh (install Git for Windows)")


def render(gid, ver=None, job=None):
    """./render.sh <id> alpha with the plan's FPS and the comp's family flags (never typed by hand), then the finish.
    Prints the exact commands. Returns the render's path."""
    gfx = _gfx_dir(job)
    fj = gfx / "compositions" / f"{gid}.family.json"
    if not fj.exists():
        sys.exit(f"render: no {fj.relative_to(gfx.parent.parent)}: write the comp through the kit (engine.write) first")
    fam = json.loads(fj.read_text(encoding="utf-8"))["family"]
    flags = FAMILY_FLAGS[fam]
    pp = gfx.parent.parent / "graphics-plan.json"
    fps = json.loads(pp.read_text(encoding="utf-8")).get("fps") if pp.exists() else None
    v = pick_ver(gfx, gid, ver)
    job_post = bool(re.search(r"\$\{GLOW", (gfx / "render.sh").read_text(encoding="utf-8")))
    env = {}
    if fps:
        env["FPS"] = str(fps)
    if flags.get("STEP_FPS"):
        env["STEP_FPS"] = flags["STEP_FPS"]
    if job_post:
        env.update({k: flags[k] for k in POST_KEYS if k in flags})
    if v:
        env["VER"] = v
    line = " ".join(f"{k}={val}" for k, val in env.items()) + f" bash ./render.sh {gid} alpha"
    print(f"[{fam}] (cd {gfx} && {line})")
    run_env = {k: val for k, val in os.environ.items() if k not in POST_KEYS + ("STEP_FPS", "VER", "MBLUR")}
    subprocess.run([*sh_argv(), "./render.sh", gid, "alpha"], cwd=gfx, env={**run_env, **env}, check=True)
    out = gfx / "renders" / f"{gid}-alpha{'-' + v if v else ''}.mov"
    recp = out.with_name(out.name + ".render.json")
    rec = json.loads(recp.read_text(encoding="utf-8")) if recp.exists() else {}
    post = {k: flags[k] for k in POST_KEYS if k in flags}
    if post and not job_post:
        rate = rec.get("FPS") or str(fps or "30000/1001")
        vf = post_pass(out, post, rate)
        print(f"  post: {' '.join(f'{k}={val}' for k, val in post.items())} (kit/engine.py: this job's render.sh predates the post-pass flags)")
        rec["post"] = {"flags": post, "vf": vf}
    rec.update({"family": fam, "kit_flags": flags,
                "re-render": f"uv run kit/engine.py render {gid}" + (f" --ver {v}" if v else "") + "   # from this folder (gfx/)"})
    recp.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(f"-> {out} ({frame_count(out)} frames)")
    return out


# ── smoke: the kit end to end on a synthetic job ───────────────────────────────────────────────────────────────────
# An invented reel (the fixture kit/build.example.py is written against): every phrase its storyboard anchors on is said
# exactly once. (text, the other voice?, the pause after it in s)
SMOKE_SCRIPT = [
    ("I gave my assistant its own phone number and now it runs my whole day.", False, 0.35),      # g1 the hook (S)
    ("You will not believe how easy this was.", False, 0.35),                                     # T, the promise
    ("I paired it with a voice platform built for real phone calls,", False, 0.2),               # g2 the partner's page
    ("and every morning I just text it what I need, and it keeps", False, 0.0),                   # g3 the chat, typing
    ("checking my inbox, my calendar, my analytics and my tasks,", False, 0.2),                   # g4 the montage
    ("so every morning it sends me a plan.", False, 0.35),                                        # g5 the reply lands
    ("It even built my booking page and the checkout behind it,", False, 0.2),                    # g9 two pages, two fills
    ("and it wrote a guide for the whole team.", False, 0.35),                                    # g10 the doc, scrolled
    ("Oh wait,", False, 0.1),                                                                     # W, a breather
    ("that's it calling me right now.", False, 0.4),                                              # g6 the call card (O)
    ("Morning, your day is ready.", True, 0.4),                                                   #    the other voice
    ("Perfect, thanks.", False, 0.35),
    ("Setting this up used to be technical, complicated and honestly overwhelming for most normal people.", False, 0.35),  # g7
    ("so comment agent below and I'll send you the setup.", False, 0.4),                         # g8 the ask, pushed in
]
TAKE = {"typing": 1.0, "keys": 8, "send": 6.0, "land": 9.2, "len": 11.5}   # the chat take's own moments (media s)
SMOKE_RENDER_TOO = ("g9", "g10")     # past one comp per family: a cut between two fills, a doc run under the caption


def _smoke_fixture(job):
    """The synthetic job's words and media: the canonical transcript of SMOKE_SCRIPT, a raw take whose audio carries the
    second voice as a tone exactly where voices.json says (captions.py's contract), the one-segment EDL, and the plan:
    the example storyboard's ten cells on a layout that tiles the reel, each switch 1 frame before its word."""
    for d in ("raw", "outputs", "transcript"):
        (job / d).mkdir(parents=True, exist_ok=True)
    words, first, t = [], [], 0.12
    for text, other, pause in SMOKE_SCRIPT:
        first.append(len(words))
        for w in text.split():
            d = round(0.12 + 0.045 * len(re.sub(r"[^\w']", "", w)), 3)
            words.append({"text": w, "start": round(t, 3), "end": round(t + d, 3), "type": "word", "_other": other})
            t += d + 0.06
        t += pause
    end = round(words[-1]["end"] + 0.4, 3)
    vw = [w for w in words if w["_other"]]
    v0, v1 = round(vw[0]["start"] - 0.05, 3), round(vw[-1]["end"] + 0.05, 3)
    for w in words:
        w.pop("_other")
    text = " ".join(x for x, _, _ in SMOKE_SCRIPT)
    (job / "outputs" / f"{job.name}.transcript.json").write_text(json.dumps(
        {"text": text, "language_code": "en", "engine": "synthetic (kit smoke)", "words": words}, indent=1), encoding="utf-8")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=0x303840:s=216x384:r={rate_str()}:d={end}",
          "-f", "lavfi", "-i", f"aevalsrc=0.6*sin(2*PI*220*t)*(0.55+0.45*sin(2*PI*3*t))*between(t\\,{v0}\\,{v1}):s=48000:d={end}",
          "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(job / "raw" / "raw.mp4")])
    (job / "transcript" / "cuts.json").write_text(json.dumps(
        {"segments": [{"clip": "raw.mp4", "start": 0.0, "end": end, "transcript": text}]}, indent=1), encoding="utf-8")
    (job / "transcript" / "voices.json").write_text(json.dumps(
        {"spans": [{"clip": "raw.mp4", "start": v0, "end": v1, "voice": "phone"}]}, indent=1), encoding="utf-8")
    on = lambda i: fsec(frames(words[i]["start"]) - 1)             # a switch lands 1 frame before its word
    at = lambda phrase, k=0: next(i for i in range(first[k], len(words)) if _norm(words[i]["text"]) == _norm(phrase))
    s = {n: on(first[i]) for n, i in (("T", 1), ("g2", 2), ("g3", 3), ("g4", 4), ("g5", 5), ("g9", 6), ("g10", 7),
                                       ("W", 8), ("g6", 9), ("g7", 12), ("g8", 13))}
    fin = fsec(frames(end))
    cuts = [on(at("my", 4) + k) for k in (2, 4, 7)]                  # "my calendar", "my analytics", "my tasks"
    assert [words[at("my", 4) + k + 1]["text"].strip(",") for k in (2, 4, 7)] == ["calendar", "analytics", "tasks"]
    cell = lambda gid, a, b, fam, kind, **kw: {"id": gid, "start": a, "end": b, "graphic": True, "family": fam, "kind": kind,
                                               "readable": fam == "capture", **kw}
    beats = [cell("g1", 0.0, s["T"], "authored", "ui-enactment", role="hook"),
             cell("g2", s["g2"], s["g3"], "capture", "screen-rec"),
             cell("g3", s["g3"], s["g4"], "capture", "screen-rec"),
             cell("g4", s["g4"], s["g5"], "montage", "screen-rec", shot_cuts=cuts),
             cell("g5", s["g5"], s["g9"], "capture", "screen-rec"),
             cell("g9", s["g9"], s["g10"], "capture", "screen-rec", shot_cuts=[on(at("checkout", 6))]),
             cell("g10", s["g10"], s["W"], "capture", "screen-rec", under_caption=True),
             cell("g6", s["g6"], s["g7"], "overlay", "call-ui", crown=625),
             cell("g7", s["g7"], s["g8"], "authored", "ui-enactment"),
             cell("g8", s["g8"], fin, "authored", "ui-enactment", role="cta")]
    layout = [{"start": 0.0, "end": s["T"], "mode": "S"}, {"start": s["T"], "end": s["g2"], "mode": "T"},
              {"start": s["g2"], "end": s["W"], "mode": "S"}, {"start": s["W"], "end": s["g6"], "mode": "W"},
              {"start": s["g6"], "end": s["g7"], "mode": "O"}, {"start": s["g7"], "end": fin, "mode": "S"}]
    plan = {"job": job.name, "format": "short-talking-head-explainer", "preset": PRESET_REL, "compositor": "premiere",
            "fps": rate_str(), "duration": fin, "beats": beats, "layout": layout}
    (job / "graphics-plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return words, plan


def _stills_to_take(states, out, size):
    """[(PIL image, seconds)] -> an all-intra take at the grid rate: a synthetic screen whose moments are real changes."""
    tmp = out.parent / f".{out.stem}-states"
    tmp.mkdir(parents=True, exist_ok=True)
    lst = []
    for i, (im, dur) in enumerate(states):
        im.save(tmp / f"{i:03d}.png")
        lst += [f"file '{(tmp / f'{i:03d}.png').as_posix()}'", f"duration {dur:.6f}"]
    lst.append(f"file '{(tmp / f'{len(states) - 1:03d}.png').as_posix()}'")
    (tmp / "list.txt").write_text("\n".join(lst) + "\n", encoding="utf-8")
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-vf",
          f"fps={rate_str()},scale={size[0]}:{size[1]},format=yuv420p", "-c:v", "libx264", "-g", "1", "-keyint_min", "1",
          "-crf", "14", "-preset", "fast", "-an", str(out)])
    shutil.rmtree(tmp)


def _smoke_assets(gfx):
    """The fixture's media: marks under assets/logos, captures under assets/captures. Kit fixtures: a testsrc2 take on a
    dark fill, a white page, a header strip, a padded icon with a baked shadow. Example fixtures: a chat take (typing, a
    send, a reply landing), a chat header, three dashboard stills and a dashboard take (a task ticks off), a site take
    (its headline word swaps), a dark checkout still, a tall doc column, the product's icon and a partner's icon +
    wordmark."""
    from PIL import Image, ImageDraw, ImageFilter
    cap, logos = gfx / "assets" / "captures", gfx / "assets" / "logos"
    logos.mkdir(parents=True, exist_ok=True)
    tmp = gfx / "assets" / "take-src.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=size=600x760:rate={rate_str()}:duration=3",
          "-vf", "pad=800:1000:100:120:color=0x0a0a0a", "-pix_fmt", "yuv420p", str(tmp)])
    all_intra(tmp, cap / "take.mp4")
    tmp.unlink()
    page = Image.new("RGB", (900, 700), (254, 254, 254))
    d = ImageDraw.Draw(page)
    d.rounded_rectangle((90, 90, 810, 190), 24, fill=(20, 20, 24))
    for y in (250, 300, 350):
        d.rectangle((90, y, 810 - (y - 250) * 2, y + 26), fill=(120, 120, 128))
    d.rounded_rectangle((90, 470, 420, 580), 55, fill=(30, 72, 255))
    page.save(cap / "page.png")
    for name, size, colour in (("header.png", (1360, 140), (245, 161, 28)), ("chat-header.png", (1360, 140), (47, 107, 255))):
        hdr = Image.new("RGB", size, (10, 10, 10))
        d = ImageDraw.Draw(hdr)
        d.ellipse((40, 26, 128, 114), fill=colour)
        d.rectangle((160, 52, 520, 88), fill=(230, 230, 236))
        hdr.save(cap / name)

    def icon(path, rgb, full=False):
        im = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        if full:
            ImageDraw.Draw(im).rectangle((0, 0, 511, 511), fill=rgb + (255,))
        else:
            sh = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle((56, 76, 468, 488), 92, fill=(0, 0, 0, 150))
            im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(14)))
            ImageDraw.Draw(im).rounded_rectangle((50, 50, 462, 462), 92, fill=rgb + (255,))
        ImageDraw.Draw(im).ellipse((196, 196, 316, 316), fill=(255, 255, 255, 255))
        im.save(path)

    icon(logos / "icon.png", (30, 72, 255))
    icon(logos / "acme-assistant.png", (30, 72, 255))
    icon(logos / "acme-voice.png", (229, 72, 77), full=True)
    (logos / "acme-voice-wordmark.svg").write_text(
        '<svg viewBox="0 0 330 64" xmlns="http://www.w3.org/2000/svg">' + "".join(
            f'<rect x="{x}" y="8" width="{w}" height="48" rx="6" fill="#151515"/>' for x, w in ((0, 58), (70, 44), (126, 70), (208, 52), (272, 58)))
        + "</svg>", encoding="utf-8")
    # the chat take: 1640x2080, a rail, older history, the input bar; typing, a send, a reply landing (TAKE)
    W, H, bg = 1640, 2080, (14, 14, 14)

    def chat(keys=0, sent=False, landed=False):
        im = Image.new("RGB", (W, H), bg)
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 279, H), fill=(22, 22, 22))
        for i, y in enumerate((260, 560, 860)):                       # older history the reply shots mask out
            x0 = 330 if i % 2 == 0 else 900
            d.rounded_rectangle((x0, y, x0 + 700, y + 220), 40, fill=(42, 43, 49))
        d.rounded_rectangle((300, 1830, 1620, 2040), 60, fill=(16, 16, 16))
        for k in range(keys):                  # the prompt typed: a glyph per keystroke, big enough for change-events to see
            d.rectangle((340 + k * 160, 1843, 340 + k * 160 + 150, 2027), fill=(255, 255, 255))
        if sent:
            d.rectangle((300, 1830, 1620, 2040), fill=bg)
            d.rounded_rectangle((300, 1830, 1620, 2040), 60, fill=(16, 16, 16))
            d.rounded_rectangle((700, 1180, 1600, 1420), 50, fill=(30, 72, 255))
            for y in (1230, 1300):
                d.rectangle((760, y, 1500, y + 40), fill=(255, 255, 255))
        if landed:
            d.rounded_rectangle((330, 1450, 1300, 1780), 50, fill=(42, 43, 49))
            for y in (1500, 1580, 1660):
                d.rectangle((380, y, 1200, y + 40), fill=(235, 235, 240))
        return im

    per = 2 / float(FPS)
    states = [(chat(), TAKE["typing"])] + [(chat(k), per) for k in range(1, TAKE["keys"] + 1)]
    states += [(chat(TAKE["keys"]), TAKE["send"] - TAKE["typing"] - TAKE["keys"] * per),
               (chat(TAKE["keys"], sent=True), TAKE["land"] - TAKE["send"]),
               (chat(TAKE["keys"], sent=True, landed=True), TAKE["len"] - TAKE["land"])]
    _stills_to_take(states, cap / "chat.mp4", (W, H))

    def dash(seed, tick=None):
        im = Image.new("RGB", (1440, 900), (27, 29, 34))
        d = ImageDraw.Draw(im)
        for i in range(4):
            d.rounded_rectangle((60 + i * 340, 150, 360 + i * 340, 300), 24, fill=(40, 43, 51))
            d.rectangle((90 + i * 340, 190, 200 + i * 340 + (seed * 37 + i * 53) % 90, 230), fill=(210, 214, 222))
        for j in range(5):
            y = 360 + j * 90
            d.rounded_rectangle((60, y, 1380, y + 70), 18, fill=(35, 38, 45))
            d.rectangle((100, y + 22, 400 + (seed * 91 + j * 131) % 600, y + 48), fill=(150, 156, 170))
        if tick is not None:
            d.rounded_rectangle((60, 360, 1380, 430), 18, fill=(28, 150, 88))
            d.rectangle((100, 382, 900, 408), fill=(235, 255, 240))
        return im

    for i, name in enumerate(("dash-inbox.png", "dash-calendar.png", "dash-analytics.png")):
        dash(i).save(cap / name)
    _stills_to_take([(dash(3), 1.2), (dash(3, tick=True), 1.8)], cap / "dash-tasks.mp4", (1440, 900))

    def site(word, rgb):
        im = Image.new("RGB", (1280, 1140), (254, 254, 254))
        d = ImageDraw.Draw(im)
        d.rectangle((40, 48, 240, 94), fill=(21, 21, 21))                 # the site's own nav (cropped off)
        d.rectangle((120, 170, 700, 280), fill=(21, 21, 21))
        d.rectangle((720, 170, 720 + word, 280), fill=rgb)                 # the headline's rotating word
        d.rectangle((260, 312, 1020, 345), fill=(120, 120, 128))
        d.rounded_rectangle((470, 398, 810, 489), 45, fill=(21, 21, 21))
        return im

    _stills_to_take([(site(440, (229, 72, 77)), 1.5), (site(360, (21, 21, 21)), 4.5)], cap / "site.mp4", (1280, 1140))
    # a dark checkout page (its own fill, unlike the white site cut before it) and a tall doc column for the scroll
    co = Image.new("RGB", (1200, 1000), (22, 23, 28))
    d = ImageDraw.Draw(co)
    d.rounded_rectangle((260, 120, 940, 880), 36, fill=(40, 42, 50))
    for k, y in enumerate((190, 330, 470, 610)):
        d.rectangle((320, y, 700 - k * 60, y + 30), fill=(150, 156, 170))
        d.rounded_rectangle((320, y + 50, 880, y + 110), 14, fill=(28, 30, 36))
    d.rounded_rectangle((320, 770, 880, 840), 35, fill=(30, 72, 255))
    co.save(cap / "checkout.png")
    doc = Image.new("RGB", (900, 2800), (255, 255, 255))
    d = ImageDraw.Draw(doc)
    for k, y in enumerate(range(80, 2700, 66)):
        heading = k % 9 == 0
        d.rectangle((70, y, (560 if heading else 830 - (k * 97) % 260), y + (40 if heading else 22)),
                    fill=(20, 20, 24) if heading else (120, 120, 128))
    doc.save(cap / "guide.png")


def _smoke_scenes(ctx):
    """The kit's own fixtures, one comp per family (k1-k5), built only through the engine's emitters: they prove the
    engine whatever the example storyboard does."""
    out, t, n = [], 0.0, 29
    ic = solid_body(ctx.gfx / "assets" / "logos" / "icon.png")
    box = 220
    canvas = round(box * 512 / (ic[2] - ic[0]))                    # sized by the SOLID body, never the padded canvas
    html = ('<div class="surface el" id="card" style="position:absolute;left:170px;top:330px;width:740px;height:360px;'
            'display:flex;align-items:center;gap:48px;padding:0 56px;">'
            f'<div style="position:relative;width:{box}px;height:{box}px;flex:none;"><img id="ic" class="bare" src="assets/logos/icon.png" '
            f'style="position:absolute;left:{-(canvas - box) / 2:.1f}px;top:{-(canvas - box) / 2:.1f}px;width:{canvas}px;height:{canvas}px;"/></div>'
            '<div><div style="font-weight:900;font-size:96px;letter-spacing:-3px;line-height:1;color:#fff;">KIT</div>'
            '<div class="label" style="margin-top:14px;">smoke check</div></div></div>')
    bump = beat(ctx.find("gave"), 0.0)       # a word anchor, printed at 4 dp on purpose: comp() snaps it to its frame
    js = ("tl.set('#card',{opacity:1},0); tl.fromTo('#card',{y:60,scale:0.92},{y:0,scale:1,duration:8*FR,ease:'power3.out',immediateRender:false},0);\n"
          f"tl.fromTo('#ic',{{scale:1}},{{scale:1.08,duration:3*FR,ease:'power2.out',yoyo:true,repeat:1,immediateRender:false}},{bump:.4f});")
    out.append(authored(html, js, "", "split", id="k1", start=t, dur=fsec(n), visible0=["#card"], bbox=(170, 330, 910, 690),
                        events=[ev("riseIn", 0, "the card rises in"), ev("bump", bump, "the icon bumps on its word")]))
    t = out[-1].end
    out.append(capture({"id": "k2", "start": t, "layout": "split", "bg": "#050505", "header": {"img": "header.png"},
                        "shots": [{"media": "take.mp4", "t0": 0.5, "dur": fsec(14), "rect": [100, 120, 700, 880], "margin": 0.92},
                                  {"media": "take.mp4", "t0": 1.6, "dur": fsec(15), "rect": [100, 120, 700, 880], "margin": 0.92,
                                   "push": 1.01, "crop": [100, 120, 700, 880], "hide_above": [300, 200],
                                   "events": [{"event": "reply", "at": 0.1, "note": "the reply lands"}]}]}))
    t = out[-1].end
    out.append(capture({"id": "k3", "start": t, "layout": "split", "bg": "#fefefe", "follows": "face",
                        "shots": [{"media": "page.png", "dur": fsec(n), "rect": [60, 60, 840, 640]}]}))
    t = out[-1].end
    out.append(capture({"id": "k4", "start": t, "layout": "split", "bg": "#050505", "look": "montage", "readable": False,
                        "follows": "graphic",
                        # each plane is cropped to its own section, so it ends above the caption band (captures.md § 7)
                        "shots": [{"media": "take.mp4", "t0": 0.2, "dur": fsec(15), "rect": [100, 300, 700, 500], "crop": [100, 300, 700, 500]},
                                  {"media": "take.mp4", "t0": 1.0, "dur": fsec(17), "rect": [300, 500, 700, 700], "crop": [300, 500, 700, 700]},
                                  {"media": "page.png", "dur": fsec(18), "rect": [60, 60, 840, 400], "crop": [0, 40, 900, 420]}]}))
    t = out[-1].end
    lv = [round(0.25 + 0.7 * abs(math.sin(k / 3.1)), 3) for k in range(n)]    # the real envelope is components.audio_envelope's
    bars = 16
    html = ('<div class="surface el" id="cc" style="position:absolute;left:70px;top:388px;width:940px;height:212px;border-radius:64px;'
            'display:flex;align-items:center;padding:0 40px;gap:26px;"><div style="width:132px;height:132px;border-radius:50%;'
            'background:var(--avatar);flex:none;"></div><div style="flex:1;font-weight:700;font-size:58px;letter-spacing:-1px;color:#fff;">Agent</div>'
            '<div id="wv" style="display:flex;align-items:center;gap:7px;height:120px;">' + "<i style=\"display:block;width:9px;height:120px;"
            "border-radius:5px;background:var(--sky);transform:scaleY(0.07);\"></i>" * bars + "</div></div>")
    js = ["tl.set('#cc',{opacity:1},0); tl.fromTo('#cc',{y:-184,scale:0.92},{y:0,scale:1,duration:11*FR,ease:'power3.out',immediateRender:false},0);"]
    for k in range(n):                          # one line per frame: bar j shows the level j frames ago (scrolling right to left)
        js.append(" ".join(f"tl.set('#wv i:nth-child({j + 1})',{{scaleY:{max(0.07, lv[k - (bars - 1 - j)] if k >= bars - 1 - j else 0.0):.3f}}},{t6(k)});"
                           for j in range(bars)))
    out.append(overlay(html, "\n".join(js), "", id="k5", start=t, dur=fsec(n), visible0=["#cc"], bbox=(70, 388, 1010, 600),
                       events=[ev("riseIn", 0, "the card drops in")]))
    return out


def smoke(tmpdir):
    """The kit end to end on a synthetic job: the fixture reel, init, the kit's own fixtures (one comp per family) and the
    example storyboard built against it, one render per family from each (plus SMOKE_RENDER_TOO: a page cut between two
    fills, a doc run under the caption), placement rows, the 9:16 gate green, then a planted caption-band defect the
    gate must catch. Prints PASS/FAIL per step; exit 1 on any FAIL."""
    tmp = Path(tmpdir).resolve()
    job = tmp / "kit-smoke"
    if job.exists():
        shutil.rmtree(job)
    job.mkdir(parents=True)
    gfx, hf = job / "hf-graphics" / "gfx", job / "hf-graphics"
    results, state = [], {"rendered": []}

    def step(name, fn):
        try:
            detail = str(fn() or "")
            results.append((name, "SKIP" if detail.startswith("SKIP") else "PASS", detail))
        except Exception as e:  # a smoke reports every step, then fails
            results.append((name, "FAIL", f"{type(e).__name__}: {e}"))
        mark = results[-1]
        print(f"{'✓' if mark[1] == 'PASS' else ('·' if mark[1] == 'SKIP' else '✗')} {mark[1]:<4} {name}  {str(mark[2])[:900]}", flush=True)
        return mark[1] == "PASS"

    use_fps("24000/1001")

    def fixture():
        words, plan = _smoke_fixture(job)
        state["plan"] = plan
        return f"{len(words)} words, {len(plan['beats'])} plan cells on a {len(plan['layout'])}-row layout, a raw take with the call voice"

    step("fixture: the invented reel (transcript, plan, layout, EDL, voices)", fixture)

    def do_init():
        init(job)
        need = ["render.sh", "hf-anim.js", "kit/engine.py", "kit/KIT.json", "assets/fonts/Display-Bold.otf", "compositions/assets"]
        miss = [p for p in need if not (gfx / p).exists()]
        if miss:
            raise RuntimeError(f"init left out {miss}")
        _smoke_assets(gfx)
        return "staged, plus the fixture's marks and takes"

    step("init", do_init)

    def clean_drift():
        if drift(job):
            raise RuntimeError("drift reports a difference right after init")
        return "in step"

    step("drift: clean right after init", clean_drift)

    def build():
        ctx = Ctx(job)
        scenes = _smoke_scenes(ctx)
        state["kit"] = scenes
        plan = state["plan"]                    # QA's cells for the kit fixtures: not graphics of the reel's storyboard
        plan["beats"] += [{"id": x.id, "start": round(x.start, 6), "end": round(x.end, 6), "kit_smoke": True,
                           "kind": "ui-enactment", "family": x.family.replace("capture-white", "capture")} for x in scenes]
        (job / "graphics-plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
        for x in scenes:
            write(x, ctx.gfx)
            write_events(ctx.hf, x.id, x.events)
        blob = "".join((ctx.gfx / "compositions" / f"{x.id}.html").read_text(encoding="utf-8") for x in scenes)
        if re.search(r"backdrop-filter|text-shadow|onUpdate", blob):
            raise RuntimeError("an emitted comp carries backdrop-filter, text-shadow or onUpdate")
        return ", ".join(f"{x.id}={x.family}" for x in scenes)

    step("build: the kit's fixtures, one comp per family (asserts on)", build)

    def asserts():
        caught = []
        probes = [
            ("off-grid position", lambda: comp(authored("<i></i>", "tl.set('#a',{opacity:1},0.3);", id="x", dur=1))),
            ("overlapping tweens", lambda: comp(authored("<i></i>", f"tl.to('#a',{{scale:1.2,duration:0.5}},0); tl.to('#a',{{scale:1,duration:0.2}},{t6(6)});",
                                                         id="x", dur=1))),
            ("backdrop-filter", lambda: comp(authored("<i style='backdrop-filter:blur(4px)'></i>", "", id="x", dur=1))),
            ("visible0 unset", lambda: comp(authored("<i></i>", "", id="x", dur=1, visible0=["#a"]))),
            ("bbox past the zone", lambda: comp(authored("<i id='a'></i>", "tl.set('#a',{opacity:1},0);", id="x", dur=1,
                                                         visible0=["#a"], bbox=(0, 300, 1080, 900)))),
            ("flat push > 1.02", lambda: capture({"id": "x", "bg": "#050505", "shots": [{"media": "page.png", "dur": 1, "rect": [0, 0, 900, 700], "push": 1.05}]})),
            ("readable montage", lambda: capture({"id": "x", "bg": "#050505", "look": "montage", "readable": True, "shots": [{"media": "page.png", "dur": 1, "rect": [0, 0, 9, 9]}]})),
        ]
        for name, fn in probes:
            try:
                fn()
            except BuildError:
                caught.append(name)
        missed = [x for x, _ in probes if x not in caught]
        if missed:
            raise RuntimeError(f"not refused: {missed}")
        html = comp(authored("<i></i>", "tl.set('#a',{opacity:1},0); tl.set('#b',{opacity:1},0.0417);", id="x", dur=1,
                             visible0=["#a"], bbox=(0, 300, 1080, 700)))
        if "0.041708" not in html:
            raise RuntimeError("a 4-dp position was not snapped to its frame's floored time")
        return f"{len(caught)} planted defects refused at build time; a rounded position snapped"

    step("asserts: planted build-time defects are refused", asserts)

    def example():
        bp = gfx / "build.py"
        if not bp.exists():
            return "SKIP: no kit/build.example.py in the preset yet"
        r = subprocess.run(["uv", "run", "-q", str(bp)], cwd=REPO, capture_output=True, encoding="utf-8", errors="replace")
        if r.returncode:
            raise RuntimeError(f"build.py exited {r.returncode}: {(r.stderr or r.stdout).strip()[-900:]}")
        ids = [c["id"] for c in state["plan"]["beats"] if c.get("graphic")]       # in reel order, so g10 never sorts first
        fam = {}
        for gid in ids:
            f = gfx / "compositions" / f"{gid}.family.json"
            if f.exists():
                fam.setdefault(json.loads(f.read_text(encoding="utf-8"))["family"], gid)
        miss = [g for g in SMOKE_RENDER_TOO if not (gfx / "compositions" / f"{g}.family.json").exists()]
        if miss:
            raise RuntimeError(f"build.py wrote no comp for {miss}")
        state["example"] = fam
        return (f"{len([g for g in ids if (gfx / 'compositions' / f'{g}.family.json').exists()])} comps; one per family: "
                f"{fam}, plus {list(SMOKE_RENDER_TOO)}")

    step("build.example.py: the storyboard against the fixture", example)

    def renders():
        todo = [(x.id, x.frames) for x in state["kit"]]
        todo += [(g, json.loads((gfx / "compositions" / f"{g}.family.json").read_text(encoding="utf-8"))["frames"])
                 for g in dict.fromkeys([*(state.get("example") or {}).values(),
                                         *(SMOKE_RENDER_TOO if "example" in state else ())])]
        for gid, n in todo:
            out = render(gid, job=job)
            if frame_count(out) != n:
                raise RuntimeError(f"{out.name}: {frame_count(out)} frames, the comp is {n}")
            state["rendered"].append(gid)
        return ", ".join(state["rendered"])

    step("render: one comp per family, kit fixtures and example (+ SMOKE_RENDER_TOO), with the family flags", renders)

    def place():
        rows = []
        for gid in state["rendered"]:
            rec = json.loads((gfx / "compositions" / f"{gid}.family.json").read_text(encoding="utf-8"))
            f = sorted((gfx / "renders").glob(f"{gid}-alpha*.mov"))[-1]
            rows.append({"id": gid, "file": str(f), "start": rec["start"], "end": round(rec["start"] + rec["dur"], 6),
                         "kind": "overlay", "track": 2})
        (hf / "placement.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        return f"{len(rows)} rows"

    step("placement.json rows", place)

    def qa(expect, must=None):
        # The child prints UTF-8 (its stdio guard); the locale codec (cp1252 on Windows) garbled "·" into "Â·".
        r = subprocess.run(["uv", "run", "-q", str(REPO / "workflows" / "graphics-qa-short.py"), str(job), "--band",
                            f"{GATE_BAND[0]}-{GATE_BAND[1]}"], cwd=REPO, capture_output=True, encoding="utf-8", errors="replace")
        if r.returncode != expect or (must and not re.search(must, r.stdout)):
            raise RuntimeError(f"graphics-qa-short exited {r.returncode}, expected {expect}{' with ' + must if must else ''}:\n"
                               f"{r.stdout[-2500:]}{r.stderr[-400:]}")
        lines = r.stdout.strip().splitlines()
        return " | ".join([x.strip() for x in lines if "FAIL" in x and "band" in x][:2] + lines[-1:])

    step("graphics-qa-short: green on the clean build", lambda: qa(0))

    def plant():
        p = gfx / "compositions" / "k1.html"
        h = p.read_text(encoding="utf-8")
        i = h.rindex("</div>\n<script>")
        p.write_text(h[:i] + '<div style="position:absolute;left:120px;top:914px;width:840px;height:40px;background:#ffffff;"></div>\n'
                     + h[i:], encoding="utf-8")
        out = render("k1", job=job)
        return f"ink planted in y914-954 of k1, re-rendered as {out.name}"

    step("plant: ink in the caption band of k1 (a spill no static check can see)", plant)
    step("graphics-qa-short: red on the planted band defect", lambda: qa(1, r"FAIL\s+band"))
    fails = [x for x in results if x[1] == "FAIL"]
    print(f"\n{'PASS' if not fails else 'FAIL'}: {len(results) - len(fails)}/{len(results)} steps · {job}")
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="the talking-head explainer kit's engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("init", help="stage the kit into projects/<job>/hf-graphics/gfx")
    a.add_argument("job")
    a = sub.add_parser("drift", help="the job's staged copies vs the preset")
    a.add_argument("job")
    a = sub.add_parser("stage", help="stage a capture (the original + the all-intra render base) or, with --mark, a brand mark")
    a.add_argument("job")
    a.add_argument("id", help="the plan cell's id (a mark: any label)")
    a.add_argument("source")
    a.add_argument("--name", help="the render base's (or the mark's) file name under hf-graphics/gfx/assets/")
    a.add_argument("--mark", action="store_true", help="a brand mark: into hf-graphics/gfx/assets/logos/")
    a = sub.add_parser("render", help="render one comp with its family's flags")
    a.add_argument("id")
    a.add_argument("--ver")
    a.add_argument("--job", help="projects/<job> (default: the job this copy of the engine lives in)")
    a = sub.add_parser("smoke", help="the kit end to end on a synthetic job")
    a.add_argument("tmpdir")
    o = ap.parse_args(argv)
    if o.cmd == "init":
        init(o.job)
        return 0
    if o.cmd == "drift":
        return drift(o.job)
    if o.cmd == "stage":
        try:
            stage(o.job, o.id, o.source, o.name, o.mark)
        except BuildError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1
        return 0
    if o.cmd == "render":
        render(o.id, o.ver, o.job)
        return 0
    return smoke(o.tmpdir)


if __name__ == "__main__":
    sys.exit(main())
