"""Regression test for a real bug found 2026-08-27: domain.text_anomalies.flag's
PUA_GLYPH_LEFTOVER_RE was copy-pasted from scratch/audit_text_anomalies.py as a
literal "[-]" (an ordinary ASCII hyphen), not the PUA range src/infrastructure/
pdf_reader.py's own icon-glyph strip regex uses. This flagged every hyphenated word
("11.6-inch", "Hands-Free", "3.0A") as a false "PUA-glyph-leftover" anomaly,
inflating every anomaly-ratio measurement in profile_fitness.score_fitness that day
(SUBARU 2026's reported 7.3% and the 2025 supplement's reported 18.4% both dropped
to 0.0% once this was fixed against the exact same generated output -- see
docs/HANDOVER.md 2026-08-27)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.text_anomalies import flag

# A genuine unstripped icon-font codepoint (Private Use Area), simulating the strip
# in pdf_reader.py having missed one -- same class of bug fixed there 2026-08-26
# for U+F075.
_PUA_GLYPH = chr(0xF075)


def test_ordinary_hyphenated_words_are_not_flagged():
    assert flag("11.6-inch display system/11.6-inch display with Navi system.") == []
    assert flag("Hands-Free Profile Ver. 1.0.") == []
    assert flag("This operation cannot be performed while driving.") == []


def test_a_real_leftover_pua_glyph_is_still_flagged():
    assert "PUA-glyph-leftover" in flag(_PUA_GLYPH + "Phone commands")


def test_a_real_replacement_char_is_flagged_but_a_valid_arrow_is_not():
    # U+2192 (an arrow) is a real, valid "see page N" cross-reference glyph the
    # source PDFs use -- confirmed 2026-08-27 after initially misreading it, via a
    # console font that can't render it, as corruption. Only the genuine U+FFFD
    # replacement char counts.
    assert flag("Display the phone screen. (" + chr(0x2192) + "P.108).") == []
    assert "replacement-char(U+FFFD)" in flag("Display the phone screen. (" + chr(0xFFFD) + "P.108).")
