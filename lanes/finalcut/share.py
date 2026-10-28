#!/usr/bin/env python3
"""share.py: Final Cut's own export of a project to a ProRes master, driven end to end through the bridge (no clicks).

  uv run lanes/finalcut/share.py projects/<job> [--project "<name>"] [--timeout 3600]
  (export.py runs it when given no --master)

The share sheet's save panel runs OUT of process (lab-notes § 9): nothing can click or type into it. But its
in-process half is an ordinary NSSavePanel in NSApp.windows, and `completeWithReturnCode:url:urls:` is the call the
remote panel makes back into Final Cut when the user presses Save. So: File > Share > Export File, Next through the
sheet, then complete the panel with the job's own path, projects/<job>/finalcut/renders/<project>-master.mov.
Final Cut renders it as it would from a click (proven 2026-09-25: a short's 3193 frames = its timeline).

Progress: Final Cut's Background Tasks window opens as the render starts (its own progress bar), and a line prints
every 5 s here: percent of the sheet's size estimate, GB written, time left.

The sheet's Settings tab is set here on every export (Video and Audio / ProRes 422 / Save only), from inside Final
Cut, so a fresh install needs no setup for it. A project whose library Final Cut reopened unloaded is loaded first.
The project defaults to the newest projects/<job>/finalcut/*.fcpxml's. The master is proven before it is returned:
ProRes, the timeline's frame count (from that FCPXML). Exit: 0 written · 1 rendered but wrong · 2 could not export.
"""
import argparse, glob, os, re, subprocess, sys, time
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sk import call, m, BridgeError, dismiss_notification_sheet, open_project  # noqa: E402
from doctor import ensure  # noqa: E402


class Fail(Exception):
    pass


def dialogs():
    return call('dialog.detect').get('dialogs') or []


