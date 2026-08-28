"""Regression test for a real bug found in manual testing: pypdfium2 (which wraps the
native, not-thread-safe PDFium library) silently returned 0 bookmarks for a real
207-bookmark PDF when the read happened on a FastAPI threadpool worker thread instead
of the main thread — no exception, just wrong data, which made generate() fail with
"no sections could be cut" for a perfectly good chapter selection.

Fix: infrastructure/pdf_reader.py now pins every pypdfium2 call to one dedicated
thread via _PDFIUM_EXECUTOR. This test calls outline_preview() concurrently from many
different threads (the same shape of access FastAPI's threadpool produces) and checks
every call still sees the full bookmark set.
"""
from __future__ import annotations

import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor
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


def test_bookmarks_are_consistent_across_threads():
    _ensure_test_pdf()
    reader = PdfManualReader()

    baseline_count, baseline_bookmarks = reader.outline_preview(str(TEST_PDF))
    assert baseline_count > 0
    assert len(baseline_bookmarks) > 0, "the fixture PDF must actually have bookmarks for this test to mean anything"

    def read_from_a_worker_thread(_):
        _, bookmarks = reader.outline_preview(str(TEST_PDF))
        return len(bookmarks)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(read_from_a_worker_thread, range(20)))

    assert all(count == len(baseline_bookmarks) for count in results), (
        f"bookmark count was inconsistent across threads: {results} "
        f"(expected {len(baseline_bookmarks)} every time)"
    )
