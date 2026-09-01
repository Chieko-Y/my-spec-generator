"""Ports: the boundary application talks through. Infrastructure implements these;
application never imports a concrete infrastructure class (composition.py is the only
place concretes and abstractions meet).
"""
from __future__ import annotations

from typing import Protocol

from domain.manual_parsing import (
    Bookmark,
    ChapterClassification,
    ConfirmedChapter,
    Line,
    RunningHeadChapter,
)
from domain.model import ManualSpec
from domain.overlay import FigureElement, GlossaryTerm, OverlayEntry
from domain.profile import Profile


class ManualReader(Protocol):
    def read(self, pdf_path: str, columns: int = 1) -> tuple[list[Line], list[Bookmark]]: ...

    def outline_preview(self, pdf_path: str) -> tuple[int, list[Bookmark]]:
        """Return (page_count, bookmarks) without extracting body text — used for the
        chapter-picker screen so a user can look before generating (REQUIREMENTS F-1-7)."""
        ...

    def cover_text(self, pdf_path: str) -> str:
        """Plain text of the first page, used only as identity-guess input."""
        ...

    def read_image_rects(
        self, pdf_path: str, page_start: int = 0, page_end: int | None = None
    ) -> dict[int, list[tuple[float, float, float, float]]]:
        """page_index -> raw embedded-image bounding boxes (x0, top, x1, bottom)
        for pages in [page_start, page_end), unfiltered by size — see domain.figures
        for the filter/merge step. Callers generating one chapter should always
        pass its actual page range rather than scanning the whole document."""
        ...


class ConfigProvider(Protocol):
    def profile_for(self, manual_id: str, maker: str) -> Profile: ...
    def profile_by_id(self, profile_id: str) -> Profile: ...

    def mapped_profile_id(self, manual_id: str) -> str | None:
        """profile_map.json's manual_id -> profile_id entry, exact match only
        -- unlike profile_for(), this does NOT fall back to a maker-level
        match or the default. UseCases.resolve_manual_profile uses this to
        tell "a human has already confirmed this exact manual's profile" apart
        from "no one has verified this yet, only a maker-level guess exists" --
        the latter still needs to go through the fit search, since two model
        years of the same car have been found to need different profiles."""
        ...

    def list_profile_ids(self) -> list[str]:
        """Every real (non-draft) profile_id under config/profiles/, for
        UseCases.resolve_manual_profile's fit-search -- trying each existing
        profile against a newly-registered PDF before falling back to deriving
        a brand-new one from scratch (see docs/HANDOVER.md: reuse should be
        decided by testing the actual PDF, not by maker/model/year naming,
        since two model years of the same car have been found to need
        completely different profiles)."""
        ...

    def assign_profile(self, manual_id: str, profile_id: str) -> None:
        """Persists manual_id -> profile_id in profile_map.json so future
        calls to profile_for() resolve this manual_id directly without
        re-running the fit search against every known profile."""
        ...

    def save_new_profile(self, profile_id: str, layout: dict, derived_from: str) -> None:
        """Writes a brand-new config/profiles/{profile_id}.json that extends
        generic_v1 and overrides only `layout` -- the human-reviewed output of
        UseCases.resolve_manual_profile's needs_review path, confirmed via
        UseCases.activate_derived_profile. Never called with an unreviewed
        derivation result."""
        ...


class SpecRepository(Protocol):
    """One manual_id can hold several generated chapters (chapter_slug) side by
    side — registration is a one-time, whole-manual action; generate() can be
    re-run for any number of chapters afterwards."""

    def save(self, spec: ManualSpec, chapter_slug: str) -> None: ...
    def load(self, manual_id: str, chapter_slug: str) -> ManualSpec | None: ...
    def list_chapters(self, manual_id: str) -> list[str]: ...


class OverlayRepository(Protocol):
    def load_thresholds(self, manual_id: str, chapter_slug: str) -> list[OverlayEntry]: ...
    def save_thresholds(self, manual_id: str, chapter_slug: str, entries: list[OverlayEntry]) -> None: ...


