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


_ABOVE_WINDOW_MARGIN_PT = 70.0
# How far left/right of a wide figure's own rect a candidate ABOVE it may
# still start and count as that figure's caption -- see caption_for's
# in_above_window docstring for the real Honda CR-V case (61.9pt) this is
# sized for, and the real case (259pt away) it must still reject.
_CAPTION_GRAZE_GAP_PT = 8.0
# The smallest vertical gap that counts as a real "printed above the figure"
# caption rather than a coincidental graze of the figure's own top edge --
# see caption_for's is_above docstring for the real 2.6pt Honda CR-V graze
# this exists to reject, versus every real confirmed caption gap checked so
# far (25.6-121pt).


_SAME_LINE_FRAGMENT_MAX_GAP_PT = 100.0
# The largest horizontal gap between a lowercase-starting line and its
# same-top left-hand sibling that still counts as "one physical PDF line
# split apart by a column-detection quirk" (see is_same_line_fragment) rather
# than "two unrelated column headers that happen to share a row in a real
# multi-column grid". Confirmed real, Honda Pilot 2026 (the true split-line
# case this whole check exists for): "Select" / "or" / "to change file." are
# 3 pieces of one fractured sentence, but "or" is itself excluded from
# page_lines by the 2-character-minimum filter above, so the closest
# qualifying sibling actually checked is "Select", 71.5pt away. Confirmed
# real, Subaru Outback 2025 2026-09-08 (the false-positive this constant was
# added to reject): a 3-column grid's own two-line headings ("Adding from
# the" / "phone screen", "Bluetooth audio screen", "settings screen") share
# one `top` on their second line, 133-136pt apart -- a real column pitch,
# not a split sentence -- which wrongly excluded the true nearer half of a
# genuine 2-line caption in each of that grid's 3 columns. 100pt sits
# between the two.


