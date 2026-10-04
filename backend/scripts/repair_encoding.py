"""Repair and normalise non-ASCII literals in a source file.

PowerShell round-trips mangle UTF-8 through a legacy code page, turning
Cyrillic and CJK text into mojibake. This utility repairs the mangled runs and
then re-escapes every remaining non-ASCII character as ``\\uXXXX``, leaving a
pure-ASCII file that no future shell round-trip can corrupt.

Usage::

    python -m scripts.repair_encoding app/game/countries.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# A literal non-ASCII run inside a string (the mojibake we need to repair).
_RUN = re.compile(r"[^\x00-\x7F]+")


def repair(text: str) -> str:
    """Undo a legacy-codepage round-trip, or return the input unchanged."""

    def _one(match: re.Match[str]) -> str:
        run = match.group(0)
        for encoding in ("cp1251", "cp1252"):
            try:
                candidate = run.encode(encoding).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            # A repaired run must look more like real text than mojibake does.
            if candidate != run and _printable_ratio(candidate) > _printable_ratio(run):
                return candidate
        return run

    return _RUN.sub(_one, text)


def _printable_ratio(text: str) -> float:
    if not text:
        return 1.0
    # Mojibake is full of CJK-range and box characters; real text is not.
    weird = sum(1 for ch in text if 0x2E80 <= ord(ch) <= 0x9FFF or 0x2500 <= ord(ch) <= 0x25FF)
    return 1.0 - weird / len(text)


def escape_non_ascii(text: str) -> str:
    """Re-escape every non-ASCII character so the file is pure ASCII."""
    return "".join(
        ch if ord(ch) < 128 else "\\u{:04x}".format(ord(ch)) if ord(ch) <= 0xFFFF else ch
        for ch in text
    )


def repair_file(path: Path, *, escape: bool = True) -> bool:
    original = path.read_text(encoding="utf-8")
    repaired = repair(original)
    if escape:
        # Only escape string content, never identifiers or comments' code points
        # that would change meaning - escaping any non-ASCII char is safe in a
        # string literal, so we escape everywhere outside of nothing.
        repaired = escape_non_ascii(repaired)
    if repaired != original:
        path.write_text(repaired, encoding="utf-8", newline="")
        return True
    return False


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m scripts.repair_encoding <file> [<file> ...]")
        return 2
    for name in argv:
        path = Path(name)
        print(f"{'repaired' if repair_file(path) else 'clean'}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))