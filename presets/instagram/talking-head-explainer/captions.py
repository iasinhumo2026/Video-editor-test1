#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""captions.py: the talking-head explainer's LOCKED caption layer, built and asserted ([captions-style.md] is the WHY).

Small white mono ALL CAPS in a see-through black box, 2-3 words a line, cut on and off with the picture, nothing
animated. Each frame's line sits where THAT frame's layout puts it (layout.py owns every height), a second voice is
yellow for its whole reply, and the text is the canonical transcript word for word. So a re-cut or a re-frame is a
re-run, never a hand edit. It runs from this folder and is never copied into a job: a job copy is how a fixed bug (the
sliver filter that deleted real words) stays alive on the next job.

  uv run presets/instagram/talking-head-explainer/captions.py projects/<job>              build, then the gate
  ... --ver b             write captions-alpha-b.mov (a placed render is never overwritten: Premiere half-stales it)
  ... --variant ad        the second deliverable: outputs/<job>.ad.transcript.json, transcript/cuts.ad.json and the
                          plan's variants.ad composed by layout.py -> captions-ad-alpha[-VER].mov, caption-sheet.ad.json
  ... --stills 6.0,20.5   current beside proposed on the raw frames -> review/caption-stills[-VER].png (a height change
                          is approved on stills before every line is re-rendered)
  ... --check <mov>       the gate on any render, against the job as it is NOW (a stale layer fails)
  ... --dry               the line table and the text gates only: nothing rendered or written

Exit 0 ok · 1 the gate failed (each failure named) · 2 bad input (the missing file, field or font named).

INPUTS (projects/<job>/):
  graphics-plan.json   `fps`; `duration`; the `layout` array and every graphic cell's in/out and `shot_cuts`
                       (layout.md § The plan contract, read through layout.py); the captions cell
                       {"id": "captions", "kind": "captions", "join": ["et cetera", "HyperFrames"], "y": {"wide": px,
                       "tight": px, "measured": "..."}}. `join` default ["et cetera"]: an entry with a space is a
                       spoken phrase kept on one line with a non-breaking space; an entry without one is a name the ASR
                       split, fused back into that one spelling. `variants.<NAME>` for --variant.
  transcript/cuts[.NAME].json            the EDL (`segments`: clip, start, end on the raw clock; `media` = a
                                         substituted file laid for that segment, read by --stills)
  outputs/<job>[.NAME].transcript.json   the canonical words (`words`: text, start, end, type) on the cut clock
  transcript/voices.json   the second voice, RAW clock, per clip, the WHOLE reply the cut keeps; no file = one voice:
                           {"spans": [{"clip": "<raw clip file>", "start": 243.9, "end": 249.75, "voice": "phone"}]}
                           (`clip` may be left out on a one-clip job; `voice` defaults to "second")
  face-frame.json      `collar` + `modes` (workflows/face-frame.py --modes): the W/O and T heights, and --stills
  hf-graphics/placement[.NAME].json   the renders on the timeline, which a build never overwrites

OUTPUTS: hf-graphics/captions/renders/captions[-NAME]-alpha[-VER].mov (ProRes 4444, yuva444p10le, BT.709 tagged,
straight alpha, at the plan fps, exactly round(duration x fps) frames) and hf-graphics/captions/caption-sheet[.NAME].json
({render, fps, font, font_warning, lines: [{text, start, end, y, voice}]}). Scratch frames in /tmp/video-editor/<job>/captions[-NAME]/.

