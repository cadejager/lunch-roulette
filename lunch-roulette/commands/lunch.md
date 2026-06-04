---
description: Run today's lunch roulette — set up a new team, collect availability, or pair people and send invites.
argument-hint: "[setup | collect | pair]  (leave blank to auto-detect the phase)"
---

Run the **lunch-roulette** skill for today.

Phase argument: `$ARGUMENTS`

Interpret it like this:

- `setup` → run **first-time setup** for a new team: confirm the Slack workspace,
  create or pick the intake channel, confirm the Drive folder, capture the
  reference timezone + organizer email, and seed the config and roster. See
  SKILL.md → "First-time setup".
- `collect` → run **Phase A** (collect availability over Slack via the
  `lunch-messenger` agent, build today's availability file in Drive, nudge
  non-responders, onboard new joiners).
- `pair` → run **Phase B** (pair everyone with `scripts/pair.py`, send Google
  Calendar invites, have the `lunch-messenger` DM each person, record history to
  Drive).
- empty / anything else → **auto-detect**: if today's `availability-<DATE>.json`
  doesn't exist in the Drive folder yet, run Phase A; if it exists, run Phase B.
  If it's genuinely ambiguous, ask which phase the user wants.

Follow the skill's normal workflow and guardrails — in particular, never call
Slack tools directly; always go through the `lunch-messenger` subagent.
