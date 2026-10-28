#!/usr/bin/env python3
"""assemble.py: the chat-only lane's composite (LANES.md steps 5' and 5): the base cut, its footage laid out per the
plan's layout map, every placed graphic over it, the caption layer last. One ffmpeg pass; the base is never
re-rendered by graphics and its audio rides through untouched.

  uv run lanes/chat-only/assemble.py projects/<job>               -> hf-graphics/renders/final.mp4
  uv run lanes/chat-only/assemble.py projects/<job> --out <mp4>
  uv run lanes/chat-only/assemble.py projects/<job> --shorts --out projects/<job>/hf-graphics/renders/final-shorts.mp4
        # a 2160x3840 base's second composite, the 4K YouTube Shorts file's (its audio passes write outputs/shorts/)

On this lane the assemble render IS the deliverable's picture (LANES.md § step 8; mix-sfx.py and mix-music.sh only copy
its video), so it is encoded ONCE at the format's export numbers, workflows/deliver.py's (the presets' § Export: a
vertical base -> 1080x1920 H.264 High 4.2 CBR 14, less past 2:48; a landscape one -> 3840x2160 High 5.1 CBR 50, 80
above 30 fps; --shorts on a 2160x3840 base -> the YouTube Shorts file), bt709 on the frames, closed GOP, moov first. It
encoded CRF 16 with primaries and transfer untagged until 2026-10-13. The base's audio is copied (the splice's AAC
256k; mix-sfx.py's 320k 48 kHz re-encode follows on every job, an empty SFX plan included).

Reads outputs/<job>.mp4 (the base cut), hf-graphics/placement.json (the placed rows: id, kind, start, end, file) and,
on a layout-rotation preset (the Talking Head Explainer), graphics-plan.json `layout` + face-frame.json `modes`
through the preset's layout.py: the base is cut at the layout edges and each span gets its footage transform (a row's
own `frame` over its mode's; S slides the frame, T punches in about the face, W is untouched; F and O keep W's
footage under their graphic; hard cuts, no ramps: layout.md § 2). A plan without `layout` keeps the footage as it is.

The mechanics below were each forced by a flash-scan FAIL on the Windows test job (2026-09-27) and stay exactly so:
  · layout edges cut FRAME-exact (trim=start_frame/end_frame): a float-second trim (14.8148 = frame 443.998) rounded
    a frame early, and every layout switch landed a frame before its graphic;
  · each overlay is placed FRAME-exact with setpts=(N+f0)/fps: a float -itsoffset ran it a frame early;
  · each overlay carries a one-frame tpad: with eof_action=pass ffmpeg never shows an overlay's LAST frame;
  · each overlay's enable window sits half a frame inside the frame grid: between(t, start, end) on float seconds
    missed the first frame whenever t and start differed in the last digit.
The caption layer goes on last. Built by captions.py --straight-alpha --ver sa (hf-graphics/captions/renders/
captions-alpha-sa*.mov) it composites as approved: ffmpeg's overlay blends straight alpha in gamma space
(incremental-graphics.md). Without --ver sa the straight build is written over captions-alpha.mov, which nothing can tell
from the linear-light build Premiere takes. The stutter guardrail measures the composite in the same pass, before the
lossy encode (which re-codes a repeated frame with a residual, so a count on the encoded file read 0.0 % on a 25 %
cadence: the 2026-10-13 audit): frames repeating the previous on a cadence (signalstats YDIF == 0, in runs of at most
CADENCE; a longer run is a hold, a still full-screen or a still page) beyond the base's own share, 8 % or more exits 1.
The deliverable is SDR Rec.709, tagged bt709 three times as Premiere's export.py stamps it (an untagged screen
recording's base otherwise ships "unknown"), and the tags are read back; an HLG or PQ (HDR) base is refused before
anything is encoded, as splice.sh refuses the raw (2026-10-13).
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parents[2]
LAYOUT = REPO / "presets" / "instagram" / "talking-head-explainer" / "layout.py"
DELIVER = REPO / "workflows" / "deliver.py"
DUP_LIMIT = 0.08
CADENCE = 2   # a run of at most this many identical frames is a repeat cadence (24 -> 30 repeats one, 10 -> 30 two)


def probe(path):
    d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate", "-of", "json", str(path)],
                                  capture_output=True, text=True, check=True).stdout)["streams"][0]
    return int(d["width"]), int(d["height"]), d["r_frame_rate"]


HDR = {"arib-std-b67": "HLG", "smpte2084": "PQ"}
BT709 = ("bt709", "bt709", "bt709")


def colour(path):
    """(color_primaries, color_transfer, color_space) of the first video stream, '' where untagged."""
    d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=color_primaries,color_transfer,color_space", "-of", "json", str(path)],
                                  capture_output=True, text=True, check=True).stdout)["streams"][0]
    return tuple(d.get(k, "") for k in ("color_primaries", "color_transfer", "color_space"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def layout_module():
    return _load("thx_layout", LAYOUT)


def seconds(path):
    """the base's duration (s): what sets the vertical file's bitrate past 2:48"""
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                 str(path)], capture_output=True, text=True, check=True).stdout.split()[0].rstrip(","))


def export_encode(W, H, rate, secs, shorts=False):
    """(the filter tail after the composite, the ffmpeg video args, a one-line description): deliver.py's numbers for
    this frame, so the assemble render is the deliverable as encoded (LANES.md § step 8)."""
    dv = _load("deliver", DELIVER)
    fr = Fraction(rate)
    OW, OH, mbps, level, _ = dv.target(W, H, float(fr), secs, shorts)
    size = f",scale={OW}:{OH}:flags=lanczos" if (OW, OH) != (W, H) else ""
    return (f"format=yuv420p{size},{dv.TAGS}", dv.video_args(mbps, level, max(1, round(float(fr) / 2)), rate),
            f"{OW}x{OH} H.264 High {level} CBR {mbps}")


def footage_chain(job, plan, W, H, fps, FPS):
    """(filter pieces, label) laying the base's footage out per the layout map; None when the plan has no layout."""
    if not plan.get("layout"):
        return None
    L = layout_module()
    md = L.modes(json.loads((job / "face-frame.json").read_text(encoding="utf-8")))
    fc, labels = [], []
    for k, (a, b, _key, m) in enumerate(L.footage_spans(plan, md)):
        s, (cx, cy) = float(m["scale"]), m["centre"]
        sw, sh = round(W * s / 2) * 2, round(H * s / 2) * 2
        x, y = round(cx * W - sw / 2), round(cy * H - sh / 2)
        f0, f1 = round(a * FPS), round(b * FPS)
        fc.append(f"[0:v]trim=start_frame={f0}:end_frame={f1},setpts=PTS-STARTPTS,scale={sw}:{sh}:flags=lanczos[s{k}];"
                  f"color=c=black:s={W}x{H}:r={fps}[bg{k}];[bg{k}][s{k}]overlay=x={x}:y={y}:shortest=1,setsar=1[v{k}]")
        labels.append(f"[v{k}]")
    fc.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[foot]")
    return fc, "foot"


