#!/usr/bin/env python3
"""frame-proof.py: prove what Premiere PLAYS at a sequence frame, never what a readback says it plays.

  uv run lanes/premiere/frame-proof.py projects/<job> --at 12.5,300f,301f [--track V1] [--track-mute V2,V3]
                                       [--clear-previews] [--motion] [--out <dir>]

  --at              sequence times: seconds (the frame Premiere shows there, the floor) or <n>f for sequence frame n
  --track           the track whose clip the frame must come from (default V1)
  --track-mute      video tracks to switch OFF for the grabs (a grade or a graphic above the proof track hides the
                    code). Every name is checked against the sequence before any track is touched, a name given
                    twice counts once, and each is put back exactly as it was afterwards, whatever happens
  --clear-previews  delete the sequence's preview renders before the grabs. A scripted write does not invalidate
                    Premiere's preview cache, so the Program monitor AND exportFrame can show the frame from BEFORE
                    the write (lanes/premiere/lab-notes.md § stale render cache): pass it after any write you are
                    proving. Opt-in because on a real job it throws away every render the creator made by hand
  --out             where the program grabs land (default <job>/review/frame-proof/); each grab's file is deleted
                    before it is grabbed again, so an old PNG can never pass for a grab that did not land
  --motion          read each clip's Motion (Scale, Position, Anchor Point) at the frame's media time, decode the grey
                    code where that transform puts it, and prove the FRAMING: every boundary of the code that shows
                    must sit within FRAME_TOL (3) sequence pixels of where the Motion puts it (THE FRAMING, below).
                    A patch the transform puts off the frame is unmeasured, never guessed

For each time: the clip on the track under that frame, read in TICKS; the source frame it should show, which is the
clip's in-point plus the frame's offset into the clip, in ticks, on the source's own frame grid; the frame the program
grab actually shows, decoded from the grey code (workflows/grey-source.py); and the delta in frames between the two.
Every clip's Motion is read at its frame first: one that moves the source (a framing key) is not read without
--motion, because the plain read looks for the code where an unmoved source sits and a moved one read there as no
code, or as a false BLACK (a code frame whose body is two levels off black, live 2026-09-24).

  Exit 0  every frame shows the source frame its clip says (and, with --motion, sits where its Motion puts it).
  Exit 1  a nonzero delta anywhere, a frame from ANOTHER source (a remnant of the clip a lay replaced), a BLACK
          frame where the track says a clip plays (a disabled clip, a hole the readback does not show), or, with
          --motion, a FRAMING off: a boundary of the code more than FRAME_TOL px from where the Motion puts it.
  Exit 2  no delta, but a frame could not be measured: its clip is not a grey source, the grab is not a grey-coded
          frame (a graphic or the grade over it: --track-mute; a source that does not fill the frame), a speed
          change, a gap, a project item whose metadata does not read (where a subclip starts is unknown), an item
          offset before the media's start timecode (Premiere is not on the file's timecode clock), a clip whose
          Motion moves the source read without --motion (never grabbed), a framing --motion cannot read (its Motion
          does not read; no boundary shows across or down the frame), or a LEVEL
          DRIFT (the grab is the expected frame with its grey off by a level or two: colour management or a LUT,
          not an edit). A grab that decodes to a frame of a source on the track is a
          FRAME, never a drift, however far away it is: a slip of 67, 86, 134 or 153 frames leaves the body within
          two levels of the expected grey, and read as a drift it hid a real 2.8 s slip (2026-09-23 review).

THE FRAMING (--motion; 2026-09-24). The code's three sample squares say WHICH source frame plays, never WHERE the
source sits: they land in three large flat regions, so live a readback 22-38 px off the program, a W grab read as the
T mode and a T grab read as W all decoded OK. So --motion also reads the code's BOUNDARIES off the grab (the band's
seam, the band line, the source's four edges against black: grey-source.py framing()) and holds each one that shows to
FRAME_TOL = 3 sequence pixels of where the Motion puts it (live, the edges sat within 1.3 px of the key math and a
neighbouring frame's within 4-20 px); an edge the Motion puts at or past the frame border must not show inside it;
and points clear of every boundary must read the grey the Motion puts there. Any of those off is a FAIL. The Scale is
pinned only when two parallel boundaries show (an edge of the source as well as a seam): a source that fills or
overfills the frame shows its seam and band line alone, a zoom about the band line would look the same, and the row
says "Scale unpinned". To pin a mode's Scale in a throwaway, give it a Position that puts an edge on the frame.

THE EXPECTED FRAME is the one the write was aiming at. On a same-rate source every clip boundary sits on the frame
grid, so the frame is the NEAREST source frame to the clip's tick time, and an in-point a tick under the grid (the
2026-09-22 float-seconds write) expects the frame it was meant to be while Premiere floors it to the frame before:
delta -1, and the row names the ticks. On a mixed-rate source a sequence frame falls between source frames, and the
expected one is the frame at or before it (Premiere's display floor; unproven live, the row says so).

A SUBCLIP (a `lay` row) is held to ONE reading: its track in-point counts from where its item starts in the media
(premiere-bridge.mjs `lay`, and lanes/premiere/lab-notes.md § the HARD-BOUNDARY subclip), so the source time is that
start plus the clip's in-point. The start is the <offset> of the item's VideoInPoint in its project metadata, never
getInPoint(), which reads 0 on the lay's subclip (live, 2026-09-23: that read failed every correct lay row by the
subclip's start). Expected and delta are computed that way only; the row prints what the other reading (the in-point
as source time) would expect as a note, never as a pass. A Source Monitor mark on a master item moves nothing.

THE OFFSET IS ON THE MEDIA'S TIMECODE CLOCK, not its media clock (live P26#2, 2026-09-23): a master item's offset IS
the file's start timecode (01:00:10:00 read 86640 frames at 23.976), a lay subclip's is that timecode plus where the
subclip starts. So the file's start timecode (ffprobe, workflows/grey-source.py probe) comes off first, in ticks on
the source's frame grid; only a file with no timecode has a master offset of 0. Read raw, the timecode failed a
correctly placed master by -86640 frames, and every camera file carries one. An offset BEFORE the timecode means
Premiere is not counting on the file's clock (a Modify > Timecode, a tag ffprobe cannot read the way Premiere does):
where the clip starts is unknown, so the row is unmeasured and never grabbed.

WHY (2026-09-22): a float-seconds in-point rendered the frame before while `.seconds`, a 0.002 s tolerance and a
frame-rounded readback all reported the right one; a program grab of a grey-coded source was the only check that saw
it. The grab time is f/fps + 1e-4, which is frame f under the bridge's display floor and under a nearest-frame
rounding alike. A throwaway job to prove a write in: lanes/premiere/scratch-project.py.
"""
import argparse, importlib.util, json, math, re, subprocess, sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pes                                                    # noqa: E402  (the ONE bridge runner)
from job_guard import require_job_project                     # noqa: E402

