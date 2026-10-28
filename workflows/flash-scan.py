#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""flash-scan.py: the whole-program gate for single-frame flashes, double cuts and unexpected hard cuts, run on each
exported file before it is delivered (where it binds: WHERE IT BINDS, below). It reads the export itself, so it needs
no extra draft.

  uv run workflows/flash-scan.py <video>                                   # flashes + double cuts; every hard cut listed
  uv run workflows/flash-scan.py <video> --expect projects/<job>           # + every hard cut checked against the plan
  uv run workflows/flash-scan.py <video> --expect projects/<job> --variant ad    # the ad deliverable's own boundaries
  uv run workflows/flash-scan.py <video> --expect-times 4.63,7.84 ...      # + checked against these times (seconds)
  ... --json OUT.json                                                      # every cut and finding, machine-readable

WHY. On a layered edit every planned boundary is several layers switching on one frame: the footage framing, the
graphic, the caption line, the V1 clip. One layer a frame off is a frame of footage with no panel over it, a blank
panel between two shots, a caption left in the wrong band for a frame. Stills never land on it and a watch at speed
rarely sees it, but a viewer's eye does. It only exists in the finished composite, so it is measured there.

HOW. ffmpeg decodes every frame to a 90 px-wide grey thumbnail (90x160 on 9:16, 160x90 on 16:9: exact enough to see a
panel, small enough for a whole program in seconds), with passthrough sync (a constant-rate read duplicates a frame on any file
with audio). D[i] is the mean absolute difference between frame i-1 and frame i, on 0-255 grey. Then:
  FLASH       frame i differs from BOTH neighbours (D[i] and D[i+1] >= 2) while the neighbours match each other
              (|f[i+1] - f[i-1]| <= 0.4 x the smaller of the two). A stray frame, a blank panel body for one frame, a
              card missing for one frame.
              The same rule runs again on the frames' CONTENT: C[i] is the mean |difference| between frame i-1's and
              frame i's grey values each SORTED (the change no rearrangement of the pixels explains, so motion is
              nearly free), and the rule asks C instead of D. That is the flash INSIDE a moving graphic: mid-slide the
              neighbours never match pixel for pixel (a ranking row moving down differs two frames apart by its own
              travel), so D alone cannot call a blank or a wrong state there, while their content still matches
              (a member's ranking video, 2026-10-13: "it flashed a little bit ... only does that sometimes"). A content
              flash also needs the change in and the change out ALIKE (the smaller D at least half the larger: a stray
              frame comes and goes the same way), so a scroll that lands with a message one frame into its fade-in,
              which swaps content without a stray state, stays motion; and the content HELD on both sides (the
              content changes into the frame before and out of the frame after at most SETTLE of the flash's: motion
              keeps its content, a stray frame alone changes it), so a fast page scroll, whose content turns over at
              the frame edges on every frame of it, stays motion. It is asked only where FLASH and DOUBLE CUT found
              nothing.
  DOUBLE CUT  a shot one or two frames long between two hard changes, the picture HELD on both outer sides: the two
              diffs before the first change and the two after the last are each at most half of the change they
              border. One frame: two or three changes on consecutive frames, each frame between them a one-frame
              shot. Two frames: two changes two frames apart, the diff between them at most half of the smaller. A
              panel landing a frame or two after its framing switch, a blank frame between two shots, a caption line
              changing a frame after the picture, a V1 cut landing a frame or two before its layout switch.
              A change is hard at D >= 6.5, or from D >= 2 on a planned boundary of its OWN (--expect: within 1
              frame of it and nearer it than the shot's other change): a V1 jump cut inside one framing moves the
              whole frame by only 3-6, and two planned boundaries one or two frames apart are the defect however
              small either change is. "Of its own" keeps a frame of wobble just after a planned cut from borrowing
              that cut's boundary. A two-frame shot also needs one of its changes on a planned boundary, so it is
              judged only against a plan: off the plan, a graphic or a screen capture animated on twos (each drawing
              held two frames) has exactly this shape.
              The hold is two frames because a stepped scroll (two frames moving, one holding: a terminal log, a
              feed) looks like a pair of cuts against one held frame, and never holds for two; and an entrance
              animated on twos steps again two frames after its first step, so a cut into one stays motion.
  HARD CUT    one change (D >= 8) at least twice the diff on either side of it.
Every finding must also stand at least 4x above the local motion: the median diff over the 8 frames on each side of
it (the event and its borders left out), the calmer side (a content flash, above the local CONTENT change). A
jittering or shaking graphic is busy on both sides, so it stays motion; a real stray frame has at least one calm
side, even inside a capture that drifts.
Four or more hard changes in a row are motion (a fast slide), never three one-frame shots.

ON A GRAPHIC'S OWN RENDER (render_scan(), called by workflows/graphics-qa.py and workflows/graphics-qa-short.py on
every placed render, the 5b->5c gate every graphics pass runs, as their `stray` check): an overlay is scaled
premultiplied, composited over mid-grey and measured only over the pixels it ever covers (grown 3 px), so a small card
that blanks for a frame is a whole-region change there, where on the export it is under any whole-frame floor; read at
RENDER_SIDE (180) on the short side. Only FLASH is asked: a render's scene cuts are its own, and a recording that zooms
in three steps reads as one-frame shots. Two or more flash frames in a row are an alternation (a file list scrolled a
row a frame aliases on the thumbnail), not a stray frame. A content flash on a render must also change the INK it
carries (its mean grey and mean alpha over the region, the same at any position and any sub-pixel phase): sorted
values are not phase-free, and an edge eased through a third of a thumbnail pixel reads one (a 1 % chip rising, 4.7).
A FLASH frame that is its neighbours' picture MOVED is a frame of a shake, and motion (shaken(), 2026-10-15): each of
the three frames is moved rigidly onto the others (within SHAKE, to a sixteenth of a pixel) and the FLASH rule asked
again on what is left: when the neighbours still differ by more than MATCH times what is left between the frame and
the nearer of them, it no longer holds; the frame's content is still asked. The Talking Head Explainer's call card
buzzes x +-5 px on every frame of a ring burst; on 24000/1001 the burst's second frame (+4.27 px, between -5 and
-3.54) read 4.88 in, 4.75 out against neighbours 1.75 (0.37), a FLASH on every rung card (the kit smoke's g6, its 2nd
and 3rd bursts); moved, 1.70 and 1.50 against 1.55 (1.04). A stray frame inside a shake stays a FLASH (the card's name
gone mid-buzz: 16.1 left against 1.6), and so does a still picture moved on one frame alone: its neighbours match
unmoved, nothing is left between them.
Swept 2026-10-14 over every render on disk of 13 jobs (1,637, captions left out): 26 renders carry a finding, each
event viewed and every one real, none on a placed version that shipped. On the 9:16 short, 19 earlier versions of five
capture cells: the chat body or its composer gone for a frame (graphics-qa-short's `ink` names those too), and what no
check named, a frame of another capture between two of the chat and a hover tooltip up for one frame. On a long-form
job, where no check looked: a CapCut viewer that drew the picture small for one frame inside a capture, a text
animation's serif word under a glow box for one frame, a bar 8 px taller for one frame, a Finder icon that blinked.
What it passed on the way: a recording zooming in three steps, a file list scrolled a row a frame, type easing through
half a thumbnail pixel, a page scrolled fast.

EXPECTED BOUNDARIES (--expect projects/<job>). A hard cut within 1 frame of one is expected; any other is an UNEXPECTED
CUT, a WARNING (a capture's own UI cuts: a message arriving, a page loading, an element that pops in one frame). Read
each one: it is a capture event or a boundary that landed off its plan. The boundaries come from graphics-plan.json and
transcript/cuts.json:
  - a plan with a top-level `layout` array (the talking-head explainer contract) goes through that preset's
    layout.py `breaks()`: the V1 cuts, every layout edge, every graphic cell's edges and every cell's `shot_cuts`,
    the same list its caption breaks are forced on;
  - any other plan: the V1 cuts, every graphic cell's start and end, and its `shot_cuts`.
--variant NAME composes the plan's `variants.NAME` in (layout.py compose_variant) and reads transcript/cuts.NAME.json.
The file's frame count is compared with the plan's duration: a mismatch means the wrong deliverable or a partial
export, and is warned.

THE LIMIT. A whole-frame mean sees what changes a visible share of the frame. A blank chat body under a pinned header
barely moved it on a mostly dark panel: the job-local scan this replaces missed two, because its hard-cut floor sat far
above them. At these floors both read here (one as a flash, one as a double cut). A defect confined to a small region
(a caption word, a single icon) is below any whole-frame floor; the per-graphic gates own those
(`workflows/graphics-qa-short.py`, the caption builder's own check).
A layer a frame or two off a planned boundary with a change under 6.5 (a caption line a frame late on a big cut, a
V1 jump cut a frame early) has no boundary of its own, so it cannot be told from motion and is not seen here; the
talking-head explainer's layout.py L-NEARCUT keeps such edges out of the plan, not a lane from landing a layer off
one. The other way round, a graphic built to land two frames after a planned cut, or one that steps once on twos out
of it and holds, reads as a two-frame shot: put it on the cut.

Calibrated (2026-09-23) on 15 exports of one 2-minute 9:16 talking-head explainer (13 drafts, the final organic and
the ad; 43k frames), every candidate viewed: the positives were the two blank chat bodies above, a blank panel frame
between two capture shots, a frame of the old capture's empty backdrop between two shots, and a split panel arriving
with the previous caption still in the old band; 0 findings on the shipped final and ad. Stepped terminal-log scrolls,
a jittering window stack, a chat app's send animation and cuts into an entrance animation all stay motion. Each floor
sits inside the band where the corpus reads clean with every positive found: HARD 6-7.9 (5.5 fails a chat input box
growing as its text wraps; 8 misses a blank panel at 7.96), SETTLE 0.45-0.5 (0.4 misses the caption lag at 0.43; 0.55
fails a cut into an entrance animation), LOCAL 1-8 (10 misses the stray frame inside a drifting capture), MATCH
0.4-0.6 (0.8 fails the jittering stack; the real flash read 0.14), HOLD 2 (3 misses the triple; 1 fails a stepped
scroll whose steps pass HARD, the synthetic control).
The shipped final still warns 8 unexpected cuts against its plan as it stands (5 when calibrated), every one a
graphic's own event: a montage's shots, chat messages arriving in a capture, icons stepping in and out on twos.
Re-checked (2026-09-25) for the two-frame shot and the planned-boundary floor: the 15 exports read exactly as before,
the final with its plan too, and so do the final's Final Cut and Resolve rebuilds and the receptionist short (final
with its plan, ad), whose graphic exits in two steps on twos (7.6 then 7.5, off the plan: the rule that keeps it
motion). The closest calls in the corpus are the final's icons: a cut into their entrance on twos (106, 12.6, 9.0,
two frames apart; HOLD keeps it out) and a shrink on twos (8.2 then 5.0, off the plan). The positives are the Final
Cut rebuild of demo-project: four two-frame shots, a V1 jump cut (5.1-10.6) two frames before its layout switch
(43-47), both on planned boundaries; its fifth short shot, a V1 cut landed a frame before a planned switch (5.4 then
52.5), is THE LIMIT's lagging layer. Viewed then, the corpus's drafts carry three one-frame shots no version of this
scan sees without their plans, which are gone: a V1 jump cut a frame before a full-screen (5.3 then 44.9 in the
first two drafts) or before a panel and caption change (3.7 then 14.8 there, 4.2 then 7.0-10.6 in v2-v10), and a
caption line a frame late on a cut (52.0 then 3.2 in the first two).
The content flash (2026-10-14): a ranking list over footage, one row sliding three places while the rows below rise
(about 80 px a frame at 1080 at its fastest), with one frame planted mid-move: the whole graphic blank (D 23 in, 24
out, but the neighbours 22 apart pixel for pixel: no FLASH, no double cut) and the rows back at their first state for
a frame (20/21, 22 apart) both passed; their content reads 14 and 4.6 against neighbours matching to 0.8-0.9. Re-run
then on 30 exports (the 18 of this short's drafts, previews, final and ad, the receptionist short's two deliverables,
three long-form masters and seven clips, 142k frames): every old finding unchanged and no new one. The two content
candidates stay motion: a chat scroll landing one frame into a message's fade-in (6.9 in, 2.2 out: not ALIKE) and a
long-form master's scrub montage of one-frame shots (its content turns over every frame: not HELD). The floor is
FLASH_MIN: the sub-floor content flashes in that corpus (1.0-1.6, D the same: the whole frame a shade off for one
frame) sit in a 4K screen-recording master and the webcam testimonials.

WHERE IT BINDS. The method is format-agnostic (any aspect, any plan), but exit 1 stops a delivery only where a step-8
definition of done names this scan. The talking-head explainer's does: its README § Export, on every deliverable, the
ad with --variant ad. The house step-8 row (edit-video's step table, CLAUDE.md pipeline row 8) is where it becomes
every job's gate. A format whose definition of done does not name it runs it as a report line, not a stop; and since
the floors above were calibrated on 9:16 only, a first run on a 16:9 program is read finding by finding before its
exit code is trusted. Exit 0 does not mean every hard cut was expected: read the warnings.

Exit 0 = no flash, no double cut (unexpected cuts are warnings). Exit 1 = a flash or a double cut. Exit 2 = the video
or an --expect input cannot be read.
"""
import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
import numpy as np

REPO = Path(__file__).resolve().parent.parent
LAYOUT_PY = REPO / "presets" / "instagram" / "talking-head-explainer" / "layout.py"

SHORT_SIDE = 90     # px: the thumbnail's short side (90x160 on 9:16)
FLASH_MIN = 2.0     # grey levels: a flash frame differs from each neighbour by at least this
MATCH = 0.4         # a flash's neighbours match: |f[i+1] - f[i-1]| <= MATCH x the smaller of its two diffs
ALIKE = 0.5         # a content flash comes and goes the same way: the smaller of D[i], D[i+1] >= ALIKE x the larger
GREY = 128          # a render's overlay is composited over this grey, the backdrop no graphic colour is far from
HARD = 6.5          # grey levels: a change inside a double cut
CUT = 8.0           # grey levels: a lone hard cut
SETTLE = 0.5        # the diffs beside a double cut are at most this share of the change they border
HOLD = 2            # frames: the picture holds this long on each side of a double cut (a stepped scroll never does)
SPIKE = 2.0         # a lone hard cut is at least this many times the diff on either side of it
LOCAL = 4.0         # every finding stands this many times above the local motion
WINDOW = 8          # frames either side the local motion is measured over
MAX_RUN = 3         # hard changes in a row that can still be one-frame shots; more is motion
TOLERANCE = 1       # frames: a hard cut this close to an expected boundary is expected
COVER = 40          # 8-bit alpha (thumbnail): a render's pixel that reaches this on any frame is part of the graphic
RENDER_SIDE = 180   # px: a render's thumbnail short side. At 90, type moving half a thumbnail pixel a frame
                    # alternates its sub-pixel phase and its CONTENT read a flash (three text chips, 2026-10-14)
SHAKE = 3.0         # render thumbnail px (18 px on a 1080 render): the farthest a flash frame is moved looking for the
                    # shake it is part of (the call card's +-5 px buzz moves at most 10 px a frame, 9.3 on 24000/1001)


class InputError(Exception):
    """An input that cannot be read: exit 2, named."""


# ── the video ───────────────────────────────────────────────────────────────────────────────────────────────────────
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,avg_frame_rate,r_frame_rate", "-of", "json", str(path)],
                       capture_output=True, text=True)
    if r.returncode:
        raise InputError(f"ffprobe cannot read {path}: {(r.stderr.strip().splitlines() or ['?'])[-1]}")
    streams = json.loads(r.stdout or "{}").get("streams") or []
    if not streams:
        raise InputError(f"{path}: no video stream")
    s = streams[0]
    fps = None
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:  # Windows ffprobe builds can print a trailing comma
            v = Fraction(str(s.get(key) or "0/0").strip().rstrip(","))
        except (ValueError, ZeroDivisionError):
            continue
        if v > 0:
            fps = float(v)
            break
    if not fps:
        raise InputError(f"{path}: no frame rate")
    return int(s["width"]), int(s["height"]), fps


def thumb_size(w, h, side=SHORT_SIDE):
    """The grey thumbnail: `side` on the short side, the aspect kept, even sides."""
    if w <= h:
        return side, max(2, int(round(side * h / w / 2)) * 2)
    return max(2, int(round(side * w / h / 2)) * 2), side


def diffs(frames, mask=None):
    """(D, M, C, CM) over grey frames (int16), read over `mask` when one is given: D[i] = mean |f[i] - f[i-1]| (D[0] =
    0), M[i] = mean |f[i+1] - f[i-1]| (0 at the two ends), and C, CM the same on each frame's values SORTED (the content
    change: what no rearrangement of the pixels explains). Streamed: a long program never sits in memory."""
    D, M, C, CM = [0.0], [], [0.0], []
    prev2 = prev1 = None
    for f in frames:
        if mask is not None:
            f = f[mask]
        s = np.sort(f, axis=None)
        if prev1 is not None:
            D.append(float(np.abs(f - prev1[0]).mean()))
            C.append(float(np.abs(s - prev1[1]).mean()))
        if prev2 is not None:
            M.append(float(np.abs(f - prev2[0]).mean()))
            CM.append(float(np.abs(s - prev2[1]).mean()))
        prev2, prev1 = prev1, (f, s)
    n = len(D) if prev1 is not None else 0
    pad = lambda x: np.array([0.0] + x + [0.0])[:n]
    return np.array(D[:n]), pad(M), np.array(C[:n]), pad(CM)


def _thumbs(path, tw, th, pix):
    """Every frame of `path` as a (th, tw, planes) uint8 array at the thumbnail size, area-scaled, passthrough sync."""
    planes = 2 if pix == "ya8" else 1
    size = tw * th * planes
    # with alpha, scaled PREMULTIPLIED: an edge pixel then carries exactly its share of the ink, whatever colour a
    # transparent pixel was left holding
    pre = "format=rgba,premultiply=inplace=1," if pix == "ya8" else ""
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v:0", *passthrough(),
           "-vf", f"{pre}scale={tw}:{th}:flags=area,format={pix}", "-f", "rawvideo", "-pix_fmt", pix, "-"]
    got = 0
    with tempfile.TemporaryFile() as errf:  # a file, not a pipe: a damaged export can print an error per frame
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf) as p:
            while True:
                buf = p.stdout.read(size * 64)
                if not buf:
                    break
                while len(buf) % size:  # a pipe read can stop mid-frame
                    more = p.stdout.read(size - len(buf) % size)
                    if not more:
                        break
                    buf += more
                n = len(buf) // size
                got += n
                yield from np.frombuffer(buf[:n * size], np.uint8).reshape(n, th, tw, planes)
        errf.seek(0)
        err = errf.read().decode(errors="replace").strip()
    if not got:
        raise InputError(f"ffmpeg decoded no frames from {path}: {(err.splitlines() or ['?'])[-1]}")


def measure(path, tw, th):
    """(D, M, C, CM) (diffs()) on the grey thumbnails of every frame."""
    return diffs(f[..., 0].astype(np.int16) for f in _thumbs(path, tw, th, "gray"))


# ── the scan ────────────────────────────────────────────────────────────────────────────────────────────────────────
def local_motion(D, a, b):
    """The motion an event D[a..b] must stand above: the median diff over WINDOW frames on each side of it (the event
    and the two diffs bordering it left out), the calmer side. A jittering or scrolling graphic is busy on both sides;
    a real cut or stray frame has at least one calm side, even when it lands inside a moving capture."""
    before = D[max(1, a - 1 - WINDOW):max(1, a - 1)]
    after = D[b + 2:b + 2 + WINDOW]
    sides = [float(np.median(x)) for x in (before, after) if len(x)]
    return min(sides) if sides else 0.0


def one_frame(X, XM, i):
    """Frame i differs from both neighbours by X while they match each other by XM, above the local X (FLASH)."""
    lo = min(X[i], X[i + 1])
    return lo >= FLASH_MIN and XM[i] <= MATCH * lo and lo >= LOCAL * local_motion(X, i, i + 1)


def content_flash(D, C, CM, i):
    """FLASH on the content (see HOW): frame i a stray inside motion, the change in and out alike, the content held
    either side. The entry, or None."""
    n = len(D)
    d = lambda k: float(D[k]) if 0 <= k < n else 0.0
    c = lambda k: float(C[k]) if 0 <= k < n else 0.0
    if (one_frame(C, CM, i) and min(d(i), d(i + 1)) >= ALIKE * max(d(i), d(i + 1))
            and max(c(i - 1), c(i + 2)) <= SETTLE * min(c(i), c(i + 1))):
        return dict(frames=[i], into=round(float(C[i]), 2), out=round(float(C[i + 1]), 2),
                    neighbours=round(float(CM[i]), 2), content=True)
    return None


def scan(D, M, expected=(), C=None, CM=None):
    """{'flashes': [...], 'doubles': [...], 'cuts': [...]} on the frame diffs. A flash or double cut names its one- or
    two-frame shot(s); a cut names the first frame of the new picture. `expected`: the planned boundary frames, where a
    change inside a double cut counts from FLASH_MIN instead of HARD (planned(), below). C, CM (diffs()): the content
    change, where a frame no rule above took is asked FLASH again (a flash inside motion)."""
    n = len(D)
    d = lambda i: float(D[i]) if 0 <= i < n else 0.0
    flashes, doubles, taken = [], [], set()
    expected = set(expected)

    def planned(k, others):
        """A boundary of k's own: within TOLERANCE of k and nearer k than any other change of the shot. A frame of
        encoder or footage wobble just after a planned cut is nearer the cut's change: it never borrows its boundary."""
        return any(b in expected and all(abs(b - k) < abs(b - o) for o in others)
                   for b in range(k - TOLERANCE, k + TOLERANCE + 1))

    def change(k, shot):
        return d(k) >= HARD or (d(k) >= FLASH_MIN and planned(k, [o for o in shot if o != k]))

    def settled(i, j):
        return (max(d(i - k) for k in range(1, HOLD + 1)) <= SETTLE * D[i]
                and max(d(j + k) for k in range(1, HOLD + 1)) <= SETTLE * D[j])

    # FLASH: frame i differs from both neighbours, and the neighbours match
    for i in range(1, n - 1):
        if one_frame(D, M, i):
            flashes.append(dict(frames=[i], into=round(d(i), 2), out=round(d(i + 1), 2),
                                neighbours=round(float(M[i]), 2)))
            taken.add(i)

    # DOUBLE CUT: 2..MAX_RUN hard changes in a row, the picture settled on both sides of them
    for i in range(1, n):
        for j in range(i + 1, min(n, i + MAX_RUN)):
            shot = range(i, j + 1)
            if any(k in taken for k in range(i, j)) or not all(change(k, shot) for k in shot):
                continue
            lo = float(D[i:j + 1].min())
            if settled(i, j) and lo >= LOCAL * local_motion(D, i, j):
                if j == i + 1 and M[i] <= MATCH * lo:   # the two neighbours match: a flash after all
                    flashes.append(dict(frames=[i], into=round(d(i), 2), out=round(d(j), 2),
                                        neighbours=round(float(M[i]), 2)))
                else:
                    doubles.append(dict(frames=list(range(i, j)), changes=list(range(i, j + 1)),
                                        diffs=[round(d(k), 2) for k in range(i, j + 1)]))
                taken.update(range(i, j))
                break

    # DOUBLE CUT, a two-frame shot: two changes two frames apart, the frame between them held, settled on both sides,
    # at least one of them on a planned boundary (an animation or a capture on twos has this shape off the plan)
    on_plan = lambda k: any(b in expected for b in range(k - TOLERANCE, k + TOLERANCE + 1))
    for i in range(1, n - 2):
        j = i + 2
        if (i in taken or i + 1 in taken or not (on_plan(i) or on_plan(j))
                or not (change(i, (i, j)) and change(j, (i, j)))):
            continue
        lo = min(d(i), d(j))
        if d(i + 1) <= SETTLE * lo and settled(i, j) and lo >= LOCAL * local_motion(D, i, j):
            doubles.append(dict(frames=[i, i + 1], changes=[i, j], diffs=[round(d(i), 2), round(d(j), 2)]))
            taken.update((i, i + 1))

    # FLASH on the content: a stray frame inside motion, the change in and out alike, the content held either side
    if C is not None:
        for i in range(1, n - 1):
            e = None if i in taken else content_flash(D, C, CM, i)
            if e:
                flashes.append(e)
                taken.add(i)

    # HARD CUT: one change, well above the diffs either side of it
    cuts = []
    for i in range(1, n):
        if (D[i] >= CUT and D[i] >= SPIKE * max(d(i - 1), d(i + 1))
                and D[i] >= LOCAL * local_motion(D, i, i)):
            cuts.append(dict(frame=i, diff=round(d(i), 2)))
    flashes.sort(key=lambda e: e["frames"][0])
    doubles.sort(key=lambda e: e["frames"][0])
    return dict(flashes=flashes, doubles=doubles, cuts=cuts)


# ── the expected boundaries ─────────────────────────────────────────────────────────────────────────────────────────
def _load_json(path, what):
    if not path.is_file():
        raise InputError(f"{what}: no file at {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise InputError(f"{what}: {path} is not JSON ({e})")


def _layout_module():
    if not LAYOUT_PY.is_file():
        raise InputError(f"the plan carries a `layout` array but {LAYOUT_PY} is missing")
    spec = importlib.util.spec_from_file_location("talking_head_layout", LAYOUT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fps(v):
    if isinstance(v, str) and "/" in v:
        n, dd = v.split("/")
        return float(n) / float(dd)
    return float(v)


def _v1_cuts(cuts, plan):
    """The interior V1 cuts on the plan's clock: the `_timeline` readback when every segment carries one, else the
    cumulative kept durations (the same reading as layout.py's v1_cuts)."""
    segs = (cuts or {}).get("segments") or []
    off = float(plan.get("timeline_offset") or 0)
    if segs and all(isinstance(s.get("_timeline"), list) for s in segs):
        ends = [float(s["_timeline"][1]) - off for s in segs]
    else:
        t, ends = 0.0, []
        for s in segs:
            t += float(s["end"]) - float(s["start"])
            ends.append(t)
    return ends[:-1]


def job_expectations(job, variant=None):
    """(times, plan, source): every expected hard-cut time (seconds, plan clock) for this job's export."""
    job = Path(job)
    plan = _load_json(job / "graphics-plan.json", "graphics-plan.json")
    if plan.get("fps") is None or plan.get("duration") is None:
        raise InputError(f"{job / 'graphics-plan.json'}: needs `fps` and `duration`")
    layout = None
    if variant:
        if not (plan.get("variants") or {}).get(variant):
            raise InputError(f"graphics-plan.json has no `variants.{variant}`")
        layout = _layout_module()
        try:
            plan = layout.compose_variant(plan, variant)
        except Exception as e:  # layout.MissingInput: the variant lacks `from` or `layout`
            raise InputError(f"layout.py cannot compose `variants.{variant}` ({e})")
    cp = job / "transcript" / (f"cuts.{variant}.json" if variant else "cuts.json")
    if variant and not cp.is_file():
        cp = job / "transcript" / "cuts.json"
    cuts = _load_json(cp, cp.name)
    if plan.get("layout"):
        layout = layout or _layout_module()
        try:
            times = list(layout.breaks(plan, cuts))
        except Exception as e:  # layout.LayoutError / MissingInput: the layout array itself is broken
            raise InputError(f"layout.py cannot resolve the plan's `layout` ({e}); run layout.py on the job first")
        source = f"{cp.name} V1 cuts, layout edges, graphic cell edges and shot_cuts (layout.py)"
    else:
        times = list(_v1_cuts(cuts, plan))
        for c in plan.get("beats") or plan.get("cells") or []:
            if not c.get("graphic") or c.get("kind") == "captions" or c.get("id") == "captions":
                continue
            times += [float(c.get("start", 0)), float(c.get("end", 0))]
            times += [float(t) for t in c.get("shot_cuts") or []]
        source = f"{cp.name} V1 cuts, graphic cell edges and shot_cuts"
    return sorted(set(round(float(t), 6) for t in times)), plan, source


def parse_times(text):
    try:
        return sorted(float(x) for x in re.split(r"[,\s]+", text.strip()) if x)
    except ValueError:
        raise InputError(f"--expect-times: not a list of seconds: {text!r}")


# ── a graphic's own render ──────────────────────────────────────────────────────────────────────────────────────────
def render_scan(path):
    """FLASH on one render, no plan (see ON A GRAPHIC'S OWN RENDER): {'frames', 'fps', 'cover' (the share of the frame
    it ever covers), 'flashes'}, frame numbers on the render's own clock."""
    w, h, fps = probe(path)
    tw, th = thumb_size(w, h, RENDER_SIDE)
    stack = np.stack(list(_thumbs(path, tw, th, "ya8")))
    covered = stack[..., 1].max(axis=0) >= COVER
    if not covered.any():
        return dict(frames=len(stack), fps=fps, cover=0.0, flashes=[])
    for _ in range(3):              # grown 3 px past the ink: an edge moving inside it keeps its values
        g = covered.copy()
        g[1:] |= covered[:-1]; g[:-1] |= covered[1:]; g[:, 1:] |= covered[:, :-1]; g[:, :-1] |= covered[:, 1:]
        covered = g

    def over_grey(f):               # premultiplied luma over the grey
        return np.rint(f[..., 0] + GREY * (255 - f[..., 1].astype(np.float32)) / 255).astype(np.int16)

    D, M, C, CM = diffs((over_grey(f) for f in stack), covered)
    # the ink a frame carries (its mean grey and its mean alpha over the region) is the same at any position and any
    # sub-pixel phase, where its sorted values are not: an edge eased through a third of a pixel reads a content flash
    # (a 1 % chip rising 20 px a frame, 4.7). A content flash on a render must change the ink too.
    ink = np.array([[f[covered].mean(), a[covered].mean()]
                    for f, a in ((over_grey(f), f[..., 1].astype(np.float32)) for f in stack)])
    step = lambda k, j: float(np.abs(ink[k] - ink[j]).max()) if 0 <= j < len(ink) else 0.0
    V = np.array([0.0] + [step(k, k - 1) for k in range(1, len(ink))])
    VM = np.array([0.0] + [step(k + 1, k - 1) for k in range(1, len(ink) - 1)] + [0.0])[:len(ink)]
    ink_ok = lambda e: not e.get("content") or one_frame(V, VM, e["frames"][0])
    flashes = [e for e in scan(D, M, (), C, CM)["flashes"] if ink_ok(e)]
    at = {e["frames"][0] for e in flashes}
    flashes = [e for e in flashes if not ({e["frames"][0] - 1, e["frames"][0] + 1} & at)]   # a run alternates
    kept = []
    for e in flashes:               # a frame of a shake is motion; what it carries is still asked on its content
        i = e["frames"][0]
        if e.get("content") or not shaken(*(over_grey(stack[k]).astype(np.float32) for k in (i - 1, i, i + 1)), covered):
            kept.append(e)
        elif (ce := content_flash(D, C, CM, i)) and ink_ok(ce):
            kept.append(ce)
    return dict(frames=len(stack), fps=fps, cover=round(float(covered.mean()), 3), flashes=kept)


def moved(a, b, mask, reach=SHAKE):
    """The mean |a - b| over `mask` once `a` is moved rigidly onto `b`: the best move within `reach` px either way,
    found on whole pixels, then quarters, then sixteenths (bilinear, the frame's edge held past its border)."""
    ys, xs = np.nonzero(mask)
    r = int(np.ceil(reach)) + 1
    y0, y1 = max(0, ys.min() - r), min(mask.shape[0], ys.max() + r + 1)
    x0, x1 = max(0, xs.min() - r), min(mask.shape[1], xs.max() + r + 1)
    a, b, mask = a[y0:y1, x0:x1], b[y0:y1, x0:x1], mask[y0:y1, x0:x1]
    P, (h, w) = np.pad(a, r, mode="edge"), a.shape

    def err(dx, dy):                # out[y, x] = a[y - dy, x - dx]
        sx, sy = r - dx, r - dy
        ix, iy = int(np.floor(sx)), int(np.floor(sy))
        fx, fy = sx - ix, sy - iy
        q = lambda oy, ox: P[iy + oy:iy + oy + h, ix + ox:ix + ox + w]
        out = (1 - fy) * ((1 - fx) * q(0, 0) + fx * q(0, 1)) + fy * ((1 - fx) * q(1, 0) + fx * q(1, 1))
        return float(np.abs(out - b)[mask].mean())

    span = int(np.floor(reach))
    best = min((err(dx, dy), dx, dy) for dx in range(-span, span + 1) for dy in range(-span, span + 1))
    for step in (0.25, 0.0625):
        _, bx, by = best
        best = min([best] + [(err(bx + j * step, by + k * step), bx + j * step, by + k * step)
                             for j in range(-3, 4) for k in range(-3, 4)
                             if abs(bx + j * step) <= reach and abs(by + k * step) <= reach])
    return best[0]


def shaken(prev, cur, nxt, mask):
    """A one-frame FLASH that is its neighbours' picture MOVED, inside a shake (the call card's ring buzz, x +-5 px on
    every frame of a burst): with each frame moved rigidly onto the others (within SHAKE), the FLASH rule no longer
    holds, the neighbours still differing by more than MATCH times what is left between the frame and the nearer of
    them. A still picture moved on one frame alone keeps its FLASH: its neighbours match unmoved, nothing left."""
    lo = min(moved(cur, prev, mask), moved(cur, nxt, mask))
    return moved(nxt, prev, mask) > MATCH * lo


def render_lines(r):
    """[(frame, what)] for each finding of render_scan(), in frame order: the gates' wording, kept here."""
    return sorted((e["frames"][0], f"differs {'in content ' if e.get('content') else ''}from both neighbours "
                                   f"({e['into']} in, {e['out']} out) while they match ({e['neighbours']}): a one-frame "
                                   f"flash{' inside motion' if e.get('content') else ''}") for e in r["flashes"])


# ── report ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def timecode(f, fps):
    """HH:MM:SS:FF, non-drop, counted at the nominal rate (how the editor shows 23.976 as 24)."""
    nom = max(1, int(round(fps)))
    s, ff = divmod(int(f), nom)
    return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}:{ff:02d}"


def where(f, fps):
    return f"f{f:<6d}{timecode(f, fps)}  {f / fps:8.3f} s"


def nearest(f, exp_frames):
    if not exp_frames:
        return None
    return min(exp_frames, key=lambda e: abs(e - f))


def run(video, expect=None, expect_times=None, variant=None, json_out=None, out=print):
    w, h, fps = probe(video)
    tw, th = thumb_size(w, h)
    D, M, C, CM = measure(video, tw, th)
    n = len(D)
    warnings = []

    exp_times, source = None, None
    if expect:
        exp_times, plan, source = job_expectations(expect, variant)
        pf = _fps(plan["fps"])
        if abs(pf - fps) > 0.01:
            warnings.append(f"the plan runs at {pf:.3f} fps and the file at {fps:.3f}: the boundaries are placed on the file's grid")
        want = int(round(float(plan["duration"]) * pf))
        if abs(want - n) > 1:
            warnings.append(f"the file has {n} frames and the plan{' (' + variant + ')' if variant else ''} {want}: "
                            f"the wrong deliverable, or a partial export")
    elif expect_times is not None:
        exp_times, source = expect_times, "--expect-times"
    exp_frames = sorted({int(round(t * fps)) for t in exp_times}) if exp_times is not None else None
    found = scan(D, M, exp_frames or (), C, CM)

    def at_expected(f):
        e = nearest(f, exp_frames)
        return e is not None and abs(e - f) <= TOLERANCE

    unexpected = []
    for c in found["cuts"]:
        if exp_frames is not None:
            c["expected"] = at_expected(c["frame"])
            e = nearest(c["frame"], exp_frames)
            c["nearest_expected"] = None if e is None else round(e / fps, 3)
            if not c["expected"]:
                unexpected.append(c)
    for e in found["doubles"] + found["flashes"]:
        e["t"] = round(e["frames"][0] / fps, 3)
        e["timecode"] = timecode(e["frames"][0], fps)
        if exp_frames is not None:
            ch = e.get("changes") or [e["frames"][0], e["frames"][-1] + 1]
            e["expected_boundary_near"] = [round(x / fps, 3) for x in exp_frames
                                           if ch[0] - TOLERANCE <= x <= ch[-1] + TOLERANCE]
    for c in found["cuts"]:
        c["t"] = round(c["frame"] / fps, 3)
        c["timecode"] = timecode(c["frame"], fps)

    fail = bool(found["flashes"] or found["doubles"])
    out(f"flash-scan: {video}")
    out(f"  {n} frames @ {fps:.3f} fps · {w}x{h} · read as {tw}x{th} grey")
    if exp_frames is not None:
        out(f"  expected boundaries: {len(exp_frames)} ({source}), each within {TOLERANCE} frame")
    for m in warnings:
        out(f"  ⚠ {m}")
    for e in found["flashes"]:
        fr = e["frames"]
        what = "in content " if e.get("content") else ""
        kind = ("a stray frame inside motion" if e.get("content") else
                "a stray frame" if len(fr) == 1 else f"{len(fr)} stray frames")
        out(f"  ✗ FLASH       {where(fr[0], fps)}  differs {what}from both neighbours ({e['into']} in, {e['out']} "
            f"out) while they match each other ({e['neighbours']}): {kind}")
    for e in found["doubles"]:
        fr, ch = e["frames"], e["changes"]
        two = ch[-1] - ch[0] == 2 and len(ch) == 2
        if two:
            shots, apart = f"frames {fr[0]}-{fr[-1]} are a two-frame shot", "two frames apart"
        else:
            shots = f"frame {fr[0]} is a one-frame shot" if len(fr) == 1 else f"frames {fr[0]}-{fr[-1]} are one-frame shots"
            apart = "on consecutive frames"
        near = e.get("expected_boundary_near")
        hint = ""
        if near and len(near) > 1:
            gap = round((near[-1] - near[0]) * fps)
            hint = (f"; planned boundaries {', '.join(f'{t:.3f} s' for t in near)}, {gap} frame{'s' if gap != 1 else ''} "
                    f"apart: two boundaries this close are the defect, land them on one frame")
        elif near:
            hint = f"; planned boundary {near[0]:.3f} s: one layer landed {'two frames' if two else 'a frame'} off the others"
        elif exp_frames is not None:
            hint = "; no planned boundary here"
        out(f"  ✗ DOUBLE CUT  {where(fr[0], fps)}  changes {' / '.join(str(x) for x in e['diffs'])} {apart}: "
            f"{shots}{hint}")
    for c in unexpected:
        off = "" if c["nearest_expected"] is None else \
            f"; nearest boundary {c['nearest_expected']:.3f} s, {abs(round(c['nearest_expected'] * fps) - c['frame'])} frames off"
        out(f"  ⚠ UNEXPECTED  {where(c['frame'], fps)}  hard cut ({c['diff']}) at no expected boundary{off}")
    if exp_frames is None:
        out(f"  hard cuts: {len(found['cuts'])} (no expected boundaries given: pass --expect projects/<job> to check them)")
        for c in found["cuts"]:
            out(f"    {where(c['frame'], fps)}  {c['diff']}")
    else:
        out(f"  hard cuts: {len(found['cuts'])} · {len(found['cuts']) - len(unexpected)} at an expected boundary · "
            f"{len(unexpected)} unexpected")
    verdict = "FAIL" if fail else "PASS"
    out(f"{verdict}: {len(found['flashes'])} flash{'es' if len(found['flashes']) != 1 else ''}, "
        f"{len(found['doubles'])} double cut{'s' if len(found['doubles']) != 1 else ''} · "
        f"{len(unexpected)} unexpected cut{'s' if len(unexpected) != 1 else ''} (warnings)")

    result = dict(video=str(video), frames=n, fps=fps, size=[w, h], thumb=[tw, th], verdict=verdict,
                  expected=None if exp_frames is None else dict(source=source, count=len(exp_frames),
                                                                 times=[round(t, 6) for t in exp_times]),
                  flashes=found["flashes"], double_cuts=found["doubles"], cuts=found["cuts"],
                  unexpected=[c["frame"] for c in unexpected], warnings=warnings,
                  thresholds=dict(FLASH_MIN=FLASH_MIN, MATCH=MATCH, ALIKE=ALIKE, HARD=HARD, CUT=CUT, SETTLE=SETTLE,
                                  HOLD=HOLD, SPIKE=SPIKE, LOCAL=LOCAL, WINDOW=WINDOW, MAX_RUN=MAX_RUN, TOLERANCE=TOLERANCE))
    if json_out:
        Path(json_out).write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Whole-program gate: single-frame flashes, double cuts, unexpected hard cuts.")
    ap.add_argument("video")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--expect", metavar="JOB", help="projects/<job>: the plan's boundaries are the expected cuts")
    g.add_argument("--expect-times", metavar="T,...", help="expected cut times in seconds, comma- or space-separated")
    ap.add_argument("--variant", help="with --expect: the plan's variants.<name> (e.g. ad), composed by layout.py")
    ap.add_argument("--json", dest="json_out", metavar="OUT", help="write every cut and finding here")
    a = ap.parse_args(argv)
    if a.variant and not a.expect:
        ap.error("--variant needs --expect")
    try:
        if not Path(a.video).is_file():
            raise InputError(f"no file at {a.video}")
        times = parse_times(a.expect_times) if a.expect_times is not None else None
        r = run(a.video, a.expect, times, a.variant, a.json_out)
    except InputError as e:
        print(f"flash-scan: {e}", file=sys.stderr)
        return 2
    return 1 if r["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
