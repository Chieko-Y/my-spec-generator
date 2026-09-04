"""Regression test for dropping rotated (upright=False) words before line-
grouping (infrastructure/pdf_reader.py::PdfManualReader.read()).

Real Honda CR-V 2026 case (docs/HANDOVER.md 2026-09-04): a vertical page-edge
tab label ("Features", printed top-to-bottom in the side margin of nearly
every page of that chapter) is real extractable text, not an image.
pdfplumber still reports a page-coordinate bounding box for it, and on some
pages that box's `top` coincidentally lands within _group_words_into_lines'
clustering tolerance of a real horizontal line's `top` -- fusing the rotated
label onto real heading/step text (e.g. "Features ■To make a call..."),
confirmed directly by a user reading the real generated output. `read()` now
filters out any word with upright=False before grouping; this test exercises
the grouping function itself with a fabricated rotated word to show why that
filter is necessary and that applying it prevents the fusion.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure.pdf_reader import _group_words_into_lines


def _word(
    text: str, top: float, x0: float, upright: bool = True, size: float = 9.0, x1: float | None = None
) -> dict:
    return {
        "text": text,
        "top": top,
        "x0": x0,
        "x1": x0 + len(text) * 6.0 if x1 is None else x1,
        "size": size,
        "height": size,
        "upright": upright,
    }


def test_a_rotated_word_at_the_same_top_fuses_into_a_real_line_if_not_filtered():
    words = [
        _word("Features", top=196.9, x0=575.1, upright=False),  # rotated side tab
        _word("To", top=196.9, x0=11.3, upright=True),
        _word("make", top=196.9, x0=20.0, upright=True),
        _word("a", top=196.9, x0=40.0, upright=True),
        _word("call.", top=196.9, x0=50.0, upright=True),
    ]

    lines = _group_words_into_lines(words, page_index=0)

    assert len(lines) == 1
    assert lines[0].text == "To make a call. Features"


def test_filtering_upright_false_words_first_prevents_the_fusion():
    words = [
        _word("Features", top=196.9, x0=575.1, upright=False),
        _word("To", top=196.9, x0=11.3, upright=True),
        _word("make", top=196.9, x0=20.0, upright=True),
        _word("a", top=196.9, x0=40.0, upright=True),
        _word("call.", top=196.9, x0=50.0, upright=True),
    ]
    upright_only = [w for w in words if w.get("upright", True)]

    lines = _group_words_into_lines(upright_only, page_index=0)

    assert len(lines) == 1
    assert lines[0].text == "To make a call."


def test_split_cross_column_fuses_a_bold_heading_with_an_unrelated_light_sentence_by_default():
    """Real Honda CR-V 2026 case, 2026-09-04: on an otherwise columns=1 page, a
    short bold-9pt heading ("Phone menu screen", x0=34-134) and an unrelated
    light-8pt sentence fragment from a genuinely different zone of the page
    (x0=371+, ~237pt gap) land in the same Y-cluster and fuse into one Line's
    text by default -- reported by a user reading real generated output, who
    pointed out the two pieces are "clearly separated, and the formatting is
    different too" (bold vs light, 9pt vs 8pt, confirmed against the real PDF).
    """
    words = [
        _word("Phone", top=82.1, x0=34.0, x1=68.9, size=9.0),
        _word("menu", top=82.1, x0=72.9, x1=98.4, size=9.0),
        _word("screen", top=82.1, x0=99.4, x1=133.9, size=9.0),
        _word("compatible", top=82.7, x0=371.3, x1=409.3, size=8.0),
        _word("cell", top=82.7, x0=410.8, x1=422.7, size=8.0),
    ]

    lines = _group_words_into_lines(words, page_index=0)

    assert len(lines) == 1
    assert lines[0].text == "Phone menu screen compatible cell"


def test_split_cross_column_opt_in_keeps_the_two_zones_as_separate_lines():
    """LayoutConfig.column_detect_per_page (threaded through PdfManualReader.
    read() as split_cross_column) opts a columns=1 manual into the same
    cross-column word-splitting a columns>1 manual already gets -- default
    False (previous test) preserves every other manual's exact behavior."""
    words = [
        _word("Phone", top=82.1, x0=34.0, x1=68.9, size=9.0),
        _word("menu", top=82.1, x0=72.9, x1=98.4, size=9.0),
        _word("screen", top=82.1, x0=99.4, x1=133.9, size=9.0),
        _word("compatible", top=82.7, x0=371.3, x1=409.3, size=8.0),
        _word("cell", top=82.7, x0=410.8, x1=422.7, size=8.0),
    ]

    lines = _group_words_into_lines(words, page_index=0, columns=1, split_cross_column=True)

    assert sorted(l.text for l in lines) == ["Phone menu screen", "compatible cell"]
