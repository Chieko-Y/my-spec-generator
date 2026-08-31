"""Regression tests for domain.spec_building._split_lines' step-continuation
handling, added 2026-08-28 after a real Subaru procedure step was found
truncated mid-sentence, with the rest of its own text surfacing as an
unrelated-looking "Service requirements" row instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Line, Section
from domain.model import SpecSlot
from domain.profile import LayoutConfig, Profile
from domain.spec_building import build_function_spec, _split_lines


def _section(lines: list[Line]) -> Section:
    return Section(
        title="Test section",
        level=0,
        page_start=0,
        page_end=1,
        lines=lines,
        matched_by_text=True,
        source_bookmark_index=0,
    )


def test_a_wrapped_step_continuation_is_merged_into_the_step():
    """Confirmed against the real 2025 Subaru supplement's Wi-Fi map-update
    procedure: step "7." wraps across three physical PDF lines ("Close the
    driver's door and lock the doors, then move at" / "least 10 feet (3 m)
    away from the vehicle to prevent the key" / "from interfering."). Before
    this fix, only the first line became the step's text and the other two
    fell into prose, ending up as a confusing, unrelated-looking "Service
    requirements" row."""
    lines = [
        Line(page=0, text="7. Close the driver's door and lock the doors, then move at", top=100.0),
        Line(page=0, text="least 10 feet (3 m) away from the vehicle to prevent the key", top=110.0),
        Line(page=0, text="from interfering.", top=120.0),
    ]

    steps, groups = _split_lines(_section(lines))

    assert steps == [
        (
            7,
            0,
            100.0,
            "Close the driver's door and lock the doors, then move at least 10 feet "
            "(3 m) away from the vehicle to prevent the key from interfering.",
        )
    ]
    assert groups == []


def test_a_bullet_line_breaks_the_continuation_instead_of_merging():
    """Confirmed against the real 2025 Subaru supplement: step 8's real
    continuation ("start the engine again.") sits 13.7pt above an unrelated
    "● The new map data will be applied." note -- a bullet-marked line always
    starts a new, distinct item and must never get glued onto the preceding
    step just because it's close by."""
    lines = [
        Line(page=0, text="8. After at least 5 minutes have elapsed, start the engine", top=100.0),
        Line(page=0, text="again.", top=110.0),
        Line(page=0, text="● The new map data will be applied.", top=113.7),
    ]

    steps, groups = _split_lines(_section(lines))

    assert steps == [(8, 0, 100.0, "After at least 5 minutes have elapsed, start the engine again.")]
    assert len(groups) == 1
    assert [l.text for l in groups[0]] == ["● The new map data will be applied."]


def test_unrelated_prose_far_from_any_step_is_left_alone():
    lines = [
        Line(page=0, text="1. Select the menu icon.", top=100.0),
        Line(page=0, text="This paragraph is unrelated body text.", top=300.0),
    ]

    steps, groups = _split_lines(_section(lines))

    assert steps == [(1, 0, 100.0, "Select the menu icon.")]
    assert len(groups) == 1
    assert [l.text for l in groups[0]] == ["This paragraph is unrelated body text."]


def test_a_continuation_never_crosses_a_page_boundary():
    lines = [
        Line(page=0, text="1. Select the menu icon.", top=100.0),
        Line(page=1, text="A caption on the next page.", top=100.0),
    ]

    steps, groups = _split_lines(_section(lines))

    assert steps == [(1, 0, 100.0, "Select the menu icon.")]
    assert len(groups) == 1
    assert [l.text for l in groups[0]] == ["A caption on the next page."]


def _profile() -> Profile:
    return Profile(profile_id="test", extends=None, derived_from="fixture", slot_rules=[], layout=LayoutConfig())


def test_requirement_between_two_steps_cites_the_step_it_leads_into():
    """Reproduces the real Subaru Outback 2026 case (Basic Operation, p.16-17,
    2026-08-31): "After a few seconds, the Caution screen will be displayed."
    sits right after step 1, physically closer to it than to step 2 (which is
    on the next page) -- but it describes what happens BEFORE step 2, so the
    useful citation is "the step the reader does next" (step 2), not the
    nearest step by raw position (step 1, already completed by this point)."""
    lines = [
        Line(page=0, text="1. When the ignition switch is turned to ACC or ON, the initial", top=634.5),
        Line(page=0, text="screen will be displayed and the system will begin operating.", top=649.0),
        Line(page=0, text="● After a few seconds, the “Caution” screen will be displayed.", top=666.0),
        Line(page=1, text="2. Touch “I Agree”.", top=170.8),
    ]

    spec = build_function_spec(_section(lines), _profile(), "manual", "Basic operation", 1)

    req = next(r for r in spec.requirements if "Caution" in r.text)
    assert req.next_step_text == "2. Touch “I Agree”."
