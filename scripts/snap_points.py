"""Add the river name, snapped marker position and in-municipality line to river_points.json.

Run after build_points.py and build_rivers.py. Idempotent. The GloFAS cell
(`lat`/`lon`) is left untouched because it is the key the poller fetches by;
the snapped position is `mlat`/`mlon`.

    python3 scripts/snap_points.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from floodwatch import config, geo, rivers  # noqa: E402


def main() -> None:
    by_id = {m.id: m for m in geo.municipalities()}
    pts = json.loads(config.POINTS_FILE.read_text())
    hit = 0
    for p in pts:
        for k in ("river_name", "mlat", "mlon", "lines"):
            p.pop(k, None)
        if not p["river"]:
            continue
        s = rivers.snap(by_id[p["id"]], p["lat"], p["lon"])
        if s:
            p.update(river_name=s["name"], mlat=s["point"][0], mlon=s["point"][1], lines=s["lines"])
            hit += 1
    config.POINTS_FILE.write_text(json.dumps(pts, ensure_ascii=False, separators=(",", ":")))
    n = sum(p["river"] for p in pts)
    print(f"snapped {hit}/{n} river points onto a named river")


if __name__ == "__main__":
    main()
