"""Regression tests for domain.manual_parsing.order_by_columns / detect_column_count
-- the multi-column reading-order fix needed for 2-column manuals (see
docs/HANDOVER.md 2026-08-26 2025 Subaru supplement finding: naive top-only sorting
interleaves left/right column text)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import (
    Line,
    detect_column_count,
    drop_repeating_margin_glyphs,
    order_by_columns,
    synthetic_top_for_position,
)


def test_single_column_profile_leaves_lines_untouched():
    lines = [Line(page=0, text="a", top=10.0, x0=50.0), Line(page=0, text="b", top=20.0, x0=52.0)]
    assert order_by_columns(lines, 1) is lines


def test_two_column_layout_reorders_by_column_not_raw_top():
    # A real column gutter is hundreds of pt wide; interleaved by raw top the way
    # pdfplumber would emit them (left/right words at similar y mixed together).
    left = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=50.0) for i in range(3)]
    right = [Line(page=0, text=f"R{i}", top=float(i * 10), x0=300.0) for i in range(3)]
    mixed = sorted(left + right, key=lambda l: l.top)

    result = order_by_columns(mixed, 2)

    left_tops = [l.top for l in result if l.text.startswith("L")]
    right_tops = [l.top for l in result if l.text.startswith("R")]
    assert max(left_tops) < min(right_tops)


def test_no_real_gap_stays_single_column():
    # x0 varies only by ordinary paragraph-indent amounts -- no real column gutter.
    lines = [Line(page=0, text=f"x{i}", top=float(i), x0=50.0 + i) for i in range(10)]
    columns, boundary = detect_column_count(lines)
    assert columns == 1
    assert boundary is None
    # order_by_columns now detects per page (not once for the whole input, see its
    # docstring), so it always returns a new list -- content equality is the real
    # contract, not object identity.
    assert order_by_columns(lines, 2) == lines


def test_two_column_layout_returns_lines_actually_sorted_by_reading_order():
    """BUG FOUND 2026-08-28: order_by_columns computed the right synthetic `top`
    for each line but returned them in their ORIGINAL (raw top-to-bottom,
    left/right interleaved) order -- a caller that only compares (page, top)
    tuples got the right answer either way, but one that walks the list in
    sequence (spec_building._split_lines' paragraph grouping) silently stitched
    a left-column line and an unrelated right-column line together. This is the
    real regression check: not just "are the values right" (see the test above,
    which passed even with the bug present) but "is the returned LIST actually
    in that order."
    """
    left = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=50.0) for i in range(3)]
    right = [Line(page=0, text=f"R{i}", top=float(i * 10), x0=300.0) for i in range(3)]
    mixed = sorted(left + right, key=lambda l: l.top)

    result = order_by_columns(mixed, 2)

    assert [l.text for l in result] == ["L0", "L1", "L2", "R0", "R1", "R2"]


def test_margin_glyph_drop_only_applies_when_columns_greater_than_one():
    """BUG FOUND 2026-08-28: drop_repeating_margin_glyphs was originally called
    unconditionally at the top of order_by_columns, before the `columns <= 1`
    early return -- so it started silently applying to single-column manuals
    too, a layout this glyph-repetition heuristic was never validated against
    (it regressed the real subaru_v1/outback-2026 pipeline: 23->21 functions).
    A line that would normally be dropped as a repeating decorative glyph must
    survive untouched when columns == 1.
    """
    lines = [
        Line(page=p, text="Chapter Tab", top=10.0, x0=500.0, size=20.0)
        for p in range(4)
    ] + [Line(page=p, text=f"Body text on page {p}.", top=100.0, x0=60.0) for p in range(4)]

    assert order_by_columns(lines, 1) == lines

    result_2col = order_by_columns(lines, 2)
    assert "Chapter Tab" not in [l.text for l in result_2col]


def test_repeating_glyph_at_same_position_across_pages_is_dropped_before_column_detection():
    """Confirmed against the real 2025 Subaru supplement: a decorative margin
    graphic ("Navigation"/"System"/"7") sits further right (x0=598-609) than the
    page's real right-hand text column (x0=348-488), so the widest x0 gap on the
    page -- what detect_column_count picks as the column boundary -- was drawn
    between the real right column and the glyph instead of between the real left
    and right columns, merging both real columns into one and leaving their
    content interleaved by raw vertical position. Dropping the glyph first (see
    order_by_columns) fixes this."""
    left = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=80.0) for i in range(3)]
    right = [Line(page=0, text=f"R{i}", top=float(i * 10), x0=400.0) for i in range(3)]
    glyph = [
        Line(page=p, text="Deco", top=50.0, x0=700.0, size=40.0) for p in range(3)
    ]
    mixed = sorted(left + right + glyph, key=lambda l: (l.page, l.top))

    result = order_by_columns(mixed, 2)

    assert "Deco" not in [l.text for l in result]
    assert [l.text for l in result if l.page == 0] == ["L0", "L1", "L2", "R0", "R1", "R2"]


def test_drop_repeating_margin_glyphs_requires_same_position_and_text():
    same_key = [Line(page=p, text="Tab", top=10.0, x0=500.0) for p in range(3)]
    different_page_content = [Line(page=p, text=f"unique {p}", top=10.0, x0=500.0) for p in range(3)]
    only_two_pages = [Line(page=p, text="Tab2", top=20.0, x0=500.0) for p in range(2)]

    result = drop_repeating_margin_glyphs(same_key + different_page_content + only_two_pages)

    assert "Tab" not in [l.text for l in result]
    assert [l.text for l in result if "unique" in l.text] == ["unique 0", "unique 1", "unique 2"]
    assert "Tab2" in [l.text for l in result]  # only 2 pages, below the min_repeat_pages bar


def test_detect_sidebars_is_off_by_default_even_with_a_real_looking_sidebar_shape():
    """LayoutConfig.column_detect_per_page defaults to False (see domain.profile)
    -- order_by_columns must leave a columns=1 manual's pages completely
    untouched unless a caller explicitly opts in, even when a page shape would
    otherwise qualify as a sidebar. Protects every existing profile's behavior
    (Subaru, Honda Pilot) from the 2026-09-04 "column-count-agnostic"
    experiment's confirmed regression risk (docs/HANDOVER.md same date)."""
    left = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=50.0) for i in range(3)]
    right = [Line(page=0, text=f"R{i}", top=float(i * 10), x0=300.0) for i in range(3)]
    mixed = sorted(left + right, key=lambda l: l.top)

    assert order_by_columns(mixed, 1) == mixed
    assert order_by_columns(mixed, 1, detect_sidebars=False) == mixed


