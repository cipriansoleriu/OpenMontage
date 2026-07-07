# Kie.ai File Upload API (cached 2026-07-07)

Source: https://docs.kie.ai/file-upload-api/upload-file-stream (+ quickstart)

## Stream upload (recommended, used by tools/_kie/client.py)
`POST https://kieai.redpandaai.co/api/file-stream-upload`
(**live-verified 2026-07-07**: the current docs render suggests api.kie.ai but
that host 404s; the working host is kieai.redpandaai.co)
Auth: `Authorization: Bearer <KIE_AI_API_KEY>` — same key as the jobs API.
multipart/form-data fields:
| field | required | notes |
|---|---|---|
| file | yes | binary |
| uploadPath | yes | e.g. `images/persona` — no leading/trailing slashes |
| fileName | no | auto-generated if omitted; identical names overwrite (cached!) |

Response: `{"success": true, "code": 200, "data": {"downloadUrl": "https://tempfile.redpandaai.co/...", "fileName", "filePath", "fileSize", "mimeType", "uploadedAt"}}`

## Alternates
- URL upload: `POST /api/file-url-upload` JSON `{fileUrl, uploadPath, fileName}`
- Base64 upload exists for small files

## Gotchas
- **Files auto-delete after 3 days** — upload-then-generate immediately; never
  store downloadUrls as durable references (keep local copies).
- Same-name overwrites can serve stale cached bytes — use unique fileNames.
- This is how a Kie-only keyframe->animate loop works with zero FAL_KEY:
  generate still -> upload_file -> use downloadUrl as first_frame_url/image_input.
