---
name: broll-own
description: "Places the creator's OWN B-roll as full-frame cutaways over the A-roll, on a preset built for it (its folder carries a broll.json; the shipped presets carry none, and this skill shows how to give a creator's own preset B-roll). Indexes any folder of their footage once (an external SSD is fine) into a cached library with a contact sheet per clip, proposes cutaway slots against the finished script at the preset's density, and writes the chosen clips as b-roll cells every lane places. Step 5. Real footage only, no AI generation. Triggers: use my b-roll, add my b-roll, here's my b-roll folder, b-roll from my SSD, b-roll from this drive, sprinkle some b-roll, put b-roll over the a-roll, index my b-roll, place b-roll from this folder, cutaways from my footage, give my preset b-roll, make a b-roll preset."
---

# broll-own: the creator's own footage, cut in over the A-roll

**Step 5, on a preset built for B-roll.** No shipped preset uses B-roll: long-form `youtube/default`, the Talking
Head Explainer and TikTok/raw carry their rhythm with graphics, layouts and captions (2026-10-14). This skill is
the know-how for a creator's OWN preset that does: they point at a folder of footage they shot ("him on the phone",
"him on the laptop", behind-the-scenes, finished work), and it turns that folder into a library Claude can search
cheaply, then places the right clip on the right line as a **full-frame cutaway**: the picture cuts to the B-roll, the
voice carries on underneath, the picture cuts back. It never generates footage.

**Only a preset whose folder holds a `broll.json` places B-roll** (§ Give a preset B-roll). `broll-place.py` refuses
any other preset, and says how to make one. Asked for B-roll on a job whose preset has none, say so in one line and
offer to give a preset of theirs B-roll; never add a `broll.json` to a shipped preset.

Two scripts carry it: `workflows/broll-index.py` (the library) and `workflows/broll-place.py` (the job).

## The prep that pays (a member's tip, 2026-10-13)

Pre-trim each clip to its best **2 to 8 seconds** and **name the file by what is on screen**: "pick like ... two to
eight seconds of B-roll that's like the best", "already name what's on the screen", because "it's going to like save
you time and tokens". A videographer's first and last seconds are the shaky ones, so the in-point defaults to the
middle of the clip. A file named `him on the phone with a client.mp4` is matched by its name and needs no description;
a camera's `C0001.MP4` has to be looked at first. Recommend this to a creator about to build a library, never require it.

## 1. Index the folder (once per library; re-run any time)

```bash
uv run workflows/broll-index.py "/Volumes/SSD/B-Roll" --job projects/<job>
```

