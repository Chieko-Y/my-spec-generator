"""ManualReader implementation. pdfplumber for layout-preserving text extraction,
pypdfium2 for the bookmark/outline tree (also used later for figure rendering, so one
less dependency than pulling in a third PDF library).

pypdfium2 wraps PDFium, a native C library that is not safe to call from more than
one thread. FastAPI's sync route handlers run in Starlette's threadpool
(`run_in_threadpool`), which can dispatch different requests to different worker
threads — calling PDFium from whichever thread happens to pick up the request causes
it to silently return empty/wrong results (get_toc() yielding 0 bookmarks for a real
207-bookmark PDF, observed directly against a live server) rather than raising an
error, which is what made a real generate() failure look like "the button does
nothing" from the browser. Every pypdfium2 call in this module is routed through a
single dedicated worker thread (_PDFIUM_EXECUTOR) so PDFium is always touched from the
same OS thread for the life of the process, regardless of which thread the calling
request landed on.
"""
from __future__ import annotations

import os
import re
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor

import pdfplumber
import pypdfium2 as pdfium

from domain.manual_parsing import Bookmark, Line

_LINE_TOLERANCE_PT = 3.0
_PDFIUM_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdfium")

# Manuals use a custom icon font (bullet-style markers ahead of sub-headings, e.g.
# "Phone commands", "Music commands") mapped into the Unicode Private Use Area.
# pdfplumber has no glyph for that codepoint and no other font to fall back to, so it
# extracts the raw PUA codepoint as if it were real text — pdfplumber fuses the icon
# glyph onto the following word with no space ("Phone commands"), and it then
# renders as a tofu/box character wherever the output is displayed (confirmed
# directly against the real Subaru PDF, 2026-08-26: U+F075 ahead of every one of
# "Phone/Navigation/Music/Climate/Apps/Vehicle commands" and several other
# sub-headings). It carries no transferable meaning outside that font, so it is
# stripped rather than kept.
_ICON_GLYPH_RE = re.compile(r"[\ue000-\uf8ff]")

# This manual's own printing convention quotes an on-screen UI element's name
# ("Network Connection", "Wi-Fi Security"). When that element is a bare icon
# instead of a text label, the icon glyph itself has no extractable text at
# all -- confirmed directly against the real 2026 Subaru supplement: pdfplumber
# returns 'Touch \u201c \u201d of the main menu.' (curly quotes, nothing but whitespace
# between them) straight from the PDF, with no character to strip -- this is a
# gap in the PDF's own text layer, not something _ICON_GLYPH_RE removes. Left
# alone, an empty quoted pair reads as a data-loss bug rather than "a real icon
# reference existed here, the manual just doesn't expose it as text" -- an
# empty quote pair is otherwise never legitimate prose, so replacing whatever
# sits between two quote marks with a placeholder when it's empty/whitespace is
# a safe, purely structural signal, not a guess at the icon's actual meaning.
_EMPTY_QUOTED_ICON_RE = re.compile(r'([\u201c"])\s*([\u201d"])')

# A numbered-procedure-step marker word by itself, e.g. "1." or "12." -- these
# routinely render larger/bolder than the step's own body text (a common list-
# marker typesetting convention), so they are excluded when picking the size that
# represents a whole line for heading detection (see _build_line_from_words).
_STEP_MARKER_RE = re.compile(r"^\d{1,2}\.$")


# A normal inter-word gap in flowing prose is a few pt (confirmed against real
# text on the same page as the bug this threshold fixes: 1.8-4.6pt between
# ordinary adjacent words). A gap this wide between two x0-adjacent words within
# one already Y-clustered group is a strong signal that two DIFFERENT columns/
# lanes happened to land at a similar vertical position and got merged by the
# Y-only clustering pass below -- confirmed directly against the real 2025 Subaru
# supplement PDF, 2026-08-27, two separate real cases on the same page (79): a
# lane-A word ending at x1=337.3 and a lane-B word starting at x0=365.7 (28.4pt
# gap, produced "...it is 2." with a stray step-number fused in), and a lane-A
# heading ending at x1=309.6 merged with a lane-B heading starting at x0=365.7
# (56.1pt gap). Trying to prevent this by pre-splitting the whole page's words by
# a single global x0 gap (tried first) was unreliable: a word's x0 reflects where
# IT starts, not where its line/lane starts, so a word near the end of a long
# lane-A sentence can have an x0 close to or past lane B's start -- the true
# column gutter is not reliably "the widest gap in the whole page's word x0
# values." Checking the gap only between ADJACENT words already inside one
# candidate line avoids that: the two false-positive-prone quantities (a whole
# page's noisy word-x0 spread, or a whole document's occasional outlier lines)
# never enter the comparison at all.
_MAX_INTRA_LINE_GAP_PT = 15.0


