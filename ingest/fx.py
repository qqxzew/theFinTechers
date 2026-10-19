"""FX rate loading and conversion helpers."""

from pathlib import Path
from typing import Any

import yaml


def load_fx(path: str | Path) -> dict[str, Any]:
    """Load an FX YAML file and return the parsed dict as is."""
    with open(path) as f:
        return yaml.safe_load(f)


def to_czk(amount: float, currency: str, fx: dict[str, Any]) -> float:
    """Convert amount in the given currency to CZK; KeyError if unknown."""
    return amount * fx["rates"][currency]
