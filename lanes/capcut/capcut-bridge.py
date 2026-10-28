#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#   "pyobjc-framework-ApplicationServices; sys_platform == 'darwin'",
#   "pyobjc-framework-Quartz; sys_platform == 'darwin'",
#   "uiautomation; sys_platform == 'win32'",
#   "rapidocr>=3,<3.9; sys_platform == 'win32'",
#   "onnxruntime; sys_platform == 'win32'",
#   "numpy; sys_platform == 'win32'",
#   "pillow; sys_platform == 'win32'",
# ]
# [tool.uv]
# exclude-newer = "14 days"
# ///
# CapCut bridge: drive the CapCut app live + replay a job's EDL into a new
# CapCut draft. macOS and Windows. Two lanes, validated 2026-07-27 on CapCut 8.9.0 (macOS)
# and ported 2026-09-27 to CapCut 9.5 on Windows (capcut_win.py: there the live lane is
# windows + keyboard shortcuts + Windows OCR, because UI Automation exposes no QML controls):
#
#   FILE lane  - CapCut has no API; drafts are plaintext JSON in
#                ~/Movies/CapCut/User Data/Projects/com.lveditor.draft/.
#                `replay` writes a new draft (draft_info.json + meta + root
#                registry entry) straight from projects/<job>/transcript/cuts.json,
#                one timeline segment per EDL cut, source times in microseconds.
#                The app must be CLOSED while writing (it rewrites the registry
#                on quit); the bridge quits/relaunches it around the write.
#
#   LIVE lane  - the QML UI ships ByteDance's internal automation IDs in the
#                macOS accessibility tree (PlayerPlayBtn, MTLSVideoP:<clip>,
#                currentProgress|HH:MM:SS:FF, ...). Elements are found by name
#                via the AX API and clicked with synthesized CGEvents at their
#                screen-point centers. AX IDs are test hooks, not a contract:
#                re-verify with `dump` after CapCut updates.
#
# FILE-LANE ops relaunch the app (structural, batched); LIVE-lane ops act on the
# open editor with no restart at all.
#
# Usage — file lane (build/structural):
#   replay <job> [--name <draft>]            # EDL -> new draft, one clip per cut (a job name, or a job folder path)
#   add-overlay <draft> <mov> --at <s> [--layer N] [--dur <s>]
#   add-text <draft> "<text>" --at <s> [--dur <s>]
#   graphics <draft> <job>                   # lay hf-graphics/placement.json (workflows/placement.py --write), premultiplied
#   layout <draft> <job> [--hand a-b:M=s,cx,cy]   # the Talking Head Explainer's footage modes on the main track
#   sfx-pack <draft> [--dry]                 # the whole SFX pack into the draft's Media panel, for hand placing
#   transform <draft> [--track main|text|overlay] [--index N] [--scale S] [--x X] [--y Y] [--rotate R] [--opacity O]
#   ls                                       # drafts in the registry
#
# Usage — live lane (open editor, no restart):
#   open <draft> · launch · quit
#   seek <seconds> [--draft <name>]          # frame-exact, closed-loop
#   select <i> · split [seconds] · delete <i>
#   trim-left · trim-right · undo · redo · marker · zoomfit · save
#   play · playhead · clips · state          # state = JSON timeline snapshot
#   shot [out.png]                           # window grab for QA
#   dump [needle] · click <name> · key <combo>

USAGE = """Usage — file lane (structural builds; quits + relaunches the app around the write):
  replay <job> [--name <draft>] [--media <polished take>]   # EDL -> new draft, one clip per cut
  add-overlay <draft> <mov> --at <s> [--layer N] [--dur <s>] [--src <s>] [--ri N] [--mute] [--force]
  add-text <draft> "<text>" --at <s> [--dur <s>] [--ri N] [--force]
  graphics <draft> <job>                   # lay hf-graphics/placement.json (workflows/placement.py --write), premultiplied
  layout <draft> <job> [--hand a-b:M=s,cx,cy]   # the Talking Head Explainer's footage modes on the main track
  sfx-pack <draft> [--dry]                 # the whole SFX pack (assets/sfx) into the draft's Media panel, for hand placing
  transform <draft> [--track main|text|overlay] [--index N] [--scale S] [--x X] [--y Y] [--rotate R] [--opacity O]
  remove <draft> [--track main|text|overlay] [--index N]
  keyframe <draft> [--track ...] [--index N] --at <s> [--scale S] [--x X] [--y Y] [--rotate R] [--opacity O]
  clear-keyframes <draft> [--track ...] [--index N]
  ls                                       # drafts in the registry

Usage — live lane (open editor, no restart):
  open <draft> · launch · quit
  seek <seconds> [--draft <name>]          # frame-exact, closed-loop
  select <i> · split [seconds] · delete <i>
  trim-left · trim-right · undo · redo · marker · zoomfit · save
  play · playhead · clips · state          # state = JSON timeline snapshot
  export [--to <dir>] [--timeout <s>] [--draft <name>] [--fps F]   # drive CapCut's export dialog, verify the file against the draft (Windows: sets every setting, writes a master + WAV, deliver.py encodes the presets' numbers into --to; --fps overrides the timeline's rate)
  shot [out.png]                           # window grab for QA
  dump [needle] · click <name> · clickxy <x> <y> · key <combo>"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

APP = "CapCut"
IS_WIN = sys.platform == "win32"
if IS_WIN:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import capcut_win as W  # noqa: E402  the Windows backend: draft root, lifecycle, the live lane
    DRAFT_ROOT = W.draft_root()
    # Windows CapCut names the draft file draft_content.json (macOS: draft_info.json) and keeps a second copy of it
    # under Timelines/<main_timeline_id>/ (multi-timeline drafts; Config/Common.ini multi_timeline_config_enabled)
    DRAFT_FILE = "draft_content.json"
else:
    DRAFT_ROOT = Path.home() / "Movies/CapCut/User Data/Projects/com.lveditor.draft"
    DRAFT_FILE = "draft_info.json"


def fold_str(p):
    """A draft path as CapCut itself writes it: forward slashes on Windows (draft_fold_path, file_Path, a material's
    path), the native string on macOS."""
    return Path(p).as_posix() if IS_WIN else str(p)


def file_in_fold(folder, name):
    """The registry's per-draft file path: CapCut on Windows writes '<forward-slash folder>' + a backslash + '<file>'."""
    return fold_str(folder) + "\\" + name if IS_WIN else str(Path(folder) / name)

# ---------------------------------------------------------------- app lifecycle


def app_pid():
    if IS_WIN:
        return W.app_pid()
    try:
        return int(subprocess.check_output(["pgrep", "-x", APP]).split()[0])
    except subprocess.CalledProcessError:
        return None


def quit_app(timeout=20):
    if IS_WIN:
        return W.quit_app()
    if app_pid() is None:
        return
    subprocess.run(["osascript", "-e", f'tell application "{APP}" to quit'], check=False)
    t0 = time.time()
    while app_pid() is not None:
        if time.time() - t0 > timeout:
            sys.exit(f"CapCut did not quit within {timeout}s, close it and re-run")
        time.sleep(0.5)


def launch_app():
    if IS_WIN:
        return W.launch_app()
    subprocess.run(["open", "-a", APP], check=True)
    subprocess.run(["osascript", "-e", f'tell application "{APP}" to activate'], check=False)


# ---------------------------------------------------------------- AX driver

if not IS_WIN:
  from ApplicationServices import (  # noqa: E402
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
    AXValueGetValue,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)
  from Quartz import (  # noqa: E402
    CGEventCreateKeyboardEvent,
    CGEventCreateMouseEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSetIntegerValueField,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskShift,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventMouseMoved,
    kCGHIDEventTap,
    kCGMouseButtonLeft,
    kCGMouseEventClickState,
)

KEYCODES = {"space": 49, "return": 36, "escape": 53, "delete": 51, "tab": 48,
            "left": 123, "right": 124, "down": 125, "up": 126,
            "home": 115, "end": 119,
            "a": 0, "b": 11, "c": 8, "s": 1, "v": 9, "z": 6}


def ax_app():
    pid = app_pid()
    if pid is None:
        sys.exit("CapCut is not running (use: launch)")
    return AXUIElementCreateApplication(pid)


def attr(el, name):
    err, val = AXUIElementCopyAttributeValue(el, name, None)
    return val if err == 0 else None


def geometry(el):
    ok, p = AXValueGetValue(attr(el, "AXPosition"), kAXValueCGPointType, None)
    ok2, s = AXValueGetValue(attr(el, "AXSize"), kAXValueCGSizeType, None)
    return (p.x, p.y, s.width, s.height) if ok and ok2 else None


def walk(el, visit, depth=0):
    if depth > 18:
        return
    visit(el, depth)
    for k in attr(el, "AXChildren") or []:
        walk(k, visit, depth + 1)


def elements(needle=None):
    """All (element, name, geometry) in all CapCut windows, name = title or description."""
    out = []

    def visit(el, depth):
        name = attr(el, "AXTitle") or attr(el, "AXDescription") or ""
        if needle is None or needle.lower() in name.lower():
            out.append((el, name, geometry(el)))

    for w in attr(ax_app(), "AXWindows") or []:
        walk(w, visit)
    return out


def find_one(needle, timeout=0):
    t0 = time.time()
    while True:
        hits = [h for h in elements(needle) if h[2]]
        if hits:
            return hits[0]
        if time.time() - t0 >= timeout:
            return None
        time.sleep(0.5)


_fronted = False


def ensure_front():
    """Activate CapCut before any synthesized input. Keystrokes go to whatever app
    is frontmost, so they need this outright. Clicks need it too, for a subtler
    reason that caused days of phantom flakiness: when the app is not frontmost,
    macOS spends the FIRST click activating the window and the app never sees it.
    In `calibrate` that meant probe A silently no-op'd, `ta` read a stale playhead,
    and the seconds<->pixels fit came out garbage — seek landing 40s off target,
    but only when some earlier action had not already fronted the app."""
    global _fronted
    if not _fronted:
        subprocess.run(["osascript", "-e", f'tell application "{APP}" to activate'],
                       check=False)
        time.sleep(0.4)
        _fronted = True


def click_at(x, y, clicks=1):
    ensure_front()
    e = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (x, y), kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, e)
    time.sleep(0.05)
    for n in range(1, clicks + 1):
        for kind in (kCGEventLeftMouseDown, kCGEventLeftMouseUp):
            e = CGEventCreateMouseEvent(None, kind, (x, y), kCGMouseButtonLeft)
            CGEventSetIntegerValueField(e, kCGMouseEventClickState, n)
            CGEventPost(kCGHIDEventTap, e)
            time.sleep(0.05)


def click_element(needle, clicks=1, timeout=5):
    hit = find_one(needle, timeout)
    if hit is None:
        sys.exit(f"element not found: {needle}")
    el, name, (x, y, w, h) = hit
    click_at(x + w / 2, y + h / 2, clicks)
    return name


def send_key(combo):
    ensure_front()
    parts = combo.lower().split("+")
    key = parts[-1]
    if key not in KEYCODES:
        sys.exit(f"unknown key: {key} (known: {', '.join(sorted(KEYCODES))})")
    flags = 0
    if "cmd" in parts:
        flags |= kCGEventFlagMaskCommand
    if "shift" in parts:
        flags |= kCGEventFlagMaskShift
    for down in (True, False):
        e = CGEventCreateKeyboardEvent(None, KEYCODES[key], down)
        if flags:
            CGEventSetFlags(e, flags)
        CGEventPost(kCGHIDEventTap, e)
        time.sleep(0.03)


def read_playhead():
    cur = find_one("currentProgress")
    tot = find_one("totalProgress")
    d = lambda h: (attr(h[0], "AXDescription") or "").split("|")[-1] if h else "?"
    return d(cur), d(tot)


# ---------------------------------------------------------------- live editing

RULER_DY = 33  # ruler row sits this far below the timeline toolbar's top edge


