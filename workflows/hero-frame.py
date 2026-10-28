#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["mediapipe==0.10.14", "opencv-python-headless", "numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""hero-frame.py — CAST a still of the creator for a graphic: score every kept frame, sheet the best, pick one, prove it.

    uv run workflows/hero-frame.py projects/<job> --id g1                  # score → review/hero-frames/g1.candidates.json + g1.sheet.jpg
    uv run workflows/hero-frame.py projects/<job> --id g1 --pick 45.337    # extract that frame → assets/g1-frame.jpg + review/hero-frames/g1.pick.json

    --raw <file>   the source clip (default: the first video under raw/)
    --all          score the whole raw; default scores ONLY the EDL's kept spans (transcript/cuts.json), so the still is a frame of the EDITED video
    --top N        candidates on the sheet (default 12, at least 1.5 s apart)
    --fps N        scoring sample rate (default 6, snapped to a whole-frame stride of the source)
    --out <path>   where --pick writes the still, job-relative (default assets/<id>-frame.jpg)

Why this exists (2026-09-13): a hook graphic showed "a real frame of this video" inside a player window, and the frame was
the one the planner had grabbed at the START of the beat. A beat starts on a word, so that is a face mid-word by
construction — eyes half shut, the mouth caught between two sounds. Nothing in the pipeline knew what a bad frame of a
person was. This tool does: it measures every candidate with MediaPipe face mesh and refuses a pick that fails.

