"""Loads profiles from config/profiles/*.json + config/profile_map.json.

profile_map.json resolves manual_id -> profile_id, preferring an exact manual_id match
over a maker-level match over the default (mirrors the original app's stated lookup
order: "profile_map.json は manual_id を最優先で引く").

A profile may `extends` a parent and override only what differs (typically `layout`) —
copying slot_rules/judgment words into a child profile is treated as a mistake
(creates a second source of truth), matching the CLAUDE.md gotcha.
"""
from __future__ import annotations

import json
from pathlib import Path

from domain.model import SpecSlot
from domain.profile import DEFAULT_SLOT_RULES, LayoutConfig, Profile, SlotRule


class FileConfigProvider:
    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.profiles_dir = self.config_dir / "profiles"
        self._cache: dict[str, Profile] = {}

    def _load_raw(self, profile_id: str) -> dict:
        path = self.profiles_dir / f"{profile_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"profile not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_profile(self, profile_id: str) -> Profile:
        if profile_id in self._cache:
            return self._cache[profile_id]

        raw = self._load_raw(profile_id)
        parent: Profile | None = None
        if raw.get("extends"):
            parent = self._build_profile(raw["extends"])

        layout_raw = raw.get("layout", {})
        base_layout = parent.layout if parent else LayoutConfig()
        layout = LayoutConfig(
            section_source=layout_raw.get("section_source", base_layout.section_source),
            section_depth_below_chapter=layout_raw.get(
                "section_depth_below_chapter", base_layout.section_depth_below_chapter
            ),
            running_head_regex=layout_raw.get("running_head_regex", base_layout.running_head_regex),
            columns=layout_raw.get("columns", base_layout.columns),
            repair_kerning=layout_raw.get("repair_kerning", base_layout.repair_kerning),
            figure_min_width_pt=layout_raw.get("figure_min_width_pt", base_layout.figure_min_width_pt),
            figure_min_height_pt=layout_raw.get("figure_min_height_pt", base_layout.figure_min_height_pt),
            figure_merge_distance_pt=layout_raw.get(
                "figure_merge_distance_pt", base_layout.figure_merge_distance_pt
            ),
            shallow_outline_level=layout_raw.get(
                "shallow_outline_level", base_layout.shallow_outline_level
            ),
            header_boundary_pt=layout_raw.get("header_boundary_pt", base_layout.header_boundary_pt),
            footer_boundary_pt=layout_raw.get("footer_boundary_pt", base_layout.footer_boundary_pt),
            page_number_offset=layout_raw.get("page_number_offset", base_layout.page_number_offset),
            heading_prefixes=layout_raw.get("heading_prefixes", base_layout.heading_prefixes),
            running_head_separator_font=layout_raw.get(
                "running_head_separator_font", base_layout.running_head_separator_font
            ),
        )

        if "slot_rules" in raw:
            slot_rules = [
                SlotRule(slot=SpecSlot(r["slot"]), keywords=r.get("keywords", []))
                for r in raw["slot_rules"]
            ]
        elif parent:
            slot_rules = parent.slot_rules
        else:
            slot_rules = DEFAULT_SLOT_RULES

        excluded = raw.get("excluded_section_titles", parent.excluded_section_titles if parent else [])

        profile = Profile(
            profile_id=profile_id,
            extends=raw.get("extends"),
            derived_from=raw.get("derived_from", ""),
            slot_rules=slot_rules,
            layout=layout,
            excluded_section_titles=excluded,
        )
        self._cache[profile_id] = profile
        return profile

    def _profile_map(self) -> dict:
        path = self.config_dir / "profile_map.json"
        if not path.exists():
            return {"mapping": {}, "default_profile_id": "generic_v1"}
        return json.loads(path.read_text(encoding="utf-8"))

    def profile_for(self, manual_id: str, maker: str) -> Profile:
        pm = self._profile_map()
        mapping = pm.get("mapping", {})
        profile_id = mapping.get(manual_id) or mapping.get(maker) or pm.get("default_profile_id", "generic_v1")
        return self._build_profile(profile_id)

    def profile_by_id(self, profile_id: str) -> Profile:
        """Load a profile directly by id, bypassing profile_map.json's manual_id/
        maker resolution -- needed by the fitness check (UseCases.check_profile_fitness),
        which is told which existing profile to try, not which manual to resolve."""
        return self._build_profile(profile_id)

    def mapped_profile_id(self, manual_id: str) -> str | None:
        pm = self._profile_map()
        return pm.get("mapping", {}).get(manual_id)

    def list_profile_ids(self) -> list[str]:
        # ".draft.json" files are deliberately excluded -- an unreviewed
        # profile-derive draft must never be tried as a fit candidate (matches
        # _load_raw / the config directory convention documented in cli.py's
        # profile-derive command: drafts are not loaded automatically).
        if not self.profiles_dir.exists():
            return []
        return sorted(
            p.stem for p in self.profiles_dir.glob("*.json") if not p.name.endswith(".draft.json")
        )

    def assign_profile(self, manual_id: str, profile_id: str) -> None:
        pm = self._profile_map()
        pm.setdefault("mapping", {})[manual_id] = profile_id
        path = self.config_dir / "profile_map.json"
        path.write_text(json.dumps(pm, indent=2, ensure_ascii=False), encoding="utf-8")

    def save_new_profile(self, profile_id: str, layout: dict, derived_from: str) -> None:
        path = self.profiles_dir / f"{profile_id}.json"
        if path.exists():
            raise FileExistsError(f"profile already exists: {path}")
        raw = {
            "profile_id": profile_id,
            "extends": "generic_v1",
            "derived_from": derived_from,
            "layout": layout,
        }
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        self._cache.pop(profile_id, None)
