#!/usr/bin/env python3
"""voice-gain.py: the step-3 gain, MEASURED from the kept speech (universal, every lane).

  uv run workflows/voice-gain.py projects/<job>            # prints the measurement + the gain to use
  uv run workflows/voice-gain.py projects/<job> --json     # {"gain_db", "lufs", "true_peak", "lra", ...}
  uv run workflows/voice-gain.py projects/<job> --edl <cuts.json> [--json]
                                                           # measure another EDL's kept ranges (splice.sh passes the
                                                           # one it renders; a relative path is from the cwd)
  uv run workflows/voice-gain.py projects/<job> --second-voice [transcript/voices.json] [--gain N] [--json]
                                                           # + the second voice's gap after the chain, and its lift

The house chain is static: +GAIN dB into a hard limiter at -6 dBFS, never dynamic. The limiter is
FIXED; the gain is whatever puts the raw's kept speech on the house target, so a quiet shoot and a
hot shoot both land in the same place:

    TARGET = -17 LUFS integrated, pre-limiter    ->    gain = round(TARGET - measured)

Measured on the KEPT ranges only (transcript/cuts.json against raw/), never the whole take: dead air
and the slate would drag the integrated number down and over-gain the speech. ffmpeg 8.0.x's aselect keeps
everything, so there the ranges are cut out by atrim + concat instead (keep(), aselect_works()).

A MONO raw is measured as DUAL MONO (ebur128 dualmono): the level it plays at on both channels of a stereo
master, so a mono raw and its stereo twin get the same gain. Measured as one channel it read 3 LU under its twin
and took 3 dB more gain (live 2026-09-24: the same mix bounced -13.5 LUFS as a mono clip, -16.4 as stereo). How a
lane plays a mono clip at that level is the lane's business (Premiere: audio-polish.py gives its -3 dB centre pan
law back).

Where the target comes from and how each lane applies the chain: LANES.md § step 3.

--second-voice (a second voice through a speaker: an AI on a call, a phone, a played clip; the Talking Head
Explainer's README § Audio owns the rule). Its spans are transcript/voices.json, RAW clock per clip:
{"spans": [{"clip", "start", "end", "voice"}]} (the file captions.py reads). A span names its raw (`clip`, matched
case-insensitively, the way APFS matches it); a span with no `clip` is allowed only on a one-raw job, and a clip name
cuts.json does not use is refused (exit 1), so a typo never reads as "the cut dropped the replies".
The house chain is simulated offline on the raw as the master hears it (the gain, then the -6 dBFS limiter, a MONO
raw read as dual mono), and the kept speech is measured apart: the HOST over
every kept host range of the job, the SECOND voice over its kept spans, plus the second voice's true peak after the
chain. gap = host - second (LU). Over LIFT_OVER_DB the lift is ceil(gap - 1.5) whole dB, a level ride AFTER the
limiter on those spans only (its ramps inside them, so the host is never lifted), which lands the phone within 1.5 dB
of the host; at or under it, none. Being after the limiter, the lift raises the spans' peaks by the same dB, so it is
CAPPED where their true peak reaches LIFT_CEILING_DBTP (-1 dBTP): the cap and the landing peak are printed. The peak
is read on EVERY kept second-voice selection, a sliver too short to gate included, so the cap (`cap_db`) is in the JSON
whenever any kept second voice is, gap or not: a lift named by ear on a short reply is capped too.
Under MIN_SECOND_S of kept second-voice speech (or a clip whose selection is too short to gate: ebur128's -70 LUFS
floor) the gap is UNMEASURABLE: printed as a warning with lift 0 and `"unmeasurable": true` in the JSON, which
audio-polish.py --lift auto refuses. `--gain N` simulates the chain at N (the gain audio-polish.json recorded over the
covered clips) instead of the measured one: the gap moves about 1.2 dB per 3 dB into the limiter.
Nothing is written: the lane applies it (Premiere: lanes/premiere/audio-polish.py --lift auto).
"""
import contextlib, json, math, os, re, subprocess, sys, tempfile
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path

