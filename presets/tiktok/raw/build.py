#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""
TikTok/raw caption + hook-card builder  (LOCKED PRESET — see presets/tiktok/raw/tiktok-raw-style.md)

Two overlays, dead simple, no animation:
  1. HOOK CARD  — one static white box / black Inter text, pinned top, shown only
                  over the spoken hook line.
  2. CAPTIONS   — line-by-line white Inter + black stroke, no box, no animation,
                  parked low under the face. Each line holds until the next one replaces it.

Source of truth = the canonical cut transcript outputs/<job>.transcript.json (transcribe-once,
remapped through cuts.json). We NEVER re-transcribe. Renders PIL PNGs and overlays them with
ffmpeg (this ffmpeg has no drawtext/libass — PIL is the house pattern).

Usage:
  uv run presets/tiktok/raw/build.py <job_dir> [--until SECONDS] [--hook-end SECONDS]
                                       [--hook-text "...."] [--out PATH]
"""
import argparse, difflib, glob, json, math, os, platform, re, subprocess, sys
import tempfile
from fractions import Fraction
from PIL import Image, ImageDraw, ImageFont
# Windows consoles/pipes default to cp1252, which can't encode the → glyphs in this
# script's status lines: a cosmetic print must never kill a pipeline step (it did once,
# 2026-08-13, mid-splice on a real Windows job). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# ---------------------------------------------------------------- layout (LOCKED)
W, H = 1080, 1920
SAFE_TOP, SAFE_BOT = 200, 1620          # no key visuals outside this band (platform UI / chrome)

FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "assets", "fonts", "Inter-Bold.otf")   # bundled Inter (no system-font dependency)
FALLBACK_FONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "assets", "fonts", "Inter-Bold.otf")  # if SFNS.ttf is absent (non-standard macOS)
HOOK_WEIGHT = "Semibold"                # hook card = Inter Semibold
CAP_WEIGHT  = "Semibold"                # captions  = Inter Semibold

# hook card
HOOK_SIZE      = 64
HOOK_TOP_Y     = 250                    # box top (just below the 200px safe band)
HOOK_BOX_W     = 940                    # box max width (centered → 70px side margins)
HOOK_PAD_X     = 32                     # white margin hugging the text (box sized to ink, not metrics)
HOOK_PAD_Y     = 20
HOOK_RADIUS    = 22
HOOK_LINE_GAP  = 10
HOOK_FILL      = (255, 255, 255, 255)   # white box
HOOK_TEXT_COL  = (0, 0, 0, 255)         # black text

# captions
CAP_SIZE       = 42                     # 30% smaller than the original 60
CAP_CENTER_Y   = 1500                   # vertical center of the caption block (low, under the face)
CAP_MAX_W      = 960                    # wrap width
CAP_MAX_CHARS  = 20                     # soft cap → keeps each line short (≈3-4 words)
CAP_MAX_WORDS  = 4
CAP_STROKE     = 4
CAP_TEXT_COL   = (255, 255, 255, 255)   # white
CAP_STROKE_COL = (0, 0, 0, 255)         # black stroke
CAP_LINE_GAP   = 8
CAP_HOLD_PAD   = 0.40                   # last line lingers this long after the final word

# empty = no hook card unless --hook-text is passed (the documented contract:
# every locked per-job invocation passes it explicitly; clipper passes "")
DEFAULT_HOOK_TEXT = ""  # set per job via --hook-text (see brand-kit.md)

# Every pixel number above is authored in the locked 1080x1920 space. A job whose base is bigger
# (a 4K rotated raw makes a 2160x3840 sequence, 2026-09-08) renders the SAME layout at that size
# by scaling the constants once, before any font or canvas is made — the look never changes, only
# the raster it lands on. Never scale the finished PNGs or mov instead (soft glyph edges).
SCALE_KEYS = ("W", "H", "SAFE_TOP", "SAFE_BOT", "HOOK_SIZE", "HOOK_TOP_Y", "HOOK_BOX_W", "HOOK_PAD_X",
              "HOOK_PAD_Y", "HOOK_RADIUS", "HOOK_LINE_GAP", "CAP_SIZE", "CAP_CENTER_Y", "CAP_MAX_W",
              "CAP_STROKE", "CAP_LINE_GAP")

def apply_scale(s):
    if abs(s - 1.0) < 1e-6:
        return
    g = globals()
    for k in SCALE_KEYS:
        g[k] = int(round(g[k] * s))

def base_upright_width(video):
    """Width of the frame as it plays: a Sony/phone raw stores 3840x2160 with rotation ±90."""
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:stream_side_data=rotation", "-of", "json", video]).decode()
    st = json.loads(out)["streams"][0]
    rot = 0
    for sd in st.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(round(float(sd["rotation"])))
    w, h = int(st["width"]), int(st["height"])
    return h if abs(rot) % 180 == 90 else w

# ---------------------------------------------------------------- corrections
def load_corrections(repo_root):
    merged = {}
    cpath = os.path.join(repo_root, "transcript-corrections.json")
    if not os.path.exists(cpath):   # pre-2026-08-31 location
        cpath = os.path.join(repo_root, "presets", "caption-corrections.json")
    if os.path.exists(cpath):
        merged.update(json.load(open(cpath, encoding="utf-8")).get("auto", {}))
    # Add your brand/product name fixes to transcript-corrections.json (loaded above).
    return merged

_token = re.compile(r"^(\W*)(.*?)(\W*)$", re.DOTALL)
def correct(word, table):
    pre, core, suf = _token.match(word).groups()
    if not core:
        return word
    hit = table.get(core.lower())
    return f"{pre}{hit}{suf}" if hit else word

# ---------------------------------------------------------------- fonts
def load_font(size, weight):
    try:
        f = ImageFont.truetype(FONT_PATH, size)
    except OSError:
        f = ImageFont.truetype(FALLBACK_FONT, size)   # SFNS.ttf absent → bundled Inter Bold
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f

# ---------------------------------------------------------------- chunking
SENT_END = (".", "?", "!", "…")
def chunk_lines(words, hook_end):
    """all words → list of {text,start,end}. Captions are always on (the hook card just
    overlays on top during the hook). Each line holds until the next begins."""
    post = list(words)
    lines, cur = [], []
    def flush():
        if cur:
            lines.append({
                "text": " ".join(w["disp"] for w in cur),
                "start": cur[0]["start"],
                "end": cur[-1]["end"],
                "nwords": len(cur),
                "rawdur": cur[-1]["end"] - cur[0]["start"],
            })
            cur.clear()
    for w in post:
        cur.append(w)
        joined = " ".join(x["disp"] for x in cur)
        ends_sentence = w["disp"].rstrip().endswith(SENT_END)
        if ends_sentence or len(cur) >= CAP_MAX_WORDS or len(joined) >= CAP_MAX_CHARS:
            flush()
    flush()
    # sub-0.2s single-word slivers never stand as their own line, and are NEVER dropped: the
    # canonical transcript is the kept-words script, so every word in it is shipped audio (the
    # drop deleted "His" and "that" through five review rounds, 2026-09-22). A sliver that
    # CONTINUES the previous line (no gap, e.g. a sentence-final "to." the 4-word cut left alone)
    # merges back into it (2026-09-08); an isolated one (a gap before it) opens the NEXT line,
    # which starts earlier to carry it, or merges back when no line follows
    merged, carry = [], None
    def join(a, b):
        a["text"] = a["text"] + " " + b["text"]
        a["end"] = b["end"]
        a["nwords"] += b["nwords"]
        a["rawdur"] = a["end"] - a["start"]
    for ln in lines:
        if ln["nwords"] == 1 and ln["rawdur"] < 0.20:
            if carry:
                join(carry, ln)
            elif merged and ln["start"] - merged[-1]["end"] <= 0.30:
                join(merged[-1], ln)
            else:
                carry = ln
            continue
        if carry:
            join(carry, ln)
            ln, carry = carry, None
        merged.append(ln)
    if carry:
        if merged:
            join(merged[-1], carry)
        else:
            merged.append(carry)
    lines = merged
    # hold each line until the next one starts (no flicker / no gaps mid-speech)
    for i in range(len(lines) - 1):
        lines[i]["end"] = lines[i + 1]["start"]
    if lines:
        lines[-1]["end"] = lines[-1]["end"] + CAP_HOLD_PAD
    return lines

def norm_words(texts, table):
    """lowercase alphanumerics of every token, the builder's spelling fixes applied first"""
    out = []
    for text in texts:
        for tok in text.split():
            for piece in correct(tok, table).split():
                n = re.sub(r"[^0-9a-z]", "", piece.lower())
                if n:
                    out.append(n)
    return out

