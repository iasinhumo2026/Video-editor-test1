#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""zoom-to-rect.py: a push from a whole page straight onto one rectangle of it, rendered here: straight, even, blurred.

  uv run workflows/zoom-to-rect.py <video|still> --page X0,Y0,X1,Y1 --target X0,Y0,X1,Y1 [--margin M]
      (--hold N | --frames N) -o <out>.mp4
  uv run workflows/zoom-to-rect.py take-4k.mp4 --page 250,284,3590,2160 --target 715,1628 --zoom 2.1 --src-start 62
      --frames 101 -o take-panel.mp4        # a typed zoom onto a point, from source frame 62 (the first one's shape)
  uv run workflows/zoom-to-rect.py page.png --fps 24000/1001 --page 0,0,2880,1800 --target 410,980,1210,1060
      --margin 0.92 --hold 60 -o zoom.mp4   # a still: the zoom derived so the rectangle is whole in the zone

Why (2026-10-15): a short's hook zoomed from a whole dashboard page into one money figure, and every app route failed
review: "the zoom in needs to be faster and start almost immediately", "the opening zoom is not smooth at all", "why
does it zoom like the movement is to the right and then to the left? Why doesn't it just go straight to the point".
Screen Studio's own zoom clamps its camera at the window's edge (the target swings), a 2x retime jumped a whole step in
one frame, and Screen Studio rendered its motion-blurred frames brighter than its settled ones. So the take is exported
with NO zoom and the zoom is rendered here. This is the approved one-off renderer, generalised:

- frame 0 shows the PAGE (a source rectangle) filling the panel (--size, default the 1080x960 split panel): scaled to
  cover it, its top-left corner on the panel's top-left (--anchor 0.5,0.5 centres the overflow instead);
