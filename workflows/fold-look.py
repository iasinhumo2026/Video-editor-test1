#!/usr/bin/env python3
"""fold-look.py: bake a Creative Look (a .cube at an intensity, plus a saturation lift) into ONE .cube.

    uv run workflows/fold-look.py <look.cube> <out.cube> [--intensity 0.80] [--saturation 1.20]
    uv run workflows/fold-look.py <look.cube> --install <NAME> [--intensity 0.80] [--saturation 1.20]

Neither consumer can set Lumetri's "Look Intensity" and "Creative Saturation" dials from a script, so
they are baked into the cube:

    out = sat(lerp(x, look(x), intensity), saturation)    saturation about Rec709 luma, clamped 0..1

evaluated on the look's own lattice, so nothing is resampled. The consumers:
  · Resolve (its node graph exposes LUT, label, enable and cache mode only): `--install NAME` writes
    <Resolve master LUT dir>/MCP/<NAME>.cube (macOS /Library/Application Support/Blackmagic Design/
    DaVinci Resolve/LUT, Windows %PROGRAMDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\LUT (writable by a standard user,
    proven on Studio 21.1 2026-09-27),
    Linux /opt/resolve/LUT) and prints the 'MCP/<NAME>.cube' to pass to project.RefreshLUTList() then
    SetLUT(1, ...) on the colour group's post-clip graph.
  · Final Cut: the positional <out.cube>, written into ProApps/Custom LUTs/ by setup-finalcut.sh.
Proven 2026-09-25: Autumn-Rec709 at 0.80 / 1.20 measured within 1-2 / 255 of Lumetri's 80 / 120.
"""
import argparse
import os
import sys
from pathlib import Path


def read_cube(path):
    size, rows = None, []
    for line in open(path, encoding="utf-8"):
        s = line.strip()
        if s.startswith("LUT_3D_SIZE"):
            size = int(s.split()[1])
        elif s and (s[0].isdigit() or s[0] in "-."):
            rows.append(tuple(float(v) for v in s.split()[:3]))
    if not size or len(rows) != size ** 3:
        raise SystemExit(f"{path}: expected LUT_3D_SIZE and size^3 rows, got {size} / {len(rows)}")
    return size, rows


def fold(size, rows, intensity, saturation):
    out, n = [], size - 1
    for idx, look in enumerate(rows):                     # .cube order: red fastest, then green, then blue
        src = (idx % size / n, idx // size % size / n, idx // (size * size) / n)
        m = [a + intensity * (b - a) for a, b in zip(src, look)]
        y = 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]
        out.append(tuple(min(1.0, max(0.0, y + saturation * (c - y))) for c in m))
    return out


def resolve_lut_dir():
    """Resolve's master LUT folder on this OS (the one RefreshLUTList() scans)."""
    if sys.platform == "darwin":
        return Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT")
    if os.name == "nt":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData") + r"\Blackmagic Design\DaVinci Resolve\Support\LUT")
    return Path("/opt/resolve/LUT")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("look")
    ap.add_argument("out", nargs="?", help="where to write the folded cube (or use --install)")
    ap.add_argument("--install", metavar="NAME",
                    help="write <Resolve master LUT dir>/MCP/NAME.cube instead of OUT and print the SetLUT path")
    ap.add_argument("--intensity", type=float, default=0.80)
    ap.add_argument("--saturation", type=float, default=1.20)
    a = ap.parse_args()
    if bool(a.out) == bool(a.install):
        ap.error("give exactly one of OUT or --install NAME")
    out = resolve_lut_dir() / "MCP" / f"{a.install}.cube" if a.install else Path(a.out)
    size, rows = read_cube(a.look)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"# fold-look.py: {a.look} at intensity {a.intensity}, saturation {a.saturation}\n")
            f.write(f"LUT_3D_SIZE {size}\n\n")
            f.writelines("%.6f %.6f %.6f\n" % r for r in fold(size, rows, a.intensity, a.saturation))
    except PermissionError as e:
        raise SystemExit(f"cannot write {out}: {e.strerror}. Make {out.parent} writable for this user "
                         f"(or write the cube elsewhere and copy it there yourself).")
    print(f"wrote {out}: {size}^3, intensity {a.intensity}, saturation {a.saturation}")
    if a.install:
        print(f"MCP/{a.install}.cube")


if __name__ == "__main__":
    main()
