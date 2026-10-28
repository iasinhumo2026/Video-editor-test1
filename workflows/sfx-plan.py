#!/usr/bin/env python3
"""sfx-plan.py: turn a job's PLACED graphics into an SFX plan (pipeline step 6, universal).

  uv run workflows/sfx-plan.py projects/<job>              # write hf-graphics/sfx-plan.{json,md}
  uv run workflows/sfx-plan.py projects/<job> --dry        # print the cut sheet, write nothing
  uv run workflows/sfx-plan.py projects/<job> --candidate  # park it as sfx-plan.candidate.{json,md} to merge by hand
  uv run workflows/sfx-plan.py projects/<job> --merge g7,g9  # re-plan ONLY those graphics into the approved sfx-plan.json
                                                             # (ids by commas and/or spaces; backed up first; --dry prints it)
  uv run workflows/sfx-plan.py projects/<job> --record [--plan hf-graphics/sfx-plan.ad.json]
                                                             # record the CURRENT placement for a plan whose cues sit on
                                                             # their graphics (--verify green); the rows are not touched
  uv run workflows/sfx-plan.py projects/<job> --restack    # re-level the approved sfx-plan.json against what plays under
                                                             # it NOW (the music bed planned after it): levels only,
                                                             # backed up first; --dry prints it

Reads: hf-graphics/placement.json (the placed rows), each row's comp HTML (the registry calls it
makes and, for a text animation, its per-word spans), graphics-plan.json (the preset, the cell kinds, and on a
layout-rotation preset its top-level `layout` map) and the sound map of the plan's `preset`: its folder's own
sfx.json when it ships one (presets/instagram/talking-head-explainer does), else the house map in
presets/youtube/default (event -> sound -> slice -> class -> target peak). Writes one row per sound:

  {"id", "gid", "event", "at", "file", "src_in", "src_out", "level_db", "track", "cls", "note"}
  (+ "fade_out_s" when the event's map entry carries one: the lane lays that tail fade)

THE LAYOUT MAP (a plan with a top-level `layout`, the Talking Head Explainer's layout.md § 12): a `cut-in` at
every switch INTO split or full-screen (S or F) from wide, tight or a card over wide (W, T, O), and at every S <-> F
switch, on the switch frame (the map's lead applies). Never at an S -> S hand-off between sibling graphics (the
incoming element makes its own sound) and never into O. The kind-`full` cut-in below then skips a row that starts
under an F span: the map already sounded that cut. A switch with no placed graphic within a second of it is filed
under the gid `layout`: `{"gid": "layout", "drop": ["cut-in"]}` in sfx-hand.json silences those.

THE SECOND VOICE (transcript/voices.json, RAW clock per clip, mapped through transcript/cuts.json), ONLY on a preset
whose sfx.json sets `"second_voice": {"silence": true}` (the Talking Head Explainer's, its sfx.md law 3): every
automatic row inside one of its spans is dropped and listed in the cut sheet, except an overlay call card's own beats
(ring, tap, riseIn, calling): nothing plays over proof audio. Hand rows stay. A map without the key (the house one,
presets/youtube/default) keeps its automatic rows under a second voice and never reads voices.json.

sfx-hand.json rows tagged `"src": "kit"` were written by a preset kit from a component's own motion: they are the
automatic first pass (the density cap and the layer rules apply, a re-plan may replace them), never the creator's
call. Every other hand row stays a hand row and outranks them. So a hand row's `"drop": ["<event>"]` silences the kit's
rows of that event on its graphic exactly as it silences the parser's, while a hand row of that event stays: a kit
recipe that sounds what the preset's law does not want is answered by a drop, never by editing the recipe in the job
(2026-10-14: a brand page's kit `camera-under` outranked {"gid": "g4", "drop": ["camera-under"]}). A kit row
{"gid", "silent": true, "src": "kit"} is a recipe saying it makes no sound by design (engine.write_events `silent`).

Beside the plan it writes `sfx-plan.meta.json`, the placement record: which placement.json the rows were
derived from (its sha1, every graphic's id/start/end and the `at` of that graphic's cues), so the lane placer can
say a plan is stale when a graphic moved after it was planned. A graphic that moved TOGETHER with its cues (a
re-cut: workflows/ripple-cut.py re-times placement.json and sfx-plan.json by the same amount) is not stale.
--record writes that record for a plan it did not write (an older job's, an AD cut's), and changes no row.

--merge re-plans the named graphics against the CURRENT placement and swaps only their rows into the approved
plan: every other row stays byte-identical with its id, a merged row reuses its graphic's old ids in time
order, a repeat of an approved cue's sound stays on that cue's layer (the one-layer rule below), and any other
merged row that would overlap an approved cue on its track moves to the first free SFX layer. Every cross-graphic
decision (the repeat's cut, the doubling, three sounds a second) reads the APPROVED rows, never a fresh row of
another graphic that the merge does not keep. A graphic that has left placement.json can be merged too: its
planned rows go. --record keeps the copy window a lane recorded (place-sfx.py --adopt --until); a whole plan
written fresh has none.

THE MUSIC BED (hf-graphics/music-plan.json, written by the lane's music pass: place-music.py, music-onset.py
--write-plan) is part of what the cues stack on: when it exists, the stacking check below decodes its track from
`source_in` at `bed_db` under every cluster. The bed is planned AFTER the SFX (its pass follows step 6), so --restack
runs that check alone over the approved plan: every row keeps its id, time, track and slice, only a level over the
ceiling comes down (the same rule: deepest layer first, whole dB, at most 12 dB a cue, a hand row keeps its level),
and the lane re-lays the rows it names.

THE SLICES (reslice()): an event with several slices plays them in TIME order over the rows that survived the density
rules, the next slice after the one its event last played (a --merge continues from the approved rows), never the
same hit twice running; and an event whose slices are all impulsive (a pop, a snip, a tap, a click) has each slice's
lead-in trimmed so every hit attacks as far from its cue's start as the tightest slice does (aligned_slices()): the
map gives one lead per event, the slices of one file carry 12 to 136 ms of differing pre-roll, so hits of one event
landed up to 4 frames apart against their picture. The cut sheet's head names the events it aligned.

pack_files() is the SFX pack every lane's "load the whole pack into the bin" command loads (LANES.md § step 6).

`at` is the timeline time in seconds, frame-snapped. `track` is the 0-based audio track index
from the preset map (A2 primary, A3/A4 layers). `level_db` is the clip Volume Level that puts the
measured slice peak on the class target. Nothing here touches an editor; placement is per lane
(LANES.md step 6). The WHY and the numbers: the preset's sfx.md (the house one: presets/youtube/default/sfx.md).

Comp calls are found by a static parse of the comp's script. The `at` argument is evaluated with
the comp's own constants: F, SF, DUR, any `const NAME = <number>`, any name built out of earlier
names (`const RACK = SUPER - 12 * F`) and any numeric array it indexes (`const T = [0.06, null]`).
A call inside a loop over an array literal is expanded over that array, and a call whose time
indexes a bound array is expanded over that array's length (its selector parameter resolving back
through the loops it sits in, so the element is what the sound rules read); anything else is listed
under ⚠ in the cut sheet for a hand entry, never guessed — and a ⚠ a hand entry already answers
stops printing. A graphic that deliberately makes no sound (raw motion no registry call names, a capture)
answers its "needs a hand entry" ⚠ with `{"gid": "<id>", "silent": true}` in sfx-hand.json.
"""
import hashlib, html as htmlmod, itertools, json, math, os, re, shutil, struct, subprocess, sys, time
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALLS = ('pop', 'slam', 'riseIn', 'riseOut', 'exit', 'slideIn', 'slideOut', 'drawOn', 'countUp', 'reveal', 'flash')
_peak_cache = {}


def slice_peak(path, a, b):
    key = (path, round(a, 3), round(b, 3))
    if key in _peak_cache: return _peak_cache[key]
    # atrim BEFORE volumedetect measures the slice alone, sample-exact. An output-side -ss/-t still ran every frame
    # from 0 through the filter, so the peak was the max over 0..b: a quiet slice after a loud hit read as the hit,
    # its class-band level came out ~10 dB low and a silent one slipped past the < -40 guard (2026-09-23)
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-vn', '-sn', '-dn',
                        '-af', f'atrim=start={a}:end={a + max(b - a, 0.05)},volumedetect', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    m = re.search(r'max_volume: (-?[0-9.]+)', r)
    v = float(m.group(1)) if m else 0.0
    _peak_cache[key] = v
    return v


_attack_cache = {}


def slice_attack(path, a, b):
    """(onset, impulsive) of the slice [a, b] of `path`: `onset` is the seconds from `a` to the first sample at 10 %
    (-20 dB) of the slice's own peak, `impulsive` that it reaches half that peak (-6 dB) within 10 ms more (a pop, a
    snip, a tap, a click; a whoosh or a scribble swells, and its attack is no single instant). None when it did not
    decode. The first 1.5 s are read: a one-shot's attack sits well inside them."""
    key = (path, round(a, 4), round(b, 4))
    if key not in _attack_cache:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vn', '-sn', '-dn', '-af',
                            f'atrim=start={a}:end={min(b, a + 1.5)},asetpts=PTS-STARTPTS', '-ac', '2', '-ar', '48000',
                            '-f', 's16le', '-'], capture_output=True)
        n = len(r.stdout) // 2
        x = struct.unpack(f'<{n}h', r.stdout[:2 * n]) if n else ()
        pk = max((abs(v) for v in x), default=0)
        if r.returncode or not pk:
            _attack_cache[key] = None
        else:
            i10 = next(i for i, v in enumerate(x) if abs(v) >= pk * 0.1) // 2
            i50 = next(i for i, v in enumerate(x) if abs(v) >= pk * 0.5) // 2
            _attack_cache[key] = (i10 / 48000, (i50 - i10) / 48000 <= 0.010)
    return _attack_cache[key]


def aligned_slices(spec, path):
    """The event's slices as laid: [(in, out)], each IMPULSIVE slice's lead-in trimmed so its attack sits as far from
    the cue's start as the tightest slice's does. The map gives ONE lead per event, and its slices of one file carry
    different pre-roll: the house pop's five run 12 to 92 ms from in-point to attack, the Talking Head Explainer's
    seven taps 41 to 136 ms, so a rotation put the same event's hits 0.4 to 4 frames after their picture, hit to hit
    (THE sfx.md law 5: the attack lands 0 to 2 frames after its event). Trimming only moves an attack EARLIER, toward
    its event, and never ahead of the cue's own start; a single-slice event, a whole file, a `fit` bed and any event
    with a swelling slice are left as the map wrote them, and so is a slice already within 2 ms of the tightest."""
    sl = [tuple(s) for s in spec.get('slices') or []]
    if spec.get('whole_file') or spec.get('fit') or len(sl) < 2:
        return sl
    att = [slice_attack(path, a, b) for a, b in sl]
    if any(x is None or not x[1] for x in att):
        return sl
    lo = min(x[0] for x in att)
    return [(round(a + x[0] - lo, 4), b) if x[0] - lo > 0.002 else (a, b) for (a, b), x in zip(sl, att)]


def reslice(rows, ctx, EV, lib, T):
    """ONE SLICE AFTER ANOTHER, in TIME order, over the rows that survived the density rules (sfx.md § The law 3: "a
    run rotates through them so no two adjacent hits play the identical sample"). add() counts its rotation in the
    order rows are ADDED (graphic by graphic, a comp's calls in parse order), before the density rules drop any, and a
    --merge restarted it at the first slice: your-job shipped two scissors 0.67 s apart on the same 1.21
    slice (s009, s010) and a merged graphic's words restarting at 0.63 beside approved ones. Here each row of an event
    with several slices takes the slice after the one its event last played (an approved row of a --merge, `ctx`,
    included, by its slice), and with three or more avoids the one the next approved hit plays; the slice is the
    attack-aligned one (aligned_slices) and its peak and class-band level are re-read. A hand level is kept.
    -> the events whose slices were attack-aligned."""
    seqs, aligned = {}, []
    for x in sorted(list(rows) + list(ctx), key=lambda p: p['at']):
        seqs.setdefault(x.get('event'), []).append(x)
    for ev, seq in seqs.items():
        spec = EV.get(ev)
        if not isinstance(spec, dict) or spec.get('whole_file') or len(spec.get('slices') or []) < 2:
            continue
        path = str(lib / spec['file'])
        raw = [tuple(s) for s in spec['slices']]
        eff = aligned_slices(spec, path)
        if eff != raw:
            aligned.append(ev)

        def which(p):
            """The slice an approved row plays (its in-point between the map's and the aligned one, its out the map's)."""
            for k, ((a, b), (a2, _)) in enumerate(zip(raw, eff)):
                if a - 2e-3 <= float(p['src_in']) <= a2 + 2e-3 and (abs(float(p['src_out']) - b) <= 2e-3 or spec.get('fit')):
                    return k
            return None
        prev = None
        for i, x in enumerate(seq):
            if x.get('fixed'):
                prev = which(x)
                continue
            k = 0 if prev is None else (prev + 1) % len(raw)
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            if len(raw) >= 3 and nxt is not None and nxt.get('fixed') and which(nxt) == k:
                k = (k + 1) % len(raw)
            # two slices of one map can be ONE hit cut with more or less lead-in (the house pop's 0-0.29 and 0.08-0.33
            # both hold the hit at 0.092 s, the Talking Head Explainer's pop-hero is only that hit twice): an aligned
            # pair starts on the same sample, and the next slice plays instead whenever there is another hit to play
            for _ in range(len(raw)):
                if prev is None or abs(eff[k][0] - eff[prev][0]) > 2e-3:
                    break
                k = (k + 1) % len(raw)
            a, b = eff[k]
            if spec.get('fit') == 'duration' and x.get('_dur'):
                b = min(b, a + max(x['_dur'], 0.2))
            peak = slice_peak(path, a, b)
            if peak < -40:
                prev = which(x)                                     # never swap a row onto a silent slice
                continue
            x.update(src_in=round(a, 4), src_out=round(b, 4), peak=peak)
            if x.get('_lv') is None:
                x['level_db'] = spec['level_db'] if 'level_db' in spec else min(6, round(T[spec['class']] - peak))
            prev = k
    return aligned


