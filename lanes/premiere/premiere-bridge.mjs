// Headless CLI driver for the Premiere MCP bridge — calls tool handlers directly,
// no MCP session needed. Works from any session as long as the MCP Bridge (CEP)
// panel is running in Premiere (Window > Extensions > MCP Bridge (CEP), temp dir
// /tmp/premiere-mcp-bridge on macOS, %TEMP%\premiere-mcp-bridge on Windows).
//
// Engine: vendor/premiere-mcp — our pinned local clone of
// github.com/hetpatel-11/Adobe_Premiere_Pro_MCP (the original project; the old
// premiere-pro-mcp npm package was a knockoff republish with a broken CEP shim).
// Pinned by clone: update ONLY via deliberate `git pull` + re-test, record the
// new commit hash in the premiere-pro skill.
//
// Usage:
//   node lanes/premiere/premiere-bridge.mjs --list [filter]        # list tools
//   node lanes/premiere/premiere-bridge.mjs --desc <tool|command>  # a tool's params, or a command's usage below
//   node lanes/premiere/premiere-bridge.mjs <tool> ['<json-args>'] # call one tool
//
// THE GUARD. Every command that takes a job (`replay` from its cuts.json path, "job" in the opts JSON,
// `es --job`) refuses with exit 2, nothing touched, unless the ACTIVE project is the job's AND the active
// sequence passes THE SEQUENCE RULE (lanes/premiere/job_guard.py's, word for word): it must exist, belong
// to that project (by sequenceID AND by the project file its treePath names: a Save-As copy keeps every
// ID), be held by no other open project of the same file name, equal the requested name when one is given
// ("sequence" in the opts, `es --sequence`,
// else env VE_SEQUENCE), and otherwise equal the sequence named after the job folder when the project
// holds one. VE_SEQUENCE='<name>' is how a second cut of a job (an AD clone) is targeted deliberately.
//
//   node lanes/premiere/premiere-bridge.mjs replay <cuts.json> <clipName> [--clear | --append]
//     # premiere-pro step 2: replay the EDL onto V1 of the ACTIVE sequence as
//     # individual overwrite edits via one batched ExtendScript (per-segment
//     # in/out + overwriteClip with position read-back — the your-job
//     # pattern; append position is read back after every overwrite because
//     # Premiere quantizes boundaries to the frame grid).
//     # REFUSES (exit 2, nothing laid) when any segment carries "media": that segment was laid from
//     # substitute media (a lip-sync clip), so its raw clip is not what is on the cut. Replay an EDL
//     # without it, then `lay` it from the media's own project item. Also exit 2, nothing laid or saved,
//     # when any segment's clip is not in the project: every clip is found before the first lay.
//     # REFUSES (exit 2, nothing laid) when V1 or A1 already holds clips: a replay onto them APPENDED after the
//     # last one (a re-cut's re-lay ran the timeline to 212 s, both cuts end to end, 2026-10-14). Say which:
//     #   --clear   saves first (the rollback), then empties V1 and A1 in the same script, after every clip is
//     #             found, and lays from 0: the re-cut re-lay. V2+ (grade, graphics) and A2+ (SFX, music) stay.
//     #   --append  lays after V1's last clip: the next section of the per-section colour replay.
//   node lanes/premiere/premiere-bridge.mjs seq-rate '{"job":"projects/<job>","fps":"30000/1001"}'
//     # Puts the EMPTY active sequence on a standard frame rate (setSettings, read back, saved). Premiere
//     # builds a sequence from a variable-rate phone clip at its AVERAGE rate (29.9766 for an iPhone take
//     # at r 30000/1001, 2026-09-27), so run this right after create-from-clip + emptying the tracks, with
//     # the raw's ffprobe r_frame_rate; `replay` refuses a sequence off the standard rates. Refuses a
//     # sequence that holds clips: a rate change moves every cut off the grid. "job" is REQUIRED (the guard).
//   node lanes/premiere/premiere-bridge.mjs frame '{"time":17.0,"out":"<path-no-ext>"}'
//     # A relative `out` resolves against YOUR cwd (never Premiere's), the parent folder is
//     # created, a trailing .png is stripped, and the command FAILS if the PNG did not land.
//     # Program-monitor-accurate frame grab from the ACTIVE sequence at `time` seconds —
//     # full render: keyframed effects + all video tracks/alpha overlays composited.
//     # The frame is the one Premiere SHOWS at `time`: floor((time + 1e-6) / frame), never the nearest,
//     # so a grab a hair before a cut is the last frame before it. "job" in the opts runs THE GUARD
//     # ("sequence" names the one you mean); without it the grab is an ad-hoc read of whatever is
//     # active ("sequence" without "job" is refused). Either way it prints the sequence it grabbed.
//     # Calls QE exportFramePNG with a proper NON-DROP TIMECODE STRING built from the
//     # sequence fps. That arg form is the ONLY correct one: numeric seconds THROW
//     # ("Illegal Parameter type") and the vendored export_frame tool's fallback passes
//     # String(seconds), which QE parses as a FRAMES timecode — it silently exports the
//     # frame at ~t/fps seconds (measured 2026-07-18: "18" → frame 18 ≈ 0.75s). A ticks
//     # string is equally wrong. Writes <out>.png and prints the timecode used.
//     # It ALSO prints any video track whose Toggle Track Output is OFF: such a track is
//     # silently missing from the composite, so a grade or graphic on it measures delta 0
//     # exactly like a dead effect — and the Exposure control is muted too, so it cannot
//     # tell them apart. Read that line before concluding anything rendered nothing.
//   node lanes/premiere/premiere-bridge.mjs diff-edl <cuts.json> [more cuts.json...]
//     # The rough-cut learning loop (skill Step 5): diff the ACTIVE sequence's
//     # V1 against the authored EDL(s) after the creator hand-edits. Matches
//     # timeline clips to EDL segments by source-range overlap (clips matched to
//     # EDLs by clip filename), then prints: deleted segments (with their
//     # transcript), boundary moves > 1 frame with the WORDS around each moved
//     # boundary (needs <job>/transcript/words.json next to each cuts.json),
//     # graft pairs (OUT-extension + IN-trim at one joint), new material, and
//     # timeline gaps. Read-only; never writes. The hand-edited timeline is the
//     # source of truth — this command exists to LEARN from it, not to sync it.
//     # A clip's source out is inPoint + (end − start), in ticks, never `outPoint`, which reads
//     # STALE after a clip.end write; where the two disagree by more than a frame it prints
//     # STALE-OUTPOINT as information, never an OUT move.
//   node lanes/premiere/premiere-bridge.mjs zoom ['<json-opts>']
//     # Opening zoom preset (re-dialled 2026-09-10): applies Transform (with
//     # Shutter Angle 360 motion blur) to a clip on V1 of the active sequence and
//     # bakes a per-frame scale ramp — the only way to script ease shapes, since
//     # Premiere's ease presets aren't reachable via the API. The scale defaults
//     # ARE the lock — 115 → 100 over 18 frames, quart ease-out; verify frame 9
//     # reads 100.94 (a cubic bake reads 101.88). Numbers:
//     # presets/youtube/default/README.md § Opening zoom-out. ALWAYS pass fps — it
//     # is the sequence's own rate, not part of the lock. All keys land at the
//     # clip's in point (source-time domain).
//     # Opts: {"job":"projects/<job>","clip":0,"from":115,"to":100,"frames":18,"ease":"quart","fps":"30000/1001"}
//     #   job: REQUIRED, the job folder: the active project must be its .prproj or nothing is touched
//     #   clip: 0-based clip index on V1 · ease: quart (the opening zoom-out's lock) | inout (the push-in's S) | cubic | quint | overshoot | linear
//     #   fps: the SEQUENCE rate as a rational string (e.g. "30000/1001") — key
//     #   spacing is 1/fps, so a wrong rate stretches/squeezes the ramp
//     #   WHERE the ramp starts (default = the clip's in point, the opening zoom-out):
//     #     "at": <sequence seconds>  — e.g. a word timestamp from the transcript
//     #     "offset": <frames>        — frames past the clip's in point
//     #   With a start past the in point, keys BEFORE it are preserved (a clip can hold the
//     #   opening zoom-out and a later push-in in the same property). Errors (exit 2, nothing saved) if
//     #   the ramp would start before the clip or run past its end.
//     # Emphasis push-in (youtube/default move 5), synced to a word:
//     #   zoom '{"job":"projects/<job>","clip":8,"from":100,"to":115,"frames":18,"ease":"inout","fps":"30000/1001","at":28.3}'
//   node lanes/premiere/premiere-bridge.mjs grade-layer ['<json-opts>']
//     # Pipeline step 4, the layer half in ONE command: mints an adjustment layer AT THE ACTIVE
//     # SEQUENCE'S OWN FRAME SIZE (read off the sequence, never typed — a 16:9 layer on a
//     # vertical timeline can be scaled to fit and leave the top and bottom ungraded), imports
//     # it, provisions tracks up to the V1/V2/V3/V4 map, places it spanning V1's full extent on
//     # the grade track, names the clip GRADE, adds Lumetri, and saves. Idempotent: it refuses
//     # if that track already holds a GRADE clip, and reuses a same-size layer already in the
//     # project instead of stacking duplicate bin items. Reports any track whose output is off.
//     # Opts: {"job":"projects/<job>","track":2,"minTracks":4,"lumetri":true} (job REQUIRED: the active-project guard)
//     # The LOOK is the separate headless step that follows (project must be CLOSED):
//     #   premiere-up.sh --quit -> grade-lut.py apply <job>.prproj -> premiere-up.sh <job>.prproj
//   node lanes/premiere/premiere-bridge.mjs lay '{"job":"projects/<job>","item":"<project item>","track":"A1","in":12.34,"out":18.90,"at":765.12}'
//     # ONE row onto a track that ALREADY holds clips — the sanctioned alternative to a hand
//     # `overwriteClip`, which wiped A1 from the lay point to the end of the sequence, twice
//     # (lanes/premiere/lab-notes.md § NEVER overwriteClip an AV project item onto an AUDIO track).
//     # The subclip flags come from the TRACK's kind, never the caller: a video-only subclip on a V
//     # track, an audio-only one on an A track, hard boundaries always (so it lays exactly its own
//     # length instead of running to media end). It counts the track's clips BEFORE and AFTER and
//     # refuses to save when the count fell further than the clips it overlapped — the check that
//     # would have caught the 39-clip wipe in the same second. `save_project` runs BEFORE the write
//     # because a scripted edit is not in Premiere's undo stack: the saved .prproj is the rollback.
//     # The laid clip carries the source item's colour label ("label":n overrides it).
//     # in/out/at are SECONDS; `in_point` in the readback is subclip-relative (hard boundaries), not source time.
//   node lanes/premiere/premiere-bridge.mjs labels ['{"job":"projects/<job>","tracks":["V1","A1"]}']
//     # Read-only: the colour-label runs on those tracks (default V1 + A1), the creator's map of the
//     # sections. Exits 1 on a grey (label 0) clip inside a labelled timeline, or on a colour that
//     # re-opens after its run closed — two sections sharing one project item, which is how a
//     # relabel silently recoloured a neighbour. It reads the PROJECT ITEM's label, so a clip laid
//     # before a relabel still shows the old colour on screen: the confirmation is a window grab.
//   node lanes/premiere/premiere-bridge.mjs clear-previews ['{"job":"projects/<job>"}']
//     # Deletes the active sequence's render/preview files over its whole length. A scripted move
//     # leaves STALE cache frames that the Program monitor AND exportFrame keep showing where no
//     # clip exists (lanes/premiere/lab-notes.md § stale render cache), so an evidence grab after a
//     # move runs this first (`review-frames.py --clear-previews`). It is not automatic: it throws
//     # away every green bar the creator rendered by hand, over the whole sequence. The QE call needs
//     # BOTH timecodes — the one-argument form throws "Not Enough Parameters" — and the end timecode
//     # is the sequence end's CEILING plus a frame, on the same nominal-fps helper `frame` uses.
//   node lanes/premiere/premiere-bridge.mjs es (--job <dir> [--sequence <name>] | --no-guard) [--timeout <ms>] '<extendscript>' | --file <path>
//     # The bridge's ONE output contract, for every hand script and for lanes/premiere/pes.py:
//     #   · --job runs THE GUARD every other command here runs (active project + sequence rule;
//     #     --sequence names the sequence, else VE_SEQUENCE): an ad-hoc
//     #     script is the one write path that used to skip it, and it can lay clips (see `lay`).
//     #     A read you are sure of passes --no-guard instead; one of the two is REQUIRED, so
//     #     the guard is never skipped by forgetting it. A Python caller guards ONCE with
//     #     lanes/premiere/job_guard.py and its pes.es passes --no-guard per call.
//     #   · a single EXPRESSION ('1+1', 'app.project.path', an IIFE) is returned for you; a statement
//     #     body must carry its own 'return <value>;', and one with none exits 2 before it is sent.
//     #   · ONE line of stdout, always — the result verbatim, or single-line JSON for an object.
//     #   · a runtime failure comes back as "ERROR: <message> @ line <n>" instead of the bare
//     #     "ExtendScript execution failed via CEP evalScript()", and exits 1 (the line counts the
//     #     bridge's own helper prelude, so it is relative to the script, not to your file).
//     #     A script that returns nothing (undefined) is an ERROR line too, never the text "undefined".
//     #   · a result at or over the CEP return cap (65535 chars) exits 1 NAMING the cap, rather
//     #     than handing the caller JSON that dies as "Unterminated string ... char 65534": page
//     #     the read (pes.paged) instead of widening it.
//     #   · --timeout reaches the CEP panel's own watchdog, which otherwise kills a script at 45 s
//     #     and reports a good long export as a failure. Watch `lsof` as the second proof.
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { LOCAL, localUsage, esBody, esEmptyResult, TC_FN, RATE_FN, TPS, srcOutOf, GUARD_ES, requestedSequence,
         guardVerdict, mediaRefusal, offGridWarning, rateTicks, seqRateRefusal, STD_RATES, steadyBeat, esLit,
         bridgeError, avSlipFrames } from "./bridge-lib.mjs";

