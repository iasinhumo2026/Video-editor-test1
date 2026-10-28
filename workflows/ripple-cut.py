#!/usr/bin/env python3
"""ripple-cut.py: re-time everything a cut change moves — the transcript clock, the graphics plan, the placement,
the SFX cues and the text-animation metas — from the OLD EDL to the current one, in one pass.

  uv run workflows/ripple-cut.py projects/<job>                                  # DRY RUN: what moves, what breaks
  uv run workflows/ripple-cut.py projects/<job> --from transcript/cuts.pre-six-lead.json
  uv run workflows/ripple-cut.py projects/<job> --apply                          # write, each file backed up first

  --from <edl>   the EDL the downstream layers were authored against (default transcript/cuts.pre-recut.json)
  --to <edl>     the EDL they must land on (default transcript/cuts.json)
  --tag <name>   backup suffix on --apply (default pre-ripple: placement.pre-ripple.json …)
  --fps <r>      the grid shifts are reported on (default: the plan's fps, else 24000/1001)
  --retake <t>   a RE-RECORD: map by the WORDS, through <t> = the approved cut's canonical transcript (its own clock),
                 onto the new take's (re-derived from words.json + --to). --from is the approved EDL (its sha1 is the
                 plan's cut_rev). Ends map on their own words, so a row's length follows the new delivery (RE-RENDER)
  --apply        actually write

Every anchor is mapped THROUGH THE SOURCE, never by one global offset: old timeline time -> the source frame it
shows -> where that source frame sits on the new timeline. A row whose material was cut away is reported as
ORPHANED and left alone; a row whose span now straddles a new cut is reported as STRADDLING and moved by its start
only, because a placed render has a fixed duration and cannot absorb a hole. The SFX cues of a placed graphic that
came out STRADDLING or TRIMMED move with it by the same shift (they sit on its render's frames) and are named under it.

Exit 0 = every row landed. Exit 1 = rows are still on a DEAD ANCHOR: they keep their old times while the plan
carries the NEW cut_rev, so place-graphics.py's stale-plan guard waves them through. Re-anchor or delete each one
before the lane's placers run — nothing downstream reads the `ripple` marker this writes.

THE LAYOUT MAP (a plan with a top-level `layout`, the Talking Head Explainer's layout.md § 12) is re-tiled through
the source too: each span keeps the material it framed. An edge whose frame was cut away moves to the span's nearest
surviving material and is reported as a DEAD EDGE: it counts toward exit 1 only when the neighbouring span's edge was
cut too (the switch itself is gone, so the layout wants a look); when the neighbour's edge maps cleanly the span only
lost the sentence at the switch, and it is listed at the end as a switch to check. A span whose material was all cut
is DROPPED (checked FIRST, so a cut first or last span is dropped, never crashed on); a gap left between two spans is
CLOSED by extending the earlier one (reported); the first span starts at 0 and the last ends on the new duration.
Under --retake the map is re-tiled through the WORDS instead: a span's material is the words it holds, so a span the
new take says none of is DROPPED, and an edge on a dropped word moves to the span's first (last) word still said.
Every cell's `shot_cuts` (the speech-anchored picture cuts inside its render) are mapped each through the source, and
one on cut material is dropped and named. A captions cell starting at 0 is re-fit to the new duration. Each
`layout_deviations[].at` is re-mapped (on cut material: ORPHANED). A `variants.<name>` (from, layout, cells or beats,
duration, its waivers) moves rigidly by the shift of its `from`, which is re-mapped like any start: its tail is its own
EDL's material, which an organic re-cut does not touch. Crowns in face-frame.json are named for a re-read.

A SECTION sub-job (its graphics-plan.json carries `timeline_offset`) runs every row on the section's own clock, but its
SFX cues are SEQUENCE times: each is mapped at `at - offset` and written back at the section's offset. When the new
EDL was read back off the timeline (`lanes/premiere/live-edl.py --write`), its first `_timeline` start IS that offset:
a creator's ripple earlier in the sequence that moved the whole section re-times every cue by the move, rewrites the
plan's `timeline_offset`, and shifts the cues recorded in `sfx-plan.meta.json` with them (the placers refuse a section
whose offset disagrees with the live V1 until this has run).

--apply writes NOTHING until every step has computed: each file is then backed up and written in one go.

A RE-RECORD (--retake, 2026-10-05) has no shared source: the creator filmed the same script again, so a frame of the
old take means nothing to the new one. The SPOKEN WORDS are the shared material instead: the approved cut's canonical
transcript and the new cut's are aligned word by word (difflib, in order, a lone short word never trusted on its own),
and every anchor keeps its offset to the word it sits on, or to the nearer word of a pause (a cut-in 30 ms before 'one'
stays 30 ms before 'one'). A row on a line the new take does not say is ORPHANED; a row's end maps on its own word, so
the report lists every cell to RE-RENDER at its new length, and every text-animation cell whose copy the new take no
longer says in its window (COPY).

What this tool does NOT do, on purpose: the timeline half. Re-lay V1/A1 from the new EDL, re-apply the audio polish,
move the grade clip, then let the lane's own placers re-place from the files this rewrote.

Why this exists (2026-09-19): a fluff pass asked for AFTER the grade and the graphics were done rebuilt every
downstream layer by hand — the transcript clock, 29 plan rows, 26 placed outro graphics, the text metas, the SFX
cues, the grade span and the baked camera moves, each by its own throwaway script, and then twice more for the two
hand re-cuts that followed. Each of those scripts hard-coded that job's sequence name and tick constant, so none of
it survived the job. The measurement is the same every time: this is it.

The rule this serves: edit-video § the cut is locked — a cut change after step 3 is a declared RE-CUT, and the
re-time runs before anything is touched on the timeline.
"""
import argparse, difflib, hashlib, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

EPS = 1e-4


def load_edl(path):
    return load_edl_doc(json.load(open(path, encoding='utf-8')))


