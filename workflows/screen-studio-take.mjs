#!/usr/bin/env node
// screen-studio-take.mjs — record a SCRIPTED screen-recording take through Screen Studio (macOS) and export it
// as a finished full-frame B-roll clip: Screen Studio's own wallpaper, rounded window, smooth cursor and zooms.
// The opt-in capture route for a machine that owns Screen Studio (graphics-build § Stage 2); the default route
// stays screen-record.sh / page-record.mjs.
//
//   node workflows/screen-studio-take.mjs <take.json> <out.mp4> --fps <the job's rate> [--height 2160]
//        [--preflight projects/<job>/pii.json] [--force] [--port 9222]
//   node workflows/screen-studio-take.mjs --reexport <old.provenance.json> <zooms.json> <out.mp4> --fps <rate>
//   node workflows/screen-studio-take.mjs --unmask <old.provenance.json> <out.mp4> --fps <rate>     # the same take, every blur mask removed
//        re-exports an EXISTING take's project with new zooms (and "padding") only: no re-recording. zooms.json is
//        {"padding": 0.4, "rect": [0, 30, 1920, 1050], "zooms": [{"start": 0, "end": "end", "rect": [...], "fill": 0.65}]}
//        with start/end in seconds of the CLIP ("end" = its last frame, a negative start opens zoomed); "rect" is the
//        recorded screen rect when the old provenance does not carry it.
//   node workflows/screen-studio-take.mjs --self-test
//
// take.json (relative paths and setup/teardown commands run from the take file's folder):
//   {
//     "window":   {"display": 1, "crop": [0, 30, 1920, 1050]}       or a DISPLAY (1 = main), cropped to a rect: the
//                 real composited screen, so a translucent window never shows the wallpaper through it, and a take
//                 can span several windows (Finder dragging into Chrome). Everything inside the crop is recorded.
//                 "front": "Claude" activates that app once the recording runs (the picker click leaves Screen Studio
//                 in front, and keys would go there).
//              |  {"app": "Finder", "size": [1280, 720]}            the window to record: app + its size in points;
//                 "picker": "Adobe Premiere" when Screen Studio's picker labels the app differently from its process
//              |  {"url": "https://…", "size": [1280, 720], "position": [320, 180], "settle": 3}
//                                                                    a page: opened in a clean chromeless Chrome window;
//                 the take waits "settle" seconds, then until the page has loaded and painted (30 s at most)
//                 A window take is refused when a dialog of its own app sits over it (Chrome's "Leave site?": setup
//                 navigated a page with unsaved changes and the old page stayed up).
//     "setup":    ["osascript …", …],      shell commands run before the take (stage the window, reset files)
//     "steps":    ["park:1300,760", "wait:0.8", "mark:in", "move:606,352,1.3", "dclick", "run:<shell>", "mark:out"],
//                 workflows/glide.swift steps, plus run:<shell> (runs between cursor segments, e.g. an invisible
//                 Finder view change); the clip is trimmed to the first step .. the last step
//     "zooms":    [{"from": "in", "to": "out", ...}], zooms between marks ("__start"/"__end" are the trim edges).
//                 Where it lands: "x"/"y" (0-1 of the recorded rect), or "focus": [x, y] (screen points), or
//                 "rect": [x, y, w, h] (screen points; its centre). How deep: "level" (Screen Studio's scale; it is
//                 relative to the whole frame, wallpaper margin included), or "fill": 0.65 with a "rect" = the level at
//                 which that rect spans 65 % of the frame width (k = 1 + 2.1 x padding, measured 2026-10-03), capped
//                 at 8. "follow": true = Screen Studio's auto zoom, which follows the cursor; "instant": true = no
//                 zoom-in animation (with "from": "__start" and "lead_in": 0.5 the take OPENS zoomed; when another
//                 zoom follows, the tool turns that opening zoom into an eased one 2 s before the clip, because
//                 Screen Studio snaps into the NEXT zoom after an instant one, measured 2026-10-04). With no aim
//                 at all it aims at the first click inside it, else the cursor at its "to" mark. Screen Studio's own
//                 click auto-zooms are dropped unless "auto_zooms": true. The camera clamps near the recording's
//                 edges: a bottom-edge target (a chat composer) centres only as far as about 0.62 of the frame
//                 height, and needs "padding": 0.4 to get there.
//     "prelude":  ["key:cmd+equal", …],    steps run once the recording runs but BEFORE the trim (a page zoom, a focus)
//     "masks":    [{"from": "menu", "to": "picked", "rect": [645, 700, 195, 235]}],   a blur over a screen rect (points)
//                 between two marks: something that must not ship (a recent-projects list, a path) is blurred in
//                 Screen Studio itself, so it follows every zoom
//     "lead": 0, "tail": 0,                seconds kept before the first step / after the last
//     "padding": 0.1,                      optional: the wallpaper margin (the default preset's otherwise)
//     "teardown": ["…"]                    shell commands run after the export, also on failure
//   }
//
// How (Screen Studio 4.0.1, 2026-10-02): Screen Studio runs with --remote-debugging-port; the take starts through
// its OFFICIAL deeplinks (screen-studio://record-window, then the picker's own Start recording button for the
// matching window, clicked in-page) and stops with screen-studio://finish-recording. The cursor is glide.swift
// (CGEvents, logged by Screen Studio like a hand on the mouse, so its smoothing and spring zooms apply). Marks are
// wall-clock and land on the recording's clock through recording/metadata.json's session unixStartMs (never the
// event logs' processTimeMs, which runs seconds ahead of the video). Edits go through the app's own collections (scene.slices / scene.zooms add/update, config
// via updateConfigProp: the camera hidden, mic + system audio muted, output 16:9), and the export runs with
// target "clipboard": Screen Studio renders to $TMPDIR/Screen Studio/Clipboard Exports with NO save panel
// (the file target opens an out-of-process panel that only takes keystrokes). The clipboard text is restored.
// The look (wallpaper, corner radius, shadow) is the app's DEFAULT PRESET, set once in Screen Studio.
//
// 4.0.4-4926 (2026-10-14), what changed from 4.0.1 and how the driver meets it, both builds on one path:
//  · window.$$focused is no longer the editor: it alternates between the editor and its bare project, so the take's
//    editor is found by PROJECT PATH in its own window's React tree (findEditor), with $$focused only as the 4.0.1
//    fallback, and every edit and the export go through that pinned editor.
//  · a window covered at the click never starts (the recorder widget sits at "Working...", no recorder spawns), and
//    a deeplink that ACTIVATES Screen Studio raises its newest editor over the take's window: the deeplinks open
//    with `open -g`, and the take's window is fronted and checked uncovered (coverer) before the click.
//  · the quick-export widget ignores Escape and its "Edit" opens an editor that stays open (orphan editors, each a
//    window the next take could land under): it is closed through its own onClose.
// Proven on 4.0.4 by a url take of whop.com/network on the second display under five open editors, recorded,
// zoomed and exported end to end, plus a --reexport of it.
//
// Exit 0 = exported and verified. 2 = usage / setup. 3 = the recording failed. 4 = the preflight refused the
// take (forbidden text on screen). 5 = the export failed.
import { execFileSync, execSync, spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync, mkdirSync, copyFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { homedir, tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP = '/Applications/Screen Studio.app';
const KNOWN_GOOD = ['4.0.1-4897', '4.0.4-4926'];  // builds this driver was proven on; another build warns, then tries
const sleep = ms => new Promise(r => setTimeout(r, ms));
const log = s => console.error(`[screen-studio-take] ${s}`);
class Stop extends Error { constructor(code, msg) { super(msg); this.code = code; } }
const die = (code, s) => { throw new Stop(code, s); };

// ---------- pure planning (covered by --self-test) ----------

export function splitSegments(steps, prelude = []) {
  const segs = [];
  for (const s of [...prelude, 'mark:__start', ...steps, 'mark:__end']) {
    if (s.startsWith('run:')) segs.push({ kind: 'run', cmd: s.slice(4) });
    else if (segs.length && segs.at(-1).kind === 'glide') segs.at(-1).args.push(s);
    else segs.push({ kind: 'glide', args: [s] });
  }
  return segs;
}

export function parseGlide(stdout) {
  const ev = [];
  for (const line of stdout.split('\n')) {
    const m = line.match(/^(mark (\S+)|click x(\d)|rclick|start|end)\b(?:.* at (-?\d+),(-?\d+))?.*unix=(\d+)/);
    if (!m) continue;
    const at = m[4] != null ? { x: +m[4], y: +m[5] } : undefined;
    ev.push(m[2] ? { type: 'mark', name: m[2], unix: +m[6], at } : { type: m[3] || m[1] === 'rclick' ? 'click' : m[1], unix: +m[6], at });
  }
  return ev;
}

// marks (wall clock) -> the recording's source clock; the slice and the zooms in source ms. A zoom with no x/y
// aims at the ACTION (2026-10-02: a zoom that lands where nothing happens is wrong): the first click
// inside it, else where the cursor is at its "to" mark, as a fraction of the recorded window `rect`.
// --fps as the rest of the repo writes it: a decimal or a fraction (24000/1001); anything else is 0 (usage).
export const parseFps = v => { const [n, d = 1] = String(v).split('/').map(Number); return n > 0 && d > 0 ? n / d : 0; };
export const zoomK = padding => 1 + 2.1 * padding;   // frame width / recorded width at zoom 1 (measured 2026-10-03)

// one zoom spec -> {level, x, y, type}: the aim and depth rules shared by takes and re-exports
export function zoomSpec(z, rect, padding, fallbackHit = null) {
  const f = (v, o, n) => Math.round(Math.max(0, Math.min(1, (v - o) / n)) * 1000) / 1000;
  let x = z.x, y = z.y, level = z.level;
  const box = z.rect, pt = z.focus ?? (box ? [box[0] + box[2] / 2, box[1] + box[3] / 2] : null);
  if (pt && rect) { x ??= f(pt[0], rect[0], rect[2]); y ??= f(pt[1], rect[1], rect[3]); }
  if ((x == null || y == null) && fallbackHit && rect) { x ??= f(fallbackHit.x, rect[0], rect[2]); y ??= f(fallbackHit.y, rect[1], rect[3]); }
  if (z.fill != null) {
    if (!box || !rect) throw new Error('a "fill" zoom needs a "rect" and the recorded rect');
    level = Math.min(8, Math.round(z.fill * zoomK(padding ?? 0.1) * rect[2] / box[2] * 100) / 100);
  }
  if (x == null || y == null) return null;
  return { level: level ?? 1.7, x, y, type: z.follow ? 'auto' : 'manual' };
}

// An "instant" zoom makes Screen Studio SNAP into the zoom after it too: the push played as a one-frame cut on six
// takes (2026-10-04, frame-differenced). An opening instant zoom that another follows becomes an eased one starting
// SETTLE_MS before the clip, so it has settled by frame 0 and the next zoom eases; a mid-take one is only warned.
const SETTLE_MS = 2000;
export function settleInstant(zooms, sliceStart, warn = m => console.error(`warning: ${m}`)) {
  return zooms.map((z, i) => {
    if (!z.instant || !zooms.some((o, j) => j !== i && o.start > z.start)) return z;
    if (z.start > sliceStart) { warn(`the instant zoom at ${Math.round(z.start)} ms makes the next zoom snap in as a cut`); return z; }
    const start = Math.max(0, sliceStart - SETTLE_MS);
    if (sliceStart - start < SETTLE_MS) warn(`the opening zoom has only ${Math.round(sliceStart - start)} ms to settle before the clip starts`);
    return { ...z, start, instant: false };
  });
}

export function plan(take, marks, recStartUnix, durationMs, clicks = [], positions = {}, rect = null) {
  const at = name => {
    if (!(name in marks)) throw new Error(`zoom mark "${name}" never ran (marks: ${Object.keys(marks).filter(k => !k.startsWith('__')).join(', ') || 'none'})`);
    return marks[name] - recStartUnix;
  };
  const aim = z => {
    const hit = clicks.find(c => c.unix >= marks[z.from] && c.unix <= marks[z.to] && c.at)?.at ?? positions[z.to];
    const a = zoomSpec(z, rect, take.padding, hit);
    if (!a) throw new Error(`zoom ${z.from}..${z.to} has no x/y and nothing to aim at (no click, no cursor position)`);
    return a;
  };
  const clamp = v => Math.max(0, Math.min(durationMs, v));
  const slice = { start: clamp(at('__start') - (take.lead ?? 0) * 1000), end: clamp(at('__end') + (take.tail ?? 0) * 1000) };
  const zooms = (take.zooms ?? []).map(z => {
    const start = Math.max(0, at(z.from) - (z.lead_in ?? 0) * 1000), end = clamp(at(z.to));
    if (end <= start) throw new Error(`zoom ${z.from}..${z.to} is empty`);
    const { level, x, y, type } = aim(z);
    return { start, end, level, x, y, instant: !!z.instant, ...(type === 'auto' ? { type } : {}) };
  });
  const settled = settleInstant(zooms, slice.start);
  const masks = (take.masks ?? []).map(k => {
    if (!rect) throw new Error('a mask needs the recorded window rect');
    const [x, y, w, h] = k.rect, f = v => Math.round(Math.max(0, Math.min(1, v)) * 10000) / 10000;
    return { start: clamp(at(k.from)), end: clamp(at(k.to)),
      bounds: { x: f((x - rect[0]) / rect[2]), y: f((y - rect[1]) / rect[3]), width: f(w / rect[2]), height: f(h / rect[3]) } };
  });
  return { slice, zooms: settled, masks };
}

// The editor a take drives, found by its PROJECT PATH. window.$$focused is only the last thing Screen Studio's focus
// manager focused: the editor itself on 4.0.1, but on 4.0.4 it alternates between the editor (exportManager,
// project) and the bare project (scenes, no exportManager, no .project), and a closing editor hands it to whatever
// is left (2026-10-14: an export read exportManager off the bare project, a take drove an orphan editor). Each editor
// window is its own page whose React tree carries its editor in a context provider; findEditor runs IN that page and
// pins the editor on the main page (the page's opener) as window.__veEditors.get(path). Serialized into the page, so
// self-contained.
export function findEditor(doc, opener, want) {
  if (!opener || !opener.$projects) return false;
  const els = doc.querySelectorAll('*');
  let key = null;
  for (const e of els) { key = Object.keys(e).find(k => k.startsWith('__reactFiber')); if (key) break; }
  if (!key) return false;
  const seen = new Set();
  for (const el of els) {
    for (let f = el[key]; f && !seen.has(f); f = f.return) {
      seen.add(f);
      for (const c of [f.memoizedProps, f.memoizedProps?.value]) {
        if (c && typeof c === 'object' && c.exportManager && c.project?.path === want) {
          (opener.__veEditors ??= new opener.Map()).set(want, c);
          return true;
        }
      }
    }
  }
  return false;
}
// 4.0.1's route, run in the main page: $$focused IS the editor when it carries an exportManager for this path
export function pinFocused(win, want) {
  const f = win.$$focused;
  if (!f || !f.exportManager || f.project?.path !== want) return false;
  (win.__veEditors ??= new win.Map()).set(want, f);
  return true;
}

// windows are the window server's on-screen list, front to back: {owner, pid, layer, name, rect: [x, y, w, h]}
const overlaps = (a, b) => a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
// the first normal window above the take's window that overlaps it. 4.0.4 never starts a window it cannot see: the
// recorder widget sits at "Working..." and no recorder process spawns (2026-10-14)
export function coverer(windows, target) {
  for (const w of windows) {
    if (w.pid === target.pid && w.rect.join() === target.join()) return null;
    if (w.layer === 0 && overlaps(w.rect, target)) return w;
  }
  return null;
}
// a modal dialog (layer 8) the take's own process holds over its window: Chrome's "Leave site?" when setup navigated
// a page with unsaved changes, which kept the old page on screen and the take recorded it (2026-10-14)
export function dialogOver(windows, target) {
  return windows.find(w => w.pid === target.pid && w.layer === 8 && overlaps(w.rect, target)) ?? null;
}

function selfTest() {
  const eq = (a, b, what) => { if (JSON.stringify(a) !== JSON.stringify(b)) { console.error(`FAIL ${what}\n  got  ${JSON.stringify(a)}\n  want ${JSON.stringify(b)}`); process.exitCode = 1; } };
  const segs = splitSegments(['park:1,2', 'mark:in', 'run:echo hi', 'dclick', 'run:a', 'run:b']);
  eq(segs.map(s => s.kind), ['glide', 'run', 'glide', 'run', 'run', 'glide'], 'segments split at run:');
  eq(segs[0].args, ['mark:__start', 'park:1,2', 'mark:in'], 'start mark leads');
  eq(segs.at(-1).args, ['mark:__end'], 'end mark trails');
  eq(splitSegments(['wait:1'], ['key:cmd+equal'])[0].args, ['key:cmd+equal', 'mark:__start', 'wait:1', 'mark:__end'], 'the prelude runs before the trim');
  eq(parseGlide('start unix=10\nmark in unix=20\nclick x2 at 5,5 unix=30\nend unix=40\nnoise'),
    [{ type: 'start', unix: 10 }, { type: 'mark', name: 'in', unix: 20 }, { type: 'click', unix: 30, at: { x: 5, y: 5 } }, { type: 'end', unix: 40 }], 'parse glide');
  eq(parseGlide('mark out at 12,-3 unix=50\nrclick at 7,8 unix=60'), [{ type: 'mark', name: 'out', unix: 50, at: { x: 12, y: -3 } }, { type: 'click', unix: 60, at: { x: 7, y: 8 } }], 'parse positions');
  const marks = { __start: 5000, in: 6000, out: 9000, __end: 12000 };
  eq(plan({ zooms: [{ from: 'in', to: 'out', level: 1.7, x: 0.2, y: 0.3 }], lead: 0.5, tail: 1 }, marks, 1000, 20000),
    { slice: { start: 3500, end: 12000 }, zooms: [{ start: 5000, end: 8000, level: 1.7, x: 0.2, y: 0.3, instant: false }], masks: [] }, 'plan maps wall clock to source');
  eq(plan({ tail: 5 }, marks, 1000, 12500).slice, { start: 4000, end: 12500 }, 'slice clamps to the recording');
  const rect = [320, 180, 1280, 720];
  eq(plan({ zooms: [{ from: 'in', to: 'out' }] }, marks, 1000, 20000, [{ unix: 7000, at: { x: 640, y: 360 } }], {}, rect).zooms[0],
    { start: 5000, end: 8000, level: 1.7, x: 0.25, y: 0.25, instant: false }, 'a zoom without x/y aims at the click inside it');
  eq(plan({ zooms: [{ from: 'in', to: 'out' }] }, marks, 1000, 20000, [{ unix: 9500, at: { x: 0, y: 0 } }], { out: { x: 1600, y: 900 } }, rect).zooms[0].x,
    1, 'no click inside it: the cursor at its "to" mark');
  let threw = ''; try { plan({ zooms: [{ from: 'nope', to: 'out' }] }, marks, 0, 1e6); } catch (e) { threw = e.message; }
  eq(threw.startsWith('zoom mark "nope" never ran'), true, 'a missing mark fails loudly');
  eq(plan({ masks: [{ from: 'in', to: 'out', rect: [640, 360, 128, 72] }] }, marks, 1000, 20000, [], {}, rect).masks,
    [{ start: 5000, end: 8000, bounds: { x: 0.25, y: 0.25, width: 0.1, height: 0.1 } }], 'a mask maps a screen rect into the recording');
  eq(zoomSpec({ rect: [560, 1010, 426, 28], fill: 0.65 }, [0, 30, 1920, 1050], 0.4), { level: 5.39, x: 0.403, y: 0.947, type: 'manual' },
    'a fill zoom: level from the rect width and the padding, aimed at the rect centre');
  eq(zoomSpec({ focus: [960, 555], level: 2, follow: true }, [0, 30, 1920, 1050], 0.1), { level: 2, x: 0.5, y: 0.5, type: 'auto' }, 'focus + follow');
  eq(plan({ zooms: [{ from: '__start', to: '__end', x: 0.5, y: 0.5, lead_in: 0.5, instant: true }] }, marks, 1000, 20000).zooms[0].start, 3500,
    'a lead_in opens the take already zoomed');
  eq([parseFps('24000/1001').toFixed(6), parseFps('23.976'), parseFps('2997/125'), parseFps('x'), parseFps('24/0')], ['23.976024', 23.976, 23.976, 0, 0],
    '--fps takes a decimal or a fraction');
  const warned = [], two = [{ start: 3500, end: 6000, instant: true }, { start: 6000, end: 9000, instant: false }];
  eq(settleInstant(two, 4000, m => warned.push(m)).map(z => [z.start, z.instant]), [[2000, false], [6000, false]],
    'an opening instant zoom that another follows eases in 2 s before the clip');
  eq(settleInstant(two.slice(0, 1), 4000), two.slice(0, 1), 'a lone instant zoom stays instant');
  settleInstant([{ start: 5000, end: 6000, instant: true }, two[1]], 4000, m => warned.push(m));
  settleInstant(two, 500, m => warned.push(m));
  eq(warned.length, 2, 'a mid-take instant zoom and a short settle are warned');
  // 4.0.4: the editor is found by path in its own window's React tree, never as whatever $$focused holds
  const path = '/p/take.screenstudio', ed = { exportManager: {}, project: { path } }, bare = { scenes: [], path };
  const fiber = (props, ret = null) => ({ memoizedProps: props, return: ret });
  const tree = fiber({ children: [] }, fiber({ value: bare }, fiber({ value: ed })));
  const doc = f => ({ querySelectorAll: () => [{ className: 'x' }, { __reactFiber$k: f }] });
  const opener = () => ({ $projects: new Set(), Map });
  let o = opener();
  eq([findEditor(doc(tree), o, path), o.__veEditors?.get(path) === ed], [true, true], 'the editor is pinned from its context provider by path');
  eq(findEditor(doc(fiber(ed)), opener(), path), true, 'an editor passed as props is found too');
  eq(findEditor(doc(tree), opener(), '/p/other.screenstudio'), false, 'another project\'s editor is never pinned');
  eq(findEditor(doc(tree), null, path), false, 'a page with no main-page opener pins nothing');
  o = { $$focused: bare, Map };
  eq(pinFocused(o, path), false, '4.0.4\'s $$focused on the bare project is never taken for the editor');
  eq(pinFocused({ $$focused: { exportManager: {}, project: { path: '/p/orphan.screenstudio' } }, Map }, path), false, 'an orphan editor in focus is refused');
  o = { $$focused: ed, Map };
  eq([pinFocused(o, path), o.__veEditors.get(path) === ed], [true, true], '4.0.1: $$focused is the editor');
  // the take's window must be the top normal window over its rect when the picker is clicked
  const tgt = Object.assign([2036, 190, 1280, 720], { pid: 7 });
  const win = (owner, pid, layer, rect, name = '') => ({ owner, pid, layer, rect, name });
  const editor = win('Screen Studio', 1, 0, [1920, 131, 1512, 949], 'Project - x'), mine = win('Google Chrome', 7, 0, [2036, 190, 1280, 720]);
  eq(coverer([win('Screen Studio', 1, 25, [1920, 98, 1512, 982]), editor, mine], tgt)?.name, 'Project - x', 'Screen Studio\'s editor over the take is found, its picker overlay is not');
  eq(coverer([mine, editor], tgt), null, 'the take on top is clear');
  eq(coverer([win('Claude', 2, 0, [0, 30, 2036, 1050]), mine], tgt), null, 'a window that only touches its edge does not cover it');
  const leave = win('Google Chrome', 7, 8, [2546, 314, 260, 218]);
  eq(dialogOver([leave, mine], tgt), leave, 'a "Leave site?" dialog over the take is found');
  eq(dialogOver([win('Google Chrome', 9, 8, [2546, 314, 260, 218]), mine], tgt), null, 'another process\'s dialog is not the take\'s');
  if (!process.exitCode) console.log('self-test: all checks passed');
}

// ---------- Chrome DevTools Protocol on Screen Studio ----------

let PORT = 9222;
async function pages() {
  const r = await fetch(`http://127.0.0.1:${PORT}/json`);
  return (await r.json()).filter(p => p.type === 'page');
}
async function cdp(page, method, params) {
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  // a native alert (an export failure) blocks Screen Studio's renderer, and an un-timed open waited forever
  await new Promise((res, rej) => { const t = setTimeout(() => rej(new Error('CDP connect timed out')), 8000); ws.onopen = () => { clearTimeout(t); res(); }; ws.onerror = rej; });
  try {
    return await new Promise((res, rej) => {
      const t = setTimeout(() => rej(new Error(`${method} timed out`)), 20000);
      ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id === 1) { clearTimeout(t); res(m.result); } };
      ws.onclose = () => { clearTimeout(t); res(null); };  // a window that closes on the click (the quick-export widget)
      ws.send(JSON.stringify({ id: 1, method, params }));
    });
  } finally { ws.close(); }
}
async function evalIn(page, expression) {
  const r = await cdp(page, 'Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r?.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
  return r?.result?.value;
}
async function clickIn(page, elementExpr) {  // a real in-page click at the element's centre (no system cursor)
  const xy = await evalIn(page, `(()=>{const el=(${elementExpr});if(!el)return null;const b=el.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2]})()`);
  if (!xy) return false;
  for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased'])
    await cdp(page, 'Input.dispatchMouseEvent', { type, x: xy[0], y: xy[1], button: 'left', clickCount: 1 });
  return true;
}
async function findPage(predicateExpr) {
  for (const p of await pages()) { try { if (await evalIn(p, predicateExpr)) return p; } catch { /* closing window */ } }
  return null;
}
async function waitFor(fn, ms, every = 250) {
  const end = Date.now() + ms;
  while (Date.now() < end) { const v = await fn(); if (v) return v; await sleep(every); }
  return null;
}
const mainPage = () => findPage('!!window.$projects');

// ---------- the take ----------

function sh(cmd, cwd) { execSync(cmd, { cwd, stdio: 'inherit', shell: '/bin/bash' }); }

function glideBinary() {
  const srcPath = join(HERE, 'glide.swift');
  const hash = createHash('sha1').update(readFileSync(srcPath)).digest('hex').slice(0, 12);
  const bin = join(tmpdir(), `video-editor-glide-${hash}`);
  if (!existsSync(bin)) execFileSync('swiftc', ['-O', srcPath, '-o', bin], { stdio: 'inherit' });
  return bin;
}

function settings() {
  try { return JSON.parse(readFileSync(join(homedir(), 'Library/Application Support/Screen Studio/user-preferences/settings-persistance.json'), 'utf8')).json; }
  catch { return {}; }
}

async function ensureScreenStudio() {
  if (!existsSync(APP)) die(2, `Screen Studio is not installed (${APP}); use the default capture route (screen-record.sh / page-record.mjs)`);
  const version = execFileSync('defaults', ['read', `${APP}/Contents/Info`, 'CFBundleShortVersionString'], { encoding: 'utf8' }).trim();
  if (!KNOWN_GOOD.includes(version)) log(`⚠ Screen Studio ${version} is not a build this driver was proven on (${KNOWN_GOOD.join(', ')}); trying anyway`);
  if (await mainPage().catch(() => null)) return version;
  const running = execFileSync('osascript', ['-e', 'application "Screen Studio" is running'], { encoding: 'utf8' }).trim() === 'true';
  if (running) die(2, `Screen Studio is running without its debug port ${PORT}. Save any work, quit it, and run this again (it relaunches with --remote-debugging-port=${PORT}).`);
  execFileSync('open', ['-a', 'Screen Studio', '--args', `--remote-debugging-port=${PORT}`]);
  if (!await waitFor(() => mainPage().catch(() => null), 20000, 500)) die(2, 'Screen Studio launched but its debug port never answered');
  return version;
}

// The target window's screen rect, by app + exact size, from the window server's own list. System Events
// cannot do it: two processes of one name (the take's Chrome beside the user's) resolve to the SAME process there.
function windowRect(app, [w, h]) {
  const js = `ObjC.import("CoreGraphics");JSON.stringify(ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(`
    + `$.kCGWindowListOptionOnScreenOnly|$.kCGWindowListExcludeDesktopElements,0))).filter(x=>x.kCGWindowOwnerName===${JSON.stringify(app)}`
    + `&&x.kCGWindowLayer===0).map(x=>({...x.kCGWindowBounds,pid:x.kCGWindowOwnerPID})))`;
  const wins = JSON.parse(execFileSync('osascript', ['-l', 'JavaScript', '-e', js], { encoding: 'utf8' }));
  const b = wins.find(r => r.Width === w && r.Height === h);
  return b ? Object.assign([b.X, b.Y, b.Width, b.Height], { pid: b.pid }) : null;
}

// every on-screen window, front to back, in the shape coverer() and dialogOver() read
function screenWindows() {
  const js = `ObjC.import("CoreGraphics");JSON.stringify(ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(`
    + `$.kCGWindowListOptionOnScreenOnly|$.kCGWindowListExcludeDesktopElements,0))).map(x=>({owner:x.kCGWindowOwnerName,pid:x.kCGWindowOwnerPID,`
    + `layer:x.kCGWindowLayer,name:x.kCGWindowName||"",rect:[x.kCGWindowBounds.X,x.kCGWindowBounds.Y,x.kCGWindowBounds.Width,x.kCGWindowBounds.Height]})))`;
  return JSON.parse(execFileSync('osascript', ['-l', 'JavaScript', '-e', js], { encoding: 'utf8' }));
}

// Front the take's window: the cursor's clicks and scrolls go to whatever is ON TOP (a take scrolled the user's own
// Chrome instead of its page window), and 4.0.4 will not start a covered window at all. By pid, so a second Chrome
// beside the user's is the one raised, and by AXRaise, which lifts that one window: NSRunningApplication's activate
// is only a request since macOS 14 and left Screen Studio's editor on top (2026-10-14).
function front(app, size) {
  const r = windowRect(app, size);
  if (!r) die(3, `the ${app} window of ${size.join('×')} is gone`);
  spawnSync('osascript', ['-e', `tell application "System Events" to tell (first process whose unix id is ${r.pid})`, '-e', 'set frontmost to true',
    '-e', `perform action "AXRaise" of (first window whose size is {${size[0]}, ${size[1]}})`, '-e', 'end tell']);
  return r;
}

// A url take's page has loaded and painted. The throwaway profile loads cold every take: whop.com painted 16 s after
// launch and the take recorded its window's empty grey, the scroll lost on a page not there yet (2026-10-14).
async function pageReady(profile, ms) {
  return waitFor(async () => {
    try {
      const port = readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0];
      const page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(p => p.type === 'page');
      return !!page && await evalIn(page, `document.readyState==="complete"&&performance.getEntriesByType("paint").some(e=>e.name==="first-contentful-paint")`);
    } catch { return false; }
  }, ms, 500);
}

