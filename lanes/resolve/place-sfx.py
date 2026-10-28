#!/usr/bin/env python3
"""place-sfx.py: put a job's sfx-plan.json on the Resolve SFX tracks (pipeline step 6, Resolve lane, Studio 21.1+).

Runs INSIDE Resolve's embedded Python through the davinci-resolve MCP's `run_script_unsafe` (it reads the plan and the
library files, which the sandboxed run_script cannot), like resolve-audio-polish/replace-clips.py. Pass the 60 s cap:

    run_script_unsafe  timeout: 60  script:
      "import io; JOB='/abs/projects/<job>'; MODE='apply'; "
      "exec(io.open('/abs/lanes/resolve/place-sfx.py', encoding='utf-8').read())"

From a shell it checks the plan offline and PRINTS that call with this machine's absolute paths (nothing here talks
to Resolve from a shell):

  uv run lanes/resolve/place-sfx.py projects/<job> --apply          # place every row not yet laid, levels, fades, read back, save
  uv run lanes/resolve/place-sfx.py projects/<job> --verify         # readback vs the plan: every missing, extra or drifting cue named
  uv run lanes/resolve/place-sfx.py projects/<job> --remove-extra [--dry]      # clear exactly the clips --verify calls extra
  uv run lanes/resolve/place-sfx.py projects/<job> --remove s004,s017 [--dry]  # those plan rows' clips (ids by commas and/or spaces)
  uv run lanes/resolve/place-sfx.py projects/<job> --remove [--dry]            # every SFX clip from the plan's libraries (a full clear)
    --timeline NAME   the timeline, by NAME (default: the one named after the job, a section's parent job, or the
                      project's only timeline); never the current one, which the creator may have switched
    --plan FILE       another cut sheet, relative to the job (default hf-graphics/sfx-plan.json)

Wrapper globals: JOB (required), MODE ('apply' | 'verify' | 'remove' | 'remove-extra'; default 'apply'), TIMELINE,
PLAN, IDS (row ids for 'remove'), DRY (True: a remove lists and touches nothing).

The contract is lanes/premiere/place-sfx.py's; the plan is universal (workflows/sfx-plan.py), only placing is per lane:
  - a row's `track` is the plan's 0-based index on the preset map (1 = A2): Resolve audio track `track + 1`. Missing
    tracks are appended as stereo tracks (nothing laid moves); A1 (the voice) and A5 (the music) are never read or written
  - each library file is imported ONCE into the media pool's `sfx` bin and found by its File Path anywhere in the
    pool afterwards (the whole pack loaded by load-sfx-pack.py counts)
  - each row is one audio-only AppendToTimeline (mediaType 2) at T0 + at x fps, its slice in WHOLE frames (an imported
    audio file ingests at the project rate) with the in-point's rounding carried by the fractional record frame (Resolve
    keeps one), so the sound plays at its planned second; CUT where the next cue on its track starts: the tail
    Premiere's overwrite leaves (sfx.md § The law 6: a repeating sound truncates the one before it, the layers never overlap)
  - the level is the item's AudioVolume (dB), written when not 0 and read back; a `fade_out_s` row (the calling bed)
    gets SetFades FadeOut in frames, read back: the fade the Premiere lane lays by hand
  - a cue whose span another clip already holds on its track is never laid over (the creator's clip, or a stale cue
    of an older plan): it is named and skipped; --remove-extra or --remove <ids>, then --apply
  - --verify reads every SFX clip back: start and source in to half a frame (Resolve lands a source in on a whole
    frame), the tail to half a frame, the level to 0.2 dB, the fade to a frame. A row no clip answers for is MISSING,
    a clip that answers for no row is EXTRA, and both fail; a cue the creator laid out of the job's own audio/sfx-src
    is named and left alone (sfx.md § Definition of done)
  - --apply stops laying new rows at the 45 s mark (the MCP stops a script at 60 s) and says so: it is idempotent,
    the same call lays the rest. Every write ends in a save (never on "Untitled Project"); a write that returns
    None or False is reported, never passed on (a Resolve modal up makes every write fail quietly)
The source in is read as GetSourceStartTime() minus the file's own start (a Broadcast-WAV's time_reference: 3600 s on
`Pop 1.wav`), never GetSourceStartFrame(), which truncates (davinci-resolve § Step 6). A plan derived from an older
placement.json (a graphic moved since) is named first. Not ported from the Premiere placer: --diff, --adopt and the
--until copy window. Resolve's embedded Python prints ASCII only, so every status line here is ASCII.
"""
import io, json, math, os, struct, sys, time

