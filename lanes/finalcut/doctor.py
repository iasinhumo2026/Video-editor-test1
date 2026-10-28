#!/usr/bin/env python3
"""doctor.py: which Final Cut the lane drives, and the one-shot repair when another copy is in its way.

  uv run lanes/finalcut/doctor.py                    report: the App Store app, the lane's copy, anything in the way
  uv run lanes/finalcut/doctor.py --repair           quit a Final Cut that is not the lane's copy, move stale patched
                                                     copies to the Trash, launch the copy BY PATH and prove the bridge
                                                     (sk.py system.version)
  uv run lanes/finalcut/doctor.py --repair --no-launch   the copies on disk only (setup-finalcut.sh)
  uv run lanes/finalcut/doctor.py --patch            quit Final Cut, open SpliceKit, print the one click to relay
  from doctor import ensure                          the lane scripts: the copy running and its bridge proven

Final Cut runs ONE instance per bundle id (LSMultipleInstancesProhibited) and the patched copy keeps its App Store
app's bundle id: whichever Final Cut of that id is running owns every later launch of ANY copy of it, by path, name or
bundle id, and a bundle-id lookup (open -b, computer use, "quit and reopen Final Cut") resolves to the App Store app,
which has no bridge (lab-notes § 21). The two editions are two ids (BUNDLE_IDS: the one-time purchase, Apple Creator
Studio), so the other edition's App Store app blocks nothing and is left alone; any running patched copy is in the way
(its bridge holds the port). So exactly one patched copy is the lane's: the one in ~/Applications/SpliceKit/ made from
the App Store Final Cut the lane drives, at its bundle id, version and build. Two App Store Final Cuts: the lane drives
the newer, since a library a newer Final Cut has opened cannot go back; on a tie the one already patched, then the
plain "Final Cut Pro.app". Every other copy is stale. A copy older than its App Store app (Final Cut updated) still
runs, with a ⚠, until the re-patch. A Final Cut older than 12.0 is refused: the lane writes FCPXML 1.14, which 11.x
cannot import.

Exit: 0 ok · 3 (report) --repair fixes what it printed · 4 SpliceKit's one click is needed (--repair and --patch
opened SpliceKit and printed the ACTION line; the report names the command) · 1 failed, or no App Store Final Cut at
12.0 or later. An Intel Mac gets a ⚠ (SpliceKit 3.3.9's snapping crash there), never a refusal, and Smooth Scroll
saved off in the copy (its playback crash there, lab-notes § 22): the report says 3 until --repair has done it.
"""
import argparse, os, plistlib, shutil, subprocess, sys, time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sk  # noqa: E402

BUNDLE_IDS = ('com.apple.FinalCut', 'com.apple.FinalCutApp')          # the one-time purchase, Apple Creator Studio
MIN_MAJOR = 12                                                         # FCPXML 1.14 (lab-notes § 2) imports from 12.0
STORE_DIR = os.environ.get('VE_FCP_STORE_DIR', '/Applications')        # the two overrides are the regression test's
COPY_DIR = os.environ.get('VE_FCP_COPY_DIR', os.path.expanduser('~/Applications/SpliceKit'))
SPLICEKIT = '/Applications/SpliceKit.app'
EXE = '/Contents/MacOS/Final Cut Pro'                                  # both editions' executable
REPAIR = 'uv run lanes/finalcut/doctor.py --repair'
SETUP = './setup.sh --lane finalcut'


class App:
    def __init__(self, path, info):
        self.path, self.name, self.bid = path, os.path.basename(path), info.get('CFBundleIdentifier')
        self.version, self.build = str(info.get('CFBundleShortVersionString', '?')), str(info.get('CFBundleVersion', '?'))

    def key(self):
        num = lambda s: tuple(int(x) if x.isdigit() else -1 for x in s.split('.'))
        return num(self.version), num(self.build)

    def __str__(self):
        return f'{self.name} {self.version} ({self.build})'


def info(path):
    try:
        with open(os.path.join(path, 'Contents', 'Info.plist'), 'rb') as f:
            return plistlib.load(f)
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None