_dur_cache = {}


def file_dur(path):
    if path not in _dur_cache:
        _dur_cache[path] = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                                                capture_output=True, text=True).stdout.strip() or 0)
    return _dur_cache[path]


_ch_cache = {}


def channels(path):
    """The file's audio channel count (2 when ffprobe cannot say)."""
    if path not in _ch_cache:
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=channels',
                            '-of', 'csv=p=0', str(path)], capture_output=True, text=True).stdout.split()
        _ch_cache[path] = int(r[0].strip(',')) if r and r[0].strip(',').isdigit() else 2
    return _ch_cache[path]


def probe_fps(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate',
                        '-of', 'csv=p=0', path], capture_output=True, text=True).stdout
    n, _, d = r.strip().split('\n')[0].strip(',').partition('/')
    return float(n) / float(d or 1)


PACK_AUDIO = ('.wav', '.mp3', '.aif', '.aiff', '.m4a', '.flac')
PACK_BIN = 'sfx'         # the bin every lane loads the pack into, the same one the placers import a cue's file into


def pack_files(lib=None):
    """THE SFX PACK as every lane's "load the whole pack into the bin" command loads it (Office Hours, 2026-10-13: "throw
    in all of the sound effects into the media bin so that I can custom place some myself"): [(folder, path)] for every
    audio file under `lib` (default assets/sfx), `folder` its sub-folder relative to the pack ('' at the top level,
    '/'-joined), which a lane mirrors as a sub-bin of PACK_BIN. README.md, the slice index and every other non-audio or
    hidden file stay out. Sorted, so every lane loads the same list in the same order."""
    lib = Path(lib or ROOT / 'assets' / 'sfx')
    out = []
    for p in lib.rglob('*'):
        rel = p.relative_to(lib)
        if p.is_file() and p.suffix.lower() in PACK_AUDIO and not any(x.startswith('.') for x in rel.parts):
            out.append(('' if len(rel.parts) == 1 else rel.parent.as_posix(), str(p)))
    return sorted(out, key=lambda x: (x[0].lower(), os.path.basename(x[1]).lower()))


class Evaluator:
    """Evaluate a comp's time expressions with its own constants. Refuses anything it cannot bind."""
    SAFE = re.compile(r'^[\w\s+\-*/().\[\]]+$')                # names, numbers, arithmetic, an index, Math.round(...)
    ARRAY = re.compile(r'(?:const|let|var)\s+(\w+)\s*=\s*\[([^\[\]]*)\]\s*(?=[;,\n])')
    SCALAR = re.compile(r'(?:(?:const|let|var)\s+|,\s*)(\w+)\s*=\s*([^;,\n]+?)\s*(?=[;,\n])')

    def __init__(self, script, fps):
        self.names = {'F': 1 / fps, 'Math': type('M', (), {'round': staticmethod(lambda x: math.floor(x + 0.5)), 'floor': staticmethod(math.floor), 'ceil': staticmethod(math.ceil), 'min': staticmethod(min), 'max': staticmethod(max)})}
        decl = re.sub(r'for\s*\([^)]*\)', ' ', script)          # a `for (let i = 0; ...)` counter is NOT a constant
        # a comp writes its times as NUMERIC ARRAYS it indexes (`const T = [0.06, null, 0.34]`): bind those as
        # tuples FIRST, because only an array can be indexed and a name means the array wherever it is. A `null`
        # slot stays None: indexing it raises, which is the comp's own `if (T[i] !== null)` guard. The scalar
        # passes below leave a bound array alone, or a comma-continued measurement helper (`let L = 0, R = FRAME.x,
        # T = 0, B = FRAME.y;`) would bind T to a number and the loop that reads T[i] would size from a scalar.
        for m in self.ARRAY.finditer(decl):
            toks = [t.strip() for t in m.group(2).split(',') if t.strip()]
            if toks and all(re.fullmatch(r'-?[\d.]+|null', t) for t in toks):
                self.names.setdefault(m.group(1), tuple(None if t == 'null' else float(t) for t in toks))
        for m in re.finditer(r'(?:(?:const|let|var)\s+|,\s*)(\w+)\s*=\s*([-\d.]+(?:\s*[/*+\-]\s*[-\d.]+)*)\s*(?=[;,\n])', decl):
            if isinstance(self.names.get(m.group(1)), tuple): continue
            try: self.names[m.group(1)] = eval(m.group(2), {'__builtins__': {}}, {})     # `const F = .., DUR = .., AUTO_T = ..;` binds all three
            except Exception: pass
        m = re.search(r'init\(\{([^}]*)\}', script)               # HF.init({fps, stepFps, dur})
        if m:
            for k, v in re.findall(r'(\w+)\s*:\s*([\w.\d/*+\- ]+)', m.group(1)):
                try: self.names[k] = eval(v, {'__builtins__': {}}, dict(self.names))
                except Exception: pass
            if 'dur' in self.names: self.names.setdefault('DUR', self.names['dur'])
            if self.names.get('stepFps'): self.names['SF'] = 1 / self.names['stepFps']
        self.names.setdefault('SF', self.names['F'])
        # names built out of earlier names (`const OVER = 4.641 - F`, `const RACK = SUPER - 12 * F`): loop the
        # scalars to a fixed point so an alias or a chain resolves too.
        pend = [(m.group(1), m.group(2)) for m in self.SCALAR.finditer(decl)]
        for _ in range(8):
            bound = False
            for name, rhs in pend:
                if name in self.names or not self.SAFE.match(rhs): continue
                try: self.names[name] = eval(rhs, {'__builtins__': {}}, dict(self.names))
                except Exception: continue
                bound = True
            if not bound: break

    def ev(self, expr, extra=None):
        if not self.SAFE.match(expr): raise ValueError(expr)
        return float(eval(expr, {'__builtins__': {}}, dict(self.names, **(extra or {}))))


def split_args(s):
    out, depth, cur, q = [], 0, '', None
    for ch in s:
        if q:
            cur += ch
            if ch == q: q = None
            continue
        if ch in '\'"': q = ch; cur += ch; continue
        if ch in '([{': depth += 1
        if ch in ')]}': depth -= 1
        if ch == ',' and depth == 0: out.append(cur.strip()); cur = ''; continue
        cur += ch
    if cur.strip(): out.append(cur.strip())
    return out


LOOP = re.compile(r'\[\s*(\[[^\[\]]*\](?:\s*,\s*\[[^\[\]]*\])*)\s*\]\s*\.forEach\(\s*\(\s*\[([^\]]*)\]\s*\)\s*=>\s*')


def literal(tok):
    tok = tok.strip()
    if tok[:1] in '\'"': return tok[1:-1]
    try: return float(tok)
    except ValueError: return tok


FOREACH_PARAM = r'(\[[^\[\]]*\]|[\w.]+)\s*\.forEach\(\s*\(\s*%s\s*,\s*(\w+)\s*\)'


def sel_expr(script, upto, name, depth=4):
    """The indexed expression a `.forEach` binds a loop's SELECTOR parameter from, so the type, completion and
    data-sfx rules downstream see the ELEMENT rather than the parameter's name. `['.a','.b'].forEach((sel, i) =>`
    gives `['.a','.b'][i]`, and a NESTED loop resolves through its outer parameter
    (`ROWS.forEach((row, r) => row.forEach((sel, c) => ...))`) gives `ROWS[r][c]`."""
    expr = name
    for _ in range(depth):
        head = re.fullmatch(r'(\w+)((?:\[\w+\])*)', expr)
        if not head: break
        fe = None
        for x in re.finditer(FOREACH_PARAM % re.escape(head.group(1)), script[:upto]): fe = x   # the nearest above the call
        if not fe: break
        expr = f'{fe.group(1)}[{fe.group(2)}]{head.group(2)}'
    return expr


def sel_arrays(script):
    """name -> the (possibly nested) list of SELECTOR strings a const holds: `const ROWS = [['.r0c0', ...], ...]`."""
    out = {}
    for m in re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*(\[[^;]*?\])\s*;', script, re.S):
        try: v = json.loads(re.sub(r',(\s*[\]}])', r'\1', m.group(2).replace("'", '"')))
        except Exception: continue
        leaf = v
        while isinstance(leaf, list) and leaf: leaf = leaf[0]
        if isinstance(leaf, str): out[m.group(1)] = v
    return out


def sel_lookup(expr, arrays, idx):
    """`ROWS[r][c]` with {'r': 0, 'c': 2} -> '.r0c2'; None when it does not resolve to a selector string."""
    m = re.fullmatch(r'(\w+|\[[^\[\]]*\])((?:\[\w+\])+)', expr or '')
    if not m: return None
    v = [literal(x) for x in split_args(m.group(1)[1:-1])] if m.group(1).startswith('[') else arrays.get(m.group(1))
    for k in re.findall(r'\[(\w+)\]', m.group(2)):
        if not isinstance(v, list) or idx.get(k) is None or idx[k] >= len(v): return None
        v = v[idx[k]]
    return v if isinstance(v, str) else None


def type_targets(html):
    """Selectors (#id / .class) of every element whose OWN text is words: that is TYPE. Type never pops
    (2026-09-10): it rises with the scissors or slams with the Impact, whatever the comp calls.
    A node/card/row/chip whose words sit in a child element is a surface, not type."""
    from html.parser import HTMLParser as _HP
    class P(_HP):
        def __init__(self):
            super().__init__(convert_charrefs=True); self.stack, self.els = [], []
        def handle_starttag(self, tag, attrs):
            a = dict(attrs); el = dict(id=a.get('id'), cls=(a.get('class') or '').split(), text='')
            self.els.append(el)
            if tag not in ('br', 'img', 'input', 'meta', 'link', 'path', 'circle', 'rect', 'polygon', 'line', 'use'): self.stack.append((tag, el))
        def handle_startendtag(self, tag, attrs): pass
        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag: del self.stack[i:]; return
        def handle_data(self, data):
            if self.stack: self.stack[-1][1]['text'] += data
    p = P(); p.feed(re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.S))
    out = set()
    for el in p.els:
        if not any(c.isalpha() for c in el['text']): continue      # one letter is a word too ("i")
        if el['id']: out.add('#' + el['id'])
        for c in el['cls']: out.add('.' + c)
    return out


COMPLETION_CLASSES = {'hi', 'done', 'ok', 'check', 'chk', 'success', 'complete', 'completed', 'finished', 'payoff', 'win', 'green'}
COMPLETION_TEXT = re.compile(r'\b(100 ?%|done|complete|completed|finished|postable|success)\b', re.I)
GREEN = ('#2ff58a', '--green', '#22c55e', '#16a34a', '#28c840', '#0ca30c', '#2ecc71', 'rgba(47,245,138')


def completion_targets(html):
    """Selectors (#id / .class) of every element that SHOWS COMPLETION: a finished node, a check, 100 %, the green
    state. Sound follows meaning before mechanism (2026-09-10: "in special scenarios like this where it's green
    or showing completion or goodness, it's nice to represent that with sound"): such an element rings the bell
    (`payoff`) when it arrives instead of popping. Read off the markup: a completion class, completion words in its own
    text, a green fill/stroke on it or inside it, a green CSS rule whose compound selector it satisfies, or an explicit
    data-sfx="payoff"; data-sfx="pop" opts out."""
    from html.parser import HTMLParser as _HP
    css = ''.join(re.findall(r'<style[^>]*>(.*?)</style>', html, re.S))
    green_compounds = []
    for sel, block in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        if any(g in block for g in GREEN):
            for branch in sel.split(','):
                toks = re.findall(r'\.([A-Za-z0-9_-]+)', branch.strip().split(' ')[-1])
                if toks: green_compounds.append(set(toks))
    class P(_HP):
        def __init__(self):
            super().__init__(convert_charrefs=True); self.stack, self.els = [], []
        def handle_starttag(self, tag, attrs):
            a = dict(attrs); cls = set((a.get('class') or '').split())
            el = dict(id=a.get('id'), cls=cls, text='', done=False, opt=a.get('data-sfx'))
            sig = bool(cls & COMPLETION_CLASSES) or any(g in (a.get('fill', '') + a.get('stroke', '') + a.get('style', '')) for g in GREEN) \
                  or any(c <= cls for c in green_compounds) or a.get('data-sfx') == 'payoff'
            if a.get('data-sfx') in ('pop', 'none'): sig = False     # the opt-out is honoured BEFORE propagation: a green
            if sig:                                                  # disc that opted out must not bell its ancestors either
                el['done'] = True
                for _, anc in self.stack: anc['done'] = True          # the green check inside a node marks the node
            self.els.append(el)
            if tag not in ('br', 'img', 'input', 'meta', 'link', 'path', 'circle', 'rect', 'polygon', 'line', 'use'): self.stack.append((tag, el))
        def handle_startendtag(self, tag, attrs): self.handle_starttag(tag, attrs); self.handle_endtag(tag)
        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag: del self.stack[i:]; return
        def handle_data(self, data):
            if self.stack: self.stack[-1][1]['text'] += data
    p = P(); p.feed(re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.S))
    out = set()
    for el in p.els:
        if el['opt'] in ('pop', 'none'): continue
        if el['done'] or COMPLETION_TEXT.search(el['text'] or ''):
            if el['id']: out.add('#' + el['id'])
            for c in el['cls']: out.add('.' + c)
    return out