THE GATE (after every build; --check on any render): captions == transcript (normalised characters, so a join is
free); no line spans a break; no line lit before its first word is spoken (early_lines: 0 frames of lead, a line
opened ON a boundary excepted, as build_lines opens it); per frame, the ink centre within INK_TOL px of that frame's
y; every line within MAX_W; no frame inside a spoken word uncaptioned. GATE_BAND is the split-frame strip no graphic ink may enter:
workflows/graphics-qa-short.py reads it from here. PIL is imported lazily, so the constants and the line builder
import without it.
"""
import argparse, bisect, contextlib, difflib, io, json, math, os, re, shutil, subprocess, sys, tempfile
from fractions import Fraction
from pathlib import Path

# Windows consoles/pipes default to cp1252, which can't encode the ✓/✗/⚠ glyphs in this script's status lines: a
# cosmetic print must never kill a pipeline step (it did once, 2026-08-13). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

HERE = Path(__file__).resolve().parent

# ── Values (captions-style.md § Values; workflows/test_talking_head_captions.py holds the two in parity) ────────────
W, H = 1080, 1920                  # the authoring frame; the lane fits it to the sequence
SIZE, TRACK = 44, 3                # px SF Mono Bold, tracking between characters (52 -> 44, "a little bit smaller")
WHITE = (255, 255, 255, 255)       # the creator
YELLOW = (255, 214, 10, 255)       # SECOND: a second voice, whole lines (sky blue sank into the blue-led frame, 2026-09-22)
BOX_FILL = (0, 0, 0, 230)          # BOX_ALPHA 90 % black: opaque sat on the picture like a slab, 80 % read too light
BOX_PAD_X, BOX_PAD_Y, BOX_R = 26, 14, 16   # PAD_X, PAD_Y, RADIUS: the box hugs its own line and never animates
BOX_ABOVE = 38.5                   # line y -> box top at 44 px (the box is 73 px: 34.5 below the line's y): draw_line
MAX_WORDS, MAX_CHARS = 3, 16       # flush triggers, not caps: a widow join can make four
MAX_W = 940                        # px of type, hard: 70 px inside each side, clear of the 60 px platform side bands
WIDOW_CHARS, WIDOW_GAP = 6, 0.4    # a short sentence-ending next word joins this line rather than stand alone
SLIVER = 0.20                      # s: a one-word line shorter than this is re-homed into a neighbour, NEVER deleted
GAP_CAP, HOLD_PAD = 1.0, 0.45      # s: hold to the next line within GAP_CAP, else HOLD_PAD past the last word
HANDOVER = 0.2                     # s: a line cut at a break mid-word hands over to the next line ON the break
Y_SPLIT = 960                      # the seam: a split's line sits ON it (every other height is layout.py's)
INK_TOL = 45                       # BAND_TOL px: the gate's per-frame tolerance on the ink centre
BAND_AIR = 13.5                    # the air a graphic keeps above the seam caption's box top
GATE_BAND = (math.floor(Y_SPLIT - BOX_ABOVE - BAND_AIR), Y_SPLIT)   # (908, 960)
SENT_END = (".", "?", "!")
JOIN_DEFAULT = ("et cetera",)
HOST = "host"                      # the creator's voice tag; any other tag is a second voice
EPS = 1e-6

FONT_SF = "/System/Library/Fonts/SFNSMono.ttf"   # the look: its Bold named instance
# The bundled stand-in where SF Mono is not installed (Windows, Linux; 2026-09-27): IBM Plex Mono Bold (OFL), its cap
# height SF Mono Bold's exactly and its advance 60 against 62 per 100 px, so it is drawn 62/60 larger: every line is SF
# Mono's width and the box SF Mono's size. [(path under the repo, size factor)]
BUNDLED_MONO = (("assets/fonts/IBMPlexMono-Bold.ttf", 62 / 60),)
SF_METRICS = (43, 10)              # SF Mono Bold's (ascent, descent) at 44 px, measured: the box draw_line sizes from them
FALLBACK_MONO = (                  # a different face: the build runs, loudly, and the sheet records it
    ("/System/Library/Fonts/Menlo.ttc", 1),
    (os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "consolab.ttf"), 0),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0),
    ("/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf", 0),
)
# the PNG -> ProRes conversion, BT.709 and tagged (render; workflows/test_alpha_colour.py reads the colours back as 709)
ALPHA_709 = ("scale=out_color_matrix=bt709:out_range=tv,"
             "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv")


class BadInput(Exception):
    """Exit 2: a missing file, field or font, named."""


# ── inputs ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _read_json(path, what):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise BadInput(f"{what} is missing: {path}")
    except ValueError as e:
        raise BadInput(f"{what} is not valid JSON ({path}): {e}")


def _paths(job, variant):
    """(transcript, EDL) of the organic or of a variant."""
    job = Path(job); tag = f".{variant}" if variant else ""
    return job / "outputs" / f"{job.name}{tag}.transcript.json", job / "transcript" / f"cuts{tag}.json"


def rate_of(plan):
    """The plan fps as an exact fraction (24000/1001), for the frame maths and for ffmpeg."""
    v = plan.get("fps")
    if v in (None, ""):
        raise BadInput("graphics-plan.json has no `fps` (the timeline rate, e.g. \"24000/1001\")")
    try:
        return Fraction(str(v)).limit_denominator(1_000_000)
    except (ValueError, ZeroDivisionError):
        raise BadInput(f"graphics-plan.json `fps` {v!r} is not a rate")


def captions_cell(plan):
    return next((b for b in plan.get("beats") or [] if b.get("id") == "captions" or b.get("kind") == "captions"), {})


def load_voices(job):
    """transcript/voices.json -> [(clip or None, raw start, raw end, voice)]."""
    p = Path(job) / "transcript" / "voices.json"
    if not p.exists():
        return []
    data = _read_json(p, "transcript/voices.json")
    spans = data.get("spans") if isinstance(data, dict) else None
    if not isinstance(spans, list):
        raise BadInput("transcript/voices.json has no `spans` list")
    out = []
    for i, s in enumerate(spans):
        if not isinstance(s, dict) or s.get("start") is None or s.get("end") is None:
            raise BadInput(f"transcript/voices.json spans[{i}] needs `start` and `end` (raw-clock seconds)")
        out.append((os.path.basename(s["clip"]) if s.get("clip") else None, float(s["start"]), float(s["end"]),
                    str(s.get("voice") or "second")))
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9$%]", "", s.lower())


def load_words(job, variant=None, plan=None):
    """-> (words, duration). Every canonical transcript word in order, mapped through the EDL onto the cut clock the
    transcript is written on (export-transcript.py's: the kept segments laid end to end):
      t      the text as written, a `join` unit fused into one token (the builder never re-spells: names are fixed
             upstream in the corrections, then reapply-corrections.sh)
      start, end   cut-clock s · clip  the EDL segment index · cend  that segment's end (a V1 cut)
      raw    the raw-clock time of the word's midpoint · voice  HOST, or the second voice's tag from voices.json
    Nothing is dropped: the gate compares the lines back to this list."""
    tpath, cpath = _paths(job, variant)
    tr = _read_json(tpath, f"the canonical transcript ({tpath.name})")
    tr = tr.get("words") if isinstance(tr, dict) else tr
    if not isinstance(tr, list):
        raise BadInput(f"{tpath.name} has no `words` list")
    segs = _read_json(cpath, f"the EDL ({cpath.name})").get("segments")
    if not segs:
        raise BadInput(f"{cpath.name} has no `segments`")
    spans, t = [], 0.0
    for i, s in enumerate(segs):
        for k in ("clip", "start", "end"):
            if s.get(k) is None:
                raise BadInput(f"{cpath.name} segments[{i}] has no `{k}`")
        d = float(s["end"]) - float(s["start"])
        if d > 0:
            spans.append((t, t + d, float(s["start"]), os.path.basename(s["clip"]), i))
            t += d
    if not spans:
        raise BadInput(f"{cpath.name}: every segment is empty")
    voices = load_voices(job)
    # the one voices.json rule every reader holds (workflows/voice-gain.py, sfx-plan.py, audio-polish.py --lift, this):
    # a span's clip is a raw the job's cuts.json cuts from (a variant's EDL, or the organic's), never merely a file in
    # raw/ (on the multi-section layout the parent's raw/ holds every section's raw), matched case-insensitively
    # (APFS); a span with no clip is refused on an EDL cut from several raws
    clips = {x[3].lower() for x in spans}
    raws = set(clips)
    if variant:
        organic = _paths(job, None)[1]
        if organic.exists():
            raws |= {os.path.basename(s.get("clip") or "").lower()
                     for s in _read_json(organic, organic.name).get("segments") or []} - {""}
    for c, s0, e0, _ in voices:
        if c is None and len(clips) > 1:
            raise BadInput(f"transcript/voices.json: a span with no `clip` ({s0:.3f}-{e0:.3f}s) on an EDL cut from "
                           f"{len(clips)} raws: name its raw")
        if c is not None and c.lower() not in raws:
            raise BadInput(f"transcript/voices.json: a span names clip {c!r}, which {cpath.name} does not cut from "
                           f"({', '.join(sorted(raws))})")
    words = []
    for w in tr:
        if w.get("type", "word") != "word" or not str(w.get("text", "")).strip():
            continue
        if w.get("start") is None or w.get("end") is None:
            raise BadInput(f"{tpath.name}: the word {w.get('text')!r} has no start/end")
        mid = (float(w["start"]) + float(w["end"])) / 2
        a, b, r0, clip, idx = next((x for x in spans if x[0] - EPS <= mid < x[1] + EPS), spans[-1])
        raw = r0 + (mid - a)
        voice = next((v for c, s, e, v in voices if (c is None or c.lower() == clip.lower()) and s <= raw < e), HOST)
        words.append({"t": str(w["text"]).strip(), "start": float(w["start"]), "end": float(w["end"]), "clip": idx,
                      "cend": b, "raw": raw, "voice": voice})
    plan = plan if plan is not None else _read_json(Path(job) / "graphics-plan.json", "graphics-plan.json")
    return join_units(words, captions_cell(plan).get("join") or JOIN_DEFAULT), t


def join_units(words, units):
    """Keep each spoken unit on one line, so no break can fall inside it. "et cetera" (a phrase, as a string or a token
    list) becomes one token joined on a non-breaking space; "HyperFrames" (a name the ASR split as "Hyper frames") fuses
    the tokens that spell it into that one spelling, keeping the outer punctuation. Never across a V1 cut or a voice
    change."""
    units = [u.split() if isinstance(u, str) else [str(x) for x in u] for u in units]
    phrases = [[_norm(x) for x in u] for u in units if len(u) > 1]
    fused = {_norm(u[0]): u[0].strip() for u in units if len(u) == 1 and _norm(u[0])}
    out, i = [], 0
    while i < len(words):
        hit = None
        for p in phrases:
            g = words[i:i + len(p)]
            if len(g) == len(p) and [_norm(w["t"]) for w in g] == p:
                hit = (g, "\u00a0".join(w["t"] for w in g)); break
        for k in (2, 3, 4) if hit is None else ():
            g = words[i:i + k]
            if len(g) == k and "".join(_norm(w["t"]) for w in g) in fused:
                pre, _, _ = re.match(r"^(\W*)(.*?)(\W*)$", g[0]["t"], re.S).groups()
                post = re.match(r"^(\W*)(.*?)(\W*)$", g[-1]["t"], re.S).group(3)
                hit = (g, pre + fused["".join(_norm(w["t"]) for w in g)] + post); break
        if hit and len({(w["clip"], w["voice"]) for w in hit[0]}) == 1:
            out.append(dict(hit[0][0], t=hit[1], end=hit[0][-1]["end"])); i += len(hit[0])
        else:
            out.append(words[i]); i += 1
    return out


# ── the layout (layout.py owns every framing number: the heights, the breaks, the footage transforms) ──────────────
class Frame:
    """The layout as the caption layer needs it: y_at(t) the line centre at cut-clock t (per frame, ask at the frame's
    midpoint); breaks the times a line may never straddle (V1 cuts, layout edges, graphic edges, shot_cuts), on the
    frame grid; mode_at(t) 'S' 'T' 'W' 'F' 'O'; footage(img, mode) the 1080x1920 frame as that layout shows it."""

    def __init__(self, y_at, breaks, mode_at=None, footage=None):
        self._y, self.breaks, self.mode_at, self.footage = y_at, sorted(set(breaks)), mode_at, footage
        self._memo = {}

    def y_at(self, t):
        k = round(t * 1e6)
        if k not in self._memo:
            self._memo[k] = self._y(t)
        return self._memo[k]

    def y_frame(self, f, fps):
        return int(round(self.y_at((f + 0.5) / fps)))


def _layout_module():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import layout                                                # this folder's executable twin of layout.md
    return layout


def resolve_plan(job, variant=None):
    """graphics-plan.json, composed by layout.compose_variant for a variant."""
    plan = _read_json(Path(job) / "graphics-plan.json", "graphics-plan.json")
    if variant:
        L = _layout_module()
        try:
            plan = L.compose_variant(plan, variant)
        except L.MissingInput as e:
            raise BadInput(str(e))
    return plan


def load_frame(job, variant=None, plan=None):
    """The job's Frame, resolved through layout.py (the plan composed for a variant unless one is passed)."""
    L = _layout_module()
    plan = plan if plan is not None else resolve_plan(job, variant)
    cuts = _read_json(_paths(job, variant)[1], "the EDL")
    fp = Path(job) / "face-frame.json"
    face = _read_json(fp, "face-frame.json") if fp.exists() else None
    try:
        sp = L.spans(plan)                                        # L-TILE first: nothing is placeable on a broken map
        brk = L.breaks(plan, cuts)
    except (L.MissingInput, L.LayoutError) as e:
        raise BadInput(f"the plan's layout: {e}")
    fps = L.parse_fps(plan.get("fps"))
    for a, b, m, cy in sp:                                        # L-CAPY, held here too: an F left on the seam by default
        if m == "F" and cy is None and not any(                   # would put the caption on the full-screen's content
                c.get("seam_clear") and L.frame(c.get("start", 0), fps) < L.frame(b, fps)
                and L.frame(c.get("end", 0), fps) > L.frame(a, fps) for c in L.cells(plan)):
            raise BadInput(f"the F span {a:.3f}-{b:.3f} has no caption line: give its layout row `ui_bottom` (the "
                           f"capture's bottom UI edge; the line goes {L.CAPTION_UI:g} px under it) or `caption_y`, or mark "
                           "the cell over it \"seam_clear\": true (layout.md § 12, L-CAPY)")

    def y_at(t):
        try:
            return L.caption_y_at(t, plan, face)
        except L.MissingInput as e:
            raise BadInput(f"{e} (the caption height of the {L.mode_at(t, plan)} layout at {t:.3f} s needs it)")

    def footage(img, mode):
        from PIL import Image
        try:
            m = L.modes(face)["W" if mode == "O" else mode]
        except L.MissingInput as e:
            raise BadInput(str(e))
        s = m["scale"]; sw, sh = round(img.width * s), round(img.height * s)   # the fitted source, whole
        out = Image.new("RGB", (W, H), (0, 0, 0))
        out.paste(img.resize((sw, sh)), (round(m["centre"][0] * W - sw / 2), round(m["centre"][1] * H - sh / 2)))
        return out

    return Frame(y_at, brk, lambda t: L.mode_at(t, plan), footage)


# ── the lines (captions-style.md § 5) ──────────────────────────────────────────────────────────────────────────────
def lead_reach(fps):
    """s: the furthest a line may open before its first word, and only ON a boundary (build_lines' start and
    handover): layout.md's 0-2 frame switch lead plus one frame, or HANDOVER, whichever is larger."""
    return max((_layout_module().SWITCH_EARLY_MAX_FRAMES + 1) / fps, HANDOVER)


def _down(t, fps):
    """t's frame, snapped DOWN (a value within 1e-3 frame of a grid line is on it)."""
    x = t * fps; r = round(x)
    return r if abs(x - r) < 1e-3 else math.floor(x)


def boundaries(words, breaks, fps):
    """(all, soft) boundary times on the frame grid: the breaks plus every V1 cut (a segment end, snapped the way
    layout.breaks snaps it); `soft` are the ones no V1 cut sits on, where a word's side is decided by its onset."""
    cuts = {round(w["cend"] * fps) for w in words}
    fr = {round(b * fps) for b in breaks} | cuts
    return [f / fps for f in sorted(fr)], [f / fps for f in sorted(fr - cuts)]


def build_lines(words, breaks, measure, fps):
    """words (load_words) -> lines [{words, text, start, end, f0, f1, voice}]; a line covers frames [f0, f1), and
    start/end are those frames in seconds.
      flush     at a change of voice, at every boundary (a V1 cut, or a break a word's onset is past or within one
                frame of), on . ? !, at MAX_WORDS or MAX_CHARS, and before a word that would pass MAX_W
      widow     a short sentence-ending next word (same voice, within WIDOW_GAP, same side of every boundary) joins
                this line instead of standing alone; the width guard still wins
      re-home   a one-word line under SLIVER joins the previous line (unless that closed a sentence), else the next:
                same voice, width permitting, never across a boundary. Otherwise it stays. It is NEVER deleted
      start     a line whose first word starts within a frame of a boundary, either side, starts ON it; after a SOFT
                boundary (a layout edge, a cell edge or a shot cut: never a V1 cut) it starts on it from further out,
                LEAD_IN (the larger of layout.md's 0-2 frame switch lead plus one frame, and HANDOVER): a graphic or
                layout cut lands 0-2 frames before its word, so the incoming shot's first frames are never bare
      hold      to the next line if it starts within GAP_CAP, else HOLD_PAD past the last word; never past the next
                line, the word's V1 cut or a break
      handover  a line cut at a boundary while its last word is still spoken hands over: the next line starts there
                if it would start within HANDOVER
      frames    a start takes the frame its moment falls in, an end snaps DOWN to the grid, and a line held to the next
                ends on that line's first frame, so two lines never blink apart"""
    F = fps
    bounds, soft = boundaries(words, breaks, F)
    cut_of = lambda w: round(w["cend"] * F) / F

    def side(w):
        return bisect.bisect_left(soft, w["start"] + 1 / F - EPS)

    def between(a, b):
        return a["clip"] != b["clip"] or side(a) != side(b)

    def width(ws):
        return measure(" ".join(x["t"] for x in ws))

    out, cur = [], []

    def flush():
        if cur:
            out.append({"words": list(cur), "start": cur[0]["start"], "end": cur[-1]["end"], "voice": cur[0]["voice"]})
            cur.clear()

    for i, w in enumerate(words):
        if cur and (cur[-1]["voice"] != w["voice"] or between(cur[-1], w) or width(cur + [w]) > MAX_W):
            flush()
        cur.append(w)
        ends = w["t"].rstrip().endswith(SENT_END)
        nxt = words[i + 1] if i + 1 < len(words) else None
        widow = (nxt is not None and not ends and nxt["voice"] == w["voice"] and not between(w, nxt)
                 and nxt["t"].rstrip().endswith(SENT_END) and len(nxt["t"]) <= WIDOW_CHARS
                 and nxt["start"] - w["end"] < WIDOW_GAP and len(cur) <= MAX_WORDS)
        if ends or ((len(cur) >= MAX_WORDS or len(" ".join(x["t"] for x in cur)) >= MAX_CHARS) and not widow):
            flush()
    flush()

    i = 0
    while i < len(out):
        ln = out[i]
        if len(ln["words"]) == 1 and ln["end"] - ln["start"] < SLIVER - EPS:    # "under 0.20 s", float-safe
            w = ln["words"][0]
            prv = out[i - 1] if i else None
            nxt = out[i + 1] if i + 1 < len(out) else None
            if (prv and prv["voice"] == ln["voice"] and not prv["words"][-1]["t"].rstrip().endswith(SENT_END)
                    and not between(prv["words"][-1], w) and width(prv["words"] + ln["words"]) <= MAX_W):
                prv["words"] += ln["words"]; prv["end"] = ln["end"]; del out[i]; continue
            if (nxt and nxt["voice"] == ln["voice"] and not between(w, nxt["words"][0])
                    and width(ln["words"] + nxt["words"]) <= MAX_W):
                nxt["words"] = ln["words"] + nxt["words"]; nxt["start"] = ln["start"]; del out[i]; continue
        i += 1

    soft_set = set(soft)
    lead_in = lead_reach(F)
    for k, ln in enumerate(out):                                 # a first word just past a boundary starts ON it
        for b in bounds:
            reach = lead_in if b in soft_set else 1 / F          # a soft cut leads its word by 0-2 frames (layout.md § 4)
            first = k == 0 or out[k - 1]["start"] < b - EPS      # only the first line after the boundary
            if first and 0 < ln["start"] - b < reach - EPS:      # strictly within the reach, float-safe
                ln["start"] = b
    for i, ln in enumerate(out):
        nxt = out[i + 1]["start"] if i + 1 < len(out) else None
        ln["end"] = nxt if nxt is not None and nxt - ln["end"] <= GAP_CAP else ln["end"] + HOLD_PAD
        if nxt is not None:
            ln["end"] = min(ln["end"], nxt)
        ln["end"] = min(ln["end"], cut_of(ln["words"][-1]))
        for b in bounds:
            if ln["start"] < b - EPS and ln["end"] > b + EPS:
                if b - ln["start"] < 1 / F - EPS:                # a first word just before a boundary starts ON it
                    ln["start"] = b
                else:
                    ln["end"] = b
        ln["held"] = nxt is not None and abs(ln["end"] - nxt) < EPS
        if nxt is not None and ln["end"] < ln["words"][-1]["end"] and out[i + 1]["start"] - ln["end"] < HANDOVER:
            out[i + 1]["start"] = ln["end"]

    for ln in out:
        ln["f0"] = math.ceil(ln["start"] * F - 0.5 - 1e-9)      # the frame whose midpoint is the first at/after start
    for i, ln in enumerate(out):
        nx = out[i + 1] if i + 1 < len(out) else None
        f1 = nx["f0"] if ln.pop("held") else _down(ln["end"], F)
        ln["f1"] = max(min(f1, nx["f0"]) if nx else f1, ln["f0"] + 1)
        if nx and nx["f0"] < ln["f1"]:                           # a sub-frame line still shows: the next one waits a frame
            nx["f0"] = ln["f1"]
    for ln in out:
        ln["start"], ln["end"] = ln["f0"] / F, ln["f1"] / F
        ln["text"] = " ".join(w["t"] for w in ln["words"]).upper()
        ln["plain"], k = [], 0                                    # the line's tokens a phrase "except" keeps white
        for w in ln["words"]:
            ln["plain"] += [k + j for j in sorted(w.get("plain", ()))]
            k += len(w["t"].split(" "))
    return out


# ── drawing (PIL, lazily) ──────────────────────────────────────────────────────────────────────────────────────────
def load_font():
    """-> (font, label, warning). SF Mono Bold; else an approved bundled mono; else Menlo / Consolas / DejaVu Sans Mono
    Bold with a loud warning, written into the sheet too: a different face moves every width."""
    from PIL import ImageFont
    if os.path.exists(FONT_SF):
        f = ImageFont.truetype(FONT_SF, SIZE)
        try:
            f.set_variation_by_name("Bold")
            return f, f"{FONT_SF} (Bold)", None
        except Exception as e:                                   # an SF Mono without the named instance
            return f, FONT_SF, f"SF Mono has no Bold instance ({e}): captions drawn in its default weight, NOT the locked look"
    repo = next((p for p in HERE.parents if (p / "assets" / "fonts").is_dir()), None)
    for rel, k in BUNDLED_MONO:
        if repo and (repo / rel).exists():
            print(f"[captions] note: SF Mono is not on this machine: the bundled stand-in {Path(rel).name}, drawn {k:.4f}x "
                  "to SF Mono Bold's advance (captions-style.md § 1)")
            class StandIn(ImageFont.FreeTypeFont):
                # the box is sized from ascent + descent (draw_line): SF Mono's, scaled to SIZE, so the stand-in's box
                # is SF Mono's box (73 px at 44), not its own (Plex's metrics would make it 80)
                def getmetrics(self):
                    return round(SF_METRICS[0] * SIZE / 44), round(SF_METRICS[1] * SIZE / 44)
            return StandIn(str(repo / rel), SIZE * k), f"{repo / rel} (the SF Mono stand-in, x{k:.4f})", None
    for path, idx in FALLBACK_MONO:
        if os.path.exists(path):
            return (ImageFont.truetype(path, SIZE, index=idx), f"{path}#{idx}",
                    f"SF Mono is not on this machine: captions drawn in {os.path.basename(path)}, NOT the locked look")
    raise BadInput(f"no caption font: {FONT_SF} is missing, and so is every fallback mono (Menlo, Consolas, DejaVu Sans Mono Bold)")


def _layout_x(font, text):
    """(width, [(x offset, token)]) of the drawn line: each word's characters carry the tracking between them, and a
    word ends on its last glyph's advance before the space (the approved draw: 3 px tighter a space than tracking
    every character). Measured per character from the resolved font: no mono assumption."""
    toks = text.upper().split(" ")
    space = font.getlength(" ") + TRACK
    x, out = 0.0, []
    for i, tok in enumerate(toks):
        out.append((x, tok))
        x += (sum(font.getlength(ch) + TRACK for ch in tok) - TRACK if tok else 0.0) + (space if i < len(toks) - 1 else 0.0)
    return x, out


def make_measure(font):
    """The drawn width of a line in px of type, the number the MAX_W guard and the gate hold to."""
    return lambda text: _layout_x(font, text)[0] if text else 0.0


# The approved box is that alpha as PREMIERE composites it, in linear light: over a white page it reads gray 89 (about
# 65 % effective). A straight-alpha compositor (the chat-only ffmpeg overlay) blends in gamma space and reads gray 25 over
# the same page. --straight-alpha draws the box at the alpha whose straight blend matches the linear one for black:
# 1 - (1 - 0.9) ** (1 / 2.2), about 65 % (captions-style.md § 1).
STRAIGHT_BOX_ALPHA = round(255 * (1 - (1 - BOX_FILL[3] / 255) ** (1 / 2.2)))
_box_alpha = BOX_FILL[3]


def draw_line(text, y, colour, font, plain=()):
    """One caption line as a 1080x1920 RGBA frame, centred on x, on y: pixel for pixel the approved draw. base = y +
    (asc - desc)/2 - 4; the box runs base - asc - BOX_PAD_Y + 6 .. base + desc + BOX_PAD_Y - 2 (the caps' optical
    centre), so at 44 px SF Mono Bold it is 73 px tall with its top BOX_ABOVE over y, BOX_PAD_X each side."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    total, toks = _layout_x(font, text)
    asc, desc = font.getmetrics()
    base = y + (asc - desc) / 2 - 4
    x0 = (W - total) / 2
    d.rounded_rectangle((x0 - BOX_PAD_X, base - asc - BOX_PAD_Y + 6, x0 + total + BOX_PAD_X, base + desc + BOX_PAD_Y - 2),
                        radius=BOX_R, fill=BOX_FILL[:3] + (_box_alpha,))
    for n, (off, tok) in enumerate(toks):
        x = x0 + off
        ink = colour if n in plain else _highlight_of(tok, colour)
        for ch in tok:
            d.text((x, base), ch, font=font, fill=ink, anchor="ls")
            x += font.getlength(ch) + TRACK
    return img


# A sponsor's contract can require its brand coloured in the captions ("highlight Whop in orange", the Whop brief,
# 2026-10-14). Opt-in per job on the plan's captions cell, "highlight": {"words": [...], "color": "#RRGGBB", "except": [...]}: the
# host's tokens whose letters START with a listed word take that colour (WHOP, WHOP'S), except a token listed whole in
# "except" (WHOP.COM stays white: you, 2026-10-15). A multi-word "except" entry is a PHRASE: its last word stays white
# wherever the transcript says the whole phrase in order, across caption lines ("comment whop": the comment ask's
# keyword stays white, you 2026-10-15). No cell key, no change: the house look emphasises no word (captions-style.md § 1).
_highlight = {}
_highlight_not = set()          # tokens a highlight word starts but must not light ("except": a URL like whop.com)


def _alnum(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


def mark_plain(words, phrases):
    """Each phrase's LAST word, wherever the words say the whole phrase in order, is stamped on its word as
    "plain" (its token index inside the word's text): draw_line keeps it white. -> the number of words stamped."""
    toks = [(i, k, _alnum(x)) for i, w in enumerate(words) for k, x in enumerate(w["t"].split(" "))]
    toks = [t for t in toks if t[2]]
    n = 0
    for ph in phrases:
        p = [_alnum(x) for x in ph.split() if _alnum(x)]
        for j in range(len(toks) - len(p) + 1):
            if p and [t[2] for t in toks[j:j + len(p)]] == p:
                i, k, _ = toks[j + len(p) - 1]
                words[i].setdefault("plain", set()).add(k)
                n += 1
    return n


def _highlight_of(tok, colour):
    if not _highlight or colour != WHITE:
        return colour
    letters = "".join(ch for ch in tok.lower() if ch.isalnum())
    if letters in _highlight_not:
        return colour
    return next((c for w, c in _highlight.items() if letters.startswith(w)), colour)


def colour_of(voice):
    return WHITE if voice == HOST else YELLOW


# ── the gate ───────────────────────────────────────────────────────────────────────────────────────────────────────
def check_script(words, lines):
    """captions == transcript on normalised characters (a join, the case and punctuation are free) -> the first 10
    differences of a token ndiff, or [] when they match."""
    script = [_norm(x) for w in words for x in w["t"].replace("\u00a0", " ").split() if _norm(x)]
    caps = [_norm(x) for ln in lines for x in ln["text"].replace("\u00a0", " ").split() if _norm(x)]
    if "".join(script) == "".join(caps):
        return []
    return [x.strip() for x in difflib.ndiff(script, caps) if x[:1] in "+-"][:10]


def check_spans(lines, breaks, words, fps):
    """-> [(start, end, boundary, text)] for every line that covers the frames on both sides of a boundary."""
    bounds, _ = boundaries(words, breaks, fps)
    return [(round(ln["start"], 3), round(ln["end"], 3), round(b, 3), ln["text"]) for ln in lines for b in bounds
            if ln["f0"] < round(b * fps) < ln["f1"]]


def early_lines(words, lines, breaks, fps):
    """-> [(text, first lit frame, its first word's frame)] for every line lit before its first word is spoken (0
    frames of lead). A word's frame is the first whose midpoint is at or after its start, the rule f0 is lit by; the one
    exception is a line opened ON a boundary (a V1 cut or a break), at most lead_reach() and the word's own rounding
    frame before its word. Each line's first word is found by its normalised characters, so a sheet's lines (no words
    attached) are read the same way as a fresh build's."""
    bounds, _ = boundaries(words, breaks, fps)
    on = {round(b * fps) for b in bounds}
    script = [(_norm(x), w) for w in words for x in w["t"].replace("\u00a0", " ").split() if _norm(x)]
    out, i = [], 0
    for ln in lines:
        if i >= len(script):
            break
        w = script[i][1]
        n = len("".join(_norm(x) for x in ln["text"].replace("\u00a0", " ").split()))
        while n > 0 and i < len(script):
            n -= len(script[i][0]); i += 1
        wf = math.ceil(w["start"] * fps - 0.5 - 1e-9)
        if ln["f0"] < wf and not (ln["f0"] in on and (wf - ln["f0"]) / fps <= lead_reach(fps) + 1 / fps + EPS):
            out.append((ln["text"], ln["f0"], wf))
    return out


def ink_per_frame(mov):
    """ffmpeg alphaextract,bbox -> ({frame: (x1, x2, y1, y2)} for every inked frame, frames read)."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "info", "-i", str(mov), "-vf", "alphaextract,bbox=min_val=40",
                        "-f", "null", "-"], capture_output=True, text=True)
    ink, n = {}, 0
    for m in re.finditer(r"Parsed_bbox\S* @ \S+\] n:(\d+) [^\n]*", r.stderr):
        f = int(m.group(1)); n = max(n, f + 1)
        c = re.search(r"x1:(\d+) x2:(\d+) y1:(\d+) y2:(\d+)", m.group(0))
        if c:
            ink[f] = tuple(int(v) for v in c.groups())
    if r.returncode or not n:
        raise BadInput(f"ffmpeg could not read {mov}: {r.stderr.strip()[-300:]}")
    return ink, n


def gate(words, lines, frame, fps, measure, mov=None, nframes=None):
    """-> the failures, named; [] = the layer is right."""
    fails = []
    d = check_script(words, lines)
    if d:
        fails.append(f"captions != transcript (first differences, - script + captions): {d}")
    sp = check_spans(lines, frame.breaks, words, fps)
    if sp:
        fails.append(f"{len(sp)} line(s) span a break or a V1 cut (start, end, boundary, text): {sp[:6]}")
    early = early_lines(words, lines, frame.breaks, fps)
    if early:
        fails.append(f"{len(early)} line(s) lit before their first word is spoken (text, first lit frame, the word's "
                     f"frame): {early[:6]}")
    wide = [(ln["text"], round(measure(ln["text"]))) for ln in lines if measure(ln["text"]) > MAX_W + EPS]
    if wide:
        fails.append(f"{len(wide)} line(s) wider than {MAX_W} px: {wide[:6]}")
    if mov is None:
        return fails
    ink, n = ink_per_frame(mov)
    if nframes is not None and n != nframes:
        fails.append(f"{Path(mov).name} has {n} frames, the cut needs {nframes}")
    off = [(f, round((y1 + y2) / 2), frame.y_frame(f, fps)) for f, (x1, x2, y1, y2) in sorted(ink.items())
           if abs((y1 + y2) / 2 - frame.y_frame(f, fps)) > INK_TOL]
    if off:
        fails.append(f"{len(off)} frame(s) with the ink off their layout's y by more than {INK_TOL} px "
                     f"(frame, ink centre, want): {off[:8]}")
    broad = sorted(f for f, (x1, x2, _, _) in ink.items() if x2 - x1 + 1 > MAX_W + 2 * BOX_PAD_X + 2)
    if broad:
        fails.append(f"{len(broad)} frame(s) carry a box wider than {MAX_W} px of type (first: frame {broad[0]})")
    bare = sorted({f for w in words for f in range(math.ceil(w["start"] * fps - 0.5), math.ceil(w["end"] * fps - 0.5))
                   if 0 <= f < n and f not in ink})
    if bare:
        fails.append(f"{len(bare)} frame(s) inside a spoken word carry no caption (first: {bare[:8]})")
    return fails


def sheet_path(job, variant):
    return Path(job) / "hf-graphics" / "captions" / (f"caption-sheet.{variant}.json" if variant else "caption-sheet.json")


def read_sheet(job, variant):
    """-> (render name or None, lines) of the caption sheet; a pre-2026-09-23 sheet is a bare list."""
    p = sheet_path(job, variant)
    if not p.exists():
        return None, None
    s = _read_json(p, p.name)
    return (None, s) if isinstance(s, list) else (s.get("render"), s.get("lines") or [])


def stale(built, sheet_lines, fps):
    """-> the first differences between a fresh build and the render's sheet (text, first frame, last frame, voice)."""
    key = lambda ln: (ln["text"], round(ln["start"] * fps), round(ln["end"] * fps), ln.get("voice", HOST))
    a, b = [key(x) for x in built], [key(x) for x in sheet_lines]
    return [] if a == b else [x.strip() for x in difflib.ndiff([str(k) for k in b], [str(k) for k in a]) if x[:1] in "+-"][:6]


# ── render ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def render(lines, frame, fps, nframes, font, work, out):
    """One PNG per (line, y) plus a blank, laid as a numbered sequence (frame f = file f, a hard link, else a copy: no
    symlinks, so it runs on Windows) read at the plan rate, encoded to ProRes 4444 straight alpha with an exact frame
    count. Every frame takes the y of its own layout, so a line moves on the frame the footage reframes. Never an
    ffconcat list with per-image durations: it inherits image2's 1/25 s time base, so its edges snapped to a 40 ms grid
    and at 29.97 a line showed a frame late or early wherever the snap passed half a frame (2026-09-27)."""
    from PIL import Image
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    blank = os.path.join(work, "blank.png")
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    src = [blank] * nframes
    for i, ln in enumerate(lines):
        pngs = {}
        for f in range(max(0, ln["f0"]), min(nframes, ln["f1"])):
            y = frame.y_frame(f, fps)
            if y not in pngs:
                pngs[y] = os.path.join(work, f"cap_{i:04d}_{y}.png")
                draw_line(ln["text"], y, colour_of(ln["voice"]), font, ln.get("plain", ())).save(pngs[y])
            src[f] = pngs[y]
    seq = os.path.join(work, "seq")
    os.makedirs(seq)
    for f, p in enumerate(src):
        q = os.path.join(seq, f"{f:07d}.png")
        try:
            os.link(p, q)
        except OSError:                                          # a volume without hard links
            shutil.copyfile(p, q)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    rate = Fraction(fps).limit_denominator(100000)                # 23.976... -> 24000/1001
    # BT.709 matrix, tagged: ffmpeg's default RGB->YUV is BT.601 with no tags, and an editing app reads untagged HD as
    # 709, so the second voice's yellow landed #ffce01 (2026-10-13). An explicit scale, never bare tag flags (older
    # ffmpeg only tags with those and the values stay 601).
    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-f", "image2", "-framerate", str(rate),
                    "-start_number", "0", "-i", Path(seq, "%07d.png").as_posix(), "-frames:v", str(nframes),
                    "-vf", ALPHA_709, "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-an", str(out)],
                   check=True)
    shutil.rmtree(work, ignore_errors=True)
    with contextlib.suppress(OSError):                            # the job's scratch folder, once nothing else is in it
        os.rmdir(os.path.dirname(work))


