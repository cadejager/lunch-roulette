#!/usr/bin/env python3
"""Deterministic tests for pair.py (UTC matcher). Run: python test_pair.py

Everything is in UTC "HH:MM"; the orchestrator does all timezone work upstream,
so these exercise pure interval overlap, odd counts, novelty rotation, the
duration floor, multi-window people, and the can't-match edge cases. Also the
input-robustness contract: parse_free_utc tolerating malformed windows and
adjacent/contiguous windows merging so a split-but-continuous span still matches.
No deps.
"""

import pair

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def avail(date, people):
    """people: list of (email, free_utc) where free_utc is [["HH:MM","HH:MM"], ...]."""
    return {"date": date, "responses": [{"email": e, "free_utc": f} for e, f in people]}


def groups_as_sets(res):
    return sorted(
        [frozenset(m["email"] for m in g["members"]) for g in res["groups"]],
        key=lambda s: sorted(s),
    )


def unmatched_emails(res):
    return {u["email"] for u in res["unmatched"]}


@case
def test_two_overlapping_pair():
    res = pair.compute(
        avail("2026-06-04", [("a@x", [["16:00", "17:00"]]), ("b@x", [["16:00", "17:00"]])]),
        {"rounds": []}, {}, {},
    )
    assert groups_as_sets(res) == [frozenset({"a@x", "b@x"})], res
    assert not res["unmatched"], res
    assert res["groups"][0]["slot_utc"] == {"start": "16:00", "end": "16:30"}, res["groups"][0]


@case
def test_no_overlap_unmatched():
    res = pair.compute(
        avail("2026-06-04", [("a@x", [["16:00", "17:00"]]), ("b@x", [["18:00", "19:00"]])]),
        {"rounds": []}, {}, {},
    )
    assert not res["groups"], res
    assert unmatched_emails(res) == {"a@x", "b@x"}, res


@case
def test_overlap_shorter_than_duration_unmatched():
    # 20-minute overlap is below the 30-minute default lunch, so no match.
    res = pair.compute(
        avail("2026-06-04", [("a@x", [["16:00", "16:20"]]), ("b@x", [["16:00", "16:20"]])]),
        {"rounds": []}, {}, {},
    )
    assert not res["groups"], res
    assert unmatched_emails(res) == {"a@x", "b@x"}, res


@case
def test_odd_makes_one_triple():
    people = [(f"{c}@x", [["16:00", "18:00"]]) for c in "abcde"]
    res = pair.compute(avail("2026-06-04", people), {"rounds": []}, {}, {})
    sizes = sorted(len(g["members"]) for g in res["groups"])
    assert sizes == [2, 3], res
    assert not res["unmatched"], res


@case
def test_single_person_unmatched():
    res = pair.compute(avail("2026-06-04", [("a@x", [["16:00", "17:00"]])]), {"rounds": []}, {}, {})
    assert not res["groups"] and unmatched_emails(res) == {"a@x"}, res


@case
def test_novelty_rotation():
    # Yesterday's pairs should be avoided when a fresh, equally-feasible option exists.
    people = [(f"{c}@x", [["16:00", "18:00"]]) for c in "abcd"]
    history = {"rounds": [{"date": "2026-06-03", "groups": [["a@x", "b@x"], ["c@x", "d@x"]]}]}
    res = pair.compute(avail("2026-06-04", people), history, {}, {})
    gs = set(groups_as_sets(res))
    assert frozenset({"a@x", "b@x"}) not in gs, res
    assert frozenset({"c@x", "d@x"}) not in gs, res
    assert not res["unmatched"], res


@case
def test_no_email_excluded():
    av = avail("2026-06-04", [("a@x", [["16:00", "17:00"]]), ("b@x", [["16:00", "17:00"]])])
    av["responses"].append({"email": None, "free_utc": [["16:00", "17:00"]]})  # no identity
    av["responses"].append({"free_utc": [["16:00", "17:00"]]})                 # email missing
    res = pair.compute(av, {"rounds": []}, {}, {})
    assert groups_as_sets(res) == [frozenset({"a@x", "b@x"})], res


@case
def test_multi_window_overlap():
    # Match on ANY overlapping window; the earliest fitting slot wins.
    res = pair.compute(
        avail("2026-06-04", [
            ("a@x", [["15:00", "15:30"], ["17:00", "17:45"]]),
            ("b@x", [["17:00", "17:45"]]),
        ]),
        {"rounds": []}, {}, {},
    )
    assert groups_as_sets(res) == [frozenset({"a@x", "b@x"})], res
    assert res["groups"][0]["slot_utc"] == {"start": "17:00", "end": "17:30"}, res