def parse_tc(tc, fps):
    """A player readout in seconds. A 29.97/59.94 draft (replay builds one for such footage, 2026-09-27) reads
    DROP-FRAME, '00:01:00;02': labels 0-1 (0-3 at 59.94) are skipped every minute but each tenth."""
    h, m, s, f = (int(x) for x in re.split(r"[:;.]", tc.strip()))
    if ";" in tc and round(fps) in (30, 60) and abs(fps - round(fps)) > 0.01:
        nom, drop, mins = round(fps), 2 * round(fps) // 30, 60 * h + m
        return ((3600 * h + 60 * m + s) * nom + f - drop * (mins - mins // 10)) / fps
    return h * 3600 + m * 60 + s + f / fps


def draft_fps(name=None):
    if name:
        try:
            return json.loads((DRAFT_ROOT / name / DRAFT_FILE).read_text(encoding="utf-8"))["fps"]
        except (OSError, KeyError, json.JSONDecodeError):
            pass
    return 30.0


def playhead_seconds(fps):
    cur, _ = read_playhead()
    return parse_tc(cur, fps) if cur != "?" else None


def timeline_clips():
    """Main + overlay clips, left-to-right, as (name, x, y, w, h)."""
    return sorted(((n, *g) for _, n, g in elements("MTLSVideoP") if g),
                  key=lambda c: (c[2], c[1]))


def ruler_y():
    hit = find_one("cutoff") or find_one("undo")
    if hit is None:
        sys.exit("timeline toolbar not found (is a draft open?)")
    return hit[2][1] + RULER_DY


def click_ruler(x, y=None):
    click_at(x, y if y is not None else ruler_y())
    time.sleep(0.35)


def visible_ruler_span():
    """Clickable x range of the ruler. Clip geometry alone is NOT usable: zoomed
    in, a long clip's AX box runs thousands of px off-screen in both directions
    (measured x=-2389 w=12646), so probe points derived from it land nowhere and
    the fit comes out garbage. Clamp to the timeline viewport, past the track
    headers on the left."""
    root = find_one("MainTimeLineRoot")
    if root is None:
        sys.exit("timeline not found (is a draft open?)")
    rx, _, rw, _ = root[2]
    left, right = rx + 180, rx + rw - 20
    clips = timeline_clips()
    if clips:                       # never probe past the end of the content
        right = min(right, max(c[1] + c[3] for c in clips))
        left = max(left, min(c[1] for c in clips))
    if right - left < 80:
        left, right = rx + 180, rx + rw - 20
    return left, right


def calibrate(fps):
    """Fit seconds<->pixels from the app's OWN playhead readout: click two ruler
    points and read where it landed. Self-calibrating, so it survives any zoom
    or scroll state instead of assuming the timeline origin."""
    left, right = visible_ruler_span()
    span = right - left
    xa, xb = left + span * 0.30, left + span * 0.75  # clear of the dead strip
    click_ruler(xa)
    ta = playhead_seconds(fps)
    click_ruler(xb)
    tb = playhead_seconds(fps)
    if ta is None or tb is None or abs(tb - ta) < 1e-6:
        sys.exit("calibration failed (playhead did not move) — check for a "
                 "yellow onboarding tooltip over the ruler: it swallows clicks "
                 "and is invisible to the AX tree. Run `shot` and look.")
    sec_per_px = (tb - ta) / (xb - xa)
    return lambda t: xa + (t - ta) / sec_per_px, sec_per_px


def seek(seconds, fps=30.0, tolerance_frames=0):
    """Park the playhead on an exact frame: click the mapped ruler x, then close
    the rest with arrow-key frame steps, re-reading between rounds.

    The arrow convergence is not a garnish, it is what makes this reliable. The
    ruler has a dead strip roughly 90px wide at its left edge that silently eats
    clicks (measured at two zoom levels, boundary fixed in screen space), so any
    target in the first few seconds cannot be clicked to directly — seek lands
    wherever it can and steps in. Steps must also be PACED: sent back to back
    CapCut drops most of them (195 sent, 28 applied)."""
    x_of, _ = calibrate(fps)
    click_ruler(x_of(seconds))
    for _ in range(8):
        now = playhead_seconds(fps)
        if now is None:
            break
        err = round((seconds - now) * fps)
        if abs(err) <= tolerance_frames:
            return now
        key = "right" if err > 0 else "left"
        for _ in range(min(abs(err), 400)):
            send_key(key)
            time.sleep(0.03)
        time.sleep(0.3)
    return playhead_seconds(fps)


def select_clip(index):
    clips = [c for c in timeline_clips()]
    if index >= len(clips):
        sys.exit(f"clip index {index} out of range (timeline has {len(clips)})")
    _, x, y, w, h = clips[index]
    click_at(x + w / 2, y + h / 2)
    time.sleep(0.5)
    return clips[index][0]


def window_id():
    from Quartz import (CGWindowListCopyWindowInfo, kCGNullWindowID,
                        kCGWindowListOptionOnScreenOnly)
    best = None
    for w in CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID):
        if w.get("kCGWindowOwnerName") != APP:
            continue
        b = w["kCGWindowBounds"]
        area = b["Width"] * b["Height"]
        if best is None or area > best[1]:
            best = (w["kCGWindowNumber"], area)
    return best[0] if best else None


def grab(out_path):
    """Window screenshot — the QA loop for checking a graphic actually landed."""
    wid = window_id()
    if wid is None:
        sys.exit("no CapCut window on screen")
    out = Path(out_path).expanduser().resolve()
    subprocess.run(["screencapture", "-x", "-o", "-l", str(wid), str(out)], check=True)
    return out


# ---------------------------------------------------------------- draft writing


def probe(path):
    """(display width, display height, duration µs, has_audio). DISPLAY size: a phone clip is stored landscape with a
    ±90° rotation tag (an iPhone .MOV: coded 1920x1080, shown 1080x1920), and the draft's material and canvas must
    carry the size the viewer sees."""
    out = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,duration:stream_side_data=rotation:format=duration", "-of", "json", str(path)]))
    v = next(s for s in out["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in out["streams"])
    w, h = int(v["width"]), int(v["height"])
    rot = next((int(sd.get("rotation", 0)) for sd in v.get("side_data_list", []) if "rotation" in sd), 0)
    if abs(rot) % 180 == 90:
        w, h = h, w
    # Matroska and WebM carry no per-stream duration (ffprobe leaves the key out): the container's stands in
    return w, h, int(float(v.get("duration") or out["format"]["duration"]) * 1e6), has_audio


def native_draft():
    """A draft CapCut itself wrote on this machine (the newest), for the fields a new draft must carry to read as
    native: the platform block, the format versions, function_assistant_info. None when there is none yet."""
    best = None
    for p in DRAFT_ROOT.glob(f"*/{DRAFT_FILE}"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if d.get("platform") and (best is None or p.stat().st_mtime > best[0]):
            best = (p.stat().st_mtime, d)
    return best[1] if best else None


def uid():
    return str(uuid.uuid4()).upper()


def platform_block():
    # Lift device ids from an existing local draft so the new one reads as native.
    nd = native_draft()
    if nd:
        return nd["platform"]
    if IS_WIN:
        return {"os": "windows", "os_version": W.os_version(), "app_id": 359289,
                "app_version": ".".join(W.app_version().split(".")[:3]), "app_source": "cc", "device_id": "",
                "hard_disk_id": "", "mac_address": ""}
    return {"os": "mac", "os_version": "", "app_id": 359289, "app_version": "8.9.0",
            "app_source": "cc", "device_id": "", "hard_disk_id": "", "mac_address": ""}


def video_material(mid, path, w, h, dur_us, has_audio):
    return {
        "id": mid, "unique_id": "", "type": "video", "duration": dur_us,
        "path": fold_str(path), "media_path": "", "local_id": "", "has_audio": has_audio,
        "reverse_path": "", "intensifies_path": "", "reverse_intensifies_path": "",
        "intensifies_audio_path": "", "cartoon_path": "", "width": w, "height": h,
        "category_id": "", "category_name": "", "material_id": "",
        "material_name": Path(path).name, "material_url": "",
        "crop": {"upper_left_x": 0.0, "upper_left_y": 0.0, "upper_right_x": 1.0,
                 "upper_right_y": 0.0, "lower_left_x": 0.0, "lower_left_y": 1.0,
                 "lower_right_x": 1.0, "lower_right_y": 1.0},
        "crop_ratio": "free", "audio_fade": None, "crop_scale": 1.0,
        "extra_type_option": 0,
        "stable": {"stable_level": 0, "matrix_path": "",
                   "time_range": {"start": 0, "duration": 0}},
        "matting": {"flag": 0, "path": "", "interactiveTime": [],
                    "has_use_quick_brush": False, "strokes": [],
                    "has_use_quick_eraser": False, "expansion": 0, "feather": 0,
                    "reverse": False, "custom_matting_id": "",
                    "enable_matting_stroke": False, "is_clould": False,
                    "mask_video_path": "", "cloud_product_fps": 0.0},
        "source": 0, "source_platform": 0, "formula_id": "", "check_flag": 62978047,
        "video_algorithm": {"algorithms": [], "time_range": None, "path": "",
                            "gameplay_configs": [], "ai_in_painting_config": [],
                            "complement_frame_config": None, "motion_blur_config": None,
                            "deflicker": None, "noise_reduction": None,
                            "quality_enhance": None, "super_resolution": None,
                            "ai_background_configs": [], "smart_complement_frame": None,
                            "aigc_generate": None, "aigc_generate_list": [],
                            "mouth_shape_driver": None, "ai_expression_driven": None,
                            "ai_motion_driven": None, "image_interpretation": None,
                            "story_video_modify_video_config": {
                                "task_id": "", "is_overwrite_last_video": False,
                                "tracker_task_id": "", "generate_id": "",
                                "generate_card_id": ""},
                            "skip_algorithm_index": []},
        "is_unified_beauty_mode": False, "is_set_beauty_mode": False,
        "object_locked": None, "smart_motion": None, "multi_camera_info": None,
        "freeze": None, "picture_from": "none", "picture_set_category_id": "",
        "picture_set_category_name": "", "team_id": "", "local_material_id": "",
        "origin_material_id": "", "request_id": "", "has_sound_separated": False,
        "is_text_edit_overdub": False, "is_ai_generate_content": False,
        "aigc_type": "none", "is_copyright": False, "aigc_history_id": "",
        "aigc_item_id": "", "local_material_from": "", "smart_match_info": None,
        "beauty_face_preset_infos": [], "beauty_body_preset_id": "",
        "beauty_face_auto_preset": {"preset_id": "", "name": "", "rate_map": "",
                                    "scene": ""},
        "beauty_face_auto_preset_infos": [], "beauty_body_auto_preset": None,
        "live_photo_timestamp": -1, "live_photo_cover_path": "",
        "content_feature_info": None, "corner_pin": None, "surface_trackings": [],
        "video_mask_stroke": {"resource_id": "", "path": "", "type": "", "color": "",
                              "size": 0.0, "alpha": 0.0, "distance": 0.0,
                              "texture": 0.0, "horizontal_shift": 0.0,
                              "vertical_shift": 0.0},
        "video_mask_shadow": {"resource_id": "", "path": "", "color": "",
                              "alpha": 0.0, "blur": 0.0, "distance": 0.0,
                              "angle": 0.0},
    }


def segment(mid, src_start, dur, tgt_start, refs):
    return {
        "id": uid(),
        "source_timerange": {"start": src_start, "duration": dur},
        "target_timerange": {"start": tgt_start, "duration": dur},
        "render_timerange": {"start": 0, "duration": 0},
        "desc": "", "state": 0, "speed": 1.0, "is_loop": False,
        "is_tone_modify": False, "reverse": False, "intensifies_audio": False,
        "cartoon": False, "volume": 1.0, "last_nonzero_volume": 1.0,
        "clip": {"scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                 "transform": {"x": 0.0, "y": 0.0},
                 "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0},
        "uniform_scale": {"on": True, "value": 1.0},
        "material_id": mid, "extra_material_refs": refs, "render_index": 0,
        "keyframe_refs": [], "enable_lut": True, "enable_adjust": True,
        "enable_hsl": False, "visible": True, "group_id": "",
        "enable_color_curves": True, "enable_hsl_curves": True,
        "track_render_index": 0,
        "hdr_settings": {"mode": 1, "intensity": 1.0, "nits": 1000},
        "enable_color_wheels": True, "track_attribute": 0, "is_placeholder": False,
        "template_id": "", "enable_smart_color_adjust": False,
        "template_scene": "default", "common_keyframes": [], "caption_info": None,
        "responsive_layout": {"enable": False, "target_follow": "",
                              "size_layout": 0, "horizontal_pos_layout": 0,
                              "vertical_pos_layout": 0},
        "enable_color_match_adjust": False, "enable_color_correct_adjust": False,
        "enable_adjust_mask": False, "raw_segment_id": "", "lyric_keyframes": None,
        "enable_video_mask": True, "digital_human_template_group_id": "",
        "color_correct_alg_result": "", "source": "segmentsourcenormal",
        "enable_mask_stroke": False, "enable_mask_shadow": False,
        "enable_color_adjust_pro": False,
    }


def segment_extras(materials):
    """Per-segment helper materials, the six-ref set CapCut itself writes."""
    ids = []
    for cat, entry in [
        ("speeds", {"type": "speed", "mode": 0, "speed": 1.0, "curve_speed": None}),
        ("placeholder_infos", {"type": "placeholder_info", "meta_type": "none",
                               "res_path": "", "res_text": "", "error_path": "",
                               "error_text": ""}),
        ("canvases", {"type": "canvas_color", "color": "", "blur": 0.0, "image": "",
                      "album_image": "", "image_id": "", "image_name": "",
                      "source_platform": 0, "team_id": ""}),
        ("sound_channel_mappings", {"type": "", "audio_channel_mapping": 0,
                                    "is_config_open": False}),
        ("material_colors", {"is_color_clip": False, "is_gradient": False,
                             "solid_color": "", "gradient_colors": [],
                             "gradient_percents": [], "gradient_angle": 90.0,
                             "width": 0.0, "height": 0.0}),
        ("vocal_separations", {"type": "vocal_separation", "choice": 0,
                               "removed_sounds": [], "time_range": None,
                               "production_path": "", "final_algorithm": "",
                               "enter_from": ""}),
    ]:
        eid = uid()
        materials[cat].append({"id": eid, **entry})
        ids.append(eid)
    return ids


EMPTY_MATERIAL_CATS = [
    "flowers", "tail_leaders", "audios", "images", "texts", "effects", "stickers",
    "transitions", "audio_effects", "audio_fades", "beats", "material_animations",
    "placeholders", "common_mask", "chromas", "text_templates", "realtime_denoises",
    "audio_pannings", "audio_pitch_shifts", "video_trackings", "hsl", "drafts",
    "color_curves", "hsl_curves", "primary_color_wheels", "log_color_wheels",
    "video_effects", "ai_text_effects", "audio_balances", "handwrites",
    "manual_deformations", "manual_beautys", "plugin_effects", "green_screens",
    "shapes", "digital_humans", "digital_human_model_dressing", "smart_crops",
    "ai_translates", "audio_track_indexes", "loudnesses", "vocal_beautifys",
    "smart_relights", "time_marks", "multi_language_refs", "video_shadows",
    "video_strokes", "video_radius", "videos", "canvases", "speeds",
    "placeholder_infos", "sound_channel_mappings", "material_colors",
    "vocal_separations",
]


def off_grid_warning(segs, fps, tol=0.001):
    """The EDL boundaries off the timeline's frame grid, which build_draft lays on the nearest frame (L11, 2026-09-27;
    the Premiere replay's offGridWarning, bridge-lib.mjs): the laid cut then runs up to that far from cuts.json, and
    so does everything timed from it. None when every boundary is on the grid (splice.sh writes them there)."""
    fr = exact_fps(fps)
    off, edl, laid, drift = [], 0.0, 0.0, 0.0
    for i, s in enumerate(segs):
        for k in ("start", "end"):
            t = float(s[k])
            q = round(t * fr) / fr
            if abs(t - q) > tol:
                off.append(f"  #{i} {k} {t:.5f} is laid at {q:.5f} ({(q - t) * fr:.2f} frame)")
        edl += float(s["end"]) - float(s["start"])
        laid += (round(float(s["end"]) * fr) - round(float(s["start"]) * fr)) / fr
        drift = max(drift, abs(edl - laid) * fr)
    if not off:
        return None
    return (f"⚠ replay: {len(off)} EDL boundar{'y is' if len(off) == 1 else 'ies are'} off the {fr:.3f} fps frame grid, "
            f"each laid on the nearest frame, so the cut in the draft runs up to {drift:.2f} frame(s) from cuts.json:\n"
            + "\n".join(off) + "\n  Put those boundaries on the grid in cuts.json (the values above) and re-export the "
            "transcript before a plan is timed from it.")


def build_draft(name, clips, cuts, canvas_w, canvas_h, fps=30.0):
    """The draft for an EDL whose segments may come from several raws: `clips` maps each segment's `clip` to its
    local (hardlinked) path. Each raw is probed once and gets ONE video material; every segment points at its own
    clip's material. `fps` is the timeline's rate, the footage's (replay reads it). Returns (draft, first clip's
    duration, width, height) for the meta entry and cover."""
    plat = platform_block()
    materials = {cat: [] for cat in EMPTY_MATERIAL_CATS}
    mids, first = {}, None
    for clip, path in clips.items():
        w, h, dur_us, has_audio = probe(path)
        mids[clip] = uid()
        materials["videos"].append(video_material(mids[clip], path, w, h, dur_us, has_audio))
        if first is None:
            first = (dur_us, w, h)

    # every time on the TIMELINE's frame grid, in CapCut's own arithmetic: a frame count, converted to µs and floored
    # (a 29.97 draft CapCut saved itself holds 126 frames as 4204200 and source frame 1021 as 34067366)
    fr = exact_fps(fps)
    us = lambda n: int(n * 1e6 / fr)
    segments = []
    cursor_f = 0
    for s in cuts["segments"]:
        f0, f1 = round(s["start"] * fr), round(s["end"] * fr)
        segments.append(segment(mids[s["clip"]], us(f0), us(f1 - f0), us(cursor_f), segment_extras(materials)))
        cursor_f += f1 - f0
    cursor = us(cursor_f)

    nd = native_draft() or {}
    extra = {}
    if IS_WIN:
        # fields CapCut 9.5 on Windows writes and 8.9 on macOS did not (the native draft's own, else neutral values)
        extra["function_assistant_info"] = nd.get("function_assistant_info") or {
            "smart_rec_applied": False, "fixed_rec_applied": False, "auto_adjust": False, "auto_adjust_segid_list": [],
            "color_correction": False, "color_correction_segid_list": [], "enhance_quality": False,
            "smooth_slow_motion": False, "deflicker_segid_list": [], "video_noise_segid_list": []}
    draft = {
        "id": uid(), "version": nd.get("version", 360000), "new_version": nd.get("new_version", "175.0.0"), "name": "",
        # the timeline's frame rate is the footage's: CapCut stores 29.97 as the EXACT 30000/1001 with drop-frame
        # timecode (a rounded 29.97 without the flag came back 30.0 after its own save, 2026-09-27), and changing it
        # in the app keeps each clip's FRAME COUNT, so every cut slides: it has to be right when the draft is built
        "duration": cursor, "create_time": 0, "update_time": 0, "fps": fr,
        "is_drop_frame_timecode": fr in (30000 / 1001, 60000 / 1001), "color_space": 0,
        "config": {"video_mute": False, "record_audio_last_index": 1,
                   "extract_audio_last_index": 1, "original_sound_last_index": 1,
                   "subtitle_recognition_id": "", "subtitle_taskinfo": [],
                   "lyrics_recognition_id": "", "lyrics_taskinfo": [],
                   "subtitle_sync": True, "lyrics_sync": True,
                   "voice_change_sync": False, "sticker_max_index": 1,
                   "adjust_max_index": 1, "material_save_mode": 0,
                   "export_range": None, "maintrack_adsorb": True,
                   "combination_max_index": 1, "attachment_info": [],
                   "zoom_info_params": None, "system_font_list": [],
                   "multi_language_mode": "none", "multi_language_main": "none",
                   "multi_language_current": "none", "multi_language_list": [],
                   "subtitle_keywords_config": None, "use_float_render": False},
        "canvas_config": {"ratio": "original", "width": canvas_w,
                          "height": canvas_h, "background": None},
        "tracks": [{"id": uid(), "type": "video", "segments": segments,
                    "flag": 0, "attribute": 0, "name": "", "is_default_name": True}],
        "group_container": None, "materials": materials,
        "keyframes": {"videos": [], "audios": [], "texts": [], "stickers": [],
                      "filters": [], "adjusts": [], "handwrites": [], "effects": []},
        "keyframe_graph_list": [], "platform": plat,
        "last_modified_platform": plat, "mutable_config": None, "cover": None,
        "retouch_cover": None, "extra_info": None, "relationships": [],
        "mixed_track_mode_on": False, "render_index_track_mode_on": True,
        "free_render_index_mode_on": False, "static_cover_image_path": "",
        "source": "default", "time_marks": None, "path": "", "lyrics_effects": [],
        "uneven_animation_template_info": {"composition": "", "content": "",
                                           "order": "", "sub_template_info_list": []},
        "draft_type": "video",
        "smart_ads_info": {"page_from": "", "routine": "", "draft_url": ""},
        **extra,
    }
    if IS_WIN:
        draft["config"]["hdr_vivid"] = False
    return draft, first[0], first[1], first[2]


def meta_entry(name, folder, draft_id, media, total_us, now_us):
    """`media` = [(path, duration_us, width, height)], one per raw: CapCut's Media panel lists exactly these
    `draft_materials` type-0 rows, so a raw missing here plays on the timeline but is absent from the bin."""
    now_s = now_us // 1_000_000
    return {
        "cloud_draft_cover": False, "cloud_draft_sync": False,
        "cloud_package_completed_time": "", "draft_cloud_capcut_purchase_info": "",
        "draft_cloud_last_action_download": False, "draft_cloud_package_type": "",
        "draft_cloud_purchase_info": "", "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "", "draft_cloud_videocut_purchase_info": "",
        "draft_cover": "draft_cover.jpg", "draft_deeplink_url": "",
        "draft_enterprise_info": {"draft_enterprise_extra": "",
                                  "draft_enterprise_id": "",
                                  "draft_enterprise_name": "",
                                  "enterprise_material": []},
        "draft_fold_path": fold_str(folder), "draft_id": draft_id,
        "draft_has_unfinished_aigc_video_effect": False, "draft_is_infinite_canvas_draft": False,
        "draft_is_ae_produce": False, "draft_is_ai_packaging_used": False,
        "draft_is_ai_shorts": False, "draft_is_ai_translate": False,
        "draft_is_article_video_draft": False, "draft_is_cloud_temp_draft": False,
        "draft_is_from_deeplink": "false", "draft_is_invisible": False,
        "draft_is_pippit_draft": False, "draft_is_web_article_video": False,
        "draft_materials": [
            {"type": 0, "value": [{
                "ai_group_type": "", "create_time": now_s, "duration": raw_dur_us,
                "enter_from": 0, "extra_info": Path(raw_path).name,
                "file_Path": fold_str(raw_path), "height": h, "material_color_tag": "",
                "id": str(uuid.uuid4()), "import_time": now_s,
                "import_time_ms": now_us, "item_source": 1, "md5": "",
                "metetype": "video",
                "roughcut_time_range": {"duration": raw_dur_us, "start": 0},
                "sub_time_range": {"duration": -1, "start": -1},
                "type": 0, "width": w} for raw_path, raw_dur_us, w, h in media]},
            {"type": 1, "value": []}, {"type": 2, "value": []},
            {"type": 3, "value": []}, {"type": 6, "value": []},
            {"type": 7, "value": []},
        ] + ([{"type": 8, "value": []}] if IS_WIN else []),
        "draft_materials_copied_info": [], "draft_name": name,
        "draft_need_rename_folder": False, "draft_new_version": "",
        "draft_removable_storage_device": "", "draft_root_path": str(DRAFT_ROOT),
        "draft_segment_extra_info": [], "draft_timeline_materials_size_": 0,
        "draft_type": "", "draft_web_article_video_enter_from": "",
        "pippit_avatar_url": "", "pippit_extra_info": "", "pippit_id": "",
        "pippit_user_name": "", "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1, "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1, "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1, "tm_draft_create": now_us,
        "tm_draft_modified": now_us, "tm_draft_removed": 0,
        "tm_duration": total_us,
    }


def registry_entry(name, folder, draft_id, total_us, now_us):
    return {
        "cloud_draft_cover": False, "cloud_draft_sync": False,
        "draft_cloud_last_action_download": False, "draft_cloud_purchase_info": "",
        "draft_cloud_template_id": "", "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": file_in_fold(folder, "draft_cover.jpg"),
        "draft_fold_path": fold_str(folder), "draft_id": draft_id,
        "draft_is_ai_shorts": False, "draft_is_cloud_temp_draft": False,
        "draft_is_infinite_canvas_draft": False,
        "draft_is_invisible": False, "draft_is_pippit_draft": False,
        "draft_is_web_article_video": False,
        "draft_json_file": file_in_fold(folder, DRAFT_FILE), "draft_name": name,
        "draft_new_version": "", "draft_root_path": str(DRAFT_ROOT),
        "draft_timeline_materials_size": 0, "draft_type": "",
        "draft_web_article_video_enter_from": "", "pippit_avatar_url": "",
        "pippit_extra_info": "", "pippit_id": "", "pippit_user_name": "",
        "streaming_edit_draft_ready": True, "tm_draft_cloud_completed": "",
        "tm_draft_cloud_entry_id": -1, "tm_draft_cloud_modified": 0,
        "tm_draft_cloud_parent_entry_id": -1, "tm_draft_cloud_space_id": -1,
        "tm_draft_cloud_user_id": -1, "tm_draft_create": now_us,
        "tm_draft_modified": now_us, "tm_draft_removed": 0,
        "tm_duration": total_us,
    }


def job_dir(job):
    """A job name (projects/<job>) or a job folder path."""
    p = Path(job).expanduser()
    if ("/" in job or os.sep in job) and p.is_dir():
        return p.resolve()
    return Path(__file__).resolve().parent.parent.parent / "projects" / job


def media_refusal(segs):
    """The Premiere replay's refusal (lanes/premiere/bridge-lib.mjs mediaRefusal), word for word in shape: a segment
    carrying `media` was laid from another file, so the raw this replay would lay is not what is on the cut."""
    hits = [(i, s) for i, s in enumerate(segs or []) if s and s.get("media")]
    if not hits:
        return None
    return (f'replay: refused, nothing laid: {len(hits)} segment(s) carry "media", so the raw clip this replay would '
            f'lay is NOT what is on the cut:\n'
            + "\n".join(f'  #{i} {float(s["start"]):.3f}-{float(s["end"]):.3f} ({s.get("clip") or "the CLI clip"}) '
                        f'was laid from {s["media"]}' for i, s in hits)
            + "\n  Replay an EDL without those segments, then lay each one by hand from its media file.")


CAPCUT_FPS = (24.0, 25.0, 29.97, 30.0, 50.0, 59.94, 60.0)   # Project settings > Frame rate (no 23.976 there)


def grid_us(d, seconds):
    """A time in µs on the draft's own frame grid, CapCut's arithmetic (frame count, floored µs)."""
    fr = exact_fps(d.get("fps") or 30.0)
    return int(round(seconds * fr) * 1e6 / fr)


def exact_fps(f):
    """A CapCut list rate as the value CapCut itself writes: the NTSC rates exact (30000/1001), the rest as is."""
    for n in (24000, 30000, 60000):
        if abs(f - n / 1001) < 0.01:
            return n / 1001
    return float(f)


def source_fps(path):
    """The footage's frame rate on CapCut's export list. CapCut's export dialog defaults to 30 fps whatever the source,
    so a 29.97 take came out at 30 (2026-09-27): export picks this instead. The NOMINAL rate (r_frame_rate) when it is
    on the list, the lanes' own choice for an iPhone VFR take (r 30000/1001, avg 29.988, which rounds to 30: the
    Premiere and chat-only finals of the same job ship at 29.97); the average only when the nominal rate is not."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=avg_frame_rate,r_frame_rate", "-of", "json", str(path)], capture_output=True, text=True)
    try:
        st = json.loads(r.stdout)["streams"][0]
    except (ValueError, KeyError, IndexError):
        return None
    rates = []
    for k in ("r_frame_rate", "avg_frame_rate"):
        try:
            n, d = st[k].split("/")
            rates.append(float(n) / float(d))
        except (KeyError, ValueError, ZeroDivisionError):
            pass
    for f in rates:
        near = min(CAPCUT_FPS, key=lambda c: abs(c - f))
        if abs(near - f) < 0.01:
            return near
    return min(CAPCUT_FPS, key=lambda c: abs(c - rates[-1])) if rates else None


def nominal_fps(path):
    """The footage's own nominal rate (ffprobe r_frame_rate) as a float, or None."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    # the first row: ffprobe 9 prints a timecoded file's video row twice (its tmcd stream group, then the stream),
    # and '30000/1001\n\n30000/1001' read whole made this None on every camera raw that carries timecode (2026-10-13)
    n, _, d = next((l for l in r.stdout.splitlines() if l.strip()), "").strip().partition("/")
    try:
        return float(n) / float(d or 1)
    except ValueError:
        return None


def grid_note(segs, fps, nominal):
    """What the replay says about where the EDL's boundaries land. When CapCut has a timeline at the footage's own rate
    the off-grid check runs (L11); when it has none (23.976: its list stops at 24) EVERY boundary sits between draft
    frames by construction, and the EDL must stay on the footage's grid for every other lane, so one note says so
    instead of asking for cuts.json to move (review, 2026-09-27)."""
    if nominal and abs(nominal - exact_fps(fps)) > 0.01:
        return (f"⚠ CapCut has no {nominal:.3f} fps timeline, so the draft runs at {exact_fps(fps):.3f}: each cut is laid on "
                f"the nearest draft frame, up to half a frame from the EDL. cuts.json stays on the footage's grid; do not "
                f"move it to the draft's.")
    return off_grid_warning(segs, fps)


def cmd_replay(job, draft_name=None, media=None):
    jobdir = job_dir(job)
    cuts_path = jobdir / "transcript" / "cuts.json"
    if not cuts_path.exists():
        sys.exit(f"no EDL at {cuts_path}, run rough-cut (RENDER=0) first")
    cuts = json.loads(cuts_path.read_text(encoding="utf-8"))
    refusal = media_refusal(cuts["segments"])
    if refusal:
        sys.exit(refusal)
    raws = {}
    for s in cuts["segments"]:
        raws.setdefault(s["clip"], jobdir / "raw" / s["clip"])
    # --media: the same take(s) with the audio chain baked in (the step-3 recipe, capcut SKILL.md § Step 3:
    # workflows/normalize-sections.sh writes audio-normalized/<clip>), so the draft is built on polished audio. A
    # folder stands in for every clip by name; a file for the one clip of a single-raw EDL
    if media:
        m = Path(media).expanduser().resolve()
        if m.is_dir():
            raws = {c: m / c for c in raws}
        elif len(raws) == 1:
            raws = {c: m for c in raws}
        else:
            sys.exit(f"--media {media}: this EDL cuts {len(raws)} raws; pass the folder holding each one's polished copy")
    missing = [str(p) for p in raws.values() if not p.exists()]
    if missing:
        sys.exit("raw footage missing, nothing laid: " + ", ".join(missing))
    name = draft_name or jobdir.name
    folder = DRAFT_ROOT / name
    if folder.exists():
        sys.exit(f"draft folder already exists: {folder} (pick another --name)")

    # every raw is read BEFORE CapCut is quit and the draft folder made: a probe that failed after both (an .mkv raw,
    # 2026-10-13) left CapCut closed and a dead folder that refused every re-run
    for p in raws.values():
        try:
            probe(p)
        except (subprocess.CalledProcessError, StopIteration, KeyError, TypeError, ValueError) as e:
            sys.exit(f"raw unreadable, nothing laid: {p} ({type(e).__name__})")
    raw = raws[cuts["segments"][0]["clip"]]

    # the canvas follows the footage's DISPLAY orientation: a vertical short is a vertical draft (a 1920x1080 canvas
    # pillarboxed every vertical job, 2026-09-27); a 4K vertical take gets the 2160x3840 canvas its Shorts file needs
    rw, rh, _, _ = probe(raw)
    canvas = ((2160, 3840) if rw >= 2160 else (1080, 1920)) if rh > rw else (1920, 1080)
    fps = source_fps(raw) or 30.0
    warn = grid_note(cuts["segments"], fps, nominal_fps(raw))
    if warn:
        print(warn)

    was_running = app_pid() is not None
    if was_running:
        print("quitting CapCut (registry is rewritten on quit)...")
        quit_app()

    try:
        folder.mkdir(parents=True)
        (folder / "Resources").mkdir()
        # CapCut is sandboxed with only assets.movies.read-write: it cannot read repo
        # paths it was never handed, so every raw must live under ~/Movies. Hardlink
        # (same APFS volume, zero bytes) into the draft folder; copy if that fails.
        clips = {clip: local_media(folder, p) for clip, p in raws.items()}
        draft = build_draft(name, clips, cuts, *canvas, fps=fps)[0]
        now_us = time.time_ns() // 1000
        draft_id = uid()
        (folder / DRAFT_FILE).write_text(
            json.dumps(draft, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        bin_media = []
        for path in clips.values():
            mw, mh, mdur, _ = probe(path)
            bin_media.append((path, mdur, mw, mh))
        (folder / "draft_meta_info.json").write_text(json.dumps(
            meta_entry(name, folder, draft_id, bin_media, draft["duration"], now_us),
            ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        subprocess.run(  # home-screen tile cover, first kept frame; cosmetic only
            ["ffmpeg", "-v", "error", "-ss", str(cuts["segments"][0]["start"]),
             "-i", str(raw), "-frames:v", "1", "-vf", "scale=480:-2",
             str(folder / "draft_cover.jpg")], check=False)

        root_path = DRAFT_ROOT / "root_meta_info.json"
        root = json.loads(root_path.read_text(encoding="utf-8"))
        root["all_draft_store"].insert(
            0, registry_entry(name, folder, draft_id, draft["duration"], now_us))
        root["draft_ids"] = root.get("draft_ids", 0) + 1
        root_path.write_text(json.dumps(root, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    except BaseException:
        # a write that fails half way leaves nothing behind (the folder it made would refuse every re-run) and
        # CapCut as it was found
        shutil.rmtree(folder, ignore_errors=True)
        if was_running:
            launch_app()
        raise

    n = len(cuts["segments"])
    print(f"draft '{name}': {n} segments from {len(clips)} clip(s), {draft['duration'] / 1e6:.2f}s, {folder}")
    if was_running:
        launch_app()
        print("CapCut relaunched")


TEMPLATES = Path(__file__).resolve().parent / "capcut-templates"
REPO = Path(__file__).resolve().parents[2]


def edit_draft(name, mutate, reopen=True):
    """Additive file-lane edit of an EXISTING draft. Loads the draft as it stands
    (so hand edits made in the app, saved on quit, are preserved and built upon), applies
    mutate(draft, folder), then wipes the Timelines/ native cache — CapCut only
    imports draft_info.json when that cache is absent, otherwise it silently
    keeps its own state and the edit vanishes."""
    folder = DRAFT_ROOT / name
    if not folder.exists():
        sys.exit(f"no such draft: {name}")
    was_running = app_pid() is not None
    quit_app()

    d = json.loads((folder / DRAFT_FILE).read_text(encoding="utf-8"))
    mutate(d, folder)
    # CapCut's own save normalizes text segments to source_timerange: null. That
    # is fine while IT owns the timeline state, but we wipe Timelines/ below to
    # force a re-import, and a null survives into the reimported draft. Give
    # every segment a real source range so the importer never sees one.
    for t in d["tracks"]:
        for s in t["segments"]:
            if s.get("source_timerange") is None:
                s["source_timerange"] = {"start": 0,
                                         "duration": s["target_timerange"]["duration"]}
    d["duration"] = max((s["target_timerange"]["start"] + s["target_timerange"]["duration"]
                         for t in d["tracks"] for s in t["segments"]), default=0)
    (folder / DRAFT_FILE).write_text(
        json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (folder / (DRAFT_FILE + ".bak")).unlink(missing_ok=True)
    shutil.rmtree(folder / "Timelines", ignore_errors=True)

    if was_running:
        launch_app()
        if reopen:
            time.sleep(8)
            cmd_open(name)
    return d


def local_media(folder, src):
    """CapCut's sandbox only grants ~/Movies, so media must live under the draft."""
    src = Path(src).expanduser().resolve()
    if not src.exists():
        sys.exit(f"media not found: {src}")
    dst = folder / "Resources" / src.name
    if not dst.exists():
        dst.parent.mkdir(exist_ok=True)
        try:
            dst.hardlink_to(src)
        except OSError:
            shutil.copy2(src, dst)
    return dst


def cmd_sfx_pack(name, dry=False):
    """The whole SFX pack (workflows/sfx-plan.py pack_files(): every audio file under assets/sfx) into the draft's Media
    panel, for hand placing ("throw in all of the sound effects into the media bin", Office Hours 2026-10-13). The
    panel lists the draft_meta_info.json `draft_materials` type-0 rows (meta_entry), and the sandbox reads only what
    sits under ~/Movies, so each file is hardlinked into the draft's Resources/sfx/ (copied across volumes, about
    150 MB) and gets one type-0 row, metetype "music"; a file already listed (that copy, or the pack file itself) is
    skipped. The timeline (draft_info.json) is not touched. The app is quit around the write and relaunched when it
    was running, like every file-lane edit. Unproven on a live CapCut: if the panel does not list them, Import the
    folder by hand (capcut skill § Step 6)."""
    import importlib.util
    folder = DRAFT_ROOT / name
    if not folder.exists():
        sys.exit(f"no such draft: {name}")
    spec = importlib.util.spec_from_file_location("sfx_plan", REPO / "workflows" / "sfx-plan.py")
    planner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner)
    files = planner.pack_files()
    if not files:
        sys.exit("no audio files under assets/sfx: nothing to load")
    mp = folder / "draft_meta_info.json"
    meta = json.loads(mp.read_text(encoding="utf-8"))
    group = next((g for g in meta.get("draft_materials", []) if g.get("type") == 0), None)
    listed = {v.get("file_Path") for v in (group or {}).get("value", [])}
    todo = []
    for sub, src in files:
        dst = folder / "Resources" / planner.PACK_BIN / sub / Path(src).name
        if fold_str(dst) not in listed and fold_str(src) not in listed:
            todo.append((src, dst))
    print(f"draft '{name}': {len(files)} pack file(s), {len(files) - len(todo)} already in its Media panel, "
          f"{len(todo)} to load" + (" (--dry: nothing touched)" if dry else ""))
    if dry or not todo:
        return
    was_running = app_pid() is not None
    quit_app()
    if group is None:
        group = {"type": 0, "value": []}
        meta.setdefault("draft_materials", []).insert(0, group)
    now_us = time.time_ns() // 1000
    for src, dst in todo:
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                dst.hardlink_to(src)
            except OSError:
                shutil.copy2(src, dst)
        dur_us = int(float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(dst)],
            text=True).strip().split("\n")[0].strip(",") or 0) * 1e6)
        group["value"].append({
            "ai_group_type": "", "create_time": now_us // 1_000_000, "duration": dur_us, "enter_from": 0,
            "extra_info": dst.name, "file_Path": fold_str(dst), "height": 0, "material_color_tag": "",
            "id": str(uuid.uuid4()), "import_time": now_us // 1_000_000, "import_time_ms": now_us, "item_source": 1,
            "md5": "", "metetype": "music", "roughcut_time_range": {"duration": dur_us, "start": 0},
            "sub_time_range": {"duration": -1, "start": -1}, "type": 0, "width": 0})
    mp.write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    back = json.loads(mp.read_text(encoding="utf-8"))
    rows = {v.get("file_Path") for g in back.get("draft_materials", []) if g.get("type") == 0 for v in g.get("value", [])}
    lost = [str(dst) for _, dst in todo if fold_str(dst) not in rows or not dst.exists()]
    print(f"loaded {len(todo) - len(lost)} into {folder / 'Resources' / planner.PACK_BIN}; the timeline untouched")
    for p in lost:
        print(f"✗ not loaded: {p}")
    if was_running:
        launch_app()
        print("CapCut relaunched")
    if lost:
        sys.exit(1)


def overlay_track(d, level):
    """Video overlay tracks are flag=2; level maps to render_index (1 = first
    layer above the main track)."""
    existing = [t for t in d["tracks"] if t["type"] == "video" and t["flag"] == 2]
    if len(existing) >= level:
        return existing[level - 1]
    t = {"id": uid(), "type": "video", "segments": [], "flag": 2,
         "attribute": 0, "name": "", "is_default_name": True}
    d["tracks"].append(t)
    return t


def add_overlay(name, media, at, level=1, duration=None, force=False,
                src=0.0, render_index=None, mute=False):
    """Place an alpha graphic (ProRes 4444 .mov) over the cut — the step-5
    graphics move, validated 2026-07-27.

    `src` takes a source in-point, so a slice of the raw can be re-laid above the
    main track (the cutout copy in the text-behind-subject build). `render_index`
    overrides the layer-derived z-order: CapCut reserves a high band for text
    (14000+), so a video layer only composites ABOVE text with an explicit index
    past it. `mute` is mandatory on a duplicate of footage already on the main
    track — an overlay segment plays its own audio and would double the voice."""
    def mutate(d, folder):
        if not force and already_at(d, round(at * 1e6), media_name=Path(media).name):
            sys.exit(f"{Path(media).name} is already at {at}s — pass --force to add a second copy")
        path = local_media(folder, media)
        w, h, dur_us, has_audio = probe(path)
        mid = uid()
        d["materials"]["videos"].append(
            video_material(mid, path, w, h, dur_us, has_audio))
        use = grid_us(d, duration) if duration else dur_us
        seg = segment(mid, grid_us(d, src), use, grid_us(d, at),
                      segment_extras(d["materials"]))
        ri = level if render_index is None else render_index
        seg["render_index"] = ri
        seg["track_render_index"] = level
        if mute:
            seg["volume"] = 0.0
            seg["last_nonzero_volume"] = 0.0
        overlay_track(d, level)["segments"].append(seg)
    edit_draft(name, mutate)
    print(f"overlay: {Path(media).name} at {at:.2f}s on layer {level}"
          f"{'' if render_index is None else f' (render_index {render_index})'}")


def add_text(name, text, at, duration=3.0, level=1, force=False,
             render_index=None):
    """Text graphic built from a template lifted from a real CapCut draft — the
    `content` field is JSON-in-JSON carrying the style run, so the styled range
    must be re-pointed at the new string or CapCut renders it unstyled."""
    tm_path, seg_path = TEMPLATES / "text-material.json", TEMPLATES / "text-segment.json"
    anim_path = TEMPLATES / "text-ref-material_animations.json"
    if not tm_path.exists():
        sys.exit(f"missing text template: {tm_path}")

    def mutate(d, folder):
        if not force and already_at(d, round(at * 1e6), text=text):
            sys.exit(f"{text!r} is already at {at}s — pass --force to add a second copy")
        tm = json.loads(tm_path.read_text(encoding="utf-8"))
        content = json.loads(tm["content"])
        content["text"] = text
        for style in content.get("styles", []):
            style["range"] = [0, len(text)]
        tm["id"] = uid()
        tm["content"] = json.dumps(content, ensure_ascii=False)
        d["materials"]["texts"].append(tm)

        anim = json.loads(anim_path.read_text(encoding="utf-8"))
        anim["id"] = uid()
        d["materials"]["material_animations"].append(anim)

        seg = json.loads(seg_path.read_text(encoding="utf-8"))
        seg["id"] = uid()
        seg["material_id"] = tm["id"]
        seg["extra_material_refs"] = [anim["id"]]
        seg["source_timerange"] = {"start": 0, "duration": grid_us(d, duration)}
        seg["target_timerange"] = {"start": grid_us(d, at),
                                   "duration": grid_us(d, duration)}
        if render_index is not None:
            seg["render_index"] = render_index
        track = next((t for t in d["tracks"] if t["type"] == "text"), None)
        if track is None:
            track = {"id": uid(), "type": "text", "segments": [], "flag": 1,
                     "attribute": 0, "name": "", "is_default_name": True}
            d["tracks"].append(track)
        track["segments"].append(seg)
    edit_draft(name, mutate)
    print(f"text: {text!r} at {at:.2f}s for {duration:.2f}s")


def remove_segment(name, track_role, index):
    """Drop a segment and any material it alone referenced. The file-lane
    counterpart to the live `delete` — use this for precise/batch removal."""
    flag = {"main": 0, "text": 1, "overlay": 2}[track_role]

    def mutate(d, folder):
        # Index runs across every track of this role: CapCut splits overlapping
        # segments onto separate tracks, so "text[1]" is not always track 1.
        flat = [(t, i) for t in d["tracks"] if t["flag"] == flag
                for i in range(len(t["segments"]))]
        if index >= len(flat):
            sys.exit(f"only {len(flat)} {track_role} segment(s), no index {index}")
        track, local = flat[index]
        seg = track["segments"].pop(local)
        still_used = {s["material_id"] for t in d["tracks"] for s in t["segments"]}
        for cat in ("videos", "texts"):
            d["materials"][cat] = [m for m in d["materials"][cat]
                                   if m["id"] in still_used]
        if not track["segments"] and flag != 0:
            d["tracks"].remove(track)
    edit_draft(name, mutate)
    print(f"removed {track_role}[{index}]")


def already_at(d, start_us, text=None, media_name=None):
    """Guard against double-applying: an interrupted file-lane run may have
    already written its edit before the app relaunch was cut short."""
    for t in d["tracks"]:
        for s in t["segments"]:
            if abs(s["target_timerange"]["start"] - start_us) > 16000:   # half a frame: grid snapping and CapCut's
                continue                                                  # own save move a start by µs
            if text is not None:
                m = next((m for m in d["materials"]["texts"]
                          if m["id"] == s["material_id"]), None)
                if m and json.loads(m["content"]).get("text") == text:
                    return True
            if media_name is not None:
                m = next((m for m in d["materials"]["videos"]
                          if m["id"] == s["material_id"]), None)
                if m and m["material_name"] == media_name:
                    return True
    return False


def set_transform(name, track_role, index, **vals):
    """Exact scale/position/rotation/opacity on one segment. This is FILE-lane on
    purpose: the inspector's QML text fields take focus but ignore synthesized
    keystrokes (measured 2026-07-27), so writing the numbers into the draft is
    both the precise path and the only reliable one. Position runs over the HALF
    canvas (±1 = an edge, so x=0.5 shifts a QUARTER frame right) and +y is UP
    (measured 2026-09-27: y -0.5 moved the picture down a quarter frame); scale is a multiplier."""
    flag = {"main": 0, "text": 1, "overlay": 2}[track_role]

    def mutate(d, folder):
        # Flattened across every track of this role, matching `remove`/`keyframe`
        # — CapCut splits overlapping segments onto separate tracks, so a single
        # track's local index is not the addressing anything else uses.
        flat = [(t, i) for t in d["tracks"] if t["flag"] == flag
                for i in range(len(t["segments"]))]
        if index >= len(flat):
            sys.exit(f"only {len(flat)} {track_role} segment(s), no index {index}")
        track, local = flat[index]
        segs, index_ = track["segments"], local
        clip = segs[index_]["clip"]
        if vals.get("scale") is not None:
            clip["scale"] = {"x": vals["scale"], "y": vals["scale"]}
            segs[index_]["uniform_scale"] = {"on": True, "value": vals["scale"]}
        if vals.get("x") is not None:
            clip["transform"]["x"] = vals["x"]
        if vals.get("y") is not None:
            clip["transform"]["y"] = vals["y"]
        if vals.get("rotation") is not None:
            clip["rotation"] = vals["rotation"]
        if vals.get("opacity") is not None:
            clip["alpha"] = vals["opacity"]
    edit_draft(name, mutate)
    applied = {k: v for k, v in vals.items() if v is not None}
    print(f"{track_role}[{index}] transform: {applied}")


KF_TYPES = {"scale": ("KFTypeScaleX", "KFTypeScaleY"), "x": ("KFTypePositionX",),
            "y": ("KFTypePositionY",), "rotation": ("KFTypeRotation",),
            "opacity": ("KFTypeAlpha",), "volume": ("KFTypeVolume",)}


def set_keyframe(name, track_role, index, at, curve="Line", **vals):
    """Animate a segment property — motion keyframes, the CapCut counterpart to
    Premiere's Effect Controls. `common_keyframes` holds one entry per property,
    each with a `keyframe_list` of points.

    `time_offset` is microseconds on the SOURCE media timeline, NOT from the
    segment start — so a point is `source_timerange.start + (t - target start)`.
    That distinction is the whole ballgame and it is easy to get wrong: a first
    probe on a clip whose source in-point was 0 made the two domains look
    identical. On a real cut (source in-point 22.133s) segment-relative offsets
    land outside the segment's source window, and CapCut silently collapses the
    whole animation to one static value instead of erroring. `--at` here is
    timeline seconds; the conversion happens below.

    File-lane on purpose, same reason as `transform`: the inspector's spin boxes
    ignore synthesized keystrokes, so exact values only go in through the JSON."""
    flag = {"main": 0, "text": 1, "overlay": 2}[track_role]
    vals = {k: v for k, v in vals.items() if v is not None}
    if not vals:
        sys.exit("nothing to animate — pass --scale/--x/--y/--rotate/--opacity")

    def mutate(d, folder):
        flat = [(t, i) for t in d["tracks"] if t["flag"] == flag
                for i in range(len(t["segments"]))]
        if index >= len(flat):
            sys.exit(f"only {len(flat)} {track_role} segment(s), no index {index}")
        track, local = flat[index]
        seg = track["segments"][local]
        start, dur = (seg["target_timerange"][k] for k in ("start", "duration"))
        rel = round(at * 1e6) - start
        if not 0 <= rel <= dur:
            sys.exit(f"{at}s is outside the segment "
                     f"({start / 1e6:.2f}s–{(start + dur) / 1e6:.2f}s)")
        src = (seg.get("source_timerange") or {}).get("start", 0)
        offset = src + rel
        kfs = seg.setdefault("common_keyframes", [])
        for prop, value in vals.items():
            for ptype in KF_TYPES[prop]:
                entry = next((e for e in kfs if e["property_type"] == ptype), None)
                if entry is None:
                    entry = {"id": uid(), "material_id": "", "property_type": ptype,
                             "keyframe_list": []}
                    kfs.append(entry)
                point = {"id": uid(), "curveType": curve, "time_offset": offset,
                         "left_control": {"x": 0.0, "y": 0.0},
                         "right_control": {"x": 0.0, "y": 0.0},
                         "values": [float(value)], "string_value": "", "graphID": ""}
                entry["keyframe_list"] = sorted(
                    [p for p in entry["keyframe_list"] if p["time_offset"] != offset]
                    + [point], key=lambda p: p["time_offset"])
    edit_draft(name, mutate)
    print(f"keyframe {track_role}[{index}] @ {at:.2f}s: {vals}")


def clear_keyframes(name, track_role, index):
    flag = {"main": 0, "text": 1, "overlay": 2}[track_role]

    def mutate(d, folder):
        flat = [(t, i) for t in d["tracks"] if t["flag"] == flag
                for i in range(len(t["segments"]))]
        flat[index][0]["segments"][flat[index][1]]["common_keyframes"] = []
    edit_draft(name, mutate)
    print(f"cleared keyframes on {track_role}[{index}]")


PREMULTIPLY = Path(__file__).resolve().parent / "premultiply.sh"


def git_bash():
    """The bash to run a .sh with: plain `bash` on macOS/Linux; Git Bash on Windows, never by bare name, because
    CreateProcess searches System32 before PATH and System32's bash.exe is WSL's (the kit's sh_argv, 2026-10-13)."""
    if os.name != "nt":
        return "bash"
    for c in [shutil.which("bash")] + [os.path.join(os.environ.get(v, ""), "Git", "bin", "bash.exe")
                                       for v in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA")]:
        if c and os.path.exists(c) and "system32" not in c.lower():
            return c
    sys.exit("no Git Bash found to run premultiply.sh (install Git for Windows)")


def premultiplied(src, cache):
    """CapCut reads ProRes 4444 alpha as PREMULTIPLIED, HyperFrames writes it straight (lab-notes): each alpha .mov is
    converted once into hf-graphics/capcut-premult/<name> (never beside the render, where place-graphics' `<id>-alpha*`
    glob would pick the copy up as a newer version), and reused while it is newer than its source."""
    dst = cache / src.name
    if not (dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime):
        cache.mkdir(parents=True, exist_ok=True)
        # through Git Bash: CreateProcess cannot run a .sh on Windows
        subprocess.run([git_bash(), str(PREMULTIPLY), str(src), str(dst)], check=True)
    return dst


def placement_levels(rows):
    """Placement track -> CapCut overlay level: graphics (2) on 1, overlaps and patches (3) on 2, the caption layer
    (4) one above the highest level anything else uses."""
    levels = [{2: 1, 3: 2}.get(int(r.get("track", 2)), 1) for r in rows if int(r.get("track", 2)) != 4]
    top = max(levels, default=0) + 1
    return [top if int(r.get("track", 2)) == 4 else {2: 1, 3: 2}.get(int(r.get("track", 2)), 1) for r in rows]


def cmd_graphics(name, job):
    """Lay every row of the job's hf-graphics/placement.json (uv run workflows/placement.py <job> --write) as overlay
    segments, in ONE cache cycle: start, end - start on the draft's frame grid, the level its track maps to, each
    alpha .mov premultiplied. A row already laid at its start (an interrupted run) is left as it is."""
    jobdir = job_dir(job)
    pj = jobdir / "hf-graphics" / "placement.json"
    if not pj.exists():
        sys.exit(f"no {pj}: run `uv run workflows/placement.py {jobdir.as_posix()} --write` first")   # pasted: forward slashes
    rows = json.loads(pj.read_text(encoding="utf-8"))
    rows = rows.get("rows", rows) if isinstance(rows, dict) else rows
    bad = [r.get("id", "?") for r in rows if r.get("ripple") == "orphaned"]
    if bad:
        sys.exit(f"placement rows orphaned by a re-cut: {', '.join(bad)}: resolve them first, nothing laid")
    queued = []
    for r, level in zip(rows, placement_levels(rows)):
        f = Path(r["file"])
        if not f.is_absolute():
            f = jobdir / f
        if r.get("start") is None or r.get("end") is None:
            print(f"  skip {r.get('id')}: no start/end")
            continue
        if not f.exists():
            print(f"  skip {r.get('id')}: {f.name} not rendered yet")
            continue
        if f.suffix.lower() == ".mov":
            f = premultiplied(f, jobdir / "hf-graphics" / "capcut-premult")
        queued.append((r, f, level))
    if not queued:
        sys.exit("nothing in placement.json is rendered yet")
    # lowest layer first: overlay_track() numbers layers by creation order, so a caption row queued first became
    # layer 1, g1 landed on it, and CapCut pushed every later graphic past the captions' end (a 55 s timeline, 2026-09-27)
    queued.sort(key=lambda q: (q[2], float(q[0]["start"])))

    def mutate(d, folder):
        for r, p, level in queued:
            if already_at(d, grid_us(d, float(r["start"])), media_name=p.name):
                print(f"  {p.name} already at {float(r['start']):.3f}s: left as it is")
                continue
            path = local_media(folder, p)
            w, h, dur_us, has_audio = probe(path)
            mid = uid()
            d["materials"]["videos"].append(
                video_material(mid, path, w, h, dur_us, has_audio))
            use = min(dur_us, grid_us(d, float(r["end"]) - float(r["start"])))
            seg = segment(mid, 0, use, grid_us(d, float(r["start"])), segment_extras(d["materials"]))
            seg["render_index"] = seg["track_render_index"] = level
            if has_audio:                       # a full-screen mp4's own sound never plays over the voice
                seg["volume"] = seg["last_nonzero_volume"] = 0.0
            overlay_track(d, level)["segments"].append(seg)
    edit_draft(name, mutate)
    print(f"placed {len(queued)} graphic(s) from {pj}")


def capcut_motion(mode):
    """A face-frame mode ({scale, centre: [x, y]} in frame fractions, y down: where the source centre lands) as
    CapCut's clip transform. MEASURED on a 1080x1920 draft (2026-09-27): position runs over the HALF canvas, so ±1 is
    an edge, and +y is UP (transform y -0.5 moved the picture DOWN a quarter frame). Scale is the same multiplier."""
    cx, cy = mode["centre"]
    return float(mode["scale"]), 2 * (cx - 0.5), -2 * (cy - 0.5)


def cmd_layout(name, job, hand=()):
    """The Talking Head Explainer's layout rotation on CapCut's main track: its footage modes (S split, T tight, W wide;
    F and O keep W's footage under their graphic) laid as the Premiere lane lays them (layout-keys.py): a clip with no
    switch inside gets its mode as STATIC values; a switch strictly inside a clip is a PAIR of keys, the outgoing mode
    one frame before, the incoming ON the switch, so the framing cuts hard on the frame and never ramps. Spans come
    from the preset's own layout.py (the one implementation the captions read), modes from face-frame.json.
    A layout row's own `frame` wins over its mode's transform (the plan's record of a span framed apart, e.g. standing
    takes); `hand` = [(a, b, mode, {scale, centre})] still overrides both from the command line."""
    import importlib.util
    repo = Path(__file__).resolve().parent.parent.parent
    jobdir = job_dir(job)
    spec = importlib.util.spec_from_file_location(
        "thx_layout", repo / "presets" / "instagram" / "talking-head-explainer" / "layout.py")
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    plan = json.loads((jobdir / "graphics-plan.json").read_text(encoding="utf-8"))
    md = L.modes(json.loads((jobdir / "face-frame.json").read_text(encoding="utf-8")))
    sp = L.spans(plan)
    fsp = L.footage_spans(plan, md)          # a row's own `frame` (face-frame.py --span) over its mode's transform
    edges = [a for a, _b, _m, _y in sp if a > 0]

    def mode_at(t):
        for (a, b, m, _y), (_a, _b, k, f) in zip(sp, fsp):
            if a <= t < b:
                for h0, h1, hm, hv in hand:
                    if m == hm and a >= h0 - 1e-3 and b <= h1 + 1e-3:
                        return capcut_motion(hv), f"{m}*"
                return capcut_motion(f), (f"{m}*" if "*" in k else m)
        return capcut_motion(fsp[-1][3]), fsp[-1][2]

    PROPS = ("KFTypeScaleX", "KFTypeScaleY", "KFTypePositionX", "KFTypePositionY")
    report = []

    def mutate(d, folder):
        fr = exact_fps(d.get("fps") or 30.0)
        for t in d["tracks"]:
            if t["flag"] != 0:
                continue
            for i, seg in enumerate(t["segments"]):
                st, du = seg["target_timerange"]["start"], seg["target_timerange"]["duration"]
                src = (seg.get("source_timerange") or {}).get("start", 0)
                a, b = st / 1e6, (st + du) / 1e6
                (s0, x0, y0), m0 = mode_at(a + 0.5 / fr)
                clip = seg["clip"]
                clip["scale"] = {"x": s0, "y": s0}
                seg["uniform_scale"] = {"on": True, "value": s0}
                clip["transform"]["x"], clip["transform"]["y"] = x0, y0
                kfs = [e for e in seg.get("common_keyframes") or [] if e["property_type"] not in PROPS]
                inside = [e for e in edges if a + 0.6 / fr < e < b - 0.6 / fr]
                names = [m0]
                if inside:
                    pts = {p: [] for p in PROPS}
                    for e in inside:
                        fe = round(e * fr)
                        for tt, vals in ((grid_us(d, (fe - 1) / fr), mode_at(e - 0.5 / fr)[0]),
                                         (grid_us(d, fe / fr), mode_at(e + 0.5 / fr)[0])):
                            off = src + (tt - st)
                            for p, v in zip(PROPS, (vals[0], vals[0], vals[1], vals[2])):
                                pts[p].append({"id": uid(), "curveType": "Line", "time_offset": off,
                                               "left_control": {"x": 0.0, "y": 0.0},
                                               "right_control": {"x": 0.0, "y": 0.0},
                                               "values": [float(v)], "string_value": "", "graphID": ""})
                        names.append(mode_at(e + 0.5 / fr)[1])
                    kfs += [{"id": uid(), "material_id": "", "property_type": p, "keyframe_list": pts[p]}
                            for p in PROPS]
                seg["common_keyframes"] = kfs
                report.append(f"  main[{i}] {a:7.3f}-{b:7.3f}  {' > '.join(names)}"
                              + (f"  ({len(inside)} switch{'es' if len(inside) > 1 else ''} keyed)" if inside else ""))
    edit_draft(name, mutate)
    print("\n".join(report))
    print(f"layout: {len(sp)} spans laid on {len(report)} main-track clips of '{name}'")


def dismiss_launch_dialogs(settle=12):
    """Close the promo/update dialogs CapCut 8.9.0 raises over the home screen after a launch ("CapCut Ultra is
    live", measured 2026-09-26 on 3 launches of 4). They are modal AXDialog windows, so the draft tile stays in the AX
    tree and `open` double-clicks it into the dialog: the editor never opens, and every file-lane command's reopen
    fails the same way. Each is closed through its own title-bar close button, never a button inside it ("Install
    now" updates the app, "Turn on" subscribes); one with no close button is named and left for the creator."""
    from ApplicationServices import AXUIElementPerformAction
    t0, closed = time.time(), 0
    while time.time() - t0 < settle:
        for w in attr(ax_app(), "AXWindows") or []:
            if attr(w, "AXSubrole") != "AXDialog" and not attr(w, "AXModal"):
                continue
            btn = attr(w, "AXCloseButton")
            if btn is None:
                sys.exit("a CapCut dialog with no close button is over the home screen: dismiss it by hand, then re-run")
            AXUIElementPerformAction(btn, "AXPress")
            closed += 1
            time.sleep(0.8)
        time.sleep(1)
    if closed:
        print(f"closed {closed} launch dialog(s)")


def cmd_open(name):
    if IS_WIN:
        ed = W.open_draft(name)
        print(f"opened '{name}' (editor window {ed['aid'] or ed['cls']}, {ed['rect'][2]}x{ed['rect'][3]})")
        return
    if app_pid() is None:
        launch_app()
    subprocess.run(["osascript", "-e", f'tell application "{APP}" to activate'], check=False)
    hit = find_one(f"HomePageDraftTitle:{name}", timeout=15)
    dismiss_launch_dialogs()
    if hit is None:
        send_key("escape")  # a promo modal can cover the home screen on launch
        hit = find_one(f"HomePageDraftTitle:{name}", timeout=15)
    if hit is None:
        sys.exit(f"draft tile not found on home screen: {name}")
    time.sleep(1.5)  # the window repositions after launch, re-find before clicking
    hit = find_one(f"HomePageDraftTitle:{name}", timeout=10) or hit
    _, _, (tx, ty, tw, th) = hit
    # The clickable tile is the HomePageDraft element whose x-span contains the title.
    tile = next((g for _, n, g in elements("HomePageDraft")
                 if n == "HomePageDraft" and g and g[0] <= tx <= g[0] + g[2]
                 and g[1] <= ty), None)
    x, y = (tile[0] + tile[2] / 2, tile[1] + tile[3] / 2) if tile else (tx, ty - 60)
    click_at(x, y, clicks=2)
    if find_one("MainTimeLineRoot", timeout=25) is None:
        sys.exit("editor did not open")
    cur, tot = read_playhead()
    print(f"opened '{name}', duration {tot}")


# Export dialog controls, as offsets from the CapCut window's CENTER. The dialog
# is a fixed-size centered QML overlay that exposes NO AX internals (same as Link
# media), so positional clicking is the only way in. Measured on 8.9.0.
EXPORT_BTN_OFFSET = (308, 302)
SYNC_CHECKBOX_OFFSET = (6, 239)


def export_frames(cw, ch):
    """The frame sizes the format's file may have for a draft of this canvas (the presets' § Export, 2026-09-26):
    any landscape draft exports 3840x2160 (a 1080 long-form goes up at 2160p), a vertical one 1080x1920, and a 4K
    vertical draft also its 2160x3840 YouTube Shorts file."""
    if cw > ch:
        return [(3840, 2160)]
    return [(1080, 1920), (2160, 3840)] if (cw, ch) == (2160, 3840) else [(1080, 1920)]


def export_checks(target, d):
    """[(label, ok)] for an exported file against its draft: H.264, the format's frame for the draft's canvas, the
    draft's frame rate, the frame count within one of the draft's duration, and the Reels cap (300 MB) on a 1080x1920 file."""
    out = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,r_frame_rate,nb_read_packets", "-of", "json", str(target)]))["streams"][0]
    cw, ch = int(d["canvas_config"]["width"]), int(d["canvas_config"]["height"])
    fps = float(d.get("fps") or 30.0)
    n, dn = (int(x) for x in out["r_frame_rate"].split("/"))
    rate = n / (dn or 1)
    frames, want = int(out.get("nb_read_packets") or 0), d["duration"] / 1e6 * fps
    ok_frames, wh = export_frames(cw, ch), (int(out["width"]), int(out["height"]))
    checks = [("H.264", out["codec_name"] == "h264"),
              (f"{wh[0]}x{wh[1]}, the format's frame for a {cw}x{ch} canvas ({' or '.join('%dx%d' % f for f in ok_frames)})",
               wh in ok_frames),
              (f"{fps:g} fps (the draft's rate; file {rate:.3f})", abs(rate - fps) < 0.01),
              (f"{frames} frames, the draft's {want:.1f} within one", abs(frames - want) <= 1)]
    if wh == (1080, 1920):
        mb = Path(target).stat().st_size / 1e6
        checks.append((f"<= 300 MB ({mb:.0f})", mb <= 300))
    return checks


def deliver_windows(video, audio, to, d):
    """Windows export, step 2: CapCut wrote a MASTER (H.264 at capcut_win.MASTER_KBPS) and a WAV of its own mix; the
    deliverable is encoded from them by workflows/deliver.py to the presets' numbers (H.264 High, CBR 14 on a vertical
    file or the Reels rule past 2:48, 3840x2160 CBR 50 on a landscape one, AAC 320k from PCM, bt709), then held to the
    draft (export_checks) and to those numbers. It lands in `to` (else beside the master) as the draft's own file name,
    never over an existing file (claim_export's rule: in outputs/ a draft named after the job lands on the base cut's
    name); on any failure the master and the WAV are kept and named. the user's call, 2026-09-27: the dialog's Recommended
    gave H.264 Main, 10 Mbps, AAC 197k."""
    dest = Path(to).expanduser().resolve() if to else video.parent
    final = dest / video.name
    if final.exists() and final.resolve() != video.resolve():
        sys.exit(f"exported to {video}, NOT delivered: {final} already exists (a draft named after the job lands on the "
                 f"base cut's name); move the master by hand, or rename the draft, and export again")
    dest.mkdir(parents=True, exist_ok=True)
    stem = video.with_name(video.stem + ".capcut-master")      # with_suffix swaps ".capcut-master": names spelled out
    # CapCut holds a finished export OPEN for a while (its share screen previews it: "resource busy", C5), so the
    # rename waits it out, as the old move did
    for i in range(30):
        try:
            vmaster = video.rename(stem.with_name(stem.name + ".mp4"))
            break
        except PermissionError:
            if i == 29:
                sys.exit(f"{video} is still held open by CapCut after 30 s (its share screen?): close it, then run "
                         f"the export again; nothing was delivered")
            time.sleep(1)
    if audio is None:
        print("⚠ no WAV of the mix landed beside the master: the deliverable's AAC is encoded from CapCut's own AAC "
              "(a second lossy pass, at 320k)")
    mov = stem.with_name(stem.name + ".mov")
    mux = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(vmaster)]
    mux += ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0"] if audio else ["-map", "0:v:0", "-map", "0:a:0"]
    subprocess.run(mux + ["-c:v", "copy", "-c:a", "pcm_s24le", str(mov)], check=True)
    r = subprocess.run([sys.executable, str(REPO / "workflows" / "deliver.py"), str(mov), str(final)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip())
    if r.returncode or not final.exists():
        sys.exit(f"deliver.py failed ({r.returncode}): {(r.stderr or '').strip()[-400:]}; kept {vmaster}"
                 + (f", {audio}" if audio else "") + f", {mov}")
    checks = export_checks(final, d)
    pr = json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,profile,sample_rate,bit_rate", "-of",
         "json", str(final)], text=True))
    v = next(x for x in pr["streams"] if x["codec_type"] == "video")
    a = next((x for x in pr["streams"] if x["codec_type"] == "audio"), {})
    vb, ab = int(v.get("bit_rate") or 0) / 1e6, int(a.get("bit_rate") or 0) / 1e3
    # the audio is proven deliver.py's encode by its 48 kHz (CapCut writes 44.1 kHz), never by the measured rate:
    # ffmpeg's AAC asked for 320k spends 246-263 kb/s on a dual-mono voice mix (R11 in docs/WINDOWS-TEST-FINDINGS.md)
    checks += [(f"H.264 {v.get('profile')} (High)", v.get("profile") == "High"),
               (f"video {vb:.1f} Mbps (deliver.py's CBR)", vb > 0),
               (f"AAC {a.get('sample_rate')} Hz, deliver.py's 320k encode of the WAV (measures {ab:.0f} kb/s)",
                a.get("codec_name") == "aac" and a.get("sample_rate") == "48000")]
    print(f"checked against draft '{d.get('name') or final.stem}' and the presets' numbers:")
    for label, ok in checks:
        print(("  ✓ " if ok else "  ✗ ") + label)
    bad = [label for label, ok in checks if not ok]
    if bad:
        sys.exit(f"{len(bad)} check(s) failed; {final} and the master ({vmaster}) are kept")
    for f in (vmaster, mov) + ((audio,) if audio else ()):
        f.unlink(missing_ok=True)
    if vmaster.parent.name.lower() == video.stem.lower() and vmaster.parent != final.parent:
        try:
            vmaster.parent.rmdir()            # the folder CapCut made for the video + WAV pair, once empty
        except OSError:
            pass
    return final


DOWNLOADS = Path.home() / "Downloads"
# TMPDIR on macOS; the real temp folder on Windows, where a native "/tmp" is C:\tmp
EXPORTED_PID = Path(os.environ.get("TMPDIR") or ("/tmp" if not IS_WIN else __import__("tempfile").gettempdir())) / "capcut-bridge-exported-pid"


def fresh_session_for_export(draft):
    """CapCut 8.9.0 completes only the FIRST export of an app launch (live, 2026-09-26, reproduced 4 times, with and
    without the bridge's escape and file move): a second export renders into the previous export's
    `.__capcut_export_temp_folder_*`, never moves the file out, and the dialog freezes at 30.0%. So an export in a
    CapCut process the bridge has already exported from relaunches it first (a graceful quit saves the draft) and
    reopens the draft. A second export by hand in the same launch is invisible here: the timeout message names it."""
    pid = app_pid()
    try:
        last = int(EXPORTED_PID.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last = None
    if pid is None or pid != last:
        return
    if not draft:
        sys.exit("CapCut already exported once since it launched, and a second export in one launch freezes at 30%: "
                 "pass --draft <name> so the bridge can relaunch it and reopen the draft")
    print("CapCut already exported once since it launched (a second export freezes at 30%): relaunching it first")
    quit_app()
    launch_app()
    time.sleep(8)
    cmd_open(draft)


def claim_export(landed, dest):
    """Move an export that landed outside --to into it. Never over an existing file: `<draft>.mp4` in outputs/ is the
    job's base cut when the draft carries the job name, so a clash leaves the export where it landed and says so."""
    if landed.parent.resolve() == dest:
        return landed
    to = dest / landed.name
    if to.exists():
        sys.exit(f"exported to {landed}, NOT moved: {to} already exists (a draft named after the job lands on the "
                 f"base cut's name); move it by hand as <job>-final.mp4")
    dest.mkdir(parents=True, exist_ok=True)
    shutil.move(str(landed), str(to))
    print(f"moved {landed} -> {to} (the dialog's Export to is {landed.parent})")
    return to


def cmd_export(out_dir=None, timeout=900, toggle_sync=False, draft=None):
    """Drive CapCut's export end to end and verify the file that lands.

    Defaults in the dialog are the draft name into ~/Downloads. A pipeline job passes
    --to projects/<job>/outputs (finalize.sh only reads outputs/). "Sync exported videos to space"
    uploads the render to CapCut's cloud — it was switched OFF on 2026-07-27 and
    the setting is sticky, so this does NOT touch it by default (a blind click
    would switch it back ON). Pass --toggle-sync only to flip it deliberately."""
    # The bridge cannot set the dialog's "Export to" (the dialog exposes no AX internals, and CapCut's sandbox only
    # writes where the creator picked): the file lands at the dialog's own destination, ~/Downloads by default,
    # whatever --to says. Watch both, then claim a Downloads landing into --to (live, 2026-09-26: a --to run
    # polled an empty folder while the render sat in ~/Downloads).
    fresh_session_for_export(draft)
    dest = Path(out_dir).expanduser().resolve() if out_dir else None
    watch = list(dict.fromkeys([dest or DOWNLOADS, DOWNLOADS]))
    before = {p: p.stat().st_mtime for d in watch for p in d.glob("*.mp4")}

    # CapCut leaves a modal "share to TikTok/YouTube" screen up after a finished
    # export, and it BLOCKS the next one — the title-bar click is swallowed and
    # the run polls forever for a file that is never written (hit 2026-07-27).
    # Escape clears any lingering modal before starting.
    send_key("escape")
    time.sleep(1.0)

    win = find_one("MainWindowTitleBarExportBtn")
    if win is None:
        sys.exit("export button not found (is a draft open?)")
    w = next((g for _, n, g in elements("CapCut") if g and g[2] > 1000), None)
    if w is None:
        sys.exit("could not locate the CapCut window rect")
    cx, cy = w[0] + w[2] / 2, w[1] + w[3] / 2

    click_element("MainWindowTitleBarExportBtn")
    time.sleep(6)  # the dialog paints well after the click returns
    if toggle_sync:
        click_at(cx + SYNC_CHECKBOX_OFFSET[0], cy + SYNC_CHECKBOX_OFFSET[1])
        time.sleep(0.6)
    click_at(cx + EXPORT_BTN_OFFSET[0], cy + EXPORT_BTN_OFFSET[1])
    EXPORTED_PID.write_text(str(app_pid()), encoding="utf-8")

    t0, last, stable, target = time.time(), -1, 0, None
    while time.time() - t0 < timeout:
        time.sleep(4)
        fresh = [p for d in watch for p in d.glob("*.mp4")
                 if p not in before or p.stat().st_mtime > before[p]]
        if not fresh:
            continue
        target = max(fresh, key=lambda p: p.stat().st_mtime)
        size = target.stat().st_size
        stable = stable + 1 if size == last and size > 0 else 0
        last = size
        if stable >= 2:
            break
    # Clear the post-export share screen so the app is left ready for the next
    # run. Never click through it: it offers TikTok/YouTube publishing.
    send_key("escape")
    time.sleep(0.8)

    if target is None:
        stuck = sorted(DOWNLOADS.glob(".__capcut_export_temp_folder_*"))
        sys.exit("export produced no file in " + " or ".join(map(str, watch))
                 + " — the dialog may still be open, or its Export to points elsewhere"
                 + (f"; {len(stuck)} CapCut export temp folder(s) are in ~/Downloads, the mark of a SECOND export in "
                    "one CapCut launch (it freezes at 30%): Cancel it in the dialog, quit CapCut, relaunch, re-run"
                    if stuck else ""))
    if dest is not None:
        target = claim_export(target, dest)

    probe_out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(target)], capture_output=True, text=True)
    dur = probe_out.stdout.strip() or "?"
    print(f"exported: {target}  {last / 1048576:.1f} MB  {dur}s")
    # the export dialog's settings are the creator's (the bridge does not set them yet): hold the file to the draft
    info = (DRAFT_ROOT / draft / DRAFT_FILE) if draft else \
        max(DRAFT_ROOT.glob(f"*/{DRAFT_FILE}"), key=lambda p: p.stat().st_mtime, default=None)
    if info is None or not info.exists():
        sys.exit(f"no {DRAFT_FILE} to verify {target.name} against (pass --draft <name>); the file is kept")
    checks = export_checks(target, json.loads(info.read_text(encoding="utf-8")))
    print(f"checked against draft '{info.parent.name}':")
    for label, ok in checks:
        print(("  ✓ " if ok else "  ✗ ") + label)
    bad = [label for label, ok in checks if not ok]
    if bad:
        sys.exit(f"{len(bad)} check(s) failed: set the export dialog to the draft's settings (H.264, the format's "
                 f"resolution, the sequence rate, the format's bitrate) and export again; {target} is kept")
    return target


def cmd_state(name=None):
    """Timeline snapshot. Exact segment times come from draft_info.json (the
    saved truth); the live AX clip count is compared against it, because live
    edits only reach disk on save/quit — a mismatch means unsaved changes."""
    if IS_WIN:      # no live clip list on Windows (UIA shows no QML items): the saved draft is the clip truth
        cur, tot = W.playhead() if W.editor_window() else ("?", "?")
        live = None
    else:
        cur, tot = read_playhead()
        live = timeline_clips()
    out = {"playhead": cur, "duration": tot, "live_clip_count": None if live is None else len(live)}

    path = DRAFT_ROOT / name / DRAFT_FILE if name else None
    if path and path.exists():
        d = json.loads(path.read_text(encoding="utf-8"))
        tracks = []
        for t in d["tracks"]:
            segs = []
            for i, s in enumerate(t["segments"]):
                mat = next((m["material_name"] for m in d["materials"]["videos"]
                            if m["id"] == s["material_id"]), None)
                if mat is None:
                    mat = next((json.loads(m["content"]).get("text", "")[:40]
                                for m in d["materials"]["texts"]
                                if m["id"] == s["material_id"]), "?")
                src = s.get("source_timerange")  # null on text segs after app save
                segs.append({"i": i, "media": mat,
                             "start": round(s["target_timerange"]["start"] / 1e6, 3),
                             "dur": round(s["target_timerange"]["duration"] / 1e6, 3),
                             "src": round(src["start"] / 1e6, 3) if src else None})
            tracks.append({"type": t["type"],
                           "role": {0: "main", 1: "text", 2: "overlay"}.get(t["flag"], t["flag"]),
                           "segments": segs})
        out["saved"] = {"duration": round(d["duration"] / 1e6, 3), "tracks": tracks}
        saved_video = sum(len(t["segments"]) for t in d["tracks"] if t["type"] == "video")
        if live is not None and saved_video != len(live):
            out["unsaved_edits"] = f"{len(live)} clips live vs {saved_video} saved"
    print(json.dumps(out, indent=1))


def cmd_clips():
    hits = [(n, g) for _, n, g in elements("MTLSVideoP") if g]
    for n, (x, y, w, h) in sorted(hits, key=lambda t: t[1][0]):
        print(f"{n}  x={x:.0f} y={y:.0f} w={w:.0f} h={h:.0f}")
    print(f"{len(hits)} clip(s) on timeline")


def opt(rest, flag, cast=str, default=None):
    return cast(rest[rest.index(flag) + 1]) if flag in rest else default


def win_live(cmd, rest):
    """The live lane on Windows (capcut_win.py): windows by automation id, CapCut's own shortcuts, OCR read-back.
    Returns False when `cmd` is not a live command (the file lane handles it, identically on both OSes)."""
    draft = opt(rest, "--draft")
    # the timeline's frame rate is the draft's own (29.97 for a 29.97 take): the OPEN draft when none is named
    fps = draft_fps(draft or (_open_draft_name() if cmd in ("seek", "split", "select", "delete", "del") else None))
    if cmd == "seek":
        landed = W.seek(float(rest[0]), fps)
        print(f"playhead: {landed:.3f}s (target {float(rest[0]):.3f}s)")
    elif cmd == "playhead":
        cur, tot = W.playhead()
        print(f"{cur} / {tot}")
    elif cmd == "split":
        # the cutoff shortcut (Ctrl+B on the built-in keymap) splits the SELECTED clip at the playhead (with nothing selected it does nothing): select the main-track
        # clip under the playhead first, which also parks the playhead there
        at = float(rest[0]) if rest and not rest[0].startswith("--") else W.parse_tc(W.playhead()[0], fps)
        W.select_at(at, fps)
        W.key_action(W.shortcut("cutoff"))
        print("split at playhead", W.playhead()[0])
    elif cmd in ("delete", "del", "select"):
        # the clip's own midpoint from the saved draft: select it on the main track by clicking at the playhead.
        # Windows exposes no live clip list, so the draft is SAVED first (the reopen round-trip CapCut saves on):
        # after an unsaved live split the saved indices were stale and the wrong clip went (the Mac review, 2026-09-27)
        name = draft or _open_draft_name()
        W.open_draft(name)
        segs = [s for t in _draft(name)["tracks"] if t["flag"] == 0 for s in t["segments"]]
        i = int(rest[0])
        if i >= len(segs):
            sys.exit(f"clip index {i} out of range (the saved draft has {len(segs)})")
        tr = segs[i]["target_timerange"]
        W.select_at((tr["start"] + tr["duration"] / 2) / 1e6, fps)
        if cmd != "select":
            before = W.playhead()[1]
            W.key_action(W.shortcut("del"))
            after = W.playhead()[1]
            # the readout is the LONGEST track's end: under a full-length caption layer a main-track delete (it
            # ripples the main track) leaves it as it was, which read as "nothing deleted" on the re-test (2026-09-27)
            print(f"deleted clip {i} ({tr['start'] / 1e6:.3f}s +{tr['duration'] / 1e6:.3f}s); the timeline total "
                  f"{before} -> {after} (the longest track's end: unchanged under a full-length layer)")
        else:
            print(f"selected clip {i}")
    elif cmd in ("trim-left", "trim-right"):
        before = W.playhead()[1]
        W.key_action(W.shortcut("cutLeft" if cmd == "trim-left" else "cutRight"))
        print(f"{cmd} at playhead: total {before} -> {W.playhead()[1]}")
    elif cmd in ("undo", "redo"):
        before = W.playhead()[1]
        W.key_action(W.shortcut(cmd))
        print(f"{cmd}: total {before} -> {W.playhead()[1]}")
    elif cmd == "marker":
        W.key_action(W.shortcut("mark"))
        print("marker added")
    elif cmd == "zoomfit":
        W.key_action(W.shortcut("quicklyAdjustZoomFit"))
        print("zoom fit")
    elif cmd == "play":
        W.key_action(W.shortcut("togglePlay"))
        print("play/pause toggled")
    elif cmd == "save":
        # no save shortcut on Windows: back to the drafts page (CapCut saves the draft on the way) and reopen it
        name = draft or _open_draft_name()
        mt = (DRAFT_ROOT / name / DRAFT_FILE).stat().st_mtime
        W.open_draft(name)
        print("saved" if (DRAFT_ROOT / name / DRAFT_FILE).stat().st_mtime > mt else "saved (draft file unchanged: nothing to save)")
    elif cmd == "clips":
        name = draft or _open_draft_name()
        segs = [(t["flag"], s) for t in _draft(name)["tracks"] for s in t["segments"]]
        for fl, s_ in segs:
            tr = s_["target_timerange"]
            print(f"{ {0: 'main', 1: 'text', 2: 'overlay'}.get(fl, fl)}  {tr['start'] / 1e6:.3f}s +{tr['duration'] / 1e6:.3f}s")
        print(f"{len(segs)} clip(s) in the saved draft (Windows exposes no live clip list)")
    elif cmd == "shot":
        print("wrote", W.shot(rest[0] if rest else "capcut.png"))
    elif cmd == "dump":
        W.dump()
    elif cmd == "click":
        print("clicked:", W.click_text(rest[0]))
    elif cmd == "clickxy":
        W.click_at(float(rest[0]), float(rest[1]), clicks=opt(rest, "--clicks", int, 1))
        print(f"clicked ({rest[0]}, {rest[1]})")
    elif cmd == "key":
        times = opt(rest, "--times", int, 1)
        W.editor()
        for i in range(times):
            W.send_key(rest[0])
            time.sleep(0.04)
    elif cmd == "export":
        # the export rate is the TIMELINE's own (the draft's fps, the footage's since replay builds it so). A rate
        # different from the timeline's RELABELS its frames: 29.97 picked off a 30 fps timeline gave video 32.399 s
        # against 32.368 s of audio (2026-09-27). --fps overrides, knowingly
        name = draft or _open_draft_name()
        fps = opt(rest, "--fps", float) or draft_fps(name)
        print(f"export frame rate: {fps:g} fps" if fps else "export frame rate: the dialog default (footage fps unread)")
        # CapCut completes only the FIRST export of a launch; a second froze at 30.0% here too (the Windows re-test,
        # 2026-09-28, as on the Mac: fresh_session_for_export): relaunch and reopen the draft first
        to = opt(rest, "--to")
        if to and (Path(to).expanduser() / f"{name}.mp4").exists():   # deliver_windows would refuse it after the render
            sys.exit(f"{Path(to).expanduser() / (name + '.mp4')} already exists: move it or rename the draft, then export")
        try:
            last = int(EXPORTED_PID.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            last = None
        if W.app_pid() is not None and W.app_pid() == last:
            print("CapCut already exported once since it launched (a second export freezes at 30%): relaunching it first")
            W.quit_app()
            W.open_draft(name)
        try:
            video, audio, size = W.export(opt(rest, "--timeout", int, 900), fps=fps)
        finally:                                  # a render that started and then failed counts too
            EXPORTED_PID.write_text(str(W.app_pid()), encoding="utf-8")
        final = deliver_windows(video, audio, to, _draft(name))
        print(f"exported: {final}  {final.stat().st_size / 1048576:.1f} MB")
    elif cmd == "state":
        cmd_state(draft)
    else:
        return False
    return True


def draft_source_fps(name):
    """The main track's footage frame rate on CapCut's export list (source_fps), or None when it cannot be read."""
    try:
        d = _draft(name)
        mids = {s["material_id"] for tr in d["tracks"] if tr["flag"] == 0 for s in tr["segments"]}
        v = next(m for m in d["materials"]["videos"] if m["id"] in mids)
        # CapCut rewrites a material's path to '##_draftpath_placeholder_<id>_##/Resources/<file>' on save
        p = re.sub(r"^##_draftpath_placeholder_[^#]*_##", (DRAFT_ROOT / name).as_posix(), v["path"])
        return source_fps(p) if Path(p).exists() else None
    except (OSError, StopIteration, KeyError, ValueError):
        return None


def _draft(name):
    return json.loads((DRAFT_ROOT / name / DRAFT_FILE).read_text(encoding="utf-8"))


def mac_draft_fps(rest):
    """The draft's rate for a macOS seek/split. replay builds each draft at its footage's rate, and the readout's frame
    field is read on that rate (drop-frame on 29.97), so without --draft the 30 fps default can land a seek off."""
    d = opt(rest, "--draft")
    if not d:
        print("⚠ no --draft: the playhead is read at 30 fps; a draft at another rate (replay builds each at its "
              "footage's) needs --draft <name>")
    return draft_fps(d)


def _open_draft_name():
    """The draft in the editor, from the editor window's title (CapCut titles it with the draft name)."""
    ed = W.editor_window()
    if ed is None:
        sys.exit("no draft is open in CapCut (use: open <draft>, or pass --draft <name>)")
    words, lines = W.ocr((ed["rect"][0], ed["rect"][1], ed["rect"][2], 40))
    names = [p.name for p in DRAFT_ROOT.iterdir() if (p / DRAFT_FILE).exists()]
    for text, _b in lines:
        if text.strip() in names:
            return text.strip()
    sys.exit("could not read the open draft's name off the title bar: pass --draft <name>")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(USAGE)
    cmd, rest = args[0], args[1:]
    if IS_WIN and win_live(cmd, rest):
        return
    if cmd == "replay":
        cmd_replay(rest[0], opt(rest, "--name"), opt(rest, "--media"))
    elif cmd == "add-overlay":
        add_overlay(rest[0], rest[1], opt(rest, "--at", float, 0.0),
                    opt(rest, "--layer", int, 1), opt(rest, "--dur", float),
                    force="--force" in rest, src=opt(rest, "--src", float, 0.0),
                    render_index=opt(rest, "--ri", int), mute="--mute" in rest)
    elif cmd == "add-text":
        add_text(rest[0], rest[1], opt(rest, "--at", float, 0.0),
                 opt(rest, "--dur", float, 3.0), force="--force" in rest,
                 render_index=opt(rest, "--ri", int))
    elif cmd == "remove":
        remove_segment(rest[0], opt(rest, "--track", str, "main"),
                       opt(rest, "--index", int, 0))
    elif cmd == "graphics":
        cmd_graphics(rest[0], rest[1])
    elif cmd == "sfx-pack":
        cmd_sfx_pack(rest[0], dry="--dry" in rest)
    elif cmd == "seek":
        fps = mac_draft_fps(rest)
        landed = seek(float(rest[0]), fps)
        print(f"playhead: {landed:.3f}s (target {float(rest[0]):.3f}s)")
    elif cmd == "select":
        print("selected:", select_clip(int(rest[0])))
    elif cmd == "split":
        if rest and not rest[0].startswith("--"):
            seek(float(rest[0]), mac_draft_fps(rest))
        click_element("cutoff")
        print("split at playhead")
    elif cmd in ("delete", "del"):
        select_clip(int(rest[0]))
        click_element("del")
        print(f"deleted clip {rest[0]}")
    elif cmd in ("trim-left", "trim-right"):
        click_element("cutLeft" if cmd == "trim-left" else "cutRight")
        print(f"{cmd} at playhead")
    elif cmd in ("undo", "redo"):
        click_element(cmd)
        print(cmd)
    elif cmd == "transform":
        set_transform(rest[0], opt(rest, "--track", str, "main"),
                      opt(rest, "--index", int, 0),
                      scale=opt(rest, "--scale", float),
                      x=opt(rest, "--x", float), y=opt(rest, "--y", float),
                      rotation=opt(rest, "--rotate", float),
                      opacity=opt(rest, "--opacity", float))
    elif cmd == "keyframe":
        set_keyframe(rest[0], opt(rest, "--track", str, "main"),
                     opt(rest, "--index", int, 0), opt(rest, "--at", float, 0.0),
                     curve=opt(rest, "--curve", str, "Line"),
                     scale=opt(rest, "--scale", float),
                     x=opt(rest, "--x", float), y=opt(rest, "--y", float),
                     rotation=opt(rest, "--rotate", float),
                     opacity=opt(rest, "--opacity", float))
    elif cmd == "layout":
        hand = []
        for h in [rest[i + 1] for i, a in enumerate(rest) if a == "--hand"]:
            # a-b:MODE=scale,cx,cy   e.g. 0-14.8148:S=1.0,0.5,0.7526 (the job's recorded standing-take override)
            rng, val = h.split("=")
            ab, hm = rng.split(":")
            h0, h1 = (float(x) for x in ab.split("-"))
            sc, cx, cy = (float(x) for x in val.split(","))
            hand.append((h0, h1, hm, {"scale": sc, "centre": [cx, cy]}))
        cmd_layout(rest[0], rest[1], hand)
    elif cmd == "clear-keyframes":
        clear_keyframes(rest[0], opt(rest, "--track", str, "main"),
                        opt(rest, "--index", int, 0))
    elif cmd == "marker":
        click_element("mark")
        print("marker added")
    elif cmd == "zoomfit":
        click_element("quicklyAdjustZoomFit")
        print("zoom fit")
    elif cmd == "save":
        send_key("cmd+s")
        time.sleep(1.5)
        print("saved")
    elif cmd == "export":
        cmd_export(opt(rest, "--to"), opt(rest, "--timeout", int, 900),
                   toggle_sync="--toggle-sync" in rest, draft=opt(rest, "--draft"))
    elif cmd == "shot":
        print("wrote", grab(rest[0] if rest else "capcut.png"))
    elif cmd == "state":
        cmd_state(opt(rest, "--draft"))
    elif cmd == "ls":
        root = json.loads((DRAFT_ROOT / "root_meta_info.json").read_text(encoding="utf-8"))
        for d in root["all_draft_store"]:
            print(f"{d['draft_name']}: {d['tm_duration'] / 1e6:.2f}s  {d['draft_fold_path']}")
    elif cmd == "launch":
        launch_app()
    elif cmd == "quit":
        quit_app()
    elif cmd == "open":
        cmd_open(rest[0])
    elif cmd == "dump":
        needle = rest[0] if rest else None
        for _, name, g in elements(needle):
            if name:
                geo = f"  [{g[0]:.0f},{g[1]:.0f} {g[2]:.0f}x{g[3]:.0f}]" if g else ""
                print(f"{name}{geo}")
    elif cmd == "click":
        print("clicked:", click_element(rest[0]))
    elif cmd == "clickxy":
        # Modal dialogs (export, Link media) are QML overlays with no AX
        # internals, so their controls can only be reached positionally.
        click_at(float(rest[0]), float(rest[1]), clicks=opt(rest, "--clicks", int, 1))
        print(f"clicked ({rest[0]}, {rest[1]})")
    elif cmd == "clips":
        cmd_clips()
    elif cmd == "playhead":
        cur, tot = read_playhead()
        print(f"{cur} / {tot}")
    elif cmd == "play":
        # The transport button's AX id reflects state: PlayerPlayBtn when paused,
        # PlayerPauseBtn while playing. Match either so the toggle always lands.
        click_element("PlayerPlayBtn" if find_one("PlayerPlayBtn") else "PlayerPauseBtn")
    elif cmd == "key":
        # --times keeps a long run of frame steps inside ONE process: the ruler
        # can have dead regions (see `nudge`), so arrow stepping is the fallback
        # way to park the playhead and 60 separate invocations would crawl.
        times = opt(rest, "--times", int, 1)
        for i in range(times):
            send_key(rest[0])
            if i + 1 < times:
                time.sleep(0.03)   # CapCut drops frame steps sent back-to-back
    else:
        sys.exit(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
