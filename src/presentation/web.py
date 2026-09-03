"""FastAPI presentation layer. Server-rendered HTML (no SPA), plain forms plus a
small amount of JS for the upload dropzone. This is the only module besides
composition.py that is allowed to know about FastAPI/Starlette types.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from application.use_cases import (
    LICENSE_STATES,
    ChapterAllowlistError,
    GenerateError,
    PublishBlockedError,
    ValidationError,
    is_publishable_license,
)
from domain.manual_parsing import ConfirmedChapter
from domain.model import ParameterStatus, TermCategory
from domain.overlay import FigureElement, GlossaryTerm, ManualWording
from domain.slug import slugify
from domain.vehicle_catalog import MAKERS, MODELS_BY_MAKER

from .composition import build_use_cases
from infrastructure import settings
from infrastructure.markdown_publisher import combined_markdown
from infrastructure.markdown_view import highlight_glossary_terms, render_markdown_to_html

APP_NAME = "Owner's Manual Spec Generator"

app = FastAPI(title=APP_NAME)
app.mount("/static", StaticFiles(directory=str(settings.PROJECT_ROOT / "static")), name="static")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

uc = build_use_cases()


@app.exception_handler(ValidationError)
@app.exception_handler(GenerateError)
@app.exception_handler(PublishBlockedError)
async def _application_error_handler(request: Request, exc: Exception):
    # Safety net: every route that can raise one of these already catches it and
    # redirects with a flash message. This handler exists so a route that forgets
    # to (or a new route added later) fails as a readable 400, not a bare 500 —
    # a mismatch between the app-level exception types here and a bare
    # `except ValueError` was caught this way during manual testing (glossary's
    # duplicate-wording rejection raised ValidationError, not ValueError).
    return PlainTextResponse(str(exc), status_code=400)


def _registration_years() -> list[int]:
    """2000 through the current year, newest first -- the form's model-year
    picker. A manual older than 2000 (or from a maker/model not in
    vehicle_catalog) is still fully supported via the form's own "Other"
    free-text fallback."""
    return list(range(date.today().year, 1999, -1))


_chapter_order_cache: dict[str, list[str]] = {}


def _chapter_display_order(manual_id: str) -> list[str]:
    """Chapter slugs in the manual's own order (confirmed TOC/running-head
    allowlist order, or raw PDF bookmark order), not the alphabetical order
    list_chapters() returns from sorting generated/ folder names. Cached for
    the process lifetime -- list_available_chapters() can re-read the PDF, and
    the sidebar recomputes this on every page render, so re-deriving it per
    request would mean re-opening every registered manual's PDF on every page
    load in the app."""
    if manual_id not in _chapter_order_cache:
        try:
            labels = uc.list_available_chapters(manual_id)["chapters"]
        except Exception:
            labels = []
        _chapter_order_cache[manual_id] = [slugify(label) for label in labels]
    return _chapter_order_cache[manual_id]


def _sort_chapters_by_manual_order(manual_id: str, chapter_slugs: list[str]) -> list[str]:
    order = _chapter_display_order(manual_id)
    rank = {slug: i for i, slug in enumerate(order)}
    # A chapter slug that doesn't match anything in `order` (e.g. it was
    # generated under a hand-typed name that doesn't match the PDF's own
    # chapter label) still needs to show up somewhere -- sorted alphabetically
    # after every chapter we could place, rather than dropped.
    return sorted(chapter_slugs, key=lambda s: (rank.get(s, len(order)), s))


def _viewable_chapters_in_order(manual_id: str) -> list[str]:
    """Published, license-viewable chapter slugs, in the manual's own chapter
    order -- shared by the sidebar accordion and the combined ("whole book")
    spec view, so the two can never disagree about which chapters count or
    what order they come in."""
    if not _license_ok(manual_id):
        return []
    published = set(_published_chapters(manual_id))
    viewable = [c for c in uc.list_chapters(manual_id) if c in published]
    return _sort_chapters_by_manual_order(manual_id, viewable)


def _makers_for_sidebar() -> list[dict]:
    # Just the maker -> model x year list -- one click on a model goes straight
    # to that manual's own Specifications page (spec_view.html), which has its
    # own chapter/file navigation. Keeping this sidebar list flat (no nested
    # per-model chapter list) was an explicit user call: the global sidebar is
    # for finding a manual, not for browsing inside one.
    by_maker: dict[str, list[dict]] = {}
    for row in uc.source_registry.list_sources():
        maker = row.get("maker") or "(unknown)"
        manual_id = row["manual_id"]
        by_maker.setdefault(maker, []).append(
            {"manual_id": manual_id, "model": row.get("model") or manual_id}
        )
    return [
        {
            "name": maker,
            "count": len(manuals),
            "manuals": sorted(manuals, key=lambda m: m["model"]),
        }
        for maker, manuals in sorted(by_maker.items())
    ]


def _render(request: Request, template: str, active_tab: str, **ctx) -> HTMLResponse:
    flash = request.query_params.get("flash")
    flash_kind = request.query_params.get("flash_kind", "ok")
    resp = templates.TemplateResponse(
        request,
        template,
        {
            "app_name": APP_NAME,
            "active_tab": active_tab,
            "makers": _makers_for_sidebar(),
            "flash": flash,
            "flash_kind": flash_kind,
            **ctx,
        },
    )
    # Every page here reflects on-disk generated/overlay state that changes
    # between requests (re-generate, save a threshold, etc.) -- without this,
    # a browser can serve a stale cached copy after data changes underneath
    # it (confirmed report, 2026-08-31: Thresholds looked unchanged after a
    # real fix landed and the page was reloaded). _render_spec_view used to
    # set this only for itself; centralizing it here covers every page
    # (Thresholds/Screen elements/Glossary included) the same way.
    resp.headers["Cache-Control"] = "no-cache"
    return resp


def _redirect(path: str, flash: str, kind: str = "ok") -> RedirectResponse:
    from urllib.parse import quote

    sep = "&" if "?" in path else "?"
    return RedirectResponse(f"{path}{sep}flash={quote(flash)}&flash_kind={kind}", status_code=303)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/manuals")


# --------------------------------------------------------------------------- Manuals
@app.get("/manuals", response_class=HTMLResponse)
def manuals_page(request: Request):
    sources = uc.source_registry.list_sources()
    maker_filter = request.query_params.get("maker")
    if maker_filter:
        sources = [s for s in sources if s.get("maker") == maker_filter]
    for s in sources:
        # A manual_id is registered once for the whole book; "generate" can be run
        # for any number of its chapters afterwards, each kept separately. This
        # lists whichever chapters already have a generated spec, instead of the
        # single "Chapter" scalar the app used to show (which wrongly implied the
        # registration itself was scoped to just one chapter).
        s["chapters"] = uc.list_chapters(s["manual_id"])
        s["published_chapters"] = set(_published_chapters(s["manual_id"]))
        s["license_ok"] = is_publishable_license(s.get("license_state") or "unreviewed")
        s["busy_chapters"] = uc.busy_chapters(s["manual_id"])
    return _render(
        request,
        "manuals.html",
        "manuals",
        sources=sources,
        license_states=LICENSE_STATES,
        catalog_makers=MAKERS,
        catalog_models_json=json.dumps(MODELS_BY_MAKER),
        registration_years=_registration_years(),
        # Unfiltered, regardless of ?maker= — the overwrite-warning check (see
        # manuals.html) needs every registered manual_id, not just whichever
        # maker the sidebar happens to be filtered to right now.
        existing_manual_ids_json=json.dumps([row["manual_id"] for row in uc.source_registry.list_sources()]),
    )


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """Used by BOTH the drag-and-drop dropzone and the plain <input type=file>
    fallback in manuals.html — same endpoint, same handling either way, so an
    upload never behaves differently depending on which one the user's browser
    lets them use (this app's fix for bug report #1: drag-and-drop not working)."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "only .pdf files can be registered")

    content = await file.read()
    inbox_id = uuid.uuid4().hex[:12]
    inbox_path = uc.original_library.store_inbox(inbox_id, file.filename, content)

    try:
        page_count, bookmarks = uc.preview_outline(inbox_path)
    except Exception as e:  # pdfium/pdfplumber couldn't open it — F-1-10
        raise HTTPException(400, f"could not open as a PDF: {e}")

    identity = uc.preview_identity(inbox_path)
    top_bookmarks = [b.title for b in bookmarks if b.level == (min((x.level for x in bookmarks), default=0))][:20]

    return {
        "inbox_path": inbox_path,
        "filename": file.filename,
        "page_count": page_count,
        "bookmark_count": len(bookmarks),
        "top_bookmarks": top_bookmarks,
        "shallow_outline": len(bookmarks) > 0 and max((b.level for b in bookmarks), default=0) < 1,
        "identity": {
            "maker": identity.maker,
            "model": identity.model,
            "year": identity.year,
            "evidence": identity.evidence,
        },
    }


@app.post("/register")
def register(
    inbox_path: str = Form(...),
    maker: str = Form(...),
    model: str = Form(...),
    booklet: str = Form(...),
    title: str = Form(""),
    source_url: str = Form(""),
    retrieved_at: str = Form(""),
    markets: str = Form(""),
    license_state: str = Form("unreviewed"),
    confirm_overwrite: str = Form(""),
):
    from domain.slug import slugify

    maker_slug, model_slug, booklet_slug = slugify(maker), slugify(model), slugify(booklet)
    manual_id = f"{maker_slug}/{model_slug}/{booklet_slug}"

    # Registering an already-registered manual_id silently overwrote both its
    # metadata and its original PDF file on disk (OriginalLibrary.commit_inbox
    # writes to the same maker/model/original/<filename> path with no existence
    # check) -- confirmed as a real risk once maker/model became pick-lists,
    # since it's now easy to reselect an existing combination by accident. The
    # form's own JS warns and requires a checkbox before submitting, but that is
    # only a convenience; this is the actual gate, since JS can be skipped/wrong.
    if confirm_overwrite != "1" and uc.source_registry.get(manual_id) is not None:
        return _redirect(
            "/manuals",
            f"{manual_id} is already registered — check the overwrite-confirmation box and resubmit if this is intentional.",
            "error",
        )

    try:
        final_path = uc.original_library.commit_inbox(inbox_path, maker, model)
        uc.register_source(
            manual_id,
            {
                "maker": maker,
                "model": model,
                "title": title,
                "local_path": final_path,
                "source_url": source_url,
                "retrieved_at": retrieved_at,
                "markets": [m.strip() for m in markets.split(",") if m.strip()],
                "license_state": license_state,
            },
        )
    except (ValidationError, FileNotFoundError) as e:
        return _redirect("/manuals", f"registration failed: {e}", "error")

    return _redirect("/manuals", f"registered {manual_id}")


@app.post("/edit-source")
def edit_source(
    manual_id: str = Form(...),
    maker: str = Form(...),
    model: str = Form(...),
    title: str = Form(""),
    source_url: str = Form(""),
    retrieved_at: str = Form(""),
    markets: str = Form(""),
    license_state: str = Form(...),
):
    """Editing maker/model/title/license_state etc. after registration used to
    require re-registering the whole manual (re-uploading the PDF via /register,
    which always needs an inbox_path) — there was no way to fix a typo or flip
    unreviewed -> internal_use_permitted without going through intake again.
    register_source() only merges the fields it's given, so this can update the
    display metadata without touching the PDF or local_path at all.

    manual_id itself is deliberately NOT editable here: it's the directory name
    under both the library and workspace, so renaming it would mean moving the PDF
    and every generated/overlay/published file to match — a real migration, not a
    metadata edit. Out of scope until there's an actual need for it.
    """
    try:
        uc.register_source(
            manual_id,
            {
                "maker": maker,
                "model": model,
                "title": title,
                "source_url": source_url,
                "retrieved_at": retrieved_at,
                "markets": [m.strip() for m in markets.split(",") if m.strip()],
                "license_state": license_state,
            },
        )
    except ValidationError as e:
        return _redirect("/manuals", str(e), "error")
    return _redirect("/manuals", f"{manual_id}: details updated")


@app.get("/api/chapters/{manual_id:path}")
def api_chapters(manual_id: str):
    """Backs the "generate…" panel. Resolves this manual's profile first
    (see UseCases.resolve_manual_profile) rather than assuming one is already
    known: a manual that fits an existing profile gets assigned to it and its
    chapters returned immediately (no human step); a manual with no confirmed
    chapter allowlist yet, or that fits no existing profile at all, comes back
    as {"status": "needs_review", ...} for manuals.html to render a review
    panel instead of a chapter dropdown."""
    try:
        resolution = uc.resolve_manual_profile(manual_id)
    except GenerateError:
        raise HTTPException(404, "manual_id not registered")
    except FileNotFoundError as e:
        raise HTTPException(404, f"original PDF not found on disk: {e}")

    if resolution.status == "ready":
        data = uc.list_available_chapters(manual_id)
        data["status"] = "ready"
        return data

    return {
        "status": "needs_review",
        "profile_id": resolution.profile_id,
        "profile_is_new": resolution.profile_is_new,
        "layout": resolution.layout,
        "derived_from": resolution.derived_from,
        "section_source": resolution.section_source,
        "notes": resolution.notes,
        "toc_chapters": [
            {
                "label": c.label,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "printed_page": c.printed_page,
            }
            for c in resolution.toc_chapters
        ],
        "running_head_candidates": [
            {"label": c.label, "page_start": c.page_start, "page_end": c.page_end}
            for c in resolution.running_head_candidates
        ],
    }


@app.post("/api/activate-profile")
async def api_activate_profile(request: Request):
    """Confirms one resolve_manual_profile needs_review result (see
    api_chapters above): saves the new profile when profile_is_new, assigns it
    to manual_id, and confirms whichever chapters the reviewer kept. A JSON
    body, not a Form -- the payload (a nested layout dict, a variable-length
    chapter list) doesn't fit flat form fields, and this is only ever called
    from manuals.html's fetch(), never a plain <form> submission."""
    body = await request.json()
    manual_id = body.get("manual_id", "")
    profile_id = body.get("profile_id", "")
    if not manual_id or not profile_id:
        raise HTTPException(400, "manual_id and profile_id are required")

    chapters_raw = body.get("chapters")
    chapters = (
        [
            ConfirmedChapter(label=c["label"], page_start=c["page_start"], page_end=c["page_end"])
            for c in chapters_raw
        ]
        if chapters_raw is not None
        else None
    )

    try:
        uc.activate_derived_profile(
            manual_id,
            profile_id,
            layout=body.get("layout"),
            derived_from=body.get("derived_from"),
            chapters=chapters,
        )
    except (ValidationError, ChapterAllowlistError, FileExistsError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/generate")
def generate(manual_id: str = Form(...), chapter_prefix: str = Form(...), chapter_label: str = Form("")):
    try:
        result = uc.generate(manual_id, chapter_prefix or None, chapter_label=chapter_label or chapter_prefix)
    except GenerateError as e:
        msg = str(e)
        if e.available_chapters:
            msg += " Available: " + ", ".join(e.available_chapters[:8])
        return _redirect("/manuals", msg, "error")
    c = result.spec.counts()
    msg = f"{manual_id} — {chapter_prefix}: generated {c['functions']} functions / {c['requirements']} requirements"
    if result.unmatched_headings:
        # Not surfaced in the published README (see markdown_publisher.py) --
        # a reviewer has no way to act on this, only whoever ran generate()
        # can investigate the matching code. Printed to the server's own
        # console (same audience as specgen.py generate's stdout) rather than
        # just the flash banner, since the full title list can be long.
        print(f"{len(result.unmatched_headings)} heading(s) could not be matched to body text:")
        for title in result.unmatched_headings:
            print(f"  - {title}")
        msg += f" ({len(result.unmatched_headings)} heading(s) used a coarser page-based boundary — see server console)"
    return _redirect("/manuals", msg)


@app.post("/publish")
def publish(manual_id: str = Form(...), chapter: str = Form(...), allow_restricted: str = Form("")):
    try:
        files = uc.publish(manual_id, chapter, allow_restricted=bool(allow_restricted))
    except PublishBlockedError as e:
        return _redirect("/manuals", f"publish blocked: {e}", "error")
    return _redirect("/manuals", f"{manual_id} — {chapter}: published {len(files)} file(s)")


# --------------------------------------------------------------------- Specifications
def _published_chapters(manual_id: str) -> list[str]:
    pub_root = settings.WORKSPACE_DIR / manual_id / "published"
    if not pub_root.exists():
        return []
    return sorted(p.name for p in pub_root.iterdir() if p.is_dir() and (p / "README.md").exists())


def _license_ok(manual_id: str) -> bool:
    row = uc.source_registry.get(manual_id)
    license_state = (row or {}).get("license_state", "unreviewed")
    return is_publishable_license(license_state)


def _manual_maker(manual_id: str) -> str:
    row = uc.source_registry.get(manual_id)
    return (row or {}).get("maker") or ""


@app.get("/specifications", response_class=HTMLResponse)
def specifications_page(request: Request):
    # One row per registered manual, linking straight to its unified spec view
    # (/specifications/{manual_id}, which defaults to the whole-book combined
    # README) -- the same manual list the sidebar shows, so the top-nav
    # "Specifications" link and the sidebar always agree on where a manual's
    # spec lives instead of the nav link landing on a separate, older flat
    # per-chapter listing (a real inconsistency reported directly, 2026-08-30).
    # Per-chapter authoring status (generated/published/Publish button) is the
    # Manuals tab's job; this page only needs to say whether there's anything
    # to actually read yet, and why not if not --
    # `_viewable_chapters_in_order` re-checks the CURRENT license state, not
    # just whatever it was at publish time, so revoking a license after
    # publishing is reflected here too, not just advisory.
    manuals = []
    for s in uc.source_registry.list_sources():
        manual_id = s["manual_id"]
        viewable_count = len(_viewable_chapters_in_order(manual_id))
        published_count = len(_published_chapters(manual_id))
        manuals.append(
            {
                "manual_id": manual_id,
                "maker": s.get("maker") or "",
                "model": s.get("model") or manual_id,
                "viewable_count": viewable_count,
                "license_state": s.get("license_state") or "unreviewed",
                "blocked": published_count > 0 and viewable_count == 0,
            }
        )
    manuals.sort(key=lambda m: (m["maker"], m["model"]))
    by_maker: dict[str, list[dict]] = {}
    for m in manuals:
        by_maker.setdefault(m["maker"] or "(unknown)", []).append(m)
    grouped = [{"name": maker, "manuals": rows} for maker, rows in sorted(by_maker.items())]
    return _render(request, "specifications.html", "specifications", grouped=grouped)


@app.get("/specifications/{manual_id:path}/file/{filename}", response_class=HTMLResponse)
def specification_file(request: Request, manual_id: str, filename: str, chapter: str):
    return _view_published_file(request, manual_id, chapter, filename)


# The markdown a function file embeds is "![figure](../figures/FIG-xxx.png)" — a
# path meant for opening the .md file directly off disk, where ".." is a real
# parent directory. Rendered into HTML and served from
# /specifications/{manual_id}/file/{filename}, the same "../figures/xxx.png" is
# instead resolved by the BROWSER against that URL, landing on
# /specifications/{manual_id}/figures/xxx.png — which had no route at all, so every
# figure 404'd silently (reported directly: caption and source line rendered, image
# did not, 2026-08-25). This route is what that browser-resolved URL needs to hit.
# Must be registered before the {manual_id:path} catch-all below, same reason as
# specification_file above.
@app.get("/specifications/{manual_id:path}/figures/{filename}")
def specification_figure(manual_id: str, filename: str):
    if "/" in filename or ".." in filename:
        raise HTTPException(404)
    if not _license_ok(manual_id):
        raise HTTPException(403, "license state is not internal_use_permitted")
    path = settings.WORKSPACE_DIR / manual_id / "published" / "figures" / filename
    if not path.exists():
        raise HTTPException(404, "figure not found — run generate for this chapter to render it")
    return FileResponse(path)


# {manual_id:path} is greedy — it matches ANY path under /specifications/, including
# .../file/xxx.md. Starlette tries routes in registration order and uses the first
# match, so this less-specific route MUST be registered after specification_file
# above, or every "view this function file" link 404s and only README.md is ever
# reachable (found by clicking an individual function link during manual testing —
# the sidebar listed all the files correctly, but every one of them 404'd).
@app.get("/specifications/{manual_id:path}", response_class=HTMLResponse)
def specification_index(request: Request, manual_id: str, chapter: str | None = None):
    # No ?chapter= at all (as opposed to any specific chapter slug) means "the
    # whole manual as one book" -- the combined view, and the page's own
    # default (a maker/model link in the sidebar points straight here). This
    # is also what the specifications-list "All chapters, combined" link
    # points at, so a bare manual_id always means the same thing everywhere.
    if chapter is None:
        return _view_combined_spec(request, manual_id)
    return _view_published_file(request, manual_id, chapter, "README.md")


def _view_combined_spec(request: Request, manual_id: str) -> HTMLResponse:
    if not _license_ok(manual_id):
        raise HTTPException(
            403,
            f"{manual_id}'s license state is not internal_use_permitted — viewing is "
            "withheld until it's re-reviewed and set from the Manuals tab. The published "
            "files themselves have not been deleted.",
        )
    chapters = _viewable_chapters_in_order(manual_id)
    spec = uc.load_combined_spec(manual_id, chapters) if chapters else None
    if spec is None:
        raise HTTPException(404, "nothing published yet for this manual — publish at least one chapter first")

    terms = uc.load_glossary()
    html = render_markdown_to_html(combined_markdown(spec, terms))
    html = highlight_glossary_terms(html, terms, spec.maker)
    return _render_spec_view(request, manual_id, html, chapter=None, current_file=None)


_LEADING_NUMBER = re.compile(r"^(\d+)-")


def _function_file_sort_key(filename: str) -> tuple[int, str]:
    # Filenames are "<chapter_number>-<slug>.md" (e.g. "10-recents-screen.md"); a
    # plain string sort puts "10" before "2", so the sidebar listed functions
    # out of the manual's own order (reported directly against a real published
    # chapter, 2026-08-25). Sort by the leading number instead.
    m = _LEADING_NUMBER.match(filename)
    return (int(m.group(1)), filename) if m else (10**9, filename)


def _view_published_file(request: Request, manual_id: str, chapter: str, filename: str) -> HTMLResponse:
    if "/" in filename or ".." in filename or "/" in chapter or ".." in chapter:
        raise HTTPException(404)
    if not _license_ok(manual_id):
        # Files may already exist on disk from an earlier publish, but the license
        # state governing this manual has since been set back to
        # unreviewed/restricted — re-checked here, not just at publish time, so
        # revoking it actually takes effect instead of being purely advisory.
        raise HTTPException(
            403,
            f"{manual_id}'s license state is not internal_use_permitted — viewing is "
            "withheld until it's re-reviewed and set from the Manuals tab. The published "
            "files themselves have not been deleted.",
        )
    pub_dir = settings.WORKSPACE_DIR / manual_id / "published" / chapter
    path = pub_dir / filename
    if not path.exists():
        raise HTTPException(404, "not published yet — run generate then publish for this chapter")

    html = render_markdown_to_html(path.read_text(encoding="utf-8"))
    html = highlight_glossary_terms(html, uc.load_glossary(), _manual_maker(manual_id))
    return _render_spec_view(request, manual_id, html, chapter=chapter, current_file=filename)


def _spec_nav(manual_id: str) -> list[dict]:
    """Left-panel data for spec_view.html: every viewable chapter, in manual
    order, each with its own function files (README excluded -- the template
    always links to a chapter's README separately, as that chapter
    accordion's first item) -- computed for every chapter regardless of which
    one is currently being viewed, so the whole nav tree is always visible,
    not just the active chapter's files."""
    nav = []
    for chapter in _viewable_chapters_in_order(manual_id):
        pub_dir = settings.WORKSPACE_DIR / manual_id / "published" / chapter
        files = sorted(
            (p.name for p in pub_dir.glob("*.md") if p.name != "README.md"),
            key=_function_file_sort_key,
        )
        nav.append({"chapter": chapter, "files": files})
    return nav


def _render_spec_view(
    request: Request, manual_id: str, body_html: str, chapter: str | None, current_file: str | None
) -> HTMLResponse:
    return _render(
        request,
        "spec_view.html",
        "specifications",
        manual_id=manual_id,
        nav=_spec_nav(manual_id),
        chapter=chapter,
        current_file=current_file,
        body_html=body_html,
    )


def _chapters_by_maker_and_manual() -> list[dict]:
    """Every registered manual's chapters, grouped maker -> model x year -> chapter
    -- one level deeper than _makers_for_sidebar (which stops at model, since the
    sidebar only needs to find a manual). Used by the Thresholds index so a tester
    can find "this maker's this model's this chapter" the same way the sidebar
    already groups manuals, rather than scanning one long flat list."""
    by_maker: dict[str, dict[str, dict]] = {}
    for row in uc.source_registry.list_sources():
        maker = row.get("maker") or "(unknown)"
        manual_id = row["manual_id"]
        manuals = by_maker.setdefault(maker, {})
        manuals[manual_id] = {
            "manual_id": manual_id,
            "model": row.get("model") or manual_id,
            "chapters": list(uc.list_chapters(manual_id)),
        }
    return [
        {
            "name": maker,
            "manuals": sorted(manuals.values(), key=lambda m: m["model"]),
        }
        for maker, manuals in sorted(by_maker.items())
    ]


# ------------------------------------------------------------------------ Thresholds
@app.get("/thresholds", response_class=HTMLResponse)
def thresholds_page(request: Request):
    return _render(request, "thresholds_index.html", "thresholds", grouped=_chapters_by_maker_and_manual())


@app.get("/thresholds/{manual_id:path}", response_class=HTMLResponse)
def thresholds_manual(request: Request, manual_id: str, chapter: str):
    spec = uc.load_spec(manual_id, chapter)
    if spec is None:
        raise HTTPException(404, "generate this chapter first")
    groups = []
    for f in spec.functions:
        rows = []
        for r in f.requirements:
            for t in r.thresholds:
                rows.append({
                    "function_path": f.function_path,
                    "source": r.source,
                    "page_citation": r.page_citation,
                    "next_step_text": r.next_step_text,
                    "threshold": t,
                })
        if rows:
            groups.append({
                "chapter_number": f.chapter_number,
                "function": f.title,
                "unfilled_count": sum(1 for row in rows if row["threshold"].status == ParameterStatus.UNFILLED),
                "rows": rows,
            })
    return _render(
        request, "thresholds.html", "thresholds",
        manual_id=manual_id, chapter=chapter, groups=groups, statuses=list(ParameterStatus),
    )


@app.post("/thresholds/{manual_id:path}")
def set_threshold(
    manual_id: str,
    chapter: str = Form(...),
    threshold_id: str = Form(...),
    value: str = Form(""),
    status: str = Form(...),
    evidence: str = Form(...),
    filled_by: str = Form(...),
):
    try:
        uc.set_parameter(manual_id, chapter, threshold_id, value, ParameterStatus(status), evidence, filled_by)
    except ValueError as e:
        return _redirect(f"/thresholds/{manual_id}?chapter={chapter}", str(e), "error")
    return _redirect(f"/thresholds/{manual_id}?chapter={chapter}", "saved")


# -------------------------------------------------------------------- Screen elements
@app.get("/screen-elements", response_class=HTMLResponse)
def screen_elements_page(request: Request):
    return _render(
        request, "screen_elements_index.html", "screen_elements",
        grouped=_chapters_by_maker_and_manual(),
    )


@app.get("/screen-elements/{manual_id:path}", response_class=HTMLResponse)
def screen_elements_manual(request: Request, manual_id: str, chapter: str):
    spec = uc.load_spec(manual_id, chapter)
    if spec is None:
        raise HTTPException(404, "generate this chapter first")
    elements = uc.load_figure_elements(manual_id, chapter)
    elements_by_figure: dict[str, list] = {}
    for e in elements:
        elements_by_figure.setdefault(e.figure_id, []).append(e)

    rows = []
    for f in spec.functions:
        for i, fig in enumerate(f.figures, start=1):
            rows.append({
                "function_number": f.chapter_number,
                "function_title": f.title,
                "index": i,
                "figure": fig,
                "image_filename": f"FIG-{fig.figure_id}.png",
                "width": round(fig.rect[2] - fig.rect[0]),
                "height": round(fig.rect[3] - fig.rect[1]),
                "elements": elements_by_figure.get(fig.figure_id, []),
            })
    return _render(
        request, "screen_elements.html", "screen_elements",
        manual_id=manual_id, chapter=chapter, rows=rows,
        figure_count=len(rows), element_count=len(elements),
    )


# {manual_id:path} is greedy, same trap as specification_file above -- a POST to
# .../delete would otherwise be swallowed by add_screen_element's own
# {manual_id:path} route (treating "...manual_id.../delete" as the manual_id
# itself). This more-specific route must be registered first.
@app.post("/screen-elements/{manual_id:path}/delete")
def delete_screen_element(
    manual_id: str,
    chapter: str = Form(...),
    figure_id: str = Form(...),
    symbol: str = Form(""),
    label: str = Form(...),
):
    uc.remove_figure_element(manual_id, chapter, figure_id, symbol, label)
    return _redirect(f"/screen-elements/{manual_id}?chapter={chapter}", "deleted")


@app.post("/screen-elements/{manual_id:path}")
def add_screen_element(
    manual_id: str,
    chapter: str = Form(...),
    figure_id: str = Form(...),
    symbol: str = Form(""),
    label: str = Form(...),
    note: str = Form(""),
    decided_by: str = Form(...),
):
    try:
        uc.add_figure_element(
            manual_id, chapter,
            FigureElement(figure_id=figure_id, symbol=symbol, label=label, note=note, decided_by=decided_by),
        )
    except ValueError as e:
        return _redirect(f"/screen-elements/{manual_id}?chapter={chapter}", str(e), "error")
    return _redirect(f"/screen-elements/{manual_id}?chapter={chapter}", "saved")


# ------------------------------------------------------------------------- Glossary
@app.get("/glossary", response_class=HTMLResponse)
def glossary_page(request: Request):
    terms = uc.load_glossary()
    by_category: dict[TermCategory, list] = {c: [] for c in TermCategory}
    for t in terms:
        by_category[t.category].append(t)
    groups = [{"category": c, "terms": ts} for c, ts in by_category.items() if ts]
    # Only makers that actually have a manual registered -- the maker picker on
    # this form is for scoping a wording to one of THOSE, not the full 36-maker
    # catalog the Manuals tab uses to register a new source.
    registered_makers = sorted({s["maker"] for s in uc.source_registry.list_sources() if s.get("maker")})
    return _render(
        request, "glossary.html", "glossary",
        groups=groups, categories=list(TermCategory), registered_makers=registered_makers,
    )


@app.post("/glossary")
def add_term(
    in_house_term: str = Form(...),
    meaning: str = Form(""),
    category: str = Form(...),
    manual_wordings: str = Form(...),
    evidence: str = Form(...),
    filled_by: str = Form(...),
    notes: str = Form(""),
):
    import hashlib

    term_id = hashlib.sha256(in_house_term.encode("utf-8")).hexdigest()[:12]
    # One wording per line, "<text>" or "<text> | <maker>" (maker omitted = every
    # maker) -- matches the original app's own registration form shape.
    wordings = []
    for line in manual_wordings.splitlines():
        line = line.strip()
        if not line:
            continue
        text, _, maker = line.partition("|")
        wordings.append(ManualWording(text=text.strip(), maker=maker.strip().lower()))
    try:
        uc.set_term(
            GlossaryTerm(
                term_id=term_id, in_house_term=in_house_term, meaning=meaning,
                category=TermCategory(category), manual_wordings=wordings,
                evidence=evidence, filled_by=filled_by, notes=notes,
            )
        )
    except (ValueError, ValidationError) as e:
        return _redirect("/glossary", str(e), "error")
    return _redirect("/glossary", "saved")


@app.post("/glossary/delete")
def delete_term(term_id: str = Form(...)):
    uc.delete_term(term_id)
    return _redirect("/glossary", "deleted")