// Bridge dir must match the CEP panel's default: /tmp on macOS, %TEMP% on Windows.
// (URL.href, not .pathname, for the imports — pathname yields /C:/... on Windows.)
const { tmpdir } = await import("node:os");
process.env.PREMIERE_TEMP_DIR = process.env.PREMIERE_TEMP_DIR ||
  (process.platform === "win32" ? `${tmpdir()}\\premiere-mcp-bridge` : "/tmp/premiere-mcp-bridge");
const V = new URL("../../vendor/premiere-mcp/", import.meta.url);
const { PremiereProBridge } = await import(new URL("dist/bridge/index.js", V).href);
const { PremiereProTools } = await import(new URL("dist/tools/index.js", V).href);

const bridge = new PremiereProBridge();
await bridge.initialize();
// A torn heartbeat read is not an absent panel (bridge-lib.mjs steadyBeat): the engine's own read, asked again.
if (typeof bridge.readHeartbeat === "function") {
  const readOnce = bridge.readHeartbeat.bind(bridge);
  bridge.readHeartbeat = () => steadyBeat(readOnce);
}
const tools = new PremiereProTools(bridge);

const call = async (name, args = {}) => {
  const r = await tools.executeTool(name, args);
  if (r && r.success === false) throw new Error(`${name} failed: ${r.error}`);
  return r && r.data !== undefined ? r.data : r;
};
// This file's own scripts go straight to bridge.executeScript, the call the `es` command makes: the
// engine's execute_extendscript tool logs "Executing tool: ... with args" with the WHOLE script on every
// call, which buried every lay/frame/zoom result under its own source. A failure still throws.
const es = async (code) => {
  let r;
  try { r = await bridge.executeScript(code, undefined, true); }
  catch (e) { throw new Error(`execute_extendscript failed: ${e && e.message ? e.message : e}`); }
  if (r && r.success === false) throw new Error(`execute_extendscript failed: ${bridgeError(r.error)}`);
  return r;
};

// THE GUARD (lanes/premiere/lab-notes.md § The active project is checked before every write; the Python
// scripts run lanes/premiere/job_guard.py, the same readback and the same rule): every command here reads or
// writes the ACTIVE sequence, which is whatever the operator last clicked, so the active project must be the
// job's (projects/<job>/..., sections included) and the active sequence must pass the sequence rule
// (bridge-lib.mjs). `start` is any path inside the job, `fallback` the job dir when no projects/ ancestor
// exists, `requested` the caller's own sequence name (env VE_SEQUENCE otherwise). Refuses, never picks.
async function requireJobProject(start, fallback, requested) {
  let jobDir = resolve(start);
  while (dirname(jobDir) !== jobDir && basename(dirname(jobDir)) !== "projects") jobDir = dirname(jobDir);
  if (dirname(jobDir) === jobDir) jobDir = resolve(fallback);
  const raw = await es(GUARD_ES);
  const g = JSON.parse(typeof raw === "string" ? raw : (raw && raw.result !== undefined ? raw.result : JSON.stringify(raw)));
  const refusal = guardVerdict(g, jobDir, requestedSequence(requested, process.env));
  if (refusal) { console.error(refusal); process.exit(2); }
  return g.path;
}
// frame, labels and clear-previews guard only when given a "job" (a jobless call is an ad-hoc read). A
// "sequence" means nothing without the guard, so alone it is refused, as `es --sequence` is without --job,
// rather than silently ignored by a caller who thinks the sequence was checked.
async function guardIfJob(opts) {
  if (opts.job) return requireJobProject(opts.job, opts.job, opts.sequence);
  if (opts.sequence !== undefined) {
    console.error(`${cmd}: "sequence" names the sequence the "job" guard must find active; pass it with "job"`);
    process.exit(2);
  }
}

const [cmd, a1, a2] = process.argv.slice(2);

