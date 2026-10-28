# Vox-collage — the Premiere lane

**Scope: this look only.** The architecture below is the `your-job` intro as shipped
(2026-07-22) — a 4K sequence over 1080p raw, adjustment layers stacked ABOVE the graphics, a
film-feel effect chain, real grain footage on its own track. It is the vox-collage look's timeline,
and it is **opt-in by name** exactly like the rest of this preset.

**It is NOT the default.** A long-form YouTube job runs `presets/youtube/default/`, whose track
map and grade placement are different on purpose:

| | vox-collage (here) | youtube/default |
|---|---|---|
| Sequence | 4K 3840×2160 over 1080p raw, everything at Motion Scale 200 | source resolution, every clip at Scale 100 |
| Track map | V1 footage / V2 graphics / V3 composite helpers / V4 adjustment layers / V5 grain | V1 footage / **V2 grade** / V3 graphics / V4 accents / V5 spare |
| The grade | on V4, **above** the graphics — the Lumetri grades the overlays too | on V2, **underneath** the graphics — footage only |
| When it runs | after the graphics, as part of the finishing stack | **pipeline step 4, BEFORE the graphics pass** |
| Grade scope | per-section Lumetri, one adjustment layer per section | one layer spanning the timeline |
| Film-feel chain | Transform wiggle + VR Glow + Lens Distortion + VR CA | none |
| Grain | real grain footage on V5 across everything | baked per full-screen graphic at render time |

If you are not deliberately building the vox-collage look, close this file and read
[`presets/youtube/default/README.md`](../default/README.md).

**Everything universal has moved out.** The keyframe and effect laws, the graphics clip lifecycle,
generated-b-roll placement and the QA loop are lane-agnostic Premiere mechanics and now live in the
**`premiere-pro` skill** (Notes → "Graphics on the timeline"). This file carries only what is
specific to this look. Engine mechanics and API gotchas: the same skill. The part-split render SOP:
the `graphics-build` skill.

## The track stack

4K 3840×2160 @ 23.976 sequence over 1080p raw footage — the timeline is 4K so 1080p-rendered
graphics can be scaled crisp, and the raw rides at Motion Scale 200 (punch-ins = nudge scale,
e.g. 210).

| Track | Role | Notes |
|---|---|---|
| V1 | Footage: EDL-replayed cuts | every cut a real edit point; scale 200 base, per-section punch-ins allowed; special composites get NESTED down to one V1 clip (see sandwich) |
| V2 | Graphics clips | ProRes 4444 alpha `.mov` from `hf-graphics`, butt-joined at EDL cut times, scale 200 |
| V3 | Composite helpers (talent cutouts etc.) | empty once a section is nested |
| V4 | Adjustment layers | film-feel treatment + per-section Lumetri grades (separate layers per section) |
| V5 | Grain overlay | real grain footage (`heavygrain`) spanning everything, split at section bounds |
| A1 | Voice (rides with the EDL replay) | untouchable — the splice chain already polished it |
| A2 | Music bed (+ occasional head SFX) | bed starts where graphics take over |
| A3–A5 | SFX rails, hand-designed on the reference job | every graphic beat gets sound: stamps→pops, slides→whooshes, paint X's→scissors/markers, land moments→impacts/dings/bells. Library: `assets/sfx/` (the bundled SFX library, repo copy) |

**When re-timing or swapping a graphic, check A3–A5 in that window** — SFX are aligned to graphic
beats and re-cut graphics orphan them silently. Surface affected SFX clips to you rather than
moving your sound design unasked. (This warning is universal; it is repeated in the `premiere-pro`
skill for jobs that never touch this file.)

## The behind-talent sandwich → nest

Text/graphics BEHIND you (e.g. the cold-open "WHAT YOU'RE WATCHING / RIGHT NOW"):

1. V1 = the raw clip (background), V2 = alpha text comp timed to measured word onsets, V3 = the
   same raw clip again with the subject cut out — the mask trick: **Crop effect at Left=100 (wipes the
   frame) restricted by a mask over the talent** (the editor draws/tracks it, often with the AI masking
   — not visible to scripting).
2. the editor then **nests** the three tracks into one V1 clip so adjustment layers + grain still stack
   above and the whole section can take a single Transform (zoom keys on the nest).

⚠️ The Premiere 26.x preview-file bug this technique surfaces is an ENGINE trap, not a look
choice, so it lives in the `premiere-pro` skill Notes as well: rendered preview files drop
AI-masked layers, green-bar playback lies, yellow is truth.

## The finishing stack (what ships on top of the graphics)

⚠️ **This whole section is the inverse of the default preset's grade** — here the treatment sits
ABOVE the graphics and colours them too. That is the vox look. Do not carry it to a
`youtube/default` job.

- **Film-feel adjustment layer** on **V4**, spanning the graphics section. The five effects, their
  order and every dialled value live in [`vox-collage-style.md`](vox-collage-style.md) § The
  homogenize pass — read them there.
- **Baking the Transform wiggle** (the only part of that stack that is Premiere work): 489 Position
  keys on twos across the layer, random-walk ±5px x / ±4px y at 4K from an LCG seed so a re-bake is
  byte-identical. Uniform Scale OFF, Scale Height/Width 101 to hide the shifted edges. Do **not**
  reach for the clip's intrinsic Motion instead: on an adjustment layer it is inert on the image.
- **Per-section Lumetri** on separate adjustment layers (one per section, split at section bounds)
  — your grade, don't touch.
- **Grain overlay on V5** across everything — motion-craft principle 3/8 done with real grain
  footage instead of per-clip ffmpeg.

## Generated b-roll, this lane's numbers

The placement mechanics are universal (`premiere-pro` skill). What is vox-specific: a 1080p
`AI b-roll` clip on this 4K timeline needs **scale 200**, and clips get homogenized per
[`motion-craft.md`](motion-craft.md) principle 8 — which, like everything else in that file, is
this look's craft layer and nothing else's.
