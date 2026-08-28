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


NUMBER_WITH_UNIT = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>seconds?|sec\.?|minutes?|min\.?|hours?|hrs?|"
    r"miles?|mi\.?|km|kilometers?|feet|ft\.?|meters?|m\b|%|percent)",
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
]


def detect_parameters(text: str, source: str) -> list[ThresholdParameter]:
    """Scan one requirement's text for vague-quantity phrases and produce a threshold
    per match. A phrase that also names a concrete number+unit nearby seeds the value
    as status=from_manual instead of leaving it unfilled."""
    found: list[ThresholdParameter] = []
    for pattern in PATTERNS:
        for match in pattern.regex.finditer(text):
            matching_text = match.group(0)
            window_start = max(0, match.start() - 60)
            window_end = min(len(text), match.end() + 60)
            context = text[window_start:window_end].strip()

            number_match = NUMBER_WITH_UNIT.search(context)
            threshold_id = content_id("threshold", source, matching_text, str(match.start()))

            if number_match:
                found.append(
                    ThresholdParameter(
                        threshold_id=threshold_id,
                        matching_text=matching_text,
                        kind=pattern.kind,
                        unit=number_match.group("unit"),
                        context=context,
                        value=number_match.group("value"),
                        status=ParameterStatus.FROM_MANUAL,
                        evidence=context,
                    )
                )
            else:
                found.append(
                    ThresholdParameter(
                        threshold_id=threshold_id,
                        matching_text=matching_text,
                        kind=pattern.kind,
                        unit=pattern.unit_hint,
                        context=context,
                    )
                )
    return found