def overlay_rows(job):
    """The placed overlays, the caption layer last (its straight-alpha build when one exists)."""
    pl = json.loads((job / "hf-graphics" / "placement.json").read_text(encoding="utf-8"))
    rows = pl["rows"] if isinstance(pl, dict) else pl
    orphans = [f"{r.get('id', '?')} at {float(r.get('start') or 0):.3f}s" for r in rows if r.get("ripple") == "orphaned"]
    if orphans:                     # a re-cut deleted their anchor (ripple-cut.py): laid, they sit at pre-recut times
        sys.exit(f"✗ placement row(s) orphaned by a re-cut: {', '.join(orphans)}. Re-anchor or delete each row, re-run "
                 "workflows/placement.py --write, then assemble (every placer refuses them, never lays them)")
    out, caps = [], []
    for r in rows:
        f = Path(r["file"])
        f = f if f.is_absolute() else job / f
        if not f.exists():
            sys.exit(f"✗ {r.get('id')}: {f} is not rendered")
        (caps if r.get("kind") == "captions" else out).append({**r, "file": str(f)})
    for c in caps:
        sa = sorted((job / "hf-graphics" / "captions" / "renders").glob("captions-alpha-sa*.mov"),
                    key=lambda p: p.stat().st_mtime)
        if sa:
            c["file"] = str(sa[-1])
        else:
            print(f"⚠ no straight-alpha caption build (captions-alpha-sa*.mov): {Path(c['file']).name} is taken as the "
                  "linear-light build, which composites heavier than approved over ffmpeg's gamma-space blend; build it "
                  "with captions.py projects/<job> --straight-alpha --ver sa", file=sys.stderr)
    return out + caps


YDIF = "signalstats,metadata=print:key=lavfi.signalstats.YDIF:file={},nullsink"   # a measuring branch's end


