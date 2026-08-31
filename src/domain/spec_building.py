"""Map section blocks to profile slots and synthesize requirement text.

The one rule that must never be violated here: a generated requirement's `text` is a
light, rule-based restructuring of the source paragraph — never a summary, never a
translation — and it always travels paired with `source_text` holding the original
wording verbatim. See CONCEPT.md section 4.
"""
from __future__ import annotations

import re

from .manual_parsing import Line, Section
from .model import (
    FunctionSpec,
    ProcedureStep,
    RequirementItem,
    RequirementStrength,
    SpecSlot,
    content_id,
)
from .parameters import detect_parameters
from .profile import Profile

_NUMBERED_STEP = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$")
_LEADING_NUMBERING = re.compile(r"^\s*[\d.\-]+\s+")
# A trailing "(→P.19)"-style page reference can end up clustered onto the SAME
# line as the orphan number rather than the continuation text that follows it —
# confirmed directly against the real Subaru PDF, 2026-08-25: "1." and "(→P.19)"
# sit only 2.4pt apart in top (inside the line-clustering tolerance), while the
# actual step text "To display..." sits 3.4pt away (just outside it), even though
# reading order is "1. To display... (→P.19)". The optional group here captures
# that reference so it can be moved to the end, after the continuation text,
# instead of staying stuck between the number and the step it belongs to.
_ORPHAN_STEP_NUMBER = re.compile(r"^\s*(\d{1,2})[.)]\s*(\(.*\))?\s*$")
_PARAGRAPH_GAP_PT = 15.0
_DEFINE_MARKERS = (" means ", " refers to ", "is defined as", " is a term for")
_CONSTRAINT_MARKERS = (" if ", " when ", " unless ", "cannot", " only if ")

# Manuals often run a bullet list together as one block of extracted text with no
# line breaks between items (e.g. "...server: ● Displaying traffic... ● Displaying
# parking..."). Each bullet is its own independently testable requirement, not a
# sub-clause of the paragraph before it, so it must not stay merged into one row.
_BULLET_CHARS = "●•▪○◦"
# A bullet only counts as a split point when nothing but whitespace (or a string
# edge) precedes it — a real bullet always starts a fresh word, though the manual's
# own typesetting doesn't reliably put a space *after* it (e.g. "●Operate the touch
# screen..." with no space, confirmed directly against the real Subaru PDF,
# 2026-08-26 — an earlier version of this fix required trailing whitespace too and
# wrongly left that bullet fused onto "Operate"). (?<!\S) is a fixed-width (1-char)
# lookbehind, valid in Python's re.
_BULLET_SPLIT = re.compile(r"(?<!\S)[" + _BULLET_CHARS + r"]")
# A manual can also use the same glyph as generic placeholder notation packed
# together with little or no real content between instances, e.g. "<○○○>"
# (confirmed directly, real Subaru PDF, 2026-08-26: "● <○○○> descriptions in the
# command lists below signify numbers/titles/names..." — a footnote explaining that
# "<○○○>" stands for a placeholder value in the tables above it, not a 3-item
# bullet list) or "(○○ ○)" (same PDF, a different footnote — the middle glyph gets
# a genuine extra space from pdfplumber's own word segmentation, which passes the
# leading-whitespace check above on its own). A REAL list bullet is never within a
# couple characters of another bullet-class glyph — there is always a whole list
# item's worth of text between two real ones — so a candidate is only accepted if no
# other bullet-class character appears within this many characters on either side.
# Kept small deliberately: the real "●" that starts the "<○○○>" sentence above is
# itself only 3 characters from the decorative cluster it introduces ("● <○"), and
# a wider radius (6 was tried first) wrongly disqualified that real bullet too —
# confirmed directly against the same PDF.
_BULLET_ISOLATION_CHARS = 2


