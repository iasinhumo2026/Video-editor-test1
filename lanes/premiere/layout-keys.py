#!/usr/bin/env python3
"""layout-keys.py: the Premiere lane's half of the talking-head layout. It bakes the plan's footage modes onto V1 as
Motion HOLD keys (S split, T tight, W wide; F and O keep W's footage under their graphic), one hard cut per switch,
and never overwrites a Motion edit the creator made by hand.

  uv run lanes/premiere/layout-keys.py projects/<job>                  # --dry (the default): the keys, offline
  uv run lanes/premiere/layout-keys.py projects/<job> --verify         # every V1 clip read back: MATCH / DRIFT / HAND
  uv run lanes/premiere/layout-keys.py projects/<job> --apply          # write, read back, prove the audio, save, record
  ... --variant ad --sequence "<job> AD"    # a second deliverable: the plan's variants.ad composed in (layout.py)
  ... --sequence "<name>"                   # a live run refuses unless the active sequence is <name> (VE_SEQUENCE too)
  ... --apply --force-clip 21[,22]          # overwrite clips classified HAND (read them with --verify first)

WHY A LAYER, NOT A CUT (layout.md § 2). The layout rotation is the pacing engine, and it is a presentation decision
independent of the edit. Razoring V1 at every switch would cost the creator his trim points, and he re-cuts by hand.
So V1's edit points stay his, and each switch is two keys on the footage's own Motion: a hard cut in the framing,
never a ramp (a ramp reads as a camera operator, a hard switch reads as an edit).

INPUTS
  graphics-plan.json `layout`  the spans, through presets/instagram/talking-head-explainer/layout.py (spans(),
                               compose_variant()): the one implementation captions.py reads too, so the footage and
                               the caption switch on the same frame.
  face-frame.json `modes`      {W, S, T: {scale, centre}} through layout.modes(): scale relative to the source fitted
                               to the frame, centre = where the source centre lands, in frame fractions. Missing = exit
                               2, naming `uv run workflows/face-frame.py projects/<job> --modes`.
  the app                      the sequence's frame size and timebase, every V1 clip with its Motion, and each clip's
                               source size (ffprobe on its media path, a phone raw's rotation applied).
  --dry reads V1 off the EDL (transcript/cuts[.<variant>].json) and assumes the sequence at the source's size, which
  is the lane's rule (the sequence is the raw's size and rate), so it needs neither Premiere nor the media.

THE KEYS (plan_keys, pure)
  to_motion: Scale = 100 x mode.scale x fit (fit = sequence / source, 1 when they are the same size; another aspect is
  refused, it needs a crop decision), Position = mode.centre.
  A clip with no switch inside it gets STATIC values: its mode half a frame in. At every switch strictly inside a clip
  (more than 0.6 frame from its edges) a key ONE FRAME BEFORE carries the outgoing mode and a key ON the switch the
  incoming one, both in MEDIA time (inPoint + t - start: a clip's keys live on its source's clock, lab-notes.md).
  Nothing else: before its first key a property holds that key's value and after its last the last's, so a clip's
  opening mode needs no key of its own. Interpolation HOLD (enum 3; lab-notes.md: 0 linear, 3 hold, 4 bezier). The
  pair already makes an on-grid switch hard; hold keeps it hard when a source frame is sampled between the two keys
  (a mixed-rate source).

THE CREATOR'S HAND (the house lock: live state that disagrees with the plan is his edit, reported and left alone)
  Every V1 clip's live Motion is classified before anything is written:
    MATCH  it already equals the plan's keys: nothing to write.
    DRIFT  it is this tool's own state, off the plan: the untouched default (Scale 100, Position 0.5 0.5, no keys), or
           exactly what premiere/layout-keys[.<variant>].json records this tool wrote on that media range (a variant
           also reads the organic record, since its clone carries the organic's keys). A stale plan, a re-cut, a
           failed write. --apply rewrites it; --verify exits 1 on it.
    HAND   anything else is his: skipped and named, unless --force-clip names it. A HAND clip whose every value is one
           of this job's modes is flagged as such (an older framing pass): read it, then --force-clip it.

--apply, in order
  1. job_guard: the active project is the job's AND the active sequence passes the sequence rule.
  2. reads only: the sequence, V1 with Motion, source sizes; the keys; the classes. Nothing to write = no save.
  3. save, then a dated copy of the saved .prproj in premiere/archive/ (the rollback: a scripted edit is not undoable).
  4. an audio snapshot of every audio clip, in ticks.
  5. the writes through the bridge's es, then all of V1 read back: a written clip must equal its keys, every other
     clip must read as it did before. A miss stops the run UNSAVED.
  6. the audio snapshot again: IDENTICAL, else the run stops UNSAVED. Only then save, and write the record.
  The proofs come before the save (place-graphics.py's order), so a failed run is undone by closing without saving.

--verify reads every clip back, classifies it, prints seconds per layout mode, and exits 1 on DRIFT only (HAND is his).

NOTES
  · A graphic's Scale is place-graphics.py fit_scale's job (it sets and reads it back on every lay). The job-local
    script this generalizes set every graphic to 200 as a side effect, and so hid the swap bug fit_scale now fixes.
  · Re-run after any replay, V1 rebuild or re-cut: a fresh clip lands at the default, and a trimmed clip keeps keys
    that sit on the old clock (they read DRIFT until re-run).
  · Never re-run over a substituted clip (a lip-sync, a re-take) without --verify first. It is laid with the replaced
    clip's own framing keys and proven on the picture (framing-continuity.py); --verify names it HAND, and it is
    overwritten only by --force-clip, after its frames have been looked at.
Generalized (2026-09-23) from one job's hard-coded reframe script, which had no verify mode, cleared every key it found
and set every graphic's Scale on the way. Owner of the rule: presets/instagram/talking-head-explainer/layout.md § 2.
Tests: workflows/test_layout_keys.py (offline; the ExtendScript runs in node against a synthetic Premiere).
"""
import argparse, bisect, importlib.util, json, os, re, shutil, subprocess, sys, time
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from job_guard import require_job_project, job_root   # lanes/premiere/job_guard.py: the active project must be this job's
from pes import es, paged                   # lanes/premiere/pes.py: the bridge's one output contract

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


