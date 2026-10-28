"""Track a piece of on-screen text through a placed recording render, frame by frame, for a highlight overlay that
stays locked to its target through Screen Studio's zooms (2026-10-03: "an animated red rectangle on top of the
screen recording to show what we're pointing at"). OCR is pii-scan.py's own shim (Apple Vision on macOS).

  uv run workflows/track-text.py <render.mp4> --match "CLAUDE.md" --from 4.0 --to 9.0 --out projects/<job>/review/tracks/r16-claude-md.json
      [--pad 14,8]        px around the text box, x,y (1920 authoring frame)
      [--row 380,1500]    widen the box to this x span (a Finder list row), keep the text's own y span
      [--union]           every block matching inside the window, unioned (a long list of skills)
      [--region x0,y0,x1,y1] only blocks inside this rect (1920 frame) count
      [--smooth 7]        rolling median over 7 frames
      [--span "7k views in 3 days"]  narrow the matched line to this phrase: Vision boxes whole lines, so the phrase's x
                          span is its character share of the line (prose in one font; checked on a frame before use)

Output: {"fps", "render", "match", "frames": {frame: [x0, y0, x1, y1]}} in the 1920x1080 authoring frame, render-relative
frames; a frame where the text was not read is filled from its neighbours (linear), never left empty, and the gaps are
listed so a hold or a fade can be decided on purpose. The track drives presets/youtube/default/highlight/build.py.
"""
import argparse, importlib.util, json, re, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

for _s in (sys.stdout, sys.stderr):   # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

spec = importlib.util.spec_from_file_location('pii', Path(__file__).resolve().with_name('pii-scan.py'))
pii = importlib.util.module_from_spec(spec); spec.loader.exec_module(pii)
FPS = 24000 / 1001


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('render'); ap.add_argument('--match', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--from', dest='t0', type=float, default=0.0); ap.add_argument('--to', dest='t1', type=float, default=None)
    ap.add_argument('--pad', default='14,8'); ap.add_argument('--row', default=None); ap.add_argument('--union', action='store_true')
    ap.add_argument('--region', default=None); ap.add_argument('--span', default=None)
    ap.add_argument('--smooth', type=int, default=1, help='rolling median over N frames (odd): a unioned list box jitters as names scroll')
    a = ap.parse_args()
    px, py = (float(v) for v in a.pad.split(','))
    region = [float(v) for v in a.region.split(',')] if a.region else None
    rx = [float(v) for v in a.row.split(',')] if a.row else None
    rx_ = re.compile(a.match, re.I)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        args = ['ffmpeg', '-v', 'error', '-ss', f'{a.t0:.4f}', '-i', a.render]
        if a.t1: args += ['-t', f'{a.t1 - a.t0:.4f}']
        subprocess.run(args + ['-vf', 'scale=1920:-1', *passthrough(), str(td / 'f%05d.png')], check=True)
        files = sorted(td.glob('f*.png'))
        shim = pii.compile_shim(td)
        rows, err = pii.ocr_rows(shim, files)
        f0 = round(a.t0 * FPS)
        boxes = {}
        for path, box in rows:
            if not box: continue
            x0, y0, x1, y1, text = box
            if not rx_.search(text): continue
            if a.span:
                i = text.lower().find(a.span.lower())
                if i < 0: continue
                w = (x1 - x0) / max(1, len(text))
                x0, x1 = x0 + w * i, x0 + w * (i + len(a.span))
            if region and not (x0 >= region[0] and y0 >= region[1] and x1 <= region[2] and y1 <= region[3]): continue
            n = f0 + int(Path(path).stem[1:]) - 1
            b = boxes.get(n)
            if b and a.union: boxes[n] = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]
            elif not b: boxes[n] = [x0, y0, x1, y1]
    if not boxes: sys.exit(f'✗ "{a.match}" was never read between {a.t0} and {a.t1}')
    lo, hi = min(boxes), max(boxes)
    frames, gaps, known = {}, [], sorted(boxes)
    for n in range(lo, hi + 1):
        if n in boxes: b = boxes[n]
        else:
            gaps.append(n)
            p = max(k for k in known if k < n); q = min(k for k in known if k > n); w = (n - p) / (q - p)
            b = [boxes[p][i] + (boxes[q][i] - boxes[p][i]) * w for i in range(4)]
        x0, y0, x1, y1 = b
        if rx: x0, x1 = rx
        frames[n] = [round(x0 - px, 1), round(y0 - py, 1), round(x1 + px, 1), round(y1 + py, 1)]
    if a.smooth > 1:
        ks, h = sorted(frames), a.smooth // 2
        raw = {k: frames[k] for k in ks}
        for i, k in enumerate(ks):
            win = [raw[ks[j]] for j in range(max(0, i - h), min(len(ks), i + h + 1))]
            frames[k] = [round(sorted(b[c] for b in win)[len(win) // 2], 1) for c in range(4)]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({'fps': '24000/1001', 'render': a.render, 'match': a.match, 'frames': frames, 'gaps': gaps}, open(a.out, 'w'), indent=None)
    print(f'{len(frames)} frames {lo}-{hi} tracked ({len(gaps)} filled); first {frames[lo]} last {frames[hi]} -> {a.out}')


if __name__ == '__main__':
    main()