The score, per frame:  eyes open (eye aspect ratio, both eyes)  ·  mouth closed (mouth aspect ratio)  ·  iris centred
(gaze)  ·  frontal (nose between the cheeks)  ·  head level (pitch)  ·  a hint of smile rewarded.  The sheet RANKS; the
pick is made BY EYE off the sheet (the score cannot see a grimace); --pick re-measures the exact frame and holds it to
the thresholds below before anything is written. A candidate's t is that frame's own time floored to the millisecond,
so --pick, the sheet and a plain `ffmpeg -ss <t>` all land on the frame that was scored (2026-09-22: the `fps` filter
labelled frames up to half a sample early, and a mouth-closed #5 extracted mid-word).

The rule this enforces: graphics-plan § THE HERO-FRAME GATE. mediapipe is pinned: 1.0 dropped the solutions API and
its tasks graph aborts on macOS inside the Metal helper ("Service is unavailable"), CPU delegate or not.
"""
import argparse, json, math, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)
from cv2_io import imwrite  # noqa: E402  (never cv2.imwrite: a non-ASCII Windows path lost the sheet in silence)

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import cv2

SCORE_LONG = 960                      # scoring long side: face mesh is stable here and decode stays cheap
TILE_LONG = 640                       # contact-sheet tile long side
CROP = 2.0                            # the mesh measures a square this many face-boxes wide (see Scorer)
THRESHOLDS = dict(ear_min=0.20, mar_max=0.06, gaze_max=0.06, yaw_max=0.25)
VIDEO_EXT = {'.mp4', '.mov', '.mkv', '.m4v', '.mxf', '.avi', '.MP4', '.MOV'}


def find_raw(job, raw_arg):
    if raw_arg:
        p = Path(raw_arg)
        return p if p.is_absolute() else (job / p)
    vids = sorted(p for p in (job / 'raw').glob('*') if p.suffix in VIDEO_EXT)
    if not vids:
        sys.exit(f'no video under {job / "raw"}; pass --raw')
    return vids[0]


def kept_spans(job, raw, use_all):
    cuts = job / 'transcript' / 'cuts.json'
    if use_all or not cuts.exists():
        if not use_all:
            print(f'⚠ no {cuts.relative_to(job)}: scoring the WHOLE raw (the still may come from a killed take)')
        return None
    segs = json.load(open(cuts, encoding='utf-8'))['segments']
    spans = [(float(s['start']), float(s['end'])) for s in segs
             if not s.get('clip') or Path(s['clip']).name == raw.name]
    if not spans:
        print(f'⚠ no cuts.json segment names {raw.name}: scoring the WHOLE raw')
        return None
    return spans


def frame_times(raw):
    """Every source frame's time as ffmpeg's -ss counts it (seconds from the file's start), in presentation order.

    Read off the packets, no decode. The n-th entry is the n-th frame the decoder hands the filter graph, so a
    `select` stride maps each sample back to the exact frame it was, CFR or not. Discarded packets never decode.
    """
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'format=start_time:packet=pts_time,flags', '-of', 'csv', str(raw)],
                         capture_output=True, text=True, check=True).stdout
    start, ts = 0.0, []
    for f in (line.split(',') for line in out.splitlines()):
        if len(f) < 2 or f[1] in ('', 'N/A'):
            continue
        if f[0] == 'format':
            start = float(f[1])
        elif f[0] == 'packet' and 'D' not in (f[2] if len(f) > 2 else ''):
            ts.append(float(f[1]))
    if not ts:
        sys.exit(f'no frame timestamps in {raw}')
    return sorted(t - start for t in ts)


def stamp(t):
    """A frame's label: its time floored to the ms, so an accurate seek to the label (first frame at or after it)
    is that frame. Rounding can land past it, and then every seek is the NEXT frame."""
    return math.floor(t * 1000) / 1000


def raw_size(raw):
    """The raw's width x height AS DECODED. ffmpeg auto-rotates before any filter, so a phone clip stored 3840x2160
    with a -90 display matrix arrives 2160x3840; older ffprobe reports the turn as a `rotate` tag instead."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height:stream_side_data=rotation:stream_tags=rotate', '-of', 'json', str(raw)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)['streams'][0]
    rot = next((sd['rotation'] for sd in s.get('side_data_list', []) if 'rotation' in sd),
               s.get('tags', {}).get('rotate', 0))
    w, h = int(s['width']), int(s['height'])
    return (h, w) if round(float(rot)) % 180 else (w, h)


def fit(w, h, long):
    """w x h with the long side capped at `long`, the aspect kept, both sides even. Every metric is a ratio of pixel
    distances, so a squashed frame moves them all: a 9:16 raw scaled to 960x540 read open eyes as shut (2026-09-22)."""
    k = min(1.0, long / max(w, h))
    return max(2, round(w * k / 2) * 2), max(2, round(h * k / 2) * 2)


def scoring_size(raw):
    """The one size the scoring pass and --pick both measure at, so a candidate re-measures identically."""
    return fit(*raw_size(raw), SCORE_LONG)


def ffmpeg_decode(raw, stride, w, h):
    # a whole-frame stride, not the `fps` filter: fps snaps to its own grid and hands over a frame up to half a
    # sample away from the n/fps it is labelled. Passthrough sync stops the muxer re-padding `select` to a constant rate.
    # Software decode, never -hwaccel: VideoToolbox drops the frames it cannot decode (a Sony H.264 4:2:2 10-bit raw),
    # select counts only what arrives, and every later label names another frame (2026-09-22). Software is also
    # ~1.9x faster on 4K HEVC here, since the frames come back to the CPU for the scale anyway.
    cmd = ['ffmpeg', '-v', 'error', '-i', str(raw), '-vf', f'select=not(mod(n\\,{stride})),scale={w}:{h}',
           *passthrough(), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=w * h * 3 * 4)


def one_frame(raw, t, w=None, h=None):
    """The exact frame at t (accurate seek), as RGB. Full resolution unless w/h are given."""
    vf = [f'scale={w}:{h}'] if w else []
    cmd = ['ffmpeg', '-v', 'error', '-ss', f'{t:.6f}', '-i', str(raw), '-frames:v', '1']
    if vf: cmd += ['-vf', ','.join(vf)]
    cmd += ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    buf = subprocess.run(cmd, capture_output=True).stdout
    if not w:   # the size AS DECODED (a rotated phone clip arrives turned), read as JSON: ffprobe 9's csv printed a
        w, h = raw_size(raw)   # timecoded file's video row twice, and the stored size reshaped a turned frame wrong
    if len(buf) < w * h * 3:
        sys.exit(f'could not decode a frame at {t}s from {raw}')
    return np.frombuffer(buf, np.uint8).reshape(h, w, 3)


def face_crop(box, w, h):
    """(x0, y0, side) of a square CROP face-boxes wide around the box (pixels), slid inside the w x h frame."""
    bx, by, bw, bh = box
    s = int(min(CROP * max(bw, bh), w, h))
    x0 = int(max(0, min(w - s, bx + bw / 2 - s / 2)))
    y0 = int(max(0, min(h - s, by + bh / 2 - s / 2)))
    return x0, y0, s


class Scorer:
    """One frame in, its metrics out, and nothing carried between frames: --pick re-measures a candidate on its own.

    The mesh's built-in detector is short-range and never fires on a wide shot (a face ~9% of the frame); a TRACKING
    mesh scored those frames only by carrying a lock from earlier ones, which a lone --pick frame never has, so a #5
    candidate came back "no face" (2026-09-22). So the full-range detector finds the face, and a static mesh measures
    a square crop around it, where the face is big enough for the mesh. Every metric is a ratio, so the crop is free.
    """
    def __init__(self):
        import mediapipe as mp
        self.fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        self.fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, refine_landmarks=True, max_num_faces=1,
                                                  min_detection_confidence=0.5)

    def metrics(self, rgb):
        fh, fw = rgb.shape[:2]
        found = self.fd.process(rgb).detections
        if not found:
            return None
        b = max(found, key=lambda d: d.score[0]).location_data.relative_bounding_box
        x0, y0, s = face_crop((b.xmin * fw, b.ymin * fh, b.width * fw, b.height * fh), fw, fh)
        rgb = np.ascontiguousarray(rgb[y0:y0 + s, x0:x0 + s])
        h, w = rgb.shape[:2]
        r = self.fm.process(rgb)
        if not r.multi_face_landmarks:
            return None
        l = r.multi_face_landmarks[0].landmark
        P = lambda i: np.array([l[i].x * w, l[i].y * h])
        d = lambda a, b: float(np.linalg.norm(a - b))
        ear = lambda o, i, u1, u2, lo1, lo2: (d(P(u1), P(lo1)) + d(P(u2), P(lo2))) / (2 * d(P(o), P(i)) + 1e-6)
        ear_l = ear(33, 133, 160, 158, 144, 153); ear_r = ear(362, 263, 385, 387, 380, 373)
        mw = d(P(78), P(308)); mar = d(P(13), P(14)) / (mw + 1e-6)
        lipc = (P(13) + P(14)) / 2
        smile = ((lipc[1] - P(78)[1]) + (lipc[1] - P(308)[1])) / (2 * mw)      # corners above the lip centre
        gl = (P(468)[0] - P(33)[0]) / (P(133)[0] - P(33)[0] + 1e-6)             # iris centre across the eye, 0.5 = centred
        gr = (P(473)[0] - P(362)[0]) / (P(263)[0] - P(362)[0] + 1e-6)
        gaze = abs((gl + gr) / 2 - 0.5)
        yaw = abs(math.log(d(P(1), P(234)) / (d(P(1), P(454)) + 1e-6)))        # nose tip between the cheeks, 0 = frontal
        eyey = (P(33)[1] + P(263)[1]) / 2
        pitch = (P(1)[1] - eyey) / (P(152)[1] - eyey + 1e-6)                    # nose between eye line and chin, ~0.45 level
        m = dict(ear=round(min(ear_l, ear_r), 3), mar=round(mar, 3), smile=round(smile, 3), gaze=round(gaze, 3),
                 yaw=round(yaw, 3), pitch=round(pitch, 3))
        m['score'] = round(min(m['ear'] / 0.30, 1.0) * 3.0 - max(0.0, m['mar'] - 0.04) * 20 - m['yaw'] * 4
                           - m['gaze'] * 8 + min(max(m['smile'], 0.0), 0.12) * 10 - abs(m['pitch'] - 0.50) * 4, 3)
        return m


def passes(m):
    why = []
    if m['ear'] < THRESHOLDS['ear_min']: why.append(f"eyes not open (ear {m['ear']} < {THRESHOLDS['ear_min']})")
    if m['mar'] > THRESHOLDS['mar_max']: why.append(f"mouth open (mar {m['mar']} > {THRESHOLDS['mar_max']})")
    if m['gaze'] > THRESHOLDS['gaze_max']: why.append(f"gaze off the lens ({m['gaze']} > {THRESHOLDS['gaze_max']})")
    if m['yaw'] > THRESHOLDS['yaw_max']: why.append(f"head turned (yaw {m['yaw']} > {THRESHOLDS['yaw_max']})")
    return why


def score_all(job, raw, spans, fps, top, gid, out_dir):
    sc = Scorer()
    ts = frame_times(raw)
    stride = max(1, round((len(ts) - 1) / (ts[-1] - ts[0]) / fps)) if len(ts) > 1 else 1
    w, h = scoring_size(raw)
    p = ffmpeg_decode(raw, stride, w, h)
    rows, i = [], 0
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3: break
        n = i * stride; i += 1
        if n >= len(ts): break
        t = ts[n]
        if spans and not any(a <= t <= b for a, b in spans): continue
        m = sc.metrics(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
        if m is None: continue
        rows.append(dict(t=stamp(t), **m))
    p.stdout.close(); p.wait()
    if not rows:
        sys.exit('no face found in any scored frame')
    rows.sort(key=lambda r: -r['score'])
    cands = []
    for r in rows:
        if all(abs(r['t'] - c['t']) > 1.5 for c in cands):
            r = dict(r); r['fails'] = passes(r); cands.append(r)
        if len(cands) >= top: break
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = dict(id=gid, raw=str(raw.relative_to(job)) if job in raw.parents else str(raw), kept_only=bool(spans), fps=fps,
               scored=len(rows), thresholds=THRESHOLDS, candidates=cands)
    (out_dir / f'{gid}.candidates.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    # the labelled contact sheet: 4 across, tiles at the raw's aspect (640 long side) decoded at the exact candidate times
    tw, th = fit(w, h, TILE_LONG)
    tiles = []
    for n, c in enumerate(cands, 1):
        tile = cv2.cvtColor(one_frame(raw, c['t'], tw, th), cv2.COLOR_RGB2BGR).copy()
        lines = [f"#{n}  t={c['t']:.3f}", f"score {c['score']}" + ('' if not c['fails'] else '  FAILS')]
        if cv2.getTextSize('  '.join(lines), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0][0] <= tw - 20:
            lines = ['  '.join(lines)]                                   # a portrait tile wraps rather than clip FAILS
        cv2.rectangle(tile, (0, 0), (tw, 8 + 26 * len(lines)), (0, 0, 0), -1)
        for k, line in enumerate(lines):
            cv2.putText(tile, line, (10, 25 + 26 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(tile)
    while len(tiles) % 4: tiles.append(np.zeros((th, tw, 3), np.uint8))
    sheet = np.vstack([np.hstack(tiles[k:k + 4]) for k in range(0, len(tiles), 4)])
    imwrite(out_dir / f'{gid}.sheet.jpg', sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f'{len(rows)} frames scored ({"kept spans only" if spans else "whole raw"}) · top {len(cands)}:')
    for n, c in enumerate(cands, 1):
        print(f"  #{n:<2} t={c['t']:<9} score {c['score']:<6} ear {c['ear']} mar {c['mar']} gaze {c['gaze']} yaw {c['yaw']} smile {c['smile']}"
              + (f"   ✗ {'; '.join(c['fails'])}" if c['fails'] else ''))
    print(f'sheet -> {out_dir / (gid + ".sheet.jpg")}   (pick BY EYE, then --pick <t>)')


def pick(job, raw, t, gid, out_rel, out_dir, spans):
    if spans and not any(a <= t <= b for a, b in spans):
        sys.exit(f'✗ {t}s is not inside a kept span of the EDL: the still must be a frame of the edited video (--all to override)')
    m = Scorer().metrics(one_frame(raw, t, *scoring_size(raw)))
    if m is None:
        sys.exit(f'✗ no face at {t}s')
    why = passes(m)
    if why:
        sys.exit(f'✗ {t}s fails: ' + '; '.join(why) + f'\n  {m}\n  pick another candidate off the sheet')
    out = job / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.6f}', '-i', str(raw), '-frames:v', '1', '-q:v', '2', str(out)], check=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = dict(id=gid, t=t, file=str(out_rel).replace('\\', '/'), raw=str(raw.relative_to(job)) if job in raw.parents else str(raw),
               kept=bool(spans), metrics=m, thresholds=THRESHOLDS, **{'pass': True})
    (out_dir / f'{gid}.pick.json').write_text(json.dumps(doc, indent=1), encoding='utf-8')
    print(f"✓ {gid}: t={t}s  ear {m['ear']} mar {m['mar']} gaze {m['gaze']} yaw {m['yaw']} smile {m['smile']}")
    print(f'  -> {out}\n  -> {out_dir / (gid + ".pick.json")}\n  plan cell: "hero_frame": {{"t": {t}, "file": "{doc["file"]}"}}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job'); ap.add_argument('--id', default='hero'); ap.add_argument('--raw')
    ap.add_argument('--all', action='store_true'); ap.add_argument('--top', type=int, default=12)
    ap.add_argument('--fps', type=float, default=6.0); ap.add_argument('--pick', type=float)
    ap.add_argument('--out')
    a = ap.parse_args()
    job = Path(a.job).resolve()
    raw = find_raw(job, a.raw).resolve()
    spans = kept_spans(job, raw, a.all)
    out_dir = job / 'review' / 'hero-frames'
    if a.pick is None:
        score_all(job, raw, spans, a.fps, a.top, a.id, out_dir)
    else:
        pick(job, raw, a.pick, a.id, a.out or f'assets/{a.id}-frame.jpg', out_dir, spans)


if __name__ == '__main__':
    main()
