#!/usr/bin/env python3
"""prproj-read.py: read one sequence out of a SAVED Premiere project, offline (Premiere may be closed).

  uv run lanes/finalcut/prproj-read.py <project.prproj> --sequence "<name>" [--out timeline.json]

What a lane port needs from a finished Premiere timeline, as plain JSON: the sequence's frame rate and frame size, then
per track (V1.., A1..) every clip in timeline order with start / end / in (ticks and seconds), the DERIVED source out
(in + (end - start), the same rule as timeline-dump.py), speed, disabled, the media path, and every component with its
params: the current value, or, when the param is time-varying, its keys as [media-time seconds, value]. A key's time is
the clip's MEDIA time, so its timeline time is start + (key - in). Audio transitions come out per track as well.

The .prproj is gzipped XML whose objects point at each other by ObjectID / ObjectUID; this walks
Sequence > TrackGroup > Track > TrackItem > SubClip > Clip > MediaSource > Media, and TrackItem > ComponentChain >
Component > Param. Nothing is written back and the project is never opened in Premiere.

Values are passed through as Premiere stores them: Position is normalised (x:y, 0..1 of the frame), Scale a percent,
an audio Level a LINEAR gain (dB = 20*log10(v) + 15 on a clip Volume, read from the Resolve lane test, 2026-09-25).

Exit: 0 written · 2 the project or the sequence could not be read (missing, ambiguous).
"""
import argparse, gzip, json, sys
import xml.etree.ElementTree as ET
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

TPS = 254016000000


def load(path):
    raw = Path(path).read_bytes()
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    root = ET.fromstring(raw)
    ids = {}
    for c in root:
        k = c.get('ObjectID') or c.get('ObjectUID')
        if k:
            ids[k] = c
    return root, ids


def ref(ids, e):
    if e is None:
        return None
    return ids.get(e.get('ObjectRef') or e.get('ObjectURef'))


def num(s, default=None):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def parse_value(s):
    """'0.5:0.727' -> [0.5, 0.727]; '100.' -> 100.0; anything else is kept as text."""
    if s is None:
        return None
    if ':' in s:
        parts = [num(x) for x in s.split(':')]
        if all(p is not None for p in parts):
            return parts
    v = num(s)
    return v if v is not None else s


def param(ids, p):
    q = ref(ids, p)
    if q is None:
        return None, None
    name = q.findtext('Name') or ''
    out = {}
    keys = q.findtext('Keyframes')
    if keys and keys.strip():
        out['keys'] = []
        for k in keys.strip().strip(';').split(';'):
            f = k.split(',')
            if len(f) >= 2:
                out['keys'].append([int(f[0]) / TPS, parse_value(f[1])])
    start = q.findtext('StartKeyframe')
    if start:
        f = start.split(',')
        if len(f) >= 2:
            out['value'] = parse_value(f[1])
    cur = q.findtext('CurrentValue')
    if cur is not None and 'value' not in out:
        out['value'] = parse_value(cur)
    return name, out


def components(ids, owner):
    comps = ref(ids, owner.find('.//ComponentOwner/Components')) if owner is not None else None
    res = []
    if comps is None:
        return res
    for c in comps.findall('.//ComponentChain/Components/Component'):
        o = ref(ids, c)
        if o is None:
            continue
        entry = {'match': o.findtext('.//MatchName') or o.tag, 'name': o.findtext('.//DisplayName') or '',
                 'disabled': (o.findtext('.//Component/Disabled') or 'false') == 'true', 'params': {}}
        for p in o.findall('.//Params/Param'):
            name, val = param(ids, p)
            if name is not None:
                key, i = name or f'#{p.get("Index")}', 2
                while key in entry['params']:
                    key, i = f'{name} ({i})', i + 1
                entry['params'][key] = val
        res.append(entry)
    return res


