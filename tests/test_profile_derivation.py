"""Regression tests for the rule-based, AI-free layout auto-detector
(src/domain/profile_derivation.py). The first fixture is shaped after the real 2025
Subaru supplement PDF (see docs/HANDOVER.md 2026-08-26): 2 print-production-marker
bookmarks (unusable), a "Audio" side-tab label repeating across many pages, and
2-column body text -- the exact combination this detector needs to resolve without
any AI."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Bookmark, Line
from domain.profile_derivation import derive_layout


def test_derives_two_columns_and_running_head_when_bookmarks_are_unusable():
    bookmarks = [
        Bookmark(title="4C_P1_P66_ProcessBlack", level=0, page_index=0),
        Bookmark(title="1C_P67_P256_ProcessBlack", level=0, page_index=66),
    ]
    lines = []
    for page in range(10):
        lines.append(Line(page=page, text="Audio", top=5.0, x0=500.0, size=8.0))
        lines.append(Line(page=page, text=f"left body {page}", top=100.0, x0=50.0, size=10.0))
        lines.append(Line(page=page, text=f"right body {page}", top=100.0, x0=300.0, size=10.0))

    report = derive_layout(lines, bookmarks, image_rects=None)

    assert report.columns == 2
    assert report.section_source == "running_head"
    assert [c.label for c in report.running_head_chapters] == ["audio"]


def test_derives_bookmarks_when_they_look_chapter_shaped():
    bookmarks = [
        Bookmark(title="Audio", level=0, page_index=0),
        Bookmark(title="Phone", level=0, page_index=10),
        Bookmark(title="Navigation", level=0, page_index=20),
    ]
    lines = [Line(page=p, text=f"line {p}", top=100.0, x0=60.0) for p in range(30)]

    report = derive_layout(lines, bookmarks, image_rects=None)

    assert report.section_source == "bookmarks"
    assert report.columns == 1


def test_prefers_chapter_toc_over_running_head_when_both_are_detectable():
    # 8/27's step 3 conclusion (docs/HANDOVER.md): a real printed table of
    # contents gives exact, unambiguous chapter boundaries, while running_head
    # only infers them from repeated margin text -- which can legitimately
    # collide across two different chapters (the "BASIC OPERATION" case). When
    # a PDF has both, chapter_toc must win. This fixture makes BOTH detectable
    # (running_head coverage alone would be ~90%, far above the 30% minimum)
    # to prove a real preference, not just "chapter_toc was the only one found".
    bookmarks = [
        Bookmark(title="4C_P1_P66_ProcessBlack", level=0, page_index=0),
        Bookmark(title="1C_P67_P256_ProcessBlack", level=0, page_index=66),
    ]

    lines = [Line(page=0, text="TABLE OF CONTENTS", top=79.0, x0=70.9, size=12.0)]

    def chapter_row(page, top, name, printed_page):
        return [
            Line(page=page, text=name, top=top, x0=-269.3, size=11.0),
            Line(page=page, text=str(printed_page), top=top + 0.4, x0=603.8, size=10.0),
        ]

    lines += chapter_row(1, 79.5, "Quick Guide", 13)
    lines += chapter_row(1, 147.5, "Settings", 79)
    lines += chapter_row(1, 181.5, "Phone", 107)
    lines.append(Line(page=12, text="Quick Guide", top=50.0, size=14.0))
    lines.append(Line(page=78, text="Settings", top=50.0, size=14.0))
    lines.append(Line(page=106, text="Phone", top=50.0, size=14.0))

    for page in range(12, 78):
        lines.append(Line(page=page, text="Quick Guide", top=5.0, x0=500.0, size=8.0))
    for page in range(78, 106):
        lines.append(Line(page=page, text="Settings", top=5.0, x0=500.0, size=8.0))
    for page in range(106, 120):
        lines.append(Line(page=page, text="Phone", top=5.0, x0=500.0, size=8.0))

    report = derive_layout(lines, bookmarks, image_rects=None)

    assert report.section_source == "chapter_toc"
    assert [c.label for c in report.toc_chapters] == ["Quick Guide", "Settings", "Phone"]
    assert report.running_head_chapters == []


def test_detects_figure_size_threshold_from_the_widest_size_gap():
    # Icons (~11pt) vs. real screen-illustration figures (100pt+) -- confirmed
    # against the real Subaru PDF, 2026-08-25 (see docs/HANDOVER.md).
    icons = {p: [(0.0, 0.0, 11.0, 11.0, None, None)] for p in range(6)}
    figures = {p + 100: [(0.0, 0.0, 200.0, 150.0, None, None)] for p in range(6)}
    image_rects = {**icons, **figures}
    bookmarks = [Bookmark(title=f"Chapter {i}", level=0, page_index=i) for i in range(3)]
    # Real body text (like a real PDF's own) covers the whole document, not just
    # the first few pages -- needed so the third (open-ended) bookmark chapter's
    # page range actually reaches the images at page 100+ instead of being cut
    # off at whatever page the last Line happens to sit on.
    lines = [Line(page=p, text="x", top=10.0, x0=60.0) for p in range(3)]
    lines.append(Line(page=105, text="x", top=10.0, x0=60.0))

    report = derive_layout(lines, bookmarks, image_rects)

    assert report.figure_min_width_pt is not None
    assert 11.0 < report.figure_min_width_pt < 200.0


def test_stretched_fill_boxes_do_not_skew_the_derived_figure_threshold():
    """Real Honda Pilot PDF case, 2026-09-02: a 1x1px background box stretched to
    194.2x336.3pt appeared on nearly every page alongside real figures (100-200pt)
    and icons (~11pt). Left in, it becomes the widest embedded image and the
    derived threshold jumps to ~265pt (between the real figures and the fill),
    which still passes but for the wrong reason -- and a bigger real manual where
    the fill is the single widest item entirely (no real figure anywhere close)
    would derive a threshold above every real figure, excluding all of them. The
    fill must be dropped before the gap search runs at all."""
    icons = {p: [(0.0, 0.0, 11.0, 11.0, 31, 24)] for p in range(6)}
    figures = {p + 100: [(0.0, 0.0, 200.0, 150.0, 400, 300)] for p in range(6)}
    fills = {p + 200: [(0.0, 0.0, 194.2, 336.3, 1, 1)] for p in range(6)}
    # A real, high-dpi full-bleed chapter-divider photo -- not a stretched fill,
    # so only the negative-x0 check catches it (Honda Pilot PDF, 2026-09-02).
    dividers = {p + 300: [(-11.1, 45.4, 684.9, 306.3, 1934, 725)] for p in range(3)}
    image_rects = {**icons, **figures, **fills, **dividers}
    bookmarks = [Bookmark(title=f"Chapter {i}", level=0, page_index=i) for i in range(3)]
    # See the sibling test above for why this needs to reach the last image page.
    lines = [Line(page=p, text="x", top=10.0, x0=60.0) for p in range(3)]
    lines.append(Line(page=302, text="x", top=10.0, x0=60.0))

    report = derive_layout(lines, bookmarks, image_rects)

    assert report.figure_min_width_pt is not None
    assert 11.0 < report.figure_min_width_pt < 200.0
    assert report.figure_min_height_pt is not None
    assert 11.0 < report.figure_min_height_pt < 150.0


def test_figure_threshold_is_scoped_per_chapter_not_whole_document():
    """Real Honda CR-V 2026 bug, 2026-09-04 (docs/HANDOVER.md same date): this
    manual's real content figures are a different size range in different
    chapters -- Quick Reference Guide's are much larger than Features' own
    ~130-213pt screen-mockup composites. A single whole-document widest-gap
    search found its biggest gap BETWEEN those two chapters' real-figure
    clusters (not between icons and figures) and proposed 282.98pt, which
    excluded every one of Features' own real figures (0 figures extracted).
    Reproduced in miniature here: 'Quick Reference' has icons (~10pt) and large
    figures (~300pt); 'Features' has icons (~10pt) and much smaller figures
    (~120pt). A whole-document gap search would pick the 120->300 gap
    (threshold ~210pt), excluding Features' real 120pt figures entirely --
    scoping per top-level chapter and taking the most conservative threshold
    must not do that."""
    quick_reference_icons = {p: [(0.0, 0.0, 10.0, 10.0, None, None)] for p in range(6)}
    quick_reference_figures = {
        p + 10: [(0.0, 0.0, 300.0, 250.0, None, None)] for p in range(6)
    }
    features_icons = {p + 100: [(0.0, 0.0, 10.0, 10.0, None, None)] for p in range(6)}
    features_figures = {
        p + 110: [(0.0, 0.0, 120.0, 100.0, None, None)] for p in range(6)
    }
    image_rects = {
        **quick_reference_icons,
        **quick_reference_figures,
        **features_icons,
        **features_figures,
    }
    bookmarks = [
        Bookmark(title="Quick Reference Guide", level=0, page_index=0),
        Bookmark(title="Features", level=0, page_index=100),
        Bookmark(title="Maintenance", level=0, page_index=200),
    ]
    lines = [Line(page=p, text="x", top=10.0, x0=60.0) for p in (0, 100, 200)]
    lines.append(Line(page=215, text="x", top=10.0, x0=60.0))

    report = derive_layout(lines, bookmarks, image_rects)

    assert report.figure_min_width_pt is not None
    assert 10.0 < report.figure_min_width_pt < 120.0
    assert report.figure_min_height_pt is not None
    assert 10.0 < report.figure_min_height_pt < 100.0
