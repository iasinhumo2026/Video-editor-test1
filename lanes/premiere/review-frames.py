#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""review-frames.py: the step-5c evidence set, grabbed off the Premiere program monitor.

  uv run lanes/premiere/review-frames.py projects/<job> --round 1                      # every placed graphic
  uv run lanes/premiere/review-frames.py projects/<job> --round 2 --ids g10,g16 --rest-sheet
  uv run lanes/premiere/review-frames.py projects/<job> --round 3 --ids g16            # a targeted re-check
  uv run lanes/premiere/review-frames.py projects/<job> --round 1 --dry-run            # the plan, nothing written
  ... --out <dir>      # somewhere other than hf-graphics/review/round<N>/
  ... --fps 30000/1001 # only when no placed render is on disk to probe
  ... --since 1        # the baseline round to diff renders against (default: round<N-1> beside this one)
  ... --clear-previews # throw away the sequence's preview renders first (see below), OPT-IN
  ... --at g7:0.4,1.25  # hand-picked moments, comp-relative seconds (repeatable; grabbed whatever --ids reads)
  ... --max-per-graphic 24  # the per-graphic cap, trimming tween frames only (default 24)
  ... --from-export outputs/<job>-draft.mp4  # cut every frame from an exported draft: no Premiere at all
  ... --pace 150       # ms between bridge grabs (default 150, plus 2 s every 40 grabs)
  ... --i-know         # allow more than 200 bridge grabs in one run (the app must be idle)
  (uv resolves Pillow from the header: the contact sheets are the only dependency)

Writes <out>/<id>-f<frame>.png, <out>/sheets/<id>.png (one contact sheet per graphic, plus
sheets/_rest.png for the untouched graphics under --rest-sheet), <out>/INDEX.md, the list
the reviewers are handed (every frame on disk with its timeline second and what to look at), and
<out>/manifest.json, what those frames depict — the placed render behind each row at grab time.

Why (2026-09-07): the loop's evidence was hand-rolled inside the job folder every run, so it
carried that job's absolute path and a hardcoded 29.97, guessed one comp directory, handed the
bridge a relative out path (which the CEP panel resolves against Premiere's own cwd, writing
nowhere while reporting success) and exited 0 with frames missing. One tool, job as an argument.
`--clear-previews` clears the sequence's render cache first: a scripted MOVE leaves stale preview
frames that the Program monitor and exportFrame keep showing where no clip exists, and a phantom
graphic is a defect a reviewer cannot tell from a real one. It is OPT-IN because the clear takes the
creator's own hand-rendered previews (the green bar) with it over the whole sequence, and a grab
after a plain place/replace does not need it: pass it after anything that MOVED clips, and after
any frame that looks like a graphic no longer on the timeline. The run prints the reminder when it
is not passed.
Two ways a round can be clean against evidence that does not depict the edit, both now hard exits:
a render that moved since the baseline round is FORCED into full sampling however --ids reads (the
_rest sheet cannot swallow it), and frames older than the render they are labelled with are deleted
with a non-zero exit — a fix applied after the grab is the hole that shipped a defect (g35, 2026-09-18).

Sample set per placed graphic (clamped to the row, frame in .. frame out-1):
  every row      in+2 (the entrance has started), mid (the readable hold), out-2 (the exit)
  HAND comps     in+6 (a pop has settled by frame 4, a rise is still mid-travel at 6), the last
                 frame before and the first frame after every internal shot cut (a <video>/<img>, or
                 an element holding one, appearing or disappearing: its data-start window, or a
                 GSAP opacity/autoAlpha/visibility/display set on it; mid-shot sampling never lands
                 there, and a leaked old thread and a reply shot 0.2 s early both passed a round
                 unseen, 2026-09-21), +4 after every registry call and every tween parsed off the
                 comp, plus the call time +2 on a `pop` or `slam` (the overshoot peaks at +3, so the
                 +4 alone never shows it), and a 1.0 s sweep frame wherever the gap it falls in is over a second
  --at picks     the hand-picked moments, on any row
