#!/usr/bin/env python3
"""placement.py: the lane-neutral half of step-5 placement: hf-graphics/placement.json derived from the plan + renders.

  uv run workflows/placement.py projects/<job> [--variant NAME]            # derive the rows, print what would change
  uv run workflows/placement.py projects/<job> [--variant NAME] --write    # save them AND sync the plan's frame-snap roundings

Every lane places graphics from the same rows: Premiere's lanes/premiere/place-graphics.py imports this module (its
--plan is this derivation), the Final Cut replay lays placement.json as connected clips, and the Resolve and CapCut
lanes read the same rows. Nothing here touches an editing app: stdlib + ffprobe only.

Rows: {"id", "file", "start", "end", "kind": "text"|"full"|"overlay"|"captions", "track": 2|3|4} (track 2 = the graphics
track, 3 = the accent track above it for a row overlapping an earlier one, 4 = the caption layer on top), plus "blend"
when the plan cell names one (`"blend": "difference"`: the highlighter, presets/youtube/default/highlight/README.md),
which the lane's placer sets on the clip and reads back (Premiere: place-graphics.py). The render
picked is the newest VERSION on disk (renders()); a plan whose `cut_rev` is not the job's transcript/cuts.json is
refused, and a row a ripple marked `"ripple": "orphaned"` is refused and named (the full rules:
lanes/premiere/place-graphics.py's docstring). A variant (`--variant ad`) derives graphics-plan.<variant>.json, or the
plan composed from graphics-plan.json's variants.<variant>, into hf-graphics/placement.<variant>.json.
"""
import argparse, hashlib, json, os, re, shlex, subprocess, sys, glob
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path


def sh(*cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"{' '.join(cmd[:3])} failed:\n{r.stderr or r.stdout}")
    return r.stdout


def probe_dur(path):
    # the first row only: ffprobe 9 prints a timecoded file's video row twice (its tmcd stream group, then the stream)
    r = sh('ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', path)
    return float(r.strip().split('\n')[0].strip().strip(',') or 0)


def probe_fps(path):
    r = sh('ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', path)
    n, _, d = r.strip().split('\n')[0].strip(',').partition('/')
    return float(n) / float(d or 1)


def check_variant_name(variant):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', variant):
        sys.exit(f'--variant {variant!r}: letters, digits, - and _ only (it becomes part of file names)')


VERSION = re.compile(r'(?P<letter>[a-z])|v(?P<n>\d+)(?P<sub>[a-z]*)')
WORD = re.compile(r'[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*')
SAME_RENDER_S = 60     # two renders of one graphic written closer than this are a COPY: a render takes minutes


def version_of(p, gid=None):
    """A render's VERSION as a sortable (N, letters), or None when its suffix cannot be read.

    The suffix is what follows `-alpha` in an alpha mov (`g10-alpha-v2d.mov` -> v2d; a comp word sits BEFORE
    it, `g17-rules-alpha-b.mov` -> b) and what follows `<id>` in a full-screen mp4, past an optional comp word
    (`g21-community-b.mp4` -> b). No suffix = (0, ''), one letter x = (1, x), v<N> = (N, ''), v<N><letters> =
    (N, letters). The old key read ONE letter only, so `-v2d` keyed '' and lost to every stale lettered file
    while a bare `g10-alpha.mov` won the path tie-break (2026-09-21: 14 of 18 scenes would have been laid from
    rejected renders, and --verify would have passed, since it checks a row only against its own file).
    How the letter series and the v series rank against EACH OTHER is renders()'s call, not this key's."""
    v = _version(p, gid)
    return v and v[1]


