#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""build.py — basic TEXT ANIMATIONS (the youtube-default preset).

Word-synced emphasis text: each word RISES in and eases to rest, timed to the
spoken word. The entrance is `riseIn` — these are NOT the `pop` scale preset,
which is a special case a spec has to ask for by name (2026-08-31). The default sprinkle-in graphic — when nothing else is
called for, a text animation is the move. Locked 2026-08-29; layout rules
re-dialed same day (bigger, lower, line-balanced — your spacing pass).

THE LOCK is the animation + the fonts: Helvetica Bold lowercase (tight tracking)
as the standard, Playfair Display Italic w700 as the emphasis font for power
words, a small rise on power3.out (fast off the mark, long settle), NO fade-in,
each word led 80 ms ahead of its transcript timestamp so the settle lands on
the audio.

THE LAYOUT LAW (2026-08-29; the band re-measured 2026-08-31):
- THE LOW BAND is the hard frame: the whole block lives between TOP_MIN and
  BOTTOM_MAX and NOTHING is allowed out of it. Type size is what gives — a
  block that does not fit is scaled down until it does. This is why a
  one-liner and a two-liner are not the same size: two lines in the same
  band means smaller type, and that is correct, not a compromise.
- The block sits LOW inside the band: vertically centered halfway between the
  chin and the bottom edge (cy 850, a touch under halfway), never on the face.
- It fills the screen: each line is sized to a target width (default 1250px),
  so the type takes real estate instead of floating small — but the band wins
  when the two disagree.
- Lines BALANCE: every line is solved to the same width — a short last line
  automatically gets bigger type (the "one big word in the emphasis font"
  look), so a two-line block reads as a clean rectangle.
- Emphasis sprinkling: mark 0-2 power words with *asterisks* in the phrase and
  they set in Playfair Italic (x-height parity, ×1.033). Don't force it.

Usage: copy this folder into projects/<job>/hf-graphics/text-animation/, write
text.json, ./render.sh. Word timings come straight from the job's canonical
transcript — never retyped, never re-transcribed.

text.json — one entry per text animation:
  {
    "p1": {
      "phrase": "this video that you're watching *right now*",
      "lines": ["this video that you're watching", "*right now*"],
      "pos": "center",      // center | left | right  (sides = beside the face)
      "width": 1500,        // target line width px (the fill-the-screen knob)
      "cy": 850,            // block vertical center (center pos only)
      "y": null,            // explicit block top px — overrides cy
      "color": "#eef4ff",   // ink; black variant: "#111"
      "glow": true,         // kill when the text already contrasts with the bg
      "size": null,         // fixed font px — disables width-solving entirely
      "hold": 0.7,          // s between the last word landing and the fade-out
      "occurrence": 1       // which match of the phrase in the transcript
    }
  }
Only "phrase" is required. Display text is used AS TYPED (so a capitalized
proper noun stays capitalized); transcript matching is case/punct-insensitive.
A pop must never bleed across a V1 cut — trim the placed clip to the edit.

