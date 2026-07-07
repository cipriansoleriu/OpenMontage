# Research Director — Consistent-Character VSL Pipeline

## When to Use

First stage of `consistent-character-vsl`. You turn the user's brief (product,
offer, audience) into a `research_brief` a VSL can be written from. This is a
direct-response pipeline: the research is about the BUYER, not the topic.

## Prerequisites

| Layer | Resource | Purpose |
|---|---|---|
| Input | the user's brief / product info | offer, audience, links |
| Schema | `schemas/artifacts/research_brief.schema.json` | canonical output |

## Process

### Step 1: Extract the offer and audience

From the brief (ask the user for gaps — do not invent): what is sold, at what
price point, to whom, on what platform (drives 9:16 vs 16:9 and duration
band), and what the desired action is (the CTA).

### Step 2: Map the pain and the promise

Document the core pain in the audience's own words, the failed alternatives
they already tried, the transformation the offer promises, and the strongest
available proof (numbers, testimonials, demos). Mark every claim as verifiable
(with source) or opinion — unverifiable claims must be framed honestly in the
script.

### Step 3: Persuasion angle

Pick the VSL angle (problem-agitate-solve, story-led, demonstration-led) and
note why it fits this audience. Note the character's role implied by the
angle: presenter to camera, demonstrator, or protagonist.

### Step 4: Self-Evaluate and Submit

Validate `research_brief` against its schema, run the reviewer against this
stage's `review_focus`, write the checkpoint (`completed` — no human gate),
and proceed to proposal.

## Quality Checklist

- [ ] Audience, platform, duration band, and CTA are explicit
- [ ] Pain is written in customer language, not marketing language
- [ ] Every on-screen-bound claim is tagged verifiable or opinion
