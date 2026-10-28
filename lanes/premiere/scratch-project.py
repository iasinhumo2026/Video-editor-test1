#!/usr/bin/env python3
"""scratch-project.py: a throwaway Premiere job to prove a lane write in, and the way back out of it.

  uv run lanes/premiere/scratch-project.py create <scratch>/projects/<name> [--fps 24000/1001] [--size 1920x1080]
                                                  [--seconds 12] [--segments 4]
  uv run lanes/premiere/scratch-project.py close <scratch>/projects/<name>

create
  1. writes <dir>/raw/grey.mp4 (workflows/grey-source.py: every frame names itself; a tone, so the replay lays A1
     too; the write reads its own clip back and stops unless every frame decodes to its own number) and
     <dir>/transcript/cuts.json: N segments with a killed gap before each, so every cut jumps in the source, and a
     tail after the last, so no out-point sits on the media's end
  2. records the ACTIVE project (its path, then its active sequence id) in <dir>/.previous-project
  3. app.newProject(<dir>/premiere/<name>.prproj), then reads app.project.path back. A new project that did not
     become the active one is a STOP, never a saveAs: a saveAs lands on whatever IS active, which is the creator's
     own project (the engine's create_project falls back to exactly that)
  4. imports the grey source and makes a sequence named <name> from it (its rate and size), empties every track,
     setSettings to the requested size when it differs (preview size included, lanes/premiere/lab-notes.md, the
     16:9-raw-as-9:16 lock), saves, and runs the job guard on it
  5. replays cuts.json onto V1 with `premiere-bridge.mjs replay` (the lane's own replay, THE GUARD included), reads
     V1 and A1 back, and prints what to prove: each segment's sequence frames beside the source frames they must
     show, and an --at list of every joint for lanes/premiere/frame-proof.py

close
  closeDocument(0, 0) on THAT project only (found by its path; nothing saved, no prompt), then openSequence on the
  recorded project's recorded sequence (else its first) to make it the active one again. The folder stays as the
  evidence; delete it by hand.

<dir> must be NEW, its parent a folder named `projects` (the guard knows a job as the child of `projects/`), and
OUTSIDE this repo's own projects/, so a throwaway never lands beside, or over, a real job.

WHY (2026-09-22): proving the `lay` fix needed a throwaway project built by hand ExtendScript, a hand-made grey
source and a scratch frame matcher; none of it was in the repo, so every UNPROVEN LIVE entry waited on rebuilding it.
"""
import argparse, importlib.util, json, os, subprocess, sys
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
import pes                                                    # noqa: E402  (the ONE bridge runner)
from job_guard import require_job_project                     # noqa: E402

_spec = importlib.util.spec_from_file_location('grey_source', REPO / 'workflows' / 'grey-source.py')
grey = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grey)

TPS = 254016000000                                            # Premiere ticks per second
MEDIA = 'grey.mp4'
PREV = '.previous-project'

STATE_ES = r"""(function(){
var o = {path: app.project ? String(app.project.path) : "", seq: "", open: []};
try { if (app.project && app.project.activeSequence) o.seq = String(app.project.activeSequence.sequenceID); } catch (e) {}
try { for (var i = 0; i < app.projects.numProjects; i++) o.open.push(String(app.projects[i].path)); } catch (e) {}
return JSON.stringify(o);
})()"""

NEW_ES = r"""(function(){
var P = @PATH@;
var made = app.newProject(P);
return JSON.stringify({made: !!made, path: app.project ? String(app.project.path) : ""});
})()"""