build.py [ids...] emits compositions/<id>.html and prints WHERE on the timeline
to place each pop (also saved to compositions/<id>.meta.json). The job folder is
auto-derived from this folder's location; pass --job <dir> to override.
"""
import json
import re
import shutil
import sys
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from html import escape
from pathlib import Path

HERE = Path(__file__).parent
W, H = 1920, 1080
# --scale 2 : render the SAME 1080 layout at 3840x2160 for a 4K master (the comp puts it on a scale(2)
# stage inside the bigger root, never CSS `zoom`; see the template). 1 = the 1080 render, the default.
RENDER_SCALE = int(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 1

# ── THE LOCK: type + animation. Ratios are relative to the line's font size. ──
# The sans is REAL Helvetica Bold, under a family name hyperframes does not alias: its compiler maps `helvetica`,
# `helvetica neue` and `arial` to its bundled Inter on every OS, so the old stack rendered Inter everywhere while the
# width solve measured Helvetica (2026-09-27: "switch it to a real Helvetica"). The @font-face takes the
# system's Helvetica Bold (every Mac), else the bundled TeX Gyre Heros Bold (GUST licence), a Helvetica clone with its
# exact advances, where Helvetica is not installed (Windows, Linux). The solve reads the same file the render draws.
SANS_FAMILY = "VE Helvetica"
SANS_FONT = "texgyreheros-bold.otf"            # from assets/fonts, copied in: the stand-in where Helvetica is missing
HELVETICA = ("/System/Library/Fonts/Helvetica.ttc", 1)   # Helvetica Bold, the face local() resolves on a Mac
FONT_STACK = f"'{SANS_FAMILY}',sans-serif"
SERIF_FONT = "PlayfairDisplay-Italic-VF.ttf"   # from assets/fonts, copied in
SERIF_STACK = "'Playfair Display',Georgia,serif"
SERIF_RATIO = 1.033   # x-height parity vs Helvetica (measured by ink height)
TRACK_R = -0.044      # Helvetica letter-spacing / font size
TRACK_SERIF_R = -0.028
GAP_R = 0.1222        # word margin each side / font size
LINE_H_R = 1.05
INK = "#eef4ff"       # off-white, never pure #fff
RISE_R = 22 / 90      # rise px / font size
RISE_DUR = 0.55
EASE = "power3.out"

# --- THE POP (entrance "punch") -------------------------------------------
# THE HOUSE POP: come in UNDER size, grow past the target,
# then snap back on one frame. 0.90 -> 1.10 over 3 frames, then 1.00 on frame 4.
# The snap is the beat; the grow is the wind-up — the grow EASES OUT so it leans
# into the overshoot and hangs a beat before the correction, which makes the snap
# hit harder than a linear grow does.
# MOTION BLUR is the HyperFrames motion-blur component on every word, ON by default since 2026-10-06 (the shutter in
# build() below; a cell opts out with "shutter": false). Never also MBLUR=1 (one blur, not two), never STEP_FPS=12.
# Before that: MBLUR off here, a slam rendered MBLUR=1 MBLUR_SS=8 MBLUR_SHUTTER=5 (creative-moves.md 4b).
SCALE_PRESETS = {
    # come in under size, grow past, snap back on one frame. THE default.
    "pop":  {"from": 0.90, "over": 1.10, "frames": 3, "ease": "power2.out"},
    # start over size and settle down to rest — heavier, use it sparingly.
    "slam": {"from": 1.16, "over": 0,    "frames": 7, "ease": "power2.out"},
}
SCALE_DEFAULT = "pop"
LEAD = 0.08
GLOW = [(24 / 90, 1.0), (9 / 90, 0.80)]  # (blur/size, opacity) black duplicates
HOLD = 0.7
OUT_DUR = 0.35
OUT_RISE = -18
MIN_HOLD_FOR_EXIT = 0.25   # less settled time than this before a cut → the cut is the exit

WIDTH_TARGET = 1250
CY_DEFAULT = 850      # low block, a touch under chin-to-bottom halfway
# THE LOW BAND, measured not guessed (2026-08-31). 765 is the floor because the
# LOWEST chin in a 242-frame sweep of the shipped cut sits at y694 (YuNet box
# bottom == the jaw line, eyeballed against the worst frame), and 765 is the top
# of the one-line block range that already read clean (766-786). 1030 leaves a
# 50px margin off the frame edge. Re-derive per shoot if the framing changes:
#   uv run workflows/chin-line.py projects/<job>/outputs/<job>.mp4
# A two-line block cannot fit 265px at full size, so it auto-scales — that IS
# the "two-liners are smaller and lower" rule, enforced by geometry.
TOP_MIN, BOTTOM_MAX = 765, 1030
SIZE_MIN, SIZE_MAX = 56, 300
MAX_RATIO = 2.0       # a balanced short line gets bigger, never cartoonishly so
DESC_R = 0.18         # serif descender allowance below the last line box
POS_DEFAULT_Y = {"left": 300, "right": 300}


def norm(w):
    return re.sub(r"^[^\w']+|[^\w']+$", "", w).lower()


def job_dir():
    if "--job" in sys.argv:
        return Path(sys.argv[sys.argv.index("--job") + 1]).resolve()
    return HERE.resolve().parent.parent


def ensure_font(name):
    dst = HERE / "assets" / name
    if dst.exists():
        return dst
    for up in HERE.resolve().parents:
        src = up / "assets" / "fonts" / name
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            return dst
    sys.exit(f"{name} not found in any parent assets/fonts/")


def load_words(job):
    p = job / "outputs" / f"{job.name}.transcript.json"
    if not p.exists():
        sys.exit(f"no canonical transcript at {p} — is this folder copied into "
                 "a job's hf-graphics/ (or pass --job <job_dir>)?")
    data = json.loads(p.read_text(encoding="utf-8"))
    entries = data["words"] if isinstance(data, dict) else data
    return [e for e in entries if e.get("type", "word") == "word"]


RED = "#ff4d5e"  # the negation/danger accent (variety law)


def tokenize(text):
    """[(display, emphasis_bool, red_bool)]: *...* = serif emphasis, ~...~ = red.
    Punctuation-aware: `*official*.` and `*official.*` both display "official." in
    emphasis (the first shipped a literal asterisk on screen, 2026-09-02)."""
    out, emph, red = [], False, False
    for tok in text.split():
        lead, body, trail, punct = re.match(r"^([*~]*)(.*?)([*~]*)([^\w*~']*)$", tok).groups()
        core = body + punct
        e_starts, r_starts = "*" in lead, "~" in lead
        e_ends = "*" in trail and len(core) > 0
        r_ends = "~" in trail and len(core) > 0
        if e_starts:
            emph = True
        if r_starts:
            red = True
        out.append((core, emph or e_starts, red or r_starts))
        if e_ends:
            emph = False
        if r_ends:
            red = False
    return out


# Words the spoken run may carry INSIDE a phrase that the on-screen copy leaves out
# ("well over, you know, six months"). The exact match runs first; this is the second pass.
FILLERS = {"um", "uh", "like", "you", "know", "so", "right", "okay", "ok", "actually",
           "basically", "just", "literally", "kinda", "kind", "of", "sort", "i", "mean",
           "yeah", "well", "and", "then"}
MAX_FILLER_SKIPS = 3


def find_phrase(words, tokens, occurrence):
    want = [norm(d) for d, _, _ in tokens]
    have = [norm(e["text"]) for e in words]
    shown = " ".join(w for w, _, _ in tokens)
    hits = [list(range(i, i + len(want))) for i in range(len(have) - len(want) + 1)
            if have[i:i + len(want)] == want]
    if not hits:
        # filler-tolerant pass: skip up to MAX_FILLER_SKIPS transcript fillers between wanted words
        for i in (k for k, w in enumerate(have) if w == want[0]):
            idx, skipped, j, k = [], [], i, 0
            while j < len(have) and k < len(want):
                if have[j] == want[k]:
                    idx.append(j); k += 1
                elif have[j] in FILLERS and len(skipped) < MAX_FILLER_SKIPS:
                    skipped.append(words[j]["text"])
                else:
                    break
                j += 1
            if k == len(want):
                hits.append(idx)
                print(f"  ! {shown!r} matched with filler skipped: {', '.join(repr(s) for s in skipped)}"
                      f" (the transcript run is {' '.join(e['text'] for e in words[i:j])!r})")
    if not hits:
        # say WHERE it nearly is, with timestamps, instead of just "not found"
        span = len(want) + MAX_FILLER_SKIPS
        best = max(range(max(1, len(have) - span + 1)),
                   key=lambda i: sum(1 for w in have[i:i + span] if w in set(want)))
        near = words[best:best + span]
        sys.exit(f"phrase not found in transcript: {shown!r}\n"
                 f"  closest run ({near[0]['start']:.2f}s → {near[-1]['end']:.2f}s): "
                 f"{' '.join(e['text'] for e in near)!r}\n"
                 f"  write the phrase as SPOKEN (the copy shows what you type; only matching is verbatim),"
                 f" or split it at the mismatch")
    if occurrence > len(hits):
        sys.exit(f"occurrence {occurrence} asked but only {len(hits)} match(es)")
    if len(hits) > 1:
        print(f"  ! phrase occurs {len(hits)}x — using #{occurrence}")
    return [words[j] for j in hits[occurrence - 1]]


def load_cuts(job):
    """Timeline V1 cut points (s) from the persisted EDL: cumulative kept durations."""
    p = job / "transcript" / "cuts.json"
    if not p.exists():
        return []
    segs = json.loads(p.read_text(encoding="utf-8"))["segments"]
    if segs and all(isinstance(s.get("_timeline"), list) for s in segs):
        # an EDL read back from the timeline carries `_timeline` [start, end] (sequence seconds): those ARE the V1 cuts;
        # the cumulative sum drifts off the sequence on a mixed-rate source (0.22 s by the outro of your-job,
        # 2026-09-18), the same rule as validate-plan.py / place-graphics.py / graphics-qa.py. A SECTION sub-job's
        # `_timeline` sits on the parent sequence while its words run on the section's own clock: take the plan's
        # timeline_offset back off, as those tools do (an outro at 578 s clamped nothing, 2026-09-28)
        plan = job / "graphics-plan.json"
        off = float(json.loads(plan.read_text(encoding="utf-8")).get("timeline_offset") or 0.0) if plan.exists() else 0.0
        return [round(float(s["_timeline"][1]) - off, 4) for s in segs]
    t, cuts = 0.0, []
    for s in segs:
        t += float(s["end"]) - float(s["start"])
        cuts.append(round(t, 4))
    return cuts


def measure_line(tokens, size):
    """Line width at a given Helvetica base size, from the real font metrics.
    Everything scales linearly with size, so one solve is exact."""
    from PIL import ImageFont
    # the face the render draws: the system's Helvetica Bold where local() finds it, else the bundled stand-in
    try:
        helv = ImageFont.truetype(HELVETICA[0], 200, index=HELVETICA[1])
    except OSError:
        helv = ImageFont.truetype(str(ensure_font(SANS_FONT)), 200)
    serif = ImageFont.truetype(str(HERE / "assets" / SERIF_FONT), 200)
    try:
        serif.set_variation_by_axes([700])
    except Exception:
        pass
    w = 0.0
    for disp, emph, _red in tokens:
        if emph:
            s = size * SERIF_RATIO
            w += serif.getlength(disp) * s / 200 + TRACK_SERIF_R * s * max(0, len(disp) - 1)
        else:
            w += helv.getlength(disp) * size / 200 + TRACK_R * size * max(0, len(disp) - 1)
        w += 2 * GAP_R * size
    return w


def solve_size(tokens, target):
    base = 100.0
    width = measure_line(tokens, base)
    if width <= 0:
        return SIZE_MIN
    return max(SIZE_MIN, min(SIZE_MAX, base * target / width))


def build(pid, spec, tokens, words, cuts=(), fps=30000 / 1001):
    # THE SHUTTER (2026-10-06: "the new motion blur does work pretty smoothly... apply that to pretty much all of
    # our graphics that would benefit from it"): HyperFrames' motion-blur component (hf-motion-blur.js beside this file)
    # integrates every word's rise / slam over a real shutter. On by default; a cell opts out with "shutter": false. The
    # flicker entrance moves nothing, so it carries none. Never with MBLUR (one blur, not two) or STEP_FPS.
    # EVERY word carries it, the one moving on frame 0 included: the frame-0 ghost that once excluded it was the
    # component's own bug (a font-load re-snapshot left the copies at the line's origin and nothing re-sampled before
    # frame 0), fixed in hf-motion-blur.js 2026-10-06 and proven by workflows/motion-blur-ab.py.
    shutter = spec.get("shutter", True) and spec.get("entrance", "rise") != "flicker"
    mb_attr = (f" data-hf-motion-blur='{{\"fps\": {fps:.9f}}}'" if shutter else "")
    F = 1.0 / fps
    pos = spec.get("pos", "center")
    target = spec.get("width", WIDTH_TARGET)
    hold = spec.get("hold", HOLD)
    ink = spec.get("color", INK)
    entrance = spec.get("entrance", "rise")
    if entrance in ("pop", "punch"):
        sys.exit(f"entrance {entrance!r} on {spec.get('phrase', spec)!r}: type never pops (2026-09-10; animations.md § TEXT NEVER POPS). "
                 "A text animation rises (the default, scissors) or slams (entrance 'slam', Impact); the pop is for objects.")
    # "punch" is the legacy spec name for the (now object-only) pop shape; kept for the slam branch below
    if entrance == "flash":
        entrance = "flicker"       # registry name -> the builder's historical knob
    shape = "pop" if entrance in ("punch", "pop") else entrance
    preset = SCALE_PRESETS.get(shape, SCALE_PRESETS[SCALE_DEFAULT])
    if entrance in ("punch", "pop", "slam"):
        entrance = "punch"          # the JS branch name
    pop_from = spec.get("pop_from", preset["from"])
    pop_over = spec.get("pop_over", preset["over"])
    pop_frames = spec.get("pop_frames", preset["frames"])
    pop_ease = spec.get("pop_ease", preset["ease"])
    tilt = spec.get("tilt", 0)

    # split into lines of (display, emph) tokens
    if spec.get("lines"):
        lines = [tokenize(l) for l in spec["lines"]]
        if [norm(d) for l in lines for d, _, _ in l] != [norm(d) for d, _, _ in tokens]:
            sys.exit(f"{pid}: \"lines\" words don't match \"phrase\"")
    else:
        lines = [tokens]

    # per-line size: fixed override, or solved so every line hits the target width
    if spec.get("size"):
        sizes = [float(spec["size"])] * len(lines)
    else:
        sizes = [solve_size(l, target) for l in lines]
        # balance guard: a short line grows to match, but never past 2x its
        # smallest sibling — a 3x jump reads broken, not designed
        mn = min(sizes)
        sizes = [min(s, MAX_RATIO * mn) for s in sizes]

    # vertical fit: the whole block (plus descender room, plus the rise-in travel, the
    # words START that far BELOW rest, so the entry frames reach lower than the rest
    # position) must live between TOP_MIN (below the chin) and BOTTOM_MAX, scale
    # everything down if not. Without the travel term six text animations dipped to
    # y1032-1053 on entry and were re-measured in every review round (2026-09-02).
    desc = DESC_R * sizes[-1]
    rise = RISE_R * sizes[-1] if entrance == "rise" else 0.0
    block_h = sum(LINE_H_R * s for s in sizes)
    avail = BOTTOM_MAX - TOP_MIN
    if block_h + desc + rise > avail:
        k = avail / (block_h + desc + rise)
        sizes = [s * k for s in sizes]
        desc *= k
        rise *= k
    heights = [round(LINE_H_R * s) for s in sizes]
    block_h = sum(heights)
    if pos == "center":
        cy = spec.get("cy", CY_DEFAULT)
        top = spec.get("y") or max(TOP_MIN, min(cy - block_h / 2,
                                                BOTTOM_MAX - block_h - desc - rise))
    else:
        top = spec.get("y", POS_DEFAULT_Y[pos])

    # "place": explicit timeline place time — clamps the animation to a clip head so it
    # can't bleed backward across a V1 cut (word 1 just loses part of its lead)
    place = spec.get("place", max(0.0, words[0]["start"] - LEAD))
    # the LEAD may not cross the PREVIOUS V1 cut either: a phrase whose first word sits within 80 ms of its clip's head
    # started a frame before the cut and showed over the outgoing shot (t12, 58.625 vs the cut at 58.659, 2026-09-27).
    # Clamp to the cut, as a hand "place" would; word 1 just loses part of its lead.
    if "place" not in spec:
        head = [c for c in cuts if place < c <= words[0]["start"]]
        if head:
            place = max(head)
            print(f"  · {pid}: placed ON the V1 cut at {place:.3f}s (the {LEAD * 1000:.0f} ms lead would cross it)")
    dur = words[-1]["end"] + hold + OUT_DUR - place
    # "until": the exit must COMPLETE before the next V1 cut. Default = the first cut after
    # the first word (from transcript/cuts.json); a number overrides; null disables. Before
    # this, a text animation running into a cut was hard-cut with its rise-out never played
    # (6 of 13 on your-job), and the placement had to be trimmed by hand.
    until = spec.get("until", "auto")
    if until == "auto":
        until = next((c for c in cuts if c > words[0]["start"] + 0.05), None)
    # The exit lands 2 frames before DUR and the block is hard-killed on the last frame, so
    # the last rendered frame is empty (registry rule; nothing may linger into the cut).
    # When the phrase runs up to the cut there are two honest options: fade the last word
    # while it is still arriving, or let the CUT be the exit. The cut wins: a picture cut
    # is already an exit event, exactly as a hard cut to a full-screen is its entrance, 
    # so the rise-out plays only when the last word can settle and hold MIN_HOLD_FOR_EXIT
    # before it starts. Either way the comp ENDS ON THE CUT; nothing is trimmed by hand.
    exit_kind = "riseOut"
    last_land = words[-1]["start"] - LEAD - place + RISE_DUR
    if until is not None and place + dur > until:
        if until < words[-1]["end"]:
            print(f"  ⚠ {pid}: a V1 cut at {until:.3f}s falls INSIDE the phrase, the last word(s) "
                  f"will not land; split the phrase at the cut")
        dur = until - place
        if dur - OUT_DUR - 2 * F - last_land < MIN_HOLD_FOR_EXIT:
            exit_kind = "cut"
            if not any(abs(until - c) < 0.5 * F for c in cuts):
                # a number that is NOT a V1 cut cannot be the exit: the block would switch off mid-shot (t11, 2026-09-27)
                print(f"  ⚠ {pid}: 'until' {until:.3f}s is not a V1 cut and leaves no room for the rise-out: the block "
                      f"will switch off mid-shot. Move 'until' to >= {place + last_land + MIN_HOLD_FOR_EXIT + OUT_DUR + 2 * F:.2f}s "
                      f"or to the cut")
            print(f"  · {pid}: runs to the V1 cut at {until:.3f}s and the cut is the exit "
                  f"(last word settles {dur - last_land:.2f}s before it; no room for a rise-out)")
        else:
            print(f"  · {pid}: clamped to the V1 cut at {until:.3f}s (hold {dur - OUT_DUR - 2*F - last_land:.2f}s)")
    out_t = dur - OUT_DUR - 2 * F if exit_kind == "riseOut" else None

    block_pos = {
        "center": f"left:0;top:{top:.0f}px;width:{W}px;text-align:center;",
        "left": f"left:120px;top:{top:.0f}px;text-align:left;",
        "right": f"right:120px;top:{top:.0f}px;text-align:right;",
    }[pos]

    it = iter(words)
    rows, css = [], []
    for li, (line, s, h) in enumerate(zip(lines, sizes, heights)):
        ss = s * SERIF_RATIO
        glow_css = "" if not spec.get("glow", True) else (
            f".l{li} .w::before{{filter:blur({GLOW[0][0]*s:.0f}px);opacity:{GLOW[0][1]};}}"
            f".l{li} .w::after{{filter:blur({GLOW[1][0]*s:.0f}px);opacity:{GLOW[1][1]};}}")
        css.append(f"""