// the text of the modal dialog a process holds up ("Leave site? / Changes you made may not be saved."), for the refusal
function dialogText(pid) {
  const r = spawnSync('osascript', ['-e', `tell application "System Events" to tell (first process whose unix id is ${pid})`,
    '-e', 'get name of every static text of (first window whose subrole is "AXDialog")', '-e', 'end tell'], { encoding: 'utf8' });
  return (r.stdout || '').trim().replace(/, /g, ' / ');
}

// display n (1 = main) in global top-left points
function displayRect(n) {
  const js = `ObjC.import("AppKit");const s=$.NSScreen.screens,m=s.objectAtIndex(0).frame;const o=[];`
    + `for(let i=0;i<s.count;i++){const f=s.objectAtIndex(i).frame;o.push([f.origin.x,m.size.height-f.origin.y-f.size.height,f.size.width,f.size.height])};JSON.stringify(o)`;
  const all = JSON.parse(execFileSync('osascript', ['-l', 'JavaScript', '-e', js], { encoding: 'utf8' }));
  return all[n - 1] ?? die(2, `no display ${n} (there are ${all.length})`);
}

function preflight(app, size, piiFile, fixedRect = null) {
  const rect = fixedRect ?? windowRect(app, size);
  if (!rect) die(4, `preflight: no ${app} window of ${size.join('×')} on screen to check`);
  const grab = join(tmpdir(), `screen-studio-preflight-${process.pid}.png`);
  execFileSync('screencapture', ['-x', `-R${rect.join(',')}`, grab]);
  const r = spawnSync('uv', ['run', join(HERE, 'pii-scan.py'), '--still', grab, '--pii', piiFile], { stdio: 'inherit' });
  if (r.status !== 0) die(4, `preflight refused the take (pii-scan exit ${r.status}); the grab is ${grab}. Clear the screen and take again.`);
  unlinkSync(grab);
}

