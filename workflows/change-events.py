#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""change-events.py: the frames where a picture visibly changes, and whether they land on the words they were timed to.

  uv run workflows/change-events.py <video> [--region x,y,w,h] [--alpha] [--threshold 2] [--min-gap-frames 3] [--json out]
  uv run workflows/change-events.py --sync projects/<job> [ids...] [--tolerance 0.10] [--region ...] [--threshold ...] [--json out]

DETECT prints every change event in a render or a capture (a message typed, sent, a reply landing, a card popping):
its onset frame, its time (the frame's own pts, so a variable-rate screen recording is timed right), its peak
magnitude and, with --alpha, whether ink APPEARED or DISAPPEARED. The magnitude is the per-frame mean absolute
difference (0-255) over the region's pixels that the file ever covers (the whole region for an opaque file, only
the drawn part of an overlay, so a top-half card measures the same as the same card cropped), on a copy at most
360 px wide: gray composited over black by default, the alpha channel with --alpha. Each frame is judged by how far
it rises above the local motion floor (the 25th percentile of the 12 frames before it), so a render that drifts,
pushes in or scrolls the whole time still shows its cuts and landings. An event opens on a frame that rises
--threshold above that floor and stays open until one rises less than half of it (hysteresis: one animation is one
event); two bursts with fewer than --min-gap-frames quiet frames between them are one event. The magnitude printed
is the event's raw peak. --alpha treats the frame before the file as empty,
because an overlay lands on the timeline at its frame 0: ink already there on frame 0 is an event at frame 0.
The noise line (median and 95th percentile of the per-frame magnitude) is what to read before moving --threshold
for a small region or a noisy capture. --region is in the file's own pixels.

SYNC checks each placed graphic (hf-graphics/placement.json) against the words it was timed to. A plan cell names
its anchors in graphics-plan.json:
    "sync": [{"word": "sent"}, {"word": "retention", "offset": 0.25}, {"word": "add", "expect": "first change"}]
  word    a word or a phrase, matched whole-word (case and edge punctuation ignored) among the words spoken while
          the row is on screen (its placed span, widened by the tolerance); "nth": 2 takes the 2nd of several
          (a whole number from 1; anything else is a BAD ANCHOR, never an index)
  expect  "change" (default): the nearest change event · "first change": the render's first one (its entrance)
  offset  a DESIGNED lag in seconds (a reply that lands 0.25 s after its word; a lead is negative); default 0, or on
          the kit's clock the "sync_offset" recorded on the kit row it meets (below)
  source  "kit" or "render": which clock the anchor is checked on (below). Default: "kit" on a kit cell, "render" on a
          capture or montage and for every "first change"; any other value is a BAD ANCHOR
