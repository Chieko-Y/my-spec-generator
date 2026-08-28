"""FastAPI presentation layer. Server-rendered HTML (no SPA), plain forms plus a
small amount of JS for the upload dropzone. This is the only module besides
composition.py that is allowed to know about FastAPI/Starlette types.
"""
from __future__ import annotations

import re
import uuid
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
from domain.overlay import FigureElement, GlossaryTerm

from .composition import build_use_cases
from infrastructure import settings
from infrastructure.markdown_view import render_markdown_to_html

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


def _makers_for_sidebar() -> list[dict]:
    counts: dict[str, int] = {}
    for row in uc.source_registry.list_sources():
        maker = row.get("maker") or "(unknown)"
        counts[maker] = counts.get(maker, 0) + 1
    return [{"name": k, "count": v} for k, v in sorted(counts.items())]


def _render(request: Request, template: str, active_tab: str, **ctx) -> HTMLResponse:
    flash = request.query_params.get("flash")
    flash_kind = request.query_params.get("flash_kind", "ok")
    return templates.TemplateResponse(
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
    return _render(request, "manuals.html", "manuals", sources=sources, license_states=LICENSE_STATES)


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
):
    from domain.slug import slugify

    maker_slug, model_slug, booklet_slug = slugify(maker), slugify(model), slugify(booklet)
    manual_id = f"{maker_slug}/{model_slug}/{booklet_slug}"

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
        msg += f" ({len(result.unmatched_headings)} heading(s) not matched — see index)"
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


@app.get("/specifications", response_class=HTMLResponse)
def specifications_page(request: Request):
    # List every generated chapter, not just published ones — a chapter that was
    # generated but not yet published used to simply not appear anywhere on this
    # page, which looked like the Generate step had silently done nothing (reported
    # directly: "Introduction generated fine but doesn't show up in Specifications").
    # Showing it here as "not published yet" makes the actual state visible instead
    # of requiring the user to remember that Generate and Publish are separate steps.
    #
    # `viewable` re-checks the CURRENT license state, not just whatever it was at
    # publish time — publish only gates the one-time act of writing the files, and
    # without a live re-check here, revoking a license after publishing had zero
    # effect: the already-written files stayed browsable forever. This doesn't
    # delete anything (a later re-review just needs to flip the state back), it only
    # withholds viewing while the state says unreviewed/restricted.
    entries = []
    for s in uc.source_registry.list_sources():
        published = set(_published_chapters(s["manual_id"]))
        license_ok = _license_ok(s["manual_id"])
        for chapter in uc.list_chapters(s["manual_id"]):
            is_published = chapter in published
            entries.append(
                {
                    "manual_id": s["manual_id"],
                    "chapter": chapter,
                    "published": is_published,
                    "viewable": is_published and license_ok,
                    "license_state": s.get("license_state") or "unreviewed",
                }
            )
    return _render(request, "specifications.html", "specifications", entries=entries)


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
def specification_index(request: Request, manual_id: str, chapter: str):
    return _view_published_file(request, manual_id, chapter, "README.md")


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
    files = sorted((p.name for p in pub_dir.glob("*.md")), key=_function_file_sort_key)
    resp = _render(
        request,
        "spec_view.html",
        "specifications",
        manual_id=manual_id,
        chapter=chapter,
        current_file=filename,
        files=files,
        body_html=html,
    )
    resp.headers["Cache-Control"] = "no-cache"
    return resp


# ------------------------------------------------------------------------ Thresholds
@app.get("/thresholds", response_class=HTMLResponse)
def thresholds_page(request: Request):
    entries = []
    for s in uc.source_registry.list_sources():
        for chapter in uc.list_chapters(s["manual_id"]):
            entries.append({"manual_id": s["manual_id"], "chapter": chapter})
    return _render(request, "thresholds_index.html", "thresholds", entries=entries)


@app.get("/thresholds/{manual_id:path}", response_class=HTMLResponse)
def thresholds_manual(request: Request, manual_id: str, chapter: str):
    spec = uc.load_spec(manual_id, chapter)
    if spec is None:
        raise HTTPException(404, "generate this chapter first")
    rows = []
    for f in spec.functions:
        for r in f.requirements:
            for t in r.thresholds:
                rows.append({"function": f.title, "threshold": t})
    return _render(
        request, "thresholds.html", "thresholds",
        manual_id=manual_id, chapter=chapter, rows=rows, statuses=list(ParameterStatus),
    )


@app.post("/thresholds/{manual_id:path}")
def set_threshold(
    manual_id: str,
    chapter: str = Form(...),
    threshold_id: str = Form(...),
    value: str = Form(...),
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
    entries = []
    for s in uc.source_registry.list_sources():
        for chapter in uc.list_chapters(s["manual_id"]):
            entries.append({"manual_id": s["manual_id"], "chapter": chapter})
    return _render(request, "screen_elements_index.html", "screen_elements", entries=entries)


@app.get("/screen-elements/{manual_id:path}", response_class=HTMLResponse)
def screen_elements_manual(request: Request, manual_id: str, chapter: str):
    spec = uc.load_spec(manual_id, chapter)
    if spec is None:
        raise HTTPException(404, "generate this chapter first")
    figures = [(f.title, fig) for f in spec.functions for fig in f.figures]
    elements = uc.load_figure_elements(manual_id, chapter)
    return _render(
        request, "screen_elements.html", "screen_elements",
        manual_id=manual_id, chapter=chapter, figures=figures, elements=elements,
    )


@app.post("/screen-elements/{manual_id:path}")
def add_screen_element(
    manual_id: str,
    chapter: str = Form(...),
    figure_id: str = Form(...),
    symbol: str = Form(...),
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
    return _render(request, "glossary.html", "glossary", terms=terms, categories=list(TermCategory))


@app.post("/glossary")
def add_term(
    in_house_term: str = Form(...),
    category: str = Form(...),
    manual_wordings: str = Form(...),
    evidence: str = Form(...),
):
    import hashlib

    term_id = hashlib.sha256(in_house_term.encode("utf-8")).hexdigest()[:12]
    wordings = [w.strip() for w in manual_wordings.split(",") if w.strip()]
    try:
        uc.set_term(
            GlossaryTerm(
                term_id=term_id, in_house_term=in_house_term, category=TermCategory(category),
                manual_wordings=wordings, evidence=evidence,
            )
        )
    except (ValueError, ValidationError) as e:
        return _redirect("/glossary", str(e), "error")
    return _redirect("/glossary", "saved")


@app.post("/glossary/delete")
def delete_term(term_id: str = Form(...)):
    uc.delete_term(term_id)
    return _redirect("/glossary", "deleted")
