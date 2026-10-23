"""Snap a GloFAS cell onto the river it is almost certainly reporting.

A cell centre is up to ~3.5 km from the water, so the marker is moved onto a
real river line and the stretch inside the municipality is drawn. Which river is
a heuristic, stated here so nobody mistakes it for a fact: among named rivers
passing within SNAP_KM of the cell centre, take the one with the most vertices
inside the municipality - the main river runs through a municipality, a tributary
only touches it. GloFAS offers no river identity to check this against.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from functools import lru_cache

from . import config

SNAP_KM = 6.0


@lru_cache(maxsize=1)
def ways() -> list[dict]:
    return json.loads((config.DATA_DIR / "rivers.json").read_text())


def _km(lat: float, lon: float, lat2: float, lon2: float) -> float:
    return math.hypot((lat2 - lat) * 111.2, (lon2 - lon) * 111.2 * math.cos(math.radians(lat)))


def _nearest_vertex(pts, lat, lon):
    return min(pts, key=lambda p: _km(lat, lon, p[0], p[1]))


def snap(m, lat: float, lon: float) -> dict | None:
    """{name, point:[lat,lon], lines:[[[lat,lon],...]]} or None if no river is near."""
    near = defaultdict(int)
    for w in ways():
        if not w["name"]:
            continue
        if min(_km(lat, lon, p[0], p[1]) for p in w["pts"]) <= SNAP_KM:
            near[w["name"]] += sum(m.contains(p[0], p[1]) for p in w["pts"])
    if not near:
        return None
    name = max(near, key=near.get)
    lines, inside = [], []
    for w in ways():
        if w["name"] != name:
            continue
        run = []
        for p in w["pts"]:
            if m.contains(p[0], p[1]):
                run.append(p)
            elif len(run) > 1:
                lines.append(run); run = []
            else:
                run = []
        if len(run) > 1:
            lines.append(run)
        inside += [p for p in w["pts"] if m.contains(p[0], p[1])]
    pool = inside or [p for w in ways() if w["name"] == name for p in w["pts"]]
    return {"name": name, "point": list(_nearest_vertex(pool, lat, lon)), "lines": lines}
