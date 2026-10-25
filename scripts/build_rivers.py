"""Download named river geometry (waterway=river) from Overpass and write data/bih/rivers.json.

Overpass mirrors are tried in turn, with retries. Vertices closer than about 300 m to the last
kept vertex are dropped.

    python3 scripts/build_rivers.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from floodwatch import config  # noqa: E402

MIRRORS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
QUERY = '[out:json][timeout:240];way["waterway"="river"](42.4,15.6,45.4,19.8);out geom;'
STEP = 0.003  # degrees; ~300 m between kept vertices


def fetch() -> dict:
    last = None
    for attempt in range(6):
        url = MIRRORS[attempt % len(MIRRORS)]
        try:
            r = requests.post(url, data={"data": QUERY}, timeout=300,
                              headers={"User-Agent": "floodwatch-build/0.1"})
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
            last = f"{url}: HTTP {r.status_code} {r.text[:120]!r}"
        except requests.RequestException as exc:
            last = f"{url}: {exc}"
        print("retry:", last, flush=True)
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"overpass failed: {last}")


def thin(pts):
    kept = [pts[0]]
    for p in pts[1:-1]:
        if abs(p[0] - kept[-1][0]) + abs(p[1] - kept[-1][1]) >= STEP:
            kept.append(p)
    kept.append(pts[-1])
    return kept


def main() -> None:
    data = fetch()
    ways = []
    for el in data["elements"]:
        g = el.get("geometry")
        if el["type"] != "way" or not g or len(g) < 2:
            continue
        pts = thin([[round(p["lat"], 4), round(p["lon"], 4)] for p in g])
        ways.append({"name": el.get("tags", {}).get("name", ""), "pts": pts})
    path = config.DATA_DIR / "rivers.json"
    path.write_text(json.dumps(ways, ensure_ascii=False, separators=(",", ":")))
    named = sum(1 for w in ways if w["name"])
    print(f"{path.name}: {len(ways)} ways ({named} named), {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
