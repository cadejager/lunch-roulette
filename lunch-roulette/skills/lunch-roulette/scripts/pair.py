#!/usr/bin/env python3
"""Pair lunch participants into groups of two (one group of three when the count
is odd), avoiding recent repeats, working entirely in **UTC**.

Every time here is a UTC ``"HH:MM"`` clock time on the availability date. By the
time the matcher runs, the orchestrator has already, for each person:

  * converted their stated local windows into UTC,
  * clipped them to that person's *own* local lunch window, and
  * materialized a "flexible / any time" person as an explicit UTC band,

so this script needs nothing but interval overlap — **no timezone logic and no
lunch-window logic live here anymore.** Two people match when their free UTC
intervals overlap by at least the lunch duration; whoever can't overlap anyone is
returned as unmatched (never forced into a group).

It is a pure, deterministic function of its inputs: the same date + availability +
history always yields the same groups, but the per-day seed reshuffles ties so
pairings rotate across days. That is what makes it testable and keeps pairings
fresh.

Usage:
    python pair.py --availability avail.json --history history.json \
        --config config.json --participants participants.json --out groups.json

Only --availability is required. --history is the *aggregated* past rounds
(``{"rounds": [{"date", "groups"}]}``) the orchestrator builds from the per-run
round files in Drive. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date as date_cls

# --- Defaults -------------------------------------------------------------
# Overridden by config.json when present. No lunch_window here on purpose — the
# orchestrator has already clipped every interval to each person's local window.
DEFAULTS = {
    "default_lunch_duration_min": 30,
    "max_group_size": 3,
    "novelty_window_days": 14,
    # Randomized restarts of the greedy matcher. The penalty landscape is simple,
    # so a few hundred is plenty even for ~60 people.
    "restarts": 500,
}


# --- Time helpers (all UTC) ----------------------------------------------
def to_minutes(hhmm: str) -> int:
    """'13:30' -> 810. Minutes since 00:00 UTC."""
    h, m = hhmm.strip().split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: int) -> str:
    """810 -> '13:30'."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def intersect_intervals(a: list[list[int]], b: list[list[int]]) -> list[list[int]]:
    """Intersection of two sets of [start, end] minute intervals."""
    out: list[list[int]] = []
    for s1, e1 in a:
        for s2, e2 in b:
            lo, hi = max(s1, s2), min(e1, e2)
            if hi > lo:
                out.append([lo, hi])
    return out


def common_free(members: list[dict]) -> list[list[int]]:
    """Intersect the free-interval sets of every member in a group."""
    acc = members[0]["intervals"]
    for m in members[1:]:
        acc = intersect_intervals(acc, m["intervals"])
        if not acc:
            return []
    return acc


def earliest_slot(intervals: list[list[int]], duration: int) -> list[int] | None:
    """Earliest [start, end] sub-interval of length `duration` that fits inside
    one of the given intervals, or None if nothing fits."""
    for s, e in sorted(intervals):
        if e - s >= duration:
            return [s, s + duration]
    return None


# --- Loading & normalization ---------------------------------------------
def parse_free_utc(free_utc: list | None) -> list[list[int]]:
    """Turn a person's UTC free windows (``[["HH:MM","HH:MM"], ...]``) into minute
    intervals. The orchestrator supplies closed UTC intervals already clipped to
    the person's lunch window, so there is nothing to clip or fill here; anything
    malformed (open-ended or zero-length) is simply dropped."""
    out: list[list[int]] = []
    for item in free_utc or []:
        if not item or item[0] is None or item[1] is None:
            continue
        s, e = to_minutes(item[0]), to_minutes(item[1])
        if e > s:
            out.append([s, e])
    return out


def load_participants(path: str | None) -> dict[str, dict]:
    """email -> {name, slack_id, slack_username, ...} for enriching output."""
    if not path:
        return {}
    with open(path) as f:
        data = json.load(f)
    return {p["email"]: p for p in data.get("participants", []) if p.get("email")}


def recency_penalties(
    history: dict, today: str, window_days: int
) -> dict[frozenset, float]:
    """Penalty for re-pairing two people, summed over past rounds inside the
    novelty window. More recent shared lunches weigh more, so the matcher avoids
    immediate repeats hardest and old ones only mildly."""
    pen: dict[frozenset, float] = {}
    today_d = date_cls.fromisoformat(today)
    for rnd in history.get("rounds", []):
        try:
            d = date_cls.fromisoformat(rnd["date"])
        except (KeyError, ValueError):
            continue
        days_ago = (today_d - d).days
        if days_ago <= 0 or days_ago > window_days:
            continue
        weight = window_days - days_ago + 1  # yesterday -> heaviest
        for group in rnd.get("groups", []):
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    key = frozenset((group[i], group[j]))
                    pen[key] = pen.get(key, 0.0) + weight
    return pen


# --- Matching -------------------------------------------------------------
def pair_penalty(pen: dict[frozenset, float], a: str, b: str) -> float:
    return pen.get(frozenset((a, b)), 0.0)


def compatible(p: dict, q: dict, duration: int) -> bool:
    """Two people can share lunch if their free windows overlap by at least the
    lunch duration."""
    return earliest_slot(intersect_intervals(p["intervals"], q["intervals"]), duration) is not None


