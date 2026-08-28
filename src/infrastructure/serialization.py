"""dataclass <-> dict conversion for the generated/spec.json format. Kept out of
domain (domain must stay free of any format-specific concern, even JSON).
"""
from __future__ import annotations

from domain.model import (
    FigureRef,
    FunctionSpec,
    ManualSpec,
    ParameterStatus,
    ProcedureStep,
    RequirementItem,
    RequirementStrength,
    RevisionChange,
    SpecSlot,
    ThresholdParameter,
)


def threshold_to_dict(t: ThresholdParameter) -> dict:
    return {
        "threshold_id": t.threshold_id,
        "matching_text": t.matching_text,
        "kind": t.kind,
        "unit": t.unit,
        "context": t.context,
        "value": t.value,
        "status": t.status.value,
        "evidence": t.evidence,
        "filled_by": t.filled_by,
    }


def threshold_from_dict(d: dict) -> ThresholdParameter:
    return ThresholdParameter(
        threshold_id=d["threshold_id"],
        matching_text=d["matching_text"],
        kind=d["kind"],
        unit=d.get("unit"),
        context=d.get("context", ""),
        value=d.get("value"),
        status=ParameterStatus(d.get("status", "unfilled")),
        evidence=d.get("evidence"),
        filled_by=d.get("filled_by"),
    )


def requirement_to_dict(r: RequirementItem) -> dict:
    return {
        "req_id": r.req_id,
        "slot": r.slot.value,
        "text": r.text,
        "source_text": r.source_text,
        "strength": r.strength.value,
        "source": r.source,
        "thresholds": [threshold_to_dict(t) for t in r.thresholds],
        "change": r.change.value if r.change else None,
        "previous_text": r.previous_text,
    }


def requirement_from_dict(d: dict) -> RequirementItem:
    return RequirementItem(
        req_id=d["req_id"],
        slot=SpecSlot(d["slot"]),
        text=d["text"],
        source_text=d["source_text"],
        strength=RequirementStrength(d["strength"]),
        source=d["source"],
        thresholds=[threshold_from_dict(t) for t in d.get("thresholds", [])],
        change=RevisionChange(d["change"]) if d.get("change") else None,
        previous_text=d.get("previous_text"),
    )


def figure_to_dict(f: FigureRef) -> dict:
    return {
        "figure_id": f.figure_id,
        "page": f.page,
        "rect": list(f.rect),
        "caption_source": f.caption_source,
        "caption_text": f.caption_text,
        "image_path": f.image_path,
        "legend_requirements": [requirement_to_dict(r) for r in f.legend_requirements],
    }


def figure_from_dict(d: dict) -> FigureRef:
    return FigureRef(
        figure_id=d["figure_id"],
        page=d["page"],
        rect=tuple(d["rect"]),
        caption_source=d.get("caption_source", ""),
        caption_text=d.get("caption_text"),
        image_path=d.get("image_path"),
        legend_requirements=[requirement_from_dict(r) for r in d.get("legend_requirements", [])],
    )


def function_to_dict(f: FunctionSpec) -> dict:
    return {
        "function_id": f.function_id,
        "chapter_number": f.chapter_number,
        "title": f.title,
        "area": f.area,
        "function_path": f.function_path,
        "pages": f.pages,
        "procedure": [
            {"number": s.number, "text": s.text, "sequence": s.sequence, "source": s.source}
            for s in f.procedure
        ],
        "requirements": [requirement_to_dict(r) for r in f.requirements],
        "figures": [figure_to_dict(fig) for fig in f.figures],
    }


def function_from_dict(d: dict) -> FunctionSpec:
    return FunctionSpec(
        function_id=d["function_id"],
        chapter_number=d["chapter_number"],
        title=d["title"],
        area=d["area"],
        function_path=d["function_path"],
        pages=d.get("pages", []),
        procedure=[
            ProcedureStep(number=s["number"], text=s["text"], sequence=s["sequence"], source=s["source"])
            for s in d.get("procedure", [])
        ],
        requirements=[requirement_from_dict(r) for r in d.get("requirements", [])],
        figures=[figure_from_dict(fig) for fig in d.get("figures", [])],
    )


def spec_to_dict(spec: ManualSpec) -> dict:
    return {
        "manual_id": spec.manual_id,
        "maker": spec.maker,
        "model": spec.model,
        "document_title": spec.document_title,
        "scope": spec.scope,
        "markets": spec.markets,
        "profile_id": spec.profile_id,
        "meta": spec.meta,
        "functions": [function_to_dict(f) for f in spec.functions],
    }


def spec_from_dict(d: dict) -> ManualSpec:
    return ManualSpec(
        manual_id=d["manual_id"],
        maker=d["maker"],
        model=d["model"],
        document_title=d.get("document_title", ""),
        scope=d.get("scope", ""),
        markets=d.get("markets", []),
        profile_id=d.get("profile_id", ""),
        meta=d.get("meta", {}),
        functions=[function_from_dict(f) for f in d.get("functions", [])],
    )