TARGET_LUFS = -17.0
LIMIT_DBFS = -6.0
GAIN_MIN, GAIN_MAX = 0, 24
LIFT_OVER_DB = 3.0        # a second voice this far or less under the host is left alone
LIFT_SHORT_DB = 1.5       # the lift lands it at most this far under the host (it still sounds like a phone)
LIFT_CEILING_DBTP = -1.0  # the lifted spans' true peak lands at or under this (README § Audio (c) allows about -0.3)
MIN_SECOND_S = 3.0        # less kept second-voice speech than this is not a measurement
EBU_FLOOR = -69.9         # ebur128 reports -70.0 LUFS for a selection too short to gate (under 0.4 s): no reading
# ffmpeg writes UTF-8 (the raw's path is echoed in it). Decoded as Windows' cp1252, a path holding an Á (UTF-8 c3 81) killed
# the reader thread, stderr came back None and the LUFS regex raised a TypeError that hid the cause.
UTF8 = dict(text=True, encoding='utf-8', errors='replace')


def select_expr(ranges):
    if not ranges:
        return '0'                                          # selects nothing (callers skip empty lists before measuring)
    # A BALANCED sum, parenthesised in halves: ffmpeg's expression parser has a nesting limit a flat
    # a+b+c+... chain hits past about 100 terms (a 193-range screen recording failed with "Cannot
    # allocate memory"). The tree is log2(n) deep and selects exactly the same samples.
    if len(ranges) == 1:
        a, b = ranges[0]
        return f'between(t,{a:.4f},{b:.4f})'
    m = len(ranges) // 2
    return f'({select_expr(ranges[:m])}+{select_expr(ranges[m:])})'


_ASELECT = {}


def aselect_works():
    """Does this ffmpeg's aselect drop what its expression rejects? ffmpeg 8.0 ported select to `activate` and left
    aselect without one (fixed upstream 2025-11-22, after 8.0.1), so on 8.0.x aselect passes EVERY frame whatever the
    expression: the kept-range measurement read the whole raw, dead air and killed takes included, and every second
    voice's gap read 0.0 dB (winget's ffmpeg 8.0.1 on Windows, 2026-09-27; 8.1.1 selects). Probed once per run on a
    1 s tone: a working aselect keeps its first half (8192 bytes), a pass-through all of it (16000)."""
    if 'ok' not in _ASELECT:
        p = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=8000:duration=1',
                            '-af', "aselect='lt(t,0.5)'", '-f', 's16le', '-'], capture_output=True)
        _ASELECT['ok'] = p.returncode == 0 and 0 < len(p.stdout) < 12000
    return _ASELECT['ok']


def union(ranges):
    """`ranges` as their sorted union: what a sum of between() terms selects, each sample once, in time order."""
    out = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def keep(ranges):
    """The filter chain that keeps only `ranges` of its input, the clock restarted: aselect over the balanced
    select_expr, or, on an ffmpeg whose aselect passes everything (aselect_works), one atrim per range of their union,
    joined in time order by concat (sample-exact where aselect keeps whole frames: the same speech)."""
    if aselect_works():
        return f"aselect='{select_expr(ranges)}',asetpts=N/SR/TB"
    u = union(ranges)
    if not u:
        return 'atrim=end_sample=0,asetpts=N/SR/TB'           # nothing, as aselect='0' (callers skip empty lists)
    trims = [f'atrim=start={a:.4f}:end={b:.4f}' for a, b in u]
    if len(u) == 1:
        return f'{trims[0]},asetpts=N/SR/TB'
    n = len(u)
    return (f"asplit={n}{''.join(f'[k{i}]' for i in range(n))};"
            + ''.join(f'[k{i}]{t}[t{i}];' for i, t in enumerate(trims))
            + ''.join(f'[t{i}]' for i in range(n)) + f'concat=n={n}:v=0:a=1,asetpts=N/SR/TB')


AF_ARGV_MAX = 8000   # chars: a longer -af graph goes in a file on Windows, or wherever keep() uses its fallback


