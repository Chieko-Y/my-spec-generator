"""Profile: the "training data" — chapter-shape and slot-judgment words hand-derived
from a real requirements document, plus per-manufacturer layout knobs. Never learned
from a model; see ARCHITECTURE.md "Profile" section for why.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .model import SpecSlot


@dataclass
class SlotRule:
    slot: SpecSlot
    keywords: list[str] = field(default_factory=list)
    heading_patterns: list[str] = field(default_factory=list)


@dataclass
class LayoutConfig:
    section_source: str = "bookmarks"  # bookmarks | running_head | chapter_toc
    section_depth_below_chapter: int = 2
    running_head_regex: str | None = None
    columns: int = 1
    repair_kerning: bool = False
    # 8pt did not actually discriminate anything: measured directly against the
    # real Subaru PDF, 2026-08-25, inline UI icon images embedded in body text are
    # ~11.5pt square while the real screen-illustration figure on the same page is
    # 312x186pt — a threshold with real margin between those two groups is needed
    # to keep icons out of the figures list, not just >0.
    figure_min_width_pt: float = 40.0
    figure_min_height_pt: float = 40.0
    figure_merge_distance_pt: float = 3.0
    shallow_outline_level: int = 1
    # Page furniture (running head / page-footer) sits at a fixed vertical band on
    # every page — measured directly against a real PDF, not guessed (see
    # subaru_v1.json's derived_from). 0.0 / None both mean "no filtering", so
    # profiles that never set these behave exactly as before.
    header_boundary_pt: float = 0.0
    footer_boundary_pt: float | None = None


@dataclass
class Profile:
    profile_id: str
    extends: str | None
    derived_from: str
    slot_rules: list[SlotRule]
    layout: LayoutConfig
    excluded_section_titles: list[str] = field(default_factory=list)

    def slot_for(self, heading: str, body: str) -> SpecSlot:
        text = f"{heading}\n{body}".lower()
        for rule in self.slot_rules:
            for kw in rule.keywords:
                if kw.lower() in text:
                    return rule.slot
        return SpecSlot.REQUIREMENTS


# No keyword rule for OVERVIEW here on purpose: the real document's "Service
# overview" rows are the lead-in prose before a section's first bullet, not text
# that happens to contain the word "overview" — spec_building.py assigns it
# positionally (the first paragraph of a section, when nothing more specific below
# matched) rather than by keyword. HMI is kept deliberately narrow — "screen"/
# "display"/"touch" were tried first and matched almost every sentence in a car
# manual (confirmed directly against real Subaru output, 2026-08-25: 11/11 rows
# in one function all landed in Hmi), which made the category meaningless. Better
# to under-trigger into the REQUIREMENTS default than repeat that.
DEFAULT_SLOT_RULES: list[SlotRule] = [
    SlotRule(
        SpecSlot.EXCEPTION,
        # "may not" is the dominant real trigger — confirmed against 6+ real
        # Exception operation rows across Subaru functions 2/5/6/8/18/19/22,
        # 2026-08-25 ("may not be shown/available/zoomed/changed/the same as...").
        # "if the" was tried and removed the same day: it matches any ordinary
        # conditional sentence describing normal behavior ("If the current
        # position is not correct, it is automatically corrected...", "If the
        # system determines... a rest may be necessary, a pop-up message will be
        # displayed" — both plain Service requirements in the original, not
        # Exception operation), so it produced false positives on functions 5 and
        # 9 rather than catching real ones.
        keywords=[
            "may not", "error", "cannot", "unavailable", "problem",
            "trouble", "warning", "caution", "hazard", "malfunction",
        ],
    ),
    SlotRule(
        SpecSlot.USER_SETTING,
        # Bare "setting" was dropped: it matched any passing mention of a UI
        # element named "Settings" (e.g. "Select to change the navigation
        # settings.", part of an ordinary Service requirements sentence in the
        # original, confirmed 2026-08-25) and pulled it out on its own. No
        # confirmed real example of this slot exists in the Subaru sample yet, so
        # these two are a conservative narrowing, not a validated rule — revisit
        # once a real "User settings" row is found to check against.
        keywords=["customize", "preference"],
    ),
    SlotRule(
        SpecSlot.HMI,
        keywords=["steering wheel switch", "voice command", "long press", "double-tap"],
    ),
]

# Number string (appended after "{function_number}-") and the real document's
# display name for each slot, confirmed directly against real published output
# (2026-08-25): OVERVIEW/REQUIREMENTS are a numbered sub-pair under a shared "2"
# ("17-2-1. Service overview", "17-2-2. Service requirements"); HMI/USER_SETTING/
# EXCEPTION/OTHER are each their own top-level number with no "2-" prefix
# ("4-3. Requirements for HMI", "4-5. Exception operation", "4-6. Others" all seen
# in one real function). Dict order is also render order.
SLOT_DISPLAY: dict[SpecSlot, tuple[str, str]] = {
    SpecSlot.OVERVIEW: ("2-1", "Service overview"),
    SpecSlot.REQUIREMENTS: ("2-2", "Service requirements"),
    SpecSlot.HMI: ("3", "Requirements for HMI"),
    SpecSlot.USER_SETTING: ("4", "User settings"),
    SpecSlot.EXCEPTION: ("5", "Exception operation"),
    SpecSlot.OTHER: ("6", "Others"),
    SpecSlot.SAFETY: ("7", "Safety notices (WARNING / NOTICE in the OM)"),
}