def _split_bullets(paragraph: str) -> list[tuple[str, bool]]:
    """Split on inline bullet glyphs, returning (text, is_bullet) pairs.

    A paragraph that starts with prose before its first "●" yields that lead-in as
    (text, False) and every split after it as (text, True). A paragraph that starts
    directly with "●" (no lead-in at all — a group made of nothing but list items)
    must not have its first item mislabeled as lead-in text: a split matched at the
    very start of the string produces a leading empty piece, which is what signals
    that case here.
    """
    if not any(ch in paragraph for ch in _BULLET_CHARS):
        return [(paragraph, False)]

    positions = []
    for m in _BULLET_SPLIT.finditer(paragraph):
        lo = max(0, m.start() - _BULLET_ISOLATION_CHARS)
        hi = min(len(paragraph), m.end() + _BULLET_ISOLATION_CHARS)
        neighborhood = paragraph[lo:m.start()] + paragraph[m.end():hi]
        if not any(ch in _BULLET_CHARS for ch in neighborhood):
            positions.append(m.start())
    if not positions:
        return [(paragraph, False)]

    raw_parts = []
    prev = 0
    for pos in positions:
        raw_parts.append(paragraph[prev:pos])
        prev = pos + 1
    raw_parts.append(paragraph[prev:])

    starts_with_bullet = not raw_parts[0].strip()
    parts = [p.strip() for p in raw_parts if p.strip()]
    if starts_with_bullet:
        return [(p, True) for p in parts]
    return [(p, i > 0) for i, p in enumerate(parts)]


# A printed line that wraps mid-word gets a trailing "-" from the typesetter (e.g.
# "sub-" / "scription"); this is a print-layout artifact like a running head, not
# content the manual actually wrote, so it is undone the same way — before any
# downstream keyword/threshold matching or content_id hashing sees the text. Merge
# only when the next fragment continues in lowercase: that is the standard signal for
# a wrapped word rather than an intentional trailing hyphen before a new sentence.
_WRAP_HYPHEN = re.compile(r"(\w)-$")


def _join_paragraph_lines(texts: list[str]) -> str:
    parts: list[str] = []
    for raw in texts:
        text = raw.strip()
        if not text:
            continue
        if parts and _WRAP_HYPHEN.search(parts[-1]) and text[:1].islower():
            parts[-1] = _WRAP_HYPHEN.sub(r"\1", parts[-1]) + text
        else:
            parts.append(text)
    return " ".join(parts)


def _clean_title(raw: str) -> str:
    return _LEADING_NUMBERING.sub("", raw).strip() or raw.strip()


def _classify_strength(paragraph: str) -> RequirementStrength:
    lowered = paragraph.lower()
    if any(marker in lowered for marker in _DEFINE_MARKERS):
        return RequirementStrength.DEFINE
    if any(marker in lowered for marker in _CONSTRAINT_MARKERS):
        return RequirementStrength.CONSTRAINT
    return RequirementStrength.CAPABILITY


def _merge_orphan_step_numbers(lines: list[Line]) -> list[Line]:
    """Some manuals print a step's number on its own line, with the step's actual
    text starting on the next line (confirmed directly against the real Subaru PDF,
    2026-08-25: "2." alone at one position, "Touch \"...\" next to..." on the next).
    Left alone, the number matches nothing and the text reads as ordinary prose,
    silently dropping a real step from the procedure. Re-attach the text to its
    number here, before step detection ever sees the lines."""
    merged: list[Line] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _ORPHAN_STEP_NUMBER.match(line.text)
        if m and i + 1 < len(lines):
            nxt = lines[i + 1]
            number, trailing_ref = m.group(1), m.group(2)
            text = f"{number}. {nxt.text.strip()}"
            if trailing_ref:
                text += f" {trailing_ref}"
            merged.append(Line(page=line.page, text=text, top=line.top, x0=line.x0, size=line.size))
            i += 2
        else:
            merged.append(line)
            i += 1
    return merged


