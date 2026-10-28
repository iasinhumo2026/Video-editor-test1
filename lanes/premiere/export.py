#!/usr/bin/env python3
"""export.py: pipeline step 8 on the Premiere lane. Export the active sequence through the FORMAT's
locked preset, wait for Premiere to finish the file, and prove it with ffprobe.

  uv run lanes/premiere/export.py projects/<job>                      # the job-named sequence -> outputs/<job>-final.mp4
  uv run lanes/premiere/export.py projects/<job> --draft              # -> outputs/<job>-draft-<n>.mp4 (never promoted)
  uv run lanes/premiere/export.py projects/<job> --sequence "<job> AD"
        # a variant sequence '<job> <VARIANT>' -> outputs/<variant>/<job>.<variant>.mp4 (never loose in outputs/)
  uv run lanes/premiere/export.py projects/<job> --shorts
        # a 2160x3840 sequence's SECOND file, the 4K one for YouTube Shorts -> outputs/shorts/<job>.shorts.mp4
  options: --out PATH  --preset EPR  --force (overwrite)  --timeout-min 60

Run it on the creator's go only: the run pauses at step 7 until he says export. Then `./finalize.sh <job> --apply`
promotes `<job>-final.mp4`; `outputs/<job>.mp4` is the base cut finalize.sh keeps, so this never writes it.

The preset is picked from the SEQUENCE, never from a word like "full quality" (a short once went out through the
2160p preset and came back pillarboxed). The numbers are the presets' § Export (researched and set 2026-09-26):
portrait 1080x1920 / 2160x3840 -> the Reels file, 1080x1920 CBR 14 at any rate, or the duration's lower bitrate
past 2:48 (video <= 2350 / seconds - 0.32 Mbps, minted); with --shorts, a 2160x3840 sequence -> the 2160x3840
YouTube Shorts file at the long-form 4K numbers (a ProRes master, encoded by workflows/deliver.py: Premiere's H.264
caps the frame at 4096x2304); 3840x2160 AND 1920x1080 -> the 3840x2160 CBR-50 YouTube preset (its
-2997 twin at 29.97; a 1080 sequence is uploaded at 2160p, because YouTube only makes renditions up to the upload's
size), CBR 80 above 30 fps. Every non-tracked preset is minted on first use by premiere-templates/mint-export-preset.py
(regenerable, gitignored). Anything else refuses, naming --preset.

Why (2026-09-21/22): every export was a hand-typed `exportAsMediaDirect`, once dug out of an old session log. The
call returned before Premiere had finished the file (ffprobe: 'moov atom not found'), the bridge gave up at 45 s
while Premiere kept writing, and a draft came back at 1104 of 3018 frames without anyone noticing. So: the call
runs with a timeout that outlives the export, the file is waited on until `lsof` shows it closed and its size
holds across three checks 2 s apart, and ffprobe then checks the moov, the preset's frame size, the sequence's
rate and frame count, and on the Reels preset Meta's 300 MB API cap (bitrate <= 2400 / seconds Mbps). Any failed
check exits non-zero and keeps the file.
"""
import argparse, json, os, re, subprocess, sys, time
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from job_guard import job_root, require_job_project  # noqa: E402
from pes import es  # noqa: E402  — lanes/premiere/pes.py: the bridge's one output contract