MUSIC_TRACK = 5            # Resolve A5: the music role on presets/youtube/default/README.md's track map (plan index 4)
BUDGET_S = 45.0            # run_script_unsafe stops a script at 60 s: no new row is started past this
LEVEL_TOL = 0.2            # dB, the Premiere lane's line
MODES = ('apply', 'verify', 'remove', 'remove-extra')
NTSC = {'23.976': 24000 / 1001, '29.97': 30000 / 1001, '47.952': 48000 / 1001, '59.94': 60000 / 1001,
        '119.88': 120000 / 1001}


def norm(p):
    return os.path.normcase(os.path.normpath(p))


def fps_of(v):
    """A Resolve frame-rate setting ('29.97', '24', '29.97 DF', 30.0) as the exact rate."""
    s = str(v).strip().split(' ')[0]
    return NTSC.get(s, float(s))


def file_start(path):
    """The file's own start in seconds: a Broadcast-WAV's bext time_reference over its sample rate, 0 for anything
    else. Resolve counts an item's source TIME from it (3600 s on `Pop 1.wav`), its frame-based in-point does not."""
    if not path.lower().endswith(('.wav', '.wave', '.bwf')):
        return 0.0
    rate = ref = None
    with open(path, 'rb') as f:
        head = f.read(12)
        if head[:4] not in (b'RIFF', b'RF64') or head[8:12] != b'WAVE':
            return 0.0
        while rate is None or ref is None:
            ch = f.read(8)
            if len(ch) < 8:
                break
            cid, size = ch[:4], struct.unpack('<I', ch[4:])[0]
            if cid == b'fmt ':
                rate = struct.unpack('<I', f.read(size)[4:8])[0]
            elif cid == b'bext' and size >= 346:
                lo, hi = struct.unpack('<II', f.read(size)[338:346])
                ref = lo + (hi << 32)
            else:
                f.seek(size, 1)                           # the samples too: the pack's bext sits AFTER them (Pop 1.wav)
            if size % 2:
                f.seek(1, 1)
    return ref / rate if rate and ref else 0.0


def snapf(x):
    """A frame position as the plan meant it: the plan's times are frame-snapped to four decimals, so a value within
    a hundredth of a frame of a whole one IS that frame."""
    r = round(x)
    return r if abs(x - r) < 0.01 else x