@contextlib.contextmanager
def af_option(af):
    """The ffmpeg option carrying the audio graph `af`: ['-af', af], or, for a long graph on Windows (a 32767-char command
    line: 900 kept ranges through keep()'s fallback raised WinError 206) or on the fallback's ffmpeg (8.0.x),
    ['-/af', <a temp file holding it>]: ffmpeg 7.1+ reads an option's value from a file. A working aselect off Windows
    keeps the command it always ran."""
    if len(af) <= AF_ARGV_MAX or (os.name != 'nt' and aselect_works()):
        yield ['-af', af]
        return
    fd, path = tempfile.mkstemp(suffix='.af')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(af)
        yield ['-/af', path]
    finally:
        os.unlink(path)


def ebur128(mono):
    """The loudness meter: a MONO raw read as dual mono, the level both master channels play it at."""
    return 'ebur128=peak=true' + (':dualmono=true' if mono else '') + ':framelog=quiet'


def measure(raw, ranges, mono=False):
    af = f"{keep(ranges)},{ebur128(mono)},volumedetect"
    with af_option(af) as opt:
        p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', raw, '-vn', '-sn', '-dn', *opt, '-f', 'null', '-'],
                           capture_output=True, **UTF8)
    r = p.stderr

    def g(pat):
        hit = re.search(pat, r)
        if not hit:
            tail = '\n'.join(r.strip().splitlines()[-12:])
            sys.exit(f'✗ ffmpeg did not measure {os.path.basename(raw)} ({len(ranges)} kept ranges, exit {p.returncode}); '
                     f'no match for {pat!r}. stderr tail:\n{tail}')
        return float(hit.group(1))
    return dict(lufs=g(r'I:\s+(-?[\d.]+) LUFS'), lra=g(r'LRA:\s+([\d.]+) LU'),
                true_peak=g(r'Peak:\s+(-?[\d.]+) dBFS'), mean=g(r'mean_volume: (-?[\d.]+)'), kept_s=sum(b - a for a, b in ranges))


def recommend_lift(gap, cap=None):
    """The second voice's lift in whole dB: none at or under LIFT_OVER_DB, else the smallest whole dB that lands it at
    most LIFT_SHORT_DB under the host (ceil: a 4.8 dB gap is +4, landing 0.8 under, where rounding gave +3 and 1.8),
    never above `cap` (the headroom) and never below 0."""
    if gap <= LIFT_OVER_DB:
        return 0
    lift = int(math.ceil(round(gap - LIFT_SHORT_DB, 3)))
    return max(0, min(lift, cap)) if cap is not None else lift


def lift_cap(peak):
    """The biggest whole-dB lift that keeps a true peak of `peak` dBTP at or under LIFT_CEILING_DBTP (0 at or over it)."""
    if peak is None or peak == float('-inf'):
        return None
    return max(0, int(math.floor(round(LIFT_CEILING_DBTP - peak, 3))))


def subtract(ranges, holes):
    """ranges minus holes, both [(a, b)]."""
    out = []
    for a, b in ranges:
        cur = [(a, b)]
        for h0, h1 in holes:
            nxt = []
            for x, y in cur:
                if h1 <= x or h0 >= y:
                    nxt.append((x, y)); continue
                if h0 > x: nxt.append((x, h0))
                if h1 < y: nxt.append((h1, y))
            cur = nxt
        out += cur
    return [(a, b) for a, b in out if b - a > 0.02]


def intersect(ranges, spans):
    out = [(max(a, s0), min(b, s1)) for a, b in ranges for s0, s1 in spans]
    return sorted((a, b) for a, b in out if b - a > 0.02)


def channels(raw):
    """The raw's audio channel count (2 when ffprobe cannot say): a MONO raw is measured as dual mono."""
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels',
                        '-of', 'csv=p=0', str(raw)], capture_output=True, **UTF8)
    try:
        return int(p.stdout.strip().split()[0])
    except (ValueError, IndexError):
        return 2


