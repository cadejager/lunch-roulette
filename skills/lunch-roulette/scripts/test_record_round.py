#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Chris DeJager
"""Tests for record_round.py — the append-only round writer. Run: python test_record_round.py

Covers: extracting groups from a pair.py result, first-write, merging into the
day's existing round (newest-wins accumulation), de-duping a re-recorded group,
and ignoring a round file from a different day. No third-party deps.
"""

import json
import os
import tempfile

import record_round

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def _write(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f)


def _pair_result(date, groups):
    """A minimal pair.py-shaped result: groups are lists of emails."""
    return {"date": date, "groups": [{"members": [{"email": e} for e in g]} for g in groups], "unmatched": []}


@case
def test_groups_from_pair_result():
    d = tempfile.mkdtemp()
    g = os.path.join(d, "groups.json")
    _write(g, _pair_result("2026-06-04", [["a@x", "b@x"], ["c@x", "d@x", "e@x"]]))
    date, groups = record_round.groups_from_pair_result(g)
    assert date == "2026-06-04", date
    assert groups == [["a@x", "b@x"], ["c@x", "d@x", "e@x"]], groups


@case
def test_first_write():
    d = tempfile.mkdtemp()
    g, out = os.path.join(d, "g.json"), os.path.join(d, "round.json")
    _write(g, _pair_result("2026-06-04", [["a@x", "b@x"]]))
    record_round.main(["--groups", g, "--out", out])
    assert json.load(open(out)) == {"date": "2026-06-04", "groups": [["a@x", "b@x"]]}


@case
def test_merge_into_existing_accumulates():
    d = tempfile.mkdtemp()
    prev = os.path.join(d, "prev.json")
    _write(prev, {"date": "2026-06-04", "groups": [["a@x", "b@x"]]})
    g, out = os.path.join(d, "g.json"), os.path.join(d, "new.json")
    _write(g, _pair_result("2026-06-04", [["c@x", "d@x"]]))
    record_round.main(["--groups", g, "--into", prev, "--out", out])
    assert json.load(open(out))["groups"] == [["a@x", "b@x"], ["c@x", "d@x"]]


@case
def test_dedup_same_group_reordered():
    d = tempfile.mkdtemp()
    prev = os.path.join(d, "prev.json")
    _write(prev, {"date": "2026-06-04", "groups": [["a@x", "b@x"]]})
    g, out = os.path.join(d, "g.json"), os.path.join(d, "new.json")
    _write(g, _pair_result("2026-06-04", [["b@x", "a@x"]]))  # same set, reversed -> not double-recorded
    record_round.main(["--groups", g, "--into", prev, "--out", out])
    assert json.load(open(out))["groups"] == [["a@x", "b@x"]]


@case
def test_into_different_day_is_ignored():
    d = tempfile.mkdtemp()
    prev = os.path.join(d, "prev.json")
    _write(prev, {"date": "2026-06-03", "groups": [["x@x", "y@x"]]})  # yesterday's file
    g, out = os.path.join(d, "g.json"), os.path.join(d, "new.json")
    _write(g, _pair_result("2026-06-04", [["a@x", "b@x"]]))
    record_round.main(["--groups", g, "--into", prev, "--out", out])
    assert json.load(open(out)) == {"date": "2026-06-04", "groups": [["a@x", "b@x"]]}


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
