# Scheduling the daily runs (Claude Cowork)

The orchestrator fires **hourly across the team's morning**. Each run is the same
job — sync the channel, then pair anyone whose lunch is imminent (see SKILL.md →
"The daily run"). There is no separate collect/pair phase anymore; pairing happens
just in time, so early timezones get matched while later ones are still waking up.

## When it should run

The ideal window is **8:00 in the earliest participant's timezone through ~noon in
the latest participant's timezone**, every hour. For a team spanning US Eastern and
Pacific that's 8:00 ET → 12:00 PT, i.e. five-ish hourly fires.

For simplicity, the default `config.run_schedule` is **hourly, 08:00–12:00 in the
team's `timezone`** (e.g. ET):

```json
"run_schedule": { "tz": "America/New_York", "from": "08:00", "to": "12:00", "every_min": 60 }
```

Widen `to` (and/or set `tz` thinking) at setup if the team reaches far-west zones.
Each run also **no-ops if it fires outside the active window**, so an over-broad cron
is harmless.

## Cowork runtime caveats (important)

- **Cron fires in the machine's local timezone**, not a per-task one — whatever zone
  the computer running the session is on. Write the cron relative to *that* zone and
  offset from the team zone yourself. Example: team on ET, machine on Mountain →
  08:00–12:00 ET is **06:00–10:00 MT**, so `0 6-10 * * 1-5`.
- **Firing drifts by up to ~10 minutes** (dispatch jitter). The hourly cadence and
  the just-in-time pairing (which only matches people whose lunch is still an hour+
  out) absorb this comfortably, and invites land at the right local time regardless
  because all the math is in UTC.

## Setting it up in Cowork

Create **one recurring scheduled task** that fires hourly across the active window,
with the prompt:

> `Run the lunch-roulette skill for today.`

(No phase argument — every run is the same job.) Make sure the scheduled session has
the **Slack, Google Calendar, and Google Drive** connectors available: the
orchestrator needs Calendar + Drive, and the `lunch-messenger` it spawns needs Slack.

## Running more than one team at once

Each independent pairing is its own Drive `drive_folder` + intake channel + its own
scheduled task. Give each its own `config.json` with a distinct `drive_folder`,
`channel_id`, and `run_schedule`, and name the tasks so you can tell them apart
(e.g. "Lunch (design)"). They share the plugin and the `lunch-messenger`; they don't
share data, so rosters and histories stay separate.

## One-off / manual runs

You don't need the scheduler to run. Use `/lunch` (or `/lunch setup` to onboard a
new team), or just ask — "run today's lunch roulette." Handy for testing, holidays,
or catching up after a missed run; a manual run does exactly what a scheduled one
does.