class Plan:
    """sfx-plan.json for one job, lane-free: its rows, the libraries they come from and each row's laid slice."""

    def __init__(self, job, plan=None):
        self.job = os.path.abspath(job)
        self.hf = os.path.join(self.job, 'hf-graphics')
        self.path = plan if plan and os.path.isabs(plan) else os.path.join(self.job, plan or os.path.join('hf-graphics', 'sfx-plan.json'))
        if not os.path.exists(self.path):
            raise SystemExit('no %s: nothing to place, verify or remove' % self.path)
        with io.open(self.path, encoding='utf-8') as f:
            rows = json.load(f)
        if not rows:
            raise SystemExit('%s has no rows: nothing to place, verify or remove (an empty plan never means "every clip")'
                             % os.path.basename(self.path))
        # a cue whose anchor a re-cut DELETED (workflows/ripple-cut.py) sits at its pre-recut time: re-anchoring it is
        # a hand decision, never a placer's guess (the Premiere placer's refusal, word for word in effect)
        dead = ['%s %s at %.3fs [%s]' % (r.get('id', '?'), r.get('event', '?'), float(r.get('at') or 0), r.get('gid', '?'))
                for r in rows if r.get('ripple') == 'orphaned']
        if dead:
            raise SystemExit('%d cue(s) are on a DEAD ANCHOR ("ripple": "orphaned"), nothing touched:\n    %s\n'
                             '  Re-anchor each row (drop its `ripple` key once its `at` is right) or delete it, then re-run.'
                             % (len(dead), '\n    '.join(dead)))
        gone = sorted({r['file'] for r in rows if not os.path.exists(r['file'])})
        if gone:
            raise SystemExit('%d library file(s) the plan names are not on disk, nothing touched:\n    %s'
                             % (len(gone), '\n    '.join(gone)))
        gp = os.path.join(self.job, 'graphics-plan.json')
        gplan = {}
        if os.path.exists(gp):
            with io.open(gp, encoding='utf-8') as f:
                gplan = json.load(f)
        # a SECTION sub-job: only the SFX clips inside the section's span are this plan's business
        self.off = float(gplan.get('timeline_offset') or 0.0)
        self.span = None
        if gplan.get('timeline_offset') or gplan.get('duration'):
            self.span = (self.off - 0.5, self.off + float(gplan.get('duration') or 1e9) + 0.5)
        self.plan_fps = gplan.get('fps')
        self.rows = sorted(rows, key=lambda r: (float(r['at']), r['track']))
        self.plan_libs = sorted({norm(os.path.dirname(r['file'])) for r in rows})
        self.local = norm(os.path.join(self.job, 'audio', 'sfx-src'))
        self.libs = self.plan_libs + [self.local]
        self.tracks = sorted({int(r['track']) for r in rows})

    def lay(self, r, fps):
        """(record frame from 0, source in frame, length in frames) of row r. Resolve lands a source in-point on a WHOLE
        frame (an imported audio file ingests at the project rate) but keeps a fractional record frame, so the record
        frame carries the in-point's rounding: every sample of the slice plays at its planned second, the attack the
        planner aligned included, never up to half a frame off. The length is whole frames, cut where the next cue on
        its track starts (that cue's own record frame)."""
        def rec_of(x):
            return snapf(float(x['at']) * fps) + round(float(x['src_in']) * fps) - float(x['src_in']) * fps
        rec, s0 = rec_of(r), int(round(float(r['src_in']) * fps))
        n = int(round(float(r['src_out']) * fps)) - s0
        nxt = [x for x in self.rows if x['track'] == r['track'] and float(x['at']) > float(r['at'])]
        if nxt:
            n = min(n, int(math.floor(rec_of(min(nxt, key=lambda x: float(x['at']))) - rec + 1e-6)))
        return rec, s0, max(n, 1)

    def stale_note(self):
        """The planner's staleness check (a graphic moved since the plan was derived), as one line, or ''."""
        try:
            import importlib.util
            here = os.path.dirname(self.job)
            while here and not os.path.exists(os.path.join(here, 'workflows', 'sfx-plan.py')):
                up = os.path.dirname(here)
                here = None if up == here else up
            if not here:
                return ''
            spec = importlib.util.spec_from_file_location('sfx_plan', os.path.join(here, 'workflows', 'sfx-plan.py'))
            planner = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(planner)
            moved = planner.stale_gids(self.path, self.hf)
        except Exception as e:                                   # the check is a warning, never the placer's blocker
            return '! the staleness check did not run (%s)' % e
        if moved is None:
            return ('! %s has no placement record: a graphic that moved since it was derived cannot be named '
                    '(workflows/sfx-plan.py --record writes one, no row changed)' % os.path.basename(self.path))
        if moved:
            return ('! %s was derived from an older placement.json (moved since: %s): re-plan those graphics first, '
                    'uv run workflows/sfx-plan.py <job> --merge %s' % (os.path.basename(self.path), ', '.join(moved), ','.join(moved)))
        return ''


def clip_path(mpi):
    props = None
    try:
        props = mpi.GetClipProperty()
    except Exception:
        pass
    if isinstance(props, dict) and props.get('File Path'):
        return props['File Path']
    return mpi.GetClipProperty('File Path') or ''


def get_volume(item):
    try:
        props = item.GetProperties()
        if isinstance(props, dict) and 'AudioVolume' in props:
            return props['AudioVolume']
    except Exception:
        pass
    return item.GetProperty('AudioVolume')


