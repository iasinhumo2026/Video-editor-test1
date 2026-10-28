# assets/sfx/ — the SFX library

This folder is the sound-effects library pipeline step 6 (SFX) reaches for: whooshes, pops,
clicks, risers, impacts and word ticks laid under graphics and cuts.

It ships the library the presets were tuned on, so a fresh install can run the entire edit
start to finish with nothing else to download. The map from motion event to
sound class to file lives in the preset's `sfx.json` (`presets/youtube/default/sfx.json`, and the
Talking Head Explainer's own `presets/instagram/talking-head-explainer/sfx.json`); `uv run
workflows/sfx-plan.py projects/<job>` reads the one the plan's `preset` names and writes the cut
sheet, and a file the map names but this folder lacks is a ⚠ in that cut sheet, never a silent
skip.

To use your own sounds, drop `.wav`/`.mp3`/`.aiff` clips in here and point the classes in
`sfx.json` at them (descriptive filenames help: "whoosh-soft.wav" beats "sfx_014.wav").
