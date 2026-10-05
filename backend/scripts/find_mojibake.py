"""Report (and optionally repair) cp1251-mojibake inside Python string literals.

Some legacy files in this repository were once saved with their UTF-8 bytes decoded
as Windows-1251, so ``"Москва"`` became ``"РЌРѕСЃРєРІР°"``. The repair is the exact
inverse - encode the literal back to cp1251 bytes and decode as UTF-8 - and it is
only applied when the round trip succeeds, so already-correct text is never touched.

    python scripts/find_mojibake.py [--fix] [path ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')


def repair(text: str) -> str | None:
    """Undo one layer of cp1251 mojibake, or return ``None`` if it does not apply."""
    try:
        fixed = text.encode("cp1251").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    return None if fixed == text else fixed


def scan(path: Path, fix: bool) -> int:
    source = path.read_text(encoding="utf-8")
    hits = 0

    def _sub(match: re.Match[str]) -> str:
        nonlocal hits
        fixed = repair(match.group(1))
        if fixed is None:
            return match.group(0)
        hits += 1
        return f'"{fixed}"'

    repaired = LITERAL.sub(_sub, source)
    if hits and fix:
        path.write_text(repaired, encoding="utf-8")
    return hits


def main(argv: list[str]) -> int:
    fix = "--fix" in argv
    targets = [Path(item) for item in argv if not item.startswith("--")]
    if not targets:
        targets = [
            path
            for path in Path(".").rglob("*.py")
            if not any(part in {".git", "node_modules", "__pycache__"} for part in path.parts)
        ]
    total = 0
    for path in sorted(targets):
        hits = scan(path, fix)
        if hits:
            total += hits
            print(f"{path}: {hits} literal(s) {'repaired' if fix else 'need repair'}")
    print(f"total: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
