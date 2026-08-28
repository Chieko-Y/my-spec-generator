"""Unit tests for GeminiChapterClassifier -- the one place in this app that
calls out to an AI model (see docs/HANDOVER.md 2026-08-27). No real network
call: httpx.post is monkeypatched. The single most safety-critical behavior
tested here is that a label the model proposes is only ever accepted when it
exactly matches the candidate's own label or one of its own evidence strings --
anything else must be rejected and silently replaced with the original label,
never trusted as-is.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx

from domain.manual_parsing import ChapterClassification, RunningHeadChapter
from infrastructure.gemini_chapter_classifier import (
    ChapterClassifierError,
    GeminiChapterClassifier,
    _build_prompt,
)


class _FakeResponse:
    def __init__(self, verdicts, status_code: int = 200):
        self._verdicts = verdicts
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(self._verdicts)}]}}
            ]
        }


def _mock_post(monkeypatch, verdicts, status_code: int = 200):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return _FakeResponse(verdicts, status_code)

    monkeypatch.setattr(httpx, "post", fake_post)
    return calls


def test_classify_keeps_original_label_when_model_returns_it_unchanged(monkeypatch):
    candidates = [RunningHeadChapter(label="bluetooth settings", page_start=0, page_end=3)]
    _mock_post(
        monkeypatch,
        [{"index": 0, "is_real_chapter": True, "label": "bluetooth settings", "reason": "real chapter"}],
    )
    classifier = GeminiChapterClassifier(api_key="fake-key")

    results = classifier.classify("manual context", candidates, [[]])

    assert results == [
        ChapterClassification(label="bluetooth settings", is_real_chapter=True, reason="real chapter")
    ]


def test_classify_accepts_a_verbatim_evidence_line_as_relabel(monkeypatch):
    candidates = [RunningHeadChapter(label="basic operation", page_start=4, page_end=7)]
    evidence = [["Map screen", "Route calculation"]]
    _mock_post(
        monkeypatch,
        [{"index": 0, "is_real_chapter": True, "label": "Map screen", "reason": "navigation content"}],
    )
    classifier = GeminiChapterClassifier(api_key="fake-key")

    results = classifier.classify("manual context", candidates, evidence)

    assert results[0].label == "Map screen"
    assert "rejected" not in results[0].reason


def test_classify_rejects_an_invented_label_and_falls_back_to_original_with_reason_noting_rejection(monkeypatch):
    candidates = [RunningHeadChapter(label="basic operation", page_start=4, page_end=7)]
    evidence = [["Map screen", "Route calculation"]]
    _mock_post(
        monkeypatch,
        [
            {
                "index": 0,
                "is_real_chapter": True,
                "label": "Navigation System (If equipped)",  # not the label, not in evidence
                "reason": "this is clearly the navigation chapter",
            }
        ],
    )
    classifier = GeminiChapterClassifier(api_key="fake-key")

    results = classifier.classify("manual context", candidates, evidence)

    assert results[0].label == "basic operation"  # fell back to the original
    assert "rejected" in results[0].reason
    assert "Navigation System (If equipped)" in results[0].reason


def test_classify_raises_on_evidence_candidates_length_mismatch(monkeypatch):
    candidates = [RunningHeadChapter(label="a", page_start=0, page_end=3)]
    classifier = GeminiChapterClassifier(api_key="fake-key")

    try:
        classifier.classify("manual context", candidates, [])  # wrong length
        raise AssertionError("expected ChapterClassifierError")
    except ChapterClassifierError as e:
        assert "evidence" in str(e)


def test_classify_raises_when_api_key_missing():
    classifier = GeminiChapterClassifier(api_key="")

    try:
        classifier.classify("ctx", [RunningHeadChapter(label="a", page_start=0, page_end=3)], [[]])
        raise AssertionError("expected ChapterClassifierError")
    except ChapterClassifierError as e:
        assert "GEMINI_API_KEY" in str(e)


def test_build_prompt_includes_evidence_lines_and_the_no_invented_text_instruction():
    candidates = [RunningHeadChapter(label="basic operation", page_start=4, page_end=7)]
    evidence = [["Map screen", "Route calculation"]]

    prompt = _build_prompt("some manual", candidates, evidence)

    assert "Map screen" in prompt
    assert "Route calculation" in prompt
    assert "never invent" in prompt.lower()
