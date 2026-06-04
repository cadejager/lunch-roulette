# Lunch Matching — Morning Collect & Onboard

**Date:** 2026-06-03  ·  **Snapshot:** ~10:00  ·  **Mode:** DRY RUN (nothing sent, no calendar events, no pairing)

## What I did

1. Read the roster (`participants.json`), prior rounds (`history.json`), and this
   morning's Slack messages (`messages.txt`).
2. Parsed each message into an availability status and built `availability.json`.
3. Cross-referenced the roster against who has replied to find non-responders.
4. Identified one sender (Nina) who is **not on the roster** and asked to join.
5. Drafted Slack messages (`drafts.md`): nudges for the three quiet folks plus an
   onboarding reply to Nina that also collects her details and today's availability.
6. Did **not** pair anyone — that's explicitly a later step.

## Today's status (roster = 6)

| Person | On roster | Status      | Window   | Source |
|--------|-----------|-------------|----------|--------|
| Alice  | yes       | IN          | 12:00–1:00 | replied 09:20 |
| Bob    | yes       | OUT         | —        | replied 09:25 (dentist) |
| Carol  | yes       | IN          | flexible | replied 09:31 |
| Dave   | yes       | no response | —        | nudge drafted |
| Erin   | yes       | no response | —        | nudge drafted |
| Frank  | yes       | no response | —        | nudge drafted |
| Nina   | **no**    | wants to join | —      | replied 09:50; onboarding drafted |

- **Confirmed in:** Alice, Carol (2)
- **Out:** Bob (1)
- **Still need to hear from:** Dave, Erin, Frank (3)
- **New / not yet on roster:** Nina (1) — needs email + slack_id confirmed before
  being added to `participants.json`; also hasn't given today's availability yet.

## What I would send if live (NOT sent)

- **Nudges** to Dave, Erin, and Frank asking "in or out?" (+ time window if in),
  noting pairings are being finalized soon. Full text in `drafts.md`.
- **Onboarding reply** to Nina: welcome her, confirm this is the lunch group, ask
  for her email and consent to recurring matching, and ask if she's free today so
  she can be folded into this round if she replies quickly. Full text in `drafts.md`.

## Onboarding Nina (proposed, not applied)

Suggested roster entry, to be completed once she confirms details:

```json
{ "name": "Nina", "email": "<TBD>", "slack_id": "<TBD>", "slack_username": "nina",
  "active": true, "joined": "2026-06-03" }
```

Did not modify `participants.json` (input files are read-only). The proposed entry
is also recorded under `new_participant_proposed_roster_entry` in `availability.json`.

## Notes / assumptions

- Bob is OUT and would be excluded from today's pairing.
- Carol is flexible; Alice wants 12–1, which overlaps fine for a later pairing step.
- History shows yesterday's (06-02) pairs were Alice–Dave, Bob–Erin, Carol–Frank.
  Relevant later for pairing novelty, not used now since pairing is out of scope.
- Nina's availability for today is still unknown; if she doesn't reply before the
  pairing step, she'd be onboarded but held for the next round.

## Outputs in this folder

- `availability.json` — parsed availability + proposed roster entry for Nina.
- `drafts.md` — all draft Slack messages, labeled by recipient.
- `PLAN.md` — this file.
