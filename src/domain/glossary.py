"""Glossary matching: find where a manual wording occurs. Deliberately has no
replace/substitute/translate/rewrite function — the dictionary is an annotation layer,
never a rewrite of source_text or requirement text. See CONCEPT.md / CLAUDE.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .overlay import GlossaryTerm


@dataclass
class GlossaryMatch:
    term_id: str
    in_house_term: str
    manual_wording: str
    count: int


def annotate(text: str, terms: list[GlossaryTerm], maker: str = "") -> list[GlossaryMatch]:
    """Return the match counts only. Does not alter `text`. A wording scoped to
    one maker (ManualWording.maker) is only counted when `maker` matches it
    (case-insensitive); a wording with no maker (used by every maker) always
    counts. Pass maker="" to count every wording regardless of scope."""
    matches: list[GlossaryMatch] = []
    for term in terms:
        for wording in term.manual_wordings:
            if not wording.text:
                continue
            if maker and wording.maker and wording.maker.lower() != maker.lower():
                continue
            count = len(re.findall(re.escape(wording.text), text, flags=re.IGNORECASE))
            if count:
                matches.append(
                    GlossaryMatch(
                        term_id=term.term_id,
                        in_house_term=term.in_house_term,
                        manual_wording=wording.text,
                        count=count,
                    )
                )
    return matches
