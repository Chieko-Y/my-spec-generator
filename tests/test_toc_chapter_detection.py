"""Regression tests for domain.manual_parsing.detect_toc_chapters -- entirely
rule-based (no AI) parsing of a PDF's own printed table of contents (see
docs/HANDOVER.md 2026-08-27: found on the real 2025 Subaru supplement, read
with columns=2, chapter name + start-page-number sit as two Lines at nearly
the same `top` in different x0 columns, while that chapter's own dot-leader
subsection list sits several points lower -- a genuinely different row).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Line, detect_toc_chapters


def _heading_line(page: int) -> Line:
    return Line(page=page, text="TABLE OF CONTENTS", top=79.0, x0=70.9, size=12.0)


def _summary_row(page: int, top: float, num: int, name: str) -> Line:
    # The compact "1 Quick Guide" style row: number+name glued into ONE Line,
    # no separate page-number Line -- must never become a chapter on its own.
    return Line(page=page, text=f"{num} {name}", top=top, x0=323.4, size=11.0)


def _chapter_row(page: int, top: float, name: str, printed_page: int) -> list[Line]:
    return [
        Line(page=page, text=name, top=top, x0=-269.3, size=11.0),
        Line(page=page, text=str(printed_page), top=top + 0.4, x0=603.8, size=10.0),
    ]


def _subsection_row(page: int, top: float, text: str) -> Line:
    return Line(page=page, text=text, top=top, x0=105.4, size=8.0)


def _realistic_toc_lines() -> list[Line]:
    lines = [_heading_line(0)]
    # Summary page (page 0 itself, after the heading) -- must be ignored.
    lines.append(_summary_row(0, 90.0, 1, "Quick Guide"))
    lines.append(_summary_row(0, 100.0, 2, "Settings"))

    # Detail page (page 1): 3 chapters, each with a subsection line further below.
    lines += _chapter_row(1, 79.5, "Quick Guide", 13)
    lines.append(_subsection_row(1, 86.0, "· System Types... 14 · Dual 7.0-inch Display System... 15"))

    lines += _chapter_row(1, 147.5, "Settings", 79)
    lines.append(
        _subsection_row(
            1, 154.2, "· Phone Settings... 83 · Setting Driver Profiles... 92 · Sound Settings... 100"
        )
    )

    lines += _chapter_row(1, 181.5, "Phone", 107)
    lines.append(_subsection_row(1, 188.2, "· Talking On The Bluetooth Phone... 116"))

    # Body headings near each chapter's computed page_start -- the offset-
    # plausibility grounding check needs these to trust the parsed page numbers
    # (see test_returns_none_when_no_computed_page_range_has_a_matching_heading
    # for the case where they're deliberately absent).
    lines.append(Line(page=12, text="Quick Guide", top=50.0, size=14.0))
    lines.append(Line(page=78, text="Settings", top=50.0, size=14.0))
    lines.append(Line(page=106, text="Phone", top=50.0, size=14.0))

    return lines


def test_detects_chapters_from_a_realistic_toc_page_layout():
    lines = _realistic_toc_lines()

    result = detect_toc_chapters(lines, page_count=120)

    assert result is not None
    labels = [c.label for c in result]
    assert labels == ["Quick Guide", "Settings", "Phone"]
    by_label = {c.label: c for c in result}
    assert (by_label["Quick Guide"].page_start, by_label["Quick Guide"].page_end) == (12, 78)
    assert (by_label["Settings"].page_start, by_label["Settings"].page_end) == (78, 106)
    # Last chapter's page_end reaches the document's last page (page_count).
    assert (by_label["Phone"].page_start, by_label["Phone"].page_end) == (106, 120)


def test_row_clustering_does_not_merge_a_chapter_row_with_its_own_subsection_line():
    lines = _realistic_toc_lines()

    result = detect_toc_chapters(lines, page_count=120)

    assert result is not None
    settings = next(c for c in result if c.label == "Settings")
    assert "Settings" not in settings.subsection_evidence  # the chapter's own name, not evidence
    assert "Phone Settings" in settings.subsection_evidence


def test_multi_segment_dot_leader_line_extracts_all_bullet_entries():
    lines = _realistic_toc_lines()

    result = detect_toc_chapters(lines, page_count=120)

    settings = next(c for c in result if c.label == "Settings")
    assert settings.subsection_evidence == [
        "Phone Settings",
        "Setting Driver Profiles",
        "Sound Settings",
    ]


def test_toc_summary_page_rows_without_a_page_number_are_ignored():
    lines = _realistic_toc_lines()

    result = detect_toc_chapters(lines, page_count=120)

    labels = [c.label for c in result]
    assert "1 Quick Guide" not in labels
    assert "2 Settings" not in labels


def test_returns_none_when_no_toc_heading_found():
    lines = _realistic_toc_lines()[1:]  # drop the "TABLE OF CONTENTS" heading line

    assert detect_toc_chapters(lines, page_count=120) is None


def test_returns_none_when_fewer_than_minimum_chapter_rows_found():
    lines = [_heading_line(0)] + _chapter_row(1, 79.5, "Quick Guide", 13) + _chapter_row(1, 147.5, "Settings", 79)

    assert detect_toc_chapters(lines, page_count=120) is None


def test_returns_none_when_printed_page_numbers_are_not_monotonically_increasing():
    lines = (
        [_heading_line(0)]
        + _chapter_row(1, 79.5, "Quick Guide", 13)
        + _chapter_row(1, 147.5, "Settings", 79)
        + _chapter_row(1, 181.5, "Phone", 50)  # goes backward
    )

    assert detect_toc_chapters(lines, page_count=120) is None


def test_returns_none_when_no_computed_page_range_has_a_matching_heading():
    # Printed numbers increase monotonically (would pass that check alone), but
    # nothing in the document actually looks like these chapters near their
    # computed pages -- guards against unnumbered front matter silently
    # offsetting every page number by a constant amount.
    lines = [_heading_line(0)] + _chapter_row(1, 79.5, "Quick Guide", 13) + _chapter_row(1, 147.5, "Settings", 79)
    lines += _chapter_row(1, 181.5, "Phone", 107)

    result = detect_toc_chapters(lines, page_count=120)

    assert result is None
