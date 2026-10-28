#!/usr/bin/env python3
"""validate-plan.py: the hard gate at graphics-plan Step 5: a plan that fails here is not PRESENTED.

  uv run .claude/skills/graphics-plan/scripts/validate-plan.py projects/<job> [--fps 24000/1001]
  uv run .claude/skills/graphics-plan/scripts/validate-plan.py projects/<job> --check   # read-only: stamp nothing

Exit 1 on any FAIL. A PASS also STAMPS the plan with `cut_rev`, the EDL it is valid against
(§ stamp_cut_rev): that stamp is what `lanes/premiere/place-graphics.py` refuses on when the cut has
moved under the plan, and what `workflows/ripple-cut.py` re-writes when it re-times one. Checks (2026-09-02, from the your-job retro, every one is a defect
the build or the review loop later paid for):
  anchor    a text-animation cell STARTS on the first word of its own copy (word.start − 0.08 lead,
            within 0.15s): not on the sentence, not on a guess (g18b, g6). A contraction anchors it and
            warns ("that" against a spoken "that's"); nothing at all prints what IS spoken there.
            A full-screen cut-in that leads no spoken word and sits on no V1 cut WARNS (the reviewer's
            call, not the gate's), and `"anchor": "none"` + the reason in content answers it
  cut       a full-screen / punch-cut edge within 8 frames of a cuts.json boundary sits ON it to the
            frame, exactly: a rounded end flashes the outgoing shot (g2 83 ms, g11 42 ms, g7 25 ms),
            and Premiere floors seconds to ticks, so an end written 16.783 for the cut at 16.78343
            lands the pin a frame early; an edge far from any cut is a cut back mid-take and passes
  readable  a cell flagged "readable": true (prompt, command, code, config, quote) holds ≥ 3.0s
            (a 2s hold of the complete content plus its reveal; the Talking Head Explainer's own hold is under
            `layout` below) and, unless it is a captured file,
            names the source_artifact it is copied from; quote/comment kinds without the
            flag are asked about
  copy      exact written source when source_artifact is set; otherwise no em dash, text animations lowercase-casual (a leading capital that is not a
            proper noun is asked about), copy present on every graphic:true cell (a declared "copy": "" is a
            graphic with no words, and passes silently on any kind but a text animation)
  shape     ids unique, start < end, kind/template/region/content present; two cells in the SAME region may
            never overlap in time (one slot, one graphic — g24 and g25 both took the low band and the
            second clamped the first mid-shot), a cross-region overlap warns; an overlap counts only past half
            a frame (a butt-join at a cut touches to a float's width and is not one); nothing but the caption layer
            overlaps an own B-roll cutaway (`broll_source`)
  fit       the two template caps the plan can be held to, both WARNS: a list card is an eyebrow + max 3 rows,
            and a side callout carrying a capture/screenshot/hero frame declares a `crop` — a crop that IS
            written and fills under half its slot is the one FAIL here, because that one is measured
  capture   a screen-rec / screenshot cell carries "asset" (a file already in the job folder, at
            assets/captures/<id>.<ext>) or "capture" {source, target, action, seconds | still}: the build
            records it, never guesses (graphics-plan § THE CAPTURE GATE, 2026-09-11). It is asked (warn) for what
            it must SHOW ("shows"), and a capture that scrolls carries no annotation pinned to its content
            (2026-09-19: a spinner shipped as the evidence, a circle drifted off its button as the page scrolled)
  hero      a still of the creator inside a graphic is CAST by workflows/hero-frame.py, never grabbed (2026-09-13, a
            hook shipped the beat's plan-frame: mid-word, eyes half shut): no cell names a plan-frames/ file; a cell
            that shows a real frame of the video carries "hero_frame" {t, file}; the pick proof
            review/hero-frames/<id>.pick.json exists, passed, and matches (graphics-plan § THE HERO-FRAME GATE)
  density   the per-minute block printed against creative-moves.md § THE DENSITY NUMBERS, measured over the
            plan's `graphics_scope` ranges when it has them: a stretch the creator bars graphics from is not
            a density hole (12 minutes of walkthrough produced four permanent unsatisfiable warns otherwise).
            Those are LONG-FORM numbers: on a short-form plan the block is printed and nothing is gated on it

  layout    the Talking Head Explainer (the plan's `preset` or `format` names talking-head-explainer): its layout map
            is gated by presets/instagram/talking-head-explainer/layout.py, imported by path and run as its own
            report (the span table, the shares against the benchmark, the rule table, the findings), then once more
            per `variants.<name>` (the ad's own layout tail). Its FAIL rules fail this plan, its WARNs are answered in
            the plan summary, and a missing input it names (face-frame.json `modes`, the transcript) fails the plan
            until it is supplied (layout.md § 13). On this preset `region` and `content` are not required (the
            layout map places every graphic) and a readable cell's hold is its own graphics.md § 13 WARN (about 2 s
            once whole), never the long-form 3.0 s FAIL

A gate here FAILS only what is a defect on its own terms. A field the plan simply has not written down is a
warn: five shipped, creator-approved plans predate half of these, and a gate that fails approved work stops
being read (2026-09-19).
"""
import hashlib, importlib.util, json, re, sys, subprocess, glob
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path

