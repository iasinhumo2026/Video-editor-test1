#!/usr/bin/env python3
"""polish-boundaries.py — uniform, peak-relative cut boundaries for every segment.

Built 2026-08-28 from the your-job session, where the creator heard exactly what the
old absolute-threshold measurement produces: some words clipped at the end, others with
too much room ("you're not even cutting right at the end of some words"). Hardened the
same day by an adversarial review (10 findings, all fixed here). Root causes covered:

  1. A threshold set from the noise floor alone falls below room tone on quiet setups,
     so a "decay" walks seconds into the gap and the clamp then cuts the word short.
  2. A soft voiced decay drops below an absolute threshold while still audible.
  3. A breath after a word gets counted as part of it (out lands late).
  4. Low-probability boundary words (p <= 0.35 clusters) mean the WhisperX TIMESTAMP IS
     FICTION, not just soft — real speech ran ~750 ms past the claimed end on a measured
     case ("...90% of the way th—"). That applies to the NEXT word too: a low-prob next
     word makes the search limit itself fiction, so the limit extends to the next
     TRUSTED word.
  5. refine-cuts.py used to classify a dead-air kill between ADJACENT transcript words
     as a continuous split and skip measuring those boundaries entirely. Both tools now
     gate continuity on the inter-WORD gap as well (continuous_split, DEAD_AIR_S); this
     pass still measures every such joint from the words, which is why it recovered.
  6. The two sides of a joint must be resolved as a PAIR (same invariant as refine's
     pass 3): independent measurement can cross in the shared silence and play frames
     twice. A pairwise pass runs after measurement; continuous splits butt-join exactly.
  7. A quiet final consonant (the -ge of "advantage", the -ts of "effects", a released
     -t / -k) sits under the broadband threshold, so the decay ended at the vowel and the
     70 ms tail cut the consonant off: 3-4 frames, heard by a member on client edits
     (2026-10-13). Measured on a real take: "effects," decayed 134 ms before WhisperX's own
     end and its /ts/ ran 220 ms past the decay: 30-40 dB over the room in the high band,
     but in the broadband barely over floor + 10 dB and behind a 110 ms /t/ closure, longer
     than the quiet terminator. consonant_end() carries the decay through the high band
     when the spelling ends on a fricative, affricate or stop (soft_ending).

Method (validated on your-job v2.1):
  envelope     5 ms RMS in dB; LOCAL noise floor = 10th pct of a −2s..+2.5s window
  threshold    max(floor + 10 dB, word peak − 28 dB)
  OUT          decay end (sustained 100 ms quiet terminator), hard-capped at
               word.end + 300 ms — widened past low-prob words to the next trusted one;
               a word spelt to end on a fricative/affricate/stop decays where its final
               consonant ends in the high band (consonant_end, same caps)
               out = decay + 70 ms, uniform on every segment (authored per-segment
               "air" was retired 2026-08-31 — see SKILL.md; tails never vary)
  IN           onset (40 ms of quiet required before it) − 40 ms
  joints       resolved pairwise after measurement; a continuous split (kept words
               ADJACENT and under DEAD_AIR_S apart — adjacency alone is not continuity)
               shares ONE boundary in the inter-word gap; real-cut overlaps are split at
               the midpoint; a pinned side never moves
  pins         segments arriving with no_refine keep their BOUNDARIES (hand-pins survive,
               and the step is idempotent); everything is pinned on output
  long-span    a merged-repeat word (> 1.0 s) at an OUT cuts after its FIRST utterance;
               at an IN the upstream prefer-last snap is kept as authored
  ⚠ lines      no-decay against a killed region, fused joints (the next killed word starts
               before the kept word decays), killed-neighbor grafts, long-spans, words a
               dead-air split cuts into or finds in its pause, hot cuts — each one is a
               clipped word / flubbed take candidate: verify by slice re-ASR (SKILL.md §
               Fresh-eyes second pass), never ship unheard

Usage (after splice.sh's refine pass has produced cuts.refined.json):
  python3 polish-boundaries.py <job_dir>
Reads  /tmp/video-editor/<job>/cuts.refined.json (falls back to transcript/cuts.json)
Writes /tmp/video-editor/<job>/cuts.json with every segment pinned, and deletes
cuts.refined.json/cuts.snapped.json so the next splice.sh run consumes the pinned EDL.
On Windows the folder is %TEMP%\\video-editor\\<job>, which is Git Bash's /tmp, so splice.sh reads the same file.
Re-run splice.sh after this (RENDER=0 on the FIRST splice of any lane — the render
belongs after this step).
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import wave
import array

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HOP_S = 0.005
TAIL_S = 0.07          # uniform out tail past the measured decay
BEAT_TAIL_S = 0.25     # a LANDED line ("beat": true on the segment) keeps up to this much of the speaker's own
                       # pause past the decay, never past the next word. Measured off your 2026-09-13 hand pass
                       # (the 2026-09-13 outro hand pass): 11 of 74 tails lengthened by hand to 130-390 ms, every one at a
                       # verdict, a section close or the section's last line; the other 63 left at decay + 70 ms.
LEAD_S = 0.04          # uniform in lead before the measured onset
DECAY_CAP_S = 0.30     # max decay length past the claimed word end (breath guard)
LOWPROB = 0.35         # words at/below this probability: timestamp is untrusted
QUIET_TERM_S = 0.10    # sustained quiet that ends a decay
ONSET_QUIET_S = 0.04   # quiet required immediately before an onset
SOFT_ONSET_S = 0.25    # pass 3: how far before the loud hop an aligner start is taken as the onset (pass 1's IN search reaches as far)
JOINT_GAP_S = 0.20     # max authored gap for two segments to count as one joint
LONG_SPAN_S = 1.0      # merged-repeat word span threshold
DEAD_AIR_S = 0.65      # a quiet run this long INSIDE a segment is dead air: split it. Calibrated on your-job (2026-09-04): the creator called the cut perfect with 0.42-0.60 s mid-sentence breaths in it and flagged only the 0.84 s pause, so 0.4 would add eight cuts he did not want
# A quiet final consonant, measured in the high band (consonant_end). Calibrated on three real takes of one voice
# (2026-10-14, every phrase-final word): the consonant words moved a median 0-20 ms and at most 220 ms ("effects,", the
# real clip); a looser burst test (25 dB) or a 150 ms closure walked into inhales, and an ungated pass moved open endings.
SOFT_END = ("ch", "sh", "th", "ph", "gh", "s", "x", "z", "t", "d", "k", "c", "p", "b", "g", "f", "v")
SOFT_FLOOR_DB = 15.0   # the high-band threshold: this far over the high band's local floor...
SOFT_PEAK_DB = 30.0    # ...and no lower than this under the word's own high-band peak
SOFT_JOIN_S = 0.03     # a high-band dip this short is the same sound
SOFT_BURST_DB = 20.0   # past a longer dip (a stop closure) the release is back within this of the peak inside 30 ms;
                       # an inhale ramps up 20-25 dB under it, and a breath is never the word


def die(msg):
    print(f"[polish] {msg}", file=sys.stderr)
    sys.exit(1)


def continuous_split(wd, i_last, i_first):
    """Do two kept word ranges of one clip carve ONE unbroken take? Returns (verdict, gap).

    Adjacent in the word list AND no dead air between them: a long silence between two
    word-list-adjacent phrases is material to REMOVE, and a shared boundary would keep every
    frame of it. Same definition as refine-cuts.py's continuous_split, which owns the reasoning."""
    if i_last is None or i_first is None or i_first > i_last + 1:
        return False, None
    gap = 0.0
    if i_first > i_last and i_first < len(wd):
        gap = float(wd[i_first]["start"]) - float(wd[i_last]["end"])
    return gap < DEAD_AIR_S, gap


