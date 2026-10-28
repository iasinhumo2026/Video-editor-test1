#!/usr/bin/env python3
"""replay.py: build a job's Final Cut timeline (FCPXML) from its PIPELINE files, so a fresh job runs on this lane.

  uv run lanes/finalcut/replay.py projects/<job> [--steps 2,3,4,5,6,music] [--grade-ranges A-B ...] [--lift N|auto]
                                   [--format long-form|short-talking-head-explainer|tiktok-raw]
  then: uv run lanes/finalcut/import.py <the .fcpxml it names>

The format (the frame size, whether step 4 grades, the layout keys) is graphics-plan.json's `format`/`preset`; a job
with no plan yet takes it from --format, else from its RUN.md (the `| preset |` row's backticked path, then the
`| format |` row). A fact line names where it came from; with step 4 asked and no format anywhere, it refuses.

It writes projects/<job>/finalcut/<name>.fcpxml for a NEW library projects/<job>/finalcut/<name>.fcpbundle (the
first free <job>, <job>-v2, ...: import.py refuses an existing library, so a rebuild is a new library and project;
the old one keeps any hand edit made in Final Cut). What it reads, per pipeline step (LANES.md, the Final Cut column):

  2  transcript/cuts.json, then each sections/<s>/transcript/cuts.json in timeline order: one V1 spine clip per
     segment carrying its own dialogue, butt-joined where no `_timeline` says otherwise, in/out on the timeline's
     frame grid exactly as the Premiere replay lays them; a `media` segment (a lip-sync substitute) plays that file
     from 0; an `audio_lead` (a hand J-cut) starts the dialogue that much early, as a split edit.
  3  audio-normalized/<raw name> for every raw that has one (workflows/normalize-sections.sh: the measured gain into the
     -6 dBFS limiter, the picture bit for bit); on the Talking Head Explainer, the second-voice lift from
     transcript/voices.json as volume keys on the dialogue (voice-gain.py --second-voice decides it, --lift names it).
  4  long-form and the Talking Head Explainer (TikTok/raw is never graded, and says so): the house Custom LUT on every
     V1 clip of the camera footage (graphics-plan.json `graphics_scope` ranges when it has them, --grade-ranges to
     override, else all of V1).
  5  hf-graphics/placement.json of the job and each section (their `timeline_offset`; written by
     `uv run workflows/placement.py projects/<job> --write`): connected clips on lanes 1.., straight alpha as rendered,
     a full-screen mp4's own sound muted. A plan with graphic cells and no placement.json is a ⚠ (a refusal when
     --steps names 5).
  5′ the Talking Head Explainer: the plan's `layout` map through face-frame.json `modes` as V1 transforms, a hold
     key pair at every switch inside a clip (V1 never razored); long-form: the opening zoom-out on the first clip and
     every `push_in` beat's push-in, 19 linear keys each (what the Premiere bridge's `zoom` bakes).
  6  hf-graphics/sfx-plan.json of the job and each section: lanes -1.. (plan track 1 = A2), levels as clip dB, each
     sound cut where the next on its track starts (as Premiere's overwrite lays it), `fade_out_s` as a fade.
  +  hf-graphics/music-plan.json (track, bed_db, source_in, tail; an optional `end`; written by
     `uv run workflows/music-onset.py <track> --write-plan projects/<job>`): the bed from 0 to the end of the job's own
     timeline (its sections excluded) at the bed level, keyed to -96 dB over the tail. A track in audio/ with no
     music-plan.json is a ⚠.

Refuses (exit 2) what the Premiere placers refuse: a plan whose `cut_rev` is not the cut on disk, an orphaned row
(`ripple: orphaned`), an sfx-plan.json whose graphic moved since it was derived while its cues did not (sfx-plan.py's
stale_gids, which place-sfx.py warns on), missing media. Everything laid differently from Premiere prints as a ⚠ line.
Exit: 0 written · 2 refused.
"""
import argparse, glob, hashlib, importlib.util, json, math, os, re, subprocess, sys
from fractions import Fraction as F
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
from fcpxml_writer import Timeline, probe  # noqa: E402