// Escape every open window-picker page AND the recorder bar (Display / Window / Area / Device, the camera and mic
// pickers), which Screen Studio brings back after a take: it floats over the bottom-centre of the main display, and
// a take or a setup click there lands on it instead of the app (the Claude composer, 2026-10-02).
async function closePicker() {
  for (const p of await pages()) {
    try {
      if (!await evalIn(p, `(()=>{const t=document.body.innerText||"";return t.includes("Start recording")||["Display","Window","Area","Device"].every(w=>t.includes(w))})()`)) continue;
      for (const type of ['keyDown', 'keyUp'])
        await cdp(p, 'Input.dispatchKeyEvent', { type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 53 });
    } catch { /* the page closed on the key */ }
  }
}

// Screen Studio reports a failed export ("frame N could not be decoded", a bad recording) in a native alert window
// (layer 8, about 260x250) that blocks its renderer until OK is clicked. Find it, click OK, report the failure.
function exportAlert() {
  const js = `ObjC.import("CoreGraphics");JSON.stringify(ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo(`
    + `$.kCGWindowListOptionOnScreenOnly|$.kCGWindowListExcludeDesktopElements,0))).filter(x=>x.kCGWindowOwnerName==="Screen Studio"`
    + `&&x.kCGWindowLayer===8&&x.kCGWindowBounds.Width<400&&x.kCGWindowBounds.Height<400).map(x=>x.kCGWindowBounds))`;
  const a = JSON.parse(execFileSync('osascript', ['-l', 'JavaScript', '-e', js], { encoding: 'utf8' }))[0];
  if (!a) return false;
  spawnSync(glideBinary(), [`park:${a.X + a.Width / 2},${a.Y + a.Height - 30}`, 'click', 'wait:0.6']);
  return true;
}

