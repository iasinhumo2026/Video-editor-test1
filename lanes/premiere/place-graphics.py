#!/usr/bin/env python3
"""place-graphics.py: owns hf-graphics/placement.json and the Premiere graphics tracks (V3/V4, plus V5 for the caption layer).

  uv run lanes/premiere/place-graphics.py projects/<job> --plan [--write]   # derive rows from the plan + renders; --write saves AND syncs the plan's frame-snap roundings
  uv run lanes/premiere/place-graphics.py projects/<job> --verify           # timeline readback vs placement.json (exit 1 on drift)
  uv run lanes/premiere/place-graphics.py projects/<job> --apply            # place every row not yet on the timeline; swap stale versions;
                                                                           #   re-lay a row whose clip --verify calls off it (a re-cut moved the row)
                                                                           #   (--any-rate: on a hand-edited sequence off the plan's rate)
  uv run lanes/premiere/place-graphics.py projects/<job> --reconcile [--apply]  # name the orphan graphics clips a creator ripple left; --apply removes + re-places
  uv run lanes/premiere/place-graphics.py projects/<job> --remove g4 g5,g6  # take graphics off the timeline (before a re-render swap); ids by spaces and/or commas;
                                                                           #   every version of each, wherever it sits (a re-cut's pre-cut copy too)
  uv run lanes/premiere/place-graphics.py projects/<job> --sync-plan        # write placed start/end back into graphics-plan.json (a hand-placed row)
  ... --variant ad --sequence "<job> AD"   # a SECOND sequence's graphics: graphics-plan.ad.json (else graphics-plan.json's
                                           # variants.ad, composed by the preset's layout.py) -> hf-graphics/placement.ad.json
  ... --sequence "<name>"                  # any run: refuse unless the active sequence is <name> (env VE_SEQUENCE works too)

A variant plan is the WHOLE graphics plan of its sequence (a clone keeps the organic graphics it was cloned
with, and every graphics clip on it that the variant plan does not list reads as extra). When there is no
graphics-plan.<variant>.json and graphics-plan.json carries `variants.<variant>` (the Talking Head Explainer's
second deliverable, its layout.md § 12), the plan is COMPOSED from it with the preset's own layout.compose_variant
(the organic cells before `from`, clipped there, plus the variant's cells; the caption layer to the variant's end):
nothing writes a separate file, and --sync-plan / --plan --write never write a composed plan back (edit
variants.<variant> in graphics-plan.json by hand). A composed plan's cut_rev is the organic plan's, checked against
transcript/cuts.json: the variant's tail is its own EDL's, which the organic stamp does not cover. Its caption layer is
hf-graphics/captions/renders/captions-<variant>-alpha*.mov, its cut_rev is checked against
transcript/cuts.<variant>.json when that exists (else cuts.json), and it refuses to run onto the job-named
organic sequence. Until 2026-09-23 every AD graphic was hand-laid with no row and no --verify.

Why (2026-09-02): eight hand-written ExtendScript batches each needed a matching hand edit to
placement.json and two post-hoc plan reconciliations; the "plan fidelity" reviewer then raised
frame-snap drift as defects. One owner for the rows, one readback that is the truth, and a
`--sync-plan` so the plan and the timeline never disagree by a rounding.

Rows: {"id", "file", "start", "end", "kind": "text"|"full"|"overlay"|"captions", "track": 2|3|4, "blend"?}
  blend    the plan cell's "blend" (the highlighter's "difference"), set on the clip's Opacity > Blend Mode after the
           lay and read back; --apply sets it on an already-placed clip that reads another mode, --verify calls a
           wrong one drift. Blend Mode is an unnamed INDEX (BLEND below, probed on a render: lab-notes § Step 5).
  A plan may carry "timeline_offset": <s> (a SECTION sub-job whose transcript and cuts.json start at 0 but whose clips sit
  later on the sequence: an outro section at 152.694208, 2026-09-14). Rows stay in the plan's own time base (so
  validate-plan.py, graphics-qa.py and --sync-plan need no offset); the offset is added and subtracted only at the
  Premiere boundary (place, remove, readback), and another section's clips outside the plan's span are not "extra".
  text     the text-animation builder's render; start/end from its <id>.meta.json (the builder owns timing)
  full     a punch-cut mp4; start/end from the plan cell (end == a V1 cut, validate-plan.py enforces it)
  overlay  an alpha mov; start from the plan cell, end = start + the render's duration
  captions the short-form caption layer (hf-graphics/captions/renders/captions-alpha*.mov), spanning the cut
  track    2 = V3 (graphics), 3 = V4 (accents), a row overlapping an earlier V3 row goes to V4;
           4 = V5, the caption layer only (provisioned on demand, always above the shuffle)
A clip is on its row when its START is within half a frame of the row's (or of the frame overwriteClip floors an
off-grid start onto), its END within half a frame when that end is a V1 cut (1.5 frames elsewhere), on the row's track:
the ONE line --verify reports by and --apply re-lays by (off_row). Until 2026-10-14 --apply kept any clip within 1.5
frames: after a re-cut moved 23 rows one frame, --verify called 19 of them DRIFT while --apply read all 23 "already
placed", and the 4 whose START sat a frame early on a cut read green on both.
A graphics clip of this job's own media (under its hf-graphics/) is this plan's WHEREVER it sits: --remove and --apply
take every version of an id there, and --verify fails on one no row answers for, past the plan's span or the last V1
frame included (a re-cut left g20's pre-cut copy 4 s past the new end under "ALL PLACED ... 0 extra", 2026-10-15). A clip
running past the last V1 frame is drift whether or not a row lays it.
The newest VERSION of a render wins (g4-alpha-d.mov over g4-alpha-c.mov, g4-alpha-v2a.mov over both): re-renders
never overwrite. `--plan` names the pick whenever a graphic has more than one version, and `--verify` prints
`⚠ STALE PICK` for a row whose file is not the newest on disk.

Premiere is driven through lanes/premiere/premiere-bridge.mjs (headless, bridge panel running). Placement
is DOM overwriteClip at start + 1e-4 (the same nudge as the EDL replay: a double a hair below the
frame tick gets FLOORED into the previous frame), then the clip's end is pinned and its Motion Scale set
to fill the sequence (fit_scale: 200 for a 1080x1920 render on a 2160x3840 sequence). Removal is DOM
TrackItem.remove(false, false) with a QE fallback. Every write is read back before it is believed.
A swap CARRIES the creator's hand-set Motion from the clip it removes (hand_motion): a Scale that is
neither 100 nor the old render's fit is re-expressed for the new render, a Position off centre is kept.
A render WITH an audio stream (probe_audio) is laid as a video-only hard-boundary subclip: overwriteClip lays a
master's linked audio onto the audio track of the same index (live 2026-09-23: g2.mp4's AAC landed on A3).
The placer never writes audio, and --apply PROVES it: every audio clip is snapshotted before the first
write and after the last, and any difference stops the run unsaved (a lay can bring linked audio, and
the creator may be editing the same timeline).

A plan whose `cut_rev` is not the job's current transcript/cuts.json is REFUSED before any read or
write: the cut moved under the plan, so every row would be placed at a pre-recut anchor
(`uv run workflows/ripple-cut.py projects/<job> --from <old EDL> --apply` re-times and re-stamps).
A plan with NO `cut_rev` only warns, unless cuts.json changed after the plan was written: then
--apply and --reconcile --apply refuse until it is stamped, and this script never writes that plan
(a sync would date it after the EDL and lift the refusal with no stamp).
A row a ripple marked `"ripple": "orphaned"` — its anchor was cut away, so nothing could re-time it —
is refused and NAMED for the same reason: the stamp says "this EDL", that row does not.
A SECTION plan (`timeline_offset`) is refused the same way, before the first write of --apply,
--reconcile --apply and --remove (and reported by --verify), when the section's run of its own media on the
live V1 does not start at the offset (or at the EDL's first `_timeline`) within half a sequence frame: a creator
ripple earlier in the sequence moved the section 66.6 s and --apply re-laid all 23 outro graphics at the
old offset, a second set on V3 (2026-09-28). job_guard.section_moved names the live start and the fix.
"""
import hashlib, importlib.util, json, math, os, re, shlex, subprocess, sys, glob
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252, which cannot encode the status glyphs
    try:
        if (getattr(_s, "encoding", "") or "").lower().replace("-", "") != "utf8":
            _s.reconfigure(encoding="utf-8")
    except Exception:
        pass
