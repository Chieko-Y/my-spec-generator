"""Regression tests for domain.mermaid.procedure_flowchart, fixed 2026-09-03
alongside build_function_spec's sequence-restart detection (see
tests/test_procedure_steps.py's test_a_restarted_step_number_starts_a_new_sequence).
A function's procedure list can span multiple, unrelated real-world procedures
that each restart their own step numbering -- the flowchart must render each as
its own isolated subgraph, never one continuous chain across all of them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.mermaid import procedure_flowchart
from domain.model import ProcedureStep


def test_steps_in_the_same_sequence_are_chained_together():
    steps = [
        ProcedureStep(number=1, text="Select Home.", sequence=1, source="p.1 / step"),
        ProcedureStep(number=2, text="Select Phone.", sequence=1, source="p.1 / step"),
    ]

    chart = procedure_flowchart("fn1", steps)

    assert "S1_1 --> S1_2" in chart


def test_two_sequences_render_as_separate_subgraphs_with_no_cross_link():
    """The real bug: a flat chain across every step in the function drew an
    arrow from sequence 1's last step straight into sequence 2's first step,
    as if the manual's second, unrelated procedure continued the first."""
    steps = [
        ProcedureStep(number=1, text="Select Home.", sequence=1, source="p.1 / step"),
        ProcedureStep(number=2, text="Select General Settings.", sequence=1, source="p.1 / step"),
        ProcedureStep(number=1, text="Select Home.", sequence=2, source="p.1 / step"),
        ProcedureStep(number=2, text="Select Vehicle Settings.", sequence=2, source="p.1 / step"),
    ]

    chart = procedure_flowchart("fn1", steps)

    assert 'subgraph SEQ1["Sequence 1"]' in chart
    assert 'subgraph SEQ2["Sequence 2"]' in chart
    assert "S1_1 --> S1_2" in chart
    assert "S2_1 --> S2_2" in chart
    # The cross-sequence link that would wrongly join the two procedures.
    assert "S1_2 --> S2_1" not in chart


def test_no_steps_produces_no_chart():
    assert procedure_flowchart("fn1", []) == ""
