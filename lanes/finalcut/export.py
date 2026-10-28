#!/usr/bin/env python3
"""export.py: the Final Cut lane's step 8. Final Cut's ProRes master in, the format's deliverable out, proven.

  uv run lanes/finalcut/export.py projects/<job> [--project "<name>"]      Final Cut renders the master, then this
  uv run lanes/finalcut/export.py projects/<job> --master <the .mov> [--frames N]    from a master already rendered
  ... --variant NAME     a second deliverable's file: outputs/NAME/<job>.NAME.mp4, for `./finalize.sh <job> --variant NAME`
  ... --shorts           a 2160x3840 master's second file, the 4K one for YouTube Shorts: outputs/shorts/<job>.shorts.mp4

Without --master, share.py has Final Cut itself render the project to a ProRes master in finalcut/renders/ first,
through the bridge, no clicks (the newest finalcut/*.fcpxml's project unless --project names one).

Final Cut's H.264 choices carry no bitrate control, so the deliverable is encoded from its master by
workflows/deliver.py, to the format's numbers (researched and set 2026-09-26), picked from the master's frame: a
1080x1920 or 2160x3840 master gets the vertical file (presets/instagram/talking-head-explainer/README.md § Export:
1080x1920, H.264 High 4.2, CBR 14, less past 2:48; the Reels ceiling 25 Mbps AND 300 MB), and with --shorts a
2160x3840 master the 4K YouTube Shorts file; a landscape master, 1920x1080 or 3840x2160, the long-form one
(presets/youtube/default/README.md § Export: 3840x2160, H.264 High, CBR 50, CBR 80 above 30 fps). The master's audio
is PCM, so the one AAC 320k encode is the only lossy audio step.

Writes outputs/<job>-final.mp4 (never outputs/<job>.mp4, which finalize.sh refuses; with --variant NAME,
outputs/NAME/<job>.NAME.mp4), then proves it: moov, the
master's frame size and rate, a frame count equal to the master's (and to --frames, the timeline's, when given),
the format's ceiling (short: <= 300 MB and 25 Mbps), integrated loudness and true peak printed. Then `./finalize.sh <job> --apply`.
The lane builds the organic cut only (replay.py has no ad variant): a --project named '<...> AD' is refused without
--variant, so an ad build can never be filed as the organic deliverable.
Exit: 0 written and proven · 1 a check failed (the file is kept) · 2 bad input.
"""
import argparse, importlib.util, json, re, subprocess, sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

