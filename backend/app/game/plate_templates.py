"""Plate template language.

A template is a string of literal separators and placeholder tokens::

    "LDDD LLL DD"     -> A777 AA 77
    "DD LLD DDD"      -> 77 XX 777
    "LL-DDDD-LL"      -> AB-7777-CD

Tokens
------
``L``  a letter drawn from the country alphabet
``D``  a digit 0-9
``F<n>``  a fixed literal digit, e.g. ``F7`` always emits ``7``
``R``  the region code (empty when the country has no regions)
``X[1234]``  a digit restricted to a choice set
``A[ABC]``  a letter restricted to a choice set

Any other character is copied verbatim (spaces, dashes, dots, bullets). Templates
are declarative data: adding a country never requires touching this module.
Unicode
-------

``normalize_plate`` is Unicode-safe: Latin, Cyrillic, Georgian, Armenian and
Japanese characters all survive. Only separator-ish characters (spaces, dashes,
dots, bullets, slashes, brackets) are collapsed into single spaces; every other
character is kept and case-folded. Lookup keys are therefore stable across
alphabets and safe to index.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.core.errors import ValidationError

MAX_PATTERN_LENGTH = 96
# Every token kind that may be followed by a ``[choices]`` group.
_CHOICE_RE = re.compile(r"^([LDFRAX])\[([^\]]+)\]$")
TOKEN_KINDS = frozenset({"L", "D", "F", "R", "X", "A"})


@dataclass(frozen=True, slots=True)
class Token:
    """One parsed variable element of a template."""

    kind: str
    choices: tuple[str, ...] = ()

    def is_literal(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Literal:
    """A run of literal characters (separator)."""

    text: str

    def is_literal(self) -> bool:
        return True


@dataclass(slots=True)
class ParsedTemplate:
    """Result of :func:`parse_template`."""

    pattern: str
    parts: list[Token | Literal] = field(default_factory=list)

    @property
    def letter_slots(self) -> int:
        return sum(1 for p in self.parts if not p.is_literal() and p.kind in ("L", "A"))

    @property
    def digit_slots(self) -> int:
        return sum(1 for p in self.parts if not p.is_literal() and p.kind in ("D", "X", "F"))

    @property
    def has_region_slot(self) -> bool:
        return any(not p.is_literal() and p.kind == "R" for p in self.parts)

    def signature(self) -> str:
        """Canonical shape, e.g. ``LDDDLLLDD`` - used to group templates."""
        return "".join("?" if p.is_literal() else p.kind for p in self.parts)


def _token_from(chunk: str) -> Token:
    """Build a token from a pattern chunk such as ``L``, ``D[7]`` or ``F12``."""
    if len(chunk) == 1:
        kind = chunk
        if kind not in TOKEN_KINDS:
            raise ValidationError(f"Unknown template token: {kind!r}", code="BAD_PLATE_TEMPLATE")
        if kind == "F":
            # ``F`` only makes sense with its literal digits (``F7``).
            raise ValidationError(
                "``F`` must be followed by digits, e.g. ``F7``.", code="BAD_PLATE_TEMPLATE"
            )
        return Token("L" if kind in ("L", "A") else ("D" if kind in ("D", "X") else kind))

    match = _CHOICE_RE.match(chunk)
    if match is None:
        raise ValidationError(f"Malformed template token: {chunk!r}", code="BAD_PLATE_TEMPLATE")
    kind, body = match.group(1), match.group(2)
    if not body:
        raise ValidationError(f"Empty choice set in {chunk!r}", code="BAD_PLATE_TEMPLATE")
    if kind == "F":
        if not body.isdigit():
            raise ValidationError(f"``F`` needs digits, got {body!r}", code="BAD_PLATE_TEMPLATE")
        return Token("F", tuple(body))
    return Token("L" if kind in ("L", "A") else "D", tuple(body))


def parse_template(pattern: str) -> ParsedTemplate:
    """Parse a pattern into literal/token parts.

    Raises ``ValidationError`` for malformed templates so a bad row fails loudly
    at seed/test time instead of silently producing junk plates.
    """
    text = (pattern or "").strip()
    if not text:
        raise ValidationError("Plate template pattern cannot be empty.", code="BAD_PLATE_TEMPLATE")
    if len(text) > MAX_PATTERN_LENGTH:
        raise ValidationError("Plate template pattern is too long.", code="BAD_PLATE_TEMPLATE")

    parts: list[Token | Literal] = []
    buffer: list[str] = []
    index = 0

    while index < len(text):
        char = text[index]

        # ``F12`` - a run of fixed digits.
        if char == "F" and index + 1 < len(text) and text[index + 1].isdigit():
            if buffer:
                parts.append(Literal("".join(buffer)))
                buffer = []
            index += 1
            fixed: list[str] = []
            while index < len(text) and text[index].isdigit():
                fixed.append(text[index])
                index += 1
            parts.append(_token_from("F[" + "".join(fixed) + "]"))
            continue

        # ``D[7]`` - a choice group; the kind letter sits just before ``[``.
        # This must be checked *before* the single-token branch below, otherwise
        # ``X[6789]`` would consume ``X`` as a plain token and then see an
        # unbalanced group.
        if char == "[":
            close = text.find("]", index)
            if close == -1 or index == 0:
                raise ValidationError(
                    f"Unbalanced choice group in {pattern!r}", code="BAD_PLATE_TEMPLATE"
                )
            kind = text[index - 1]
            if kind not in TOKEN_KINDS:
                raise ValidationError(
                    f"Choice group must follow a token, got {kind!r}", code="BAD_PLATE_TEMPLATE"
                )
            # Drop the kind letter we already buffered as a literal.
            if buffer:
                buffer.pop()
                if buffer:
                    parts.append(Literal("".join(buffer)))
                buffer = []
            parts.append(_token_from(f"{kind}[{text[index + 1 : close]}]"))
            index = close + 1
            continue

        # ``X`` is a token kind too - but when it directly precedes ``[``,
        # it is the group's kind letter, not a slot of its own. Defer to the
        # ``[`` branch below (which pops it back off the buffer), otherwise a
        # bare token would be double-counted alongside the group token.
        if char in TOKEN_KINDS and not (
            index + 1 < len(text) and text[index + 1] == "["
        ):
            if buffer:
                parts.append(Literal("".join(buffer)))
                buffer = []
            parts.append(_token_from(char))
            index += 1
            continue

        buffer.append(char)
        index += 1

    if buffer:
        parts.append(Literal("".join(buffer)))
    if not any(not p.is_literal() for p in parts):
        raise ValidationError(f"Template {pattern!r} has no variable slots.", code="BAD_PLATE_TEMPLATE")
    return ParsedTemplate(pattern=text, parts=parts)


def normalize_plate(text: str) -> str:
    """Canonical lookup key: Unicode-safe, case-folded, separators collapsed.

    Unlike a naive ``[^A-Z0-9]`` filter this never destroys non-Latin alphabets.
    Separator-like characters (space, dash, dot, bullet, slash, brackets) become
    a single space; every remaining character is preserved after NFKC folding so
    visually identical inputs share one canonical key.
    """
    if not text:
        return ""
    folded = unicodedata.normalize("NFKC", text).strip().upper()
    chars = []
    for char in folded:
        if char.isalnum():
            chars.append(char)
        else:
            chars.append(" ")
    return re.sub(r"\s+", " ", "".join(chars)).strip()


__all__ = [
    "MAX_PATTERN_LENGTH",
    "TOKEN_KINDS",
    "Literal",
    "ParsedTemplate",
    "Token",
    "normalize_plate",
    "parse_template",
]
