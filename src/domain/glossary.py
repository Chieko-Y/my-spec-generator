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


def annotate(text: str, terms: list[GlossaryTerm]) -> list[GlossaryMatch]:
    """Return the match positions/counts only. Does not alter `text`."""
    matches: list[GlossaryMatch] = []
    for term in terms:
        for wording in term.manual_wordings:
            if not wording:
                continue
            count = len(re.findall(re.escape(wording), text, flags=re.IGNORECASE))
            if count:
                matches.append(
                    GlossaryMatch(
                        term_id=term.term_id,
                        in_house_term=term.in_house_term,
                        manual_wording=wording,
                        count=count,
                    )
                )
    return matches
