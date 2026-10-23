"""Turn a discharge series into a warning level.

The level is a claim about the *forecast*, not about water already in the
street: GloFAS is a ~5 km model, so "warning" means this river is expected to
reach a flow that happens about once in five years at that cell. Levels use the
highest day in the window because a flood peak is what matters, and a mean
would smooth a two-day crest below its threshold.
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
    """Current level, forecast peak and when it lands.

    Days before `today` are observations (reanalysis), the rest forecast; only
    today onward can raise a warning, since a flood that already crested is
    history, not news.
    """
    ahead = [(t, q) for t, q in zip(times, flows) if t >= today and q is not None]
    now = next((q for t, q in ahead if t == today), None)
    if not ahead:
        return {"level": "normal", "now": now, "peak": None, "peak_day": None}
    peak_day, peak = max(ahead, key=lambda x: x[1])
    return {"level": classify(peak, th), "now": now,
            "peak": round(peak, 2), "peak_day": peak_day}
