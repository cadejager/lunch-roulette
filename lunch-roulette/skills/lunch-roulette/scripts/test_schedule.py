#!/usr/bin/env python3
"""Tests for schedule.py — the just-in-time run logic. Run: python test_schedule.py

Includes the three scheduling scenarios we care about:
  * an early-bird who can't be matched on the first run but is matched on a later
    run once a compatible person shows up (and is NOT told "no match" in between),
  * an odd headcount (one triple),
  * someone genuinely unmatchable (told "no match" only at the last run).

Run schedule throughout: hourly 08:00–12:00 America/New_York on 2026-06-04, i.e.
runs at 12:00, 13:00, 14:00, 15:00, 16:00 UTC. No third-party deps.
"""

import schedule
import pair

CASES = []
RS = {"tz": "America/New_York", "from": "08:00", "to": "12:00", "every_min": 60}
DATE = "2026-06-04"


def case(fn):
    CASES.append(fn)
    return fn


def resp(slack_id, free_utc, email=None):
    return {"slack_id": slack_id, "email": email or f"{slack_id.lower()}@x", "free_utc": free_utc}


def pair_pool(responses):
    """Run the matcher on a pool of availability responses."""
    res = pair.compute({"date": DATE, "responses": responses}, {"rounds": []}, {}, {})
    return res


def groups_as_sets(res):
    return [frozenset(m["email"] for m in g["members"]) for g in res["groups"]]


# --- timing primitives ----------------------------------------------------
@case
def test_next_run_and_last_run():
    assert schedule.next_run_utc("2026-06-04T12:00:00Z", RS, DATE).strftime("%H:%M") == "13:00"
    assert schedule.is_last_run("2026-06-04T12:00:00Z", RS, DATE) is False
    assert schedule.is_last_run("2026-06-04T15:30:00Z", RS, DATE) is False
    assert schedule.is_last_run("2026-06-04T16:00:00Z", RS, DATE) is True   # at the last run
    assert schedule.is_last_run("2026-06-04T18:00:00Z", RS, DATE) is True   # past all runs


@case
def test_due_now_due_vs_wait():
    early = resp("A", [["12:30", "13:00"]])   # opens before the 13:00 next run -> due
    late = resp("B", [["15:30", "16:00"]])    # opens much later -> can wait
    due = schedule.due_now("2026-06-04T12:00:00Z", RS, DATE, [early, late])
    assert due == ["A"], due


@case
def test_due_now_skips_paired_and_no_email():
    a = resp("A", [["12:30", "13:00"]])
    b = resp("B", [["12:30", "13:00"]], email=None); b["email"] = None  # no calendar identity
    due = schedule.due_now("2026-06-04T12:00:00Z", RS, DATE, [a, b], paired=["A"])
    assert due == [], due  # A already paired, B has no email


@case
def test_last_run_sweeps_ready_but_not_passed():
    ready = resp("A", [["15:30", "16:30"]])   # still open at 16:00 -> swept
    passed = resp("B", [["12:00", "13:00"]])  # long over by 16:00 -> not due
    due = schedule.due_now("2026-06-04T16:00:00Z", RS, DATE, [ready, passed])
    assert due == ["A"], due


@case
def test_should_notify_only_when_hopeless():
    # Not the last run, a window survives to the next run -> don't give up.
    assert schedule.should_notify_unmatched("2026-06-04T12:00:00Z", RS, DATE, [["15:00", "16:00"]]) is False
    # Not the last run, but all windows pass by the next (13:00) run -> hopeless.
    assert schedule.should_notify_unmatched("2026-06-04T12:00:00Z", RS, DATE, [["12:00", "12:30"]]) is True
    # The last run -> always okay to say no-match.
    assert schedule.should_notify_unmatched("2026-06-04T16:00:00Z", RS, DATE, [["15:00", "16:30"]]) is True


