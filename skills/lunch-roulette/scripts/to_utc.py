#!/usr/bin/env python3
"""Convert a person's stated **local** lunch availability into **UTC** windows for
the matcher.

The lunch-messenger reports times in the person's own timezone (it never converts);
the matcher works entirely in UTC. This is the single place that bridges the two —
in tested code, not by LLM mental math, because timezone/DST arithmetic is exactly
what an LLM gets subtly wrong.

Given a person's free windows in their local clock, their timezone, the date, and
the team's local lunch band, return a list of UTC `["HH:MM","HH:MM"]` windows
already **clipped to that person's lunch band**:

  * a flexible person (`free_local` null/empty) becomes their whole lunch band,
  * an open-ended window (`["12:30", null]`) is clipped to the band's end,
  * an open-start window (`[null, "13:00"]`) starts at the band's start,
  * anything entirely outside the band drops out.

Inputs come (via an LLM messenger) from messy human Slack messages, so a single
malformed window degrades rather than crashing the run: an empty element, an
unparseable time (`"9"`, `"noon"`, `"24:00"`), or a window that would wrap past a
UTC day boundary is dropped with a one-line note to stderr (stdout stays clean
JSON). The exception is a misconfigured band (`earliest >= latest`), which raises
`ValueError` rather than silently zeroing out everyone's availability.

`zoneinfo` handles DST automatically from the date. UTC windows are assumed to fall
within a single UTC day, which holds for the Americas (a daytime local lunch maps to
afternoon/evening UTC); a team spanning the date line would need date-aware windows,
which is out of scope here — such windows are detected and dropped, not corrupted.

Usage (CLI, for the orchestrator):
    python to_utc.py --tz America/Chicago --date 2026-06-04 \
        --lunch-window '{"earliest":"10:00","latest":"14:00"}' \
        --free '[["10:45","11:15"],["13:00","13:30"]]'
    # -> [["15:45","16:15"],["18:00","18:30"]]   (CDT = UTC-5)

`--free` omitted or 'null' means flexible. Prints the UTC windows as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, date as date_cls
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")


def _local_dt(d: date_cls, hhmm: str, tz: ZoneInfo) -> datetime:
    """Parse a local ``"HH:MM"`` on date `d` into an aware datetime.

    Raises ``ValueError`` on anything not a well-formed in-range 24h clock time
    (no colon, non-numeric, out-of-range hour/minute) so callers can drop just
    the offending window rather than crash the whole run."""
    if not isinstance(hhmm, str):
        raise ValueError(f"time must be a string, got {hhmm!r}")
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"unparseable time {hhmm!r} (expected HH:MM)")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"unparseable time {hhmm!r} (non-numeric)")
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"time out of range {hhmm!r}")
    return datetime(d.year, d.month, d.day, h, m, tzinfo=tz)


def to_free_utc(free_local, tz_name: str, date_str: str, lunch_window_local: dict):
    """Local windows -> list of UTC ["HH:MM","HH:MM"], clipped to the lunch band.

    Inputs are derived from messy human Slack messages, so this degrades rather
    than crashing: an individually malformed window (empty, unparseable time, or
    one that would wrap past a UTC day boundary) is dropped with a one-line note
    to stderr, leaving the rest. The one thing that *does* raise is a misconfigured
    band (earliest >= latest), because silently returning ``[]`` for everyone is a
    zero-lunch outage with no signal — the orchestrator should surface it loudly.
    """
    tz = ZoneInfo(tz_name)
    d = date_cls.fromisoformat(date_str)
    band_lo = _local_dt(d, lunch_window_local["earliest"], tz).astimezone(UTC)
    band_hi = _local_dt(d, lunch_window_local["latest"], tz).astimezone(UTC)

    # A misconfigured band wipes out everyone's availability silently — fail loud.
    if band_hi <= band_lo:
        raise ValueError(
            f"lunch_window earliest {lunch_window_local['earliest']} "
            f"must be before latest {lunch_window_local['latest']}"
        )

    windows = []
    if not free_local:  # None or [] (top level) -> flexible across the whole band
        windows.append((band_lo, band_hi))
    else:
        for w in free_local:
            if not w:  # empty/None element inside the list -> nothing stated, skip
                continue
            try:
                # null/missing start -> band start; null/missing end -> band end.
                start = band_lo if w[0] is None else _local_dt(d, w[0], tz).astimezone(UTC)
                end = band_hi if (len(w) < 2 or w[1] is None) else _local_dt(d, w[1], tz).astimezone(UTC)
            except ValueError as e:
                print(f"to_utc: dropping window {w!r}: {e}", file=sys.stderr)
                continue
            windows.append((start, end))

    out = []
    for start, end in windows:
        lo = max(start, band_lo)
        hi = min(end, band_hi)
        if hi <= lo:
            continue
        # The matcher assumes a single UTC day (Americas: daytime local -> same-day
        # UTC). A non-Americas zone can push a window across UTC midnight, where
        # strftime("%H:%M") drops the date and downstream reads end < start as
        # garbage. Detect the wrap (start/end on different UTC dates) and drop it,
        # rather than emit a corrupted interval. Out of scope: multi-day windows.
        if lo.date() != hi.date():
            print(
                f"to_utc: dropping window {[start.strftime('%H:%M'), end.strftime('%H:%M')]} "
                f"in {tz_name}: crosses a UTC day boundary",
                file=sys.stderr,
            )
            continue
        out.append([lo.strftime("%H:%M"), hi.strftime("%H:%M")])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert local availability windows to UTC.")
    ap.add_argument("--tz", required=True, help="IANA timezone, e.g. America/Chicago")
    ap.add_argument("--date", required=True, help="local date YYYY-MM-DD")
    ap.add_argument("--lunch-window", required=True, help='JSON {"earliest","latest"} local')
    ap.add_argument("--free", help='JSON list of ["HH:MM","HH:MM"] local, or null/omitted for flexible')
    args = ap.parse_args(argv)

    free = json.loads(args.free) if args.free not in (None, "", "null") else None
    window = json.loads(args.lunch_window)
    print(json.dumps(to_free_utc(free, args.tz, args.date, window)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