def resolve_index(pos, parts_of, seg, t, side):
    """(final index, the boundary time as WRITTEN) for a line collected BEFORE the dead-air split.

    `pos` maps id(segment) -> its index in the array this run writes; `parts_of` maps a parent
    segment to the part(s) it became ([itself] when it was not split). An unsplit segment keeps its
    identity through the split pass; a split parent resolves to the part holding the line's own
    boundary time, so every printed seg N is an index a reviewer can look up. Module level so the
    regression test measures THIS resolver (workflows/test_polish_renumber.py).

    A miss returns index -1 (printed `seg??`) and says so on stderr: defaulting to 0 would send a
    reviewer to the first segment, which is the exact failure this renumbering exists to end."""
    ps = parts_of.get(id(seg)) or [seg]
    hit = next((p for p in ps if float(p["start"]) - 0.02 <= t <= float(p["end"]) + 0.02),
               min(ps, key=lambda p: abs(float(p["start"]) - t)))
    if id(hit) not in pos:
        print(f"[polish] ⚠ BUG: the line at {t:.3f}s is keyed to no written segment — index "
              f"unavailable, DO NOT trust a seg number on it", file=sys.stderr)
    return pos.get(id(hit), -1), (float(hit["start"]) if side == "in" else
                                  float(hit["end"]) if side == "out" else t)


def soft_ending(word):
    """Is the word SPELT to end on a fricative, affricate or stop (s, t, ge, ch, sh, f, th, k ...)? A silent final e
    is dropped first ("advantage" ends -g, "make" -k; "the", "she" keep it), a final -ng is a nasal. Spelling is only
    the gate: consonant_end measures whether the sound is there, so a miss here keeps the old decay, never adds air."""
    w = re.sub(r"[^a-z]", "", (word or "").lower())
    if not w or w.endswith("ng"):
        return False
    if len(w) > 2 and w[-1] == "e" and w[-2] not in "aeiouy" and any(ch in "aeiouy" for ch in w[:-2]):
        w = w[:-1]
    return w.endswith(SOFT_END)


def consonant_end(levels, hop, w, decay, cap):
    """Where word `w`'s final consonant ends: `decay` (its broadband decay end) carried on through the HIGH band.

    A final /s/, /dʒ/, /f/ or a released /t/ /k/ is noise high in the spectrum: on a real take it sat 30-40 dB over the
    high band's room tone and barely over the broadband threshold, where hum and room tone live (fix 7 in the header).
    levels(k0, k1) -> the high-band level (dB, Env.hf) of hops k0..k1-1; `hop` is seconds per hop. The decay is
    extended through hops at or over max(local high-band floor + 15 dB, the word's own high-band peak - 30 dB), across
    dips up to QUIET_TERM_S (a stop closure) when the sound past the dip comes back within SOFT_BURST_DB of the peak.
    Only for a soft_ending spelling; never before `decay`, never past `cap` (the next killed word) or the word's
    end + DECAY_CAP_S. cut-audit.py imports this, so the polish and the audit place a word's end identically."""
    if decay is None or not soft_ending(w.get("w")):
        return decay
    w_start, w_end = float(w["start"]), float(w["end"])
    reach = min(cap, w_end + DECAY_CAP_S)
    k_lo = max(0, int((w_end - 2.0) / hop))
    win = levels(k_lo, int((w_end + 2.5) / hop))
    k0 = max(k_lo, int(round(decay / hop)))
    if not win or k0 - k_lo >= len(win):
        return decay
    fl = sorted(win)[len(win) // 10]
    pk = max(win[max(0, int(w_start / hop) - k_lo):max(0, int(min(w_end + 0.06, reach) / hop) + 1 - k_lo)] or [fl])
    thr = max(fl + SOFT_FLOOR_DB, pk - SOFT_PEAK_DB)
    last, end = k0 - 1, decay
    for k in range(k0, min(int(reach / hop), k_lo + len(win) - 1) + 1):
        v = win[k - k_lo]
        if v >= thr:
            if (k - last) * hop > SOFT_JOIN_S and max(win[k - k_lo:k - k_lo + 6]) < pk - SOFT_BURST_DB:
                break                    # a slow ramp after a pause: an inhale, not the word
            last, end = k, (k + 1) * hop
        elif (k - last) * hop > QUIET_TERM_S:
            break
    return max(decay, round(end, 6))


def decode_mono16k(path):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000",
         "-y", tmp.name],
        capture_output=True)
    if r.returncode != 0:
        die(f"ffmpeg decode failed for {path}: {r.stderr.decode()[:300]}")
    wf = wave.open(tmp.name, "rb")
    sr = wf.getframerate()
    pcm = array.array("h")
    pcm.frombytes(wf.readframes(wf.getnframes()))
    wf.close()
    os.unlink(tmp.name)
    return pcm, sr


