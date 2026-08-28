"""Regression tests for domain.manual_parsing.detect_item_index_entries and
build_blocks_from_item_index -- a chapter's own local index of its items (one
level deeper than the manual's main table of contents, see detect_toc_chapters)
added 2026-08-28 after finding one on the real 2025 Subaru supplement's
Navigation chapter, printed page 195.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import (
    Line,
    RunningHeadChapter,
    build_blocks_from_item_index,
    detect_item_index_entries,
)


def test_parses_name_leader_page_entries_and_ignores_group_headers():
    lines = [
        Line(page=0, text="Basic Operation", top=5.0),  # group label, no page number -> ignored
        Line(page=0, text="Map Screen........196", top=10.0),
        Line(page=0, text="Current Position Display........197", top=20.0),
        Line(page=0, text="Route Calculation........210", top=30.0),
        Line(page=0, text="Standard Map Icon........217", top=40.0),
        Line(page=0, text="Typical Voice Guidance Prompts........218", top=50.0),
    ]

    entries = detect_item_index_entries(lines, chapter_page_start=0, chapter_page_end=5)

    assert entries == [
        ("Map Screen", 196),
        ("Current Position Display", 197),
        ("Route Calculation", 210),
        ("Standard Map Icon", 217),
        ("Typical Voice Guidance Prompts", 218),
    ]


def test_a_short_ellipsis_is_not_mistaken_for_a_dot_leader():
    # Real prose can end "...see P.14." -- only 3 dots, nowhere near a real
    # dot-leader run (confirmed real leaders are tens of characters long).
    lines = [Line(page=0, text="Refer to the appendix...14", top=10.0)]
    assert detect_item_index_entries(lines, 0, 5) is None


def test_fewer_than_the_minimum_entries_returns_none():
    lines = [Line(page=0, text="Map Screen........196", top=10.0)]
    assert detect_item_index_entries(lines, 0, 5) is None


def test_dedup_key_is_name_and_page_not_name_alone():
    """Confirmed against the real 2025 Subaru supplement: "Using Wi-Fi" lists
    once under "Updating The Map Data Manually" (page 225) and again under
    "Updating The Map Data Automatically" (page 226) -- both are real, distinct
    sections and deduping by name alone silently dropped the second one."""
    lines = [
        Line(page=0, text="Using Wi-Fi........225", top=10.0),
        Line(page=0, text="Using Wi-Fi........226", top=20.0),
        Line(page=0, text="Using Wi-Fi........225", top=30.0),  # exact duplicate, dropped
        Line(page=0, text="Item Four........201", top=40.0),
        Line(page=0, text="Item Five........202", top=50.0),
        Line(page=0, text="Item Six........203", top=60.0),
    ]

    entries = detect_item_index_entries(lines, 0, 5)

    assert entries.count(("Using Wi-Fi", 225)) == 1
    assert ("Using Wi-Fi", 226) in entries
    assert len(entries) == 5


def test_scan_window_is_limited_to_the_chapters_first_few_pages():
    lines = []
    for p in range(6):
        lines.append(Line(page=p, text=f"Item A{p}........{300 + p}", top=10.0))
        lines.append(Line(page=p, text=f"Item B{p}........{400 + p}", top=20.0))

    entries = detect_item_index_entries(lines, chapter_page_start=0, chapter_page_end=6)

    # _ITEM_INDEX_SEARCH_WINDOW_PAGES == 3 -- only pages 0-2 are scanned
    assert {page for _, page in entries} == {300, 301, 302, 400, 401, 402}


def _chapter_lines(headings_and_bodies: list[tuple[str, float, float]]) -> list[Line]:
    """headings_and_bodies: list of (heading_text, top, size) for headings, plus
    a fixed set of body-sized filler lines so the median body size stays low."""
    lines = [Line(page=0, text=text, top=top, x0=60.0, size=size) for text, top, size in headings_and_bodies]
    for i in range(6):
        lines.append(Line(page=0, text=f"Body filler {i}.", top=1000.0 + i, x0=60.0, size=9.0))
    return lines


def test_exact_match_cuts_a_section_per_entry():
    chapter = RunningHeadChapter(label="ch", page_start=0, page_end=1)
    lines = _chapter_lines(
        [
            ("Map Screen Overview", 50.0, 14.0),
            ("Route Calculation Screen", 80.0, 14.0),
        ]
    )
    lines += [
        Line(page=0, text="Body under overview.", top=60.0, x0=60.0, size=9.0),
        Line(page=0, text="Body under route calc.", top=90.0, x0=60.0, size=9.0),
    ]
    entries = [("Map Screen Overview", 1), ("Route Calculation Screen", 1)]

    result = build_blocks_from_item_index(lines, chapter, entries)

    assert result is not None
    assert [s.title for s in result.sections] == ["Map Screen Overview", "Route Calculation Screen"]
    assert result.unmatched_headings == []


def test_fuzzy_match_when_the_real_heading_runs_longer_than_the_entry():
    """A real heading may run longer than the index's own name for it (a
    trailing word merged on) -- accepted when the containment is strong
    (_MIN_CONTAINMENT_RATIO) and the candidate line is heading-sized."""
    chapter = RunningHeadChapter(label="ch", page_start=0, page_end=1)
    lines = _chapter_lines(
        [
            ("Register Phone Now", 50.0, 14.0),  # real heading: entry name + 1 word
            ("Second Topic", 80.0, 14.0),
        ]
    )
    lines += [
        Line(page=0, text="Body under phone.", top=60.0, x0=60.0, size=9.0),
        Line(page=0, text="Body under second.", top=90.0, x0=60.0, size=9.0),
    ]
    entries = [("Register Phone", 1), ("Second Topic", 1)]

    result = build_blocks_from_item_index(lines, chapter, entries)

    assert result is not None
    # The section is titled with the index's own entry name (consistent,
    # human-curated wording), not the matched line's raw text.
    assert result.unmatched_headings == []
    assert [s.title for s in result.sections] == ["Register Phone", "Second Topic"]
    assert [l.text for l in result.sections[0].lines] == ["Body under phone."]


def test_fuzzy_match_when_the_real_heading_is_shorter_than_the_entry():
    """Confirmed against the real 2025 Subaru supplement: the index entry
    "Using A USB Memory Device" is only text-findable via its real heading's
    own shorter wording, "USB Memory Device"."""
    chapter = RunningHeadChapter(label="ch", page_start=0, page_end=1)
    lines = _chapter_lines(
        [
            ("Bluetooth System", 50.0, 14.0),  # real heading: only the tail of the entry name
            ("Second Topic", 80.0, 14.0),
        ]
    )
    lines += [
        Line(page=0, text="Body under bluetooth.", top=60.0, x0=60.0, size=9.0),
        Line(page=0, text="Body under second.", top=90.0, x0=60.0, size=9.0),
    ]
    entries = [("Configure The Bluetooth System", 1), ("Second Topic", 1)]

    result = build_blocks_from_item_index(lines, chapter, entries)

    assert result is not None
    assert result.unmatched_headings == []
    assert [s.title for s in result.sections] == ["Configure The Bluetooth System", "Second Topic"]
    assert [l.text for l in result.sections[0].lines] == ["Body under bluetooth."]


def test_weak_coincidental_containment_is_rejected():
    """Confirmed against the real 2025 Subaru supplement: the unrelated entry
    "Map Data" (its own real topic is elsewhere) coincidentally sits inside the
    real heading "Updating The Map Data Manually" (the entry is only a 26%
    fraction of it) -- accepting it stole that heading position from the entry
    it actually belongs to. _MIN_CONTAINMENT_RATIO (0.5) rejects this weak a
    containment; the entry falls back to a coarse page boundary instead."""
    chapter = RunningHeadChapter(label="ch", page_start=0, page_end=1)
    lines = _chapter_lines(
        [
            ("Updating The Map Data Manually", 50.0, 14.0),
            ("Second Topic", 80.0, 14.0),
        ]
    )
    lines += [
        Line(page=0, text="Body under updating.", top=60.0, x0=60.0, size=9.0),
        Line(page=0, text="Body under second.", top=90.0, x0=60.0, size=9.0),
    ]
    entries = [("Map Data", 1), ("Second Topic", 1)]

    result = build_blocks_from_item_index(lines, chapter, entries)

    assert result is not None
    assert result.unmatched_headings == ["Map Data"]
    assert "Updating The Map Data Manually" not in [s.title for s in result.sections]


def test_a_body_sized_caption_fragment_is_never_matched_even_with_strong_containment():
    """Confirmed against the real 2025 Subaru supplement: a short index entry
    can have strong text containment (by length ratio) against an inline
    caption fragment that is NOT the real heading -- min_heading_size (the same
    font-size-ratio signal build_blocks_from_font_headings uses) is what keeps
    a real heading distinguishable from those, independent of the text-length
    ratio alone."""
    chapter = RunningHeadChapter(label="ch", page_start=0, page_end=1)
    lines = _chapter_lines(
        [
            ("Second Topic", 80.0, 14.0),
        ]
    )
    lines += [
        # normalized "contact" is a 58%-length containment of "contact list" --
        # strong enough to pass _MIN_CONTAINMENT_RATIO on its own -- but this
        # line is body-sized (9pt, same as the filler), not heading-sized.
        Line(page=0, text="(Contact)", top=50.0, x0=60.0, size=9.0),
        Line(page=0, text="Body under second.", top=90.0, x0=60.0, size=9.0),
    ]
    entries = [("Contact List", 1), ("Second Topic", 1)]

    result = build_blocks_from_item_index(lines, chapter, entries)

    assert result is not None
    assert result.unmatched_headings == ["Contact List"]


def test_returns_none_when_fewer_than_half_the_entries_match():
    chapter = RunningHeadChapter(label="ch", page_start=0, page_end=1)
    lines = _chapter_lines([("Second Topic", 80.0, 14.0)])
    lines.append(Line(page=0, text="Body under second.", top=90.0, x0=60.0, size=9.0))
    entries = [("Nonexistent One", 1), ("Nonexistent Two", 1), ("Second Topic", 1)]

    result = build_blocks_from_item_index(lines, chapter, entries)

    assert result is None
