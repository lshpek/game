"""Server-side RNG: distribution and safety guarantees."""

from __future__ import annotations

from typing import ClassVar

import pytest

from app.game.constants import NUMBER_MAX, NUMBER_MIN
from app.game.rng import (
    default_rng,
    normalize_weights,
    random_number,
    roll_rarity,
    sample_distribution,
    weighted_choice,
)


class TestRandomNumber:
    def test_always_returns_four_padded_digits(self):
        rng = default_rng()
        for _ in range(500):
            value = random_number(rng)
            assert len(value) == 4
            assert value.isdigit()

    def test_stays_inside_the_range(self):
        rng = default_rng()
        values = {int(random_number(rng)) for _ in range(2000)}
        assert min(values) >= NUMBER_MIN
        assert max(values) <= NUMBER_MAX

    def test_distribution_is_roughly_uniform(self):
        # Bucket the 10 000 numbers into 10 deciles and check they are close.
        rng = default_rng()
        buckets = [0] * 10
        samples = 20_000
        for _ in range(samples):
            buckets[min(int(random_number(rng)) // 1000, 9)] += 1

        expected = samples / 10
        for count in buckets:
            assert abs(count - expected) / expected < 0.15

    def test_client_cannot_influence_the_outcome(self):
        """The RNG takes no external input at all - it is server side only."""
        import inspect

        signature = inspect.signature(random_number)
        assert list(signature.parameters) == ["rng"]


class TestRarityDistribution:
    """Approximate distribution must match the configured weights."""

    DEFAULT_WEIGHTS: ClassVar[dict[str, float]] = {
        "COMMON": 70.0,
        "UNCOMMON": 20.0,
        "RARE": 7.0,
        "EPIC": 2.0,
        "LEGENDARY": 0.8,
        "MYTHIC": 0.19,
        "SECRET": 0.01,
    }

    def test_distribution_matches_configuration(self):
        samples = 200_000
        observed = sample_distribution(self.DEFAULT_WEIGHTS, samples, seed=1337)

        for code, expected_pct in self.DEFAULT_WEIGHTS.items():
            expected_probability = expected_pct / 100
            observed_probability = observed[code]
            # Relative tolerance is generous for the very rare buckets.
            tolerance = 0.03 if expected_probability > 0.01 else 0.0006
            assert abs(observed_probability - expected_probability) < tolerance, code

    def test_distribution_sums_to_one(self):
        observed = sample_distribution(self.DEFAULT_WEIGHTS, 5_000, seed=7)
        assert sum(observed.values()) == pytest.approx(1.0)

    def test_seeded_sampling_is_reproducible(self):
        first = sample_distribution(self.DEFAULT_WEIGHTS, 1_000, seed=42)
        second = sample_distribution(self.DEFAULT_WEIGHTS, 1_000, seed=42)
        assert first == second

    def test_single_outcome_weights(self):
        chosen = weighted_choice({"A": 1.0}, default_rng())
        assert chosen == "A"

    def test_zero_weight_is_never_selected(self):
        observed = sample_distribution({"A": 1.0, "B": 0.0}, 2_000, seed=3)
        assert observed["B"] == 0.0
        assert observed["A"] == pytest.approx(1.0)

    def test_roll_rarity_uses_the_given_table(self):
        assert roll_rarity({"MYTHIC": 100.0}, default_rng()) is not None
        for _ in range(50):
            assert roll_rarity({"MYTHIC": 100.0}, default_rng()).value == "MYTHIC"


class TestWeightNormalisation:
    def test_normalisation_produces_probabilities(self):
        normalized = normalize_weights({"A": 3.0, "B": 1.0})
        assert normalized == {"A": 0.75, "B": 0.25}

    def test_zero_total_is_rejected(self):
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            normalize_weights({"A": 0.0})

    def test_empty_sample_size_is_rejected(self):
        from app.core.errors import ValidationError

        with pytest.raises(ValidationError):
            sample_distribution({"A": 1.0}, 0)
