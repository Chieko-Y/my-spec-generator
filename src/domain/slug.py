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


_FILENAME_SLUG_MAX_LEN = 80  # Windows MAX_PATH (260) minus the deep workspace path


def function_filename(chapter_number: str, title: str) -> str:
    """Published per-function file name. The title slug is capped: a long heading
    (Outback 2025 Quick Guide's first two "functions" are whole sentences) made a
    name too long for git/Windows to even index (2026-09-21)."""
    slug = slugify(title)[:_FILENAME_SLUG_MAX_LEN].rstrip("-")
    return f"{chapter_number}-{slug}.md"
