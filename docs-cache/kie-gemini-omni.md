# Kie.ai — Gemini Omni (video + character) (cached 2026-07-08)
Sources: https://docs.kie.ai/market/gemini-omni-video ,
https://docs.kie.ai/market/gemini-omni-character , https://kie.ai/gemini-omni

## Character create (synchronous, NOT the jobs API)
`POST https://api.kie.ai/api/v1/omni/character/create`  (Bearer KIE key)
Body: {image_urls: [ONE public URL, <=20MB JPEG/PNG/WEBP], descriptions: "..." (req),
character_name?, audio_ids? (<=1, from gemini-omni-audio)}
Response: {code:200, data:{characterId, characterName, imageUrl}}
Retention/expiry undocumented.

## Video (jobs API)
createTask model `gemini-omni-video`; input: prompt (req, <=20k chars),
character_ids (<=3; each uses 1 of 7 image slots), image_urls (<=7 total slots),
video_list (<=1, uses 2 slots; overrides duration), audio_ids (<=1-3),
duration "4|6|8|10" (string, seconds), aspect_ratio 16:9|9:16,
resolution 720p|1080p|4k (default 720p), seed [0, 2147483647].
Output: VIDEO via recordInfo resultJson.resultUrls. Pricing not published —
creditsConsumed is authoritative.
