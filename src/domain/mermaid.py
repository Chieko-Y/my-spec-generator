"""Deterministic Mermaid generation. Labels are always quoted: manual body text is
riddled with `[Search]` / `(-> P.140)` and unquoted brackets break Mermaid's own
syntax. See CLAUDE.md gotcha on domain/mermaid.py.
"""
from __future__ import annotations

from .model import FunctionSpec, ManualSpec, ProcedureStep


def label(text: str, max_len: int = 60) -> str:
    text = text.replace('"', "'").replace("\n", " ").strip()
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return f'"{text}"'


def procedure_flowchart(function_id: str, steps: list[ProcedureStep]) -> str:
    """One subgraph per `ProcedureStep.sequence`, steps chained only within
    their own sequence -- a manual restarting its step numbering (2, 3, ...
    procedures under one function, see build_function_spec) means step 1 of
    procedure 2 is NOT a continuation of the last step of procedure 1, and
    must not be drawn as one. Confirmed real, Honda Pilot "Defaulting All the
    Settings": a flat chain across all of a function's steps regardless of
    sequence wrongly drew "...6.Select Reset again..." --> "1.Select Home."
    as if the second procedure continued the first."""
    if not steps:
        return ""
    lines = ["```mermaid", "flowchart TD"]
    sequences: dict[int, list[ProcedureStep]] = {}
    for step in steps:
        sequences.setdefault(step.sequence, []).append(step)
    for seq, seq_steps in sequences.items():
        lines.append(f'    subgraph SEQ{seq}["Sequence {seq}"]')
        lines.append("    direction TB")
        node_ids = []
        for step in seq_steps:
            node_id = f"S{seq}_{step.number}"
            node_ids.append(node_id)
            lines.append(f"    {node_id}[{label(f'{step.number}. {step.text}')}]")
        for a, b in zip(node_ids, node_ids[1:]):
            lines.append(f"    {a} --> {b}")
        lines.append("    end")
    lines.append("```")
    return "\n".join(lines)


def threshold_pie(filled: int, unfilled: int) -> str:
    lines = [
        "```mermaid",
        "pie showData",
        f'    "Filled" : {filled}',
        f'    "Unfilled" : {unfilled}',
        "```",
    ]
    return "\n".join(lines)


def function_tree(spec: ManualSpec) -> str:
    # A manual with many functions makes for many nodes -- at mermaid's default
    # font size the whole tree renders very large even scaled to fit its own
    # content (not just "too wide for the page", reported directly 2026-09-01,
    # after the page-width-stretch issue was already fixed separately). A
    # smaller font shrinks every node (and so the whole diagram) without
    # touching the pie chart elsewhere, which has its own default size and
    # doesn't need this.
    lines = [
        "```mermaid",
        '%%{init: {"themeVariables": {"fontSize": "11px"}}}%%',
        "flowchart LR",
        f"    ROOT[{label(spec.display_title)}]",
    ]
    areas: dict[str, list[FunctionSpec]] = {}
    for function in spec.functions:
        areas.setdefault(function.area or "General", []).append(function)

    for a_idx, (area, functions) in enumerate(areas.items(), start=1):
        area_node = f"A{a_idx}"
        lines.append(f"    ROOT --> {area_node}[{label(area)}]")
        for f_idx, function in enumerate(functions, start=1):
            func_node = f"{area_node}F{f_idx}"
            marker = " ⚠" if not function.is_test_ready else ""
            lines.append(
                f"    {area_node} --> {func_node}[{label(f'{function.chapter_number} {function.title}{marker}')}]"
            )
    lines.append("```")
    return "\n".join(lines)
