"""Figure-region geometry. Pure rect math — no PDF rendering here (that is
infrastructure's job, see PdfiumFigureRenderer). Wired up in full during the figures
phase; the merge primitive lives here now so later phases don't have to touch domain
layering rules.
"""
from __future__ import annotations

from domain.manual_parsing import Line

Rect = tuple[float, float, float, float]  # (x0, top, x1, bottom)


def _close_or_overlapping(a: Rect, b: Rect, distance_pt: float) -> bool:
    ax0, atop, ax1, abottom = a
    bx0, btop, bx1, bbottom = b
    gap_x = max(bx0 - ax1, ax0 - bx1, 0.0)
    gap_y = max(btop - abottom, atop - bbottom, 0.0)
    return gap_x <= distance_pt and gap_y <= distance_pt


def merge_rects(rects: list[Rect], distance_pt: float = 3.0) -> list[Rect]:
    """Combine rects into figures BEFORE any size-based filtering.

    Order matters: filtering by size first (as an earlier attempt at this app did)
    permanently loses any figure that happens to be built from many small fragments
    (Honda's 22-fragment figures disappear entirely); merging first keeps them
    findable. See ARCHITECTURE.md "図の扱い" 2.
    """
    merged = [r for r in rects]
    changed = True
    while changed:
        changed = False
        result: list[Rect] = []
        used = [False] * len(merged)
        for i, a in enumerate(merged):
            if used[i]:
                continue
            cur = a
            for j in range(i + 1, len(merged)):
                if used[j]:
                    continue
                b = merged[j]
                if _close_or_overlapping(cur, b, distance_pt):
                    cur = (
                        min(cur[0], b[0]),
                        min(cur[1], b[1]),
                        max(cur[2], b[2]),
                        max(cur[3], b[3]),
                    )
                    used[j] = True
                    changed = True
            result.append(cur)
        merged = result
    return merged


def is_figure_sized(rect: Rect, min_width_pt: float, min_height_pt: float) -> bool:
    x0, top, x1, bottom = rect
    return (x1 - x0) >= min_width_pt and (bottom - top) >= min_height_pt


def caption_for(rect: Rect, page: int, lines: list[Line], column_margin_pt: float = 20.0) -> Line | None:
    """The nearest text line to a figure, as a stand-in caption — the source PDFs
    have no real figure captions (confirmed against the original app's own output,
    which does the same thing: see docs/SPECIFICATION.md "figures.caption_for | 同じ段
    の一番近い行を手がかりに採る", i.e. "the nearest line in the same column").

    Column match is the primary filter, not a tiebreaker: a line's `top` can fall
    inside the rect's own vertical span (vertical distance 0) purely because a manual
    page has two side-by-side columns and an unrelated column's line happens to sit
    level with the figure — confirmed directly against a real Subaru case,
    2026-08-26, where a lone legend digit "5" in a callout column ~320pt to the right
    of the figure won on vertical distance alone (0) over "Select to change audio
    modes.", a line directly below the figure in the *same* column (x0 within
    column_margin_pt of the rect) that vertical distance alone ranked worse.
    Restricting to same-column candidates first, and falling back to the full page
    only when no line shares the figure's column, avoids that.

    Lines of 2 characters or less are excluded outright, in both passes — confirmed
    directly, 2026-08-26: a lone "1" sits at the exact same (page-relative)
    coordinates on 8 different Subaru pages, a page-decoration element (not body
    text — it plays no role in any paragraph on those pages) that happened to fall
    inside 3 different figures' vertical span and win as their "caption" purely on
    that coincidence. A caption this short is useless even on the rare chance it
    were real body text, so excluding it outright is strictly better than trying to
    tell "real" and "furniture" apart by pattern.
    """
    x0, top, x1, bottom = rect
    page_lines = [l for l in lines if l.page == page and len(l.text.strip()) > 2]
    if not page_lines:
        return None
    same_column = [l for l in page_lines if x0 - column_margin_pt <= l.x0 <= x1 + column_margin_pt]
    candidates = same_column or page_lines

    def distance(l: Line) -> tuple[float, float]:
        if l.top < top:
            vertical = top - l.top
        elif l.top > bottom:
            vertical = l.top - bottom
        else:
            vertical = 0.0
        return vertical, abs(l.x0 - x0)

    return min(candidates, key=distance)
