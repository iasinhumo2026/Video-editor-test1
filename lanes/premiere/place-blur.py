#!/usr/bin/env python3
"""place-blur.py: the privacy region blur on the Premiere lane — the boxes a sweep found, blurred in-app.

  uv run lanes/premiere/place-blur.py projects/<job> --plan            # the layers, touch nothing
  uv run lanes/premiere/place-blur.py projects/<job> --apply           # remove this source's blur clips, lay fresh, save
  uv run lanes/premiere/place-blur.py projects/<job> --remove          # take this source's blur layers off
  ... --hits <file>    the hit map (default: <job>/review/pii-scan.json, from workflows/pii-scan.py; a job that
                       plays several raws has one review/pii-scan-<stem>.json per raw: run once per map)
  ... --source <name>  the SCREEN-RECORDING media to blur (default: the raw that sweep read); a
                       substring of the clip's media path is enough
  ... --track N        first blur track, 0-based (default: the first empty video track, above everything)

The WHAT is one bullet in lanes/premiere/lab-notes.md § a region blur; this is the HOW. Each box gets a
DUPLICATE of the V1 footage clip on its own track above the graphics, carrying the Impact Gaussian Blur
(Amount 3, Edge Behavior 2 — the Legacy blur at 40 reads as a glow) then Crop, so only the boxed area
shows, blurred. A box that moves gets crop keyframes on the frames it moves. NOT an adjustment layer:
a cropped adjustment layer renders BLACK outside its box in Premiere 26's live Program monitor while
exportFrame shows it correct, so the proof is a window grab, never a frame export.

Boxes are read in SOURCE frames and mapped through a LIVE readback of V1, so a hand edit since the EDL
is honoured. The blur is laid ONLY on the clips whose media IS the screen recording: a camera-angle clip
has no screen, and a blanket lay puts a blurred box on the creator's face (23 of them did, 2026-09-19).
When no V1 clip matches the source, this refuses rather than widening the match. --apply and --remove
take off only the blur clips laid over THIS source (a blur clip is a duplicate of its footage, so its
media path names it): one map's apply used to remove every PRIVACY BLUR clip, so blurring a job's
second raw wiped the first raw's blur (2026-10-13).

Why it lives here (2026-09-19): the worked driver was written inside a job folder, with that job's path,
that job's filename regex and that job's frame rate baked in — one archive.sh run from being lost.
"""
import argparse, json, math, os, shlex, subprocess, sys
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from job_guard import require_job_project   # lanes/premiere/job_guard.py: the active project must be this job's
from pes import es, paged                   # lanes/premiere/pes.py: the bridge's one output contract

BRIDGE = Path(__file__).resolve().parent / 'premiere-bridge.mjs'
TICKS = 254016000000
NAME = 'PRIVACY BLUR'
PADX, PADT, PADB = 36, 30, 39   # crop pad past the text, source px (the creator's hand-set clip, 2026-09-19)
AMOUNT, THICKNESS, EDGE = 3, 3, 2
GAP = 8                         # OCR dropout, in source frames, that is interpolated across rather than split
PAGE = 40                       # clips per readback call: a full media path per row blows the 64 KB return cap


# ── the sweep's hit map ──────────────────────────────────────────────────────
def load_hits(path):
    """{source frame: [[x0,y0,x1,y1,fragment], ...]} for the frames that hit. OCR drops a box for a frame
    or two (a cursor crossing it, motion blur); a gap up to GAP frames is interpolated between the boxes
    on either side, or the blur flickers off over the thing it is hiding."""
    hits = {int(k): v for k, v in json.load(open(path, encoding='utf-8')).items() if v}
    fr = sorted(hits)
    for a, b in zip(fr, fr[1:]):
        if 1 < b - a <= GAP:
            for n in range(a + 1, b):
                k = (n - a) / (b - a); fill = []
                for bx in hits[a]:
                    near = min(hits[b], key=lambda q: abs(q[0] - bx[0]) + abs(q[1] - bx[1]))
                    if abs(near[0] - bx[0]) + abs(near[1] - bx[1]) < 400:
                        fill.append([round(bx[i] + (near[i] - bx[i]) * k) for i in range(4)] + [bx[4]])
                    else:
                        fill.append(bx)
                hits[n] = fill
    return hits


