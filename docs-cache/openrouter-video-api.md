# OpenRouter video generation API (cached 2026-07-07)

Sources: https://openrouter.ai/docs/cookbook/video-generation/reference-to-video ,
https://openrouter.ai/bytedance/seedance-2.0 , announcement blog.

## Endpoints
- Create: `POST https://openrouter.ai/api/v1/videos` (spends credits immediately)
- Poll: `GET https://openrouter.ai/api/v1/videos/{job_id}` (job response also has `polling_url`)
- Download: `unsigned_urls[0]` if present, else `GET .../videos/{job_id}/content?index=0`
- Auth: `Authorization: Bearer <OPENROUTER_API_KEY>`

## Request body
```json
{
  "model": "bytedance/seedance-2.0",          // or bytedance/seedance-2.0-fast
  "prompt": "...",
  "duration": 5,
  "resolution": "480p|720p",
  "aspect_ratio": "1:1|3:4|9:16|4:3|16:9|21:9|9:21",
  "generate_audio": true,
  "input_references": [{"type": "image_url", "image_url": {"url": "https://..."}}]
}
```
`input_references` = visual guidance; `frame_images` = exact first/last frame control.
`frame_images` entries REQUIRE a `frame_type` designator (verified against the live
image-to-video cookbook 2026-07-07):
```json
{"type": "image_url", "image_url": {"url": "https://..."}, "frame_type": "first_frame"}
```
(`frame_type`: `first_frame` | `last_frame`.)

## Response / status
`{id, status, polling_url, unsigned_urls[], bytes, error}` with
`status`: `pending | completed | failed | cancelled | expired`.
Docs suggest ~30s poll interval, ≤60 attempts.

## Pricing
"from $0.06726/second"; tokens = (height × width × duration × 24) / 1024.
Per-resolution $/s must be treated as an estimate (≈$0.067/s at 480p,
≈$0.15/s at 720p by pixel scaling). No 1080p listed for this API (480p/720p only).
