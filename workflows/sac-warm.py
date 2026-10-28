#!/usr/bin/env python3
"""sac-warm.py: on Windows with Smart App Control on, load every native file the pipeline's Python tools load, once,
one at a time, before an edit needs them.

Smart App Control checks a native file online the first time it loads it (36 s for one fresh venv on the test PC,
2026-10-13), and under load that check fails as a block a second load passes: on a fresh machine 15 regression
suites died with "An Application Control policy has blocked this file" and most were green on a re-run. A release
too new to have reputation stays blocked whatever the load (numpy 2.5.4, three days old); the 14-day cooldown in
every PEP 723 header keeps those out, and this names any that still get through. Each tool's environment is built
exactly as `uv run <tool>` builds it (`uv sync --script`), so the files loaded here are the files the tools load: uv
hardlinks every environment from one cache, so a verdict paid here holds for every tool that shares the file.

  uv run workflows/sac-warm.py                       # every shipped tool that declares dependencies
  uv run workflows/sac-warm.py --only face-frame.py  # just these (comma-separated file names)
  uv run workflows/sac-warm.py --force               # even when Smart App Control reads off

Exit 0: every native file loaded (some after one retry), or nothing to do (off Windows, Smart App Control off: said
so). 1: a file stays blocked, named with its package, version and the tools that need it. 2: a tool's environment
could not be built (named). setup.sh runs it on Windows, reports, and carries on either way.
"""
import argparse
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):    # utf-8 for the ✓/✗ lines; line-buffered so setup shows each line as it lands
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
BLOCKED = 4551          # ERROR_SYSTEM_INTEGRITY_POLICY_VIOLATION: "An Application Control policy has blocked this file"
SKIP_DIRS = {".git", "projects", "node_modules", "vendor", "__pycache__", "hf-graphics", ".venv"}
STATES = {0: "off", 1: "on", 2: "evaluation"}

# The child loads one file per line of the list file it is handed and answers one JSON line each; a DLL that crashes
# the child is named by the parent from the last "start" it saw, and the rest continue in a new child. The list goes in
# a file, never stdin: the parent writing hundreds of paths into the pipe while the child's answers filled the other
# one deadlocked both (a 29-file run fit the pipe buffers; the whole repo's did not, 2026-10-13).
LOADER = r'''
import ctypes, json, sys, time
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.LoadLibraryExW.restype = ctypes.c_void_p
k32.LoadLibraryExW.argtypes = (ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32)
k32.FreeLibrary.argtypes = (ctypes.c_void_p,)
FLAGS = 0x00001100      # LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS, as Python's own import
for line in open(sys.argv[1], encoding="utf-8"):
    path = line.rstrip("\n")
    print(json.dumps({"start": path}), flush=True)
    t = time.monotonic()
    h = k32.LoadLibraryExW(path, None, FLAGS)
    err = 0 if h else ctypes.get_last_error()
    if h:
        k32.FreeLibrary(h)
    print(json.dumps({"path": path, "err": err, "s": round(time.monotonic() - t, 2)}), flush=True)
'''


def sac_state():
    """Smart App Control's state from the registry (read only): 'off', 'on', 'evaluation', or None (not on this OS)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as k:
            return STATES.get(winreg.QueryValueEx(k, "VerifiedAndReputablePolicyState")[0], "unknown")
    except (ImportError, OSError):
        return None


def vendored(root):
    """The upstream HyperFrames skills (skills-lock.json): their scripts are not the pipeline's tools."""
    try:
        return set(json.loads((root / "skills-lock.json").read_text(encoding="utf-8"))["skills"])
    except (OSError, ValueError, KeyError):
        return set()


def tools(root, only=None):
    """Every shipped .py whose PEP 723 block declares dependencies (tests excluded: they never ship)."""
    skip = vendored(root)
    out = []
    for dirpath, dirs, files in os.walk(root):
        rel = Path(dirpath).relative_to(root).parts
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith("-venv")
                   and not (rel == (".claude", "skills") and d in skip)]
        for f in files:
            if not f.endswith(".py") or f.startswith("test_") or (only and f not in only):
                continue
            p = Path(dirpath) / f
            text = p.read_text(encoding="utf-8", errors="replace")
            block = re.search(r"^# /// script\n(.*?)^# ///$", text, re.M | re.S)
            if block and re.search(r"dependencies\s*=\s*\[[\s#]*[\"']", block.group(1)):   # one a line too
                out.append(p)
    return sorted(out)


