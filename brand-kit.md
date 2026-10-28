# 🎨 Brand Kit — make this editor yours

This is the **one file you personalize.** Everything the editor produces — caption voice, on-screen
copy, the signature graphics look — reads from what you put here. Fill in the blanks, then tell Claude
**"apply my brand kit"** and it pushes these values into the presets for you (the exact map is in
**Part B** at the bottom, if you'd rather do it by hand or want to know precisely what changes).

**This is optional, and it can wait.** The editor works out of the box with a neutral bundled look
(Inter fonts, a generic starter palette); fill this in whenever you want captions and graphics to
sound and look like *you*, on day one or after your tenth video.

---

# Part A — fill this in

## 1. Identity

- **Name / creator:** `<<YOUR_NAME>>`
- **Niche (one line):** `<<YOUR_NICHE>>`  — e.g. "AI automations", "fitness for busy parents", "indie game dev"
- **Handles:**
  - Instagram: `<<YOUR_IG_HANDLE>>`
  - YouTube: `<<YOUR_YT_HANDLE>>`  ·  channel ID: `<<YOUR_YT_CHANNEL_ID>>`
  - TikTok: `<<YOUR_TIKTOK_HANDLE>>`

## 2. Voice & tone (drives caption + hook copy)

How your captions should *sound* — punchy? formal? lowercase-casual? slang-heavy? One or two sentences.
Burn-in captions and on-screen copy are written to match this.

```
<<YOUR_VOICE_TONE>>
```

## 3. Brand colors

**Short-form (the Talking Head Explainer):** its palette lives in
`presets/instagram/talking-head-explainer/graphics.md` § 10 (Palette and colour roles) and § Values; the caption
colours live in `presets/instagram/talking-head-explainer/captions-style.md`. Colour there carries MEANING, so only
the brand roles are yours to swap:

| Role | Token | Default | Yours |
|------|-------|---------|-------|
| **Hero accent** (sent, the solution, the action button) | `ROYAL` | `#1e48ff` | `<<HEX_HERO>>` |
| **Live accent** (waveforms, pulse rings, a live line) | `SKY` | `#57c9f0` | `<<HEX_LIVE_OR_BLANK>>` |

Green (success), red (error), the phone's own call-button colours and every captured screen keep their colours:
they are meaning, not brand.

**Long-form liquid-glass panels** (`presets/youtube/liquid-glass/liquid-glass-style.md`, opt-in by name): six colors
as hex. The roles map 1:1 to that preset's color tokens — pick a color for each role. (The defaults shown are the
starter palette; replace with yours.)

| Role | Token in presets | Default | Yours |
|------|------------------|---------|-------|
| **Background base** (the canvas) | `--sky` | `#ddf4ff` | `<<HEX_BACKGROUND>>` |
| **Grid lines** (thin texture) | `--grid` | `#74dff6` | `<<HEX_GRID>>` |
| **Hero accent** (the ONE loud color) | `--royal` | `#1e48ff` | `<<HEX_HERO>>` |
| **Secondary accent** (gradients/decorative) | `--peri` | `#879cff` | `<<HEX_SECONDARY>>` |
| **Title text** (dark, primary copy) | `--ink` | `#0a1a4d` | `<<HEX_TITLE>>` |
| **Muted text** (subheads/labels) | `--slate` | `#5e687d` | `<<HEX_MUTED>>` |

> Tip: keep **Background light** and **Title text dark** (or vice-versa) so copy stays readable, and let
> **Hero accent** be your one bold brand color. The graphics use it sparingly for emphasis.

## 4. Fonts