def load_edl_doc(doc):
    """Segments in EDL order, each with its source span and the timeline span it lands on. A segment the creator sped
    up carries `speed` (5.0 = 500 %, lanes/premiere/lab-notes.md): it covers (end - start) / speed of timeline, and `k`
    converts timeline seconds inside it to source seconds."""
    segs = doc['segments']
    rows, t = [], 0.0
    for s in segs:
        k = float(s.get('speed') or 1.0)
        dur = (float(s['end']) - float(s['start'])) / k
        rows.append(dict(clip=Path(s.get('clip', '')).name, s0=float(s['start']), s1=float(s['end']),
                         t0=t, t1=t + dur, k=k))
        t += dur
    return rows, t


def fps_of(text):
    num, _, den = str(text).partition('/')
    return float(num) / float(den or 1)


def overlap(a, b):
    return 0.0 if a['clip'] != b['clip'] else max(0.0, min(a['s1'], b['s1']) - max(a['s0'], b['s0']))


class Ripple:
    """Old segment -> new segment, IN ORDER, then the source frame inside it.

    Matching is ordinal, not a source lookup: a cold open replays material the body also uses, and a pure
    "which segment holds this source time" search happily sends the hook's graphics into the demo.
    """

    def __init__(self, old, new):
        self.old, self.new = old, new
        key = lambda r: (r['clip'], round(r['s0'], 2), round(r['s1'], 2))
        blocks = difflib.SequenceMatcher(a=[key(r) for r in old], b=[key(r) for r in new],
                                         autojunk=False).get_matching_blocks()
        self.match = {a + d: b + d for a, b, size in blocks for d in range(size)}
        for i in range(len(old)):                    # a segment whose head or tail was trimmed keeps no key, but
            if i in self.match:                      # it still lies between its neighbours: take the best overlap
                continue
            lo = max((self.match[k] for k in self.match if k < i), default=-1)
            hi = min((self.match[k] for k in self.match if k > i), default=len(new))
            cands = [(overlap(old[i], new[k]), k) for k in range(lo + 1, hi)]
            best = max(cands, default=(0.0, None))
            if best[0] > 0:
                self.match[i] = best[1]
        # A segment SPLIT by a hand cut (a pause razored out of one line) is one old segment and two or more
        # new ones: every new segment of its clip between its neighbours' matches is a home for its frames, its own
        # match tried FIRST: a cold open that replays an intact segment's material between the same neighbours took
        # its graphics when the lowest index won (2026-09-28).
        self.homes = {}
        for i, j in self.match.items():
            lo = max((self.match[k] for k in self.match if k < i), default=-1)
            hi = min((self.match[k] for k in self.match if k > i), default=len(new))
            self.homes[i] = [j] + sorted(k for k in range(lo + 1, hi) if k != j and overlap(old[i], new[k]) > 0)

    def map(self, t, side='start'):
        """-> (new timeline time, why) where why is None, 'past-the-end', 'cut' or 'trimmed'.

        A time that lands exactly ON a joint belongs to TWO segments. A start anchor belongs to the one it opens
        (search backwards, last match wins); an end anchor to the one it closes (search forwards). Reading it the
        other way round orphans a graphic that comes in on a cut whenever the outgoing segment is the one removed.
        """
        order = reversed(range(len(self.old))) if side == 'start' else range(len(self.old))
        for i in order:
            o = self.old[i]
            if not (o['t0'] - EPS <= t <= o['t1'] + EPS):
                continue
            j = self.match.get(i)
            if j is None:
                return None, 'cut'
            u = o['s0'] + (t - o['t0']) * o.get('k', 1.0)
            homes = [self.new[k] for k in self.homes.get(i, [j])]
            for n in homes:
                if n['s0'] - EPS <= u <= n['s1'] + EPS:
                    return n['t0'] + (u - n['s0']) / n.get('k', 1.0), None
            # the frame itself was trimmed off (a head, a tail, or a pause cut out of the middle): pin it to the
            # nearest surviving edge of its own material
            n = min(homes, key=lambda n: max(n['s0'] - u, u - n['s1'], 0.0))
            return n['t0'] + (min(max(u, n['s0']), n['s1']) - n['s0']) / n.get('k', 1.0), 'trimmed'
        return None, 'past-the-end'

    def surviving(self, a, b, side):
        """the span a..b's first (side='start') or last (side='end') moment of material the new EDL keeps, or None."""
        segs = [o for i, o in enumerate(self.old) if self.match.get(i) is not None and o['t1'] > a + EPS and o['t0'] < b - EPS]
        if not segs:
            return None
        return self.map(max(a, segs[0]['t0']), 'start')[0] if side == 'start' else self.map(min(b, segs[-1]['t1']), 'end')[0]


def norm_word(w):
    return re.sub(r"[^0-9a-z]+", "", str(w).lower())


