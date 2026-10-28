"""layout.py: the executable twin of layout.md. One implementation of the frame: the mode spans, the caption height per
frame, the forced caption breaks and the layout checks. validate-plan.py, captions.py and lanes/premiere/layout-keys.py
import it, so the framing numbers and rules live here once and layout.md explains them.

  uv run presets/instagram/talking-head-explainer/layout.py projects/<job>                  # tables + rules, exit 1 on a FAIL
  uv run presets/instagram/talking-head-explainer/layout.py projects/<job> --check          # findings only (the gate form)
  uv run presets/instagram/talking-head-explainer/layout.py projects/<job> --variant ad     # the plan's variants.ad composed in
  uv run presets/instagram/talking-head-explainer/layout.py projects/<job> --json OUT.json  # spans, switches, breaks, shares, findings

Reads projects/<job>/graphics-plan.json (its top-level `layout`), face-frame.json (`modes`, written by
`workflows/face-frame.py projects/<job> --modes`), transcript/cuts.json (the V1 cuts), outputs/<job>.transcript.json (the
words a switch lands on) and, when it exists, hf-graphics/placement.json (the L-ALIGN placement check). A variant reads
cuts.<v>.json, outputs/<job>.<v>.transcript.json and placement.<v>.json when they exist.

THE PLAN CONTRACT (layout.md § 12). `layout` tiles 0..duration on the frame grid, on the timeline clock:
  "layout": [{"start": 0.0, "end": 4.629625, "mode": "S", "why": "the hook"},
             {"start": 9.551208, "end": 14.76475, "mode": "F", "caption_y": 1420, "why": "the escalation"}, ...]
  (a row may also be [start, end, mode] or [start, end, mode, caption_y]; `why` is carried, never read)
  S split · T tight · W wide (bare) · F full-screen graphic · O wide with a card over it.
  A row may carry its own footage transform, "frame": {"scale": s, "centre": [x, y]} (the units of face-frame.json
  `modes`), over its mode's: a take where the creator stands while the median framing is seated (the hook of the
  Windows test job put the face under the opaque panel) gets the span's own fit, measured with
  `face-frame.py projects/<job> --span A B --modes`. Every lane reads it through footage_spans().
  `caption_y` (the caption line's centre, 1080x1920) is required on F unless a cell over it carries "seam_clear": true
  (the graphic keeps the seam clear, so the line stays on the seam). On W/T/O it is only an override. An F row may give
  "ui_bottom" (the capture's bottom UI edge) instead: the line is then derived, ui_bottom + 58.5 (captions-style.md § 2).
  The captions cell (kind "captions") may carry "y": {"wide": px, "tight": px, "measured": "...", "measured_at": ISO}:
  heights read on stills and approved (captions-style.md § 2). A W/O line is the measured collar + 78.5 (face-frame.json
  `collar`); y.wide / y.tight win over it only with their `measured` note and a `measured_at` not older than the
  collar's (face-frame.json collar_read.at), or when no collar is measured.
  Graphic cells carry `family` (authored | capture | montage | overlay), `readable`, `shot_cuts`, `sync`, and an overlay
  card its box and the measured crown: "card": {"top": y, "bottom": y, "enter_top": y}, "crown": y
  (face-frame.py --crown A B; or face-frame.json "crowns": [{"start", "end", "y"}]). A montage's shots (its edges and
  its `shot_cuts`) each hold captures.md's MONTAGE_SHOT_S. The CTA cells carry "role": "cta"; a video with none has no
  ask, and L-CTA does not apply to it (layout.md § 7).
  "layout_deviations": [{"rule": "L-CTA", "why": "..."}] turns every FAIL of that rule (only the one within 0.5 s of an
  optional "at") into a WARN printed with its why.
  "variants": {"ad": {"from": t, "layout": [...], "cells": [...]}}: a second deliverable that inherits everything before
  `from`; its layout tiles `from` to its own end and its cells replace every cell from there.

face-frame.json `modes`: {"W"|"S"|"T": {"scale": s, "centre": [x, y]}}: scale relative to the source fitted to the frame
(1.0 = the untouched shot), centre = where the source's centre lands, in frame fractions (Premiere's Position on a
same-size sequence). The lanes convert them to their own units.

As a library (captions.py, lanes/premiere/layout-keys.py, validate-plan.py): spans, mode_at, caption_y_at, breaks, check,
report, compose_variant, modes, parse_fps; a missing input raises MissingInput, a broken map LayoutError.
Exit 0 = ok (warnings allowed) · 1 = a FAIL · 2 = a missing input, named by its field. Stdlib only; importing this module
has no side effects.
"""
import argparse
import bisect
import json
import math
import os
import re
import sys

# ── § Values (layout.md § Values: the same names, the same numbers; test_talking_head_layout.py holds them equal) ──
SEAM_Y = 960                       # the split seam: panel y0-960, the face under it; the caption line centre in S
SAFE = (200, 1620)                 # the platform-safe box: nothing identifying outside it, first entrance frame included
SPLIT_ZONE = (200, 845)            # S key content; ink ends 75 px above the seam caption's box top
SPILL_DISSOLVE_Y = 900             # a side spill is transparent by here
FULL_TOP = 260                     # F content starts here (the header clears the platform UI)
HAIR_GAP = 100                     # S: the median hair top this far under the seam (y1060); face-frame.py owns it too
FACE_CY_FALLBACK = 1385            # S fallback: the face-box centre here when the hair read fails
HAIR_GAP_MIN_Y = 1020              # S: with CHIN_MAX_Y, the largest face span a landscape S scales to (600 px)
CHIN_MAX_Y = 1620                  # S: a chin past this is a printed note, never a raised face (layout.md § 2)
T_SCALE = 1.40                     # T: the benchmark's punch-in at its face height (calibration only, read by no code)
T_FACE = (540, 866)                # T: the face-box centre's y lands here; x is the shoulders' (layout.md § 2)
T_FACE_H = 400                     # T: the face-box height the punch-in aims for
T_MIN = 1.15                       # T: never looser (a wobble, not a new angle)
W_BREATH_S = (0.6, 1.7)            # a W breather (an outcome band, not a gate)
BARE_W_MAX_S = 2.0                 # a longer face-only line punches in (T)
T_SPAN_S = (1.5, 4.5)
F_SPAN_S = (5.0, 7.0)              # one sentence; warn outside F_SPAN_WARN_S
F_SPAN_WARN_S = (4.0, 8.0)         # the Values block's "(warn outside 4-8)"
F_PER_120 = 2
F_SHARE_MAX = 0.12
FACE_MIN = 0.85
COVER_MIN = 0.75
STALE_MAX_S = 4.5
LONG_SHOT_S = 10
CARD_CROWN_AIR = 25                # a card's bottom edge this far above the tallest crown in its span
CARD_TOP_MIN = 204                 # no card entrance frame above this
SWITCH_EARLY_MAX_FRAMES = 2        # a mid-clip switch lands 0-2 frames before the word's onset, never late
NEAR_CUT_FRAMES = 2                # a layout edge this close to a V1 cut and not on it is a double cut: it sits ON the cut
PUSH_FRAMES = 10                   # the lateral push (graphics.md owns the motion; listed for the CTA hand-off)

