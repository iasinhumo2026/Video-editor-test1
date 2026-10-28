# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""wincap.py: the Windows backend of window-grab.sh and screen-record.sh (both delegate here on Windows).

  uv run workflows/wincap.py list <app>                                   # windows of <app>, biggest first, with bounds
  uv run workflows/wincap.py grab <app> <out.png> [index]                 # a COVERED window's own buffer, never fronted
  uv run workflows/wincap.py record [--list] [--clicks] [--force] [--preflight <pii.json>] [--settle MS]
                                    [--bounds W,H[,X,Y]] <app> <out.mp4> [seconds] [index]

<app> matches a window's process name (chrome.exe, Adobe Premiere Pro.exe) or its title, case-insensitive, substring.
The same contract as the macOS scripts (their headers are the spec): index 1 = the biggest matching window; a record is
an H.264 mp4 at a CONSTANT rate (FPS env, default 30000/1001), native pixels, exactly <seconds> long (default 5), no audio, of the
window's screen RECT with the app fronted for the take (VE_CAPTURE_FRONTED=1 skips the fronting); --bounds sizes (and
places) the window for the take and puts it back afterwards, on failure too; --preflight runs pii-scan.py --still on
the window's own buffer (before fronting) and on the exact screen rect (after fronting and --settle), refusing the take
with exit 4 on a hit or on a grab that reads no text. Exit 0 ok · 1 could not · 2 usage, or an output that exists (no --force) · 4 preflight refused.

Windows mechanics (2026-09-27): the buffer grab is PrintWindow(PW_RENDERFULLCONTENT), which reads a covered window
(Chrome, Premiere, Electron apps included); a MINIMIZED window has no buffer and is refused. Bounds and the screen rect
are the DWM extended frame (the visible window, no drop shadow), in physical pixels (per-monitor DPI aware). The take
is ffmpeg gdigrab over that rect (gdigrab cannot read a covered window, the same reason macOS fronts the app).
--clicks: gdigrab draws the cursor but has no click rings; the flag is accepted and said out loud.
"""
import ctypes
import os
import signal
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
if sys.platform == "win32":
    user32, gdi32, kernel32, dwmapi = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32, ctypes.windll.dwmapi
else:                                  # importable anywhere: its pure parts are tested on every OS
    user32 = gdi32 = kernel32 = dwmapi = None
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))      # per-monitor v2: physical pixels everywhere
except Exception:
    pass


def say(msg):
    print(f"[wincap] {msg}", file=sys.stderr, flush=True)


def exe_of(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)             # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(h)


def frame_rect(hwnd):
    """The visible window (DWM extended frame, no shadow): (x, y, w, h) in physical pixels."""
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def outer_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def outer_for(want, frame, outer):
    """The OUTER rect (what SetWindowPos takes) that puts the visible frame at `want` (x, y, w, h): the outer rect carries
    invisible resize borders the DWM frame does not (about 7 px a side at 100 %, more at higher scaling), so setting the
    frame's numbers as the outer rect shrank and shifted every take's window by them (the Mac review, 2026-09-27)."""
    l, t = frame[0] - outer[0], frame[1] - outer[1]
    r, b = (outer[0] + outer[2]) - (frame[0] + frame[2]), (outer[1] + outer[3]) - (frame[1] + frame[3])
    return want[0] - l, want[1] - t, want[2] + l + r, want[3] + t + b


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
                ("ptMinPosition", wintypes.POINT), ("ptMaxPosition", wintypes.POINT), ("rcNormalPosition", wintypes.RECT)]


def placement(hwnd):
    """The window's placement (its normal rect AND its maximized/minimized state), for put_back()."""
    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(wp)
    user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
    return wp


def put_back(hwnd, wp):
    """Restore a placement saved by placement(): a maximized window comes back maximized, a normal one to its rect."""
    wp.length = ctypes.sizeof(wp)
    return bool(user32.SetWindowPlacement(hwnd, ctypes.byref(wp)))


def windows(app):
    """Visible, uncloaked top-level windows of <app>, biggest first: [{hwnd, exe, title, rect}]."""
    needle, out = app.lower(), []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        cloaked = wintypes.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        if cloaked.value:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        title, exe = buf.value, exe_of(hwnd)
        x, y, w, h = frame_rect(hwnd)
        if w < 100 or h < 60 or not (needle in exe.lower() or needle in title.lower()):
            return True
        out.append({"hwnd": hwnd, "exe": exe, "title": title, "rect": (x, y, w, h),
                    "minimized": bool(user32.IsIconic(hwnd))})
        return True
    user32.EnumWindows(cb, 0)
    return sorted(out, key=lambda w: -(w["rect"][2] * w["rect"][3]))


