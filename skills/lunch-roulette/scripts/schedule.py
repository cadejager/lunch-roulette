#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Chris DeJager
"""Just-in-time scheduling decisions for the hourly lunch runs — kept here, in
tested code, rather than left to the orchestrator's in-the-moment arithmetic.

The bot fires several times across the team's morning (`config.run_schedule`).
Pairing is *just in time*: each run we pair only people whose lunch is close enough
that waiting for the next run would risk it, and we tell someone "no match" only
when it's genuinely hopeless. From the schedule + the clock this answers:

  next_run_utc / is_last_run    - when does the bot next fire; is this the last fire?
  due_now(...)                  - which opted-in people must be paired THIS run
  should_notify_unmatched(...)  - after pairing, may we tell this leftover "no match"?

All comparisons are UTC. Availability windows (`free_utc`, from to_utc.py) and the
run times are assumed to share one UTC day (true for the Americas).

CLI (for the orchestrator):
    python schedule.py --now 2026-06-04T12:00:00Z --date 2026-06-04 \
        --run-schedule '{"tz":"America/New_York","from":"08:00","to":"12:00","every_min":60}' \
        --availability avail.json
    # -> {"is_last_run": false, "next_run_utc": "...", "due": ["U1","U2"]}
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, date as date_cls, timedelta
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")


def _min(hhmm: str) -> int:
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def _parse_now(now) -> datetime:
    if isinstance(now, datetime):
        return now if now.tzinfo else now.replace(tzinfo=UTC)
    dt = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
    # A timezone-naive timestamp is assumed to be UTC (never the machine's local
    # zone) — the orchestrator works in UTC and the box may be on any timezone.
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


def _run_datetimes_utc(run_schedule: dict, date_str: str):
    tz = ZoneInfo(run_schedule.get("tz", "UTC"))
    d = date_cls.fromisoformat(date_str)
    start, end = _min(run_schedule["from"]), _min(run_schedule["to"])
    step = int(run_schedule.get("every_min", 60))
    # A non-positive step (0 or negative) would loop forever and march `t` out of
    # the valid 0..1439 range, crashing datetime(); fall back to the hourly default.
    if step <= 0:
        step = 60
    out, t = [], start
    while t <= end:
        out.append(datetime(d.year, d.month, d.day, t // 60, t % 60, tzinfo=tz).astimezone(UTC))
        t += step
    # set() de-dupes the rare case where a DST gap collapses two local run times
    # onto the same UTC instant.
    return sorted(set(out))


def next_run_utc(now, run_schedule, date_str):
    """The next run strictly after `now`, or None if `now` is at/after the last run."""
    now = _parse_now(now)
    for r in _run_datetimes_utc(run_schedule, date_str):
        if r > now:
            return r
    return None


def is_last_run(now, run_schedule, date_str) -> bool:
    return next_run_utc(now, run_schedule, date_str) is None


def is_within_active_window(now, run_schedule, date_str, grace_min=15) -> bool:
    """Is `now` inside the day's active window `[first_run - grace, last_run + grace]`?

    `is_last_run` is True for *any* `now` at/after the last scheduled fire, so an
    extra/over-broad cron fire well after the window (or a stray one before it) would
    be misread as "the last run" and trigger a sweep + "no match" finalization. This
    is the clean signal the orchestrator uses to NO-OP such a stale fire instead.
    The grace absorbs cron's ~10-min jitter so a slightly-late real last fire still
    counts as in-window."""
    now = _parse_now(now)
    runs = _run_datetimes_utc(run_schedule, date_str)
    if not runs:
        return False
    grace = timedelta(minutes=grace_min)
    return runs[0] - grace <= now <= runs[-1] + grace


def _mins_of_day(dt, date_str) -> int:
    d = date_cls.fromisoformat(date_str)
    base = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return int((dt.astimezone(UTC) - base).total_seconds() // 60)


def _well_formed(w):
    """A closed [start, end] window — defensively skip null/short ones (pair.py
    tolerates malformed windows too; the matcher only ever gets closed UTC windows)."""
    return bool(w) and len(w) >= 2 and w[0] is not None and w[1] is not None


def _usable_windows(free_utc, now_min):
    """Windows not yet fully passed (end strictly after now)."""
    return [w for w in (free_utc or []) if _well_formed(w) and _min(w[1]) > now_min]


def due_now(now, run_schedule, date_str, responses, paired=None, lead_min=0):
    """slack_ids that must be paired THIS run: opted in, matchable (email present),
    not already in `paired`, with a still-open window — and either it's the last run,
    or one of those windows opens at/before the next run (plus an optional lead)."""
    now = _parse_now(now)
    paired = set(paired or [])
    last = is_last_run(now, run_schedule, date_str)
    nr = next_run_utc(now, run_schedule, date_str)
    next_min = _mins_of_day(nr, date_str) if nr else None
    now_min = _mins_of_day(now, date_str)
    due = []
    for r in responses:
        if not r.get("email") or r.get("slack_id") in paired:
            continue
        usable = _usable_windows(r.get("free_utc"), now_min)
        if not usable:
            continue
        if last or any(_min(w[0]) <= next_min + lead_min for w in usable):
            due.append(r["slack_id"])
    return due


def should_notify_unmatched(now, run_schedule, date_str, free_utc) -> bool:
    """After the matcher leaves someone out, may we tell them "no match"? Only when
    it's hopeless: the last run of the day, or all of their windows will have passed
    by the next run (nothing left to try). Otherwise stay quiet — a later run may
    still match them."""
    now = _parse_now(now)
    if is_last_run(now, run_schedule, date_str):
        return True
    # With no well-formed windows we have no evidence their windows have *passed*
    # (free_utc may simply be empty/garbled this run), so `all([])` must NOT be read
    # as "hopeless" on a non-last run — stay quiet and let a later run try (the last
    # run above still finalizes unconditionally).
    windows = [w for w in (free_utc or []) if _well_formed(w)]
    if not windows:
        return False
    next_min = _mins_of_day(next_run_utc(now, run_schedule, date_str), date_str)
    return all(_min(w[1]) <= next_min for w in windows)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Just-in-time run scheduling decisions.")
    ap.add_argument("--now", required=True, help="current time, ISO-8601 UTC (…Z)")
    ap.add_argument("--date", required=True, help="working date YYYY-MM-DD")
    ap.add_argument("--run-schedule", required=True, help="JSON config.run_schedule")
    ap.add_argument("--availability", help="availability JSON (responses + paired); adds the `due` list")
    ap.add_argument("--unmatched-free", help="one person's free_utc JSON; adds should_notify_unmatched for them")
    args = ap.parse_args(argv)

    rs = json.loads(args.run_schedule)
    nr = next_run_utc(args.now, rs, args.date)
    out = {
        "is_last_run": is_last_run(args.now, rs, args.date),
        "within_active_window": is_within_active_window(args.now, rs, args.date),
        "next_run_utc": nr.strftime("%Y-%m-%dT%H:%M:%SZ") if nr else None,
    }
    if args.availability:
        with open(args.availability) as f:
            av = json.load(f)
        out["due"] = due_now(args.now, rs, args.date, av.get("responses", []), av.get("paired", []))
    if args.unmatched_free is not None:
        out["should_notify_unmatched"] = should_notify_unmatched(
            args.now, rs, args.date, json.loads(args.unmatched_free)
        )
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