def sfx_markers(html):
    """selector -> {event, file} from data-sfx attributes in the comp: the judgement call, named where the element is
    authored. The palette is the DOCUMENTED map only (2026-09-10; owner: presets/youtube/default/sfx.md
    § Sound follows MEANING). data-sfx="<event>" swaps the element's mechanical sound for any event documented in
    sfx.json (emphasis, gunshot, processing, click included); data-sfx="none" silences the element; data-sfx-file is
    parsed only so it can be REFUSED with a warning (sfx.md § Sound follows MEANING, sfx.json `_judgement`: only
    sounds the user has heard and documented are ever placed)."""
    from html.parser import HTMLParser as _HP
    found = {}
    class P(_HP):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if not any(k.startswith('data-sfx') for k in a): return
            m = {k: v for k, v in (('event', a.get('data-sfx')), ('file', a.get('data-sfx-file'))) if v}
            keys = (['#' + a['id']] if a.get('id') else []) + ['.' + c for c in (a.get('class') or '').split()]
            for k in keys: found[k] = m
        def handle_startendtag(self, tag, attrs): self.handle_starttag(tag, attrs)
    P().feed(re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.S))
    return found


def comp_events(html, fps):
    """[(event, at_seconds, note)] from a comp's registry calls, plus ⚠ notes it could not bind."""
    script = '\n'.join(re.findall(r'<script[^>]*>(.*?)</script>', html, re.S))
    ev = Evaluator(script, fps)
    selarr = sel_arrays(script)
    events, warns = [], []
    consumed = []                                                  # spans handled by the loop expander
    # `[[a, b, 1.1], ...].forEach(([x, y, at]) => BODY)`: bind the params per tuple, evaluate the body's calls
    for lm in LOOP.finditer(script):
        tuples = [[literal(x) for x in split_args(t[1:-1])] for t in split_args(lm.group(1))]
        params = [x.strip() for x in lm.group(2).split(',')]
        i = lm.end(); depth = 0; j = i
        if script[i] == '{':
            while j < len(script):
                depth += {'{': 1, '}': -1}.get(script[j], 0); j += 1
                if depth == 0: break
            body = script[i:j]
        else:
            while j < len(script) and script[j] not in ';\n': j += 1
            body = script[i:j]
        consumed.append((lm.start(), j))
        for tup in tuples:
            bind = {k: v for k, v in zip(params, tup)}
            for cm in re.finditer(r'\b(' + '|'.join(CALLS) + r')\(([^()]*)\)', body):
                args = split_args(cm.group(2))
                if len(args) < 2: continue
                sel = bind.get(args[0].strip(), args[0])
                try: events.append((cm.group(1), ev.ev(args[1], {k: v for k, v in bind.items() if isinstance(v, float)}), str(sel)))
                except Exception: warns.append(f'{cm.group(1)}({args[0]}, {args[1]}) in a loop could not be evaluated')
    FOR = re.compile(r'for\s*\(\s*(?:const|let|var)\s*\[([^\]]*)\]\s*of\s*(\[[^;]*?\]|\w+)\s*\)\s*')
    for fm in FOR.finditer(script):
        src = fm.group(2)
        if not src.startswith('['):                                  # `of ROWS` -> the const array literal
            cm_ = re.search(r'(?:const|let|var)\s+' + re.escape(src) + r'\s*=\s*(\[[^;]*?\])\s*;', script)
            if not cm_: warns.append(f'for-of over {src}: array not found'); continue
            src = cm_.group(1)
        tuples = [[literal(x) for x in split_args(t[1:-1])] for t in split_args(src[1:-1]) if t.startswith('[')]
        params = [x.strip() for x in fm.group(1).split(',')]
        i = fm.end(); j = i
        if script[i] == '{':
            depth = 0
            while j < len(script):
                depth += {'{': 1, '}': -1}.get(script[j], 0); j += 1
                if depth == 0: break
        else:
            while j < len(script) and script[j] not in ';\n': j += 1
        body = script[i:j]; consumed.append((fm.start(), j))
        for tup in tuples:
            bind = {k: v for k, v in zip(params, tup)}
            for cm in re.finditer(r'\b(' + '|'.join(CALLS) + r')\(([^()]*(?:\([^()]*\)[^()]*)*)\)', body):
                args = split_args(cm.group(2))
                if len(args) < 2: continue
                sel = bind.get(args[0].strip(), args[0])
                try: events.append((cm.group(1), ev.ev(args[1], {k: v for k, v in bind.items() if isinstance(v, float)}), str(sel)))
                except Exception: warns.append(f'{cm.group(1)}({args[0]}, {args[1]}) in a for-of could not be evaluated')
    # hand-rolled motion the registry would have named: a tween that carries an element a frame-width
    # in x is a slide, a stroke-dash reveal is a draw-on (pre-registry comps, and scene moves inside
    # a full-screen that no registry primitive covers)
    for fm_ in re.finditer(r'tl\.set\(([^,]+),\s*\{\s*opacity:\s*o\s*\},\s*(?:(.+?)\s*\+\s*)?f\s*\*\s*F\s*\)', script):
        try: events.append(('flash', ev.ev(fm_.group(2).strip()) if fm_.group(2) else 0.0, fm_.group(1).strip() + ' (hand-rolled strobe)'))
        except Exception:
            if not re.fullmatch(r'\w+', (fm_.group(2) or '').strip()): warns.append(f'flash {fm_.group(1).strip()} at {fm_.group(2).strip()}: could not be evaluated')
    for hm in re.finditer(r'tl\.to\(([^,]+),\s*\{([^}]*)\},\s*([^)]+)\)', script):
        props, at_expr = hm.group(2), hm.group(3).strip()
        xm = re.search(r'\bx:\s*(-?\d+(?:\.\d+)?)', props)
        kind = None
        if xm and abs(float(xm.group(1))) >= 900: kind = 'slideOut' if float(xm.group(1)) < 0 else 'slideIn'
        elif re.search(r'strokeDashoffset:\s*0\b', props): kind = 'drawOn'
        if not kind: continue
        try: events.append((kind, ev.ev(at_expr), hm.group(1).strip() + ' (hand-rolled)'))
        except Exception:
            if not re.fullmatch(r'\w+', at_expr):                    # a bare unknown name is a helper's parameter, not a call
                warns.append(f'{kind} {hm.group(1).strip()} at {at_expr}: could not be evaluated')
    for m in re.finditer(r'\b(' + '|'.join(CALLS) + r')\(', script):
        if any(a <= m.start() < b for a, b in consumed): continue
        name = m.group(1)
        i = m.end(); depth = 1; j = i
        while j < len(script) and depth:
            depth += {'(': 1, ')': -1}.get(script[j], 0); j += 1
        args = split_args(script[i:j - 1])
        if name == 'exit' and (not args or len(args) < 2):
            continue                                              # exit() at the comp end: silent anyway
        if len(args) < 2: continue
        at_expr, sel = args[1], args[0]
        extra = {}
        if 'dur' in [a.strip() for a in args[2:3]]: pass
        try:
            # names the expression uses that nothing binds are the enclosing loop's indices. Each is sized by the
            # array the CALL indexes with it (`ROW_BASE[r]` in the time, `CARD_LEFT[c]` in the travel), falling back
            # for `i` to an array literal `.forEach`ed just above; the call then expands over every combination.
            free = sorted({n for n in re.findall(r'(?<![.\w])[A-Za-z_]\w*', at_expr) if n not in ev.names})
            sizes, call_txt = {}, script[m.start():j]
            for v in free:
                # EVERY array the call indexes with this name is a candidate size, not just the first: a selector
                # list beside a times array (`slideIn(ROWS[r], T[r])`) is no size at all, and stopping there
                # gives up on a loop the call itself measures.
                for am in re.finditer(r'(?<![.\w])(\w+)\s*\[\s*' + re.escape(v) + r'\s*\]', call_txt):
                    if isinstance(ev.names.get(am.group(1)), tuple): sizes[v] = len(ev.names[am.group(1)]); break
                if v in sizes: continue
                if v == 'i':
                    arr = re.findall(r'\[([^\[\]]*)\]\s*\.forEach', script[max(0, m.start() - 400):m.start()])
                    if arr: sizes[v] = len(split_args(arr[-1]))
            if free and all(v in sizes for v in free):
                # the loop's SELECTOR param resolves from the array it runs over — a literal
                # (`['.r1','.r2'].forEach((sel, i) => riseIn(sel, T[i]))`) or, through the outer loop's own
                # parameter, a nested one (a wall's `ROWS[r][c]`) — so the type, completion and data-sfx rules
                # downstream still see the element rather than the parameter's name
                sx = sel if re.fullmatch(r'\w+(?:\[\w+\])+', sel) else (      # already indexed: `slideIn(ROWS[r], T[r])`
                    sel_expr(script, m.start(), sel) if re.fullmatch(r'\w+', sel) and sel not in ev.names else None)
                hit = False
                for combo in itertools.product(*[range(sizes[v]) for v in free]):
                    try: t = ev.ev(at_expr, dict(zip(free, combo)))
                    except Exception: continue                    # a null slot: the comp's own guard skips it too
                    idx = dict(zip(free, combo))
                    tag = ','.join(f'{v}={k}' for v, k in zip(free, combo))
                    events.append((name, t, f"[{tag}] {sel_lookup(sx, selarr, idx) or sel}")); hit = True
                if not hit: warns.append(f'{name}({sel}, {at_expr}) could not be evaluated')
            elif free and (re.search(r'\w\s*\[', at_expr) or 'i' in free):
                warns.append(f'{name}({sel}, {at_expr}) runs in a loop this parser cannot size')
            else:
                t = ev.ev(at_expr)
                dur = None
                if name == 'countUp' and len(args) > 2:
                    try: dur = ev.ev(args[2])
                    except Exception: dur = None
                if name == 'reveal' and len(args) > 2 and args[2][:1] in '\'"`':
                    # reveal(sel, at, text): the registry reveals 2-6 words per beat on a fixed burst
                    # pattern, doubling on punctuation; replay that on the literal text for the duration
                    text = args[2][1:-1]; words_ = text.split(' '); sizes = [3, 5, 2, 4, 6, 3, 2, 5, 4, 3, 6, 2]
                    beat = ev.names['SF'] if ev.names.get('stepFps') else 2 * ev.names['F']
                    i_ = 0; k_ = 0; dur = 0.0
                    while i_ < len(words_):
                        i_ = min(len(words_), i_ + sizes[k_ % len(sizes)]); k_ += 1
                        dur += 2 * beat if re.search(r'[.,;:!?]$', ' '.join(words_[:i_])) else beat
                elif name == 'reveal':
                    warns.append(f'reveal({sel}) has no literal text: give it a hand entry with dur')
                events.append((name, t, sel if dur is None else f'{sel} dur {dur:.2f}'))
                if dur is not None: events[-1] = (name, t, events[-1][2], dur)
        except Exception:
            warns.append(f'{name}({sel}, {at_expr}) could not be evaluated')
    return events, warns


def find_comp(hf, gid, render):
    """Resolve within the placed render's build folder first; never score a retired sibling comp.

    Older slug-named jobs can fall back across folders only when the best match is unique.
    An ambiguous source is an error, not a filesystem-order editorial decision.
    """
    base = Path(render).stem
    local = Path(render).parent.parent / 'compositions'
    scopes = [list(local.glob('*.html'))]
    if not (Path(render).parent.name == 'renders' and local.parent.parent.resolve() == hf.resolve()):
        scopes.append(list(hf.glob('*/compositions/*.html')))
    for comps in scopes:
        named = [c for c in comps if base == c.stem or base.startswith(c.stem + '-')]
        candidates = named or [c for c in comps if c.stem == gid]
        if not candidates:
            candidates = [c for c in comps if c.stem.startswith(gid + '-')]
        if candidates:
            if named:
                longest = max(len(c.stem) for c in candidates)
                candidates = [c for c in candidates if len(c.stem) == longest]
            if len(candidates) != 1:
                raise ValueError(f'{gid}: ambiguous composition for {render}: ' + ', '.join(map(str, candidates)))
            return candidates[0]
    return None


