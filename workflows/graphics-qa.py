#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""graphics-qa.py: the build-time QA gate between the graphics BUILD (5b) and the REVIEW loop (5c).

  uv run workflows/graphics-qa.py projects/<job> [--ids g1,g2] [--json hf-graphics/qa-report.json] [--fps 24000/1001]
  (uv resolves numpy from the header; plain python3 works where numpy is installed; --selftest lints two fixtures offline)

Exit 1 on any FAIL: the handoff to edit-review is blocked until it is green. Everything it owns is
OFF-LIMITS to the LLM reviewers, they review intent, copy and depiction; this sweeps every frame.

Why: most review-round defects are deterministic, so this sweeps them in seconds instead of burning
review rounds on them. Long-form 16:9 only — the geometry is authored at 1920x1080 and a 4K render of the same design (3840x2160,
the 1080 layout on a `scale(2)` stage, never `#root{zoom:2}`, 2026-09-07) is measured in that frame by scaling the planes down, so it refuses
any other frame size rather than hand back a false green.

Inputs (all in the job folder): hf-graphics/placement.json (the placement manifest, one row per placed
graphic: {id, file, start, end, kind: text|full|overlay, track}; `uv run workflows/placement.py <job> --write`
writes it on any lane, and the Premiere lane's place-graphics.py --plan --write is the same derivation),
graphics-plan.json, transcript/cuts.json (V1 cut points = cumulative kept durations), the comps under
hf-graphics/*/compositions/, the renders those rows point at, and hf-graphics/qa-waivers.json:
  {"g18": {"band": "its lowest bounce frame sits ON y1030 by design"}, "g16": {"source:overshoot": "the chip sits BEHIND the node"}}
A waiver replaces a prose "deliberate deviation" in the build report: machine-read, named per check (or
per `check:tag`, the narrower key a tagged FAIL answers to first), shown in the report as `waived`, so a
reviewer cannot dismiss a real defect on a sentence (round 2 dismissed a real 83 ms cut-end flash that way).
A waiver silences a FAIL **or a warn**; `info` is never waived. A deviation the build justified once is
recorded once: before 2026-09-19 a waiver only answered a FAIL, so every warn-level deviation was
re-adjudicated from scratch by every review round (11 dead entries in one job's waiver file).

Checks (per placed graphic unless noted):
  render     file exists · overlay = ProRes 4444 alpha, full-screen = opaque mp4 · fps == the timeline's
  duration   placed length vs the render's, within 1.5 frames (a trim means an exit was cut off); a STEPPED
             render (bg-dark, STEP_FPS=12) may sit up to one step (2 frames) long — render.sh's `fps=` expansion
             pads it and the placer trims it back to the authored span by design
  parity     a placed render that has a sibling VERSION at another resolution (g6-k.mp4 at 4K beside g6.mp4 at 1080)
             must be the same picture: workflows/render-diff.py against the newest such sibling (2026-09-07: three
             4K punch-cuts shipped 77x43 px off-centre under `#root{zoom:2}`, reported pixel-identical, unmeasured)
  band       overlays: no ink below the band floor (y1030), none within 80 px of the left/right edge (100 top),
             low-band graphics never above the band top, EVERY frame of the render (alpha sweep)
  face       side callouts (region callout-L/R): on every hold frame the ink stays 60 px off the head, ears
             included, as measured per window by chin-line.py --edl and carried in the plan cell as `head`
             (2026-09-10: g7, g12, g30 sat on his ear for a whole shipped video, the zone was picked, never measured)
  exit       overlays: the last rendered frame is EMPTY (hard-kill) unless the V1 cut is the exit
  stray      every render: no one-frame flash anywhere in it (workflows/flash-scan.py's
             render_scan(): an overlay over mid-grey, measured over the pixels it ever covers; FLASH on the pixels AND
             on the content, so a frame that blanks or jumps back to an earlier state INSIDE a move is caught: a member's
             ranking video, 2026-10-13, "it flashed a little bit ... only does that sometimes"). A graphic whose source
             strobes (the registry's `flash(`, a text animation's "flicker" entrance) is built of one-frame pulses, so
             there it warns, naming the frames to read
  lead       full-screens: static lead frames before the first element arrives (frame-0 rule)
  grain      full-screens carry the film-grain pass (section titles are exempt), measured off the pixels that
             are not clipped at black (a near-black window clips half the luma noise and read 0.82 with the pass on)
             and on the first LIT frame of its opening 3 s, never frame 0 alone (one that opens on black — a
             fade-in, a dark scene's first beat — is measured where it has picture instead of abstaining)
  dynamics   full-screens: share of its life that sits still on the 12 fps grid (warn over 60 %) + the count of big visual beats
  rack       full-screens: when the centre darkens (a rack focus) the frame edges darken with it, else the racked
             layer sits inside the scaled content. Read on the frame where the EDGES are darkest — the dim layer's
             own settled state — since the recipe lands bright type dead centre over the racked scene. A declared
             #racked with no dim at all WARNS on either field: on a dark one that can also be a correct blur-ladder
             rack, so a wired rack there is a `rack` waiver, but the question is always asked
  centre     full-screens: on the fullest frame the whole composed box centres within 40 px horizontally (FAIL) and every ink
             ROW (words + the prop beside them are ONE row) within 40 px — FAIL on a text punch-cut, warn on a scene (a window's
             title bar, the chip row under one side of a diagram); the vertical box centre warns (2026-09-13: g5's words were
             centred, the props beside them hung off the right end, two rows 100/116 px right); a deliberate deviation waives
             `centre:row` / `centre:box`. AND every SETTLED state after a camera/scale move or a scene change centres within
             40 px on BOTH axes and stays inside the frame (FAIL, waived `centre:settled`): a 12 fps sample that keeps under
             half the previous one's ink in place starts a new phase, and a phase's box is the union of what settles in it,
             so a slot reserved early and filled later in the same phase is part of it (2026-10-06: f02-b's late push, scale
             1.12 about 50% 72% plus y −110, parked the comment panel off the top edge for its last 34 frames, ~120 px above
             centre, and passed, because the fullest frame was a pre-push one). A phase no move led into stays the fullest
             frame's: a hollow dark window's bottom edge is invisible to this ink, which is why that vertical only warns
  margin     full-screens: no ink within 100 px of the top or bottom edge or 80 px of a side that HOLDS STILL there (in
             place within 2 px of the frame before) for 0.25 s, on any frame of the render; a pass through the edge (a scene
             sliding in from off-screen crosses it in 1-5 frames) is exempt, the way a slide is on an overlay's `band`
             (f02-b's 'Comments' header sat at y~70 for 31 frames)
             (lead, the centre ROWS, the settled states and `margin` do not run on FOOTAGE — a capture or a generated b-roll
             clip has no authored entrance and no centred type, fills the frame, and its zooms are the app's, the way grain
             exempts a section title. `dynamics` is exempt on a REAL
             capture only — a recorded file, by kind or by the `capture`/captures asset it names — because a
             screen recording's motion is the app's, while a generated clip that sits still is a finding)
  cut      a full-screen (or a text animation whose exit is the cut) that ends within 8 frames of a V1 cut
             must end ON it, EXACTLY: a frame above flashes the outgoing shot, a hair below floors to the
             tick and lands short; ending far from any cut (a cut back mid-take, g14) is a choice and passes
  holes      overlays on one track: overlaps (FAIL) and sub-3-frame gaps between neighbours (warn). Measured
             PER TRACK, always: two graphics that overlap on DIFFERENT tracks are a hard-cut exit, the
             reviewer's to read on the render, never a gate finding
  plan       every plan graphic is placed and vice versa; start/end agree within 1.5 frames
  hero       a cell with "hero_frame" (a still of the creator CAST by workflows/hero-frame.py --pick): the comp's <img> is that file
  copy       text-animation phrase == the plan's copy · no U+2014 in any on-screen copy
  font       every @font-face url() in a comp is a file under its render root (the folder above compositions/): a missing
             one renders exit 0 in a fallback face, Times where the family is not installed (2026-10-13)
  source     hand comps: helpers defined or hf-anim.js loaded · registry constants exact · riseOut relative · a riseIn's distance (22 on a card, the type ratio at 90 px+, rise-dist) · pop() never on type ·
             float() on a wrapper over 0 → DUR · 12 fps form on bg-dark · no flash at 12 fps · no Math.random /
             onUpdate · no CSS filter-string tween · content reveals pin the zero frame · arrowheads computed ·
             position:absolute with no offsets · a pop's overshoot clears its neighbours · exits never before entrances ·
             an element parked outside an overflow:hidden ancestor (clip) · an opacity:0 element no script ever
             touches (unlit) · rows split across source lines under white-space:pre (pre-rows) · an overlay box
             whose registry TRAVEL leaves the band or the edge margin (clearance) · the overshoot again on RENDERED INK, every
             frame of it, against every neighbour incl. type and SVG-wrapped props (workflows/overshoot-ink.mjs: node + a
             headless Chrome, one per run; missing = a warn, never a silent pass)
  density    (job) events/min, longest bare stretch, full-screen share + rate + SPREAD (≤ 40 s without one), same field twice
             in a row — all of it over the plan's `graphics_scope` ranges when it has them, else the whole runtime
Not here (the reviewers own them): copy meaning, depiction (card vs scene), asset contrast on its plate,
glow spill outside a prop's box, reveal burst cadence on the render.
"""
import json, os, re, subprocess, sys, glob, math, tempfile, shutil, importlib.util
from html.parser import HTMLParser
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
RENDER_DIFF = Path(__file__).resolve().parent / 'render-diff.py'   # the parity proof, same folder
FLASH_SCAN = Path(__file__).resolve().parent / 'flash-scan.py'     # render_scan(): the `stray` check's one home
OVERSHOOT_INK = Path(__file__).resolve().parent / 'overshoot-ink.mjs'   # the overshoot on RENDERED ink (headless Chrome), same folder

try:
    import numpy as np
except ImportError:
    sys.exit("graphics-qa.py needs numpy (uv run workflows/graphics-qa.py resolves it, or: brew install numpy)")

FRAME_W, FRAME_H = 1920, 1080   # the AUTHORING frame every number below lives in; a render may be an integer
                                # multiple of it (3840x2160 on a 4K job) and is measured after scaling back down
EDGE, TOP_EDGE = 80, 100   # side margin: default-overlay-style.md § Placement (80, the user 2026-09-10; was 100)
SUBJECT = 60               # px a side callout keeps off the head, ears included (default-overlay-style.md § SIDE CALLOUTS)
ALPHA_INK = 160           # 0-255 on a 4x-downscaled alpha plane: solid ink: a glow or shadow bleeding past the box is not ink
ALPHA_ANY = 40            # anything at all (the last-frame emptiness check)
INK_OVER = 4.0            # px² in the authoring frame: a pop/slam's grown ink this far into a neighbour's ink is a collision (g9's
                          # controller over the 'r' of "or": 27.8 at scale 1.10 and 0 at rest), and an overlap this big AT REST is authored
GRAIN_MIN = 0.9           # mean |frame − 3x3 median| on a full-screen's first frame; the grain pass sits ~2-4
GRAIN_FLOOR = 12          # luma below this is clipped at black and carries no noise: those pixels are not measured
CENTRE_MAX = 40           # px in the authoring frame a full-screen's ink row or whole box may sit off the frame centre (creative-moves move 2
                          # § CENTRED MEANS THE COMPOSED ROW; g5's prop-carrying rows measured +100/+116, its centred rows ±6)
MOVE_KEEP = 0.5           # share of the previous 12 fps sample's ink still in place (within 6 px) under which the picture MOVED: a camera
                          # or scale move, a reflow or a scene change starts a new phase (f02-b's push kept 0.12, its reveals 1.00)
SETTLE_S, SETTLE_TOL = 0.4, 12   # a SETTLED state: the ink box holds this long, each edge within this many px of the state's first sample
MARGIN_HOLD_S = 0.25      # s full-screen ink must sit still inside the edge margin to count: a scene sliding in from off-screen
                          # crosses it in 1-5 frames (f01, f06, g5 on your-job), f02-b's pushed header held 31
DENSITY = dict(per_min=(11, 13), bare_max=6.0, full_pct_max=25.0, full_gap_max=40.0, full_per_min=(2, 3))   # creative-moves § THE DENSITY NUMBERS (+ SPREAD, 2026-09-10)
REGISTRY = {  # the numbers an INLINE helper block must carry (skipped when hf-anim.js is loaded)
    'DRAW': ['DRAW = 9'],
    'float': ['subtle: [6, 8, 1.25, 0.95]', 'medium: [10, 16, 1.35, 1.05]'],
    'riseIn': ['dist = 22', '0.55', 'power3.out'],
    'riseOut': ['dist = 18', '0.35', 'power2.in'],
    'pop': ['0.90', '1.10', '3*F', 'power2.out'],
    'slam': ['1.16', 'power2.out'],
}
POP_OVER, SLAM_FROM = float(REGISTRY['pop'][1]), float(REGISTRY['slam'][0])   # the overshoot scales, from the same copy
HELPERS = ('pop', 'slam', 'flash', 'riseIn', 'riseOut', 'slideIn', 'slideOut', 'float', 'camera', 'arrow', 'drawOn', 'countUp', 'reveal', 'exit')
ENTRANCES = ('pop', 'slam', 'flash', 'riseIn', 'slideIn', 'drawOn')
EXITS = ('riseOut', 'slideOut', 'exit')


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = sh('ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
           'stream=pix_fmt,r_frame_rate,nb_frames,duration,width,height', '-of', 'json', path)
    if r.returncode: return None
    s = json.loads(r.stdout)['streams'][0]
    num, _, den = s['r_frame_rate'].partition('/')
    return dict(pix=s.get('pix_fmt'), fps=float(num) / float(den or 1),
                frames=int(s.get('nb_frames') or 0), dur=float(s.get('duration') or 0),
                w=int(s.get('width') or 0), h=int(s.get('height') or 0))


def frames(path, vf, w, h, pix='gray', n_frames=None):
    """Yield numpy frames from ffmpeg (rawvideo pipe)."""
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', vf] + (['-frames:v', str(n_frames)] if n_frames else [])
                         + ['-f', 'rawvideo', '-pix_fmt', pix, '-'], stdout=subprocess.PIPE)
    n = w * h * (1 if pix == 'gray' else 3)
    while True:
        b = p.stdout.read(n)
        if len(b) < n: break
        yield np.frombuffer(b, np.uint8).reshape(h, w) if pix == 'gray' else np.frombuffer(b, np.uint8).reshape(h, w, 3)
    p.stdout.close(); p.wait()


def ink(g):
    """A full-screen's INK on a luma frame: sharp pixel-to-pixel contrast, so the field gradient, the vignette, a glow
    bloom and the grain never count (the `centre` and settled-state measure)."""
    a = g.astype(int); m = np.zeros(a.shape, bool)
    m[:, 1:] |= np.abs(np.diff(a, axis=1)) > 28
    m[1:, :] |= np.abs(np.diff(a, axis=0)) > 28
    return m


def grow(m, r):
    """`m` dilated by r px (a square), never wrapping round the frame."""
    o = m.copy()
    for d in range(1, r + 1):
        o[:, d:] |= m[:, :-d]; o[:, :-d] |= m[:, d:]
    p = o.copy()
    for d in range(1, r + 1):
        p[d:, :] |= o[:-d, :]; p[:-d, :] |= o[d:, :]
    return p


def norm_words(s):
    return [re.sub(r"^[^\w']+|[^\w']+$", '', w).lower() for w in re.sub(r'[*~]', '', s).split() if re.sub(r"[^\w']", '', w)]


def scope_ranges(plan, dur):
    """The stretches of runtime the plan allows graphics IN — `"graphics_scope": {"ranges": [[a, b], ...]}` —
    else the whole thing. The cadence is measured over the SCOPE, never the runtime: a stretch the creator
    barred graphics from is not a density hole (creative-moves.md § THE DENSITY NUMBERS). Without this, a
    12-minute screen recording nobody may decorate produced four permanent unsatisfiable warns."""
    rs = (plan.get('graphics_scope') or {}).get('ranges') if isinstance(plan.get('graphics_scope'), dict) else None
    out = []
    for r in rs if isinstance(rs, list) else []:
        try: a, b = float(r[0]), float(r[1])
        except (TypeError, ValueError, IndexError, KeyError): continue
        if b > a: out.append((a, b))
    return sorted(out) or [(0.0, float(dur))]


def longest_gap(ranges, spans):
    """The longest stretch INSIDE the scope carrying none of `spans`. Every range is walked on its own, so
    the runtime BETWEEN two ranges is never counted as a hole."""
    worst = 0.0
    for a, b in ranges:
        prev = a
        for s, e in sorted(spans):
            if e <= a or s >= b: continue
            worst = max(worst, max(s, a) - prev); prev = max(prev, min(e, b))
        worst = max(worst, b - prev)
    return worst


# ── the comp's static geometry: enough CSS/DOM to place a box, never a browser ─────────────
class _Dom(HTMLParser):
    """Every element with its parent, id, classes and inline style. <template> children count:
    the comp clones them in at runtime."""
    VOID = {'br', 'img', 'input', 'meta', 'link', 'hr', 'source', 'use', 'path', 'circle',
            'rect', 'polygon', 'line', 'ellipse', 'stop'}

    def __init__(self, src):
        super().__init__(convert_charrefs=True)
        self.stack, self.els = [], []
        self.feed(src)

    def _add(self, tag, attrs):
        a = dict(attrs)
        el = dict(tag=tag, id=a.get('id'), cls=(a.get('class') or '').split(), line=self.getpos()[0],
                  style=a.get('style') or '', parent=self.stack[-1] if self.stack else None, text='')
        self.els.append(el); return el

    def handle_data(self, data):                     # an element's OWN text (children keep theirs): is it type?
        if self.stack: self.stack[-1]['text'] += data

    def handle_startendtag(self, tag, attrs):        # `<polygon .../>`: recorded, never pushed
        self._add(tag, attrs)

    def handle_starttag(self, tag, attrs):
        el = self._add(tag, attrs)
        if tag not in self.VOID: self.stack.append(el)

    def handle_endtag(self, tag):                    # unwind to the matching open tag, never blind-pop
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]; return


def _compound(el, c):
    """Does one compound selector (`div.node.hi`, `#n3`, `.arr`) apply to el?"""
    if ':' in c or '[' in c: return False
    toks = re.findall(r'[#.][A-Za-z0-9_-]+', c)
    tag = re.match(r'^[A-Za-z][A-Za-z0-9]*', c)
    if tag and tag.group(0).lower() not in (el['tag'], '*'): return False
    if not toks and not tag and c.strip() != '*': return False
    for t in toks:
        if t[0] == '#' and t[1:] != (el['id'] or ''): return False
        if t[0] == '.' and t[1:] not in el['cls']: return False
    return True


def _sel(el, sel):
    """(ids, classes, tags) if this ONE selector branch applies to el, else None. Ancestor-aware:
    `.node .ic svg` must not paint an #a2 svg with the icon's box (it did, and hid a real overlap)."""
    sel = sel.strip()
    if '+' in sel or '~' in sel: return None                 # sibling combinators are not modelled
    parts = [p for p in re.split(r'\s*(>)\s*|\s+', sel) if p]
    if not parts or not _compound(el, parts[-1]): return None
    node, i = el['parent'], len(parts) - 2
    while i >= 0:
        if parts[i] == '>':
            i -= 1
            if node is None or i < 0 or not _compound(node, parts[i]): return None
        else:
            while node is not None and not _compound(node, parts[i]): node = node['parent']
            if node is None: return None
        node = node['parent']; i -= 1
    return (sel.count('#'), len(re.findall(r'\.[A-Za-z]', sel)), len(re.findall(r'(?:^|[\s>])[A-Za-z]', sel)))


def _decls(el, rules):
    """The cascade, best-effort: matching rules by (specificity, source order), inline style last."""
    hits = []
    for i, (sel, blk) in enumerate(rules):
        spec = None
        for branch in sel.split(','):
            sp = _sel(el, branch)
            if sp and (spec is None or sp > spec): spec = sp
        if spec: hits.append((spec, i, blk))
    d = {}
    for _, _, blk in sorted(hits, key=lambda h: (h[0], h[1])): d.update(blk)
    for k, _, v in (x.partition(':') for x in el['style'].split(';')):
        if k.strip(): d[k.strip().lower()] = v.strip()
    return d


def _px(v):
    m = re.fullmatch(r'(-?\d+(?:\.\d+)?)(px)?', (v or '').strip())
    return float(m.group(1)) if m and (m.group(2) or float(m.group(1)) == 0) else None


def _box(d):
    l, t, w, h = _px(d.get('left')), _px(d.get('top')), _px(d.get('width')), _px(d.get('height'))
    return None if None in (l, t, w, h) else (l, t, l + w, t + h)


def _shifted(d):
    """A transform moves the element off its CSS box, so the box is not where it renders (the
    left/top + translate(-50%,-50%) centring idiom): measured geometry does not apply."""
    return bool(re.search(r'translate|rotate|matrix|skew', d.get('transform') or ''))


def _origin(d, b):
    o = (d.get('transform-origin') or '50% 50%').split() or ['50%']
    if len(o) == 1: o.append('50%')
    KEY = {'left': '0%', 'top': '0%', 'center': '50%', 'right': '100%', 'bottom': '100%'}
    out = []
    for i, part in enumerate(o[:2]):
        part = KEY.get(part, part)
        span = b[2] - b[0] if i == 0 else b[3] - b[1]
        if part.endswith('%'): out.append(b[i] + span * float(part[:-1]) / 100)
        elif _px(part) is not None: out.append(b[i] + _px(part))
        else: return None
    return tuple(out)


def _ovl(a, b):
    return (min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1]))


def _name(el):
    return '#' + el['id'] if el['id'] else ('.' + '.'.join(el['cls']) if el['cls'] else '<%s>' % el['tag'])


def _args(js, i):
    """The text inside the call whose '(' sits at js[i]; quote- and paren-aware."""
    d, j, q = 0, i, ''
    while j < len(js):
        c = js[j]
        if q:
            if c == '\\': j += 2; continue
            if c == q: q = ''
        elif c in '\'"`': q = c
        elif c == '(': d += 1
        elif c == ')':
            d -= 1
            if d == 0: return js[i + 1:j]
        j += 1
    return js[i + 1:]


class QA:
    def __init__(self, job, fps=None, ids=None):
        self.job = Path(job).resolve()
        self.hf = self.job / 'hf-graphics'
        pj = self.hf / 'placement.json'
        if not pj.exists():
            sys.exit(f'{pj} missing: the placement manifest (see the docstring): uv run workflows/placement.py <job> '
                     '--write (any lane; Premiere: lanes/premiere/place-graphics.py <job> --plan --write, the same rows).')
        self.rows = json.load(open(pj, encoding="utf-8"))
        for r in self.rows:
            if r.get('kind') == 'alpha': r['kind'] = 'overlay'     # older rows named the format, not the role
        self.rows = [r for r in self.rows if r.get('kind') != 'captions']   # the caption layer is not a graphic event (and is short-form anyway)
        if ids: self.rows = [r for r in self.rows if r['id'] in ids]
        self.plan = json.load(open(self.job / 'graphics-plan.json', encoding="utf-8"))
        self.cells = {b['id']: b for b in self.plan['beats'] if b.get('graphic')}
        # a graphic split into part clips for BUILD reasons (`graphics-build` § split part clips) is ONE graphic,
        # exactly as validate-plan.py reads it: its INTERNAL seams are butt-joins, not outer boundaries, so the
        # cut gate skips them (a part's seam lands mid-take by construction and is not an edit point)
        self.inner = set()
        _parts = {}
        for c in self.cells.values():
            _parts.setdefault(c.get('part_of') or c['id'], []).append(c)
        for g in _parts.values():
            g.sort(key=lambda x: float(x.get('start') or 0))
            for i, c in enumerate(g):
                if i: self.inner.add((c['id'], 'start'))
                if i < len(g) - 1: self.inner.add((c['id'], 'end'))
        wp = self.hf / 'qa-waivers.json'
        self.waivers = json.load(open(wp, encoding="utf-8")) if wp.exists() else {}
        self.findings = []       # (id, check, level, msg)
        self.ink = []            # comps with a pop/slam, measured on rendered ink after the rows (check_overshoot_ink)
        # source: presets/youtube/default/default-overlay-style.md § THE LOW BAND
        # (the plan carries the per-shoot edges; the defaults are the reference shoot's,
        #  re-derive with workflows/chin-line.py)
        self.band_top = (self.plan.get('low_band') or {}).get('top', 765)
        self.band_floor = (self.plan.get('low_band') or {}).get('bottom', 1030)
        self.band_measured = bool(self.plan.get('low_band'))
        cuts, t = [], 0.0
        cp = self.job / 'transcript' / 'cuts.json'
        if cp.exists():
            segs = json.load(open(cp, encoding="utf-8"))['segments']
            off = float(self.plan.get('timeline_offset') or 0.0)
            if segs and all(isinstance(s.get('_timeline'), list) for s in segs):
                # an EDL read back from the timeline carries `_timeline` [start, end] per segment (sequence seconds): those ARE the V1 cuts;
                # the cumulative sum of source durations drifts off the sequence grid on a mixed-rate source (a 30 fps screen recording on 23.976,
                # 2026-09-14: every edge read 0.37 ms 'off the cut' while sitting on the frame Premiere placed)
                cuts = [float(s['_timeline'][1]) - off for s in segs]
            else:
                for s in segs:
                    t += float(s['end']) - float(s['start']); cuts.append(t)
        self.cuts = cuts
        self.fps = fps
        self.text_meta = {}
        self.scaled_noted = set()
        for m in glob.glob(str(self.hf / '*' / 'compositions' / '*.meta.json')):
            self.text_meta[Path(m).name.replace('.meta.json', '')] = json.load(open(m, encoding="utf-8"))

    def note(self, gid, check, level, msg, tag=None):
        # `check:tag` waives ONE assertion of a many-assertion check (source carries a dozen);
        # the bare `check` key still waives all of them, as the older waiver files do.
        gw = self.waivers.get(gid) or {}
        w = (gw.get(f'{check}:{tag}') if tag else None) or gw.get(check)
        if w and level in ('FAIL', 'warn'):
            level, msg = 'waived', f'{msg}  [waived: {w}]'
        self.findings.append((gid, check, level, msg))

    def comp(self, gid):
        # `<id>.html` or `<id>-<slug>.html` (g6-wall.html); never a bare `<id>*` prefix, g1 would swallow g11.
        # 2026-09-03: the slug form matched nothing, so the whole source lint silently never ran on a job.
        for pat in (f'{gid}.html', f'{gid}-[a-z]*.html'):
            for p in sorted(glob.glob(str(self.hf / '*' / 'compositions' / pat))):
                return Path(p)
        return None

    def cut_miss(self, t, window=8):
        """The V1 cut this time nearly lands on but misses, or None. A boundary within `window`
        frames of a cut is meant to sit ON it (off by one = a flash of the other shot); a boundary
        far from every cut is a cut back mid-take, which is a choice, not a miss. ANY miss counts:
        a row a hair BELOW the tick floors to the previous frame on placement and lands short, so
        only float noise on a snapped row (3e-06 s) is clean, never half a frame."""
        if not self.cuts: return None
        f = 1.0 / self.fps
        c = min(self.cuts, key=lambda x: abs(x - t))
        return c if 1e-4 < abs(t - c) <= window * f else None

    def other_resolution_sibling(self, f, pr):
        """The newest sibling VERSION of this render at a different resolution, or None. Siblings share the
        stem (g6, g16-alpha, g17-rules-alpha) and extension and differ only in the -<letter> version;
        the newest is the highest letter (an unversioned file is the oldest)."""
        p = Path(f)
        stem = re.sub(r'-[a-z]$', '', p.stem)
        best = None
        for q in p.parent.glob(f'{stem}*{p.suffix}'):
            if q == p or re.sub(r'-[a-z]$', '', q.stem) != stem: continue
            pq = probe(str(q))
            if not pq or (pq['w'], pq['h']) == (pr['w'], pr['h']): continue
            key = (re.search(r'-([a-z])$', q.stem) or [None, ''])[1]
            if best is None or key > best[0]: best = (key, str(q))
        return best[1] if best else None

    # ── per graphic ──────────────────────────────────────────────────────────
    def check_row(self, r):
        gid, f = r['id'], r['file']
        if not os.path.exists(f):
            self.note(gid, 'render', 'FAIL', f'render missing: {f}'); return
        pr = probe(f)
        if not pr: self.note(gid, 'render', 'FAIL', f'ffprobe cannot read {f}'); return
        if pr['w'] * FRAME_H != pr['h'] * FRAME_W or pr['w'] < FRAME_W or pr['w'] % FRAME_W:
            sys.exit(f"{f} is {pr['w']}x{pr['h']}: this gate covers long-form 16:9 renders at {FRAME_W}x{FRAME_H} or an "
                     'integer multiple of it (3840x2160). Its band floor, edge margins and alpha-sweep geometry are all '
                     '16:9 authoring-frame numbers, so a short-form job would get a meaningless green — a 9:16 job gates on '
                     'workflows/graphics-qa-short.py instead.')
        scale = pr['w'] // FRAME_W
        if scale != 1 and gid not in self.scaled_noted:
            self.scaled_noted.add(gid); print(f"  {gid}: {pr['w']}x{pr['h']} render, measured in the {FRAME_W}x{FRAME_H} authoring frame (scale {scale}x)")
        if self.fps is None: self.fps = pr['fps']
        if abs(pr['fps'] - self.fps) > 0.01:
            self.note(gid, 'render', 'FAIL', f"render fps {pr['fps']:.3f} != timeline {self.fps:.3f}")
        F = 1.0 / self.fps
        full = r.get('kind') == 'full'
        if full and pr['pix'] and pr['pix'].startswith('yuva'):
            self.note(gid, 'render', 'FAIL', 'a full-screen graphic must be an OPAQUE mp4 (this has alpha)')
        if not full and pr['pix'] != 'yuva444p12le':
            self.note(gid, 'render', 'FAIL', f"overlay must be ProRes 4444 straight alpha (yuva444p12le), got {pr['pix']}")
        cell = self.cells.get(gid)
        placed = r['end'] - r['start']
        # a STEPPED render (bg-dark = STEP_FPS=12) comes out of render.sh's `fps=` expansion up to one 12 fps
        # step (2 timeline frames) longer than its authored span, and the placer trims that pad back by design.
        # `drift` is POSITIVE when the render is longer than the placed span — the trim direction — so that is
        # the one the pad relaxes to 2 frames; the other direction (placed longer than the render, a frozen
        # last frame) has no pad to explain it and stays at 1.5. A full-screen cell that names no `bg` takes
        # the pad too: dark IS the field's default (creative-moves.md § THE DENSITY NUMBERS, the field), so an
        # unwritten `bg` is a stepped render until the plan says otherwise — validate-plan.py is where a
        # long-form plan is made to write it down.
        over = 2.0 if (full and (cell or {}).get('bg', 'dark') == 'dark') else 1.5
        drift = (pr['dur'] - placed) / F
        if drift > over + 0.01 or drift < -1.5:
            self.note(gid, 'duration', 'warn', f"placed {placed:.3f}s vs render {pr['dur']:.3f}s "
                      f"({drift:+.1f} frames): a trimmed tail cuts the exit off; extended = a frozen last frame")
        # parity: a version of this render at ANOTHER resolution must be the same picture (see the docstring)
        sib = self.other_resolution_sibling(f, pr)
        if sib:
            d = sh(sys.executable, str(RENDER_DIFF), f, sib, '--frames', '5', '--quiet')
            tail = (d.stdout.strip().splitlines() or [''])[-1]
            if d.returncode == 0:
                self.note(gid, 'parity', 'info', f'{tail} vs {os.path.basename(sib)}')
            else:
                self.note(gid, 'parity', 'FAIL', f'{tail} vs {os.path.basename(sib)}: a resolution change must not change the picture '
                          '(a comp renders at a multiple of 1080 on a scale(N) stage, never #root{zoom}); a deliberate redesign waives this')
        meta = self.text_meta.get(gid, {})
        # band / edge / exit sweep on the alpha plane (overlays only)
        if not full:
            self.sweep_alpha(gid, f, r, cell, meta, F)
        else:
            self.sweep_full(gid, f, r, cell, F, pr)
        self.check_stray(gid, f, r, F)
        # cut alignment
        if full or meta.get('exit') == 'cut':
            for edge in (('end', r['end']),) + ((('start', r['start']),) if full else ()):
                if (gid, edge[0]) in self.inner: continue   # an internal seam of a split graphic, not an outer boundary
                miss = self.cut_miss(edge[1])
                if miss is not None:
                    self.note(gid, 'cut', 'FAIL', f"{edge[0]} {edge[1]:.4f} is {(edge[1] - miss) / F:+.2f} frames off the V1 cut at {miss:.4f}: "
                              f"the other shot flashes for those frames, sit exactly on the cut")
        # plan reconciliation
        if not cell:
            self.note(gid, 'plan', 'FAIL', 'placed but not a graphic:true cell in graphics-plan.json')
        else:
            for k in ('start', 'end'):
                if abs(float(cell[k]) - float(r[k])) > 1.5 * F:
                    self.note(gid, 'plan', 'FAIL', f"plan {k} {float(cell[k]):.3f} vs placed {float(r[k]):.3f} "
                              f"({(float(r[k]) - float(cell[k])) / F:+.1f} frames): reconcile the plan to the placement "
                              f"(workflows/placement.py --write; Premiere: place-graphics.py --plan --write) or fix the placement")
            if '—' in (cell.get('copy') or ''):
                self.note(gid, 'copy', 'FAIL', 'em dash (U+2014) in the plan copy')
            if r.get('kind') == 'text':
                self.check_text_copy(gid, cell)
        # source lints on hand comps
        c = self.comp(gid)
        if c:
            self.check_fonts(gid, c)
        if c and r.get('kind') != 'text':
            self.lint_comp(gid, c, cell, full)
        elif c and r.get('kind') == 'text':
            src = c.read_text(encoding="utf-8")
            if 'data-w="' in src:
                for w in re.findall(r'data-w="([^"]*)"', src):
                    if '*' in w or '~' in w or '—' in w:
                        self.note(gid, 'copy', 'FAIL', f'literal marker/em dash on screen: {w!r}')

    def check_stray(self, gid, f, r, F):
        """`stray`: one-frame flashes on the render itself (see the docstring)."""
        if not hasattr(QA, '_flash_scan'):
            spec = importlib.util.spec_from_file_location('flash_scan', FLASH_SCAN)
            QA._flash_scan = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(QA._flash_scan)
        fs = QA._flash_scan
        try:
            found = fs.render_lines(fs.render_scan(f))
        except fs.InputError as e:
            self.note(gid, 'stray', 'warn', f'not checked ({e}): read the render for one-frame flashes by eye'); return
        if not found:
            return
        c = self.comp(gid)
        js = c.read_text(encoding="utf-8") if c else ''
        strobe = re.search(r'\bflash\s*\(', js) or re.search(r'ENTRANCE\s*=\s*["\']flicker', js)
        i, what = found[0]
        msg = (f'{len(found)} one-frame flash(es) in the render (first: frame {i} = {r["start"] + i * F:.3f}s, {what}; '
               f'render frames {[k for k, _ in found][:6]})')
        if strobe:
            self.note(gid, 'stray', 'warn', msg + ': this graphic strobes (flash/flicker), built of one-frame pulses; '
                      'any of these outside its 7-frame strobe is a real flash')
        else:
            self.note(gid, 'stray', 'FAIL', msg)

    def sweep_alpha(self, gid, f, r, cell, meta, F):
        w, h = 480, 1080
        low_band = (cell or {}).get('region') == 'low-band' or r.get('kind') == 'text'
        # an element that SLIDES in or out crosses the frame edge by definition: the left/right edge
        # rule holds on its hold, not while it is passing through
        c = self.comp(gid)
        js = c.read_text(encoding="utf-8") if c else ''
        slide_in = 0.75 if 'slideIn(' in js else 0.0
        slide_out = 0.38 if 'slideOut(' in js else 0.0
        worst = dict(bottom=(-1, -1), top=(10**6, -1), left=(10**6, -1), right=(-1, -1), topedge=(10**6, -1))
        last = None; n = 0
        total = probe(f)['frames'] or 0
        for i, fr in enumerate(frames(f, f'alphaextract,scale={w}:{h}', w, h)):
            n += 1; last = fr
            ys, xs = np.where(fr > ALPHA_INK)
            if ys.size == 0: continue
            b, t, l, rr = int(ys.max()), int(ys.min()), int(xs.min()) * 4, int(xs.max()) * 4
            if b > worst['bottom'][0]: worst['bottom'] = (b, i)
            if t < worst['top'][0]: worst['top'] = (t, i)
            passing = (i * F < slide_in) or (total and (total - 1 - i) * F < slide_out)
            if not passing:
                if l < worst['left'][0]: worst['left'] = (l, i)
                if rr > worst['right'][0]: worst['right'] = (rr, i)
        if n == 0:
            self.note(gid, 'render', 'FAIL', 'no frames decoded'); return
        b, bi = worst['bottom']
        if b > self.band_floor:
            self.note(gid, 'band', 'FAIL', f'ink reaches y{b} (floor {self.band_floor}) at frame {bi} ({bi * F + r["start"]:.3f}s)')
        t, ti = worst['top']
        if low_band and t < self.band_top:
            self.note(gid, 'band', 'FAIL', f'low-band graphic has ink at y{t} (band top {self.band_top}, chin clearance) at frame {ti}')
        if not low_band and t < TOP_EDGE:
            self.note(gid, 'band', 'FAIL', f'ink within {TOP_EDGE}px of the top edge (y{t}) at frame {ti}')
        l, li = worst['left']
        if l < EDGE: self.note(gid, 'band', 'FAIL', f'ink within {EDGE}px of the left edge (x{l}) at frame {li}')
        rr, ri = worst['right']
        if rr > FRAME_W - EDGE: self.note(gid, 'band', 'FAIL', f'ink within {EDGE}px of the right edge (x{rr}) at frame {ri}')
        # face: a side callout keeps SUBJECT px off the head (ears included) on every hold frame. The head is measured
        # over the graphic's own window (chin-line.py --edl, worst frame) and carried in the plan cell as
        # `head {left, right, frame}` — chin-line's own `frame` normalises a measurement taken on a 4K raw back
        # into the 1920x1080 authoring frame every number here lives in.
        region = (cell or {}).get('region') or ''
        if region in ('callout-L', 'callout-R'):
            head = (cell or {}).get('head') or {}
            fw = (head.get('frame') or [0])[0]
            # any positive width scales: a raw is not always an integer multiple of the authoring frame
            # (this repo's own long-form raws probe 3836x2160, not 3840)
            k = FRAME_W / fw if isinstance(fw, (int, float)) and fw > 0 else None
            if 'left' not in head or 'right' not in head:
                self.note(gid, 'face', 'warn', 'side callout with no measured head in its plan cell: run chin-line.py --edl over its window and record head {left,right,frame} (default-overlay-style.md § SIDE CALLOUTS)')
            elif k is None:
                self.note(gid, 'face', 'warn', f"head measured in an unknown frame (head.frame {head.get('frame')!r}): re-run chin-line.py --edl and record its `frame`, "
                          "or the margin cannot be checked (default-overlay-style.md § SIDE CALLOUTS)")
            elif region == 'callout-L' and rr > head['left'] * k - SUBJECT:
                self.note(gid, 'face', 'FAIL', f"ink reaches x{rr} at frame {ri}, inside {SUBJECT}px of the head (head left x{head['left'] * k:.0f}, ears included): "
                          "it covers his ear (default-overlay-style.md § SIDE CALLOUTS)")
            elif region == 'callout-R' and l < head['right'] * k + SUBJECT:
                self.note(gid, 'face', 'FAIL', f"ink reaches x{l} at frame {li}, inside {SUBJECT}px of the head (head right x{head['right'] * k:.0f}, ears included): "
                          "it covers his ear (default-overlay-style.md § SIDE CALLOUTS)")
            elif region == 'callout-L':
                self.note(gid, 'face', 'info', f"clear of the head: ink reaches x{rr}, head left x{head['left'] * k:.0f} ({head['left'] * k - rr:.0f}px clearance, floor {SUBJECT})")
            elif region == 'callout-R':
                self.note(gid, 'face', 'info', f"clear of the head: ink reaches x{l}, head right x{head['right'] * k:.0f} ({l - head['right'] * k:.0f}px clearance, floor {SUBJECT})")
        # an overlay that ends ON a V1 cut may use the cut as its exit (a text animation says so in
        # its meta; a hand comp says so by ending there, g4's FREE chip holds to the cut by design)
        on_cut = bool(self.cuts) and min(abs(r['end'] - c) for c in self.cuts) <= 0.6 * F
        if meta.get('exit') == 'cut' and not on_cut and last is not None and int(last.max()) > ALPHA_ANY:
            # the builder's word is not enough: a text animation built to exit ON a cut but placed to end away from any
            # (an `until` that is not a V1 cut) switches off mid-shot with no exit (t11, 2026-09-27, edit-review r2)
            near = min((abs(r['end'] - c) for c in self.cuts), default=float('inf')) / F
            self.note(gid, 'exit', 'FAIL', f'built to exit ON a V1 cut, but its placed end {r["end"]:.3f} is {near:.0f} frames from '
                      'the nearest cut and the last frame still carries ink: it switches off mid-shot (rebuild with the exit as a riseOut)')
        elif not on_cut and last is not None and int(last.max()) > ALPHA_ANY:
            self.note(gid, 'exit', 'FAIL', f'last rendered frame still carries ink (alpha max {int(last.max())}): '
                      'the exit did not complete (fade ending AT DUR instead of 2 frames before) or the hard-kill is missing')

    def sweep_full(self, gid, f, r, cell, F, pr):
        # FOOTAGE — a capture or a generated b-roll clip — is not an authored scene: it has no entrance to
        # start on frame 0 and no centred type, so `lead` and the centre ROWS read it as a defect by
        # construction (a full-screen b-roll took lead + centre warns on a clean take).
        # `dynamics` is narrower, and only a REAL CAPTURE is exempt from it: a screen recording's motion is
        # the app's, while a generated clip is chosen for its motion and a static one is a real finding.
        # A capture is a recorded FILE — the cell's kind says so, or it names what the build recorded — never
        # a `b-roll` template on a hand-authored comp, which has an authored entrance like any other scene.
        kind_ = (cell or {}).get('kind')
        capture = kind_ in ('screen-rec', 'screenshot') or bool((cell or {}).get('capture')) \
            or 'captures/' in str((cell or {}).get('asset') or '').replace('\\', '/') \
            or bool((cell or {}).get('broll_source'))   # the creator's own B-roll (broll-own): real footage, its motion is the camera's
        footage = capture or kind_ == 'b-roll' or 'b-roll' in ((cell or {}).get('template') or '').lower()
        w, h = 64, 36
        seq = list(frames(f, f'scale={w}:{h}', w, h))
        if not seq: self.note(gid, 'render', 'FAIL', 'no frames decoded'); return
        diffs = [float(np.abs(seq[i].astype(int) - seq[i - 1].astype(int)).mean()) for i in range(1, min(16, len(seq)))]
        lead = 0
        for d in diffs:
            if d < 1.0: lead += 1
            else: break
        if lead >= 2 and any(d > 2.5 for d in diffs) and not footage:
            self.note(gid, 'lead', 'warn', f'{lead} static lead frames before the first element arrives, a defect if that '
                      "element is near-full-frame (animations.md § A full-screen graphic's entrance starts on FRAME 0), "
                      'fine for a small first element')
        # dynamics: how much of its life does the full-screen sit still? Measured on the 12 fps grid (every 3rd frame,
        # so a stepped render's duplicate frames do not count as stillness): a triplet is static when no 12x12 block moved. A scene has phases, props and a camera (creative-moves
        # move 2 § A FULL-SCREEN IS A SCENE): over 60 % static is the plain-Jane number (g16 as first built: three nodes
        # arriving over 10 s read 71 % static).
        # measured at 192x108 on 12x12 blocks: a clock hand, a scrolling strip or a pulsing icon moves a few blocks a lot
        # (the frame MEAN would miss them on a dark field), while grain, THE FLOAT and a slow camera push stay under the bar
        step = 3
        fine = list(frames(f, 'scale=192:108', 192, 108))
        def blockmax(a, b):
            d = np.abs(a.astype(int) - b.astype(int)).reshape(9, 12, 16, 12).mean(axis=(1, 3))
            return float(d.max())
        d3 = [blockmax(fine[i], fine[i - step]) for i in range(step, len(fine), step)]
        # rack: a comp that declares a rack layer (#racked) must darken the FRAME EDGES when it racks, not just the centre —
        # a racked layer inside the 0.92 content box leaves a bright border 4 % of the frame wide (g10/g22, 2026-09-10).
        # Keyed on the source, never on luminance alone: a dark window arriving in the centre is not a rack.
        cp_ = self.comp(gid)
        if cp_ and '#racked' in cp_.read_text(encoding="utf-8"):
            lum = [fr.astype(float) for fr in fine[::step]]
            cen = [float(a[22:86, 38:154].mean()) for a in lum]
            # the racked state is the dim layer's own SETTLED state, read off the EDGES, never off the centre:
            # the recipe lands bright type dead centre over the racked scene and ramps the dim over 20 frames,
            # so the centre's argmin is a frame into the ramp, before the edges catch up (g5 waived exactly that,
            # 2026-09-19: settled the same render reads centre −83% / edges −69%, a pass)
            edg = [float(np.concatenate([a[:2].ravel(), a[-2:].ravel(), a[:, :2].ravel(), a[:, -2:].ravel()]).mean()) for a in lum]
            j = min(range(len(edg)), key=lambda k: edg[k])
            # IS there a rack at all is asked of the centre at ITS OWN darkest (jc): reading that question off
            # the edges' frame would answer "the centre never darkens" for a real rack whose centre bottoms out
            # earlier than the edges — the exact asymmetry this block exists to handle. The MEASUREMENT stays on
            # the settled frame j; only the entry test and the "never darkens" report use jc.
            jc = min(range(len(cen)), key=lambda k: cen[k])
            if cen[0] > 30 and cen[jc] / cen[0] < 0.65:
                # the edges, measured at 960x540 in the outer 8 px (16 px at 1080): a 22 px bright rim vanishes in a coarser band
                big = list(frames(f, 'scale=960:540', 960, 540, n_frames=j * step + 1))
                bd = lambda a: float(np.concatenate([a[:8].ravel(), a[-8:].ravel(), a[:, :8].ravel(), a[:, -8:].ravel()]).mean())
                b0, bj = bd(big[0].astype(float)), bd(big[j * step].astype(float))
                cr = cen[j] / cen[0]
                br = bj / b0 if b0 > 30 else cr
                if br > cr + 0.15:                                             # the edges darken at least as much as the centre, within 15 points
                    self.note(gid, 'rack', 'FAIL', f'racked at {j * step * F:.2f}s the centre is {100 * (1 - cr):.0f}% darker than on frame 0 but the '
                              f'frame edges only {100 * (1 - br):.0f}%: the rack focus does not reach the edges (the racked layer belongs at '
                              'frame level, creative-moves move 2 § THE RACK FOCUS; the bad build read edges −40% against centre −66%)')
                else:
                    self.note(gid, 'rack', 'info', f'racked at {j * step * F:.2f}s: centre {100 * (1 - cr):.0f}% darker, edges {100 * (1 - br):.0f}% darker')
            else:
                # no measurable dim. A comp that DECLARES #racked and never wires it looks exactly like this, and
                # so does a correct rack on an already-dark field (a dark scene racking behind type: no light left
                # to take, the rack carried by the blur ladder alone). The gate cannot separate them — which is a
                # reason to ask, not a reason to go quiet: downgrading the dark-field case to info (2026-09-19)
                # took the only "is the rack wired?" signal there was and put nothing in its place. It warns on
                # both fields and says which one it is measuring; a wired rack on a dark field is a `rack` waiver.
                dark = cen[0] <= 30
                self.note(gid, 'rack', 'warn', f'#racked is declared but the centre never darkens past 35% (darkest {100 * (1 - cen[jc] / max(cen[0], 1)):.0f}% at {jc * step * F:.2f}s)'
                          + (f': frame-0 centre luma {cen[0]:.0f}, an already-dark field — if the rack is its blur ladder this is the expected reading, waive `rack`; otherwise it is not wired'
                             if dark else ': is the rack wired?'))
        if d3:
            static = sum(1 for d in d3 if d < 4.0) / len(d3)
            beats = sum(1 for d in d3 if d > 40.0)
            lvl = 'warn' if static > 0.60 and not capture else 'info'   # a real capture only: a static generated clip is a finding
            self.note(gid, 'dynamics', lvl, f'{100 * static:.0f}% of its life is static on the 12 fps grid, {beats} big visual beat(s)'
                      + (' — a full-screen is a SCENE: phases, visuals, a camera move (creative-moves move 2)' if lvl == 'warn' else ''))
        # grain: residual against a 3x3 median at half the RENDER's res (the grain pass runs at render
        # resolution, so a 4K render measured at 960x540 would average 4x more grain away than a 1080 one),
        # read on a LIT frame and never on frame 0 alone: a full-screen that opens on black (a fade-in, a
        # dark scene's first beat) carries nothing above the floor there, so frame 0 either abstained or
        # read the fade as a missing pass. The coarse grid decoded above already says which frame has
        # picture; the first one over the floor inside the first 3 s is the one decoded at grain resolution.
        cap_n = min(len(fine), int(3.0 / F) + 1)
        lit_at = [(k, float((fine[k] > GRAIN_FLOOR).mean())) for k in range(0, cap_n, step)] or [(0, 0.0)]
        gi = next((k for k, v in lit_at if v >= 0.05), max(lit_at, key=lambda kv: kv[1])[0])
        gw, gh = pr['w'] // 2, pr['h'] // 2
        g0 = None
        for g0 in frames(f, f'scale={gw}:{gh}', gw, gh, n_frames=gi + 1): pass
        if g0 is None:
            self.note(gid, 'grain', 'info', 'grain unmeasured: no frame decoded')
            self.check_centre(gid, f, fine, step, F, cell, footage); return self.check_settled(gid, f, F, footage)
        med = np.median(np.stack([np.roll(np.roll(g0, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]), axis=0)
        # measured only where the picture is NOT clipped at black: below the floor the codec has nothing left to
        # carry the noise, so a #030303 window halves the residual with the pass fully applied (g28 read 0.82/0.87
        # against 0.9 and was waived twice). Too little unclipped picture to judge = no assertion at all.
        lit = med > GRAIN_FLOOR
        resid = float(np.abs(g0.astype(float) - med)[lit].mean()) if lit.mean() >= 0.05 else None
        is_title = (cell or {}).get('template', '').startswith('section') or (cell or {}).get('kind') == 'section-title'
        if resid is None:
            self.note(gid, 'grain', 'info', f'grain unmeasured: the lightest frame of its first {cap_n * F:.1f}s (at {gi * F:.2f}s) has only '
                      f'{100 * lit.mean():.0f}% above the black floor ({GRAIN_FLOOR})')
        elif resid < GRAIN_MIN and not is_title and not (cell or {}).get('broll_source'):  # own camera B-roll carries its own noise: the grain pass is a graphics rule
            self.note(gid, 'grain', 'FAIL', f'no film-grain pass on this full-screen (residual {resid:.2f} < {GRAIN_MIN} at {gi * F:.2f}s, '
                      f'over the {100 * lit.mean():.0f}% of that frame above the black floor)')
        self.check_centre(gid, f, fine, step, F, cell, footage)
        self.check_settled(gid, f, F, footage)

    def check_centre(self, gid, f, fine, step, F, cell, footage=False):
        """A full-screen sits DEAD CENTRE, and centred means the COMPOSED row and group, never the type alone (creative-moves
        move 2, the user 2026-09-13: g5's words were centred while the clapperboard and chip beside them hung off the right end,
        so two rows sat 100/116 px right of centre and the graphic read off-centre through three review rounds).
        Measured on the render's FULLEST frame (the most edge pixels on the 12 fps grid, so a comp with an exit is read before
        it): ink = sharp pixel-to-pixel contrast, so the field gradient, the vignette, a glow bloom and the grain never count;
        the ink rows (split at 24 px gaps) and the whole box must each centre within CENTRE_MAX px of the frame centre."""
        if (cell or {}).get('broll_source'): return                       # the creator's own camera footage: nothing composed to centre
        edges = ink
        counts = [int(edges(fr).sum()) for fr in fine[::step]]
        if not counts or max(counts) < 20: return                          # nothing composed on screen: nothing to centre
        j = max(range(len(counts)), key=lambda k: counts[k]) * step
        big = list(frames(f, 'scale=960:540', 960, 540, n_frames=j + 1))
        if not big: return
        m = edges(big[-1]); S = FRAME_W / 960                              # authoring px per measured px
        ys = np.where(m.any(axis=1))[0]
        if not len(ys): return
        xs = np.where(m.any(axis=0))[0]
        dx = ((xs.min() + xs.max()) / 2 - 480) * S; dy = ((ys.min() + ys.max()) / 2 - 270) * S
        bands, a, p = [], ys[0], ys[0]
        for y in ys[1:]:
            if y - p > 12: bands.append((a, p)); a = y
            p = y
        bands.append((a, p))
        rows = []
        for a, b in bands:
            sub = m[a:b + 1]
            if sub.sum() < 40 or b - a < 5: continue                       # a speck, not a row
            xx = np.where(sub.any(axis=0))[0]
            rows.append((a * S, b * S, ((xx.min() + xx.max()) / 2 - 480) * S))
        t = j * F
        # Rows are the law on a TEXT punch-cut (stacked centred lines: g5). On a scene they only warn: a terminal window's
        # title bar and left-aligned prompt lines (g10) and the chip row under one side of a two-column diagram (g27) are
        # rows off centre by design, and a waiver or the reviewer settles them. The box's VERTICAL centre warns too: a
        # dark window on the dark field has no readable bottom edge, so its empty lower half drops out of the ink box.
        # FOOTAGE rows are the captured page's or the generated clip's own layout, not authored type: they are reported, never warned about.
        text_cut = 'text' in ((cell or {}).get('template') or '').lower()
        off = [r for r in rows if abs(r[2]) > CENTRE_MAX]
        if off:
            self.note(gid, 'centre', 'FAIL' if text_cut else ('info' if footage else 'warn'), f'at {t:.2f}s ' + ', '.join(f'the row y{r[0]:.0f}-{r[1]:.0f} centres {r[2]:+.0f} px' for r in off)
                      + f' off the frame centre (limit {CENTRE_MAX}): centred means the COMPOSED row, words + the prop beside them as ONE '
                      'inline box, never the type alone (creative-moves move 2 § CENTRED MEANS THE COMPOSED ROW)'
                      + ('' if text_cut else (' — the footage\'s own rows, not authored type' if footage else ' — a scene row, fine when it belongs to one side of the scene, a defect when it is a centred line')), tag='row')
        if abs(dx) > CENTRE_MAX:
            self.note(gid, 'centre', 'FAIL', f'at {t:.2f}s the whole composed box centres {dx:+.0f} px off the frame centre horizontally '
                      f'(limit {CENTRE_MAX}): a full-screen sits DEAD CENTRE (creative-moves move 2); a specific reason is a waiver', tag='box')
        elif abs(dy) > CENTRE_MAX:
            self.note(gid, 'centre', 'warn', f'at {t:.2f}s the ink box centres {dy:+.0f} px off the frame centre vertically (limit {CENTRE_MAX}): '
                      'a defect on stacked lines, a hollow dark window losing its bottom edge otherwise — read the frame', tag='box')
        elif not off:
            worst = max((abs(r[2]) for r in rows), default=0)
            self.note(gid, 'centre', 'info', f'at {t:.2f}s the composed box sits {dx:+.0f} x {dy:+.0f} px off centre, worst row {worst:.0f} px')

    def check_settled(self, gid, f, F, footage=False):
        """The two assertions the fullest frame cannot make, in one 960x540 pass over every frame, on the same ink as `centre`
        (2026-10-06, f02-b: a late push, scale 1.12 about 50% 72% plus y −110, parked the comment panel off the top edge
        for the last 34 frames, its box ~120 px above centre, the 'Comments' header at y~70; `centre` read a pre-push
        frame and passed it, and the edit-review reviewer reported the missing assertion).
          settled: on the 12 fps grid, a sample that keeps under MOVE_KEEP of the previous one's ink in place (within 6 px)
            starts a new PHASE (a camera or scale move, a reflow, a scene change). A SETTLED state is a box that holds
            SETTLE_S with every edge within SETTLE_TOL px; a phase's composed box is the UNION of its settled states, so a
            slot reserved early and filled later in the same phase is part of it (a build-up is never measured alone:
            g15's empty '335' slot and f04's empty '$5' slot read 117 and 191 px off on their own). Every phase a move led
            into is held to CENTRE_MAX on BOTH axes and to the frame, FAIL, tag `settled`. The phase no move led into is the
            fullest frame's, whose vertical only warns: a hollow dark window's bottom edge is invisible to this ink.
          margin: ink within TOP_EDGE px of the top or bottom edge or EDGE px of a side that HOLDS STILL there (each frame's
            margin ink in place within 2 px of the frame before) for MARGIN_HOLD_S. A scene sliding in from off-screen
            crosses the margin in 1-5 frames and is exempt, the way a slide is on an overlay's band.
        FOOTAGE is exempt from both: a capture fills the frame and its zooms are the app's."""
        if footage: return
        W, H = 960, 540; S = FRAME_W / W                                   # authoring px per measured px
        k = max(1, round(1.0 / (12 * F)))                                  # the 12 fps grid
        need = max(1, math.ceil(SETTLE_S / (k * F) - 1e-6))                # samples a settled state holds
        hold = max(1, round(MARGIN_HOLD_S / F))
        my, mx = round(TOP_EDGE / S), round(EDGE / S)
        band = np.ones((H, W), bool); band[my:H - my, mx:W - mx] = False
        samples, prev, prev_b, held = [], None, None, []
        for i, fr in enumerate(frames(f, f'scale={W}:{H}', W, H)):
            m = ink(fr)
            b = m & band; n = int(b.sum())
            still = n >= 8 and prev_b is not None and int((b & grow(prev_b, 1)).sum()) >= 0.8 * n
            held.append(self._margin_ink(b, my, mx, S) if still else None)
            prev_b = b
            if i % k: continue
            c = int(m.sum())
            if c >= 20:
                ys = np.where(m.any(axis=1))[0]; xs = np.where(m.any(axis=0))[0]
                box = (xs.min() * S, xs.max() * S, ys.min() * S, ys.max() * S)
            else: box = None
            keep = int((prev[0] & grow(m, 3)).sum()) / prev[1] if prev and prev[1] >= 20 and c >= 20 else 1.0
            samples.append((i, c, box, keep)); prev = (m, c)
        # settled states after a move
        phases, cur = [], []
        for s in samples:
            if cur and s[3] < MOVE_KEEP: phases.append(cur); cur = []
            cur.append(s)
        if cur: phases.append(cur)
        measured = []
        for n_, ph in enumerate(phases):
            if not n_: continue                                                 # no move led into it: the fullest frame's
            runs, run = [], []
            for s in ph:
                if s[2] is None or (run and max(abs(a - b) for a, b in zip(s[2], run[0][2])) > SETTLE_TOL):
                    if len(run) >= need: runs.append(run)
                    run = [s] if s[2] is not None else []
                else: run.append(s)
            if len(run) >= need: runs.append(run)
            if not runs: continue
            bx = np.array([np.median([s[2] for s in r], axis=0) for r in runs])
            x0, x1, y0, y1 = bx[:, 0].min(), bx[:, 1].max(), bx[:, 2].min(), bx[:, 3].max()
            dx, dy = (x0 + x1) / 2 - FRAME_W / 2, (y0 + y1) / 2 - FRAME_H / 2
            cross = [e for e, hit in (('left', x0 <= S), ('right', x1 >= FRAME_W - 2 * S), ('top', y0 <= S),
                                      ('bottom', y1 >= FRAME_H - 2 * S)) if hit]
            t0, t1 = runs[0][0][0] * F, runs[-1][-1][0] * F
            measured.append((abs(dx), abs(dy)))
            if abs(dx) > CENTRE_MAX or abs(dy) > CENTRE_MAX or cross:
                self.note(gid, 'centre', 'FAIL', f'settled {t0:.2f}-{t1:.2f}s after a camera/scale move or a scene change, the composed box '
                          f'x{x0:.0f}-{x1:.0f} y{y0:.0f}-{y1:.0f} centres {dx:+.0f} x {dy:+.0f} px off the frame centre (limit {CENTRE_MAX} on both axes)'
                          + (f" and crosses the frame's {'/'.join(cross)} edge" if cross else '')
                          + ': a full-screen sits DEAD CENTRE in every state it settles in, not only on its fullest frame (creative-moves move 2); '
                          'a deliberate off-centre state is a `centre:settled` waiver', tag='settled')
        if measured:
            self.note(gid, 'centre', 'info', f'{len(measured)} settled state(s) after a move, worst {max(m[0] for m in measured):.0f} px '
                      f'horizontally, {max(m[1] for m in measured):.0f} px vertically')
        # margin: the longest run of frames whose margin ink holds still
        spans, a = [], None
        for i, e in enumerate(held + [None]):
            if e is None:
                if a and i - a[0] >= hold: spans.append(a + [i - a[0]])
                a = None
            elif a is None: a = [i, dict(e)]
            else:
                for side, v in e.items():
                    a[1][side] = v if side not in a[1] else (min if side in ('top', 'left') else max)(a[1][side], v)
        if spans:
            s0, ext, n_ = max(spans, key=lambda s: s[2])
            lim = dict(top=TOP_EDGE, bottom=TOP_EDGE, left=EDGE, right=EDGE)
            where = ', '.join(f"{'y' if side in ('top', 'bottom') else 'x'}{v:.0f} (the {side} margin is {lim[side]} px)" for side, v in ext.items())
            self.note(gid, 'margin', 'FAIL', f'ink holds still inside the edge margin for {n_} frames from {s0 * F:.2f}s: {where}. '
                      f'Full-screen copy keeps {TOP_EDGE} px off the top and bottom and {EDGE} px off the sides (creative-moves move 2, '
                      'default-overlay-style.md § Placement); only a pass through the edge (a scene sliding in from off-screen) is exempt'
                      + (f'; {len(spans) - 1} more hold(s)' if len(spans) > 1 else ''))

    @staticmethod
    def _margin_ink(b, my, mx, S):
        """{side: the outermost ink coordinate inside that margin, in authoring px} for one frame's margin ink."""
        H, W = b.shape; out = {}
        for side, sub, axis, pick in (('top', b[:my], 1, 'min'), ('bottom', b[H - my:], 1, 'max'),
                                      ('left', b[:, :mx], 0, 'min'), ('right', b[:, W - mx:], 0, 'max')):
            idx = np.where(sub.any(axis=axis))[0]
            if not len(idx): continue
            off = {'bottom': H - my, 'right': W - mx}.get(side, 0)
            out[side] = ((idx.min() if pick == 'min' else idx.max()) + off) * S
        return out

    def check_text_copy(self, gid, cell):
        tj = self.hf / 'text-animation' / 'text.json'
        if not tj.exists(): return
        spec = json.load(open(tj, encoding="utf-8")).get(gid)
        if not spec: self.note(gid, 'copy', 'FAIL', 'text animation has no entry in text.json'); return
        shown = spec.get('display') or spec['phrase']
        # `copy` is the SPOKEN phrase (validate-plan.py anchors on it); when a cell shows different words
        # (the builder's `display`, e.g. *never* over the spoken 'ever') the plan carries them in `display`
        expect = cell.get('display') or cell.get('copy') or ''
        if norm_words(shown) != norm_words(expect):
            self.note(gid, 'copy', 'FAIL', f"on-screen words {' '.join(norm_words(shown))!r} != plan copy "
                      f"{' '.join(norm_words(expect))!r} (reconcile the plan or the spec)")

    def check_fonts(self, gid, path):
        """Every @font-face url() in the comp is a file under its render root, the folder above compositions/ that
        hyperframes serves `assets/…` from. A missing one still renders, exit 0, in a fallback face: Times wherever the
        family is not installed (a client's Windows, Linux or SF-Pro-less Mac), while the author's machine draws the
        system copy and never sees it (the scaffold's SF Pro files, 2026-10-13)."""
        root = path.parent.parent
        css = ''.join(re.findall(r'<style[^>]*>(.*?)</style>', path.read_text(encoding="utf-8"), re.S))
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        for face in re.findall(r'@font-face\s*\{([^}]*)\}', css):
            for _, u in re.findall(r'url\(\s*([\'"]?)([^\'")]+?)\1\s*\)', face):
                if re.match(r'(?i)(data|https?|file):|//', u):
                    continue
                rel = u.split('?')[0].split('#')[0].lstrip('/')
                if not (root / rel).is_file():
                    self.note(gid, 'font', 'FAIL', f"@font-face src {u!r} is not a file under {root.name}/ (the render's "
                              'root): the render exits 0 in a fallback face, Times where the family is not installed. '
                              'Copy the font in (graphics-build § Stage 2, Fonts) or point the src at the copy')

    def lint_comp(self, gid, path, cell, full):
        src = path.read_text(encoding="utf-8")
        js = ''.join(re.findall(r'<script>(.*?)</script>', src, re.S))
        js = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
        js = re.sub(r'(^|[^:\\])//[^\n]*', r'\1', js)          # comments are not code ("never onUpdate" matched once)
        css = ''.join(re.findall(r'<style>(.*?)</style>', src, re.S))
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)        # a comment before a rule became part of its selector (g15's .num)
        # the static geometry, parsed ONCE for every check below that needs a box or a cascade
        rules = re.findall(r'([^{}]+)\{([^{}]*)\}', css)          # (selector, raw block), in source order
        cascade = [(s, dict((k.strip().lower(), v.strip()) for k, _, v in
                            (x.partition(':') for x in b.split(';')) if k.strip())) for s, b in rules]
        dom = _Dom(src)
        dec = {id(e): _decls(e, cascade) for e in dom.els}
        body = re.search(r'<body[^>]*>(.*)</body>', src, re.S)
        body = body.group(1) if body else src
        body = re.sub(r'<(script|style)>.*?</\1>', '', body, flags=re.S)
        body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
        visible = re.sub(r'<[^>]+>', ' ', body)
        if '—' in visible: self.note(gid, 'copy', 'FAIL', 'em dash (U+2014) in on-screen text')
        # hand-comp copy vs the plan cell (2026-09-13 round 1: two comps shipped words their cell never
        # said): every ' · '-separated fragment of the cell's copy must appear in the comp's text nodes. A readable cell
        # whose copy IS a written artifact (source_artifact) is the validator's, and its text rides in a JSON script tag.
        if cell and cell.get('copy') and not cell.get('source_artifact') and (cell.get('kind') or '') != 'text-animation':
            norm = lambda s: re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()
            # the words may be INJECTED, never typed into the markup (reveal('.txt', 0.28, 'Hook my agent up to
            # my calendar')), so the script's own string literals count as on-screen copy: without them the check
            # warned on two comps whose lines were plainly on screen (g28, g38, 2026-09-19)
            shown = norm(visible + ' ' + ' '.join(re.findall(r"""['"`]([^'"`]{4,})['"`]""", js)))
            for frag in re.split(r'\s*[·|]\s*', cell['copy']):
                f = norm(frag)
                if f and f not in shown:
                    self.note(gid, 'copy', 'warn', f"plan copy fragment {frag.strip()!r} is not in the comp's text nodes: match the cell or note the deviation in the report")
        # a captured VIDEO inside a comp steps its frames (a page-record scroll holds each position for a frame), and the
        # MBLUR supersample averages two of those steps into one output frame: the text doubles (a scroll capture,
        # 2026-09-13 round 3). The render flags are not visible here, so this is a reminder on every comp that embeds one.
        if re.search(r'<video\b', body):
            self.note(gid, 'source', 'warn', 'embeds a <video> capture: render this comp WITHOUT the MBLUR supersample (a stepping capture doubles under tmix); the registry smear still rides its slides')
        # a still of the creator inside a comp is the plan's CAST frame (hero_frame, written by workflows/hero-frame.py --pick),
        # never a hand grab (2026-09-13: a hook shipped the beat's plan-frame, mid-word, eyes half shut, past three rounds).
        if cell and cell.get('hero_frame'):
            want = Path(str((cell['hero_frame'] or {}).get('file', '') if isinstance(cell['hero_frame'], dict) else '')).name
            imgs = [Path(m).name for m in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', body)]
            if want and want not in imgs:
                self.note(gid, 'hero', 'FAIL', f"the plan casts hero_frame {want!r} but the comp's <img> sources are {imgs}: use the cast file, never a hand grab")
        uses_hf = 'hf-anim.js' in src
        used = {h for h in HELPERS if re.search(r'\b%s\s*\(' % h, js)}
        if not uses_hf:
            for h in used:
                if not re.search(r'\b(const|let|var|function)\s+%s\b' % h, js):
                    self.note(gid, 'source', 'FAIL', f'calls {h}() but never defines it and does not load hf-anim.js (renders blank)')
            for name, needles in REGISTRY.items():
                defined = re.search(r'\b(const|let|var|function)\s+%s\b' % name, js)
                if not defined: continue
                if name in ('pop', 'slam') and (full and (cell or {}).get('bg') == 'dark'): continue   # the 12 fps form is checked below
                missing = [n for n in needles if n.replace(' ', '') not in js.replace(' ', '')]
                if missing:
                    self.note(gid, 'source', 'FAIL', f'inline {name} drifts from the registry: {", ".join(missing)} not found (animations.md): load hf-anim.js instead of retyping')
            m = re.search(r'riseOut\s*=\s*\([^)]*\)\s*=>\s*\{.*?\n|riseOut\s*=\s*\([^)]*\)\s*=>\s*\{[^\n]*', js)
            if m and "'-='" not in m.group(0) and '"-="' not in m.group(0):
                self.note(gid, 'source', 'FAIL', 'riseOut writes an ABSOLUTE y: an element resting off 0 exits the wrong way; use y: "-=" + dist')
        if 'float' not in used:
            self.note(gid, 'source', 'FAIL', 'no float() call: every hand graphic carries THE FLOAT for its whole life (creative-moves.md move 2)')
        else:
            for sel, t0, t1, preset in re.findall(r"float\(\s*'([^']+)'\s*,\s*([^,]+),\s*([^,]+),\s*'(\w+)'\s*\)", js):
                if t0.strip() != '0' or t1.strip() != 'DUR':
                    self.note(gid, 'source', 'warn', f'float({sel}) spans {t0.strip()} → {t1.strip()}, not 0 → DUR')
                if preset not in ('subtle', 'medium'):
                    self.note(gid, 'source', 'FAIL', f'float preset {preset!r} is not subtle|medium')
                sid = sel.lstrip('#.')
                blk = re.search(r'[#.]%s\b[^{]*\{([^}]*)\}' % re.escape(sid), css)
                if blk and 'inset:0' not in blk.group(1).replace(' ', '') and 'position:absolute' not in blk.group(1).replace(' ', ''):
                    self.note(gid, 'source', 'warn', f'float wrapper {sel} is not a position:absolute;inset:0 wrapper')
        dark = full and (cell or {}).get('bg', 'dark') == 'dark'
        if dark:
            if 'flash(' in js or 'flicker' in js:
                self.note(gid, 'source', 'FAIL', 'flash on a 12 fps graphic (its single-frame gaps vanish), pop or slam')
            if uses_hf and not re.search(r'stepFps\s*:\s*12', js):
                self.note(gid, 'source', 'FAIL', 'bg-dark full-screen loads hf-anim.js without stepFps: 12 (pop/slam will be authored in timeline frames)')
            if not uses_hf and ('pop(' in js or 'slam(' in js) and not re.search(r'S12|SF\b|/\s*12\b|\* 12\)', js):
                self.note(gid, 'source', 'FAIL', 'pop/slam authored in timeline frames on a 12 fps comp, re-express in 83 ms states (or load hf-anim.js with stepFps: 12)')
        # same-slot swap overlap (2026-09-04, g19): an in that starts before a riseOut has finished puts two
        # elements on screen at once for the 0.35s of the out. Literal times only; a swap on the same time
        # is the defect that shipped, anything inside the out's window is suspect. Different slots are
        # legitimate, so this is a warn the reviewer confirms against the layout, never a FAIL.
        outs = [(m.group(1), float(m.group(2))) for m in re.finditer(r"riseOut\(\s*'([^']+)'\s*,\s*([\d.]+)", js)]
        ins = [(m.group(2), float(m.group(3))) for m in re.finditer(r"\b(riseIn|pop|slam|slideIn)\(\s*'([^']+)'\s*,\s*([\d.]+)", js)]
        for osel, ot in outs:
            for isel, it in ins:
                if isel != osel and -0.001 <= it - ot < 0.35 - 0.001:
                    self.note(gid, 'source', 'warn', f"riseOut({osel}) at {ot} and an entrance on {isel} at {it}: if they share a slot the in starts before the out finishes (animations.md: sequence the swap, in at out + 0.35)")
        if 'Math.random' in js: self.note(gid, 'source', 'FAIL', 'Math.random in a comp: the headless render seeks, so every pass differs')
        if 'onUpdate' in js: self.note(gid, 'source', 'FAIL', 'onUpdate-driven content renders FROZEN headless (never fires on seek)')
        if 'innerText' in js and not re.search(r'innerText[^}]*\}\s*,\s*0\s*\)', js) and 'countUp(' not in js and 'reveal(' not in js:
            self.note(gid, 'source', 'FAIL', 'content reveal (innerText) has no zero-frame pin: tl.set(el, {innerText: ...}, 0)')
        if re.search(r'<polygon[^>]*class="[^"]*\bhead\b[^"]*"[^>]*points=', src):
            self.note(gid, 'source', 'FAIL', 'hand-typed arrowhead points: heads ship empty and arrow() computes them from the end tangent')
        if re.search(r'<polygon[^>]*class="[^"]*\bhead\b', src) and 'arrow(' not in js:
            self.note(gid, 'source', 'FAIL', 'arrow head present but arrow() never called (head never gets points)')
        OFFSETS = {'left', 'right', 'top', 'bottom', 'inset'}
        for sel, blk in rules:
            b = blk.replace(' ', '')
            if 'position:absolute' not in b or re.search(r'\b(left|right|top|bottom|inset)\s*:', blk) or 'root' in sel:
                continue
            # the offsets may live in ANOTHER rule (g24 declares .br's position, #tl/#tr its left/top):
            # resolve the cascade per element and name only the elements that really land at 0,0.
            els = [e for e in dom.els if any(_sel(e, br) for br in sel.split(','))]
            bare = [e for e in els if not (OFFSETS & set(dec[id(e)]))]
            if els and not bare: continue
            who = ' / '.join(_name(e) for e in bare) if bare else sel.strip()[:40]   # no match = built in JS, the g3 case
            self.note(gid, 'source', 'warn', f'{who} is position:absolute with no offsets (lands at 0,0 of its parent, the g3 check-dot bug)')
        # exits never before entrances (numeric or simple expressions)
        env = {}
        for name, val in re.findall(r'const\s+(DUR|F|SF|S12)\s*=\s*([^,;]+)', js):
            try: env[name] = eval(val, {'__builtins__': {}}, dict(env))
            except Exception: pass
        def ev(expr):
            try: return float(eval(expr, {'__builtins__': {}}, dict(env)))
            except Exception: return None
        ins, outs = {}, {}
        for fn, sel, t in re.findall(r"\b(%s)\(\s*'([^']+)'\s*,\s*([^,)]+)" % '|'.join(ENTRANCES + EXITS), js):
            v = ev(t.strip())
            if v is None: continue
            (ins if fn in ENTRANCES else outs).setdefault(sel, []).append(v)
        for sel, ts in outs.items():
            if sel in ins and min(ts) < min(ins[sel]):
                self.note(gid, 'source', 'FAIL', f'{sel} exits at {min(ts):.2f}s before it enters at {min(ins[sel]):.2f}s')
        self.check_filter_tween(gid, js)
        self.check_overshoot(gid, js, dom, dec)
        self.check_rise_dist(gid, js, dom, dec)
        if hasattr(self, 'ink') and re.search(r'\b(pop|slam)\s*\(', js):
            # the literal calls are the fallback for a comp with inline helpers: on hf-anim.js the probe hooks every call itself
            lit = [dict(fn=fn, sel=sel, at=ev(t.strip())) for fn, sel, t in re.findall(r"\b(pop|slam)\(\s*'([^']+)'\s*,\s*([^,)]+)", js)]
            self.ink.append(dict(id=gid, path=str(path), calls=[c for c in lit if c['at'] is not None]))
        self.check_authoring(gid, js, dom, dec, cell, full)
        # type never pops (2026-09-10; animations.md § TEXT NEVER POPS): a pop() whose target's OWN text is
        # words is a FAIL. Words inside a child (a node's label, a row's label, the REC badge's span) make a surface.
        for m in re.finditer(r"\bpop\(\s*'([^']+)'\s*[,)]", js):
            sel = m.group(1)
            for el in (e for e in dom.els if _sel(e, sel)):
                if any(c.isalpha() for c in el['text']):
                    self.note(gid, 'source', 'FAIL', f"pop({sel}) on type ({_name(el)}: {el['text'].strip()[:40]!r}): type never pops, "
                              "it rises with the scissors or slams with the Impact (animations.md § TEXT NEVER POPS)", tag='type-pop')
                    break

    def check_filter_tween(self, gid, js):
        """A CSS `filter` STRING cannot be tweened on a seek render. GSAP parses the running value
        from the computed style only when the tween PLAYS; seeking a paused timeline it interpolates
        from the zero filter, so a wall dimmed brightness(0.55) → (0.30) blinked near-black for three
        12 fps frames (your-job g10; an explicit fromTo did not help). Dim through a black
        scrim's OPACITY; a discrete tl.set is fine."""
        for m in re.finditer(r'\b(tl|gsap)\s*\.\s*(to|from|fromTo)\s*\(', js):
            if re.search(r'(?:^|[{,\s\'"])(?:webkit)?[Ff]ilter\s*:', _args(js, m.end() - 1)):
                self.note(gid, 'source', 'FAIL', f'{m.group(1)}.{m.group(2)}() tweens a CSS `filter` string: on a seek render GSAP '
                          'interpolates it from filter(0) and the element blinks (g10). Ride the change on a black '
                          "scrim's opacity, or set the filter discretely with tl.set", tag='filter')

    def check_rise_dist(self, gid, js, dom, dec):
        """THE RISE travels 22 px on a card or panel and is ratio-scaled on type, 22 px at a 90 px font
        (animations.md § Nudge family). The helper's own constant is checked above; a per-call `dist` never
        was, so g15's 168 px counters rose 26 px instead of 41 and g2's player 10 instead of 22 (2026-10-02,
        round 2). A target whose subtree holds a SURFACE (a background not clipped to text, a border) is a
        card; one with no surface is type, scaled by the largest font-size declared in it when that is 90 px or more
        (the helper's 22 px stands under it; no size declared = unknown, skipped)."""
        kids = {}
        for e in dom.els:
            p = e['parent']
            while p is not None:
                kids.setdefault(id(p), []).append(e); p = p['parent']
        def surface(e):
            d = dec[id(e)]
            bg = d.get('background') or d.get('background-color') or ''
            clip = 'text' in (d.get('background-clip', '') + d.get('-webkit-background-clip', ''))
            border = d.get('border') or ''
            return (bg and bg not in ('none', 'transparent') and not clip) or (border and not border.startswith(('none', '0')))
        for m in re.finditer(r"\briseIn\(\s*'([^']+)'\s*,\s*[^,)]+(?:,\s*([\d.]+))?\s*\)", js):
            sel, dist = m.group(1), float(m.group(2)) if m.group(2) else 22.0
            for el in (e for e in dom.els if any(_sel(e, br) for br in sel.split(','))):
                tree = [el] + kids.get(id(el), [])
                if any(surface(e) for e in tree):
                    want, what = 22.0, 'a card or panel'
                else:
                    # every declared size in the subtree: a counter's digits are injected by countUp, never typed
                    sizes = [s for s in (_px(dec[id(e)].get('font-size')) for e in tree) if s]
                    if not sizes or max(sizes) < 90: break      # under 90 px the hand helper's 22 px default stands
                    want, what = 22.0 * max(sizes) / 90.0, f'{max(sizes):g} px type'
                if abs(dist - want) > 2.0:
                    self.note(gid, 'source', 'FAIL', f"riseIn({sel}) travels {dist:g} px; {what} rises {want:.0f} px (animations.md "
                              "§ Nudge family: 22 px, ratio-scaled on type, 22 px at a 90 px font)", tag='rise-dist')
                break

    def check_overshoot(self, gid, js, dom, dec):
        """A pop overshoots to 1.10 (a slam starts at 1.16) for three frames. Best effort from the
        comp's static CSS boxes: the scaled box must not reach a SIBLING it does not already overlap
        at rest (g16's payoff node slid 17 px over the '2-3 hrs' chip, missed by three review rounds).
        Unknown or transformed geometry is info, never a FAIL."""
        geo = {k: _box(d) for k, d in dec.items()}
        skipped = []
        for m in re.finditer(r"\b(pop|slam)\(\s*'([^']+)'\s*[,)]", js):
            fn, sel = m.group(1), m.group(2)
            k = POP_OVER if fn == 'pop' else SLAM_FROM
            targets = [e for e in dom.els if _sel(e, sel)]
            if not targets:
                skipped.append(f'{fn}({sel}): no such element in the markup (built in JS?)'); continue
            for el in targets:
                b, d = geo[id(el)], dec[id(el)]
                if not b:
                    skipped.append(f'{fn}({sel}) -> {_name(el)}: no explicit left/top/width/height'); continue
                if _shifted(d):
                    skipped.append(f'{fn}({sel}) -> {_name(el)}: a transform moves it off its CSS box'); continue
                o = _origin(d, b)
                if not o:
                    skipped.append(f'{fn}({sel}) -> {_name(el)}: unreadable transform-origin'); continue
                big = (o[0] - (o[0] - b[0]) * k, o[1] - (o[1] - b[1]) * k,
                       o[0] + (b[2] - o[0]) * k, o[1] + (b[3] - o[1]) * k)
                hits = {}
                for sib in dom.els:
                    if sib is el or sib['parent'] is None or sib['parent'] is not el['parent']: continue
                    sb = geo[id(sib)]
                    if not sb or _shifted(dec[id(sib)]): continue
                    rx, ry = _ovl(b, sb)
                    if rx > 0 and ry > 0: continue          # already overlapping at rest: authored
                    ox, oy = _ovl(big, sb)
                    if ox > 1 and oy > 1:
                        # an <svg>'s box is its FRAME, not its ink (g16's arrow draws to 104 of its 130 px):
                        # that pair is a warn the reviewer confirms on the render, never a gate-blocking FAIL
                        hits.setdefault((round(ox), round(oy), 'svg' in (el['tag'], sib['tag'])), []).append(_name(sib))
                for (ox, oy, soft), names in sorted(hits.items(), key=lambda h: -h[0][0] * h[0][1]):
                    head = f'{fn}({sel}) overshoot x{k:.2f} puts {_name(el)} {ox}x{oy} px over ' + ' / '.join(names)
                    if not soft:
                        self.__dict__.setdefault('ov_boxed', set()).update((gid, _name(el), n) for n in names)
                        # the finding's index: check_overshoot_ink drops it to info when the ink of every pair measures clear
                        self.__dict__.setdefault('ov_notes', []).append((len(self.findings), gid, _name(el), names, head))
                    self.note(gid, 'source', 'warn' if soft else 'FAIL', head
                              + (' (svg box, not its ink: confirm on the render)' if soft
                                 else ': shift or shrink the NEIGHBOUR, never the pop (or waive it: source:overshoot)'), tag='overshoot')
        for m in re.finditer(r"\b(pop|slam)\(\s*(?!'[^']+'\s*[,)])", js):
            skipped.append(f'{m.group(1)}() on a computed selector')
        if skipped:
            self.note(gid, 'source', 'info', 'overshoot unmeasured on ' + '; '.join(skipped))

    def check_overshoot_ink(self):
        """The same law on the RENDERED INK, for every comp with a pop or slam: workflows/overshoot-ink.mjs loads the comp in
        headless Chrome, seeks each rendered frame of the overshoot and screenshots the target and every neighbour ALONE
        (siblings of the target and of each ancestor), so a TYPE neighbour (no CSS box: its box is its glyphs) and an
        SVG-wrapped prop (a div around an svg, whose ink is not its frame) are measured as drawn. g9 (2026-09-28): the
        controller popped at left 320 beside a 40 px Black "or" at left 283 and covered its "r" for two frames; the
        static check skipped the box-less text and wrote no overshoot entry at all. A pair already overlapping at rest
        is authored, as above; a pair the static boxes already FAILed is not reported twice. One browser for the job."""
        if not self.ink: return
        def unmeasured(ids, why):
            for g in ids:
                self.note(g, 'source', 'warn', f'overshoot on rendered ink UNMEASURED: {why}: a type or SVG-wrapped neighbour '
                          'the static boxes cannot see is unchecked (confirm the pops on the render)', tag='overshoot')
        node = shutil.which('node')
        if not node or not OVERSHOOT_INK.exists():
            return unmeasured([c['id'] for c in self.ink], 'no node on PATH' if not node else f'{OVERSHOOT_INK.name} missing')
        with tempfile.TemporaryDirectory() as td:
            sp = Path(td) / 'spec.json'
            sp.write_text(json.dumps(dict(comps=self.ink, fps=self.fps, alpha=ALPHA_INK)), encoding='utf-8')
            try:
                r = subprocess.run([node, str(OVERSHOOT_INK), str(sp)], capture_output=True, text=True, encoding='utf-8',
                                   timeout=90 + 30 * len(self.ink))
                rep = json.loads((r.stdout.strip().splitlines() or ['{}'])[-1])
            except (subprocess.TimeoutExpired, ValueError, OSError) as e:
                return unmeasured([c['id'] for c in self.ink], f'the probe did not answer ({type(e).__name__})')
        if rep.get('error') or 'comps' not in rep:
            return unmeasured([c['id'] for c in self.ink], rep.get('error') or (r.stderr.strip().splitlines() or ['no output'])[-1])
        boxed = getattr(self, 'ov_boxed', set())
        for res in rep['comps']:
            gid = res['id']
            if res.get('error'):
                unmeasured([gid], res['error']); continue
            n_t = n_f = found = dup = 0
            ink = {}   # (target, neighbour) -> [worst ink overlap, overshoot or rest, px²; frames measured]
            for call in res['calls']:
                n_t += 1; n_f += len(call['frames'])
                for h in sorted(call['hits'], key=lambda h: -h['px']):
                    w = ink.setdefault((call['target'], h['neighbour']), [0.0, 0])
                    w[0] = max(w[0], h['px'], h['rest_px']); w[1] += len(h.get('series') or [])
                    if h['rest_px'] >= INK_OVER or h['px'] < INK_OVER: continue      # authored at rest, or clear
                    if (gid, call['target'], h['neighbour']) in boxed:               # the box check already named it
                        dup += 1; continue
                    found += 1
                    k = POP_OVER if call['fn'] == 'pop' else SLAM_FROM
                    bad = sum(1 for _, px in h.get('series') or [] if px >= INK_OVER)
                    what = f"{h['kind']} {h['text']!r}" if h['kind'] == 'type' else h['kind']
                    self.note(gid, 'source', 'FAIL',
                              f"{call['fn']}({call['sel'] or call['target']}) overshoot x{k:.2f} puts {call['target']}'s RENDERED INK "
                              f"{h['px']:.0f} px² ({h['w']:.0f}x{h['h']:.0f}) into {h['neighbour']} ({what}) on {bad} frame(s), worst "
                              f"frame {h['n']} (comp t={h['t']:.3f}s, scale {h['scale']:.2f}), clear at rest: shift or shrink the NEIGHBOUR, "
                              'never the pop (or waive it: source:overshoot)', tag='overshoot')
            # a box FAIL whose every pair the probe MEASURED and found clear on its ink (two SVG-wrapper divs: the wrappers
            # overlap, the drawn shapes never touch) is the box, not a collision: it drops to info naming the ink result.
            # Unmeasured or touching ink leaves the FAIL as it was.
            for i, g, tgt, names, head in getattr(self, 'ov_notes', []):
                got = [ink.get((tgt, n)) for n in names]
                if g != gid or self.findings[i][2] != 'FAIL' or not all(w and w[0] < INK_OVER for w in got): continue
                self.findings[i] = (g, 'source', 'info', f'{head} on the CSS boxes only: the RENDERED INK stays clear ('
                                    + ' / '.join(f'{n} {w[0]:.1f} px² at worst over {w[1]} frame(s)' for n, w in zip(names, got))
                                    + f', FAIL at {INK_OVER:.0f}): a wrapper box, not a collision')
            if not n_t:
                unmeasured([gid], 'no pop/slam call resolved to an element in the loaded comp')
            elif not found:
                self.note(gid, 'source', 'info', f'overshoot measured on rendered ink: {n_t} pop/slam target(s) over {n_f} frame(s), '
                          + ('no collision beyond the box FAIL(s) above' if dup else 'clear of every neighbour')
                          + ('' if res.get('hooked') else ' (literal calls: the comp does not load hf-anim.js)'))

    def check_authoring(self, gid, js, dom, dec, cell, full):
        """The four HTML/CSS traps every one of five parallel builders hit on its first pass (2026-09-19),
        read off the same static geometry check_overshoot uses: an element parked outside a clipping
        ancestor (g35's FREE stamp, opacity 1 and fully clipped inside `.win`), an opacity:0 element no
        script ever turns on, rows split across source lines under `white-space:pre` (g18 lost 3 of 8
        terminal lines to the whitespace text nodes between them), and an overlay authored at REST inside
        a band it leaves as soon as it MOVES (g10/g36 at y780 against an 810 band top = 798 − riseOut 18).
        Unknown or transformed geometry is never a finding."""
        geo = {k: _box(d) for k, d in dec.items()}
        computed_sel = bool(re.search(r"""['"`][#.][\w-]*['"`]\s*\+|\$\{""", js))   # the comp builds selectors in JS
        deep_sel = [s for s in re.findall(r"""['"`]([#.][^'"`]*)['"`]""", js) if ' ' in s.strip()]   # '.arrowbox svg'
        for el in dom.els:
            d = dec[id(el)]
            b = geo[id(el)]
            # clip: an element that must paint OUTSIDE a box is a SIBLING of that box, never a child
            if b and not _shifted(d) and d.get('position') in ('absolute', 'fixed'):
                anc = el['parent']
                while anc is not None and (dec[id(anc)].get('position') or 'static') == 'static':
                    anc = anc['parent']                       # the containing block: only there do left/top read
                da = dec[id(anc)] if anc is not None else {}
                aw, ah = _px(da.get('width')), _px(da.get('height'))
                if any('hidden' in (da.get(k) or '') for k in ('overflow', 'overflow-x', 'overflow-y')) and aw and ah \
                        and (b[2] <= 0 or b[3] <= 0 or b[0] >= aw or b[1] >= ah):
                    self.note(gid, 'source', 'FAIL', f'{_name(el)} is laid out entirely outside {_name(anc)} '
                              f'({b[0]:.0f},{b[1]:.0f} in a {aw:.0f}x{ah:.0f} box) and that box is overflow:hidden: it renders '
                              'NOTHING at any opacity — an element that paints outside a box is a SIBLING of it', tag='clip')
            # unlit: CSS opacity:0 with no script that ever names it (g1's discs shipped invisible). An element
            # lit THROUGH an ancestor counts as named, but only by a DESCENDANT selector (`arrow('.arrowbox svg')`
            # fills the .head polygon) — every comp names its float wrapper, which lights nothing. A comp that
            # builds its selectors ('#b' + i, `${…}`) is too dynamic to judge at all.
            # A PART's static state is not a dead element: a split-part comp (the locked long-graphic SOP,
            # `graphics-build` § split part clips) carries the whole DOM in every part with the elements that
            # part does not light held at 0, so an element whose class has a LIT twin in the same comp is
            # answering the part, not missing an entrance (measured 2026-09-19: one shipped 9-node grid
            # produced 137 of these across its parts, every one of them correct by design).
            if _px(d.get('opacity')) == 0 and not computed_sel \
                    and not any(set(o['cls']) & set(el['cls']) and _px(dec[id(o)].get('opacity')) != 0
                                for o in dom.els if o is not el):
                toks = (['#' + el['id']] if el['id'] else []) + ['.' + c for c in el['cls']]
                anc = el['parent']
                while anc is not None and not any(t in s for s in deep_sel for t in
                                                  (['#' + anc['id']] if anc['id'] else []) + ['.' + c for c in anc['cls']]):
                    anc = anc['parent']
                if toks and anc is None and not any(t in js for t in toks):
                    self.note(gid, 'source', 'FAIL', f'{_name(el)} is opacity:0 and no script selector names it: '
                              'it renders invisible for the whole graphic (give it an entrance, or drop it). A split '
                              'part whose state pair is keyed by ID (#x-on / #x-off) has no class twin to read, so a '
                              'correct off-state reads as this: answer it with a `source:unlit` waiver naming the part',
                              tag='unlit')
            # pre-rows: under white-space:pre the newlines BETWEEN sibling rows are text nodes of their own
            if (d.get('white-space') or '').strip() == 'pre':
                kids = [k for k in dom.els if k['parent'] is el]
                if len(kids) >= 2 and len({k['line'] for k in kids}) > 1:
                    self.note(gid, 'source', 'FAIL', f"{_name(el)} is white-space:pre and its {len(kids)} children are authored on "
                              f"{len({k['line'] for k in kids})} source lines: every newline between them renders as a blank row and the last rows "
                              'clip away invisibly — put the row elements on ONE source line', tag='pre-rows')
        if full: return
        # clearance: the band and the edge margins bound an overlay's EXTREME position, not its rest box.
        # The registry's own travel is known: riseOut lifts 18 px (animations.md), the float drifts 6 px right /
        # 8 px up (subtle), 10/16 (medium) — out and back from the rest, never straddling it (creative-moves.md
        # move 2), so only the TOP and RIGHT extremes carry the travel and the left extreme is the rest itself.
        # Measured only on elements whose left/top really read in the FRAME (every
        # positioned ancestor is a full-frame wrapper), so a card inside a card is never guessed at.
        m = re.search(r"float\([^)]*'(subtle|medium)'\s*\)", js)
        fx, fy = {'subtle': (6, 8), 'medium': (10, 16)}.get(m.group(1) if m else '', (0, 0))
        rise = 18 if 'riseOut(' in js else 0
        top_floor = self.band_top if (cell or {}).get('region') == 'low-band' else TOP_EDGE
        def frame_level(el):
            anc = el['parent']
            while anc is not None:
                da = dec[id(anc)]
                if (da.get('position') or 'static') != 'static' and _px(da.get('inset')) != 0 \
                        and not ((_px(da.get('left')), _px(da.get('top'))) == (0.0, 0.0)
                                 and (_px(da.get('width')), _px(da.get('height'))) == (float(FRAME_W), float(FRAME_H))):
                    return False
                anc = anc['parent']
            return True
        tight = []
        for el in dom.els:
            b, d = geo[id(el)], dec[id(el)]
            if not b or _shifted(d) or not frame_level(el): continue
            if b[2] - b[0] > 0.95 * FRAME_W or b[3] - b[1] > 0.95 * FRAME_H: continue   # a backdrop, not a card
            if b[1] - rise - fy < top_floor:
                tight.append(f'{_name(el)} tops out at y{b[1] - rise - fy:.0f} (rest y{b[1]:.0f}), floor y{top_floor}')
            if b[0] < EDGE:      # the float never travels LEFT, so the left extreme IS the rest
                tight.append(f'{_name(el)} rests at x{b[0]:.0f}, margin {EDGE}')
            if b[2] + fx > FRAME_W - EDGE:
                tight.append(f'{_name(el)} reaches x{b[2] + fx:.0f} (rest x{b[2]:.0f}), margin {EDGE}')
        if tight:
            self.note(gid, 'source', 'warn', 'authored at REST inside its clearance, but riseOut lifts '
                      f'{rise} px and the float drifts {fx} px right / {fy} px up: ' + ' · '.join(tight[:4])
                      + ' (default-overlay-style.md § THE LOW BAND / Placement: the box bounds the EXTREME position)', tag='clearance')

    # ── job-wide ─────────────────────────────────────────────────────────────
    def check_job(self):
        F = 1.0 / self.fps
        rows = sorted(self.rows, key=lambda r: r['start'])
        by_track = {}
        for r in rows: by_track.setdefault(r.get('track', 2), []).append(r)
        for t, rs in by_track.items():
            for a, b in zip(rs, rs[1:]):
                gap = b['start'] - a['end']
                if gap < -0.3 * F:
                    self.note(b['id'], 'holes', 'FAIL', f"overlaps {a['id']} on V{t + 1} by {-gap / F:.1f} frames (overwriteClip would eat the earlier clip)")
                elif 0.3 * F < gap < 3 * F:
                    self.note(b['id'], 'holes', 'warn', f"{gap / F:.1f}-frame hole between {a['id']} and {b['id']} on V{t + 1}, butt-join them or mean the gap")
        placed = {r['id'] for r in self.rows}
        for gid in self.cells:
            if gid not in placed and not self.only_ids:
                self.note(gid, 'plan', 'FAIL', 'graphic:true in the plan but not in placement.json')
        # THE LOW BAND is MEASURED per shoot (default-overlay-style.md § THE LOW BAND): without the plan's own
        # low_band every under-the-face overlay is silently held to the 2026-08-31 reference shoot's numbers
        _scope = f"{self.plan.get('format') or ''} {self.plan.get('preset') or ''}".lower()
        if not self.band_measured and not any(k in _scope for k in ('short', 'tiktok', 'instagram', 'explainer')):
            self.note('job', 'band', 'warn', f'plan has no low_band: measuring against the reference shoot {self.band_top}/{self.band_floor} — '
                      'run `uv run workflows/chin-line.py <base-cut>` and record low_band {top,bottom} in graphics-plan.json')
        # density
        if self.only_ids: return   # a job-level cadence measured on a filtered row set is a lie
        dur = float(self.plan.get('duration') or (rows[-1]['end'] if rows else 0)) or 1
        # every number below is measured over the GRAPHICS SCOPE (see scope_ranges): the stretches this plan
        # is allowed to decorate, which is the whole runtime unless the plan says otherwise
        scope = scope_ranges(self.plan, dur)
        sdur = sum(b - a for a, b in scope) or 1
        scoped = scope != [(0.0, float(dur))]
        if self.plan.get('graphics_scope') is not None and not scoped:
            self.note('job', 'density', 'info', 'graphics_scope carries no machine-readable "ranges": measuring the cadence over the '
                      'whole runtime (write {"ranges": [[a, b], …], "why": "…"} and the numbers follow the scope)')
        # a split graphic counts ONCE, over its whole span: its parts are a build mechanic, and validate-plan.py
        # measures the same collapsed event list — the two gates must not disagree on a gated term
        _g = {}
        for r in rows:
            _g.setdefault((self.cells.get(r['id']) or {}).get('part_of') or r['id'], []).append(r)
        ev = []
        for stem, g in _g.items():
            g.sort(key=lambda x: x['start'])
            ev.append(dict(g[0], id=stem, start=g[0]['start'], end=g[-1]['end']))
        ev.sort(key=lambda x: x['start'])
        per_min = len(ev) / (sdur / 60)
        bare = longest_gap(scope, [(r['start'], r['end']) for r in ev])
        # the creator's own B-roll is a cutaway, not a full-screen GRAPHIC: validate-plan.py never counts a b-roll cell without `bg`
        fulls = [r for r in ev if r.get('kind') == 'full' and not (self.cells.get(r['id']) or {}).get('broll_source')]
        full_s = sum(r['end'] - r['start'] for r in fulls)
        # spread: never more than 40 s of runtime without a full-screen (3 in the first 41 s and none in the last 95 passed
        # every other number here and read front-loaded, your-job 2026-09-10)
        full_gap = longest_gap(scope, [(r['start'], r['end']) for r in fulls])
        msg = (f"{len(ev)} events over {sdur:.1f}s = {per_min:.1f}/min · longest bare stretch {bare:.1f}s · "
               f"full-screens {len(fulls)} = {full_s:.1f}s = {100 * full_s / sdur:.1f}% of runtime, {len(fulls) / (sdur / 60):.1f}/min, "
               f"longest stretch without one {full_gap:.1f}s"
               + (f" (the graphics scope: {len(scope)} range(s) of the {dur:.1f}s runtime)" if scoped else ''))
        lvl = 'info'
        if not (DENSITY['per_min'][0] <= per_min <= DENSITY['per_min'][1] + 0.5) or bare > DENSITY['bare_max'] or 100 * full_s / sdur > DENSITY['full_pct_max'] \
                or full_gap > DENSITY['full_gap_max'] or len(fulls) / (sdur / 60) < DENSITY['full_per_min'][0]:
            lvl = 'warn'
        self.note('job', 'density', lvl, msg)
        for a, b in zip(fulls, fulls[1:]):
            ca, cb = self.cells.get(a['id'], {}), self.cells.get(b['id'], {})
            if ca.get('bg') and ca.get('bg') == cb.get('bg') and not any(r['start'] > a['end'] and r['end'] < b['start'] for r in ev if r.get('kind') != 'full'):
                self.note(b['id'], 'density', 'info', f"same full-screen field ({ca['bg']}) as {a['id']} with nothing between (dark is the default field since 2026-09-10; a light one is an accent, not a rotation)")

    def run(self, only_ids=None):
        self.only_ids = only_ids
        for r in self.rows:
            self.check_row(r)
        if self.fps is None: sys.exit('no readable render: cannot determine the timeline fps')
        self.check_overshoot_ink()
        self.check_job()
        return self.findings


def selftest():
    """The three source assertions that really PARSE (the filter tween, the pop overshoot, type never pops)
    run against a fixture that must fail and one that must not: the rest are one-line regexes whose behaviour
    is obvious by reading them, these go quietly dead (2026-09-03: a comp lookup did exactly that)."""
    src = ('<style>#float{position:absolute;inset:0}\n'
           '#a{position:absolute;left:100px;top:100px;width:100px;height:100px}\n'
           '#b{position:absolute;left:%dpx;top:100px;width:100px;height:100px}</style>\n'
           '<body><div id="float"><div id="a"></div><div id="b"></div><div id="c">words</div></div>\n'
           '<script src="hf-anim.js"></script><script>const DUR = 3;\n'
           "float('#float', 0, DUR, 'subtle'); pop('#a', 0); %s</script></body>")
    want = {'bad': ('filter', 'never pops', 'overshoot'), 'good': ()}
    with tempfile.TemporaryDirectory() as td:
        for name, args in (('bad', (200, "tl.to('#a', {filter: 'brightness(0.3)', duration: 0.3}, 0); pop('#c', 0);")),
                           ('good', (230, "tl.set('#a', {filter: 'brightness(0.3)'}, 0);"))):
            qa = QA.__new__(QA); qa.waivers, qa.findings = {}, []
            p = Path(td) / f'{name}.html'; p.write_text(src % args, encoding="utf-8")
            qa.lint_comp(name, p, None, False)
            fails = [f for f in qa.findings if f[2] == 'FAIL']
            got = tuple(k for k in ('filter', 'never pops', 'overshoot') if any(k in f[3] for f in fails))
            if got != want[name] or len(fails) != len(want[name]):
                sys.exit(f'selftest FAILED on the {name} fixture: expected {want[name] or "no FAIL"}, got '
                         + (' / '.join(f'{f[2]} {f[3][:90]}' for f in qa.findings) or 'nothing'))
    # the four authoring traps, each on a fixture that must trip it and one that must not (the same comp
    # with the stamp moved out of the clipping box, the rows on one line, the ghost given an entrance and
    # the card inside its margin). They read real geometry, so they earn the same treatment as the three above.
    auth = ('<style>#float{position:absolute;inset:0}\n'
            '.win{position:absolute;left:400px;top:200px;width:600px;height:400px;overflow:hidden}\n'
            '.stamp{position:absolute;left:%dpx;top:%dpx;width:120px;height:60px}\n'
            '.body{position:absolute;left:20px;top:20px;width:200px;height:200px;white-space:pre}\n'
            '.ghost{position:absolute;left:900px;top:400px;width:40px;height:40px;opacity:0}\n'
            '#card{position:absolute;left:%dpx;top:700px;width:300px;height:200px}</style>\n'
            '<body><div id="float"><div class="win">%s<div class="body">%s</div></div>%s\n'
            '<div class="ghost"></div><div id="card"></div></div>\n'
            '<script src="hf-anim.js"></script><script>const DUR = 3;\n'
            "float('#float', 0, DUR, 'subtle'); riseOut('#card', 2); %s</script></body>")
    ROWS_SPLIT = '<div class="row">a</div>\n<div class="row">b</div>'
    KEYS = ('overflow:hidden', 'no script selector names it', 'white-space:pre', 'riseOut lifts')
    awant = {'bad': KEYS, 'good': ()}
    with tempfile.TemporaryDirectory() as td:
        STAMP = '<div class="stamp"></div>'
        for name, args in (('bad', (640, -80, 60, STAMP, ROWS_SPLIT, '', '')),                 # a child of .win, laid out above it
                           ('good', (960, 160, 100, '', ROWS_SPLIT.replace('\n', ''), STAMP, "riseIn('.ghost', 0.5);"))):
            qa = QA.__new__(QA); qa.waivers, qa.findings, qa.band_top = {}, [], 765
            p = Path(td) / f'{name}.html'; p.write_text(auth % args, encoding="utf-8")
            qa.lint_comp(name, p, None, False)
            got = tuple(k for k in KEYS if any(k in f[3] for f in qa.findings if f[2] in ('FAIL', 'warn')))
            if got != awant[name]:
                sys.exit(f'selftest FAILED on the authoring {name} fixture: expected {awant[name] or "nothing"}, got '
                         + (' / '.join(f'{f[2]} {f[3][:90]}' for f in qa.findings) or 'nothing'))
    # THE RISE's per-call distance (2026-10-02): a card at 22, type of 90 px or more on the ratio
    rise = ('<style>#float{position:absolute;inset:0}\n'
            '.card{position:absolute;left:100px;top:100px;width:300px;height:200px;background:#222}\n'
            '/* a comment before the rule must not hide it */\n'
            '.big{position:absolute;left:600px;top:400px;font-size:180px}\n'
            '.lab{position:absolute;left:900px;top:100px;font-size:32px}</style>\n'
            '<body><div id="float"><div class="card"></div><div class="big">17</div><div class="lab">x</div></div>\n'
            '<script src="hf-anim.js"></script><script>const DUR = 3;\n'
            "float('#float', 0, DUR, 'subtle'); %s</script></body>")
    with tempfile.TemporaryDirectory() as td:
        for name, calls, n in (('bad', "riseIn('.card', 0, 10); riseIn('.big', 0.5, 22); riseIn('.lab', 1);", 2),
                               ('good', "riseIn('.card', 0); riseIn('.big', 0.5, 44); riseIn('.lab', 1);", 0)):
            qa = QA.__new__(QA); qa.waivers, qa.findings = {}, []
            p = Path(td) / f'{name}.html'; p.write_text(rise % calls, encoding="utf-8")
            qa.lint_comp(name, p, None, False)
            got = [f for f in qa.findings if f[2] == 'FAIL' and 'riseIn(' in f[3]]
            if len(got) != n:
                sys.exit(f'selftest FAILED on the rise {name} fixture: expected {n} FAIL, got '
                         + (' / '.join(f'{f[2]} {f[3][:90]}' for f in qa.findings) or 'nothing'))
    print('selftest OK')


