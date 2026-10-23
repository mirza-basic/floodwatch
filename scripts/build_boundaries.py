"""One light polygon per municipality for the map.

The full boundaries are 8.8 MB - fine for point-in-polygon, far too heavy to
inline into a page. Vertices closer than ~400 m to the last one kept are
dropped; at country zoom that is invisible, and rings are kept closed with
at least four points so Leaflet never receives a degenerate polygon.

    python3 scripts/build_boundaries.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from floodwatch import config, geo  # noqa: E402

MIN_STEP = 0.004  # degrees


def thin(ring):
    kept = [ring[0]]
    for x, y in ring[1:-1]:
        if abs(x - kept[-1][0]) + abs(y - kept[-1][1]) >= MIN_STEP:
            kept.append((x, y))
    kept.append(ring[0])
    return kept if len(kept) >= 4 else ring


def main() -> None:
    out = {m.id: [[[round(y, 4), round(x, 4)] for x, y in thin(r)] for r in m.rings if len(r) >= 4]
           for m in geo.municipalities()}
    path = config.DATA_DIR / "boundaries-simple.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{path.name}: {path.stat().st_size / 1024:.0f} KB, "
          f"{sum(len(r) for rs in out.values() for r in rs)} vertices")


if __name__ == "__main__":
    main()
