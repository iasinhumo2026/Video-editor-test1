# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["mediapipe==0.10.14", "opencv-python-headless"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""
face-frame.py — compute the Talking Head Explainer's face framing. Measured, not guessed.

LOCKED framing standard (short-form talking-head explainer, graphics top / face
bottom): in split the median hair top sits 100px below the y960 seam (HAIR_GAP).
WHY 100 and not the old 50: the seam caption's box straddles the seam (y921.5-994.5),
so the head needs clearance under the BOX; 100 leaves about 65px of air under it,
50 left about 15px and the caption sat on the hair. The owner of the number is
presets/instagram/talking-head-explainer/layout.md § 2 (its § Values holds the same
HAIR_GAP and FACE_CY_FALLBACK; workflows/test_talking_head_layout.py keeps them equal).
First pass must get this right with zero hand-tuning.

How: sample ~12 frames of the base cut, detect the face (OpenCV YuNet, model
vendored in assets/models/: on each still the largest box within 0.10 of its best
score, and a still whose box sits apart from every other is dropped), then find the true hair top with median-background
subtraction (the head moves, the room doesn't — robust against dark hair on a
dark background). Median across frames rides out take-to-take drift.

Usage (top of Graphics, before building anything):
  uv run workflows/face-frame.py projects/<job>/outputs/<job>.mp4
      → prints the #head object-position line, writes projects/<job>/face-frame.json
  uv run workflows/face-frame.py projects/<job>          (or projects/<job>/raw/<clip>)
      → EDL mode, for app lanes where RENDER=0 leaves no base cut: samples the raw ONLY
        inside transcript/cuts.json's kept spans of that clip, spread by kept duration,
        so killed takes never move the median. --edl <cuts.json> names another EDL. A job
        folder measures the clip the EDL keeps the most of and names every other kept clip:
        pass raw/<clip> to measure each of those.
  uv run workflows/face-frame.py --verify <draft-render.mp4>
      → re-measures the composite; must PASS before review (exit 1 on fail)
  uv run workflows/face-frame.py --verify <program.mp4> --plan projects/<job>
      → the same, sampling ONLY the plan's S (split) spans: on a layout-rotation job
        the other layouts frame the face elsewhere by design (layout.md § 2)
  add --annotate out.png to either for an eyeball frame; --out <json> writes the
  result there instead of projects/<job>/face-frame.json