# --- the three scenarios --------------------------------------------------
@case
def test_scenario_early_bird_matched_on_later_run():
    # E is available early AND later; at run 1 nobody else is around. We must NOT
    # tell E "no match" (a later window survives). P shows up later sharing E's
    # afternoon slot, and at the run before that slot E+P are both due and pair up.
    E = resp("E", [["12:30", "13:00"], ["15:30", "16:00"]])
    # Run 1 (12:00 UTC): E is due (early window), alone -> unmatched, but NOT notified.
    assert schedule.due_now("2026-06-04T12:00:00Z", RS, DATE, [E]) == ["E"]
    assert schedule.should_notify_unmatched("2026-06-04T12:00:00Z", RS, DATE, E["free_utc"]) is False
    assert not pair_pool([E])["groups"]  # nobody to match yet
    # Run at 15:00 UTC: P has now opted in for the afternoon slot; both are due.
    P = resp("P", [["15:30", "16:00"]])
    due = schedule.due_now("2026-06-04T15:00:00Z", RS, DATE, [E, P])
    assert set(due) == {"E", "P"}, due
    # Feeding the due pool to the matcher pairs them on the shared afternoon window.
    assert groups_as_sets(pair_pool([E, P])) == [frozenset({"e@x", "p@x"})]


@case
def test_scenario_odd_count_makes_one_triple():
    pool = [resp(c, [["12:30", "13:30"]]) for c in ["A", "B", "C", "D", "E"]]
    due = schedule.due_now("2026-06-04T12:00:00Z", RS, DATE, pool)
    assert set(due) == {"A", "B", "C", "D", "E"}, due
    res = pair_pool(pool)
    assert sorted(len(g["members"]) for g in res["groups"]) == [2, 3], res
    assert not res["unmatched"]


@case
def test_scenario_unmatchable_notified_only_at_last_run():
    # A & B overlap and pair; C's only windows never overlap anyone (and are too
    # short anyway), so C is unmatchable.
    A = resp("A", [["12:30", "13:00"]])
    B = resp("B", [["12:30", "13:00"]])
    C = resp("C", [["15:30", "15:50"], ["12:30", "12:45"]])  # 20m & 15m, no viable overlap
    res = pair_pool([A, B, C])
    assert frozenset({"a@x", "b@x"}) in groups_as_sets(res)
    assert {u["email"] for u in res["unmatched"]} == {"c@x"}, res
    # C is NOT told "no match" early (the 15:30 window survives the 13:00 next run)…
    assert schedule.should_notify_unmatched("2026-06-04T12:00:00Z", RS, DATE, C["free_utc"]) is False
    # …only at the last run.
    assert schedule.should_notify_unmatched("2026-06-04T16:00:00Z", RS, DATE, C["free_utc"]) is True


@case
def test_naive_now_is_read_as_utc():
    # A timezone-naive --now must be interpreted as UTC, never the box's local
    # zone (the deployment machine is on Mountain time). Otherwise scheduling
    # silently shifts hours and can flip is_last_run.
    assert schedule._parse_now("2026-06-04T12:00:00") == schedule._parse_now("2026-06-04T12:00:00Z")
    assert schedule.is_last_run("2026-06-04T12:00:00", RS, DATE) == schedule.is_last_run("2026-06-04T12:00:00Z", RS, DATE)


@case
def test_tolerates_malformed_windows():
    # Null / open-ended elements in free_utc must not crash schedule.py (pair.py
    # tolerates malformed windows too); they're simply skipped.
    resps = [{"slack_id": "A", "email": "a@x", "free_utc": [["12:30", None], ["12:30", "13:00"]]}]
    schedule.due_now("2026-06-04T12:00:00Z", RS, DATE, resps)
    schedule.should_notify_unmatched("2026-06-04T12:00:00Z", RS, DATE, [["12:30", None]])


def main():
    failed = 0
    for fn in CASES:
        try:
            fn()
            print("PASS", fn.__name__)
        except AssertionError as e:
            failed += 1
            print("FAIL", fn.__name__, "::", e)
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
