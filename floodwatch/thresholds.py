"""Return-period thresholds from the GloFAS archive.

Open-Meteo serves discharge, not warning levels, so levels are derived here:
fit a Gumbel (EV1) distribution to each year's maximum daily discharge by the
method of moments and read off the 2-, 5- and 20-year flows. That is the same
family GloFAS's own return-period products use. It is deliberately simple; a
42-year sample makes the 20-year figure an extrapolation, so treat levels as
relative severity, not as the figure an authority would publish.
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