def _split_cross_column_cluster(ws_sorted: list[dict]) -> list[list[dict]]:
    if len(ws_sorted) < 2:
        return [ws_sorted]
    groups: list[list[dict]] = [[ws_sorted[0]]]
    for prev, cur in zip(ws_sorted, ws_sorted[1:]):
        if cur["x0"] - prev["x1"] > _MAX_INTRA_LINE_GAP_PT:
            groups.append([cur])
        else:
            groups[-1].append(cur)
    return groups


def _build_line_from_words(ws_sorted: list[dict], page_index: int) -> Line | None:
    cleaned = [(_ICON_GLYPH_RE.sub("", w["text"]), w) for w in ws_sorted]
    cleaned = [(t, w) for t, w in cleaned if t]
    if not cleaned:
        return None
    text = " ".join(t for t, _ in cleaned).strip()
    text = _EMPTY_QUOTED_ICON_RE.sub(r"\1[icon]\2", text)
    if not text:
        return None
    # Median across every word in the line, not just the first (leftmost) word's
    # size. BUG FOUND 2026-08-27: using only the first word's size made a numbered
    # procedure step ("1. Turn the Bluetooth connection setting of your Bluetooth
    # phone/device on.") look like a section heading to
    # build_blocks_from_font_headings, purely because its leading "1." marker
    # renders at a larger size (12pt) than the sentence's own body-sized text
    # (9pt) -- confirmed against the real 2025 Subaru supplement PDF, page 79. A
    # median is robust to one or two such outlier marker words; using it also
    # means each PDF's own font-size fallback (Some PDFs -- confirmed the same
    # document -- expose no character-level "size" at all, pdfplumber returns the
    # key present but None rather than omitting it, so this falls back to
    # "height", the word's own bounding-box height, which is always present) is
    # applied per-word before taking the median, not just to a single word.
    #
    # A leading step-number marker ("1.", "2.", ...) is excluded from the median
    # when the line has other words: a short step ("3. Select .") can still have
    # the marker outvote 1-2 real body words even under a median (confirmed
    # against the same real page, 2026-08-27 -- "3. Select" alone still measured
    # 10.5, just above the heading threshold). If EVERY word is a marker (a lone
    # "2." split off on its own, a real residual case from imperfect column
    # splitting -- see _split_cross_column_cluster above), fall back to using it,
    # since there is nothing else to represent the line's size with.
    non_marker = [(t, w) for t, w in cleaned if not _STEP_MARKER_RE.match(t)]
    size_source = non_marker or cleaned
    word_sizes = [w.get("size") or w.get("height") or 0.0 for _, w in size_source]
    return Line(
        page=page_index,
        text=text,
        top=min(w["top"] for _, w in cleaned),
        x0=min(w["x0"] for _, w in cleaned),
        size=statistics.median(word_sizes),
    )


def _group_words_into_lines(words: list[dict], page_index: int, columns: int = 1) -> list[Line]:
    # Cluster by proximity to the first word's top in the current cluster, not by
    # rounding top/tolerance to a fixed grid. Binning put two words 1.06pt apart —
    # well inside the 3pt tolerance — into different lines because they straddled a
    # rounding boundary (423.55 -> bucket 141, 424.61 -> bucket 142), which knocked
    # the last word of one printed line ("dis-", a line-wrap hyphen) into its own
    # phantom line and left the real content reassembled out of order (confirmed
    # directly against the real Subaru PDF, 2026-08-25: "display" split into a
    # stray "dis-" line and a "play ..." line, with an unrelated sentence between
    # them once the paragraph text was joined). Proximity to a fixed anchor has no
    # such boundary.
    ordered = sorted(words, key=lambda w: w["top"])
    clusters: list[list[dict]] = []
    for w in ordered:
        if clusters and abs(w["top"] - clusters[-1][0]["top"]) <= _LINE_TOLERANCE_PT:
            clusters[-1].append(w)
        else:
            clusters.append([w])

    lines: list[Line] = []
    for ws in clusters:
        ws_sorted = sorted(ws, key=lambda w: w["x0"])
        # columns > 1 only: a Y-cluster can still legitimately contain two
        # different columns' words (see _MAX_INTRA_LINE_GAP_PT above) -- gated on
        # columns so the well-tested single-column pipeline's behavior is
        # unchanged (a genuinely wide gap within one real single-column line, e.g.
        # a table row, should NOT be split there).
        groups = _split_cross_column_cluster(ws_sorted) if columns > 1 else [ws_sorted]
        for group in groups:
            line = _build_line_from_words(group, page_index)
            if line is not None:
                lines.append(line)
    return lines


