#!/usr/bin/env python3
"""refine-cuts.py — measured onset/offset boundary refinement (the "clipped attack" fix).

WhisperX word-START timestamps run ~50-100 ms LATE vs the real acoustic onset
(measured on real footage: a word timestamped 50.212 whose attack begins at 50.113),
so a cut authored at word.start minus a fixed pad still lands INSIDE the word and
chops its attack. Word-END timestamps run early the same way, clipping decays.

This is NOT a silence-snapper and does not violate the "don't auto-snap cuts to
silence" gotcha: the words Claude chose stay fixed. Per
boundary we MEASURE the chosen word's acoustic edge on a 5 ms RMS envelope of the
raw audio, then move the cut just outside it — clamped so it can never cross the
adjacent word's timestamps or leave the local gap. If there is no clean gap
(continuous speech, deliberate mid-flow split), the authored boundary is untouched.

In-point:  cut = onset − 40 ms   (onset = end of the last sustained-quiet run
                                  before the first kept word's audio)
Out-point: cut = offset + 50 ms  (offset = start of the first sustained-quiet run
                                  after the last kept word's audio)

Both margins exceed a half-frame at 23.976 fps (20.9 ms), so splice.sh's frame-grid
snap can never round the cut back into the word.

Per-segment opt-out: "no_refine": true in cuts.json. A pinned boundary is never
moved, not even by joint resolution: an overlap against a pinned side is repaired
by moving the UNPINNED side only, and with both sides pinned nothing moves
(splice.sh then hard-aborts naming the pair). Continuous splits (one unbroken take
carved into separate timeline clips) are detected by transcript adjacency AND an
inter-word gap under the dead-air threshold, then merged to ONE shared boundary by
the pairwise joint-resolution pass, so padded edges can never lay the same source
frames down twice — while two adjacent words with a long silence between them stay
a real cut, and the silence is removed (see continuous_split).

--repair-only runs ONLY the joint-resolution pass, with zero re-measurement.
Refinement is not idempotent (it measures from the authored cut), so an EDL that
has already been refined or shipped gets repaired with this flag, never a second
full pass.

usage: refine-cuts.py [--repair-only] <media_dir> <words.json> <cuts.json> <out_cuts.json>
Stdlib only. Report goes to stderr; exit 0 with out_cuts.json written (worst case a
verbatim copy), so splice.sh can consume the output unconditionally.
"""
import array
import json
import math
import os
import statistics
import subprocess
import sys
# Windows consoles/pipes default to cp1252, which can't encode the ⚠/→ glyphs in this
# script's status lines: a cosmetic print must never kill a pipeline step (it did once,
# 2026-08-13, mid-splice on a real Windows job). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

SR = 16000          # analysis rate — envelopes only, plenty for speech energy
WIN = 0.005         # 5 ms RMS frames
PRE = 0.040         # room tone kept before a measured onset
POST = 0.050        # decay kept after a measured offset
DROP_DB = 18.0      # "quiet" = this far below the word's own median level
HOLD = 6            # frames (30 ms) of sustained quiet to count as a real gap
SEARCH = 0.60       # how far past the word edge we look for the gap
MAX_MOVE = 0.50     # sanity cap on any single boundary move
# Caps RELATIVE TO THE BOUNDARY WORD, not to the authored cut. MAX_MOVE only bounds the
# distance travelled, so a boundary authored deep inside a long pause could still be
# dragged onto a breath 400 ms away from its own word and read as a legitimate onset.
# WhisperX starts run 50-100 ms late and ends run early, so a real acoustic edge is never
# further out than these; anything beyond is a mis-measurement (room tone, a breath, the
# neighbouring word's tail). MAX_MOVE is waived on a boundary the joint test named a DEAD-AIR
# KILL — there the authored cut is legitimately seconds from its own word, and the word-relative
# caps below are what keep the repair honest.
MAX_LEAD = 0.25     # furthest an in-point may sit BEFORE its first word's timestamp
MAX_TAIL = 0.30     # furthest an out-point may sit AFTER its last word's timestamp
REPEAT_GAP = 0.25   # sustained quiet >= this INSIDE one word's span = merged repeat
LONG_WORD = 1.0     # only word spans at least this long get the burst scan
DEAD_AIR_S = 0.65   # polish-boundaries.py's dead-air threshold: a silence this long is material
                    # to REMOVE, so two words either side of it are not one unbroken take