def greedy_round(people: list[dict], pen, duration, rng) -> tuple[list[tuple], list[dict]]:
    """One randomized greedy matching pass. Returns (pairs, leftovers)."""
    order = people[:]
    rng.shuffle(order)
    by_email = {p["email"]: p for p in order}
    used: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for p in order:
        if p["email"] in used:
            continue
        candidates = [
            q for q in order
            if q["email"] not in used
            and q["email"] != p["email"]
            and compatible(p, q, duration)
        ]
        if not candidates:
            continue
        # Lowest repeat penalty wins; the prior shuffle breaks ties, which is what
        # rotates pairings on days when penalties are all equal.
        q = min(candidates, key=lambda q: pair_penalty(pen, p["email"], q["email"]))
        pairs.append((p["email"], q["email"]))
        used.add(p["email"])
        used.add(q["email"])
    leftovers = [by_email[e] for e in by_email if e not in used]
    return pairs, leftovers


def attach_leftovers(pairs, leftovers, people_by_email, pen, duration, max_group_size):
    """Fold each leftover person into the cheapest compatible existing pair to form
    a triple. Returns (groups, unmatched) where groups are lists of emails.
    Normally there is at most one leftover (odd count); availability gaps can
    produce more, which surface as unmatched."""
    groups = [list(pr) for pr in pairs]
    unmatched: list[dict] = []
    for lp in leftovers:
        best_idx, best_cost = None, None
        for idx, g in enumerate(groups):
            if len(g) >= max_group_size:
                continue
            members = [people_by_email[e] for e in g] + [lp]
            if not earliest_slot(common_free(members), duration):
                continue
            cost = sum(pair_penalty(pen, lp["email"], e) for e in g)
            if best_cost is None or cost < best_cost:
                best_idx, best_cost = idx, cost
        if best_idx is None:
            unmatched.append({
                "email": lp["email"],
                "reason": "no compatible group with overlapping free time",
            })
        else:
            groups[best_idx].append(lp["email"])
    return groups, unmatched


def total_penalty(groups, pen) -> float:
    score = 0.0
    for g in groups:
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                score += pair_penalty(pen, g[i], g[j])
    return score


def match(people: list[dict], pen, duration, max_group_size, seed, restarts):
    """Run many randomized greedy passes and keep the best solution.

    "Best" prefers, in order: more people matched, fewer triples, lower repeat
    penalty. Matching everyone matters most — nobody should be left out for the
    sake of a marginally fresher pairing."""
    people_by_email = {p["email"]: p for p in people}
    best = None  # (key, groups, unmatched)
    rng = random.Random(seed)
    for _ in range(restarts):
        pairs, leftovers = greedy_round(people, pen, duration, rng)
        groups, unmatched = attach_leftovers(
            pairs, leftovers, people_by_email, pen, duration, max_group_size
        )
        key = (
            len(unmatched),
            sum(1 for g in groups if len(g) >= 3),
            total_penalty(groups, pen),
        )
        if best is None or key < best[0]:
            best = (key, groups, unmatched)
    _, groups, unmatched = best
    return groups, unmatched


# --- Orchestration --------------------------------------------------------
def compute(availability: dict, history: dict, config: dict, participants: dict):
    cfg = {**DEFAULTS, **(config or {})}
    duration = int(cfg["default_lunch_duration_min"])
    today = availability.get("date") or date_cls.today().isoformat()

    # Only people who can actually be matched: opted in today, have a calendar
    # identity (email), and have at least one usable UTC window.
    people: list[dict] = []
    for r in availability.get("responses", []):
        if not r.get("email"):
            continue
        intervals = parse_free_utc(r.get("free_utc"))
        if not intervals:
            continue
        people.append({"email": r["email"], "intervals": intervals})

    result = {"date": today, "groups": [], "unmatched": []}

    if len(people) < 2:
        for p in people:
            result["unmatched"].append({
                "email": p["email"],
                "reason": "only one person available today — no match possible",
            })
        return result

    pen = recency_penalties(history or {}, today, int(cfg["novelty_window_days"]))
    seed = int(date_cls.fromisoformat(today).strftime("%Y%m%d"))
    groups, unmatched = match(
        people, pen, duration, int(cfg["max_group_size"]), seed, int(cfg["restarts"])
    )

    people_by_email = {p["email"]: p for p in people}

    def enrich(email: str) -> dict:
        info = participants.get(email, {})
        return {
            "email": email,
            "name": info.get("name", email),
            "slack_id": info.get("slack_id"),
            "slack_username": info.get("slack_username"),
        }

    for g in groups:
        members = [people_by_email[e] for e in g]
        slot = earliest_slot(common_free(members), duration)
        result["groups"].append({
            "members": [enrich(e) for e in g],
            "slot_utc": (
                {"start": to_hhmm(slot[0]), "end": to_hhmm(slot[1])} if slot else None
            ),
            "repeat_penalty": round(total_penalty([g], pen), 1),
        })

    for u in unmatched:
        result["unmatched"].append({**enrich(u["email"]), "reason": u["reason"]})

    return result


def _load(path: str | None, default):
    """Load JSON, or fall back to `default` if the path is missing, empty, or
    unparseable. An autonomous run should degrade (e.g. no rotation history) rather
    than crash on a missing or half-written file."""
    if not path:
        return default
    try:
        with open(path) as f:
            text = f.read().strip()
        return json.loads(text) if text else default
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pair lunch participants (UTC).")
    ap.add_argument("--availability", required=True, help="today's availability JSON (UTC)")
    ap.add_argument("--history", help="aggregated past rounds: {'rounds': [...]}")
    ap.add_argument("--config", help="config JSON")
    ap.add_argument("--participants", help="roster JSON (for names/slack ids)")
    ap.add_argument("--out", help="write result here (default: stdout)")
    args = ap.parse_args(argv)

    availability = _load(args.availability, {})
    history = _load(args.history, {"rounds": []})
    config = _load(args.config, {})
    participants = load_participants(args.participants)

    result = compute(availability, history, config, participants)
    text = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"Wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
