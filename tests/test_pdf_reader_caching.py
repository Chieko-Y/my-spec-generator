"""Regression tests for PdfManualReader.read()'s in-process cache, added
2026-09-03 to fix a real performance problem: generate() re-scans the WHOLE
document on every call regardless of which chapter was asked for, confirmed
the dominant cost for a large manual (Honda Pilot, 700+ pages: 1-2 minutes per
call) -- a second chapter of the same manual paid the full re-read again with
nothing to show for the first one.
"""
from __future__ import annotations

import os
import sys
import subprocess
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure.pdf_reader import PdfManualReader

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_PDF = PROJECT_ROOT / "scratch" / "test_manual.pdf"


def _ensure_test_pdf() -> None:
    if TEST_PDF.exists():
        return
    subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "make_test_pdf.py")],
        check=True,
        cwd=str(PROJECT_ROOT),
    )


def test_a_second_read_of_the_same_pdf_and_columns_is_served_from_cache():
    _ensure_test_pdf()
    reader = PdfManualReader()

    lines1, bookmarks1 = reader.read(str(TEST_PDF), columns=1)
    lines2, bookmarks2 = reader.read(str(TEST_PDF), columns=1)

    # Identity, not just equality -- the whole point is the second call never
    # re-scanned the PDF at all, it returned the exact cached objects.
    assert lines2 is lines1
    assert bookmarks2 is bookmarks1


def test_a_different_columns_value_is_a_cache_miss_not_stale_data():
    _ensure_test_pdf()
    reader = PdfManualReader()

    lines1, _ = reader.read(str(TEST_PDF), columns=1)
    lines2, _ = reader.read(str(TEST_PDF), columns=2)

    assert lines2 is not lines1


def test_replacing_the_pdf_on_disk_invalidates_the_cache():
    """A corrected re-upload under the same path must not silently keep
    serving the old scan -- mtime rides along in the cache key specifically
    so this can never happen."""
    _ensure_test_pdf()
    reader = PdfManualReader()

    lines1, _ = reader.read(str(TEST_PDF), columns=1)

    # Touch the file with a distinctly later mtime (some filesystems have
    # coarse mtime resolution -- back it off by a full 2 seconds so this
    # can't flake).
    new_mtime = os.path.getmtime(str(TEST_PDF)) + 2
    os.utime(str(TEST_PDF), (new_mtime, new_mtime))

    lines2, _ = reader.read(str(TEST_PDF), columns=1)

    assert lines2 is not lines1
    assert lines2 == lines1  # same PDF content, just re-scanned, not corrupted