TEMPLATES = Path(__file__).resolve().parent / 'premiere-templates'
TICKS = 254016000000                 # Premiere ticks per second
TPF_23976 = 10594584000              # ticks per frame at 23.976 (24000/1001)
TPF_2997 = 8475667200                # ticks per frame at 29.97 (30000/1001)
REELS = 'instagram-1080x1920-h264-cbr14-23976.epr'
YT, YT_2997 = 'youtube-2160p-h264-cbr50.epr', 'youtube-2160p-h264-cbr50-2997.epr'
MINT_DIR = TEMPLATES                 # where a non-tracked preset is minted on first use (premiere-templates/mint-export-preset.py)
LONG_MBPS, LONG_HFR_MBPS = 50, 80    # presets/youtube/default/README.md § Export: CBR 50 at <= 30 fps, CBR 80 at 48-60 fps
REELS_MBPS = 14                      # presets/instagram/talking-head-explainer/README.md § Export: CBR 14, lower past 2:48
REELS_SIZE = (1080, 1920)            # any preset with this target is held to the Reels cap
REELS_CAP = 300_000_000              # bytes: Meta's publishing-API cap on a Reel (presets/instagram/talking-head-explainer/README.md § Export)
AUDIO_MBPS = 0.32                    # AAC 320k, in every locked preset
POLL, STABLE = 2.0, 3                # the file is done when closed and the same size across 3 checks 2 s apart
APPEAR_GRACE = 120                   # after a failed bridge call, how long the file gets to show up at all
RETURN_GRACE = 10                    # after a normal return: the call is synchronous, so a file still absent was never written

# seq.end can read 0 on a sequence Premiere has not re-evaluated; the tracks always know (premiere-bridge.mjs
# clear-previews). So the length is the later of seq.end and the latest end of EVERY clip on every track, never
# each track's last item: a scripted move leaves a track's items out of time order.
READ_ES = r"""(function(){ var s = app.project.activeSequence; if (!s) return "null";
  var off = [], last = 0, lists = [s.videoTracks, s.audioTracks], l, t, i, k, e;
  for (l = 0; l < 2; l++) for (t = 0; t < lists[l].numTracks; t++) { k = lists[l][t];
    if (k.isMuted() && k.clips.numItems > 0) off.push((l ? "A" : "V") + (t + 1));
    for (i = 0; i < k.clips.numItems; i++) { e = Number(k.clips[i].end.ticks); if (e > last) last = e; } }
  var marks = null; try { marks = [Number(s.getInPoint()), Number(s.getOutPoint())]; } catch (x) {}
  return JSON.stringify({name: s.name, w: Number(s.frameSizeHorizontal), h: Number(s.frameSizeVertical),
                         tpf: String(s.timebase), end: String(s.end), clipEnd: String(last), off: off, marks: marks}); })()"""

EXPORT_ES = r"""(function(){ var s = app.project.activeSequence;
  if (!s || s.name !== %s) return JSON.stringify({err: "the active sequence is now " + (s ? s.name : "none")});
  return JSON.stringify({r: String(s.exportAsMediaDirect(%s, %s, 0))}); })()"""


def rate(tpf):
    """'23.976', '29.97', '30' — a sequence rate the way the preset names spell it."""
    return f'{TICKS / tpf:.3f}'.rstrip('0').rstrip('.')


def prores_preset():
    """The installed Premiere's own 'Apple ProRes 422 HQ' system preset (match source), found, never typed: the
    master the 4K Shorts file is encoded from (PREMIERE_PRORES_PRESET overrides)."""
    env = os.environ.get('PREMIERE_PRORES_PRESET')
    if env:
        return Path(env) if os.path.isfile(env) else sys.exit(f'PREMIERE_PRORES_PRESET={env} does not exist')
    rel = 'MediaIO/systempresets/3F3F3F3F_4D6F6F56/Apple ProRes 422 HQ.epr'
    pats = (['/Applications/Adobe Premiere Pro*/Adobe Premiere Pro*.app/Contents/' + rel] if sys.platform == 'darwin'
            else ['C:/Program Files/Adobe/Adobe Premiere Pro*/' + rel] if os.name == 'nt' else [])
    import glob
    hits = sorted(h for pat in pats for h in glob.glob(pat) if 'Beta' not in h)
    return Path(hits[-1]) if hits else sys.exit("no Premiere 'Apple ProRes 422 HQ.epr' found: set PREMIERE_PRORES_PRESET")


