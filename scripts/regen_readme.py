"""Regenerate the README matrix block from code: python scripts/regen_readme.py"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from hopscope.meter.matrix import format_matrix, run_matrix

START = "<!-- matrix:start -->\n```text\n"
END = "\n```\n<!-- matrix:end -->"


def main() -> int:
    path = Path(__file__).resolve().parents[1] / "README.md"
    text = path.read_text(encoding="utf-8")
    i, j = text.index(START) + len(START), text.index(END)
    new = text[:i] + format_matrix(asyncio.run(run_matrix(10))) + text[j:]
    path.write_text(new, encoding="utf-8")
    print("README matrix", "updated" if new != text else "unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
