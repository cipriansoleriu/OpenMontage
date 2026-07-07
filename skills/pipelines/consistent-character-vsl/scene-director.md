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
