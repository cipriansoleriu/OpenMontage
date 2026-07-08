# fal.ai — InstantCharacter (cached 2026-07-08)
Source: https://fal.ai/models/fal-ai/instant-character/api

Queue REST (same convention as other fal tools): `POST https://queue.fal.run/fal-ai/instant-character`
Auth `Authorization: Key <FAL_KEY>`; poll status_url/response_url.

Input: prompt (req), image_url (req — SINGLE subject reference), image_size
(square_hd default; portrait_16_9/landscape_16_9/... or {width,height}),
scale (float, 1 = subject prominence), negative_prompt, guidance_scale (3.5),
num_inference_steps (28), seed, num_images (1), output_format (jpeg|png).

Output: {images: [{url, width, height, ...}], seed, ...}
Pricing: not published on the API page (flux-class serverless; verify via billing).