def reels_mbps(seconds):
    """The Reels video bitrate for a piece this long: CBR 14, or less once 14 would break Meta's 300 MB cap
    (video <= 2350 / seconds - 0.32 Mbps: 300 MB less 2 % for the container, less the AAC 320k), whole Mbps."""
    if not seconds or seconds <= 0:
        return REELS_MBPS
    return max(1, min(REELS_MBPS, int(2350 / seconds - AUDIO_MBPS)))


def minted(size, mbps, df=False, reels=False):
    """A non-tracked preset (premiere-templates/mint-export-preset.py), minted into MINT_DIR on first use."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('mint_export_preset', TEMPLATES / 'mint-export-preset.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    want = MINT_DIR / mod.name_for(size, mbps, df, reels)
    if not want.is_file():
        want = mod.mint(size, df, TEMPLATES, MINT_DIR, mbps=mbps, reels=reels)
        print(f'[export] minted {want.name} ({size[0]}x{size[1]}, CBR {mbps:g}; LANES.md § step 8)')
    return want


def pick_preset(w, h, tpf, override=None, seconds=None):
    """The locked preset for this sequence's FORMAT (LANES.md § step 8), or a refusal naming what is missing."""
    if override:
        p = Path(override).expanduser().resolve()
        if not p.is_file():
            sys.exit(f'preset not found: {p}')
        return p
    hfr = tpf and TICKS / tpf > 30.5                   # 48-60 fps: YouTube's high-frame-rate row
    long_mbps = LONG_HFR_MBPS if hfr else LONG_MBPS
    if (w, h) in ((1080, 1920), (2160, 3840)):
        # any rate: the exporter matches the SEQUENCE rate, not the .epr's ADBEVideoFPS (live 2026-09-23: this 23.976
        # preset wrote a 29.97 sequence at 30000/1001), and verify() fails a file whose rate is not the sequence's
        if tpf != TPF_23976:
            print(f"[export] note: the Reels preset names 23.976; Premiere exports at the sequence's {rate(tpf)} fps, "
                  "and the file's rate is checked against it")
        mbps = reels_mbps(seconds)
        return TEMPLATES / REELS if mbps == REELS_MBPS else minted((1080, 1920), mbps, reels=True)
    if (w, h) in ((3840, 2160), (1920, 1080)):
        # a 1080 sequence goes up at 3840x2160 too: YouTube makes renditions only up to the upload's size, and its
        # 1440p/2160p ones carry several times the 1080p bitrate (presets/youtube/default/README.md § Export)
        if hfr:
            return minted((3840, 2160), long_mbps)
        return TEMPLATES / (YT_2997 if tpf == TPF_2997 else YT)
    sys.exit(f'no export preset for a {w}x{h} sequence at {rate(tpf)} fps: pass one with --preset')


def check_shape(w, h, tw, th):
    """Refuse a preset whose frame is not the sequence's SHAPE: Premiere fits the picture inside it, so a landscape
    preset on a portrait sequence exports a pillarboxed file that is 'the right size' for the preset."""
    if tw and th and Fraction(tw, th) != Fraction(w, h):
        sys.exit(f'the preset exports {tw}x{th}, not the shape of this {w}x{h} sequence: the picture would be '
                 f'{"pillarboxed" if tw * h > th * w else "letterboxed"}. Nothing exported; pick a preset of the same shape.')


def preset_target(epr):
    """The .epr's own ADBEVideoWidth / Height (px) and target bitrate (Mbps); None where the preset leaves it out."""
    x = Path(epr).read_text(errors='replace', encoding="utf-8")

    def param(k):
        m = re.search(r'<ParamIdentifier>%s</ParamIdentifier>(.*?)</ExporterParam>' % k, x, re.S)
        v = m and re.search(r'<ParamValue>([^<]*)</ParamValue>', m.group(1))
        try:
            return float(v.group(1)) if v else None
        except ValueError:
            return None
    w, h, mbps = param('ADBEVideoWidth'), param('ADBEVideoHeight'), param('ADBEVideoTargetBitrate')
    return (int(w) if w else None), (int(h) if h else None), mbps