def tracks_of(hits):
    """Link boxes frame to frame into tracks — one instance of the hidden thing, over time."""
    live, done = [], []
    for n in sorted(hits):
        nxt, used = [], set()
        for tr in live:
            ln, lb = tr[-1]
            if n - ln > 1: done.append(tr); continue
            best = None
            for i, b in enumerate(hits[n]):
                if i in used: continue
                d = abs(b[0] - lb[0]) + abs(b[1] - lb[1])
                if d < 350 and abs((b[2] - b[0]) - (lb[2] - lb[0])) < 0.5 * (lb[2] - lb[0]) + 40 and (best is None or d < best[0]):
                    best = (d, i)
            if best: used.add(best[1]); tr.append((n, hits[n][best[1]])); nxt.append(tr)
            else: done.append(tr)
        for i, b in enumerate(hits[n]):
            if i not in used: nxt.append([(n, b)])
        live = nxt
    return [dict(t) for t in done + live]


def crop_of(b, sw, sh):
    """A box in source pixels -> Crop's Left/Top/Right/Bottom percentages."""
    x0, y0, x1, y1 = b[0] - PADX, b[1] - PADT, b[2] + PADX, b[3] + PADB
    return [round(max(0, x0) / sw * 100, 3), round(max(0, y0) / sh * 100, 3),
            round(max(0, sw - x1) / sw * 100, 3), round(max(0, sh - y1) / sh * 100, 3)]


def keys_for(crops):
    """Crop keys: one per change, each held until the frame before the next (a linear tween between two
    different boxes would slide the blur off the thing it hides)."""
    ks = sorted(crops); out = [(ks[0], crops[ks[0]])]
    for k in ks[1:]:
        if crops[k] != crops[k - 1]:
            if out[-1][0] != k - 1: out.append((k - 1, crops[k - 1]))
            out.append((k, crops[k]))
    return out


# ── the timeline ─────────────────────────────────────────────────────────────
# usedTracks skips this tool's own blur clips: it is read BEFORE --apply removes them, so counting them
# put every re-run one track higher and left the old blur track behind empty
SEQ_ES = r"""(function(){
  var seq = app.project.activeSequence; if (!seq) return "ERROR: no active sequence";
  var vt = seq.videoTracks, used = 0, NAME = %s;
  for (var t = 0; t < vt.numTracks; t++)
    for (var i = 0; i < vt[t].clips.numItems; i++) if (vt[t].clips[i].name !== NAME) { used = t + 1; break; }
  return JSON.stringify({ticks: Number(seq.timebase), videoTracks: vt.numTracks, usedTracks: used,
                         audioTracks: seq.audioTracks.numTracks, name: seq.name});
})()"""

V1_ES = r"""(function(){
  var seq = app.project.activeSequence; if (!seq) return "ERROR: no active sequence";
  var N0 = %d, N1 = %d, tr = seq.videoTracks[0], out = [];
  function comp(c, n){ for (var k = 0; k < c.components.numItems; k++) if (c.components[k].displayName === n) return c.components[k]; return null; }
  function prop(cm, n){ for (var q = 0; q < cm.properties.numItems; q++) if (cm.properties[q].displayName === n) return cm.properties[q]; return null; }
  for (var i = N0; i < tr.clips.numItems; i++) {
    if (out.length >= N1 - N0) break;
    var c = tr.clips[i], sc = 100;
    try { sc = prop(comp(c, "Motion"), "Scale").getValue(); } catch (e) {}
    out.push({i: i, start: c.start.seconds, end: c.end.seconds, srcIn: c.inPoint.seconds, scale: sc,
              path: c.projectItem ? c.projectItem.getMediaPath() : ""});
  }
  return JSON.stringify(out);
})()"""

