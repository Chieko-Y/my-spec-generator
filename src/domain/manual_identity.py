"""Guess maker/model/year from a PDF's own self-description (bookmark root title +
cover page text). Pure text classification — no PDF library import here; the caller
extracts the two strings first.

This is a CANDIDATE only. The confirmed value always comes from a human (see
REQUIREMENTS.md G-4). This module exists specifically to fix bug #2 from the bug
report: when a document is registered without the app ever having read its own title,
the display later falls back to a raw manual_id slug. Surfacing a candidate title here
gives the registration form something better to prefill than nothing, in both the
manual-registration and drag-and-drop paths, using the *same* function either way so
the two paths cannot produce different-looking results.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Small built-in list — the real config/makers.json (36 IQS makers) was not handed
# over with this project, so this is deliberately short and easy to extend.
KNOWN_MAKERS = [
    "Toyota", "Honda", "Chevrolet", "GMC", "Cadillac", "Buick", "Ford", "Lincoln",
    "Jeep", "Ram", "Dodge", "Chrysler", "Mazda", "Subaru", "MINI", "BMW",
    "Mercedes-Benz", "Volkswagen", "Audi", "Nissan", "Infiniti", "Hyundai", "Kia",
    "Lexus", "Acura", "Volvo", "Tesla", "Genesis", "Mitsubishi", "Porsche",
]

_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-4]\d)\b")


@dataclass
class IdentityGuess:
    maker: str | None
    model: str | None
    year: str | None
    evidence: str


def guess_identity(bookmark_root_title: str, cover_text: str) -> IdentityGuess:
    combined = f"{bookmark_root_title}\n{cover_text}".strip()

    maker = next((m for m in KNOWN_MAKERS if m.lower() in combined.lower()), None)

    year_match = _YEAR_RE.search(combined)
    year = year_match.group(0) if year_match else None

    model = None
    if maker:
        # crude heuristic: the token(s) right after the maker name, up to the next
        # digit-year or a small stopword, are usually the model name
        pattern = re.compile(re.escape(maker) + r"\s+([A-Za-z0-9][\w-]*(?:\s+[A-Za-z0-9][\w-]*){0,2})", re.IGNORECASE)
        m = pattern.search(combined)
        if m:
            candidate = m.group(1).strip()
            candidate = _YEAR_RE.sub("", candidate).strip()
            stopwords = {"owner's", "owners", "manual", "guide", "navigation"}
            words = [w for w in candidate.split() if w.lower().strip(".,") not in stopwords]
            model = " ".join(words[:2]).strip() or None

    evidence = combined[:200]
    return IdentityGuess(maker=maker, model=model, year=year, evidence=evidence)
