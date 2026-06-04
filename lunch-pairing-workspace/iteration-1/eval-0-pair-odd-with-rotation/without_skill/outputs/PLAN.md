# Lunch Roulette Plan — 2026-06-03 (DRY RUN)

## What I did
1. **Parsed availability** from `inputs/messages.txt`. All 7 active roster members opted in.
   - Alice 12:00–13:00, Carol 12:30–13:30, Frank 11:45–12:45 (explicit windows);
     Erin "after 12" (lower bound 12:00); Bob, Dave, Grace open ("any time"/"flexible"/"whenever").
   - Saved to `availability.json`.
2. **Built recent-pair history** from `inputs/history.json` for the last 2 rounds (06-01, 06-02)
   and listed every pair to avoid this round.
3. **Computed groups** (`groups.json`). 7 is odd → two pairs + one trio. Constraints applied:
   - Do not re-pair anyone who shared a group in the last 2 rounds.
   - Rotate the trio: Frank and Grace were in the trio both prior rounds, so this round
     Frank moves to a pair; Grace stays in a trio but with two brand-new partners.
   - Pick each group's time from the intersection of its members' stated windows.
   - Result (zero recent-repeat collisions, all time-feasible):
     - Pair: **Alice + Frank** @ 12:00–12:45
     - Pair: **Dave + Erin** @ 12:15–13:00
     - Trio: **Bob + Carol + Grace** @ 12:30–13:30
   - Unmatched: none.
4. **Drafted** all calendar invites and per-person Slack messages in `drafts.md`.

## What I would send if live
- **3 Google Calendar events** (one per group) with the summaries, attendee emails, and
  start/end times listed in `drafts.md`. No event was created.
- **7 Slack DMs** (one per participant) with the text in `drafts.md`, addressed by slack_id /
  username from `participants.json`. No message was sent.

## Notes / judgment calls
- There is no single time slot that satisfies Alice, Carol, and Frank simultaneously
  (Carol starts 12:30, Frank ends 12:45), so I timed **each group independently** rather than
  forcing one global slot. Every member's stated constraint is respected.
- "After 12" (Erin) treated as a soft lower bound with no end; placed at 12:15–13:00.
- This was a DRY RUN: no Google Calendar, Slack, or Gmail calls were made; outputs are files only.