def _split_lines(section: Section) -> tuple[list[tuple[int, int, float, str]], list[list]]:
    """Return (numbered_steps, paragraph_line_groups). Each numbered step is
    (number, page, top, text) -- top is the step number's own line position,
    kept so a requirement can be matched to "whichever step comes next" by
    plain (page, top) reading-order comparison (see build_function_spec's
    nearby-step citation). Each paragraph group is a list of Line.

    A step's own operation text can wrap onto following physical lines that
    don't repeat the number (e.g. "7. Close the driver's door and lock the
    doors, then move at" / "least 10 feet (3 m) away from the vehicle to
    prevent the key" / "from interfering." as three separate Lines, confirmed
    against the real 2025 Subaru supplement's Wi-Fi map-update procedure).
    Those continuation lines used to fall straight into prose_lines and come
    out as unrelated-looking "Service requirements" rows, while the step itself
    stayed truncated mid-sentence -- the same _PARAGRAPH_GAP_PT adjacency test
    prose grouping already uses (a non-step line immediately following, on the
    same page, with no big vertical gap) reattaches it to the step instead. A
    line starting with a bullet glyph is never treated as a continuation even if
    it's close by: a bullet always starts a new, distinct item (confirmed
    against the same page -- "8. After at least 5 minutes ... start the engine
    again." sits 13.7pt above an unrelated "● The new map data will be
    applied." note, well inside the gap threshold).
    """
    steps: list[list] = []
    prose_lines: list = []
    open_step_idx: int | None = None
    prev_top = None
    prev_page = None

    for line in _merge_orphan_step_numbers(section.lines):
        text = line.text.strip()
        if not text:
            continue
        m = _NUMBERED_STEP.match(text)
        if m:
            steps.append([int(m.group(1)), line.page, line.top, m.group(2).strip()])
            open_step_idx = len(steps) - 1
        elif (
            open_step_idx is not None
            and text[0] not in _BULLET_CHARS
            and line.page == prev_page
            and prev_top is not None
            and (line.top - prev_top) <= _PARAGRAPH_GAP_PT
        ):
            steps[open_step_idx][3] += " " + text
        else:
            open_step_idx = None
            prose_lines.append(line)
        prev_top = line.top
        prev_page = line.page
    steps = [(number, page, top, text) for number, page, top, text in steps]

    groups: list[list] = []
    current: list = []
    prev_top = None
    prev_page = None
    for line in prose_lines:
        text = line.text.strip()
        if not text:
            continue
        starts_new = False
        if current:
            if line.page != prev_page:
                starts_new = True
            elif prev_top is not None and (line.top - prev_top) > _PARAGRAPH_GAP_PT:
                starts_new = True
        if starts_new:
            groups.append(current)
            current = []
        current.append(line)
        prev_top = line.top
        prev_page = line.page
    if current:
        groups.append(current)
    return steps, groups


