#!/usr/bin/env python3
"""deliver.py: the house deliverable encode from a finished master, to the presets' § Export numbers (ffmpeg, any lane).

  uv run workflows/deliver.py <master.mov> <out.mp4> [--shorts]

A lane whose own encoder cannot reach a number encodes its master here instead: Final Cut for every deliverable (its
H.264 choices carry no bitrate control), Premiere for the 4K YouTube Shorts file (its H.264 exporter caps the frame
at 4096x2304, so 2160x3840 comes out 1296x2304; its HEVC exporter answers exportAsMediaDirect with -1). The chat-only
lane has no master: lanes/chat-only/assemble.py encodes its composite with these numbers in the same pass (target(),
video_args() and TAGS), and its audio passes (mix-sfx.py, mix-music.sh) take the AAC 320k 48 kHz. The numbers
(researched and set 2026-09-26; presets/youtube/default/README.md § Export, presets/instagram/talking-head-explainer/
README.md § Export), picked from the master's frame:
  landscape, 1920x1080 or 3840x2160   -> 3840x2160, H.264 High 5.1 CBR 50 (5.2 CBR 80 above 30 fps)
  vertical, 1080x1920 or 2160x3840    -> 1080x1920, H.264 High 4.2 CBR 14 (video <= 2350 / seconds - 0.32 past 2:48)
  vertical 2160x3840 with --shorts    -> 2160x3840 at the landscape 4K numbers (the YouTube Shorts file)
All: closed GOP of half the frame rate, CABAC, 4:2:0, bt709 tags on the frames, limited range, the master's frame
rate, AAC-LC 320k 48 kHz, moov first, no timecode track (a camera master's tmcd is not muxed into the MP4). A
frame-size change is a lanczos scale. The master's audio is PCM, so this AAC encode is the only lossy audio step
(never below 256k). Proving the file is the caller's job (each lane's export.py ffprobes it). Stdlib only.
THE ENCODER (2026-10-14): on a Mac, Apple's hardware encoder (VideoToolbox, as Premiere's own export), wherever this
ffmpeg holds its constant bitrate (workflows/ffmpeg_compat.py videotoolbox_cbr(), ffmpeg 6.0+); elsewhere libx264
-preset slow with 2 B-frames. x264 slow pinned every core of a member's M5 MacBook Pro on a 10-minute export. On an
M4 Pro, 10 s of 4K camera footage: x264 15 s, VideoToolbox 4.5 s; a 60 s 1080 screen-recording master to 4K: x264
38 s on 9.4 cores, VideoToolbox 23.5 s on 1.3 (its encoder is the limit, about 61 fps). VMAF, VideoToolbox against
x264 at CBR 50: 95.5 to 96.1 on a talking head, 96.7 to 97.8 on a screen recording with captions, indistinguishable
at 1:1.
VideoToolbox takes no -maxrate/-bufsize (it reads them as a data-rate cap: CBR 50 landed at 31.7 Mbps) and no -bf (it
ignores the count, builds a B pyramid two frames deep that ffmpeg 9 times one deep, "Invalid DTS" with two frames'
pts moved a tick, and it scored lower), so its file has no B-frames and every keyframe is an IDR: the GOP is closed.
Its CBR adds no filler, so an easy picture lands a little under the target (a talking head: 47.5 Mbps of 50).
"""
import argparse, functools, importlib.util, json, subprocess, sys
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

LONG_MBPS, LONG_HFR_MBPS = 50, 80   # 3840x2160 (and the Shorts 2160x3840): CBR 50 at <= 30 fps, CBR 80 at 48-60
REELS_MBPS, AUDIO_MBPS = 14, 0.32   # the vertical 1080x1920 file; AAC 320k


def reels_mbps(secs):
    """The vertical file's video bitrate: CBR 14, or video <= 2350 / seconds - 0.32 (300 MB less 2 % for the
    container, less the AAC) once 14 would break Meta's 300 MB cap, in whole Mbps."""
    return max(1, min(REELS_MBPS, int(2350 / secs - AUDIO_MBPS))) if secs and secs > 0 else REELS_MBPS


