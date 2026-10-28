#!/usr/bin/env python3
"""audio-polish.py: pipeline step 3 on the Premiere lane, the house chain on every A1 clip.

  uv run lanes/premiere/audio-polish.py projects/<job> --apply             # gain from voice-gain.py, chain on every A1 clip, read back, save
  uv run lanes/premiere/audio-polish.py projects/<job> --apply --gain 15   # a named gain instead of the measured one
  uv run lanes/premiere/audio-polish.py projects/<job> --verify            # read every A1 clip's chain back, exit 1 on a miss
  uv run lanes/premiere/audio-polish.py projects/<job> --verify --gain 15  # hold every clip to THIS gain instead of the records
  uv run lanes/premiere/audio-polish.py projects/<job>/sections/<s> --apply --range FROM TO
        # multi-section job: the gain measured on that section's own cuts.json, applied only to the
        # A1 clips starting in [FROM, TO) timeline seconds (every section shoots at its own level), compared to the
        # microsecond, so a bound copied from a readback (19.9782916666667) is that clip's start: FROM takes it, TO leaves it out

Every successful --apply appends {gain, source ('named' | 'measured: …'), range or null, date} to
projects/<job>/premiere/audio-polish.json (a section's record goes to its parent job's file). A bare --verify
holds each A1 clip to the gain --apply last wrote over it: the latest record whose range holds the clip's
start (a whole-timeline record holds every clip), else the measured gain, as before there were records. So a
named gain and per-section gains verify together without retyping any of them, and every mismatch names the
record it was held to. `--verify --gain N` still means "every clip at N".

The WHAT: Amplify +GAIN (measured, workflows/voice-gain.py: the raw's kept speech to -17 LUFS)
into a Hard Limiter at -6 dBFS, one static pass, never loudnorm. The HOW, all read back:

  - every A1 clip gets Amplify + Hard Limiter as CLIP effects (QE addAudioEffect when missing,
    matched to the DOM clip by start time, so an existing chain is updated in place, not doubled)
  - Amplify Left/Right v = (dB + 96) / 144 · Hard Limiter Maximum Amplitude v = (dB + 100) / 100
    (both ranges verified in the UI 2026-07-30; a 0 dB check cannot tell the ranges apart)
  - a MONO clip exposes one Amplify "Gain" slider (same range) and plays under Premiere's -3 dB centre pan law
    on a stereo master, so it gets gain + 3 dB into a Hard Limiter at -3 dBFS: the master hears it exactly as the
    same audio in stereo, at the gain and under the -6 ceiling (voice-gain.py measures a mono raw as dual mono;
    live 2026-09-24, lanes/premiere/lab-notes.md § the mono clip)
  - a timeline rebuild (re-replay) drops clip effects: run --apply again after one

THE SECOND-VOICE LIFT (the Talking Head Explainer's README § Audio owns the rule; lanes/premiere/lab-notes.md the lock):

  uv run lanes/premiere/audio-polish.py projects/<job> --lift auto     # workflows/voice-gain.py --second-voice decides
  uv run lanes/premiere/audio-polish.py projects/<job> --lift 5        # a named lift, in dB (refused over the headroom cap)
  uv run lanes/premiere/audio-polish.py projects/<job> --lift 5 --force   # ... taken anyway, over the cap
  uv run lanes/premiere/audio-polish.py projects/<job> --lift 0        # drop the lift: the recorded keys come off
  uv run lanes/premiere/audio-polish.py projects/<job>/sections/<s> --lift auto [--range FROM TO]   # one section
  uv run lanes/premiere/audio-polish.py projects/<job> --verify        # the chain, and every clip's latest lift record
  uv run lanes/premiere/audio-polish.py projects/<job> --bounce        # A1 alone bounced twice (lift bypassed, then on; no AME)

  A second voice through a speaker (an AI on a call, a phone) sits 5-7 dB under the close mic after the chain. Its
  spans are transcript/voices.json ({"spans": [{"clip", "start", "end", "voice"}]}, RAW clock, the file captions.py
  reads; a span's `clip` is matched case-insensitively and a clip-less span is refused on a job of several raws);
  each is mapped onto the A1 clips that lay that raw material (split where it crosses a cut) and lifted with a
  SECOND Amplify appended AFTER the clip's Hard Limiter, keyed on its Left/Right (a mono clip's one Gain, at the same
  values, never + the pan law: that plays after it on host and phone alike): 0 dB outside the spans, the lift inside,
  50 ms ramps INSIDE each span so the host beside it is never lifted, the up-ramp starting 20 ms in (LIFT_LEAD):
  Premiere plays a ramp from 20 ms before its first key to 10 ms before its second (live 2026-09-24), which lifted
  the host up to 0.22 x the lift in the ~19 ms before a ramp keyed on the span's edge; with the lead the lift starts
  on the span's edge and the down-ramp is over 10 ms before the span ends (a span that starts at a cut starts lifted).
  Never the clip's Volume > Level: Premiere runs the fixed Volume effect BEFORE the clip effects (read live
  2026-09-23: a +15 Level lift on a span peaking -19.05 bounced at exactly -6.00, the limiter's ceiling), so Level
  keys would push the phone into the limiter instead of riding on top of it. `auto` lifts ceil(gap - 1.5) dB when the
  measured gap is over 3 dB, capped where the spans' true peak reaches -1 dBTP (voice-gain.py measures both, at the
  gain audio-polish.json recorded over the covered clips, and reads the peak even on a reply too short for a gap); a
  named lift over that cap, or one whose headroom cannot be measured, is refused without --force.
  The write is bracketed: job_guard (the active project is the job's), a save and a dated .prproj copy in
  premiere/archive/ (the rollback), every audio clip's position and every A1 chain value snapshotted before and read
  IDENTICAL after, the keys read back, and only then saved. A lift Amplify whose keys this tool did not record is the
  creator's: named and skipped. The lift's scope is the A1 clips THIS job's cuts.json lays (its raws, and the
  segments of them it keeps), never its raw/ folder: on the multi-section layout the parent's raw/ holds every
  section's raw. Every lift is recorded in premiere/audio-polish.json as {"kind": "lift", "scope": {those raws and
  segments, the --range}, the gap it measured, ...}: a section's lift never touches another section's clips, and a
  bare --verify holds each A1 clip to the LATEST lift record whose scope covers it. A timeline rebuild drops the lift
  Amplify: re-run --lift, then --verify, then --bounce. Proven live on a stereo and a MONO clip (2026-09-24, the lock
  in lanes/premiere/lab-notes.md), the ramps, the 20 ms lead and --bounce as it runs included. --bounce is the proof,
  the key readback is not: A1 alone through exportAsMediaDirect, twice over the same range when a lift is recorded
  (its lift Amplify bypassed inside the export script, which bounced the chain-only mix to 0 LSB live, then as it
  plays), and the lift is judged on its PLATEAUS (each span inside its lead and ramps): the lifted bounce's power over
  the bypassed one's reads the recorded lift within 0.25 dB on every one (a pure gain after the limiter: live, every
  plateau read +5.00 / +8.00), a sample either bounce clipped left out of both. The gaps before and after are
  Premiere's own, never voice-gain.py's simulated limiter (0.5-1.0 dB off Premiere's where the phone drives it); the
  lifted bounce's true peak over -1 dBTP fails, a forced lift included (read on the mono fold-down, so a stereo raw
  whose channels differ can hide its hotter channel under it); a forced lift, with no measured gap, is held within
  1.5 dB of the host either side, and no lift to a gap of 3 dB or less. It puts the creator's in/out marks, every
  track's mute and every Bypass switch back (read back live).
"""
import json, math, os, re, shutil, subprocess, sys, time
from array import array
from datetime import datetime
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path

VOICE_GAIN = Path(__file__).resolve().parent.parent.parent / 'workflows' / 'voice-gain.py'
LIMIT_DB = -6
LIFT_RAMP = 0.05   # s: the second-voice lift's ramps
LIFT_LEAD = 0.02   # s: the up-ramp starts this far INSIDE the span: Premiere starts a ramp 20 ms before its first key
                   # (live 2026-09-24), so the lift starts on the span's edge; no more than LIFT_MIN_S, so it stays
                   # inside every span it keys
LIFT_MIN_S = 0.02  # s: voice-gain.py's intersect() bar: a span overlapping a clip by no more is not second voice there
LIFT_CEILING_DBTP = -1.0   # voice-gain.py's: a named lift that lands the spans' true peak over this is refused
LIFT_STAGE = 'amplify-after-limiter'   # the lift's home: a second Amplify after the Hard Limiter (records carry it)
PAN_LAW_DB = 3   # a MONO clip on a stereo sequence plays at -3 dB per channel (Premiere's centre pan law): its Gain and
                 # its limiter's ceiling get this back, so the master hears it as the same audio in stereo


