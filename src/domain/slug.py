"""URL/filesystem-safe slug from arbitrary text (e.g. a chapter title -> chapter_slug
used as a directory name). Stdlib only, so both domain/application and infrastructure
can share one implementation instead of drifting.
"""
from __future__ import annotations

import re
import unicodedata

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = _SLUG_RE.sub("-", text.lower()).strip("-")
    return text or "untitled"
