# Seedance 2.0 — API knowledge pack

- Modes: text->video, image->video, reference-to-video, first/last-frame. Native audio.
- Character: identity comes from the reference image (Face Lock; strong for front/3-4).
- Dialogue: put the spoken line in quotes in the prompt for native lip-sync (EN ships).
- Keep clips <= 10s (15s native-audio drift). 1080p on Kie/OpenRouter; Replicate caps at 720p.
- Cheapest routes: Kie reference ~$0.31/s, OpenRouter ~token formula ($7/M tokens ~ $5.10/15s 1080p).