def placed_files(job, variant=None):
    p = Path(job) / "hf-graphics" / (f"placement.{variant}.json" if variant else "placement.json")
    rows = _read_json(p, p.name) if p.exists() else []
    rows = rows if isinstance(rows, list) else rows.get("rows", [])
    return {os.path.realpath(r["file"]) for r in rows if isinstance(r, dict) and r.get("file")}


def out_path(job, variant, ver):
    return (Path(job) / "hf-graphics" / "captions" / "renders" /
            f"captions{'-' + variant if variant else ''}-alpha{'-' + ver if ver else ''}.mov")


def next_free_ver(job, variant, placed):
    for c in "abcdefghijklmnopqrstuvwxyz":
        p = out_path(job, variant, c)
        if not p.exists() and os.path.realpath(p) not in placed:
            return c
    return "<a new name>"


def write_sheet(job, variant, lines, frame, fps, font_label, warn, mov):
    p = sheet_path(job, variant)
    os.makedirs(p.parent, exist_ok=True)
    sheet = {"render": Path(mov).name, "fps": fps, "font": font_label, "font_warning": warn,
             "lines": [{"text": ln["text"], "start": round(ln["start"], 6), "end": round(ln["end"], 6),
                        "y": frame.y_frame(ln["f0"], fps), "voice": ln["voice"]} for ln in lines]}
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(sheet, fh, indent=1, ensure_ascii=False)
    return p


