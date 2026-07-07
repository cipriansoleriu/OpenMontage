# Compose Director — Consistent-Character VSL Pipeline

## When to Use

Final stage of `consistent-character-vsl`. You render the approved
`edit_decisions` into the deliverable via `video_compose`, verify the output,
and write the `render_report` with a spend summary.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifact | `edit_decisions`, `asset_manifest` | the EDL and asset paths |
| Tool | `video_compose` | routes by `edit_decisions.render_runtime` |
| Tool | `hyperframes_compose` (via video_compose) | HyperFrames engine + doctor |
| Skill | `skills/core/hyperframes.md` | HyperFrames gotchas (fonts, keyframes, workers) |
| Tool | `identity_drift` + `frame_sampler` | final identity spot check |

## Process

### Step 1: Verify the runtime contract

`video_compose` routes by `edit_decisions.render_runtime` — the value locked at
proposal. Confirm it is present and matches
`proposal_packet.production_plan.render_runtime`. **No silent runtime swap**:
if the locked runtime (typically HyperFrames on this pipeline) is unavailable
at compose time (`hyperframes doctor` fails, Node < 22, npm unresolvable),
STOP and escalate per "Escalate Blockers Explicitly" — do not route to
Remotion or FFmpeg without user approval plus a new `render_runtime_selection`
decision-log entry.

### Step 2: Pre-compose checks

Pass `proposal_packet` into `video_compose` inputs so its final review can
detect a runtime swap. Confirm `renderer_family` is set in `edit_decisions`,
every cut's asset id resolves in `asset_manifest`, and narration/music paths
exist. If the runtime is HyperFrames, re-read `skills/core/hyperframes.md`
first — mapped fonts only, re-encode stock clips to dense keyframes, and
preview-scrub before long renders.

### Step 3: Render

Call `video_compose` with `edit_decisions`, `asset_manifest`, and an
`output_path` under `projects/<project-id>/renders/final.mp4`. Watch for the
governance blocker result shape — surface it verbatim if it appears.

### Step 4: Verify the deliverable

Probe the render (duration, resolution, audio track). Then run the LAST
identity gate: `frame_sampler` is wired into `identity_drift` via
`video_paths` — one call with the final render and the `character_id` judges
sampled frames against the character's references. A failed final check is a
finding for the user, not a silent re-render.

### Step 5: Render report, final review, and spend summary

Write `render_report` with output path, encoding profile, runtime used,
verification notes (probe + identity result), and the full spend rollup from
`asset_manifest` provenance (per-scene credits/cost vs the approved budget).
Carry `video_compose`'s `final_review` data (including the runtime-swap and
promise-preservation checks) into the checkpoint artifacts alongside
`render_report` — the reviewer treats a compose without `final_review` as a
CRITICAL finding.

### Step 6: Self-Evaluate and Submit

Run the reviewer against this stage's `review_focus`, validate the artifact,
write the checkpoint (`completed` — this stage auto-proceeds), and present the
deliverable path plus the spend report to the user.

## Quality Checklist

- [ ] Runtime used == proposal-locked `render_runtime` (hyperframes/remotion/ffmpeg)
- [ ] Final render passed the identity spot check or the failure is surfaced
- [ ] `render_report` includes spend vs budget and verification notes
- [ ] Output lives under `projects/<project-id>/renders/`