The Talking Head Explainer's extra measurements (EDL mode, one run or several: each
adds its fields to face-frame.json and keeps the others it finds there):
  --modes     writes `modes`, the footage transforms, lane-neutral, in 1080x1920 frame
              fractions ({scale, centre: [x, y]}, scale 1.0 = the untouched wide shot,
              centre = where the source's centre lands):
                W  the wide shot, scale 1.0, slid sideways so the median shoulder midpoint
                   (the neck: MediaPipe pose's two shoulder landmarks, read on the same
                   stills as the face) lands on x540, as far as the footage still covers
                   the frame edge to edge (a 9:16 raw fills it: centre [0.5, 0.5]).
                   Shoulders unseen on half the stills (a tight shot, a shoulder out of
                   frame): the face-centred crop as measured, with a printed note
                S  W's scale, except a face taller than its window (hair top to chin over
                   600 px, y1020-1620): a landscape raw scales S down in 0.05 steps until
                   it fits, while the footage covers the bottom half edge to edge (a 9:16
                   raw cannot scale below its fit). THEN slid so the median hair top lands
                   on y1060 (fallback: the face-box centre on y1385), whatever the chin
                   does: a chin past y1620 is a printed note, never a raise; the neck on
                   x540 as in W
                T  a face box about 400px tall (scale 400 / the wide face height, never
                   under 1.15x; with a collar, measured now or stored by an earlier
                   --collar run, never so tight the derived tight caption leaves the
                   safe box), the face-box centre on y866 and the shoulder midpoint on
                   x540 (shoulders unseen: the face-box centre on x540)
              layout.md § 2 owns the formulas; lanes/premiere/layout-keys.py reads them.
  --collar    the y where the collar meets the skin on the wide framing: skin calibrated
              on the face's own cheek pixels, the first sustained non-skin row under the
              chin in a neck-wide column; the upper third (by y) of the sampled stills'
              readings that agree with the rest (captions-style.md § 2), with a confidence.
              With --plan projects/<job>: 8 stills over the layout's W, O and T spans only,
              the takes whose caption sits on the collar (a row with its own caption_y is
              left out; without --plan it says so and reads every kept span, S-only takes
              included). Unconfident (a turtleneck, a
              skin-coloured shirt, too few readings) = an annotated sheet next to the json
              and exit 3, UNMEASURED: it never guesses. A collar read after an earlier
              --modes run re-derives the stored modes with it, so T comes out capped as
              one joint run would write it; a new collar also names every --span fit
              for a re-fit (the collar caps a fit's T too).
  --crown A B the tallest crown (smallest hair-top y, W frame) over timeline span A-B s,
              sampled about every 0.25s through the EDL, into `crowns` (repeatable; an
              overlay card's clearance, layout.md § 9), each stamped with the EDL's
              fingerprint (`edl_sig`): layout.py ignores a crown read through another cut.
              Unmeasurable = exit 3.
  --span A B --modes   the W/S/T transforms fitted to timeline span A-B s ONLY (repeatable), into `span_modes`
              [{start, end, modes, edl_sig}], printed as a layout row's `frame`: a take framed apart from the
              median (the creator stands for the hook, sits after) gets its own fit, pasted into the plan's layout
              rows over that span (layout.md § 12; every lane reads it through layout.footage_spans()). The job's own
              `modes` and face fields are left as they are.
A bare run keeps every field those flags wrote (it re-measures the face only). When the face drifts past
SPREAD_WARN across the samples and splits into two framings, the warning names the EDL spans of the smaller one:
measure those with --span.

Every number below is measured in the 1080x1920 frame the #head shows: a 9:16 source
(any size) only scales onto it ("no reframe needed"), anything else gets the
face-centred reframe crop first.

Fallback when hair can't be measured (hood, hat, detection failure): face-box
center → y1385 (equivalent framing, derived from the same approved reference).
"""
import argparse, json, os, shutil, statistics, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # cv2_io.py: OpenCV file I/O on any path (Windows)
# Windows consoles/pipes default to cp1252, which can't encode the ✓/✗/⚠/→ glyphs in this
# script's status lines: a cosmetic print must never kill a pipeline step (it did once,
# 2026-08-13, mid-splice on a real Windows job). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

FRAME_W, FRAME_H = 1080, 1920
SEAM_Y = 960                  # graphics/face split
BOX_H = FRAME_H - SEAM_Y      # bottom box height (960)
HAIR_GAP = 100                # LOCKED: hair top sits this far below the seam (layout.md § 2 owns it)
FACE_CY_FALLBACK = 1385       # face-box center target if hair is unmeasurable
VERIFY_TOL = 40               # px tolerance in verify mode
CAPTION_BOX_BELOW = 34.5      # the seam caption box reaches this far under its line (layout.py BOX_BELOW)
VERIFY_FLOOR_Y = 1000         # --verify's hair search starts here, UNDER the seam caption box (y921.5-994.5): its text
                              # changes every frame, so background subtraction read the box as the hair top (y964)
                              # and failed a correct program. Under HAIR_GAP_MIN_Y, the top of S's face window
SAMPLES = 12
SPREAD_WARN = 150             # px of face drift across takes worth flagging
SCORE_MARGIN = 0.10           # a still's subject: the largest YuNet box within this of its best score (chin-line.py)
BOX_MAD_K = 6                 # a still's face centre this many MADs off the median is suspect (chin-line.py MAD_K) ...
BOX_GAP = 70                  # ... and dropped when no other still's sits within this many frame px (chin-line.py GAP)
# --modes (layout.md § 2 and § Values)
HAIR_GAP_MIN_Y = 1020         # S: with CHIN_MAX_Y, the window the face (hair top to chin) must fit: 600 px at most, a landscape
CHIN_MAX_Y = 1620             # raw scaling S down until it does. Neither moves the hair: it sits on y1060 whatever the chin
                              # does (2026-10-14), and a chin past y1620 (the platform's bottom band) is a note
POSE_LONG = 1280              # px: the long side a still is read at for its shoulders (the pose model's own input is 256)
SHOULDER_VIS = 0.5            # a shoulder landmark counts at this visibility or more, and inside the frame
T_FACE = (540, 866)           # T: the face-box centre on y866, and on x540 when the shoulders are unseen (seen: the neck on x540)
T_FACE_H = 400                # T: the face-box height the punch-in aims for
T_MIN = 1.15                  # T: never looser (a wobble, not a new angle)
T_CAPTION_MAX = 1585.5        # T: the derived caption line (collar through T + 78.5) stays on or above this
CAPTION_COLLAR = 78.5         # captions-style.md: the W/O line is collar + 78.5 (box top 40 under the collar)
# --collar / --crown
EXIT_UNMEASURED = 3
COLLAR_SPREAD = 40            # px: a reading this far under the median is an outlier, never the collar
COLLAR_QUANTILE = 2 / 3       # the collar written: the upper third of the agreeing readings (by y). Not the single lowest,
                              # which only moves lower as stills are added (a plan-less run's 12 read lowest y1260, the
                              # S-only CTA take, 20 px under the approved y1239.5). Not the median either: on a turned head
                              # collar_row's column, centred on the face box, misses the neck V and reads 12-28 px high.
                              # Benchmark raw, --collar --plan's 8 W/O/T stills: y1189-1244 (V-tips y1217-1248), median
                              # 1228, written y1236 (captions-style.md § 2)
COLLAR_STILLS = 8             # --collar --plan: stills over the layout's W, O and T spans (captions-style.md § 2)
S_STEP = 0.05                 # S on a landscape raw: scaled down in these steps until the face fits its window (layout.md § 2)
COLLAR_SUSTAIN = 10           # rows of non-skin in a row that make the collar (at the least)
COLLAR_RUN_FACE = 0.25        # ... and at least this share of the face height: the shadow under the jaw runs 20-40 rows
                              # (a purple-lit room read it as the collar on half the stills), the shirt runs hundreds
CROWN_STEP = 0.25             # s between crown samples

# the Talking Head Explainer's fields, kept across runs: span_modes too, the --span fits the plan rows' `frame` were
# pasted from, which a later --collar, --modes, --crown or bare run deleted (2026-10-13)
PRESET_KEYS = ("modes", "collar", "collar_read", "crowns", "span_modes")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(REPO, "assets", "models", "face_detection_yunet_2023mar.onnx")
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".m4v", ".mxf", ".avi")


def kept_spans(cuts, video):
    """The EDL's kept source spans of this clip: cuts.json segments with no clip, or a clip
    of this file's name. Copied from hero-frame.py / pii-scan.py (hyphenated, not importable)."""
    with open(cuts, encoding="utf-8") as fp:
        segs = json.load(fp)["segments"]
    name = os.path.basename(video)
    return sorted((float(s["start"]), float(s["end"])) for s in segs
                  if not s.get("clip") or os.path.basename(s["clip"]) == name)


def find_raw(job, cuts):
    """The job's raw clip: the one the EDL keeps the most of, else the first under raw/.
    Says which, and names every OTHER clip the EDL keeps: one run measures one clip."""
    rdir = os.path.join(job, "raw")
    vids = sorted(f for f in os.listdir(rdir) if f.lower().endswith(VIDEO_EXT)) \
        if os.path.isdir(rdir) else []
    if not vids:
        sys.exit(f"✗ no video under {rdir}")
    if not (cuts and os.path.isfile(cuts)):
        print(f"measuring raw/{vids[0]}")
        return os.path.join(rdir, vids[0])
    kept = {v: sum(b - a for a, b in kept_spans(cuts, v)) for v in vids}
    pick = max(vids, key=kept.get)
    print(f"measuring raw/{pick} (the EDL keeps {kept[pick]:.1f}s of it)")
    others = [v for v in vids if v != pick and kept[v] > 0]
    if others:
        print("⚠ the EDL also keeps " + ", ".join(f"{kept[v]:.1f}s of raw/{v}" for v in others)
              + f": this run measures raw/{pick} only — pass each raw/<clip> to measure it")
    return os.path.join(rdir, pick)


def resolve(target, edl=None, out=None):
    """(video, kept spans or None, EDL path or None, result json or None) for a base cut,
    a raw clip, or a job folder. A job folder or a clip under <job>/raw/ defaults to the
    job's transcript/cuts.json; a base cut is already the edit and is sampled whole."""
    target = os.path.abspath(target)
    job = None
    if os.path.isdir(target):
        job = target
    elif os.path.basename(os.path.dirname(target)) == "raw":
        job = os.path.dirname(os.path.dirname(target))
    if edl is None and job:
        edl = os.path.join(job, "transcript", "cuts.json")
        if not os.path.isfile(edl):
            print("⚠ no transcript/cuts.json: measuring the WHOLE raw (killed takes included)")
            edl = None
    elif edl and not os.path.isfile(edl):
        sys.exit(f"✗ no EDL at {edl}")
    video = find_raw(job, edl) if os.path.isdir(target) else target
    spans = kept_spans(edl, video) if edl else None
    if edl and not spans:
        print(f"⚠ {os.path.basename(edl)} keeps nothing of {os.path.basename(video)}: "
              f"measuring the WHOLE clip")
        spans = edl = None
    if out is None and job:
        out = os.path.join(job, "face-frame.json")
    return video, spans, edl, out


def sample_times(dur, n=SAMPLES, spans=None):
    """n sample times, evenly spread: over the whole video, or over the kept spans only,
    by kept duration (each lands inside a span, never on a killed take)."""
    if not spans:
        return [dur * (i + 0.5) / n for i in range(n)]
    spans = [(max(0.0, a), min(dur, b)) for a, b in spans if min(dur, b) > max(0.0, a)]
    total = sum(b - a for a, b in spans)
    times = []
    for i in range(n if spans else 0):
        off = total * (i + 0.5) / n
        for a, b in spans:
            if off < b - a or (a, b) == spans[-1]:
                times.append(min(a + off, b - 1e-3))
                break
            off -= b - a
    return times


def print_sampled(video, spans, times):
    kept = sum(b - a for a, b in spans)
    print(f"EDL: {len(spans)} kept spans of {os.path.basename(video)}, {kept:.1f}s kept; "
          f"sampled {len(times)} frames in:")
    for k, (a, b) in enumerate(spans):
        ts = [t for t in times if a <= t < b]
        if ts:
            print(f"  span {k + 1:>2}  {a:8.2f}–{b:8.2f}s  → t " + ", ".join(f"{t:.2f}" for t in ts))


def probe(video):
    """(width, height, duration) as CODED (measure() reads the decoded size off the frames). JSON, never csv: iPhone
    side data and ffprobe 9's timecode stream group add elements and rows to csv, and a Matroska or WebM stream has
    no duration of its own (csv 'N/A', a ValueError on an OBS .mkv raw), so the container's is taken."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration:format=duration", "-of", "json", video],
        capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s = d["streams"][0]
    return int(s["width"]), int(s["height"]), float(s.get("duration") or d["format"]["duration"])


def sample_frames(video, times):
    from cv2_io import imread     # never cv2.imread: %TEMP% sits under the user profile, any name (cv2_io.py)
    imgs = []
    with tempfile.TemporaryDirectory() as tmp:  # 4K raws: a dozen PNGs per run must not pile up
        for i, t in enumerate(times):
            f = os.path.join(tmp, f"f{i}.png")
            subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video,
                            "-frames:v", "1", "-y", f], capture_output=True)
            img = imread(f)
            if img is not None:
                imgs.append(img)
    return imgs


def to_frame(img, x0, crop_w):
    """A source frame as the #head shows it: the reframe crop, scaled onto 1080x1920."""
    import cv2
    img = img[:, x0:x0 + crop_w]
    if img.shape[:2] == (FRAME_H, FRAME_W):
        return img
    return cv2.resize(img, (FRAME_W, FRAME_H), interpolation=cv2.INTER_AREA)


def subject(dets, margin=SCORE_MARGIN):
    """THE SUBJECT IS THE BIGGEST CONFIDENT FACE (chin-line.py's subject(), the house lock ONE SAMPLE IS NEVER THE FLOOR):
    every YuNet row within `margin` of the still's best score, then the largest of those. The largest box alone fell for
    a big low-score phantom (whop-first-10k, 3 of 12 stills: a 459x578 box at score 0.64 in the room beside him, against
    his own 460x466 at 0.72), the top score alone falls for a small face-like print in the room."""
    top = max(float(d[14]) for d in dets)
    return max((d for d in dets if float(d[14]) >= top - margin), key=lambda d: float(d[2]) * float(d[3]))


def detect_faces(imgs, w, h):
    from cv2_io import face_detector
    det = face_detector(MODEL, (w, h), score_threshold=0.6)
    boxes = []
    for img in imgs:
        _, dets = det.detect(img)
        if dets is None or len(dets) == 0:
            continue
        x, y, bw, bh = (float(v) for v in subject(dets)[:4])
        boxes.append((x, y, bw, bh))
    return boxes


def stray_boxes(boxes, scale):
    """The indices of the stills whose face box sits apart from every other still's: its centre more than BOX_MAD_K MADs
    off the median on x or y AND no other still's within BOX_GAP frame px (`scale` = frame px per source px). chin-line.py's
    outliers(): one detector call is not a measurement, but a real lean, or a second posture, is on several stills and
    corroborates itself."""
    if len(boxes) < 3:
        return []
    bad = set()
    for vals in ([(x + w / 2) * scale for x, y, w, h in boxes], [(y + h / 2) * scale for x, y, w, h in boxes]):
        med = statistics.median(vals)
        mad = statistics.median(abs(v - med) for v in vals) or 1.0
        for i, v in enumerate(vals):
            if abs(v - med) > BOX_MAD_K * mad and not any(abs(o - v) <= BOX_GAP for j, o in enumerate(vals) if j != i):
                bad.add(i)
    return sorted(bad)


def median_box(boxes):
    cx = statistics.median(x + w / 2 for x, y, w, h in boxes)
    cy = statistics.median(y + h / 2 for x, y, w, h in boxes)
    fw = statistics.median(w for x, y, w, h in boxes)
    fh = statistics.median(h for x, y, w, h in boxes)
    top = statistics.median(y for x, y, w, h in boxes)
    return cx, cy, fw, fh, top


def hair_tops(imgs, face_cx, face_top, y_floor=0, plate=None):
    """Topmost moving-person row per frame via median-background subtraction. `plate` is
    the empty room (default: the median of these frames); --crown passes the take's own."""
    import cv2, numpy as np
    if plate is None:
        plate = np.median(np.stack([i.astype(np.float32) for i in imgs]), axis=0)
    x0 = max(0, int(face_cx - 300))
    x1 = min(imgs[0].shape[1], int(face_cx + 300))
    y0 = max(y_floor, int(face_top - 350))
    y1 = int(face_top)
    tops = []
    for img in imgs:
        diff = np.abs(img.astype(np.float32) - plate).mean(axis=2)
        mask = (diff > 14).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        band = mask[y0:y1, x0:x1]
        rows = np.where(band.sum(axis=1) > 25)[0]
        if len(rows):
            tops.append(y0 + int(rows[0]))
    return tops


def w_centre_x(src_w, x0, crop_w):
    """W's centre x in frame fractions: where the source's centre lands on the (reframed) wide shot."""
    return (src_w / 2 - x0) * (FRAME_W / crop_w) / FRAME_W


def slide_x(c, anchor, k, src_w):
    """The centre x (frame px) at scale k that puts `anchor` on the frame's centre x, no further than the footage still
    covers the frame edge to edge. `anchor` and `c` are frame px on the W framing as measured (c = where the source's
    centre lands on it), src_w the source's width in frame px on that framing (1080 on a 9:16 raw, which fills the frame
    and has no room). -> (centre x, where the anchor lands less the centre x: 0 unless the footage ran out of room)."""
    want = FRAME_W / 2 - k * (anchor - c)
    room = max(0.0, k * src_w / 2 - FRAME_W / 2)
    got = min(max(want, FRAME_W / 2 - room), FRAME_W / 2 + room)
    return got, got - want


def compute_modes(face_c, face_h, hair, wx, collar=None, landscape=None, shoulders=None):
    """face-frame.json `modes` from the wide-frame measurement (1080x1920 px): layout.md § 2's formulas.
    face_c = the face-box centre (x, y), face_h its height, hair the median hair top (None = unmeasured), wx W's centre x
    as measured (frame fractions: a landscape raw's face-centred crop), collar the collar line (None = not measured),
    landscape the height-fitted source's width in frame px on a landscape raw (None on a 9:16 raw), shoulders the median
    shoulder midpoint x, the neck, in frame px on that same framing (None = unseen). -> (modes, notes).
    S: a face taller than its window (hair top to chin over CHIN_MAX_Y - HAIR_GAP_MIN_Y, 600 px) scales down in S_STEP
    steps on a landscape raw while the footage covers the bottom half, then the hair top goes on y1060 whatever the chin
    does (2026-10-14: the approved S is 0.85x with the hair on y1060, "a tiny bit of space between my hair and the
    top"). W, S and T put the neck on the frame's centre x (2026-10-14: "keep my shoulder and my neck centered"),
    T's scale and height staying the face's."""
    fx, fy = face_c
    notes = []
    c = wx * FRAME_W
    src_w = landscape or FRAME_W
    chin = fy + face_h / 2
    if hair is not None:
        top, anchor, onto, what = hair, hair, SEAM_Y + HAIR_GAP, "hair top"
    else:                                                       # the face-box top stands in for the hair
        top, anchor, onto, what = fy - face_h / 2, fy, FACE_CY_FALLBACK, "face-box top"
        notes.append(f"S: hair top unmeasured, face-box centre on y{FACE_CY_FALLBACK} (the fallback)")
    span, window = chin - top, CHIN_MAX_Y - HAIR_GAP_MIN_Y
    s_cy = lambda k: onto - k * (anchor - FRAME_H / 2)          # the anchor on its line at scale k
    s_cx = lambda k: slide_x(c, shoulders, k, src_w)[0] if shoulders is not None else fx - k * (fx - c)
    covers = lambda k: (k > 0 and s_cy(k) + k * FRAME_H / 2 >= FRAME_H and s_cy(k) - k * FRAME_H / 2 <= SEAM_Y
                        and s_cx(k) - k * src_w / 2 <= 0 and s_cx(k) + k * src_w / 2 >= FRAME_W)
    s = 1.0
    if span > window and landscape:
        while s * span > window and covers(round(s - S_STEP, 2)):
            s = round(s - S_STEP, 2)
        if s < 1.0:
            notes.append(f"S: the face spans {span:.0f} px ({what} to chin), over its {window} px window: a landscape raw, "
                         f"scaled to {s:.2f}x ({s * span:.0f} px)")
    if s * span > window:
        notes.append(f"S: the face spans {s * span:.0f} px ({what} to chin), over its {window} px window: "
                     + ("the footage cannot scale further and still cover the bottom half edge to edge" if landscape
                        else "a 9:16 raw cannot scale below its fit"))
    end = s_cy(s) + s * (chin - FRAME_H / 2)
    if end > CHIN_MAX_Y + 0.5:
        notes.append(f"S: the chin sits on y{end:.0f}, past y{CHIN_MAX_Y} (the platform's bottom band): the hair gap "
                     "holds, and nothing raises the face for the chin (layout.md § 2)")
    k = max(T_MIN, T_FACE_H / face_h)
    if collar is not None and collar > fy:
        cap = (T_CAPTION_MAX - CAPTION_COLLAR - T_FACE[1]) / (collar - fy)
        if k > cap:
            notes.append(f"T: {k:.2f}x would push the derived tight caption past y{T_CAPTION_MAX}: {cap:.2f}x"
                         + ("" if cap >= T_MIN else f", under the {T_MIN}x floor: the framing is wrong, not the caption"))
            k = max(T_MIN, cap)
    wcx, tcx = c, T_FACE[0] - k * (fx - c)                      # shoulders unseen: W as measured, T on the face
    if shoulders is not None:
        wcx, off = slide_x(c, shoulders, 1.0, src_w)
        if abs(off) >= 1:
            notes.append(f"W, S: the shoulder midpoint lands {off:+.0f} px off x{FRAME_W // 2}: "
                         + ("a 9:16 raw fills the frame and cannot slide without baring a side" if landscape is None
                            else "the footage cannot slide further and still cover the frame edge to edge"))
        tcx, off = slide_x(c, shoulders, k, src_w)
        if abs(off) >= 1:
            notes.append(f"T: the shoulder midpoint lands {off:+.0f} px off x{FRAME_W // 2}: the footage cannot slide "
                         "further and still cover the frame edge to edge")
    r = lambda v: round(v, 4)
    modes = {"W": {"scale": 1.0, "centre": [r(wcx / FRAME_W), 0.5]},
             "S": {"scale": s, "centre": [r(s_cx(s) / FRAME_W), r(s_cy(s) / FRAME_H)]},
             "T": {"scale": r(k), "centre": [r(tcx / FRAME_W), r((T_FACE[1] - k * (fy - FRAME_H / 2)) / FRAME_H)]}}
    return modes, notes


def shoulder_mids(imgs):
    """Per still, the shoulder midpoint x (the neck) in that still's own px, or None: MediaPipe pose's two shoulder
    landmarks (11, 12), each seen (visibility SHOULDER_VIS) inside the frame. Read on the whole source still, so a
    shoulder the 9:16 crop cuts still counts. mediapipe is pinned to 0.10.14: 1.0 dropped the solutions API
    (hero-frame.py), and pose model 1 ships inside the wheel (0 and 2 are downloaded on first use)."""
    import cv2
    import mediapipe as mp
    out = []
    with mp.solutions.pose.Pose(static_image_mode=True, model_complexity=1) as pose:
        for img in imgs:
            h, w = img.shape[:2]
            s = min(1.0, POSE_LONG / max(h, w))
            small = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA) if s < 1 else img
            res = pose.process(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
            lm = res.pose_landmarks.landmark if res.pose_landmarks else None
            seen = lm is not None and all(lm[i].visibility >= SHOULDER_VIS and 0 <= lm[i].x <= 1 for i in (11, 12))
            out.append((lm[11].x + lm[12].x) / 2 * w if seen else None)
    return out


def collar_row(img, box):
    """The collar/skin line under one frame's face (frame px), or None. Skin is calibrated on the face's own cheeks
    (chroma only); the collar is the first row after skin where a neck-wide column stops being skin for a LONG run
    (COLLAR_SUSTAIN rows and COLLAR_RUN_FACE of the face height), so the short dark band of the jaw's shadow, with
    neck skin under it, is stepped over. No neck under the chin (a turtleneck) or no end to it (a skin-coloured
    shirt, bare shoulders) is None: never a guess."""
    import cv2, numpy as np
    H, W = img.shape[:2]
    x, y, bw, bh = box
    c = lambda v, hi: int(max(0, min(hi, round(v))))
    ycc = cv2.cvtColor(np.ascontiguousarray(img), cv2.COLOR_BGR2YCrCb).astype(np.float32)[..., 1:]
    r0, r1 = c(y + 0.55 * bh, H), c(y + 0.75 * bh, H)
    cheeks = np.concatenate([ycc[r0:r1, c(x + 0.15 * bw, W):c(x + 0.35 * bw, W)].reshape(-1, 2),
                             ycc[r0:r1, c(x + 0.65 * bw, W):c(x + 0.85 * bw, W)].reshape(-1, 2)])
    if len(cheeks) < 50:
        return None
    m, s = np.median(cheeks, axis=0), np.maximum(cheeks.std(axis=0), 4.0)
    mid = x + bw / 2
    top, bottom = c(y + bh, H), c(y + 2.5 * bh, H)
    col = ycc[top:bottom, c(mid - 0.15 * bw, W):c(mid + 0.15 * bw, W)]
    if col.size == 0:
        return None
    skin = ((np.abs(col - m) / s) <= 3).all(axis=2).mean(axis=1) >= 0.5
    need = max(COLLAR_SUSTAIN, int(COLLAR_RUN_FACE * bh))
    seen, run = False, 0
    for i, sk in enumerate(skin):
        if sk:
            seen, run = True, 0
        elif seen:
            run += 1
            if run >= need:
                return top + i - run + 1
    return None


def quantile(xs, q):
    """The q-quantile of xs, linear between order statistics (xs non-empty)."""
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    lo = int(i)
    return xs[lo] + (xs[min(lo + 1, len(xs) - 1)] - xs[lo]) * (i - lo)


def measure_collar(fimgs, boxes):
    """(collar y or None, report dict): the upper third of the agreeing readings (COLLAR_QUANTILE, by y), so the box
    clears the skin on most takes without one low still dragging every line down (captions-style.md § 2)."""
    import statistics as st
    reads = [collar_row(img, b) if b else None for img, b in zip(fimgs, boxes)]
    got = [r for r in reads if r is not None]
    rep = {"frames": len(fimgs), "readings": got}
    if len(got) < max(3, len(fimgs) / 2):
        rep["why"] = f"a collar read on only {len(got)} of {len(fimgs)} stills"
        return None, rep
    med = st.median(got)
    kept = [r for r in got if r - med <= COLLAR_SPREAD]
    rep["dropped"] = sorted(r for r in got if r - med > COLLAR_SPREAD)
    if len(kept) < max(3, len(fimgs) / 2):
        rep["why"] = f"the readings disagree ({sorted(got)})"
        return None, rep
    rep["median"] = round(med)
    rep["lowest"] = max(kept)
    rep["confidence"] = round(len(kept) / len(fimgs), 2)
    return int(round(quantile(kept, COLLAR_QUANTILE))), rep


def edl_sig(segs):
    """A short fingerprint of an EDL's segments (layout.py's edl_sig is the same function): a crown read through one
    EDL is stale on another."""
    import hashlib
    body = json.dumps([[os.path.basename(str(x.get("clip") or "")), round(float(x["start"]), 6), round(float(x["end"]), 6)]
                       for x in segs or []], separators=(",", ":"))
    return hashlib.sha1(body.encode()).hexdigest()[:12]


def plan_source_spans(plan, segs, name, modes=("W", "O", "T")):
    """The raw-clock spans of clip `name` under the plan's `layout` spans of `modes`, through the EDL: where the caption
    sits on the collar (W, O, and T carried through its transform). A row with its own `caption_y` (or `ui_bottom`) puts
    its line there instead (layout.py's _row and _span_y), so it is left out."""
    path = os.path.join(plan, "graphics-plan.json") if os.path.isdir(plan) else plan
    with open(path, encoding="utf-8") as fp:
        rows = json.load(fp).get("layout") or []
    want = []
    for r in rows:
        if isinstance(r, dict):
            a, b, m = r["start"], r["end"], r["mode"]
            own = r.get("caption_y") is not None or r.get("ui_bottom") is not None
        else:
            a, b, m = r[0], r[1], r[2]
            own = len(r) > 3 and r[3] is not None
        if m in modes and not own:
            want.append((float(a), float(b)))
    out, pos = [], 0.0
    for sg in segs or []:
        d = float(sg["end"]) - float(sg["start"])
        clip = sg.get("clip")
        if not (name and clip and os.path.basename(clip) != name):
            for a, b in want:
                x, y = max(a, pos), min(b, pos + d)
                if y - x > 1e-3:
                    out.append((float(sg["start"]) + x - pos, float(sg["start"]) + y - pos))
        pos += d
    return sorted(out)


def collar_sheet(fimgs, boxes, reads, out):
    """The annotated contact sheet an UNMEASURED collar leaves for the eye: every still, its face box, its reading."""
    import cv2, numpy as np
    from cv2_io import imwrite
    tiles = []
    for img, b, r in zip(fimgs, boxes, reads):
        t = np.ascontiguousarray(img).copy()
        if b:
            x, y, w, h = (int(v) for v in b)
            cv2.rectangle(t, (x, y), (x + w, y + h), (0, 0, 255), 6)
        if r is not None:
            cv2.line(t, (0, r), (t.shape[1], r), (0, 255, 255), 4)
        tiles.append(cv2.resize(t, (t.shape[1] // 4, t.shape[0] // 4)))
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [cv2.hconcat(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]
    imwrite(out, cv2.vconcat(rows))
    return out


def timeline_to_source(t, segs, name=None):
    """A timeline time -> the source time on clip `name` through the EDL's segments in order, or None when it lands
    on another clip or past the end. segs=None: the video IS the timeline (a base cut)."""
    if segs is None:
        return t
    pos = 0.0
    for s in segs:
        d = float(s["end"]) - float(s["start"])
        if t < pos + d:
            clip = s.get("clip")
            if name and clip and os.path.basename(clip) != name:
                return None
            return float(s["start"]) + (t - pos)
        pos += d
    return None


def measure_crowns(video, windows, edl, x0, crop_w, face_cx, face_top, plate):
    """[{start, end, y, samples}] per timeline window: the tallest crown (smallest hair-top y, W frame) over it."""
    segs = None
    if edl:
        with open(edl, encoding="utf-8") as fp:
            segs = json.load(fp)["segments"]
    name = os.path.basename(video)
    found, missing = [], []
    for a, b in windows:
        ts = [a + i * CROWN_STEP for i in range(int((b - a) / CROWN_STEP) + 1) if a + i * CROWN_STEP < b]
        ts.append(max(a, b - 0.02))
        src = [s for s in (timeline_to_source(t, segs, name) for t in ts) if s is not None]
        imgs = sample_frames(video, src) if src else []
        tops = hair_tops([to_frame(i, x0, crop_w) for i in imgs], face_cx, face_top, plate=plate) if imgs else []
        if tops:
            found.append({"start": a, "end": b, "y": round(min(tops)), "samples": len(tops)}
                         | ({"edl_sig": edl_sig(segs)} if segs is not None else {}))
            print(f"crown {a:.2f}-{b:.2f}s: y{min(tops):.0f} (the tallest of {len(tops)} reads)")
        else:
            missing.append((a, b))
            print(f"✗ crown {a:.2f}-{b:.2f}s: UNMEASURED ({len(src)} frames on this clip, no hair top read): "
                  "read it by eye on the span's stills (layout.md § 9)")
    return found, missing


def plan_spans(plan, mode="S"):
    """The plan's `layout` spans of one mode, [(start, end)]: a graphics-plan.json or its job folder."""
    path = os.path.join(plan, "graphics-plan.json") if os.path.isdir(plan) else plan
    with open(path, encoding="utf-8") as fp:
        rows = json.load(fp).get("layout") or []
    out = []
    for r in rows:
        a, b, m = (r["start"], r["end"], r["mode"]) if isinstance(r, dict) else (r[0], r[1], r[2])
        if m == mode:
            out.append((float(a), float(b)))
    if not out:
        sys.exit(f"✗ {path} has no {mode} spans in its top-level `layout`")
    return out


def merge_out(out, result, keep=PRESET_KEYS):
    """The fields an earlier --modes/--collar/--crown run wrote, kept unless this run measured them again; crowns
    merge by span (a re-read span replaces its old reading)."""
    try:
        with open(out, encoding="utf-8") as fp:
            old = json.load(fp)
    except (OSError, ValueError):
        return result
    for k in keep:
        if k in old and k not in result:
            result[k] = old[k]
        elif k == "crowns" and k in old:
            spans = {(c["start"], c["end"]) for c in result["crowns"]}
            result["crowns"] = sorted([c for c in old["crowns"] if (c["start"], c["end"]) not in spans]
                                      + result["crowns"], key=lambda c: c["start"])
    return result


def timeline_ranges(src_times, segs, name):
    """The EDL segments (TIMELINE [a, b], merged when adjacent) that hold these SOURCE times of clip `name`."""
    out, pos = [], 0.0
    for s_ in segs:
        a, b = float(s_["start"]), float(s_["end"])
        if (not s_.get("clip") or os.path.basename(s_["clip"]) == name) and any(a <= t < b for t in src_times):
            if out and abs(out[-1][1] - pos) < 1e-6:
                out[-1] = (out[-1][0], pos + b - a)
            else:
                out.append((pos, pos + b - a))
        pos += b - a
    return out


def split_warn(video, imgs, times, w, h, sy, edl):
    """Two framings in one take list (a standing hook, seated after: 354 px of drift on the Windows test job, the face
    under the S panel in the hook): the face-centre heights split at their widest gap; when that gap is over half
    SPREAD_WARN, name the smaller group's EDL spans so each gets its own --span fit and a layout row `frame`."""
    ys = []
    for t, img in zip(times, imgs):
        b = detect_faces([img], w, h)
        if b:
            ys.append((b[0][1] * sy + b[0][3] * sy / 2, t))
    if len(ys) < 4:
        return
    ys.sort()
    gap, i = max((ys[k + 1][0] - ys[k][0], k) for k in range(len(ys) - 1))
    if gap <= SPREAD_WARN / 2:
        return
    lo, hi = ys[:i + 1], ys[i + 1:]
    small = lo if len(lo) <= len(hi) else hi
    with open(edl, encoding="utf-8") as fp:
        segs = json.load(fp)["segments"]
    rng = timeline_ranges([t for _y, t in small], segs, os.path.basename(video))
    where = "higher" if small is lo else "lower"
    print(f"⚠ two framings: {len(small)} of {len(ys)} samples sit {gap:.0f}px {where} than the rest (face centre "
          f"y{statistics.median(y for y, _t in small):.0f} against y{statistics.median(y for y, _t in (hi if small is lo else lo)):.0f}). "
          "Fit each apart and give those layout rows their own `frame`:")
    for a, b in rng:
        print(f"    uv run workflows/face-frame.py <job> --span {a:.3f} {b:.3f} --modes")


def measure_spans(target, edl, out, span_list):
    """--span A B --modes: the W/S/T transforms fitted to each timeline span alone, into face-frame.json
    `span_modes`, printed as the layout row `frame` to paste; the job's own fields stay as they are."""
    video, _spans, edl, out = resolve(target, edl, out)
    if not edl:
        sys.exit("✗ --span maps a timeline span through the EDL: measure a job folder or a raw with its cuts.json")
    with open(edl, encoding="utf-8") as fp:
        segs = json.load(fp)["segments"]
    name = os.path.basename(video)
    stored = {}
    if out and os.path.exists(out):
        with open(out, encoding="utf-8") as fp:
            stored = json.load(fp)
    entries = [e for e in stored.get("span_modes", []) if (e["start"], e["end"]) not in {tuple(x) for x in span_list}]
    for a, b in span_list:
        src, pos = [], 0.0
        for s_ in segs:
            s0, s1 = float(s_["start"]), float(s_["end"])
            x, y = max(a, pos), min(b, pos + s1 - s0)
            if y - x > 1e-3 and (not s_.get("clip") or os.path.basename(s_["clip"]) == name):
                src.append((s0 + x - pos, s0 + y - pos))
            pos += s1 - s0
        if not src:
            sys.exit(f"✗ timeline {a:.3f}-{b:.3f} holds none of {name}")
        print(f"\n── span {a:.3f}-{b:.3f}s ({sum(y - x for x, y in src):.1f}s of {name}) ──")
        tmp = None
        if out and os.path.exists(out):                 # the stored collar still caps T: measure against a copy
            tmp = os.path.join(tempfile.mkdtemp(), "face-frame.json")
            shutil.copyfile(out, tmp)
        r = measure(video, spans=src, edl=edl, out=tmp, modes=True)
        if tmp:
            shutil.rmtree(os.path.dirname(tmp), ignore_errors=True)
        entries.append({"start": a, "end": b, "modes": r["modes"], "edl_sig": edl_sig(segs)})
        for k in ("S", "T", "W"):
            m = r["modes"][k]
            print(f'  {k} rows in {a:.3f}-{b:.3f}: "frame": {{"scale": {m["scale"]}, "centre": [{m["centre"][0]}, {m["centre"][1]}]}}')
    if out:
        stored["span_modes"] = sorted(entries, key=lambda e: e["start"])
        with open(out, "w", encoding="utf-8") as fp:
            json.dump(stored, fp, indent=2)
        print(f"wrote span_modes into {out}")


def measure(video, annotate=None, spans=None, edl=None, out=None, modes=False, collar=False, crowns=None, plan=None):
    sw, sh, dur = probe(video)
    times = sample_times(dur, SAMPLES, spans)
    if spans:
        spans = [(a, b) for a, b in spans if min(dur, b) > max(0.0, a)]
        if not times:
            print(f"✗ the EDL keeps nothing inside this clip's {dur:.1f}s — not writing a crop.")
            sys.exit(1)
    imgs = sample_frames(video, times)
    if not imgs:
        print(f"✗ ffmpeg decoded no frames of {os.path.basename(video)} — not writing a crop.")
        sys.exit(1)
    # measure the frame as DECODED: ffmpeg applies a phone raw's rotation matrix, the
    # stream's coded size does not (3840x2160 rotated −90 decodes 2160x3840 upright)
    h, w = imgs[0].shape[:2]
    print(f"source: {w}x{h}  {dur:.1f}s"
          + ("" if (w, h) == (sw, sh) else f"  (coded {sw}x{sh}, rotated on decode)"))
    if spans:
        print_sampled(video, spans, times)
    boxes = detect_faces(imgs, w, h)
    stray = stray_boxes(boxes, FRAME_H / h)
    if stray:
        print(f"⚠ face: dropped {len(stray)} still(s) whose box sits apart from every other (centre "
              + ", ".join(f"({boxes[i][0] + boxes[i][2] / 2:.0f},{boxes[i][1] + boxes[i][3] / 2:.0f})" for i in stray)
              + f" against the median ({statistics.median(b[0] + b[2] / 2 for b in boxes):.0f},"
              + f"{statistics.median(b[1] + b[3] / 2 for b in boxes):.0f})): a mis-detection, never the subject")
        boxes = [b for i, b in enumerate(boxes) if i not in stray]
    if len(boxes) < len(imgs) / 2:
        print(f"✗ face detected in only {len(boxes)}/{len(imgs)} frames — "
              f"not writing a crop. Eyeball the framing manually.")
        sys.exit(1)
    cx, cy, fw, fh, ftop = median_box(boxes)

    # horizontal: a 9:16 source only scales onto the frame; anything else gets the
    # reframe crop that centers the face
    x0, crop_w = 0, w
    if w * FRAME_H == h * FRAME_W:
        reframe = None
    else:
        crop_w = round(h * 9 / 16 / 2) * 2
        x0 = max(0, min(w - crop_w, round(cx - crop_w / 2)))
        reframe = {"crop_w": crop_w, "crop_h": h, "crop_x": x0,
                   "ffmpeg": f"crop={crop_w}:{h}:{x0}:0,scale={FRAME_W}:{FRAME_H}"}
    # everything from here is in the 1080x1920 frame the #head shows, where the numbers live
    sx, sy = FRAME_W / crop_w, FRAME_H / h
    spread = (max(y + h_ / 2 for x, y, w_, h_ in boxes)
              - min(y + h_ / 2 for x, y, w_, h_ in boxes)) * sy
    print(f"face: center=({cx:.0f},{cy:.0f})  box={fw:.0f}x{fh:.0f}  "
          f"drift across takes: {spread:.0f}px")
    if spread > SPREAD_WARN:
        print(f"⚠ framing varies {spread:.0f}px across takes (> {SPREAD_WARN}) — "
              f"median crop may not fit every take; review the draft closely.")
        if spans and edl:
            split_warn(video, imgs, times, w, h, sy, edl)

    result = {"video": os.path.abspath(video), "source": {"w": w, "h": h},
              "face": {"cx": round(cx), "cy": round(cy), "w": round(fw),
                       "h": round(fh), "spread_y": round(spread),
                       "frames": len(boxes)}}
    if spans:
        result["edl"] = {"path": os.path.abspath(edl) if edl else None,
                         "kept_spans": len(spans), "sampled": [round(t, 3) for t in times]}
    if reframe:
        result["reframe"] = reframe
        print(f"reframe 9:16 first: ffmpeg -vf \"{reframe['ffmpeg']}\"")
    else:
        print(f"no reframe needed: {w}x{h} is already 9:16"
              + ("" if w == FRAME_W else f", it scales straight onto {FRAME_W}x{FRAME_H}"))
    cx, cy, fh, ftop = (cx - x0) * sx, cy * sy, fh * sy, ftop * sy

    # vertical anchor: hair top HAIR_GAP px below the seam
    fimgs = [to_frame(i, x0, crop_w) for i in imgs]
    tops = hair_tops(fimgs, cx, ftop)
    hair = None
    if len(tops) >= len(imgs) / 2:
        hair = statistics.median(tops)
        result["hair_top"] = round(hair)
        win_top = hair - HAIR_GAP
        anchor = f"hair top y{hair:.0f} → {HAIR_GAP}px below seam"
    else:
        print("⚠ hair top unmeasurable — falling back to face-center anchor")
        win_top = cy - (FACE_CY_FALLBACK - SEAM_Y)
        anchor = f"face center y{cy:.0f} → frame y{FACE_CY_FALLBACK}"

    p = win_top / (FRAME_H - BOX_H)
    clamped = min(1.0, max(0.0, p))
    if clamped != p:
        print(f"⚠ ideal crop clamps at frame edge ({p:.1%} → {clamped:.1%}) — "
              f"face sits {abs(p - clamped) * (FRAME_H - BOX_H):.0f}px off target.")
    result["object_position_y"] = round(clamped * 100, 1)
    result["anchor"] = anchor
    print(f"anchor: {anchor}")
    print(f"→ #head {{ object-fit:cover; object-position:50% {result['object_position_y']}%; }}")

    vdir = os.path.dirname(os.path.abspath(video))
    if out is None and os.path.basename(vdir) == "outputs":
        out = os.path.join(os.path.dirname(vdir), "face-frame.json")

    unmeasured = []
    col = None
    if collar:
        cimgs, cfimgs = imgs, fimgs
        if plan:                                        # only where the caption sits on the collar: W, O, T
            with open(edl, encoding="utf-8") as fp:
                segs = json.load(fp)["segments"]
            cspans = plan_source_spans(plan, segs, os.path.basename(video))
            if not cspans:
                sys.exit(f"✗ the plan's W, O and T spans (bar those with their own caption_y) hold none of "
                         f"{os.path.basename(video)}: nothing to read the collar on")
            ctimes = sample_times(dur, COLLAR_STILLS, cspans)
            print(f"collar: {len(ctimes)} stills over the plan's W/O/T spans ({sum(b - a for a, b in cspans):.1f}s of this clip)")
            cimgs = sample_frames(video, ctimes)
            cfimgs = [to_frame(i, x0, crop_w) for i in cimgs]
        else:
            print("⚠ collar: no --plan, so the stills cover every kept span, S-only takes included (whose caption never "
                  "sits on the collar): pass --plan projects/<job> once the layout map exists (captions-style.md § 2)")
        fboxes = []
        for img in cimgs:                               # per still: the collar sits under THAT frame's chin
            b = detect_faces([img], w, h)
            fboxes.append(((b[0][0] - x0) * sx, b[0][1] * sy, b[0][2] * sx, b[0][3] * sy) if b else None)
        fimgs_c = cfimgs
        col, rep = measure_collar(fimgs_c, fboxes)
        if col is not None:
            result["collar"] = int(col)
            result["collar_read"] = {k: rep[k] for k in ("frames", "median", "lowest", "confidence", "dropped")}
            result["collar_read"]["spans"] = "plan W/O/T" if plan else "every kept span"
            from datetime import datetime
            result["collar_read"]["at"] = datetime.now().isoformat(timespec="seconds")   # layout.py: an older y.wide yields
            print(f"collar: y{col} (the upper third of {len(rep['readings'])} readings, median y{rep['median']}, lowest "
                  f"y{rep['lowest']}, confidence {rep['confidence']})" + (f"; dropped outliers {rep['dropped']}" if rep["dropped"] else ""))
        else:
            sheet = os.path.join(os.path.dirname(os.path.abspath(out)) if out else tempfile.gettempdir(),
                                 "face-frame-collar.png")
            collar_sheet(fimgs_c, fboxes, [collar_row(i, b) if b else None for i, b in zip(fimgs_c, fboxes)], sheet)
            print(f"✗ collar UNMEASURED: {rep['why']}. Read it by eye on {sheet} (or anchor on the chin, "
                  "captions-style.md § 2); nothing written for `collar`")
            unmeasured.append("collar")
    stored = {}
    if out and (modes or col is not None):
        try:
            with open(out, encoding="utf-8") as fp:
                stored = json.load(fp)
        except (OSError, ValueError):
            stored = {}
    # a --collar run after --modes (graphics-plan's order: --modes before the map, --collar --plan after it): the
    # stored T was derived with no collar to cap it, so it is derived again here, as one joint run would
    recap = not modes and col is not None and isinstance(stored.get("modes"), dict)
    if modes or recap:
        if col is None and not collar:                  # a collar an earlier --collar run stored still caps T
            col = stored.get("collar")
            if col is not None:
                print(f"modes: T capped by the stored collar y{col} (face-frame.json)")
        if recap:
            print(f"modes: re-derived with the new collar y{col} (the stored modes predate it, and it caps T)")
        landscape = w * FRAME_H / h if reframe else None
        mids = [x for x in shoulder_mids(imgs) if x is not None]       # the same stills the face was read on
        neck = None
        if len(mids) >= len(imgs) / 2:
            neck = (statistics.median(mids) - x0) * sx
            print(f"shoulders: the midpoint (the neck) on x{neck:.0f} of the wide frame, {neck - cx:+.0f} px from the "
                  f"face-box centre ({len(mids)} of {len(imgs)} stills): W, S and T centre it")
        else:
            print(f"⚠ shoulders seen on {len(mids)} of {len(imgs)} stills (a tight shot, a shoulder out of frame): W and S "
                  "centred as measured, T on the face (layout.md § 2)")
        m, notes = compute_modes((cx, cy), fh, hair, w_centre_x(w, x0, crop_w), col, landscape=landscape, shoulders=neck)
        result["modes"] = m
        for n in notes:
            print(f"⚠ {n}")
        print("modes: " + "  ".join(f"{k} scale {v['scale']} centre ({v['centre'][0]}, {v['centre'][1]})"
                                    for k, v in m.items()))
    fits = stored.get("span_modes") or []
    if collar and result.get("collar") is not None and fits and stored.get("collar") != result["collar"]:
        # a --span fit's T is capped by the collar stored when it was fitted (T 2.5358 uncapped, 1.4596 under the
        # collar, 2026-10-13), and the plan's layout rows carry the `frame` pasted from it: name them for a re-fit
        was = f"y{stored['collar']}" if stored.get("collar") is not None else "no collar"
        print(f"⚠ {len(fits)} --span fit(s) predate this collar (y{result['collar']}; the stored one was {was}), "
              "and the collar caps a fit's T: re-fit them, then paste each printed `frame` into its layout rows again:")
        print("    uv run workflows/face-frame.py <job> "
              + " ".join(f"--span {e['start']:.3f} {e['end']:.3f}" for e in fits) + " --modes")
    if crowns:
        import numpy as np
        plate = np.median(np.stack([i.astype(np.float32) for i in fimgs]), axis=0)
        found, missing = measure_crowns(video, crowns, edl, x0, crop_w, cx, ftop, plate)
        result["crowns"] = found
        if missing:
            unmeasured.append("crown")

    if out:
        result = merge_out(out, result)                 # a bare re-measure keeps the preset's modes, collar and crowns
        with open(out, "w", encoding="utf-8") as fp:
            json.dump(result, fp, indent=2)
        print(f"wrote {out}")

    if annotate:
        annotate_frame(imgs[len(imgs) // 2], result, annotate, sy)
    if unmeasured:
        print(f"UNMEASURED: {', '.join(unmeasured)} (exit {EXIT_UNMEASURED})")
        sys.exit(EXIT_UNMEASURED)
    return result


def annotate_frame(img, result, out, sy=1.0):
    import cv2
    from cv2_io import imwrite
    f = result["face"]
    x, y = f["cx"] - f["w"] // 2, f["cy"] - f["h"] // 2
    cv2.rectangle(img, (x, y), (x + f["w"], y + f["h"]), (0, 0, 255), 6)
    if "hair_top" in result:  # frame px → this source frame's rows
        hy = round(result["hair_top"] / sy)
        cv2.line(img, (0, hy), (img.shape[1], hy), (0, 255, 255), 3)
    imwrite(out, img)
    print(f"annotated frame → {out}")


def verify(render, annotate=None, plan=None):
    w, h, dur = probe(render)
    if (w, h) != (FRAME_W, FRAME_H):
        print(f"✗ render is {w}x{h}, expected {FRAME_W}x{FRAME_H}")
        sys.exit(1)
    spans = plan_spans(plan) if plan else None
    if spans:
        print(f"sampling the plan's {len(spans)} S spans only ({sum(b - a for a, b in spans):.1f}s)")
    imgs = sample_frames(render, sample_times(dur, SAMPLES, spans))
    boxes = detect_faces(imgs, w, h)
    if not boxes:
        print("✗ no face detected in the render")
        sys.exit(1)
    cx, cy, fw, fh, ftop = median_box(boxes)
    tops = hair_tops(imgs, cx, ftop, y_floor=VERIFY_FLOOR_Y)  # under the seam caption box: its text changes every frame
    if len(tops) >= len(imgs) / 2:
        hair = statistics.median(tops)
        target = SEAM_Y + HAIR_GAP
        off = hair - target
        label = f"hair top y{hair:.0f}  target y{target}"
    else:
        off = cy - FACE_CY_FALLBACK
        label = f"hair unmeasurable; face center y{cy:.0f}  target y{FACE_CY_FALLBACK}"
    ok = abs(off) <= VERIFY_TOL
    print(f"{label}  offset {off:+.0f}px  (tolerance ±{VERIFY_TOL})")
    print("✓ PASS — face framed on the locked standard" if ok
          else "✗ FAIL — face off the locked standard; re-run measure and rebuild")
    if annotate:
        import cv2
        from cv2_io import imwrite
        img = imgs[len(imgs) // 2]
        cv2.line(img, (0, SEAM_Y), (w, SEAM_Y), (255, 0, 0), 4)
        cv2.line(img, (0, SEAM_Y + HAIR_GAP), (w, SEAM_Y + HAIR_GAP), (0, 255, 255), 3)
        imwrite(annotate, img)
        print(f"annotated frame → {annotate}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?", help="a base cut, a raw clip, or a job folder")
    ap.add_argument("--edl", metavar="CUTS_JSON",
                    help="sample only this EDL's kept spans of the clip (default: the job's "
                         "transcript/cuts.json for a job folder or a clip under <job>/raw/)")
    ap.add_argument("--out", metavar="JSON",
                    help="write the result here instead of <job>/face-frame.json")
    ap.add_argument("--verify", metavar="RENDER")
    ap.add_argument("--plan", metavar="PLAN",
                    help="with --verify: sample only the S spans of this graphics-plan.json (or job folder); with --collar: "
                         "read the collar only on its W, O and T spans")
    ap.add_argument("--annotate", metavar="OUT_PNG")
    ap.add_argument("--modes", action="store_true",
                    help="write the W/S/T footage transforms into face-frame.json `modes` (layout.md § 2)")
    ap.add_argument("--collar", action="store_true",
                    help="measure the collar/skin line on the wide framing into `collar` (exit 3 = UNMEASURED)")
    ap.add_argument("--crown", nargs=2, type=float, action="append", metavar=("A", "B"),
                    help="the tallest crown over timeline span A-B s into `crowns` (repeatable; exit 3 = UNMEASURED)")
    ap.add_argument("--span", nargs=2, type=float, action="append", metavar=("A", "B"),
                    help="with --modes: fit the W/S/T transforms to timeline span A-B s alone, into `span_modes` "
                         "(repeatable; the layout row `frame` for that span is printed)")
    a = ap.parse_args()
    if a.span:
        if not (a.modes and a.video) or a.verify or a.collar or a.crown:
            ap.error("--span goes with --modes on a job folder (or a raw with its EDL), alone")
        measure_spans(a.video, a.edl, a.out, [tuple(x) for x in a.span])
        sys.exit(0)
    if a.plan and not (a.verify or a.collar):
        ap.error("--plan goes with --verify or --collar")
    if a.verify:
        verify(a.verify, annotate=a.annotate, plan=a.plan)
    elif a.video:
        video, spans, edl, out = resolve(a.video, a.edl, a.out)
        if a.plan and a.collar and not edl:
            ap.error("--collar --plan maps the plan's spans through the EDL: measure a job folder or a raw with its cuts.json")
        measure(video, annotate=a.annotate, spans=spans, edl=edl, out=out,
                modes=a.modes, collar=a.collar, crowns=[tuple(c) for c in a.crown or []], plan=a.plan if a.collar else None)
    else:
        ap.error("give a base cut, a raw clip or a job folder to measure, or --verify RENDER")