_spec = importlib.util.spec_from_file_location('grey_source', HERE.parent.parent / 'workflows' / 'grey-source.py')
grey = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grey)

for _s in (sys.stdout, sys.stderr):   # the bridge's grab line can carry a warning sign; Windows pipes are cp1252
    try:
        if (getattr(_s, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
            _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

TPS = 254016000000                                            # Premiere ticks per second
NUDGE = 1e-4                                                  # seconds past a frame's start: that frame, floor or round
DRIFT = 2                                                     # luma levels a right frame may be off before it is read wrong
FRAME_TOL = 3                                                 # --motion: sequence px a boundary may sit off its Motion

HEAD_ES = r"""(function(){
var s = app.project.activeSequence;
if (!s) return JSON.stringify({error: "no active sequence"});
var o = {name: String(s.name), id: String(s.sequenceID), tpf: 0, video: s.videoTracks.numTracks};
try { o.tpf = Number(s.timebase); } catch (e) {}
if (!(o.tpf > 0)) { try { o.tpf = Math.round(s.getSettings().videoFrameRate.seconds * 254016000000); } catch (e) {} }
return JSON.stringify(o);
})()"""

# One page of a video track, every time as a TICKS string. ES3: no reserved words as keys.
# item_in is where the clip's project item starts on its media's TIMECODE clock: the <offset> of the item's
# VideoInPoint in its project metadata (the start timecode on a master item, plus the subclip's start on a subclip;
# none, or 0, on a master with no timecode: main() takes the file's timecode off). NEVER getInPoint(): on the
# hard-boundary subclip `lay` makes it reads 0 (and getInPoint(1), getInPoint(4) too), while the offset read the lay's
# in-point to the tick (live, 2026-09-23); on a master item it reads the Source Monitor mark, which moves no track
# clip. "?" = the metadata did not read, so the offset is unknown.
PAGE_ES = r"""(function(){
var ID = @ID@, T = @T@, N0 = @N0@, N1 = @N1@;
var s = app.project.activeSequence;
if (!s || String(s.sequenceID) !== ID) return "ERROR: the active sequence changed during the read";
var tr = s.videoTracks[T], out = [];
for (var i = N0; i < N1 && i < tr.clips.numItems; i++) {
  var c = tr.clips[i], pi = null;
  var r = {i: i, name: String(c.name), path: "", item_in: "0", start: String(c.start.ticks), end: String(c.end.ticks),
           inp: String(c.inPoint.ticks), speed: 1};
  try { pi = c.projectItem; } catch (e) {}
  if (pi) {
    try { r.path = String(pi.getMediaPath() || ""); } catch (e) {}
    try {
      var pm = String(pi.getProjectMetadata() || "");
      var vb = /Column\.Intrinsic\.VideoInPoint\b[^>]*>([\s\S]*?)<\/[^>]*Column\.Intrinsic\.VideoInPoint>/.exec(pm);
      var vo = vb ? /:offset>\s*(-?\d+)\s*</.exec(vb[1]) : null;
      r.item_in = vo ? vo[1] : "0";
    } catch (e) { r.item_in = "?"; }
  }
  try { r.speed = c.getSpeed(); } catch (e) {}
  out.push(r);
}
return JSON.stringify(out);
})()"""

# One clip's Motion at a media time (a framing key moves the source: Position in frame fractions, Scale in percent,
# the Anchor Point a fraction of the source), and the sequence's frame size the Position is a fraction of. Read for
# EVERY grabbed frame, --motion or not. A Motion that does not read comes back as nulls (and `error`), never as an
# ERROR: the caller decides what an unread Motion means.
MOTION_ES = r"""(function(){
var ID = @ID@, T = @T@, I = @I@, MT = @MT@;
var s = app.project.activeSequence;
if (!s || String(s.sequenceID) !== ID) return "ERROR: the active sequence changed during the read";
var o = {w: Number(s.frameSizeHorizontal), h: Number(s.frameSizeVertical), scale: null, pos: null, anchor: null};
try {
  var c = s.videoTracks[T].clips[I], m = null;
  for (var k = 0; k < c.components.numItems; k++) if (c.components[k].displayName === "Motion") m = c.components[k];
  if (!m) return JSON.stringify(o);
  var p = function(n){ for (var q = 0; q < m.properties.numItems; q++) if (m.properties[q].displayName === n) return m.properties[q]; return null; };
  var v = function(P){ if (!P) return null; try { if (P.isTimeVarying()) { var t = new Time(); t.seconds = MT; return P.getValueAtTime(t); } } catch (e2) {}
    return P.getValue(); };
  o.scale = v(p("Scale")); o.pos = v(p("Position")); o.anchor = v(p("Anchor Point"));
} catch (e) { o.error = String(e); }
return JSON.stringify(o);
})()"""


def read_motion(seq_id, t, i, mt):
    """Clip i of track t's Motion at media time mt (MOTION_ES)."""
    return json.loads(pes.es(fill(MOTION_ES, ID=seq_id, T=t, I=i, MT=mt)))


def motion_xform(mo, src_w, src_h, grab_w, grab_h):
    """--motion: a Motion readback -> grey-source.measure's (k, px, py, ax, ay) in GRAB pixels, or None when it does not
    read. Position is a fraction of the sequence frame (layout-keys.py writes it that way; a value past 2 is read as
    pixels), Scale a percent of the source's own pixels, the Anchor Point a fraction of the source (default centre)."""
    try:
        W, H = float(mo['w']), float(mo['h'])
        sc = float(mo['scale'])
        px, py = (float(x) for x in mo['pos'])
    except (TypeError, ValueError, KeyError):
        return None
    if not (W > 0 and H > 0 and sc > 0):
        return None
    if max(abs(px), abs(py)) <= 2:
        px, py = px * W, py * H
    ax, ay = (0.5, 0.5) if not mo.get('anchor') else (float(x) for x in mo['anchor'])
    if max(abs(ax), abs(ay)) <= 2:
        ax, ay = ax * src_w, ay * src_h
    gx, gy = grab_w / W, grab_h / H
    return sc / 100 * gx, px * gx, py * gy, ax, ay


def at_rest(mo, src_w, src_h):
    """Does the plain read (no --motion) look for the code where this Motion puts it? True when the source fills the
    sequence frame (its corners within a pixel of the frame's) or the Motion is Premiere's default (Scale 100, Position
    and Anchor Point centred: a source of another size keeps the plain read's own fill and letterbox handling), False
    when the Motion moves it (a framing key: read it with --motion), None when the Motion does not read."""
    try:
        W, H = float(mo['w']), float(mo['h'])
    except (TypeError, ValueError, KeyError):
        return None
    xf = motion_xform(mo, src_w, src_h, W, H)
    if xf is None or not src_w or not src_h:
        return None
    k, px, py, ax, ay = xf
    corners = (px - k * ax, px + k * (src_w - ax), py - k * ay, py + k * (src_h - ay))
    if all(abs(c - e) <= 1 for c, e in zip(corners, (0, W, 0, H))):
        return True
    return (abs(k - 1) < 1e-6 and abs(px - W / 2) <= .5 and abs(py - H / 2) <= .5
            and abs(ax - src_w / 2) <= .5 and abs(ay - src_h / 2) <= .5)


def framing_verdict(png, src, xf, got, seq_w, grab_w):
    """--motion's framing proof of one grab (grey-source.py framing(), FRAME_TOL sequence px scaled to the grab) ->
    (kind, the main line's framing word, [notes], scale pinned)."""
    tol = FRAME_TOL * grab_w / float(seq_w or grab_w)
    fr = grey.framing(png, src['w'], src['h'], xf, got, tol)
    rows, (seen, miss) = fr['boundaries'], fr['cover']
    pinned = [r for r in rows if r['kind'] == 'pinned']
    wrong = [r for r in rows if r['kind'] in ('lost', 'off') or r['kind'] == 'pinned' and abs(r['err']) > tol]
    notes = []
    for r in wrong[:4]:
        where = f"{r['name']} ({r['axis']} {r['at']:.1f})"
        if r['kind'] == 'pinned':
            notes.append(f"framing: the {r['name']} reads at {r['axis']} {r['got']:.1f}, the Motion puts it at "
                         f"{r['at']:.1f}: {r['err']:+.1f} px, over the {tol:.1f} px tolerance")
        else:
            notes.append(f'framing: the {where}: {r["note"]}')
    if miss:
        x, y, want, g, v = miss[0]
        notes.append(f'framing: {len(miss)} of {seen} points clear of every boundary read off the grey the Motion puts '
                     f'there (first: {v:.0f} at ({x}, {y}) where it puts the {want}, {g}): the source is not where '
                     'the Motion puts it (or a track under it shows: --track-mute)')
    if fr['verdict'] == 'fail':                            # a number on the line only where a boundary was FOUND
        off = [r['err'] for r in wrong if r['kind'] == 'pinned']
        return 'fail', (f'framing {max(off, key=abs):+.1f} px' if off else 'framing off'), notes, fr['scale']
    if fr['verdict'] == 'unmeasured':
        return 'unmeasured', 'framing ?', [f"framing not proven: {fr['why']}"], fr['scale']
    worst = max(pinned, key=lambda r: abs(r['err']))
    notes.append(f"framing: {len(pinned)} boundar{'y' if len(pinned) == 1 else 'ies'} within {tol:.1f} px of where "
                 f"the Motion puts {'it' if len(pinned) == 1 else 'them'} (worst the {worst['name']}, "
                 f"{worst['err']:+.1f} px), {seen} points on their grey")
    if not fr['scale']:
        notes.append('Scale unpinned: one boundary shows each way and no edge of the source parallel to it (the source '
                     'fills the frame), so a zoom about where they cross would read the same; only the frame border '
                     'bounds it')
    return 'ok', f"framing {worst['err']:+.1f} px", notes, fr['scale']


# Track Output on the named video tracks: returns what each was, so it can be put back exactly; TO null only reads.
# Every index is checked (on the sequence, and not named twice) before ANY track is touched: a bad name half-way
# down the list used to leave the tracks before it muted with nothing recorded to put them back.
MUTE_ES = r"""(function(){
var ID = @ID@, IDX = @IDX@, TO = @TO@;
var s = app.project.activeSequence;
if (!s || String(s.sequenceID) !== ID) return "ERROR: the active sequence changed before the mute";
var n = s.videoTracks.numTracks, seen = {};
for (var k = 0; k < IDX.length; k++) {
  if (!(IDX[k] >= 0 && IDX[k] < n)) return "ERROR: no V" + (IDX[k] + 1) + " on " + s.name + " (" + n + " video tracks): nothing muted";
  if (seen[IDX[k]]) return "ERROR: V" + (IDX[k] + 1) + " named twice: nothing muted";
  seen[IDX[k]] = 1;
}
var was = [];
for (var j = 0; j < IDX.length; j++) was.push(s.videoTracks[IDX[j]].isMuted() ? 1 : 0);
if (TO) for (var m = 0; m < IDX.length; m++) s.videoTracks[IDX[m]].setMute(TO[m]);
return JSON.stringify(was);
})()"""


def fill(es, **kw):
    for k, v in kw.items():
        es = es.replace(f'@{k}@', json.dumps(v))
    return es


def track_index(name):
    m = re.fullmatch(r'[Vv](\d+)', str(name).strip())
    if not m or int(m.group(1)) < 1:
        raise ValueError(f'bad video track {name!r}: V1..Vn')
    return int(m.group(1)) - 1


def read_track(t):
    """(head, clips) of the ACTIVE sequence: its name, id, ticks per frame, and track t's clips in time order."""
    head = json.loads(pes.es(HEAD_ES))
    if head.get('error'):
        sys.exit(f"{head['error']}: nothing grabbed.")
    if not int(head.get('tpf') or 0) > 0:
        sys.exit(f"could not read the frame rate of {head['name']!r}: nothing grabbed.")
    if t >= int(head.get('video') or 0):
        sys.exit(f"{head['name']!r} has {head.get('video')} video track(s), no V{t + 1}: nothing grabbed.")
    rows = pes.paged(lambda n0, n1: fill(PAGE_ES, ID=head['id'], T=t, N0=n0, N1=n1))
    clips = [dict(r, start=int(r['start']), end=int(r['end']), inp=int(r['inp']),
                  item_in=None if r.get('item_in') == '?' else int(r.get('item_in') or 0)) for r in rows]
    return head, sorted(clips, key=lambda c: c['start'])


def grab(job, t, out):
    """The program frame at sequence time t -> out.png, through the bridge's `frame` (which runs THE GUARD on the job
    for every grab, so a switch of the active sequence between grabs refuses instead of grabbing the wrong cut)."""
    r = subprocess.run(['node', str(HERE / 'premiere-bridge.mjs'), 'frame',
                        json.dumps({'time': t, 'out': str(out), 'job': str(job)})], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'frame grab at {t:.6f}s: {pes._why(r.stderr, (r.stdout or "").strip())}')
    return (r.stdout or '').strip().splitlines()[-1] if (r.stdout or '').strip() else ''


def clear_previews(job):
    """--clear-previews: the bridge's `clear-previews` (THE GUARD included) before any grab, or no grab at all."""
    r = subprocess.run(['node', str(HERE / 'premiere-bridge.mjs'), 'clear-previews', json.dumps({'job': str(job)})],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'clear-previews: {pes._why(r.stderr, (r.stdout or "").strip())}\n'
                 '  nothing grabbed: a stale cache frame would pass for the write under proof')
    print((r.stdout or '').strip().strip('"'), flush=True)


def parse_at(spec, tpf):
    """'12.5,300f' -> sequence frames: seconds are floored like the Program monitor (the bridge's frameAt), 'Nf' is
    frame N."""
    frames = []
    for tok in (x.strip() for x in str(spec).split(',') if x.strip()):
        if tok.lower().endswith('f'):
            f = int(tok[:-1])
        else:
            f = math.floor((float(tok) + 1e-6) * TPS / tpf)
        if f < 0:
            raise ValueError(f'--at {tok}: before the sequence start')
        frames.append(f)
    if not frames:
        raise ValueError('--at names no time')
    return frames


def grab_time(f, tpf):
    """Seconds to ask the bridge for sequence frame f: its start plus 1e-4 s, frame f under a floor or a rounding."""
    return f * tpf / TPS + NUDGE


def clip_at(clips, f, tpf):
    """The clip on the track covering sequence frame f, compared in ticks, or None (a gap)."""
    t = f * tpf
    for c in clips:
        if c['start'] <= t < c['end']:
            return c
    return None


def expected(clip, f, tpf, fps):
    """The source frame clip `clip` should show at sequence frame f, and the notes that go with it. `fps` is the
    source's rate (a Fraction). A subclip's in-point counts from where its item starts in the media (item_in: the
    module docstring), and that is the ONLY reading the frame is held to. Returns (frame, [notes])."""
    stpf = Fraction(TPS) / fps                                    # ticks per SOURCE frame, exact
    same_rate = stpf == tpf

    def frame(ticks):                                             # the frame a source time aims at
        x = Fraction(ticks) / stpf
        return math.floor(x + Fraction(1, 2)) if same_rate else math.floor(x)

    off = f * tpf - clip['start']                                 # ticks into the clip
    src = clip['item_in'] + clip['inp'] + off                     # the source time the frame asks for, in ticks
    n, notes = frame(src), []
    if same_rate and math.floor(Fraction(src) / stpf) != n:
        notes.append(f'in-point {float(src - n * stpf):+.0f} ticks off the source frame grid: Premiere shows the '
                     f'floor, frame {math.floor(Fraction(src) / stpf)}')
    if not same_rate:
        notes.append(f'mixed rate ({float(fps):.3f} fps source on a {TPS / tpf:.3f} fps sequence): expected is the '
                     'frame at or before, unproven live')
    if clip['item_in']:
        notes.append(f"subclip (its item starts at source frame {float(Fraction(clip['item_in']) / stpf):.3f}, its "
                     f"VideoInPoint offset): the in-point is read RELATIVE to it; read as source time it would expect "
                     f"#{frame(clip['inp'] + off)}")
    return n, notes


def verdict(exp, src, got, lv, others):
    """-> ('ok' | 'fail' | 'unmeasured', delta or None, got label, note). `src` is the expected source's probe,
    `got` the decoded number (None when the grab is not grey-coded), `lv` the grab's measured (body, band left,
    band right) luma, `others` the probes of the track's other media."""
    name = src['name']
    first, span = src['first'], src['frames'] or grey.LIMIT
    measured = all(v is not None for v in lv)
    want = grey.levels(first + exp)
    # No grey-coded frame is black in all three regions (the band's halves are 110 levels apart), so a black grab is
    # nothing rendering where the track says a clip plays: the defect class this proof exists for, never frame 0.
    if measured and all(v <= 16 + DRIFT for v in lv):
        return 'fail', None, 'BLACK', ('nothing renders where the track says this clip plays: a disabled clip, a '
                                       'hole the readback does not show, or a black layer above the track (--track-mute)')
    if got is not None and got == first + exp:
        return 'ok', 0, f'{name}#{exp}', ''
    # A decoded number already has every region within half a level of its grey and the band's halves paired, so a
    # number that is a frame of a source on the track IS that frame, before any drift reading: a slip of 67, 86, 134
    # or 153 frames leaves the body within 2 levels of the expected grey, with the band exact.
    if got is not None and first <= got < first + span:
        near = got // grey.SPAN == (first + exp) // grey.SPAN and abs(grey.levels(got)[0] - want[0]) <= DRIFT
        return 'fail', got - first - exp, f'{name}#{got - first}', (
            'the body is within 2 levels of the expected grey and the band exact: a real slip, or a grey drift on '
            'the body alone (a LUT would show on every row)' if near else '')
    if got is not None:
        for o in others:
            if o['first'] is not None and o['first'] <= got < o['first'] + (o['frames'] or grey.LIMIT):
                return 'fail', None, f"{o['name']}#{got - o['first']}", 'a frame of ANOTHER source'
    if measured and all(abs(v - w) <= DRIFT for v, w in zip(lv, want)):
        off = '/'.join(f'{v - w:+.1f}' for v, w in zip(lv, want))
        return 'unmeasured', None, 'no code' if got is None else f'code {got}', (
            f'LEVEL DRIFT: the grey is {off} levels off the expected frame, not a frame away (colour management or a '
            'LUT on the path): not a verdict')
    if got is None:
        return 'unmeasured', None, 'no code', (f'the grab is not a grey-coded frame ({grey.show(lv)}): mute what '
                                              'covers the track, or the source does not fill the frame')
    return 'fail', None, f'code {got}', 'a number no source on the track carries'


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job', help='the job folder (projects/<job>): its project must be the active one')
    ap.add_argument('--at', required=True, help='comma list: seconds, or <n>f for sequence frame n')
    ap.add_argument('--track', default='V1', help='the track the frames must come from (default V1)')
    ap.add_argument('--track-mute', default='', help='video tracks to switch off for the grabs, e.g. V2,V3')
    ap.add_argument('--clear-previews', action='store_true',
                    help="delete the sequence's preview renders first (after any write under proof)")
    ap.add_argument('--out', help='grab folder (default <job>/review/frame-proof)')
    ap.add_argument('--motion', action='store_true',
                    help="read each clip's Motion at the frame, decode the source where it puts it, and prove the "
                         f'framing: every boundary of the code that shows within {FRAME_TOL} px of where it puts it')
    a = ap.parse_args(argv)
    job = Path(a.job).resolve()
    try:
        t = track_index(a.track)
        mute = sorted({track_index(x) for x in a.track_mute.split(',') if x.strip()})   # V2,v2 is ONE track
    except ValueError as e:
        ap.error(str(e))
    if t in mute:
        ap.error(f'--track-mute switches off {a.track}, the track under proof')
    out = Path(a.out).resolve() if a.out else job / 'review' / 'frame-proof'

    require_job_project(pes.es, job)
    head, clips = read_track(t)
    tpf = int(head['tpf'])
    try:
        frames = parse_at(a.at, tpf)
    except ValueError as e:
        ap.error(str(e))
    missing = [i for i in mute if i >= int(head.get('video') or 0)]
    if missing:
        ap.error(f"--track-mute {', '.join(f'V{i + 1}' for i in missing)}: {head['name']!r} has {head.get('video')} "
                 'video track(s); nothing muted, nothing grabbed')
    if a.clear_previews:
        clear_previews(job)
    else:
        print('previews kept: after a scripted write pass --clear-previews, or a stale cache frame from before the '
              'write can pass for it (lanes/premiere/lab-notes.md § stale render cache)', file=sys.stderr)

    probes = {}

    def media(path):
        if path not in probes:
            p = {'first': None, 'frames': None, 'fps': None, 'w': 0, 'h': 0}
            if path and Path(path).is_file():
                try:
                    p = grey.probe(path)
                except (subprocess.CalledProcessError, OSError, ValueError):
                    pass
            p['name'] = Path(path).name if path else '(no media)'
            probes[path] = p
        return probes[path]

    others = [media(c['path']) for c in clips if c.get('path')]
    print(f"{head['name']} · {a.track} · {len(clips)} clip(s) · {TPS / tpf:.3f} fps · grabs in {out}")
    kinds, was, unpinned = [], None, []

    def row(kind, line):                                      # printed as it lands: a grab takes a second or two
        kinds.append(kind)
        print(line, flush=True)

    if mute:   # what each track IS, read before anything is switched, so the finally can always put it back
        was = json.loads(pes.es(fill(MUTE_ES, ID=head['id'], IDX=mute, TO=None)))
    try:
        if mute:
            pes.es(fill(MUTE_ES, ID=head['id'], IDX=mute, TO=[1] * len(mute)))
            print('track output OFF for the grabs: ' + ', '.join(f'V{i + 1}' for i in mute))
        for f in frames:
            tg = grab_time(f, tpf)
            c = clip_at(clips, f, tpf)
            lead = f'frame {f:>6} ({tg:.4f}s)'
            if c is None:
                row('unmeasured', f'{lead}  no clip on {a.track}: a gap')
                continue
            src = media(c['path'])
            where = f"{a.track} clip {c['i']} {src['name']}"
            if abs(float(c.get('speed') or 1) - 1) > 1e-9:
                row('unmeasured', f"{lead}  {where}  speed {c['speed']}: the mapping holds at 100 % only")
                continue
            if src['first'] is None or not src['fps']:
                row('unmeasured', f'{lead}  {where}  not a grey source (workflows/grey-source.py writes one)')
                continue
            if c['item_in'] is None:
                row('unmeasured', f"{lead}  {where}  its project item's metadata did not read: where a subclip "
                                  'starts in the media is unknown')
                continue
            tc = src.get('timecode')
            if tc and src.get('tc_frames') is None:
                row('unmeasured', f'{lead}  {where}  start timecode {tc} does not parse at {src["fps"]}: where the '
                                  'clip starts in the media is unknown')
                continue
            tc_ticks = round(src.get('tc_frames', 0) * Fraction(TPS) / src['fps'])   # the timecode, on the source grid
            if c['item_in'] < tc_ticks:
                row('unmeasured', f"{lead}  {where}  its item offset {c['item_in']} ticks is before the media's start "
                                  f'timecode {tc} ({tc_ticks} ticks): Premiere is not on the file\'s timecode clock, '
                                  'so where the clip starts is unknown')
                continue
            exp, notes = expected(dict(c, item_in=c['item_in'] - tc_ticks), f, tpf, src['fps'])
            if tc:
                notes.append(f'start timecode {tc} ({src["tc_frames"]} frames) taken off the item offset')
            png = out / f'f{f:06d}'
            # The last run's grab must never pass for this one: the bridge's only proof that a grab LANDED is that
            # <out>.png exists afterwards (Premiere says "exported" either way), which means nothing over an old file.
            Path(f'{png}.png').unlink(missing_ok=True)
            xf, framed = None, ''
            mt = float(Fraction(c['inp'] + f * tpf - c['start'], TPS))       # the frame's media time on the clip
            mo = read_motion(head['id'], t, c['i'], mt)
            moved = f"Scale {mo.get('scale')} Position {mo.get('pos')} Anchor Point {mo.get('anchor')}"
            if not a.motion:
                rest = at_rest(mo, src['w'], src['h'])
                if rest is False:
                    row('unmeasured', f"{lead}  {where}  expected {src['name']}#{exp}  not grabbed  UNMEASURED\n"
                                      f"{'':>8}its Motion moves the source here ({moved}): the plain read looks for the "
                                      'code where an unmoved source sits, and reads a moved one as no code or a false '
                                      'BLACK. Re-run with --motion')
                    continue
                if rest is None:
                    notes.append(f'its Motion did not read ({mo}): read as unmoved; if the clip is keyed, --motion')
            said = grab(job, tg, png)
            if a.motion:
                g = grey.probe(f'{png}.png')
                xf = motion_xform(mo, src['w'], src['h'], g['w'], g['h'])
                notes = notes + ([f'Motion: {moved} (the code read where it puts the source)'] if xf else
                                 [f'Motion did not read ({mo}): measured as unscaled, the framing not proven'])
            (got, *lv), = grey.read(f'{png}.png', src['w'], src['h'], xf)
            kind, delta, label, note = verdict(exp, src, got, lv, [o for o in others if o is not src])
            if a.motion and got is not None and kind != 'unmeasured':
                fk, framed, fnotes, pinned = ('unmeasured', 'framing ?', [], True) if xf is None else \
                    framing_verdict(f'{png}.png', src, xf, got, mo.get('w'), g['w'])
                kind = 'fail' if 'fail' in (kind, fk) else 'unmeasured' if 'unmeasured' in (kind, fk) else 'ok'
                notes = notes + fnotes
                unpinned.append(fk == 'ok' and not pinned)
                framed = f'  {framed}'
            d = 'delta ?' if delta is None else f'delta {delta:+d}'
            line = f"{lead}  {where}  expected {src['name']}#{exp}  got {label}  {d}{framed}  {kind.upper()}"
            if got is None and kind == 'unmeasured':
                g = grey.probe(f'{png}.png')
                if abs(g['w'] * src['h'] - g['h'] * src['w']) > 0.01 * g['h'] * src['w']:
                    notes = notes + [f"the grab is {g['w']}x{g['h']} and the source {src['w']}x{src['h']}: a source "
                                     'that does not fill the frame (letterboxed, or cropped at 100 %) cannot be read']
            for n in ([note] if note else []) + notes:
                line += f'\n{"":>8}{n}'
            if 'TRACK OUTPUT OFF' in said:
                line += f'\n{"":>8}bridge: {said}'
            row(kind, line)
    finally:
        if mute and was is not None:
            back = ', '.join(f"V{i + 1} {'off' if w else 'on'}" for i, w in zip(mute, was))
            try:
                pes.es(fill(MUTE_ES, ID=head['id'], IDX=mute, TO=was))
            except SystemExit as e:
                print(f'COULD NOT RESTORE track output ({e}): set it back by hand: {back}', file=sys.stderr)
                raise
            print('track output restored: ' + back)
    n = {k: kinds.count(k) for k in ('ok', 'fail', 'unmeasured')}
    loose = sum(unpinned)
    print(f"{len(kinds)} frame(s): {n['ok']} match, {n['fail']} FAIL, {n['unmeasured']} unmeasured"
          + (f" ({loose} of the matches with the Scale unpinned: no edge of the source on the frame)" if loose else ''))
    return 1 if n['fail'] else 2 if n['unmeasured'] else 0


if __name__ == '__main__':
    sys.exit(main())
