#!/usr/bin/env python3
"""Organize a job's Premiere project bin (2026-10-04: "Organize the project bin, please").

Every loose item at the root is sorted by what the TIMELINE uses (project item nodeIds of every clip on every track),
never by name alone, and moved with ProjectItem.moveBin. Nothing is deleted: superseded versions, retired renders and
stale subclips go to "07 Unused". Bins already at the root stay where they are; the "sfx" bin must: place-sfx.py finds
it there by name (every other placer finds its items by media path anywhere in the tree).

  uv run lanes/premiere/organize-bins.py projects/<job>               # print the plan (read only)
  uv run lanes/premiere/organize-bins.py projects/<job> --apply       # move, read back, save
      [--pip-track V6]    the track the corner-cam (PiP) subclips play on: they go to "03 Corner Cam/Camera"

The bins: 01 Sequence · 02 Footage (+ /Subclips) · 03 Corner Cam (/Camera, /Shadow) · 04 Recordings/<Section> ·
05 Graphics/<Section> · 06 Grade · 07 Unused (/Old Camera Pieces, /Retired Renders, /Old Versions, /Other) · 08 Other.
Sections are the job's sections/*/ folder names, title-cased (how-it-works -> How It Works); a single-section job's
recordings and graphics land in 04 Recordings / 05 Graphics directly. A render is a recording when its plan cell's kind
is screen-rec. The active-project guard (job_guard.py) runs before the first read.
"""
import argparse, json, re, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from job_guard import job_root, require_job_project   # noqa: E402
from pes import es, paged                             # noqa: E402  (lanes/premiere/pes.py: the bridge's one output contract)

