"""Regression test for a real bug found in manual testing: generate() had no guard
against running twice for the same manual_id at once. A slow PDF read (15-20s on a
real manual) with no "working…" feedback led to repeated clicks, which piled up
several full PDF parses competing for the GIL — looked exactly like a hang. Fixed by
a per-manual_id, non-blocking lock in UseCases.generate()/publish(); this test
verifies a concurrent second call is rejected immediately rather than queuing.
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application.use_cases import GenerateError
from test_pipeline import (
    FakeChapterClassifier,
    FakeConfigProvider,
    FakeFigureRenderer,
    FakeOriginalLibrary,
    _build_use_cases,
)
from domain.manual_parsing import Bookmark, Line


class SlowManualReader:
    """Same shape as FakeManualReader but blocks for a bit, to give a second call a
    window to observe the lock as held."""

    def __init__(self, delay_s: float):
        self.delay_s = delay_s

    def read(self, pdf_path: str, columns: int = 1):
        time.sleep(self.delay_s)
        lines = [
            Line(page=0, text="Multimedia", top=20.0),
            Line(page=1, text="Touch to open.", top=90.0),
        ]
        bookmarks = [
            Bookmark(title="Navigation", level=0, page_index=1),
            Bookmark(title="Overview", level=1, page_index=1),
        ]
        return lines, bookmarks

    def outline_preview(self, pdf_path: str):
        return 3, self.read(pdf_path)[1]

    def cover_text(self, pdf_path: str) -> str:
        return ""

    def read_image_rects(self, pdf_path: str, page_start: int = 0, page_end: int | None = None):
        return {}


def _build_slow_uc(tmp_path, delay_s: float):
    from infrastructure.markdown_publisher import MarkdownSpecPublisher
    from infrastructure.repositories import (
        JsonChapterAllowlistRepository,
        JsonGlossaryRepository,
        JsonSourceRegistry,
        JsonSpecRepository,
        YamlFigureElementRepository,
        YamlOverlayRepository,
    )
    from application.use_cases import UseCases

    workspace = tmp_path / "workspace"
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)

    uc = UseCases(
        manual_reader=SlowManualReader(delay_s=delay_s),
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
    manual_id = "toyota/rav4-2026/multimedia"
    uc.register_source(
        manual_id,
        {"maker": "Toyota", "model": "RAV4 2026", "title": "Multimedia", "license_state": "internal_use_permitted"},
    )
    return uc, manual_id


def test_concurrent_generate_is_rejected_not_queued(tmp_path):
    uc, manual_id = _build_slow_uc(tmp_path, delay_s=0.5)

    results = []

    def call():
        try:
            uc.generate(manual_id, chapter_prefix="Navigation")
            results.append("ok")
        except GenerateError as e:
            results.append(str(e))

    t1 = threading.Thread(target=call)
    t1.start()
    time.sleep(0.1)  # let t1 acquire the lock and start its slow "read"
    t2 = threading.Thread(target=call)
    t2.start()
    t1.join()
    t2.join()

    assert results.count("ok") == 1, results
    rejected = [r for r in results if r != "ok"]
    assert len(rejected) == 1
    assert "already generating" in rejected[0]


def test_busy_chapters_reflects_true_state_for_a_fresh_page_load(tmp_path):
    # Regression test: the Manuals page only disabled a button via client-side JS
    # on the page instance that was open when the click happened. A reload (or a
    # second tab) got a fresh, enabled button while the server was still actually
    # working — reported directly as "the button stays pressable while Working is
    # showing". busy_chapters() is what a fresh page load checks to show the true
    # state instead of trusting client-side-only disabling.
    uc, manual_id = _build_slow_uc(tmp_path, delay_s=0.3)

    assert uc.busy_chapters(manual_id) == set()

    t = threading.Thread(target=lambda: uc.generate(manual_id, chapter_prefix="Navigation"))
    t.start()
    time.sleep(0.1)  # let it acquire the lock and start its slow "read"

    assert uc.busy_chapters(manual_id) == {"navigation"}

    t.join()
    assert uc.busy_chapters(manual_id) == set()
