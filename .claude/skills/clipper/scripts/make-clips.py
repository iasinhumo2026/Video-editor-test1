#!/usr/bin/env python3
"""make-clips.py: scaffold and build clip sub-jobs from a clips-plan.json.

Part of the clipper skill. Reads projects/<parent>/clips-plan.json (authored by
the skill's selection pass) and turns each approved clip into a standard job
folder under projects/<parent>/clips/<name>/, then (with --build) runs the full
lane per clip: rough-cut splice, 9:16 face-centered reframe, locked tiktok-raw
captions, deliverable + export copy. A plan with "parent_job" (the job the
long-form was edited in) is cut from that job's RAW footage: each published-timeline
segment is mapped through its cuts.json, so no burned-in graphic reaches the crop.

Usage:
  uv run .claude/skills/clipper/scripts/make-clips.py <parent_job_dir>              # scaffold only
  uv run .claude/skills/clipper/scripts/make-clips.py <parent_job_dir> --build      # scaffold + build all
  uv run .claude/skills/clipper/scripts/make-clips.py <parent_job_dir> --build --only <name> [<name> ...]

Env:
  AMPLIFY_DB   the creator's manual override of the measured gain, passed through to splice.sh (a deviation,
               recorded in RUN.md); never set it to quiet an audio-qa warning on your own.
  VE_EXPORT_DIR  overrides the ~/Downloads export-copy target

Per clip, --build does:
  1. splice.sh RENDER=0 (refine + frame-snap), then cut-audit.py --grid <the source's rate> --promote: every cut
     proven on the waveform (rough-cut § Audit the cut), then splice.sh renders exactly the audited EDL
                                   -> outputs/<name>.mp4 (16:9) + canonical transcript
  2. face-frame.py measures the face -> face-centered crop to 1080x1920
     (center crop when no face is detectable, e.g. screencast-heavy clips);
     the 16:9 original is kept as outputs/<name>-169.mp4
  3. presets/tiktok/raw/build.py  -> outputs/<name>.final.mp4 (captions always on,
     hook card only when the plan gives hook_text)
  4. flash-scan.py on the deliverable, the clip's joints expected (review/flash-scan.json): a FAIL fails the clip and
     no export copy is made (a published long-form has picture cuts of its own the audio-only tools never see: an
     edge a frame past one is a one-frame shot); so does a first or last shot of 2 frames or fewer, which flash-scan
     lists only as an unexpected cut
  5. export copy of the deliverable into ~/Downloads (or VE_EXPORT_DIR)
Once every clip has built, it ends on finalize.sh's Next: line (it never runs finalize.sh): the bake-preset offer.
A parent's corrections.local.json (the clips job's, else the parent_job's) is merged into each clip folder at scaffold:
export-transcript.py reads only the clip folder's, and the sponsor's name shipped misspelled on a clip ("Habata").
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
# Windows consoles/pipes default to cp1252, which can't encode the {glyphs} glyphs in this
# script's status lines: a cosmetic print must never kill a pipeline step (it did once,
# 2026-08-13, mid-splice on a real Windows job). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

REPO = Path(__file__).resolve().parents[4]
SPLICE = REPO / ".claude/skills/rough-cut/scripts/splice.sh"
FACE_FRAME = REPO / "workflows/face-frame.py"
TIKTOK_BUILD = REPO / "presets/tiktok/raw/build.py"
CUT_AUDIT = REPO / "workflows/cut-audit.py"
FLASH_SCAN = REPO / "workflows/flash-scan.py"
INHERITED = "_inherited_from"      # marks a clip's corrections.local.json as make-clips' merge (rewritten each scaffold)


def die(msg):
    sys.exit(f"make-clips: {msg}")


def git_bash():
    """The bash to run splice.sh with: plain `bash` on macOS/Linux; Git Bash on Windows, never by bare name, because
    CreateProcess searches System32 before PATH and System32's bash.exe is WSL's (the kit's sh_argv, 2026-10-13)."""
    if os.name != "nt":
        return "bash"
    for c in [shutil.which("bash")] + [os.path.join(os.environ.get(v, ""), "Git", "bin", "bash.exe")
                                       for v in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")]:
        if c and os.path.exists(c) and "system32" not in c.lower():
            return c
    die("no Git Bash found to run splice.sh (install Git for Windows)")


def run(cmd, **kw):
    """Run a child streaming its output (audio-qa warnings must stay visible)."""
    print(f"  $ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run([str(c) for c in cmd], **kw).returncode


def probe_wh(video):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)])
    # iPhone footage carries stream side data that the csv writer emits as extra
    # elements/rows ("1920,1080," or an extra line): keep the first two real tokens.
    tok = [t for t in out.decode().strip().splitlines()[0].split(",") if t.strip()]
    return int(tok[0]), int(tok[1])


