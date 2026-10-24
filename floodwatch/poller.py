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

from . import config, gauges as gauges_mod, glofas, levels

TZ = ZoneInfo("Europe/Sarajevo")
SNAPSHOT = config.STATE_DIR / "snapshot.json"


def cycle() -> dict:
    config.ensure_state_dir()
    points = json.loads(config.POINTS_FILE.read_text())
    munis = {m["id"]: m for m in json.loads((config.DATA_DIR / "municipalities.json").read_text())}
    rivers = [p for p in points if p["river"]]
    cells = sorted({(p["lat"], p["lon"]) for p in rivers})
    series = dict(zip(cells, glofas.fetch(cells, past_days=3, forecast_days=7)))
    today = datetime.now(TZ).date().isoformat()

    out = {}
    for p in points:
        rec = out.setdefault(p["id"], {"id": p["id"], "name": munis[p["id"]]["short_name"],
                                       "level": "normal", "rivers": []})
        if not p["river"]:
            continue
        d = series[(p["lat"], p["lon"])]
        r = {"river": p.get("river_name"), "near": p.get("near", False), "lat": p["lat"], "lon": p["lon"], "thresholds": p["thresholds"],
             "times": d["time"], "flows": [None if q is None else round(q, 2) for q in d["river_discharge"]]}
        r.update(levels.assess(d["time"], d["river_discharge"], p["thresholds"], today))
        rec["rivers"].append(r)
        if levels.ORDER.index(r["level"]) > levels.ORDER.index(rec["level"]):
            rec["level"] = r["level"]  # a municipality is as bad as its worst river
    for rec in out.values():
        rec["rivers"].sort(key=lambda r: -levels.ORDER.index(r["level"]))

    g, gstatus = gauges_mod.fetch_all() if config.GAUGES_ENABLED else ([], {})
    if g:
        gauges_mod.update_history(g)
    snap = {"gauges": g, "gauge_status": gstatus, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "today": today, "municipalities": list(out.values())}
    tmp = SNAPSHOT.with_suffix(".tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False))
    os.replace(tmp, SNAPSHOT)
    return snap