It walks every subfolder, probes each video (length, rate, display size with a phone's rotation applied, audio, HDR),
writes a 4-frame contact sheet per clip and records the library in `projects/<job>/broll/library.json`.
**The library lives in `projects/_broll-library/<folder>-<hash>/`, never in the B-roll folder**: an external drive may be
read-only, the creator's folder stays clean, and one library serves every future job. A re-run probes only what is new
or changed (path, size, modified time); a clip renamed or moved inside the folder keeps its probe, sheet and
description. A first run over thousands of clips takes a while and is safe to stop and resume. Hidden files (a
drive's `._` files) are passed over; it reports anything not video (counted by extension), files ffmpeg cannot read
(BRAW, R3D: export H.264 or ProRes copies into the folder) and HDR clips (they are placed without tone mapping and look
washed out: export SDR copies).

**A drive that comes back under another name** (macOS `SSD 1`, a new Windows drive letter) is a new path: index it with
`--cache <the old library folder>`, which re-probes nothing (clips are keyed by their path inside the folder), then
re-run `apply` so the cells point at the new path.

## 2. Describe what the names do not say

```bash
uv run workflows/broll-index.py "/Volumes/SSD/B-Roll" --pages          # camera-named clips only; --all for every undescribed one
```

Each page image holds 6 clips, every row labelled `#n <id> <length> <path>`. Read each page and write one line per clip
into a JSON file, then merge it:

```bash
uv run workflows/broll-index.py "/Volumes/SSD/B-Roll" --describe projects/<job>/broll/descriptions.json
```

```json
{"c601396923": "man on a phone call at his desk, calling a client, side angle, daylight, landscape"}
```

A description is 6 to 15 words: the subject, the action, the setting and the framing, written with the nouns AND verbs
a script would use (phone, call, calling, client). An unknown id refuses the whole merge. A changed clip is described
again; a renamed one keeps its description.

## 3. Propose slots against the script

```bash
uv run workflows/broll-place.py projects/<job> propose                # the density in the preset's broll.json
uv run workflows/broll-place.py projects/<job> propose --every 5-10   # this job only: "one every 5 to 10 seconds"
```

It reads the canonical transcript (`outputs/<job>.transcript.json`), splits it into sentence beats and keeps every beat
where a cutaway fits: the preset's `len` long (2 to 8 s by default), starting 2 frames before its first word, ending
just after a word, never over the opening line (the hook stays on the face) or the closing line, never under or over a
graphic in `graphics-plan.json` (the caption layer is the one exception: it rides on top), inside the plan's
`graphics_scope`, and an edge within 8 frames of a V1 cut sits ON the cut. Each slot lists up to 5 candidate clips (their description or name shares the
line's words), and a subset is marked ★ at the density. A library of 150 clips or fewer is also printed whole. The
proposal lands in `projects/<job>/broll/own-proposal.json`.

## 4. Pick: the clip shows what the words say

The candidate list is a pre-filter; **the choice is Claude's, by what is on screen against what is said.** The literal
verb wins: when he says he was on the phone, the clip is him on the phone, not him at a laptop. Take each ★ slot, swap a
★ for a nearby slot when the match is clearly better there, and **drop a slot no clip fits**: a cutaway that does not
match the line is worse than the face. Avoid the same clip twice. Then write the picks:

```json
{"picks": [
  {"slot": "s4", "clip": "05f1bb2db0"},
  {"slot": "s9", "clip": "8ecf7f1bf6", "in": 1.5, "focus": [0.35, 0.5], "reason": "he says he typed the plan out"}
]}
```

`in` is the clip's in-point (default: the middle of the clip). `start` / `end` move the slot's edges. `focus` is where the
crop centres, `[x, y]` from 0 to 1 (default the middle), for a clip whose shape differs from the frame: a portrait clip
in a 16:9 frame keeps a third of its height, a landscape clip in a 9:16 frame keeps a third of its width.

## 5. Apply

```bash
uv run workflows/broll-place.py projects/<job> apply projects/<job>/broll/picks.json
uv run .claude/skills/graphics-plan/scripts/validate-plan.py projects/<job>
```

Every pick is held to the slot rules and to the density (no two cut-ins closer than its LO, at least 1.5 s of the
creator between two cutaways, never two overlapping, the clip long enough from its in-point); one failure refuses the
whole set and writes nothing. A passing set:

- becomes `kind: "b-roll"` cells in `graphics-plan.json` (ids `br1`, `br2` …, `region: "full-screen"`, `broll_source`
  naming the clip, its in-point and the focus), each inserted before the first later beat. A re-apply replaces the
  previous own B-roll cells, nothing else;
- gets a silent plain-cut row each in `hf-graphics/sfx-hand.json`: footage laid full-frame takes no cut-in sound
  (rows the creator added by hand stay);
- is rendered: each cell conformed to the job's frame and rate (scale to fill, crop at `focus`, no audio) as
  `hf-graphics/gfx/renders/<id>.mp4`, with a `<file>.render.json` record.

Then the lane places them with the other graphics (`graphics-build` § Stage 6): each is a full-screen row in
`hf-graphics/placement.json`. After a re-cut (`ripple-cut.py` re-times the cells) or a hand edit of a cell:

```bash
uv run workflows/broll-place.py projects/<job> render [--only br3]
```

An unchanged cell is skipped; a changed one renders to a NEW name (`br3-b.mp4`), never over a placed file. The source
drive has to be plugged in to render; once rendered, the job carries its own copies.

## Give a preset B-roll

A preset places B-roll when its folder holds a `broll.json`. Make it the creator's own preset, never a shipped one: a
new folder is theirs alone, and an update never touches it.

1. **Copy the preset it should look like, whole**, so every step still finds its docs and its `sfx.json`, and keep the
   base preset's name in the new one (some tools read the preset's family from its name):
   `cp -R presets/youtube/default presets/youtube/default-broll`.
2. **Add `broll.json`** to the new folder:

   ```json
   {"every": [20, 40], "len": [2, 8], "library": "/Volumes/SSD/B-Roll"}
   ```

   `every` (required) is the density: one cut-in every LO-HI seconds, in the creator's own words ("one every 10
   seconds" is 8-12, "a little every now and then" 20-40). `len` is how long a cutaway runs (default 2-8 s, the
   pre-trim range). `library` (optional) is the folder used when a job names none.
3. **Name it on the job**: `"preset": "presets/youtube/default-broll"` in `graphics-plan.json` (before there is a plan,
   `propose --preset presets/youtube/default-broll`).

The placer then proposes slots at that density and length, keeps at least 1.5 s of the creator between two cutaways,
and holds every pick to both at `apply`. `--every LO-HI` and `--len LO-HI` change them for one job; to keep a change,
write it into the `broll.json` ("lock it into my preset" means this file, the `bake-preset` route).

## Where it sits in step 5

On a B-roll preset, **place it first**: right after the beat sheet (`graphics-plan` Steps 1-2),
propose, pick and apply, then storyboard the graphics around the cutaways (no graphic overlaps one). A plan written
first works too: the slots fill the gaps it left, which on a dense long-form plan are few.

## What the lanes do with it

Every lane lays an own B-roll cell as a full-screen row on the graphics track, the way it lays a full-screen render.
Not yet proven live on any lane (`LANES.md`). Three consequences on every lane:

- **It sits above the grade, so it stays ungraded** (the same choice as generated b-roll, `presets/youtube/default/README.md`
  § Grade, One consequence to carry): grade the library before indexing it, or move a clip under the grade by hand.
- **Picture only**: the clip's own sound is never laid; the voice carries the cutaway.
- **No handles**: the render is exactly the slot. To slip a clip, change `in` in its cell and `render`.

## The client case

"Here's my B-roll folder, it's on my SSD": give the preset they edit with B-roll (§ Give a preset B-roll, the folder
as its `library`), index the folder with `--job`, describe what the names do not say, then place it on each job. The
library outlives the job, so the next video on that preset starts at step 3.
