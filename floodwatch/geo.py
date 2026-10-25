"""Boundary geometry for the 145 municipalities.

A boundary can consist of several rings (enclaves, exclaves). All rings of all parts are used,
and a point is inside when an odd number of rings enclose it (even-odd rule).
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

from . import config


def _rings(geom: dict) -> list[list[tuple[float, float]]]:
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return [[(x, y) for x, y in ring] for poly in polys for ring in poly]


def _inside(rings, lat: float, lon: float) -> bool:
    hit = False
    for ring in rings:
        j = len(ring) - 1
        for i, (xi, yi) in enumerate(ring):
            xj, yj = ring[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                hit = not hit
            j = i
    return hit


class Municipality:
    __slots__ = ("id", "short_name", "rings", "bbox", "centroid")

    def __init__(self, id_: str, short_name: str, rings):
        self.id, self.short_name, self.rings = id_, short_name, rings
        xs = [x for r in rings for x, _ in r]
        ys = [y for r in rings for _, y in r]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))
        self.centroid = (sum(ys) / len(ys), sum(xs) / len(xs))  # (lat, lon) vertex-mean

    def contains(self, lat: float, lon: float) -> bool:
        w, s, e, n = self.bbox
        return s <= lat <= n and w <= lon <= e and _inside(self.rings, lat, lon)


@lru_cache(maxsize=1)
def municipalities() -> tuple[Municipality, ...]:
    out = []
    for m in json.loads((config.DATA_DIR / "municipalities.json").read_text()):
        fc = json.loads((config.DATA_DIR / m["boundary"]).read_text())
        out.append(Municipality(m["id"], m["short_name"], _rings(fc["features"][0]["geometry"])))
    return tuple(out)


def cell_centres(m: Municipality) -> list[tuple[float, float]]:
    """GloFAS cell centres whose centre lies inside the municipality."""
    g = config.GRID_DEG
    w, s, e, n = m.bbox
    k0, k1 = int((s - 0.025) // g), int((n - 0.025) // g) + 1
    j0, j1 = int((w - 0.025) // g), int((e - 0.025) // g) + 1
    cells = []
    for k in range(k0, k1 + 1):
        lat = round(0.025 + k * g, 3)
        for j in range(j0, j1 + 1):
            lon = round(0.025 + j * g, 3)
            if m.contains(lat, lon):
                cells.append((lat, lon))
    return cells


def snap(lat: float, lon: float) -> tuple[float, float]:
    g = config.GRID_DEG
    return (round(0.025 + round((lat - 0.025) / g) * g, 3),
            round(0.025 + round((lon - 0.025) / g) * g, 3))


def distance_to_boundary_km(m: Municipality, lat: float, lon: float) -> float:
    """Distance in km from a point to the nearest boundary vertex."""
    k = math.cos(math.radians(lat))
    return 111.2 * min(math.hypot(y - lat, (x - lon) * k) for r in m.rings for x, y in r)
