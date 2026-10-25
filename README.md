# FloodWatch Bosna i Hercegovina

A flood-forecast map for all 145 municipalities of Bosnia and Herzegovina.

**Live map:** https://mirza-basic.github.io/floodwatch/ ·
**Documentation:** https://mirza-basic.github.io/floodwatch/docs/floodwatch-documentation.html

> **Read this first.** FloodWatch shows a **model forecast**, not an official warning. It cannot see
> small rivers, flash floods in narrow valleys, or water already in the street. **No alert on the map
> never means there is no risk.** For official information, contact the water agencies and civil
> protection in your area.

## Na bosanskom (kratko)

FloodWatch prikazuje prognozu protoka rijeka za svih 145 općina u Bosni i Hercegovini i pokazuje koje
rijeke bi u narednih 7 dana mogle dostići nivo koji se javlja jednom u 2, 5 ili 20 godina. To je
**prognoza modela (oko 5 km), a ne zvanično upozorenje.** Model ne vidi male vodotoke, a odsustvo
upozorenja ne znači da rizika nema. Za zvanične informacije obratite se vodnim agencijama i civilnoj
zaštiti. Karta je na bosanskom (uz engleski). Osvježavanje je zakazano svaka tri sata, ali GitHub ponekad kasni ili preskoči (do sada je uočen razmak do oko 5,5 sati), pa na karti uvijek provjerite vrijeme ažuriranja.

## What it does

- Takes a 7-day river-discharge forecast for the model cells that carry the main rivers
  (232 river points in 120 municipalities, up to five rivers per municipality).
- Turns each river's flow into a level by comparing it with how often that flow has happened in
  33 years of history: **watch** (about once in 2 years), **warning** (5 years), **severe** (20 years).
  These thresholds are our own estimates, not official figures.
- Shows the forecast spread across the ensemble members, so the worst plausible case is visible
  even when the main forecast stays below a threshold.
- Draws each shown river along its whole course, with a chart, a one-sentence summary and a per-day
  level strip.

## What it does not do

- It does not send alerts. (Telegram alerts are planned, not built.)
- It does not cover rivers the model cannot resolve. Of 389 pairs of a municipality and a named
  OpenStreetMap river, 51% are drawn, 41% have too little modelled flow to forecast, and 8% have
  flow but are not shown. The map says so in its legend and in every popup.
- It does not publish measured gauge readings. Code that reads three agencies' public gauge
  data exists in this repository but is **switched off by default** and never enabled for the
  published site, because none of those sources states a licence for reuse.

## Data and attribution

| Data | Source | Terms |
|---|---|---|
| River discharge and ensemble forecast | GloFAS via [Open-Meteo](https://open-meteo.com/) | Free API for non-commercial use, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Municipality boundaries, rivers, base map | © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors | ODbL |
| Map rendering | [Leaflet](https://leafletjs.com/) | |

The map credits Open-Meteo and OpenStreetMap on screen, as their terms require.

## Run it yourself

Needs Python 3 (CI uses 3.12) and `requests`. There is no build step and no API key.

```bash
python3 -m pip install requests certifi
python3 tests_levels.py          # thresholds, levels, ensemble spread
python3 tests_rivers.py          # river layout (which river is drawn where)
python3 -m floodwatch poll       # fetch the forecast, write state/snapshot.json and state/floodmap.html
python3 -m floodwatch map        # serve the page on http://127.0.0.1:8765/ and open it
```

Open the map through `map` (http), **not** by double-clicking `floodmap.html`: OpenStreetMap's tile
servers answer a page with no `Referer` (which is what a `file://` page sends) with an
"Access blocked" picture instead of the map.

The data under `data/bih/` is built once and committed (`scripts/build_*.py`): boundaries, river lines,
and the river points with their thresholds. Rebuilding the points needs about 33 years of history for
~170 model cells from Open-Meteo, which exceeds its free daily limit in one go. The script
(`scripts/build_points.py`) is resumable and caches what it has fetched, so run it again after a
rate-limit error.

## How it is published

`.github/workflows/poll.yml` is scheduled every three hours, builds the site with `deploy/build-site.py`
and deploys it to GitHub Pages. The page is a single self-contained HTML file with the data inlined.
GitHub delays or skips scheduled runs (the first three scheduled runs were 2.4 and 5.5 hours apart), so check the update time shown on the map. Open-Meteo limits calls per IP address and warns that shared platforms such as CI runners can be limited
sooner, so a run may occasionally fail; a failed run publishes nothing, and the map shows a warning when
its data is more than nine hours old.

## Repository layout

```
floodwatch/     poller, thresholds, levels, river layout, map generator (mapgen.py, ui.css)
scripts/        one-off builders for the committed data
data/bih/       boundaries, rivers, river points, fill stretches (derived from OpenStreetMap)
deploy/         assembles the published site
docs/           system documentation (also served at /docs/)
tests_*.py      plain scripts that exit non-zero on failure
CLAUDE.md       working notes: architecture, measured behaviour, pitfalls
```

## Licence

Not yet chosen. Until a `LICENSE` file is added, the code is not licensed for reuse. Data derived from
OpenStreetMap remains © OpenStreetMap contributors under the ODbL.