def probe_rate(video):
    """The video's r_frame_rate (num/den), the grid its splice snaps to."""
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=r_frame_rate", "-of", "csv=p=0", str(video)]).decode()
    return (out.split() or ["30000/1001"])[0].rstrip(",")   # first row: ffprobe 9 prints a timecoded row twice


def inherit_corrections(cdir, parent, pjob=None):
    """Merge the parent's per-job corrections into the clip folder, the only place export-transcript.py looks: the
    parent_job's, then the clips job's on top (the nearer job wins). A clip's own hand-made file is left alone."""
    srcs = [p / "corrections.local.json" for p in (pjob, parent) if p is not None]
    srcs = [s for s in srcs if s.exists()]
    dst = cdir / "corrections.local.json"
    if dst.exists():
        try:
            mine = INHERITED not in json.loads(dst.read_text(encoding="utf-8"))
        except ValueError:
            mine = True
        if mine:
            if srcs:
                print(f"  {cdir.name}: keeps its own corrections.local.json (the parent's not merged in)")
            return
    if not srcs:
        if dst.exists():
            dst.unlink()                   # our merge from a parent file that is gone
        return
    auto, flag = {}, []
    for s in srcs:
        c = json.loads(s.read_text(encoding="utf-8"))
        auto.update(c.get("auto", {}))
        flag += [w for w in c.get("flag", []) if w not in flag]
    dst.write_text(json.dumps({INHERITED: [str(s) for s in srcs], "auto": auto,
                               "flag": [w for w in flag if w.lower() not in {k.lower() for k in auto}]},
                              indent=1) + "\n", encoding="utf-8")


def encoder_args():
    if platform.system() == "Darwin":
        return ["-c:v", "h264_videotoolbox", "-b:v", "10M"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]


def scratch_root():
    """Where splice.sh reads a clip's working EDL: /tmp/video-editor on macOS/Linux, %TEMP%\\video-editor on Windows
    (Git Bash's /tmp IS %TEMP%, so the shell and this script meet in the same folder)."""
    return os.path.join("/tmp" if os.name != "nt" else tempfile.gettempdir(), "video-editor")


def link_into(dst_dir, src):
    link = dst_dir / src.name
    if not link.exists():
        try:
            os.link(src, link)             # same volume: zero bytes copied
        except OSError:
            shutil.copy2(src, link)        # cross-volume fallback


def parent_timeline(pjob):
    """The parent job's EDL laid on its PUBLISHED timeline: [(timeline start, timeline end, raw clip, raw in)], from
    each segment's `_timeline` readback when the EDL carries one (a hand-edited or mixed-rate timeline), else the
    running sum of segment lengths (the splice's own arithmetic)."""
    segs = json.loads((pjob / "transcript" / "cuts.json").read_text(encoding="utf-8"))["segments"]
    out, t = [], 0.0
    for s in segs:
        a, b = float(s["start"]), float(s["end"])
        t0, t1 = (float(s["_timeline"][0]), float(s["_timeline"][1])) if s.get("_timeline") else (t, t + b - a)
        out.append((t0, t1, os.path.basename(s["clip"]), a))
        t += b - a
    return out