LUT_UID = 'FxPlug:14B39AEF-607D-42DF-98DD-DB3DD345E925'   # Final Cut's Custom LUT
STEPS = ('2', '3', '4', '5', '6', 'music')
# --format: the plan's own (format, preset) for a job with no graphics-plan.json yet
FORMATS = {'long-form': ('long-form', 'presets/youtube/default'),
           'short-talking-head-explainer': ('short-talking-head-explainer', 'presets/instagram/talking-head-explainer'),
           'tiktok-raw': ('short-tiktok-raw', 'presets/tiktok/raw')}
AUDIO_EXT = ('.mp3', '.wav', '.m4a', '.aac', '.aif', '.aiff', '.flac')
EDGE = F(6, 10)            # a layout switch closer than this many frames to a clip edge is that clip's neighbour's
LIFT_RAMP, LIFT_LEAD, LIFT_MIN = F(1, 20), F(1, 50), F(1, 50)   # the lift's ramp / lead inside the span / min overlap
BLUR_K = 3.8               # Zoom blur Amount per scale point moved in one frame (calibrated on Premiere's 360° shutter)
ZOOM_UID = '.../Effects.localized/Blur.localized/Zoom.localized/Zoom.moef'   # Final Cut's Blur > Zoom
# Final Cut plays a MONO clip into L and R at half amplitude each (-6.02 dB, measured 2026-09-25); Premiere plays it at
# -3 dB (its centre pan law) and audio-polish.py gives the dialogue that 3 dB back. So, to sound as Premiere does:
MONO_DIALOGUE_DB = 20 * math.log10(2)     # a mono dialogue clip at the level the house chain measured it for
MONO_OTHER_DB = 10 * math.log10(2)        # a mono SFX or music clip at Premiere's -3 dB


