#!/usr/bin/env python3
"""grey-source.py: a grey-coded test clip whose every frame names itself, and the decoder that reads a frame back.

  uv run workflows/grey-source.py out.mp4 --fps 24000/1001 --size 1920x1080 --seconds 12 [--audio] [--first N0]
                                   [--timecode 01:00:10:00]
  uv run workflows/grey-source.py --decode grab.png [more.png ...]      # the frame each still shows
  uv run workflows/grey-source.py --decode clip.mp4                     # every frame of a clip, against its own index

THE CODE. Frame n of the clip carries the number N = N0 + n (N0 = --first, default 0) as three flat grey regions:
  the BODY (everything under the band) has luma 16 + (23*N mod 220)                     -> N mod 220
  the BAND (the top 10%, a whole number of 16-px rows) carries the digit b = N div 220, split in two halves:
    its LEFT half has luma 16 + (23*b mod 220), its RIGHT half 16 + (23*(b + 110) mod 220)
A region decodes as 67*(L - 16) mod 220 (67 is the inverse of 23 mod 220), so 220*220 = 48 400 frames are named
exactly. 23 is coprime with 220, so ADJACENT frames sit 23 levels apart (never 1): a grab one frame off cannot pass
for the right one. Give a second source its own --first (say 10000) and a frame of one can never pass for the other:
a remnant of the old clip under a lay reads as the OLD clip, not as a plausible frame of the new one.

THE BAND CHECKS ITSELF: its right half must decode to the left half's digit + 110 (mod 220), so its two halves are
always 110 levels apart. A frame that is one flat colour (black: a gap, a disabled clip; a solid; the body of a
source cropped at 100 % so its band is off the frame) and a band patch that lands on a letterbox bar both fail the
check and decode to None, never to a number. Before this check, a black frame read as frame 0 (2026-09-23 review).

A still is read as Premiere's program grab delivers it (`premiere-bridge.mjs frame`, exportFramePNG): full-range
RGB, R = G = B = round((Y - 16) * 255/219), so Y = 16 + R * 219/255 recovers the code within 0.43 of a level. Nine
program grabs of a grey code on 2026-09-22 all decoded exact (e.g. Y 57 -> RGB 48 -> 57.22). A patch that is not
flat and neutral (a graphic, the grade) is not a grey-coded frame and decodes to None, never to a guess.

WHY (2026-09-22/23): proving the `lay` fix frame-for-frame needed a hand-built grey source, because an ffmpeg
testsrc was too uniform to tell adjacent frames apart (a mean-difference match scored frame 766 at 6.63 against
767 at 6.74), plus a scratch matcher and hand ExtendScript. A float-seconds in-point had rendered the frame before
while every readback said it was right; only a program grab matched to its source frame caught it. The kit is this
file, lanes/premiere/scratch-project.py (a throwaway Premiere job) and lanes/premiere/frame-proof.py (the proof).

Every write reads its own file back and raises unless each frame decodes to its own number, so no caller can build
on a clip this ffmpeg encoded wrong. The file carries `comment=grey-source first=<N0> frames=<n> fps=<rate>` so a
reader can tell a grey source from footage and which numbers it holds. Stdlib only; ffmpeg and ffprobe do the pixels.

A START TIMECODE (--timecode HH:MM:SS:FF, ';' before the frames for drop frame) is stamped as the file's timecode
track, the way camera files carry one; it moves no code (frame n still carries N0 + n). Premiere counts a clip's
item offsets on that clock, not the media's (live, 2026-09-23: a master stamped 01:00:10:00 read a VideoInPoint offset
of 86640 frames), so frame-proof's timecoded case needs a source that has one. `probe` reads it back as `timecode`
and `tc_frames` (0 when the file carries none).

THE FRAMING (`framing()`, frame-proof --motion). The three sample squares say WHICH frame plays, never WHERE: they sit
in three large flat regions, so a transform 22-38 px off the program, or a whole wrong layout mode, still lands each
square in its region and decodes (live, 2026-09-24). Where the source sits is read off its BOUNDARIES instead: the
band's seam, the band line and the source's four edges against black, each placed by the same transform. A boundary
whose two sides are 30+ levels apart is profiled across, and its measured position is compared with where the
transform puts it; a boundary whose outer side is off the frame (a source that fills or overfills it) is read on the
side that shows; a grid of points clear of every boundary must read the grey the transform puts there. The Scale is
PINNED only when two parallel boundaries are measured (an edge of the source as well as a seam): a source that
overfills the frame shows its seam and band line alone, and a zoom about the band line would look the same.
"""
import argparse, json, math, re, subprocess, sys
from fractions import Fraction
from pathlib import Path