REMOVE_ES = r"""(function(){
  var seq = app.project.activeSequence, NAME = %s, SRC = %s, out = [];
  for (var t = 0; t < seq.videoTracks.numTracks; t++) { var tr = seq.videoTracks[t];
    for (var i = tr.clips.numItems - 1; i >= 0; i--) { var c = tr.clips[i];
      if (c.name !== NAME) continue;
      var p = ""; try { p = c.projectItem ? c.projectItem.getMediaPath() : ""; } catch (e) {}
      if (p.indexOf(SRC) < 0) continue;     // another source's blur: a second raw's map never wipes the first's
      var ok = false;
      try { ok = c.remove(false, false); } catch (e) { ok = false; }
      out.push("V" + (t + 1) + "@" + c.start.seconds.toFixed(3) + (ok ? "" : " (FAILED)")); } }
  return JSON.stringify(out);
})()"""

LAY_ES = r"""(function(){
var seq = app.project.activeSequence;
var TR = %(track)d, K0 = %(k0)d, K1 = %(k1)d, FT = %(ft)d, KEYS = %(keys)s, VI = %(v1)d, SCALE = %(scale)s, NAME = %(name)s;
function T(k){ var t = new Time(); t.ticks = String(k * FT); return t; }
var src = seq.videoTracks[0].clips[VI], item = src.projectItem;
app.enableQE();
var addedTracks = 0;
while (seq.videoTracks.numTracks <= TR) { qe.project.getActiveSequence().addTracks(1, seq.videoTracks.numTracks, 0, 0, 0, 0, 0); addedTracks++;
  if (addedTracks > 16) return "ERROR: could not provision V" + (TR + 1); }
// The audio state BEFORE the write, as a SIGNATURE per clip, not just its start: an AV overwriteClip
// on a video track rewrites the audio under it (lanes/premiere/lab-notes.md § NEVER overwriteClip an AV
// project item onto an AUDIO track — "the same call on V1 rewrites A1 underneath it, a frame early,
// chain gone"). A rewritten A1 clip keeps its start tick, so a start-only map calls the damage untouched
// and the takeback below leaves it. end + in-point + effect count is what moves when it happens.
var audioBefore = seq.audioTracks.numTracks, before = {}, beforeN = 0;
for (var a = 0; a < seq.audioTracks.numTracks; a++)
  for (var i = 0; i < seq.audioTracks[a].clips.numItems; i++) { var bc = seq.audioTracks[a].clips[i];
    before[a + "@" + bc.start.ticks] = String(bc.end.ticks) + "/" + String(bc.inPoint.ticks) + "/" + bc.components.numItems;
    beforeN++; }
var tr = seq.videoTracks[TR], vBefore = tr.clips.numItems;
var st = K0 * FT / 254016000000, en = K1 * FT / 254016000000;
// V1's source position on frame K0, in TICKS: the same sum in float seconds lands one tick under the frame
// on about one layer in seven, and Premiere renders the frame before (lanes/premiere/lab-notes.md § a head trim)
var SINT = Number(src.inPoint.ticks) + (K0 * FT - Number(src.start.ticks)), sin = SINT / 254016000000;
item.setInPoint(sin, 4); item.setOutPoint(sin + (en - st) + 1e-4, 4);
tr.overwriteClip(item, st + 1e-4);
item.clearInPoint(4); item.clearOutPoint(4);
// overwriteClip lays the footage item's LINKED AUDIO too: take back every audio clip that was not there
// before, or a duplicate of the dialogue plays under the mix (and count any track it provisioned).
var gone = 0;
for (var a = 0; a < seq.audioTracks.numTracks; a++)
  for (var i = seq.audioTracks[a].clips.numItems - 1; i >= 0; i--) { var ac = seq.audioTracks[a].clips[i];
    if (!before[a + "@" + ac.start.ticks]) { ac.remove(false, false); gone++; } }
// ... and then the dialogue that WAS there is checked against its signature. This is the damage no count
// of removed clips can see, and it is not undoable, so it refuses in the same second, unsaved.
var kept = 0, hurt = [];
for (var a = 0; a < seq.audioTracks.numTracks; a++)
  for (var i = 0; i < seq.audioTracks[a].clips.numItems; i++) { var ac2 = seq.audioTracks[a].clips[i];
    var sg = before[a + "@" + ac2.start.ticks];
    if (!sg) continue;
    kept++;
    if (sg !== String(ac2.end.ticks) + "/" + String(ac2.inPoint.ticks) + "/" + ac2.components.numItems)
      hurt.push("A" + (a + 1) + "@" + ac2.start.seconds.toFixed(3)); }
if (kept !== beforeN || hurt.length)
  return "ERROR: the lay REWROTE the audio under it: " + beforeN + " audio clip(s) before, " + kept
       + " unchanged" + (hurt.length ? ", altered: " + hurt.join(", ") : "")
       + ". NOT saved — close the project WITHOUT saving (a scripted edit is not in the undo stack) and "
       + "re-lay the dialogue from the EDL before re-running.";
var clip = null;
for (var i = 0; i < tr.clips.numItems; i++) if (Math.abs(tr.clips[i].start.seconds - st) < 0.01) clip = tr.clips[i];
if (!clip) return "ERROR: the blur clip did not land on V" + (TR + 1) + " at " + st;
// the lane is empty over this span by construction, so the lay ADDS a clip; anything else overwrote one
if (tr.clips.numItems !== vBefore + 1)
  return "ERROR: V" + (TR + 1) + " went " + vBefore + " -> " + tr.clips.numItems + " clip(s): this lay "
       + "overwrote something instead of filling empty track. NOT saved — close without saving.";
// Premiere can floor the in-point a source frame off: fix it PER CLIP from V1's own mapping and read it
// back. A blanket nudge on every layer fixes the first one and breaks the next.
if (Number(clip.inPoint.ticks) !== SINT) { var ti = new Time(); ti.ticks = String(SINT); clip.inPoint = ti; }
clip.end = T(K1);
try { clip.name = NAME; } catch (e) {}
function comp(n){ for (var c = 0; c < clip.components.numItems; c++) if (clip.components[c].displayName === n) return clip.components[c]; return null; }
function prop(cm, n){ for (var p = 0; p < cm.properties.numItems; p++) if (cm.properties[p].displayName === n) return cm.properties[p]; return null; }
// the duplicate must frame EXACTLY like the clip under it, so the scale is copied off V1, never assumed
try { prop(comp("Motion"), "Scale").setValue(SCALE, 1); } catch (e) {}
var qt = qe.project.getActiveSequence().getVideoTrackAt(TR), q = null;
for (var j = 0; j < qt.numItems; j++) { var it = qt.getItemAt(j);
  if (it.type === "Clip" && Math.abs(it.start.secs - st) < 0.01) q = it; }
if (!q) return "ERROR: no QE item for the blur clip at " + st;
q.addVideoEffect(qe.project.getVideoEffectByName("Crop"));            // QE PREPENDS, so Crop first ...
q.addVideoEffect(qe.project.getVideoEffectByName("Gaussian Blur"));   // ... lands the chain as Blur > Crop
var gb = comp("Gaussian Blur");
if (!gb || gb.matchName !== "AE.Impact_Blur_FX") return "ERROR: the Gaussian Blur that landed is not the Impact one (matchName " + (gb ? gb.matchName : "none") + ")";
prop(gb, "Amount").setValue(%(amount)s, 1); prop(gb, "Thickness").setValue(%(thickness)s, 1); prop(gb, "Edge Behavior").setValue(%(edge)s, 1);
var cr = comp("Crop"), names = ["Left", "Top", "Right", "Bottom"], P = [];
for (var n = 0; n < 4; n++) P.push(prop(cr, names[n]));
var inT = clip.inPoint.ticks * 1;     // key times are in the clip's OWN media time
if (KEYS.length === 1) { for (var n = 0; n < 4; n++) P[n].setValue(KEYS[0][1][n], 1); }
else { for (var n = 0; n < 4; n++) { P[n].setTimeVarying(true);
  for (var m = 0; m < KEYS.length; m++) { var kt = new Time(); kt.ticks = String(inT + (KEYS[m][0] - K0) * FT);
    P[n].addKey(kt); P[n].setValueAtKey(kt, KEYS[m][1][n], 1); } } }
var order = []; for (var c = 0; c < clip.components.numItems; c++) order.push(clip.components[c].displayName);
return JSON.stringify({start: clip.start.seconds, end: clip.end.seconds, srcIn: clip.inPoint.seconds, want: sin,
                       srcInTicks: String(clip.inPoint.ticks), wantTicks: String(SINT),
                       audioRemoved: gone, audioTracksAdded: seq.audioTracks.numTracks - audioBefore,
                       videoTracksAdded: addedTracks, order: order.join(">")});
})()"""


