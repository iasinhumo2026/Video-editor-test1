// The pure logic of premiere-bridge.mjs: no bridge, no Premiere, so workflows/test_premiere_bridge.py
// holds every decision here offline. The functions whose SOURCE is injected into ExtendScript (TC_FN)
// are written in ES3 on purpose — no let/const, arrows, templates or default params — because Premiere
// runs exactly this text.
import { existsSync, readFileSync } from "node:fs";
import { basename } from "node:path";

// This file's own commands, listed ahead of the engine's tools by --list and described by --desc.
export const LOCAL = ["replay", "seq-rate", "diff-edl", "frame", "zoom", "grade-layer", "lay", "labels", "clear-previews", "es"];

export const TPS = 254016000000;   // Premiere ticks per second

// --desc for a LOCAL command: its block in premiere-bridge.mjs's own header comment, the one source of
// the usage text, so the two can never drift. A block is the `//   node lanes/premiere/premiere-bridge.mjs
// <cmd>` line plus every deeper-indented `//     ` line under it; the header ends at the first code line.
export function localUsage(source, cmd) {
  const head = /^\/\/ {3}node lanes\/premiere\/premiere-bridge\.mjs (\S+)/;
  let out = null;
  for (const l of source.split(/\r?\n/)) {
    if (!l.startsWith("//")) break;
    const m = head.exec(l);
    if (m) { if (out) break; if (m[1] === cmd) out = [l.slice(5)]; continue; }
    if (out) { if (/^\/\/ {5}/.test(l)) out.push(l.slice(5)); else break; }
  }
  return out ? out.join("\n") : null;
}

// `es`: what to send for a hand script. A single EXPRESSION (`1+1`, `app.project.path`, the IIFE every
// lane script writes) is RETURNED; a statement body that has its own `return` goes as written; anything
// else would come back as nothing, and is refused before it is sent (2026-09-21 and 09-23: a bare
// statement came back as `{}`/`undefined`, and ten calls went to hunting a Premiere modal that was not
// there). The expression test is node's own parser; the newline before the closing paren keeps a
// trailing line comment from swallowing it. The one expression may be followed by its `;` and then only
// semicolons, blanks and comments ('(function(){ ... })(); // done', a .jsx whose `})();` has a comment
// line under it): that head is the expression, and it is the head, exactly as written, that must close
// `return (<head>);` with no newline added, so a `;` inside a comment, string or regex is never taken for
// the end of it (a head that ends inside a line comment swallows the paren and fails).
export function esBody(script) {
  const s = String(script).trim();
  if (parses(`return (${s}\n);`)) return { body: `return (${s}\n);` };
  for (let i = s.lastIndexOf(";"); i > 0; i = s.lastIndexOf(";", i - 1)) {
    if (!inert(s.slice(i + 1))) continue;
    const head = s.slice(0, i);
    if (parses(`return (${head});`)) return { body: `return (${head}\n);` };
  }
  if (/\breturn\b/.test(script)) return { body: s };
  return { error: "the script has no return and is not a single expression, so it would come back empty: "
    + "end it with 'return <value>;' (an IIFE must return its result too)" };
}
function parses(code) {
  try { new Function(code); return true; } catch { return false; }
}
// Nothing but semicolons, blanks and comments, read from a point that is known to be code.
function inert(t) {
  for (let i = 0; i < t.length;) {
    if (t[i] === ";" || /\s/.test(t[i])) { i++; continue; }
    if (t.startsWith("//", i)) { const n = t.indexOf("\n", i); if (n < 0) return true; i = n + 1; continue; }
    if (t.startsWith("/*", i)) { const n = t.indexOf("*/", i + 2); if (n < 0) return false; i = n + 2; continue; }
    return false;
  }
  return true;
}

// A result that is no value at all: CEP hands `undefined` back as the text "undefined" (or nothing),
// and a response with no result key comes back as the panel's own envelope. Each is an ERROR, never a
// line of output a caller parses as data. `null` is a value (the script returned it) and passes.
export function esEmptyResult(r) {
  const empty = r === undefined || (typeof r === "string" && (r.trim() === "" || r.trim() === "undefined"))
    || (r !== null && typeof r === "object" && r.success === true && !("result" in r) && "timestamp" in r);
  return empty ? "the script returned no value (undefined or an empty string): end it with 'return <value>;'" : null;
}

// THE FRAME AT A TIME is the frame Premiere SHOWS there: the floor, never the nearest. Rounding sent a
// grab a hair before a cut to the first frame AFTER it (2026-09-22); a caller's +1e-4 nudge onto a grid
// time is unchanged under the floor.
export function frameAt(t, frameDur) {
  return Math.floor((t + 1e-6) / frameDur);
}