// Screen Studio floats a quick-export preview (408x230, bottom-left, the last take with its webcam bubble) after
// every recording, and a window take recorded it where it overlapped (2026-10-02). Dismiss it before each take:
// its own onClose (the app's close path: the widget leaves the app's set and React closes its window), else Escape,
// else its "Edit" button. On 4.0.4 Escape does nothing and Edit OPENS a full editor that stays open: two orphan
// editors per run, and the next record-window deeplink raised one over the take's window (2026-10-14). NEVER
// window.close() its page: that took down the window host that the record-window picker opens in, and no take could
// start until Screen Studio restarted.
const WIDGET = `[...document.querySelectorAll('[data-tooltip="Continue editing in full editor"]')][0]`;
const WIDGET_CLOSE = `(()=>{const els=document.querySelectorAll("*");let key=null;for(const e of els){key=Object.keys(e).find(k=>k.startsWith("__reactFiber"));if(key)break}
  if(!key)return 0;const seen=new Set(),done=new Set();for(const el of els)for(let f=el[key];f&&!seen.has(f);f=f.return){seen.add(f);const p=f.memoizedProps;
  if(p&&typeof p.onClose==="function"&&"onOpenEditor" in p&&"project" in p&&!done.has(p.onClose)){done.add(p.onClose);p.onClose()}}return done.size})()`;
