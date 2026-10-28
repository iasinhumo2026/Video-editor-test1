"""replace-clips.py — swap normalized audio under a LOCKED Resolve timeline, safely.

Runs INSIDE Resolve's embedded Python via Blackmagic's davinci-resolve MCP, through `run_script_unsafe` (it needs the
filesystem; the sandboxed `run_script` has no os/open). Its timeout defaults to 10 s: pass the 60 s cap.

    run_script_unsafe  timeout: 60  script:
      "import io; JOB='/abs/path/to/projects/<job>'; "
      "exec(io.open('<abs>/lanes/resolve/resolve-audio-polish/replace-clips.py', encoding='utf-8').read())"

Pass JOB in from the wrapper as above (or export RESOLVE_JOB before launching Resolve).
Expects normalized copies already rendered by workflows/normalize-sections.sh into
<JOB>/audio-normalized/, matched to media pool clips BY FILENAME.

WHY ReplaceClip AND NOT A RE-EDIT. The timeline references media pool CLIPS, not files, so
repointing a clip's media leaves every cut, trim, slip and hand edit exactly where it is.
That is what makes an audio pass safe to run on a timeline that has already been hand-cut —
which is the only time you should be running one.

WHY THE BEFORE/AFTER SNAPSHOT. "Nothing moved" is a claim, and on a 200-clip timeline nobody
can eyeball it. Every track's (name, start, duration, source start, source end) is captured before
the swap and diffed after; the pass is only correct if every track reports UNCHANGED. The source
times are what a re-clocked clip moves: ReplaceClip re-ingests at the file's native rate, so an
iPhone take's 29.97 FPS property comes back 30.0 and every V1 item plays the wrong source frames
with every start and duration intact (2026-10-13). A clip whose FPS was set (every iPhone take) is
never swapped: lay the timeline from audio-normalized/ instead (davinci-resolve § Step 3).

REVERT. Each clip's original path is written to audio-normalized/REVERT.json as it is
replaced. To undo, set REVERT = True in the wrapper beside JOB (or RESOLVE_REVERT=1). A clip already
on its target is skipped, and a re-run merges into an existing map, so the originals are never lost.

Resolve's embedded Python opens files as ASCII — io.open(..., encoding='utf-8') everywhere.
"""
import io
import json
import os

try:
    JOB                  # noqa: F821 — pre-set by the run_script_unsafe wrapper (see docstring)
except NameError:
    JOB = os.environ.get("RESOLVE_JOB", "")
if not JOB:
    raise SystemExit("set JOB in the run_script_unsafe wrapper (or RESOLVE_JOB env) "
                     "to the absolute projects/<job> folder")
try:
    REVERT              # noqa: F821 — True = put the original media back from REVERT.json (set in the wrapper)
except NameError:
    REVERT = os.environ.get("RESOLVE_REVERT", "") == "1"

NORM = os.path.join(JOB, "audio-normalized")
MAP = os.path.join(NORM, "REVERT.json")

pm = resolve.GetProjectManager()          # noqa: F821
proj = pm.GetCurrentProject()
mp = proj.GetMediaPool()
tl = proj.GetCurrentTimeline()
print("project :", proj.GetName())
print("timeline:", tl.GetName(), tl.GetStartFrame(), "->", tl.GetEndFrame())


def src_time(c, which):
    # the SOURCE time an item plays from: a swap that keeps every start and duration can still move it (a clip
    # re-ingests at its native FPS, so an iPhone take's 29.97 FPS property reverts to 30.0 and every V1 item reads
    # source frames by the wrong clock: 2-20 frames late across an 11-minute take, 2026-10-13). None = no readback.
    try:
        v = c.GetSourceStartTime() if which == 0 else c.GetSourceEndTime()
        return None if v is None else float(v)
    except Exception:
        return None


def snapshot():
    s = {}
    for kind, n_tracks in (("V", tl.GetTrackCount("video")), ("A", tl.GetTrackCount("audio"))):
        for t in range(1, n_tracks + 1):
            items = sorted(tl.GetItemListInTrack("video" if kind == "V" else "audio", t) or [],
                           key=lambda i: i.GetStart())
            s["%s%d" % (kind, t)] = [(c.GetName(), c.GetStart(), c.GetDuration(), src_time(c, 0), src_time(c, 1))
                                     for c in items]
    return s


SRC_TOL = 0.0002    # seconds: readback float noise sat at 0.03 ms; a 1.5 ms move already flipped a decoded frame


