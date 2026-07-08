# Asset Director — Consistent-Character VSL Pipeline

## When to Use

The production heart of the pipeline. For every scene in the approved
scene_plan you run the per-scene loop — keyframe, identity gate, animate,
clip QC, voice — and assemble the `asset_manifest` with full provenance and
spend. The loop lives HERE (in this skill), not in the manifest: the agent
drives it scene by scene.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifacts | `scene_plan`, `character_bible`, `identity_record` | scenes + identity mode |
| Tools | `keyframe_lock`, `identity_drift`, `frame_sampler` | identity loop |
| Tools | `seedance_kie` / `seedance_video` / `seedance_openrouter`, `kling_video`, `video_selector` | animation |
| Tools | `tts_selector`, `music_library`/music tools, `audio_mixer` | audio |
| Layer 3 | `seedance-kie`, `seedance-2-0`, `ai-video-gen`, `nano-banana-pro` skills | prompting + gateway mechanics |
| Governance | `tools/cost_tracker.py` + approved budget | spend tracking |

## Process

### Step 0: Plan the loop and announce spend

Build the per-scene worklist from scene_plan. Announce the itemized plan
(tool, model, per-scene estimate, key_alias) before the first paid call.
Track every scene's actual spend (`credits_consumed`) against the estimate.

### Step 1 — per scene: identity-locked keyframe

`keyframe_lock` with the character_id, the scene's keyframe brief, and the
mode from `identity_record` (`references` default; `lora` only if trained).
Write to `projects/<id>/assets/images/scene-<n>-keyframe.png`. Surface any
`warning_missing_references` immediately.

### Step 2 — per scene: keyframe identity gate (BEFORE animation)

`identity_drift` with the character_id and the keyframe as `candidate_paths`
(threshold 0.75). **A failing keyframe never proceeds to animation** — that is
the money-saving order of operations. Regenerate (vary the prompt, keep
references fixed) up to 2 times; if still failing, stop and present the best
attempts to the user.

### Step 3 — per scene: animate by scene type

Model mix from the proposal, honored per scene_type:

- **talking** → Seedance (`seedance_kie` first — cheapest; `image_to_video`
  with the keyframe as `image_path` (auto-uploaded on the Kie key — no
  FAL_KEY needed), `generate_audio: true` for scenes where the character
  speaks on camera). Pass `key_alias` for client-billed work.
- **action** → `kling_video` (fal) `image_to_video` from the keyframe; or
  Seedance `reference_to_video` with character refs when motion needs
  identity anchoring beyond the first frame.
- **presenter loop (VO-led, character on camera)** → the patterns below.
  This is its own animation mode, learned the expensive way: a
  talking-motion clip under an unrelated voiceover ALWAYS reads as broken
  lip-sync. Presenter loops are CLOSED-MOUTH presence shots.

#### Presenter-loop prompt library (closed-mouth presence under VO)

The iron law, appended verbatim to EVERY presenter-loop motion prompt:

> "Her mouth stays CLOSED the entire time — she is NOT talking; lips gently
> together, no mouthing, no whispering. No hand-talking gestures."

Generation rules for all patterns:

- `generate_audio: false` — presenter loops carry the VO track, and
  generated ambient is fake-speech gibberish (see edit-director ducking note).
- **Loopability**: motion must be subtle, continuous, and end near the
  opening pose ("the motion is gentle and cyclical, ending in a pose close
  to the first frame"). Ban one-way events inside a loop: no drinking to
  completion, no standing up, no exiting frame, no completed gestures.
- **Energy matches the VO**: a placid loop under a fired-up narration reads
  dead — give the VO's emotion a physical carrier (firmer nods, a lean-in)
  while the mouth stays closed. Match pattern energy to the beat below.
- Renderer: `seedance_kie` `image_to_video` fast from the scene keyframe,
  same as any i2v clip; the pattern text IS the motion prompt.

| # | Pattern | Motion prompt core | Best for beat |
|---|---|---|---|
| 1 | **Engaged listener** | "She looks into the camera with soft steady eye contact, slow natural blinks, slight head tilts and small affirming nods, calm breathing, faint changes of expression" | solution, authority, trust beats |
| 2 | **Prop business** | "She cradles the mug in both hands, lifts it slightly without drinking, thumb strokes the rim, a thoughtful glance down and back up to camera" | problem/empathy beats, kitchen-table authenticity (the original M4 fix) |
| 3 | **Reflective look-away** | "Her gaze drifts toward the window light, a small exhale, then returns to the camera with quiet resolve; shoulders soften" | agitation, story, dead-end beats |
| 4 | **Working presence** | "Seen in three-quarter view, she [writes on the pad / turns a page / rests a hand on the dog], absorbed in the task, face clearly visible, occasional glance toward camera" | proof and demonstration-adjacent beats |
| 5 | **Walking presence** | "She walks at a steady natural pace [toward / alongside] the camera, neutral-calm expression, eyes ahead then briefly to lens, ambient world motion around her" | transitions, future-pacing beats |
| 6 | **Warm close** | "A subtle smile forms with lips together, a single slow nod, steady warm eye contact held to the end of the shot" | CTA underlay, pressure-free close |

Anti-patterns (regenerate on sight): visible mouth movement of any kind;
gesture rhythms that mimic speech emphasis; loop seams (pose at cut point
far from the start frame); energy mismatch with the VO underneath. True
talking belongs ONLY to native-audio talking beats — never fake it with
motion under VO.

Duration 4-15s per the scene_plan. Deviating from the approved model mix is a
user decision, not a fallback — escalate per "No Unilateral Substitutions".

### Step 4 — per scene: clip identity QC (cross-scene, on real frames)

Run `identity_drift` with `video_paths: [the rendered clip]` and the
character_id — the tool frame-samples the clip via `frame_sampler`
(`frames_per_video: 3`) and judges every frame; the per-video verdict uses the
WORST frame. A failing clip gets ONE regeneration (animation is stochastic);
a second failure is presented to the user with the frame scores.

### Step 5 — voice and music

Narration via `tts_selector` per the script's narration segments (honor the
proposal's voice decision); write per-scene audio under
`projects/<id>/assets/audio/`. Resolve the music decision from the proposal
(library track / generated / none).

### Step 6: Assemble asset_manifest (schema-legal provenance)

The asset_manifest schema is strict — route provenance through its EXISTING
fields: `source_tool` (tool name), `model`, `provider`, `cost_usd` (actual
spend from credits_consumed), `quality_score` (the identity similarity for
this asset), `scene_id`, `prompt`, `seed`, and `generation_summary` (a short
string carrying task/request id + key_alias + credits, e.g.
"kie task_abc, alias client, 165 credits"). Cross-asset detail that doesn't
fit an entry goes in the manifest's top-level `metadata`. `total_cost_usd`
is the spend rollup vs the approved budget.

### Step 7: Self-Evaluate and Submit

Reviewer pass against `review_focus` (identity gate order, provenance,
budget), validate `asset_manifest` against its schema, refresh
`metadata.partial_progress` after each scene during the run, write the
checkpoint as `awaiting_human`, present the filmstrip (keyframes + clips +
scores + spend), and END YOUR TURN.

## Gate Reminder

This stage is gated (`human_approval_default: true`): the user reviews the
generated assets scene by scene before compose locks them in. Per-scene
regeneration requests here are normal — preserve everything except what the
user asks to change.
