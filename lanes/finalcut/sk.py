#!/usr/bin/env python3
"""sk.py: the ONE client for SpliceKit's JSON-RPC bridge inside the patched Final Cut Pro (127.0.0.1:9876).

  uv run lanes/finalcut/sk.py <method> ['<json params>']      one call, result printed as JSON
  from sk import call                                          call('timeline.getDetailedState', {...})
  uv run lanes/finalcut/sk.py --dismiss                        close Final Cut's notification sheet if it is up

The bridge is what SpliceKit's MCP server wraps (`/Applications/SpliceKit.app/Contents/Resources/mcp/server.py`);
scripts in this lane talk to it directly so they run without an MCP client. Newline-delimited JSON-RPC 2.0 over TCP.
Exit: 0 ok · 1 the bridge answered with an error · 2 no bridge (the patched FCP is not running: doctor.py --repair).
"""
import json, socket, sys

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

HOST, PORT = '127.0.0.1', 9876


class BridgeError(RuntimeError):
    pass


def call(method, params=None, timeout=120):
    req = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}
    with socket.create_connection((HOST, PORT), timeout=timeout) as s:
        s.sendall((json.dumps(req) + '\n').encode())
        buf = b''
        while not buf.endswith(b'\n'):
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    resp = json.loads(buf.decode())
    if 'error' in resp:
        raise BridgeError(json.dumps(resp['error']))
    return resp.get('result')


def dismiss_notification_sheet():
    """Final Cut's "Stay Up To Date With Notifications" sheet (buttons Continue / Not Now) is MODAL and comes back
    every time FCP wants to post a notification (an export finishing), whatever its dismissal count: its own
    shouldShowWarmingSheetForLastDismissalDate:... answers YES whenever isNotificationTriggered (probed 2026-09-25).
    It ends only when the macOS notification permission for the patched copy is answered once. Until then every
    lane script clears it with "Not Now" before and after its work. Returns True when one was closed."""
    closed = False
    for d in (call('dialog.detect').get('dialogs') or []):
        if {b.get('title') for b in d.get('buttons', [])} == {'Not Now', 'Continue'}:
            call('dialog.click', {'button': 'Not Now'})
            closed = True
    return closed


def m(target, sel, args=(), handle=False, cls=False):
    """One ObjC call through the bridge. Never pass a SELECTOR-typed argument (sendAction:to:): it crashed Final Cut
    (2026-09-25, lab-notes § 18); pick a menu item with its menu's performActionForItemAtIndex: (an int) instead."""
    return call('system.callMethodWithArgs', {'target': target, 'selector': sel, 'args': list(args),
                                              'classMethod': cls, 'returnHandle': handle})


def load_libraries():
    """Final Cut reopens its libraries lazily after a launch: project.open cannot see a project until its library's
    event is loaded (clicking the library in the sidebar does it). This loads every open library's events, the same
    way: FFLibrary.events -> loadPrimaryObject -> loadProjectData (lab-notes § 19)."""
    libs = m('FFLibraryDocument', 'copyActiveLibraries', handle=True, cls=True)['handle']
    for i in range(int(m(libs, 'count')['result'])):
        lib = m(libs, 'objectAtIndex:', [{'type': 'int', 'value': i}], handle=True)['handle']
        evs = m(lib, 'events', handle=True)['handle']
        for j in range(int(m(evs, 'count')['result'])):
            ev = m(m(evs, 'objectAtIndex:', [{'type': 'int', 'value': j}], handle=True)['handle'], 'loadPrimaryObject', handle=True)
            if ev.get('handle') and not m(ev['handle'], 'isProjectDataLoaded').get('result'):
                m(ev['handle'], 'loadProjectData')
    call('object.release', {'all': True})


def open_project(name):
    """Open a project by its EXACT name (project.open matches a prefix, lab-notes § 17), loading libraries if needed."""
    for attempt in (0, 1):
        try:
            r = call('project.open', {'name': name}, timeout=30)
            if r.get('project') == name:
                return r
        except BridgeError:
            pass
        load_libraries()
    raise BridgeError(f'no project named exactly "{name}" in the libraries Final Cut has open')


if __name__ == '__main__':
    if sys.argv[1:] == ['--dismiss']:
        print('closed the notification sheet' if dismiss_notification_sheet() else 'no notification sheet up')
        sys.exit(0)
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    try:
        r = call(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {})
    except (ConnectionRefusedError, socket.timeout, OSError) as ex:
        print(f'✗ no SpliceKit bridge on {HOST}:{PORT} ({ex}): run uv run lanes/finalcut/doctor.py --repair (it quits '
              'a Final Cut that is not the lane\'s copy and launches the copy by its path)', file=sys.stderr)
        sys.exit(2)
    except BridgeError as ex:
        print(f'✗ {ex}', file=sys.stderr)
        sys.exit(1)
    print(json.dumps(r, indent=1))