# derived or owned elsewhere, never restated as a rule here
FRAME_W, FRAME_H = 1080, 1920      # the authoring frame
COLLAR_BOX_GAP = 40                # captions-style.md § Values: box top 40 px under the collar (2026-09-22)
UI_BOX_GAP = 20                    # captions-style.md § Values: box top 20 px under an F capture's bottom UI
BOX_ABOVE, BOX_BELOW = 38.5, 34.5  # captions-style.md § Values: the caption box around its line centre
CAPTION_COLLAR = COLLAR_BOX_GAP + BOX_ABOVE        # 78.5: line = collar + this
CAPTION_UI = UI_BOX_GAP + BOX_ABOVE                # 58.5: line = ui_bottom + this
MONTAGE_SHOT_S = (0.6, 1.3)        # captures.md § Values: one montage shot (the approved ran 1.1/1.0/0.6/1.3 s)
MODES = ("S", "T", "W", "F", "O")
FAMILIES = ("authored", "capture", "montage", "overlay")
FORBIDDEN_KINDS = ("punch-cut", "full-screen", "scene")   # the lane placer sends these down the full-screen mp4 path
CTA_ROLE, HOOK_ROLE = "cta", "hook"
# the approved benchmark's measured outcome (a 119.8 s sponsored explainer, 2026-09-23), printed beside a job's shares:
# calibration, never a quota (layout.md § 14)
BENCHMARK = {"S": 59.6, "T": 7.7, "W": 22.8, "W_bare": 6.1, "O": 16.7, "F": 10.0, "face": 90.0, "graphics": 86.2,
             "switches": 21, "mean_W": 1.22, "mean_T": 3.06}

# ── § 13 The checks (layout.md § 13: the same codes, levels and meanings, in the same order) ─────────────────────
RULES = [
    ("L-TILE", "FAIL", "gaps, overlaps, or an edge off the frame grid"),
    ("L-OPEN", "FAIL", "span 0 is not S at t=0"),
    ("L-EMPTY", "FAIL", "an S or F span not fully covered by graphic cells"),
    ("L-CROSS", "FAIL", "a non-overlay cell reaching into T or W"),
    ("L-OVERLAY", "FAIL", "an O span without an overlay cell"),
    ("L-CARD-T", "FAIL", "T under a card"),
    ("L-CARD-CLEAR", "FAIL", "a card over the measured crown, or entering above y204"),
    ("L-CTA", "FAIL", "any W or T from the last content graphic to the end"),
    ("L-SWITCH", "FAIL", "a switch neither on a V1 cut nor 0-2 frames before a word onset"),
    ("L-NEARCUT", "FAIL", "a layout edge 1-2 frames off a V1 cut instead of on it"),
    ("L-FAMILY", "FAIL", "a cell without a valid `family`"),
    ("L-READ-MONTAGE", "FAIL", "`readable: true` on a montage"),
    ("L-MONTAGE-SLOW", "FAIL", "a montage shot over 1.3 s, cell edge or shot cut to the next"),
    ("L-KIND", "FAIL", "a forbidden kind or a `bg` key"),
    ("L-CAPY", "FAIL", "an F span without `caption_y` whose graphic does not keep the seam clear, or a W/T/O span with no "
                       "measured collar and no plan override"),
    ("L-POSTHOOK", "WARN", "the span after the hook is not T"),
    ("L-BAREW", "WARN", "bare W over 2.0 s"),
    ("L-TIGHT", "WARN", "T outside 1.5-4.5 s"),
    ("L-FULL-COUNT", "WARN", "more than 2 F per 120 s"),
    ("L-FULL-SHARE", "WARN", "F over 12 %"),
    ("L-FULL-LEN", "WARN", "an F span outside 4-8 s"),
    ("L-FACE", "WARN", "face visible under 85 %"),
    ("L-COVER", "WARN", "graphics under 75 %"),
    ("L-LONGSHOT", "WARN", "a V1 segment of 10 s or more with no switch inside"),
    ("L-STALE", "WARN", "more than 4.5 s with no switch or cell boundary, outside O"),
    ("L-WORDCARD", "WARN", "a non-hook cell whose visuals are type only"),
    ("L-MONTAGE-FAST", "WARN", "a montage shot under 0.6 s"),
]
# run only when a placement exists (after 5b placed the graphics), so it cannot be a plan-time rule
PLACEMENT_RULES = [
    ("L-ALIGN", "FAIL", "a placed graphic edge off its framing switch frame, or a gap or overlap between back-to-back rows"),
]
_LEVEL = {code: level for code, level, _ in RULES + PLACEMENT_RULES}
_DEV_WINDOW = 0.5      # s: a deviation's optional `at` names its finding within this
_ALIGN_NEAR = 3        # frames: a placed edge this close to a switch or to its neighbour must sit ON it
_TYPE = re.compile(r"\b(type|text|word|words|headline|title|kinetic|keyword|label|lettering|copy|caption|quote)\b", re.I)
_THING = re.compile(r"\b(icon|logo|ui|screen|app|photo|image|picture|prop|chart|graph|diagram|avatar|phone|video|capture|"
                    r"button|bubble|map|card ui|window|dashboard|object|device|waveform|cursor|hand|product)\b", re.I)
_TEXT_KINDS = ("text-animation", "kinetic-title", "word-card", "title-card", "text")


class MissingInput(FileNotFoundError):
    """An input the layout cannot be resolved without: the file or field is named. main() exits 2 on it. It is a
    FileNotFoundError, so an importer's missing-file handler catches a missing field too."""


class LayoutError(ValueError):
    """The `layout` array itself is invalid (L-TILE): no span, share or caption height can be trusted."""


# ── the grid ───────────────────────────────────────────────────────────────────────────────────────────────────────
def parse_fps(v):
    if v is None:
        raise MissingInput("graphics-plan.json: no `fps` (the timeline rate, e.g. \"24000/1001\")")
    if isinstance(v, str) and "/" in v:
        n, d = v.split("/")
        return float(n) / float(d)
    return float(v)


def _fps(plan, fps=None):
    return parse_fps(fps if fps is not None else plan.get("fps"))


def frame(t, fps):
    return int(round(float(t) * fps))


def snap(t, fps):
    """t on the nearest frame of the grid, in seconds."""
    return round(round(float(t) * fps) / fps, 6)


def _on_grid(t, fps, tol=0.02):
    x = float(t) * fps
    return abs(x - round(x)) <= tol


# ── the spans ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _row(r):
    if isinstance(r, dict):
        cy = r.get("caption_y")
        if cy is None and r.get("ui_bottom") is not None:      # derived under the capture's bottom UI, never typed
            cy = float(r["ui_bottom"]) + CAPTION_UI
        return r.get("start"), r.get("end"), r.get("mode"), cy
    if isinstance(r, (list, tuple)) and len(r) in (3, 4):
        return r[0], r[1], r[2], (r[3] if len(r) == 4 else None)
    return None, None, None, None


FOOTAGE = {"S": "S", "T": "T", "W": "W", "F": "W", "O": "W"}   # F and O keep the untouched shot under their graphic