@case
def test_triple_has_common_slot():
    res = pair.compute(
        avail("2026-06-04", [(f"{c}@x", [["16:00", "17:00"]]) for c in "abc"]),
        {"rounds": []}, {}, {},
    )
    assert len(res["groups"]) == 1 and len(res["groups"][0]["members"]) == 3, res
    assert res["groups"][0]["slot_utc"] == {"start": "16:00", "end": "16:30"}, res


@case
def test_deterministic_same_day():
    people = [(f"{c}@x", [["16:00", "18:00"]]) for c in "abcdef"]
    a = pair.compute(avail("2026-06-04", people), {"rounds": []}, {}, {})
    b = pair.compute(avail("2026-06-04", people), {"rounds": []}, {}, {})
    assert a == b, (a, b)


@case
def test_parse_free_utc_tolerates_malformed():
    # parse_free_utc promises to drop anything not a well-formed closed pair instead
    # of crashing: single-element, empty/whitespace endpoint, non-numeric.
    assert pair.parse_free_utc([["16:00"], ["", "16:30"], ["16:00", "17:00"]]) == [[960, 1020]]
    assert pair.parse_free_utc(
        [None, ["16:00"], ["16:00", ""], ["  ", "16:30"], ["ab", "cd"], ["16:00", "17:00"]]
    ) == [[960, 1020]]
    assert pair.parse_free_utc(None) == []
    assert pair.parse_free_utc([]) == []


@case
def test_parse_free_utc_drops_scalar_elements():
    # A window ELEMENT that is a bare scalar (not a list) — e.g. a number or bool an
    # LLM/JSON quirk slipped in — must be dropped, not crash on len()/subscript. The
    # good neighbour window survives (degrade-don't-crash contract).
    assert pair.parse_free_utc([123]) == []
    assert pair.parse_free_utc([1.5]) == []
    assert pair.parse_free_utc([True]) == []
    assert pair.parse_free_utc([123, ["16:00", "17:00"]]) == [[960, 1020]]


@case
def test_parse_hhmm_rejects_out_of_range():
    # _parse_hhmm range-checks like to_utc._local_dt, so an out-of-range value drops
    # to None instead of becoming a junk interval. Valid times still parse.
    assert pair._parse_hhmm("25:99") is None
    assert pair._parse_hhmm("-1:00") is None
    assert pair._parse_hhmm("0:99") is None
    assert pair._parse_hhmm("13:30") == 810
    assert pair._parse_hhmm("00:00") == 0
    assert pair._parse_hhmm("23:59") == 1439


@case
def test_merge_intervals_coalesces_overlap_and_adjacent():
    # Overlapping AND touching pieces merge; a real gap stays split.
    assert pair.merge_intervals([[960, 980], [980, 1000], [1010, 1020]]) == [[960, 1000], [1010, 1020]]
    assert pair.merge_intervals([[960, 1000], [970, 990]]) == [[960, 1000]]  # nested
    assert pair.merge_intervals([]) == []


@case
def test_adjacent_windows_merge_to_match():
    # Two people each free 16:00-16:20 and 16:20-16:40 form a continuous 40-min span;
    # merged it clears the 30-min floor, so they MUST match (previously unmatched).
    res = pair.compute(
        avail("2026-06-04", [
            ("a@x", [["16:00", "16:20"], ["16:20", "16:40"]]),
            ("b@x", [["16:00", "16:20"], ["16:20", "16:40"]]),
        ]),
        {"rounds": []}, {}, {},
    )
    assert groups_as_sets(res) == [frozenset({"a@x", "b@x"})], res
    assert not res["unmatched"], res
    assert res["groups"][0]["slot_utc"] == {"start": "16:00", "end": "16:30"}, res["groups"][0]


@case
def test_malformed_windows_dont_crash_compute():
    # Malformed windows inside a response are dropped, not fatal; a good neighbour
    # window keeps the person matchable.
    res = pair.compute(
        avail("2026-06-04", [
            ("a@x", [["16:00"], ["", "16:30"], ["16:00", "17:00"]]),
            ("b@x", [["16:00", "17:00"]]),
        ]),
        {"rounds": []}, {}, {},
    )
    assert groups_as_sets(res) == [frozenset({"a@x", "b@x"})], res
    assert not res["unmatched"], res


@case
def test_enrich_from_participants():
    pdict = {"a@x": {"email": "a@x", "name": "Alice", "slack_id": "U1", "slack_username": "alice"}}
    res = pair.compute(
        avail("2026-06-04", [("a@x", [["16:00", "17:00"]]), ("b@x", [["16:00", "17:00"]])]),
        {"rounds": []}, {}, pdict,
    )
    members = {m["email"]: m for g in res["groups"] for m in g["members"]}
    assert members["a@x"]["name"] == "Alice" and members["a@x"]["slack_id"] == "U1", members
    # Unknown person falls back to email as name.
    assert members["b@x"]["name"] == "b@x", members


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
