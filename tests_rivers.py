"""Plain linear script, same shape as tests_levels.py: exits non-zero on failure.

rivers.layout() is the most intricate logic in the project (it decides which river is drawn
where), so it is checked on a tiny synthetic map: two squares side by side, a river through both,
a point for the river in the first square only, and a same-named river inside the second square, unconnected,
that must NOT be joined in (different rivers share names: Bistrica, Ribnica...).
"""
from __future__ import annotations

import sys

from floodwatch import geo, rivers

fails = 0


def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name)
    fails += 0 if ok else 1


sq = lambda x0, x1: [[(x0, 0.0), (x1, 0.0), (x1, 1.0), (x0, 1.0), (x0, 0.0)]]   # (lon, lat) rings
A, B = geo.Municipality("A", "A", sq(0.0, 1.0)), geo.Municipality("B", "B", sq(1.0, 2.0))
LONS = [-0.25, 0.25, 0.75, 1.25, 1.75, 2.25]       # none on a border; the two ends are far outside both squares
rivers.ways = lambda: [
    {"name": "R", "pts": [[0.5, x] for x in LONS]},
    {"name": "R", "pts": [[0.9, 1.25], [0.9, 1.75]]},          # another river called R, INSIDE B but 44 km from ours
]
# the real anchor (mlat/mlon) is always a vertex of the river, so it is one here too
pts = [{"id": "A", "river": True, "river_name": "R", "mlat": 0.5, "mlon": 0.75}]
fill = rivers.layout(pts, [A, B])
own = pts[0]["lines"]
lon = lambda run: [round(p[1], 2) for p in run]

check("own stretch is one run", len(own) == 1)
check("own stretch reaches one vertex into the neighbour so the two stretches join", lon(own[0])[-1] == 1.25)
check("own stretch keeps its inside vertices", lon(own[0])[1:3] == [0.25, 0.75])
check("a municipality without a point gets a fill stretch", len(fill.get("R", [])) == 1)
f = fill["R"][0]
check("fill borrows the level of the municipality that has the point", f["ref"] == "A")
check("fill overlaps back into the drawn stretch", lon(f["lines"][0])[0] == 0.75)
outside = lambda q: not (A.contains(q[0], q[1]) or B.contains(q[0], q[1]))
check("a run overshoots the country by at most its one joining vertex per end",
      all(sum(outside(q) for q in run) <= 2 for run in own + [r for x in fill["R"] for r in x["lines"]]))
check("an unconnected river with the same name is not joined in (it lies inside the country, so only the connectivity rule keeps it out)",
      all(p[0] != 0.9 for r in own for p in r) and all(p[0] != 0.9 for x in fill["R"] for r in x["lines"] for p in r))

# every vertex inside Bosnia is covered (the 100% requirement), counting own + fill
inside = {x for x in LONS if A.contains(0.5, x) or B.contains(0.5, x)}
drawn = {p[1] for r in own for p in r} | {p[1] for x in fill["R"] for r in x["lines"] for p in r}
check("every in-country vertex of the shown river is drawn", inside <= drawn)
# --- two UNRELATED rivers with the same name, each with its own point (real: "Una", "Ricina") ---
# R1 runs along lat 0.2 through A and B (point in A); R2 along lat 0.8 through A and B (point in B).
# Pooling by name would draw R2's part inside A as R1's line and borrow the wrong level for fills.
rivers.ways = lambda: [
    {"name": "R", "pts": [[0.2, x] for x in (0.25, 0.75, 1.25, 1.75)]},
    {"name": "R", "pts": [[0.8, x] for x in (0.25, 0.75, 1.25, 1.75)]},
]
pa = {"id": "A", "river": True, "river_name": "R", "mlat": 0.2, "mlon": 0.75}
pb = {"id": "B", "river": True, "river_name": "R", "mlat": 0.8, "mlon": 1.25}
fill2 = rivers.layout([pa, pb], [A, B])
lats = lambda lines: {round(q[0], 2) for r in lines for q in r}
check("each river keeps its own point's stretch (no cross-drawing by name)", lats(pa["lines"]) == {0.2} and lats(pb["lines"]) == {0.8})
refs = {(f["ref"], tuple(sorted(lats(f["lines"])))) for f in fill2["R"]}
check("each fill borrows the level of its own river's point", refs == {("A", (0.2,)), ("B", (0.8,))})
sys.exit(1 if fails else 0)
