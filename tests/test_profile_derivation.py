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
    icons = {p: [(0.0, 0.0, 11.0, 11.0)] for p in range(6)}
    figures = {p + 100: [(0.0, 0.0, 200.0, 150.0)] for p in range(6)}
    image_rects = {**icons, **figures}
    bookmarks = [Bookmark(title=f"Chapter {i}", level=0, page_index=i) for i in range(3)]
    lines = [Line(page=p, text="x", top=10.0, x0=60.0) for p in range(3)]

    report = derive_layout(lines, bookmarks, image_rects)

    assert report.figure_min_width_pt is not None
    assert 11.0 < report.figure_min_width_pt < 200.0