STEP, INV, SPAN = 23, 67, 220          # level = 16 + STEP*n mod SPAN; n = INV*(level - 16) mod SPAN
PAIR = SPAN // 2                       # the band's right half carries its left digit + PAIR: 110 levels apart
LIMIT = SPAN * SPAN                    # frames the code can name
TAG = 'grey-source'
FLAT_TOL = 4                           # RGB spread inside a patch still read as one flat, neutral grey
BLACK = 16                             # the luma where no source plays: nothing under the track
EDGE_CONTRAST = 30                     # levels a boundary's two sides must differ by before framing() reads it
EDGE_LEVEL = 10                        # levels a plateau beside a boundary, or a grid point, may sit off its grey
assert STEP * INV % SPAN == 1


class NotSelfConsistent(RuntimeError):
    """A written clip whose frames do not all decode to their own numbers (an ffmpeg build that moves luma)."""


def level(code):
    """The luma that carries one base-220 digit."""
    return 16 + STEP * code % SPAN


def levels(n):
    """(body, band left, band right) luma of frame number n."""
    b = n // SPAN
    return level(n % SPAN), level(b), level((b + PAIR) % SPAN)


def decode_level(y):
    """A measured luma -> its base-220 digit, or None off the 16..235 code range (or unmeasured)."""
    if y is None:
        return None
    yi = round(y)
    return INV * (yi - 16) % SPAN if 16 <= yi <= 235 else None


def decode(body_y, band_l_y, band_r_y):
    """The frame number carried by a (body, band left, band right) luma triple, or None: None when any region is
    unmeasured or off the code, and when the band's halves are not their pair (a flat frame, a mis-framed grab)."""
    lo, hl, hr = decode_level(body_y), decode_level(band_l_y), decode_level(band_r_y)
    if lo is None or hl is None or hr is None or hr != (hl + PAIR) % SPAN:
        return None
    return hl * SPAN + lo


def rgb_to_y(v):
    """Full-range RGB grey (what Premiere's program grab and an ffmpeg RGB decode deliver) -> limited-range luma."""
    return 16 + v * 219 / 255


def band_height(h):
    """The top band: 10% of the frame, a whole number of 16-px macroblock rows (so it never shares one with the body)."""
    return max(16, round(h * 0.10 / 16) * 16)