def sh(*cmd):
    # voice-gain.py writes UTF-8 (its stdio guard): read as Windows' cp1252, every ✗ it refuses with printed as mojibake
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode: sys.exit(f"{' '.join(cmd[:3])} failed:\n{r.stderr or r.stdout}")
    return r.stdout


from job_guard import require_job_project, job_root   # lanes/premiere/job_guard.py: the active project must be this job's
from pes import es, lsof_open, wav_preset    # lanes/premiere/pes.py: the bridge's one output contract


amp_v = lambda db: (db + 96) / 144
lim_v = lambda db: (db + 100) / 100


def load_records(path):
    """What every successful --apply wrote, oldest first. Read before Premiere is touched, so a broken file
    stops the run with nothing changed."""
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"{path} is not valid JSON ({e}): nothing touched. Fix or remove it and re-run.")


def record(path, gain, src, rng):
    """Append one successful --apply to the job's record file -> its 1-based number."""
    recs = load_records(path) + [dict(gain=gain, source=src, range=list(rng) if rng else None,
                                      date=datetime.now().isoformat(timespec='seconds'))]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(recs, indent=1) + '\n', encoding="utf-8")
    os.replace(tmp, path)
    return len(recs)


# ── the second-voice lift ─────────────────────────────────────────────────────────────────────────────────────
def load_voices(job):
    """transcript/voices.json -> [(clip basename or None, raw start, raw end)] (captions.py reads the same file)."""
    p = Path(job) / 'transcript' / 'voices.json'
    if not p.exists():
        sys.exit(f"✗ no {p}: write the second voice's RAW-clock spans there first (rough-cut § Transcribe)")
    data = json.loads(p.read_text(encoding="utf-8"))
    spans = data.get('spans') if isinstance(data, dict) else None
    if not isinstance(spans, list):
        sys.exit(f'✗ {p} has no `spans` list: {{"spans": [{{"clip", "start", "end", "voice"}}]}}')
    return [(os.path.basename(x['clip']) if x.get('clip') else None, float(x['start']), float(x['end'])) for x in spans]


def job_raws(job):
    """(the raws THIS job's cuts.json cuts from, lower-cased basenames; how many; its EDL segments as [(basename, raw
    start, raw end)]). The lift's scope is what the job's own EDL lays, never its raw/ folder: on the multi-section
    layout the parent job is the first section and its raw/ holds every section's raw (a section's raw/<file> is a
    symlink to it), so a raw/-wide scope let a parent --lift take a section's keys off. raw/ is read only when the job
    has no cuts.json."""
    cuts = Path(job) / 'transcript' / 'cuts.json'
    if cuts.exists():
        segs = [(os.path.basename(s_.get('clip') or '').lower(), float(s_['start']), float(s_['end']))
                for s_ in json.loads(cuts.read_text(encoding="utf-8")).get('segments') or []]
        segs = [s_ for s_ in segs if s_[0]]
        names = {n for n, _, _ in segs}
        return names, max(1, len(names)), segs
    names = {p.name.lower() for p in (Path(job) / 'raw').glob('*') if p.is_file() and not p.name.startswith('.')}
    return names, max(1, len(names)), []


def in_edl(c, names, segs):
    """Does A1 clip c lay this job's EDL? Its raw is one the job cuts from and, when the job's segments are known, its
    media range overlaps one of that raw's segments by over half the shorter of the two: two sections cutting the SAME
    raw lay different material of it, while a hand trim, split or extension keeps most of its segment. A clip read
    without an end (an old record's entry) is held by its in-point."""
    name = os.path.basename(c.get('path') or '').lower()
    if name not in names:
        return False
    if not segs:
        return True
    a = c['in']
    b = a + max(0.0, c.get('end', c['start']) - c['start'])
    for n, s_, e in segs:
        if n != name:
            continue
        if b - a < 1e-3:
            if s_ - 1e-3 <= a < e:
                return True
        elif min(b, e) - max(a, s_) > 0.5 * min(b - a, e - s_):
            return True
    return False


def check_spans(spans, names, n_raws, where='transcript/voices.json'):
    """The one rule every voices.json reader holds (voice-gain.py, captions.py, sfx-plan.py, this): a span's clip is a
    raw this job's cuts.json cuts from, matched case-insensitively, and a span with no clip is allowed only on a
    one-raw job."""
    for clip, a, b in spans:
        if clip is None and n_raws > 1:
            sys.exit(f"✗ {where}: a span with no `clip` ({a:.3f}-{b:.3f}s) on a job cut from {n_raws} raws: name its raw")
        if clip is not None and clip.lower() not in names:
            sys.exit(f"✗ {where}: a span names clip {clip!r}, which this job's cuts.json does not cut from "
                     f"({', '.join(sorted(names)) or 'none'})")


def edl_clips(cuts):
    """A1 as the EDL lays it: [{i, start, end, in, path}] (timeline seconds; `in` = the media in-point). Tests only:
    the live path reads A1 (read_a1)."""
    out, t = [], 0.0
    for k, s_ in enumerate(cuts['segments']):
        d = float(s_['end']) - float(s_['start'])
        out.append(dict(i=k, start=t, end=t + d, **{'in': float(s_['start'])}, path=s_.get('clip') or ''))
        t += d
    return out


def lift_keys(spans, clips, db, ramp=LIFT_RAMP, base=None):
    """The lift as keys per A1 clip -> [{i, start, in, keys: [(media seconds, dB)]}], only clips a span touches. A span
    is intersected with each clip's MEDIA range (so one crossing a cut is split, one key set per clip); overlapping or
    touching spans merge, and the gap between two spans stays at rest. The ramps sit INSIDE the span, so nothing
    outside it is ever lifted: the lift runs after the limiter, and host audio beside a span has no ceiling over it
    (live 2026-09-24: ramps outside the span took a -16 dBFS host to -1 at +15). Premiere plays the keys EARLY: a ramp
    plays from 20 ms before its first key to 10 ms before its second, its half-lift 10.3 ms early (live 2026-09-24, every
    edge on stereo and mono, whatever the limiter's look-ahead), so an up-ramp keyed on the span's edge lifted the host
    up to 0.22 x the lift in the ~19 ms before it: the up-ramp starts LIFT_LEAD inside, and the lift now starts on the
    span's edge (live: the host before it within 4 LSB of the chain-only bounce). Up: base at (start + LIFT_LEAD),
    lifted at (start + LIFT_LEAD + ramp); down: lifted at (end - ramp), base at end, left there: played early it is
    gone 10 ms before the span ends, so the host after a span is never lifted (live: within 10 LSB), and the reply's
    last ~10 ms plays unlifted. A span shorter than its lead and
    ramps ramps over its own halves, and a span that reaches the clip's edge (a cut) starts or ends there lifted (the
    clip's audio begins or ends there, so an early key has no host to lift). An overlap of LIFT_MIN_S or less stays
    at rest: voice-gain.py neither measures it nor reads its peak into the cap, so lifting it (a host tail pad running
    into a quick reply) would ramp to the full lift at the cut with no ceiling over it. `base` = {clip i: its level in
    dB}, 0 dB by default (the lift Amplify's own rest)."""
    out = []
    for c in clips:
        c_in = c['in']
        c_out = c_in + (c['end'] - c['start'])
        name = os.path.basename(c.get('path') or '').lower()
        ivs = sorted((max(a, c_in), min(b, c_out)) for clip, a, b in spans
                     if (clip is None or clip.lower() == name) and min(b, c_out) - max(a, c_in) > LIFT_MIN_S)
        merged = []
        for a, b in ivs:
            if merged and a <= merged[-1][1] + 1e-6:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))
        if not merged:
            continue
        b0 = (base or {}).get(c['i'], 0.0)
        keys = []
        for a, b in merged:
            up, down = a > c_in + 1e-6, b < c_out - 1e-6
            lead = LIFT_LEAD if up else 0.0
            r = min(ramp, (b - a - lead) / ((up + down) or 1))
            for t, v in (([(a + lead, b0), (a + lead + r, b0 + db)] if up else [(a, b0 + db)])
                         + ([(b - r, b0 + db), (b, b0)] if down else [(b, b0 + db)])):
                t = round(t, 6)
                if not (keys and abs(keys[-1][0] - t) < 1e-6):   # a short span's two ramps meet in one key
                    keys.append((t, v))
        out.append(dict(i=c['i'], start=c['start'], keys=keys, **{'in': c_in}))
    return out


