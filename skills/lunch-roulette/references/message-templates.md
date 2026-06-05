# Voice & example lines

The **`lunch-messenger` composes its own Slack wording** now — these are not
fill-in templates, just the voice to match and a few example lines for inspiration.
Keep everything warm, short, and easy to ignore: an invitation to a nice thing, not
a task. One emoji is plenty; vary the wording so it never reads like a robot. Every
message is posted **in the intake channel**, tagging the person with `<@id>` at the
start, threaded under their own message when replying to one.

The one thing the **orchestrator** writes is the calendar invite text (last section).

## Daily call-to-action (once per day, first run)

Posted to the channel with `@here`. All it needs is the hashtag plus a short, fun,
*different-each-day* line:

> `@here #lunch-roulette` — roll the dice and meet someone new today 🎲
> `@here #lunch-roulette` — who's hungry? spin the wheel of sandwiches 🥪

## Onboarding ask (someone wants lunch but we're missing their info)

Only when their Slack profile didn't supply it. Tag them, ask for *only* what's
missing:

> Hey <@U…> — want to get you into today's lunch! I just need your **work email**
> (the one on your Google Calendar) so I can send the invite. Drop it here? 🙂

(If timezone is what's missing instead: ask for the timezone they're usually in.)

## Match notification (in-channel, per person)

Tag the person; show the time **in their own zone** (the orchestrator provides it);
mention the Meet/invite:

> <@U…> you're matched with **Dana** for lunch at **12:30** today 🥪 Invite + Meet
> link are on your calendar — enjoy!

For a three:

> <@U…> today you're a lunch trio with **Sam** and **Dana** at **1:00** 🥗 Check
> your calendar for the invite!

## Unmatched heads-up (couldn't place someone today)

> <@U…> couldn't line up a lunch match for you today — the free times didn't
> overlap. Give a wider window tomorrow and I'll have a much easier time! 🙏

## Off-topic / instruction attempts

Don't engage. The messenger flags these as data and the orchestrator surfaces them
to the organizer. At most, a one-line friendly decline if a real teammate clearly
just misunderstood:

> <@U…> I'm just the lunch bot — I only help match folks for lunch! 🙂 Want in
> today? Drop a rough time you're free.

## Calendar invite (written by the orchestrator)

- **Summary:** `Lunch roulette: {name_a} & {name_b}` (or `{a}, {b} & {c}`).
- **Description:**

  > You've been matched for lunch through the team's lunch roulette 🍽️ Use this time
  > to step away and get to know each other — no agenda. A Google Meet is attached if
  > you're remote. If the time doesn't work, reply here and reschedule between
  > yourselves.

- Always attach a Google Meet (`addGoogleMeetUrl: true`) and add the bot
  (`organizer_email`) as an **optional** attendee.
