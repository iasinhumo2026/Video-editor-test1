#!/usr/bin/env python3
"""selftest.py: does this machine's ffmpeg run the pipeline? Report only: nothing is written outside a temp folder.

    uv run workflows/selftest.py            the ffmpeg vocabulary (about 2 s): every option, filter, filter option,
                                            encoder and format the shipped code passes (workflows/ffmpeg-vocab.json),
                                            probed on the ffmpeg and ffprobe on PATH
    uv run workflows/selftest.py --smoke    the vocabulary, then a smoke (under 30 s): a timecoded clip read the way
                                            the tools read one (ffprobe's first row), a frame-exact read through
                                            ffmpeg_compat.passthrough(), and a two-segment splice.sh render (RENDER=1)

check-setup.sh runs the first on every call (a ✗ here is a core miss there), setup.sh the second before it writes
.setup-complete. The version floors (ffmpeg, uv, node, python, the platform) are check-setup.sh's.

Why (2026-10-13): Homebrew moved to ffmpeg 9.0.2, which deleted -vsync, and a client's first run died mid-edit on an
"Unrecognized option" that setup had never exercised. A deleted option, a filter a lean build lacks or a frame read that
breaks now stops setup with the cause named, on the client's own machine, before an edit.

Stdlib only, Python 3.8+ (it runs on whatever python check-setup.sh found). Exit 0 = every check passed, 1 = a failure
(each line says what failed), 2 = no ffmpeg to test.
"""
import argparse
import concurrent.futures
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
VOCAB = HERE / "ffmpeg-vocab.json"
SPLICE = REPO / ".claude" / "skills" / "rough-cut" / "scripts" / "splice.sh"
sys.path.insert(0, str(HERE))
from ffmpeg_compat import passthrough  # noqa: E402  (-fps_mode or -vsync 0, whichever this ffmpeg has)
import ffmpeg_compat  # noqa: E402  (a manifest fallback's `picked_by` names one of its probes)

W, H, FPS, SECONDS = 320, 240, 25, 4      # testsrc2's own defaults: no option the pipeline itself never passes
SEGMENTS = ((0.5, 1.5), (2.0, 3.2))      # the smoke's EDL: 2.2 s kept, one joint


def ok(label, text):
    print("  ✓ %-12s %s" % (label, text))


def bad(label, text):
    print("  ✗ %-12s %s" % (label, text))


def warn(label, text):
    print("  ! %-12s %s" % (label, text))


