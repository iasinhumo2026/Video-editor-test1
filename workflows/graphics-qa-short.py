#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""graphics-qa-short.py: the deterministic gate between the graphics BUILD (5b) and the REVIEW loop (5c) for SHORT-FORM
9:16 renders. workflows/graphics-qa.py is its 16:9 counterpart and refuses any other frame size.

  uv run workflows/graphics-qa-short.py projects/<job> [ids...] [--band Y0-Y1]
  uv run workflows/graphics-qa-short.py projects/<job> --variant ad     # the ad's placement.ad.json and composed plan

Exit 1 on any FAIL: the handoff to edit-review is blocked until it is green.

Inputs, all in the job folder, nothing job-local: hf-graphics/placement.json (every row except the caption layer),
graphics-plan.json (its `fps`, its `format`/`preset`, and each cell's `family`, `copy` and optional `copy_ocr_skip`,
`seam_clear` and `under_caption`), the renders,
and hf-graphics/qa-waivers.json when there is one (the 16:9 gate's format, {"g4": {"blank": "why"}}: a waiver silences
a FAIL or a warn of that check on that graphic and is printed as `waived`).

Authoring frame 1080x1920. A 2160x3840 render (the same layout on a 4K sequence) is measured scaled back to it, the
way graphics-qa.py measures a 4K 16:9 render. Every plane is read as 8-bit (pix_fmt ya8: luma + alpha).

QA always runs the render `workflows/placement.py --write` (and Premiere's `place-graphics.py --plan`, which is the
same derivation) would pick NOW, the newest version on disk, picked by workflows/placement.py's own `renders` (the rule
keeps one home), and says so when placement.json still points at another file. A checkout without it, or a picker
without `renders`/`Placer.globs`, cannot be asked: there QA runs the files placement.json names, and says that too.

Layout, classified per render from its alpha (8-bit, >= 250 = opaque) on >= 80 % of its frames:
  full     the whole frame is opaque
  panel    the top half is (measured y20-920: inside the panel, clear of the seam fade into y960)
  overlay  anything else

Checks:
  frames   frame count == round((end - start) x plan fps) +/- 1 (a short render leaves a hole, a long one eats the next clip)
  solid    panel/full: no frame whose panel-region alpha is under 250 (a transparent frame = a flash of raw footage)
  blank    overlay: no fully transparent frame between the first and last frame that carry ink
  stray    every layout: no one-frame flash anywhere in the render, the frames solid/blank/ink already named left
           out: workflows/flash-scan.py's render_scan() (the overlay over mid-grey, measured over the pixels it ever
           covers; FLASH on the pixels AND on the content, so a stray frame inside a moving graphic is caught: a member's
           ranking video, 2026-10-13). The render's first and last frames have one neighbour and are not asked
  ink      panel/full: the panel body's bright-pixel fraction (gray > 110) must not COLLAPSE: a frame under 35 % of the
           median of the 3 frames on BOTH sides (10 % on a cell whose plan `family` is "authored": an authored swap
           passes through a frame where the incoming element is still small, so only next to NO content is a blank
           there; a capture keeps 35 %, and so does a cell with no `family`). The render's first and last 2 frames are exempt (an entrance or an
           exit has only one side), and so is a blank (one such frame, or a run of them) whose neighbours differ by
           more than 2x (a designed swap or fade passes through a near-empty frame with a dim frame on one side and
           new content on the other). A run is judged by the frames just outside it, so a 2-frame blank still FAILs
  band     panel/overlay: no graphic ink inside the caption band, every frame. The band is --band, else the preset's own
           caption box (Talking Head Explainer: the split-frame strip above the seam, GATE_BAND in
           presets/instagram/talking-head-explainer/captions.py; TikTok/raw: the low line, read from presets/tiktok/raw/build.py). Ink on an opaque solid-colour panel = a pixel
           that differs from the panel colour by more than 40; on any other panel, gray > 70; on an overlay, any visible
           pixel. A FULL-screen covers the band by design and its captions are moved off its content (a caption-layer
           position this gate does not read), so ink there warns, naming the band; unless its plan cell carries
           "seam_clear": true, which keeps the caption ON the seam: then band ink is a collision and FAILs. A real
           capture may run on under the caption's own 90 % box (2026-10-15, three times: "the captions already
           have a background, so they can go over the graphics"): a cell whose plan `family` is "capture" and that
           carries "under_caption": true reports its band ink as an `ok` line, by design (captures.md § 4), never a
           FAIL and never a per-cell waiver. The flag is for real captures only: on any other family it still FAILs,
           saying so. An `ok` line counts in neither total and leaves the graphic's mark ✓
  cut      every plan `shot_cuts` time of the cell must change the picture ON its frame: of the body's frame-to-frame
           change above the render's own floor (its median: grain, a drift), the planned frame must carry the biggest
           within CUT_WIN frames, by CUT_RATIO; a bigger change later is the cut landing late, earlier early, and none
           at all a cut that never rendered. On a STEP_FPS render (its renders/<file>.render.json says so: an authored
           scene) the planned frame is where the 12 fps sample that frame shows lands, the frame itself or one before
           (the kit's components.Clock.cut sets it there). An authored render with no record is warned, not checked.
           Why (2026-10-14): an authored offer sheet's cut, set on its grid time 5.005 s, missed the sample its frame
           showed (5.000 s) and changed 2 frames after the caption broke; change-events.py --sync's 0.10 s tolerance
           passes 2 frames, so only a frame-exact check sees it
  copy     6 frames OCR'd (macOS: Apple Vision through a Swift shim compiled once per run; elsewhere RapidOCR through
           workflows/ocr_shim.py --joined, the same protocol); every plan `copy` word of
           >= 4 letters, and every figure of 2+ digits (read as its digits, a zero decimal tail dropped: "$2,000/mo"
           asks for 2000, so "2.000" and "$2,000.00" pass and "$20" does not; 2026-10-14: a figure-only line was never
           checked), must be read, a missing one FAILs. `copy_ocr_skip` on the cell (a list of words or figures)
           excuses what only exists as a logo. A word written only inside ( ) or < > with a lowercase word in it is a stage
           direction in practice ("(masked dots)", "<rotating word>"): missing, it warns. An aside whose every word is
           capitalised is a title's own copy ("(Full Guide)") and FAILs like the rest. With no swiftc on macOS, or an
           OCR that exits with nothing read, the check warns that it did not run.