def check_captions(words, lines, table):
    """captions == transcript, word for word and in order: a caption that loses or invents a word
    exits non-zero with the diff (nothing else compared them, and a dropped word shipped)"""
    want = norm_words([correct(w["text"], table) for w in words], table)
    got = norm_words([ln["text"] for ln in lines], table)
    if got != want:
        diff = difflib.unified_diff(want, got, "transcript", "captions", lineterm="")
        print("[tiktok-raw] ✗ captions != transcript:\n" + "\n".join(diff), file=sys.stderr)
        sys.exit(1)

def word_frame(t, fps):
    """The frame a moment belongs to: the first whose midpoint is at or after it (a half-frame tie goes late)."""
    return math.ceil(t * fps - 0.5 - 1e-9)


def check_onsets(words, lines, fps):
    """no line lights before its first word is spoken, 0 frames of lead: a line's first lit frame is the first whose
    TIME is at or after its start as the overlay writes it (between(t, start, end), to the ms), its first word's frame
    is word_frame(); a line that lights earlier exits non-zero, naming it. (A caption that shows a word before it is
    said reads as wrong, 2026-10-13; nothing here leads a word, and this keeps it so.)"""
    early, k = [], 0
    for ln in lines:
        w = words[k]["start"]
        k += ln["nwords"]
        lit = math.ceil(round(ln["start"], 3) * fps - 1e-6)
        if lit < word_frame(w, fps):
            early.append(f"  {ln['text']!r} lights on frame {lit} ({ln['start']:.3f}s), its first word on frame "
                         f"{word_frame(w, fps)} ({w:.3f}s)")
    if early:
        print("[tiktok-raw] ✗ caption line(s) light before their first word:\n" + "\n".join(early), file=sys.stderr)
        sys.exit(1)

