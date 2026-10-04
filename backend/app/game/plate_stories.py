"""Plate stories - deterministic, no AI call during a roll.

A story is composed from at most three sentences: the plate's strongest pattern,
its country and (when relevant) the first-discovery note. Nothing here claims
anything about a real vehicle, a real owner, or any official plate value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.game.plate_rarity import RARITY_LABEL, Rarity

if TYPE_CHECKING:  # pragma: no cover
    from app.game.plate_generator import GeneratedPlate

PATTERN_STORIES: dict[str, tuple[str, str]] = {
    "all_same": ("Every digit repeats - the purest form of plate repetition.", "Все цифры повторяются — чистейшая форма повтора."),
    "four_of_kind": ("A four-of-a-kind: the rarest shape a serial can take.", "Четвёрка одинаковых — самая редкая форма серийного номера."),
    "triple": ("Three identical digits dominate this plate.", "Три одинаковые цифры задают характер этого номера."),
    "triple_letter": ("Triple letter: the letters repeat just as hard as the digits.", "Тройная буква — буквы повторяются так же сильно, как цифры."),
    "palindrome": ("Reads the same in both directions.", "Читается одинаково в обе стороны."),
    "symmetric_plate": ("The whole plate is symmetric from end to end.", "Весь номер симметричен от края до края."),
    "ascending": ("A perfect ascending run - every digit steps up.", "Идеальный ряд по возрастанию — каждая цифра на ступень выше."),
    "descending": ("A perfect descending run - every digit steps down.", "Идеальный ряд по убыванию — каждая цифра на ступень ниже."),
    "sequence": ("A long run of consecutive digits holds the middle together.", "Длинная последовательность подряд идущих цифр держит середину."),
    "repeated_pattern": ("Two identical halves stitched together.", "Две одинаковые половины соединены вместе."),
    "contains_777": ("Triple seven gives this plate a strong lucky-pattern score.", "Тройная семёрка даёт номеру высокий балл счастливой комбинации."),
    "contains_666": ("Triple six hides in the digits.", "Тройная шестёрка скрыта в цифрах."),
    "contains_123": ("The classic 1-2-3 run appears in the digits.", "Классическая последовательность 1-2-3 появляется в цифрах."),
    "contains_007": ("Double-oh-seven - a licence-to-collect reference.", "Два нуля и семёрка — отсылка к «лицензии собирать»."),
    "contains_000": ("A triple zero sits inside the serial.", "Тройной ноль спрятан внутри номера."),
    "lucky_pattern": ("The digits are composed of folklore's favourite numbers.", "Цифры составлены из любимых чисел фольклора."),
    "meme_pattern": ("An internet-culture pattern that refuses to be forgotten.", "Интернет-мем, который не собирается забываться."),
    "special_run": ("Contains a special combination collectors chase.", "Содержит особую комбинацию, за которой охотятся коллекционеры."),
    "special_code": ("The serial itself is a special, deliberately-shaped plate.", "Сам серийный номер — особый, намеренно собранный номер."),
    "region_match": ("The serial repeats the region code - a rare local coincidence.", "Серийный номер повторяет код региона — редкое местное совпадение."),
    "number_mirrors_region": ("The digits mirror the region code exactly.", "Цифры точно зеркалят код региона."),
    "mirrored_letters": ("The letters read as a mirror image.", "Буквы читаются как зеркальное отражение."),
    "letter_palindrome": ("The letters form a palindrome.", "Буквы образуют палиндром."),
    "alphabetical_run": ("The letters form a strict alphabetical run.", "Буквы образуют строгий алфавитный ряд."),
    "repeated_letter_prefix": ("The same letter opens every group.", "Одна и та же буква открывает каждую группу."),
    "repeated_letter_suffix": ("The plate ends on a repeated letter.", "Номер заканчивается повторяющейся буквой."),
    "rare_template": ("An uncommon plate format for this country.", "Необычный формат номера для этой страны."),
}

COUNTRY_STORIES: dict[str, tuple[str, str]] = {
    "RUS": ("A Russian-style plate from the NUMORA World collection.", "Российский номер из коллекции Мира NUMORA."),
    "USA": ("A US-style plate from the NUMORA World collection.", "Американский номер из коллекции Мира NUMORA."),
    "KAZ": ("A Kazakhstan-style plate from the NUMORA World collection.", "Казахский номер из коллекции Мира NUMORA."),
    "DEU": ("A German-style plate from the NUMORA World collection.", "Немецкий номер из коллекции Мира NUMORA."),
    "GBR": ("A British-style plate from the NUMORA World collection.", "Британский номер из коллекции Мира NUMORA."),
    "FRA": ("A French-style plate from the NUMORA World collection.", "Французский номер из коллекции Мира NUMORA."),
    "ITA": ("An Italian-style plate from the NUMORA World collection.", "Итальянский номер из коллекции Мира NUMORA."),
    "CAN": ("A Canadian plate from the NUMORA World collection.", "Канадский номер из коллекции Мира NUMORA."),
    "JPN": ("A Japanese-style collectible from the NUMORA World collection.", "Японский коллекционный номер из коллекции Мира NUMORA."),
    "ARE": ("A Gulf-style plate from the NUMORA World collection.", "Номер в стиле залива из коллекции Мира NUMORA."),
    "ARM": ("An Armenian plate from the NUMORA World collection.", "Армянский номер из коллекции Мира NUMORA."),
    "GEO": ("A Georgian plate from the NUMORA World collection.", "Грузинский номер из коллекции Мира NUMORA."),
}

FIRST_DISCOVERY = (
    "This was the first recorded discovery of this plate in NUMORA.",
    "Это первое зафиксированное открытие этого номера в NUMORA.",
)

SECRET_STORY = (
    "A Secret plate - the combination was engineered by the pattern engine.",
    "Секретный номер — комбинация собрана движком паттернов.",
)

GENERIC_STORY = (
    "An unremarkable plate - and that is exactly what makes it common.",
    "Обычный номер — и именно это делает его распространённым.",
)


def _best_patterns(traits: list[str]) -> list[str]:
    """Pattern codes with a story, in the plate's own (score-ordered) order."""
    return [code for code in traits if code in PATTERN_STORIES]


