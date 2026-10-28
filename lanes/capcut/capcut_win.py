"""capcut_win.py: the Windows backend of capcut-bridge.py (imported only on win32).

WHY a different live lane on Windows. On macOS CapCut's QML UI is in the accessibility tree, ByteDance's own test ids
and all, and the bridge finds every control by name. On Windows (CapCut 9.5, Qt 6.2.2) UI Automation exposes ONLY the
top-level windows, each with its automation id (`HomeWindow`, …), and nothing inside them: no children in the control
or raw view, `ElementFromPoint` returns the window itself, and Qt 6 no longer implements MSAA (probed 2026-09-27). So the
Windows lane is built from what IS reachable, keeping the mac lane's locate → act → read-back loop:

  - WINDOWS by automation id / class (home, editor, dialogs): which screen is up, its rect;
  - ACTIONS through CapCut's own keyboard shortcuts (User Data/Config/Shortcut/Custom1.json: split Ctrl+K, delete Del,
    export Ctrl+M, trims Q/W, Home/End, frame steps, next/prev cut point Down/Up, undo/redo, marker M, zoom fit Shift+Z,
    play Space, back to the drafts page Ctrl+Alt+Q), sent with SendInput to the fronted window;
  - LOCATING and READING on screen with the Windows OCR engine (Windows.Media.Ocr through `winocr`): a draft's title on
    the home screen, the export dialog's Export button, the player's timecode readout. OCR is the read-back.

Every coordinate here is PHYSICAL screen px (the process is made per-monitor DPI aware), matching UIA's rects and
SendInput's absolute mapping on the virtual desktop.
"""
import ctypes
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)        # per-monitor: rects and clicks in physical px
except OSError:
    pass

user32 = ctypes.windll.user32
EXE = Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "Apps" / "CapCut.exe"
USER_DATA = Path(os.environ.get("LOCALAPPDATA", "")) / "CapCut" / "User Data"


# ---------------------------------------------------------------- draft root / version facts

def draft_root():
    """CapCut's own setting (Config/globalSetting currentCustomDraftPath), else the default under User Data."""
    gs = USER_DATA / "Config" / "globalSetting"
    try:
        for line in gs.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("currentCustomDraftPath="):
                p = line.split("=", 1)[1].strip().replace("\\\\", "\\")
                if p:
                    return Path(p)
    except OSError:
        pass
    return USER_DATA / "Projects" / "com.lveditor.draft"


def app_version():
    apps = USER_DATA.parent / "Apps"
    vers = sorted((p.name for p in apps.glob("*.*.*.*") if p.is_dir()), key=lambda v: [int(x) for x in v.split(".")])
    return vers[-1] if vers else ""


def os_version():
    v = sys.getwindowsversion()
    return f"{v.major}.{v.minor}.{v.build}"


# ---------------------------------------------------------------- process control

def pids():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CapCut.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return [int(row.split('","')[1]) for row in out.splitlines() if row.startswith('"CapCut.exe"')]


def app_pid():
    w = main_window()
    if w:
        return w["pid"]
    p = pids()
    return p[0] if p else None


