"""Detect quantities a manual leaves vague, and turn each into an unfilled threshold.

Reconstructed from the phrase examples named in ARCHITECTURE.md / REQUIREMENTS.md
("a certain period of time", "too short or too long", "the upper limit", "nearby") —
the original config/parameter_patterns.json was not handed over, so this list is a
best-effort re-derivation, not a byte-for-byte copy. Extend it as real manuals turn up
phrasings these patterns miss.

Policy carried over unchanged: a missed vague phrase is worse than a false positive.
A false positive gets closed by a tester as "not applicable"; a miss never surfaces at
all. When in doubt, add the pattern.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import ParameterStatus, ThresholdParameter, content_id


@dataclass
class ParameterPattern:
    pattern_id: str
    kind: str
    regex: re.Pattern
    unit_hint: str | None = None
    # "quantity"-kind phrases (e.g. "a certain level of inaccuracy") have no
    # fixed physical dimension of their own -- unlike duration/speed/distance,
    # there's no single natural unit to report. When a nearby number+unit IS
    # found, keep the whole matched span ("100 m") as one value and report the
    # unit as the literal "as stated" rather than the parsed unit group, since
    # "as stated" here means "whatever the manual itself wrote", not a
    # category this pattern already knows to expect.
    combined_value_unit: bool = False


_UNIT_ALTERNATION = (
    r"seconds?|sec\.?|minutes?|min\.?|hours?|hrs?|"
    r"miles?|mi\.?|km|kilometers?|feet|ft\.?|meters?|m\b|%|percent"
)

NUMBER_WITH_UNIT = re.compile(
    rf"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{_UNIT_ALTERNATION})",
    re.IGNORECASE,
)

# A number+unit that sits in parentheses, e.g. "300 feet (100 m)" -- the
# manual's own converted/precise equivalent, printed right next to the
# primary figure. Confirmed against the real Subaru Outback 2026 PDF,
# 2026-08-31: "The GPS system has a certain level of inaccuracy. ... errors of
# up to 300 feet (100 m) can and should be expected." -- the parenthetical
# "100 m" is the value worth surfacing, not "300 feet" (which sits closer to
# the vague phrase and would otherwise win a plain nearest-match search) and
# not reachable at all within the normal +/-60-char window this module
# otherwise uses (117 chars away in this real sentence). Used only as a
# fallback for "quantity"-kind patterns, scoped narrowly to avoid changing
# already-working behavior for duration/speed/etc. patterns.
_PAREN_NUMBER_WITH_UNIT = re.compile(
    rf"\(\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{_UNIT_ALTERNATION})\s*\)",
    re.IGNORECASE,
)

PATTERNS: list[ParameterPattern] = [
    ParameterPattern(
        "vague_duration",
        "duration",
        re.compile(
            r"\b(?:a\s+certain\s+(?:period\s+of\s+)?time|for\s+a\s+while|"
            r"after\s+a\s+(?:short|brief)\s+(?:time|period)|"
            r"(?:shortly|briefly)\s+(?:after|before))\b",
            re.IGNORECASE,
        ),
        "time",
    ),
    ParameterPattern(
        "vague_extreme",
        "range",
        re.compile(r"\btoo\s+(?:short|long|far|close|high|low|fast|slow)\b", re.IGNORECASE),
        None,
    ),
    ParameterPattern(
        "vague_limit",
        "limit",
        re.compile(r"\bthe\s+(?:upper|lower|maximum|minimum)\s+limit\b", re.IGNORECASE),
        None,
    ),
    ParameterPattern(
        "vague_distance",
        "distance",
        re.compile(r"\b(?:nearby|in\s+the\s+vicinity|a\s+short\s+distance)\b", re.IGNORECASE),
        "distance",
    ),
    ParameterPattern(
        "vague_frequency",
        "frequency",
        re.compile(r"\b(?:periodically|from\s+time\s+to\s+time|occasionally)\b", re.IGNORECASE),
        None,
    ),
    ParameterPattern(
        "vague_few_duration",
        "duration",
        re.compile(
            r"\ba\s+few\s+(?P<unit>seconds?|sec\.?|minutes?|min\.?|hours?|hrs?)\b",
            re.IGNORECASE,
        ),
        "time",
    ),
    ParameterPattern(
        "vague_certain_quantity",
        "quantity",
        re.compile(
            r"\ba\s+certain\s+(?:level|degree|amount)\s+of\s+[A-Za-z]+\b",
            re.IGNORECASE,
        ),
        "as stated",
        combined_value_unit=True,
    ),
    ParameterPattern(
        "vague_speed",
        "speed",
        re.compile(r"\b(?:high|low)\s+speed\b", re.IGNORECASE),
        "speed",
    ),
    ParameterPattern(
        "vague_repeatedly",
        "count",
        # Confirmed real, Honda Pilot 2026-09-03: "Repeatedly select the shuffle
        # or repeat icon until you find a play mode..." and "Select random or
        # repeat icon repeatedly until a desired mode." -- both name a repeated
        # action with no stated count, bounded only by "until <some state>".
        # Matches either word order (the "repeatedly" can land before or after
        # the verb it modifies), scoped to one sentence (`[^.]` gap) so an
        # unrelated "until" much later in the same paragraph doesn't pair up.
        re.compile(r"\brepeatedly\b[^.]{0,80}\buntil\b|\buntil\b[^.]{0,80}\brepeatedly\b", re.IGNORECASE),
        "times",
    ),
    ParameterPattern(
        "vague_certain_count",
        "count",
        # Confirmed real, Honda Pilot 2026-09-03: "Remind me Later will stop
        # displaying after it has been selected a certain number of times." --
        # same shape as vague_certain_quantity ("a certain level/degree/amount
        # of X") but for a bare repeat count, which that pattern's noun-phrase
        # shape doesn't cover.
        re.compile(r"\ba\s+certain\s+number\s+of\s+times\b", re.IGNORECASE),
        "times",
    ),
    ParameterPattern(
        "vague_stated_duration",
        "duration",
        # NOT a vague phrase -- the manual DOES state a number ("for 10
        # seconds", "30 seconds have elapsed") -- but the original app's own
        # real output still flags these as thresholds (status=from_manual,
        # "Stated in the OM"), confirmed real, Honda Pilot 2026-09-03 (a scan
        # duration and an auto-off timeout). A documented timing spec is worth
        # verifying against the real vehicle even when the manual already
        # states a value -- unlike the other patterns here, the match IS the
        # number+unit itself, so `detect_parameters`'s own nearby-number
        # search always finds it and seeds `status=from_manual` automatically.
        re.compile(
            r"\bfor\s+\d+\s+(?:seconds?|sec\.?|minutes?|min\.?|hours?|hrs?)\b|"
            r"\b\d+\s+(?:seconds?|sec\.?|minutes?|min\.?|hours?|hrs?)\s+(?:have\s+)?elapsed\b",
            re.IGNORECASE,
        ),
        "time",
    ),
    # A bare "immediately" pattern was tried and deliberately dropped,
    # 2026-09-03: the original app's own real output has ONE genuine hit for
    # it ("the system update begins immediately", Honda Pilot System
    # Updates -- this rebuild's own text extraction currently drops that
    # exact sentence, a separate still-open bug), but a real regenerate
    # against Subaru's own manuals showed this word overwhelmingly appears
    # in generic safety-precaution boilerplate instead ("stop using the unit
    # immediately", "wipe off immediately") -- not a testable system
    # response time at all. Unlike this file's other patterns, that noise
    # isn't a handful of one-off false positives a reviewer occasionally
    # dismisses; it's the DOMINANT real-world match for the bare word, so it
    # was left out rather than accepted per the usual "when in doubt, add
    # it" policy. Revisit only with a narrower trigger (e.g. requiring
    # "begins/starts immediately", closer to the one real confirmed case)
    # if a future manual makes this worth another look.
]


def detect_parameters(text: str, source: str) -> list[ThresholdParameter]:
    """Scan one requirement's text for vague-quantity phrases and produce a threshold
    per match. A phrase that also names a concrete number+unit nearby seeds the value
    as status=from_manual instead of leaving it unfilled."""
    found: list[ThresholdParameter] = []
    for pattern in PATTERNS:
        for match in pattern.regex.finditer(text):
            matching_text = match.group(0)
            # A narrow window, used ONLY to decide whether a nearby number should
            # seed a value -- kept small so an unrelated number elsewhere in a
            # long paragraph doesn't get picked up. The reviewer-facing citation
            # is the full requirement text instead (see `context` below): a
            # fixed-width slice can start or end mid-word/mid-sentence, which a
            # real user flagged as confusing when reviewing a real threshold
            # (2026-08-31, Navigation chapter: a snippet started "pected." --
            # the tail of "expected." cut off by the window boundary).
            window_start = max(0, match.start() - 60)
            window_end = min(len(text), match.end() + 60)
            search_window = text[window_start:window_end].strip()
            context = text.strip()

            number_match = NUMBER_WITH_UNIT.search(search_window)
            if number_match is None and pattern.combined_value_unit:
                number_match = _PAREN_NUMBER_WITH_UNIT.search(text)
            threshold_id = content_id("threshold", source, matching_text, str(match.start()))

            if number_match:
                if pattern.combined_value_unit:
                    value = f"{number_match.group('value')} {number_match.group('unit')}"
                    unit = pattern.unit_hint
                else:
                    value = number_match.group("value")
                    unit = number_match.group("unit")
                found.append(
                    ThresholdParameter(
                        threshold_id=threshold_id,
                        matching_text=matching_text,
                        kind=pattern.kind,
                        unit=unit,
                        context=context,
                        value=value,
                        status=ParameterStatus.FROM_MANUAL,
                        evidence=f'Stated in the OM: "{value}"',
                    )
                )
            else:
                named_unit = match.groupdict().get("unit")
                found.append(
                    ThresholdParameter(
                        threshold_id=threshold_id,
                        matching_text=matching_text,
                        kind=pattern.kind,
                        unit=named_unit or pattern.unit_hint,
                        context=context,
                    )
                )
    return found