def pick(app, index):
    ws = windows(app)
    if not ws:
        say(f"no visible window matches '{app}' (process name or title)")
        sys.exit(1)
    if index < 1 or index > len(ws):
        say(f"'{app}' has {len(ws)} window(s), no index {index}")
        sys.exit(2)
    return ws[index - 1]


def list_windows(app):
    ws = windows(app)
    for i, w in enumerate(ws, 1):
        x, y, ww, hh = w["rect"]
        print(f"{i}\t{w['exe']}\t{ww}x{hh} at {x},{y}{'  (minimized)' if w['minimized'] else ''}\t{w['title']}")
    if not ws:
        say(f"no visible window matches '{app}'")
        return 1
    return 0


def grab_buffer(w, out):
    """PrintWindow(PW_RENDERFULLCONTENT) into a bitmap, cropped to the visible frame: a covered window grabs correctly."""
    from PIL import Image
    hwnd = w["hwnd"]
    if user32.IsIconic(hwnd):
        say("the window is MINIMIZED: it has no live buffer to grab (restore it, it need not be in front)")
        return False
    wr = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    W, H = wr.right - wr.left, wr.bottom - wr.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, W, H)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, 2)                          # PW_RENDERFULLCONTENT

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bih = BIH(ctypes.sizeof(BIH), W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(W * H * 4)
    gdi32.GetDIBits(mdc, bmp, 0, H, buf, ctypes.byref(bih), 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    if not ok:
        say("PrintWindow failed on this window")
        return False
    img = Image.frombuffer("RGB", (W, H), buf, "raw", "BGRX", 0, 1)
    fx, fy, fw, fh = w["rect"]
    img = img.crop((fx - wr.left, fy - wr.top, fx - wr.left + fw, fy - wr.top + fh))
    if img.getextrema() in (((0, 0), (0, 0), (0, 0)),):
        say("the grab is solid black: the app did not render into PrintWindow (a hardware-overlay surface?)")
        return False
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"{out}  {fw}x{fh}  ({w['exe']}: {w['title'][:60]})")
    return True


def front(w):
    """Foreground a window from a background process: the foreground lock needs the thread input attached."""
    hwnd = w["hwnd"]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)                                   # SW_RESTORE
    fg = user32.GetForegroundWindow()
    a = user32.GetWindowThreadProcessId(fg, None)
    b = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(b, a, True)
    user32.keybd_event(0x12, 0, 0, 0); user32.keybd_event(0x12, 0, 2, 0)     # an Alt tap releases the lock
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    user32.AttachThreadInput(b, a, False)
    time.sleep(0.4)


def preflight_check(pii, img, label):
    r = subprocess.run(["uv", "run", "-q", str(HERE / "pii-scan.py"), "--still", str(img), "--pii", str(pii)],
                       capture_output=True, text=True, encoding="utf-8")
    txt = (r.stdout + r.stderr).strip()
    if r.returncode == 0 and "flagged" in txt and " 0 flagged" not in txt and "✗" in txt:
        pass
    hits = [l for l in txt.splitlines() if l.strip().startswith("✗")]
    if r.returncode != 0 or hits:
        say(f"PREFLIGHT refused the take on the {label}:\n" + "\n".join("    " + l for l in txt.splitlines()[-8:]))
        return False
    say(f"preflight {label}: clean ({txt.splitlines()[0] if txt else 'no output'})")
    return True