def text_events(html):
    """One event per word span; the word comes from data-w when the builder wrote it, else the span text."""
    out = []
    for m in re.finditer(r'<span class="(w[^"]*)" data-t="([\d.]+)"([^>]*)>([^<]*)', html):
        w = re.search(r'data-w="([^"]*)"', m.group(3))
        out.append(('word', float(m.group(2)), htmlmod.unescape((w.group(1) if w else m.group(4)).strip()), m.group(1)))
    return out


def write_plan(hf, rows, md, candidate=False):
    """Write the cut sheet; --candidate parks it beside an approved plan instead of replacing it."""
    stem = 'sfx-plan.candidate' if candidate else 'sfx-plan'
    prev = hf / 'sfx-plan.json'
    changed = []
    if not candidate and prev.exists():
        key = lambda rs: {g: sorted(((r.get('event'), r.get('at'), r.get('level_db'), r.get('track')) for r in rs if r.get('gid') == g), key=repr)
                          for g in {r.get('gid') for r in rs}}
        old, new = key(json.loads(prev.read_text(encoding="utf-8"))), key(rows)
        changed = sorted(g for g in set(old) | set(new) if old.get(g) != new.get(g))
    (hf / f'{stem}.json').write_text(json.dumps(rows, indent=1) + '\n', encoding="utf-8")
    (hf / f'{stem}.md').write_text(md, encoding="utf-8")
    print(f'wrote {hf / (stem + ".json")} (+ {stem}.md)' + ('; existing sfx-plan.json unchanged. '
          'Merge affected graphic IDs, preserving approved cues and levels elsewhere.' if candidate else ''))
    if changed: print('rows changed vs the previous plan: ' + ', '.join(changed))
    return 0


def meta_path(plan_path):
    """The plan's PLACEMENT RECORD, beside it: `sfx-plan.json` -> `sfx-plan.meta.json`."""
    plan_path = Path(plan_path)
    return plan_path.with_name(plan_path.stem + '.meta.json')


def plan_cues(plan_path):
    """{gid: [the `at` of every row of that graphic]} in the plan at `plan_path` ({} when there is none)."""
    cues = {}
    if Path(plan_path).exists():
        for r in json.loads(Path(plan_path).read_text(encoding="utf-8")): cues.setdefault(r.get('gid'), []).append(float(r['at']))
    return cues


def placement_record(hf, cues=None):
    """Which placement.json a plan is derived from: its sha1 (the fast path) and every placed graphic's id, start
    and end (what names the moved ones), with the `at` of that graphic's cues in the plan (`cues`, plan_cues()),
    which tells a re-cut that moved both from a graphic that moved alone. The caption layer is left out: it makes
    no sound, and it is re-placed on every caption tweak."""
    raw = (Path(hf) / 'placement.json').read_bytes()
    rows = [dict(id=r['id'], start=r['start'], end=r['end'], **({} if cues is None else {'cues': sorted(cues.get(r['id'], []))}))
            for r in json.loads(raw) if r.get('kind') != 'captions']
    return dict(placement_sha1=hashlib.sha1(raw).hexdigest(), placement=rows)


KEEP = object()


def write_meta(plan_path, hf, source='sfx-plan.py', gids=None, until=KEEP):
    """Record the placement a plan was derived from, read against the plan as written. With `gids` (a --merge)
    only those graphics were re-derived: the rest keep the entry their rows came from, or a graphic that moved since
    would stop being named. A merge into a plan that has no record writes none, since nothing says what the other
    rows were derived from. `until` is the COPY WINDOW a lane adopted the plan with (place-sfx.py --until), which every
    later command on the plan holds; KEEP carries the recorded one (a --record, a --merge), None clears it (a whole
    plan written fresh)."""
    rec, mp = dict(placement_record(hf, plan_cues(plan_path)), source=source), meta_path(plan_path)
    if until is KEEP: until = json.loads(mp.read_text(encoding="utf-8")).get('until') if mp.exists() else None
    if gids is not None:
        if not mp.exists(): return
        old = json.loads(mp.read_text(encoding="utf-8"))
        cur = {r['id']: r for r in rec['placement']}
        rows = sorted([r for r in old.get('placement', []) if r['id'] not in gids] + [cur[g] for g in gids if g in cur],
                      key=lambda r: (float(r['start']), r['id']))
        same = {r['id']: (r['start'], r['end']) for r in rows} == {r['id']: (r['start'], r['end']) for r in rec['placement']}
        rec = dict(placement_sha1=rec['placement_sha1'] if same else None, placement=rows, source=old.get('source', source))
    if until is not None: rec['until'] = until
    mp.write_text(json.dumps(rec, indent=1) + '\n', encoding="utf-8")


def stale_gids(plan_path, hf):
    """The graphics that moved, appeared or left since the plan was derived, and whose cues did not move with them
    ([] when none); None when the plan has no placement record (a plan written before the record existed)."""
    mp = meta_path(plan_path)
    if not mp.exists(): return None
    meta, rec = json.loads(mp.read_text(encoding="utf-8")), placement_record(hf)
    if meta.get('placement_sha1') == rec['placement_sha1']: return []
    old, new, cues = {r['id']: r for r in meta.get('placement', [])}, {r['id']: r for r in rec['placement']}, plan_cues(plan_path)
    def stale(g):
        if g not in old or g not in new: return True
        (a0, a1), (b0, b1) = ((float(x['start']), float(x['end'])) for x in (old[g], new[g]))
        if abs(b0 - a0) <= 1e-4 and abs(b1 - a1) <= 1e-4: return False
        # A RE-CUT moves the graphic AND its cues by the same amount (ripple-cut.py re-times placement.json and
        # sfx-plan.json together, 2026-09-23): the cues still sit on the graphic's motion, so that plan is not stale.
        # Naming it sent the creator to a re-plan that replaces hand-tuned rows. A graphic moved alone is stale.
        if 'cues' not in old[g] or abs((b1 - b0) - (a1 - a0)) > 1e-4: return True
        was, now = sorted(old[g]['cues']), sorted(cues.get(g, []))
        return len(was) != len(now) or any(abs(y - x - (b0 - a0)) > 1e-3 for x, y in zip(was, now))
    moved = [g for g in old.keys() | new.keys() if stale(g)]
    return sorted(moved, key=lambda g: (float((new.get(g) or old[g])['start']), g))


def arg_list(a, flag):
    """The values after `flag` up to the next flag, split on commas: `--merge g7,g9`, `--merge g7 g9` and a mix name
    the same ids (place-sfx.py's --remove too: only its first value was ever read, so four space-separated ids
    removed one clip without a word, 2026-09-22). None when the flag is absent, [] when no value follows it. Values
    that name no id at all ("", ",", " ": what `--remove "$IDS"` sends when IDS is empty) are refused, never read
    as no value: a bare --remove is the full clear."""
    if flag not in a: return None
    i, raw = a.index(flag) + 1, []
    while i < len(a) and not a[i].startswith('-'):
        raw.append(a[i]); i += 1
    out = [x.strip() for v in raw for x in v.split(',') if x.strip()]
    if raw and not out:
        sys.exit(f"✗ {flag} got {' '.join(repr(v) for v in raw)}, which names no id: nothing done")
    return out


def opt(a, flag):
    """The value after `flag`, None when the flag is absent; a flag with no value, or an empty one (`--plan "$P"` with
    P unset), is an error, never the default."""
    if flag not in a: return None
    i = a.index(flag) + 1
    if i >= len(a) or a[i].startswith('--'): sys.exit(f'{flag} needs a value')
    if not a[i].strip(): sys.exit(f'✗ {flag} got an empty value {a[i]!r}: nothing done (an empty value is never read as the default)')
    return a[i]


def check_args(a, flags, valued=(), listed=()):
    """Refuse a command line the script would half-read: an unknown flag (a typo'd --dry runs the real thing) and a
    value no flag takes (`--remove --sequence X s025` reads no id, and a bare --remove is the full clear). a[0] is
    the job; `valued` flags take one value, `listed` flags every value up to the next flag."""
    i, bad = 1, []
    while i < len(a):
        x = a[i]; i += 1
        if not x.startswith('-') or x not in flags: bad.append(x); continue
        if x in valued: i += 1
        elif x in listed:
            while i < len(a) and not a[i].startswith('-'): i += 1
    if bad: sys.exit(f"✗ not understood: {' '.join(bad)}: nothing done (--help lists the flags)")


def merge_rows(old, fresh, gids, tracks, win=1e-3):
    """An approved plan with ONLY `gids` re-planned: their old rows out, their fresh rows in, every other row the
    very same object (so the same bytes and id). A fresh row reuses its graphic's old ids in time order, then takes
    new ones past the plan's highest. A REPEAT of a sound already there (the same file, overlapping it) stays on that
    cue's layer and the earlier copy's tail is cut by the later one, as the planner lays repeats (the 2026-09-14
    one-layer lock): an earlier merged copy is trimmed here, an approved one by the overwrite, which the lane's tail
    line already reads off the next cue. Any other row that would overlap an approved cue on its track moves to the
    first free layer of `tracks`, because overwriteClip truncates whichever cue it lands on; the same sound within
    `win` (the layer window) of one already there is a doubling, not merged. Retiming one graphic's sound used
    to mean --candidate plus an inline copy of one row (2026-09-22). A row the lane ADOPTED off the timeline
    (event "hand": a cue the creator laid, which no comp or sfx-hand.json row can re-plan) is kept and named,
    never dropped in silence. Returns (rows, merged, warnings)."""
    adopted = [r for r in old if r.get('gid') in gids and r.get('event') == 'hand']
    kept = [r for r in old if r.get('gid') not in gids or r.get('event') == 'hand']
    reuse = {g: [r['id'] for r in sorted((r for r in old if r.get('gid') == g and r.get('event') != 'hand'), key=lambda r: r['at'])] for g in gids}
    top = max([int(m.group(1)) for r in old for m in [re.fullmatch(r's(\d+)', str(r.get('id', '')))] if m], default=0)
    span = lambda r: (r['at'], r['at'] + r['src_out'] - r['src_in'])
    def free(tr, x, placed):
        a, b = span(x)
        return not any(p['track'] == tr and p['at'] < b - 1e-4 and a < span(p)[1] - 1e-4 for p in placed)
    placed, merged = list(kept), []
    warns = [f"{r['gid']}: {r['id']} @{r['at']:.3f} ({os.path.basename(r['file'])}) was adopted off the timeline, so no re-plan "
             "can reproduce it: kept as it is; delete it from sfx-plan.json if the re-planned cue replaces it" for r in adopted]
    for x in sorted((dict(r) for r in fresh if r['gid'] in gids), key=lambda r: r['at']):
        rep = [p for p in placed if p['file'] == x['file'] and p['at'] < span(x)[1] - 1e-4 and x['at'] < span(p)[1] - 1e-4]
        dbl = next((p for p in placed if p['file'] == x['file'] and abs(p['at'] - x['at']) <= win), None)
        if dbl is not None:
            warns.append(f"{x['gid']} {x['event']} @{x['at']:.3f}: the same sound as {dbl.get('id', '?')} @{dbl['at']:.3f} "
                         f"[{dbl.get('gid')}] within the layer window, a doubling: not merged"); continue
        if rep:
            prior = [p for p in rep if p['at'] <= x['at']]
            x['track'] = (max(prior, key=lambda p: p['at']) if prior else min(rep, key=lambda p: p['at']))['track']
            nxt = [p['at'] for p in rep if p['track'] == x['track'] and p['at'] > x['at']]
            if nxt: x['src_out'] = round(x['src_in'] + min(nxt) - x['at'], 4)
        elif not free(x['track'], x, placed):
            tr = next((t for t in tracks if free(t, x, placed)), None)
            if tr is None:
                warns.append(f"{x['gid']} {x['event']} @{x['at']:.3f}: every SFX layer holds an approved cue there, not merged"); continue
            x['track'] = tr
        if reuse[x['gid']]: x['id'] = reuse[x['gid']].pop(0)
        else: top += 1; x['id'] = f's{top:03d}'
        placed.append(x); merged.append(x)
    return sorted(kept + merged, key=lambda r: r['at']), merged, warns


def layout_runs(plan):
    """The plan's top-level `layout` map as [(start, end, mode)] runs, sorted, adjacent same-mode rows merged (so an
    S -> S hand-off is not a switch). Rows are {start, end, mode} or [start, end, mode, ...]."""
    rows = []
    for r in plan.get('layout') or []:
        a, b, m = (r['start'], r['end'], r['mode']) if isinstance(r, dict) else (r[0], r[1], r[2])
        rows.append((float(a), float(b), str(m)))
    runs = []
    for a, b, m in sorted(rows):
        if runs and runs[-1][2] == m and a <= runs[-1][1] + 1e-3:
            runs[-1] = (runs[-1][0], max(runs[-1][1], b), m)
        else:
            runs.append((a, b, m))
    return runs


def layout_cut_ins(runs):
    """[(t, from, to)]: the switches that take the layout cut-in: INTO S or F from W, T or O, and S <-> F."""
    return [(y[0], x[2], y[2]) for x, y in zip(runs, runs[1:])
            if y[2] in ('S', 'F') and x[2] in ('W', 'T', 'O', {'S': 'F', 'F': 'S'}[y[2]])]