CEIL_MBPS, CEIL_MB = 25, 300          # the vertical file's Reels ceiling (the Talking Head Explainer README § Export)
_spec = importlib.util.spec_from_file_location('deliver', Path(__file__).resolve().parents[2] / 'workflows' / 'deliver.py')
deliver = importlib.util.module_from_spec(_spec)   # workflows/deliver.py: the numbers and the one ffmpeg encode
_spec.loader.exec_module(deliver)


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-count_packets', '-show_entries',
                          'stream=codec_type,codec_name,profile,level,width,height,r_frame_rate,nb_read_packets,bit_rate,'
                          'sample_rate,color_primaries,color_transfer:format=duration,size,format_name',
                          '-of', 'json', str(path)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--master', help='a ProRes master already rendered (default: Final Cut renders one now)')
    ap.add_argument('--project', help='the Final Cut project to render (default: the newest finalcut/*.fcpxml)')
    ap.add_argument('--frames', type=int, help="the timeline's frame count, when known")
    ap.add_argument('--variant', help='a second deliverable (e.g. ad): outputs/NAME/<job>.NAME.mp4')
    ap.add_argument('--shorts', action='store_true', help="a 2160x3840 master's 4K YouTube Shorts file: "
                    'outputs/shorts/<job>.shorts.mp4')
    a = ap.parse_args()
    job = Path(a.job)
    if not (job / 'transcript' / 'cuts.json').exists():
        print(f'✗ {job} is not a job folder (no transcript/cuts.json)', file=sys.stderr)
        return 2
    if a.variant and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', a.variant):
        print(f'✗ --variant {a.variant!r}: letters, digits, - and _ only (it becomes part of file names)', file=sys.stderr)
        return 2
    if a.project and a.project.endswith(' AD') and not a.variant:
        print(f'✗ --project "{a.project}" is an ad cut: pass --variant ad so it is filed as the second deliverable, '
              'never as outputs/<job>-final.mp4. Nothing exported.', file=sys.stderr)
        return 2
    (job / 'outputs').mkdir(exist_ok=True)
    if not a.master:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from share import share, Fail
        try:
            master, a.frames = share(job, a.project)
        except Fail as ex:
            print(f'✗ {ex}', file=sys.stderr)
            return 2
        a.master = str(master)
    master = Path(a.master)
    if not master.exists():
        print(f'✗ no master at {master}', file=sys.stderr)
        return 2
    m = probe(master)
    mv = next(s for s in m['streams'] if s['codec_type'] == 'video')
    W, H = int(mv['width']), int(mv['height'])
    if W <= H and (W, H) not in ((1080, 1920), (2160, 3840)):
        print(f'✗ master is {W}x{H}: a vertical master is 1080x1920 or 2160x3840, a long-form one landscape',
              file=sys.stderr)
        return 2
    if a.shorts and ((W, H) != (2160, 3840) or a.variant):
        print(f'✗ --shorts is the 4K vertical file for YouTube Shorts: a 2160x3840 master, no --variant (this one is {W}x{H})'
              + ('; a 1080x1920 master has one file, and it already serves Shorts' if (W, H) == (1080, 1920) else ''),
              file=sys.stderr)
        return 2
    name = job.resolve().name
    out = (job / 'outputs' / a.variant / f'{name}.{a.variant}.mp4' if a.variant
           else job / 'outputs' / 'shorts' / f'{name}.shorts.mp4' if a.shorts
           else job / 'outputs' / f'{job.name}-final.mp4')
    out.parent.mkdir(parents=True, exist_ok=True)
    pl = deliver.encode(master, out, a.shorts)
    rate, frames, OW, OH, short = pl['rate'], pl['frames'], pl['OW'], pl['OH'], pl['vertical']

    d = probe(out)
    v = next(s for s in d['streams'] if s['codec_type'] == 'video')
    au = next(s for s in d['streams'] if s['codec_type'] == 'audio')
    size_mb = int(d['format']['size']) / 1e6
    n = int(v['nb_read_packets'])
    checks = [
        ('mp4', 'mp4' in d['format']['format_name']),
        (f'{OW}x{OH}', (int(v['width']), int(v['height'])) == (OW, OH)),
        ('H.264 High', v['codec_name'] == 'h264' and v.get('profile') == 'High'),
        ('bt709', v.get('color_primaries') == 'bt709' and v.get('color_transfer') == 'bt709'),
        (f'rate {rate}', v['r_frame_rate'] == rate),
        (f'frames {n} == master {frames}', n == frames),
        ('AAC 48k', au['codec_name'] == 'aac' and au['sample_rate'] == '48000'),
    ]
    if short:
        checks += [(f'<= {CEIL_MB} MB ({size_mb:.0f})', size_mb <= CEIL_MB),
                   (f'<= {CEIL_MBPS} Mbps', int(v.get('bit_rate', 0)) <= CEIL_MBPS * 1e6)]
    if a.frames:
        checks.append((f'frames == timeline {a.frames}', n == a.frames))
    loud = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(out), '-vn', '-af', 'ebur128=peak=true',
                           '-f', 'null', '-'], capture_output=True, text=True).stderr
    summ = loud[loud.rfind('Summary:'):]
    lufs = re.search(r'I:\s+(-?[\d.]+) LUFS', summ)
    tp = re.search(r'Peak:\s+(-?[\d.]+) dBFS', summ)
    bad = [c for c, ok in checks if not ok]
    for c, ok in checks:
        print(('✓ ' if ok else '✗ ') + c)
    print(f'  loudness {lufs.group(1) if lufs else "?"} LUFS integrated, true peak {tp.group(1) if tp else "?"} dBFS, '
          f'{int(v.get("bit_rate", 0)) / 1e6:.2f} Mbps video')
    if bad:
        print(f'✗ {len(bad)} check(s) failed; {out} kept', file=sys.stderr)
        return 1
    var = a.variant or ('shorts' if a.shorts else '')
    nxt = f'./finalize.sh {name}' + (f' --variant {var}' if var else '') + ' --apply'
    print(f'✓ {out} — next: {nxt}')
    if (W, H) == (2160, 3840) and not a.shorts and not a.variant:
        print(f'  a 4K vertical job has a second file, the 4K one for YouTube Shorts: '
              f'uv run lanes/finalcut/export.py {a.job} --master {master} --shorts')
    return 0


if __name__ == '__main__':
    sys.exit(main())
