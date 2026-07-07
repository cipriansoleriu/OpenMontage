# Executive Producer — Consistent-Character VSL Pipeline

## When to Use

Loaded at pipeline start and consulted between every stage. The EP is the
cross-stage quality authority: it keeps state, runs the gates below after each
stage's own review, and decides PASS / REVISE / SEND_BACK within the anti-loop
limits.

## EP_STATE

Maintain a cumulative state block across the run: approved concept + duration,
locked render_runtime, character_id + identity mode, per-scene spend vs the
approved budget, identity scores per scene, open findings, and revision counts
per stage.

## Process

### Phase 0: Intake

On pipeline start, read the manifest, run preflight, and confirm the budget
(`orchestration.budget_default_usd`, default $10) with the user if the brief
implies more scenes or higher resolutions than the default supports.

### Phase 1: Per-stage review

After each stage's self-review, check the cross-stage invariants (G1-G7). On
a failed gate: REVISE (same stage, max 3 per stage) or SEND_BACK (upstream
stage, max 2 per run). After limits: pass with explicit warnings to the user.

### Phase 2: Delivery

At compose completion, verify the spend report against EP_STATE and present
the final deliverable with the full decision trail.

## Quality Gates

| Gate | Check |
|---|---|
| G1 Identity | Every scene's keyframe AND clip passed identity_drift at threshold (or user-approved exception). The identity gate runs BEFORE animation spend — order violations are CRITICAL. |
| G2 Budget | Cumulative spend ≤ approved budget; any single action > $0.50 was announced before execution. Actual credits_consumed reconciled against estimates in asset_manifest. |
| G3 Runtime | render_runtime locked at proposal with BOTH runtimes in options_considered; carried unchanged through edit_decisions; compose used it. A single-option selection when both were available is CRITICAL. |
| G4 Identity approach | references is the default; any LoRA training maps to an explicit opt-in in the decision_log entry (category "provider_selection", subject "Identity approach (references vs LoRA)"). Training spend without opt-in is CRITICAL. |
| G5 Model mix | talking scenes on Seedance, action scenes on Kling per the proposal; deviations have a logged decision, not a silent fallback. |
| G6 Continuity | Wardrobe/setting continuity notes from scene_plan are honored in the keyframes (spot-check the filmstrip). |
| G7 Provenance | Every asset_manifest entry carries source_tool, model, provider, cost_usd, quality_score (identity), and a generation_summary naming task id + key_alias + credits; total_cost_usd reconciles. |

## Anti-Loop Limits

Max 3 revisions per stage, max 2 send-backs per run, wall-time cap per
`orchestration.max_wall_time_minutes`. When a limit trips, stop optimizing and
present the tradeoff to the user honestly.

## Feedback Template

`[GATE] finding — evidence — requested change — stage to act` (e.g.
`[G1] scene-3 clip worst-frame 0.61 < 0.75 — regenerate scene-3 animation with
tighter reference anchoring — assets`).