def print_table(lines, frame, fps):
    for ln in lines:
        v = "" if ln["voice"] == HOST else ln["voice"][:7]
        print(f"  {ln['start']:8.3f}-{ln['end']:8.3f}  y{frame.y_frame(ln['f0'], fps):<5}{v:8}{ln['text']}")


# ── stills: a height change is approved on stills, current beside proposed ─────────────────────────────────────────
def raw_frame(job, variant, t):
    """The source frame under cut-clock t (a `media` segment reads its substitute file), fitted to the 1920 frame height
    (a landscape raw keeps its full width: its W is a face-centred window onto it, face-frame.json `modes`)."""
    from PIL import Image
    segs = [s for s in _read_json(_paths(job, variant)[1], "the EDL").get("segments", [])
            if float(s["end"]) - float(s["start"]) > 0]
    a = 0.0
    for s in segs:
        d = float(s["end"]) - float(s["start"])
        if t < a + d or s is segs[-1]:
            break
        a += d
    src, at = ((Path(job) / s["media"], t - a) if s.get("media")
               else (Path(job) / "raw" / os.path.basename(s["clip"]), float(s["start"]) + t - a))
    if not src.exists():
        raise BadInput(f"--stills needs the source footage: {src} is missing")
    # fitted by HEIGHT and never cropped (a narrower-than-9:16 source by width): face-frame.json's modes place the
    # WHOLE fitted source (on a landscape raw W's centre is its face-centred crop), so a centre crop here put the
    # discarded sides back as black and the face off-centre on the still the creator approves
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0.0, at):.4f}", "-i", str(src), "-frames:v", "1",
                        "-vf", f"scale='if(gte(iw*{H},ih*{W}),-2,{W})':'if(gte(iw*{H},ih*{W}),{H},-2)'",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if r.returncode or not r.stdout:
        raise BadInput(f"ffmpeg could not read a frame of {src} at {at:.3f} s")
    return Image.open(io.BytesIO(r.stdout)).convert("RGB")


