"""End-to-end test of generate -> set_parameter -> publish against fake PDF input
(no real PDF needed — ManualReader/OriginalLibrary are stubbed) but real filesystem
repositories, so the actual Markdown output is exercised.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application.use_cases import UseCases
from domain.manual_parsing import Bookmark, Line
from domain.model import ParameterStatus
from domain.profile import LayoutConfig, Profile, DEFAULT_SLOT_RULES
from infrastructure.markdown_publisher import MarkdownSpecPublisher
from infrastructure.repositories import (
    JsonChapterAllowlistRepository,
    JsonGlossaryRepository,
    JsonSourceRegistry,
    JsonSpecRepository,
    YamlFigureElementRepository,
    YamlOverlayRepository,
)


class FakeManualReader:
    def read(self, pdf_path: str, columns: int = 1, split_cross_column: bool = False):
        lines = [
            Line(page=0, text="Multimedia", top=20.0),
            Line(page=1, text="Navigation", top=20.0),
            Line(page=1, text="Map Screen Overview", top=60.0),
            Line(page=1, text="Touch the map icon to open the map screen.", top=90.0),
            Line(
                page=1,
                text="The screen dims after a certain period of time if no operation is made.",
                top=110.0,
            ),
            Line(page=1, text="1. Touch the Menu button.", top=140.0),
            Line(page=1, text="2. Touch Navigation.", top=155.0),
            Line(page=1, text="3. Touch Map.", top=170.0),
            Line(page=2, text="Route Overview", top=30.0),
            Line(page=2, text="A calculated route is shown on the map in blue.", top=60.0),
            Line(page=3, text="Source Selection", top=30.0),
            Line(page=3, text="Touch the Source button to switch between AM, FM, and Bluetooth.", top=60.0),
        ]
        bookmarks = [
            Bookmark(title="Navigation", level=0, page_index=1),
            Bookmark(title="Map Screen Overview", level=1, page_index=1),
            Bookmark(title="Route Overview", level=1, page_index=2),
            Bookmark(title="Audio", level=0, page_index=3),
            Bookmark(title="Source Selection", level=1, page_index=3),
        ]
        return lines, bookmarks

    def outline_preview(self, pdf_path: str):
        _, bookmarks = self.read(pdf_path)
        return 3, bookmarks

    def read_image_rects(self, pdf_path: str, page_start: int = 0, page_end: int | None = None):
        return {}

    def render_figure(self, pdf_path: str, page_index: int, rect, out_path: str) -> None:
        raise AssertionError("render_figure should not be called when read_image_rects is empty")


class FakeConfigProvider:
    def profile_for(self, manual_id: str, maker: str) -> Profile:
        return Profile(
            profile_id="test_profile",
            extends=None,
            derived_from="test fixture",
            slot_rules=DEFAULT_SLOT_RULES,
            layout=LayoutConfig(section_depth_below_chapter=1),
        )


class FakeFigureRenderer:
    def render(self, pdf_path, manual_id, figure_id, page_index, rect) -> None:
        raise AssertionError("render should not be called when read_image_rects is empty")


class FakeOriginalLibrary:
    def path_for(self, manual_id: str) -> str:
        return "fake.pdf"

    def exists(self, manual_id: str) -> bool:
        return True

    def store_upload(self, maker, model, filename, content) -> str:
        raise NotImplementedError


class FakeChapterClassifier:
    def classify(self, manual_context, candidates, evidence):
        raise AssertionError("classify should not be called by generate()/publish()")


def _build_use_cases(tmp_path: Path) -> UseCases:
    workspace = tmp_path / "workspace"
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)

    return UseCases(
        manual_reader=FakeManualReader(),
        figure_renderer=FakeFigureRenderer(),
        config_provider=FakeConfigProvider(),
        spec_repository=JsonSpecRepository(workspace),
        overlay_repository=YamlOverlayRepository(workspace),
        figure_element_repository=YamlFigureElementRepository(workspace),
        glossary_repository=JsonGlossaryRepository(workspace),
        spec_publisher=MarkdownSpecPublisher(workspace),
        source_registry=JsonSourceRegistry(library),
        original_library=FakeOriginalLibrary(),
        chapter_classifier=FakeChapterClassifier(),
        chapter_allowlist_repository=JsonChapterAllowlistRepository(workspace),
    )


def test_generate_and_publish(tmp_path):
    uc = _build_use_cases(tmp_path)
    manual_id = "toyota/rav4-2026/multimedia"

    uc.register_source(
        manual_id,
        {"maker": "Toyota", "model": "RAV4 2026", "title": "Multimedia Owner's Manual", "license_state": "internal_use_permitted"},
    )

    result = uc.generate(manual_id, chapter_prefix="Navigation", chapter_label="Navigation")
    assert len(result.spec.functions) == 2, [f.title for f in result.spec.functions]
    assert result.spec.display_title == "Multimedia Owner's Manual — Navigation"

    map_fn = next(f for f in result.spec.functions if "Map" in f.title)
    assert len(map_fn.procedure) == 3
    assert any(t.status == ParameterStatus.UNFILLED for t in map_fn.all_thresholds), \
        "the vague 'a certain period of time' phrase should produce an unfilled threshold"

    unfilled_threshold = next(t for t in map_fn.all_thresholds if t.status == ParameterStatus.UNFILLED)
    uc.set_parameter(
        manual_id,
        "navigation",
        unfilled_threshold.threshold_id,
        value="10",
        status=ParameterStatus.MEASURED,
        evidence="measured on a test bench: display dims after 10s idle",
        filled_by="tester1",
    )

    # re-generate must not lose the tester's input (invariant 3)
    result2 = uc.generate(manual_id, chapter_prefix="Navigation", chapter_label="Navigation")
    map_fn2 = next(f for f in result2.spec.functions if "Map" in f.title)
    refilled = next(t for t in map_fn2.all_thresholds if t.threshold_id == unfilled_threshold.threshold_id)
    assert refilled.value == "10"
    assert refilled.status == ParameterStatus.MEASURED
    assert refilled.filled_by == "tester1"

    files = uc.publish(manual_id, "navigation")
    assert any(f.endswith("README.md") for f in files)

    readme = next(Path(f) for f in files if f.endswith("README.md"))
    content = readme.read_text(encoding="utf-8")
    assert "Multimedia Owner's Manual — Navigation" in content
    assert "toyota/rav4-2026/multimedia" not in content.split("\n")[0], \
        "H1 must not be the raw manual_id slug (bug #2 regression)"
    assert "Toyota" in content and "RAV4 2026" in content

    map_file = next(Path(f) for f in files if "map" in f.lower() and f.endswith(".md"))
    map_content = map_file.read_text(encoding="utf-8")
    assert "10" in map_content  # the filled threshold value made it into the published file
    assert "tester1" in map_content


def test_multiple_chapters_from_one_registration(tmp_path):
    # Regression test for a UX report: registering a manual is a one-time,
    # whole-book action. generate() must be repeatable for as many different
    # chapters as the manual has, without re-registering, and each chapter's
    # output must be kept independently (not overwrite the others).
    uc = _build_use_cases(tmp_path)
    manual_id = "subaru/outback-2026/multimedia"
    uc.register_source(
        manual_id,
        {
            "maker": "Subaru",
            "model": "Outback 2026",
            "title": "Multimedia Owner's Manual",
            "license_state": "internal_use_permitted",
        },
    )

    assert uc.list_chapters(manual_id) == []

    nav_result = uc.generate(manual_id, chapter_prefix="Navigation", chapter_label="Navigation")
    assert uc.list_chapters(manual_id) == ["navigation"]

    audio_result = uc.generate(manual_id, chapter_prefix="Audio", chapter_label="Audio")
    assert set(uc.list_chapters(manual_id)) == {"navigation", "audio"}

    # generating Audio must not have touched Navigation's already-saved spec
    nav_reloaded = uc.load_spec(manual_id, "navigation")
    assert len(nav_reloaded.functions) == len(nav_result.spec.functions) == 2
    assert len(audio_result.spec.functions) == 1
    assert audio_result.spec.functions[0].title == "Source Selection"

    nav_files = uc.publish(manual_id, "navigation")
    audio_files = uc.publish(manual_id, "audio")
    assert all("navigation" in Path(f).parts for f in nav_files)
    assert all("audio" in Path(f).parts for f in audio_files)


def test_publish_blocked_when_license_unreviewed(tmp_path):
    uc = _build_use_cases(tmp_path)
    manual_id = "honda/pilot-2026/features"
    uc.register_source(manual_id, {"maker": "Honda", "model": "Pilot 2026", "title": "Owner's Manual"})
    uc.generate(manual_id, chapter_prefix="Navigation", chapter_label="Navigation")

    from application.use_cases import PublishBlockedError

    raised = False
    try:
        uc.publish(manual_id, "navigation")
    except PublishBlockedError:
        raised = True
    assert raised, "publish must refuse when license_state is unreviewed (the default)"

    files = uc.publish(manual_id, "navigation", allow_restricted=True)
    assert files
