"""Rule A alert counts for every unit interpretation of the CNB profile columns (feeds docs/DECISIONS.md D-008)."""
from __future__ import annotations

from itertools import product

import polars as pl

from node.rules.rule_a import rule_a

UNITS = ["monthly", "quarterly", "yearly"]


def rule_a_counts(tx: pl.DataFrame, cl: pl.DataFrame, cfg: dict) -> dict[str, int]:
    out = {}
    for eu, qu in product(UNITS, UNITS):
        out[f"expected={eu},q2={qu}"] = rule_a(tx, cl, {**cfg["rule_a"], "expected_unit": eu, "q2_unit": qu}).height
    return out