def _ui_font(size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT_SF, size)
    except OSError:
        return ImageFont.load_default(size)


def _label(img, box, text):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.rectangle(box, fill=(70, 70, 74))
    d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, font=_ui_font(120), fill=(150, 150, 156), anchor="mm")


def stills(job, variant, times, lines, frame, fps, font, ver):
    """review/caption-stills[-VER].png: per time, the current layer (the caption sheet) beside the proposed one, each
    on the source frame as that time's layout shows it (S slid under a grey stand-in panel, T punched in, W as shot,
    F a flat grey stand-in labelled F)."""
    from PIL import Image, ImageDraw
    _, cur = read_sheet(job, variant)
    pw, ph, gap, head = W // 2, H // 2, 24, 40
    board = Image.new("RGB", (2 * pw + 3 * gap, len(times) * (ph + head + gap) + gap), (18, 18, 20))
    d, hf = ImageDraw.Draw(board), _ui_font(20)
    for r, t in enumerate(times):
        f = math.floor(t * fps)
        mode = frame.mode_at((f + 0.5) / fps)
        base = Image.new("RGB", (W, H))
        if mode == "F":
            _label(base, (0, 0, W, H), "F")
        else:
            base = frame.footage(raw_frame(job, variant, t), mode)
            if mode == "S":
                _label(base, (0, 0, W, Y_SPLIT), "panel")
        prop = next((ln for ln in lines if ln["f0"] <= f < ln["f1"]), None)
        was = next((ln for ln in cur or [] if round(ln["start"] * fps) <= f < round(ln["end"] * fps)), None)
        panels = (("current", was and (was["text"], was["y"], was.get("voice", HOST))),
                  ("proposed", prop and (prop["text"], frame.y_frame(f, fps), prop["voice"], prop.get("plain", ()))))
        y0 = gap + r * (ph + head + gap)
        for c, (name, cap) in enumerate(panels):
            img = base.convert("RGBA")
            if cap:
                img.alpha_composite(draw_line(cap[0], cap[1], colour_of(cap[2]), font, cap[3] if len(cap) > 3 else ()))
            x0 = gap + c * (pw + gap)
            board.paste(img.convert("RGB").resize((pw, ph)), (x0, y0 + head))
            note = ("no caption sheet yet" if cur is None else "no line") if name == "current" and not cap else \
                   (f"y{cap[1]}" if cap else "no line")
            d.text((x0, y0 + 10), f"{name}  ·  t {t:.2f} s  ·  layout {mode}  ·  {note}", font=hf, fill=(230, 230, 230))
    out = Path(job) / "review" / f"caption-stills{'-' + ver if ver else ''}.png"
    os.makedirs(out.parent, exist_ok=True)
    board.save(out)
    return out