def _version(p, gid=None):
    """(series, key) for version_of: series 'letter' (no suffix, or one letter) or 'v' (v<N>...), None if unreadable."""
    stem, ext = os.path.splitext(os.path.basename(p))
    if ext.lower() == '.mp4':
        if not gid or not stem.startswith(gid): return None
        s = stem[len(gid):]
    else:
        if '-alpha' not in stem: return None
        s = stem.rpartition('-alpha')[2]
    if not s: return 'letter', (0, '')
    if not s.startswith('-'): return None
    s = s[1:]
    m = VERSION.fullmatch(s)
    if not m and ext.lower() == '.mp4':
        head, _, tail = s.rpartition('-')
        m = VERSION.fullmatch(tail) if head and WORD.fullmatch(head) else None
        if not m and WORD.fullmatch(s): return 'letter', (0, '')     # a comp word and no version: g21-community.mp4
    if not m: return None
    return ('letter', (1, m.group('letter'))) if m.group('letter') else ('v', (int(m.group('n')), m.group('sub')))


def renders(*patterns, gid=None):
    """Every render the patterns match, ending with THE PICK (the newest version); the one before it is the runner-up.

    Neither the names nor the file times are right on their own, and both failures are on disk:
      · within ONE name series the NAME orders: a restored copy rewrites every mtime within seconds in no order
        (a job copied back from cold storage 2026-09-14 reads its bare g08.mp4 as newer than g08-f.mp4);
      · BETWEEN the letter series and the v series the RENDER TIME orders: a job rendered a v2a..v2d set and
        then went back to lettering, and its b..s renders (a day of work, 2026-09-22) are newer than v2d, which a
        name-only rank would have laid instead;
      · two series tops written less than SAME_RENDER_S apart are a copy (the 2026-09-21 workaround cloned v2d
        to a letter in the same second), not two renders: the name decides (v over letters), with a ⚠.
    An unreadable suffix ranks below every readable version, named. Ties go to the newer file, then the path."""
    bad, series = [], {}
    for f in sorted({f for pat in patterns for f in glob.glob(pat)}):
        v = _version(f, gid)
        if v is None:
            print(f"⚠ {os.path.basename(f)}: version suffix not readable (none, one letter, v<N> or v<N><letters>), "
                  "ranked below every readable version")
            bad.append((os.path.getmtime(f), f))
        else:
            series.setdefault(v[0], []).append((v[1], os.path.getmtime(f), f, v[0]))
    for lst in series.values(): lst.sort()
    tops = sorted((lst[-1] for lst in series.values()), key=lambda t: (t[1], t[2]))
    if len(tops) == 2 and tops[1][1] - tops[0][1] < SAME_RENDER_S:
        tops.sort(key=lambda t: t[3] == 'v')
        print(f"⚠ {os.path.basename(tops[1][2])} and {os.path.basename(tops[0][2])} were written "
              f"{abs(tops[1][1] - tops[0][1]):.0f} s apart, a copy rather than two renders: ranked by NAME, check the pick")
    rest = sorted(t for lst in series.values() for t in lst[:-1])
    return [f for _, f in sorted(bad)] + [t[2] for t in rest] + [t[2] for t in tops]


LAYOUT_PY = Path(__file__).resolve().parents[1] / 'presets' / 'instagram' / 'talking-head-explainer' / 'layout.py'


