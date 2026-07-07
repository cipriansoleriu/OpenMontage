---
name: seedance-kie
description: |
  Route Seedance 2.0 generation through budget gateways: Kie.ai (`seedance_kie` tool — the cheapest route, with-reference discounts) and OpenRouter (`seedance_openrouter` tool — reuse an existing OpenRouter account/named keys, 480p/720p only). Use when: (1) cost matters — Kie 720p runs ~$0.205/s text-only and ~$0.125/s with references vs ~$0.30/s on fal, (2) billing a specific client — both tools accept `key_alias` to select a named key (PERSONA_KEY_kie_<alias> / PERSONA_KEY_openrouter_<alias>), (3) reference-conditioned generation on a budget (Kie supports the full 9 images + 3 videos + 3 audio surface). Read seedance-2-0 for model-level prompting; this skill covers the gateway mechanics, pricing, and gotchas.
allowed-tools: Bash, Read, Write
metadata:
  openclaw:
    requires:
      env_any:
        - KIE_AI_API_KEY
        - OPENROUTER_API_KEY
---

# Seedance 2.0 via Kie.ai and OpenRouter

## When to Use

- Prompting technique, camera direction, lip-sync-from-dialogue: read `seedance-2-0` first — it applies unchanged; these tools only change the gateway.
- Pick `seedance_kie` for the lowest cost and the full reference surface (9 images + 3 videos + 3 audio, first/last frame control, 480p-4k).
- Pick `seedance_openrouter` when the user wants everything billed through OpenRouter or already has per-client OpenRouter keys. 480p/720p only; `input_references` are visual guidance, `frame_images` are exact frames.
- Both accept `key_alias` — route client work to named keys (`python -m lib.keyvault` lists aliases). Alias-less calls bill `main`, then the conventional env key.

## Pricing (estimates — Kie recordInfo.creditsConsumed is authoritative)

| Route | 480p | 720p | 1080p | notes |
|---|---|---|---|---|
| Kie text-only | $0.095/s | $0.205/s | $0.51/s | 4k undocumented, budget 2x 1080p |
| Kie with references | $0.0575/s | $0.125/s | $0.31/s | discount applies with reference inputs |
| OpenRouter | ~$0.068/s | ~$0.152/s | n/a | token-formula billing, treat as estimate |
| fal (`seedance_video`) | — | $0.3034/s | — | for comparison; fast $0.2419/s |

## Process

1. Resolve the key story first: which alias bills this generation? Pass `key_alias` explicitly for client work.
2. Inputs must be **public URLs** — neither gateway uploads local files. Generate stills to a URL-hosted store first, or use `seedance_video` (fal) which auto-uploads local paths.
3. Kie: `operation=image_to_video` maps `image_url` -> `first_frame_url`; `reference_to_video` takes `reference_image_urls/reference_video_urls/reference_audio_urls` (ceilings 9/3/3, videos <=15s total, audio <=15s total).
4. Kie has **no seed parameter** — reproducibility comes from references, not seeds.
5. Results expire in 24h — the tools download to `output_path` immediately; always pass an explicit `output_path` under `projects/<project-id>/`.
6. Generation runs ~4-5 min; the tools poll with backoff and give up after 15 min, returning a ToolResult error (never hanging).

## Quality Checklist

- [ ] `key_alias` chosen deliberately (client work never bills `main` by accident)
- [ ] All input URLs public and under the size caps (images 30MB, video 50MB, audio 15MB)
- [ ] Resolution matches budget (with-reference Kie rates when references exist)
- [ ] `output_path` set under the project workspace
- [ ] `credits_consumed` from the ToolResult data checked against the estimate
