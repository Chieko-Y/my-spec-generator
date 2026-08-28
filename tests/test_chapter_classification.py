"""Regression tests for AI-assisted running_head chapter classification and
evidence-grounded relabeling (see docs/HANDOVER.md 2026-08-27):
UseCases.classify_running_head_chapters/confirm_chapter_allowlist,
JsonChapterAllowlistRepository, list_available_chapters' allowlist filtering,
and _generate_locked's confirmed-page-range bypass (the fix for two chapters
sharing the same raw running-head label). No real Gemini/network call anywhere
here -- ChapterClassifier is faked, so this covers the wiring/persistence/
filtering/generation logic, not the Gemini adapter itself (see
test_gemini_chapter_classifier.py for that).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application.use_cases import ChapterAllowlistError, GenerateError, UseCases
from domain.manual_parsing import ChapterClassification, ConfirmedChapter, Line
from domain.profile import DEFAULT_SLOT_RULES, LayoutConfig, Profile
from infrastructure.markdown_publisher import MarkdownSpecPublisher
from infrastructure.repositories import (
    JsonChapterAllowlistRepository,
    JsonGlossaryRepository,
    JsonSourceRegistry,
    JsonSpecRepository,
    YamlFigureElementRepository,
    YamlOverlayRepository,
)


def _running_head_lines() -> list[Line]:
    # "Bluetooth settings" is a real chapter label; "note" is the kind of generic
    # short word the structural heuristic can't tell apart from one (see
    # docs/HANDOVER.md 2026-08-27's "navi system" bug). No font sizes set, so
    # sample_heading_evidence has nothing to find here -- that's tested
    # separately with a fixture that does set sizes.
    lines = []
    for page in range(3):
        lines.append(Line(page=page, text="Bluetooth settings", top=5.0))
        lines.append(Line(page=page, text=f"Body text {page}.", top=100.0))
    for page in range(3, 6):
        lines.append(Line(page=page, text="note", top=5.0))
        lines.append(Line(page=page, text=f"Body text {page}.", top=100.0))
    return lines


def _duplicate_label_lines() -> list[Line]:
    # The real bug this regression-tests (docs/HANDOVER.md 2026-08-27): the same
    # running-head label ("basic operation") printed for two structurally
    # different chapters. Pages 0-2 are audio-flavored, pages 4-6 are
    # navigation-flavored -- distinguishable only by their own heading text, not
    # by the shared margin label. Font sizes are set so build_blocks_from_font_
    # headings/sample_heading_evidence can actually find headings.
    lines = []
    for page in range(3):
        lines.append(Line(page=page, text="basic operation", top=5.0, size=8.0))
    lines.append(Line(page=0, text="Selecting a source", top=50.0, size=14.0))
    lines.append(Line(page=0, text="Touch the source icon to select it.", top=60.0, size=10.0))
    lines.append(Line(page=1, text="Adjusting the volume", top=50.0, size=14.0))
    lines.append(Line(page=1, text="Turn the volume knob.", top=60.0, size=10.0))
    lines.append(Line(page=3, text="filler", top=5.0, size=8.0))  # breaks the running-head run
    for page in range(4, 7):
        lines.append(Line(page=page, text="basic operation", top=5.0, size=8.0))
    lines.append(Line(page=4, text="Map screen", top=50.0, size=14.0))
    lines.append(Line(page=4, text="Touch the map icon to open the map.", top=60.0, size=10.0))
    lines.append(Line(page=5, text="Route calculation", top=50.0, size=14.0))
    lines.append(Line(page=5, text="Select a destination to calculate a route.", top=60.0, size=10.0))
    return lines


class FakeManualReader:
    def __init__(self, lines: list[Line] | None = None):
        self._lines = lines if lines is not None else _running_head_lines()

    def read(self, pdf_path: str, columns: int = 1):
        return self._lines, []

    def outline_preview(self, pdf_path: str):
        return 7, []

    def cover_text(self, pdf_path: str) -> str:
        return "Subaru Outback 2025 Owner's Manual Supplement"

    def read_image_rects(self, pdf_path: str, page_start: int = 0, page_end: int | None = None):
        return {}


class FakeConfigProvider:
    def __init__(self, section_source: str):
        self.section_source = section_source

    def profile_for(self, manual_id: str, maker: str) -> Profile:
        return Profile(
            profile_id="test_profile",
            extends=None,
            derived_from="test fixture",
            slot_rules=DEFAULT_SLOT_RULES,
            layout=LayoutConfig(section_source=self.section_source),
        )

    def profile_by_id(self, profile_id: str) -> Profile:
        raise NotImplementedError


class FakeOriginalLibrary:
    def path_for(self, manual_id: str) -> str:
        return "fake.pdf"

    def exists(self, manual_id: str) -> bool:
        return True

    def store_upload(self, maker, model, filename, content) -> str:
        raise NotImplementedError


class FakeFigureRenderer:
    def render(self, pdf_path, manual_id, figure_id, page_index, rect) -> None:
        raise AssertionError("render should not be called by these tests")


class FakeChapterClassifier:
    """Canned verdicts by (already-normalized) label, keyed the same way
    detect_running_head_chapters normalizes its candidates. Only returns a
    renamed label when the caller explicitly asks for one via
    renames_by_label -- otherwise echoes the candidate's own label, matching
    GeminiChapterClassifier's "default to unchanged" behavior."""

    def __init__(self, verdicts_by_label: dict[str, bool], renames_by_label: dict[str, str] | None = None):
        self.verdicts_by_label = verdicts_by_label
        self.renames_by_label = renames_by_label or {}
        self.received_context = None
        self.received_candidates = None
        self.received_evidence = None

    def classify(self, manual_context, candidates, evidence):
        self.received_context = manual_context
        self.received_candidates = candidates
        self.received_evidence = evidence
        return [
            ChapterClassification(
                label=self.renames_by_label.get(c.label, c.label),
                is_real_chapter=self.verdicts_by_label[c.label],
                reason="fake",
            )
            for c in candidates
        ]


