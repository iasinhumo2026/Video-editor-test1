#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""
bake-emoji.py — bake emoji glyphs to trimmed PNGs so the headless render never font-resolves a live emoji.

Raw emoji codepoints DEADLOCK the HyperFrames headless render (a font-load hang that never errors or
times out — see lanes/chat-only/incremental-graphics.md, the emoji gotcha). The fix is to never put an emoji
in graphic markup: either fake the look in the embedded brand font, or bake the glyph to a PNG here and
overlay it as an <img>.

Renders the platform's color-emoji font via PIL (embedded_color) at the largest bitmap strike it has (160 on
Apple Color Emoji), trims to the drawn pixels, then re-centers on a square with even padding.

ONE CODEPOINT PER EMOJI, unless this Pillow can shape text (libraqm; PyPI's wheels cannot). Without shaping a
ZWJ sequence (🧑‍💻), a skin tone (👍🏽), a flag (🇺🇸) or a keycap (1️⃣) is drawn as its separate glyphs, a person
beside a laptop, and still printed as a success (2026-10-13): such a pair is refused and named. Every pair is
tried, and the run exits non-zero naming each one it did not bake.

Usage:
    uv run workflows/bake-emoji.py <name>=<emoji> [<name>=<emoji> ...] [--out DIR]

    uv run workflows/bake-emoji.py rocket=🚀 check=✅ palette=🎨
    uv run workflows/bake-emoji.py intake=📥 --out ./assets/emoji

Writes <out>/<name>.png for each pair. Default out: ./assets/emoji next to the cwd.
"""
import os
import sys
import pathlib
from PIL import Image, ImageFont, ImageDraw, features

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the glyphs printed below
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Color-emoji font, by platform. Apple Color Emoji on macOS; Segoe UI Emoji on Windows; Noto Color
# Emoji on Linux/WSL (apt install fonts-noto-color-emoji). First one that exists wins.
EMOJI_FONT_CANDIDATES = [
    "/System/Library/Fonts/Apple Color Emoji.ttc",          # macOS
    "C:\\Windows\\Fonts\\seguiemj.ttf",                      # Windows (Segoe UI Emoji)
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",    # Linux / WSL (fonts-noto-color-emoji)
]
STRIKES = (160, 136, 109, 96, 64)   # a bitmap color font opens ONLY at one of its own strikes ("invalid pixel size"
                                    # at any other): Apple's largest is 160, Noto Color Emoji's (CBDT, Linux) its one 109
DRAW = 320          # generous draw canvas so the glyph never clips while drawing (anchor mm rides high)
PAD_FRAC = 0.12     # even breathing room around the trimmed glyph


def parse_args(argv):
    pairs, out = [], pathlib.Path("assets/emoji")
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            out = pathlib.Path(argv[i + 1]); i += 2; continue
        if "=" not in a:
            sys.exit("each arg must be name=emoji (got %r)" % a)
        name, glyph = a.split("=", 1)
        pairs.append((glyph, name)); i += 1
    if not pairs:
        sys.exit(__doc__)
    return pairs, out


def load_font(path):
    """The color-emoji font at the largest of STRIKES it opens at (Segoe's COLR takes any size)."""
    for size in STRIKES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:                                     # not one of this bitmap font's strikes
            continue
    sys.exit("[emoji] %s opens at none of the sizes %s" % (path, ", ".join(map(str, STRIKES))))


def bake(glyph, name, font, out_dir):
    """Write <out_dir>/<name>.png. Returns None, or why the glyph was not baked."""
    if len(glyph.replace("\ufe0f", "")) > 1 and not features.check("raqm"):
        return ("%d codepoints (a ZWJ sequence, a skin tone, a flag or a keycap), and this Pillow has no text shaping "
                "(raqm), so they would be drawn side by side: pick a single-codepoint emoji, or fake the look in the "
                "brand font" % len(glyph))
    big = Image.new("RGBA", (DRAW, DRAW), (0, 0, 0, 0))
    ImageDraw.Draw(big).text((DRAW // 2, DRAW // 2), glyph, font=font, anchor="mm", embedded_color=True)
    bb = big.getbbox()                                      # trim to the actual drawn pixels...
    if bb is None:
        return "drew nothing — bad glyph or font missing color strike"
    cropped = big.crop(bb)
    side = max(cropped.width, cropped.height)
    pad = int(round(side * PAD_FRAC))
    out_side = side + 2 * pad
    out = Image.new("RGBA", (out_side, out_side), (0, 0, 0, 0))   # ...then re-center on a square w/ even pad
    out.paste(cropped, ((out_side - cropped.width) // 2, (out_side - cropped.height) // 2), cropped)
    out.save(out_dir / (name + ".png"))
    print("[emoji] %s -> %s.png (%dx%d)" % (glyph, name, out_side, out_side))
    return None


def main():
    pairs, out_dir = parse_args(sys.argv[1:])
    out_dir.mkdir(parents=True, exist_ok=True)
    emoji_font = next((p for p in EMOJI_FONT_CANDIDATES if os.path.exists(p)), None)
    if emoji_font is None:
        sys.exit("[emoji] no color-emoji font found. Install one:\n"
                 "  Linux/WSL:  sudo apt install fonts-noto-color-emoji\n"
                 "  (macOS/Windows ship one by default.)\n"
                 "Or skip baking and fake the look in your brand font (see lanes/chat-only/incremental-graphics.md).")
    font = load_font(emoji_font)
    failed = []
    for glyph, name in pairs:
        why = bake(glyph, name, font, out_dir)
        if why:
            print("[emoji] ✗ %s=%s not baked: %s" % (name, glyph, why), file=sys.stderr)
            failed.append(name)
    if failed:
        sys.exit("[emoji] %d of %d not baked: %s" % (len(failed), len(pairs), ", ".join(failed)))
    print("done ->", out_dir)


if __name__ == "__main__":
    main()