def _row_frame(r):
    """A row's own footage transform ({"scale", "centre": (x, y)}), None when it has none; raises ValueError when it
    is malformed."""
    f = r.get("frame") if isinstance(r, dict) else None
    if f is None:
        return None
    c = f.get("centre") if isinstance(f, dict) else None
    if not (isinstance(f, dict) and isinstance(f.get("scale"), (int, float)) and f["scale"] > 0
            and isinstance(c, (list, tuple)) and len(c) == 2 and all(isinstance(v, (int, float)) for v in c)
            and all(-0.5 <= float(v) <= 1.5 for v in c)):
        raise ValueError(f'`frame` needs {{"scale": > 0, "centre": [x, y]}} in frame fractions, got {f!r}')
    return {"scale": float(f["scale"]), "centre": (float(c[0]), float(c[1]))}


def _problems(plan, fps):
    """(spans, problems): the snapped spans and every L-TILE defect of the `layout` array."""
    if not plan.get("layout"):
        raise MissingInput("graphics-plan.json: no top-level `layout` array (layout.md § 12)")
    if plan.get("duration") is None:
        raise MissingInput("graphics-plan.json: no `duration`")
    end_f = frame(plan["duration"], fps)
    out, bad = [], []
    for i, r in enumerate(plan["layout"]):
        a, b, m, cy = _row(r)
        if a is None or b is None or m is None:
            bad.append((0.0, f"layout[{i}] needs start, end and mode: {r!r}"))
            continue
        a, b = float(a), float(b)
        if m not in MODES:
            bad.append((a, f"layout[{i}] mode {m!r} is not one of {' '.join(MODES)}"))
        for name, t in (("start", a), ("end", b)):
            if not _on_grid(t, fps):
                bad.append((t, f"layout[{i}] {name} {t:.6f} is off the frame grid (frame {t * fps:.3f}): snap it"))
        if frame(b, fps) <= frame(a, fps):
            bad.append((a, f"layout[{i}] {a:.3f}-{b:.3f} holds no frame"))
        try:
            _row_frame(r)
        except ValueError as e:
            bad.append((a, f"layout[{i}] {e}"))
        out.append((snap(a, fps), snap(b, fps), m, None if cy is None else float(cy)))
    out.sort(key=lambda s: s[0])
    if out and frame(out[0][0], fps) != 0:
        bad.append((0.0, f"the layout starts at {out[0][0]:.3f}, not 0"))
    for (a0, b0, m0, _), (a1, b1, m1, _) in zip(out, out[1:]):
        g = frame(a1, fps) - frame(b0, fps)
        if g:
            bad.append((min(a1, b0), f"a {abs(g)}-frame {'gap' if g > 0 else 'overlap'} between {m0} and {m1} "
                                     f"at {min(a1, b0):.3f}-{max(a1, b0):.3f}"))
    if out and frame(out[-1][1], fps) != end_f:
        bad.append((out[-1][1], f"the layout ends on frame {frame(out[-1][1], fps)}, the cut on frame {end_f} "
                                f"({float(plan['duration']):.3f} s)"))
    return out, bad


def spans(plan, fps=None):
    """[(a, b, mode, caption_y)] frame-snapped and sorted; caption_y is the row's own (None when it has none). Raises
    LayoutError (L-TILE) unless the array tiles 0..duration on the frame grid with modes from S T W F O."""
    fps = _fps(plan, fps)
    out, bad = _problems(plan, fps)
    if bad:
        raise LayoutError("; ".join(m for _, m in bad))
    return out


def footage_spans(plan, md, fps=None):
    """[(a, b, key, {scale, centre})] per layout row, frame-snapped and sorted like spans(): the FOOTAGE transform
    each lane lays (layout-keys.py, the CapCut `layout` command, the chat-only assemble). F and O keep W's footage; a
    row's own `frame` wins over its mode's face-frame.json transform. `key` names the transform (the footage mode, or
    "<mode>*<scale>,<x>,<y>" for a row frame), so two adjacent rows of one mode with different frames are a switch
    and two with the same are not. `md` is modes(face)."""
    fps = _fps(plan, fps)
    sp = spans(plan, fps)
    rows = sorted(((snap(float(_row(r)[0]), fps), r) for r in plan["layout"]), key=lambda x: x[0])
    out = []
    for (a, b, m, _y), (_a, r) in zip(sp, rows):
        f = _row_frame(r)
        k = FOOTAGE[m]
        if f is None or (abs(f["scale"] - float(md[k]["scale"])) < 1e-6
                         and all(abs(x - float(y)) < 1e-6 for x, y in zip(f["centre"], md[k]["centre"]))):
            out.append((a, b, k, md[k]))                # a frame equal to its mode's transform is that mode
        else:
            out.append((a, b, f"{FOOTAGE[m]}*{f['scale']:g},{f['centre'][0]:g},{f['centre'][1]:g}", f))
    return out


def footage_at(t, fsp):
    """(key, {scale, centre}) of the footage_spans() row holding t (a <= t < b; the last keeps its own end)."""
    i = bisect.bisect_right([s[0] for s in fsp], t + 1e-9) - 1
    s = fsp[max(0, min(i, len(fsp) - 1))]
    return s[2], s[3]


def runs(sp):
    """spans merged into maximal same-mode runs [(a, b, mode)]: what the viewer sees as one layout."""
    out = []
    for a, b, m, *_ in sp:
        if out and out[-1][2] == m and abs(out[-1][1] - a) < 1e-6:
            out[-1] = (out[-1][0], b, m)
        else:
            out.append((a, b, m))
    return out


def switches(sp):
    """[(t, from_mode, to_mode)]: every layout change, in order (the SFX cut-ins and the footage keys read these)."""
    r = runs(sp)
    return [(y[0], x[2], y[2]) for x, y in zip(r, r[1:])]


def span_at(t, sp):
    """the span holding t (a <= t < b; the last span keeps its own end)."""
    i = bisect.bisect_right([s[0] for s in sp], t + 1e-9) - 1
    return sp[max(0, min(i, len(sp) - 1))]


def mode_at(t, plan_or_spans, fps=None):
    """the layout mode at t (per frame f, ask at (f + 0.5) / fps): mode_at(t, plan) or mode_at(t, spans)."""
    sp = spans(plan_or_spans, fps) if isinstance(plan_or_spans, dict) else plan_or_spans
    return span_at(t, sp)[2]


# ── the cells ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _is_captions(c):
    return c.get("kind") == "captions" or c.get("id") == "captions"


def cells(plan):
    """the graphic cells that occupy the frame (the caption layer is not one)."""
    return [c for c in plan.get("beats") or [] if c.get("graphic") and not _is_captions(c)]


def _cf(c, fps):
    return frame(c.get("start", 0), fps), frame(c.get("end", 0), fps)


def _merge(ranges):
    out = []
    for a, b in sorted(r for r in ranges if r[1] > r[0]):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _uncovered(a, b, cover):
    gaps, t = [], a
    for x, y in cover:
        if y <= t or x >= b:
            continue
        if x > t:
            gaps.append((t, x))
        t = max(t, y)
    if t < b:
        gaps.append((t, b))
    return gaps