- **Display font** (titles/graphics): `<<DISPLAY_FONT>>` — default is **Inter**, bundled in `assets/fonts/`
  (nothing to install). To use your own, drop the `.otf`/`.ttf` (with **Black/Bold/Regular** weights) into
  `assets/fonts/` and name it here. *(Prefer Apple's SF Pro Display? Install from https://developer.apple.com/fonts.)*
- **Caption font** (burn-in, the Talking Head Explainer): a bold monospace in caps, SF Mono on macOS and a named
  system mono elsewhere (`captions.py` picks it and says which). Swap only if you want a different caption identity.

## 5. Hook style (TikTok/raw front card)

- **Default hook text** (leave blank to require it per-job): `<<YOUR_HOOK_TEXT_OR_BLANK>>`
- The hook card leaves at the end of the first spoken sentence (or where the plan's hook cell says): nothing
  to fill in for it.

## 6. Brand / product wordlist (transcript corrections)

WhisperX sometimes mishears product or brand names. List yours as `heard → correct` and the fix is applied
once, to the canonical transcript, at pipeline step 2 — so graphics copy, captions and long-form all
inherit it. Worth filling in even if you only make long-form, which never gets a burned-in caption. **Keys must be a single word** — matching runs one word at a time, so a multi-word key
(like "chat gpt") can never fire. List the one-word mishears WhisperX actually produces.

```
<<example: "chatgbt" → "ChatGPT", "utube" → "YouTube", "<one-word mishear>" → "<Correct Casing>">>
```

---

# Part B — what "apply my brand kit" changes (the exact map)

Tell Claude **"apply my brand kit"** and it does all of this. This section is the precise spec it follows —
read it only if you want to verify or do it by hand.

### Colors → the Talking Head Explainer: `presets/instagram/talking-head-explainer/graphics.md`
Replace `ROYAL` (and `SKY` if you gave one) in § 10 and § Values, and the same hex in `kit/engine.py` and
`kit/components.py`, which mirror the Values block. Leave every other token alone: it carries meaning.

### Colors → `presets/youtube/liquid-glass/liquid-glass-style.md`
Replace each **default hex with yours, everywhere it appears** in the file. Most colors live only in the
`--token` table; **four** of them *also* appear inline in the background / glass CSS as an **`rgba(R,G,B,a)`**
triple (same R,G,B numbers, varying alpha). For those four, replace the **R,G,B number group** too (leave
the alpha after it alone):

| Your color | Token | Old hex | Also inline as `rgba()` — replace the R,G,B group |
|------------|-------|---------|---------------------------------------------------|
| Background | `--sky`   | `#ddf4ff` | — (hex / token only, one place) |
| Grid       | `--grid`  | `#74dff6` | `rgba(116,223,246, …)` |
| Hero       | `--royal` | `#1e48ff` | `rgba(30,72,255, …)` |
| Secondary  | `--peri`  | `#879cff` | `rgba(135,156,255, …)` |
| Title ink  | `--ink`   | `#0a1a4d` | `rgba(10,26,77, …)` |
| Muted      | `--slate` | `#5e687d` | — (hex / token only, one place) |

(Find-and-replace each old hex; for the four with an `rgba()` form, also swap its `R,G,B` numbers — the
alpha after them stays. Claude does this in one pass.)

### Colors → `presets/youtube/default/default-overlay-style.md` (the long-form DEFAULT graphics tier)
The everyday long-form overlay cards — what a plain "do a graphics pass" builds on a long-form job — have their **own**
token table in this file (dark navy panels). "Apply my brand kit" maps your **Hero** color onto its `--royal` accent and
your **Secondary** onto its `--sky` wherever they appear; the navy surface tokens (`--bg`, `--line`) stay
unless you ask for a different panel color. Don't skip them: this is the look most videos ship with.

### Fonts → the graphics presets
If you swapped the display font: in `presets/instagram/talking-head-explainer/graphics.md`,
`presets/instagram/talking-head-explainer/kit/engine.py`, `presets/youtube/liquid-glass/liquid-glass-style.md` and
`presets/youtube/default/default-overlay-style.md`, replace the `Inter-{Black,Bold,Regular}.otf` filenames (and the
"Inter" name) with your font's files — which must live in `assets/fonts/`. Two builders set their font in code, so
change them too: `presets/youtube/default/titles/build.py` (the long-form section title cards: its `FONT` constant
AND the `'Inter'` family name in its `@font-face` and `font-family` lines) and `presets/tiktok/raw/build.py` (the
TikTok/raw captions and hook card: `FONT_PATH` and `FALLBACK_FONT`). Keeping Inter (or installing SF Pro)? Nothing to change.

### Identity → `my-rules.md` (a Brand identity block) + voice everywhere
Your name, niche, handles, channel ID, and voice/tone go into a **Brand identity** block at the top of
`my-rules.md`, which Claude reads every session and no update ever changes, so a new version never
conflicts with it. An older version wrote them into `CLAUDE.md`'s Brand Kit section: move any such
lines into `my-rules.md` and delete them from `CLAUDE.md`. The voice/tone is what captions and
on-screen copy are written to match.

### Wordlist → `transcript-corrections.json` (repo root)
Your `heard → correct` pairs go under `"auto"` (applied silently to the canonical transcript at step 2, so
every downstream format inherits them). Ambiguous words go in `"flag"` (printed for you to eyeball each run).

### Hook → `presets/tiktok/raw/build.py`
Your default hook text → `DEFAULT_HOOK_TEXT`. The card's end is timed, not a word: the first sentence break
of the spoken hook, or `--hook-end` from the plan's hook cell, so there is nothing else to swap.

### Logos → `assets/logos/`
Any brand marks you want available to graphics.

### Verify
After applying, render a quick test — e.g. ask Claude to **"make a 5-second title card in my brand style"**
(exercises your fonts in `assets/fonts/` and your hero color) or just run
one real clip through. Check that titles use your font and your hero color shows up on the emphasis word.
Run `./check-setup.sh` to confirm fonts are found.
