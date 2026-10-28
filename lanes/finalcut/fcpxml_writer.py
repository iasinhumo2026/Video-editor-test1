#!/usr/bin/env python3
"""fcpxml_writer.py: the Final Cut lane's ONE FCPXML emitter (a library; the CLIs are replay.py and port-premiere.py).

A timeline is described as plain items and written as FCPXML 1.14 that Final Cut 12.x imports into a NEW library with
no dialog (the `<import-options>` block names the library location; FCP creates it). Layout:

  spine        the V1 items, each carrying its paired dialogue (A1) as ONE A/V clip, a J/L cut as a split edit
               (audioStart / audioDuration); a hole becomes a <gap>
  lane +1..    every other video track (V2.. graphics, patches, captions), connected clips
  lane -1..    every other audio track (SFX, music), connected clips

Each connected clip is anchored to the spine item under its start, its offset expressed in THAT item's source time
(parent start + (t - parent offset)), so every clip stays a separate, trimmable edit.

Times are exact rationals: every input is a fraction of a second (Premiere ticks / 254016000000, or seconds) and is
written reduced, e.g. "1001/24000s". Transform units are FCPXML's: position in percent of the FRAME HEIGHT from the
centre (+y up), scale as a ratio of the media already fitted to the frame (adjust-conform "fit", the default).

Item dict (every key optional unless marked):
  media*      absolute path            start* / dur* / src_in*   Fraction seconds (timeline start, length, source in)
  track*      'V1'..'V9' / 'A1'..'A9'  name                      clip name in FCP
  position    (x, y) FCP units          scale  (sx, sy)           keys {'position': [(t, (x, y))], 'scale': [(t, (sx, sy))]}
  volume_db   float                     volume_keys [(t, dB)]     fade_out Fraction seconds (fade on the clip's tail)
  filters     [effect name]             each a key of write(effects=): {name: (uid, filter-video template with ref="{REF}")}
  filter_keys {effect name: {param: [(t, value)]}}   keyframes for a template param written as {KEYS:<param>}
Key times are SOURCE time (the clip's own media time), which is what FCPXML keyframes use inside an asset-clip. All
source times (src_in, key times) are ZERO-based, as Premiere counts them; the writer adds each file's embedded
timecode (probe()'s 'tc'), which is where FCP counts from.
"""
import json, os, re, subprocess
from fractions import Fraction
from xml.sax.saxutils import quoteattr

FRAME = Fraction(1001, 24000)


MAX_DEN = 2400000   # divisible by 24000 and 48000; FCP misreads a time whose denominator is past 32 bits


def t(v):
    """Fraction seconds -> FCPXML time string. Premiere tick times (1/254016000000 s) are rounded onto 1/2400000 s:
    FCP read "122070796932671/254016000000s" as 122070796932671 SECONDS (2026-09-25)."""
    v = Fraction(v)
    if v.denominator > MAX_DEN:
        v = Fraction(round(v * MAX_DEN), MAX_DEN)
    return '0s' if v == 0 else (f'{v.numerator}s' if v.denominator == 1 else f'{v.numerator}/{v.denominator}s')


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                          'stream=codec_type,width,height,r_frame_rate,nb_frames,sample_rate,channels'
                          ':stream_tags=timecode,rotate:stream_side_data=rotation'
                          ':format=duration:format_tags=time_reference,timecode',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next((s for s in d['streams'] if s['codec_type'] == 'video'), None)
    a = next((s for s in d['streams'] if s['codec_type'] == 'audio'), None)
    dur = Fraction(d['format']['duration'])
    info = {'video': v is not None, 'audio': a is not None}
    if v:
        n, den = (int(x) for x in v['r_frame_rate'].split('/'))
        info.update(width=int(v['width']), height=int(v['height']), frame=Fraction(den, n))
        # 'display': the size Final Cut SHOWS, which every fit and scale is a ratio of. A phone clip is stored
        # landscape with a ±90 rotation (an iPhone portrait take: coded 1920x1080, shown 1080x1920); older ffprobe
        # reports it as a `rotate` tag. width/height stay the coded size, the asset <format>'s.
        rot = next((sd['rotation'] for sd in v.get('side_data_list') or [] if 'rotation' in sd),
                   v.get('tags', {}).get('rotate', 0))
        info['display'] = (info['height'], info['width']) if round(float(rot)) % 180 else (info['width'], info['height'])
        if v.get('nb_frames', 'N/A') not in ('N/A', '0'):
            dur = int(v['nb_frames']) * Fraction(den, n)
    if a:
        info.update(channels=int(a['channels']), rate=int(a['sample_rate']))
        if not v:
            dur = Fraction(round(dur * info['rate']), info['rate'])
    info['duration'] = dur
    # The media's own start time. FCP places a file's first sample at its embedded timecode (a Broadcast-WAV
    # time_reference, a timecode track), and a clip whose start is before it is DROPPED on import without a word:
    # 50 of 103 SFX vanished that way ('Pop 1.wav' starts at 01:00:00:00, 2026-09-25). Premiere's in-points are
    # zero-based, so every source time written for this media is shifted by it.
    tags = d['format'].get('tags', {})
    tc = Fraction(0)
    if tags.get('time_reference') and a:
        tc = Fraction(int(tags['time_reference']), info['rate'])
    else:
        code = tags.get('timecode') or next((s.get('tags', {}).get('timecode') for s in d['streams'] if s.get('tags', {}).get('timecode')), None)
        if code and v:
            h, m, sec, fr = (int(x) for x in code.replace(';', ':').split(':'))
            fps = round(1 / info['frame'])
            frames = (h * 3600 + m * 60 + sec) * fps + fr
            # DROP-FRAME (a ';', 29.97/59.94: Sony, Canon and Panasonic NTSC defaults): labels 0-1 (0-3 at 59.94) are
            # skipped every minute but each tenth, so the label counts ahead of the file's own tmcd frame counter
            if ';' in code and fps in (30, 60) and 1 / info['frame'] != fps:
                mins = 60 * h + m
                frames -= 2 * fps // 30 * (mins - mins // 10)
            tc = frames * info['frame']
    info['tc'] = tc
    return info


