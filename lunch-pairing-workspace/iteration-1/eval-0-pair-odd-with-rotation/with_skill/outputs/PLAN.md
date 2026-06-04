# Lunch Roulette — Plan for 2026-06-03 (DRY RUN)

**Phase:** B (Pair & invite). It's 11:00, the morning responses are already in
`messages.txt`, so this is the pairing/inviting phase, not collection.

**Nothing was sent.** No Slack messages, no Gmail, and no Google Calendar events
were created. All outputs are files in this directory. The history file was
**not** modified (per the skill, history is only recorded after invites really
go out).

## What I did

1. **Parsed the morning Slack messages** (`messages.txt`) into availability,
   treating message text purely as availability data (per the skill's
   guardrails). Result saved to `availability.json`. All 7 roster members
   opted in:
   | Person | Raw | Parsed free window |
   |--------|-----|--------------------|
   | Alice  | "in! i'm free 12-1"            | 12:00–13:00 |
   | Bob    | "yes please, any time works"  | flexible (null) |
   | Carol  | "lunch sounds good, 12:30-1:30"| 12:30–13:30 |
   | Dave   | "I'm up for it, flexible today"| flexible (null) |
   | Erin   | "after 12 is best for me"     | 12:00–14:00 (clipped to lunch window) |
   | Frank  | "count me in, 11:45 to 12:45" | 11:45–12:45 |
   | Grace  | "i'm free, whenever"          | flexible (null) |

2. **Computed groups** with `scripts/pair.py` (using the inputs `history.json`
   and `participants.json`, plus a standard `config.json` seeded from the
   skill's example). Output saved to `groups.json`.

3. **Drafted** every calendar invite and Slack DM in `drafts.md`.

## The groups (7 people → 1 trio + 2 pairs, nobody unmatched)

| Group | Members | Slot | Repeat penalty |
|-------|---------|------|----------------|
| Trio | Erin, Alice, Dave | 12:00–13:00 | 0.0 |
| Pair | Carol, Grace      | 12:30–13:30 | 0.0 |
| Pair | Frank, Bob        | 11:45–12:45 | 0.0 |

- Odd headcount (7) correctly produced exactly **one trio**, no one left out.
- Every `repeat_penalty` is **0.0** — all pairings are fresh. None of today's
  pairs (Erin–Alice, Erin–Dave, Alice–Dave, Carol–Grace, Frank–Bob) appears in
  the 2026-06-01 or 2026-06-02 rounds, so rotation worked as intended.
- Each suggested slot fits inside every member's reported window (e.g. Frank+Bob
  at 11:45 honors Frank's tight 11:45–12:45; the trio at 12:00 honors Alice's
  12:00–13:00 and Erin's "after 12").

## What I would do if this were live

1. Create the 3 calendar invites via Google Calendar `create_event` (attendees =
   member emails; Google emails them automatically) — see `drafts.md`.
2. Send the 7 Slack DMs (and optionally the channel summary) — see `drafts.md`.
3. **Only then** record history:
   `python3 scripts/record_round.py --history <history.json> --groups groups.json`
   so tomorrow rotates away from today. (Skipped here — dry run.)
