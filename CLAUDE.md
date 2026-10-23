# CLAUDE.md

Guidance for Claude Code (claude.ai/code) in this repository. Status date: 2026-10-24.

## What this is

FloodWatch BiH: a flood-warning map for all 145 municipalities of Bosnia and
Herzegovina. It is the sibling of `../fire-detection` (FireWatch) and reuses its
shape - build-time data artifacts, one poll cycle, one published snapshot, one
self-contained HTML map - but it is a **separate system, not a branch**. Do not
port changes between the two by reflex.

The key difference from fire: there is no near-live *detection* feed for floods.
The core product is a **forecast** (GloFAS river discharge via Open-Meteo, ~5 km
cells, 7-day horizon); measured **gauges** from the agencies are a separate,
permission-gated layer.

No package manager, no build step. Dependencies: `requests` only (geometry
is written by hand, no shapely). Tests are plain linear scripts.

## Commands

```bash
python3 scripts/build_boundaries.py   # light polygons for the map (done, committed)
python3 scripts/build_rivers.py       # OSM river lines via Overpass (done, committed)
python3 scripts/build_points.py       # river points + thresholds (resumable; see Build)
python3 -m floodwatch poll            # one cycle -> state/snapshot.json + state/floodmap.html
python3 -m floodwatch map             # render (polls if no snapshot) and open
python3 tests_levels.py               # 11 assertions, exits non-zero on failure
```

## Architecture

```
glofas.py      Open-Meteo flood API (keyless), batching + rate-limit handling
thresholds.py  Gumbel fit on annual maxima -> watch/warning/severe (2/5/20-year flows)
levels.py      discharge series -> level; only today-and-later days can warn
geo.py         boundaries, point-in-polygon (all rings, even-odd), GloFAS cell centres
rivers.py      snap a cell onto a named OSM river; nearest_name() per cell
gauges.py      measured gauges: Sava agency, RHMZ RS, Adriatic agency (local only)
poller.py      one cycle -> snapshot.json
mapgen.py      snapshot + boundaries + river lines inlined into one HTML page
```

Data artifacts (committed, build-time only, never fetched at runtime):
`data/bih/municipalities.json` (no Telegram fields on purpose - flood needs its
own bot and channels), `data/bih/*.geojson` boundaries, `boundaries-simple.json`,
`rivers.json`, and `river_points.json` (once built).

Municipality level = worst level among its rivers (up to `MAX_RIVERS` = 3, so
Bosna and Krivaja both appear at Zavidovici). Colours run blue -> violet ->
magenta deliberately, so the flood scale never reads as FireWatch's orange/red.

## Build (`scripts/build_points.py`)

Picks up to three river cells per municipality and derives thresholds. It is
**resumable**: results are cached in `state/build-cache.json` (gitignored), so a
run that dies on a rate limit resumes where it stopped. Just run it again.

Stages: (1) 30-day mean discharge for every GloFAS cell inside any municipality
(2,312 cells); (2) per municipality, the strongest `CANDIDATES` (8) cells are each
named by their nearest OSM river, best cell per river kept; (3) 33-year archive
(`HISTORY_START` = 1993-01-01 to last full year) for the chosen cells -> Gumbel
thresholds. A municipality whose best cell is below `MIN_RIVER_M3S` gets
`river: false` and no point.

**Status 2026-10-24: stage 1 is fully cached; stage 3 had not run** - Open-Meteo's
*daily* quota was exhausted by earlier runs. A background loop was started
(`retry.sh` in the Claude job tmp dir) that probes the API every 10 min and then
runs the build. If it is gone, simply rerun `python3 scripts/build_points.py`
once the API answers again. Check `data/bih/river_points.json` exists.

## Landmines (all measured)

1. **Open-Meteo limits are per IP**: 10,000 calls/day, 5,000/hour, 600/min, and
   the terms warn shared platforms can be limited sooner. Calls are weighted by
   locations x days, so the 33-year archive is far heavier than a 30-day sample.
   A first run that fetched 93 days for all 2,312 cells exhausted the hourly limit,
   and repeated attempts exhausted the daily one. Three distinct 429 messages:
   "Minutely", "Hourly", "Daily ... try again tomorrow". `glofas._get` waits out
   only the minutely one; the others raise so the caller resumes from cache.
2. **HTTP 400 "requests too much data"** when locations x days is too large:
   archive fetches use `batch=3`, recent windows `BATCH=50`.
3. **The flood API snaps to a 0.05 degree grid** with cell centres at
   `0.025 + k*0.05`. Ask for centres (`geo.cell_centres`) to get one cell
   reproducibly. A cell centre is **not on the river** (up to ~3.5 km off), hence
   `rivers.py` snapping for display.
4. **Non-river cells answer 0.0, not an error.** `MIN_RIVER_M3S` (1.0) filters them.
5. **A single point per municipality was a design bug**: the Bosna and Krivaja
   flood together at Zavidovici. Hence multiple rivers per municipality.