def target(W, H, fps, secs, shorts=False):
    """(out W, out H, Mbps, H.264 level, vertical 1080 file?) for a W x H master."""
    hfr = fps > 30.5
    if W > H or shorts:
        return (*((3840, 2160) if W > H else (2160, 3840)), LONG_HFR_MBPS if hfr else LONG_MBPS,
                '5.2' if hfr else '5.1', False)
    return 1080, 1920, reels_mbps(secs), '4.2', True


def plan(master, shorts=False):
    """What the master is and what it becomes: {W, H, rate, fps, frames, secs, OW, OH, mbps, level, vertical, gop}."""
    d = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries',
                                   'stream=width,height,r_frame_rate,nb_read_packets', '-of', 'json', str(master)],
                                  capture_output=True, text=True, check=True).stdout)['streams'][0]
    W, H, rate, frames = int(d['width']), int(d['height']), d['r_frame_rate'], int(d['nb_read_packets'])
    fps = Fraction(*map(int, rate.split('/')))
    secs = float(frames / fps)
    OW, OH, mbps, level, vertical = target(W, H, float(fps), secs, shorts)
    return dict(W=W, H=H, rate=rate, fps=fps, frames=frames, secs=secs, OW=OW, OH=OH, mbps=mbps, level=level,
                vertical=vertical, gop=max(1, round(float(fps) / 2)))


@functools.cache
def hardware():
    """True on a Mac whose ffmpeg holds the CBR on VideoToolbox (the docstring's THE ENCODER); libx264 otherwise."""
    if sys.platform != 'darwin':
        return False
    spec = importlib.util.spec_from_file_location('ffmpeg_compat', Path(__file__).resolve().with_name('ffmpeg_compat.py'))
    compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compat)
    return compat.videotoolbox_cbr()


def video_args(mbps, level, gop, rate):
    """The house H.264 video settings as ffmpeg output args (the frame size and the bt709 frame tags are the filter's)."""
    m = f'{mbps}M'
    tail = ['-r', rate, '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv']
    if hardware():   # no -maxrate/-bufsize, no -bf: the docstring's THE ENCODER (CABAC is its High default)
        return ['-c:v', 'h264_videotoolbox', '-profile:v', 'high', '-level:v', level, '-pix_fmt', 'yuv420p',
                '-b:v', m, '-constant_bit_rate', '1', '-g', str(gop), *tail]
    return ['-c:v', 'libx264', '-profile:v', 'high', '-level:v', level, '-pix_fmt', 'yuv420p', '-preset', 'slow',
            '-b:v', m, '-minrate', m, '-maxrate', m, '-bufsize', m, '-g', str(gop), '-bf', '2', '-flags', '+cgop',
            '-x264-params', 'nal-hrd=cbr:force-cfr=1:open-gop=0', *tail]


TAGS = 'setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv'


def command(master, out, p):
    """The one ffmpeg command for plan `p`."""
    scale = f'scale={p["OW"]}:{p["OH"]}:flags=lanczos,' if (p['OW'], p['OH']) != (p['W'], p['H']) else ''
    # the tags ride the FRAMES: ffmpeg 8 lets an untagged master's frame properties override -color_primaries & co.
    return ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(master), '-map', '0:v:0', '-map', '0:a:0',
            '-vf', scale + TAGS, *video_args(p['mbps'], p['level'], p['gop'], p['rate']),
            '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-write_tmcd', '0', '-movflags', '+faststart', str(out)]


def encode(master, out, shorts=False):
    """Encode `master` to `out`; returns the plan. Raises CalledProcessError on an ffmpeg failure."""
    p = plan(master, shorts)
    print(f'… encoding {master} → {out}: {p["W"]}x{p["H"]}'
          + (f' → {p["OW"]}x{p["OH"]}' if (p['OW'], p['OH']) != (p['W'], p['H']) else '')
          + f' H.264 High {p["level"]} CBR {p["mbps"]} Mbps, GOP {p["gop"]} closed, AAC 320k'
          + (' (Apple hardware encoder)' if hardware() else ' (libx264)'), flush=True)
    subprocess.run(command(master, out, p), check=True)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('master')
    ap.add_argument('out')
    ap.add_argument('--shorts', action='store_true', help='a 2160x3840 master: the 4K YouTube Shorts file')
    a = ap.parse_args()
    encode(a.master, a.out, a.shorts)
    return 0


if __name__ == '__main__':
    sys.exit(main())
