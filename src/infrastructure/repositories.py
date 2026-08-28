"""Port implementations backed by the filesystem. generated/ = JSON (throwaway,
recreated every generate). overlay/ = YAML (human input, never silently discarded).
glossary.json lives at the workspace root, not under one manual_id, because a term
applies across manuals.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from domain.manual_parsing import ConfirmedChapter
from domain.model import ManualSpec, TermCategory
from domain.overlay import FigureElement, GlossaryTerm, OverlayEntry, ParameterStatus
from domain.slug import slugify

from .serialization import spec_from_dict, spec_to_dict


class JsonSpecRepository:
    """One manual_id can hold many generated chapters side by side — registering a
    manual is a one-time action independent of chapter, and 'generate' can be run
    again and again for different chapters of the same book (fix for a UX report:
    the old one-spec-per-manual_id layout made the Manuals list show a single
    "Chapter" as if it were a property of the registration itself, which was
    confusing since the whole manual had been registered)."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)

    def _path(self, manual_id: str, chapter_slug: str) -> Path:
        return self.workspace_dir / manual_id / "generated" / chapter_slug / "spec.json"

    def save(self, spec: ManualSpec, chapter_slug: str) -> None:
        path = self._path(spec.manual_id, chapter_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec_to_dict(spec), indent=2, ensure_ascii=False), encoding="utf-8")

    def load(self, manual_id: str, chapter_slug: str) -> ManualSpec | None:
        path = self._path(manual_id, chapter_slug)
        if not path.exists():
            return None
        return spec_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_chapters(self, manual_id: str) -> list[str]:
        generated_dir = self.workspace_dir / manual_id / "generated"
        if not generated_dir.exists():
            return []
        return sorted(
            p.parent.name for p in generated_dir.glob("*/spec.json")
        )


