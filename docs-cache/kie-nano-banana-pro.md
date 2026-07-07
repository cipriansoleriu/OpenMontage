# Kie.ai — Google Nano Banana Pro (cached 2026-07-07)

Source: https://docs.kie.ai/market/google/pro-image-to-image

## Model ID (createTask `model` field)
`nano-banana-pro` (Gemini 3.0 Pro Image architecture; one model id covers
text-to-image and image-to-image — references are just optional).

## `input` object
| field | type | notes |
|---|---|---|
| prompt | string, required | ≤10,000 chars |
| image_input | array ≤8 URLs | JPEG/PNG/WebP, ≤30MB each — identity/product references |
| aspect_ratio | `1:1\|2:3\|3:2\|3:4\|4:3\|4:5\|5:4\|9:16\|16:9\|21:9\|auto` | default 1:1 |
| resolution | `1K\|2K\|4K` | default 1K |
| output_format | `png\|jpg` | default png |

## Pricing (via kie.ai pricing pages, 2026-07)
~24 credits ≈ $0.12/image at 1K/2K (≈20% under Google's $0.134);
4K ≈ $0.24/image. `recordInfo.creditsConsumed` is authoritative.

Result via jobs recordInfo: `resultJson.resultUrls[0]` (expires in 24h).
