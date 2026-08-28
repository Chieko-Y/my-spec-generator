"""Machine check: domain/ imports stdlib (+ domain itself) only. Run:
    python tests/check_layers.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DOMAIN_DIR = SRC / "domain"

STDLIB_ALLOWED_PREFIXES = None  # populated lazily below


def _stdlib_module_names() -> set[str]:
    return set(sys.stdlib_module_names)


def _imported_top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import within domain — always allowed
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def main() -> int:
    stdlib = _stdlib_module_names()
    failures: list[str] = []

    for path in sorted(DOMAIN_DIR.glob("*.py")):
        for name in _imported_top_level_names(path):
            if name in stdlib or name == "domain" or name == "__future__":
                continue
            failures.append(f"{path.relative_to(ROOT)}: imports {name!r} (domain must be stdlib-only)")

    if failures:
        print("check_layers: FAIL")
        for f in failures:
            print(f"  {f}")
        return 1

    print("check_layers: PASS (domain/ is stdlib-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
