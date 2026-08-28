"""Rule-based, from-scratch layout derivation for a brand-new PDF that no existing
Profile fits (profile_fitness.score_fitness said no). Pure geometric/statistical
signals over already-read Line/Bookmark/image-rect data -- no AI. Output is a draft
only: a JSON-serializable dict matching config/profiles/*.json's "layout" shape,
plus a human-readable report of what was detected and why, for a person to review
before it's saved as a real profile file. See docs/HANDOVER.md 2026-08-26 for the
design discussion this implements.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .manual_parsing import (
    Bookmark,
    Line,
    RunningHeadChapter,
    TocChapterCandidate,
    detect_column_count,
    detect_running_head_chapters,
    detect_toc_chapters,
)
from .profile_fitness import bookmark_depth_ok

_MIN_RUNNING_HEAD_COVERAGE = 0.3  # running_head chapters must cover at least this
# fraction of the document's pages to be trusted as the section-cutting strategy,
# not a handful of coincidental short-line repeats.
_HEADER_FOOTER_BAND_PT = 5.0  # lines within this many pt of each other's top count
# as "the same vertical position" across pages, for header/footer detection.
_MIN_HEADER_FOOTER_REPEATS = 5
# A real running head/footer sits on nearly every page of the whole document, not
# just a handful of times -- a fixed count alone let ordinary instructional
# phrasing that happens to repeat at a similar height a few times outrank the real
# header/footer band (confirmed against the real Subaru 2026 PDF: without this
# ratio, the detector proposed 355.0/430.0pt against a hand-verified 165.0/685.0pt).
_MIN_HEADER_FOOTER_COVERAGE = 0.5
_FIGURE_GAP_MARGIN_PT = 2.0


@dataclass
class DerivedLayoutReport:
    columns: int
    section_source: str  # "bookmarks" | "chapter_toc" | "running_head" | "undetermined"
    running_head_chapters: list[RunningHeadChapter] = field(default_factory=list)
    toc_chapters: list[TocChapterCandidate] = field(default_factory=list)
    header_boundary_pt: float = 0.0
    footer_boundary_pt: float | None = None
    figure_min_width_pt: float | None = None
    figure_min_height_pt: float | None = None
    notes: list[str] = field(default_factory=list)

    def as_profile_layout_dict(self) -> dict:
        """Matches config/profiles/*.json's "layout" object shape directly."""
        d: dict = {"columns": self.columns, "section_source": self.section_source}
        if self.header_boundary_pt:
            d["header_boundary_pt"] = self.header_boundary_pt
        if self.footer_boundary_pt is not None:
            d["footer_boundary_pt"] = self.footer_boundary_pt
        if self.figure_min_width_pt is not None:
            d["figure_min_width_pt"] = self.figure_min_width_pt
        if self.figure_min_height_pt is not None:
            d["figure_min_height_pt"] = self.figure_min_height_pt
        return d


def _detect_header_footer(lines: list[Line]) -> tuple[float, float | None, list[str]]:
    """Running-header/footer detection by POSITION only, not exact text: a short
    line recurring at the same vertical band across most pages. Deliberately does
    not require the same text -- confirmed necessary against the real Subaru 2026
    PDF, whose running head is a rotating per-chapter title ("Audio operation" on
    Audio's pages, "Phone operation" on Phone's pages, etc.): the position is fixed
    but the string changes every chapter, so no single string ever repeats across a
    useful fraction of the whole document. Distinct from
    detect_running_head_chapters (which needs the SAME text across CONSECUTIVE
    pages to mark chapter boundaries) -- this needs the same position across the
    WHOLE document instead, regardless of the words used or consecutiveness.
    """
    notes: list[str] = []
    total_pages = max((l.page for l in lines), default=-1) + 1
    min_repeats = max(_MIN_HEADER_FOOTER_REPEATS, int(total_pages * _MIN_HEADER_FOOTER_COVERAGE))

    buckets: dict[int, set[int]] = {}
    for l in lines:
        text = l.text.strip()
        if not text or len(text) > 60:
            continue
        band = round(l.top / _HEADER_FOOTER_BAND_PT)
        buckets.setdefault(band, set()).add(l.page)

    header_tops = sorted(
        {band * _HEADER_FOOTER_BAND_PT for band, pages in buckets.items() if len(pages) >= min_repeats}
    )
    if not header_tops:
        notes.append("no repeated header/footer text found at a consistent position")
        return 0.0, None, notes

    if len(header_tops) == 1:
        # Only one repeating band found -- treat it as a header if it sits above
        # the bulk of body text, else a footer.
        all_tops = sorted(l.top for l in lines)
        body_median = all_tops[len(all_tops) // 2] if all_tops else 0.0
        if header_tops[0] < body_median:
            boundary = header_tops[0] + _HEADER_FOOTER_BAND_PT
            notes.append(f"header boundary proposed at {boundary:.1f}pt from 1 repeated band")
            return boundary, None, notes
        boundary = header_tops[0] - _HEADER_FOOTER_BAND_PT
        notes.append(f"footer boundary proposed at {boundary:.1f}pt from 1 repeated band")
        return 0.0, boundary, notes

    # Multiple repeating bands: the header region (page-filename artifacts, chapter
    # titles) and the footer region (page numbers) are each internally close
    # together but far apart from each other -- same widest-gap idea as
    # detect_column_count, applied to vertical position instead of horizontal.
    gap, idx = max((header_tops[i + 1] - header_tops[i], i) for i in range(len(header_tops) - 1))
    top_band = header_tops[: idx + 1]
    bottom_band = header_tops[idx + 1 :]

    header_boundary = max(top_band) + _HEADER_FOOTER_BAND_PT
    footer_boundary = min(bottom_band) - _HEADER_FOOTER_BAND_PT
    notes.append(
        f"header boundary proposed at {header_boundary:.1f}pt from {len(top_band)} repeated band(s)"
    )
    notes.append(
        f"footer boundary proposed at {footer_boundary:.1f}pt from {len(bottom_band)} repeated band(s)"
    )
    return header_boundary, footer_boundary, notes


def _detect_figure_thresholds(
    image_rects: dict[int, list[tuple[float, float, float, float]]]
) -> tuple[float | None, float | None, list[str]]:
    """Icons and real screen-illustration figures cluster at very different sizes
    (confirmed against the real Subaru PDF, 2026-08-25: ~11.5pt icons vs. 100pt+
    figures) -- find the widest gap in the sorted size distribution instead of
    assuming a fixed threshold like the current hardcoded 40pt."""
    widths: list[float] = []
    heights: list[float] = []
    for rects in image_rects.values():
        for x0, top, x1, bottom in rects:
            widths.append(x1 - x0)
            heights.append(bottom - top)
    notes: list[str] = []
    if len(widths) < 4:
        notes.append("too few embedded images to detect a size threshold; keeping default")
        return None, None, notes

    def _gap_threshold(values: list[float]) -> float | None:
        vs = sorted(values)
        gap, idx = max((vs[i + 1] - vs[i], i) for i in range(len(vs) - 1))
        if gap < _FIGURE_GAP_MARGIN_PT:
            return None
        return vs[idx] + gap / 2

    w = _gap_threshold(widths)
    h = _gap_threshold(heights)
    if w is not None:
        notes.append(
            f"figure_min_width_pt proposed at {w:.1f}pt (widest gap in {len(widths)} embedded image widths)"
        )
    if h is not None:
        notes.append(
            f"figure_min_height_pt proposed at {h:.1f}pt (widest gap in {len(heights)} embedded image heights)"
        )
    return w, h, notes


def derive_layout(
    lines: list[Line],
    bookmarks: list[Bookmark],
    image_rects: dict[int, list[tuple[float, float, float, float]]] | None = None,
) -> DerivedLayoutReport:
    notes: list[str] = []

    columns, boundary = detect_column_count(lines)
    if columns > 1:
        notes.append(f"detected {columns}-column layout (x0 gap boundary at {boundary:.1f}pt)")
    else:
        notes.append("detected single-column layout")

    section_source = "undetermined"
    running_chapters: list[RunningHeadChapter] = []
    toc_chapters: list[TocChapterCandidate] = []
    total_pages = max((l.page for l in lines), default=-1) + 1
    bookmarks_ok, bookmark_reason = bookmark_depth_ok(bookmarks)
    if bookmarks_ok:
        section_source = "bookmarks"
        notes.append("bookmarks look chapter-shaped -- using section_source=bookmarks")
    else:
        notes.append(f"bookmarks not usable: {bookmark_reason}")
        # Prefer the manual's own printed table of contents over running-head
        # detection when both are available: a real TOC page gives exact,
        # unambiguous chapter boundaries straight from the document, while
        # running_head only infers boundaries from repeated margin text, which
        # can legitimately collide across two different chapters (see
        # docs/HANDOVER.md 2026-08-27, the "BASIC OPERATION" collision this
        # ordering was specifically found to sidestep). Both are AI-free.
        toc_candidates = detect_toc_chapters(lines, total_pages)
        if toc_candidates:
            section_source = "chapter_toc"
            toc_chapters = toc_candidates
            labels = [c.label for c in toc_chapters]
            notes.append(
                f"found a parseable table of contents with {len(toc_chapters)} "
                f"chapter(s): {labels}"
            )
        else:
            notes.append("no parseable table-of-contents page found")
            running_chapters = detect_running_head_chapters(lines)
            covered_pages = sum(c.page_end - c.page_start for c in running_chapters)
            coverage = covered_pages / total_pages if total_pages else 0.0
            if running_chapters and coverage >= _MIN_RUNNING_HEAD_COVERAGE:
                section_source = "running_head"
                labels = [c.label for c in running_chapters]
                notes.append(
                    f"found {len(running_chapters)} running-head chapter(s) covering "
                    f"{coverage:.0%} of pages: {labels}"
                )
            else:
                notes.append(
                    f"no reliable running-head chapters found (coverage {coverage:.0%}) -- "
                    "layout.section_source needs to be authored by hand"
                )

    header_boundary_pt, footer_boundary_pt, hf_notes = _detect_header_footer(lines)
    notes.extend(hf_notes)

    fig_w, fig_h, fig_notes = _detect_figure_thresholds(image_rects or {})
    notes.extend(fig_notes)

    return DerivedLayoutReport(
        columns=columns,
        section_source=section_source,
        running_head_chapters=running_chapters,
        toc_chapters=toc_chapters,
        header_boundary_pt=header_boundary_pt,
        footer_boundary_pt=footer_boundary_pt,
        figure_min_width_pt=fig_w,
        figure_min_height_pt=fig_h,
        notes=notes,
    )