// QE takes a TIMECODE STRING and nothing else: numeric seconds throw, and a numeric string is read as
// FRAMES. The count is NOMINAL (round(1/frameDur)), so 23.976 counts to 24 — deriving it a second time
// per call site is how a fractional rate drifts, so every QE caller uses this one.
export function tcOfFrame(f, frameDur) {
  var nominal = Math.round(1 / frameDur);
  var ff = f % nominal, s = (f - ff) / nominal;
  var ss = s % 60, mm = ((s - ss) / 60) % 60, hh = Math.floor(s / 3600);
  function p(n){ return (n < 10 ? "0" : "") + n; }
  return p(hh) + ":" + p(mm) + ":" + p(ss) + ":" + p(ff);
}

// clear-previews' END: it must COVER the last clip, so it takes the ceiling of the sequence end plus one
// frame of margin — the display floor above would stop short of a clip that ends between two frames.
export function previewEndFrame(end, frameDur) {
  return Math.ceil(end / frameDur - 1e-6) + 1;
}

export const TC_FN = "\n" + [frameAt, tcOfFrame, previewEndFrame].map(String).join("\n");

// THE SOURCE GRID a clip's in/out is floored to: its footage interpretation, an NTSC float snapped back to its rational
// only when it is float NOISE (the interpretation is a float32, 29.9700298...). A variable-rate phone clip is
// interpreted at its AVERAGE (29.9766 for an iPhone take at r 30000/1001), and that IS the grid Premiere floors its
// in/out to: snapped to 29.97 (the old 0.01 window), every in-point landed one frame early (2026-09-27). `replay` and
// `lay` both inject this one function: `lay` kept the 0.01 window after `replay` dropped it (audit, 2026-10-13).
export function snapRate(fps) {
  if (Math.abs(fps - 24000 / 1001) < 1e-4) return 24000 / 1001;
  if (Math.abs(fps - 30000 / 1001) < 1e-4) return 30000 / 1001;
  if (Math.abs(fps - 60000 / 1001) < 1e-4) return 60000 / 1001;
  return fps;
}

export const RATE_FN = "\n" + String(snapRate);

// A NAME OR PATH WRITTEN INTO A SCRIPT. The MCP Bridge panel refuses, as a bare "Script validation failed", any
// command whose TEXT matches eval( / new Function( / require( / __dirname / __filename / process. / child_process,
// string literals included (vendor cep-plugin/bridge-cep.js validateScript, unchanged upstream through v1.2.9). So a
// clip named "Editing Process.MP4" or "Retrieval (2).mp4" failed every command that named it, cause unsaid (audit,
// 2026-10-13). esLit is JSON.stringify with every '.', '(' and '_' inside a string written as a \u escape, which
// ExtendScript reads back as the same character and the filter never matches; numbers are untouched.
// lanes/premiere/pes.py es_lit is the same for the Python lane scripts.
export function esLit(v) {
  const j = JSON.stringify(v);
  return j === undefined ? "undefined" : j.replace(/"(?:[^"\\]|\\.)*"/g,
    (s) => s.replace(/[._(]/g, (c) => "\\u00" + c.charCodeAt(0).toString(16)));
}

// The panel's refusal, with its cause named.
export function bridgeError(err) {
  return String(err) === "Script validation failed"
    ? `${err} (the MCP Bridge panel refuses a script whose text holds eval( / new Function( / require( / __dirname / `
      + "__filename / process. / child_process, a media name or path included: write each one through esLit, "
      + "or pes.es_lit from Python)"
    : String(err);
}

// diff-edl's SOURCE OUT is derived from the clip's own length, in ticks: `outPoint` reads STALE after a
// `clip.end` write and keeps reading stale in every later session (2026-09-21: a +21-frame extend read
// 0.876 s short, was logged as a hand trim, and a wrong EDL mis-synced six graphics). `c` carries the
// tick counts off the readback (`inT`, `startT`, `endT`, `outT`) and the clip `speed` (1 when unread).
// `stale` says the readback disagrees with the derived out by more than a frame: an info line, never a move.
// A speed-changed clip reads `inPoint` and `outPoint` in its own SPED timebase, i.e. source time / speed (a 500 %
// clip cut from source 6865.40 read inPoint 1373.08 and outPoint 1389.72, your-job 2026-09-28), so
// both are multiplied back by the speed; at speed 1 nothing changes.
export function srcOutOf(c, frameSec) {
  const speed = c.speed > 0 ? c.speed : 1;
  const srcOut = Math.round((c.inT + (c.endT - c.startT)) * speed) / TPS;
  const readOut = Math.round(c.outT * speed) / TPS;
  return { srcOut, readOut, stale: Math.abs(readOut - srcOut) > frameSec };
}

