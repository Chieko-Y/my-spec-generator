"""Regression tests for PdfFigureRenderer -- specifically the fix for a real bug
found 2026-08-27 (see application/ports.py FigureRenderer docstring): a two-page-
spread foldout illustration in the real 2025 Subaru supplement reuses the same
embedded-image coordinates on both of its pages, putting one page's copies at a
negative x0 entirely outside that page's own bbox. pdfplumber's crop() raises
ValueError for any rect not fully inside the page -- which used to take down the
whole chapter's generate() over one bad image. Now the renderer clips to the
page's own bbox and returns False (skip this one figure) instead of raising.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from infrastructure.figure_renderer import PdfFigureRenderer


def _make_single_page_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)
    c.rect(50, 50, 200, 200, fill=1)
    c.showPage()
    c.save()


def test_render_succeeds_for_a_rect_fully_within_the_page(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _make_single_page_pdf(pdf_path)
    renderer = PdfFigureRenderer(tmp_path / "workspace")

    ok = renderer.render(str(pdf_path), "maker/model/booklet", "fig1", 0, (50.0, 50.0, 250.0, 250.0))

    assert ok is True
    out_path = tmp_path / "workspace" / "maker/model/booklet" / "published" / "figures" / "FIG-fig1.png"
    assert out_path.exists()
    assert out_path.stat().st_size > 0


def test_render_returns_false_without_raising_for_a_rect_entirely_outside_the_page(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _make_single_page_pdf(pdf_path)
    renderer = PdfFigureRenderer(tmp_path / "workspace")

    # letter page is 612x792pt -- this rect sits entirely to the left of x=0,
    # the same shape as the real negative-x0 bug.
    ok = renderer.render(str(pdf_path), "maker/model/booklet", "fig2", 0, (-500.0, 100.0, -100.0, 300.0))

    assert ok is False
    out_path = tmp_path / "workspace" / "maker/model/booklet" / "published" / "figures" / "FIG-fig2.png"
    assert not out_path.exists()


def test_render_clips_a_partially_out_of_bounds_rect_and_still_succeeds(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    _make_single_page_pdf(pdf_path)
    renderer = PdfFigureRenderer(tmp_path / "workspace")

    # Extends 100pt past the right/bottom edges of a 612x792pt letter page.
    ok = renderer.render(str(pdf_path), "maker/model/booklet", "fig3", 0, (500.0, 700.0, 700.0, 900.0))

    assert ok is True
    out_path = tmp_path / "workspace" / "maker/model/booklet" / "published" / "figures" / "FIG-fig3.png"
    assert out_path.exists()