layout = _module('talking_head_layout', REPO / 'presets' / 'instagram' / 'talking-head-explainer' / 'layout.py')
audio_diff = _module('place_graphics', HERE / 'place-graphics.py').audio_diff   # one wording for the audio proof

BRIDGE = HERE / 'premiere-bridge.mjs'
TPS = 254016000000          # Premiere ticks per second
EDGE = 0.6                  # frames: a switch closer than this to a clip edge IS that edge (no key pair)
HOLD = 3                    # setInterpolationTypeAtKey: 0 linear, 3 hold, 4 bezier (lab-notes.md, verified 2026-07-17)
T_TOL, S_TOL, P_TOL = 1e-3, 1e-3, 1e-4   # key time (s), Scale (%), Position (frame fraction): readback tolerances
PAGE = 20                   # V1 clips per readback call (a media path and the keys per clip; the bridge caps at 64 KB)
BATCH = 10                  # clips per write call
FOOTAGE = {'S': 'S', 'T': 'T', 'W': 'W', 'F': 'W', 'O': 'W'}   # F and O keep the untouched shot under their graphic
DEFAULT = {'scale': 100.0, 'pos': [0.5, 0.5]}                  # a freshly laid clip: no keys, native size, centred
FACE_HINT = 'uv run workflows/face-frame.py projects/<job> --modes'


def refuse(msg, code=2):
    print(msg)
    sys.exit(code)


# ── pure planning ────────────────────────────────────────────────────────────────────────────────────────────────
def footage_runs(spans):
    """layout spans [(a, b, mode, ...)] -> the footage's own runs [(a, b, S|T|W)]. F and O keep W's footage, so a W>O
    or O>F switch is no switch on V1 (the graphic changes, the shot does not)."""
    out = []
    for s in spans:
        a, b, m = float(s[0]), float(s[1]), FOOTAGE.get(s[2], s[2])   # a framed row's key is its own footage
        if out and out[-1][2] == m and abs(out[-1][1] - a) < 1e-6:
            out[-1] = (out[-1][0], b, m)
        else:
            out.append((a, b, m))
    return out


def mode_at(runs, t):
    i = bisect.bisect_right([r[0] for r in runs], t) - 1
    return runs[max(0, min(i, len(runs) - 1))][2]


def to_motion(mode, seq=None, src=None):
    """A face-frame mode {scale, centre} as Premiere Motion {scale (%), pos [x, y] (frame fractions)} on this sequence
    for this source. fit = sequence / source: 1 at the same size, 2 for a 1080 source on a 2160 sequence."""
    fit = 1.0
    if seq and src and tuple(seq) != tuple(src):
        (sw, sh), (w, h) = seq, src
        if abs(sw * h - sh * w) <= 0.005 * sw * h:
            fit = sw / w
        elif w * sh > sw * h:
            # a source WIDER than the frame (a 16:9 raw finished as a 9:16 short): W is the source fitted by HEIGHT, and
            # face-frame.py measures a landscape raw on that face-centred crop, so its modes already carry the crop
            # (centre x = where the source's centre lands); layout.md § A 16:9 raw finished vertical
            fit = sh / h
        else:
            raise ValueError(f'a {w}x{h} source on a {sw}x{sh} sequence is narrower than the frame: the layout keys fit a '
                             'source of the sequence\'s own aspect, or a wider one by its height (a 16:9 raw on a 9:16 '
                             'short), never one that would leave the frame\'s sides bare')
    return {'scale': round(100.0 * float(mode['scale']) * fit, 4),
            'pos': [round(float(mode['centre'][0]), 6), round(float(mode['centre'][1]), 6)]}