for _s in (sys.stdout, sys.stderr):   # item names can carry non-ASCII; Windows pipes default to cp1252
    try:
        if (getattr(_s, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
            _s.reconfigure(encoding='utf-8')
    except Exception:
        pass


# One page of the root's children [n0, n1): nodeId, name, job-relative media path, is-bin, is-sequence, the tracks that
# play it. The root is unbounded on a fresh project (every import lands there), so it is paged (pes.py § paged).
READ = r"""(function(){
var s=app.project.activeSequence, used={}, root=app.project.rootItem, items=[], JOB=%s;
function mark(tracks,kind){for(var t=0;t<tracks.numTracks;t++){var tr=tracks[t];for(var i=0;i<tr.clips.numItems;i++){var c=tr.clips[i];
  if(!c.projectItem)continue;var k=c.projectItem.nodeId;(used[k]=used[k]||[]).push(kind+(t+1));}}}
mark(s.videoTracks,'V'); mark(s.audioTracks,'A');
for(var i=%d;i<Math.min(%d,root.children.numItems);i++){var c=root.children[i];var mp='';try{mp=c.getMediaPath();}catch(e){}
  mp=String(mp).replace(/\\/g,'/');var at=mp.lastIndexOf('/'+JOB+'/');if(at>=0)mp=mp.substring(at+JOB.length+2);
  var u=used[c.nodeId]||[],ut={};for(var q=0;q<u.length;q++)ut[u[q]]=1;var us=[];for(var q in ut)us.push(q);
  items.push([c.nodeId,c.name,mp,c.type==ProjectItemType.BIN?1:0,(c.isSequence&&c.isSequence())?1:0,us.join(',')]);}
return JSON.stringify(items);
})()"""


def sections(job):
    """{folder: bin name} for a multi-section job, {} for a single-section one."""
    d = job / 'sections'
    return {p.name: ' '.join(w.capitalize() for w in p.name.split('-'))
            for p in sorted(d.iterdir()) if p.is_dir()} if d.is_dir() else {}


def kinds(job, secs):
    k = {}
    for sec, plan in ([(s, job / 'sections' / s / 'graphics-plan.json') for s in secs] if secs
                      else [(None, job / 'graphics-plan.json')]):
        if not plan.exists():
            continue
        for b in json.load(open(plan, encoding='utf-8'))['beats']:
            if b.get('id'): k[(sec, b['id'])] = b.get('kind')
    return k


def plan(job, pip_track):
    js = json.dumps(job.name)
    items = [dict(id=r[0], name=r[1], path=r[2], bin=r[3], seq=r[4], used=[u for u in r[5].split(',') if u])
             for r in paged(lambda n0, n1: (READ % (js, n0, n1)).replace('\n', ' '), size=100)]
    used_paths = {i['path'] for i in items if i['used'] and i['path']}
    secs = sections(job)
    kd = kinds(job, secs)
    moves = []
    for i in items:
        if i['bin']:
            continue
        name, path, used = i['name'], i['path'], i['used']
        rel = path                                                          # job-relative (the read strips the prefix)
        sub = bool(path) and name != Path(path).name                       # a subclip ("VID x.mp4 @12.34s")
        live = bool(used) if (sub or not path) else path in used_paths     # a master counts while any clip plays its file
        if i['seq']:
            dest = '01 Sequence'
        elif not path:
            dest = '06 Grade' if live else '07 Unused/Other'
        elif rel.startswith('raw/'):
            if not sub: dest = '02 Footage'
            elif not live: dest = '07 Unused/Old Camera Pieces'
            elif any(u == pip_track for u in used): dest = '03 Corner Cam/Camera'
            else: dest = '02 Footage/Subclips'
        elif rel.startswith('assets/pip-shadow'):
            dest = '03 Corner Cam/Shadow' if live else '07 Unused/Old Camera Pieces'
        elif (secs and rel.startswith('sections/')) or (not secs and rel.startswith('hf-graphics/')):
            sec = rel.split('/')[1] if secs else None
            m = re.match(r'(?:VID )?([a-z]+\d+[a-z]?)', Path(rel).name)
            gid = m.group(1) if m else ''
            what = 'Recordings' if kd.get((sec, gid)) == 'screen-rec' else 'Graphics'
            sub_bin = f'/{secs.get(sec, sec)}' if sec else ''
            dest = f'{"04" if what == "Recordings" else "05"} {what}{sub_bin}' if live else \
                   ('07 Unused/Retired Renders' if '/retired/' in rel else '07 Unused/Old Versions')
        else:
            dest = '07 Unused/Other' if not live else '08 Other'
        moves.append((i['id'], name, dest))
    return moves


APPLY = r"""
var root=app.project.rootItem, M=%s, made={}, moved=0, miss=[];
function child(bin,name){for(var i=0;i<bin.children.numItems;i++){var c=bin.children[i];if(c.type==ProjectItemType.BIN&&c.name==name)return c;}return null;}
function binAt(path){if(made[path])return made[path];var parts=path.split('/'),b=root;for(var i=0;i<parts.length;i++){b=child(b,parts[i])||b.createBin(parts[i]);}made[path]=b;return b;}
var byId={};for(var i=0;i<root.children.numItems;i++){var c=root.children[i];byId[c.nodeId]=c;}
for(var k=0;k<M.length;k++){var it=byId[M[k][0]];if(!it){miss.push(M[k][1]);continue;}it.moveBin(binAt(M[k][2]));moved++;}
var loose=[];for(var i=0;i<root.children.numItems;i++){var c=root.children[i];if(c.type!=ProjectItemType.BIN)loose.push(c.name);}
app.project.save(); return JSON.stringify({moved:moved,miss:miss,loose:loose});
"""

READBACK = r"""
var out={};function walk(b,p){for(var i=0;i<b.children.numItems;i++){var c=b.children[i];
  if(c.type==ProjectItemType.BIN){walk(c,p?p+'/'+c.name:c.name);}else{out[p||'(root)']=(out[p||'(root)']||0)+1;}}}
walk(app.project.rootItem,''); var s=app.project.activeSequence,n=[];
for(var i=0;i<s.videoTracks.numTracks;i++)n.push('V'+(i+1)+':'+s.videoTracks[i].clips.numItems);
for(var i=0;i<s.audioTracks.numTracks;i++)n.push('A'+(i+1)+':'+s.audioTracks[i].clips.numItems);
return JSON.stringify({bins:out,tracks:n.join(' '),offline:(function(){var o=0;function w(b){for(var i=0;i<b.children.numItems;i++){var c=b.children[i];if(c.type==ProjectItemType.BIN)w(c);else if(c.isOffline&&c.isOffline())o++;}}w(app.project.rootItem);return o;})()});
"""


def wrap(body):
    """The bare `return` bodies above, as the one expression the bridge evaluates."""
    return '(function(){' + body.replace('\n', ' ') + '})()'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('job', help='projects/<job> (a section sub-job resolves to its parent: one project per job)')
    ap.add_argument('--apply', action='store_true', help='move, read back, save (default: print the plan only)')
    ap.add_argument('--pip-track', default='V6', help='the track the corner-cam subclips play on (default V6)')
    a = ap.parse_args()
    job = job_root(a.job)
    require_job_project(es, job)          # THE GUARD before any read: the job's project and its own sequence
    moves = plan(job, a.pip_track)
    by = {}
    for _, n, d in moves:
        by.setdefault(d, []).append(n)
    for d, n in sorted(Counter(m[2] for m in moves).items()):
        print(f'{n:4d}  {d}')
        if not a.apply:
            for name in by[d]:
                print(f'        {name}')
    if not moves:
        print('   0  moves: nothing loose at the root')
    if a.apply:
        before = json.loads(es(wrap(READBACK)))
        r = json.loads(es(wrap(APPLY % json.dumps(moves))))
        after = json.loads(es(wrap(READBACK)))
        print('moved', r['moved'], 'missing', r['miss'], 'still loose at root', r['loose'])
        print('tracks before', before['tracks'], '| after', after['tracks'], '| offline', before['offline'], '->', after['offline'])
        for b, n in sorted(after['bins'].items()):
            print(f'{n:4d}  {b}')
