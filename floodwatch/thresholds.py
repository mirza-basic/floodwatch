"""Return-period thresholds from the GloFAS archive.

A Gumbel (extreme-value) distribution is fitted by the method of moments to each year's maximum
daily discharge. The flows expected once in 2, 5 and 20 years are the watch, warning and severe
thresholds.
"""
from __future__ import annotations

import math
from collections import defaultdict

EULER = 0.5772156649
LEVELS = {"watch": 2, "warning": 5, "severe": 20}  # return period in years


def annual_maxima(daily: dict) -> list[float]:
    by_year: dict[str, float] = defaultdict(float)
    for t, q in zip(daily["time"], daily["river_discharge"]):
        if q is not None:
            by_year[t[:4]] = max(by_year[t[:4]], q)
    return list(by_year.values())


def gumbel(maxima: list[float]) -> dict[str, float] | None:
    n = len(maxima)
    if n < 20:
        return None
    mean = sum(maxima) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in maxima) / (n - 1))
    if sd == 0:
        return None
    beta = sd * math.sqrt(6) / math.pi
    mu = mean - EULER * beta
    return {k: round(mu - beta * math.log(-math.log(1 - 1 / T)), 2)
            for k, T in LEVELS.items()}