def same_track(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x[:3] != y[:3]:
            return False
        for p, q in zip(x[3:], y[3:]):
            if (p is None) != (q is None) or (p is not None and abs(p - q) > SRC_TOL):
                return False
    return True


def walk(folder, acc):
    for c in (folder.GetClipList() or []):
        acc.append(c)
    for f in (folder.GetSubFolderList() or []):
        walk(f, acc)
    return acc


before = snapshot()
items = walk(mp.GetRootFolder(), [])

if REVERT:
    if not os.path.exists(MAP):
        raise SystemExit("no revert map at " + MAP)
    want = json.load(io.open(MAP, encoding="utf-8"))
    print("\nREVERTING from", MAP)
else:
    if not os.path.isdir(NORM):
        raise SystemExit("no normalized dir at " + NORM + " — run workflows/normalize-sections.sh first")
    want = dict((f, os.path.join(NORM, f)) for f in sorted(os.listdir(NORM))
                if f.lower().endswith((".mp4", ".mov", ".mkv", ".m4v")))   # normalize-sections.sh's raws
    print("\nnormalized files available:", len(want))

revert, done, missing = {}, [], []
for clip in items:      # never `c`: the module's names land in the run_script_unsafe wrapper's globals
    n = clip.GetName()
    if n not in want:
        continue
    target = want[n]
    if not os.path.exists(target):
        missing.append(n)
        continue
    old = clip.GetClipProperty("File Path")
    if os.path.normpath(old) == os.path.normpath(target):
        continue        # already on its target: recording it would overwrite the true original in the map
    fps0 = clip.GetClipProperty("FPS")
    ok = clip.ReplaceClip(target)
    new = clip.GetClipProperty("File Path")
    fps1 = clip.GetClipProperty("FPS")
    # the new file is ingested at ITS native rate: a clip whose FPS was set (an iPhone take, 29.97) comes back 30.0.
    # Put it back and say so; the snapshot diff below still judges whether the items' source times survived it.
    fps_note = ""
    try:
        if abs(float(fps1) - float(fps0)) > 0.001:
            put = clip.SetClipProperty("FPS", "%g" % float(fps0))
            fps_note = "FPS %s -> %s on re-ingest, put back: %s" % (fps0, fps1,
                                                                     clip.GetClipProperty("FPS") if put else "REFUSED")
    except (TypeError, ValueError):
        if fps0 != fps1:
            fps_note = "FPS %s -> %s on re-ingest (unreadable)" % (fps0, fps1)
    revert[n] = old
    done.append((n, bool(ok), old != new, fps_note))

print("\n--- ReplaceClip ---")
for n, ok, changed, fps_note in done:
    print("  %s %-30s path changed: %s%s" % ("OK " if ok else "BAD", n, changed, ("   " + fps_note) if fps_note else ""))
print("replaced:", len(done))
if missing:
    print("MISSING on disk, skipped:", missing)

if not REVERT and revert:
    if os.path.exists(MAP):     # a re-run adds to the map; an entry already there holds the true original
        prior = json.load(io.open(MAP, encoding="utf-8"))
        prior.update(dict((k, v) for k, v in revert.items() if k not in prior))
        revert = prior
    io.open(MAP, "w", encoding="utf-8").write(json.dumps(revert, indent=2))
    print("revert map ->", MAP)

after = snapshot()
print("\n--- timeline integrity ---")
moved = 0
for k in sorted(before):
    same = same_track(before[k], after[k])
    if not same:
        moved += 1
    print("  %-4s %4d items  %s" % (k, len(after[k]), "UNCHANGED" if same else "*** MOVED ***"))
    if not same and len(before[k]) == len(after[k]):
        for x, y in zip(before[k], after[k]):
            if x[3] is not None and y[3] is not None and abs(y[3] - x[3]) > SRC_TOL:
                print("        %-30s source %+.1f ms" % (x[0], (y[3] - x[3]) * 1000))
print("timeline range:", tl.GetStartFrame(), "->", tl.GetEndFrame())
if moved:
    # ASCII only: Resolve's embedded Python may not print an em dash or a section sign on this, the path that matters
    print("\n*** %d track(s) MOVED: the swap was not clean. Revert (REVERT = True) and lay the timeline from "
          "audio-normalized/ instead (the davinci-resolve skill, Step 3). ***" % moved)
else:
    print("\nclean: every track identical before and after.")
print("save:", pm.SaveProject())