Why (2026-09-21, a 9:16 job): with no short-form gate its step-5 renders were checked by eye, then by a job-local
script that was blind five times, each found only when a planted defect went through it:
  1. alpha read at 12 bits (yuva444p12le runs 0-4095) against an 8-bit 250: a 25 %-covered overlay passed as a solid panel
  2. a whole-frame mean-luma flash scan cannot see a BLANK chat body (a jump cut whose incoming <video> had not produced
     its first frame): a blank body barely moves the mean of a mostly dark panel, so `ink` measures the body alone
  3. dim red terminal text (gray ~90) slipped under a 110 band threshold: the band reads ink at 70
  4. a one-sided collapse test fired on every authored entrance and designed swap (8 false FAILs): the test is bilateral
  5. QA read the PLACED file while a newer render sat on disk: QA picks the newest itself
"""
import argparse, contextlib, importlib.util, io, json, math, os, platform, re, shutil, subprocess, sys, tempfile
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import numpy as np
except ImportError:
    sys.exit("graphics-qa-short.py needs numpy (uv run workflows/graphics-qa-short.py resolves it)")

REPO = Path(__file__).resolve().parent.parent
FRAME_W, FRAME_H = 1080, 1920   # the AUTHORING frame; a render may be an integer multiple of it (2160x3840)
OPAQUE = 250                    # 8-bit alpha a panel must hold
LAYOUT_SHARE = 0.80             # share of frames that decides full / panel
PANEL_Y = (20, 920)             # the top-half panel, measured inside it and clear of the seam fade
SAFE_TOP, SAFE_BOT = 200, 1620  # the short-form safe box (both short-form presets)
BODY = {'panel': (SAFE_TOP, 900), 'full': (SAFE_TOP, SAFE_BOT)}   # the panel body the ink check reads
BRIGHT, COLLAPSE, SIDE_FLOOR, EDGE_FRAMES = 110, 0.35, 0.004, 2
COLLAPSE_AUTHORED = 0.10       # a cell whose plan `family` is "authored" (the Talking Head Explainer's layout.md § 12)
EMPTY_ALPHA = 2                 # a frame whose alpha never exceeds this is fully transparent
BAND_VISIBLE, BAND_DIFF, BAND_GRAY, BAND_PX, SOLID_SHARE = 128, 40, 70, 40, 0.5
CUT_WIN, CUT_RATIO, CUT_MIN = 4, 2.0, 1.0   # frames each side (two 12 fps samples); the cut's margin; the least change
OCR_AT = (0.12, 0.3, 0.5, 0.7, 0.86, 0.97)

SWIFT_OCR = r'''
import Foundation
import Vision
import CoreGraphics
import ImageIO

// One image path per line on stdin; one "path \t all the text read" row per image.
while let line = readLine(strippingNewline: true) {
    let path = line.trimmingCharacters(in: .whitespaces)
    if path.isEmpty { continue }
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        FileHandle.standardError.write("cannot decode \(path)\n".data(using: .utf8)!); continue
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    do {
        try VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    } catch {                                  // never swallow: a silent throw reads as "nothing on screen"
        FileHandle.standardError.write("ocr failed \(path): \(error)\n".data(using: .utf8)!); continue
    }
    let text = (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
    print("\(path)\t\(text.replacingOccurrences(of: "\t", with: " ").replacingOccurrences(of: "\n", with: " "))")
}
'''


# ── the render placement.py (and place-graphics.py --plan) would pick ───────
PLACER = REPO / 'workflows' / 'placement.py'
FLASH_SCAN = REPO / 'workflows' / 'flash-scan.py'   # render_scan(): the `stray` check's one home
_flash_scan = None


def flash_scan():
    global _flash_scan
    if _flash_scan is None:
        spec = importlib.util.spec_from_file_location('flash_scan', FLASH_SCAN)
        _flash_scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_flash_scan)
    return _flash_scan


def load_picker():
    """workflows/placement.py itself (its `renders` and `Placer.globs`, which Premiere's place-graphics.py imports), so QA
    runs exactly the file the next placement lays and the rule has ONE home. (module, None), or (None, why) when it is
    not in this checkout (an older package kept the picker in the Premiere lane), it will not load, or it has no
    `renders`/`Placer.globs`: QA then runs the placed files, and says so."""
    if not PLACER.exists():
        return None, (f'no {PLACER.name} in this checkout (and no Premiere lane picker to fall back on), so no --plan '
                      'pick: QA runs the files placement.json names')
    spec = importlib.util.spec_from_file_location('place_graphics', PLACER)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(PLACER.parent))                      # any sibling import it makes
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(mod)
    except Exception as e:
        return None, f'{os.path.relpath(PLACER, REPO)} did not load ({type(e).__name__}: {e}): QA runs the files placement.json names'
    finally:
        sys.path.remove(str(PLACER.parent))
    if not (callable(getattr(mod, 'renders', None)) and callable(getattr(getattr(mod, 'Placer', None), 'globs', None))):
        return None, (f'{os.path.relpath(PLACER, REPO)} has no renders()/Placer.globs() to ask for its --plan pick: '
                      'QA runs the files placement.json names')
    return mod, None


# ── inputs ──────────────────────────────────────────────────────────────────
def parse_band(s):
    m = re.fullmatch(r'\s*y?(\d+)\s*-\s*y?(\d+)\s*', s or '')
    if not m or not int(m.group(1)) < int(m.group(2)) <= FRAME_H:
        sys.exit(f'--band {s!r}: give it as Y0-Y1 in the {FRAME_W}x{FRAME_H} frame, e.g. --band 908-960')
    return int(m.group(1)), int(m.group(2))


def _const(text, name, src):
    m = re.search(rf'^{name}\s*=\s*"?(\d+(?:\.\d+)?)', text, re.M)
    if not m:
        sys.exit(f'cannot read the caption geometry ({name}) from {src}: pass --band Y0-Y1')
    return float(m.group(1))


def preset_band(plan):
    """The preset's caption box as (y0, y1) in the authoring frame, read from the preset's own builder, and where
    it came from. None when the plan names no short-form preset."""
    scope = f"{plan.get('format') or ''} {plan.get('preset') or ''}".lower()
    if 'tiktok' in scope:
        src = REPO / 'presets' / 'tiktok' / 'raw' / 'build.py'
        t = src.read_text(encoding='utf-8')
        size, centre, gap, stroke = (_const(t, n, src) for n in ('CAP_SIZE', 'CAP_CENTER_Y', 'CAP_LINE_GAP', 'CAP_STROKE'))
        half = (1.2 * size + gap) / 2 + stroke     # one line: ascent + descent ~1.2 em, the line gap, the stroke
    elif 'explainer' in scope:
        # the Talking Head Explainer's captions.py owns the band (its GATE_BAND: the split-frame strip no graphic ink may
        # enter), imported by path: the one number the caption layer and this gate share
        src = REPO / 'presets' / 'instagram' / 'talking-head-explainer' / 'captions.py'
        spec = importlib.util.spec_from_file_location('th_captions', src)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            y0, y1 = (int(v) for v in mod.GATE_BAND)
        except Exception as e:
            sys.exit(f'cannot read the caption band (GATE_BAND) from {src.relative_to(REPO)} ({e}): pass --band Y0-Y1')
        return (y0, y1), f'{src.relative_to(REPO)} GATE_BAND'
    else:
        return None, None
    return (math.floor(centre - half), math.ceil(centre + half)), str(src.relative_to(REPO))


def plan_fps(plan):
    v = plan.get('fps')
    if v in (None, ''): return None
    try: return float(Fraction(str(v)))
    except (ValueError, ZeroDivisionError): sys.exit(f'graphics-plan.json fps {v!r} is not a rate (24000/1001, 30)')


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,r_frame_rate', '-of', 'json', path], capture_output=True, text=True)
    if r.returncode: return None
    try: s = json.loads(r.stdout)['streams'][0]
    except (ValueError, KeyError, IndexError): return None
    try: rate = float(Fraction(str(s.get('r_frame_rate') or '0/1')))
    except (ValueError, ZeroDivisionError): rate = 0.0                 # '0/0': a stream that declares no rate
    return dict(w=int(s.get('width') or 0), h=int(s.get('height') or 0), fps=rate)


def planes(path, k):
    """Yield (luma, alpha) per frame, 8-bit, in the authoring frame."""
    vf = ['-vf', f'scale={FRAME_W}:{FRAME_H}:flags=area'] if k != 1 else []
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, *vf, '-f', 'rawvideo', '-pix_fmt', 'ya8', '-'],
                         stdout=subprocess.PIPE)
    n = FRAME_W * FRAME_H * 2
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n: break
            f = np.frombuffer(b, np.uint8).reshape(FRAME_H, FRAME_W, 2)
            yield f[..., 0], f[..., 1]
    finally:                                   # a caller that stops early closes the pipe: ffmpeg exits on EPIPE
        p.stdout.close(); p.wait()


def band_ink(y, a):
    """(visible pixels, ink pixels on a panel) inside the band strip of one frame."""
    vis = a >= BAND_VISIBLE
    solid = y[a >= OPAQUE]
    ink = y > BAND_GRAY
    if solid.size:
        hist = np.convolve(np.bincount(solid, minlength=256), np.ones(9), 'same')   # the panel colour, +/- 4 levels
        bg = int(hist.argmax())
        if hist[bg] >= SOLID_SHARE * solid.size:
            ink = np.abs(y.astype(np.int16) - bg) > BAND_DIFF
    return int(vis.sum()), int((vis & ink).sum())


def collapses(bright, thr=COLLAPSE):
    """Frames where the panel body's content collapses against BOTH sides (see the docstring's `ink`). Consecutive
    collapsed frames are ONE blank and are judged by the frames just outside it: a two-frame blank at a jump cut has a
    collapsed frame on one side of each of its frames, so a per-frame neighbour test would call it a designed swap. An
    EMPTY frame (<= SIDE_FLOOR) beside the run is part of the blank too, so the judges are the first frames with content:
    a 3-frame blank's outer frames are candidates to no side, and their residues (0.001 vs 0.003) would otherwise read
    as a swap and pass it, while a designed swap through 3 empty frames (0 vs 0) would FAIL."""
    cand = []
    for i in range(EDGE_FRAMES, len(bright) - EDGE_FRAMES):
        sides = [sorted(x)[len(x) // 2] for x in (bright[max(0, i - 3):i], bright[i + 1:i + 4])]
        if all(m > SIDE_FLOOR and bright[i] < thr * m for m in sides): cand.append(i)
    out, k = [], 0
    while k < len(cand):
        lo = hi = cand[k]
        while k + 1 < len(cand) and cand[k + 1] == hi + 1: k += 1; hi += 1
        while lo > 0 and bright[lo - 1] <= SIDE_FLOOR: lo -= 1
        while hi < len(bright) - 1 and bright[hi + 1] <= SIDE_FLOOR: hi += 1
        if 0 < lo and hi < len(bright) - 1:                                # a blank that reaches the edge is an entrance/exit
            before, after = bright[lo - 1], bright[hi + 1]
            if min(before, after) >= 0.5 * max(before, after):             # else a designed swap or fade
                out += range(lo, hi + 1)
        while k < len(cand) and cand[k] <= hi: k += 1
    return out


def cut_frame(k, fps, step=None):
    """The render frame a picture cut planned on frame k must change on: k at the timeline rate. A STEP_FPS render is
    sampled at `step` fps and held up to the grid by ffmpeg's fps filter, which puts sample j on frame
    floor(j x fps / step + 1/2), so frame k shows the last sample landed by it: the cut changes where that sample lands."""
    if not step or step >= fps:
        return k
    fps = Fraction(fps).limit_denominator(1001000)
    lands = lambda j: math.floor(Fraction(j) * fps / step + Fraction(1, 2))
    j = math.floor(Fraction(k) * step / fps) + 1
    while j > 0 and lands(j) > k:
        j -= 1
    return lands(j)


def cut_lands(moved, k, e):
    """The render frame the picture change of a cut planned on frame k lands on: e (cut_frame) when e carries the biggest
    change within CUT_WIN frames of k, by CUT_RATIO, else the frame that does; None when nothing there changes by CUT_MIN.
    moved[i] = the body's change from frame i-1 to i, above the render's floor."""
    window = range(max(1, k - CUT_WIN), min(len(moved) - 1, k + CUT_WIN) + 1)
    if not window or max(moved[i] for i in window) < CUT_MIN:
        return None
    big = max(window, key=lambda i: moved[i])
    return e if moved[big] <= CUT_RATIO * (moved[e] if e in window else 0.0) else big


ASIDE = re.compile(r'\([^()]*\)|<[^<>]*>')
FIGURE = re.compile(r'\d+(?:[.,]\d+)*')                # a figure as written: 2,000 · 10.000 · 2.5 · 2,000.00


def figure(s):
    """what a figure is compared by: its digits, a zero decimal tail dropped (a checkout's "$2,000.00" is the plan's
    "$2,000"; "10.000" keeps its three)"""
    return re.sub(r'\D', '', re.sub(r'[.,]0{1,2}$', '', s))


def copy_tokens(cell):
    """(words that must be read, words only inside a stage direction). A word is 4+ letters, lowercased; a figure is a
    run of 2+ digits with its separators, as the plan writes it ("2,000" out of "$2,000/mo"), read by figure(). A plan
    writes stage directions in ( ) or < > ("(masked dots)", "<rotating word>"), so a word found nowhere else is asked
    about, never failed. An aside whose every word is capitalised ("(Full Guide)", "(Brand + Product)") is on-screen
    copy, a title's own parenthetical, and must be read like the rest."""
    skip = cell.get('copy_ocr_skip') or []
    skip = [str(s) for s in ([skip] if isinstance(skip, str) else skip)]
    skip_w = {w.lower() for s in skip for w in re.findall(r'[A-Za-z]+', s)}
    skip_f = {figure(f) for s in skip for f in FIGURE.findall(s)}
    copy, asides, shown = cell.get('copy') or '', [], []
    titled = lambda s: all(w[0].isupper() for w in re.findall(r'[A-Za-z]+', s)) and re.search(r'[A-Za-z]', s)
    while ASIDE.search(copy):                          # innermost first, so a nested aside comes out whole
        for a in ASIDE.findall(copy): (shown if titled(a) else asides).append(a)
        copy = ASIDE.sub(' ', copy)

    def words(s, have=()):
        figs = {}
        for f in FIGURE.findall(s):
            if len(figure(f)) >= 2 and figure(f) not in skip_f | {figure(h) for h in have}: figs.setdefault(figure(f), f)
        return ({w.lower() for w in re.findall(r'[A-Za-z]{4,}', s)} - skip_w) | set(figs.values())
    must = words(' '.join([copy, *shown]))
    return sorted(must), sorted(words(' '.join(asides), must) - must)