async function closeQuickExport() {
  for (let round = 0; round < 3; round++) {
    const widget = await findPage(`(document.body.innerText||"").includes("Will export")`);
    if (!widget) return;
    if (round === 0) await evalIn(widget, WIDGET_CLOSE).catch(() => {});
    else if (round === 1) for (const type of ['keyDown', 'keyUp'])
      await cdp(widget, 'Input.dispatchKeyEvent', { type, key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 53 }).catch(() => {});
    else { log('⚠ the quick-export widget only closed through its Edit button, which may leave an editor open'); await clickIn(widget, WIDGET).catch(() => {}); }
    await sleep(800);
  }
}

// `app` is the take's process (fronted before the click), `picker` the name Screen Studio's picker shows for it
async function startRecording(app, [w, h], display = false, picker = app) {
  await closeQuickExport();
  // -g: the deeplink must not ACTIVATE Screen Studio. Activation raised its newest editor over the take's window,
  // and 4.0.4 then never starts it (2026-10-14)
  execFileSync('open', ['-g', display ? 'screen-studio://record-display' : 'screen-studio://record-window']);
  const size = `${w} × ${h}`;
  // a display's picker page IS that display (its viewport is the display's size); a window's is a card in a list
  const pick = display ? `(()=>{if(innerWidth!==${w}||innerHeight!==${h})return null;
    const label=[...document.querySelectorAll("div")].find(d=>[...d.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()==="Start recording"));
    return label&&label.parentElement.querySelector("svg")})()` : `(()=>{const bs=[...document.querySelectorAll("*")].filter(e=>{const t=e.innerText||"";return t.startsWith(${JSON.stringify(picker)})&&t.includes(${JSON.stringify(size)})&&t.length<160});
    const inner=bs.filter(b=>!bs.some(o=>o!==b&&b.contains(o)));if(inner.length!==1)return null;
    const label=[...inner[0].parentElement.querySelectorAll("div")].find(d=>[...d.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()==="Start recording"));
    return label&&label.parentElement.querySelector("svg")})()`;
  const page = await waitFor(() => findPage(`!!${pick}`), 10000, 400);
  if (!page) {
    let matches = 0;
    for (const p of await pages()) {
      try { matches += await evalIn(p, `(()=>{const bs=[...document.querySelectorAll("*")].filter(e=>{const t=e.innerText||"";return t.startsWith(${JSON.stringify(picker)})&&t.includes(${JSON.stringify(size)})&&t.length<160});return bs.filter(b=>!bs.some(o=>o!==b&&b.contains(o))).length})()`); } catch {}
    }
    await closePicker();
    if (matches > 1) die(3, `${matches} "${picker}" windows are ${size}: the picker cannot tell them apart. Close the extra one (or size the target uniquely) and take again.`);
    const seen = [];
    for (const p of await pages()) {
      try { seen.push(...await evalIn(p, `[...document.querySelectorAll("*")].filter(e=>/\\d+ × \\d+/.test(e.innerText||"")&&(e.innerText||"").length<60).map(e=>e.innerText.split("\\n").slice(0,2).join(" "))`)); } catch {}
    }
    await closePicker();
    die(3, `no single "${picker}" window of ${size} in Screen Studio's window picker (seen: ${[...new Set(seen)].join('; ') || 'nothing'})`);
  }
  // B-roll never records the creator: the recorder bar (open beside the picker) must read "No camera" and
  // "No microphone", or the take is refused before it starts (2026-10-02: "why is my camera in the recording").
  const inputs = await findPage(`(()=>{const t=document.body.innerText||"";return ["Display","Window","Area","Device"].every(w=>t.includes(w))})()`);
  const inputsOff = inputs && await evalIn(inputs, `(()=>{const t=document.body.innerText||"";return t.includes("No camera")&&t.includes("No microphone")})()`);
  if (!inputsOff) {
    await closePicker();
    die(3, 'Screen Studio would record the camera or the microphone: in its recorder bar pick "Don\'t record camera" and "Don\'t record microphone", then take again');
  }
  // 4.0.4 never starts a window it cannot see (the click hangs at "Working...", no recorder spawns), and the
  // record-window deeplink itself raises Screen Studio's newest editor window, which buried the take's window on its
  // display: every url-route take on 2026-10-14. So the window is fronted with the picker up, then checked.
  if (!display) {
    let over = null;
    for (let i = 0; i < 4; i++) {
      const target = front(app, [w, h]);
      await sleep(600);  // an editor still opening lands on top after the raise
      if (!(over = coverer(screenWindows(), target))) break;
    }
    if (over) {
      await closePicker();
      die(3, `the ${app} window is covered by ${over.owner}${over.name ? ` "${over.name}"` : ''} and could not be fronted: Screen Studio will not start a window it cannot see. Move one of them and take again.`);
    }
  }
  const clickedAt = Date.now();
  await clickIn(page, pick);
  // the recording widget ("Working…") shows a bare m:ss timer once it records (an editor's ruler has bare m:ss too)
  const ok = await waitFor(() => findPage(`(()=>{const t=document.body.innerText||"";return t.includes("Working")&&t.split("\\n").some(l=>/^\\d+:\\d\\d$/.test(l.trim()))})()`), 8000, 250);
  if (!ok) {
    await closePicker();  // the picker stays up over the screen after a start that never came
    die(3, 'Screen Studio did not start recording (no recording timer appeared)');
  }
  return clickedAt;
}