class WordRipple:
    """Old cut -> a RE-RECORDED cut of the same script, through the words both takes say (--retake).

    Same interface as Ripple.map. Matching is ordinal (difflib on normalised words, in order); a block of one word is
    trusted only when the word is long (4+ letters), since a lone "the" matches anywhere. An anchor inside a matched
    word moves with that word (linear across it); an anchor in a pause keeps its offset to the NEARER matched word
    (start anchors lean to the next word, the one a graphic comes in on; end anchors to the previous), clamped inside
    the new pause. An anchor on a word the new take does not say is 'cut'.
    """

    def __init__(self, old_words, new_words):
        self.ow = [w for w in old_words if norm_word(w.get('text', ''))]
        self.nw = [w for w in new_words if norm_word(w.get('text', ''))]
        a = [norm_word(w['text']) for w in self.ow]
        b = [norm_word(w['text']) for w in self.nw]
        self.match = {}
        for i, j, size in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks():
            if size == 1 and len(a[i]) < 4:
                continue
            for d in range(size):
                self.match[i + d] = j + d
        self.new_end = max((float(w['end']) for w in self.nw), default=0.0)

    def matched_share(self):
        return len(self.match) / max(1, len(self.ow))

    def _at_word(self, i, t):
        o, n = self.ow[i], self.nw[self.match[i]]
        os_, oe, ns, ne = float(o['start']), float(o['end']), float(n['start']), float(n['end'])
        f = 0.0 if oe - os_ <= EPS else (t - os_) / (oe - os_)
        return ns + f * (ne - ns)

    def map(self, t, side='start'):
        ow = self.ow
        if not ow or not self.match:
            return None, 'cut'
        # the word holding t, else the pause it sits in: words k (before) and k + 1 (after)
        k = -1
        for i, w in enumerate(ow):
            if float(w['start']) - EPS <= t <= float(w['end']) + EPS:
                if i not in self.match:
                    return None, 'cut'
                return self._at_word(i, t), None
            if float(w['end']) < t:
                k = i
        prev, nxt = k, k + 1
        pm, nm = prev in self.match, nxt < len(ow) and nxt in self.match
        if not pm and not nm:
            return None, 'cut' if 0 <= prev and nxt < len(ow) else 'past-the-end' if nxt >= len(ow) else 'cut'
        lo = float(self.nw[self.match[prev]]['end']) if pm else 0.0
        hi = float(self.nw[self.match[nxt]]['start']) if nm else self.new_end + 10.0
        d_prev = t - float(ow[prev]['end']) if prev >= 0 else float('inf')
        d_next = float(ow[nxt]['start']) - t if nxt < len(ow) else float('inf')
        use_next = nm and (not pm or (d_next <= d_prev if side == 'start' else d_next < d_prev))
        new = (hi - d_next) if use_next else (lo + d_prev)
        new = min(max(new, lo), hi)
        if nxt >= len(ow) and new > self.new_end + 2.0:
            return None, 'past-the-end'
        return max(0.0, new), None

    def surviving(self, a, b, side):
        """Ripple.surviving through the WORDS: the span's material is the words it holds, so its first (last) moment the
        new take still says is its first (last) matched word. A span holding no word at all (a pause, the tail) keeps its
        own edge on the pause map; one whose every word the new take drops is None (dropped)."""
        inside = [i for i, w in enumerate(self.ow) if float(w['end']) > a + EPS and float(w['start']) < b - EPS]
        if not inside:
            return self.map(a if side == 'start' else b, side)[0]
        said = [i for i in inside if i in self.match]
        if not said:
            return None
        if side == 'start':
            return self.map(max(a, float(self.ow[said[0]]['start'])), 'start')[0]
        return self.map(min(b, float(self.ow[said[-1]]['end'])), 'end')[0]


def copy_check(beat, words, start, end, pad=1.0):
    """A text animation's copy words the new take says inside its window -> (said, total); stage directions skipped."""
    copy = beat.get('copy')
    if not isinstance(copy, str) or not copy.strip():
        return None
    want = [norm_word(x) for x in re.sub(r'\([^)]*\)|<[^>]*>', ' ', copy.replace('*', '')).split()]
    want = [x for x in want if x]
    have = {norm_word(w['text']) for w in words if float(w['start']) >= start - pad and float(w['end']) <= end + pad}
    return sum(1 for x in want if x in have), len(want)


def rewrite(rip, rows, keys, fps, label, out, orphans=None, rigid=None, riders=None, free_end=False, rerender=None):
    """Move each row by its START; a fixed-length render keeps its own duration. Returns the notes to print.

    `orphans` collects '<label> <name>' for every row left on a dead anchor, because NOTHING downstream
    reads the `ripple` marker: the lane's placers would lay those rows at their pre-recut times under a
    freshly stamped cut_rev. The run reports them as a block and fails, rather than trusting the note.
    `rigid` collects {name: start shift} for every row that came out TRIMMED or STRADDLING: its render did not take
    the cut, so the cues on its frames move with its start, never through the source. `riders` ({name: [cue id]})
    names those cues under the row's note, so the hand decision on the graphic covers its sound too.
    """
    notes = []
    for row, name in rows:
        start = row.get(keys[0])
        if start is None:
            continue
        if row.get('ripple') == 'orphaned':
            # Marked by an earlier ripple. Its times mean nothing now, so re-mapping them would invent a position.
            notes.append(f'  ORPHANED  {label} {name}: still orphaned from an earlier re-cut — re-anchor it or delete the row')
            if orphans is not None:
                orphans.append(f'{label} {name}')
            continue
        new_start, why = rip.map(float(start), 'start')
        if why in ('cut', 'past-the-end'):
            row['ripple'] = 'orphaned'
            notes.append(f'  ORPHANED  {label} {name}: {start:.3f}s {"is past the new end" if why == "past-the-end" else "was cut away"} — marked, left where it was, decide by hand')
            if orphans is not None:
                orphans.append(f'{label} {name}')
            continue
        held = why == 'trimmed'
        if why == 'trimmed':
            notes.append(f'  TRIMMED   {label} {name}: the frame it was anchored on is gone; pinned to the new join at {new_start:.3f}s')
        shift = new_start - float(start)
        if free_end and len(keys) > 1 and row.get(keys[1]) is not None:
            # a re-record: the end rides its own word, and a render whose length changed is re-rendered
            end = float(row[keys[1]])
            new_end, why_end = rip.map(end, 'end')
            if why_end in ('cut', 'past-the-end') or new_end <= new_start:
                new_end = new_start + (end - float(start))
                notes.append(f'  END?      {label} {name}: its end word {end:.3f}s is not in the new take — kept its length, '
                             f'set the end by hand')
            if rerender is not None and abs((new_end - new_start) - (end - float(start))) > 0.5 / fps:
                rerender.append((name, end - float(start), new_end - new_start))
            row[keys[1]] = round(new_end, 6)
            row[keys[0]] = round(new_start, 6)
            if abs(shift) > 0.5 / fps:
                out.append((name, float(start), new_start, shift))
            continue
        if len(keys) > 1 and row.get(keys[1]) is not None:
            end = float(row[keys[1]])
            new_end, why_end = rip.map(end, 'end')
            if why_end in ('cut', 'past-the-end') or abs((new_end - new_start) - (end - float(start))) > 0.5 / fps:
                held = True
                notes.append(f'  STRADDLING {label} {name}: {start:.3f}–{end:.3f}s now spans a cut — moved by its start, '
                             f're-check its tail (and any render trimmed to the old join)')
            row[keys[1]] = round(new_start + (end - float(start)), 6)
        row[keys[0]] = round(new_start, 6)
        if held and rigid is not None:
            rigid[name] = shift
            if (riders or {}).get(name):
                notes.append(f'             its cue(s) {", ".join(riders[name])} move with it by its start ({shift:+.3f}s), '
                             f'not through the source: re-check them with its tail')
        if abs(shift) > 0.5 / fps:
            out.append((name, float(start), new_start, shift))
    return notes