def auto_lift(sv):
    """voice-gain.py --second-voice's `second_voice` block -> (lift dB, source). An UNMEASURABLE gap stops the run:
    a sliver of phone reads -70 LUFS and used to recommend about +51 dB."""
    if sv.get('unmeasurable'):
        sys.exit(f"✗ --lift auto: {sv.get('warn')}: nothing written. Widen transcript/voices.json or name a lift (--lift N).")
    if sv.get('warn'):
        return 0, f"auto: {sv['warn']}"
    cap = (f" · capped from {sv['want_db']:+d} to the headroom ({sv.get('second_true_peak')} dBTP peak)"
           if sv.get('capped') else '')
    return int(sv['lift_db']), (f"auto: gap {sv['gap_db']} dB after the chain at {sv.get('gain_db', 0):+d} dB "
                                f"(host {sv['host_lufs']} / second {sv['second_lufs']} LUFS){cap}")


JS_HELPERS = r"""
  function comp(c, name){ for (var k = 0; k < c.components.numItems; k++) if (c.components[k].displayName === name) return c.components[k]; return null; }
  function prop(cm, name){ for (var q = 0; q < cm.properties.numItems; q++) if (cm.properties[q].displayName === name) return cm.properties[q]; return null; }
  function r6(x){ return Math.round(x * 1e6) / 1e6; }
  function level(c){ var v = comp(c, "Volume"); return v ? prop(v, "Level") : null; }
  // the chain by POSITION: the gain Amplify is the one BEFORE the Hard Limiter, the lift Amplify the one AFTER it
  function chainIdx(c){ var lim = -1, amp = -1, lift = -1, pre = 0;
    for (var k = 0; k < c.components.numItems; k++) { var n = c.components[k].displayName;
      if (n === "Hard Limiter") { if (lim < 0) lim = k; }
      else if (n === "Amplify") { if (lim < 0) { pre++; if (amp < 0) amp = k; } else if (lift < 0) lift = k; } }
    return {amp: amp, lim: lim, lift: lift, pre: pre}; }
  function ampProps(cm){ var L = prop(cm, "Left"), R = prop(cm, "Right"), G = prop(cm, "Gain");
    return (L && R) ? [L, R] : (G ? [G] : []); }"""


def read_a1():
    """Every A1 clip with its chain and its lift Amplify: [{i, start, end, in, path, mono, order, chain: [gain v...,
    limiter v], lift: null | {tv, v, keys: [[media t, v]] per slider}}]."""
    r = es(r"""(function(){
  var seq = app.project.activeSequence; if (!seq) return "ERROR: no active sequence";
  %s
  var tr = seq.audioTracks[0], out = [];
  for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i], ix = chainIdx(c);
    var e = {i: i, start: r6(c.start.seconds), end: r6(c.end.seconds), "in": r6(c.inPoint.seconds),
             path: c.projectItem ? c.projectItem.getMediaPath() : "", order: (ix.amp >= 0 && ix.lim > ix.amp && ix.pre === 1),
             mono: false, chain: [], lift: null};
    if (ix.amp >= 0) { var gp = ampProps(c.components[ix.amp]); e.mono = gp.length === 1;
      for (var g = 0; g < gp.length; g++) e.chain.push(r6(gp[g].getValue())); }
    if (ix.lim >= 0) { var M = prop(c.components[ix.lim], "Maximum Amplitude"); e.chain.push(M ? r6(M.getValue()) : null); }
    if (ix.lift >= 0) { var ps = ampProps(c.components[ix.lift]), lf = {tv: false, v: [], keys: []};
      for (var p = 0; p < ps.length; p++) { var P = ps[p], ks = [], tv = P.isTimeVarying();
        lf.tv = lf.tv || tv; lf.v.push(r6(P.getValue()));
        if (tv) { var kk = P.getKeys(); for (var z = 0; z < kk.length; z++) ks.push([r6(kk[z].seconds), r6(P.getValueAtKey(kk[z]))]); }
        lf.keys.push(ks); }
      e.lift = lf; }
    out.push(e); }
  return JSON.stringify(out); })()""" % JS_HELPERS, timeout=120000)
    if str(r).startswith('ERROR'): sys.exit(r)
    return json.loads(r)


def audio_snapshot():
    """Every audio clip's place (track, start, end, in-point in ticks, media), and every OTHER track's static Level:
    the lift writes A1 lift-Amplify keys and nothing else, and this (with read_a1's chain values) proves it."""
    r = es(r"""(function(){
  var seq = app.project.activeSequence; if (!seq) return "ERROR: no active sequence";
  %s
  var out = [seq.audioTracks.numTracks];
  for (var t = 0; t < seq.audioTracks.numTracks; t++) { var tr = seq.audioTracks[t];
    for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i], L = level(c);
      out.push([t, String(c.start.ticks), String(c.end.ticks), String(c.inPoint.ticks),
                c.projectItem ? c.projectItem.getMediaPath() : "", L ? r6(L.getValue()) : null,
                L && L.isTimeVarying() ? L.getKeys().length : 0]); } }
  return JSON.stringify(out); })()""" % JS_HELPERS, timeout=120000)
    if str(r).startswith('ERROR'): sys.exit(r)
    return json.loads(r)


def write_lift(rows):
    """rows = [{i, st, v0, keys: [[media t, v]]}]: each A1 clip's lift Amplify (appended after the Hard Limiter when
    missing) keyed on every slider, or set static to v0 (0 dB) when no keys. Keys are written through setValueAtKey,
    never a static setValue first (the time-varying trap: lab-notes § A time-varying music Level)."""
    r = es(r"""(function(){
  var seq = app.project.activeSequence; if (!seq) return "ERROR: no active sequence";
  %s
  app.enableQE(); var qtr = qe.project.getActiveSequence().getAudioTrackAt(0);
  function qItemAt(t){ for (var q = 0; q < qtr.numItems; q++) { var it = qtr.getItemAt(q);
    if (it.type === "Clip" && Math.abs(it.start.secs - t) < 0.002) return it; } return null; }
  var ROWS = %s, tr = seq.audioTracks[0], done = [];
  for (var n = 0; n < ROWS.length; n++) { var w = ROWS[n], c = tr.clips[w.i];
    if (!c || Math.abs(c.start.seconds - w.st) > 0.002) return "ERROR: A1 clip " + w.i + " is not where it was read";
    var ix = chainIdx(c);
    if (ix.amp < 0 || ix.lim < ix.amp || ix.pre !== 1) return "ERROR: A1 clip " + w.i + " has no Amplify -> Hard Limiter chain: run --apply first";
    if (ix.lift < 0) { if (!w.keys.length) { done.push(w.i); continue; }
      var qi = qItemAt(c.start.seconds); if (!qi) return "ERROR: no QE item for A1 clip " + w.i;
      qi.addAudioEffect(qe.project.getAudioEffectByName("Amplify")); ix = chainIdx(c);
      if (ix.lift < 0) return "ERROR: the lift Amplify did not land AFTER the Hard Limiter on A1 clip " + w.i; }
    var ps = ampProps(c.components[ix.lift]); if (!ps.length) return "ERROR: no Left/Right or Gain on A1 clip " + w.i + "'s lift Amplify";
    for (var p = 0; p < ps.length; p++) { var P = ps[p];
      if (P.isTimeVarying()) P.setTimeVarying(false);
      if (!w.keys.length) { P.setValue(w.v0, true); continue; }
      P.setTimeVarying(true);
      for (var k = 0; k < w.keys.length; k++) { P.addKey(w.keys[k][0]); P.setValueAtKey(w.keys[k][0], w.keys[k][1], true); } }
    done.push(w.i); }
  return JSON.stringify(done); })()""" % (JS_HELPERS, json.dumps(rows)), timeout=120000)
    if str(r).startswith('ERROR'): sys.exit(r)
    return json.loads(r)


def same_keys(a, b):
    return len(a) == len(b) and all(abs(x[0] - y[0]) < 1e-3 and abs(x[1] - y[1]) < 1e-4 for x, y in zip(a, b))


V0 = amp_v(0)   # the lift Amplify at rest


def lift_state(c):
    """A1 clip c's lift Amplify -> 'none' (absent or static at 0 dB), ('keys', keys) when every slider carries the
    same keys, or 'other' (a static level off 0 dB, or sliders that disagree)."""
    L = c.get('lift')
    if not L:
        return 'none'
    if not L['tv']:
        return 'none' if all(abs(v - V0) < 1e-4 for v in L['v']) else 'other'
    ks = L['keys']
    return ('keys', ks[0]) if ks and all(same_keys(k, ks[0]) for k in ks) else 'other'


def lift_records(recs):
    """[(record number from 1, record)] of every lift record this version wrote (a Level-key record from before the
    move after the limiter is skipped: it keyed a different effect)."""
    return [(k + 1, r) for k, r in enumerate(recs) if r.get('kind') == 'lift' and r.get('stage') == LIFT_STAGE]


def listed(rec, c):
    """The entry lift record `rec` keeps for A1 clip c (matched by its start and in-point), or None."""
    for x in rec.get('clips') or []:
        if abs(x['start'] - c['start']) < 1e-3 and abs(x['in'] - c['in']) < 1e-3:
            return x
    return None


