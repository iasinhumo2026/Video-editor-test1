#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""broll-index.py: index a folder of the creator's OWN B-roll (any drive, any size) into a cached library Claude can place from.

  uv run workflows/broll-index.py <folder> [--job projects/<job>] [--jobs N]   # probe + sheet every NEW or CHANGED clip
  uv run workflows/broll-index.py <folder> --pages [--all] [--per-page 6]      # page images for Claude to describe
  uv run workflows/broll-index.py <folder> --describe <descriptions.json>      # merge {"<clip id>": "what is on screen"}

  --cache DIR   where the library lives (default below); --job records it in projects/<job>/broll/library.json

What it keeps per clip: its path (relative to the folder), size and mtime (the cache key), duration, fps, stored and
DISPLAY size (a phone clip's rotation applied), orientation, whether it has audio, HDR, a 4-frame contact sheet, a
`name_hint` read off its folders and file name, `camera_name` (the file name says nothing: C0001, IMG_1234, GX010123)
and an empty `description` that Claude fills (the `broll-own` skill's describe step). Nothing here calls a paid API.

THE CACHE lives in projects/_broll-library/<folder>-<hash of its path>/ (index.json, sheets/, pages/), never in the
B-roll folder itself: an external drive may be read-only (an NTFS or camera-formatted card on a Mac), the creator's
library should not fill up with sidecar files, and the index has to outlive any one job. projects/ is local to this
machine and kept out of git and out of the client package. A re-run only probes what is new or changed (path, size,
mtime); a clip that was renamed or moved inside the folder keeps its probe, sheet and description (same size and
mtime), which is what the pre-trim tip ("name the file by what's on screen") does to a library after it is indexed.

Skipped, by design: hidden files and folders (macOS `._` AppleDouble files on an exFAT drive, .Spotlight-V100,
.Trashes), files that are not video (counted by extension, never listed one by one: a camera card carries an XML
sidecar per clip), a video file ffmpeg cannot read (BRAW, R3D: listed under `unreadable` with the reason, cached so a
re-run does not re-probe it) and anything under half a second.
"""
import argparse, hashlib, io, json, os, re, shutil, subprocess, sys, time
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.mkv', '.avi', '.mts', '.m2ts', '.mxf', '.webm', '.mpg', '.mpeg', '.wmv', '.3gp',
             '.flv', '.ts', '.dv', '.braw', '.r3d'}
SKIP_DIRS = {'$RECYCLE.BIN', 'System Volume Information'}
MIN_DUR = 0.5
SHEET_FRAMES = 4          # frames per clip sheet, at (k + 0.5) / 4 of its length: never the shaky first or last second
TILE_H = 160              # sheet tile height; the width follows the clip's display aspect (a portrait clip stays narrow)
GAP = 4
LABEL_H = 24
SAVE_EVERY = 25           # an interrupted run on a terabyte drive keeps what it finished
# file-name words that say nothing about what is on screen: a camera's own naming, or an editor's
CAMERA_WORDS = {'img', 'mvi', 'dsc', 'dji', 'gopr', 'pxl', 'vid', 'mah', 'mov', 'clip', 'video', 'movie', 'untitled',
                'broll', 'roll', 'final', 'edit', 'export', 'copy', 'take', 'shot', 'new', 'proxy', 'render', 'raw',
                'cam', 'camera', 'rec', 'recording', 'screen', 'file', 'trim', 'trimmed', 'version'}


def default_cache(folder):
    root = Path(folder).expanduser().resolve()
    slug = re.sub(r'[^a-z0-9]+', '-', root.name.lower()).strip('-') or 'library'
    return REPO / 'projects' / '_broll-library' / f"{slug[:40]}-{hashlib.sha1(str(root).encode('utf-8')).hexdigest()[:8]}"


def clip_id(rel, taken):
    """Ten hex of the path's sha1: stable across runs, short enough to write by hand. A collision takes 16."""
    h = hashlib.sha1(rel.encode('utf-8')).hexdigest()
    return h[:10] if taken.get(h[:10], rel) == rel else h[:16]


def words_of(text):
    s = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', text)          # HimOnThePhone -> Him On The Phone
    return re.findall(r'[^\W_]+', s)                       # letters and digits in any script; dashes and _ split


def says_something(w):
    """A file-name word that could describe a picture: no digits (C0001, A001, 0101XY, a date) and no camera word."""
    return not any(ch.isdigit() for ch in w) and w.lower() not in CAMERA_WORDS


def is_camera_name(stem):
    return not [w for w in words_of(stem) if len(w) >= 3 and says_something(w)]


def name_hint(rel):
    """The folders and the file name as words, a camera's own tokens dropped: `Phone calls/him dialing.mp4` ->
    'phone calls him dialing'. The matcher reads it beside the description, so a library named by what is on screen
    needs no description at all."""
    return ' '.join(w.lower() for p in Path(rel).with_suffix('').parts for w in words_of(p) if says_something(w))


def ratio(s):
    n, _, d = str(s or '').partition('/')
    try:
        v = float(n) / float(d or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0
    return v


def probe(path):
    """(info, None) or (None, why). JSON, never csv: ffprobe 9 prints a timecoded file's video row twice in csv."""
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-of', 'json', '-show_format', '-show_streams', str(path)],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    except subprocess.TimeoutExpired:
        return None, 'ffprobe timed out'
    if r.returncode:
        why = ((r.stderr or '').strip().splitlines() or ['ffprobe failed'])[-1]
        return None, why.replace(f'{path}: ', '')[:200]
    try:
        d = json.loads(r.stdout or '{}')
    except json.JSONDecodeError:
        return None, 'ffprobe printed no JSON'
    streams = d.get('streams') or []
    vs = [s for s in streams if s.get('codec_type') == 'video' and not (s.get('disposition') or {}).get('attached_pic')]
    if not vs:
        return None, 'no video stream'
    v = vs[0]
    w, h = int(v.get('width') or 0), int(v.get('height') or 0)
    if not (w and h):
        return None, f"no picture size (ffmpeg cannot decode {v.get('codec_name') or 'this codec'}: export an H.264/HEVC/ProRes copy)"
    rot = 0
    for sd in v.get('side_data_list') or []:
        if 'rotation' in sd:
            rot = int(round(float(sd['rotation'])))
    if not rot and (v.get('tags') or {}).get('rotate'):
        rot = int(round(float(v['tags']['rotate'])))
    rot %= 360
    dw, dh = (h, w) if rot in (90, 270) else (w, h)
    dur = ratio(v.get('duration')) or ratio((d.get('format') or {}).get('duration'))
    if dur < MIN_DUR:
        return None, f'{dur:.2f} s long: under {MIN_DUR} s'
    fps = v.get('avg_frame_rate') if ratio(v.get('avg_frame_rate')) else v.get('r_frame_rate')
    return dict(duration=round(dur, 3), fps=fps, fps_float=round(ratio(fps), 3), width=w, height=h, rotation=rot,
                display=[dw, dh], orientation='landscape' if dw > dh else 'portrait' if dh > dw else 'square',
                audio=any(s.get('codec_type') == 'audio' for s in streams), codec=v.get('codec_name'),
                hdr=v.get('color_transfer') in ('arib-std-b67', 'smpte2084')), None


def grab(path, t, h=TILE_H):
    """One frame as JPEG bytes, upright (ffmpeg applies the rotation on decode), or None."""
    try:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', f'{max(0.0, t):.3f}', '-i', str(path),
                            '-frames:v', '1', '-vf', f'scale=-2:{h}', '-f', 'image2pipe', '-c:v', 'mjpeg', '-q:v', '3', '-'],
                           capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        return None
    return r.stdout if r.returncode == 0 and r.stdout else None


def make_sheet(path, info, out):
    from PIL import Image
    dw, dh = info['display']
    tw = max(2, round(TILE_H * dw / dh / 2) * 2)
    tiles = []
    for k in range(SHEET_FRAMES):
        b = grab(path, info['duration'] * (k + 0.5) / SHEET_FRAMES) or grab(path, 0)
        tiles.append(Image.open(io.BytesIO(b)).convert('RGB') if b else Image.new('RGB', (tw, TILE_H), (48, 48, 48)))
    sheet = Image.new('RGB', (sum(t.width for t in tiles) + GAP * (len(tiles) - 1), TILE_H), (0, 0, 0))
    x = 0
    for t in tiles:
        sheet.paste(t, (x, 0))
        x += t.width + GAP
    tmp = out.with_name(out.stem + '.part.jpg')
    sheet.save(tmp, 'JPEG', quality=82)
    os.replace(tmp, out)


def walk(root):
    """[(rel posix path, stat)] of every video file, plus {ext: count} of what was not video and walk errors."""
    found, ignored, errors = [], {}, []
    for dirpath, dirs, files in os.walk(root, onerror=lambda e: errors.append(str(e))):
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS)
        for f in sorted(files):
            if f.startswith('.'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in VIDEO_EXT:
                ignored[ext or '(none)'] = ignored.get(ext or '(none)', 0) + 1
                continue
            p = os.path.join(dirpath, f)
            try:
                st = os.stat(p)
            except OSError as e:
                errors.append(str(e))
                continue
            found.append((Path(os.path.relpath(p, root)).as_posix(), st))
    return found, ignored, errors


def load_index(cache):
    p = Path(cache) / 'index.json'
    if p.exists():
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    return {'version': 1, 'clips': [], 'unreadable': []}


def save_index(cache, idx):
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    tmp = cache / 'index.json.part'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(idx, f, indent=1, ensure_ascii=False)
    os.replace(tmp, cache / 'index.json')


def build(folder, cache, jobs=4, log=print):
    """Index `folder` into `cache`. Returns the counts: probed / reused / renamed / dropped / unreadable."""
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        sys.exit(f'✗ {root} is not a folder (is the drive plugged in?)')
    cache = Path(cache)
    (cache / 'sheets').mkdir(parents=True, exist_ok=True)
    old = load_index(cache)
    found, ignored, errors = walk(root)
    here = {rel for rel, _ in found}
    by_path = {c['path']: c for c in old.get('clips', [])}
    bad_by_path = {u['path']: u for u in old.get('unreadable', [])}
    # a vanished path whose (size, mtime) a NEW path carries is the same file renamed or moved: keep its work
    gone = {(c['size'], c['mtime_ns']): c for c in old.get('clips', []) if c['path'] not in here}
    taken, clips, bad, todo = {}, [], [], []
    n = dict(probed=0, reused=0, renamed=0, dropped=0, unreadable=0)

    def entry(rel, st, info, prev=None):
        cid = clip_id(rel, taken)
        taken[cid] = rel
        c = dict(id=cid, path=rel, size=st.st_size, mtime_ns=st.st_mtime_ns, **info,
                 sheet=f'sheets/{cid}.jpg', name_hint=name_hint(rel), camera_name=is_camera_name(Path(rel).stem),
                 description=(prev or {}).get('description', ''))
        return c

    for rel, st in found:
        c = by_path.get(rel)
        u = bad_by_path.get(rel)
        if c and (c['size'], c['mtime_ns']) == (st.st_size, st.st_mtime_ns) and (cache / c['sheet']).exists():
            taken[c['id']] = rel
            c.update(name_hint=name_hint(rel), camera_name=is_camera_name(Path(rel).stem))   # cheap: re-read every run
            clips.append(c); n['reused'] += 1
        elif u and (u['size'], u['mtime_ns']) == (st.st_size, st.st_mtime_ns):
            bad.append(u); n['unreadable'] += 1
        elif (st.st_size, st.st_mtime_ns) in gone and (cache / gone[(st.st_size, st.st_mtime_ns)]['sheet']).exists():
            prev = gone.pop((st.st_size, st.st_mtime_ns))
            info = {k: prev[k] for k in ('duration', 'fps', 'fps_float', 'width', 'height', 'rotation', 'display',
                                         'orientation', 'audio', 'codec', 'hdr')}
            c = entry(rel, st, info, prev)
            if c['sheet'] != prev['sheet']:
                os.replace(cache / prev['sheet'], cache / c['sheet'])
            clips.append(c); n['renamed'] += 1
        else:
            todo.append((rel, st))
    n['dropped'] = len([c for c in old.get('clips', []) if c['path'] not in here]) - n['renamed']

    def work(rel, st):
        info, why = probe(root / rel)
        if why:
            return rel, st, None, why
        # a worker never takes an id (the main thread does, in one place): its sheet lands under a scratch name
        tmp_sheet = cache / 'sheets' / f"tmp-{hashlib.sha1(rel.encode('utf-8')).hexdigest()}.jpg"
        make_sheet(root / rel, info, tmp_sheet)
        return rel, st, (info, tmp_sheet), None

    idx = dict(version=1, root=str(root), cache=str(cache), clips=clips, unreadable=bad, ignored=ignored, errors=errors[:50])
    if todo:
        log(f'probing {len(todo)} clip(s) with {jobs} worker(s) ({len(clips)} cached)…')
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as ex:
        futs = [ex.submit(work, rel, st) for rel, st in todo]
        for fu in as_completed(futs):
            rel, st, got, why = fu.result()
            prev = by_path.get(rel)          # a CHANGED file: its old description no longer describes it
            if why:
                bad.append(dict(path=rel, size=st.st_size, mtime_ns=st.st_mtime_ns, why=why)); n['unreadable'] += 1
            else:
                info, tmp_sheet = got
                c = entry(rel, st, info)
                os.replace(tmp_sheet, cache / c['sheet'])
                clips.append(c); n['probed'] += 1
                if prev and prev['id'] != c['id'] and (cache / prev['sheet']).exists():
                    (cache / prev['sheet']).unlink()
            done += 1
            if done % SAVE_EVERY == 0:
                save_index(cache, idx)
                log(f'  {done}/{len(todo)}')
    clips.sort(key=lambda c: c['path'])
    bad.sort(key=lambda u: u['path'])
    keep = {c['sheet'] for c in clips}
    for p in (cache / 'sheets').glob('*.jpg'):      # a deleted clip's sheet goes with it
        if f'sheets/{p.name}' not in keep:
            p.unlink()
    idx.update(updated=time.strftime('%Y-%m-%dT%H:%M:%S'), counts=dict(clips=len(clips), unreadable=len(bad),
               undescribed=sum(1 for c in clips if not c.get('description'))))
    save_index(cache, idx)
    return n


def pages(cache, every=False, per=6, log=print):
    """Page images of the clips still to describe (camera-named ones only, unless `every`): one image per `per` clips,
    each row labelled with its number, id, length and path. Returns [{page, file, ids}] (also pages/pages.json)."""
    from PIL import Image, ImageDraw, ImageFont
    cache = Path(cache)
    idx = load_index(cache)
    sel = [c for c in idx['clips'] if not c.get('description') and (every or c.get('camera_name'))]
    sel.sort(key=lambda c: (not c.get('camera_name'), c['path']))
    out_dir = cache / 'pages'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    try:                                             # Inter ships with the repo and covers accented names
        font = ImageFont.truetype(str(REPO / 'assets' / 'fonts' / 'Inter-Regular.otf'), 15)
    except OSError:
        font = ImageFont.load_default()
    made = []
    for i in range(0, len(sel), per):
        rows = sel[i:i + per]
        sheets = [Image.open(cache / c['sheet']).convert('RGB') for c in rows]
        W = max(max(s.width for s in sheets), 640)
        page = Image.new('RGB', (W, sum(LABEL_H + s.height + GAP for s in sheets)), (16, 16, 16))
        d = ImageDraw.Draw(page)
        y = 0
        for k, (c, s) in enumerate(zip(rows, sheets), start=i + 1):
            d.text((6, y + 4), f"#{k}  {c['id']}  {c['duration']:.1f}s {c['orientation']}  {c['path']}", fill=(255, 220, 90), font=font)
            page.paste(s, (0, y + LABEL_H))
            y += LABEL_H + s.height + GAP
        name = f'page-{len(made) + 1:03d}.jpg'
        page.save(out_dir / name, 'JPEG', quality=80)
        made.append(dict(page=len(made) + 1, file=str(out_dir / name), ids=[c['id'] for c in rows]))
    with open(out_dir / 'pages.json', 'w', encoding='utf-8') as f:
        json.dump(made, f, indent=1, ensure_ascii=False)
    left = sum(1 for c in idx['clips'] if not c.get('description'))
    log(f'{len(sel)} clip(s) on {len(made)} page(s) in {out_dir} ({left} undescribed in all'
        + ('' if every else '; camera-named ones only, --all for the rest') + ')')
    for m in made:
        log(f"  {Path(m['file']).name}: " + ', '.join(m['ids']))
    return made


def describe(cache, mapping):
    """Merge {id: description} into the index; an unknown id refuses the whole merge (a typo would silently drop one)."""
    idx = load_index(cache)
    by_id = {c['id']: c for c in idx['clips']}
    unknown = sorted(k for k in mapping if k not in by_id)
    if unknown:
        sys.exit(f'✗ not in the index (nothing written): {", ".join(unknown)}')
    for k, v in mapping.items():
        by_id[k]['description'] = str(v).strip()
    idx.setdefault('counts', {})['undescribed'] = sum(1 for c in idx['clips'] if not c.get('description'))
    save_index(cache, idx)
    return len(mapping)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('folder', help='the B-roll folder (an external drive is fine: nothing is written to it)')
    ap.add_argument('--cache', help='where the library lives (default: projects/_broll-library/<folder>-<hash>/)')
    ap.add_argument('--job', help='record this library in projects/<job>/broll/library.json')
    ap.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1), help='clips probed at once (default 4)')
    ap.add_argument('--pages', action='store_true', help='write page images of the clips still to describe')
    ap.add_argument('--all', action='store_true', help='with --pages: every undescribed clip, not only camera-named ones')
    ap.add_argument('--per-page', type=int, default=6)
    ap.add_argument('--describe', metavar='JSON', help='merge {"<clip id>": "description"} into the index')
    a = ap.parse_args(argv)
    cache = Path(a.cache).resolve() if a.cache else default_cache(a.folder)
    if a.describe:
        with open(a.describe, encoding='utf-8') as f:
            m = json.load(f)
        print(f'{describe(cache, m)} description(s) merged into {cache / "index.json"}')
        return 0
    if a.pages:
        if not (cache / 'index.json').exists():
            sys.exit(f'✗ no index at {cache}: index the folder first')
        pages(cache, every=a.all, per=max(1, a.per_page))
        return 0
    n = build(a.folder, cache, jobs=a.jobs)
    idx = load_index(cache)
    c = idx['counts']
    print(f"✓ {c['clips']} clip(s) indexed: {n['probed']} probed, {n['reused']} cached, {n['renamed']} renamed/moved, "
          f"{n['dropped']} gone · {c['unreadable']} unreadable · {c['undescribed']} undescribed")
    print(f'  library: {cache / "index.json"}')
    for u in idx['unreadable'][:10]:
        print(f"  ⚠ {u['path']}: {u['why']}")
    if len(idx['unreadable']) > 10:
        print(f"  ⚠ … {len(idx['unreadable']) - 10} more unreadable (index.json `unreadable`)")
    hdr = [x['path'] for x in idx['clips'] if x.get('hdr')]
    if hdr:
        print(f'  ⚠ {len(hdr)} HDR clip(s) (HLG/PQ), e.g. {hdr[0]}: they are placed without tone mapping and will look '
              'washed out next to SDR footage; export SDR copies')
    if idx.get('ignored'):
        print('  not video, skipped: ' + ', '.join(f'{k} ×{v}' for k, v in sorted(idx['ignored'].items())))
    if a.job:
        j = Path(a.job).resolve()
        if not j.is_dir():
            sys.exit(f'✗ --job {a.job}: no such job folder')
        (j / 'broll').mkdir(exist_ok=True)
        with open(j / 'broll' / 'library.json', 'w', encoding='utf-8') as f:
            json.dump(dict(index=str(cache / 'index.json'), root=idx['root']), f, indent=1, ensure_ascii=False)
        print(f'  recorded in {j / "broll" / "library.json"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