def continuous_split(m, n):
    """Do consecutive segments m and n carve ONE unbroken take? Returns (verdict, gap).

    Nothing removed between them means the joint is a CONTINUOUS SPLIT (one take carved into
    separate clips for the timeline), not a cut, so both sides must share ONE boundary time: pad
    each edge outward the normal way and the pads overlap, laying the same source frames twice.

    Adjacency in the WORD LIST is not enough — it is necessary. Two kept phrases can be
    neighbouring words with a long silence between them (a hold on a phone call, a wait for a
    render): that silence is a dead-air KILL, and a shared boundary would keep every frame of it
    (51 s of it on one job, a 19.5-minute first cut, your-job 2026-09-18). So the inter-word gap
    must also be under DEAD_AIR_S.

    That gap is between the two WORDS, never between the two authored boundaries: the old 50 ms
    boundary-proximity test missed every split whose pads had already pushed the edges further
    apart than that, which is exactly the failing case this function exists for.

    "Adjacent" is <= i_last + 1, not == i_last + 1: an out-pad of 80 ms routinely reaches past the
    next word's timestamp, so segment m appears to KEEP the word segment n opens on. Requiring a
    strict +1 reads that as a cut with material removed and repairs it the wrong way."""
    if not (m["clip"] == n["clip"] and m["i_last"] is not None
            and n["i_first"] is not None and n["i_first"] <= m["i_last"] + 1):
        return False, None
    words = m["words"]
    gap = 0.0
    if n["i_first"] > m["i_last"] and n["i_first"] < len(words):
        gap = float(words[n["i_first"]]["start"]) - float(words[m["i_last"]]["end"])
    return gap < DEAD_AIR_S, gap


def envelope(path, t0, t1):
    """5 ms RMS envelope (dBFS) of [t0, t1] in path. Returns (actual_t0, frames)."""
    t0 = max(0.0, t0)
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
         "-i", path, "-vn", "-af", "pan=mono|c0=c0", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True).stdout
    x = array.array("f")
    x.frombytes(raw)
    w = int(WIN * SR)
    frames = []
    for i in range(0, len(x) - w + 1, w):
        s = 0.0
        for v in x[i:i + w]:
            s += v * v
        frames.append(20 * math.log10(math.sqrt(s / w) + 1e-9))
    return t0, frames


def quiet_runs(frames, q):
    """Maximal runs of >= HOLD consecutive frames below q, as (start_idx, end_idx)."""
    runs, s = [], None
    for i, d in enumerate(frames):
        if d < q:
            if s is None:
                s = i
        else:
            if s is not None and i - s >= HOLD:
                runs.append((s, i))
            s = None
    if s is not None and len(frames) - s >= HOLD:
        runs.append((s, len(frames)))
    return runs


def merged_bursts(path, word):
    """WhisperX collapses an immediately repeated word ("However... However,")
    into ONE entry whose span covers every utterance — the transcript shows a
    single word, so a cut authored from it keeps the stutter. Detect it on the
    envelope: sustained internal quiet >= REPEAT_GAP inside a long word span
    means multiple utterances. Returns (first_gap_start, last_gap_end) in
    absolute seconds, or None for a normal word."""
    if word["end"] - word["start"] < LONG_WORD:
        return None
    t0, fr = envelope(path, word["start"] - 0.05, word["end"] + 0.10)
    k0 = max(0, int(round((word["start"] - t0) / WIN)))
    k1 = max(k0 + 1, int(round((word["end"] - t0) / WIN)))
    if len(fr) < k0 + 10:
        return None
    span = sorted(fr[k0:k1])
    ref = span[int(0.8 * len(span))]   # speech level; median would sink into the gaps
    gaps = []
    for rs, re_ in quiet_runs(fr, ref - DROP_DB):
        gs, ge = t0 + rs * WIN, t0 + re_ * WIN
        if (gs > word["start"] + 0.05 and ge < word["end"] + 0.05
                and ge - gs >= REPEAT_GAP):
            gaps.append((gs, ge))
    if not gaps:
        return None
    return gaps[0][0], gaps[-1][1]