def words_in(words, clip, a, b):
    """The parent's words (raw clock) whose midpoint falls in [a, b) of `clip`, as one line of text."""
    for c in words.get("clips", []):
        if os.path.basename(c.get("clip", "")) == clip:
            return " ".join(w.get("w") or w.get("word") or "" for w in c.get("words", [])
                            if "start" in w and "end" in w and a <= (w["start"] + w["end"]) / 2 < b).strip()
    return ""


def to_raw(seg, tl, words):
    """One clip segment on the PUBLISHED timeline -> the parent's raw segments that play it, split at the parent's
    cuts. An edge on a parent cut is pinned on its own (pin_in / pin_out): that boundary was refined and polished in
    the parent job already, and re-refining it could pull a word the parent killed back in. The clip's own start and end
    are refined like any cut (a whole-piece no_refine froze them too, review 2026-09-27)."""
    a, b = float(seg["start"]), float(seg["end"])
    pieces = []
    for t0, t1, clip, r0 in tl:
        x, y = max(a, t0), min(b, t1)
        if y - x <= 1e-3:
            continue
        s0, s1 = r0 + x - t0, r0 + y - t0
        piece = {k: v for k, v in seg.items() if k not in ("start", "end", "transcript", "clip")}
        piece.update(clip=clip, start=round(s0, 6), end=round(s1, 6), transcript=words_in(words, clip, s0, s1))
        if x > a + 1e-3:
            piece["pin_in"] = True                      # starts on a parent cut
        if y < b - 1e-3:
            piece["pin_out"] = True                     # ends on a parent cut
        pieces.append(piece)
    if not pieces:
        die(f"segment {a:.3f}-{b:.3f} of the published timeline is outside the parent job's EDL")
    covered = sum(p["end"] - p["start"] for p in pieces)
    if abs(covered - (b - a)) > 0.05:
        die(f"segment {a:.3f}-{b:.3f}: the parent's EDL covers {covered:.3f} s of its {b - a:.3f} s (a gap in the parent)")
    return pieces


def scaffold(parent, clip, source, words, pjob=None):
    """Create the clip's standard job folder + authored cuts (durable and /tmp). With `pjob` (the plan's parent_job)
    the clip is cut from the parent's RAW footage instead of the published file: a published long-form made here
    carries its graphics burned in, and the 9:16 face-centred reframe cut them to fragments ("ling", "ally important"
    on the Windows test clip, 2026-09-27)."""
    name = clip["name"]
    cdir = parent / "clips" / name
    for sub in ("raw", "transcript", "outputs"):
        (cdir / sub).mkdir(parents=True, exist_ok=True)
    inherit_corrections(cdir, parent, pjob)

    wcopy = cdir / "transcript" / "words.json"
    if pjob is None:
        link_into(cdir / "raw", source)
        if not wcopy.exists():
            shutil.copy2(words, wcopy)
        segments = []
        for seg in clip["segments"]:
            s = dict(seg)
            s.setdefault("clip", source.name)
            segments.append(s)
    else:
        pwords = json.loads((pjob / "transcript" / "words.json").read_text(encoding="utf-8"))
        tl = parent_timeline(pjob)
        segments = [p for seg in clip["segments"] for p in to_raw(seg, tl, pwords)]
        for c in sorted({s["clip"] for s in segments}):
            if not (pjob / "raw" / c).exists():
                die(f"the parent's raw {pjob / 'raw' / c} is missing")
            link_into(cdir / "raw", pjob / "raw" / c)
        shutil.copy2(pjob / "transcript" / "words.json", wcopy)     # the raw clock the segments now run on
    cuts = {"segments": segments}

    # Durable authored copy (macOS wipes /tmp) + the /tmp copy splice.sh reads.
    (cdir / "transcript" / "cuts.authored.json").write_text(
        json.dumps(cuts, indent=1) + "\n", encoding="utf-8")
    work = Path(scratch_root()) / name
    work.mkdir(parents=True, exist_ok=True)
    (work / "cuts.json").write_text(json.dumps(cuts, indent=1) + "\n", encoding="utf-8")

    dur = sum(s["end"] - s["start"] for s in segments)
    print(f"  scaffolded clips/{name}  ({len(segments)} segment(s), {dur:.1f}s)")
    return cdir