.l{li} .w{{font-size:{s:.1f}px;line-height:{h}px;letter-spacing:{TRACK_R*s:.1f}px;
  margin:0 {GAP_R*s:.0f}px;}}
.l{li} .w.serif{{font-size:{ss:.1f}px;letter-spacing:{TRACK_SERIF_R*ss:.1f}px;}}{glow_css}""")
        cells = []
        for disp, emph, red in line:
            wd = next(it)
            t0 = max(0.0, wd["start"] - LEAD - place)
            cls = "w" + (" serif" if emph else "") + (" red" if red else "")
            cells.append(f'<span class="{cls}" data-t="{t0:.4f}" data-rise="{RISE_R*s:.0f}" '
                         f'data-w="{escape(disp, quote=True)}"{mb_attr}>{escape(disp)}</span>')
        rows.append(f'<div class="line l{li}">{"".join(cells)}</div>')

    glow_common = "" if not spec.get("glow", True) else """
/* faint black glow = blurred duplicates of the word behind it (never text-shadow) */
.w::before,.w::after{content:attr(data-w);position:absolute;left:0;top:0;
  z-index:-1;color:#000;pointer-events:none;}"""

    # RENDER_SCALE 2 = a 4K render of the SAME 1080 layout: the block sits on a scale(2) STAGE inside the bigger
    # root. NEVER CSS `zoom` (Chrome double-resolves percentage origins and gradient positions under zoom; three
    # punch-cuts shipped off-centre on your-job, 2026-09-07). At 1 the stage is omitted, so the 1080
    # comp stays byte-identical to the proven builder output. Prove a re-render: workflows/render-diff.py.
    stage_css = (f"#stage{{position:absolute;left:0;top:0;width:{W}px;height:{H}px;transform:scale({RENDER_SCALE});transform-origin:0 0;}}\n"
                 if RENDER_SCALE != 1 else "")
    stage_open = '<div id="stage">\n' if RENDER_SCALE != 1 else ''
    stage_close = '</div>\n' if RENDER_SCALE != 1 else ''
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width={W*RENDER_SCALE}, height={H*RENDER_SCALE}"/>
<title>{pid}</title>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
{'<script src="hf-motion-blur.js"></script>' if shutter else ''}
<style>
@font-face{{font-family:'{SANS_FAMILY}';
  src:local('Helvetica Bold'),local('Helvetica-Bold'),url('assets/{SANS_FONT}') format('opentype');
  font-weight:700;font-style:normal;font-display:block;}}
@font-face{{font-family:'Playfair Display';
  src:url('assets/{SERIF_FONT}') format('truetype');
  font-weight:400 900;font-style:italic;font-display:block;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
#root{{position:relative;width:{W*RENDER_SCALE}px;height:{H*RENDER_SCALE}px;overflow:hidden;background:transparent;}}
{stage_css}#block{{position:absolute;{block_pos}}}
.line{{white-space:nowrap;}}
.w{{position:relative;display:inline-block;
  font-family:{FONT_STACK};font-weight:700;color:{ink};
  opacity:0;will-change:transform,opacity;}}
.w.serif{{font-family:{SERIF_STACK};font-weight:700;font-style:italic;}}
.w.red{{color:{RED};}}{glow_common}
{'/* the motion-blur copies carry the LETTERS only: the shadow stays on the real word (copied 17 times it summed into a pale haze round every rising word, 2026-10-06) */' if shutter else ''}
{'[data-hf-motion-blur-group] .w::before,[data-hf-motion-blur-group] .w::after{content:none;display:none;}' if shutter else ''}
{''.join(css)}
</style></head>
<body style="margin:0;background:transparent;">
<div id="root" data-composition-id="main" data-width="{W*RENDER_SCALE}" data-height="{H*RENDER_SCALE}"
     data-start="0" data-duration="{dur:.4f}">
{stage_open}<div id="block">
{chr(10).join(rows)}
</div>
{stage_close}</div>
<script>
// Entrances: rise (default, per-word settle) | pop / punch (the house pop:
// 0.90 -> 1.10 over 3f, snap to 1.00) | slam (1.16 settling over 7f)
// | flicker (whole block strobes in on the 7-frame 20%-pulse pattern).
const DUR = {dur:.4f}, RISE_DUR = {RISE_DUR}, F = {F:.6f};
const OUT_T = {'null' if out_t is None else f'{out_t:.4f}'}, OUT_DUR = {OUT_DUR};   // null = the V1 cut is the exit
const ENTRANCE = "{entrance}", TILT = {tilt};
const POP_FROM = {pop_from}, POP_OVER = {pop_over}, POP_F = {pop_frames},
      POP_EASE = "{pop_ease}";

const tl = gsap.timeline({{paused: true}});
if (TILT) gsap.set('#block', {{rotation: TILT}});
const els = [...document.querySelectorAll('.w')];
if (ENTRANCE === 'flicker') {{
  const t0 = Math.min(...els.map(e => +e.dataset.t));
  for (const el of els) tl.set(el, {{opacity: 1}}, 0);
  tl.set('#block', {{opacity: 0}}, 0);
  for (const [f, o] of [[0,.2],[1,0],[3,.2],[4,0],[5,.2],[6,1]])
    tl.set('#block', {{opacity: o}}, t0 + f * F);
}} else {{
  for (const el of els) {{
    const t0 = +el.dataset.t;
    if (ENTRANCE === 'punch') {{
      tl.set(el, {{opacity: 1, scale: POP_FROM}}, t0);
      if (POP_OVER > 0) {{                       // grow past, then snap back on 1 frame
        tl.to(el, {{scale: POP_OVER, duration: POP_F * F, ease: POP_EASE}}, t0);
        tl.set(el, {{scale: 1}}, t0 + (POP_F + 1) * F);
      }} else if (POP_F > 0) {{                  // settle shape (the old slam)
        tl.to(el, {{scale: 1, duration: POP_F * F, ease: POP_EASE}}, t0);
      }} else {{
        tl.set(el, {{scale: 1}}, t0 + F);
      }}
    }} else {{
      tl.fromTo(el, {{y: +el.dataset.rise}}, {{y: 0, duration: RISE_DUR, ease: '{EASE}'}}, t0);
      tl.set(el, {{opacity: 1}}, t0);
    }}
  }}
}}
if (OUT_T !== null) {{
  // riseOut is RELATIVE ('-=') so it rises from wherever the words rest (registry rule). The travel rides the WORDS and
  // the fade the block: the motion-blur component reads an element's own transform, so a block that moved carried its
  // words out sharp (2026-10-06); the fade stays one layer, so the shadows overlapping between words fade as before.
  tl.to('#block', {{opacity: 0, duration: OUT_DUR, ease: 'power2.in'}}, OUT_T);
  tl.to(els, {{y: '-={-OUT_RISE}', duration: OUT_DUR, ease: 'power2.in'}}, OUT_T);
  tl.set('#block', {{opacity: 0}}, DUR - F);   // hard-kill: the last rendered frame is empty
}}
tl.set({{}}, {{}}, DUR);   // pin the timeline's total duration
tl.progress(0);
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
</script></body></html>
"""
    return html, place, dur, sizes, until, exit_kind


def main():
    if not (HERE / "text.json").exists():
        sys.exit("no text.json next to build.py — copy text.json.example")
    specs = json.loads((HERE / "text.json").read_text(encoding="utf-8"))
    if "--ids" in sys.argv:
        print(" ".join(specs))
        return
    # --fps 24000/1001 : the timeline's exact rational rate (frame margins depend on it)
    fps = 30000 / 1001
    if "--fps" in sys.argv:
        num, _, den = sys.argv[sys.argv.index("--fps") + 1].partition("/")
        fps = float(num) / float(den or 1)
    # a flag's value is dropped by POSITION: render.sh always passes --scale and --fps, and an id equal to their
    # value (an id "1" beside --scale 1) must still build
    vals = {sys.argv.index(flag) + 1 for flag in ("--job", "--fps", "--scale") if flag in sys.argv}
    args = [a for i, a in enumerate(sys.argv) if i and i not in vals and not a.startswith("-")]
    want = args or list(specs)
    ensure_font(SERIF_FONT)
    ensure_font(SANS_FONT)
    words = load_words(job_dir())
    cuts = load_cuts(job_dir())
    comps = HERE / "compositions"
    comps.mkdir(parents=True, exist_ok=True)
    for pid in want:
        if pid not in specs:
            sys.exit(f"unknown text animation {pid!r} — have: {' '.join(specs)}")
        spec = specs[pid]
        match_tokens = tokenize(spec["phrase"])
        got = find_phrase(words, match_tokens, spec.get("occurrence", 1))
        # "display": render different words than were spoken (1:1 token map) —
        # e.g. show "never been built" over the spoken "ever been built"
        tokens = tokenize(spec.get("display", spec["phrase"]))
        if len(tokens) != len(match_tokens):
            sys.exit(f"{pid}: \"display\" must have the same word count as \"phrase\"")
        html, place, dur, sizes, until, exit_kind = build(pid, spec, tokens, got, cuts, fps)
        (comps / f"{pid}.html").write_text(html, encoding="utf-8")
        (comps / f"{pid}.meta.json").write_text(json.dumps(
            {"place": round(place, 4), "duration": round(dur, 4),
             "until": None if until is None else round(until, 4), "exit": exit_kind}, indent=2), encoding="utf-8")
        print(f"wrote {pid}: {len(got)} words, line sizes "
              f"{'/'.join(str(round(s)) for s in sizes)}px — place at "
              f"{place:.3f}s on the timeline, {dur:.2f}s long")


if __name__ == "__main__":
    main()
