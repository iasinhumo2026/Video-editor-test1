# /// script
# requires-python = ">=3.10"
# dependencies = ["opencv-python-headless", "numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""
chin-line.py — measure the chin line of a talking-head cut. Measured, not guessed.

Every overlay that shares the frame with the face lives BELOW the chin, and the
only honest way to know where the chin is is to look. This sweeps the video,
detects the face on each sample (OpenCV YuNet, model vendored in assets/models/)
and reports the LOWEST jaw line it finds — the worst case a fixed layout band has
to clear. The YuNet box bottom sits on the jaw, so it is the chin proxy.

ONE SAMPLE IS NEVER THE FLOOR (§ THE LOW BAND). The subject is the biggest CONFIDENT
face, not the biggest box and not the top score alone; and a chin no other sample
corroborates is re-sampled on the source frames either side before it is believed —
it is dropped and named only when those frames disagree with it too.

Feeds the youtube/default text-animation band (presets/youtube/default/text-animation/build.py
TOP_MIN) and any hand-authored overlay that has to sit under the face. Re-derive
per shoot: a tighter or wider frame moves the chin by 100px+.

It also reports the HEAD'S HORIZONTAL EXTENT (the face box widened by an ear allowance,
worst case over the window) and the side-callout zones that leave it alone (the user,
2026-09-10: a side card never covers the ear; margin to the subject SUBJECT px, to the
frame edge EDGE px; the card goes on the side with more room and takes the room's width).
Usage:
  uv run workflows/chin-line.py projects/<job>/outputs/<job>.mp4
  uv run workflows/chin-line.py <video> --from 43.3 --to 47.0   # one graphic's window
  uv run workflows/chin-line.py <raw> --edl projects/<job>/transcript/cuts.json --from 46.6 --to 52.7 --step 0.1
        # app-finish job (no flat cut): --from/--to are TIMELINE seconds, mapped onto the raw through the EDL
  uv run workflows/chin-line.py <video> --json                  # machine-readable
  uv run workflows/chin-line.py <video> --out chin.json         # durable: a truncated pipe loses it
  uv run workflows/chin-line.py <video> --annotate out.png      # eyeball the worst frame
  uv run workflows/chin-line.py <video> --full-res              # detect on full-size frames (slow; parity check)
"""
import argparse, json, os, statistics, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

# Windows consoles/pipes default to cp1252 and cannot encode the status glyphs below.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(REPO, "assets", "models", "face_detection_yunet_2023mar.onnx")
GAP = 70          # the breathing room a layout band leaves under the worst chin
STEP = 0.5        # sweep interval, seconds
EAR = 0.20        # ear allowance each side, as a fraction of the YuNet face-box width (the box stops at the cheek)
SUBJECT = 60      # px between a side callout and the head, ears included (default-overlay-style.md § Placement)
EDGE = 80         # px between a side callout and the frame edge (same home)
DETECT_W = 960    # faces are detected on a copy this wide and scaled back — a 4K sweep is ~30x cheaper
MAD_K = 6         # a chin this many MADs off the window's median is suspect
MIN_AGREE = 1     # ...and a suspect chin needs at least this many other samples within the gap to stand
RECHECK = 3       # ...or agreement from the source frames this far either side of it (see recheck())
SCORE_MARGIN = 0.10   # how far under the best score a box can be and still count as the subject


def outliers(vals, k=MAD_K, gap=GAP):
    """Split a sample series into (kept indices, dropped indices).

    A value is a mis-detection only when it sits more than k MADs off the window's median AND no
    other sample corroborates it within gap px. One detector call is not a measurement — a single
    bad box once put a floor 500px low — but a real lean is on several frames in a row, so the
    median test alone would throw it away.
    """
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals]) or 1.0
    keep, drop = [], []
    for i, v in enumerate(vals):
        agree = sum(1 for j, o in enumerate(vals) if j != i and abs(o - v) <= gap)
        (drop if abs(v - med) > k * mad and agree < MIN_AGREE else keep).append(i)
    return keep, drop


def subject(faces, margin=SCORE_MARGIN):
    """THE SUBJECT IS THE BIGGEST CONFIDENT FACE — neither the biggest box nor the top score alone.

    Two different decoys share a talking-head frame and each rule on its own falls for one of them.
    A print, a poster or a screen in the room is a small but genuinely face-like box that outranks
    the speaker the moment his score dips, so the top score alone is not enough. But YuNet also
    throws BIG low-score phantoms over a shoulder or the mic arm — measured on a real take, a
    604k-px box at score 0.63 against his real 296k at 0.94 — and those beat him on area, which puts
    the chin 800px low. So: keep every face within `margin` of the best score, then take the largest
    of those. A lone face is unaffected, which is the usual case.
    """
    top = max(float(f[14]) for f in faces)
    return max([f for f in faces if float(f[14]) >= top - margin], key=lambda r: r[2] * r[3])


def detect_size(w, h):
    """YuNet's input size: a talking head is found at 960px wide, and the decode is what costs."""
    if w <= DETECT_W:
        return w, h
    return DETECT_W, max(2, round(h * DETECT_W / w / 2) * 2)


def spans(times, step):
    """Group (timeline, source) samples into runs contiguous in the SOURCE — one decode pass each."""
    runs = []
    for s in times:
        if runs and abs(s[1] - (runs[-1][-1][1] + step)) < 1e-3:
            runs[-1].append(s)
        else:
            runs.append([s])
    return runs


def src_fps(video):
    """The source frame rate — the sample grid is stepped in WHOLE SOURCE FRAMES (see grid())."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=r_frame_rate", "-of", "default=nw=1:nk=1", video],
                         capture_output=True, text=True, check=True).stdout.strip()
    num, _, den = out.splitlines()[0].partition("/") if out else ("", "", "")
    try:
        fps = float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return None
    return fps if fps > 0 else None


def grid(times, step, fps):
    """Plan the sweep: runs of (timeline label, source time) at the instants the decoder REACHES.

    A LABEL IS A PROMISE ABOUT A FRAME. ffmpeg's `fps` filter snaps to a grid anchored at the
    source's own zero, not at the seek point, so a run asked for at 3.3s came back at 3.5s with
    every label off by up to half a step — `at`, the dropped times and the frame `--annotate` draws
    on all pointed somewhere else. So the grid steps in whole source frames from the seek point
    (`select=not(mod(n,stride))`, which anchors on the first decoded frame) and the labels say where
    the samples actually land. fps None keeps the asked-for times for the --full-res path, whose
    per-sample seeks are exact.
    """
    stride = max(1, round(step * fps)) if fps else 1
    eff = stride / fps if fps else step
    runs = []
    for run in spans(times, step):
        tl0, st0 = run[0]
        # as many samples as were asked for (rounding, not flooring: a 0.5s step on 23.976fps
        # footage is really 0.5005s, and flooring drops the last sample of every short run), but
        # never more, so the sweep cannot walk out of its EDL segment.
        n = min(len(run), int((run[-1][1] - st0) / eff + 0.5) + 1)
        runs.append([(round(tl0 + k * eff, 3), st0 + k * eff) for k in range(n)])
    return runs, stride


def frames(video, runs, stride, dw, dh, full_res=False):
    """Yield (timeline t, BGR frame) for every planned sample.

    One ffmpeg pipe per contiguous run at the detect size, not one seek + PNG + imread per sample:
    a 4K sweep that ran past the 600s tool timeout finishes in seconds. --full-res keeps the old
    per-sample path for a parity check.
    """
    import numpy as np
    if full_res:
        from cv2_io import imread    # never cv2.imread: a temp dir under a non-ASCII user name (cv2_io.py)
        png = os.path.join(tempfile.mkdtemp(), "f.png")
        for run in runs:
            for tl, st in run:
                subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{st}", "-i", video,
                                "-frames:v", "1", "-y", png], check=True)
                yield tl, st, imread(png)
        return
    size = dw * dh * 3
    for run in runs:
        # passthrough sync is load-bearing: without it the muxer re-pads `select` back up to a constant rate
        # and every frame in the run comes back as a copy of the first one.
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{run[0][1]}", "-i", video,
                              "-vf", f"select=not(mod(n\\,{stride})),scale={dw}:{dh}",
                              *passthrough(), "-frames:v", str(len(run)),
                              "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
        for tl, st in run:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield tl, st, np.frombuffer(buf, np.uint8).reshape(dh, dw, 3)
        p.stdout.close()
        p.wait()


def sweep(video, runs, stride, det, dw, dh, sx, sy, full_res=False):
    """Detect the subject on every planned frame; measurements come back in SOURCE pixels."""
    samples, misses = [], 0
    for tl, st, img in frames(video, runs, stride, dw, dh, full_res):
        _, faces = det.detect(img)
        if faces is None or len(faces) == 0:
            misses += 1
            continue
        f = subject(faces)
        samples.append({"t": tl, "src": st, "score": round(float(f[14]), 3),
                        "chin": round(float(f[1] + f[3]) * sy), "top": float(f[1]) * sy,
                        "left": float(f[0]) * sx, "right": float(f[0] + f[2]) * sx, "w": float(f[2]) * sx})
    return samples, misses


def recheck(video, sample, det, dw, dh, sx, sy, fps, gap):
    """Is this lone low chin a bad box, or a real lean? Look at the frames either side of it.

    Dropping an uncorroborated sample fixes the floor that came back 500px LOW, but it opens the
    same bug in the other direction and that one is worse: he ducks toward the mic for half a
    second, the lean lands on ONE sample at a 0.5s step, nothing corroborates it, and the floor
    comes back 200px HIGH — a band sitting on his chin, and nothing says so. So no sample is
    dropped on the statistics alone: it is re-sampled at the source frame rate either side, and it
    goes back if those frames agree with it.
    """
    fine = [(round(sample["src"] + k / fps, 3), sample["src"] + k / fps)
            for k in range(-RECHECK, RECHECK + 1) if k and sample["src"] + k / fps >= 0]
    near, _ = sweep(video, *grid(fine, 1 / fps, fps), det, dw, dh, sx, sy)
    return any(abs(n["chin"] - sample["chin"]) <= gap for n in near)


def edl_map(path, video):
    """timeline seconds -> source seconds of `video` through a cuts.json (segments' start/end are source times), or
    None where the timeline plays another clip. A meme insert's own 0-4.2 s used to map onto the main raw, so a window
    over the meme sampled the raw's opening and widened the head (face-frame.py's timeline_to_source, 2026-10-13). A
    lip-sync re-take names the raw as its clip and runs on the raw's clock, so it maps onto the raw."""
    c = json.load(open(path, encoding="utf-8"))
    segs = c.get("segments") if isinstance(c, dict) else c
    name = os.path.basename(video)
    spans, t = [], 0.0
    for sg in segs:
        d = float(sg["end"]) - float(sg["start"])
        other = sg.get("clip") and os.path.basename(sg["clip"]) != name
        spans.append((t, t + d, None if other else float(sg["start"])))
        t += d
    def f(tl):
        for a, b, s0 in spans:
            if a <= tl < b:
                return None if s0 is None else s0 + (tl - a)
        return None
    return f


def probe(video):
    """(width, height, duration) AS DECODED. ffmpeg auto-rotates before any filter, so an iPhone portrait take coded
    1920x1080 with a -90 display matrix arrives 1080x1920. Read as coded, every frame was squashed into 960x540: 292 of
    321 samples found no face and the rest were measured in a frame that does not exist (chin "y727" in a 1080x1920
    picture, wt-long, 2026-10-13). Older ffprobe reports the turn as a `rotate` tag (hero-frame.py's raw_size)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,duration:stream_side_data=rotation:stream_tags=rotate:format=duration", "-of", "json", video],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    rot = next((sd["rotation"] for sd in s.get("side_data_list", []) if "rotation" in sd),
               s.get("tags", {}).get("rotate", 0))
    w, h = int(s["width"]), int(s["height"])
    dur = float(s.get("duration") or d.get("format", {}).get("duration"))
    return (h, w, dur) if round(float(rot)) % 180 else (w, h, dur)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--step", type=float, default=STEP)
    ap.add_argument("--gap", type=float, default=GAP)
    ap.add_argument("--edl", metavar="CUTS.JSON", help="--from/--to are timeline seconds; map them onto the video through this EDL")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", metavar="FILE", help="also write the JSON to FILE (stdout can be truncated)")
    ap.add_argument("--annotate", metavar="OUT.PNG")
    ap.add_argument("--full-res", action="store_true", help="detect on full-size frames, one decode per sample (the old, much slower path)")
    a = ap.parse_args()

    import cv2
    from cv2_io import face_detector, imread, imwrite
    w, h, dur = probe(a.video)
    t1 = a.t1 if a.t1 is not None else dur
    to_src = edl_map(a.edl, a.video) if a.edl else (lambda x: x)

    times, t = [], a.t0 + (0.05 if a.edl else 0.3)
    while t < t1:
        st = to_src(t)
        if st is not None:
            times.append((round(t, 2), st))
        t += a.step
    if not times:
        sys.exit("the window maps to nothing in the video — check --from/--to (and the EDL)")

    # detection runs on a downscaled copy; every measurement is scaled back into SOURCE pixels,
    # which is what the plan cell's `head` and graphics-qa.py's frame normalisation expect.
    dw, dh = (w, h) if a.full_res else detect_size(w, h)
    det = face_detector(MODEL, (dw, dh), 0.6, 0.3, 5000)
    det.setInputSize((dw, dh))
    sx, sy = w / dw, h / dh
    fps = None if a.full_res else src_fps(a.video)
    if fps is None and not a.full_res:
        # the fast path steps the sweep in whole source frames, so without a frame rate it would
        # sample consecutive frames and label them a step apart — a silently wrong measurement.
        sys.exit(f"no usable frame rate on {os.path.basename(a.video)} (r_frame_rate unreadable) — "
                 "re-run with --full-res, which seeks each sample itself")
    runs, stride = grid(times, a.step, fps)
    planned = sum(len(r) for r in runs)

    samples, misses = sweep(a.video, runs, stride, det, dw, dh, sx, sy, a.full_res)
    if not samples:
        sys.exit("no face detected anywhere in the window — measure by hand")

    undecoded = planned - len(samples) - misses   # a run that ended early: sampled fewer frames than asked
    keep, drop = outliers([s["chin"] for s in samples], gap=a.gap)
    if fps:   # no sample is dropped on the statistics alone — prove each one on its own neighbours
        rescued = {i for i in drop if recheck(a.video, samples[i], det, dw, dh, sx, sy, fps, a.gap)}
        for i in rescued:
            samples[i]["rescued"] = True
        keep, drop = sorted(keep + list(rescued)), [i for i in drop if i not in rescued]
    kept = [samples[i] for i in keep]
    dropped = [{"t": samples[i]["t"], "y": samples[i]["chin"], "score": samples[i]["score"]} for i in drop]

    low = max(kept, key=lambda s: s["chin"])
    lowest, at = low["chin"], low["t"]
    corroborating = sum(1 for s in kept if s is not low and abs(s["chin"] - lowest) <= a.gap)
    med = statistics.median([s["chin"] for s in kept])
    floor = round(lowest + a.gap)

    # the head, worst case over the SURVIVING samples: leftmost box edge, rightmost box edge, each widened by the ear
    ear = round(EAR * statistics.median(s["w"] for s in kept))
    hl_box = min(kept, key=lambda s: s["left"]); hr_box = max(kept, key=lambda s: s["right"])
    head_left, head_right = round(hl_box["left"] - ear), round(hr_box["right"] + ear)
    head_top = round(min(s["top"] for s in kept))
    zone_l = [EDGE, head_left - SUBJECT]; zone_r = [head_right + SUBJECT, w - EDGE]
    room_l, room_r = zone_l[1] - zone_l[0], zone_r[1] - zone_r[0]
    side = "L" if room_l >= room_r else "R"
    head = {"left": head_left, "right": head_right, "top": head_top,
            "face_left": round(hl_box["left"]), "face_right": round(hr_box["right"]), "ear_px": ear,
            "left_at": hl_box["t"], "right_at": hr_box["t"]}
    callout = {"L": zone_l, "R": zone_r, "room_left": room_l, "room_right": room_r, "side": side,
               "subject_margin": SUBJECT, "edge_margin": EDGE}

    if a.annotate:
        png = os.path.join(tempfile.mkdtemp(), "f.png")   # the worst frame, full size, for the eye
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{to_src(at)}", "-i", a.video,
                        "-frames:v", "1", "-y", png], check=True)
        img = imread(png)
        cv2.line(img, (0, lowest), (w, lowest), (0, 0, 255), 3)
        cv2.line(img, (0, floor), (w, floor), (0, 255, 0), 3)
        cv2.rectangle(img, (head_left, head_top), (head_right, lowest), (0, 200, 255), 3)
        for z in (zone_l, zone_r):
            cv2.rectangle(img, (z[0], 150), (z[1], 710), (255, 160, 0), 3)
        cv2.putText(img, f"chin {lowest}", (24, lowest - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3)
        cv2.putText(img, f"floor {floor}", (24, floor - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3)
        imwrite(a.annotate, img)

    payload = {"lowest_chin": lowest, "at": at, "median_chin": med,
               "floor": floor, "gap": a.gap, "samples": len(kept),
               "corroborating": corroborating, "rescued": bool(low.get("rescued")), "dropped": dropped,
               "score_min": min(s["score"] for s in kept),
               "misses": misses, "undecoded": undecoded, "frame": [w, h], "detect_frame": [dw, dh],
               "head": head, "callout": callout,
               "window": [a.t0, t1], "timeline": bool(a.edl)}
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
    if a.json:
        print(json.dumps(payload, indent=2))
        return
    print(f"samples {len(kept)} (+{misses} no-face, {len(dropped)} dropped"
          f"{f', {undecoded} undecoded' if undecoded else ''})   frame {w}x{h}"
          f"   detected at {dw}x{dh}   worst score {min(s['score'] for s in kept):.2f}")
    print(f"median chin  y{med:.0f}")
    proof = ("proven a real lean on the source frames either side" if low.get("rescued") else
             f"{corroborating} other sample{'' if corroborating == 1 else 's'} within {a.gap:.0f}px corroborate it")
    print(f"LOWEST chin  y{lowest}  at t={at}s   ← the worst case a band must clear   ({proof})")
    if dropped:
        shown = ", ".join(f"y{d['y']} at t={d['t']}s (score {d['score']})" for d in dropped[:6])
        print(f"  dropped as mis-detections, no agreement on the frames either side: {shown}"
              + (f" … +{len(dropped) - 6} more" if len(dropped) > 6 else "")
              + "   ← re-run over one with --from/--to --annotate to see it")
    print(f"→ overlay floor  y{floor}  (chin + {a.gap:.0f}px)")
    print(f"HEAD incl. ears  x{head_left}–{head_right}  (face box {head['face_left']}–{head['face_right']}, ear +{ear}px; "
          f"leftmost at t={hl_box['t']}s, rightmost at t={hr_box['t']}s)")
    print(f"→ side callouts  L x{zone_l[0]}–{zone_l[1]} ({room_l}px wide) · R x{zone_r[0]}–{zone_r[1]} ({room_r}px wide)"
          f"  → more room on the {'LEFT' if side == 'L' else 'RIGHT'}   ({SUBJECT}px off the head, {EDGE}px off the edge)")
    if a.annotate:
        print(f"  annotated worst frame: {a.annotate}")
    if a.out:
        print(f"  json: {a.out}")


if __name__ == "__main__":
    main()