def deliver():
    """workflows/deliver.py, the lane-neutral encode from a master."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('deliver', TEMPLATES.parent.parent.parent / 'workflows' / 'deliver.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def next_draft(folder, base):
    """1 + the highest draft number already in `folder` (`<base>-<n>` or the older `<base>-v<n>`)."""
    pat = re.compile(re.escape(base) + r'-v?(\d+)\.mp4$')
    ns = [int(m.group(1)) for f in (folder.iterdir() if folder.is_dir() else []) for m in [pat.match(f.name)] if m]
    return max(ns, default=0) + 1


def out_path(root, seq_name, draft=False, out=None, force=False, shorts=False):
    """Where the export lands. The job-named sequence -> outputs/<job>-final.mp4 (finalize.sh promotes it), --draft ->
    outputs/<job>-draft-<n>.mp4, a '<job> <VARIANT>' sequence -> outputs/<variant>/<job>.<variant>.mp4. Never
    outputs/<job>.mp4, the base cut finalize.sh keeps; never over an existing file without --force."""
    job, outputs = root.name, root / 'outputs'
    variant = re.sub(r'[^a-z0-9]+', '-', seq_name[len(job):].lower()).strip('-') if seq_name.startswith(job + ' ') else ''
    if out:
        p = Path(out).expanduser().resolve()
    else:
        if shorts and seq_name == job:
            folder, final = outputs / 'shorts', f'{job}.shorts'   # finalize.sh <job> --variant shorts
            base = f'{job}.shorts-draft'
        elif shorts:
            sys.exit(f"--shorts exports the job's own sequence ({job!r}), not {seq_name!r}: pass --out for anything else")
        elif seq_name == job:
            folder, final = outputs, f'{job}-final'
            base = f'{job}-draft'
        elif variant:
            folder, final = outputs / variant, f'{job}.{variant}'
            base = f'{job}.{variant}-draft'
        else:
            sys.exit(f"the sequence {seq_name!r} is neither the job's own ({job!r}) nor a variant ('{job} <VARIANT>'), "
                     "so there is no default name for its export: pass --out")
        p = (folder / f'{base}-{next_draft(folder, base)}.mp4') if draft else folder / f'{final}.mp4'
    base_cut = outputs / f'{job}.mp4'
    if p.resolve() == base_cut.resolve() or (p.exists() and base_cut.exists() and os.path.samefile(p, base_cut)):
        # samefile: APFS and NTFS are case-insensitive, so outputs/<JOB>.mp4 IS the base cut there
        sys.exit(f'{p} is the base cut finalize.sh keeps: an export never writes it. Use the default name or another --out.')
    if p.exists() and not force:
        sys.exit(f'{p} already exists: nothing exported. Pass --force to replace it, or --draft for a numbered draft.')
    return p


def lsof_open(path):
    """Does any process still hold the file open? No lsof (Windows) = the size test carries the wait alone."""
    try:
        r = subprocess.run(['lsof', '--', str(path)], capture_output=True, text=True)
    except FileNotFoundError:
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


def wait_closed(path, deadline, appear_by=None, lsof=None, sleep=None, now=None):
    """True once the file exists, is non-empty, no process holds it open and its size holds across STABLE checks
    POLL s apart. False at `deadline`, or at `appear_by` if the file has not appeared by then. Never ffprobe
    before this: Premiere writes the moov LAST, and a file probed mid-write reads 'moov atom not found'."""
    lsof, sleep, now = lsof or lsof_open, sleep or time.sleep, now or time.monotonic
    sizes = []
    while True:
        t = now()
        if t > deadline or (appear_by is not None and t > appear_by and not path.exists()):
            return False
        size = path.stat().st_size if path.exists() else 0
        if size > 0 and not lsof(path):
            sizes.append(size)
            if len(sizes) >= STABLE and len(set(sizes[-STABLE:])) == 1:
                return True
        else:
            sizes = []
        sleep(POLL)


def probe(path):
    """(info, error): ffprobe's video stream + format, or the reason it could not read the file."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=codec_name,width,height,r_frame_rate,nb_frames,bit_rate,color_primaries,color_transfer,'
                        'color_space:format=duration,size', '-of', 'json', str(path)],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout or '{}')
    except ValueError:
        d = {}
    if r.returncode or not d.get('streams'):
        err = [re.sub(r'^\[[^\]]*\]\s*', '', l.strip()) for l in (r.stderr or '').splitlines() if l.strip()]
        return None, ('; '.join(err) if err else 'no video stream')
    s, f = d['streams'][0], d.get('format', {})
    frames = s.get('nb_frames')
    if not str(frames or '').isdigit():   # a container without a frame count in its header: count the packets
        c = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                            'stream=nb_read_packets', '-of', 'csv=p=0', str(path)], capture_output=True, text=True)
        # the first row only: ffprobe 9 prints a timecoded file's video row twice
        frames = next((l for l in c.stdout.splitlines() if l.strip()), '').split(',')[0].strip()
    return {'w': int(s['width']), 'h': int(s['height']), 'fps': Fraction(s['r_frame_rate']),
            'frames': int(frames) if str(frames).isdigit() else None,
            'size': int(f.get('size') or Path(path).stat().st_size), 'seconds': float(f.get('duration') or 0),
            'codec': s.get('codec_name'), 'mbps': int(s['bit_rate']) / 1e6 if str(s.get('bit_rate', '')).isdigit() else None,
            'colour': tuple(s.get(k) or 'unknown' for k in ('color_primaries', 'color_transfer', 'color_space'))}, None


