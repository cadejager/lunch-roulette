# Lunch Pairing — Plan & Run Notes (2026-06-03)

## Mode
**DRY RUN.** Nothing was sent or created. No calls to Google Calendar, Slack, or Gmail. All outputs are files in this `outputs/` folder.

## Inputs used
- `inputs/participants.json` — roster (5 active: Alice, Bob, Carol, Dave, Ivan)
- `inputs/history.json` — prior pairings (2026-06-02: Alice+Carol, Bob+Dave)
- `inputs/messages.txt` — this morning's availability replies

## What I did
1. **Parsed availability** from `messages.txt` → `availability.json`:
   - Alice 11:30–12:30, Bob 11:30–12:30, Carol 13:00–14:00 ("1 to 2pm"), Dave 13:00–14:00, Ivan 12:00–13:00.
   - Everyone on the roster replied; nobody declined.
2. **Computed pairwise overlaps** and applied matching rules:
   - Require ≥30 min of shared availability to pair.
   - Avoid repeating any pairing from `history.json`.
   - Objective: match as many people as possible; break ties by most total shared lunch time.
3. **Selected groups** → `groups.json`:
   - **Alice + Bob** (11:30–12:30, 60 min, new pair)
   - **Carol + Dave** (13:00–14:00, 60 min, new pair; deliberately avoids the Bob+Dave repeat from yesterday)
4. **Identified the unmatched person and why:**
   - **Ivan (12:00–13:00) could not be matched.** With 5 available people, one must be left out. Ivan's window overlaps Alice/Bob by only 30 min and Carol/Dave by 0 min (they merely touch at 13:00). Every arrangement that pairs Ivan breaks a strong 60-min pair, gives Ivan only a 30-min lunch, and still leaves someone else out — strictly worse. So pairing the two 60-min couples and leaving Ivan is the best overall outcome.
5. **Drafted all messages** → `drafts.md`: 2 calendar invites, 4 paired-confirmation Slack DMs, and 1 warm note to Ivan explaining the miss and offering a 1:1 / wider window next time.

## What I would send if this were live
- **Calendar:** 2 invites — Alice+Bob (11:30–12:30) and Carol+Dave (13:00–14:00).
- **Slack:** 4 confirmation DMs (Alice, Bob, Carol, Dave) + 1 friendly unmatched note to Ivan.
- **History update (recommended):** append today's round to `history.json` so Alice+Bob and Carol+Dave aren't repeated next time:
  ```json
  {"date":"2026-06-03","groups":[["alice@org.com","bob@org.com"],["carol@org.com","dave@org.com"]]}
  ```
  (Not written in this dry run since inputs must not be modified.)

## Flag for the human
- One person (Ivan, the newest member, joined 2026-05-20) is unmatched today purely due to a scheduling gap. Consider a manual 1:1 for him this week or nudging him toward a wider window next round.
