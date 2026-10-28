#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""lip-sync.py: measure how far a camera stream runs from the voice it is cut against, and whether the offset DRIFTS.

  uv run workflows/lip-sync.py <cam.mp4> --audio <mic-source.mp4>                      # 9 windows across the take
  uv run workflows/lip-sync.py <cam.mp4> --audio <mic.mp4> --mouth-crop iw*0.14:ih*0.16:iw*0.44:ih*0.53
  uv run workflows/lip-sync.py <cam.mp4> --audio <mic.mp4> --windows 5 --window-len 90 --json

  --fps N           the grid the answer is reported on (default: the cam's own rate)
  --mouth-crop C    ffmpeg crop (w:h:x:y) around the mouth; default is the centre column's lower band
  --windows N       probe points spread across the take (default 9), each slid onto the talkiest window in its slot
  --window-len S    seconds correlated per window (default 120; a long window is what makes sub-frame drift readable)
  --max-lag N       frames searched either way (default 12)
  --min-speech F    fraction of a window that must carry voice for it to be probed (default 0.35)
  --min-peak S      drop a window whose peak stands less than S sigma above its own curve (default 0: report only)
  --json            the table, the fit and the verdict as JSON
  --slip-out PATH   write the whole-frame V1 slip for the replay (`<job>/transcript/av-slip.json`): 0 on PASS, the
                    median window's lag on FAIL, rounded so the sound never leads by more than 0.3 frame; refused
                    (nothing written) on UNMEASURED or when a window sits more than 1.5 frames off that number (a take
                    that drifts: one number cannot fix it)

Positive lag = the PICTURE is late against the voice by that many frames, so the camera clip's source in-point
moves LATER by the lag to line up.

Exit 0 = PASS, in sync within a frame across the take. Exit 1 = FAIL, with the per-clip slip to apply. Exit 2 =
UNMEASURED: the windows disagree, or fewer than two measured, so there is no answer to act on (almost always the
mouth crop — see below).

Why this exists (2026-09-19): a screen recorder's facecam is not lip-synced to its own mic, and the error
is not constant — that take ran +1.9 frames at the start and +8.3 by the end, a slow stretch of about 2 frames per
1000 s. It is invisible while the facecam is a corner bubble and unmissable the moment the angle is cut full frame,
which is when the creator caught it on playback. Measuring it is two envelopes: the mouth region's frame-to-frame
motion, and the voice's energy change. Both spike on a plosive, so their cross-correlation peak IS the offset; the
peak is fitted parabolically for sub-frame resolution and the per-window lags are fitted linearly (weighted by peak
strength) to expose the drift a single probe would hide.

THE WINDOWS HAVE TO LAND ON SPEECH. A probe point dropped on a silent stretch — a pause, a demo playing, a long
read — still returns a peak, just one correlated out of room tone and idle face motion: a weak window like that
sits at the wrong lag and, because it is only DOWN-weighted rather than excluded, it tilts the whole drift line.
So the evenly-spread probe points are slid onto the talkiest window inside their own slot, measured off a coarse
voice envelope of the take, and a slot with no speech in it is skipped and named rather than measured. Ties go to
the even spacing: on a take that talks throughout, sliding every window to the first-best candidate bunches the
probes into a corner of the take, and the drift line is only as good as its lever arm.

VOICE IN THE MIC IS NOT PROOF THE SPEAKER IS ON CAMERA, though — a clip playing on screen, an off-camera line, a
stretch of listening all fill a window with speech energy while the mouth does something else. Each window
therefore also reports how far its correlation peak stands above the rest of its own curve, in sigma, and that
number is what weights the drift fit (measured against a hand-built reference fit, it tracked it twice as closely
as weighting by the correlation itself). It is NOT a gate by default: on the take it was calibrated against, an
accurate window and one seven frames out both read 1.4 sigma, so a threshold would have thrown away good windows
to catch a bad one. --min-peak turns it into a gate for a take whose own table shows a clean split.

The rule this enforces: rough-cut § Gotchas — a facecam laid as its own angle is lip-sync-measured first, and each
clip's in-point slips by the lag AT ITS OWN SOURCE TIME, not by one number for the whole take.
"""
import argparse, json, math, subprocess, sys

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np

# The mouth sits in the centre column, below the midline, on any sane face framing — wide enough to survive a
# reframe, tight enough to keep a moving hand or a busy background out of the motion envelope.
DEFAULT_CROP = 'iw*0.34:ih*0.30:iw*0.33:ih*0.45'
COVER = 0.8         # a window is measured only when this much of it decodes, picture AND voice


def probe(path):
    """(video frame rate or 0.0, duration or 0.0). JSON keeps the stream apart from the container: the plain read put
    an audio-only file's (a WAV mic's) format duration where the rate goes and read its duration as 0 s, so the take
    ran on the camera's length past the mic's end (2026-10-13). A container without a duration answers 0.0."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=r_frame_rate:format=duration', '-of', 'json', str(path)],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
    except ValueError:
        d = {}
    num, _, den = ((d.get('streams') or [{}])[0].get('r_frame_rate') or '0/1').partition('/')
    try:
        dur = float((d.get('format') or {}).get('duration') or 0)
    except ValueError:
        dur = 0.0
    return (float(num) / float(den or 1) if float(num) else 0.0), dur


