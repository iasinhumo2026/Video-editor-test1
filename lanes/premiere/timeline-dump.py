#!/usr/bin/env python3
"""timeline-dump.py: every clip of a Premiere sequence read BY NAME (never activated), and the diff of two sequences.

  uv run lanes/premiere/timeline-dump.py projects/<job> --sequence "<name>" [--out dump.json]
  uv run lanes/premiere/timeline-dump.py projects/<job> --diff "<seq A>" "<seq B>" [--until <seconds>]

Each track is read in pages of 40 clips, then its transitions the same way. Per clip: track, start, end, inPoint and
the DERIVED source out (inPoint + (end - start); trackItem.outPoint reads stale after an in-place extend,
lanes/premiere/lab-notes.md), both in SOURCE time (a sped clip's inPoint reads source / speed, so both are multiplied
back by its speed), media path, disabled, speed, and one FNV-1a hash of every component property value
(keyframes included: each key's time and value; non-integer numbers at 5 significant digits, because a float32
value can come back one ulp off after a save and reopen). Per transition: track, start, end, name, matchName and the same hash.
The hash is computed INSIDE Premiere, so a Lumetri look blob (hundreds of KB per clip) never crosses the bridge: a
hand dump of one sequence hit the CEP return cap twice at 350840 and 273740 chars and the proof that an ad matched its
organic cut took twelve hand calls (2026-09-23). Every component also carries its own hash, so a diff names the effect
that differs.

--diff compares the two sequences track by track, pairing clips (and, separately, transitions) by start frame, and
prints ONLY what differs: an item present in one sequence alone; a clip's start / end / inPoint / derived out / media
/ disabled / speed / reversed / hash (never its name: a track item's name is a label, and a renamed one plays the
same); a transition's start / end / name / matchName / hash; the frame rate and frame size; each track's mute.

--until T is "identical up to the CTA": only what starts before T seconds is compared, its end (and derived out) is
clamped to T, and every keyed property is hashed as it plays before T: the keys at or before T on the timeline (a
key's time is the clip's MEDIA time, so timeline = start + key - inPoint) and the value where the clip stops counting,
min(end, T). A music bed whose tail fade moved with the ad's new end is then identical before the CTA, while a key
moved before it is not.

The job guard runs first (the job's project), but WHICH sequence is active does not matter: nothing here reads it.

Exit: 0 dumped / identical · 1 the sequences differ · 2 refused or failed (a sequence missing, two carrying the name,
the job guard, a bridge error), so a script never reads a run that compared nothing as a difference.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pes                                                    # noqa: E402  (the ONE bridge runner)
from job_guard import GUARD_ES, require_job_project           # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
            _s.reconfigure(encoding='utf-8')
    except Exception:
        pass

TPS = 254016000000
PAGE = 40
TIMEOUT = 300000           # ms per page: hashing a Lumetri blob per clip is ExtendScript string work, not a lookup

# A track's transitions are read unguarded: a collection Premiere cannot hand over fails the run, it never certifies
# two sequences identical with their crossfades unread.
HEAD_ES = r"""(function(){
var NAME = @NAME@, hits = [], names = [];
for (var i = 0; i < app.project.sequences.numSequences; i++) {
  var q = app.project.sequences[i];
  names.push(String(q.name));
  if (String(q.name) === NAME) hits.push(i);
}
if (hits.length !== 1) return JSON.stringify({error: hits.length ? "ambiguous" : "missing", count: hits.length, names: names});
var s = app.project.sequences[hits[0]];
var o = {name: String(s.name), id: String(s.sequenceID), frame: 0, width: 0, height: 0, video: [], audio: []};
try { o.frame = Number(s.timebase); } catch (e) {}
try { var st = s.getSettings(); o.width = st.videoFrameWidth; o.height = st.videoFrameHeight;
      if (!(o.frame > 0)) o.frame = Math.round(st.videoFrameRate.seconds * 254016000000); } catch (e) {}
for (var k = 0; k < 2; k++) {
  var list = k ? s.audioTracks : s.videoTracks;
  for (var t = 0; t < list.numTracks; t++) {
    var m = false;
    try { m = !!list[t].isMuted(); } catch (e) {}
    (k ? o.audio : o.video).push({clips: list[t].clips.numItems, transitions: list[t].transitions.numItems, muted: m});
  }
}
return JSON.stringify(o);
})()"""

# One page of one track's clips or transitions. FNV-1a 32-bit in ES3: the multiply by 16777619 = 2^24 + 403 is split
# so no product passes 2^53, and every step is folded back to uint32 with >>> 0. Every NUMBER a property hands over
# (plain, or inside an array/object) that is NOT an integer is hashed at 5 significant digits: Premiere keeps values as
# float32, and a level copied by script read 2.81838311e-06 on one sequence and 2.81838288e-06 on its AD after a save
# and reopen (one ulp, 2026-09-23), which the full-precision hash called a difference. 5 digits is 0.001 dB on a level,
# 0.02 px on a normalised position; two values an ulp apart can still straddle a rounding edge, about 1 value in
# 100-1000. Integers stay verbatim: a colour param's getValue() is a 64-bit PACKED ARGB (18374897589125431000 for
# 255,192,192,192), which 5 digits would collapse to its alpha. Arrays and objects are walked by hand (qv) before
# JSON.stringify, because Premiere's ExtendScript stringify IGNORES a replacer function (live probe, 2026-09-23).
# Strings (a Lumetri blob) are hashed verbatim; key times are ticks, exact. UNTIL (sequence ticks, or null)
# scopes every keyed property to what plays before it (the module docstring); an item starting at or after UNTIL is
# not hashed at all, because the diff never reads it.
PAGE_ES = r"""(function(){
var ID = @ID@, KIND = @KIND@, T = @T@, SET = @SET@, UNTIL = @UNTIL@, N0 = @N0@, N1 = @N1@;
var s = null;
for (var i = 0; i < app.project.sequences.numSequences; i++)
  if (String(app.project.sequences[i].sequenceID) === ID) s = app.project.sequences[i];
if (!s) return "ERROR: sequence " + ID + " is no longer in the project";
var tr = (KIND === "A" ? s.audioTracks : s.videoTracks)[T];
var items = SET === "transitions" ? tr.transitions : tr.clips;
function fnv(h, str) {
  for (var j = 0; j < str.length; j++) {
    h = (h ^ str.charCodeAt(j)) >>> 0;
    h = (((h << 24) >>> 0) + h * 403) >>> 0;
  }
  return h;
}
function hex(h) { var x = h.toString(16); while (x.length < 8) x = "0" + x; return x; }
function qn(x) { return (isFinite(x) && x !== Math.floor(x)) ? Number(x.toPrecision(5)) : x; }
function qv(v) {
  if (typeof v === "number") return qn(v);
  if (v === null || typeof v !== "object") return v;
  var o, k;
  if (Object.prototype.toString.call(v) === "[object Array]") { o = []; for (k = 0; k < v.length; k++) o.push(qv(v[k])); return o; }
  o = {}; for (k in v) o[k] = qv(v[k]); return o;
}
function str(v) {
  if (v === null || v === undefined) return String(v);
  if (typeof v === "number") return String(qn(v));
  if (typeof v === "object") {
    try { return JSON.stringify(qv(v)); } catch (e) { return String(v); }
  }
  return String(v);
}
function hashAll(c, r) {
  var st = Number(r.start), ip = Number(r.inp), lim = null, at = null;
  if (UNTIL !== null) { lim = UNTIL - st + ip; at = (Math.min(Number(r.end), UNTIL) - st + ip) / 254016000000; }
  var all = 2166136261, n = 0;
  try { n = c.components.numItems; } catch (e) {}
  for (var k = 0; k < n; k++) {
    var cp = c.components[k], h = fnv(2166136261, String(cp.matchName));
    for (var p = 0; p < cp.properties.numItems; p++) {
      var pr = cp.properties[p], tv = false, keys = null, v = "?";
      h = fnv(h, "|" + pr.displayName + "=");
      try { tv = !!pr.isTimeVarying(); } catch (e) {}
      if (tv) {
        try { keys = pr.getKeys(); } catch (e) {}
        if (keys) for (var q = 0; q < keys.length; q++) {
          var kt = keys[q], kv = "?";
          var tk = (kt && kt.ticks !== undefined) ? String(kt.ticks) : String(Math.round(Number(kt) * 254016000000));
          if (lim !== null && Number(tk) > lim) continue;
          try { kv = str(pr.getValueAtKey(kt)); } catch (e) {}
          h = fnv(h, "@" + tk + ":" + kv);
        }
        if (at !== null) {
          try { v = str(pr.getValueAtTime(at)); } catch (e) {}
          h = fnv(h, "@T:" + v);
        }
      } else {
        try { v = str(pr.getValue()); } catch (e) {}
        h = fnv(h, v);
      }
    }
    r.comps.push(String(cp.matchName) + ":" + hex(h));
    all = fnv(all, r.comps[r.comps.length - 1] + ";");
  }
  r.hash = hex(all);
}
var out = [];
for (var i = N0; i < N1 && i < items.numItems; i++) {
  var c = items[i];
  var r = {i: i, name: "", match: "", media: "", start: String(c.start.ticks), end: String(c.end.ticks), inp: "0",
           disabled: false, speed: 1, reversed: false, hash: "", comps: []};
  try { r.name = String(c.name); } catch (e) {}
  try { r.match = String(c.matchName || ""); } catch (e) {}
  try { r.inp = String(c.inPoint.ticks); } catch (e) {}
  if (SET === "clips") {
    try { r.media = String(c.projectItem.getMediaPath() || ""); } catch (e) {}
    try { r.disabled = !!c.disabled; } catch (e) {}
    try { r.speed = c.getSpeed(); } catch (e) {}
    try { r.reversed = !!c.isSpeedReversed(); } catch (e) {}
  }
  if (UNTIL === null || Number(r.start) < UNTIL) hashAll(c, r);
  out.push(r);
}
return JSON.stringify(out);
})()"""


def es_str(v):
    return json.dumps(v)


def page_es(sid, kind, t, what, n0, n1, until=None):
    """One page of track `kind`+`t` ('clips' or 'transitions'); `until` in sequence ticks scopes the hash."""
    return (PAGE_ES.replace('@ID@', es_str(sid)).replace('@KIND@', es_str(kind)).replace('@T@', str(t))
            .replace('@SET@', es_str(what)).replace('@UNTIL@', 'null' if until is None else str(int(until)))
            .replace('@N0@', str(n0)).replace('@N1@', str(n1)))


def refuse(msg):
    print(msg, file=sys.stderr)
    raise SystemExit(2)


def guard(job):
    """The job guard for a BY-NAME reader: the project must be the job's and its active sequence one of the project's,
    but the active sequence is never read, so it is handed to the guard as the requested one. Without that, the
    sequence rule refuses `--diff '<job>' '<job> AD'` whenever the AD clone is active, the usual state right after an
    ad is built. One readback, handed to the guard."""
    raw = pes.es(GUARD_ES)
    require_job_project(lambda _script: raw, job, sequence=(json.loads(raw).get('active') or {}).get('name'))


def dump(name, until=None):
    """One sequence, found by NAME in app.project.sequences (the active one is never touched), every track paged.
    `until` (seconds) hashes every keyed property as it plays before it (--diff --until)."""
    head = json.loads(pes.es(HEAD_ES.replace('@NAME@', es_str(name))))
    if head.get('error'):
        refuse(f"sequence {name!r} is {head['error']}"
               + (f" ({head.get('count')} carry that name)" if head['error'] == 'ambiguous' else '')
               + f": nothing read.\n  sequences in this project: {', '.join(head.get('names') or []) or 'none'}")
    frame = int(float(head.get('frame') or 0))
    if frame <= 0:
        refuse(f"could not read the frame rate of {name!r}: nothing read.")
    cut = None if until is None else round(until * TPS)
    tracks = []
    for kind, heads in (('V', head['video']), ('A', head['audio'])):
        for t, th in enumerate(heads):
            def read(what, kind=kind, t=t):
                return pes.paged(lambda n0, n1: page_es(head['id'], kind, t, what, n0, n1, cut), size=PAGE,
                                 timeout=TIMEOUT) if th.get(what) else []
            clips, trans = [], []
            for r in read('clips'):
                # a sped clip reads inPoint in its SPED timebase (source / speed), so in and the derived out are
                # multiplied back by the speed, as bridge-lib.mjs srcOutOf does (lanes/premiere/lab-notes.md)
                s, e, sp = int(r['start']), int(r['end']), r['speed'] if (r['speed'] or 0) > 0 else 1
                i, o = round(int(r['inp']) * sp), round((int(r['inp']) + e - s) * sp)
                clips.append(dict(track=f'{kind}{t + 1}', i=r['i'], name=r['name'], start=s, end=e, inp=i,
                                  out=o, start_s=round(s / TPS, 6), end_s=round(e / TPS, 6),
                                  in_s=round(i / TPS, 6), out_s=round(o / TPS, 6), media=r['media'],
                                  disabled=r['disabled'], speed=r['speed'], reversed=r['reversed'],
                                  hash=r['hash'], comps=r['comps']))
            for r in read('transitions'):
                s, e = int(r['start']), int(r['end'])
                trans.append(dict(track=f'{kind}{t + 1}', i=r['i'], name=r['name'], match=r.get('match', ''),
                                  start=s, end=e, start_s=round(s / TPS, 6), end_s=round(e / TPS, 6),
                                  hash=r['hash'], comps=r['comps']))
            clips.sort(key=lambda c: c['start'])
            trans.sort(key=lambda c: c['start'])
            tracks.append(dict(track=f'{kind}{t + 1}', muted=th['muted'], clips=clips, transitions=trans))
    return dict(sequence=head['name'], id=head['id'], frame=frame, fps=round(TPS / frame, 6),
                width=head.get('width'), height=head.get('height'), until=until, tracks=tracks)


def base(p):
    return str(p or '').replace('\\', '/').rsplit('/', 1)[-1]


# what a diff compares per item kind: the times (printed in seconds), then the plain fields
FIELDS = {'clips': (('start', 'end', 'inp', 'out'), ('media', 'disabled', 'speed', 'reversed')),
          'transitions': (('start', 'end'), ('name', 'match'))}


def diff(a, b, until=None):
    """The lines that differ between two dumps; [] = identical (up to `until` seconds)."""
    lines, frame = [], a['frame']
    for k in ('frame', 'width', 'height'):
        if a.get(k) != b.get(k):
            lines.append(f"sequence {k}: {a.get(k)} != {b.get(k)}")
    cut = None if until is None else round(until * TPS)

    def scoped(items):
        out = {}
        for c in items:
            if cut is not None and c['start'] >= cut:
                continue
            c = dict(c)
            if cut is not None and c['end'] > cut:
                c['end'] = cut
                if 'out' in c:
                    c['out'] = c['inp'] + round((cut - c['start']) * (c['speed'] if (c.get('speed') or 0) > 0 else 1))
            out[round(c['start'] / frame)] = c
        return out

    empty = dict(muted=None, clips=[], transitions=[])
    ta, tb = {t['track']: t for t in a['tracks']}, {t['track']: t for t in b['tracks']}
    order = sorted(set(ta) | set(tb), key=lambda n: (n[0] != 'V', int(n[1:])))
    for name in order:
        xa, xb = ta.get(name, empty), tb.get(name, empty)
        if xa['muted'] is not None and xb['muted'] is not None and xa['muted'] != xb['muted']:
            lines.append(f"{name}: muted {xa['muted']} != {xb['muted']}")
        for kind, (times, plain) in FIELDS.items():
            ka, kb = scoped(xa.get(kind) or []), scoped(xb.get(kind) or [])
            for f in sorted(set(ka) | set(kb)):
                ca, cb = ka.get(f), kb.get(f)
                c = ca or cb
                what = c['name'] if kind == 'clips' else f"transition {c['name'] or c.get('match') or '?'!r}"
                at = f"{name} @{c['start'] / TPS:.3f}s {what}"
                if ca is None or cb is None:
                    lines.append(f"{at}: only in {(a if ca else b)['sequence']!r}"
                                 + (f" ({base(c['media']) or 'no media'})" if kind == 'clips' else ''))
                    continue
                d = [f"{field} {ca[field] / TPS:.5f} != {cb[field] / TPS:.5f}" for field in times if ca[field] != cb[field]]
                d += [f"{field} {ca.get(field)} != {cb.get(field)}" for field in plain if ca.get(field) != cb.get(field)]
                if ca['hash'] != cb['hash']:
                    pa, pb = ca['comps'], cb['comps']
                    named = [x.split(':')[0] for x, y in zip(pa, pb) if x != y] + [x.split(':')[0] for x in (pa[len(pb):] or pb[len(pa):])]
                    d.append(f"hash {ca['hash']} != {cb['hash']} ({', '.join(named) or 'components'})")
                if d:
                    lines.append(f"{at}: " + '; '.join(d))
    return lines


def main(argv=None):
    """cli(), with every failure that exits with its message (the job guard's refusals, a pes bridge failure such as
    the CEP return cap) turned into exit 2, so exit 1 only ever means the sequences differ."""
    try:
        return cli(argv)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            raise SystemExit(2)
        raise


def cli(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--sequence', help='dump this sequence (read by name, never activated)')
    g.add_argument('--diff', nargs=2, metavar=('SEQ_A', 'SEQ_B'), help='diff two sequences; exit 1 if they differ')
    ap.add_argument('--out', help='--sequence: write the dump as JSON here instead of printing a line per clip')
    ap.add_argument('--until', type=float, help='--diff: compare only what plays before this many seconds')
    a = ap.parse_args(argv)
    guard(Path(a.job).resolve())
    if a.sequence:
        d = dump(a.sequence)
        if a.out:
            with open(a.out, 'w', encoding='utf-8') as f:
                json.dump(d, f, indent=1)
            for t in d['tracks']:
                print(f"{t['track']}  {len(t['clips'])} clip(s)" + ('  MUTED' if t['muted'] else '')
                      + (f"  {t['clips'][0]['start_s']:.3f}-{max(c['end_s'] for c in t['clips']):.3f}s" if t['clips'] else '')
                      + (f"  {len(t['transitions'])} transition(s)" if t['transitions'] else ''))
            print(f"wrote {a.out}: {d['sequence']!r} at {d['fps']} fps")
        else:
            print(f"{d['sequence']!r} · {d['fps']} fps · {d['width']}x{d['height']}")
            for t in d['tracks']:
                for c in t['clips']:
                    print(f"{c['track']:4s} {c['start_s']:10.5f}-{c['end_s']:10.5f}  in {c['in_s']:10.5f} out {c['out_s']:10.5f}"
                          f"  {'OFF ' if c['disabled'] else ''}{c['hash']}  {base(c['media']) or c['name']}")
                for c in t['transitions']:
                    print(f"{c['track']:4s} {c['start_s']:10.5f}-{c['end_s']:10.5f}  transition {c['name'] or c['match']!r}  {c['hash']}")
        return 0
    da, db = dump(a.diff[0], a.until), dump(a.diff[1], a.until)
    lines = diff(da, db, a.until)
    scope = f" before {a.until:.3f}s" if a.until is not None else ''
    if lines:
        print("\n".join(lines))
        print(f"{len(lines)} difference(s) between {a.diff[0]!r} and {a.diff[1]!r}{scope}")
        return 1
    cut = None if a.until is None else round(a.until * TPS)
    n = {k: sum(1 for t in da['tracks'] for c in t[k] if cut is None or c['start'] < cut) for k in FIELDS}
    print(f"IDENTICAL{scope}: {a.diff[0]!r} and {a.diff[1]!r} ({n['clips']} clip(s) and {n['transitions']} transition(s) "
          f"compared, every component hashed{', keyframes as they play before the cut' if cut is not None else ''})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