from collections import Counter
from pathlib import Path
from job_guard import require_job_project, job_root, section_moved   # lanes/premiere/job_guard.py: the active project must be this job's
from pes import es, paged                   # lanes/premiere/pes.py: the bridge's one output contract

BRIDGE = Path(__file__).resolve().parent / 'premiere-bridge.mjs'
NUDGE = 1e-4
PAGE = 40          # clips per readback call: full media paths blow the bridge's 64 KB return cap around 200 (pes.paged)
# Opacity > Blend Mode is an unnamed INDEX, never the Photoshop order (lanes/premiere/lab-notes.md § Step 5): probed on
# Premiere 2026 (26.x, macOS) with a 50 % grey plate over a graded camera frame, each candidate's program frame fitted
# against the blend models. 18 = Normal (every laid clip reads it; the plate came back flat 0.502), 5 = Difference
# (|a - b| per pixel in display space, mean error 0.00000, no other index within 0.13), 2026-10-05.
BLEND = {'normal': 18, 'difference': 5}
# the clip's Opacity > Blend Mode property: the FIRST one so named (the probe set it and the picture changed; the
# component also lists a second one, at 0)
BLEND_JS = ('function blendProp(c){ for (var k = 0; k < c.components.numItems; k++) if (c.components[k].matchName === '
            '"AE.ADBE Opacity") { var op = c.components[k]; for (var q = 0; q < op.properties.numItems; q++) '
            'if (op.properties[q].displayName === "Blend Mode") return op.properties[q]; } return null; }')


def blend_name(v):
    """A Blend Mode index as its name, or `index N` for one this script does not know."""
    return next((k for k, i in BLEND.items() if i == v), f'index {v}')


def check_blends(rows):
    """Refuse a row naming a blend this lane cannot set, before anything is read or written."""
    bad = sorted({str(r['blend']) for r in rows if r.get('blend') and r['blend'] not in BLEND})
    if bad:
        sys.exit(f"✗ blend {', '.join(bad)} is not a mode this placer knows ({', '.join(BLEND)}): probe its index on a "
                 "render first (lanes/premiere/lab-notes.md § Step 5) and add it to BLEND. Nothing touched.")


# the offline half (rows from the plan + renders, the version pick, the cut_rev guard, the plan sync) is lane-neutral:
# workflows/placement.py, imported by path so every lane derives the same rows
_spec = importlib.util.spec_from_file_location('ve_placement', Path(__file__).resolve().parents[2] / 'workflows' / 'placement.py')
placement = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(placement)
sh, probe_dur, probe_fps = placement.sh, placement.probe_dur, placement.probe_fps
VERSION, WORD, SAME_RENDER_S, LAYOUT_PY = placement.VERSION, placement.WORD, placement.SAME_RENDER_S, placement.LAYOUT_PY
version_of, _version, renders, compose_variant_plan = placement.version_of, placement._version, placement.renders, placement.compose_variant_plan


def probe_audio(path):
    """True when the render carries an audio stream (a punch-cut mp4 exported with its sound). place() lays such a
    render as a VIDEO-ONLY subclip; a file ffprobe cannot read is not called AV."""
    return bool((sh('ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0',
                   path, check=False) or '').strip())


