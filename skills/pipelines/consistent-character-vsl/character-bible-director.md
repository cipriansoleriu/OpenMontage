# Character Bible Director — Consistent-Character VSL Pipeline

## When to Use

After scene_plan approval. You make the approved character REAL and reusable:
a registered `character_id` in `lib/character_registry.py` with 4-8 canonical
reference images that pass a self-consistency identity check. Everything
downstream (keyframes, clips, QC) anchors to this registry entry.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifact | `scene_plan` + the proposal's character plan | who the character is |
| Library | `lib/character_registry.py` | create/reuse the character record |
| Tool | `nano_banana_pro` | generate reference images when starting from text |
| Tool | `identity_drift` | self-consistency gate on the reference set |
| Layer 3 | `.agents/skills/nano-banana-pro/SKILL.md` | reference-conditioning technique |

## Process

### Step 1: Reuse before create

If the proposal picked an existing `character_id`, load it, verify
`reference_paths()` returns 4+ existing files, surface any
`missing_reference_paths()`, and skip to Step 4. Reuse is the point of the
registry — never rebuild an existing character without the user asking.

### Step 2: Create the character record

`CharacterRegistry().create(char_id, name=..., description=...)`. The
description must capture DURABLE identity markers — face structure, hair
color/texture, eye color, marks/freckles, build — not wardrobe or mood.

### Step 3: Build the reference set (4-8 images)

- **User-supplied photos**: `add_reference()` each (they are copied local).
- **From text**: generate a canonical portrait with `nano_banana_pro`
  (neutral background, head-and-shoulders), get user approval on the face,
  then generate 3-5 more angles/framings USING the portrait as `image_paths`
  reference so the set stays self-consistent. Register each approved image.

Aim for variety the scenes will need (close-up, half-body, full-body) while
keeping identity constant. Every image must show ONLY this character.

### Step 4: Self-consistency identity gate

Run `identity_drift` with the first/canonical reference as
`reference_image_paths` and the remaining refs as `candidate_paths`
(threshold 0.75). A reference that fails is removed or regenerated — a bad
reference poisons every downstream keyframe.

### Step 5: Write the character_bible artifact

`character_bible` (non-schema artifact) records: `character_id`, description,
reference image list (registry-relative), the self-consistency scores, the
identity approach from the proposal (references default / lora opt-in), and
wardrobe/setting continuity notes per scene from the scene_plan.

### Step 6: Self-Evaluate and Submit

Run the reviewer against this stage's `review_focus`, write the checkpoint as
`awaiting_human`, present the reference sheet (image paths) + scores to the
user, and END YOUR TURN.

## Gate Reminder

This stage is gated (`human_approval_default: true`): the user must see and
approve the character's face before any per-scene spend. Approval here does
not cover the assets gate.
