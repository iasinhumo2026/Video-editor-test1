#!/usr/bin/env python3
"""sfx-pack.py: the whole SFX pack (assets/sfx/) as a Final Cut library to drag from, for hand placing (Final Cut lane).

  uv run lanes/finalcut/sfx-pack.py projects/<job>            # write projects/<job>/finalcut/sfx-pack.fcpxml
  uv run lanes/finalcut/sfx-pack.py projects/<job> --import   # ... and import it into the lane's Final Cut, checked

"Throw in all of the sound effects into the media bin so that I can custom place some myself" (Office Hours,
2026-10-13). The step-6 cues come from the plan (replay.py lays sfx-plan.json); this puts every library sound one drag
away. The pack is workflows/sfx-plan.py's pack_files(): every audio file under assets/sfx.

The FCPXML makes a NEW library `projects/<job>/finalcut/SFX Pack.fcpbundle`, the one import route proven to create no
dialog (lab-notes § 1: `library location` = a new .fcpbundle, copy assets 0, so the library references the pack in
place). Its event `sfx` holds one browser clip per file, each with the keyword `sfx` (a file in a pack sub-folder
also takes the sub-folder's name), so the pack shows as a keyword collection; clips drag from it into the job's
project in its own library. Each clip starts at its file's embedded timecode (a Broadcast-WAV's time_reference: a clip
written from 0s is DROPPED on import, lab-notes § 4), read by fcpxml_writer.probe(), and lasts the whole file.

--import runs Final Cut's own import, as import.py does (doctor.ensure: the lane's copy running by its path; the
notification sheet cleared; `open -a <copy> <fcpxml>`), waits for the library bundle and for no dialog, then reads
the event's clips back through the bridge (browser.listClips) and holds them to the pack. An existing SFX Pack library
is refused, never imported over: open it in Final Cut instead (File > Open Library).
Exit: 0 written (and imported, every clip read back) · 1 imported but the read-back disagrees or could not be read · 2 refused.
"""
import argparse, os, subprocess, sys, time
from pathlib import Path
from xml.sax.saxutils import quoteattr

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fcpxml_writer import probe, t  # noqa: E402
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location('sfx_plan', HERE.parents[1] / 'workflows' / 'sfx-plan.py')
planner = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(planner)

LIBRARY = 'SFX Pack'


def write(path, library, files):
    """The pack as one FCPXML 1.14 event of browser clips, for a NEW library. -> the clips written [(name, keyword)]."""
    res, clips, names = [], [], []
    for n, (folder, media) in enumerate(files, 1):
        info = probe(media)
        if not info['audio']:
            continue
        rid = f'r{n}'
        name = os.path.splitext(os.path.basename(media))[0]
        src = 'file://' + media.replace(' ', '%20').replace('&', '%26')
        res.append(f'<asset id="{rid}" name={quoteattr(name)} start="{t(info["tc"])}" duration="{t(info["duration"])}" '
                   f'hasAudio="1" audioSources="1" audioChannels="{info["channels"]}" audioRate="{info["rate"]}">\n'
                   f'   <media-rep kind="original-media" src={quoteattr(src)}/>\n  </asset>')
        kw = ', '.join([planner.PACK_BIN] + ([folder.replace('/', ' ')] if folder else []))
        clips.append(f'<asset-clip ref="{rid}" name={quoteattr(name)} start="{t(info["tc"])}" duration="{t(info["duration"])}" '
                     f'audioRole="effects">\n    <keyword start="{t(info["tc"])}" duration="{t(info["duration"])}" value={quoteattr(kw)}/>\n'
                     f'   </asset-clip>')
        names.append(name)
    lib = 'file://' + os.path.abspath(library).replace(' ', '%20')
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.14">
 <import-options>
  <option key="library location" value={quoteattr(lib)}/>
  <option key="copy assets" value="0"/>
  <option key="suppress warnings" value="1"/>
 </import-options>
 <resources>
  ''' + '\n  '.join(res) + f'''
 </resources>
 <library>
  <event name={quoteattr(planner.PACK_BIN)}>
   ''' + '\n   '.join(clips) + '''
  </event>
 </library>
</fcpxml>
'''
    Path(path).write_text(xml, encoding='utf-8')
    return names


def import_and_check(fcpxml, library, names, timeout=120):
    """Final Cut's own import of the pack FCPXML, then its event read back. -> exit code."""
    from sk import call, dismiss_notification_sheet  # noqa: E402
    from doctor import ensure  # noqa: E402
    app = ensure()
    if not app:
        return 2
    dismiss_notification_sheet()
    subprocess.run(['open', '-a', app, os.path.abspath(fcpxml)], check=True)
    t0 = time.time()
    while time.time() - t0 < timeout and not os.path.isdir(library):
        time.sleep(2)
    dialogs = 0
    for _ in range(6):            # an import leaves a transient progress sheet up for a few seconds
        dismiss_notification_sheet()
        dialogs = (call('dialog.detect') or {}).get('dialogCount', 0)
        if not dialogs:
            break
        time.sleep(2.5)
    if not os.path.isdir(library):
        print(f'✗ {library} did not appear within {timeout:.0f} s (dialogs open: {dialogs})', file=sys.stderr)
        return 2
    if dialogs:
        print(f'✗ imported, but {dialogs} dialog(s) are open in Final Cut: read them with sk.py dialog.detect', file=sys.stderr)
        return 2
    try:
        got = call('browser.listClips', {'event': planner.PACK_BIN}) or {}
    except Exception as e:
        print(f'⚠ imported {library}, but its clips could not be read back ({e}): open the SFX Pack library and count '
              f'{len(names)} clips in its {planner.PACK_BIN} event', file=sys.stderr)
        return 1
    listed = {c.get('name') for c in (got.get('clips') if isinstance(got, dict) else got) or [] if isinstance(c, dict)}
    lost = [n for n in names if n not in listed]
    if lost:
        print(f'✗ {len(lost)} of {len(names)} pack clips are not in the {planner.PACK_BIN} event as read back '
              f'(the active library may be another one: select SFX Pack and re-check): {", ".join(lost[:8])}'
              + (' ...' if len(lost) > 8 else ''), file=sys.stderr)
        return 1
    print(f'✓ {len(names)} pack clips in the {planner.PACK_BIN} event of {library}')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--import', dest='do_import', action='store_true', help='import it into the lane\'s Final Cut, checked')
    a = ap.parse_args()
    job = Path(a.job).resolve()
    if not job.is_dir():
        print(f'✗ no job folder {job}', file=sys.stderr)
        return 2
    files = planner.pack_files()
    if not files:
        print('✗ no audio files under assets/sfx: nothing to load', file=sys.stderr)
        return 2
    out_dir = job / 'finalcut'
    out_dir.mkdir(exist_ok=True)
    library = out_dir / f'{LIBRARY}.fcpbundle'
    if library.exists():
        print(f'✗ {library} already exists: it is the pack, already made. Open it in Final Cut (File > Open Library); '
              'to rebuild it, close it there and move it aside first', file=sys.stderr)
        return 2
    fcpxml = out_dir / 'sfx-pack.fcpxml'
    names = write(fcpxml, library, files)
    print(f'wrote {fcpxml}: {len(names)} pack clips into a new library {library.name}, event {planner.PACK_BIN}')
    if not a.do_import:
        print(f'  import it: uv run lanes/finalcut/sfx-pack.py {a.job} --import')
        return 0
    return import_and_check(fcpxml, str(library), names)


if __name__ == '__main__':
    sys.exit(main())
