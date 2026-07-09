# fal.ai — Kling v3 Standard image-to-video (cached 2026-07-08)

Sources: https://fal.ai/models/fal-ai/kling-video/v3/standard/image-to-video (+ /api)

## Endpoint
`queue.fal.run/fal-ai/kling-video/v3/standard/image-to-video`

## Input schema (v3 standard i2v)
| field | type | notes |
|---|---|---|
| prompt / multi_prompt | string, ONE required | not both |
| start_image_url | string URL, required | **NOT `image_url`** (older variants used image_url) |
| duration | enum "3".."15" | default "5" — arbitrary 3-15s, not just 5/10 |
| aspect_ratio | `16:9\|9:16\|1:1` | default 16:9 |
| generate_audio | bool, **default TRUE** | native audio; billed at a higher tier |

No resolution parameter. No seed.

## Pricing (published, per second of output)
| mode | $/s | 10s clip |
|---|---|---|
| audio OFF | $0.084 | $0.84 |
| audio ON (default!) | $0.126 | $1.26 |
| audio ON + voice control | $0.154 | $1.54 |

Gotchas learned 2026-07-08 (reactive-dog-vsl-full reconcile):
- The tool's old estimate ($0.10/5s standard) understated real billing by ~4x
  audio-on. `generate_audio: false` MUST be passed explicitly for VO-led clips
  — both for cost and because generated ambient is fake-speech gibberish.
- The 90s acceptance run logged $0.20/clip from the stale estimate with
  `credits_consumed: null` — those clips likely billed $1.26 each (audio-on
  default, 10s). Treat any unreconciled fal cost as the audio-on rate.
- fal response payload carries no billing metadata; reconcile against this
  published table or the fal dashboard.