def compose_variant(plan, name):
    """The plan of a second deliverable: the main layout clipped at variants[name].from plus the variant's layout; the
    main cells that start before `from` (clipped to it) plus the variant's cells; the variant's own end as duration."""
    v = (plan.get("variants") or {}).get(name)
    if v is None:
        raise MissingInput(f"graphics-plan.json: no `variants.{name}`")
    for k in ("from", "layout"):
        if k not in v:
            raise MissingInput(f"graphics-plan.json: `variants.{name}` has no `{k}`")
    cut = snap(v["from"], _fps(plan))
    lay = []
    for r in plan.get("layout") or []:
        a, b, m, cy = _row(r)
        if a is not None and float(a) < cut - 1e-6:
            lay.append({"start": float(a), "end": min(float(b), cut), "mode": m}
                       | ({} if cy is None else {"caption_y": cy}))
    for r in v["layout"]:
        a, b, m, cy = _row(r)
        lay.append({"start": a, "end": b, "mode": m} | ({} if cy is None else {"caption_y": cy}))
    duration = float(v.get("duration") or max(float(_row(r)[1]) for r in v["layout"]))
    beats = []
    for c in plan.get("beats") or []:
        if _is_captions(c):
            beats.append(dict(c, end=duration))
        elif float(c.get("start", 0)) < cut - 1e-6:
            beats.append(dict(c, end=min(float(c.get("end", 0)), cut)))
    beats += [dict(c) for c in (v.get("cells") or v.get("beats") or [])]
    # the main plan's waivers still apply before `from` (one pinned after it named replaced material); an inherited one
    # is marked, so a variant run never calls the organic's waiver stale
    devs = [dict(d, inherited=True) for d in plan.get("layout_deviations") or []
            if d.get("at") is None or float(d["at"]) < cut]
    out = {k: x for k, x in plan.items() if k != "variants"}
    out.update(layout=lay, beats=beats, duration=duration, variant=name,
               layout_deviations=devs + list(v.get("layout_deviations") or []))
    return out


# ── the caption height ─────────────────────────────────────────────────────────────────────────────────────────────
def modes(face):
    """face-frame.json `modes` -> {W, S, T: {scale, centre: [x, y]}} (see the header for the units)."""
    m = (face or {}).get("modes")
    if not isinstance(m, dict):
        raise MissingInput("face-frame.json: no `modes` (run: uv run workflows/face-frame.py projects/<job> --modes)")
    out = {}
    for k in ("W", "S", "T"):
        v = m.get(k)
        if not isinstance(v, dict) or "scale" not in v or len(v.get("centre") or []) != 2:
            raise MissingInput(f"face-frame.json: `modes.{k}` needs `scale` and `centre` [x, y] "
                               "(run: uv run workflows/face-frame.py projects/<job> --modes)")
        out[k] = {"scale": float(v["scale"]), "centre": (float(v["centre"][0]), float(v["centre"][1]))}
    return out


def _captions_y(plan):
    for c in plan.get("beats") or []:
        if _is_captions(c) and isinstance(c.get("y"), dict):
            return c["y"]
    return {}


def _override(plan, face, key):
    """The captions cell's approved y.<key> when it still holds, else None. ONE precedence (captions-style.md § 2): a
    measured collar in face-frame.json wins, unless the override carries its `measured` note AND is not older than that
    collar (y.measured_at >= face-frame.json collar_read.at, ISO dates). With no measured collar the override stands.
    So a stale y.wide never silently beats a fresh measurement, and an approved nudge (a new still test) still wins."""
    y = _captions_y(plan)
    v = y.get(key)
    if v is None:
        return None
    col = (face or {}).get("collar")
    if col is None:
        return float(v)
    if not y.get("measured"):
        return None
    at = str(((face or {}).get("collar_read") or {}).get("at") or "")
    return float(v) if not at or str(y.get("measured_at") or "") >= at else None


def collar(plan, face):
    """the collar/skin line on the wide shot (y, 1080x1920): face-frame.json `collar`, else read back from the captions
    cell's y.wide (the approved line minus 78.5). None when neither exists."""
    c = (face or {}).get("collar")
    if isinstance(c, dict):
        c = c.get("y")
    if c is not None:
        return float(c)
    w = _captions_y(plan).get("wide")
    return None if w is None else float(w) - CAPTION_COLLAR


def _wide_y(plan, face):
    w = _override(plan, face, "wide")
    if w is not None:
        return w
    c = collar(plan, face)
    if c is None:
        raise MissingInput("no collar: face-frame.json `collar` or the captions cell `y.wide` (captions-style.md § 2)")
    return c + CAPTION_COLLAR


def _tight_y(plan, face):
    t = _override(plan, face, "tight")
    if t is not None:
        return t
    c = collar(plan, face)
    if c is None:
        raise MissingInput("no collar: face-frame.json `collar` or the captions cell `y.wide` (captions-style.md § 2)")
    md = modes(face)
    w, tt = md["W"], md["T"]
    src = (c - w["centre"][1] * FRAME_H) / w["scale"] + FRAME_H / 2      # the collar on the fitted source
    return tt["centre"][1] * FRAME_H + tt["scale"] * (src - FRAME_H / 2) + CAPTION_COLLAR


def _clamp(y):
    lo, hi = SAFE[0] + BOX_ABOVE, SAFE[1] - BOX_BELOW
    return min(hi, max(lo, y)), not (lo <= y <= hi)


def _span_y(span, plan, face):
    a, b, m, cy = span
    if cy is not None:
        return float(cy)
    if m == "S" or m == "F":
        return float(SEAM_Y)
    if m == "T":
        return _tight_y(plan, face)
    return _wide_y(plan, face)


def caption_y_at(t, plan, face=None, warn=None):
    """the caption line's centre y at t: S on the seam; W and O on the shirt (collar + 78.5); T that collar carried
    through the punch-in (layout.md § 10); F its span's caption_y, else the seam. A span's own caption_y overrides.
    Clamped into the safe box; a clamp is appended to `warn` (a list) as (t, message) when one is given."""
    sp = span_at(t, spans(plan))
    return _clamped(sp, _span_y(sp, plan, face), warn)


def _clamped(sp, y, warn):
    y2, clamped = _clamp(y)
    if clamped and warn is not None:
        warn.append((sp[0], f"{sp[2]} {sp[0]:.3f}-{sp[1]:.3f}: caption y{y:.1f} leaves the safe box {SAFE[0]}-{SAFE[1]}, "
                            f"clamped to y{y2:.1f}: the framing is wrong (a punch-in too tight), never the caption"))
    return round(y2, 1)


# ── the breaks ─────────────────────────────────────────────────────────────────────────────────────────────────────
def v1_cuts(cuts, plan=None):
    """the interior V1 cut times on the plan's clock, from a cuts.json dict (or a list of times)."""
    if cuts is None:
        return []
    if isinstance(cuts, (list, tuple)):
        return sorted(float(x) for x in cuts)
    segs = cuts.get("segments") or []
    off = float((plan or {}).get("timeline_offset") or 0)
    if segs and all(isinstance(s.get("_timeline"), list) for s in segs):
        ends = [float(s["_timeline"][1]) - off for s in segs]      # an EDL read back from the timeline: its own grid
    else:
        t, ends = 0.0, []
        for s in segs:
            t += float(s["end"]) - float(s["start"])
            ends.append(t)
    return ends[:-1]


def caption_breaks_on(c):
    """Do cell c's own shot_cuts break the caption line? A picture change inside a graphic breaks it, EXCEPT inside a
    montage: its shots cut on a steady beat, mid-word, and the band stays S the whole time, so a line jumps nowhere and
    no word vanishes; breaking there stranded words (a 3-frame SOCIALS line, spoken frames with no caption) where the
    approved short ran its lines straight across the cuts. A cell's `caption_breaks` (true / false) overrides."""
    v = c.get("caption_breaks")
    return bool(v) if v is not None else c.get("family") != "montage"