# ---------------------------------------------------------------- wrapping
def wrap_to_width(text, font, max_w, draw):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = wd
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- rendering
def render_caption(text, font, draw_probe):
    lines = wrap_to_width(text, font, CAP_MAX_W, draw_probe)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    asc, desc = font.getmetrics()
    lh = asc + desc + CAP_LINE_GAP
    total_h = lh * len(lines)
    y = CAP_CENTER_Y - total_h / 2
    for ln in lines:
        d.text((W / 2, y), ln, font=font, fill=CAP_TEXT_COL, anchor="ma",
               stroke_width=CAP_STROKE, stroke_fill=CAP_STROKE_COL)
        y += lh
    return crop(img)

def render_hook(text, font):
    inner_w = HOOK_BOX_W - 2 * HOOK_PAD_X
    probe = ImageDraw.Draw(Image.new("RGBA", (W, H)))
    lines = []
    for para in text.split("\n"):
        lines += wrap_to_width(para, font, inner_w, probe) or [""]
    asc, desc = font.getmetrics()
    lh = asc + desc + HOOK_LINE_GAP
    # draw text on a scratch layer, then size the box to the ACTUAL ink extents
    # (not font ascent/descent) so the white box hugs the text instead of ballooning.
    scratch = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scratch)
    y = 120
    for ln in lines:
        sd.text((W / 2, y), ln, font=font, fill=HOOK_TEXT_COL, anchor="ma")
        y += lh
    bb = scratch.getbbox()
    if bb is None:
        # No ink (empty / whitespace-only hook). Without this guard scratch.crop(None)
        # returns the WHOLE 1080x1920 frame, ballooning the box to cover the footage.
        return crop(Image.new("RGBA", (W, H), (0, 0, 0, 0)))
    text_crop = scratch.crop(bb)
    box_w = text_crop.width + 2 * HOOK_PAD_X
    box_h = text_crop.height + 2 * HOOK_PAD_Y
    box_x = (W - box_w) // 2
    box_y = HOOK_TOP_Y
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h], radius=HOOK_RADIUS, fill=HOOK_FILL)
    out.alpha_composite(text_crop, (box_x + HOOK_PAD_X, box_y + HOOK_PAD_Y))
    assert box_y >= SAFE_TOP, "hook card crosses the top safe band"
    return crop(out)