def probe_size(path):
    r = sh('ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path)
    w, h = r.strip().split('\n')[0].strip(',').split(',')[:2]
    return int(w), int(h)


def fit_scale(seq_w, seq_h, src_w, src_h):
    """The Motion Scale (percent) a render needs to fill the sequence frame. overwriteClip lays every clip at
    100 = its native pixels, so a 1080x1920 render on a 2160x3840 sequence landed HALF SIZE on a swap
    (your-job, 2026-09-22). 100 at the sequence's own size; k*100 when the sequence is
    the SAME integer multiple k > 1 of the render on both axes; None for anything else (another aspect, a
    render larger than the frame), which the caller lays at 100 and names rather than guessing."""
    if (src_w, src_h) == (seq_w, seq_h):
        return 100.0
    if src_w and src_h and seq_w % src_w == 0 and seq_h % src_h == 0 and seq_w // src_w == seq_h // src_h > 1:
        return 100.0 * (seq_w // src_w)
    return None


TICKS = 254016000000     # Premiere ticks per second


def audio_diff(before, after):
    """What changed between two audio snapshots (Placer.audio_snapshot), one line per clip or track count, [] if
    nothing. Clips compare on EVERY field, in ticks, so a one-tick slip or a relinked path is a difference."""
    def say(c):
        if 'tracks' in c: return f"{c['tracks']} audio track(s)"
        return (f"A{c['track'] + 1} {c.get('name') or '(unnamed)'} {int(c['start']) / TICKS:.4f} → {int(c['end']) / TICKS:.4f} "
                f"in {int(c['inPoint']) / TICKS:.4f} ({os.path.basename(c.get('path') or '') or 'no media'})")
    k = lambda c: json.dumps(c, sort_keys=True)
    lost = Counter(map(k, before)) - Counter(map(k, after))
    new = Counter(map(k, after)) - Counter(map(k, before))
    out = []
    for c in before:
        if lost[k(c)] > 0: out.append('- was ' + say(c)); lost[k(c)] -= 1
    for c in after:
        if new[k(c)] > 0: out.append('+ now ' + say(c)); new[k(c)] -= 1
    return out


class Placer(placement.Placer):
    """The Premiere half: the offline rows, plan and cut_rev guard are workflows/placement.py's Placer."""
    def __init__(self, job, variant=None, sequence=None):
        # the sequence this run targets: every readback and write refuses unless it is the active one
        self.sequence = sequence or os.environ.get('VE_SEQUENCE') or None
        if variant:
            placement.check_variant_name(variant)
            if not self.sequence:
                sys.exit(f'--variant {variant} places onto a second sequence: name it with --sequence "<name>" '
                         '(or VE_SEQUENCE), nothing touched')
            if self.sequence == job_root(Path(job).resolve()).name:
                sys.exit(f'--variant {variant} names {self.sequence}, the job-named ORGANIC sequence: the variant plan '
                         'would replace its graphics. Nothing touched. Name the variant sequence with --sequence.')
        self._seq = None
        self._audio0 = None         # the audio snapshot taken before this run's first write
        self._carry = {}            # row id -> the hand Motion read off the clip a swap removed
        self._split = set()         # row ids whose removed clips carried DIFFERENT hand Motion: nothing is carried
        super().__init__(job, variant)

    # this module's own probes (patchable here), not workflows/placement.py's
    def _dur(self, f):
        return probe_dur(f)

    def _fps(self, f):
        return probe_fps(f)

    def require_job_project(self):
        """Every readback and write goes to app.project.activeSequence, which is whatever project the operator last clicked.
        With two projects open the placer laid all 37 v2 graphics over the v1 timeline (2026-09-13: unsaved,
        reverted by closing without saving). So the ACTIVE project must be THIS job's (projects/<job>/premiere/*.prproj, or a
        .prproj named after the job) before anything is read or written; the placer refuses, it never picks a project."""
        if getattr(self, '_guarded', False): return
        if self.sequence:
            os.environ['VE_SEQUENCE'] = self.sequence     # job_guard's sequence rule reads the requested name from here
        require_job_project(es, self.job)
        self._guarded = True

    def seq_js(self):
        """ES, after `var seq = app.project.activeSequence`: refuse unless it is the sequence this run targets
        (--sequence / VE_SEQUENCE). Every call carries it, so a click on another timeline mid-run stops the
        next call instead of writing there, whatever job_guard checked at startup."""
        return ('if (!seq) return "ERROR: no active sequence"; var WANT_SEQ = %s; '
                'if (WANT_SEQ !== null && seq.name !== WANT_SEQ) return "ERROR: the active sequence is " + seq.name '
                '+ ", not " + WANT_SEQ + ": nothing touched";') % json.dumps(self.sequence)

    def readback(self):
        self.require_job_project()
        # PAGED: one row per clip carries a full media path, so a whole-timeline read hits the CEP
        # return cap around 200 clips and comes back as JSON that dies mid-string (lanes/premiere/lab-notes.md
        # § the bridge's output contract). The ES walks the tracks in the same order every call and
        # returns the slice [N0, N1); a short page ends the loop.
        # every row carries `v1`, the end of the last V1 clip (the sequence's last picture frame): a graphic past it
        # is drift whether or not a row lays it (verify)
        guard = self.seq_js()
        tl = paged(lambda n0, n1: r"""
(function(){
  var seq = app.project.activeSequence; %s
  %s
  var N0 = %d, N1 = %d, n = 0, out = [], v1 = null, vt = seq.videoTracks[0];
  for (var j = 0; j < vt.clips.numItems; j++) if (v1 === null || vt.clips[j].end.seconds > v1) v1 = vt.clips[j].end.seconds;
  for (var t = 2; t < seq.videoTracks.numTracks; t++) {
    var tr = seq.videoTracks[t];
    for (var i = 0; i < tr.clips.numItems; i++) {
      if (n++ < N0) continue;
      if (out.length >= N1 - N0) return JSON.stringify(out);
      var c = tr.clips[i], bp = blendProp(c);
      out.push({track: t, name: c.name, start: c.start.seconds, end: c.end.seconds, v1: v1,
                path: c.projectItem ? c.projectItem.getMediaPath() : "", blend: bp ? bp.getValue() : null}); }
  }
  return JSON.stringify(out);
})()""" % (guard, BLEND_JS, n0, n1), size=PAGE)
        self._v1_end = next((c['v1'] - self.off for c in tl if c.get('v1') is not None), None)
        if self.off or self.plan.get('duration'):
            # a plan's readback covers ITS span: another section's graphics (the outro's four after section 1's 33, or the
            # reverse) are neither drift nor extra to this plan (2026-09-14). This job's OWN media is its wherever it sits:
            # a re-cut shortened the plan and g20's pre-cut copy, 4 s past the new end, read as nothing at all (2026-10-15)
            lo, hi = self.span()
            tl = [c for c in tl if lo <= c['start'] <= hi or self.ours(c['path'])]
            for c in tl:
                c['start'] -= self.off; c['end'] -= self.off
        return tl

    def check_section(self, refuse=True):
        """A SECTION plan's `timeline_offset` against the live V1 (job_guard.section_moved), read once per run: the
        write paths refuse on a moved section, --verify reports it."""
        if self.plan.get('timeline_offset') is None: return None
        if not hasattr(self, '_moved'):
            self.require_job_project()
            self._moved = section_moved(es, 'var seq = app.project.activeSequence; ' + self.seq_js(), self.job, self.off,
                                        self.F(), self.cuts_p, self.plan_p.name)
        if self._moved and refuse: sys.exit(f'{self._moved}\n  Nothing written.')
        return self._moved

    def verify(self, quiet=False):
        self.check_seq_rate(refuse=False)
        moved = self.check_section(refuse=False)
        if moved: print(moved)
        F = self.F()
        tl = self.readback()
        ok = not moved
        seen = set()
        v1 = getattr(self, '_v1_end', None)        # the last V1 frame (readback): nothing of ours plays past it
        past = lambda c: v1 is not None and c['end'] > v1 + 0.5 * F
        for r in self.rows:
            # a row is checked against its OWN file below, so a row derived from a stale pick passes that check:
            # name it when a newer version of the same graphic is on disk (a hand-named file is not a candidate)
            cand = renders(*self.globs(r['id'], r.get('kind')), gid=r['id'])
            if cand and os.path.basename(r['file']) in {os.path.basename(f) for f in cand[:-1]}:
                print(f"⚠ STALE PICK {r['id']}: placed {os.path.basename(r['file'])}, newest on disk {os.path.basename(cand[-1])}")
            hit = [c for c in tl if os.path.basename(c['path']) == os.path.basename(r['file'])]
            # one clip per row: a clip another row took is not this one's, and of two copies the one ON the row is the
            # row's (the other is extra), never whichever the track lists first
            m = [c for c in hit if id(c) not in seen and abs(c['start'] - r['start']) <= 1.5 * F]
            if not m:
                ok = False
                if hit: print(f"✗ {r['id']}: {os.path.basename(r['file'])} is on the timeline at {hit[0]['start']:.4f}, placement says {r['start']:.4f}")
                else: print(f"✗ {r['id']}: {os.path.basename(r['file'])} not on V3/V4")
                continue
            c = min(m, key=lambda c: (self.off_row(r, c) is not None, abs(c['start'] - r['start']))); seen.add(id(c))
            bad = self.off_row(r, c)
            if past(c):
                ok = False; print(f"✗ {r['id']}: runs to {c['end']:.4f}, past the last V1 frame at {v1:.4f} (the row is off the cut:"
                                  " re-time it, `workflows/ripple-cut.py`)")
            elif bad:
                ok = False; print(f"✗ {r['id']}: {bad}")
            elif r.get('blend') and c.get('blend') != BLEND.get(r['blend']):
                ok = False; print(f"✗ {r['id']}: blend reads {blend_name(c.get('blend'))}, placement says {r['blend']}"
                                  " (--apply sets it)")
            elif not quiet:
                print(f"✓ {r['id']:<5} V{c['track'] + 1} {c['start']:.4f} → {c['end']:.4f}  {os.path.basename(c['path'])}"
                      + (f"  · blend {blend_name(c.get('blend'))}" if r.get('blend') else ''))
        # What counts as an EXTRA is the clip's MEDIA, not its name: a graphic's media lives under the job's
        # hf-graphics/, a lane layer's does not (the GRADE adjustment layer has no path at all, a phone-blur
        # clip is a duplicate of the raw). The old one-name allowlist reported 55-81 PHONE BLUR clips as drift
        # on every run and the real extras had to be grepped out of it (2026-09-19).
        hf = os.path.normcase(str(self.hf)) + os.sep   # the separator, or a sibling `hf-graphics-old/` counts as ours
        mine = lambda c: os.path.normcase(os.path.normpath(c['path'] or '.')).startswith(hf)
        extra = [c for c in tl if id(c) not in seen and mine(c)]
        foreign = [c for c in tl if id(c) not in seen and not mine(c)]
        # an extra clip of this job's own media is DRIFT: the timeline plays a graphic placement.json does not (a re-cut's
        # pre-cut copy past the new end read "ALL PLACED ... 0 extra clip(s)", whop-first-10k 2026-10-15)
        for c in extra:
            ok = False
            print(f"✗ extra clip on V{c['track'] + 1}: {c['name']} {c['start']:.4f} → {c['end']:.4f} ({os.path.basename(c['path'])}): not in {self.pj.name}"
                  + (f", past the last V1 frame at {v1:.4f}" if past(c) else '')
                  + f" (`--reconcile --apply` removes it)")
        if foreign:
            n = {}
            for c in foreign: n[c['name'] or '(unnamed)'] = n.get(c['name'] or '(unnamed)', 0) + 1
            print('· ' + f"{len(foreign)} non-graphic clip(s) on the graphics tracks: "
                  + ', '.join(f'{k} ×{v}' for k, v in sorted(n.items())) + " — a lane layer, not this script's business")
        print(f"{'ALL PLACED' if ok else 'DRIFT'}: {len(self.rows)} rows, {len(extra)} extra clip(s)")
        self.extra = extra
        return ok

    def off_row(self, r, c):
        """What puts clip c off row r's place, None when it sits on it: the ONE line --verify reports by and --apply
        re-lays by. The start is held to half a frame of the row (rows are frame-snapped, and place() lays at start +
        NUDGE) or of the frame Premiere floors an off-grid start onto; the end to half a frame on a V1 cut, 1.5 elsewhere."""
        F = self.F()
        land = math.floor((r['start'] + self.off + NUDGE) / F + 1e-6) * F - self.off
        if min(abs(c['start'] - r['start']), abs(c['start'] - land)) > 0.5 * F:
            return (f"starts {c['start']:.4f} on the timeline, placement says {r['start']:.4f} ({(c['start'] - r['start']) / F:+.1f} frames)"
                    + (' - that start IS a V1 cut, one frame early flashes the graphic over the outgoing shot' if self.on_cut(r['start']) else ''))
        cut_end = self.on_cut(r['end'])
        if abs(c['end'] - r['end']) > (0.5 * F if cut_end else 1.5 * F):
            return (f"ends {c['end']:.4f} on the timeline, placement says {r['end']:.4f} ({(c['end'] - r['end']) / F:+.1f} frames)"
                    + (' - that end IS a V1 cut, one frame short flashes the outgoing shot' if cut_end else ''))
        if c['track'] != r.get('track', 2):
            return f"on V{c['track'] + 1}, placement says V{r.get('track', 2) + 1}"
        return None

    def reconcile(self, do_apply=False):
        """A creator ripple razors the graphics tracks into orphan fragments the placer cannot own (52 of them
        on your-job, 2026-09-19, removed with hand-written ExtendScript). Dry-run by default: it names every
        hf-graphics clip that matches no placement row, and only removes them — and re-places the affected
        rows — once the operator has read that list and passed --apply."""
        if do_apply: self.require_stamp(); self.check_section()
        self.verify(quiet=True)
        orphans = self.extra
        if not orphans:
            print('no orphan graphics clips: every hf-graphics clip on V3+ belongs to a placement row')
            return True
        bases = sorted({os.path.basename(c['path']) for c in orphans})
        if not do_apply:
            print(f"{len(orphans)} orphan clip(s) from {len(bases)} render(s). Read the ⚠ lines above, then"
                  " re-run with --apply to remove them and re-place their rows.")
            return True
        failed, done = [], []
        self.audio_before()
        for b in bases:
            # removal is by basename inside the plan's span: a razored row's OWN clip goes too (its fragments
            # share the file), and apply() below lays it back down whole. An OLD VERSION of a row's graphic
            # (g0-alpha-c.mov under a row laying g0-alpha-d.mov: all 26 orphans of the live 2026-09-21 reconcile)
            # is that row's too. Either way the hand Motion is read before the clip goes, for the re-lay to carry.
            r = self.owner(b)
            if r:
                self.keep_carry(r['id'], self.hand_motion(r['id'], r['file'], path_base=b))
            gone = self.remove(r['id'] if r else '', path_base=b)
            done.append(b)
            print(f"- {b}: removed {gone}")
            failed += [g for g in gone if g.endswith('(FAILED)')]
        # A clip the DOM and the QE fallback both refused to remove is still on the track: re-placing over
        # it would stack a second copy on top of the fragment instead of replacing it, and nothing downstream
        # would say so. Stop here, with the track named, and leave the project unsaved.
        if failed:
            sys.exit(f"✗ {len(failed)} clip(s) would not remove: {', '.join(failed)}\n"
                     f"  {len(done)} render(s) were processed and NOTHING has been re-placed or saved — close the "
                     "project without saving to undo, or clear those clips by hand and re-run --reconcile --apply.")
        return self.apply()

    def owner(self, base):
        """The row a graphics clip's file belongs to: the row laying that exact file, else the row whose graphic it
        is a version of (apply()'s stale-clip rule, `<id>-` or `<id>.`; the longest id wins), else None."""
        r = next((r for r in self.rows if os.path.basename(r['file']) == base), None)
        own = [r for r in self.rows if re.match(r'%s[-.]' % re.escape(r['id']), base)]
        return r or (max(own, key=lambda r: len(r['id'])) if own else None)

    def keep_carry(self, gid, carry):
        """Keep the hand Motion read off a clip this run removes, for the row's re-lay (place). A row can lose
        several clips in one run (razor fragments, an old version beside them): they must agree, or none is carried."""
        if not carry or gid in self._split: return
        have = self._carry.get(gid)
        if have and (have['scale'], have['pos']) != (carry['scale'], carry['pos']):
            print(f"⚠ {gid}: the clips being removed carry DIFFERENT hand Motion (Scale {have['scale']}, Position "
                  f"{have['pos']} vs Scale {carry['scale']}, Position {carry['pos']}): none carried, set it on the new clip by hand")
            del self._carry[gid]; self._split.add(gid)
            return
        self._carry[gid] = carry

    # ── writes ──────────────────────────────────────────────────────────────
    def span(self):
        """The plan's span on the sequence (lo, hi), seconds: a section sub-job's ids restart per section, so a clip of
        ANOTHER directory's media is this plan's only inside it (2026-09-14). Unbounded for a plan with neither."""
        if self.off or self.plan.get('duration'):
            return self.off - 0.5, self.off + float(self.plan.get('duration') or 1e9) + 0.5
        return -1e9, 1e9

    def ours(self, path):
        """True when a clip's media is this job's own graphics build (under its hf-graphics/, the separator included, so
        a sibling `hf-graphics-old/` is not): such a clip is this plan's WHEREVER it sits on the sequence."""
        hf, norm = os.path.normcase(os.path.normpath(str(self.hf))) + os.sep, lambda f: os.path.normcase(os.path.normpath(f or '.'))
        return norm(path).startswith(hf) or norm(path) in {norm(r['file']) for r in self.rows}

    def match_js(self, gid, path_base):
        """ES: the variables and the `mine(c, p, b)` test remove() and hand_motion() share. A clip is the graphic's when
        its file is the graphic's (BASE exactly, else any VERSION of the id: `<id>-` or `<id>.`) AND it is this plan's: its
        media is this job's own hf-graphics/ or a row's own file, anywhere on the sequence, or any other media inside the
        plan's span. Until 2026-10-15 the span alone scoped it: once a re-cut shortened the plan, g20's pre-cut copy sat
        4 s past the new end, outside it, and `--remove g20` took nothing (whop-first-10k)."""
        lo, hi = self.span()
        norm = lambda f: os.path.normpath(f).replace(os.sep, '/')
        files = sorted({norm(r['file']) for r in self.rows
                        if (os.path.basename(r['file']) == path_base if path_base else r['id'] == gid)})
        nocase = os.path.normcase('A') == 'a'        # Windows: paths compare case-blind
        hf = norm(str(self.hf)) + '/'
        if nocase: hf, files = hf.lower(), [f.lower() for f in files]
        return ('var GID = %s, BASE = %s, LO = %s, HI = %s, HF = %s, FILES = %s, NOCASE = %s;'
                ' function mine(c, p, b){'
                ' if (!(BASE ? (b === BASE) : (b.indexOf(GID + "-") === 0 || b.indexOf(GID + ".") === 0))) return false;'
                ' var q = p.replace(/\\\\/g, "/"); if (NOCASE) q = q.toLowerCase();'
                ' if (q.indexOf(HF) === 0) return true;'
                ' for (var k = 0; k < FILES.length; k++) if (q === FILES[k]) return true;'
                ' return c.start.seconds >= LO && c.start.seconds <= HI; }'
                % (json.dumps(gid), json.dumps(path_base), lo, hi, json.dumps(hf), json.dumps(files), json.dumps(nocase)))

    def remove(self, gid, path_base=None):
        self.require_job_project()
        r = es(r"""
(function(){
  var seq = app.project.activeSequence; %s %s var removed = [];
  for (var t = 2; t < seq.videoTracks.numTracks; t++) {
    var tr = seq.videoTracks[t];
    for (var i = tr.clips.numItems - 1; i >= 0; i--) { var c = tr.clips[i];
      var p = c.projectItem ? c.projectItem.getMediaPath() : ""; var b = p.split(/[\/\\]/).pop() || "";   // getMediaPath is backslashed on Windows; ExtendScript splits "" by a regex into [] (a media-less Premiere Graphic clip crashed the swap, 2026-10-07)
      if (!mine(c, p, b)) continue;
      var ok = false;
      try { ok = c.remove(false, false); } catch (e) { ok = false; }
      if (!ok) { app.enableQE(); var qt = qe.project.getActiveSequence().getVideoTrackAt(t);
        for (var q = qt.numItems - 1; q >= 0; q--) { var it = qt.getItemAt(q);
          if (it.type === "Clip" && Math.abs(it.start.secs - c.start.seconds) < 0.002) { it.remove(false, false); ok = true; break; } } }
      removed.push(b + "@" + c.start.seconds.toFixed(3) + (ok ? "" : " (FAILED)"));
    }
  }
  return JSON.stringify(removed);
})()""" % (self.seq_js(), self.match_js(gid, path_base)))
        return json.loads(r)

    def check_seq_rate(self, refuse=True):
        """Refuse a sequence whose frame is not the plan's: every row is snapped to the plan's grid, so a sequence on another
        one lays graphics off its cuts. Premiere builds a sequence from a variable-rate phone clip at the clip's AVERAGE rate
        (29.9766 or 30.0013 fps for iPhone takes nominally 29.97 or 30, macOS and Windows, 2026-09-27: g5 on frame 824 not
        823). `node lanes/premiere/premiere-bridge.mjs seq-rate` puts an EMPTY sequence on the nominal rate. `--verify` only
        warns (it writes nothing), and `--any-rate` places on a timeline that already carries hand edits, where re-laying
        the cut on a new sequence would throw the edits away: its rows may sit a frame off."""
        if getattr(self, '_rate_ok', False) or not self.plan.get('fps'):
            return
        self.require_job_project()
        tpf = int(es(r"""(function(){ var seq = app.project.activeSequence; %s
  return String(seq.getSettings().videoFrameRate.ticks); })()""" % self.seq_js()))
        n, _, d = str(self.plan['fps']).partition('/')
        fps = float(n) / float(d or 1)
        # a decimal plan rate ("29.97", which validate-plan and layout.py accept) is its NTSC rational, not 2997/100
        fps = next((q for q in (24000 / 1001, 30000 / 1001, 48000 / 1001, 60000 / 1001, 120000 / 1001)
                    if abs(fps - q) < 0.005), fps)
        want = round(TICKS / fps)
        if abs(tpf - want) > 1:
            msg = (f"the active sequence's frame is {tpf} ticks ({TICKS / tpf:.4f} fps), the plan's fps "
                   f"{self.plan['fps']} is {want}: every row would land off its cut. A phone clip's average rate: put the "
                   "EMPTY sequence on the plan's rate with `node lanes/premiere/premiere-bridge.mjs seq-rate "
                   # json.dumps of the forward-slashed job: a backslashed Windows path is no JSON string (\U, \j escapes)
                   + shlex.quote(json.dumps({'job': self.shown_job(quote=False), 'fps': str(self.plan['fps'])},
                                            separators=(',', ':')))
                   + "` and re-run the replay (premiere-pro § "
                   "Step 2), or fix the plan's fps if the sequence is the right one. A timeline that already carries hand "
                   "edits is never re-replayed: --any-rate places on it as it is (rows may sit a frame off)")
            if refuse and '--any-rate' not in sys.argv:
                sys.exit(f"✗ {msg}. Nothing touched.")
            print(f"⚠ {msg}.")
        self._rate_ok = True

    def seq_size(self):
        """The active sequence's frame size, read once per run: every row's Scale is sized against it."""
        if self._seq is None:
            self.require_job_project()
            self._seq = tuple(json.loads(es(r"""(function(){ var seq = app.project.activeSequence; %s
  return JSON.stringify([Number(seq.frameSizeHorizontal), Number(seq.frameSizeVertical)]); })()""" % self.seq_js())))
        return self._seq

    def hand_motion(self, gid, new_file, path_base=None):
        """The creator's hand-set Motion on the clips about to be removed, re-expressed for `new_file`, or None.

        A swap is a remove plus a fresh lay at the COMPUTED Scale, so a hand Scale 113 / Position 0.5, 0.5276 on
        a hook (2026-09-22) was lost by every re-render. Read before the removal, with the same match remove()
        uses: a Scale that is neither 100 nor the OLD render's fit on this sequence was set by hand, and is
        carried as old * fit_new / fit_old, so it stays the same size relative to the frame whatever the new
        render's resolution; a Position off the default centre is carried as it is (it is normalized to the
        frame). A Scale of exactly 100 where the fit is not 100 is the old half-size swap bug, never a choice,
        so it is NOT carried. Keyframed Motion, or clips that disagree, are named and not carried."""
        self.require_job_project()
        got = json.loads(es(r"""
(function(){
  var seq = app.project.activeSequence; %s %s var out = [];
  for (var t = 2; t < seq.videoTracks.numTracks; t++) {
    var tr = seq.videoTracks[t];
    for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i];
      var p = c.projectItem ? c.projectItem.getMediaPath() : ""; var b = p.split(/[\/\\]/).pop() || "";
      if (!mine(c, p, b)) continue;
      var sc = null, po = null;
      for (var k = 0; k < c.components.numItems; k++) if (c.components[k].displayName === "Motion") {
        var mo = c.components[k];
        for (var q = 0; q < mo.properties.numItems; q++) { var pr = mo.properties[q];
          if (pr.displayName === "Scale") sc = pr; else if (pr.displayName === "Position") po = pr; } }
      out.push({path: p, start: c.start.seconds, scale: sc ? sc.getValue() : null, pos: po ? po.getValue() : null,
                keyed: !!((sc && sc.isTimeVarying()) || (po && po.isTimeVarying()))});
    }
  }
  return JSON.stringify(out);
})()""" % (self.seq_js(), self.match_js(gid, path_base))))
        if not got:
            return None
        W, H = self.seq_size()
        fit_new = fit_scale(W, H, *probe_size(new_file)) or 100.0
        found = []
        for c in got:
            b = os.path.basename(c['path'])
            if c.get('keyed'):
                print(f"⚠ {gid}: {b} at {c['start']:.3f} has KEYFRAMED Motion, not carried: re-key it on the new clip by hand")
                continue
            s, pos = c.get('scale'), c.get('pos')
            hand_pos = bool(pos) and (abs(float(pos[0]) - 0.5) > 1e-4 or abs(float(pos[1]) - 0.5) > 1e-4)
            fit_old = None
            if c['path'] and os.path.exists(c['path']):
                fit_old = fit_scale(W, H, *probe_size(c['path'])) or 100.0
            hand_s = s is not None and abs(float(s) - 100) > 1e-3 and (fit_old is None or abs(float(s) - fit_old) > 1e-3)
            if hand_s and fit_old is None:
                print(f"⚠ {gid}: {b} is at Scale {float(s):g} but is no longer on disk to size against: Scale not carried")
                hand_s = False
            if hand_s or hand_pos:
                found.append({'scale': round(float(s) * fit_new / fit_old, 4) if hand_s else None,
                              'pos': [round(float(pos[0]), 6), round(float(pos[1]), 6)] if hand_pos else None,
                              'old_scale': float(s) if hand_s else None, 'fit_old': fit_old, 'fit_new': fit_new})
        if not found:
            return None
        kinds = {(f['scale'], tuple(f['pos'] or ())) for f in found}
        if len(kinds) > 1:
            print(f"⚠ {gid}: the clips being removed carry DIFFERENT hand Motion "
                  f"({'; '.join(sorted(str(k) for k in kinds))}): none carried, set it on the new clip by hand")
            return None
        return found[0]

    def scale_for(self, f):
        W, H = self.seq_size()
        w, h = probe_size(f)
        s = fit_scale(W, H, w, h)
        if s is None:
            print(f"⚠ {os.path.basename(f)} is {w}x{h} on a {W}x{H} sequence, not one integer multiple on both axes: "
                  "laid at Scale 100, size it by hand")
            return 100.0
        return s

    def place(self, r):
        self.require_job_project()
        F = self.F()
        carry = self._carry.pop(r['id'], None)      # hand Motion read off the clip this lay replaces (hand_motion)
        scale = carry['scale'] if carry and carry.get('scale') is not None else self.scale_for(r['file'])
        pos = carry.get('pos') if carry else None
        blend = BLEND[r['blend']] if r.get('blend') else None
        av = probe_audio(r['file'])
        out = es(r"""
(function(){
  var seq = app.project.activeSequence, root = app.project.rootItem; %s
  %s
  var PATH = %s, START = %s, END = %s, TRACK = %s, SCALE = %s, POS = %s, BLEND = %s;
  var AV = %s;
  function findByPath(bin){ for (var i = 0; i < bin.children.numItems; i++) { var c = bin.children[i];
    if (c.type === ProjectItemType.BIN) { var f = findByPath(c); if (f) return f; }
    else if (c.getMediaPath && c.getMediaPath() === PATH && String(c.name).indexOf("VID ") !== 0) return c; } return null; }
  var item = findByPath(root);      // the MASTER: an earlier AV lay's "VID " subclip shares its media path
  if (!item) { app.project.importFiles([PATH], true, root, false); item = findByPath(root); }
  if (!item) return "ERROR: import failed for " + PATH;
  // provision the track if the sequence is short (the caption layer rides V5, which a fresh
  // replay does not have): QE addTracks appends video tracks at the end, nothing below moves
  if (seq.videoTracks.numTracks <= TRACK) {
    app.enableQE();
    qe.project.getActiveSequence().addTracks(TRACK + 1 - seq.videoTracks.numTracks, seq.videoTracks.numTracks, 0, 0, 0, 0, 0);
    if (seq.videoTracks.numTracks <= TRACK) return "ERROR: could not add video track V" + (TRACK + 1);
  }
  var tr = seq.videoTracks[TRACK];
  // trim BEFORE laying: a render that runs longer than its slot (a 12 fps expansion, a versioned
  // re-render) would otherwise overwrite the head of the next clip on this track and the end pin
  // below cannot give those frames back (g15 lost 2 frames to a longer g14 swap, 2026-09-04)
  // An AV render (an mp4 with sound): overwriteClip on the master also lays its LINKED AUDIO on the audio
  // track of the same index (live 2026-09-23: g2.mp4 on A3), and an AV lay on a video track can rewrite
  // the audio under it (lanes/premiere/lab-notes.md § NEVER overwriteClip an AV project item). So it is laid
  // as a VIDEO-ONLY hard-boundary subclip of the same span (premiere-bridge.mjs lay's rule); a hard boundary
  // lays exactly its own length, and the end pin below only ever pulls the tail in.
  if (AV) {
    var lay = item.createSubClip("VID " + item.name, "0", String(Math.round((END - START + %s) * 254016000000)), 1, 1, 0);
    if (!lay) return "ERROR: createSubClip (video only) returned nothing for " + PATH;
    tr.overwriteClip(lay, START + %s);
  } else {
    item.setInPoint(0, 4); item.setOutPoint(END - START + %s, 4);
    tr.overwriteClip(item, START + %s);
    item.clearInPoint(4); item.clearOutPoint(4);
  }
  var clip = null;
  for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i];
    if (Math.abs(c.start.seconds - START) < 0.02 && c.projectItem && c.projectItem.getMediaPath() === PATH) clip = c; }
  if (!clip) return "ERROR: clip did not land on V" + (TRACK + 1) + " at " + START;
  if (clip.end.seconds > END + 0.0005) { var t = new Time(); t.seconds = END + %s; clip.end = t; }
  // overwriteClip lays at Scale 100 = native pixels: a render smaller than the sequence needs its Scale set (fit_scale),
  // and a swap re-applies the creator's hand Scale / Position read off the clip it replaced (hand_motion)
  var mo = null, sc = null, pp = null;
  for (var k = 0; k < clip.components.numItems; k++) if (clip.components[k].displayName === "Motion") mo = clip.components[k];
  if (mo) for (var q = 0; q < mo.properties.numItems; q++) {
    if (mo.properties[q].displayName === "Scale") sc = mo.properties[q];
    else if (mo.properties[q].displayName === "Position") pp = mo.properties[q]; }
  if (!sc) return "ERROR: no Motion > Scale on the clip at " + START;
  if (Math.abs(sc.getValue() - SCALE) > 1e-3) sc.setValue(SCALE, 1);
  if (POS) { if (!pp) return "ERROR: no Motion > Position on the clip at " + START; pp.setValue(POS, 1); }
  // the plan cell's blend (the highlighter's Difference): an unnamed index on Opacity > Blend Mode, read back below
  var bp = null;
  if (BLEND !== null) { bp = blendProp(clip); if (!bp) return "ERROR: no Opacity > Blend Mode on the clip at " + START;
    bp.setValue(BLEND, 1); }
  return JSON.stringify({start: clip.start.seconds, end: clip.end.seconds, name: clip.name, scale: sc.getValue(),
                         pos: POS ? pp.getValue() : null, blend: bp ? bp.getValue() : null});
})()""" % (self.seq_js(), BLEND_JS, json.dumps(r['file']), r['start'] + self.off, r['end'] + self.off, r.get('track', 2),
           scale, json.dumps(pos), json.dumps(blend), json.dumps(av), NUDGE, NUDGE, NUDGE, NUDGE, NUDGE))
        if str(out).startswith('ERROR'): sys.exit(f"{r['id']}: {out}")
        got = json.loads(out)
        got['start'] -= self.off; got['end'] -= self.off
        if abs(got['start'] - r['start']) > 1.5 * F or abs(got['end'] - r['end']) > 1.5 * F:
            sys.exit(f"{r['id']}: placed {got['start']:.4f} → {got['end']:.4f} but wanted {r['start']:.4f} → {r['end']:.4f} (readback mismatch, stopping)")
        if abs(float(got.get('scale', 0)) - scale) > 0.01:
            sys.exit(f"{r['id']}: placed at Scale {got.get('scale')} but wanted {scale:g} (readback mismatch, stopping)")
        if pos and (not got.get('pos') or max(abs(float(a) - b) for a, b in zip(got['pos'], pos)) > 1e-4):
            sys.exit(f"{r['id']}: placed at Position {got.get('pos')} but wanted {pos} (readback mismatch, stopping)")
        if blend is not None and got.get('blend') != blend:
            sys.exit(f"{r['id']}: placed with blend {blend_name(got.get('blend'))} but wanted {r['blend']} (readback mismatch, stopping)")
        if carry:
            print(f"↻ carried hand Motion {r['id']}: "
                  + ' · '.join(([f"Scale {carry['old_scale']:g} → {scale:g} (fit {carry['fit_old']:g} → {carry['fit_new']:g})"]
                                if carry.get('scale') is not None else [])
                               + ([f"Position {pos[0]:.4f}, {pos[1]:.4f}"] if pos else [])))
        return got

    def audio_snapshot(self):
        """Every clip on every AUDIO track (track, start, end, in-point in ticks, media path, name), plus the track
        count as the first row. PAGED like readback(): a long dialogue track carries hundreds of media paths."""
        self.require_job_project()
        guard = self.seq_js()
        return paged(lambda n0, n1: r"""
(function(){
  var seq = app.project.activeSequence; %s
  var N0 = %d, N1 = %d, n = 0, out = [];
  if (n++ >= N0) out.push({tracks: seq.audioTracks.numTracks});
  for (var t = 0; t < seq.audioTracks.numTracks; t++) {
    var tr = seq.audioTracks[t];
    for (var i = 0; i < tr.clips.numItems; i++) {
      if (n++ < N0) continue;
      if (out.length >= N1 - N0) return JSON.stringify(out);
      var c = tr.clips[i];
      out.push({track: t, name: c.name, start: String(c.start.ticks), end: String(c.end.ticks), inPoint: String(c.inPoint.ticks),
                path: c.projectItem ? c.projectItem.getMediaPath() : ""}); }
  }
  return JSON.stringify(out);
})()""" % (guard, n0, n1), size=PAGE)

    def audio_before(self):
        """Snapshot the audio ONCE, before this run's first timeline write (apply, or reconcile's removals)."""
        if self._audio0 is None:
            self._audio0 = self.audio_snapshot()

    def audio_check(self):
        """The placer writes V3+ only, and this PROVES the audio was left alone: the snapshot after the last write
        must equal the one before the first. On 2026-09-23 a scratch before/after snapshot around every
        placement fired once, on the creator's own live edit mid-run; a lay can also bring a render's linked
        audio with it. Either way nothing is saved: the operator reads the difference and decides."""
        diff = audio_diff(self._audio0, self.audio_snapshot())
        if diff:
            for d in diff: print('  ' + d)
            sys.exit(f"✗ AUDIO CHANGED during the placement ({len(diff)} difference(s) above). The placer never writes "
                     "audio: either the timeline was edited during the run, or a lay brought a render's linked audio "
                     "with it. The project was NOT saved: close it without saving to undo the placement, or put the "
                     "audio right and save by hand.")

    def set_blend(self, r):
        """Set the row's blend on its ALREADY-PLACED clip (the plan gained a blend after the lay) and read it back."""
        self.require_job_project()
        want = BLEND[r['blend']]
        out = es(r"""
(function(){
  var seq = app.project.activeSequence; %s
  %s
  var PATH = %s, START = %s, TRACK = %s, BLEND = %s;
  var tr = seq.videoTracks[TRACK], clip = null;
  for (var i = 0; i < tr.clips.numItems; i++) { var c = tr.clips[i];
    if (Math.abs(c.start.seconds - START) < 0.07 && c.projectItem && c.projectItem.getMediaPath() === PATH) clip = c; }
  if (!clip) return "ERROR: no clip of " + PATH + " on V" + (TRACK + 1) + " at " + START;
  var bp = blendProp(clip); if (!bp) return "ERROR: no Opacity > Blend Mode on the clip at " + START;
  bp.setValue(BLEND, 1);
  return String(bp.getValue());
})()""" % (self.seq_js(), BLEND_JS, json.dumps(r['file']), r['start'] + self.off, r.get('track', 2), want))
        if str(out).startswith('ERROR'): sys.exit(f"{r['id']}: {out}")
        if int(float(out)) != want:
            sys.exit(f"{r['id']}: blend set to {r['blend']} but reads {blend_name(int(float(out)))} (readback mismatch, stopping)")

    def apply(self):
        check_blends(self.rows)
        self.require_stamp()
        self.check_seq_rate()
        self.check_section()
        F = self.F()
        tl = self.readback()
        placed, swapped, kept, blended, relaid = [], [], [], [], []
        for r in self.rows:
            base = os.path.basename(r['file'])
            # kept only on the line --verify holds (off_row): at 1.5 frames, 23 rows a re-cut had moved one frame read
            # "already placed" while --verify called them drift (whop-first-10k, 2026-10-14)
            same = [c for c in tl if os.path.basename(c['path']) == base and not self.off_row(r, c)]
            if same:
                kept.append(r['id'])
                if r.get('blend') and same[0].get('blend') != BLEND[r['blend']]:
                    # placed right, blended wrong (the cell gained its blend after the lay): set it, no re-lay
                    self.audio_before()
                    self.set_blend(r)
                    blended.append(f"{r['id']}: blend {blend_name(same[0].get('blend'))} → {r['blend']}")
                continue
            self.audio_before()
            ver = re.compile(r'%s[-.]' % re.escape(r['id']))       # a version of this graphic: what remove(gid) takes
            stale = [c for c in tl if os.path.basename(c['path']) != base and ver.match(os.path.basename(c['path']))]
            # its OWN render laid off the row (a re-cut moved the row): taken up and laid again at the row's time, the
            # hand Motion carried, never left beside a second copy
            own = [c for c in tl if os.path.basename(c['path']) == base]
            if stale or own:
                by_id = bool(stale or ver.match(base))
                if by_id: self.keep_carry(r['id'], self.hand_motion(r['id'], r['file']))
                if own and not ver.match(base): self.keep_carry(r['id'], self.hand_motion(r['id'], r['file'], path_base=base))
                gone = (self.remove(r['id']) if by_id else []) + (self.remove(r['id'], path_base=base) if own and not ver.match(base) else [])
                (swapped if stale else relaid).append(f"{r['id']}: removed {gone}")
            try:
                got = self.place(r)
            except SystemExit as e:
                # place() refuses a row it cannot read back, which is right — but it stops mid-batch, and a
                # half-written graphics track that nobody named is how a "placed" round gets reviewed. Say
                # exactly what is on the timeline before the exit goes through; nothing has been saved yet.
                for s in swapped: print('↻ ' + s)
                for s in relaid: print('↦ ' + s)
                for p in placed: print('+ ' + p)
                print(f"✗ STOPPED at {r['id']}: {e}")
                print(f"{len(placed)} row(s) laid and {len(swapped)} swapped BEFORE this one, "
                      f"{len(self.rows) - len(kept) - len(placed)} not placed — and the project was NOT saved: "
                      "close it without saving to undo, or fix the row and re-run --apply (it is idempotent).")
                raise
            placed.append(f"{r['id']}: V{r.get('track', 2) + 1} {got['start']:.4f} → {got['end']:.4f} {base}"
                          + (f" · Scale {got['scale']:g}" if got.get('scale', 100) != 100 else '')
                          + (f" · blend {r['blend']}" if r.get('blend') else ''))
        for s in swapped: print('↻ ' + s)
        for s in relaid: print('↦ ' + s)
        for p in placed: print('+ ' + p)
        for b in blended: print('◐ ' + b)
        print(f"{len(kept)} already placed · {len(placed)} placed · {len(swapped)} swapped"
              + (f" · {len(relaid)} re-laid at their row's time" if relaid else '')
              + (f" · {len(blended)} blend(s) set" if blended else ''))
        if self._audio0 is not None:     # a write happened here or in reconcile(): prove the audio, then save
            self.audio_check()
            print('audio untouched: every audio clip reads back as it was before the first write')
            sh('node', str(BRIDGE), 'save_project')
            print('saved')
            # the DRIFT verify() prints is the run's verdict: returned so --apply EXITS non-zero on it.
            # `place-graphics.py --apply && review-frames.py` otherwise grabs its evidence round off a
            # timeline the placer itself just called wrong.
            return self.verify(quiet=True)
        return True

def opt(a, flag):
    """The NAME after `flag` in argv, None when the flag is absent."""
    if flag not in a: return None
    i = a.index(flag)
    if i + 1 >= len(a) or a[i + 1].startswith('--'): sys.exit(f'{flag} needs a NAME')
    return a[i + 1]


def main():
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    p = Placer(a[0], variant=opt(a, '--variant'), sequence=opt(a, '--sequence'))
    if '--plan' in a:
        rows, changes = p.derive()
        for c in changes: print('  ' + c)
        if '--write' in a:
            with open(p.pj, 'w', encoding="utf-8") as f: json.dump(rows, f, indent=1)
            print(f'wrote {len(rows)} rows -> {p.pj}')
            # and reconcile the plan to them in the same command, so the gate's `plan` check cannot FAIL on
            # frame-snap noise (2026-09-19: 62 values, a whole 1800s gate run). BOUNDED to half a frame —
            # the rows were just derived FROM the plan, so a sub-frame gap can only be snap()'s rounding,
            # and anything bigger is a real plan-vs-build disagreement the gate exists to show (see
            # sync_plan). Syncing at the end of --apply instead would stomp a hand-retimed plan that had
            # not been re-derived.
            p.rows = rows
            p.sync_plan(max_frames=0.5)
        else:
            print(f'{len(rows)} rows derived, {len(changes)} change(s) vs {p.pj.name} (add --write to save)')
    elif '--verify' in a:
        sys.exit(0 if p.verify() else 1)
    elif '--reconcile' in a:     # before --apply: `--reconcile --apply` is the reconcile, not a plain apply
        sys.exit(0 if p.reconcile('--apply' in a) else 1)
    elif '--apply' in a:
        sys.exit(0 if p.apply() else 1)
    elif '--remove' in a:
        # every id after the flag, by spaces and/or commas: one id per call read `g4,g5` as ONE id, removed nothing and
        # printed [] (2026-10-14). An id that takes nothing off the timeline fails the run, named.
        i, ids = a.index('--remove') + 1, []
        while i < len(a) and not a[i].startswith('-'):
            ids += [x.strip() for x in a[i].split(',') if x.strip()]; i += 1
        if not ids: sys.exit('--remove needs one or more graphic ids (g4, or g4 g5,g6): nothing removed')
        p.check_section()        # the span it removes from is the plan's offset's
        missing = []
        for gid in ids:
            gone = p.remove(gid)
            print(f"{gid}: {gone}")
            if not gone: missing.append(gid)
        if missing:
            sys.exit(f"✗ nothing on V3+ under {', '.join(missing)}: check the id(s) against placement.json")
    elif '--sync-plan' in a:
        p.sync_plan()
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