// THE GUARD'S READBACK, identical to lanes/premiere/job_guard.py's GUARD_ES so the two can never read
// different things: the active project, every open one, the active sequence, and the project's own.
// `activeInProject` is proved by the project FILE as well as the sequenceID: a Save-As copy keeps every
// sequenceID (live, 2026-09-23), so with the copy as `app.project` and the original's timeline in front
// the ID alone passed, and a guarded `frame`/`es --job` acted on the other project. A sequence's own
// `projectItem.treePath` starts with its OWNING project's file name (`\<file>.prproj\[bins\]<seq>`,
// proven live on both copies), so it must start with app.project's; a treePath that throws or is missing
// proves nothing and fails. `ambiguous` lists every OTHER open project with the SAME file name that holds
// the active sequenceID (a Finder copy open from another folder), which no treePath can tell apart, and an
// open project whose sequences cannot be read counts as one. No backslash in this text: B is char 92, so
// the JS template and job_guard.py's raw string are the same characters.
export const GUARD_ES = `(function(){ var o = {path: app.project ? app.project.path : "", open: [], active: null, activeInProject: false, sequences: [], ambiguous: []};
  var B = String.fromCharCode(92);
  function fileOf(x) { x = String(x); return x.substring(Math.max(x.lastIndexOf("/"), x.lastIndexOf(B)) + 1); }
  try { for (var i = 0; i < app.projects.numProjects; i++) o.open.push(app.projects[i].path); } catch (e) {}
  if (app.project) { var s = app.project.activeSequence, file = fileOf(o.path), own = false;
    if (s) { o.active = {name: s.name, sequenceID: s.sequenceID};
      try { own = String(s.projectItem.treePath).indexOf(B + file + B) === 0; } catch (e) {} }
    for (var j = 0; j < app.project.sequences.numSequences; j++) { var q = app.project.sequences[j];
      o.sequences.push(q.name);
      if (s && own && q.sequenceID === s.sequenceID) o.activeInProject = true; }
    if (o.activeInProject) { try { for (var k = 0; k < app.projects.numProjects; k++) { var p = app.projects[k];
        if (p.path === o.path || fileOf(p.path) !== file) continue;
        for (var m = 0; m < p.sequences.numSequences; m++) if (p.sequences[m].sequenceID === s.sequenceID) { o.ambiguous.push(p.path); break; } } }
      catch (e) { o.ambiguous.push("an open project whose sequences could not be read"); } } }
  return JSON.stringify(o); })()`;

// The sequence a caller asked for: its own (`"sequence"` in the opts, `es --sequence`) beats the env's.
export function requestedSequence(explicit, env) {
  return explicit || (env && env.VE_SEQUENCE) || null;
}

// THE SEQUENCE RULE, word for word lanes/premiere/job_guard.py's (2026-09-22: `app.project` was the
// job's while `activeSequence` was another open project's timeline; 09-23: the active sequence switched
// from the job's AD cut to its organic between two grabs, and `frame` grabbed the organic). With S the
// active sequence: (a) no S refuses; (b) S outside this project's sequences refuses, by sequenceID AND
// by project file (GUARD_ES's activeInProject), and so does S also held by another open copy of the same
// file name (`ambiguous`); (c) a requested name must be S's; (d) otherwise a project holding a sequence
// named after the job refuses any other S, naming VE_SEQUENCE as the deliberate way to target it;
// (e) otherwise it passes. Returns the refusal text, or null to proceed.
export function sequenceRule({ job, path, open, activeName, activeInProject, ambiguous, requested, projectSequenceNames }) {
  const names = projectSequenceNames || [];
  if (activeName === null || activeName === undefined)
    return `there is no active sequence in ${path}: nothing touched.\n  Open the job's timeline and re-run.`;
  if (!activeInProject)
    return `the active sequence ${activeName} belongs to another open project, not ${path}: nothing touched.\n`
      + `  open projects: ${(open || []).join(", ") || "none"}\n`
      + "  Click this job's timeline (or close the other project) and re-run.";
  if (ambiguous && ambiguous.length)
    return `the active sequence ${activeName} is also in ${ambiguous.join(", ")}, another open project with the same file name,`
      + " so which copy it belongs to cannot be proven: nothing touched.\n"
      + "  Close the other copy and re-run.";
  if (requested && activeName !== requested)
    return `the active sequence is ${activeName}, not the requested ${requested}: nothing touched.\n`
      + `  sequences in this project: ${names.join(", ") || "none"}\n`
      + "  Open the requested sequence (or change VE_SEQUENCE) and re-run.";
  if (!requested && names.includes(job) && activeName !== job)
    return `the active sequence is ${activeName}, not the job's own sequence ${job}: nothing touched.\n`
      + `  To target ${activeName} deliberately, set VE_SEQUENCE='${activeName}' and re-run.`;
  return null;
}

