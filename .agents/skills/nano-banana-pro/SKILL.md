---
name: nano-banana-pro
description: |
  Generate identity-locked stills with Nano Banana Pro (Gemini 3.0 Pro Image) via Kie.ai (`nano_banana_pro` tool). Use when: (1) a character/product must look identical across many images — pass up to 8 reference photos as identity anchors, (2) branded or product imagery — always pass the real product photo, never a text-only description, (3) images need readable rendered text (posters, packaging, UI), (4) building a character bible or per-scene keyframes for consistent-character video pipelines. ~$0.12/image at 1K/2K, ~$0.24 at 4K.
allowed-tools: Bash, Read, Write
metadata:
  openclaw:
    requires:
      env_any:
        - KIE_AI_API_KEY
---

# Nano Banana Pro (Kie.ai)

## When to Use

- Identity consistency is the whole point: `image_input` takes up to 8 public reference URLs; the model preserves faces, wardrobe, products, and settings from them. Text-only prompts for branded objects are a known failure mode — always anchor with real photos.
- Long structured prompts work well (up to 10,000 chars) — describe scene, action, lighting, and composition; let references carry identity.
- For general non-identity imagery, cheaper models (flux_image, google_imagen) may suffice — this tool earns its price on consistency and text rendering.

## Process

1. Collect reference URLs (public, JPEG/PNG/WebP, <=30MB each; max 8). Order does not encode priority — name subjects explicitly in the prompt ("the woman from the reference photos").
2. Choose `resolution`: 1K for drafts/keyframes ($0.12), 2K for delivery ($0.12), 4K for print/detail ($0.24). `aspect_ratio` supports 1:1 through 21:9 plus `auto`.
3. Pass `key_alias` for client-billed work (PERSONA_KEY_kie_<alias>); alias-less calls bill `main`, then KIE_AI_API_KEY.
4. Always set `output_path` under `projects/<project-id>/assets/images/` — result URLs expire in 24h; the tool downloads immediately.
5. No seed parameter — regenerate variations by rephrasing the prompt, keeping references fixed.

## Quality Checklist

- [ ] Real reference photos passed for anything branded or identity-critical
- [ ] Identity match verified against references before using the still downstream
- [ ] Rendered text (if any) proofread — strong but not infallible
- [ ] `credits_consumed` in ToolResult data checked against the ~$0.12/$0.24 estimate
