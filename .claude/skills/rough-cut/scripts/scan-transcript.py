#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = ["english-words>=2.0; sys_platform == 'win32'"]
# [tool.uv]
# exclude-newer = "14 days"
# ///
"""scan-transcript.py — deterministic SUSPECT FINDER for transcription errors the
static dictionary didn't catch. The dynamic-correction step (see rough-cut SKILL.md)
runs this to narrow ~500 transcript words down to a handful of likely mistranscribed
proper nouns / brand terms, which Claude then judges IN CONTEXT and auto-applies as
single-token dictionary fixes (timestamp-safe — never changes word count or timings).

It flags nothing on its own — it only surfaces candidates. A word is a SUSPECT when
it is NOT a common English word, NOT already a known-correct term in the dictionary,
and NOT obvious noise (numbers, 1–2 char tokens). Proper nouns that are already
correct will show up too; Claude skips those.

usage: scan-transcript.py <job_dir | transcript.json> [--json]
"""
import json
import os
import pathlib
import re
import sys
# Windows consoles/pipes default to cp1252, which can't encode the ×/…/→ glyphs in this
# script's status lines: a cosmetic print must never kill a pipeline step (it did once,
# 2026-08-13, mid-splice on a real Windows job). Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# modern/informal/slang words missing from the old (1934) web2 wordlist — not suspects
ALLOW = {
    "ok", "okay", "yeah", "yep", "nope", "gonna", "wanna", "gotta", "kinda", "sorta",
    "app", "blog", "vlog", "online", "website", "email", "internet", "selfie",
    "podcast", "emoji", "wifi", "login", "setup", "signup", "username", "dropdown",
    "screenshot", "workflow", "dataset", "chatbot", "automation", "scroll", "repost",
    "dm", "niche", "monetize", "monetization", "viral", "clickbait", "ish", "lol",
    "vibe", "stuff", "wassup", "yo", "gosh", "whatnot", "demo", "guru", "op",
    "fuck", "shit", "damn", "ass", "crap", "wtf", "af", "bro", "dude",
    "carousel", "larp", "reel", "thumbnail", "hook", "repurpose", "evergreen",
}

# common derivational suffixes — strip to find the base word in the wordlist
_SUFFIXES = [("ies", "y"), ("es", ""), ("s", ""), ("ed", ""), ("d", ""),
             ("ing", ""), ("ing", "e"), ("er", ""), ("est", ""), ("ly", ""), ("ment", "")]


def _base_forms(w):
    forms = {w}
    for suf, repl in _SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            forms.add(w[:len(w) - len(suf)] + repl)
    return forms


def is_common(w, common):
    """True if w (or an inflected/hyphenated form of it) is ordinary English."""
    if w in common or w in ALLOW:
        return True
    if any(f in common or f in ALLOW for f in _base_forms(w)):
        return True
    if "-" in w:  # hyphenated compound: every part ordinary → not a suspect
        parts = [p for p in w.split("-") if p]
        if parts and all(len(p) < 3 or is_common(p, common) for p in parts):
            return True
    return False


