# Pexels — Video Search API (cached 2026-07-08)

Source: https://www.pexels.com/api/documentation/

## Endpoint
`GET https://api.pexels.com/v1/videos/search` (older clients used
`https://api.pexels.com/videos/search`; keep as fallback if /v1 404s)
Auth header: `Authorization: <PEXELS_API_KEY>` (raw key, no Bearer prefix).

## Params
| param | type | notes |
|---|---|---|
| query | string, required | |
| orientation | `landscape\|portrait\|square` | |
| size | `large` (4K) / `medium` (FHD) / `small` (HD) | minimum size |
| per_page | int, default 15, max 80 | |
| page | int, default 1 | |

## Response
`videos[]`: id, width, height, url (pexels page), image (poster), duration (s),
user{name,url}, `video_files[]`: {id, quality: hd|sd, file_type, width, height,
fps, link (direct mp4)}.

## Limits & license
200 req/hour, 20k/month default. Pexels license: free commercial use, no
attribution required on the content itself; API terms ask for a prominent
Pexels link in end-user-facing apps where feasible. Relevance for animal
queries observed far better than Pixabay video search (2026-07-08).
