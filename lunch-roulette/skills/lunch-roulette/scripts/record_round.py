#!/usr/bin/env python3
"""Write an **append-only** lunch round file.

Drive can't overwrite or delete, so history is kept as one immutable file per
(date, run): ``rounds/round-<DATE>-<ts>.json``. The newest file for a date is the
complete record of that day. Because pairing happens incrementally across the
day's runs (each run pairs whoever's lunch is imminent), every run merges the
day's groups so far with the groups it just formed and writes a fresh file.
Reading the newest file back always gives the full day; re-running is safe.

Each round file is simply:
    {"date": "2026-06-04", "groups": [["a@x","b@x"], ["c@x","d@x","e@x"]]}

The matcher reads the *aggregate* of these (one newest file per past date, within
the novelty window) as its --history; that aggregation is the orchestrator's job.

Usage:
    python record_round.py --groups groups-this-run.json \
        [--into rounds/round-2026-06-04-T1500.json] \
        --out rounds/round-2026-06-04-T1600.json
"""

import argparse
import json
import os


def groups_from_pair_result(path):
    """Pull (date, [[email, ...], ...]) out of a pair.py result file."""
    with open(path) as f:
        result = json.load(f)
    date = result.get("date")
    groups = [[m["email"] for m in g["members"]] for g in result.get("groups", [])]
    return date, groups


def load_existing(path):
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"date": None, "groups": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Append a lunch round (immutable file).")
    ap.add_argument("--groups", required=True, help="this run's pair.py result")
    ap.add_argument("--into", help="today's current (newest) round file, if any")
    ap.add_argument("--date", help="override / supply the date (YYYY-MM-DD)")
    ap.add_argument("--out", required=True, help="new round file to write")
    args = ap.parse_args(argv)

    date, new_groups = groups_from_pair_result(args.groups)
    if args.date:
        date = args.date
    if not date:
        ap.error("need a date (via --date or inside the --groups file)")

    existing = load_existing(args.into)
    # Guard against accidentally merging a different day's file.
    prior = existing.get("groups", []) if existing.get("date") in (None, date) else []

    # Merge, de-duping by membership set so a retried run can't double-record a group.
    seen, merged = set(), []
    for g in prior + new_groups:
        key = frozenset(g)
        if key in seen:
            continue
        seen.add(key)
        merged.append(g)

    round_obj = {"date": date, "groups": merged}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(round_obj, f, indent=2)
        f.write("\n")
    print(f"Wrote {args.out}: {len(merged)} group(s) for {date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
