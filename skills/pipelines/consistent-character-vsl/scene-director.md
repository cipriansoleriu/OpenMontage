# Scene Director — Consistent-Character VSL Pipeline

## When to Use

After script approval. You break the script into 4-6 concrete scenes, each
tagged with the scene_type that drives the model mix, with a keyframe brief
the character bible + assets stages will execute.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifacts | `script` (approved) | narration + on-camera markers |
| Schema | `schemas/artifacts/scene_plan.schema.json` | canonical output |

## Process

### Step 1: Scene segmentation

Map script sections to 4-6 scenes. Each scene gets: `id`,
`script_section_id`, `start_seconds`/`end_seconds` (per-scene span of 4-15s —
the Seedance/Kling envelope; duration is the difference, never a separate
field), and `framing` matching the platform aspect ratio.

Time each scene to its narration: plan the generated clip at **duration ≥
that scene's VO seconds + 1** — a clip shorter than its narration freezes on
the last frame or needs slow-mo. If VO isn't measured yet, default talky
beats to 7-8s. Trimming a long clip at edit is free; fixing a short one
costs a regeneration.

### Step 2: Scene-type tagging (drives the model mix — schema-legal encoding)

The scene_plan schema is strict (`additionalProperties: false`); encode the
talking/action split with the EXISTING `type` enum — never invent fields:

- **talking beat** → `type: "talking_head"` — the character addresses the
  camera or speaks in-scene → Seedance (lip-sync + native audio).
- **action beat** → `type: "character_scene"` — the character does something
  (walks, demonstrates, reacts) with voiceover on top → Kling (or Seedance
  reference_to_video when identity needs anchoring beyond the first frame).

A standard VSL alternates: talking hook → action problem illustration →
talking solution → action proof/demo → talking CTA.

### Step 3: Keyframe briefs and continuity

The keyframe brief lives in the scene's `description` (setting, wardrobe,
camera, lighting, emotion — written as the `keyframe_lock` scene prompt;
identity comes from the registry, never re-describe the face), with concrete
motion in `character_actions` and asset needs in `required_assets`. Note
wardrobe/setting continuity across scenes (same outfit unless the story
changes it) — continuity errors read as identity errors to viewers.

Brief vocabulary — bake these into every `description`:

- **Grade + guard suffix.** End the brief with a grade line adapted to the
  act's mood, plus the guard: "natural daylight, shallow depth of field,
  subtle film grain, documentary realism. No on-screen text, no captions,
  no watermark." Keep "daylight" / "bright" in cinematic grades or the
  model drifts dark.
- **Screens are never readable.** If a device must appear, frame it wide or
  angled and say "the screen is an indistinct soft glow; no UI, no
  numbers". Never make a readable screen the subject — video models garble
  on-screen text (readable beats belong to compose overlays, Step 4).
- **Exact content + negative domain guard.** When a brief specifies real
  set/prop content (a list on a desk, a board, paperwork), give concrete
  example rows AND forbid the wrong domain — e.g. "incoming PHONE CALL rows
  like 'Maria L. 9:12 AM', 'Unknown 10:05 AM'; these are customer calls,
  absolutely NOT questions, quizzes, courses or sessions." Vague briefs
  invent off-topic placeholder content.
- **Moderation-safe wording.** Innocent words fail paid generations:
  "ghost" → "a faint translucent figure of light that dissolves";
  "foggy/steamy glass" + "wiping" + "storefront" → "mist on a cold window
  clearing to reveal…"; brand names / real products → describe generically
  and add "no brand logos". Reserve rephrasing for moderation rejects — a
  plain transient failure just retries.

### Step 4: Asset requirements

Per scene: keyframe + clip + narration segment + any overlay text (CTA cards
belong to compose, not to the generated video — no readable UI text in video
prompts).

### Step 5: Self-Evaluate and Submit

Validate `scene_plan` against its schema, reviewer pass against
`review_focus`, checkpoint as `awaiting_human`, present the scene table, and
END YOUR TURN.

## Gate Reminder

Gated stage (`human_approval_default: true`) — scene count times per-scene
cost is the budget commitment; the user approves it here.