def layout_rows(rows):
    """[(start, end, mode, rest)] from a plan `layout`: {start, end, mode, ...} or [start, end, mode, ...] rows,
    `rest` = the row itself so its other fields ride along."""
    out = []
    for r in rows or []:
        a, b, m = (r['start'], r['end'], r['mode']) if isinstance(r, dict) else (r[0], r[1], r[2])
        out.append((float(a), float(b), m, r))
    return sorted(out, key=lambda x: x[0])


def _set(r, a, b):
    if isinstance(r, dict):
        return dict(r, start=round(a, 6), end=round(b, 6))
    return [round(a, 6), round(b, 6), *list(r)[2:]]


def remap_layout(rip, rows, old_dur, new_dur, fps, label, orphans, moved=None):
    """(new layout rows, notes): the map re-tiled on the new timeline (see the header, THE LAYOUT MAP). A DEAD EDGE
    whose neighbour's matching edge still maps cleanly is a sentence lost at the switch, not a lost switch: it goes to
    `moved` (a check, printed at the end), and only an edge whose neighbour's edge was cut too joins `orphans`."""
    notes, spans = [], []
    tol = 0.5 / fps
    surviving = rip.surviving       # through the source (Ripple) or, under --retake, through the words (WordRipple)

    rows_ = layout_rows(rows)
    dead = lambda why: why in ('cut', 'past-the-end')
    edge = []                                   # per row: (start why, end why) as mapped, before any pin
    for a, b, m, r in rows_:
        edge.append((None if a <= EPS else rip.map(a, 'start')[1], None if b >= old_dur - EPS else rip.map(b, 'end')[1]))
    for k, (a, b, m, r) in enumerate(rows_):
        if surviving(a, b, 'start') is None:        # FIRST: a span with no surviving material is gone, whatever the
            notes.append(f'  DROPPED   {label} {m} {a:.3f}–{b:.3f}s: all of its material was cut')   # 0 / end pins say
            continue
        na, wa = (0.0, None) if a <= EPS else rip.map(a, 'start')
        nb, wb = (new_dur, None) if b >= old_dur - EPS else rip.map(b, 'end')
        for side, why in (('start', wa), ('end', wb)):
            if dead(why):
                t = surviving(a, b, side)
                if side == 'start': na = t
                else: nb = t
                j = k - 1 if side == 'start' else k + 1
                lost = not (0 <= j < len(rows_)) or dead(edge[j][1 if side == 'start' else 0])
                notes.append(f'  DEAD EDGE {label} {m} {a:.3f}–{b:.3f}s: its {side} ({a if side == "start" else b:.3f}s) '
                             f'was cut away, moved to its surviving material at {t:.3f}s: check the switch'
                             + ('' if lost else ' (the neighbouring edge maps cleanly: the switch survives)'))
                (orphans if lost else (moved if moved is not None else [])).append(f'{label} {m} {a:.3f}s ({side})')
            elif why == 'trimmed':
                notes.append(f'  TRIMMED   {label} {m} {a:.3f}–{b:.3f}s: its {side} frame is gone, pinned to the new join')
        if nb - na <= tol:
            notes.append(f'  DROPPED   {label} {m} {a:.3f}–{b:.3f}s: collapsed to nothing on the new timeline')
            continue
        spans.append([na, nb, m, r])
    spans.sort(key=lambda x: x[0])
    if spans and spans[0][0] > tol:
        notes.append(f'  GAP       {label}: nothing framed 0–{spans[0][0]:.3f}s, the first span extended to 0')
    if spans:
        spans[0][0] = 0.0
    for x, y in zip(spans, spans[1:]):
        if y[0] - x[1] > tol:
            notes.append(f'  GAP       {label}: {x[1]:.3f}–{y[0]:.3f}s left unframed, closed by extending the {x[2]} before it')
        elif x[1] - y[0] > tol:
            notes.append(f'  OVERLAP   {label}: {x[2]} ran {x[1] - y[0]:.3f}s into the {y[2]} after it, cut at {y[0]:.3f}s')
        x[1] = y[0]
    if spans:
        spans[-1][1] = new_dur
    return [_set(r, a, b) for a, b, m, r in spans], notes


def remap_times(rip, ts, label, notes):
    """Timeline times (a cell's shot_cuts) mapped each through the source -> the survivors; one on cut material is
    dropped and named. A picture cut inside a render is speech-anchored: a hole inside the cell moves the cuts after it."""
    out = []
    for t in ts or []:
        n, why = rip.map(float(t), 'start')
        if why in ('cut', 'past-the-end'):
            notes.append(f'  DROPPED   {label} shot cut {float(t):.3f}s: its material was cut')
            continue
        out.append(round(n, 6))
    return out


def report(label, out, fps, notes):
    if not out and not notes:
        print(f'{label}: nothing moves')
        return
    shifts = sorted({round(s, 3) for _, _, _, s in out})
    print(f'{label}: {len(out)} row(s) move, {min(shifts) if shifts else 0:+.3f}s … {max(shifts) if shifts else 0:+.3f}s '
          f'({min(shifts) * fps if shifts else 0:+.0f} … {max(shifts) * fps if shifts else 0:+.0f} frames)')
    for name, a, b, s in out[:6]:
        print(f'    {name:<10} {a:9.3f} -> {b:9.3f}  ({s:+.3f}s / {s * fps:+.0f} fr)')
    if len(out) > 6:
        print(f'    … {len(out) - 6} more')
    for n in notes:
        print(n)


PENDING = []   # every write of an --apply run, made only once every step has been computed (flush)


def save(path, doc, tag, apply, indent=1):
    """Queue the file's new content (--apply): nothing is written until the whole run has computed, so a failure
    part-way leaves every file as it was, never a transcript re-clocked under an un-rippled plan."""
    if not apply:
        return
    PENDING.append((path, json.dumps(doc, indent=indent).encode('utf-8'), tag))


