"""Regression test for a real routing bug found in manual testing: FastAPI/Starlette
tries routes in registration order, and `{manual_id:path}` is greedy enough to match
ANY path under /specifications/ — including .../file/xxx.md. With the plain chapter
index route registered before the /file/{filename} route, every "open this function
file" link 404'd (the sidebar listed the files correctly, since that part is server-
rendered from the real directory listing, but every link was dead — only README.md
was ever reachable). Fixed by registering the more specific route first.

This needs the actual FastAPI app + real filesystem (env vars point it at a temp
workspace/library), not a use_cases-level test, because the bug was in URL routing
itself and use_cases was never involved.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SPECGEN_LIBRARY_DIR", str(tmp_path / "library"))
    monkeypatch.setenv("SPECGEN_WORKSPACE_DIR", str(tmp_path / "workspace"))
    monkeypatch.setenv("SPECGEN_CONFIG_DIR", str(PROJECT_ROOT / "config"))
    monkeypatch.setenv("SPECGEN_STATIC_DIR", str(PROJECT_ROOT / "static"))
    sys.path.insert(0, str(SRC))

    # settings.py reads env vars at import time, and web.py builds its `uc` singleton
    # at import time too, so every module that captured stale paths from a previous
    # test's env vars must be evicted before re-importing under the new ones.
    for name in list(sys.modules):
        if name == "infrastructure" or name.startswith("infrastructure.") or name in (
            "presentation.web",
            "presentation.composition",
        ):
            del sys.modules[name]

    from fastapi.testclient import TestClient

    from presentation.web import app, uc

    workspace = tmp_path / "workspace"
    manual_id = "toyota/rav4-2026/multimedia"
    uc.register_source(
        manual_id,
        {"maker": "Toyota", "model": "RAV4 2026", "title": "Multimedia", "license_state": "internal_use_permitted"},
    )

    published_dir = workspace / manual_id / "published" / "navigation"
    published_dir.mkdir(parents=True)
    (published_dir / "README.md").write_text("# Index\n", encoding="utf-8")
    (published_dir / "1-map-screen.md").write_text("# 1. Map screen\nsome body text\n", encoding="utf-8")

    # list_chapters() (used by the /specifications listing) reads generated/*/spec.json,
    # not the published/ directory — a real publish always follows a real generate, so
    # this fixture needs a matching (content doesn't matter here) generated spec too.
    generated_dir = workspace / manual_id / "generated" / "navigation"
    generated_dir.mkdir(parents=True)
    (generated_dir / "spec.json").write_text("{}", encoding="utf-8")

    return TestClient(app)


def test_function_file_link_is_not_swallowed_by_the_index_route(client):
    resp = client.get(
        "/specifications/toyota/rav4-2026/multimedia/file/1-map-screen.md",
        params={"chapter": "navigation"},
        follow_redirects=False,
    )
    assert resp.status_code == 200, resp.text
    assert "Map screen" in resp.text
    assert "some body text" in resp.text


def test_chapter_index_still_works(client):
    resp = client.get(
        "/specifications/toyota/rav4-2026/multimedia", params={"chapter": "navigation"}, follow_redirects=False
    )
    assert resp.status_code == 200, resp.text
    assert "Index" in resp.text


def test_revoking_license_after_publish_blocks_viewing(client):
    # Regression test: publish only checked license_state at the moment it ran.
    # Files already written to disk stayed browsable forever afterwards even if the
    # license state was later set back to unreviewed/restricted — the safeguard had
    # no effect once publish had already happened once. Specification viewing must
    # re-check the CURRENT license state, not rely on whatever it was at publish time.
    from presentation.web import uc

    manual_id = "toyota/rav4-2026/multimedia"

    resp = client.get(
        "/specifications/toyota/rav4-2026/multimedia", params={"chapter": "navigation"}, follow_redirects=False
    )
    assert resp.status_code == 200  # license_state="internal_use_permitted" from the fixture

    uc.register_source(manual_id, {"license_state": "unreviewed"})

    resp = client.get(
        "/specifications/toyota/rav4-2026/multimedia", params={"chapter": "navigation"}, follow_redirects=False
    )
    assert resp.status_code == 403, resp.text

    resp = client.get(
        "/specifications/toyota/rav4-2026/multimedia/file/1-map-screen.md",
        params={"chapter": "navigation"},
        follow_redirects=False,
    )
    assert resp.status_code == 403, resp.text

    # the file itself must still exist on disk — this withholds viewing, it doesn't delete
    from infrastructure import settings

    assert (settings.WORKSPACE_DIR / manual_id / "published" / "navigation" / "README.md").exists()

    resp = client.get("/specifications", follow_redirects=False)
    assert "published, but license is unreviewed" in resp.text


def test_manuals_page_hides_view_link_when_license_is_not_ok(client):
    # Regression test: the Manuals page's per-chapter "View" link only checked
    # whether a chapter was published, not whether the CURRENT license state still
    # allows viewing it — reported directly: after setting license back to
    # unreviewed, the View button for an already-published chapter was still shown
    # and clickable (it 403'd on click, since _view_published_file was already
    # fixed, but showing a doomed-to-fail link is still a bug in its own right).
    from presentation.web import uc

    manual_id = "toyota/rav4-2026/multimedia"

    resp = client.get("/manuals", follow_redirects=False)
    assert f'href="/specifications/{manual_id}?chapter=navigation"' in resp.text
    assert ">View</a>" in resp.text

    uc.register_source(manual_id, {"license_state": "unreviewed"})

    resp = client.get("/manuals", follow_redirects=False)
    assert f'href="/specifications/{manual_id}?chapter=navigation"' not in resp.text
    assert "not viewable" in resp.text
