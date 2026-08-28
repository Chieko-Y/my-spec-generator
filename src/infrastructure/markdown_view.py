"""Turns a published .md file into HTML for the Specifications viewer. ```mermaid
fences become `<pre class="mermaid">` blocks so the client-side mermaid.js (vendored,
no CDN) picks them up and renders them in place.
"""
from __future__ import annotations

import re

import markdown as md

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