def splice(cdir, render=True):
    """splice.sh on the clip folder; render=False is RENDER=0 (refine, frame-snap, persisted EDL, no encode)."""
    env = None if render else {**os.environ, "RENDER": "0"}
    if run([git_bash(), SPLICE, cdir], env=env) != 0:
        raise RuntimeError("splice failed (see output above)")


def audit(cdir, name):
    """Every cut proven on the waveform on the source's grid (rough-cut § Audit the cut): cut-audit.py --promote writes
    the audited EDL over transcript/cuts.json, and the /tmp EDL the render splice reads becomes that file. Without it
    a clip shipped a cut 146 ms into its "And" and a tail one frame into the published file's next shot (2026-10-13)."""
    raws = sorted(p for p in (cdir / "raw").iterdir() if p.suffix.lower() in (".mp4", ".mov", ".m4v", ".mkv"))
    if not raws:
        raise RuntimeError("no raw to audit against")
    (cdir / "review").mkdir(exist_ok=True)
    if run(["uv", "run", CUT_AUDIT, cdir, "--grid", probe_rate(raws[0]), "--promote",
            "--sheet", cdir / "review" / "cut-audit-sheet.png"]) != 0:
        raise RuntimeError("cut-audit failed (see output above)")
    shutil.copy2(cdir / "transcript" / "cuts.json", Path(scratch_root()) / name / "cuts.json")


def joints(cdir):
    """The clip's cut points on its own timeline (seconds), from the persisted EDL."""
    segs = json.loads((cdir / "transcript" / "cuts.json").read_text(encoding="utf-8"))["segments"]
    out, t = [], 0.0
    for s in segs[:-1]:
        t += float(s["end"]) - float(s["start"])
        out.append(round(t, 4))
    return segs, out


EDGE_SHOT_FRAMES = 2   # a first or last shot this short is a flash flash-scan cannot call: it has one neighbour


