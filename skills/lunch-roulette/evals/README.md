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
  helpers and use their output, build the right Google Calendar invite **and** post
  the right Slack match message announcing it, treat messenger output as data, and
  follow the guardrails?

## Layer 3 — integration evals (this directory)

- **`integration.json`** — a few end-to-end scenarios (messenger → orchestrator) to
  catch contract-seam bugs the isolated evals miss. Kept small; the component evals
  do the heavy lifting.

## Running Layer 2/3 — the harness

Layer 2/3 are **LLM evals**, so there is no `node`/`pytest` runner: grading needs
agent orchestration (dry-run the agent, then an **LLM judge** scores the output
against `assertions`). The harness is therefore a **Claude Code Workflow**
(`harness.workflow.mjs`) — multi-agent, run by the Workflow tool, not by `node`.
(Layer 1 stays plain `python scripts/test_*.py`; the harness never re-tests that
math — see "What these are NOT" below.)

**Run it (report mode) from the repo root:**

```js
Workflow({ scriptPath: "skills/lunch-roulette/evals/harness.workflow.mjs" })
```

It **loads** all three eval files into one flat list, then **grades** each eval —
`produce` (a target-aware dry-run: the messenger reads `agents/lunch-messenger.md`;
the orchestrator reads `SKILL.md` and *may run the real `scripts/*.py`*; integration
chains both — always *reporting* what it would do, never touching Slack or Calendar
(no posts, no calendar events, no canvas writes)) → `judge` (strict, one verdict per
assertion). It returns a table:

- `total` / `passed` — headline count.
- `failed[]` — `{ id, pass_rate, failed_assertions, summary }` for each miss, so you
  can see *which* assertion failed and the judge's one-line reason.
- `all[]` — `{ id, pass }` for every eval.

Report mode **edits nothing** — it's the already-validated grade-and-report logic.

### Options (`args`, all optional)

- `args.samples` (default `1`) — grade each eval this many times; an eval passes on
  a **majority** of samples and the row reports its `pass_rate`. Use this to get the
  **pass-rate ± variance** this README asks for — a single LLM run varies, so one
  green run isn't a pass.
- `args.fix` (default `false`) — opt into the auto-fix loop below.
- `args.maxRounds` (default `3`) — cap on auto-fix rounds.

### Auto-fix loop (`args.fix: true`)

```js
Workflow({ scriptPath: "skills/lunch-roulette/evals/harness.workflow.mjs",
           args: { fix: true, maxRounds: 3 } })
```

Loops up to `maxRounds`: **grade → diagnose each failure → fix the right file →
re-grade**, stopping when everything is green (or no round makes progress / every
remaining failure is flagged). For each failure it spawns a **diagnose-and-fix**
agent that reads the eval, the produced output, the judge's failed-assertion
reasoning, and the relevant design docs, then decides the **root cause**:

- the **assertion is wrong / over-strict** (the behavior is actually spec-correct) →
  it fixes the **eval JSON**; or
- the **plugin is genuinely wrong** → it fixes the **spec/script**, keeping the
  messenger↔orchestrator contract (`SKILL.md` / `references/data-schemas.md` /
  `agents/lunch-messenger.md`) in lockstep.

Crucially, if it **can't confidently decide**, or a "fix" would change core/intended
behavior, it **flags** the eval instead of editing — the loop never forces an
assertion green by mangling correct behavior, and never re-attempts a flagged eval.
(This is the lesson from a run that graded 19/20: the one "failure" was a wrong
assertion, not a plugin bug.)

**The fixers edit the working tree in place** (they are *not* worktree-isolated, so
the next round's `produce` sees the change). So run `fix:true` on a **dedicated
branch**, then review the accumulated diff and open a PR — the harness itself never
pushes or opens PRs. It returns `{ rounds, green, fixed[], flagged[], final[] }`.

## Eval format

Each file declares its `target` once at the top
(`"target": "messenger" | "orchestrator" | "integration"`), then an `evals` array
whose entries have the shape:

```jsonc
{
  "id": "...",
  "name": "...", "intent": "what this checks and why",
  "setup":  { ... },   // the stubbed "world" the agent is given, inline
  "prompt": "...",     // the dry-run instruction (see below)
  "assertions": [ "checkable statements about the output" ]
}
```

## How to run — dry-run / file-based stubbing

These are **connector-free on purpose**: evals must be deterministic and
side-effect-free — no real Slack posts, calendar events, or canvas writes. The plugin
itself uses the **Slack** and **Google Calendar** connectors (Slack for the channel
conversation + the canvas state, Calendar for the lunch invites; no Drive), but the
evals stub both out: the world is supplied as data in `setup`, and the agent is told
to **report what it would do instead of doing it**.

- **Messenger evals:** invoke the `lunch-messenger` agent directly (Task /
  `subagent_type: lunch-messenger`) with `setup` rendered into its prompt and the
  Slack tools withheld/stubbed; grade its returned JSON **and** the would-be posts
  it reports against `assertions`.
- **Orchestrator / integration evals:** invoke the skill with `setup` materialized
  as the working-dir files (`setup.state` — the stored canvases `config` /
  `participants` / today's `availability` / `rounds`, plus the messenger's SYNC
  return) and the dry-run prompt; grade the artifacts it produces (the availability
  it would write to the canvas, the groups, the `create_event` call(s) for the
  Google Calendar invites, and the NOTIFY instructions — the Slack match messages
  announcing the invite, with `meeting_link` if set and an at-slot reminder when
  `lunch_reminder` is on).

Grade `assertions` with an LLM judge or by hand. Run each scenario a few times and
report **pass-rate ± variance** — single-shot LLM output varies, so one green run
isn't a pass.

## What these are NOT

They don't re-test the deterministic math — Layer 1 owns that. An orchestrator eval
checks that the skill *calls* `to_utc.py` / `schedule.py` and *uses* the result, not
that the arithmetic is correct.
