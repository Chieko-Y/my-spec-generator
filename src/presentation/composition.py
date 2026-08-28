"""The only place concrete infrastructure classes and the application layer meet."""
from __future__ import annotations

from application.use_cases import UseCases
from infrastructure import settings
from infrastructure.config_provider import FileConfigProvider
from infrastructure.figure_renderer import PdfFigureRenderer
from infrastructure.gemini_chapter_classifier import GeminiChapterClassifier
from infrastructure.markdown_publisher import MarkdownSpecPublisher
from infrastructure.pdf_reader import PdfManualReader
from infrastructure.repositories import (
    JsonChapterAllowlistRepository,
    JsonGlossaryRepository,
    JsonSourceRegistry,
    JsonSpecRepository,
    ManualLibrary,
    YamlFigureElementRepository,
    YamlOverlayRepository,
)


def build_use_cases() -> UseCases:
    settings.LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    return UseCases(
        manual_reader=PdfManualReader(),
        figure_renderer=PdfFigureRenderer(settings.WORKSPACE_DIR),
        config_provider=FileConfigProvider(settings.CONFIG_DIR),
        spec_repository=JsonSpecRepository(settings.WORKSPACE_DIR),
        overlay_repository=YamlOverlayRepository(settings.WORKSPACE_DIR),
        figure_element_repository=YamlFigureElementRepository(settings.WORKSPACE_DIR),
        glossary_repository=JsonGlossaryRepository(settings.WORKSPACE_DIR),
        spec_publisher=MarkdownSpecPublisher(settings.WORKSPACE_DIR),
        source_registry=JsonSourceRegistry(settings.LIBRARY_DIR),
        original_library=ManualLibrary(settings.LIBRARY_DIR),
        chapter_classifier=GeminiChapterClassifier(settings.GEMINI_API_KEY, settings.GEMINI_MODEL),
        chapter_allowlist_repository=JsonChapterAllowlistRepository(settings.WORKSPACE_DIR),
    )
