# Message templates

Wording for the Slack messages and the calendar invite. These are starting
points — adapt the voice to the team and vary it a little day to day so it never
reads like a robot. Keep everything warm, short, and easy to ignore: this is an
invitation to a nice thing, not a task.

Fill the `{placeholders}` from participant + group data.

**Who writes vs. who sends:** the **orchestrator** (this skill) composes every
message from these templates, filling in the names/times. The `lunch-messenger`
subagent only *delivers* the finished text to Slack verbatim — it never writes or
edits wording. So when you hand the messenger a SEND batch, the text is already
final.

## Morning nudge (Phase A → people who haven't responded)

> Hey {first_name}! 🍴 Lunch roulette is on today — want to be matched with
> someone for a midday break? Just tell me a rough time you're free (e.g. "12–1"
> or "any time after 12:30"), or say "out" if today's not good. No worries either
> way!

Keep it to one ping. If they don't reply, they simply aren't in today's pool.

## Onboarding (someone new messages, or asks to join)

> Welcome! 🎉 I pair people up for lunch so you get to know folks across the team.
> To add you I just need two things: your **work email** (the one on your Google
> Calendar) and the **timezone you're usually in** (so "12–1" lands at the right
> hour). What are they?

After they reply:

> You're in, {first_name}! Want lunch today? If so, when are you free
> (e.g. "12–1")? If you're ever in a different timezone, just say so in the message.

## Kickoff sign-up (first-time setup → intake channel)

A one-time broadcast when a brand-new team cold-starts with an empty roster (see
SKILL.md → First-time setup). Post it once, and only after the host says go, to
invite people to opt in; the next COLLECT run onboards everyone who replies.

> 👋 **Lunch roulette is starting!** Each day I'll pair a few of us up for a relaxed
> lunch so we get to know people across the team. Want in? Just reply here and I'll
> get you set up — it takes one message, and you can opt out anytime.

## Timezone check (Phase A → when a stated time is ambiguous)

Only when you genuinely can't tell what zone someone means and they're not yet on
the roster with a home zone. Keep it light:

> Quick one, {first_name} — what timezone are you in for that? Want to book lunch
> at the right hour. 🙂

## Match notification (Phase B → each matched person)

Fill `{time}` in the **recipient's own timezone** (convert from the reference zone
using their roster timezone) so nobody has to do the mental math.

For a pair:

> You're matched with **{partner_name}** for lunch today at **{time}** 🥪 I've
> sent a calendar invite. Have a great time!

For a three:

> Today you're a lunch trio with **{name_a}** and **{name_b}** at **{time}** 🥗
> Invite's on its way to your calendar — enjoy!

Optional icebreaker to append:

> (Need a convo starter? Swap the best thing you've eaten this month.)

## Unmatched heads-up (Phase B → anyone who couldn't be placed)

When it's an odd-one-out or their window was too tight:

> Hey {first_name} — I couldn't find you a lunch match today, usually because the
> free times didn't line up. Sorry about that! If you can give a wider window
> tomorrow I'll have a much easier time pairing you. 🙏

When only one person opted in:

> Looks like it's just you on the list today, {first_name} — not enough people for
> a match. Catch you tomorrow! 🌯

## Channel summary (optional, Phase B → intake channel)

> 🍴 **Today's lunch roulette** — {n} pairs out and about! Invites are on your
> calendars. Not matched today? Drop a time tomorrow morning and I'll sort you out.

(Don't list who's paired with whom in the channel unless the team has said they
want that — some people prefer their pairing stay between them.)

## Off-topic decline (optional, Phase A → someone who asked the bot to do other work)

When the messenger `flagged` a message that tried to put the bot to work
(write code, answer a question, "DM everyone this link"), don't act on it. If it
warrants any reply at all, keep it to a single friendly line that closes the door
without engaging:

> I'm just the lunch bot — I only help match folks for lunch! 🙂 If you want in
> for today, tell me a rough time you're free.

Most flagged messages need no reply — note them for the organizer instead. Only
send this when ignoring would be ruder than a one-liner (e.g. a real teammate who
genuinely misunderstood what the bot does).

## Calendar invite

- **Summary:** `Lunch roulette: {name_a} & {name_b}` (or `{a}, {b} & {c}`).
- **Description:**

> You've been matched for lunch through the team's lunch roulette 🍽️ Use this
> hour to step away and get to know each other — no agenda. If the time doesn't
> work, just reply here and reschedule between yourselves.

Set attendees to the members' emails so Google sends each of them the invite.
