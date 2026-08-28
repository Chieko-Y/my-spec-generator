"""Regression tests for infrastructure.pdf_reader._group_words_into_lines — no real
PDF needed, fake pdfplumber-style word dicts are enough since the function only reads
'text' / 'top' / 'x0' / (optional) 'size' per word. Locks in 2 real-Subaru-PDF fixes
from 2026-08-25/26 (see docs/HANDOVER.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure.pdf_reader import _group_words_into_lines


def _word(text: str, top: float, x0: float) -> dict:
    return {"text": text, "top": top, "x0": x0, "size": 10.0}


def test_icon_font_glyph_fused_onto_a_word_is_stripped_not_kept():
    """Real Subaru case: the manual's icon font puts a Private Use Area codepoint
    (U+F075) directly ahead of a sub-heading word with no space, e.g.
    'Phone commands'. pdfplumber has no glyph for it and previously carried it
    through into the output text, where it rendered as a tofu/box character."""
    words = [_word("Phone", top=100.0, x0=50.0), _word("commands", top=100.0, x0=90.0)]
    lines = _group_words_into_lines(words, page_index=0)
    assert len(lines) == 1
    assert lines[0].text == "Phone commands"
    assert "" not in lines[0].text


def test_ordinary_words_are_unaffected():
    words = [_word("Touch", top=50.0, x0=10.0), _word("the", top=50.0, x0=40.0), _word("icon.", top=50.0, x0=60.0)]
    lines = _group_words_into_lines(words, page_index=2)
    assert len(lines) == 1
    assert lines[0].text == "Touch the icon."
    assert lines[0].page == 2


def test_a_word_that_is_entirely_an_icon_glyph_is_dropped_not_left_as_an_empty_token():
    words = [
        _word("", top=10.0, x0=5.0),  # a lone icon glyph, its own "word"
        _word("Real", top=10.0, x0=20.0),
        _word("text.", top=10.0, x0=45.0),
    ]
    lines = _group_words_into_lines(words, page_index=0)
    assert len(lines) == 1
    assert lines[0].text == "Real text."


def test_lines_split_by_vertical_proximity_not_a_fixed_grid_boundary():
    """Real Subaru case: two words 1.06pt apart in `top` used to land in different
    line-buckets under a fixed-grid rounding scheme, splitting one printed line's
    trailing hyphen ("dis-") into its own phantom line."""
    words = [
        _word("dis-", top=423.55, x0=10.0),
        _word("play", top=424.61, x0=40.0),  # 1.06pt away — same printed line
    ]
    lines = _group_words_into_lines(words, page_index=0)
    assert len(lines) == 1
    assert lines[0].text == "dis- play"