def apps(folder, patched):
    """The Final Cuts directly in folder, by bundle id: a patched copy carries SpliceKit's framework, the App Store
    app does not."""
    out = []
    for n in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        p = os.path.join(folder, n)
        i = info(p) if n.endswith('.app') else None
        if i and i.get('CFBundleIdentifier') in BUNDLE_IDS and is_patched(p) == patched:
            out.append(App(p, i))
    return out


def is_patched(path):
    return os.path.isdir(os.path.join(path, 'Contents', 'Frameworks', 'SpliceKit.framework'))


def resolve():
    """(stores, store, why, copy, current, stale): every App Store Final Cut, the one the lane drives and why, the
    lane's patched copy (None: never patched), whether it is at that app's version and build, every other copy. A
    newest App Store Final Cut older than 12.0 is refused: store None, and `why` says so."""
    stores, copies = apps(STORE_DIR, False), apps(COPY_DIR, True)
    if not stores:
        return stores, None, '', None, False, copies
    same = lambda c, s: c.bid == s.bid and c.name == s.name and c.key() == s.key()
    top = max(s.key() for s in stores)
    if top[0][0] < MIN_MAJOR:
        old = max(stores, key=lambda s: s.key())
        return stores, None, (f'{old} is older than {MIN_MAJOR}.0: the lane writes FCPXML 1.14, which Final Cut imports '
                              f'from {MIN_MAJOR}.0 on. Update Final Cut Pro to {MIN_MAJOR}.0 or later in the App Store '
                              f'(a Mac that cannot run it cannot use this lane), then run {SETUP}'), None, False, copies
    tied = [s for s in stores if s.key() == top]
    patched = [s for s in tied if any(same(c, s) for c in copies)]
    plain = [s for s in tied if s.name == 'Final Cut Pro.app']
    store = (patched or plain or tied)[0]
    why = ('the newer' if len(tied) == 1 else 'the same version, already patched' if patched
           else 'the same version, the plain name')
    copy = next((c for c in copies if same(c, store)), None)
    current = copy is not None
    if not copy and copies:      # Final Cut updated past its copy: the old copy still runs until the re-patch
        copy = max(copies, key=lambda c: (c.bid == store.bid, c.name == store.name, c.key()))
    return stores, store, why, copy, current, [c for c in copies if c is not copy]


def running():
    """[(pid, app path)] of every Final Cut running, either edition's App Store app or any copy."""
    out = []
    for line in subprocess.run(['ps', '-axo', 'pid=,comm='], capture_output=True, text=True).stdout.splitlines():
        pid, _, exe = line.strip().partition(' ')
        if exe.endswith('.app' + EXE) \
                and (info(exe[:-len(EXE)]) or {}).get('CFBundleIdentifier', BUNDLE_IDS[0]) in BUNDLE_IDS:
            out.append((int(pid), exe[:-len(EXE)]))
    return out


def in_way(path, bid):
    """Whether a running Final Cut keeps the lane's copy (bundle id `bid`) from starting or answering: one of the same
    id swallows every launch of the copy, and any patched copy holds the bridge's port. The other edition's App Store
    app blocks neither, so it is left alone (an unreadable bundle counts as in the way)."""
    i = info(path)
    return i is None or i.get('CFBundleIdentifier') == bid or is_patched(path)


INTEL = ('⚠ Intel Mac: SpliceKit 3.3.9 crashes Final Cut when the timeline is skimmed with snapping on (its haptic snap '
         'code; the fix, SpliceKit PR #92, is not in a release yet). Tell the user to keep snapping OFF in the lane\'s '
         'Final Cut (press N, or the snapping button at the top right of the timeline). Its Smooth Scroll crashes '
         'Final Cut the moment the timeline plays (SpliceKit issue #84, no fix yet), so --repair keeps it off in the '
         'copy; Splices > Smooth Scroll in its menu bar turns it back on, and the crash with it.')
SMOOTH_SCROLL = ('SpliceKitTimelinePerformanceMode', 'SpliceKitTimelinePlayheadOverlay')   # the switch, its overlay