def crop(img):
    bb = img.getbbox()
    if not bb:
        return img, 0, 0
    l, t, r, b = bb
    l, t = max(0, l - 4), max(0, t - 4)
    r, b = min(W, r + 4), min(H, b + 4)
    return img.crop((l, t, r, b)), l, t

# ---------------------------------------------------------------- ffmpeg
def cut_duration(job_dir, words):
    """Length of the cut with no flat render to probe: the EDL's kept seconds, else the last word."""
    cj = os.path.join(job_dir, "transcript", "cuts.json")
    if os.path.exists(cj):
        segs = json.load(open(cj, encoding="utf-8")).get("segments", [])
        if segs:
            return sum(float(s["end"]) - float(s["start"]) for s in segs)
    return max(w["end"] for w in words) + 0.5


def raw_fps(job_dir):
    """The timeline rate = the raw's rate (an overlay on the wrong grid drifts a frame per minute)."""
    raws = sorted(f for f in os.listdir(os.path.join(job_dir, "raw")) if f.lower().endswith((".mp4", ".mov")))
    if not raws:
        return "30000/1001"
    return video_rate(os.path.join(job_dir, "raw", raws[0])) or "30000/1001"


def video_rate(path):
    """The file's r_frame_rate as ffprobe prints it ('24000/1001'), '' when it has none."""
    r = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                 "stream=r_frame_rate", "-of", "csv=p=0", path]).decode()
    return (r.split() or [""])[0].rstrip(",")    # first row: ffprobe 9 prints a timecoded file's video row twice


