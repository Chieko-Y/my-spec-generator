"""FigureRenderer implementation: crops a figure region out of the source PDF and
writes it into the manual's workspace. Kept separate from PdfManualReader the same
way MarkdownSpecPublisher is kept separate from ManualReader — reading the PDF and
writing into the workspace are different concerns (see application/ports.py).
"""
from __future__ import annotations

from pathlib import Path

import pdfplumber

# Rendering the page at a fixed DPI and cropping throws away detail if that DPI is
# lower than the embedded image's own resolution — confirmed directly against the
# real Subaru PDF, 2026-08-25: a screen-illustration figure's embedded XObject is
# 1705x1016px for a 312x186pt region, i.e. ~393 native DPI, while this renderer was
# using 150 (reported directly as visibly rougher than the original's own images).
# 400 covers real screenshots in this manual with margin without extracting the
# XObject bytes directly, which pdfplumber doesn't expose simply.
_RESOLUTION_DPI = 400


class PdfFigureRenderer:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)

    def render(
        self,
        pdf_path: str,
        manual_id: str,
        figure_id: str,
        page_index: int,
        rect: tuple[float, float, float, float],
    ) -> bool:
        # One figures/ folder shared by every chapter of this manual, directly
        # under "published/" — matches the "../figures/..." path markdown_publisher
        # falls back to from a file at published/{chapter_slug}/N-slug.md. Content-
        # hashed filenames (figure_id from content_id) mean re-rendering the same
        # figure is a no-op write, so doing this eagerly during generate() rather
        # than waiting for an explicit publish() is safe.
        out_dir = self.workspace_dir / manual_id / "published" / "figures"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"FIG-{figure_id}.png"
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_index]
            # Clip to the page's own bbox before cropping -- see this method's
            # port docstring (application/ports.py) for the real two-page-spread
            # case this guards against. pdfplumber's own crop() raises ValueError
            # for any rect not fully inside the page, which would otherwise take
            # down the whole chapter's generate() over one bad embedded image.
            px0, ptop, px1, pbottom = page.bbox
            x0, top, x1, bottom = rect
            clipped = (max(x0, px0), max(top, ptop), min(x1, px1), min(bottom, pbottom))
            if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
                return False
            page.crop(clipped).to_image(resolution=_RESOLUTION_DPI).save(str(out_path))
            return True
