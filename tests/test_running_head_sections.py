"""Regression tests for the section_source="running_head" path (domain.manual_parsing:
detect_running_head_chapters, find_running_head_chapter, build_blocks_from_font_headings)
-- needed when a PDF has no usable per-chapter bookmarks, only a short label repeating
across a run of consecutive pages (see docs/HANDOVER.md 2026-08-26 2025 Subaru
supplement finding: "Audio" recurs on 18 consecutive pages as a side-tab label)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import (
    Line,
    RunningHeadChapter,
    build_blocks_from_font_headings,
    detect_running_head_chapters,
    find_running_head_chapter,
    sample_heading_evidence,
)


def _label_line(page: int) -> Line:
    return Line(page=page, text="Audio", top=5.0, x0=500.0, size=8.0)


def test_detects_chapter_boundaries_from_a_repeated_short_label():
    lines = []
    for page in range(5):
        lines.append(Line(page=page, text="Audio", top=5.0, x0=500.0, size=8.0))
        lines.append(Line(page=page, text=f"Body text on page {page}.", top=100.0, x0=60.0, size=10.0))
    for page in range(5, 8):
        lines.append(Line(page=page, text="Phone", top=5.0, x0=500.0, size=8.0))
        lines.append(Line(page=page, text=f"Body text on page {page}.", top=100.0, x0=60.0, size=10.0))

    chapters = detect_running_head_chapters(lines, min_repeat_pages=3)
    by_label = {c.label: (c.page_start, c.page_end) for c in chapters}
    assert by_label["audio"] == (0, 5)
    assert by_label["phone"] == (5, 8)


def test_a_run_shorter_than_the_minimum_is_not_a_chapter():
    lines = [Line(page=p, text="Settings", top=5.0, x0=500.0, size=8.0) for p in range(2)]
    assert detect_running_head_chapters(lines, min_repeat_pages=3) == []


def test_prose_sentences_are_never_mistaken_for_labels():
    # A sentence repeating by coincidence should never happen in practice, but the
    # terminal-punctuation guard is what would stop it if it did.
    lines = [
        Line(page=p, text="Touch the screen to continue.", top=100.0, x0=60.0, size=10.0)
        for p in range(5)
    ]
    assert detect_running_head_chapters(lines, min_repeat_pages=3) == []


def test_find_running_head_chapter_matches_case_and_punctuation_insensitively():
    chapters = [RunningHeadChapter(label="audio", page_start=0, page_end=5)]
    assert find_running_head_chapter(chapters, "Audio") is not None
    assert find_running_head_chapter(chapters, "Phone") is None


def test_build_blocks_from_font_headings_cuts_sections_on_larger_font_size():
    chapter = RunningHeadChapter(label="audio", page_start=0, page_end=1)
    lines = [
        Line(page=0, text="Selecting a source", top=50.0, x0=60.0, size=14.0),
        Line(page=0, text="Touch the source icon to select it.", top=60.0, x0=60.0, size=10.0),
        Line(page=0, text="Adjusting the volume", top=80.0, x0=60.0, size=14.0),
        Line(page=0, text="Turn the volume knob.", top=90.0, x0=60.0, size=10.0),
    ]

    result = build_blocks_from_font_headings(lines, chapter)

    assert [s.title for s in result.sections] == ["Selecting a source", "Adjusting the volume"]
    assert [l.text for l in result.sections[0].lines] == ["Touch the source icon to select it."]
    assert [l.text for l in result.sections[1].lines] == ["Turn the volume knob."]


def test_build_blocks_from_font_headings_drops_a_heading_that_repeats_the_chapter_title():
    """Real Honda CR-V 2026 case (docs/HANDOVER.md 2026-09-04): a chapter's own
    opening page reprints its title ("Features") as a large-font divider line,
    immediately above the chapter's intro sentence and its own printed item
    index. Without this exclusion that divider line became its own spurious
    function -- literally named the same as its parent chapter -- whose body was
    the intro blurb plus the raw item-index text (a user-reported garbled-looking
    real result, not a hypothetical)."""
    chapter = RunningHeadChapter(label="Features", page_start=0, page_end=1)
    lines = [
        Line(page=0, text="Features", top=10.0, x0=60.0, size=18.0),  # chapter-title divider repeat
        Line(page=0, text="This chapter describes how to operate technology features.", top=20.0, x0=60.0, size=10.0),
        Line(page=0, text="Audio System....................252", top=30.0, x0=60.0, size=10.0),
        Line(page=0, text="About Your Audio System", top=50.0, x0=60.0, size=14.0),
        Line(page=0, text="Touch the source icon to select it.", top=60.0, x0=60.0, size=10.0),
    ]

    result = build_blocks_from_font_headings(lines, chapter)

    assert [s.title for s in result.sections] == ["About Your Audio System"]


def test_sample_heading_evidence_finds_font_sized_headings_within_page_range():
    lines = [
        Line(page=0, text="audio", top=5.0, x0=500.0, size=8.0),  # the running-head label itself
        Line(page=0, text="Selecting a source", top=50.0, x0=60.0, size=14.0),
        Line(page=0, text="Touch the source icon to select it.", top=60.0, x0=60.0, size=10.0),
        Line(page=1, text="Adjusting the volume", top=50.0, x0=60.0, size=14.0),
        Line(page=1, text="Turn the volume knob.", top=60.0, x0=60.0, size=10.0),
    ]

    evidence = sample_heading_evidence(lines, page_start=0, page_end=2, exclude_label="audio")

    assert evidence == ["Selecting a source", "Adjusting the volume"]


def test_sample_heading_evidence_excludes_the_candidates_own_label():
    lines = [
        Line(page=0, text="basic operation", top=5.0, size=8.0),
        Line(page=0, text="Basic Operation", top=50.0, size=14.0),  # same text, different casing
        Line(page=0, text="Map screen", top=60.0, size=14.0),
        Line(page=0, text="Touch the map icon.", top=70.0, size=10.0),
    ]

    evidence = sample_heading_evidence(lines, page_start=0, page_end=1, exclude_label="basic operation")

    assert evidence == ["Map screen"]


def test_sample_heading_evidence_deduplicates_and_respects_max_lines_cap():
    # Body lines dominate in count so the font-size median lands squarely on the
    # body size (10.0), not the heading size (14.0) -- otherwise "notably larger
    # than body" has nothing to be larger than.
    lines = [Line(page=0, text="audio", top=5.0, size=8.0)]
    lines += [Line(page=0, text=f"Body text {i}.", top=30.0 + i, size=10.0) for i in range(20)]
    for i in range(3):
        lines.append(Line(page=0, text="Repeated heading", top=50.0 + i, size=14.0))
    for i in range(3):
        lines.append(Line(page=0, text=f"Unique heading {i}", top=200.0 + i, size=14.0))

    evidence = sample_heading_evidence(lines, page_start=0, page_end=1, exclude_label="audio", max_lines=3)

    assert len(evidence) == 3
    assert evidence[0] == "Repeated heading"  # only counted once despite recurring
    assert len(set(evidence)) == len(evidence)


def test_build_blocks_from_font_headings_ignores_repeating_margin_glyphs():
    """Confirmed against the real 2025 Subaru supplement's Navigation chapter:
    a decorative chapter-number graphic ("Navigation"/"System"/"7") prints at
    pixel-identical (top, x0) on every even page, in a much larger font than
    any real heading -- each glyph line used to become its own spurious section
    (e.g. a section titled just "7"), and on pages where the pieces stayed
    adjacent in reading order they merged into one bogus heading, "Navigation
    System 7", swallowing whatever real heading should have started there."""
    chapter = RunningHeadChapter(label="nav", page_start=0, page_end=3)
    lines = [Line(page=p, text="Deco", top=20.0, x0=500.0, size=40.0) for p in range(3)]
    lines += [
        Line(page=0, text="Selecting a source", top=50.0, x0=60.0, size=14.0),
        Line(page=0, text="Touch the source icon to select it.", top=60.0, x0=60.0, size=10.0),
    ]

    result = build_blocks_from_font_headings(lines, chapter)

    assert [s.title for s in result.sections] == ["Selecting a source"]