def build(job_dir, until, hook_end_override, hook_text, out_path, alpha=False, scale=None, hook_only=False,
          deliver=False):
    job_dir = os.path.abspath(job_dir)
    job = os.path.basename(job_dir)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    src = os.path.join(job_dir, "outputs", f"{job}.mp4")
    tj = os.path.join(job_dir, "outputs", f"{job}.transcript.json")
    assert os.path.exists(tj), f"missing transcript: {tj}"
    if alpha:
        # the step-5 overlay (2026-09-04): no flat render exists on an app finish (RENDER=0),
        # so the layer is a transparent ProRes 4444 the lane's placer lays on the top graphics track
        src = None
        src_dur = cut_duration(job_dir, json.load(open(tj, encoding="utf-8"))["words"])
        fps = raw_fps(job_dir)
        raws = sorted(f for f in os.listdir(os.path.join(job_dir, "raw")) if f.lower().endswith((".mp4", ".mov")))
        base_w = base_upright_width(os.path.join(job_dir, "raw", raws[0]))
    else:
        assert os.path.exists(src), f"missing render: {src}"
        src_dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", src]).decode().strip())
        base_w = base_upright_width(src)
    # auto: the base's upright width over the locked 1080 authoring width (2160 → 2x)
    scale = float(scale) if scale else base_w / 1080.0
    apply_scale(scale)

    table = load_corrections(repo_root)
    words = json.load(open(tj, encoding="utf-8"))["words"]
    for w in words:
        w["disp"] = correct(w["text"], table)

    # hook end = end of the last hook word (auto: the first sentence break)
    if hook_end_override is not None:
        hook_end = hook_end_override
    else:
        hook_end = None
        for w in words:
            if w["text"].rstrip().endswith(SENT_END):
                hook_end = w["end"] + 0.10; break
        hook_end = hook_end or 5.0

    work = os.path.join((tempfile.gettempdir() if os.name == "nt" else "/tmp"), "video-editor", job, "tiktok-raw")
    os.makedirs(work, exist_ok=True)
    for stale in glob.glob(os.path.join(work, "*.png")):   # never a shell `rm`: cmd.exe on Windows passes the glob
        os.remove(stale)                                    # through unexpanded and every stale overlay stayed

    cap_font = load_font(CAP_SIZE, CAP_WEIGHT)
    hook_font = load_font(HOOK_SIZE, HOOK_WEIGHT)
    probe = ImageDraw.Draw(Image.new("RGBA", (W, H)))

    overlays = []   # (png_path, x, y, start, end)

    # hook card — skip entirely when there's no hook text (e.g. an unset DEFAULT_HOOK_TEXT),
    # so an empty hook is a clean no-op (captions still run) instead of a frame-covering box.
    if hook_text and hook_text.strip():
        himg, hx, hy = render_hook(hook_text, hook_font)
        hp = os.path.join(work, "hook.png"); himg.save(hp)
        overlays.append((hp, hx, hy, 0.0, hook_end))

    # captions
    lines = chunk_lines(words, hook_end)
    check_captions(words, lines, table)   # the whole script, before any --until / --hook-only trim
    check_onsets(words, lines, float(Fraction(fps if alpha else video_rate(src) or "30000/1001")))
    if hook_only:
        # the hook card as its OWN overlay (the plan's hook cell): no captions, clip ends at hook_end,
        # so the placer lays it and the caption layer as two trimmable clips
        lines, until = [], hook_end
    if until:
        lines = [ln for ln in lines if ln["start"] < until]
    for i, ln in enumerate(lines):
        img, x, y = render_caption(ln["text"], cap_font, probe)
        p = os.path.join(work, f"cap_{i:03d}.png"); img.save(p)
        end = min(ln["end"], until) if until else ln["end"]
        overlays.append((p, x, y, ln["start"], end))

    # ffmpeg overlay chain
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    fc, last = [], "0:v"
    if alpha:
        # format=rgba INSIDE the source graph: negotiated afterwards the color source picks a no-alpha
        # format first and the layer ships opaque (caught on the first test render, 2026-09-04)
        cmd += ["-f", "lavfi", "-i", f"color=c=black@0.0:s={W}x{H}:r={fps}:d={src_dur:.3f},format=rgba"]
    else:
        cmd += ["-i", src]
    for ov in overlays:
        cmd += ["-loop", "1", "-i", ov[0]]
    for idx, ov in enumerate(overlays, start=1):
        _, x, y, s, e = ov
        nxt = f"v{idx}"
        # the alpha layer composites in RGB, so its one conversion to YUV is the BT.709 one below
        fc.append(f"[{last}][{idx}:v]overlay={x}:{y}:enable='between(t,{s:.3f},{e:.3f})'{':format=rgb' if alpha else ''}[{nxt}]")
        last = nxt
    if alpha:
        # BT.709 matrix, tagged: ffmpeg's default RGB->YUV is BT.601 with no tags, and an editing app reads untagged HD
        # as 709, so any colour shifts (2026-10-13). An explicit scale, never bare tag flags (older ffmpeg only tags).
        fc.append(f"[{last}]scale=out_color_matrix=bt709:out_range=tv,"
                  f"setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=tv[c709]")
        last = "c709"
    filter_complex = ";".join(fc)
    # ALWAYS bound the output: the -loop 1 image inputs never EOF, so without -t the render
    # runs away past the base video. Cap at the preview length, else the source duration.
    tcap = min(until, src_dur) if until else src_dur
    if alpha:
        # straight alpha, the same ProRes 4444 every other overlay ships as (CapCut premultiplies later)
        cmd += ["-filter_complex", filter_complex, "-map", f"[{last}]", "-t", f"{tcap:.3f}",
                "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-an", out_path]
    else:
        cmd += ["-filter_complex", filter_complex, "-map", f"[{last}]", "-map", "0:a",
                "-t", f"{tcap:.3f}"]
        # Apple HW encoder on macOS; libx264 everywhere else (Windows/Linux) — see splice.sh. With deliver (the
        # clipper's .final.mp4 IS a deliverable), the vertical file's numbers from workflows/deliver.py instead.
        if deliver:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "deliver", os.path.join(repo_root, "workflows", "deliver.py"))
            dv = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(dv)
            rate = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                            "stream=r_frame_rate", "-of", "csv=p=0", src]).decode().split()[0].rstrip(",")
            num, den = (int(x) for x in rate.split("/"))
            size = "" if base_w == 1080 else "scale=1080:1920:flags=lanczos,"
            venc = dv.video_args(dv.reels_mbps(tcap), "4.2", max(1, round(num / den / 2)), rate)
            cmd[cmd.index("-filter_complex") + 1] = filter_complex + f";[{last}]{size}{dv.TAGS}[dlv]"
            cmd[cmd.index("-map") + 1] = "[dlv]"
        elif platform.system() == "Darwin":
            venc = ["-c:v", "h264_videotoolbox", "-b:v", "10M"]
        else:
            venc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
        # audio is unfiltered (mapped straight from the base cut) — stream-copy it;
        # re-encoding here was a second lossy AAC generation below the splice's 256k
        cmd += [*venc, "-c:a", "copy",
                "-movflags", "+faststart", out_path]

    print(f"[tiktok-raw] {'ALPHA overlay' if alpha else 'burn'}  {W}x{H} (scale {scale:g})  hook_end={hook_end:.2f}s  caption_lines={len(lines)}  overlays={len(overlays)}  dur={tcap:.3f}s")
    print(f"[tiktok-raw] rendering → {out_path}")
    subprocess.run(cmd, check=True)
    print(f"[tiktok-raw] done: {out_path}")
    # echo the caption sheet for review
    for i, ln in enumerate(lines):
        print(f"  {ln['start']:6.2f}-{ln['end']:6.2f}  {ln['text']}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("job_dir")
    ap.add_argument("--until", type=float, default=None, help="preview length cap (seconds)")
    ap.add_argument("--hook-end", type=float, default=None, help="override hook card end (seconds)")
    ap.add_argument("--hook-text", default=DEFAULT_HOOK_TEXT)
    ap.add_argument("--out", default=None)
    ap.add_argument("--alpha", action="store_true",
                    help="the step-5 layer: a transparent ProRes 4444 overlay for the lane's placer "
                         "(default out: <job>/hf-graphics/captions/renders/captions-alpha.mov); needs no flat render")
    ap.add_argument("--scale", type=float, default=None,
                    help="render the locked 1080x1920 layout at this factor (default: auto from the base's "
                         "upright width, 2160 → 2); the look is unchanged, only the raster size")
    ap.add_argument("--hook-only", action="store_true",
                    help="emit ONLY the hook card (no captions), ending at hook_end, so the hook cell and the "
                         "caption layer place as two separate clips (default out with --alpha: "
                         "<job>/hf-graphics/gfx/renders/<hook-id>-alpha.mov, set --out)")
    ap.add_argument("--deliver", action="store_true",
                    help="the burn IS the deliverable (clipper's .final.mp4): the vertical file's numbers from "
                         "workflows/deliver.py (1080x1920 H.264 High 4.2 CBR 14, less past 2:48) instead of the preview encoder")
    a = ap.parse_args()
    job_abs = os.path.abspath(a.job_dir)
    job = os.path.basename(job_abs)
    if a.alpha and a.hook_only:
        out = a.out or os.path.join(job_abs, "hf-graphics", "gfx", "renders", "hook-alpha.mov")
    elif a.alpha:
        out = a.out or os.path.join(job_abs, "hf-graphics", "captions", "renders", "captions-alpha.mov")
    else:
        out = a.out or os.path.join((tempfile.gettempdir() if os.name == "nt" else "/tmp"), "video-editor", job, "tiktok-raw", "preview.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build(a.job_dir, a.until, a.hook_end, a.hook_text, out, alpha=a.alpha, scale=a.scale, hook_only=a.hook_only,
          deliver=a.deliver)