def plan_keys(clips, spans, modes, fps, seq=None):
    """Every V1 clip's Motion target. clips: [{start, end, in (media s), src (w, h) optional, ...}] in timeline
    seconds; spans: layout spans; modes: {S, T, W: {scale, centre}}; fps: the SEQUENCE rate (switches are snapped to
    its grid). -> [{i, start, end, in, modes: [..], switches: [(t, out, in)], motion: {scale, pos} | {keys: [[t, s,
    [x, y]], ..]}}]"""
    F = 1.0 / fps
    runs = footage_runs(spans)
    switch = [round(r[0] / F) for r in runs[1:]]     # sequence FRAMES: the keys are deduped on integers, never seconds
    out = []
    for i, c in enumerate(clips):
        a, b, src = float(c['start']), float(c['end']), c.get('src')
        inner = [f for f in switch if a + EDGE * F < round(f * F, 6) < b - EDGE * F]
        row = {'i': c.get('i', i), 'start': a, 'end': b, 'in': float(c['in'])}
        if not inner:
            m = mode_at(runs, a + 0.5 * F)
            row.update(modes=[m], switches=[], motion=to_motion(modes[m], seq, src))
        else:
            at, sw = {}, []                  # sequence frame -> the mode keyed on it
            for f in inner:
                t = round(f * F, 6)
                o, n = mode_at(runs, t - 0.5 * F), mode_at(runs, t + 0.5 * F)
                at.setdefault(f - 1, o)      # a one-frame layout: its outgoing key IS the previous incoming key
                at[f] = n
                sw.append((t, o, n))
            keys = []
            for f in sorted(at):             # each time rounded ONCE, from the frame: 7.75775 and 7.757749 were one key
                v = to_motion(modes[at[f]], seq, src)
                keys.append([round(float(c['in']) + f * F - a, 6), v['scale'], v['pos']])
            row.update(modes=[sw[0][1]] + [s[2] for s in sw], switches=sw, motion={'keys': keys})
        out.append(row)
    return out


def _pos(p, q):
    return abs(float(p[0]) - float(q[0])) <= P_TOL and abs(float(p[1]) - float(q[1])) <= P_TOL


def same(a, b):
    """Two Motion states equal within the readback tolerances (static vs static, or the same keys)."""
    if 'keys' in a and 'keys' in b:
        return len(a['keys']) == len(b['keys']) and all(
            abs(x[0] - y[0]) <= T_TOL and abs(x[1] - y[1]) <= S_TOL and _pos(x[2], y[2]) for x, y in zip(a['keys'], b['keys']))
    if 'scale' in a and 'scale' in b:
        return abs(a['scale'] - b['scale']) <= S_TOL and _pos(a['pos'], b['pos'])
    return False


def live_motion(c):
    """A readback row's Position and Scale as one Motion state. Both static -> {scale, pos}; both keyed at the same
    times -> {keys}; anything else (one keyed, keys at different times, no Motion) -> a form that equals nothing, so
    it can only ever read HAND."""
    P, S = c.get('P'), c.get('S')
    if not P or not S:
        return {'other': 'no Motion Position/Scale'}
    if not P.get('keyed') and not S.get('keyed'):
        return {'scale': float(S['value']), 'pos': [float(P['value'][0]), float(P['value'][1])]}
    if P.get('keyed') and S.get('keyed'):
        pk, sk = (sorted(x.get('keys') or [], key=lambda k: k[0]) for x in (P, S))
        if pk and len(pk) == len(sk) and all(abs(p[0] - s[0]) <= T_TOL for p, s in zip(pk, sk)):
            return {'keys': [[round(float(p[0]), 6), float(s[1]), [float(p[1][0]), float(p[1][1])]] for p, s in zip(pk, sk)]}
    return {'other': f"Position {'keyed' if P.get('keyed') else 'static'}, Scale {'keyed' if S.get('keyed') else 'static'}, "
                     'keys that do not pair'}


def _rounded(x):
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, list):
        return [_rounded(v) for v in x]
    if isinstance(x, dict):
        return {k: _rounded(v) for k, v in x.items()}
    return x


def unchanged(c0, c1):
    """One V1 clip's Motion read twice, equal: through live_motion, or raw for a form live_motion cannot pair."""
    a, b = live_motion(c0), live_motion(c1)
    if 'other' not in a and 'other' not in b:
        return same(a, b)
    return _rounded([c0.get('P'), c0.get('S')]) == _rounded([c1.get('P'), c1.get('S')])


def recorded(records, c):
    """The Motion this tool recorded writing on this clip's media range: same media path, overlapping source span."""
    lo, hi = float(c['in']), float(c['in']) + float(c['end']) - float(c['start'])
    return [r['motion'] for rec in records for r in (rec or {}).get('clips') or []
            if r.get('path') == c.get('path')
            and min(hi, r['in'] + r['end'] - r['start']) - max(lo, r['in']) > T_TOL]


def classify(live, target, recorded_motions=()):
    """MATCH (at the plan) · DRIFT (this tool's own state, off the plan: the default or a recorded write) · HAND."""
    if same(live, target):
        return 'MATCH'
    if same(live, DEFAULT) or any(same(live, r) for r in recorded_motions):
        return 'DRIFT'
    return 'HAND'


def in_vocab(live, allowed):
    """True when every value in a live Motion state is one of `allowed` (to_motion of the job's modes)."""
    if 'keys' in live:
        vals = [(k[1], k[2]) for k in live['keys']]
    elif 'scale' in live:
        vals = [(live['scale'], live['pos'])]
    else:
        return False
    return all(any(abs(s - m['scale']) <= S_TOL and _pos(p, m['pos']) for m in allowed) for s, p in vals)


