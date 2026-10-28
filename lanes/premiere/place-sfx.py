#!/usr/bin/env python3
"""place-sfx.py: put a job's sfx-plan.json on the Premiere SFX tracks (pipeline step 6, Premiere lane).

  uv run lanes/premiere/place-sfx.py projects/<job> --apply     # place every row not yet on the timeline (and re-lay a moved one), set levels, read back, save
  uv run lanes/premiere/place-sfx.py projects/<job> --verify    # timeline readback vs sfx-plan.json (exit 1 on drift)
  uv run lanes/premiere/place-sfx.py projects/<job> --remove    # clear every SFX clip from the PLAN's libraries, only for a deliberate full replacement
  uv run lanes/premiere/place-sfx.py projects/<job> --remove --include-local   # …and the job's own audio/sfx-src cues with them
  uv run lanes/premiere/place-sfx.py projects/<job> --remove s004,s017 s020    # clear exactly those plan rows' clips (ids by commas and/or spaces)
  uv run lanes/premiere/place-sfx.py projects/<job> --remove-extra       # clear exactly the clips --verify calls extra
  uv run lanes/premiere/place-sfx.py projects/<job> --diff      # the timeline vs the plan: the creator's hand edits, the input for the next rule
  uv run lanes/premiere/place-sfx.py projects/<job> --adopt     # the LIVE timeline becomes the plan (backed up first): accepted hand edits stop reading as drift

  --plan <file>     the cut sheet, relative to the job (default hf-graphics/sfx-plan.json; an AD cut's is its own file)
  --sequence NAME   refuse unless the active sequence is NAME: the job guard (VE_SEQUENCE) and every read and write here
  --until T         the COPY WINDOW, for --adopt, --apply, --verify, --remove-extra and --diff: only rows and clips starting
                    before T seconds, and inside it EVERY clip on the SFX tracks counts, whatever folder it came from, so a
                    copy is exact (--remove-extra also takes a clip that sits on its row but fails --verify's level, slice
                    or tail line, for --apply to lay again); a cue before T that rings past it is held to, and laid
                    only up to, the sequence's OWN next cue at or after T on its track, which the window never touches
  --dry             with --remove / --remove-extra: list the clips that would go, touch nothing; with --adopt: print
                    what it would keep, change, add and drop, write nothing (any other command refuses it, as it
                    refuses an unknown flag or a value no flag takes, before it talks to Premiere)

--adopt reads every clip on the SFX tracks (every audio track but A1, the voice, and A5, the music) from any
folder and writes one row per clip: the id, gid and event of the plan row it matches (same file and track, `at`
within 1.5 frames), else a new h-id on the nearest placed graphic with event "hand". The source out is the
in-point plus the laid length, never Premiere's outPoint (stale after a clip.end write). It prints what it kept,
changed, added and dropped; an empty readback never empties a plan.

Copy the creator-tuned SFX of one sequence onto a variant of it (an AD cut). T is the FIRST FRAME where the two
sequences differ, in picture OR in SFX, and it sits at or before the target's own first cue: a lead-in whoosh laid a
frame or two before the target's own cut is the target's, so T goes before it, never on the cut after it (inside the
window that whoosh is foreign to the copy and --remove-extra takes it; the dry list marks a foreign clip that runs
past T as "the target's own lead-in?"). Read T off the sequence grid, in seconds:
  1. the source active:  --sequence "<job>" --adopt --plan hf-graphics/sfx-plan.ad.json --until T
  2. --sequence "<job> AD" --plan hf-graphics/sfx-plan.ad.json --remove-extra --dry     (read the list)
  3. the same without --dry, then the same with --apply, then with --verify
--adopt --until RECORDS the window in the plan's .meta.json, and every later command on that plan holds it: typed
again or left out, it is the same window; another T is refused (only --adopt moves it), and so is the bare full clear.
--adopt --until none clears it (the whole sequence adopted, no window recorded). The window is a VARIANT's: --adopt
refuses one on the job's own hf-graphics/sfx-plan.json (a --plan left out of step 1), which is the whole sequence.

A cue's START is held to HALF A FRAME of its row's `at` (or of the frame overwriteClip floors an off-grid `at` onto) by
--verify, --diff and --apply alike (2026-10-14): after a re-cut moved every row of whop-first-10k one frame, --verify read
all 70 cues green at 1.5 frames and --apply placed nothing. --apply now RE-LAYS a cue that sits on its row's file, track,
level and slice but off its `at` (removed, then laid at the plan's time, each named `~ moved`), before it saves; a cue
whose level or slice differs too is a hand edit, named by --verify and left alone. A cue the creator nudged on purpose
is taken into the plan with --adopt BEFORE an --apply, or the --apply puts it back.

Every clip on the SFX tracks answers for ONE row by file and start, the clip on the row ahead of a copy a frame off it,
and a second copy is extra: --verify fails it and --remove-extra takes it. Only a SECTION's plan is scoped to its span;
a whole job's plan reads every cue on the sequence (its `duration` hid the four g20 cues a re-cut left 4 s past the new
end, whop-first-10k 2026-10-15). A cue ringing past the last V1 frame fails --verify, and no cue there is exempt.

A SECTION sub-job (graphics-plan.json carries `timeline_offset`): --apply, --adopt, --remove and --remove-extra refuse
before they read or write a cue, and --verify and --diff report, when the section's run of its own media on the live V1
does not start at the offset (or at the EDL's first `_timeline`) within half a sequence frame. A creator ripple had
moved the section, and the graphics placer re-laid a whole second set at the old offset (2026-09-28); these cues
carry the same exposure (job_guard.section_moved). `workflows/ripple-cut.py` moves the offset and the cues.

--apply, --verify, --diff and --adopt first say when the plan was derived from an older placement.json (a graphic
moved since, so its cues sit where it used to be), naming the moved graphics; a graphic that moved together with its
cues (a re-cut, workflows/ripple-cut.py) is not stale. The record is the plan's `<plan>.meta.json`, written by
workflows/sfx-plan.py (its --record for a plan it did not write) and by --adopt.

The plan is universal (workflows/sfx-plan.py); this is the HOW for Premiere. Rows carry
{at, file, src_in, src_out, level_db, track}. Mechanics, all read back before they are believed:

  - the library file is imported ONCE into an `sfx` bin (found by media path on later runs)
  - audio tracks are provisioned with QE addTracks so the plan's track index exists (appends, so
    nothing already placed moves)
  - each slice is placed by setting the project item's in/out and DOM overwriteClip at
    at + 1e-4 (the replay's floor-nudge), then the in/out are cleared again — and the clip's
    in-point is WRITTEN BACK, because overwriteClip floors it to the sequence grid (up to a
    frame of phantom source drift), then read back before it is believed — a write-back that
    does not hold fails the run at the END, naming every affected row, never mid-batch
  - the level is the clip's intrinsic Volume > Level, through `clip_level.lvl_v` — the encoding's
    ONE code home; its prose home is lanes/premiere/lab-notes.md, and neither is restated here
"""
import importlib.util, json, math, os, re, shutil, subprocess, sys, time
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from pathlib import Path
from job_guard import require_job_project, section_moved, job_root
from pes import es, paged                     # lanes/premiere/pes.py: the bridge's one output contract
from clip_level import lvl_v, v_lvl           # lanes/premiere/clip_level.py: the ONE Volume > Level encoding

