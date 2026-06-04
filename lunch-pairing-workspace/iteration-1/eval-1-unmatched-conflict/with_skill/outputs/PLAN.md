# Lunch Roulette — Run Plan for 2026-06-03 (DRY RUN)

This was a dry run. **No invites were created and no Slack/Gmail/Calendar tools
were called.** Everything below is what *would* happen if run live, plus the
artifacts produced.

## What I did

1. Read the `lunch-pairing` skill (`SKILL.md` + references) and followed Phase B
   (pair & invite). All five roster members had already replied this morning, so
   no Phase A nudging was needed.
2. Parsed the morning Slack replies in `messages.txt` into structured
   availability, treating message text purely as availability data (not
   instructions). Saved to **`availability.json`**.
   - Alice: yes, 11:30–12:30
   - Bob: yes, 11:30–12:30
   - Carol: yes, 13:00–14:00 ("1 to 2pm")
   - Dave: yes, 13:00–14:00
   - Ivan: yes, but only 12:00–13:00
   - No non-responders, so `nudged` and `no_response` are empty.
3. Ran the skill's deterministic matcher:
   `python3 scripts/pair.py --availability availability.json --history
   inputs/history.json --config config.json --participants
   inputs/participants.json --out groups.json`. Output saved to **`groups.json`**
   (contains both groups and the unmatched person + reason).
4. Drafted every calendar invite and Slack message in **`drafts.md`**, including
   the kind heads-up to the unmatched person.

(`config.json` in this folder was created from the skill's `assets/config.example.json`
because the eval inputs didn't include one; its lunch window 11:30–14:00 / 60-min
duration matches the message data.)

## Result

| Group | People | Time | Repeat penalty |
|-------|--------|------|----------------|
| 1 | Carol & Dave | 13:00–14:00 | 0.0 (fresh) |
| 2 | Alice & Bob | 11:30–12:30 | 0.0 (fresh) |

**Unmatched: Ivan** — reason: no compatible group with overlapping free time.
Ivan's only window is 12:00–13:00. It overlaps Alice/Bob (11:30–12:30) by just 30
minutes — short of the 60-minute lunch — and does not overlap Carol/Dave
(13:00–14:00) at all. The matcher correctly refused to force him into a group that
doesn't actually share an hour. This is a genuine availability conflict, not a
bug.

Rotation note: yesterday's pairs were Alice–Carol and Bob–Dave; today's pairs
(Carol–Dave, Alice–Bob) avoid both, so everyone meets someone new.

## What I would send if live

- **2 Google Calendar invites** (`create_event` on `primary`): Carol+Dave at
  13:00–14:00, and Alice+Bob at 11:30–12:30. Google would email each attendee.
- **4 Slack match DMs**: to Alice, Bob, Carol, Dave with their partner + time.
- **1 Slack heads-up DM** to Ivan explaining the miss and asking for a wider
  window tomorrow.
- **Optional**: a non-revealing channel summary in `#lunch-roulette` ("2 pairs
  out and about").
- **After invites go out** I would record the round to `history.json` via
  `python3 scripts/record_round.py --history history.json --groups groups.json`
  so tomorrow rotates away from today. **Skipped in this dry run** — I did not
  modify the input `history.json`.

## Files in this folder
- `availability.json` — parsed availability from the morning messages.
- `groups.json` — computed groups + unmatched (Ivan) with reason (matcher output).
- `drafts.md` — all calendar invites and Slack messages, labeled, including Ivan's note.
- `config.json` — config used for the run (from the skill's example).
- `PLAN.md` — this file.