LAYOUT_PY = REPO / 'presets' / 'instagram' / 'talking-head-explainer' / 'layout.py'


def variant_plan(job, variant):
    """A second deliverable's whole plan: graphics-plan.<v>.json, else graphics-plan.json's variants.<v> composed by the
    preset's layout.compose_variant (the placer composes it the same way)."""
    vp, pp = job / f'graphics-plan.{variant}.json', job / 'graphics-plan.json'
    if vp.exists():
        with open(vp, encoding='utf-8') as fh:
            return json.load(fh)
    if not pp.exists():
        sys.exit(f'no graphics-plan.{variant}.json and no graphics-plan.json in {job}')
    with open(pp, encoding='utf-8') as fh:
        plan = json.load(fh)
    if variant not in (plan.get('variants') or {}):
        sys.exit(f'no graphics-plan.{variant}.json in {job}, and graphics-plan.json has no variants.{variant}')
    spec = importlib.util.spec_from_file_location('th_layout_qa', LAYOUT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.compose_variant(plan, variant)


class ShortQA:
    def __init__(self, job, band=None, variant=None):
        self.job = Path(job).resolve()
        self.hf = self.job / 'hf-graphics'
        self.variant = variant
        tag = f'.{variant}' if variant else ''
        pj, pp = self.hf / f'placement{tag}.json', self.job / 'graphics-plan.json'
        for p in (pj,) + (() if variant else (pp,)):
            if not p.exists(): sys.exit(f'no {p.relative_to(self.job)} in {self.job}')
        with open(pj, encoding='utf-8') as fh:
            self.rows = [r for r in json.load(fh) if r.get('id') != 'captions' and r.get('kind') != 'captions']
        if variant:
            self.plan = variant_plan(self.job, variant)
        else:
            with open(pp, encoding='utf-8') as fh:
                self.plan = json.load(fh)
        self.cells = {b['id']: b for b in self.plan.get('beats') or [] if b.get('id')}
        self.fps = plan_fps(self.plan)
        self.band, self.band_src = (band, '--band') if band else preset_band(self.plan)
        wp = self.hf / 'qa-waivers.json'
        self.waivers = {}
        if wp.exists():
            with open(wp, encoding='utf-8') as fh:
                self.waivers = json.load(fh)
        self._tmp = tempfile.TemporaryDirectory(prefix='gqa-short-')
        self.tmp = Path(self._tmp.name)
        self._ocr = None                               # the compiled shim, or the reason there is none
        self.picker, self.picker_note = load_picker()

    def close(self):
        self._tmp.cleanup()

    def ocr_bin(self):
        if self._ocr is None:
            if platform.system() != 'Darwin':
                # RapidOCR through workflows/ocr_shim.py, the same "path \t text" protocol (Windows, 2026-09-27)
                self._ocr = ['uv', 'run', '-q', str(REPO / 'workflows' / 'ocr_shim.py'), '--joined']
            elif not shutil.which('swiftc'):
                self._ocr = 'no swiftc (xcode-select --install)'
            else:
                src, out = self.tmp / 'ocr.swift', self.tmp / 'ocr'
                src.write_text(SWIFT_OCR, encoding='utf-8')
                r = subprocess.run(['swiftc', '-O', str(src), '-o', str(out)], capture_output=True, text=True)
                self._ocr = [str(out)] if r.returncode == 0 else f'the OCR shim did not compile: {(r.stderr or r.stdout).strip()[:200]}'
        return self._ocr

    def pick(self, r):
        """The render --plan would pick now, and the notes to print (place-graphics' own ⚠ lines, a stale row)."""
        if not self.picker: return r.get('file'), []
        gid, kind = r['id'], {'alpha': 'overlay'}.get(r.get('kind'), r.get('kind') or 'overlay')
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            c = self.picker.renders(*self.picker.Placer.globs(SimpleNamespace(hf=self.hf, variant=self.variant), gid, kind), gid=gid)
        notes = [l.strip() for l in said.getvalue().splitlines() if l.strip()]
        if not c: return r.get('file'), notes
        f = c[-1]
        if r.get('file') and os.path.realpath(r['file']) != os.path.realpath(f):
            notes.append(f"placement.json points at {os.path.basename(r['file'])}, --plan would pick {os.path.basename(f)} "
                         'now: QA ran that one (re-place: workflows/placement.py --write, or on Premiere '
                         'place-graphics.py --plan --write, then --apply)')
        return f, notes

    def check_row(self, r):
        gid = r['id']
        res = dict(id=gid, layout='?', frames=0, findings=[], file=None)

        def note(check, level, msg):
            w = (self.waivers.get(gid) or {}).get(check)
            if w and level in ('FAIL', 'warn'): level, msg = 'waived', f'{msg}  [waived: {w}]'
            res['findings'].append((check, level, msg))

        f, notes = self.pick(r)
        res['file'] = f
        for m in notes: note('render', 'warn', m)
        if not f or not os.path.exists(f):
            note('render', 'FAIL', f'render missing: {f}'); return res
        pr = probe(f)
        if not pr:
            note('render', 'FAIL', f'ffprobe cannot read {f}'); return res
        k = pr['w'] // FRAME_W if pr['w'] >= FRAME_W else 0
        if not k or (pr['w'], pr['h']) != (k * FRAME_W, k * FRAME_H):
            note('render', 'FAIL', f"{os.path.basename(f)} is {pr['w']}x{pr['h']}: this gate measures 9:16 renders at "
                 f'{FRAME_W}x{FRAME_H} or an integer multiple (2160x3840); a 16:9 render gates on graphics-qa.py')
            return res
        fps = self.fps or pr['fps']
        if not fps:
            note('frames', 'FAIL', f'{os.path.basename(f)} reports no frame rate and graphics-plan.json has no fps: '
                 'nothing to hold the render to'); return res
        t0 = round(float(r['start']) * fps)
        where = lambda i: f'render frame {i} = timeline frame {t0 + i}'

        full, top, amax, bright, band = [], [], [], {L: [] for L in BODY}, []
        moved, prev = {L: [0.0] for L in BODY}, None          # the body's change from the frame before (the cut check)
        for y, a in planes(f, k):
            full.append(a.mean()); top.append(a[PANEL_Y[0]:PANEL_Y[1]].mean()); amax.append(int(a.max()))
            y4 = y.reshape(FRAME_H // 4, 4, FRAME_W // 4, 4).mean(axis=(1, 3))
            for L, (b0, b1) in BODY.items():
                bright[L].append(float((y4[b0 // 4:b1 // 4] > BRIGHT).mean()))
                if prev is not None:
                    moved[L].append(float(np.abs(y4[b0 // 4:b1 // 4] - prev[b0 // 4:b1 // 4]).mean()))
            prev = y4
            if self.band:
                band.append(band_ink(y[self.band[0]:self.band[1]], a[self.band[0]:self.band[1]]))
        n = res['frames'] = len(full)
        if not n:
            note('render', 'FAIL', f'no frames decoded from {f}'); return res

        # frames: the render fills its row exactly
        want = round((float(r['end']) - float(r['start'])) * fps)
        if abs(n - want) > 1:
            note('frames', 'FAIL', f"render has {n} frames ({pr['fps']:.3f} fps), the row spans {want} at {fps:.3f} "
                 f"({float(r['start']):.3f}-{float(r['end']):.3f}s): a short render leaves a hole, a long one eats the next clip")

        L = 'full' if sum(v >= OPAQUE for v in full) >= LAYOUT_SHARE * n else \
            'panel' if sum(v >= OPAQUE for v in top) >= LAYOUT_SHARE * n else 'overlay'
        res['layout'] = L

        named = set()                                   # frames solid/blank/ink report: `stray` leaves them out
        if L in ('panel', 'full'):
            region = full if L == 'full' else top
            bad = [i for i, v in enumerate(region) if v < OPAQUE]
            if bad:
                note('solid', 'FAIL', f'{len(bad)} frame(s) where the opaque {L} is not solid (first: {where(bad[0])}, '
                     f'alpha {region[bad[0]]:.0f}): raw footage flashes through')
            fam = (self.cells.get(gid) or {}).get('family')
            holes = collapses(bright[L], COLLAPSE_AUTHORED if fam == 'authored' else COLLAPSE)
            if holes:
                note('ink', 'FAIL', f"{len(holes)} frame(s) where the {L} body's content collapses against both sides "
                     f"(first: {where(holes[0])}; render frames {holes[:6]})")
            named.update(bad, holes)
        else:
            inked = [i for i, v in enumerate(amax) if v > EMPTY_ALPHA]
            holes = [i for i in range(inked[0], inked[-1] + 1) if amax[i] <= EMPTY_ALPHA] if inked else []
            if holes:
                note('blank', 'FAIL', f'{len(holes)} fully transparent frame(s) inside the graphic\'s life '
                     f'(first: {where(holes[0])})')
            named.update(holes)

        try:
            stray = [(i, what) for i, what in flash_scan().render_lines(flash_scan().render_scan(f)) if i not in named]
        except flash_scan().InputError as e:
            stray = []
            note('stray', 'warn', f'not checked ({e}): read the render for one-frame flashes by eye')
        if stray:
            note('stray', 'FAIL', f'{len(stray)} one-frame flash(es) in the render (first: {where(stray[0][0])} '
                 f'{stray[0][1]}; render frames {[i for i, _ in stray][:6]})')

        if self.band:
            hit = [i for i, (vis, ink) in enumerate(band) if (vis if L == 'overlay' else ink) > BAND_PX]
            seam = bool((self.cells.get(gid) or {}).get('seam_clear'))
            under = bool((self.cells.get(gid) or {}).get('under_caption'))
            fam = (self.cells.get(gid) or {}).get('family')
            if hit and L == 'full' and seam:           # the plan kept the caption ON the seam over this full-screen
                note('band', 'FAIL', f'graphic ink inside the caption band y{self.band[0]}-{self.band[1]} on {len(hit)} '
                     f'frame(s) (first: {where(hit[0])}): the cell says "seam_clear": true, so the caption sits on the '
                     'seam here and collides (layout.md § 12, L-CAPY)')
            elif hit and L == 'full':                  # the whole frame is the graphic: where its captions sit is the caption layer's call
                note('band', 'warn', f'full-screen ink inside the caption band y{self.band[0]}-{self.band[1]} on {len(hit)} '
                     f'frame(s) (first: {where(hit[0])}): the captions on this span must sit off it (not checked here)')
            elif hit and under and fam == 'capture':   # a real screen the caption's own box sits over, by the plan's call
                note('band', 'ok', f'capture ink under the caption band y{self.band[0]}-{self.band[1]} on {len(hit)} '
                     'frame(s), by design: the cell says "under_caption": true, so the page runs on under the caption\'s '
                     'own box (captures.md § 4)')
            elif hit and under:
                note('band', 'FAIL', f'graphic ink inside the caption band y{self.band[0]}-{self.band[1]} on {len(hit)} '
                     f'frame(s) (first: {where(hit[0])}): "under_caption" applies only to a real capture (family '
                     f'"capture"), and this cell\'s family is {fam!r}: lift, scale or reframe it (layout.md § 8)')
            elif hit:
                note('band', 'FAIL', f'graphic ink inside the caption band y{self.band[0]}-{self.band[1]} on {len(hit)} '
                     f'frame(s) (first: {where(hit[0])})')

        cell = self.cells.get(gid)
        if cell and cell.get('shot_cuts'):
            self.check_cuts(f, r, cell, moved['full' if L == 'full' else 'panel'], fps, where, note)
        if cell is None:
            note('copy', 'warn', 'no graphics-plan.json cell with this id: its copy is not checked')
        elif any(copy_tokens(cell)):
            self.check_copy(f, cell, n, pr['fps'] or fps, note)
        return res

    def check_cuts(self, f, r, cell, moved, fps, where, note):
        rec = Path(f + '.render.json')
        try:
            step = int(json.loads(rec.read_text(encoding='utf-8')).get('STEP_FPS') or 0) or None
        except (OSError, ValueError):
            if cell.get('family') == 'authored':
                note('cut', 'warn', f'not checked: no {rec.name} to say whether the render is stepped (render it through '
                     'kit/engine.py render)'); return
            step = None                                 # a capture, a montage, an overlay: the timeline rate
        floor = float(np.median(moved[1:])) if len(moved) > 1 else 0.0
        moved = [max(0.0, v - floor) for v in moved]
        for t in cell['shot_cuts']:
            kc = round((float(t) - float(r['start'])) * fps)
            if not 0 < kc < len(moved):
                continue                                # a cut outside the render is the frames check's business
            e = cut_frame(kc, fps, step)
            got = cut_lands(moved, kc, e)
            at = f'shot cut {float(t):.3f}s ({where(kc)})'
            why = (f'; on a {step} fps render the change belongs on frame {e}, where the sample frame {kc} shows lands '
                   '(an authored cut set on its grid time misses it: components.Clock.cut lands it)') if step else ''
            if got is None:
                note('cut', 'FAIL', f'{at}: the picture does not change within {CUT_WIN} frames of it{why}')
            elif got != e:
                note('cut', 'FAIL', f'{at}: the picture changes on render frame {got}, {abs(got - e)} frame(s) '
                     f"{'late' if got > e else 'early'}{why}")

    def check_copy(self, f, cell, n, fps, note):
        must, aside = copy_tokens(cell)
        ocr = self.ocr_bin()
        if not isinstance(ocr, list):
            note('copy', 'warn', f'not checked ({ocr}): read {len(must + aside)} plan word(s) off the render by eye'); return
        shots = []
        for j, frac in enumerate(OCR_AT):
            png = self.tmp / f"{cell['id']}-{j}.png"
            png.unlink(missing_ok=True)                # a frame that does not extract must not read an older one
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{min(n - 1, int(frac * n)) / fps:.3f}', '-i', f,
                            '-frames:v', '1', '-vf', f'scale={FRAME_W}:{FRAME_H},format=rgb24', str(png)], capture_output=True)
            if png.exists(): shots.append(str(png))
        r = subprocess.run(ocr, input='\n'.join(shots) + '\n', capture_output=True, text=True, encoding='utf-8')
        read = [l for l in r.stdout.splitlines() if '\t' in l]    # one "path \t text" row per frame the OCR READ
        why = (r.stderr or '').strip()[-160:]
        if not read:
            # Nothing read is "not checked", never a FAIL on every plan word. A shim that could not start exits non-zero;
            # one whose OCR failed on every frame exits 0 with no rows (the Windows re-test, 2026-09-27: 'hbada' FAILed)
            note('copy', 'warn', f'not checked (the OCR read none of {len(shots)} frame(s)'
                 f'{f", exit {r.returncode}" if r.returncode else ""}: {why}): read {len(must + aside)} plan word(s) off '
                 'the render by eye'); return
        text = ' '.join(l.partition('\t')[2] for l in read)
        seen, figs = re.sub(r'[^a-z]', '', text.lower()), {figure(f) for f in FIGURE.findall(text)}
        found = lambda t: figure(t) in figs if t[0].isdigit() else t in seen     # a figure is read whole (figure())
        miss = [t for t in must if not found(t)]
        if miss and len(read) < len(shots):                       # the word may be on a frame it could not read
            note('copy', 'warn', f'not checked: {len(miss)}/{len(must)} plan word(s) not read on the {len(read)} of '
                 f'{len(shots)} OCR frame(s) it could read ({why}): {miss[:12]}: read them off the render by eye')
        elif miss:
            note('copy', 'FAIL', f'{len(miss)}/{len(must)} plan word(s) not read on {len(shots)} OCR frame(s): {miss[:12]} '
                 '(a word that only exists as a logo goes in the cell\'s copy_ocr_skip)')
        miss = [t for t in aside if not found(t)]
        if miss:
            note('copy', 'warn', f'{len(miss)} word(s) written in ( ) or < > not read: {miss[:12]} (a stage direction, '
                 'or on-screen copy that did not render?)')


def main(argv=None):
    ap = argparse.ArgumentParser(description='the 5b->5c gate for 9:16 renders')
    ap.add_argument('job')
    ap.add_argument('ids', nargs='*', help='check only these graphics')
    ap.add_argument('--band', help='the caption band Y0-Y1 in the 1080x1920 frame (default: the preset\'s caption box)')
    ap.add_argument('--variant', metavar='NAME', help='a second deliverable: hf-graphics/placement.NAME.json, and its plan '
                    '(graphics-plan.NAME.json, else graphics-plan.json variants.NAME composed)')
    a = ap.parse_args(argv)
    qa = ShortQA(a.job, parse_band(a.band) if a.band else None, a.variant)
    try:
        rows = [r for r in qa.rows if not a.ids or r['id'] in a.ids]
        head = [f'{g}: no such row in hf-graphics/placement.json' for g in sorted(set(a.ids) - {r['id'] for r in qa.rows} - {'captions'})]
        if qa.band: print(f'caption band y{qa.band[0]}-{qa.band[1]} ({qa.band_src})')
        else: head.append("band: graphics-plan.json names no short-form preset (format/preset): pass --band Y0-Y1, not checked")
        if qa.fps is None: head.append("graphics-plan.json has no fps: each render is held to its own rate")
        if qa.picker_note: head.append(qa.picker_note)
        for m in head: print(f'⚠ {m}')
        fails, warns = 0, len(head)                    # a check that did not run is a warn in the total, not only a line
        for r in rows:
            res = qa.check_row(r)
            fs = res['findings']
            fails += sum(1 for x in fs if x[1] == 'FAIL'); warns += sum(1 for x in fs if x[1] == 'warn')
            mark = '✗' if any(x[1] == 'FAIL' for x in fs) else ('⚠' if any(x[1] != 'ok' for x in fs) else '✓')
            print(f"{mark} {res['id']:<6} {res['layout']:<7} {res['frames']:>4}f  {os.path.basename(res['file'] or '?')}")
            for check, level, msg in fs:
                print(f'    {level:<6} {check:<6} {msg}')
        print(f'\n{fails} FAIL · {warns} warn · {len(rows)} graphics')
        return 1 if fails else 0
    finally:
        qa.close()


if __name__ == '__main__':
    sys.exit(main())