async function openProject(path) {
  const widget = await findPage(`!!document.querySelector('[data-tooltip="Continue editing in full editor"]')`);
  if (widget) await clickIn(widget, `document.querySelector('[data-tooltip="Continue editing in full editor"]')`).catch(() => {});
  else execFileSync('open', [path]);
  const opened = () => waitFor(() => pinEditor(path), 20000, 500);
  let main = await opened();
  if (!main) { log('the editor did not open; opening the project directly'); execFileSync('open', [path]); main = await opened(); }
  if (!main) { raiseEditor(path); main = await opened(); }  // 4.0.1's $$focused only moves when the window is raised
  if (!main) die(5, `the new project never opened in an editor: ${path}`);
  return main;
}

// the main page, with the editor of `path` pinned on it (findEditor, pinFocused); null while no editor shows it
async function pinEditor(path) {
  const main = await mainPage();
  if (!main) return null;
  const want = JSON.stringify(path);
  for (const p of await pages()) {
    if (p.id === main.id) continue;
    try { if (await evalIn(p, `(${findEditor})(document, window.opener, ${want})`)) return main; } catch { /* a closing window */ }
  }
  return await evalIn(main, `(${pinFocused})(window, ${want})`) ? main : null;
}
const ED = path => `window.__veEditors.get(${JSON.stringify(path)})`;

// The recording's source clock starts at its session's unixStartMs. NOT at the event logs' processTimeMs zero:
// the video began 2.56 s after it on the first 4.0.1 take, and a mapping off the logs cut the first click away.
// Screen Studio's editor windows are named "Project - <project name>"
const editorWindow = path => `Project - ${path.split('/').pop().replace(/\.screenstudio$/, '')}`;
function raiseEditor(path) {
  spawnSync('osascript', ['-e', 'tell application "System Events" to tell process "Screen Studio"', '-e', 'set frontmost to true',
    '-e', `perform action "AXRaise" of window ${JSON.stringify(editorWindow(path))}`, '-e', 'end tell']);
}
// Save, then close: closing an unsaved take's editor raises a native "save or delete?" dialog (on whichever display
// the editor is) and the close never happens. The project stays on disk; an editor per take piled up to 17 otherwise.
function closeEditor(path) {
  raiseEditor(path);
  spawnSync('osascript', ['-e', 'tell application "System Events" to tell process "Screen Studio"',
    '-e', 'click menu item "Save" of menu "File" of menu bar 1', '-e', 'delay 1',
    '-e', `click (first button of window ${JSON.stringify(editorWindow(path))} whose subrole is "AXCloseButton")`, '-e', 'end tell']);
}

function recordingClock(path) {
  let sessions;
  try { sessions = JSON.parse(readFileSync(join(path, 'recording', 'metadata.json'), 'utf8')).sessions; } catch { return null; }
  if (!Array.isArray(sessions) || sessions.length !== 1) die(3, `the take has ${sessions?.length ?? 0} recording sessions (a paused take?); one is required`);
  return sessions[0].unixStartMs ?? null;
}

