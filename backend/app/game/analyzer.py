"""Number analyzer: turns a 4-digit string into traits and a natural rarity."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import ValidationError
from app.game.constants import NUMBER_FORMAT, NUMBER_MAX, NUMBER_MIN
from app.game.rarity import SPECIAL_NUMBER_RARITY, Rarity, max_rarity, rarity_rank
from app.game.rules import ALL_RULES, Rule, longest_consecutive_run
from app.game.traits import TRAITS


@dataclass(frozen=True, slots=True)
class NumberAnalysis:
    """Deterministic analysis of a single number."""

    number: str
    value: int
    traits: list[str]
    rarity: Rarity
    sequence_length: int
    is_special: bool
    tags: list[str] = field(default_factory=list)

    @property
    def trait_labels(self) -> list[str]:
        return [TRAITS[code].label for code in self.traits if code in TRAITS]

    def to_dict(self) -> dict[str, object]:
        return {
            "number": self.number,
            "value": self.value,
            "traits": self.traits,
            "rarity": self.rarity.value,
            "sequence_length": self.sequence_length,
            "is_special": self.is_special,
            "tags": self.tags,
        }


def normalize_number(raw: str | int) -> str:
    """Zero-pad any input into the canonical 4-digit representation."""
    text = str(raw).strip()
    if not text.isdigit():
        raise ValidationError("Number must contain digits only.", code="INVALID_NUMBER")
    value = int(text)
    if not (NUMBER_MIN <= value <= NUMBER_MAX):
        raise ValidationError("Number must be between 0000 and 9999.", code="INVALID_NUMBER")
    return f"{value:{NUMBER_FORMAT}}"


def natural_rarity(number: str, matched_traits: list[str]) -> Rarity:
    """Highest rarity implied either by special table or by trait hints."""
    hint = SPECIAL_NUMBER_RARITY.get(number)
    if hint is not None:
        return hint
    rarity = Rarity.COMMON
    for code in matched_traits:
        trait = TRAITS.get(code)
        if trait is not None and rarity_rank(trait.rarity_hint) > rarity_rank(rarity):
            rarity = trait.rarity_hint
    return rarity


def build_tags(number: str, matched_traits: list[str]) -> list[str]:
    """Human-facing tags shown on cards and used by filters."""
    tags: list[str] = []
    if number in SPECIAL_NUMBER_RARITY:
        tags.append("special")
    if "palindrome" in matched_traits:
        tags.append("mirror")
    if "ascending" in matched_traits or "descending" in matched_traits:
        tags.append("ordered")
    if "meme_pattern" in matched_traits:
        tags.append("meme")
    if int(number) < 10:
        tags.append("tiny")
    if number.startswith("0"):
        tags.append("leading-zero")
    return tags


def analyze(raw: str | int, rules: tuple[Rule, ...] = ALL_RULES) -> NumberAnalysis:
    """Analyse a number using the rule registry."""
    number = normalize_number(raw)
    matched = [rule.code for rule in rules if rule.matches(number)]
    rarity = natural_rarity(number, matched)
    return NumberAnalysis(
        number=number,
        value=int(number),
        traits=matched,
        rarity=rarity,
        sequence_length=longest_consecutive_run(number),
        is_special=number in SPECIAL_NUMBER_RARITY,
        tags=build_tags(number, matched),
    )


def combine_with_luck(natural: Rarity, luck: Rarity) -> Rarity:
    """Final rarity is the more prestigious of the natural and rolled rarity."""
    return max_rarity(natural, luck)
