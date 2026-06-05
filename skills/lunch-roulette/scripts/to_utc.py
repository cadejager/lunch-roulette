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
  * anything entirely outside the band drops out.

`zoneinfo` handles DST automatically from the date. UTC windows are assumed to fall
within a single UTC day, which holds for the Americas (a daytime local lunch maps to
afternoon/evening UTC); a team spanning the date line would need date-aware windows,
which is out of scope here.

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
    h, m = (int(x) for x in hhmm.strip().split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=tz)


def to_free_utc(free_local, tz_name: str, date_str: str, lunch_window_local: dict):
    """Local windows -> list of UTC ["HH:MM","HH:MM"], clipped to the lunch band."""
    tz = ZoneInfo(tz_name)
    d = date_cls.fromisoformat(date_str)
    band_lo = _local_dt(d, lunch_window_local["earliest"], tz).astimezone(UTC)
    band_hi = _local_dt(d, lunch_window_local["latest"], tz).astimezone(UTC)

    if not free_local:  # None or [] -> flexible across the whole band
        windows = [(band_lo, band_hi)]
    else:
        windows = []
        for w in free_local:
            start = _local_dt(d, w[0], tz).astimezone(UTC)
            end = band_hi if (len(w) < 2 or w[1] is None) else _local_dt(d, w[1], tz).astimezone(UTC)
            windows.append((start, end))

    out = []
    for start, end in windows:
        lo = max(start, band_lo)
        hi = min(end, band_hi)
        if hi > lo:
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