def describe(m, names=()):
    """A Motion state on one line. Every key prints with its media time, so a switch that MOVED reads as moved: as its
    mode (S@14.139) when `names` [(mode, to_motion)] holds its value, else as its Scale and Position."""
    if 'keys' in m:
        def key(k):
            n = next((n for n, v in names if abs(k[1] - v['scale']) <= S_TOL and _pos(k[2], v['pos'])), None)
            return f'{n}@{k[0]:.3f}' if n else f'Scale {k[1]:g} Position {k[2][0]:.4f} {k[2][1]:.4f} @{k[0]:.3f}'
        return f"{len(m['keys'])} keys ({', '.join(key(k) for k in m['keys'])})"
    if 'scale' in m:
        return f"Scale {m['scale']:g} Position {m['pos'][0]:.4f} {m['pos'][1]:.4f}"
    return m.get('other', '?')


def mode_seconds(spans):
    d = {}
    for s in spans:
        d[s[2]] = d.get(s[2], 0.0) + float(s[1]) - float(s[0])
    return d


def edl_clips(cuts, fps):
    """V1 as the EDL lays it (the --dry view): each segment's timeline span, frame-snapped the way the replay lays it,
    and its source in-point. A segment laid from substitute media keeps its `media` (its own clock on the timeline)."""
    F = 1.0 / fps
    snap = lambda t: round(round(t / F) * F, 6)
    segs = cuts.get('segments') or []
    tl = bool(segs) and all(isinstance(s.get('_timeline'), list) for s in segs)
    out, t = [], 0.0
    for i, s in enumerate(segs):
        d = float(s['end']) - float(s['start'])
        a, b = (float(s['_timeline'][0]), float(s['_timeline'][1])) if tl else (t, t + d)
        t = b
        out.append({'i': i, 'start': snap(a), 'end': snap(b), 'in': float(s['start']), 'media': s.get('media')})
    return out


# ── inputs ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _json(path, what):
    if not os.path.isfile(path):
        raise layout.MissingInput(f'{what}: no file at {path}')
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def load_inputs(job, variant=None):
    """(plan, spans, modes, plan fps) through layout.py. A missing input or a layout that does not tile exits 2."""
    try:
        plan = _json(os.path.join(job, 'graphics-plan.json'), 'graphics-plan.json')
        if variant:
            plan = layout.compose_variant(plan, variant)
        face = _json(os.path.join(job, 'face-frame.json'), f'face-frame.json (run: {FACE_HINT})')
        modes = layout.modes(face)
        fps = layout.parse_fps(plan.get('fps'))
        spans = layout.spans(plan, fps)
        # a row's own `frame` (a take framed apart from the median, face-frame.py --span) is a footage mode of its own:
        # its key and transform join the modes, so its clips are keyed to it and a hand Motion equal to it reads MATCH
        fsp = layout.footage_spans(plan, modes, fps)
        modes = {**modes, **{k: f for _a, _b, k, f in fsp}}
        spans = [(a, b, k if '*' in k else m, cy) for (a, b, m, cy), (_a, _b, k, _f) in zip(spans, fsp)]
    except layout.MissingInput as e:
        refuse(f'✗ missing input: {e}')
    except layout.LayoutError as e:
        refuse(f'✗ the plan\'s `layout` does not tile (L-TILE), so no key can be trusted: {e}\n'
               f'  uv run presets/instagram/talking-head-explainer/layout.py {Path(job).as_posix()}')   # pasted: forward slashes
    return plan, spans, modes, fps


def records_for(job, variant):
    """[this sequence's record, and for a variant the organic's too (a clone carries the organic's keys)]."""
    d = job_root(job) / 'premiere'
    paths = [d / f"layout-keys{'.' + variant if variant else ''}.json"] + ([d / 'layout-keys.json'] if variant else [])
    out = []
    for p in paths:
        if p.exists():
            with open(p, encoding="utf-8") as fp:
                out.append(json.load(fp))
    return out


