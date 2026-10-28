#!/usr/bin/env python3
"""cut-proof.py: the production gate for a laid rough cut. Bounce the section's dialogue off the LIVE
timeline, transcribe the bounce independently, and diff it word by word against the script the EDL
promised. A chopped syllable ("a 50" for "a 53"), a doubled word at a joint or a missing word shows
up as a substitution / insertion / deletion with its timeline position; nothing else does.

  uv run lanes/premiere/cut-proof.py projects/<job>[/sections/<s>] [--from 152.694] [--to 503.545]
        # bounces [from, to) of the ACTIVE sequence (other audio tracks muted for the take), writes
        # <job>/review/cut-proof.wav + cut-proof.json, prints the diff and exits 1 on any defect;
        # --from defaults to the EDL's first frame on the timeline, --to to the EDL's last frame (the sequence end
        # when that is within half a second: the same cut, off by the grid), so a middle section bounces alone
  uv run lanes/premiere/cut-proof.py projects/<job>[/sections/<s>] --wav <existing.wav> [--from <t>]
        # re-diff an existing bounce (--from = where that bounce started on the timeline)
  uv run lanes/premiere/cut-proof.py projects/<job> --from 300 --to 360 --triage
        # prove ONE window: the script is cut to the segments the bounce covers, and every defect
        # gets its own ±1.5 s slice re-transcribed underneath it
  uv run lanes/premiere/cut-proof.py projects/<job> --check-text
        # offline, no bounce: every EDL segment's `transcript` against the words words.json places in it

A triaged ASR false positive (a reduced "with" every engine hears as "for", the raw included) is accepted in
<job>/review/cut-proof.accepted.json, a list of {script, heard, t, cut_rev, reason}: a defect with the same script
and heard words within ±0.5 s of `t` (timeline seconds, as printed) on the same `cut_rev` (the first 12 of sha1 over
the EDL, printed in the summary) is reported `accepted` and does not fail the gate. `reason` is required, and a row
from another cut_rev is ignored (named), so a re-cut re-opens every accepted defect.

Before the bounce every segment's `transcript` is checked against words.json: text that omits a word wholly inside
the segment, or carries one the segment does not hold, is a false DEFECT waiting to happen (two segments on the
Windows proof, 2026-09-27), so it is named first.

Where the EDL's first frame sits on the timeline (--edl-start) is read from the job when not passed: the
EDL's own `_timeline` readback, else a section's graphics-plan.json `timeline_offset`, else 0 for a
top-level projects/<job>. Only when none applies does it fall back to --from, with a ⚠. The window the
script is cut to is printed on every run.

The EDL's `transcript` fields are the promise (rough-cut writes them from the kept WhisperX words);
the bounce is transcribed by workflows/asr_cli.py (word timestamps: mlx-whisper on Apple Silicon, faster-whisper
elsewhere, one engine process for the bounce and every --triage slice) and both sides are normalised (lower,
alphanumerics only, common number words to digits, then the repo's spelling map) before a difflib
alignment. Small ASR noise (a/the, contractions, a brand the two engines spell differently, a digit
heard for its sound-alike: "too" / "2") is reported but tagged `minor`; a changed or missing content word is `DEFECT`.
Runs after the replay + audio polish; re-run after any hand edit.
"""
import argparse, contextlib, difflib, hashlib, importlib.util, json, math, os, re, subprocess, sys, time
from collections import Counter
from pathlib import Path

# Windows consoles/pipes default to cp1252, which can't encode the ⚠ in this script's status
# lines: a cosmetic print must never kill the gate. Force UTF-8; no-op on macOS/Linux.
for _s in (sys.stdout, sys.stderr):
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from job_guard import require_job_project  # noqa: E402
from pes import es, lsof_open, wav_preset  # noqa: E402  — lanes/premiere/pes.py: the bridge's one output contract
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workflows"))
import asr_cli  # noqa: E402  — the slice-ASR engine per OS (mlx on macOS, faster-whisper elsewhere)

EXPORT_TRANSCRIPT = Path(__file__).resolve().parents[2] / ".claude/skills/rough-cut/scripts/export-transcript.py"
ASR_MODEL = "mlx-community/whisper-large-v3-turbo"
NUM = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
       "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
       "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
       "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90", "hundred": "100"}