# the plan's placement record (which placement.json its rows were derived from) has ONE home, the planner
_spec = importlib.util.spec_from_file_location('sfx_plan', Path(__file__).resolve().parents[2] / 'workflows' / 'sfx-plan.py')
planner = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(planner)

BRIDGE = Path(__file__).resolve().parent / 'premiere-bridge.mjs'
NUDGE = 1e-4
MUSIC = 4            # A5: the music role on presets/youtube/default/README.md's track map, never an SFX track
# Is a clip's media one of the SFX this script reads (LIBS = the folders, or null = EVERY folder: the copy window
# and --adopt)? Every folder still means AUDIO FILES: a clip of a video file on an SFX track is picture sound (a
# second raw channel, a lip-sync take), and the copy window's --remove-extra would otherwise delete it.
IS_LIB = r"""function isLib(p){ if (!LIBS) return p !== "" && !/\.(mp4|mov|m4v|mxf|avi|mkv|mts|m2ts|webm|mpg|mpeg)$/i.test(p);
    for (var k = 0; k < LIBS.length; k++) if (p.indexOf(LIBS[k]) === 0) return true; return false; }"""
# THE SOURCE-IN TOLERANCE, one number for every command here, so --verify and --diff hold the same
# line. Half a frame since the `clip.inPoint` write-back was PROVEN on a live Premiere (the 2026-09-23 overnight
# run: 8 off-grid rows tick-exact, the bounce under a sample off). A cue laid before the write-back existed carries
# overwriteClip's sequence-grid floor (about 0.94 frame at 23.976) and now reads as drift: --remove <ids> and
# --apply lays it again, exact.
SRC_TOL_FRAMES = 0.5
# place() re-writes a laid clip's in-point and end only when they are more than PIN_TOL off the row, so a cue it laid
# can legitimately sit up to PIN_TOL off; --adopt reads its start slice and tail to ADOPT_TOL, just above that line
# (a one-frame trim is 41.7 ms at 23.976, far past it) so an untouched cue is never adopted as a hand edit.
PIN_TOL = 0.002
ADOPT_TOL = 0.0025


def sh(*cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"{' '.join(cmd[:3])} failed:\n{r.stderr or r.stdout}")
    return r.stdout


def probe_fps(path):
    r = sh('ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', path)
    n, _, d = r.strip().split('\n')[0].strip(',').partition('/')
    return float(n) / float(d or 1)


# the command-line helpers are the planner's too: `--remove s025 s042` reads every id (arg_list), and an unknown
# flag or a value no flag takes is refused before anything talks to Premiere (check_args)
arg_list, opt, check_args = planner.arg_list, planner.opt, planner.check_args
COMMANDS = ('--adopt', '--apply', '--verify', '--remove-extra', '--remove', '--diff')