def mouth(cam, t0, dur, crop, fps):
    """Frame-to-frame motion of the mouth region, one sample per frame."""
    raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(t0), '-t', str(dur), '-i', str(cam),
                          '-vf', f'crop={crop},scale=64:40,format=gray', '-r', str(fps),
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    f = np.frombuffer(raw, np.uint8).reshape(-1, 40, 64).astype(float)
    if len(f) < 2:
        sys.exit(f'✗ no video decoded from {cam} at {t0}s')
    return np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))


def voice(audio, t0, dur, fps):
    """Change in voice energy, on the SAME grid as the mouth envelope (1000 samples per frame)."""
    rate = int(round(1000 * fps))
    raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(t0), '-t', str(dur), '-i', str(audio),
                          '-vn', '-ac', '1', '-ar', str(rate), '-f', 's16le', '-'], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(float)
    n = len(a) // 1000
    if n < 2:
        sys.exit(f'✗ no audio decoded from {audio} at {t0}s')
    e = np.sqrt((a[:n * 1000].reshape(n, 1000) ** 2).mean(1))
    return np.abs(np.diff(e))


def envelope(audio, dur, hop=1.0):
    """One RMS per `hop` seconds across the whole take: the coarse map of where the voice is."""
    raw = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-t', str(dur), '-i', str(audio),
                          '-vn', '-ac', '1', '-ar', '1000', '-f', 's16le', '-'], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(float)
    step = int(1000 * hop)
    n = len(a) // step
    if n < 2:
        return None
    return np.sqrt((a[:n * step].reshape(n, step) ** 2).mean(1))


def place_windows(env, hop, span, length, n, floor):
    """-> [(start, speech fraction)] — the evenly-spread probe points, each slid onto the talkiest
    window inside its own slot, and a slot with no speech in it dropped.

    Loud is measured against the take's own 90th percentile, so a quiet shoot is not all silence and
    a hot one is not all speech; `floor` is how much of a window has to be above that.
    """
    if n < 2:
        return [(span / 2, 1.0)]
    even = [span * k / (n - 1) for k in range(n)]
    if env is None:
        return [(t, 1.0) for t in even]
    # 20 dB under the take's own loud level is not voice — relative, so a quiet shoot is not all silence and
    # a hot one is not all speech — but with an absolute floor under it, or a dead track reads as 100% speech
    # (its own percentile is room tone, and everything clears a tenth of that).
    active = env > max(0.1 * float(np.percentile(env, 90)), 0.001 * 32768)
    win = max(1, int(round(length / hop)))
    def speech(t):
        # over the WHOLE window: a window straddling the voice's end scored only the seconds it had, so 1 s of
        # speech read 100% (2026-10-13); seconds past the end count as silence
        lo = int(round(t / hop))
        return float(active[lo:lo + win].sum()) / win
    reach = span / (2 * (n - 1))
    out = []
    for t in even:
        cands = [min(max(t + d * hop, 0.0), span)
                 for d in range(-int(reach / hop), int(reach / hop) + 1)]
        # Ties go to the evenly-spread point: on a take that talks throughout, every candidate scores 1.0
        # and a plain max() slides every window to the near edge of its slot, bunching the probes.
        best = max(cands, key=lambda c: (speech(c), -abs(c - t)))
        if speech(best) >= floor:
            out.append((best, speech(best)))
        else:
            print(f'  slot at {t + length / 2:8.1f}s: {speech(best) * 100:.0f}% speech at best, under the {floor:.0%} '
                  f'floor — skipped (nothing to correlate there)')
    return out


