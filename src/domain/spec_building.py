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

_NUMBERED_STEP = re.compile(r"^\s*(\d{1,2})[.)]\s*(?=[A-Z])(.+?)\s*$")
# The space after the step number's punctuation is OPTIONAL -- confirmed real,
# Honda Pilot, 2026-09-03: every numbered step in this manual's real PDF is set
# with NO space at all ("1.Select Home.", "2.Select General Settings.", ...),
# unlike Subaru's spaced style ("1. Select the menu icon."). Requiring `\s+`
# here meant _split_lines never recognized ANY of Honda Pilot's own numbered
# steps as steps at all -- they fell through to plain paragraph/prose grouping
# instead, so `build_function_spec`'s `procedure` list came out empty (no
# Procedure section, no test-readiness) for functions whose real content is
# entirely step-driven (confirmed: "27. HFL Menus", 372-384, 0 procedure steps
# despite pages full of "N.Do X." lines). The lookahead requiring a capital
# letter right after (rather than just requiring the whitespace) is what keeps
# this from also matching an unrelated decimal number at the start of its own
# line (e.g. "3.5 V" -- "5" isn't a capital letter, so this doesn't fire).
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

# Honda Pilot's own DTP tooling draws a "note/result" bullet by reusing the
# Latin lowercase "u" code point in a dedicated symbol font (HONDACommon) --
# the exact same reused-glyph trick already known from the running-head
# arrows (see infrastructure.pdf_reader.read_running_head_breadcrumbs), just
# used here inline within body paragraphs instead of the page margin.
# Confirmed real, 2026-09-03, Honda Pilot p.385 (CabinTalk®): the character
# rendered as "u" directly before "Select OFF to mute your voice." is in
# font `HONDACommon`, same as the running-head separator, while every other
# "u" on that same page (inside real words like "your"/"audio") is in the
# ordinary body font (FrutigerLTStd-*). Distinguishing by FONT would need
# character-level PDF access this module doesn't have (pure domain layer,
# works on already-extracted Line text) -- but the glyph is reliably
# recognizable by its own TEXT SHAPE instead: it always sits directly against
# a capitalized word with no space ("uSelect", "uWhen", "uIf", "uThe",
# "uConfirm", "uHFL" -- confirmed real across many pages), a shape no real
# English word has (a lowercase "u" is never immediately followed by a
# capital letter with nothing between). The original app's own real output
# for this exact sentence confirms both halves of the fix this pattern
# drives: the glyph is dropped entirely ("Select OFF to mute your voice.",
# no leading "u") and the note becomes its own separate row, never merged
# into the step/sentence before it ("26-hfl-menus.md": step "2. Select
# CabinTalk." and the note "Select OFF to mute your voice." are two distinct
# table rows, not one fused sentence).
_NOTE_GLYPH = re.compile(r"(?<!\S)u(?=[A-Z])")


def strip_leading_note_glyph(text: str) -> str:
    """Public wrapper around _NOTE_GLYPH for callers outside this module that
    only ever need to drop a LEADING occurrence (e.g. a figure caption, which
    is otherwise quoted verbatim -- see application.use_cases._extract_figures.
    Unlike the mid-paragraph splitting _split_bullets does, a caption is a
    single short phrase, not a paragraph to split into multiple rows -- only
    strip, never split, and only when the glyph is the very first thing (a
    real occurrence is always sentence-initial in the confirmed data)."""
    return _NOTE_GLYPH.sub("", text, count=1) if _NOTE_GLYPH.match(text) else text


def _split_bullets(paragraph: str) -> list[tuple[str, bool]]:
    """Split on inline bullet glyphs (or Honda's "u"-glyph note marker, see
    _NOTE_GLYPH), returning (text, is_bullet) pairs.

    A paragraph that starts with prose before its first split point yields that
    lead-in as (text, False) and every split after it as (text, True). A
    paragraph that starts directly with a bullet/note glyph (no lead-in at
    all — a group made of nothing but list items) must not have its first
    item mislabeled as lead-in text: a split matched at the very start of the
    string produces a leading empty piece, which is what signals that case
    here.
    """
    if not any(ch in paragraph for ch in _BULLET_CHARS) and not _NOTE_GLYPH.search(paragraph):
        return [(paragraph, False)]

    positions = []
    for m in re.finditer(r"(?<!\S)[" + _BULLET_CHARS + r"]|" + _NOTE_GLYPH.pattern, paragraph):
        lo = max(0, m.start() - _BULLET_ISOLATION_CHARS)
        hi = min(len(paragraph), m.end() + _BULLET_ISOLATION_CHARS)
        neighborhood = paragraph[lo:m.start()] + paragraph[m.end():hi]
        if not any(ch in _BULLET_CHARS for ch in neighborhood) and not _NOTE_GLYPH.search(neighborhood):
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


# Honda's own printed sub-heading marker ("■ Receiving a Call", "■Editing a
# favorite station...") sits directly against the heading text with no space,
# same layout quirk as _BULLET_CHARS -- but unlike a bullet it never starts a
# new requirement item, it's fused with the body text that follows it into one
# paragraph (confirmed 2026-09-02, Honda Pilot: "Display Setup■Changing the
# Screen Brightness." -- one requirement, not two). The original app's own
# real output for this exact same text has no "■" at all ("Changing the Screen
# Brightness"), confirming it's page typography to drop, not real content.
# Only a LEADING "■" is stripped -- it is always a heading marker at the start
# of the section's own paragraph, never seen elsewhere in the confirmed cases.
_LEADING_HEADING_MARKER = re.compile(r"^■\s*")


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


