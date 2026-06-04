#!/usr/bin/env python3
"""Deterministic tests for pair.py. Run: python test_pair.py

These exercise the parts most likely to break: odd counts, novelty rotation,
availability overlap, and the single-person edge case. No third-party deps.
"""

import sys

import pair


def groups_as_sets(result):
    return [frozenset(m["email"] for m in g["members"]) for g in result["groups"]]


def avail(date, people):
    """people: list of (email, free) where free is None or [["HH:MM","HH:MM"]]."""
    return {
        "date": date,
        "responses": [
            {"email": e, "wants_lunch": True, "free": f} for (e, f) in people
        ],
    }


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def test_even_all_flexible():
    res = pair.compute(
        avail("2026-06-03", [("a@x", None), ("b@x", None), ("c@x", None), ("d@x", None)]),
        {"rounds": []}, {}, {},
    )
    gs = groups_as_sets(res)
    assert len(gs) == 2, gs
    assert sum(len(g) for g in gs) == 4
    assert not res["unmatched"], res["unmatched"]
    assert all(len(g) == 2 for g in gs), gs


@case
def test_odd_makes_one_triple():
    res = pair.compute(
        avail("2026-06-03", [(f"{c}@x", None) for c in "abcde"]),
        {"rounds": []}, {}, {},
    )
    gs = groups_as_sets(res)
    assert not res["unmatched"], res["unmatched"]
    assert sorted(len(g) for g in gs) == [2, 3], gs
    # Everyone placed exactly once.
    everyone = set().union(*gs)
    assert everyone == {f"{c}@x" for c in "abcde"}


@case
def test_novelty_rotation():
    # a&b and c&d were paired yesterday; today they should rotate apart.
    hist = {"rounds": [{"date": "2026-06-02", "groups": [["a@x", "b@x"], ["c@x", "d@x"]]}]}
    res = pair.compute(
        avail("2026-06-03", [("a@x", None), ("b@x", None), ("c@x", None), ("d@x", None)]),
        hist, {}, {},
    )
    gs = groups_as_sets(res)
    assert frozenset({"a@x", "b@x"}) not in gs, gs
    assert frozenset({"c@x", "d@x"}) not in gs, gs


@case
def test_availability_overlap_respected():
    # a free only late morning, b free only early afternoon -> cannot share.
    # c, d flexible. Expect a&b never grouped, and slots inside their windows.
    res = pair.compute(
        avail("2026-06-03", [
            ("a@x", [["11:30", "12:30"]]),
            ("b@x", [["13:00", "14:00"]]),
            ("c@x", None),
            ("d@x", None),
        ]),
        {"rounds": []}, {}, {},
    )
    gs = groups_as_sets(res)
    assert frozenset({"a@x", "b@x"}) not in gs, gs
    assert not res["unmatched"], res["unmatched"]
    # Check a's slot sits within 11:30-12:30.
    for g in res["groups"]:
        emails = {m["email"] for m in g["members"]}
        if "a@x" in emails:
            assert g["suggested_slot"]["start"] >= "11:30"
            assert g["suggested_slot"]["end"] <= "12:30"


@case
def test_single_person_unmatched():
    res = pair.compute(
        avail("2026-06-03", [("solo@x", None)]),
        {"rounds": []}, {}, {},
    )
    assert res["groups"] == []
    assert len(res["unmatched"]) == 1
    assert res["unmatched"][0]["email"] == "solo@x"


@case
def test_triple_has_common_slot():
    res = pair.compute(
        avail("2026-06-03", [
            ("a@x", [["12:00", "13:30"]]),
            ("b@x", [["12:00", "13:30"]]),
            ("c@x", [["12:00", "13:30"]]),
        ]),
        {"rounds": []}, {}, {},
    )
    assert len(res["groups"]) == 1
    g = res["groups"][0]
    assert len(g["members"]) == 3
    assert g["suggested_slot"] is not None
    # Slot is a 60-min block inside the shared window.
    assert g["suggested_slot"]["start"] >= "12:00"
    assert g["suggested_slot"]["end"] <= "13:30"


@case
def test_declined_excluded():
    a = avail("2026-06-03", [("a@x", None), ("b@x", None)])
    a["responses"].append({"email": "c@x", "wants_lunch": False, "free": None})
    res = pair.compute(a, {"rounds": []}, {}, {})
    everyone = set().union(*groups_as_sets(res)) if res["groups"] else set()
    assert "c@x" not in everyone
    assert "c@x" not in {u["email"] for u in res["unmatched"]}


@case
def test_deterministic_same_day():
    args = (
        avail("2026-06-03", [(f"{c}@x", None) for c in "abcdef"]),
        {"rounds": []}, {}, {},
    )
    r1 = groups_as_sets(pair.compute(*args))
    r2 = groups_as_sets(pair.compute(*args))
    assert r1 == r2, (r1, r2)


@case
def test_local_window_respected():
    # Local mode: the orchestrator has already converted each person's local
    # lunch band into the reference zone and clipped their free time to it, so a
    # band *outside* the default 11:30-14:00 window must survive untouched —
    # this is how a whole team that lunches at, say, 15:00 their own time still
    # gets matched. The matcher must not re-clip to the global window here.
    res = pair.compute(
        avail("2026-06-03", [
            ("a@x", [["15:00", "16:00"]]),
            ("b@x", [["15:00", "16:00"]]),
        ]),
        {"rounds": []}, {"lunch_window_is_local": True}, {},
    )
    gs = groups_as_sets(res)
    assert gs == [frozenset({"a@x", "b@x"})], gs
    assert not res["unmatched"], res["unmatched"]
    assert res["groups"][0]["suggested_slot"] == {"start": "15:00", "end": "16:00"}


@case
def test_default_mode_clips_to_global_window():
    # Same out-of-window band, but WITHOUT the local flag: the default
    # reference-zone behavior clips to the one global lunch window. Everything
    # they stated falls outside it, so they fall back to flexible and meet
    # inside 11:30-14:00 — proving the flag is what changes the semantics.
    res = pair.compute(
        avail("2026-06-03", [
            ("a@x", [["15:00", "16:00"]]),
            ("b@x", [["15:00", "16:00"]]),
        ]),
        {"rounds": []}, {}, {},
    )
    gs = groups_as_sets(res)
    assert gs == [frozenset({"a@x", "b@x"})], gs
    slot = res["groups"][0]["suggested_slot"]
    assert slot["start"] == "11:30" and slot["end"] == "12:30", slot


def main():
    failed = 0
    for fn in CASES:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
