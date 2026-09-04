"""Regression tests for the rule-based, AI-free profile fitness check
(src/domain/profile_fitness.py). Fixtures are shaped after real cases already found
in this project -- see docs/HANDOVER.md 2026-08-26 "AIによるProfile判定" for the
two-tier design this implements, and the 2025 Subaru supplement finding that
motivated it (2 print-production-marker bookmarks, 2-column body text)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.manual_parsing import Bookmark, Line
from domain.profile import DEFAULT_SLOT_RULES, LayoutConfig, Profile
from domain.profile_fitness import bookmark_depth_ok, score_fitness


def _profile(section_source: str = "bookmarks", columns: int = 1) -> Profile:
    return Profile(
        profile_id="test",
        extends=None,
        derived_from="test fixture",
        slot_rules=DEFAULT_SLOT_RULES,
        layout=LayoutConfig(section_source=section_source, columns=columns),
    )


def test_bookmark_depth_ok_rejects_real_print_production_markers():
    # The real 2025 Subaru supplement PDF's only 2 bookmarks, verbatim.
    bookmarks = [
        Bookmark(title="4C_P1_P66_ProcessBlack", level=0, page_index=0),
        Bookmark(title="1C_P67_P256_ProcessBlack", level=0, page_index=66),
    ]
    ok, reason = bookmark_depth_ok(bookmarks)
    assert ok is False
    assert reason


def test_bookmark_depth_ok_accepts_real_chapter_titles():
    bookmarks = [
        Bookmark(title="Audio", level=0, page_index=0),
        Bookmark(title="Phone", level=0, page_index=20),
        Bookmark(title="Navigation System", level=0, page_index=40),
        Bookmark(title="Settings", level=0, page_index=60),
    ]
    ok, _reason = bookmark_depth_ok(bookmarks)
    assert ok is True


def test_bookmark_depth_ok_rejects_too_few_top_level_bookmarks():
    bookmarks = [Bookmark(title="Only Chapter", level=0, page_index=0)]
    ok, reason = bookmark_depth_ok(bookmarks)
    assert ok is False
    assert reason


def test_score_fitness_flags_column_count_mismatch():
    left = [Line(page=0, text=f"L{i}", top=float(i * 10), x0=50.0) for i in range(5)]
    right = [Line(page=0, text=f"R{i}", top=float(i * 10), x0=300.0) for i in range(5)]
    profile = _profile(section_source="running_head", columns=1)

    report = score_fitness(left + right, [], profile)

    assert report.fits is False
    assert report.column_match_ok is False
    assert any("column" in r for r in report.reasons)


def test_score_fitness_fails_bookmarks_profile_with_no_bookmarks():
    profile = _profile(section_source="bookmarks", columns=1)
    lines = [Line(page=0, text="hello", top=10.0, x0=60.0)]

    report = score_fitness(lines, [], profile)

    assert report.fits is False
    assert report.bookmark_depth_ok is False


def test_score_fitness_skips_bookmark_and_anomaly_checks_for_running_head_profile():
    profile = _profile(section_source="running_head", columns=1)
    lines = [Line(page=0, text="hello", top=10.0, x0=60.0)]

    report = score_fitness(lines, [], profile)

    assert report.bookmark_depth_ok is None
    assert report.anomaly_ratio is None


def test_score_fitness_catches_one_chapter_being_a_different_column_count():
    """Real Honda CR-V 2026 case (docs/HANDOVER.md 2026-09-04): the document as a
    whole is 1-column, but its Features chapter specifically is 2-column. A
    whole-document aggregate check missed this and let generic_v1 (columns=1) pass
    cleanly; the per-chapter check must catch it even though every OTHER chapter
    genuinely agrees with the profile."""
    bookmarks = [
        Bookmark(title="Safety", level=0, page_index=0),
        Bookmark(title="Features", level=0, page_index=10),
        Bookmark(title="Maintenance", level=0, page_index=20),
    ]
    # Front matter and Maintenance: single-column, no wide x0 gap.
    one_column_lines = [
        Line(page=p, text=f"L{p}", top=10.0, x0=50.0)
        for p in list(range(0, 10)) + list(range(20, 30))
    ]
    # Features (pages 10-19): two clearly separated columns, x0 gap > MIN_COLUMN_GAP_PT.
    two_column_lines = [
        Line(page=p, text=f"left{p}", top=10.0, x0=50.0) for p in range(10, 20)
    ] + [
        Line(page=p, text=f"right{p}", top=10.0, x0=300.0) for p in range(10, 20)
    ]
    profile = _profile(section_source="bookmarks", columns=1)

    report = score_fitness(one_column_lines + two_column_lines, bookmarks, profile)

    assert report.column_match_ok is False
    assert any("Features" in r and "2-column" in r for r in report.reasons)


def test_sample_anomaly_ratio_reports_the_worst_chapter_not_just_the_first(monkeypatch):
    """The 'one-click Generate' path (resolve_manual_profile) doesn't know a target
    chapter yet, so it used to sample only the first top-level bookmark chapter --
    typically front matter (e.g. "A Few Words About Safety" for every Honda manual
    seen so far), which is rarely where a real layout mismatch garbles text. A
    profile that's clean for front matter but garbles a later real chapter (e.g.
    Features) must still fail. Isolated from build_blocks/text_anomalies'
    heuristics (covered elsewhere) by faking _anomaly_ratio_for_chapter's per-
    chapter result directly -- this test is only about the sampling/aggregation
    logic in _sample_anomaly_ratio itself."""
    import domain.profile_fitness as profile_fitness

    bookmarks = [
        Bookmark(title="Safety", level=0, page_index=0),
        Bookmark(title="Features", level=0, page_index=1),
        Bookmark(title="Maintenance", level=0, page_index=2),
    ]
    ratios_by_chapter = {"Safety": 0.0, "Features": 0.9, "Maintenance": 0.1}
    monkeypatch.setattr(
        profile_fitness,
        "_anomaly_ratio_for_chapter",
        lambda lines, bookmarks, profile, prefix: ratios_by_chapter[prefix],
    )
    profile = _profile(section_source="bookmarks", columns=1)

    ratio, chapter = profile_fitness._sample_anomaly_ratio([], bookmarks, profile, None)

    assert chapter == "Features"
    assert ratio == 0.9

    report = score_fitness([], bookmarks, profile)
    assert any("Features" in r and "90%" in r for r in report.reasons)
