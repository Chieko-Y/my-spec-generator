"""Regression test for infrastructure.markdown_publisher's figure block
formatting. Real report, 2026-09-04: with two or more figures in one function,
the published markdown never put a blank line between one figure's own
3-line block (image + source + caption) and the next figure's image line --
python-markdown's nl2br extension (see markdown_view.py) then rendered the
WHOLE figures section as a single <p> with plain <br> between every line, so
the visual gap between one figure's caption and the NEXT figure's image
looked identical to the gap between an image and its own caption ("図と
キャプションがちょっと離れていて、次の図のキャプションとまちがえそう")."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.model import FigureRef, FunctionSpec, ManualSpec
from infrastructure.markdown_publisher import MarkdownSpecPublisher


def _spec_with_two_figures() -> ManualSpec:
    function = FunctionSpec(
        function_id="f1",
        chapter_number="1",
        title="Phone screen",
        area="Features",
        function_path="Features / Phone screen",
        pages=[1],
        figures=[
            FigureRef(
                figure_id="aaa",
                page=0,
                rect=(0, 0, 10, 10),
                caption_source="pdf_image",
                caption_text="Phone menu screen",
                printed_page=1,
            ),
            FigureRef(
                figure_id="bbb",
                page=0,
                rect=(0, 0, 10, 10),
                caption_source="pdf_image",
                caption_text="Phone screen",
                printed_page=2,
            ),
        ],
    )
    return ManualSpec(
        manual_id="honda/cr-v-2026/ivi",
        maker="Honda",
        model="CR-V 2026",
        document_title="2026 Honda CR-V Owner's Manual",
        scope="Features",
        markets=["US"],
        profile_id="test",
        functions=[function],
    )


def test_a_blank_line_separates_each_figures_own_block(tmp_path):
    publisher = MarkdownSpecPublisher(tmp_path)
    publisher.publish(_spec_with_two_figures(), "features", allow_restricted=True, terms=[])

    text = (tmp_path / "honda/cr-v-2026/ivi/published/features/1-phone-screen.md").read_text(encoding="utf-8")
    figures_section = text.split("## Figures", 1)[1]

    first_caption_line = next(
        i for i, line in enumerate(figures_section.splitlines()) if "Phone menu screen" in line
    )
    lines = figures_section.splitlines()
    assert lines[first_caption_line + 1].strip() == "", (
        "expected a blank line right after the first figure's caption, before the second figure's image"
    )


def test_each_figure_renders_as_its_own_paragraph_not_one_shared_block():
    from infrastructure.markdown_view import render_markdown_to_html

    md = (
        "## Figures\n"
        "![figure](../figures/FIG-a.png)\n"
        "- Figure 1-1 source: p.1\n"
        "- (Copied from OM) caption one\n"
        "\n"
        "![figure](../figures/FIG-b.png)\n"
        "- Figure 1-2 source: p.2\n"
        "- (Copied from OM) caption two\n"
    )

    html = render_markdown_to_html(md)

    assert html.count("<p>") == 2, "each figure must be its own paragraph, not one shared <p> for the whole section"
    assert "caption one" not in html.split("<p>")[2]  # not bled into the second figure's paragraph
