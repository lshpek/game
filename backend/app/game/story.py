"""Deterministic story engine.

Stories are derived from the number's traits and a small lookup table for
notable combinations. No AI/network call happens during a roll, so latency and
cost stay at zero and the same number always gets the same story.
"""

from __future__ import annotations

from app.game.analyzer import NumberAnalysis

SPECIAL_STORIES: dict[str, str] = {
    "1234": "Perfect sequence: 1 -> 2 -> 3 -> 4.",
    "4321": "The perfect sequence in reverse - countdown to zero.",
    "7777": "Four sevens. One of the most recognizable repeated-digit combinations.",
    "6666": "Four sixes - the number folklore refuses to forget.",
    "0000": "Absolute zero, four times over. The blank slate of the number world.",
    "9999": "The highest possible combination - the end of the road.",
    "1111": "Four ones. Every digit starts somewhere.",
    "1337": "1337 is a classic leetspeak reference from internet culture.",
    "0007": "Double-oh-seven. A licence to collect - 007 reference.",
    "0777": "007's luckier cousin, leading with a zero.",
    "8008": "An upside-down calculator classic from the schoolyard era.",
    "4200": "A calendar year wrapped around a very specific inside joke.",
    "6969": "The internet's most predictable punchline, built into four digits.",
    "1000": "Exactly one thousand. Round, clean and satisfying.",
    "2048": "Powers of two all the way down - a puzzle in four digits.",
    "2024": "A recent year that many collectors remember first-hand.",
    "5000": "Halfway to the maximum, mid-millennium and proud of it.",
}

TRAIT_STORIES: dict[str, str] = {
    "all_same": "Every digit is the same - pure repetition.",
    "four_of_kind": "A four-of-a-kind: the rarest shape a four-digit number can take.",
    "triple": "Three identical digits dominate this number.",
    "two_pairs": "Two neat pairs, balanced on either side.",
    "pair": "A single repeated pair gives this number its rhythm.",
    "ascending": "The digits climb steadily from left to right.",
    "descending": "The digits march downwards in perfect order.",
    "palindrome": "This number reads the same in both directions.",
    "repeated_pattern": "Two identical halves stitched together.",
    "contains_777": "The triple-seven sequence hides inside it.",
    "contains_666": "The triple-six sequence hides inside it.",
    "contains_123": "The classic 1-2-3 run appears in the digits.",
    "contains_000": "A triple zero sits inside the number.",
    "round_number": "Ends in zeros - a tidy, rounded figure.",
    "year_like": "Could pass for a calendar year.",
    "lucky_pattern": "Digits that gamblers and folklore call lucky.",
    "meme_pattern": "A pattern internet culture refuses to let go.",
    "low_number": "A low number: the first hundred are the hardest to find.",
    "sequence": "A long run of consecutive digits holds the middle together.",
}

MAX_TRAIT_SENTENCES = 2


def build_story(analysis: NumberAnalysis) -> str:
    """Compose a short, deterministic story for an analysed number."""
    if analysis.number in SPECIAL_STORIES:
        return SPECIAL_STORIES[analysis.number]

    sentences = [TRAIT_STORIES[code] for code in analysis.traits if code in TRAIT_STORIES]
    if not sentences:
        return "An unremarkable four-digit number - and that is exactly what makes it common."

    # Prefer the most distinctive traits (declared first in the registry).
    ordered = sorted(
        sentences,
        key=lambda sentence: -len(sentence),
    )
    return " ".join(ordered[:MAX_TRAIT_SENTENCES])


def story_for_traits(traits: list[str]) -> str:
    """Fallback helper for callers that only have trait codes."""
    sentences = [TRAIT_STORIES[code] for code in traits if code in TRAIT_STORIES]
    if not sentences:
        return "An ordinary four-digit number."
    return " ".join(sentences[:MAX_TRAIT_SENTENCES])


__all__ = ["SPECIAL_STORIES", "TRAIT_STORIES", "build_story", "story_for_traits"]
