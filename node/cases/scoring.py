"""Transparent additive log-odds scoring for cases (no ML)."""
from __future__ import annotations

import math

from common.schemas import Signal


def score_case(signals: list[Signal], exculpatory: list[Signal], weights: dict) -> dict:
    """Sum weighted signal scores into a logit and squash to a probability.

    Unknown detector ids raise KeyError; every signal contributes, suspicious
    or exculpatory alike.
    """
    points = {s.signal_id: weights["points"][s.detector_id] * s.score for s in [*signals, *exculpatory]}
    logit = weights["bias"] + sum(points.values())
    return {"logit": logit, "prob": 1.0 / (1.0 + math.exp(-logit)), "points": points}