BUILD_ES = r"""(function(){
var P = @PATH@, MEDIA = @MEDIA@, NAME = @NAME@, W = @W@, H = @H@;
if (!app.project || String(app.project.path) !== P)
  return "ERROR: the active project is " + (app.project ? app.project.path : "none") + ", not " + P;
var root = app.project.rootItem;
function find(bin, name){
  for (var i = 0; i < bin.children.numItems; i++) {
    var c = bin.children[i];
    if (c.name === name) return c;
    if (c.type === ProjectItemType.BIN) { var f = find(c, name); if (f) return f; }
  }
  return null;
}
var base = MEDIA.replace(/^.*[\\\/]/, "");
if (!app.project.importFiles([MEDIA], true, root, false)) return "ERROR: importFiles returned false for " + MEDIA;
var item = find(root, base);
if (!item) return "ERROR: " + base + " is not in the project after the import";
var seq = app.project.createNewSequenceFromClips(NAME, [item], root);
if (!seq) return "ERROR: createNewSequenceFromClips returned nothing";
app.project.openSequence(seq.sequenceID);
seq = app.project.activeSequence;
if (!seq || String(seq.name) !== NAME) return "ERROR: the new sequence " + NAME + " is not the active one";
var lists = [seq.videoTracks, seq.audioTracks], removed = 0, left = 0;
for (var l = 0; l < 2; l++)
  for (var t = 0; t < lists[l].numTracks; t++)
    for (var k = lists[l][t].clips.numItems - 1; k >= 0; k--) { lists[l][t].clips[k].remove(false, false); removed++; }
var st = seq.getSettings(), resized = false;
if (Number(st.videoFrameWidth) !== W || Number(st.videoFrameHeight) !== H) {
  st.videoFrameWidth = W; st.videoFrameHeight = H; st.previewFrameWidth = W; st.previewFrameHeight = H;
  seq.setSettings(st);
  st = seq.getSettings();
  resized = true;
}
for (var l2 = 0; l2 < 2; l2++)
  for (var t2 = 0; t2 < lists[l2].numTracks; t2++) left += lists[l2][t2].clips.numItems;
var tpf = 0;
try { tpf = Number(seq.timebase); } catch (e) {}
if (!(tpf > 0)) { try { tpf = Math.round(st.videoFrameRate.seconds * 254016000000); } catch (e) {} }
app.project.save();
return JSON.stringify({seq: String(seq.name), id: String(seq.sequenceID), tpf: tpf, w: Number(st.videoFrameWidth),
  h: Number(st.videoFrameHeight), removed: removed, left: left, resized: resized, item: String(item.name)});
})()"""

READ_ES = r"""(function(){
var s = app.project.activeSequence;
if (!s) return "ERROR: no active sequence";
function rd(tr){ var o = []; for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i];
  o.push([String(c.start.ticks), String(c.end.ticks), String(c.inPoint.ticks)]); } return o; }
return JSON.stringify({name: String(s.name), v1: rd(s.videoTracks[0]), a1: s.audioTracks.numTracks ? rd(s.audioTracks[0]) : []});
})()"""

CLOSE_ES = r"""(function(){
var P = @PATH@, BACK = @BACK@, SEQ = @SEQ@;
var closed = false, back = null, how = "";
// No path, no close: an untitled project's path can read "" too, and it is not the throwaway.
if (P) for (var i = 0; i < app.projects.numProjects; i++)
  if (String(app.projects[i].path) === P) { app.projects[i].closeDocument(0, 0); closed = true; break; }
if (BACK) for (var j = 0; j < app.projects.numProjects; j++) if (String(app.projects[j].path) === BACK) back = app.projects[j];
if (back) {
  var id = "";
  for (var k = 0; k < back.sequences.numSequences; k++) if (String(back.sequences[k].sequenceID) === SEQ) id = SEQ;
  if (!id && back.sequences.numSequences) id = String(back.sequences[0].sequenceID);
  if (id) { back.openSequence(id); how = (id === SEQ) ? "its recorded sequence" : "its first sequence"; }
  else how = "no sequence to open";
}
var open = [];
for (var m = 0; m < app.projects.numProjects; m++) open.push(String(app.projects[m].path));
return JSON.stringify({closed: closed, back: back ? String(back.path) : "", how: how,
  active: app.project ? String(app.project.path) : "", open: open});
})()"""


def fill(es, **kw):
    for k, v in kw.items():
        es = es.replace(f'@{k}@', json.dumps(v))
    return es


def same(a, b):
    return bool(a) and bool(b) and os.path.realpath(a) == os.path.realpath(b)