def caption_for(
    rect: Rect, page: int, lines: list[Line], column_margin_pt: float = 30.0,
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

    column_margin_pt default raised 20 -> 30, 2026-09-04: real Subaru Outback
    2026 case, "Search screen" (Navigation if equipped) -- the figure's own
    rect sits at x0=144.9, and the real closest paragraph text ("...can be set
    for places where postal address is not precisely allocated.") sits at
    x0=119.1, a genuine 25.8pt gap, just outside the old 20pt margin. Excluded
    from the same-column candidate set entirely, the caption fell through to
    a same-column-but-farther, completely unrelated bullet item ("Select to
    display a list of gas stations.", describing a different icon in a
    button list on the same page) -- reported directly by a user reading real
    generated output. 30pt still leaves a wide margin below the ~320pt gap
    the original 20pt value was chosen to reject (see the "5" legend-digit
    case above), so this widening doesn't reopen that one.

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

    A "use the section/function title when the rect looks like a composite
    (merge_rects fused 2+ source rects into it)" fallback was tried and reverted,
    2026-09-09: it fixed 7 confirmed real Honda Pilot cases (a full-screen
    composite's nearest line picking one arbitrary unrelated icon label out of
    several scattered around it -- e.g. "is connected to HFL.", a fragment of
    the neighboring "Bluetooth® Indicator" icon's own description, beating the
    real "Play/Pause Icon" purely on tier) but broke several already-good CR-V
    captions when regenerated to check for regressions: real, specific, directly
    printed labels ("(Home) Button", "Left Selector Wheel") on CR-V's own
    multi-fragment composite crops got overwritten with a generic, duplicate
    section title, and two DIFFERENT figures sharing one function ended up with
    the identical, non-distinguishing caption. A merge count > 1 does not
    reliably mean "no single caption is correct" -- confirmed real, same PDF, a
    composite fused from 4 source rects can still carry one genuine, specific,
    directly-printed label for the whole crop. The real fix this project's own
    comments already point to (associate each PRE-merge rect with its own
    nearest label before merging, not after) is a bigger architectural change,
    not yet attempted -- see docs/HANDOVER.md 2026-09-09 for the full incident.
    """
    x0, top, x1, bottom = rect
    page_lines = [l for l in lines if l.page == page and len(l.text.strip()) > 2]
    if not page_lines:
        return None

    def is_heading_line(l: Line) -> bool:
        return bool(heading_prefixes) and l.text.startswith(heading_prefixes)

    # Excluding a heading-prefixed line from candidacy entirely when it's
    # printed larger than the page's own body text was tried and reverted,
    # 2026-09-09: it matches the original app's own documented caption_for
    # principle (AGENTS.md/CLAUDE.md 2026-07-30, "節見出しは候補から外す(機能
    # 名として既に出ている)") and correctly fixed a confirmed real Honda Pilot
    # false positive ("■Vehicle Information and Message from Honda Tips",
    # 10.98pt vs. the page's 9.00pt body text, beating "Notification") without
    # disturbing any of the 3 confirmed real CR-V cases that need a heading to
    # win (all printed at exactly 9.00pt, indistinguishable from body text) --
    # but regenerating CR-V to check for regressions surfaced 7 DIFFERENT
    # changes, several clearly worse (a running-head page-nav snippet or a
    # lowercase sentence fragment replacing a correct label). Removing the
    # heading that was previously winning exposes a DIFFERENT, already-latent
    # tier1-beats-tier2 problem for an unrelated candidate on the same page --
    # the same failure class as the reverted distance-cap attempt just before
    # this one. 4th confirmed case (`in_rect_x_span`, the 5-tier redesign
    # detour, composite_fallback+distance-cap, now this) of a targeted
    # caption_for change breaking CR-V's already-verified baseline -- see
    # docs/HANDOVER.md 2026-09-09 for the full incident.
    def overlaps_vertically(l: Line) -> bool:
        return top <= l.top <= bottom

    def is_above(l: Line) -> bool:
        # A real caption/header printed ABOVE a composite figure -- Honda's
        # own house style, confirmed in every real case checked so far
        # (Pilot/CR-V) -- must clear a real gap, not just graze the figure's
        # top edge: confirmed real, Honda CR-V 2026 ("Start Up"), a
        # completely unrelated right-column callout sat only 2.6pt above the
        # figure and would otherwise pass as "above" too.
        return l.top < top and (top - l.top) >= _CAPTION_GRAZE_GAP_PT

    def in_narrow_window(l: Line) -> bool:
        # Same column as the figure's own left edge -- where a real body
        # paragraph in this column actually starts.
        return abs(l.x0 - x0) <= column_margin_pt

    def in_wide_window(l: Line) -> bool:
        # Extends out to the figure's own RIGHT edge + margin, not just its
        # left, so a real screenshot's own printed step-list running down its
        # right side -- confirmed real, Honda CR-V 2026 (a numbered step list
        # beside "Phone menu screen" whose `top` falls inside the image's own
        # height) -- is still reachable even though it doesn't share the
        # figure's left-edge x0.
        return x0 - column_margin_pt <= l.x0 <= x1 + column_margin_pt

    def in_above_window(l: Line) -> bool:
        # A real caption above a WIDE composite figure isn't bound by the
        # figure's own narrow column margin on the LEFT -- confirmed real,
        # Honda CR-V 2026 ("Music Playback via Wired Connection"): the true
        # caption, "Cover Art Audio/Information Screen", starts 61.9pt left
        # of the figure's own x0, well outside column_margin_pt, because
        # it's a header for the whole composite block, not aligned to the
        # merged image rect's own (somewhat arbitrary) left edge. No such
        # widening on the RIGHT, though (capped at the figure's own x1, not
        # beyond it): confirmed real, same PDF, "Start Up" -- a right-column
        # callout box's own first line ("Select OK.") sits only 11.6pt past
        # the figure's x1 with a real (non-graze) 14.1pt vertical gap above
        # it, and would otherwise beat the figure's genuine caption on pure
        # distance. An above-positioned caption never starts to the right of
        # the figure it captions in any real case checked so far -- only
        # level-with-or-left-of it.
        #
        # The LEFT widening itself is scoped to profiles with heading_prefixes
        # configured (Honda's own convention today) -- confirmed real,
        # 2026-09-08: regenerating every already-reviewed Subaru chapter
        # against the widened window (no heading_prefixes involved at all)
        # surfaced 60+ new caption changes across chapters that were
        # previously untouched and clean. The one confirmed real case
        # motivating the wider window is Honda-only; without independent
        # confirmation it generalizes safely to every other manual's own
        # layout conventions, it must not touch content this project has
        # already spent real review time getting right. Without
        # heading_prefixes this degrades to EXACTLY in_narrow_window's own
        # symmetric range, not just "the same left margin, still capped at
        # x1" -- confirmed real, same day: for a WIDE figure x1 sits far to
        # the right of x0+column_margin_pt, so a naive `x0 - margin <= l.x0
        # <= x1` fallback still reached almost as far right as the old wide
        # window ever did, with no left widening involved at all.
        if not heading_prefixes:
            return in_narrow_window(l)
        return x0 - _ABOVE_WINDOW_MARGIN_PT <= l.x0 <= x1

    def is_same_line_fragment(l: Line) -> bool:
        # A line starting with a lowercase letter that has ANOTHER line on
        # this page at (near enough) the same `top`, positioned to ITS OWN
        # left AND close enough horizontally (word-spacing close, not
        # column-pitch close -- see _SAME_LINE_FRAGMENT_MAX_GAP_PT), is
        # almost certainly one half of a single physical sentence a
        # column-detection quirk split apart horizontally -- confirmed real,
        # Honda Pilot 2026: "Select or to change file." (one printed line, a
        # 3-column dense icon-legend page) came back as three separate Line
        # objects ("Select", "or", "to change file.") all sharing one `top`.
        # A genuine multi-line paragraph wrap (e.g. "...will be" ->
        # "displayed.") always sits at a DIFFERENT `top` than the sentence's
        # own start -- only a same-line splitting artifact repeats it, so
        # this never flags a real wrapped caption.
        stripped = l.text.lstrip()
        if not stripped or not stripped[0].islower():
            return False
        return any(
            o is not l
            and o.page == l.page
            and abs(o.top - l.top) < 1.0
            and o.x0 < l.x0
            and (l.x0 - o.x0) <= _SAME_LINE_FRAGMENT_MAX_GAP_PT
            for o in page_lines
        )

    same_column = [l for l in page_lines if in_wide_window(l) or (is_above(l) and in_above_window(l))]
    candidates = same_column or page_lines

    def tier(l: Line) -> int:
        # Tier 0 (heading) always wins outright, distance never considered.
        # Tier 1 ("trustworthy": same column at ANY vertical position, a
        # real caption-shaped gap above the figure reaching left of it, or a
        # candidate literally inside the figure's own horizontal footprint)
        # is compared by raw nearest-distance internally -- confirmed real,
        # Honda CR-V 2026, two DIFFERENT real cases pulling in opposite
        # directions settle correctly under nearest-within-tier1: "Music
        # Playback via Wired Connection" needs its real above-caption
        # (44.5pt gap) to beat a same-column-but-unrelated icon label
        # 70.2pt below ("Repeat Icon"), while a real Subaru case (this
        # file's own first test) needs a same-column line 62.2pt below to
        # beat a same-column-but-unrelated line 129.8pt above -- an above-
        # beats-narrow (or narrow-beats-above) STRICT tier ordering breaks
        # one of these no matter which way it's set; plain nearest-wins,
        # once both are established as trustworthy at all, settles both.
        # Confirmed again real, 2026-09-08, Honda CR-V ("Audio Remote
        # Controls" and "About Your Audio System"): a STRICT "above always
        # outranks narrow" ordering (tried the same day, briefly) broke 4
        # already-reviewed CR-V captions where a genuinely close narrow-
        # window candidate (2.2-12.2pt away) must beat a farther above-
        # window candidate (12.2-28.1pt away) that happened to also qualify
        # as "above" -- reverted back to one merged pool, pure nearest-wins.
        # Tier 2 (wide-only: reachable only by overlapping the figure's own
        # height, or previously reachable only past its right edge, from a
        # column matched by neither narrow nor above) is the same "weak"
        # last-resort shape this function has always needed to de-prioritize
        # rather than drop outright -- see is_same_line_fragment's sibling
        # note on why dropping instead of de-prioritizing empties
        # `same_column` for a figure whose only real candidate happens to be
        # this shape.
        #
        # A candidate literally inside the figure's own horizontal footprint
        # [x0, x1] but reachable by neither narrow nor above was tried as an
        # ADDITIONAL tier-1 signal (`in_rect_x_span`) same day -- it fixed 2
        # confirmed real Subaru "Phone Screen" cases (a true caption 90.8pt
        # right of the figure's own x0, and one 11.9pt below it, both too
        # far for in_narrow_window) but also surfaced 28 new, mostly
        # unverified caption changes across an already-reviewed, previously-
        # clean chapter (Quick Guide) once every densely-packed grid page's
        # own internal labels started competing for tier 1 -- an "own x-span,
        # not overlapping" guard fixed the one CR-V case caught by direct
        # testing ("Device"/"USB Flash Drive"), but the volume and breadth of
        # still-unverified changes elsewhere was not worth the 2 cases it
        # fixed. Reverted; those 2 Phone Screen cases are left as a known,
        # accepted residual limitation (docs/ARCHITECTURE.md 2026-09-08 "29.")
        # -- same standing policy as Honda Pilot's "Play/Pause Icon" case.
        #
        # A distance cap on this unconditional win was tried and reverted,
        # 2026-09-09: it fixed 2 confirmed real Honda Pilot false positives (an
        # unrelated subsection heading 48-80pt away beating the true nearby
        # caption) but changed 5 already-good Honda CR-V captions when
        # regenerated to check for regressions, at least 3 of them clearly worse
        # (a lowercase sentence fragment or a wrong nearby label replacing a
        # correct one) -- see docs/HANDOVER.md 2026-09-09 for the full incident.
        # Left as a known, accepted residual limitation, same standing policy as
        # the "Play/Pause Icon" case above.
        if is_heading_line(l):
            return 0
        if is_same_line_fragment(l):
            return 3  # last resort, kept only so same_column is never empty
        if in_narrow_window(l) or (is_above(l) and in_above_window(l)):
            return 1
        return 2

    def distance(l: Line) -> tuple[int, float, float]:
        if l.top < top:
            vertical = top - l.top
        elif l.top > bottom:
            vertical = l.top - bottom
        else:
            vertical = 0.0
        return tier(l), vertical, abs(l.x0 - x0)

    best = min(candidates, key=distance)
    if is_heading_line(best):
        return _merge_wrapped_caption(best, page_lines)
    # A caption horizontally split into two same-height pieces by a column-
    # detection quirk (the SAME real shape is_same_line_fragment guards
    # against, just with both halves reading as complete phrases on their
    # own instead of one being a lowercase mid-sentence fragment) is merged
    # back into one line here -- confirmed real, Honda CR-V 2026 ("Music
    # Playback via Wired Connection"): "Cover Art Audio/Information Screen",
    # one printed line per the original app's own real citation, comes back
    # from this rebuild's column-aware line-grouping as two Line objects,
    # "Cover Art" and "Audio/Information Screen", sharing one `top` -- both
    # independently TIE for the win (same tier, same vertical distance),
    # which is itself the signal that they belong together.
    #
    # Matching on tier+vertical (an exact tie), not just "any same_column
    # line at this top", is required -- confirmed real, Honda Pilot 2026: a
    # dense icon-legend grid routinely row-aligns two genuinely DIFFERENT
    # icons' own separate labels at the same height by design (not a split
    # caption at all), and merging on shared height alone glued unrelated
    # pairs together (e.g. "Left Selector" + "VOL(+/VOL(-", two different
    # controls). Only a real tie is trustworthy enough to merge.
    tied = distance(best)[:2]
    siblings = sorted(
        (l for l in same_column if l is not best and distance(l)[:2] == tied),
        key=lambda l: l.x0,
    )
    if siblings:
        ordered = sorted([best, *siblings], key=lambda l: l.x0)
        best = replace(best, text=" ".join(l.text for l in ordered))
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