def pref(bid, key, off=False):
    """One of the copy's defaults ('' when unset), or, with off, write it NO. The copy runs unsandboxed on
    ~/Library/Preferences/<bundle id>.plist (lab-notes § 7); `defaults` goes through cfprefsd, safe while it runs."""
    cmd = ['defaults', 'write', bid, key, '-bool', 'NO'] if off else ['defaults', 'read', bid, key]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


def smooth_scroll_on(bid):
    """Whether SpliceKit's Smooth Scroll installs in the copy: an unset switch is ON (SpliceKit's default)."""
    return any(pref(bid, k) != '0' for k in SMOOTH_SCROLL)


def smooth_scroll_off(bid, running):
    """Intel only (lab-notes § 22): Smooth Scroll's playhead overlay crashes Final Cut on every playback there. SpliceKit
    reads the switch at launch, so a running copy keeps it until its next one (never restarted for it)."""
    if smooth_scroll_on(bid):
        for k in SMOOTH_SCROLL:
            pref(bid, k, off=True)
        print('· turned SpliceKit\'s Smooth Scroll off in the lane\'s copy (on Intel it crashes Final Cut when the '
              'timeline plays)' + (': from its next launch; Splices > Smooth Scroll turns it off now' if running
                                    else ''), flush=True)


def intel():
    """An Intel Mac (hw.optional.arm64 is 1 on Apple silicon, under Rosetta too, and absent or 0 on Intel)."""
    if sys.platform != 'darwin':
        return False
    try:
        r = subprocess.run([shutil.which('sysctl') or '/usr/sbin/sysctl', '-n', 'hw.optional.arm64'],
                           capture_output=True, text=True)
    except OSError:
        return False
    return r.stdout.strip() != '1'


def bridge_pid():
    r = subprocess.run(['lsof', '-nP', f'-iTCP:{sk.PORT}', '-sTCP:LISTEN', '-Fp'], capture_output=True, text=True).stdout
    return next((int(l[1:]) for l in r.splitlines() if l.startswith('p')), None)


def bridge():
    try:
        return sk.call('system.version', timeout=5)
    except (OSError, ValueError, sk.BridgeError):
        return None


def quit_app(pid, timeout=60):
    """Quit ONE Final Cut by its pid, as its own Quit does (NSRunningApplication terminate: nothing addressed by bundle
    id, so it cannot reach the other copy). Never a force-kill: one that will not quit is reported."""
    subprocess.run(['osascript', '-l', 'JavaScript', '-e', 'ObjC.import("AppKit"); '
                    f'$.NSRunningApplication.runningApplicationWithProcessIdentifier({int(pid)}).terminate'],
                   capture_output=True)
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(1)
    return False


def trash(path):
    """To the Trash, never deleted: restorable, and SpliceKit can always make the copy again. Returns where it went."""
    if os.path.exists('/usr/bin/trash'):
        r = subprocess.run(['/usr/bin/trash', '-v', path], capture_output=True, text=True)
        if r.returncode == 0:
            return r.stdout.strip().rpartition(' to ')[2].strip('"') or '~/.Trash'
    dest = os.path.join(os.path.expanduser('~/.Trash'), f'{os.path.basename(path)[:-4]} {time.strftime("%Y%m%d-%H%M%S")}.app')
    shutil.move(path, dest)
    return dest


def launch(path, front=False):
    subprocess.run(['open'] + ([] if front else ['-g']) + [path], check=True)   # by PATH; Final Cut is never fronted