CALL_UI = frozenset({'ring', 'tap', 'riseIn', 'calling'})   # an overlay call card's own beats: the only sounds under a second voice


def voice_ranges(job, off=0.0):
    """The second voice (transcript/voices.json, RAW clock per clip) as TIMELINE ranges [(a, b)], mapped through
    transcript/cuts.json the way voice_spans_of() lays the voice: a sped segment plays its source over its `speed`, a
    segment's `_timeline` start wins when the EDL carries one, else `off` (the plan's timeline_offset) is added like
    every `at`. Summed at source length, a reply after a 500 % stretch was silenced seconds late (2026-10-13 audit).
    The one voices.json rule every reader holds: a span's clip is matched case-insensitively, a span with no clip is
    refused on an EDL cut from several raws, and a clip name the EDL does not use is refused (a typo would silently put
    sounds over the proof). No file: no second voice, []."""
    vp, cp = job / 'transcript' / 'voices.json', job / 'transcript' / 'cuts.json'
    if not vp.exists():
        return []
    data = json.loads(vp.read_text(encoding='utf-8'))
    spans = data.get('spans') if isinstance(data, dict) else None
    if not isinstance(spans, list):
        sys.exit(f'✗ {vp} has no `spans` list: {{"spans": [{{"clip", "start", "end", "voice"}}]}}')
    if not cp.exists():
        sys.exit(f'✗ {vp} names second-voice spans but there is no {cp} to map them onto the timeline')
    segs = json.loads(cp.read_text(encoding='utf-8'))['segments']
    clips = {os.path.basename(s_.get('clip') or '').lower() for s_ in segs}
    out = []
    for i, v in enumerate(spans):
        c = os.path.basename(v['clip']).lower() if v.get('clip') else None
        if c is None and len(clips) > 1:
            sys.exit(f'✗ {vp.name} spans[{i}] has no `clip` on an EDL cut from {len(clips)} raws: name its raw')
        if c is not None and c not in clips:
            sys.exit(f"✗ {vp.name} spans[{i}] names clip {v['clip']!r}, which {cp.name} does not use: fix the name")
        a0, b0, t = float(v['start']), float(v['end']), off
        for s_ in segs:                                  # mapped as voice_spans_of() lays them: `speed`, `_timeline`
            s0, s1, sp = float(s_['start']), float(s_['end']), float(s_.get('speed') or 1)
            sp = sp if sp > 0 else 1.0
            tl = s_.get('_timeline')
            a, t = (float(tl[0]), float(tl[1])) if isinstance(tl, list) and len(tl) == 2 else (t, t + (s1 - s0) / sp)
            if c is None or os.path.basename(s_.get('clip') or '').lower() == c:
                x, y = max(a0, s0), min(b0, s1)
                if y - x > 1e-3:
                    out.append((round(a + (x - s0) / sp, 4), round(a + (y - s0) / sp, 4)))
    return sorted(out)


STACK_CEIL_DB = -1.0     # the summed peak of the cues stacked on one moment, plus the voice under them


def job_gain(job):
    """The voice chain's gain in dB: the Premiere lane's own record (premiere/audio-polish.json, the highest gain any
    --apply wrote, so the check errs loud), else voice-gain.py's measurement. None when neither answers."""
    rp = job / 'premiere' / 'audio-polish.json'
    try:
        recs = json.loads(rp.read_text(encoding='utf-8')) if rp.exists() else []
        gains = [float(r['gain']) for r in recs if isinstance(r, dict) and r.get('gain') is not None]
        if gains:
            return max(gains)
    except (ValueError, OSError, TypeError):
        pass
    r = subprocess.run(['uv', 'run', '-q', str(ROOT / 'workflows' / 'voice-gain.py'), str(job), '--json'],
                       capture_output=True, text=True)
    try:
        return float(json.loads(r.stdout.strip().splitlines()[-1])['gain_db'])
    except (ValueError, IndexError, KeyError):
        return None


def voice_spans_of(job, off=0.0):
    """[(timeline start, timeline end, raw in, raw path, speed)] for every EDL segment, and the chain gain; ([], None)
    when the voice cannot be rebuilt (no EDL or no gain). A segment plays (end - start) / speed seconds of timeline (a
    clip the creator sped to 500 % carries "speed": 5.0, lanes/premiere/lab-notes.md), at its `_timeline` [start, end]
    (sequence seconds, a section's offset included) when the EDL carries one, else end to end from `off`."""
    cp = job / 'transcript' / 'cuts.json'
    gain = job_gain(job) if cp.exists() else None
    if gain is None:
        return [], None
    spans, t = [], off
    for s_ in json.loads(cp.read_text(encoding='utf-8'))['segments']:
        s0, s1, sp = float(s_['start']), float(s_['end']), float(s_.get('speed') or 1)
        sp = sp if sp > 0 else 1.0
        tl = s_.get('_timeline')
        a, t = (float(tl[0]), float(tl[1])) if isinstance(tl, list) and len(tl) == 2 else (t, t + (s1 - s0) / sp)
        spans.append((a, t, s0, job / 'raw' / os.path.basename(s_.get('clip') or ''), sp))
    return spans, gain


BED_DB = -20             # the house flat bed: what the lanes lay a music-plan.json with no bed_db at (place-music.py)


def music_bed(hf):
    """The opt-in music bed as the stacking check hears it: {track, source_in, bed_db, end} from
    hf-graphics/music-plan.json, None when there is none. It runs from timeline 0 at `source_in` (so timeline t plays
    source source_in + t), once, never looped, to the plan's `end` when it names one. `bed_db` is the clip gain in dB
    every lane lays it at (Premiere writes it through lanes/premiere/clip_level.py, the encoding that also carries every
    cue's level_db), so it is mixed exactly as a cue's level is. Held flat through the tail fade: that errs loud. A plan
    the check cannot decode is refused, never skipped: a bed left out is a stack read quiet. A SECTION sub-job
    (projects/<job>/sections/<s>/) with no plan of its own hears the PARENT's: the bed is laid once, from 0 of the one
    sequence the sections share, so its timeline is SEQUENCE time, which a section's cue `at` and voice spans already
    are (timeline_offset added): it mixes with no shift."""
    mp = Path(hf) / 'music-plan.json'
    job = Path(hf).parent
    if not mp.exists() and job.parent.name == 'sections':
        mp = job.parent.parent / 'hf-graphics' / 'music-plan.json'
    if not mp.exists():
        return None
    m = json.loads(mp.read_text(encoding='utf-8'))
    track = m.get('track')
    if not track or not os.path.exists(track):
        sys.exit(f'✗ {mp} names track {track!r}, which does not exist: fix the plan (or re-plan the bed), then re-run')
    try:
        sin, bed = float(m['source_in']), float(m.get('bed_db', BED_DB))
        end = float(m['end']) if m.get('end') is not None else None
    except (KeyError, TypeError, ValueError):
        sys.exit(f'✗ {mp} has no usable source_in / bed_db: lay the bed first (its pass writes the landed in-point)')
    if not (math.isfinite(sin) and sin >= 0 and math.isfinite(bed)):
        sys.exit(f'✗ {mp}: source_in {sin} / bed_db {bed} is not a bed this check can decode')
    return dict(track=track, source_in=sin, bed_db=bed, end=end)


def under_how(spans, gain, bed):
    """What the stacking check mixed under the cues, for the cut sheet."""
    v = (f'the voice rebuilt from the raw at {gain:+g} dB into the -6 dBFS limiter' if spans
         else 'no voice (no EDL or gain to rebuild it)')
    return v + (f", and the music bed ({os.path.basename(bed['track'])} from {bed['source_in']:g} s at {bed['bed_db']:+g} dB)"
                if bed else '')


def mix_peak(group, spans, gain, a, b, bed=None):
    """The TRUE peak (dBTP) of timeline [a, b] as the lane plays it: the voice (its raw spans through the house chain,
    the measured gain into the -6 dBFS limiter), the music bed under it when there is one (music_bed()), plus every
    cue of `group` at its level, summed, never normalised. A sped span reads `speed` seconds of source per timeline
    second, resampled to play in its timeline length. A MONO raw is rebuilt as DUAL MONO, full level on both channels,
    the way voice-gain.py measures it and every lane plays it (Premiere's pan-law give-back, Final Cut's +6 dB): the
    stereo upmix put it 3 dB under its stereo twin and passed stacks up to 3 dB over the ceiling (2026-10-13 audit).
    A mono cue or bed keeps that upmix: the lanes play them under the pan law."""
    ins, fc, lab = [], [], []
    for t0, t1, s0, raw, sp in spans:
        x, y = max(a, t0), min(b, t1)
        if y - x > 1e-3 and raw.exists():
            k = len(ins) // 6
            ins += ['-ss', f'{s0 + (x - t0) * sp:.4f}', '-t', f'{(y - x) * sp:.4f}', '-i', str(raw)]
            fc.append(f'[{k}:a]' + ('pan=stereo|c0=c0|c1=c0,' if channels(raw) == 1 else '')
                      + 'aformat=sample_rates=48000:channel_layouts=stereo,'
                      + (f'asetrate={round(48000 * sp)},aresample=48000,' if sp != 1 else '') + f'volume={gain}dB,'
                      f'alimiter=level_in=1:level_out=1:limit=0.501:attack=5:release=50:level=disabled:latency=1,'
                      f'adelay={int(round((x - a) * 1000))}:all=1[m{k}]')
            lab.append(f'[m{k}]')
    be = min(b, bed['end']) if bed and bed['end'] is not None else b
    if bed and be - a > 1e-3 and bed['source_in'] + a < file_dur(bed['track']) - 1e-3:   # past its end the bed is silent
        k = len(ins) // 6
        ins += ['-ss', f"{bed['source_in'] + a:.4f}", '-t', f'{be - a:.4f}', '-i', bed['track']]
        fc.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={bed['bed_db']}dB[m{k}]")
        lab.append(f'[m{k}]')
    for r in group:
        k = len(ins) // 6
        ins += ['-ss', '0', '-t', '36000', '-i', r['file']]
        fc.append(f"[{k}:a]atrim=start={r['src_in']}:end={r['src_out']},asetpts=PTS-STARTPTS,"
                  f"aformat=sample_rates=48000:channel_layouts=stereo,volume={r['level_db']}dB,"
                  f"adelay={int(round((r['at'] - a) * 1000))}:all=1[m{k}]")
        lab.append(f'[m{k}]')
    fc.append(''.join(lab) + f'amix=inputs={len(lab)}:normalize=0:duration=longest,ebur128=peak=true:framelog=quiet[o]')
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', *ins, '-filter_complex', ';'.join(fc), '-map', '[o]',
                        '-f', 'null', '-'], capture_output=True, text=True)
    m = re.findall(r'Peak:\s+(-?[0-9.]+|-inf) dBFS', r.stderr)
    if r.returncode or not m:                 # a mix that did not measure is never "under the ceiling"
        sys.exit(f"✗ the stacked-cue peak did not measure (ffmpeg exit {r.returncode}): {r.stderr.strip()[-300:]}")
    return float(m[-1]) if m[-1] != '-inf' else -120.0


def stack_levels(rows, spans, gain, fixed=frozenset(), bed=None):
    """Keep every moment where cues overlap under STACK_CEIL_DB TRUE peak, measured on the mix itself: each cluster
    of overlapping cues is summed with the voice and the music bed (`bed`, music_bed()) under it (mix_peak), and over
    the ceiling the deepest layer comes
    down first (A4, then A3, then A2; the later cue on a tie), whole dB, at most 12 dB a cue; a hand row keeps its
    level. Cues were levelled one by one against a class target, so a cut-in whoosh + a slam + a loud word reached
    -0.007 dBFS on the Windows long-form (2026-09-27) while the voice alone is limited at -6. A moment that stays
    under the ceiling is never touched: the levels are the preset's, tuned by ear. A lone cue is measured only over
    the rebuilt voice or the bed (on its own it sits at its class target). `fixed` holds the id() of rows that keep their level
    like a hand row: on --merge, every approved row the merge keeps ("kept as approved"), so only the re-planned
    graphic's own sounds can come down. -> [line] per change."""
    end = lambda r: r['at'] + (r['src_out'] - r['src_in'])
    clusters, cur = [], []
    for r in sorted(rows, key=lambda r: r['at']):
        if cur and r['at'] >= max(end(c) for c in cur):
            clusters.append(cur); cur = []
        cur.append(r)
    if cur: clusters.append(cur)
    cut, lines = {}, []
    for c in clusters:
        if len(c) < 2 and not spans and not bed:
            continue                                              # a lone cue at its class target cannot reach the ceiling alone
        a, b = c[0]['at'], max(end(r) for r in c)
        for _ in range(24):
            pk = mix_peak(c, spans, gain, a, b, bed)
            if pk <= STACK_CEIL_DB:
                break
            cand = [r for r in c if not r.get('hand') and id(r) not in fixed and cut.get(id(r), 0) < 12]
            if not cand:
                lines.append(f"⚠ @{a:.3f}: the stack {', '.join(r['id'] for r in c)} peaks at {pk:.1f} dBTP and nothing left "
                             "can come down (a hand row, an approved row a --merge keeps, a lone cue, or 12 dB already): "
                             "lower one by hand")
                break
            r = max(cand, key=lambda r: (r['track'], r['at']))
            d = min(12 - cut.get(id(r), 0), max(1, math.ceil(pk - STACK_CEIL_DB)))
            r['level_db'] -= d
            cut[id(r)] = cut.get(id(r), 0) + d
    under = ' and '.join(x for x, on in (('the voice', spans), ('the bed', bed)) if on)
    for r in rows:
        if id(r) in cut:
            others = [o['id'] for o in rows if o is not r and o['at'] < end(r) and r['at'] < end(o)]
            lines.append(f"{r['id']} A{r['track'] + 1} {r['gid']} {r['event']} @{r['at']:.3f}: -{cut[id(r)]} dB to "
                         f"{r['level_db']:+g} (" + (f"stacked with {', '.join(others)}" + (f" and {under})" if under else ")")
                                                    if others else f"over {under} alone)"))
    return lines


