---
name: lora-training
description: |
  Train and use identity LoRAs for recurring characters (`lora_train` tool, fal-ai/flux-lora-portrait-trainer). Use when: (1) a character will appear across MANY projects or dozens of scenes — train once (~$2, minutes-to-an-hour), reuse forever via the character registry, (2) Nano Banana Pro reference-conditioning isn't holding identity tightly enough across extreme scene changes, (3) generating keyframes with `keyframe_lock` in mode='lora'. The adapter is keyed to the CHARACTER in lib/character_registry.py, never to a project. For one-off characters prefer references mode (instant, ~$0.12/still, no training cost).
allowed-tools: Bash, Read, Write
metadata:
  openclaw:
    requires:
      env_any:
        - FAL_KEY
---

# Identity LoRA training (fal)

## When to Use

- Decision rule: **references first, LoRA when scale demands it.** Nano Banana Pro with 4-8 good reference photos holds identity for most VSL/UGC work with zero training cost. Train a LoRA when the character recurs across projects, needs dozens+ of generations (amortize the ~$2 training), or drifts under extreme restyling.
- The dataset IS the quality: 15-30 images, varied angles/lighting/expressions, consistent subject, no other people in frame. The tool enforces a floor of 5 but treat 15 as the real minimum for production identity.
- `trigger_phrase` is the token that summons the identity at inference (default `<character_id> person`). Keep it unusual enough not to collide with normal prose.

## Process

1. Register the character (`lib/character_registry.py`) and add reference images — the trainer defaults to the registry refs, and the adapter record lands back on the character (reuse-everywhere).
2. Run `lora_train` with `key_alias` if the training bills a client. Training is paid and never auto-retried; if polling times out, check https://fal.ai/dashboard/requests before re-running.
3. Generate with `keyframe_lock` mode='lora' (fal-ai/flux-lora, `loras=[{path: adapter_url, scale: 1.0}]`, trigger phrase auto-prepended), or pass the adapter to any fal flux endpoint that accepts `loras`.
4. QC every batch with `identity_drift` against the registry references before animating.

## Quality Checklist

- [ ] 15-30 varied, single-subject training images (5 is the hard floor, not the target)
- [ ] Trigger phrase recorded in the registry (it is — automatically) and used at inference
- [ ] Adapter reused via `registry.latest_lora(char_id)` — never retrain an existing character casually (~$2/run)
- [ ] Keyframes pass identity_drift vs the same references the LoRA trained on
- [ ] Adapter URL is provider-hosted and may expire — refs stay local, retrain is always possible
