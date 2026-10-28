#!/usr/bin/env node
// page-record.mjs — record a WEB PAGE headlessly for a `screen-rec` / `screenshot` cell whose
// capture source is a URL (step 5b, Stage 2). Never touches the user's own browser: it drives a
// separate headless Chrome (an installed Chrome binary or the renderer's own shell, its own profile), so nothing is
// fronted, no tab switches mid-take, no extension banner in the frame (the 2026-09-11 take through
// the live Chrome caught a tab switch and a "started debugging" bar; that route is retired for URLs).
//
//   node workflows/page-record.mjs <url> <out.mp4|out.png> [--seconds 6] [--scroll 1200] [--dark]
//        [--width 1920] [--height 1080] [--scale 2] [--fps 30000/1001] [--wait 1500] [--hide "css,css"]
//        [--ready "css"] [--ready-gone "css"] [--find "sentence||sentence" --rects <out.json>]
//
//   --seconds  length of the take (mp4 only)
//   --scroll   total pixels to scroll over the take, eased (0 = hold still)
//   --dark     prefers-color-scheme: dark (sites that follow the OS theme)
//   --scale    device scale factor: 2 = Retina-crisp (3840x2160 from a 1920x1080 viewport)
//   --wait     ms after load before the take starts (fonts, lazy images)
//   --hide     selectors to remove before the take (cookie bars, banners)
//   --scroll-el  css selector of the element that actually scrolls, when it is not the window (Notion:
//              ".notion-frame .notion-scroller"; 2026-09-17, a --scroll on a Notion page moved nothing)
//   --ready    css selector that must be VISIBLE before the take starts (in the DOM, non-zero box, not
//              visibility:hidden — a skeleton row sitting in the DOM is exactly what this has to reject),
//              and --ready-gone one that must be GONE (a spinner): polled for 15 s, and the take never
//              runs without them, so a half-loaded page can no longer become the evidence (a spinner over
//              a blank page shipped as a graphic, 2026-09-19). Asserted here, never raced against --wait.
//   --force    overwrite an existing output (default: refuse — a placed capture keeps its name)
//   --find     one or more passages (split on ||) to locate on the page AFTER the scroll is set: their
//              line rectangles land in --rects as {passage: [[x, y, w, h], ...]} in CAPTURE pixels (viewport
//              css px x scale), so a comp can draw a highlight exactly over the cited sentence (the article
//              B-roll, 2026-09-14). Whitespace and curly quotes are normalised; a passage
//              not found is reported and left out. Stills only.
//   a .png output takes one still instead of a recording (--scroll then sets the scroll position first)
//
// Output: a CONSTANT-rate H.264 mp4 (conformed by ffmpeg from Chrome's screencast webm) or a png,
// at viewport x scale pixels. The comp frames and scales it (a screen-rec is a scene, never parked
// full-frame). The runtime is puppeteer-core out of HyperFrames' own npx cache, so nothing new is
// installed; the browser is the installed Google Chrome or Chromium, else hyperframes' own chrome-headless-shell (the
// renderer's browser, which setup always installs: a client on Safari, Arc or Edge has no Chrome), else Edge on
// Windows. CHROME_PATH overrides.
import { existsSync, readdirSync, readFileSync, mkdirSync, unlinkSync, statSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';
import { execFileSync, execSync } from 'node:child_process';

const args = process.argv.slice(2);
if (args.length < 2 || args.includes('-h') || args.includes('--help')) {
  // the header comment down to (not including) the `// Output:` paragraph — a SENTINEL, never a line
  // count: the old slice(1, N) silently dropped the last help line every time a flag was documented
  const head = readFileSync(new URL(import.meta.url)).toString().split('\n').slice(1);
  const stop = head.findIndex(l => /^\/\/ Output:/.test(l) || !/^(\/\/|\s*$)/.test(l));
  console.error(head.slice(0, stop < 0 ? head.length : stop).map(l => l.replace(/^\/\/ ?/, '')).join('\n').trimEnd());
  process.exit(args.includes('-h') || args.includes('--help') ? 0 : 2);
}
const [url, outArg] = args;
if (!/^https?:\/\//i.test(url) || !outArg || outArg.startsWith('-')) { console.error('[page-record] usage: <http(s) url> <out.mp4|out.mov|out.png> [flags]'); process.exit(2); }
const opt = (k, d) => { const i = args.indexOf(k); return i > -1 ? args[i + 1] : d; };
const num = (k, d) => { const v = +opt(k, d); if (!Number.isFinite(v) || v < 0) { console.error(`[page-record] ${k} needs a number, got ${opt(k, d)}`); process.exit(2); } return v; };
const SECS = num('--seconds', 6), SCROLL = num('--scroll', 0), DARK = args.includes('--dark'), FORCE = args.includes('--force');
const W = num('--width', 1920), H = num('--height', 1080), SCALE = num('--scale', 2);
const FPS = opt('--fps', '30000/1001'), WAIT = num('--wait', 1500), HIDE = opt('--hide', '');
const SCROLL_EL = opt('--scroll-el', '');   // a page that scrolls an INNER container (Notion: .notion-frame .notion-scroller), not the window
const READY = opt('--ready', ''), READY_GONE = opt('--ready-gone', '');   // what must be on screen (and what must be gone) before the take
const FIND = opt('--find', ''), RECTS = opt('--rects', '');
if ((FIND && !RECTS) || (RECTS && !FIND)) { console.error('[page-record] --find and --rects go together'); process.exit(2); }
if (!/^\d+(\/\d+)?$/.test(FPS)) { console.error(`[page-record] --fps wants a rational like 30000/1001, got ${FPS}`); process.exit(2); }
const out = resolve(outArg); const ext = out.toLowerCase().match(/\.(mp4|mov|png)$/)?.[1];
if (!ext) { console.error('[page-record] output must end in .mp4, .mov or .png'); process.exit(2); }
const still = ext === 'png';
if (existsSync(out) && !FORCE) { console.error(`[page-record] ${out} exists — a capture already in a comp keeps its name; write a new one or pass --force`); process.exit(2); }
if (!still && SECS <= 0) { console.error('[page-record] --seconds must be > 0 for a recording'); process.exit(2); }
mkdirSync(dirname(out), { recursive: true });

// puppeteer-core: the newest copy any hyperframes run left in the npx cache (the job pin is per job and bumps; a pin bonus here went stale on the next bump)
// the npm cache is not always ~/.npm: npm_config_cache overrides it, and Windows keeps it under %LOCALAPPDATA%\npm-cache
let npmCache = '';
// Windows runs npm through its .cmd shim, so a shell is needed there; Node 24 deprecates args with a shell (DEP0190),
// so the shell gets ONE command string and no args array
const npmOpts = { encoding: 'utf8', timeout: 15000, stdio: ['ignore', 'pipe', 'ignore'] };
try { npmCache = (process.platform === 'win32' ? execSync('npm config get cache', npmOpts) : execFileSync('npm', ['config', 'get', 'cache'], npmOpts)).trim(); } catch {}
const npxDirs = [...new Set([process.env.npm_config_cache, join(homedir(), '.npm'), process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'npm-cache'), npmCache]
  .filter(Boolean).map(r => join(resolve(r), '_npx')))];
let pick = null;
for (const npx of npxDirs) for (const d of existsSync(npx) ? readdirSync(npx) : []) {
  const nm = join(npx, d, 'node_modules');
  const pc = join(nm, 'puppeteer-core', 'package.json'); if (!existsSync(pc)) continue;
  const pcv = JSON.parse(readFileSync(pc)).version;
  const score = pcv.split('.').reduce((a, b, i) => a + (parseInt(b, 10) || 0) / 1000 ** i, 0);
  if (!pick || score > pick.score) pick = { score, nm, pcv };
}
if (!pick) { console.error(`[page-record] no puppeteer-core in any npx cache (searched: ${npxDirs.join(', ')}) — run \`npm_config_before=2026-10-01T23:59:59Z npx -y hyperframes@0.8.105 --version\` once`); process.exit(2); }
const entry = ['lib/puppeteer/puppeteer-core.js', 'lib/esm/puppeteer/puppeteer-core.js'].map(e => join(pick.nm, 'puppeteer-core', e)).find(existsSync);
const puppeteer = await import(pathToFileURL(entry).href);

// hyperframes' chrome-headless-shell, newest version first (overshoot-ink.mjs's lookup): `browser ensure` puts it there
const shells = join(homedir(), '.cache', 'hyperframes', 'chrome', 'chrome-headless-shell');
const shell = (existsSync(shells) ? readdirSync(shells).sort().reverse() : []).map(v => {
  const d = join(shells, v); const sub = existsSync(d) ? readdirSync(d).find(x => x.startsWith('chrome-headless-shell')) : null;
  return sub && ['chrome-headless-shell', 'chrome-headless-shell.exe'].map(b => join(d, sub, b)).find(existsSync);
}).find(Boolean);
const CHROME = process.env.CHROME_PATH || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe') : '',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
  shell,
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].filter(Boolean).find(existsSync);
if (!CHROME) { console.error('[page-record] no Chrome found (an installed Chrome, hyperframes\' chrome-headless-shell or Edge) — set CHROME_PATH'); process.exit(2); }

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--hide-scrollbars', '--force-device-scale-factor=' + SCALE] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: SCALE });
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: DARK ? 'dark' : 'light' }]);
  try {
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 });
  } catch (e) {
    if (!/timeout/i.test(String(e))) throw new Error(`cannot load ${url}: ${String(e).split('\n')[0]}`);
    console.error('[page-record] network never went idle (a live page); continuing on load');   // goto already reached load
  }
  if (HIDE) await page.evaluate(sel => document.querySelectorAll(sel).forEach(e => e.remove()), HIDE);
  // readiness is ASSERTED before anything is recorded: nothing half-loaded ever reaches a file, so the
  // capture cannot quietly become a spinner over a blank page (2026-09-19)
  for (const [sel, gone] of [[READY, false], [READY_GONE, true]]) {
    if (!sel) continue;
    try {
      // `visible`, not mere DOM presence: a skeleton/placeholder row IS in the DOM, and a --ready that
      // resolves on presence alone would green-light exactly the half-loaded page this exists to reject
      await page.waitForSelector(sel, { timeout: 15000, visible: !gone, hidden: gone });
      console.error(`[page-record] ready: ${gone ? 'gone ' : ''}${sel}`);
    } catch {
      console.error(`[page-record] NOT READY: ${sel}${gone ? ' is still on the page' : ' never became visible'} after 15s`);
      throw new Error(`the page never reached its ready state (${sel}): nothing recorded`);
    }
  }
  await new Promise(r => setTimeout(r, WAIT));
  // Chrome's screencast only emits a frame on PAINT: a static page yields an EMPTY take (measured on
  // example.com, 0-byte webm). A 1 px near-invisible ticker forces a repaint every tick of the take.
  await page.evaluate(() => { const t = document.createElement('div'); t.id = '__hf_tick'; t.style.cssText = 'position:fixed;left:0;top:0;width:2px;height:2px;opacity:0.01;background:#000;pointer-events:none;z-index:2147483647'; document.body.appendChild(t); });
  const tick = (n) => page.evaluate(n => { const t = document.getElementById('__hf_tick'); if (t) t.style.transform = `translateX(${n % 2}px)`; }, n);
  console.error(`[page-record] ${url}  ${W}x${H}@${SCALE}x  ${still ? 'still' : SECS + 's, scroll ' + SCROLL + 'px'}${DARK ? '  dark' : ''}`);

  if (still) {
    if (SCROLL > 0) { await page.evaluate((y, sel) => { const e = sel && document.querySelector(sel); if (e) e.scrollTop = y; else window.scrollTo(0, y); }, SCROLL, SCROLL_EL); await new Promise(r => setTimeout(r, 300)); }
    await page.evaluate(() => document.getElementById('__hf_tick')?.remove());
    if (FIND) {
      // locate each passage across the page's text nodes (a sentence usually spans several) and return the
      // line boxes of the DOM Range that covers it, in viewport css px; the caller gets capture px
      const found = await page.evaluate((queries) => {
        const norm = s => s.replace(/[\u2018\u2019\u201A]/g, "'").replace(/[\u201C\u201D\u201E]/g, '"').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ');
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, { acceptNode: n => {
          const p = n.parentElement; if (!p) return NodeFilter.FILTER_REJECT;
          const tag = p.tagName; if (/^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(tag)) return NodeFilter.FILTER_REJECT;
          return n.nodeValue.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT; } });
        const nodes = []; let text = ''; const map = [];   // map[i] = [node index, offset in node] for each char of `text`
        for (let n; (n = walker.nextNode());) {
          const raw = n.nodeValue; nodes.push(n);
          for (let i = 0; i < raw.length; i++) { text += raw[i]; map.push([nodes.length - 1, i]); }
          text += ' '; map.push([nodes.length - 1, raw.length]);
        }
        // normalise text while keeping the char map: build a normalised string with an index map back
        const nt = []; const nmap = []; let prevSpace = true;
        for (let i = 0; i < text.length; i++) {
          let c = text[i];
          if (/[\u2018\u2019\u201A]/.test(c)) c = "'"; else if (/[\u201C\u201D\u201E]/.test(c)) c = '"'; else if (c === '\u00a0') c = ' ';
          if (/\s/.test(c)) { if (prevSpace) continue; c = ' '; prevSpace = true; } else prevSpace = false;
          nt.push(c); nmap.push(i);
        }
        const hay = nt.join('');
        const out = {};
        for (const q of queries) {
          const needle = norm(q).trim(); const at = hay.indexOf(needle);
          if (at < 0) { out[q] = null; continue; }
          const [n0, o0] = map[nmap[at]]; const [n1, o1] = map[nmap[at + needle.length - 1]];
          const r = document.createRange(); r.setStart(nodes[n0], o0); r.setEnd(nodes[n1], o1 + 1);
          out[q] = Array.from(r.getClientRects()).filter(b => b.width > 1 && b.height > 1).map(b => [b.x, b.y, b.width, b.height]);
        }
        return out;
      }, FIND.split('||'));
      const rects = {};
      for (const [q, rs] of Object.entries(found)) {
        if (!rs) { console.error(`[page-record] --find: passage NOT on the page: "${q.slice(0, 80)}"`); continue; }
        rects[q] = rs.map(([x, y, w, h]) => [Math.round(x * SCALE), Math.round(y * SCALE), Math.round(w * SCALE), Math.round(h * SCALE)]);
        const off = rs.filter(([, y, , h]) => y < 0 || y + h > H).length;
        console.error(`[page-record] --find: "${q.slice(0, 60)}${q.length > 60 ? '…' : ''}" -> ${rs.length} line box(es)${off ? `, ${off} OUTSIDE the viewport (adjust --scroll)` : ''}`);
      }
      const { writeFileSync } = await import('node:fs');
      writeFileSync(RECTS, JSON.stringify({ url, scroll: SCROLL, viewport: [W, H], scale: SCALE, rects }, null, 1));
    }
    await page.screenshot({ path: out });
  } else {
    const webm = out.replace(/\.(mp4|mov)$/i, '') + '.rec.webm';
    try {
      const rec = await page.screencast({ path: webm });
      const t0 = Date.now();
      // eased scroll over the whole take, driven from here so the timing is the take's, not the page's
      const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      let n = 0, done = false;
      while (!done) {
        const t = Math.min(1, (Date.now() - t0) / (SECS * 1000)); done = t >= 1;
        if (SCROLL > 0) await page.evaluate((y, sel) => { const e = sel && document.querySelector(sel); if (e) e.scrollTop = y; else window.scrollTo(0, y); }, Math.round(ease(t) * SCROLL), SCROLL_EL);
        await tick(n++);
        await new Promise(r => setTimeout(r, 16));
      }
      await rec.stop();
      const size = existsSync(webm) ? statSync(webm).size : 0;
      if (size < 1000) throw new Error(`the screencast captured nothing (${size} bytes): the page never painted a frame`);
      // Chrome's screencast is variable-rate: conform to the timeline's constant rate
      execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', webm, '-an', '-vf', `fps=${FPS}`, '-c:v', 'libx264', '-crf', '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: 'inherit' });
    } finally {
      if (existsSync(webm)) unlinkSync(webm);
    }
  }
  const probe = execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', still ? 'stream=width,height' : 'stream=width,height:format=duration', '-of', 'csv=p=0', out]).toString().trim().replace(/\n/g, ' ');
  console.log(`[page-record] ${probe.replace(',', 'x')} -> ${out}`);
} catch (e) {
  console.error(`[page-record] failed: ${String(e.message || e).split('\n')[0]}`); process.exitCode = 1;
} finally {
  await browser.close();
}