def test_build_blocks_from_font_headings_ignores_numbered_step_markers():
    """Confirmed against the real 2025 Subaru supplement: a numbered-step
    marker inside a procedure prints a couple points larger than its own body
    text (e.g. 12pt vs ~8-9pt), clearing the font-size heading threshold even
    though "1." is never a real section title -- _HAS_LETTER_RE already used
    for the same judgment call elsewhere (detect_running_head_chapters) applies
    here too."""
    chapter = RunningHeadChapter(label="nav", page_start=0, page_end=1)
    lines = [Line(page=0, text=f"Body line {i}.", top=100.0 + i, x0=60.0, size=9.0) for i in range(10)]
    lines += [
        Line(page=0, text="Selecting a source", top=50.0, x0=60.0, size=14.0),
        Line(page=0, text="1.", top=60.0, x0=60.0, size=12.0),
        Line(page=0, text="Touch the source icon to select it.", top=65.0, x0=60.0, size=9.0),
    ]

    result = build_blocks_from_font_headings(lines, chapter)

    assert [s.title for s in result.sections] == ["Selecting a source"]


def test_sample_heading_evidence_returns_empty_when_no_font_size_data():
    lines = [
        Line(page=0, text="audio", top=5.0),
        Line(page=0, text="Selecting a source", top=50.0),
    ]

    assert sample_heading_evidence(lines, page_start=0, page_end=1, exclude_label="audio") == []