def build_function_spec(
    section: Section,
    profile: Profile,
    manual_id: str,
    area_title: str,
    sequence_in_area: int,
    figures: list | None = None,
    page_running_head: dict[int, str] | None = None,
) -> FunctionSpec:
    title = _clean_title(section.title)
    chapter_number = str(sequence_in_area)

    function_id = content_id("function", manual_id, area_title, section.title)
    function_path = f"{area_title} / {title}" if area_title else title

    steps_raw, paragraph_groups = _split_lines(section)
    # (page, top, "N. text") per step, in reading-order -- used below to cite
    # "whichever step comes next" alongside a requirement. Confirmed against
    # the real Subaru Outback 2026 PDF, 2026-08-31: a requirement/exception
    # line's own page can be BEFORE the step it logically leads into (e.g.
    # "After a few seconds, the Caution screen will be displayed." sits right
    # after step 1 at the bottom of one page, describing what happens before
    # step 2, printed at the top of the next page) -- "the step the reader
    # does next" is the useful citation here, not "the nearest step by raw
    # position" (step 1 is closer on the page but already done by this point).
    step_positions = sorted((page, top, f"{number}. {text}") for number, page, top, text in steps_raw)

    def _next_step_after(pos: tuple[int, float]) -> str | None:
        for page, top, label in step_positions:
            if (page, top) > pos:
                return label
        return None

    procedure: list[ProcedureStep] = []
    for seq, (number, page, top, text) in enumerate(steps_raw, start=1):
        procedure.append(
            ProcedureStep(number=number, text=text, sequence=seq, source=f"p.{page + 1} / step")
        )

    requirements: list[RequirementItem] = []
    # "Service overview" in the real document is everything in a section before its
    # first bullet/list item — however many paragraphs that spans — not just the
    # first paragraph: confirmed directly against two real Subaru samples,
    # 2026-08-25. One section had two plain paragraphs with no bullets at all, and
    # the original kept both as Service overview; another had a lead-in paragraph
    # plus a later plain paragraph ("Candidate routes...") sitting before the
    # section's first "●", and the original kept that one as Overview too, only
    # switching to Service requirements once an actual bullet appeared. So the
    # trigger is "has this section produced a bullet item yet", tracked once across
    # every paragraph — not "is this the first paragraph".
    seen_bullet_in_section = False

    for group in paragraph_groups:
        paragraph = _join_paragraph_lines([l.text for l in group]).strip()
        if len(paragraph) < 8:
            continue
        page = group[0].page
        next_step_text = _next_step_after((group[0].page, group[0].top))

        # A paragraph that itself uses "shall/must" wording is kept, verbatim, like
        # any other paragraph — dropping it would silently discard information the
        # manual actually states. What must never happen is the reverse: this
        # generator inventing an obligation the source didn't make. That invariant
        # lives in RequirementStrength itself (no MUST/SHALL value exists to assign;
        # see model.py), not in filtering source paragraphs. See CONCEPT.md section 4.
        for item, is_bullet in _split_bullets(paragraph):
            if len(item) < 8:
                continue
            req_text = item if item.endswith((".", "!", "?")) else item + "."
            req_id = content_id("requirement", manual_id, section.title, item[:120])
            source = f"p.{page + 1} / {'bullet' if is_bullet else 'text'}"
            page_citation = page_running_head.get(page) if page_running_head else None

            if is_bullet:
                seen_bullet_in_section = True
            # Keyword rules (Exception/HMI/User setting) only apply once the section
            # has started producing bullets — confirmed directly against a real
            # Subaru sample, 2026-08-25: a lead-in paragraph containing "cannot" and
            # "errors" ("we cannot guarantee that map data contains no errors...")
            # was still Service overview in the original, because that section has
            # no bullets at all. Exception/HMI/User setting rows in every real
            # example found are bullet items — the wording alone, out of context,
            # is not enough to justify leaving Overview.
            item_slot = profile.slot_for("", item) if seen_bullet_in_section else SpecSlot.OVERVIEW

            thresholds = detect_parameters(item, source)
            requirements.append(
                RequirementItem(
                    req_id=req_id,
                    slot=item_slot,
                    text=req_text,
                    source_text=item,
                    strength=_classify_strength(item),
                    source=source,
                    page_citation=page_citation,
                    next_step_text=next_step_text,
                    thresholds=thresholds,
                )
            )

    pages = sorted({l.page + 1 for l in section.lines} | {section.page_start + 1})

    return FunctionSpec(
        function_id=function_id,
        chapter_number=chapter_number,
        title=title,
        area=area_title,
        function_path=function_path,
        pages=pages,
        procedure=procedure,
        requirements=requirements,
        figures=figures or [],
    )


def build_manual_spec_functions(
    sections: list[Section],
    profile: Profile,
    manual_id: str,
    area_title: str,
    figures_by_section: list[list] | None = None,
    page_running_head: dict[int, str] | None = None,
) -> list[FunctionSpec]:
    return [
        build_function_spec(
            section,
            profile,
            manual_id,
            area_title,
            i + 1,
            figures_by_section[i] if figures_by_section else None,
            page_running_head,
        )
        for i, section in enumerate(sections)
    ]