def flash_gate(final, cdir, name):
    """flash-scan.py on the deliverable with the clip's joints expected. The published file's own cuts inside a span
    are warnings; a flash or a double cut fails the clip, named on the source clock. So does a FIRST or LAST shot of
    EDGE_SHOT_FRAMES or fewer: an IN a frame before a picture cut of the source (or an OUT a frame past one) opens (or
    ends) the clip on a one-frame shot, which flash-scan lists only as an unexpected cut, having no neighbour on that
    side to call a flash (the Windows test clip, 2026-10-13: an IN refined back into "For" opened on a frame of the
    previous shot, flash-scan PASS)."""
    segs, js = joints(cdir)
    rep = cdir / "review" / "flash-scan.json"
    rep.parent.mkdir(exist_ok=True)
    rep.unlink(missing_ok=True)            # this build's report only, never the last build's
    cmd = ["uv", "run", FLASH_SCAN, final, "--json", rep]
    if js:
        cmd += ["--expect-times", ",".join(f"{j:.4f}" for j in js)]
    rc = run(cmd)
    try:
        d = json.loads(rep.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if rc == 0:
            return
        raise RuntimeError(f"flash-scan failed on {final.name} with no report")
    starts = [0.0] + js
    src = lambda t, k: float(segs[k]["start"]) + t - starts[k]
    where = []
    for f in d.get("flashes", []) + d.get("double_cuts", []):
        t = float(f["t"])
        k = max(i for i, t0 in enumerate(starts) if t0 <= t + 1e-6)
        where.append(f"{f.get('timecode', '')} = source {src(t, k):.3f} s (segment {k + 1})")
    n = int(d.get("frames") or 0)
    for c in d.get("cuts", []):
        f = int(c["frame"])
        if c.get("expected"):
            continue
        if f <= EDGE_SHOT_FRAMES:
            where.append(f"the first shot is {f} frame{'s' if f > 1 else ''} ({c.get('timecode', '')}): segment 1's start "
                         f"{float(segs[0]['start']):.3f} s sits before a picture cut of the source at about "
                         f"{src(float(c['t']), 0):.3f} s")
        elif n and n - f <= EDGE_SHOT_FRAMES:
            k = len(segs) - 1
            where.append(f"the last shot is {n - f} frame{'s' if n - f > 1 else ''} ({c.get('timecode', '')}): segment "
                         f"{k + 1}'s end {float(segs[k]['end']):.3f} s runs past a picture cut of the source at about "
                         f"{src(float(c['t']), k):.3f} s")
    if rc == 0 and not where:
        return
    raise RuntimeError(f"flash gate FAIL ({rep}): {'; '.join(where) or 'see the report'}. An edge a frame or two from a "
                       "picture cut of the source leaves a one-frame shot: move that segment's edge onto the source's "
                       "cut in clips-plan.json (pin_in / pin_out) and rebuild with --only " + name)


def reframe(cdir, name):
    """Face-centered crop of the spliced 16:9 base to the 1080x1920 clean base."""
    base = cdir / "outputs" / f"{name}.mp4"
    if not base.exists():
        die(f"{name}: splice produced no {base}")
    w, h = probe_wh(base)
    if (w, h) == (1080, 1920):
        print(f"  {name}: already 1080x1920, no reframe needed")
        return

    vf = None
    rc = run(["uv", "run", FACE_FRAME, base])
    ff_json = cdir / "face-frame.json"
    if rc == 0 and ff_json.exists():
        data = json.loads(ff_json.read_text(encoding="utf-8"))
        vf = data.get("reframe", {}).get("ffmpeg")
    if vf is None:
        crop_w = round(h * 9 / 16 / 2) * 2
        crop_x = max(0, (w - crop_w) // 2 // 2 * 2)
        vf = f"crop={crop_w}:{h}:{crop_x}:0,scale=1080:1920"
        print(f"  {name}: no measurable face, using center crop")

    wide = cdir / "outputs" / f"{name}-169.mp4"
    shutil.move(base, wide)
    rc = run(["ffmpeg", "-y", "-v", "error", "-i", wide, "-vf", vf,
              *encoder_args(), "-c:a", "copy", "-movflags", "+faststart", base])
    if rc != 0:
        shutil.move(wide, base)   # restore the base so a re-run starts clean
        die(f"{name}: reframe ffmpeg failed")
    print(f"  {name}: reframed to 1080x1920 ({vf})")


def built_time(cdir, t):
    """A clip-timeline second of the AUTHORED plan (cuts.authored.json: the plan's segments, on the raw clock for a
    parent_job, same order and lengths) -> the same moment on the BUILT timeline (transcript/cuts.json after refine and
    the audit, which move and trim edges). A moment the build trimmed away lands on the nearest kept edge."""
    seg_list = lambda p: json.loads(p.read_text(encoding="utf-8"))["segments"]
    auth, built = seg_list(cdir / "transcript" / "cuts.authored.json"), seg_list(cdir / "transcript" / "cuts.json")
    acc = 0.0
    for s in auth:
        a, b = float(s["start"]), float(s["end"])
        if t <= acc + (b - a) + 1e-9 or s is auth[-1]:
            clip, src = os.path.basename(s["clip"]), a + t - acc
            break
        acc += b - a
    best, acc = None, 0.0
    for s in built:
        a, b = float(s["start"]), float(s["end"])
        if os.path.basename(s["clip"]) == clip:
            d = max(a - src, 0.0, src - b)
            if best is None or d < best[0]:
                best = (d, acc + min(max(src, a), b) - a)
        acc += b - a
    return round(best[1], 3) if best else t


def captions(cdir, name, clip):
    final = cdir / "outputs" / f"{name}.final.mp4"
    # uv run, never python3 or sys.executable, so build.py's PEP 723 pillow dep is honoured.
    # --deliver: this burn IS the clip's deliverable, so it takes the vertical file's numbers (workflows/deliver.py)
    cmd = ["uv", "run", TIKTOK_BUILD, cdir, "--hook-text", clip.get("hook_text", ""), "--out", final, "--deliver"]
    if clip.get("hook_end") is not None:
        # hook_end is authored on the plan's clip timeline; the refine and the audit move edges after it was written
        # (an audited 234 ms tail trim left the card 4 frames into the next sentence, 2026-10-13)
        he = built_time(cdir, float(clip["hook_end"]))
        if abs(he - float(clip["hook_end"])) > 0.0005:
            print(f"  {name}: hook_end {float(clip['hook_end']):.3f} s (plan) -> {he:.3f} s on the built timeline")
        cmd += ["--hook-end", f"{he:.3f}"]
    if run(cmd) != 0:
        die(f"{name}: caption build failed")
    return final


def export_copy(final, name):
    dl = Path(os.environ.get("VE_EXPORT_DIR") or Path.home() / "Downloads")
    if dl.is_dir():
        shutil.copy2(final, dl / final.name)
        print(f"  {name}: export copy -> {dl / final.name}")
    else:
        print(f"  {name}: export dir {dl} missing, skipped copy")


def main():
    args = sys.argv[1:]
    if not args:
        die("usage: make-clips.py <parent_job_dir> [--build] [--only <name> ...]")
    parent = Path(args[0]).resolve()
    build = "--build" in args
    only = args[args.index("--only") + 1:] if "--only" in args else None

    plan_path = parent / "clips-plan.json"
    if not plan_path.exists():
        die(f"missing {plan_path} (run the clipper selection pass first)")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    source = parent / plan["source"]
    if not source.exists():
        die(f"plan source not found: {source}")
    words = parent / "transcript" / "words.json"
    if not words.exists():
        die(f"missing {words} (transcribe the parent first)")
    # parent_job: the long-form was edited HERE, so the clip is cut from that job's raw (its segments are still
    # authored on the published timeline, from the published transcript)
    pjob = None
    if plan.get("parent_job"):
        pjob = Path(plan["parent_job"])
        pjob = (pjob if pjob.is_absolute() else REPO / pjob).resolve()
        for need in ("transcript/cuts.json", "transcript/words.json"):
            if not (pjob / need).exists():
                die(f"parent_job {pjob}: no {need}")
        print(f"cutting from the parent job's raw footage: {pjob}")

    clips = [c for c in plan["clips"] if only is None or c["name"] in only]
    if not clips:
        die("no clips matched")

    failed = []
    for clip in clips:
        name = clip["name"]
        print(f"\n=== {name} ===")
        cdir = scaffold(parent, clip, source, words, pjob)
        if not build:
            continue
        try:
            splice(cdir, render=False)
            audit(cdir, name)
            splice(cdir)
            reframe(cdir, name)
            final = captions(cdir, name, clip)
            flash_gate(final, cdir, name)
            export_copy(final, name)
            print(f"  ✓ {name}: {final}")
        except (RuntimeError, SystemExit) as e:
            print(f"  ✗ {name}: {e}")
            failed.append(name)

    if not build:
        print("\nScaffold done. Build with:  make-clips.py <parent> --build")
    elif failed:
        die(f"failed clips: {', '.join(failed)}")
    else:
        print(f"\nAll {len(clips)} clip(s) built.")
        # finished exports, as finalize.sh --apply ends on: the same offer (2026-10-14: on every finished export)
        print("Next: offer to bake these clips' creative calls into their preset (skill bake-preset), "
              "so the next clips like them come out right first try")


if __name__ == "__main__":
    main()