def lag_at(cam, audio, t0, length, crop, fps, max_lag):
    """-> (lag in frames, correlation at the peak, how far that peak stands above the rest of the curve, why it was
    skipped or None).

    The third number is the one to trust of the two. The correlation itself is small even on a good window
    (two coarse envelopes, not two copies of a signal) and its size says little: the window that disagreed
    most with the others, on the take this was calibrated against, carried the HIGHEST correlation of the
    nine. How far the peak stands above its own curve at least measures whether one lag beat the rest.
    """
    m, v = mouth(cam, t0, length, crop, fps), voice(audio, t0, length, fps)
    n = min(len(m), len(v))
    if n < COVER * length * fps:
        # past the end of the voice (or the picture): a window with 0.8 s of audio in it still correlated 20 frames
        # and carried the HIGHEST weight of the fit (2026-10-13)
        return None, 0.0, 0.0, f'only {n / fps:.1f} s of its {length:.0f} s decoded'
    m, v = m[:n], v[:n]
    if m.std() < 1e-9 or v.std() < 1e-9:
        return None, 0.0, 0.0, None                       # a still frame or silence: nothing to correlate
    m = (m - m.mean()) / m.std(); v = (v - v.mean()) / v.std()
    L = np.arange(-max_lag, max_lag + 1)
    sc = np.array([np.dot(v[max(0, -l):n - max(0, l)], m[max(0, l):n - max(0, -l)]) / (n - abs(l)) for l in L])
    i = int(sc.argmax())
    z = float((sc[i] - sc.mean()) / (sc.std() or 1.0))
    if i in (0, len(L) - 1):
        return None, float(sc[i]), z, None   # pinned at the edge of the search: not a peak, widen --max-lag
    d = 0.0
    if (sc[i - 1] - 2 * sc[i] + sc[i + 1]) != 0:
        d = 0.5 * (sc[i - 1] - sc[i + 1]) / (sc[i - 1] - 2 * sc[i] + sc[i + 1])   # parabolic peak: sub-frame
    return float(L[i] + d), float(sc[i]), z, None


