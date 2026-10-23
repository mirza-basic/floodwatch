"""Pick one river point per municipality and derive its flood thresholds.

Build-time artifact, like fire-detection's boundaries: run once, commit the
result, never call at runtime. For each municipality every GloFAS cell whose
centre lies inside is sampled over the last 30 days and the cell with the
highest mean discharge is taken to be its main river. A municipality too small
to contain a cell centre falls back to the cell nearest its centroid; one whose
best cell is below MIN_RIVER_M3S gets `river: false` and no thresholds, rather
than a made-up point on a hillside.

    python3 scripts/build_points.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from floodwatch import config, geo, glofas, thresholds  # noqa: E402


CACHE = config.STATE_DIR / "build-cache.json"


def cached(key: str, cells, fetch):
    """Resume across runs: Open-Meteo's hourly quota is shared by every call
    this script makes, so a run that dies on 429 must not redo what it paid for."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    for i in range(0, len(cells), 15):
        part = [c for c in cells[i:i + 15] if f"{key}:{c}" not in cache]
        if part:
            for c, d in zip(part, fetch(part)):
                cache[f"{key}:{c}"] = d
            tmp = CACHE.with_suffix(".tmp")
            tmp.write_text(json.dumps(cache))
            os.replace(tmp, CACHE)
    return [cache[f"{key}:{c}"] for c in cells]


def main() -> None:
    munis = geo.municipalities()
    cells_of = {m.id: geo.cell_centres(m) or [geo.snap(*m.centroid)] for m in munis}
    unique = sorted({c for cs in cells_of.values() for c in cs})
    print(f"{len(munis)} municipalities, {len(unique)} unique cells", flush=True)

    recent = dict(zip(unique, cached('recent', unique,
                                     lambda p: glofas.fetch(p, past_days=30, forecast_days=1))))
    mean = {c: (sum(q for q in d["river_discharge"] if q is not None)
                / max(1, sum(q is not None for q in d["river_discharge"])))
            for c, d in recent.items()}

    best = {m.id: max(cells_of[m.id], key=lambda c: mean[c]) for m in munis}
    rivers = sorted({c for c in best.values() if mean[c] >= config.MIN_RIVER_M3S})
    print(f"{len(rivers)} river cells chosen; fetching archive", flush=True)

    end = f"{date.today().year - 1}-12-31"
    th = {}
    for c, d in zip(rivers, cached('archive', rivers, lambda p: glofas.fetch(
            p, batch=3, start_date=config.HISTORY_START, end_date=end))):
        th[c] = thresholds.gumbel(thresholds.annual_maxima(d))

    out = []
    for m in munis:
        c = best[m.id]
        ok = mean[c] >= config.MIN_RIVER_M3S and th.get(c)
        out.append({"id": m.id, "river": bool(ok), "lat": c[0], "lon": c[1],
                    "inside": m.contains(*c), "mean_m3s": round(mean[c], 2),
                    "thresholds": th.get(c) if ok else None})
    config.POINTS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    n = sum(p["river"] for p in out)
    print(f"wrote {config.POINTS_FILE.name}: {n} with a river, {len(out) - n} without")


if __name__ == "__main__":
    main()