class FigureElementRepository(Protocol):
    def load(self, manual_id: str, chapter_slug: str) -> list[FigureElement]: ...
    def save(self, manual_id: str, chapter_slug: str, elements: list[FigureElement]) -> None: ...


class GlossaryRepository(Protocol):
    def load_all(self) -> list[GlossaryTerm]: ...
    def save_all(self, terms: list[GlossaryTerm]) -> None: ...


class SpecPublisher(Protocol):
    def publish(
        self, spec: ManualSpec, chapter_slug: str, allow_restricted: bool, terms: list[GlossaryTerm]
    ) -> list[str]: ...


class FigureRenderer(Protocol):
    """Crops one figure out of the source PDF and writes it under this manual's
    workspace — the file-writing counterpart to ManualReader.read_image_rects,
    kept separate the same way SpecPublisher is kept separate from ManualReader:
    reading the PDF and writing into the workspace are different concerns, and
    application never constructs workspace paths itself (see module docstring).

    Returns False (no file written) instead of raising when `rect`, once clipped
    to the page's own bbox, has no positive area left -- confirmed directly,
    2026-08-27: a two-page-spread foldout illustration in the real 2025 Subaru
    supplement's "Quick Guide" chapter reuses the same embedded-image
    coordinates on both of its pages, putting the second page's copies at a
    negative x0 entirely outside that page. One bad rect must not fail the
    whole chapter's generate() -- the caller skips just that figure."""

    def render(
        self,
        pdf_path: str,
        manual_id: str,
        figure_id: str,
        page_index: int,
        rect: tuple[float, float, float, float],
    ) -> bool: ...


class ChapterClassifier(Protocol):
    """AI is scoped to exactly this one call site in the whole app (see
    docs/HANDOVER.md 2026-08-27): classifying running_head chapter candidates as a
    genuine chapter/section title vs. noise (a repeating footnote fragment, a
    generic word) that no structural filter can distinguish -- doing so requires
    understanding the text's meaning, not just its shape. Called once, at manual
    registration time, never from generate() or any other runtime path. The result
    must never be applied directly; it is only meaningful once persisted via
    ChapterAllowlistRepository after a human reviews it, so generate() and the
    chapter picker stay deterministic and reproducible without a live model call.

    `evidence` is index-aligned with `candidates` (see
    domain.manual_parsing.sample_heading_evidence) -- real text found within each
    candidate's own page range. A relabeling decision must be grounded in this
    evidence: the returned ChapterClassification.label must be either the
    candidate's own label unchanged, or one of its evidence strings copied
    verbatim -- never freely composed text (see GeminiChapterClassifier for the
    code-level enforcement of this, not just a prompt instruction)."""

    def classify(
        self,
        manual_context: str,
        candidates: list[RunningHeadChapter],
        evidence: list[list[str]],
    ) -> list[ChapterClassification]: ...


class ChapterAllowlistRepository(Protocol):
    """The confirmed, human-approved subset of running_head chapter candidates --
    the only artifact ChapterClassifier's output is allowed to become. Stores each
    confirmed chapter's page range alongside its label (not just the bare label
    string) because the same running-head margin text can legitimately recur for
    two structurally different chapters (see docs/HANDOVER.md 2026-08-27, the
    "BASIC OPERATION" collision) -- page range is what makes each entry
    unambiguous even when relabeling doesn't fully disambiguate the text. load()
    returning None (vs. an empty list) means this manual has never been through
    the classify/confirm flow, and callers must fall back to the unfiltered
    candidate list for backward compatibility with manuals registered before this
    feature existed."""

    def load(self, manual_id: str) -> list[ConfirmedChapter] | None: ...
    def save(self, manual_id: str, chapters: list[ConfirmedChapter]) -> None: ...


class SourceRegistry(Protocol):
    def list_sources(self) -> list[dict]: ...
    def get(self, manual_id: str) -> dict | None: ...
    def upsert(self, manual_id: str, fields: dict) -> None: ...


class OriginalLibrary(Protocol):
    def path_for(self, manual_id: str) -> str: ...
    def exists(self, manual_id: str) -> bool: ...
    def store_upload(self, maker: str, model: str, filename: str, content: bytes) -> str: ...
