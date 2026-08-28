"""ChapterClassifier implementation backed by the Gemini API. This is the one and
only network call anywhere in this app (see application/ports.py's
ChapterClassifier docstring and docs/HANDOVER.md 2026-08-27) -- everything else
stays deterministic and offline. Uses httpx directly against Gemini's REST API
rather than adding the google-genai SDK as a dependency, since httpx is already
a dependency of this project.
"""
from __future__ import annotations

import json

import httpx

from domain.manual_parsing import ChapterClassification, RunningHeadChapter

_ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# gemini-flash-latest is a thinking model (returns a thoughtSignature even for a
# trivial prompt) -- a trivial "ok" reply alone took ~19s in testing, so a real
# batch of dozens of candidates needs real headroom, not the 60s a non-thinking
# model would need.
_TIMEOUT_SECONDS = 120.0
# Enough to cover a typical manual's cover/title page (maker, model, "supplement"
# wording etc.) without inflating the request for no benefit.
_MANUAL_CONTEXT_MAX_CHARS = 1500

_RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "index": {"type": "INTEGER"},
            "is_real_chapter": {"type": "BOOLEAN"},
            "label": {"type": "STRING"},
            "reason": {"type": "STRING"},
        },
        "required": ["index", "is_real_chapter", "label", "reason"],
    },
}


class ChapterClassifierError(Exception):
    """Raised on a missing API key, a network/API failure, or a response that
    doesn't match what was asked for -- never silently swallowed, since this is a
    one-shot, human-reviewed call (see docs/HANDOVER.md 2026-08-27)."""