def script_env(tool):
    """Build the tool's environment as `uv run` would and return its site-packages, or (None, why)."""
    sync = subprocess.run(["uv", "sync", "-q", "--script", str(tool)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if sync.returncode:
        return None, (sync.stderr.strip().splitlines() or ["uv sync failed"])[-1]
    find = subprocess.run(["uv", "python", "find", "--script", str(tool)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    py = Path(find.stdout.strip())
    site = py.parent.parent / "Lib" / "site-packages"
    if find.returncode or not site.is_dir():
        return None, f"no environment found for it ({find.stdout.strip() or find.stderr.strip()})"
    return site, None


def owners(site):
    """Each file in a site-packages mapped to its distribution, from the dist-infos' RECORDs: path -> 'name version'."""
    out = {}
    for rec in site.glob("*.dist-info/RECORD"):
        name, _, version = rec.parent.name[:-len(".dist-info")].partition("-")
        for line in rec.read_text(encoding="utf-8", errors="replace").splitlines():
            rel = line.split(",", 1)[0]
            if rel.lower().endswith((".pyd", ".dll")):
                out[os.path.normcase(str((site / rel).resolve()))] = f"{name} {version}"   # looked up by normcase
    return out


def load_all(paths, hang=120):
    """Load each file in a child, sequentially: {path: (err, seconds)}. A file that killed its child gets err -1, one
    whose load had not returned after `hang` seconds err -2 (its child is killed); either way the rest go on."""
    results, todo, total = {}, list(paths), len(paths)
    while todo:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
            f.write("".join(p + "\n" for p in todo))
        child = subprocess.Popen([sys.executable, "-c", LOADER, f.name], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, text=True, encoding="utf-8")
        lines = queue.Queue()
        threading.Thread(target=lambda: ([lines.put(x) for x in child.stdout], lines.put(None)), daemon=True).start()
        current = None
        while True:
            try:
                line = lines.get(timeout=hang)
            except queue.Empty:
                child.kill()
                stuck = current or next(p for p in todo if p not in results)
                results[stuck] = (-2, float(hang))
                current = None
                break
            if line is None:
                break
            msg = json.loads(line)
            if "start" in msg:
                current = msg["start"]
                continue
            results[msg["path"]] = (msg["err"], msg["s"])
            current = None
            if msg["s"] >= 10:
                print(f"  · {msg['s']:.0f} s for its first look: {Path(msg['path']).name}")
            if len(results) % 50 == 0:
                print(f"  · {len(results)}/{total} files")
        child.wait()
        child.stdout.close()
        os.unlink(f.name)
        if current is not None:                      # it died loading `current`: name it, go on past it
            results[current] = (-1, 0.0)
        todo = [p for p in todo if p not in results]
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pay Smart App Control's first look at every native file the tools load.")
    ap.add_argument("--only", help="comma-separated tool file names (e.g. face-frame.py,hero-frame.py)")
    ap.add_argument("--force", action="store_true", help="run even when Smart App Control reads off")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if os.name != "nt":
        print("sac-warm: Smart App Control is Windows-only; nothing to do here")
        return 0
    state = sac_state()
    if state in (None, "off") and not args.force:
        print(f"sac-warm: Smart App Control is {state or 'not on this Windows'}; nothing to warm (--force runs anyway)")
        return 0
    only = set(args.only.split(",")) if args.only else None
    found = tools(args.root, only)
    print(f"sac-warm: Smart App Control {state}; building {len(found)} tool environments the way `uv run` does")
    files, needed_by, owner, broken = {}, {}, {}, []
    for tool in found:
        site, why = script_env(tool)
        name = tool.relative_to(args.root).as_posix()
        if site is None:
            broken.append((name, why))
            print(f"  ✗ {name}: {why}")
            continue
        print(f"  · {name}")
        owner.update(owners(site))
        for p in list(site.rglob("*.pyd")) + list(site.rglob("*.dll")):
            try:
                st = p.stat()
            except OSError:
                continue
            key = (st.st_dev, st.st_ino)              # uv hardlinks one cache file into every env: one look each
            files.setdefault(key, str(p.resolve()))
            needed_by.setdefault(files[key], set()).add(name)
    paths = sorted(set(files.values()))
    print(f"sac-warm: loading {len(paths)} native files one at a time (a first look can take tens of seconds)")
    t0 = time.monotonic()
    first = load_all(paths)
    again = [p for p, (err, _) in first.items() if err == BLOCKED]
    if again:
        time.sleep(2)
        second = load_all(again)
    else:
        second = {}
    blocked = [p for p in again if second[p][0] == BLOCKED]
    crashed = [p for p, (err, _) in first.items() if err == -1]
    hung = [p for p, (err, _) in first.items() if err == -2]
    slow = sum(1 for _, s in first.values() if s >= 5)
    standalone = sum(1 for p, (err, _) in {**first, **second}.items() if err not in (0, BLOCKED, -1, -2))
    print(f"sac-warm: {len(paths)} files in {time.monotonic() - t0:.0f} s: {len(paths) - len(blocked) - standalone - len(crashed) - len(hung)} "
          f"loaded ({len(again) - len(blocked)} after a first-look retry, {slow} took 5 s or more), {standalone} not "
          f"loadable on their own (a missing dependency or another architecture, not a block)")
    for p in crashed:
        print(f"  · {owner.get(os.path.normcase(p), '?')}: {p} ended its loader process (not a block; the tools load it inside Python)")
    for p in hung:
        print(f"  · {owner.get(os.path.normcase(p), '?')}: {p} did not finish loading in 120 s (skipped; not a block)")
    for p in blocked:
        print(f"  ✗ BLOCKED by Smart App Control: {owner.get(os.path.normcase(p), 'unknown package')} ({p})")
        print(f"    needed by: {', '.join(sorted(needed_by[p]))}")
    if blocked:
        print("sac-warm: a blocked release has no reputation yet with Smart App Control; the tools above fail until it "
              "is replaced by an older release. Report the package and version; never turn Smart App Control off for it.")
        return 1
    if broken:
        return 2
    print("sac-warm: ✓ every native file the tools load passed Smart App Control")
    return 0


if __name__ == "__main__":
    sys.exit(main())