LEAD = 0.08
FULL_KINDS = {'punch-cut', 'full-screen', 'scene', 'kinetic-title'}
TH_READ_HOLD = 2.0         # the Talking Head Explainer's read hold, a WARN (its graphics.md § 13), never the long-form 3.0 s
TEXT_KINDS = {'text-animation'}
LIST_ROWS = 3              # eyebrow + max 3 rows (default-overlay-style.md § THE SIX TEMPLATES)
# the side callout's MAXIMUM box (same doc § Placement / § SIDE CALLOUTS): the real width is measured per
# window and capped at 620, so this is an ASPECT test — does the crop's shape fill a box of that shape — and
# never a claim about the slot this callout actually got. The measured width is chin-line.py's, not a constant.
CALLOUT_W, CALLOUT_H = 620, 560
# the words that name a mark drawn ON the capture. Deliberately NOT "ring": a shipped plan's "three sky ring
# arcs pulse out from the phone" is a prop, not an annotation, and this drives a FAIL.
ANNOTATION = re.compile(r'\b(circle[ds]?|circling|underline[ds]?|highlight(?:s|ed|ing)?|marker)\b', re.I)
FILLERS = {"um", "uh", "like", "you", "know", "so", "right", "okay", "ok", "actually", "basically", "just",
           "literally", "kinda", "kind", "of", "sort", "i", "mean", "yeah", "well", "and", "then"}
PROPER = {'claude', 'premiere', 'cfo', 'youtube', 'instagram', 'tiktok', 'p&l', 'ai'}   # plus any word the transcript itself capitalizes


def _num(v):
    try: return float(v or 0)
    except (TypeError, ValueError): return 0.0


def norm(w):
    return re.sub(r"^[^\w']+|[^\w']+$", '', w).lower()


def stem_word(w):
    """The word without its contraction tail: the transcript says "that's" where the copy wrote "that",
    and an exact-token anchor crashed the plan over it (2026-09-19)."""
    return re.sub(r"('s|'re|'ve|'ll|'m|'d|n't)$", '', w)


def scope_ranges(plan, dur):
    """The stretches of runtime the plan may decorate — `"graphics_scope": {"ranges": [[a, b], ...]}` — else
    the whole thing. The cadence is measured over the SCOPE, never the runtime (creative-moves.md § THE
    DENSITY NUMBERS); graphics-qa.py reads the same field the same way."""
    rs = (plan.get('graphics_scope') or {}).get('ranges') if isinstance(plan.get('graphics_scope'), dict) else None
    out = []
    for r in rs if isinstance(rs, list) else []:
        try: a, b = float(r[0]), float(r[1])
        except (TypeError, ValueError, IndexError, KeyError): continue
        if b > a: out.append((a, b))
    return sorted(out) or [(0.0, float(dur))]


def longest_gap(ranges, spans):
    """The longest stretch INSIDE the scope carrying none of `spans`; each range is walked on its own, so the
    runtime BETWEEN two ranges is never a hole."""
    worst, where = 0.0, ''
    for a, b in ranges:
        prev, prev_id = a, f'{a:.0f}s'
        for s, e, gid in sorted(spans):
            if e <= a or s >= b: continue
            if max(s, a) - prev > worst: worst, where = max(s, a) - prev, f'{prev_id} → {gid}'
            if e > prev: prev, prev_id = min(e, b), gid
        if b - prev > worst: worst, where = b - prev, f'{prev_id} → {b:.0f}s'
    return worst, where


def stamp_cut_rev(job, plan, path, failed, check):
    """A VALIDATED plan names the EDL it was authored against: `cut_rev`, the first 12 hex of sha1 over
    `transcript/cuts.json`. The same 12-hex form `workflows/ripple-cut.py` re-stamps on a re-time and
    `lanes/premiere/place-graphics.py` refuses on when it disagrees — so a plan authored against an old
    cut can no longer reach the placer and put every row on a pre-recut anchor. Until this stamp existed
    every freshly validated plan arrived unstamped and took the placer's warn-once-and-continue path,
    which is the original bug's behaviour.

    Written ONLY on a PASS: a plan carrying FAILs is not the plan that ships, so it never gets the
    certificate. Written only when the value actually CHANGES, so a re-validation does not touch the
    file (or its mtime). `--check` is the read-only path and writes nothing at all."""
    cp = job / 'transcript' / 'cuts.json'
    if not cp.exists():
        return
    rev = hashlib.sha1(cp.read_bytes()).hexdigest()[:12]
    have = plan.get('cut_rev')
    if failed:
        print(f'cut_rev {rev} NOT stamped: a plan with FAILs is not the plan that ships')
    elif have == rev:
        print(f'cut_rev {rev} (already stamped, file untouched)')
    elif check:
        print(f'cut_rev {rev} would be stamped (plan carries {have or "none"}) — --check writes nothing')
    else:
        plan['cut_rev'] = rev
        path.write_text(json.dumps(plan, indent=1), encoding='utf-8')
        print(f'cut_rev {have or "none"} → {rev}, stamped into {path.name}')


REPO = Path(__file__).resolve().parents[4]
LAYOUT_PY = REPO / 'presets' / 'instagram' / 'talking-head-explainer' / 'layout.py'


class _Tee:
    """stdout that also keeps what was written: the layout report is printed as it runs and read back afterwards."""
    def __init__(self, out):
        self.out, self.buf = out, []

    def write(self, s):
        self.buf.append(s)
        return self.out.write(s)

    def flush(self):
        self.out.flush()

    def __getattr__(self, k):
        return getattr(self.out, k)