def slip_frames(lags, ok):
    """-> (whole-frame V1 slip, the median lag, the worst window's distance from the slip). The residual (median - slip)
    is at most 0.3 frame of sound leading the lips and otherwise leaves the sound late (rough-cut § Lip sync at intake)."""
    med = float(np.median(lags))
    n = 0 if ok else math.ceil(med - 0.3)
    return n, med, float(max(abs(x - n) for x in lags))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cam'); ap.add_argument('--audio', required=True)
    ap.add_argument('--fps', type=float); ap.add_argument('--mouth-crop', default=DEFAULT_CROP)
    ap.add_argument('--windows', type=int, default=9); ap.add_argument('--window-len', type=float, default=120.0)
    ap.add_argument('--max-lag', type=int, default=12); ap.add_argument('--min-speech', type=float, default=0.35)
    ap.add_argument('--min-peak', type=float, default=0.0); ap.add_argument('--json', action='store_true')
    ap.add_argument('--slip-out', metavar='PATH')
    a = ap.parse_args()
    cam_fps, cam_dur = probe(a.cam)
    _, aud_dur = probe(a.audio)
    fps = a.fps or cam_fps
    if not fps:
        sys.exit(f'✗ cannot read a frame rate from {a.cam}; pass --fps')
    dur = min(cam_dur, aud_dur) if aud_dur else cam_dur
    if dur <= 0:
        sys.exit(f'✗ ffprobe reports no duration for {a.cam}: every window would start at 0 and the drift fit '
                 f'would be meaningless. Remux the take, or measure a trimmed copy.')
    length = min(a.window_len, max(10.0, dur / 4))
    span = max(0.0, dur - length)
    print(f'{a.cam} vs {a.audio}  ·  {dur:.0f}s @ {fps:.3f} fps  ·  {a.windows} windows of {length:.0f}s'
          f'  ·  mouth crop {a.mouth_crop}')
    env = envelope(a.audio, dur)
    if env is None:
        print(f'⚠ no voice envelope decoded from {a.audio}: probing evenly, so a window may land on silence')
    starts = place_windows(env, 1.0, span, length, a.windows, a.min_speech)
    pts, weak_peaks = [], 0
    for t0, sp in starts:
        lag, r, z, why = lag_at(a.cam, a.audio, t0, length, a.mouth_crop, fps, a.max_lag)
        centre = t0 + length / 2
        if why:
            print(f'  src {centre:8.1f}s: {why} — skipped')
            continue
        if lag is None:
            print(f'  src {centre:8.1f}s: no peak inside ±{a.max_lag} frames (r={r:.3f}) — skipped')
            continue
        line = (f'  src {centre:8.1f}s: lag {lag:+6.2f} fr ({lag / fps * 1000:+5.0f} ms)  r={r:.3f}  peak {z:4.1f}σ'
                f'  speech {sp:.0%}')
        if z < a.min_peak:                    # opt-in, and only when the take's own table splits cleanly
            print(line + f' — DROPPED, peak under the {a.min_peak:.1f}σ asked for')
            weak_peaks += 1
            continue
        print(line)
        pts.append((centre, lag, z))
    if len(pts) < 2:                          # no line at all: UNMEASURED, never exit 1 (FAIL, with a slip to apply)
        print(f'⚠ UNMEASURED: fewer than two usable windows ({weak_peaks} dropped on --min-peak): widen --window-len, '
              f'point --mouth-crop at the mouth (it is printed above), or lower --min-peak and read the table by hand')
        return 2
    t, l, w = (np.array(x) for x in zip(*pts))
    slope, base = np.polyfit(t, l, 1, w=w)                # weighted by peak strength: a soft peak steers less
    ends = [base, base + slope * dur]
    rms = float(np.sqrt((((base + slope * t) - l) ** 2).mean()))
    worst = max(abs(x) for x in list(l) + ends)
    # A WEAK MEASUREMENT GETS NO VERDICT. Every window returns a peak, so a crop that is not on the mouth
    # still produces a confident-looking line — and a FAIL hands back a slip formula that would move every
    # clip by a number nothing corroborates. Windows that disagree with their own fit, or a take where most
    # of them had no peak at all, are reported as unmeasured rather than answered. Two windows are never enough:
    # the line passes through both points, so the residual is 0 whatever they say and they cannot disagree (a
    # same-file self-test, true lag 0, read "FAIL: off by up to 6.31 frames" off two windows, 2026-10-13).
    two_points = len(pts) < 3
    weak = rms > 1.0 or two_points or len(pts) < len(starts) // 2
    ok = worst < 1.0 and not weak
    print(f'fit: lag_frames = {base:+.3f} + {slope * 1000:.4f} per 1000 s   '
          f'(0 s: {ends[0]:+.2f} fr · {dur:.0f} s: {ends[1]:+.2f} fr)   residual {rms:.2f} fr rms')
    if weak and two_points:
        print(f'⚠ UNMEASURED: only {len(pts)} of {len(starts)} windows measured, and a line through two points fits '
              f'them exactly whatever they say, so nothing corroborates the line above and nothing should be slipped by it.')
    elif weak:
        print(f'⚠ UNMEASURED: {len(pts)} of {len(starts)} windows measured and they do not agree (residual {rms:.2f} fr), '
              f'so the line above is not an answer and nothing should be slipped by it.')
        print(f'  Point --mouth-crop at the mouth — the default {DEFAULT_CROP} is a generic centre band, and on a wide '
              f'framing it correlates head and background motion instead — then raise --window-len and re-run.')
    elif ok:
        print(f'✓ PASS: within {worst:.2f} frames across the take — lay the angle as cut')
    else:
        print(f'✗ FAIL: off by up to {worst:.2f} frames, drifting {abs(ends[1] - ends[0]):.2f} fr across the take.')
        print(f'  Slip each camera clip LATER in its source by its own lag: lag_frames = {base:+.4f} '
              f'+ {slope:.8f} * src_seconds  (timeline start/end unchanged), then prove it on a timeline export.')
    if a.slip_out:
        # THE INTAKE STEP (rough-cut § Lip sync at intake): the replay lays V1 this many frames LATER than A1, so a camera
        # whose audio runs early is in sync from the first lay (premiere-bridge.mjs replay; live-edl.py reads it back)
        # the MEDIAN window (a few windows land on a weak peak), rounded so the residual leaves the sound LATE: viewers catch
        # sound that LEADS the lips at about 45 ms but take sound that trails them up to about 125 ms (ITU-R BT.1359), so
        # at most 0.3 frame of lead is left, never half a frame. On the 2026-10-02 OBS takes the medians read 4.44,
        # 4.62 and 4.86 frames (-> 5); 4 was laid by hand and is within the same half frame (your-job).
        # One number is refused only when a WINDOW sits more than 1.5 frames off it: those takes fit drifts of -1.5 and +1.2
        # frames (opposite signs, one device: fit noise, residual 0.3), while a screen recorder's facecam that really
        # drifts ran +1.9 to +8.3 (2026-09-19)
        n, med, spread = slip_frames(list(l), ok)
        if weak or spread > 1.5:
            print(f'✗ --slip-out: nothing written to {a.slip_out}: '
                  + ('the measurement is UNMEASURED' if weak else f'a window sits {spread:.2f} frames off {n:+d}, so one whole-frame '
                     f'slip cannot fix the take (it drifts): slip each clip by its own lag, the line above'))
        else:
            doc = dict(v1_frames=n, measured=dict(cam=a.cam, crop=a.mouth_crop, fps=round(fps, 6),
                                                  lags=[round(float(x), 2) for x in l], median=round(med, 3),
                                                  worst_window_after=round(spread, 2)),
                       why=('in sync within a frame' if n == 0 else
                            f'the audio runs {abs(n)} frame(s) {"EARLY" if n > 0 else "LATE"} against the picture; V1 is laid {n:+d} '
                            f'frame(s) against A1 so the picture meets the sound. The EDL (cuts.json) stays the AUDIO cut.'))
            with open(a.slip_out, 'w', encoding='utf-8') as f:
                json.dump(doc, f, indent=1)
            print(f'→ {a.slip_out}: v1_frames {n}')
    if a.json:
        print(json.dumps(dict(cam=a.cam, audio=a.audio, fps=fps, duration=dur, crop=a.mouth_crop,
                              windows=[dict(centre=round(c, 3), lag_frames=round(x, 3), peak_sigma=round(zz, 2))
                                       for c, x, zz in pts],
                              fit=dict(base_frames=round(float(base), 4), frames_per_second=round(float(slope), 8),
                                       at_start=round(float(ends[0]), 3), at_end=round(float(ends[1]), 3),
                                       residual_frames=round(rms, 3)),
                              verdict='UNMEASURED' if weak else 'PASS' if ok else 'FAIL'), indent=1))
    return 2 if weak else 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