BT709 = ('bt709', 'bt709', 'bt709')


def stamp_bt709(path):
    """Write the Rec.709 colour tags into an H.264 file that carries none, losslessly: a stream copy through
    h264_metadata (the SPS VUI) plus the container's own tags. Premiere on Windows wrote NO colour tags (every
    template's ADBE_H264_ColorPrimaries is false and disabled, so ffprobe read 'unknown'), while the Mac's hardware
    encoder tags bt709 on its own (2026-09-27): the picture is Rec.709 on both, only the label was missing."""
    # the copy is written beside the file under a name no render picker matches (never "*final*.mp4": finalize.sh
    # promotes the newest final-named render), and removed if ffmpeg fails part way
    tmp = path.with_name('.' + path.name + '.bt709-tmp')
    try:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(path), '-map', '0', '-c', 'copy', '-bsf:v',
                        'h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1',
                        '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                        '-movflags', '+faststart', '-f', 'mp4', str(tmp)], check=True, capture_output=True)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def reels_rule(seconds, mbps):
    """Meta's cap as a sentence: the ceiling for THIS duration and the duration where `mbps` stops fitting."""
    cap = REELS_CAP * 8 / 1e6                          # 2400 Mb
    s = (f'video <= 2350 / seconds - 0.32 Mbps: <= {2350 / seconds - AUDIO_MBPS:.1f} Mbps for this {seconds:.1f} s piece '
         f'(the file <= {cap / seconds:.1f} Mbps in all)')
    if mbps:
        brk = round(cap / (mbps + AUDIO_MBPS))
        s += f'; the preset\'s {mbps:g} Mbps (+ AAC 320k) breaks 300 MB past {brk} s ({brk // 60}:{brk % 60:02d})'
    return s


