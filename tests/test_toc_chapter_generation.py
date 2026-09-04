"""UseCases-level regression tests for section_source="chapter_toc": derive_toc_
chapters, and the _generate_locked/list_available_chapters branches that consume
a confirmed TOC-derived chapter allowlist. Mirrors test_chapter_classification.py's
conventions. No AI/Gemini call anywhere in this path -- ChapterClassifier is faked
but never invoked.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application.use_cases import ChapterAllowlistError, GenerateError, UseCases
from domain.manual_parsing import ConfirmedChapter, Line
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
from test_chapter_classification import FakeChapterClassifier, FakeFigureRenderer, FakeOriginalLibrary


def _toc_and_body_lines() -> list[Line]:
    lines = [Line(page=0, text="TABLE OF CONTENTS", top=79.0, size=12.0)]

    # Chapter rows on the TOC detail page (page 1).
    lines += [
        Line(page=1, text="Introduction", top=100.0, x0=-269.3, size=11.0),
        Line(page=1, text="3", top=100.4, x0=603.8, size=10.0),
        Line(page=1, text="· Read First... 3", top=106.0, x0=105.4, size=8.0),
        Line(page=1, text="Settings", top=140.0, x0=-269.3, size=11.0),
        Line(page=1, text="5", top=140.4, x0=603.8, size=10.0),
        Line(page=1, text="· Sound Settings... 6", top=146.0, x0=105.4, size=8.0),
        Line(page=1, text="Audio", top=180.0, x0=-269.3, size=11.0),
        Line(page=1, text="8", top=180.4, x0=603.8, size=10.0),
        Line(page=1, text="· Radio Operation... 9", top=186.0, x0=105.4, size=8.0),
    ]

    # Body content. Introduction: pages 2-3 (page_start=2, page_end=4).
    lines += [
        Line(page=2, text="Introduction", top=50.0, size=14.0),
        Line(page=2, text="Welcome to the manual.", top=60.0, size=10.0),
        Line(page=3, text="Read First", top=50.0, size=14.0),
        Line(page=3, text="Please read this section first.", top=60.0, size=10.0),
    ]
    # Settings: pages 4-6 (page_start=4, page_end=7).
    lines += [
        Line(page=4, text="Settings", top=50.0, size=14.0),
        Line(page=4, text="Adjust the settings here.", top=60.0, size=10.0),
        Line(page=5, text="Sound Settings", top=50.0, size=14.0),
        Line(page=5, text="Adjust the volume levels.", top=60.0, size=10.0),
    ]
    # Audio: pages 7-8 (page_start=7, page_end=page_count=9).
    lines += [
        Line(page=7, text="Audio", top=50.0, size=14.0),
        Line(page=7, text="Overview of the audio system.", top=60.0, size=10.0),
        Line(page=8, text="Radio Operation", top=50.0, size=14.0),
        Line(page=8, text="How to operate the radio.", top=60.0, size=10.0),
    ]
    return lines


class FakeManualReader:
    def read(self, pdf_path: str, columns: int = 1, split_cross_column: bool = False):
        return _toc_and_body_lines(), []

    def outline_preview(self, pdf_path: str):
        return 9, []

    def cover_text(self, pdf_path: str) -> str:
        return ""

    def read_image_rects(self, pdf_path: str, page_start: int = 0, page_end: int | None = None):
        return {}


class FakeConfigProvider:
    def __init__(self, section_source: str = "chapter_toc"):
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


def _build_uc(tmp_path: Path, section_source: str = "chapter_toc"):
    workspace = tmp_path / "workspace"
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)

    uc = UseCases(
        manual_reader=FakeManualReader(),
        figure_renderer=FakeFigureRenderer(),
        config_provider=FakeConfigProvider(section_source),
        spec_repository=JsonSpecRepository(workspace),
        overlay_repository=YamlOverlayRepository(workspace),
        figure_element_repository=YamlFigureElementRepository(workspace),
        glossary_repository=JsonGlossaryRepository(workspace),
        spec_publisher=MarkdownSpecPublisher(workspace),
        source_registry=JsonSourceRegistry(library),
        original_library=FakeOriginalLibrary(),
        chapter_classifier=FakeChapterClassifier({}),
        chapter_allowlist_repository=JsonChapterAllowlistRepository(workspace),
    )
    manual_id = "subaru/outback-2025/ivi"
    uc.register_source(
        manual_id,
        {"maker": "Subaru", "model": "Outback 2025", "license_state": "internal_use_permitted"},
    )
    return uc, manual_id


def test_derive_toc_chapters_raises_when_profile_is_not_chapter_toc(tmp_path):
    uc, manual_id = _build_uc(tmp_path, section_source="running_head")

    try:
        uc.derive_toc_chapters(manual_id)
        raise AssertionError("expected GenerateError")
    except GenerateError as e:
        assert "chapter_toc" in str(e)


def test_derive_toc_chapters_finds_the_real_toc_structure(tmp_path):
    uc, manual_id = _build_uc(tmp_path)

    candidates = uc.derive_toc_chapters(manual_id)

    assert [c.label for c in candidates] == ["Introduction", "Settings", "Audio"]
    by_label = {c.label: c for c in candidates}
    assert (by_label["Introduction"].page_start, by_label["Introduction"].page_end) == (2, 4)
    assert (by_label["Settings"].page_start, by_label["Settings"].page_end) == (4, 7)
    assert (by_label["Audio"].page_start, by_label["Audio"].page_end) == (7, 9)


def test_derive_toc_chapters_raises_when_no_toc_found(tmp_path):
    class NoTocManualReader(FakeManualReader):
        def read(self, pdf_path: str, columns: int = 1, split_cross_column: bool = False):
            return [Line(page=0, text="Body text only.", top=50.0)], []

    uc, manual_id = _build_uc(tmp_path)
    uc.manual_reader = NoTocManualReader()

    try:
        uc.derive_toc_chapters(manual_id)
        raise AssertionError("expected GenerateError")
    except GenerateError as e:
        assert "table-of-contents" in str(e) or "table of contents" in str(e).lower()


def test_generate_raises_when_chapter_toc_manual_has_no_confirmed_allowlist(tmp_path):
    uc, manual_id = _build_uc(tmp_path)

    try:
        uc.generate(manual_id, chapter_prefix="Settings")
        raise AssertionError("expected GenerateError")
    except GenerateError as e:
        assert "confirmed" in str(e)


def test_generate_uses_confirmed_toc_chapter_page_range(tmp_path):
    uc, manual_id = _build_uc(tmp_path)
    uc.confirm_chapter_allowlist(manual_id, [ConfirmedChapter(label="Settings", page_start=4, page_end=7)])

    result = uc.generate(manual_id, chapter_prefix="Settings")

    assert {f.title for f in result.spec.functions} & {"Settings", "Sound Settings"}


def test_generate_with_confirmed_allowlist_rejects_unknown_chapter_prefix(tmp_path):
    uc, manual_id = _build_uc(tmp_path)
    uc.confirm_chapter_allowlist(manual_id, [ConfirmedChapter(label="Settings", page_start=4, page_end=7)])

    try:
        uc.generate(manual_id, chapter_prefix="Audio")
        raise AssertionError("expected GenerateError")
    except GenerateError as e:
        assert e.available_chapters == ["Settings"]


def test_list_available_chapters_previews_unconfirmed_toc_candidates(tmp_path):
    uc, manual_id = _build_uc(tmp_path)

    result = uc.list_available_chapters(manual_id)

    assert result["chapters"] == ["Introduction", "Settings", "Audio"]
    assert result["ai_reviewed"] is False


def test_list_available_chapters_is_confirmed_list_after_confirmation(tmp_path):
    uc, manual_id = _build_uc(tmp_path)
    uc.confirm_chapter_allowlist(
        manual_id,
        [
            ConfirmedChapter(label="Introduction", page_start=2, page_end=4),
            ConfirmedChapter(label="Settings", page_start=4, page_end=7),
        ],
    )

    result = uc.list_available_chapters(manual_id)

    assert result["chapters"] == ["Introduction", "Settings"]
    assert result["ai_reviewed"] is True


def test_confirm_chapter_allowlist_rejects_duplicate_toc_labels(tmp_path):
    uc, manual_id = _build_uc(tmp_path)

    try:
        uc.confirm_chapter_allowlist(
            manual_id,
            [
                ConfirmedChapter(label="Settings", page_start=4, page_end=7),
                ConfirmedChapter(label="settings", page_start=7, page_end=9),
            ],
        )
        raise AssertionError("expected ChapterAllowlistError")
    except ChapterAllowlistError:
        pass
