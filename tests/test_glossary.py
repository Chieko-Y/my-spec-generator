"""Glossary rebuild, 2026-09-01: brought up to parity with the original app's
real screen (pasted by the user) -- meaning/filled_by/notes fields, per-wording
maker scoping ("<text> | <maker>", maker omitted = every maker), and the
highlight+hover annotation in the Specifications viewer.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from application.use_cases import UseCases, ValidationError
from domain.glossary import annotate
from domain.model import (
    FunctionSpec,
    ManualSpec,
    RequirementItem,
    RequirementStrength,
    SpecSlot,
    TermCategory,
)
from domain.overlay import GlossaryTerm, ManualWording
from infrastructure.markdown_publisher import _index_markdown
from infrastructure.markdown_view import highlight_glossary_terms


class _FakeGlossaryRepository:
    def __init__(self):
        self._terms: list[GlossaryTerm] = []

    def load_all(self) -> list[GlossaryTerm]:
        return list(self._terms)

    def save_all(self, terms: list[GlossaryTerm]) -> None:
        self._terms = list(terms)


def _uc(repo: _FakeGlossaryRepository) -> UseCases:
    return UseCases(None, None, None, None, None, None, repo, None, None, None, None, None)


def _term(term_id, wordings, **kw) -> GlossaryTerm:
    defaults = dict(
        in_house_term="Select operation", meaning="", category=TermCategory.OPERATION,
        evidence="ev", filled_by="A",
    )
    defaults.update(kw)
    return GlossaryTerm(term_id=term_id, manual_wordings=wordings, **defaults)


def test_wording_without_maker_requires_evidence_and_filled_by():
    with pytest.raises(ValueError):
        GlossaryTerm(
            term_id="t1", in_house_term="X", meaning="", category=TermCategory.OPERATION,
            manual_wordings=[ManualWording(text="Touch")], evidence="", filled_by="A",
        )
    with pytest.raises(ValueError):
        GlossaryTerm(
            term_id="t1", in_house_term="X", meaning="", category=TermCategory.OPERATION,
            manual_wordings=[ManualWording(text="Touch")], evidence="ev", filled_by="",
        )


def test_same_wording_different_makers_does_not_collide():
    repo = _FakeGlossaryRepository()
    uc = _uc(repo)
    uc.set_term(_term("t1", [ManualWording(text="Touch", maker="toyota")]))
    # Should not raise -- same word, different maker scope.
    uc.set_term(_term("t2", [ManualWording(text="Touch", maker="honda")], in_house_term="Different meaning"))
    assert {t.term_id for t in uc.load_glossary()} == {"t1", "t2"}


def test_same_wording_all_makers_collides_with_any_scope():
    repo = _FakeGlossaryRepository()
    uc = _uc(repo)
    uc.set_term(_term("t1", [ManualWording(text="Touch")]))  # every maker
    with pytest.raises(ValidationError):
        uc.set_term(_term("t2", [ManualWording(text="Touch", maker="honda")], in_house_term="Other"))


def test_same_wording_same_maker_collides():
    repo = _FakeGlossaryRepository()
    uc = _uc(repo)
    uc.set_term(_term("t1", [ManualWording(text="Touch", maker="toyota")]))
    with pytest.raises(ValidationError):
        uc.set_term(_term("t2", [ManualWording(text="touch", maker="Toyota")], in_house_term="Other"))


def test_annotate_respects_maker_scope():
    terms = [
        _term("t1", [ManualWording(text="Touch", maker="toyota")]),
        _term("t2", [ManualWording(text="Press")], in_house_term="Y"),  # every maker
    ]
    honda_matches = annotate("Touch the screen. Press the button.", terms, maker="honda")
    assert {m.manual_wording for m in honda_matches} == {"Press"}

    toyota_matches = annotate("Touch the screen. Press the button.", terms, maker="toyota")
    assert {m.manual_wording for m in toyota_matches} == {"Touch", "Press"}


def test_highlight_wraps_only_plain_text_and_skips_pre_blocks():
    terms = [_term("t1", [ManualWording(text="Touch")], meaning="tap the screen")]
    html = '<p>Touch the icon.</p><pre class="mermaid">A[Touch]</pre><a href="/x?Touch=1">Touch link</a>'
    out = highlight_glossary_terms(html, terms)

    assert '<mark class="glossary-term" title="Select operation: tap the screen">Touch</mark> the icon.' in out
    # Mermaid diagram source must survive completely untouched.
    assert '<pre class="mermaid">A[Touch]</pre>' in out
    # A tag's own attribute text (the href) must never be rewritten, only the
    # visible link text between the tags.
    assert 'href="/x?Touch=1"' in out
    assert '<mark class="glossary-term" title="Select operation: tap the screen">Touch</mark> link</a>' in out


def test_highlight_is_case_insensitive_and_no_op_with_no_terms():
    assert highlight_glossary_terms("<p>touch it</p>", []) == "<p>touch it</p>"
    terms = [_term("t1", [ManualWording(text="Touch")])]
    out = highlight_glossary_terms("<p>please touch here</p>", terms)
    assert "<mark" in out and "touch" in out


def _spec_with_text(*texts: str, maker: str = "subaru") -> ManualSpec:
    reqs = [
        RequirementItem(
            req_id=f"r{i}", slot=SpecSlot.REQUIREMENTS, text=t, source_text=t,
            strength=RequirementStrength.CAPABILITY, source="p.1 / text",
        )
        for i, t in enumerate(texts)
    ]
    fn = FunctionSpec(
        function_id="f1", chapter_number="1", title="Apps Screen", area="Apps",
        function_path="Apps Screen", pages=[1], requirements=reqs,
    )
    return ManualSpec(
        manual_id="subaru/outback-2026/ivi", maker=maker, model="Outback",
        document_title="Outback OM", scope="apps", markets=["US"], profile_id="subaru_v1",
        functions=[fn],
    )


def test_index_markdown_adds_glossary_section_with_hits_from_manual_text():
    terms = [
        _term(
            "t1", [ManualWording(text="Android Auto")],
            in_house_term="AA", meaning="phone mirroring", category=TermCategory.ABBREVIATION,
        )
    ]
    spec = _spec_with_text("Android Auto can be used to view Google Maps.", "Connect Android Auto via USB.")
    md = _index_markdown(spec, terms, combined=True)

    assert "## Glossary (registered by a reviewer)" in md
    assert "| AA | abbreviation | `Android Auto` | 2 |" in md


def test_index_markdown_omits_glossary_section_when_nothing_matches():
    terms = [_term("t1", [ManualWording(text="Android Auto")])]
    spec = _spec_with_text("This function has nothing to do with phones.")
    md = _index_markdown(spec, terms, combined=True)
    assert "## Glossary" not in md


def test_index_markdown_glossary_section_respects_maker_scope():
    terms = [_term("t1", [ManualWording(text="Touch", maker="toyota")], in_house_term="Select operation")]
    spec = _spec_with_text("Touch the screen to select.", maker="subaru")
    md = _index_markdown(spec, terms, combined=True)
    # Registered for toyota only -- must not show up in a Subaru manual's own index.
    assert "## Glossary" not in md
