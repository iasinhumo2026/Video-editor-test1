#!/usr/bin/env python3
"""load-sfx-pack.py: the whole SFX pack (assets/sfx/) into the Resolve media pool's `sfx` bin, for hand placing (Resolve lane).

Office Hours, 2026-10-13 (a member finishing in Resolve): "throw in all of the sound effects into the media bin so that
I can custom place some myself". The pipeline's own cues only ever import the handful of files a plan names; this puts
every sound one drag away. Nothing on any timeline is touched.

Runs INSIDE Resolve's embedded Python through the davinci-resolve MCP's `run_script_unsafe` (it lists the pack on disk,
which the sandboxed run_script cannot), into the project open in Resolve. From a shell it prints that call:

  uv run lanes/resolve/load-sfx-pack.py           # print the run_script_unsafe call for this checkout
  uv run lanes/resolve/load-sfx-pack.py --dry     # ... one that counts what is in and what would come in, touching nothing

    run_script_unsafe  timeout: 60  script:
      "import io; ROOT='/abs/repo'; exec(io.open('/abs/lanes/resolve/load-sfx-pack.py', encoding='utf-8').read())"

The pack is workflows/sfx-plan.py's pack_files() (every audio file under assets/sfx, its sub-folders mirrored as
sub-bins of `sfx`). A file already anywhere in the pool (found by File Path: a cue place-sfx.py imported, an earlier
load) is never imported twice. Then every pack file is read back from the pool and the project is saved (never an
"Untitled Project"); a file that did not come in is named. ASCII output only (Resolve's embedded Python).
"""
import io, os, sys


def norm(p):
    return os.path.normcase(os.path.normpath(p))


def clip_path(mpi):
    props = None
    try:
        props = mpi.GetClipProperty()
    except Exception:
        pass
    if isinstance(props, dict) and props.get('File Path'):
        return props['File Path']
    return mpi.GetClipProperty('File Path') or ''


def pack(root):
    """workflows/sfx-plan.py's pack_files(), the pack's one definition."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('sfx_plan', os.path.join(root, 'workflows', 'sfx-plan.py'))
    planner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner)
    return planner.PACK_BIN, planner.pack_files(os.path.join(root, 'assets', 'sfx'))


def in_pool(mp):
    def walk(folder):
        got = [norm(clip_path(m)) for m in folder.GetClipList() or []]
        for sub in folder.GetSubFolderList() or []:
            got += walk(sub)
        return got
    return set(walk(mp.GetRootFolder()))


def load(resolve, root, dry=False, out=print):
    """Every pack file into the open project's `sfx` bin -> True when every one reads back from the pool."""
    if not root or not os.path.isdir(os.path.join(root, 'assets', 'sfx')):
        raise SystemExit('ROOT=%r is not this repo (no assets/sfx under it): set ROOT in the wrapper' % root)
    bin_name, files = pack(root)
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    if not proj:
        raise SystemExit('no project is open in Resolve')
    mp = proj.GetMediaPool()
    have = in_pool(mp)
    want = [(folder, path) for folder, path in files if norm(path) not in have]
    out('project "%s": %d pack file(s), %d already in the pool, %d to import' % (proj.GetName(), len(files),
                                                                               len(files) - len(want), len(want)))
    if dry or not want:
        if dry:
            out('dry: nothing imported')
        return not want
    was = mp.GetCurrentFolder()
    try:
        for folder in sorted({f for f, _ in want}):
            target = mp.GetRootFolder()
            for name in [bin_name] + [x for x in folder.split('/') if x]:
                target = next((s for s in target.GetSubFolderList() or [] if s.GetName() == name), None) or mp.AddSubFolder(target, name)
                if not target:
                    raise SystemExit('could not make the bin "%s" (a Resolve modal up?): nothing more imported' % name)
            mp.SetCurrentFolder(target)
            mp.ImportMedia([{'FilePath': path} for f, path in want if f == folder])
    finally:
        if was:
            mp.SetCurrentFolder(was)
    have = in_pool(mp)
    failed = [path for _, path in files if norm(path) not in have]
    out('imported %d into the %s bin; %d of %d pack files in the pool' % (len(want) - len(failed), bin_name,
                                                                       len(files) - len(failed), len(files)))
    for path in failed:
        out('  NOT IMPORTED ' + path)
    if proj.GetName() == 'Untitled Project':
        out('NOT saved: the project is "Untitled Project" (a save opens a name dialog that hangs the script); save it by hand')
    else:
        ok = pm.SaveProject()
        out('save: %s' % ('ok' if ok else 'FAILED (SaveProject returned %r: a Resolve modal up?)' % ok))
    return not failed


def shell_main(argv):
    if '-h' in argv or '--help' in argv:
        print(__doc__)
        return 0
    bad = [x for x in argv if x != '--dry']
    if bad:
        raise SystemExit('not understood: %s (--help)' % ' '.join(bad))
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _bin, files = pack(root)
    print('%d pack file(s) under %s. Run it in Resolve: the davinci-resolve MCP tool run_script_unsafe, timeout 60, '
          'script:\n' % (len(files), os.path.join(root, 'assets', 'sfx')))
    print('; '.join(['import io', 'ROOT=%r' % root] + (['DRY=True'] if '--dry' in argv else [])
                    + ["exec(io.open(%r, encoding='utf-8').read())" % os.path.abspath(__file__)]))
    return 0


if 'resolve' in globals():
    load(globals()['resolve'], globals().get('ROOT', ''), bool(globals().get('DRY')))
elif __name__ == '__main__':
    sys.exit(shell_main(sys.argv[1:]))