def fmt_num(x):
    s = f'{x:.6f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


class Timeline:
    def __init__(self, name, width, height, frame=FRAME, event=None):
        self.name, self.width, self.height, self.frame = name, width, height, frame
        self.event = event or name
        self.items = []

    def add(self, **item):
        self.items.append(item)

    def write(self, path, library, effects=None, dialogue_track='A1'):
        """effects: {name: (uid, template_xml)}; an item's filters reference them by name as ('name', ...)."""
        effects = effects or {}
        res, fmt_ids, asset_ids = [], {}, {}
        rid = iter(range(1, 100000))

        def new_id():
            return f'r{next(rid)}'

        def fmt_for(w, h, frame):
            key = (w, h, frame)
            if key not in fmt_ids:
                fmt_ids[key] = new_id()
                res.append(f'<format id="{fmt_ids[key]}" frameDuration="{t(frame)}" width="{w}" height="{h}" colorSpace="1-1-1 (Rec. 709)"/>')
            return fmt_ids[key]

        seq_fmt = fmt_for(self.width, self.height, self.frame)
        infos = {}
        probe_cached = lambda m: infos[m]
        for it in self.items:
            m = it['media']
            if m in asset_ids:
                continue
            info = infos[m] = probe(m)
            aid = asset_ids[m] = new_id()
            attrs = [f'id="{aid}"', f'name={quoteattr(os.path.splitext(os.path.basename(m))[0])}', f'start="{t(info["tc"])}"',
                     f'duration="{t(info["duration"])}"']
            if info['video']:
                attrs += ['hasVideo="1"', f'format="{fmt_for(info["width"], info["height"], info["frame"])}"']
            if info['audio']:
                attrs += ['hasAudio="1"', 'audioSources="1"', f'audioChannels="{info["channels"]}"', f'audioRate="{info["rate"]}"']
            src = 'file://' + m.replace(' ', '%20').replace('&', '%26')
            res.append(f'<asset {" ".join(attrs)}>\n <media-rep kind="original-media" src={quoteattr(src)}/>\n</asset>')
        eff_ids = {}
        for name, (uid, _tmpl) in effects.items():
            eff_ids[name] = new_id()
            res.append(f'<effect id="{eff_ids[name]}" name={quoteattr(name)} uid={quoteattr(uid)}/>')

        spine = sorted([dict(i) for i in self.items if i['track'] == 'V1'], key=lambda i: i['start'])
        others = [i for i in self.items if i['track'] != 'V1']
        # FCP ignores srcEnable on import (12.3, 2026-09-25): a clip always brings every component of its media. So the
        # dialogue rides ON its V1 clip, a J/L cut written as a split edit (audioStart / audioDuration, which FCP keeps).
        # Pair = same media, same sync (source - timeline), overlapping. A V1 clip with no partner is muted (-96 dB);
        # a dialogue clip with no partner stays a connected clip below the spine (its picture hidden under V1).
        self.warnings = []
        for v in spine:
            v['audio'] = None
        for a in [i for i in others if i['track'] == dialogue_track]:
            sync = a['src_in'] - a['start']
            v = next((v for v in spine if v['audio'] is None and v['media'] == a['media']
                      and v['src_in'] - v['start'] == sync
                      and a['start'] < v['start'] + v['dur'] and v['start'] < a['start'] + a['dur']), None)
            if v is None:
                self.warnings.append(f'{dialogue_track} {float(a["start"]):.3f}s: no V1 partner, laid as a connected clip on lane -1 (its picture sits under V1)')
                continue
            v['audio'] = a
            others.remove(a)
        for v in spine:
            if v['audio'] is None and probe_cached(v['media'])['audio']:
                self.warnings.append(f'V1 {float(v["start"]):.3f}s: no {dialogue_track} partner, its own audio muted (-96 dB)')
        lanes = {}
        vtracks = sorted({i['track'] for i in others if i['track'][0] == 'V'}, key=lambda s: int(s[1:]))
        atracks = sorted({i['track'] for i in others if i['track'][0] == 'A'}, key=lambda s: int(s[1:]))
        for n, tr in enumerate(vtracks, 1):
            lanes[tr] = n
        for n, tr in enumerate(atracks, 1):
            lanes[tr] = -n

        # the spine: V1 clips, holes filled with gaps, so every connected clip has a parent under it
        end_all = max(i['start'] + i['dur'] for i in self.items)
        parents, cursor = [], Fraction(0)
        for i in spine:
            if i['start'] > cursor:
                parents.append({'gap': True, 'start': cursor, 'dur': i['start'] - cursor, 'src_in': Fraction(0), 'children': []})
            parents.append(dict(i, children=[]))
            cursor = i['start'] + i['dur']
        if end_all > cursor:
            parents.append({'gap': True, 'start': cursor, 'dur': end_all - cursor, 'src_in': Fraction(0), 'children': []})
        for i in sorted(others, key=lambda i: (i['start'], lanes[i['track']])):
            p = next((p for p in parents if p['start'] <= i['start'] < p['start'] + p['dur']), parents[-1])
            p['children'].append(i)

        def clip_xml(i, offset, lane=None, video_only=False, indent='    '):
            info = infos[i['media']]
            a = [f'ref="{asset_ids[i["media"]]}"']
            if lane is not None:
                a.append(f'lane="{lane}"')
            tc = info['tc']
            a += [f'offset="{t(offset)}"', f'name={quoteattr(i.get("name") or os.path.basename(i["media"]))}',
                  f'start="{t(i["src_in"] + tc)}"', f'duration="{t(i["dur"])}"']
            au = i.get('audio')
            if video_only and au and (au['src_in'] != i['src_in'] or au['dur'] != i['dur']):
                a += [f'audioStart="{t(au["src_in"] + tc)}"', f'audioDuration="{t(au["dur"])}"']
            if i['track'][0] == 'A':
                a.append('audioRole="music"' if i.get('role') == 'music' else ('audioRole="effects"' if i.get('role') == 'effects' else 'audioRole="dialogue"'))
            elif video_only and au:
                a.append('audioRole="dialogue"')
            intrinsic, filters = [], []
            if i['track'][0] == 'V':
                intrinsic += transform_xml(i)
                if video_only and info['audio']:
                    intrinsic += volume_xml(au) if au else ['<adjust-volume amount="-96dB"/>']
                elif info['audio']:   # a connected picture (a full-screen mp4) brings its sound too: srcEnable is ignored
                    intrinsic += ['<adjust-volume amount="-96dB"/>']
                for ename in i.get('filters', []):
                    x = effects[ename][1].strip().replace('{REF}', eff_ids[ename])
                    for pname, ks in ((i.get('filter_keys') or {}).get(ename) or {}).items():   # {KEYS:<param>} in the template
                        x = x.replace('{KEYS:%s}' % pname, '<keyframeAnimation>' + ''.join(
                            f'<keyframe time="{t(kt + tc)}" value="{fmt_num(v)}" interp="linear" curve="linear"/>'
                            for kt, v in ks) + '</keyframeAnimation>')
                    filters.append(re.sub(r'\{KEYS:[^}]*\}', '', x))
            else:
                intrinsic += volume_xml(i)
            return a, intrinsic, filters

        def transform_xml(i):
            keys = i.get('keys') or {}
            pos, sc = i.get('position'), i.get('scale')
            if not (pos or sc or keys):
                return []
            attrs = []
            if pos:
                attrs.append(f'position="{fmt_num(pos[0])} {fmt_num(pos[1])}"')
            if sc:
                attrs.append(f'scale="{fmt_num(sc[0])} {fmt_num(sc[1])}"')
            params = []
            for pname in ('position', 'scale'):
                if keys.get(pname):
                    ks = ''.join(f'<keyframe time="{t(kt + infos[i["media"]]["tc"])}" value="{fmt_num(v[0])} {fmt_num(v[1])}" interp="linear" curve="linear"/>'
                                 for kt, v in keys[pname])
                    params.append(f'<param name="{pname}"><keyframeAnimation>{ks}</keyframeAnimation></param>')
            if params:
                return [f'<adjust-transform {" ".join(attrs)}>' + ''.join(params) + '</adjust-transform>']
            return [f'<adjust-transform {" ".join(attrs)}/>']

        def volume_xml(i):
            vk, db, fo = i.get('volume_keys'), i.get('volume_db'), i.get('fade_out')
            if not (vk or fo or (db is not None and abs(db) > 1e-6)):
                return []
            amount = f' amount="{fmt_num(db)}dB"' if db is not None else ''
            inner = ''
            if fo:
                inner += f'<fadeOut type="easeOut" duration="{t(fo)}"/>'
            if vk:
                inner += '<keyframeAnimation>' + ''.join(
                    f'<keyframe time="{t(kt + infos[i["media"]]["tc"])}" value="{fmt_num(v)}dB" interp="linear" curve="linear"/>' for kt, v in vk) + '</keyframeAnimation>'
            if inner:
                return [f'<adjust-volume{amount}><param name="amount">{inner}</param></adjust-volume>']
            return [f'<adjust-volume{amount}/>']

        def element(tag, attrs, intrinsic, children, indent, filters=()):
            # DTD order inside a clip: intrinsic adjustments, anchored items, then video filters
            if not intrinsic and not children and not filters:
                return f'{indent}<{tag} {" ".join(attrs)}/>'
            inner = [indent + ' ' + b for b in intrinsic] + list(children) + [indent + ' ' + f.replace(chr(10), chr(10) + indent + ' ') for f in filters]
            return f'{indent}<{tag} {" ".join(attrs)}>\n' + '\n'.join(inner) + f'\n{indent}</{tag}>'

        spine_xml = []
        for p in parents:
            kids = []
            for c in p['children']:
                off = p['src_in'] + (0 if p.get('gap') else infos[p['media']]['tc']) + (c['start'] - p['start'])
                ca, ci, cf = clip_xml(c, off, lane=lanes[c['track']])
                kids.append(element('asset-clip', ca, ci, [], '      ', cf))
            if p.get('gap'):
                spine_xml.append(element('gap', [f'name="Gap"', f'offset="{t(p["start"])}"', f'start="{t(p["src_in"])}"',
                                                 f'duration="{t(p["dur"])}"'], [], kids, '     '))
            else:
                pa, pi, pf = clip_xml(p, p['start'], video_only=True)
                spine_xml.append(element('asset-clip', pa, pi, kids, '     ', pf))

        lib = 'file://' + os.path.abspath(library).replace(' ', '%20')
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.14">
 <import-options>
  <option key="library location" value={quoteattr(lib)}/>
  <option key="copy assets" value="0"/>
  <option key="suppress warnings" value="1"/>
 </import-options>
 <resources>
''' + '\n'.join('  ' + r.replace('\n', '\n  ') for r in res) + f'''
 </resources>
 <library>
  <event name={quoteattr(self.event)}>
   <project name={quoteattr(self.name)}>
    <sequence format="{seq_fmt}" duration="{t(end_all)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
     <spine>
''' + '\n'.join(spine_xml) + '''
     </spine>
    </sequence>
   </project>
  </event>
 </library>
</fcpxml>
'''
        with open(path, 'w', encoding="utf-8") as f:
            f.write(xml)
        return {'assets': len(asset_ids), 'spine': len(parents), 'connected': len(others), 'duration': float(end_all),
                'warnings': self.warnings}
