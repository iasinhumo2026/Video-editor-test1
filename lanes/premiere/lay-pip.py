#!/usr/bin/env python3
"""lay-pip.py: the creator's CORNER CAM over every full-frame recording graphic, on Premiere
(presets/youtube/default/README.md § The corner cam; promoted from your-job, 2026-10-05).

  uv run lanes/premiere/lay-pip.py projects/<job> --plan        # the window, the geometry and every piece (no Premiere)
  uv run lanes/premiere/lay-pip.py projects/<job> --lay         # lay the missing pieces on V6
  uv run lanes/premiere/lay-pip.py projects/<job> --style       # Rounded Crop + Motion + Lumetri on every piece, read back
  uv run lanes/premiere/lay-pip.py projects/<job> --shadow      # the soft shadow under every PiP window, on V5
  uv run lanes/premiere/lay-pip.py projects/<job> --reconcile   # remove pieces that match no planned piece, then --lay
  uv run lanes/premiere/lay-pip.py projects/<job> --relay-all   # every piece off V6 and laid again (a source change the
                                                                # timeline cannot show: a new A/V slip)
      [--face-x N]   the face centre in camera px (default: <job>/pip.json, measured by chin-line.py when the raws changed)

For each `screen-rec` cell with `"pip": true` in the job's graphics-plan.json (every section's, on a multi-section job,
at its `timeline_offset`), the cell's window is split by the section's V1 cuts (cuts.json `_timeline`, written by
`live-edl.py --write`) and each piece is laid from that segment's own camera clip with `premiere-bridge.mjs lay` (a
video-only hard-boundary subclip): source in = the V1 clip's source time at the piece start PLUS the section's A/V slip
(transcript/av-slip.json), so the corner cam is frame for frame the camera under it. A hard-boundary subclip cannot be
extended or slipped in place (an extension FREEZES its extra frames): a moved window is --reconcile + --lay.

THE LOOK (2026-10-03/04, picked off preview sheets): a 600x600 box 60 px off the bottom-right of the 3840x2160
frame (x3180-3780, y1500-2100), corners rounded 108 px on screen ("100 pixels is perfect": Roundness 35.99 on this
window), showing a SQUARE camera window as tall as 2125/2160 of the camera frame, top at 0, placed so the face centre
sits CENTRED in the window (2026-10-07; 120 camera px right of centre until then), graded with the house Look,
and a soft shadow under it (the box's rounded rect 18 px down, blur 26, black 45 %).

HOW, on Premiere 26 (lanes/premiere/lab-notes.md § Step 5): Rounded Crop's Left/Right/Top/Bottom set only the window's
SIZE, always centred on the frame; its Offset (normalised to the frame) moves window and picture together; Roundness is
a % of half the window's short side. Rounded Crop masks AFTER every other effect on its clip, so a Drop Shadow on the
clip renders nothing: the shadow is its own full-frame alpha clip per window on V5. QE addVideoEffect inserts at the TOP,
so a fresh clip takes Lumetri first (stack read back as 'Rounded Crop|Lumetri Color'). The Lumetri is EMPTY until the
Look is written into it by grade-lut.py on the closed project (a copied Lumetri renders live but does not save):
premiere-up.sh --quit, grade-lut.py apply on a copy with --which for the new instances, check every instance carries the
Look, swap, reopen (lanes/premiere/lab-notes.md § Step 4).
"""
import argparse, json, os, subprocess, sys
from fractions import Fraction
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO = Path(__file__).resolve().parents[2]
SEQ_W, SEQ_H = 3840, 2160
BOX = (3180, 1500, 3780, 2100)              # the 600 px box, 60 px off the bottom-right corner
WIN_OF_H = 2125 / 2160                      # the square camera window's side, as a share of the camera height
FACE_RIGHT = 0                              # camera px (on a 3840-wide camera) the face sits right of the window centre: centred (2026-10-07; 120 until then)
CORNER = 107.97                             # screen px: what Roundness 35.99 draws on the 2125 window at 600 px
PIP_TRACK, SHADOW_TRACK = 5, 4              # V6 (0-based): V3/V4 graphics and overlays, V5 the shadow
SHADOW = dict(dy=18, blur=26, opacity=0.45, radius=100, secs=16)


def bridge(*args, timeout=180):
    r = subprocess.run(['node', 'lanes/premiere/premiere-bridge.mjs', *args], cwd=REPO, capture_output=True, text=True, timeout=timeout)
    return r.returncode, '\n'.join(l for l in r.stdout.splitlines() if '[INFO]' not in l), r.stderr


