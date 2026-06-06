#!/usr/bin/env python3
"""Tests for to_utc.py — the local→UTC availability conversion. Run: python test_to_utc.py

Covers the DST-sensitive arithmetic an LLM would get wrong: per-zone conversion,
summer vs. winter offsets, flexible→band, open-ended clip, multi-window, and
out-of-band drop. Also the input-robustness contract: open-start clip, empty
elements skipped, unparseable times dropped per-window, an inverted band raising,
and cross-UTC-midnight windows dropped (not corrupted). No third-party deps
(zoneinfo is stdlib; needs the system tz db).
"""

import to_utc

CASES = []
WINDOW = {"earliest": "10:00", "latest": "14:00"}  # local lunch band used throughout


def case(fn):
    CASES.append(fn)
    return fn


def conv(free, tz, date, window=WINDOW):
    return to_utc.to_free_utc(free, tz, date, window)


@case
def test_eastern_summer():
    # EDT = UTC-4 on 2026-06-04: 11:00-13:00 ET -> 15:00-17:00 UTC
    assert conv([["11:00", "13:00"]], "America/New_York", "2026-06-04") == [["15:00", "17:00"]]


@case
def test_central_summer_multi_window():
    # CDT = UTC-5: docstring example
    got = conv([["10:45", "11:15"], ["13:00", "13:30"]], "America/Chicago", "2026-06-04")
    assert got == [["15:45", "16:15"], ["18:00", "18:30"]], got


@case
def test_pacific_summer():
    # PDT = UTC-7: 11:00-12:00 PT -> 18:00-19:00 UTC
    assert conv([["11:00", "12:00"]], "America/Los_Angeles", "2026-06-04") == [["18:00", "19:00"]]


@case
def test_dst_winter_vs_summer_differ():
    # Same wall-clock window, different UTC because of DST — the whole point of doing
    # this in zoneinfo, not by hand.
    summer = conv([["11:00", "13:00"]], "America/New_York", "2026-06-04")  # EDT UTC-4
    winter = conv([["11:00", "13:00"]], "America/New_York", "2026-01-15")  # EST UTC-5
    assert summer == [["15:00", "17:00"]], summer
    assert winter == [["16:00", "18:00"]], winter
    assert summer != winter


@case
def test_flexible_is_whole_band():
    # None / flexible -> the person's whole local band, in UTC (EDT 10:00-14:00 = 14:00-18:00 UTC)
    assert conv(None, "America/New_York", "2026-06-04") == [["14:00", "18:00"]]
    assert conv([], "America/New_York", "2026-06-04") == [["14:00", "18:00"]]


@case
def test_open_ended_clips_to_band_end():
    # "after 12:30" -> [["12:30", null]] -> 16:30 UTC to band end 18:00 UTC
    assert conv([["12:30", None]], "America/New_York", "2026-06-04") == [["16:30", "18:00"]]


@case
def test_outside_band_drops():
    # 15:00-16:00 ET is past the 14:00 band end -> nothing survives
    assert conv([["15:00", "16:00"]], "America/New_York", "2026-06-04") == []


@case
def test_partial_overlap_clipped_to_band():
    # 09:00-11:00 ET: 09:00 is before the 10:00 band start -> clipped to 10:00 (14:00 UTC)
    assert conv([["09:00", "11:00"]], "America/New_York", "2026-06-04") == [["14:00", "15:00"]]


@case
def test_single_element_window_is_open_ended():
    # ["12:30"] (no end given) is treated as open-ended — clipped to the band end,
    # same as ["12:30", null].
    assert conv([["12:30"]], "America/New_York", "2026-06-04") == [["16:30", "18:00"]]


@case
def test_open_start_clips_to_band_start():
    # "before 13:00" -> [[null, "13:00"]] starts at the band start (10:00 ET =
    # 14:00 UTC), mirroring the open-ended (null end) case. Must not crash.
    assert conv([[None, "13:00"]], "America/New_York", "2026-06-04") == [["14:00", "17:00"]]


@case
def test_empty_element_is_skipped():
    # An empty/None element INSIDE the list is dropped (vs. top-level []/None which
    # means "flexible, whole band"). The good window survives.
    assert conv([[]], "America/New_York", "2026-06-04") == []
    assert conv([None], "America/New_York", "2026-06-04") == []
    assert conv([[], ["11:00", "13:00"], None], "America/New_York", "2026-06-04") == [["15:00", "17:00"]]


@case
def test_scalar_element_is_dropped():
    # A window ELEMENT that is a bare scalar (e.g. 123) rather than a [start, end]
    # pair must be dropped like other malformed windows, not crash on w[0]. A good
    # neighbour window survives (degrade-don't-crash contract).
    assert conv([123], "America/New_York", "2026-06-04") == []
    assert conv([1.5], "America/New_York", "2026-06-04") == []
    assert conv([123, ["11:00", "13:00"]], "America/New_York", "2026-06-04") == [["15:00", "17:00"]]


@case
def test_unparseable_time_skips_only_that_window():
    # Times an LLM might emit from messy text — no colon, words, out-of-range — drop
    # just their own window, leaving the rest of the person's availability intact.
    assert conv([["9", "13:00"], ["11:00", "12:00"]], "America/New_York", "2026-06-04") == [["15:00", "16:00"]]
    assert conv([["noon", "13:00"]], "America/New_York", "2026-06-04") == []
    assert conv([["1pm", "13:00"]], "America/New_York", "2026-06-04") == []
    assert conv([["10:00", "24:00"]], "America/New_York", "2026-06-04") == []
    # A bad endpoint on one window doesn't poison a good neighbour.
    assert conv([["11:00", "25:99"], ["12:00", "13:00"]], "America/New_York", "2026-06-04") == [["16:00", "17:00"]]


@case
def test_inverted_band_raises():
    # earliest >= latest is a misconfig that would silently zero out EVERYONE's
    # availability — fail loud instead so the orchestrator can surface it.
    raised = False
    try:
        conv([["11:00", "13:00"]], "America/New_York", "2026-06-04",
             {"earliest": "14:00", "latest": "10:00"})
    except ValueError:
        raised = True
    assert raised, "expected ValueError on earliest > latest"
    # Equal bounds (zero-width band) also raise.
    raised = False
    try:
        conv([["11:00", "13:00"]], "America/New_York", "2026-06-04",
             {"earliest": "12:00", "latest": "12:00"})
    except ValueError:
        raised = True
    assert raised, "expected ValueError on earliest == latest"


@case
def test_cross_utc_midnight_window_dropped():
    # A non-Americas zone can push a converted window across UTC midnight, where
    # strftime drops the date and end < start reads as garbage. Detect and drop it
    # rather than emit a corrupted interval.
    assert conv([["11:00", "13:00"]], "Pacific/Auckland", "2026-06-04") == []
    # A flexible person whose whole band wraps UTC midnight likewise drops to empty.
    assert conv(None, "Pacific/Auckland", "2026-06-04") == []
    # A non-wrapping non-Americas zone is unaffected (London BST +1 stays same UTC day).
    assert conv([["11:00", "13:00"]], "Europe/London", "2026-06-04") == [["10:00", "12:00"]]


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