# ── CLI ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None, frame=None):
    """`frame` injects a resolved layout (the tests); the CLI resolves it through layout.py."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("job")
    ap.add_argument("--variant", help="a second deliverable (its own transcript, EDL and layout), e.g. ad")
    ap.add_argument("--ver", help="version suffix: captions-alpha-<VER>.mov")
    ap.add_argument("--stills", help="comma-separated cut-clock seconds: current beside proposed, for approval")
    ap.add_argument("--check", metavar="MOV", help="the gate on this render, against the job as it is now")
    ap.add_argument("--dry", action="store_true", help="the line table and the text gates; nothing rendered or written")
    ap.add_argument("--straight-alpha", action="store_true",
                    help="for a straight-alpha compositor (the chat-only ffmpeg assemble): draw the box at the alpha that "
                         "reads like Premiere's linear-light 80 %% (captions-style.md § 1)")
    a = ap.parse_args(argv)
    global _box_alpha
    _box_alpha = STRAIGHT_BOX_ALPHA if a.straight_alpha else BOX_FILL[3]
    if a.straight_alpha:
        print(f"[captions] --straight-alpha: box alpha {_box_alpha} (the straight-blend match for the approved linear-light "
              f"{BOX_FILL[3]}); for a straight-alpha compositor only, never for Premiere")
    for flag, v in (("--variant", a.variant), ("--ver", a.ver)):
        if v and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", v):
            raise BadInput(f"{flag} {v!r}: letters, digits, - and _ only (it becomes part of file names)")
    job = Path(a.job).resolve()
    if not job.is_dir():
        raise BadInput(f"no job folder at {job}")
    plan = resolve_plan(job, a.variant)
    hl = captions_cell(plan).get("highlight") or {}
    if hl:
        hx = str(hl.get("color", "")).lstrip("#")
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", hx) or not hl.get("words"):
            raise BadInput('the captions cell\'s "highlight" needs "words" and a "color" #RRGGBB')
        _highlight.update({"".join(ch for ch in w.lower() if ch.isalnum()): tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
                           for w in hl["words"]})
        _highlight_not.update(_alnum(w) for w in hl.get("except") or [] if len(w.split()) == 1)
        print(f"[captions] highlight: {', '.join(hl['words'])} in #{hx} (the plan's captions cell: a sponsor's requirement)")
    rate = rate_of(plan); fps = float(rate)
    words, dur = load_words(job, a.variant, plan)
    if not words:
        raise BadInput(f"{_paths(job, a.variant)[0].name} has no words")
    phrases = [w for w in hl.get("except") or [] if len(w.split()) > 1]
    if phrases:
        print(f"[captions] highlight kept white after: {', '.join(phrases)} ({mark_plain(words, phrases)} word(s))")
    frame = frame or load_frame(job, a.variant, plan)
    font, font_label, warn = load_font()
    if warn:
        print(f"[captions] ⚠⚠⚠ {warn}", file=sys.stderr)
    measure = make_measure(font)
    lines = build_lines(words, frame.breaks, measure, fps)
    nframes = round(dur * fps)
    tag = job.name + (f" · variant {a.variant}" if a.variant else "")

    if a.stills:
        try:
            times = [float(x) for x in a.stills.split(",") if x.strip()]
        except ValueError:
            raise BadInput(f"--stills {a.stills!r}: comma-separated seconds, e.g. 6.0,20.5")
        print(f"[captions] {tag}: stills -> {stills(job, a.variant, times, lines, frame, fps, font, a.ver)}")
        return 0

    fails, mov, checked = [], None, lines
    if not a.dry and not shutil.which("ffmpeg"):
        raise BadInput("ffmpeg is not on PATH: the render and the per-frame gate need it (check-setup.sh)")
    if a.check:
        mov = Path(a.check).resolve()
        if not mov.exists():
            raise BadInput(f"--check {mov}: no such render")
        name, sheet = read_sheet(job, a.variant)
        if sheet is not None and name == mov.name:               # the text gates read what the render carries
            checked = [dict(ln, f0=round(ln["start"] * fps), f1=round(ln["end"] * fps)) for ln in sheet]
            diff = stale(lines, sheet, fps)
            if diff:
                fails.append(f"{mov.name} is stale: a build of the job as it is now differs (- render + now): {diff}")
        else:
            print(f"[captions] ⚠ no caption sheet names {mov.name}: its text is checked against a fresh build")
    elif not a.dry:
        placed = placed_files(job, a.variant)
        mov = out_path(job, a.variant, a.ver)
        if os.path.realpath(mov) in placed:                      # realpath: /var and /private/var are one folder
            raise BadInput(f"{mov.name} is placed on the timeline (placement{'.' + a.variant if a.variant else ''}.json) and "
                           "is never overwritten: never overwrite a placed render, Premiere half-stales its frame index. "
                           f"Rebuild with --ver {next_free_ver(job, a.variant, placed)}")
        root = "/tmp" if os.name != "nt" else tempfile.gettempdir()
        work = os.path.join(root, "video-editor", job.name, "captions" + (f"-{a.variant}" if a.variant else ""))
        render(lines, frame, fps, nframes, font, work, mov)
        write_sheet(job, a.variant, lines, frame, fps, font_label, warn, mov)
    print(f"[captions] {tag}: {len(lines)} lines · {len(words)} words · {nframes} frames @ {rate}"
          + (f" · {mov}" if mov else " · dry run, nothing written"))
    print_table(checked, frame, fps)
    fails += gate(words, checked, frame, fps, measure, mov, nframes if mov else None)
    for f in fails:
        print(f"[captions] ✗ {f}")
    if not fails:
        print(f"[captions] ✓ gate: captions == transcript ({len(words)} words), no line spans a break or leads its "
              f"first word, every line ≤ {MAX_W} px"
              + (", every inked frame on its layout's y, every spoken frame captioned" if mov else ""))
    if warn:
        print(f"[captions] ⚠⚠⚠ {warn}")
    return 1 if fails else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BadInput as e:
        print(f"[captions] ✗ {e}", file=sys.stderr)
        sys.exit(2)