def _split_lines(
    section: Section, heading_prefixes: tuple[str, ...] = ()
) -> tuple[list[tuple[int, int, float, str]], list[list]]:
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

    A line starting with one of the profile's own heading_prefixes (see
    LayoutConfig.heading_prefixes) is treated the same way -- it always starts a
    new paragraph group and is never merged as a step continuation, even when
    close by. Without this, a real sub-heading fuses into whatever text happens
    to sit near it (confirmed real Honda Pilot case, 2026-09-02: "■Editing a
    favorite station" fusing with the unrelated body text that followed it into
    one unreadable requirement) -- the same defect the original app
    (OnlineManualSpecTranslator) found and fixed on this exact PDF.
    """
    steps: list[list] = []
    prose_lines: list = []
    open_step_idx: int | None = None
    prev_top = None
    prev_page = None

    def _starts_new_heading(text: str) -> bool:
        return bool(heading_prefixes) and text.startswith(heading_prefixes)

    for line in _merge_orphan_step_numbers(section.lines):
        text = line.text.strip()
        if not text:
            continue
        m = _NUMBERED_STEP.match(text)
        if m and not _starts_new_heading(text):
            steps.append([int(m.group(1)), line.page, line.top, m.group(2).strip()])
            open_step_idx = len(steps) - 1
        elif (
            open_step_idx is not None
            and text[0] not in _BULLET_CHARS
            and not _NOTE_GLYPH.match(text)
            and not _starts_new_heading(text)
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
    prev_was_heading = False
    for line in prose_lines:
        text = line.text.strip()
        if not text:
            continue
        is_heading = _starts_new_heading(text)
        starts_new = False
        if current:
            if line.page != prev_page:
                starts_new = True
            elif prev_top is not None and (line.top - prev_top) > _PARAGRAPH_GAP_PT:
                starts_new = True
            # A heading line is always its own solo group -- never absorbs the
            # prose that follows it either, matching the original app's own
            # real output (a printed sub-heading becomes its own row, distinct
            # from the body text or numbered step that follows it).
            elif is_heading or prev_was_heading:
                starts_new = True
        if starts_new:
            groups.append(current)
            current = []
        current.append(line)
        prev_top = line.top
        prev_page = line.page
        prev_was_heading = is_heading
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

    steps_raw, paragraph_groups = _split_lines(section, tuple(profile.layout.heading_prefixes))
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

    offset = profile.layout.page_number_offset
    procedure: list[ProcedureStep] = []
    sequence = 0
    prev_number: int | None = None
    for number, page, top, text in steps_raw:
        # A real step's own number never decreases within one procedure -- a
        # drop back to 1 (or any non-increase) means the manual restarted the
        # numbering for a NEW, unrelated procedure (confirmed real, Honda
        # Pilot "Defaulting All the Settings": "...6.Select Reset again..."
        # immediately followed by "1.Select Home." starting a second,
        # distinct procedure on the same page). This used to be a flat
        # per-step counter (`enumerate(steps_raw, start=1)`), so every step
        # got its OWN unique "sequence" -- procedure_flowchart then chained
        # every step in the whole function into one continuous flowchart
        # regardless of these restarts, wrongly drawing an arrow from one
        # procedure's last step into an unrelated procedure's first step.
        if prev_number is None or number <= prev_number:
            sequence += 1
        prev_number = number
        procedure.append(
            ProcedureStep(number=number, text=text, sequence=sequence, source=f"p.{page + offset} / step")
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
        paragraph = _LEADING_HEADING_MARKER.sub("", _join_paragraph_lines([l.text for l in group]).strip())
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
            source = f"p.{page + offset} / {'bullet' if is_bullet else 'text'}"
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

    pages = sorted({l.page + offset for l in section.lines} | {section.page_start + offset})

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
            section.area or area_title,
            i + 1,
            figures_by_section[i] if figures_by_section else None,
            page_running_head,
        )
        for i, section in enumerate(sections)
    ]


def filter_excluded_sections(
    functions: list[FunctionSpec], excluded_titles: list[str]
) -> tuple[list[FunctionSpec], list[str]]:
    """Drop functions whose title matches one of Profile.excluded_section_titles
    (case-insensitive substring -- a real title is rarely the exact configured
    phrase verbatim, e.g. Honda's real "Honda App License Agreement" against a
    configured "License Agreement"). Returns (kept, excluded_titles_seen) so a
    caller can record what was dropped and why (see meta["excluded_sections"])
    rather than let it vanish silently -- license/copyright text isn't a real
    operable function, but a reviewer should still be able to see it was found
    and deliberately excluded, not simply missed."""
    if not excluded_titles:
        return functions, []
    needles = [t.lower() for t in excluded_titles]
    kept: list[FunctionSpec] = []
    excluded: list[str] = []
    for fn in functions:
        title_lower = fn.title.lower()
        if any(n in title_lower for n in needles):
            excluded.append(fn.title)
        else:
            kept.append(fn)
    # chapter_number was assigned by position in the UNFILTERED list -- dropping
    # entries here would otherwise leave gaps (confirmed real, Honda Pilot,
    # 2026-09-02: "CabinTalk®" stayed numbered "32" after 4 earlier License
    # entries were filtered out, instead of renumbering down to its real "28").
    # function_id/content_id don't depend on chapter_number, so renumbering here
    # is safe -- it doesn't change identity, only display order.
    for i, fn in enumerate(kept, start=1):
        fn.chapter_number = str(i)
    return kept, excluded