def save_project(why):
    """The saved .prproj is the ONLY rollback for a scripted edit, and the only proof the laid blur
    persisted — so a save that did not happen is never reported as one. A silently-ignored save is how a
    run says 'saved' over a project that still only exists in Premiere's memory."""
    r = subprocess.run(['node', str(BRIDGE), 'save_project'], capture_output=True, text=True)
    bad = r.returncode or '"success": false' in r.stdout or '"success":false' in r.stdout
    if bad:
        sys.exit(f'✗ save_project failed ({why}):\n' + (r.stderr or r.stdout or '').strip()[-800:])
    return True


class Blurrer:
    def __init__(self, job, hits_path=None, source=None, track=None):
        self.job = Path(job).resolve()
        self.hits_p = Path(hits_path) if hits_path else self.job / 'review' / 'pii-scan.json'
        if not self.hits_p.exists():
            # a command to paste: forward slashes (Git Bash drops the separators of a backslashed path), quoted
            shown = shlex.quote((Path(os.path.relpath(self.job)) if self.job.is_relative_to(Path.cwd().resolve())
                                 else self.job).as_posix())
            maps = sorted(p.name for p in (self.job / 'review').glob('pii-scan-*.json') if '.meta' not in p.suffixes)
            sys.exit(f'no hit map at {self.hits_p}: run `uv run workflows/pii-scan.py {shown} --needle "<string>"` '
                     'first and confirm its hits by eye off review/pii-hits/sheet.jpg'
                     + (f'\n  review/ holds per-video maps (a job that plays several raws writes one per raw): pass '
                        f'--hits for each of {", ".join(maps)}' if maps and not hits_path else ''))
        meta_p = self.hits_p.with_suffix('.meta.json')
        self.meta = json.loads(meta_p.read_text(encoding='utf-8')) if meta_p.exists() else {}
        self.src_w, self.src_h = self.meta.get('source') or (0, 0)
        self.src_fps = float(self.meta.get('fps') or 0)
        # the source is NAMED, never inferred from "the clips that look like footage": the sweep read one
        # file and its boxes are in that file's pixels, so that file is the only thing they may be laid on
        self.source = source or (os.path.basename(self.meta.get('raw') or '') or None)
        if not self.source:
            sys.exit(f'{meta_p.name} carries no `raw`, so the screen-recording source is unknown: pass '
                     '--source <media name>. This never lays on every V1 clip — a camera-angle clip has no screen.')
        if not (self.src_w and self.src_h and self.src_fps):
            sys.exit(f'{meta_p.name} is missing source/fps: re-run workflows/pii-scan.py, which writes both '
                     '(the boxes are in source pixels at the source rate and cannot be mapped without them)')
        self.track = track
        require_job_project(es, self.job)
        self.seq = json.loads(es(SEQ_ES % json.dumps(NAME)))
        self.ft = int(self.seq['ticks'])          # ticks per SEQUENCE frame, read off the sequence
        self.fs = self.ft / TICKS

    def v1(self):
        """Every V1 clip, paged (a media path per row hits the return cap on a long timeline)."""
        return paged(lambda n0, n1: V1_ES % (n0, n1), size=PAGE)

    def base_track(self):
        """The blur rides ABOVE everything: the first empty video track, unless --track names one."""
        return self.track if self.track is not None else self.seq['usedTracks']

    def plan(self):
        boxes = tracks_of(load_hits(self.hits_p))
        clips = self.v1()
        mine = [c for c in clips if self.source in (c['path'] or '')]
        if not mine:
            sys.exit(f"no V1 clip's media matches --source {self.source!r} ({len(clips)} clip(s) on V1: "
                     + ', '.join(sorted({os.path.basename(c['path'] or '?') for c in clips})) + ')\n'
                     '  Nothing laid: a blanket lay would put a blurred box on the creator\'s face.')
        layers = []
        for c in mine:
            k0, k1 = round(c['start'] / self.fs), round(c['end'] / self.fs)
            for tr in boxes:
                fr = {}
                for k in range(k0, k1):
                    s = c['srcIn'] + (k * self.fs - c['start'])          # source seconds on this timeline frame
                    n = math.floor(s * self.src_fps + 1e-6)
                    bx = [tr[m] for m in (n - 1, n, n + 1) if m in tr]   # the conform can land a frame either side
                    if bx:
                        fr[k] = [min(b[0] for b in bx), min(b[1] for b in bx), max(b[2] for b in bx), max(b[3] for b in bx)]
                if not fr: continue
                ks = sorted(fr)                                          # split on gaps inside this V1 clip
                runs = [[ks[0], ks[0]]]
                for k in ks[1:]:
                    if k - runs[-1][1] <= 1: runs[-1][1] = k
                    else: runs.append([k, k])
                for a, b in runs:
                    crops = {k: crop_of(fr[k], self.src_w, self.src_h) for k in range(a, b + 1)}
                    layers.append({'k0': a, 'k1': b + 1, 'keys': keys_for(crops), 'v1': c['i'], 'scale': c['scale'],
                                   'frag': next(iter(tr.values()))[4]})
        lanes = []                                                       # greedy lanes so overlapping layers stack
        for L in sorted(layers, key=lambda l: l['k0']):
            for i, end in enumerate(lanes):
                if end <= L['k0']: lanes[i] = L['k1']; L['lane'] = i; break
            else: lanes.append(L['k1']); L['lane'] = len(lanes) - 1
        return layers, len(lanes), len(mine), len(clips)

    def report(self, layers, lanes, mine, total):
        base = self.base_track()
        for L in layers:
            print(f"V{base + 1 + L['lane']}  {L['k0'] * self.fs:9.3f} → {L['k1'] * self.fs:9.3f}  "
                  f"keys {len(L['keys']):3d}  V1 clip {L['v1']}  {L['frag']}")
        print(f"{len(layers)} layer(s) on {lanes} track(s) from V{base + 1} · source {self.source} "
              f"({mine} of {total} V1 clips) · {self.seq['name']} at {1 / self.fs:.5f} fps")

    def remove(self):
        gone = json.loads(es(REMOVE_ES % (json.dumps(NAME), json.dumps(self.source))))
        failed = [g for g in gone if g.endswith('(FAILED)')]
        print(f"removed {len(gone) - len(failed)} {NAME} clip(s) over {self.source}"
              + (f", {len(failed)} FAILED: {failed}" if failed else ''))
        return gone, failed

    def apply(self):
        layers, lanes, mine, total = self.plan()
        self.report(layers, lanes, mine, total)
        if not layers:
            print('nothing to blur: the sweep found no box inside a clip of this source'); return True
        # the saved .prproj is the rollback: a scripted edit is not in Premiere's undo stack
        # (lanes/premiere/lab-notes.md § the lay command saves before the write). It is checked, because a
        # rollback that did not get written is worse than none: the run would go ahead believing in it.
        save_project('the pre-write rollback — nothing was laid')
        gone, failed = self.remove()
        if failed:
            sys.exit(f'✗ {len(failed)} old blur clip(s) would not remove: {failed}\n'
                     '  Nothing was laid and nothing saved — clear them by hand and re-run.')
        base, laid, audio = self.base_track(), [], 0
        for L in layers:
            try:
                r = es(LAY_ES % {'track': base + L['lane'], 'k0': L['k0'], 'k1': L['k1'], 'ft': self.ft,
                                 'keys': json.dumps([[k, c] for k, c in L['keys']]), 'v1': L['v1'],
                                 'scale': repr(float(L['scale'])), 'name': json.dumps(NAME),
                                 'amount': AMOUNT, 'thickness': THICKNESS, 'edge': EDGE})
            except SystemExit:
                # an ERROR: from the lay exits inside pes.es, so the layers that DID land have to be named
                # here or the next command starts from a timeline nobody described
                for x in laid: print('+ ' + x)
                print(f"✗ STOPPED on the layer at {L['k0'] * self.fs:.3f}s · {len(laid)} of {len(layers)} "
                      "layer(s) are on the timeline and the project was NOT saved: close it without saving, "
                      "or run --remove and re-run --apply.", file=sys.stderr)
                raise
            bad = None
            g = json.loads(r)
            if not g['order'].endswith('Gaussian Blur>Crop'):
                bad = f"effect order is {g['order']}, want ... Gaussian Blur>Crop"
            elif int(g['srcInTicks']) != int(g['wantTicks']):   # ticks, exactly: one tick under renders the frame before
                bad = f"source in {g['srcInTicks']} ticks, want {g['wantTicks']} ({g['srcIn']:.4f}s)"
            elif abs(g['start'] - L['k0'] * self.fs) > 0.5 * self.fs or abs(g['end'] - L['k1'] * self.fs) > 0.5 * self.fs:
                bad = f"landed {g['start']:.4f} → {g['end']:.4f}, want {L['k0'] * self.fs:.4f} → {L['k1'] * self.fs:.4f}"
            if bad:
                # every layer that DID land is named, because the next command has to start from what is
                # really on the timeline — and nothing has been saved, so closing without saving undoes it
                for x in laid: print('+ ' + x)
                sys.exit(f"✗ STOPPED on the layer at {L['k0'] * self.fs:.3f}s: {bad}\n"
                         f"  {len(laid)} of {len(layers)} layer(s) are on the timeline and the project was NOT "
                         f"saved: close it without saving, or run --remove and re-run --apply.")
            audio += g['audioRemoved']
            laid.append(f"V{base + L['lane'] + 1} {g['start']:.3f} → {g['end']:.3f}  keys {len(L['keys']):3d}  {L['frag']}")
            if g['audioTracksAdded']:
                print(f"⚠ the lay provisioned {g['audioTracksAdded']} EMPTY audio track(s) — delete them by hand, "
                      "or they stay in the project forever")
        for x in laid: print('+ ' + x)
        print(f'{len(laid)} layer(s) laid · {audio} linked audio clip(s) taken back off')
        save_project(f'{len(laid)} layer(s) ARE on the timeline but only in Premiere\'s memory')
        print('saved — now confirm the blur on a WINDOW GRAB of the Program monitor '
              '(./workflows/window-grab.sh "Adobe Premiere" out.png), never a frame export')
        return True


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('job', nargs='?')
    ap.add_argument('--hits'); ap.add_argument('--source'); ap.add_argument('--track', type=int)
    ap.add_argument('--plan', action='store_true'); ap.add_argument('--apply', action='store_true')
    ap.add_argument('--remove', action='store_true')
    a, rest = ap.parse_known_args()
    if not a.job or rest or not (a.plan or a.apply or a.remove):
        sys.exit(__doc__ + (f'\nunknown argument(s): {rest}' if rest else ''))
    b = Blurrer(a.job, a.hits, a.source, a.track)
    if a.remove:
        gone, failed = b.remove()
        # only a removal that actually took something off is saved: nothing changed means the save would
        # only overwrite the rollback, and a removal that FAILED must leave that rollback on disk
        if gone and not failed:
            save_project('the removal is only in Premiere\'s memory')
            print('saved')
        return 1 if failed else 0
    if a.apply:
        return 0 if b.apply() else 1
    b.report(*b.plan())
    return 0


if __name__ == '__main__':
    sys.exit(main())
