#!/usr/bin/env python3
"""mint-export-preset.py: the export presets the house numbers need beyond the three tracked .eprs, minted from them.

  uv run lanes/premiere/premiere-templates/mint-export-preset.py 3840x2160 --mbps 80      long-form at 48-60 fps
  uv run lanes/premiere/premiere-templates/mint-export-preset.py 1920x1080 [--2997]       a NATIVE 1080 long-form file
  uv run lanes/premiere/premiere-templates/mint-export-preset.py 1080x1920 --reels --mbps 9   a Reel past 2:48

The numbers are the presets' (presets/youtube/default/README.md § Export, presets/instagram/talking-head-explainer/
README.md § Export); this only writes them into an .epr. A YouTube mint copies youtube-2160p-h264-cbr50.epr (or its
-2997 twin) to youtube-<2160p|1080p>-h264-cbr<N>[-2997].epr; a --reels mint copies
instagram-1080x1920-h264-cbr14-23976.epr to instagram-1080x1920-h264-cbr<N>-23976.epr. Only the frame-size values
(ADBEVideoWidth / Height) and the bitrate values (ADBEVideoTargetBitrate / MaxBitrate, target = max keeps it CBR)
change, each asserted found exactly once; everything else is the tracked preset's (CBR, H.264 High, AAC 320k).
Premiere exports at the SEQUENCE's rate whatever the .epr names, so a mint never changes the frame rate. The minted
files are regenerable and gitignored (the same bytes every time); lanes/premiere/export.py mints what it needs on
first use and says so. Prints the minted path. Stdlib only.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# never 2160x3840: Premiere's H.264 exporter caps the frame at 4096x2304 and wrote such a preset 1296x2304 (2026-09-26)
YT_SIZES = {(3840, 2160): '2160p', (1920, 1080): '1080p'}
YT_MBPS, REELS_MBPS = 50, 14                      # what the tracked templates carry


def name_for(size, mbps=YT_MBPS, df=False, reels=False):
    """The file name a mint of these numbers writes."""
    if reels:
        return f'instagram-1080x1920-h264-cbr{mbps:g}-23976.epr'
    return f'youtube-{YT_SIZES[tuple(size)]}-h264-cbr{mbps:g}{"-2997" if df else ""}.epr'


def _sub(text, ident, old, new, src):
    pat = re.compile(r'(<ParamIdentifier>%s</ParamIdentifier>(?:(?!</ExporterParam>).)*?<ParamValue>)%s(</ParamValue>)'
                     % (ident, re.escape(old)), re.S)
    text, n = pat.subn(lambda m: m.group(1) + new + m.group(2), text)
    if n != 1:
        raise SystemExit(f'{src.name}: expected exactly one {ident} = {old}, found {n}: the template changed, nothing minted')
    return text


def mint(size=(1920, 1080), df=False, src_dir=HERE, out_dir=HERE, mbps=None, reels=False):
    """Write the minted .epr for `size` at `mbps` (29.97 twin when df) into out_dir and return its path."""
    size = tuple(size)
    if reels:
        if size != (1080, 1920) or df:
            raise SystemExit('a --reels mint is 1080x1920 only (the Reels frame), and never a -2997 twin')
        src, from_size, from_mbps = Path(src_dir) / 'instagram-1080x1920-h264-cbr14-23976.epr', (1080, 1920), REELS_MBPS
    else:
        if size not in YT_SIZES:
            raise SystemExit(f'mint-export-preset.py mints {", ".join("%dx%d" % s for s in YT_SIZES)} (or 1080x1920 '
                             f'--reels), not {size[0]}x{size[1]}')
        src, from_size, from_mbps = Path(src_dir) / f'youtube-2160p-h264-cbr50{"-2997" if df else ""}.epr', (3840, 2160), YT_MBPS
    mbps = from_mbps if mbps is None else mbps
    if not 1 <= mbps <= 200:
        raise SystemExit(f'--mbps {mbps:g}: outside 1..200')
    if size == from_size and mbps == from_mbps:
        raise SystemExit(f'{src.name} IS that preset (tracked): nothing to mint')
    with open(src, encoding='utf-8', newline='') as f:     # newline='': the bytes round-trip, only the values change
        text = f.read()
    for ident, old, new in (('ADBEVideoWidth', from_size[0], size[0]), ('ADBEVideoHeight', from_size[1], size[1])):
        if old != new:
            text = _sub(text, ident, str(old), str(new), src)
    if mbps != from_mbps:
        for ident in ('ADBEVideoTargetBitrate', 'ADBEVideoMaxBitrate'):
            text = _sub(text, ident, f'{from_mbps}.', f'{mbps:g}.', src)
    out = Path(out_dir) / name_for(size, mbps, df, reels)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    return out


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    df, reels, mbps = '--2997' in a, '--reels' in a, None
    if '--mbps' in a:
        i = a.index('--mbps')
        try:
            mbps = float(a[i + 1])
        except (IndexError, ValueError):
            raise SystemExit(__doc__)
        del a[i:i + 2]
    a = [x for x in a if x not in ('--2997', '--reels')]
    m = re.fullmatch(r'(\d+)x(\d+)', a[0]) if len(a) == 1 else None
    if not m:
        raise SystemExit(__doc__)
    print(mint((int(m.group(1)), int(m.group(2))), df, mbps=mbps, reels=reels))
    return 0


if __name__ == '__main__':
    sys.exit(main())