def dup_share(path):
    """(frames, share repeating the previous frame on a cadence) from a YDIF branch's metadata file. A longer run of
    identical frames is a hold (a still full-screen, a still page), never the stutter: the guard counted every one, and
    a 3 s static card exited 1 on a clean edit (2026-10-13)."""
    ydif = [float(l.split("=")[1]) for l in Path(path).read_text(encoding="utf-8").splitlines() if "YDIF=" in l]
    runs, run = [], 0
    for v in ydif[1:]:
        if v == 0.0:
            run += 1
        else:
            runs.append(run)
            run = 0
    runs.append(run)
    return len(ydif), sum(r for r in runs if r <= CADENCE) / max(1, len(ydif) - 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Composite a chat-only job: footage layout, overlays, captions.")
    ap.add_argument("job")
    ap.add_argument("--out", help="default: hf-graphics/renders/final.mp4")
    ap.add_argument("--shorts", action="store_true",
                    help="a 2160x3840 base: encode the 4K YouTube Shorts file (deliver.py --shorts), not the 1080x1920 one")
    a = ap.parse_args(argv)
    job = Path(a.job).resolve()
    base = job / "outputs" / f"{job.name}.mp4"
    if not base.exists():
        sys.exit(f"✗ no base cut at {base}: splice it first (rough-cut, RENDER=1)")
    hdr = HDR.get(colour(base)[1])
    if hdr:
        sys.exit(f"✗ {base.name} is {hdr} (HDR): the chat-only deliverable is SDR Rec.709. Finish this job in an "
                 "editing app, or convert the raw to Rec.709 SDR once and re-cut (edit-video § Step 0)")
    plan = json.loads((job / "graphics-plan.json").read_text(encoding="utf-8"))
    W, H, rate = probe(base)
    fps = str(plan.get("fps") or rate)
    FPS = float(Fraction(fps))
    out = (Path(a.out) if a.out else job / "hf-graphics" / "renders" / "final.mp4").resolve()  # ffmpeg runs elsewhere

    inputs, fc = ["-i", str(base)], []
    lay = footage_chain(job, plan, W, H, fps, FPS)
    if lay:
        fc += lay[0]
        last = lay[1]
    else:
        fc.append("[0:v]null[foot]")
        last = "foot"
    rows = overlay_rows(job)
    for i, r in enumerate(rows, start=1):
        inputs += ["-i", r["file"]]
        f0 = round(float(r["start"]) * FPS)
        h = 0.5 / FPS
        a_, b_ = f0 / FPS - h, round(float(r["end"]) * FPS) / FPS - h
        fc.append(f"[{i}:v]tpad=stop=1:stop_mode=clone,setpts=(N+{f0})/({fps})/TB[g{i}]")
        fc.append(f"[{last}][g{i}]overlay=eof_action=pass:enable='between(t,{a_:.6f},{b_:.6f})'[o{i}]")
        last = f"o{i}"
    # the tags ride the FRAMES (deliver.py's TAGS, in export_encode's tail) and the output options (its video_args):
    # ffmpeg 8+ lets an untagged base's frame properties override the -color_* options, which then tag colorspace alone
    tail, venc, enc = export_encode(W, H, fps, seconds(base), a.shorts)
    # the stutter guardrail reads the composite here, before the lossy encode, and the base on the same pass: the
    # identical frames the composite ADDS are the stutter. fps= is the plan-rate conversion the encoder's -r made after
    # the graph, out of the guard's sight (a 24 fps base under a 30 fps plan repeats every 4th frame)
    fc.append(f"[{last}]fps={fps}:eof_action=pass,split[enc][chk]")
    fc.append("[chk]" + YDIF.format("comp.ydif"))
    fc.append("[0:v]" + YDIF.format("base.ydif"))
    fc.append(f"[enc]{tail}[vout]")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:   # the YDIF files land here: a bare name needs no filtergraph escaping
        subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(fc), "-map", "[vout]",
                        "-map", "0:a", *venc, "-c:a", "copy", "-movflags", "+faststart", str(out)], check=True, cwd=td)
        n, dups = dup_share(Path(td) / "comp.ydif")
        own = dup_share(Path(td) / "base.ydif")[1]
    if colour(out) != BT709:
        sys.exit(f"✗ {out} reads {'/'.join(c or '?' for c in colour(out))}, not bt709/bt709/bt709")
    print(f"-> {out}  ({len(rows)} overlay(s){', layout keyed' if lay else ''}; {enc}; {n} frames, "
          f"{100 * dups:.1f}% repeating the previous on a cadence, {100 * own:.1f}% in the base)")
    if dups - own >= DUP_LIMIT:
        plan_rate = (f"a plan fps ({fps}) other than the base's rate ({rate}), "
                     if Fraction(fps) != Fraction(rate) else "")
        sys.exit(f"✗ {100 * (dups - own):.1f}% duplicated frames added by the composite (the stutter trap, "
                 f"incremental-graphics.md): {plan_rate}an overlay without eof_action=pass, or a slow input")
    return 0


if __name__ == "__main__":
    sys.exit(main())