6. **Which river a cell reports is a heuristic** (`rivers.nearest_name`: the
   closest named OSM river line within 6 km). GloFAS gives no river identity.
   Known weak spots will be municipalities with two similar rivers; review the
   picks in `river_points.json` after every rebuild.
7. **Thresholds are estimates, not official figures.** Gumbel (method of moments)
   on annual maxima; the 20-year level is an extrapolation. Treat levels as
   relative severity. A level means the *forecast* reaches that flow at a ~5 km
   cell - not water in the street.
8. **Overpass is flaky**: `build_rivers.py` rotates mirrors and retries. Only
   `waterway=river` is taken (streams would make a ditch a "river").
9. **Never read only `coordinates[0]` of a boundary** - MultiPolygons exist
   (same lesson as fire-detection's `geo.py`).
10. **Test the map by rendering**: headless Chrome screenshot of a temp copy
    (inject a `setTimeout` to open a popup), delete the copy afterwards. There is
    no JS test framework, by the same decision as FireWatch. Synthetic demo maps
    must carry an unmistakable "DEMO - SYNTHETIC DATA" banner.

## Measured gauges (`gauges.py`) - local only until permission is on file

Three public sources, probed 2026-10-23. **None states a reuse licence.** See
`Importat_to_to.md` (Bosnian) for the terms table, rules and draft permission
emails. Until written replies exist: do not publish gauge data, do not wire it to
alerts, `GAUGES_ENABLED` is for local use.

| Source | Access | Notes (verified) |
|---|---|---|
| Sava agency `vodostaji.voda.ba` | static JSON `/data/internet/layers/10/index.json` (a WISKI web-public export) | 99 stations, hourly; carries the agency's own class (`#MIN#`=N, `#TH1#`=P, `#TH2#`=R, `#TH3#`=V, `#TH4#`=Z). No class = "thresholds not defined"; the agency flags data older than 6 h / 2 days. Impressum: informative, not official. Main site `voda.ba` returned 503 every time. |
| RHMZ RS `rhmzrs.com` | `/data/feeds/HidroPodaci.json` | 34 stations, 31 with a reading. **No unit stated anywhere** (feed or page) - do not assume cm. No thresholds. Terms: non-commercial/informational use only and **no modification without prior written approval**; whether a derived warning level counts as modification is unanswered. |
| Adriatic agency `jadran.ba` | stations embedded as JSON in the HTML of `avpjm.jadran.ba/vodomjerne_stanice` (`<stations-map :stations=...>`) | 20 stations, raw flood-defence thresholds on 6. Fragile (HTML scrape). Timestamps described as "winter time" - zone unconfirmed, so shown as published and flagged. No terms found. |

Rules the code follows: values shown exactly as published; the only class shown
is one the source publishes itself; nothing derived from a gauge reading; each
source isolated so one failure never costs the others.

Not checked or unresolved: Vode Srpske (site not found), Brcko, FHMZ bulletin
(`fop.fhmzbih.gov.ba`, few stations, some thresholds, no terms found), DHMZ
Croatia (no terms found, possible fees), Sava HIS `savahis.org` (login-style app,
policy page unreadable). Do not use any of these without checking.

## Licences and attribution (for publishing)

- **Open-Meteo free API**: non-commercial only (no subscriptions or advertising),
  CC-BY 4.0 - the map needs visible attribution. Confirm exact wording on their
  licence page before publishing.
- **OpenStreetMap** tiles and river lines: attribution (tiles already credited).
- Agencies: attribution as each requests in its written reply.

## Roadmap to publish

Phase 1 - map only (GloFAS forecast, no gauges, no alerts):
1. Finish the data build (blocked on Open-Meteo daily quota).
2. Render the real map; review river picks and thresholds; fix doubtful ones.
3. GitHub: new repo, Pages source = GitHub Actions, `poll.yml` as
   `workflow_dispatch` only (same reasoning as FireWatch: no `schedule:`).
   Poll about every 3 hours. **Risk: shared GitHub runner IPs may be rate-limited
   by Open-Meteo**; fallback is polling from a laptop or small server.
   Never push or enable Pages without the user's explicit go-ahead.
4. Add attributions; write README and field notes.

Phase 2 - gauges: send the three permission emails (drafts in
`Importat_to_to.md`), wait for written replies, store them under `permissions/`,
then enable the layer publicly and decide whether gauge classes may raise a
municipality's level.

Phase 3 - alerts: new Telegram bot and channels (per municipality or fewer -
undecided; FireWatch's provisioning hit platform limits), de-duplication store
for sent alerts, `FIREWATCH_`-style secrets. **Never trigger real alerts as a side
effect of testing.**

## Repo conventions

`from __future__ import annotations`, a module docstring that explains *why*,
comments only for non-obvious decisions and measured facts. Commit messages end
with the Co-Authored-By line used in this session.
