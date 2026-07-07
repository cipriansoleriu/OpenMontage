# LoRA training (fal / Replicate) — API knowledge pack

- Dataset: 15-30 images, varied angles/lighting, consistent subject. Caption with a unique
  trigger token (e.g. `ohwx_person`).
- fal: fast Flux LoRA trainer; returns an adapter usable in fal image/video gen.
- Replicate: LoRA trainers billed per compute-minute; returns a model/version id.
- Apply at generation by referencing the trigger token (and adapter id where required).
- Reuse: one adapter per character, reusable across unlimited generations — train once.