def breaks(plan, cuts):
    """every time a caption line must break at, frame-snapped and deduped: the V1 cuts, the layout edges, every graphic
    cell's edges and the shot_cuts of every cell that breaks on them (caption_breaks_on: never a montage's own)."""
    fps = _fps(plan)
    end_f = frame(plan["duration"], fps)
    ts = list(v1_cuts(cuts, plan))
    for a, b, _, _ in spans(plan, fps):
        ts += [a, b]
    for c in cells(plan):
        ts += [c.get("start", 0), c.get("end", 0)] + (list(c.get("shot_cuts") or []) if caption_breaks_on(c) else [])
    return [round(f / fps, 6) for f in sorted({frame(t, fps) for t in ts}) if 0 < f < end_f]


# ── the checks ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _words(words):
    if words is None:
        return []
    if isinstance(words, dict):
        words = words.get("words") or []
    return sorted((w for w in words if w.get("type", "word") == "word" and "start" in w), key=lambda w: w["start"])


def edl_sig(segs):
    """A short fingerprint of an EDL's segments, the same function as workflows/face-frame.py's (the parity test holds
    them equal): face-frame.py stamps each crown with the EDL it was read through."""
    import hashlib
    body = json.dumps([[os.path.basename(str(x.get("clip") or "")), round(float(x["start"]), 6), round(float(x["end"]), 6)]
                       for x in segs or []], separators=(",", ":"))
    return hashlib.sha1(body.encode()).hexdigest()[:12]


def _crown(c, face, sigs=None):
    """(the tallest measured crown over cell c or None, how many overlapping crowns were read through another cut).
    A crown stamped with an EDL fingerprint not in `sigs` is stale after a re-cut and never used: its timeline span
    now holds other material."""
    if c.get("crown") is not None:
        return float(c["crown"]), 0
    a, b = float(c.get("start", 0)), float(c.get("end", 0))
    over = [x for x in (face or {}).get("crowns") or [] if float(x["start"]) < b and float(x["end"]) > a]
    fresh = [x for x in over if not sigs or x.get("edl_sig") is None or x["edl_sig"] in sigs]
    ys = [float(x["y"]) for x in fresh]
    return (min(ys) if ys else None), len(over) - len(fresh)       # the TALLEST crown is the smallest y


def _type_only(c):
    if str(c.get("kind", "")).lower() in _TEXT_KINDS:
        return True
    vs = c.get("visuals")
    return (isinstance(vs, list) and len(vs) > 0
            and all(_TYPE.search(str(v)) and not _THING.search(str(v)) for v in vs))


def check(plan, cuts, words, face, placement=None):
    """[(code, level, t, message)] for every rule in RULES (and PLACEMENT_RULES when a placement is passed), in time
    order. layout_deviations turn a named FAIL into a WARN carrying its why. An invalid `layout` (L-TILE) returns only
    those findings: nothing else can be judged on it. face may be None before face-frame.json exists: a height that
    needs it is then an L-CAPY FAIL."""
    return _check(plan, cuts, words, face, placement)[0]