// The whole guard on one GUARD_ES readback `g`: the active PROJECT must be the job's (a .prproj under
// the job folder, or one named after it), then the sequence rule. Refuses, never picks.
export function guardVerdict(g, jobDir, requested) {
  const job = basename(jobDir);
  // Windows: Premiere reports C:\...\x.prproj with backslashes (and any case), so a bare startsWith(jobDir + "/") never
  // matched and only the "file named after the job" fallback passed: <job>.graded.prproj, the grade recipe's working
  // copy, was refused (2026-09-27). Compare on forward slashes, case-folded on win32.
  const norm = (s) => { const n = String(s).replace(/\\/g, "/").replace(/\/+$/, ""); return process.platform === "win32" ? n.toLowerCase() : n; };
  if (!g.path || !(norm(g.path).startsWith(norm(jobDir) + "/") || basename(g.path.replace(/\\/g, "/"), ".prproj") === job))
    return `the ACTIVE Premiere project is ${g.path || "none"}, not this job's (${job}/premiere/*.prproj): nothing touched.\n`
      + `  open projects: ${(g.open || []).join(", ") || "none"}\n  Make the job's project active (click its timeline, or close the other) and re-run.`;
  return sequenceRule({ job, path: g.path, open: g.open, activeName: g.active ? g.active.name : null,
    activeInProject: !!g.activeInProject, ambiguous: g.ambiguous, requested, projectSequenceNames: g.sequences || [] });
}

// replay lays every segment from its RAW clip. A segment that carries `media` was laid from a substitute
// file (a lip-sync clip on the raw clock with re-recorded audio), so replaying it would silently put the
// old raw line back. Refuse the whole replay, naming each such segment.
export function mediaRefusal(segs) {
  const hits = (segs || []).map((s, i) => [i, s]).filter(([, s]) => s && s.media);
  if (!hits.length) return null;
  return `replay: refused, nothing laid: ${hits.length} segment(s) carry "media", so the raw clip this replay would lay is NOT what is on the cut:\n`
    + hits.map(([i, s]) => `  #${i} ${Number(s.start).toFixed(3)}-${Number(s.end).toFixed(3)} (${s.clip || "the CLI clip"}) was laid from ${s.media}`).join("\n")
    + "\n  Replay an EDL without those segments, then lay each one with `lay` from the media's own project item"
    + " (import the media first; in/out on the media's clock).";
}

// A boundary off the sequence's frame grid (L11, 2026-09-27). The replay lays every in and out on the NEAREST sequence
// frame, so a boundary a hand EDL edit left between frames is laid up to half a frame away, and each such segment's laid
// length differs from its EDL length: the transcript, the plan and every graphic timed from the EDL then sit that far
// off the real cut (a full-screen planned to the EDL's end landed a frame short of it on the Windows test job).
// splice.sh writes every boundary on the source grid, so on a same-rate job only a hand edit after it leaves one off.
// The warning (printed before anything is laid), or null.
export function offGridWarning(segs, ticks, tolSec = 0.001) {
  const f = Number(ticks) / TPS;
  if (!(f > 0)) return null;
  const off = [];
  let edl = 0, laid = 0, drift = 0;
  (segs || []).forEach((s, i) => {
    for (const k of ["start", "end"]) {
      const t = Number(s[k]), q = Math.round(t / f) * f;
      if (Math.abs(t - q) > tolSec) off.push(`  #${i} ${k} ${t.toFixed(5)} is laid at ${q.toFixed(5)} (${((q - t) / f).toFixed(2)} frame)`);
    }
    edl += Number(s.end) - Number(s.start);
    laid += (Math.round(Number(s.end) / f) - Math.round(Number(s.start) / f)) * f;
    drift = Math.max(drift, Math.abs(edl - laid) / f);
  });
  if (!off.length) return null;
  return `⚠ replay: ${off.length} EDL boundar${off.length === 1 ? "y is" : "ies are"} off the sequence's frame grid, each laid on `
    + `the nearest frame, so the cut on the timeline runs up to ${drift.toFixed(2)} frame(s) from cuts.json:\n${off.join("\n")}\n`
    + "  Put those boundaries on the grid in cuts.json (the values above; on a mixed-rate job cut-audit.py --grid <sequence "
    + "rate> picks them) and re-export the transcript before a plan is timed from it.";
}