A cell with no "sync" falls back to its START WORD when its start is on a word (a word starts within the tolerance
of it): that word must meet the render's first change. A "first change" (the fallback or named) is read on the
render's pixels on every cell unless its anchor says "source": "kit": it is the render's ENTRANCE, and a kit comp's
entrance can make no sound, so its first kit row is not its entrance.
A KIT cell, family "authored" or "overlay" (what a preset kit's components build: the Talking Head Explainer's hook,
escalation, CTAs and call card) with rows of its id in hf-graphics/sfx-hand.json marked "src": "kit", is checked on
those KIT events: each row is a beat the component placed on the comp's own clock (the value keyed in, a badge
landing, a window stacking, the accept tapped), the timeline the render is drawn from. A RUN of one sound is ONE event
at its first row, as one animation is one event below, so an anchor meets the run's onset, never a row inside it.
Runs are read in SECONDS, the same at every frame rate: consecutive rows of the same event each within 0.17 s of the
one before (a fast burst, 3 to 4 f apart on the 23.976 grid: a pop-run), and every row of the same event after a row
carrying "sync_offset", up to a row of another event, whatever the gap (the gesture that designed lead opens:
masked_value's taps, 0.11 to 0.2 s apart by the value's digit count). "sync_offset" is a DESIGNED offset from its word
that the component recorded (masked_value's key lead, shorter when its pill lands late): an anchor with no "offset"
READS it off the row (each kit event is sought where its own recorded offset puts it), so the plan need not repeat
it and the lead is applied exactly, never absorbed by the tolerance; an anchor that declares a DIFFERENT "offset" FAILS
naming the row's, because the plan and the comp disagree about what was built.
Pixel differencing cannot separate them there (small dots merge with a pill's rise, a scene that scrolls or a waveform
that moves the whole time is one long event), so the render's changes are printed for reference and the anchors are
held to the kit's events. "source": "render" on an anchor forces the pixel check; "source": "kit" forces the kit's rows
on any family (a capture's cut-in) and is NOT CHECKED when the id has no kit rows, never quietly measured on pixels.
A kit row is held to what the timeline shows exactly as a change is (below): a beat at or after the out-point is
never matched. The render must still exist and decode: a kit cell with a missing render is not checked (the kit's
rows are read from sfx-hand.json, so a comp rebuilt and not re-rendered is not caught here).
The word's time comes from the canonical outputs/<job>.transcript.json and is mapped into the render's own clock
through the row's start. Events are detected on what the render adds to the timeline (gray over black or alpha, whichever changed more, with the frame
before the file empty, so a render's entrance is an event), and only those the timeline SHOWS count: the placer lays
a render from its frame 0 and trims one that runs longer than its slot at the row's end, so a change whose onset is
at or after the out-point is never seen and is neither listed nor matched. Each anchor prints its delta to the expected event;
beyond --tolerance it FAILS. A word not spoken in the row's span, or spoken there more than once with no "nth", is
REPORTED with where it is spoken, never guessed.

Exit: detect 0, or 2 on unreadable input. Sync 0 = every anchor within tolerance, 1 = any FAIL, 2 = no FAIL but an
anchor could not be checked (unknown or ambiguous word, bad anchor, missing render, "source": "kit" with no kit rows)
or nothing was checked.

Why (2026-09-21): six scenes were timed to a transcript that ran 0.876 s early, and every check passed them
(framing, sweeps, cut frames), because none compared picture to words; a job-local sync script found it. Capture
shots were timed with a job-local tblend/signalstats shell one-liner that broke under zsh, and SFX cues were
re-timed three times by hand-run frame differencing. This is that measurement, once, for every job.
"""
import argparse, json, re, subprocess, sys, threading
from fractions import Fraction
from pathlib import Path
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

WORK_W = 360        # measured on a copy at most this wide: fast, and a one-pixel flicker averages out
THRESHOLD = 2.0     # mean absolute difference (0-255) over the region that opens an event
MIN_GAP = 3         # quiet frames needed between two bursts for them to be two events
FLOOR_WINDOW = 12   # frames before each frame whose 25th percentile is the local motion floor it is measured above
TOLERANCE = 0.10    # seconds: a sync anchor further than this from its event FAILS
RUN_GAP_S = 0.17    # seconds: kit rows of one event this close to the one before are one RUN, at every frame rate (a
                    # fast burst is 3 to 4 f apart, sfx.md's pop-run: 0.167 s at most, on the slowest grid, 23.976)
EXPECTS = ('change', 'first change')
SOURCES = ('kit', 'render')
KIT_FAMILIES = ('authored', 'overlay')   # the families a kit's components build (engine.authored / engine.overlay);
                                         # a capture or a montage keeps the pixel check (its motion is the app's own)
ALPHA_FMT = re.compile(r'^(yuva|gbrap|ya\d|rgba|bgra|argb|abgr|ayuv|vuya|rgbaf)')
SHOWINFO = re.compile(r'\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s')
TIMEBASE = re.compile(r'config in time_base:\s*(\d+)/(\d+)')


class MediaError(Exception):
    pass


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,pix_fmt,r_frame_rate,avg_frame_rate:stream_side_data=rotation',
                        '-of', 'json', str(path)], capture_output=True, text=True)
    ss = (json.loads(r.stdout or '{}').get('streams') or []) if r.returncode == 0 else []
    if not ss or not ss[0].get('width'):
        raise MediaError(f'cannot read a video stream in {path}')
    s = ss[0]
    w, h = int(s['width']), int(s['height'])
    rot = next((abs(int(float(d['rotation']))) for d in s.get('side_data_list') or [] if 'rotation' in d), 0)
    if rot % 180 == 90:          # ffmpeg auto-rotates on decode, so the region is in the DISPLAYED frame
        w, h = h, w
    fps = next((f for f in (s.get('avg_frame_rate'), s.get('r_frame_rate')) if f and not f.startswith('0/')), '30/1')
    pix = s.get('pix_fmt') or ''
    return dict(w=w, h=h, pix_fmt=pix, fps=Fraction(fps.rstrip(',')), alpha=bool(ALPHA_FMT.match(pix)))


def measure(path, region=None, mode='gray', empty_before=False):
    """Decode the file once and measure each frame's change from the frame before it.

    mode 'gray': the gray picture composited over black · 'alpha': the alpha channel · 'visible': the larger of the
    two (what an overlay adds to the timeline). empty_before: the frame before frame 0 is transparent black.
    Returns the probe plus per-frame lists: t (seconds from the first frame, off each frame's pts), mag, ink_in, ink_out."""
    info = probe(path)
    x, y, w, h = region or (0, 0, info['w'], info['h'])
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > info['w'] or y + h > info['h']:
        raise MediaError(f'region {x},{y},{w},{h} is outside the {info["w"]}x{info["h"]} frame of {path}')
    tw = min(WORK_W, w)
    th = max(1, round(h * tw / w))
    vf = ([f'crop={w}:{h}:{x}:{y}'] if region else []) + [f'scale={tw}:{th}:flags=area', 'showinfo']
    cmd = ['ffmpeg', '-hide_banner', '-nostats', '-v', 'info', '-i', str(path), '-map', '0:v:0', '-an',
           '-vf', ','.join(vf), *passthrough(), '-f', 'rawvideo', '-pix_fmt', 'ya8', '-']
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    err = []
    drain = threading.Thread(target=lambda: err.append(p.stderr.read().decode('utf-8', 'replace')), daemon=True)
    drain.start()
    size = tw * th * 2
    zero = np.zeros((th, tw), np.float32)
    prev = (zero, zero) if empty_before else None
    covered = np.zeros((th, tw), bool)          # every pixel the file ever puts ink on
    sums = []                                   # per frame: summed |gray change|, ink in, ink out
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        f = np.frombuffer(buf, np.uint8).reshape(th, tw, 2).astype(np.float32)
        alpha = f[..., 1]
        vis = f[..., 0] * alpha / 255.0
        covered |= alpha > 0
        if prev is None:
            sums.append((0.0, 0.0, 0.0))
        else:
            da = alpha - prev[1]
            sums.append((float(np.abs(vis - prev[0]).sum()), float(np.maximum(da, 0).sum()), float(np.maximum(-da, 0).sum())))
        prev = (vis, alpha)
    p.stdout.close()
    p.wait()
    drain.join()
    p.stderr.close()
    # The MEAN is taken over the pixels the file ever covers, not the whole region: a top-half overlay leaves half the
    # frame transparent, and a card landing in it measured half as big (under the threshold) as the same card cropped.
    # An opaque file covers the whole region, so for footage and captures this is the plain mean.
    area = int(covered.sum()) or tw * th
    mag, ink_in, ink_out = [], [], []
    for dg, i_, o_ in sums:
        dg, i_, o_ = dg / area, i_ / area, o_ / area
        mag.append(dg if mode == 'gray' else i_ + o_ if mode == 'alpha' else max(dg, i_ + o_))
        ink_in.append(i_); ink_out.append(o_)
    log = ''.join(err)
    if p.returncode or not mag:
        tail = ' | '.join(l for l in log.splitlines()[-3:] if l.strip())
        raise MediaError(f'ffmpeg could not decode {path}: {tail or "no frames"}')
    tb = TIMEBASE.search(log)
    pts = [int(m.group(2)) for m in SHOWINFO.finditer(log)]
    if tb and len(pts) == len(mag):
        base = Fraction(int(tb.group(1)), int(tb.group(2)))
        t = [float((q - pts[0]) * base) for q in pts]
        clock = 'pts'
    else:                        # no per-frame timestamps to read: fall back to the nominal rate, and say so
        t = [float(i / info['fps']) for i in range(len(mag))]
        clock = 'nominal'
    return dict(info, work=(tw, th), region=[x, y, w, h] if region else None, mode=mode, t=t, mag=mag,
                ink_in=ink_in, ink_out=ink_out, clock=clock, coverage=area / (tw * th))


def detect(mag, threshold=THRESHOLD, min_gap=MIN_GAP):
    """Change events from a per-frame magnitude series: [{frame, end_frame, magnitude}], onset-ordered.
    A frame's change is measured ABOVE the local motion floor (the 25th percentile of the FLOOR_WINDOW frames before
    it), so a continuous drift, push-in or scroll does not hold one event open over every cut and landing inside it.
    An event opens at >= threshold and stays open down to threshold/2; fewer than min_gap quiet frames between two
    bursts make them one event. `magnitude` is the event's raw peak."""
    low = threshold / 2.0
    events, cur = [], None
    for i, raw in enumerate(mag):
        hist = mag[max(0, i - FLOOR_WINDOW):i]
        m = raw - (float(np.percentile(hist, 25)) if hist else 0.0)
        if cur is None:
            if m >= threshold:
                if events and i - events[-1]['end_frame'] - 1 < min_gap:
                    cur = events.pop()
                else:
                    cur = dict(frame=i, end_frame=i, magnitude=raw)
                cur['end_frame'] = i
                cur['magnitude'] = max(cur['magnitude'], raw)
        elif m < low:
            events.append(cur)
            cur = None
        else:
            cur['end_frame'] = i
            cur['magnitude'] = max(cur['magnitude'], raw)
    if cur:
        events.append(cur)
    return events


def events_of(meas, threshold=THRESHOLD, min_gap=MIN_GAP):
    """detect() on a measure() result, with times and (where alpha moved) the ink direction."""
    out = []
    for e in detect(meas['mag'], threshold, min_gap):
        a, b = e['frame'], e['end_frame']
        ins, outs = sum(meas['ink_in'][a:b + 1]), sum(meas['ink_out'][a:b + 1])
        ink = None
        if ins + outs > 1e-3:
            ink = 'appear' if outs <= 0.25 * ins else 'disappear' if ins <= 0.25 * outs else 'in+out'
        out.append(dict(frame=a, end_frame=b, seconds=round(meas['t'][a], 6), end_seconds=round(meas['t'][b], 6),
                        magnitude=round(e['magnitude'], 3), ink=ink))
    return out


def on_screen(ev, dur, fps):
    """The events a placed render SHOWS: onset before its placed duration. The placer lays the render from frame 0 and
    trims one that runs longer than its slot at the out-point, so a change after it never reaches the timeline. Half a
    frame of slack keeps the last shown frame and drops the first hidden one whatever the rounding of start and end."""
    cut = dur - 0.5 / float(fps)
    return [e for e in ev if e['seconds'] < cut]


def parse_region(s):
    try:
        v = [int(round(float(x))) for x in s.split(',')]
    except ValueError:
        v = []
    if len(v) != 4:
        raise argparse.ArgumentTypeError(f'--region wants x,y,w,h in pixels, got {s!r}')
    return v


# ── detect ──────────────────────────────────────────────────────────────────────────────────────────────────────
def run_detect(a):
    mode = 'alpha' if a.alpha else 'gray'
    try:
        meas = measure(a.target, a.region, mode, empty_before=a.alpha)
    except MediaError as e:
        print(f'✗ {e}')
        return 2
    ev = events_of(meas, a.threshold, a.min_gap_frames)
    mags = np.array(meas['mag'][1:] or [0.0])
    tw, th = meas['work']
    print(f"{a.target}  {meas['w']}x{meas['h']} {meas['pix_fmt']}, {meas['fps']} fps, {len(meas['mag'])} frames "
          f"(times off the {'frame pts' if meas['clock'] == 'pts' else 'NOMINAL rate: no pts could be read'})")
    print(f"  measured {mode} on {'region ' + ','.join(map(str, meas['region'])) if meas['region'] else 'the whole frame'} "
          f"at {tw}x{th} (ink covers {meas['coverage'] * 100:.0f}% of it); threshold {a.threshold:g} "
          f"(holds to {a.threshold / 2:g}), min gap {a.min_gap_frames} frames")
    print(f"  noise: median change {float(np.median(mags)):.3f}, 95th percentile {float(np.percentile(mags, 95)):.3f}")
    if a.alpha and not meas['alpha']:
        print(f"⚠ --alpha on a file with no alpha channel ({meas['pix_fmt']}): every frame is opaque, so only frame 0 can change")
    for e in ev:
        span = f"frames {e['frame']}-{e['end_frame']}" if e['end_frame'] > e['frame'] else f"frame {e['frame']}"
        ink = f"  {e['ink']}" if a.alpha and e['ink'] else ''
        print(f"  frame {e['frame']:5d}  {e['seconds']:9.3f} s  magnitude {e['magnitude']:6.2f}{ink}   ({span})")
    print(f"{len(ev)} change event{'s' if len(ev) != 1 else ''}")
    if a.json:
        rec = dict(video=str(a.target), size=[meas['w'], meas['h']], work=[tw, th], region=meas['region'], mode=mode,
                   fps=str(meas['fps']), frames=len(meas['mag']), clock=meas['clock'],
                   coverage=round(meas['coverage'], 4), threshold=a.threshold,
                   hold=a.threshold / 2, min_gap_frames=a.min_gap_frames, events=ev)
        Path(a.json).write_text(json.dumps(rec, indent=1), encoding="utf-8")
        print(f'wrote {a.json}')
    return 0


# ── sync ────────────────────────────────────────────────────────────────────────────────────────────────────────
def norm(w):
    return re.sub(r"^[^\w']+|[^\w']+$", '', str(w).replace('’', "'")).lower()


def spoken(words, phrase):
    """Start times of every whole-word occurrence of `phrase` (one or more words) in the transcript."""
    toks = [t for t in (norm(x) for x in str(phrase).split()) if t]
    if not toks:
        return []
    return [words[i][1] for i in range(len(words) - len(toks) + 1)
            if all(words[i + k][0] == toks[k] for k in range(len(toks)))]


def anchors_of(cell, words, tol):
    """The cell's sync anchors, or its start word as a 'first change' anchor, or ([], why-not)."""
    raw = cell.get('sync')
    if raw:
        raw = raw if isinstance(raw, list) else [raw]
        return [x if isinstance(x, dict) else {'word': x} for x in raw], None
    try:
        start = float(cell.get('start'))
    except (TypeError, ValueError):
        return [], 'no sync anchor and no start'
    if not words:
        return [], 'no sync anchor and the transcript has no words'
    near = min(words, key=lambda w: abs(w[1] - start))
    if abs(near[1] - start) > tol + 1e-9:
        return [], f'no sync anchor; start {start:.3f} is not on a word (nearest "{near[2]}" at {near[1]:.3f})'
    return [{'word': near[2], 'expect': 'first change', 'at': near[1], 'fallback': True}], None


def kit_events(job):
    """{gid: [{'seconds', 'event', 'note', 'sync_offset'}]} from hf-graphics/sfx-hand.json's `"src": "kit"` rows
    (comp-relative seconds: the beats a preset kit's components placed on the comp's own clock; sync_offset = the
    designed offset from its word the component recorded on the row, or None), each gid's in time order."""
    p = job / 'hf-graphics' / 'sfx-hand.json'
    if not p.exists():
        return {}
    out = {}
    for r in load_json(p):
        if r.get('src') == 'kit' and r.get('at') is not None:
            so = r.get('sync_offset')
            out.setdefault(r.get('gid'), []).append(dict(seconds=float(r['at']), event=r.get('event'), note=r.get('note', ''),
                                                         sync_offset=None if so is None else float(so)))
    for v in out.values():
        v.sort(key=lambda e: e['seconds'])
    return out


def kit_runs(rows, fps):
    """A gid's kit rows (time order) as EVENTS. A run of one sound is ONE event at its first row (one animation is one
    event, the pixel clock's rule): without it every row of a 0.6 s run was an anchor's nearest candidate, and any word
    inside the run passed. A run is read in seconds, never frames, so it is the same at every frame rate and for every
    value length (a frame count once split masked_value's taps at 50 fps, or at 23.976 for a 5-digit value):
      - a row carrying a sync_offset (a designed lead) opens an event that takes every following row of the same event
        up to a row of another event, whatever the gap: masked_value's taps sit 0.11 to 0.2 s apart by digit count;
      - otherwise consecutive rows of one event, each within RUN_GAP_S of the one before, are one run (a pop-run).
    fps only numbers the frame. Each event: the first row plus frame, end_seconds (its last row), rows (how many)."""
    out = []
    for r in rows:
        last = out[-1] if out else None
        if (last and r['event'] == last['event'] and r.get('sync_offset') is None
                and (last.get('sync_offset') is not None or r['seconds'] - last['end_seconds'] <= RUN_GAP_S + 1e-9)):
            last.update(end_seconds=r['seconds'], rows=last['rows'] + 1)
        else:
            out.append(dict(r, frame=round(r['seconds'] * fps), end_seconds=r['seconds'], rows=1))
    return out


def kit_extras(e):
    """['5 rows', 'designed -0.12 s']: what a kit event holds beyond its name, as the sync print names it."""
    return ([f"{e['rows']} rows"] if e.get('rows', 1) > 1 else []) \
        + ([f"designed {e['sync_offset']:+g} s"] if e.get('sync_offset') is not None else [])


def check_anchor(anc, row, ev, words, tol, none_shown='the render never visibly changes while it is on screen'):
    """One anchor against a list of events (the render's changes, or a kit's beats: a kit event carries its `event`
    name, and a designed one its `sync_offset`). Returns a result dict; status PASS / FAIL / UNKNOWN / AMBIGUOUS /
    BAD ANCHOR. none_shown is the FAIL note when the list is empty. An anchor with no "offset" takes the met event's
    recorded sync_offset (result: offset = it, offset_from = 'row'); one that declares another FAILS."""
    word, expect = anc.get('word'), anc.get('expect', 'change')
    declared = anc.get('offset') not in (None, '')
    res = dict(id=row['id'], word=word, expect=expect, offset=anc.get('offset', 0), fallback=bool(anc.get('fallback')))
    try:
        offset = float(anc.get('offset', 0) or 0)
    except (TypeError, ValueError):
        return dict(res, status='BAD ANCHOR', note=f'offset {anc.get("offset")!r} is not a number of seconds')
    if not word or not str(word).strip():
        return dict(res, status='BAD ANCHOR', note='no "word"')
    if expect not in EXPECTS:
        return dict(res, status='BAD ANCHOR', note=f'expect {expect!r} is not one of {", ".join(EXPECTS)}')
    if anc.get('source') is not None and anc.get('source') not in SOURCES:
        return dict(res, status='BAD ANCHOR', note=f'source {anc.get("source")!r} is not one of {", ".join(SOURCES)}')
    nth = anc.get('nth')
    if nth is not None and (isinstance(nth, bool) or not isinstance(nth, int) or nth < 1):
        # a 0 would read as "the 1st" and a -1 as "the one before last": an index is never guessed from a bad number
        return dict(res, status='BAD ANCHOR', note=f'nth {nth!r} is not a whole number from 1 (the 1st time it is spoken during the row)')
    start, end = float(row['start']), float(row['end'])
    if 'at' in anc:
        wt = float(anc['at'])
    else:
        lo, hi = start - tol, end + tol
        every = spoken(words, word)
        inside = [t for t in every if lo <= t <= hi]
        elsewhere = ', '.join(f'{t:.3f}' for t in every[:8]) or 'nowhere in the transcript'
        at = ', '.join(f'{t:.3f}' for t in inside)
        if not inside:
            return dict(res, status='UNKNOWN', note=f'not spoken during {lo:.3f}-{hi:.3f} (spoken at: {elsewhere})')
        if nth is None and len(inside) > 1:
            return dict(res, status='AMBIGUOUS', note=f'spoken {len(inside)}x during {lo:.3f}-{hi:.3f} at {at}: name one with "nth"')
        if (nth or 1) > len(inside):
            return dict(res, status='UNKNOWN', note=f'nth {nth}, but it is spoken {len(inside)}x during {lo:.3f}-{hi:.3f} (at {at})')
        wt = inside[(nth or 1) - 1]
    res.update(word_time=round(wt, 6), render_time=round(wt - start, 6))
    if not ev:
        return dict(res, status='FAIL', note=none_shown)
    # where each event belongs on the render's own clock: the word plus the anchor's offset, or with none declared the
    # event's own recorded sync_offset (a kit row's designed lead: read off the row, never retyped in the plan)
    lag = (lambda e: offset) if declared else (lambda e: e.get('sync_offset') or 0.0)
    hit = ev[0] if expect == 'first change' else min(ev, key=lambda e: abs(e['seconds'] - (wt - start + lag(e))))
    want = wt - start + lag(hit)
    delta = hit['seconds'] - want
    status = 'PASS' if abs(delta) <= tol + 1e-9 else 'FAIL'
    if hit.get('event'):
        res['kit_event'] = hit['event']
        if hit.get('rows', 1) > 1:
            res['kit_rows'] = hit['rows']
    designed = hit.get('sync_offset')
    if designed is not None:
        res['kit_sync_offset'] = designed
        if not declared:                         # the lead applied exactly as built, never absorbed by the tolerance
            res.update(offset=designed, offset_from='row')
        elif abs(offset - designed) > 1e-3:      # the plan and the comp disagree about what was built
            status = 'FAIL'
            res['note'] = (f'the {hit["event"]} it meets is built {designed:+g} s off its word (a designed offset: '
                           f'"sync_offset" on its sfx-hand.json row), and the anchor declares {offset:+g} s: '
                           f'drop the anchor\'s "offset" (the row\'s is read) or make it {designed:g}')
    return dict(res, status=status, event=hit['seconds'],
                event_frame=hit['frame'], event_time=round(start + hit['seconds'], 6), delta=round(delta, 6))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def run_sync(a):
    job = Path(a.target).resolve()
    tol = a.tolerance
    need = {'placement': job / 'hf-graphics' / 'placement.json',
            'transcript': job / 'outputs' / f'{job.name}.transcript.json'}
    for what, p in need.items():
        if not p.exists():
            print(f'✗ no {what} at {p}: nothing to check')
            return 2
    rows = load_json(need['placement'])
    words = [(norm(w['text']), float(w['start']), w['text']) for w in load_json(need['transcript'])['words']
             if w.get('type', 'word') == 'word' and norm(w.get('text', ''))]
    kit = kit_events(job)
    plan_p = job / 'graphics-plan.json'
    cells = {c.get('id'): c for c in (load_json(plan_p).get('beats') or [])} if plan_p.exists() else {}
    if not cells:
        print(f'⚠ no plan cells in {plan_p}: no row has an anchor')
    if a.ids:
        missing = [i for i in a.ids if i not in {r.get('id') for r in rows}]
        rows = [r for r in rows if r.get('id') in a.ids]
    else:
        missing = []
    print(f"sync {job.name}: {len(rows)} placed row{'s' if len(rows) != 1 else ''}, tolerance ±{tol:g} s, "
          f"threshold {a.threshold:g}, min gap {a.min_gap_frames} frames"
          + (f", region {','.join(map(str, a.region))}" if a.region else ''))
    results, unchecked = [], 0
    for gid in missing:
        print(f'? {gid}: no such row in {need["placement"].name}')
        results.append(dict(id=gid, status='UNKNOWN', note='no such placement row'))
        unchecked += 1
    for row in rows:
        gid = row.get('id')
        cell = cells.get(gid)
        if cell is None:
            print(f'  {gid}: no plan cell: not checked')
            results.append(dict(id=gid, status='SKIP', note='no plan cell'))
            continue
        anchors, why = anchors_of(cell, words, tol)
        if not anchors:
            print(f'  {gid}: {why}: not checked')
            results.append(dict(id=gid, status='SKIP', note=why))
            continue
        f = Path(row.get('file') or '')
        f = f if f.is_absolute() else job / f
        t0, t1 = float(row['start']), float(row['end'])
        try:
            meas = measure(f, a.region, 'visible', empty_before=True)
        except MediaError as e:      # a kit cell too: its rows alone are never checked without a placed render that decodes
            print(f'? {gid}: {e}')
            for anc in anchors:
                results.append(dict(id=gid, word=anc.get('word'), status='UNCHECKED', note=str(e)))
                unchecked += 1
            continue
        every = events_of(meas, a.threshold, a.min_gap_frames)
        ev = on_screen(every, t1 - t0, meas['fps'])         # a change after the out-point is trimmed off the timeline
        hidden = len(every) - len(ev)
        shown = ' '.join(f"{t0 + e['seconds']:.2f}" for e in ev[:14]) + (' …' if len(ev) > 14 else '')
        print(f"{gid}  {f.name}  on {t0:.3f}-{t1:.3f} · {len(ev)} change{'s' if len(ev) != 1 else ''} "
              f"(timeline s): {shown or 'none'}"
              + (f" · {hidden} more after the out-point, never shown" if hidden else ''))
        own = kit.get(gid) or []
        rows_shown = on_screen(own, t1 - t0, meas['fps'])     # a kit beat on or after the out-point is never shown either
        kev = kit_runs(rows_shown, meas['fps'])                  # a run of one sound is one event, at its first row
        held = bool(own) and cell.get('family') in KIT_FAMILIES
        if own:
            shown = ' '.join(f"{e['event']}@{t0 + e['seconds']:.2f}"
                             + (f"-{t0 + e['end_seconds']:.2f}" if e['rows'] > 1 else '')
                             + (f"({', '.join(kit_extras(e))})" if kit_extras(e) else '')
                             for e in kev[:14]) + (' …' if len(kev) > 14 else '')
            print("    kit events (hf-graphics/sfx-hand.json, the comp's own beats; a run of one sound is one event"
                  + ('' if held else '; on source "kit" only') + '): ' + (shown or 'none shown')
                  + (f" · {len(own) - len(rows_shown)} more after the out-point, never shown" if len(own) > len(rows_shown) else ''))
        for anc in anchors:
            src = anc.get('source')
            # a "first change" (the start-word fallback or named) is the render's ENTRANCE, and a kit comp's entrance
            # can make no sound, so its first kit row is not its entrance: pixels, unless the anchor names the kit
            use_kit = src == 'kit' or (src is None and held and anc.get('expect', 'change') != 'first change')
            r = check_anchor(anc, row, kev if use_kit else ev, words, tol,
                             **({'none_shown': f'none of its {len(own)} kit beats is shown before the out-point'}
                                if use_kit else {}))
            if use_kit and r['status'] != 'BAD ANCHOR':
                r['source'] = 'kit'
            if use_kit and not own and r['status'] == 'FAIL':    # asked for the kit's clock, and there is none to read
                r.update(status='UNCHECKED', note=f'source "kit", but {gid} has no "src": "kit" rows in '
                                                  'hf-graphics/sfx-hand.json (the kit writes them when build.py builds the comp)')
            results.append(r)
            label = f'"{r["word"]}"' + (f' {float(r["offset"]):+g} s' if r.get('offset') not in (0, None, '') and r['status'] != 'BAD ANCHOR' else '') \
                + (' (its row)' if r.get('offset_from') == 'row' else '') \
                + (' first change' if r.get('expect') == 'first change' else '') + (' (start word)' if r['fallback'] else '') \
                + (' [kit]' if r.get('source') == 'kit' else '')
            if r['status'] in ('PASS', 'FAIL') and 'delta' in r:
                mark = '✓' if r['status'] == 'PASS' else '✗'
                print(f"   {mark} {label:34s} word {r['word_time']:8.3f}  change {r['event_time']:8.3f}  "
                      f"delta {r['delta']:+.3f} s{'' if r['status'] == 'PASS' else '  FAIL'}"
                      + (f"  ({', '.join([r['kit_event']] + kit_extras(dict(rows=r.get('kit_rows', 1), sync_offset=r.get('kit_sync_offset'))))})"
                         if r.get('kit_event') else ''))
                if r.get('note'):
                    print(f"      {r['note']}")
            elif r['status'] == 'FAIL':
                print(f"   ✗ {label:34s} word {r['word_time']:8.3f}  FAIL: {r['note']}")
            else:
                print(f"   ? {label:34s} {r['status']}: {r['note']}")
                unchecked += 1
    checked = [r for r in results if r['status'] in ('PASS', 'FAIL')]
    fails = [r for r in checked if r['status'] == 'FAIL']
    worst = max((abs(r['delta']) for r in checked if 'delta' in r), default=None)
    print(f"{len(checked)} anchor{'s' if len(checked) != 1 else ''} checked, {len(fails)} FAIL, {unchecked} not checked"
          + (f' · worst |delta| {worst:.3f} s' if worst is not None else ''))
    code = 1 if fails else 2 if unchecked or not checked else 0
    if not checked and not fails:
        print('✗ nothing was checked: add "sync" anchors to the plan cells, or name rows that start on a word')
    if a.json:
        Path(a.json).write_text(json.dumps(dict(job=job.name, tolerance=tol, threshold=a.threshold,
                                                min_gap_frames=a.min_gap_frames, exit=code, results=results), indent=1), encoding="utf-8")
        print(f'wrote {a.json}')
    return code


def main(argv=None):
    ap = argparse.ArgumentParser(description='Detect visual change events in a video, or check placed graphics against their words.')
    ap.add_argument('target', help='a video file, or with --sync a job folder')
    ap.add_argument('ids', nargs='*', help='--sync only: the placement row ids to check (default every row)')
    ap.add_argument('--sync', action='store_true', help='check the placed graphics of a job against their anchor words')
    ap.add_argument('--region', type=parse_region, help='x,y,w,h in the file\'s pixels (default the whole frame)')
    ap.add_argument('--alpha', action='store_true', help='measure the alpha channel and report ink appearing / disappearing')
    ap.add_argument('--threshold', type=float, default=THRESHOLD, help=f'mean abs difference 0-255 that opens an event (default {THRESHOLD:g})')
    ap.add_argument('--min-gap-frames', type=int, default=MIN_GAP, help=f'quiet frames that separate two events (default {MIN_GAP})')
    ap.add_argument('--tolerance', type=float, default=TOLERANCE, help=f'--sync: seconds an event may sit off its word (default {TOLERANCE:g})')
    ap.add_argument('--json', help='also write the result as JSON to this path')
    a = ap.parse_args(argv)
    if a.threshold <= 0 or a.min_gap_frames < 0:
        ap.error('--threshold must be > 0 and --min-gap-frames >= 0')
    if a.sync:
        if a.alpha:
            ap.error('--sync measures what each render adds to the timeline (gray and alpha); drop --alpha')
        return run_sync(a)
    if a.ids:
        ap.error(f'unexpected arguments {a.ids}: row ids go with --sync')
    return run_detect(a)


if __name__ == '__main__':
    sys.exit(main())
