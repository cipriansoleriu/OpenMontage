# Kie.ai — ByteDance Seedance 2.0 (cached 2026-07-07)

Sources: https://docs.kie.ai/market/bytedance/seedance-2 ,
https://docs.kie.ai/market/bytedance/seedance-2-fast , https://kie.ai/seedance-2-0

## Model IDs (createTask `model` field)
- `bytedance/seedance-2` — standard, highest quality (~5 min/gen)
- `bytedance/seedance-2-fast` — faster/cheaper (~4 min/gen), 480p/720p focus

## `input` object
| field | type | notes |
|---|---|---|
| prompt | string, required | 3–20,000 chars |
| first_frame_url | string URL | image-to-video start frame |
| last_frame_url | string URL | optional end frame |
| reference_image_urls | array ≤9 | JPEG/PNG/WEBP/JPG, ≤30MB each |
| reference_video_urls | array ≤3 | ≤50MB each, total length ≤15s |
| reference_audio_urls | array ≤3 | ≤15MB each, total length ≤15s |
| generate_audio | bool, default true | audio increases cost |
| resolution | `480p\|720p\|1080p\|4k` | default 720p |
| aspect_ratio | `16:9\|4:3\|1:1\|3:4\|9:16\|21:9` (+`adaptive` per docs) | default 16:9 |
| duration | integer 4–15 | default 5 |
| web_search | bool | optional |
| nsfw_checker | bool, default false (true in playground) | |

No `seed` parameter. Inputs must be public URLs (or Kie `asset://`).

## Pricing (per second, from kie.ai Seedance 2.0 page via search index, 2026-07)
| resolution | text-only | with reference |
|---|---|---|
| 480p | $0.095 | $0.0575 |
| 720p | $0.205 | $0.125 |
| 1080p | $0.51 | $0.31 |
| 4k | undocumented (est. ~2× 1080p) | undocumented |

`recordInfo.creditsConsumed` is authoritative; treat the table as estimates.
Comparison: fal.ai seedance_video ≈ $0.3034/s standard, $0.2419/s fast.