def patches(w, h):
    """(x, y, side) of the body, band-left and band-right sample squares: the body's at the frame centre of the body,
    the band's at the centres of its two halves, all clear of the seams."""
    b = band_height(h)
    s = max(2, min(32, b // 2, w // 4)) // 2 * 2

    def at(cx, cy):
        return (cx - s // 2) // 2 * 2, (cy - s // 2) // 2 * 2, s

    return at(w // 2, (b + h) // 2), at(w // 4, b // 2), at(3 * w // 4, b // 2)


def geq(first, w, h):
    """The ffmpeg geq luma expression for frame N (plus the --first offset)."""
    n = f'(N+{first})' if first else 'N'
    hi = f'trunc({n}/{SPAN})'
    return (f"if(lt(Y,{band_height(h)}),"
            f"if(lt(X,{w // 2}),16+mod({STEP}*{hi},{SPAN}),16+mod({STEP}*{hi}+{STEP * PAIR % SPAN},{SPAN})),"
            f"16+mod({STEP}*{n},{SPAN}))")


def parse_fps(s):
    """A rational rate. A decimal NTSC rate (23.976, 29.97, 59.94) is refused, never taken literally: 23.976 is
    2997/125, a clip Premiere may conform to 24000/1001, and every expected frame would then be off by the drift."""
    f = Fraction(str(s))
    if f <= 0:
        raise ValueError(f'bad fps {s!r}')
    for k in (24, 30, 48, 60, 120):
        ntsc = Fraction(k * 1000, 1001)
        if f != ntsc and abs(f - ntsc) < Fraction(1, 100):
            raise ValueError(f'fps {s}: write the NTSC rate as {ntsc.numerator}/{ntsc.denominator}')
    return f


def frame_count(rate, seconds, first=0):
    """Frames in `seconds` at `rate`, or ValueError when they do not fit the code from `first`."""
    frames = round(Fraction(str(seconds)) * rate)
    if frames < 1 or first < 0 or first + frames > LIMIT:
        raise ValueError(f'{frames} frames from --first {first} do not fit the {LIMIT}-frame code')
    return frames


def timecode_frames(tc, rate):
    """'HH:MM:SS:FF' (';' or '.' before FF = drop frame) at `rate` -> frames from 00:00:00:00, or ValueError. Drop
    frame skips the first 2 (29.97) or 4 (59.94) numbers of every minute but every tenth, as SMPTE counts it."""
    m = re.fullmatch(r'(\d{1,2}):(\d\d):(\d\d)([:;.])(\d\d)', str(tc).strip())
    base = round(Fraction(rate))
    if not m or int(m.group(2)) > 59 or int(m.group(3)) > 59 or int(m.group(5)) >= base:
        raise ValueError(f'bad timecode {tc!r} at {rate}: HH:MM:SS:FF, FF under {base}')
    hh, mm, ss, ff = (int(m.group(k)) for k in (1, 2, 3, 5))
    drop = 0
    if m.group(4) != ':':
        if base not in (30, 60) or Fraction(rate) == base:
            raise ValueError(f'drop-frame timecode {tc!r} at {rate}: only 30000/1001 and 60000/1001 drop frames')
        drop = base // 15                                      # 2 at 29.97, 4 at 59.94
        if ss == 0 and ff < drop and mm % 10:
            raise ValueError(f'drop-frame timecode {tc!r}: {ff:02d} is a dropped number at the top of minute {mm}')
    minutes = 60 * hh + mm
    return base * (3600 * hh + 60 * mm + ss) + ff - drop * (minutes - minutes // 10)


def parse_size(s):
    w, h = (int(x) for x in str(s).lower().split('x'))
    if w < 16 or h < 64 or w % 2 or h % 2:
        raise ValueError(f'bad size {s!r}: even width >= 16 and even height >= 64 (4:2:0 video, a band above a body)')
    return w, h


def write(out, fps='24000/1001', size='1920x1080', seconds=12.0, audio=False, first=0, timecode=None):
    """Encode the grey-coded clip to `out` (H.264 yuv420p, BT.709 limited range, optional 1 kHz stereo tone, optional
    start timecode), then read it back: raises NotSelfConsistent unless every frame decodes to its own number and the
    timecode reads back as written. Returns (frames, fps, (w, h))."""
    rate, (w, h) = parse_fps(fps), parse_size(size)
    frames = frame_count(rate, seconds, first)
    if timecode:
        timecode_frames(timecode, rate)                        # refused before anything is written
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    # The BT.709 tags go on the FRAMES (setparams), never as output options: `-colorspace bt709 -color_range tv`
    # on the output makes ffmpeg convert the unlabelled geq frames, and that conversion moved luma 85 to 84 and
    # 108 to 107 (measured 2026-09-23), so 165 of 288 frames decoded as other numbers.
    src = (f"nullsrc=s={w}x{h}:r={rate.numerator}/{rate.denominator},format=yuv420p,"
           f"geq=lum='{geq(first, w, h)}':cb=128:cr=128,"
           "setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709")
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', src]
    if audio:
        dur = float(Fraction(frames) / rate)
        cmd += ['-f', 'lavfi', '-i', f'sine=frequency=1000:sample_rate=48000:duration={dur:.6f}']
    cmd += ['-frames:v', str(frames), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '10', '-pix_fmt', 'yuv420p']
    if audio:
        cmd += ['-c:a', 'aac', '-b:a', '256k', '-ac', '2']
    if timecode:
        cmd += ['-timecode', str(timecode)]
    cmd += ['-metadata', f'comment={TAG} first={first} frames={frames} fps={rate.numerator}/{rate.denominator}',
            str(out)]
    subprocess.run(cmd, check=True)
    # The clip proves itself before anything trusts it: every frame must read back as its own number.
    rows = read(out)
    wrong = [k for k, (n, *_) in enumerate(rows) if n != first + k]
    if wrong or len(rows) != frames:
        raise NotSelfConsistent(f'{out}: {len(rows)} of {frames} frames decoded, {len(wrong)} not their own number '
                                f'(first: {wrong[:5]}); this ffmpeg moves luma, so no proof can stand on the clip')
    # compared in FRAMES: ffmpeg stores an accepted spelling canonically ('.' before FF -> ';', 1: -> 01:)
    if timecode and probe(out)['tc_frames'] != timecode_frames(timecode, rate):
        raise NotSelfConsistent(f"{out}: stamped timecode {timecode}, read back {probe(out)['timecode']}")
    return frames, rate, (w, h)


def probe(path):
    """{'w','h','fps' (Fraction),'first','frames','pix_fmt','range','timecode','tc_frames'} of a video or still;
    'first' is None unless it is a grey source. 'timecode' is the start timecode the file carries (on its video stream,
    a tmcd track or the container: camera files put it in any of them), None when it has none; 'tc_frames' is that
    timecode in frames at the file's rate, 0 with no timecode and None when it does not parse."""
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                        'stream=codec_type,width,height,r_frame_rate,pix_fmt,color_range:stream_tags=timecode'
                        ':format_tags=comment,timecode', '-of', 'json', str(path)],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    streams = d.get('streams') or []
    st = next((x for x in streams if x.get('codec_type') == 'video'), {})
    info = {'w': int(st.get('width') or 0), 'h': int(st.get('height') or 0), 'fps': None, 'first': None,
            'frames': None, 'pix_fmt': str(st.get('pix_fmt') or ''), 'range': str(st.get('color_range') or ''),
            'timecode': None, 'tc_frames': 0}
    try:
        info['fps'] = parse_fps(st.get('r_frame_rate'))
    except (ValueError, ZeroDivisionError, TypeError):
        pass
    tcs = [x.get('tags', {}).get('timecode') for x in [st, *streams]] + [(d.get('format') or {}).get('tags', {}).get('timecode')]
    info['timecode'] = next((str(t) for t in tcs if t), None)
    if info['timecode']:
        try:
            info['tc_frames'] = timecode_frames(info['timecode'], info['fps'])
        except (ValueError, TypeError):
            info['tc_frames'] = None
    words = str((d.get('format') or {}).get('tags', {}).get('comment', '')).split()
    if words[:1] == [TAG]:
        kv = dict(x.split('=', 1) for x in words[1:] if '=' in x)
        info['first'], info['frames'] = int(kv.get('first', 0)), int(kv.get('frames', 0)) or None
    return info


def _flat(px):
    """The mean of a patch's bytes if the patch is one flat (and, in RGB, neutral) grey, else None."""
    return sum(px) / len(px) if px and max(px) - min(px) <= FLAT_TOL else None


def measure(path, w=None, h=None, xform=None):
    """Every frame of `path` (one for a still) -> (body_y, band_left_y, band_right_y) in limited-range luma, None for
    a region that is not flat neutral grey. `w`/`h` is the SOURCE's size when `path` is a grab of it at another size
    (a source scaled to fill a sequence): each square is placed where its region's centre lands under that scaling.
    Default: the file's own size. `xform` = (k, px, py, ax, ay) places the source by a Motion transform instead (a
    framing key: lanes/premiere/frame-proof.py --motion): source pixel (x, y) lands on file pixel
    (px + k * (x - ax), py + k * (y - ay)), and each square is scaled by k.

    Nothing is converted between YUV and RGB, because swscale's yuv->rgb is not exact: a full-frame conversion read
    luma 116 as 115 on a 1080x1920 clip, and a 24-px-wide strip of three 8-px squares read 39 as 37.5 (2026-09-23;
    16, 48 and 96 px wide read true). So a YUV file (a clip) gives its Y plane as it is, and an RGB file (a program
    grab) its RGB bytes, the squares cropped first and nothing scaled."""
    i = probe(path)
    fw, fh = i['w'], i['h']
    w, h = (w, h) if w and h else (fw, fh)
    if xform:
        k, px, py, ax, ay = xform
        s = max(2, round(patches(w, h)[0][2] * k) // 2 * 2)
        xy = [(round(px + k * (x + side / 2 - ax) - s / 2) // 2 * 2, round(py + k * (y + side / 2 - ay) - s / 2) // 2 * 2)
              for x, y, side in patches(w, h)]
        if any(x < 0 or y < 0 or x + s > fw or y + s > fh for x, y in xy):
            return [(None, None, None)]                                   # a region off the frame: no reading
    else:
        s = max(2, round(patches(w, h)[0][2] * min(fw / w, fh / h)) // 2 * 2)
        xy = [(round((x + side / 2) * fw / w - s / 2) // 2 * 2, round((y + side / 2) * fh / h - s / 2) // 2 * 2)
              for x, y, side in patches(w, h)]
    yuv = i['pix_fmt'].startswith(('yuv', 'nv', 'gray'))
    full = i['range'] == 'pc' or i['pix_fmt'].startswith('yuvj')          # full-range luma reads like RGB
    crops = ''.join(f'[c{j}]crop={s}:{s}:{x}:{y}[p{j}];' for j, (x, y) in enumerate(xy))
    graph = f"[0:v]split=3[c0][c1][c2];{crops}[p0][p1][p2]hstack=inputs=3,{'extractplanes=y' if yuv else 'format=rgb24'}"
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-filter_complex', graph, '-f', 'rawvideo', '-'],
                         capture_output=True, check=True).stdout
    bpp = 1 if yuv else 3
    row, per = 3 * s * bpp, 3 * s * s * bpp
    out = []
    for k in range(len(raw) // per):
        fr = raw[k * per:(k + 1) * per]
        ys = []
        for j in range(3):
            m = _flat(b''.join(fr[y * row + j * s * bpp:y * row + (j + 1) * s * bpp] for y in range(s)))
            ys.append(None if m is None else m if yuv and not full else rgb_to_y(m))
        out.append(tuple(ys))
    return out


def read(path, w=None, h=None, xform=None):
    """[(frame number or None, body_y, band_left_y, band_right_y)] for every frame of `path`."""
    return [(decode(*lv), *lv) for lv in measure(path, w, h, xform)]


# ── the framing: where the source sits on a grab, read off its boundaries (module docstring, THE FRAMING) ──────────

def geometry(w, h, xform):
    """Where a w x h source's boundaries land under `xform` (measure's (k, px, py, ax, ay)), in the grab's pixels:
    x0/x1 its left/right edge, xs the band's seam, y0/y1 its top/bottom edge, yb the band line."""
    k, px, py, ax, ay = xform
    return {'x0': px - k * ax, 'xs': px + k * (w / 2 - ax), 'x1': px + k * (w - ax),
            'y0': py - k * ay, 'yb': py + k * (band_height(h) - ay), 'y1': py + k * (h - ay)}


def region(x, y, g):
    """'out', 'band_l', 'band_r' or 'body': the part of the code that geometry `g` puts at grab point (x, y)."""
    if not (g['x0'] <= x < g['x1'] and g['y0'] <= y < g['y1']):
        return 'out'
    if y < g['yb']:
        return 'band_l' if x < g['xs'] else 'band_r'
    return 'body'


def boundaries(w, h, g):
    """Every boundary of the code on the grab: (name, axis, source coordinate, grab position, (along from, to),
    region before, region after). Axis 'x' is a vertical line at grab x = position, running down y; 'y' a horizontal
    one. Before/after are the regions at the lower/higher coordinate."""
    b = band_height(h)
    return [('seam', 'x', w / 2, g['xs'], (g['y0'], g['yb']), 'band_l', 'band_r'),
            ('band line', 'y', b, g['yb'], (g['x0'], g['xs']), 'band_l', 'body'),
            ('band line', 'y', b, g['yb'], (g['xs'], g['x1']), 'band_r', 'body'),
            ('top edge', 'y', 0, g['y0'], (g['x0'], g['xs']), 'out', 'band_l'),
            ('top edge', 'y', 0, g['y0'], (g['xs'], g['x1']), 'out', 'band_r'),
            ('bottom edge', 'y', h, g['y1'], (g['x0'], g['x1']), 'body', 'out'),
            ('left edge', 'x', 0, g['x0'], (g['y0'], g['yb']), 'out', 'band_l'),
            ('left edge', 'x', 0, g['x0'], (g['yb'], g['y1']), 'out', 'body'),
            ('right edge', 'x', w, g['x1'], (g['y0'], g['yb']), 'band_r', 'out'),
            ('right edge', 'x', w, g['x1'], (g['yb'], g['y1']), 'body', 'out')]


def plane(path):
    """(width, height, get) of the first frame of `path`: get(x, y) is pixel (x, y)'s limited-range luma. A YUV file
    gives its Y plane as it is and an RGB file (a program grab) its green bytes, converted like measure()'s."""
    i = probe(path)
    fw, fh = i['w'], i['h']
    yuv = i['pix_fmt'].startswith(('yuv', 'nv', 'gray'))
    full = i['range'] == 'pc' or i['pix_fmt'].startswith('yuvj')
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-frames:v', '1', '-vf',
                          'extractplanes=y' if yuv else 'format=rgb24', '-f', 'rawvideo', '-'],
                         capture_output=True, check=True).stdout
    px = raw[:fw * fh] if yuv else raw[1:3 * fw * fh:3]
    lut = [float(v) if yuv and not full else rgb_to_y(v) for v in range(256)]
    return fw, fh, lambda x, y: lut[px[y * fw + x]]


def _read_boundary(get, fw, fh, bd, grey, tol, reach, q):
    """One boundary off the grab -> {name, axis, src, at, kind, got, err, note}, or None when it cannot be read (its
    two sides one grey, too short on the frame, or off the frame by more than `reach`). kind 'pinned': found, err =
    got - at; 'lost': both sides are on the frame and the boundary is not within reach - q of `at`; 'bound': its outer
    side is off the frame and the side that shows holds its grey from tol px past `at` (the border hides how far past);
    'off': that side does not hold, err = how far inside `at` the boundary is at least."""
    name, axis, src, at, (a0, a1), before, after = bd
    lo, hi = grey[before], grey[after]
    if abs(lo - hi) < EDGE_CONTRAST:
        return None
    dim, span = (fw, fh) if axis == 'x' else (fh, fw)
    a0, a1 = max(a0, 0) + tol + 2, min(a1, span) - tol - 2            # clear of the boundaries it runs between
    if a1 <= a0:
        return None
    lines = sorted({min(span - 1, int(a0 + (a1 - a0) * (j + .5) / 16)) for j in range(16)})

    def profile(i0, i1):                                                # mean luma at each position across it
        if axis == 'x':
            return [sum(get(i, r) for r in lines) / len(lines) for i in range(i0, i1)]
        return [sum(get(r, i) for r in lines) / len(lines) for i in range(i0, i1)]

    r = {'name': name, 'axis': axis, 'src': src, 'at': at, 'kind': None, 'got': None, 'err': None, 'note': ''}
    if at - q - 3 >= 0 and at + q + 3 <= dim:                          # both sides show: find it
        i0, i1 = max(0, math.floor(at - reach)), min(dim, math.ceil(at + reach))
        p = profile(i0, i1)
        m0, m1 = sum(p[:q]) / q, sum(p[-q:]) / q
        if abs(m0 - lo) > EDGE_LEVEL or abs(m1 - hi) > EDGE_LEVEL:
            r.update(kind='lost', note=f'reads {m0:.0f} | {m1:.0f} at {at - i0:.0f} / {i1 - at:.0f} px either side of '
                                       f'where the transform puts it, which puts {before} {lo} | {after} {hi} there: '
                                       f'it is not within {reach - q:.0f} px')
            return r
        mid = (m0 + m1) / 2
        xs = [i0 + j + .5 + (mid - p[j]) / (p[j + 1] - p[j]) for j in range(len(p) - 1)
              if (p[j] > mid) != (p[j + 1] > mid)]
        if len(xs) != 1:
            r.update(kind='lost', note=f'{len(xs)} crossings of {mid:.0f} within {reach:.0f} px: not one clean edge')
            return r
        r.update(kind='pinned', got=xs[0], err=xs[0] - at)
        return r
    if at - q - 3 < 0:                                                  # its before side is off the low border
        i0, i1, want, side = max(0, math.ceil(at + tol + 1)), min(dim, math.ceil(at + reach)), hi, after
    else:                                                               # its after side is off the high border
        i0, i1, want, side = max(0, math.floor(at - reach)), min(dim, math.floor(at - tol - 1)), lo, before
    if i1 <= i0:
        return None
    p = profile(i0, i1)
    bad = [j for j, v in enumerate(p) if abs(v - want) > EDGE_LEVEL]
    if not bad:
        r.update(kind='bound')
        return r
    j = max(bad) if side == after else min(bad)                         # the offending pixel furthest inside
    err = i0 + j + 1 - at if side == after else i0 + j - at
    r.update(kind='off', err=err, note=f'the frame reads {p[j]:.0f} {abs(err):.0f} px inside where the transform puts '
                                       f'it, where it puts the {side} ({want})')
    return r


def _distance(x, y, bd):
    """From grab point (x, y) to boundary `bd` (a segment)."""
    _, axis, _, at, (a0, a1), _, _ = bd
    u, v = (x, y) if axis == 'x' else (y, x)
    return math.hypot(u - at, max(a0 - v, 0.0, v - a1))


def framing(path, w, h, xform, n, tol):
    """Where the grab `path` shows frame number `n` of a w x h grey source, against where `xform` (measure's
    (k, px, py, ax, ay), grab pixels) puts it, to `tol` grab pixels (module docstring, THE FRAMING). Returns
    {verdict 'ok'|'fail'|'unmeasured', worst (the largest pinned err, or None), scale (True: pinned by two parallel
    boundaries), boundaries [_read_boundary rows], cover (points read, [(x, y, region, its grey, read)]), why, tol}.

      fail        a boundary more than tol off, not found within reach of where it is put, or short of a frame
                  border it should reach; or a grid point off the grey the transform puts there
      unmeasured  nothing failed, but no measured boundary places the source across (or down) the frame, or the
                  band is too small on the grab to read an edge at tol
      ok          every boundary that shows is within tol and every point reads its grey; `scale` False = the frame
                  border only bounds the Scale (no edge of the source shows)"""
    fw, fh, get = plane(path)
    g = geometry(w, h, xform)
    grey = dict(zip(('body', 'band_l', 'band_r'), levels(n)), out=BLACK)
    b, k = band_height(h), xform[0]
    reach = min(max(4 * tol, 8.0), (k * min(b, h - b, w / 2) - 2) / 2)   # never as far as the next parallel one
    q = max(2, int(reach / 4))                                           # plateau px at each end of a profile
    res = {'verdict': 'unmeasured', 'worst': None, 'scale': False, 'boundaries': [], 'cover': (0, []), 'why': '',
           'tol': tol}
    if reach < tol + q + 1:
        res['why'] = f'the band is {k * b:.0f} px tall on the grab: too small to read an edge within {tol:.1f} px'
        return res
    bds = boundaries(w, h, g)
    rows = [r for r in (_read_boundary(get, fw, fh, bd, grey, tol, reach, q) for bd in bds) if r]
    step = max(4, round(min(fw, fh) / 24))
    pts = {(x, y) for y in range(step // 2, fh, step) for x in range(step // 2, fw, step)}
    pts |= {(x, y) for y in range(step // 2, fh, step) for x in (0, fw - 1)}
    pts |= {(x, y) for x in range(step // 2, fw, step) for y in (0, fh - 1)}
    seen, miss = 0, []
    for x, y in sorted(pts):
        if min(_distance(x + .5, y + .5, bd) for bd in bds) <= tol + 2:
            continue                                                    # a boundary within tol: the rows judge it
        seen += 1
        want, v = region(x + .5, y + .5, g), get(x, y)
        if abs(v - grey[want]) > EDGE_LEVEL:
            miss.append((x, y, want, grey[want], v))
    pinned = [r for r in rows if r['kind'] == 'pinned']
    across = {r['src'] for r in pinned if r['axis'] == 'x'}
    down = {r['src'] for r in pinned if r['axis'] == 'y'}
    res.update(boundaries=rows, cover=(seen, miss), scale=bool(across and down and len(across) + len(down) > 2),
               worst=max((r['err'] for r in pinned), key=abs, default=None))
    if miss or any(r['kind'] in ('lost', 'off') or r['kind'] == 'pinned' and abs(r['err']) > tol for r in rows):
        res['verdict'] = 'fail'
    elif not across or not down:
        res['why'] = f"no boundary that shows places the source {'across' if not across else 'down'} the frame"
    else:
        res['verdict'] = 'ok'
    return res


def show(lv):
    """'body 57.2  band 16.0/126.0' for a measured triple."""
    f = ['-' if v is None else f'{v:.1f}' for v in lv]
    return f'body {f[0]}  band {f[1]}/{f[2]}'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', nargs='*', help='the clip to write (or, with --decode, the stills/clips to read)')
    ap.add_argument('--fps', default='24000/1001', help='rational frame rate (default 24000/1001)')
    ap.add_argument('--size', default='1920x1080', help='WxH (default 1920x1080)')
    ap.add_argument('--seconds', type=float, default=12.0, help='length (default 12)')
    ap.add_argument('--audio', action='store_true', help='add a 1 kHz stereo tone the length of the picture')
    ap.add_argument('--first', type=int, default=0, help='the number frame 0 carries (a second source: 10000)')
    ap.add_argument('--timecode', help="start timecode to stamp, HH:MM:SS:FF (';' before FF: drop frame), as a "
                                       'camera file carries one (default: none)')
    ap.add_argument('--decode', action='store_true', help='read the named files instead of writing one')
    a = ap.parse_args(argv)
    if not a.out:
        ap.error('name the clip to write, or the files to --decode')
    if a.decode:
        bad = 0
        for p in a.out:
            info, rows = probe(p), read(p)
            base = info['first']
            for k, (n, *lv) in enumerate(rows):
                where = f'{p}' + (f' frame {k}' if len(rows) > 1 else '')
                if n is None:
                    bad += 1
                    print(f'{where}: not a grey-coded frame ({show(lv)})')
                    continue
                own = '' if base is None or len(rows) == 1 else ('' if n == base + k else f'  MISMATCH (index {k} carries {base + k})')
                bad += bool(own)
                print(f'{where}: number {n}' + (f' = source frame {n - base}' if base is not None and len(rows) > 1 else '')
                      + f'  ({show(lv)}){own}')
        return 1 if bad else 0
    if len(a.out) != 1:
        ap.error('write one clip at a time')
    try:
        frames, rate, (w, h) = write(a.out[0], a.fps, a.size, a.seconds, a.audio, a.first, a.timecode)
    except ValueError as e:
        ap.error(str(e))
    except NotSelfConsistent as e:
        print(f'FAIL: {e}', file=sys.stderr)
        return 1
    print(f'{a.out[0]}: {frames} frames {w}x{h} @ {rate.numerator}/{rate.denominator}'
          f"{' + 1 kHz tone' if a.audio else ''}, numbers {a.first}..{a.first + frames - 1}, band {band_height(h)} px"
          + (f', start timecode {a.timecode}' if a.timecode else ''))
    print('every frame decodes to its own number (H.264, its Y plane read back)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