class YamlOverlayRepository:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)

    def _path(self, manual_id: str, chapter_slug: str) -> Path:
        return self.workspace_dir / manual_id / "overlay" / chapter_slug / "thresholds.yaml"

    def load_thresholds(self, manual_id: str, chapter_slug: str) -> list[OverlayEntry]:
        path = self._path(manual_id, chapter_slug)
        if not path.exists():
            return []
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = []
        for item in raw.get("thresholds", []):
            entries.append(
                OverlayEntry(
                    threshold_id=item["threshold_id"],
                    value=item["value"],
                    status=ParameterStatus(item["status"]),
                    evidence=item["evidence"],
                    filled_by=item["filled_by"],
                )
            )
        return entries

    def save_thresholds(self, manual_id: str, chapter_slug: str, entries: list[OverlayEntry]) -> None:
        path = self._path(manual_id, chapter_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "thresholds": [
                {
                    "threshold_id": e.threshold_id,
                    "value": e.value,
                    "status": e.status.value,
                    "evidence": e.evidence,
                    "filled_by": e.filled_by,
                }
                for e in entries
            ]
        }
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class YamlFigureElementRepository:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)

    def _path(self, manual_id: str, chapter_slug: str) -> Path:
        return self.workspace_dir / manual_id / "overlay" / chapter_slug / "figure_elements.yaml"

    def load(self, manual_id: str, chapter_slug: str) -> list[FigureElement]:
        path = self._path(manual_id, chapter_slug)
        if not path.exists():
            return []
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return [
            FigureElement(
                figure_id=item["figure_id"],
                symbol=item["symbol"],
                label=item["label"],
                note=item.get("note", ""),
                decided_by=item["decided_by"],
            )
            for item in raw.get("elements", [])
        ]

    def save(self, manual_id: str, chapter_slug: str, elements: list[FigureElement]) -> None:
        path = self._path(manual_id, chapter_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "elements": [
                {
                    "figure_id": e.figure_id,
                    "symbol": e.symbol,
                    "label": e.label,
                    "note": e.note,
                    "decided_by": e.decided_by,
                }
                for e in elements
            ]
        }
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class JsonChapterAllowlistRepository:
    """The human-confirmed subset of running_head chapter candidates (see
    application.ports.ChapterAllowlistRepository). load() returning None -- not
    an empty list -- means this manual has never been through the
    classify/confirm flow, so callers must fall back to the unfiltered
    candidate list. Stores page_start/page_end alongside each label (not just
    the bare label string) because the same running-head margin text can
    legitimately recur for two structurally different chapters -- see
    ConfirmedChapter's docstring."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)

    def _path(self, manual_id: str) -> Path:
        return self.workspace_dir / manual_id / "chapter_allowlist.json"

    def load(self, manual_id: str) -> list[ConfirmedChapter] | None:
        path = self._path(manual_id)
        if not path.exists():
            return None
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [
            ConfirmedChapter(
                label=c["label"], page_start=c["page_start"], page_end=c["page_end"]
            )
            for c in raw.get("chapters", [])
        ]

    def save(self, manual_id: str, chapters: list[ConfirmedChapter]) -> None:
        path = self._path(manual_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "chapters": [
                {"label": c.label, "page_start": c.page_start, "page_end": c.page_end}
                for c in chapters
            ]
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class JsonGlossaryRepository:
    def __init__(self, workspace_dir: Path):
        self.path = Path(workspace_dir) / "glossary.json"

    def load_all(self) -> list[GlossaryTerm]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [
            GlossaryTerm(
                term_id=item["term_id"],
                in_house_term=item["in_house_term"],
                category=TermCategory(item["category"]),
                manual_wordings=item["manual_wordings"],
                evidence=item["evidence"],
            )
            for item in raw.get("terms", [])
        ]

    def save_all(self, terms: list[GlossaryTerm]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "terms": [
                {
                    "term_id": t.term_id,
                    "in_house_term": t.in_house_term,
                    "category": t.category.value,
                    "manual_wordings": t.manual_wordings,
                    "evidence": t.evidence,
                }
                for t in terms
            ]
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class JsonSourceRegistry:
    """Ledger of registered manuals. One row per manual_id. Lives at the library root
    alongside the original PDFs, matching the original app's stated layout
    (<library>/sources.json)."""

    def __init__(self, library_dir: Path):
        self.path = Path(library_dir) / "sources.json"

    def _load_all(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save_all(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def list_sources(self) -> list[dict]:
        data = self._load_all()
        return [{"manual_id": k, **v} for k, v in data.items()]

    def get(self, manual_id: str) -> dict | None:
        data = self._load_all()
        row = data.get(manual_id)
        return {"manual_id": manual_id, **row} if row is not None else None

    def upsert(self, manual_id: str, fields: dict) -> None:
        data = self._load_all()
        row = data.get(manual_id, {})
        row.update({k: v for k, v in fields.items() if v is not None})
        data[manual_id] = row
        self._save_all(data)


class ManualLibrary:
    """Stores/locates original PDFs under <library>/<maker>/<model>/original/<file>.

    Never fetches anything itself (no HTTP client anywhere in this class) — a human
    places the PDF, this class only manages the local path.
    """

    def __init__(self, library_dir: Path):
        self.library_dir = Path(library_dir)

    def path_for(self, manual_id: str) -> str:
        row_path = self.library_dir / "sources.json"
        if row_path.exists():
            data = json.loads(row_path.read_text(encoding="utf-8"))
            row = data.get(manual_id)
            if row and row.get("local_path"):
                return row["local_path"]
        maker, model, _booklet = manual_id.split("/")
        original_dir = self.library_dir / maker / model / "original"
        if original_dir.exists():
            pdfs = sorted(original_dir.glob("*.pdf"))
            if pdfs:
                return str(pdfs[0])
        raise FileNotFoundError(f"no original PDF found for {manual_id}")

    def exists(self, manual_id: str) -> bool:
        try:
            return Path(self.path_for(manual_id)).exists()
        except FileNotFoundError:
            return False

    def store_upload(self, maker: str, model: str, filename: str, content: bytes) -> str:
        maker_slug, model_slug = slugify(maker), slugify(model)
        target_dir = self.library_dir / maker_slug / model_slug / "original"
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name  # strip any directory component from the client
        target_path = target_dir / safe_name
        target_path.write_bytes(content)
        return str(target_path)

    def store_inbox(self, inbox_id: str, filename: str, content: bytes) -> str:
        """Holding area for a PDF whose identity has not been confirmed yet
        (REQUIREMENTS/CLAUDE.md `_inbox/`). Both the drag-and-drop path and the
        plain file-picker fallback land here first, then `commit_inbox` moves the
        file once a human has confirmed maker/model/title — this is what keeps
        the two upload paths from producing differently-formed data."""
        inbox_dir = self.library_dir / "_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        target = inbox_dir / f"{inbox_id}__{safe_name}"
        target.write_bytes(content)
        return str(target)

    def commit_inbox(self, inbox_path: str, maker: str, model: str) -> str:
        src = Path(inbox_path)
        if not src.exists():
            raise FileNotFoundError(f"inbox file not found: {inbox_path}")
        maker_slug, model_slug = slugify(maker), slugify(model)
        target_dir = self.library_dir / maker_slug / model_slug / "original"
        target_dir.mkdir(parents=True, exist_ok=True)
        # strip the "<inbox_id>__" prefix added by store_inbox
        original_name = src.name.split("__", 1)[-1]
        target_path = target_dir / original_name
        target_path.write_bytes(src.read_bytes())
        src.unlink()
        return str(target_path)


def sha256_of(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
