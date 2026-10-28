#!/usr/bin/env python3
"""port-premiere.py: rebuild a finished Premiere sequence as a Final Cut project (FCPXML), every clip still a real edit.

  uv run lanes/finalcut/prproj-read.py <job>/premiere/<job>.prproj --sequence "<name>" --out timeline.json
  uv run lanes/finalcut/port-premiere.py timeline.json --out <fcp-job>/finalcut/<name>.fcpxml \
      --library <fcp-job>/finalcut/<name>.fcpbundle [--media-map old=new ...] [--grade-track V2] [--music-track A5]
      [--width W --height H]
  then import it: uv run lanes/finalcut/import.py <that .fcpxml>

The Final Cut project takes the Premiere sequence's frame size, except that a portrait sequence (a 2160x3840 short)
becomes 1080x1920, the deliverable's; --width/--height override both.

What carries over, per track (the lane's step numbers):
  V1   the footage, one spine clip per Premiere clip, video only; Motion Position/Scale as FCP adjust-transform, keyed
       where Premiere keyed it (the layout keys are 1-frame pairs, so linear keys reproduce the holds exactly)
  V2   a Lumetri adjustment layer is NOT a clip in Final Cut: every V1 clip it covers gets the house Custom LUT instead
       (--grade-track; the look is the folded cube, lanes/finalcut/README.md § Step 4). Footage graded, graphics not.
  V3+  graphics, patches, captions: connected clips on lanes 1.. above, their Motion converted the same way
  A1   dialogue, carried ON its V1 clip (FCP ignores srcEnable on import), a J/L cut as a split edit; point
       --media-map at the audio-normalized copies (§ Step 3), which carry the identical picture
  A2+  SFX and music: lanes -2.., Premiere clip Volume Level -> dB (Premiere stores 0 dB as 0.17782794, so
       dB = 20*log10(v) + 15), a keyed Level (the music's tail) as volume keyframes; a one-sided audio transition
       becomes the clip's fade (a both-sided crossfade is reported, not built)

Units: Premiere Position is normalised to the SEQUENCE frame, FCPXML position is percent of the FCP frame height from
the centre, +y up; FCP first fits each media into the frame, so scale_fcp = premiere% / 100 * (fcp_w / seq_w) / fit.
Exit: 0 written · 2 bad input.
"""
import argparse, json, math, os, sys
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fcpxml_writer import Timeline, probe  # noqa: E402

TPS = 254016000000
HERE = Path(__file__).resolve().parent
LUT_UID = 'FxPlug:14B39AEF-607D-42DF-98DD-DB3DD345E925'   # Final Cut's Custom LUT


def sec(x):
    return Fraction(round(x * TPS), TPS)


def motion(clip):
    m = [c for c in clip['components'] if c['match'] == 'AE.ADBE Motion']
    return m[0]['params'] if m else {}


def level(clip):
    for c in clip['components']:
        if 'Level' in c['params']:
            return c['params']['Level']
    return None