def chained(raw, ranges, gain_db, mono=False):
    """(integrated LUFS, true peak dBTP) of `ranges` of the raw AFTER the house chain as the master hears it: the gain,
    then the -6 dBFS limiter. Measured on the continuous chained audio so the limiter sees what it sees on the
    timeline. A MONO raw is read as dual mono, so it measures exactly as its stereo twin: the loudness and the peak
    per master channel (a lane that plays mono under a pan law gives it back, Premiere's audio-polish.py)."""
    lim = 10 ** (LIMIT_DBFS / 20)
    af = (f"volume={gain_db}dB,alimiter=limit={lim:.6f}:level=false,"
          f"{keep(ranges)},{ebur128(mono)}")
    with af_option(af) as opt:
        p = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', str(raw), '-vn', '-sn', '-dn', *opt, '-f', 'null', '-'],
                           capture_output=True, **UTF8)
    hit = re.search(r'I:\s+(-?[\d.]+) LUFS', p.stderr)
    if not hit:
        tail = '\n'.join(p.stderr.strip().splitlines()[-12:])
        sys.exit(f'✗ ffmpeg did not measure the chained {os.path.basename(str(raw))} (exit {p.returncode}). stderr tail:\n{tail}')
    pk = re.search(r'Peak:\s+(-?(?:inf|[\d.]+)) dBFS', p.stderr)
    peak = float(pk.group(1)) if pk else None
    if peak == float('-inf'):
        peak = None                                           # digital silence: no peak to cap against
    return float(hit.group(1)), peak


def chained_lufs(raw, ranges, gain_db, mono=False):
    """Integrated loudness of `ranges` of the raw AFTER the house chain (see chained())."""
    return chained(raw, ranges, gain_db, mono)[0]


def second_voice(raw, host, second, gain_db, mono=False):
    """{host_lufs, second_lufs, gap_db, lift_db, ...} for ONE raw: host and second = kept raw-clock ranges."""
    (h, _), (s, pk) = chained(raw, host, gain_db, mono), chained(raw, second, gain_db, mono)
    gap = round(h - s, 1)
    cap = lift_cap(pk)
    return dict(host_lufs=h, second_lufs=s, gap_db=gap, lift_db=recommend_lift(gap, cap), want_db=recommend_lift(gap),
                cap_db=cap, second_true_peak=pk, host_s=round(sum(b - a for a, b in host), 1),
                second_s=round(sum(b - a for a, b in second), 1))


