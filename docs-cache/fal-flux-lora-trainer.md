# fal.ai — Flux LoRA Portrait Trainer (cached 2026-07-07)

Source: https://fal.ai/models/fal-ai/flux-lora-portrait-trainer/api

## Endpoints (raw queue REST, same convention as seedance_video)
- Submit: `POST https://queue.fal.run/fal-ai/flux-lora-portrait-trainer`
  -> `{status_url, response_url, request_id}`
- Poll `status_url` until status COMPLETED/FAILED/CANCELLED; fetch `response_url`.
- Auth: `Authorization: Key <FAL_KEY>`.

## Input
| field | type | default | notes |
|---|---|---|---|
| images_data_url | string URL | required | zip archive of subject images |
| trigger_phrase | string | optional | replaces [trigger]; fallback caption |
| steps | int | 2500 | |
| learning_rate | float | 0.00009 | |
| multiresolution_training | bool | true | |
| subject_crop | bool | true | auto-crop subject |
| resume_from_checkpoint | string | "" | |

## Output
`diffusers_lora_file: {url, content_type, file_name, file_size}` + `config_file`.

## Usage at inference (fal-ai/flux-lora)
`POST https://queue.fal.run/fal-ai/flux-lora` with
`{"prompt": "<trigger_phrase> ...", "loras": [{"path": "<diffusers_lora_file.url>", "scale": 1.0}]}`.

## Notes
- Long-running (minutes to ~1h); poll patiently, never blind-retry (paid).
- Pricing not published on the API page; ~$2/run ballpark — verify on dashboard.
- Zip upload via fal storage 2-step (initiate/PUT, content_type application/zip).