def _build_uc(tmp_path: Path, section_source: str, classifier=None, lines: list[Line] | None = None):
    workspace = tmp_path / "workspace"
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)

    uc = UseCases(
        manual_reader=FakeManualReader(lines),
        figure_renderer=FakeFigureRenderer(),
        config_provider=FakeConfigProvider(section_source),
        spec_repository=JsonSpecRepository(workspace),
        overlay_repository=YamlOverlayRepository(workspace),
        figure_element_repository=YamlFigureElementRepository(workspace),
        glossary_repository=JsonGlossaryRepository(workspace),
        spec_publisher=MarkdownSpecPublisher(workspace),
        source_registry=JsonSourceRegistry(library),
        original_library=FakeOriginalLibrary(),
        chapter_classifier=classifier or FakeChapterClassifier({}),
        chapter_allowlist_repository=JsonChapterAllowlistRepository(workspace),
    )
    manual_id = "subaru/outback-2025/ivi"
    uc.register_source(
        manual_id,
        {"maker": "Subaru", "model": "Outback 2025", "license_state": "internal_use_permitted"},
    )
    return uc, manual_id


def test_classify_running_head_chapters_passes_detected_candidates_to_the_classifier(tmp_path):
    classifier = FakeChapterClassifier({"bluetooth settings": True, "note": False})
    uc, manual_id = _build_uc(tmp_path, "running_head", classifier)

    reviews = uc.classify_running_head_chapters(manual_id)

    assert {r.candidate.label for r in reviews} == {"bluetooth settings", "note"}
    assert classifier.received_context == "Subaru Outback 2025 Owner's Manual Supplement"
    assert len(classifier.received_evidence) == len(classifier.received_candidates)
    assert {r.candidate.label: r.classification.is_real_chapter for r in reviews} == {
        "bluetooth settings": True,
        "note": False,
    }


def test_classify_running_head_chapters_computes_per_candidate_evidence_from_font_sized_headings(tmp_path):
    classifier = FakeChapterClassifier({"basic operation": True})
    uc, manual_id = _build_uc(tmp_path, "running_head", classifier, lines=_duplicate_label_lines())

    reviews = uc.classify_running_head_chapters(manual_id)

    by_pages = {(r.candidate.page_start, r.candidate.page_end): r for r in reviews}
    assert set(by_pages[(0, 3)].evidence) == {"Selecting a source", "Adjusting the volume"}
    assert set(by_pages[(4, 7)].evidence) == {"Map screen", "Route calculation"}


def test_classify_running_head_chapters_rejects_non_running_head_profiles(tmp_path):
    uc, manual_id = _build_uc(tmp_path, "bookmarks")

    try:
        uc.classify_running_head_chapters(manual_id)
        raise AssertionError("expected GenerateError")
    except GenerateError as e:
        assert "running_head" in str(e)


