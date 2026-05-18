"""Input normalization for feed quantities, types, and poop consistency."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches

OZ_TO_ML = 29.5735

FEED_TYPE_CANONICAL: dict[str, str] = {
    "breast_milk": "breast_milk",
    "breastmilk": "breast_milk",
    "milk" : "breast_milk",
    "breast": "breast_milk",
    "bm": "breast_milk",
    "formula": "formula",
    "form": "formula",
    "solid": "solids",
    "solids": "solids",
    "food": "solids",
    "water": "water",
    "h2o": "water",
}

CONSISTENCY_VOCAB = ("watery", "soft", "formed", "hard")


class NormalizationError(ValueError):
    """Raised when input cannot be safely normalized."""


@dataclass(slots=True, frozen=True)
class FeedQuantity:
    quantity: float
    unit: str  # "ml" or "g"


def normalize_feed_type(raw: str) -> str:
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if key not in FEED_TYPE_CANONICAL:
        raise NormalizationError(f"Unknown feed_type: {raw!r}")
    return FEED_TYPE_CANONICAL[key]


def normalize_feed_quantity(quantity: float, unit: str) -> FeedQuantity:
    """Convert oz → ml; pass-through ml and g."""
    if quantity <= 0:
        raise NormalizationError("quantity must be > 0")
    u = unit.strip().lower()
    if u in {"oz", "ounce", "ounces", "fl oz", "fl_oz"}:
        return FeedQuantity(quantity=round(quantity * OZ_TO_ML, 2), unit="ml")
    if u in {"ml", "milliliter", "milliliters"}:
        return FeedQuantity(quantity=round(quantity, 2), unit="ml")
    if u in {"g", "gram", "grams"}:
        return FeedQuantity(quantity=round(quantity, 2), unit="g")
    raise NormalizationError(f"Unknown unit: {unit!r}")


@dataclass(slots=True, frozen=True)
class ConsistencyResolution:
    value: str
    needs_confirmation: bool
    suggestion: str | None = None


def normalize_consistency(raw: str) -> ConsistencyResolution:
    key = raw.strip().lower()
    if key in CONSISTENCY_VOCAB:
        return ConsistencyResolution(value=key, needs_confirmation=False)
    match = get_close_matches(key, CONSISTENCY_VOCAB, n=1, cutoff=0.6)
    if match:
        return ConsistencyResolution(
            value=match[0], needs_confirmation=True, suggestion=match[0]
        )
    raise NormalizationError(f"Unrecognized consistency: {raw!r}")
