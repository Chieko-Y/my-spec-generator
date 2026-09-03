"""Regression test for a real design gap in the published README, found
2026-09-03: its "Headings not matched to body text" section first said those
headings "were not turned into functions" -- false, per domain.
manual_parsing._cut_sections (an unmatched-by-text candidate with real body
content still gets its own Section via a coarser page-number fallback).
Wording was corrected once, but the user then asked the harder question:
even worded accurately, what is a reviewer supposed to DO with this? A real
example (Subaru outback-2025/ascent-2026, "Map Data") turned out to have
nothing wrong at all -- it's flagged only because a coincidental, weak text
overlap with an UNRELATED heading was correctly rejected by
_MIN_CONTAINMENT_RATIO. A reviewer reading the published README has no way
to act on this even when something genuinely IS wrong -- fixing a real
extraction gap means changing the matching code, not something fillable on
a review screen. So it's deliberately not surfaced there at all anymore;
only at generate() time (cli.py's stdout, web.py's server console + flash
message), where the audience is whoever ran the generate and can actually
investigate.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.model import FunctionSpec, ManualSpec
from infrastructure.markdown_publisher import _index_markdown


def test_unmatched_headings_are_not_surfaced_in_the_published_readme():
    function = FunctionSpec(
        function_id="f1", chapter_number="1", title="Map Data", area="Navigation",
        function_path="Navigation / Map Data", pages=[223],
    )
    spec = ManualSpec(
        manual_id="m", maker="Subaru", model="Outback 2025", document_title="Test",
        scope="navigation", markets=["US"], profile_id="p",
        meta={"unmatched_headings": ["Map Data"]},
        functions=[function],
    )

    index = _index_markdown(spec, terms=[], combined=False, chapter_slug="navigation")

    assert "not matched" not in index.lower()
    assert "were not turned into functions" not in index
    # The function itself must still appear normally -- this isn't about
    # hiding the function, only about not showing a not-actionable-by-a-
    # reviewer diagnostic on their review page.
    assert "Map Data" in index
