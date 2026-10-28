#!/usr/bin/env python3
"""live-edl.py: the LIVE V1 of the active Premiere sequence -> transcript/cuts.json, source-out DERIVED, never read.

  uv run lanes/premiere/live-edl.py projects/<job>                        # read V1, diff it against transcript/cuts.json
  uv run lanes/premiere/live-edl.py projects/<job> --sequence "<name>"    # the ACTIVE sequence must carry this name
  uv run lanes/premiere/live-edl.py projects/<job> --write                # back cuts.json up, write the live cut into it
  uv run lanes/premiere/live-edl.py projects/<job> --live-out live.json   # [[src_in, src_out], ...] in EDL order, the
                                                                          #   input of `workflows/cut-audit.py --live`
  uv run lanes/premiere/live-edl.py projects/<job> --sequence "<job> AD" --edl transcript/cuts.ad.json --write
                                                                          # a sequence that carries ANOTHER EDL

THE SOURCE OUT IS inPoint + (end - start), IN TICKS. NEVER trackItem.outPoint: after an in-place `clip.end = t`
extend Premiere's outPoint reads STALE forever. On a 2026-09-21 job a +21-frame extend left outPoint 0.876 s short;
that stale value was read as a creator trim, cuts.json and the canonical transcript were rewritten from it, and seven
scenes after it ran 0.876 s early. Every clip whose outPoint disagrees with its own length by more than a frame is
printed as STALE-OUTPOINT: information, never a failure, because this reader does not use it.

Each V1 clip is mapped to the EDL by its MEDIA basename (the replay lays one project item per `clip` basename) and
carries the fields of the old segment whose source span it matches best: the most shared source RELATIVE to the two
spans' union, so a cold-open hook that is a sub-span of a body line, hand-extended, stays the hook (an absolute overlap
mapped it onto the body line, which then read as a split and the hook as deleted), and first a segment no other clip
fits better, so a body line trimmed tight around its hook stays the body line. A boundary more than half a frame
off the EDL (one frame is a real hand move; the replay lands untouched ones on the nearest frame) is the finish
surface's decision: the old pin_*, `beat` (out) and `_refine` side are dropped, the new boundary is stamped `pin_in` /
`pin_out` (rough-cut § a boundary a human decided is pinned for the audit), and the transcript is re-derived from
words.json with polish-boundaries.py's rule: the span keeps every word it PLAYS (inside it, or overlapped by 30 ms or
half the word), so a killed neighbour a boundary grazes never joins the text and a kept word whose aligner end
overshoots a hand OUT does; clips that continue each other in source (a razor split) share those words, each going to
the clip holding its END, else its START. cut-proof holds the laid dialogue to these texts. A clip that shares under
half a frame of source with a segment is a neighbour laid against it, never that segment. `media` / `note` and every
other field are kept. `_timeline` = [start, end] of the clip in sequence seconds (the graphics tools read it).

A MIXED-RATE clip (a source rate other than the sequence's: 24 fps footage on a 23.976 sequence) is judged against
where the replay LANDS each EDL time, never a half-frame window: the replay asks for the first source frame at or above
the nearest sequence frame q (premiere-bridge.mjs replay `land()`), so an untouched in-point reads back on the SOURCE
grid, up to a source frame past q. A half-frame window read 154 false moves on your-job's untouched replay, and
--write would have pinned every one. An untouched side is one whose live value is that landing (q, the source frame S,
or S floored to the sequence grid; an out also as the in's landing plus the replay's laid length), to 10 microseconds
(an out also plus the exact drift a head trim of k source frames carries, k * (1/rate - frame): 41.7 microseconds a
frame at 24 on 23.976, never a tolerance that grows with the trim); a one-frame hand move of either kind is off it. An untouched side of a
mixed-rate clip keeps the EDL's own value, verbatim (its source-grid readback would round to the NEXT sequence frame on a
re-replay); --live-out still carries the live values, where the audio plays. Live (2026-09-23, 24 on 23.976) every
side read S floored to the sequence grid, which is q on a faster source; the source-grid readback is your-job's.
That landing rule is only sound for a FASTER source (its frame shorter than the sequence's), where every landing sits
inside one sequence frame. A SLOWER source (23.976 footage on a 29.97 sequence, 24 on 25) lands up to a whole source
frame past q, so a one-frame hand move can sit ON a landing. There the rule is the one Premiere proved live (2026-09-23,
21/21 clips at 23.976 on 29.97, both sides, to the tick): each side lands on S floored back to the sequence grid, the in
on floor(S_in) and the derived out on floor(S_out), so the V1 length is NOT q_out - q_in (8 of 21 clips were a sequence
frame off it) and an in can read q or S within one timeline. A side is untouched only when it sits on that landing.

Refused, nothing written (exit 2): a subclip laid by `premiere-bridge.mjs lay` ("VID <item> @<in>s": its in-point is
SUBCLIP-relative, and the mapping back to source time is not proven live), a clip with no media file, a clip at a
speed other than 100 % or reversed, a disabled clip, a clip laid from a segment's `media` (a lip-sync render on its own
clock) whose length changed, and a clip whose media neither the EDL (`clip` / `media`) nor words.json names: its
in-point is on that file's own clock (a re-rendered take, an ad's own CTA render, a camera angle over the dialogue),
so it cannot be written as source time.

--write and --live-out also refuse a sequence that is not the job's own (the project holds a sequence named after the
job folder, and this is another one, e.g. its AD clone) unless --edl names the EDL that sequence carries: its cut must
never land in the organic's transcript/cuts.json.

A multi-section job (projects/<job>/sections/<s>/ beside the parent's own EDL) shares ONE V1: the clips of this job's
media must form one contiguous run, and the other sections' clips are left alone.

Exit: 0 read (and written, with --write) · 1 V1 does not add up (a gap, an overlap, or durations that do not sum to the
run) · 2 refused or failed (the job guard, a bridge error, nothing of this job's on V1, or any refusal above), so a
script can tell a timeline that does not add up from a run that never read one.
"""
import argparse, json, math, os, re, shutil, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes                                                    # noqa: E402  (the ONE bridge runner)
from job_guard import job_root, require_job_project           # noqa: E402