def verify(path, want):
    """(failures, notes) for the finished file against `want`: {w, h, fps (Fraction), frames, reels, mbps, seconds}."""
    info, err = probe(path)
    if not info:
        return [f"parse: ffprobe cannot read it ({err}); 'moov atom not found' = Premiere never finished the file"], []
    fails, notes = [], []
    if (info['w'], info['h']) != (want['w'], want['h']):
        fails.append(f"frame size: {info['w']}x{info['h']}, the preset's target is {want['w']}x{want['h']}")
    if info['fps'] != want['fps']:
        fails.append(f"frame rate: {info['fps']} ({float(info['fps']):.3f}), the sequence runs {want['fps']} ({float(want['fps']):.3f})")
    if info['frames'] is None:
        fails.append('frame count: ffprobe reports none')
    elif info['frames'] != want['frames']:
        d = info['frames'] - want['frames']
        if abs(d) == 1:
            notes.append(f"frame count {info['frames']} vs the sequence's {want['frames']} ({d:+d}, inside the ±1 rounding of its end)")
        else:
            fails.append(f"frame count: {info['frames']}, the sequence is {want['frames']} ({d:+d}: "
                         f"{'truncated' if d < 0 else 'longer than the timeline'})")
    if want.get('reels') and info['size'] > REELS_CAP:
        fails.append(f"size: {info['size'] / 1e6:.1f} MB > 300 MB, Meta's Reels API cap ({reels_rule(want['seconds'], want.get('mbps'))})")
    colour, mbps = info.get('colour') or ('unknown',) * 3, info.get('mbps')
    if want.get('bt709') and colour != BT709:
        fails.append(f"colour tags: primaries/transfer/matrix read {'/'.join(colour)}, not bt709")
    if want.get('mbps') and mbps and mbps < 0.9 * want['mbps']:
        # a note, never a failure: YouTube re-encodes, and its own 4K 24-30 fps SDR row is 35-45 Mbps. Premiere on
        # Windows delivered 41.2 Mbps from the CBR 50 preset (its encoder, not the file's settings; 2026-09-27)
        notes.append(f"⚠ video {mbps:.1f} Mbps, under the preset's {want['mbps']:g} Mbps CBR target (this OS's encoder)")
    return fails, notes + [f"{info['w']}x{info['h']} @ {float(info['fps']):.3f} fps, {info['frames']} frames, "
                           f"{info['seconds']:.3f} s, {info['size'] / 1e6:.1f} MB"
                           + (f", video {mbps:.1f} Mbps" if mbps else '') + f", {'/'.join(colour)}"]