def sfx_planner():
    """workflows/sfx-plan.py as a module (its stale_gids)."""
    spec = importlib.util.spec_from_file_location('sfx_plan', REPO / 'workflows' / 'sfx-plan.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Refuse(Exception):
    pass


def jload(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def frac(x):
    return F(x).limit_denominator(10 ** 9) if isinstance(x, float) else F(x)


class Part:
    """The job or one of its sections: its own cut, plan, placement and SFX plan on the shared timeline."""

    def __init__(self, d, root):
        self.dir, self.root = Path(d), Path(root)
        self.cuts = jload(self.dir / 'transcript' / 'cuts.json')
        if not self.cuts:
            raise Refuse(f'no transcript/cuts.json in {self.dir}: run rough-cut first')
        self.plan = jload(self.dir / 'graphics-plan.json', {})
        self.offset = frac(self.plan.get('timeline_offset', 0))
        first = self.cuts['segments'][0].get('_timeline')
        self.order = frac(first[0]) if first else self.offset

    def raw(self, seg):
        if seg.get('media'):
            m = seg['media']
            for base in (self.dir, self.root, REPO):
                if (base / m).exists():
                    return os.path.realpath(base / m)
            raise Refuse(f'{self.dir.name}: media {m} not found')
        want = seg['clip'].lower()
        for p in sorted((self.dir / 'raw').iterdir()) if (self.dir / 'raw').is_dir() else []:
            if p.name.lower() == want:
                return os.path.realpath(p)
        raise Refuse(f'{self.dir.name}: raw {seg["clip"]} not found in raw/')


def cut_rev(part):
    return hashlib.sha1((part.dir / 'transcript' / 'cuts.json').read_bytes()).hexdigest()[:12]


def resolve_format(plan, job, flag):
    """(format, preset, where it came from): graphics-plan.json's own, else --format, else RUN.md's `| preset |` row
    (its backticked path), then its `| format |` row. ('', '', None) when none of them names it."""
    if plan.get('format') or plan.get('preset'):
        return (plan.get('format') or '').lower(), plan.get('preset') or '', 'graphics-plan.json'
    if flag:
        return FORMATS[flag] + ('--format',)
    run = job / 'RUN.md'
    txt = run.read_text(encoding='utf-8', errors='replace') if run.exists() else ''
    m = re.search(r'^\|\s*preset\s*\|([^|\n]*)\|', txt, re.M | re.I)
    b = re.search(r'`([^`]*presets/[^`]*)`', m.group(1)) if m else None
    if b:
        p = b.group(1)
        return next(((f, p, 'RUN.md preset') for f, pp in FORMATS.values() if pp in p),
                    ('long-form' if 'youtube/' in p else 'short', p, 'RUN.md preset'))
    m = re.search(r'^\|\s*format\s*\|([^|\n]*)\|', txt, re.M | re.I)
    t = m.group(1).lower() if m else ''
    for key, word in (('short-talking-head-explainer', 'explainer'), ('tiktok-raw', 'tiktok'), ('long-form', 'long')):
        if word in t:
            return FORMATS[key] + ('RUN.md format',)
    return '', '', None


def mode_xf(mode, info, FW, FH):
    """A face-frame.json mode (scale 1 = the source fitted by height into the 9:16 frame, centre = where the source's
    centre lands, frame fractions) as FCP units: scale over the media conform-fitted, position in % of frame height.
    The media's DISPLAY size: a phone raw coded 1920x1080 with a 90° rotation is fitted as the 1080x1920 it shows."""
    mw, mh = info['display']
    fit = min(FW / mw, FH / mh)
    s = mode['scale'] * (FH / mh) / fit
    cx, cy = mode['centre']
    return (cx - 0.5) * FW / FH * 100, -(cy - 0.5) * 100, s


def ease(name, x):
    if name.startswith('quart'):
        return 1 - (1 - x) ** 4
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2      # inout (cubic), the push-in


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--steps', help='which to build (default all): ' + ','.join(STEPS))
    ap.add_argument('--format', choices=sorted(FORMATS), help='the job\'s format when graphics-plan.json has none '
                    '(default: RUN.md\'s preset / format row)')
    ap.add_argument('--name', help='project + library name (default: the first free <job>, <job>-v2, ...)')
    ap.add_argument('--out-dir', help='default projects/<job>/finalcut')
    ap.add_argument('--width', type=int)
    ap.add_argument('--height', type=int)
    ap.add_argument('--grade-ranges', nargs='*', help='timeline seconds A-B the grade covers (camera footage)')
    ap.add_argument('--lift', default='auto', help='second-voice lift in dB, or auto (voice-gain.py decides), or 0')
    a = ap.parse_args(argv)
    try:
        return build(a)
    except Refuse as ex:
        print(f'✗ {ex}', file=sys.stderr)
        return 2


def build(a):
    job = Path(a.job).resolve()
    steps = set(s.strip().replace('′', '') for s in (a.steps or ','.join(STEPS)).split(','))
    parts = [Part(job, job)] + sorted((Part(d, job) for d in sorted(glob.glob(str(job / 'sections' / '*')))
                                        if (Path(d) / 'transcript' / 'cuts.json').exists()), key=lambda p: p.order)
    plan = parts[0].plan
    fmt, preset, fsrc = resolve_format(plan, job, a.format)
    short = fmt.startswith('short') or fmt.startswith('tiktok') or 'instagram/' in preset or 'tiktok/' in preset
    explainer = 'talking-head-explainer' in preset or 'explainer' in fmt
    graded = fmt == 'long-form' or 'youtube/default' in preset or explainer
    fps = plan.get('fps') or parts[0].cuts.get('fps')
    notes, facts = [], []
    if fsrc is None and '4' in steps:
        raise Refuse('the job\'s format is unknown (no format in graphics-plan.json, no preset or format row in RUN.md), '
                     'and step 4 grades by format: pass --format long-form|short-talking-head-explainer|tiktok-raw')
    facts.append(f'format: {fmt or "?"}{" · " + preset if preset else ""} (from {fsrc or "nowhere: step 4 not asked"})')

    first = parts[0].raw(parts[0].cuts['segments'][0])
    info0 = probe(first)
    FR = F(1) / F(fps) if fps else info0['frame']
    dw, dh = info0['display']
    FW, FH = (a.width or (1080 if short else dw)), (a.height or (1920 if short else dh))
    snap = lambda x: round(frac(x) / FR) * FR

    out_dir = Path(a.out_dir) if a.out_dir else job / 'finalcut'
    name = a.name
    if not name:
        n = 1
        while (out_dir / (name := job.name + ('' if n == 1 else f'-v{n}'))).with_suffix('.fcpbundle').exists():
            n += 1
    T = Timeline(name, FW, FH, frame=FR, event=job.name)
    infos = {}

    def info(m):
        if m not in infos:
            infos[m] = probe(m)
        return infos[m]

    # ── step 2 (and 3's media): the cut ────────────────────────────────────────────────────────────────────
    baked = job / 'audio-normalized'
    v1, a1 = [], []
    cursor = F(0)
    for part in parts:
        for s in part.cuts['segments']:
            raw = part.raw(s)
            if s.get('media'):
                src_in, dur = F(0), snap(s['end']) - snap(s['start'])
            else:
                src_in = snap(s['start'])
                dur = snap(s['end']) - src_in
                src_frame = info(raw)['frame']
                if src_frame > FR * F(1001, 1000):
                    notes.append(f'{os.path.basename(raw)} runs slower than the timeline: Premiere floors its in/out '
                                 f'to its own frames, here they sit on the timeline grid (check the cut at its joints)')
            start = snap(s['_timeline'][0]) if s.get('_timeline') else cursor
            media = raw
            if '3' in steps:
                b = baked / os.path.basename(raw)
                if b.exists():
                    media = str(b)
                elif not s.get('media'):
                    notes.append(f'no baked audio for {os.path.basename(raw)} (run workflows/'
                                 f'normalize-sections.sh {job}): its dialogue is laid raw, no house chain')
            nm = os.path.splitext(os.path.basename(raw))[0]
            v1.append(dict(track='V1', media=media, start=start, dur=dur, src_in=src_in, name=nm, part=part))
            lead = snap(s.get('audio_lead') or 0)
            if lead and a1:
                a1[-1]['dur'] -= lead
            a1.append(dict(track='A1', media=media, start=start - lead, dur=dur + lead, src_in=src_in - lead, name=nm,
                           role='dialogue'))
            cursor = start + dur
    missing = {os.path.basename(p) for p in (i['media'] for i in v1) if not os.path.exists(p)}
    if missing:
        raise Refuse(f'media missing: {", ".join(sorted(missing))}')
    if any(abs(x['start'] - (y['start'] + y['dur'])) > FR / 2 and x['start'] < y['start'] + y['dur']
           for y, x in zip(v1, v1[1:])):
        raise Refuse('V1 clips overlap: the cut\'s _timeline and its durations disagree')

    # ── step 3: the second-voice lift (the Talking Head Explainer) ───────────────────────────────────────────
    voices = jload(job / 'transcript' / 'voices.json')
    if '3' in steps and explainer and voices and voices.get('spans') and a.lift != '0':
        if a.lift == 'auto':
            r = subprocess.run(['uv', 'run', str(REPO / 'workflows' / 'voice-gain.py'), str(job), '--second-voice', '--json'],
                               capture_output=True, text=True)
            try:
                sv = json.loads(r.stdout).get('second_voice') or json.loads(r.stdout)
                lift = 0 if sv.get('unmeasurable') else int(sv.get('lift_db') or 0)
            except (ValueError, AttributeError):
                raise Refuse(f'voice-gain.py --second-voice failed: {(r.stderr or r.stdout).strip()[-400:]}')
        else:
            lift = int(a.lift)
        if lift:
            spans = [(sp.get('clip'), frac(sp['start']), frac(sp['end'])) for sp in voices['spans']]
            n = 0
            for c in a1:
                keys = lift_keys(spans, c, lift)
                if keys:
                    c['volume_keys'] = keys
                    n += 1
            facts.append(f'second voice lifted {lift:+d} dB on {n} dialogue clip(s) (voices.json spans, after the baked limiter)')

    # A mono file sounds 6 dB down in Final Cut, 3 in Premiere (MONO_*_DB): each clip gets the difference back.
    mono = lambda c: info(c['media']).get('channels') == 1
    for c in a1:
        if mono(c):
            c['volume_db'] = MONO_DIALOGUE_DB
            c['volume_keys'] = [(t, v + MONO_DIALOGUE_DB) for t, v in c.get('volume_keys', [])] or None
    if any(mono(c) for c in a1):
        facts.append(f'mono dialogue on {sum(mono(c) for c in a1)} clip(s): +{MONO_DIALOGUE_DB:.2f} dB (Final Cut splits mono to L+R at -6.02 dB)')

    # ── step 4: the grade ───────────────────────────────────────────────────────────────────────────────────
    lut = {}
    if '4' in steps and not graded:
        facts.append(f'grade: none on this format ({preset or fmt}: TikTok/raw footage plays as shot)')
    if '4' in steps and graded:
        ranges = None
        if a.grade_ranges:
            ranges = [tuple(frac(x) for x in r.split('-')) for r in a.grade_ranges]
        else:
            got = []
            for part in parts:
                sc = part.plan.get('graphics_scope')
                if isinstance(sc, dict) and isinstance(sc.get('ranges'), list):
                    got += [(frac(x) + part.offset, frac(y) + part.offset) for x, y in sc['ranges']]
                elif sc is not None:
                    notes.append(f'{part.dir.name}: graphics_scope is not a list of ranges: graded all its V1 '
                                 f'(pass --grade-ranges for the camera footage only)')
            ranges = got or None
        n = 0
        for c in v1:
            cov = sum(max(F(0), min(c['start'] + c['dur'], y) - max(c['start'], x)) for x, y in ranges) if ranges else c['dur']
            if cov > 0:
                c['filters'] = ['Custom LUT']
                n += 1
                if cov < c['dur']:
                    notes.append(f'V1 {float(c["start"]):.3f}s: only partly inside the grade ranges, graded whole')
        tmpl = (HERE / 'templates' / 'house-lut-filter.xml').read_text(encoding="utf-8")
        lut = {'Custom LUT': (LUT_UID, tmpl)}
        facts.append(f'grade: Custom LUT (the house cube) on {n} of {len(v1)} V1 clips')

    # ── step 5′: footage moves ──────────────────────────────────────────────────────────────────────────────
    if '5' in steps:
        for c in v1:     # a near-miss aspect (a 3836-wide raw on 3840) fills the frame, as Premiere's replay was scaled
            mw, mh = info(c['media'])['display']
            fit, fill = min(FW / mw, FH / mh), max(FW / mw, FH / mh)
            if 1 < fill / fit < 1.01:
                c['scale'] = (fill / fit, fill / fit)
        if explainer and plan.get('layout'):
            layout_moves(plan, job, v1, info, FW, FH, FR, facts)
        if not short:
            push_moves(parts, v1, FR, notes, facts)

    # ── step 5: graphics ────────────────────────────────────────────────────────────────────────────────────
    gfx = []
    if '5' in steps:
        for part in parts:
            rows = jload(part.dir / 'hf-graphics' / 'placement.json')
            if rows is None:
                if any(isinstance(b, dict) and b.get('graphic') for b in part.plan.get('beats') or []):
                    msg = (f'{part.dir.name}: graphics-plan.json has graphic cells but no hf-graphics/placement.json: '
                           f'run uv run workflows/placement.py {part.dir} --write')
                    if a.steps is not None:
                        raise Refuse(msg)
                    notes.append(msg + ' (no graphics laid)')
                continue
            want = part.plan.get('cut_rev')
            if want and want != cut_rev(part):
                raise Refuse(f'{part.dir.name}: graphics-plan.json cut_rev {want} is not the cut on disk '
                             f'({cut_rev(part)}): re-plan the graphics after the re-cut (workflows/ripple-cut.py)')
            rows = rows.get('rows', rows) if isinstance(rows, dict) else rows
            for r in rows:
                if r.get('ripple') == 'orphaned':
                    raise Refuse(f'{part.dir.name}: placement row {r.get("id")} is orphaned by a re-cut: resolve it first')
                f = r['file']
                if not os.path.exists(f):
                    raise Refuse(f'{part.dir.name}: render missing for {r.get("id")}: {f}')
                start = snap(frac(r['start']) + part.offset)
                end = snap(frac(r['end']) + part.offset)
                m = info(f)
                dur = min(end - start, m['duration'])
                item = dict(track=f'V{int(r.get("track", 2)) + 1}', media=f, start=start, dur=dur, src_in=F(0),
                            name=r.get('id') or Path(f).stem)
                # Premiere (place-graphics.py fit_scale) fills the frame only with a render at the sequence's size or
                # an integer fraction of it; anything else lays at its native pixels. Final Cut's conform fit fills
                # the first case by itself, so only the second needs a scale.
                # the Premiere sequence is the raw's size only when the raw has the project's aspect (a 16:9 raw on a
                # 9:16 Talking Head Explainer is filled into a 1080x1920 sequence)
                iw, ih = info0['display']
                sw, sh = (iw, ih) if iw * FH == ih * FW else (FW, FH)
                rw, rh = m['width'], m['height']
                if not ((rw, rh) == (sw, sh) or sw % rw == 0 and sh % rh == 0 and sw // rw == sh // rh):
                    fit = min(FW / rw, FH / rh)
                    sc = (FW / sw) / fit
                    item['scale'] = (sc, sc)
                    notes.append(f'{item["name"]}: {rw}x{rh} is no fraction of the {sw}x{sh} frame: '
                                 f'laid at its native pixels, as Premiere does')
                gfx.append(item)

    # ── step 6: SFX ─────────────────────────────────────────────────────────────────────────────────────────
    sfx = []
    if '6' in steps:
        for part in parts:
            hf = part.dir / 'hf-graphics'
            rows = jload(hf / 'sfx-plan.json')
            # a graphic moved by hand after the plan: laid, its cues sit where it used to be (place-sfx.py warns too)
            moved = sfx_planner().stale_gids(hf / 'sfx-plan.json', hf) if rows and (hf / 'placement.json').exists() else []
            if moved:
                raise Refuse(f'{part.dir.name}: graphic(s) moved since sfx-plan.json was derived and their cues did not: '
                             f'{", ".join(moved)}: re-plan them (workflows/sfx-plan.py --merge {",".join(moved)}), '
                             'or --record when the cues are right')
            for r in rows or []:
                if r.get('ripple') == 'orphaned':
                    raise Refuse(f'{part.dir.name}: sfx row {r.get("id")} is orphaned by a re-cut: re-run workflows/sfx-plan.py')
                f = r['file']
                if not os.path.exists(f):
                    alt = REPO / 'assets' / 'sfx' / os.path.basename(f)
                    if not alt.exists():
                        raise Refuse(f'{part.dir.name}: sound missing for {r.get("id")}: {f}')
                    f = str(alt)
                item = dict(track=f'A{int(r["track"]) + 1}', media=f, start=snap(r['at']), src_in=frac(r['src_in']),
                            full=frac(r['src_out']) - frac(r['src_in']), volume_db=float(r.get('level_db', 0)),
                            role='effects', name=r.get('id') or Path(f).stem)
                if r.get('fade_out_s'):
                    item['fade_out'] = frac(r['fade_out_s'])
                if info(f).get('channels') == 1:
                    item['volume_db'] += MONO_OTHER_DB
                sfx.append(item)
        by_track = {}
        for s in sorted(sfx, key=lambda s: s['start']):
            by_track.setdefault(s['track'], []).append(s)
        for rows in by_track.values():    # Premiere's overwrite cuts each sound where the next on its track starts
            for s, n in zip(rows, rows[1:] + [None]):
                end = s['start'] + s.pop('full')
                if n is not None and n['start'] < end:
                    end = n['start']
                s['dur'] = end - s['start']
            if any(s['dur'] <= 0 for s in rows):
                raise Refuse('two sounds start on the same frame of one track: fix sfx-plan.json')

    # ── music ───────────────────────────────────────────────────────────────────────────────────────────────
    music = []
    if 'music' in steps:
        mp = jload(job / 'hf-graphics' / 'music-plan.json')
        aud = [p.name for p in sorted((job / 'audio').glob('*')) if p.suffix.lower() in AUDIO_EXT] \
            if (job / 'audio').is_dir() else []
        if not mp and aud:
            notes.append(f'audio/ holds {", ".join(aud)} but there is no hf-graphics/music-plan.json, so no bed is laid: '
                         f'uv run workflows/music-onset.py <track> --write-plan {job}')
        if mp:
            track = mp['track'] if os.path.exists(mp['track']) else str(job / 'audio' / os.path.basename(mp['track']))
            if not os.path.exists(track):
                raise Refuse(f'music track missing: {mp["track"]}')
            own = [i for i in v1 + a1 + sfx + gfx if i.get('part', parts[0]) is parts[0]]
            main_end = parts[1].offset if len(parts) > 1 else None
            end = snap(mp['end']) if mp.get('end') else max(
                i['start'] + i['dur'] for i in own if main_end is None or i['start'] < main_end)
            if main_end is not None and not mp.get('end'):
                end = min(end, main_end)
            src_in, tail, bed = snap(mp['source_in']), frac(mp.get('tail', 2)), float(mp['bed_db'])
            if src_in + end > info(track)['duration']:
                notes.append(f'the music runs out {float(src_in + end - info(track)["duration"]):.1f} s before the bed ends (no loop)')
            bed += MONO_OTHER_DB if info(track).get('channels') == 1 else 0
            music.append(dict(track='A5', media=track, start=F(0), dur=end, src_in=src_in, role='music',
                              name=Path(track).stem, volume_keys=[(src_in + end - tail, bed), (src_in + end - F(1, 1000), -96.0)]))
            if len(parts) > 1 and not mp.get('end'):
                notes.append(f'music under the main timeline only (0 to {float(end):.3f} s), not its sections: '
                             f'add "end" to music-plan.json to run it further')

    for c in v1 + a1 + gfx + sfx + music:
        c.pop('part', None)
        T.add(**c)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{name}.fcpxml'
    if any('Zoom' in (c.get('filters') or []) for c in v1):
        lut['Zoom'] = (ZOOM_UID, (HERE / 'templates' / 'zoom-blur-filter.xml').read_text(encoding="utf-8"))
    r = T.write(str(out), str(out_dir / f'{name}.fcpbundle'), effects=lut)
    per = {}
    for it in T.items:
        per[it['track']] = per.get(it['track'], 0) + 1
    print(f'✓ {out}\n  project "{name}" · {FW}x{FH} @ {float(1 / FR):.3f} fps · {r["duration"]:.3f} s · '
          f'{r["assets"]} files · clips per track {dict(sorted(per.items()))}\n'
          f'  next: uv run lanes/finalcut/import.py {out}')
    for x in facts:
        print(f'  · {x}')
    for x in dict.fromkeys(notes + r['warnings']):
        print(f'  ⚠ {x}')
    return 0


def lift_keys(spans, c, db):
    """The second-voice lift as volume keys (source seconds, dB) on one dialogue clip: ramps INSIDE each span (the
    host beside it is never lifted, it has no limiter over it), a span reaching the clip's edge starts or ends lifted
    (audio-polish.py lift_keys, the same rule; its 20 ms lead kept, since Final Cut's key timing is unmeasured)."""
    name = os.path.basename(c['media']).lower()
    c_in, c_out = c['src_in'], c['src_in'] + c['dur']
    ivs = sorted((max(x, c_in), min(y, c_out)) for clip, x, y in spans
                 if (clip is None or clip.lower() == name or os.path.splitext(clip.lower())[0] == os.path.splitext(name)[0])
                 and min(y, c_out) - max(x, c_in) > LIFT_MIN)
    merged = []
    for x, y in ivs:
        if merged and x <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], y))
        else:
            merged.append((x, y))
    keys = []
    for x, y in merged:
        up, down = x > c_in, y < c_out
        lead = LIFT_LEAD if up else F(0)
        r = min(LIFT_RAMP, (y - x - lead) / ((up + down) or 1))
        for t, v in (([(x + lead, 0.0), (x + lead + r, float(db))] if up else [(x, float(db))])
                     + ([(y - r, float(db)), (y, 0.0)] if down else [(y, float(db))])):
            if not (keys and keys[-1][0] == t):
                keys.append((t, v))
    return keys


