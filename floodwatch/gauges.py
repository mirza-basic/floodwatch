"""Measured water levels from the agencies that publish them.

Three adapters (Sava basin agency, RHMZ Republika Srpska, Adriatic agency) return one record shape.
Values are kept exactly as published. The only class carried is one the source itself publishes;
nothing is derived from a reading. Each source is fetched independently, so one failing does not
affect the others. Reading is disabled unless FLOODWATCH_GAUGES=1.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import datetime, timezone

import requests

from . import config

log = logging.getLogger("floodwatch.gauges")
UA = {"User-Agent": "FloodWatch/0.1 (non-commercial research project)"}

SAVA_URL = "https://vodostaji.voda.ba/data/internet/layers/10/index.json"
RHMZ_URL = "https://www.rhmzrs.com/data/feeds/HidroPodaci.json"
JADRAN_URL = "https://avpjm.jadran.ba/vodomjerne_stanice"

SOURCES = {
    "sava": "Agencija za vodno područje rijeke Save",
    "rhmzrs": "RHMZ Republike Srpske",
    "jadran": "Agencija za vodno područje Jadranskog mora",
}

# Codes used by the Sava agency's water-level classification; other codes get no class.
SAVA_CLASS = {"#MIN#": "N", "#TH1#": "P", "#TH2#": "R", "#TH3#": "V", "#TH4#": "Z"}


def _get(url: str) -> requests.Response:
    r = requests.get(url, headers=UA, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    return r


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def fetch_sava() -> list[dict]:
    rows = _get(SAVA_URL).json()
    if not isinstance(rows, list) or not rows or "metadata_station_id" not in rows[0]:
        raise RuntimeError("sava: unexpected layer shape")
    out = []
    for r in rows:
        lat, lon = _num(r.get("metadata_station_latitude")), _num(r.get("metadata_station_longitude"))
        if lat is None or lon is None:
            continue
        out.append({"source": "sava", "id": f"sava:{r['metadata_station_id']}",
                    "name": r.get("metadata_station_name"), "river": r.get("metadata_river_name")
                    or r.get("metadata_catchment_name"),
                    "lat": lat, "lon": lon, "value": _num(r.get("L1_ts_value")), "unit": r.get("L1_ts_unitsymbol"),
                    "time": r.get("L1_timestamp"), "class": SAVA_CLASS.get(r.get("L1_web_waterlevel_class"))})
    return out


def fetch_rhmzrs() -> list[dict]:
    rows = _get(RHMZ_URL).json()
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("rhmzrs: unexpected feed shape")
    out = []
    for r in rows:
        keys = list(r)  # Cyrillic headers; positions are time, station, level, temp, flow, Lat, Lon
        if len(keys) != 7 or "Lat" not in r or "Lon" not in r:
            raise RuntimeError("rhmzrs: columns changed")
        lat, lon = _num(r["Lat"]), _num(r["Lon"])
        name = html.unescape(re.sub(r"<[^>]+>", "", r[keys[1]])).strip()
        if lat is None or lon is None or not name:
            continue
        out.append({"source": "rhmzrs", "id": f"rhmzrs:{name}", "name": name, "river": None,
                    "lat": lat, "lon": lon, "value": _num(r[keys[2]]), "unit": None,  # The feed gives no unit.
                    "time": r[keys[0]] or None, "class": None})
    return out


def fetch_jadran() -> list[dict]:
    page = _get(JADRAN_URL).text
    m = re.search(r'<stations-map[^>]*?:stations="([^"]+)"', page, re.S)
    if not m:
        raise RuntimeError("jadran: stations-map element not found (page changed?)")
    rows = json.loads(html.unescape(m.group(1)))
    out = []
    for r in rows:
        try:
            lat, lon = (float(x) for x in r["location"].split(","))
        except (KeyError, ValueError, AttributeError):
            continue
        th = {k: r.get(k) for k in ("redovna_obrana", "vanredna_obrana", "kontinuirana_obrana") if r.get(k)}
        # `valtime` is an epoch whose time zone is not given, so it is stored as published.
        out.append({"source": "jadran", "id": f"jadran:{r['id']}", "name": r["title"], "river": r.get("vodotok"),
                    "lat": lat, "lon": lon, "value": _num(r.get("val")), "unit": r.get("unit"),
                    "time": None, "time_raw_epoch": r.get("valtime"), "thresholds": th or None, "class": None})
    return out


FETCHERS = {"sava": fetch_sava, "rhmzrs": fetch_rhmzrs, "jadran": fetch_jadran}


def fetch_all() -> tuple[list[dict], dict]:
    """(gauges, status) - status maps each source to a count or an error string."""
    from . import geo
    munis = geo.municipalities()
    gauges, status = [], {}
    for name, fn in FETCHERS.items():
        try:
            rows = fn()
            gauges += rows
            status[name] = len(rows)
        except Exception as exc:  # noqa: BLE001 - a failing source is recorded and the others continue
            log.warning("gauges %s: %s", name, exc)
            status[name] = f"error: {exc}"
    for g in gauges:
        g["municipality"] = next((m.id for m in munis if m.contains(g["lat"], g["lon"])), None)
    return gauges, status


HISTORY_FILE = config.STATE_DIR / "gauge-history.json"
HISTORY_KEEP = 96  # Maximum readings kept per station.


def update_history(gauges: list[dict], path=HISTORY_FILE) -> None:
    """Append each new published reading to its station's history and attach the history to the gauge.

    A reading is added only when its timestamp differs from the last stored one.
    """
    config.ensure_state_dir()
    hist = json.loads(path.read_text()) if path.exists() else {}
    for g in gauges:
        t = g.get("time") or g.get("time_raw_epoch")
        h = hist.setdefault(g["id"], [])
        if g.get("value") is not None and t is not None and (not h or h[-1][0] != t):
            h.append([t, g["value"]])
            del h[:-HISTORY_KEEP]
        g["history"] = h
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(hist, ensure_ascii=False))
    os.replace(tmp, path)


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
