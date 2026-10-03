"""Repair text files: strip UTF-8 BOMs and undo a cp1251 round trip.

Run once from the repository root after PowerShell has rewritten files:

    python backend/scripts/fix_encoding.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", ".pytest_cache", ".vite", ".ruff_cache"}
TEXT_SUFFIXES = {".py", ".ts", ".tsx", ".json", ".md", ".ini", ".toml", ".yml", ".css", ".html", ".conf", ".js"}
TEXT_NAMES = {".env", ".env.example", ".gitignore"}
NON_ASCII_RUN = re.compile(r"[^\x00-\x7f]+")


def is_cyrillic(text: str) -> bool:
    return any("\u0400" <= ch <= "\u04FF" for ch in text)


def restore(run: str) -> str | None:
    """Reverse one UTF-8 -> cp1251 -> UTF-8 round trip."""
    if not is_cyrillic(run):
        return None
    try:
        candidate = run.encode("cp1251").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None
    return None if is_cyrillic(candidate) else candidate


def repair_text(text: str) -> tuple[str, int]:
    if text.startswith("\ufeff"):
        text = text[1:]
    repaired = 0

    def handle(match: re.Match[str]) -> str:
        nonlocal repaired
        fixed = restore(match.group(0))
        if fixed is None:
            return match.group(0)
        repaired += 1
        return fixed

    return NON_ASCII_RUN.sub(handle, text), repaired


def iter_files() -> list[pathlib.Path]:
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES:
            yield path


def main() -> int:
    changed: list[str] = []
    for path in iter_files():
        try:
            original = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fixed, _ = repair_text(original)
        if fixed != original:
            path.write_text(fixed, encoding="utf-8", newline="\n")
            changed.append(str(path.relative_to(ROOT)))

    if changed:
        print(f"repaired {len(changed)} file(s):")
        for name in changed:
            print(f"  - {name}")
    else:
        print("nothing to repair")
    return 0


if __name__ == "__main__":
    sys.exit(main())