def set_volume(item, db):
    try:
        if item.SetProperties({'AudioVolume': float(db)}):
            return True
    except Exception:
        pass
    return bool(item.SetProperty('AudioVolume', float(db)))


class Lane:
    """The plan against one Resolve timeline, found by NAME."""

    def __init__(self, resolve, plan, timeline=None, out=print):
        self.plan, self.out, self.t0 = plan, out, time.time()
        self.pm = resolve.GetProjectManager()
        self.proj = self.pm.GetCurrentProject()
        if not self.proj:
            raise SystemExit('no project is open in Resolve')
        self.mp = self.proj.GetMediaPool()
        tls = [self.proj.GetTimelineByIndex(i) for i in range(1, (self.proj.GetTimelineCount() or 0) + 1)]
        tls = [t for t in tls if t]
        job = os.path.basename(plan.job)
        if os.path.basename(os.path.dirname(plan.job)) == 'sections':
            job = os.path.basename(os.path.dirname(os.path.dirname(plan.job)))   # a section lives on its parent's timeline
        want = timeline or job
        hit = [t for t in tls if t.GetName() == want]
        if not hit and not timeline and len(tls) == 1:
            hit = tls
            out('timeline: the project\'s only one, "%s" (none is named "%s")' % (tls[0].GetName(), want))
        if not hit:
            raise SystemExit('no timeline named "%s" in project "%s" (it has: %s): pass TIMELINE (--timeline NAME)'
                             % (want, self.proj.GetName(), ', '.join('"%s"' % t.GetName() for t in tls) or 'none'))
        self.tl = hit[0]
        self.fps = fps_of(self._timeline_rate())
        self.T0 = self.tl.GetStartFrame()
        self.F = 1.0 / self.fps
        if plan.plan_fps:
            n, _, d = str(plan.plan_fps).partition('/')
            pf = float(n) / float(d or 1)
            if abs(pf - self.fps) > 0.01:
                out('! the plan is on a %.3f fps grid and the timeline runs at %.3f: every cue is laid at its second, '
                    'its frames are the timeline\'s' % (pf, self.fps))
        self._starts = {}

    def _timeline_rate(self):
        for obj in (self.tl, self.proj):
            try:
                s = obj.GetSettings()
                if isinstance(s, dict) and s.get('timelineFrameRate'):
                    return s['timelineFrameRate']
            except Exception:
                pass
            try:
                v = obj.GetSetting('timelineFrameRate')
                if v:
                    return v
            except Exception:
                pass
        raise SystemExit('the timeline\'s frame rate did not read back: nothing touched')

    def start_of(self, path):
        if path not in self._starts:
            self._starts[path] = file_start(path)
        return self._starts[path]

    def in_libs(self, path, libs):
        p = norm(path)
        return bool(p) and any(p.startswith(l + os.sep) for l in libs)

    def sfx_tracks(self):
        return [t for t in range(2, (self.tl.GetTrackCount('audio') or 0) + 1) if t != MUSIC_TRACK]

    def readback(self, libs=None):
        """Every SFX clip on the timeline (A2.. but A5) whose media is in `libs` (default: the plan's libraries and the
        job's audio/sfx-src), as dicts in seconds from the timeline start."""
        libs = self.plan.libs if libs is None else libs
        got = []
        for t in self.sfx_tracks():
            for it in self.tl.GetItemListInTrack('audio', t) or []:
                mpi = it.GetMediaPoolItem()
                path = clip_path(mpi) if mpi else ''
                if not self.in_libs(path, libs):
                    continue
                s0 = it.GetStart(True) if self._sub(it) else it.GetStart()
                e0 = it.GetEnd(True) if self._sub(it) else it.GetEnd()
                src = it.GetSourceStartTime()
                fades = None
                try:
                    fades = it.GetFades()
                except Exception:
                    pass
                c = dict(track=t, start=(s0 - self.T0) * self.F, end=(e0 - self.T0) * self.F, path=path, item=it,
                         src_in=None if src is None else float(src) - self.start_of(path), db=get_volume(it),
                         fade=(fades or {}).get('FadeOut') if isinstance(fades, dict) else None)
                if self.plan.span and not (self.plan.span[0] <= c['start'] <= self.plan.span[1]
                                           and not (c['start'] < self.plan.off and c['end'] <= self.plan.off + 1e-3)):
                    continue
                got.append(c)
        return got

    @staticmethod
    def _sub(it):
        try:
            it.GetStart(True)
            return True
        except TypeError:
            return False

    def match(self, r, tl, seen=()):
        return [c for c in tl if id(c) not in seen and norm(c['path']) == norm(r['file'])
                and c['track'] == int(r['track']) + 1 and abs(c['start'] - float(r['at'])) <= 1.5 * self.F]

    def local(self, c):
        return norm(c['path']).startswith(self.plan.local + os.sep) and not self.in_libs(c['path'], self.plan.plan_libs)

    def check(self, r, c):
        """What is wrong with clip c as row r's cue, None when it is right: the one set of lines --verify holds."""
        rec, s0, n = self.plan.lay(r, self.fps)
        tol = self.F / 2 + 1e-3
        db = c['db']
        if db is None and float(r['level_db']) == 0:
            db = 0.0                                              # an untouched clip may read no level at all: 0 dB
        if db is None or abs(float(db) - float(r['level_db'])) > LEVEL_TOL:
            return 'level %s dB, plan %+g' % (db, float(r['level_db']))
        if c['src_in'] is None or abs(c['src_in'] - s0 * self.F) > tol:
            return 'source in %s, plan %.3f' % ('unreadable' if c['src_in'] is None else '%.3f' % c['src_in'], float(r['src_in']))
        if abs(c['start'] - rec * self.F) > tol:
            return 'start %.3f, plan %.3f' % (c['start'], float(r['at']))
        if abs(c['end'] - (rec + n) * self.F) > tol:
            return 'tail %.3f, plan %.3f (the slice, cut by the next cue on its track)' % (c['end'], (rec + n) * self.F)
        if r.get('fade_out_s'):
            want = min(int(round(float(r['fade_out_s']) * self.fps)), n)
            if c['fade'] is None or abs(float(c['fade']) - want) > 1:
                return 'fade-out %s frames, plan %d' % (c['fade'], want)
        return None

    def verify(self, quiet=False):
        tl = self.readback()
        ok, seen = True, set()
        for r in self.plan.rows:
            m = self.match(r, tl, seen)
            if not m:
                ok = False
                self.out('MISSING %s %s A%d %.3f %s: not on the timeline' % (r['id'], r.get('event', ''), int(r['track']) + 1,
                                                                               float(r['at']), os.path.basename(r['file'])))
                continue
            c = m[0]
            seen.add(id(c))
            bad = self.check(r, c)
            if bad:
                ok = False
                self.out('DRIFT   %s: %s' % (r['id'], bad))
            elif not quiet:
                self.out('ok      %s A%d %.3f -> %.3f %+g dB %s' % (r['id'], c['track'], c['start'], c['end'],
                                                                     float(r['level_db']), os.path.basename(c['path'])))
        rest = [c for c in tl if id(c) not in seen]
        loc = [c for c in rest if self.local(c)]
        extra = [c for c in rest if not self.local(c)]
        name = os.path.basename(self.plan.path)
        for c in extra:
            ok = False
            self.out('EXTRA   A%d %.3f %s: not in %s' % (c['track'], c['start'], os.path.basename(c['path']), name))
        for c in loc:
            self.out('local   A%d %.3f %s: hand-placed from audio/sfx-src, not in %s (left alone)'
                     % (c['track'], c['start'], os.path.basename(c['path']), name))
        self.out('%s: %d rows, %d extra%s' % ('ALL PLACED' if ok else 'DRIFT', len(self.plan.rows), len(extra),
                                              ', %d job-local' % len(loc) if loc else ''))
        return ok

    def extras(self):
        tl = self.readback()
        seen = set()
        for r in self.plan.rows:
            m = self.match(r, tl, seen)
            if m:
                seen.add(id(m[0]))
        return [c for c in tl if id(c) not in seen and not self.local(c)]

    def provision(self):
        need = max(self.plan.tracks) + 1
        if need >= MUSIC_TRACK:
            raise SystemExit('the plan lays a cue on A%d, the music track: nothing touched' % need)
        before = self.tl.GetTrackCount('audio') or 0
        while (self.tl.GetTrackCount('audio') or 0) < need:
            if not self.tl.AddTrack('audio', 'stereo'):
                raise SystemExit('could not add audio track %d (AddTrack refused: a Resolve modal up?): nothing laid'
                                 % ((self.tl.GetTrackCount('audio') or 0) + 1))
        after = self.tl.GetTrackCount('audio') or 0
        if after != before:
            self.out('audio tracks %d -> %d' % (before, after))

    def pool(self):
        """{normalised File Path: MediaPoolItem} across every bin of the pool."""
        def walk(folder):
            out = list(folder.GetClipList() or [])
            for sub in folder.GetSubFolderList() or []:
                out += walk(sub)
            return out
        return dict((norm(clip_path(m)), m) for m in walk(self.mp.GetRootFolder()))

    def ensure_media(self):
        """Every file the plan names as a media pool item: the missing ones imported ONCE into the `sfx` bin."""
        have = self.pool()
        want = sorted({r['file'] for r in self.plan.rows})
        missing = [f for f in want if norm(f) not in have]
        if missing:
            root = self.mp.GetRootFolder()
            sfx = next((f for f in root.GetSubFolderList() or [] if f.GetName() == 'sfx'), None) or self.mp.AddSubFolder(root, 'sfx')
            if not sfx:
                raise SystemExit('could not make the `sfx` bin (a Resolve modal up?): nothing laid')
            was = self.mp.GetCurrentFolder()
            self.mp.SetCurrentFolder(sfx)
            try:
                got = self.mp.ImportMedia([{'FilePath': f} for f in missing]) or []
            finally:
                if was:
                    self.mp.SetCurrentFolder(was)
            have = self.pool()
            failed = [f for f in missing if norm(f) not in have]
            if failed:
                raise SystemExit('ImportMedia did not bring in %d file(s), nothing laid:\n    %s'
                                 % (len(failed), '\n    '.join(failed)))
            self.out('imported %d library file(s) into the sfx bin (%d returned)' % (len(missing), len(got)))
        return have

    def occupant(self, track, a, b, skip=()):
        """A clip already on audio track `track` overlapping frames [a, b) from the timeline start, or None."""
        for it in self.tl.GetItemListInTrack('audio', track) or []:
            if id(it) in skip:
                continue
            s = (it.GetStart(True) if self._sub(it) else it.GetStart()) - self.T0
            e = (it.GetEnd(True) if self._sub(it) else it.GetEnd()) - self.T0
            if s < b - 1e-3 and a < e - 1e-3:
                return it
        return None

    def apply(self):
        if not self.proj.SetCurrentTimeline(self.tl):             # AppendToTimeline lays on the CURRENT timeline
            raise SystemExit('could not make "%s" the current timeline (a Resolve modal up?): nothing touched' % self.tl.GetName())
        self.provision()
        have = self.ensure_media()
        tl = self.readback()
        seen, placed, kept, blocked, failed = set(), [], 0, [], []
        todo = []
        for r in self.plan.rows:
            m = self.match(r, tl, seen)
            if m:
                seen.add(id(m[0]))
                kept += 1
            else:
                todo.append(r)
        left = []
        for i, r in enumerate(todo):
            if time.time() - self.t0 > BUDGET_S:
                left = todo[i:]
                break
            rec, s0, n = self.plan.lay(r, self.fps)
            track = int(r['track']) + 1
            occ = self.occupant(track, rec, rec + n)
            if occ is not None:
                mpi = occ.GetMediaPoolItem()
                blocked.append('%s A%d %.3f: the span already holds %s at %.3f'
                               % (r['id'], track, float(r['at']), os.path.basename(clip_path(mpi)) if mpi else occ.GetName(),
                                  ((occ.GetStart(True) if self._sub(occ) else occ.GetStart()) - self.T0) * self.F))
                continue
            items = self.mp.AppendToTimeline([{'mediaPoolItem': have[norm(r['file'])], 'startFrame': s0, 'endFrame': s0 + n,
                                               'recordFrame': self.T0 + rec, 'trackIndex': track, 'mediaType': 2}])
            if not items:
                failed.append('%s A%d %.3f: AppendToTimeline returned nothing' % (r['id'], track, float(r['at'])))
                continue
            it = items[0]
            why = []
            if float(r['level_db']) != 0 and not set_volume(it, r['level_db']):
                why.append('AudioVolume refused')
            if r.get('fade_out_s'):
                if not it.SetFades({'FadeOut': min(int(round(float(r['fade_out_s']) * self.fps)), n)}):
                    why.append('SetFades refused')
            if why:
                failed.append('%s A%d %.3f: %s' % (r['id'], track, float(r['at']), ', '.join(why)))
            placed.append('%s %-9s A%d %.3f +%df %+g dB %s [%s]' % (r['id'], r.get('event', ''), track, float(r['at']), n,
                                                                    float(r['level_db']), os.path.basename(r['file']), r.get('gid', '')))
        for p in placed:
            self.out('+ ' + p)
        self.out('%d already placed, %d placed%s' % (kept, len(placed), ', %d NOT placed:' % len(blocked) if blocked else ''))
        for b in blocked:
            self.out('  blocked ' + b)
        for f in failed:
            self.out('  FAILED  ' + f)
        if left:
            self.out('PARTIAL: stopped at the %ds mark with %d row(s) to go (first %s): run the same --apply call again, '
                     'it lays only what is missing' % (BUDGET_S, len(left), left[0]['id']))
        ok = self.verify(quiet=True) and not blocked and not failed and not left
        self.save()
        if blocked:
            self.out('a blocked span is the creator\'s clip or a stale cue: --verify names it, --remove-extra or '
                     '--remove <ids> clears a stale one, then --apply again')
        return ok

    def remove(self, clips, dry=False):
        for c in clips:
            self.out('- A%d %8.3f -> %.3f %s%s' % (c['track'], c['start'], c['end'], os.path.basename(c['path']),
                                                   '  (%s)' % c['why'] if c.get('why') else ''))
        if dry:
            self.out('%d clip(s) would be removed (dry: nothing touched)' % len(clips))
            return True
        if not clips:
            self.out('nothing to remove')
            return True
        ok = self.tl.DeleteClips([c['item'] for c in clips], False)
        self.out('removed %d SFX clip(s): %s' % (len(clips), 'ok' if ok else 'DeleteClips REFUSED (a Resolve modal up?)'))
        self.save()
        return bool(ok)

    def targets(self, ids):
        tl, want, missing, seen = self.readback(), [], [], set()
        for i in ids:
            r = next((r for r in self.plan.rows if r['id'] == i), None)
            if r is None:
                missing.append('%s (no such plan row)' % i)
                continue
            m = self.match(r, tl, seen)
            if not m:
                missing.append('%s (not on the timeline)' % i)
                continue
            seen.add(id(m[0]))
            want.append(m[0])
        if missing:
            raise SystemExit('nothing removed: ' + ', '.join(missing))
        return want

    def save(self):
        name = self.proj.GetName()
        if name == 'Untitled Project':
            self.out('NOT saved: the project is "Untitled Project" (a save opens a name dialog that hangs the script); '
                     'save it under a name by hand')
            return False
        ok = self.pm.SaveProject()
        self.out('save: %s' % ('ok' if ok else 'FAILED (SaveProject returned %r: a Resolve modal up?)' % ok))
        return bool(ok)


