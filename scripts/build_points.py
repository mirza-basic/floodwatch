"""Choose the river points of each municipality (up to MAX_RIVERS) and derive their flood thresholds.

The strongest GloFAS cells inside each municipality (and a few just outside it) are named by their
nearest river, the best cell per river is kept, and the discharge history gives each cell its
thresholds. A municipality without a cell above MIN_RIVER_M3S gets `river: false`. Results go to
data/bih/river_points.json and river_fill.json. Fetched data is cached in state/build-cache.json,
so the script can be run again after a rate-limit error.

    python3 scripts/build_points.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from floodwatch import config, geo, glofas, rivers, thresholds  # noqa: E402

CANDIDATES = 12  # strongest cells inside a municipality that are considered
NEAR_CANDIDATES = 6  # strongest cells just outside a municipality that are considered


CACHE = config.STATE_DIR / "build-cache.json"


def cached(key: str, cells, fetch):
    """Return the fetched series for `cells`, fetching and caching those not yet cached."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    for i in range(0, len(cells), 15):
        part = [c for c in cells[i:i + 15] if f"{key}:{c}" not in cache]
        if part:
            for c, d in zip(part, fetch(part)):
                cache[f"{key}:{c}"] = d
            time.sleep(4)  # Pause between batches.
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

    # Per municipality: take its strongest cells, name each by its nearest river line, keep the
    # best cell per river name, and keep at most MAX_RIVERS rivers.
    chosen: dict[str, list[tuple[tuple[float, float], str | None]]] = {}
    for m in munis:
        inside = set(cells_of[m.id])
        w, s_, e, n = m.bbox
        pad = config.NEAR_KM / 111.0 * 1.3
        near = [c for c in unique if c not in inside and s_ - pad <= c[0] <= n + pad and w - pad <= c[1] <= e + pad
                and geo.distance_to_boundary_km(m, *c) <= config.NEAR_KM]
        strong = lambda cs: sorted((c for c in cs if mean[c] >= config.MIN_RIVER_M3S), key=lambda c: -mean[c])
        # Cells inside and cells just outside the municipality are ranked separately.
        cand = sorted(strong(inside)[:CANDIDATES] + strong(near)[:NEAR_CANDIDATES], key=lambda c: -mean[c])
        per: dict[str | None, tuple[float, float]] = {}
        for c in cand:
            name = rivers.nearest_name(*c)
            if c not in inside:
                # A cell outside the municipality counts only for a named river that has a stretch inside it.
                if not name or not (rivers.snap(m, c[0], c[1], name) or {}).get("lines"):
                    continue
            per.setdefault(name, c)  # cells are sorted by flow, so the first cell per river is its strongest
        named = [(c, n) for n, c in per.items() if n]
        chosen[m.id] = (named or [(c, n) for n, c in per.items()])[:config.MAX_RIVERS]

    cells = sorted({c for v in chosen.values() for c, _ in v})
    print(f"{len(cells)} river cells chosen; fetching archive", flush=True)

    end = f"{date.today().year - 1}-12-31"
    th = {}
    for c, d in zip(cells, cached('archive', cells, lambda p: glofas.fetch(
            p, batch=3, start_date=config.HISTORY_START, end_date=end))):
        th[c] = thresholds.gumbel(thresholds.annual_maxima(d))

    out = []
    for m in munis:
        picks = [(c, n) for c, n in chosen[m.id] if th.get(c)]
        if not picks:
            c = max(cells_of[m.id], key=lambda c: mean[c])
            out.append({"id": m.id, "river": False, "lat": c[0], "lon": c[1],
                        "mean_m3s": round(mean[c], 2), "thresholds": None})
            continue
        for c, n in picks:
            rec = {"id": m.id, "river": True, "lat": c[0], "lon": c[1],
                   "inside": m.contains(*c), "near": not m.contains(*c), "mean_m3s": round(mean[c], 2),
                   "thresholds": th[c], "river_name": n}
            s = rivers.snap(m, c[0], c[1], n) if n else None
            if s:
                rec.update(mlat=s["point"][0], mlon=s["point"][1], lines=s["lines"])
            out.append(rec)
    # Lay out every shown river along its whole course and write the fill stretches.
    fill = rivers.layout(out, munis)
    (config.DATA_DIR / "river_fill.json").write_text(json.dumps(fill, ensure_ascii=False, separators=(",", ":")))
    config.POINTS_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    n = len({p["id"] for p in out if p["river"]})
    print(f"wrote {config.POINTS_FILE.name}: {len(out)} points; {n} municipalities with a river, "
          f"{len(munis) - n} without")


if __name__ == "__main__":
    main()
