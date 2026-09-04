"""Figure-region geometry. Pure rect math — no PDF rendering here (that is
infrastructure's job, see PdfiumFigureRenderer). Wired up in full during the figures
phase; the merge primitive lives here now so later phases don't have to touch domain
layering rules.
"""
from __future__ import annotations

import re
from dataclasses import replace

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


def is_full_bleed_placement(rect: Rect) -> bool:
    """A rect that starts past the page's own left or top edge (negative
    coordinate) is deliberate full-bleed cover/divider art, not a screen
    illustration -- confirmed against the real Honda Pilot PDF, 2026-09-02: a
    696x260.9pt chapter-divider photo (a real, high-resolution embedded image,
    not a domain.figures.is_stretched_fill case -- ~200 effective dpi) sits at
    x0=-11.1pt on 8 of the manual's 9 chapter-opener pages, identically. A real
    screen-illustration figure is placed within the page's printed margins and
    would never have a negative coordinate, so no page-size lookup is needed to
    tell them apart. Left uncaught, this single outlier still drags the
    auto-derived figure_min_width_pt up to ~517pt even after stretched fills
    are excluded, since it is real (high-dpi) and passes that filter."""
    x0, top, x1, bottom = rect
    return x0 < 0 or top < 0


_BARE_URL_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)


def is_qr_code_caption(caption_text: str | None) -> bool:
    """A figure whose nearest-line "caption" is nothing but a bare URL is a
    printed QR code (a marketing insert linking to that URL), not a real screen
    illustration -- confirmed against a real Subaru case, 2026-08-31: two small
    (57x57pt) images captioned exactly "https://www.mysubaru.com/connect.html"
    and ".ca/connect.html" respectively, which the original app's own output
    for this manual does not include as figures at all. A QR code has no
    on-screen icons/symbols to transcribe, so it doesn't belong in the Screen
    elements review either way -- filtered at extraction, not just hidden from
    one screen, so figure counts everywhere (published Markdown included) match.
    """
    return bool(caption_text and _BARE_URL_RE.match(caption_text))


def is_stretched_fill(
    native_width_px: int | None,
    native_height_px: int | None,
    placed_width_pt: float,
    placed_height_pt: float,
    min_dpi: float = 10.0,
) -> bool:
    """A background/text box painted by stretching a tiny (often literally 1x1)
    source image across a large placed area is not a figure, no matter how big
    its placed rect is -- confirmed against the real Honda Pilot PDF, 2026-09-02:
    a 194x336pt rect that survived every size-based filter (bigger than every
    real figure on its own page) turned out to be a 1x1px image at ~0.3
    effective DPI, painting a body-text background box. This is exactly the
    same defect the original app (OnlineManualSpecTranslator) hit and fixed on
    this same PDF -- see its docs/ARCHITECTURE.md "図の扱い" 2: a stretched fill
    sits at ~0.4dpi, a real figure or inline icon at 130dpi or higher, three
    orders of magnitude apart. Maker/profile-independent (unlike
    figure_min_width/height_pt), so this applies before any profile-derived
    size threshold, not instead of it.
    """
    if not native_width_px or not native_height_px or placed_width_pt <= 0 or placed_height_pt <= 0:
        return False
    dpi_w = native_width_px / placed_width_pt * 72
    dpi_h = native_height_px / placed_height_pt * 72
    return dpi_w < min_dpi and dpi_h < min_dpi