TABLE_HEAD = '| # | at | track | graphic | event | sound | slice | level | peak→ | note |'


def sheet_row(x):
    """Plan row x as a line of the cut sheet's table."""
    return (f"| {x['id']} | {x['at']:.3f} | A{x['track'] + 1} | {x['gid']} | {x['event']} | {os.path.basename(x['file'])} | "
            f"{x['src_in']:.2f}–{x['src_out']:.2f} | {x['level_db']:+g} dB | "
            + (f"{x['peak'] + x['level_db']:.1f}" if 'peak' in x else '—') + f" | {x.get('note', '')}"   # an adopted row has no measured peak
            + (f" · fade-out {x['fade_out_s']:g} s on the tail" if x.get('fade_out_s') else '') + " |")


def restack(job, hf, dry=False):
    """--restack: the stacking check ALONE over the approved sfx-plan.json, against what plays under it now: the voice
    and the music bed, whose pass lays it after the SFX. Only level_db moves, and only in a stack over the ceiling
    (stack_levels(), the rule unchanged: a hand row, an adopted one included, keeps its level); every other field of
    every row stays as approved. The cut sheet's table is re-read from the rows and the changes are appended under
    their own heading; its other sections stay the last full plan's. Writes nothing when nothing moved. -> 1 while a
    stack stays over the ceiling (a ⚠: nothing left here may come down), else 0."""
    pp = hf / 'sfx-plan.json'
    if not pp.exists():
        sys.exit(f'✗ no {pp} to re-level: plan the SFX first (sfx-plan.py with no flags)')
    rows = json.loads(pp.read_text(encoding='utf-8'))
    off = float(json.loads((job / 'graphics-plan.json').read_text(encoding='utf-8')).get('timeline_offset') or 0.0)
    bed = music_bed(hf)
    vspans, vgain = voice_spans_of(job, off)
    how = under_how(vspans, vgain, bed)
    was = [r['level_db'] for r in rows]
    lines = stack_levels(rows, vspans, vgain, bed=bed)
    moved = [r for r, w in zip(rows, was) if r['level_db'] != w]
    warned = any(ln.startswith('⚠') for ln in lines)
    print(f"mixed every stack of {pp.name} with {how}")
    for ln in lines: print('  ' + ln)
    if not moved:
        print(f"{pp.name} unchanged: " + ('a stack stays over the ceiling (⚠ above)' if warned
                                          else f'every stack is under {STACK_CEIL_DB:g} dBTP'))
        return 1 if warned else 0
    if dry:
        print(f"--dry: {len(moved)} row(s) would come down, nothing written")
        return 1 if warned else 0
    mdp = hf / 'sfx-plan.md'
    md = mdp.read_text(encoding='utf-8').splitlines() if mdp.exists() else [f'# SFX plan — {job.name}']
    table = [TABLE_HEAD, '|---|---|---|---|---|---|---|---|---|---|'] + [sheet_row(x) for x in rows]
    if TABLE_HEAD in md:
        i = j = md.index(TABLE_HEAD)
        while j < len(md) and md[j].startswith('|'): j += 1
        md[i:j] = table
    else:
        md += ['', *table]
    md += ['', f"## re-levelled by --restack, {time.strftime('%Y-%m-%d %H:%M')} ({len(moved)})", '',
           f'Every stack re-mixed with {how} and its TRUE peak read; over {STACK_CEIL_DB:g} dBTP the deepest layer came '
           'down first. sfx.md § The law 5.', ''] + [f'- {d}' for d in lines]
    bak = hf / f"sfx-plan.pre-restack-{time.strftime('%Y%m%d-%H%M%S')}.json"
    shutil.copy2(pp, bak)
    write_plan(hf, rows, '\n'.join(md) + '\n')
    ids = ','.join(r['id'] for r in moved)
    jarg = (Path(os.path.relpath(job)) if job.is_relative_to(Path.cwd().resolve()) else job).as_posix()
    print(f"re-levelled {len(moved)} row(s): {ids}; backup {bak.name}")
    print(f"  -> re-lay them on the lane (LANES.md § step 6); Premiere: uv run lanes/premiere/place-sfx.py {jarg} "
          f"--remove {ids}, then --apply, then --verify")
    return 1 if warned else 0


