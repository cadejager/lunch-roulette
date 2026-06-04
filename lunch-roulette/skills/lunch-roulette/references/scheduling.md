# Scheduling the two daily runs (Claude Cowork)

The orchestrator fires twice every workday. In Cowork, set up **two scheduled
tasks** — one per phase. Each task wakes a fresh session with a prompt that names
the phase and triggers this skill.

## Recommended schedule

| Phase | When | Cron (weekdays) | What it does |
|-------|------|-----------------|--------------|
| A — collect & nudge | ~10:00 | `0 10 * * 1-5` | Messenger reads Slack; orchestrator builds today's availability in Drive, nudges non-responders, onboards new joiners |
| B — pair & invite | ~11:00 | `0 11 * * 1-5` | Orchestrator pairs everyone, sends Calendar invites, has the messenger DM people, records history to Drive |

The hour-ish gap gives people nudged at 10:00 time to reply before pairing at
11:00.

## Invocation prompts

Give each task a prompt that names the phase so the skill doesn't have to guess:

- **Phase A:** `Run the lunch-roulette skill — Phase A (collect & nudge) for today.`
- **Phase B:** `Run the lunch-roulette skill — Phase B (pair & invite) for today.`

## Setting them up in Cowork

Create two recurring scheduled tasks (via Cowork's scheduled-tasks feature):

1. **Lunch — collect**, weekdays at 10:00 in the team timezone, prompt = the
   Phase A prompt above.
2. **Lunch — pair**, weekdays at 11:00 in the team timezone, prompt = the Phase B
   prompt above.

Make sure each scheduled session has the **Slack, Google Calendar, and Google
Drive** connectors available — the orchestrator needs Calendar + Drive, and the
`lunch-messenger` subagent it spawns needs Slack.

## Running more than one team at once

Each independent pairing (say, two different teams) is just its own Drive
`drive_folder` plus its own pair of scheduled tasks. Give each its own config with a
distinct `drive_folder` and `slack_intake_channel`, name the scheduled tasks so you
can tell them apart (e.g. "Lunch (design) — collect"), and point each task's prompt
at the same skill. They share the plugin and the `lunch-messenger`; they don't share
data, so histories and rosters stay separate.

## Timezone

Set the scheduled task's timezone to the **reference** timezone (the same value as
`timezone` in `config.json`). That avoids the daylight-saving math entirely.

If your scheduler only fires in UTC, you'll have to convert and adjust twice a
year: e.g. 10:00 `America/New_York` is `0 14 * * 1-5` in winter (EST) and
`0 13 * * 1-5` in summer (EDT). The pairing math always uses `timezone` from
config, so invites land at the right local time regardless — only the *trigger*
time needs aligning.

## One-off / manual runs

You don't need the scheduler to run a phase. Use the `/lunch` command (e.g.
`/lunch setup` to onboard a new team, `/lunch collect` or `/lunch pair`), or just
ask — "run today's lunch roulette" —
and the skill works out the phase from whether today's availability file exists in
Drive yet. Handy for testing, holidays, or catching up after a missed run.