def wait_bridge(timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = bridge()
        if v:
            return v
        time.sleep(2)
    return None


def same_app(a, b):
    return os.path.realpath(a) == os.path.realpath(b)


def who(path, stores, stale):
    if any(same_app(path, s.path) for s in stores):
        return f'the App Store Final Cut ({os.path.basename(path)})'
    if path in [c.path for c in stale]:
        return f'a stale patched copy ({path})'
    return f'a Final Cut outside the lane ({path})'


def quit_all(pids, stores, stale):
    for pid, path in pids:
        print(f'· quitting {who(path, stores, stale)}, pid {pid}', flush=True)
        if not quit_app(pid):
            print(f'✗ Final Cut (pid {pid}) did not quit within 60 s: a render or a dialog is holding it. Ask the user '
                  'to finish or cancel it and quit Final Cut, then run this again.', file=sys.stderr)
            return False
    return True


def patch(stores=None, store=None, rerun=SETUP):
    """The user's one click: SpliceKit makes the patched copy from the App Store app, with Final Cut quit."""
    if store is None:
        stores, store, why, *_ = resolve()
        if not store:
            print('✗ ' + (why or f'no App Store Final Cut in {STORE_DIR}'), file=sys.stderr)
            return 1
    if not quit_all([(pid, p) for pid, p in running() if in_way(p, store.bid)], stores, []):
        return 1
    if not os.path.isdir(SPLICEKIT):
        print(f'✗ SpliceKit is not installed ({SPLICEKIT}): run {SETUP}', file=sys.stderr)
        return 1
    launch(SPLICEKIT, front=True)
    pick = (f' If it asks which Final Cut, choose {store.name[:-4]}, not '
            + ' or '.join(s.name[:-4] for s in stores if s is not store) + '.') if len(stores) > 1 else ''
    print(f'[splicekit] {store} needs its patched copy made by SpliceKit. Final Cut is quit and SpliceKit is open.')
    print('ACTION FOR CLAUDE: tell the user, in one short message: "Click Continue in the SpliceKit window.' + pick)
    print('It makes a separate copy of Final Cut that Claude can drive (your App Store Final Cut is not changed). Tell')
    print(f'me when it says it is done." Then run {rerun} yourself.')
    return 4


def repair(launch_copy=True, tidy=True):
    """Make the lane's copy the Final Cut that runs, by path, and prove its bridge. Returns (exit code, copy path)."""
    stores, store, why, copy, current, stale = resolve()
    if not store:
        print('✗ ' + (why or f'no App Store Final Cut in {STORE_DIR}: install Final Cut Pro, open it once, then run '
                             f'{SETUP}'), file=sys.stderr)
        return 1, None
    if len(stores) > 1:
        print(f'[fcp] {len(stores)} App Store Final Cuts: the lane drives {store} ({why}); '
              + ', '.join(str(s) for s in stores if s is not store) + ' left alone', flush=True)
    if intel():
        print(INTEL, flush=True)
    if not copy or (not launch_copy and not current):     # setup asks for the copy at the App Store app's version
        return patch(stores, store, rerun=REPAIR if launch_copy else SETUP), None   # the re-run after it tidies
    up = [(pid, p) for pid, p in running() if same_app(p, copy.path)]
    wrong = [(pid, p) for pid, p in running() if (pid, p) not in up and in_way(p, copy.bid)]
    if not launch_copy:
        wrong = [(pid, p) for pid, p in wrong if p in [c.path for c in stale]]   # only what stands in the Trash's way
    if not quit_all(wrong, stores, stale):
        return 1, None
    for c in stale if tidy else []:
        print(f'· moved the stale patched copy {c.path} ({c.version}) to the Trash: {trash(c.path)}', flush=True)
    if intel():
        smooth_scroll_off(copy.bid, running=bool(up))     # before the launch below: SpliceKit reads it at launch
    if not current:
        print(f'⚠ Final Cut was updated ({store.version}) but its patched copy is {copy.version}: it still runs; '
              f'{SETUP} re-patches it (one click in SpliceKit)', flush=True)
    if not launch_copy:
        print(f'✓ the lane\'s patched copy: {copy.path} ({copy.version}), the only one', flush=True)
        return 0, copy.path
    for attempt in (0, 1):
        if not up:
            launch(copy.path)
            print(f'· launched {copy.path} by its path', flush=True)
        v = wait_bridge()
        pid = bridge_pid()
        up = [(p, a) for p, a in running() if same_app(a, copy.path)]
        if v and up and pid == up[0][0]:
            print(f'✓ bridge up: Final Cut {v.get("fcp_version")}, SpliceKit {v.get("splicekit_version")}, pid {pid} '
                  f'= {copy.name} (the lane\'s copy)', flush=True)
            return 0, copy.path
        if attempt == 0 and up:   # the copy runs but its bridge never answered: one restart, by path
            print(f'· {copy.name} is running but its bridge does not answer: restarting it', flush=True)
            if not quit_all(up, stores, stale):
                return 1, None
            up = []
    print(f'✗ no bridge from {copy.path} after a launch by path: read ~/Library/Logs/SpliceKit/splicekit.log; if '
          f'SpliceKit itself was updated, {SETUP} re-patches the copy', file=sys.stderr)
    return 1, None


def ensure():
    """For the lane scripts, before they attach: the lane's copy running, by path, its bridge proven. A Final Cut that
    is not the lane's copy is quit first. Returns the copy's path, or None (the reason is printed)."""
    if bridge():
        pid, copy = bridge_pid(), resolve()[3]
        if copy and any(p == pid and same_app(a, copy.path) for p, a in running()):
            if intel():
                smooth_scroll_off(copy.bid, running=True)
            return copy.path
    rc, path = repair(tidy=False)
    return path if rc == 0 else None


def report():
    stores, store, why, copy, current, stale = resolve()
    if not store:
        print('✗ ' + (why or f'no App Store Final Cut in {STORE_DIR}'))
        return 1
    print(f'[fcp] App Store Final Cut: {store}')
    for s in stores:
        if s is not store:
            print(f'[fcp] also installed: {s}: left alone, the lane drives {store.name} ({why})')
    if copy:
        print(f'[fcp] the lane\'s patched copy: {copy.path}, {copy.version} ({copy.build})')
    rc = 0
    if intel():
        print(INTEL)
        if copy and smooth_scroll_on(copy.bid):
            print('⚠ SpliceKit\'s Smooth Scroll is on in the lane\'s copy: on Intel it crashes Final Cut when the '
                  'timeline plays; --repair turns it off')
            rc = 3
    for c in stale:
        print(f'⚠ stale patched copy: {c.path}, {c.version} ({c.build}): --repair moves it to the Trash')
        rc = 3
    up = False
    for pid, path in running():
        if copy and same_app(path, copy.path):
            up = True
            v = bridge()
            if v and bridge_pid() == pid:
                print(f'[fcp] running, pid {pid}: bridge up (Final Cut {v.get("fcp_version")}, SpliceKit '
                      f'{v.get("splicekit_version")})')
            else:
                print(f'⚠ the lane\'s copy is running (pid {pid}) but its bridge does not answer: --repair restarts it')
                rc = 3
        elif in_way(path, (copy or store).bid):
            print(f'⚠ {who(path, stores, stale)} is running, pid {pid}: it has no bridge, and while it runs the lane\'s '
                  'copy cannot start or answer: --repair quits it')
            rc = 3
        else:
            print(f'[fcp] {who(path, stores, stale)} is running, pid {pid}: the other edition, it does not block the '
                  'lane\'s copy and is left alone')
    if not copy or not current:
        print(f'⚠ Final Cut {store.version} has no patched copy at its version ('
              + (f'the copy is {copy.version}' if copy else 'never patched') + ')')
        print(f'⚠ Final Cut needs SpliceKit\'s one click: run {SETUP}')
        return 4
    if rc:
        print(f'⚠ the Final Cut lane needs a repair: run {REPAIR} (it fixes every line above)')
    else:
        print(f'✓ Final Cut lane: {copy.name} {copy.version}, its only patched copy'
              + ('' if up else ' (not running: --repair starts it by its path)'))
    return rc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--repair', action='store_true')
    g.add_argument('--patch', action='store_true')
    ap.add_argument('--no-launch', action='store_true', help='with --repair: the copies on disk only (setup)')
    a = ap.parse_args()
    if a.patch:
        return patch()
    if a.repair:
        return repair(launch_copy=not a.no_launch)[0]
    return report()


if __name__ == '__main__':
    sys.exit(main())
