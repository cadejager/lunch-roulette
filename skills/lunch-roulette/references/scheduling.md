# Scheduling the daily runs (Claude Cowork)

The orchestrator fires **hourly across the morning**. Each run is the same job —
sync the channel, then pair anyone whose lunch is imminent (see SKILL.md → "The
daily run"). There is no separate collect/pair phase anymore; pairing happens just
in time, so early timezones get matched while later ones are still waking up.

## The host timezone anchors everything

The team has **no single timezone**, so we don't try to track a "team zone." Instead
everything is anchored to the **host** — the machine that fires the scheduled task:

- `config.timezone` is the **host's** IANA zone. It decides which calendar day
  "today" is and is the per-person fallback when someone's own zone is unknown.
- `config.run_schedule.tz` is the **host zone too**, so `schedule.py`'s just-in-time
  logic and the cron agree **by construction** — no offset to guess, no drift.

Setup detects the host zone and writes it to both fields (see SKILL.md → "First-time
setup").

## When it should run

The default `config.run_schedule` is **hourly, 07:40–11:40 in the host zone**:

```json
"run_schedule": { "tz": "<host zone>", "from": "07:40", "to": "11:40", "every_min": 60 }
```

That's five fires — 07:40 / 08:40 / 09:40 / 10:40 / 11:40 host-local — covering a
normal working morning. It's **configurable at setup**: widen `from`/`to` (or change
`every_min`) if the team spreads across far-apart zones and you want the window to
reach earlier risers or later coasts.

**Match the cron to the schedule** — don't leave it over-broad. A fire that lands
*after* the last scheduled run (e.g. a stray extra hour on the cron, or jitter that
pushes a fire well past `to`) is NOT a harmless no-op by accident: `is_last_run` is
True for *any* time at/after the last fire, so an unchecked late fire would be treated
as "the last run" and would sweep + finalize "no match" for people whose lunch is
still hours away. `schedule.py` exposes the signal to guard against this:
`within_active_window` is True only when the fire falls inside
`[first_run − grace, last_run + grace]` (grace ≈ 15 min). The orchestrator should
read it at the top of a run and **no-op** when it is False — not re-pairing anyone or
finalizing any "no match", and waiting for the next legitimate fire. With that guard
in place an over-broad cron is *tolerated* (the extra fires are dropped), but it is
still wasted work; size the cron to the window.

## Cowork runtime caveats (important)

- **Cron fires in the host machine's local timezone**, not a per-task one. Because
  `run_schedule.tz` *is* the host zone, the cron times **equal the `run_schedule`
  times directly — no offset math.** For the 07:40–11:40 default the cron is simply
  `40 7-11 * * 1-5`. (This removes the old silent-failure risk where the schedule
  was on a "team zone" and someone had to hand-offset the cron to the host zone and
  could quietly get it wrong.)
- **Firing drifts by up to ~10 minutes** (dispatch jitter). Jitter *within* the
  window is absorbed comfortably by the hourly cadence and the just-in-time pairing
  (which only matches people whose lunch is still an hour+ out), and invites land at
  the right local time regardless because all the math is in UTC. For the **last**
  fire specifically, the `within_active_window` grace (≈ 15 min, above) covers a
  slightly-late dispatch so it still counts as the in-window last run rather than a
  dropped stale fire.

## Setting it up in Cowork

Create **one recurring scheduled task**, at the host-local times matching
`run_schedule` (the default `40 7-11 * * 1-5`), with the **minimal** prompt:

> `Run the lunch-roulette skill for today.`

(No phase argument, and **no inlined config** — every run is the same job, and the
orchestrator reads the current config from its Slack canvas at run time, so the
channel, timezone, window, and schedule all live in one place and can't drift.)
Create this task **only after the plugin install is confirmed** — a schedule made
before the plugin is registered fires background sessions with no skill/messenger and
can't pair. Make sure the scheduled session has the **Slack** connector available —
that's the only one needed now: the orchestrator stores all state in Slack canvases,
and the `lunch-messenger` it spawns needs Slack too.

## Running more than one team at once

Each independent pairing is its own `state_namespace` + intake channel + its own
scheduled task. Give each its own `config.json` with a distinct `state_namespace`,
`channel_id`, and `run_schedule`, and name the tasks so you can tell them apart
(e.g. "Lunch (design)"). They share the plugin and the `lunch-messenger`; they don't
share data, so rosters and histories stay separate.

## One-off / manual runs

You don't need the scheduler to run. Use `/lunch` (or `/lunch setup` to onboard a
new team), or just ask — "run today's lunch roulette." Handy for testing, holidays,
or catching up after a missed run; a manual run does exactly what a scheduled one
does.
