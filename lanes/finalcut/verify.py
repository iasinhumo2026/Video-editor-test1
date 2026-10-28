#!/usr/bin/env python3
"""verify.py: prove the LIVE Final Cut project matches the FCPXML it was built from, clip by clip.

  uv run lanes/finalcut/verify.py <built.fcpxml> [--project "<name>"] [--live <exported.fcpxml>]

Without --live it asks SpliceKit's bridge (fcpxml.export) to write the ACTIVE project's FCPXML to a temp file; open the
project first (sk.py project.open). Both files are flattened to one row per clip, keyed by lane and timeline start
(a connected clip's timeline time = parent offset + (its offset - parent start)), and compared on: media, source in,
duration, a spine clip's split-edit audio range, the transform (position / scale and their keys), the volume (static, keys, fade), the video filters by name, their keyed params and their static params (the Custom LUT's
choice among them: a dropped LUT choice is otherwise silent). Media compares as the resolved file path, so a file://
URL and a plain path, or a symlinked folder, name the same file.
FCP rewrites some values on import (a keyframe time onto its own timebase, a fraction reduced), so times compare
within 1 audio sample and numbers within 1e-3.

Exit: 0 identical · 1 differences (each printed) · 2 could not read / export.
"""
import argparse, os, sys, tempfile
import xml.etree.ElementTree as ET
from urllib.parse import unquote
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

TOL_T = Fraction(1, 48000)


def ft(s):
    if not s:
        return Fraction(0)
    s = s.rstrip('s')
    return Fraction(s) if '/' not in s else Fraction(int(s.split('/')[0]), int(s.split('/')[1]))


def flatten(path):
    root = ET.parse(path).getroot()
    assets = {}
    for a in root.iter('asset'):
        u = unquote(a.find('media-rep').get('src'))
        assets[a.get('id')] = os.path.realpath(u[7:] if u.startswith('file://') else u)
    effects = {e.get('id'): e.get('name') for e in root.iter('effect')}
    rows = []

    def params(el):
        out = {}
        tr = el.find('adjust-transform')
        if tr is not None:
            out['position'] = tr.get('position', '0 0')
            out['scale'] = tr.get('scale', '1 1')
            for p in tr.findall('param'):
                out[f'keys.{p.get("name")}'] = [(ft(k.get('time')), k.get('value')) for k in p.iter('keyframe')]
        vol = el.find('adjust-volume')
        if vol is not None:
            out['volume'] = vol.get('amount', '0dB')
            p = vol.find('param')
            if p is not None:
                out['volume.keys'] = [(ft(k.get('time')), k.get('value')) for k in p.iter('keyframe')]
                fo = p.find('fadeOut')
                if fo is not None:
                    out['fadeOut'] = ft(fo.get('duration'))
        out['filters'] = [effects.get(f.get('ref'), f.get('name')) for f in el.findall('filter-video')]
        fk = [(effects.get(f.get('ref'), f.get('name')), q.get('name'), [(ft(k.get('time')), k.get('value')) for k in q.iter('keyframe')])
              for f in el.findall('filter-video') for q in f.findall('param') if q.find('keyframeAnimation') is not None]
        if fk:
            out['filters.keys'] = fk
        fp = [(effects.get(f.get('ref'), f.get('name')), q.get('name'), q.get('value'))
              for f in el.findall('filter-video') for q in f.findall('param') if q.find('keyframeAnimation') is None]
        if fp:
            out['filters.params'] = fp
        return out

    for spine in root.iter('spine'):
        for p in spine:
            if p.tag not in ('asset-clip', 'gap', 'clip'):
                continue
            po, ps = ft(p.get('offset')), ft(p.get('start'))
            if p.tag == 'asset-clip':
                rows.append(dict(lane=0, t=po, media=assets[p.get('ref')], src=ps, dur=ft(p.get('duration')),
                                 audio_src=ft(p.get('audioStart')) if p.get('audioStart') else ps,
                                 audio_dur=ft(p.get('audioDuration')) if p.get('audioDuration') else ft(p.get('duration')),
                                 **params(p)))
            for c in p.findall('asset-clip'):
                rows.append(dict(lane=int(c.get('lane', 0)), t=po + ft(c.get('offset')) - ps, media=assets[c.get('ref')],
                                 src=ft(c.get('start')), dur=ft(c.get('duration')), **params(c)))
        break
    return sorted(rows, key=lambda r: (r['lane'], r['t']))


def near(a, b):
    if isinstance(a, Fraction) and isinstance(b, Fraction):
        return abs(a - b) <= TOL_T
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(near(x, y) for x, y in zip(a, b))
    if isinstance(a, tuple) and isinstance(b, tuple):
        return all(near(x, y) for x, y in zip(a, b))
    if isinstance(a, str) and isinstance(b, str):
        try:
            fa = [float(x.rstrip('dB')) for x in a.split()]
            fb = [float(x.rstrip('dB')) for x in b.split()]
            return len(fa) == len(fb) and all(abs(x - y) < 1e-3 for x, y in zip(fa, fb))
        except ValueError:
            return a == b
    return a == b


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('built')
    ap.add_argument('--live')
    a = ap.parse_args()
    live = a.live
    if not live:
        from sk import call
        live = os.path.join(tempfile.mkdtemp(), 'live.fcpxml')
        try:
            call('fcpxml.export', {'path': live})
        except Exception as ex:
            print(f'✗ export failed: {ex}', file=sys.stderr)
            return 2
    want, got = flatten(a.built), flatten(live)
    keyed = lambda rows: {(r['lane'], r['t']): r for r in rows}
    W, G = keyed(want), keyed(got)
    # match within one sample on the timeline start
    diffs, used = [], set()
    for k, r in W.items():
        m = next((g for gk, g in G.items() if gk[0] == k[0] and abs(gk[1] - k[1]) <= TOL_T and gk not in used), None)
        if m is None:
            diffs.append(f'MISSING lane {k[0]} at {float(k[1]):.4f}s {os.path.basename(r["media"])}')
            continue
        used.add((m['lane'], m['t']))
        for f in sorted(set(r) | set(m)):
            if f in ('lane', 't'):
                continue
            if not near(r.get(f), m.get(f)):
                diffs.append(f'lane {k[0]} at {float(k[1]):.4f}s {os.path.basename(r["media"])}: {f} built={r.get(f)} live={m.get(f)}')
    for gk, g in G.items():
        if gk not in used:
            diffs.append(f'EXTRA lane {gk[0]} at {float(gk[1]):.4f}s {os.path.basename(g["media"])}')
    lanes = {}
    for r in want:
        lanes[r['lane']] = lanes.get(r['lane'], 0) + 1
    if diffs:
        for d in diffs:
            print('✗', d)
        print(f'✗ {len(diffs)} difference(s) over {len(want)} built clips')
        return 1
    print(f'✓ live project == built FCPXML: {len(want)} clips, per lane {dict(sorted(lanes.items()))}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