def src_size(path):
    """(w, h) as Premiere shows the media: a phone raw coded 3840x2160 with a -90 rotation is 2160x3840. None if unreadable."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height:stream_side_data=rotation', '-of', 'json', path], capture_output=True, text=True)
    if r.returncode:
        return None
    s = (json.loads(r.stdout or '{}').get('streams') or [{}])[0]
    w, h = s.get('width'), s.get('height')
    if not w or not h:
        return None
    rot = next((abs(int(float(d['rotation']))) for d in s.get('side_data_list') or [] if 'rotation' in d), 0)
    return (int(h), int(w)) if rot % 180 == 90 else (int(w), int(h))


# ── the app ──────────────────────────────────────────────────────────────────────────────────────────────────────
def seq_js(sequence):
    """After `var seq = app.project.activeSequence`: refuse unless it is the sequence this run targets. Every call
    carries it, so a click on another timeline mid-run stops the next call instead of writing there."""
    return ('if (!seq) return "ERROR: no active sequence"; var WANT_SEQ = %s; '
            'if (WANT_SEQ !== null && seq.name !== WANT_SEQ) return "ERROR: the active sequence is " + seq.name '
            '+ ", not " + WANT_SEQ + ": nothing touched";') % json.dumps(sequence)


JS_MOTION = r"""
  function motionOf(c) { for (var i = 0; i < c.components.numItems; i++) if (c.components[i].displayName === "Motion") return c.components[i]; return null; }
  function propOf(m, n) { if (!m) return null; for (var i = 0; i < m.properties.numItems; i++) if (m.properties[i].displayName === n) return m.properties[i]; return null; }"""


def seq_es(sequence):
    return r"""(function(){ var seq = app.project.activeSequence; %s
  return JSON.stringify({name: seq.name, w: Number(seq.frameSizeHorizontal), h: Number(seq.frameSizeVertical),
                         timebase: String(seq.timebase), v1: seq.videoTracks[0].clips.numItems}); })()""" % seq_js(sequence)


def read_es(sequence, n0, n1):
    """V1 clips [n0, n1) with their Motion Position and Scale: a static value, or every key (media seconds, value)."""
    return r"""(function(){ var seq = app.project.activeSequence; %s %s
  function rd(p) { if (!p) return null; var o = {keyed: !!p.isTimeVarying()};
    if (o.keyed) { var ks = p.getKeys(), a = []; if (ks) for (var k = 0; k < ks.length; k++) a.push([ks[k].seconds, p.getValueAtKey(ks[k])]); o.keys = a; }
    else o.value = p.getValue();
    return o; }
  var v1 = seq.videoTracks[0], out = [];
  for (var i = %d; i < Math.min(%d, v1.clips.numItems); i++) { var c = v1.clips[i], m = motionOf(c);
    out.push({i: i, name: c.name, start: c.start.seconds, end: c.end.seconds, inPoint: c.inPoint.seconds,
              st: String(c.start.ticks), it: String(c.inPoint.ticks), path: c.projectItem ? c.projectItem.getMediaPath() : "",
              P: rd(propOf(m, "Position")), S: rd(propOf(m, "Scale"))}); }
  return JSON.stringify(out); })()""" % (seq_js(sequence), JS_MOTION, n0, n1)


def write_es(sequence, rows):
    """Write each row's Motion on its V1 clip. rows: [{i, st, it, scale, pos} | {i, st, it, keys}]. A clip whose start or
    in-point moved since it was read is refused (the creator is editing): the batch stops there, unsaved."""
    return r"""(function(){ var seq = app.project.activeSequence; %s %s
  var W = %s, HOLD = %d, v1 = seq.videoTracks[0], done = [];
  function clear(p) { var ks = p.getKeys(); if (ks) for (var k = ks.length - 1; k >= 0; k--) p.removeKey(ks[k], 1); }
  for (var n = 0; n < W.length; n++) { var w = W[n], c = v1.clips[w.i];
    if (!c || String(c.start.ticks) !== w.st || String(c.inPoint.ticks) !== w.it)
      return "ERROR: V1 clip " + w.i + " moved since it was read (written before it in this batch: " + (done.join(",") || "none") + ")";
    var m = motionOf(c), P = propOf(m, "Position"), S = propOf(m, "Scale");
    if (!P || !S) return "ERROR: V1 clip " + w.i + " has no Motion Position/Scale";
    var props = [P, S];
    for (var q = 0; q < 2; q++) if (props[q].isTimeVarying()) clear(props[q]);
    if (!w.keys) {
      P.setTimeVarying(false); S.setTimeVarying(false); P.setValue(w.pos, 1); S.setValue(w.scale, 1);
    } else {
      P.setTimeVarying(true); S.setTimeVarying(true);
      for (var k = 0; k < w.keys.length; k++) { var t = w.keys[k][0];
        P.addKey(t); P.setValueAtKey(t, w.keys[k][2], 1); S.addKey(t); S.setValueAtKey(t, w.keys[k][1], 1); }
      for (var q2 = 0; q2 < 2; q2++) { var ks = props[q2].getKeys();
        // a key the stopwatch made on its own (at the playhead) is not one of the plan's: drop it
        if (ks) for (var j = ks.length - 1; j >= 0; j--) { var mine = false;
          for (var x = 0; x < w.keys.length; x++) if (Math.abs(ks[j].seconds - w.keys[x][0]) < 1e-4) mine = true;
          if (!mine) props[q2].removeKey(ks[j], 1); }
        ks = props[q2].getKeys();
        if (ks) for (var j2 = 0; j2 < ks.length; j2++) { try { props[q2].setInterpolationTypeAtKey(ks[j2], HOLD, 1); } catch (e) {} } }
    }
    done.push(w.i); }
  return JSON.stringify(done); })()""" % (seq_js(sequence), JS_MOTION, json.dumps(rows), HOLD)


def audio_es(sequence, n0, n1):
    """Every clip on every audio track (track, start, end, in-point in ticks, path, name), the track count first."""
    return r"""(function(){ var seq = app.project.activeSequence; %s
  var N0 = %d, N1 = %d, n = 0, out = [];
  if (n++ >= N0) out.push({tracks: seq.audioTracks.numTracks});
  for (var t = 0; t < seq.audioTracks.numTracks; t++) { var tr = seq.audioTracks[t];
    for (var i = 0; i < tr.clips.numItems; i++) {
      if (n++ < N0) continue;
      if (out.length >= N1 - N0) return JSON.stringify(out);
      var c = tr.clips[i];
      out.push({track: t, name: c.name, start: String(c.start.ticks), end: String(c.end.ticks), inPoint: String(c.inPoint.ticks),
                path: c.projectItem ? c.projectItem.getMediaPath() : ""}); } }
  return JSON.stringify(out); })()""" % (seq_js(sequence), n0, n1)


def read_v1(sequence):
    return paged(lambda n0, n1: read_es(sequence, n0, n1), size=PAGE)


def audio_snapshot(sequence):
    return paged(lambda n0, n1: audio_es(sequence, n0, n1), size=40)


def save():
    r = subprocess.run(['node', str(BRIDGE), 'save_project'], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'✗ save_project failed: {(r.stderr or r.stdout).strip()}')


def backup(prproj, job):
    """Save, then copy the saved .prproj to premiere/archive/<name>.pre-layout-keys-<stamp>.prproj: the rollback."""
    save()
    arch = job_root(job) / 'premiere' / 'archive'
    arch.mkdir(parents=True, exist_ok=True)
    stem = f"{Path(prproj).stem}.pre-layout-keys-{time.strftime('%Y%m%d-%H%M%S')}"
    dst, n = arch / f'{stem}.prproj', 1
    while dst.exists():      # two runs in one second (an organic pass, then its variant): never overwrite a rollback
        n += 1
        dst = arch / f'{stem}-{n}.prproj'
    shutil.copy2(prproj, dst)
    return dst


# ── runs ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def modes_line(modes, seq=None, src=None):
    return '  modes  ' + ' · '.join(f"{k} {describe(to_motion(modes[k], seq, src))}" for k in ('S', 'T', 'W'))


def dry(job, variant):
    plan, spans, modes, fps = load_inputs(job, variant)
    tag = f'.{variant}' if variant else ''
    cp = Path(job) / 'transcript' / f'cuts{tag}.json'
    cp = cp if cp.exists() else Path(job) / 'transcript' / 'cuts.json'
    try:
        cuts = _json(str(cp), 'transcript/cuts.json')
    except layout.MissingInput as e:
        refuse(f'✗ missing input: {e}')
    clips = edl_clips(cuts, fps)
    rows = plan_keys(clips, spans, modes, fps)
    print(f"layout-keys --dry · {Path(job).name}{' · variant ' + variant if variant else ''} · {len(clips)} V1 clips off "
          f"transcript/{cp.name} · {fps:.3f} fps · the sequence at the source's size (--apply reads the live V1 and sizes)")
    print(modes_line(modes))
    pairs, static = 0, {}
    for c, r in zip(clips, rows):
        if not r['switches']:
            static[r['modes'][0]] = static.get(r['modes'][0], 0) + 1
            continue
        for t, o, n in r['switches']:
            kt = r['in'] + (t - r['start'])
            pairs += 1
            print(f"  #{r['i']:<3} {t:9.3f}  {o}>{n}  hold keys at media {kt - 1.0 / fps:.6f} ({o}) · {kt:.6f} ({n})"
                  + ('  [substituted media: its own clock; --verify it before --apply]' if c.get('media') else ''))
    keyed = sum(1 for r in rows if r['switches'])
    print(f"{pairs} key pair(s) on {keyed} clip(s) · {len(rows) - keyed} clip(s) static ("
          + ' · '.join(f'{k} {static[k]}' for k in ('S', 'T', 'W') if k in static) + ')')
    return 0


class Live:
    """One --verify or --apply run against the active sequence."""

    def __init__(self, job, variant=None, sequence=None):
        self.job, self.variant = Path(job).resolve(), variant
        self.sequence = sequence or os.environ.get('VE_SEQUENCE') or None
        if variant:
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', variant):
                refuse(f'--variant {variant!r}: letters, digits, - and _ only (it becomes part of a file name)')
            if not self.sequence:
                refuse(f'--variant {variant} keys a second sequence: name it with --sequence "<name>" (or VE_SEQUENCE), '
                       'nothing touched')
            if self.sequence == job_root(self.job).name:
                refuse(f'--variant {variant} names {self.sequence}, the job-named ORGANIC sequence: its layout would be '
                       'keyed with the variant\'s. Nothing touched. Name the variant sequence with --sequence.')
        self.plan, self.spans, self.modes, self.fps_plan = load_inputs(str(self.job), variant)
        self.rec_path = job_root(self.job) / 'premiere' / f"layout-keys{'.' + variant if variant else ''}.json"

    def read(self):
        """Guard, then every read this run needs: the sequence, V1, source sizes, the keys and each clip's class."""
        if self.sequence:
            os.environ['VE_SEQUENCE'] = self.sequence   # job_guard's sequence rule reads the requested name from here
        self.prproj = require_job_project(es, self.job, sequence=self.sequence)
        self.info = json.loads(es(seq_es(self.sequence)))
        self.F = int(float(self.info['timebase'])) / TPS
        fps = 1.0 / self.F
        if abs(fps - self.fps_plan) > 1e-3 * fps:
            refuse(f"✗ the plan is on a {self.fps_plan:.3f} fps grid and {self.info['name']} runs at {fps:.3f}: every switch "
                   'would land off the frame grid. Nothing touched. Fix the plan\'s `fps`.')
        self.seq = (int(self.info['w']), int(self.info['h']))
        self.clips = read_v1(self.sequence)
        sizes = {p: (src_size(p) if p else None) for p in {c['path'] for c in self.clips}}
        bad = sorted(f"#{c['i']} {c['path'] or c['name']}" for c in self.clips if not sizes[c['path']])
        if bad:
            refuse('✗ no source size for V1 clip(s) ' + ', '.join(bad) + ': their media is not readable by ffprobe. Nothing touched.')
        for c in self.clips:
            c['in'], c['src'] = c['inPoint'], sizes[c['path']]
        try:
            self.targets = plan_keys(self.clips, self.spans, self.modes, fps, seq=self.seq)
        except ValueError as e:
            refuse(f'✗ {e}. Nothing touched.')
        records = records_for(self.job, self.variant)
        self.live, self.cls = [], []
        for c, t in zip(self.clips, self.targets):
            lv = live_motion(c)
            self.live.append(lv)
            self.cls.append(classify(lv, t['motion'], recorded(records, c)))
        print(f"layout-keys · {self.job.name}{' · variant ' + self.variant if self.variant else ''} · {self.info['name']} · "
              f"{len(self.clips)} V1 clips · {fps:.3f} fps · {self.seq[0]}x{self.seq[1]}")

    def line(self, k, mark, note=''):
        c, t = self.clips[k], self.targets[k]
        want = '>'.join(t['modes'])
        return f"  {mark} #{c['i']:<3} {c['start']:.3f}-{c['end']:<8.3f} {want:<7} {note}"

    def names(self, k):
        """[(mode, its Motion on V1 clip k)]: what describe() labels a key with."""
        return [(m, to_motion(self.modes[m], self.seq, self.clips[k]['src'])) for m in ('S', 'T', 'W')]

    def desc(self, k, m):
        return describe(m, self.names(k))

    def hand_note(self, k):
        vocab = ' (every value is one of this job\'s modes: an older framing pass? read it, then --force-clip it)' \
            if in_vocab(self.live[k], [v for _, v in self.names(k)]) else ''
        return f"HAND, his: {self.desc(k, self.live[k])}{vocab}"

    def verify(self):
        self.read()
        n = {'MATCH': 0, 'DRIFT': 0, 'HAND': 0}
        for k, cl in enumerate(self.cls):
            n[cl] += 1
            if cl == 'MATCH':
                print(self.line(k, '✓', self.desc(k, self.targets[k]['motion'])))
            elif cl == 'DRIFT':
                print(self.line(k, '✗', f"DRIFT: live {self.desc(k, self.live[k])}, the plan "
                                        f"{self.desc(k, self.targets[k]['motion'])} (re-run --apply)"))
            else:
                print(self.line(k, '⚠', self.hand_note(k)))
        sec = mode_seconds(self.spans)
        tot = sum(sec.values()) or 1.0
        print('  seconds per mode  ' + ' · '.join(f'{m} {sec[m]:.2f} s ({100 * sec[m] / tot:.1f} %)'
                                                   for m in ('S', 'T', 'W', 'O', 'F') if m in sec))
        print(f"{len(self.clips)} clips: {n['MATCH']} MATCH · {n['DRIFT']} DRIFT · {n['HAND']} HAND"
              + (' (HAND is the creator\'s: named, never an exit)' if n['HAND'] else ''))
        return 1 if n['DRIFT'] else 0

    def apply(self, force=()):
        self.read()
        idx = {c['i']: k for k, c in enumerate(self.clips)}
        unknown = [f for f in force if f not in idx]
        if unknown:
            refuse(f"✗ --force-clip {','.join(map(str, unknown))}: V1 has clips #0-#{len(self.clips) - 1}. Nothing touched.")
        todo = []
        for k, cl in enumerate(self.cls):
            forced = self.clips[k]['i'] in force
            if cl == 'MATCH':
                continue
            if cl == 'HAND' and not forced:
                print(self.line(k, '⚠', self.hand_note(k) + f" · skipped (--force-clip {self.clips[k]['i']} overwrites it)"))
                continue
            todo.append(k)
            print(self.line(k, '↻', f"{self.desc(k, self.live[k])} -> {self.desc(k, self.targets[k]['motion'])}"
                                    + (' (FORCED over a hand edit)' if cl == 'HAND' else '')))
        if todo:
            self.write(todo)
        else:
            print('  nothing to write: no save, no backup')
        self.record([k for k, cl in enumerate(self.cls) if cl == 'MATCH'] + todo)
        n_hand = sum(1 for k, cl in enumerate(self.cls) if cl == 'HAND' and k not in todo)
        print(f"{len(self.clips)} clips: {self.cls.count('MATCH')} already at the plan · {len(todo)} written · "
              f"{n_hand} HAND skipped · record {self.rec_path.relative_to(job_root(self.job))}")
        return 0

    def write(self, todo):
        bak = backup(self.prproj, self.job)
        print(f'  backup {bak.relative_to(job_root(self.job))}')
        audio0 = audio_snapshot(self.sequence)
        rows = []
        for k in todo:
            c, m = self.clips[k], self.targets[k]['motion']
            row = {'i': c['i'], 'st': c['st'], 'it': c['it']}
            row.update({'keys': m['keys']} if 'keys' in m else {'scale': m['scale'], 'pos': m['pos']})
            rows.append(row)
        done = []
        for b in range(0, len(rows), BATCH):
            try:
                done += json.loads(es(write_es(self.sequence, rows[b:b + BATCH]), timeout=120000))
            except SystemExit as e:
                print(f"✗ STOPPED writing ({e}). {len(done)} clip(s) written before this batch: "
                      f"{','.join(map(str, done)) or 'none'}. The project was NOT saved: close it without saving to undo, "
                      f"or restore {bak.name}.")
                raise
        after = read_v1(self.sequence)
        wrong = []
        if [(c['st'], c['it']) for c in after] != [(c['st'], c['it']) for c in self.clips]:
            wrong.append(f'V1 changed under the run: {len(self.clips)} clips read, {len(after)} now, or their edges moved')
        else:
            for k, c in enumerate(after):
                if k in todo and not same(live_motion(c), self.targets[k]['motion']):
                    wrong.append(f"#{c['i']}: wrote {self.desc(k, self.targets[k]['motion'])}, reads back "
                                 f"{self.desc(k, live_motion(c))}")
                elif k not in todo and not unchanged(self.clips[k], c):
                    wrong.append(f"#{c['i']}: not written, but now reads {self.desc(k, live_motion(c))} "
                                 f"(was {self.desc(k, self.live[k])}): edited during the run?")
        if wrong:
            for w in wrong:
                print('  ✗ ' + w)
            sys.exit(f'✗ READBACK MISMATCH on {len(wrong)} clip(s). The project was NOT saved: close it without saving to '
                     f'undo, or restore {bak.name}.')
        diff = audio_diff(audio0, audio_snapshot(self.sequence))
        if diff:
            for d in diff:
                print('  ' + d)
            sys.exit(f'✗ AUDIO CHANGED during the run ({len(diff)} difference(s) above). This tool never writes audio: the '
                     'timeline was edited during the run. The project was NOT saved: close it without saving to undo, or '
                     'put the audio right and save by hand.')
        save()
        print(f"  ✓ {len(todo)} clip(s) written and read back · audio IDENTICAL ({len(audio0)} rows) · saved")

    def record(self, ks):
        """premiere/layout-keys[.<variant>].json: what this tool's keys are, per clip, now. The next run reads a clip
        that still equals its entry as the tool's own state, and anything else as the creator's."""
        rec = {'tool': 'lanes/premiere/layout-keys.py', 'variant': self.variant, 'sequence': self.info['name'],
               'written': time.strftime('%Y-%m-%dT%H:%M:%S'), 'fps': round(1.0 / self.F, 6), 'sequence_size': list(self.seq),
               'modes': self.modes,
               'clips': [{'i': self.clips[k]['i'], 'path': self.clips[k]['path'], 'start': self.clips[k]['start'],
                          'end': self.clips[k]['end'], 'in': self.clips[k]['in'], 'motion': self.targets[k]['motion']}
                         for k in sorted(ks)]}
        self.rec_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.rec_path, 'w', encoding="utf-8") as fp:
            json.dump(rec, fp, indent=1)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job', help='projects/<job>')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--dry', action='store_true', help='the keys it would write, off the EDL (the default)')
    g.add_argument('--apply', action='store_true', help='write the keys onto V1, read back, prove the audio, save')
    g.add_argument('--verify', action='store_true', help='read V1 back: MATCH / DRIFT / HAND (exit 1 on DRIFT)')
    ap.add_argument('--variant', metavar='NAME', help="the plan's variants.NAME composed in (a second deliverable)")
    ap.add_argument('--sequence', metavar='NAME', help='refuse unless the active sequence is NAME (env VE_SEQUENCE works too)')
    ap.add_argument('--force-clip', metavar='N[,N]', action='append', default=[],
                    help='--apply only: overwrite these V1 clips (0-based, as printed) although they read HAND')
    a = ap.parse_args(argv)
    try:
        force = sorted({int(x) for f in a.force_clip for x in f.split(',') if x.strip()})
    except ValueError:
        refuse(f"--force-clip {','.join(a.force_clip)}: clip numbers, 0-based as printed (e.g. 21 or 21,22)")
    if force and not a.apply:
        refuse('--force-clip only means something with --apply')
    if not os.path.isdir(a.job):
        refuse(f'✗ no job folder at {a.job}')
    if a.apply:
        return Live(a.job, a.variant, a.sequence).apply(force)
    if a.verify:
        return Live(a.job, a.variant, a.sequence).verify()
    return dry(a.job, a.variant)


if __name__ == '__main__':
    sys.exit(main())