Tweens closer than 6 frames are one moment (earliest wins, a registry call absorbs the tweens
around it), and the tween frames are CAPPED per graphic (--max-per-graphic, default 24, spread
evenly by TIME over what the rest leaves): a call card's per-frame waveform sets were 440 of 734
grabs (2026-09-21). The run prints every graphic the cap trimmed. The entrance/exit, registry-call,
shot-cut and --at frames are never merged or dropped (a staggered pop's +2 is its own evidence), and
the sweep is never capped: it keeps every gap under a second, and on a capture comp it is the only
evidence for a change inside a shot (the cap once took all of it, a 41-frame hole, 2026-09-23). A cut
landing on a frame already kept adds its label to that frame's line in INDEX.md.
A hand comp is a row whose kind is not `text`: the text-animation comps are generated, their
motion is the builder's, and scanning them for tl.to times floods the plan with dead frames.

Bridge grabs are PACED (--pace, 150 ms apart, 2 s every 40) and a run over 200 of them refuses
without --i-know: a 426-grab burst beach-balled Premiere into a force quit while the creator worked
(2026-09-17). `--from-export <mp4>` cuts the same frames from an exported draft with ffmpeg instead
(the output -ss, after -i, is exact): no bridge, no active-project guard, safe while the creator is
in the app. The draft must run at the sequence rate, cover every planned frame and be newer than
placement.json and every planned graphic's placed render, or the run refuses.

Reads hf-graphics/placement.json (a bare list or {"rows": [...]}), the comps under
hf-graphics/*/compositions/<id>.html (the glob workflows/graphics-qa.py uses), and takes the fps
from the job, never a constant. Grabs run through lanes/premiere/premiere-bridge.mjs `frame`,
never fronting the app, after the active-project guard (lanes/premiere/job_guard.py) has confirmed
the active project is this job's. A frame that does not land is a non-zero exit: a partial evidence set
must never feed a review round. An existing png is skipped, so a run is restartable.
A SECTION sub-job (graphics-plan.json carries `timeline_offset`) is grabbed at row time + offset and
labelled in sequence seconds; the frame numbers in the file names stay in the section's own time base.
"""
import bisect, json, math, os, re, subprocess, sys, glob, time
from html.parser import HTMLParser
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from job_guard import require_job_project   # lanes/premiere/job_guard.py: frames come off the ACTIVE sequence
from pes import es                          # lanes/premiere/pes.py: the bridge's one output contract

BRIDGE = Path(__file__).resolve().parent / 'premiere-bridge.mjs'
NUDGE = 1e-4
CALL = re.compile(r"\b(riseIn|riseOut|pop|slam|drawOn|slideIn|slideOut|flash|exit|reveal|countUp)\(\s*'[^']*'\s*,\s*([0-9.]+)")
TL = re.compile(r"tl\.(?:to|set)\([^;]*?,\s*([0-9.]+)\s*\)\s*;")
# a visibility switch: tl.set(<sel>, {..}, T), tl.to(<sel>, {..}, T), tl.fromTo(<sel>, {..}, {..}, T)
SWITCH = re.compile(r"""tl\.(set|to|fromTo)\(\s*(['"])([^'"]*)\2\s*,\s*(\{[^{}]*\})\s*(?:,\s*(\{[^{}]*\})\s*)?,\s*([0-9.]+)\s*\)""")
VIS = re.compile(r"\b(?:opacity|autoAlpha|visibility|display)\s*:")
DURATION = re.compile(r"\bduration\s*:\s*([0-9.]+)")
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
MERGE = 6         # tweens closer than this many frames are one moment
MAX_PER_GRAPHIC = 24
PACE_MS = 150     # between bridge grabs
BREATHER = 40     # every this many bridge grabs, a 2 s pause for the app to drain
MAX_BRIDGE = 200  # bridge grabs in one run without --i-know
PRESEEK = 1.0     # --from-export: the fast keyframe seek lands this far before the exact one
TILE = 480        # contact sheet tile width, px
PAD = 6           # gutter around each tile, px
BAR = 22          # label bar above each tile, px
LABEL_FONT = Path(__file__).resolve().parents[2] / 'assets' / 'fonts' / 'Inter-Bold.otf'


def clear_previews(job):
    """`--clear-previews` only. A scripted move does not invalidate Premiere's preview cache, so
    the Program monitor AND exportFrame keep rendering an old graphic over a span where no clip
    exists (lanes/premiere/lab-notes.md § stale render cache) — a phantom no reviewer can tell from a
    real defect, and the creator caught the last one. Non-zero exit fails the run, the same rule this
    file already applies to a frame that did not land.
    NOT the default: it deletes the preview renders over the WHOLE sequence, and the creator renders
    those by hand (2026-09-19, twice lost). The caller asks for it after a move."""
    r = subprocess.run(['node', str(BRIDGE), 'clear-previews', json.dumps({'job': str(job)})],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit('clear-previews failed, so every frame below could be stale cache:\n'
                 + (r.stderr or r.stdout or '').strip()[-800:])
    print(r.stdout.strip(), flush=True)


def rows_of(job):
    d = json.load(open(job / 'hf-graphics' / 'placement.json', encoding="utf-8"))
    return d['rows'] if isinstance(d, dict) and 'rows' in d else d


def parse_fps(s):
    num, _, den = str(s).partition('/')
    return float(num) / float(den or 1)


def job_fps(job, rows, override):
    """The timeline rate, from the job: the placed renders carry it, so nothing here is a constant.
    The grabber this replaces held 1001/30000, which samples every frame of a 24p job at the wrong
    second and reads as a motion defect."""
    if override:
        return parse_fps(override)
    f = next((r['file'] for r in rows if r.get('file') and os.path.exists(r['file'])), None)
    if f:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                            'stream=r_frame_rate', '-of', 'json', f], capture_output=True, text=True)
        if not r.returncode:
            return parse_fps(json.loads(r.stdout)['streams'][0]['r_frame_rate'])
    cuts = job / 'transcript' / 'cuts.json'
    if cuts.exists():
        c = json.load(open(cuts, encoding="utf-8"))
        if isinstance(c, dict) and c.get('fps'):
            return parse_fps(c['fps'])
    sys.exit('no placed render to probe and no fps in transcript/cuts.json: pass --fps 30000/1001')


def comp_for(job, gid):
    """The comp, through the same wide glob graphics-qa.py uses: a job may split its comps across
    hf-graphics/gfx/ and hf-graphics/text-animation/."""
    hits = sorted(glob.glob(str(job / 'hf-graphics' / '*' / 'compositions' / f'{gid}.html')))
    return Path(hits[0]) if hits else None


class _Elements(HTMLParser):
    """Every element of a comp: tag, id, classes, its data-start/data-duration, and whether it IS or
    HOLDS a <video>/<img> (`media`)."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.els, self.open = [], []

    def handle_starttag(self, tag, attrs):
        a = {k: v or '' for k, v in attrs}
        el = {'tag': tag, 'id': a.get('id', ''), 'cls': set(a.get('class', '').split()),
              'start': a.get('data-start'), 'dur': a.get('data-duration'),
              'root': 'data-composition-id' in a, 'media': tag in ('video', 'img')}
        if el['media']:
            for p in self.open:
                p['media'] = True
        self.els.append(el)
        if tag not in VOID:
            self.open.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.open) - 1, -1, -1):
            if self.open[i]['tag'] == tag:
                del self.open[i:]
                break


def targets(els, sel):
    """The elements a GSAP selector string names, by the last compound of each comma part (tag, #id,
    .class; attribute and pseudo parts ignored). A selector that names none of those matches nothing."""
    hits = []
    for part in re.sub(r'\[[^\]]*\]', '', sel).split(','):
        last = re.sub(r'::?[\w-]+(\([^)]*\))?', '', (re.split(r'[\s>+~]+', part.strip()) or [''])[-1])
        tag = re.match(r'[a-zA-Z][\w-]*', last)
        ids, cls = re.findall(r'#([\w-]+)', last), set(re.findall(r'\.([\w-]+)', last))
        if not (tag or ids or cls):
            continue
        hits += [el for el in els if (not tag or el['tag'] == tag.group(0).lower())
                 and all(el['id'] == i for i in ids) and cls <= el['cls']]
    return hits


def shot_cuts(src, fps):
    """The comp's internal shot cuts, comp seconds: every moment a <video>/<img>, or an element holding
    one, appears or disappears. Two ways in:
      - a TIMED element (data-start: the runtime's visibility window [start, start + duration), with or
        without class="clip", which the runtime never reads), at both edges;
      - a GSAP visibility switch on one: tl.set(<sel>, {opacity|autoAlpha|visibility|display..}, T), or a
        to/fromTo of those under a frame long.
    The capture comps cut the second way: each shot sits in a wrapper whose opacity is SET at the cut,
    its clip pre-rolled 6 frames early under it and running a frame past the next shot's switch, and a
    still is a bare <img> with no timing at all, so sampling the clip edges alone left 10 of one job's 19
    cuts without their outgoing frame (2026-09-23)."""
    p = _Elements()
    p.feed(src)
    p.close()
    cuts = set()
    for el in p.els:
        if not el['media'] or el['root'] or el['start'] is None:
            continue
        try:
            st = float(el['start'])
        except ValueError:   # a clip-time reference: no number to sample at
            continue
        cuts.add(st)
        try:
            cuts.add(st + float(el['dur']))
        except (TypeError, ValueError):
            pass
    for m in SWITCH.finditer(src):
        how, sel, a, b = m.group(1), m.group(3), m.group(4), m.group(5)
        if (how == 'fromTo') != (b is not None):
            continue
        end = b if how == 'fromTo' else a
        if not VIS.search(end):
            continue
        if how != 'set':
            d = DURATION.search(end)
            try:
                if not d or float(d.group(1)) >= 1.0 / fps:   # a fade, not a cut
                    continue
            except ValueError:
                continue
        try:
            t = float(m.group(6))
        except ValueError:
            continue
        if any(el['media'] for el in targets(p.els, sel)):
            cuts.add(t)
    return sorted(cuts)


def straddle(x):
    """[(render frame, label)] either side of a switch at comp frame position x (its time x fps). The
    render's frame k shows comp time k/fps and a switch shows from the first frame at or after it, so the
    last frame before it is ceil(x)-1 and the first after it ceil(x). A switch within a hundredth of a
    frame of the grid gets both neighbours and its own frame: a 4-decimal time and the renderer's seek
    can put it either side."""
    n = round(x)
    if abs(x - n) < 0.01:
        return [(n - 1, 'cut-1: the last frame before'), (n, 'cut: the frame on'), (n + 1, 'cut+1: the first frame after')]
    k = math.ceil(x)
    return [(k - 1, 'cut-1: the last frame before'), (k, 'cut+1: the first frame after')]


def merge(events, anchors=()):
    """[(frame, name, t)] with every event closer than MERGE frames to one already kept dropped:
    a per-frame waveform `tl.set` is one moment, not a grab per frame. Earliest wins; `anchors`
    (the registry-call frames) absorb the tweens around them. Only tweens go through here: every
    registry call keeps its own frames (a staggered pop's +2 overshoot is its evidence)."""
    kept, frames = [], list(anchors)
    for ev in sorted(events):
        if all(abs(ev[0] - k) >= MERGE for k in frames):
            kept.append(ev); frames.append(ev[0])
    return kept


def spread(frames, k):
    """k of the sorted frames, evenly across their TIME span, first and last kept: each of k targets
    evenly spaced from the first frame to the last takes the nearest frame not yet taken (the earlier
    on a tie). By index, a dense burst of tweens took the budget and a quiet stretch went unsampled."""
    if k >= len(frames):
        return list(frames)
    if k <= 0:
        return []
    lo, hi = frames[0], frames[-1]
    free, out = list(frames), []
    for i in range(k):
        t = (lo + hi) / 2 if k == 1 else lo + (hi - lo) * i / (k - 1)
        f = min(free, key=lambda x: (abs(x - t), x))
        free.remove(f); out.append(f)
    return sorted(out)


def fill(planned, grid, step):
    """The grid frames (the 1 s sweep, `step` frames apart) worth grabbing beside the planned ones:
    walking the grid in time order, a sweep frame is kept only when the gap it falls in is still wider
    than a second, so no gap ends up over one and a gap already under a second costs nothing (a sweep
    frame beside a nearer one took the tween budget from 15 to 4 on a 17 s flood). The sweep is never
    capped: on a capture comp it is the only evidence for a change inside a shot the source does not
    declare (the cap once took all of it, a 41-frame hole)."""
    have, add = sorted(planned), []
    for g in sorted(grid):
        if g in have:
            continue
        i = bisect.bisect(have, g)
        if i == 0 or i == len(have) or have[i] - have[i - 1] > math.ceil(step):   # 24 frames IS a second at 23.976
            bisect.insort(have, g); add.append(g)
    return add


def plan_rows(job, rows, fps, ids, rest_sheet, at=None, cap=MAX_PER_GRAPHIC, capped=None):
    """[(id, frame, why)], in row order. `ids` limits full sampling; the rest get their mid frame
    only when --rest-sheet asked for it. `at` = {id: [comp seconds]} (--at), grabbed on any row.
    `cap` bounds the frames per graphic by trimming tweens (the sweep, calls and cuts are never
    trimmed, so a graphic can exceed it); `capped`, when a dict, collects
    {id: (planned, kept)} for every graphic the cap trimmed."""
    def fr(t): return int(round(t * fps))
    at = at or {}
    out = []
    for r in rows:
        gid, s, e = r['id'], float(r['start']), float(r['end'])
        lo, hi = fr(s), fr(e) - 1
        # str() on both sides: --ids and the forced set are text, while a plan may carry a numeric id
        # (the same mismatch write_index already guards) — and a force that silently matches nothing
        # is the round-2 hole reopened, this time announced as fixed on stderr.
        full = not ids or str(gid) in ids
        picks = at.get(str(gid), [])
        if not full and not rest_sheet and not picks:
            continue
        keep, calls, pool, grid = {}, {}, {}, set()   # keep, calls, the sweep grid: never capped; pool: the tweens
        if full or rest_sheet:
            keep[fr((s + e) / 2)] = 'mid: the readable hold'
        if full:
            keep[fr(s) + 2] = 'in+2: the entrance has started'
            keep[fr(e) - 2] = 'out-2: the exit, and the last frame is a hard kill'
            comp = comp_for(job, gid) if r.get('kind') != 'text' else None
            if comp:
                src = comp.read_text(encoding='utf-8', errors='replace')
                keep.setdefault(fr(s) + 6, 'in+6: a pop has settled by frame 4, a rise is mid-travel at 6')
                for c in shot_cuts(src, fps):
                    # the comp's own edges (a switch on its first frame, or on or after the row's end):
                    # in+2 and out-2 hold those
                    if c * fps <= 0.01 or c * fps >= fr(e) - fr(s) - 0.01:
                        continue
                    # the placed render's frame k is timeline frame fr(s) + k
                    for k, what in straddle(c * fps):
                        # a cut on a frame already kept (mid, in+6) adds its label: INDEX.md names the cut
                        f, w = fr(s) + k, f'{what} the shot cut at t={c:.4f}s'
                        keep[f] = f'{keep[f]} · {w}' if f in keep else w
                cf = []
                for m in CALL.finditer(src):
                    name, t = m.group(1), float(m.group(2))
                    cf.append(fr(s + t))
                    # the +2 twin is the pop/slam overshoot only: it peaks at +3 and is settled by +4
                    for off in ((2, 4) if name in ('pop', 'slam') else (4,)):
                        calls.setdefault(fr(s + t) + off, f'{off} frames into {name}() at t={t:.2f}s')
                for f, _, t in merge([(fr(s + float(m.group(1))), 'tween', float(m.group(1))) for m in TL.finditer(src)],
                                     cf):
                    pool.setdefault(f + 4, f'4 frames into a tween at t={t:.2f}s')
                t = s + 1.0
                while t < e - 0.1:
                    grid.add(fr(t)); t += 1.0
        for t in picks:
            if not lo <= fr(s + t) <= hi:
                sys.exit(f'--at {gid}:{t:g} is outside the graphic: its comp runs 0 to {e - s:.3f}s')
            keep.setdefault(fr(s + t), f'hand-picked: t={t:.2f}s into the comp')
        keep = {f: w for f, w in keep.items() if lo <= f <= hi}
        calls = {f: w for f, w in calls.items() if lo <= f <= hi and f not in keep}
        pool = {f: w for f, w in pool.items() if lo <= f <= hi and f not in keep and f not in calls}
        grid = {f for f in grid if lo <= f <= hi}
        # the registry calls spend the budget first and are never trimmed: each is an authored entrance
        # with its own evidence rule (a pop's +2 overshoot), and every flood measured was tweens. The
        # sweep fills every gap over a second whatever the cap; the tweens take what the budget leaves,
        # as many as fit once the sweep they leave behind is counted.
        def sample(k):
            take = spread(sorted(pool), k)
            return take, fill([*keep, *calls, *take], grid, fps)
        k = max(0, min(len(pool), cap - len(keep) - len(calls)))
        take, sweep = sample(k)
        while k > 0 and len(keep) + len(calls) + len(take) + len(sweep) > cap:
            k -= 1
            take, sweep = sample(k)
        if capped is not None and len(take) < len(pool):
            capped[str(gid)] = (len(keep) + len(calls) + len(pool) + len(sample(len(pool))[1]),
                                len(keep) + len(calls) + len(take) + len(sweep))
        why = dict(keep)
        why.update(calls)
        why.update({f: pool[f] for f in take})
        why.update({f: 'sweep' for f in sweep})
        for f in sorted(why):
            out.append((gid, f, why[f]))
    return out


def section_offset(job):
    """A SECTION sub-job's graphics-plan.json carries `timeline_offset`: its rows sit in the section's own
    time base, so the offset is added at the bridge boundary only (the grab time), the way place-graphics.py
    adds it. 2026-09-14: the first section round sampled the sequence at section time and handed the
    reviewers 58 frames of the wrong 40 s of footage, labelled as the graphics."""
    p = job / 'graphics-plan.json'
    if p.exists():
        try:
            return float(json.load(open(p, encoding="utf-8")).get('timeline_offset') or 0.0)
        except Exception:
            pass
    return 0.0


def manifest_of(rows):
    """{id: {file, mtime, size}} — what the frames in this round DEPICT, recorded at grab time.
    The round's own record, so the next round can measure what changed instead of trusting a
    hand-typed --ids."""
    m = {}
    for r in rows:
        f = r.get('file')
        try:
            st = os.stat(f)
        except (OSError, TypeError, ValueError):
            continue
        m[str(r['id'])] = {'file': os.path.basename(f), 'mtime': st.st_mtime, 'size': st.st_size}
    return m


def baseline_dir(out_dir, since, rnd):
    """The previous round's dir: --since takes a round number or a path, else round<N-1> beside this
    one. Returns None when there is nothing to diff against (round 1, or a hand --out)."""
    if since:
        p = since if os.path.sep in str(since) else os.path.join(os.path.dirname(out_dir), f'round{since}')
        return p if os.path.isdir(p) else None
    try:
        prev = int(rnd) - 1
    except (TypeError, ValueError):
        return None
    p = os.path.join(os.path.dirname(out_dir), f'round{prev}')
    return p if prev >= 1 and os.path.isdir(p) else None


def changed_since(rows, prev_dir):
    """The ids whose PLACED RENDER moved since the baseline round — "changed" as a measured fact.
    Round 2 sampled 37 graphics with one mid-frame tile each because they were believed unchanged;
    one of them had been re-rendered by a round-1 fix, so the defect that fix introduced was never
    looked at and the round was declared clean (g35, 2026-09-18). A missing manifest (a round grabbed
    before manifests existed) falls back to the newest frame on disk for that id."""
    try:
        prev = json.load(open(os.path.join(prev_dir, 'manifest.json'), encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    forced = set()
    for r in rows:
        gid, f = str(r['id']), r.get('file')
        if not f or not os.path.exists(f):
            continue
        rec = prev.get(gid)
        if rec is None:
            pngs = glob.glob(os.path.join(prev_dir, f'{gid}-f*.png'))
            newest = max((os.path.getmtime(p) for p in pngs), default=None)
            # No record AND no frame in the baseline round: the graphic did not exist last round (a
            # fix that added a cell). "Unchanged" cannot be said of evidence that was never grabbed,
            # so it is sampled in full rather than handed to the _rest sheet as one mid tile.
            if newest is None or os.path.getmtime(f) > newest:
                forced.add(gid)
        elif rec.get('file') != os.path.basename(f) or os.path.getmtime(f) > rec.get('mtime', 0):
            forced.add(gid)
    return forced


def stale_ids(rows, out_dir, have):
    """The frames a graphic's placed render is NEWER than: evidence that no longer depicts the render
    it is labelled with. The other half of the g35 hole — there the fix landed AFTER the grab, and the
    run still exited 0.
    Checked PER FRAME, never against the id's newest one: a round dir mixes grabs from several runs
    (an existing png is skipped, and --since forces a changed id into full sampling beside the single
    mid frame the _rest sheet left there), so one fresh grab would otherwise vouch for a stale
    neighbour and put the pre-fix render straight into that id's contact sheet."""
    stale = []
    for r in rows:
        gid, f = str(r['id']), r.get('file')
        if gid not in have or not f or not os.path.exists(f):
            continue
        rendered = os.path.getmtime(f)
        old = [p for p in (os.path.join(out_dir, f'{gid}-f{x}.png') for x in have[gid])
               if os.path.exists(p) and os.path.getmtime(p) < rendered]
        if old:
            stale.append((gid, old))
    return stale


def grab(gid, f, fps, outp, off=0.0):
    """One program-monitor frame. The out path is ABSOLUTE because the ExtendScript runs inside
    Premiere, whose cwd is its own app folder: a relative path writes nowhere, silently.
    `off` is the section's timeline_offset (sequence time = row time + off)."""
    subprocess.run(['node', str(BRIDGE), 'frame',
                    json.dumps({'time': round(f / fps + off + NUDGE, 5), 'out': str(outp)})],
                   capture_output=True, text=True)


def seq_frame(f, fps, off=0.0):
    """Row frame f as a frame of the SEQUENCE: the one the program monitor shows at grab()'s time."""
    return int((f / fps + off + NUDGE) * fps)


def cut_from_export(mp4, f, fps, outp, off=0.0):
    """--from-export: the frame grab() would take, cut from the draft. ffmpeg's -ss keeps the first
    frame AT OR AFTER its time, so the bridge's +NUDGE would cut the NEXT frame: the seek is half a
    frame before it instead. The -ss before -i is a fast keyframe seek PRESEEK short of it; the -ss
    after -i decodes the rest and is exact."""
    t = max(0.0, (seq_frame(f, fps, off) - 0.5) / fps)
    pre = max(0.0, t - PRESEEK)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{pre:.6f}', '-i', str(mp4), '-ss', f'{t - pre:.6f}',
                    '-frames:v', '1', '-an', str(outp) + '.png'], capture_output=True, text=True)


def export_check(job, mp4, fps, plan, rows, off=0.0):
    """--from-export refuses a draft that does not hold this sequence's frames: another rate (its frame
    N is not sequence frame N), too short for the planned frames, older than placement.json (the rows
    it would be sampled at may have moved since), or older than a planned graphic's placed render (its
    frames would show the pre-fix graphic under a manifest that names the fixed one: the g35 hole
    again). Returns the draft's mtime."""
    if not os.path.isfile(mp4):
        sys.exit(f'--from-export: no such file: {mp4}')
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate,duration',
                        '-show_entries', 'format=duration', '-of', 'json', str(mp4)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        st = d['streams'][0]
        rate = parse_fps(st['r_frame_rate'])
        dur = float(st.get('duration') or d['format']['duration'])
    except (ValueError, KeyError, IndexError, TypeError, ZeroDivisionError):
        sys.exit(f'--from-export: ffprobe found no video stream in {mp4}')
    if abs(rate - fps) > 1e-3:
        sys.exit(f'--from-export: the draft runs at {rate:.5f} fps and the sequence at {fps:.5f}, so its frame N is '
                 'not the sequence\'s frame N: export at the sequence rate')
    last = max((seq_frame(f, fps, off) for _, f, _ in plan), default=-1)
    if last + 0.5 > dur * fps:
        sys.exit(f'--from-export: the draft ends at {dur:.3f}s and the plan reaches {last / fps:.3f}s: export the whole '
                 'sequence from its start')
    if os.path.getmtime(job / 'hf-graphics' / 'placement.json') > os.path.getmtime(mp4):
        sys.exit('--from-export: placement.json was written after the draft was exported, so the rows its frames '
                 'are cut at may have moved: re-export first')
    planned ={str(g) for g, _, _ in plan}
    newer = [str(x['id']) for x in rows if str(x['id']) in planned and x.get('file') and os.path.exists(x['file'])
             and os.path.getmtime(x['file']) > os.path.getmtime(mp4)]
    if newer:
        sys.exit(f'--from-export: {",".join(newer)} re-rendered after the draft was exported, so its frames show the '
                 'old render: re-export first')
    return os.path.getmtime(mp4)


def parse_at(vals):
    """--at <id>:<t,t,...> (repeatable) -> {id: [comp seconds]}."""
    at = {}
    for v in vals:
        gid, _, ts = v.rpartition(':')
        try:
            times = [float(x) for x in ts.split(',') if x.strip()]
        except ValueError:
            times = []
        if not gid or not times:
            sys.exit(f'--at {v}: expected <id>:<seconds>[,<seconds>...], comp-relative')
        at.setdefault(gid, []).extend(times)
    return at


def on_disk(out_dir):
    """{id: [frames]} from the round dir, not from this invocation: a targeted second run extends
    the index instead of replacing it."""
    have = {}
    for p in sorted(glob.glob(os.path.join(out_dir, '*.png'))):
        m = re.match(r'^(.+)-f(\d+)\.png$', os.path.basename(p))
        if m:
            have.setdefault(m.group(1), []).append(int(m.group(2)))
    for v in have.values():
        v.sort()
    return have


def sheet(tiles, out_png):
    """A labelled contact sheet: tiles = [(label, png path)], 3 per row, each TILE px wide under a
    BAR px caption. Pillow, not ImageMagick `montage`: montage is absent on a stock Windows Git Bash
    box, so a client would get frames and no sheets while the pack sends reviewers to sheets/<id>.png."""
    ims = []
    for label, p in tiles:
        try:
            im = Image.open(p).convert('RGB')
        except Exception:
            continue
        ims.append((label, im.resize((TILE, max(1, round(im.height * TILE / im.width))))))
    if not ims:
        return False
    try:
        font = ImageFont.truetype(str(LABEL_FONT), 15)
    except Exception:
        font = ImageFont.load_default()
    cell = max(im.height for _, im in ims) + BAR
    cols, rows_n = min(3, len(ims)), (len(ims) + 2) // 3
    canvas = Image.new('RGB', (cols * (TILE + PAD) + PAD, rows_n * (cell + PAD) + PAD), (21, 21, 21))
    d = ImageDraw.Draw(canvas)
    for i, (label, im) in enumerate(ims):
        x, y = PAD + (i % 3) * (TILE + PAD), PAD + (i // 3) * (cell + PAD)
        d.text((x + 2, y + 3), label, font=font, fill=(255, 255, 255))
        canvas.paste(im, (x, y + BAR))
    canvas.save(out_png)
    return True


def write_index(out_dir, rows, fps, why_all, off=0.0, source=None):
    """The reviewers' list, rebuilt from what is ON DISK in the round dir (frames and sheets alike),
    so a targeted second run extends the index instead of shrinking it to its own ids. `source` is
    the draft a --from-export run cut its frames from."""
    have = on_disk(out_dir)
    # ids as strings on both sides: the frame files carry the id as text, while a plan may write a
    # numeric id (cell 1 on your-job read as "? · 0.000s to 0.000s", 2026-09-08)
    row_ids = {str(r['id']) for r in rows}
    order = [str(r['id']) for r in rows if str(r['id']) in have] + [g for g in have if g not in row_ids]
    span = {str(r['id']): (float(r['start']), float(r['end']), r.get('kind', '?')) for r in rows}
    L = [f'# Evidence frames: {os.path.basename(out_dir)}', '',
         f'fps {fps:.5f} · frame N is at N/{fps:.5f} = {1.0 / fps:.6f} x N seconds' + (f' + the section offset {off:.6f} s' if off else '') + ' on the timeline.',
         (f'Each png cut by this run is that frame of the exported draft `{os.path.basename(source)}`, every video track composited.'
          if source else 'Each png is the program monitor at that frame, every video track composited.'), '']
    for gid in order:
        s, e, kind = span.get(gid, (0.0, 0.0, '?'))
        head = f'## {gid} · {kind} · {s:.3f}s to {e:.3f}s'
        for rel in (f'sheets/{gid}.png', 'sheets/_rest.png'):
            if os.path.exists(os.path.join(out_dir, rel)):
                head += f' · sheet {rel}'; break
        L += [head]
        for f in have[gid]:
            L.append(f'- `{gid}-f{f}.png` t={f / fps + off:.3f}s · {why_all.get((gid, f), "extra grab")}')
        L.append('')
    open(os.path.join(out_dir, 'INDEX.md'), 'w', encoding='utf-8').write('\n'.join(L))


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith('-'):
        sys.exit(__doc__)

    def opt(name, default=None):
        return a[a.index(name) + 1] if name in a else default

    job = Path(a[0]).resolve()
    rnd = opt('--round', '1')
    ids = {x for x in (opt('--ids') or '').split(',') if x}
    rest_sheet = '--rest-sheet' in a
    dry = '--dry-run' in a
    at = parse_at([a[i + 1] for i, x in enumerate(a[:-1]) if x == '--at'])
    cap = int(opt('--max-per-graphic', MAX_PER_GRAPHIC))
    pace = float(opt('--pace', PACE_MS)) / 1000.0
    export = opt('--from-export')
    export = os.path.abspath(export) if export else None
    rows = rows_of(job)
    unknown = sorted(set(at) - {str(r['id']) for r in rows})
    if unknown:
        sys.exit(f'--at names no placed graphic: {",".join(unknown)}')
    fps = job_fps(job, rows, opt('--fps'))
    off = section_offset(job)   # a section sub-job: rows are section time, the sequence is off later
    out_dir = os.path.abspath(opt('--out') or str(job / 'hf-graphics' / 'review' / f'round{rnd}'))

    # "Changed" is COMPUTED, never remembered: a graphic whose placed render moved since the baseline
    # round is forced into full sampling whatever --ids says, or the _rest sheet swallows it.
    prev_dir = baseline_dir(out_dir, opt('--since'), rnd)
    if prev_dir and ids:
        forced = changed_since(rows, prev_dir) - ids
        if forced:
            print(f'forced full sampling (render changed since {os.path.basename(prev_dir)}): '
                  + ','.join(sorted(forced)), file=sys.stderr)
        ids |= forced
    elif ids and not dry:
        print('no baseline round to diff against: --ids is taken as given', file=sys.stderr)

    capped = {}
    plan = plan_rows(job, rows, fps, ids, rest_sheet, at, cap, capped)
    if capped:
        print(f'capped at {cap} frames per graphic (--max-per-graphic N to change; the entrance/exit, registry-call, '
              'shot-cut and --at frames are never dropped): ' + ', '.join(f'{g} {n}->{k}' for g, (n, k) in capped.items()),
              file=sys.stderr)
    export_mtime = export_check(job, export, fps, plan, rows, off) if export else None

    def todo(png):
        # a frame older than the draft it would be cut from does not depict that draft
        return not os.path.exists(png) or (export_mtime is not None and os.path.getmtime(png) < export_mtime)
    grabs = sum(todo(os.path.join(out_dir, f'{gid}-f{f}.png')) for gid, f, _ in plan)
    burst = (f'{grabs} bridge grabs planned, over {MAX_BRIDGE}: a 426-grab burst beach-balled Premiere into a '
             'force quit while the creator worked (2026-09-17). Cut them from an export instead (--from-export '
             '<draft.mp4>), narrow the round (--ids, --max-per-graphic), or pass --i-know with the app idle')
    if dry:
        print(f'{len(plan)} frames planned at {fps:.5f} fps -> {out_dir}', file=sys.stderr)
        if not export and grabs > MAX_BRIDGE and '--i-know' not in a:
            print(f'a live run refuses: {burst}', file=sys.stderr)
        for gid, f, _ in plan:
            print(gid, f, os.path.join(out_dir, f'{gid}-f{f}.png'))
        return 0

    if export:   # no bridge, no active project: the draft is named, and checked above
        if '--clear-previews' in a:
            print('--clear-previews ignored: an export run never reads the program monitor', file=sys.stderr)
    else:
        if grabs > MAX_BRIDGE and '--i-know' not in a:
            sys.exit(burst)
        require_job_project(es, job)   # another open project's frames would pass as this job's evidence
        if '--clear-previews' in a:    # a stale cache frame is a defect the reviewers cannot see is fake
            clear_previews(job)
        else:
            print('previews kept (the creator renders them by hand): pass --clear-previews after anything '
                  'that MOVED clips, or a stale cache frame ships as a phantom graphic', file=sys.stderr)
    os.makedirs(os.path.join(out_dir, 'sheets'), exist_ok=True)
    print(f'{len(plan)} frames at {fps:.5f} fps -> {out_dir}'
          + (f' · cut from {export}' if export else f' · bridge grabs {round(pace * 1000)} ms apart, 2 s every {BREATHER}'),
          flush=True)
    missing, got = [], 0
    for gid, f, _ in plan:
        png = os.path.join(out_dir, f'{gid}-f{f}.png')
        if not todo(png):
            continue
        if export:
            if os.path.exists(png):   # older than the draft: a failed cut must not leave it passing as new
                os.remove(png)
            cut_from_export(export, f, fps, os.path.join(out_dir, f'{gid}-f{f}'), off)
        else:
            n = got + len(missing)
            if n:   # paced: back-to-back exportFrame calls beach-balled the app the creator was working in
                time.sleep(pace + (2.0 if n % BREATHER == 0 else 0.0))
            grab(gid, f, fps, os.path.join(out_dir, f'{gid}-f{f}'), off)
        if os.path.exists(png):
            got += 1
        else:
            print(f'MISSING {gid} {f}', flush=True); missing.append((gid, f))
    print(f'{got} {"cut" if export else "grabbed"} · {len(plan) - got - len(missing)} already on disk · '
          f'{len(missing)} missing', flush=True)

    # Evidence older than the render it depicts, checked BEFORE anything is sheeted or indexed: an
    # existing png is skipped, so a fix applied after the grab sits in the round dir looking current.
    # The stale frames are removed, which makes re-running this command the way to clear it.
    stale = stale_ids(rows, out_dir, on_disk(out_dir))
    if stale:
        for _, pngs in stale:
            for p in pngs:
                try:
                    os.remove(p)
                except OSError:
                    pass
        sys.exit(f'{len(stale)} graphic(s) re-rendered after their frames were grabbed: '
                 + ','.join(g for g, _ in stale) + ' — those frames are deleted, re-run to re-grab '
                 'them before this round is reviewed')

    why_all = {(g, f): w for g, f, w in plan_rows(job, rows, fps, set(), True, at, cap)}
    for g, f, w in plan:
        why_all[(g, f)] = w
    have, built = on_disk(out_dir), 0
    full = [str(r['id']) for r in rows if (not ids or str(r['id']) in ids or str(r['id']) in at) and str(r['id']) in have]
    for gid in full:
        tiles = [(f'{gid}-f{f}  t={f / fps + off:.2f}s', os.path.join(out_dir, f'{gid}-f{f}.png')) for f in have[gid]]
        built += sheet(tiles, os.path.join(out_dir, 'sheets', f'{gid}.png'))
    rest = [str(r['id']) for r in rows if str(r['id']) not in full and str(r['id']) in have]
    if rest_sheet and rest:
        mid = {g: have[g][len(have[g]) // 2] for g in rest}
        tiles = [(f'{g}-f{mid[g]}  t={mid[g] / fps + off:.2f}s', os.path.join(out_dir, f'{g}-f{mid[g]}.png')) for g in rest]
        built += sheet(tiles, os.path.join(out_dir, 'sheets', '_rest.png'))
    print(f'{built} contact sheet(s) -> {os.path.join(out_dir, "sheets")}')
    write_index(out_dir, rows, fps, why_all, off, export)
    json.dump(manifest_of(rows), open(os.path.join(out_dir, 'manifest.json'), 'w', encoding="utf-8"), indent=1)
    print(f'INDEX.md -> {os.path.join(out_dir, "INDEX.md")}')
    if missing:
        sys.exit(f'{len(missing)} frame(s) did not land: a partial evidence set cannot feed a review round')
    return 0


if __name__ == '__main__':
    sys.exit(main())
