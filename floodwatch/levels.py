"""Turn a discharge series into a warning level.

The level is the highest threshold reached by the highest forecast day in the window.
"""
from __future__ import annotations

ORDER = ("normal", "watch", "warning", "severe")


def classify(q: float | None, th: dict[str, float] | None) -> str:
    if q is None or not th:
        return "normal"
    level = "normal"
    for name in ORDER[1:]:
        if q >= th[name]:
            level = name
    return level


def assess(times: list[str], flows: list[float | None], th: dict[str, float] | None,
           today: str) -> dict:
    """Current level, forecast peak and the day it falls on.

    Only today and later days count; earlier days are observations.
    """
    ahead = [(t, q) for t, q in zip(times, flows) if t >= today and q is not None]
    now = next((q for t, q in ahead if t == today), None)
    if not ahead:
        return {"level": "normal", "now": now, "peak": None, "peak_day": None}
    peak_day, peak = max(ahead, key=lambda x: x[1])
    return {"level": classify(peak, th), "now": now,
            "peak": round(peak, 2), "peak_day": peak_day}
