#!/usr/bin/env python3
"""audio-qa.py <job_dir> — post-splice audio self-check (advisory, never fails the build).

Scans the freshly spliced output for the two artifact classes that have actually shipped:
  1. JOINT CLICKS — step discontinuities at segment butt-joins. The splice applies 5 ms
     edge declick fades, so any joint that still spikes means a regression (or a source
     transient landing exactly on a boundary — inspect by ear).
  2. LIMITER PRESSURE — how hard the -6 dBFS brickwall is working. A static gain that
     drives sustained speech into the ceiling ducks the surrounding audio (5 ms attack /
     50 ms release) — audible as tiny "swallows" on stressed words. If pressure is high,
     the gain came from voice-gain.py's -17 LUFS target, which deliberately runs the
     limiter hard (2026-09-03); only act on this if it is audible, with AMPLIFY_DB
     two under the measured number, and compare by ear.
  3. LOUDNESS against the -17 LUFS target: a render more than 2.5 LU under it lost gain on the way.

Stdlib only (no numpy). Reads outputs/<job>.mp4 + transcript/cuts.json.
"""
import array, json, math, os, statistics, subprocess, sys
# Windows consoles/pipes default to cp1252, which can't encode the ⚠/✓ glyphs in this
# script's status lines: a cosmetic print must never kill a pipeline step (it did once,
# 2026-08-13, mid-splice on a real Windows job). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

SR = 48000
job_dir = os.path.abspath(sys.argv[1])
job = os.path.basename(job_dir)
out_mp4 = os.path.join(job_dir, "outputs", f"{job}.mp4")
cuts_p = os.path.join(job_dir, "transcript", "cuts.json")
if not (os.path.exists(out_mp4) and os.path.exists(cuts_p)):
    print("[audio-qa] missing output or cuts.json — skipped"); sys.exit(0)

# decode left channel as f32 (pan, NOT -ac 1: default downmix adds +3 dB and skews levels)
raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", out_mp4, "-vn", "-af", "pan=mono|c0=c0",
     "-f", "f32le", "-"], capture_output=True).stdout
x = array.array("f"); x.frombytes(raw)
n = len(x)
if n < SR:
    print("[audio-qa] output too short — skipped"); sys.exit(0)

segs = json.load(open(cuts_p, encoding="utf-8"))["segments"]
joints, t = [], 0.0
for s in segs[:-1]:
    t += float(s["end"]) - float(s["start"])
    joints.append(t)
expected = t + float(segs[-1]["end"]) - float(segs[-1]["start"])

# ── 0. timeline integrity ──
# decoded length may exceed the EDL sum by up to one AAC frame (1024 samples) of encoder
# tail padding — benign. Anything beyond that, or any internal zero-run at a joint, means
# concat padded silence (the frame-snap regression).
actual = n / SR
slack = (actual - expected) * SR
gaps = []
for j in joints:
    c = int(j * SR)
    run = mx = 0
    for i in range(max(0, c - 2400), min(n, c + 2400)):
        run = run + 1 if x[i] == 0.0 else 0
        mx = max(mx, run)
    if mx >= 48:
        gaps.append((j, mx))
if gaps or slack < -240 or slack > 1100:
    print(f"[audio-qa] ⚠ TIMELINE STRETCH: audio {actual:.3f}s vs EDL sum {expected:.3f}s "
          f"({(actual-expected)*1000:+.0f} ms); zero-gaps at joints: "
          + (", ".join(f"{j:.2f}s ({m} smp)" for j, m in gaps) if gaps else "none")
          + " — check frame-grid snap")
else:
    print(f"[audio-qa] ✓ timeline exact: audio = EDL sum {(actual-expected)*1000:+.1f} ms "
          f"(≤1 AAC frame tail padding), no joint gaps")

