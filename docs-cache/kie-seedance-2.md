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

## Pricing (per second)
**OBSERVED BILLING (2026-07-07/08 acceptance run) contradicts the advertised
with-reference discount: 720p billed FLAT $0.205/s (41cr/s) on BOTH
image_to_video and reference_to_video (410cr for a 10s r2v clip).** Budget at
the flat rate; the marketing-page table below is retained for reference only.

| resolution | advertised text-only | advertised with-ref | observed |
|---|---|---|---|
| 480p | $0.095 | $0.0575 | unverified |
| 720p | $0.205 | $0.125 | **$0.205 flat** |
| 1080p | $0.51 | $0.31 | unverified |
| 4k | undocumented | undocumented | unverified |

`recordInfo.creditsConsumed` is authoritative (1 credit ≈ $0.005 observed).
Observed variant split (2026-07-08 bake-off): **fast i2v = 33cr/s ≈ $0.165/s**
(132cr/4s); standard + r2v = 41cr/s ≈ $0.205/s. seedance_kie.estimate_cost
deliberately uses the flat $0.205/s for both (never understate budgets).
Comparison: fal.ai seedance_video ≈ $0.3034/s standard, $0.2419/s fast;
Kie gemini-omni-video ≈ $0.08/s at 720p (63cr/4s) — cheap, but failed the
identity bake-off (0.45) so it is a B-roll option only.