def refine_in(path, seg_start, first, prev_end, dead_air=False):
    """Returns (new_start, note) — note is None when unchanged.

    dead_air: the boundary sits at the far side of a dead-air KILL the joint test just named, so the
    authored cut can be many seconds from its own word and MAX_MOVE (a sanity cap on distance
    travelled) would reject the repair and keep the whole silence. The word-relative cap is the real
    guard here and still applies, so the move is allowed."""
    mb = merged_bursts(path, first)
    if mb:
        # keep only the LAST utterance (prefer-last-take, acoustically applied);
        # intentionally larger than MAX_MOVE — bounded by the word's own span
        new = max(mb[1] - PRE, seg_start)
        if new < first["end"] - 0.08:
            return new, (f'merged repeat in "{first["w"]}" — '
                         f"snapped to last utterance @ {mb[1]:.3f}")
    lo = max(prev_end - 0.02, first["start"] - SEARCH, 0.0)
    hi = max(first["start"] + 0.08, first["end"])
    t0, fr = envelope(path, lo, hi)
    k0 = int(round((first["start"] - t0) / WIN))
    if len(fr) < k0 + 3:
        return seg_start, None
    # speech level from the word's OWN span, 80th percentile as merged_bursts does: the 80 ms after a
    # late WhisperX start can be the word's decaying tail, and its median sinks into the gap
    span = sorted(fr[k0:max(k0 + 3, int(round((first["end"] - t0) / WIN)))])
    ref = span[int(0.8 * len(span))]
    # the gap before the word ENDS at or before its timestamp (WhisperX starts run late, never early
    # enough to matter): a quiet run that ends after it is INSIDE the word, a stop closure ("It",
    # "But", "That"), and snapping to its end cut the vowel off ("Uh. It cuts", 2026-10-13)
    runs = [r for r in quiet_runs(fr, ref - DROP_DB) if t0 + r[1] * WIN <= first["start"] + WIN]
    if not runs:
        return seg_start, "no-gap"
    rs, re_ = runs[-1]
    onset = t0 + re_ * WIN
    new = max(onset - PRE, t0 + rs * WIN)      # stay inside the measured gap
    new = min(new, first["start"] + 0.02)
    new = max(new, first["start"] - MAX_LEAD)  # a real onset is never this far out
    if abs(new - seg_start) > MAX_MOVE:
        if not dead_air:
            return seg_start, "move>cap"
        return new, f"dead-air IN: onset {onset:.3f}, {new - seg_start:+.1f}s onto its own word (silence cut)"
    into = (seg_start - onset) * 1000
    return new, (f'onset {onset:.3f}, cut was {into:.0f} ms INTO "{first["w"]}"'
                 if into > 2 else f"onset {onset:.3f}")


def refine_out(path, seg_end, last, nxt_start, last_is_first=False, dead_air=False):
    # last_is_first: single-word segment — the IN side already snapped to the
    # last utterance, so the normal decay measurement below is the right out
    # dead_air: the silence after this segment is a KILL, not a joint — see refine_in
    mb = None if last_is_first else merged_bursts(path, last)
    if mb:
        # segment ENDS on a merged repeat: trim after the first utterance
        new = min(mb[0] + POST, seg_end)
        if new > last["start"] + 0.08:
            return new, (f'merged repeat in "{last["w"]}" — '
                         f"trimmed to first utterance @ {mb[0]:.3f}")
    lo = last["end"] - 0.08
    hi = last["end"] + SEARCH
    if nxt_start is not None:
        hi = min(hi, nxt_start + 0.02)
    t0, fr = envelope(path, lo, hi)
    kend = max(2, int(round((last["end"] - t0) / WIN)))
    if len(fr) < kend + HOLD:
        return seg_end, None
    ref = statistics.median(fr[:kend])
    runs = [r for r in quiet_runs(fr, ref - DROP_DB)
            if t0 + r[0] * WIN >= last["end"] - 0.03]
    if not runs:
        return seg_end, "no-gap"
    rs, re_ = runs[0]
    offset = t0 + rs * WIN
    new = min(offset + POST, t0 + re_ * WIN - 0.005)
    if nxt_start is not None:
        new = min(new, nxt_start - 0.02)
    new = min(new, last["end"] + MAX_TAIL)     # a real decay is never this long
    new = max(new, last["end"] - 0.05)
    if abs(new - seg_end) > MAX_MOVE:
        if not dead_air:
            return seg_end, "move>cap"
        return new, f"dead-air OUT: offset {offset:.3f}, {new - seg_end:+.1f}s onto its own word (silence cut)"
    hot = (offset - seg_end) * 1000
    return new, (f'offset {offset:.3f}, cut was {hot:.0f} ms before "{last["w"]}" finished'
                 if hot > 2 else f"offset {offset:.3f}")