def load_common():
    words = set()
    # macOS ships words/web2 by default; Debian/Ubuntu provides american-english via
    # `apt install wamerican` (also symlinked to /usr/share/dict/words). First one found wins.
    # Windows has no system wordlist: the `english-words` package (a win32-only inline dependency, `uv run` installs
    # it) ships the SAME web2 list macOS does (2026-09-27; before, the scan returned empty and was skipped).
    for p in ("/usr/share/dict/words", "/usr/share/dict/web2", "/usr/share/dict/american-english"):
        if os.path.exists(p):
            with open(p, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip().lower()
                    if w:
                        words.add(w)
            break
    if not words:
        try:
            from english_words import get_english_words_set
            words = set(get_english_words_set(["web2"], lower=True))
        except Exception:
            pass
    return words


def load_known_correct(transcript_path):
    """Words that are ALREADY handled by the dictionary — skip them as suspects.
    = every auto value + auto key + flag word (lowercased)."""
    known = set()
    out = pathlib.Path(transcript_path).resolve()
    candidates = []
    LEGACY = ("presets", "caption-corrections.json")   # pre-2026-08-31 location + name
    if len(out.parents) >= 4:
        candidates.append(out.parents[3] / "transcript-corrections.json")
        candidates.append(out.parents[3].joinpath(*LEGACY))
    here = pathlib.Path(__file__).resolve()
    if len(here.parents) >= 5:
        candidates.append(here.parents[4] / "transcript-corrections.json")
        candidates.append(here.parents[4].joinpath(*LEGACY))
    for c in candidates:
        if c.exists():
            cfg = json.load(open(c, encoding="utf-8"))
            for k, v in cfg.get("auto", {}).items():
                known.add(k.lower())
                known.add(re.sub(r"[^\w]", "", str(v)).lower())
            for w in cfg.get("flag", []):
                known.add(w.lower())
            break
    # the job's own one-offs (projects/<job>/corrections.local.json, merged on top by export-transcript.py): a brand
    # fixed there was still listed as a suspect on every scan after the fix (wt-short "Hbada", 2026-10-13)
    local = out.parent.parent / "corrections.local.json"
    if local.exists():
        cfg = json.load(open(local, encoding="utf-8"))
        for k, v in cfg.get("auto", {}).items():
            known.add(k.lower())
            known.add(re.sub(r"[^\w]", "", str(v)).lower())
        for w in cfg.get("flag", []):
            known.add(w.lower())
    return known


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        sys.exit("usage: scan-transcript.py <job_dir | transcript.json> [--json]")
    target = pathlib.Path(args[0])
    if target.is_dir():
        tp = target / "outputs" / f"{target.name}.transcript.json"
    else:
        tp = target
    if not tp.exists():
        sys.exit(f"transcript not found: {tp}")

    data = json.load(open(tp, encoding="utf-8"))
    words = [w.get("text", "") for w in data.get("words", [])]
    common = load_common()
    if not common:
        # No system wordlist (/usr/share/dict/words|web2). Without it EVERY non-allowlisted word
        # reads as a suspect, so skip the scan rather than emit a wall of false positives.
        if as_json:
            print(json.dumps({"transcript": str(tp), "suspects": [], "skipped": "no system wordlist"}, indent=2))
        else:
            print("[scan] no system wordlist (/usr/share/dict/words) found — skipping suspect scan.", file=sys.stderr)
        return
    known = load_known_correct(tp)

    suspects = {}  # core -> {count, first_idx, surface}
    for i, raw in enumerate(words):
        core = re.sub(r"^\W+|\W+$", "", raw)
        low = core.lower()
        if len(low) < 3 or low in known:
            continue
        if "'" in low or "’" in low:        # contraction / possessive — never a brand mishear
            continue
        if re.sub(r"[\d,.\-/]", "", low) == "":  # all digits/separators (e.g. 200,000)
            continue
        if is_common(low, common):
            continue
        if low not in suspects:
            ctx = " ".join(w for w in words[max(0, i - 3):i + 4])
            suspects[low] = {"surface": core, "count": 0, "first_idx": i, "context": ctx}
        suspects[low]["count"] += 1

    ranked = sorted(suspects.values(), key=lambda s: (-s["count"], s["first_idx"]))

    if as_json:
        print(json.dumps({"transcript": str(tp), "suspects": ranked}, indent=2))
        return

    print(f"[scan] {tp}")
    print(f"[scan] {len(words)} words → {len(ranked)} suspects (not common, not in dict)\n")
    if not ranked:
        print("  none — transcript is clean against the wordlist + dictionary.")
        return
    for s in ranked:
        print(f"  {s['surface']:<22} ×{s['count']:<3}  …{s['context']}…")
    print("\nJudge each in context. For a real mistranscription:")
    print("  • recurring name/brand → add to transcript-corrections.json (auto: single-token only)")
    print("  • one-off for this video → projects/<job>/corrections.local.json")
    print("  • then re-run export-transcript.py to apply (timings untouched).")
    print("Skip the ones that are already-correct proper nouns.")


if __name__ == "__main__":
    main()
