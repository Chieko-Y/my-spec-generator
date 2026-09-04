"""Regression test for infrastructure.config_provider.FileConfigProvider --
guards against the exact class of bug found 2026-09-04: LayoutConfig.
column_detect_per_page was added to the dataclass and set in
config/profiles/honda_v2.json, but FileConfigProvider._build_profile's
constructor call for LayoutConfig(...) was never updated to read it from the
raw JSON -- so it silently kept the dataclass default (False) no matter what
the profile file said. Confirmed real: this made every fix gated on
column_detect_per_page (docs/ARCHITECTURE.md "18."/"20-4.") completely inert
in the actual running app, even though every standalone verification script
(which builds Profile/LayoutConfig directly with **kwargs, not through
FileConfigProvider) showed the fix working -- the bug was invisible to any
check that didn't go through the real config-loading path.

Rather than one hand-written test per field (which the NEXT new field could
just as easily be left out of, reproducing the same bug), this iterates
dataclasses.fields(LayoutConfig) so a future field is covered automatically:
every field gets a JSON profile value clearly different from the dataclass
default, and the loaded Profile must reflect it.
"""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.profile import LayoutConfig
from infrastructure.config_provider import FileConfigProvider

# One clearly-non-default JSON value per LayoutConfig field type. Extend this
# when a new field's type isn't covered yet -- the test below will fail loudly
# (KeyError) rather than silently skipping the new field.
_NON_DEFAULT_BY_TYPE = {
    "str": "changed",
    "int": 99,
    "float": 12.5,
    "bool": True,
    "str | None": "changed",
    "float | None": 12.5,
    "list[str]": ["changed"],
}


def _non_default_json_value(f: dataclasses.Field) -> object:
    default = f.default if f.default is not dataclasses.MISSING else f.default_factory()
    type_key = str(f.type)
    if type_key in _NON_DEFAULT_BY_TYPE:
        candidate = _NON_DEFAULT_BY_TYPE[type_key]
    elif default is False:
        candidate = True
    elif default is True:
        candidate = False
    else:
        raise AssertionError(f"no non-default JSON value registered for field {f.name!r} (type {f.type!r})")
    assert candidate != default, f"chosen non-default value for {f.name!r} equals the real default"
    return candidate


def test_every_layout_config_field_is_actually_read_from_the_profile_json(tmp_path):
    fields = dataclasses.fields(LayoutConfig)
    layout_json = {f.name: _non_default_json_value(f) for f in fields}

    config_dir = tmp_path / "config"
    (config_dir / "profiles").mkdir(parents=True)
    (config_dir / "profiles" / "test_v1.json").write_text(
        json.dumps({
            "profile_id": "test_v1",
            "extends": None,
            "derived_from": "test fixture",
            "layout": layout_json,
        }),
        encoding="utf-8",
    )
    (config_dir / "profile_map.json").write_text(json.dumps({}), encoding="utf-8")

    provider = FileConfigProvider(config_dir)
    profile = provider.profile_by_id("test_v1")

    for f in fields:
        loaded = getattr(profile.layout, f.name)
        expected = layout_json[f.name]
        assert loaded == expected, (
            f"LayoutConfig.{f.name} was not read from the profile JSON "
            f"(FileConfigProvider._build_profile's LayoutConfig(...) call is missing this field) -- "
            f"got {loaded!r}, expected {expected!r}"
        )
