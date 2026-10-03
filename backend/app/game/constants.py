"""Numeric game constants. No magic numbers elsewhere in the codebase."""

from __future__ import annotations

NUMBER_MIN = 0
NUMBER_MAX = 9999
NUMBER_DIGITS = 4
NUMBER_FORMAT = "04d"

# Longest run of consecutive digits that upgrades a number's flavour.
MIN_SEQUENCE_LENGTH_FOR_TRAIT = 3
