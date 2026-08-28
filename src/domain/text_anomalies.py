"""Shape-based signals that a piece of extracted text was cut mid-token by some PDF
processing step rather than being genuine, intact source text -- orphan punctuation,
replacement chars, leftover bullet glyphs, very-short fragments. Originally a one-off
script (scratch/audit_text_anomalies.py, 2026-08-26) for auditing already-generated
SUBARU chapters with no original-app reference to diff against; promoted here so
profile_fitness.py can reuse the same signals to score whether a candidate profile's
parsing of a brand-new manual is garbled, instead of re-implementing them.
"""
from __future__ import annotations

import re

REPLACEMENT_CHAR = "�"
# Private Use Area range, matching pdf_reader.py's own icon-glyph strip regex
# (_ICON_GLYPH_RE) -- a leftover PUA codepoint here means that strip missed one.
# BUG FOUND 2026-08-27: this was copy-pasted from scratch/audit_text_anomalies.py
# as a literal "[-]" (an ordinary hyphen), not the PUA range -- flagged every
# hyphenated word ("11.6-inch", "Hands-Free", ...) as a false positive, inflating
# every anomaly-ratio measurement taken today (both the SUBARU 2026 7.3% baseline
# and the 2025 supplement's 18.4%/22.7% figures were overstated because of this).
PUA_GLYPH_LEFTOVER_RE = re.compile("[-]")
# A token starting with a "closing" punctuation mark, or ending with an "opening"
# one, is a strong signal of a split that landed inside a bracket/quote pair instead
# of between words (exactly what the bullet-in-placeholder bug produced: text
# starting with a bare ">", see docs/HANDOVER.md 2026-08-26).
ORPHAN_LEAD_RE = re.compile(r'^[>\]\)\}»”’]')
ORPHAN_TRAIL_RE = re.compile(r'[<\[\(\{«“‘]$')
BULLET_CHARS = "●•▪○◦"
BULLET_LEFTOVER_RE = re.compile("[" + BULLET_CHARS + "]")


def flag(text: str) -> list[str]:
    reasons = []
    if not text:
        return reasons
    if REPLACEMENT_CHAR in text:
        reasons.append("replacement-char(U+FFFD)")
    if PUA_GLYPH_LEFTOVER_RE.search(text):
        reasons.append("PUA-glyph-leftover")
    if ORPHAN_LEAD_RE.match(text.strip()):
        reasons.append("starts-with-closing-punct")
    if ORPHAN_TRAIL_RE.search(text.strip()):
        reasons.append("ends-with-opening-punct")
    if BULLET_LEFTOVER_RE.search(text):
        reasons.append("bullet-char-leftover")
    stripped = text.strip(" .:,;-")
    if 0 < len(stripped) <= 2:
        reasons.append("very-short-fragment")
    return reasons
