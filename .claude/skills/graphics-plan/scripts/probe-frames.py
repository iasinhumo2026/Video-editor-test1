#!/usr/bin/env python3
"""probe-frames.py — extract one frame per beat so the graphics plan is grounded
in what the footage actually shows (face position, screen recordings, gestures).

Beat times live on the CUT timeline (the canonical transcript). On app-finish
jobs there is no flat render (RENDER=0), so each beat time is mapped back
through the EDL (transcript/cuts.json, source seconds, butt-joined in order)
to a source time in the raw footage and the frame is pulled from the raw.
If outputs/<job>.mp4 exists it is used directly instead (same timeline).

usage:
  probe-frames.py <job_dir> <beats.json> [out_dir]

<beats.json> = the scaffold from segment-script.py (or any JSON with
beats:[{id,start,...}]).  Frames land in <job_dir>/plan-frames/beat-<id>.jpg
(regenerable scratch — re-runnable at any time).
Grabs the frame at each beat's midpoint, not its start: starts sit on cut
boundaries where the previous shot may still be decaying.
"""
import json
import os
import subprocess
import sys

for s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252
    if hasattr(s, "reconfigure"):
        s.reconfigure(encoding="utf-8", errors="replace")


def die(msg):
    print(f"probe-frames: {msg}", file=sys.stderr)
    sys.exit(1)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) < 3:
        die(__doc__.strip().splitlines()[0] + "  (usage: probe-frames.py <job_dir> <beats.json> [out_dir])")
    job_dir, beats_path = sys.argv[1].rstrip("/"), sys.argv[2]
    job = os.path.basename(job_dir)
    out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(job_dir, "plan-frames")

    data = load(beats_path)
    beats = data["beats"] if isinstance(data, dict) else data

    flat = os.path.join(job_dir, "outputs", f"{job}.mp4")
    segs = None
    if os.path.exists(flat):
        src_for = lambda t: (flat, t)  # flat render already lives on the cut timeline
    else:
        cuts = os.path.join(job_dir, "transcript", "cuts.json")
        if not os.path.exists(cuts):
            die(f"no flat render ({flat}) and no EDL ({cuts}) — run rough-cut first")
        cj = load(cuts)
        segs = cj["segments"] if isinstance(cj, dict) else cj
        raws = [os.path.join(job_dir, "raw", f) for f in sorted(os.listdir(os.path.join(job_dir, "raw")))
                if f.lower().endswith((".mp4", ".mov", ".mkv"))]

        def seg_file(seg):
            f = seg.get("clip") or seg.get("file")  # rough-cut writes `clip`; older hand EDLs wrote `file`
            media = seg.get("media")
            if media and not any(os.path.basename(r) == os.path.basename(f or "") for r in raws):
                # an insert (a meme, a b-roll clip) laid from its own file on its own clock: no raw/ file of that name
                # exists, so the grab failed and the beat was planned blind. A lip-sync re-take names the raw as its
                # clip and runs on the raw's clock, so it keeps the raw's frame (the same framing)
                return media if os.path.isabs(media) else os.path.join(job_dir, media)
            if f:
                return f if os.path.isabs(f) else os.path.join(job_dir, "raw", os.path.basename(f))
            if len(raws) == 1:
                return raws[0]
            die(f"multiple raw files and segment has no 'clip' (or 'file') key — pass frames by hand: {raws}")

        # butt-joined EDL: cut-timeline position of segment i = sum of prior durations
        cum = []
        t = 0.0
        for s in segs:
            d = float(s["end"]) - float(s["start"])
            cum.append((t, t + d, s))
            t += d

        def src_for(ct):
            for lo, hi, s in cum:
                if lo <= ct < hi or (s is cum[-1][2] and ct >= hi):
                    return seg_file(s), float(s["start"]) + min(ct - lo, hi - lo - 0.001)
            die(f"beat time {ct:.2f}s falls outside the EDL ({cum[-1][1]:.2f}s total)")

    os.makedirs(out_dir, exist_ok=True)
    ok = 0
    for b in beats:
        mid = (float(b["start"]) + float(b["end"])) / 2.0
        src, st = src_for(mid)
        out = os.path.join(out_dir, f"beat-{b['id']}.jpg")
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{st:.3f}",
             "-i", src, "-frames:v", "1", "-q:v", "3", "-y", out],
            capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out):
            ok += 1
        else:
            print(f"  ! beat {b['id']}: frame grab failed at {st:.2f}s of {os.path.basename(src)}",
                  file=sys.stderr)
    print(f"{ok}/{len(beats)} frames -> {out_dir}")


if __name__ == "__main__":
    main()
