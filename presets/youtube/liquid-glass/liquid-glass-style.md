<!-- ⚠️  BRAND VALUES BELOW ARE PLACEHOLDERS — replace with your own.
     Fill in brand-kit.md and tell Claude "apply my brand kit", or edit the values here directly. -->

# Liquid-Glass — the takeover-panel look (opt-in by name)

**It is NOT the default.** A long-form YouTube job runs [`presets/youtube/default/`](../default/README.md);
this look ships only when you ask for it by name. The "clean liquid-glass displays + visuals that pop up
from where I'm pointing" treatment: the locked brand constants below plus a glass surface language built
for a horizontal talking-head. Self-contained — everything this look needs is in this doc.
**Philosophy:** brand CONSTANTS are locked; each graphic is designed fresh (vary side, scale, template, motion
— no two stamped alike). Locked 2026-06-24 (`your-job` intro).

Build mechanics (how parts are built/rendered/placed) live in the `graphics-build` skill. This doc
is the **visual language**.

---

## 🔒 CONSTANTS — never change these

### Colors — the locked brand tokens
`--sky #ddf4ff` · `--grid #74dff6` · `--royal #1e48ff` (hero accent) · `--peri #879cff` (secondary) ·
`--ink #0a1a4d` (title text) · `--slate #5e687d` (muted/labels). Royal is the one hero accent.

### Fonts — Inter
`Inter-{Black,Bold,Regular}.otf` → `@font-face` into the hf project (headless render needs the file).
Titles = Black, mixed case, `letter-spacing:-2px`, tight line-height. Labels/eyebrows = Bold (uppercase OK for
small labels only). Body/subhead = Regular, `--slate`.

### THE glass surface — the defining element
Frosted **bright** translucent white (NOT translucent-dark — dark glass is unreadable over dark studio footage,
and it must read on its OWN fill so isolated overlay renders composite identically; see the `graphics-build` render gotchas):
```css
.glass{background:linear-gradient(155deg,rgba(255,255,255,0.88),rgba(238,244,255,0.74));
  backdrop-filter:blur(22px) saturate(160%);-webkit-backdrop-filter:blur(22px) saturate(160%);
  border:1.5px solid rgba(255,255,255,0.85);border-radius:26px;
  box-shadow:0 26px 60px rgba(10,26,77,0.34),inset 0 2px 0 rgba(255,255,255,0.95),inset 0 -1px 0 rgba(135,156,255,0.3);}
.glass.royal{border-color:rgba(30,72,255,0.35);                       /* payoff/hero panels */
  box-shadow:0 26px 60px rgba(30,72,255,0.34),0 0 0 1.5px rgba(30,72,255,0.22),inset 0 2px 0 rgba(255,255,255,0.95);}
```
Add a `.sheen` sweep on hero panels (diagonal white gradient swiped across). Every panel is `.glass`.

### Background — "spotlight grid" (brighter long-form variant of Signature A)
`--sky` base + thin `--grid` lines (120px cells) + a strong soft-white radial glow behind the focal area.
Revealed full-frame behind the face during the **takeover** (below).

### Frame & safe zones — 16:9, 1920×1080, NO reframe
Source is already 16:9 — never reframe to 9:16. Long-form has no platform safe bands: never cover your face
or important on-screen content, keep essential copy off the very edge of the frame (~100px breathing room),
and keep the **outro right side + bottom band** clear for YouTube end-screen cards.

---

## 🎨 DESIGN TOOLBOX — compose, don't repeat

**Pop from where you point.** The signature beat: a glass panel slides in from the **side your hand gestures to**
(left or right), holds while you references it, exits before the next line. Slide from `x:±60`, `power3.out`;
exit `opacity:0` + hard-kill. Default to **visual** panels (bars/diagram/icons/checks), not text walls
(reserve text cards for hook/punchline).

**Template vocabulary** (each a glass panel — mix per the words): title-card · stat (big number + label) ·
checklist (royal check rows) · ranked list · icon-row · screenshot-card · diagram/flow · **engine/pipeline**
(raw → Claude → finished, nodes + arrows) · **system-map rail** · bar-chart card · hook badge · payoff card (`.glass.royal` + sheen).

**System-map rail** (the "show the whole system" flex — built for `your-job` on the
"most cracked, dialed-in editing system" line): a vertical stack of numbered glass step-rows (number chip +
step name + tiny sub) that stamp in fast top→bottom (`back.out`, `stagger:0.12`). Reads as a complete pipeline,
not a list. Flag the steps that branch/matter with a **royal** number chip + a small uppercase pill tag (e.g.
graphics & captions tagged "by format"); pop those royal chips after the rows land. Pair with a quiet footnote
for an optional side path. Pin it in the **takeover** (face cards right, rail fills the left). It naturally reads
raw-in (step 1) → finished-out (last step), so it can double for a "drop in footage, Claude does the rest" beat.

**The two footage moves** (the camera "takes over" — both are FOOTAGE, keep them out of the browser, see below):
- **Takeover / reframe** — the hero move: the face resizes + slides to a 4:5 card on one side while the
  spotlight-grid background **takes over the full frame** and full-screen graphics (title + pipeline, or the
  **system-map rail** above) build in behind it; then the face un-crops back to full frame, sweeping OVER
  (covering) the graphics on restore.
- **Push-in zoom** — a gentle ~12% punch-in on the face for emphasis on a punchy line; eased to scale 1.0 at
  both ends so there's no pop.

**Motion = entrance, deterministic, seek-safe.** ONE paused GSAP timeline (`window.__timelines["main"]`), absolute
times. Every clip hard-killed at its end boundary (`tl.set("#id",{opacity:0}, end)` or it POPS / lint-errors).
No `Math.random`. Let GSAP own transforms. Overlapping cross-fades → alternating `data-track-index`.

---

## 🏗️ How it's built — GENERATE the composition, don't hand-author

A long-form piece is ~20+ graphics — too many clips to hand-write. **A `build.py` is the single source of truth**
(CSS + per-graphic markup + per-graphic anim from ~10 templates) and emits the comps, rendered part by part.
The second pass is `edit build.py → re-render the one changed part → re-place it` (seconds: on the chat-only lane
`uv run lanes/chat-only/assemble.py projects/<job>`), never a full re-render. Layer kinds (overlay / ffseg / segment) and slice alignment are chat-only assemble mechanics — see [`../../../lanes/chat-only/incremental-graphics.md`](../../../lanes/chat-only/incremental-graphics.md).

## Reference implementation
No sample project ships — author `build.py` fresh under `projects/<job>/hf-graphics/` from the templates + the "How it's built" section above. Point it at your rough cut + `graphics-plan`, design the panels, render parts, assemble.

> ⚠️ Author `build.py` under `projects/<job>/hf-graphics/`, never `/tmp` (see the `graphics-build` skill, Stage 1).