if (!cmd || cmd === "--list") {
  const filter = a1?.toLowerCase();
  const keep = (n) => !filter || n.includes(filter);
  console.log([...LOCAL.filter(keep), "# --- engine tools ---",
    ...tools.getAvailableTools().map(t => t.name).filter(keep)].join("\n"));
} else if (cmd === "--desc") {
  // A LOCAL command's usage is its block in the header above (the one copy of it); an engine tool's is its schema.
  if (LOCAL.includes(a1)) console.log(localUsage(readFileSync(new URL(import.meta.url), "utf-8"), a1));
  else {
    const t = tools.getAvailableTools().find(x => x.name === a1);
    if (!t) { console.error(`--desc: no command or tool named ${a1 ?? "(none)"} (--list shows both)`); process.exit(1); }
    console.log(JSON.stringify({ description: t.description, parameters: t.inputSchema }, null, 2));
  }
} else if (cmd === "replay") {
  // <cuts.json> <clipName> and at most one of --clear / --append, in any order: a flag is never read as a path or a name
  const rargs = process.argv.slice(3), flags = rargs.filter(x => x.startsWith("--"));
  const [edlPath, clipName] = rargs.filter(x => !x.startsWith("--"));
  const unknown = flags.filter(x => x !== "--clear" && x !== "--append");
  if (!edlPath || unknown.length || flags.length > 1) {
    console.error(`replay: usage: replay <cuts.json> <clipName> [--clear | --append]` +
                  (unknown.length ? ` (unknown: ${unknown.join(" ")})` : flags.length > 1 ? " (one of them, not both)" : ""));
    process.exit(2);
  }
  const mode = flags.length ? flags[0].slice(2) : "";
  const segs = JSON.parse(readFileSync(edlPath, "utf-8")).segments;
  // A segment laid from substitute media cannot come back from its raw clip: refuse before anything is sent.
  const media = mediaRefusal(segs);
  if (media) { console.error(media); process.exit(2); }
  // WHERE A BOUNDARY LANDS (124 boundaries + a WAV bounce cross-correlated against the raw,
  // a screen-recording outro section, 2026-09-13): Premiere floors the requested in/out to the SOURCE frame
  // grid, then floors again to the SEQUENCE grid. Same-rate footage never shows it (both floors hit
  // the EDL's own frame), but a 30 fps screen recording on a 23.976 sequence landed every in AND
  // out one sequence frame (41.7 ms) early: a clipped tail on every cut. So the ES below first
  // rounds each boundary to the NEAREST sequence frame (the author's intent; an EDL already on that
  // grid is unchanged), then requests the first source frame at or above it, which the double floor
  // maps back onto exactly that sequence frame whenever the source rate >= the sequence rate. The
  // +1e-4 nudge stays: tick conversion floors, so a grid time serialised a hair low drops a frame.
  // Carry each segment's SOURCE CLIP. rough-cut explicitly allows cuts to cross clips
  // ("segments CAN cross clips in any order — that's the whole point"), so a multi-file EDL
  // must resolve one project item PER SEGMENT. Falls back to the CLI <clipName> when a
  // segment has no `clip` (single-file EDLs, and the older hand-written ones).
  const segJson = esLit(segs.map(s => [
    s.start, s.end, s.clip ? String(s.clip).split("/").pop() : null,
  ]));
  // The active-project guard: the replay lays V1 of the ACTIVE sequence, so it must belong to the job that owns
  // this cuts.json (<job>/transcript/cuts.json when there is no projects/ ancestor).
  await requireJobProject(dirname(resolve(edlPath)), resolve(dirname(resolve(edlPath)), ".."));
  const seqTicks = await es("(function(){ var q = app.project.activeSequence; return q ? String(q.getSettings().videoFrameRate.ticks) : ''; })()");
  // The raw's own r_frame_rate for the refusal's hint, when every EDL clip under <job>/raw/ reads the same one
  // (probed only for a sequence that is off the standard rates).
  const offStd = Number(seqTicks) > 0 && !Object.values(STD_RATES).some(v => Math.abs(v - Number(seqTicks)) <= 1);
  const rawFps = !offStd ? null : await (async () => {
    const { execFileSync } = await import("node:child_process");
    const rawDir = resolve(dirname(resolve(edlPath)), "..", "raw");
    const got = new Set();
    for (const c of new Set(segs.map(s => (s.clip ? String(s.clip).split("/").pop() : clipName)))) {
      try {
        // the first row: ffprobe 9 prints a timecoded file's video row twice (its tmcd stream group, then the stream)
        got.add((execFileSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
          "-of", "default=nw=1:nk=1", resolve(rawDir, c)], { encoding: "utf8" }).split("\n")[0]).trim());
      } catch { return null; }
    }
    return got.size === 1 ? [...got][0] : null;
  })();
  const rateRefusal = seqRateRefusal(seqTicks, rawFps);
  if (rateRefusal) { console.error(`replay: refused, nothing laid: ${rateRefusal}`); process.exit(2); }
  const gridWarn = offGridWarning(segs, seqTicks);
  if (gridWarn) console.error(gridWarn);
  // THE CAMERA A/V SLIP (rough-cut § Lip sync at intake): a camera whose audio runs early is laid with V1 this many
  // sequence frames LATER than A1, read from transcript/av-slip.json beside the cuts.json (written by
  // workflows/lip-sync.py --slip-out). The EDL stays the AUDIO cut; live-edl.py and diff-edl subtract the slip on
  // read-back. Missing file = 0 (an unmeasured camera is laid as cut, as before).
  const slip = avSlipFrames(dirname(resolve(edlPath)));
  // --clear is a write Premiere's undo stack does not hold: the saved .prproj is the rollback (as `lay` saves first)
  if (mode === "clear") await call("save_project");
  const r = await es(`
(function(){
var SEGS = ${segJson};
var NAME = ${esLit(clipName)};${RATE_FN}
var SLIP = ${slip};
var MODE = ${esLit(mode)};
function find(bin, name){
  for (var i = 0; i < bin.children.numItems; i++) {
    var c = bin.children[i];
    if (c.name === name) return c;
    if (c.type === ProjectItemType.BIN) { var f = find(c, name); if (f) return f; }
  }
  return null;
}
var cache = {}, used = [], rates = {}, labels = {};
function resolve(name){
  if (cache[name] !== undefined) return cache[name];
  var it = find(app.project.rootItem, name);
  cache[name] = it;
  if (it) {
    used.push(name);
    // The colour label is stamped onto a clip AT INSERT TIME from the project item, so it is decided
    // here: two sections resolving to ONE item cannot be told apart afterwards, and a label-0 item
    // lays grey clips inside a coloured section. Report it now rather than at diagnosis time.
    try { labels[name] = Number(it.getColorLabel()); } catch (e) { labels[name] = -1; }
    var fps = 0;
    try { fps = it.getFootageInterpretation().frameRate; } catch (e) {}
    rates[name] = snapRate(fps);                           // the source grid (bridge-lib.mjs snapRate)
  }
  return it;
}
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
var FRS = seq.getSettings().videoFrameRate.seconds;      // the sequence's frame duration
function land(t, fps){
  var q = Math.round(t / FRS) * FRS;                       // nearest sequence frame
  if (!(fps > 0)) return q + 1e-4;
  return Math.ceil(q * fps - 1e-6) / fps + 1e-4;           // first source frame at/above it
}
// Every segment's clip is found BEFORE the first lay: a clip missing at segment k used to leave 0..k-1 on V1, and the
// retry appended the whole EDL after them.
for (var s0 = 0; s0 < SEGS.length; s0++)
  if (!resolve(SEGS[s0][2] || NAME)) return "ERROR: project item not found for segment " + s0 + ": " + (SEGS[s0][2] || NAME);
var vt = seq.videoTracks[0], at1 = seq.audioTracks.numTracks ? seq.audioTracks[0] : null;
function held(){ return vt.clips.numItems + (at1 ? at1.clips.numItems : 0); }
// an occupied V1/A1 is never appended to unasked: a re-cut's re-lay ran the timeline on with both cuts (2026-10-14)
if (held() && !MODE) return "ERROR: V1/A1 of " + seq.name + " already hold " + vt.clips.numItems + "/" + (at1 ? at1.clips.numItems : 0) +
  " clip(s), and a replay onto them lays AFTER the last one. Re-laying the cut: --clear empties V1 and A1 first. " +
  "The next section of a per-section replay: --append";
var cleared = 0;
if (MODE === "clear") {
  var both = at1 ? [vt, at1] : [vt];
  for (var k = 0; k < both.length; k++)
    for (var i = both[k].clips.numItems - 1; i >= 0; i--) { both[k].clips[i].remove(false, false); cleared++; }
  if (held()) return "ERROR: --clear left " + held() + " clip(s) on V1/A1, nothing laid: close the project without saving to undo the clear";
}
var pos = vt.clips.numItems ? vt.clips[vt.clips.numItems - 1].end.seconds : 0;
var first = vt.clips.numItems;
for (var s = 0; s < SEGS.length; s++) {
  var want = SEGS[s][2] || NAME;                 // per-segment clip, else the CLI name
  var item = resolve(want);
  item.setInPoint(land(SEGS[s][0], rates[want]), 4);
  item.setOutPoint(land(SEGS[s][1], rates[want]), 4);
  vt.overwriteClip(item, pos);
  pos = vt.clips[vt.clips.numItems - 1].end.seconds;
}
for (var u = 0; u < used.length; u++) {
  var ci = cache[used[u]];
  if (ci) { ci.clearInPoint(4); ci.clearOutPoint(4); }
}
// the slip: in and out move together in ticks, start/end stay (proven on 105 clips, 2026-10-04); a fresh clip has no
// keyframes yet, so nothing else moves. Read back per clip.
var slipNote = "";
if (SLIP) {
  var TPS = 254016000000, DT = SLIP * Math.round(FRS * TPS), bad = 0, n = 0;
  for (var k = first; k < vt.clips.numItems; k++) {
    var c = vt.clips[k], st = c.start.ticks, en = c.end.ticks, inT = Number(c.inPoint.ticks), outT = Number(c.outPoint.ticks);
    var ti = new Time(); ti.ticks = String(inT + DT); var to = new Time(); to.ticks = String(outT + DT);
    c.inPoint = ti; c.outPoint = to; c = vt.clips[k]; n++;
    if (c.start.ticks != st || c.end.ticks != en || Number(c.inPoint.ticks) - inT != DT) bad++;
  }
  slipNote = ", V1 slipped " + (SLIP > 0 ? "+" : "") + SLIP + " frame(s) against A1 on " + n + " clip(s)" + (bad ? " (" + bad + " FAILED THE READBACK)" : "");
  if (bad) return "ERROR: the A/V slip failed its readback on " + bad + " of " + n + " clip(s): undo the replay";
}
var srcs = [];
for (var n = 0; n < used.length; n++)
  srcs.push(used[n] + " (label " + (labels[used[n]] >= 0 ? labels[used[n]] : "?") + ")");
return (cleared ? "cleared " + cleared + " clip(s) off V1/A1, " : "") + "laid " + SEGS.length + " segments from " + used.length +
       " source clip(s) [" + srcs.join(", ") + "], timeline ends " + pos.toFixed(3) + "s" + slipNote;
})()
`);
  // An ERROR is returned before anything is laid: exit 2 and leave the saved project as it was.
  if (String(r).startsWith("ERROR")) { console.error(`${r} (replay: nothing laid, nothing saved)`); process.exit(2); }
  console.log(JSON.stringify(r));
  console.log(JSON.stringify(await call("save_project")));
} else if (cmd === "seq-rate") {
  const opts = JSON.parse(a1 || "{}");
  if (!opts.job || !opts.fps) throw new Error('seq-rate needs {"job":"projects/<job>","fps":"30000/1001"}');
  const tpf = rateTicks(opts.fps);
  if (!tpf) throw new Error(`seq-rate: ${opts.fps} is not one of the standard rates (${Object.keys(STD_RATES).join(", ")})`);
  await requireJobProject(opts.job, opts.job, opts.sequence);
  const r = await es(`
(function(){
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
var n = 0;
for (var t = 0; t < seq.videoTracks.numTracks; t++) n += seq.videoTracks[t].clips.numItems;
for (var a = 0; a < seq.audioTracks.numTracks; a++) n += seq.audioTracks[a].clips.numItems;
if (n) return "ERROR: " + seq.name + " holds " + n + " clip(s): a rate change moves every cut off the grid, so empty it and re-run the replay after";
var st = seq.getSettings(), was = String(st.videoFrameRate.ticks);
var fr = new Time(); fr.ticks = "${tpf}";
st.videoFrameRate = fr;
seq.setSettings(st);
return seq.name + ": " + was + " -> " + String(seq.getSettings().videoFrameRate.ticks) + " ticks a frame";
})()`);
  if (String(r).startsWith("ERROR")) { console.error(`seq-rate: ${r}`); process.exit(2); }
  if (!String(r).endsWith(` ${tpf} ticks a frame`)) { console.error(`seq-rate: the rate did not read back: ${r}`); process.exit(1); }
  console.log(r);
  console.log(JSON.stringify(await call("save_project")));
} else if (cmd === "diff-edl") {
  const { dirname, basename, join } = await import("node:path");
  const edlPaths = process.argv.slice(3);
  if (!edlPaths.length) throw new Error("diff-edl needs at least one cuts.json path");

  // segments from every EDL, keyed by clip basename; word lists for boundary context
  const segs = [];
  const wordsByClip = {};
  for (const p of edlPaths) {
    // V1 is laid av-slip.json's frames LATER than A1 (the replay): its in-points are read back that much earlier
    const slipF = avSlipFrames(dirname(p));
    if (slipF) console.log(`${p}: V1 carries an A/V slip of ${slipF} frame(s) (av-slip.json), subtracted from its read-back`);
    for (const [i, s] of JSON.parse(readFileSync(p, "utf-8")).segments.entries())
      segs.push({ edl: basename(dirname(dirname(p))) || p, i, clip: basename(s.clip), ...s, slipF, used: false });
    // transcript/words.json sits next to transcript/cuts.json
    try {
      const w = JSON.parse(readFileSync(join(dirname(p), "words.json"), "utf-8"));
      for (const c of w.clips || []) wordsByClip[basename(c.clip)] = c.words || [];
    } catch { /* words optional — boundary context just goes quiet */ }
  }
  const wordsAt = (clip, t) => {
    const ws = wordsByClip[clip];
    if (!ws) return "";
    const near = ws.filter(w => w.end > t - 0.8 && w.start < t + 0.8).map(w => w.w).join(" ");
    return near ? `  [“${near}”]` : "";
  };

  const dump = await es(`
(function(){
var s = app.project.activeSequence;
if (!s) return "ERROR: no active sequence";
var fps = 1 / s.getSettings().videoFrameRate.seconds;
var v = [];
for (var t = 0; t < s.videoTracks.numTracks; t++) {
  var vt = s.videoTracks[t];
  for (var i = 0; i < vt.clips.numItems; i++) {
    // Ticks only, speed only when it is not 1: this is one unpaged return under the 65535-char cap,
    // so the seconds are derived below rather than read twice.
    var c = vt.clips[i], o = { trk: t, name: c.name, inT: Number(c.inPoint.ticks),
      startT: Number(c.start.ticks), endT: Number(c.end.ticks), outT: Number(c.outPoint.ticks) };
    try { var sp = c.getSpeed(); if (sp !== 1) o.speed = sp; } catch (e) {}
    v.push(o);
  }
}
return JSON.stringify({ fps: fps, clips: v });
})()`);
  const tl = JSON.parse(typeof dump === "string" ? dump : dump.result || JSON.stringify(dump));
  if (tl.ERROR) throw new Error(tl.ERROR);
  const FRAME = 1 / (tl.fps || 30);
  const fmt = (x) => x.toFixed(2);

  // The source out comes off the clip's own length, never the outPoint readback (bridge-lib.mjs srcOutOf):
  // a stale outPoint is reported as what it is, and never reaches the move detection below.
  const infos = [];
  for (const c of tl.clips) {
    c.tlIn = c.startT / TPS; c.tlOut = c.endT / TPS; c.srcIn = Math.round(c.inT * (c.speed > 0 ? c.speed : 1)) / TPS;
    const d = srcOutOf(c, FRAME);
    c.srcOut = d.srcOut;
    if (d.stale) infos.push(`STALE-OUTPOINT ${c.name}: outPoint ${d.readOut.toFixed(3)}, its own length says ${d.srcOut.toFixed(3)}`
      + `  (V${c.trk + 1} @${fmt(c.tlIn)}s; a stale readback, not a trim)`);
  }
  if (infos.length) console.log(infos.join("\n"));

  const lines = [];
  let grafts = 0, moves = 0;
  const clipRows = [];
  for (const c of tl.clips) {
    let best = null, bo = 0;
    const sh = (s) => (c.trk === 0 ? s.slipF * FRAME : 0);
    for (const s of segs) {
      if (c.name !== s.clip) continue;
      const o = Math.min(c.srcOut - sh(s), s.end) - Math.max(c.srcIn - sh(s), s.start);
      if (o > bo) { bo = o; best = s; }
    }
    if (!best) { lines.push(`NEW      ${c.name} src ${fmt(c.srcIn)}-${fmt(c.srcOut)} — not from any EDL segment`); continue; }
    best.used = true;
    clipRows.push({ c, s: best, dIn: c.srcIn - sh(best) - best.start, dOut: c.srcOut - sh(best) - best.end });
  }
  for (let k = 0; k < clipRows.length; k++) {
    const { c, s, dIn, dOut } = clipRows[k];
    if (Math.abs(dIn) > FRAME) {
      moves++;
      lines.push(`IN  ${dIn > 0 ? "trimmed " : "extended"} ${Math.abs(dIn).toFixed(2)}s  ${s.edl}#${s.i} @src ${fmt(s.start)}→${fmt(c.srcIn)}${wordsAt(c.name, c.srcIn)}`);
    }
    if (Math.abs(dOut) > FRAME) {
      moves++;
      lines.push(`OUT ${dOut > 0 ? "extended" : "trimmed "} ${Math.abs(dOut).toFixed(2)}s  ${s.edl}#${s.i} @src ${fmt(s.end)}→${fmt(c.srcOut)}${wordsAt(c.name, c.srcOut)}`);
    }
    // graft signature: this clip's OUT extended into words + next clip's IN trimmed past its start
    const nxt = clipRows[k + 1];
    if (nxt && dOut > FRAME && nxt.dIn > FRAME) {
      grafts++;
      lines.push(`  ↳ GRAFT at joint: kept take-1 through ${fmt(c.srcOut)}, re-entered take 2 at ${fmt(nxt.c.srcIn)} — mid-sentence splice around a restart`);
    }
  }
  for (const s of segs.filter(x => !x.used))
    lines.push(`DELETED  ${s.edl}#${s.i} ${fmt(s.start)}-${fmt(s.end)}  “${(s.transcript || "").slice(0, 90)}”`);
  const v1 = tl.clips.filter(c => c.trk === 0);
  for (let k = 1; k < v1.length; k++) {
    const g = v1[k].tlIn - v1[k - 1].tlOut;
    if (Math.abs(g) > 0.001) lines.push(`GAP      ${g > 0 ? "+" : ""}${g.toFixed(3)}s on the timeline at ${fmt(v1[k - 1].tlOut)}`);
  }
  console.log(lines.length ? lines.join("\n") : "timeline matches the EDL(s) exactly — no hand edits detected");
  console.log(`— ${tl.clips.length} timeline clips vs ${segs.length} EDL segments · ${segs.filter(x => !x.used).length} deleted · ${moves} boundary moves · ${grafts} graft(s) · end ${fmt(v1.length ? v1[v1.length - 1].tlOut : 0)}s`);
} else if (cmd === "frame") {
  const opts = JSON.parse(a1);
  if (!(opts.time >= 0) || !opts.out) throw new Error('frame needs {"time":<seconds>,"out":"<path-no-ext>"}');
  // With a job, THE GUARD: a grab of the wrong sequence is evidence of the wrong cut (2026-09-23: the active
  // sequence switched from the job's AD cut to its organic between calls, and a whole sheet came back organic).
  await guardIfJob(opts);
  // `<out>.png` is the ONE filename this command promises, so strip a trailing .png: otherwise QE
  // writes g5.png and the landed-check below looks for g5.png.png and throws on a good grab.
  opts.out = String(opts.out).replace(/\.png$/i, "");
  // The ExtendScript runs INSIDE Premiere, whose cwd is its own app folder, so a relative `out`
  // handed straight through writes nothing while the command still reports success: that is how
  // 184 review grabs landed nowhere (2026-09-07). Resolve against the CALLER's cwd first.
  const ABS = /^([a-zA-Z]:[\\/]|\/)/;
  if (!ABS.test(opts.out)) opts.out = resolve(process.cwd(), opts.out);
  // Premiere on Windows wants a drive path — a Git Bash /c/... path is the one path here that comes from outside.
  // QE exportFramePNG then needs it with BACKSLASHES: C:/... throws "Unknown error exception" and no grab lands
  // (Premiere 26.5 on Windows, 2026-09-27), so the ExtendScript below gets the backslashed form.
  if (process.platform === "win32") opts.out = String(opts.out).replace(/\\/g, "/").replace(/^\/([a-zA-Z])\//, "$1:/");
  // Any other rooted path on Windows is a Git Bash MOUNT (/tmp is %TEMP%): node reads it as C:\tmp\..., makes that
  // folder and the grab fails with a bare "ExtendScript execution failed" (the Windows re-test, 2026-09-27). cygpath
  // maps it; without cygpath, refuse and say why.
  if (process.platform === "win32" && opts.out.startsWith("/")) {
    const { execFileSync } = await import("node:child_process");
    try { opts.out = execFileSync("cygpath", ["-m", opts.out], { encoding: "utf8" }).trim(); }
    catch { throw new Error(`frame: ${opts.out} is a Git Bash path and cygpath is not on PATH: pass a drive path (C:/...)`); }
  }
  mkdirSync(dirname(opts.out), { recursive: true });
  const r = await es(`
(function(){
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
var frameDur = seq.getSettings().videoFrameRate.seconds;${TC_FN}
var f = frameAt(${opts.time}, frameDur);
var tc = tcOfFrame(f, frameDur);
app.enableQE();
var qs = qe.project.getActiveSequence();
if (!qs) return "ERROR: no QE sequence";
qs.exportFramePNG(tc, ${esLit(process.platform === "win32" ? opts.out.replace(/\//g, "\\") : opts.out)});
// Toggle Track Output state, reported on EVERY grab. A muted track is silently absent from the
// composite, so a grade/graphic on it measures delta 0 — indistinguishable from a dead effect,
// and the Exposure control cannot tell them apart either (it is muted too). Cost a whole
// diagnosis on a real job, 2026-09-02. Only tracks that actually hold clips are worth naming.
var off = [];
for (var t = 0; t < seq.videoTracks.numTracks; t++) {
  var trk = seq.videoTracks[t];
  if (trk.isMuted() && trk.clips.numItems > 0)
    off.push("V" + (t + 1) + "(" + trk.clips.numItems + " clip" + (trk.clips.numItems === 1 ? "" : "s") + ")");
}
return "exported " + seq.name + " @ " + tc + " (frame " + f + ") -> " + ${esLit(opts.out)} + ".png"
  + (off.length ? "  |  ⚠ TRACK OUTPUT OFF, NOT IN THIS FRAME: " + off.join(", ")
                  + " — anything on those tracks measures delta 0; setMute(0) to include it, and restore what the creator had"
                : "");
})()
`);
  // Premiere's return string is built from ExtendScript state alone: it says "exported" whether or
  // not a file landed. Check the PNG, or a whole review round reads as good grabs (2026-09-07).
  if (!existsSync(`${opts.out}.png`))
    throw new Error(`frame: Premiere reported ${r} but ${opts.out}.png does not exist`);
  console.log(JSON.stringify(r));
} else if (cmd === "zoom") {
  const opts = { clip: 0, from: 115, to: 100, frames: 18, ease: "quart", fps: "24000/1001",
                 offset: 0, at: null, ...(a1 ? JSON.parse(a1) : {}) };
  if (!opts.job) throw new Error('zoom: pass "job" in the opts JSON (e.g. "projects/<job>") so the active-project guard runs first');
  await requireJobProject(opts.job, opts.job, opts.sequence);
  const [fpsNum, fpsDen = 1] = String(opts.fps).split("/").map(Number);
  if (!fpsNum || !fpsDen) throw new Error(`bad fps: ${opts.fps} (rational string like "30000/1001")`);
  const EASE = {
    linear: t => t,
    cubic: t => 1 - Math.pow(1 - t, 3),
    quart: t => 1 - Math.pow(1 - t, 4),    // sharper ease-out: 94% of the travel by the midpoint (2026-09-10)
    quint: t => 1 - Math.pow(1 - t, 5),    // sharper still: 97% by the midpoint
    inout: t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,   // the S: cubic ease-in-out, 50% at the midpoint, eased on both ends (the push-in, the user 2026-09-10)
    overshoot: t => { const s = 1.70158; return 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2); },
  };
  const fn = EASE[opts.ease];
  if (!fn) throw new Error(`unknown ease: ${opts.ease} (use ${Object.keys(EASE).join("/")})`);
  const vals = [];
  for (let f = 0; f <= opts.frames; f++) vals.push(opts.from + (opts.to - opts.from) * fn(f / opts.frames));
  const r = await es(`
(function(){
var TRACK = 0, CLIP = ${opts.clip}, VALS = ${JSON.stringify(vals)};
var frameDur = ${fpsDen} / ${fpsNum};
var AT = ${opts.at === null ? "null" : Number(opts.at)}, OFFSET_F = ${Number(opts.offset)};
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
var clip = seq.videoTracks[TRACK].clips[CLIP];
if (!clip) return "ERROR: no clip " + CLIP + " on V" + (TRACK + 1);
var hasTransform = false;
for (var i = 0; i < clip.components.numItems; i++) {
  if (clip.components[i].displayName === "Transform") hasTransform = true;
}
if (!hasTransform) {
  app.enableQE();
  var qtrack = qe.project.getActiveSequence().getVideoTrackAt(TRACK);
  var nth = -1;
  for (var q = 0; q < qtrack.numItems; q++) {
    var it = qtrack.getItemAt(q);
    if (it && it.type === "Clip") {
      nth++;
      if (nth === CLIP) { it.addVideoEffect(qe.project.getVideoEffectByName("Transform")); break; }
    }
  }
  clip = seq.videoTracks[TRACK].clips[CLIP];
}
var inPt = clip.inPoint.seconds;
// WHERE THE RAMP STARTS. Default = the clip's in point (the opening zoom-out). "at" is a
// SEQUENCE time in seconds (use a word timestamp straight from the transcript); "offset" is
// frames from the in point. Keys live in SOURCE time, so both resolve through inPoint.
var startSrc = (AT !== null) ? (inPt + (AT - clip.start.seconds)) : (inPt + OFFSET_F * frameDur);
if (startSrc < inPt - 1e-6) return "ERROR: ramp starts before the clip (" + startSrc.toFixed(4) + " < " + inPt.toFixed(4) + ")";
var clipEndSrc = inPt + (clip.end.seconds - clip.start.seconds);
if (startSrc + (VALS.length - 1) * frameDur > clipEndSrc + 1e-6)
  return "ERROR: not enough clip left — ramp needs " + (VALS.length - 1) + " frames past " + startSrc.toFixed(4) + "s, clip ends at " + clipEndSrc.toFixed(4) + "s";
var baked = 0;
for (var i = 0; i < clip.components.numItems; i++) {
  var comp = clip.components[i];
  if (comp.displayName !== "Transform") continue;
  for (var p = 0; p < comp.properties.numItems; p++) {
    var prop = comp.properties[p];
    var dn = prop.displayName;
    if (dn === "Scale Height" || dn === "Scale Width") {
      // Clear only from the ramp start ONWARD. At the default offset that is every key
      // (unchanged behaviour); with an offset it preserves anything earlier — clip 1 carries
      // the opening zoom-out AND a push-in in this same property, and a blanket clear would
      // silently destroy the opening move.
      var keys = prop.getKeys();
      if (keys) {
        for (var k = keys.length - 1; k >= 0; k--)
          if (keys[k].seconds >= startSrc - 1e-6) prop.removeKey(keys[k], 1);
      }
      if (!prop.isTimeVarying()) prop.setTimeVarying(true);
      for (var f = 0; f < VALS.length; f++) {
        var kt = startSrc + f * frameDur;
        prop.addKey(kt);
        prop.setValueAtKey(kt, VALS[f], 1);
      }
      var check = prop.getKeys();
      for (var c = 0; c < check.length; c++) {
        if (check[c].seconds < startSrc - 1e-6) continue;   // leave earlier ramps alone
        try { prop.setInterpolationTypeAtKey(check[c], 0, 1); } catch (e) {}
      }
      baked++;
    } else if (dn === "Shutter Angle") {
      prop.setValue(360, 1);
    }
  }
}
if (baked !== 2) return "ERROR: baked " + baked + " scale props, expected 2";
return "zoom baked: clip " + CLIP + ", " + VALS.length + " keys/prop, first key " + startSrc.toFixed(4) + "s (source time)";
})()
`);
  if (String(r).startsWith("ERROR")) { console.error(`${r} (zoom: not saved)`); process.exit(2); }
  console.log(JSON.stringify(r));
  console.log(JSON.stringify(await call("save_project")));
} else if (cmd === "grade-layer") {
  // Pipeline step 4, the whole layer half in ONE command: mint an adjustment layer at the
  // ACTIVE SEQUENCE'S OWN FRAME SIZE, import it, place it spanning the timeline on the grade
  // track, name it GRADE, add Lumetri. The size is READ, never typed — that is the point of
  // the command (2026-09-02). The Look is the separate headless step that follows:
  //   premiere-up.sh --quit -> grade-lut.py apply <job>.prproj -> premiere-up.sh <job>.prproj
  const opts = { track: 2, minTracks: 4, lumetri: true, ...(a1 ? JSON.parse(a1) : {}) };
  if (!opts.job) throw new Error('grade-layer: pass "job" in the opts JSON (e.g. "projects/<job>") so the active-project guard runs first');
  await requireJobProject(opts.job, opts.job, opts.sequence);
  const { execFileSync } = await import("node:child_process");

  // 1. Read what the sequence actually is. Never assume 16:9, and never trust a job's format
  //    tag over the sequence in front of you.
  const probe = await es(`
(function(){
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
var v1 = seq.videoTracks[0], end = 0;
for (var c = 0; c < v1.clips.numItems; c++)
  if (v1.clips[c].end.seconds > end) end = v1.clips[c].end.seconds;
// ☠️ The grade track must be EMPTY or already ours. overwriteClip REPLACES whatever occupies
// the range without asking (the vendored engine's own source records a case of it silently
// destroying audio), so anything here that is not our GRADE clip is a stop, not a fall-through.
// The real scenario: a timeline that got graphics before the grade ran. CLAUDE.md's documented
// recovery for that is a QE addTracks INSERT at index 1, which shifts the old V2 up to V3 with
// its effects intact — never an overwrite.
var existing = "";
if (seq.videoTracks.numTracks >= ${opts.track}) {
  var gt = seq.videoTracks[${opts.track - 1}], mine = 0, other = 0;
  for (var g = 0; g < gt.clips.numItems; g++)
    if (gt.clips[g].name === "GRADE") mine++; else other++;
  if (mine) existing = "V${opts.track} already holds a GRADE clip";
  else if (other) existing = "V${opts.track} holds " + other + " non-GRADE clip(s) — refusing to overwrite. "
    + "If graphics are already on this track, INSERT a grade track instead "
    + "(QE addTracks(1, 1, 0,0,0,0,0) shifts them up intact) — see CLAUDE.md, the grade-under-graphics note.";
}
return [seq.name, seq.frameSizeHorizontal, seq.frameSizeVertical, end,
        seq.videoTracks.numTracks, v1.clips.numItems, existing].join("\\u0001");
})()
`);
  if (String(probe).startsWith("ERROR")) throw new Error(probe);
  const [seqName, W, H, endStr, nTracks, v1Clips, existing] = String(probe).split("\u0001");
  if (existing) { console.log(JSON.stringify({ skipped: existing })); process.exit(0); }
  if (Number(v1Clips) === 0) throw new Error(`V1 of "${seqName}" is empty — lay the footage before the grade layer`);
  const end = Number(endStr);

  // 2. Mint a template at exactly that size. Deterministic: same size => byte-identical file,
  //    so re-running is idempotent and a second job at the same size re-imports the same item.
  // fileURLToPath, never .pathname — pathname yields /C:/... on Windows (same trap the imports
  // at the top of this file avoid). And probe for python: Windows ships a fake `python3` Store
  // stub that `command -v` trusts, so fall back to `python` the way every .sh here does.
  const { fileURLToPath } = await import("node:url");
  const mint = fileURLToPath(new URL("premiere-templates/mint-adjustment-layer.py", import.meta.url));
  let PY = "python3";
  try { execFileSync(PY, ["-c", ""], { stdio: "ignore" }); } catch { PY = "python"; }
  const [tplPath, tplUuid] = execFileSync(PY, [mint, `${W}x${H}`], { encoding: "utf-8" })
    .trim().split(/\r?\n/);

  // 3. Import, provision tracks, place, name, Lumetri — all read back before reporting.
  const r = await es(`
(function(){
var seq = app.project.activeSequence, root = app.project.rootItem;
var ITEM = "Adjustment Layer ${W}x${H}", JUNK = "adj-template-${W}x${H}";

// Recursive, like this file's own find() in the replay command: the editor is free to file
// into a bin, and a flat scan would miss it and re-import a duplicate.
function findItem(name, bin){
  bin = bin || root;
  for (var i = 0; i < bin.children.numItems; i++) {
    var c = bin.children[i];
    if (c.name === name) return c;
    if (c.type === ProjectItemType.BIN) { var f = findItem(name, c); if (f) return f; }
  }
  return null;
}

// A project that already holds a layer at this size (a second sequence of the same shape,
// or a re-run) reuses it — importing again would just stack duplicate bin items.
var al = findItem(ITEM), imported = "reused";
if (!al) {
  if (!app.project.importSequences(${esLit(tplPath)}, [${esLit(tplUuid)}]))
    return "ERROR: importSequences returned false";
  al = findItem(ITEM);
  imported = "minted";
}
if (!al) return "ERROR: '" + ITEM + "' not found after import";
var junk = findItem(JUNK);
// The donor drags a throwaway sequence in with it. deleteBin on a fresh bin is the only
// removal that works on a clip item (deleteItem/deleteBin no-op directly).
if (junk) { var b = root.createBin("__trash"); junk.moveBin(b); b.deleteBin(); }

// A fresh sequence has too few tracks for V1 footage / V2 grade / V3 graphics / V4 accents.
// addTracks APPENDS, so nothing already placed moves.
app.enableQE();
var added = 0;
while (seq.videoTracks.numTracks < Math.max(${opts.track}, ${opts.minTracks})) {
  qe.project.getActiveSequence().addTracks(1, seq.videoTracks.numTracks, 0, 0, 0, 0, 0);
  added++;
  if (added > 8) return "ERROR: addTracks did not grow the sequence";
}

var gt = seq.videoTracks[${opts.track - 1}];
gt.overwriteClip(al, 0);
var g = null;
for (var c = 0; c < gt.clips.numItems; c++) if (gt.clips[c].start.seconds < 1e-6) g = gt.clips[c];
if (!g) return "ERROR: layer did not land on V${opts.track}";
var t = new Time(); t.seconds = ${end};
g.end = t;
try { g.name = "GRADE"; } catch (e) {}

var lum = "none";
if (${opts.lumetri}) {
  var qt = qe.project.getActiveSequence().getVideoTrackAt(${opts.track - 1}), target = null;
  for (var q = 0; q < qt.numItems; q++) { var it = qt.getItemAt(q); if (it.type === "Clip") { target = it; break; } }
  if (!target) return "ERROR: no QE clip on V${opts.track}";
  var eff = qe.project.getVideoEffectByName("Lumetri Color");
  if (!eff) return "ERROR: 'Lumetri Color' effect not found";
  target.addVideoEffect(eff);
  var names = [];
  for (var k = 0; k < g.components.numItems; k++) names.push(g.components[k].displayName);
  lum = names.join("/");
}

// Toggle Track Output: a muted grade track measures delta 0 on every later verification and
// is indistinguishable from a dead effect, so say so now rather than at diagnosis time.
var muted = [];
for (var m = 0; m < seq.videoTracks.numTracks; m++)
  if (seq.videoTracks[m].isMuted() && seq.videoTracks[m].clips.numItems > 0) muted.push("V" + (m + 1));

return ["ok", seq.name, "${W}x${H} (" + imported + ")", g.name,
        g.start.seconds.toFixed(3) + "-" + g.end.seconds.toFixed(3),
        seq.videoTracks.numTracks + " video tracks (+" + added + ")", lum,
        muted.length ? "\\u26a0 TRACK OUTPUT OFF: " + muted.join(",") : "all track output on"].join("  |  ");
})()
`);
  if (String(r).startsWith("ERROR")) throw new Error(r);
  console.log(String(r));
  console.log(JSON.stringify(await call("save_project")));
} else if (cmd === "lay") {
  // ONE row onto a track that ALREADY holds clips. A hand `overwriteClip` of an AV project item onto
  // A1 wiped the track from the lay point to the END of the sequence (39 clips) and dumped the items'
  // video halves at the 53-minute mark — twice, and neither was recoverable because a scripted edit
  // never enters Premiere's undo stack. So the flags come from the TRACK, not the caller, and the
  // clip count is read before and after: the damage is caught in the same second, against a .prproj
  // saved a moment earlier. Owner of the rule: lanes/premiere/lab-notes.md.
  const opts = { label: null, ...(a1 ? JSON.parse(a1) : {}) };
  if (!opts.job) throw new Error('lay: pass "job" in the opts JSON (e.g. "projects/<job>") so the active-project guard runs first');
  if (!opts.item || !opts.track || !(opts.in >= 0) || !(opts.out > opts.in) || !(opts.at >= 0))
    throw new Error('lay needs {"job":"projects/<job>","item":"<project item>","track":"A1","in":<s>,"out":<s>,"at":<s>}');
  const tk = /^([VvAa])(\d+)$/.exec(String(opts.track));
  if (!tk || Number(tk[2]) < 1) throw new Error(`lay: bad track "${opts.track}" — V1..Vn or A1..An`);
  const KIND = tk[1].toUpperCase(), IDX = Number(tk[2]) - 1;
  await requireJobProject(opts.job, opts.job, opts.sequence);
  // The saved .prproj is the ONLY rollback for a scripted mutation, so it is taken BEFORE the write.
  await call("save_project");
  const r = await es(`
(function(){
var NAME = ${esLit(opts.item)}, KIND = ${JSON.stringify(KIND)}, IDX = ${IDX};${RATE_FN}
var IN = ${Number(opts.in)}, OUT = ${Number(opts.out)}, AT = ${Number(opts.at)};
var LABEL = ${opts.label === null || opts.label === undefined ? "null" : Number(opts.label)};
var TPS = 254016000000;                                  // ticks per second
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
function find(bin, name){
  for (var i = 0; i < bin.children.numItems; i++) {
    var c = bin.children[i];
    if (c.name === name) return c;
    if (c.type === ProjectItemType.BIN) { var f = find(c, name); if (f) return f; }
  }
  return null;
}
var item = find(app.project.rootItem, NAME);
if (!item) return "ERROR: project item not found: " + NAME;
var list = (KIND === "A") ? seq.audioTracks : seq.videoTracks;
if (IDX >= list.numTracks) return "ERROR: no " + KIND + (IDX + 1) + ": the sequence has " + list.numTracks + " " + (KIND === "A" ? "audio" : "video") + " tracks";
var tr = list[IDX];
var FRS = seq.getSettings().videoFrameRate.seconds;      // the sequence's frame duration
var TPF = Math.round(FRS * TPS);                         // ticks per sequence frame (an integer at every rate)
var fps = 0;
try { fps = item.getFootageInterpretation().frameRate; } catch (e) {}
fps = snapRate(fps);                                     // the replay's own source grid (bridge-lib.mjs snapRate)
// the replay's own grid math, for the same reason: Premiere floors to the SOURCE grid, then to the
// SEQUENCE grid, so a mixed-rate source lands a frame early unless the first source frame at or
// above the intended sequence frame is asked for.
function land(t){
  var q = Math.round(t / FRS) * FRS;
  if (!(fps > 0)) return q + 1e-4;
  return Math.ceil(q * fps - 1e-6) / fps + 1e-4;
}
var inSrc = land(IN);
var frames = Math.max(1, Math.round((OUT - IN) / FRS));  // the wanted length, on the sequence grid
var atF = Math.round(AT / FRS);
// The state BEFORE the write. \`overlap\` is what this lay may legitimately replace; anything beyond
// that is the runaway, and there is no undo to fall back on. \`kept\` counts the edges of overlapped
// clips that run past the span and survive as pieces of their own; \`spans\` is every clip as it was.
var before = tr.clips.numItems, overlap = 0, kept = 0, endBefore = 0, spans = [];
for (var i = 0; i < before; i++) {
  var c0 = tr.clips[i];
  if (c0.start.seconds < (atF + frames) * FRS - 1e-6 && c0.end.seconds > atF * FRS + 1e-6) {
    overlap++;
    if (c0.start.seconds < atF * FRS - 1e-6) kept++;
    if (c0.end.seconds > (atF + frames) * FRS + 1e-6) kept++;
  }
  if (c0.end.seconds > endBefore) endBefore = c0.end.seconds;
  spans.push([c0.start.seconds, c0.end.seconds]);
}
// THE SUBCLIP. Hard boundaries (arg 4 = 1) so it lays exactly its own length — a soft-boundary
// subclip ignores its out-point and runs to media end, wiping every later clip on the track. The
// halves come from the TRACK's kind, so an AV item cannot reach an audio track at all.
// Its length is set in TICKS, a quarter-frame UNDER the wanted length: an out-point that overshoots
// by a hair lays one frame too many and trims the head off the neighbour, while the clip's own \`end\`
// below can only ever pull the tail back to the exact frame (a hard boundary cannot be extended).
var inT = Math.round(inSrc * TPS), outT = inT + frames * TPF - Math.round(TPF / 4);
var subName = (KIND === "A" ? "AUD " : "VID ") + NAME + " @" + inSrc.toFixed(2) + "s";
var sub = item.createSubClip(subName, String(inT), String(outT),
                             1, KIND === "V" ? 1 : 0, KIND === "A" ? 1 : 0);
if (!sub) return "ERROR: createSubClip returned nothing for " + NAME;
// The label is stamped at insert time, and every clip laid after the first replay carries its
// SECTION's colour: the subclip inherits the source item's unless the caller names one.
var label = LABEL;
if (label === null) { try { label = Number(item.getColorLabel()); } catch (e) { label = null; } }
if (label !== null) { try { sub.setColorLabel(label); } catch (e) {} }
var ts = new Time(); ts.ticks = String(atF * TPF + 10000);
tr.overwriteClip(sub, ts);
var after = tr.clips.numItems, laid = null, endAfter = 0;
for (var j = 0; j < after; j++) {
  var c = tr.clips[j];
  if (Math.abs(c.start.seconds - atF * FRS) < FRS * 0.5) laid = c;
  if (c.end.seconds > endAfter) endAfter = c.end.seconds;
}
if (after < before - overlap)
  return "ERROR: " + KIND + (IDX + 1) + " LOST CLIPS: " + before + " -> " + after
       + " (a lay over " + overlap + " clip(s) cannot take the count below " + (before - overlap)
       + "). NOT saved: revert to the .prproj saved a moment ago — a scripted edit is not in the undo stack.";
if (!laid) return "ERROR: nothing landed at " + (atF * FRS).toFixed(3) + "s on " + KIND + (IDX + 1)
       + " (clips " + before + " -> " + after + ")";
var te = new Time(); te.ticks = String((atF + frames) * TPF);
laid.end = te;
// THE REMNANT. The short subclip lays a frame shy of the span, so over an existing clip the overwrite
// leaves that clip's last frame behind and the pin above lays the new clip OVER it (a short-form job,
// 2026-09-22: one frame of the old clip under the new one's tail, saved). Whatever now
// sits wholly inside the laid span and was not a clip of its own before the write is that remnant.
var EPS = FRS * 0.5, ls = laid.start.seconds, le = laid.end.seconds, removed = 0;
for (var k = tr.clips.numItems - 1; k >= 0; k--) {
  var rc = tr.clips[k], rs = rc.start.seconds, re = rc.end.seconds;
  if (Math.abs(rs - ls) < EPS || rs < ls - EPS || re > le + EPS) continue;   // the laid clip, or not inside it
  var was = false;
  for (var s = 0; s < spans.length; s++)
    if (Math.abs(spans[s][0] - rs) < EPS && Math.abs(spans[s][1] - re) < EPS) was = true;
  if (was) continue;
  try { rc.remove(false, false); removed++; } catch (e) {}
}
// THE STRADDLER. A lay that ends inside a longer clip leaves that clip's tail starting where the short
// subclip stopped, so the pin lays the new clip's last frame over its head. Trim the head to the laid
// end and move its in-point by the same amount: a \`start\` write alone slides the picture a frame
// (the in-point stays put, proven on a program grab 2026-09-22). ALL IN TICKS, compared exactly: the
// same write in float seconds landed one tick under the frame, Premiere floored it to the frame
// before, and every seconds readback rounded it back to look right.
var trimmed = 0, TE = Number(te.ticks);
for (var q = 0; q < tr.clips.numItems; q++) {
  var sc = tr.clips[q], ss = sc.start.seconds, se = sc.end.seconds;
  if (!(ss > ls + EPS && ss < le - EPS && se > le + EPS)) continue;
  var siT = Number(sc.inPoint.ticks), seT = Number(sc.end.ticks), inT2 = siT + (TE - Number(sc.start.ticks));
  var tst = new Time(); tst.ticks = String(TE); sc.start = tst;
  var tin = new Time(); tin.ticks = String(inT2); sc.inPoint = tin;
  if (Number(sc.start.ticks) !== TE || Number(sc.end.ticks) !== seT || Number(sc.inPoint.ticks) !== inT2)
    return "ERROR: the clip after the lay did not trim cleanly: wanted ticks " + TE + "-" + seT + " in " + inT2
         + ", got " + sc.start.ticks + "-" + sc.end.ticks + " in " + sc.inPoint.ticks
         + ". NOT saved: revert to the .prproj saved a moment ago — a scripted edit is not in the undo stack.";
  trimmed++;
}
// The exact count, now the remnant is gone: the overlapped clips leave, the laid one arrives, and an
// overlapped clip that ran past an edge keeps that end as its own piece.
after = tr.clips.numItems;
if (after !== before - overlap + 1 + kept)
  return "ERROR: " + KIND + (IDX + 1) + " holds " + after + " clips after the lay, expected " + (before - overlap + 1 + kept)
       + " (" + before + " before, " + overlap + " overlapped, " + kept + " edge piece(s) kept, 1 laid, "
       + removed + " remnant(s) removed). NOT saved: revert to the .prproj saved a moment ago — a scripted edit is not in the undo stack.";
// The track's end as it now stands: the scan above ran before the pin, when the short subclip still
// ended a frame shy (live 2026-09-23: 0.959 reported for a clip ending at 1.001).
endAfter = 0;
for (var n = 0; n < after; n++) if (tr.clips[n].end.seconds > endAfter) endAfter = tr.clips[n].end.seconds;
return JSON.stringify({track: KIND + (IDX + 1), item: NAME, subclip: subName, label: label,
  at: laid.start.seconds, end: laid.end.seconds,
  frames_laid: Math.round((laid.end.seconds - laid.start.seconds) / FRS), frames_wanted: frames,
  src_in: inSrc, in_point: laid.inPoint.seconds, src_fps: fps, seq_fps: 1 / FRS,
  clips_before: before, clips_after: after, overlapped: overlap, remnants_removed: removed, heads_trimmed: trimmed,
  track_end_before: endBefore, track_end_after: endAfter});
})()
`);
  const out = typeof r === "string" ? r : JSON.stringify(r);
  if (out.startsWith("ERROR")) { console.error(out); process.exit(2); }
  const laid = JSON.parse(out);
  console.log(out);
  // A length that did not come out right is not persisted: the pre-write save is still the file on
  // disk, so the operator can revert instead of hunting a one-frame hole later.
  if (laid.frames_laid !== laid.frames_wanted) {
    // Name the likeliest cause instead of leaving a bare count: the subclip's length is asked for in
    // SEQUENCE ticks while its boundaries land on the SOURCE grid, so a source whose rate is not the
    // sequence's can come back a frame short — the one case where re-running changes nothing.
    const mixed = laid.src_fps > 0 && Math.abs(laid.src_fps - laid.seq_fps) > 0.01;
    console.error(`lay: ${laid.track} holds ${laid.frames_laid} frames, wanted ${laid.frames_wanted} — NOT saved, revert and re-run`
      + (mixed ? `\n  the source runs at ${laid.src_fps.toFixed(3)} fps on a ${laid.seq_fps.toFixed(3)} fps sequence: the subclip's`
               + ` boundaries land on the SOURCE grid, so this row may never lay exactly. Lay it by hand, or conform the source.`
               : ""));
    process.exit(2);
  }
  console.log(JSON.stringify(await call("save_project")));
} else if (cmd === "labels") {
  // Read-only. The colour labels are the creator's map of the sections, and they live on the PROJECT
  // ITEM, stamped onto a clip at insert time: two sections cut from one source file cannot be told
  // apart, and a subclip minted later lays grey. Reasoning about item names instead of looking
  // "proved" five clean runs while three outro clips sat blue and four preview clips orange.
  const opts = { tracks: ["V1", "A1"], ...(a1 ? JSON.parse(a1) : {}) };
  await guardIfJob(opts);
  const r = await es(`
(function(){
var TRACKS = ${JSON.stringify(opts.tracks)};
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
var out = {project: app.project.path, sequence: seq.name, tracks: []};
for (var t = 0; t < TRACKS.length; t++) {
  var kind = String(TRACKS[t]).charAt(0).toUpperCase(), idx = Number(String(TRACKS[t]).substring(1)) - 1;
  var list = (kind === "A") ? seq.audioTracks : seq.videoTracks;
  if (!(idx >= 0) || idx >= list.numTracks) { out.tracks.push({track: TRACKS[t], error: "no such track"}); continue; }
  var tr = list[idx], runs = [], greys = 0;
  for (var i = 0; i < tr.clips.numItems; i++) {
    var c = tr.clips[i], lab = -1, nm = "";
    try { nm = c.projectItem.name; } catch (e) {}
    try { lab = Number(c.projectItem.getColorLabel()); } catch (e) {}
    if (lab === 0) greys++;
    var last = runs.length ? runs[runs.length - 1] : null;
    if (last && last.label === lab) {
      last.n++; last.to = c.end.seconds;
      if (last.items.length < 6 && ("|" + last.items.join("|") + "|").indexOf("|" + nm + "|") < 0) last.items.push(nm);
    }
    else runs.push({label: lab, from: c.start.seconds, to: c.end.seconds, n: 1, items: [nm]});
  }
  out.tracks.push({track: TRACKS[t], clips: tr.clips.numItems, greys: greys, runs: runs});
}
return JSON.stringify(out);
})()
`);
  let dump = r;
  if (typeof dump === "string") {
    if (dump.startsWith("ERROR")) { console.error(dump); process.exit(1); }
    dump = JSON.parse(dump);
  }
  console.log(`${dump.project} · ${dump.sequence}`);
  let bad = 0;
  for (const t of dump.tracks) {
    if (t.error) { console.log(`${t.track}  ${t.error}`); continue; }
    console.log(`${t.track}  ${t.clips} clips · ${t.runs.length} colour run(s)`);
    const seen = new Map();
    for (const [k, run] of t.runs.entries()) {
      console.log(`  label ${String(run.label).padStart(2)}  ${run.from.toFixed(2)}-${run.to.toFixed(2)}s  ${String(run.n).padStart(4)} clip(s)  [${run.items.slice(0, 3).join(", ")}]`);
      // a colour that re-opens after its run closed = two sections sharing one project item, which
      // is what made labelling one section recolour the other.
      if (run.label > 0 && seen.has(run.label) && seen.get(run.label) < k - 1) {
        console.log(`  ⚠ ${t.track}: label ${run.label} RE-OPENS at ${run.from.toFixed(2)}s after closing earlier — two sections share one project item; re-import that source under its own name`);
        bad++;
      }
      seen.set(run.label, k);
    }
    // all-grey = a timeline that never used sections, not a defect; grey INSIDE colour is one.
    if (t.greys && t.greys < t.clips) {
      console.log(`  ⚠ ${t.track}: ${t.greys} clip(s) carry label 0 inside a labelled timeline — lay them from their section's own project item`);
      bad++;
    }
  }
  console.log("this reads the PROJECT ITEM's label: a clip laid BEFORE a relabel still shows the old colour on screen,\n"
    + 'so confirm with ./workflows/window-grab.sh "Adobe Premiere" out.png on the V1/A1 strip.');
  if (bad) process.exit(1);
} else if (cmd === "clear-previews") {
  // A scripted move (trackItem.move() on hundreds of clips) does not invalidate Premiere's preview
  // cache, so the Program monitor AND exportFrame keep rendering an old graphic where the timeline is
  // empty — a phantom that vanishes when any track is muted. Both timecodes are required: the
  // one-argument form throws "Not Enough Parameters".
  const opts = a1 ? JSON.parse(a1) : {};
  await guardIfJob(opts);
  const r = await es(`
(function(){
var seq = app.project.activeSequence;
if (!seq) return "ERROR: no active sequence";
var frameDur = seq.getSettings().videoFrameRate.seconds;${TC_FN}
var end = Number(seq.end) / 254016000000;
if (!(end > 0)) end = 0;
// seq.end can read 0 on a sequence Premiere has not re-evaluated; the tracks always know.
// EVERY clip, not each track's last one: the scripted move this command exists to clean up after is
// exactly what leaves a track's items out of time order (lab-notes § never razor-and-move), so the
// highest index is not reliably the latest clip — and a short end leaves the phantom uncleared.
var lists = [seq.videoTracks, seq.audioTracks];
for (var l = 0; l < lists.length; l++)
  for (var t = 0; t < lists[l].numTracks; t++) {
    var tr = lists[l][t];
    for (var i = 0; i < tr.clips.numItems; i++)
      if (tr.clips[i].end.seconds > end) end = tr.clips[i].end.seconds;
  }
if (!(end > 0)) return "ERROR: the active sequence is empty";
app.enableQE();
var qs = qe.project.getActiveSequence();
if (!qs) return "ERROR: no QE sequence";
var tc = tcOfFrame(previewEndFrame(end, frameDur), frameDur);
try { qs.deletePreviewFiles("00:00:00:00", tc); }
catch (e) { return "ERROR: deletePreviewFiles(00:00:00:00, " + tc + ") threw: " + e.message; }
return "cleared preview files on " + seq.name + ": 00:00:00:00 - " + tc + " (" + end.toFixed(2) + "s)";
})()
`);
  const out = typeof r === "string" ? r : JSON.stringify(r);
  if (out.startsWith("ERROR")) { console.error(out); process.exit(1); }
  console.log(out);
} else if (cmd === "es") {
  // THE OUTPUT CONTRACT (lanes/premiere/lab-notes.md): one line out, ERROR: in, a 65535-char return
  // cap that names itself, and a timeout the caller passes. Every hand script and lanes/premiere/pes.py
  // comes through here, so the six hand-rolled parsers that each guessed a different contract stop
  // being necessary.
  const rest = process.argv.slice(3);
  let timeout, job, sequence, noGuard = false, script = "";
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === "--timeout") timeout = Number(rest[++i]);
    else if (rest[i] === "--job") job = rest[++i];
    else if (rest[i] === "--sequence") sequence = rest[++i];
    else if (rest[i] === "--no-guard") noGuard = true;
    else if (rest[i] === "--file") script = readFileSync(rest[++i], "utf-8");
    else script += rest[i];
  }
  script = script.trim();
  if (!script) throw new Error("es needs a script argument, or --file <path>");
  if (timeout !== undefined && !(timeout > 0)) throw new Error(`es: bad --timeout ${timeout} (milliseconds)`);
  // The active-project guard, same as every other command here: an ad-hoc script writes to whatever
  // project the operator last clicked, which is how 37 graphics landed on the wrong open timeline
  // (lanes/premiere/lab-notes.md § The active project is checked before every write). One of the two
  // flags is required so the guard is never skipped by forgetting it exists.
  if (job && noGuard) { console.error("es: pass --job <dir> OR --no-guard, not both"); process.exit(2); }
  if (!job && !noGuard) {
    console.error("es: pass --job <projects/<job>> so the active project is checked before this runs, "
      + "or --no-guard for a read you are sure of (lanes/premiere/job_guard.py is the same check from Python).");
    process.exit(2);
  }
  if (sequence !== undefined && !job) { console.error("es: --sequence names the sequence the --job guard must find active; pass it with --job"); process.exit(2); }
  // An expression (the IIFE every caller writes, or a bare '1+1') has to be RETURNED, or the wrap below
  // throws its value away; a statement body brings its own return, and one without is refused HERE,
  // before anything is sent (bridge-lib.mjs esBody).
  const w = esBody(script);
  if (w.error) { console.error(`es: ${w.error}`); process.exit(2); }
  if (job) await requireJobProject(job, job, sequence);
  const r = await bridge.executeScript(
    `try {\n${w.body}\n} catch (e) { return "ERROR: " + (e && e.message ? e.message : String(e)) + (e && e.line ? " @ line " + e.line : ""); }`,
    timeout, true);
  if (r && r.success === false) { console.error(`bridge error: ${bridgeError(r.error)}`); process.exit(1); }
  // No value at all is an ERROR line, never the text "undefined" (nor a crash on JSON.stringify(undefined)).
  const empty = esEmptyResult(r);
  if (empty) { console.log(`ERROR: ${empty}`); process.exit(1); }
  const out = typeof r === "string" ? r : JSON.stringify(r);
  // The CEP evalScript return is capped: past it the caller gets JSON that dies as "Unterminated
  // string ... char 65534" three calls into a task. Name the cap instead, and page the read.
  if (out.length >= 65535) {
    console.error(`result hit the CEP evalScript return cap (${out.length} chars) — page the read (lanes/premiere/pes.py \`paged\`, or fetch one track at a time)`);
    process.exit(1);
  }
  console.log(out);
  if (out.startsWith("ERROR:")) process.exit(1);
} else {
  const t = tools.getAvailableTools().find(x => x.name === cmd);
  if (!t) { console.error(`Unknown tool: ${cmd}`); process.exit(1); }
  const r = await tools.executeTool(cmd, a1 ? JSON.parse(a1) : {});
  console.log(JSON.stringify(r, null, 2));
  // The vendor handler RETURNS {success:false,…} instead of throwing, so an unchecked exit(0) is how a
  // run says "saved" over a project that only exists in Premiere's memory (lab-notes.md: the SAVED
  // .prproj is the only rollback — ExtendScript mutations never enter the undo stack).
  if (r && r.success === false) process.exit(2);
}
process.exit(0);
