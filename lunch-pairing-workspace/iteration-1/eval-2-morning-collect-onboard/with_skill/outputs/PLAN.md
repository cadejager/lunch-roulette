# Lunch roulette — Phase A plan (2026-06-03, ~10:00)

> DRY RUN. Nothing sent; no calendar events created. Drafts and availability are files only.

## What phase this is

**Phase A — Collect & nudge** (runs around the 10:00 collect time). It's ~10:00, today's
availability file did not exist yet, and lunch (window 11:30–14:00, pair time ~11:00) hasn't
arrived. So we collect responses, onboard unknown senders, and nudge non-responders.
**No pairing and no calendar invites** — that's Phase B (~11:00), to run later.

Config used (from skill assets / defaults): timezone America/New_York (EDT, -04:00),
lunch window 11:30–14:00, default lunch 60 min.

## Responses collected so far

| Person | Slack | Wants lunch? | Free | Source |
|--------|-------|--------------|------|--------|
| Alice  | @alice (U1) | Yes | 12:00–13:00 | "in, 12-1" |
| Bob    | @bob (U2)   | No  | —           | "out today, got a dentist appt" (opt-out for today) |
| Carol  | @carol (U3) | Yes | flexible (null) | "yes! flexible whenever" |

In the pool so far for today: **Alice, Carol** (Bob is out).

## Who we still need to hear from (nudged this run)

- **Dave** (@dave, U4) — no response → nudged
- **Erin** (@erin, U5) — no response → nudged
- **Frank** (@frank, U6) — no response → nudged

Recorded in `availability.json` under `nudged` so the next run won't ping them twice.
(Note: SKILL.md says to prioritize people who look online/active in Slack. No Slack
presence tool was available in this dry run, so all three non-responders were nudged.)

## New person to onboard

- **Nina** (@nina) messaged "hey is this the lunch buddies thing? can I join?" — not on
  the roster. Onboarding reply drafted asking for her **work email** only. She is tracked
  under `pending_onboarding` in `availability.json`, status `awaiting_email`.
- **Not yet added to `participants.json`** and **not in today's pool** — per the skill,
  she's appended to the roster (active: true, joined: 2026-06-03) and folded into today's
  availability only after she replies with an email and a time. A queued follow-up message
  is drafted for that moment.

## What I would send if live

1. Nudge DMs to **Dave, Erin, Frank** (drafts in `drafts.md`).
2. Onboarding email-request DM to **Nina** (draft in `drafts.md`); then, on her reply,
   the queued "you're in" follow-up and add her to `participants.json`.
3. Nothing to Alice/Bob/Carol — they already answered (Bob opted out today).

## Next phase (later, ~11:00 — do NOT do now)

Phase B: load `availability-2026-06-03.json`, run `scripts/pair.py` against `history.json`
+ `participants.json` + `config.json`, create one Google Calendar invite per group, DM
matches, then record the round with `scripts/record_round.py`. Yesterday (2026-06-02)
paired alice–dave, bob–erin, carol–frank, so the matcher will rotate away from those.