def covers(rec, c):
    """Does lift record `rec`'s scope (the raws and segments that job's EDL lays, its --range) hold A1 clip c?"""
    sc = rec.get('scope') or {}
    names = {n.lower() for n in sc.get('clips') or []}
    rng = sc.get('range')
    return (in_edl(c, names, [tuple(s_) for s_ in sc.get('segs') or []])
            and (rng is None or grid(rng[0]) <= grid(c['start']) < grid(rng[1])))


def holding(lifts, c):
    """The latest lift record whose scope holds A1 clip c -> (number, record), or (None, None)."""
    for n, r in reversed(lifts):
        if covers(r, c) or listed(r, c):
            return n, r
    return None, None


def verify_lifts(recs, a1):
    """--verify's lift half: each A1 clip held to the latest lift record covering it -> (bad lines, {record n: clips
    whose keys read back})."""
    lifts = lift_records(recs)
    bad, ok = [], {}
    for n, r in lifts:                                 # a clip a record keyed that no A1 clip matches any more
        for x in r.get('clips') or []:
            if any(abs(x['start'] - c['start']) < 1e-3 and abs(x['in'] - c['in']) < 1e-3 for c in a1):
                continue
            later = [m for m, q in lifts if m > n and covers(q, dict(path=x.get('path') or '', start=x['start'],
                                                                     end=x.get('end', x['start']), **{'in': x['in']}))]
            if not later:
                bad.append(f"lift #{n}: no A1 clip at {x['start']:.3f}s (in {x['in']:.3f}) any more: the cut changed, re-run --lift")
    for c in a1:
        n, r = holding(lifts, c)
        if r is None:
            continue
        x, st = listed(r, c), lift_state(c)
        if x and x['keys']:
            if st != 'none' and st != 'other' and same_keys(st[1], x['keys']):
                ok[n] = ok.get(n, 0) + 1
            else:
                got = 'no lift' if st == 'none' else ('a lift the record did not write' if st == 'other' else f"{len(st[1])} key(s)")
                bad.append(f"lift #{n}: A1 clip {c['i']} at {c['start']:.3f}s reads {got}, the record {len(x['keys'])} key(s): "
                           "a rebuild drops the lift, re-run --lift")
        elif st != 'none':
            bad.append(f"lift #{n}: A1 clip {c['i']} at {c['start']:.3f}s carries a lift the record ({r['lift_db']:+d} dB) "
                       "does not: a hand edit, or a --lift that did not finish")
    return bad, ok


def recorded_gain(recs, clips, fallback=None):
    """The one gain audio-polish.json records over `clips` (the chain voice-gain.py must simulate), None when no record
    holds any of them, and a stop when they carry different gains (one --lift per section: --range)."""
    gains = set()
    for c in clips:
        k = held_by(recs, grid(c['start']))
        if k is not None:
            gains.add(recs[k]['gain'])
    if len(gains) > 1:
        sys.exit(f"✗ the clips this lift covers carry different recorded gains ({', '.join(f'{g:+d}' for g in sorted(gains))}): "
                 "run --lift per section (from the section's folder, with its --range)")
    return next(iter(gains)) if gains else fallback


def second_voice(job, gain):
    """voice-gain.py --second-voice --json at the recorded gain -> its `second_voice` block."""
    cmd = ['uv', 'run', str(VOICE_GAIN), str(job), '--second-voice', '--json'] + (['--gain', str(gain)] if gain is not None else [])
    return json.loads(sh(*cmd)).get('second_voice') or {}


def lift(job, arg, recs, log, rng=None, force=False):
    """--lift auto|<dB>: scope, plan, classify, bracket, write, read back, save, record."""
    names, n_raws, segs = job_raws(job)
    if not names:
        sys.exit(f"✗ {job} has no cuts.json clip names and no raw/ files: the lift cannot tell its clips from another section's")
    spans = load_voices(job)
    check_spans(spans, names, n_raws)
    prproj = require_job_project(es, job)
    a1 = read_a1()
    lo, hi = (grid(rng[0]), grid(rng[1])) if rng else (-1, 1e9)
    scope = [c for c in a1 if in_edl(c, names, segs) and lo <= grid(c['start']) < hi]
    if not scope:
        sys.exit(f"✗ no A1 clip lays this job's EDL ({', '.join(sorted(names))})" + (f" in --range {rng[0]!r}–{rng[1]!r}s" if rng else '')
                 + ": nothing to lift, nothing recorded")
    sv = {}
    if arg == 'auto':
        sv = second_voice(job, recorded_gain(recs, scope))
        db, src = auto_lift(sv)
    else:
        db, src = int(arg), 'named'
        if db > 0 and force:
            print(f"⚠ --force: +{db} dB is taken without the headroom check (the creator's named lift)")
            src += ' (forced, headroom not checked)'
        elif db > 0:
            sv = second_voice(job, recorded_gain(recs, scope))
            cap = sv.get('cap_db')
            if cap is None:   # nothing would hold the lifted spans under the ceiling: after the limiter, +6 on a -6 peak clips
                sys.exit(f"✗ --lift {db:+d}: the headroom could not be measured ({sv.get('warn') or 'no true peak read on the spans'}), "
                         f"so nothing holds the lifted spans under the {LIFT_CEILING_DBTP:g} dBTP ceiling. Nothing written: "
                         "pass --force to take it anyway (the creator's call).")
            elif db > cap:
                sys.exit(f"✗ --lift {db:+d}: the second voice's spans peak {sv.get('second_true_peak')} dBTP after the chain, so the "
                         f"lift lands them at {sv['second_true_peak'] + db:+.1f} dBTP, over the {LIFT_CEILING_DBTP:g} dBTP ceiling (cap {cap:+d}). "
                         "Nothing written: lift less, or pass --force to take it anyway.")
    bad = [c for c in scope if not c['order']]
    if bad:
        sys.exit('✗ ' + '; '.join(f"A1 clip {c['i']} at {c['start']:.3f}s has no Amplify -> Hard Limiter chain" for c in bad)
                 + ': run --apply first (the lift goes AFTER the limiter)')
    lifts = lift_records(recs)
    plan = {p_['i']: p_ for p_ in lift_keys(spans, scope, db)} if db else {}
    if db and not plan:
        sys.exit(f"✗ --lift {db:+d}: the voices.json spans touch no A1 clip of this job (kept A1 media: "
                 f"{', '.join(sorted({os.path.basename(c['path']) for c in scope}))}): nothing written, nothing recorded")
    rows, hand, match, recorded = [], [], 0, []
    for c in scope:
        p_ = plan.get(c['i'])
        _, rec = holding(lifts, c)
        mine = listed(rec, c) if rec else None
        # the same values on a MONO clip's one Gain slider as on Left/Right, never + PAN_LAW_DB: the centre pan law
        # plays after every clip effect, on the host and the phone alike, so it leaves the gap alone; the gain Amplify
        # and the limiter's ceiling already carry the +3, so the headroom is the master's, and voice-gain.py reads a
        # mono raw as its stereo twin
        want = [[t, round(amp_v(d), 6)] for t, d in p_['keys']] if p_ else []
        st = lift_state(c)
        if not p_ and st == 'none':
            continue                                      # nothing planned, nothing of ours to take off
        ours = st == 'none' or (st != 'other' and ((mine and same_keys(st[1], mine['keys'])) or same_keys(st[1], want)))
        if not ours:
            hand.append(c); continue                      # a lift Amplify this tool never keyed: the creator's
        if want and st not in ('none', 'other') and same_keys(st[1], want):
            match += 1
        else:
            rows.append(dict(i=c['i'], st=c['start'], v0=round(V0, 6), keys=want))
        if want:
            recorded.append(dict(i=c['i'], start=c['start'], end=c['end'], path=os.path.basename(c['path']), keys=want,
                                 **{'in': c['in']}))
    for c in hand:
        print(f"⚠ A1 clip {c['i']} at {c['start']:.3f}s: its lift Amplify carries a level this tool did not write "
              "(the creator's): skipped. Clear it by hand, then re-run --lift.")
    print(f"lift {db:+d} dB ({src}) · scope {len(scope)} A1 clip(s) of {', '.join(sorted(names))} · {len(plan)} touched by the "
          f"second voice · {match} already keyed · {len(rows)} to write · {len(hand)} hand-keyed, skipped")
    if rows:
        save_es()
        arch = job_root(job) / 'premiere' / 'archive'
        arch.mkdir(parents=True, exist_ok=True)
        bak = arch / f"{Path(prproj).stem}.pre-lift-{time.strftime('%Y%m%d-%H%M%S')}.prproj"
        shutil.copy2(prproj, bak)
        print(f'  backup {bak.relative_to(job_root(job))}')
        snap0, chain0 = audio_snapshot(), {c['i']: c['chain'] for c in a1}
        write_lift(rows)
        after = read_a1()
        by_i = {c['i']: c for c in after}
        wrong = []
        for w in rows:
            st = lift_state(by_i.get(w['i'], {}))
            ok = (st not in ('none', 'other') and same_keys(st[1], w['keys'])) if w['keys'] else st == 'none'
            if not ok:
                wrong.append(f"A1 clip {w['i']}: wrote {len(w['keys'])} key(s), reads "
                             + ('none' if st == 'none' else 'a mismatch' if st == 'other' else f"{len(st[1])}"))
        if {c['i']: c['chain'] for c in after} != chain0:
            wrong.append('an A1 chain value (the gain Amplify or the limiter) changed')
        if wrong or audio_snapshot() != snap0:
            for x in wrong: print('  ✗ ' + x)
            sys.exit('✗ the lift did not read back (or another audio clip changed during the run). The project was NOT '
                     f'saved: close it without saving to undo, or restore {bak.name}.')
        save_es()
        print(f'  ✓ {len(rows)} clip(s) keyed and read back · every other audio clip and every A1 chain IDENTICAL · saved')
    # what --bounce judges against: the gap before the lift (when measured) and, on auto, whether the headroom capped
    # it. A named lift is the creator's number and never capped (over the cap it is refused): auto's own want_db and
    # capped, measured here only for the headroom check, would label it "capped by the headroom" on the bounce
    measured = {k: sv[k] for k in (('gap_db', 'want_db', 'capped') if arg == 'auto' else ('gap_db',))
                if sv.get(k) is not None}
    recs = load_records(log) + [dict(kind='lift', stage=LIFT_STAGE, lift_db=db, source=src, ramp=LIFT_RAMP, lead=LIFT_LEAD, **measured,
                                     scope=dict(clips=sorted(names), segs=[list(s_) for s_ in segs],
                                                range=list(rng) if rng else None, job=str(job)),
                                     clips=recorded, date=datetime.now().isoformat(timespec='seconds'))]
    log.parent.mkdir(parents=True, exist_ok=True)
    tmp = log.with_name(log.name + '.tmp')
    tmp.write_text(json.dumps(recs, indent=1) + '\n', encoding="utf-8")
    os.replace(tmp, log)
    print(f"recorded as {log.name} #{len(recs)}" + ('' if db else ' (no lift)'))
    if hand: sys.exit(1)


