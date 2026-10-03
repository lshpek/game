"""Trait metadata registry.

Traits are declared here (label, rarity hint, value multiplier) while their
detectors live in :mod:`app.game.rules`. Adding a new characteristic means
adding one entry here plus one rule - no other file changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.game.rarity import Rarity


@dataclass(frozen=True, slots=True)
class Trait:
    """Static description of a number characteristic."""

    code: str
    label: str
    description: str
    rarity_hint: Rarity = Rarity.COMMON
    value_multiplier: float = 1.0


TRAITS: dict[str, Trait] = {
    trait.code: trait
    for trait in (
        Trait("all_same", "All Same", "Every digit is identical.", Rarity.EPIC, 8.0),
        Trait("four_of_kind", "Four of a Kind", "A four-digit repetition.", Rarity.EPIC, 8.0),
        Trait("triple", "Triple", "Three identical digits.", Rarity.RARE, 3.0),
        Trait("two_pairs", "Two Pairs", "Two distinct pairs of digits.", Rarity.RARE, 2.2),
        Trait("pair", "Pair", "One repeated pair of digits.", Rarity.UNCOMMON, 1.35),
        Trait("ascending", "Ascending", "Digits increase from left to right.", Rarity.RARE, 2.0),
        Trait("descending", "Descending", "Digits decrease from left to right.", Rarity.RARE, 2.0),
        Trait("palindrome", "Palindrome", "Reads the same forwards and backwards.", Rarity.RARE, 2.0),
        Trait("repeated_pattern", "Repeated Pattern", "Two identical halves such as ABAB.", Rarity.RARE, 3.0),
        Trait("contains_777", "Contains 777", "The sequence 777 appears in the number.", Rarity.UNCOMMON, 2.0),
        Trait("contains_666", "Contains 666", "The sequence 666 appears in the number.", Rarity.UNCOMMON, 1.8),
        Trait("contains_123", "Contains 123", "The sequence 123 appears in the number.", Rarity.RARE, 1.8),
        Trait("contains_000", "Contains 000", "The sequence 000 appears in the number.", Rarity.RARE, 2.0),
        Trait("round_number", "Round Number", "Ends in two or more zeros.", Rarity.UNCOMMON, 1.3),
        Trait("year_like", "Year-like", "Looks like a calendar year.", Rarity.UNCOMMON, 1.25),
        Trait("lucky_pattern", "Lucky", "Digit composition associated with luck.", Rarity.UNCOMMON, 1.7),
        Trait("meme_pattern", "Meme", "Recognisable internet culture pattern.", Rarity.EPIC, 2.5),
        Trait("low_number", "Low Roller", "Below 100 - a rare short number.", Rarity.UNCOMMON, 1.4),
        Trait("sequence", "Sequence", "A run of three or more consecutive digits.", Rarity.RARE, 1.9),
    )
}

TRAIT_CODES: tuple[str, ...] = tuple(TRAITS)


def get_trait(code: str) -> Trait | None:
    return TRAITS.get(code)


def trait_labels(codes: list[str]) -> list[str]:
    return [TRAITS[code].label for code in codes if code in TRAITS]