def record(argv):
    opts = {"clicks": False, "force": False, "preflight": None, "settle": 800, "bounds": None, "list": False}
    a = list(argv)
    while a and a[0].startswith("--"):
        f = a.pop(0)
        if f in ("--clicks", "--force", "--list"):
            opts[f[2:]] = True
        elif f in ("--preflight", "--settle", "--bounds"):
            if not a:
                say(f"{f} needs a value"); return 2
            opts[f[2:]] = a.pop(0)
        else:
            say(f"unknown flag {f}"); return 2
    if opts["list"]:
        return list_windows(a[0] if a else "")
    if len(a) < 2:
        say("usage: record [flags] <app> <out.mp4> [seconds] [index]"); return 2
    app, out, secs = a[0], Path(a[1]), (a[2] if len(a) > 2 else "5")    # macOS screen-record.sh: 5 s by default
    index = int(a[3]) if len(a) > 3 else 1
    try:
        secs = float(secs); settle = int(opts["settle"])
    except ValueError:
        say("seconds must be a number and --settle whole milliseconds"); return 2
    if out.exists() and not opts["force"]:                              # exit 2, as screen-record.sh on macOS
        say(f"{out} exists: a capture already in a comp keeps its name; write a new one or pass --force"); return 2
    if opts["preflight"] and not Path(opts["preflight"]).is_file():
        say(f"--preflight: no file at {opts['preflight']}"); return 2
    fps = os.environ.get("FPS", "30000/1001")
    w = pick(app, index)
    if opts["clicks"]:
        say("--clicks: gdigrab draws the cursor but has no click rings on Windows")
    tmp = out.with_suffix(".preflight")
    tmp.mkdir(parents=True, exist_ok=True)
    orig = saved = None
    try:
        if opts["preflight"]:
            time.sleep(settle / 1000)
            if not grab_buffer(w, tmp / "window.png") or not preflight_check(opts["preflight"], tmp / "window.png", "window buffer"):
                return 4
        if opts["bounds"]:
            parts = [int(v) for v in opts["bounds"].split(",")]
            if len(parts) not in (2, 4):
                say("--bounds is W,H[,X,Y]"); return 2
            orig, saved = w["rect"], placement(w["hwnd"])       # the placement keeps a maximized window's state too
            user32.ShowWindow(w["hwnd"], 9)                     # SW_RESTORE: a maximized window takes no size
            time.sleep(0.2)
            now = frame_rect(w["hwnd"])
            x, y = (parts[2], parts[3]) if len(parts) == 4 else now[:2]
            ox, oy, ow, oh = outer_for((x, y, parts[0], parts[1]), now, outer_rect(w["hwnd"]))
            user32.SetWindowPos(w["hwnd"], 0, ox, oy, ow, oh, 0x0004 | 0x0010)   # NOZORDER|NOACTIVATE
            time.sleep(0.3)
            w["rect"] = frame_rect(w["hwnd"])
            say(f"bounds: {orig[2]}x{orig[3]} at {orig[0]},{orig[1]} -> {w['rect'][2]}x{w['rect'][3]} at {w['rect'][0]},{w['rect'][1]}")
            if abs(w["rect"][2] - parts[0]) > 16 or abs(w["rect"][3] - parts[1]) > 16:
                say("the app would not take that size: refusing the take rather than record the wrong layout"); return 1
        if os.environ.get("VE_CAPTURE_FRONTED") != "1":
            front(w)
            say(f"fronted {w['exe']} for the take")
        x, y, ww, hh = w["rect"]
        ww, hh = ww - ww % 2, hh - hh % 2
        if opts["preflight"]:
            time.sleep(max(settle, 400) / 1000)
            from PIL import ImageGrab
            ImageGrab.grab(bbox=(x, y, x + ww, y + hh), all_screens=True).save(tmp / "rect.png")
            if not preflight_check(opts["preflight"], tmp / "rect.png", "screen rect"):
                return 4
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "gdigrab", "-framerate", "60", "-draw_mouse", "1",
               "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{ww}x{hh}", "-i", "desktop",
               "-t", f"{secs:.3f}", "-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "16", "-an", "-movflags", "+faststart", str(out)]
        say(f"recording {ww}x{hh} at {x},{y} for {secs:g} s at {fps} fps -> {out}")
        r = subprocess.run(cmd)
        if r.returncode != 0 or not out.exists():
            say("ffmpeg did not produce the take"); return 1
        print(f"{out}  {ww}x{hh}  {secs:g}s")
        return 0
    finally:
        if saved is not None:
            put_back(w["hwnd"], saved)
            back = frame_rect(w["hwnd"])
            say(f"bounds restored to {back[2]}x{back[3]} at {back[0]},{back[1]}"
                + ("" if back == tuple(orig) else f" (was {orig[2]}x{orig[3]} at {orig[0]},{orig[1]})"))
        for f in tmp.glob("*.png"):
            f.unlink()
        try:
            tmp.rmdir()
        except OSError:
            pass


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "list":
        return list_windows(rest[0] if rest else "")
    if cmd == "grab":
        if not rest:
            say("usage: grab <app> <out.png> [index]"); return 2
        w = pick(rest[0], int(rest[2]) if len(rest) > 2 else 1)
        return 0 if grab_buffer(w, rest[1] if len(rest) > 1 else "window-grab.png") else 1
    if cmd == "record":
        return record(rest)
    print(__doc__); return 2


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8")
        except Exception:
            pass
    sys.exit(main())