class Placer:
    # class defaults, so every method reads as the plain run on a Placer built without __init__ (the tests)
    until = None          # --until T: the copy window
    every = False         # inside the copy window every clip on the SFX tracks counts, whatever folder it came from
    sequence = None       # --sequence NAME: the one active sequence every script here accepts
    fence = {}            # inside the copy window: {track: starts of the timeline's OWN clips at or after T} (readback)
    span = None
    v1_end = None         # the end of the last V1 clip, read with every readback: no cue plays past the picture
    off = 0.0
    section = False       # graphics-plan.json carries timeline_offset: the live V1 is checked against it (check_section)

    def __init__(self, job, plan=None, sequence=None, until=None, adopt=False):
        self.job = Path(job).resolve()
        self.hf = self.job / 'hf-graphics'
        # --plan names another cut sheet (an AD cut's), relative to the job: the placer used to hard-open
        # sfx-plan.json, so the AD's SFX could be laid and verified only through a scratch subclass (2026-09-23)
        self.plan_path = Path(plan) if plan and Path(plan).is_absolute() else self.job / (plan or 'hf-graphics/sfx-plan.json')
        # --until none (--adopt only, main refuses it elsewhere): the recorded window is cleared, never inherited
        clear = until == 'none'
        if clear: until = None
        # --sequence, else VE_SEQUENCE (the job guard reads the same pair): head() holds every script here to it
        self.sequence, self.until, self.every = sequence or os.environ.get('VE_SEQUENCE') or None, until, until is not None
        if self.plan_path.exists(): rows = json.load(open(self.plan_path, encoding="utf-8"))
        elif adopt and self.plan_path.parent.is_dir(): rows = []   # --adopt writes the plan it names: a new one starts empty
        elif adopt: sys.exit(f'✗ no folder {self.plan_path.parent}: --plan names a file in the job (hf-graphics/sfx-plan.ad.json), nothing adopted')
        else: sys.exit(f'✗ no {self.plan_path}: nothing to place, verify or remove')
        if not rows and not adopt:
            sys.exit(f'{self.plan_path.name} has no rows: nothing to place, verify or remove (an empty plan must never mean "every clip")')
        # `workflows/ripple-cut.py` marks a cue whose anchor a re-cut DELETED with `"ripple": "orphaned"` and
        # leaves it at its old time — nothing can invent a new one. The marker had no consumer at all until
        # 2026-09-19, so those cues went down at their PRE-RECUT frames, under a freshly stamped plan. Refuse
        # and name them: re-anchoring one is a hand decision, never a placer's guess. (--adopt is exempt: it
        # rewrites the plan from the timeline, and a matched row keeps its marker for the next --apply to name.)
        dead = [f"{r.get('id', '?')} {r.get('event', '?')} at {float(r.get('at') or 0):.3f}s [{r.get('gid', '?')}]"
                for r in rows if r.get('ripple') == 'orphaned']
        if dead and not adopt:
            sys.exit(f'✗ {len(dead)} cue(s) are on a DEAD ANCHOR (`"ripple": "orphaned"`, left at their pre-recut '
                     f'times by a re-cut). Nothing touched:\n' + '\n'.join(f'    {d}' for d in dead)
                     + '\n  Re-anchor each row (drop its `ripple` key once its `at` is right) or delete it, then re-run.')
        # every folder the job's sounds can come from, so the readback SEES them all: the preset library, plus the
        # job's own audio/sfx-src (a one-off cue downloaded for this piece). A sound the readback cannot see is
        # invisible to --verify and --diff, which is how a cue goes missing without anything failing. SEEING a
        # job-local cue is not licence to DELETE it: the bare full clear takes `plan_libs` only (see main).
        self.plan_libs = sorted({str(Path(r['file']).parent) for r in rows})
        self.libs = sorted(set(self.plan_libs) | {str(self.job / 'audio' / 'sfx-src')})
        self.floored = []                   # rows whose in-point write-back did not hold, reported by apply()
        pp = self.job / 'graphics-plan.json'
        plan = json.load(open(pp, encoding="utf-8")) if pp.exists() else {}
        gfx = self.gfx = json.load(open(self.hf / 'placement.json', encoding="utf-8"))
        # the grid is the SEQUENCE's: the plan's rate wins when it names one (a section whose raw runs at
        # another rate), else a placed render — which a job with its renders deleted has not got
        if plan.get('fps'):
            n, _, d = str(plan['fps']).partition('/'); fps = float(n) / float(d or 1)
        else:
            f = next((r['file'] for r in gfx if os.path.exists(r['file'])), None)
            if not f:
                sys.exit('✗ no placed graphics render is on disk and graphics-plan.json names no "fps": nothing '
                         'can give the frame grid. Re-render the '
                         'graphics (hf-graphics/PROJECT.md) or add "fps" to the plan, then re-run.')
            fps = probe_fps(f)
        self.F = 1 / fps
        # the COPY WINDOW a plan was adopted with is recorded beside it, and holds every later command: a windowed plan
        # carries no row after T, so run without the window --remove-extra took the target's OWN cues after T (its call
        # to action) and saved (the 2026-09-23 live run). Left out it is the recorded one; another T is refused.
        mp = planner.meta_path(self.plan_path)
        rec = json.loads(mp.read_text(encoding="utf-8")).get('until') if self.plan_path.exists() and mp.exists() and not clear else None
        if rec is not None and until is None:
            until = rec; print(f"· {self.plan_path.name} was adopted with --until {rec:.3f}: that copy window holds this command")
        elif rec is not None and abs(until - rec) > self.F / 2 and not adopt:
            sys.exit(f"✗ {self.plan_path.name} was adopted with --until {rec:.3f}, not {until:.3f}: nothing read or written. "
                     "Leave --until out (the recorded window holds), or --adopt again with the new T on the source sequence")
        # the window is a VARIANT's (an AD cut's plan): on the job's own plan it windowed the organic cut for good, since
        # only a fresh planner run cleared it (a --plan left out of the recipe's step 1, the 2026-09-23 review)
        if adopt and until is not None and self.plan_path.resolve() == (self.hf / 'sfx-plan.json').resolve():
            sys.exit(f"✗ --adopt --until {until:.3f} on {self.plan_path.name}, the job's own plan: nothing read or written. The copy "
                     "window is a variant's (--plan hf-graphics/sfx-plan.ad.json); --adopt --until none adopts the whole "
                     "sequence and clears a recorded window")
        self.until, self.every = until, until is not None
        # a SECTION sub-job (graphics-plan.json carries timeline_offset + duration): only the SFX clips inside the
        # section's span are this plan's business; another section's cues are neither drift nor extra (2026-09-14).
        # A whole job's plan owns every cue on the sequence: its `duration` scoped it too until 2026-10-15, and once a
        # re-cut shortened the plan the four g20 cues left 4 s past the new end were invisible to --verify and
        # --remove-extra alike ("0 extra", whop-first-10k)
        self.span = None
        self.off = float(plan.get('timeline_offset') or 0.0)
        self.section = plan.get('timeline_offset') is not None
        if self.section or job_root(self.job) != self.job:
            off = self.off; self.span = (off - 0.5, off + float(plan.get('duration') or 1e9) + 0.5)
        self.all_rows = rows                # every row, the --until window's too: a cue after T still truncates one before it
        self.rows = [r for r in rows if self.before(r['at'])]
        if until is not None and not self.rows and not adopt:
            sys.exit(f'{self.plan_path.name} has no rows before {until:.3f}s: nothing to place, verify or remove '
                     '(an empty window must never mean "every clip")')
        self.tracks = sorted({r['track'] for r in self.rows})
        # the job guard enforces VE_SEQUENCE too (lanes/premiere/job_guard.py); head() holds every script here to it
        if sequence: os.environ['VE_SEQUENCE'] = sequence
        require_job_project(es, self.job)   # every command here reads or writes the ACTIVE sequence (lanes/premiere/job_guard.py)

    def before(self, t):
        """Inside the --until window: starting at least HALF A FRAME before T, so a cue ON the cut stays outside
        it whether T was read off the sequence grid or typed to the plan's four decimals."""
        return self.until is None or t < self.until - self.F / 2

    def head(self):
        """The first statement of every script here: the active sequence, refused when --sequence (or VE_SEQUENCE)
        names another.
        The job guard checks once at startup; this holds every later read and write to the same sequence, so a
        click on another timeline mid-run stops the run instead of landing on it."""
        return (r'var seq = app.project.activeSequence; if (!seq) return "ERROR: no active sequence"; var SEQ = %s; '
                r"""if (SEQ !== null && seq.name !== SEQ) return "ERROR: the active sequence is '" + seq.name + "', not '" + SEQ + "': nothing read or written";"""
                % json.dumps(self.sequence))

    def readback(self, libs=None, every=None):
        """The SFX clips on the timeline: every audio track but A1 (the voice) and A5 (the music), from the given
        folders (default: every folder the job's sounds come from), or from ANY folder when `every` (the copy
        window, and --adopt)."""
        every = self.every if every is None else every
        LIBS = 'null' if every else json.dumps(self.libs if libs is None else libs)
        # PAGED: a media path per clip puts a whole-timeline dump over the bridge's 65535-char return cap on a
        # long job, and the caller sees that as JSON dying mid-string rather than as an error (pes.py § paged).
        # every clip carries `v1`, the end of the last V1 clip (the picture's last frame), read in the same call
        tl = paged(lambda n0, n1: r"""
(function(){
  %s
  var LIBS = %s, MUSIC = %d, N0 = %d, N1 = %d, out = [], v1 = null;
  %s
  if (seq.videoTracks && seq.videoTracks.numTracks) { var vt = seq.videoTracks[0];
    for (var j = 0; j < vt.clips.numItems; j++) if (v1 === null || vt.clips[j].end.seconds > v1) v1 = vt.clips[j].end.seconds; }
  for (var t = 1; t < seq.audioTracks.numTracks; t++) { if (t === MUSIC) continue;
    var tr = seq.audioTracks[t];
    for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i];
      var p = c.projectItem ? c.projectItem.getMediaPath() : "";
      if (!isLib(p)) continue;
      var lvl = null, kf = false;
      for (var k = 0; k < c.components.numItems; k++) { var cm = c.components[k];
        if (cm.displayName !== "Volume") continue;
        for (var q = 0; q < cm.properties.numItems; q++) if (cm.properties[q].displayName === "Level") {
          lvl = cm.properties[q].getValue(); try { kf = cm.properties[q].isTimeVarying(); } catch (e) {} } }
      out.push({track: t, start: c.start.seconds, end: c.end.seconds, srcIn: c.inPoint.seconds, srcOut: c.outPoint.seconds, path: p, v: lvl, kf: kf, v1: v1}); }
  }
  return JSON.stringify(out.slice(N0, N1));
})()""" % (self.head(), LIBS, MUSIC, n0, n1, IS_LIB))
        # the half second before the section is for ITS lead-ins, which run into it; a cue that ENDS before the section
        # starts is the previous section's last sound, never this plan's extra (the intro's last scissors read as an extra
        # on how-it-works and blocked every save, 2026-10-03)
        self.v1_end = next((c['v1'] for c in tl if c.get('v1') is not None), None)
        # a cue past the picture's last frame is no section's: it is read whatever span the plan has
        if self.span: tl = [c for c in tl if self.past(c) or (self.span[0] <= c['start'] <= self.span[1]
                            and not (c['start'] < self.off and c['end'] <= self.off + 1e-3))]
        if self.until is not None:
            # the clips at or after T are never read or written through the window, but one still cuts short the cue
            # before it on its track (tail(), place()): keep where they start
            self.fence = {}
            for c in tl:
                if not self.before(c['start']): self.fence.setdefault(c['track'], []).append(c['start'])
            tl = [c for c in tl if self.before(c['start'])]
        return tl

    def match(self, r, tl):
        return [c for c in tl if c['path'] == r['file'] and c['track'] == r['track'] and abs(c['start'] - r['at']) <= 1.5 * self.F]

    def best(self, r, cs):
        """The ONE clip of `cs` (row r's matches) that answers for the row: one that passes the row's check over one that
        does not, then the nearest start. A second clip of the row's file is extra, never the row's: a re-cut leaves
        copies a frame off their rows (a Camera Clicks at 76.493 for a row at 76.451, whop-first-10k 2026-10-15), and
        taking whichever the track listed first handed the row a copy listed ahead of its own clip, and the own clip
        to --remove-extra."""
        return min(cs, key=lambda c: (self.check(r, c) is not None, abs(c['start'] - r['at'])), default=None)

    def past(self, c):
        """Clip c rings past the last V1 frame (more than half a frame): the export is the whole sequence, so it plays
        over black. Unknown V1 (a readback without one) is never past."""
        return self.v1_end is not None and c['end'] > self.v1_end + self.F / 2

    def exempt(self, c):
        """A job-local hand cue is left alone (local() below), except inside the copy window, which is exact, and past
        the picture's last frame, where no cue is anyone's (a re-cut's leftover lengthens the export with black)."""
        return not self.every and self.local(c) and not self.past(c)

    def local(self, c):
        """A cue out of the job's OWN audio/sfx-src that answers for no plan row: a one-off the creator placed
        by hand. The readback sees it on purpose, so --diff names it and it cannot go missing in silence — but
        it is NOT this plan's drift and NOT this plan's to delete. Live state that disagrees with a write is
        the creator's hand edit (CLAUDE.md § Lab Notes): report it, leave it alone. Counting it as `extra`
        made --verify unpassable and apply() refuse to save on every job carrying one, and handed the whole
        set to --remove-extra."""
        return c['path'].startswith(str(self.job / 'audio' / 'sfx-src')) \
            and not any(c['path'].startswith(l) for l in self.plan_libs)

    def tail(self, r, rows=None):
        """The END row r's clip should have, and its source out: the slice, truncated by the next cue on its track,
        because overwriteClip truncates a repeated sound when the next cue occupies its track. Checked against the
        timeline inside the --until window, the next cue after T is the TIMELINE's own (the fence), never the plan's:
        the window copies onto a sequence whose cues after T are its own (an AD's call to action), and a plan that
        knew only the source's made a pre-T cue ringing into one read as drift, and --apply lay it over that cue's
        head where nothing reads again (2026-09-23 review). `rows` (--adopt) names the neighbours outright."""
        end = r['at'] + r['src_out'] - r['src_in']
        if self.until is not None:
            # --adopt's neighbours too: the plan's rows INSIDE the window plus the fence, the very line check() holds
            # (a cross-T cue read back cut by the fence was otherwise re-adopted as changed, the live run's h003)
            nb = self.rows if rows is None else [n for n in rows if self.before(n['at'])]
            next_at = [n['at'] for n in nb if n['track'] == r['track'] and n['at'] > r['at']] \
                + [s for s in self.fence.get(r['track'], ()) if s > r['at']]
        else:
            next_at = [n['at'] for n in (self.all_rows if rows is None else rows) if n['track'] == r['track'] and n['at'] > r['at']]
        if next_at: end = min(end, min(next_at))
        return end, r['src_in'] + end - r['at']

    def start_off(self, r, c):
        """Clip c starts more than HALF A FRAME off row r's `at`, and off the frame overwriteClip floors an off-grid
        `at` onto (place() lays at `at` + NUDGE, which Premiere floors to the sequence grid), so a cue laid there is right.
        The line was 1.5 frames outside the copy window: a re-cut that moved every row one frame read green (2026-10-14)."""
        land = math.floor((r['at'] + NUDGE) / self.F + 1e-6) * self.F
        return min(abs(c['start'] - r['at']), abs(c['start'] - land)) > self.F / 2

    def misplaced(self, r, c):
        """Clip c is row r's cue (its file, track, level and slice) laid off the row's time: the plan moved under it (a
        re-cut, workflows/ripple-cut.py). --apply re-lays it; any other difference is a hand edit, left to the creator."""
        return self.start_off(r, c) and c['v'] is not None and abs(v_lvl(c['v']) - r['level_db']) <= 0.2 \
            and abs(c['srcIn'] - r['src_in']) <= SRC_TOL_FRAMES * self.F

    def check(self, r, c):
        """What is wrong with clip c as row r's cue, None when it is right: the one set of lines --verify holds."""
        got = v_lvl(c['v']) if c['v'] is not None else None
        # Verify the intended tail, not the untrimmed source slice or just its in-point.
        end, src_out = self.tail(r)
        # inside the COPY WINDOW the copy is exact: the tail held to half a frame too, which the window reaches (it
        # lays through the in-point and end write-back). At 1.5 frames a creator's one-frame nudge, slip or trim on the
        # source was adopted, and the target's stale clone still read green on every command (2026-09-23 review).
        tol = self.F / 2 if self.every else 1.5 * self.F
        if got is None or abs(got - r['level_db']) > 0.2:
            return f"level {got} dB, plan {r['level_db']:+g}"
        if abs(c['srcIn'] - r['src_in']) > SRC_TOL_FRAMES * self.F:
            return f"source in {c['srcIn']:.3f}, plan {r['src_in']:.3f}"
        if self.start_off(r, c):
            return f"start {c['start']:.3f}, plan {r['at']:.3f} ({(c['start'] - r['at']) / self.F:+.1f} fr)"
        if abs(c['srcIn'] + (c['end'] - c['start']) - src_out) > tol or abs(c['end'] - end) > tol:
            # the source out is DERIVED (in + laid duration): after a clip.end write Premiere's outPoint readback is STALE
            # (the same stale-outPoint read as the V1 clock error of 2026-09-21), so it cannot be compared directly
            return f"tail {c['end']:.3f} / source out {c['srcIn'] + (c['end'] - c['start']):.3f}, plan {end:.3f} / {src_out:.3f}"
        return None

    def check_section(self, refuse=True):
        """A SECTION's `timeline_offset` against the live V1 (job_guard.section_moved), read once per run: the writing
        commands refuse on a moved section (--apply before its first write, the track provisioning), --verify and --diff
        report it."""
        if not self.section: return None
        if not hasattr(self, '_moved'):
            self._moved = section_moved(es, self.head(), self.job, self.off, self.F, self.job / 'transcript' / 'cuts.json',
                                        'graphics-plan.json')
        if self._moved and refuse: sys.exit(f'{self._moved}\n  Nothing written.')
        return self._moved

    def verify(self, quiet=False):
        moved = self.check_section(refuse=False)
        if moved: print(moved)
        tl = self.readback(); ok = not moved; seen = set()
        for r in self.rows:
            c = self.best(r, [c for c in self.match(r, tl) if id(c) not in seen])      # a clip answers for ONE row
            if c is None:
                ok = False; print(f"✗ {r['id']} {r['event']:<8} A{r['track'] + 1} {r['at']:.3f} {os.path.basename(r['file'])}: not on the timeline"); continue
            seen.add(id(c))
            bad = self.check(r, c)
            if self.past(c):
                ok = False; print(f"✗ {r['id']}: rings to {c['end']:.3f}, past the last V1 frame at {self.v1_end:.3f} (the row is "
                                  "off the cut: re-time the plan, workflows/ripple-cut.py)")
            elif bad:
                ok = False; print(f"✗ {r['id']}: {bad}")
            elif not quiet:
                print(f"✓ {r['id']} A{c['track'] + 1} {c['start']:.3f} → {c['end']:.3f} {r['level_db']:+g} dB {os.path.basename(c['path'])}")
        rest = [c for c in tl if id(c) not in seen]
        loc = [c for c in rest if self.exempt(c)]                    # hand-placed job-local cues: named, never failed
        extra = [c for c in rest if not self.exempt(c)]
        if extra: ok = False
        name = self.plan_path.name
        for c in extra: print(f"⚠ extra SFX clip on A{c['track'] + 1} at {c['start']:.3f}: {os.path.basename(c['path'])}, not in {name}"
                              + (f", past the last V1 frame at {self.v1_end:.3f}" if self.past(c) else '') + " (--remove-extra takes it)")
        for c in loc: print(f"· job-local cue on A{c['track'] + 1} at {c['start']:.3f}: {os.path.basename(c['path'])}, hand-placed and not in {name} (left alone)")
        print(f"{'ALL PLACED' if ok else 'DRIFT'}: {len(self.rows)} rows" + (f" before {self.until:.3f}s" if self.until is not None else '')
              + f", {len(extra)} extra" + (f", {len(loc)} job-local" if loc else ''))
        return ok

    def extras(self):
        """The timeline's SFX clips that answer for no plan row: exactly what verify() reports as extra, which
        is why a job-local hand-placed cue is not one of them — --remove-extra would otherwise take the very
        cues the readback was widened to make visible. Inside the COPY WINDOW (--until) the target must end up
        exact, so every folder counts there and a clip that sits on its row but fails the row's check goes too
        (carrying `why`), for --apply to lay again: the one hand copy re-laid every clip its level had changed."""
        tl = self.readback(); seen = set(); stale = []
        for r in self.rows:
            c = self.best(r, [c for c in self.match(r, tl) if id(c) not in seen])     # verify()'s one clip per row
            if c is None: continue
            seen.add(id(c))
            bad = self.every and self.check(r, c)
            if bad: stale.append(dict(c, why=bad))
        foreign = [c for c in tl if id(c) not in seen and not self.exempt(c)]
        # a foreign clip that runs past T is most likely the TARGET's own lead-in to its cue after T (a whoosh two frames
        # before its cut): T was set after it. Marked for the --dry read, never silently one of the list
        return stale + [dict(c, why="runs past T: the target's own lead-in? then T goes before it")
                        if self.until is not None and c['end'] > self.until
                        else dict(c, why=f"past the last V1 frame at {self.v1_end:.3f}") if self.past(c) else c for c in foreign]

    def diff(self):
        """The creator's hand edits, read off the timeline against the plan: the input for the next rule."""
        tl = self.readback(); F = self.F; used = set(); n = 0
        lv = lambda v: round(v_lvl(v), 1) if v is not None else None
        for r in self.rows:
            c = next((c for i, c in enumerate(tl) if id(c) not in used and c['path'] == r['file'] and c['track'] == r['track'] and abs(c['start'] - r['at']) <= 1.5 * F), None)
            moved = c is None
            if c is None:
                near = [(i, c) for i, c in enumerate(tl) if id(c) not in used and c['path'] == r['file'] and abs(c['start'] - r['at']) <= 1.0]
                if near:
                    i, c = min(near, key=lambda ic: abs(ic[1]['start'] - r['at'])); used.add(id(c)); n += 1
                    print(f"MOVED    {r['id']} {r['event']:<9} {os.path.basename(r['file'])[:22]:22} {r['at']:8.3f} -> {c['start']:.3f} ({(c['start'] - r['at']) / F:+.1f} fr)" + (f" A{r['track'] + 1}->A{c['track'] + 1}" if c['track'] != r['track'] else '') + f"  [{r['gid']} {r['note'][:24]}]")
                else:
                    print(f"REMOVED  {r['id']} {r['event']:<9} {os.path.basename(r['file'])[:22]:22} {r['at']:8.3f}  [{r['gid']} {r['note'][:24]}]"); n += 1; continue
            else: used.add(id(c))
            if c['v'] is not None and abs(lv(c['v']) - r['level_db']) > 0.2:
                print(f"LEVEL    {r['id']} {r['event']:<9} {os.path.basename(r['file'])[:22]:22} {r['at']:8.3f}  {r['level_db']:+g} -> {lv(c['v']):+.1f} dB  [{r['gid']} {r['note'][:24]}]"); n += 1
            if abs(c['srcIn'] - r['src_in']) > SRC_TOL_FRAMES * F:   # the same line --verify holds, so it names what verify fails on
                print(f"SLICE    {r['id']} {r['event']:<9} {os.path.basename(r['file'])[:22]:22} {r['at']:8.3f}  src {r['src_in']:.3f} -> {c['srcIn']:.3f}  [{r['gid']} {r['note'][:24]}]"); n += 1
            elif self.every and not moved and self.check(r, c) and not self.check(r, c).startswith('level'):
                # the window's half-frame line (a one-frame nudge or trim): what --verify fails on, --diff names
                print(f"WINDOW   {r['id']} {r['event']:<9} {os.path.basename(r['file'])[:22]:22} {r['at']:8.3f}  {self.check(r, c)}  [{r['gid']} {r['note'][:24]}]"); n += 1
            elif not self.every and not moved and self.start_off(r, c):
                # the half-frame start line --verify holds: a cue a re-cut left a frame early is named, never 0 differences
                print(f"MOVED    {r['id']} {r['event']:<9} {os.path.basename(r['file'])[:22]:22} {r['at']:8.3f} -> {c['start']:.3f} ({(c['start'] - r['at']) / F:+.1f} fr)  [{r['gid']} {r['note'][:24]}]"); n += 1
        for c in tl:
            if id(c) not in used:
                # the source out is DERIVED, never c['srcOut']: Premiere's outPoint reads stale after a clip.end write
                print(f"ADDED    A{c['track'] + 1} {c['start']:8.3f}-{c['end']:.3f} {os.path.basename(c['path'])[:26]:26} src {c['srcIn']:.2f}-{c['srcIn'] + c['end'] - c['start']:.2f} {lv(c['v'])!s:>6} dB"); n += 1
        print(f"{n} difference(s) between the timeline and {self.plan_path.name}")
        return n

    def warn_stale(self):
        """A plan derived from an OLDER placement.json reads 0 differences against a timeline whose graphic moved:
        the cues still sit where the graphic used to be (a moved g7, 2026-09-22). Name the moved graphics first.
        The remedy is the plan's own: the planner writes only sfx-plan.json, so another plan (an AD cut's) is
        answered on the lane, and a plain planner re-run is never named, since it replaces the approved rows."""
        moved = planner.stale_gids(self.plan_path, self.hf)
        name, mp = self.plan_path.name, planner.meta_path(self.plan_path)
        # the remedy is a command to paste: forward slashes, which every shell and Python take (backslashes from
        # relpath on Windows are escapes to Git Bash, so the pasted path lost its separators)
        job = Path(os.path.relpath(self.job) if self.job.resolve().is_relative_to(Path.cwd().resolve()) else self.job).as_posix()
        own = self.plan_path.resolve() == (self.hf / 'sfx-plan.json').resolve()
        plan = '' if own else f' --plan {Path(os.path.relpath(self.plan_path, self.job)).as_posix()}'
        if moved is None:
            print(f"⚠ {name} has no placement record ({mp.name}): it predates the staleness check, so a graphic that moved "
                  f"since it was derived cannot be named. When the timeline's cues are right and --verify is green, record the "
                  f"current placement: uv run workflows/sfx-plan.py {job} --record{plan} (it changes no row)")
        elif moved and not own:
            print(f"⚠ {name} was derived from an older placement.json (moved since: {', '.join(moved)}): move those graphics' "
                  f"cues on this sequence (or copy them over again, the --until recipe in --help), then "
                  f"uv run lanes/premiere/place-sfx.py {job}{plan} --adopt (with the --until it was adopted with)")
        elif moved and json.loads(mp.read_text(encoding="utf-8")).get('source') == 'adopt':
            print(f"⚠ {name} was adopted against an older placement.json (moved since: {', '.join(moved)}): move those "
                  f"graphics' cues on the timeline and --adopt again, or re-plan only them: "
                  f"uv run workflows/sfx-plan.py {job} --merge {','.join(moved)}")
        elif moved:
            print(f"⚠ {name} was derived from an older placement.json: re-run workflows/sfx-plan.py for the moved graphics "
                  f"only: uv run workflows/sfx-plan.py {job} --merge {','.join(moved)} (moved since: {', '.join(moved)}; "
                  "the approved rows of every other graphic stay as they are)")
        return moved

    def adopt(self, dry=False):
        """The LIVE timeline INTO the plan. The creator's accepted swaps (another sound, another slice, another
        level) read as missing + extra on every --verify with nothing to write them back, so a finished job stayed
        red forever (2026-09-23: "our current timeline is the source of truth"). Every clip on the SFX tracks, from
        any folder, becomes a row; a row it matches keeps its id, gid and event (and stays byte-identical when
        nothing changed), a clip no row answers for gets a new h-id on the nearest placed graphic. Inside --until
        only the window is rewritten: rows at or after T stay as they were. The plan is backed up first; `dry`
        prints the same report and writes nothing."""
        if self.plan_path.exists():
            self.warn_stale()       # adopting on a stale plan ratifies the cues a moved graphic left behind: say so first
        tl = sorted(self.readback(every=True), key=lambda c: (c['start'], c['track']))
        if not tl: sys.exit(f'✗ no clip on the SFX tracks{" before %.3fs" % self.until if self.until is not None else ""}: '
                            f'nothing adopted, {self.plan_path.name} unchanged (an empty readback never empties a plan)')
        ref, seeded = self.all_rows, None
        default = self.hf / 'sfx-plan.json'
        if not self.plan_path.exists() and default.exists() and default.resolve() != self.plan_path.resolve():
            ref, seeded = json.load(open(default, encoding="utf-8")), default.name   # a NEW plan keeps the ids the timeline was laid from
        pre = [r for r in ref if self.before(r['at'])]
        post = [r for r in self.all_rows if not self.before(r['at'])]
        nums = [int(m.group(1)) for r in ref + post for m in [re.fullmatch(r'h(\d+)', str(r.get('id', '')))] if m]
        nxt = iter(range(max(nums, default=0) + 1, 10 ** 6))
        gfx = [g for g in self.gfx if g.get('kind') != 'captions']      # the caption layer spans the whole cut
        def nearest(t):
            t -= self.off                                               # a section's placement is section-relative
            inside = lambda g: 0.0 if g['start'] <= t <= g['end'] else min(abs(t - g['start']), abs(t - g['end']))
            return min(gfx, key=lambda g: (inside(g), abs(t - g['start'])))['id'] if gfx else '?'
        used, rows, kept, changed, added = set(), [], [], [], []
        for c in tl:
            clip = f"A{c['track'] + 1} {c['start']:.3f} {os.path.basename(c['path'])}"
            if c['v'] is None: print(f"⚠ {clip}: no Volume > Level to read, left out"); continue
            if c.get('kf'): print(f"⚠ {clip}: its Level is keyframed; adopted at the value it reads now, and a plan row cannot carry the ramp")
            db = round(v_lvl(c['v']), 1)
            # 6 decimals: at 4 the copy laid on the AD sat 0.4 samples off and timeline-dump --diff read 3 differences
            new = dict(at=round(c['start'], 6), file=c['path'], src_in=round(c['srcIn'], 6),
                       src_out=round(c['srcIn'] + c['end'] - c['start'], 6),   # never outPoint: stale after a clip.end write
                       level_db=int(db) if db == int(db) else db, track=c['track'])
            m = [r for r in pre if id(r) not in used and r['file'] == c['path'] and r['track'] == c['track']
                 and abs(r['at'] - c['start']) <= 1.5 * self.F]
            if not m:
                rows.append(dict(id=f'h{next(nxt):03d}', gid=nearest(c['start']), event='hand', **new,
                                 note='adopted from the timeline', hand=True))
                added.append(rows[-1]); continue
            r = min(m, key=lambda r: abs(r['at'] - c['start'])); used.add(id(r))
            # the start, the slice and the level are compared TIGHT (a one-frame nudge is an edit); the tail below
            if all(abs(r[k] - new[k]) <= ADOPT_TOL for k in ('at', 'src_in')) and abs(r['level_db'] - new['level_db']) <= 0.05:
                rows.append(r); kept.append((r, c, new))                # unchanged: the row itself, byte for byte
            else:
                rows.append(dict(r, **new)); changed.append((r, rows[-1]))
        dropped = [r for r in pre if id(r) not in used]
        out = sorted(rows, key=lambda r: (r['at'], r['track'])) + post
        # the TAIL, TIGHT, against the NEW plan's neighbours (in the window: its rows before T and the fence, check()'s
        # own line): place() pins clip.end to PIN_TOL, so a laid end within ADOPT_TOL IS the planned one and anything else is an edit (a one-frame
        # trim was kept at 1.5 frames and never reached a copy); a cue the creator deleted no longer cuts short the one
        # before it, whose truncated clip then becomes that row's slice
        for r, c, new in list(kept):
            if abs(c['end'] - self.tail(r, out)[0]) > ADOPT_TOL:
                i = next(i for i, x in enumerate(out) if x is r)
                out[i] = dict(r, **new); kept.remove((r, c, new)); changed.append((r, out[i]))
        bak = None
        if dry: pass
        elif self.plan_path.exists():
            bak = self.plan_path.with_name(f"{self.plan_path.stem}.pre-adopt-{time.strftime('%Y%m%d-%H%M%S')}.json")
            shutil.copy2(self.plan_path, bak)
        if not dry:
            self.plan_path.write_text(json.dumps(out, indent=1) + '\n', encoding="utf-8")
            planner.write_meta(self.plan_path, self.hf, source='adopt', until=self.until)   # the window, for every later command
        for r in dropped:
            print(f"- {r['id']} {r['event']:<8} A{r['track'] + 1} {r['at']:8.3f} {os.path.basename(r['file'])}  [{r.get('gid')}]: not on the timeline, dropped")
        for o, r in changed:
            print(f"~ {r['id']} {r['event']:<8} A{r['track'] + 1} {r['at']:8.3f} {os.path.basename(r['file'])}  "
                  + ', '.join(f"{k} {o[k]} -> {r[k]}" for k in ('at', 'src_in', 'src_out', 'level_db') if o[k] != r[k]) + f"  [{r.get('gid')}]")
        for r in added:
            print(f"+ {r['id']} A{r['track'] + 1} {r['at']:8.3f} {os.path.basename(r['file'])} {r['level_db']:+g} dB  [{r['gid']}, the nearest graphic]")
        print(f"{'would adopt' if dry else 'adopted'} the timeline into {self.plan_path.name}: {len(kept)} kept · {len(changed)} changed · {len(added)} added · {len(dropped)} dropped"
              + (f" · {len(post)} at or after {self.until:.3f}s left as they were" if self.until is not None else '')
              + (f" (ids from {seeded}: {self.plan_path.name} did not exist)" if seeded else '')
              + (f"; backup {bak.name}" if bak else '') + (' (--dry: nothing written)' if dry else ''))
        return out

    def provision(self):
        need = max(self.tracks) + 1
        r = es(r"""
(function(){
  %s
  var NEED = %d; app.enableQE();
  var before = seq.audioTracks.numTracks, tries = 0;
  while (seq.audioTracks.numTracks < NEED && tries++ < 8)
    qe.project.getActiveSequence().addTracks(0, 0, 1, 1, seq.audioTracks.numTracks, 0, 0);
  return JSON.stringify({before: before, after: seq.audioTracks.numTracks});
})()""" % (self.head(), need))
        got = json.loads(r)
        if got['after'] < need: sys.exit(f"could not provision audio tracks: have {got['after']}, need {need}")
        if got['after'] != got['before']: print(f"audio tracks {got['before']} → {got['after']}")

    def place(self, r):
        # inside the copy window the slice is laid only to the end --verify holds it to: run to its full length, a cue
        # before T overwrites the head of the timeline's own cue after T, which the window never reads again
        sout = self.tail(r)[1] if self.until is not None else r['src_out']
        out = es(r"""
(function(){
  %s
  var root = app.project.rootItem;
  var PATH = %s, AT = %s, SIN = %s, SOUT = %s, TRACK = %d, V = %s, PIN = %s;
  function findByPath(bin){ for (var i = 0; i < bin.children.numItems; i++) { var c = bin.children[i];
    if (c.type === ProjectItemType.BIN) { var f = findByPath(c); if (f) return f; }
    else if (c.getMediaPath && c.getMediaPath() === PATH) return c; } return null; }
  function findBin(name){ for (var i = 0; i < root.children.numItems; i++) { var c = root.children[i];
    if (c.type === ProjectItemType.BIN && c.name === name) return c; } return null; }
  var item = findByPath(root);
  if (!item) { var bin = findBin("sfx") || root.createBin("sfx"); app.project.importFiles([PATH], true, bin, false); item = findByPath(root); }
  if (!item) return "ERROR: import failed for " + PATH;
  item.setInPoint(SIN + 1e-4, 4); item.setOutPoint(SOUT + 1e-4, 4);
  var tr = seq.audioTracks[TRACK];
  tr.overwriteClip(item, AT + 1e-4);
  item.clearInPoint(4); item.clearOutPoint(4);
  var clip = null;
  for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i];
    if (Math.abs(c.start.seconds - AT) < 0.03 && c.projectItem && c.projectItem.getMediaPath() === PATH) clip = c; }
  if (!clip) return "ERROR: clip did not land on A" + (TRACK + 1) + " at " + AT;
  if (Math.abs(clip.inPoint.seconds - SIN) > PIN) {   // overwriteClip FLOORS the in-point to the sequence grid
    // the same guarded idiom as place-music.py's clip.end write: a build where the property is read-only must
    // fail on the readback below with the row's name, not abort the whole script with a bare ExtendScript error
    var ti = new Time(); ti.seconds = SIN; try { clip.inPoint = ti; } catch (e) {} }
  // ...and the OUT-point too (your-job, 2026-09-21): a slice whose out sits between two sequence frames lost up to 1.5 frames of
  // its tail on 4 of 94 rows (the click's 2.90 landed at 2.836) and --verify then refused to save. Pin the END from the in.
  if (Math.abs(clip.end.seconds - (AT + SOUT - SIN)) > PIN) {
    var te = new Time(); te.seconds = AT + SOUT - SIN; try { clip.end = te; } catch (e) {} }
  var got = null;
  for (var k = 0; k < clip.components.numItems; k++) { var cm = clip.components[k];
    if (cm.displayName !== "Volume") continue;
    for (var q = 0; q < cm.properties.numItems; q++) { var pr = cm.properties[q];
      if (pr.displayName === "Level") { pr.setValue(V, true); got = pr.getValue(); } } }
  return JSON.stringify({start: clip.start.seconds, end: clip.end.seconds, srcIn: clip.inPoint.seconds, v: got});
})()""" % (self.head(), json.dumps(r['file']), r['at'], r['src_in'], sout, r['track'], lvl_v(r['level_db']), PIN_TOL))
        if str(out).startswith('ERROR'): sys.exit(f"{r['id']}: {out}")
        got = json.loads(out)
        if abs(got['start'] - r['at']) > 1.5 * self.F:
            sys.exit(f"{r['id']}: landed at {got['start']:.4f}, wanted {r['at']:.4f} (readback mismatch, stopping)")
        if got['v'] is None or abs(v_lvl(got['v']) - r['level_db']) > 0.2:
            sys.exit(f"{r['id']}: level read back {got['v']} ({v_lvl(got['v']) if got['v'] else None} dB), wanted {r['level_db']:+g}")
        if abs(got['srcIn'] - r['src_in']) > SRC_TOL_FRAMES * self.F:
            # NOT a mid-batch exit. `clip.inPoint =` is a write Premiere may ignore on a build where the property
            # is read-only, and stopping on the first row would leave the pass half-laid with no report of how
            # wide the problem is. Finish the batch; apply() names every floored row and refuses to save.
            self.floored.append(f"{r['id']} {r['event']:<8} A{r['track'] + 1} {r['at']:.3f}: source in read back "
                                f"{got['srcIn']:.4f}, wanted {r['src_in']:.4f}")
        return got

    def apply(self):
        self.check_section()
        self.provision()
        tl = self.readback()
        placed, kept, todo, stale = [], 0, [], {}
        near = [(r, min(self.match(r, tl), key=lambda c: abs(c['start'] - r['at']), default=None)) for r in self.rows]
        fits = {id(c) for r, c in near if c is not None and not self.misplaced(r, c)}   # a clip another row sits on is never taken up
        for r, c in near:
            if c is not None and (id(c) in fits or not self.misplaced(r, c)): kept += 1; continue
            if c is not None: stale[id(c)] = (r, c)        # laid off its row's time: taken up, then laid again below
            todo.append(r)
        if stale:
            # removed first, unsaved: laid over the old clip, overwriteClip would leave its first frame behind
            self.remove([c for _, c in stale.values()], save=False)
            for r, c in stale.values():
                print(f"~ {r['id']} {r['event']:<8} A{r['track'] + 1} moved {c['start']:.3f} → {r['at']:.3f} "
                      f"({(r['at'] - c['start']) / self.F:+.1f} fr): the plan moved under it")
        for r in todo:
            try:
                g = self.place(r)
            except SystemExit as e:
                # place() refuses a row it cannot read back, which is right — but it stops mid-batch, and the
                # cues already on the SFX tracks have to be named here or the next command starts from a
                # timeline nobody described. Nothing has been saved yet.
                for p in placed: print('+ ' + p)
                print(f"✗ STOPPED at {r['id']}: {e}")
                print(f"{len(placed)} cue(s) laid BEFORE this one and the project was NOT saved: close it "
                      "without saving to undo, or fix the row and re-run --apply (it is idempotent).")
                raise
            placed.append(f"{r['id']} {r['event']:<8} A{r['track'] + 1} {g['start']:.3f} → {g['end']:.3f} {r['level_db']:+g} dB {os.path.basename(r['file'])} [{r['gid']} {r['note']}]")
        for p in placed: print('+ ' + p)
        print(f"{kept} already placed · {len(placed)} placed" + (f" ({len(stale)} of them re-laid at their moved time)" if stale else ''))
        if self.floored:
            for m in self.floored: print('✗ ' + m)
            print(f"{len(self.floored)} clip(s) kept overwriteClip's sequence-grid floor on their in-point: the in-point "
                  "write-back did not hold, so those slices start up to a frame early. Project NOT saved — remove those "
                  "rows (--remove <ids>) and re-apply once the write-back works.")
            return False
        if not self.verify(quiet=True):
            print(f"{len(placed)} clip(s) placed, project NOT saved: resolve the drift (--diff for hand edits, --remove-extra for the "
                  "stale clips), then re-apply")
            return False
        if placed:
            sh('node', str(BRIDGE), 'save_project'); print('saved')
        return True

    def targets(self, ids=None, extra=False):
        """The clips a targeted remove acts on, resolved against the timeline: the rows named by id, or the
        clips that answer for no row. None means EVERY SFX clip (the deliberate full clear)."""
        if extra: return self.extras()
        tl = self.readback(); want, missing = [], []
        for i in ids:
            r = next((r for r in self.rows if r['id'] == i), None)
            if r is None: missing.append(f'{i} (no such plan row)'); continue
            m = [c for c in self.match(r, tl) if id(c) not in {id(x) for x in want}]
            if not m: missing.append(f'{i} (not on the timeline)'); continue
            want.append(m[0])
        if missing: sys.exit('nothing removed: ' + ', '.join(missing))
        return want

    def remove(self, targets=None, libs=None, save=True):
        sel = 'null' if targets is None else json.dumps([{'t': c['track'], 's': c['start']} for c in targets])
        # a TARGETED remove inside the copy window reaches every folder, because its targets came off the
        # every-folder readback; the full clear never does (main refuses --until on it)
        LIBS = 'null' if targets is not None and self.every else json.dumps(libs or self.libs)
        r = es(r"""
(function(){
  %s
  var LIBS = %s, SEL = %s, MUSIC = %d, n = 0;
  %s
  function wanted(t, s){ if (!SEL) return true;      // no selection = the full clear
    for (var k = 0; k < SEL.length; k++) if (SEL[k].t === t && Math.abs(SEL[k].s - s) < 0.002) return true; return false; }
  for (var t = 1; t < seq.audioTracks.numTracks; t++) { if (t === MUSIC) continue; var tr = seq.audioTracks[t];
    for (var i = tr.clips.numItems - 1; i >= 0; i--) { var c = tr.clips[i];
      var p = c.projectItem ? c.projectItem.getMediaPath() : "";
      if (!isLib(p) || !wanted(t, c.start.seconds)) continue;
      var ok = false; try { ok = c.remove(false, false); } catch (e) {}
      if (!ok) { app.enableQE(); var qt = qe.project.getActiveSequence().getAudioTrackAt(t);
        for (var q = qt.numItems - 1; q >= 0; q--) { var it = qt.getItemAt(q);
          if (it.type === "Clip" && Math.abs(it.start.secs - c.start.seconds) < 0.002) { it.remove(false, false); ok = true; break; } } }
      if (ok) n++; } }
  return JSON.stringify({removed: n, left: (function(){ var k = 0; for (var t = 1; t < seq.audioTracks.numTracks; t++) { if (t === MUSIC) continue; var tr = seq.audioTracks[t];
    for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i]; if (isLib(c.projectItem ? c.projectItem.getMediaPath() : "")) k++; } } return k; })()});
})()""" % (self.head(), LIBS, sel, MUSIC, IS_LIB))
        got = json.loads(r)
        if targets is not None and got['removed'] != len(targets):
            sys.exit(f"asked to remove {len(targets)} clip(s), removed {got['removed']}: stopping, project NOT saved")
        print(f"removed {got['removed']} SFX clip(s), {got['left']} left")
        if got['removed'] and save: sh('node', str(BRIDGE), 'save_project'); print('saved')