def launch_app():
    if not EXE.exists():
        sys.exit(f"CapCut launcher not found: {EXE}")
    subprocess.Popen([str(EXE)], creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
    t0 = time.time()
    while time.time() - t0 < 60:
        if window("HomeWindow") or editor_window():
            time.sleep(2)
            return
        time.sleep(1)
    sys.exit("CapCut launched but no home or editor window appeared within 60 s")


def quit_app(timeout=40):
    """Graceful: WM_CLOSE to every CapCut top-level window (CapCut saves the draft and rewrites its registry on the
    way out), then wait for the process. A modal that blocks it is reported, never killed silently."""
    if not pids():
        return
    WM_CLOSE = 0x0010
    t0, sent = time.time(), 0
    while pids():
        if time.time() - t0 > timeout:
            left = [w["aid"] or w["cls"] for w in windows()]
            sys.exit(f"CapCut did not quit within {timeout}s (windows still up: {left}); close it and re-run")
        # closing the EDITOR only returns to the home page, a window of its own that then needs its own close
        # (2026-09-27: one round left HomeWindow up for the whole timeout), so every 2 s re-close what is still up
        if time.time() - t0 >= sent * 2:
            for w in windows():
                user32.PostMessageW(w["hwnd"], WM_CLOSE, 0, 0)
            sent += 1
        time.sleep(0.5)


# ---------------------------------------------------------------- windows (UIA top level only)

def windows(tries=4):
    """Every visible top-level window of a CapCut process: {hwnd, pid, name, aid, cls, rect(x,y,w,h)}. UIA's
    enumeration fails transiently while windows open or close (COMError 'An event was unable to invoke any of the
    subscribers'): retried."""
    for k in range(tries):
        try:
            return _windows()
        except Exception:
            if k == tries - 1:
                raise
            time.sleep(0.6)


def _windows():
    import uiautomation as auto
    mine = set(pids())
    out = []
    for w in auto.GetRootControl().GetChildren():
        try:
            if w.ProcessId not in mine:
                continue
            r = w.BoundingRectangle
            if r.width() <= 0 or r.height() <= 0:
                continue
            out.append({"hwnd": w.NativeWindowHandle, "pid": w.ProcessId, "name": w.Name, "aid": w.AutomationId,
                        "cls": w.ClassName, "rect": (r.left, r.top, r.width(), r.height())})
        except Exception:
            continue
    return out


def window(aid=None, cls_prefix=None):
    for w in windows():
        if (aid and w["aid"] == aid) or (cls_prefix and w["cls"].startswith(cls_prefix)):
            return w
    return None


def editor_window():
    """The editor: CapCut's biggest top-level window that is not the home page, a splash or an update prompt."""
    cands = [w for w in windows() if w["aid"] not in ("HomeWindow",) and not w["cls"].startswith(("Splash", "Update"))
             and w["name"] != "Version update" and w["rect"][2] > 900 and w["rect"][3] > 600]
    return max(cands, key=lambda w: w["rect"][2] * w["rect"][3]) if cands else None


def main_window():
    return editor_window() or window("HomeWindow")


def front(w, maximize=True):
    """Foreground a window reliably: Windows refuses SetForegroundWindow from a background process unless the
    thread input is attached (the foreground lock); an Alt tap releases it."""
    hwnd = w["hwnd"]
    if maximize:
        user32.ShowWindow(hwnd, 3)                              # SW_MAXIMIZE
    fg = user32.GetForegroundWindow()
    cur = ctypes.windll.kernel32.GetCurrentThreadId()
    tgt = user32.GetWindowThreadProcessId(hwnd, None)
    fgt = user32.GetWindowThreadProcessId(fg, None)
    user32.keybd_event(0x12, 0, 0, 0)                           # Alt down/up releases the foreground lock
    user32.keybd_event(0x12, 0, 2, 0)
    user32.AttachThreadInput(cur, fgt, True)
    user32.AttachThreadInput(cur, tgt, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(cur, fgt, False)
    user32.AttachThreadInput(cur, tgt, False)
    time.sleep(0.5)
    return user32.GetForegroundWindow() == hwnd


def rect_of(w):
    """Refresh a window's rect (it changes after a maximize)."""
    r = wintypes.RECT()
    user32.GetWindowRect(w["hwnd"], ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


# ---------------------------------------------------------------- input (SendInput)

class _MI(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _KI(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _IU(ctypes.Union):
    _fields_ = [("mi", _MI), ("ki", _KI)]


class _IN(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _IU)]


def _send(*events):
    arr = (_IN * len(events))(*events)
    user32.SendInput(len(events), arr, ctypes.sizeof(_IN))


def click_at(x, y, clicks=1):
    """A left click at physical screen px, through the virtual-desktop absolute mapping."""
    vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
    vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
    ax = int((x - vx) * 65535 / max(1, vw - 1))
    ay = int((y - vy) * 65535 / max(1, vh - 1))
    MOVE, ABS, VD, DOWN, UP = 0x0001, 0x8000, 0x4000, 0x0002, 0x0004
    _send(_IN(0, _IU(mi=_MI(ax, ay, 0, MOVE | ABS | VD, 0, None))))
    time.sleep(0.05)
    for _ in range(clicks):
        _send(_IN(0, _IU(mi=_MI(ax, ay, 0, DOWN | ABS | VD, 0, None))))
        time.sleep(0.03)
        _send(_IN(0, _IU(mi=_MI(ax, ay, 0, UP | ABS | VD, 0, None))))
        time.sleep(0.06)


VK = {"space": 0x20, "return": 0x0D, "enter": 0x0D, "escape": 0x1B, "esc": 0x1B, "delete": 0x2E, "del": 0x2E,
      "backspace": 0x08, "tab": 0x09, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28, "home": 0x24, "end": 0x23,
      "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "f": 0x46, "=": 0xBB, "-": 0xBD}
EXTENDED = {0x25, 0x26, 0x27, 0x28, 0x24, 0x23, 0x2E}


def _vk(k):
    k = k.lower()
    if k in VK:
        return VK[k]
    if len(k) == 1 and k.isalnum():
        return ord(k.upper())
    raise SystemExit(f"unknown key: {k}")


def _scan(vk):
    return user32.MapVirtualKeyW(vk, 0)       # the scan code too: Qt reads the physical key for shortcut matching


def send_key(combo):
    """'ctrl+k', 'shift+right', 'del', 'ctrl+alt+q' (mac 'cmd' maps to ctrl)."""
    parts = [p.strip() for p in combo.lower().replace("cmd", "ctrl").split("+")]
    mods, key = parts[:-1], parts[-1]
    down = [_vk(m) for m in mods] + [_vk(key)]
    # one event per SendInput, spaced: a modifier and its key in ONE batch reached CapCut as the bare key for some
    # shortcuts (Ctrl+K split did nothing while Del and Ctrl+Z worked), so the modifier is held before the key lands
    for v in down:
        _send(_IN(1, _IU(ki=_KI(v, _scan(v), (0x0001 if v in EXTENDED else 0), 0, None))))
        time.sleep(0.05)
    for v in reversed(down):
        _send(_IN(1, _IU(ki=_KI(v, _scan(v), (0x0001 if v in EXTENDED else 0) | 0x0002, 0, None))))
        time.sleep(0.03)
    time.sleep(0.03)


# ---------------------------------------------------------------- screen read-back (grab + OCR)

def grab(rect, out=None):
    from PIL import ImageGrab
    x, y, w, h = rect
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
    if out:
        img.save(out)
    return img


_RAPID = []


def ocr(rect, scale=1, det=True):
    """Text on screen inside rect: (words, lines). words = [(text, x, y, w, h)] and lines = [(text, (x, y, w, h))], in
    physical screen px. The engine is RapidOCR (PaddleOCR models on ONNX; pip, offline, no admin). Windows' own OCR
    (Windows.Media.Ocr) was tried first and never read CapCut's player timecode, the one read-back the live lane
    cannot do without (small monospace digits; empty however it was inverted, thresholded, padded or scaled), while
    RapidOCR read it at 0.97-0.98 confidence (2026-09-27). A line's words get boxes in proportion to their characters."""
    import numpy as np
    if not _RAPID:
        from rapidocr import RapidOCR
        # Det.limit_type "max": the default ("min", 736) UPSCALES every crop until its short side is 736 px, so the
        # player readout's 254x39 strip was detected at ~4800x736 (2 s a read; 0.1 s at native size, same text,
        # 2026-09-27). Errors only: 3.x logs a warning for every read with no text, and this lane polls
        _RAPID.append(RapidOCR(params={"Global.log_level": "error", "Det.limit_type": "max", "Det.limit_side_len": 2600}))
    img = grab(rect)
    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), 3)
    # no angle classifier: CapCut never draws rotated text, and it cost 2/3 of a read (5.9 s -> 2.2 s on the ruler).
    # det=False reads a crop already known to hold ONE line (the player readout) with the recogniser alone: texts and
    # scores, no boxes. Nothing read: txts is None. Boxes as plain floats, as 1.4.4 returned them (a numpy array in 3.x)
    res = _RAPID[0](np.asarray(img.convert("RGB")), use_cls=False, use_det=det)
    if not det:
        rows = [([[0, 0], [img.width, 0], [img.width, img.height], [0, img.height]], t, s)
                for t, s in zip(res.txts or (), res.scores or ())]
    else:
        rows = list(zip(res.boxes.tolist(), res.txts, res.scores)) if res.txts else []
    words, lines = [], []
    for box, text, conf in rows:
        xs = [p[0] for p in box]; ys = [p[1] for p in box]
        x0, y0 = rect[0] + min(xs) / scale, rect[1] + min(ys) / scale
        w, h = (max(xs) - min(xs)) / scale, (max(ys) - min(ys)) / scale
        lines.append((text, (x0, y0, w, h)))
        n, pos = max(1, len(text)), 0
        for wd in text.split(" "):
            if wd:
                words.append((wd, x0 + w * pos / n, y0, w * len(wd) / n, h))
            pos += len(wd) + 1
    words.sort(key=lambda t: (round(t[2] / 10), t[1]))
    return words, lines


def find_text(needle, rect, timeout=0, exact=False):
    """The first run of OCR words matching `needle` (case-insensitive; all its words in order on one line), as
    (text, x, y, w, h), or None. Polls until `timeout`."""
    want = needle.lower().split()
    t0 = time.time()
    while True:
        words, _ = ocr(rect)
        low = [w[0].lower().strip(".,:") for w in words]
        for i in range(len(words) - len(want) + 1):
            seg = low[i:i + len(want)]
            if all((a == b) if exact else (b in a) for a, b in zip(seg, want)):
                ws = words[i:i + len(want)]
                if len({round(w[2] / 8) for w in ws}) > 2:   # not on one line
                    continue
                x0 = min(w[1] for w in ws); y0 = min(w[2] for w in ws)
                x1 = max(w[1] + w[3] for w in ws); y1 = max(w[2] + w[4] for w in ws)
                return (" ".join(w[0] for w in ws), x0, y0, x1 - x0, y1 - y0)
        if time.time() - t0 >= timeout:
            return None
        time.sleep(0.7)


TC = re.compile(r"(\d{2}):(\d{2}):(\d{2})[:;.](\d{2})")


def read_timecodes(rect, det=True):
    """Every HH:MM:SS:FF on screen inside rect, left to right (the player shows current / total)."""
    words, lines = ocr(rect, det=det)
    found = []
    for text, box in sorted(lines, key=lambda l: l[1][0]):
        for m in TC.finditer(text.replace(" ", "")):
            found.append(m.group(0))
    return found


def dismiss_promos(tries=3):
    """CapCut opens promo/onboarding popups as separate SplashDialog windows over the home page (an 'Ultra is live'
    card on launch). Each has a close cross in its top-right corner: click it and read back that the window is gone.
    Returns how many were closed."""
    n = 0
    for _ in range(tries):
        sp = [w for w in windows() if w["cls"].startswith("Splash")]
        if not sp:
            break
        for w in sp:
            x, y, ww, hh = w["rect"]
            click_at(x + ww - 21, y + 21)
            time.sleep(0.8)
            n += 1
    left = [w for w in windows() if w["cls"].startswith("Splash")]
    if left:
        send_key("escape")
        time.sleep(0.5)
    return n


# ---------------------------------------------------------------- live commands

def home_or_launch():
    if not pids():
        launch_app()
    dismiss_promos()
    ed = editor_window()
    if ed:                                          # back to the drafts page: CapCut saves the open draft on the way
        front(ed)
        send_key(shortcut("returnDraftPage"))
        t0 = time.time()
        while editor_window() and time.time() - t0 < 20:
            time.sleep(0.5)
        dismiss_promos()
    home = window("HomeWindow")
    if home is None:
        sys.exit("CapCut's home window did not come up")
    front(home)
    home["rect"] = rect_of(home)
    return home


def open_draft(name, timeout=40):
    """Open a draft from the home page: its title read by OCR in the Projects grid, the tile double-clicked just above
    the title, and the editor window read back as open. Returns the editor window."""
    home = home_or_launch()
    hit = find_text(name, home["rect"], timeout=10, exact=True)
    if hit is None:
        send_key("escape")
        time.sleep(0.8)
        hit = find_text(name, home["rect"], timeout=8, exact=True)
    if hit is None:
        sys.exit(f"draft tile not found on the home page: {name} (scrolled out of view? or not in the registry)")
    _, x, y, w, h = hit
    click_at(x + 60, y - 80, clicks=2)             # the tile's thumbnail sits right above its title
    t0 = time.time()
    while time.time() - t0 < timeout:
        ed = editor_window()
        if ed:
            time.sleep(3)
            ed["rect"] = rect_of(ed)
            front(ed)
            return ed
        time.sleep(0.7)
    sys.exit("the editor did not open")


def editor():
    ed = editor_window()
    if ed is None:
        sys.exit("no draft is open in CapCut (use: open <draft>)")
    ed["rect"] = rect_of(ed)
    front(ed, maximize=False)
    if not _TIPS_CHECKED:
        _TIPS_CHECKED.append(dismiss_tips(ed))
    return ed


_TIPS_CHECKED = []   # once per command: every live action calls editor() several times


def dismiss_tips(ed, tries=3):
    """Toasts and onboarding tips CapCut draws INSIDE the editor window (not separate windows, so dismiss_promos never
    sees them), bottom-right, over the timeline: 'Keyboard shortcut conflicts with an existing one' (a cross, top right)
    the EditPilot tour ('Close' / 'Next') and 'Auto optimization is on' ('OK'). Left up they swallow the clicks select_at lands there (2026-09-27)."""
    x, y, w, h = ed["rect"]
    zone = (x + int(w * 0.72), y + int(h * 0.6), int(w * 0.28), int(h * 0.4))
    for _ in range(tries):
        words, lines = ocr(zone)
        hit = None
        for t, (lx, ly, lw, lh) in lines:
            k = t.replace(" ", "").lower()
            if k in ("close", "ok"):          # the EditPilot tour's Close; 'Auto optimization is on' … OK
                hit = (lx + lw / 2, ly + lh / 2)
            elif k.startswith("keyboardshortcutconflict"):
                # the cross sits at the toast's right edge, one header row above this line
                hit = (x + w - 45, ly - 58)
        if not hit:
            return
        click_at(*hit)
        time.sleep(0.8)


def parse_tc(tc, fps):
    h, m, s, f = (int(x) for x in TC.match(tc).groups())
    if ";" in tc and round(fps) in (30, 60) and abs(fps - round(fps)) > 0.01:
        # DROP-FRAME (a 29.97/59.94 draft reads 00:01:00;02): labels 0-1 (0-3 at 59.94) are skipped at every minute
        # but each tenth, so the label is not linear in time past the first minute
        nom, drop = round(fps), 2 * round(fps) // 30
        mins = 60 * h + m
        frames = (3600 * h + 60 * m + s) * nom + f - drop * (mins - mins // 10)
        return frames / fps
    return h * 3600 + m * 60 + s + f / fps


def playhead(ed=None):
    """(current, total) timecodes read off the player by OCR: the read-back every live action is checked against."""
    ed = ed or editor()
    x, y, w, h = ed["rect"]
    c = _layout(ed).get("tc")
    if c:
        tcs = read_timecodes(tuple(c))   # det=False (recogniser only) garbled the ' / ' between the two readouts
        if len(tcs) >= 2:
            return tcs[0], tcs[1]
    # the first read (or the panel moved): search the player band, then the window, and remember the readout's box
    for rect in ((x, y + int(h * 0.35), int(w * 0.9), int(h * 0.35)), ed["rect"]):
        words, lines = ocr(rect)
        hits = [(t, b) for t, b in sorted(lines, key=lambda l: l[1][0]) if TC.search(t.replace(" ", ""))]
        tcs = [m.group(0) for t, _ in hits for m in TC.finditer(t.replace(" ", ""))]
        if len(tcs) >= 2:
            bx = [b for _, b in hits]
            x0, y0 = min(b[0] for b in bx), min(b[1] for b in bx)
            x1, y1 = max(b[0] + b[2] for b in bx), max(b[1] + b[3] for b in bx)
            _remember(ed, tc=[int(x0 - 30), int(y0 - 12), int(x1 - x0 + 80), int(y1 - y0 + 24)])
            return tcs[0], tcs[1]
    return "?", "?"


# ---------------------------------------------------------------- layout cache
# Where the player readout and the ruler sit, per window rect: OCR over half the screen took 7 s a read (a seek made
# a dozen), a remembered 300x40 crop takes a fraction of that (2026-09-27). A crop that stops reading is searched again.

def _cache_file():
    import tempfile
    return Path(tempfile.gettempdir()) / "capcut-win-layout.json"


def _layout(ed):
    import json
    try:
        return json.loads(_cache_file().read_text(encoding="utf-8")).get(",".join(map(str, ed["rect"])), {})
    except (OSError, ValueError):
        return {}


def _remember(ed, **kv):
    import json
    try:
        d = json.loads(_cache_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d.setdefault(",".join(map(str, ed["rect"])), {}).update(kv)
    try:
        _cache_file().write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


RULER = re.compile(r"^[|1lI]?(\d{2}):(\d{2})$")   # the tick mark before a label reads as | or 1 ("100:20")


def ruler(ed=None, fps=30.0):
    """The timeline ruler, fitted from its own labels (OCR): (y, x_of(seconds), seconds_of(x)). The labels are the
    ruler's own tick captions, so the fit survives any zoom and scroll. A 30 fps timeline labels '00:10'; a 29.97 one
    labels full drop-frame timecode, '00:00:10;00' … '00:01:00;02' (2026-09-27), read through parse_tc."""
    ed = ed or editor()
    x, y, w, h = ed["rect"]
    ry = _layout(ed).get("ruler_y")
    # the remembered band's LEFT HALF: two labels fit the scale, and every label more cost OCR time (1.4 s the full width)
    bands = ([(x, int(ry) - 22, w // 2, 44)] if ry else []) + [(x, y + int(h * 0.5), w, int(h * 0.3))]
    for band in bands:
        words, _ = ocr(band)
        pts = []
        for t, wx, wy, ww, wh in words:
            t = t.replace(" ", "")
            m = RULER.match(t)
            if m:
                pts.append((int(m.group(1)) * 60 + int(m.group(2)), wx, wy + wh / 2))
                continue
            m = TC.search(t)
            if m and t.lstrip("|1lI").startswith(m.group(0)):
                pts.append((parse_tc(m.group(0), fps), wx, wy + wh / 2))
        if len(pts) >= 2:
            break
    if len(pts) < 2:
        sys.exit("timeline ruler not found (is the timeline panel visible?)")
    if band is bands[-1]:
        _remember(ed, ruler_y=round(sorted(p[2] for p in pts)[len(pts) // 2]))
    pts.sort()
    (t0, x0, y0), (t1, x1, _) = pts[0], pts[-1]
    px = (x1 - x0) / (t1 - t0)
    # a label sits just right of its tick mark (the '|' OCR often drops): the tick is ~6 px left of the text
    x_of = lambda s: x0 - 6 + (s - t0) * px
    return y0, x_of, (lambda X: t0 + (X - x0 + 6) / px)


def seek(seconds, fps=30.0):
    """Park the playhead on an exact frame: a ruler click at the fitted x, then paced arrow-key frame steps closed
    against the player's OCR'd readout (the mac lane's loop: CapCut drops back-to-back steps)."""
    ed = editor()
    ry, x_of, _ = ruler(ed, fps)
    click_at(max(ed["rect"][0] + 230, x_of(seconds)), ry)
    time.sleep(0.4)
    now = None
    for _ in range(8):
        cur, _tot = playhead(ed)
        if cur == "?":
            break
        now = parse_tc(cur, fps)
        err = round((seconds - now) * fps)
        if err == 0:
            return now
        key = "right" if err > 0 else "left"
        for _ in range(min(abs(err), 300)):
            send_key(key)
            time.sleep(0.04)
        time.sleep(0.4)
    cur, _ = playhead(ed)
    return parse_tc(cur, fps) if cur != "?" else now


def main_track_y(ed=None):
    """The main video track's row: the y of its clips' filename labels (OCR)."""
    ed = ed or editor()
    x, y, w, h = ed["rect"]
    words, _ = ocr((x, y + int(h * 0.62), w, int(h * 0.38)))
    # the main track carries the 'Cover' button at its head, centred on the thumbnails: steadier than the filename
    # labels, which OCR read on one crop and dropped on a crop 9 px wider (2026-09-27)
    cov = [wy + wh / 2 for t, wx, wy, ww, wh in words if t.lower() == "cover" and wx < x + w * 0.2]
    if cov:
        return cov[0]
    ys = [wy + wh / 2 for t, wx, wy, ww, wh in words if re.search(r"\.(mov|mp4|m4v|mkv)", t.lower())]
    # no `$`: OCR glues a label to the clip's duration beside it ("take1.mov00:00:09:23") at some zoom levels
    if not ys:
        sys.exit("no clip labels found on the timeline")
    return max(ys) + 30              # the lowest labelled row is the main track; its thumbnails start under the label


def select_at(seconds, fps=30.0):
    """Select the main-track clip under `seconds`: seek there, then click the main track at the playhead's x."""
    ed = editor()
    seek(seconds, fps)
    _, x_of, _ = ruler(ed, fps)
    click_at(x_of(seconds) + 2, main_track_y(ed))
    time.sleep(0.4)


def key_action(combo, ed=None):
    editor() if ed is None else None
    send_key(combo)
    time.sleep(0.5)


def shot(out):
    ed = editor_window() or window("HomeWindow")
    if ed is None:
        sys.exit("no CapCut window")
    grab(rect_of(ed), out)
    return out


def dump():
    for w in windows():
        print(f"window {w['aid'] or '-':14s} {w['cls']:34s} {w['rect']}")
    w = editor_window() or window("HomeWindow")
    if w:
        _, lines = ocr(rect_of(w))
        for t, _l in lines:
            print("  text:", t)


def click_text(needle):
    w = editor_window() or window("HomeWindow")
    front(w, maximize=False)
    hit = find_text(needle, rect_of(w), timeout=3)
    if hit is None:
        sys.exit(f"text not found on screen: {needle}")
    click_at(hit[1] + hit[3] / 2, hit[2] + hit[4] / 2)
    return hit[0]


# CapCut's Windows default "Export to" is %LOCALAPPDATA%\CapCut\Videos (created on the first export; stored in no
# config file, 2026-09-27); a folder the user picked in the dialog is one of the usual libraries
EXPORT_DIRS = [USER_DATA.parent / "Videos"] + [Path.home() / d for d in ("Videos", "Downloads", "Documents", "Desktop")]


def close_share(ed):
    """The post-export share screen ('Video is saved to your desktop… Share / Close') is painted in the editor and holds
    the file OPEN (its preview plays it: the move failed 'resource busy', 2026-09-27), and while it is up the export
    shortcut does nothing. Close it by its Close button, the one beside Share; never Share, which publishes."""
    for _ in range(4):
        _, lines = ocr(ed["rect"])
        share = [bx for t, bx in lines if t.strip().lower() == "share" and bx[1] > ed["rect"][1] + 100]
        close = [bx for t, bx in lines if t.strip().lower() == "close"
                 and any(abs(sb[1] - bx[1]) < 12 and 0 < bx[0] - sb[0] < 300 for sb in share)]
        if not close:
            return
        c = close[0]
        click_at(c[0] + c[2] / 2, c[1] + c[3] / 2)
        time.sleep(1.5)


def _norm(t):
    return t.replace(" ", "").replace(".", "").lower()        # OCR reads "H.264" as "H264" as often as not


def set_export_choice(ed, label, want, is_value):
    """Pick `want` on the export dialog's `label` row (a dropdown), read back: the value right of the label on its row,
    then the option by its text in the open list. `is_value(normalised text)` says which texts on the row can be the
    value. Exits on a row, an option or a readback it cannot find."""
    def row():
        _, lines = ocr(ed["rect"])
        for lab in [bx for t, bx in lines if _norm(t) == _norm(label)]:
            val = [(_norm(t), bx) for t, bx in lines
                   if abs(bx[1] - lab[1]) < 14 and 50 < bx[0] - lab[0] < 400 and is_value(_norm(t))]
            if val:
                return val[0]
        return None

    cur = row()
    if cur is None:
        sys.exit(f"export dialog: the {label} row is not on screen")
    if cur[0] == _norm(want):
        return
    click_at(cur[1][0] + cur[1][2] / 2, cur[1][1] + cur[1][3] / 2)
    time.sleep(1.0)
    _, lines = ocr(ed["rect"])
    opts = [bx for t, bx in lines if _norm(t) == _norm(want) and abs(bx[1] - cur[1][1]) > 10]
    if not opts:
        send_key("escape")
        sys.exit(f"export dialog: no '{want}' in the {label} list")
    o = opts[0]
    click_at(o[0] + o[2] / 2, o[1] + o[3] / 2)
    time.sleep(1.0)
    now = row()
    if now is None or now[0] != _norm(want):
        sys.exit(f"export dialog: {label} reads {now and now[0]!r} after picking {want}")


def set_export_fps(ed, fps):
    """Pick the export frame rate ('29.97fps'): the dialog defaults to 30 fps whatever the footage (2026-09-27)."""
    set_export_choice(ed, "Frame rate", (f"{fps:.3f}".rstrip("0").rstrip(".")) + "fps", lambda t: t.endswith("fps"))


MASTER_KBPS = 50000                  # the dialog's Custom bit rate ceiling: typed 60000, it read back 50000 (2026-09-27)
AUDIO_FORMATS = ("mp3", "wav", "aac", "flac")
BIT_RATES = ("lower", "recommended", "higher", "custom")


def wheel(x, y, notches):
    """Mouse-wheel `notches` down (negative: up) with the cursor at (x, y), physical px: the export dialog's settings
    panel scrolls under the cursor, and its Audio section sits below the fold."""
    user32.SetCursorPos(int(x), int(y))
    for _ in range(abs(notches)):
        user32.mouse_event(0x0800, 0, 0, -120 if notches > 0 else 120, 0)   # MOUSEEVENTF_WHEEL
        time.sleep(0.05)
    time.sleep(0.6)


def dialog_value(ed, label, is_value=lambda t: True):
    """(text, box) of the value right of `label` on its row in the export dialog, or None."""
    _, lines = ocr(ed["rect"])
    for lab in [bx for t, bx in lines if _norm(t) == _norm(label)]:
        val = [(t, bx) for t, bx in lines if abs(bx[1] - lab[1]) < 14 and 50 < bx[0] - lab[0] < 400 and is_value(_norm(t))]
        if val:
            return val[0]
    return None


def set_export_kbps(ed, kbps):
    """Bit rate = Custom and `kbps` typed into its Kbps field, read back (the field takes real key input; CapCut clamps it
    at MASTER_KBPS)."""
    set_export_choice(ed, "Bit rate", "Custom", lambda t: t in BIT_RATES)
    time.sleep(0.8)
    _, lines = ocr(ed["rect"])
    lab = [bx for t, bx in lines if _norm(t) == "bitrate"][0]
    field = [bx for t, bx in lines if t.strip().isdigit() and 20 < bx[1] - lab[1] < 60]
    if not field:
        sys.exit("export dialog: no Kbps field under Bit rate = Custom")
    f = field[0]
    click_at(f[0] + f[2] / 2, f[1] + f[3] / 2, clicks=3)
    time.sleep(0.3)
    send_key("ctrl+a")
    for ch in str(int(kbps)):
        send_key(ch)
    send_key("tab")
    time.sleep(0.8)
    _, lines = ocr(ed["rect"])
    now = [t.strip() for t, bx in lines if t.strip().isdigit() and 20 < bx[1] - lab[1] < 60]
    if not now or int(now[0]) != int(kbps):
        sys.exit(f"export dialog: the Kbps field reads {now and now[0]!r} after typing {kbps}")


def set_export_audio(ed, fmt="WAV"):
    """Tick the Audio section (a separate audio file beside the video) and pick its Format, read back. The section sits
    below the fold: the panel is wheeled down over the Frame rate row and back up after. A ticked box is drawn in the
    accent colour (a bright, blue-green pixel left of the title), an unticked one grey."""
    fr = dialog_value(ed, "Frame rate")
    if fr is None:
        sys.exit("export dialog: no Frame rate row to scroll from")
    x, y = fr[1][0], fr[1][1]
    wheel(x, y, 8)
    _, lines = ocr(ed["rect"])
    title = [bx for t, bx in lines if _norm(t).startswith("audio") and abs(bx[0] - (x - 90)) < 250]
    if not title:
        sys.exit("export dialog: the Audio section is not on screen after scrolling")
    a = title[0]
    box = (a[0] - 18, a[1] + a[3] / 2)

    def ticked():
        px = grab((int(box[0]) - 3, int(box[1]) - 3, 7, 7)).convert("RGB").getpixel((3, 3))
        return px[1] > 120 and px[2] > 120 and px[0] < 120
    if not ticked():
        click_at(*box)
        time.sleep(0.8)
    if not ticked():
        sys.exit("export dialog: the Audio section did not tick")
    set_export_choice(ed, "Format", fmt, lambda t: t in AUDIO_FORMATS)
    wheel(x, y, -8)


def set_export_codec(ed, codec="H.264"):
    """Pick the export codec: the dialog defaulted to HEVC on the Windows re-test (2026-09-27), which the bridge's own
    check then failed ("✗ H.264"); every lane's deliverable is H.264 (the presets' § Export)."""
    set_export_choice(ed, "Codec", codec, lambda t: t in ("h264", "hevc", "av1", "h265", "prores"))


def export(timeout=900, fps=None, master=True):
    """The exportVideo shortcut (Ctrl+E on the built-in keymap) opens the export dialog; the settings are set and read
    back, its Export button (the one beside Cancel, never the title-bar one) is clicked, and the render is polled for
    until its size holds. The post-export share screen is closed by its Close, never clicked through (it publishes).
    -> (video, audio or None, size): where CapCut wrote them, never moved (the bridge places the deliverable).

    master=True (the default, the user's call 2026-09-27): the presets' numbers are H.264 High, CBR 14, AAC 320k, and the
    dialog has no profile or audio-bitrate control (its Recommended landed Main, 10 Mbps, AAC 197k), so CapCut writes a
    MASTER: H.264 at MASTER_KBPS, plus the Audio section's WAV of its own mix, and the bridge encodes the deliverable
    from them with workflows/deliver.py. master=False: H.264 at the dialog's own bit rate, no audio file.

    Only the dialog's own Name is watched for (read off the dialog), in CapCut's export folders: an unrelated mp4 that
    changes during the render (a browser download, a finalize.sh copy) is never taken for it (the Mac review)."""
    ed = editor()
    close_share(ed)                                     # a share screen left up from an earlier export

    def sig(p):
        st = p.stat()
        return st.st_size, st.st_mtime_ns, st.st_ctime_ns

    send_key(shortcut("exportVideo"))

    def dialog_button():
        # the dialog is painted INSIDE the editor window on Windows (no window of its own): its button is the 'Export'
        # with a 'Cancel' beside it on the same row, never the title-bar 'Export' or the 'Export to' label
        dlg = [w for w in windows() if w["hwnd"] != ed["hwnd"] and w["aid"] != "HomeWindow"
               and not w["cls"].startswith("Splash")]
        area = rect_of(max(dlg, key=lambda w: w["rect"][2] * w["rect"][3])) if dlg else ed["rect"]
        _, lines = ocr(area)
        cancel = [bx for t, bx in lines if t.strip().lower() == "cancel"]
        for t, bx in lines:
            if t.strip().lower() == "export" and any(abs(c[1] - bx[1]) < 12 and 0 < c[0] - bx[0] < 300 for c in cancel):
                return bx
        return None

    btn, t0 = None, time.time()
    while btn is None and time.time() - t0 < 25:
        time.sleep(1.5)
        btn = dialog_button()
    if btn is None:
        sys.exit("export dialog: no Export button beside a Cancel read on screen")
    nm = dialog_value(ed, "Name")
    if nm is None or not nm[0].strip():
        sys.exit("export dialog: the Name field is not readable (the file to wait for is named by it)")
    name = nm[0].strip()
    set_export_codec(ed)
    if master:
        set_export_kbps(ed, MASTER_KBPS)
    if fps:
        set_export_fps(ed, fps)
    if master:
        set_export_audio(ed, "WAV")
    btn = dialog_button() or btn

    def ours(ext):
        # the export itself, or CapCut's numbered twin of it ("<name>(1).mp4"): never any other file in those folders.
        # With the Audio section ticked CapCut writes BOTH files into a folder named after the export,
        # <Export to>\<name>\<name>.mp4 + <name>.WAV (read on the re-test, 2026-09-28), so that folder is looked in too
        pat = re.compile(re.escape(name) + r"( ?\(\d+\)|_\d+)?" + re.escape(ext) + "$", re.I)
        dirs = [x for d in EXPORT_DIRS for x in (d, d / name) if x.is_dir()]
        return [p for d in dirs for p in d.iterdir() if p.is_file() and pat.match(p.name)]
    # a file is NEW when its (size, mtime, birth) differs from before the click: CapCut stamps an overwritten export
    # with the ORIGINAL file's mtime, so a start-time filter missed a real render (2026-09-27)
    before = {p: sig(p) for ext in (".mp4", ".wav") for p in ours(ext)}
    t_start = time.time()

    def started():
        return any(before.get(p) != sig(p) for ext in (".mp4", ".wav") for p in ours(ext))

    def refuse_existing():
        # CapCut asks "File already exists ... replace it?" when <name> is already in its export folder. Never OK: that
        # replaces a file the creator may have exported by hand. Its Cancel is the one nearest under the question.
        _, lines = ocr(ed["rect"])
        q = [bx for t, bx in lines if "already exists" in t.lower()]
        if not q:
            return False
        cancels = sorted((bx for t, bx in lines if t.strip().lower() == "cancel" and bx[1] > q[0][1]),
                         key=lambda b: b[1] - q[0][1])
        if cancels:
            click_at(cancels[0][0] + cancels[0][2] / 2, cancels[0][1] + cancels[0][3] / 2)
            time.sleep(1)
        b = dialog_button()
        if b is not None:                              # and close the export dialog itself
            _, lines = ocr(ed["rect"])
            c = [bx for t, bx in lines if t.strip().lower() == "cancel" and abs(bx[1] - b[1]) < 12]
            if c:
                click_at(c[0][0] + c[0][2] / 2, c[0][1] + c[0][3] / 2)
        there = [str(p) for ext in (".mp4", ".wav") for p in ours(ext)]
        sys.exit(f"export refused: CapCut's export folder already holds {', '.join(there) or name} and asked to replace "
                 f"it; move that file (it may be your own export), or rename the draft, then export again")

    # A click counts as taken when the render's own file changes or the dialog goes away. Not "the dialog is gone
    # within 3 s": with the Audio section ticked a 32 s draft rendered in about 4 s and CapCut showed the export
    # dialog AGAIN, so the old loop clicked Export a second time and met "File already exists" (the re-test, 2026-09-28)
    for attempt in range(3):
        click_at(btn[0] + btn[2] / 2, btn[1] + btn[3] / 2)
        t_click, taken = time.time(), False
        while time.time() - t_click < 12:
            time.sleep(1.5)
            refuse_existing()
            if started() or dialog_button() is None:
                taken = True
                break
        if taken:
            break
    else:
        sys.exit("export dialog: the Export click did not start the render (the dialog is still up, no file changed)")
    target, last, stable = None, -1, 0
    while time.time() - t_start < timeout:
        time.sleep(3)
        fresh = [p for p in ours(".mp4") if before.get(p) != sig(p)]
        if not fresh:
            continue
        target = max(fresh, key=lambda p: p.stat().st_mtime_ns)
        size = target.stat().st_size
        stable = stable + 1 if size == last and size > 0 else 0
        last = size
        if stable >= 2:
            break
    close_share(ed)
    b = dialog_button()
    if b is not None:                                   # CapCut re-showed the export dialog after the render: close it
        _, lines = ocr(ed["rect"])
        c = [bx for t, bx in lines if t.strip().lower() == "cancel" and abs(bx[1] - b[1]) < 12]
        if c:
            click_at(c[0][0] + c[0][2] / 2, c[0][1] + c[0][3] / 2)
            time.sleep(1)
    if target is None:
        sys.exit(f"export produced no {name}.mp4 in {', '.join(str(d) for d in EXPORT_DIRS if d.exists())}")
    audio = None
    if master:
        wavs = [p for p in ours(".wav") if before.get(p) != sig(p) and p.parent == target.parent]
        audio = max(wavs, key=lambda p: p.stat().st_mtime_ns) if wavs else None
    return target, audio, last


# ---------------------------------------------------------------- the ACTIVE keymap
# Config/keymapSettings currentKeymapIndex picks the keymap. Index 0 is CapCut's BUILT-IN default, which has no file:
# its split is Ctrl+B (proven 2026-09-27: Ctrl+K from Custom1.json did nothing, Ctrl+B split the selected clip) and it
# matches the shipped "Final Cut Pro X.json" on every action read, so that file stands in for it. The other indexes
# map to the shipped files in the order CapCut lists them (UNVERIFIED past index 0: check `key` on a new install).
KEYMAP_FILES = [None, "Final Cut Pro X.json", "Premiere Pro.json", "Custom1.json", "Custom2.json", "Custom3.json"]


def keymap():
    import json as _json
    cfg = USER_DATA / "Config"
    idx = 0
    try:
        for line in (cfg / "keymapSettings").read_text(encoding="utf-8").splitlines():
            if line.startswith("currentKeymapIndex="):
                idx = int(line.split("=", 1)[1])
    except (OSError, ValueError):
        pass
    name = KEYMAP_FILES[idx] if 0 <= idx < len(KEYMAP_FILES) and KEYMAP_FILES[idx] else "Final Cut Pro X.json"
    try:
        return _json.loads((cfg / "Shortcut" / name).read_text(encoding="utf-8"))["sequence"]
    except (OSError, ValueError, KeyError):
        return {"cutoff": ["Ctrl+B"], "del": ["Del"], "undo": ["Ctrl+Z"], "redo": ["Ctrl+Shift+Z"],
                "exportVideo": ["Ctrl+E"], "mark": ["M"], "cutLeft": ["Q"], "cutRight": ["W"],
                "quicklyAdjustZoomFit": ["Shift+Z"], "togglePlay": ["Space"], "returnDraftPage": ["Ctrl+Alt+Q"]}


def shortcut(action):
    """The key combo for a CapCut action in the ACTIVE keymap, as send_key takes it ('ctrl+b')."""
    keys = [k for k in keymap().get(action) or [] if k and "Mouse" not in k and "Wheel" not in k]
    if not keys:
        sys.exit(f"no keyboard shortcut for CapCut action {action!r} in the active keymap")
    return keys[0].lower()
