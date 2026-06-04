# Data schemas

Every file is plain JSON, stored in the Google Drive folder named by
`drive_folder` (default `lunch-roulette/`) and downloaded to a local working dir
per run (see SKILL.md → "Where the data lives"). Times are `"HH:MM"` 24-hour. The
stored availability and the matcher work entirely in the **reference timezone**
(`config.timezone`); each person's own timezone lives on their roster entry and is
used only to interpret and convert what they type. Dates are `"YYYY-MM-DD"`.

## config.json

```json
{
  "timezone": "America/New_York",
  "drive_folder": "lunch-roulette",
  "slack_intake_channel": "#lunch-roulette",
  "collect_time": "10:00",
  "pair_time": "11:00",
  "lunch_window": { "earliest": "11:30", "latest": "14:00" },
  "default_lunch_duration_min": 60,
  "max_group_size": 3,
  "novelty_window_days": 14,
  "organizer_email": "you@org.com",
  "calendar_id": "primary"
}
```

- **timezone** — the **reference timezone**. The lunch window, the matcher, the
  stored availability, and the calendar invites all live on this single axis. It's
  also the zone assumed for anyone whose own `timezone` is unknown. People in other
  zones are handled per-person (see participants.json): their stated times are
  converted into this reference zone before matching.
- **lunch_window** — the outer bounds the bot will ever schedule lunch within,
  expressed in the reference `timezone`. Self-reported free times are normalized to
  the reference zone and then clipped to this.
- **novelty_window_days** — how far back the matcher looks to avoid repeats.
  A pairing inside this window is penalized; more recent = heavier penalty.
- **max_group_size** — keep at 3. The matcher only makes a three when the count
  is odd.

## participants.json (the roster)

```json
{
  "participants": [
    {
      "name": "Alice Rivera",
      "email": "alice@org.com",
      "slack_id": "U01ALICE",
      "slack_username": "alice",
      "timezone": "America/New_York",
      "active": true,
      "joined": "2026-06-01"
    }
  ]
}
```

- **email** is the identity used everywhere (matching, history, invites). It must
  be the address on the person's Google Calendar.
- **slack_id** is what you DM; **slack_username** is for human-readable logs.
- **timezone** is the person's home zone — how to read the bare times they type
  ("free 12–1" means noon in *their* zone). Captured at onboarding. If they name a
  zone in a message (e.g. while travelling), that overrides it for that day. If
  it's missing and a time is ambiguous, ask rather than guess.
- **active: false** means opted out — kept for history, never nudged or paired.

## history.json

```json
{
  "rounds": [
    {
      "date": "2026-06-02",
      "groups": [
        ["alice@org.com", "bob@org.com"],
        ["carol@org.com", "dave@org.com", "erin@org.com"]
      ]
    }
  ]
}
```

Groups are lists of emails. `scripts/record_round.py` maintains this — append the
day's groups after invites go out. One entry per date (re-running replaces it).

## availability-YYYY-MM-DD.json

Written in Phase A, read in Phase B. Built by the orchestrator from the
`lunch-messenger` agent's COLLECT return; stored in the Drive folder. **All `free`
windows here are in the reference `timezone`** — the orchestrator converts each
person's stated times (read in their home timezone, or a zone they named in the
message) into the reference zone before writing this file, so the matcher only ever
sees one zone.

```json
{
  "date": "2026-06-03",
  "responses": [
    {
      "email": "alice@org.com",
      "wants_lunch": true,
      "free": [["12:00", "13:00"]],
      "tz": "America/New_York",
      "raw": "free 12-1!",
      "responded_at": "2026-06-03T09:40:00-04:00"
    },
    {
      "email": "bob@org.com",
      "wants_lunch": true,
      "free": null,
      "raw": "any time works",
      "responded_at": "2026-06-03T09:42:00-04:00"
    }
  ],
  "nudged": ["carol@org.com"],
  "no_response": ["dave@org.com"]
}
```

- **wants_lunch: false** → excluded from pairing entirely.
- **free: null or []** → fully flexible (free across the whole lunch window).
- **free: [["12:00","13:00"], ...]** → one or more windows; the matcher needs an
  overlap of at least `default_lunch_duration_min` to put two people together.
- **tz** — the timezone the `free` windows were originally given in (the person's
  home zone, or one they named that day). Audit only — `free` is already in the
  reference zone, so the matcher ignores `tz`. Handy when a parse looks wrong.
- **raw** — keep the original message; useful when a parse looks wrong.
- **nudged / no_response** — bookkeeping so you don't nudge the same person twice.

## groups-YYYY-MM-DD.json (output of pair.py)

```json
{
  "date": "2026-06-03",
  "groups": [
    {
      "members": [
        { "email": "alice@org.com", "name": "Alice Rivera",
          "slack_id": "U01ALICE", "slack_username": "alice" }
      ],
      "suggested_slot": { "start": "12:00", "end": "13:00" },
      "repeat_penalty": 0.0
    }
  ],
  "unmatched": [
    { "email": "frank@org.com", "name": "Frank",
      "slack_id": "U09FRANK", "slack_username": "frank",
      "reason": "no compatible group with overlapping free time" }
  ]
}
```

- **suggested_slot** — the earliest block of `default_lunch_duration_min` inside
  every member's overlapping free time. Use it for the calendar invite. Null only
  if something is off; fall back to the start of the lunch window.
- **repeat_penalty** — 0 means a fresh pairing; higher means the matcher had to
  reuse a recent pairing because nothing better fit. Informational.
- **unmatched** — people who couldn't be placed, each with a reason. Handle these
  kindly (see SKILL.md Phase B).