def main():
    args = sys.argv[1:]
    # --repair-only: run the joint-resolution pass WITHOUT re-measuring any boundary.
    # Refinement is not idempotent — it measures from the authored cut, so running it
    # over an already-refined EDL re-measures from the moved boundary and drifts tails
    # further out (observed: +0.4s on a section that had nothing wrong with it). Use
    # this to repair or re-validate an EDL that has already shipped, or a hand-authored
    # one, and only the overlapping joints change.
    repair_only = "--repair-only" in args
    args = [a for a in args if a != "--repair-only"]
    if len(args) != 4:
        sys.exit("usage: refine-cuts.py [--repair-only] "
                 "<media_dir> <words.json> <cuts.json> <out_cuts.json>")
    media_dir, words_path, cuts_path, out_path = args
    with open(cuts_path, encoding="utf-8") as f:
        cuts = json.load(f)
    with open(words_path, encoding="utf-8") as f:
        wdata = json.load(f)
    by_clip = {os.path.basename(c["clip"]): c.get("words", [])
               for c in wdata.get("clips", [])}

    segs = cuts.get("segments", [])

    # ---- pass 1: resolve every segment's kept-word index range UP FRONT.
    # A joint is a relationship between two segments, so neither side can be decided
    # from one segment alone — the in-point of j+1 needs to know what j kept.
    meta = []
    for seg in segs:
        clip = os.path.basename(seg["clip"])
        words = by_clip.get(clip, [])
        a, b = float(seg["start"]), float(seg["end"])
        idx = [i for i, w in enumerate(words) if w["end"] > a and w["start"] < b]
        meta.append({"clip": clip, "words": words,
                     "i_first": idx[0] if idx else None,
                     "i_last": idx[-1] if idx else None})

    warned_gap = set()
    dead_gap = {}          # j -> the silence between segments j and j+1 that is a KILL, not a joint

    def contiguous(j):
        """True when segments j and j+1 carve one unbroken take (see continuous_split).

        A False with a gap means the two edges are measured from their own words AND the silence
        between them is removed: the distance cap that normally bounds a measurement is waived for
        that one boundary (refine_in/refine_out's dead_air), or cuts.refined.json would still carry
        the whole pause — the warning would name a repair the file did not get (your-job 2026-09-18)."""
        if j < 0 or j + 1 >= len(segs):
            return False
        ok, gap = continuous_split(meta[j], meta[j + 1])
        if not ok and gap is not None:
            dead_gap[j] = gap
            if j not in warned_gap:
                warned_gap.add(j)
                print(f"[refine] seg{j}/{j+1}  ⚠ adjacent words but {gap:.1f}s of silence between "
                      f"them — a dead-air KILL, not a continuous split; measuring both edges from "
                      f"their own words and cutting the silence", file=sys.stderr)
        return ok

    out_segs = []
    moved = 0
    for j, seg in enumerate(segs):
        new_seg = dict(seg)
        if repair_only:
            out_segs.append(new_seg)
            continue
        clip = os.path.basename(seg["clip"])
        path = seg["clip"] if os.path.isabs(seg["clip"]) else os.path.join(media_dir, seg["clip"])
        words = by_clip.get(clip, [])
        a, b = float(seg["start"]), float(seg["end"])
        overl = [(i, w) for i, w in enumerate(words) if w["end"] > a and w["start"] < b]

        if seg.get("no_refine") or not words or not overl or not os.path.exists(path):
            why = "no_refine" if seg.get("no_refine") else "no words/clip"
            print(f"[refine] seg{j}  unchanged ({why})", file=sys.stderr)
            out_segs.append(new_seg)
            continue

        i_first, first = overl[0]
        i_last, last = overl[-1]
        prev_end = words[i_first - 1]["end"] if i_first > 0 else 0.0
        nxt_start = words[i_last + 1]["start"] if i_last + 1 < len(words) else None

        # a boundary pinned on its own ("pin_in" / "pin_out") is kept as authored while the other edge is refined:
        # the clipper pins the edge that sits on a PARENT job's cut, already refined and polished there (2026-09-27)
        if seg.get("pin_in"):
            new_in, in_note = a, "pin_in (kept)"
        elif contiguous(j - 1):
            new_in, in_note = a, "continuous split"
        else:
            new_in, in_note = refine_in(path, a, first, prev_end, dead_air=(j - 1) in dead_gap)
        if seg.get("pin_out"):
            new_out, out_note = b, "pin_out (kept)"
        elif contiguous(j):
            new_out, out_note = b, "continuous split"
        else:
            new_out, out_note = refine_out(path, b, last, nxt_start,
                                           last_is_first=(i_first == i_last),
                                           dead_air=j in dead_gap)

        for _, w in overl[1:-1]:   # merged repeats NOT at a boundary need an
            if merged_bursts(path, w):  # authored split — warn, never auto-cut
                print(f'[refine] seg{j}  ⚠ merged-repeat word {w["w"]!r} MID-SEGMENT '
                      f'({w["start"]:.2f}-{w["end"]:.2f}) — every utterance kept; '
                      f"split the segment to keep only the last one", file=sys.stderr)

        # Authored "air" (extra tail for emphasis) was RETIRED 2026-08-31, you:
        # every tail is the measured decay, uniform on every segment. A stray "air"
        # in an old cuts.json is ignored here.

        if new_out <= new_in:  # degenerate — keep the authored segment
            new_in, new_out, in_note, out_note = a, b, "degenerate", "degenerate"
        new_seg["start"], new_seg["end"] = round(new_in, 3), round(new_out, 3)
        di, do = (new_in - a) * 1000, (new_out - b) * 1000
        if abs(di) > 1 or abs(do) > 1:
            moved += 1
            new_seg["_refine"] = {"orig_start": a, "orig_end": b}
        print(f"[refine] seg{j}  in {a:8.3f}→{new_seg['start']:8.3f} ({di:+4.0f} ms)  "
              f"out {b:8.3f}→{new_seg['end']:8.3f} ({do:+4.0f} ms)"
              + (f"  | {in_note}" if in_note else "")
              + (f"  | {out_note}" if out_note else ""), file=sys.stderr)
        out_segs.append(new_seg)

    # ---- pass 3: PAIRWISE JOINT RESOLUTION — the no-duplicate-frames invariant.
    #
    # Every boundary above is measured from ONE side. The two sides of a joint reach
    # into the same silence from opposite ends and nothing made them agree, so they can
    # cross: segment j ends AFTER segment j+1 starts. Those overlapping source frames
    # then get laid down twice — once as j's tail, once as j+1's head — and play as a
    # 1-15 frame stutter. It survives into every downstream surface (flat render, EDL
    # replay, Premiere/Resolve/CapCut timelines) and is invisible to every per-segment
    # check, because each segment is individually perfect. Only the PAIR is wrong.
    #
    # Measured on your-job 2026-08-06: 19 overlapping joints, 69 duplicate
    # frames. 17 were authored (a continuous split padded outward on both sides) and 2
    # were the refiner itself.
    dups = 0
    for j in range(len(out_segs) - 1):
        x, y = out_segs[j], out_segs[j + 1]
        if meta[j]["clip"] != meta[j + 1]["clip"]:
            continue                                    # different clips never collide
        xa, xb, ya = float(x["start"]), float(x["end"]), float(y["start"])
        if ya >= xb or ya <= xa:
            continue        # ordered, or a deliberate out-of-order re-use of the clip
        over = (xb - ya) * 1000

        if float(y["end"]) <= xb:
            # seg j+1 sits fully INSIDE seg j's source range — every resolution below
            # would collapse it to zero/negative duration. No legal shared boundary
            # exists; this is an authoring error, so flag it loudly and touch nothing
            # (splice.sh's degenerate-segment abort backstops the render path).
            print(f"[refine] seg{j}/{j + 1}  ⚠ seg{j + 1} is fully CONTAINED in seg{j}'s "
                  f"source range — no legal shared boundary; re-author the pair "
                  f"(leaving both untouched).", file=sys.stderr)
            continue

        xp = bool(x.get("no_refine") or x.get("pin_out"))    # x's END is pinned
        yp = bool(y.get("no_refine") or y.get("pin_in"))     # y's START is pinned
        if xp or yp:
            # A pin is a hand-set boundary (false starts, verified repeats). Joint
            # resolution may not undo it: repair by moving the unpinned side only.
            if xp and yp:
                print(f"[refine] seg{j}/{j + 1}  ⚠ OVERLAP {over:.0f} ms but BOTH sides "
                      f"are no_refine-pinned — leaving them; splice.sh will abort naming "
                      f"the pair. Re-author one boundary.", file=sys.stderr)
                continue
            if xp:
                y["start"] = x["end"]
                why = f"seg{j + 1} butt-joined to seg{j}'s PINNED end @ {x['end']}"
            else:
                x["end"] = y["start"]
                why = f"seg{j} trimmed to seg{j + 1}'s PINNED start @ {y['start']}"
            dups += 1
            print(f"[refine] seg{j}/{j + 1}  OVERLAP {over:.0f} ms — {why}", file=sys.stderr)
            continue

        if contiguous(j):
            # One unbroken take, split for the timeline. Both sides are kept, so the
            # audio runs straight through and the boundary may sit anywhere — but it
            # belongs in an inter-word gap near where the author aimed, not inside a
            # word. Locate that gap by TIME rather than by word index: the pads have
            # already overshot, so the index either side of the joint is unreliable.
            ws = meta[j]["words"]
            mid = (xb + ya) / 2
            k = max((i for i in range(len(ws) - 1) if ws[i]["end"] <= mid), default=None)
            shared = mid if k is None else min(max(mid, ws[k]["end"]), ws[k + 1]["start"])
            x["end"] = y["start"] = round(shared, 3)
            why = f"continuous split — shared boundary @ {shared:.3f}"
        else:
            # Material WAS removed here, so there is no single legal boundary: the
            # out must land before the removed run and the in after it. Push both
            # edges clear of it; if they still cross, butt-join at its midpoint.
            mi, ni = meta[j]["i_last"], meta[j + 1]["i_first"]
            if mi is None or ni is None:
                # a wordless side (room-tone/hold segment) has no word edges to
                # push against: butt-join at the overlap's midpoint
                mid = round((ya + xb) / 2, 3)
                x["end"] = y["start"] = mid
                dups += 1
                print(f"[refine] seg{j}/{j + 1}  OVERLAP {over:.0f} ms — wordless side, "
                      f"butt-joined @ {mid:.3f}", file=sys.stderr)
                continue
            gap_lo = meta[j]["words"][mi]["end"]
            gap_hi = meta[j + 1]["words"][ni]["start"]
            cut_words = meta[j]["words"][mi + 1:ni]
            if cut_words:
                gap_lo, gap_hi = cut_words[0]["start"], cut_words[-1]["end"]
            x["end"] = round(min(xb, gap_lo), 3)
            y["start"] = round(max(ya, gap_hi), 3)
            if float(y["start"]) < float(x["end"]):
                mid = round((gap_lo + gap_hi) / 2, 3)
                x["end"] = y["start"] = mid
                why = f"removed run collapsed — butt-joined @ {mid:.3f}"
            else:
                why = "pushed both edges clear of the removed words"
        dups += 1
        print(f"[refine] seg{j}/{j + 1}  OVERLAP {over:.0f} ms — {why}", file=sys.stderr)

    if dups:
        print(f"[refine] resolved {dups} overlapping joint(s) — no duplicate frames",
              file=sys.stderr)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({**cuts, "segments": out_segs}, f, indent=1)
    print(f"[refine] {moved}/{len(segs)} segments adjusted → {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
