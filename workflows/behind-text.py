#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""Bake a title to an alpha ProRes 4444 mov, for type that sits BEHIND a subject.

CapCut composites by track stacking, so a native text track can never render
below a video layer — behind-the-subject type has to be a video overlay. Same
mov drops onto a Premiere timeline. Pair with the cutout recipe in the `capcut`
skill: black dim on layer 1, this on layer 2, the matted duplicate on layer 3.

  uv run workflows/behind-text.py "what you're|watching right now" \
      --out projects/<job>/assets/behind-text.mov

Split lines with `|`. Lines are sized off the longest one so both run wide
enough to stay readable where the subject punches through the middle.
"""
import argparse
import subprocess
import sys
from pathlib import Path

import os
from PIL import Image, ImageDraw, ImageFont

FONT = "/Library/Fonts/SF-Pro-Display-Black.otf"
if not os.path.exists(FONT):  # not every machine has SF Pro; fall back to the bundled Inter Black
    FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "fonts", "Inter-Black.otf")
TRACK = -0.03  # letter-spacing as a fraction of the font size


def line_width(text, font, size):
    return sum(font.getlength(c) for c in text) + TRACK * size * (len(text) - 1)


def fit(text, target, cap):
    size = 8
    while size < cap:
        probe = ImageFont.truetype(FONT, size + 4)
        if line_width(text, probe, size + 4) > target:
            break
        size += 4
    return ImageFont.truetype(FONT, size), size


def draw_tracked(dr, x, y, text, font, size, fill):
    for c in text:
        dr.text((x, y), c, font=font, fill=fill)
        x += font.getlength(c) + TRACK * size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text", help="title; split lines with |")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--dur", type=float, default=2.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--top", type=int, help="block top in px (default: centered)")
    ap.add_argument("--margin", type=int, default=180, help="side margin in px")
    ap.add_argument("--max-size", type=int, default=400)
    ap.add_argument("--color", default="255,255,255")
    a = ap.parse_args()

    if not Path(FONT).exists():
        sys.exit(f"font not found: {FONT}")
    lines = [s for s in a.text.split("|") if s]
    fill = tuple(int(v) for v in a.color.split(",")) + (255,)

    font, size = fit(max(lines, key=len), a.width - 2 * a.margin, a.max_size)
    lead = int(size * 0.92)
    top = a.top if a.top is not None else (a.height - lead * len(lines)) // 2

    im = Image.new("RGBA", (a.width, a.height), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    y = top
    for ln in lines:
        draw_tracked(dr, (a.width - line_width(ln, font, size)) / 2, y,
                     ln, font, size, fill)
        y += lead

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    png = out.with_suffix(".png")
    im.save(png)
    # BT.709 matrix, tagged: ffmpeg's default RGB->YUV is BT.601 with no tags, and an editing app reads untagged HD
    # as 709, so a --color shifted (2026-10-13). An explicit scale, never bare tag flags (older ffmpeg only tags).
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(a.dur),
        "-i", str(png), "-vf", "scale=out_color_matrix=bt709:out_range=tv,"
        "setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv",
        "-c:v", "prores_ks", "-profile:v", "4444",
        "-pix_fmt", "yuva444p10le", "-r", str(a.fps), str(out)], check=True)
    print(f"{size}px, widest line {line_width(max(lines, key=len), font, size):.0f}px "
          f"-> {out}")


if __name__ == "__main__":
    main()
