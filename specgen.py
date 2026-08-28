#!/usr/bin/env python
"""CLI entry point. Usage: python specgen.py <command> ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from presentation.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
