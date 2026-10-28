#!/usr/bin/env python3
"""broll-place.py: place the creator's OWN B-roll (a library from broll-index.py) against a job's script, as plan cells.

  uv run workflows/broll-place.py projects/<job> propose [--library <folder|index.json>] [--every 5-10|liberal|light] [--len 2-8] [--top 5]
  uv run workflows/broll-place.py projects/<job> apply <picks.json> [--frame WxH]   # cells into the plan + their renders
  uv run workflows/broll-place.py projects/<job> render [--only br1,br2] [--frame WxH]   # re-conform from the plan's cells

propose  The canonical transcript (outputs/<job>.transcript.json) split into sentence beats (graphics-plan's
         segment-script.py split) becomes SLOTS: a span of 2-8 s (the preset's `len`) where a full-frame cutaway can
         go. A slot starts 2 frames before its first word, ends just after a word, sits clear of every graphic cell
         in graphics-plan.json (captions excepted: they ride on top), inside the plan's graphics_scope, off the
         opening line (the hook stays on the face) and off the closing line, and an edge within 8 frames of a V1
         cut sits ON the cut (off by a frame flashes the other shot). Each slot carries a SHORT candidate list (the
         clips whose description or file name shares the line's words, rarer words weighing more): a pre-filter so
         Claude reads five clips per line, never the library; the choice is Claude's, by what is on screen
         against what is said. A subset is marked `suggested`, spaced at the preset's density (`every`: one cut-in
         every LO-HI seconds, at least 1.5 s of face between two). Writes projects/<job>/broll/own-proposal.json.
apply    Claude's picks ({"picks": [{"slot", "clip", "in"?, "start"?, "end"?, "focus"?, "reason"?}]}) are held to
         the same rules plus the density (no two cut-ins closer than LO, never two cutaways overlapping, the clip
         long enough from its in-point), then written into graphics-plan.json as `kind: "b-roll"` cells carrying
         `broll_source` (the clip, its in-point, the crop focus), each with a silent plain-cut row in
         hf-graphics/sfx-hand.json (footage laid full-frame takes no cut-in whoosh), then rendered. Nothing is
         written unless every pick passes.
render   Each `broll_source` cell is conformed to the job's frame and rate (scale to fill, crop at `focus`, no
         audio: the voice carries on) as hf-graphics/gfx/renders/<id>.mp4, the full-screen render every lane's
         placer picks, with a <file>.render.json record. A changed cell renders to a NEW version name (<id>-b.mp4),
         never over a placed file; an unchanged one is skipped.

Only a preset built for B-roll places it (2026-10-14): the job's preset declares it in its own
presets/<platform>/<preset>/broll.json (`every`, the density; `len`, the clip length; `library`, the default folder).
The shipped presets carry none, so a job on one is refused with how to give a preset B-roll. Inside a B-roll preset,
--every (the creator's own words: "one every 5 to 10 s" = 5-10, `liberal` 5-10, `light` 20-40) and --len override
its numbers. Owner of the flow: the `broll-own` skill (§ Give a preset B-roll).
"""
import argparse, hashlib, importlib.util, json, math, os, re, subprocess, sys, time
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PRESETS = REPO / 'presets'   # a B-roll preset's broll.json lives in its folder here
LEAD_FRAMES = 2            # a cutaway cuts in 2 frames before its word, as a full-screen cut-in does
TAIL = 0.12                # and cuts back just after the last word, inside the pause
SNAP_FRAMES = 8            # an edge this close to a V1 cut sits ON it (validate-plan.py's full-screen rule)
MIN_FACE = 1.5             # seconds of the creator between two cutaways: the face is the brand
LEN = (2.0, 8.0)           # a member's pre-trim range: under 2 s is a flash, over 8 s the face has gone too long
WORDS = {'liberal': (5.0, 10.0), 'light': (20.0, 40.0)}
HOW = ('To give a preset B-roll: copy the preset into its own folder (presets/<platform>/<name>/), add a broll.json with '
       'its density and clip length ({"every": [LO, HI], "len": [2, 8]}), and name that preset in graphics-plan.json '
       '(the broll-own skill, § Give a preset B-roll).')
CATALOGUE_MAX = 150        # a library this small is printed whole, so Claude can pick past the candidate lists
STOP = set('''a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further get gets getting got gonna had
has have having he her here hers him himself his how i if in into is it its itself just know like literally me more
most my myself no nor not now of off on once only or other our ours out over own really right same she should so some
something such than that the their them then there these they thing things this those through to too under until up
very was we were what when where which while who whom why will with would yeah yes you your yours okay ok basically
actually kind sort stuff guys going want wanna need make made way lot one two three time let us said say says don can
won didn doesn isn wasn aren couldn wouldn shouldn ain'''.split())
SEG = None


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def seg():
    """graphics-plan's segment-script.py: the sentence split and its sub-split of long sentences (one beat grid)."""
    global SEG
    if SEG is None:
        SEG = load_module('segment_script', REPO / '.claude' / 'skills' / 'graphics-plan' / 'scripts' / 'segment-script.py')
    return SEG