MINOR = {"a", "the", "an", "uh", "um", "like", "and", "so", "to", "of", "that", "it", "its", "is", "i", "you", "im", "youre", "gonna", "going"}
# a digit and the words that sound like it: "too" heard as "2" read as a DEFECT (Windows, 2026-10-13). One word for one
# word only, either way round; a number word normalises to its digit (NUM), so "two" / "four" / "eight" never reach here
HOMO = {"2": {"to", "too", "two"}, "4": {"for", "four"}, "8": {"ate", "eight"}}
AUTO = {}          # the repo's spelling map, loaded per job in main() — see load_auto()
CONTRACT = {"iam": "im", "cannot": "cant", "willnot": "wont", "goingto": "gonna", "wantto": "wanna",
            "gotto": "gotta", "letus": "lets", "kindof": "kinda", "outof": "outta"}
SUFFIX = (("have", "ve"), ("would", "d"), ("will", "ll"), ("are", "re"), ("not", "nt"), ("is", "s"))


def alnum(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def split_words(text):
    """Words for the diff, a hyphenated compound split into its parts on BOTH sides: WhisperX writes
    "four-hour-long" as one word (one token "fourhourlong") where another engine hears "4 hour long", three
    tokens, and the pair read as a DEFECT no normalisation could fold (2026-09-27, the first Windows proof)."""
    return [p for p in re.split(r"[\s\-‐-—]+", text) if p]


def norm(w):
    w = alnum(w)
    w = NUM.get(w, w)
    return AUTO.get(w, w)


def load_auto(job):
    """The repo's spelling map, applied to BOTH sides of the diff. The EDL carries what WhisperX heard
    ("widgit bot") and the bounce carries what mlx-whisper hears ("widgetbot"), and transcript-corrections.json
    (+ the job's corrections.local.json) is the repo's own equivalence between the two — unread here until
    2026-09-19, which made every brand name a permanent DEFECT and put exit 0 out of reach. Path resolution
    stays in export-transcript.py, its one home; we consume the AUTO dict only. A section sub-job inherits
    the parent job's local file, then its own."""
    roots = [job.parent.parent, job] if job.parent.name == "sections" else [job]
    auto = {}
    try:
        spec = importlib.util.spec_from_file_location("export_transcript", EXPORT_TRANSCRIPT)
        mod = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(sys.stderr):    # its "corrections ←" lines are not our output
            spec.loader.exec_module(mod)
            for r in roots:
                auto.update(mod.load_corrections(r / "outputs" / f"{r.name}.transcript.json", None)[0])
    except Exception as e:
        print(f"[cut-proof] ⚠ no corrections dictionary ({e}) — brand spellings will read as defects")
        return {}
    out = {}
    for k, v in auto.items():
        a, b = alnum(k), alnum(v)
        if a and b and a != b:
            out[a] = b
    return out


def reduce_pair(j):
    """'whatis' -> 'whats', 'donot' -> 'dont', 'ihave' -> 'ive'. None when the pair is not an expansion."""
    if j in CONTRACT:
        return CONTRACT[j]
    for long, short in SUFFIX:
        if j.endswith(long) and len(j) > len(long):
            return j[:-len(long)] + short
    return None


def contract(toks):
    """The span with every EXPANDED contraction written the way an ASR writes it: ['they','are','going','to']
    -> 'theyregonna'. Only an adjacent PAIR is reduced, so a lone word is never mangled ('this' stays
    'this'), and a span can carry several contractions. Tested above the FRAGMENT rule, which otherwise
    reads 'what' / 'whats' as a chopped syllable."""
    out, i = [], 0
    while i < len(toks):
        red = reduce_pair(toks[i] + toks[i + 1]) if i + 1 < len(toks) else None
        out.append(red or toks[i])
        i += 2 if red else 1
    return "".join(out)


def lev(a, b):
    """Edit distance, for the spelling test (gbt6 / gpts, astra / astro)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def spelling_pair(x, y):
    """Is this one word written two ways (astro / astra, fable / fables)? Two NUMBERS never are: "53" / "50"
    is a different number, and a chopped one is precisely what this gate exists to catch, so a pair of
    digit tokens has to match exactly. Only a PAIR, though — a number word normalises to a digit, so
    "two" / "to" and "one" / "a" are one side digit, one side homophone, and they stay ASR noise.
    A shared prefix with more than two letters missing is a chopped word too ("clickbait" / "click"),
    not a spelling — it falls through to FRAGMENT."""
    if x.isdigit() and y.isdigit():
        return x == y
    return (x[:3] == y[:3] and abs(len(x) - len(y)) <= 2) or lev(x, y) <= 2


def join_numbers(toks):
    """'2 100' (two hundred) -> '200', so the joined-form test sees the same number the script has."""
    out = []
    for x in toks:
        if x == "100" and out and out[-1].isdigit() and len(out[-1]) == 1:
            out[-1] = out[-1] + "00"
        else:
            out.append(x)
    return out


def tokens_from_edl(edl, lo=0.0, hi=None):
    """The script the bounce is supposed to contain. [lo, hi) is the bounce window in OUTPUT time
    (0 = the EDL's first frame): without it a windowed proof reports the whole script outside the
    window as deletes, so a partial-range proof could never exit 0. Returns (tokens, head, tail) —
    the token counts a boundary segment the bounce only PARTLY covers may legitimately add or drop
    at each end; 0 when the window lands on a segment edge, so a full proof stays strict.
    The slack is that segment's UNCOVERED FRACTION, never its whole word count: a full-section proof
    whose --to sits a few frames inside the last segment (Premiere floors every in/out to the grid,
    so the laid timeline and the EDL sum disagree by frames) would otherwise hand a real missing
    tail a free pass — the gate failing open, silently."""
    out, kept, cursor = [], [], 0.0
    for s in edl["segments"]:
        a = cursor
        cursor += float(s["end"]) - float(s["start"])
        if cursor <= a:
            continue
        if (hi is not None and a >= hi) or cursor <= lo:
            continue
        toks = [n for n in (norm(x) for x in split_words(s.get("transcript", ""))) if n]
        kept.append((a, cursor, len(toks)))
        out += toks
    def slack(seg, uncovered):
        return math.ceil(seg[2] * min(1.0, uncovered / (seg[1] - seg[0])))
    head = slack(kept[0], lo - kept[0][0]) if kept and kept[0][0] < lo - 0.01 else 0
    tail = slack(kept[-1], kept[-1][1] - hi) if kept and hi is not None and kept[-1][1] > hi + 0.01 else 0
    return out, head, tail


def stale_text(edl, words):
    """[warning] per EDL segment whose `transcript` disagrees with the words words.json places in it: a word WHOLLY
    inside the segment that the text omits, or a text word no word overlapping the segment carries. The text is the
    script this gate diffs against, so either one is a false DEFECT (two boundary edits left "with" and "actually"
    out of their segments' text on the Windows proof, 2026-09-27). Both sides go through the diff's own norm()."""
    by_clip = {Path(c.get("clip", "")).name: c.get("words", []) for c in (words.get("clips") or [])}
    tok = lambda w: [n for n in (norm(p) for p in split_words(w.get("w") or w.get("word") or "")) if n]
    out = []
    for i, s in enumerate(edl.get("segments", [])):
        ws = by_clip.get(Path(str(s.get("clip") or "")).name)
        if ws is None or s.get("media"):
            continue
        a, b = float(s["start"]), float(s["end"])
        timed = [w for w in ws if "start" in w and "end" in w]
        inside = [t for w in timed if a <= float(w["start"]) and float(w["end"]) <= b for t in tok(w)]
        near = [t for w in timed if float(w["end"]) > a and float(w["start"]) < b for t in tok(w)]
        text = [n for n in (norm(x) for x in split_words(s.get("transcript", ""))) if n]
        miss, extra = Counter(inside) - Counter(text), Counter(text) - Counter(near)
        if miss or extra:
            out.append(f"segment #{i} {a:.3f}-{b:.3f} ({s.get('clip')}): its text"
                       + (f" omits {', '.join(sorted(miss.elements()))} (inside it in words.json)" if miss else "")
                       + (" and" if miss and extra else "")
                       + (f" carries {', '.join(sorted(extra.elements()))} (no word there)" if extra else ""))
    return out


def load_accepted(path, rev):
    """(rows on this cut_rev, [note]) from review/cut-proof.accepted.json. A row without a reason exits: an accepted
    defect is a human's triage call, and it has to say why."""
    if not path.exists():
        return [], []
    rows = json.load(open(path, encoding="utf-8"))
    rows = rows.get("accepted", rows) if isinstance(rows, dict) else rows
    live, notes = [], []
    for r in rows:
        if not str(r.get("reason") or "").strip():
            sys.exit(f"[cut-proof] {path}: every accepted row needs a reason, this one has none: {json.dumps(r)}")
        if r.get("cut_rev") != rev:
            notes.append(f"accepted row ignored, it was made on cut_rev {r.get('cut_rev')} and the EDL is {rev}: "
                         f"{r.get('script')!r} heard {r.get('heard')!r} @ {r.get('t')}")
            continue
        live.append({**r, "_script": " ".join(n for n in (norm(x) for x in split_words(str(r.get("script") or ""))) if n),
                     "_heard": " ".join(n for n in (norm(x) for x in split_words(str(r.get("heard") or ""))) if n)})
    return live, notes


def edl_start_of(job, edl):
    """Where the EDL's first frame sits on the timeline, from what the job already records: the EDL's
    `_timeline` readback, else a section sub-job's graphics-plan.json `timeline_offset`, else 0 for a
    top-level projects/<job> (its EDL IS the timeline from frame 0). (None, None) when nothing says.
    Defaulting it to --from instead diffed a mid-timeline window of a single-section job against the
    EDL's HEAD (three false NEW DEFECTs on a single-section short, 2026-09-22)."""
    segs = edl.get("segments") or []
    if segs and isinstance(segs[0].get("_timeline"), list) and segs[0]["_timeline"]:
        return float(segs[0]["_timeline"][0]), "cuts.json _timeline"
    plan = job / "graphics-plan.json"
    if plan.exists():
        with contextlib.suppress(ValueError, OSError):
            off = json.load(open(plan, encoding="utf-8")).get("timeline_offset")
            if off is not None:
                return float(off), "graphics-plan.json timeline_offset"
    if Path(os.path.abspath(job)).parent.name == "projects":
        return 0.0, "a top-level job"
    return None, None


def section_end(edl, edl_start, seq_end):
    """The default --to: where the EDL's last frame sits on the timeline (its `_timeline` readback, else
    edl_start + the EDL's length), or the sequence end when that is no more than half a second past it (the
    same last cut, off by the grid drift of a mixed-rate sum) or short of it (a tail trimmed by hand). The
    sequence end alone bounced every LATER section of a multi-section job with a middle one, as insert DEFECTs.
    -> (seconds, what it is)."""
    segs = edl.get("segments") or []
    tl = segs[-1].get("_timeline") if segs else None
    if isinstance(tl, list) and len(tl) > 1:
        nominal, how = float(tl[1]), "the EDL's _timeline end"
    else:
        nominal, how = edl_start + sum(float(x["end"]) - float(x["start"]) for x in segs), "edl_start + the EDL's length"
    if seq_end <= nominal + 0.5:
        return seq_end, "the sequence end"
    return nominal, f"{how}; the sequence runs on to {seq_end:.3f} s"


def transcribe(wav, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    engine = asr_cli.argv()    # mlx-whisper on Apple Silicon, the WhisperX venv's faster-whisper elsewhere
    if engine is None:
        sys.exit(f"ASR failed: {asr_cli.unavailable_reason()}")
    # the engine process stays up for --triage's slices, so the model loads once (asr_cli.run)
    r = asr_cli.run(["--model", ASR_MODEL, "--word-timestamps", "True",
                     "--output-format", "json", "--output-dir", str(outdir), str(wav)])
    j = outdir / (Path(wav).name.split(".")[0] + ".json")
    if r.returncode or not j.exists():
        sys.exit(f"ASR failed: {(r.stderr or r.stdout)[-600:]}")
    d = json.load(open(j, encoding="utf-8"))
    # a zero-length word is a decoder hallucination ("that's" between "this" and "valuable"), not audio
    return [(norm(p), w["start"], w["end"]) for s in d.get("segments", []) for w in s.get("words", []) for p in split_words(w["word"])
            if norm(p) and w["end"] - w["start"] > 0.02]


def slice_asr(wav, at, outdir, pad=1.5):
    """Re-transcribe ±pad s of the bounce ON ITS OWN (--triage). A transcription slip reads differently
    in isolation, a real defect reads the same — the hand pass this replaces was the cost of the
    2026-09-19 rough cut. Returns the slice's words, or None where the engine or ffmpeg is missing."""
    outdir.mkdir(parents=True, exist_ok=True)
    name = f"t{int(round(at * 1000))}"                  # mlx_whisper names its output by the basename up to the FIRST dot
    cut = outdir / f"{name}.wav"
    try:                                                # a missing ffmpeg/uvx degrades the LINE, never the gate
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, at - pad):.3f}", "-t", f"{2 * pad:.3f}",
                        "-i", str(wav), "-ac", "1", "-ar", "16000", "-y", str(cut)], capture_output=True)
        if not cut.exists():
            return None
        engine = asr_cli.argv()
        if engine is None:
            return None
        r = asr_cli.run(["--model", ASR_MODEL, "--word-timestamps", "True",
                         "--output-format", "json", "--output-dir", str(outdir), str(cut)])
    except OSError:
        return None
    j = outdir / f"{name}.json"
    if r.returncode or not j.exists():
        return None
    d = json.load(open(j, encoding="utf-8"))
    return " ".join(w["word"].strip() for s in d.get("segments", []) for w in s.get("words", []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--from", dest="t0", type=float, default=None,
                    help="timeline start (s) of the bounce; default = the EDL's first frame on the timeline (--edl-start)")
    ap.add_argument("--to", dest="t1", type=float, default=None,
                    help="timeline end (s); default = the EDL's last frame on the timeline (the sequence end within 0.5 s)")
    ap.add_argument("--wav", default=None, help="diff an existing bounce instead of bouncing")
    ap.add_argument("--edl", default=None)
    ap.add_argument("--edl-start", dest="edl_start", type=float, default=None,
                    help="timeline (s) where the EDL's FIRST frame sits; default = the EDL's _timeline, else the section's "
                         "graphics-plan.json timeline_offset, else 0 for a top-level projects/<job>, else --from")
    ap.add_argument("--triage", action="store_true", help="re-transcribe a ±1.5 s slice under every defect")
    ap.add_argument("--check-text", dest="check_text", action="store_true",
                    help="only check every segment's transcript against words.json (offline) and exit 1 on a mismatch")
    a = ap.parse_args()
    job = Path(a.job)
    edl_p = Path(a.edl) if a.edl else job / "transcript" / "cuts.json"
    edl = json.load(open(edl_p, encoding="utf-8"))
    rev = hashlib.sha1(edl_p.read_bytes()).hexdigest()[:12]
    if a.check_text:
        AUTO.update(load_auto(job))
        wp = edl_p.parent / "words.json"
        if not wp.exists():
            sys.exit(f"[cut-proof] no {wp}: nothing to check the text against")
        bad = stale_text(edl, json.load(open(wp, encoding="utf-8")))
        for w in bad:
            print(f"[cut-proof] ⚠ {w}")
        print(f"[cut-proof] text check: {len(bad)} of {len(edl.get('segments', []))} segment(s) disagree with words.json")
        sys.exit(1 if bad else 0)
    edl_start, how = (a.edl_start, "--edl-start") if a.edl_start is not None else edl_start_of(job, edl)
    if edl_start is None:
        if a.t0 is None:
            ap.error("nothing says where the EDL starts on the timeline (no _timeline in the EDL, no timeline_offset in "
                     "graphics-plan.json, not a top-level projects/<job>): pass --from and --edl-start")
        edl_start, how = a.t0, "--from"
        print(f"[cut-proof] ⚠ nothing says where the EDL's first frame sits on the timeline: --edl-start assumed = --from "
              f"({a.t0:.3f} s), i.e. the bounce starts on the EDL's first frame. Pass --edl-start if it does not.")
    if a.t0 is None:
        a.t0 = edl_start
    AUTO.update(load_auto(job))
    wp = edl_p.parent / "words.json"
    if wp.exists():
        for w in stale_text(edl, json.load(open(wp, encoding="utf-8"))):
            print(f"[cut-proof] ⚠ {w}: the proof will read it as a DEFECT; fix the text to the kept audio")
    review = job / "review"; review.mkdir(exist_ok=True)
    wav = (Path(a.wav) if a.wav else review / "cut-proof.wav").resolve()   # Premiere resolves a relative path against ITS cwd, not ours

    if not a.wav:
        require_job_project(es, job)
        if a.t1 is None:
            seq_end = float(es("(function(){var s=app.project.activeSequence;var v=s.videoTracks[0];return String(v.clips[v.clips.numItems-1].end.seconds);})()").strip('"'))
            a.t1, why = section_end(edl, edl_start, seq_end)
            print(f"[cut-proof] --to {a.t1:.3f} s ({why})", flush=True)
    lo, hi = a.t0 - edl_start, None if a.t1 is None else a.t1 - edl_start
    end = hi if hi is not None else sum(float(s["end"]) - float(s["start"]) for s in edl["segments"])
    # printed BEFORE the bounce: a wrong window is visible (and abortable) before a minutes-long export
    print(f"[cut-proof] script window: EDL {lo:.3f}-{end:.3f} s (edl_start {edl_start:.3f}, from {how})", flush=True)

    if not a.wav:
        if wav.exists():
            wav.unlink()
        preset = wav_preset()
        try:
            r = es(f"""(function(){{var s=app.project.activeSequence;var m=[];for(var t=1;t<s.audioTracks.numTracks;t++){{m.push(s.audioTracks[t].isMuted());s.audioTracks[t].setMute(1);}}
s.setInPoint({a.t0}); s.setOutPoint({a.t1});
var r=String(s.exportAsMediaDirect({json.dumps(str(wav))}, {json.dumps(preset)}, 1));
for(var t=1;t<s.audioTracks.numTracks;t++) s.audioTracks[t].setMute(m[t-1]?1:0);
s.setInPoint(-400000); s.setOutPoint(-400000); return r;}})()""",
                   # the panel's watchdog kills a script at 45 s and reports a FINISHED export as a failure
                   # (lanes/premiere/lab-notes.md § the bridge's output contract); a long section bounces for
                   # minutes, and the unmute is the last statement, so a false failure leaves the timeline muted
                   timeout=1800000)
        except SystemExit:
            print("[cut-proof] ⚠ the bounce did not come back: every audio track except A1 may still be MUTED, and "
                  "the sequence in/out are still set. Fix both in Premiere before anything else is exported.",
                  file=sys.stderr)
            raise
        print(f"[cut-proof] bounce {a.t0:.3f}-{a.t1:.3f}s -> {wav} ({r})")
        for _ in range(240):
            if wav.exists() and not lsof_open(wav) and wav.stat().st_size > 1000:
                break
            time.sleep(2)
        else:
            sys.exit("bounce never finished")

    heard = transcribe(wav, review / "cut-proof-asr")
    want, head, tail = tokens_from_edl(edl, lo, hi)
    got = [w[0] for w in heard]
    sm = difflib.SequenceMatcher(a=want, b=got, autojunk=False)
    ops = sm.get_opcodes()
    defects, minors, keys, ats, accepted_hits = [], [], [], [], []
    accepted, acc_notes = load_accepted(review / "cut-proof.accepted.json", rev)
    for n_ in acc_notes:
        print(f"[cut-proof] ⚠ {n_}")
    for n, (tag, i1, i2, j1, j2) in enumerate(ops):
        if tag == "equal":
            continue
        w_ = want[i1:i2]; g_ = got[j1:j2]
        at = heard[j1][1] if j1 < len(heard) else (heard[j1 - 1][2] if heard else 0.0)
        tl = a.t0 + at
        line = f"{tag:8s} @ timeline {tl:8.2f}s (bounce {at:7.2f}s)  script: {' '.join(w_) or '-':40s}  heard: {' '.join(g_) or '-'}"
        content = [x for x in w_ + g_ if x not in MINOR]
        jw, jg = "".join(w_).replace("one", "1"), "".join(join_numbers([x for x in g_ if x not in ("dollars", "dollar")]))
        jw2 = jw[1:] if jw.startswith("a") and len(w_) > 1 and w_[0] == "a" else jw
        # "et cetera" / "etc" — an abbreviation is notation. Folded as a SUBSTRING so a repeated one ("et cetera, et cetera" heard
        # as "etc etc", a short-form job 2026-09-20) folds too; the whole-string lookup only ever matched a single one.
        jw, jg, jw2 = (x.replace("etcetera", "etc") for x in (jw, jg, jw2))
        edge = max(i2 - i1, j2 - j1) <= (head if n == 0 else tail if n == len(ops) - 1 else 0)
        if tag == "insert" and all(x in ("dollars", "dollar", "percent") for x in g_):
            kind = "notation"                            # "$100" read as "100 dollars"
        elif tag == "replace" and len(w_) == len(g_) == 1 and (g_[0] in HOMO.get(w_[0], ()) or w_[0] in HOMO.get(g_[0], ())):
            kind = "notation"                            # "too" / "2", "for" / "4", "ate" / "8"
        elif tag == "replace" and (jw == jg or jw2 == jg or jw.replace("s", "") == jg.replace("s", "") or jw2.replace("s", "") == jg.replace("s", "")):
            kind = "notation"                            # "oneshot" / "1 shot", "51" / "5 1", "openai" / "open ai", "$200" / "2 100 dollars"
        elif tag == "replace" and len(w_) == len(g_) and all(spelling_pair(x, y) for x, y in zip(w_, g_)):
            kind = "spelling"                            # astro / astra, fable / fables, gbt6 astra / gpts extra
        elif tag == "replace" and len(w_) == 1 and len(g_) >= 1 and not (w_[0].isdigit() or "".join(g_).isdigit()) \
                and w_[0][:3] == g_[0][:3] and abs(len(w_[0]) - len("".join(g_))) <= 2:
            kind = "spelling"                            # races / race is
        elif tag == "replace" and (contract(w_) == "".join(g_) or "".join(w_) == contract(g_)):
            kind = "contract"                            # "i am" / "im", "what is" / "whats" — BEFORE the fragment test
        elif tag in ("delete", "insert") and edge:
            kind = "edge"                                # a boundary segment the bounce only partly covers
        elif tag == "replace" and any(x.startswith(y) or y.startswith(x) for x in w_ for y in g_ if len(x) > 2 and len(y) > 2 and x != y):
            kind = "FRAGMENT"                            # "clickbait" vs "click" (a chopped number is a DEFECT: spelling_pair)
        elif not content:
            kind = "minor"
        else:
            kind = "DEFECT"
        if kind in ("FRAGMENT", "DEFECT"):
            ok = next((r for r in accepted if r["_script"] == " ".join(w_) and r["_heard"] == " ".join(g_)
                       and abs(float(r.get("t", -1e9)) - tl) <= 0.5), None)
            if ok:
                minors.append(f"{'accepted':10s}" + line + f"  ({ok['reason']})")
                accepted_hits.append(ok)
                continue
            defects.append(f"{kind:10s}" + line)
            keys.append(f"{' '.join(w_)} > {' '.join(g_)}")   # the pair, not the second: a re-lay moves every timeline position
            ats.append(at)
        else:
            minors.append(f"{kind:10s}" + line)
    proof = review / "cut-proof.json"
    prev = set()
    if proof.exists():
        with contextlib.suppress(ValueError, OSError):
            prev = set(json.load(open(proof, encoding="utf-8")).get("defect_keys", []))
    order = sorted(range(len(defects)), key=lambda i: keys[i] in prev)   # what this round introduced, first
    json.dump({"wav": str(wav), "from": a.t0, "to": a.t1, "edl_start": edl_start, "cut_rev": rev, "want": len(want),
               "got": len(got), "defects": defects, "defect_keys": keys, "minor": minors,
               "accepted": [{k: v for k, v in r.items() if not k.startswith("_")} for r in accepted_hits]},
              open(proof, "w", encoding="utf-8"), indent=1)
    for i in order:
        print(("    " if keys[i] in prev else "NEW ") + defects[i])
        if a.triage:
            print(f"{'':14s}slice @ bounce {ats[i]:7.2f}s: {slice_asr(wav, ats[i], review / 'cut-proof-asr' / 'triage') or '(ASR unavailable)'}")
    for l in minors: print("    " + l)
    carried = sum(1 for k in keys if k in prev)
    print(f"[cut-proof] {len(want)} script words · {len(got)} heard · {len(defects)} defects "
          f"({len(defects) - carried} new, {carried} carried) · {len(accepted_hits)} accepted · "
          f"{len(minors) - len(accepted_hits)} minor ASR diffs · cut_rev {rev} -> {proof}")
    if defects:
        print(f"[cut-proof] a defect triaged as an ASR false positive is accepted in {review / 'cut-proof.accepted.json'}: "
              f'{{"script": ..., "heard": ..., "t": <timeline s>, "cut_rev": "{rev}", "reason": "..."}}')
    sys.exit(1 if defects else 0)


if __name__ == "__main__":
    main()
