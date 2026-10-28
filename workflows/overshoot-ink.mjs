#!/usr/bin/env node
// overshoot-ink.mjs — graphics-qa.py's `source:overshoot` check on RENDERED INK (the helper it runs; not a step of its own).
//
//   node workflows/overshoot-ink.mjs <spec.json>      → JSON on stdout
//   spec: {"comps": [{"id": "g9", "path": "/abs/compositions/g9.html", "calls": [{"fn": "pop", "sel": "#pad", "at": 2.26}]}],
//          "fps": 23.976, "alpha": 160}
//
// Why: a pop overshoots to 1.10 (a slam starts at 1.16) and the grown element must clear its neighbours
// (animations.md § The presets). The static check reads CSS boxes, so a TYPE neighbour (no width/height: its
// box is its glyphs) and an SVG-wrapped prop (a div around an svg whose ink is not its frame) were never
// measured: g9's controller popped over the "r" of a 40 px "or" for two frames with no entry in the report
// (2026-09-28). This loads the comp in headless Chrome (hyperframes' own chrome-headless-shell when present,
// the renderer's engine), seeks every rendered frame of each pop/slam's overshoot, and screenshots the target
// and each neighbour ALONE on a transparent page (everything else visibility:hidden, the transforms, clips and
// the smear exactly as rendered). Ink = alpha >= spec.alpha. Per frame it measures the overlap of the target's
// ink with each neighbour's ink, and of the same target forced to scale 1 (its rest size, same frame, same
// float), so an authored overlap at rest is told apart from the overshoot.
//
// Neighbours = the siblings of the target and of every ancestor (each a whole subtree), so a label in the next
// wrapper over counts too. The pop/slam calls come from a hook on HF.init (every call, computed selectors
// included); a comp with inline helpers falls back to the literal calls graphics-qa.py parsed.
// Output per comp: {id, fps, mult, calls: [{fn, sel, at, target, frames, hits: [{neighbour, kind, text, px, rest_px,
// w, h, n, t, scale, series: [[frame, px], ...]}]}]} in AUTHORING pixels (a 4K comp's are divided by its multiple), the
// worst frame's numbers with rest_px the largest at-rest overlap over the window; or {id, error}.
// The runtime is puppeteer-core out of HyperFrames' npx cache (as page-record.mjs); gsap and other CDN scripts are
// cached under ~/.cache/video-editor/cdn/ on first fetch, so a later run works offline.
import { existsSync, readdirSync, readFileSync, writeFileSync, mkdirSync, renameSync, statSync } from 'node:fs';
import { join, dirname, resolve, extname, sep } from 'node:path';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';
import { execFileSync, execSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import http from 'node:http';

const spec = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const ALPHA = spec.alpha || 160;
const WINDOW = { pop: 4, slam: 4 };   // frames after the call that carry the overshoot (pop 0.90→1.10 over 3, settles on 4; slam's biggest are its first)
const fail = m => { console.log(JSON.stringify({ error: m })); process.exit(0); };

// puppeteer-core: the newest copy in any npx cache (the same search page-record.mjs does)
let npmCache = '';
// Windows runs npm through its .cmd shim, so a shell is needed there; Node 24 deprecates args with a shell (DEP0190),
// so the shell gets ONE command string and no args array
const npmOpts = { encoding: 'utf8', timeout: 15000, stdio: ['ignore', 'pipe', 'ignore'] };
try { npmCache = (process.platform === 'win32' ? execSync('npm config get cache', npmOpts) : execFileSync('npm', ['config', 'get', 'cache'], npmOpts)).trim(); } catch {}
const npxDirs = [...new Set([process.env.npm_config_cache, join(homedir(), '.npm'), process.env.LOCALAPPDATA && join(process.env.LOCALAPPDATA, 'npm-cache'), npmCache]
  .filter(Boolean).map(r => join(resolve(r), '_npx')))];
let pick = null;
for (const npx of npxDirs) for (const d of existsSync(npx) ? readdirSync(npx) : []) {
  const pc = join(npx, d, 'node_modules', 'puppeteer-core', 'package.json'); if (!existsSync(pc)) continue;
  const score = JSON.parse(readFileSync(pc)).version.split('.').reduce((a, b, i) => a + (parseInt(b, 10) || 0) / 1000 ** i, 0);
  if (!pick || score > pick.score) pick = { score, nm: join(npx, d, 'node_modules') };
}
if (!pick) fail('no puppeteer-core in any npx cache: run `npm_config_before=2026-10-01T23:59:59Z npx -y hyperframes@0.8.105 --version` once');
const entry = ['lib/puppeteer/puppeteer-core.js', 'lib/esm/puppeteer/puppeteer-core.js'].map(e => join(pick.nm, 'puppeteer-core', e)).find(existsSync);
const puppeteer = await import(pathToFileURL(entry).href);

// the browser: hyperframes' chrome-headless-shell (what the render runs on), else CHROME_PATH / an installed Chrome
const shells = join(homedir(), '.cache', 'hyperframes', 'chrome', 'chrome-headless-shell');
const shell = (existsSync(shells) ? readdirSync(shells).sort().reverse() : []).map(v => {
  const d = join(shells, v); const sub = existsSync(d) ? readdirSync(d).find(x => x.startsWith('chrome-headless-shell')) : null;
  return sub && ['chrome-headless-shell', 'chrome-headless-shell.exe'].map(b => join(d, sub, b)).find(existsSync);
}).find(Boolean);
const CHROME = process.env.CHROME_PATH || shell || [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  process.env.LOCALAPPDATA ? join(process.env.LOCALAPPDATA, 'Google', 'Chrome', 'Application', 'chrome.exe') : '',
  '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
].filter(Boolean).find(existsSync);
if (!CHROME) fail('no Chrome found (hyperframes chrome-headless-shell, CHROME_PATH or an installed Chrome)');

// a static server over the comp's folder's parent (`hf-anim.js` and `assets/` resolve beside the comp, `../` one up)
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.otf': 'font/otf', '.ttf': 'font/ttf', '.woff': 'font/woff', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.gif': 'image/gif', '.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm' };
let ROOT = '/';
const server = http.createServer((req, res) => {
  const p = resolve(ROOT, '.' + decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!(p + sep).startsWith(ROOT + sep) && p !== ROOT) { res.writeHead(403); return res.end(); }
  try { if (!statSync(p).isFile()) throw 0; } catch { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': TYPES[extname(p).toLowerCase()] || 'application/octet-stream' }); res.end(readFileSync(p));
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const ORIGIN = `http://127.0.0.1:${server.address().port}`;

const CDN = join(homedir(), '.cache', 'video-editor', 'cdn');
async function cdn(req) {
  const url = req.url(), key = join(CDN, createHash('sha1').update(url).digest('hex'));
  try {
    if (!existsSync(key)) {
      const r = await fetch(url); if (!r.ok) throw new Error(String(r.status));
      mkdirSync(CDN, { recursive: true });
      writeFileSync(key + '.tmp' + process.pid, Buffer.from(await r.arrayBuffer())); renameSync(key + '.tmp' + process.pid, key);
      writeFileSync(key + '.type', r.headers.get('content-type') || 'text/javascript');
    }
    await req.respond({ status: 200, contentType: existsSync(key + '.type') ? readFileSync(key + '.type', 'utf8') : 'text/javascript',
      headers: { 'access-control-allow-origin': '*' }, body: readFileSync(key) });
  } catch { await req.abort(); }
}

// every pop/slam the comp makes, recorded as it is authored (HF.init returns the helpers the comp destructures)
const HOOK = () => {
  let hf; window.__ovCalls = [];
  Object.defineProperty(window, 'HF', { configurable: true, get: () => hf, set: v => {
    if (v && typeof v.init === 'function' && !v.__ov) {
      const init = v.init;
      v = Object.assign({}, v, { __ov: 1, init(o) {
        const H = init(o); window.__ovFps = o && o.fps;
        for (const fn of ['pop', 'slam']) {
          const f = H[fn]; if (typeof f !== 'function') continue;
          H[fn] = function (el, at, ...rest) { window.__ovCalls.push({ fn, el, at }); return f.call(this, el, at, ...rest); };
        }
        return H;
      } });
    }
    hf = v;
  } });
};

const ISO = `html.__ovIso, html.__ovIso body { background: transparent !important; }
html.__ovIso * { visibility: hidden !important; }
html.__ovIso .__ovShow, html.__ovIso .__ovShow * { visibility: visible !important; }`;

const browser = await puppeteer.launch({ executablePath: CHROME, headless: /headless-shell/.test(CHROME) ? 'shell' : true,
  args: ['--hide-scrollbars', '--force-device-scale-factor=1', '--font-render-hinting=none'] });
const out = [];
try {
  for (const c of spec.comps) {
    const html = readFileSync(c.path, 'utf8');
    const W = +(html.match(/data-width="(\d+)"/) || [0, 1920])[1], Hh = +(html.match(/data-height="(\d+)"/) || [0, 1080])[1];
    const mult = W / 1920;
    ROOT = resolve(dirname(dirname(c.path)));
    const page = await browser.newPage();
    try {
      await page.setViewport({ width: W, height: Hh, deviceScaleFactor: 1 });
      await page.setRequestInterception(true);
      page.on('request', req => req.url().startsWith(ORIGIN) ? req.continue() : /^https:\/\//.test(req.url()) && req.method() === 'GET' ? cdn(req) : req.continue());
      const errs = [];
      page.on('pageerror', e => errs.push(String(e && e.message || e).split('\n')[0]));
      page.on('requestfailed', r => errs.push('failed ' + r.url()));
      await page.evaluateOnNewDocument(HOOK);
      const rel = resolve(c.path).slice(ROOT.length).split(sep).map(encodeURIComponent).join('/');
      await page.goto(ORIGIN + rel, { waitUntil: 'load', timeout: 45000 });
      await page.waitForFunction(() => !!(window.__timelines && window.__timelines.main), { timeout: 15000 })   // a boolean: a GSAP timeline is a thenable
        .catch(() => { throw new Error('the comp never exposed window.__timelines.main' + (errs.length ? ': ' + errs.slice(0, 3).join(' · ') : ' (did its script throw?)')); });
      await page.evaluate(async (css) => {
        const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s);
        await document.fonts.ready;
        await Promise.all([...document.fonts].map(f => (f.status === 'unloaded' ? f.load() : f.loaded).catch(() => {})));
      }, ISO);
      const info = await page.evaluate((lit) => {
        const hooked = window.__ovCalls.length > 0;
        const src = hooked ? window.__ovCalls : lit.map(l => ({ fn: l.fn, el: l.sel, at: l.at }));
        const els = x => typeof x === 'string' ? [...document.querySelectorAll(x)] : x instanceof Element ? [x]
          : x && typeof x.length === 'number' ? [...x].filter(e => e instanceof Element) : [];
        const name = e => e.id ? '#' + e.id : (e.getAttribute('class') || '').trim() ? '.' + e.getAttribute('class').trim().split(/\s+/).join('.') : '<' + e.tagName.toLowerCase() + '>';
        window.__ovT = [];
        const calls = src.map(s => ({ fn: s.fn, at: +s.at, sel: typeof s.el === 'string' ? s.el : null,
          targets: els(s.el).map(e => { window.__ovT.push(e); return { k: window.__ovT.length - 1, name: name(e) }; }) }));
        return { hooked, fps: window.__ovFps || null, dur: window.__timelines.main.duration(), calls };
      }, c.calls || []);
      const fps = info.fps || spec.fps;
      if (!fps) throw new Error('no fps: the comp does not call HF.init and graphics-qa.py passed none');
      const F = 1 / fps;
      const res = { id: c.id, fps, mult, hooked: info.hooked, calls: [] };
      for (const call of info.calls) {
        const n0 = Math.ceil(call.at * fps - 1e-6), n1 = Math.floor((call.at + (WINDOW[call.fn] || 4) * F) * fps + 1e-6);
        const frames = []; for (let n = n0; n <= n1; n++) if (n / fps < info.dur) frames.push(n);
        for (const tg of call.targets) {
          const worst = {};
          for (const n of frames) {
            const t = n / fps;
            const plan = await page.evaluate((k, t) => {
              const tl = window.__timelines.main; tl.seek(0); tl.seek(t);
              const T = window.__ovT[k];
              const box = el => {   // the union of the subtree's boxes (a positioned wrapper can be 0x0 around its children)
                let r = null;
                const add = b => { if (b.width > 0 && b.height > 0) r = r ? { l: Math.min(r.l, b.left), t: Math.min(r.t, b.top), r: Math.max(r.r, b.right), b: Math.max(r.b, b.bottom) }
                  : { l: b.left, t: b.top, r: b.right, b: b.bottom }; };
                for (const e of [el, ...el.querySelectorAll('*')]) add(e.getBoundingClientRect());
                const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                for (let x = w.nextNode(); x; x = w.nextNode()) if (x.textContent.trim()) { const g = document.createRange(); g.selectNodeContents(x); add(g.getBoundingClientRect()); }
                return r;
              };
              const tb = box(T); if (!tb) return null;
              const name = e => e.id ? '#' + e.id : (e.getAttribute('class') || '').trim() ? '.' + e.getAttribute('class').trim().split(/\s+/).join('.') : '<' + e.tagName.toLowerCase() + '>';
              const cands = []; window.__ovC = [];
              for (let a = T; a && a.parentElement && a !== document.body; a = a.parentElement)
                for (const s of a.parentElement.children) {
                  if (s === a || ['SCRIPT', 'STYLE', 'TEMPLATE', 'LINK', 'META'].includes(s.tagName)) continue;
                  const b = box(s);
                  if (!b || b.r < tb.l - 4 || b.l > tb.r + 4 || b.b < tb.t - 4 || b.t > tb.b + 4) continue;
                  const text = s.textContent.replace(/\s+/g, ' ').trim();
                  window.__ovC.push(s);
                  cands.push({ k: window.__ovC.length - 1, name: name(s), text: text.slice(0, 40), b,
                    kind: /[\p{L}\p{N}]/u.test(text) ? 'type' : (s.tagName.toLowerCase() === 'svg' || s.querySelector('svg')) ? 'svg' : 'box' });
                }
              if (!cands.length) return { cands };
              const u = cands.reduce((r, c) => ({ l: Math.min(r.l, c.b.l), t: Math.min(r.t, c.b.t), r: Math.max(r.r, c.b.r), b: Math.max(r.b, c.b.b) }), tb);
              const x = Math.max(0, Math.floor(u.l) - 2), y = Math.max(0, Math.floor(u.t) - 2);
              const clip = { x, y, width: Math.min(innerWidth, Math.ceil(u.r) + 2) - x, height: Math.min(innerHeight, Math.ceil(u.b) + 2) - y };
              return { cands, clip, scale: +gsap.getProperty(T, 'scale') };
            }, tg.k, t);
            if (!plan || !plan.cands.length || plan.clip.width <= 0 || plan.clip.height <= 0) continue;
            const shots = [['T', null], ...plan.cands.map(c => ['C' + c.k, c.k]), ['R', null]];
            for (const [key, ck] of shots) {
              await page.evaluate((k, ck, rest) => {
                document.querySelectorAll('.__ovShow').forEach(e => e.classList.remove('__ovShow'));
                document.documentElement.classList.add('__ovIso');
                (ck === null ? window.__ovT[k] : window.__ovC[ck]).classList.add('__ovShow');
                if (rest) gsap.set(window.__ovT[k], { scale: 1 });   // the SAME frame at rest size: the overshoot is the only difference
              }, tg.k, ck, key === 'R');
              const b64 = await page.screenshot({ clip: plan.clip, omitBackground: true, encoding: 'base64' });
              await page.evaluate(async (key, b64, A) => {
                const img = new Image(); img.src = 'data:image/png;base64,' + b64; await img.decode();
                const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
                const x = cv.getContext('2d'); x.drawImage(img, 0, 0);
                const d = x.getImageData(0, 0, cv.width, cv.height).data, m = new Uint8Array(cv.width * cv.height);
                for (let i = 0; i < m.length; i++) m[i] = d[i * 4 + 3] >= A ? 1 : 0;
                (window.__ovM = window.__ovM || {})[key] = { m, w: cv.width };
              }, key, b64, ALPHA);
            }
            const cmp = await page.evaluate((ks) => {
              document.documentElement.classList.remove('__ovIso');
              document.querySelectorAll('.__ovShow').forEach(e => e.classList.remove('__ovShow'));
              const M = window.__ovM, T = M.T.m, R = M.R.m, w = M.T.w;
              return ks.map(k => {
                const C = M['C' + k].m; let px = 0, rest = 0, l = 1e9, t = 1e9, r = -1, b = -1;
                for (let i = 0; i < C.length; i++) {
                  if (!C[i]) continue;
                  if (R[i]) rest++;
                  if (T[i]) { px++; const X = i % w, Y = (i / w) | 0; if (X < l) l = X; if (X > r) r = X; if (Y < t) t = Y; if (Y > b) b = Y; }
                }
                return { k, px, rest, w: px ? r - l + 1 : 0, h: px ? b - t + 1 : 0 };
              });
            }, plan.cands.map(c => c.k));
            for (const m of cmp) {
              const cd = plan.cands.find(c => c.k === m.k), key = cd.name + '|' + cd.text;
              const a = mult * mult, hit = { neighbour: cd.name, kind: cd.kind, text: cd.text, px: +(m.px / a).toFixed(1), rest_px: +(m.rest / a).toFixed(1),
                w: +(m.w / mult).toFixed(1), h: +(m.h / mult).toFixed(1), n, t: +t.toFixed(4), scale: +plan.scale.toFixed(4) };
              const prev = worst[key], series = (prev ? prev.series : []).concat([[n, hit.px]]);
              worst[key] = Object.assign(!prev || hit.px > prev.px ? hit : prev, { rest_px: Math.max(prev ? prev.rest_px : 0, hit.rest_px), series });
            }
          }
          res.calls.push({ fn: call.fn, sel: call.sel, at: call.at, target: tg.name, frames, hits: Object.values(worst) });
        }
      }
      out.push(res);
    } catch (e) {
      out.push({ id: c.id, error: String(e && e.message || e).split('\n')[0] });
    } finally { await page.close().catch(() => {}); }
  }
} finally { await browser.close().catch(() => {}); server.close(); }
console.log(JSON.stringify({ comps: out }));