def layout_moves(plan, job, v1, info, FW, FH, FR, facts):
    """The layout map (timeline clock) as V1 transforms: W/S/T from face-frame.json modes, F and O keep W's footage.
    A clip with no switch inside it is static; a switch inside one is a 1-frame key pair (the hold), V1 never razored."""
    ff = jload(job / 'face-frame.json') or {}
    modes = ff.get('modes')
    if not modes:
        raise Refuse('the plan has a layout map but face-frame.json has no modes: run workflows/face-frame.py --modes')
    runs = []
    for row in plan['layout']:
        s, e, m = (row['start'], row['end'], row['mode']) if isinstance(row, dict) else row[:3]
        m = {'F': 'W', 'O': 'W'}.get(m, m)
        if m not in modes:
            raise Refuse(f'layout mode {m} has no face-frame.json mode')
        s, e = round(frac(s) / FR) * FR, round(frac(e) / FR) * FR
        if runs and runs[-1][2] == m:
            runs[-1] = (runs[-1][0], e, m)
        else:
            runs.append((s, e, m))

    def mode_at(t):
        return next((m for s, e, m in runs if s <= t < e), runs[-1][2] if t >= runs[-1][1] else runs[0][2])

    switches = [s for s, _e, _m in runs[1:]]
    keyed = 0
    for c in v1:
        a, b = c['start'], c['start'] + c['dur']
        inner = [n for n in switches if a + EDGE * FR < n < b - EDGE * FR]
        xf = lambda m: mode_xf(modes[m], info(c['media']), FW, FH)
        if not inner:
            x, y, s = xf(mode_at(a + FR / 2))
            if abs(x) > 1e-9 or abs(y) > 1e-9:
                c['position'] = (x, y)
            if abs(s - 1) > 1e-9:
                c['scale'] = (s, s)
            continue
        pos, sc = [], []
        for n in inner:
            for t, m in ((n - FR, mode_at(n - FR / 2)), (n, mode_at(n + FR / 2))):
                x, y, s = xf(m)
                src = c['src_in'] + (t - a)
                if not pos or pos[-1][0] != src:
                    pos.append((src, (x, y)))
                    sc.append((src, (s, s)))
        c['keys'] = {'position': pos, 'scale': sc}
        keyed += 1
    facts.append(f'layout: {len(runs)} runs from face-frame.json modes, {keyed} V1 clip(s) keyed across a switch')


