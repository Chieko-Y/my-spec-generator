"""Regression tests for domain.overlay.existing_threshold_overlay's round-trip
rule, added 2026-08-31 after the user asked for a way to revert a mistakenly
confirmed threshold back to unfilled -- with the revert itself (who, why) kept
on record, the same as any other human input to this project's overlay layer.

Before this fix, existing_threshold_overlay only re-extracted entries whose
status != UNFILLED, so a deliberate revert-to-unfilled entry (which DOES carry
evidence + filled_by, unlike a plain never-touched threshold) would be silently
dropped the next time this chapter was regenerated -- violating invariant 3
("a re-generate never wipes out what a tester already filled in").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.model import (
    FunctionSpec,
    ManualSpec,
    ParameterStatus,
    RequirementItem,
    RequirementStrength,
    SpecSlot,
    ThresholdParameter,
)
from domain.overlay import OverlayEntry, existing_threshold_overlay


def _spec_with_threshold(threshold: ThresholdParameter) -> ManualSpec:
    req = RequirementItem(
        req_id="r1",
        slot=SpecSlot.REQUIREMENTS,
        text="Something happens after a certain period of time.",
        source_text="Something happens after a certain period of time.",
        strength=RequirementStrength.CAPABILITY,
        source="p.1 / text",
        thresholds=[threshold],
    )
    fn = FunctionSpec(
        function_id="f1", chapter_number="1", title="X", area="A", function_path="A/X",
        pages=[1], requirements=[req],
    )
    return ManualSpec(
        manual_id="m", maker="Test", model="X", document_title="Test", scope="",
        markets=[], profile_id="p", functions=[fn],
    )


def test_a_never_touched_unfilled_threshold_is_not_round_tripped():
    threshold = ThresholdParameter(
        threshold_id="t1", matching_text="a certain period of time", kind="duration", unit="time",
        context="ctx",
    )
    assert existing_threshold_overlay(_spec_with_threshold(threshold)) == []


def test_a_normal_filled_threshold_is_round_tripped():
    threshold = ThresholdParameter(
        threshold_id="t1", matching_text="a certain period of time", kind="duration", unit="time",
        context="ctx", value="3", status=ParameterStatus.FROM_MANUAL,
        evidence="Stated in the OM: \"3\"", filled_by="tester A",
    )
    out = existing_threshold_overlay(_spec_with_threshold(threshold))
    assert len(out) == 1
    assert out[0].threshold_id == "t1"
    assert out[0].status == ParameterStatus.FROM_MANUAL


def test_a_deliberate_revert_to_unfilled_is_still_round_tripped():
    """The real fix: status=UNFILLED with evidence+filled_by present (a tester
    explicitly reverting a mistaken confirmation) must survive a re-generate,
    not vanish just because its status happens to be UNFILLED again."""
    threshold = ThresholdParameter(
        threshold_id="t1", matching_text="a certain period of time", kind="duration", unit="time",
        context="ctx", value="", status=ParameterStatus.UNFILLED,
        evidence="Confirmed by mistake, reverting.", filled_by="tester B",
    )
    out = existing_threshold_overlay(_spec_with_threshold(threshold))
    assert len(out) == 1
    assert out[0].threshold_id == "t1"
    assert out[0].status == ParameterStatus.UNFILLED
    assert out[0].evidence == "Confirmed by mistake, reverting."
    assert out[0].filled_by == "tester B"


def test_overlay_entry_allows_a_blank_value_when_reverting_to_unfilled():
    """Real bug hit via the actual web form, 2026-08-31: FastAPI's Form(...)
    treats a submitted-but-empty text field as MISSING, not "", returning a 422
    before this code even runs -- fixed separately in web.py (Form("") default).
    This test covers the domain-level half: OverlayEntry itself must accept an
    empty value for a revert."""
    entry = OverlayEntry(
        threshold_id="t1", value="", status=ParameterStatus.UNFILLED,
        evidence="Confirmed by mistake, reverting.", filled_by="tester B",
    )
    assert entry.value == ""


def test_overlay_entry_rejects_a_blank_value_for_any_non_revert_status():
    """A blank value is only legitimate when explicitly reverting to unfilled --
    any other status claims to be a real confirmed/derived number and must
    actually carry one."""
    for status in ParameterStatus:
        if status == ParameterStatus.UNFILLED:
            continue
        try:
            OverlayEntry(threshold_id="t1", value="", status=status, evidence="e", filled_by="f")
            assert False, f"expected ValueError for status={status}"
        except ValueError:
            pass
