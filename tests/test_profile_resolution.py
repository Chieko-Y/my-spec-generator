"""Regression tests for UseCases.resolve_manual_profile / activate_derived_profile
-- the "one-click Generate" orchestrator (see docs/HANDOVER.md and the plan this
implements). Covers the three paths a manual can take:

1. already mapped in profile_map.json (exact manual_id match) -> ready, no PDF
   read at all needed to decide that.
2. not mapped, but an existing profile fits the real PDF (checked via
   score_fitness, AI-free) -> assigned automatically, still no human step.
3. nothing fits -> a brand-new layout is derived (derive_layout, still AI-free)
   for a human to review via activate_derived_profile.

Also covers that a resolved profile whose section_source needs a confirmed
chapter allowlist (running_head/chapter_toc) surfaces as needs_review instead
of silently offering an unreviewed/ambiguous candidate list, matching the
"reuse should be verified against the real PDF, not assumed from maker/model/
year naming" conclusion in docs/HANDOVER.md (two model years of the same real
car were found to need completely different profiles).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dataclasses import replace

from application.use_cases import ChapterAllowlistError, UseCases
from domain.manual_parsing import Bookmark, ConfirmedChapter, Line
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


class FakeManualReader:
    def __init__(self, lines, bookmarks, image_rects=None, page_count=None):
        self.lines = lines
        self.bookmarks = bookmarks
        self.image_rects = image_rects or {}
        self.page_count = (
            page_count if page_count is not None else (max((l.page for l in lines), default=-1) + 1)
        )
        self.read_calls = 0

    def read(self, pdf_path: str, columns: int = 1, split_cross_column: bool = False):
        self.read_calls += 1
        return self.lines, self.bookmarks

    def outline_preview(self, pdf_path: str):
        return self.page_count, self.bookmarks

    def cover_text(self, pdf_path: str) -> str:
        return ""

    def read_image_rects(self, pdf_path: str, page_start: int = 0, page_end: int | None = None):
        return self.image_rects


class FakeConfigProvider:
    def __init__(self, profiles: dict[str, Profile], mapping: dict[str, str] | None = None):
        self.profiles = dict(profiles)
        self.mapping = dict(mapping or {})

    def profile_for(self, manual_id: str, maker: str) -> Profile:
        profile_id = self.mapping.get(manual_id) or self.mapping.get(maker) or "generic_v1"
        return self.profile_by_id(profile_id)

    def profile_by_id(self, profile_id: str) -> Profile:
        # Mirrors FileConfigProvider: the returned Profile.profile_id always
        # matches the id it was looked up by, regardless of what placeholder
        # id the fixture happened to construct it with.
        return replace(self.profiles[profile_id], profile_id=profile_id)

    def mapped_profile_id(self, manual_id: str) -> str | None:
        return self.mapping.get(manual_id)

    def list_profile_ids(self) -> list[str]:
        return sorted(self.profiles.keys())

    def assign_profile(self, manual_id: str, profile_id: str) -> None:
        self.mapping[manual_id] = profile_id

    def save_new_profile(self, profile_id: str, layout: dict, derived_from: str) -> None:
        if profile_id in self.profiles:
            raise FileExistsError(profile_id)
        self.profiles[profile_id] = Profile(
            profile_id=profile_id,
            extends="generic_v1",
            derived_from=derived_from,
            slot_rules=DEFAULT_SLOT_RULES,
            layout=LayoutConfig(**layout),
        )


class FakeFigureRenderer:
    def render(self, pdf_path, manual_id, figure_id, page_index, rect) -> bool:
        raise AssertionError("figures are not exercised by these tests")


class FakeOriginalLibrary:
    def path_for(self, manual_id: str) -> str:
        return "fake.pdf"

    def exists(self, manual_id: str) -> bool:
        return True

    def store_upload(self, maker, model, filename, content) -> str:
        raise NotImplementedError


class FakeChapterClassifier:
    def classify(self, manual_context, candidates, evidence):
        raise AssertionError("resolve_manual_profile must never call the AI classifier")


def _profile(section_source: str, columns: int = 1) -> Profile:
    return Profile(
        profile_id="unused",
        extends=None,
        derived_from="test fixture",
        slot_rules=DEFAULT_SLOT_RULES,
        layout=LayoutConfig(section_source=section_source, columns=columns),
    )


def _build_uc(tmp_path: Path, manual_reader, config_provider) -> UseCases:
    workspace = tmp_path / "workspace"
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)
    return UseCases(
        manual_reader=manual_reader,
        figure_renderer=FakeFigureRenderer(),
        config_provider=config_provider,
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


def test_exact_mapping_is_used_directly_without_reading_the_pdf(tmp_path):
    manual_id = "acme/model-2026/ivi"
    bookmarks = [
        Bookmark(title="Audio", level=0, page_index=0),
        Bookmark(title="Phone", level=0, page_index=10),
        Bookmark(title="Navigation", level=0, page_index=20),
    ]
    lines = [Line(page=p, text=f"line {p}", top=100.0, x0=60.0) for p in range(30)]
    reader = FakeManualReader(lines, bookmarks)
    config = FakeConfigProvider(
        profiles={"acme_v1": _profile("bookmarks")},
        mapping={manual_id: "acme_v1"},
    )
    uc = _build_uc(tmp_path, reader, config)
    uc.register_source(manual_id, {"maker": "Acme", "model": "Model 2026"})

    resolution = uc.resolve_manual_profile(manual_id)

    assert resolution.status == "ready"
    assert resolution.profile_id == "acme_v1"
    assert reader.read_calls == 0, "an exact profile_map.json match must not need to re-read the PDF"


def test_fit_search_assigns_a_profile_that_was_never_explicitly_mapped(tmp_path):
    # Bookmarks are too few/junk-shaped to fit any bookmarks-based profile
    # (bookmark_depth_ok requires >= 3 real chapter-shaped top-level bookmarks)
    # -- generic_v1 must fail so the search continues to profile_b, whose
    # section_source="running_head" does not care about bookmarks at all.
    manual_id = "acme/model-2027/ivi"
    bookmarks = [Bookmark(title="4C_P1_P66_ProcessBlack", level=0, page_index=0)]
    lines = [Line(page=p, text=f"line {p}", top=100.0, x0=60.0) for p in range(10)]
    reader = FakeManualReader(lines, bookmarks)
    config = FakeConfigProvider(
        profiles={"generic_v1": _profile("bookmarks"), "profile_b": _profile("running_head")}
    )
    uc = _build_uc(tmp_path, reader, config)
    uc.register_source(manual_id, {"maker": "Acme", "model": "Model 2027"})
    # Pre-confirm the chapter allowlist so this manual's running_head profile
    # is fully ready -- isolates "was a fitting profile found and assigned" from
    # the separate chapter-confirmation concern covered by the next test.
    uc.confirm_chapter_allowlist(manual_id, [ConfirmedChapter(label="Bluetooth", page_start=0, page_end=5)])

    resolution = uc.resolve_manual_profile(manual_id)

    assert resolution.status == "ready"
    assert resolution.profile_id == "profile_b"
    assert config.mapping[manual_id] == "profile_b", "a fit-search match must be persisted for next time"


def test_fit_matched_running_head_profile_without_confirmed_chapters_needs_review(tmp_path):
    manual_id = "acme/model-2028/ivi"
    bookmarks = [Bookmark(title="4C_P1_P66_ProcessBlack", level=0, page_index=0)]
    lines = [Line(page=p, text=f"line {p}", top=100.0, x0=60.0) for p in range(10)]
    for p in range(6):
        # Same x0 as the body text -- detect_column_count operates over the
        # whole document here (score_fitness doesn't scope it to one chapter
        # the way _generate_locked does), so a running-head label at a very
        # different x0 would spuriously look like a second column and make
        # profile_b fail its own column_match_ok check.
        lines.append(Line(page=p, text="Bluetooth settings", top=5.0, x0=60.0, size=8.0))
    reader = FakeManualReader(lines, bookmarks)
    config = FakeConfigProvider(
        profiles={"generic_v1": _profile("bookmarks"), "profile_b": _profile("running_head")}
    )
    uc = _build_uc(tmp_path, reader, config)
    uc.register_source(manual_id, {"maker": "Acme", "model": "Model 2028"})

    resolution = uc.resolve_manual_profile(manual_id)

    assert resolution.status == "needs_review"
    assert resolution.profile_id == "profile_b"
    assert resolution.profile_is_new is False
    assert resolution.section_source == "running_head"
    labels = [c.label for c in resolution.running_head_candidates]
    assert "bluetooth settings" in labels


def test_nothing_fits_derives_a_brand_new_profile_for_review(tmp_path):
    manual_id = "newmaker/model-2026/ivi"
    # Too few top-level bookmarks for bookmark_depth_ok, and no profile at all
    # matches -- only generic_v1 exists, and it requires section_source=bookmarks.
    bookmarks = [Bookmark(title="X", level=0, page_index=0)]
    lines = [Line(page=0, text="TABLE OF CONTENTS", top=79.0, x0=70.9, size=12.0)]

    def chapter_row(page, top, name, printed_page):
        return [
            Line(page=page, text=name, top=top, x0=-269.3, size=11.0),
            Line(page=page, text=str(printed_page), top=top + 0.4, x0=603.8, size=10.0),
        ]

    lines += chapter_row(1, 79.5, "Quick Guide", 3)
    lines += chapter_row(1, 147.5, "Settings", 20)
    lines += chapter_row(1, 181.5, "Phone", 40)
    lines.append(Line(page=2, text="Quick Guide", top=50.0, size=14.0))
    lines.append(Line(page=19, text="Settings", top=50.0, size=14.0))
    lines.append(Line(page=39, text="Phone", top=50.0, size=14.0))

    reader = FakeManualReader(lines, bookmarks, page_count=60)
    config = FakeConfigProvider(profiles={"generic_v1": _profile("bookmarks")})
    uc = _build_uc(tmp_path, reader, config)
    uc.register_source(manual_id, {"maker": "NewMaker", "model": "Model 2026"})

    resolution = uc.resolve_manual_profile(manual_id)

    assert resolution.status == "needs_review"
    assert resolution.profile_is_new is True
    assert resolution.profile_id == "newmaker_v1"
    assert resolution.section_source == "chapter_toc"
    assert [c.label for c in resolution.toc_chapters] == ["Quick Guide", "Settings", "Phone"]
    assert resolution.layout["section_source"] == "chapter_toc"
    assert "newmaker_v1" not in config.profiles, "must not save anything until activate_derived_profile"


def test_suggest_profile_id_avoids_colliding_with_an_existing_one(tmp_path):
    manual_id = "acme/model-2029/ivi"
    bookmarks = [Bookmark(title="X", level=0, page_index=0)]
    lines = [Line(page=p, text=f"line {p}", top=100.0, x0=60.0) for p in range(5)]
    reader = FakeManualReader(lines, bookmarks)
    config = FakeConfigProvider(profiles={"generic_v1": _profile("bookmarks"), "acme_v1": _profile("bookmarks")})
    uc = _build_uc(tmp_path, reader, config)
    uc.register_source(manual_id, {"maker": "Acme", "model": "Model 2029"})

    resolution = uc.resolve_manual_profile(manual_id)

    assert resolution.profile_is_new is True
    assert resolution.profile_id == "acme_v2"


def test_activate_derived_profile_saves_assigns_and_confirms_chapters(tmp_path):
    manual_id = "newmaker/model-2026/ivi"
    config = FakeConfigProvider(profiles={"generic_v1": _profile("bookmarks")})
    uc = _build_uc(tmp_path, FakeManualReader([], []), config)
    uc.register_source(manual_id, {"maker": "NewMaker", "model": "Model 2026"})

    uc.activate_derived_profile(
        manual_id,
        "newmaker_v1",
        layout={"section_source": "chapter_toc", "columns": 2},
        derived_from="test",
        chapters=[ConfirmedChapter(label="Quick Guide", page_start=2, page_end=19)],
    )

    assert "newmaker_v1" in config.profiles
    assert config.profiles["newmaker_v1"].layout.section_source == "chapter_toc"
    assert config.mapping[manual_id] == "newmaker_v1"
    confirmed = uc.chapter_allowlist_repository.load(manual_id)
    assert confirmed == [ConfirmedChapter(label="Quick Guide", page_start=2, page_end=19)]


def test_activate_derived_profile_with_an_existing_profile_does_not_resave_it(tmp_path):
    manual_id = "acme/model-2030/ivi"
    config = FakeConfigProvider(profiles={"generic_v1": _profile("bookmarks"), "acme_v1": _profile("running_head")})
    uc = _build_uc(tmp_path, FakeManualReader([], []), config)
    uc.register_source(manual_id, {"maker": "Acme", "model": "Model 2030"})

    uc.activate_derived_profile(
        manual_id,
        "acme_v1",
        layout=None,
        derived_from=None,
        chapters=[ConfirmedChapter(label="Bluetooth", page_start=0, page_end=5)],
    )

    assert config.mapping[manual_id] == "acme_v1"
    assert uc.chapter_allowlist_repository.load(manual_id) is not None


def test_activate_derived_profile_rejects_duplicate_chapter_labels(tmp_path):
    manual_id = "acme/model-2031/ivi"
    config = FakeConfigProvider(profiles={"generic_v1": _profile("bookmarks"), "acme_v1": _profile("running_head")})
    uc = _build_uc(tmp_path, FakeManualReader([], []), config)
    uc.register_source(manual_id, {"maker": "Acme", "model": "Model 2031"})

    raised = False
    try:
        uc.activate_derived_profile(
            manual_id,
            "acme_v1",
            layout=None,
            derived_from=None,
            chapters=[
                ConfirmedChapter(label="Bluetooth", page_start=0, page_end=5),
                ConfirmedChapter(label="bluetooth", page_start=10, page_end=15),
            ],
        )
    except ChapterAllowlistError:
        raised = True
    assert raised