def item(ids, ti):
    o = ref(ids, ti)
    if o is None:
        return None
    if o.tag.endswith('TransitionTrackItem'):
        t = o.find('.//TransitionTrackItem')
        s = int(t.findtext('TrackItem/Start') or 0)
        e = int(t.findtext('TrackItem/End') or 0)
        return {'kind': 'transition', 'name': t.findtext('DisplayName'), 'match': t.findtext('MatchName'),
                'start': s / TPS, 'end': e / TPS, 'start_ticks': s, 'end_ticks': e,
                'outgoing': t.findtext('HasOutgoingClip') == 'true', 'incoming': t.findtext('HasIncomingClip') == 'true'}
    cti = o.find('ClipTrackItem')
    s = int(cti.findtext('TrackItem/Start') or 0)
    e = int(cti.findtext('TrackItem/End') or 0)
    sub = ref(ids, cti.find('SubClip'))
    clip = ref(ids, sub.find('Clip')) if sub is not None else None
    c = clip.find('Clip') if clip is not None else None
    inp = int(c.findtext('InPoint') or 0) if c is not None else 0
    media = None
    if c is not None:
        src = ref(ids, c.find('Source'))
        m = ref(ids, src.find('.//Media')) if src is not None else None
        if m is not None:
            media = m.findtext('ActualMediaFilePath') or m.findtext('FilePath')
    speed = num(c.findtext('PlaybackSpeed'), 1.0) if c is not None else 1.0
    return {'kind': 'clip', 'name': sub.findtext('Name') if sub is not None else None, 'media': media,
            'start': s / TPS, 'end': e / TPS, 'in': inp / TPS, 'out': (inp + (e - s)) / TPS,
            'start_ticks': s, 'end_ticks': e, 'in_ticks': inp, 'speed': speed,
            'disabled': (cti.findtext('TrackItem/Disabled') or c.findtext('Disabled') if c is not None else 'false') == 'true',
            'components': components(ids, cti)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('project')
    ap.add_argument('--sequence', required=True)
    ap.add_argument('--out')
    a = ap.parse_args()
    try:
        root, ids = load(a.project)
    except Exception as ex:
        print(f'✗ cannot read {a.project}: {ex}', file=sys.stderr)
        return 2
    hits = [s for s in root.findall('Sequence') if s.findtext('Name') == a.sequence]
    if len(hits) != 1:
        names = [s.findtext('Name') for s in root.findall('Sequence')]
        print(f'✗ sequence "{a.sequence}": {len(hits)} matches; the project has {names}', file=sys.stderr)
        return 2
    seq = hits[0]
    out = {'project': str(Path(a.project).resolve()), 'sequence': a.sequence, 'tracks': {}}
    for g in seq.find('TrackGroups'):
        grp = ref(ids, g.find('Second'))
        if grp is None:
            continue
        prefix = {'VideoTrackGroup': 'V', 'AudioTrackGroup': 'A'}.get(grp.tag)
        if not prefix:
            continue
        tg = grp.find('TrackGroup')
        rate = int(tg.findtext('FrameRate') or 0)
        if prefix == 'V':
            out['frame_ticks'] = rate
            out['fps'] = TPS / rate if rate else None
            fr = grp.findtext('FrameRect')
            if fr:
                x0, y0, x1, y1 = (int(v) for v in fr.split(','))
                out['width'], out['height'] = x1 - x0, y1 - y0
        for t in tg.findall('Tracks/Track'):
            tr = ref(ids, t)
            if tr is None:
                continue
            name = f'{prefix}{int(t.get("Index")) + 1}'
            items = [item(ids, ti) for ti in tr.findall('.//ClipItems/TrackItems/TrackItem')]
            trans = [item(ids, ti) for ti in tr.findall('.//TransitionItems/TrackItems/TrackItem')]
            muted = (tr.findtext('.//IsMuted') or 'false') == 'true'
            out['tracks'][name] = {'muted': muted,
                                   'clips': sorted([i for i in items if i], key=lambda i: i['start_ticks']),
                                   'transitions': sorted([i for i in trans if i], key=lambda i: i['start_ticks'])}
    js = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(js, encoding="utf-8")
        n = {k: len(v['clips']) for k, v in out['tracks'].items()}
        print(f'✓ {a.sequence}: {out.get("width")}x{out.get("height")} @ {out.get("fps"):.3f} fps · clips per track {n} → {a.out}')
    else:
        print(js)
    return 0


if __name__ == '__main__':
    sys.exit(main())
