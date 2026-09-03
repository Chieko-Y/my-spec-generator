"""Regression tests for domain.manual_parsing.build_blocks_from_running_head_breadcrumbs
and domain.spec_building.filter_excluded_sections -- added 2026-09-02 after the real
Honda Pilot Features chapter's item-index-based section splitting silently dropped 3
real functions (their own heading failed to text-match) and mis-promoted 4 Area
headers to their own "functions" (30 functions found vs. the original app's own real
26). A 2-level "Area>Function" breadcrumb printed in every page's own margin gives
exact per-page boundaries directly, no text-matching needed at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Line, RunningHeadChapter, build_blocks_from_running_head_breadcrumbs
from domain.model import FunctionSpec
from domain.spec_building import filter_excluded_sections


def _lines_for_pages(pages: range) -> list[Line]:
    return [Line(page=p, text=f"Body text on page {p}.", top=100.0, x0=60.0) for p in pages]


def test_consecutive_pages_with_the_same_breadcrumb_become_one_section():
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=7)
    lines = _lines_for_pages(range(0, 7))
    breadcrumbs = {
        0: ["Audio System"],  # bare area -- this area's own lead-in, has children below
        1: ["Audio System", "USB Ports"],
        2: ["Audio System", "USB Ports"],
        3: ["Audio System", "Audio Remote Controls"],
        4: ["Audio System", "Audio Remote Controls"],
        5: ["Audio System", "Audio Remote Controls"],
        6: ["Audio System", "Audio System Theft Protection"],
    }

    result = build_blocks_from_running_head_breadcrumbs(lines, chapter, breadcrumbs)

    assert result is not None
    titles = [s.title for s in result.sections]
    assert titles == ["USB Ports", "Audio Remote Controls", "Audio System Theft Protection"]
    assert all(s.area == "Audio System" for s in result.sections)
    # page 0's bare "Audio System" (this area's own lead-in) is not promoted to
    # its own function -- confirmed real, Honda Pilot: the original app's own
    # output has no "About Your Audio System" function. It's folded FORWARD
    # into "USB Ports" (the area's first real function) rather than dropped,
    # so page 0's own content (and any figure on it) still belongs to some
    # section -- see 2026-09-03 update below.
    assert result.sections[0].page_start == 0


def test_a_leaf_area_with_no_2level_children_becomes_its_own_function():
    """Real Honda Pilot case: "CabinTalk®" never gets a second breadcrumb level
    anywhere in the chapter, so it becomes a function in its own right rather
    than being folded away like "Audio System" is in the test above.

    This was written from an untested assumption ("it must be a real
    function, unlike an area lead-in") -- checked against the original app's
    own real output 2026-09-03 and found the assumption was wrong about the
    ORIGINAL: it actually merges a run like this BACKWARD into the preceding
    function instead (confirmed: the original's own "26-hfl-menus.md"
    contains CabinTalk®'s own body text verbatim, no separate CabinTalk®
    function exists in its real published output). This rebuild's behavior
    (own leaf function) is a DELIBERATE, considered divergence, not an
    oversight -- CabinTalk® is a real, independently-named feature, and
    burying its content inside an unrelated function ("HFL Menus") would be
    worse for a reviewer than giving it its own reviewable card, even though
    it moves the function count away from the original's own count. See
    feedback memory "exceed the original" and docs/ARCHITECTURE.md "7.6"."""
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=9)
    lines = _lines_for_pages(range(0, 9))
    breadcrumbs = {
        0: ["Bluetooth® HandsFreeLink®", "Using HFL"],
        1: ["Bluetooth® HandsFreeLink®", "HFL Menus"],
        2: ["Bluetooth® HandsFreeLink®", "HFL Menus"],
        3: ["Bluetooth® HandsFreeLink®", "HFL Menus"],
        4: ["CabinTalk®"],
    }
    # a 3rd distinct area, purely to satisfy the min-coverage bar
    breadcrumbs[5] = ["Audio System", "USB Ports"]
    breadcrumbs[6] = ["Audio System", "USB Ports"]

    result = build_blocks_from_running_head_breadcrumbs(lines, chapter, breadcrumbs)

    assert result is not None
    titles = [s.title for s in result.sections]
    assert "CabinTalk®" in titles
    cabin = next(s for s in result.sections if s.title == "CabinTalk®")
    assert cabin.area == ""


def test_a_dtp_watermark_page_with_no_real_breadcrumb_is_rejected():
    """Real Honda Pilot case: a chapter's own divider page has only a DTP
    timestamp/filename watermark in its header band (no real breadcrumb at all),
    which read_running_head_breadcrumbs still returns as one long garbled
    "segment" -- it must never become its own spurious one-page function."""
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=6)
    lines = _lines_for_pages(range(0, 6))
    breadcrumbs = {
        0: ["26 PILOT-31T9063000.book 263 page 2025-10-08"],
        1: ["Audio System", "USB Ports"],
        2: ["Audio System", "USB Ports"],
        3: ["Audio System", "USB Ports"],
        4: ["Audio System", "Audio Remote Controls"],
        5: ["Audio System", "Audio System Theft Protection"],
    }

    result = build_blocks_from_running_head_breadcrumbs(lines, chapter, breadcrumbs)

    assert result is not None
    titles = [s.title for s in result.sections]
    assert not any("book" in t for t in titles)
    assert titles == ["USB Ports", "Audio Remote Controls", "Audio System Theft Protection"]


def test_too_little_coverage_returns_none():
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=3)
    lines = _lines_for_pages(range(0, 3))
    breadcrumbs = {0: ["Audio System", "USB Ports"]}

    assert build_blocks_from_running_head_breadcrumbs(lines, chapter, breadcrumbs) is None


def test_a_mid_chapter_bare_area_page_is_folded_into_the_next_function_not_the_previous_one():
    """Real Honda Pilot case, found 2026-09-02, root-caused and fixed 2026-09-03:
    a page's own running head reflects whichever breadcrumb was current at the
    TOP of that page. p.370 (page_index) of the real PDF still read "Bluetooth®
    HandsFreeLink®" alone (no Function level yet) in its margin, but its BODY
    already contained "Using HFL"'s own heading, text, and a figure -- the
    "Using HFL" heading appeared partway down the page, after the margin was
    already printed. Dropping this bare run (the old behavior, and confirmed
    the original app's own real output does the same, see docs/HANDOVER.md
    2026-09-03) left page 2 owned by no Section, so _extract_figures's
    (page, start_top) window search silently attributed it to the PRECEDING
    section ("Defaulting All the Settings") instead of "Using HFL" where its
    own content actually was. Deliberately not matching the original here
    (see feedback memory "exceed the original", 2026-09-03) -- this rebuild
    folds the bare page forward into "Using HFL" instead."""
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=5)
    lines = _lines_for_pages(range(0, 5))
    breadcrumbs = {
        0: ["Customized Features", "Defaulting All the Settings"],
        1: ["Customized Features", "Defaulting All the Settings"],
        2: ["Bluetooth® HandsFreeLink®"],  # bare -- "Using HFL" already started on this page's body
        3: ["Bluetooth® HandsFreeLink®", "Using HFL"],
        4: ["Bluetooth® HandsFreeLink®", "HFL Menus"],
    }

    result = build_blocks_from_running_head_breadcrumbs(lines, chapter, breadcrumbs)

    assert result is not None
    titles = [s.title for s in result.sections]
    assert titles == ["Defaulting All the Settings", "Using HFL", "HFL Menus"]
    defaulting = result.sections[0]
    using_hfl = result.sections[1]
    assert defaulting.page_start == 0 and defaulting.page_end == 2
    # page 2 (the bare lead-in) now belongs to "Using HFL", not "Defaulting
    # All the Settings" -- a figure sitting on page 2 will be assigned there.
    assert using_hfl.page_start == 2 and using_hfl.page_end == 4


def test_a_multi_page_bare_area_run_is_dropped_not_folded_into_the_next_function():
    """Real Honda Pilot case, found 2026-09-03 while implementing the 1-page
    fold above: "Customized Features" has a bare (no Function level) run
    spanning 22 CONSECUTIVE real pages before "Defaulting All the Settings"
    even begins -- genuine standalone area-introduction content, not a
    running-head lag (a lag only ever costs at most one page, the one whose
    body outran its own margin). Folding a run this long forward would bloat
    "Defaulting All the Settings" with 22 pages of unrelated content -- a
    real regression, not an improvement. Only a single-page bare run gets
    folded forward; anything longer keeps the old drop-it behavior."""
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=8)
    lines = _lines_for_pages(range(0, 8))
    breadcrumbs = {
        0: ["Audio System", "USB Ports"],
        1: ["Audio System", "USB Ports"],
        2: ["Audio System", "Audio Remote Controls"],
        3: ["Customized Features"],  # bare, but spans 3 pages -- not a 1-page lag
        4: ["Customized Features"],
        5: ["Customized Features"],
        6: ["Customized Features", "Defaulting All the Settings"],
        7: ["Customized Features", "Defaulting All the Settings"],
    }

    result = build_blocks_from_running_head_breadcrumbs(lines, chapter, breadcrumbs)

    assert result is not None
    titles = [s.title for s in result.sections]
    assert titles == ["USB Ports", "Audio Remote Controls", "Defaulting All the Settings"]
    defaulting = next(s for s in result.sections if s.title == "Defaulting All the Settings")
    assert defaulting.page_start == 6  # not 3 -- the 3-page bare run was dropped, not folded in


def test_a_bare_area_page_at_the_end_of_the_chapter_with_nothing_to_fold_into_is_dropped():
    """A bare-area run with no following run for the same area (chapter simply
    ends, or the next run is a different area) has nothing safe to attribute
    it to -- falls back to the previous behavior of being dropped entirely,
    same as when it can't be folded forward."""
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=6)
    lines = _lines_for_pages(range(0, 6))
    breadcrumbs = {
        0: ["Audio System", "USB Ports"],
        1: ["Audio System", "USB Ports"],
        2: ["Audio System", "Audio Remote Controls"],
        3: ["Audio System", "Audio System Theft Protection"],
        4: ["Audio System", "Audio System Theft Protection"],
        5: ["Audio System"],  # bare, chapter ends here -- nothing to fold into
    }

    result = build_blocks_from_running_head_breadcrumbs(lines, chapter, breadcrumbs)

    assert result is not None
    titles = [s.title for s in result.sections]
    assert titles == ["USB Ports", "Audio Remote Controls", "Audio System Theft Protection"]
    assert result.sections[-1].page_end == 5


