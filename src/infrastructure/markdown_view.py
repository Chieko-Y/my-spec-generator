"""Turns a published .md file into HTML for the Specifications viewer. ```mermaid
fences become `<pre class="mermaid">` blocks so the client-side mermaid.js (vendored,
no CDN) picks them up and renders them in place.
"""
from __future__ import annotations

import html
import re

import markdown as md

from domain.overlay import GlossaryTerm

_MERMAID_FENCE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def render_markdown_to_html(text: str) -> str:
    # Pull mermaid fences out before the general markdown pass (python-markdown's
    # fenced_code extension would otherwise wrap them as <code>, HTML-escaping the
    # diagram source and hiding it from mermaid.js).
    placeholders: list[str] = []

    def _stash(m: re.Match) -> str:
        placeholders.append(m.group(1))
        return f"\n\n<!--MERMAID_PLACEHOLDER_{len(placeholders) - 1}-->\n\n"

    stashed = _MERMAID_FENCE.sub(_stash, text)
    html = md.markdown(stashed, extensions=["tables", "fenced_code", "nl2br"])

    for i, diagram in enumerate(placeholders):
        marker = f"<!--MERMAID_PLACEHOLDER_{i}-->"
        block = f'<pre class="mermaid">{diagram}</pre>'
        html = html.replace(f"<p>{marker}</p>", block).replace(marker, block)

    return html


_TAG_SPLIT = re.compile(r"(<[^>]+>)")


def highlight_glossary_terms(rendered_html: str, terms: list[GlossaryTerm], maker: str = "") -> str:
    """Wrap each matched manual wording in a <mark> carrying the in-house term
    (+ meaning) as its hover title -- the annotation layer the original app's
    own Glossary screen described (yellow highlight, hover shows "in-house
    term: meaning"), rendered here rather than in domain/glossary.py because
    that module must never contain a text-rewriting function (see its own
    docstring and check_domain.py 9-5). Only ever touches text that sits
    between HTML tags -- never a tag's own markup/attributes, and never inside
    a <pre>...</pre> block (a mermaid diagram's own source, not manual prose)
    -- so a real match can never corrupt the surrounding HTML or a diagram."""
    entries: list[tuple[str, GlossaryTerm]] = []
    for term in terms:
        for wording in term.manual_wordings:
            if not wording.text:
                continue
            if maker and wording.maker and wording.maker.lower() != maker.lower():
                continue
            entries.append((wording.text, term))
    if not entries:
        return rendered_html

    # Longest wording first: at a given position, the regex alternation below
    # tries left-to-right, so this makes a longer wording win over a shorter
    # one it happens to contain (e.g. a future "Select operation" alias
    # wouldn't get shadowed by a shorter "Select").
    entries.sort(key=lambda e: len(e[0]), reverse=True)
    lookup = {w.lower(): term for w, term in entries}
    pattern = re.compile("|".join(re.escape(w) for w, _ in entries), re.IGNORECASE)

    def _mark(m: re.Match) -> str:
        term = lookup.get(m.group(0).lower())
        if term is None:  # pragma: no cover - can't happen, kept defensive
            return m.group(0)
        tooltip = f"{term.in_house_term}: {term.meaning}" if term.meaning else term.in_house_term
        return f'<mark class="glossary-term" title="{html.escape(tooltip, quote=True)}">{m.group(0)}</mark>'

    parts = _TAG_SPLIT.split(rendered_html)
    in_pre = 0
    for i, part in enumerate(parts):
        if i % 2 == 1:  # a tag, never rewritten
            lowered = part.lower()
            if lowered.startswith("<pre"):
                in_pre += 1
            elif lowered.startswith("</pre"):
                in_pre = max(0, in_pre - 1)
            continue
        if in_pre or not part:
            continue
        parts[i] = pattern.sub(_mark, part)
    return "".join(parts)
