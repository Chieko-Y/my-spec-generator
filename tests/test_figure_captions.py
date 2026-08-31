"""Regression tests for domain.figures.caption_for — locks in the 2 real-Subaru-PDF
cases found and fixed 2026-08-25/26 (see docs/HANDOVER.md for the full incidents).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.figures import caption_for, is_qr_code_caption
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