# ── the vocabulary, on this ffmpeg (the probe workflows/test_ffmpeg_vocab.py runs in the repo) ───────────────────
@functools.lru_cache(maxsize=None)
def run(*argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return r.stdout + r.stderr


def known(kind, name):
    """This ffmpeg has the filter, encoder or format (a muxer or a demuxer, an input device included): asked one
    name at a time through `-h`, the one help option every ffmpeg since 4.4 answers the same way."""
    if kind == "format":
        return any(run("ffmpeg", "-hide_banner", "-h", "%s=%s" % (k, name)).lstrip().startswith(("Muxer", "Demuxer"))
                   for k in ("muxer", "demuxer"))
    return run("ffmpeg", "-hide_banner", "-h", "%s=%s" % (kind, name)).lstrip().startswith(kind.capitalize())


def parse_help(text):
    """{name: [(is_main, deprecated)]} from `-h` text: main options at column 0, AVOptions indented."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"-([A-Za-z0-9_]+)(?:\[:<[a-z_]+>\])?(?:\s|$)", line)
        if m:
            out.setdefault(m.group(1), []).append((True, "deprecated" in line))
            continue
        m = re.match(r"\s+-?([A-Za-z0-9_]+)\s+(?:<[^>]+>\s+|\[<[^>]+>\s*\])(\S{11})\s?(.*)", line)
        if m:
            out.setdefault(m.group(1), []).append((False, m.group(2).endswith("P") or "deprecated" in m.group(3)))
    return out


@functools.lru_cache(maxsize=None)
def options(tool, topic="full"):
    return parse_help(run(tool, "-hide_banner", "-h", topic))


def verdict(name, table):
    """None when usable, else 'missing' or 'deprecated' (a main option decides; an AVOption fails only when every
    class that has it deprecates it)."""
    rows = table.get(name)
    if not rows and name.startswith("no"):                 # -nostdin / -nostats: a boolean main option, negated
        rows = [r for r in table.get(name[2:], []) if r[0]]
    if not rows:
        return "missing"
    mains = [d for is_main, d in rows if is_main]
    if mains:
        return "deprecated" if all(mains) else None
    return "deprecated" if all(d for _m, d in rows) else None


def filter_problems(filt, keys):
    out = []
    for key in keys:
        if key == "enable":                                # the timeline option: named in prose, not in the table
            if "timeline through the 'enable' option" not in run("ffmpeg", "-hide_banner", "-h", "filter=" + filt):
                out.append(("missing", "filter %s has no timeline support (enable)" % filt))
            continue
        v = verdict(key, options("ffmpeg", "filter=" + filt))
        if v:
            out.append((v, "filter %s option %s" % (filt, key)))
    return out


def applies(entry):
    return not entry.get("os") or sys.platform in entry["os"]


def vocabulary(vocab):
    """[(verdict, what)] for every manifest entry this ffmpeg lacks ('missing') or deprecates ('deprecated')."""
    found = []
    for token, e in sorted(vocab["options"].items()):
        if not applies(e):
            continue
        # ffmpeg_compat's fallbacks: -vsync only on an ffmpeg without -fps_mode (when_missing), the graph-file option
        # only where graph_file() picks it (picked_by)
        fb = e.get("fallback")
        if fb and ("picked_by" in fb and getattr(ffmpeg_compat, fb["picked_by"])() != token
                   or "when_missing" in fb and verdict(fb["when_missing"][1:], options("ffmpeg")) is None):
            continue
        tools = ["ffmpeg", "ffprobe"] if e["tool"] == "both" else [e["tool"]]
        name = token[1:].split(":")[0]
        for t in tools:
            v = verdict(name, options(t))
            if v:
                found.append((v, "%s option %s" % (t, token)))
    names = [("filter", f) for f, e in sorted(vocab["filters"].items()) if applies(e)]
    names += [("encoder", n) for n, e in sorted(vocab["encoders"].items()) if applies(e)]
    names += [("format", n) for n, e in sorted(vocab["formats"].items()) if applies(e)]
    with concurrent.futures.ThreadPoolExecutor(8) as pool:   # one `-h` call a name: run them side by side
        have = dict(zip(names, pool.map(lambda kn: known(*kn), names)))
        found += [("missing", "%s %s" % kn) for kn in names if not have[kn]]
        wanted = [(f, vocab["filters"][f].get("options", [])) for k, f in names if k == "filter" and have[(k, f)]]
        for probs in pool.map(lambda fk: filter_problems(*fk), [(f, ks) for f, ks in wanted if ks]):
            found += probs
    return found


def check_vocabulary():
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    found = vocabulary(vocab)
    missing = [w for v, w in found if v == "missing"]
    for w in missing:
        bad("vocabulary", "this ffmpeg lacks %s, which the pipeline passes" % w)
    for v, w in found:
        if v == "deprecated":
            warn("vocabulary", "this ffmpeg deprecates %s: it works now, and the next ffmpeg may delete it" % w)
    if missing:
        print("    a lean or old build: install the full current ffmpeg (brew upgrade ffmpeg · "
              "winget upgrade --id Gyan.FFmpeg -e · Linux: a current static build), then re-run")
    else:
        n = sum(applies(e) for k in ("options", "filters", "encoders", "formats") for e in vocab[k].values())
        ok("vocabulary", "all %d options, filters, encoders and formats the pipeline passes are in this ffmpeg" % n)
    return not missing


# ── the smoke ──────────────────────────────────────────────────────────────────────────────────────────────────────
def scratch_root():
    """splice.sh's scratch folder: /tmp/video-editor, or %TEMP%\\video-editor on Windows (Git Bash's /tmp)."""
    return os.path.join("/tmp" if os.name != "nt" else tempfile.gettempdir(), "video-editor")


def git_bash():
    """The bash to run splice.sh with: plain `bash` on macOS/Linux; Git Bash on Windows, never by bare name, because
    CreateProcess searches System32 before PATH and System32's bash.exe is WSL's (make-clips.py's git_bash)."""
    if os.name != "nt":
        return "bash"
    for c in [shutil.which("bash")] + [os.path.join(os.environ.get(v, ""), "Git", "bin", "bash.exe")
                                       for v in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")]:
        if c and os.path.exists(c) and "system32" not in c.lower():
            return c
    return None


def tail(text, n=6):
    return "\n".join("      " + l for l in [l for l in text.splitlines() if l.strip()][-n:])


def smoke():
    """Each step's failure is named with ffmpeg's own words. True when all of them pass."""
    passed = True
    tmp = Path(tempfile.mkdtemp(prefix="ve-selftest-"))
    job = tmp / ("ve-selftest-%d" % os.getpid())
    work = Path(scratch_root()) / job.name
    try:
        (job / "raw").mkdir(parents=True)
        clip = job / "raw" / "take.mov"
        # a camera-style raw: a timecode (tmcd) track beside picture and sound, the shape ffprobe 9 doubles rows for
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-t", str(SECONDS), "-i", "testsrc2",
                            "-f", "lavfi", "-t", str(SECONDS), "-i", "sine", "-c:v", "prores_ks", "-c:a", "pcm_s24le",
                            "-timecode", "01:00:00:00", str(clip)], capture_output=True, text=True, errors="replace")
        if r.returncode or not clip.is_file():
            bad("smoke", "ffmpeg could not write a timecoded test clip:\n" + tail(r.stderr))
            return False
        # 1. ffprobe's first row: every text-format video read in the tools takes it (test_ffmpeg_compat.py)
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                              "-of", "csv=p=0", str(clip)], capture_output=True, text=True, errors="replace")
        first = next((l for l in out.stdout.splitlines() if l.strip()), "").strip()
        rows = sum(1 for l in out.stdout.splitlines() if l.strip())
        if first == "%d,%d" % (W, H):
            ok("first row", "ffprobe reads a timecoded clip's video row" + (
                " (this ffprobe prints it %d times; the tools read the first)" % rows if rows > 1 else ""))
        else:
            bad("first row", "ffprobe read %r off a %dx%d timecoded clip:\n%s" % (first, W, H, tail(out.stderr)))
            passed = False
        # 2. a frame-exact read, the way chin-line, flash-scan, framing-continuity and change-events read frames
        flag = list(passthrough())
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(clip), "-map", "0:v:0", *flag,
                            "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
        frames = len(r.stdout) // (W * H)
        if r.returncode == 0 and frames == FPS * SECONDS:
            ok("frame read", "%d of %d frames, passthrough sync (%s)" % (frames, FPS * SECONDS, " ".join(flag)))
        else:
            bad("frame read", "%d of %d frames with %s (exit %d):\n%s" % (
                frames, FPS * SECONDS, " ".join(flag), r.returncode, tail(r.stderr.decode("utf-8", "replace"))))
            passed = False
        # 3. a two-segment splice, rendered: the step-2 chain (trim, fps, crossfade, the limiter) and the encoder
        bash = git_bash()
        if not SPLICE.is_file():
            warn("splice", "no %s here: the splice is not tested" % SPLICE.relative_to(REPO))
            return passed
        if not bash:
            bad("splice", "no Git Bash found to run splice.sh (install Git for Windows)")
            return False
        work.mkdir(parents=True, exist_ok=True)
        (work / "cuts.json").write_text(json.dumps({"segments": [
            {"clip": "take.mov", "start": a, "end": b} for a, b in SEGMENTS]}), encoding="utf-8")
        env = dict(os.environ, RENDER="1", REFINE="0", AMPLIFY_DB="0")
        r = subprocess.run([bash, str(SPLICE), str(job)], capture_output=True, text=True, errors="replace", env=env)
        mp4 = job / "outputs" / (job.name + ".mp4")
        want = sum(b - a for a, b in SEGMENTS)
        got = None
        if r.returncode == 0 and mp4.is_file():
            p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(mp4)],
                               capture_output=True, text=True)
            try:
                got = float(json.loads(p.stdout)["format"]["duration"])
            except (ValueError, KeyError, TypeError):
                got = None
        if got is not None and abs(got - want) < 0.1:
            ok("splice", "a two-segment cut rendered: %.2f s, the EDL's %.2f s" % (got, want))
        else:
            bad("splice", "splice.sh (RENDER=1) on a two-segment test cut: exit %d, %s:\n%s" % (
                r.returncode, "%.2f s against %.2f s" % (got, want) if got is not None else "no render",
                tail(r.stderr + r.stdout, 10)))
            passed = False
        return passed
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
        shutil.rmtree(str(work), ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--smoke", action="store_true", help="also run the smoke (under 30 s)")
    args = ap.parse_args(argv)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        bad("self-test", "no ffmpeg/ffprobe on PATH to test")
        return 2
    passed = check_vocabulary()
    if args.smoke:
        passed = smoke() and passed
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