// A sequence's frame duration in ticks for each standard rate. Premiere builds a sequence from a VARIABLE-rate phone
// clip at the clip's AVERAGE rate (an iPhone take at r 30000/1001 gave 29.9766 fps, one at r 30/1 gave 30.0013, on
// macOS AND Windows, 2026-09-27), while splice, the plan and the renders run on the NOMINAL grid, so every graphic
// landed a frame off. `seq-rate` puts the empty sequence on the nominal rate; `replay` refuses anything off this list.
export const STD_RATES = { "24000/1001": 10594584000, "24": 10584000000, "25": 10160640000, "30000/1001": 8475667200,
  "30": 8467200000, "48000/1001": 5297292000, "48": 5292000000, "50": 5080320000, "60000/1001": 4237833600,
  "60": 4233600000, "100": 2540160000, "120000/1001": 2118916800, "120": 2116800000 };

export function rateTicks(fps) {
  const k = String(fps).trim().replace(/\/1$/, "");
  return STD_RATES[k] || null;
}

// rawFps: the EDL's raw's ffprobe r_frame_rate when the replay could read one (every clip the same). The hint names
// THAT rate, never the standard rate nearest the average: an iPhone take at r 30000/1001 averaged 29.9887 on the
// Windows re-test (2026-09-27), nearer 30, so the nearest-rate hint put the sequence on the wrong grid.
export function seqRateRefusal(ticks, rawFps) {
  const t = Number(ticks);
  if (!(t > 0)) return "no active sequence (or its frame rate did not read back)";
  if (Object.values(STD_RATES).some(v => Math.abs(v - t) <= 1)) return null;
  const raw = rawFps && rateTicks(rawFps) ? String(rawFps).trim().replace(/\/1$/, "") : null;
  return `the active sequence runs at ${(TPS / t).toFixed(4)} fps (${t} ticks a frame), no standard rate: Premiere built it `
    + `at a variable-rate phone clip's AVERAGE rate, and a plan, a splice and every render run on the nominal grid. Put the `
    + `EMPTY sequence on the raw's r_frame_rate first: node lanes/premiere/premiere-bridge.mjs seq-rate `
    + `'{"job":"projects/<job>","fps":"${raw || "<r_frame_rate>"}"}' `
    + (raw ? "(the raw's own r_frame_rate, read by ffprobe)" : "(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate on the raw names it)")
    + ", then re-run the replay.";
}

// A TORN HEARTBEAT READ IS NOT AN ABSENT PANEL (Windows, Premiere 26.5.1, 2026-10-13). The CEP panel rewrites
// bridge-heartbeat.json every 250 ms with a plain writeFileSync, which truncates before it writes, so a read can land on
// an EMPTY file (2 of 962 back-to-back reads on an idle Premiere). The engine's readHeartbeat answers null for that, and
// its response wait turns one null into "MCP Bridge is not running" for any call still running after 1.5 s: 4 of 12
// five-second `es` calls failed so while the panel was alive, a grade-layer lost its save, and each failed call left
// its response orphaned in the bridge dir while Premiere finished the work. So a null is asked again, `tries` times
// `gapMs` apart, before it stands: a torn read is gone well inside that, a dead or stale panel stays null.
export async function steadyBeat(read, tries = 5, gapMs = 20) {
  for (let i = 0; i < tries; i++) {
    const beat = await read();
    if (beat) return beat;
    if (i < tries - 1) await new Promise(r => setTimeout(r, gapMs));
  }
  return null;
}

// THE CAMERA A/V SLIP: whole sequence frames V1 is laid LATER than A1 for the EDL in `transcriptDir`
// (transcript/av-slip.json, written by workflows/lip-sync.py --slip-out at intake; rough-cut § Lip sync at intake).
// Missing file = 0. A file that does not parse, or a non-integer, throws: a silently ignored slip is lost lip sync.
export function avSlipFrames(transcriptDir, read = (p) => readFileSync(p, "utf-8"), exists = existsSync) {
  const p = `${transcriptDir}/av-slip.json`;
  if (!exists(p)) return 0;
  const n = JSON.parse(read(p)).v1_frames;
  if (n === undefined || n === null) return 0;
  if (!Number.isInteger(n)) throw new Error(`${p}: v1_frames must be a whole number of frames, got ${JSON.stringify(n)}`);
  return n;
}