def main():
    a = sys.argv[1:]
    if '-h' in a or '--help' in a: print(__doc__); return 0
    if not a: sys.exit(__doc__)
    check_args(a, {'--dry', '--candidate', '--merge', '--record', '--plan', '--restack'}, valued={'--plan'}, listed={'--merge'})
    job = Path(a[0]).resolve(); dry = '--dry' in a
    hf = job / 'hf-graphics'
    for f in (hf / 'placement.json', job / 'graphics-plan.json'):
        if not f.exists(): sys.exit(f'✗ no {f}: sfx-plan.py scores the PLACED graphics of a job (placement.json, graphics-plan.json)')
    if '--record' in a:
        # the placement record for a plan this run did not write: an older job's (hand-tuned, so a re-run would
        # replace approved rows) or an AD cut's (adopted off its own sequence, which this script never writes)
        if {'--merge', '--candidate', '--dry', '--restack'} & set(a): sys.exit('--record writes the placement record and nothing else: run it on its own')
        pp = job / (opt(a, '--plan') or 'hf-graphics/sfx-plan.json')
        if not pp.exists(): sys.exit(f'✗ no {pp}: nothing to record')
        mp = meta_path(pp)
        write_meta(pp, hf, source=json.loads(mp.read_text(encoding="utf-8")).get('source', 'record') if mp.exists() else 'record')
        print(f'recorded the current placement.json for {pp.name} in {mp.name}; {pp.name} unchanged')
        return 0
    if '--plan' in a: sys.exit('--plan names the plan --record records; the planner itself writes hf-graphics/sfx-plan.json')
    if '--restack' in a:
        if {'--merge', '--candidate'} & set(a): sys.exit('--restack re-levels the approved sfx-plan.json and nothing else: run it on its own (or with --dry)')
        return restack(job, hf, dry)
    rows_in = json.load(open(hf / 'placement.json', encoding="utf-8"))
    plan = json.load(open(job / 'graphics-plan.json', encoding="utf-8"))
    merge = arg_list(a, '--merge')
    if merge is not None:
        if not merge: sys.exit('--merge names the graphics to re-plan: --merge g7,g9')
        if '--candidate' in a: sys.exit('--merge writes into the approved sfx-plan.json; --candidate parks a whole plan beside it: pick one')
        if not (hf / 'sfx-plan.json').exists(): sys.exit(f"✗ no {hf / 'sfx-plan.json'} to merge into: run without --merge first")
        # a graphic that LEFT placement.json is merged too (its planned rows go): the staleness warning names it
        known = {r['id'] for r in rows_in if r.get('kind') != 'captions'} | set(plan_cues(hf / 'sfx-plan.json'))
        unknown = [g for g in merge if g not in known]
        if unknown: sys.exit(f"✗ --merge {', '.join(unknown)}: not a placed graphic (placement.json ids) and no row of sfx-plan.json")
        approved = json.loads((hf / 'sfx-plan.json').read_text(encoding="utf-8"))
    # a SECTION sub-job's rows sit in the section's own time base; the plan's timeline_offset puts every cue on the
    # sequence (an outro section at 152.694208, 2026-09-14). `at` stays a TIMELINE time, as documented above.
    OFF = float(plan.get('timeline_offset') or 0.0)
    preset_dir = ROOT / plan.get('preset', 'presets/youtube/default')
    if preset_dir.is_file(): preset_dir = preset_dir.parent          # plans point at the style doc
    if not (preset_dir / 'sfx.json').exists():
        # SFX runs on every format (2026-09-04): a preset with no sound map of its own borrows the house
        # one, and the report says so (the Talking Head Explainer ships its own)
        print(f"[sfx-plan] {preset_dir.relative_to(ROOT)} has no sfx.json: using presets/youtube/default/sfx.json (the house sound map)")
        preset_dir = ROOT / 'presets/youtube/default'
    cfg = json.load(open(preset_dir / 'sfx.json', encoding="utf-8"))
    lib = ROOT / cfg['library']
    fps = probe_fps(next(r['file'] for r in rows_in if os.path.exists(r['file'])))
    F = 1 / fps
    snap = lambda t: round(round(t / F) * F, 4)
    T = cfg['targets_dbfs']; TR = cfg['tracks']; EV = cfg['events']
    rot = {}
    out, warns = [], []
    n_answered = 0
    seen_gids = set()
    # hand entries for comps whose motion is not written with the registry (pre-2026-09-02 jobs):
    # hf-graphics/sfx-hand.json = [{"gid", "event", "at": <comp-relative seconds>, "note"?, "dur"?}]; a "src": "kit" row
    # may also carry "sync_offset"? (the beat's designed offset from its word, s, negative = ahead): ignored here, it is
    # for change-events.py --sync and a reader
    HAND = {}
    hp = hf / 'sfx-hand.json'
    if hp.exists():
        for h in json.load(open(hp, encoding="utf-8")): HAND.setdefault(h['gid'], []).append(h)
    # the plan cell behind a placed row (id equal, or the row id is <planid>-<slug>): its KIND decides
    # some pairings (a pop inside a list/card graphic is a row tick, not an object)
    cells = {b['id']: b for b in plan.get('beats', []) if b.get('graphic')}
    def cell_kind(gid):
        c = cells.get(gid) or next((cells[k] for k in sorted(cells, key=len, reverse=True) if gid.startswith(k + '-')), None)
        return (c or {}).get('kind', '')
    first_cut_in = not OFF   # a SECTION sub-job (timeline_offset) is never the job's first cut-in: no opening riser (2026-09-14)
    LAYOUT = layout_runs(plan)
    under_f = lambda t: any(a_ - 1e-3 <= t < b_ - 1e-3 for a_, b_, m_ in LAYOUT if m_ == 'F')

    def add(gid, event, at, note='', dur=None, level=None, auto=True, hand=False):
        # an event the preset does not KNOW is a typo or a sound that never entered the palette, and dropping it
        # in silence is how a cue that only ever lived in a job's plan disappears on the next rebuild. A
        # documented event mapped to null (an exit, a cut-out) is deliberate silence and says nothing.
        if event not in EV: warns.append(f'{gid}: {event!r} is not an event in sfx.json, dropped: document it there first (sfx.md § The map)'); return
        spec = EV.get(event)
        if spec is None or not isinstance(spec, dict): return
        if auto and spec.get('hand_only'): return
        path = str(lib / spec['file'])
        if not os.path.exists(path): warns.append(f'{event}: {spec["file"]} missing from {lib}'); return
        k = rot.get(event, 0); rot[event] = k + 1
        s_in, s_out = (0.0, file_dur(path)) if spec.get('whole_file') else spec['slices'][k % len(spec['slices'])]
        if spec.get('fit') == 'duration' and dur: s_out = min(s_out, s_in + max(dur, 0.2))
        at = at - spec.get('lead_frames', 0) * F + spec.get('offset_frames', 0) * F + OFF
        peak = slice_peak(path, s_in, s_out)
        if peak < -40:
            warns.append(f'{event}: slice {s_in}-{s_out} of {spec["file"]} is silent ({peak} dBFS), skipped'); return
        lvl = int(round(level)) if level is not None else (spec['level_db'] if 'level_db' in spec else min(6, round(T[spec['class']] - peak)))   # hand > fixed > class band
        out.append(dict(gid=gid, event=event, at=snap(at), file=path, src_in=round(s_in, 3), src_out=round(s_out, 3),
                        level_db=lvl, cls=spec['class'], note=note, hand=hand, peak=peak,
                        **({'fade_out_s': spec['fade_out_s']} if spec.get('fade_out_s') else {}), _lv=level, _dur=dur))

    for r in sorted(rows_in, key=lambda r: r['start']):
        gid, kind, start = r['id'], r.get('kind'), float(r['start'])
        if kind == 'captions': continue     # the caption layer has no comp and makes no sound (captions are silent by design)
        try:
            comp = find_comp(hf, gid, r['file'])
        except ValueError as e:
            warns.append(f"{e}; leave exactly one composition matching that id in the placed render's own compositions/ "
                         'folder (retire the obsolete comp and its builder spec out of the scanned folders), or name the '
                         'part comp in the render filename, then re-run')
            continue
        if not comp:
            if any(h.get('silent') for h in HAND.get(gid, [])): n_answered += 1; seen_gids.add(gid); continue   # it makes no sound, by design
            warns.append(f'{gid}: no comp found under hf-graphics/*/compositions; events for it need a hand entry '
                         f'(or {{"gid": "{gid}", "silent": true}} if it makes no sound)'); continue
        html = comp.read_text(encoding="utf-8")
        hand = HAND.get(gid, []); seen_gids.add(gid)
        drop = {d for h in hand for d in h.get('drop', [])}
        words = text_events(html)                                  # word spans: a text animation, or a line inside a full-screen
        # a hand entry addressed by WORD (any event) resolves to that span's time; emphasis also
        # takes the word's scissors away
        emph = set()
        for h in hand:
            if not h.get('word') or h.get('at') is not None: continue
            key = h['word'].lower().strip('.,!?')
            hit = next((t for _, t, w_, _ in words if w_.lower().strip('.,!?') == key), None)
            if hit is None: warns.append(f"{gid}: hand entry word {h['word']!r} matches no span in {comp.name}"); continue
            h['at'] = hit
            if h['event'] == 'emphasis': emph.add(key)
        # the text builder's ENTRANCE decides the word sound: rise -> scissors (a RED word -> the
        # Error Buzz, an EMPHASIS hand entry -> the Impact), punch/pop -> the pop, slam -> the
        # Impact stamp, flicker -> ONE Neon Flicker at the block's first word (the strobe start)
        ent = (re.search(r'const ENTRANCE\s*=\s*"(\w+)"', html) or [None, 'rise'])[1]
        if ent == 'punch':                                          # the builder emits pop AND slam as "punch"; the shape tells them apart
            over = re.search(r'POP_OVER\s*=\s*([\d.]+)', html)
            ent = 'pop' if over and float(over.group(1)) > 0 else 'slam'
        if ent == 'flicker' and words:
            add(gid, 'word-flicker', start + min(t for _, t, _, _ in words), 'flicker strobe: ' + ' '.join(w_ for _, _, w_, _ in words))
        else:
            wev = {'pop': 'word-pop', 'slam': 'word-slam'}.get(ent, 'word')
            for ev, t, w_, cls in words:
                key = w_.lower().strip('.,!?')
                if key in emph: continue                            # the emphasis hand entry places its own row
                if wev == 'word' and 'red' in cls.split() and 'word-negative' not in drop: add(gid, 'word-negative', start + t, f'{w_} (red: negation)'); continue
                if wev not in drop: add(gid, wev, start + t, f'{w_} ({ent})' if ent != 'rise' else w_)
        if kind == 'text' and words and not any(h.get('at') is not None for h in hand): continue   # a pure text animation has no other events (a hand entry keeps going)
        evs, w = comp_events(html, fps)
        # a ⚠ the hand entries already ANSWER is not a warning: a hand row for this gid whose event is the call
        # the parser could not bind IS the answer, and reprinting it every run buries a genuinely new one
        hand_ev = {h.get('event') for h in hand}
        kept_w = []
        for x in w:
            mm = re.match(r'(\w+)', x)
            if mm and mm.group(1) in hand_ev: n_answered += 1; continue
            kept_w.append(x)
        w = kept_w
        ck = cell_kind(gid)
        evs = [e for e in evs if e[0] not in drop]
        if ck in ('list', 'card'): evs = [('row-tick',) + tuple(e[1:]) if e[0] == 'pop' else e for e in evs]   # rows tick on, objects pop
        # TYPE in a hand comp takes the text sounds (2026-09-10: type never pops; text = the scissors on a
        # rise, the Impact on a slam): an element whose OWN text is words, found from the markup, no marker needed
        tt = type_targets(html)
        done = completion_targets(html)
        marks = sfx_markers(html); used_marks = set()
        # a hand-rolled event carries its note after the selector ('.cur (hand-rolled)'): the note stays on the row,
        # but the marker lookup keys on the selector, or a data-sfx on a hand-tweened element is never honoured
        def _sel(e): return re.sub(r'\s*\(hand-rolled[^)]*\)$', '', str(e[2]).strip()).strip("'\"").split(' ')[-1] if len(e) > 2 else ''
        remap = []
        for e in evs:
            s = _sel(e)
            m = marks.get(s)
            if m:                                                       # the author named a DOCUMENTED sound: it wins over every rule below
                used_marks.add(id(m))
                if m.get('event') == 'none': continue
                if m.get('file'): warns.append(f"{gid}: data-sfx-file={m['file']!r} on {s} ignored: only the events documented in sfx.json may be used (2026-09-10: nobody here can listen to a file; document it first)")
                elif m.get('event') and m['event'] in EV: remap.append((m['event'], e[1], f"{s} (named: {m['event']})") + tuple(e[3:])); continue
                else: warns.append(f"{gid}: data-sfx={m.get('event')!r} on {s} is not an event in sfx.json")
            if s in done and e[0] in ('pop', 'slam', 'row-tick') and 'payoff' not in drop:
                remap.append(('payoff', e[1], f"{s} (completion: the bell, not the {e[0]})") + tuple(e[3:])); continue   # sound follows meaning
            if s in tt:
                if e[0] == 'riseIn': remap.append(('word',) + tuple(e[1:])); continue
                if e[0] == 'slam': remap.append(('word-slam',) + tuple(e[1:])); continue
                if e[0] == 'pop': warns.append(f'{gid}: pop({s}) on TYPE: type never pops (animations.md), fix the comp (rise + scissors, or slam + Impact)')
            remap.append(e)
        for k, mm in marks.items():
            # `none` is an explicit SILENCE and says nothing more, so it rides nothing by definition. `pop` is
            # different: it doubles as the completion opt-out AND as a real placeable event in the same map, so
            # an element marked `pop` that rode no registry call is either a deliberate opt-out on hand-tweened
            # motion or a cue the author expected and never got — and silence cannot tell them apart. That is
            # the silent-cue-loss class this whole warning exists to stop, so `pop` warns like every other event
            # and a hand row for this gid naming it is what answers (2026-09-19).
            if id(mm) in used_marks or mm.get('event') == 'none': continue
            used_marks.add(id(mm))                                  # one warning per element, not per selector key
            ev_ = mm.get('event') or mm.get('file')
            if ev_ in hand_ev: n_answered += 1; continue
            warns.append(f"{gid}: data-sfx={ev_!r} on {k} rode no registry event (the element is not animated by the registry): add a row in hf-graphics/sfx-hand.json, or animate it with the registry (sfx.md § Sound follows MEANING)"
                         + (" — or, if this is the completion opt-out on hand-tweened motion, say so with a hand row" if ev_ == 'pop' else ''))
        # `drop` names the event as the PLAN names it, not only the registry call the comp wrote: a pop the
        # rules turned into a row-tick, a riseIn on type turned into a word, a data-sfx remap. The pre-remap
        # filter above cannot see those, so the remedy every ⚠ prints ("drop": ["<the automatic event>"])
        # was a no-op on exactly the remapped rows. Both spellings work now.
        evs = [e for e in remap if e[0] not in drop]
        for h in hand:
            if h.get('file'): warns.append(f"{gid}: hand row with file={h['file']!r} ignored: only the events documented in sfx.json may be used (document it first)")
        # a row the preset kit wrote (`src: kit`) is the AUTOMATIC first pass: it rides as an automatic row (the
        # density cap, the layer rules and a hand row's `drop` apply to it), never as the creator's hand row, which
        # outranks it
        hand_evs = [(h['event'], float(h['at']), h.get('note', 'kit' if h.get('src') == 'kit' else 'hand'), h.get('dur'),
                     h.get('level_db'), h.get('src') == 'kit') for h in hand if h.get('at') is not None and not h.get('file')
                    and not (h.get('src') == 'kit' and h['event'] in drop)]
        for h in hand_evs: evs.append(h)
        warns += [f'{gid}: {x}' for x in w if not any(x.startswith(k + '(') for k, v in EV.items() if v is None)]
        if not evs and not w and not words:
            # its hand rows ARE the answer to hand-rolled motion, and `{"gid", "silent": true}` is the answer for a
            # graphic that deliberately makes no sound (five raw-GSAP comps warned on every run for want of one)
            if hand: n_answered += 1
            else: warns.append(f'{gid}: no registry calls found in {comp.name} (hand-rolled motion): its events need a hand entry '
                               f'(or {{"gid": "{gid}", "silent": true}} if it makes no sound)')
        if kind == 'full':
            if under_f(start):
                pass                                                # the layout map sounds this cut (below)
            elif not any(e[0] == 'flash' and abs(e[1]) <= 2 * F + 1e-4 for e in evs) and 'cut-in' not in drop:
                add(gid, 'cut-in', start, 'hard cut into the full-screen')   # a flicker on frame 0 IS the cut's sound
            if EV.get('riser') and (first_cut_in or not EV['riser'].get('first_cut_in_only', True)):   # the riser belongs to the FIRST full-screen, whoosh or not
                sp = EV['riser']; d = sp['slices'][0][1] - sp['slices'][0][0]
                t0 = start - cfg['riser_gap_s'] - d
                if t0 >= 0: add(gid, 'riser', t0, 'first cut-in of the job')
                else: warns.append(f'{gid}: no room for the riser before the first full-screen at {start:.2f}s (needs {cfg["riser_gap_s"] + d:.2f}s)')
                first_cut_in = False
        for e in evs:
            name, t, note = e[0], e[1], e[2]
            dur = e[3] if len(e) > 3 else None
            level = e[4] if len(e) > 4 else None
            if t < 0 or t > float(r['end']) - start + 0.05: continue
            hand_row = len(e) > 4 and not (len(e) > 5 and e[5])    # a kit row is automatic
            add(gid, name, start + t, note, dur, level, auto=not hand_row, hand=hand_row)

    # THE LAYOUT MAP'S CUT-INS (layout.md § 12; sfx.md § 2): the face-to-graphic hard cuts. Each is filed under the
    # graphic the switch opens (the placed row starting nearest it, within a second), else under `layout`.
    if LAYOUT:
        placed_ = [r for r in rows_in if r.get('kind') != 'captions']
        for t, m0, m1 in layout_cut_ins(LAYOUT):
            near = min(placed_, key=lambda r: abs(float(r['start']) - t), default=None)
            gid = near['id'] if near is not None and abs(float(near['start']) - t) <= 1.0 else 'layout'
            if merge is not None and gid not in merge: continue
            if 'cut-in' in {d for h in HAND.get(gid, []) for d in h.get('drop', [])}: continue
            add(gid, 'cut-in', t, f'layout {m0} -> {m1}')

    if LAYOUT:
        seen_gids.add('layout')                                    # a switch with no graphic near it is filed here
    for g_ in HAND:
        if g_ not in seen_gids: warns.append(f'sfx-hand.json names {g_!r}, which is not a placed graphic (placement.json ids: check the spelling)')
    # NOTHING OVER PROOF AUDIO (the Talking Head Explainer's sfx.md law 3, which outranks every other rule): while the
    # second voice plays (transcript/voices.json, through the EDL) every automatic row goes silent, the layout's
    # cut-ins and the kit's rows included, except an overlay call card's own beats (its ring, its answer tap, its
    # entrance, the calling bed). A hand row is the creator's call and stays. Each drop is named in the cut sheet.
    # The rule is the PRESET's (its sfx.json `second_voice.silence`): the house map does not carry it, so a long-form
    # with a call keeps its automatic rows, as it did before this rule existed.
    voiced = []
    VR = voice_ranges(job, OFF) if (cfg.get('second_voice') or {}).get('silence') else []
    if VR:
        fam = lambda g: ((cells.get(g) or next((cells[k] for k in sorted(cells, key=len, reverse=True)
                                                 if g.startswith(k + '-')), None)) or {}).get('family')
        kept = []
        for x in out:
            vr = next(((a_, b_) for a_, b_ in VR if a_ - 1e-3 <= x['at'] < b_ - 1e-3), None)
            if vr and not x['hand'] and not (fam(x['gid']) == 'overlay' and x['event'] in CALL_UI):
                voiced.append(f"{x['gid']} {x['event']} @{x['at']:.3f} ({x['note'][:30]}): under the second voice "
                              f"{vr[0]:.3f}-{vr[1]:.3f}s")
                continue
            kept.append(x)
        out = kept
    # --MERGE RE-DECIDES THE NAMED GRAPHICS AGAINST THE APPROVED PLAN, never against fresh rows it does not keep: a
    # fresh neighbour the approved plan moved or deleted by hand cut a merged cue's tail (the repeat truncation) or
    # dropped it (the doubling, the density cap), and nothing warned (2026-09-23 review). So only the merged graphics'
    # fresh rows go on from here: the cross-graphic cap reads the approved rows as fixed CONTEXT (counted, never
    # dropped), and merge_rows() re-derives the repeat, the doubling and the layer against the approved rows.
    ctx = []
    if merge is not None:
        out = [x for x in out if x['gid'] in merge]
        ctx = [dict(r, fixed=True, cls=r.get('cls', ''), hand=r.get('hand', False)) for r in approved
               if r.get('gid') not in merge or r.get('event') == 'hand']
    # layer stacking: a sound that would OVERLAP a different sound already on a track goes a layer
    # down, so both ring out (the reference put Deep Whoosh 3 under Deep Whoosh 4 on its own track);
    # the same sound repeating on top of itself stays on one track and truncates, which is exactly
    # the reference's machine-gun pops (0.29 / 0.25 / 0.21s, each cut by the next). An identical
    # sound within 2 frames is a doubling, not a layer, and is dropped.
    # A HAND ENTRY OUTRANKS THE AUTOMATIC ROW IT DOUBLES: the two density rules below already refuse to drop a
    # hand entry, and the doubling rule under them keeps whichever copy it reaches first, so the hand row sorts
    # ahead of the automatic one at the same instant. Without this the creator's note, level and slice are the
    # copy that silently loses (2026-09-19: three hand-written wall whooshes replaced by the parser's own rows).
    # ONLY against the copy it doubles, though — the same sound within the layer window. Sorting every hand row
    # ahead of everything on its instant also reorders the TRACK ALLOCATOR at the bottom of this function, and a
    # hand BED that sorts first takes the primary layer and pushes that frame's transients a layer up: seven rows
    # on a shipped job changed track for no editorial reason, which reads as drift on the lane's --verify.
    lw_ = cfg['layer_window_frames'] * F + 1e-4
    doubles = {id(x) for x in out if x['hand']
               and any(p['file'] == x['file'] and not p['hand'] and abs(p['at'] - x['at']) <= lw_ for p in out)}
    out.sort(key=lambda x: (x['at'], id(x) not in doubles))
    # ── DENSITY (2026-09-10, on a 2 s stretch carrying seven sounds: "there's too many, it's too much going on") ──
    # 1. THE STAMP OWNS ITS BEAT: a slam / Impact carries the beat alone. The same graphic's other transients within
    #    ±stamp_owns_beat_s (the scissors of the words around it, the marker stroke under it, a pop) are dropped; the
    #    cut-in stays (the graphic's own entrance, two frames before), beds stay, hand entries stay.
    STAMPS = {'word-slam', 'slam', 'emphasis'}
    beat = float(cfg.get('stamp_owns_beat_s', 0.6))
    drops = []
    stamps = [x for x in out if x['event'] in STAMPS]
    kept = []
    for x in out:
        s_ = next((s for s in stamps if s is not x and s['gid'] == x['gid'] and abs(s['at'] - x['at']) <= beat), None)
        if s_ and x['event'] not in STAMPS and x['event'] not in ('cut-in', 'riser', 'slideIn', 'slideOut') and x['cls'] != 'bed' and not x['hand']:   # scene changes are structure, not accents: they keep their whoosh
            drops.append(f"{x['gid']} {x['event']} @{x['at']:.3f} ({x['note'][:30]}): inside the {s_['event']} @{s_['at']:.3f}'s beat (±{beat:.1f}s)"); continue
        kept.append(x)
    out = kept
    # 2. THREE SOUNDS A SECOND, NO MORE, across all graphics (rolling 1 s), where a RUN of one sound from one graphic
    #    (the scissors of a text animation's words, a wall's machine-gun pops) counts ONCE: the pile-up is different
    #    sounds from different graphics landing together. The lowest-priority source in an over-full second goes (a
    #    newcomer on a tie); beds (typing, loading) are textures and are not counted; a hand entry is never dropped.
    PRIO = {'payoff': 7, 'gunshot': 7, 'title-card': 7, 'word-slam': 6, 'emphasis': 6, 'word-negative': 6, 'cut-in': 5, 'riser': 5,
            'slam': 4, 'pop': 3, 'row-tick': 3, 'riseIn': 2, 'slideIn': 2, 'slideOut': 2, 'flash': 2, 'word-flicker': 2, 'click': 2,
            'word': 1, 'drawOn': 0}
    cap = int(cfg.get('max_per_second', 3))
    src = lambda p: (p['gid'], p['file'])
    kept = []
    for x in sorted(out + ctx, key=lambda p: p['at']):          # stable: out's own order on a tie
        if x['cls'] == 'bed': kept.append(x); continue
        take = True
        while True:
            win_ = [p for p in kept if p['cls'] != 'bed' and x['at'] - p['at'] < 1.0]
            groups = {}
            for p in win_: groups.setdefault(src(p), []).append(p)
            if src(x) in groups or len(groups) < cap: break            # its own run, or room for another source
            # over-full: the lowest-priority SOURCE goes (x on a tie); a source with a hand entry in it stays
            cand = [g for g in list(groups.items()) + [(src(x), [x])] if not any(p.get('fixed') for p in g[1])]
            if not cand: break                                       # approved context only: it is never dropped
            lo = min(cand, key=lambda g: (min(PRIO.get(p['event'], 2) for p in g[1]), any(p['hand'] for p in g[1]), g[0] != src(x)))
            if any(p['hand'] for p in lo[1]): break
            if lo[0] == src(x):
                drops.append(f"{x['gid']} {x['event']} @{x['at']:.3f} ({x['note'][:30]}): {cap} sources already in the second before it"); take = False; break
            for p in lo[1]:
                drops.append(f"{p['gid']} {p['event']} @{p['at']:.3f} ({p['note'][:30]}): {cap} sources in the second around {x['at']:.3f}, the lowest-priority one"); kept.remove(p)
        if take: kept.append(x)
    out = [x for x in kept if not x.get('fixed')]
    # 3. A HAND ROW OWNS ITS FRAME. A hand entry written as the ANSWER to a call the parser could not bind
    #    becomes a DOUBLE CUE the day the parser learns to bind it: same graphic, same instant, two different
    #    sounds, both audible on their own layers. The doubling rule below cannot see it, because the two rows
    #    are different files, so the plan would ship both. The hand row is the copy approved by ear, so the
    #    automatic one goes — and the stand-in is named under ⚠ so it can be retired at source. The signature is
    #    the SAME FRAME, not the layer window: a cut-in or a riser under a graphic's first entrance is the layer
    #    stacking working as designed, and a bed under a transient is a texture.
    STRUCTURAL = {'cut-in', 'riser'}
    accent = lambda p: p['cls'] != 'bed' and p['event'] not in STRUCTURAL
    hands = [x for x in out if x['hand'] and accent(x)]
    kept = []
    for x in out:
        h_ = None if x['hand'] or not accent(x) else next(
            (h for h in hands if h['gid'] == x['gid'] and h['file'] != x['file'] and abs(h['at'] - x['at']) < 1e-3), None)
        if h_:
            drops.append(f"{x['gid']} {x['event']} @{x['at']:.3f} ({x['note'][:30]}): the hand row {h_['event']} owns that frame")
            warns.append(f"{x['gid']}: the hand row {h_['event']} @{h_['at']:.3f} stacks on the automatic {x['event']} "
                         f"on the same frame: the automatic row is dropped, but the parser binds that call now — "
                         f'retire the hand row, or give it "drop": ["{x["event"]}"] (sfx.md § Density)')
            continue
        kept.append(x)
    out = kept
    # the slices: in time order, after the drops, against the approved rows on a --merge, attack-aligned (reslice)
    aligned = reslice(out, ctx, EV, lib, T)
    win = cfg['layer_window_frames'] * F + 1e-4
    placed = []
    final = []
    for x in out:
        near = [p for p in placed if abs(p['at'] - x['at']) <= win]
        if any(p['file'] == x['file'] for p in near): continue      # one sound per frame; a second copy is a doubling, not a layer
        repeat = next((p for p in reversed(placed) if p['file'] == x['file']
                       and x['at'] < p['at'] + p['src_out'] - p['src_in']), None)
        if repeat is not None:
            # A repeating sound owns one layer. Retire its ringing tail now, so later
            # distinct sounds do not collide with phantom tails on several tracks.
            repeat['src_out'] = round(repeat['src_in'] + x['at'] - repeat['at'], 4)
            x['track'] = repeat['track']
            placed.append(x); final.append(x)
            continue
        x_end = x['at'] + (x['src_out'] - x['src_in'])
        used = {p['track'] for p in placed if p['file'] != x['file'] and p['at'] < x_end and x['at'] < p['at'] + (p['src_out'] - p['src_in'])}
        for tr in (TR['primary'], TR['layer2'], TR['layer3']):
            if tr not in used: x['track'] = tr; break
        else:
            warns.append(f"{x['gid']} {x['event']} @{x['at']}: four sounds on one frame, dropped"); continue
        placed.append(x); final.append(x)
    for i, x in enumerate(final): x['id'] = f's{i + 1:03d}'

    merged = None
    if merge is not None:
        final, merged, mw = merge_rows(approved, final, set(merge),
                                       [TR['primary'], TR['layer2'], TR['layer3']], win=win)
        warns += mw
        drops = [d for d in drops if d.split(' ')[0] in merge]      # only the re-planned graphics were re-scored
    for x in final:
        x.pop('_lv', None); x.pop('_dur', None)                     # add()'s own notes for reslice, never plan fields

    # the summed peak: cues were levelled one at a time; a moment where several land on a loud word must still stay
    # under -1 dBTP (sfx.md § The law 5)
    vspans, vgain = voice_spans_of(job, OFF)
    bed = music_bed(hf)                                             # the opt-in bed, when its pass has planned one
    # on --merge the approved rows keep their levels (merge_rows promises the very same objects, "kept as approved")
    keep = frozenset(id(r) for r in final) - frozenset(id(r) for r in merged) if merged is not None else frozenset()
    stacked = stack_levels(final, vspans, vgain, fixed=keep, bed=bed)
    vhow = under_how(vspans, vgain, bed)

    # cut sheet
    span = (final[-1]['at'] - final[0]['at']) if len(final) > 1 else 0
    lines = [f"# SFX plan — {job.name}", '',
             f"{len(final)} sounds over {span:.1f}s ({len(final) / span if span else 0:.2f}/s) · preset {preset_dir.relative_to(ROOT)} · fps {fps:.3f}"
             + (f" · {n_answered} ⚠ answered by sfx-hand.json" if n_answered else '')
             + (f" · slices attack-aligned: {', '.join(sorted(aligned))}" if aligned else ''), '',
             *([f"Merged {', '.join(merge)} into the approved plan ({len(merged)} row(s) re-planned against the current "
                f"placement); every other row is as approved.", ''] if merged is not None else []),
             TABLE_HEAD, '|---|---|---|---|---|---|---|---|---|---|']
    lines += [sheet_row(x) for x in final]
    if stacked:
        lines += ['', f'## lowered so stacked cues stay under {STACK_CEIL_DB:g} dBFS ({len(stacked)})', '',
                  f'Every stack of overlapping cues is mixed with what plays under it ({vhow}) and its TRUE peak read; '
                  'over the ceiling the deepest layer comes down first. sfx.md § The law 5.', ''] + [f'- {d}' for d in stacked]
    if voiced:
        lines += ['', f'## silent under the second voice ({len(voiced)})', '', 'Nothing over proof audio: only the call '
                  'card\'s own beats sound while transcript/voices.json\'s other voice plays (the preset\'s sfx.md law 3).',
                  ''] + [f'- {d}' for d in voiced]
    if drops:
        lines += ['', f'## dropped by the density rules ({len(drops)})', '', 'The stamp owns its beat (±%.1f s, same graphic) · %d sounds a second, no more (rolling 1 s, all graphics) · a hand row owns its frame. sfx.md § Density.' % (beat, cap), ''] + [f'- {d}' for d in drops]
    if warns:
        hint = ('This parser never guesses a time it cannot bind (a call inside a loop it cannot size, an argument it '
                'cannot evaluate, a `reveal` with no literal text). Enter each line by hand in `hf-graphics/sfx-hand.json`, '
                'a list of `{"gid", "event", "at": <comp-relative seconds>}` rows (`"word": <text>` places it on that span '
                'instead of `at`; `dur`, `level_db`, `note`, `drop` optional), then re-run this script. A graphic that '
                'makes no sound by design takes `{"gid": "<id>", "silent": true}`.')
        lines += ['', '## ⚠ needs a hand entry', '', hint, ''] + [f'- {w}' for w in warns]
    md = '\n'.join(lines) + '\n'
    if dry:
        print(md); return
    if merged is not None:
        bak = hf / f"sfx-plan.pre-merge-{time.strftime('%Y%m%d-%H%M%S')}.json"
        shutil.copy2(hf / 'sfx-plan.json', bak)
        write_plan(hf, final, md)
        write_meta(hf / 'sfx-plan.json', hf, gids=set(merge))
        print(f"merged {', '.join(merge)}: {len(merged)} row(s) re-planned, {len(final) - len(merged)} kept as approved; backup {bak.name}")
    else:
        write_plan(hf, final, md, candidate='--candidate' in a)
        write_meta(hf / ('sfx-plan.candidate.json' if '--candidate' in a else 'sfx-plan.json'), hf, until=None)   # a whole plan: no window
        print(f"scored {len(final)} rows; {len(warns)} ⚠ ({n_answered} answered by sfx-hand.json); {len(drops)} dropped by the density rules"
              + (f"; {len(voiced)} silent under the second voice" if voiced else '') + " (listed in the cut sheet)")
    for w in warns: print('  ⚠ ' + w)
    if warns: print(f"  -> hand-enter these in {hf / 'sfx-hand.json'}: [{{\"gid\", \"event\", \"at\": <comp-relative seconds>}}], then re-run")
    return 0


if __name__ == '__main__':
    sys.exit(main())
