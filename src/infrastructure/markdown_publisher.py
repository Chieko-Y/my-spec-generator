"""Markdown + Mermaid writer. Format reverse-engineered from the real sample output
(workspace/toyota/rav4-2026/multimedia/published/*.md) handed over with the project
docs, since the original publisher source was not available.

Generation-block convention: everything the machine writes lives between
GENERATED:START / GENERATED:END. A human may add text outside that block and it
survives the next publish — only the inside gets replaced (same idea as the source
project's OMST:START/END markers).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from domain import glossary, mermaid
from domain.model import ManualSpec, ParameterStatus
from domain.overlay import GlossaryTerm
from domain.profile import SLOT_DISPLAY

from .repositories import slugify

_START_RE = lambda tag: re.compile(  # noqa: E731
    r"<!-- GENERATED:START " + re.escape(tag) + r".*?-->", re.DOTALL
)
_END_RE = lambda tag: re.compile(r"<!-- GENERATED:END " + re.escape(tag) + r" -->", re.DOTALL)


def _esc(text: str) -> str:
    return html.escape(text, quote=False)


def _wrap_generated(tag: str, body: str, existing_path: Path) -> str:
    """Preserve any human text outside the generated block from a prior publish."""
    prefix, suffix = "", ""
    if existing_path.exists():
        old = existing_path.read_text(encoding="utf-8")
        start_m = _START_RE(tag).search(old)
        end_m = _END_RE(tag).search(old)
        if start_m and end_m and start_m.start() <= end_m.start():
            prefix = old[: start_m.start()]
            suffix = old[end_m.end() :]

    block = (
        f"<!-- GENERATED:START {tag} "
        "(generated; edits inside this block are overwritten by the next publish "
        "— write your own notes outside it) -->\n"
        f"{body}\n"
        f"<!-- GENERATED:END {tag} -->\n"
    )
    return f"{prefix}{block}{suffix}"


def _function_filename(function) -> str:
    return f"{function.chapter_number}-{slugify(function.title)}.md"


def _threshold_table(thresholds) -> str:
    if not thresholds:
        return ""
    rows = ["| Threshold | Matching text (Copied from OM) | Kind | Unit | Value | Status | Evidence | Filled by |",
            "|---|---|---|---|---|---|---|---|"]
    for t in thresholds:
        value = t.value if t.value else "**unfilled**"
        evidence = _esc(t.evidence) if t.evidence else "—"
        filled_by = t.filled_by or "—"
        rows.append(
            f"| {t.threshold_id} | {_esc(t.matching_text)} | {t.kind} | {t.unit or '—'} | "
            f"{value} | {t.status.value} | {evidence} | {filled_by} |"
        )
    return "\n".join(rows)


def _manual_body_text(spec: ManualSpec) -> str:
    """Every piece of real manual-quoted ("Copied from OM") text this spec
    carries, joined into one string for glossary.annotate to search — the same
    kind of text a reviewer would be reading when they registered a term's
    evidence in the first place."""
    pieces: list[str] = []
    for f in spec.functions:
        for r in f.requirements:
            pieces.append(r.text)
            if r.previous_text:
                pieces.append(r.previous_text)
        pieces.extend(step.text for step in f.procedure)
        pieces.extend(fig.caption_text for fig in f.figures if fig.caption_text)
    return "\n".join(pieces)


def _glossary_table(spec: ManualSpec, terms: list[GlossaryTerm]) -> str:
    if not terms:
        return ""
    matches = glossary.annotate(_manual_body_text(spec), terms, maker=spec.maker)
    if not matches:
        return ""
    by_id = {t.term_id: t for t in terms}
    hits: dict[str, int] = {}
    wordings: dict[str, list[str]] = {}
    for m in matches:
        hits[m.term_id] = hits.get(m.term_id, 0) + m.count
        seen = wordings.setdefault(m.term_id, [])
        if m.manual_wording not in seen:
            seen.append(m.manual_wording)

    rows = [
        "| In-house term | Category | Wording in the manual | Hits | Evidence |",
        "|---|---|---|---:|---|",
    ]
    for term_id, count in sorted(hits.items(), key=lambda kv: -kv[1]):
        term = by_id[term_id]
        wording_cell = ", ".join(f"`{w}`" for w in wordings[term_id])
        rows.append(
            f"| {_esc(term.in_house_term)} | {term.category.value} | {wording_cell} | "
            f"{count} | {_esc(term.evidence)} |"
        )
    return "\n".join(rows)


def _requirement_tables(function) -> str:
    by_slot: dict = {}
    for req in function.requirements:
        by_slot.setdefault(req.slot, []).append(req)

    sections = []
    has_change = any(r.change for r in function.requirements)
    # Fixed order (Overview, Requirements, HMI, User settings, Exception, Others),
    # matching the source document's own numbering — not insertion order — and a
    # slot nothing landed in is skipped entirely rather than printed empty.
    for slot, (number, slot_name) in SLOT_DISPLAY.items():
        reqs = by_slot.get(slot)
        if not reqs:
            continue
        header = ["| # | Presumed requirement | Change | Strength | Source |", "|---|---|---|---|---|"] \
            if has_change else \
            ["| # | Presumed requirement | Strength | Source |", "|---|---|---|---|"]
        rows = [f"## {function.chapter_number}-{number}. {slot_name}", "", *header]
        for i, req in enumerate(reqs, start=1):
            # Two stacked lines, not one flowing sentence: a label (the function's
            # own title for lead-in prose, "Step -" for a requirement split out of a
            # bullet — matching how the source document tells the two apart), then
            # the requirement text itself. The "machine-derived, not AI" disclaimer
            # used to repeat on every single row; moved to one mention in the
            # function header instead (2026-08-25) — repeating identical boilerplate
            # on every line reads like a template dump, not a requirements document,
            # and each row already carries its own provenance in the Source column.
            label = "Step -" if req.source.endswith("/ bullet") else function.title
            text = f'<span class="req-label">{_esc(label)}</span>{_esc(req.text)}'
            if req.previous_text:
                text += f"<br>~~{_esc(req.previous_text)}~~"
            row_cells = [str(i), text]
            if has_change:
                row_cells.append(req.change.value if req.change else "")
            row_cells.extend([req.strength.value, _esc(req.source)])
            row = "| " + " | ".join(row_cells) + " |"
            if req.change and req.change.value == "REMOVED":
                row = f"~~{row}~~"
            rows.append(row)
        sections.append("\n".join(rows))
    return "\n\n".join(sections)


def _function_markdown(function, manual_id: str) -> str:
    counts = {
        "thresholds": len(function.all_thresholds),
        "unfilled": sum(1 for t in function.all_thresholds if t.status == ParameterStatus.UNFILLED),
    }
    test_ready_class = "yes" if function.is_test_ready else "no"
    lines = [
        f"# {function.chapter_number}. {_esc(function.title)}",
        "",
        '<div class="fn-meta">'
        f"<b>Function path:</b> {_esc(function.function_path)}<br>"
        f"<b>Source:</b> printed page {', '.join(str(p) for p in function.pages) or '—'}<br>"
        f'<b>Test-ready:</b> <span class="test-ready-{test_ready_class}">'
        f"{'yes' if function.is_test_ready else 'no'} — "
        f"{'no unfilled thresholds and a procedure is present' if function.is_test_ready else 'procedure missing or thresholds unfilled'}"
        "</span></div>",
        "",
    ]

    if function.requirements:
        lines.append(
            '<p class="fn-disclaimer">Every "Presumed requirement" row below is '
            "machine-derived from the Owner's Manual text by rule-based extraction "
            "— not AI-written — and traceable to the printed page in its Source "
            "column.</p>"
        )
        lines.append("")

    if function.figures:
        lines.append("## Figures (areas of the original PDF; the OM has no figure numbers or captions)")
        for i, fig in enumerate(function.figures, start=1):
            lines.append(f"![figure]({fig.image_path or f'../figures/FIG-{fig.figure_id}.png'})")
            lines.append(f"- Figure {function.chapter_number}-{i} source: p.{fig.page + 1}")
            if fig.caption_text:
                lines.append(f"- (Copied from OM) {_esc(fig.caption_text)}")
        lines.append("")

    if function.procedure:
        lines.append("## Procedure")
        lines.append(mermaid.procedure_flowchart(function.function_id, function.procedure))
        lines.append("")
        lines.append("| Seq | Step | Operation (Copied from OM) | Source |")
        lines.append("|---|---|---|---|")
        for step in function.procedure:
            lines.append(f"| {step.sequence} | {step.number} | {_esc(step.text)} | {_esc(step.source)} |")
        lines.append("")

    if function.all_thresholds:
        lines.append("## Numeric thresholds (filled in by a tester)")
        lines.append(f"Filled: {counts['thresholds'] - counts['unfilled']} / unfilled: {counts['unfilled']}")
        lines.append("")
        lines.append(_threshold_table(function.all_thresholds))
        lines.append("")

    if function.requirements:
        lines.append(_requirement_tables(function))

    return "\n".join(lines)


def _index_markdown(
    spec: ManualSpec, terms: list[GlossaryTerm], *, combined: bool, chapter_slug: str | None = None
) -> str:
    # Functions table row links jump straight to that function's own published
    # page (_function_filename, a separate file from this index). In a
    # per-chapter README every row shares the same chapter_slug (given by the
    # caller) and chapter_number is still the original, so _function_filename
    # gives the right on-disk name directly. In the combined (whole-manual)
    # view chapter_number has been renumbered to avoid collisions across
    # chapters (see load_combined_spec) and no longer matches the real
    # filename, so FunctionSpec.published_href (set only there) is used as-is
    # instead of being recomputed here.
    counts = spec.counts()
    lines = [
        f"# {_esc(spec.display_title)} — Presumed specification",
        "",
        "> This is a machine-derived estimate, not an official requirements document. "
        "Numeric thresholds left blank could not be found in the manual and must be "
        "filled in by a tester with evidence.",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Maker / Model | {_esc(spec.maker)} / {_esc(spec.model)} |",
        f"| Scope | {_esc(spec.scope or spec.manual_id)} |",
        f"| Markets | {_esc(', '.join(spec.markets) or '—')} |",
        f"| Profile | {_esc(spec.profile_id)} |",
        f"| Manual ID | {_esc(spec.manual_id)} |",
        "",
        "## Numeric thresholds",
        f"Filled: {counts['thresholds_filled']} / Unfilled: {counts['thresholds_unfilled']}",
        "",
        mermaid.threshold_pie(counts["thresholds_filled"], counts["thresholds_unfilled"]),
        "",
        "## Figures in the manual",
        "",
        f"- Figures: **{counts['figures']}** / images rendered: **{counts['figures']}**",
        "",
        "Each image is a rendering of the corresponding area of the original PDF. "
        "**Images are not kept in the repository** (they are copies of another "
        "company's manual); `publish` creates them under `../figures/` on the "
        "machine that runs it.",
        "",
    ]

    glossary_table = _glossary_table(spec, terms)
    if glossary_table:
        lines.append("## Glossary (registered by a reviewer)")
        lines.append("")
        lines.append(
            "How wording in the manual maps to the in-house term. **The original "
            "text is not rewritten** — the mapping is only annotated here. "
            "Register terms on the Glossary screen. Evidence (why the mapping "
            "holds) is required."
        )
        lines.append("")
        lines.append(glossary_table)
        lines.append("")

    if spec.meta.get("unmatched_headings"):
        lines.append("## Headings not matched to body text")
        lines.append(
            "These bookmark entries could not be located in the extracted body text and "
            "were not turned into functions. Reported instead of silently dropped."
        )
        for title in spec.meta["unmatched_headings"]:
            lines.append(f"- {_esc(title)}")
        lines.append("")

    lines.append("## Functions")
    lines.append("")
    lines.append(mermaid.function_tree(spec))
    lines.append("")
    lines.append("| No. | Function | Area | Requirements | Figures | Unfilled thresholds | Test-ready |")
    lines.append("|---|---|---|---|---|---|---|")
    for f in spec.functions:
        unfilled = sum(1 for t in f.all_thresholds if t.status == ParameterStatus.UNFILLED)
        link = (
            f.published_href
            if combined
            else f"/specifications/{spec.manual_id}/file/{_function_filename(f)}?chapter={chapter_slug}"
        )
        lines.append(
            f"| {f.chapter_number} | [{_esc(f.title)}]({link}) | {_esc(f.area)} | {len(f.requirements)} | "
            f"{len(f.figures)} | {unfilled} | {'o' if f.is_test_ready else '-'} |"
        )

    return "\n".join(lines)


def combined_markdown(spec: ManualSpec, terms: list[GlossaryTerm]) -> str:
    """Whole-manual view: the same index summary _index_markdown produces, over
    a spec whose .functions is every viewable chapter merged together, so its
    counts/pie/table/tree are manual-wide totals, not one chapter's. Stays a
    single index/summary page -- it used to also re-print every function's
    full markdown inline below the table, one after another; dropped
    (2026-09-01) since the Functions table already links each row to that
    function's own already-published page, and re-printing everything inline
    on top of that made the page very tall and slow to scroll to the bottom
    of for no reason."""
    return _index_markdown(spec, terms, combined=True)


class MarkdownSpecPublisher:
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir)

    def publish(
        self, spec: ManualSpec, chapter_slug: str, allow_restricted: bool, terms: list[GlossaryTerm] = ()
    ) -> list[str]:
        published_dir = self.workspace_dir / spec.manual_id / "published" / chapter_slug
        published_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        current_filenames: set[str] = set()

        for function in spec.functions:
            filename = _function_filename(function)
            current_filenames.add(filename)
            path = published_dir / filename
            body = _function_markdown(function, spec.manual_id)
            content = _wrap_generated(f"function={function.function_id}", body, path)
            path.write_text(content, encoding="utf-8")
            written.append(str(path))

        readme_path = published_dir / "README.md"
        readme_content = _wrap_generated(
            "index",
            _index_markdown(spec, list(terms), combined=False, chapter_slug=chapter_slug),
            readme_path,
        )
        readme_path.write_text(readme_content, encoding="utf-8")
        written.append(str(readme_path))

        # Stale files are reported, not deleted — the original app's own doc warns
        # that silent deletion of published output without a git history to fall
        # back on is a footgun (see docs/CLAUDE.md "publish は古いファイルを消さない").
        stale = [
            p.name
            for p in published_dir.glob("*.md")
            if p.name != "README.md" and p.name not in current_filenames
        ]
        if stale:
            (published_dir / ".stale_files_after_last_publish.txt").write_text(
                "\n".join(stale), encoding="utf-8"
            )

        return written
