"""premiere_win.py: the Windows backend of premiere-pid.sh and premiere-dismiss.sh (both delegate here on Windows).

  python lanes/premiere/premiere_win.py pid [--name]                  # the app's pid ("Adobe Premiere Pro" with --name)
  python lanes/premiere/premiere_win.py dismiss [--check] [--key 36|53|2] [--tries N]

Same contract as the macOS scripts (their headers are the spec). Exit: pid 0 / 1 not running; dismiss 0 = no modal
(or dismissed), 1 = Premiere not running, 2 = a modal is still up.

Windows mechanics (2026-09-27): the app binary is `Adobe Premiere Pro.exe` (no year in the name, unlike the Mac
bundle; `tasklist` finds it exactly). A native modal DISABLES the main window (Win32 modality), so DETECT = the main
window is disabled. The modal is the enabled window OWNED by it (its GW_OWNER chain reaches the main window; a dialog
opened from a dialog is owned by the first): Premiere's save dialog is a `#32770` owned by the main window. Never just
"the biggest other window": the MCP bridge's CEP panel keeps an ownerless CEF host window (320x400 at 0,0) that was
bigger than the save dialog, so the first detector named it and a dismiss would have posted Return into the panel.
DISMISS = WM_KEYDOWN/WM_KEYUP of Return (Mac keycode 36) or Escape (53) posted straight to the modal, which lands on its
default / cancel button without fronting anything.
PROVEN on a real modal (the Windows re-test, 2026-09-27, Premiere 26.5.1): a QE razor dirtied a scratch project, the
bridge's app.quit() raised "Save changes to '<name>.prproj' before closing?" (Save / Don't Save / Cancel); `--check`
named it, `--key 53` (Cancel) cleared it with Premiere still up, and a bare dismiss (Return = Save) saved and quit.
`--key 2` (the D key, macOS keycode 2) answers Don't Save: proven 2026-10-13 on the same dialog ("Save project: Save
changes to '<name>.prproj' before closing?", Save / Don't Save / Cancel) raised by closeDocument(0, 1) on a QE-dirtied
scratch project: the project closed and its file on disk kept the clips it had before the razor. N did nothing. The
dialog's buttons are Adobe's own (DroverLord) controls, not Win32 buttons, so a key is the only way in.
An ExtendScript edit (a marker) does NOT dirty a project: that quit raised no dialog and dropped the marker.
"""
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32 if sys.platform == "win32" else None   # importable anywhere: modal() is tested on every OS
EXE = "Adobe Premiere Pro.exe"
KEYS = {36: 0x0D, 53: 0x1B, 2: 0x44}  # macOS virtual keycodes the .sh takes -> VK_RETURN (Save), VK_ESCAPE (Cancel), D (Don't Save)
KEY_NAMES = {0x0D: "Return", 0x1B: "Escape", 0x44: "D (Don't Save)"}


def pid():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {EXE}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if len(cols) > 1 and cols[0].strip('"').lower() == EXE.lower():
            return int(cols[1])
    return None


def top_windows(p):
    out = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        wp = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wp))
        if wp.value == p and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            n = user32.GetWindowTextLengthW(hwnd)
            b = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, b, n + 1)
            c = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, c, 256)
            out.append({"hwnd": hwnd, "title": b.value, "class": c.value, "enabled": bool(user32.IsWindowEnabled(hwnd)),
                        "owner": user32.GetWindow(hwnd, 4) or 0,          # GW_OWNER
                        "iconic": bool(user32.IsIconic(hwnd)),
                        "area": (r.right - r.left) * (r.bottom - r.top)})
        return True
    user32.EnumWindows(cb, 0)
    return out


MAIN_CLASS = "Premiere Pro"          # the main frame's window class (26.5.1, read live 2026-09-27)


def main_window(ws):
    """Premiere's main frame by its own identity: its class, else its "Adobe Premiere" title, minimized or not. Never
    "the biggest window": minimized, the frame is a 160x28 rect, and the MCP panel's ownerless 320x400 CEF host was then
    taken for it (the Mac review of the Windows port, 2026-09-27). The biggest is the last resort only."""
    for pick in (lambda w: w["class"] == MAIN_CLASS, lambda w: w["title"].startswith("Adobe Premiere")):
        hits = [w for w in ws if pick(w) and not w["owner"]]
        if hits:
            return max(hits, key=lambda w: w["area"])
    return max(ws, key=lambda w: w["area"])


def modal(p, ws=None):
    """The modal window, or None. A modal disables the main window and is owned by it (header). A disabled main window
    with no enabled window it owns in sight (minimized, the dialog hides with it) comes back as the MAIN window marked
    "suspected": a modal is up, and there is no dialog to send a key to."""
    ws = top_windows(p) if ws is None else ws
    if not ws:
        return None
    main = main_window(ws)
    if main["enabled"]:
        return None
    by = {w["hwnd"]: w for w in ws}

    def owned_by_main(w):
        seen, o = set(), w["owner"]
        while o and o not in seen:
            if o == main["hwnd"]:
                return True
            seen.add(o)
            o = by[o]["owner"] if o in by else 0
        return False
    owned = [w for w in ws if w["hwnd"] != main["hwnd"] and w["enabled"] and owned_by_main(w)]
    if owned:
        return max(owned, key=lambda w: (w["class"] == "#32770", w["area"]))
    return dict(main, suspected=True)                  # disabled, and no dialog of its own in sight


def name(m):
    if m.get("suspected"):
        return ("none found: Premiere's main window is disabled but no dialog it owns is visible"
                + (" (Premiere is minimized; restore it to see the dialog)" if m.get("iconic") else ""))
    return f"'{m['title']}'" if m["title"] else f"untitled {m['class']} window {m['hwnd']}"


def main():
    a = sys.argv[1:]
    if not a or a[0] not in ("pid", "dismiss"):
        print(__doc__)
        return 2
    p = pid()
    if a[0] == "pid":
        if p is None:
            print("[premiere-pid] Premiere is not running", file=sys.stderr)
            return 1
        print("Adobe Premiere Pro" if "--name" in a else p)
        return 0
    if p is None:
        print("[premiere-dismiss] Premiere is not running", file=sys.stderr)
        return 1
    key = int(a[a.index("--key") + 1]) if "--key" in a else 36
    tries = int(a[a.index("--tries") + 1]) if "--tries" in a else 8
    m = modal(p)
    if "--check" in a:
        if m:
            print(f"[premiere-dismiss] a modal is up: {name(m)}")
            return 2
        print("[premiere-dismiss] no modal")
        return 0
    vk = KEYS.get(key)
    if vk is None:
        print(f"[premiere-dismiss] --key {key}: only 36 (Return), 53 (Escape) and 2 (D, Don't Save) map on Windows", file=sys.stderr)
        return 1
    for i in range(tries):
        m = modal(p)
        if not m:
            print("[premiere-dismiss] no modal" if i == 0 else f"[premiere-dismiss] dismissed after {i} key(s)")
            return 0
        if m.get("suspected"):                                   # never a key into the main frame
            print(f"[premiere-dismiss] a modal is up, {name(m)}: no key sent", file=sys.stderr)
            return 2
        print(f"[premiere-dismiss] modal {name(m)}: posting {KEY_NAMES[vk]}")
        user32.PostMessageW(m["hwnd"], 0x0100, vk, 0)            # WM_KEYDOWN
        user32.PostMessageW(m["hwnd"], 0x0101, vk, 0xC0000001)   # WM_KEYUP
        time.sleep(1.0)
    return 2 if modal(p) else 0


if __name__ == "__main__":
    sys.exit(main())