// apply the trim, zooms, masks and look to an open project, export it through the clipboard target, close its editor
async function applyAndExport(main, project, { slice, zooms, masks = [], padding = null, crop01 = null, autoZooms = false, fps, height, out, keepMasks = false, clearMasks = false }) {
    const applied = await evalIn(main, `(()=>{const p=${ED(project)}.project,sc=p.scenes[0];
      sc.slices.first.update({sourceStartMs:${slice.start},sourceEndMs:${slice.end}});
      while(sc.slices.length>1)sc.slices.remove(sc.slices.last);
      if(${!autoZooms})sc.zooms.removeAll();
      for(const z of ${JSON.stringify(zooms)})sc.zooms.add({sourceStartMs:z.start,sourceEndMs:z.end,zoom:z.level,type:z.type??"manual",presentation:"screen",
        manualTargetPoint:{x:z.x,y:z.y},isDisabled:false,hasInstantAnimation:z.instant,
        loupeOptions:{radius01:0.35,bevelRatio:0.2,chromaticAberration:0.5,hasGlassOptics:true}});
      // bounds is a LIST of rects in 4.0.1: a bare rect is stored and serialized, but getCanShow() is false and
      // nothing renders (2026-10-02: a recent-projects menu shipped unblurred in the first take)
      if(${clearMasks}){if(sc.masks.removeAll)sc.masks.removeAll();else while(sc.masks.length)sc.masks.remove(sc.masks.last);}
      for(const k of ${JSON.stringify(masks)})sc.masks.add({type:"sensitive-data",sourceStartMs:k.start,sourceEndMs:k.end,bounds:[k.bounds]});
      const c=p.serialize().config;
      if(${JSON.stringify(crop01)})p.updateConfigProp("crop",{...c.crop,rect01:${JSON.stringify(crop01)}});
      p.updateConfigProp("camera",{...c.camera,hide:true});
      p.updateConfigProp("cursor",{...c.cursor,removeShakeTreshold:0});  // a scripted cursor has no shake; the holds' drift must survive
      p.updateConfigProp("audio",{...c.audio,muteMicrophone:true,muteSystemAudio:true});
      p.updateConfigProp("output",{...c.output,aspectRatio:16/9${padding != null ? `,paddingRatio01:${Number(padding)}` : ''}});
      const s=p.serialize();return {slices:s.scenes[0].slices.map(x=>[Math.round(x.sourceStartMs),Math.round(x.sourceEndMs)]),zooms:s.scenes[0].zooms.length,
        masks:sc.masks.filter(m=>m.getCanShow()).length,
        look:[s.config.styles.background.systemName||s.config.styles.background.type,s.config.styles.screenBorderRadius]}})()`);
    log(`project ${project}\n  slice ${applied.slices.map(s => s.join('-')).join(', ')} ms · ${applied.zooms} zoom(s) · ${applied.masks} mask(s) · look ${applied.look.join(' / ')}`);
    if (clearMasks && applied.masks !== 0) die(5, `${applied.masks} mask(s) survived the clear: nothing exported`);
    if (!keepMasks && applied.masks !== masks.length) die(5, `${masks.length} mask(s) planned, ${applied.masks} that Screen Studio can show: nothing is exported unblurred`);

    // export to the clipboard target: no save panel; the file lands in $TMPDIR/Screen Studio/Clipboard Exports
    const exportDir = join(tmpdir(), 'Screen Studio', 'Clipboard Exports');
    mkdirSync(exportDir, { recursive: true });
    const before = new Set(readdirSync(exportDir));
    const clip = spawnSync('pbpaste', { encoding: 'utf8' }).stdout;
    await evalIn(main, `(async()=>{const ed=${ED(project)},em=ed.exportManager,p=ed.project;
      if(!em)throw new Error("the editor of "+p.path+" has no exportManager");
      await em.startExport({format:"mp4",fps:${fps},quality:"studio",height:${height},gifDisableLoop:false,shareableLinkVisbility:"public",
        target:"clipboard",projectPath:p.path,projectData:p.serialize()});return true})()`);
    let last = 0;
    let failed = false;
    const file = await waitFor(async () => {
      if (exportAlert()) { failed = true; return 'failed'; }
      const busy = await evalIn(main, `!!${ED(project)}.exportManager.isExportInProgress`).catch(() => true);
      const pct = await evalIn(main, `Math.round(100*(${ED(project)}.exportManager.exportProgress?.progress??0))`).catch(() => 0);
      if (busy && Math.floor(pct / 25) > last) { last = Math.floor(pct / 25); log(`export ${pct} %`); }
      if (busy) return null;
      const fresh = readdirSync(exportDir).filter(n => !before.has(n) && n.endsWith('.mp4'));
      return fresh.length ? join(exportDir, fresh.sort().at(-1)) : null;
    }, 15 * 60000, 1000);
    if (clip) spawnSync('pbcopy', { input: clip });  // the clipboard export took it; text comes back, an image would not
    if (failed) die(5, `Screen Studio's export failed on this recording (its alert was dismissed): take it again. Project: ${project}`);
    if (!file) die(5, 'the export never produced a file');
    mkdirSync(dirname(out), { recursive: true });
    copyFileSync(file, out);
    unlinkSync(file);
    closeEditor(project);
    await evalIn(main, `window.__veEditors.delete(${JSON.stringify(project)})`).catch(() => {});
    await closeQuickExport();
    await closePicker();
    return { applied };

}

// --reexport <old.provenance.json> <zooms.json> <out.mp4>: the same recording, new zooms (and padding) only
async function reexport([provPath, zoomsPath, outArg], { fps, height, force }) {
  if (!provPath || !zoomsPath || !outArg || !fps) die(2, 'usage: screen-studio-take.mjs --reexport <old.provenance.json> <zooms.json> <out.mp4> --fps <rate> [--height 2160] [--force]');
  const out = resolve(outArg);
  if (existsSync(out) && !force) die(2, `${out} exists; pass --force to replace it`);
  const prov = JSON.parse(readFileSync(provPath, 'utf8'));
  const spec = JSON.parse(readFileSync(zoomsPath, 'utf8'));
  const rect = spec.rect ?? prov.rect ?? die(2, 'zooms.json needs "rect" (the recorded screen rect): the old provenance does not carry it');
  const padding = spec.padding ?? prov.padding ?? null;
  const [s0, s1] = prov.slice_ms;
  const zooms = settleInstant((spec.zooms ?? []).map(z => {
    const a = zoomSpec(z, rect, padding) ?? die(2, `a zoom has no aim: ${JSON.stringify(z)}`);
    const start = Math.max(0, s0 + z.start * 1000), end = z.end === 'end' ? s1 : Math.min(s1, s0 + z.end * 1000);
    return { start, end, level: a.level, x: a.x, y: a.y, instant: !!z.instant, ...(a.type === 'auto' ? { type: 'auto' } : {}) };
  }), s0);
  const version = await ensureScreenStudio();
  await closePicker();
  await closeQuickExport();
  if (!existsSync(prov.project)) die(2, `the project is gone: ${prov.project}`);
  const main = await openProject(prov.project);
  // masks and crop the take already carries stay as they are; only the zooms and the padding change
  await applyAndExport(main, prov.project, { slice: { start: s0, end: s1 }, zooms, masks: [], padding, crop01: prov.crop01 ?? null, fps, height, out, keepMasks: true });
  const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate:format=duration', '-of', 'json', out], { encoding: 'utf8' }));
  const st = probe.streams[0], dur = Number(probe.format.duration);
  const summary = { out, project: prov.project, screen_studio: version, width: st.width, height: st.height, fps: st.r_frame_rate, seconds: +dur.toFixed(3), zooms: zooms.length };
  writeFileSync(out.replace(/\.mp4$/, '') + '.provenance.json', JSON.stringify({ ...prov, ...summary, reexported_from: resolve(provPath), zooms_spec: resolve(zoomsPath),
    zooms_ms: zooms, rect, padding }, null, 2));
  console.log(JSON.stringify(summary));
}

