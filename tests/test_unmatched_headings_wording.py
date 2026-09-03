"""Regression test for a real user-facing wording bug, found 2026-09-03: the
published README's "Headings not matched to body text" section claimed those
headings "were not turned into functions" -- false. Tracing domain.
manual_parsing._cut_sections shows an unmatched-by-text candidate with real
body content still gets its own Section (a coarser page-number boundary is
used instead of an exact text match); `unmatched_headings` only flags that
the boundary is less precise, not that the function is missing. Confirmed
against real data, Subaru outback-2025/ascent-2026 navigation-system-
if-equipped: all 10 reported "unmatched" headings (e.g. "Map Screen
Operation", "Location Menu Pop-up") are present as real numbered functions
in the final output.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.model import FunctionSpec, ManualSpec
from infrastructure.markdown_publisher import _index_markdown


def test_an_unmatched_heading_is_not_claimed_to_be_missing_a_function():
    function = FunctionSpec(
        function_id="f1", chapter_number="1", title="Map Screen Operation", area="Navigation",
        function_path="Navigation / Map Screen Operation", pages=[10],
    )
    spec = ManualSpec(
        manual_id="m", maker="Subaru", model="Outback 2025", document_title="Test",
        scope="navigation", markets=["US"], profile_id="p",
        meta={"unmatched_headings": ["Map Screen Operation"]},
        functions=[function],
    )

    index = _index_markdown(spec, terms=[], combined=False, chapter_slug="navigation")

    assert "were not turned into functions" not in index
    assert "Map Screen Operation" in index
    # The function itself must still appear as a real row/node, not just as
    # the warning's own bullet point -- otherwise the wording fix would just
    # be papering over a genuine loss.
    assert index.count("Map Screen Operation") >= 2
