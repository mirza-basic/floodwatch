"""One cycle: fetch discharge for every river point, assess it, publish a snapshot.

Unlike fire-detection there is no per-detection novelty to track - the state is
"what level is each river at", recomputed whole every cycle from a ~10-day
window, so there is nothing to store between runs for the map. (Alert
de-duplication will need a store once alerting exists.)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import config, glofas, levels

TZ = ZoneInfo("Europe/Sarajevo")
SNAPSHOT = config.STATE_DIR / "snapshot.json"


def cycle() -> dict:
    points = json.loads(config.POINTS_FILE.read_text())
    munis = {m["id"]: m for m in json.loads((config.DATA_DIR / "municipalities.json").read_text())}
    rivers = [p for p in points if p["river"]]
    cells = sorted({(p["lat"], p["lon"]) for p in rivers})
    series = dict(zip(cells, glofas.fetch(cells, past_days=3, forecast_days=7)))
    today = datetime.now(TZ).date().isoformat()

    out = []
    for p in points:
        rec = {"id": p["id"], "name": munis[p["id"]]["short_name"], "river": p["river"],
               "lat": p["lat"], "lon": p["lon"], "level": "normal"}
        if p["river"]:
            d = series[(p["lat"], p["lon"])]
            rec.update(levels.assess(d["time"], d["river_discharge"], p["thresholds"], today))
            rec.update(thresholds=p["thresholds"], times=d["time"],
                       flows=[None if q is None else round(q, 2) for q in d["river_discharge"]])
        out.append(rec)

    snap = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "today": today, "municipalities": out}
    tmp = SNAPSHOT.with_suffix(".tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False))
    os.replace(tmp, SNAPSHOT)
    return snap
