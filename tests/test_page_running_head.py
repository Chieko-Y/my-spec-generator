"""Regression tests for domain.manual_parsing.capture_page_running_head, added
2026-08-31. The real Subaru Outback 2026 PDF's header band carries two lines
per page: a production-filename/page-number artifact ("NB8_北米英語.book 16
ページ" -- a FrameMaker book-file name) and the chapter/section running-head
label itself. User's explicit call: drop the filename line because it's a
filename (redundant with the p.<n> citation already shown), NOT because it's
Japanese -- a future Japanese-market manual's real running-head text must
survive this filter untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Line, capture_page_running_head


def test_production_filename_line_is_dropped():
    lines = [
        Line(page=0, text="NB8_北米英語.book 16 ページ", top=69.3),
        Line(page=0, text="Basic information before operation", top=152.0),
        Line(page=0, text="Real body text below the header band.", top=200.0),
    ]
    result = capture_page_running_head(lines, header_boundary_pt=165.0)
    assert result == {0: "Basic information before operation"}


def test_japanese_running_head_text_is_kept_when_it_is_not_a_filename():
    """A future Japanese-market manual's real running-head label (e.g. its own
    section title) must not be discarded just because it's Japanese -- only
    the filename-shaped line should ever be dropped."""
    lines = [Line(page=0, text="初期画面について", top=152.0)]
    assert capture_page_running_head(lines, header_boundary_pt=165.0) == {0: "初期画面について"}


def test_page_with_only_a_filename_header_line_yields_no_citation():
    lines = [Line(page=0, text="NB8_北米英語.book 16 ページ", top=69.3)]
    assert capture_page_running_head(lines, header_boundary_pt=165.0) == {}


def test_lines_outside_the_header_band_are_ignored():
    lines = [Line(page=0, text="Some running head", top=200.0)]
    assert capture_page_running_head(lines, header_boundary_pt=165.0) == {}


def test_honda_breadcrumb_arrow_glyphs_are_stripped_and_replaced_with_spaces():
    """Real Honda CR-V 2026 case, "5. Start Up" (Features), 2026-09-08: this
    manual's "▶▶Area▶Function" margin breadcrumb draws its arrows by reusing
    the Latin lowercase "u" code point in the HONDACommon font -- Line objects
    here carry no font info, so the raw text leaks the arrow glyphs verbatim
    ('uu9" Color TouchscreenuStart Up'), including one glued directly between
    two labels with no real space at all. Reported directly by a user reading
    real generated output while investigating an unrelated figure-caption bug
    for this exact page."""
    lines = [Line(page=260, text='uu9" Color TouchscreenuStart Up', top=13.8, x0=431.7)]
    result = capture_page_running_head(lines, header_boundary_pt=20.0)
    assert result == {260: '9" Color Touchscreen Start Up'}


def test_a_real_lowercase_u_inside_a_word_is_left_alone():
    """The arrow-glyph strip must never touch an ordinary word containing the
    letter "u" -- only a "u" run sitting at a label boundary (start of text,
    or glued directly onto the next capitalized/numeric label with no real
    space) qualifies. "Audio Settings" has a real "u" mid-word and a real
    space before its capitalized second word -- neither should ever match."""
    lines = [Line(page=0, text="Audio Settings", top=13.8)]
    assert capture_page_running_head(lines, header_boundary_pt=20.0) == {0: "Audio Settings"}
