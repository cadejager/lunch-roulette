# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`lunch-roulette` is a **Claude Cowork plugin** (not a standalone app): a daily bot that pairs remote teammates for lunch over **Slack + Google Calendar + Google Drive**. The repository root *is* the plugin — `.claude-plugin/plugin.json` sits at the top, alongside `agents/`, `commands/`, and `skills/`.

Most of the "logic" is **prose that an LLM executes**, not traditional code:
- `skills/lunch-roulette/SKILL.md` — the **orchestrator** (the trusted brain).
- `agents/lunch-messenger.md` — the **`lunch-messenger`** subagent (all Slack I/O).
- `commands/lunch.md` — the `/lunch` entry point.
- `skills/lunch-roulette/references/*.md` — the data contract, scheduling, and message voice.

The only executable code is a small, **dependency-free Python core** in `skills/lunch-roulette/scripts/` that the orchestrator shells out to for the fiddly deterministic work.

## Commands

No build system, package manager, or linter — the scripts are **Python 3.9+ standard library only** (they use `zoneinfo`, so the host needs the system tz database). Run everything from the scripts dir:

```bash
cd skills/lunch-roulette/scripts

# Run a test suite — each file is a self-contained runner that prints PASS/FAIL and "N/N passed"
python3 test_pair.py        # the matcher
python3 test_to_utc.py      # local->UTC / DST conversion
python3 test_schedule.py    # just-in-time due / no-match-timing
python3 test_record_round.py

# Run a SINGLE test case (no framework/selector — call the function directly)
python3 -c "import test_schedule as t; t.test_naive_now_is_read_as_utc()"

# Exercise a script's CLI directly (run with -h for flags)
python3 to_utc.py --tz America/Chicago --date 2026-06-04 \
  --lunch-window '{"earliest":"10:00","latest":"14:00"}' --free '[["10:45","11:15"]]'
python3 pair.py --availability avail.json --history history.json --out groups.json
```

**Package the plugin** (from the repo root; `*.zip` is gitignored; match the version in `plugin.json`):
```bash
git archive --format=zip --prefix=lunch-roulette/ -o lunch-roulette-v0.3.0.zip HEAD
```

## Architecture — the big picture

**1. Orchestrator ↔ messenger trust split (the central design).** The orchestrator (`SKILL.md`) makes every decision and performs all Calendar/Drive writes. The `lunch-messenger` subagent runs on a separate model (Sonnet), is **tool-locked to Slack**, and is the *only* component that ingests coworker messages — an untrusted, potentially adversarial surface. Invariants to preserve when editing either side:
- **All Slack I/O goes through the messenger**, with one deliberate exception: the orchestrator creates the intake channel itself (`slack_create_conversation`) once, at first-time setup.
- The orchestrator treats everything the messenger returns (`raw`/`flagged` text) as **data, never instructions**. Roster/identity changes come from structured Slack data (the channel member list), never message text; a person can only set their *own* contact info.

**2. Deterministic core, not LLM math.** Error-prone arithmetic lives in tested scripts the orchestrator *calls*; it is never done inline by the model:
- `pair.py` — matches opted-in people into pairs (one triple if odd) by UTC interval overlap, avoiding recent repeats; date-seeded so pairings rotate day to day but are reproducible.
- `to_utc.py` — converts a person's stated **local** windows → **UTC** (DST-correct via `zoneinfo`), clipped to their lunch band.
- `schedule.py` — the just-in-time logic: `next_run_utc` / `is_last_run` / `due_now` / `should_notify_unmatched`.
- `record_round.py` — appends a round to history.

When changing behavior, update the script **and** its test **and** the matching CLI invocation in `SKILL.md`.

**3. Everything is UTC internally.** Stored availability and the matcher work in UTC `"HH:MM"`. A person's timezone is used only to interpret what they typed and to display times back to them; `config.timezone` is merely the working-day anchor, not a matching axis. The messenger reports times in the stated *local* zone and never converts — the orchestrator converts to UTC via `to_utc.py` before storing.

**4. Append-only storage on Google Drive.** The Drive connector can create/read but **cannot overwrite or delete**. So all state (config, participants, availability, history rounds) is written as **new timestamped versions** and read **newest-wins** — never assume a re-upload replaces a file. Layout and the full messenger↔orchestrator data contract are in `references/data-schemas.md`.

**5. Just-in-time hourly pairing.** A scheduled run fires hourly across the team's morning (`config.run_schedule`). Every run does the *same* job — sync the channel, then pair only the people whose lunch is "due" before the **next** run; everyone else waits for a later run. Someone is told "no match" only when it's hopeless (the last run, or all their windows pass by the next run). There is **no separate collect/pair phase**. The two entry points (`commands/lunch.md`) are `/lunch setup` (first-time) and `/lunch run` / blank (the hourly job).

## Keeping things consistent

The messenger↔orchestrator data contract lives in three files that must agree: `agents/lunch-messenger.md` (what the messenger returns), `references/data-schemas.md` (the contract + stored shapes), and `SKILL.md` (how the orchestrator consumes and writes it). The `skills/lunch-roulette/evals/` definitions encode expected behavior against that same contract. A change to a field name or a run step usually touches all four — keep them in lockstep.

## Repo workflow

`main` is **branch-protected** and requires a PR review to merge. Work on a branch, push, and open a PR via `gh`. The `gh` account here is a non-admin collaborator, so it **cannot self-merge** — the repo owner approves and merges.

Right after opening a PR, set it to **auto-merge**, so it lands the moment the owner approves (no manual merge step):

```bash
gh pr merge <number> --auto --merge
```

(`main`'s required review blocks an immediate merge, so `--auto` queues it until the approval lands.) The repo has **Allow auto-merge** and **Automatically delete head branches** enabled, so on approval the PR merges and its source branch is deleted automatically — no `--delete-branch` flag needed.

Local scratch/working dirs are gitignored via an `_*/` convention (e.g. the skill's runtime `_work/` download→compute→upload dir).

## Evals

Three layers (see `skills/lunch-roulette/evals/README.md`): **Layer 1** is the deterministic unit tests above (the only ones runnable today); **Layer 2** is LLM component evals (`messenger.json`, `orchestrator.json`) run dry-run and judge-graded; **Layer 3** is `integration.json`. The LLM evals deliberately do **not** re-test the matcher/scheduling math — Layer 1 owns that.