def run(resolve, job, mode='apply', timeline=None, plan=None, ids=None, dry=False, out=print):
    """One MODE against the running Resolve -> True when it ended clean."""
    if not job:
        raise SystemExit('set JOB in the run_script_unsafe wrapper to the absolute projects/<job> folder')
    if mode not in MODES:
        raise SystemExit('MODE %r: one of %s' % (mode, ', '.join(MODES)))
    p = Plan(job, plan)
    note = p.stale_note()
    if note:
        out(note)
    lane = Lane(resolve, p, timeline, out)
    out('project "%s", timeline "%s" at %.3f fps, start frame %d' % (lane.proj.GetName(), lane.tl.GetName(), lane.fps, lane.T0))
    if mode == 'verify':
        return lane.verify()
    if mode == 'apply':
        return lane.apply()
    if mode == 'remove-extra':
        return lane.remove(lane.extras(), dry)
    if ids:
        return lane.remove(lane.targets(ids), dry)
    return lane.remove(lane.readback(libs=p.plan_libs), dry)      # the full clear: the PLAN's libraries, never a job-local cue


def wrapper(job, mode, timeline=None, plan=None, ids=None, dry=False):
    """The run_script_unsafe script for this job, with absolute paths."""
    g = ['import io', 'JOB=%r' % os.path.abspath(job), 'MODE=%r' % mode]
    if timeline:
        g.append('TIMELINE=%r' % timeline)
    if plan:
        g.append('PLAN=%r' % plan)
    if ids:
        g.append('IDS=%r' % list(ids))
    if dry:
        g.append('DRY=True')
    return '; '.join(g + ["exec(io.open(%r, encoding='utf-8').read())" % os.path.abspath(__file__)])


