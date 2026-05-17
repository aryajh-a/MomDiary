"""Unit tests for the normalization service (T071)."""

from __future__ import annotations

import pytest

from momdiary.services.normalization import (
    NormalizationError,
    normalize_consistency,
    normalize_feed_quantity,
    normalize_feed_type,
)


def test_oz_to_ml_round_trip() -> None:
    q = normalize_feed_quantity(4, "oz")
    assert q.unit == "ml"
    assert 118.0 < q.quantity < 119.0


def test_ml_passthrough() -> None:
    q = normalize_feed_quantity(120, "ml")
    assert q == type(q)(quantity=120.0, unit="ml")


def test_grams_passthrough() -> None:
    q = normalize_feed_quantity(30, "g")
    assert q.unit == "g"


def test_invalid_unit() -> None:
    with pytest.raises(NormalizationError):
        normalize_feed_quantity(1, "tbsp")


def test_non_positive_quantity() -> None:
    with pytest.raises(NormalizationError):
        normalize_feed_quantity(0, "ml")


def test_feed_type_alias_mapping() -> None:
    assert normalize_feed_type("breast milk") == "breast_milk"
    assert normalize_feed_type("BM") == "breast_milk"
    assert normalize_feed_type("Formula") == "formula"


def test_unknown_feed_type() -> None:
    with pytest.raises(NormalizationError):
        normalize_feed_type("juice")


def test_consistency_exact_match() -> None:
    r = normalize_consistency("soft")
    assert r.value == "soft"
    assert r.needs_confirmation is False


def test_consistency_closest_match_flags_confirmation() -> None:
    r = normalize_consistency("formd")
    assert r.value == "formed"
    assert r.needs_confirmation is True
    assert r.suggestion == "formed"


def test_consistency_no_match() -> None:
    with pytest.raises(NormalizationError):
        normalize_consistency("zzzz")
