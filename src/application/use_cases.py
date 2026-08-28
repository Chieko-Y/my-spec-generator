"""The three verbs (generate / publish / set_parameter) plus the small helpers that
live in the same layer. Application touches no filesystem directly — every read/write
goes through a port (SourceRegistry, OriginalLibrary, ...), the concrete
implementations of which are wired up in presentation/composition.py only.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

from domain.figures import caption_for, is_figure_sized, merge_rects
from domain.manual_identity import IdentityGuess, guess_identity
from domain.manual_parsing import (
    ChapterClassification,
    ConfirmedChapter,
    Line,
    RunningHeadChapter,
    Section,
    TocChapterCandidate,
    build_blocks,
    build_blocks_from_font_headings,
    build_blocks_from_item_index,
    detect_item_index_entries,
    detect_running_head_chapters,
    detect_toc_chapters,
    drop_repeating_margin_glyphs,
    filter_page_furniture,
    find_running_head_chapter,
    normalize_label,
    order_by_columns,
    sample_heading_evidence,
    synthetic_top_for_position,
)
from domain.profile_derivation import DerivedLayoutReport, derive_layout
from domain.profile_fitness import FitnessReport, score_fitness
from domain.model import FigureRef, ManualSpec, ParameterStatus, content_id
from domain.slug import slugify
from domain.overlay import (
    FigureElement,
    GlossaryTerm,
    MergeReport,
    OverlayEntry,
    apply_thresholds,
    existing_threshold_overlay,
)
from domain.spec_building import build_manual_spec_functions

from .ports import (
    ChapterAllowlistRepository,
    ChapterClassifier,
    ConfigProvider,
    FigureElementRepository,
    FigureRenderer,
    GlossaryRepository,
    ManualReader,
    OriginalLibrary,
    OverlayRepository,
    SourceRegistry,
    SpecPublisher,
    SpecRepository,
)

MANUAL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*$")

# Single source of truth for the license-state vocabulary, so the allowed values and
# which one(s) unlock publish/viewing live in exactly one place. There used to be a
# second "ok" state alongside "internal_use_permitted" that the code treated
# identically — two labels for one behavior, which just invited confusion about
# what (if anything) distinguished them. Removed rather than keeping it around as a
# no-op alias.
LICENSE_STATES = ["unreviewed", "internal_use_permitted", "restricted"]
PUBLISHABLE_LICENSE_STATES = {"internal_use_permitted"}

# "unreviewed" and "restricted" are deliberately distinct labels (nobody has looked
# yet, vs. someone looked and found a real restriction) but are currently treated
# identically by publish/view gating — both blocked, both overridable the same way
# via allow_restricted. Decided (2026-08-24) to leave this as-is until there's a
# concrete case for giving "restricted" stricter handling (e.g. not overridable via
# allow_restricted at all) — not implementing that split speculatively.


def is_publishable_license(license_state: str) -> bool:
    return license_state in PUBLISHABLE_LICENSE_STATES


class ValidationError(Exception):
    pass


class GenerateError(Exception):
    def __init__(self, message: str, available_chapters: list[str] | None = None):
        super().__init__(message)
        self.available_chapters = available_chapters or []


class PublishBlockedError(Exception):
    pass


class ChapterAllowlistError(Exception):
    """Raised by confirm_chapter_allowlist when two confirmed chapters of the
    same manual would end up sharing a normalized label -- the exact collision
    that made chapter_slug/scope silently overwrite each other before
    running_head chapters could be individually confirmed by page range (see
    docs/HANDOVER.md 2026-08-27)."""


def validate_manual_id(manual_id: str) -> None:
    # F-1-4: exactly maker/model/booklet, no parent references or separators smuggled in.
    if ".." in manual_id or manual_id.startswith("/") or manual_id.endswith("/"):
        raise ValidationError(f"invalid manual_id: {manual_id!r}")
    if not MANUAL_ID_RE.match(manual_id):
        raise ValidationError(
            f"manual_id must be <maker>/<model>/<booklet>, got {manual_id!r}"
        )


@dataclass
class GenerateResult:
    spec: ManualSpec
    merge_report: MergeReport
    unmatched_headings: list[str]


@dataclass
class ChapterCandidateReview:
    """One running_head candidate paired with its AI verdict and the real
    evidence text that verdict is allowed to draw from -- everything a human
    needs to review before confirm_chapter_allowlist persists anything (see
    classify_running_head_chapters)."""

    candidate: RunningHeadChapter
    classification: ChapterClassification
    evidence: list[str]


@dataclass
class ProfileResolution:
    """Result of UseCases.resolve_manual_profile -- the "one-click Generate"
    orchestrator (see docs/HANDOVER.md and the plan this implements). status
    "ready" means the chapter picker/generate() can proceed exactly as before
    (call list_available_chapters); "needs_review" means a human must look at
    `notes`/`toc_chapters`/`running_head_candidates` (and, when profile_is_new,
    edit/confirm `profile_id`/`layout`) and then call activate_derived_profile
    before generate() will work for this manual_id."""

    status: str  # "ready" | "needs_review"
    profile_id: str | None = None
    profile_is_new: bool = False
    layout: dict | None = None  # only set when profile_is_new (a brand-new layout to save)
    derived_from: str | None = None
    section_source: str | None = None
    notes: list[str] = field(default_factory=list)
    toc_chapters: list[TocChapterCandidate] = field(default_factory=list)
    running_head_candidates: list[RunningHeadChapter] = field(default_factory=list)


class UseCases:
    def __init__(
        self,
        manual_reader: ManualReader,
        figure_renderer: FigureRenderer,
        config_provider: ConfigProvider,
        spec_repository: SpecRepository,
        overlay_repository: OverlayRepository,
        figure_element_repository: FigureElementRepository,
        glossary_repository: GlossaryRepository,
        spec_publisher: SpecPublisher,
        source_registry: SourceRegistry,
        original_library: OriginalLibrary,
        chapter_classifier: ChapterClassifier,
        chapter_allowlist_repository: ChapterAllowlistRepository,
    ) -> None:
        self.manual_reader = manual_reader
        self.figure_renderer = figure_renderer
        self.config_provider = config_provider
        self.spec_repository = spec_repository
        self.overlay_repository = overlay_repository
        self.figure_element_repository = figure_element_repository
        self.glossary_repository = glossary_repository
        self.spec_publisher = spec_publisher
        self.source_registry = source_registry
        self.original_library = original_library
        self.chapter_classifier = chapter_classifier
        self.chapter_allowlist_repository = chapter_allowlist_repository
        # F-5-7 in the source project's own requirements: never run two generate/publish
        # jobs on the same manual_id at once. Reading a 100+ page PDF with pdfplumber is
        # CPU-bound pure Python (15-20s), so a slow first click plus an impatient retry
        # click used to pile up N full re-reads competing for the GIL, which looked
        # indistinguishable from a hang (observed directly via a live stack dump: 7
        # concurrent /generate requests all stuck inside pdfminer parsing the same PDF).
        # One lock per manual_id, shared between generate() and publish(), rejects a
        # second concurrent call immediately instead of letting it queue up.
        self._locks_guard = threading.Lock()
        self._manual_locks: dict[str, threading.Lock] = {}

    def _lock_for(self, manual_id: str, chapter_slug: str) -> threading.Lock:
        key = f"{manual_id}::{chapter_slug}"
        with self._locks_guard:
            if key not in self._manual_locks:
                self._manual_locks[key] = threading.Lock()
            return self._manual_locks[key]

    def busy_chapters(self, manual_id: str) -> set[str]:
        """Chapter slugs of `manual_id` currently mid-generate/publish, so a page
        LOAD (not just a click on the page that started the job) can show the true
        state. The client-side "disable the button on submit" guard only protects
        the one page instance that was open when the click happened — reloading the
        page, opening it in a second tab, or the request simply outliving that DOM
        state all produce a fresh, enabled button while the server is still actually
        working (reported directly: the button stayed clickable during "Working…").
        threading.Lock.locked() is a non-blocking peek, not an acquire."""
        prefix = f"{manual_id}::"
        with self._locks_guard:
            return {
                key[len(prefix):]
                for key, lock in self._manual_locks.items()
                if key.startswith(prefix) and lock.locked()
            }

    # ------------------------------------------------------------------ generate
    def generate(
        self, manual_id: str, chapter_prefix: str | None, chapter_label: str | None = None
    ) -> GenerateResult:
        validate_manual_id(manual_id)
        if not chapter_prefix:
            raise GenerateError("chapter_prefix is required — pick a chapter from this manual's outline")
        chapter_slug = slugify(chapter_prefix)

        lock = self._lock_for(manual_id, chapter_slug)
        if not lock.acquire(blocking=False):
            raise GenerateError(
                f"{manual_id} ({chapter_prefix}) is already generating or publishing — please "
                "wait for it to finish (reading a large manual can take under a minute) "
                "instead of clicking again."
            )
        try:
            return self._generate_locked(manual_id, chapter_slug, chapter_prefix, chapter_label)
        finally:
            lock.release()

    def _generate_locked(
        self, manual_id: str, chapter_slug: str, chapter_prefix: str, chapter_label: str | None
    ) -> GenerateResult:
        source = self.source_registry.get(manual_id)
        if source is None:
            raise GenerateError(f"manual_id not registered: {manual_id}")

        pdf_path = self.original_library.path_for(manual_id)
        profile = self.config_provider.profile_for(manual_id, source.get("maker", ""))
        # Column-aware word-to-line clustering (columns > 1) needs the profile's
        # columns value at read() time, before any line even exists to reorder --
        # merging words from two different columns into one Line's text (when they
        # happen to land close vertically) can't be undone by reordering lines
        # afterward. See pdf_reader.py::_group_words_into_lines for the real case
        # this fixes (2026-08-27, 2025 Subaru supplement).
        lines, bookmarks = self.manual_reader.read(pdf_path, columns=profile.layout.columns)

        if profile.layout.section_source == "running_head":
            # A confirmed allowlist (see classify_running_head_chapters /
            # confirm_chapter_allowlist) is the deterministic source of truth once
            # it exists: it stores each chapter's own page range directly, so
            # resolution never goes through label-text search at all -- which
            # matters because the same running-head margin text can legitimately
            # repeat for two structurally different chapters (see
            # docs/HANDOVER.md 2026-08-27, the "BASIC OPERATION" collision) and
            # find_running_head_chapter below only ever reaches the first one.
            # Confirmed labels are enforced unique at confirm time, so this lookup
            # can never be ambiguous.
            confirmed = self.chapter_allowlist_repository.load(manual_id)
            if confirmed is not None:
                target = normalize_label(chapter_prefix)
                found = next(
                    (c for c in confirmed if normalize_label(c.label) == target), None
                )
                if found is None:
                    raise GenerateError(
                        f"no confirmed chapter found for chapter_prefix={chapter_prefix!r}. "
                        "This manual has a confirmed chapter allowlist -- check the chapter "
                        "picker for available chapters.",
                        available_chapters=[c.label for c in confirmed],
                    )
                match = RunningHeadChapter(
                    label=found.label, page_start=found.page_start, page_end=found.page_end
                )
                available_chapters = [c.label for c in confirmed]
            else:
                # Detect chapters on the RAW lines, before header/footer stripping:
                # the running-head label IS the chapter-boundary signal, and on a
                # real PDF it can sit inside the same vertical band
                # filter_page_furniture would strip as page furniture (confirmed
                # against the real 2025 Subaru supplement -- filtering first made
                # every chapter label vanish before detect_running_head_chapters
                # ever saw it). Only the chapter's own body content gets
                # furniture-filtered/column-reordered, once we know which pages it
                # spans.
                running_chapters = detect_running_head_chapters(lines)
                match = find_running_head_chapter(running_chapters, chapter_prefix)
                if match is None:
                    raise GenerateError(
                        f"no running-head chapter found for chapter_prefix={chapter_prefix!r}. "
                        "Check the chapter picker for available chapters.",
                        available_chapters=[c.label for c in running_chapters],
                    )
                available_chapters = [c.label for c in running_chapters]
            # A chapter's own local item index (see domain.manual_parsing
            # detect_item_index_entries), if it has one, gives exact ground-truth
            # heading text+page instead of guessing from font size -- tried first,
            # position-agnostic so it can run on the raw lines same as chapter
            # detection above. Falls back to the font-size heuristic below when
            # there's no index, or too few of its entries text-match real content.
            item_index_entries = detect_item_index_entries(lines, match.page_start, match.page_end)
            lines = filter_page_furniture(
                lines, profile.layout.header_boundary_pt, profile.layout.footer_boundary_pt
            )
            # Column boundary detection is scoped to just this chapter's pages, not
            # the whole (possibly hundreds-of-pages) document: a handful of outlier
            # lines elsewhere in the PDF can otherwise dominate detect_column_count's
            # single widest-gap search and produce a boundary that doesn't reflect
            # this chapter's actual layout at all (confirmed against the real 2025
            # Subaru supplement -- 9 stray negative-x0 lines on an unrelated page
            # made the whole-document boundary -111pt, which classified every real
            # line as column 0 and left the true left/right column text unsplit and
            # interleaved, same as if columns=1 had been used).
            chapter_lines = [l for l in lines if match.page_start <= l.page < match.page_end]
            chapter_lines = order_by_columns(chapter_lines, profile.layout.columns)
            blocks = None
            if item_index_entries is not None:
                blocks = build_blocks_from_item_index(chapter_lines, match, item_index_entries)
            if blocks is None:
                blocks = build_blocks_from_font_headings(chapter_lines, match)
            if not blocks.sections:
                raise GenerateError(
                    f"no sections could be cut for chapter_prefix={chapter_prefix!r} "
                    f"(pages {match.page_start + 1}-{match.page_end}). Check the chapter "
                    "picker for available chapters.",
                    available_chapters=available_chapters,
                )
        elif profile.layout.section_source == "chapter_toc":
            # Deterministic, rule-based chapter boundaries derived from this
            # manual's own printed table of contents (see domain.manual_parsing.
            # detect_toc_chapters), confirmed via profile-derive-toc-chapters +
            # profile-confirm-chapters. Unlike running_head, there is no
            # "always available" raw detector to fall back to at generate time --
            # an unconfirmed chapter_toc manual is a hard error, not a guess.
            confirmed = self.chapter_allowlist_repository.load(manual_id)
            if confirmed is None:
                raise GenerateError(
                    f"{manual_id} uses section_source='chapter_toc' but has no "
                    "confirmed chapter allowlist yet -- run profile-derive-toc-chapters, "
                    "review the output, then profile-confirm-chapters."
                )
            target = normalize_label(chapter_prefix)
            found = next(
                (c for c in confirmed if normalize_label(c.label) == target), None
            )
            if found is None:
                raise GenerateError(
                    f"no confirmed chapter found for chapter_prefix={chapter_prefix!r}. "
                    "Check the chapter picker for available chapters.",
                    available_chapters=[c.label for c in confirmed],
                )
            match = RunningHeadChapter(
                label=found.label, page_start=found.page_start, page_end=found.page_end
            )
            item_index_entries = detect_item_index_entries(lines, match.page_start, match.page_end)
            lines = filter_page_furniture(
                lines, profile.layout.header_boundary_pt, profile.layout.footer_boundary_pt
            )
            chapter_lines = [l for l in lines if match.page_start <= l.page < match.page_end]
            chapter_lines = order_by_columns(chapter_lines, profile.layout.columns)
            blocks = None
            if item_index_entries is not None:
                blocks = build_blocks_from_item_index(chapter_lines, match, item_index_entries)
            if blocks is None:
                blocks = build_blocks_from_font_headings(chapter_lines, match)
            if not blocks.sections:
                raise GenerateError(
                    f"no sections could be cut for chapter_prefix={chapter_prefix!r} "
                    f"(pages {match.page_start + 1}-{match.page_end}). Check the chapter "
                    "picker for available chapters.",
                    available_chapters=[c.label for c in confirmed],
                )
        else:
            lines = filter_page_furniture(
                lines, profile.layout.header_boundary_pt, profile.layout.footer_boundary_pt
            )
            lines = order_by_columns(lines, profile.layout.columns)
            blocks = build_blocks(
                lines,
                bookmarks,
                chapter_prefix,
                section_depth_below_chapter=profile.layout.section_depth_below_chapter,
            )
        if not blocks.sections:
            top_level = min((b.level for b in bookmarks), default=0)
            available = [b.title for b in bookmarks if b.level == top_level]
            raise GenerateError(
                f"no sections could be cut for chapter_prefix={chapter_prefix!r}. "
                "Check the chapter picker for available chapters.",
                available_chapters=available,
            )

        area_title = blocks.chapter_title or chapter_prefix or ""
        figures_by_section = self._extract_figures(pdf_path, manual_id, profile, blocks.sections, lines)
        functions = build_manual_spec_functions(
            blocks.sections, profile, manual_id, area_title, figures_by_section
        )

        meta = {
            "unmatched_headings": blocks.unmatched_headings,
            "chapter_prefix": chapter_prefix,
            "chapter_slug": chapter_slug,
            "chapter_label": chapter_label or blocks.chapter_title or chapter_prefix,
            "excluded_sections": [],
        }

        spec = ManualSpec(
            manual_id=manual_id,
            maker=source.get("maker", ""),
            model=source.get("model", ""),
            document_title=source.get("title", ""),
            scope=chapter_prefix or "",
            markets=source.get("markets", []),
            profile_id=profile.profile_id,
            meta=meta,
            functions=functions,
        )

        # Invariant 3: read the existing overlay BEFORE writing anything back, so a
        # re-generate never wipes out what a tester already filled in. Scoped to this
        # one chapter — a different chapter of the same manual_id has its own overlay.
        existing_entries = self.overlay_repository.load_thresholds(manual_id, chapter_slug)
        merge_report = apply_thresholds(spec, existing_entries)

        self.spec_repository.save(spec, chapter_slug)
        self.overlay_repository.save_thresholds(manual_id, chapter_slug, existing_threshold_overlay(spec))

        return GenerateResult(
            spec=spec, merge_report=merge_report, unmatched_headings=blocks.unmatched_headings
        )

    # ---------------------------------------------------------- profile judgment
    def check_profile_fitness(
        self, manual_id: str, profile_id: str, chapter_prefix: str | None = None
    ) -> FitnessReport:
        """Tier 1 of the AI-free profile-judgment design (docs/HANDOVER.md
        2026-08-26): does an already-registered PDF actually fit an EXISTING
        profile, checked with no AI at all. Reads the PDF once and scores it
        against `profile_id` directly (not the manual_id/maker-based resolution
        `generate()` uses) so a caller can try any candidate profile, including one
        the manual isn't mapped to yet."""
        validate_manual_id(manual_id)
        source = self.source_registry.get(manual_id)
        if source is None:
            raise GenerateError(f"manual_id not registered: {manual_id}")
        pdf_path = self.original_library.path_for(manual_id)
        lines, bookmarks = self.manual_reader.read(pdf_path)
        profile = self.config_provider.profile_by_id(profile_id)
        return score_fitness(lines, bookmarks, profile, chapter_prefix)

    def derive_profile_draft(self, manual_id: str) -> DerivedLayoutReport:
        """Tier 2 of the same design: when no existing profile fits, derive
        candidate `layout` values from scratch for a human to review — never
        written directly to config/profiles/ (see cli.py's profile-derive
        command)."""
        validate_manual_id(manual_id)
        source = self.source_registry.get(manual_id)
        if source is None:
            raise GenerateError(f"manual_id not registered: {manual_id}")
        pdf_path = self.original_library.path_for(manual_id)
        lines, bookmarks = self.manual_reader.read(pdf_path)
        image_rects = self.manual_reader.read_image_rects(pdf_path)
        return derive_layout(lines, bookmarks, image_rects)

    def classify_running_head_chapters(self, manual_id: str) -> list[ChapterCandidateReview]:
        """The one AI call in this app (docs/HANDOVER.md 2026-08-27): asks
        ChapterClassifier to judge which running_head candidates are genuine
        chapter titles vs. noise a structural filter can't tell apart, and to
        relabel a candidate only when its own evidence (real text found in its
        page range, see sample_heading_evidence) justifies it -- e.g. two
        candidates sharing the same running-head margin text but covering
        different real chapters. Read-only and idempotent like derive_profile_
        draft/check_profile_fitness (no lock) -- its result is meaningless until
        a human reviews it and confirm_chapter_allowlist persists the approved
        subset; list_available_chapters/generate() never call this directly."""
        validate_manual_id(manual_id)
        source = self.source_registry.get(manual_id)
        if source is None:
            raise GenerateError(f"manual_id not registered: {manual_id}")
        pdf_path = self.original_library.path_for(manual_id)
        profile = self.config_provider.profile_for(manual_id, source.get("maker", ""))
        if profile.layout.section_source != "running_head":
            raise GenerateError(
                f"{manual_id} uses section_source={profile.layout.section_source!r} -- "
                "chapter classification only applies to running_head manuals "
                "(bookmark-based manuals don't have noisy chapter candidates to classify)."
            )
        lines, _ = self.manual_reader.read(pdf_path, columns=profile.layout.columns)
        candidates = detect_running_head_chapters(lines)
        evidence = [
            sample_heading_evidence(lines, c.page_start, c.page_end, exclude_label=c.label)
            for c in candidates
        ]
        manual_context = self.manual_reader.cover_text(pdf_path)
        classifications = self.chapter_classifier.classify(manual_context, candidates, evidence)
        return [
            ChapterCandidateReview(candidate=c, classification=cl, evidence=ev)
            for c, cl, ev in zip(candidates, classifications, evidence)
        ]

    def derive_toc_chapters(self, manual_id: str) -> list[TocChapterCandidate]:
        """The chapter_toc counterpart to classify_running_head_chapters -- but
        pure rule-based (see domain.manual_parsing.detect_toc_chapters): no AI
        call, no evidence-grounding-validation step, since the label IS literal
        text copied from this manual's own printed table of contents, not a
        model's guess. Read-only and idempotent, same as classify_running_head_
        chapters -- its result is meaningless until a human reviews it and
        confirm_chapter_allowlist persists the approved subset."""
        validate_manual_id(manual_id)
        source = self.source_registry.get(manual_id)
        if source is None:
            raise GenerateError(f"manual_id not registered: {manual_id}")
        pdf_path = self.original_library.path_for(manual_id)
        profile = self.config_provider.profile_for(manual_id, source.get("maker", ""))
        if profile.layout.section_source != "chapter_toc":
            raise GenerateError(
                f"{manual_id} uses section_source={profile.layout.section_source!r} -- "
                "TOC-chapter derivation only applies to chapter_toc manuals."
            )
        lines, _ = self.manual_reader.read(pdf_path, columns=profile.layout.columns)
        page_count = max((l.page for l in lines), default=-1) + 1
        candidates = detect_toc_chapters(lines, page_count)
        if candidates is None:
            raise GenerateError(
                f"no parseable table-of-contents page found in {manual_id} -- this "
                "manual can't use section_source='chapter_toc'; consider running_head "
                "or bookmarks instead."
            )
        return candidates

    def confirm_chapter_allowlist(self, manual_id: str, chapters: list[ConfirmedChapter]) -> None:
        """Persists the human-approved subset of a classify_running_head_chapters
        or derive_toc_chapters run so list_available_chapters/generate() can
        resolve chapters deterministically without re-running either. Rejects two
        chapters that would share a normalized label -- that collision is exactly
        what made the second occurrence of a duplicated running-head label
        unreachable before this feature existed (docs/HANDOVER.md 2026-08-27)."""
        validate_manual_id(manual_id)
        seen: dict[str, ConfirmedChapter] = {}
        for c in chapters:
            norm = normalize_label(c.label)
            prior = seen.get(norm)
            if prior is not None:
                raise ChapterAllowlistError(
                    f"duplicate chapter label {c.label!r} for {manual_id} -- also used by "
                    f"pages {prior.page_start + 1}-{prior.page_end} (this one: pages "
                    f"{c.page_start + 1}-{c.page_end}). Two confirmed chapters must have "
                    "distinct labels; rename one in the review file before confirming again."
                )
            seen[norm] = c
        self.chapter_allowlist_repository.save(manual_id, chapters)

    def resolve_manual_profile(self, manual_id: str) -> ProfileResolution:
        """Orchestrates the "one-click Generate" flow: (1) a manual_id already
        pinned in profile_map.json is used as-is; (2) otherwise every known
        profile is tried against the real PDF via score_fitness (AI-free) and
        the first that fits is assigned automatically -- deciding reuse from
        the PDF itself, not from maker/model/year naming (two model years of
        the same real car have been found here to need completely different
        profiles, see docs/HANDOVER.md); (3) if nothing fits, a brand-new
        layout is derived (derive_layout, still AI-free) for a human to review
        via activate_derived_profile. Whichever profile is settled on, if its
        section_source needs a confirmed chapter allowlist that doesn't exist
        yet, that surfaces as needs_review too instead of generate() hard-
        failing or (for running_head) silently offering an unreviewed, possibly
        ambiguous candidate list."""
        validate_manual_id(manual_id)
        source = self.source_registry.get(manual_id)
        if source is None:
            raise GenerateError(f"manual_id not registered: {manual_id}")
        pdf_path = self.original_library.path_for(manual_id)
        maker = source.get("maker", "")

        mapped_id = self.config_provider.mapped_profile_id(manual_id)
        if mapped_id is not None:
            profile = self.config_provider.profile_by_id(mapped_id)
            return self._chapter_review_for(manual_id, profile, pdf_path)

        lines, bookmarks = self.manual_reader.read(pdf_path)
        # profile_for()'s maker-level/default match is used only to order the
        # search (try the maker's usual profile first) -- it is NOT trusted
        # as a verified fit the way an exact manual_id mapping is.
        hint = self.config_provider.profile_for(manual_id, maker).profile_id
        candidate_ids = self.config_provider.list_profile_ids()
        ordered = (
            [hint, *(c for c in candidate_ids if c != hint)] if hint in candidate_ids else candidate_ids
        )
        for candidate_id in ordered:
            profile = self.config_provider.profile_by_id(candidate_id)
            if score_fitness(lines, bookmarks, profile).fits:
                self.config_provider.assign_profile(manual_id, candidate_id)
                return self._chapter_review_for(manual_id, profile, pdf_path)

        image_rects = self.manual_reader.read_image_rects(pdf_path)
        report = derive_layout(lines, bookmarks, image_rects)
        return ProfileResolution(
            status="needs_review",
            profile_id=self._suggest_profile_id(maker),
            profile_is_new=True,
            layout=report.as_profile_layout_dict(),
            derived_from=f"Auto-derived from {manual_id} via derive_layout -- review before activating.",
            section_source=report.section_source,
            notes=report.notes,
            toc_chapters=report.toc_chapters,
            running_head_candidates=report.running_head_chapters,
        )

    def _chapter_review_for(self, manual_id: str, profile, pdf_path: str) -> ProfileResolution:
        """Second half of resolve_manual_profile: given a profile that's
        already settled on (pre-mapped or just fit-matched), decide whether
        its chapters are ready to generate from or still need a human to pick
        the confirmed subset."""
        if profile.layout.section_source not in ("running_head", "chapter_toc"):
            return ProfileResolution(status="ready", profile_id=profile.profile_id)
        if self.chapter_allowlist_repository.load(manual_id) is not None:
            return ProfileResolution(status="ready", profile_id=profile.profile_id)

        lines, _ = self.manual_reader.read(pdf_path, columns=profile.layout.columns)
        if profile.layout.section_source == "chapter_toc":
            page_count = max((l.page for l in lines), default=-1) + 1
            candidates = detect_toc_chapters(lines, page_count)
            if candidates is None:
                return ProfileResolution(
                    status="needs_review",
                    profile_id=profile.profile_id,
                    section_source="chapter_toc",
                    notes=[
                        "this manual's profile assumes section_source=chapter_toc but no "
                        "parseable table-of-contents page was found in this PDF."
                    ],
                )
            return ProfileResolution(
                status="needs_review",
                profile_id=profile.profile_id,
                section_source="chapter_toc",
                toc_chapters=candidates,
                notes=[
                    f"{len(candidates)} chapter(s) found in the printed table of contents "
                    "-- confirm before generating."
                ],
            )

        candidates = detect_running_head_chapters(lines)
        return ProfileResolution(
            status="needs_review",
            profile_id=profile.profile_id,
            section_source="running_head",
            running_head_candidates=candidates,
            notes=[
                f"{len(candidates)} running-head candidate(s) found -- pick which ones are "
                "real chapters before generating."
            ],
        )

    def _suggest_profile_id(self, maker: str) -> str:
        base = slugify(maker) or "manual"
        existing = set(self.config_provider.list_profile_ids())
        n = 1
        while f"{base}_v{n}" in existing:
            n += 1
        return f"{base}_v{n}"

    def activate_derived_profile(
        self,
        manual_id: str,
        profile_id: str,
        layout: dict | None,
        derived_from: str | None,
        chapters: list[ConfirmedChapter] | None,
    ) -> None:
        """Persists a resolve_manual_profile needs_review result once a human
        has reviewed it. `layout` is only passed (non-None) when profile_id is
        a genuinely new profile to create -- reusing an already-existing
        profile that merely needed its chapter allowlist confirmed passes
        layout=None and skips save_new_profile. Reuses confirm_chapter_
        allowlist's own duplicate-label rejection (docs/HANDOVER.md
        2026-08-27) so this can never persist an ambiguous chapter set."""
        validate_manual_id(manual_id)
        if layout is not None:
            self.config_provider.save_new_profile(profile_id, layout, derived_from or "")
        self.config_provider.assign_profile(manual_id, profile_id)
        if chapters is not None:
            self.confirm_chapter_allowlist(manual_id, chapters)

    def _extract_figures(
        self, pdf_path: str, manual_id: str, profile, sections: list[Section], lines: list[Line]
    ) -> list[list[FigureRef]]:
        """One FigureRef list per section, parallel to `sections`. Merges close
        rects into one figure before filtering by size (see domain.figures.merge_rects
        docstring — filtering first would permanently lose a figure built from many
        small fragments), then assigns each surviving figure to whichever section's
        (page, top) window it falls into — the same window build_blocks cuts text
        into, via each Section's start_top. Page number alone is not enough: two
        sections routinely share a page, and a figure sitting right after one
        section's heading but before the next section even starts is still that
        first section's figure. Assigning by page range alone got this wrong on a
        real Subaru case, 2026-08-25 — a screen-illustration figure at the top of
        page 118 (belonging to "Starting the navigation system", confirmed against
        the original's own published output) landed on "Map screen overview"
        instead, the next section starting further down that same page."""
        if not sections:
            return []
        page_start = min(s.page_start for s in sections)
        page_end = max(s.page_end for s in sections)
        rects_by_page = self.manual_reader.read_image_rects(pdf_path, page_start, page_end)
        if not rects_by_page:
            return [[] for _ in sections]

        # Section.start_top is a column-major synthetic key for a multi-column
        # chapter (see order_by_columns), not a real coordinate -- a figure rect's
        # own (x0, top) must be converted the same way before comparing against
        # it, or a right-column figure can never match a right-column section
        # (see synthetic_top_for_position's docstring).
        boundary_lines_by_page: dict[int, list[Line]] = {}
        for l in drop_repeating_margin_glyphs([l for l in lines if page_start <= l.page < page_end]):
            boundary_lines_by_page.setdefault(l.page, []).append(l)

        figures_by_section: list[list[FigureRef]] = [[] for _ in sections]
        for page_index, raw_rects in rects_by_page.items():
            merged = merge_rects(raw_rects, profile.layout.figure_merge_distance_pt)
            sized = [
                r
                for r in merged
                if is_figure_sized(r, profile.layout.figure_min_width_pt, profile.layout.figure_min_height_pt)
            ]
            for rect in sized:
                # rect = (x0, top, x1, bottom)
                synthetic_top = synthetic_top_for_position(
                    boundary_lines_by_page.get(page_index, []), rect[0], rect[1], profile.layout.columns
                )
                image_pos = (page_index, synthetic_top)
                section_idx = None
                for i, s in enumerate(sections):
                    start = (s.page_start, s.start_top)
                    end = (
                        (sections[i + 1].page_start, sections[i + 1].start_top)
                        if i + 1 < len(sections)
                        else (page_end + 1, 0.0)
                    )
                    if start <= image_pos < end:
                        section_idx = i
                        break
                if section_idx is None:
                    continue
                figure_id = content_id(
                    "figure", manual_id, str(page_index), ",".join(f"{v:.1f}" for v in rect)
                )
                if not self.figure_renderer.render(pdf_path, manual_id, figure_id, page_index, rect):
                    continue  # rect had no area within the page -- see FigureRenderer's docstring
                nearest_line = caption_for(rect, page_index, lines)
                figures_by_section[section_idx].append(
                    FigureRef(
                        figure_id=figure_id,
                        page=page_index,
                        rect=rect,
                        caption_source="pdf_image",
                        caption_text=nearest_line.text if nearest_line else None,
                    )
                )
        return figures_by_section

    # ------------------------------------------------------------------- publish
    def publish(self, manual_id: str, chapter_slug: str, allow_restricted: bool = False) -> list[str]:
        validate_manual_id(manual_id)
        lock = self._lock_for(manual_id, chapter_slug)
        if not lock.acquire(blocking=False):
            raise PublishBlockedError(
                f"{manual_id} ({chapter_slug}) is already generating or publishing — please wait for it to finish."
            )
        try:
            return self._publish_locked(manual_id, chapter_slug, allow_restricted)
        finally:
            lock.release()

    def _publish_locked(self, manual_id: str, chapter_slug: str, allow_restricted: bool) -> list[str]:
        source = self.source_registry.get(manual_id)
        if source is None:
            raise PublishBlockedError(f"manual_id not registered: {manual_id}")

        license_state = source.get("license_state", "unreviewed")
        if not is_publishable_license(license_state) and not allow_restricted:
            raise PublishBlockedError(
                f"license_state={license_state!r} — pass allow_restricted=True to publish anyway"
            )

        spec = self.spec_repository.load(manual_id, chapter_slug)
        if spec is None:
            raise PublishBlockedError(f"no generated spec for {manual_id} ({chapter_slug}); run generate first")

        return self.spec_publisher.publish(spec, chapter_slug=chapter_slug, allow_restricted=allow_restricted)

    def list_chapters(self, manual_id: str) -> list[str]:
        """Chapter slugs that have a generated spec for this manual_id — what the
        Manuals list shows instead of a single misleading 'Chapter' scalar."""
        return self.spec_repository.list_chapters(manual_id)

    # -------------------------------------------------------------- set_parameter
    def set_parameter(
        self,
        manual_id: str,
        chapter_slug: str,
        threshold_id: str,
        value: str,
        status: ParameterStatus,
        evidence: str,
        filled_by: str,
    ) -> MergeReport:
        # OverlayEntry.__post_init__ enforces evidence/filled_by (F-3-2 / F-3-4).
        entry = OverlayEntry(
            threshold_id=threshold_id, value=value, status=status, evidence=evidence, filled_by=filled_by
        )
        entries = self.overlay_repository.load_thresholds(manual_id, chapter_slug)
        entries = [e for e in entries if e.threshold_id != threshold_id]
        entries.append(entry)
        self.overlay_repository.save_thresholds(manual_id, chapter_slug, entries)

        spec = self.spec_repository.load(manual_id, chapter_slug)
        report = MergeReport()
        if spec is not None:
            report = apply_thresholds(spec, entries)
            self.spec_repository.save(spec, chapter_slug)
        return report

    # ------------------------------------------------------------- figure elements
    def add_figure_element(self, manual_id: str, chapter_slug: str, element: FigureElement) -> None:
        elements = self.figure_element_repository.load(manual_id, chapter_slug)
        elements = [e for e in elements if e.figure_id != element.figure_id or e.symbol != element.symbol]
        elements.append(element)
        self.figure_element_repository.save(manual_id, chapter_slug, elements)

    def remove_figure_element(self, manual_id: str, chapter_slug: str, figure_id: str, symbol: str) -> None:
        elements = self.figure_element_repository.load(manual_id, chapter_slug)
        elements = [e for e in elements if not (e.figure_id == figure_id and e.symbol == symbol)]
        self.figure_element_repository.save(manual_id, chapter_slug, elements)

    def load_figure_elements(self, manual_id: str, chapter_slug: str) -> list[FigureElement]:
        return self.figure_element_repository.load(manual_id, chapter_slug)

    # ------------------------------------------------------------------- glossary
    def set_term(self, term: GlossaryTerm) -> None:
        terms = self.glossary_repository.load_all()
        for existing in terms:
            if existing.term_id == term.term_id:
                continue
            overlap = set(w.lower() for w in existing.manual_wordings) & set(
                w.lower() for w in term.manual_wordings
            )
            if overlap:
                # F-3-7: the same manual wording cannot be claimed by two in-house terms —
                # which one is meant is a human judgement call, not a machine one.
                raise ValidationError(
                    f"wording {sorted(overlap)} already registered under {existing.in_house_term!r}"
                )
        terms = [t for t in terms if t.term_id != term.term_id]
        terms.append(term)
        self.glossary_repository.save_all(terms)

    def delete_term(self, term_id: str) -> None:
        terms = self.glossary_repository.load_all()
        terms = [t for t in terms if t.term_id != term_id]
        self.glossary_repository.save_all(terms)

    def load_glossary(self) -> list[GlossaryTerm]:
        return self.glossary_repository.load_all()

    # ---------------------------------------------------------------------- misc
    def register_source(self, manual_id: str, fields: dict) -> None:
        validate_manual_id(manual_id)
        self.source_registry.upsert(manual_id, fields)

    def load_spec(self, manual_id: str, chapter_slug: str) -> ManualSpec | None:
        return self.spec_repository.load(manual_id, chapter_slug)

    def preview_outline(self, pdf_path: str) -> tuple[int, list]:
        return self.manual_reader.outline_preview(pdf_path)

    def list_available_chapters(self, manual_id: str) -> dict:
        """Chapter-picker data for the web UI (GET /api/chapters/{manual_id}).
        BUG FOUND 2026-08-27: this used to always list raw PDF bookmarks,
        regardless of the manual's profile -- for a section_source="running_head"
        manual (no usable bookmarks by definition) that meant the picker kept
        showing the same 2 print-production-marker bookmark titles the whole
        feature was built to work around, even after _generate_locked itself had
        long since been fixed to use running-head chapter detection. Dispatches on
        profile.layout.section_source the same way _generate_locked does, so the
        two can never disagree about what a manual's chapters are again."""
        source = self.source_registry.get(manual_id)
        if source is None:
            raise GenerateError(f"manual_id not registered: {manual_id}")
        pdf_path = self.original_library.path_for(manual_id)
        profile = self.config_provider.profile_for(manual_id, source.get("maker", ""))

        if profile.layout.section_source == "running_head":
            page_count, _bookmarks = self.manual_reader.outline_preview(pdf_path)
            confirmed = self.chapter_allowlist_repository.load(manual_id)
            if confirmed is not None:
                # Confirmed labels are the deterministic source of truth once
                # they exist -- no need to re-read/re-detect the raw PDF at all.
                chapter_labels = [c.label for c in confirmed]
            else:
                lines, _ = self.manual_reader.read(pdf_path, columns=profile.layout.columns)
                chapter_labels = [c.label for c in detect_running_head_chapters(lines)]
            return {
                "page_count": page_count,
                "chapters": chapter_labels,
                "bookmark_levels": 0,
                "shallow_warning": False,
                "ai_reviewed": confirmed is not None,
            }

        if profile.layout.section_source == "chapter_toc":
            page_count, _bookmarks = self.manual_reader.outline_preview(pdf_path)
            confirmed = self.chapter_allowlist_repository.load(manual_id)
            if confirmed is not None:
                chapter_labels = [c.label for c in confirmed]
            else:
                # Unlike running_head's raw detector, detect_toc_chapters is
                # pure rule-based (not an AI guess) -- safe to preview here
                # even though generate() itself still hard-fails until confirmed.
                lines, _ = self.manual_reader.read(pdf_path, columns=profile.layout.columns)
                candidates = detect_toc_chapters(lines, page_count)
                chapter_labels = [c.label for c in candidates] if candidates is not None else []
            return {
                "page_count": page_count,
                "chapters": chapter_labels,
                "bookmark_levels": 0,
                "shallow_warning": False,
                "ai_reviewed": confirmed is not None,
            }

        page_count, bookmarks = self.manual_reader.outline_preview(pdf_path)
        top_level = min((b.level for b in bookmarks), default=0)
        chapters = [b.title for b in bookmarks if b.level == top_level]
        max_level = max((b.level for b in bookmarks), default=0)
        return {
            "page_count": page_count,
            "chapters": chapters,
            "bookmark_levels": max_level + 1 if bookmarks else 0,
            "shallow_warning": bool(bookmarks) and max_level < 1,
        }

    def preview_identity(self, pdf_path: str) -> IdentityGuess:
        """Candidate maker/model/year for the registration form to prefill —
        used by BOTH the manual "register" form and the drag-and-drop intake flow,
        so the two paths cannot disagree on how a document's title is derived
        (bug #2 in the report this app was rebuilt to fix)."""
        page_count, bookmarks = self.manual_reader.outline_preview(pdf_path)
        root_title = bookmarks[0].title if bookmarks else ""
        cover = self.manual_reader.cover_text(pdf_path)
        return guess_identity(root_title, cover)
