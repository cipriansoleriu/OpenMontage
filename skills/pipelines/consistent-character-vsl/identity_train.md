# Stage: identity_train

Goal: lock the character into model weights so it survives varied scenes (a single reference
image drifts; a trained LoRA does not).

Do:
1. Select 15-30 varied reference images (angles, lighting) from the bible.
2. Call `lora_train` (provider: fal default; replicate if cheaper) with a unique trigger token.
   Respect an explicit `key_alias` if the user named a key.
3. Poll to completion; store `{ lora_id, provider, trigger }` on the character for reuse across
   projects. Record cost to the ledger.
4. Skip this stage only for `ugc-talking-head` when one locked reference image is sufficient.
