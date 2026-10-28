#!/usr/bin/env python3
"""
compare-transcripts.py — diff two words.json transcripts of the SAME footage (e.g. WhisperX
vs Scribe v2) on the two things the rough cut actually depends on: what was heard, and
WHEN each word starts and ends.

    uv run .claude/skills/rough-cut/scripts/compare-transcripts.py <A.json> <B.json> [--snips N] [--out DIR]

Prints, per engine: word count, low-prob words (p ≤ 0.35, polish-boundaries' LOWPROB),
long-span words (the merged-repeat heuristic). Then the text diff (substitutions /
insertions / deletions with context) and, for every word both engines agree on, the
start/end deltas: median, p90, max, and the signed mean (a systematic offset).

--snips N cuts N short audio snippets around the words the engines disagree on MOST in
time, one file per engine's timing, into --out (default <job>/transcript/compare-snips/).
Listen to the pair: the one that contains exactly the word and nothing else is right.
Neither transcript is ground truth — the ear is.
"""
import difflib
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LOWPROB = 0.35
NORM = re.compile(r"[^\w']+")


def load(path: Path) -> tuple[list[dict], Path]:
    d = json.loads(path.read_text(encoding="utf-8"))
    words, src = [], None
    for c in d["clips"]:
        src = src or Path(c["path"])
        words.extend(c["words"])
    return words, src


def norm(w: str) -> str:
    return NORM.sub("", w.lower())


def long_span(w: dict) -> bool:
    span = w["end"] - w["start"]
    return span > 1.0 or (span > 0.5 and w.get("prob", 1.0) < 0.5)


def profile(name: str, words: list[dict]) -> None:
    low = sum(1 for w in words if w.get("prob", 1.0) <= LOWPROB)
    ls = sum(1 for w in words if long_span(w))
    spans = [w["end"] - w["start"] for w in words]
    print(f"{name}: {len(words)} words · low-prob(≤{LOWPROB}) {low} · long-span {ls} · "
          f"median word span {statistics.median(spans):.3f}s")


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)
    snips = int(args[args.index("--snips") + 1]) if "--snips" in args else 0
    out_dir = Path(args[args.index("--out") + 1]) if "--out" in args else None
    pa, pb = Path(args[0]), Path(args[1])
    A, src = load(pa)
    B, _ = load(pb)
    na, nb = pa.name, pb.name

    profile(na, A)
    profile(nb, B)

    ta = [norm(w["w"]) for w in A]
    tb = [norm(w["w"]) for w in B]
    sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
    subs = ins = dels = 0
    diffs: list[str] = []
    pairs: list[tuple[dict, dict]] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            pairs.extend(zip(A[i1:i2], B[j1:j2]))
            continue
        if op == "replace":
            subs += max(i2 - i1, j2 - j1)
        elif op == "insert":
            ins += j2 - j1
        else:
            dels += i2 - i1
        t = A[i1]["start"] if i1 < len(A) else A[-1]["end"]
        left = " ".join(w["w"] for w in A[max(0, i1 - 3):i1])
        a_txt = " ".join(w["w"] for w in A[i1:i2]) or "∅"
        b_txt = " ".join(w["w"] for w in B[j1:j2]) or "∅"
        diffs.append(f"  {t:7.2f}s  …{left}  [{na}: {a_txt}]  vs  [{nb}: {b_txt}]")

    n = max(len(A), 1)
    print(f"\nTEXT — {len(pairs)} words agree; {subs} substituted, {ins} only in {nb}, "
          f"{dels} only in {na}  (disagreement {100 * (subs + ins + dels) / n:.1f}% of {na})")
    for line in diffs[:60]:
        print(line)
    if len(diffs) > 60:
        print(f"  … {len(diffs) - 60} more")

    ds = [b["start"] - a["start"] for a, b in pairs]
    de = [b["end"] - a["end"] for a, b in pairs]
    ads = [abs(x) for x in ds]
    ade = [abs(x) for x in de]
    print(f"\nTIMING on agreed words ({nb} minus {na}, seconds):")
    print(f"  start: median |Δ| {statistics.median(ads):.3f} · p90 {pct(ads, 0.9):.3f} · "
          f"max {max(ads):.3f} · signed mean {statistics.mean(ds):+.3f}")
    print(f"  end:   median |Δ| {statistics.median(ade):.3f} · p90 {pct(ade, 0.9):.3f} · "
          f"max {max(ade):.3f} · signed mean {statistics.mean(de):+.3f}")
    big = sum(1 for x, y in zip(ads, ade) if max(x, y) > 0.1)
    print(f"  words where either edge differs by > 100 ms: {big} "
          f"({100 * big / max(len(pairs), 1):.1f}%)  ← these are the cut-point risks")

    worst = sorted(pairs, key=lambda p: -max(abs(p[1]["start"] - p[0]["start"]),
                                             abs(p[1]["end"] - p[0]["end"])))[:20]
    print("\nBIGGEST TIMING DISAGREEMENTS (agreed word, A start→end | B start→end):")
    for a, b in worst:
        print(f"  {a['w']:<16} {a['start']:8.3f}→{a['end']:8.3f} (p{a.get('prob', 1):.2f})  |  "
              f"{b['start']:8.3f}→{b['end']:8.3f} (p{b.get('prob', 1):.2f})")

    if snips and src and src.exists():
        out_dir = out_dir or (pa.parent / "compare-snips")
        out_dir.mkdir(parents=True, exist_ok=True)
        for k, (a, b) in enumerate(worst[:snips], 1):
            for tag, w in ((pa.stem, a), (pb.stem, b)):
                s = max(0.0, w["start"] - 0.15)
                d = (w["end"] - w["start"]) + 0.30
                f = out_dir / f"{k:02d}-{norm(w['w'])[:12]}-{tag}.wav"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s:.3f}", "-t",
                                f"{d:.3f}", "-i", str(src), "-vn", "-ac", "1", str(f)],
                               check=True)
        print(f"\nsnippets → {out_dir}  (each pair: 150 ms pad either side of that engine's word)")


if __name__ == "__main__":
    main()