def lifted_ranges(spans, clips):
    """Timeline ranges of the second voice on `clips` (A1 as read), and the rest of those clips (the host). An overlap
    lift_keys leaves at rest (LIFT_MIN_S or less) is host here."""
    second, host = [], []
    for c in clips:
        name = os.path.basename(c.get('path') or '').lower()
        c_in, c_out = c['in'], c['in'] + c['end'] - c['start']
        iv = sorted((max(a, c_in), min(b, c_out)) for clip, a, b in spans
                    if (clip is None or clip.lower() == name) and min(b, c_out) - max(a, c_in) > LIFT_MIN_S)
        t = c_in
        for a, b in iv:
            if a > t: host.append((c['start'] + t - c_in, c['start'] + a - c_in))
            second.append((c['start'] + a - c_in, c['start'] + b - c_in))
            t = max(t, b)
        if c_out > t: host.append((c['start'] + t - c_in, c['end']))
    return second, host


def plateaus(rec, clips):
    """Timeline ranges where lift record `rec`'s own keys hold its full lift on `clips` (A1 as read): each span inside
    its lead and ramps, the end a down-ramp follows pulled in LIFT_LEAD more (Premiere starts a ramp 20 ms before its
    first key, live 2026-09-24). --bounce judges the lift there and nowhere else: over a whole span its lead and ramps
    dilute it (live 2026-09-24: +8 read +7.3 over whole replies of 0.4-1.3 s)."""
    full = amp_v(rec.get('lift_db') or 0)
    out = []
    for c in clips:
        ks = (listed(rec, c) or {}).get('keys') or []
        for k in range(len(ks) - 1):
            (ta, va), (tb, vb) = ks[k], ks[k + 1]
            if abs(va - full) < 1e-4 and abs(vb - full) < 1e-4:
                tb -= LIFT_LEAD if k + 2 < len(ks) else 0.0
                a, b = max(c['start'], c['start'] + ta - c['in']), min(c['end'], c['start'] + tb - c['in'])
                if b - a >= PLATEAU_MIN_S:
                    out.append((round(a, 6), round(b, 6)))
    return out


