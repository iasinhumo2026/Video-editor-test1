#!/usr/bin/env python3
"""segment-script.py — turn a rough-cut transcript into sentence BEATS.

The graphics-plan skill decides graphics per beat. Eyeballing a few-hundred-word
array to find sentence boundaries + timestamps is tedious and error-prone, so this
does the mechanical part deterministically: group the cut-aligned words into
sentence-sized beats with time ranges. The CREATIVE decision (graphic? what kind?
where?) is the model's job — this only scaffolds the rows.

Reads the finished-script transcript written by rough-cut's splice.sh:
  projects/<job>/outputs/<job>.transcript.json   ({text, words:[{text,start,end}]}, seconds)

usage:
  segment-script.py <job_dir|transcript.json> [out.json]

Beats split on sentence-final punctuation (. ! ?). Any sentence longer than
MAX_DUR or MAX_WORDS is sub-split at its largest internal pause so no beat is too
big to land a single graphic on. Prints a readable beat sheet to stderr.
"""
import json
import os
import sys
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

MAX_DUR = 9.0     # seconds — a beat longer than this gets sub-split
MAX_WORDS = 22    # words — same
SENT_END = (".", "!", "?")


def find_transcript(arg):
    if arg.endswith(".json"):
        return arg
    # treat as a job dir: projects/<job>/outputs/<job>.transcript.json
    job = os.path.basename(arg.rstrip("/"))
    cand = os.path.join(arg, "outputs", f"{job}.transcript.json")
    if os.path.exists(cand):
        return cand
    # fall back to any *.transcript.json under the dir
    for root, _, files in os.walk(arg):
        for f in files:
            if f.endswith(".transcript.json"):
                return os.path.join(root, f)
    sys.exit(f"no transcript.json found under {arg} — run rough-cut first")


def split_long(words):
    """Split a word run that's too long at its largest internal gap, recursively."""
    dur = words[-1]["end"] - words[0]["start"]
    if dur <= MAX_DUR and len(words) <= MAX_WORDS:
        return [words]
    # largest gap between consecutive words (avoid the very ends)
    best_i, best_gap = None, -1.0
    for i in range(1, len(words)):
        gap = words[i]["start"] - words[i - 1]["end"]
        if gap > best_gap:
            best_gap, best_i = gap, i
    if best_i is None or best_i in (0, len(words)):
        return [words]
    return split_long(words[:best_i]) + split_long(words[best_i:])


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: segment-script.py <job_dir|transcript.json> [out.json]")
    tpath = find_transcript(sys.argv[1])
    with open(tpath, encoding="utf-8") as f:
        data = json.load(f)
    words = [w for w in data.get("words", []) if str(w.get("text", "")).strip()]
    if not words:
        sys.exit(f"{tpath} has no words")

    # group into sentences on sentence-final punctuation
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if str(w["text"]).strip().rstrip('"\'’”)').endswith(SENT_END):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)

    # sub-split overlong sentences, then emit beats
    beats = []
    for sent in sentences:
        for run in split_long(sent):
            line = " ".join(str(w["text"]).strip() for w in run)
            beats.append({
                "id": len(beats) + 1,
                "start": round(float(run[0]["start"]), 2),
                "end": round(float(run[-1]["end"]), 2),
                "line": line,
                "graphic": None,      # ← model fills: true / false
                "kind": None,         # ← model fills: see SKILL toolbox
                "region": None,       # ← model fills: e.g. top-half / lower-third / full
                "content": None,      # ← model fills: the actual graphic idea
                "reason": None,       # ← model fills: why graphic, or why plain
            })

    out = {
        "source_transcript": tpath,
        "duration": round(float(words[-1]["end"]), 2),
        "beat_count": len(beats),
        "beats": beats,
    }
    out_path = sys.argv[2] if len(sys.argv) > 2 else None
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)

    # readable beat sheet to stderr
    print(f"[segment-script] {len(beats)} beats · {out['duration']}s · {tpath}", file=sys.stderr)
    for b in beats:
        print(f"  {b['id']:>3}. [{b['start']:>6.2f}-{b['end']:>6.2f}] {b['line']}", file=sys.stderr)
    if out_path:
        print(f"[segment-script] scaffold → {out_path}", file=sys.stderr)
    else:
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
