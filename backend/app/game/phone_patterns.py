"""Structural traits for digit-heavy collectibles (phones, SIM serials).

Rarity must come from the *shape* of the number, never from a random dice throw.
These detectors read the digits of the generated collectible and report what is
actually there, so the same number always scores the same on every roll, on every
server, for every player.

Each detector is deliberately conservative: it must not claim a trait that is not
literally present in the string, because the trait chips are shown to the player
next to the number.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import pairwise

#: Digits that read as "lucky" in most markets. Used as an *extra* signal only:
#: a run of 7s is a trait, never a rarity decision by itself.
LUCKY_DIGITS = frozenset("777")


def digits_of(text: str) -> str:
    return "".join(char for char in text if char.isdigit())


def has_repeated_run(digits: str, length: int = 3) -> bool:
    """True when some digit repeats ``length`` times in a row (``777``, ``0000``)."""
    if len(digits) < length:
        return False
    run = 1
    for previous, current in pairwise(digits):
        run = run + 1 if previous == current else 1
        if run >= length:
            return True
    return False


def repeated_runs(digits: str, minimum: int = 3) -> list[str]:
    """Every maximal run of one repeated digit, as ``"7x3"`` markers."""
    runs: list[str] = []
    if not digits:
        return runs
    current = digits[0]
    count = 1
    for char in digits[1:]:
        if char == current:
            count += 1
            continue
        if count >= minimum:
            runs.append(f"{current}x{count}")
        current, count = char, 1
    if count >= minimum:
        runs.append(f"{current}x{count}")
    return runs


def triple_repetition(digits: str) -> bool:
    return has_repeated_run(digits, 3)


def quadruple_repetition(digits: str) -> bool:
    return has_repeated_run(digits, 4)


def palindrome(digits: str) -> bool:
    return len(digits) >= 4 and digits == digits[::-1]


def mirror_blocks(digits: str) -> bool:
    """A ``ABBA`` style mirror: the first half equals the reversed second half."""
    if len(digits) < 6 or len(digits) % 2:
        return False
    half = len(digits) // 2
    return digits[:half] == digits[half:][::-1]


def sequential_run(digits: str, length: int = 3) -> bool:
    """``123``, ``4321`` - a strictly ordered run in either direction."""
    if len(digits) < length:
        return False
    run = 1
    step = 0
    for previous, current in pairwise(digits):
        delta = int(current) - int(previous)
        if delta in (1, -1) and (step in (0, delta)):
            step = delta
            run += 1
            if run >= length:
                return True
        else:
            step = delta if delta in (1, -1) else 0
            run = 2 if step else 1
    return False


def ascending(digits: str) -> bool:
    return len(digits) >= 3 and all(
        int(b) > int(a) for a, b in pairwise(digits)
    )


def descending(digits: str) -> bool:
    return len(digits) >= 3 and all(
        int(b) < int(a) for a, b in pairwise(digits)
    )


def alternating(digits: str) -> bool:
    """``121212`` / ``454545``: a two-value alternation."""
    if len(digits) < 6:
        return False
    return len(set(digits)) == 2 and len(set(digits[::2])) == 1


def lucky_runs(digits: str) -> list[str]:
    """Lucky digit runs present, as short labels (``777``, ``0000``)."""
    return [
        run
        for run in repeated_runs(digits, minimum=3)
        if run[0] in {"7", "0", "1", "8", "9"}
    ]


def low_entropy(digits: str) -> bool:
    """The number draws from very few distinct digits - a collectible 'flat' feel."""
    if len(digits) < 6:
        return False
    return len(set(digits)) <= 3


def entropy_bits(digits: str) -> float:
    """Shannon entropy of the digit distribution, in bits.

    Reported alongside the value so a player can see *why* a number is special:
    ``000 111 000`` and ``407 512 993`` have very different structure.
    """
    if not digits:
        return 0.0
    counts = Counter(digits)
    total = len(digits)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def perfect_symmetry(digits: str) -> bool:
    """Everything at once: palindromic *and* mirrored *and* low entropy."""
    return palindrome(digits) and low_entropy(digits)


def detect_phone_traits(text: str) -> list[str]:
    """Trait codes for a phone number or SIM serial.

    Ordered strongest-first so the UI can show the most impressive chips first.
    """
    digits = digits_of(text)
    if len(digits) < 6:
        return []

    traits: list[str] = []

    def add(code: str) -> None:
        if code not in traits:
            traits.append(code)

    if perfect_symmetry(digits):
        add("perfect_symmetry")
    if quadruple_repetition(digits):
        add("quad_repeat")
    if triple_repetition(digits):
        add("triple_repeat")
    if runs := lucky_runs(digits):
        add("lucky_run")
        del runs
    if palindrome(digits):
        add("palindrome")
    if mirror_blocks(digits):
        add("mirrored")
    if sequential_run(digits, 4):
        add("sequence_4")
    elif sequential_run(digits, 3):
        add("sequence_3")
    if ascending(digits):
        add("ascending")
    if descending(digits):
        add("descending")
    if alternating(digits):
        add("alternating")
    if low_entropy(digits):
        add("low_entropy")
    return traits


#: How much each trait is worth when scoring a phone/SIM. Deterministic, so the
#: same structure always produces the same rarity band.
PHONE_TRAIT_WEIGHTS: dict[str, int] = {
    "perfect_symmetry": 46,
    "quad_repeat": 38,
    "triple_repeat": 26,
    "lucky_run": 22,
    "palindrome": 20,
    "mirrored": 14,
    "sequence_4": 18,
    "sequence_3": 10,
    "ascending": 8,
    "descending": 10,
    "alternating": 12,
    "low_entropy": 6,
}

#: The luckiest digit run, used for the "secret" band. A number has to earn it:
#: at least five identical lucky digits in a row.
ULTRA_PATTERN_RUN = "7"
ULTRA_PATTERN_MIN_RUN = 5


def has_ultra_pattern(digits: str, digit: str = ULTRA_PATTERN_RUN) -> bool:
    """True when a lucky digit repeats at least five times in a row.

    Comparing against a run *marker* string would only match one exact length
    (``7x9``), so the run length is checked instead.
    """
    if digit not in {"7", "8", "9", "0", "1"}:
        return False
    run = 0
    for char in digits:
        run = run + 1 if char == digit else 0
        if run >= ULTRA_PATTERN_MIN_RUN:
            return True
    return False


def score_phone_traits(traits: list[str]) -> int:
    """Sum of the trait weights, capped so no single number runs away."""
    return min(100, sum(PHONE_TRAIT_WEIGHTS.get(trait, 0) for trait in traits))


__all__ = [
    "LUCKY_DIGITS",
    "PHONE_TRAIT_WEIGHTS",
    "ULTRA_PATTERN_MIN_RUN",
    "ULTRA_PATTERN_RUN",
    "alternating",
    "ascending",
    "descending",
    "detect_phone_traits",
    "digits_of",
    "entropy_bits",
    "has_repeated_run",
    "has_ultra_pattern",
    "low_entropy",
    "lucky_runs",
    "mirror_blocks",
    "palindrome",
    "perfect_symmetry",
    "quadruple_repetition",
    "repeated_runs",
    "score_phone_traits",
    "sequential_run",
    "triple_repetition",
]
