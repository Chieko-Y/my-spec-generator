"""Human input types and the merge that applies them onto a generated ManualSpec.

Merge is "add or fill only" — it never rewrites requirement text, slot, or source.
Anything that can't be applied (its target id vanished after a re-generate) is
reported as orphaned rather than silently dropped. See ARCHITECTURE.md invariant 3.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .model import ManualSpec, ParameterStatus, TermCategory


@dataclass
class OverlayEntry:
    threshold_id: str
    value: str
    status: ParameterStatus
    evidence: str
    filled_by: str

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("OverlayEntry requires evidence — a threshold cannot be confirmed without it")
        if not self.filled_by:
            raise ValueError("OverlayEntry requires filled_by")


@dataclass
class FigureElement:
    figure_id: str
    symbol: str
    label: str
    note: str
    decided_by: str

    def __post_init__(self) -> None:
        if not self.decided_by:
            raise ValueError("FigureElement requires decided_by — only the person who saw the figure can say what it means")


@dataclass
class GlossaryTerm:
    term_id: str
    in_house_term: str
    category: TermCategory
    manual_wordings: list[str]
    evidence: str

    def __post_init__(self) -> None:
        if not self.manual_wordings:
            raise ValueError("GlossaryTerm requires at least one manual wording (alias)")
        if not self.evidence:
            raise ValueError("GlossaryTerm requires evidence")


@dataclass
class MergeReport:
    applied: int = 0
    orphaned: list[str] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (id, reason)


def apply_thresholds(spec: ManualSpec, entries: list[OverlayEntry]) -> MergeReport:
    report = MergeReport()
    index = {t.threshold_id: t for f in spec.functions for r in f.requirements for t in r.thresholds}

    for entry in entries:
        target = index.get(entry.threshold_id)
        if target is None:
            report.orphaned.append(entry.threshold_id)
            continue
        target.value = entry.value
        target.status = entry.status
        target.evidence = entry.evidence
        target.filled_by = entry.filled_by
        report.applied += 1
    return report


def existing_threshold_overlay(spec: ManualSpec) -> list[OverlayEntry]:
    """Extract the currently-filled thresholds back out as overlay entries, so a
    re-`generate` can read-then-write without losing them (invariant 3)."""
    out: list[OverlayEntry] = []
    for function in spec.functions:
        for requirement in function.requirements:
            for threshold in requirement.thresholds:
                if threshold.status != ParameterStatus.UNFILLED and threshold.evidence and threshold.filled_by:
                    out.append(
                        OverlayEntry(
                            threshold_id=threshold.threshold_id,
                            value=threshold.value or "",
                            status=threshold.status,
                            evidence=threshold.evidence,
                            filled_by=threshold.filled_by,
                        )
                    )
    return out
