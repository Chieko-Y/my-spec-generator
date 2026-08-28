"""Rule-based fitness check: does an existing Profile's layout assumptions actually
fit a newly-registered PDF? No AI -- pure signal checks over Line/Bookmark data
already read from the PDF, reusing the same shape-based garbling signals the SUBARU
audit script used (text_anomalies.flag) instead of reinventing a quality metric. See
docs/HANDOVER.md 2026-08-26 "AIによるProfile判定" for why this two-tier design (cheap
fitness check first, expensive from-scratch derivation only when this fails) was
chosen over calling an LLM for every new manual.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .manual_parsing import (
    Bookmark,
    Line,
    build_blocks,
    detect_column_count,
    filter_page_furniture,
    order_by_columns,
)
from .profile import Profile
from .spec_building import build_manual_spec_functions
from .text_anomalies import flag as flag_anomalies

_MIN_TOP_LEVEL_BOOKMARKS = 3
# A real chapter title is words; a print-production marker is a short run of
# uppercase letters/digits glued together with underscores (confirmed against the
# real 2025 Subaru supplement PDF: "4C_P1_P66_...", "1C_P67_P256_...") -- no
# lowercase letters and no spaces is the distinguishing shape.
_PRODUCTION_MARKER_RE = re.compile(r"^[0-9A-Z_]+$")
_ANOMALY_RATIO_THRESHOLD = 0.15


@dataclass
class FitnessReport:
    fits: bool
    reasons: list[str] = field(default_factory=list)
    bookmark_depth_ok: bool | None = None
    column_match_ok: bool | None = None
    anomaly_ratio: float | None = None


def bookmark_depth_ok(bookmarks: list[Bookmark]) -> tuple[bool, str]:
    """Shared with profile_derivation.py's section_source decision -- a real
    chapter-shaped bookmark outline (see this function's shape checks) is exactly
    the condition under which "bookmarks" is usable as section_source at all,
    whether we're checking an existing profile's assumption (here) or deciding a
    brand-new one from scratch (there)."""
    if not bookmarks:
        return False, "no bookmarks in this PDF"
    top_level = min(b.level for b in bookmarks)
    chapters = [b for b in bookmarks if b.level == top_level]
    if len(chapters) < _MIN_TOP_LEVEL_BOOKMARKS:
        return False, f"only {len(chapters)} top-level bookmark(s) (need >= {_MIN_TOP_LEVEL_BOOKMARKS})"
    marker_like = [c.title for c in chapters if _PRODUCTION_MARKER_RE.match(c.title.replace(" ", ""))]
    if len(marker_like) > len(chapters) / 2:
        return False, f"top-level bookmarks look like print-production markers, not chapter titles: {marker_like[:3]}"
    return True, ""


def _column_match_ok(lines: list[Line], profile: Profile) -> tuple[bool, str]:
    detected, _ = detect_column_count(lines)
    if detected != profile.layout.columns:
        return False, f"detected {detected}-column layout, profile assumes {profile.layout.columns}"
    return True, ""


def _sample_anomaly_ratio(
    lines: list[Line], bookmarks: list[Bookmark], profile: Profile, chapter_prefix: str | None
) -> float | None:
    """Actually run the parsing pipeline with this profile on one sample chapter and
    score the result with text_anomalies.flag -- the most direct signal available,
    matching this project's practice of checking real output rather than assuming a
    profile fits from its config values alone. Only meaningful for
    section_source="bookmarks" today: running_head/chapter_toc sampling would need a
    chapter target this function doesn't have without running its own detection
    first, which belongs in profile_derivation.py, not here.
    """
    if profile.layout.section_source != "bookmarks" or not bookmarks:
        return None
    top_level = min(b.level for b in bookmarks)
    prefix = chapter_prefix or next((b.title for b in bookmarks if b.level == top_level), None)
    if prefix is None:
        return None

    filtered = filter_page_furniture(
        lines, profile.layout.header_boundary_pt, profile.layout.footer_boundary_pt
    )
    filtered = order_by_columns(filtered, profile.layout.columns)
    blocks = build_blocks(
        filtered, bookmarks, prefix, section_depth_below_chapter=profile.layout.section_depth_below_chapter
    )
    if not blocks.sections:
        return 1.0  # nothing parsed at all -- worst case, not "no signal"

    functions = build_manual_spec_functions(
        blocks.sections, profile, "fitness-check", blocks.chapter_title or prefix
    )
    total = 0
    flagged = 0
    for fn in functions:
        for req in fn.requirements:
            total += 1
            if flag_anomalies(req.text):
                flagged += 1
        for step in fn.procedure:
            total += 1
            if flag_anomalies(step.text):
                flagged += 1
    if total == 0:
        return 1.0
    return flagged / total


def score_fitness(
    lines: list[Line],
    bookmarks: list[Bookmark],
    profile: Profile,
    chapter_prefix: str | None = None,
) -> FitnessReport:
    reasons: list[str] = []

    bookmarks_ok: bool | None = None
    if profile.layout.section_source == "bookmarks":
        bookmarks_ok, reason = bookmark_depth_ok(bookmarks)
        if not bookmarks_ok:
            reasons.append(reason)

    column_match_ok, reason = _column_match_ok(lines, profile)
    if not column_match_ok:
        reasons.append(reason)

    anomaly_ratio = _sample_anomaly_ratio(lines, bookmarks, profile, chapter_prefix)
    if anomaly_ratio is not None and anomaly_ratio > _ANOMALY_RATIO_THRESHOLD:
        reasons.append(
            f"{anomaly_ratio:.0%} of sample requirement/step text looks garbled "
            f"(threshold {_ANOMALY_RATIO_THRESHOLD:.0%})"
        )

    return FitnessReport(
        fits=not reasons,
        reasons=reasons,
        bookmark_depth_ok=bookmarks_ok,
        column_match_ok=column_match_ok,
        anomaly_ratio=anomaly_ratio,
    )
