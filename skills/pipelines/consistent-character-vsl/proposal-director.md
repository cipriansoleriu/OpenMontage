# Proposal Director — Consistent-Character VSL Pipeline

## When to Use

Second stage of `consistent-character-vsl`, after the research brief is approved.
You turn the brief into at least 3 concept directions, a locked production
plan, a character plan, an identity approach, a runtime decision, and an
itemized cost estimate — then stop at the human gate.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifact | `research_brief` | audience, offer, pain, platform, duration band |
| Schema | `schemas/artifacts/proposal_packet.schema.json` | canonical output |
| Registry | `registry.provider_menu_summary()` | live capability envelope |
| Registry | `lib/character_registry.py` (`CharacterRegistry().list()`) | reusable characters |
| Layer 3 | `.agents/skills/seedance-kie/SKILL.md`, `.agents/skills/nano-banana-pro/SKILL.md` | pricing + gateway mechanics |

## Process

### Step 1: Preflight and capability envelope

Run the registry preflight and confirm which of the video backends
(`seedance_kie`, `seedance_video`, `seedance_openrouter`, `kling_video`), image
backends (`nano_banana_pro`), TTS, and composition runtimes are configured.
Present the "N of M configured" menu. Do not plan around a tool that is
unavailable without offering the setup fix.

### Step 2: Concept directions

Design at least 3 genuinely different VSL concepts from the research brief
(the proposal_packet schema requires 3+), each with a distinct hook and
emotional arc. Every concept names: the character's role (presenter,
demonstrator, story protagonist), the scene-type split (how many talking beats
vs action beats), platform framing (9:16 vs 16:9), and duration.

### Step 3: Character plan

Check `CharacterRegistry().list()` for a reusable character first — reuse is
the whole point of the registry. Propose either an existing `character_id` or
a new character (name, identity markers, wardrobe). The character bible stage
will build/verify the reference set; here you only lock WHO.

### Step 4: Identity approach (references default, LoRA opt-in)

Record the identity decision in `decision_log` using the EXACT pair
`category: "provider_selection"`, `subject: "Identity approach (references vs
LoRA)"` — the decision_log schema has a closed category enum, and downstream
skills (identity-train-director, EP gate G4) look this pair up verbatim:

- **Default: `references`** — Nano Banana Pro reference-conditioning holds
  identity at 0.95+ judge similarity across scenes (verified 2026-07-07).
  $0.09-0.12 per keyframe, zero setup.
- **Opt-in: `lora`** — offer ONLY when the character is heavily reused
  (recurring across projects, dozens of generations) or references drift under
  extreme restyling. ~$2 training + minutes-to-an-hour wait. Never pre-select
  it; the user must opt in explicitly.

### Step 5: Runtime selection — present both (HARD RULE)

`production_plan.render_runtime` is locked here and carried through
`edit_decisions` unchanged. When both runtimes are available you MUST present
both to the user — never silently default, even though this pipeline has a
recommendation:

- **HyperFrames (recommended)** — HTML/CSS/GSAP composition. Recommended for
  this pipeline because it is Apache-2.0: free at any scale and product-safe
  if this fork ever ships as a service, and VSL cut/caption/CTA composition
  maps naturally to HTML. Tradeoff: Phase-1 scope (stills, clips, text cards,
  narration/music); richer bespoke scenes need hand-authored blocks.
- **Remotion** — React composition with the mature scene-type catalog
  (stat cards, charts, captions). Tradeoff: free only within the ≤3-person
  license today; becomes a paid Automators license the moment it renders for
  end users — a real constraint for productized use.

State one honest sentence per runtime for THIS brief, recommend HyperFrames
with the rationale above, and wait for the user's pick. Lock the choice as
`production_plan.render_runtime` (`hyperframes`, `remotion`, or `ffmpeg`) and
log `render_runtime_selection` in `decision_log` with BOTH runtimes (plus
ffmpeg where honest) in `options_considered`. If only one runtime is
available, say so explicitly and record the other as
`rejected_because: "not available"`.

### Step 5b: Renderer family (locked here, like render_runtime)

Lock `production_plan.renderer_family` — for a character-led VSL the natural
pick is `presenter` (enum options include explainer-data, cinematic-trailer,
product-reveal, ...). Edit carries it into `edit_decisions` verbatim; compose
blocks without it. Log the pick with the runtime decision.

### Step 6: Model mix and cost estimate

Bake the model mix into the production plan: **Seedance for talking beats**
(lip-sync, native audio; route `seedance_kie` first — cheapest), **Kling for
action beats** (motion variety via fal). Itemize cost per scene: keyframe
($0.09-0.12) + clip (Kie 720p: ~$0.63/5s with reference discount; Kling:
$0.10-0.30/5s) + TTS + music. Include the identity QC judge (~$0.01/scene).
Show the total against `orchestration.budget_default_usd` ($10).

### Step 7: Music plan (mandatory)

Check `music_library/` and the music-generation tools; present the options
(library track / user-provided / generated / none) and record the decision.

### Step 8: Self-Evaluate and Submit

Validate `proposal_packet` against its schema (including
`production_plan.render_runtime`), run the reviewer meta skill against this
stage's `review_focus`, write the checkpoint as `awaiting_human`, present the
concepts + decisions + costs, and END YOUR TURN.

## Gate Reminder

This stage is gated (`human_approval_default: true`). Approval here covers the
proposal only — later gates (script, scene_plan, character_bible, assets) each
need their own approval. Never start character or asset spend from this stage.