def test_detect_sidebars_reorders_a_genuine_looking_sidebar_on_a_1column_manual():
    """Real Honda CR-V 2026 case (docs/ARCHITECTURE.md "17."): a chapter that's
    1-column overall still has pages with a real local sidebar (an icon-meaning
    legend running parallel to the main step-by-step procedure column) -- with
    detect_sidebars=True and enough corroboration (>=2 lines each side, real
    vertical overlap), it must be reordered the same way a columns=2 manual
    would be."""
    left = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=50.0) for i in range(4)]
    right = [Line(page=0, text=f"R{i}", top=float(i * 10) + 5.0, x0=300.0) for i in range(4)]
    mixed = sorted(left + right, key=lambda l: l.top)

    result = order_by_columns(mixed, 1, detect_sidebars=True)

    assert [l.text for l in result] == ["L0", "L1", "L2", "L3", "R0", "R1", "R2", "R3"]


def test_detect_sidebars_ignores_a_single_stray_line_on_the_far_side():
    """The clearest real false-positive shape found during investigation (a
    Subaru page number/lone dot-leader digit landing far to one side of an
    otherwise single-column page): only 1 line on the far side, with zero
    vertical overlap with the main text -- must NOT be treated as a sidebar."""
    main = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=50.0) for i in range(10)]
    stray = [Line(page=0, text="1", top=500.0, x0=560.0)]  # a lone page-number-shaped line
    mixed = main + stray

    result = order_by_columns(mixed, 1, detect_sidebars=True)

    assert result == mixed


def test_detect_sidebars_ignores_two_lines_with_no_vertical_overlap():
    """Two lines on the far side is still not enough if they don't run in
    parallel with the main column -- e.g. a small legend/graphic sitting well
    below the main text, not a real sidebar note."""
    main = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=50.0) for i in range(5)]
    far_below = [Line(page=0, text="Poor", top=500.0, x0=400.0), Line(page=0, text="Excellent", top=510.0, x0=400.0)]
    mixed = main + far_below

    result = order_by_columns(mixed, 1, detect_sidebars=True)

    assert result == mixed


def test_synthetic_top_for_position_matches_column_major_order():
    """A raw (x0, top) position -- e.g. a PDF image rect's own coordinates,
    which never go through order_by_columns -- must convert into the same
    column-major key a Section built from these same lines would use, or a
    figure can never be compared against its section correctly (see
    use_cases.py::_extract_figures, BUG FOUND 2026-08-28: a right-column
    figure's raw top could never satisfy a right-column section's synthetic
    start_top, so it silently landed on an earlier, unrelated section)."""
    page_lines = [
        Line(page=0, text="left heading", top=10.0, x0=80.0),
        Line(page=0, text="right heading", top=10.0, x0=400.0),
    ]

    assert synthetic_top_for_position(page_lines, x0=80.0, top=55.0, columns=2) == 55.0
    right_top = synthetic_top_for_position(page_lines, x0=400.0, top=55.0, columns=2)
    assert right_top > 55.0 + 1000  # pushed into the column-1 synthetic range

    # single column: never touched
    assert synthetic_top_for_position(page_lines, x0=400.0, top=55.0, columns=1) == 55.0
