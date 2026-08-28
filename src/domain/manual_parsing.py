"""Turn a page/line stream plus a bookmark outline into section blocks.

Pure logic — takes plain data structures the infrastructure layer fills in from a PDF,
returns plain data structures. No pdfplumber/pypdfium2 import here.

Design note (fixes a known issue in the app this was rebuilt from, see
docs/HANDOVER.md section A "見出しがしおりにあるのに本文と一致しない"): the original
matched a bookmark heading to a body line by exact string equality, and any heading
that did not find an exact match was silently dropped (Ram: 39 candidate headings,
1 survived). This version does two things differently:

1. Normalizes both sides (collapses whitespace/dashes/case) before comparing, so
   headings that differ only by punctuation still match.
2. Any heading that still cannot be matched to a body line falls back to the
   bookmark's own page number as the section boundary (coarser, but not zero), and is
   recorded in `unmatched_headings` instead of vanishing without a trace.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field, replace


@dataclass
class Line:
    page: int  # 0-based
    text: str
    top: float
    x0: float = 0.0
    size: float = 0.0


@dataclass
class Bookmark:
    title: str
    level: int  # 0-based, 0 = top
    page_index: int  # 0-based


@dataclass
class Section:
    title: str
    level: int
    page_start: int
    page_end: int
    lines: list[Line]
    matched_by_text: bool
    source_bookmark_index: int  # position among siblings, used for chapter_number fallback
    start_top: float = -1.0  # exact (page_start, start_top) this section's own content
    # begins at — needed by anything assigning a PDF-page-level object (a figure) to
    # a section by more than just page number, since two sections routinely share a
    # page. Without it, a figure sitting between two sections on the same page can
    # only be assigned by whichever section's page RANGE the page falls into, which
    # is exactly wrong when the figure actually sits before that section even starts
    # (confirmed directly: a Subaru figure at the top of page 118 belongs to the
    # section ending there, not the one starting later on the same page — assigning
    # by page range alone put it on the wrong function, 2026-08-25).


@dataclass
class BuildBlocksResult:
    chapter_title: str | None
    sections: list[Section]
    unmatched_headings: list[str] = field(default_factory=list)


_STEP_LINE_RE = re.compile(r"^\s*\d{1,2}[.)]\s+\S")
# A numbered procedure step never IS header/footer furniture, only ever sits near
# it by coincidence -- confirmed against the real 2025 Subaru supplement: step "5.
# ->" of a right-column map-update procedure prints at top=67.8pt, just inside the
# manual's header_boundary_pt=75.0 cutoff, because that column's screenshot starts
# unusually high on that one page. A single global boundary can't tell "real
# content that happens to sit high on this one page" from "actual repeating header
# junk", so real header/footer text (production filenames, page numbers, running
# chapter titles) is excluded by its OWN shape instead: it is never "<number>.
# <text>" or "<number>) <text>" -- that shape belongs to a procedure step alone.
#
# The step's own continuation can ALSO fall inside the band: on that same page,
# "(Update XX MB)" / "Update XX MB" at top=70.0/71.3 -- both still under the
# 75.0pt cutoff -- are the manual's own continuation of step "5." (confirmed
# directly by the user reading the real PDF), not separate furniture. A line in
# the band is kept if it sits within _STEP_CONTINUATION_GAP_PT of an
# already-kept line on the same page, so "real content, just printed high"
# keeps propagating outward from a step anchor instead of stopping at the first
# line after the step number.
_STEP_CONTINUATION_GAP_PT = 15.0


def filter_page_furniture(
    lines: list[Line], header_boundary_pt: float, footer_boundary_pt: float | None
) -> list[Line]:
    """Drop running-head/footer lines that sit at a fixed vertical band on every page
    (production filenames, repeated chapter titles, bare page numbers) before any
    section/paragraph logic sees them. Values are measured per-manual from the real
    PDF (see e.g. subaru_v1.json derived_from) — never guessed. Both boundaries
    default to "off" (0.0 / None) so a profile that doesn't set them is unaffected.
    A numbered-step line, and anything immediately continuing it, is kept even
    inside the header/footer band -- see _STEP_LINE_RE/_STEP_CONTINUATION_GAP_PT
    above. Lines are assumed to already arrive in (page, top) reading order (true
    of manual_reader.read()'s own per-page top-sort, before any column reordering).
    """
    kept: list[Line] = []
    prev_kept_top: float | None = None
    prev_page: int | None = None
    for l in lines:
        if l.page != prev_page:
            prev_kept_top = None
        in_body_band = l.top >= header_boundary_pt and (
            footer_boundary_pt is None or l.top <= footer_boundary_pt
        )
        keep = (
            in_body_band
            or _STEP_LINE_RE.match(l.text)
            or (prev_kept_top is not None and 0 <= l.top - prev_kept_top <= _STEP_CONTINUATION_GAP_PT)
        )
        if keep:
            kept.append(l)
            prev_kept_top = l.top
        prev_page = l.page
    return kept


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[‒–—―\-–—]+", " ", text)  # dashes -> space
    text = re.sub(r"[^\w\s]", "", text)  # drop remaining punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_label(text: str) -> str:
    """Public alias of _normalize for callers outside this module that need the
    same case/punctuation-insensitive comparison used internally here (e.g.
    UseCases.confirm_chapter_allowlist's duplicate-label check, and
    UseCases._generate_locked's confirmed-chapter lookup by chapter_prefix)."""
    return _normalize(text)


def _find_line_for_heading(heading: str, candidate_lines: list[Line]) -> Line | None:
    target = _normalize(heading)
    if not target:
        return None
    for line in candidate_lines:
        if _normalize(line.text) == target:
            return line
    # Loosen: heading text contained in a line (running heads sometimes trail a page number)
    for line in candidate_lines:
        norm_line = _normalize(line.text)
        if target and (target in norm_line or norm_line in target) and len(target) > 3:
            return line
    return None


_MIN_CONTAINMENT_RATIO = 0.5
# See _find_exact_line_for_heading: how much of the longer string the shorter
# one must cover for a non-exact containment match to count as "probably the
# same heading" rather than a coincidental fragment.


def _find_exact_line_for_heading(
    heading: str, candidate_lines: list[Line], min_heading_size: float | None = None
) -> Line | None:
    """Stricter sibling of _find_line_for_heading, used by
    build_blocks_from_item_index: an item-index entry's name is expected to
    appear near-verbatim as a real heading, either as an exact match or a
    strong (see _MIN_CONTAINMENT_RATIO) containment in either direction, guarded
    by `min_heading_size` so it never wins against a low-signal body-sized
    caption fragment. _find_line_for_heading's own "norm_line in target"
    loosening (for a bookmark title that trails a page number) is too
    permissive here -- confirmed against the real 2025 Subaru supplement: the
    short entry "Using Wi-Fi®" (normalized "using wifi") loosely matches an
    unrelated inline figure caption fragment reading just "(Wi-Fi)" (normalized
    "wifi", 4 chars) because "wifi" sits inside "using wifi". The index entry
    and its real heading can differ in EITHER direction -- the heading can run
    longer, as a prefix the entry name is only the tail of ("UPDATING THE MAP
    DATA MANUALLY USING Wi-Fi®" vs. index entry "Using Wi-Fi®"), or shorter, as
    just the tail of the entry name ("USB MEMORY DEVICE" vs. index entry "Using
    A USB Memory Device") -- so both containment directions are needed. What
    makes this safe against the "(Wi-Fi)" false positive is `min_heading_size`:
    a candidate is only accepted this way if its own font size clears it, and
    the caption fragment that caused that false positive was body-sized, not
    heading-sized. That alone isn't enough, though -- confirmed directly
    against the real PDF: a SEPARATE entry, "Map Data" (target page 223), also
    passes the size gate against the unrelated real heading "UPDATING THE MAP
    DATA MANUALLY USING" (top half of a two-physical-line heading whose bottom
    half, "Wi-Fi®" alone, is what "Using Wi-Fi®" is supposed to match) purely
    because "map data" happens to sit inside it -- a coincidental, weak
    containment, not a real reference to the same heading. `_MIN_CONTAINMENT_RATIO`
    additionally requires the shorter string to be a substantial fraction of the
    longer one: "usb memory device"/"using a usb memory device" is a strong
    18/26 (69%) containment (accept), "map data"/"...manually using" is a weak
    8/37 (22%) one (reject), and "wifi"/"using wifi" is 4/10 (40%, reject) --
    also correctly rejecting the original "(Wi-Fi)" caption case even without
    the size gate's help.
    """
    target = _normalize(heading)
    if not target:
        return None
    for line in candidate_lines:
        norm_line = _normalize(line.text)
        if norm_line == target:
            return line
    if min_heading_size is None:
        return None
    for line in candidate_lines:
        if line.size < min_heading_size:
            continue
        norm_line = _normalize(line.text)
        if not norm_line:
            continue
        contained = norm_line in target or target in norm_line
        if not contained:
            continue
        ratio = min(len(norm_line), len(target)) / max(len(norm_line), len(target))
        if ratio >= _MIN_CONTAINMENT_RATIO:
            return line
    return None



# A heading becomes its own section only if there is real body text sitting directly
# under it (before the very next heading, of any level). A heading with nothing of
# its own — a pure container whose text starts immediately at its first child, e.g.
# Subaru's "Map screen operation" sitting right above "Map scrolling operation" with
# not one line between them — is skipped, and the search simply continues into its
# children. This replaces picking one fixed depth for the whole chapter (which either
# swallows a nested child's content into its container parent's section, or, if the
# depth doesn't reach that far, drops the child entirely): depth varies node-to-node
# in real manuals (confirmed against Subaru's own outline, 2026-08-25), so the
# decision has to be made per node, not once for the whole chapter. A parent that
# does have its own lead-in text before its first child (e.g. "Search screen") still
# gets counted, in addition to that child — both are real, independent content.
#
# "Has content" means at least one real line, not a length cutoff: page furniture is
# already stripped upstream (filter_page_furniture), so anything left here is genuine
# body text, and a short line is still a real line (e.g. a single short instruction).


def build_blocks(
    lines: list[Line],
    bookmarks: list[Bookmark],
    chapter_prefix: str | None,
    section_depth_below_chapter: int = 2,  # unused by the current algorithm; kept so
    # existing profile.json layout blocks and call sites don't need to change shape.
) -> BuildBlocksResult:
    if not bookmarks:
        return BuildBlocksResult(chapter_title=None, sections=[], unmatched_headings=[])

    top_level = min(b.level for b in bookmarks)
    chapters = [b for b in bookmarks if b.level == top_level]

    if chapter_prefix:
        prefix_norm = _normalize(chapter_prefix)
        matched_chapters = [c for c in chapters if _normalize(c.title).startswith(prefix_norm)]
    else:
        matched_chapters = chapters

    if not matched_chapters:
        return BuildBlocksResult(chapter_title=None, sections=[], unmatched_headings=[])

    chapter = matched_chapters[0]
    chapter_start_idx = bookmarks.index(chapter)
    next_chapter = next(
        (b for b in bookmarks[chapter_start_idx + 1 :] if b.level <= chapter.level), None
    )
    chapter_end_page = next_chapter.page_index if next_chapter else max(l.page for l in lines) + 1

    candidates = [
        b
        for b in bookmarks[chapter_start_idx + 1 :]
        if (next_chapter is None or bookmarks.index(b) < bookmarks.index(next_chapter))
    ]

    # Pass 1: resolve where each candidate's own heading line actually starts. The
    # search window is bounded by the *next* candidate (any level) so a heading with a
    # tight, same-page neighbor can't accidentally text-match something further down.
    starts: list[tuple[int, float, bool]] = []  # (page, top, matched_by_text)
    for i, heading in enumerate(candidates):
        next_candidate = candidates[i + 1] if i + 1 < len(candidates) else None
        window_end_page = next_candidate.page_index if next_candidate else chapter_end_page
        candidate_lines = [
            l
            for l in lines
            if heading.page_index <= l.page <= min(window_end_page, heading.page_index + 2)
        ]
        matched_line = _find_line_for_heading(heading.title, candidate_lines)
        if matched_line is not None:
            starts.append((matched_line.page, matched_line.top, True))
        else:
            starts.append((heading.page_index, -1.0, False))

    candidate_headings = [
        (heading.title, starts[i][0], starts[i][1], heading.level, starts[i][2], i)
        for i, heading in enumerate(candidates)
    ]
    sections, unmatched = _cut_sections(lines, candidate_headings, chapter_end_page)

    return BuildBlocksResult(chapter_title=chapter.title, sections=sections, unmatched_headings=unmatched)


def _cut_sections(
    lines: list[Line],
    candidates: list[tuple[str, int, float, int, bool, int]],
    chapter_end_page: int,
) -> tuple[list[Section], list[str]]:
    """Shared by build_blocks (bookmark-matched headings) and
    build_blocks_from_font_headings (font-size-detected headings, used when there
    are no usable bookmarks — see section_source="running_head" below). Once a
    caller has resolved where each candidate heading actually starts in the line
    stream as (title, page, top, level, matched_by_text, source_index) tuples in
    reading order, this decides which candidates get their own Section: only ones
    with real body text before the next heading (see build_blocks' module-level
    comment above for why a fixed depth doesn't work instead).
    """
    sections: list[Section] = []
    unmatched: list[str] = []

    for i, (title, page_start, start_top, level, matched_by_text, source_index) in enumerate(candidates):
        page_end, end_top = (
            (candidates[i + 1][1], candidates[i + 1][2]) if i + 1 < len(candidates) else (chapter_end_page, -1.0)
        )

        section_lines = [
            l
            for l in lines
            if (l.page, l.top) > (page_start, start_top) and (l.page, l.top) < (page_end, end_top)
        ]

        if not section_lines:
            continue  # pure container heading — no section of its own, keep descending

        if not matched_by_text:
            unmatched.append(title)

        sections.append(
            Section(
                title=title,
                level=level,
                page_start=page_start,
                page_end=page_end,
                lines=section_lines,
                matched_by_text=matched_by_text,
                source_bookmark_index=source_index,
                start_top=start_top,
            )
        )

    return sections, unmatched


# ---------------------------------------------------------------------------
# Multi-column reading order (section_source-independent: any profile with
# layout.columns > 1 needs this before build_blocks/build_blocks_from_font_headings
# sees the lines, regardless of which section-cutting strategy it uses).
# ---------------------------------------------------------------------------

MIN_COLUMN_GAP_PT = 50.0  # a real column gutter is hundreds of pt wide; ordinary
# paragraph-indent/bullet variation within one column is a few pt to a few tens of
# pt — this threshold only needs to sit between those two scales, not be exact.
_COLUMN_OFFSET_PT = 100_000.0  # far larger than any real page height, so "column 1"
# lines always sort after every "column 0" line on the same page once top is
# rewritten to column * _COLUMN_OFFSET_PT + top.


def detect_column_count(lines: list[Line]) -> tuple[int, float | None]:
    """(columns, boundary_x0) — 2 columns and the x0 midpoint of the widest gap in
    the document's x0 distribution if that gap clears MIN_COLUMN_GAP_PT, else
    (1, None). Two-column detection only (see docs/HANDOVER.md 2025 Subaru
    supplement finding); three-or-more-column manuals are out of scope until a real
    one shows up. Computed once over the whole document, not per page — a printed
    manual's column boundary doesn't move page to page.
    """
    xs = sorted(l.x0 for l in lines)
    if len(xs) < 2:
        return 1, None
    gap, idx = max((xs[i + 1] - xs[i], i) for i in range(len(xs) - 1))
    if gap < MIN_COLUMN_GAP_PT:
        return 1, None
    return 2, (xs[idx] + xs[idx + 1]) / 2


def order_by_columns(lines: list[Line], columns: int) -> list[Line]:
    """Rewrite each Line's `top` into a reading-order key AND return the lines
    sorted by (page, new top), so every caller — whether it only compares
    (page, top) tuples (build_blocks' section-window logic, filter_page_furniture's
    boundary check) or actually walks the list in order (spec_building._split_lines'
    adjacent-line paragraph grouping) — sees correct column-major order. After this
    call `top` is a synthetic position within the page, not a physical y-coordinate:
    anything that needs the real coordinate (figure-to-section assignment against
    raw PDF image rects in use_cases.py::_extract_figures) must run against the
    original lines, before this transform — that is a known, undocumented-elsewhere
    gap for two-column manuals, deliberately not solved here (see the
    profile-derivation plan).

    Must run AFTER filter_page_furniture (which needs the real physical top to
    compare against header_boundary_pt/footer_boundary_pt) and BEFORE build_blocks.

    BUG FOUND 2026-08-28: this function computed the right synthetic `top` for
    each line but returned them in their original (raw top-to-bottom, left/right
    interleaved) order instead of sorted by that new key -- a caller doing pure
    tuple comparisons (filtering into a page/top window) got the right answer
    either way, but spec_building._split_lines walks Section.lines in sequence,
    comparing each line's top only to the PREVIOUS line's, to decide where one
    paragraph ends and the next begins. Fed the original interleaved order, it
    silently stitched a left-column sentence and an unrelated right-column
    sentence into one "requirement" row -- confirmed against the real 2025 Subaru
    supplement's Navigation chapter (user report: content reads "jumbled", not
    left-column-then-right-column). The existing column-ordering regression test
    (test_column_ordering.py) only asserted the *values* were right (all left tops
    less than all right tops), not that the returned list was actually sorted by
    them, so it didn't catch this.

    The boundary is detected separately for EACH PAGE, not once for the whole
    input. BUG FOUND 2026-08-27: a single boundary computed over an entire
    multi-page chapter is not reliable when the chapter mixes plain 2-column prose
    with other content shapes (spec tables, multi-level indentation) -- confirmed
    against the real 2025 Subaru supplement's "Bluetooth settings" chapter, whose
    aggregate x0 distribution across 12 pages had no gap wide enough to detect
    (widest was 36pt, under the 50pt threshold) even though individual pages are
    cleanly 2-column. Per-page detection also naturally handles a chapter that
    mixes single- and multi-column pages, each judged on its own.

    Drops repeating-margin-glyph noise (see drop_repeating_margin_glyphs) BEFORE
    detecting columns, not after. BUG FOUND 2026-08-28: a decorative margin
    graphic sitting further right than the page's real right-hand column (e.g.
    the "Navigation"/"System"/"7" glyphs at x0=598-609, real right column at
    x0=348-488) widens the gap on the far side of the true column gutter enough
    to beat it -- detect_column_count picks the single WIDEST x0 gap on the page,
    so with the glyphs still present it drew the boundary between the right
    column and the glyphs instead of between the left and right columns, lumping
    both real columns into one "column 0" and leaving their content interleaved
    by raw vertical position instead of properly column-major. Confirmed against
    the real 2025 Subaru supplement, page 225 (0-based 224): two independent
    numbered procedures (steps 1-4 in the left column, steps 5-8 in the right)
    came out as 6,1,7,2,3,8,4 with step 5 lost. Filtering first removes the
    x0=598-609 outliers so the widest remaining gap is the real column gutter.
    Scoped to columns > 1 only -- this phenomenon (and the fix) is confirmed
    only for a 2-column layout; applying it unconditionally regressed the
    single-column subaru_v1/outback-2026 pipeline (23->21 functions, 179->136
    requirements, caught by a manual regression check right after this was
    first written column-count-agnostic) with zero real-data evidence it was
    even needed there.
    """
    if columns <= 1:
        return lines
    lines = drop_repeating_margin_glyphs(lines)
    by_page: dict[int, list[Line]] = {}
    for l in lines:
        by_page.setdefault(l.page, []).append(l)

    out: list[Line] = []
    for page_lines in by_page.values():
        detected_columns, boundary = detect_column_count(page_lines)
        if detected_columns <= 1 or boundary is None:
            out.extend(page_lines)
            continue
        out.extend(
            replace(l, top=(0 if l.x0 < boundary else 1) * _COLUMN_OFFSET_PT + l.top)
            for l in page_lines
        )
    out.sort(key=lambda l: (l.page, l.top))
    return out


def synthetic_top_for_position(lines_on_page: list[Line], x0: float, top: float, columns: int) -> float:
    """Convert a raw (x0, top) position that never went through order_by_columns
    -- e.g. a PDF image rect's own coordinates -- into the same column-major
    reading-order key Section.start_top uses, so a figure can be compared
    against section boundaries consistently.

    BUG FOUND 2026-08-28: use_cases.py::_extract_figures assigned each figure to
    a section by comparing the figure's raw (page, top) directly against
    Section.start_top, which for a 2-column chapter is a synthetic column-major
    value (see order_by_columns), not a real coordinate -- a figure sitting in
    the RIGHT column (raw top e.g. ~200) could never satisfy `start <= pos` for
    any section whose heading is also in the right column (synthetic start_top
    ~100200), so it silently fell into whatever earlier, unrelated section's
    window it happened to satisfy instead. Confirmed against the real 2025
    Subaru supplement: the "Using Wi-Fi®" section's own figure landed on
    "Using A USB Memory Device" instead. This existed before today but was
    masked by the old font-heading sections being coarse enough to often
    "accidentally" catch the right figure anyway; today's more precise
    item-index-based sections exposed it.

    `lines_on_page` should be this page's real text lines (ideally already run
    through drop_repeating_margin_glyphs, same as order_by_columns does) so the
    detected column boundary matches what order_by_columns used when it
    originally cut these sections.
    """
    if columns <= 1:
        return top
    _detected, boundary = detect_column_count(lines_on_page)
    if boundary is None:
        return top
    return (0 if x0 < boundary else 1) * _COLUMN_OFFSET_PT + top


# ---------------------------------------------------------------------------
# section_source == "running_head": no bookmarks exist (or they're unusable print-
# production markers), so chapters are found by a short label that repeats
# verbatim across a run of consecutive pages — a side-tab/margin label, not a
# one-time running head. Confirmed against the real 2025 Subaru supplement PDF:
# "Audio" recurs on 18 consecutive pages, x-position/margin geometry not needed
# since this only looks at text repetition, which this function can check without
# ever knowing the page width.
# ---------------------------------------------------------------------------

_RUNNING_HEAD_MAX_LEN = 30
# A real chapter/section label has at least one letter; a print-production
# timestamp stamp ("20240129 80153": digits and a space only) does not. Confirmed
# necessary against the real 2025 Subaru supplement, 2026-08-27: without this,
# such stamps recur across consecutive pages just like real chapter labels do (one
# batch of the production run shares a stamp for a few pages) and swamped the
# picker with ~35 of them out of 101 total candidates. Purely structural, not
# English- or maker-specific.
_HAS_LETTER_RE = re.compile(r"[a-zA-Z]")


@dataclass
class RunningHeadChapter:
    label: str
    page_start: int  # inclusive, 0-based
    page_end: int  # exclusive, matches Section.page_end's convention


@dataclass
class ChapterClassification:
    """AI's real-chapter-title-vs-noise verdict for one RunningHeadChapter
    candidate (see application.ports.ChapterClassifier). `label` is the
    validated, possibly-renamed label -- either the candidate's own original
    label, or one of its evidence heading strings copied verbatim (see
    sample_heading_evidence) -- never freely composed text."""

    label: str
    is_real_chapter: bool
    reason: str


@dataclass
class ConfirmedChapter:
    """One human-confirmed running_head chapter: a label (possibly AI-renamed,
    always traceable to real PDF text) paired with the exact page range it was
    detected at. Two ConfirmedChapters for the same manual_id must never share a
    normalized label (enforced in UseCases.confirm_chapter_allowlist) -- that
    invariant is what lets a bare label string keep working as generate()'s
    chapter_prefix identity even when the underlying running-head margin text is
    duplicated across two structurally different chapters (see
    docs/HANDOVER.md 2026-08-27, the "BASIC OPERATION" collision)."""

    label: str
    page_start: int
    page_end: int


def detect_running_head_chapters(
    lines: list[Line], min_repeat_pages: int = 3
) -> list[RunningHeadChapter]:
    page_labels: dict[int, set[str]] = {}
    for l in lines:
        stripped = l.text.strip()
        if not stripped or stripped.endswith((".", "!", "?", ":", ";")):
            continue  # prose, not a label
        norm = _normalize(stripped)
        if not norm or len(norm) > _RUNNING_HEAD_MAX_LEN or not _HAS_LETTER_RE.search(norm):
            continue
        page_labels.setdefault(l.page, set()).add(norm)

    label_pages: dict[str, list[int]] = {}
    for page, labels in page_labels.items():
        for label in labels:
            label_pages.setdefault(label, []).append(page)

    chapters: list[RunningHeadChapter] = []
    for label, pages in label_pages.items():
        pages = sorted(pages)
        run_start = prev = pages[0]
        for p in pages[1:]:
            if p == prev + 1:
                prev = p
                continue
            if prev - run_start + 1 >= min_repeat_pages:
                chapters.append(RunningHeadChapter(label, run_start, prev + 1))
            run_start = prev = p
        if prev - run_start + 1 >= min_repeat_pages:
            chapters.append(RunningHeadChapter(label, run_start, prev + 1))

    chapters.sort(key=lambda c: c.page_start)
    return chapters


def find_running_head_chapter(
    chapters: list[RunningHeadChapter], chapter_prefix: str
) -> RunningHeadChapter | None:
    target = _normalize(chapter_prefix)
    for c in chapters:
        if _normalize(c.label) == target:
            return c
    return None


def _merge_wrapped_heading_lines(
    ordered_chapter_lines: list[Line], heading_lines: list[Line]
) -> list[Line]:
    """A heading that wraps across 2+ physical PDF lines (e.g. "REGISTERING A
    Bluetooth PHONE/" / "DEVICE FOR THE FIRST TIME", both heading-sized, confirmed
    against the real 2025 Subaru supplement) must become ONE heading, not one per
    physical line — otherwise each wrapped fragment becomes its own spurious
    section. Two heading-sized lines are considered one wrapped heading only when
    they are IMMEDIATELY adjacent in reading order (no body-sized line of the
    chapter falls between them); this deliberately does not merge two heading
    lines separated by real content, which are genuinely two different headings.
    """
    heading_positions = {(l.page, l.top) for l in heading_lines}
    merged: list[Line] = []
    i = 0
    n = len(ordered_chapter_lines)
    while i < n:
        line = ordered_chapter_lines[i]
        if (line.page, line.top) not in heading_positions:
            i += 1
            continue
        texts = [line.text]
        j = i + 1
        while j < n and (ordered_chapter_lines[j].page, ordered_chapter_lines[j].top) in heading_positions:
            texts.append(ordered_chapter_lines[j].text)
            j += 1
        merged.append(replace(line, text=" ".join(texts)))
        i = j
    return merged


_MARGIN_GLYPH_MIN_REPEAT_PAGES = 3
# Some manuals print a decorative chapter-number graphic in the outer page
# margin: fixed text sitting at the exact same (top, x0) on every page of a
# chapter, often in a much larger font than any real heading. Confirmed against
# the real 2025 Subaru supplement's Navigation chapter: "Navigation" (top=194.3,
# x0=598.7, size=44.27) / "System" (top=240.3, x0=598.7) / "7" (top=283.6,
# x0=609.2) recur at those exact coordinates on every even page from 196 to 224
# -- each was being picked up as its own spurious heading (e.g. a section titled
# just "7"), and on pages where the three lines happened to stay adjacent in
# reading order they merged into one heading, "Navigation System 7", instead.
# filter_page_furniture can't catch this: it only knows a fixed header/footer
# vertical band, and this graphic sits well inside the body band. Unlike
# detect_running_head_chapters (text-only repetition, used to find chapter
# boundaries, where real headings can legitimately recur loosely), this also
# requires the exact same position -- real content essentially never sits at
# pixel-identical coordinates on 3+ different pages, so this is a much stricter,
# lower-risk signal than a text- or length-based heuristic.


def drop_repeating_margin_glyphs(
    lines: list[Line], min_repeat_pages: int = _MARGIN_GLYPH_MIN_REPEAT_PAGES
) -> list[Line]:
    keyed: dict[tuple[float, float, str], set[int]] = {}
    for l in lines:
        norm = _normalize(l.text)
        if not norm:
            continue
        keyed.setdefault((round(l.top, 1), round(l.x0, 1), norm), set()).add(l.page)

    noise_keys = {key for key, pages in keyed.items() if len(pages) >= min_repeat_pages}
    if not noise_keys:
        return lines
    return [
        l for l in lines if (round(l.top, 1), round(l.x0, 1), _normalize(l.text)) not in noise_keys
    ]


def build_blocks_from_font_headings(
    lines: list[Line], chapter: RunningHeadChapter, size_ratio: float = 1.15
) -> BuildBlocksResult:
    """The running_head counterpart to build_blocks: since there are no bookmarks
    to text-match, a heading candidate is any line whose font size is notably
    larger than the chapter's own body-text size (its median line size). Reuses
    _cut_sections for the actual "does this heading have real content of its own"
    decision — see that function's docstring. Drops repeating-margin-glyph noise
    first (see drop_repeating_margin_glyphs) so it neither skews the body-size
    median nor leaks into real sections' content, and also excludes candidates
    with no letter at all (e.g. "1.", "3.") -- confirmed against the real 2025
    Subaru supplement: numbered-step markers inside a procedure are printed a
    couple points larger than body text (e.g. 12pt vs ~8-9pt body), clearing the
    size_ratio threshold even though they aren't real headings. Same _HAS_LETTER_RE
    signal detect_running_head_chapters already uses for the same judgment call.
    Cuts sections from ordered_chapter_lines (not the raw, possibly column-
    interleaved chapter_lines) so each Section's own lines come out in true
    column-major reading order even if a caller passes lines straight from a
    multi-column page without routing them through order_by_columns first (see
    that function's 2026-08-28 bug note) -- belt and suspenders, since
    order_by_columns is now fixed to return pre-sorted lines itself.
    """
    chapter_lines = [l for l in lines if chapter.page_start <= l.page < chapter.page_end]
    chapter_lines = drop_repeating_margin_glyphs(chapter_lines)
    sizes = [l.size for l in chapter_lines if l.size > 0]
    if not sizes:
        return BuildBlocksResult(chapter_title=chapter.label, sections=[], unmatched_headings=[])

    body_size = statistics.median(sizes)
    ordered_chapter_lines = sorted(chapter_lines, key=lambda l: (l.page, l.top))
    raw_heading_lines = sorted(
        (
            l
            for l in chapter_lines
            if l.size >= body_size * size_ratio and _HAS_LETTER_RE.search(l.text)
        ),
        key=lambda l: (l.page, l.top),
    )
    heading_lines = _merge_wrapped_heading_lines(ordered_chapter_lines, raw_heading_lines)
    candidates = [
        (l.text, l.page, l.top, 0, True, i) for i, l in enumerate(heading_lines)
    ]
    sections, unmatched = _cut_sections(ordered_chapter_lines, candidates, chapter.page_end)
    return BuildBlocksResult(chapter_title=chapter.label, sections=sections, unmatched_headings=unmatched)


_EVIDENCE_SAMPLE_CAP = 8  # bounds prompt size per candidate, see ChapterClassifier.
_EVIDENCE_SIZE_RATIO = 1.15  # same threshold build_blocks_from_font_headings uses.


def sample_heading_evidence(
    lines: list[Line],
    page_start: int,
    page_end: int,
    exclude_label: str,
    max_lines: int = _EVIDENCE_SAMPLE_CAP,
) -> list[str]:
    """Real, verbatim heading-like text found within [page_start, page_end) --
    the only text an AI chapter-relabeling decision is allowed to draw from (see
    application.ports.ChapterClassifier). Uses the exact same "bigger than this
    range's own body-text size" signal build_blocks_from_font_headings uses, plus
    the same structural noise filters detect_running_head_chapters uses (has a
    letter, not too long, not prose-punctuated) -- deliberately reusing both
    rather than inventing a third heuristic. Excludes the candidate's own
    recurring margin label (no new information) and duplicates. Returns original,
    un-normalized text, since this exact string may become the persisted chapter
    label and must stay traceable to real PDF text.
    """
    range_lines = [l for l in lines if page_start <= l.page < page_end]
    sizes = [l.size for l in range_lines if l.size > 0]
    if not sizes:
        return []
    body_size = statistics.median(sizes)
    excluded = _normalize(exclude_label)

    evidence: list[str] = []
    seen: set[str] = set()
    for l in sorted(range_lines, key=lambda l: (l.page, l.top)):
        if l.size < body_size * _EVIDENCE_SIZE_RATIO:
            continue
        stripped = l.text.strip()
        if not stripped or stripped.endswith((".", "!", "?", ":", ";")):
            continue
        norm = _normalize(stripped)
        if not norm or len(norm) > _RUNNING_HEAD_MAX_LEN or not _HAS_LETTER_RE.search(norm):
            continue
        if norm == excluded or norm in seen:
            continue
        seen.add(norm)
        evidence.append(stripped)
        if len(evidence) >= max_lines:
            break
    return evidence


# ---------------------------------------------------------------------------
# section_source == "chapter_toc": some manuals print a real table of contents
# (chapter name + start page, sometimes with a dot-leader subsection list) --
# a far more reliable structural signal than running-head margin-text repetition
# when it exists, and entirely rule-based (no AI). Confirmed against the real
# 2025 Subaru supplement, 2026-08-27: read with columns=2 (this manual's real
# profile column count), each chapter's name and start-page-number sit as two
# separate Lines at nearly the same `top` (~0.4pt apart) but different `x0`
# columns, e.g. 'Settings' and '79' -- while that chapter's own dot-leader
# subsection list ('· Phone Settings... 83 · ...') sits ~6-7pt lower, a
# genuinely different row. A shorter, page-number-free summary list ('1 Quick
# Guide', '2 Basic Function', ...) often precedes the detailed rows; it's
# ignored automatically since it has no separate page-number Line to pair with.
# ---------------------------------------------------------------------------

_TOC_HEADING_SEARCH_PAGE_LIMIT = 15  # front matter is always near the start
_TOC_HEADING_TEXTS = {"table of contents", "contents"}
_TOC_SCAN_WINDOW_PAGES = 6
_TOC_ROW_TOP_TOLERANCE_PT = 2.0  # real data: ~0.4pt within a row, ~6.7pt between rows
_TOC_MIN_CHAPTER_ROWS = 3
# Deliberately NOT _RUNNING_HEAD_MAX_LEN (30) -- that constant is tuned for
# short margin/side-tab labels. A real chapter TITLE can legitimately run
# longer (e.g. "Appendix/What To Do If/Index" is already 29 chars).
_TOC_CHAPTER_NAME_MAX_LEN = 80
_TOC_PAGE_NUM_RE = re.compile(r"^\d{1,4}$")
_TOC_SUBSECTION_RE = re.compile(r"([^\d].*?)\.{2,}\s*(\d{1,4})")
_TOC_OFFSET_CHECK_WINDOW = (-1, 2)  # pages around a computed page_start to look for its heading


@dataclass
class TocChapterCandidate:
    label: str
    page_start: int  # 0-based inclusive
    page_end: int  # 0-based exclusive
    printed_page: int  # 1-based, as printed in the TOC -- for the review file's
    # human-readable reason only, never compared/matched on.
    subsection_evidence: list[str] = field(default_factory=list)


def _cluster_toc_rows(lines: list[Line]) -> list[list[Line]]:
    """Group Lines into (page, top)-adjacent row clusters via greedy nearest-
    neighbor grouping -- NOT a round(top) dict key, which can split two Lines
    of the same real row apart purely because their fractional top values
    straddle a rounding boundary. Must run on real geometric coordinates: Lines
    straight from ManualReader.read(), never after order_by_columns (which
    rewrites `top` into a synthetic reading-order key -- see its docstring)."""
    ordered = sorted(lines, key=lambda l: (l.page, l.top))
    clusters: list[list[Line]] = []
    for l in ordered:
        if (
            clusters
            and clusters[-1][-1].page == l.page
            and l.top - clusters[-1][-1].top <= _TOC_ROW_TOP_TOLERANCE_PT
        ):
            clusters[-1].append(l)
        else:
            clusters.append([l])
    return clusters


def _is_chapter_row(cluster: list[Line]) -> tuple[str, int] | None:
    """A row is a chapter row iff it has exactly one bare page number and
    exactly one plain-text (non-dot-leader) member -- returns (name,
    printed_page) or None. A summary-list row ('1 Quick Guide', one Line, no
    separate page-number member) naturally fails this and is ignored."""
    page_nums = [l for l in cluster if _TOC_PAGE_NUM_RE.match(l.text.strip())]
    plain = [
        l
        for l in cluster
        if not _TOC_PAGE_NUM_RE.match(l.text.strip()) and ".." not in l.text
    ]
    if len(page_nums) != 1 or len(plain) != 1:
        return None
    name = plain[0].text.strip()
    if not name or len(name) > _TOC_CHAPTER_NAME_MAX_LEN or not _HAS_LETTER_RE.search(name):
        return None
    return name, int(page_nums[0].text.strip())


def _toc_offset_plausible(candidates: list[TocChapterCandidate], lines: list[Line]) -> bool:
    """Guards against a systematic page-number offset (e.g. unnumbered front
    matter before the printed page numbers begin) that monotonicity alone
    can't catch -- every printed number would still increase in order, just be
    uniformly wrong. Checks whether each chapter's own name text actually shows
    up near its computed page_start; if fewer than half do, the whole parse is
    untrustworthy."""
    if not candidates:
        return False
    found = 0
    lo, hi = _TOC_OFFSET_CHECK_WINDOW
    for c in candidates:
        target = _normalize(c.label)
        window_lines = [l for l in lines if c.page_start + lo <= l.page <= c.page_start + hi]
        if any(
            target and len(target) > 3 and (target in _normalize(l.text) or _normalize(l.text) in target)
            for l in window_lines
        ):
            found += 1
    return found * 2 >= len(candidates)


def detect_toc_chapters(lines: list[Line], page_count: int) -> list[TocChapterCandidate] | None:
    """Finds and parses this manual's own printed table of contents, if one
    exists -- entirely rule-based, no AI (see application.ports.ChapterClassifier
    for the AI-assisted alternative used when no TOC page is found). Returns
    None (never a partial/best-effort list) when no TOC heading is found, too
    few chapter rows are found, page numbers aren't monotonically increasing, or
    the offset-plausibility check fails -- callers must treat None as "this
    manual can't use section_source='chapter_toc'", not retry with a guess.
    Scope limit: only the first "table of contents"/"contents" heading found is
    used; a document with two such sections (e.g. a bound-together supplement)
    only gets the first one.
    """
    heading_page = None
    for l in lines:
        if l.page >= _TOC_HEADING_SEARCH_PAGE_LIMIT:
            continue
        if _normalize(l.text) in _TOC_HEADING_TEXTS:
            heading_page = l.page
            break
    if heading_page is None:
        return None

    window_lines = [
        l for l in lines if heading_page <= l.page < heading_page + _TOC_SCAN_WINDOW_PAGES
    ]
    clusters = _cluster_toc_rows(window_lines)

    rows: list[tuple[str, int, int]] = []  # (name, printed_page, cluster_index)
    for i, cluster in enumerate(clusters):
        hit = _is_chapter_row(cluster)
        if hit is not None:
            rows.append((hit[0], hit[1], i))

    if len(rows) < _TOC_MIN_CHAPTER_ROWS:
        return None
    if any(rows[i][1] >= rows[i + 1][1] for i in range(len(rows) - 1)):
        return None  # not monotonically increasing -- likely a mis-clustered row

    candidates: list[TocChapterCandidate] = []
    for idx, (name, printed_page, cluster_i) in enumerate(rows):
        page_start = printed_page - 1
        if idx + 1 < len(rows):
            page_end = rows[idx + 1][1] - 1
            next_cluster_i = rows[idx + 1][2]
        else:
            page_end = page_count
            next_cluster_i = len(clusters)

        evidence: list[str] = []
        for between in clusters[cluster_i + 1 : next_cluster_i]:
            for line in between:
                for name_match, _num in _TOC_SUBSECTION_RE.findall(line.text):
                    evidence.append(name_match.strip(" ·"))

        candidates.append(
            TocChapterCandidate(
                label=name,
                page_start=page_start,
                page_end=page_end,
                printed_page=printed_page,
                subsection_evidence=evidence,
            )
        )

    if not _toc_offset_plausible(candidates, lines):
        return None
    return candidates


# ---------------------------------------------------------------------------
# Item index: some chapters print their OWN local index near their first page --
# one level deeper than the manual's main table of contents (section_source==
# "chapter_toc" above), listing every function/item name in that chapter with a
# dot-leader (or similar repeated-glyph leader) to its own start page. Confirmed
# against the real 2025 Subaru supplement's Navigation chapter, printed page 195:
# two labeled groups ("Basic Operation", "Tips For The Navigation System", no
# leader/page number of their own -- just group labels, naturally excluded since
# the regex below requires a trailing page number) each listing real items like
# "Map Screen Overview" + a run of repeated leader glyphs (here a private-use
# codepoint, not a literal ".", so the pattern below only requires "some run of
# non-word non-space characters" rather than specifically dots) + "196". Unlike
# the main-document TOC (name and page number as two separate Lines matched by
# row-proximity, see above), each entry here is already ONE single Line -- the
# whole "name + leader + page number" text pdfplumber joined as one line -- so
# no row-clustering is needed, only a per-line regex.
# ---------------------------------------------------------------------------

_ITEM_INDEX_ENTRY_RE = re.compile(r"^(.+?)[^\w\s]{6,}\s*(\d{1,4})\s*$")
# 6+ leader characters distinguishes a real dot-leader run from ordinary prose
# punctuation (an ellipsis is at most 3-4 dots) -- deliberately not "." specific,
# since this manual's leader is a private-use glyph, not a literal period.
_ITEM_INDEX_MIN_ENTRIES = 5  # same spirit as _TOC_MIN_CHAPTER_ROWS: a couple of
# incidental matches could be noise, five is a real list.
_ITEM_INDEX_NAME_MAX_LEN = 80  # matches _TOC_CHAPTER_NAME_MAX_LEN's reasoning
_ITEM_INDEX_SEARCH_WINDOW_PAGES = 3  # the index sits on/near the chapter's own
# first page, not scattered through it
_ITEM_INDEX_MATCH_WINDOW = (0, 2)  # pages after an entry's own printed page to
# search for its real heading line


def detect_item_index_entries(
    lines: list[Line], chapter_page_start: int, chapter_page_end: int
) -> list[tuple[str, int]] | None:
    """(name, printed_page) pairs from a chapter's own local item index, if one
    exists near its first page -- position-agnostic (each entry is a single,
    self-contained Line, so this works equally well before or after
    order_by_columns). Returns None (never a partial guess) when fewer than
    _ITEM_INDEX_MIN_ENTRIES matching lines are found -- callers must treat that
    as "this chapter has no usable item index", not retry with less.

    Dedup key is (name, page), not name alone: the same leaf item name can
    legitimately recur under two different parent groups pointing at two
    different pages (confirmed against the real 2025 Subaru supplement --
    "Using Wi-Fi®" lists once under "Updating The Map Data Manually" -> page
    225 and again under "Updating The Map Data Automatically" -> page 226;
    deduping by name alone silently dropped the second, real, distinct section).
    """
    window_end = min(chapter_page_start + _ITEM_INDEX_SEARCH_WINDOW_PAGES, chapter_page_end)
    window_lines = [l for l in lines if chapter_page_start <= l.page < window_end]

    seen: set[tuple[str, int]] = set()
    entries: list[tuple[str, int]] = []
    for l in window_lines:
        m = _ITEM_INDEX_ENTRY_RE.match(l.text.strip())
        if not m:
            continue
        name = m.group(1).strip(" ·")
        if not name or len(name) > _ITEM_INDEX_NAME_MAX_LEN or not _HAS_LETTER_RE.search(name):
            continue
        norm = _normalize(name)
        page = int(m.group(2))
        if not norm or (norm, page) in seen:
            continue
        seen.add((norm, page))
        entries.append((name, page))

    if len(entries) < _ITEM_INDEX_MIN_ENTRIES:
        return None
    return entries


def build_blocks_from_item_index(
    lines: list[Line], chapter: RunningHeadChapter, entries: list[tuple[str, int]]
) -> BuildBlocksResult | None:
    """The item-index counterpart to build_blocks_from_font_headings: instead of
    guessing headings from font size, each entry's name is text-matched (same
    _find_line_for_heading logic build_blocks already uses for bookmark titles)
    against the real body line near its own printed page, giving an exact
    (page, top) heading position instead of a guess. `lines` must already be
    column-ordered (see order_by_columns) so a matched line's `top` is in the
    same synthetic reading-order space _cut_sections compares against.

    Returns None -- not a partial result -- if fewer than half the entries can
    be text-matched (same bar detect_toc_chapters' offset-plausibility check
    uses): callers must fall back to build_blocks_from_font_headings rather than
    trust an index whose page numbers don't actually line up with this PDF's
    real content.
    """
    chapter_lines = [l for l in lines if chapter.page_start <= l.page < chapter.page_end]
    chapter_lines = drop_repeating_margin_glyphs(chapter_lines)

    sizes = [l.size for l in chapter_lines if l.size > 0]
    # Same size_ratio build_blocks_from_font_headings uses -- gates the prefix/
    # suffix fallback match (see _find_exact_line_for_heading) on the candidate
    # line actually looking like a heading, not just any line containing the
    # entry's name as a substring.
    min_heading_size = statistics.median(sizes) * 1.15 if sizes else None

    lo, hi = _ITEM_INDEX_MATCH_WINDOW
    resolved: list[tuple[str, int, float, bool]] = []
    matched_count = 0
    for name, printed_page in entries:
        guess_page = printed_page - 1  # printed pages are 1-based, Line.page is 0-based
        candidate_lines = [l for l in chapter_lines if guess_page + lo <= l.page <= guess_page + hi]
        matched_line = _find_exact_line_for_heading(name, candidate_lines, min_heading_size)
        if matched_line is not None:
            resolved.append((name, matched_line.page, matched_line.top, True))
            matched_count += 1
        else:
            resolved.append((name, guess_page, -1.0, False))

    if matched_count * 2 < len(resolved):
        return None

    resolved.sort(key=lambda e: (e[1], e[2]))
    candidates = [
        (name, page, top, 0, matched_by_text, i)
        for i, (name, page, top, matched_by_text) in enumerate(resolved)
    ]
    sections, unmatched = _cut_sections(chapter_lines, candidates, chapter.page_end)
    return BuildBlocksResult(chapter_title=chapter.label, sections=sections, unmatched_headings=unmatched)
