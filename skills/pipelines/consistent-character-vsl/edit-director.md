# Edit Director — Consistent-Character VSL Pipeline

## When to Use

After the assets gate. You turn the approved assets into concrete
`edit_decisions`: the cut list, narration/music mix, subtitles, and overlays —
the EDL that compose renders.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifacts | `asset_manifest` (approved) | asset ids, paths, durations |
| Artifact | `proposal_packet` | the locked `render_runtime` + music decision |
| Schema | `schemas/artifacts/edit_decisions.schema.json` | canonical output |
| Tools | `silence_cutter`, `audio_mixer`, `subtitle_gen` | audio/subtitle prep |

## Process

### Step 1: Carry the runtime forward unchanged

Copy `render_runtime` (and `renderer_family`) from the proposal into
`edit_decisions` VERBATIM. Changing it here is forbidden — that is a
`render_runtime_selection` decision only the user can make.

### Step 2: Cut list

One cut per scene in script order: `id`, `source` (asset id from
asset_manifest), `in_seconds`/`out_seconds` trimmed to the narration timing.
Trim clip heads/tails that drift (generated clips often need 0.2-0.5s off the
ends). Total duration must match the approved script timing.

Retention pacing (optional): documentary-style VSLs hold attention better
rendered at **+8-10% uniform speed**, applied once to the assembled
video+audio at the very end so sync is preserved — never per-cut. Only
propose it when the locked runtime supports a global speed factor, and as a
user decision, never a silent default.

### Step 3: Audio

Narration segments mapped to cut timings (`audio.narration.segments`);
music track per the proposal decision with volume + fade under narration
(`audio.music`); mix levels sanity-checked (`audio_mixer` if pre-mixing).
Generated-clip ambient is fake-speech gibberish — hold it at a fixed LOW
level ducked under narration, never normalize it up (that amplifies the
mumble); drop it entirely if it distracts.

### Step 4: Subtitles and overlays

Subtitles from the script (burn decision per platform: 9:16 social defaults to
burned captions). CTA text belongs to compose-time overlays, never baked into
generated video. Keep overlay copy short and in the script's voice — no em
dashes in customer-facing text.

Text-card / CTA overlay design: full-screen statement and CTA cards sit on a
near-black contrast ground with white text plus the SINGLE brand accent — a
glowing accent pill for the CTA button; data/report cards stay light on
white/off-white. State overlay copy as "reads exactly: <text>" — no
paraphrase room for the renderer or a generation model.

Burned-caption craft: white words with a strong dark outline — verify
legibility over a light frame AND a dark one; each word fills to the brand
accent as spoken, subtle scale-pop per phrase, bottom-centre text-safe.
Skip captions on full-screen text-card scenes — they already show text.

### Step 5: Self-Evaluate and Submit

Validate `edit_decisions` against its schema (render_runtime, renderer_family,
cuts, audio all present), reviewer pass against `review_focus`, checkpoint
(`completed` — auto-proceeds), and hand to compose.

## Quality Checklist

- [ ] `render_runtime` identical to the proposal lock
- [ ] Every cut resolves to an asset_manifest id; timings sum to the script
- [ ] Narration/music/subtitle decisions are concrete, not deferred