class Job:
    def __init__(self, path, face_x=None):
        self.dir = Path(path).resolve()
        self.rel = os.path.relpath(self.dir, REPO)
        secs = sorted(p.parent for p in (self.dir / 'sections').glob('*/graphics-plan.json')) if (self.dir / 'sections').is_dir() else []
        self.sections = secs or [self.dir]
        self.plans = {d: json.load(open(self._plan(d), encoding='utf-8')) for d in self.sections}
        self.sections.sort(key=lambda d: float(self.plans[d].get('timeline_offset', 0)))
        fps = self.plans[self.sections[0]].get('fps', '24000/1001')
        self.F = float(1 / Fraction(fps))
        self.cam_w, self.cam_h = self._cam_size()
        self.face_x = face_x if face_x is not None else self._face_x()
        self._geometry()

    @staticmethod
    def _plan(d):
        return next(p for p in (d / 'graphics-plan.json', d / 'hf-graphics' / 'graphics-plan.json') if p.exists())

    def raws(self):
        out = []
        for d in self.sections:
            for s in json.load(open(d / 'transcript' / 'cuts.json', encoding='utf-8'))['segments']:
                p = d / 'raw' / Path(s['clip']).name
                if p not in out:
                    out.append(p)
        return out

    def _cam_size(self):
        r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                            '-of', 'csv=p=0', str(self.raws()[0])], capture_output=True, text=True)
        w, h = (int(x) for x in r.stdout.strip().splitlines()[0].split(',')[:2])
        return w, h

    def _face_x(self):
        """The face centre in camera px: <job>/pip.json when it was measured on THESE raws, else chin-line.py over every
        section (the midpoint of the face's widest extents), written back to pip.json."""
        pj = self.dir / 'pip.json'
        stamp = {p.name: p.stat().st_size for p in self.raws()}
        # only the sections that SHOW a corner cam: averaging in a Zoom-call section and a take with no recordings put the
        # face 330 px off the crop's centre (your-job, 2026-10-07)
        cams = [d for d in self.sections if any(b.get('kind') == 'screen-rec' and b.get('pip')
                                                for b in self.plans[d].get('beats') or self.plans[d].get('cells') or [])]
        names = [d.name for d in cams]
        if pj.exists():
            doc = json.load(open(pj, encoding='utf-8'))
            if doc.get('raws') == stamp and doc.get('sections') == names:
                return float(doc['face_x'])
            print(f'⚠ {pj.name} was measured on other raws or sections: re-measuring the face on {", ".join(names)}')
        xs = []
        for d in cams:
            cuts = d / 'transcript' / 'cuts.json'
            dur = float(self.plans[d].get('duration') or 0) or None
            raw = d / 'raw' / Path(json.load(open(cuts, encoding='utf-8'))['segments'][0]['clip']).name
            cmd = ['uv', 'run', 'workflows/chin-line.py', str(raw), '--edl', str(cuts), '--from', '0', '--step', '3', '--json']
            if dur:
                cmd += ['--to', str(dur)]
            r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit(f'✗ chin-line.py failed on {d.name}: {r.stderr[-400:]}')
            h = json.loads(r.stdout)['head']
            xs.append((h['face_left'] + h['face_right']) / 2)
            print(f'  face {d.name}: x {h["face_left"]}-{h["face_right"]} -> centre {xs[-1]:.1f}')
        fx = round(sum(xs) / len(xs), 1)
        json.dump(dict(face_x=fx, raws=stamp, sections=names, how='workflows/chin-line.py, the midpoint of the face extents in '
                                                  'each section that carries a corner cam, averaged (lanes/premiere/lay-pip.py)'),
                  open(pj, 'w', encoding='utf-8'), indent=1)
        print(f'→ {pj}: face_x {fx}')
        return fx

    def _geometry(self):
        side = round(WIN_OF_H * self.cam_h)
        x0 = round(self.face_x - FACE_RIGHT * self.cam_w / 3840 - side / 2)
        x0 = min(max(x0, 0), self.cam_w - side)
        self.win = (x0, 0, x0 + side, side)
        W, H = self.cam_w, self.cam_h
        self.scale = (BOX[2] - BOX[0]) / side * 100
        self.crop = {k: (W - side) / 2 / W * 100 for k in ('Left', 'Right')}
        self.crop.update({k: (H - side) / 2 / H * 100 for k in ('Top', 'Bottom')})
        cx, cy = (self.win[0] + self.win[2]) / 2, (self.win[1] + self.win[3]) / 2
        self.offset = ((cx - W / 2) / W, (cy - H / 2) / H)
        self.round = CORNER / (side / 2 * self.scale / 100) * 100
        bx, by = (BOX[0] + BOX[2]) / 2, (BOX[1] + BOX[3]) / 2
        self.pos = ((bx - (cx - W / 2) * self.scale / 100) / SEQ_W, (by - (cy - H / 2) * self.scale / 100) / SEQ_H)

    def slip(self, d):
        p = d / 'transcript' / 'av-slip.json'
        return int(json.load(open(p, encoding='utf-8')).get('v1_frames', 0)) * self.F if p.exists() else 0.0

    def pieces(self):
        rows = []
        for d in self.sections:
            plan = self.plans[d]
            off = float(plan.get('timeline_offset', 0))
            segs = json.load(open(d / 'transcript' / 'cuts.json', encoding='utf-8'))['segments']
            if any('_timeline' not in s for s in segs):
                sys.exit(f'✗ {d.name}: cuts.json carries no _timeline: run lanes/premiere/live-edl.py {os.path.relpath(d, REPO)} --write first')
            slip = self.slip(d)
            for b in plan.get('beats') or plan.get('cells') or []:
                if b.get('kind') != 'screen-rec' or not b.get('pip'):
                    continue
                a, z = off + float(b['start']), off + float(b['end'])
                for s in segs:
                    t0, t1 = s['_timeline']
                    x, y = max(a, t0), min(z, t1)
                    if y - x < 0.5 * self.F:
                        continue
                    src = float(s['start']) + (x - t0) + slip
                    rows.append(dict(sec=d.name, gid=b['id'], item=Path(s['clip']).name, at=round(x, 6), end=round(y, 6),
                                     src_in=round(src, 6), src_out=round(src + (y - x), 6)))
        return rows

    def windows(self):
        w = {}
        for p in self.pieces():
            a, z = w.get((p['sec'], p['gid']), (1e9, 0))
            w[(p['sec'], p['gid'])] = (min(a, p['at']), max(z, p['end']))
        return sorted(w.values())

    def es(self, script, timeout=300):
        code, out, err = bridge('es', '--job', self.rel, script, timeout=timeout)
        if code != 0:
            sys.exit(f'✗ ES failed: {out} {err[-400:]}')
        return out.strip().splitlines()[-1] if out.strip() else ''

    def track(self, t):
        return json.loads(self.es("var t=app.project.activeSequence.videoTracks[%d],r=[];for(var i=0;i<t.clips.numItems;i++){var c=t.clips[i];"
                                  "r.push([Math.round(c.start.seconds*1e5)/1e5,Math.round(c.end.seconds*1e5)/1e5,c.name,"
                                  "c.projectItem?c.projectItem.getMediaPath():''])}return JSON.stringify(r);" % t))

    def ensure_tracks(self, n):
        # QE addTracks appends video tracks at the end, nothing below moves (place-graphics.py's own provisioning)
        print(self.es("var s=app.project.activeSequence;if(s.videoTracks.numTracks<%d){app.enableQE();qe.project.getActiveSequence()"
                      ".addTracks(%d-s.videoTracks.numTracks,s.videoTracks.numTracks,0,0,0,0,0);}return 'video tracks '+s.videoTracks.numTracks;"
                      % (n, n)))

    def remove(self, t, starts, raw_only=True):
        js = ("var t=app.project.activeSequence.videoTracks[%d],S=%s,n=0;for(var i=t.clips.numItems-1;i>=0;i--){var c=t.clips[i];"
              "for(var k=0;k<S.length;k++){if(Math.abs(c.start.seconds-S[k])<0.02%s){c.remove(false,false);n++;break;}}}"
              "app.project.save();return n;") % (t, json.dumps(starts), "&&c.projectItem&&c.projectItem.getMediaPath().indexOf('/raw/')>=0" if raw_only else '')
        return self.es(js)

    def lay(self):
        self.ensure_tracks(PIP_TRACK + 1)
        have = self.track(PIP_TRACK)
        for p in self.pieces():
            if any(abs(c[0] - p['at']) < 0.5 * self.F for c in have):
                continue
            opts = {'job': self.rel, 'item': p['item'], 'track': 'V%d' % (PIP_TRACK + 1), 'in': p['src_in'], 'out': p['src_out'], 'at': p['at']}
            code, out, err = bridge('lay', json.dumps(opts))
            print(p['sec'], p['gid'], p['at'], '->', p['end'], 'rc', code, ((out or err).strip().splitlines() or [''])[-1][:160])
            if code != 0:
                sys.exit('✗ lay failed; stopping')

    def reconcile(self):
        want = [(p['at'], p['end']) for p in self.pieces()]
        stale = [c for c in self.track(PIP_TRACK) if '/raw/' in c[3]
                 and not any(abs(c[0] - a) < 0.5 * self.F and abs(c[1] - z) < 0.5 * self.F for a, z in want)]
        if not stale:
            print('PiP in sync: nothing to remove')
            return
        print('removed', self.remove(PIP_TRACK, [c[0] for c in stale]), 'stale PiP clip(s):', [(c[0], c[1]) for c in stale])

    def style(self):
        js = """
var s=app.project.activeSequence; app.enableQE(); var qs=qe.project.getActiveSequence();
var vt=s.videoTracks[%(T)d], qt=qs.getVideoTrackAt(%(T)d), out=[];
var CROP=%(CROP)s, SC=%(SC)f, POS=[%(PX)f,%(PY)f], OFF=[%(OX)f,%(OY)f], N=['Left','Right','Top','Bottom'];
function comp(c,name){for(var j=0;j<c.components.numItems;j++){if(c.components[j].displayName==name)return c.components[j];}return null;}
function prop(cm,name){for(var k=0;k<cm.properties.numItems;k++){if(cm.properties[k].displayName==name)return cm.properties[k];}return null;}
function stack(c){var r=[];for(var j=0;j<c.components.numItems;j++){var n=c.components[j].displayName;if(n!='Opacity'&&n!='Motion')r.push(n);}return r.join('|');}
function fx(n){return qe.project.getVideoEffectByName(n);}
var qi=[]; for(var i=0;i<qt.numItems;i++){var it=qt.getItemAt(i); if(it.type=="Clip") qi.push(it);}
for(var i=0;i<vt.clips.numItems;i++){
  var c=vt.clips[i]; var mp=c.projectItem?c.projectItem.getMediaPath():''; if(mp.indexOf('/raw/')<0) continue;
  var q=qi[i];
  if(!comp(c,'Lumetri Color')) q.addVideoEffect(fx('Lumetri Color'));
  for(var k=q.numComponents-1;k>=0;k--){var qc=q.getComponentAt(k); if(qc.name=='Drop Shadow') qc.remove();}
  if(!comp(c,'Rounded Crop')) q.addVideoEffect(fx('Rounded Crop'));
  c=vt.clips[i];
  var cr=comp(c,'Crop'); if(cr){for(var n=0;n<4;n++) prop(cr,N[n]).setValue(0,1);}
  var rc=comp(c,'Rounded Crop'); for(var n=0;n<4;n++) prop(rc,N[n]).setValue(CROP[N[n]],1); prop(rc,'Roundness').setValue(%(RD)f,1); prop(rc,'Offset').setValue(OFF,1);
  var mo=comp(c,'Motion'); prop(mo,'Scale').setValue(SC,1); prop(mo,'Position').setValue(POS,1);
  var pp=prop(mo,'Position').getValue();
  out.push([Math.round(c.start.seconds*1000)/1000, Math.round(prop(mo,'Scale').getValue()*100)/100, Math.round(pp[0]*1e4)/1e4, Math.round(pp[1]*1e4)/1e4,
            Math.round(prop(rc,'Left').getValue()*100)/100, Math.round(prop(rc,'Roundness').getValue()*100)/100, stack(c), cr?Math.round(prop(cr,'Left').getValue()*100)/100:0]);
}
app.project.save(); return JSON.stringify(out);
""" % dict(T=PIP_TRACK, CROP=json.dumps(self.crop), SC=self.scale, PX=self.pos[0], PY=self.pos[1], RD=self.round,
           OX=self.offset[0], OY=self.offset[1])
        rows = json.loads(self.es(js.replace('\n', ' ')))
        bad = [r for r in rows if abs(r[1] - self.scale) > 0.05 or abs(r[2] - self.pos[0]) > 1e-3 or abs(r[3] - self.pos[1]) > 1e-3
               or abs(r[4] - self.crop['Left']) > 0.02 or abs(r[5] - self.round) > 0.01 or r[6] != 'Rounded Crop|Lumetri Color' or r[7] != 0]
        print(len(rows), 'PiP clips styled; readback mismatches:', bad or 'none')
        print('NEXT: the Lumetri on a new piece is EMPTY until grade-lut.py writes the Look into it on the closed project')
        if bad:
            sys.exit(1)

    def shadow(self):
        """One full-frame alpha clip per PiP window on V5, under the camera on V6 (built + imported once)."""
        f = self.dir / 'assets' / 'pip-shadow-alpha.mov'
        if not f.exists():
            f.parent.mkdir(exist_ok=True)
            png = f.with_suffix('.png')
            code = ("from PIL import Image, ImageDraw, ImageFilter\n"
                    f"m = Image.new('L', ({SEQ_W}, {SEQ_H}), 0)\n"
                    f"ImageDraw.Draw(m).rounded_rectangle(({BOX[0]}, {BOX[1] + SHADOW['dy']}, {BOX[2] - 1}, {BOX[3] - 1 + SHADOW['dy']}), "
                    f"{SHADOW['radius']}, fill={round(255 * SHADOW['opacity'])})\n"
                    f"m = m.filter(ImageFilter.GaussianBlur({SHADOW['blur']}))\n"
                    f"im = Image.new('RGBA', ({SEQ_W}, {SEQ_H}), (0, 0, 0, 0)); im.putalpha(m)\n"
                    f"im.save({str(png)!r})\n")
            subprocess.run(['uv', 'run', '-q', '--with', 'pillow', 'python3', '-c', code], check=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-framerate', '24000/1001', '-i', str(png), '-t', str(SHADOW['secs']),
                            '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', '-vendor', 'apl0', str(f)], check=True)
            print('built', f, round(f.stat().st_size / 1e6, 1), 'MB')
        name = f.name
        print(self.es("var r=app.project.rootItem;function find(b){for(var i=0;i<b.children.numItems;i++){var c=b.children[i];if(c.name==%s)return c;"
                      "if(c.type==ProjectItemType.BIN){var x=find(c);if(x)return x;}}return null;}if(!find(r)){app.project.importFiles([%s],true,r,false);}"
                      "return find(r)?'shadow item ready':'IMPORT FAILED';" % (json.dumps(name), json.dumps(str(f)))))
        self.ensure_tracks(SHADOW_TRACK + 1)
        want = self.windows()
        have = self.track(SHADOW_TRACK)
        stale = [c[0] for c in have if name in c[3] and not any(abs(c[0] - a) < 0.5 * self.F and abs(c[1] - z) < 0.5 * self.F for a, z in want)]
        if stale:
            print('removed', self.remove(SHADOW_TRACK, stale, raw_only=False), 'stale shadow clip(s)')
        for a, z in want:
            if any(abs(c[0] - a) < 0.5 * self.F and abs(c[1] - z) < 0.5 * self.F for c in have):
                continue
            code, out, err = bridge('lay', json.dumps({'job': self.rel, 'item': name, 'track': 'V%d' % (SHADOW_TRACK + 1), 'in': 0, 'out': z - a, 'at': a}))
            if code != 0:
                sys.exit(f'✗ shadow lay failed at {a}: {(out or err)[-300:]}')
        have = self.track(SHADOW_TRACK)
        miss = [(a, z) for a, z in want if not any(abs(c[0] - a) < 0.5 * self.F and abs(c[1] - z) < 0.5 * self.F for c in have)]
        print('shadow windows', len(want), '· clips on V%d' % (SHADOW_TRACK + 1), len(have), '· missing', miss or 'none')
        if miss:
            sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job')
    ap.add_argument('--face-x', type=float)
    g = ap.add_mutually_exclusive_group(required=True)
    for m in ('plan', 'lay', 'style', 'shadow', 'reconcile', 'relay-all'):
        g.add_argument('--' + m, action='store_true')
    a = ap.parse_args()
    j = Job(a.job, a.face_x)
    if a.plan:
        ps = j.pieces()
        for p in ps:
            print(p)
        print(f'{len(ps)} pieces in {len(j.windows())} windows · camera {j.cam_w}x{j.cam_h} · face x {j.face_x} · window {j.win} · '
              f'scale {j.scale:.4f} · roundness {j.round:.4f} · offset ({j.offset[0]:.6f}, {j.offset[1]:.6f}) · '
              f'position ({j.pos[0]:.6f}, {j.pos[1]:.6f}) · slips ' + ', '.join(f'{d.name} {round(j.slip(d) / j.F)}' for d in j.sections))
    elif a.lay:
        j.lay()
    elif a.style:
        j.style()
    elif a.shadow:
        j.shadow()
    elif a.reconcile:
        j.reconcile()
    elif a.relay_all:
        stale = [c[0] for c in j.track(PIP_TRACK) if '/raw/' in c[3]]
        print('removed from V%d:' % (PIP_TRACK + 1), j.remove(PIP_TRACK, stale) if stale else 0)
        j.lay()


if __name__ == '__main__':
    main()
