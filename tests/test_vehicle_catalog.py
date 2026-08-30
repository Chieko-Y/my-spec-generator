"""Sanity checks for domain.vehicle_catalog -- the manual-registration form's
maker/model pick-lists (see templates/manuals.html). Not a test of the sales
data's real-world accuracy (that's the responsibility of whoever refreshes this
file), just that the two tables stay structurally consistent with each other.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.vehicle_catalog import MAKERS, MODELS_BY_MAKER


def test_every_maker_has_a_model_list():
    assert set(MAKERS) == set(MODELS_BY_MAKER.keys())


def test_no_duplicate_makers():
    assert len(MAKERS) == len(set(MAKERS))


def test_every_maker_has_at_least_one_model_and_no_duplicates():
    for maker, models in MODELS_BY_MAKER.items():
        assert models, f"{maker} has an empty model list"
        assert len(models) == len(set(models)), f"{maker} has a duplicate model"