def load_voice_spans(path):
    """voices.json -> {clip basename or None: [(start, end)]} (the schema captions.py reads)."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    spans = data.get('spans') if isinstance(data, dict) else None
    if not isinstance(spans, list):
        sys.exit(f'✗ {path} has no `spans` list: {{"spans": [{{"clip", "start", "end", "voice"}}]}}')
    out = {}
    for s in spans:
        out.setdefault(os.path.basename(s['clip']) if s.get('clip') else None, []).append((float(s['start']), float(s['end'])))
    return out


def resolve_spans(voices, by_clip, raw_of, where):
    """{clip key of by_clip: [spans]}: each voices.json clip name matched case-insensitively against the EDL's clips and
    their raw files. A name nothing matches, or a span with no `clip` on a job of several raws, stops the run: both
    used to read as "no second-voice speech inside the kept spans" and pass with no lift."""
    names = {}
    for c in by_clip:
        names[c.lower()] = c
        if raw_of.get(c) is not None:
            names[raw_of[c].name.lower()] = c
    out = {c: [] for c in by_clip}
    for c, spans in voices.items():
        if c is None:
            if len(by_clip) > 1:
                sys.exit(f"✗ {where}: a span with no `clip` on a job of {len(by_clip)} raws ({', '.join(sorted(by_clip))}): "
                         "name the raw each span is on")
            key = next(iter(by_clip))
        else:
            key = names.get(c.lower())
            if key is None:
                sys.exit(f"✗ {where}: a span names clip {c!r}, which cuts.json does not use "
                         f"({', '.join(sorted(n for n in names if n)) or 'no clip names'}): fix the name")
        out[key] += spans
    return out


def second_voice_job(vp, by_clip, raw_of, gain_db, mono_of=None):
    """The job's second-voice block: the host over EVERY kept host range of the job (a raw that is all second voice,
    a played clip, is measured against the host's own raws), the second voice over its kept spans, weighted by
    unrounded seconds, each clip's reading dropped when its selection is under ebur128's gate (-70 LUFS), though its
    peak still counts toward the headroom: the lift raises every kept second-voice sample, gated or not."""
    spans_of = resolve_spans(load_voice_spans(vp), by_clip, raw_of, vp)
    mono_of = mono_of or {}
    host, second, notes, peaks = [], [], [], []
    for clip, ranges in by_clip.items():
        raw = raw_of[clip]
        mono = mono_of[clip] if clip in mono_of else channels(raw) == 1
        sp = spans_of[clip]
        for kind, rr in (('host', subtract(ranges, sp)), ('second', intersect(ranges, sp) if sp else [])):
            if not rr:
                continue
            secs = sum(b - a for a, b in rr)
            lufs, peak = chained(raw, rr, gain_db, mono)
            if kind == 'second' and peak is not None:
                peaks.append(peak)   # every kept second-voice sample is lifted: a selection too short to gate still peaks
            if lufs <= EBU_FLOOR:
                notes.append(f'{raw.name}: {secs:.2f}s of {kind} speech is too short to measure (ebur128 reads {lufs} LUFS), left out')
                continue
            (host if kind == 'host' else second).append(dict(raw=raw.name, lufs=lufs, true_peak=peak, s=secs, mono=mono))
    out = dict(voices=str(vp), gain_db=gain_db, host=host, second=second, notes=notes, lift_db=0,
               host_s=round(sum(x['s'] for x in host), 2), second_s=round(sum(x['s'] for x in second), 2))
    tp = max(peaks) if peaks else None
    # the headroom needs no gap: a lift named by ear on a reply too short to measure is still capped
    headroom = dict(second_true_peak=tp, cap_db=lift_cap(tp)) if tp is not None else {}
    kept_second = any(intersect(by_clip[c], spans_of[c]) for c in by_clip if spans_of[c])
    if not kept_second:
        out['warn'] = 'no second-voice speech inside the kept ranges: the cut dropped every span'
        return out
    if out['second_s'] < MIN_SECOND_S:
        out.update(unmeasurable=True, warn=f"only {out['second_s']:.2f}s of second-voice speech is measurable "
                                            f"(under {MIN_SECOND_S:g}s): no gap, no lift", **headroom)
        return out
    if not host:
        out.update(unmeasurable=True, warn='no host speech is kept to measure the second voice against', **headroom)
        return out
    hs, ss = sum(x['s'] for x in host), sum(x['s'] for x in second)
    out['host_lufs'] = round(sum(x['lufs'] * x['s'] for x in host) / hs, 1)
    out['second_lufs'] = round(sum(x['lufs'] * x['s'] for x in second) / ss, 1)
    out['second_true_peak'] = tp
    out['gap_db'] = round(out['host_lufs'] - out['second_lufs'], 1)
    out['cap_db'] = lift_cap(tp)
    out['want_db'] = recommend_lift(out['gap_db'])
    out['lift_db'] = recommend_lift(out['gap_db'], out['cap_db'])
    out['capped'] = out['lift_db'] < out['want_db']
    if out['second_true_peak'] is not None:
        out['landing_peak'] = round(out['second_true_peak'] + out['lift_db'], 1)
    return out


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    job = Path(a[0]).resolve()
    edl = job / 'transcript' / 'cuts.json'
    if '--edl' in a:
        i = a.index('--edl')
        if i + 1 >= len(a) or a[i + 1].startswith('--'):
            sys.exit('--edl takes a cuts.json path')
        edl = Path(a[i + 1]).resolve()
    if not edl.exists():
        sys.exit(f'no EDL at {edl}: run rough-cut first, or pass --edl <cuts.json>')
    cuts = json.loads(edl.read_text(encoding="utf-8"))['segments']
    raws = sorted(job.glob('raw/*'))
    by_clip = {}
    for s in cuts:
        clip = os.path.basename(s.get('clip') or '')
        # inserted media (a meme or b-roll insert laid from its own file) is not the creator's voice; without this the
        # one-raw fallback below measured its span of the RAW (2026-09-28: pre-roll dead air, the gain read +12 for +11)
        if s.get('media') and not any(p.name == clip for p in raws):
            continue
        by_clip.setdefault(clip, []).append((float(s['start']), float(s['end'])))
    out = []
    raw_of = {}
    for clip, ranges in by_clip.items():
        raw = next((p for p in raws if p.name == clip), None) or (raws[0] if len(raws) == 1 else None)
        if not raw: sys.exit(f'no raw file for {clip!r} under {job / "raw"}')
        raw_of[clip] = raw
        mono = channels(raw) == 1
        m = measure(str(raw), ranges, mono); m.update(raw=raw.name, mono=mono); out.append(m)
    # one gain for the whole job: weight the per-clip integrated loudness by kept seconds
    tot = sum(m['kept_s'] for m in out)
    lufs = sum(m['lufs'] * m['kept_s'] for m in out) / tot
    tp = max(m['true_peak'] for m in out)
    gain = int(round(TARGET_LUFS - lufs))
    warn = None
    if gain < GAIN_MIN or gain > GAIN_MAX:
        clamped = max(GAIN_MIN, min(GAIN_MAX, gain))
        warn = (f'measured {gain:+d}, clamped to {clamped:+d} ({GAIN_MIN}..{GAIN_MAX}): the raw is far off a normal shoot, '
                'check it before trusting this')
        gain = clamped
    res = dict(gain_db=gain, target_lufs=TARGET_LUFS, lufs=round(lufs, 1), true_peak=tp, lra=out[0]['lra'],
               over_ceiling_db=round(tp + gain - LIMIT_DBFS, 1), kept_s=round(tot, 1), clips=out, warn=warn,
               premiere_amplify_v=round((gain + 96) / 144, 6))
    if '--second-voice' in a:
        i = a.index('--second-voice')
        vp = a[i + 1] if i + 1 < len(a) and not a[i + 1].startswith('--') else 'transcript/voices.json'
        vp = Path(vp) if Path(vp).is_absolute() else job / vp
        if not vp.exists():
            sys.exit(f'✗ no {vp}: write the second voice\'s RAW-clock spans there first (rough-cut § Transcribe)')
        chain_gain = gain
        if '--gain' in a:          # the gain the timeline carries (audio-polish.json's record), not today's measurement
            try:
                chain_gain = int(a[a.index('--gain') + 1])
            except (IndexError, ValueError):
                sys.exit('--gain takes a whole dB number')
        res['second_voice'] = second_voice_job(vp, by_clip, raw_of, chain_gain)
    if '--json' in a:
        print(json.dumps(res)); return
    print(f"kept speech {res['kept_s']}s in {len(out)} clip(s): {res['lufs']} LUFS integrated · true peak {tp} dBFS · LRA {res['lra']} LU")
    print(f"target {TARGET_LUFS} LUFS pre-limiter -> gain {gain:+d} dB  (Amplify v={res['premiere_amplify_v']}; limiter stays at {LIMIT_DBFS:.0f} dBFS, peaks land {res['over_ceiling_db']:+.1f} dB over it)")
    if warn: print('⚠ ' + warn)
    sv_ = res.get('second_voice')
    if sv_:
        for n in sv_.get('notes') or []:
            print(f'second voice: ⚠ {n}')
    if sv_ and sv_.get('warn'):
        print(f"second voice: ⚠ {sv_['warn']} ({sv_['voices']})")
        if sv_.get('cap_db') is not None:
            print(f"second voice: headroom cap {sv_['cap_db']:+d} (its kept spans peak {sv_['second_true_peak']} dBTP after the chain, "
                  f"the ceiling is {LIFT_CEILING_DBTP:g}): a lift named by ear over it is refused")
    elif sv_:
        print(f"second voice after the chain at {sv_['gain_db']:+d} dB: host {sv_['host_lufs']} LUFS ({sv_['host_s']}s) · "
              f"second {sv_['second_lufs']} LUFS ({sv_['second_s']}s, true peak {sv_['second_true_peak']} dBTP) · gap {sv_['gap_db']} dB")
        if not sv_['want_db']:
            print(f"-> no lift (the gap is {LIFT_OVER_DB:g} dB or less)")
        else:
            cap = (f" · CAPPED from {sv_['want_db']:+d} by the headroom: the spans peak {sv_['second_true_peak']} dBTP, "
                   f"the ceiling is {LIFT_CEILING_DBTP:g}" if sv_['capped'] else f" · headroom cap {sv_['cap_db']:+d}")
            print(f"-> lift {sv_['lift_db']:+d} dB on its spans, after the limiter, 50 ms ramps inside them (applied and announced){cap} · "
                  f"lifted peak {sv_.get('landing_peak')} dBTP")

if __name__ == '__main__':
    main()
