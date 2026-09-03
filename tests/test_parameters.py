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


def test_repeatedly_until_is_detected_as_an_unfilled_count_threshold():
    """Real Honda Pilot case, 2026-09-03: comparing this rebuild's threshold
    count against the original app's own real output (7 for the Features
    chapter, this rebuild only had 1) surfaced this and 2 more missing vague
    patterns below. "Repeatedly select ... until you find ..." names a
    repeated action with no stated count, bounded only by reaching some
    state -- the original flags this as an unfilled "count" threshold."""
    text = "Repeatedly select the shuffle or repeat icon until you find a play mode option of your preference."
    found = detect_parameters(text, "p.293")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.kind == "count"
    assert threshold.unit == "times"
    assert threshold.status == ParameterStatus.UNFILLED


def test_repeatedly_can_come_after_the_verb_it_modifies():
    """Same phrase, opposite word order -- confirmed real, Honda Pilot's own
    Music Playback via USB Flash Drive function."""
    text = "Select random or repeat icon repeatedly until a desired mode."
    found = detect_parameters(text, "p.297")

    assert len(found) == 1
    assert found[0].kind == "count"


def test_a_certain_number_of_times_is_detected_as_an_unfilled_count_threshold():
    """Real Honda Pilot case, 2026-09-03: same shape as "a certain level of
    X" but for a bare repeat count, which that pattern's noun-phrase shape
    doesn't cover."""
    text = "Remind me Later will stop displaying after it has been selected a certain number of times."
    found = detect_parameters(text, "p.282")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.matching_text == "a certain number of times"
    assert threshold.kind == "count"
    assert threshold.status == ParameterStatus.UNFILLED


def test_a_stated_scan_duration_is_still_flagged_as_a_threshold_to_verify():
    """Real Honda Pilot case, 2026-09-03: unlike every other pattern here,
    the manual DOES state a number ("for 10 seconds") -- but the original
    app's own real output still flags this as a threshold worth verifying
    against the real vehicle (status=from_manual), not something to leave
    alone just because a number is already written down."""
    text = "Samples each of the strongest stations on the selected band for 10 seconds. To turn off scan, select Stop or Back."
    found = detect_parameters(text, "p.290")

    assert len(found) == 1
    threshold = found[0]
    assert threshold.kind == "duration"
    assert threshold.status == ParameterStatus.FROM_MANUAL
    assert threshold.value == "10"
    assert threshold.unit == "seconds"
    assert threshold.evidence == 'Stated in the OM: "10"'


def test_an_elapsed_duration_without_the_word_after_is_also_flagged():
    """Real Honda Pilot case, 2026-09-03: "When 30 seconds have elapsed" --
    same shape as the scan-duration case above, but without "after"."""
    text = "The lights will stop flashing under the following: When 30 seconds have elapsed."
    found = detect_parameters(text, "p.300")

    assert len(found) == 1
    assert found[0].status == ParameterStatus.FROM_MANUAL
    assert found[0].value == "30"


def test_immediately_in_safety_boilerplate_is_deliberately_not_a_threshold():
    """A bare "immediately" pattern was tried and dropped, 2026-09-03: the
    original app has one genuine hit for it (a system response time), but a
    real regenerate against Subaru's own manuals showed the word
    overwhelmingly appears in generic safety-precaution instructions instead
    ("stop using the unit immediately", "wipe off immediately") -- not a
    testable system behavior. Locking this in so nobody re-adds a bare
    \\bimmediately\\b pattern without re-deriving why it was left out."""
    text = "If such an abnormality occurs, stop using the unit immediately and contact your dealer."
    assert detect_parameters(text, "p.1") == []


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
