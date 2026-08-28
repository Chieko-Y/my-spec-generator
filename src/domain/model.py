"""Pure domain model. No PDF / HTTP / file-format knowledge here (stdlib only)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


def content_id(*parts: str, length: int = 12) -> str:
    """Identity derived from content, never from position (chapter number / page / extraction order).

    Mixing position into the id means a manual revision reshuffles ids and every
    tester-entered overlay value becomes orphaned. See ARCHITECTURE.md invariant 5.
    """
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return digest[:length]


class SpecSlot(str, Enum):
    """The 7-category taxonomy carried over from the real TMC nav requirements
    document (see docs/CONCEPT.md section 5: this shape, unlike layout, was
    validated across 4 manufacturers in the app this was rebuilt from — it is the
    shared baseline, not a Toyota-only quirk). Confirmed directly against real
    published output, 2026-08-25: OVERVIEW/REQUIREMENTS share one numbered pair
    ("2-1"/"2-2") while the other five are each their own top-level number
    (3/4/5/6/7) — display name and the exact number string for each live in
    profile.SLOT_DISPLAY, not here (that's presentation, this is just identity).

    Three of these are keyed to a PDF structural element this app doesn't extract
    yet, not to keywords in flowing text, confirmed against real Toyota rows the
    same day: HMI comes from figure-callout labels ("p.15 / figure_callout" — a
    diagram's numbered/lettered part descriptions), USER_SETTING from a structured
    setting-name/definition list ("p.175 / itemdef"), and SAFETY from a boxed
    WARNING/NOTICE call-out in the PDF. build_function_spec can only approximate
    HMI/USER_SETTING with narrow keyword rules today (deliberately conservative —
    see profile.DEFAULT_SLOT_RULES) and never populates SAFETY at all; real
    fidelity for all three needs the same kind of structural extraction as figures
    (deferred, see the figures-phase note in domain/figures.py)."""

    OVERVIEW = "overview"
    REQUIREMENTS = "requirements"
    HMI = "hmi"
    USER_SETTING = "user_setting"
    EXCEPTION = "exception"
    OTHER = "other"
    SAFETY = "safety"


class RequirementStrength(str, Enum):
    """Only 3 values. MUST/SHALL is deliberately absent — a manual never states an
    obligation, only "do X and Y happens". Adding MUST here would let the generator
    assert something the source text never claimed. See CONCEPT.md section 4."""

    CAPABILITY = "capability"
    DEFINE = "define"
    CONSTRAINT = "constraint"


class ParameterStatus(str, Enum):
    UNFILLED = "unfilled"
    FROM_MANUAL = "from_manual"
    FROM_SPEC = "from_spec"
    MEASURED = "measured"
    ASSUMED = "assumed"


class TermCategory(str, Enum):
    OPERATION = "operation"
    SCREEN_ELEMENT = "screen_element"
    FUNCTION = "function"
    STATE = "state"
    ABBREVIATION = "abbreviation"


class RevisionChange(str, Enum):
    ADDED = "ADDED"
    CHANGED = "CHANGED"
    REMOVED = "REMOVED"


@dataclass
class ProcedureStep:
    number: int
    text: str
    sequence: int
    source: str


@dataclass
class ThresholdParameter:
    threshold_id: str
    matching_text: str
    kind: str
    unit: str | None
    context: str
    value: str | None = None
    status: ParameterStatus = ParameterStatus.UNFILLED
    evidence: str | None = None
    filled_by: str | None = None

    def __post_init__(self) -> None:
        # Invariant 2 (ARCHITECTURE.md): a value can never be confirmed without evidence.
        # This has to live in the constructor, not a setter method, so both the
        # generation path and the overlay-apply path are forced through the same gate.
        has_value = self.status != ParameterStatus.UNFILLED
        if has_value and not self.evidence:
            raise ValueError(
                f"ThresholdParameter {self.threshold_id!r} has status={self.status} "
                "but no evidence — a value cannot be confirmed without grounds."
            )


@dataclass
class RequirementItem:
    req_id: str
    slot: SpecSlot
    text: str
    source_text: str
    strength: RequirementStrength
    source: str
    thresholds: list[ThresholdParameter] = field(default_factory=list)
    change: RevisionChange | None = None
    previous_text: str | None = None


@dataclass
class FigureRef:
    figure_id: str
    page: int
    rect: tuple[float, float, float, float]
    caption_source: str
    caption_text: str | None
    image_path: str | None = None
    legend_requirements: list[RequirementItem] = field(default_factory=list)


@dataclass
class FunctionSpec:
    function_id: str
    chapter_number: str
    title: str
    area: str
    function_path: str
    pages: list[int]
    procedure: list[ProcedureStep] = field(default_factory=list)
    requirements: list[RequirementItem] = field(default_factory=list)
    figures: list[FigureRef] = field(default_factory=list)

    @property
    def all_thresholds(self) -> list[ThresholdParameter]:
        return [t for r in self.requirements for t in r.thresholds]

    @property
    def is_test_ready(self) -> bool:
        # Invariant 4: "roughly written" is not enough. A procedure must exist and
        # every threshold in this function must be filled.
        if not self.procedure:
            return False
        return all(t.status != ParameterStatus.UNFILLED for t in self.all_thresholds)


@dataclass
class ManualSpec:
    manual_id: str
    maker: str
    model: str
    document_title: str
    scope: str
    markets: list[str]
    profile_id: str
    meta: dict = field(default_factory=dict)
    functions: list[FunctionSpec] = field(default_factory=list)

    @property
    def display_title(self) -> str:
        """The title shown in generated output.

        Must never fall back to the raw manual_id slug (e.g. "subaru/outback-2026/multimedia")
        — that is a known display bug in the app this was rebuilt from: when the
        document title metadata was empty, every downstream view silently printed the
        path slug instead. See docs bug report #2. The fallback here is the
        human-confirmed maker/model instead, which is always populated (registration
        requires it) even when the document's own printed title could not be read.

        When the generation scope is a subset of the document's chapters (see bug #3:
        the original app cloned the document's registration title even when only one
        chapter/section had been generated), the chosen chapter scope is appended so
        the reader can tell "Multimedia" the book from "Multimedia — Navigation" the
        generated slice.
        """
        base = self.document_title.strip() if self.document_title else ""
        if not base:
            base = f"{self.maker} {self.model}".strip()
        chapter_label = (self.meta or {}).get("chapter_label")
        if chapter_label:
            return f"{base} — {chapter_label}"
        return base

    def counts(self) -> dict:
        functions = self.functions
        requirements = sum(len(f.requirements) for f in functions)
        thresholds = [t for f in functions for t in f.all_thresholds]
        unfilled = [t for t in thresholds if t.status == ParameterStatus.UNFILLED]
        figures = sum(len(f.figures) for f in functions)
        test_ready = sum(1 for f in functions if f.is_test_ready)
        return {
            "functions": len(functions),
            "requirements": requirements,
            "thresholds": len(thresholds),
            "thresholds_unfilled": len(unfilled),
            "thresholds_filled": len(thresholds) - len(unfilled),
            "figures": figures,
            "test_ready": test_ready,
        }
