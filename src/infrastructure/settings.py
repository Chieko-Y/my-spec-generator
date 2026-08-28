"""Single place default paths live (no hardcoded paths elsewhere in the codebase).
Override via environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Explicit path (not bare load_dotenv()) so this doesn't depend on the CWD the
# app happens to be launched from.
load_dotenv(PROJECT_ROOT / ".env")

LIBRARY_DIR = Path(os.environ.get("SPECGEN_LIBRARY_DIR", PROJECT_ROOT / "data" / "library"))
WORKSPACE_DIR = Path(os.environ.get("SPECGEN_WORKSPACE_DIR", PROJECT_ROOT / "workspace"))
CONFIG_DIR = Path(os.environ.get("SPECGEN_CONFIG_DIR", PROJECT_ROOT / "config"))
STATIC_DIR = Path(os.environ.get("SPECGEN_STATIC_DIR", PROJECT_ROOT / "static"))
PORT = int(os.environ.get("SPECGEN_PORT", "8711"))
HOST = os.environ.get("SPECGEN_HOST", "127.0.0.1")

# The one AI call in this app (see application/ports.py ChapterClassifier) --
# used only by profile-classify-chapters, never at generate()/runtime.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# gemini-2.5-flash/-pro/-flash-lite were all retired for new callers as of this
# writing (confirmed directly: 404 "no longer available to new users" for all
# three, even though they still appear in ListModels), the pinned preview
# gemini-3.6-flash timed out repeatedly in testing, and gemini-flash-latest
# returned 503 "currently experiencing high demand" on the real ~60-candidate
# request even though a trivial prompt succeeded on it. gemini-flash-lite-latest
# is the one that actually completed the real request reliably in testing.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
