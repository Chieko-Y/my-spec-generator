"""Regression test for domain.parameters.detect_parameters -- added 2026-08-31
after a real gap was found in the real Subaru Outback 2026 manual: "After a
few seconds, the "Caution" screen will be displayed." (Basic Operation, p.16)
produced no threshold at all, because "a few <unit>" was not among the
re-derived vague-quantity patterns (only "a certain period of time" and a
handful of others were named in ARCHITECTURE.md/REQUIREMENTS.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.model import ParameterStatus
from domain.parameters import detect_parameters


def test_a_few_seconds_is_detected_as_an_unfilled_duration_threshold():
    text = 'After a few seconds, the "Caution" screen will be displayed.'
    found = detect_parameters(text, "p.16")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.matching_text == "a few seconds"
    assert threshold.kind == "duration"
    assert threshold.unit == "seconds"
    assert threshold.status == ParameterStatus.UNFILLED
    assert threshold.value is None


def test_a_few_minutes_also_detected_with_its_own_named_unit():
    text = "The system will shut down after a few minutes of inactivity."
    found = detect_parameters(text, "p.42")

    assert len(found) == 1
    assert found[0].matching_text == "a few minutes"
    assert found[0].unit == "minutes"


def test_a_few_seconds_seeds_a_value_when_a_real_number_sits_nearby():
    text = "Wait a few seconds (about 5 sec) for the screen to update."
    found = detect_parameters(text, "p.16")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.status == ParameterStatus.FROM_MANUAL
    assert threshold.value == "5"
    assert threshold.unit == "sec"


def test_a_certain_level_of_x_seeds_a_combined_value_from_a_parenthetical_number():
    """Reproduces the real Subaru Outback 2026 GPS-accuracy paragraph
    (Navigation, "Limitations of the navigation system", 2026-08-31): "The GPS
    system has a certain level of inaccuracy. ... errors of up to 300 feet
    (100 m) can and should be expected." The original app's own threshold for
    this text showed value="100 m" (the parenthetical metric figure, not the
    nearer "300 feet"), unit="as stated", kind="quantity" -- reproduced here."""
    text = (
        "The GPS system has a certain level of inaccuracy. While the navigation "
        "system compensates for this most of the time, occasional positioning "
        "errors of up to 300 feet (100 m) can and should be expected."
    )
    found = detect_parameters(text, "p.136")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.matching_text == "a certain level of inaccuracy"
    assert threshold.kind == "quantity"
    assert threshold.unit == "as stated"
    assert threshold.status == ParameterStatus.FROM_MANUAL
    assert threshold.value == "100 m"
    assert threshold.evidence == 'Stated in the OM: "100 m"'


def test_a_certain_degree_and_amount_of_x_also_match():
    assert detect_parameters("There is a certain degree of play in the pedal.", "p.1")
    assert detect_parameters("Expect a certain amount of delay before it responds.", "p.1")


def test_a_certain_level_of_x_with_no_nearby_number_is_left_unfilled():
    text = "There is a certain level of variation between vehicles."
    found = detect_parameters(text, "p.1")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.status == ParameterStatus.UNFILLED
    assert threshold.unit == "as stated"
    assert threshold.value is None


def test_high_speed_and_low_speed_are_detected_as_unfilled_speed_thresholds():
    text = "When a long route is searched during high speed driving."
    found = detect_parameters(text, "p.140")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.matching_text == "high speed"
    assert threshold.kind == "speed"
    assert threshold.unit == "speed"
    assert threshold.status == ParameterStatus.UNFILLED

    assert detect_parameters("Reduce to low speed before turning.", "p.1")[0].matching_text == "low speed"