- from --start (default frame 1) a --length (default 12) frame push lands the TARGET's centre on the content point
  (--center, default the content zone's centre: (540, 522.5) on the split panel) at the final zoom. The scale grows
  GEOMETRICALLY (an even zoom rate) and the target's centre travels a STRAIGHT line on screen, both on one cubic
  in-out curve: nothing swings sideways and nothing is clamped;
- every frame of the push is the average of --samples (8) sub-frame transforms over a --shutter (180 degree) shutter
  (motion blur); every other frame is one sharp transform. Then it holds on the target.

The final zoom is --zoom typed, or, for a rectangle target without --zoom, DERIVED like the kit's fit(): the largest
zoom that keeps the rectangle whole inside the content zone (--zone, default y200-845) and the panel's width, times
--margin (captures.md § 3: name the rectangle that must be whole, never type the zoom). A point target needs --zoom.

A video is read at the frames it needs: output frame n shows source frame --src-start + n (at another --fps, the source
frame at its time), and each sub-sample reads the source frame at its own time, so a page that moves under the zoom is
sampled as it moves. Where every sub-sample of a frame lands on one source frame (always, at the source's own rate),
that one decoded frame serves them all: the fast path. A still is one frame for every sample. An untagged source is
read as BT.709, the way the editing apps read untagged HD.

The output is H.264 (libx264 CRF 10, yuv420p, the GOP libx264 picks), BT.709 matrix and tags written on the frames
(CLAUDE.md § ALPHA OVERLAYS ARE BT.709: never bare tag flags); the kit's stage re-encodes it all-intra for the renderer.
It prints the derived zoom and the frames written, and warns (⚠) where the view runs past the page rectangle or the
source frame (the push is never clamped: pick another target, zoom or anchor) and where a typed zoom puts the target
rectangle outside the zone. An existing output is refused (a placed file is never overwritten in place) unless --force.

Tests: workflows/test_zoom_to_rect.py.
"""
import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)

# Windows consoles/pipes default to cp1252 and cannot encode the status glyphs below.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

PANEL = (1080, 960)                     # the split panel
ZONE = (200.0, 845.0)                   # the split content zone (engine.SPLIT_ZONE)
START, LENGTH = 1, 12                   # one frame of the page, then a 12-frame push (the approved hook)
SAMPLES, SHUTTER = 8, 180.0             # motion blur: 8 sub-frames over a 180-degree shutter
STILLS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
TO709 = ("scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,"
         "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv")


class ZoomError(Exception):
    pass


def ease(u):
    """Cubic in-out on [0, 1], clamped."""
    u = min(1.0, max(0.0, u))
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def fit_zoom(rect, center, zone=ZONE, width=PANEL[0], margin=1.0):
    """The largest zoom that keeps the SOURCE rectangle whole inside the zone rows and the panel's width when its centre
    sits on `center`, times margin (the kit's fit(); at the zone's own centre the same numbers)."""
    x0, y0, x1, y1 = rect
    if x1 <= x0 or y1 <= y0:
        raise ZoomError(f"target {rect}: not a rectangle")
    half_w, half_h = min(center[0], width - center[0]), min(center[1] - zone[0], zone[1] - center[1])
    if half_w <= 0 or half_h <= 0:
        raise ZoomError(f"the content point {center} is outside the zone y{zone[0]:g}-{zone[1]:g} or the panel")
    return round(min(2 * half_w * margin / (x1 - x0), 2 * half_h * margin / (y1 - y0)), 4)


@dataclass
class Push:
    """The camera: the page filling the panel, then a straight, geometric push onto the target, then a hold."""
    page: tuple                         # source rect that fills the panel at the start
    target: tuple                       # source point the push lands on (a rectangle's centre)
    z1: float                           # the final zoom (source px -> panel px)
    size: tuple = PANEL
    center: tuple = (540.0, 522.5)      # the panel point the target lands on
    start: float = START
    length: float = LENGTH
    anchor: tuple = (0.0, 0.0)          # where the cover-fitted page's overflow goes: 0 = its top-left on the panel's

    def __post_init__(self):
        x0, y0, x1, y1 = self.page
        if x1 <= x0 or y1 <= y0:
            raise ZoomError(f"page {self.page}: not a rectangle")
        w, h = self.size
        self.z0 = max(w / (x1 - x0), h / (y1 - y0))
        ox = (w - self.z0 * (x1 - x0)) * self.anchor[0]
        oy = (h - self.z0 * (y1 - y0)) * self.anchor[1]
        self.s0 = (ox + (self.target[0] - x0) * self.z0, oy + (self.target[1] - y0) * self.z0)

    def progress(self, t):
        return ease((t - self.start) / self.length)

    def framing(self, t):
        """((x, y) the target's centre on the panel, zoom) at frame time t (frames, fractional)."""
        e = self.progress(t)
        z = self.z0 * (self.z1 / self.z0) ** e
        return (self.s0[0] + (self.center[0] - self.s0[0]) * e, self.s0[1] + (self.center[1] - self.s0[1]) * e), z

    def view(self, t):
        """The source rectangle on the panel at t."""
        (sx, sy), z = self.framing(t)
        (tx, ty), (w, h) = self.target, self.size
        return (tx - sx / z, ty - sy / z, tx + (w - sx) / z, ty + (h - sy) / z)

    def times(self, n, samples=SAMPLES, shutter=SHUTTER):
        """The frame times output frame n is rendered at: the shutter's sub-frames while the camera moves, else n."""
        sh = shutter / 360
        if samples > 1 and self.start - sh / 2 < n < self.start + self.length + sh / 2:
            return [n - sh / 2 + sh * (s + 0.5) / samples for s in range(samples)]
        return [float(n)]

    def warp(self, img, t):
        (sx, sy), z = self.framing(t)
        tx, ty = self.target
        # output -> input: in = target + (out - its screen position) / z
        return img.transform(self.size, Image.AFFINE, (1 / z, 0, tx - sx / z, 0, 1 / z, ty - sy / z),
                             resample=Image.BICUBIC)


def render(push, at, n, samples=SAMPLES, shutter=SHUTTER):
    """Output frame n as an HxWx3 uint8 array; at(t) is the source image at frame time t."""
    ts = push.times(n, samples, shutter)
    if len(ts) == 1:
        return np.asarray(push.warp(at(ts[0]), ts[0]), np.uint8)
    acc = np.zeros((push.size[1], push.size[0], 3), np.float32)
    for t in ts:
        acc += np.asarray(push.warp(at(t), t), np.float32)
    return (acc / len(ts) + 0.5).astype(np.uint8)


# ── sources ────────────────────────────────────────────────────────────────────────────────────────────────────────
class Still:
    def __init__(self, path):
        self.im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        self.size = self.im.size

    def at(self, t):
        return self.im

    def close(self):
        pass


def probe(path):
    """The first video stream's decoded size, rate, frame count and whether it carries a colour matrix tag."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate,avg_frame_rate,nb_frames,color_space"
                        ":stream_side_data=rotation:stream_tags=rotate", "-of", "json", str(path)],
                       capture_output=True, text=True, errors="replace")
    streams = json.loads(r.stdout or "{}").get("streams") if r.returncode == 0 else None
    if not streams:
        raise ZoomError(f"{path}: no video stream ffprobe can read ({r.stderr.strip()[:200]})")
    s = streams[0]
    # ffmpeg auto-rotates before any filter, so a phone take stored 3840x2160 with a -90 matrix decodes 2160x3840
    rot = next((sd["rotation"] for sd in s.get("side_data_list", []) if "rotation" in sd),
               s.get("tags", {}).get("rotate", 0))
    w, h = int(s["width"]), int(s["height"])
    try:
        rate = Fraction(s["r_frame_rate"])
        avg = Fraction(s.get("avg_frame_rate") or s["r_frame_rate"])
    except (ValueError, ZeroDivisionError, KeyError):
        raise ZoomError(f"{path}: no frame rate ffprobe can read") from None
    nb = s.get("nb_frames")
    return {"size": (h, w) if round(float(rot)) % 180 else (w, h), "rate": rate,
            "vfr": avg > 0 and abs(avg - rate) / rate > Fraction(1, 100),
            "frames": int(nb) if str(nb or "").isdigit() else None,
            "tagged": s.get("color_space") not in (None, "", "unknown")}


class Video:
    """Source frames read in order from --src-start, each decoded once; at(t) maps output frame time t onto the
    source frame at that time and keeps only what a later call can still ask for (calls never go back in time)."""

    def __init__(self, path, info, out_rate, src_start, last_t):
        self.size, self.first = info["size"], src_start
        self.ratio = float(info["rate"] / out_rate)
        count = self.index(last_t) - src_start + 1
        if info["frames"] is not None and src_start + count > info["frames"]:
            raise ZoomError(f"{path}: {info['frames']} frames, and the output needs source frames {src_start}-"
                            f"{src_start + count - 1}")
        vf = [f"trim=start_frame={src_start},setpts=PTS-STARTPTS"] if src_start else []
        if not info["tagged"]:
            vf.append("setparams=colorspace=bt709")   # read untagged HD the way the editing apps do
        self.proc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                                      *(["-vf", ",".join(vf)] if vf else []), *passthrough(), "-frames:v", str(count),
                                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
        self.nbytes = self.size[0] * self.size[1] * 3
        self.next, self.cache, self.path = src_start, {}, path

    def index(self, t):
        return self.first + math.floor(t * self.ratio + 0.5)

    def at(self, t):
        i = self.index(t)
        while self.next <= i:
            b = self.proc.stdout.read(self.nbytes)
            if len(b) < self.nbytes:
                raise ZoomError(f"{self.path}: the source ended at frame {self.next - 1}; the output needs frame {i}")
            self.cache[self.next] = Image.frombytes("RGB", self.size, b)
            self.next += 1
        for k in [k for k in self.cache if k < i]:
            del self.cache[k]
        return self.cache[i]

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()


# ── checks ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def overshoot(push, total, samples, shutter, rect):
    """(frames whose view runs past `rect`, the most source px past it, the edges it runs past)."""
    frames, worst, edges = [], 0.0, set()
    for n in range(total):
        over = 0.0
        for t in push.times(n, samples, shutter):
            v = push.view(t)
            for name, d in (("left", rect[0] - v[0]), ("top", rect[1] - v[1]), ("right", v[2] - rect[2]),
                            ("bottom", v[3] - rect[3])):
                if d > 0.5:
                    edges.add(name)
                    over = max(over, d)
        if over:
            frames.append(n)
            worst = max(worst, over)
    return frames, worst, edges


def span(frames):
    return f"frame {frames[0]}" if len(frames) == 1 else f"frames {frames[0]}-{frames[-1]}"


def nums(s, n, what):
    try:
        v = tuple(float(x) for x in s.replace("x", ",").split(","))
    except ValueError:
        v = ()
    if len(v) not in ((n,) if isinstance(n, int) else n):
        raise ZoomError(f"{what} {s!r}: want {n if isinstance(n, int) else ' or '.join(map(str, n))} numbers")
    return v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="a video, or a still image of the page")
    ap.add_argument("--page", required=True, help="X0,Y0,X1,Y1: the source rectangle that fills the panel at the start")
    ap.add_argument("--target", required=True,
                    help="X0,Y0,X1,Y1 the rectangle to land on (its centre goes to --center), or X,Y with --zoom")
    ap.add_argument("--zoom", type=float, help="the final zoom, typed (default: derived from a rectangle target)")
    ap.add_argument("--margin", type=float, default=1.0, help="the derived zoom's margin, the kit's fit() (default 1.0)")
    ap.add_argument("--zone", default=f"{ZONE[0]:g},{ZONE[1]:g}", help="TOP,BOTTOM of the content zone, panel px")
    ap.add_argument("--center", help="X,Y: the panel point the target lands on (default the zone's centre)")
    ap.add_argument("--size", default=f"{PANEL[0]}x{PANEL[1]}", help="the output panel, WxH (default 1080x960)")
    ap.add_argument("--anchor", default="0,0", help="AX,AY in 0-1: where the page's overflow goes at the start")
    ap.add_argument("--start", type=int, default=START, help="the push's first frame (default 1)")
    ap.add_argument("--length", type=int, default=LENGTH, help="the push's length in frames (default 12)")
    n_ = ap.add_mutually_exclusive_group(required=True)
    n_.add_argument("--hold", type=int, help="frames on the target from the landing frame (start + length) on")
    n_.add_argument("--frames", type=int, help="the total frame count")
    ap.add_argument("--fps", help="the output rate as a rational, e.g. 24000/1001 (default the source video's)")
    ap.add_argument("--src-start", type=int, default=0, help="the source video frame output frame 0 shows")
    ap.add_argument("--samples", type=int, default=SAMPLES, help="motion-blur sub-frames per moving frame (default 8)")
    ap.add_argument("--shutter", type=float, default=SHUTTER, help="the shutter angle in degrees (default 180)")
    ap.add_argument("-o", "--out", required=True, help="the output .mp4")
    ap.add_argument("--force", action="store_true", help="overwrite an existing output")
    a = ap.parse_args(argv)
    src = None
    try:
        out = Path(a.out)
        if out.suffix.lower() != ".mp4":
            raise ZoomError(f"{out}: the output is an .mp4")
        if out.exists() and not a.force:
            raise ZoomError(f"{out} exists: a placed file is never overwritten in place; pick a new name, or --force")
        size = tuple(int(v) for v in nums(a.size, 2, "--size"))
        if size[0] % 2 or size[1] % 2 or min(size) <= 0:
            raise ZoomError(f"--size {a.size}: both sides even (yuv420p)")
        zone = nums(a.zone, 2, "--zone")
        center = nums(a.center, 2, "--center") if a.center else (size[0] / 2, (zone[0] + zone[1]) / 2)
        anchor = nums(a.anchor, 2, "--anchor")
        page = nums(a.page, 4, "--page")
        tgt = nums(a.target, (2, 4), "--target")
        if a.start < 0 or a.length < 1 or a.samples < 1 or not 0 <= a.shutter <= 360:
            raise ZoomError("--start >= 0, --length >= 1, --samples >= 1, --shutter 0-360")
        total = a.frames if a.frames is not None else a.start + a.length + a.hold
        if total < a.start + a.length + 1:
            raise ZoomError(f"the push lands on frame {a.start + a.length}: the output needs at least "
                            f"{a.start + a.length + 1} frames (--hold >= 1)")

        try:
            rate = Fraction(a.fps) if a.fps else None
        except (ValueError, ZeroDivisionError):
            rate = Fraction(0)
        if rate is not None and rate <= 0:
            raise ZoomError(f"--fps {a.fps}: a positive rate, e.g. 24000/1001")
        if Path(a.source).suffix.lower() in STILLS:
            if rate is None:
                raise ZoomError("a still needs --fps (the timeline's rate, e.g. 24000/1001)")
            still = Still(a.source)
            src_size, info = still.size, None
        else:
            still, info = None, probe(a.source)
            src_size, rate = info["size"], rate or info["rate"]
            if info["vfr"]:
                print(f"⚠ {a.source}: variable frame rate; it is read as {info['rate']} fps frame by frame: conform it "
                      "to a constant rate first (fps=)")

        x0, y0, x1, y1 = page
        if len(tgt) == 4:
            point = ((tgt[0] + tgt[2]) / 2, (tgt[1] + tgt[3]) / 2)
            fitted = fit_zoom(tgt, center, zone, size[0], a.margin)
            z1 = a.zoom if a.zoom is not None else fitted
        else:
            if a.zoom is None:
                raise ZoomError("a point target needs --zoom (or give the rectangle that must be whole)")
            point, z1, fitted = tgt, a.zoom, None
        if z1 <= 0:
            raise ZoomError(f"--zoom {z1}: a positive zoom")
        if not (x0 <= point[0] <= x1 and y0 <= point[1] <= y1):
            raise ZoomError(f"the target's centre {point} is outside the page {page}")
        push = Push(page, point, z1, size, center, a.start, a.length, anchor)

        typed = a.zoom is not None
        how = (f"typed; the rectangle fits up to {fit_zoom(tgt, center, zone, size[0]):.4f}" if fitted and typed
               else f"derived: whole in y{zone[0]:g}-{zone[1]:g}, margin {a.margin:g}" if fitted else "typed")
        land = a.start + a.length
        print(f"zoom-to-rect: final zoom {z1:.4f} ({how}); the page at {push.z0:.4f}; the target "
              f"({point[0]:.1f}, {point[1]:.1f}) from panel ({push.s0[0]:.1f}, {push.s0[1]:.1f}) to "
              f"({center[0]:g}, {center[1]:g}); push frames {a.start}-{land} (motion-blurred, {a.samples} samples, "
              f"{a.shutter:g} degrees), held to frame {total - 1}; {total} frames at {rate}")
        if fitted and typed and a.zoom > fit_zoom(tgt, center, zone, size[0]) + 1e-4:
            print(f"⚠ at zoom {a.zoom:g} the target rectangle runs out of the zone y{zone[0]:g}-{zone[1]:g} or the "
                  "panel's width: drop --zoom to derive it")
        if x0 < 0 or y0 < 0 or x1 > src_size[0] or y1 > src_size[1]:
            print(f"⚠ the page {page} runs past the {src_size[0]}x{src_size[1]} source frame")
        for rect, what, there in ((page, "the page rectangle", "what surrounds the page shows there"),
                                  ((0, 0, *src_size), "the source frame", "black there")):
            fr, worst, edges = overshoot(push, total, a.samples, a.shutter, rect)
            if fr:
                print(f"⚠ {span(fr)}: the view runs up to {worst:.0f} source px past {what}'s "
                      f"{'/'.join(sorted(edges))} edge ({there}; the push is never clamped: another target, zoom or "
                      "anchor moves it)")

        last_t = max(push.times(total - 1, a.samples, a.shutter))
        src = still or Video(a.source, info, rate, a.src_start, last_t)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f".{out.stem}.part.mp4")
        enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                                f"{size[0]}x{size[1]}", "-r", f"{rate.numerator}/{rate.denominator}", "-i", "-",
                                "-vf", TO709, "-c:v", "libx264", "-crf", "10", "-preset", "slow", "-pix_fmt",
                                "yuv420p", str(tmp)], stdin=subprocess.PIPE)
        try:
            for n in range(total):
                enc.stdin.write(render(push, src.at, n, a.samples, a.shutter).tobytes())
            enc.stdin.close()
        except (BrokenPipeError, ZoomError):
            enc.kill()
            enc.wait()
            tmp.unlink(missing_ok=True)
            raise
        if enc.wait():
            tmp.unlink(missing_ok=True)
            raise ZoomError(f"the encode failed (ffmpeg exit {enc.returncode})")
        got = probe(tmp)["frames"]
        if got != total:
            tmp.unlink(missing_ok=True)
            raise ZoomError(f"the encode holds {got} frames, not {total}")
        os.replace(tmp, out)
        print(f"✓ {total} frames -> {out} ({size[0]}x{size[1]}, {rate} fps, H.264 BT.709; final zoom {z1:.4f})")
        return 0
    except (ZoomError, OSError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    finally:
        if src is not None:
            src.close()


if __name__ == "__main__":
    sys.exit(main())
