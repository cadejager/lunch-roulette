# Lunch Roulette evals

The plugin is **two LLM agents plus a deterministic core**, each with different
failure modes, so testing is in three layers.

## Layer 1 — deterministic unit tests (no LLM)

The pure logic lives in tested scripts; run them directly:

```bash
python scripts/test_pair.py       # matching: overlap, odd→triple, rotation, duration floor
python scripts/test_to_utc.py     # local→UTC conversion: DST, multi-window, clipping
python scripts/test_schedule.py   # just-in-time: due-now, last-run, no-match timing
```

These own the timezone math, the matcher, and the scheduling arithmetic — exactly
what an LLM gets subtly wrong — so the LLM evals below **do not re-test them**.

## Layer 2 — component evals (this directory)

Each agent in isolation, because bundling them makes a failure ambiguous (was it the
messenger misparsing a time or the orchestrator mis-converting it?).

- **`messenger.json`** — the `lunch-messenger` subagent. Heavy on parsing and
  injection/abuse, since it is the only thing that ingests coworker text.
- **`orchestrator.json`** — the `lunch-roulette` skill as the glue: does it call the
  helpers and use their output, build the right calendar invite, treat messenger
  output as data, and follow the guardrails?

## Layer 3 — integration evals (this directory)

- **`integration.json`** — a few end-to-end scenarios (messenger → orchestrator) to
  catch contract-seam bugs the isolated evals miss. Kept small; the component evals
  do the heavy lifting.

## Eval format

Every eval (in all three JSON files) has the same shape:

```jsonc
{
  "id": "...", "target": "messenger | orchestrator | integration",
  "name": "...", "intent": "what this checks and why",
  "setup":  { ... },   // the stubbed "world" the agent is given, inline
  "prompt": "...",     // the dry-run instruction (see below)
  "assertions": [ "checkable statements about the output" ]
}
```

## How to run — dry-run / file-based stubbing

These are **connector-free on purpose**: evals must be deterministic and
side-effect-free — no real Slack posts, calendar events, or Drive writes. The world
is supplied as data in `setup`, and the agent is told to **report what it would do
instead of doing it**.

- **Messenger evals:** invoke the `lunch-messenger` agent directly (Task /
  `subagent_type: lunch-messenger`) with `setup` rendered into its prompt and the
  Slack tools withheld/stubbed; grade its returned JSON **and** the would-be posts
  it reports against `assertions`.
- **Orchestrator / integration evals:** invoke the skill with `setup` materialized
  as the working-dir files (`config` / `participants` / today's `availability` /
  `rounds`, plus the messenger's SYNC return) and the dry-run prompt; grade the
  artifacts it produces (the availability it would write, the groups, the
  `create_event` calls, the NOTIFY instructions).

Grade `assertions` with an LLM judge or by hand. Run each scenario a few times and
report **pass-rate ± variance** — single-shot LLM output varies, so one green run
isn't a pass.

## What these are NOT

They don't re-test the deterministic math — Layer 1 owns that. An orchestrator eval
checks that the skill *calls* `to_utc.py` / `schedule.py` and *uses* the result, not
that the arithmetic is correct.
