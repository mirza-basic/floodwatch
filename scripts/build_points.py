"""Pick river points per municipality (up to MAX_RIVERS) and derive their flood thresholds.

Build-time artifact, like fire-detection's boundaries: run once, commit the
result, never call at runtime. For each municipality every GloFAS cell whose
centre lies inside is sampled over the last 30 days and the cell with the
highest mean discharge is taken to be a main river. A municipality too small
to contain a cell centre falls back to the cell nearest its centroid; one whose
best cell is below MIN_RIVER_M3S gets `river: false` and no thresholds, rather
than a made-up point on a hillside.

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

CANDIDATES = 12  # strongest inside cells per municipality considered for naming
NEAR_CANDIDATES = 6  # strongest nearby outside cells considered on top of those


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
            time.sleep(4)  # stay under the per-minute quota
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

    # Several rivers per municipality: Bosna and Krivaja flood together at
    # Zavidovici, and one point could only show one of them. Candidates are the
    # municipality's strongest cells; each is named by its nearest river line,
    # the best cell per river name is kept, and at most MAX_RIVERS survive.
    chosen: dict[str, list[tuple[tuple[float, float], str | None]]] = {}
    for m in munis:
        inside = set(cells_of[m.id])
        w, s_, e, n = m.bbox
        pad = config.NEAR_KM / 111.0 * 1.3
        near = [c for c in unique if c not in inside and s_ - pad <= c[0] <= n + pad and w - pad <= c[1] <= e + pad
                and geo.distance_to_boundary_km(m, *c) <= config.NEAR_KM]
        strong = lambda cs: sorted((c for c in cs if mean[c] >= config.MIN_RIVER_M3S), key=lambda c: -mean[c])
        # Separate pools: a big river along the border must not crowd out the
        # municipality's own tributaries (Bosna vs Krivaja at Zavidovici).
        cand = sorted(strong(inside)[:CANDIDATES] + strong(near)[:NEAR_CANDIDATES], key=lambda c: -mean[c])
        per: dict[str | None, tuple[float, float]] = {}
        for c in cand:
            name = rivers.nearest_name(*c)
            if c not in inside:
                # An outside cell counts only for a named river that actually runs
                # through this municipality - otherwise it is the neighbour's river.
                if not name or not (rivers.snap(m, c[0], c[1], name) or {}).get("lines"):
                    continue
            per.setdefault(name, c)  # sorted, so the first cell per river is its best
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
    # Complete every shown river along its whole course (see rivers.layout) - without
    # this, stretches inside municipalities that have no point for the river stay blank.
    fill = rivers.layout(out, munis)
    (config.DATA_DIR / "river_fill.json").write_text(json.dumps(fill, ensure_ascii=False, separators=(",", ":")))
    config.POINTS_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    n = len({p["id"] for p in out if p["river"]})
    print(f"wrote {config.POINTS_FILE.name}: {len(out)} points; {n} municipalities with a river, "
          f"{len(munis) - n} without")


if __name__ == "__main__":
    main()