def build_plate_story(
    *,
    traits: list[str],
    country_code: str,
    rarity: str | Rarity = Rarity.COMMON,
    is_secret: bool = False,
    is_first_discovery: bool = False,
    lang: str = "en",
) -> str:
    """Compose a short, deterministic story in RU or EN."""
    index = 1 if lang.lower().startswith("ru") else 0
    sentences: list[str] = []

    if is_secret:
        sentences.append(SECRET_STORY[index])
    else:
        for code in _best_patterns(traits)[:2]:
            sentences.append(PATTERN_STORIES[code][index])

    country_story = COUNTRY_STORIES.get(country_code)
    if country_story is not None and len(sentences) < 2:
        sentences.append(country_story[index])

    if is_first_discovery:
        sentences.append(FIRST_DISCOVERY[index])

    if not sentences:
        sentences.append(GENERIC_STORY[index])

    return " ".join(sentences[:3])


def rarity_label(rarity: str | Rarity) -> str:
    """English rarity label (the UI localises it from the stable code)."""
    code = rarity.value if isinstance(rarity, Rarity) else str(rarity).upper()
    return RARITY_LABEL.get(code, code)


def story_for_generated(
    generated: "GeneratedPlate",
    *,
    is_first_discovery: bool = False,
    lang: str = "en",
) -> str:
    """Convenience helper taking a :class:`GeneratedPlate` directly."""
    return build_plate_story(
        traits=list(generated.analysis.traits),
        country_code=generated.country.code,
        rarity=generated.rarity,
        is_secret=generated.is_secret,
        is_first_discovery=is_first_discovery,
        lang=lang,
    )


__all__ = [
    "COUNTRY_STORIES",
    "PATTERN_STORIES",
    "build_plate_story",
    "rarity_label",
    "story_for_generated",
]