def main():
    a = sys.argv[1:]
    if '--selftest' in a: return selftest()
    if not a: sys.exit(__doc__)
    job = a[0]
    ids = None; out = None; fps = None
    if '--ids' in a: ids = a[a.index('--ids') + 1].split(',')
    if '--json' in a: out = a[a.index('--json') + 1]
    if '--fps' in a:
        num, _, den = a[a.index('--fps') + 1].partition('/'); fps = float(num) / float(den or 1)
    qa = QA(job, fps, ids)
    findings = qa.run(ids)
    fails = [f for f in findings if f[2] == 'FAIL']
    for gid in sorted({f[0] for f in findings}, key=lambda g: (g != 'job', g)):
        fs = [f for f in findings if f[0] == gid]
        mark = '✗' if any(f[2] == 'FAIL' for f in fs) else ('·' if all(f[2] == 'info' for f in fs) else '⚠')
        print(f'{mark} {gid}')
        for _, check, level, msg in fs:
            print(f'    {level:<6} {check:<8} {msg}')
    clean = [r['id'] for r in qa.rows if r['id'] not in {f[0] for f in findings}]
    if clean: print('✓ clean: ' + ' '.join(clean))
    print(f"\n{len(fails)} FAIL · {sum(1 for f in findings if f[2] == 'warn')} warn · "
          f"{sum(1 for f in findings if f[2] == 'waived')} waived · {len(qa.rows)} graphics · fps {qa.fps:.3f}")
    if out:
        rep = {'job': str(qa.job), 'fps': qa.fps, 'graphics': [r['id'] for r in qa.rows],
               'findings': [dict(id=g, check=c, level=l, msg=m) for g, c, l, m in findings],
               'waivers': qa.waivers}
        if ids:
            # a targeted run measures only the ids it was given: MERGE it into whatever report is
            # already there instead of replacing 27 graphics of proof with 2 (round-scoped reports
            # are the documented path, this is the guard for the shared one).
            rep['rechecked'] = ids
            try: old = json.load(open(out, encoding="utf-8")) if os.path.exists(out) else None
            except Exception: old = None
            if isinstance(old, dict) and old.get('job') == rep['job'] and old.get('graphics'):
                gids = old['graphics'] + [g for g in rep['graphics'] if g not in old['graphics']]
                rep['findings'] = [f for f in old.get('findings') or [] if f.get('id') not in set(ids)] + rep['findings']
                rep['graphics'] = gids
                print(f'  merged {len(ids)} re-checked id(s) into the {len(gids)}-graphic report')
        json.dump(rep, open(out, 'w', encoding="utf-8"), indent=1)
        print(f'report -> {out}')
    if fails:
        sys.exit(1)


if __name__ == '__main__':
    main()
