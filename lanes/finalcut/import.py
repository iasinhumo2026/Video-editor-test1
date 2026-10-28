#!/usr/bin/env python3
"""import.py: import a lane FCPXML into the patched Final Cut as a NEW library, then prove it landed clip for clip.

  uv run lanes/finalcut/import.py <built.fcpxml> [--timeout 120]

Final Cut's own import (NSWorkspace open of the .fcpxml with the patched app), never SpliceKit's `fcpxml.import`:
that routes the XML through the pasteboard (it overwrites the clipboard) and failed on FCP 12.3 with a nil-insert
exception, leaving a "Which library do you want to import (null) into?" sheet (2026-09-25). The FCPXML's
`<import-options>` names the library location, so FCP creates the library with no dialog.

The lane's patched copy is made the running Final Cut first, by its path (doctor.py ensure: a Final Cut that is not
the copy is quit, since it would take the import, lab-notes § 21).
It refuses when the target .fcpbundle already exists (FCP would ask which library to use), waits until the project
opens through the bridge, fails on a dialog still open 15 s later (a progress sheet is transient), then runs verify.py against the live export.
Exit: 0 imported and identical · 1 imported but different · 2 refused / not imported.
"""
import argparse, os, re, subprocess, sys, time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sk import call, dismiss_notification_sheet, open_project  # noqa: E402
from doctor import ensure  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('fcpxml')
    ap.add_argument('--timeout', type=float, default=120)
    a = ap.parse_args()
    x = Path(a.fcpxml).read_text(encoding="utf-8")
    lib = re.search(r'key="library location" value="file://([^"]+)"', x)
    proj = re.search(r'<project name="([^"]+)"', x)
    if not lib or not proj:
        print('✗ not a lane FCPXML: no library location / project', file=sys.stderr)
        return 2
    lib_path = lib.group(1).replace('%20', ' ')
    if os.path.exists(lib_path):
        print(f'✗ {lib_path} already exists: close it in FCP (File > Close Library) and move it aside first', file=sys.stderr)
        return 2
    app = ensure()               # the lane's copy running, launched by its path, its bridge proven (doctor.py)
    if not app:
        return 2
    dismiss_notification_sheet()
    subprocess.run(['open', '-a', app, os.path.abspath(a.fcpxml)], check=True)
    t0, ok = time.time(), False
    while time.time() - t0 < a.timeout:
        time.sleep(3)
        try:
            open_project(proj.group(1))
            ok = True
            break
        except Exception:
            pass
    for _ in range(6):            # an import leaves a transient progress sheet up for a few seconds
        dismiss_notification_sheet()
        dialogs = call('dialog.detect').get('dialogCount', 0)
        if not dialogs:
            break
        time.sleep(2.5)
    if not ok:
        print(f'✗ project "{proj.group(1)}" did not open within {a.timeout:.0f} s (dialogs open: {dialogs})', file=sys.stderr)
        return 2
    if dialogs:
        print(f'✗ imported, but {dialogs} dialog(s) are open in FCP: read them with sk.py dialog.detect', file=sys.stderr)
        return 2
    print(f'✓ imported "{proj.group(1)}" into {lib_path} in {time.time() - t0:.0f} s', flush=True)
    return subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'verify.py'), a.fcpxml]).returncode


if __name__ == '__main__':
    sys.exit(main())