def _check(plan, cuts, words, face, placement=None):
    """(findings, the layout_deviations that matched no FAIL)"""
    fps = _fps(plan)
    sp, bad = _problems(plan, fps)
    raw = [("L-TILE", t, m) for t, m in bad]
    if raw:
        return _waive(plan, raw)
    dur = float(plan["duration"])
    end_f = frame(dur, fps)
    rn = runs(sp)
    rf = [(frame(a, fps), frame(b, fps), m) for a, b, m in rn]
    sw = switches(sp)
    cs = cells(plan)
    ws = _words(words)
    cutl = v1_cuts(cuts, plan)
    cut_f = [frame(c, fps) for c in cutl]
    over = [c for c in cs if c.get("family") == "overlay"]

    def add(code, t, msg):
        raw.append((code, round(float(t), 6), msg))

    # the hook
    if rn[0][2] != "S":
        add("L-OPEN", 0.0, f"frame 0 is {rn[0][2]}: the hook opens split, its visual moving on frame 0 (§ 6)")
    elif len(rn) > 1 and rn[1][2] != "T":
        add("L-POSTHOOK", rn[1][0], f"after the hook comes {rn[1][2]} {rn[1][0]:.3f}-{rn[1][1]:.3f}: the promise punches in (T)")

    # coverage: S and F carry a graphic on every frame, O its card, T and W none
    cover = _merge([_cf(c, fps) for c in cs])
    card = _merge([_cf(c, fps) for c in over])
    for (fa, fb, m), (a, b, _) in zip(rf, rn):
        if m in ("S", "F"):
            for x, y in _uncovered(fa, fb, cover):
                add("L-EMPTY", x / fps, f"{m} {a:.3f}-{b:.3f}: {(y - x) / fps:.2f} s ({x / fps:.3f}-{y / fps:.3f}) with no graphic: "
                                        "an empty panel; hold the face and cut on the word (§ 4)")
        elif m == "O":
            gaps = _uncovered(fa, fb, card)
            if gaps == [(fa, fb)]:
                add("L-OVERLAY", a, f"O {a:.3f}-{b:.3f} has no overlay cell (family \"overlay\"): an O without its card is a W")
            else:
                for x, y in gaps:
                    add("L-OVERLAY", x / fps, f"O {a:.3f}-{b:.3f}: its card is missing {x / fps:.3f}-{y / fps:.3f}: "
                                              "the card holds across the whole live beat (§ 2)")
        if m in ("T", "W"):
            for c in cs:
                ca, cb = _cf(c, fps)
                x, y = max(fa, ca), min(fb, cb)
                if y <= x:
                    continue
                if c.get("family") == "overlay":
                    if m == "T":
                        add("L-CARD-T", x / fps, f"{c.get('id')} is a card over T {a:.3f}-{b:.3f}: a punch-in pushes the "
                                                 "forehead into the card; the framing never changes under a card (§ 9)")
                else:
                    add("L-CROSS", x / fps, f"{c.get('id')} reaches {(y - x) / fps:.2f} s into {m} {a:.3f}-{b:.3f}: "
                                            "a graphic boundary and its framing switch are the same frame (§ 4)")

    # the cards clear the crown
    sigs = {s_ for s_ in (edl_sig(cuts.get("segments")) if isinstance(cuts, dict) else None,
                          plan.get("_edl_sig_main")) if s_}
    for c in over:
        box, (crown, stale) = c.get("card") or {}, _crown(c, face, sigs)
        t = float(c.get("start", 0))
        if box.get("bottom") is None or crown is None:
            add("L-CARD-CLEAR", t, f"{c.get('id')}: record its \"card\" box and the measured \"crown\" "
                                   "(uv run workflows/face-frame.py projects/<job> --crown A B): clearance is measured (§ 9)"
                                   + (f"; {stale} crown(s) in face-frame.json were read through another cut (a re-cut "
                                      "moved the material): re-read them" if stale else ""))
            continue
        if float(box["bottom"]) > crown - CARD_CROWN_AIR:
            add("L-CARD-CLEAR", t, f"{c.get('id')}: the card's bottom y{box['bottom']} is within {CARD_CROWN_AIR} px of the "
                                   f"tallest crown y{crown:.0f} (needs <= y{crown - CARD_CROWN_AIR:.0f})")
        top = box.get("enter_top", box.get("top"))
        if top is not None and float(top) < CARD_TOP_MIN:
            add("L-CARD-CLEAR", t, f"{c.get('id')}: the card's entrance reaches y{top} (< y{CARD_TOP_MIN}): under the platform UI")

    # the CTA stays split from the last content graphic to the end. The rule protects the ask (§ 7), so a video with no
    # `role: cta` cell has nothing for it to hold: one that ends on a face-carried punchline or a T closer is not failed
    cta = [c for c in cs if str(c.get("role", "")).lower() == CTA_ROLE]
    first = min((frame(c["start"], fps) for c in cta), default=end_f)
    content = [_cf(c, fps)[1] for c in cs if c not in cta and _cf(c, fps)[1] <= first]
    if cta and content:
        lf = max(content)
        for (fa, fb, m), (a, b, _) in zip(rf, rn):
            if m in ("W", "T") and fb > lf:
                add("L-CTA", max(fa, lf) / fps, f"{m} {a:.3f}-{b:.3f} after the last content graphic ({lf / fps:.3f}): "
                                                "the CTA never breaks the split; push graphic to graphic (§ 7)")

    # every layout edge (a switch, or a same-mode row edge: both break the caption line) sits ON a V1 cut or clear of
    # it. 1-2 frames off, the new clip plays that long in the old layout (or the old clip in the new one): a double cut
    # on the program, which flash-scan.py fails at export. Every lane keys the edge where the plan puts it
    for a, _, _, _ in sp[1:]:
        fe = frame(a, fps)
        near = sorted((fc for fc in cut_f if 0 < abs(fe - fc) <= NEAR_CUT_FRAMES), key=lambda fc: abs(fe - fc))
        if near and fe not in cut_f:
            fc, n = near[0], abs(fe - near[0])
            add("L-NEARCUT", a, f"the layout edge on frame {fe} ({a:.6f}) is {n} frame{'s' if n > 1 else ''} "
                                f"{'after' if fe > fc else 'before'} the V1 cut on frame {fc}: {n} frame{'s' if n > 1 else ''} "
                                f"of the {'new clip in the old' if fe > fc else 'old clip in the new'} layout, a double cut. "
                                f"Move the edge, and every cell edge on it, onto the cut: {round(fc / fps, 6)} (§ 4)")

    # where each switch lands
    for t, m0, m1 in sw:
        fs = frame(t, fps)
        if any(abs(fs - fc) <= NEAR_CUT_FRAMES for fc in cut_f):
            continue            # on a V1 cut; 1-2 frames off one is L-NEARCUT's defect, never judged as a word landing
        if not ws:
            continue
        if any(0 <= frame(w["start"], fps) - fs <= SWITCH_EARLY_MAX_FRAMES for w in ws):
            continue
        nxt = next((w for w in ws if frame(w["start"], fps) > fs), None)
        prv = next((w for w in reversed(ws) if frame(w["start"], fps) < fs), None)
        why = (f"{frame(nxt['start'], fps) - fs} frames before '{nxt.get('text')}'" if nxt else "after the last word")
        if prv and prv["end"] > t:
            why += f", inside '{prv.get('text')}'"
        add("L-SWITCH", t, f"the {m0}>{m1} switch at {t:.3f} is on no V1 cut and lands {why}: cut on the word's onset, "
                           f"0-{SWITCH_EARLY_MAX_FRAMES} frames early, never late (§ 4)")

    # the cells themselves
    # a montage shot is felt, never read: its band's ends are taken to the whole frame outside them, so 1.3 s on a
    # 23.976 grid is 32 frames (the approved chart-drawing last shot) and 0.6 s is 14
    m_lo = math.floor(MONTAGE_SHOT_S[0] * fps + 1e-6)
    m_hi = math.ceil(MONTAGE_SHOT_S[1] * fps - 1e-6)
    for c in cs:
        t, gid = float(c.get("start", 0)), c.get("id")
        if c.get("family") not in FAMILIES:
            add("L-FAMILY", t, f"{gid}: family {c.get('family')!r} is not one of {', '.join(FAMILIES)} (graphics.md § Families)")
        if c.get("family") == "montage" and c.get("readable") is True:
            add("L-READ-MONTAGE", t, f"{gid}: a montage is glanced, never read: frame what must be read whole and flat (captures.md)")
        if c.get("family") == "montage":
            ca, cb = _cf(c, fps)
            ed = [ca, *sorted({f for f in (frame(x, fps) for x in c.get("shot_cuts") or []) if ca < f < cb}), cb]
            for i, (x, y) in enumerate(zip(ed, ed[1:]), 1):
                shot = f"{gid}: shot {i} of {len(ed) - 1} holds {(y - x) / fps:.2f} s ({x / fps:.3f}-{y / fps:.3f})"
                if y - x > m_hi:
                    add("L-MONTAGE-SLOW", x / fps, f"{shot}, over {MONTAGE_SHOT_S[1]:g} s: a montage this slow reads as a "
                                                   "slideshow. Cut on a steady beat of about 1 s from the clause's first "
                                                   "word; a noun further off than that gets two close-ups of its screen, "
                                                   "never one long hold (captures.md § 7)"
                                                   + ("" if c.get("shot_cuts") else "; the cell has no `shot_cuts`"))
                elif y - x < m_lo:
                    add("L-MONTAGE-FAST", x / fps, f"{shot}, under {MONTAGE_SHOT_S[0]:g} s: a flash, not a glance; two "
                                                   "items on one screen share a shot (captures.md § 7)")
        if str(c.get("kind", "")).lower() in FORBIDDEN_KINDS or "bg" in c:
            add("L-KIND", t, f"{gid}: kind {c.get('kind')!r}{' with a `bg` key' if 'bg' in c else ''}: every render here is an "
                             "alpha overlay; a full-screen is layout mode F, never a kind (§ 12)")
        if _type_only(c) and str(c.get("role", "")).lower() != HOOK_ROLE and frame(c.get("start", 0), fps) != 0:
            add("L-WORDCARD", t, f"{gid}: its visuals are type only: enact the line with an object, a UI or a state change; "
                                 "the caption carries the words (graphics.md § The two laws)")

    # the caption heights
    for s in sp:
        a, b, m, cy = s
        if m == "F" and cy is None:
            fa, fb = frame(a, fps), frame(b, fps)
            if not any(c.get("seam_clear") for c in cs if _cf(c, fps)[0] < fb and _cf(c, fps)[1] > fa):
                add("L-CAPY", a, f"F {a:.3f}-{b:.3f} has no caption_y and no cell over it keeps the seam clear "
                                 "(\"seam_clear\": true): record the graphic's bottom UI as `ui_bottom` (the line goes "
                                 f"{CAPTION_UI:g} px under it) or set caption_y (§ 10)")
            continue
        try:
            wn = []
            _clamped(s, _span_y(s, plan, face), wn)
            for tt, msg in wn:
                add("L-CAPY", tt, msg)
        except MissingInput as e:
            add("L-CAPY", a, f"{m} {a:.3f}-{b:.3f}: no caption height: {e}")

    # cadence (outcomes; each a question to the plan)
    share = {m: sum(b - a for a, b, mm in rn if mm == m) / dur for m in MODES}
    for a, b, m in rn:
        d = b - a
        if m == "W" and d > BARE_W_MAX_S + 1e-6:
            add("L-BAREW", a, f"bare W {a:.3f}-{b:.3f} holds {d:.2f} s: a longer face-only line punches in (T)")
        if m == "T" and not (T_SPAN_S[0] - 1e-6 <= d <= T_SPAN_S[1] + 1e-6):
            add("L-TIGHT", a, f"T {a:.3f}-{b:.3f} holds {d:.2f} s (outside {T_SPAN_S[0]}-{T_SPAN_S[1]} s)")
        if m == "F" and not (F_SPAN_WARN_S[0] - 1e-6 <= d <= F_SPAN_WARN_S[1] + 1e-6):
            add("L-FULL-LEN", a, f"F {a:.3f}-{b:.3f} holds {d:.2f} s: a full-screen is one sentence "
                                 f"({F_SPAN_S[0]:g}-{F_SPAN_S[1]:g} s, warn outside {F_SPAN_WARN_S[0]:g}-{F_SPAN_WARN_S[1]:g})")
    nf = sum(1 for _, _, m in rn if m == "F")
    cap = math.ceil(F_PER_120 * dur / 120 - 1e-9)
    if nf > cap:
        add("L-FULL-COUNT", 0.0, f"{nf} full-screens in {dur:.1f} s (at most {cap}: {F_PER_120} per 120 s)")
    if share["F"] > F_SHARE_MAX + 1e-9:
        add("L-FULL-SHARE", 0.0, f"F is {share['F']:.1%} of runtime (over {F_SHARE_MAX:.0%})")
    if 1 - share["F"] < FACE_MIN - 1e-9:
        add("L-FACE", 0.0, f"the face is on screen {1 - share['F']:.1%} of runtime (under {FACE_MIN:.0%})")
    covered = sum(min(y, end_f) - max(x, 0) for x, y in cover if min(y, end_f) > max(x, 0)) / end_f
    if covered < COVER_MIN - 1e-9:
        add("L-COVER", 0.0, f"graphics cover {covered:.1%} of runtime (under {COVER_MIN:.0%})")
    edges = [0] + cut_f + [end_f]
    sw_f = [frame(t, fps) for t, _, _ in sw]
    for x, y in zip(edges, edges[1:]):
        if (y - x) / fps >= LONG_SHOT_S - 1e-6 and not any(x < s < y for s in sw_f):
            add("L-LONGSHOT", x / fps, f"a {(y - x) / fps:.1f} s V1 shot {x / fps:.3f}-{y / fps:.3f} with no switch inside: "
                                       "is the whole line necessary? if it stays, switch at a phrase boundary")
    pts = {0, end_f, *sw_f}
    for c in cs:
        pts |= {*_cf(c, fps), *(frame(t, fps) for t in c.get("shot_cuts") or [])}
    pts = sorted(p for p in pts if 0 <= p <= end_f)
    for x, y in zip(pts, pts[1:]):
        if (y - x) / fps > STALE_MAX_S + 1e-6 and mode_at((x + 0.5) / fps, sp) != "O":
            add("L-STALE", x / fps, f"{(y - x) / fps:.1f} s ({x / fps:.3f}-{y / fps:.3f}) with no switch, cell boundary or "
                                    "shot cut: give the line a beat (a new shot, a switch)")

    # the placement, once the graphics are placed
    if placement:
        rows = [r for r in placement if r.get("kind") != "captions" and r.get("id") != "captions"]
        for r in rows:
            for name in ("start", "end"):
                e = frame(r[name], fps)
                near = [s for s in sw_f if 0 < abs(e - s) <= _ALIGN_NEAR]
                if near and e not in sw_f:
                    add("L-ALIGN", e / fps, f"{r.get('id')} {name} on frame {e} is {e - near[0]:+d} frames off the switch on "
                                            f"frame {near[0]}: a graphic edge and its framing switch are one frame")
        tracks = {}
        for r in rows:
            tracks.setdefault(r.get("track"), []).append(r)
        for rs in tracks.values():
            rs.sort(key=lambda r: float(r["start"]))
            for x, y in zip(rs, rs[1:]):
                g = frame(y["start"], fps) - frame(x["end"], fps)
                if g < 0 or 0 < g <= _ALIGN_NEAR:
                    add("L-ALIGN", float(y["start"]), f"{x.get('id')} > {y.get('id')}: a {abs(g)}-frame "
                                                      f"{'overlap' if g < 0 else 'gap'}: back-to-back graphics hand off on one frame")
    return _waive(plan, raw)


