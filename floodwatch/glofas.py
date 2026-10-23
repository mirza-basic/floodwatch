"""GloFAS river discharge through Open-Meteo's keyless flood API.

Two shapes of call: a short window (recent + forecast) for the poll cycle, and
the full 1984-onward archive for deriving thresholds. The API answers a list
when given several locations and a bare object when given one - normalised
here so callers never branch on it.
"""
from __future__ import annotations

import time

import requests

from . import config

DAILY = "river_discharge"


def _get(params: dict) -> list[dict]:
    last = None
    for attempt in range(4):
        r = requests.get(config.FLOOD_API, params=params, timeout=config.HTTP_TIMEOUT)
        if r.status_code == 200:
            j = r.json()
            return j if isinstance(j, list) else [j]
        last = f"HTTP {r.status_code}: {r.text[:200]}"
        if r.status_code == 429:
            # "Hourly API request limit exceeded" - retrying inside the hour
            # only burns more of the next one, so fail and let the caller resume.
            raise RuntimeError(f"flood api rate limit: {r.text[:160]}")
        if r.status_code == 400:
            break
        time.sleep(2 ** attempt)
    raise RuntimeError(f"flood api: {last}")


def fetch(cells: list[tuple[float, float]], batch: int = config.BATCH, **window) -> list[dict]:
    """Daily discharge for each cell: {time:[...], river_discharge:[...]}.

    `window` is either past_days/forecast_days or start_date/end_date.
    Results come back in request order. The API caps locations x days per call,
    so the 42-year archive needs a much smaller `batch` than a 93-day window.
    """
    out: list[dict] = []
    for i in range(0, len(cells), batch):
        part = cells[i:i + batch]
        res = _get({"latitude": ",".join(str(c[0]) for c in part),
                    "longitude": ",".join(str(c[1]) for c in part),
                    "daily": DAILY, **window})
        if len(res) != len(part):
            raise RuntimeError(f"flood api returned {len(res)} for {len(part)} cells")
        out += [r["daily"] for r in res]
    return out
