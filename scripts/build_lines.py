"""Recompute the drawn line of every river point and the fill stretches, without any API call.

Reads river_points.json and rivers.json and rewrites the `lines` of each point and
data/bih/river_fill.json (stretches in municipalities that have no point for the river, each
tagged with the municipality whose level it takes).

    python3 scripts/build_lines.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from floodwatch import config, geo, rivers  # noqa: E402

FILL_FILE = config.DATA_DIR / "river_fill.json"


def main() -> None:
    pts = json.loads(config.POINTS_FILE.read_text())
    fill = rivers.layout(pts, geo.municipalities())
    config.POINTS_FILE.write_text(json.dumps(pts, ensure_ascii=False, separators=(",", ":")))
    FILL_FILE.write_text(json.dumps(fill, ensure_ascii=False, separators=(",", ":")))
    n = sum(len(v) for v in fill.values())
    print(f"lines rewritten for {sum(1 for p in pts if p.get('lines') is not None)} points; "
          f"{n} fill stretches on {len(fill)} rivers -> {FILL_FILE.name} ({FILL_FILE.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