def dry_list(clips):
    """--dry: the clips a remove would take, and nothing touched."""
    for c in clips:
        print(f"- A{c['track'] + 1} {c['start']:8.3f} → {c['end']:.3f} {os.path.basename(c['path'])}" + (f"  ({c['why']})" if c.get('why') else ''))
    print(f"{len(clips)} clip(s) would be removed (--dry: nothing touched)")


def main():
    a = sys.argv[1:]
    if '-h' in a or '--help' in a: print(__doc__); sys.exit(0)
    if len(a) < 2: sys.exit(__doc__)
    check_args(a, set(COMMANDS) | {'--dry', '--include-local', '--plan', '--sequence', '--until'},
               valued={'--plan', '--sequence', '--until'}, listed={'--remove'})
    until = opt(a, '--until')
    try: until = None if until is None else until if until == 'none' else float(until)
    except ValueError: sys.exit(f'--until takes seconds on the timeline, got {until!r}')
    cmds = [c for c in COMMANDS if c in a]
    if not cmds: sys.exit(__doc__)
    if len(cmds) > 1: sys.exit(f"one command at a time, got {' '.join(cmds)}: nothing done")
    cmd, dry = cmds[0], '--dry' in a
    if until == 'none' and cmd != '--adopt':
        sys.exit('--until none clears a recorded copy window, and only --adopt writes one: nothing done')
    if until is not None and cmd == '--remove':
        sys.exit('--until is the copy window of --adopt, --apply, --verify, --remove-extra and --diff: --remove takes plan ids, or clears every SFX clip')
    if dry and cmd not in ('--remove', '--remove-extra', '--adopt'):
        sys.exit(f'--dry previews --remove, --remove-extra and --adopt; {cmd} has no dry run: nothing done')
    ids = arg_list(a, '--remove')        # read BEFORE the guard talks to Premiere: `--remove ""` exits here, never clears
    p = Placer(a[0], plan=opt(a, '--plan'), sequence=opt(a, '--sequence'), until=until, adopt=cmd == '--adopt')
    if cmd in ('--apply', '--verify', '--diff'): p.warn_stale()
    if cmd in ('--adopt', '--remove', '--remove-extra'): p.check_section()      # the span they read is the plan's offset's
    if cmd == '--diff':
        moved = p.check_section(refuse=False)
        if moved: print(moved)
    if cmd == '--adopt': p.adopt(dry=dry)
    elif cmd == '--apply': sys.exit(0 if p.apply() else 1)
    elif cmd == '--verify': sys.exit(0 if p.verify() else 1)
    elif cmd == '--remove-extra':
        t = p.targets(extra=True)
        if dry: dry_list(t)
        else: p.remove(t)
    elif cmd == '--remove':
        if ids:
            t = p.targets(ids)
            if dry: dry_list(t)
            else: p.remove(t)
        elif p.until is not None:
            sys.exit(f"✗ {p.plan_path.name} was adopted with --until {p.until:.3f}: the full clear would take this sequence's own "
                     "cues after it. Nothing removed: --remove-extra (or --remove <ids>) works inside the window")
        else:
            # bare --remove is still the full clear, but it stops at the PLAN's own libraries: a job-local cue in
            # audio/sfx-src was hand-placed and is not this plan's to delete just because the readback can see it
            libs = p.libs if '--include-local' in a else p.plan_libs
            if dry: dry_list(p.readback(libs=libs))
            else: p.remove(None, libs=libs)
    elif cmd == '--diff': p.diff()


if __name__ == '__main__':
    main()