def _read_bookmarks_unsafe(pdf_path: str) -> list[Bookmark]:
    """Not thread-safe on its own — call only via _read_bookmarks(), which pins this
    to the dedicated PDFium thread."""
    doc = pdfium.PdfDocument(pdf_path)
    try:
        out: list[Bookmark] = []
        for bm in doc.get_toc():
            dest = bm.get_dest()
            page_index = dest.get_index() if dest is not None else None
            if page_index is None:
                continue
            out.append(Bookmark(title=bm.get_title().strip(), level=bm.level, page_index=page_index))
        return out
    finally:
        doc.close()


def _read_bookmarks(pdf_path: str) -> list[Bookmark]:
    return _PDFIUM_EXECUTOR.submit(_read_bookmarks_unsafe, pdf_path).result()


class PdfManualReader:
    """`read()` memoizes its own (expensive) full-document scan per process --
    see its own docstring below for why."""

    def __init__(self) -> None:
        self._read_cache: dict[tuple[str, int, float], tuple[list[Line], list[Bookmark]]] = {}
        self._read_cache_lock = threading.Lock()

    def read(self, pdf_path: str, columns: int = 1) -> tuple[list[Line], list[Bookmark]]:
        """generate() calls this once per chapter, but it always re-scans the
        WHOLE document regardless of which chapter was asked for -- confirmed
        the dominant cost for a large manual (Honda Pilot, 700+ pages: 1-2
        minutes per call, see feedback memory "diagnose hang via CPU"),
        observed real 2026-09-01: a second chapter of the SAME manual paid
        the full re-read again with nothing to show for the first one.

        Cached in-process, keyed by (pdf_path, columns, mtime) -- mtime rides
        along so replacing the PDF on disk under the same path (a corrected
        upload) invalidates the cache automatically rather than silently
        serving stale content. Safe to share the returned Line/Bookmark
        objects across callers: nothing downstream mutates them in place
        (every transform, e.g. domain.manual_parsing.order_by_columns, uses
        dataclasses.replace to produce new objects) -- confirmed by grepping
        the whole src/ tree for any `.top =`/`.text =`/`.x0 =`/`.page =`
        assignment before relying on this, 2026-09-03.

        Unbounded for now -- deliberately not an LRU or similar: this
        process only ever sees a handful of distinct manuals across its
        lifetime today, so eviction would be premature engineering. Revisit
        if the number of manuals actively cycled through in one running
        server grows enough for memory to matter.
        """
        cache_key = (pdf_path, columns, os.path.getmtime(pdf_path))
        with self._read_cache_lock:
            cached = self._read_cache.get(cache_key)
        if cached is not None:
            return cached
        lines: list[Line] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_index, page in enumerate(pdf.pages):
                words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
                lines.extend(_group_words_into_lines(words, page_index, columns))
        bookmarks = _read_bookmarks(pdf_path)
        result = (lines, bookmarks)
        with self._read_cache_lock:
            self._read_cache[cache_key] = result
        return result

    def read_image_rects(
        self, pdf_path: str, page_start: int = 0, page_end: int | None = None
    ) -> dict[int, list[tuple[float, float, float, float, int | None, int | None]]]:
        """page_index -> raw embedded-image bounding boxes (x0, top, x1, bottom,
        native_width_px, native_height_px), for pages in [page_start, page_end).

        Screen-illustration figures in a real owner's manual are embedded raster
        images, not vector art assembled from many small shapes — confirmed
        directly against the Subaru PDF, 2026-08-25: page.images on a page with a
        known figure returned exactly one large image whose size (312x186pt)
        matched that figure's published metadata pixel-for-point, alongside a
        handful of small (~11pt) inline icon images that are not figures at all.
        Size filtering happens later (domain.figures.is_figure_sized); this just
        collects candidates.

        The native pixel size (pdfplumber's "srcsize") rides along too: a real
        figure/icon and a stretched-fill background box can be the same placed
        size in points, but not the same *effective resolution* — see
        domain.figures.is_stretched_fill, confirmed against the Honda Pilot PDF,
        2026-09-02.

        page_start/page_end default to the whole document, but a caller generating
        one chapter should always pass its actual page range: scanning every page
        of a 140-page manual for one 20-page chapter's figures was the dominant
        cost in a generate() that otherwise finished in seconds (observed directly,
        2026-08-25 — phone chapter, 9 real figures, over 2 minutes end to end).
        """
        out: dict[int, list[tuple[float, float, float, float, int | None, int | None]]] = {}
        with pdfplumber.open(pdf_path) as pdf:
            pages = pdf.pages[page_start:page_end] if page_end is not None else pdf.pages[page_start:]
            for offset, page in enumerate(pages):
                page_index = page_start + offset
                rects = []
                for im in page.images:
                    native_w, native_h = im.get("srcsize") or (None, None)
                    rects.append((im["x0"], im["top"], im["x1"], im["bottom"], native_w, native_h))
                if rects:
                    out[page_index] = rects
        return out

    def read_running_head_breadcrumbs(
        self,
        pdf_path: str,
        page_start: int,
        page_end: int,
        header_boundary_pt: float,
        separator_font_hint: str,
    ) -> dict[int, list[str]]:
        """page_index -> breadcrumb levels (e.g. ["Audio System Basic Operation",
        "Display Setup"]) read from that page's own header-band running head.

        Some manuals print a "▶▶Area▶Function"-shaped breadcrumb in the page
        margin of every content page. The arrow glyphs are drawn by a dedicated
        symbol font that reuses a Latin code point (confirmed real, Honda Pilot,
        2026-09-02: both arrows decode as the letter "u", indistinguishable by
        character code alone from a real "u" inside a word like "Audio" -- but
        always rendered in a different font, `separator_font_hint` a substring of
        it (e.g. "HONDACommon"), never the surrounding body font. Splitting on
        "u"-in-that-font (not on "u" generally, which would butcher every real
        word containing the letter) recovers the levels cleanly.

        The header band can hold more than one physical line (confirmed real,
        Honda Pilot: a DTP timestamp/filename watermark line sits above the
        breadcrumb's own line, at a different `top`) -- sorting every header-band
        character by x0 alone, ignoring which line each one is actually on,
        interleaves the two lines' characters together into garbage whenever
        their x0 ranges happen to overlap on a given page. Characters are
        grouped by (rounded) `top` first; only the LAST (bottom-most, closest to
        the body) line is used, matching this manual's own consistent stacking
        order -- the breadcrumb line isn't always the one holding a separator
        character (a page whose whole breadcrumb is just one bare Area name, no
        Function yet, has none at all), so "which line has a separator" can't be
        the selector.
        """
        out: dict[int, list[str]] = {}
        with pdfplumber.open(pdf_path) as pdf:
            for page_index in range(page_start, min(page_end, len(pdf.pages))):
                page = pdf.pages[page_index]
                lines_by_top: dict[float, list] = {}
                for c in page.chars:
                    if c["top"] < header_boundary_pt:
                        # Rounding to 1 decimal wrongly split one real visual line
                        # into two groups (confirmed real, Honda Pilot: the same
                        # breadcrumb line's own glyphs land at top=70.1 and
                        # top=70.3 -- different glyphs' baselines differ by a
                        # fraction of a point even within one line). A whole
                        # point is coarse enough to always merge those, still far
                        # finer than the ~30pt gap between genuinely different
                        # header-band lines.
                        lines_by_top.setdefault(round(c["top"]), []).append(c)
                if not lines_by_top:
                    continue
                breadcrumb_line = lines_by_top[max(lines_by_top)]
                chars = sorted(breadcrumb_line, key=lambda c: c["x0"])
                # A page whose whole breadcrumb is a single bare Area name (no
                # Function reached yet) has NO separator character at all on this
                # line -- confirmed real, Honda Pilot p.265 ("Audio System" alone,
                # zero arrows). Separators are pure delimiters here, not a
                # "collection hasn't started yet" gate: with zero of them the
                # whole line becomes one segment; with two, three parts split
                # into two segments (an empty first split, from two adjacent
                # separators, is silently dropped by the `if current.strip()`
                # checks below).
                segments: list[str] = []
                current = ""
                for c in chars:
                    if c["text"] == "u" and separator_font_hint in c["fontname"]:
                        if current.strip():
                            segments.append(current.strip())
                        current = ""
                    else:
                        current += c["text"]
                if current.strip():
                    segments.append(current.strip())
                if segments:
                    out[page_index] = segments
        return out

    def outline_preview(self, pdf_path: str) -> tuple[int, list[Bookmark]]:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
        bookmarks = _read_bookmarks(pdf_path)
        return page_count, bookmarks

    def cover_text(self, pdf_path: str) -> str:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return ""
            return pdf.pages[0].extract_text() or ""