def pcm(wav, sr=48000):
    """A WAV's samples, decoded to mono float (audio only)."""
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(wav), '-vn', '-sn', '-dn', '-ac', '1', '-ar', str(sr),
                        '-f', 'f32le', '-'], capture_output=True)
    if p.returncode:
        sys.exit(f"✗ ffmpeg could not read the bounce {wav}: {p.stderr.decode(errors='replace')[-300:]}")
    x = array('f')
    x.frombytes(p.stdout[:len(p.stdout) // 4 * 4])
    if sys.byteorder == 'big':
        x.byteswap()
    return x


def plateau_lift(off, on, ranges, sr=48000):
    """The lift that played on each range (bounce seconds): the lifted bounce's power over the bypassed one's, in dB,
    off the samples (ebur128 over a joined selection read +7.4 on samples that are exactly +8.000, live 2026-09-24)
    -> [dB, or None where the bypassed bounce is silent there]. A sample either bounce CLIPPED (at full scale: the WAV
    stops at 0 dBFS, Premiere's mix does not) is left out of both, so a lift that plays past the ceiling reads what
    played and the ceiling check names the clip (live 2026-09-24: a forced +14 read +12.9 to +13.1 on its clipped
    plateaus, and the verdict blamed a dropped lift)."""
    x, y = pcm(off, sr), pcm(on, sr)
    out = []
    for a, b in ranges:
        i0, i1 = max(0, round(a * sr)), max(0, round(b * sr))
        kept = [(u, v) for u, v in zip(x[i0:i1], y[i0:i1]) if abs(u) < CLIP_FS and abs(v) < CLIP_FS]
        po = math.fsum(u * u for u, _ in kept) / len(kept) if kept else 0.0
        pn = math.fsum(v * v for _, v in kept) / len(kept) if kept else 0.0
        out.append(None if po < SILENT_MS else (round(10 * math.log10(pn / po), 2) if pn > 0 else -99.0))
    return out


def export_a1(t0, t1, wav, bypass=()):
    """A1 ALONE over [t0, t1] of the active sequence to `wav` through exportAsMediaDirect (never AME): every other audio
    track muted, and the creator's own in/out marks read first and put back after (export.py's rule: his marks are his;
    unset reads -400000, which put back clears them again). `bypass` = the A1 clips whose lift Amplify plays BYPASSED
    for this export (its Bypass switch, property 0; bypassed, it renders the chain-only mix to the LSB, live 2026-09-24),
    each switch put back as it was and read back after the export."""
    wav.parent.mkdir(parents=True, exist_ok=True)
    if wav.exists(): wav.unlink()
    preset = wav_preset()
    try:
        r = es(r"""(function(){var s=app.project.activeSequence; if(!s) return "ERROR: no active sequence"; var m=[];
%s
var BYP=%s, was=[];
function byp(i){ var c=s.audioTracks[0].clips[i], ix=chainIdx(c); return ix.lift<0 ? null : c.components[ix.lift].properties[0]; }
for(var b=0;b<BYP.length;b++){ if(!s.audioTracks[0].clips[BYP[b]]) return "ERROR: no A1 clip "+BYP[b]; var P=byp(BYP[b]); if(!P) continue;
  if(typeof P.getValue()!=="boolean") return "ERROR: A1 clip "+BYP[b]+"'s lift Amplify has no Bypass switch at property 0"; was.push([BYP[b], P.getValue()]); }
var mk=[Number(s.getInPoint()), Number(s.getOutPoint())];
for(var t=1;t<s.audioTracks.numTracks;t++){m.push(s.audioTracks[t].isMuted());s.audioTracks[t].setMute(1);}
for(var w=0;w<was.length;w++) byp(was[w][0]).setValue(true, true);
var r; try { s.setInPoint(%r); s.setOutPoint(%r); r=String(s.exportAsMediaDirect(%s, %s, 1)); } catch(e) { r="ERROR: the export threw: "+e; }
var stuck=[]; for(var w=0;w<was.length;w++){ var Q=byp(was[w][0]); Q.setValue(was[w][1], true); if(Q.getValue()!==was[w][1]) stuck.push(was[w][0]); }
for(var t=1;t<s.audioTracks.numTracks;t++) s.audioTracks[t].setMute(m[t-1]?1:0);
s.setInPoint(-400000); s.setOutPoint(-400000); s.setInPoint(mk[0]); s.setOutPoint(mk[1]);
return stuck.length ? "ERROR: the lift Amplify's Bypass did not read back as it was on A1 clip(s) "+stuck.join(", ")+": set it by hand" : r;})()""" % (
                   JS_HELPERS, json.dumps(list(bypass)), t0, t1, json.dumps(str(wav)), json.dumps(preset)),
               timeout=1800000)
    except SystemExit:
        print('⚠ the bounce did not come back: every audio track except A1 may still be MUTED and the sequence in/out '
              'still set to the bounce range (the creator\'s own marks, if any, are lost)'
              + (f", and the lift Amplify on A1 clip(s) {', '.join(map(str, bypass))} may still be BYPASSED" if bypass else '')
              + '. Fix it in Premiere before anything else is exported.', file=sys.stderr)
        raise
    if str(r).startswith('ERROR'): sys.exit(r)
    for _ in range(240):
        if wav.exists() and not lsof_open(wav) and wav.stat().st_size > 1000:
            break
        time.sleep(2)
    else:
        sys.exit(f'✗ the bounce never finished ({wav})')


def bounce(job, recs, rng=None, measure=None, wav=None):
    """--bounce: A1 ALONE over this job's clips through exportAsMediaDirect (no AME). With a lift recorded, twice over the
    same range: the lift Amplify bypassed, then as it plays; the lift is judged on its plateaus (the lifted bounce's
    power over the bypassed one's), and the gap before and after it and the lifted bounce's true peak are Premiere's own,
    never voice-gain.py's simulated limiter. The proof --lift's key readback cannot give."""
    names, n_raws, segs = job_raws(job)
    spans = load_voices(job)
    check_spans(spans, names, n_raws)
    require_job_project(es, job)
    a1 = read_a1()
    lo, hi = (grid(rng[0]), grid(rng[1])) if rng else (-1, 1e9)
    scope = [c for c in a1 if in_edl(c, names, segs) and lo <= grid(c['start']) < hi]
    if not scope:
        sys.exit("✗ no A1 clip lays this job's EDL: nothing to bounce")
    second, host = lifted_ranges(spans, scope)
    if not second:
        sys.exit('✗ the voices.json spans touch no A1 clip of this job: nothing to measure')
    touched = [c for c in scope if lifted_ranges(spans, [c])[0]]
    held = {n: r for n, r in (holding(lift_records(recs), c) for c in touched) if r is not None}
    if len(held) > 1:
        sys.exit(f"✗ the clips this bounce covers are held by different lift records ({', '.join(f'#{n}' for n in sorted(held))}): "
                 "bounce each section on its own (from its folder, with its --range)")
    t0, t1 = min(c['start'] for c in scope), max(c['end'] for c in scope)
    wav = Path(wav or (job_root(job) / 'review' / 'lift-bounce.wav')).resolve()   # Premiere resolves a relative path against its own cwd
    off = wav.with_name(wav.stem + '.bypassed' + wav.suffix)
    if off.exists(): off.unlink()
    n, rec = next(iter(held.items()), (None, None))
    db = (rec or {}).get('lift_db') or 0
    if db:   # the lift's own "before": the same range with the lift Amplify of every clip it touches bypassed
        export_a1(t0, t1, off, bypass=[c['i'] for c in touched])
    export_a1(t0, t1, wav)
    measure = measure or bounce_lufs
    rel = lambda rr: [(a - t0, b - t0) for a, b in rr]
    (h, _), (s2, _) = measure(wav, rel(host)), measure(wav, rel(second))
    _, pk = measure(wav, [(0.0, t1 - t0 + 1.0)])   # one range: a join inside a selection rings on the true-peak meter
    gap = round(h - s2, 1)
    print(f"A1 bounce {t0:.3f}-{t1:.3f}s ({wav.name}, mono fold-down): host {h} LUFS · second voice {s2} LUFS · gap {gap} dB "
          f"· true peak {pk} dBTP (the whole bounce)")
    before, played = None, []
    if db:
        (hb, _), (sb, _) = measure(off, rel(host)), measure(off, rel(second))
        before = round(hb - sb, 1)
        pl = plateaus(rec, touched)
        played = [(a, v) for (a, _), v in zip(pl, plateau_lift(off, wav, rel(pl)) if pl else []) if v is not None]
        print(f"  the lift bypassed ({off.name}): host {hb} LUFS · second voice {sb} LUFS · gap {before} dB · the lift on "
              f"{len(played)} plateau(s) of the second voice: " + (' '.join(f'{v:+.2f}' for _, v in played) or 'none measurable'))
    ok, msg = bounce_verdict(n, rec, gap, played, pk, before)
    if not ok:
        sys.exit('✗ ' + msg)
    print('✓ ' + msg)


TARGET_DB = 1.5       # the README's target: the lifted voice within 1.5 dB of the host
NO_LIFT_DB = 3.0      # voice-gain.py's LIFT_OVER_DB: a gap at or under this gets no lift
SLACK_DB = 0.5        # a bounce read against one of those two rules
LIFT_PLAY_TOL_DB = 0.25   # a plateau reads the lift within this: after the limiter it is a pure gain (live: +8.000 exactly)
PLATEAU_MIN_S = 0.05      # s: a plateau shorter than this is not measured
SILENT_MS = 1e-9          # mean square (-90 dBFS): a plateau this quiet on the bypassed bounce has no level to compare
CLIP_FS = 0.9999          # a bounce sample this near full scale is clipped (24-bit PCM stops at 0 dBFS): not read


def bounce_verdict(n, rec, gap, played=(), peak=None, before=None):
    """--bounce's verdict on the bounced clips, held by lift record `rec` (number n) -> (ok, message). `gap` = host minus
    second voice on the bounce as it plays (LUFS over their whole ranges; negative when the second voice plays over the
    host); `played` = [(timeline s, dB)]: the lifted bounce over the bypassed one on each plateau; `peak` = the lifted
    bounce's true peak (dBTP); `before` = the gap on the bypassed bounce.
      - the lift PLAYED: every plateau reads the recorded lift within LIFT_PLAY_TOL_DB. Never judged against
        voice-gain.py's simulated gap: its limiter is not Premiere's (0.5-1.0 dB apart where the phone drives it) and a
        whole span dilutes the lift, so a correct capped mono +8 false-failed (expected 4.6, read 6.3; live 2026-09-24)
      - the CEILING: the lifted bounce's true peak at or under LIFT_CEILING_DBTP, a forced lift included (live: a forced
        +14 whose bounce clipped at +0.5 dBTP passed on its gap)
      - the RULE: no lift, a gap of 3 dB or less; a forced lift, which measured no gap, within 1.5 dB of the host EITHER
        side (live: a +15 that put the phone 7.6 dB OVER the host passed on the signed gap); a measured lift passes on
        what it recorded (a headroom cap cannot reach the target), noted where it lands off the 1.5 dB target
    No record: the gap says whether a lift is needed."""
    db = (rec or {}).get('lift_db') or 0
    fails = []
    if peak is not None and peak > LIFT_CEILING_DBTP:
        fails.append(f"the bounce peaks {peak} dBTP, over the {LIFT_CEILING_DBTP:g} dBTP ceiling: "
                     + ("the lift is too big for the headroom" + (" (forced past the headroom check)" if 'forced' in str(rec.get('source')) else '')
                        + ", re-run --lift with less" if db else
                        "nothing this tool lifted plays here, so a clip lost its chain or carries a hand lift: --verify"))
    if rec is None:
        if gap > NO_LIFT_DB + SLACK_DB:
            fails.insert(0, f"no lift is recorded over these clips, and the second voice sits {gap} dB under the host "
                            f"(over {NO_LIFT_DB:g} dB): run --lift auto")
        return (False, '\n✗ '.join(fails)) if fails else \
            (True, f"no lift record holds these clips, and a gap of {gap} dB needs none (the rule lifts over {NO_LIFT_DB:g} dB)")
    head = f"lift #{n} {db:+d} dB ({rec.get('source')})"
    measured = rec.get('gap_db') is not None
    why = (' (no lift: the gap was 3 dB or less)' if not db and measured else
           ' (capped by the headroom: the 1.5 dB target was out of reach)' if db and rec.get('capped') else '')
    miss = [(t, v) for t, v in played if abs(v - db) > LIFT_PLAY_TOL_DB]
    if db and not played:
        fails.insert(0, f"{head}: no plateau of the second voice ({PLATEAU_MIN_S:g} s or more inside its lead and ramps, not "
                        "silent) to read the lift on, so nothing proves it played: --verify (a rebuild drops the lift)")
    elif miss:
        fails.insert(0, f"{head} did not play as recorded: " + ', '.join(f"the plateau at {t:.3f}s reads {v:+.2f} dB" for t, v in miss[:3])
                        + (f" (and {len(miss) - 3} more)" if len(miss) > 3 else '')
                        + f", the record {db:+d} dB on every one (the lifted bounce over the bypassed one). A rebuild dropped "
                          "it, its lift Amplify is bypassed, or another level moved: --verify, then re-run --lift")
    if not db and gap > NO_LIFT_DB + SLACK_DB:
        fails.append(f"{head}: no lift, and the bounce gap is {gap} dB, over {NO_LIFT_DB:g} dB"
                     + (f" (the record's simulation read {rec['gap_db']}): name the lift (--lift N)" if measured else ": run --lift auto"))
    elif db and not measured and abs(gap) > TARGET_DB + SLACK_DB:
        fails.append(f"{head}: the second voice plays {-gap} dB OVER the host after the lift (target within {TARGET_DB:g}; the "
                     "record has no measured gap to hold it to): the lift is too big, re-run --lift with less" if gap < 0 else
                     f"{head}: the second voice still sits {gap} dB under the host after the lift (target within {TARGET_DB:g}; "
                     "the record has no measured gap to hold it to): the lift did not play, or it was too small")
    if fails:
        return False, '\n✗ '.join(fails)
    if not db:
        return True, f"{head}: no lift, and the bounce gap is {gap} dB{why}"
    lo_, hi_ = min(v for _, v in played), max(v for _, v in played)
    lifted = (f"{lo_:+.2f}" if lo_ == hi_ else f"{lo_:+.2f} to {hi_:+.2f}") + f" dB on {len(played)} plateau(s)"
    if not measured:
        return True, f"{head}: the lift played ({lifted}), and the lifted second voice plays within {TARGET_DB:g} dB of the host ({gap} dB)"
    named = str(rec.get('source') or '').startswith('named')
    note = '' if rec.get('capped') or abs(gap) <= TARGET_DB + SLACK_DB else \
        (f" · a named lift that leaves {gap} dB, short of the {TARGET_DB:g} dB target: the creator's call" if named else
         f" · Premiere's chain leaves it {gap} dB under the host, short of the {TARGET_DB:g} dB target: name a bigger lift if it sounds short") if gap > 0 else \
        (f" · a named lift that puts the second voice {-gap} dB OVER the host (target within {TARGET_DB:g}): the creator's call" if named else
         f" · Premiere's chain puts it {-gap} dB OVER the host (target within {TARGET_DB:g}): name a smaller lift if it sounds loud")
    return True, (f"{head} played as recorded: {lifted}; the gap {before} dB before it in Premiere's own chain (the record's "
                  f"simulation {rec['gap_db']}), {gap} dB after{why}{note}")


_VG = []


def voice_gain():
    """workflows/voice-gain.py as a module: the one owner of the kept-range selection (its keep())."""
    if not _VG:
        import importlib.util
        spec = importlib.util.spec_from_file_location('voice_gain', VOICE_GAIN)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _VG.append(mod)
    return _VG[0]


def bounce_lufs(wav, ranges):
    """(integrated LUFS, true peak dBTP) of `ranges` of a bounced WAV (audio only). The ranges are kept by voice-gain.py's
    keep(): its balanced aselect (a flat a+b+... chain breaks ffmpeg past about 100 terms), or atrim + concat on
    ffmpeg 8.0.x, whose aselect keeps everything (a bounce read host and second voice alike: gap 0.0 dB)."""
    vg = voice_gain()
    with vg.af_option(f"{vg.keep(ranges)},ebur128=peak=true:framelog=quiet") as opt:   # a long graph goes in a file
        p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(wav), '-vn', '-sn', '-dn', *opt, '-f', 'null', '-'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')   # ffmpeg writes UTF-8
    hit = re.search(r'I:\s+(-?[\d.]+) LUFS', p.stderr)
    pk = re.search(r'Peak:\s+(-?(?:inf|[\d.]+)) dBFS', p.stderr)
    if not hit:
        sys.exit(f'✗ ffmpeg did not measure the bounce {wav}')
    return float(hit.group(1)), (float(pk.group(1)) if pk else None)


def save_es():
    r = es('(function(){ app.project.save(); return "ok"; })()')
    if str(r).startswith('ERROR'): sys.exit(r)


def grid(t):
    """A --range bound on the grid A1 starts are compared on: whole microseconds, the six places the polish
    script rounds every clip start to (its r6) before --apply scopes the clip and before --verify sends the start
    back. One number on both sides: ExtendScript's JSON prints 15 significant digits, so the raw double scoped a
    clip one way in the script and was held the other way here (live, 2026-09-23: `--range 16.016 19.9782916666667`
    wrote clip 5, then held it to the whole-timeline record). On the grid, a bound copied from a readback IS that
    clip's start: FROM takes the clip, TO leaves it out."""
    return round(t, 6)


def held_by(recs, start):
    """The index of the record --apply last wrote over an A1 clip starting at `start` (timeline seconds, as the
    script's verify row sends it): the latest one whose range holds it, [FROM, TO) on the same grid --apply
    scoped it on, a whole-timeline record holding every clip. None = no record covers the clip."""
    for k in range(len(recs) - 1, -1, -1):
        if recs[k].get('kind') == 'lift':                 # a second-voice lift record holds no gain
            continue
        r = recs[k].get('range')
        if r is None or grid(r[0]) <= start < grid(r[1]):
            return k
    return None


def holder(recs, name, fallback):
    """A bare --verify's expectation: start -> (gain, label) from the covering record, else `fallback()`
    (the measured gain, measured once and only when some clip has no record over it)."""
    measured = []
    def expect(start):
        k = held_by(recs, start)
        if k is None:
            if not measured: measured.append(fallback())
            g, s = measured[0]
            return g, s + (f' · no {name} record holds it' if recs else '')
        r = recs[k]
        where = f"range {r['range'][0]!r}–{r['range'][1]!r}s" if r['range'] else 'whole timeline'
        return r['gain'], f"{name} #{k + 1}: {r['source']} · {where} · {r['date']}"
    return expect


def judge(rows, expect):
    """--verify: every A1 clip's chain as read back, held to the gain `expect(start)` names for it
    -> (ok, mono, bad lines, {(gain, label): clips held to it})."""
    ok = mono = 0; bad = []; groups = {}
    for i, start, is_mono, gl, gr, gm in rows:
        gain, label = expect(start)
        groups[(gain, label)] = groups.get((gain, label), 0) + 1
        want = amp_v(gain + (PAN_LAW_DB if is_mono else 0))
        if abs(gl - want) > 1e-4 or abs(gr - want) > 1e-4 or abs(gm - lim_v(LIMIT_DB + (PAN_LAW_DB if is_mono else 0))) > 1e-4:
            bad.append(f"{i}: " + (f"Gain={gl}" if is_mono else f"L={gl} R={gr}") + f" lim={gm}"
                       f" · held to {gain:+d} dB ({label})")
        else:
            ok += 1; mono += bool(is_mono)
    return ok, mono, bad, groups


def measure(job):
    m = json.loads(sh('uv', 'run', str(VOICE_GAIN), job, '--json'))
    if m.get('warn'): print('⚠ ' + m['warn'])
    return m['gain_db'], f"measured: kept speech {m['lufs']} LUFS -> target {m['target_lufs']}"


def run(gain, apply, rng=None):
    lo, hi = (grid(rng[0]), grid(rng[1])) if rng else (-1, 1e9)
    try:
        r = es(r"""
(function(){
  var seq = app.project.activeSequence; if (!seq) return "ERROR: no active sequence";
  %s
  var AMP = %s, AMP_MONO = %s, LIM = %s, LIM_MONO = %s, APPLY = %s, LO = %s, HI = %s;
  var tr = seq.audioTracks[0], out = {clips: 0, added: 0, ok: 0, bad: [], rows: []};
  var qtr = null;
  if (APPLY) { app.enableQE(); qtr = qe.project.getActiveSequence().getAudioTrackAt(0); }
  function qItemAt(t){ for (var q = 0; q < qtr.numItems; q++) { var it = qtr.getItemAt(q);
    if (it.type === "Clip" && Math.abs(it.start.secs - t) < 0.002) return it; } return null; }
  for (var i = 0; i < tr.clips.numItems; i++) {
    var c = tr.clips[i], st = r6(c.start.seconds);   // ONE start for the --range scope AND the verify row: JSON prints 15 digits, Python holds this exact value
    if (!out.span) out.span = [st, st]; else { if (st < out.span[0]) out.span[0] = st; if (st > out.span[1]) out.span[1] = st; }   // named when the scope matches nothing
    if (st < LO || st >= HI) continue;   // --range: this section's clips only (LO/HI arrive on the same six-place grid)
    out.clips++;
    if (APPLY) {
      // the chain by POSITION (chainIdx): QE appends, so an Amplify added to a clip that already has its Hard Limiter
      // would land AFTER it, and the lift's Amplify (after the limiter) must never be taken for the gain's
      var ix = chainIdx(c);
      if ((ix.lim >= 0 && ix.amp < 0) || ix.pre > 1) { out.bad.push(i + ": the chain is out of order (the gain Amplify must be the one Amplify before the Hard Limiter): remove the clip's audio effects and re-run --apply"); continue; }
      var need = []; if (ix.amp < 0) need.push("Amplify"); if (ix.lim < 0) need.push("Hard Limiter");
      if (need.length) { var qi = qItemAt(c.start.seconds); if (!qi) { out.bad.push(i + ": no QE item"); continue; }
        for (var n = 0; n < need.length; n++) { qi.addAudioEffect(qe.project.getAudioEffectByName(need[n])); out.added++; } }
      ix = chainIdx(c);
      var a = ix.amp >= 0 ? c.components[ix.amp] : null, l = ix.lim >= 0 ? c.components[ix.lim] : null;
      if (!a || !l || ix.lim < ix.amp) { out.bad.push(i + ": chain missing after add"); continue; }
      // stereo source: Amplify exposes Left + Right; MONO source: one "Gain" slider on the same -96..+48
      // range. A mono clip plays under the -3 dB centre pan law on a stereo master (peaks -9.0 on a -6 limiter,
      // live 2026-09-24), so it takes gain + PAN_LAW into a ceiling PAN_LAW higher: the master hears the same
      // audio in stereo, level and ceiling alike
      var L = prop(a, "Left"), R = prop(a, "Right"), G = prop(a, "Gain"), M = prop(l, "Maximum Amplitude");
      if (!((L && R) || G) || !M) { out.bad.push(i + ": property not found"); continue; }
      var isMono = !!G && !(L && R);
      if (isMono) G.setValue(AMP_MONO, true); else { L.setValue(AMP, true); R.setValue(AMP, true); }
      M.setValue(isMono ? LIM_MONO : LIM, true);
    }
    var jx = chainIdx(c), a2 = jx.amp >= 0 ? c.components[jx.amp] : null, l2 = jx.lim >= 0 ? c.components[jx.lim] : null;
    if (!a2 || !l2) { out.bad.push(i + ": no chain"); continue; }
    if (jx.lim < jx.amp || jx.pre > 1) { out.bad.push(i + ": the chain is out of order (Amplify, then Hard Limiter)"); continue; }
    var L2 = prop(a2, "Left"), R2 = prop(a2, "Right"), G2 = prop(a2, "Gain"), M2 = prop(l2, "Maximum Amplitude");
    if (!((L2 && R2) || G2) || !M2) { out.bad.push(i + ": property not found"); continue; }
    var mono = !(L2 && R2);
    var gl = mono ? G2.getValue() : L2.getValue(), gr = mono ? gl : R2.getValue(), gm = M2.getValue();
    // --verify: the values go back to Python, which holds each clip to the gain --apply recorded over it
    if (!APPLY) { out.rows.push([i, st, mono ? 1 : 0, r6(gl), r6(gr), r6(gm)]); continue; }
    var want = mono ? AMP_MONO : AMP, wantLim = mono ? LIM_MONO : LIM;
    if (Math.abs(gl - want) > 1e-4 || Math.abs(gr - want) > 1e-4 || Math.abs(gm - wantLim) > 1e-4) out.bad.push(i + (mono ? ": Gain=" : ": L=") + gl + (mono ? "" : " R=" + gr) + " lim=" + gm);
    else { out.ok++; if (mono) out.mono = (out.mono || 0) + 1; }
  }
  if (APPLY && !out.bad.length && out.clips) app.project.save();
  return JSON.stringify(out);
})()""" % ((JS_HELPERS,) + ((amp_v(gain), amp_v(gain + PAN_LAW_DB)) if apply else ('null', 'null'))   # --verify judges in Python
                + (lim_v(LIMIT_DB), lim_v(LIMIT_DB + PAN_LAW_DB), 'true' if apply else 'false', repr(float(lo)), repr(float(hi)))),
               # every A1 clip in ONE script: the panel's 45 s watchdog kills a several-hundred-clip pass
               # and reports the whole thing as a failure (lanes/premiere/lab-notes.md § the output contract)
               timeout=900000)
    except SystemExit:
        if apply:
            # the chain is written clip by clip and saved only at the end, so a failure part-way leaves some
            # A1 clips amplified and some not, unsaved. Never re-run --apply on top of a guess: it is
            # idempotent (it updates an existing chain in place), but the state has to be read first.
            print('⚠ the pass stopped part-way: some A1 clips may carry the chain and some not, and the project '
                  'was NOT saved. Close without saving, or re-run --verify to see what is on the clips.', file=sys.stderr)
        raise
    if str(r).startswith('ERROR'): sys.exit(r)
    return json.loads(r)


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    job = a[0]
    apply = '--apply' in a
    rng = None
    if '--range' in a:   # multi-section jobs: only A1 clips starting in [FROM, TO) seconds get this gain
        i = a.index('--range'); rng = (float(a[i + 1]), float(a[i + 2]))
    log = job_root(job) / 'premiere' / 'audio-polish.json'   # what every successful --apply wrote (a section's too)
    recs = load_records(log)
    if '--lift' in a or '--bounce' in a:
        if apply or '--verify' in a or '--gain' in a or ('--lift' in a and '--bounce' in a):
            sys.exit('--lift and --bounce run on their own (the chain first with --apply, then --lift, then --bounce; '
                     'a bare --verify checks the chain and the lift)')
        if '--bounce' in a:
            return bounce(job, recs, rng)
        i = a.index('--lift') + 1
        if i >= len(a) or not (a[i] == 'auto' or a[i].lstrip('+-').isdigit()):
            sys.exit('--lift takes auto or a whole dB number (0 drops the lift)')
        return lift(job, a[i], recs, log, rng, force='--force' in a)
    gain = src = None
    if '--gain' in a:
        gain = int(a[a.index('--gain') + 1]); src = 'named'
    elif apply:
        gain, src = measure(job)
    require_job_project(es, job)   # the chain lands on the ACTIVE sequence's A1: it must be this job's project
    got = run(gain, apply, rng)
    if not got['clips']:   # a mistyped --range (or an empty A1) touched nothing: never a pass, never 'saved'
        span = got.get('span')
        a1 = f"A1 clips start {span[0]!r}–{span[1]!r}s" if span else 'A1 holds no clips'
        sys.exit(f"✗ no A1 clip starts in {f'--range {rng[0]!r}–{rng[1]!r}s' if rng else 'the sequence'} ({a1}): "
                 f"nothing {'written, nothing recorded' if apply else 'verified'}.")
    groups = {(gain, src): got['clips']}
    if not apply:   # each clip held to one gain: the one named here, else the record --apply left over it
        expect = (lambda start: (gain, src)) if gain is not None else holder(recs, log.name, lambda: measure(job))
        ok, mono, bad, held = judge(got['rows'], expect)
        got.update(ok=ok, mono=mono, bad=got['bad'] + bad)
        groups = held or (groups if gain is not None else {})
    scope = f" · range {rng[0]!r}–{rng[1]!r}s" if rng else ''
    head = ', '.join(f"{g:+d} dB ({s})" + (f" on {n} clip(s)" if len(groups) > 1 else '') for (g, s), n in groups.items()) or '— (no chain read back)'
    mono_at = f"{next(iter(groups))[0] + PAN_LAW_DB:+d} dB" if len(groups) == 1 else f"the clip's gain {PAN_LAW_DB:+d} dB"
    print(f"gain {head} · limiter {LIMIT_DB} dBFS · A1 clips {got['clips']}{scope} · chain added on {got['added']} effect slot(s) · {got['ok']} verified" + (f" ({got['mono']} mono: Gain slider at {mono_at} into a {LIMIT_DB + PAN_LAW_DB} dBFS ceiling, the -3 dB centre pan law given back)" if got.get('mono') else ''))
    lifts = lift_records(recs) if not apply else []
    if not apply and any(r.get('kind') == 'lift' and r.get('stage') != LIFT_STAGE for r in recs):
        print('⚠ audio-polish.json holds a lift record from before the lift moved after the limiter (Volume > Level '
              'keys): not verified. Re-run --lift, which writes the lift Amplify and a current record.')
    if lifts:
        lbad, lok = verify_lifts(recs, read_a1())
        got['bad'] += lbad
        for n, r in lifts:
            if lok.get(n):
                print(f"lift #{n} {r['lift_db']:+d} dB ({r['source']}) on {lok[n]} A1 clip(s): keys read back "
                      "(a readback, not a bounce: --bounce is the proof)")
    for b in got['bad']: print('✗ ' + b)
    if got['bad']: sys.exit(1)
    if apply:
        print('saved')
        if got['clips']:
            n = record(log, gain, src, rng)
            print(f"recorded as {log.name} #{n}: a bare --verify holds these clips to {gain:+d} dB")


if __name__ == '__main__':
    main()