// --unmask <old.provenance.json> <out.mp4>: the same take with every blur mask taken off, nothing else changed
// (2026-10-06: the tutorial's blurs "weren't necessary at all"). Zooms replay from the provenance's zooms_ms.
async function unmask([provPath, outArg], { fps, height, force }) {
  if (!provPath || !outArg || !fps) die(2, 'usage: screen-studio-take.mjs --unmask <old.provenance.json> <out.mp4> --fps <rate> [--height 2160] [--force]');
  const out = resolve(outArg);
  if (existsSync(out) && !force) die(2, `${out} exists; pass --force to replace it`);
  const prov = JSON.parse(readFileSync(provPath, 'utf8'));
  const zooms = prov.zooms_ms ?? die(2, 'the provenance carries no zooms_ms to replay');
  const [s0, s1] = prov.slice_ms;
  const version = await ensureScreenStudio();
  await closePicker();
  await closeQuickExport();
  if (!existsSync(prov.project)) die(2, `the project is gone: ${prov.project}`);
  const main = await openProject(prov.project);
  await applyAndExport(main, prov.project, { slice: { start: s0, end: s1 }, zooms, masks: [], padding: prov.padding ?? null, crop01: prov.crop01 ?? null, fps, height, out, keepMasks: true, clearMasks: true });
  const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate:format=duration', '-of', 'json', out], { encoding: 'utf8' }));
  const st = probe.streams[0], dur = Number(probe.format.duration);
  const summary = { out, project: prov.project, screen_studio: version, width: st.width, height: st.height, fps: st.r_frame_rate, seconds: +dur.toFixed(3), zooms: zooms.length, masks: 0 };
  writeFileSync(out.replace(/\.mp4$/, '') + '.provenance.json', JSON.stringify({ ...prov, ...summary, unmasked_from: resolve(provPath) }, null, 2));
  console.log(JSON.stringify(summary));
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv[0] === '--self-test') return selfTest();
  const opt = (name, dflt) => { const i = argv.indexOf(name); if (i < 0) return dflt; const v = argv[i + 1]; argv.splice(i, 2); return v; };
  const flag = name => { const i = argv.indexOf(name); if (i < 0) return false; argv.splice(i, 1); return true; };
  const fps = parseFps(opt('--fps', '0'));
  const height = Number(opt('--height', '2160'));
  const piiFile = opt('--preflight', null);
  PORT = Number(opt('--port', '9222'));
  const force = flag('--force');
  if (flag('--reexport')) return reexport(argv, { fps, height, force });
  if (flag('--unmask')) return unmask(argv, { fps, height, force });
  const [takePath, outArg] = argv;
  if (!takePath || !outArg || !fps) die(2, 'usage: screen-studio-take.mjs <take.json> <out.mp4> --fps <the job\'s rate> [--height 2160] [--preflight pii.json] [--force] [--port 9222]   |   --self-test');
  if (process.platform !== 'darwin') die(2, 'Screen Studio is macOS-only; use the default capture route');
  const out = resolve(outArg);
  if (existsSync(out) && !force) die(2, `${out} exists (a placed capture keeps its name); pass --force to replace it`);
  const take = JSON.parse(readFileSync(takePath, 'utf8'));
  const cwd = dirname(resolve(takePath));
  const display = take.window?.display ? displayRect(take.window.display) : null;
  const size = display ? [display[2], display[3]] : take.window?.size;
  if (!display && (!Array.isArray(size) || size.length !== 2 || !(take.window.app || take.window.url))) die(2, 'take.window needs "display", or "size": [w, h] and "app" or "url"');
  if (!Array.isArray(take.steps) || !take.steps.length) die(2, 'take.steps is empty');

  const version = await ensureScreenStudio();
  const glide = glideBinary();
  let chromeProfile = null, recording = false;
  try {
    await closePicker();
    await closeQuickExport();
    for (const c of take.setup ?? []) sh(c, cwd);
    let app = take.window.app;
    if (take.window.url) {  // a page: its own chromeless Chrome window on a throwaway profile, never the user's browser
      app = 'Google Chrome';
      chromeProfile = join(tmpdir(), `screen-studio-take-chrome-${process.pid}`);
      const [x, y] = take.window.position ?? [320, 180];
      // its own debug port (0 = any free one, written to the profile's DevToolsActivePort) says when the page has painted
      execFileSync('open', ['-na', 'Google Chrome', '--args', `--user-data-dir=${chromeProfile}`, '--no-first-run', '--no-default-browser-check', '--disable-notifications',
        '--remote-debugging-port=0', `--window-position=${x},${y}`, `--window-size=${size[0]},${size[1]}`, `--app=${take.window.url}`]);
      await sleep((take.window.settle ?? 3) * 1000);
      if (!windowRect(app, size)) die(2, `the page window did not come up at ${size.join('×')}`);
      if (!await pageReady(chromeProfile, 30000)) die(2, `${take.window.url} never finished loading and painting in its window (30 s)`);
    }
    const crop = display ? (take.window.crop ?? display) : null;
    const target = display ? null : windowRect(app, size);
    const dialog = target && dialogOver(screenWindows(), target);
    if (dialog) die(2, `a dialog is up over the ${app} window ("${dialogText(dialog.pid) || 'no text'}"): setup's navigation never happened `
      + 'and the take would record the page behind it. A "Leave site?" means the page holds unsaved changes: choose in the dialog yourself, then take again.');
    if (piiFile) preflight(app, size, resolve(piiFile), crop);

    // a notification banner (another session finishing, a message) draws over the recorded rect: wait it out
    if (spawnSync(join(HERE, 'banner-clear.sh'), ['12']).status !== 0) log('⚠ a notification banner stayed up for 12 s; recording anyway');
    const t0 = Date.now();
    await startRecording(app, size, !!display, take.window.picker ?? app);
    recording = true;
    if (!display) front(app, size);
    // a display take names the app its keys and clicks are for: the picker click left Screen Studio in front
    else if (take.window.front) { execFileSync('osascript', ['-e', `tell application ${JSON.stringify(take.window.front)} to activate`]); await sleep(400); }
    await sleep(500);
    const marks = {}, positions = {}, clicks = [];
    const rect = crop ?? windowRect(app, size);
    // the crop as fractions of the recorded display
    const crop01 = display && take.window.crop ? { x: (crop[0] - display[0]) / display[2], y: (crop[1] - display[1]) / display[3], width: crop[2] / display[2], height: crop[3] / display[3] } : null;
    for (const seg of splitSegments(take.steps, take.prelude ?? [])) {
      if (seg.kind === 'run') { sh(seg.cmd, cwd); continue; }
      const r = spawnSync(glide, seg.args, { encoding: 'utf8' });
      if (r.status !== 0) die(3, `glide failed: ${r.stderr.trim()}`);
      for (const e of parseGlide(r.stdout)) {
        if (e.type === 'mark') { marks[e.name] = e.unix; if (e.at) positions[e.name] = e.at; }
        if (e.type === 'click') clicks.push(e);
      }
    }
    execFileSync('open', ['-g', 'screen-studio://finish-recording']);
    recording = false;

    const folder = settings().projectsFolderPath ?? join(homedir(), 'Screen Studio Projects');
    const project = await waitFor(() => {
      const fresh = readdirSync(folder).filter(n => n.endsWith('.screenstudio')).map(n => join(folder, n))
        .filter(p => statSync(p).birthtimeMs >= t0 - 2000 && existsSync(join(p, 'project.json')) && existsSync(join(p, 'recording', 'mousemoves-0.json')));
      return fresh.length === 1 ? fresh[0] : null;
    }, 60000, 500);
    if (!project) die(3, `no new project appeared in ${folder}`);
    const recStart = recordingClock(project);
    if (recStart == null) die(3, `no recording session start in ${project}/recording/metadata.json`);
    const main = await openProject(project);
    const durationMs = await evalIn(main, `${ED(project)}.project.sourceDurationMs`);
    const { slice, zooms, masks: planned } = plan(take, marks, recStart, durationMs, clicks, positions, rect);
    // 4.0.2 stores a mask's bounds in POINTS of the recorded display (a 0-1 rect is kept but covers nothing, so the
    // first 4.0.2 mask take exported unblurred, 2026-10-05); 4.0.1 takes 0-1 fractions of the recorded rect
    const origin = display ?? rect;
    const masks = version.startsWith('4.0.1') ? planned : planned.map((m, i) => {
      const [x, y, w, h] = take.masks[i].rect;
      return { ...m, bounds: { x: x - origin[0], y: y - origin[1], width: w, height: h } };
    });

    const { applied } = await applyAndExport(main, project, { slice, zooms, masks, padding: take.padding, crop01, autoZooms: !!take.auto_zooms, fps, height, out });

    const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate:format=duration', '-of', 'json', out], { encoding: 'utf8' }));
    const st = probe.streams[0], dur = Number(probe.format.duration), want = (slice.end - slice.start) / 1000;
    if (Math.abs(dur - want) > 0.25) log(`⚠ the export runs ${dur.toFixed(2)} s, the slice ${want.toFixed(2)} s`);
    const summary = { out, project, screen_studio: version, width: st.width, height: st.height, fps: st.r_frame_rate, seconds: +dur.toFixed(3), zooms: applied.zooms };
    writeFileSync(out.replace(/\.mp4$/, '') + '.provenance.json', JSON.stringify({ ...summary, take: resolve(takePath), slice_ms: [slice.start, slice.end], zooms_ms: zooms, rect, padding: take.padding ?? null, crop01 }, null, 2));
    console.log(JSON.stringify(summary));
  } finally {
    if (recording) execFileSync('open', ['-g', 'screen-studio://finish-recording']);
    if (chromeProfile) spawnSync('pkill', ['-f', `user-data-dir=${chromeProfile}`]);
    for (const c of take.teardown ?? []) { try { sh(c, cwd); } catch (e) { log(`teardown failed: ${e.message}`); } }
  }
}

main().catch(e => { log(e instanceof Stop ? e.message : (e.stack || String(e))); process.exitCode = e instanceof Stop ? e.code : 1; });