class Env:
    def __init__(self, pcm, sr):
        self.hop = max(1, int(sr * HOP_S))
        self.sr = sr
        self.pcm = pcm
        self._hf = {}
        self.db = []
        for i in range(0, len(pcm) - self.hop, self.hop):
            seg = pcm[i:i + self.hop]
            r = math.sqrt(sum(x * x for x in seg) / len(seg))
            self.db.append(20 * math.log10(r + 1.0))

    def hf(self, k0, k1):
        """The high band of hops k0..k1-1: RMS of the second difference (+12 dB/octave: hum and vowel bodies drop
        out, fricatives and stop releases stay), in dB on the same s16 scale as `db`. Computed on demand around the
        boundaries that need it and cached; cut-audit.py's hf_envelope() is the same sum in numpy."""
        out, p, n = [], self.pcm, self.hop
        for k in range(max(0, k0), min(len(self.db), k1)):
            v = self._hf.get(k)
            if v is None:
                acc = 0
                for j in range(max(k * n, 2), (k + 1) * n):
                    d = p[j] - 2 * p[j - 1] + p[j - 2]
                    acc += d * d
                v = self._hf[k] = 20 * math.log10(math.sqrt(acc / n) + 1.0)
            out.append(v)
        return out

    def idx(self, t):
        return max(0, min(len(self.db) - 1, int(t * self.sr / self.hop)))

    def t(self, k):
        return k * self.hop / self.sr

    def floor(self, t):
        w = self.db[self.idx(t - 2.0):self.idx(t + 2.5)]
        return sorted(w)[len(w) // 10] if w else 25.0

    def band(self, t0, t1):
        w = self.db[self.idx(t0):self.idx(t1)]
        return sum(w) / len(w) if w else 0.0


def scratch_root():
    """splice.sh's scratch folder: /tmp/video-editor, or %TEMP%\\video-editor on Windows (Git Bash's /tmp)."""
    return os.path.join("/tmp" if os.name != "nt" else tempfile.gettempdir(), "video-editor")


def main():
    if len(sys.argv) < 2:
        die("usage: polish-boundaries.py <job_dir>")
    job_dir = os.path.abspath(sys.argv[1])
    job = os.path.basename(job_dir)
    tmpdir = os.path.join(scratch_root(), job)
    src = os.path.join(tmpdir, "cuts.refined.json")
    if not os.path.exists(src):
        src = os.path.join(job_dir, "transcript", "cuts.json")
    if not os.path.exists(src):
        die(f"no cuts found ({tmpdir}/cuts.refined.json or transcript/cuts.json)")
    # The refined EDL is a splice by-product. If the AUTHORED EDL (the /tmp cuts.json splice
    # reads, or the persisted transcript/cuts.json) is newer than it, the refine is stale and
    # this pass would polish the PRE-EDIT cut and report every segment "hand-pinned, untouched"
    # (your-job 2026-09-02: it did exactly that against an EDL edited a minute earlier).
    # The right order is: edit cuts.json -> splice.sh -> polish-boundaries.py -> splice.sh.
    if src.endswith("cuts.refined.json"):
        # the refined EDL is ONE job's: /tmp/video-editor/<name> is shared by every job with that name
        # (section sub-jobs), and splice.sh's .job-path names the job it last spliced there (2026-10-02)
        owner = os.path.join(tmpdir, ".job-path")
        other = open(owner, encoding="utf-8").read().strip() if os.path.exists(owner) else ""
        if other and os.path.realpath(other) != os.path.realpath(job_dir):
            die(f"{src} is {other}'s refined EDL: every job named {job} shares {tmpdir}.\n"
                f"  cp this job's EDL to {tmpdir}/cuts.json, re-run splice.sh (RENDER=0 is fine), then polish.")
        snapped = os.path.join(tmpdir, "cuts.snapped.json")
        persisted = os.path.join(job_dir, "transcript", "cuts.json")
        for authored in (os.path.join(tmpdir, "cuts.json"), persisted):
            # transcript/cuts.json is NOT an authored EDL: splice.sh copies it from cuts.snapped.json
            # AFTER the frame-snap, which takes ~10 s on a 208-segment EDL (2026-09-18), so its mtime
            # is newer than cuts.refined.json BY CONSTRUCTION and the clock alone false-aborted every
            # long-form job. Identical bytes prove this run wrote it; a hand edit changes them and
            # still trips the guard below. Never clear a stale abort by touching the refined file.
            if authored == persisted and os.path.exists(snapped) and os.path.exists(authored) and \
                    open(authored, "rb").read() == open(snapped, "rb").read():
                continue
            # 5 s slack: splice.sh persists transcript/cuts.json AFTER writing cuts.refined.json in the
            # same run (measured 0.63 s apart on a 34-segment EDL, 2026-09-03), so a sub-second
            # tolerance flagged every normal run as stale. A hand edit is minutes later, never seconds.
            if os.path.exists(authored) and os.path.getmtime(authored) > os.path.getmtime(src) + 5.0:
                die(f"{authored} is NEWER than {src}: the refined EDL is stale.\n"
                    f"  Re-run splice.sh (RENDER=0 is fine) so refine-cuts measures the edited EDL, "
                    f"then polish.")
    print(f"[polish] source: {src}")
    cuts = json.load(open(src, encoding="utf-8"))
    words_doc = json.load(open(os.path.join(job_dir, "transcript", "words.json"), encoding="utf-8"))
    clips = {os.path.basename(c["clip"]): c for c in words_doc["clips"]}
    segs = cuts["segments"]
    for s in segs:
        if os.path.basename(s["clip"]) not in clips:
            die(f"clip {s['clip']!r} not in words.json")

    used = {os.path.basename(s["clip"]) for s in segs}
    envs = {}
    for name in used:
        c = clips[name]
        raw = c.get("path") or os.path.join(job_dir, "raw", name)
        if not os.path.exists(raw):
            raw = os.path.join(job_dir, "raw", name)
        pcm, sr = decode_mono16k(raw)
        envs[name] = Env(pcm, sr)

    # Every line this run prints is numbered against the cuts.json it WRITES, so each one is
    # collected as (segment, boundary time, text) and numbered after pass 3 — pass 1 runs in the
    # pre-split index space and the interior dead-air pass renumbers everything after a split, so a
    # pass-1 "seg17" and a hot-cut "seg19" named the same boundary in one file and a reviewer had to
    # re-key 81 of them against the cut sheet (your-job 2026-09-18).
    status, infos, warns = [], [], []
    meta = []          # per-segment: dict(clip, i_first, i_last, pinned, orig_a, orig_b)

    # ---------------- pass 1: per-segment measurement ----------------
    for i, s in enumerate(segs):
        clip = os.path.basename(s["clip"])
        wd = clips[clip]["words"]
        env = envs[clip]
        a, b = float(s["start"]), float(s["end"])
        pinned = bool(s.get("no_refine"))
        # membership by OVERLAP (refine's own rule): the words this segment plays
        overl = [(k, w) for k, w in enumerate(wd) if w["end"] > a and w["start"] < b]
        m = dict(clip=clip, orig_a=a, orig_b=b, pinned=pinned,
                 pin_in=bool(s.get("pin_in")), pin_out=bool(s.get("pin_out")),
                 i_first=overl[0][0] if overl else None,
                 i_last=overl[-1][0] if overl else None,
                 butt_in=False, butt_out=False)
        meta.append(m)
        if pinned:
            status.append((s, a, b, "(hand-pinned — untouched)"))
            continue
        if not overl:
            warns.append((s, a, "in", "wordless — boundaries kept as authored"))
            continue
        wa = overl[0][1]
        wb = overl[-1][1]
        pw = wd[m["i_first"] - 1] if m["i_first"] > 0 else None
        nw = wd[m["i_last"] + 1] if m["i_last"] + 1 < len(wd) else None

        # joint tests use AUTHORED values (source-ordered, small gap)
        def joint_prev():
            if i == 0 or os.path.basename(segs[i - 1]["clip"]) != clip:
                return False
            g = a - float(meta[i - 1]["orig_b"])
            # negative gap = authored pads overlapping (the classic padded continuous
            # split) — that IS a joint; require source order, bound the overlap
            return -0.5 < g < JOINT_GAP_S and a > float(meta[i - 1]["orig_a"])

        def contiguous_prev():
            return joint_prev() and continuous_split(wd, meta[i - 1]["i_last"], m["i_first"])[0]

        # ---------------- IN ----------------
        n_warn_in = len(warns)
        in_note = "kept"
        if (wa["end"] - wa["start"]) > LONG_SPAN_S and a > wa["start"] + 0.05:
            # merged-repeat start: the upstream prefer-last-take snap put the cut
            # deliberately inside the word — keep it, flag for the second pass
            in_note = "long-span(prefer-last, kept)"
            warns.append((s, a, "in", f"IN: starts inside long-span '{wa['w']}' — "
                                      f"prefer-last snap kept as authored; verify by ear/slice-ASR"))
        else:
            fl = env.floor(wa["start"])
            peak = max(env.db[env.idx(wa["start"] - 0.05):
                              env.idx(wa["start"] + 0.25) + 1] or [fl])
            thr = max(fl + 10.0, peak - 28.0)
            lo = max((pw["end"] - 0.02) if pw else 0.0, wa["start"] - 0.25, 0.0)
            onset = None
            for k in range(env.idx(lo), env.idx(wa["start"] + 0.15) + 1):
                if env.db[k] >= thr:
                    qk = env.idx(env.t(k) - ONSET_QUIET_S)
                    if k > qk and all(env.db[j] < thr for j in range(qk, k)):
                        onset = env.t(k)
                        break
            if onset is not None:
                s["start"] = round(max(onset - LEAD_S,
                                       (pw["end"] - 0.01) if pw else 0.0), 3)
                in_note = f"onset−{int(LEAD_S*1000)}ms"
            elif contiguous_prev():
                m["butt_in"] = True          # resolved in the pairwise pass
                in_note = "butt-join(pending)"
            else:
                if pw is not None:
                    s["start"] = round(max(float(s["start"]), pw["end"] - 0.005,
                                           wa["start"] - 0.03), 3)
                in_note = "graft"
                warns.append((
                    s, a, "in",
                    f"IN: no clean onset for '{wa['w']}' and the previous raw "
                    f"word '{pw['w'] if pw else '?'}' is KILLED — verify by ear / "
                    f"slice-ASR (possible flubbed take)"))

        if m["pin_in"]:
            # a boundary pinned on its own is kept as authored while the other edge is measured (the clipper pins the
            # edge on a PARENT job's cut, polished there already, 2026-09-27)
            s["start"], m["butt_in"], in_note = a, False, "pin_in (kept)"
            del warns[n_warn_in:]

        # ---------------- OUT ----------------
        n_warn_out = len(warns)
        def joint_next():
            if i + 1 >= len(segs) or os.path.basename(segs[i + 1]["clip"]) != clip:
                return False
            g = float(segs[i + 1]["start"]) - b
            return -0.5 < g < JOINT_GAP_S and float(segs[i + 1]["start"]) > a

        def contiguous_next():
            # next segment's meta isn't built yet — compute its first word directly
            if not joint_next():
                return False
            na = float(segs[i + 1]["start"])
            nb = float(segs[i + 1]["end"])
            novl = [k for k, w in enumerate(wd) if w["end"] > na and w["start"] < nb]
            return bool(novl) and continuous_split(wd, m["i_last"], novl[0])[0]

        cont_next = contiguous_next()
        # a low-prob NEXT word makes the limit itself fiction: extend to the next
        # trusted word
        nw_trusted = nw
        kk = m["i_last"] + 1
        while nw_trusted is not None and nw_trusted.get("prob", 1.0) <= LOWPROB:
            kk += 1
            nw_trusted = wd[kk] if kk < len(wd) else None
        lowprob = wb.get("prob", 1.0) <= LOWPROB or \
            (pw is not None and m["i_last"] == m["i_first"] and
             pw.get("prob", 1.0) <= LOWPROB) or \
            (m["i_last"] > 0 and wd[m["i_last"] - 1].get("prob", 1.0) <= LOWPROB) or \
            (nw is not None and nw.get("prob", 1.0) <= LOWPROB)
        if nw is None:
            limit = b + 0.5
        elif lowprob and nw_trusted is not None and nw_trusted is not nw:
            limit = nw_trusted["start"] - 0.015
        else:
            limit = nw["start"] - 0.015

        fl = env.floor(wb["end"])
        k0 = env.idx(wb["start"])
        k1 = env.idx(min(wb["end"] + 0.06, limit))
        peak = max(env.db[k0:k1 + 1] or [fl])
        thr = max(fl + 10.0, peak - 28.0)
        out_note = "kept"
        decay = None
        soft_note = ""
        if (wb["end"] - wb["start"]) > LONG_SPAN_S:
            # merged repeat at an OUT: cut after the FIRST utterance
            bursts = []
            cur = None
            for k in range(env.idx(wb["start"]),
                           env.idx(min(wb["end"] + 0.5, limit))):
                if env.db[k] >= thr:
                    if cur is None:
                        cur = [env.t(k), env.t(k)]
                    else:
                        cur[1] = env.t(k)
                elif cur and env.t(k) - cur[1] > 0.12:
                    bursts.append(tuple(cur))
                    cur = None
            if cur:
                bursts.append(tuple(cur))
            if bursts:
                decay = bursts[0][1] + HOP_S
                warns.append((s, b, "out", f"OUT: long-span '{wb['w']}' — cut after FIRST "
                                           f"utterance @{decay:.2f}; verify (merged-repeat rule)"))
        else:
            cap = limit if lowprob else min(wb["end"] + DECAY_CAP_S, limit)
            klim = env.idx(cap)
            last_above = None
            k = k0
            while k <= klim:
                if env.db[k] >= thr:
                    last_above = k
                elif last_above is not None and \
                        env.t(k) - env.t(last_above) > QUIET_TERM_S:
                    break
                k += 1
            decay = env.t(last_above) + HOP_S if last_above is not None else None
            if decay is not None:
                kq1 = env.idx(min(decay + QUIET_TERM_S, limit))
                if any(env.db[j] >= thr
                       for j in range(env.idx(decay) + 1, kq1)) and \
                        env.t(kq1) - decay >= 0.08:
                    decay = None
            # a quiet final consonant under the broadband threshold is still the word (fix 7)
            soft = consonant_end(env.hf, HOP_S, wb, decay, limit)
            soft_note = f"soft+{round((soft - decay) * 1000)}ms " if decay is not None and soft > decay else ""
            decay = soft

        if decay is not None:
            new_out = round(min(decay + (BEAT_TAIL_S if s.get("beat") else TAIL_S), limit), 3)
            if new_out > float(s["start"]) + 0.1:
                s["end"] = new_out
                applied = new_out - decay
                out_note = f"{soft_note}decay+{int(applied*1000)}ms"
                # the limit clamped the out at the decay: the kept word is still loud where the next
                # KILLED word starts, so the cut is inside speech. The decay search stops at the limit,
                # so a clamped decay sits within one hop of it and the note reads between 'decay+-5ms'
                # and 'decay+0ms' (a 09-20 seg shipped a leak as 'decay+-1ms'): less than one hop of tail
                # is the test. Labelled CLAMPED, not FUSED: cut-audit's FUSED is a fine cut placed on the dip.
                if applied < HOP_S and nw is not None and not cont_next:
                    out_note = "⚠ CLAMPED"
                    warns.append((
                        s, new_out, "out",
                        f"OUT: the next killed word '{nw['w']}' starts before '{wb['w']}' decays: "
                        f"speech runs through the cut (fused joint), verify / pin"))
        elif cont_next:
            m["butt_out"] = True             # resolved in the pairwise pass
            out_note = "butt-join(pending)"
        else:
            out_note = "⚠ NO-DECAY"
            warns.append((
                s, b, "out",
                f"OUT: no decay found for '{wb['w']}'"
                f"{' [LOW-PROB]' if lowprob else ''} and the next raw word is KILLED "
                f"— speech may run through the cut; widen by ear or slice-ASR. "
                f"Boundary kept as authored, do NOT ship unverified."))

        if m["pin_out"]:
            s["end"], m["butt_out"], out_note = b, False, "pin_out (kept)"
            del warns[n_warn_out:]

        # degenerate guard: never write an inverted/collapsed segment
        if float(s["end"]) <= float(s["start"]) + 0.05:
            s["start"], s["end"] = m["orig_a"], m["orig_b"]
            warns.append((s, a, "in", "measurement collapsed the segment — authored "
                                      "boundaries restored; re-author this pair"))
            in_note += "/restored"
            out_note += "/restored"
        # (segment, its IN time, its OUT time, line) — both boundaries, because pass 3 may split the
        # segment between them and each note then belongs to a different written index
        status.append((s, float(s["start"]), float(s["end"]),
                       f"…{wb['w'][:14]:<14} in:{in_note:<26} out:{out_note}"))

    # ---------------- pass 2: pairwise joint resolution ----------------
    # Same invariant as refine-cuts.py pass 3: consecutive same-clip source-ordered
    # segments may never overlap, and a continuous split shares ONE boundary.
    for i in range(len(segs) - 1):
        x, y = segs[i], segs[i + 1]
        mx, my = meta[i], meta[i + 1]
        if mx["clip"] != my["clip"]:
            continue
        gap = my["orig_a"] - mx["orig_b"]
        if not (-0.5 < gap < JOINT_GAP_S) or my["orig_a"] <= mx["orig_a"]:
            continue                       # not one joint (dead-air kill or reuse)
        wd = clips[mx["clip"]]["words"]
        contiguous, cgap = continuous_split(wd, mx["i_last"], my["i_first"])
        if not contiguous and cgap is not None:
            warns.append((x, float(x["end"]), "out",
                          f"adjacent words but {cgap:.1f}s of silence before seg<N1> — a dead-air "
                          f"KILL, not a continuous split; both edges measured, the silence is cut"))
        xb, ya = float(x["end"]), float(y["start"])
        if contiguous and (mx["butt_out"] or my["butt_in"] or ya < xb):
            # one unbroken take split for the timeline: ONE shared boundary, placed
            # in the inter-word gap near the midpoint
            if (mx["pinned"] or mx["pin_out"]) and (my["pinned"] or my["pin_in"]):
                continue
            if (mx["pinned"] or mx["pin_out"]):
                shared = xb
            elif (my["pinned"] or my["pin_in"]):
                shared = ya
            else:
                # place the shared boundary in an inter-word gap BY TIME, never by
                # index — an out-pad overshoot makes the index unreliable (it made
                # seg i look like it keeps the next word), same rule as refine's
                # pass 3
                mid = (xb + ya) / 2
                k = max((j for j in range(len(wd) - 1) if wd[j]["end"] <= mid),
                        default=None)
                shared = mid if k is None else \
                    min(max(mid, wd[k]["end"]), wd[k + 1]["start"])
            x["end"] = y["start"] = round(shared, 3)
            infos.append((x, shared, "out", f"[joint] seg<N>/<N1>: continuous split — "
                                            f"shared boundary @{shared:.3f}"))
        elif ya < xb:
            # real cut whose measured edges crossed in the shared silence
            if (mx["pinned"] or mx["pin_out"]) and (my["pinned"] or my["pin_in"]):
                warns.append((x, xb, "out", f"OVERLAP {int((xb-ya)*1000)}ms with seg<N1> but both "
                                            f"pinned — re-author one side (splice will abort)"))
            elif (mx["pinned"] or mx["pin_out"]):
                y["start"] = x["end"]
            elif (my["pinned"] or my["pin_in"]):
                x["end"] = y["start"]
            else:
                mid = round((xb + ya) / 2, 3)
                x["end"] = y["start"] = mid
                infos.append((x, mid, "out", f"[joint] seg<N>/<N1>: OVERLAP {int((xb-ya)*1000)}ms — "
                                             f"butt-joined @{mid:.3f}"))

    # ---------------- pass 3: interior dead air (measured, never trusted) ----------------
    # The "silences > 0.4 s = dead air" rule used to live only in the author's transcript-gap
    # split, which trusts WhisperX word boundaries. On your-job (2026-09-04) a p0.35 "the"
    # was stretched by the aligner across a 0.9 s pause ("about [0.9 s] the Claude"), so no
    # inter-word gap existed and 0.8 s of room tone shipped inside one segment. you found it
    # on the timeline. So the rule is measured here on the envelope: any run below the local
    # speech threshold lasting >= DEAD_AIR_S strictly inside a segment splits it, out = last
    # loud hop + TAIL_S, in = first loud hop (or an aligner start just before it, a soft
    # onset) − LEAD_S (the same uniform tails as pass 1).
    # A pin protects a segment's BOUNDARIES, not its interior: a pinned segment is split too and its
    # outer in/out stay exactly where they were (the 2026-09-13 outro hand pass: every segment was
    # pinned after the audit, so a 940 ms pause after "So" and 1.4 s inside "in API [ ] equivalent
    # cost" shipped, and you razored both out by hand). "keep_pauses": true is the explicit opt-out
    # for a deliberate pause. A word is assigned to the part holding its END, so an aligner-stretched
    # word whose audible part sits after the pause travels with the second half.
    new_segs, new_meta = [], []
    parts_of = {}      # parent segment -> the part(s) it becomes; [itself] when it is not split
    for i, s in enumerate(segs):
        m = meta[i]
        env = envs[m["clip"]]
        wd = clips[m["clip"]]["words"]
        a, b = float(s["start"]), float(s["end"])
        parts_of[id(s)] = [s]
        if b - a < 2 * DEAD_AIR_S + 0.3:
            new_segs.append(s); new_meta.append(m); continue
        fl = env.floor((a + b) / 2)
        thr = fl + 10.0
        # quiet runs: q0 = first quiet hop (the previous sound's decay end), q1 = the next loud hop
        # (the next sound's onset). A run ends at the FIRST loud hop, blip or word: a lip smack in
        # the middle of a pause just means the cut lands 40 ms before the smack, which is a natural
        # onset anyway, and the remaining quiet is measured as its own run.
        runs, q0 = [], None
        for k in range(env.idx(a + 0.15), env.idx(b - 0.15)):
            if env.db[k] < thr:
                if q0 is None:
                    q0 = env.t(k)
            elif q0 is not None:
                if env.t(k) - q0 >= DEAD_AIR_S:
                    runs.append((q0, env.t(k)))
                q0 = None
        if not runs:
            new_segs.append(s); new_meta.append(m); continue
        if s.get("keep_pauses"):
            for q0, q1 in runs:
                warns.append((s, q0, None, f"{int((q1-q0)*1000)} ms of dead air inside a keep_pauses "
                                           f"segment @{q0:.2f}–{q1:.2f} — left whole by request"))
            new_segs.append(s); new_meta.append(m); continue
        cut_at = []
        for q0, q1 in runs:
            # q1 is the first hop above floor + 10 dB, so a soft onset (a /k/, an /s/) starts before it
            # and q1 − LEAD cut 62 ms into 'calls' (09-20). An aligner start close before q1 is the
            # earlier onset, whatever its probability (keeping 0.25 s of pause costs less than an IN
            # inside a word); one further back is the stretched word this pass exists for ("about
            # [0.9 s] the"), so q1 stands. The floor at the OUT is defensive: the reach is shorter than
            # DEAD_AIR_S − TAIL_S − LEAD_S, so the IN cannot come back past it unless SOFT_ONSET_S grows.
            on = min((w["start"] for w in wd if q1 - SOFT_ONSET_S <= w["start"] < q1), default=q1)
            # q0 is the first BROADBAND-quiet hop: the word before the pause may still be saying its final consonant
            # there (fix 7). The word is the last one starting before q0, unless the aligner stretched it over the pause.
            wq = max((w for w in wd if w["start"] < q0), key=lambda w: w["start"], default=None)
            if wq is not None and wq["end"] <= q0 + DECAY_CAP_S:
                q0 = consonant_end(env.hf, HOP_S, wq, q0, q1 - DEAD_AIR_S / 2)
            out_t = round(q0 + TAIL_S, 3)
            in_t = round(max(on - LEAD_S, q0 + TAIL_S + 0.01), 3)
            if out_t - a < 0.25 or b - in_t < 0.25 or (cut_at and out_t - cut_at[-1][1] < 0.25):
                continue
            cut_at.append((out_t, in_t, q0, q1))
        if not cut_at:
            new_segs.append(s); new_meta.append(m); continue
        bounds = [a] + [t for cut in cut_at for t in cut[:2]] + [b]
        parts = [(bounds[j], bounds[j + 1]) for j in range(0, len(bounds), 2)]
        # every word the parent plays goes to exactly ONE part, so the parts' transcripts join to the
        # parent's word list: the part holding its END (an aligner-stretched word starts in the
        # silence, its audible part is where it ends), else the part holding its START (a word whose
        # aligner end overshoots into the removed pause: 'tasks,' 572.04–572.52 against an OUT at
        # 572.447 fell in neither part and cut-proof reported 'insert tasks', 09-20), else the nearest
        # part. The parent plays a word that sits inside its FINAL [a, b] or overlaps it by 30 ms or half
        # the word: a killed neighbour grazed by the IN clamp's 10 ms, a frame-snapped pinned OUT or
        # pass 2's shared boundary never joins the text, a kept word whose aligner end overshoots does.
        def plays(w):
            ov = min(w["end"], b) - max(w["start"], a)
            return (a <= w["start"] and w["end"] <= b) or \
                (ov > 0 and ov >= min(0.03, (w["end"] - w["start"]) / 2))
        pwords = [w for w in wd if plays(w)]
        owned = [[] for _ in parts]
        for w in pwords:
            j = next((j for j, (pa, pb) in enumerate(parts) if pa <= w["end"] <= pb), None)
            if j is None:
                j = next((j for j, (pa, pb) in enumerate(parts) if pa <= w["start"] <= pb), None)
                # the word's end runs past an interior split OUT (more than the aligner's 20 ms frame):
                # the text keeps it, but the split may have cut its tail off, which cut-proof can no
                # longer see once the text holds the word (the 09-20 'tasks,' sibilant)
                if j is not None and j < len(parts) - 1 and w["end"] - parts[j][1] > 0.02:
                    warns.append((s, parts[j][1], "out",
                                  f"'{w['w']}' ends {round((w['end'] - parts[j][1]) * 1000)} ms past the split "
                                  f"OUT: the dead-air split may clip it, verify by slice-ASR / pin"))
            if j is None:
                j = min(range(len(parts)), key=lambda j: max(0.0, parts[j][0] - w["end"], w["start"] - parts[j][1]))
                if parts[0][0] < w["start"] and w["end"] < parts[-1][1]:
                    # keyed to the part that now holds the word, so the ⚠ names the segment its text is in
                    past = w["start"] > parts[j][1]      # the word lies after the part: key its OUT
                    warns.append((s, parts[j][1] if past else parts[j][0], "out" if past else "in",
                                  f"'{w['w']}' @{w['start']:.2f}–{w['end']:.2f} lies inside the removed dead "
                                  f"air: the aligner or the envelope is wrong, verify by slice-ASR"))
            owned[j].append(w)
        parts_of[id(s)] = []
        for j, (pa, pb) in enumerate(parts):
            ns = dict(s)
            ns["start"], ns["end"] = pa, pb
            # the outer pins and the beat belong to the outer boundaries only
            if pa != a:
                ns.pop("pin_in", None)
            if pb != b:
                ns.pop("pin_out", None); ns.pop("beat", None)
            # a wordless parent keeps its own text on its first part only (never duplicated)
            ns["transcript"] = " ".join(w["w"] for w in owned[j]) if pwords else \
                (s.get("transcript", "") if j == 0 else "")
            ovl = [k for k, w in enumerate(wd) if w["end"] > pa and w["start"] < pb]
            new_segs.append(ns); parts_of[id(s)].append(ns)
            new_meta.append(dict(m, orig_a=pa, orig_b=pb,
                                 i_first=ovl[0] if ovl else None, i_last=ovl[-1] if ovl else None))
        for (o_t, i_t, q0, q1) in cut_at:
            infos.append((s, o_t, "out",
                          f"[split] seg<N>: {round((q1 - q0)*1000)} ms of dead air "
                          f"@{q0:.2f}–{q1:.2f} → cut {o_t:.3f} | {i_t:.3f}"))
    if len(new_segs) != len(segs):
        print(f"[polish] dead-air pass: {len(segs)} → {len(new_segs)} segments")
    segs[:] = new_segs
    meta[:] = new_meta

    # ---------------- hot-cut QA sweep ----------------
    for i, s in enumerate(segs):
        m = meta[i]
        if m["i_last"] is None:
            continue
        wd = clips[m["clip"]]["words"]
        env = envs[m["clip"]]
        b = float(s["end"])
        # skip resolved butt joints (the next segment resumes exactly here)
        if i + 1 < len(segs) and abs(float(segs[i + 1]["start"]) - b) < 0.002 and \
                meta[i + 1]["clip"] == m["clip"]:
            continue
        # window ends at the next TRUSTED word (a low-prob next word's start is
        # fiction and must not shield the sweep)
        kk = m["i_last"] + 1
        while kk < len(wd) and wd[kk].get("prob", 1.0) <= LOWPROB:
            kk += 1
        hi = min(b + 0.15, (wd[kk]["start"] - 0.01) if kk < len(wd) else b + 0.15)
        if hi - b < 0.04:
            continue
        fl = env.floor(b)
        if env.band(b + 0.01, hi) > fl + 12:
            warns.append((s, b, "out", f"OUT @{b:.2f}: speech energy past the cut — "
                                       f"possible clipped tail (verify; may be the next killed "
                                       f"word only if it sits closer than the trusted window)"))

    for s in segs:
        s["no_refine"] = True

    # ---------------- one index space: number every buffered line against the FINAL array ----------
    # seg N below = the index in the cuts.json this run just wrote. An unsplit segment keeps its
    # identity through pass 3; a split parent resolves to the part that holds the line's own
    # boundary time, so a warning always names the segment a reviewer can look up.
    pos = {id(x): k for k, x in enumerate(segs)}

    def where(seg, t, side):
        return resolve_index(pos, parts_of, seg, t, side)

    def lbl(k):
        return "??" if k < 0 else str(k)       # -1 = the resolver could not key the line (it said so)

    def fill(msg, k):
        return msg.replace("<N1>", lbl(k + 1 if k >= 0 else k)).replace("<N>", lbl(k))

    print("# seg N = index in the cuts.json this run writes; @T = that segment's own boundary")
    for seg, a_, b_, msg in status:
        # a status line carries BOTH notes, and pass 3 can split its segment between them: number each
        # side against the part that now owns it (segN/M) instead of keying the whole line by the IN
        # time, which made the `out:` note read as a boundary belonging to a later index (b20).
        ki, ko = where(seg, a_, "in")[0], where(seg, b_, "out")[0]
        print(f"seg{lbl(ki):>3} {msg}" if ki == ko else f"seg{lbl(ki)}/{lbl(ko)} {msg}")
    for seg, t, side, msg in infos:
        print(fill(msg, where(seg, t, side)[0]))
    for seg, t, side, msg in warns:
        k, tt = where(seg, t, side)
        print(f"⚠ seg{lbl(k)} @{tt:.2f} {fill(msg, k)}")
    dur = sum(float(s["end"]) - float(s["start"]) for s in segs)
    os.makedirs(tmpdir, exist_ok=True)
    json.dump(cuts, open(os.path.join(tmpdir, "cuts.json"), "w", encoding="utf-8"), indent=1)
    for f in ("cuts.refined.json", "cuts.snapped.json"):
        p = os.path.join(tmpdir, f)
        if os.path.exists(p):
            os.remove(p)
    print(f"[polish] {len(segs)} segments pinned, runtime {dur:.1f}s "
          f"({dur/60:.2f} min), {len(warns)} ⚠ — wrote {tmpdir}/cuts.json; "
          f"re-run splice.sh to consume it")


if __name__ == "__main__":
    main()