def push_moves(parts, v1, FR, notes, facts):
    """Long-form: the opening zoom-out on the first V1 clip and each push_in beat's push-in, the Premiere bridge's `zoom`
    (18 frames, the preset's ease) as Premiere RENDERS it: its Transform runs a 360° shutter, so its frame t shows the
    move half a frame on, blurred over the frame. So the linear scale keys sit at each frame with the value half a frame
    ahead (plus one key before the ramp holding the start), and Final Cut's Zoom blur is keyed to BLUR_K x the scale
    points moved in that frame. Measured against a long-form test's Premiere master (2026-09-25): the opening
    frames from 26-38 dB PSNR to 38-49 dB; the lane's lab-notes § 15."""
    moves = []
    oz = parts[0].plan.get('opening_zoom_out') or {}
    moves.append((F(oz.get('start', 0)), int(oz.get('frames', 18)), oz.get('scale_from', 115), oz.get('scale_to', 100),
                  oz.get('ease', 'quart.out'), 'opening zoom-out'))
    for part in parts:
        for b in part.plan.get('beats') or []:
            if isinstance(b, dict) and b.get('push_in'):
                at = frac(b.get('push_at') if b.get('push_at') is not None else b['start']) + part.offset
                moves.append((at, 18, 100, 115, 'inout', f'push-in {b.get("id")}'))
    for at, frames, v0, v1_, ez, what in moves:
        at = round(at / FR) * FR
        c = next((c for c in v1 if c['start'] <= at < c['start'] + c['dur']), None)
        if c is None:
            notes.append(f'{what} at {float(at):.3f}s: no V1 clip there, skipped')
            continue
        if c.get('keys'):
            notes.append(f'{what} at {float(at):.3f}s: its clip already moves, skipped')
            continue
        if at + frames * FR > c['start'] + c['dur']:
            notes.append(f'{what} at {float(at):.3f}s runs past its clip\'s end (the Premiere bridge refuses it)')
        base = c.get('scale', (1, 1))[0]
        val = lambda x: v0 + (v1_ - v0) * ease(ez, min(1.0, max(0.0, x)))
        ks, blur = [], []
        for f in range(-1 if at - FR >= c['start'] else 0, frames + 1):
            t = c['src_in'] + (at - c['start']) + f * FR
            v = val((f + 0.5) / frames) / 100 * base
            ks.append((t, (v, v)))
            blur.append((t, BLUR_K * abs(val((f + 1) / frames) - val(f / frames)) if 0 <= f < frames else 0.0))
        c['keys'] = {'scale': ks}
        c['filters'] = ['Zoom'] + c.get('filters', [])        # the blur on the footage, then the grade (Premiere's order)
        c['filter_keys'] = {'Zoom': {'Amount': blur}}
    facts.append(f'footage moves: {len(moves)} (the opening zoom-out + {len(moves) - 1} push-ins)')


if __name__ == '__main__':
    sys.exit(main())
