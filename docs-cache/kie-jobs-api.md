# Kie.ai unified jobs API (cached 2026-07-07 from docs.kie.ai)

Source: https://docs.kie.ai/ and https://docs.kie.ai/market/common/get-task-detail

## Auth
`Authorization: Bearer <KIE_AI_API_KEY>` + `Content-Type: application/json`.
Keys at https://kie.ai/api-key. Task logs at https://kie.ai/logs.

## Create task
`POST https://api.kie.ai/api/v1/jobs/createTask`
Body: `{"model": "<model-id>", "input": {...}, "callBackUrl": "<optional webhook>"}`
Response: `{"code": 200, "msg": "success", "data": {"taskId": "task_..."}}`
Non-200 `code` values: 401 auth, 402 credits, 404, 422 validation, 429 rate limit, 500+.

## Poll task
`GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId=<taskId>`
`data.state` enum: `waiting | queuing | generating | success | fail`.
On `success`, `data.resultJson` (JSON string) holds `{"resultUrls": ["https://..."]}`
(video/image); Seedance may add `firstFrameUrl`/`lastFrameUrl`. On `fail`,
`data.failCode` / `data.failMsg` carry the error. `data.creditsConsumed` is the
authoritative spend for the task.

Polling guidance from docs: start 2-3s, exponential backoff, stop after 10-15 min.
**Generated URLs expire after 24 hours — download immediately.**
