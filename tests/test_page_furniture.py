"""Regression tests for domain.manual_parsing.filter_page_furniture -- the
header/footer vertical-band filter, and the two carve-outs added 2026-08-28
after real content was found sitting inside that band on the real 2025 Subaru
supplement (a numbered procedure step, and that step's own wrapped
continuation text).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Line, filter_page_furniture


def test_lines_outside_the_band_are_kept():
    lines = [Line(page=0, text="Body text.", top=200.0)]
    assert filter_page_furniture(lines, header_boundary_pt=75.0, footer_boundary_pt=700.0) == lines


def test_lines_inside_the_header_or_footer_band_are_dropped():
    lines = [
        Line(page=0, text="Running head label", top=20.0),
        Line(page=0, text="12", top=720.0),
    ]
    assert filter_page_furniture(lines, header_boundary_pt=75.0, footer_boundary_pt=700.0) == []


def test_numbered_step_line_is_kept_even_inside_the_header_band():
    """Confirmed against the real 2025 Subaru supplement: step "5. ->" of a
    right-column map-update procedure prints at top=67.8pt, just inside the
    manual's header_boundary_pt=75.0 cutoff, because that column's screenshot
    starts unusually high on that one page. A numbered step is never real
    header/footer furniture (production filenames, running titles, bare page
    numbers never look like "<number>. <text>"), so it survives regardless of
    where it happens to sit."""
    lines = [
        Line(page=0, text="GX3_US.indb 225", top=20.0, x0=46.8),
        Line(page=0, text="5. Select the update option.", top=67.8, x0=348.7),
    ]

    result = filter_page_furniture(lines, header_boundary_pt=75.0, footer_boundary_pt=700.0)

    assert [l.text for l in result] == ["5. Select the update option."]


def test_a_bare_number_alone_is_not_rescued_as_a_step():
    # "(number)." with nothing after it is not the numbered-step shape --
    # real header/footer furniture (page numbers) must still be excluded.
    lines = [Line(page=0, text="12", top=20.0)]
    assert filter_page_furniture(lines, header_boundary_pt=75.0, footer_boundary_pt=700.0) == []


def test_a_steps_own_continuation_is_rescued_alongside_it():
    """Confirmed against the real 2025 Subaru supplement: step "5." continues
    with "(Update XX MB)" / "Update XX MB" at top=70.0/71.3 -- both still
    inside the same header band -- which are the manual's own continuation of
    that step, not separate furniture. A furniture-band line within
    _STEP_CONTINUATION_GAP_PT of an already-kept line keeps propagating
    outward from the step anchor instead of stopping after one line."""
    lines = [
        Line(page=0, text="5. Select the update option.", top=67.8, x0=348.7),
        Line(page=0, text="(Update XX MB)", top=70.0, x0=443.7),
        Line(page=0, text="Update XX MB", top=71.3, x0=378.4),
    ]

    result = filter_page_furniture(lines, header_boundary_pt=75.0, footer_boundary_pt=700.0)

    assert [l.text for l in result] == [
        "5. Select the update option.",
        "(Update XX MB)",
        "Update XX MB",
    ]


def test_continuation_rescue_does_not_reach_across_a_big_gap():
    lines = [
        Line(page=0, text="5. Select the update option.", top=10.0, x0=348.7),
        Line(page=0, text="Unrelated running head, further down", top=50.0, x0=488.1),
    ]

    result = filter_page_furniture(lines, header_boundary_pt=75.0, footer_boundary_pt=700.0)

    assert [l.text for l in result] == ["5. Select the update option."]


def test_continuation_rescue_resets_at_a_page_boundary():
    lines = [
        Line(page=0, text="5. Select the update option.", top=67.8, x0=348.7),
        Line(page=1, text="Running head on the next page", top=70.0, x0=443.7),
    ]

    result = filter_page_furniture(lines, header_boundary_pt=75.0, footer_boundary_pt=700.0)

    assert [l.text for l in result] == ["5. Select the update option."]
