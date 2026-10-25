"""Match GloFAS cells to named OpenStreetMap rivers and lay the rivers out for drawing.

snap() moves a cell onto a river line and returns the stretch inside one municipality. The river
is the named one within SNAP_KM of the cell centre with the most vertices inside the municipality.
layout() draws each shown river along its whole course.
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
    out = json.loads((config.DATA_DIR / "rivers.json").read_text())
    for w in out:  # Bounding box of each way, used to skip ways far from a cell.
        la = [p[0] for p in w["pts"]]; lo = [p[1] for p in w["pts"]]
        w["bb"] = (min(la), min(lo), max(la), max(lo))
    return out


def _km(lat: float, lon: float, lat2: float, lon2: float) -> float:
    return math.hypot((lat2 - lat) * 111.2, (lon2 - lon) * 111.2 * math.cos(math.radians(lat)))


def _nearest_vertex(pts, lat, lon):
    return min(pts, key=lambda p: _km(lat, lon, p[0], p[1]))


def nearest_name(lat: float, lon: float) -> str | None:
    """Name of the closest named river line within SNAP_KM of a cell centre."""
    best, dist = None, SNAP_KM
    pad = SNAP_KM / 111.0 * 1.6
    for w in ways():
        b = w["bb"]
        if not w["name"] or not (b[0] - pad <= lat <= b[2] + pad and b[1] - pad <= lon <= b[3] + pad):
            continue
        d = min(_km(lat, lon, p[0], p[1]) for p in w["pts"])
        if d < dist:
            best, dist = w["name"], d
    return best


def snap(m, lat: float, lon: float, name: str | None = None) -> dict | None:
    """{name, point:[lat,lon], lines:[[[lat,lon],...]]}, or None when no river is near.

    `name` selects the river; without it the river with the most vertices inside `m` is chosen.
    """
    near = defaultdict(int)
    for w in ways():
        if not w["name"]:
            continue
        b, pad = w["bb"], SNAP_KM / 111.0 * 1.6
        if not (b[0] - pad <= lat <= b[2] + pad and b[1] - pad <= lon <= b[3] + pad):
            continue
        if min(_km(lat, lon, p[0], p[1]) for p in w["pts"]) <= SNAP_KM:
            near[w["name"]] += sum(m.contains(p[0], p[1]) for p in w["pts"])
    if name is None:
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


# --- full-length layout -------------------------------------------------------------------
# layout() draws each shown river along its whole course: the stretches inside the municipalities
# that have a point for it (each extended by one vertex into the neighbour so they join), and the
# remaining stretches as 'fill' that takes the level of the nearest stretch of the same river.
# Only ways connected to the shown river are used, because different rivers can share a name.

JOIN_KM = 0.5      # two ways of one river join when an end lies this close to the other
BORDER_KM = 1.5    # a vertex this close to a municipality still counts as inside BiH


def _components(ws):
    """Group same-name ways into connected rivers (end of one near any vertex of another)."""
    parent = list(range(len(ws)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, a in enumerate(ws):
        for j in range(i + 1, len(ws)):
            b = ws[j]
            if find(i) == find(j):
                continue
            ends = (a["pts"][0], a["pts"][-1])
            endsb = (b["pts"][0], b["pts"][-1])
            near = any(_km(e[0], e[1], p[0], p[1]) <= JOIN_KM for e in ends for p in b["pts"]) or \
                any(_km(e[0], e[1], p[0], p[1]) <= JOIN_KM for e in endsb for p in a["pts"])
            if near:
                parent[find(i)] = find(j)
    comp: dict[int, list] = {}
    for i, w in enumerate(ws):
        comp.setdefault(find(i), []).append(w)
    return list(comp.values())


def layout(points: list[dict], munis) -> dict:
    """Set p["lines"] for every river point and return {river: [{ref, lines}]} fill stretches.

    The work is done per connected river, not per name, because different rivers can share a name.
    """
    rpts = [p for p in points if p.get("river") and p.get("river_name") and p.get("mlat") is not None]
    fill: dict[str, list] = {}
    from . import geo

    def near_bih(q):
        """Nearest municipality within BORDER_KM of q, or None. Municipalities are pre-filtered by bounding box."""
        pad = 0.03
        cands = [m for m in munis if m.bbox[0] - pad <= q[1] <= m.bbox[2] + pad and m.bbox[1] - pad <= q[0] <= m.bbox[3] + pad]
        if not cands:
            return None
        d, best = min((geo.distance_to_boundary_km(m, q[0], q[1]), m.id) for m in cands)
        return best if d <= BORDER_KM else None

    def owner_of(q, has):
        inside = [m.id for m in munis if m.contains(q[0], q[1])]
        for i in inside:
            if i in has:
                return i
        return inside[0] if inside else near_bih(q)

    for p in rpts:
        p["lines"] = []
    for name in sorted({p["river_name"] for p in rpts}):
        mine = [p for p in rpts if p["river_name"] == name]
        claimed: set[int] = set()
        for comp in _components([w for w in ways() if w["name"] == name]):
            anchors = [p for p in mine if id(p) not in claimed and
                       any(_km(p["mlat"], p["mlon"], q[0], q[1]) <= 2.0 for w in comp for q in w["pts"])]
            if not anchors:
                continue
            claimed.update(id(p) for p in anchors)
            has = {p["id"] for p in anchors}
            own: dict[str, list] = {i: [] for i in has}
            stretches, ref_pool = [], []
            for w in comp:
                pts = w["pts"]
                owners = [owner_of(q, has) for q in pts]
                i = 0
                while i < len(pts):
                    if owners[i] is None:
                        i += 1
                        continue
                    j = i
                    while j + 1 < len(pts) and owners[j + 1] == owners[i]:
                        j += 1
                    run = pts[max(0, i - 1):min(len(pts), j + 2)]     # one vertex into the neighbour
                    if len(run) > 1:
                        if owners[i] in has:
                            own[owners[i]].append(run)
                            ref_pool += [(q, owners[i]) for q in pts[i:j + 1]]
                        else:
                            stretches.append(run)
                    i = j + 1
            for p in anchors:
                p["lines"] = own[p["id"]]
            for run in stretches:
                mid = run[len(run) // 2]
                if ref_pool:
                    ref = min(ref_pool, key=lambda x: _km(mid[0], mid[1], x[0][0], x[0][1]))[1]
                    fill.setdefault(name, []).append({"ref": ref, "lines": [run]})
    return fill