def compose_variant_plan(job, variant):
    """graphics-plan.json's `variants.<variant>` composed into the whole plan of that sequence, by the preset's own
    layout.compose_variant (imported by path, as validate-plan.py does): one composition, shared with captions.py,
    layout.py and graphics-qa-short.py. Exits naming what is missing."""
    main = Path(job) / 'graphics-plan.json'
    if not main.exists():
        sys.exit(f'no graphics-plan.{variant}.json and no graphics-plan.json in {job}: nothing to place')
    with open(main, encoding="utf-8") as f: plan = json.load(f)
    if variant not in (plan.get('variants') or {}):
        sys.exit(f'no graphics-plan.{variant}.json in {job}, and graphics-plan.json has no variants.{variant}: nothing to place')
    import importlib.util
    spec = importlib.util.spec_from_file_location('th_layout_placer', LAYOUT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return mod.compose_variant(plan, variant)
    except (mod.MissingInput, mod.LayoutError) as e:
        sys.exit(f'✗ graphics-plan.json variants.{variant} does not compose: {e}')


class Placer:
    def __init__(self, job, variant=None):
        self.job = Path(job).resolve()
        self.hf = self.job / 'hf-graphics'
        self.variant = variant
        if variant:
            # a SECOND sequence of the same job (an AD cut, a clone of the organic one) with its own plan and rows
            check_variant_name(variant)
        tag = f'.{variant}' if variant else ''
        self.pj = self.hf / f'placement{tag}.json'
        if self.pj.exists():
            with open(self.pj, encoding="utf-8") as f: self.rows = json.load(f)
        else:
            self.rows = []
        for r in self.rows:
            if r.get('kind') == 'alpha': r['kind'] = 'overlay'     # older rows named the format, not the role
        self.plan_p = self.job / f'graphics-plan{tag}.json'
        self.composed = False
        if variant and not self.plan_p.exists():
            self.plan = compose_variant_plan(self.job, variant)      # graphics-plan.json variants.<v>, or exits naming both
            self.plan_p = self.job / 'graphics-plan.json'
            self.composed = True
            print(f'no graphics-plan.{variant}.json: composed from graphics-plan.json variants.{variant} '
                  '(the preset\'s layout.compose_variant)')
        else:
            if not self.plan_p.exists():
                sys.exit(f'no {self.plan_p.name} in {self.job}: nothing to place')
            with open(self.plan_p, encoding="utf-8") as f: self.plan = json.load(f)
        vc = self.job / 'transcript' / f'cuts.{variant}.json'
        self.cuts_p = vc if variant and vc.exists() else self.job / 'transcript' / 'cuts.json'
        # the cut_rev stamp belongs to the file it is in: a composed plan's is the organic plan's, against cuts.json
        self.rev_p = self.job / 'transcript' / 'cuts.json' if self.composed else self.cuts_p
        self.cells = [b for b in self.plan['beats'] if b.get('graphic')]
        self.off = float(self.plan.get('timeline_offset') or 0.0)
        self.fps = None
        self._cuts = None
        self._unstamped = None      # set when an unstamped plan is older than its EDL: the writes refuse
        self.check_cut_rev()
        self.check_orphans()

    def shown_job(self, quote=True):
        """The job folder as a remedy command names it: relative to the cwd when under it, forward slashes (and quoted
        for the shell unless `quote` is False), because the command is pasted into a shell (Git Bash drops the
        separators of a backslashed path) and into a JSON argument (a backslash is an escape there)."""
        j = self.job
        s = (Path(os.path.relpath(j)) if j.is_relative_to(Path.cwd().resolve()) else j).as_posix()
        return shlex.quote(s) if quote else s

    # the probes, as methods so a lane subclass (and its tests) can supply its own
    def _dur(self, f):
        return probe_dur(f)

    def _fps(self, f):
        return probe_fps(f)

    def check_orphans(self):
        """`workflows/ripple-cut.py` marks a row whose anchor a re-cut DELETED with `"ripple": "orphaned"`
        and leaves it at its old time, because nothing can invent a new one. The plan is re-stamped with the
        new `cut_rev` in the same pass, so the guard above waves the job through — and this placer would lay
        that row at a PRE-RECUT anchor under a green light, which is the exact bug ripple-cut exists to
        prevent. The marker had no consumer at all until now (2026-09-19). Refuse and NAME every one: the
        answer is a hand decision (re-anchor the row, or delete it), never a placer's guess."""
        bad = [f"placement row {r.get('id', '?')} at {r.get('start', 0):.3f}s" for r in self.rows if r.get('ripple') == 'orphaned'] \
            + [f"plan cell {c.get('id', '?')} at {float(c.get('start') or 0):.3f}s" for c in self.cells if c.get('ripple') == 'orphaned']
        if bad:
            sys.exit(f'✗ {len(bad)} row(s) are on a DEAD ANCHOR — a re-cut removed the frame they were timed to '
                     f'and `ripple-cut.py` marked them `"ripple": "orphaned"`. Placing them would put them at their '
                     f'pre-recut times. Nothing touched:\n' + '\n'.join(f'    {b}' for b in bad)
                     + '\n  Re-anchor each row (drop the `ripple` key once its time is right) or delete it, then re-run.')

    def check_cut_rev(self):
        """A plan authored against an OLD EDL places every row at a pre-recut anchor, silently: the cut
        moved under it and nothing here can tell. So the plan carries `cut_rev`, the first 12 of sha1 over
        the job's transcript/cuts.json (validate-plan.py stamps it, workflows/ripple-cut.py re-stamps it),
        and this refuses before any read or write when it disagrees. A plan with no stamp is an older job:
        warn once and continue, rather than bricking it — UNLESS the EDL changed after the plan was written
        (2026-09-22: an unstamped plan was placed straight after cuts.json was rewritten by hand, and the
        warning was waved through as old news). Then the plan provably predates the cut, and --apply /
        --reconcile --apply refuse (require_stamp); --plan and --verify only read, so they still warn."""
        cp = self.rev_p
        want = self.plan.get('cut_rev')
        if not cp.exists():
            return
        rev = hashlib.sha1(cp.read_bytes()).hexdigest()[:12]
        if not want:
            # validate-plan.py stamps graphics-plan.json against cuts.json and nothing else: a variant plan is stamped by hand
            stamp = (f'a PASSING `uv run .claude/skills/graphics-plan/scripts/validate-plan.py {self.shown_job()}` stamps it'
                     if not self.variant else f'validate-plan.py stamps graphics-plan.json only, so {self.plan_p.name} is stamped by hand')
            print(f'⚠ {self.plan_p.name} carries no cut_rev: nothing can prove it was authored against the '
                  f'current EDL ({cp.name} is {rev}). Every job authored before the stamp prints this; '
                  f'{stamp}, `workflows/ripple-cut.py --apply` re-stamps it on a re-time, and by hand it is '
                  f'"cut_rev": "{rev}" once the plan is known to match this EDL.')
            if cp.stat().st_mtime > self.plan_p.stat().st_mtime:
                self._unstamped = (f'✗ {self.plan_p.name} carries no cut_rev and transcript/{cp.name} changed AFTER it was '
                                   f'written: the cut moved under an unstamped plan, so nothing proves a single row still sits '
                                   f'on its anchor. Nothing touched.\n'
                                   f'  If the plan matches this EDL, stamp it: {stamp} ("cut_rev": "{rev}"). If the cut moved '
                                   f'under it, re-time it first: `uv run workflows/ripple-cut.py {self.shown_job()} --from <the old '
                                   f'{cp.name}> --apply`.')
                print(f'⚠ and {cp.name} is NEWER than {self.plan_p.name}: --apply and --reconcile --apply refuse until it is stamped.')
            return
        if want != rev:
            sys.exit(f'✗ the plan was authored against EDL {want}, the job is on {rev}: every row here would be '
                     f'placed at a pre-recut anchor. Nothing touched.\n'
                     f'  run `uv run workflows/ripple-cut.py {self.shown_job()} --from <the old {cp.name}> --apply` to '
                     f're-time and re-stamp, then re-run this.')

    def require_stamp(self):
        """The write paths' half of check_cut_rev: an unstamped plan older than its EDL is refused here."""
        if self._unstamped:
            sys.exit(self._unstamped)

    def F(self):
        if self.fps is None and self.plan.get('fps'):
            # the plan names the SEQUENCE rate: a section whose raw runs at another rate (the outro screen recording,
            # 30 fps on a 23.976 sequence, 2026-09-14) would otherwise snap every row to the raw's grid
            n, _, d = str(self.plan['fps']).partition('/'); self.fps = float(n) / float(d or 1)
        if self.fps is None:
            f = next((r['file'] for r in self.rows if os.path.exists(r['file'])), None)
            if not f:
                # first derive on a fresh job: no rows yet, so the grid comes from the raw footage (the
                # timeline's rate) — the 29.97 default snapped a 25 fps job's caption end to 19.5195 and
                # placed it a frame short of the cut (your-job, 2026-09-08)
                f = next((p for p in sorted(glob.glob(str(self.job / 'raw' / '*')))
                          if p.lower().endswith(('.mp4', '.mov', '.mkv', '.m4v'))), None)
            self.fps = self._fps(f) if f else 30000 / 1001
        return 1.0 / self.fps

    def snap(self, t):
        """Frame-snap a row time. Rows carry seconds and Premiere FLOORS to ticks, so a value a hair
        under a frame tick (a plan end written 16.783 for the cut at 16.78343, a builder end rounded
        to 4 decimals) lands the end pin one frame early AND trims the item out-point one frame short
        (g4 g5 g17 g21 each read one frame short of their V1 cut on your-job, 2026-09-07:
        the outgoing shot flashed for a frame before the cut). Nearest frame, 5 decimals, so the NUDGE
        always lands above the tick and END-START is a whole number of frames."""
        F = self.F()
        return round(round(t / F) * F, 5)

    def cuts(self):
        """The V1 cut points = cumulative kept durations (the same derivation as workflows/graphics-qa.py)."""
        if self._cuts is None:
            cp = self.cuts_p
            out, t = [], 0.0
            if cp.exists():
                with open(cp, encoding="utf-8") as f: segs = json.load(f)['segments']
                if segs and all(isinstance(s.get('_timeline'), list) for s in segs):
                    # an EDL read back from the timeline carries `_timeline` [start, end] per segment (sequence seconds): those ARE the V1 cuts;
                    # the cumulative sum of source durations drifts off the sequence grid on a mixed-rate source (a 30 fps screen recording on 23.976,
                    # 2026-09-14: every edge read 0.37 ms 'off the cut' while sitting on the frame Premiere placed)
                    out = [float(s['_timeline'][1]) - self.off for s in segs]
                else:
                    for s in segs:
                        t += float(s['end']) - float(s['start']); out.append(t)
            self._cuts = out
        return self._cuts

    def on_cut(self, t):
        """True when this row time IS a V1 cut (within half a frame). A clip a frame short of a cut
        flashes the outgoing shot, so a cut edge is held to half the usual readback tolerance."""
        c = self.cuts()
        return bool(c) and min(abs(t - x) for x in c) <= 0.5 * self.F()

    # ── rows from the plan ──────────────────────────────────────────────────
    def globs(self, gid, kind):
        """The render files a row of this kind is picked from (`kind` is the ROW's: text/captions/full/overlay)."""
        g = self.hf / 'gfx' / 'renders'
        return [str(p) for p in {
            'text': [self.hf / 'text-animation' / 'renders' / f'{gid}-alpha*.mov'],
            # a variant's caption layer is captions-<variant>-alpha*: the organic glob can never pick it up
            'captions': [self.hf / 'captions' / 'renders' / (f'captions-{self.variant}-alpha*.mov' if self.variant else 'captions-alpha*.mov')],
            'full': [g / f'{gid}.mp4', g / f'{gid}-*.mp4'],
            # a comp may carry a suffix word (g17-rules-alpha.mov): match `<id>-alpha*` or `<id>-<word>-alpha*`,
            # never a bare `<id>*` prefix (g1 would swallow g11 and g17b)
            'overlay': [g / f'{gid}-alpha*.mov', g / f'{gid}-[a-z]*-alpha*.mov'],
        }.get(kind, [])]

    def pick(self, gid, kind):
        """The newest version of this graphic's render, NAMED whenever there was a choice to make."""
        c = renders(*self.globs(gid, kind), gid=gid)
        if len(c) > 1:
            a, b = _version(c[-1], gid), _version(c[-2], gid)
            across = f', the top of the {b[0]} series, written before it' if a and b and a[0] != b[0] else ''
            print(f'  {gid}: picks {os.path.basename(c[-1])}, the newest of {len(c)} versions (next: {os.path.basename(c[-2])}{across})')
        return c[-1] if c else None

    def derive(self):
        have = {r['id']: r for r in self.rows}
        out, changes = [], []
        for c in self.cells:
            gid, kind = c['id'], c.get('kind')
            row = dict(have.get(gid, {}))
            if kind == 'text-animation':
                meta = self.hf / 'text-animation' / 'compositions' / f'{gid}.meta.json'
                f = self.pick(gid, 'text')
                if not meta.exists() or not f:
                    changes.append(f'{gid}: text animation not built/rendered yet'); continue
                with open(meta, encoding="utf-8") as fh: m = json.load(fh)
                new = dict(id=gid, file=f, start=self.snap(m['place']), end=self.snap(m['place'] + m['duration']), kind='text')
            elif kind == 'captions':
                # the short-form caption layer (a step-5 graphic, the user 2026-09-04): one alpha mov spanning the
                # cut, from the preset's caption builder, on its own track ABOVE every other overlay (V5) so the
                # V3/V4 overlap shuffle below can never land a card on top of it
                f = self.pick(gid, 'captions')
                if not f: changes.append(f'{gid}: caption layer not rendered yet (tiktok/raw: build.py --alpha; Talking Head Explainer: captions.py)'); continue
                end = float(c.get('end') or 0) or (float(c.get('start', 0)) + self._dur(f))
                new = dict(id=gid, file=f, start=self.snap(float(c.get('start', 0))), end=self.snap(end), kind='captions')
                row['track'] = 4
            elif kind in ('punch-cut', 'full-screen', 'scene') or c.get('bg') or c.get('broll_source'):
                # the creator's own B-roll: a full-frame cutaway conformed to gfx/renders/<id>.mp4 by workflows/broll-place.py
                f = self.pick(gid, 'full')
                if not f: changes.append(f'{gid}: no full-screen render yet'); continue
                new = dict(id=gid, file=f, start=self.snap(float(c['start'])), end=self.snap(float(c['end'])), kind='full')
            else:
                f = self.pick(gid, 'overlay')
                if not f: changes.append(f'{gid}: no overlay render yet'); continue
                # the renderer ceils a render to a whole frame, so an overlay whose cell ends ON a V1 cut would
                # overshoot it by one frame and flash over the next shot: the plan's end pins the out point
                end = float(c['start']) + self._dur(f)
                if c.get('end'): end = min(end, float(c['end']))
                new = dict(id=gid, file=f, start=self.snap(float(c['start'])), end=self.snap(end), kind='overlay')
            new['track'] = row.get('track', 2)
            if c.get('blend'):
                new['blend'] = str(c['blend']).lower()    # the clip's blend mode in the editor (the highlighter's difference)
            # a row already placed within HALF a frame of the derived time keeps its placed value: a sub-frame
            # rounding is not a change. A whole frame IS one (your-job, 2026-09-17: a split-part seam moved from
            # frame 2133 to 2132 across builds, the 1.5-frame tolerance kept the old edges, and the part ran one
            # frame past its render as a blank frame while its neighbour started a frame late)
            for k in ('start', 'end'):
                if k in row and abs(float(row[k]) - new[k]) <= 0.5 * self.F():
                    new[k] = float(row[k])
            if not row:
                changes.append(f"{gid}: new row {os.path.basename(new['file'])} {new['start']:.4f} → {new['end']:.4f} V{new['track'] + 1}")
            for k, v in new.items():
                if row and row.get(k) != v:
                    changes.append(f'{gid}: {k} {row.get(k)!r} → {v!r}')
            out.append(new)
        # track assignment: a row overlapping an earlier V3 row goes to V4, and is DERIVED every run: a row kept on V4
        # after its overlap was retired sat on the picture-in-picture track and hid its own PiP (2026-10-02, r27/p12)
        placed3 = []
        for r in out:
            if r['track'] in (2, 3):
                want = 3 if any(r['start'] < p['end'] - 1e-3 and p['start'] < r['end'] - 1e-3 for p in placed3) else 2
                if want != r['track']:
                    changes.append(f"{r['id']}: overlaps a V3 graphic → V4" if want == 3 else f"{r['id']}: no longer overlaps a V3 graphic → V3")
                r['track'] = want
            if r['track'] == 2: placed3.append(r)
        return out, [c for c in changes if c]

    # ── the timeline, read back ─────────────────────────────────────────────

    def sync_plan(self, max_frames=None):
        """Write placed start/end back into the plan. `max_frames` bounds what may be written: the
        automatic writeback on `--plan --write` passes 0.5 so it can carry back the snap() rounding and
        NOTHING ELSE. A bigger gap is a real disagreement between the plan and the build, and laundering
        it into the plan destroys the cell the gap was measured against (2026-09-19, both proved offline):
        an overlay's plan `end` is a BOUND — `derive()` reads it as `min(start + render, end)` — so writing
        the realized end back pins the graphic to the SHORTEST render it ever had, and a later extended
        re-render is then clamped back to it with nothing printed anywhere; and a text row whose meta.json
        is stale against the plan pushed 8 frames per row into your-job's plan, moving the word anchor the
        cell was written from. Those belong on screen as a gate FAIL, which says to reconcile or fix the
        placement. Unbounded stays the standalone `--sync-plan`: a row placed by hand IS the new truth.

        Neither writes a plan check_cut_rev() found unstamped and OLDER than its EDL: that age is what arms the
        --apply refusal, and a sync (even half a frame of snap rounding, which `--plan --write` finds on most
        jobs) would date the plan after the EDL and lift the refusal with no stamp (2026-09-23)."""
        if self.composed:
            msg = (f'{self.plan_p.name} NOT synced: the {self.variant} plan is composed from its variants.{self.variant}, and '
                   'writing the composed plan back would replace the organic one. Edit the variant\'s cells in '
                   f'graphics-plan.json variants.{self.variant} by hand.')
            if max_frames is None: sys.exit('✗ ' + msg)
            print('⚠ ' + msg)
            return
        if self._unstamped:
            again = '--plan --write' if max_frames is not None else '--sync-plan'
            msg = (f'{self.plan_p.name} NOT synced: it carries no cut_rev and {self.cuts_p.name} changed after it, so '
                   f'writing it now would date it AFTER that EDL and lift the --apply refusal without a stamp. Stamp it '
                   f'first, then re-run {again}.')
            if max_frames is None: sys.exit('✗ ' + msg)
            print('⚠ ' + msg)
            return
        F = self.F()
        rows = {r['id']: r for r in self.rows}
        n, held = 0, []
        for b in self.plan['beats']:
            r = rows.get(b.get('id'))
            if not r: continue
            for k in ('start', 'end'):
                if abs(float(b[k]) - r[k]) > 1e-4:
                    d = (r[k] - float(b[k])) / F
                    if max_frames is not None and abs(d) > max_frames:
                        held.append(f"{b['id']}: {k} plan {float(b[k]):.4f} vs placed {r[k]:.4f} ({d:+.2f} frames)")
                        continue
                    print(f"{b['id']}: {k} {float(b[k]):.4f} → {r[k]:.4f} ({d:+.2f} frames)")
                    b[k] = r[k]; n += 1
        if held:
            print(f"NOT synced — {len(held)} value(s) over {max_frames} frame(s) from the plan; the plan and the build "
                  "disagree, reconcile them by hand (or `--sync-plan` if the placement is the truth):")
            for h in held: print('  ⚠ ' + h)
        if n:
            with open(self.plan_p, 'w', encoding="utf-8") as f: json.dump(self.plan, f, indent=1)
            print(f'{self.plan_p.name}: {n} value(s) synced to the placement')
        else:
            print(f'{self.plan_p.name} already matches {self.pj.name}')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--variant', help='a second sequence\'s rows: graphics-plan.<NAME>.json -> placement.<NAME>.json')
    ap.add_argument('--write', action='store_true', help='save the rows and sync the plan\'s frame-snap roundings')
    a = ap.parse_args(argv)
    p = Placer(a.job, variant=a.variant)
    rows, changes = p.derive()
    for c in changes: print('  ' + c)
    if a.write:
        p.pj.parent.mkdir(parents=True, exist_ok=True)
        with open(p.pj, 'w', encoding="utf-8") as f: json.dump(rows, f, indent=1)
        print(f'wrote {len(rows)} rows -> {p.pj}')
        # bounded to half a frame: the rows were just derived FROM the plan, so a sub-frame gap is snap()'s rounding
        p.rows = rows
        p.sync_plan(max_frames=0.5)
    else:
        print(f'{len(rows)} rows derived, {len(changes)} change(s) vs {p.pj.name} (add --write to save)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
