// hf-anim.js: THE REGISTRY as code (animations.md + creative-moves.md, executable).
//
// Copy this file into projects/<job>/hf-graphics/gfx/ beside render.sh, and start every hand
// comp from comp-scaffold.html, which loads it as  <script src="hf-anim.js"></script>
// (bare name — the render base is the gfx/ root; a "../" form trips hyperframes'
// invalid_parent_traversal_in_asset_path lint). After gsap, before the comp's own script.
// Nothing in here is retyped into a comp.
//
// Why: eleven hand comps on your-job each re-typed the same four helper blocks and each
// got a different subset wrong, nine of the ten motion defects the review rounds found were
// re-typings (2026-09-02). A comp now DECLARES its rate and calls the registry:
//
//   const DUR = 4.642;
//   const H = HF.init({fps: 30000/1001, stepFps: 12, dur: DUR});
//   //  fps MUST equal the base footage rate (ffprobe the raw) and the render's FPS=:
//   //  30000/1001 for 29.97, 24000/1001 for 23.976.
//   //  stepFps: 12  on a bg-DARK full-screen (rendered STEP_FPS=12: pop/slam/countUp re-express
//   //  themselves in 83 ms states and flash refuses); omit it on overlays and bg-light full-screens.
//   const {tl, F, SF, pop, slam, flash, riseIn, riseOut, exit, slideIn, slideOut, float, camera, arrow, drawOn, countUp, reveal, DRAW} = H;
//   ...
//   H.finish();   // pins DUR, rewinds, exposes window.__timelines.main
//
// Every number below is the registry's. Change it in the owning doc FIRST, then here, never in a
// comp: animations.md for the in/out presets and the arrow, creative-moves.md move 2 for the float
// and 4d for the reveal bursts.
window.HF = (function () {
  const REG = {
    rise:  {in: {dist: 22, dur: 0.55, ease: 'power3.out'}, out: {dist: 18, dur: 0.35, ease: 'power2.in'}},
    slide: {in: {dur: 0.75, ease: 'power2.out'}, out: {dur: 0.38, ease: 'power3.inOut'}},
    smear: {k: 0.2, max: 60, scale: 6},                                // THE SMEAR: on a slide sigma = k x the peak px/frame (capped); on a pop/slam an isotropic sigma of `scale` px decaying with the move (2026-09-10)
    pop:   {from: 0.90, over: 1.10, frames: 3, ease: 'power2.out'},   // then 1.00 on frame 4 (a one-frame linear settle, not a set: MBLUR)
    slam:  {from: 1.16, frames: 7, ease: 'power2.out'},
    slamSteps: [1.16, 1.09, 1.03, 1.00],                              // the 12 fps re-expression (four 83 ms states)
    flash: [[0, 0.2], [1, 0], [3, 0.2], [4, 0], [5, 0.2], [6, 1]],
    float: {subtle: [6, 8, 1.25, 0.95], medium: [10, 16, 1.35, 1.05]}, // [travel x, travel y, period x, period y]
    camera: {push: [1.00, 1.05], pan: 24},                               // a full-screen's scene wrapper over its span (creative-moves move 2)
    draw:  9,                                                          // frames a stroke takes to arrive
    arrow: {len: 2.27, half: 1.33, sink: 0.27},                        // head geometry in stroke widths
    burst: [3, 5, 2, 4, 6, 3, 2, 5, 4, 3, 6, 2],                        // reveal burst sizes: fixed, irregular, never a modulo
  };
  const AXIS = {bottom: ['y', 1], top: ['y', -1], left: ['x', -1], right: ['x', 1]};
  const FRAME = {x: 1920, y: 1080};

  function init(o) {
    if (!o || !o.fps || !o.dur) throw new Error('HF.init needs {fps, dur[, stepFps]}');
    const fps = o.fps, stepFps = o.stepFps || null, DUR = o.dur;
    // shutter: true = the comp loads hf-motion-blur.js (HyperFrames' motion-blur component, real trajectory integration on the
    // elements marked data-hf-motion-blur) and renders WITHOUT MBLUR, so THE SMEAR's stand-in filter steps aside on every
    // element the component blurs (2026-10-06). Only those: an unmarked mover, or a mark the component refuses, keeps the
    // smear, or a comp-wide off left it with no blur at all (g9's chips, whose marks never parsed, 2026-10-06).
    const shutter = !!o.shutter;
    const MB_KEYS = ['shutterAngle', 'shutterPhase', 'samplesPerFrame', 'fps'];
    const shuttered = n => {                             // the component's own acceptance test, so the two never disagree
      if (!shutter || !window.attachMotionBlur || !n || !n.hasAttribute || !n.hasAttribute('data-hf-motion-blur')) return false;
      const v = n.getAttribute('data-hf-motion-blur').trim(); if (v === '') return true;
      let p; try { p = JSON.parse(v); } catch (e) { return false; }
      return !!p && typeof p === 'object' && !Array.isArray(p) &&
        Object.keys(p).every(k => MB_KEYS.includes(k) && typeof p[k] === 'number' && Number.isFinite(p[k]));
    };
    const F = 1 / fps;                                   // one TIMELINE frame
    const SF = stepFps ? 1 / stepFps : F;                // one RENDERED step (83 ms at 12 fps)
    const q = t => stepFps ? Math.round(t * stepFps) / stepFps : t;   // snap a time to the step grid
    const tl = gsap.timeline({paused: true});

    // ── the scale family (OBJECTS: props, chips, icons, the mascot, flow nodes) ──
    const pop = (el, at, extra) => {
      const first = Object.assign({opacity: 1, scale: REG.pop.from}, extra || {});
      smear(el, at, 'xy', 0, REG.pop.frames * F, 'scale');                 // an isotropic sigma of REG.smear.scale px, decaying over the pop's frames
      if (stepFps) {                                     // 0.90 → 1.10 → 1.00, one 83 ms state each
        const a = q(at); tl.set(el, first, a); tl.set(el, {scale: REG.pop.over}, a + SF); tl.set(el, {scale: 1}, a + 2 * SF); return;
      }
      tl.set(el, first, at);
      tl.to(el, {scale: REG.pop.over, duration: REG.pop.frames * F, ease: REG.pop.ease}, at);
      // the settle is a ONE-FRAME tween, never a set: on whole frames it reads exactly as the old set(1.00) on frame 4
      // (1.10 on frame 3, 1.00 on frame 4), but under MBLUR's sub-frame shutter a set was a jump inside the shutter and
      // the render averaged both scales into a DOUBLE IMAGE of the whole element (f3's thermometer, 2026-09-27)
      tl.to(el, {scale: 1, duration: F, ease: 'none'}, at + REG.pop.frames * F);
    };
    const slam = (el, at) => {
      smear(el, at, 'xy', 0, REG.slam.frames * F, 'scale');
      if (stepFps) { const a = q(at); REG.slamSteps.forEach((s, i) => tl.set(el, i ? {scale: s} : {opacity: 1, scale: s}, a + i * SF)); return; }
      tl.set(el, {opacity: 1, scale: REG.slam.from}, at);
      tl.to(el, {scale: 1, duration: REG.slam.frames * F, ease: REG.slam.ease}, at);
    };
    const flash = (el, at) => {
      if (stepFps) throw new Error('HF: flash is banned on a 12 fps graphic (its single-frame gaps vanish), use pop or slam');
      for (const [f, op] of REG.flash) tl.set(el, {opacity: op}, at + f * F);
    };

    // ── the nudge family (TYPE, cards, panels), opacity CUTS in, the travel is the entrance ──
    const riseIn = (el, at, dist = REG.rise.in.dist, dur = REG.rise.in.dur, ease = REG.rise.in.ease) => {
      tl.set(el, {opacity: 1}, at); tl.fromTo(el, {y: dist}, {y: 0, duration: dur, ease}, at);
    };
    const riseOut = (el, at, dist = REG.rise.out.dist) => {   // RELATIVE: rises from wherever it rests
      tl.to(el, {y: '-=' + dist, opacity: 0, duration: REG.rise.out.dur, ease: REG.rise.out.ease}, at);
    };
    // the standard tail: riseOut landing two frames before DUR, hard-kill on the last frame
    const exit = (el, at) => {
      const t = at === undefined ? DUR - REG.rise.out.dur - 2 * F : at;
      riseOut(el, t); tl.set(el, {opacity: 0}, DUR - F);
    };

    // ── THE SMEAR: a directional blur that rides every slide, sized from its speed (2026-09-10: "motion blur really
    // helps on the slides and large movements"). The renderer's 240 fps cap leaves an 8x supersample stepping 16 px at 4K on a
    // frame-wide slide, so the element itself carries an SVG feGaussianBlur along the slide's axis whose stdDeviation follows
    // the velocity profile (a slideIn's power2.out decays linearly from its peak; a slideOut's power3.inOut peaks mid-way).
    // Tweened as an SVG ATTRIBUTE, never a CSS filter string (the g10 blink). One filter element per call. REG.smear.k = 0 turns it off.
    let smearN = 0;
    const smear = (el, at, ax, dist, dur, shape) => {
      const k = REG.smear.k; if (!k || stepFps) return;                    // never on a 12 fps graphic: that look steps, it does not blur (creative-moves 4c; you tried it 2026-09-10 and undid it)
      el = (typeof el === 'string' ? [...document.querySelectorAll(el)] : [el]).filter(n => !shuttered(n));   // one blur, not two
      if (!el.length) return;
      const node = el[0];
      const base = node ? getComputedStyle(node).filter : 'none';
      const keep = (base && base !== 'none') ? base + ' ' : '';            // the element's own filter stays under the smear
      const peak = (shape === 'out' ? 3 : 2) * dist / dur / fps;          // px per frame at the fastest point of the ease
      const S = shape === 'scale' ? REG.smear.scale : Math.min(REG.smear.max, k * peak);
      const NS = 'http://www.w3.org/2000/svg';
      let svg = document.getElementById('hf-mb-defs');
      if (!svg) { svg = document.createElementNS(NS, 'svg'); svg.id = 'hf-mb-defs'; svg.setAttribute('width', '0'); svg.setAttribute('height', '0');
        svg.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden'; document.body.appendChild(svg); }
      const id = 'hf-mb-' + (smearN++);
      const f = document.createElementNS(NS, 'filter'); f.id = id;
      for (const [k_, v] of [['x', '-25%'], ['y', '-25%'], ['width', '150%'], ['height', '150%'], ['color-interpolation-filters', 'sRGB']]) f.setAttribute(k_, v);
      const g = document.createElementNS(NS, 'feGaussianBlur'); g.setAttribute('stdDeviation', '0 0'); f.appendChild(g); svg.appendChild(f);
      const sd = v => ax === 'x' ? v.toFixed(2) + ' 0' : ax === 'y' ? '0 ' + v.toFixed(2) : v.toFixed(2) + ' ' + v.toFixed(2);
      tl.set(el, {filter: keep + 'url(#' + id + ')'}, at);
      if (shape === 'scale') {                                              // a pop / slam: a small isotropic blur that decays as the move settles
        tl.fromTo(g, {attr: {stdDeviation: sd(S)}}, {attr: {stdDeviation: sd(0)}, duration: dur, ease: 'power2.out'}, at);
      } else if (shape === 'out') {                                                // 0 → S → 0 around the midpoint
        tl.fromTo(g, {attr: {stdDeviation: sd(0)}}, {attr: {stdDeviation: sd(S)}, duration: dur / 2, ease: 'power1.in'}, at);
        tl.to(g, {attr: {stdDeviation: sd(0)}, duration: dur / 2, ease: 'power1.out'}, at + dur / 2);
      } else {                                                              // S → 0, linearly (power2.out's speed decays linearly)
        tl.fromTo(g, {attr: {stdDeviation: sd(S)}}, {attr: {stdDeviation: sd(0)}, duration: dur, ease: 'none'}, at);
      }
      tl.set(el, {filter: base}, at + dur + F);                             // sharp again once it has landed / left — the element's own filter restored, never clobbered
    };

    // ── the slide family (OFF SCREEN only) — every slide carries THE SMEAR ──
    // A slide travels until the element's WHOLE SUBTREE clears the frame, never a bare frame width: the g16 filmstrip
    // (2800 px wide, 480 px past the frame's right edge) hung at the left edge for five frames after its scene had
    // "left" on a 1920 px slide, and was hidden by an opacity cut instead (2026-09-10). Measured from offsets (transforms
    // ignored, so a slideIn's immediate from-state cannot skew it); an explicit dist still wins.
    const extent = (el, side) => {
      const els = typeof el === 'string' ? document.querySelectorAll(el) : [el];
      let L = 0, R = FRAME.x, T = 0, B = FRAME.y;
      const off = (c, root) => { let x = 0, y = 0, e = c;            // offsetLeft is measured from offsetParent, not the DOM parent
        while (e && e !== root) { x += e.offsetLeft; y += e.offsetTop; e = e.offsetParent; } return [x, y]; };
      for (const root of els) {
        R = Math.max(R, root.offsetWidth || 0); B = Math.max(B, root.offsetHeight || 0);   // the root's OWN size counts (L/T already seed at its origin)
        const walk = (n) => {
          for (const c of n.children) {
            if (!(c instanceof HTMLElement)) continue;
            const [x, y] = off(c, root);
            L = Math.min(L, x); R = Math.max(R, x + c.offsetWidth); T = Math.min(T, y); B = Math.max(B, y + c.offsetHeight);
            walk(c);
          }
        };
        walk(root);
      }
      return side === 'left' ? R : side === 'right' ? FRAME.x - L : side === 'top' ? B : FRAME.y - T;
    };
    const slideIn = (el, at, from, dist) => { const [ax, sg] = AXIS[from], c = REG.slide.in, d = dist || extent(el, from);
      tl.set(el, {opacity: 1}, at); tl.fromTo(el, {[ax]: sg * d}, {[ax]: 0, duration: c.dur, ease: c.ease}, at); smear(el, at, ax, d, c.dur, 'in'); };
    const slideOut = (el, at, to, dist) => { const [ax, sg] = AXIS[to], c = REG.slide.out, d = dist || extent(el, to);
      tl.to(el, {[ax]: sg * d, duration: c.dur, ease: c.ease}, at); smear(el, at, ax, d, c.dur, 'out'); };

    // ── THE CAMERA: a full-screen's scene wrapper moves over its span (creative-moves.md move 2, A FULL-SCREEN IS A SCENE) ──
    // camera(sel, t0, t1, from, to): from/to are {scale, x, y} (px, scale factor), power1.inOut, on the SCENE wrapper
    // (its own element, inside the float wrapper, never the float wrapper itself: GSAP gives x/y to the last tween added).
    // Presets: REG.camera.push = 1.00 -> 1.05 over the span; REG.camera.pan = 24 px of x. The clone layers take it too.
    const camera = (sel, t0, t1, from, to) => {
      const f = Object.assign({scale: 1, x: 0, y: 0, transformOrigin: '50% 50%'}, from || {});
      const t = Object.assign({}, to || {}, {duration: Math.max(0.05, t1 - t0), ease: 'power1.inOut'});
      tl.fromTo(sel, f, t, t0);
    };

    // ── THE FLOAT: hold life, on a position:absolute;inset:0 WRAPPER, 0 → DUR, every time ──
    const float = (target, t0, t1, preset) => {
      const p = REG.float[preset]; if (!p) throw new Error('HF: float preset must be subtle or medium');
      const [AX, AY, PX, PY] = p;
      const leg = (prop, A, per) => { let cur = 0, out = true;
        for (let t = t0; t < t1 - 0.02; t += per) { const rem = Math.min(per, t1 - t);
          cur += ((out ? A : 0) - cur) * (rem / per);            // the last leg scales with the time left: never a truncated excursion
          tl.to(target, {[prop]: cur, duration: rem, ease: 'sine.inOut'}, t); out = !out; } };
      leg('x', AX, PX); leg('y', -AY, PY);
    };

    // ── the arrow: head COMPUTED from the path's end tangent, sized off stroke-width ──
    const DRAW = REG.draw;
    const arrow = (sel) => {                              // call ONCE, after any bloom clone
      for (const svg of document.querySelectorAll(sel)) {
        const p = svg.querySelector('path'), head = svg.querySelector('.head');
        const L = p.getTotalLength(); const sw = parseFloat(getComputedStyle(p).strokeWidth) || 10;
        const p1 = p.getPointAtLength(L), p0 = p.getPointAtLength(Math.max(0, L - 8));
        let tx = p1.x - p0.x, ty = p1.y - p0.y; const n = Math.hypot(tx, ty) || 1; tx /= n; ty /= n;
        const px = -ty, py = tx, A = REG.arrow;
        const tip = {x: p1.x + tx * A.len * sw, y: p1.y + ty * A.len * sw};
        const b = {x: p1.x - tx * A.sink * sw, y: p1.y - ty * A.sink * sw}; const h = A.half * sw;
        if (head) head.setAttribute('points', [[tip.x, tip.y], [b.x + px * h, b.y + py * h], [b.x - px * h, b.y - py * h]]
          .map(c => c[0].toFixed(1) + ',' + c[1].toFixed(1)).join(' '));
        p.style.strokeDasharray = L; p.style.strokeDashoffset = L;
        if (head) head.style.opacity = 0;                 // hidden until drawOn lands it on the last frame: the group's opacity 0 hid it only until `at`, so the head used to appear BEFORE the line (your-job, 2026-09-11)
      }
    };
    const drawOn = (sel, at) => {
      tl.set(sel, {opacity: 1}, at);
      tl.to(sel + ' path', {strokeDashoffset: 0, duration: DRAW * F, ease: 'power2.out'}, at);
      tl.set(sel + ' .head', {opacity: 1}, at + (DRAW - 1) * F);
    };

    // ── content reveals: DISCRETE states on the beat grid, zero frame PINNED, never onUpdate ──
    const BEAT = stepFps ? SF : 2 * F;                   // one ~12 fps beat
    const countUp = (sel, at, dur, to, fmt, from, ease) => {
      fmt = fmt || (v => String(v)); from = from || 0; ease = ease || (p => 1 - Math.pow(1 - p, 3));
      const N = Math.max(1, Math.round(dur / BEAT));
      tl.set(sel, {innerText: fmt(from)}, 0);            // PIN THE ZERO FRAME
      for (let i = 1; i <= N; i++) tl.set(sel, {innerText: fmt(Math.round(from + (to - from) * ease(i / N)))}, at + i * BEAT);
      tl.set(sel, {innerText: fmt(to)}, at + N * BEAT);
      return at + N * BEAT;
    };
    // reveal(sel, at, text): bursts of 2-6 words, one beat each, DOUBLE on punctuation; returns the
    // time the text is complete, so the caller budgets the hold backwards (creative-moves.md 4d).
    const reveal = (sel, at, text, opts) => {
      opts = opts || {}; const words = text.split(' '); const sizes = opts.pattern || REG.burst;
      tl.set(sel, {innerText: ''}, 0);                   // PIN THE ZERO FRAME
      let i = 0, t = at, k = 0;
      while (i < words.length) {
        i = Math.min(words.length, i + sizes[k % sizes.length]); k++;
        const shown = words.slice(0, i).join(' ');
        tl.set(sel, {innerText: shown}, t);
        t += /[.,;:!?]$/.test(shown) ? 2 * BEAT : BEAT;
      }
      return t;
    };

    const finish = () => { tl.set({}, {}, DUR); tl.progress(0); window.__timelines = window.__timelines || {}; window.__timelines.main = tl; };

    return {tl, F, SF, DUR, BEAT, REG, pop, slam, flash, riseIn, riseOut, exit, slideIn, slideOut, float, camera, arrow, drawOn, DRAW, countUp, reveal, finish};
  }
  return {init, REG};
})();