def check_dir(d):
    """The throwaway's folder: new, a child of a folder named `projects`, never inside this repo's projects/."""
    d = Path(d).resolve()
    if d.parent.name != 'projects':
        return f'{d}: the parent folder must be named projects (the job guard finds a job as the child of projects/)'
    if d.is_relative_to((REPO / 'projects').resolve()):
        return f"{d}: inside this repo's projects/, beside the real jobs; put the throwaway under a scratch folder"
    if d.exists():
        return f'{d}: already exists; a throwaway is built fresh, never over a folder'
    return None


def plan(frames, n):
    """N kept segments over a `frames`-long source, a killed gap before each and a tail after the last (so no
    out-point sits on the media's end, where Premiere clamps): [(src_in, src_out)] in source frames."""
    slot = frames // max(n, 1)
    skip = max(1, slot // 6)
    if n < 1 or slot - 2 * skip < 2:
        raise ValueError(f'{n} segment(s) do not fit {frames} frames: fewer segments or more seconds')
    return [(k * slot + skip, (k + 1) * slot - (skip if k == n - 1 else 0)) for k in range(n)]


def mapping(segs):
    """[(seq_in, seq_out, src_in, src_out)] in frames: the replay lays the segments end to end from frame 0."""
    out, at = [], 0
    for a, b in segs:
        out.append((at, at + b - a, a, b))
        at += b - a
    return out


def joints(rows):
    """The --at list that proves every cut: each segment's first and last sequence frame."""
    return ','.join(f'{f}f' for s, e, _, _ in rows for f in (s, e - 1))


def cuts_json(segs, fps):
    return {'segments': [{'clip': MEDIA, 'start': round(float(Fraction(a) / fps), 9), 'end': round(float(Fraction(b) / fps), 9),
                          'transcript': f'grey frames {a}-{b - 1}'} for a, b in segs]}


def create(d, fps, size, seconds, n):
    d = Path(d).resolve()
    why = check_dir(d)
    if why:
        sys.exit(why)
    # Every argument is checked before a folder exists: a folder left half-built blocks the re-run ("already exists").
    rate, (w, h) = grey.parse_fps(fps), grey.parse_size(size)
    name, prproj = d.name, d / 'premiere' / f'{d.name}.prproj'
    frames = grey.frame_count(rate, seconds)
    segs = plan(frames, n)
    # Premiere's state FIRST: a bridge that is down stops the run before a folder exists to be in the way of the next.
    st = json.loads(pes.es(STATE_ES))
    if any(same(p, prproj) for p in st['open']):
        sys.exit(f'{prproj} is already open in Premiere: close it first.')
    for sub in ('raw', 'transcript', 'premiere'):
        (d / sub).mkdir(parents=True)
    try:   # the write reads its own clip back: a source that does not decode stops here, before any Premiere write
        grey.write(d / 'raw' / MEDIA, fps, size, seconds, audio=True)
    except (grey.NotSelfConsistent, subprocess.CalledProcessError, OSError) as e:
        sys.exit(f'writing the grey source: {e}\n  Nothing written to Premiere. Remove {d} before a re-run.')
    (d / 'transcript' / 'cuts.json').write_text(json.dumps(cuts_json(segs, rate), indent=2) + '\n', encoding='utf-8')
    (d / PREV).write_text(f"{st['path']}\n{st['seq']}\n", encoding='utf-8')
    print(f"recorded the active project: {st['path'] or 'none'}")

    made = json.loads(pes.es(fill(NEW_ES, PATH=str(prproj))))
    if not same(made['path'], prproj):
        sys.exit(f"app.newProject did not make {prproj} the active project (returned {made['made']}, active: "
                 f"{made['path'] or 'none'}). Nothing saved over anything: no saveAs fallback, by design.\n"
                 f"  Back out with: uv run lanes/premiere/scratch-project.py close {d.as_posix()}")
    b = json.loads(pes.es(fill(BUILD_ES, PATH=made['path'], MEDIA=str(d / 'raw' / MEDIA), NAME=name, W=w, H=h),
                          timeout=120000))
    tpf = Fraction(TPS) / rate
    if b['left'] or int(b['tpf']) != tpf or (b['w'], b['h']) != (w, h):
        sys.exit(f"the sequence came out wrong: {b['w']}x{b['h']}, {b['tpf']} ticks/frame (wanted {w}x{h}, {tpf}), "
                 f"{b['left']} clip(s) left on its tracks.\n  Back out with: uv run lanes/premiere/scratch-project.py close {d.as_posix()}")
    print(f"{made['path']}: sequence {b['seq']} {w}x{h} @ {rate.numerator}/{rate.denominator}"
          f"{' (resized)' if b['resized'] else ''}, tracks emptied ({b['removed']} clip(s) from the sequence-from-clip)")
    require_job_project(pes.es, d)

    r = subprocess.run(['node', str(HERE / 'premiere-bridge.mjs'), 'replay', str(d / 'transcript' / 'cuts.json'),
                        b['item']], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"replay: {pes._why(r.stderr, (r.stdout or '').strip())}\n"
                 f"  Back out with: uv run lanes/premiere/scratch-project.py close {d.as_posix()}")
    print('replay: ' + ' '.join((r.stdout or '').split()))
    rb = json.loads(pes.es(READ_ES))
    rows = mapping(segs)
    bad = []
    if len(rb['v1']) != len(rows) or len(rb['a1']) != len(rows):
        bad.append(f"V1 holds {len(rb['v1'])} clip(s) and A1 {len(rb['a1'])}, the EDL {len(rows)}")
    for (s, e, a, _), clip in zip(rows, rb['v1']):
        cs, ce, ci = (int(x) for x in clip)
        if (cs, ce, ci) != (s * tpf, e * tpf, a * tpf):
            bad.append(f'V1 clip at frame {s}: ticks {cs}-{ce} in {ci}, the EDL says {s * tpf}-{e * tpf} in {a * tpf}')
    print(f"{'segment':>7}  {'sequence frames':>15}  {'source frames':>13}")
    for k, (s, e, a, bb) in enumerate(rows):
        print(f'{k:>7}  {s:>7}-{e - 1:<7}  {a:>6}-{bb - 1:<6}')
    for x in bad:
        print(f'READBACK: {x}')
    print(f'prove it:  uv run lanes/premiere/frame-proof.py {d.as_posix()} --at {joints(rows)}')
    print(f'back out:  uv run lanes/premiere/scratch-project.py close {d.as_posix()}')
    return 1 if bad else 0


def close(d):
    d = Path(d).resolve()
    prproj = d / 'premiere' / f'{d.name}.prproj'
    rec = (d / PREV).read_text(encoding='utf-8').splitlines() if (d / PREV).exists() else []
    back, seq = (rec + ['', ''])[:2]
    st = json.loads(pes.es(STATE_ES))
    mine = next((p for p in st['open'] if same(p, prproj)), '')
    if not mine:
        print(f'{prproj} is not open in Premiere: nothing to close')
    got = json.loads(pes.es(fill(CLOSE_ES, PATH=mine, BACK=next((p for p in st['open'] if same(p, back)), ''), SEQ=seq)))
    if mine and any(same(p, prproj) for p in got['open']):
        print(f'closeDocument(0, 0) left {mine} open: close it by hand, without saving')
        return 1
    if got['closed']:
        print(f'closed {mine} without saving')
    if back and not got['back']:
        print(f'the recorded project {back} is no longer open: make the right project active by hand')
        return 1
    if back:
        print(f"re-activated {got['back']} on {got['how']}")
    if back and not same(got['active'], back):
        print(f"but the ACTIVE project is {got['active'] or 'none'}, not {back}: click its timeline")
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('create', help='build the throwaway job and replay its EDL')
    c.add_argument('dir')
    c.add_argument('--fps', default='24000/1001')
    c.add_argument('--size', default='1920x1080')
    c.add_argument('--seconds', type=float, default=12.0)
    c.add_argument('--segments', type=int, default=4)
    x = sub.add_parser('close', help='close the throwaway without saving and re-activate the recorded project')
    x.add_argument('dir')
    a = ap.parse_args(argv)
    if a.cmd == 'close':
        return close(a.dir)
    try:
        return create(a.dir, a.fps, a.size, a.seconds, a.segments)
    except ValueError as e:
        ap.error(str(e))


if __name__ == '__main__':
    sys.exit(main())