def _function(title: str, chapter_number: str = "1") -> FunctionSpec:
    return FunctionSpec(
        function_id=title,
        chapter_number=chapter_number,
        title=title,
        area="Area",
        function_path=title,
        pages=[1],
    )


def test_filter_excluded_sections_drops_a_case_insensitive_substring_match():
    """Real Honda Pilot case: the configured phrase is "License Agreement" but
    the manual's own real title is "Honda App License Agreement" -- an exact
    match would miss it."""
    functions = [_function("USB Ports"), _function("Honda App License Agreement")]

    kept, excluded = filter_excluded_sections(functions, ["License Agreement"])

    assert [f.title for f in kept] == ["USB Ports"]
    assert excluded == ["Honda App License Agreement"]


def test_filter_excluded_sections_renumbers_the_survivors():
    """Real Honda Pilot bug, 2026-09-02: chapter_number is assigned by position
    in the UNFILTERED list. Dropping 4 License entries ahead of it left
    "CabinTalk®" still numbered "32" (its original position) instead of its
    real "28" -- confirmed directly in the live Web UI, reported by the user
    ("32. CabinTalk®になってますが30といってませんでした?")."""
    functions = [
        _function("USB Ports", "1"),
        _function("Honda App License Agreement", "2"),
        _function("License Information", "3"),
        _function("CabinTalk®", "4"),
    ]

    kept, _ = filter_excluded_sections(functions, ["License Agreement", "License Information"])

    assert [(f.title, f.chapter_number) for f in kept] == [("USB Ports", "1"), ("CabinTalk®", "2")]


def test_filter_excluded_sections_is_a_noop_with_no_configured_titles():
    functions = [_function("USB Ports")]

    kept, excluded = filter_excluded_sections(functions, [])

    assert kept == functions
    assert excluded == []
