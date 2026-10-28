#!/usr/bin/env python3
"""mix-sfx.py: the chat-only lane's SFX pass (LANES.md § step 6). Every row of hf-graphics/sfx-plan.json (at, file,
src_in, src_out, level_db, fade_out_s) is cut to its slice, levelled, faded where the plan says, delayed to its
timeline second and summed onto the render's own dialogue, never normalised; the video is stream-copied.

  uv run lanes/chat-only/mix-sfx.py projects/<job> <in.mp4> <out.mp4>

Refuses a row orphaned by a re-cut and a plan whose graphic moved since it was derived while its cues did not
(sfx-plan.py's stale_gids). Run it on the assemble render (lanes/chat-only/assemble.py), before the optional music
bed (mix-music.sh). The AAC
re-encode is 320k at 48 kHz, the export numbers' audio and above the splice's 256k (downstream steps never degrade the
voice), so it runs on a job with no cue too: an empty plan ([]) mixes nothing and still gives the deliverable that audio
(the assemble copies the base's). The plan's levels are the preset's, and sfx-plan.py has already held every stack of
cues to -1 dBTP on the mix.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252: the ✗ exit printed as an escape code (2026-10-13)
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parents[2]


def moved_graphics(hf):
    """The graphics that moved since sfx-plan.json was derived while their cues did not (sfx-plan.py's stale_gids,
    what place-sfx.py warns on); [] when none or when there is no placement record to compare."""
    if not (hf / "placement.json").exists():
        return []
    spec = importlib.util.spec_from_file_location("sfx_plan", REPO / "workflows" / "sfx-plan.py")
    planner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(planner)
    return planner.stale_gids(hf / "sfx-plan.json", hf) or []


def main(argv=None):
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 3:
        sys.exit(__doc__)
    job, src, dst = Path(a[0]).resolve(), a[1], a[2]
    rows = json.loads((job / "hf-graphics" / "sfx-plan.json").read_text(encoding="utf-8"))
    rows = rows["rows"] if isinstance(rows, dict) else rows
    orphans = [str(r.get("id", "?")) for r in rows if r.get("ripple") == "orphaned"]
    if orphans:                     # a re-cut deleted their anchor (ripple-cut.py): mixed, they land at pre-recut times
        sys.exit(f"✗ sfx row(s) orphaned by a re-cut: {', '.join(orphans)}. Re-run workflows/sfx-plan.py, then mix")
    moved = moved_graphics(job / "hf-graphics")
    if moved:                       # a graphic moved by hand after the plan: mixed, its cues land where it used to be
        sys.exit(f"✗ graphic(s) moved since sfx-plan.json was derived, their cues did not: {', '.join(moved)}. Re-plan "
                 f"them (uv run workflows/sfx-plan.py <job> --merge {','.join(moved)}), or --record when the cues are "
                 "right, then mix")
    ins, fc, mix = ["-i", src], [], ["[0:a]"]
    for i, r in enumerate(rows, start=1):
        f = Path(r["file"])
        if not f.is_absolute():
            f = REPO / "assets" / "sfx" / r["file"]
        if not f.exists():
            hit = next((REPO / "assets" / "sfx").rglob(Path(r["file"]).name), None)
            if hit is None:
                sys.exit(f"✗ {r.get('id')}: no {Path(r['file']).name} in assets/sfx")
            f = hit
        s0, s1 = float(r["src_in"]), float(r["src_out"])
        fade = float(r.get("fade_out_s") or 0)
        ins += ["-i", str(f)]
        fc.append(f"[{i}:a]atrim={s0}:{s1},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
                  f"volume={float(r['level_db'])}dB"
                  + (f",afade=t=out:st={max(0.0, s1 - s0 - fade):.4f}:d={fade:.4f}" if fade else "")
                  + f",adelay={int(round(float(r['at']) * 1000))}:all=1[s{i}]")
        mix.append(f"[s{i}]")
    fc.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0[a]")
    # -map_chapters 0: the render's own chapters, never a sound's. ffmpeg copies them from the first input that has
    # any, and the pack's "Pop 1.wav" carries two, which shipped as a chapter text track in the deliverable (2026-09-27)
    # Windows caps a command line at 32,767 characters and each cue adds ~260 (its -i and its chain): 150 cues died with
    # WinError 206 (2026-10-13). There the graph goes in a file, read with the option this ffmpeg has
    # (ffmpeg_compat.graph_file(): -/filter_complex from 7.0, -filter_complex_script on 5.1 to 6.1).
    graph = ";".join(fc)
    Path(dst).parent.mkdir(parents=True, exist_ok=True)     # a Shorts file's first write into outputs/shorts/
    with tempfile.TemporaryDirectory() as td:
        if os.name == "nt" and len(graph) > 8000:
            sys.path.insert(0, str(REPO / "workflows"))
            from ffmpeg_compat import graph_file
            gf = Path(td) / "mix-sfx.filter_complex.txt"
            gf.write_text(graph, encoding="utf-8")
            fco = [graph_file(), str(gf)]
        else:
            fco = ["-filter_complex", graph]
        subprocess.run(["ffmpeg", "-y", "-v", "error", *ins, *fco, "-map", "0:v", "-map", "[a]",
                        "-map_chapters", "0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                        "-movflags", "+faststart", dst],
                       check=True)
    print(f"-> {dst}  ({len(rows)} sounds mixed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
