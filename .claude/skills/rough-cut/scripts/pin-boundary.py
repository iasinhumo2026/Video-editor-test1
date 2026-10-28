#!/usr/bin/env python3
"""pin-boundary.py — address a segment by WHAT IT IS, then pin its boundary.

A hand fix to one boundary (a stutter trimmed out, a clipped onset moved, a false start killed) is
written into the EDL as an explicit start/end plus `"no_refine": true`. Picking the segment by time
alone is what goes wrong: neighbouring segments sit 0.3-0.5 s apart, so a nearest-start match lands
on the wrong one and the fix is applied to an edit nobody meant to touch (your-job 2026-09-18: a pin
meant for a clipped "MP3." onset moved "this in" instead, costing a full author -> splice -> polish
-> pin cycle from clean). So `expect` is REQUIRED here: it refuses instead of picking, and prints
the segment it landed on so the log proves the pin.

Import it from a job's own fix script (both live beside the EDL they repair):

    import importlib.util, json, sys
    from pathlib import Path
    _p = Path(".claude/skills/rough-cut/scripts/pin-boundary.py")
    _s = importlib.util.spec_from_file_location("pin_boundary", _p)
    pb = importlib.util.module_from_spec(_s); _s.loader.exec_module(pb)

    edl = json.load(open(pb.edl_path("<job>")))
    S = edl["segments"]
    pb.pin(pb.seg(S, "walkthrough.mp4", 656.9, expect="MP3"), start=657.15)
    json.dump(edl, open(pb.edl_path("<job>"), "w"), indent=1)

`edl_path` is splice.sh's working EDL, named as polish-boundaries.py names it: a literal /tmp/video-editor/<job> is
C:\\tmp on Windows, where Git Bash's /tmp (what splice.sh reads) is %TEMP%.

Stdlib only. `cut-audit.py`'s "pin_in" / "pin_out" are the AUDIT's pins and a different thing:
`no_refine` pins a boundary against the refiner and the polish, `pin_in` / `pin_out` pin it against
the audit's own re-derivation (rough-cut SKILL.md § Audit the cut on the finish surface's grid).
"""
import os
import re
import sys
import tempfile

WINDOW_S = 0.5   # how far from a segment's own edges a pin time may sit


def edl_path(job):
    """splice.sh's working EDL for <job>: /tmp/video-editor/<job>/cuts.json, and on Windows the temp folder Git Bash
    calls /tmp (native Python reads a literal /tmp as C:\\tmp; polish-boundaries.scratch_root is the same rule)."""
    return os.path.join(tempfile.gettempdir() if os.name == "nt" else "/tmp", "video-editor", job, "cuts.json")


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", str(s).lower()).strip()


def seg(segments, clip, t, expect, window=WINDOW_S):
    """The ONE segment of `clip` near `t` whose transcript contains `expect`. Refuses otherwise.

    `expect` is required and is matched on the transcript with punctuation and case ignored."""
    if not expect:
        raise SystemExit(f"pin @{t}: expect= is required — a pin is asserted on text, never on time alone")
    near = [s for s in segments
            if os.path.basename(s["clip"]) == os.path.basename(clip)
            and float(s["start"]) - window <= t <= float(s["end"]) + window]
    if not near:
        raise SystemExit(f"pin @{t}: no segment within {window}s on {os.path.basename(clip)}")
    hit = [s for s in near if norm(expect) in norm(s.get("transcript", ""))]
    if len(hit) != 1:
        raise SystemExit(
            f"pin @{t} expect={expect!r}: matched {len(hit)} of {len(near)} segments near it — "
            + " | ".join(f"[{float(s['start']):.2f}-{float(s['end']):.2f}] "
                         f"{s.get('transcript', '')[:50]!r}" for s in near))
    s = hit[0]
    print(f"pin @{t} -> [{float(s['start']):.2f}-{float(s['end']):.2f}] "
          f"{s.get('transcript', '')[:60]!r}", file=sys.stderr)
    return s


def pin(segment, **kw):
    """Set the boundaries given (start=/end=) and pin the segment against the refiner + polish."""
    for k, v in kw.items():
        if k not in ("start", "end", "beat", "keep_pauses", "pin_in", "pin_out", "transcript"):
            raise SystemExit(f"pin: {k!r} is not a segment field this helper sets")
        segment[k] = v
    segment["no_refine"] = True
    return segment


if __name__ == "__main__":
    sys.exit(__doc__)