for _s in (sys.stdout, sys.stderr):   # a transcript can carry non-ASCII; Windows pipes default to cp1252
    try:
        if (getattr(_s, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
            _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

TPS = 254016000000                                            # Premiere ticks per second
SUBCLIP = re.compile(r'^(VID|AUD) .+ @\d+(?:\.\d+)?s$')       # the names `premiere-bridge.mjs lay` gives its subclips
EXPORTER = '.claude/skills/rough-cut/scripts/export-transcript.py'
LAND_TOL = 1e-5                                               # s: a replay landing read back (ticks are exact)

HEAD_ES = r"""(function(){
var s = app.project.activeSequence;
if (!s) return JSON.stringify({error: "no active sequence"});
var o = {name: String(s.name), id: String(s.sequenceID), frame: 0, tracks: s.videoTracks.numTracks, v1: 0, names: []};
for (var i = 0; i < app.project.sequences.numSequences; i++) o.names.push(String(app.project.sequences[i].name));
try { o.frame = Number(s.timebase); } catch (e) {}
if (!(o.frame > 0)) { try { o.frame = Math.round(s.getSettings().videoFrameRate.seconds * 254016000000); } catch (e) {} }
if (s.videoTracks.numTracks) o.v1 = s.videoTracks[0].clips.numItems;
return JSON.stringify(o);
})()"""

# One page of V1, every number as a TICKS string (seconds are derived in Python). ES3: no reserved words as keys.
PAGE_ES = r"""(function(){
var ID = @ID@, N0 = @N0@, N1 = @N1@;
var s = app.project.activeSequence;
if (!s || String(s.sequenceID) !== ID) return "ERROR: the active sequence changed during the read";
var tr = s.videoTracks[0], out = [];
for (var i = N0; i < N1 && i < tr.clips.numItems; i++) {
  var c = tr.clips[i], pi = null;
  var r = {i: i, name: String(c.name), item: "", path: "", item_in: null,
           start: String(c.start.ticks), end: String(c.end.ticks),
           inp: String(c.inPoint.ticks), outp: String(c.outPoint.ticks),
           speed: 1, reversed: false, disabled: false, fps: 0};
  try { pi = c.projectItem; } catch (e) {}
  if (pi) {
    try { r.item = String(pi.name); } catch (e) {}
    try { r.path = String(pi.getMediaPath() || ""); } catch (e) {}
    try { r.item_in = String(pi.getInPoint().ticks); } catch (e) {}
    try { r.fps = Number(pi.getFootageInterpretation().frameRate) || 0; } catch (e) {}
  }
  try { r.speed = c.getSpeed(); } catch (e) {}
  try { r.reversed = !!c.isSpeedReversed(); } catch (e) {}
  try { r.disabled = !!c.disabled; } catch (e) {}
  out.push(r);
}
return JSON.stringify(out);
})()"""


def page_es(sid, n0, n1):
    return PAGE_ES.replace('@ID@', json.dumps(sid)).replace('@N0@', str(n0)).replace('@N1@', str(n1))


def base(p):
    return str(p or '').replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]


def secs(ticks):
    return ticks / TPS


def refuse(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def read_v1(sequence):
    """The active sequence's head and its V1 clips in time order, ticks as ints and the source out derived."""
    head = json.loads(pes.es(HEAD_ES))
    if head.get('error'):
        refuse(f"{head['error']}: nothing read.")
    if sequence and head['name'] != sequence:
        refuse(f"the active sequence is {head['name']!r}, not the requested {sequence!r}: nothing read.")
    frame = int(float(head.get('frame') or 0))
    if frame <= 0:
        refuse(f"could not read the frame rate of {head['name']!r}: nothing read.")
    rows = []
    for r in pes.paged(lambda n0, n1: page_es(head['id'], n0, n1)):
        s, e, i, o = (int(r[k]) for k in ('start', 'end', 'inp', 'outp'))
        rows.append(dict(r, start=s, end=e, inp=i, outp=o, dout=i + (e - s), base=base(r.get('path'))))
    rows.sort(key=lambda r: r['start'])
    return head, frame, rows


def src_rate(fps):
    """A footage interpretation's frame rate, the NTSC floats back to their rationals (the replay's own mapping)."""
    x = float(fps or 0)
    for n in (24000 / 1001, 30000 / 1001, 60000 / 1001):
        if abs(x - n) < 0.01:
            return n
    return x if x > 0 else 0.0


def landings(t, fs, rate):
    """Where premiere-bridge.mjs `replay` lands EDL time t on a source of `rate` fps: the nearest sequence frame q,
    the first source frame at or above it S (what it asks for), and S floored back to the sequence grid."""
    q = round(t / fs) * fs
    s = math.ceil(q * rate - 1e-6) / rate
    return [q, s, math.floor(s / fs + 1e-6) * fs]


def plays(w, a, b):
    """polish-boundaries.py's `plays`: source [a, b] plays a word inside it, or one it overlaps by 30 ms or half the
    word. A killed neighbour a boundary grazes never joins the text; a kept word whose aligner end overshoots a hand
    OUT ('tasks,' 572.04-572.52 against an OUT at 572.447, 2026-09-20) does."""
    s, e = float(w['start']), float(w['end'])
    ov = min(e, b) - max(s, a)
    return (a <= s and e <= b) or (ov > 0 and ov >= min(0.03, (e - s) / 2))


def texts(run, words, frame):
    """Each clip's transcript re-derived from words.json: the words its source span plays. Clips that continue each
    other in source (a razor split on V1) own them the polish's way: every word the stretch plays goes to ONE clip,
    the one holding its END (an aligner-stretched word starts in the silence), else its START, else the nearest, so a
    word across the razor is never promised twice."""
    out, j = [], 0
    while j < len(run):
        k = j + 1
        while k < len(run) and run[k]['base'] == run[j]['base'] and abs(run[k]['inp'] - run[k - 1]['dout']) <= frame / 2:
            k += 1
        spans = [(secs(r['inp']), secs(r['dout'])) for r in run[j:k]]
        a, b, owned = spans[0][0], spans[-1][1], [[] for _ in spans]
        for w in words.get(run[j]['base'], []):
            if w.get('start') is None or w.get('end') is None or not plays(w, a, b):
                continue
            s, e = float(w['start']), float(w['end'])
            i = next((i for i, (p, q) in enumerate(spans) if p <= e <= q), None)
            if i is None:
                i = next((i for i, (p, q) in enumerate(spans) if p <= s <= q), None)
            if i is None:
                i = min(range(len(spans)), key=lambda i: max(0.0, spans[i][0] - e, s - spans[i][1]))
            owned[i].append(str(w.get('w', '')).strip())
        out += [' '.join(t for t in o if t) for o in owned]
        j = k
    return out


def media_of(edl, words):
    """Every media basename one EDL can lay: its segments' `clip` and `media`, and its words.json's clips."""
    names = set()
    for p, key in ((edl, 'segments'), (words, 'clips')):
        if p.exists():
            for s in json.loads(p.read_text(encoding='utf-8')).get(key, []):
                names.add(base(s.get('clip')))
                if s.get('media'):
                    names.add(base(s['media']))
    names.discard('')
    return names


def siblings(job):
    """The other EDLs sharing this job's timeline: the parent's own and every sections/<s>/ sub-job's."""
    root = job_root(job)
    cands = [root] + sorted(p for p in (root / 'sections').glob('*') if p.is_dir())
    return [c for c in cands if c.resolve() != job.resolve() and (c / 'transcript' / 'cuts.json').exists()]


def assign(run, segs, fs):
    """Each clip -> the index of the old segment it carries, or None for new material. The fit is the shared source
    over the two spans' union (frames), never the shared source alone: a hand-extended hook that is a sub-span of a
    body line shares more source with the body segment than with its own, but matches its own far better. A clip goes
    first to a segment it fits AS WELL AS any clip does (a mutual match): a body line trimmed around its hook fits the
    hook better than its own segment, but the hook clip fits the hook better still, so the body clip keeps its own.
    Then the fit; ties (a cold open replaying a body line) go to the segment not taken yet, then to the next in order."""
    fit = []
    for r in run:
        row = {}
        for k, s in enumerate(segs):
            if s.get('media'):
                if base(s['media']) == r['base']:
                    row[k] = 1.0
                continue
            if base(s.get('clip')) != r['base']:
                continue
            a, b = secs(r['inp']), secs(r['dout'])
            shared = round((min(b, float(s['end'])) - max(a, float(s['start']))) / fs)
            if shared <= 0:        # under half a frame of shared source: a neighbour laid against it, not this segment
                continue
            row[k] = shared / max(1, round((max(b, float(s['end'])) - min(a, float(s['start']))) / fs))
        fit.append(row)
    top = {}
    for row in fit:
        for k, ov in row.items():
            top[k] = max(top.get(k, 0.0), ov)
    out, used, prev = [], set(), -1
    for row in fit:
        best = None
        for k, ov in row.items():
            rank = (ov >= top[k] - 1e-9, ov, k not in used, -abs(k - (prev + 1)))
            if best is None or rank > best[0]:
                best = (rank, k)
        k = best[1] if best else None
        out.append(k)
        if k is not None:
            used.add(k)
            prev = k
    return out


def check(run, frame, v1_end, whole):
    """V1 must hold the run with no hole: every joint within half a frame, and the derived durations summing to the
    run (to V1's own end on a single-EDL job) within a frame."""
    bad = []
    if whole and run[0]['start'] > frame / 2:
        bad.append(f"GAP {secs(run[0]['start']) * 1000:.0f} ms at the head of V1 (clip {run[0]['i']} starts at "
                   f"{secs(run[0]['start']):.3f}s)")
    for p, q in zip(run, run[1:]):
        g = q['start'] - p['end']
        if abs(g) > frame / 2:
            bad.append(f"{'GAP' if g > 0 else 'OVERLAP'} {secs(abs(g)) * 1000:.0f} ms on V1 at {secs(p['end']):.3f}s "
                       f"(between clip {p['i']} and clip {q['i']})")
    total = sum(r['end'] - r['start'] for r in run)
    ref = v1_end if whole else run[-1]['end'] - run[0]['start']
    if abs(total - ref) > frame:
        bad.append(f"the derived durations add up to {secs(total):.3f}s, but V1 "
                   f"{'ends at' if whole else 'spans'} {secs(ref):.3f}s")
    return bad, total


def carry(r, seg, fs, text):
    """The new segment for one clip: the old one's fields, the live boundaries, its re-derived `text` where they moved."""
    new = json.loads(json.dumps(seg)) if seg is not None else {'clip': r['base']}
    if seg is not None and seg.get('media'):
        # laid from a render on its own clock (a lip-sync clip): its raw span stays as authored (the length was
        # checked equal before this runs), and words.json is not its transcript.
        start, end, moved = float(seg['start']), float(seg['end']), {}
    else:
        # MOVED = off the EDL by more than half a frame. The replay lands every boundary on the NEAREST sequence frame,
        # so an untouched one reads back within half a frame; a one-frame hand move is real (the fused-joint snaps
        # of a hand pass are exactly one frame) and must be pinned like any other.
        start, end = secs(r['inp']), secs(r['dout'])
        moved = {'in': seg is None or abs(start - float(seg['start'])) > fs / 2,
                 'out': seg is None or abs(end - float(seg['end'])) > fs / 2}
        rate = src_rate(r.get('fps'))
        if seg is not None and rate and rate * fs < 1 - 1e-6:
            # SLOWER SOURCE (23.976 on 29.97, 24 on 25): the source frame is LONGER than the sequence frame, so the
            # landings span more than a frame and a one-frame hand move can land ON one. Premiere lays each side on the
            # source frame the replay asked for, floored back to the sequence grid (proven live, module docstring):
            # a side is untouched only on that landing.
            li, lo = landings(float(seg['start']), fs, rate), landings(float(seg['end']), fs, rate)
            moved = {'in': abs(start - li[2]) > LAND_TOL, 'out': abs(end - lo[2]) > LAND_TOL}
            start = start if moved['in'] else float(seg['start'])
            end = end if moved['out'] else float(seg['end'])
        elif seg is not None and rate and abs(rate * fs - 1) > 1e-6:
            # MIXED RATE: the in-point lands on the SOURCE grid, up to a source frame past the nearest sequence
            # frame, so only the replay's own landing is untouched (module docstring). Untouched sides keep the EDL.
            li, lo = landings(float(seg['start']), fs, rate), landings(float(seg['end']), fs, rate)
            # The untouched OUT is judged from the in the REPLAY laid (`_replay_start`, kept when --write pinned a hand-
            # moved in): a pinned in is a live value, not a replay landing, so lengths measured from it never match.
            lb = landings(float(seg.get('_replay_start', seg['start'])), fs, rate)
            lengths = {lo[0] - lb[0], lo[2] - lb[2]}
            off = lambda x, cands: min(abs(x - c) for c in cands)
            # A head trim read back on the source grid (k source frames) shortens the clip by k SEQUENCE frames, so the
            # derived out drifts off the in's landing plus the laid length by the trim times the rate mismatch: 41.7 us
            # a frame at 24 on 23.976. Only a near-1:1 rate pairs source and sequence frames like that.
            # That drift is exact, k * (1/rate - fs) for a trim of k source frames, never an allowance that grows with it.
            near = abs(rate * fs - 1) < 0.01
            drift = lambda c: (0.0, round((start - c) * rate) * (1 / rate - fs)) if near else (0.0,)
            moved = {'in': off(start, li) > LAND_TOL,
                     'out': off(end, lo) > LAND_TOL and all(abs(end - (c + n + d)) > LAND_TOL
                                                             for c in lb for n in lengths for d in drift(c))}
            start = start if moved['in'] else float(seg['start'])
            end = end if moved['out'] else float(seg['end'])
        if seg is not None and rate and abs(rate * fs - 1) > 1e-6:
            # A side a --write already pinned holds the LIVE value, not a replay landing: reading the same timeline
            # again must find it untouched, or every re-read reports the last hand pass as new moves and re-pins it.
            for side, key, live in (('in', 'start', start), ('out', 'end', end)):
                if moved[side] and abs(live - float(seg[key])) <= LAND_TOL:
                    moved[side] = False
            start = start if moved['in'] else float(seg['start'])
            end = end if moved['out'] else float(seg['end'])
            if moved['in'] and not moved['out'] and rate * fs > 1 + 1e-6:
                new['_replay_start'] = seg.get('_replay_start', seg['start'])
    new['start'], new['end'] = round(start, 5), round(end, 5)
    for side, key in (('in', 'start'), ('out', 'end')):
        if seg is not None and not seg.get('media') and not moved.get(side) and float(seg[key]) == (start if side == 'in' else end):
            new[key] = seg[key]                # an untouched side kept the EDL: its value verbatim, never re-rounded
    for side, key in (('in', 'orig_start'), ('out', 'orig_end')):
        if not moved.get(side):
            continue
        if side == 'out':
            new.pop('beat', None)
        if isinstance(new.get('_refine'), dict):
            new['_refine'].pop(key, None)
            if not new['_refine']:
                new.pop('_refine')
        new[f'pin_{side}'] = True              # the finish surface decided this boundary: hold it for the audit
        new['no_refine'] = True                # ...and against the refiner/polish, which re-derive unpinned ones
    if any(moved.values()):
        new['transcript'] = text
    new['_timeline'] = [round(secs(r['start']), 6), round(secs(r['end']), 6)]
    return new, moved


def move_txt(label, old, new, fs, moved=None):
    """One side of a diff row; `moved` (carry()'s verdict) overrides the half-frame test, which a mixed-rate side
    judged against the replay's landing does not use."""
    d = new - old
    if (not moved) if moved is not None else abs(d) <= fs / 2:
        return f"{label} {new:.5f} same"
    verb = ('trimmed' if d > 0 else 'extended') if label == 'IN' else ('extended' if d > 0 else 'trimmed')
    return f"{label} {old:.5f} -> {new:.5f} ({d * 1000:+.1f} ms, {verb})"


def main(argv=None):
    """sync(), with every failure that exits with its message (the job guard's refusals, a pes bridge failure) turned
    into exit 2, so exit 1 only ever means the timeline does not add up."""
    try:
        return sync(argv)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            raise SystemExit(2)
        raise


def sync(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--sequence', help='the name the ACTIVE sequence must carry (also handed to the guard as VE_SEQUENCE)')
    ap.add_argument('--write', action='store_true', help='back up transcript/cuts.json and write the live cut into it')
    ap.add_argument('--live-out', help='write [[src_in, src_out], ...] in EDL order for workflows/cut-audit.py --live')
    ap.add_argument('--edl', help="the EDL this sequence carries (default transcript/cuts.json; relative to the job "
                                  "folder unless it exists as given), e.g. an ad cut's transcript/cuts.ad.json")
    a = ap.parse_args(argv)
    job = Path(a.job).resolve()
    own_edl, words_p = job / 'transcript' / 'cuts.json', job / 'transcript' / 'words.json'
    cuts_p = own_edl
    if a.edl:
        cuts_p = Path(a.edl) if Path(a.edl).is_absolute() or Path(a.edl).exists() else job / a.edl
        cuts_p = cuts_p.resolve()
    for p in (cuts_p, words_p):
        if not p.exists():
            refuse(f"no {p}: nothing read.")
    doc = json.loads(cuts_p.read_text(encoding='utf-8'))
    segs = doc.get('segments', [])
    words = {base(c.get('clip')): c.get('words') or [] for c in json.loads(words_p.read_text(encoding='utf-8')).get('clips', [])}

    # THE GUARD before any read: the job's project, and (new guard) the requested sequence. Then the name ourselves.
    if a.sequence:
        os.environ['VE_SEQUENCE'] = a.sequence
    require_job_project(pes.es, job)
    head, frame, rows = read_v1(a.sequence)
    # A camera whose audio runs early is fixed on the timeline by slipping V1 later than A1 (lanes/premiere/lab-notes.md
    # § the camera A/V offset). The EDL is the AUDIO cut, so the slip (transcript/av-slip.json, beside cuts.json and out
    # of its cut_rev hash) comes back off the V1 read
    sp = job / 'transcript' / 'av-slip.json'
    slip = int(json.loads(sp.read_text(encoding='utf-8')).get('v1_frames', 0)) if sp.exists() else 0
    if slip:
        for r in rows:
            for k in ('inp', 'outp', 'dout'):
                r[k] -= slip * frame
        print(f'V1 carries an A/V slip of {slip} frame(s) ({sp.name}): its in-points are read back {slip} frame(s) earlier')
    fs = frame / TPS
    if not rows:
        refuse(f"V1 of {head['name']!r} is empty: nothing read.")

    # A sequence beside the job's own (its AD clone) carries ANOTHER EDL: its cut never lands in the organic's.
    own = job_root(job).name
    if own in (head.get('names') or []) and head['name'] != own and not a.edl:
        if a.write or a.live_out:
            refuse(f"{head['name']!r} is not the job's own sequence {own!r}, and transcript/cuts.json is the EDL of {own!r}: "
                   f"{'--write' if a.write else '--live-out'} would put this sequence's cut into it. Pass --edl with "
                   f"the EDL this sequence carries (an ad cut: --edl transcript/cuts.ad.json): nothing written.")
        print(f"NOTE {head['name']!r} is not the job's own sequence {own!r}: this is a diff against the EDL of {own!r} "
              f"(--edl names the one this sequence carries)")

    # Scope: on a multi-section job the other EDLs' clips share this V1 and are theirs, not new material. Anything
    # from media no EDL here names is refused below: its in-point is on that file's own clock, never source time.
    sibs = siblings(job)
    known = media_of(cuts_p, words_p)
    others = set().union(*(media_of(s / 'transcript' / 'cuts.json', s / 'transcript' / 'words.json')
                           for s in sibs)) - known if sibs else set()
    run, unknown = [], []
    for r in rows:
        if r['base'] in known:
            run.append(r)
        elif r['base'] not in others:
            unknown.append(r)
    if not run and not unknown:                 # (unknown clips are refused, and named, below)
        refuse(f"no V1 clip of {head['name']!r} is from this job's media ({', '.join(sorted(known)) or 'none'}): "
               f"nothing read.")

    for r in run:
        if abs(r['dout'] - r['outp']) > frame:
            print(f"STALE-OUTPOINT clip {r['i']}: outPoint {secs(r['outp']):.5f}, own length says {secs(r['dout']):.5f} "
                  f"({secs(r['dout'] - r['outp']) * 1000:+.1f} ms). NOT an edit.")

    match = assign(run, segs, fs)
    why, renamed = [], {}
    for r, k in zip(run, match):
        tag = f"clip {r['i']} ({r['name']!r} at {secs(r['start']):.3f}s)"
        if SUBCLIP.match(r.get('item') or ''):
            item_in = '%.5f' % secs(int(r['item_in'])) if r.get('item_in') not in (None, '') else '?'
            why.append(f"{tag} is the subclip {r['item']!r} laid by `premiere-bridge.mjs lay`: its in-point "
                       f"{secs(r['inp']):.5f}s is SUBCLIP-relative (the item's own in point reads {item_in}s), and "
                       f"mapping it back to source time is not proven live")
        if abs(float(r.get('speed') or 1) - 1) > 1e-6 or r.get('reversed'):
            why.append(f"{tag} runs at speed {r.get('speed')}{' reversed' if r.get('reversed') else ''}: an EDL row has no speed")
        if r.get('disabled'):
            why.append(f"{tag} is DISABLED: an EDL row cannot be off. Enable or delete it")
        if k is not None and segs[k].get('media'):
            want, have = float(segs[k]['end']) - float(segs[k]['start']), secs(r['end'] - r['start'])
            if abs(have - want) > fs + 1e-6:
                why.append(f"{tag} is laid from segment {k}'s `media` {base(segs[k]['media'])}, whose clock is not the "
                           f"raw's, and its length changed ({want:.3f}s -> {have:.3f}s): its raw span cannot be derived. "
                           f"Fix segment {k} by hand")
        if r.get('path') and r.get('item') and r['item'] != r['base'] and not SUBCLIP.match(r['item']):
            renamed.setdefault((r['item'], r['base']), []).append(tag)
    # ONE note per renamed item, never one per clip: a long-form's sections each get their own project item of one raw
    # (premiere-pro § Colour labels), and a 37-clip replay printed 37 identical notes (Windows pass, 2026-10-13)
    for (item, b), tags in renamed.items():
        print(f"NOTE {tags[0]}{f' and {len(tags) - 1} more' if len(tags) > 1 else ''}: project item {item!r} is not "
              f"named after its media {b!r} (a renamed item, or a hand-made subclip whose in-point may be subclip-relative)")
    for r in unknown:
        tag = f"clip {r['i']} ({r['name']!r} at {secs(r['start']):.3f}s)"
        if not r.get('path'):
            why.append(f"{tag} has no media file (a nest, a graphic or an adjustment layer): it cannot be an EDL row")
        elif sibs:
            why.append(f"{tag} is from {r['base']!r}, which no EDL of this job names, and this timeline carries more "
                       f"than one EDL: nothing says which one it belongs to")
        else:
            why.append(f"{tag} is from {r['base']!r}, which neither {cuts_p.name} nor words.json names: its in-point "
                       f"is on that file's own clock, not source time (a re-rendered take, an ad's own render, a camera "
                       f"angle). Lay the media the EDL names, or pass --edl with the EDL this sequence carries")
    if why:
        refuse("refused, nothing written:\n  " + "\n  ".join(why))

    # The run must be ONE contiguous stretch of V1 with no hole in it.
    pos = [rows.index(r) for r in run]
    bad = [f"clip {rows[p]['i']} ({rows[p]['base'] or rows[p]['name']!r}) sits inside this job's run but belongs to "
           f"another EDL" for p in range(pos[0], pos[-1] + 1) if rows[p] not in run]
    b2, total = check(run, frame, max(r['end'] for r in rows), whole=not sibs)
    bad += b2

    # The new EDL and the per-segment diff against the current one: only the rows that changed (a moved boundary,
    # new material, a segment played out of order or twice) and the `media` rows this reader did not derive.
    new, lines, moves, prev, live_rows = [], [], 0, -1, []
    tx = texts(run, words, frame)
    for j, (r, k) in enumerate(zip(run, match)):
        seg = segs[k] if k is not None else None
        ns, moved = carry(r, seg, fs, tx[j])
        new.append(ns)
        # --live-out is where the audio PLAYS: the live values, even where an untouched mixed-rate side kept the EDL's
        live_rows.append([ns['start'], ns['end']] if seg is not None and seg.get('media') else
                         [round(secs(r['inp']), 5), round(secs(r['dout']), 5)])
        if seg is None:
            lines.append(f"seg {j:02d} NEW   {r['base']} {ns['start']:.5f}-{ns['end']:.5f}  \"{ns['transcript'][:80]}\"")
            continue
        moves += sum(1 for v in moved.values() if v)
        if any(moved.values()) or seg.get('media') or k <= prev:
            lines.append(f"seg {j:02d} <- #{k:02d}  " + ('[media, carried]' if seg.get('media') else
                         f"{move_txt('IN', float(seg['start']), ns['start'], fs, moved['in'])}  "
                         f"{move_txt('OUT', float(seg['end']), ns['end'], fs, moved['out'])}"))
        prev = k
    gone = [k for k in range(len(segs)) if k not in match]
    for k in gone:
        lines.append(f"DELETED #{k:02d} {float(segs[k]['start']):.5f}-{float(segs[k]['end']):.5f}  "
                     f"\"{(segs[k].get('transcript') or '')[:80]}\"")
    same_shape = match == list(range(len(segs)))
    in_sync = same_shape and not moves
    kept = [k for k in match if k is not None]
    if lines:
        print("\n".join(lines))
    print(f"{len(run)} clip(s) on V1 of {head['name']!r}"
          + (f" ({len(rows) - len(run)} of another EDL's left alone)" if len(rows) != len(run) else '')
          + f" · timeline {secs(run[0]['start']):.3f}-{secs(run[-1]['end']):.3f}s · EDL total {secs(total):.3f}s · "
          + ('OK' if not bad else 'MISMATCH'))
    print(f"{cuts_p.name} is IN SYNC with the timeline" if in_sync else
          f"{cuts_p.name} DIFFERS from the timeline: {moves} boundary move(s), {len(gone)} deleted, {match.count(None)} new"
          + (f", {len(kept) - len(set(kept))} split" if len(kept) != len(set(kept)) else '')
          + (', order changed' if kept != sorted(kept) else '')
          + ('' if a.write else ' (--write syncs it)'))
    if bad:
        print("\n".join(bad))
        print("V1 does not add up: nothing written.")
        return 1

    # cut-audit --live pairs each row with the EDL segment at the same index, so its rows must be THAT EDL's.
    if a.live_out and not (a.write or same_shape):
        refuse(f"--live-out: the live cut no longer maps one-to-one onto {cuts_p.name} ({len(run)} clips vs "
               f"{len(segs)} segments, or out of order), so cut-audit --live would pair the wrong rows. "
               f"Run with --write first: nothing written.")
    out_doc = dict(doc, segments=new)
    if a.write:
        if json.dumps(out_doc, sort_keys=True) == json.dumps(doc, sort_keys=True):
            print(f"{cuts_p.name} already carries the live cut: nothing written.")
        else:
            backup = cuts_p.with_name(f"{cuts_p.stem}.pre-live-{time.strftime('%Y%m%d-%H%M%S')}.json")
            if backup.exists():
                refuse(f"{backup} already exists: nothing written. Re-run in a second.")
            shutil.copyfile(cuts_p, backup)
            tmp = cuts_p.with_name(cuts_p.name + '.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(out_doc, f, indent=1)
            os.replace(tmp, cuts_p)
            rel, brel = (os.path.relpath(x, job).replace(os.sep, '/') for x in (cuts_p, backup))
            print(f"wrote {rel} ({len(new)} segments); the old EDL is {brel}")
            j = a.job.rstrip('/\\')
            if cuts_p == own_edl:
                # ripple-cut FIRST: it re-derives the canonical transcript itself when one exists and backs the old
                # one up as .pre-ripple only if it runs before the exporter (after it, that backup holds the new file).
                print(f"next:\n  uv run workflows/ripple-cut.py {j} --from {brel} --apply\n"
                      f"  uv run {EXPORTER} {j}/transcript/words.json {j}/transcript/cuts.json {j}/outputs/{job.name}.transcript.json"
                      f"   # only if ripple-cut had no canonical transcript to re-derive")
            else:
                print("not the job's own EDL: ripple-cut and export-transcript follow transcript/cuts.json, so nothing "
                      "downstream was re-timed from this one.")
    if a.live_out:
        with open(a.live_out, 'w', encoding='utf-8') as f:
            json.dump(live_rows, f)
        print(f"wrote {a.live_out}: {len(new)} [src_in, src_out] rows for workflows/cut-audit.py {a.job} --live {a.live_out}"
              + ('' if cuts_p == own_edl else f" --edl {os.path.relpath(cuts_p)}"))
    return 0


if __name__ == '__main__':
    sys.exit(main())
