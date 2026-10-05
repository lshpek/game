"""Server-side RNG.

All randomness that affects the player's rewards lives here and is executed on
the server. ``SystemRandom`` is used in production; tests inject a seeded
``random.Random`` for reproducibility.
"""

from __future__ import annotations

import random
import secrets
from collections.abc import Mapping
from typing import Protocol

from app.core.errors import ValidationError
from app.game.constants import NUMBER_FORMAT, NUMBER_MAX, NUMBER_MIN
from app.game.rarity import Rarity, load_rarity_weights


class Rng(Protocol):
    """Minimal random interface so tests can inject deterministic sources."""

    def random(self) -> float: ...
    def randint(self, a: int, b: int) -> int: ...
    def choice(self, seq): ...


def default_rng() -> Rng:
    """Cryptographically seeded generator for production rolls."""
    return secrets.SystemRandom()


def random_number(rng: Rng) -> str:
    """Uniformly pick a number in the 0000-9999 range, zero padded."""
    return f"{rng.randint(NUMBER_MIN, NUMBER_MAX):{NUMBER_FORMAT}}"


def normalize_weights(weights: Mapping[str, float]) -> dict[str, float]:
    """Return weights normalised into probabilities.

    Normalisation is *only* a defensive division: the tables that matter (the
    chance table, country weights, template weights) are already relative
    weights, and the chance table sums to exactly 100, so ``weight / total``
    reproduces the declared percent to within one ulp - including the
    ``0.0001`` probability of Secret, which survives as a distinct band rather
    than collapsing into zero.
    """
    total = sum(weights.values())
    if total <= 0:
        raise ValidationError("Rarity weights must sum to a positive value.", code="BAD_RARITY_CONFIG")
    return {code: weight / total for code, weight in weights.items()}


def weighted_choice(weights: Mapping[str, float], rng: Rng) -> str:
    """Pick a key from a weight mapping using a single uniform sample.

    One sample, one walk of the cumulative bands in declaration order: the
    boundaries are ``0 -> 0.54 -> 0.84 -> 0.97 -> 0.995 -> 0.999 -> 0.9999 -> 1``
    for the game's chance table, so Secret's band is the final ``0.0001``
    interval and is reachable but never generous. The tail returns the last key
    rather than raising, because ``rng.random()`` can return ``1.0 - 2**-53``.
    """
    probabilities = normalize_weights(weights)
    threshold = rng.random()
    cumulative = 0.0
    last_key = next(iter(probabilities))
    for key, probability in probabilities.items():
        cumulative += probability
        last_key = key
        if threshold < cumulative:
            return key
    # Floating point tail - return the last key deterministically.
    return last_key


def roll_rarity(weights: Mapping[str, float] | None = None, rng: Rng | None = None) -> Rarity:
    """Roll the "luck" rarity for a single roll."""
    generator = rng or default_rng()
    table = weights if weights is not None else load_rarity_weights()
    return Rarity(weighted_choice(table, generator))


def sample_distribution(
    weights: Mapping[str, float],
    samples: int,
    *,
    seed: int | None = None,
) -> dict[str, float]:
    """Test/telemetry utility: empirical distribution of the rarity roll.

    Never used by the production roll path.
    """
    if samples <= 0:
        raise ValidationError("Sample count must be positive.", code="BAD_SAMPLE_COUNT")
    rng = random.Random(seed)
    counters: dict[str, int] = dict.fromkeys(weights, 0)
    for _ in range(samples):
        counters[weighted_choice(weights, rng)] += 1
    return {code: count / samples for code, count in counters.items()}