# ── 1. joint click scan: max |diff| in ±10 ms vs local median |diff| in ±150 ms ──
bad = []
for j in joints:
    c = int(j * SR)
    if not (SR // 2 < c < n - SR // 2):
        continue
    win = [abs(x[i] - x[i - 1]) for i in range(c - 480, c + 480)]
    ctx = [abs(x[i] - x[i - 1]) for i in range(c - 7200, c - 960)] + \
          [abs(x[i] - x[i - 1]) for i in range(c + 960, c + 7200)]
    med = statistics.median(ctx) or 1e-9
    mx = max(win)
    if mx / med > 40 and mx > 0.01:
        bad.append((j, mx / med))
if bad:
    print(f"[audio-qa] ⚠ JOINT CLICKS at: " +
          ", ".join(f"{j:.2f}s (x{r:.0f})" for j, r in bad) +
          " — crossfades should prevent this; inspect these cuts by ear")
else:
    print(f"[audio-qa] ✓ joints clean ({len(joints)} checked)")

# ── 1b. ambience continuity: room tone must not dip through a joint ──
# (fading joint edges to silence instead of crossfading punches an audible ~20 ms
#  room-tone hole — measured 8-13 dB dips; this catches that regression)
def rms(seg):
    return math.sqrt(sum(v * v for v in seg) / max(1, len(seg)))
holes = []
for j in joints:
    c = int(j * SR)
    if not (SR // 2 < c < n - SR // 2):
        continue
    at = rms(x[c - 480:c + 720])
    # ref = the quietest natural ambience nearby (10th percentile of 10 ms RMS over ±300 ms)
    # — comparing against adjacent windows flags natural speech decay/onset as a "hole"
    wins = sorted(rms(x[c + k * 480:c + (k + 1) * 480]) for k in range(-30, 30))
    ref = wins[max(0, len(wins) // 10)]
    if ref > 1e-6 and 20 * math.log10(max(at, 1e-9) / ref) < -8:
        holes.append((j, 20 * math.log10(max(at, 1e-9) / ref)))
if holes:
    print(f"[audio-qa] ⚠ AMBIENCE HOLES at: " +
          ", ".join(f"{j:.2f}s ({d:.0f} dB)" for j, d in holes) +
          " — joint audio dips through the cut; crossfade regression")
else:
    print(f"[audio-qa] ✓ ambience continuous through all joints")

# ── 2. limiter pressure: ceiling-pinned density + engagement events ──
CEIL = 0.4995
pinned = [i for i, v in enumerate(x) if abs(v) >= CEIL]
events, last = 0, -10 ** 9
for i in pinned:
    if i - last > SR // 20:
        events += 1
    last = i
pct = 100 * len(pinned) / n
peak = max(abs(v) for v in x)
rms = math.sqrt(sum(v * v for v in x) / n)
print(f"[audio-qa] levels: mean {20*math.log10(rms):.1f} dBFS · peak {20*math.log10(peak):.2f} dBFS"
      f" · limiter pinned {len(pinned)} samples ({pct:.4f}%) in {events} events")
if pct > 0.01 or events > 250:
    print(f"[audio-qa] ⚠ LIMITER PRESSURE high — peaky source at this gain; ducking artifacts likely on"
          f" stressed words. The -17 LUFS target runs the limiter hard on purpose; if it is AUDIBLE, report it: a named AMPLIFY_DB is the creator's call, announced and recorded in RUN.md as a deviation (LANES.md § step 3)")
else:
    print("[audio-qa] ✓ limiter engagement in the transparent range (peaks kissing)")

# ── 3. loudness against the target: the measured gain puts kept speech at -17 LUFS pre-limiter (voice-gain.py's
# TARGET_LUFS), so the render reads that less what the limiter takes (about a LU) and the whole-dB rounding. A gain
# the render lost on the way (a mono raw upmixed 3 dB down a channel shipped 3 LU under, 2026-10-13) reads well under.
TARGET, SHORT = -17.0, 2.5
r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", out_mp4, "-vn", "-af", "ebur128=framelog=quiet",
                    "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
lufs = [float(l.split()[1]) for l in r.stderr.splitlines() if l.strip().startswith("I:") and "LUFS" in l]
if not lufs:
    print("[audio-qa] ⚠ loudness did not measure (ebur128 printed no integrated reading)")
elif lufs[-1] < TARGET - SHORT:
    print(f"[audio-qa] ⚠ LOUDNESS {lufs[-1]:.1f} LUFS integrated, {TARGET - lufs[-1]:.1f} LU under the {TARGET:g} LUFS "
          "target: the render lost gain the measurement gave it (or AMPLIFY_DB named less); find where before shipping")
else:
    print(f"[audio-qa] ✓ loudness {lufs[-1]:.1f} LUFS integrated (target {TARGET:g} pre-limiter)")