def wait(what, pred, timeout, step=0.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = pred()
        if r:
            return r
        time.sleep(step)
    raise Fail(f'{what} did not happen within {timeout:.0f} s')


WANT = (('Video and Audio', ('Video and Audio',)),                          # Format
        ('Apple ProRes 422', ('Source - Apple ProRes 422', 'Apple ProRes 422')),  # Video codec
        ('Save only', ('Save only',)))                                     # Action


def views(v, cls, out):
    if m(v, 'className')['result'] == cls:
        out.append(v)
    subs = m(v, 'subviews', handle=True)['handle']
    for i in range(int(m(subs, 'count')['result'])):
        views(m(subs, 'objectAtIndex:', [{'type': 'int', 'value': i}], handle=True)['handle'], cls, out)
    return out


def configure_sheet():
    """The Export File sheet's Settings tab, set to what the lane renders: Video and Audio, ProRes 422 (the project's
    Source codec when that is ProRes 422), Action Save only. Its popups sit in FFSharePanel.settingsView; an item is
    chosen through the popup's menu (performActionForItemAtIndex:, an int: a selector argument crashes Final Cut)
    so the share model follows, which the sheet's size estimate shows (2.07 -> 1.48 GB on ProRes 422 LT, 2026-09-25)."""
    app = m('NSApplication', 'sharedApplication', handle=True, cls=True)
    ws = m(app['handle'], 'windows', handle=True)['handle']
    panel = next(w['handle'] for i in range(int(m(ws, 'count')['result']))
                 for w in [m(ws, 'objectAtIndex:', [{'type': 'int', 'value': i}], handle=True)]
                 if w['class'] == 'LKPanel' and m(w['handle'], 'title').get('result') == 'Export File')
    seg = views(m(panel, 'contentView', handle=True)['handle'], 'LKSegmentedControl', [])[0]
    settings = m(m(seg, 'target', handle=True)['handle'], 'settingsView', handle=True)['handle']
    pops = [(p, str(m(p, 'itemTitles')['result'])) for p in views(settings, 'LKPopUpButton', [])]
    for pick, accept in WANT:
        pop = next((p for p, items in pops if pick in items), None)
        if pop is None:
            raise Fail(f'no "{pick}" choice in the Export File settings')
        if m(pop, 'titleOfSelectedItem')['result'] in accept:
            continue
        idx = int(m(pop, 'indexOfItemWithTitle:', [{'type': 'string', 'value': pick}])['result'])
        m(m(pop, 'menu', handle=True)['handle'], 'performActionForItemAtIndex:', [{'type': 'int', 'value': idx}])
        time.sleep(1)
        got = m(pop, 'titleOfSelectedItem')['result']
        if got not in accept:
            raise Fail(f'the Export File setting reads "{got}" after choosing "{pick}"')
        print(f'  · export setting set: {pick}')


def save_panel():
    """The in-process NSSavePanel behind the share sheet's (out-of-process) save panel, as a bridge handle."""
    ws = m('NSApplication', 'sharedApplication', handle=True, cls=True)
    arr = m(ws['handle'], 'windows', handle=True)
    for i in range(int(m(arr['handle'], 'count')['result'])):
        w = m(arr['handle'], 'objectAtIndex:', [{'type': 'int', 'value': i}], handle=True)
        if w.get('class') == 'NSSavePanel' and m(w['handle'], 'isVisible').get('result'):
            return w['handle']
    return None


def timeline(fcpxml):
    x = Path(fcpxml).read_text(encoding="utf-8")
    name = re.search(r'<project name="([^"]+)"', x).group(1)
    seq = re.search(r'<sequence format="([^"]+)" duration="([^"]+)"', x)
    fmt = re.search(r'<format id="%s" frameDuration="([^"]+)"' % re.escape(seq.group(1)), x)
    ts = lambda s: Fraction(s.rstrip('s'))
    return name, round(ts(seq.group(2)) / ts(fmt.group(1)))


def share(job, project=None, timeout=3600, out=None):
    job = Path(job)
    xmls = sorted(glob.glob(str(job / 'finalcut' / '*.fcpxml')), key=os.path.getmtime)
    if not xmls:
        raise Fail(f'no {job}/finalcut/*.fcpxml: build and import the timeline first (replay.py, import.py)')
    built = next((x for x in xmls[::-1] if timeline(x)[0] == project), None) if project else xmls[-1]
    if not built:
        raise Fail(f'no FCPXML in {job}/finalcut/ builds project "{project}"')
    project, frames = timeline(built)
    dest = Path(out) if out else job / 'finalcut' / 'renders' / f'{project}-master.mov'
    if dest.exists():
        raise Fail(f'{dest} exists: move it aside (Final Cut would be asked to replace it)')
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not ensure():              # the lane's copy running, by its path, its bridge proven (doctor.py, lab-notes § 21)
        raise Fail('Final Cut is not ready for the export (the line above says why)')
    dismiss_notification_sheet()
    if any(d.get('title') == 'Export File' for d in dialogs()):
        raise Fail('an Export File sheet is already open in Final Cut: close it first')
    try:
        open_project(project)
    except BridgeError as ex:
        raise Fail(str(ex))
    try:
        call('share.export', {'destination': 'Export File (default)…'})
    except BridgeError:
        pass                      # it answers "Menu execute failed" and opens the sheet anyway (lab-notes)
    sheet = wait('the Export File sheet', lambda: next((d for d in dialogs() if d.get('title') == 'Export File'), None), 20)
    try:
        configure_sheet()
    except (BridgeError, Fail) as ex:
        call('dialog.click', {'button': 'Cancel'})
        raise Fail(f'could not set the export settings: {ex}')
    sheet = next(d for d in dialogs() if d.get('title') == 'Export File')
    labels = [l.get('text') for l in sheet.get('labels', [])]
    est = next((float(g.group(1)) * (1e9 if g.group(2) == 'GB' else 1e6) for l in labels
                for g in [re.match(r'([\d.]+) (GB|MB) est', l or '')] if g), None)   # the sheet's own size estimate
    if '.mov' not in labels:
        call('dialog.click', {'button': 'Cancel'})
        raise Fail(f'the Export File settings still do not write a .mov ({labels})')
    call('dialog.click', {'button': 'Next…'})
    panel = wait('the save panel', save_panel, 20)
    url = m('NSURL', 'fileURLWithPath:', [{'type': 'string', 'value': str(dest.resolve())}], handle=True, cls=True)
    urls = m('NSArray', 'arrayWithObject:', [{'type': 'handle', 'value': url['handle']}], handle=True, cls=True)
    m(panel, 'completeWithReturnCode:url:urls:', [{'type': 'int', 'value': 1}, {'type': 'handle', 'value': url['handle']},
                                                   {'type': 'handle', 'value': urls['handle']}])
    t0 = time.time()
    try:                          # Final Cut's own progress bar, in its Background Tasks window (⌘9)
        call('menu.execute', {'menuPath': ['Window', 'Background Tasks']})
    except BridgeError:
        pass
    wait(f'{dest.name} to appear', dest.exists, 60)
    last, still, shown = -1, 0, 0
    while still < 3:              # done = the size holds and no process has it open
        if time.time() - t0 > timeout:
            raise Fail(f'{dest.name} still growing after {timeout:.0f} s')
        time.sleep(3)
        size = dest.stat().st_size
        busy = subprocess.run(['lsof', '-t', str(dest)], capture_output=True, text=True).stdout.strip()
        still = still + 1 if size == last and not busy else 0
        last = size
        el = time.time() - t0
        if el - shown >= 5 and still == 0:
            shown = el
            if est:
                pct = min(99, int(100 * size / est))
                eta = f', about {int(el * (est - size) / size)} s left' if 0 < size < est else ''
                print(f'  … rendering {pct}% ({size / 1e9:.2f} of about {est / 1e9:.2f} GB), {int(el)} s{eta}', flush=True)
            else:
                print(f'  … rendering, {size / 1e9:.2f} GB written, {int(el)} s', flush=True)
    for _ in range(3):
        dismiss_notification_sheet()
        time.sleep(1)
    call('object.release', {'all': True})
    p = subprocess.run(['ffprobe', '-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries',
                        'stream=codec_name,nb_read_packets', '-of', 'csv=p=0', str(dest)], capture_output=True, text=True).stdout
    # the first row only: ffprobe 9 prints a timecoded file's video row twice, and a Final Cut master carries timecode
    p = next((l for l in p.splitlines() if l.strip()), '').strip()
    codec, n = (p.split(',') + ['', ''])[:2]
    print(f'✓ Final Cut rendered {dest} in {time.time() - t0:.0f} s: {codec}, {n} frames (timeline {frames})')
    if codec != 'prores' or int(n or 0) != frames:
        raise Fail(f'the master is {codec} with {n} frames; the timeline has {frames}')
    return dest, frames


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--project')
    ap.add_argument('--timeout', type=float, default=3600)
    ap.add_argument('--out', help='the master\'s path (default finalcut/renders/<project>-master.mov)')
    a = ap.parse_args()
    try:
        share(a.job, a.project, a.timeout, a.out)
    except Fail as ex:
        print(f'✗ {ex}', file=sys.stderr)
        return 1 if 'the master is' in str(ex) else 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