def shell_main(argv):
    if '-h' in argv or '--help' in argv:
        print(__doc__)
        return 0
    if not argv or argv[0].startswith('-'):
        raise SystemExit(__doc__)
    job, a = argv[0], argv[1:]
    flags = {'--apply': 'apply', '--verify': 'verify', '--remove': 'remove', '--remove-extra': 'remove-extra'}
    i, cmds, ids, opts, bad = 0, [], [], {}, []
    while i < len(a):
        x = a[i]
        i += 1
        if x in flags:
            cmds.append(flags[x])
            if x == '--remove':
                while i < len(a) and not a[i].startswith('-'):
                    ids += [v.strip() for v in a[i].split(',') if v.strip()]
                    i += 1
        elif x in ('--timeline', '--plan'):
            if i >= len(a) or not a[i].strip() or a[i].startswith('--'):
                raise SystemExit('%s needs a value' % x)
            opts[x] = a[i]
            i += 1
        elif x == '--dry':
            opts['--dry'] = True
        else:
            bad.append(x)
    if bad:
        raise SystemExit('not understood: %s: nothing done (--help lists the flags)' % ' '.join(bad))
    if len(cmds) != 1:
        raise SystemExit('one command: --apply, --verify, --remove [ids] or --remove-extra')
    mode = cmds[0]
    if opts.get('--dry') and mode not in ('remove', 'remove-extra'):
        raise SystemExit('--dry previews --remove and --remove-extra; %s has no dry run' % mode)
    p = Plan(job, opts.get('--plan'))                     # the offline half: refusals, files on disk
    note = p.stale_note()
    if note:
        print(note)
    try:
        shown = os.path.relpath(p.path)
    except ValueError:                                    # Windows: another drive has no relative path
        shown = p.path
    print('%s: %d rows on A%s from %d library file(s), checked offline'
          % (shown, len(p.rows), '/A'.join(str(t + 1) for t in p.tracks), len({r['file'] for r in p.rows})))
    print('Run it in Resolve: the davinci-resolve MCP tool run_script_unsafe, timeout 60, script:\n')
    print(wrapper(job, mode, opts.get('--timeline'), opts.get('--plan'), ids, opts.get('--dry')))
    return 0


if 'resolve' in globals():
    # inside Resolve: the wrapper set JOB (and MODE, TIMELINE, PLAN, IDS, DRY); every name below is the wrapper's to read
    run(globals()['resolve'], globals().get('JOB') or os.environ.get('RESOLVE_JOB', ''), globals().get('MODE', 'apply'),
        globals().get('TIMELINE'), globals().get('PLAN'), globals().get('IDS'), bool(globals().get('DRY')))
elif __name__ == '__main__':
    sys.exit(shell_main(sys.argv[1:]))
