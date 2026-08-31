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
