"""Regression tests for domain.figures.caption_for — locks in the 2 real-Subaru-PDF
cases found and fixed 2026-08-25/26 (see docs/HANDOVER.md for the full incidents).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.figures import caption_for, is_full_bleed_placement, is_qr_code_caption, is_stretched_fill
from domain.manual_parsing import Line


def test_picks_the_nearest_line_in_the_same_column_not_an_offcolumn_line_that_happens_to_overlap():
    """Real Subaru case, page 103: a figure's own rect vertically overlaps a lone
    legend digit "5" sitting ~320pt away in an unrelated callout column, while the
    real caption-worthy line ("Select to change audio modes.") sits in the same
    column just below the figure but doesn't vertically overlap it at all. Naive
    nearest-by-vertical-distance picked "5"; column-matching must prefer the
    same-column line instead."""
    rect = (165.6, 329.8, 435.1, 481.1)  # (x0, top, x1, bottom)
    lines = [
        Line(page=0, text="5", top=437.3, x0=487.5),  # off-column, vertically overlaps rect
        Line(page=0, text="Select to change audio modes.", top=543.3, x0=157.0),  # same column, below rect
        Line(page=0, text="Unrelated line on a different page.", top=200.0, x0=157.0),
        Line(page=1, text="5", top=437.3, x0=200.0),  # different page — must be ignored
    ]
    result = caption_for(rect, page=0, lines=lines)
    assert result is not None
    assert result.text == "Select to change audio modes."


def test_excludes_a_lone_short_line_even_when_no_better_column_candidate_exists():
    """Real Subaru case: a lone "1" recurs at the exact same coordinates on 8
    different pages — a page-decoration glyph, not body text — and happened to fall
    inside 3 different figures' vertical span with no other line anywhere near.
    A caption this short is useless even on the small chance it were real, so it
    must be excluded outright rather than won by default."""
    rect = (305.9, 186.8, 465.1, 286.4)
    lines = [
        Line(page=0, text="1", top=267.2, x0=487.5),  # inside rect's vertical span, but too short
        Line(page=0, text="Center information display overview", top=313.6, x0=124.7),
    ]
    result = caption_for(rect, page=0, lines=lines)
    assert result is not None
    assert result.text == "Center information display overview"


def test_returns_none_when_every_candidate_on_the_page_is_too_short():
    rect = (100.0, 100.0, 200.0, 200.0)
    lines = [Line(page=0, text="1", top=150.0, x0=100.0), Line(page=0, text="12", top=400.0, x0=100.0)]
    assert caption_for(rect, page=0, lines=lines) is None


def test_returns_none_when_page_has_no_lines_at_all():
    rect = (0.0, 0.0, 10.0, 10.0)
    assert caption_for(rect, page=5, lines=[]) is None


def test_is_qr_code_caption_flags_a_bare_url():
    """Real Subaru Outback 2026 case, 2026-08-31: two small (57x57pt) images
    captioned exactly a bare URL ("https://www.mysubaru.com/connect.html")
    are printed QR codes, not real screen illustrations -- the original app's
    own output for this manual (Navigation, "About Subaru connected
    navigation") does not include them as figures at all."""
    assert is_qr_code_caption("https://www.mysubaru.com/connect.html") is True
    assert is_qr_code_caption("https://www.mysubaru.ca/connect.html") is True


def test_is_qr_code_caption_does_not_flag_real_captions():
    assert is_qr_code_caption("Select to change audio modes.") is False
    assert is_qr_code_caption("Visit https://www.mysubaru.com for details.") is False
    assert is_qr_code_caption(None) is False
    assert is_qr_code_caption("") is False


def test_is_stretched_fill_flags_a_one_pixel_background_box():
    """Real Honda Pilot PDF case, 2026-09-02: a text-background box painted by
    stretching a 1x1px source image to 194.2x336.3pt (~0.3 effective dpi) was
    the widest embedded image on nearly every page of the manual, dragging the
    auto-derived figure_min_width/height_pt up to ~517x299pt -- above every
    real figure in the whole manual (max ~337x261pt) -- and silently excluding
    all of them. This is the same defect the original app's own docs record
    fixing on this exact PDF (a stretched fill sits at ~0.4dpi, a real figure
    or icon at 130dpi+, three orders of magnitude apart)."""
    assert is_stretched_fill(1, 1, 194.2, 336.3) is True


def test_is_stretched_fill_does_not_flag_real_figures_or_icons():
    # Real Honda Pilot measurements, same PDF/session: a full screen-mockup
    # figure and a small inline icon, both ~150-300dpi.
    assert is_stretched_fill(631, 309, 227.2, 111.1) is False
    assert is_stretched_fill(31, 24, 11.1, 8.5) is False


def test_is_stretched_fill_is_false_without_native_size():
    # Most PDF libraries won't always expose srcsize -- fall back to size-only
    # filtering (domain.figures.is_figure_sized) rather than guessing.
    assert is_stretched_fill(None, None, 194.2, 336.3) is False
    assert is_stretched_fill(0, 0, 194.2, 336.3) is False


def test_is_full_bleed_placement_flags_a_negative_origin():
    """Real Honda Pilot PDF case, 2026-09-02: a 696x260.9pt chapter-divider photo
    (a real, high-dpi embedded image -- not a stretched fill) sits at x0=-11.1pt,
    bleeding past the page's own left edge, on 8 of the manual's 9 chapters.
    Left in, it alone still drags the auto-derived figure_min_width_pt up to
    ~517pt -- above every real figure in the manual -- even after stretched
    fills are excluded, since it's real and passes that filter cleanly."""
    assert is_full_bleed_placement((-11.1, 45.4, 684.9, 306.3)) is True
    assert is_full_bleed_placement((10.0, -2.0, 200.0, 150.0)) is True


def test_is_full_bleed_placement_does_not_flag_a_real_figure():
    assert is_full_bleed_placement((123.4, 197.8, 256.2, 293.9)) is False