class GeminiChapterClassifier:
    def __init__(self, api_key: str, model: str = "gemini-flash-lite-latest") -> None:
        self.api_key = api_key
        self.model = model

    def classify(
        self,
        manual_context: str,
        candidates: list[RunningHeadChapter],
        evidence: list[list[str]],
    ) -> list[ChapterClassification]:
        if not self.api_key:
            raise ChapterClassifierError(
                "GEMINI_API_KEY is not set -- add it to .env before running "
                "profile-classify-chapters."
            )
        if not candidates:
            return []
        if len(evidence) != len(candidates):
            raise ChapterClassifierError(
                f"evidence has {len(evidence)} entries but there are {len(candidates)} "
                "candidates -- caller must pass one evidence list per candidate, index-aligned."
            )

        prompt = _build_prompt(manual_context, candidates, evidence)
        url = _ENDPOINT_TEMPLATE.format(model=self.model)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
            },
        }
        try:
            response = httpx.post(
                url,
                json=body,
                headers={"x-goog-api-key": self.api_key},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise ChapterClassifierError(f"Gemini API call failed: {e}") from e

        try:
            payload = response.json()
            raw_text = payload["candidates"][0]["content"]["parts"][0]["text"]
            verdicts = json.loads(raw_text)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ChapterClassifierError(
                f"Gemini API returned an unexpected response shape: {e}"
            ) from e

        by_index = {}
        for v in verdicts:
            try:
                by_index[v["index"]] = v
            except (KeyError, TypeError) as e:
                raise ChapterClassifierError(
                    f"Gemini API returned a malformed verdict entry: {v!r} ({e})"
                ) from e

        if set(by_index.keys()) != set(range(len(candidates))):
            raise ChapterClassifierError(
                f"Gemini API returned verdicts for indices {sorted(by_index.keys())}, "
                f"expected exactly 0..{len(candidates) - 1}."
            )

        results = []
        for i, candidate in enumerate(candidates):
            v = by_index[i]
            proposed = str(v["label"]).strip()
            reason = str(v["reason"])
            # Code-level enforcement, not just a prompt instruction: the only
            # values ever accepted as a chapter's label are its own original
            # label, or one of its own evidence strings copied verbatim --
            # anything else is treated as invented text and rejected, no matter
            # how plausible it reads (see application/ports.py ChapterClassifier
            # docstring and docs/HANDOVER.md 2026-08-27).
            if proposed == candidate.label or proposed in evidence[i]:
                label = proposed
            else:
                label = candidate.label
                reason = (
                    f"{reason} [label override rejected: model proposed {proposed!r}, "
                    "which matches neither the candidate's own label nor any of its "
                    "evidence lines verbatim -- falling back to the original label]"
                )
            results.append(
                ChapterClassification(
                    label=label,
                    is_real_chapter=bool(v["is_real_chapter"]),
                    reason=reason,
                )
            )
        return results


def _build_prompt(
    manual_context: str, candidates: list[RunningHeadChapter], evidence: list[list[str]]
) -> str:
    context = manual_context.strip()[:_MANUAL_CONTEXT_MAX_CHARS]

    # A real chapter's running-head label normally shows up as ONE long contiguous
    # run. A label that recurs at several separate, scattered locations is much
    # more likely a footnote/spec-table/trim-variant annotation that happens to
    # repeat for a few pages wherever it's referenced -- confirmed directly against
    # real data (2026-08-27): "x dual 70 inch display system" recurred at 5
    # separate 2-3-page spots and was still called REAL by the model without this
    # signal, the same failure shape as the original "navi system" bug this whole
    # feature exists to catch.
    occurrence_counts: dict[str, int] = {}
    for c in candidates:
        occurrence_counts[c.label] = occurrence_counts.get(c.label, 0) + 1

    def _format_evidence(ev: list[str]) -> str:
        if not ev:
            return "(none found)"
        return ", ".join(f'"{e}"' for e in ev)

    candidate_lines = "\n".join(
        f'{i}: "{c.label}" (spans {c.page_end - c.page_start} consecutive pages; '
        f"this exact label recurs at {occurrence_counts[c.label]} separate, "
        "non-adjacent location(s) in this document)\n"
        f"   evidence headings found on these pages: {_format_evidence(evidence[i])}"
        for i, c in enumerate(candidates)
    )
    return f"""You are reviewing text labels extracted from a vehicle infotainment
owner's-manual PDF. Each label was picked out because it repeats verbatim across
3 or more consecutive pages -- a heuristic for detecting a running-head chapter
label printed in the page margin. This heuristic also picks up noise that happens
to repeat the same way: a footnote or spec-table fragment, a generic single word
("note", "system", "page"), a print-production artifact, or a page-number-like
string.

For each candidate, decide whether it is a genuine chapter/section title (e.g.
"Bluetooth settings", "Audio operation", "Navigation menu screen") or noise.

Important structural signal: a genuine chapter/section title normally appears as
ONE single long contiguous run in the running head. A label that recurs at
SEVERAL separate, scattered locations across otherwise-unrelated parts of the
manual -- especially when each individual occurrence only spans a few pages -- is
much more likely a footnote, spec-table annotation, or hardware/trim-variant
marker (e.g. a display-size or equipment note referenced from many different
chapters) than a real chapter title, even if the label text itself reads
plausibly like a section name. Weigh a high occurrence count as evidence toward
noise.

Some candidates share the exact same label text with another candidate even
though they cover completely different content -- the same margin text can be
printed for two different chapters in the same manual. Each candidate's "evidence
headings" are real sub-heading text found within that specific candidate's own
page range (not the label itself), which is the only way to tell such duplicates
apart.

For each candidate's "label" in your answer, you have exactly two allowed
choices: (1) the candidate's own label, unchanged -- the default, safe choice --
or (2) ONE of that candidate's own evidence headings, copied EXACTLY as given,
when the evidence clearly shows this page range is really about something more
specific than the shared label suggests (e.g. the same "BASIC OPERATION" label
printed for both an audio chapter and, elsewhere, a navigation chapter,
distinguishable only by their own evidence headings like "MAP SCREEN" or "ROUTE
CALCULATION"). You must never invent, compose, paraphrase, translate, or reword a
label -- any text that is not the candidate's own original label or one of its
own evidence headings, copied verbatim, will be rejected.

Manual context (from the cover/title page):
{context}

Candidates:
{candidate_lines}

Return a verdict for every candidate index, with a label chosen per the rules
above, and a short reason for each."""
