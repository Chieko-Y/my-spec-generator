"""Regression tests for stale published-file tracking/cleanup
(infrastructure/markdown_publisher.py, use_cases.list_stale_published_files /
delete_stale_published_files). Motivated by a real report: after Honda CR-V 2026
was regenerated under a corrected profile (different function slugs), the
Specifications sidebar showed both the old and new file for the same function
number side by side (e.g. "1-audio-system.md" from a stale run alongside
"1-features.md" from the current one) -- publish() itself never deletes old
files (docs/ARCHITECTURE.md "9."), it only reports them."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.model import FunctionSpec, ManualSpec
from infrastructure.markdown_publisher import MarkdownSpecPublisher


def _spec(manual_id: str, titles: list[str]) -> ManualSpec:
    functions = [
        FunctionSpec(
            function_id=f"f{i}",
            chapter_number=str(i + 1),
            title=title,
            area="Features",
            function_path=f"Features / {title}",
            pages=[1],
        )
        for i, title in enumerate(titles)
    ]
    return ManualSpec(
        manual_id=manual_id,
        maker="Honda",
        model="CR-V 2026",
        document_title="2026 Honda CR-V Owner's Manual",
        scope="Features",
        markets=["US"],
        profile_id="test",
        functions=functions,
    )


def test_republishing_under_a_different_section_cut_reports_the_old_files_as_stale(tmp_path):
    publisher = MarkdownSpecPublisher(tmp_path)
    manual_id = "honda/cr-v-2026/ivi"

    publisher.publish(_spec(manual_id, ["Audio System"]), "features", allow_restricted=True, terms=[])
    assert publisher.list_stale_files(manual_id, "features") == []

    publisher.publish(_spec(manual_id, ["Features", "About Your Audio System"]), "features", allow_restricted=True, terms=[])

    stale = publisher.list_stale_files(manual_id, "features")
    assert stale == ["1-audio-system.md"]
    pub_dir = tmp_path / manual_id / "published" / "features"
    assert (pub_dir / "1-audio-system.md").exists()  # not deleted automatically
    assert (pub_dir / "1-features.md").exists()


def test_delete_stale_files_removes_only_the_reported_files(tmp_path):
    publisher = MarkdownSpecPublisher(tmp_path)
    manual_id = "honda/cr-v-2026/ivi"
    pub_dir = tmp_path / manual_id / "published" / "features"

    publisher.publish(_spec(manual_id, ["Audio System"]), "features", allow_restricted=True, terms=[])
    publisher.publish(_spec(manual_id, ["Features"]), "features", allow_restricted=True, terms=[])
    assert publisher.list_stale_files(manual_id, "features") == ["1-audio-system.md"]

    deleted = publisher.delete_stale_files(manual_id, "features")

    assert deleted == ["1-audio-system.md"]
    assert not (pub_dir / "1-audio-system.md").exists()
    assert (pub_dir / "1-features.md").exists()  # current file untouched
    assert publisher.list_stale_files(manual_id, "features") == []


def test_a_clean_republish_clears_a_previously_stale_manifest(tmp_path):
    """If a human already deleted the stale files (or a later publish just no
    longer has any), the manifest from an earlier publish must not keep
    claiming there's cleanup to do."""
    publisher = MarkdownSpecPublisher(tmp_path)
    manual_id = "honda/cr-v-2026/ivi"

    publisher.publish(_spec(manual_id, ["Audio System"]), "features", allow_restricted=True, terms=[])
    publisher.publish(_spec(manual_id, ["Features"]), "features", allow_restricted=True, terms=[])
    assert publisher.list_stale_files(manual_id, "features") == ["1-audio-system.md"]

    (tmp_path / manual_id / "published" / "features" / "1-audio-system.md").unlink()
    publisher.publish(_spec(manual_id, ["Features"]), "features", allow_restricted=True, terms=[])

    assert publisher.list_stale_files(manual_id, "features") == []