def flush():
    """Write every queued file, each backed up first (a backup already there is kept: it is the pre-ripple original)."""
    for path, body, tag in PENDING:
        backup = path.with_suffix(f'.{tag}{path.suffix}')
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
        path.write_bytes(body)
    PENDING.clear()


def derive_transcript(job, new_path):
    """The canonical transcript as a FUNCTION of words.json + the EDL (export-transcript.py) -> its bytes, or None.

    export-transcript.py finds the job's corrections.local.json from the OUT path's own parents
    (<job>/outputs/<file> -> <job>/corrections.local.json), so a draft written flat into the temp dir loses every
    per-job correction in silence, and the canonical transcript is where they are applied ONCE (CLAUDE.md
    § transcript corrections). So the draft is written into a MIRROR of the job layout with the override carried
    in beside it; the repo-wide map still resolves off the exporter's own location."""
    words_src = job / 'transcript' / 'words.json'
    exporter = Path(__file__).resolve().parent.parent / '.claude/skills/rough-cut/scripts/export-transcript.py'
    if not (words_src.exists() and exporter.exists()):
        return None
    with tempfile.TemporaryDirectory(prefix='ripple-cut-') as td:
        mirror = Path(td) / job.name / 'outputs'
        mirror.mkdir(parents=True)
        local = job / 'corrections.local.json'
        if local.exists():
            shutil.copyfile(local, mirror.parent / local.name)
        draft = mirror / f'{job.name}.transcript.json'
        subprocess.run([sys.executable, str(exporter), str(words_src), str(new_path), str(draft)], check=True)
        body = draft.read_bytes()
    return body if json.loads(body).get('words') else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--from', dest='src', default='transcript/cuts.pre-recut.json')
    ap.add_argument('--to', dest='dst', default='transcript/cuts.json')
    ap.add_argument('--tag', default='pre-ripple'); ap.add_argument('--fps')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--force', action='store_true', help='ripple again even though the job already names the target EDL')
    ap.add_argument('--retake', metavar='TRANSCRIPT', help="a re-record: the approved cut's canonical transcript; map by words")
    a = ap.parse_args()
    job = Path(a.job).resolve()
    old_path, new_path = job / a.src, job / a.dst
    for p in (old_path, new_path):
        if not p.exists():
            sys.exit(f'✗ no {p}')
    old, old_dur = load_edl(old_path)
    new, new_dur = load_edl(new_path)
    draft = None
    if a.retake:
        rt = Path(a.retake) if Path(a.retake).is_absolute() else (job / a.retake if (job / a.retake).exists() else Path(a.retake).resolve())
        if not rt.exists():
            sys.exit(f'✗ --retake: no {rt}')
        if not (job / 'transcript' / 'words.json').exists():
            sys.exit('✗ --retake needs the new take\'s transcript/words.json: the words ARE the map')
        draft = derive_transcript(job, new_path)
        if not draft:
            sys.exit('✗ --retake: the new canonical transcript could not be derived (0 words)')
        olddoc = json.load(open(rt, encoding='utf-8'))
        rip = WordRipple(olddoc['words'] if isinstance(olddoc, dict) else olddoc, json.loads(draft)['words'])
        print(f'RE-TAKE: {rt.name} ({len(rip.ow)} words) -> the new take ({len(rip.nw)} words): '
              f'{len(rip.match)} matched ({rip.matched_share():.0%} of the approved script)')
    else:
        rip = Ripple(old, new)

    plan_path = next((p for p in (job / 'graphics-plan.json', job / 'hf-graphics' / 'graphics-plan.json') if p.exists()), None)
    plan = json.load(open(plan_path, encoding='utf-8')) if plan_path else None
    fps = fps_of(a.fps or (plan or {}).get('fps') or '24000/1001')
    new_rev = hashlib.sha1(new_path.read_bytes()).hexdigest()[:12]
    # A SECTION sub-job: the plan's timeline_offset is where the section's EDL time 0 sits on the shared sequence. Rows and
    # metas run on the section's own clock, but sfx-plan.json's `at` are SEQUENCE times (sfx-plan.py adds the offset), and a
    # creator's ripple earlier in the sequence moves the whole section. An EDL re-read by live-edl.py carries `_timeline`,
    # and its first start IS the section's offset now (2026-09-28: every cue came back orphaned off the section's clock).
    off0 = off1 = None
    if plan is not None and plan.get('timeline_offset') is not None:
        off0 = off1 = float(plan['timeline_offset'])
        seg0 = (json.load(open(new_path, encoding='utf-8')).get('segments') or [{}])[0]
        if isinstance(seg0.get('_timeline'), list) and seg0['_timeline']:
            off1 = float(seg0['_timeline'][0])

    # A RE-RUN IS THE DANGEROUS CASE. Every anchor is read as an OLD-timeline time, so a second pass over
    # already-rippled files maps them a second time: rows double-shift onto each other and the ones that landed
    # where cut material used to be come back marked ORPHANED — and the run reports all of it as ordinary work.
    # The plan's cut_rev is the stamp that says which EDL these files are already on.
    if plan is not None and plan.get('cut_rev') == new_rev and not a.force:
        sys.exit(f'✗ {plan_path.name} already carries cut_rev {new_rev}: this job is ALREADY timed against '
                 f'{new_path.name}.\n  A second pass would re-map times that are on the NEW timeline and silently '
                 f'double-shift them. Nothing was read or written.\n  Restore from the .{a.tag}. backups if a pass '
                 f'went wrong, or pass --force if the stamp itself is wrong.')
    old_rev = hashlib.sha1(old_path.read_bytes()).hexdigest()[:12]
    if plan is not None and plan.get('cut_rev') and plan['cut_rev'] not in (old_rev, new_rev):
        # --from is the BASELINE every anchor is read against, and picking the wrong snapshot out of a folder
        # of them maps every row from a timeline the plan was never on — silently, because the arithmetic is
        # just as well-behaved. The stamp is the only thing that knows which one it was.
        print(f'⚠ {plan_path.name} is stamped cut_rev {plan["cut_rev"]}, but --from {old_path.name} is {old_rev}: '
              f'this is NOT the EDL the plan was authored against. Every row would be mapped off the wrong '
              f'baseline. Pick the snapshot whose sha1 matches the stamp before --apply.')
    if plan is None and (job / 'hf-graphics' / f'placement.{a.tag}.json').exists() and not a.force:
        print(f'⚠ hf-graphics/placement.{a.tag}.json already exists: a ripple has run here before. With no '
              f'graphics-plan.json to carry cut_rev, nothing can prove these files are not already re-timed — '
              f'check one row against the new EDL before --apply.')

    print(f'{old_path.name} -> {new_path.name}   {len(old)} segments / {old_dur:.3f}s  ->  {len(new)} / {new_dur:.3f}s '
          f'({new_dur - old_dur:+.3f}s, {(new_dur - old_dur) * fps:+.0f} frames at {fps:.3f} fps)')
    print(f'cut_rev {old_rev} -> {new_rev}'
          + ('' if a.apply else '   [DRY RUN: nothing is written]'))
    if off0 is not None and off1 != off0:
        print(f'section: timeline_offset {off0:.6f} -> {off1:.6f} ({off1 - off0:+.3f}s, {new_path.name}\'s first _timeline): '
              'the SFX cues move with it')

    # 1. the canonical transcript — RE-DERIVED, not shifted
    tpath = job / 'outputs' / f'{job.name}.transcript.json'
    words_src = job / 'transcript' / 'words.json'
    exporter = Path(__file__).resolve().parent.parent / '.claude/skills/rough-cut/scripts/export-transcript.py'
    if tpath.exists() and words_src.exists() and exporter.exists():
        # The canonical transcript is a FUNCTION of words.json + the EDL, so the re-cut re-runs that function:
        # the repo's own law is to re-run a step from its durable inputs rather than patch its output. Shifting
        # the old file cannot give back a passage the re-cut RESTORED (those words are in words.json and in no
        # timeline at all), and it leaves the doc's `text` prose still describing lines the video no longer has.
        before = len(json.load(open(tpath, encoding='utf-8')).get('words', []))
        body = draft or derive_transcript(job, new_path)
        after = len(json.loads(body).get('words', [])) if body else 0
        if after == 0 and before:
            print(f'✗ the re-derive produced 0 words from {words_src.name}: leaving {tpath.name} alone and '
                  f're-deriving nothing. Check that words.json covers the clips this EDL names.')
        else:
            print(f'transcript: re-derived from {words_src.name} + {new_path.name}, {before} -> {after} words'
                  + ('' if a.apply else '   (preview only, nothing written)'))
            if a.apply and body:
                PENDING.append((tpath, body, a.tag))
    elif tpath.exists():
        # No words.json (an archived job, a client tree): shift what is there, and rebuild the prose with it.
        doc = json.load(open(tpath, encoding='utf-8'))
        kept, dropped = [], 0
        for w in doc.get('words', []):
            s, why = rip.map(float(w['start']), 'start')
            e, why_e = rip.map(float(w['end']), 'end')
            if why in ('cut', 'past-the-end') or why_e in ('cut', 'past-the-end'):
                dropped += 1
                continue
            w['start'], w['end'] = round(s, 3), round(e, 3)
            kept.append(w)
        doc['words'] = kept
        if 'text' in doc:   # the prose is the kept words: leaving it stale ships a script of lines that were cut
            doc['text'] = re.sub(r'\s+([,.!?;:])', r'\1', ' '.join(w.get('text', '') for w in kept)).strip()
        print(f'⚠ no {words_src.name}: SHIFTED the transcript clock instead of re-deriving it — {len(kept)} words '
              f're-clocked, {dropped} dropped. Restored material cannot come back this way.')
        save(tpath, doc, a.tag, a.apply)

    # 2. the graphics plan
    orphans, moved = [], []
    if plan:
        out = []
        beats = plan.get('beats') or plan.get('cells') or []
        # the caption layer spans the whole cut: it is re-fit to the new duration, never moved by its start (a moved
        # captions cell straddled every re-cut with end = the OLD duration, and the placer lays it to that end)
        is_caps = lambda b: (b.get('kind') == 'captions' or b.get('id') == 'captions') and float(b.get('start') or 0) <= EPS
        notes = []
        for b in beats:
            if is_caps(b) and b.get('end') is not None and abs(float(b['end']) - new_dur) > EPS:
                notes.append(f'  REFIT     beat {b.get("id", "captions")}: the caption layer now ends at {new_dur:.3f}s '
                             f'(was {float(b["end"]):.3f}s): rebuild it (captions.py)')
                b['end'] = round(new_dur, 6)
        rerender = [] if a.retake else None
        notes += rewrite(rip, [(b, b.get('id', '?')) for b in beats if not is_caps(b)], ('start', 'end'), fps, 'beat', out, orphans,
                         free_end=bool(a.retake), rerender=rerender)
        if a.retake:
            nwords = json.loads(draft)['words']
            for b in beats:
                if b.get('ripple') == 'orphaned' or b.get('kind') != 'text-animation':
                    continue
                said = copy_check(b, nwords, float(b['start']), float(b['end']))
                if said and said[0] < said[1]:
                    notes.append(f'  COPY      beat {b.get("id", "?")}: the new take says {said[0]} of the {said[1]} words of '
                                 f'{b.get("copy")!r} in its window — rewrite the copy (and its text.json phrase) to what he says')
            if rerender:
                notes.append(f'  RE-RENDER {len(rerender)} cell(s) whose length follows the new delivery: '
                             + ', '.join(f'{n} {d0:.2f}->{d1:.2f}s' for n, d0, d1 in rerender))
        for b in beats:                                       # the picture cuts inside a render, each through the source
            if b.get('shot_cuts') and b.get('ripple') != 'orphaned' and not is_caps(b):
                b['shot_cuts'] = remap_times(rip, b['shot_cuts'], f'beat {b.get("id", "?")}', notes)
            if b.get('push_at') is not None and b.get('ripple') != 'orphaned':
                # the emphasis push-in's own word (the lane bakes the zoom AT it): left behind, the re-bake lands on the old clock
                n, why = rip.map(float(b['push_at']), 'start')
                if why in ('cut', 'past-the-end'):
                    notes.append(f'  ORPHANED  beat {b.get("id", "?")} push_at {float(b["push_at"]):.3f}s: its word was cut — re-pick it or drop the push-in')
                    orphans.append(f'beat {b.get("id", "?")} (push_at)')
                else:
                    b['push_at'] = round(n, 6)
        if plan.get('layout'):
            before = len(plan['layout'])
            plan['layout'], lnotes = remap_layout(rip, plan['layout'], old_dur, new_dur, fps, 'layout', orphans, moved)
            notes += [f'  layout: {before} span(s) -> {len(plan["layout"])}'] + lnotes
        for d_ in plan.get('layout_deviations') or []:        # a waiver is matched to its finding within 0.5 s of `at`
            if d_.get('at') is None:
                continue
            n, why = rip.map(float(d_['at']), 'start')
            if why in ('cut', 'past-the-end'):
                notes.append(f'  ORPHANED  layout_deviations {d_.get("rule")} at {float(d_["at"]):.3f}s: its material was cut '
                             '— re-pin it or drop it')
                orphans.append(f'layout_deviations {d_.get("rule")} (at)')
                continue
            d_['at'] = round(n, 6)
        for name, v in (plan.get('variants') or {}).items():
            if not isinstance(v, dict) or v.get('from') is None:
                continue
            nf, why = rip.map(float(v['from']), 'start')
            if why in ('cut', 'past-the-end'):
                notes.append(f'  ORPHANED  variant {name}: its from {float(v["from"]):.3f}s was cut away — re-anchor it by hand')
                orphans.append(f'variant {name} (from)')
                continue
            # the variant's tail is its OWN EDL's material, which an organic re-cut does not touch: it moves rigidly
            d = nf - float(v['from'])
            v['from'] = round(nf, 6)
            v['layout'] = [_set(r, a + d, b + d) for a, b, m, r in layout_rows(v.get('layout'))]
            if v.get('duration') is not None:                 # layout.py compose_variant's end: it moves with the rest
                v['duration'] = round(float(v['duration']) + d, 6)
            for c in v.get('cells') or v.get('beats') or []:
                for k in ('start', 'end'):
                    if c.get(k) is not None: c[k] = round(float(c[k]) + d, 6)
                if c.get('shot_cuts'): c['shot_cuts'] = [round(float(t) + d, 6) for t in c['shot_cuts']]
            for d_ in v.get('layout_deviations') or []:
                if d_.get('at') is not None: d_['at'] = round(float(d_['at']) + d, 6)
            if abs(d) > 0.5 / fps:
                notes.append(f'  variant {name}: from, layout, cells, duration and waivers moved {d:+.3f}s with its from')
        for b in beats:                                       # a section job's own timeline anchors ride along
            if isinstance(b.get('_timeline'), list) and len(b['_timeline']) == 2:
                s, why = rip.map(float(b['_timeline'][0]), 'start')
                if not why:
                    b['_timeline'] = [round(s, 6), round(s + float(b['_timeline'][1]) - float(b['_timeline'][0]), 6)]
                else:   # never leave a second timing record behind: `start` moved and this one could not
                    notes.append(f'  ORPHANED  beat {b.get("id", "?")}: its _timeline anchor {b["_timeline"][0]:.3f}s '
                                 f'{"is past the new end" if why == "past-the-end" else "was cut away"} while its start moved — re-anchor it')
                    orphans.append(f'beat {b.get("id", "?")} (_timeline)')
        plan['duration'] = round(new_dur, 6)
        plan['cut_rev'] = new_rev                             # the plan now names the EDL it is valid against
        if off0 is not None and off1 != off0:
            plan['timeline_offset'] = round(off1, 6)
        report('graphics plan', out, fps, notes)
        save(plan_path, plan, a.tag, a.apply)
        baked = [b.get('id', '?') for b in beats if b.get('push_in')]
        if baked:
            print(f'  RE-BAKE  {len(baked)} emphasis push-in(s) sit on V1 under {", ".join(baked)}: their anchors moved, '
                  f'the baked keyframes did not')
        print(f'  RE-BAKE  the opening zoom-out rides the first clip, and the grade layer now ends at {new_dur:.3f}s')

    # 3. placement, 4. SFX cues, 5. the text-animation metas
    place_path = job / 'hf-graphics' / 'placement.json'
    sfx_path = job / 'hf-graphics' / 'sfx-plan.json'
    sfx_rows = json.load(open(sfx_path, encoding='utf-8')) if sfx_path.exists() else []
    cue_name = lambda r: r.get('id', r.get('gid', '?'))
    rigid = {}                                                # placed graphic -> its start shift, when its render did not take the cut
    if place_path.exists():
        doc = json.load(open(place_path, encoding='utf-8'))
        rows = doc['rows'] if isinstance(doc, dict) and 'rows' in doc else doc   # both shapes, as review-frames.py reads it
        out, riders = [], {}
        for r in sfx_rows:
            if r.get('at') is not None and r.get('ripple') != 'orphaned':
                riders.setdefault(r.get('gid'), []).append(cue_name(r))
        notes = rewrite(rip, [(r, r.get('id', '?')) for r in rows], ('start', 'end'), fps, 'placed', out, orphans,
                        rigid, riders, free_end=bool(a.retake))
        report('placement', out, fps, notes)
        save(place_path, doc, a.tag, a.apply)

    if sfx_path.exists():
        rows = sfx_rows
        out = []
        if off0 is not None:                                  # sequence times onto the section's own clock, mapped, and back
            for r in rows:
                if r.get('at') is not None: r['at'] = float(r['at']) - off0
        # A cue on a TRIMMED or STRADDLING graphic sits on a frame of its render, which moved by its start only: mapped
        # through the source, the pop 1.2 s into g1 played 24 frames before it after a 1 s hole inside g1 (2026-10-13).
        held = [r for r in rows if r.get('gid') in rigid and r.get('at') is not None and r.get('ripple') != 'orphaned']
        notes = rewrite(rip, [(r, cue_name(r)) for r in rows if not any(r is h for h in held)], ('at',), fps, 'cue',
                        out, orphans)
        for r in held:
            d, at = rigid[r['gid']], float(r['at'])
            r['at'] = round(at + d, 6)
            if abs(d) > 0.5 / fps:
                out.append((cue_name(r), at, r['at'], d))
            notes.append(f'  WITH      cue {cue_name(r)}: moved {d:+.3f}s with placed {r["gid"]}, whose render spans the cut')
        if off0 is not None:
            for r in rows:                                    # a cue left on a dead anchor keeps its OLD sequence time
                if r.get('at') is not None: r['at'] = round(float(r['at']) + (off0 if r.get('ripple') == 'orphaned' else off1), 6)
            if off1 != off0:
                notes.append(f'  every cue also moved {off1 - off0:+.3f}s with the section\'s timeline_offset')
                # the plan's placement record holds the cues' `at` too: moved with them, so a graphic re-timed together
                # with its cues still reads as not stale (sfx-plan.py stale_gids)
                mp = sfx_path.with_name('sfx-plan.meta.json')
                if mp.exists():
                    meta = json.load(open(mp, encoding='utf-8'))
                    for g in meta.get('placement', []):
                        if 'cues' in g: g['cues'] = [round(float(x) + off1 - off0, 6) for x in g['cues']]
                    save(mp, meta, a.tag, a.apply)
        report('sfx cues', out, fps, notes)
        save(sfx_path, rows, a.tag, a.apply)

    # The text-animation folder is the one whose metas the lane's placer reads back for timing, so it is the
    # set that has to move. A timed meta under any OTHER comp folder is named rather than touched: re-timing a
    # file nothing reads is noise, and leaving one unnamed is how a second timing record drifts in silence.
    metas = sorted((job / 'hf-graphics' / 'text-animation' / 'compositions').glob('*.meta.json'))
    out, notes = [], []
    for m in metas:
        doc = json.load(open(m, encoding='utf-8'))
        notes += rewrite(rip, [(doc, m.stem.split('.')[0])], ('place', 'until'), fps, 'meta', out, orphans,
                         free_end=bool(a.retake))
        save(m, doc, a.tag, a.apply, indent=2)
    if metas:
        report('text-animation metas', out, fps, notes)
    # text.json's explicit "until" (an exit pinned to a cut) is the BUILDER's input: every re-render re-reads it, so one
    # this run did not move re-lays the old exit (g19 on your-job ran 18 frames into the next
    # section after a re-render, 2026-10-06). Mapped as an END anchor; a pin the re-cut removed is named, never moved.
    tj = job / 'hf-graphics' / 'text-animation' / 'text.json'
    if tj.exists():
        specs, pins = json.load(open(tj, encoding='utf-8')), []
        for pid, sp in specs.items():
            old = sp.get('until') if isinstance(sp, dict) else None
            if not isinstance(old, (int, float)) or isinstance(old, bool):
                continue
            new, why = rip.map(float(old), 'end')
            if new is None:
                print(f'  ⚠ text.json {pid}: until {old:.3f}s {"is past the new end" if why == "past-the-end" else "was cut away"}: set it by hand')
                continue
            if abs(new - old) > 1e-4:
                pins.append((pid, old, new)); sp['until'] = round(new, 5)
        if pins:
            print(f'text.json until: {len(pins)} pin(s) move')
            for pid, old, new in pins:
                print(f'    {pid:<10} {old:9.3f} -> {new:9.3f}  ({new - old:+.3f}s)')
            save(tj, specs, a.tag, a.apply, indent=2)
    others = sorted(p for p in (job / 'hf-graphics').glob('*/compositions/*.meta.json')
                    if p.parent.parent.name != 'text-animation'
                    and {'place', 'until'} & set(json.load(open(p, encoding='utf-8'))))
    if others:
        print(f'⚠ {len(others)} timed meta(s) outside text-animation/ were NOT re-timed '
              f'({", ".join(sorted({p.parent.parent.name for p in others}))}): check them by hand')

    face = job / 'face-frame.json'
    try:
        crowns = json.loads(face.read_text(encoding='utf-8')).get('crowns') if face.exists() else None
    except ValueError:
        crowns = None
    if crowns:
        print(f'⚠ face-frame.json holds {len(crowns)} crown(s) read through the OLD cut: their timeline spans now hold other '
              'material. layout.py ignores a crown stamped with another EDL; re-read each card\'s crown '
              '(uv run workflows/face-frame.py projects/<job> --crown A B) before the card clearance is trusted.')
    if moved:
        print(f'\n⚠ {len(moved)} layout edge(s) moved onto surviving material (the sentence at the switch was cut, the '
              'switch itself survives): check each switch on the new cut')
        for name in moved:
            print(f'    {name}')

    if orphans:
        # THE STAMP DOES NOT COVER THESE ROWS. cut_rev says "timed against this EDL", and place-graphics.py
        # believes it — so a row left on a dead anchor is placed at its PRE-RECUT time with a green stamp on
        # the plan, which is the exact bug this tool exists to prevent. Nothing downstream reads `ripple`,
        # so the run ends non-zero instead of on a note in the middle of a long report.
        print(f'\n✗ {len(orphans)} row(s) are still on a DEAD ANCHOR and were left at their old times:')
        for name in orphans[:20]:
            print(f'    {name}')
        if len(orphans) > 20:
            print(f'    … {len(orphans) - 20} more')
        print('  Nothing downstream reads the `ripple` marker: re-anchor each row (or delete it) BEFORE the '
              'lane\'s placers run, or they go down at their pre-recut times under a current cut_rev.')
    flush()
    print('\nNEXT, on the lane: re-lay V1/A1 from the new EDL, re-apply the audio polish, move the grade clip to the '
          f'new end, re-place from these files, re-bake the moves above, then prove the cut.'
          + ('' if a.apply else '\nNothing was written: re-run with --apply once the numbers above read right.'))
    return 1 if orphans else 0


if __name__ == '__main__':
    sys.exit(main())