def layout_gate(job, variant=None):
    """The Talking Head Explainer's layout checks, run through layout.py's own report -> (exit code, what it printed)
    (0 ok, WARNs allowed · 1 a FAIL · 2 a missing input, named · 3 layout.py itself crashed, named)."""
    tag = f' --variant {variant}' if variant else ''
    print(f'\n── layout gate{tag}: {LAYOUT_PY.relative_to(REPO)} ──')
    tee, was = _Tee(sys.stdout), sys.stdout
    sys.stdout = tee
    try:
        spec = importlib.util.spec_from_file_location('th_layout', LAYOUT_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rc = mod.main([str(job)] + (['--variant', variant, '--check'] if variant else []))
    except Exception as e:                       # a corrupt face-frame.json, a bug: one named FAIL, never a traceback
        print(f'✗ layout.py crashed: {type(e).__name__}: {e}')
        rc = 3
    finally:
        sys.stdout = was
    print('──')
    return rc, ''.join(tee.buf)


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    job = Path(a[0]).resolve()
    check = '--check' in a           # read-only: validate and report, stamp nothing
    plan = json.load(open(job / 'graphics-plan.json', encoding="utf-8"))
    fps = None
    if '--fps' in a:
        n, _, d = a[a.index('--fps') + 1].partition('/'); fps = float(n) / float(d or 1)
    if fps is None and plan.get('fps'):
        # the plan names the SEQUENCE rate (lanes/premiere/place-graphics.py reads it the same way): a section
        # whose raw runs at another rate (a 30 fps screen recording on a 23.976 sequence) would otherwise snap
        # every tolerance below to the raw's grid
        n, _, d = str(plan['fps']).partition('/'); fps = float(n) / float(d or 1)
    if fps is None:
        raws = sorted(glob.glob(str(job / 'raw' / '*')))
        if raws:
            r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                                '-of', 'csv=p=0', raws[0]], capture_output=True, text=True).stdout.strip().split('\n')[0]
            n, _, d = r.strip(',').partition('/'); fps = float(n) / float(d or 1)
    fps = fps or 30000 / 1001
    F = 1.0 / fps
    # the SCENE and SPREAD rules are youtube/default rules (creative-moves.md): a short-form plan is not
    # held to them. Default to long-form when the plan states neither, so a long-form plan never loses them.
    _scope = f"{plan.get('format') or ''} {plan.get('preset') or ''}".lower()
    LONG = not any(k in _scope for k in ('short', 'tiktok', 'instagram', 'explainer'))
    beats = plan['beats']
    cells = [b for b in beats if b.get('graphic')]
    words = []
    tp = job / 'outputs' / f'{job.name}.transcript.json'
    if tp.exists():
        d = json.load(open(tp, encoding="utf-8")); words = [w for w in (d['words'] if isinstance(d, dict) else d) if w.get('type', 'word') == 'word']
    cuts, t = [], 0.0
    cp = job / 'transcript' / 'cuts.json'
    if cp.exists():
        segs = json.load(open(cp, encoding="utf-8"))['segments']
        if segs and all(isinstance(s.get('_timeline'), list) for s in segs):
            # an EDL read back from the timeline carries `_timeline` [start, end] per segment (sequence seconds): those ARE the V1 cuts;
            # the cumulative sum of source durations drifts off the sequence grid on a mixed-rate source (a 30 fps screen recording on 23.976,
            # 2026-09-14: every edge read 0.37 ms 'off the cut' while sitting on the frame Premiere placed)
            off = float(plan.get('timeline_offset') or 0.0)
            cuts = [float(s['_timeline'][1]) - off for s in segs]
        else:
            for s in segs:
                t += float(s['end']) - float(s['start']); cuts.append(t)
    fails, warns = [], []
    F_ = fails.append; W_ = warns.append
    # names the transcript corrections already capitalize (brands, people) are proper nouns here too
    proper = PROPER | {norm(w['text']) for w in words if w['text'][:1].isupper()}

    ids = [b['id'] for b in beats]
    for i in set(ids):
        if ids.count(i) > 1: F_(f'{i}: duplicate id')
    # a graphic split into part clips for BUILD reasons (graphics-build § split part clips) is ONE graphic:
    # each continuation carries "part_of": "<stem id>", and the cut / scene / readable / density maths below
    # measure the GROUP, so a split graphic is held to exactly the numbers an unsplit one is
    by_id = {c['id']: c for c in cells}
    parts = set()
    for c in cells:
        p = c.get('part_of')
        if p is None: continue
        stem = by_id.get(p)
        if stem is None or p == c['id']:
            F_(f"{c['id']}: part_of {p!r} names no other graphic cell in this plan")
        elif stem.get('kind') != c.get('kind'):
            F_(f"{c['id']}: part_of {p!r} is a {stem.get('kind')} cell: the parts of one graphic share its kind")
        elif stem.get('part_of'):
            F_(f"{c['id']}: part_of {p!r} is itself a part: every part names the STEM cell")
        else:
            parts.add(c['id'])
    groups = {}
    for c in cells:
        groups.setdefault(c['part_of'] if c['id'] in parts else c['id'], []).append(c)
    for g in groups.values():
        g.sort(key=lambda x: float(x.get('start') or 0))
    inner = set()   # a split graphic's INTERNAL seams: not outer boundaries, so the cut gate skips them
    for g in groups.values():
        for i, c in enumerate(g):
            if i: inner.add((c['id'], 'start'))
            if i < len(g) - 1: inner.add((c['id'], 'end'))
        for a1, b1 in zip(g, g[1:]):
            d = float(b1.get('start') or 0) - float(a1.get('end') or 0)
            if abs(d) > 0.5 * F:
                F_(f"{b1['id']}: part starts {d / F:+.2f} frames from the end of {a1['id']} ({float(a1.get('end') or 0):.5f}): "
                   f"the parts of one graphic butt-join (the shot underneath flashes for those frames)")
    TH = 'talking-head-explainer' in _scope
    # the Talking Head Explainer places every graphic through its layout map (layout.md § 12), so `region` (a long-form
    # slot) and `content` are not its fields: requiring them failed every plan written to the preset's own contract
    required = ('kind', 'start', 'end') if TH else ('kind', 'region', 'content', 'start', 'end')
    for c in cells:
        gid = c['id']
        for k in required:
            if k not in c: F_(f'{gid}: missing {k}')
        if LONG and c.get('kind') in FULL_KINDS and c.get('bg') not in ('dark', 'light'):
            F_(f'{gid}: full-screen without "bg": dark is the default CHOICE, write it — the locked render flags follow the field (bg-dark = STEP_FPS=12 + the glow pass; creative-moves.md move 2)')
        if 'start' in c and 'end' in c and float(c['end']) <= float(c['start']): F_(f'{gid}: end <= start')
        if c.get('region') in ('callout-L', 'callout-R'):
            hd = c.get('head')
            if not (isinstance(hd, dict) and 'left' in hd and 'right' in hd and 'frame' in hd):
                F_(f"{gid}: side callout without a measured head: run chin-line.py --edl over its window and record head {{left, right, frame}} (preset § SIDE CALLOUTS)")
            elif not (isinstance(hd['frame'], (list, tuple)) and len(hd['frame']) == 2
                      and all(isinstance(v, (int, float)) for v in hd['frame'])):
                # graphics-qa.py reads head.frame as [w, h]; a bare 1080 crashed its face check with a TypeError
                # instead of failing here (2026-09-27)
                F_(f"{gid}: head.frame must be chin-line.py's frame as [width, height] (e.g. [1920, 1080]), got {hd['frame']!r}")
        copy = c.get('copy') or ''
        # a declared "copy": "" is a graphic that shows no words (talking-head-explainer/layout.md § 12): only a missing
        # key is asked about, and a text animation, which IS its words
        if not copy and (c.get('copy') is None or c.get('kind') in TEXT_KINDS) \
                and c.get('kind') not in ('screen-rec', 'screenshot', 'b-roll', 'enacting-overlay', 'annotation', 'captions'):
            W_(f'{gid}: no copy on a {c.get("kind")} cell (fine only if the graphic has no words)')
        artifact = c.get('source_artifact')
        if artifact:
            source = (job / str(artifact)).resolve()
            if job not in source.parents:
                F_(f'{gid}: source_artifact {artifact!r} is outside the job folder (job-relative paths only)')
            elif not source.is_file():
                F_(f'{gid}: source_artifact file missing: {artifact}')
            elif copy.strip() != source.read_text(encoding='utf-8').strip():
                F_(f'{gid}: copy differs from the complete source_artifact (preserve punctuation and case)')
        else:
            if c.get('readable') and copy and not c.get('asset') and not c.get('capture'):
                F_(f'{gid}: readable copy with no source_artifact: a readable cell IS the written thing — name the '
                   f'job-relative file it is copied from and make copy that file in full')
            if '—' in copy:
                F_(f'{gid}: em dash in authored copy {copy!r}; verbatim artifacts need source_artifact')
        if c.get('kind') in TEXT_KINDS and c.get('entrance') in ('pop', 'punch'):
            F_(f"{gid}: entrance {c['entrance']!r} on a text animation: type never pops (animations.md § TEXT NEVER POPS); rise (default) or slam")
        kind = c.get('kind')
        # anchor: the first word of the copy is spoken at start + LEAD
        if kind in TEXT_KINDS and words and copy:
            cw = [norm(w) for w in re.sub(r'[*~]', '', copy).split() if norm(w)]
            if cw:
                at = [w for w in words if abs(w['start'] - LEAD - float(c['start'])) <= 0.15]
                near = [w for w in at if norm(w['text']) == cw[0]]
                # a contraction still ANCHORS the cell: the word is the same word, the copy wrote it short
                loose = [w for w in at if stem_word(norm(w['text'])) == stem_word(cw[0])]
                if not near and loose:
                    W_(f"{gid}: copy starts {cw[0]!r} but he says {norm(loose[0]['text'])!r} at {loose[0]['start']:.2f}: "
                       f"write the copy as spoken (the builder matches the transcript verbatim)")
                elif not near:
                    times = ', '.join(f"{w['start']:.2f}" for w in words
                                      if norm(w['text']) == cw[0] and abs(w['start'] - float(c['start'])) < 3.0)
                    spoken = ' '.join(w['text'] for w in words if abs(w['start'] - float(c['start'])) <= 0.5)
                    hint = f" ('{cw[0]}' is spoken at {times}; start = word − {LEAD})" if times else \
                           f" ('{cw[0]}' is not spoken within 3s of {float(c['start']):.2f})"
                    F_(f"{gid}: start {float(c['start']):.2f} does not anchor to the first word of its copy{hint}"
                       + (f'; there the transcript reads: …{spoken}…' if spoken else ''))
            # duration: a text animation is a few words in the low band; one over 8 s is an anchor that
            # matched the WRONG occurrence of its first word (g11 anchored to an 'ever' 36 s early, 2026-09-04)
            if float(c['end']) - float(c['start']) > 8.0:
                F_(f"{gid}: text animation spans {float(c['end']) - float(c['start']):.1f}s, over 8s; the start probably anchored to an earlier occurrence of {cw[0]!r}")
            # lowercase-casual register
            first = re.sub(r'[*~"\'(]', '', copy.split()[0]) if copy.split() else ''
            if first[:1].isupper() and first.lower() not in proper and not first.isupper():
                W_(f"{gid}: text animation starts with a capital ({first!r}), captions keep the lowercase-casual register unless it is a name")
        # cut: a full-screen edge within 8 frames of a V1 cut sits ON it (off by one flashes the
        # other shot); an edge far from every cut is a cut back mid-take, which is a choice
        if (kind in FULL_KINDS or c.get('bg') or c.get('broll_source')) and cuts:
            for edge in ('start', 'end'):
                if (gid, edge) in inner: continue   # an internal seam of a split graphic, not an outer boundary
                t_ = float(c[edge])
                nearest = min(cuts, key=lambda x: abs(x - t_))
                if 1e-4 < abs(nearest - t_) <= 8 * F:
                    F_(f"{gid}: full-screen {edge} {t_:.4f} is {(t_ - nearest) / F:+.2f} frames off the V1 cut at {nearest:.5f}, "
                       f"set {edge} = {nearest:.5f} exactly (off by a frame flashes the other shot)")
        # a full-screen's cut-IN leads a spoken word by a hair (~1-3 frames): one that leads nothing is
        # anchored to the wrong word (the your-job hook was first computed off "shot," instead of "one")
        if (kind in FULL_KINDS or c.get('bg')) and words:
            st = float(c['start'])
            lead = [w for w in words if 0 <= w['start'] - st <= 0.12]
            # the timeline's ORIGIN is an edit point like any other and is not in cuts.json: without this, the
            # opening graphic of every video FAILs by construction (a kinetic title at 0.000 cannot lead a
            # word it starts on top of), and the escape hatch would be spent on every job
            on_cut = st <= 1.5 * F or (cuts and min(abs(st - x) for x in cuts) <= 1.5 * F)
            # a warn, not a FAIL (2026-09-19): raising it fails 14 cells across three shipped, approved plans —
            # a cut-in landing between words is a choice often enough that it is the reviewer's call, not the
            # gate's. `"anchor": "none"` + the reason in content is how a plan states that choice.
            if not lead and not on_cut and c.get('anchor') != 'none':
                W_(f"{gid}: full-screen cut-in at {st:.3f} leads no spoken word within 120 ms and sits on no V1 cut; "
                   f'name the word it anchors to, or state "anchor": "none" in the cell and say in content why it lands there')
        # a full-screen is a SCENE: phases (≥ 2 visual beats) + visuals (≥ 1 that is not type) stated in the cell
        # (creative-moves.md move 2 § A FULL-SCREEN IS A SCENE, you 2026-09-10: "more moving parts, more visuals")
        if LONG and (kind in FULL_KINDS or c.get('bg')) and gid not in parts:   # once per graphic, on the stem cell
            ph = c.get('phases'); vs = c.get('visuals')
            if not (isinstance(ph, list) and len(ph) >= 2 and all(isinstance(x, dict) and 'at' in x and 'what' in x for x in ph)):
                F_(f'{gid}: a full-screen needs "phases": [{{at, what}}, …] with at least 2 visual beats (a scene arriving/leaving, a rack focus, a reveal): it is a SCENE, not a card (creative-moves.md move 2 § A FULL-SCREEN IS A SCENE)')
            if not (isinstance(vs, list) and len(vs) >= 1):
                F_(f'{gid}: a full-screen needs "visuals": [...] naming at least one element that is not type (a picture, artifact, prop, diagram, UI) (creative-moves.md move 2 § A FULL-SCREEN IS A SCENE)')
        # readable hold — the whole graphic's span, so a split graphic is measured across its parts
        if c.get('readable') and gid not in parts:
            g_ = groups[gid]
            hold = float(g_[-1]['end']) - float(g_[0]['start'])
            if TH:
                # the preset's own hold (graphics.md § 13): a claim, stat or reply the viewer reads holds about 2 s once
                # whole, and the cut never moves for a hold; the approved short's read captures ran 1.2-2.9 s. So a
                # warn to check the whole-content hold on the render, never the long-form 3.0 s FAIL
                if hold < TH_READ_HOLD:
                    W_(f"{gid}: readable graphic spans {hold:.2f}s: check on the render that its content holds whole about "
                       f"{TH_READ_HOLD:g} s (talking-head-explainer/graphics.md § 13; the cut never moves for a hold)")
            elif hold < 3.0:
                F_(f"{gid}: readable graphic holds {hold:.2f}s, needs ≥ 3.0s (2s complete-content hold + reveal), or less text")
        elif kind in ('quote', 'comment', 'screenshot') and 'readable' not in c:
            W_(f"{gid}: a {kind} cell with no \"readable\" flag, if the viewer is meant to read it, flag it and size the slot")
        # hero: a still of the creator inside a graphic is CAST (workflows/hero-frame.py), never grabbed at a word
        blob = ' '.join(str(c.get(k) or '') for k in ('asset', 'content', 'visuals', 'copy'))
        if re.search(r'plan-frames[/\\]|\bbeat-\d+\.jpg\b', blob):
            F_(f'{gid}: names a plan-frames file: those are planning evidence, never assets (a beat frame is grabbed on a word, a mid-word face); cast the still with `uv run workflows/hero-frame.py <job> --id {gid}` and record it as "hero_frame" (graphics-plan § THE HERO-FRAME GATE)')
        hero = c.get('hero_frame')
        wants = re.search(r'\b(real|actual)? ?(frame|still|freeze[- ]frame) of (this|the) (video|footage|shoot|edit)\b|\bframe grab\b|\bstill of (him|her|the creator|the speaker)\b', blob, re.I)
        if wants and hero is None:
            F_(f'{gid}: shows a real frame of the video ({wants.group(0)!r}) with no "hero_frame": cast it with `uv run workflows/hero-frame.py <job> --id {gid}` (sheet, pick by eye, --pick <t>) and record {{"t", "file"}} (graphics-plan § THE HERO-FRAME GATE)')
        if hero is not None:
            if not (isinstance(hero, dict) and isinstance(hero.get('t'), (int, float)) and hero.get('file')):
                F_(f'{gid}: "hero_frame" needs {{"t": <raw seconds>, "file": "assets/<id>-frame.jpg"}}, both written by hero-frame.py --pick')
            else:
                hp = (job / str(hero['file'])).resolve()
                pk = job / 'review' / 'hero-frames' / f'{gid}.pick.json'
                if job not in hp.parents: F_(f'{gid}: hero_frame.file {hero["file"]!r} is outside the job folder')
                elif not hp.exists(): F_(f'{gid}: hero_frame.file {hero["file"]!r} not found under the job folder')
                if not pk.exists():
                    F_(f'{gid}: no review/hero-frames/{gid}.pick.json: the still was not cast by `hero-frame.py --pick` (a hand ffmpeg -ss at a word is the mistake this gate exists for)')
                else:
                    try: pj = json.load(open(pk, encoding='utf-8'))
                    except Exception: pj = {}
                    if not pj.get('pass'): F_(f'{gid}: {pk.name} did not pass the expression thresholds')
                    if abs(float(pj.get('t', -1)) - float(hero['t'])) > 0.002: F_(f'{gid}: hero_frame.t {hero["t"]} != the cast pick {pj.get("t")} in {pk.name}')
                    if Path(str(pj.get('file', ''))).name != hp.name: F_(f'{gid}: hero_frame.file {hp.name!r} != the cast file {Path(str(pj.get("file", ""))).name!r} in {pk.name}')
        # capture: a screen-rec / screenshot cell names its file or says what the build records
        if kind in ('screen-rec', 'screenshot'):
            cap, asset = c.get('capture'), c.get('asset')
            if not asset and not cap:
                F_(f'{gid}: a {kind} cell needs "asset" (a file already in the job folder) or "capture" {{source, target, action, seconds | still}}: the build records it, it never guesses (graphics-plan § THE CAPTURE GATE)')
            if asset:
                ap = (job / str(asset)).resolve()
                if job not in ap.parents: F_(f'{gid}: asset {asset!r} is outside the job folder (job-relative paths only)')
                elif not ap.exists(): F_(f'{gid}: asset {asset!r} not found under the job folder: a capture lives at '
                                         f'assets/captures/{gid}.<ext> (the copy under hf-graphics/gfx/assets/ is the render base\'s, never the original)')
            # a capture is evidence only if it SHOWS the thing: a spinner, a skeleton, a blank page or a
            # half-loaded list is not it, and the take is redone, never cropped around (2026-09-19)
            # a warn, not a FAIL: the missing LINE is not itself a defect (five shipped, approved plans predate
            # the field), and a gate that fails approved work stops being read. The defect it guards against is
            # read off the FRAME, by the build and by edit-review class 1k.
            if (asset or cap) and not str(c.get('shows') or '').strip():
                W_(f'{gid}: a capture cell wants "shows": one line naming what must be visible in the frame for it to be '
                   f'evidence (the panel open with the row it is about in it, the command\'s output on screen); the build '
                   f'reads a frame against it (graphics-plan § THE CAPTURE GATE)')
            if cap is not None:
                if not isinstance(cap, dict): cap = {}
                if not cap.get('target'):
                    F_(f'{gid}: "capture" needs a target (an app name or a URL)')
                src = cap.get('source')
                if src not in ('url', 'app'):
                    F_(f'{gid}: "capture" needs "source": "url" (page-record.mjs, headless) or "app" (screen-record.sh / window-grab.sh): the build routes on it')
                elif src == 'url' and not re.match(r'https?://', str(cap.get('target') or '')):
                    F_(f'{gid}: a "url" capture needs an http(s) target, got {cap.get("target")!r}')
                if kind == 'screen-rec' and cap.get('still'):
                    F_(f'{gid}: "still" on a screen-rec cell: a still is a screenshot cell (kind "screenshot"), a recording needs "seconds"')
                if kind == 'screen-rec' and not _num(cap.get('seconds')) > 0:
                    F_(f'{gid}: a screen-rec capture needs "seconds" (a number > 0), how long the take runs')
                if not cap.get('action'):
                    W_(f'{gid}: capture has no "action": say what is on screen / what happens during the take, or the build guesses the state')
                # an annotation is REGISTERED on its target, so the target has to hold still: a circle over a
                # scrolling capture drifts off the thing it rings (g9 needed scroll compensation, then a widening)
                # read off `content` and the phases — what the cell SAYS it draws — never off `copy`, which
                # is the on-screen words: a card whose copy reads "the highlights" is not an annotation, and
                # this is a FAIL, so a word that only happens to be on screen must not reach it
                ann = ANNOTATION.search(' '.join([str(c.get('content') or '')] +
                                                 [str(p.get('what') or '') for p in c.get('phases') or [] if isinstance(p, dict)]))
                if ann and _num(cap.get('scroll')) > 0:
                    F_(f'{gid}: a {ann.group(0)!r} over a capture that scrolls {cap.get("scroll")}px: the marker drifts off its target. '
                       f'Hold the capture still (scroll 0) and measure the target rect (page-record.mjs --find … --rects), or drop the annotation')
        # fit: the two template caps the plan can be held to, so the BUILDER never has to pick an
        # interpretation and report it afterwards (default-overlay-style.md § THE SIX TEMPLATES / SIDE CALLOUTS)
        tpl = (c.get('template') or '').lower()
        if 'list' in tpl and copy:
            # rows are separated by `|` or by a newline (both are shipped); NEVER by `·`, which a shipped
            # eyebrow uses inside itself ("STEP 1 · THE SETUP") and which would read that card as five rows
            rows_ = [x for x in re.split(r'\s*\|\s*|\n+', copy) if x.strip()]
            if len(rows_) > LIST_ROWS + 1:
                # a warn: the cap is a template guideline and a shipped, approved card carries four rows. What a
                # fourth row really costs is measured on the RENDER (band, clearance, legibility), not here.
                W_(f'{gid}: list card with an eyebrow and {len(rows_) - 1} rows ({copy!r}): max {LIST_ROWS} rows '
                   f'(default-overlay-style.md § THE SIX TEMPLATES) — split it, cut a row, or use another template')
        if c.get('region') in ('callout-L', 'callout-R') and (c.get('asset') or c.get('capture') or c.get('hero_frame')):
            crop = c.get('crop') if isinstance(c.get('crop'), dict) else None
            cw_, ch_ = _num((crop or {}).get('w')), _num((crop or {}).get('h'))
            if not (cw_ > 0 and ch_ > 0):
                # warn: an unwritten crop is a decision left to the builder, not a defect (a shipped, approved
                # plan has one). A crop that IS written and does not fill the slot stays a FAIL: that is measured.
                W_(f'{gid}: a side callout carrying a capture/still wants "crop": {{"w", "h"}} — the framing is a plan '
                   f'decision, not the builder\'s; shape it to the slot (at most {CALLOUT_W}x{CALLOUT_H}, the '
                   f'width measured per window by chin-line.py --edl)')
            else:
                k_ = min(CALLOUT_W / cw_, CALLOUT_H / ch_)
                fillsq = (cw_ * k_) * (ch_ * k_) / (CALLOUT_W * CALLOUT_H)
                if fillsq < 0.5:
                    F_(f'{gid}: a {cw_:.0f}x{ch_:.0f} crop letterboxes into a {CALLOUT_W}x{CALLOUT_H} callout box, filling '
                       f'{100 * fillsq:.0f}% of it — the crop is the wrong SHAPE for a side slot at any measured width: '
                       f'reframe it to the slot\'s shape, or give the shot the full frame')
    # the caption layer (short-form, kind "captions") spans the whole cut on its own track: it is not an
    # event, so it stays out of the overlap, anti-stale and density maths below
    cells = [c for c in cells if c.get('kind') != 'captions']
    # one region, one graphic: the band IS one slot, so two cells that share a region may never overlap in
    # time (g24 and g25 both took the low band, the builder's `until` clamp hard-stopped g24 mid-shot and the
    # graphic was retired after a 4K render, 2026-09-19). Across regions an overlap is still only a choice to state.
    for i, a1 in enumerate(cells):
        for b1 in cells[i + 1:]:
            lo, hi = max(float(a1['start']), float(b1['start'])), min(float(a1['end']), float(b1['end']))
            # a butt-join is not an overlap: two cells meeting at a cut share its edge to a float's width (your-job-pa
            # g10 end 49.25754 / g10m start 49.2575, 0.04 ms, FAILed here and blocked the cut_rev stamp, 2026-09-23),
            # so an overlap counts only past half a frame of the plan's grid, the tolerance the part seams above use
            if hi - lo <= 0.5 * F: continue
            p = 2   # the window is printed at the first precision that shows its width, never as 'x → x'
            while p < 6 and f'{lo:.{p}f}' == f'{hi:.{p}f}': p += 1
            window = f'{lo:.{p}f} → {hi:.{p}f}'
            if a1.get('broll_source') or b1.get('broll_source'):
                F_(f"{a1['id']} and {b1['id']} overlap over {window}: nothing but the caption layer shares the screen with an "
                   "own B-roll cutaway (the placer lays the later-listed row on V4 over the earlier one; broll-own)")
                continue
            if a1.get('region') and a1.get('region') == b1.get('region'):
                F_(f"{a1['id']} and {b1['id']} both occupy {a1['region']} over {window}: one slot, one graphic — "
                   f"merge them or let one breathe (graphics-plan § Step 3)")
            elif a1.get('kind') not in TEXT_KINDS and b1.get('kind') not in TEXT_KINDS:
                W_(f"{a1['id']} and {b1['id']} overlap on the timeline ({window}): the second goes to V4; say so in content")
    # anti-stale: same template twice in a row (text animations exempt)
    # a continuation part MUST share its stem's template and bg, so the stem alone stands for the group here
    seq = [c for c in sorted(cells, key=lambda c: float(c['start'])) if c.get('kind') not in TEXT_KINDS and c['id'] not in parts]
    for a1, b1 in zip(seq, seq[1:]):
        # a punch-cut on the OTHER field is a different look (dark ≠ light: the other field reads as a different look), so the pair is (template, bg)
        if a1.get('template') and (a1.get('template'), a1.get('bg')) == (b1.get('template'), b1.get('bg')):
            W_(f"{b1['id']}: same template as the previous graphic {a1['id']} ({a1['template']}{' on ' + a1['bg'] if a1.get('bg') else ''}), the anti-stale law")
    # density block — a split graphic counts ONCE, over its whole span: its parts are a build mechanic
    ev = []
    for c in cells:
        if c['id'] in parts: continue
        g_ = [x for x in groups[c['id']] if x.get('kind') != 'captions']
        ev.append(dict(c, start=float(g_[0]['start']), end=float(g_[-1]['end'])) if len(g_) > 1 else c)
    dur = float(plan.get('duration') or max(float(c['end']) for c in ev))
    # every number below is measured over the GRAPHICS SCOPE: the stretches this plan may decorate, which is
    # the whole runtime unless the plan says otherwise
    scope = scope_ranges(plan, dur)
    sdur = sum(b - a for a, b in scope) or 1
    scoped = scope != [(0.0, float(dur))]
    if plan.get('graphics_scope') is not None and not scoped:
        W_('graphics_scope carries no machine-readable "ranges": the cadence below is measured over the whole '
           'runtime — write {"ranges": [[a, b], …], "why": "…"} and it follows the scope instead')
    n = len(ev); per_min = n / (sdur / 60)
    texts = sum(1 for c in ev if c.get('kind') in TEXT_KINDS)
    fulls = [c for c in ev if c.get('kind') in FULL_KINDS or c.get('bg')]
    full_s = sum(float(c['end']) - float(c['start']) for c in fulls)
    push = sum(1 for c in ev if c.get('push_in'))
    bare, bare_where = longest_gap(scope, [(float(c['start']), float(c['end']), str(c['id'])) for c in ev])
    print(f"density: {n} events / {sdur:.1f}s = {per_min:.1f}/min (11-13) · text animations {texts} ({texts / (sdur / 60):.1f}/min, 6-7) · "
          f"full-screens {len(fulls)} = {full_s:.1f}s = {100 * full_s / sdur:.1f}% (25% decorative guideline; demonstrations may exceed) · push-ins {push} ({push / (sdur / 60):.1f}/min, 2-3) · "
          f"longest bare {bare:.1f}s (≤6)" + (f" · measured over the graphics scope, {len(scope)} range(s) of the {dur:.1f}s runtime" if scoped else '')
          + ('' if LONG else ' · SHORT-FORM: the bracketed numbers are the long-form cadence, printed for reference and not gated here'))
    # the cadence brackets are creative-moves.md § THE DENSITY NUMBERS, a youtube/default rule: a short-form
    # plan has its own preset and is not held to them (a 143 s explainer with 9 graphics took three of these)
    if LONG and per_min < 10.5: W_(f'density {per_min:.1f}/min is under the look (11-13)')
    if LONG and bare > 6.0: W_(f'longest bare stretch {bare:.1f}s > 6s ({bare_where})')
    if LONG and 100 * full_s / sdur > 25: W_(f'full-screens are {100 * full_s / sdur:.1f}% of runtime (> 25% decorative guideline): review coverage; retain required prompt/capture demonstrations for their whole explanation and record the reason in content')
    # spread: never more than 40 s of runtime without a full-screen (creative-moves § THE DENSITY NUMBERS, SPREAD;
    # your-job shipped 3 in its first 41 s and none in the last 95, 2026-09-10)
    fs = sorted(fulls, key=lambda c: float(c['start'])) if LONG else []
    if fs:
        g, where = longest_gap(scope, [(float(c['start']), float(c['end']), str(c['id'])) for c in fs])
        if g > 40: W_(f'full-screens are not spread: {g:.0f}s without one ({where}); ≤ 40 s (creative-moves.md § THE DENSITY NUMBERS, SPREAD)')
        if len(fs) / (sdur / 60) < 2: W_(f'full-screens {len(fs) / (sdur / 60):.1f}/min under the look (2-3)')
    elif LONG:
        W_('no full-screen graphic at all (2-3/min, spread ≤ 40 s apart)')
    if TH:
        # the organic, then every second deliverable: layout.md § 7 holds on the variant too, and a variant's ask that
        # hops to W or T passed here while `layout.py --variant ad` failed it
        for variant in [None] + sorted(plan.get('variants') or {}):
            rc, said = layout_gate(job, variant)
            what = f"variants.{variant}" if variant else 'the layout map'
            if rc == 1:
                F_(f'layout.py{" --variant " + variant if variant else ""}: {what} fails its rules (the table above; '
                   'talking-head-explainer/layout.md § 13)')
            elif rc == 2:
                miss = next((l for l in said.splitlines() if 'missing input' in l), '')
                F_(f'layout.py: a missing input (named above) keeps the layout gate from running on {what}: supply it '
                   'and re-run' + (' (uv run workflows/face-frame.py projects/<job> --modes --collar --plan projects/<job>)'
                                   if 'face-frame' in miss else ''))
            elif rc == 3:
                F_(f'layout.py crashed on {what} (named above): fix the input it names and re-run')
    for w in warns: print(f'  warn {w}')
    for f in fails: print(f'  FAIL {f}')
    print(f"{len(fails)} FAIL · {len(warns)} warn · {n} graphics · fps {fps:.3f}")
    stamp_cut_rev(job, plan, job / 'graphics-plan.json', bool(fails), check)
    if fails: sys.exit(1)


if __name__ == '__main__':
    main()
