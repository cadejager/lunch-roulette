#!/usr/bin/env python3
"""Append today's pairings to the history file so future days can rotate away
from them. Run this only AFTER invites have actually gone out — history is the
record of who-met-whom, and the matcher trusts it.

Re-running for the same date replaces that date's entry rather than adding a
duplicate, so it's safe to run again if a later step failed and you retried.

Usage:
    python record_round.py --history history.json --groups groups.json
    python record_round.py --history history.json --date 2026-06-03 \
        --group alice@org.com bob@org.com --group carol@org.com dave@org.com
"""

import argparse
import json
import os


def load_history(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"rounds": []}


def groups_from_result(path):
    with open(path) as f:
        result = json.load(f)
    date = result.get("date")
    groups = [[m["email"] for m in g["members"]] for g in result.get("groups", [])]
    return date, groups


def main(argv=None):
    ap = argparse.ArgumentParser(description="Record a lunch round into history.")
    ap.add_argument("--history", required=True)
    ap.add_argument("--groups", help="a groups.json produced by pair.py")
    ap.add_argument("--date", help="override / supply the date (YYYY-MM-DD)")
    ap.add_argument(
        "--group", action="append", nargs="+", metavar="EMAIL",
        help="one group's emails; repeat --group per group",
    )
    args = ap.parse_args(argv)

    if args.groups:
        date, groups = groups_from_result(args.groups)
        if args.date:
            date = args.date
    else:
        date, groups = args.date, args.group or []
    if not date:
        ap.error("need a date (via --date or inside --groups file)")

    history = load_history(args.history)
    history["rounds"] = [r for r in history.get("rounds", []) if r.get("date") != date]
    history["rounds"].append({"date": date, "groups": groups})
    history["rounds"].sort(key=lambda r: r["date"])

    os.makedirs(os.path.dirname(os.path.abspath(args.history)), exist_ok=True)
    with open(args.history, "w") as f:
        json.dump(history, f, indent=2)
        f.write("\n")
    print(f"Recorded {len(groups)} group(s) for {date} into {args.history}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
