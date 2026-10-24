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
    out = json.loads((config.DATA_DIR / "rivers.json").read_text())
    for w in out:  # bbox lets snap() skip the ~95% of ways nowhere near a cell
        la = [p[0] for p in w["pts"]]; lo = [p[1] for p in w["pts"]]
        w["bb"] = (min(la), min(lo), max(la), max(lo))
    return out


def _km(lat: float, lon: float, lat2: float, lon2: float) -> float:
    return math.hypot((lat2 - lat) * 111.2, (lon2 - lon) * 111.2 * math.cos(math.radians(lat)))


def _nearest_vertex(pts, lat, lon):
    return min(pts, key=lambda p: _km(lat, lon, p[0], p[1]))


def nearest_name(lat: float, lon: float) -> str | None:
    """Name of the closest named river line within SNAP_KM of a cell centre.

    Used per cell when a municipality has several: a high-discharge cell is on a
    main stem, so the nearest line to its centre is the river it reports, which
    is what lets Bosna and Krivaja get separate points at Zavidovici."""
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
    """{name, point:[lat,lon], lines:[[[lat,lon],...]]} or None if no river is near.

    `name` forces the river (used once several cells have each been matched);
    without it the heuristic in the module docstring picks one."""
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
# `snap()` clips a river to one municipality, which leaves two kinds of gap: the vertex
# lost at every border crossing, and whole stretches inside municipalities that have no
# point for that river. `layout()` draws each shown river along its whole course in BiH:
# its own municipality's stretches (extended one vertex into the neighbour so they join),
# and the rest as "fill" that borrows the level of the nearest stretch of the same river.
# Several different rivers share a name (Bistrica, Ribnica...), so only ways *connected*
# to the shown river are used, never every way with that name.

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
    """Set p["lines"] for every river point and return {river: [{ref, lines}]} fill stretches."""
    by_id = {m.id: m for m in munis}
    rpts = [p for p in points if p.get("river") and p.get("river_name") and p.get("mlat") is not None]
    names = sorted({p["river_name"] for p in rpts})
    fill: dict[str, list] = {}
    from . import geo

    def owner_of(p, has):
        inside = [m.id for m in munis if m.contains(p[0], p[1])]
        for i in inside:
            if i in has:
                return i
        if inside:
            return inside[0]
        best = min(munis, key=lambda m: geo.distance_to_boundary_km(m, p[0], p[1]))
        return best.id if geo.distance_to_boundary_km(best, p[0], p[1]) <= BORDER_KM else None

    for name in names:
        mine = [p for p in rpts if p["river_name"] == name]
        has = {p["id"] for p in mine}
        anchors = [(p["mlat"], p["mlon"]) for p in mine]
        ws = [w for w in ways() if w["name"] == name]
        comps = [c for c in _components(ws)
                 if any(_km(a[0], a[1], q[0], q[1]) <= 2.0 for a in anchors for w in c for q in w["pts"])]
        own: dict[str, list] = {i: [] for i in has}
        stretches = []                         # (owner, run) for owners with no point
        ref_pool = []                          # (vertex, municipality id) of the drawn stretches
        for comp in comps:
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
                    lo, hi = max(0, i - 1), min(len(pts), j + 2)    # one vertex into the neighbour
                    run = pts[lo:hi]
                    if len(run) > 1:
                        if owners[i] in has:
                            own[owners[i]].append(run)
                            ref_pool += [(q, owners[i]) for q in pts[i:j + 1]]
                        else:
                            stretches.append((owners[i], run))
                    i = j + 1
        for p in mine:
            p["lines"] = own[p["id"]]
        for _, run in stretches:
            mid = run[len(run) // 2]
            ref = min(ref_pool, key=lambda x: _km(mid[0], mid[1], x[0][0], x[0][1]))[1] if ref_pool else None
            if ref:
                fill.setdefault(name, []).append({"ref": ref, "lines": [run]})
    return fill