def to_db(v):
    return -96.0 if v <= 0 else max(-96.0, 20 * math.log10(v) + 15)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('timeline')
    ap.add_argument('--out', required=True)
    ap.add_argument('--library', required=True)
    ap.add_argument('--name', help='project name (default: the sequence name)')
    ap.add_argument('--width', type=int, help='the Final Cut frame (default: the sequence\'s; portrait: 1080x1920)')
    ap.add_argument('--height', type=int)
    ap.add_argument('--media-map', nargs='*', default=[], help='old_path=new_path, e.g. a raw -> its audio-normalized copy')
    ap.add_argument('--audio-media-map', nargs='*', default=[], help='like --media-map, for audio tracks only')
    ap.add_argument('--grade-track', default='V2')
    ap.add_argument('--music-track', default='A5')
    a = ap.parse_args()

    tl = json.load(open(a.timeline, encoding="utf-8"))
    SW, SH = tl['width'], tl['height']
    FW, FH = (a.width, a.height) if a.width and a.height else ((SW, SH) if SW > SH else (1080, 1920))
    k = FW / SW
    vmap = dict(x.split('=', 1) for x in a.media_map)
    amap = dict(vmap, **dict(x.split('=', 1) for x in a.audio_media_map))
    name = a.name or tl['sequence']
    T = Timeline(name, FW, FH, event=name)
    dims = {}

    def fit(media):
        if media not in dims:
            p = probe(media)
            dims[media] = p['display']        # the size Premiere and Final Cut SHOW: a rotated phone raw's turned one
        mw, mh = dims[media]
        return min(FW / mw, FH / mh)

    def pos_fcp(p):
        return ((p[0] - 0.5) * SW * k / FH * 100, -(p[1] - 0.5) * SH * k / FH * 100)

    def xform(item, clip, media):
        pr = motion(clip)
        if not pr:
            return
        f = fit(media)
        sc = lambda s: (s / 100 * k / f, s / 100 * k / f)
        pos, scale = pr.get('Position', {}), pr.get('Scale', {})
        keys = {}
        if pos.get('keys'):
            keys['position'] = [(sec(t), pos_fcp(v)) for t, v in pos['keys']]
        elif isinstance(pos.get('value'), list):
            item['position'] = pos_fcp(pos['value'])
        if scale.get('keys'):
            keys['scale'] = [(sec(t), sc(v)) for t, v in scale['keys']]
        elif isinstance(scale.get('value'), (int, float)):
            item['scale'] = sc(scale['value'])
        if keys:
            item['keys'] = keys
        if item.get('position') and max(abs(x) for x in item['position']) < 1e-9:
            del item['position']
        if item.get('scale') and max(abs(x - 1) for x in item['scale']) < 1e-9:
            del item['scale']

    grade = [(Fraction(c['start_ticks'], TPS), Fraction(c['end_ticks'], TPS))
             for c in tl['tracks'].get(a.grade_track, {}).get('clips', [])
             if any(x['match'] == 'AE.ADBE Lumetri' for x in c['components'])]
    notes = []
    for tr, body in sorted(tl['tracks'].items(), key=lambda kv: (kv[0][0] != 'V', int(kv[0][1:]))):
        if tr == a.grade_track and grade:
            continue
        if body['muted']:
            notes.append(f'{tr} is muted in Premiere: ported as-is (unmute/mute by hand)')
        for c in body['clips']:
            if c['disabled']:
                notes.append(f'{tr} {c["start"]:.3f}: a DISABLED clip, skipped')
                continue
            if abs(c['speed'] - 1) > 1e-9:
                notes.append(f'{tr} {c["start"]:.3f}: speed {c["speed"]} is NOT ported')
            media = (vmap if tr[0] == 'V' else amap).get(c['media'], c['media'])
            if not os.path.exists(media):
                print(f'✗ {tr} {c["start"]:.3f}: media missing: {media}', file=sys.stderr)
                return 2
            s, e, i = (Fraction(c[x], TPS) for x in ('start_ticks', 'end_ticks', 'in_ticks'))
            item = {'track': tr, 'media': media, 'start': s, 'dur': e - s, 'src_in': i,
                    'name': os.path.splitext(os.path.basename(c['media']))[0]}
            if tr[0] == 'V':
                xform(item, c, media)
                if tr == 'V1' and grade:
                    cover = sum(max(Fraction(0), min(e, ge) - max(s, gs)) for gs, ge in grade)
                    if cover > 0:
                        item['filters'] = ['Custom LUT']
                        if cover < e - s:
                            notes.append(f'V1 {c["start"]:.3f}: only partly under the grade layer; graded whole')
            else:
                item['role'] = 'dialogue' if tr == 'A1' else ('music' if tr == a.music_track else 'effects')
                lv = level(c)
                if lv:
                    if lv.get('keys'):
                        item['volume_keys'] = [(sec(t), to_db(v)) for t, v in lv['keys']]
                    elif isinstance(lv.get('value'), (int, float)):
                        item['volume_db'] = to_db(lv['value'])
                for x in body['transitions']:
                    xs, xe = Fraction(x['start_ticks'], TPS), Fraction(x['end_ticks'], TPS)
                    if x['outgoing'] and not x['incoming'] and xe == e:
                        item['fade_out'] = xe - xs
                    elif x['incoming'] and not x['outgoing'] and xs == s:
                        notes.append(f'{tr} {c["start"]:.3f}: an incoming-only transition, NOT ported')
                    elif x['incoming'] and x['outgoing'] and xs < e <= xe:
                        notes.append(f'{tr} {x["start"]:.3f}: a two-sided crossfade, NOT ported')
            T.add(**item)
    tmpl = (HERE / 'templates' / 'house-lut-filter.xml').read_text(encoding="utf-8")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    r = T.write(a.out, a.library, effects={'Custom LUT': (LUT_UID, tmpl)} if grade else {})
    n = {}
    for it in T.items:
        n[it['track']] = n.get(it['track'], 0) + 1
    print(f'✓ {a.out}: {r["assets"]} assets · clips per track {n} · {r["duration"]:.3f} s · library {a.library}')
    for x in notes + r['warnings']:
        print(f'  ⚠ {x}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
