"""Regression tests for domain.spec_building._split_bullets — locks in the 3
real-Subaru-PDF cases found and fixed 2026-08-26. Each fix in this history broke a
*different* real case than the one that motivated it (see docs/HANDOVER.md), so this
file exists to make sure a future edit can't silently reintroduce any of them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain.spec_building import (
    _LEADING_HEADING_MARKER,
    _NOTE_GLYPH,
    _split_bullets,
    _split_lines,
    strip_leading_note_glyph,
)


def test_plain_paragraph_with_no_bullets_is_untouched():
    text = "Recognizable voice commands and their actions are shown below."
    assert _split_bullets(text) == [(text, False)]


def test_real_spaced_bullet_list_splits_into_one_item_per_bullet():
    text = (
        "server: ● Displaying traffic information. "
        "● Displaying parking information."
    )
    result = _split_bullets(text)
    assert result == [
        ("server:", False),
        ("Displaying traffic information.", True),
        ("Displaying parking information.", True),
    ]


def test_bullet_with_no_space_after_it_still_splits():
    """Real Subaru wording: '●Operate the touch screen...' with zero space
    between the bullet glyph and the word. An earlier version of the fix required
    trailing whitespace after the bullet and wrongly left this fused onto the word."""
    text = "Center information display ●Operate the touch screen by directly touching it."
    result = _split_bullets(text)
    assert result == [
        ("Center information display", False),
        ("Operate the touch screen by directly touching it.", True),
    ]


def test_multiple_no_space_bullets_in_one_paragraph():
    text = (
        "VOLUME knob ●Turn the knob to adjust the volume. "
        "●Press the knob to turn the volume mute on/off."
    )
    result = _split_bullets(text)
    assert result == [
        ("VOLUME knob", False),
        ("Turn the knob to adjust the volume.", True),
        ("Press the knob to turn the volume mute on/off.", True),
    ]


def test_placeholder_circles_packed_together_are_not_treated_as_bullets():
    """Real Subaru wording: a footnote explaining the manual's own placeholder
    notation, '● <○○○> descriptions in the command lists below signify
    numbers/titles/names to be spoken.' The leading ● is a real bullet (strip it,
    is_bullet=True); the three ○ inside <...> are decorative, not a 3-item list —
    naive splitting on every ○ character used to shred this down to a stray '>'."""
    text = (
        "● <○○○> descriptions in the command lists below signify "
        "numbers/titles/names to be spoken."
    )
    result = _split_bullets(text)
    assert result == [
        (
            "<○○○> descriptions in the command lists below signify "
            "numbers/titles/names to be spoken.",
            True,
        )
    ]


def test_placeholder_circles_with_a_spurious_extra_space_are_not_treated_as_bullets():
    """Real Subaru wording, a second footnote in the same style — but this time
    pdfplumber's own word segmentation inserted a genuine extra space in the middle
    of one '○○○' cluster ('○○ ○' instead of '○○○'), which passed an
    earlier, looser version of the leading-whitespace check and shredded the
    sentence into two rows with a character silently dropped."""
    text = (
        "● In this manual, screen buttons and displays are described as "
        "“○○○”. In Owner’s Manuals of some languages, they are described as "
        "“○○ ○)”. Displays after languages are changed in the settings screen "
        "are described as “(○○○)”."
    )
    result = _split_bullets(text)
    assert len(result) == 1
    item, is_bullet = result[0]
    assert is_bullet is True
    # every character of the original sentence (all four circle-clusters) survives —
    # this is the actual regression check, not just "it didn't crash"
    assert item.count("○") == 9
    assert item.startswith("In this manual")
    assert item.endswith("”.")


def test_leading_heading_marker_is_stripped():
    """Real Honda Pilot case, 2026-09-02: "■" is Honda's own printed sub-heading
    marker, sitting directly against the heading text with no space
    ("■Changing the Screen Brightness."). The original app's own real output for
    this exact text has no "■" at all -- confirmed directly
    (workspace/honda/pilot-2026/features/published/9-display-setup.md: "Changing
    the Screen Brightness", source=heading). Reported by the user as showing up
    in the rebuild's requirement text ("手順に■Receiving a Call.とかある")."""
    assert _LEADING_HEADING_MARKER.sub("", "■Changing the Screen Brightness.") == "Changing the Screen Brightness."
    assert _LEADING_HEADING_MARKER.sub("", "■ Receiving a Call") == "Receiving a Call"


def test_leading_heading_marker_only_strips_a_leading_occurrence():
    # "■" mid-sentence (not the confirmed real case) is left alone -- only ever
    # seen at the very start of the paragraph in the real data.
    text = "Select the ■ icon to continue."
    assert _LEADING_HEADING_MARKER.sub("", text) == text


def test_honda_note_glyph_is_split_off_and_stripped():
    """Real Honda Pilot case, 2026-09-03: "u" reused as a note/result bullet
    glyph in font HONDACommon (same reused-glyph trick as the running-head
    arrows, see infrastructure.pdf_reader) sits directly against a
    capitalized word with no space ("uSelect OFF to mute your voice.").
    Reported by the user ("28. CabinTalk®でステップがSelect CabinTalk.
    uSelect OFF to mute your voice.と出てる"). The original app's own real
    output for this exact text has no "u" and treats it as its own separate
    row (26-hfl-menus.md: "Select CabinTalk." and "Select OFF to mute your
    voice." are two distinct table rows, not one fused sentence)."""
    text = "Select CabinTalk. uSelect OFF to mute your voice."
    result = _split_bullets(text)
    assert result == [
        ("Select CabinTalk.", False),
        ("Select OFF to mute your voice.", True),
    ]


def test_note_glyph_regex_matches_only_the_confirmed_real_shapes():
    assert _NOTE_GLYPH.search("uSelect OFF to mute your voice.")
    assert _NOTE_GLYPH.search("uWhen you select Proceed Now, the update begins.")
    assert not _NOTE_GLYPH.search("your audio system")
    assert not _NOTE_GLYPH.search("until you find a mode")


def test_note_glyph_does_not_misfire_on_a_real_word():
    """A real lowercase "u" is never immediately followed by a capital letter
    with nothing between in ordinary English prose -- this shape is what
    makes the glyph safely distinguishable at the text level alone."""
    text = "Your audio system allows your voice to be used."
    assert _split_bullets(text) == [(text, False)]


def test_a_note_glyph_line_breaks_a_step_continuation_instead_of_merging():
    """The real bug: a numbered step ("2.Select CabinTalk.") was swallowing
    the very next line ("uSelect OFF to mute your voice.") as if it were the
    step's own wrapped continuation text, purely because it sat close enough
    vertically. A note-glyph line must break the continuation the same way a
    real bullet character already does."""
    from domain.manual_parsing import Line, Section

    lines = [
        Line(page=0, text="1.Select Home.", top=100.0),
        Line(page=0, text="2.Select CabinTalk.", top=110.0),
        Line(page=0, text="uSelect OFF to mute your voice.", top=120.0),
    ]
    section = Section(
        title="CabinTalk", level=0, page_start=0, page_end=1, lines=lines,
        matched_by_text=True, source_bookmark_index=0,
    )

    steps, groups = _split_lines(section)

    assert steps == [(1, 0, 100.0, "Select Home."), (2, 0, 110.0, "Select CabinTalk.")]
    assert len(groups) == 1
    assert [l.text for l in groups[0]] == ["uSelect OFF to mute your voice."]


def test_strip_leading_note_glyph_used_for_figure_captions():
    """User asked for this too, 2026-09-03: the figure caption for this same
    CabinTalk image was still showing the raw glyph ("uSelect OFF to mute
    your voice.") since caption_for (application.use_cases._extract_figures)
    is a separate code path from _split_lines/_split_bullets. Unlike a
    paragraph, a caption is one short phrase quoted verbatim -- only strip a
    LEADING occurrence, never split it into multiple pieces."""
    assert strip_leading_note_glyph("uSelect OFF to mute your voice.") == "Select OFF to mute your voice."
    # A real word is never touched, same guarantee _NOTE_GLYPH itself gives.
    assert strip_leading_note_glyph("Your audio system allows your voice.") == "Your audio system allows your voice."
    # Only a LEADING occurrence is stripped -- a mid-caption one (not a
    # confirmed real case) is left alone, matching _LEADING_HEADING_MARKER's
    # own leading-only precedent for "■".
    assert strip_leading_note_glyph("Select the icon. uThen confirm.") == "Select the icon. uThen confirm."
