"""Machine check of the domain invariants. No PDF, no network — everything here is a
pure function, so this check catches real regressions cheaply. Run:
    python tests/check_domain.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Bookmark, Line, build_blocks
from domain.model import (
    FunctionSpec,
    ManualSpec,
    ParameterStatus,
    RequirementStrength,
    ThresholdParameter,
)
from domain.overlay import OverlayEntry
from domain.spec_building import build_function_spec
from domain.profile import DEFAULT_SLOT_RULES, LayoutConfig, Profile

_FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "ok" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


def test_no_must_shall_in_type() -> None:
    values = {s.value for s in RequirementStrength}
    check(
        "1. RequirementStrength has no MUST/SHALL",
        values == {"capability", "define", "constraint"},
        str(values),
    )


def test_threshold_requires_evidence() -> None:
    raised = False
    try:
        ThresholdParameter(
            threshold_id="t1",
            matching_text="a certain period of time",
            kind="duration",
            unit=None,
            context="ctx",
            value="5",
            status=ParameterStatus.MEASURED,
            evidence=None,
        )
    except ValueError:
        raised = True
    check("2. ThresholdParameter rejects a confirmed value with no evidence", raised)

    raised = False
    try:
        OverlayEntry(threshold_id="t1", value="5", status=ParameterStatus.MEASURED, evidence="", filled_by="tester")
    except ValueError:
        raised = True
    check("2b. OverlayEntry rejects empty evidence", raised)


def test_generate_reads_overlay_before_writing() -> None:
    # This is enforced structurally in application.use_cases.UseCases._generate_locked
    # (load_thresholds is called before spec_repository.save) — checked by reading
    # the source order rather than re-implementing IO here. generate() itself is now
    # just a per-manual_id lock wrapper around _generate_locked (added after a real
    # concurrency bug: no guard against two generate() calls for the same manual_id
    # running at once, which piled up competing PDF reads and looked like a hang).
    import inspect

    from application.use_cases import UseCases

    src = inspect.getsource(UseCases._generate_locked)
    read_pos = src.find("overlay_repository.load_thresholds")
    save_pos = src.find("spec_repository.save")
    check(
        "3. generate() reads existing overlay before saving the new spec",
        -1 < read_pos < save_pos,
    )


def test_is_test_ready_requires_procedure_and_filled_thresholds() -> None:
    from domain.model import ProcedureStep, RequirementItem, SpecSlot

    threshold = ThresholdParameter(
        threshold_id="t1", matching_text="nearby", kind="distance", unit=None, context="ctx"
    )
    req = RequirementItem(
        req_id="r1",
        slot=SpecSlot.REQUIREMENTS,
        text="Something happens nearby.",
        source_text="Something happens nearby.",
        strength=RequirementStrength.CAPABILITY,
        source="p.1 / text",
        thresholds=[threshold],
    )
    fn_no_procedure = FunctionSpec(
        function_id="f1", chapter_number="1", title="X", area="A", function_path="A/X", pages=[1],
        procedure=[], requirements=[req],
    )
    check("4a. no procedure -> not test-ready", fn_no_procedure.is_test_ready is False)

    fn_with_procedure_unfilled = FunctionSpec(
        function_id="f2", chapter_number="1", title="X", area="A", function_path="A/X", pages=[1],
        procedure=[ProcedureStep(number=1, text="Do X.", sequence=1, source="p.1 / step")],
        requirements=[req],
    )
    check(
        "4b. procedure present but threshold unfilled -> not test-ready",
        fn_with_procedure_unfilled.is_test_ready is False,
    )

    threshold.value = "5"
    threshold.status = ParameterStatus.MEASURED
    threshold.evidence = "measured on bench"
    threshold.filled_by = "tester1"
    check("4c. procedure present and all thresholds filled -> test-ready", fn_with_procedure_unfilled.is_test_ready is True)


def test_content_id_ignores_position() -> None:
    from domain.model import content_id

    a = content_id("function", "toyota/rav4-2026/multimedia", "Area", "Map screen overview")
    b = content_id("function", "toyota/rav4-2026/multimedia", "Area", "Map screen overview")
    c = content_id("function", "toyota/rav4-2026/multimedia", "Area", "Different title")
    check("5. content_id is deterministic and content-based", a == b and a != c)


def test_title_never_falls_back_to_raw_slug() -> None:
    # Regression test for bug #2 (subaru/outback-2026 displaying as a raw manual_id
    # slug because the document title metadata was empty).
    spec = ManualSpec(
        manual_id="subaru/outback-2026/multimedia",
        maker="Subaru",
        model="Outback 2026",
        document_title="",  # simulate manual registration where the PDF's own title wasn't captured
        scope="",
        markets=[],
        profile_id="generic_v1",
    )
    check(
        "bug2. display_title never equals the raw manual_id slug",
        spec.display_title != spec.manual_id and spec.display_title == "Subaru Outback 2026",
        spec.display_title,
    )


def test_title_reflects_generated_chapter_scope() -> None:
    # Regression test for bug #3 (registering "Multimedia" and generating only the
    # Navigation chapter produced output titled "Multimedia").
    spec = ManualSpec(
        manual_id="toyota/rav4-2026/multimedia",
        maker="Toyota",
        model="RAV4 2026",
        document_title="Multimedia Owner's Manual",
        scope="Navigation",
        markets=[],
        profile_id="tmc_navi_v1",
        meta={"chapter_label": "Navigation"},
    )
    check(
        "bug3. display_title includes the generated chapter scope, not just the document title",
        spec.display_title == "Multimedia Owner's Manual — Navigation",
        spec.display_title,
    )


def test_unmatched_headings_are_reported_not_dropped() -> None:
    # Regression guard for HANDOVER.md section A: a bookmark heading that can't be
    # text-matched to the body must still produce a section (page-level fallback)
    # and must be listed, never silently vanish.
    lines = [
        Line(page=0, text="Some unrelated body text.", top=100.0),
        Line(page=1, text="More body text on the next page.", top=50.0),
    ]
    bookmarks = [
        Bookmark(title="Chapter 1", level=0, page_index=0),
        Bookmark(title="Where To? — Main Menu", level=1, page_index=1),  # won't text-match
    ]
    result = build_blocks(lines, bookmarks, chapter_prefix="Chapter 1", section_depth_below_chapter=1)
    check(
        "handover-A. an unmatched heading still yields a section (page fallback)",
        len(result.sections) == 1,
    )
    check(
        "handover-A. an unmatched heading is reported, not silently dropped",
        "Where To? — Main Menu" in result.unmatched_headings,
    )


def test_obligation_wording_kept_verbatim_not_dropped() -> None:
    # Regression guard: a manual paragraph that itself says "shall"/"must" is real
    # information the manual states, so it must not be silently discarded — dropping
    # it would be exactly the kind of silent information loss this app exists to
    # avoid (see the 2026-08-25 discussion: a real Toyota RAV4 sample keeps "the
    # device must be registered in advance" verbatim, classified as an ordinary
    # capability row, not excluded). What must never happen is the opposite — this
    # generator inventing an obligation the source didn't make; that invariant is
    # enforced by RequirementStrength having no MUST/SHALL value (test 1 above), not
    # by filtering source paragraphs.
    from domain.manual_parsing import Section

    profile = Profile(
        profile_id="test",
        extends=None,
        derived_from="test fixture",
        slot_rules=DEFAULT_SLOT_RULES,
        layout=LayoutConfig(),
    )
    lines = [Line(page=0, text="The driver must confirm the destination before starting.", top=100.0)]
    section = Section(
        title="Confirming the destination",
        level=1,
        page_start=0,
        page_end=0,
        lines=lines,
        matched_by_text=True,
        source_bookmark_index=0,
    )
    fn = build_function_spec(section, profile, "toyota/rav4-2026/multimedia", "Navigation", 1)
    check("concept4. a paragraph using 'must' is kept, not dropped", len(fn.requirements) == 1)
    if fn.requirements:
        check(
            "concept4. the manual's own wording ('must') survives verbatim",
            "must" in fn.requirements[0].text.lower(),
        )
        check(
            "concept4. strength stays one of the 3 non-MUST values",
            fn.requirements[0].strength
            in {RequirementStrength.CAPABILITY, RequirementStrength.DEFINE, RequirementStrength.CONSTRAINT},
        )


def main() -> int:
    test_no_must_shall_in_type()
    test_threshold_requires_evidence()
    test_generate_reads_overlay_before_writing()
    test_is_test_ready_requires_procedure_and_filled_thresholds()
    test_content_id_ignores_position()
    test_title_never_falls_back_to_raw_slug()
    test_title_reflects_generated_chapter_scope()
    test_unmatched_headings_are_reported_not_dropped()
    test_obligation_wording_kept_verbatim_not_dropped()

    print()
    if _FAILURES:
        print(f"check_domain: FAIL ({len(_FAILURES)} failure(s))")
        return 1
    print("check_domain: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