def _waive(plan, raw):
    """(findings, unused deviations): each finding at its rule's level, a FAIL named by a deviation turned WARN."""
    devs = list(plan.get("layout_deviations") or [])
    for i, d in enumerate(devs):
        if not d.get("rule") or not str(d.get("why") or d.get("reason") or "").strip():
            raise MissingInput(f"graphics-plan.json: layout_deviations[{i}] needs `rule` and `why`")
    used, out = set(), []
    for code, t, msg in raw:
        level = _LEVEL[code]
        if level == "FAIL":
            for i, d in enumerate(devs):
                if d["rule"] == code and (d.get("at") is None or abs(float(d["at"]) - t) <= _DEV_WINDOW):
                    level, msg = "WARN", f"{msg} [deviation: {d.get('why') or d.get('reason')}]"
                    used.add(i)
                    break
        out.append((code, level, t, msg))
    out.sort(key=lambda f: (f[2], f[0]))
    return out, [d for i, d in enumerate(devs) if i not in used]


def report(plan, fps=None):
    """the outcome numbers (percent of runtime, seconds): S T W (the wide framing, bare or carded) O F, bare W, face
    visible, graphics coverage, switch count, mean W breather and mean T beat."""
    fps = _fps(plan, fps)
    dur = float(plan["duration"])
    rn = runs(spans(plan, fps))
    tot = {m: sum(b - a for a, b, mm in rn if mm == m) for m in MODES}
    end_f = frame(dur, fps)
    gfx = sum(min(y, end_f) - max(x, 0) for x, y in _merge([_cf(c, fps) for c in cells(plan)])
              if min(y, end_f) > max(x, 0)) / fps
    w = [b - a for a, b, m in rn if m == "W"]
    t = [b - a for a, b, m in rn if m == "T"]
    pct = lambda x: round(100 * x / dur, 1)
    return {"S": pct(tot["S"]), "T": pct(tot["T"]), "W": pct(tot["W"] + tot["O"]), "W_bare": pct(tot["W"]),
            "O": pct(tot["O"]), "F": pct(tot["F"]), "face": pct(dur - tot["F"]), "graphics": pct(gfx),
            "switches": len(rn) - 1, "mean_W": round(sum(w) / len(w), 2) if w else 0.0,
            "mean_T": round(sum(t) / len(t), 2) if t else 0.0, "duration": round(dur, 3)}


