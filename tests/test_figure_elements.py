"""Regression tests for UseCases.add_figure_element / remove_figure_element's
dedup key, fixed 2026-08-31. Real Subaru case: a figure with an unlabeled icon
("Map icon", no A/B/1 symbol) -- keying on (figure_id, symbol) alone made a
second unlabeled icon on the same figure silently overwrite the first instead
of coexisting. User's own fix suggestion: key on (figure_id, symbol, label).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application.use_cases import UseCases
from domain.overlay import FigureElement


class _FakeFigureElementRepository:
    def __init__(self):
        self._store: dict[tuple[str, str], list[FigureElement]] = {}

    def load(self, manual_id: str, chapter_slug: str) -> list[FigureElement]:
        return list(self._store.get((manual_id, chapter_slug), []))

    def save(self, manual_id: str, chapter_slug: str, elements: list[FigureElement]) -> None:
        self._store[(manual_id, chapter_slug)] = list(elements)


def _uc(repo: _FakeFigureElementRepository) -> UseCases:
    return UseCases(None, None, None, None, None, repo, None, None, None, None, None, None)


def test_two_unlabeled_icons_on_the_same_figure_both_survive():
    repo = _FakeFigureElementRepository()
    uc = _uc(repo)
    uc.add_figure_element(
        "m", "c", FigureElement(figure_id="f1", symbol="", label="Map icon", note="", decided_by="A")
    )
    uc.add_figure_element(
        "m", "c", FigureElement(figure_id="f1", symbol="", label="Home icon", note="", decided_by="A")
    )
    elements = uc.load_figure_elements("m", "c")
    assert {e.label for e in elements} == {"Map icon", "Home icon"}


def test_resubmitting_the_same_figure_symbol_label_updates_in_place():
    repo = _FakeFigureElementRepository()
    uc = _uc(repo)
    uc.add_figure_element(
        "m", "c", FigureElement(figure_id="f1", symbol="", label="Map icon", note="v1", decided_by="A")
    )
    uc.add_figure_element(
        "m", "c", FigureElement(figure_id="f1", symbol="", label="Map icon", note="v2", decided_by="A")
    )
    elements = uc.load_figure_elements("m", "c")
    assert len(elements) == 1
    assert elements[0].note == "v2"


def test_remove_figure_element_only_removes_the_matching_symbol_and_label():
    repo = _FakeFigureElementRepository()
    uc = _uc(repo)
    uc.add_figure_element(
        "m", "c", FigureElement(figure_id="f1", symbol="", label="Map icon", note="", decided_by="A")
    )
    uc.add_figure_element(
        "m", "c", FigureElement(figure_id="f1", symbol="", label="Home icon", note="", decided_by="A")
    )
    uc.remove_figure_element("m", "c", "f1", "", "Map icon")
    elements = uc.load_figure_elements("m", "c")
    assert len(elements) == 1
    assert elements[0].label == "Home icon"
