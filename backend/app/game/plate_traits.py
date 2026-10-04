"""Plate trait registry.

Each entry declares the label (RU/EN), the score the trait contributes to
``rarity_score``, the rarity floor it implies and the value multiplier it earns.
Detectors live in :mod:`app.game.plate_patterns`; adding a trait means adding one
``TraitDef`` plus one detector entry - no other file changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TraitDef:
    code: str
    label_en: str
    label_ru: str
    score: int
    rarity_hint: str = "COMMON"
    value_multiplier: float = 1.0
    category: str = "NUMBER"


PLATE_TRAITS: dict[str, TraitDef] = {
    trait.code: trait
    for trait in (
        # --- number repetition
        TraitDef("all_same", "All Same", "Все одинаковые", 46, "EPIC", 2.6, "NUMBER"),
        TraitDef("four_of_kind", "Four of a Kind", "Четыре одинаковых", 50, "EPIC", 2.8, "NUMBER"),
        TraitDef("triple", "Triple", "Тройка", 26, "RARE", 1.7, "NUMBER"),
        TraitDef("two_pairs", "Two Pairs", "Две пары", 18, "RARE", 1.4, "NUMBER"),
        TraitDef("pair", "Pair", "Пара", 8, "UNCOMMON", 1.12, "NUMBER"),
        # --- order and symmetry
        TraitDef("ascending", "Ascending", "По возрастанию", 22, "RARE", 1.5, "NUMBER"),
        TraitDef("descending", "Descending", "По убыванию", 22, "RARE", 1.5, "NUMBER"),
        TraitDef("palindrome", "Palindrome", "Палиндром", 26, "RARE", 1.6, "NUMBER"),
        TraitDef("repeated_pattern", "Repeated Pattern", "Повторяющийся блок", 20, "RARE", 1.45, "NUMBER"),
        TraitDef("sequence", "Sequence", "Последовательность", 16, "UNCOMMON", 1.25, "NUMBER"),
        # --- lucky / meme
        TraitDef("contains_777", "Triple 7", "Тройная семёрка", 28, "RARE", 1.8, "LUCKY"),
        TraitDef("contains_666", "Triple 6", "Тройная шестёрка", 16, "UNCOMMON", 1.3, "LUCKY"),
        TraitDef("contains_123", "Contains 123", "Содержит 123", 14, "UNCOMMON", 1.2, "LUCKY"),
        TraitDef("contains_007", "007", "007", 24, "RARE", 1.6, "LUCKY"),
        TraitDef("contains_000", "Triple 0", "Тройной ноль", 18, "UNCOMMON", 1.3, "LUCKY"),
        TraitDef("lucky_pattern", "Lucky", "Счастливая комбинация", 14, "UNCOMMON", 1.3, "LUCKY"),
        TraitDef("leading_zeros", "Leading Zeros", "Ведущие нули", 10, "UNCOMMON", 1.15, "NUMBER"),
        TraitDef("round_number", "Round Number", "Круглое число", 8, "UNCOMMON", 1.1, "NUMBER"),
        TraitDef("year_like", "Year-like", "Похоже на год", 10, "UNCOMMON", 1.2, "NUMBER"),
        TraitDef("meme_pattern", "Meme", "Мем", 24, "RARE", 1.7, "LUCKY"),
        # --- special combinations inside a plate
        TraitDef("special_run", "Special Combination", "Особая комбинация", 30, "RARE", 1.9, "SPECIAL"),
        TraitDef("special_code", "Special Plate", "Особый номер", 38, "EPIC", 2.2, "SPECIAL"),
        # --- letters
        TraitDef("triple_letter", "Triple Letter", "Тройная буква", 30, "RARE", 1.8, "LETTER"),
        TraitDef("pair_letter", "Matching Letters", "Повтор букв", 14, "UNCOMMON", 1.3, "LETTER"),
        TraitDef("letter_palindrome", "Letter Mirror", "Зеркало букв", 22, "RARE", 1.5, "LETTER"),
        TraitDef("letter_ascending", "Alphabet Run", "Алфавитный ряд", 18, "RARE", 1.4, "LETTER"),
        TraitDef("alphabetical_run", "ABC Run", "Ряд ABC", 18, "RARE", 1.4, "LETTER"),
        TraitDef("repeated_letter_prefix", "Repeated Prefix", "Повтор в начале", 12, "UNCOMMON", 1.2, "LETTER"),
        TraitDef("repeated_letter_suffix", "Repeated Suffix", "Повтор в конце", 12, "UNCOMMON", 1.2, "LETTER"),
        TraitDef("mirrored_letters", "Mirrored Letters", "Зеркальные буквы", 28, "EPIC", 1.9, "LETTER"),
        # --- plate level
        TraitDef("region_match", "Rare Region Match", "Совпадение региона", 24, "RARE", 1.6, "PLATE"),
        TraitDef("number_mirrors_region", "Number Matches Region", "Номер = регион", 32, "EPIC", 2.0, "PLATE"),
        TraitDef("symmetric_plate", "Symmetric Plate", "Симметричный номер", 34, "EPIC", 2.0, "PLATE"),
        TraitDef("rare_template", "Rare Template", "Редкий формат", 12, "UNCOMMON", 1.2, "PLATE"),
    )
}

TRAIT_CODES: tuple[str, ...] = tuple(PLATE_TRAITS)


def get_trait(code: str) -> TraitDef | None:
    return PLATE_TRAITS.get(code)


def trait_labels(codes: list[str], lang: str = "en") -> list[str]:
    """Localised labels for the reason chips shown on the result screen."""
    out: list[str] = []
    for code in codes:
        trait = PLATE_TRAITS.get(code)
        if trait is None:
            out.append(code.replace("_", " ").title())
        else:
            out.append(trait.label_ru if lang.startswith("ru") else trait.label_en)
    return out


__all__ = ["PLATE_TRAITS", "TRAIT_CODES", "TraitDef", "get_trait", "trait_labels"]