def main(argv=None):
    ap = argparse.ArgumentParser(description='Export the active Premiere sequence through its format preset, then prove the file.')
    ap.add_argument('job')
    ap.add_argument('--sequence', help="the sequence to export (it must be the ACTIVE one); default = the guard's own rule")
    ap.add_argument('--out', help='output file (default: named from the sequence, see the docstring)')
    ap.add_argument('--preset', help='an .epr overriding the format pick')
    ap.add_argument('--draft', action='store_true', help='a numbered draft finalize.sh never promotes')
    ap.add_argument('--shorts', action='store_true',
                    help="a 2160x3840 sequence's 4K YouTube Shorts file -> outputs/shorts/<job>.shorts.mp4")
    ap.add_argument('--force', action='store_true', help='replace an existing output file')
    ap.add_argument('--timeout-min', dest='timeout_min', type=float, default=60, help='how long the export may take (default 60)')
    a = ap.parse_args(argv)
    root = job_root(a.job)

    if a.sequence:
        os.environ['VE_SEQUENCE'] = a.sequence          # the guard's sequence rule: the active one must be this one
    require_job_project(es, a.job)
    seq = json.loads(es(READ_ES))
    if not seq:
        sys.exit('there is no active sequence: nothing exported.')
    if a.sequence and seq['name'] != a.sequence:
        sys.exit(f"the active sequence is {seq['name']!r}, not {a.sequence!r}: nothing exported. Open it and re-run.")
    w, h = int(seq['w'] or 0), int(seq['h'] or 0)
    tpf, seq_end, clip_end = (int(x) if str(x).isdigit() else 0 for x in (seq['tpf'], seq['end'], seq.get('clipEnd')))
    end = max(seq_end, clip_end)
    if tpf <= 0 or end <= 0:
        sys.exit(f"the sequence reads back no timebase or length (timebase {seq['tpf']!r}, end {seq['end']!r}, "
                 f"latest clip end {seq.get('clipEnd')!r}): nothing exported.")
    if abs(seq_end - clip_end) > tpf:
        print(f"[export] note: seq.end reads {seq_end / tpf:.1f} frames, the latest clip ends at {clip_end / tpf:.1f}: "
              f"the length is the later one (seq.end goes stale on a sequence Premiere has not re-evaluated)")
    fps, frames, seconds = Fraction(TICKS, tpf), round(Fraction(end, tpf)), end / TICKS

    final = None
    if a.shorts:
        # Premiere's H.264 exporter caps the frame at 4096x2304 (a 2160x3840 preset wrote 1296x2304, live 2026-09-26)
        # and its HEVC exporter answers exportAsMediaDirect with -1, so the Shorts file is a ProRes master from
        # Premiere, encoded to the numbers by workflows/deliver.py
        if (w, h) != (2160, 3840) or a.preset:
            sys.exit(f'--shorts is the 4K vertical file for YouTube Shorts: a 2160x3840 sequence and no --preset, not {w}x{h}'
                     + ('; a 1080x1920 sequence has one file, and it already serves Shorts' if (w, h) == (1080, 1920) else ''))
        epr, tw, th, mbps = prores_preset(), w, h, None
        final = out_path(root, seq['name'], a.draft, a.out, a.force, a.shorts)
        out = root / 'premiere' / 'renders' / f'{root.name}-shorts-master.mov'
        if out.exists():
            sys.exit(f'{out} exists (a master left by a run that stopped): move it aside, nothing exported')
    else:
        epr = pick_preset(w, h, tpf, a.preset, seconds)
        tw, th, mbps = preset_target(epr)
        check_shape(w, h, tw, th)
        out = out_path(root, seq['name'], a.draft, a.out, a.force, a.shorts)
    want = {'w': tw or w, 'h': th or h, 'fps': fps, 'frames': frames, 'seconds': seconds, 'mbps': mbps,
            'reels': (tw or w, th or h) == REELS_SIZE}
    print(f"[export] {seq['name']}: {w}x{h} @ {rate(tpf)} fps, {frames} frames ({seconds:.3f} s)\n"
          f"[export] preset {epr.name} -> {want['w']}x{want['h']}{f', {mbps:g} Mbps' if mbps else ''}\n[export] -> {out}")
    if seq.get('off'):
        print(f"[export] ⚠ TRACK OUTPUT OFF: {', '.join(seq['off'])}: those tracks hold clips and will NOT be in the "
              "export. Turn them back on first unless the creator muted them on purpose.")
    mk = seq.get('marks')
    if mk and None not in mk and (mk[0] > 0.0005 or 0.0005 < mk[1] < seconds - 0.0005):
        # a bounce that died mid-script leaves its in/out behind (cut-proof.py says so); an export that honoured
        # them would come back short, which the frame count below fails. Unset reads negative (-400000), and
        # 0 / 0 is the old hand call's setInPoint(0);setOutPoint(0): an empty range, never a mark.
        print(f"[export] ⚠ in/out marks are set ({mk[0]:.3f} to {mk[1]:.3f} s) on a {seconds:.3f} s sequence: the export is "
              "the whole sequence, and a file short of it fails the frame count. Leftovers from a bounce are cleared "
              "with setInPoint(-400000) / setOutPoint(-400000); the creator's own marks are his.")
    if want['reels'] and mbps and (mbps + AUDIO_MBPS) * seconds / 8 * 1e6 > REELS_CAP:
        print(f"[export] ⚠ at {mbps:g} Mbps this lands about {(mbps + AUDIO_MBPS) * seconds / 8:.0f} MB, over Meta's 300 MB "
              f"Reels API cap: {reels_rule(seconds, mbps)}. Drop --preset: the Reels pick lowers the bitrate by duration.")

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()                                    # --force: an old file must never pass for the new one
    t0 = time.monotonic()
    deadline, appear_by, r = t0 + a.timeout_min * 60, None, None
    try:
        r = json.loads(es(EXPORT_ES % (json.dumps(seq['name']), json.dumps(str(out)), json.dumps(str(epr))),
                          timeout=int(a.timeout_min * 60000)))
    except SystemExit as e:                             # the bridge gave up; Premiere may not have
        msg = str(e.code)
        if msg.startswith('bridge: ERROR') and not out.exists():
            sys.exit(f'the export call failed: {msg}')
        print(f"[export] ⚠ {msg}: Premiere may still be writing, so the file itself decides", file=sys.stderr)
        appear_by = time.monotonic() + APPEAR_GRACE
    if r and r.get('err'):
        sys.exit(f"{r['err']}, not {seq['name']!r}: nothing exported.")
    if r:
        print(f"[export] exportAsMediaDirect returned {r.get('r')!r} after {time.monotonic() - t0:.0f} s; waiting on the file")
        appear_by = time.monotonic() + RETURN_GRACE
    if not wait_closed(out, deadline, appear_by):
        if not out.exists():
            sys.exit(f'✗ no file was written at {out}'
                     + (f": exportAsMediaDirect returned {r.get('r')!r}" if r else ' after the bridge call failed'))
        sys.exit(f'✗ the export did not finish within {(time.monotonic() - t0) / 60:.1f} min: '
                 f'{out} is still open or growing (kept)')
    info, _ = probe(out)
    if info and info.get('codec') == 'h264' and info.get('colour') != BT709:
        print(f"[export] colour tags read {'/'.join(info['colour'])}: stamping bt709 (a lossless stream copy)")
        stamp_bt709(out)
    # the ProRes master is not the deliverable (deliver.py tags its file), and only an H.264 file is stamped, so a --preset
    # override to another codec is not held to tags this tool cannot write
    want['bt709'] = not final and (info or {}).get('codec') == 'h264'
    fails, notes = verify(out, want)
    if final and not fails:
        print(f'[export] master {out.name} proven ({notes[-1]}); encoding the Shorts file')
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            final.unlink()                              # --force (out_path refused it otherwise)
        try:
            deliver().encode(out, final, shorts=True)
        except subprocess.CalledProcessError as e:
            sys.exit(f'✗ the Shorts encode failed ({e}); the master is kept: {out}')
        out.unlink()                                    # the master was only the encode's input
        out = final
        want['bt709'] = True
        fails, notes = verify(out, want)
    for n in notes:
        print(f'[export] {n}')
    if fails:
        for f in fails:
            print(f'[export] ✗ {f}')
        sys.exit(f'✗ {len(fails)} check(s) failed; the file is kept for diagnosis: {out}')
    print(f"[export] ✓ {out} (frame size, rate, frame count, bt709 tags{', 300 MB cap' if want['reels'] else ''} verified)")
    if out.name.endswith('-final.mp4') and out.parent == root / 'outputs':
        print(f'[export] next: ./finalize.sh {root.name} --apply')
        if (w, h) == (2160, 3840) and not a.shorts:
            print(f'[export] a 4K vertical job has a second file, the 4K one for YouTube Shorts: '
                  f'uv run lanes/premiere/export.py {a.job} --shorts')
    elif a.shorts and out.parent == root / 'outputs' / 'shorts':
        print(f'[export] next: ./finalize.sh {root.name} --variant shorts --apply')


if __name__ == '__main__':
    main()
