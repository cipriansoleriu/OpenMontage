# Stage: keyframe_lock (per scene)

Goal: an identity-locked still for THIS scene, before any motion.

Do:
1. Compose: identity block + LoRA (lora_id) + scene description (setting, camera, emotion).
2. Generate with `keyframe_lock` (nano_banana_pro under the hood). Multi-character frames: pass
   each character's references; Nano Banana Pro holds up to 5 subjects.
3. Run `identity_drift` against the reference sheet. If it fails, regenerate (up to 2x) before
   spending on animation. Only a passing keyframe proceeds to `animate`.
