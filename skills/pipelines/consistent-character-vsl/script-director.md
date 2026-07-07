# Script Director — Consistent-Character VSL Pipeline

## When to Use

After proposal approval. You write the VSL script: narration the character (or
a voiceover) will actually speak, structured in the classic beats, timed to
the approved duration.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Artifacts | `proposal_packet` (approved concept) | angle, duration, character role |
| Schema | `schemas/artifacts/script.schema.json` | canonical output |

## Process

### Step 1: Beat structure

Sections in order: **hook** (first 3-5s, pattern interrupt), **problem**,
**agitation**, **solution** (introduce the offer through the character),
**proof**, **CTA**. Each section carries narration text and a timing budget
that sums to the approved duration.

### Step 2: Write for the voice

Spoken-word register: short sentences, contractions, no em dashes, no
paragraph-length clauses. Read it aloud mentally at ~150 wpm to check the
timings. Scenes where the character speaks ON CAMERA are marked (they become
Seedance talking beats with native audio / lip-sync); voiceover-only sections
are marked too.

### Step 3: Honesty pass

Every claim from the research brief keeps its verifiable/opinion tag; rewrite
anything the proof cannot carry. The CTA states the actual action and offer.

### Step 4: Self-Evaluate and Submit

Validate `script` against its schema (section timings must sum correctly),
reviewer pass against `review_focus`, checkpoint as `awaiting_human`, present
the script with timings, and END YOUR TURN.

## Gate Reminder

Gated stage (`human_approval_default: true`) — the user approves the words
before scenes are planned around them.
