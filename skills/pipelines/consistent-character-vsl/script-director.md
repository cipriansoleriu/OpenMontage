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

Two script skeletons — pick per the proposal's angle:

- **Classic direct beats** (default): the section order above.
- **Story-led (condensed PIG)**: crisis gut-punch hook → setting the table
  (the events that led here) → the choice (three options; the hero takes
  control) → dead ends (the alternatives the viewer is considering, tried
  and failed — objections die in story, not argument) → mechanism reveal →
  results → proof across different viewer segments → offer → emotional
  callback close. Story beats must be factually true for this product and
  character — dead ends and any origin-story beat pass the Step 3 honesty
  gate like every other claim.

Copy Logic backbone (both skeletons): open on an absolute true statement —
certainty, never "if". Advance with If/Then chains ("if [accepted truth],
then [next conclusion]"), put proof immediately after each conditional, lead
with gain before loss, and stack agreed truths until the CTA is the only
logical step left.

Agitation works best as a causal argument: what changed in the viewer's
world → why the old approach stopped working → why this mechanism exists
now → the cost of not acting. Urgency must be legitimate — a deadline or
limit that is real, never manufactured.

The solution beat is a unique-mechanism reveal: first why nothing they
tried worked (the missing link), then the mechanism that changes it. Name
the offer only after the mechanism has landed.

Hook library — draft 3-5 hook candidates from DIFFERENT formula families
and present them as alternates at the gate; the user picks and hand-tunes
the final hook. Build each hook from 2-3 ingredients: identity label,
failed-objection ("tried everything?"), desired outcome, bold/contrarian
statement, unique mechanism, specificity (numbers, timeframes), curiosity
gap.

Ten proven formulas, by trigger family:

- *Curiosity*: **pattern interrupt** — "Stop [common practice].";
  **information gap** — "Here's what nobody tells you about [topic].";
  **contrast** — "The difference between [bad] and [good] is this.";
  **riddle/paradox** — "What if the thing you're doing to fix [problem] is
  causing it?" (the riddle must genuinely resolve into the mechanism,
  never clickbait).
- *Social proof*: **proof + method** — "I [result] in [timeframe]. Here's
  how."; **experience transfer** — "I wish someone told me this when I
  started [topic]."; **controversy** — "Unpopular opinion: [bold
  statement]." (soften for conservative audiences).
- *Behavior*: **loss aversion** — "This is the #1 reason your [thing] is
  failing."; **future pacing** — "POV: you finally [desirable outcome].";
  **targeting call-out** — "If you're a [audience] who [situation], watch
  this."; **save signal** — "Save this. You'll need it." (short-form
  social only).

Spoken headline templates adapt well too: "How [person] [result] without
[sacrifice]", "Warning: don't [X] until [Y]", "Give me [seconds] and I'll
give you [result]", "Are you making these [N] [topic] mistakes?". Run two
tests on every candidate: the acid test (would this line stop a stranger
on its own?) and the editing test (can any word go without losing impact?).

### Step 2: Write for the voice

Spoken-word register: short sentences, contractions, no em dashes, no
paragraph-length clauses. Read it aloud mentally at ~150 wpm to check the
timings. Scenes where the character speaks ON CAMERA are marked (they become
Seedance talking beats with native audio / lip-sync); voiceover-only sections
are marked too.

Persuasion register, layered on top of the spoken register:

- **Timeline language** — bridge the viewer into their future: "once you
  [do this], then you'll [experience this]", "after [mechanism] handles
  [problem], you're free to…", "within [timeframe], you notice…".
  Motivational beats educational: say what it DOES for them, never what it
  IS.
- **Magic Pill pass** — swap work words for effortless ones: learn →
  discover, teach → show/reveal, understand → see, earn → receive/collect,
  work → use/apply.
- **Copy payoffs at intervals** — give the "will" to the product: "it
  handles X for you, so you can…", never "you'll have to…". Attention
  decays; a payoff per section re-energizes it.
- **Bucket-brigade transitions** between sections keep the ear hooked:
  "but here's the thing…", "and that's not all…", "here's the kicker…",
  "best part:", "now here's where it gets interesting…".
- **Present-tense trance for after-state scenes** — "what you notice", not
  "what you will notice"; walk the transformed moment like a movie scene.
- **AI-tell ban list** (worse heard than read — never in VO or captions):
  leverage, unlock, seamlessly, game-changer, dive in, navigate (as verb),
  delve, robust, paradigm, holistic, synergy, cutting-edge, revolutionize,
  transformative, empower, harness, embark, journey (as metaphor),
  tapestry, landscape (as metaphor), realm, foster (as verb), elevate,
  "it's important to note", "in today's world".
- **"So what?" test** — every sentence must answer "so what? who cares?";
  cut or rewrite what can't. If a line doesn't fit one natural breath,
  shorten it.

### Step 3: Honesty pass

Every claim from the research brief keeps its verifiable/opinion tag; rewrite
anything the proof cannot carry. Story beats (dead ends, how the offer came
to be) pass the same gate — never invent biography for persuasion. The CTA
states the actual action and offer, and asks for ONE action, never a menu.
Optionally close pressure-free: a callback to the opening scene plus
"whatever you decide…" warmth — at the end of a VSL, reassurance converts
better than pressure.

### Step 4: Self-Evaluate and Submit

Validate `script` against its schema (section timings must sum correctly),
reviewer pass against `review_focus`, checkpoint as `awaiting_human`, present
the script with timings, and END YOUR TURN.

## Gate Reminder

Gated stage (`human_approval_default: true`) — the user approves the words
before scenes are planned around them.