# ── CLI ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _read(path, what, required=True):
    if not os.path.isfile(path):
        if required:
            raise MissingInput(f"{what}: no file at {path}")
        return None
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def _inputs(job, variant=None):
    """(plan, face, cuts, words, placement) of projects/<job>, the variant composed in. The face-frame.json modes and
    the transcript are required here: the footage keys and every mid-clip switch are resolved against them."""
    name = os.path.basename(os.path.abspath(job))
    plan = _read(os.path.join(job, "graphics-plan.json"), "graphics-plan.json")
    if variant:
        plan = compose_variant(plan, variant)
        main = os.path.join(job, "transcript", "cuts.json")     # a crown read through the organic cut holds before `from`
        if os.path.isfile(main):
            plan["_edl_sig_main"] = edl_sig((_read(main, "transcript/cuts.json") or {}).get("segments"))
    _problems(plan, _fps(plan))      # the plan's own fields (layout, fps, duration) are named before any other file
    tag = f".{variant}" if variant else ""
    face = _read(os.path.join(job, "face-frame.json"),
                 "face-frame.json (run: uv run workflows/face-frame.py projects/<job> --modes)")
    modes(face)
    cp = os.path.join(job, "transcript", f"cuts{tag}.json")
    cuts = _read(cp if os.path.isfile(cp) else os.path.join(job, "transcript", "cuts.json"), "transcript/cuts.json")
    tp = os.path.join(job, "outputs", f"{name}{tag}.transcript.json")
    words = _read(tp if os.path.isfile(tp) else os.path.join(job, "outputs", f"{name}.transcript.json"),
                  f"outputs/{name}.transcript.json (the words every mid-clip switch is checked against)")
    placement = _read(os.path.join(job, "hf-graphics", f"placement{tag}.json"), "placement", required=False)
    return plan, face, cuts, words, placement


def _y(s, plan, face):
    try:
        return _clamped(s, _span_y(s, plan, face), None)
    except MissingInput:
        return None


def _how(t, cutl, ws, fps):
    fs = frame(t, fps)
    off = min((fs - frame(c, fps) for c in cutl), key=abs, default=None)
    if off == 0:
        return "on a V1 cut"
    if off is not None and abs(off) <= NEAR_CUT_FRAMES:
        return f"{off:+d} fr off a V1 cut (L-NEARCUT)"
    w = next((w for w in ws if 0 <= frame(w["start"], fps) - fs <= SWITCH_EARLY_MAX_FRAMES), None)
    return f"{frame(w['start'], fps) - fs} fr before '{w.get('text')}'" if w else "off the cuts and the words"


def _print_tables(job, plan, face, cuts, words, placement, findings):
    fps = _fps(plan)
    sp, cs, cutl, ws, rep = spans(plan, fps), cells(plan), v1_cuts(cuts, plan), _words(words), report(plan, fps)
    print(f"layout · {plan.get('job') or os.path.basename(os.path.abspath(job))}"
          f"{' · variant ' + plan['variant'] if plan.get('variant') else ''} · {rep['duration']:.2f} s @ {fps:.3f} fps · "
          f"{len(sp)} spans · {rep['switches']} switches")
    print(f"\n  {'#':>2}  {'from':>8}  {'to':>8}  {'dur':>5}  mode  {'cap y':>6}  cells")
    for i, s in enumerate(sp, 1):
        a, b, m, _ = s
        y = _y(s, plan, face)
        ids = [str(c.get("id")) for c in cs if float(c["start"]) < b - 1e-6 and float(c["end"]) > a + 1e-6]
        print(f"  {i:>2}  {a:8.3f}  {b:8.3f}  {b - a:5.2f}  {m:^4}  {'?' if y is None else y:>6}  {' '.join(ids)}")
    print(f"\n  {'share':<14}{'this job':>10}{'benchmark':>11}")
    for label, k, u in (("S split", "S", " %"), ("T tight", "T", " %"), ("W wide", "W", " %"), ("  bare W", "W_bare", " %"),
                        ("  O card", "O", " %"), ("F full", "F", " %"), ("face visible", "face", " %"),
                        ("graphics", "graphics", " %"), ("switches", "switches", ""), ("mean W", "mean_W", " s"),
                        ("mean T", "mean_T", " s")):
        print(f"  {label:<14}{str(rep[k]) + u:>10}{str(BENCHMARK[k]) + u:>11}")
    print("\n  switches")
    for t, m0, m1 in switches(sp):
        print(f"  {t:8.3f}  {m0}>{m1}  {_how(t, cutl, ws, fps)}")
    print("\n  rules")
    ask = any(str(c.get("role", "")).lower() == CTA_ROLE for c in cs)
    for code, level, meaning in RULES + (PLACEMENT_RULES if placement else []):
        n = [f for f in findings if f[0] == code]
        nf = sum(f[1] == "FAIL" for f in n)
        st = "ok" if not n else (f"{nf} FAIL" if nf else f"{len(n)} WARN")
        if code == "L-CTA" and not ask:
            st, meaning = "n/a", f"{meaning} (no `role: cta` cell: no ask to hold; tag the ask's cells if there is one)"
        print(f"  {code:<15}{level:<5} {st:<8} {meaning}")


def main(argv=None):
    for s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
        try:
            if (getattr(s, "encoding", "") or "").lower().replace("-", "") != "utf8":
                s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="the talking-head explainer's layout: spans, shares, switches and checks")
    ap.add_argument("job", help="projects/<job>")
    ap.add_argument("--check", action="store_true", help="print the findings only (the gate form)")
    ap.add_argument("--variant", metavar="NAME", help="compose the plan's variants.NAME (a second deliverable)")
    ap.add_argument("--json", metavar="OUT", help="write spans, switches, breaks, shares and findings here")
    a = ap.parse_args(argv)
    try:
        plan, face, cuts, words, placement = _inputs(a.job, a.variant)
        findings, unused = _check(plan, cuts, words, face, placement)
        tiled = not any(f[0] == "L-TILE" for f in findings)
        if tiled and not a.check:
            _print_tables(a.job, plan, face, cuts, words, placement, findings)
    except MissingInput as e:
        print(f"✗ missing input: {e}")
        return 2
    fails = [f for f in findings if f[1] == "FAIL"]
    warns = [f for f in findings if f[1] == "WARN"]
    if findings:
        print("layout findings" if a.check else "\n  findings")
    for code, level, t, msg in findings:
        print(f"  {'✗' if level == 'FAIL' else '⚠'} {code:<15}{t:8.3f}  {msg}")
    for d in (d for d in unused if not d.get("inherited")):
        print(f"  · layout_deviations {d.get('rule')}{' at ' + str(d['at']) if d.get('at') is not None else ''} "
              "matches no FAIL: drop it")
    if a.json:
        out = {"variant": a.variant, "findings": [dict(zip(("code", "level", "t", "message"), f)) for f in findings]}
        if tiled:
            sp = spans(plan)
            out.update(spans=[{"start": x, "end": y, "mode": m, "caption_y": _y(s, plan, face)} for s in sp
                              for x, y, m, _ in [s]],
                       switches=[{"t": t, "from": m0, "to": m1} for t, m0, m1 in switches(sp)],
                       breaks=breaks(plan, cuts), report=report(plan), benchmark=BENCHMARK)
        with open(a.json, "w", encoding="utf-8") as fp:
            json.dump(out, fp, indent=1)
        print(f"wrote {a.json}")
    print(f"\nlayout {'FAIL' if fails else 'PASS'}: {len(fails)} FAIL · {len(warns)} WARN"
          + (" (answer each WARN in the plan summary)" if warns else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
