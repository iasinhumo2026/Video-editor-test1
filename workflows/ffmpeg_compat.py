#!/usr/bin/env python
"""ffmpeg_compat.py: the passthrough frame-sync flag, the graph-from-a-file option, and whether Apple's hardware encoder
can hold a constant bitrate, for whichever ffmpeg is on PATH.

Every frame-exact read here needs passthrough sync: the default constant-rate sync duplicates a frame on any file
with audio and re-pads `select` back up to a constant rate (framing-continuity.py, chin-line.py). The flag changed
name: `-vsync 0` up to ffmpeg 5.0, `-fps_mode passthrough` from 5.1, and 9.0 deleted `-vsync` outright
("Unrecognized option 'vsync'", exit 8: Homebrew's 9.0.2, a client's first run, 2026-10-13). So the flag is read off
the ffmpeg's own help once per process, and a caller splices `*passthrough()` where it used to type `-vsync 0`.
workflows/test_ffmpeg_compat.py fails on any shipped script that types `-vsync` or `-fps_mode` again.
The `-vsync` branch is not a supported ffmpeg: the shipped code needs 5.1 (ochl, alimiter's latency; the `floor` in
workflows/ffmpeg-vocab.json), and check-setup.sh counts an older ffmpeg (Ubuntu 22.04's 4.4) as missing. It only keeps
a frame read from dying on the flag name alone.
"""
import functools
import re
import subprocess


@functools.cache
def passthrough(ffmpeg="ffmpeg"):
    """('-fps_mode', 'passthrough') on an ffmpeg that has it (5.1+), else ('-vsync', '0')."""
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-h", "long"], capture_output=True, text=True, errors="replace").stdout
    except OSError:  # no ffmpeg at all: the caller's own run says so
        out = ""
    return ("-fps_mode", "passthrough") if re.search(r"^-fps_mode\b", out, re.M) else ("-vsync", "0")


@functools.cache
def graph_file(ffmpeg="ffmpeg"):
    """The option that reads a -filter_complex graph from a FILE (a Windows command line caps at 32,767 characters):
    `-filter_complex_script` where this ffmpeg lists it undeprecated (5.1 to 6.1, which have no `-/opt` syntax), else
    `-/filter_complex` (7.0 to 8.x print the old one "deprecated, use -/filter_complex instead", 9.0 deleted it).
    `-/filter_complex` alone was an unknown option on the 5.1 to 6.1 a client's setup accepts (2026-10-13)."""
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-h", "long"], capture_output=True, text=True, errors="replace").stdout
    except OSError:  # no ffmpeg at all: the caller's own run says so
        out = ""
    m = re.search(r"^-filter_complex_script\b.*$", out, re.M)
    return "-filter_complex_script" if m and "deprecated" not in m.group(0) else "-/filter_complex"


@functools.cache
def videotoolbox_cbr(ffmpeg="ffmpeg"):
    """True where this ffmpeg's h264_videotoolbox takes constant_bit_rate (ffmpeg 6.0+, macOS 13+): workflows/deliver.py
    then encodes the deliverable on Apple's hardware encoder at the house CBR. Without it VideoToolbox treats the
    target as a ceiling (a VBR 50 export landed at 17.6 Mbps), so a Mac on an older ffmpeg stays on libx264."""
    try:
        out = subprocess.run([ffmpeg, "-hide_banner", "-h", "encoder=h264_videotoolbox"], capture_output=True, text=True,
                             errors="replace").stdout
    except OSError:  # no ffmpeg at all: the caller's own run says so
        out = ""
    return bool(re.search(r"^\s*-?constant_bit_rate\b", out, re.M))