def caption_for(
    rect: Rect, page: int, lines: list[Line], column_margin_pt: float = 20.0,
    heading_prefixes: tuple[str, ...] = (),
) -> Line | None:
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

    `heading_prefixes` (from LayoutConfig.heading_prefixes, e.g. Honda's "■") is
    tried as a same-column tiebreaker BEFORE plain distance: a heading-prefixed
    line always wins over a non-heading one, closest-first among each group.
    Confirmed real, Honda CR-V 2026, 2026-09-04: a real screenshot's own printed
    label ("■Phone menu screen", 30pt above the image) lost to an unrelated
    numbered step ("3.Select Menu.") purely because that step's own `top` fell
    INSIDE the image's vertical span (vertical distance 0, same column as the
    image, tied for "closest" against everything else on the page) -- a step
    list running down the page alongside a screenshot will always coincide with
    the screenshot's height this way, but that doesn't make any one step
    "about" the image the way its own printed label is. Reported directly by a
    user reading real generated output. Default empty tuple preserves every
    profile without heading_prefixes (most manuals, including every confirmed
    Subaru case above) exactly as before -- this tiebreaker can never change
    the result unless a heading-prefixed candidate actually exists.

    A winning heading-prefixed line that itself wraps across 2+ physical PDF
    lines is merged forward into one caption (see _merge_wrapped_caption below)
    -- confirmed real, same session: "■To pair a cell phone (when there is no"
    came back truncated, missing its own wrapped continuation "phone paired to
    the system) Phone Pairing Tips:" on the very next physical line. Scoped to
    the heading-prefixed case only (not every plain-sentence caption) since
    that is the confirmed real pattern; a plain sentence winning on distance
    alone already reads as a complete phrase in every case checked so far
    (matches the original app's own equally "rough" sentence-as-caption style,
    see docs/ARCHITECTURE.md "19.").
    """
    x0, top, x1, bottom = rect
    page_lines = [l for l in lines if l.page == page and len(l.text.strip()) > 2]
    if not page_lines:
        return None
    same_column = [l for l in page_lines if x0 - column_margin_pt <= l.x0 <= x1 + column_margin_pt]
    candidates = same_column or page_lines

    def is_heading_line(l: Line) -> bool:
        return bool(heading_prefixes) and l.text.startswith(heading_prefixes)

    def distance(l: Line) -> tuple[bool, float, float]:
        if l.top < top:
            vertical = top - l.top
        elif l.top > bottom:
            vertical = l.top - bottom
        else:
            vertical = 0.0
        return not is_heading_line(l), vertical, abs(l.x0 - x0)

    best = min(candidates, key=distance)
    if is_heading_line(best):
        best = _merge_wrapped_caption(best, page_lines)
    return best


_CAPTION_WRAP_GAP_PT = 15.0  # same threshold spec_building._PARAGRAPH_GAP_PT
# uses for the identical "does this line continue the previous one" judgment
# -- a wrapped heading's own two physical lines sit one ordinary line-height
# apart (confirmed real, Honda CR-V 2026: 10pt), well under a real paragraph
# break.
_CAPTION_SENTENCE_END_RE = re.compile(r"[.!?:]\s*$")
# A numbered procedure step ("1.Press the button.") sitting just below a
# wrapped heading at a small vertical gap must NOT be swallowed as if it were
# the heading's own continuation -- confirmed real, same session: without this
# exclusion "■Phone menu screen" (a genuinely complete 3-word label, no
# terminal punctuation of its own) absorbed the very next step, "1.Press the
# button.", into one caption. Same shape spec_building._NUMBERED_STEP matches.
_CAPTION_STEP_START_RE = re.compile(r"^\s*\d{1,2}[.)]")
_CAPTION_WRAP_X0_TOLERANCE_PT = 40.0  # a wrapped heading's continuation can sit
# at a slightly different x0 than its own first line (e.g. a hanging indent
# under a bullet/number, confirmed real Honda CR-V 2026: 177.2 -> 187.1, 9.9pt)
# but never anywhere near as far as a genuinely different column/zone on the
# same page (confirmed real, same PDF: a real unrelated zone sits 337pt away).
# Restricting candidates to this range BEFORE sorting by top also stops a
# same-top-ish off-column line from being picked as "next in reading order"
# ahead of the real, same-zone continuation, which raw top-only ordering
# cannot tell apart on its own.


def _merge_wrapped_caption(best: Line, page_lines: list[Line]) -> Line:
    """A caption-worthy heading can wrap across 2+ physical PDF lines just like
    any other heading (see manual_parsing._merge_wrapped_heading_lines) --
    caption_for only ever looks at ONE line's text, so a wrapped one came back
    truncated at the first physical line. Merges forward, in reading order,
    while the accumulated text doesn't yet end in sentence-terminal
    punctuation, the next line is close enough vertically to be the same
    wrapped run (not a new paragraph) AND close enough horizontally to be the
    same zone (not a different column happening to sit at a similar height),
    that next line doesn't itself start a new numbered step, AND that next
    line starts with a lowercase letter -- the same signal spec_building.
    _join_paragraph_lines already uses to tell a genuine mid-sentence wrap
    from the start of a new sentence. The lowercase check is required,
    confirmed real, same session: "■To make a call using the imported
    phonebook" (a complete heading with no terminal punctuation of its own)
    was wrongly absorbing the ENTIRE next paragraph ("When your phone is
    paired, ...") without it -- that continuation starts with a capital "W", a
    new sentence, not a wrapped fragment of the heading. The x0 check is
    required too, confirmed real, same session: without it, a short heading
    and an unrelated light-weight sentence from a genuinely different zone of
    the page (confirmed 337pt away) that happen to land at a near-identical
    `top` and start with a lowercase letter were wrongly merged back
    together -- the exact cross-zone fusion this whole feature exists to
    prevent, just reintroduced at the merge step instead of the initial
    candidate-selection step."""
    same_zone = [
        l
        for l in page_lines
        if l.page == best.page and abs(l.x0 - best.x0) <= _CAPTION_WRAP_X0_TOLERANCE_PT
    ]
    ordered = sorted(same_zone, key=lambda l: l.top)
    idx = next(i for i, l in enumerate(ordered) if l is best)
    texts = [best.text]
    prev = best
    for nxt in ordered[idx + 1 :]:
        if _CAPTION_SENTENCE_END_RE.search(" ".join(texts)):
            break
        if nxt.top - prev.top > _CAPTION_WRAP_GAP_PT:
            break
        if _CAPTION_STEP_START_RE.match(nxt.text):
            break
        stripped = nxt.text.lstrip()
        if not stripped or not stripped[0].islower():
            break
        texts.append(nxt.text)
        prev = nxt
    if len(texts) == 1:
        return best
    return replace(best, text=" ".join(texts))