def index_mod():
    return load_module('broll_index', REPO / 'workflows' / 'broll-index.py')


def ratio(s):
    n, _, d = str(s or '').partition('/')
    try:
        return float(n) / float(d or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def sha12(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()[:12] if Path(p).exists() else None


def stem(w):
    w = w[:-2] if w.endswith("'s") else w
    if w.endswith('s') and not w.endswith('ss') and len(w) > 3: w = w[:-1]
    if w.endswith('ing') and len(w) > 5: w = w[:-3]
    elif w.endswith('ed') and len(w) > 4: w = w[:-2]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in 'aeiouls': w = w[:-1]       # runn -> run, never call -> cal
    return w[:-1] if w.endswith('e') and len(w) > 3 else w                        # phone/phoning -> phon


def tokens(text):
    out = set()
    for w in re.findall(r"[a-z][a-z']*", str(text or '').lower()):
        w = w.split("'")[0]                                  # that's -> that, don't -> don (a stop word)
        if len(w) >= 3 and w not in STOP:
            out.add(stem(w))
    return out


def preset_key(*names):
    for s in names:
        m = re.search(r'presets[/\\]([^/\\]+[/\\][^/\\.]+)', str(s or ''))
        if m:
            return m.group(1).replace('\\', '/')
    return None


def scope_ranges(plan, dur):
    """The plan's graphics_scope ranges (validate-plan.py's reading): B-roll stays inside them as graphics do."""
    g = (plan or {}).get('graphics_scope')
    rs = g.get('ranges') if isinstance(g, dict) else None
    out = []
    for r in rs if isinstance(rs, list) else []:
        try:
            a, b = float(r[0]), float(r[1])
        except (TypeError, ValueError, IndexError):
            continue
        if b > a: out.append((a, b))
    return sorted(out) or [(0.0, float(dur))]


def raw_info(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-of', 'json', '-show_streams', str(path)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    v = ((json.loads(r.stdout or '{}').get('streams') or [{}]) + [{}])[0]
    rot = 0
    for sd in v.get('side_data_list') or []:
        if 'rotation' in sd: rot = int(round(float(sd['rotation']))) % 360
    w, h = int(v.get('width') or 0), int(v.get('height') or 0)
    return v.get('r_frame_rate'), ((h, w) if rot in (90, 270) else (w, h))


class Job:
    def __init__(self, path, preset=None, frame=None):
        self.dir = Path(path).resolve()
        if not self.dir.is_dir():
            sys.exit(f'✗ {path}: no such job folder')
        self.tp = self.dir / 'outputs' / f'{self.dir.name}.transcript.json'
        if not self.tp.exists():
            sys.exit(f'✗ no outputs/{self.tp.name}: B-roll is placed against the canonical transcript (rough-cut, step 2)')
        with open(self.tp, encoding='utf-8') as f:
            d = json.load(f)
        self.words = [w for w in (d['words'] if isinstance(d, dict) else d)      # a token the aligner left untimed is skipped
                      if w.get('type', 'word') == 'word' and str(w.get('text', '')).strip() and 'start' in w and 'end' in w]
        if not self.words:
            sys.exit(f'✗ {self.tp.name} has no words')
        self.plan_p = self.dir / 'graphics-plan.json'
        self.plan = None
        if self.plan_p.exists():
            with open(self.plan_p, encoding='utf-8') as f:
                self.plan = json.load(f)
        self.preset = (self.plan or {}).get('preset') or preset
        self.cuts_p = self.dir / 'transcript' / 'cuts.json'
        self.rev = sha12(self.cuts_p)
        self.off = float((self.plan or {}).get('timeline_offset') or 0.0)
        self.cuts, total = [], 0.0
        if self.cuts_p.exists():
            with open(self.cuts_p, encoding='utf-8') as f:
                segs = json.load(f).get('segments') or []
            if segs and all(isinstance(s.get('_timeline'), list) for s in segs):
                self.cuts = [float(s['_timeline'][1]) - self.off for s in segs]      # read back from the timeline
            else:
                for s in segs:
                    total += float(s['end']) - float(s['start']); self.cuts.append(total)
        self.dur = (self.cuts[-1] if self.cuts else 0.0) or float(self.words[-1]['end'])
        raws = [p for d_ in (self.dir / 'raw', self.dir.parent.parent / 'raw' if self.dir.parent.name == 'sections' else None)
                if d_ and d_.is_dir() for p in sorted(d_.iterdir())
                if p.suffix.lower() in ('.mp4', '.mov', '.mkv', '.m4v', '.mxf')]
        rfps, rframe = raw_info(raws[0]) if raws else (None, (0, 0))
        self.fps_s = str((self.plan or {}).get('fps') or rfps or '30000/1001')
        self.fps = ratio(self.fps_s) or 30000 / 1001
        self.F = 1.0 / self.fps
        self.frame = tuple(frame) if frame else (rframe if all(rframe) else None)

    def snap(self, t):
        return round(round(t / self.F) * self.F, 5)

    def shown(self):
        try:
            return self.dir.relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return self.dir.as_posix()


# ── density ──────────────────────────────────────────────────────────────────

def parse_range(s, what):
    if s in WORDS: return WORDS[s]
    m = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*', str(s))
    if not m: sys.exit(f'✗ {what} {s!r}: LO-HI seconds (e.g. 5-10){", liberal or light" if what == "--every" else ""}')
    lo = float(m.group(1)); hi = float(m.group(2) or lo)
    if not 0 < lo <= hi: sys.exit(f'✗ {what} {s!r}: needs 0 < LO <= HI')
    return lo, hi


def preset_broll(job):
    """(preset key, its broll.json). Refuses a job whose preset declares no B-roll: the shipped presets carry none."""
    key = preset_key(job.preset)
    if not key:
        sys.exit('✗ no preset named for this job (graphics-plan.json `preset`, or propose --preset): B-roll is placed only '
                 f'on a preset built for it. {HOW}')
    p = PRESETS / key / 'broll.json'
    if not p.is_file():
        sys.exit(f'✗ presets/{key} has no B-roll (no broll.json): B-roll is placed only on a preset built for it. {HOW}')
    with open(p, encoding='utf-8') as f:
        return key, json.load(f)


def density(job, every=None, length=None):
    """(rules, library folder or None) from the preset's broll.json; --every and --len override it."""
    key, cfg = preset_broll(job)
    if every:
        e, src = parse_range(every, '--every'), 'asked (--every)'
    elif cfg.get('every'):
        e, src = tuple(float(x) for x in cfg['every']), f'presets/{key}/broll.json'
    else:
        sys.exit(f'✗ presets/{key}/broll.json names no density: add "every": [LO, HI] (one cut-in every LO-HI seconds)')
    L = parse_range(length, '--len') if length else tuple(float(x) for x in cfg.get('len') or LEN)
    return dict(every=list(e), len=list(L), min_face=MIN_FACE, source=src), cfg.get('library')


# ── slots ────────────────────────────────────────────────────────────────────

class Space:
    """Where a cutaway may sit: inside the graphics scope, off the opening and closing lines, clear of every graphic."""
    def __init__(self, job, beats):
        self.job = job
        self.occ = [(float(c['start']), float(c['end']), str(c.get('id')))
                    for c in (job.plan or {}).get('beats', [])
                    if c.get('graphic') and c.get('kind') != 'captions' and not c.get('broll_source')
                    and c.get('start') is not None and c.get('end') is not None]
        self.blocked = [(-1e9, float(beats[0][-1]['end']), 'the opening line')] + list(self.occ)
        if len(beats) > 1:
            self.blocked.append((float(beats[-1][0]['start']) - LEAD_FRAMES * job.F, 1e9, 'the closing line'))
        rs = scope_ranges(job.plan, job.dur)
        edges = [-1e9] + [x for r in rs for x in r] + [1e9]
        self.blocked += [(edges[i], edges[i + 1], 'outside the graphics scope') for i in range(0, len(edges), 2)
                         if edges[i + 1] > edges[i]]

    def hits(self, s, e):
        tol = 0.5 * self.job.F
        return [b for b in self.blocked if s < b[1] - tol and b[0] < e - tol]

    def snap_cuts(self, s, e):
        F = self.job.F
        for c in self.job.cuts:
            if 1e-4 < abs(c - s) <= SNAP_FRAMES * F: s = c
            if 1e-4 < abs(c - e) <= SNAP_FRAMES * F: e = c
        return s, e

    def fit(self, s, e, lmin, lmax):
        """(s, e) trimmed off whatever blocks it, edges on the frame grid or ON a V1 cut, or None."""
        job, F = self.job, self.job.F
        for _ in range(6):
            hit = self.hits(s, e)
            if not hit: break
            for b0, b1, _why in hit:
                if b0 <= s:                                     # blocks the start: begin on the first word after it
                    w = next((w for w in job.words if w['start'] - LEAD_FRAMES * F >= b1 - 1e-6), None)
                    if not w: return None
                    s = job.snap(w['start'] - LEAD_FRAMES * F)
                else:                                           # blocks the end: end on the last word before it
                    w = next((w for w in reversed(job.words) if w['end'] <= b0 - F and w['start'] >= s), None)
                    if not w: return None
                    e = math.floor(min(w['end'] + TAIL, b0) / F + 1e-6) * F
            if e - s < lmin - 1e-6: return None
        if self.hits(s, e): return None
        e = min(e, s + math.floor(lmax / F + 1e-6) * F)
        s, e = self.snap_cuts(s, e)
        if self.hits(s, e) or not (lmin - 1e-6 <= e - s <= lmax + 1e-6): return None
        return round(s, 5), round(e, 5)


def beats_of(words):
    S = seg()
    sents, cur = [], []
    for w in words:
        cur.append(w)
        if str(w['text']).strip().rstrip('"\'’”)').endswith(S.SENT_END):
            sents.append(cur); cur = []
    if cur: sents.append(cur)
    return [run for s in sents for run in S.split_long(s)]


def make_slots(job, rules):
    lmin, lmax = rules['len']
    beats = beats_of(job.words)
    space = Space(job, beats)
    F, out = job.F, []
    for i, ws in enumerate(beats):
        nxt = beats[i + 1][0]['start'] if i + 1 < len(beats) else ws[-1]['end'] + TAIL
        s = job.snap(ws[0]['start'] - LEAD_FRAMES * F)
        k = len(ws) - 1
        while k > 0 and ws[k]['end'] - s > lmax: k -= 1
        after = ws[k + 1]['start'] if k + 1 < len(ws) else nxt
        e = job.snap(min(ws[k]['end'] + TAIL, max(ws[k]['end'], after)))
        got = space.fit(s, e, lmin, lmax)
        if not got: continue
        s, e = got
        line = ' '.join(str(w['text']).strip() for w in job.words if s - 1e-6 <= w['start'] and w['end'] <= e + TAIL)
        out.append(dict(start=s, end=e, line=line, covers_cuts=sum(1 for c in job.cuts if s + F < c < e - F)))
    for n, sl in enumerate(out, 1):
        sl['id'] = f's{n}'
    return out, space


def matcher(clips):
    docs = {c['id']: tokens(f"{c.get('description', '')} {c.get('name_hint', '')}") for c in clips}
    df = Counter(t for d in docs.values() for t in d)
    idf = {t: math.log(1 + len(clips) / n) for t, n in df.items()}

    def top(text, k, orient, need):
        q = tokens(text)
        scored = []
        for c in clips:
            sc = sum(idf[t] for t in q & docs[c['id']])
            if sc <= 0: continue
            off = orient and c['orientation'] not in (orient, 'square')
            scored.append((round(sc * (0.5 if off else 1.0), 2), c, off))
        scored.sort(key=lambda x: (-x[0], x[1]['path']))
        return [dict(clip=c['id'], path=c['path'], duration=c['duration'], orientation=c['orientation'],
                     text=(c.get('description') or c.get('name_hint') or '')[:140], score=sc,
                     **({'short': f"{c['duration']:.1f} s"} if c['duration'] + 1e-3 < need else {}),
                     **({'crop': f"{c['orientation']} into a {orient} frame"} if off else {}))
                for sc, c, off in scored[:k]]
    return top, docs


def suggest(slots, every, min_face):
    """Cut-ins at the density: each one LO-HI s after the last (the slot with the best match inside that window, then
    the one nearest its middle), never closer than LO, never overlapping, MIN_FACE of the creator between two. A window
    where no line matches any clip takes the next line that does, up to 2 x HI away, rather than suggest a slot that
    would only be dropped."""
    lo, hi = every
    mid = (lo + hi) / 2
    out, prev = [], None
    while True:
        ref = prev['start'] if prev else 0.0
        feas = [x for x in slots if x['start'] > ref + 1e-6 and (prev is None or (
            x['start'] - prev['start'] >= lo - 1e-6 and x['start'] - prev['end'] >= min_face - 1e-6))]
        if not feas: break
        win = [x for x in feas if x['start'] - ref <= hi + 1e-6]
        if not any(x['best'] > 0 for x in win):
            win = [x for x in feas if x['best'] > 0 and x['start'] - ref <= 2 * hi + 1e-6][:1] or win
        best = min(win, key=lambda x: (-x['best'], abs(x['start'] - ref - mid), x['start'])) if win else feas[0]
        out.append(best)
        prev = best
    return out


def resolve_library(job, arg, preset_lib):
    IDX = index_mod()
    cand = arg or None
    if not cand and (job.dir / 'broll' / 'library.json').exists():
        with open(job.dir / 'broll' / 'library.json', encoding='utf-8') as f:
            cand = json.load(f).get('index')
    cand = cand or preset_lib
    if not cand:
        sys.exit('✗ no B-roll library for this job: `uv run workflows/broll-index.py <folder> --job '
                 f'{job.shown()}` first (or --library <folder>)')
    p = Path(cand).expanduser()
    if p.suffix == '.json': ip = p
    elif (p / 'index.json').exists(): ip = p / 'index.json'
    else: ip = IDX.default_cache(p) / 'index.json'
    if not ip.exists():
        sys.exit(f'✗ no library index at {ip}: run `uv run workflows/broll-index.py {cand}` first')
    return ip.resolve(), IDX.load_index(ip.parent)


def orient_of(frame):
    return None if not frame else 'landscape' if frame[0] > frame[1] else 'portrait' if frame[1] > frame[0] else 'square'


def propose(job, library=None, every=None, length=None, top=5, log=print):
    rules, preset_lib = density(job, every, length)
    ip, idx = resolve_library(job, library, preset_lib)
    clips = [c for c in idx['clips'] if c['duration'] >= rules['len'][0]]
    find, docs = matcher(clips)
    slots, _ = make_slots(job, rules)
    orient = orient_of(job.frame)
    for sl in slots:
        sl['candidates'] = find(sl['line'], top, orient, sl['end'] - sl['start'])
        sl['best'] = sl['candidates'][0]['score'] if sl['candidates'] else 0.0
    picked = {id(x) for x in suggest(slots, rules['every'], rules['min_face'])}
    for sl in slots:
        sl['suggested'] = id(sl) in picked
        sl.pop('best')
    sugg = [s for s in slots if s['suggested']]
    lo, hi = rules['every']
    gaps = [[a['start'], b['start']] for a, b in zip(sugg, sugg[1:]) if b['start'] - a['start'] > hi + 1e-6]
    prop = dict(job=job.dir.name, preset=job.preset, made=time.strftime('%Y-%m-%dT%H:%M:%S'), cut_rev=job.rev, transcript=sha12(job.tp),
                library=str(ip), root=idx.get('root'), density=rules, fps=job.fps_s, frame=list(job.frame or []),
                slots=slots, gaps=gaps)
    out = job.dir / 'broll' / 'own-proposal.json'
    out.parent.mkdir(exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(prop, f, indent=1, ensure_ascii=False)
    blind = [c for c in clips if not docs[c['id']]]
    short = len(idx['clips']) - len(clips)
    log(f"library: {idx.get('root')} · {len(idx['clips'])} clip(s), {len(clips) - len(blind)} matchable by description or "
        f"file name" + (f", {short} under {rules['len'][0]:g} s left out" if short else '')
        + (f"; {len(blind)} say nothing yet: `uv run workflows/broll-index.py \"{idx.get('root')}\" --pages`, then describe "
           "them" if blind else ''))
    log(f"density: a cut-in every {lo:g}-{hi:g} s, {rules['len'][0]:g}-{rules['len'][1]:g} s each, ≥ {MIN_FACE:g} s of face "
        f"between two · {rules['source']}")
    log(f'{len(slots)} slot(s) fit (clear of graphics, the opening and the closing line); {len(sugg)} suggested (★)')
    for sl in slots:
        mark = '★' if sl['suggested'] else ' '
        cov = f"  covers {sl['covers_cuts']} cut(s)" if sl['covers_cuts'] else ''
        log(f"{mark} {sl['id']:<4} {sl['start']:8.3f}-{sl['end']:8.3f} {sl['end'] - sl['start']:4.1f}s{cov}  \"{sl['line'][:90]}\"")
        if sl['suggested']:
            for c in sl['candidates']:
                extra = ''.join(f"  {k}: {c[k]}" for k in ('short', 'crop') if k in c)
                log(f"        {c['clip']}  {c['duration']:5.1f}s {c['orientation'][0].upper()}  {c['text'][:80]}  [{c['score']}]{extra}")
    for a, b in gaps:
        log(f'  ⚠ {a:.1f} → {b:.1f}: {b - a:.1f} s between suggested cut-ins, over {hi:g} (no slot in that window, or none with a match)')
    if len(clips) <= CATALOGUE_MAX:
        log(f'catalogue ({len(clips)} clip(s) of {rules["len"][0]:g} s or more):')
        for c in clips:
            log(f"  {c['id']}  {c['duration']:5.1f}s {c['orientation'][0].upper()}  {(c.get('description') or c.get('name_hint') or '(nothing yet)')[:100]}")
    log(f'→ {out}\n  pick a clip per ★ slot (swap a ★ for a nearby slot when the match is better there; drop one with no '
        f'fitting clip), write {{"picks": [{{"slot", "clip", "in"?}}]}}, then `apply <picks.json>`')
    return prop


# ── apply ────────────────────────────────────────────────────────────────────

def load_picks(path):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    return d['picks'] if isinstance(d, dict) else d


def check(job, prop, picks, space, clips, root):
    """(cells, every reason a pick is refused). Same rules as propose, plus the density and the clip's own length."""
    rules = prop['density']
    lmin, lmax = rules['len']
    lo, _hi = rules['every']
    slots = {s['id']: s for s in prop['slots']}
    F, errs, cells = job.F, [], []
    for p in picks:
        tag = f"{p.get('slot')}/{p.get('clip')}"
        sl, c = slots.get(p.get('slot')), clips.get(p.get('clip'))
        if not sl: errs.append(f'{tag}: no slot {p.get("slot")!r} in the proposal'); continue
        if not c: errs.append(f'{tag}: clip {p.get("clip")!r} is not in the library'); continue
        s = float(p.get('start', sl['start'])); e = float(p.get('end', sl['end']))
        if 'start' in p or 'end' in p:
            s, e = space.snap_cuts(job.snap(s), job.snap(e))
        need = e - s
        cin = float(p['in']) if p.get('in') is not None else max(0.0, (c['duration'] - need) / 2)
        if cin < 0: errs.append(f'{tag}: in {cin} < 0'); continue
        if cin + need > c['duration'] + 1e-3:
            short = f"{c['path']} is {c['duration']:.2f} s, from in {cin:.2f} it covers {c['duration'] - cin:.2f} s"
            if 'end' in p:
                errs.append(f'{tag}: {short} and the span needs {need:.2f} s'); continue
            e = s + math.floor((c['duration'] - cin) / F + 1e-6) * F       # the clip runs out: cut back early
            later = [x for x in job.cuts if 1e-4 < x - e <= SNAP_FRAMES * F]
            if later:
                errs.append(f'{tag}: {short}, so it would end {(later[0] - e) / F:.1f} frames before the V1 cut at '
                            f'{later[0]:.5f} (a flash of the other shot): an earlier in-point or a longer clip'); continue
            e = next((x for x in job.cuts if 1e-4 < e - x <= SNAP_FRAMES * F), e)
            need = e - s
        if not (lmin - 1e-6 <= need <= lmax + 1e-6):
            errs.append(f'{tag}: {need:.2f} s, outside the {lmin:g}-{lmax:g} s a cutaway runs (--len on propose to change it)'); continue
        hit = space.hits(s, e)
        if hit:
            errs.append(f"{tag}: {s:.3f}-{e:.3f} overlaps {', '.join(h[2] for h in hit)}"); continue
        near = [x for x in job.cuts for t in (s, e) if 1e-4 < abs(x - t) <= SNAP_FRAMES * F]
        if near:
            errs.append(f'{tag}: an edge sits {min(abs(x - t) for x in near for t in (s, e)) / F:.1f} frames off the V1 cut '
                        f'at {near[0]:.5f}: put it ON the cut'); continue
        fx, fy = (p.get('focus') or [0.5, 0.5])[:2]
        if not (0 <= fx <= 1 and 0 <= fy <= 1): errs.append(f'{tag}: focus {p.get("focus")} outside 0-1'); continue
        text = c.get('description') or c.get('name_hint') or ''
        cells.append(dict(
            start=round(s, 5), end=round(e, 5), line=sl['line'], graphic=True, kind='b-roll', region='full-screen', copy='',
            content=(f"Own B-roll cutaway, full frame, a hard cut in and out while the voice carries on: {c['path']} from "
                     f"{cin:.2f} s ({text[:120]}). Conformed by broll-place.py, no comp."),
            reason=p.get('reason') or 'shows what the line says with the creator\'s own footage',
            broll_source=dict(clip=c['id'], path=str(Path(root) / c['path']), rel=c['path'], **{'in': round(cin, 4)},
                              focus=[fx, fy], library=prop['library'])))
    cells.sort(key=lambda x: x['start'])
    for a, b in zip(cells, cells[1:]):
        if b['start'] < a['end'] - 1e-6:
            errs.append(f"{b['broll_source']['clip']} at {b['start']:.3f} overlaps the cutaway at {a['start']:.3f}-{a['end']:.3f}")
        elif b['start'] - a['start'] < lo - 1e-6:
            errs.append(f"cut-ins at {a['start']:.3f} and {b['start']:.3f} are {b['start'] - a['start']:.2f} s apart, under the "
                        f"density's {lo:g} s (propose with --every to change it)")
        elif b['start'] - a['end'] < MIN_FACE - 1e-6:
            errs.append(f"only {b['start'] - a['end']:.2f} s of the creator between the cutaways at {a['start']:.3f} and "
                        f"{b['start']:.3f} (≥ {MIN_FACE:g})")
    return cells, errs


def apply(job, picks_path, frame=None, log=print):
    pp = job.dir / 'broll' / 'own-proposal.json'
    if not pp.exists():
        sys.exit('✗ no broll/own-proposal.json: run `propose` first')
    with open(pp, encoding='utf-8') as f:
        prop = json.load(f)
    job.preset = job.preset or prop.get('preset')
    preset_broll(job)
    if (prop.get('cut_rev'), prop.get('transcript')) != (job.rev, sha12(job.tp)):
        sys.exit('✗ the cut or the transcript changed since the proposal: run `propose` again')
    if job.plan and job.plan.get('cut_rev') and job.rev and job.plan['cut_rev'] != job.rev:
        sys.exit(f"✗ graphics-plan.json was authored against EDL {job.plan['cut_rev']}, the job is on {job.rev}: re-time it "
                 f"first (`uv run workflows/ripple-cut.py {job.shown()} --from <the old cuts.json> --apply`)")
    with open(prop['library'], encoding='utf-8') as f:
        idx = json.load(f)
    clips = {c['id']: c for c in idx['clips']}
    beats = beats_of(job.words)
    cells, errs = check(job, prop, load_picks(picks_path), Space(job, beats), clips, idx['root'])
    if errs:
        log(f'✗ {len(errs)} pick(s) refused, nothing written:')
        for e in errs: log('  ' + e)
        return 1
    used = Counter(c['broll_source']['clip'] for c in cells)
    for k, n in used.items():
        if n > 1: log(f'  ⚠ {clips[k]["path"]} is used {n} times: the same shot twice reads as a loop')
    plan = job.plan or dict(job=job.dir.name, format='long-form' if orient_of(job.frame) != 'portrait' else 'short-form',
                            **({'preset': job.preset} if job.preset else {}), duration=round(job.dur, 5), beats=[])
    old = [b for b in plan['beats'] if b.get('broll_source')]
    keep = [b for b in plan['beats'] if not b.get('broll_source')]
    taken = {str(b.get('id')) for b in keep}
    n = 0
    for c in cells:
        n += 1
        while f'br{n}' in taken: n += 1
        c['id'] = f'br{n}'
    for c in sorted(cells, key=lambda x: x['start'], reverse=True):             # each before the first later beat
        at = next((i for i, b in enumerate(keep) if float(b.get('start') or 0) > c['start']), len(keep))
        keep.insert(at, {'id': c['id'], **{k: v for k, v in c.items() if k != 'id'}})
    plan['beats'] = keep
    with open(job.plan_p, 'w', encoding='utf-8') as f:
        json.dump(plan, f, indent=1, ensure_ascii=False)
    job.plan = plan
    hand_rows(job, {str(b['id']) for b in old}, [c['id'] for c in cells])
    log(f"✓ {len(cells)} own B-roll cell(s) in graphics-plan.json ({', '.join(c['id'] for c in cells) or 'none'})"
        + (f', replacing {len(old)}' if old else ''))
    rc = render(job, frame=frame, log=log)
    log(f'next: `uv run .claude/skills/graphics-plan/scripts/validate-plan.py {job.shown()}`, then the lane places them with '
        'the other graphics (graphics-build § Stage 6)')
    return rc


SILENT_NOTE = 'own B-roll cutaway: a plain cut under the voice, no cut-in sound (footage laid full-frame, 2026-10-02)'


def hand_rows(job, old_ids, new_ids):
    """A silent plain-cut row per cutaway in hf-graphics/sfx-hand.json (sfx-plan.py asks for one: no comp makes it).
    Only rows this tool wrote are replaced; a sound the creator added by hand stays."""
    p = job.dir / 'hf-graphics' / 'sfx-hand.json'
    rows = []
    if p.exists():
        with open(p, encoding='utf-8') as f:
            rows = json.load(f)
    mine = set(old_ids) | set(new_ids)
    rows = [r for r in rows if not (r.get('gid') in mine and r.get('note') == SILENT_NOTE)]
    have = {r.get('gid') for r in rows}
    rows += [dict(gid=g, silent=True, drop=['cut-in'], note=SILENT_NOTE) for g in new_ids if g not in have]
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)


# ── render ───────────────────────────────────────────────────────────────────

def versions(d, gid):
    """This id's renders, oldest version first: <id>.mp4, then <id>-b.mp4, <id>-c.mp4 … (placement.py's letter series)."""
    vs = []
    for p in d.glob(f'{gid}*.mp4'):
        m = re.fullmatch(re.escape(gid) + r'(?:-([a-z]))?\.mp4', p.name)
        if m: vs.append((m.group(1) or '', p))
    return [p for _, p in sorted(vs)]


def render(job, only=None, frame=None, log=print):
    cells = [c for c in (job.plan or {}).get('beats', []) if c.get('broll_source') and (not only or c['id'] in only)]
    if not cells:
        log('no own B-roll cells to render'); return 0
    W, H = frame or job.frame or (0, 0)
    if not (W and H):
        sys.exit('✗ no frame size: no raw/ footage to read it from, pass --frame WxH')
    d = job.dir / 'hf-graphics' / 'gfx' / 'renders'
    d.mkdir(parents=True, exist_ok=True)
    bad = 0
    for c in cells:
        src = c['broll_source']
        sp = Path(src['path'])
        if not sp.exists():
            log(f"✗ {c['id']}: {sp} is offline (plug in the drive the library lives on)"); bad += 1; continue
        n = int(round((float(c['end']) - float(c['start'])) * job.fps))
        fx, fy = (src.get('focus') or [0.5, 0.5])[:2]
        spec = {'source': str(sp), 'in': round(float(src['in']), 4), 'frames': n, 'FPS': job.fps_s, 'frame': [W, H], 'focus': [fx, fy]}
        have = versions(d, c['id'])
        if have:
            rec = have[-1].with_name(have[-1].name + '.render.json')
            if rec.exists():
                with open(rec, encoding='utf-8') as f:
                    r = json.load(f)
                if {k: r.get(k) for k in spec} == spec:
                    log(f"  {c['id']}: {have[-1].name} is current"); continue
            last = have[-1].stem[len(c['id']) + 1:] or 'a'
            if last == 'z':
                log(f"✗ {c['id']}: 26 versions on disk, clear the old renders first"); bad += 1; continue
            name = f"{c['id']}-{chr(ord(last) + 1)}.mp4"
        else:
            name = f"{c['id']}.mp4"
        out, tmp = d / name, d / f'.{name}.part'
        vf = (f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy},'
              f'setsar=1,fps={job.fps_s},format=yuv420p')
        r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-y', '-ss', f"{spec['in']:.4f}", '-i', str(sp), '-frames:v', str(n),
                            '-vf', vf, '-an', '-c:v', 'libx264', '-crf', '14', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                            '-movflags', '+faststart', '-f', 'mp4', str(tmp)], capture_output=True, text=True, errors='replace')
        got = 0
        if r.returncode == 0:
            q = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=nb_frames',
                                '-of', 'json', str(tmp)], capture_output=True, text=True)
            got = int(((json.loads(q.stdout or '{}').get('streams') or [{}])[0]).get('nb_frames') or 0)
        if got != n:
            tmp.unlink(missing_ok=True)
            log(f"✗ {c['id']}: rendered {got} of {n} frames from {sp.name} at {spec['in']:.2f} s"
                + (f": {r.stderr.strip()[-200:]}" if r.returncode else ' (the clip ran out)')); bad += 1; continue
        os.replace(tmp, out)
        with open(out.with_name(out.name + '.render.json'), 'w', encoding='utf-8') as f:
            json.dump(dict(file=name, id=c['id'], mode='own-broll', **spec, date=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                           **{'re-render': f"uv run workflows/broll-place.py {job.shown()} render --only {c['id']}"}),
                      f, indent=1, ensure_ascii=False)
        log(f"  {c['id']}: {name} ← {src['rel']} {spec['in']:.2f} s, {n} frames at {W}x{H}")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p1 = sub.add_parser('propose')
    p1.add_argument('--library', help='the B-roll folder, its index.json or its cache folder (default: broll/library.json)')
    p1.add_argument('--every', help='one cut-in every LO-HI seconds, or liberal (5-10) / light (20-40): overrides the '
                                     "preset's broll.json")
    p1.add_argument('--len', help="a cutaway runs LO-HI seconds (default: the preset's broll.json, else 2-8)")
    p1.add_argument('--top', type=int, default=5, help='candidates per slot')
    p1.add_argument('--preset', help='the preset when there is no graphics-plan.json yet (e.g. presets/youtube/my-broll)')
    p2 = sub.add_parser('apply')
    p2.add_argument('picks')
    p3 = sub.add_parser('render')
    p3.add_argument('--only', help='cell ids, comma-separated')
    for p in (p2, p3):
        p.add_argument('--frame', help='WxH of the timeline (default: the raw footage\'s display size)')
    a = ap.parse_args(argv)
    frame = None
    if getattr(a, 'frame', None):
        m = re.fullmatch(r'(\d+)x(\d+)', a.frame)
        if not m: sys.exit('✗ --frame WxH, e.g. 1920x1080')
        frame = (int(m.group(1)), int(m.group(2)))
    job = Job(a.job, preset=getattr(a, 'preset', None), frame=frame)
    if a.cmd == 'propose':
        propose(job, a.library, a.every, a.len, a.top)
        return 0
    if a.cmd == 'apply':
        return apply(job, a.picks, frame=frame)
    return render(job, only=set(a.only.split(',')) if a.only else None, frame=frame)


if __name__ == '__main__':
    sys.exit(main())
