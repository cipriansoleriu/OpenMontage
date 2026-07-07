# Identity Train Director — Consistent-Character VSL Pipeline

## When to Use

After the character bible is approved. This stage resolves the ACTIVE identity
mode for the assets stage — and in the default case it does no work at all.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifact | `character_bible` | character_id + identity approach decision |
| Tool | `lora_train` | fal portrait-trainer (opt-in path only) |
| Layer 3 | `.agents/skills/lora-training/SKILL.md` | dataset + trigger phrase guidance |

## Process

### Step 1: Read the identity approach decision

Look up the proposal's `decision_log` entry with `category:
"provider_selection"` and `subject: "Identity approach (references vs LoRA)"`.
**Default is `references` — SKIP training.** Nano Banana Pro reference-conditioning holds
identity at 0.95+ judge similarity across scenes (verified finding), so LoRA
is an opt-in optimization for heavily-reused characters, never a default step.

### Step 2 (default path): record the skip

Write `identity_record` with `mode: references`, the character_id, and a note
that training was skipped per the default. Checkpoint `completed` (this stage
auto-proceeds) and move on. Zero spend.

### Step 3 (opt-in path only): train

Only when the user explicitly opted into `lora` at the proposal gate:

1. Confirm the character has 15+ reference images (`lora_train` enforces a
   floor of 5, but 15-30 is the production minimum — see the Layer 3 skill).
   If the set is thin, go back through the character-bible director to extend
   it rather than training on a weak dataset.
2. Announce the spend (~$2, minutes-to-an-hour) and the `key_alias` it bills
   to, then run `lora_train`. Never auto-retry a training; if polling times
   out, check the fal dashboard before re-running.
3. The adapter lands on the CHARACTER record (`registry.latest_lora`) — it is
   reusable across every future project. If the result carries
   `warning_registry_write_failed`, save the adapter manually per the warning
   before proceeding.
4. Write `identity_record` with `mode: lora`, the adapter record, and the
   trigger phrase.

### Step 4: Self-Evaluate and Submit

Reviewer pass against `review_focus` (especially: no training spend without an
opt-in decision), validate the identity_record is present, checkpoint, and
proceed — no human gate on this stage.

## Quality Checklist

- [ ] `identity_record.mode` matches the decision_log identity_approach
- [ ] Default path spent $0 and made no API calls
- [ ] Opt-in path announced cost + key_alias before training
- [ ] Adapter (if trained) is on the character record, not the project