def test_chapter_allowlist_repository_round_trip(tmp_path):
    repo = JsonChapterAllowlistRepository(tmp_path)
    manual_id = "subaru/outback-2025/ivi"

    assert repo.load(manual_id) is None

    repo.save(manual_id, [ConfirmedChapter(label="bluetooth settings", page_start=0, page_end=3)])
    assert repo.load(manual_id) == [
        ConfirmedChapter(label="bluetooth settings", page_start=0, page_end=3)
    ]

    repo.save(
        manual_id,
        [
            ConfirmedChapter(label="bluetooth settings", page_start=0, page_end=3),
            ConfirmedChapter(label="audio", page_start=3, page_end=6),
        ],
    )
    assert repo.load(manual_id) == [
        ConfirmedChapter(label="bluetooth settings", page_start=0, page_end=3),
        ConfirmedChapter(label="audio", page_start=3, page_end=6),
    ]


def test_confirm_chapter_allowlist_rejects_duplicate_normalized_labels(tmp_path):
    uc, manual_id = _build_uc(tmp_path, "running_head")

    try:
        uc.confirm_chapter_allowlist(
            manual_id,
            [
                ConfirmedChapter(label="Basic Operation", page_start=0, page_end=3),
                ConfirmedChapter(label="basic operation", page_start=4, page_end=7),
            ],
        )
        raise AssertionError("expected ChapterAllowlistError")
    except ChapterAllowlistError as e:
        assert "basic operation" in str(e).lower() or "Basic Operation" in str(e)


def test_list_available_chapters_is_unfiltered_when_never_classified(tmp_path):
    uc, manual_id = _build_uc(tmp_path, "running_head")

    result = uc.list_available_chapters(manual_id)

    assert sorted(result["chapters"]) == ["bluetooth settings", "note"]
    assert result["ai_reviewed"] is False


def test_list_available_chapters_is_filtered_after_confirmation(tmp_path):
    uc, manual_id = _build_uc(tmp_path, "running_head")
    uc.confirm_chapter_allowlist(
        manual_id, [ConfirmedChapter(label="bluetooth settings", page_start=0, page_end=3)]
    )

    result = uc.list_available_chapters(manual_id)

    assert result["chapters"] == ["bluetooth settings"]
    assert result["ai_reviewed"] is True


def test_generate_uses_confirmed_page_range_and_bypasses_raw_detection(tmp_path):
    # If this used find_running_head_chapter/detect_running_head_chapters at all,
    # it would resolve "renamed label" to nothing (that text was never a running-
    # head label in the raw PDF) -- proving the confirmed-allowlist path is what
    # actually resolves it, not a coincidental page-range match.
    uc, manual_id = _build_uc(tmp_path, "running_head", lines=_duplicate_label_lines())
    uc.confirm_chapter_allowlist(
        manual_id, [ConfirmedChapter(label="renamed label", page_start=0, page_end=3)]
    )

    result = uc.generate(manual_id, chapter_prefix="renamed label")

    assert {f.title for f in result.spec.functions} & {"Selecting a source", "Adjusting the volume"}


def test_generate_reaches_both_chapters_sharing_the_same_raw_running_head_label(tmp_path):
    uc, manual_id = _build_uc(tmp_path, "running_head", lines=_duplicate_label_lines())
    uc.confirm_chapter_allowlist(
        manual_id,
        [
            ConfirmedChapter(label="basic operation", page_start=0, page_end=3),
            ConfirmedChapter(label="map screen", page_start=4, page_end=7),
        ],
    )

    audio = uc.generate(manual_id, chapter_prefix="basic operation")
    nav = uc.generate(manual_id, chapter_prefix="map screen")

    audio_titles = {f.title for f in audio.spec.functions}
    nav_titles = {f.title for f in nav.spec.functions}
    assert audio_titles & {"Selecting a source", "Adjusting the volume"}
    assert nav_titles & {"Map screen", "Route calculation"}
    assert audio_titles.isdisjoint(nav_titles)


def test_generate_with_confirmed_allowlist_rejects_unknown_chapter_prefix(tmp_path):
    uc, manual_id = _build_uc(tmp_path, "running_head", lines=_duplicate_label_lines())
    uc.confirm_chapter_allowlist(
        manual_id, [ConfirmedChapter(label="basic operation", page_start=0, page_end=3)]
    )

    try:
        uc.generate(manual_id, chapter_prefix="map screen")
        raise AssertionError("expected GenerateError")
    except GenerateError as e:
        assert e.available_chapters == ["basic operation"]
