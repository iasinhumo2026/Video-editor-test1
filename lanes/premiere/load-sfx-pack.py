#!/usr/bin/env python3
"""load-sfx-pack.py: the whole SFX pack (assets/sfx/) into the job's Premiere project, in the `sfx` bin (Premiere lane).

  uv run lanes/premiere/load-sfx-pack.py projects/<job>          # import every pack file not yet in the project, read back, save
  uv run lanes/premiere/load-sfx-pack.py projects/<job> --dry    # count what is in and what would come in, touch nothing

"Throw in all of the sound effects into the media bin so that I can custom place some myself" (Office Hours,
2026-10-13). The step-6 placer imports only the files its plan names; before the creator's own sound pass every library
sound is one drag away (presets/instagram/talking-head-explainer/sfx.md § 7). The pack is workflows/sfx-plan.py's
pack_files(): every audio file under assets/sfx, its sub-folders mirrored as sub-bins of `sfx` (the bin place-sfx.py
imports a cue's file into, so the two never import a file twice: a file already ANYWHERE in the project, found by its
media path, is skipped).

The job guard runs first (lanes/premiere/job_guard.py: the ACTIVE project must be this job's). The import goes in
batches of 40 files (a script carrying all 150 paths sits near Windows' 32,767-character command line), each read
back before the next. Every sequence's clip count is read before and after and must be IDENTICAL: loading a bin
never touches a timeline. Saved only when something came in.
"""
import json, os, subprocess, sys
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
import importlib.util
from pathlib import Path
from job_guard import require_job_project
from pes import es, es_lit                    # lanes/premiere/pes.py: the bridge's one output contract

_spec = importlib.util.spec_from_file_location('sfx_plan', Path(__file__).resolve().parents[2] / 'workflows' / 'sfx-plan.py')
planner = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(planner)

BRIDGE = Path(__file__).resolve().parent / 'premiere-bridge.mjs'
BATCH = 40

# PATHS: the batch; BIN: the bin path to import the missing ones into (["sfx", <sub-folders>...]), or null to only read
LOAD_ES = r"""(function(){
  var PATHS = %s, BIN = %s;
  var root = app.project.rootItem, seen = {};
  function walk(b){ for (var i = 0; i < b.children.numItems; i++) { var c = b.children[i];
    if (c.type === ProjectItemType.BIN) walk(c); else { try { seen[c.getMediaPath()] = 1; } catch (e) {} } } }
  walk(root);
  var want = [], k;
  for (k = 0; k < PATHS.length; k++) if (!seen[PATHS[k]]) want.push(PATHS[k]);
  if (BIN && want.length) {
    var bin = root;
    for (var n = 0; n < BIN.length; n++) { var f = null;
      for (var j = 0; j < bin.children.numItems; j++) { var c = bin.children[j];
        if (c.type === ProjectItemType.BIN && c.name === BIN[n]) { f = c; break; } }
      bin = f || bin.createBin(BIN[n]);
      if (!bin) return "ERROR: could not create the bin " + BIN[n]; }
    app.project.importFiles(want, true, bin, false);
    seen = {}; walk(root);
  }
  var missing = [];
  for (k = 0; k < PATHS.length; k++) if (!seen[PATHS[k]]) missing.push(PATHS[k]);
  return JSON.stringify({had: PATHS.length - want.length, missing: missing});
})()"""

CLIPS_ES = r"""(function(){ var n = 0, s = app.project.sequences;
  for (var i = 0; i < s.numSequences; i++) { var q = s[i], t;
    for (t = 0; t < q.videoTracks.numTracks; t++) n += q.videoTracks[t].clips.numItems;
    for (t = 0; t < q.audioTracks.numTracks; t++) n += q.audioTracks[t].clips.numItems; }
  return String(n); })()"""


def load(job, dry=False, lib=None):
    """-> True when every pack file reads back from the project and no timeline changed."""
    files = planner.pack_files(lib)
    if not files:
        sys.exit(f'✗ no audio files under {lib or "assets/sfx"}: nothing to load')
    require_job_project(es, job)
    before = int(es(CLIPS_ES))
    had, imported, missing = 0, 0, []
    groups = {}
    for folder, path in files:
        groups.setdefault(folder, []).append(path)
    for folder in sorted(groups):
        paths = groups[folder]
        for i in range(0, len(paths), BATCH):
            part = paths[i:i + BATCH]
            bin_path = None if dry else [planner.PACK_BIN] + [x for x in folder.split('/') if x]
            got = json.loads(es(LOAD_ES % (es_lit(part), es_lit(bin_path))))
            had += got['had']
            if dry:
                imported += len(got['missing'])          # what an import would bring in
            else:
                imported += len(part) - got['had'] - len(got['missing'])
                missing += got['missing']
    after = int(es(CLIPS_ES))
    if dry:
        print(f"{len(files)} pack file(s): {had} already in the project, {imported} would be imported into the "
              f"{planner.PACK_BIN} bin (--dry: nothing touched)")
        return True
    print(f"{len(files)} pack file(s): {had} already in the project, {imported} imported into the {planner.PACK_BIN} bin")
    for p in missing:
        print(f"✗ not imported: {p}")
    if after != before:
        print(f"✗ the timelines held {before} clips before the load and {after} after: a bin load never touches a "
              "timeline, so the project was NOT saved. Undo in Premiere (or close without saving) and look.")
        return False
    print(f"timelines unchanged ({after} clips)")
    if imported:
        r = subprocess.run(['node', str(BRIDGE), 'save_project'], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"✗ save_project failed: {r.stderr or r.stdout}")
        print('saved')
    return not missing


def main():
    a = sys.argv[1:]
    if '-h' in a or '--help' in a: print(__doc__); return 0
    if not a or a[0].startswith('-'): sys.exit(__doc__)
    planner.check_args(a, {'--dry'})
    return 0 if load(a[0], dry='--dry' in a) else 1


if __name__ == '__main__':
    sys.exit(main())
