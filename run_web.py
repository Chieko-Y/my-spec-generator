#!/usr/bin/env python
"""Start the web UI. Usage: python run_web.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import uvicorn

from infrastructure import settings

if __name__ == "__main__":
    uvicorn.run("presentation.web:app", host=settings.HOST, port=settings.PORT, reload=False)
