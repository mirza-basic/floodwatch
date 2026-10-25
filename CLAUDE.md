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

**Status 2026-10-24: built, then improved the same day.** `data/bih/river_points.json`
(committed): 207 river points in 120 of 145 municipalities (superseded below), 201/207 matched to a named OSM river, 0 threshold-ordering violations. The
map renders with live data; every river was far below its "watch" flow (max 32%).
The build took several attempts because Open-Meteo's daily/hourly quotas were
exhausted first; it finished on a different IP after the user switched on a VPN.
(The VPN was the user's decision - circumventing a per-IP limit is against the
spirit of the free tier; do not make it a routine.)

**Nearby cells (`NEAR_KM` = 8).** A GloFAS cell is 5 km wide and a river often runs
along a border or through a polygon containing no cell centre, so counting only
cells whose centre is inside left 42 municipalities with no river (Zavidovici got
Krivaja but not the Bosna). Now cells up to `NEAR_KM` outside are also candidates,
in a separate pool (`NEAR_CANDIDATES`) so a big border river cannot crowd out the
municipality's own tributaries, and only if a *named river with a stretch inside the
municipality* passes next to the cell. Such points carry `near: true` and the popup
says "nearby model cell, outside the municipality". 99 of 207 points are near cells.
Result: 120/145 municipalities (was 103); Zavidovici = Bosna, Krivaja, Vozucica.

**Cap raised to 5 rivers (2026-10-24, second pass).** A first count found 55 strong rivers being
dropped (Tavna at Bijeljina ~31 m3/s, Krusnica at Bosanska Krupa, Vrbanja at Banja Luka), so
`MAX_RIVERS` 3 -> 5, `CANDIDATES` 8 -> 12, `NEAR_CANDIDATES` 4 -> 6 (a dry run, no API calls,
predicted 13 new history fetches; the real build needed no more). **That first count used the
strongest cell within 4 km of the river, which borrows a neighbouring river's flow (it made Gostovic
look like it shared the Bosna's cell). The right test is the cell that COVERS each vertex**
(`geo.snap`). Recount on 2026-10-25, 389 (municipality, named OSM river with >=5 points inside)
pairs: 198 shown (51%), 158 where the covering cells carry <1 m3/s (41% - invisible to the model),
33 with flow in their own cell but not shown (8% - cap, or the cell is named for another river).
Now **232 river points in 120 municipalities** (1 river: 53, 2: 36, 3: 20, 4: 8, 5: 3).
Not recovered: Jadar at Bratunac (the cell is named for another river - the naming heuristic,
not the cap). Gostovic at Zavidovici is a 13.8 km line whose own cell carries 0.02 m3/s: the model cannot see it
(the 14 m3/s cell at its mouth is the Bosna's). Not shown, and nothing honest could be.
**Names are OSM's `name` tag as is**, so some are Cyrillic (e.g. "Јања", "Крижевица"); the
HOT export has `name_latin`/`name_bs` but our Overpass data does not.
**The map states its coverage** (legend, every popup, empty state): only rivers the model can
resolve are shown and no alert never means no risk - a calm map is easily read as "my small
river is fine".

**Still without a river (25):** banovici, buzim, celic, centar, dobretici, gradacac,
han-pijesak, istocni-drvar, istocni-stari-grad, istocno-novo-sarajevo, kalesija,
kladanj, kresevo, kupres-rs, lopare, novo-sarajevo, osmaci, pale-rs, pelagicevo,
srebrenik, stanari, stari-grad, travnik, trnovo-fbih, velika-kladusa. Not yet
diagnosed per municipality; the likely reason (unverified) is that GloFAS at ~5 km
does not resolve those small rivers (cells below `MIN_RIVER_M3S`). The map says "no
significant river in the model", which is accurate; do not claim these have no river.

**Other open items:** thresholds are not compared against any official figure; 6
points have no river name; popups with up to five rivers scroll.

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

## OpenStreetMap tiles need a Referer (measured 2026-10-24)

`tile.openstreetmap.org` answers HTTP **200** with a "403 Access blocked - app is not
following the tile usage policy" *image* (6,987 bytes) when a request has a
browser-like User-Agent and **no Referer**; the same tile with any Referer is the real
one (41,833 bytes). A page opened from `file://` sends no Referer, so the local map
showed blocked tiles in the user's browser. The policy
(operations.osmfoundation.org/policies/tiles/) says web pages must send a valid
Referer and says nothing about `file://`.

- **Never open the map from the file.** `python3 -m floodwatch map [port]` serves
  `floodmap.html` only (loopback, port 8765) so the browser sends
  `Referer: http://127.0.0.1:8765/`. Confirmed working by the user in their browser.
- Headless Chrome did **not** reproduce the block (real tiles from both file:// and
  http://), so screenshots cannot verify this; trust the curl test and the user.
- A published page is fine as long as nothing sets a restrictive `Referrer-Policy`
  (the policy forbids it). The default browser behaviour is acceptable.
- Same policy: show the attribution (done), do not bulk-download tiles, honour cache
  headers (the browser does). FireWatch's local map uses the same tile URL and may be
  affected when opened from a file - not checked or changed.

## Measured gauges (`gauges.py`) - local only until permission is on file

Three public sources, probed 2026-10-23. **None states a reuse licence.** See
the local, **unpublished** file `Importat_to_to.md` (Bosnian; kept out of the public
repo, listed in `.gitignore`) for the terms table, rules and draft permission emails. Until written replies exist: do not publish gauge data, do not wire it to
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

## Deployment (decided 2026-10-24: one public repo, Pages deployed from it)

**Pushed 2026-10-24** to https://github.com/mirza-basic/floodwatch (public, `main`). Public site will be
https://mirza-basic.github.io/floodwatch/ once Pages is enabled. Remaining by hand in the
GitHub UI: Settings > Pages > Source = **GitHub Actions**, then Actions > "Poll and publish" >
Run workflow. Verified after the push via the API: 16 commits, one no-reply identity, no work
email, neither removed file present, workflow file present, 0 runs yet.

Chosen over a private-source + public-site split. (Docs read 2026-10-24: Pages on
GitHub Free requires a public repo; a private repo's Pages site is public anyway; a
cross-repo deploy would need a deploy key or token, and whether a push made with one
triggers a Pages build is **not stated** in the docs - untested.)

- `.github/workflows/poll.yml`: every 3 h (`schedule`) or manually; checkout, tests,
  poll, `deploy/build-site.py public`, then `upload-pages-artifact` +
  `deploy-pages`. **Written but never run** - no repo exists yet. Scheduled
  workflows may be disabled after a long period of repo inactivity (recalled from
  FireWatch's notes, not verified here), which would stop the map silently; the map
  shows a warning when its data is over 9 h old.
- **Gauges are off by default** (`FLOODWATCH_GAUGES=1` enables them, for local use
  only) and the workflow has a guard step that fails the run if gauge data appears
  in the built page. The guard was tested: it trips when gauges are on.
- `deploy/build-site.py` puts the map at `/` and wraps `docs/*.html` into real pages.
- **History was rewritten before the first push (2026-10-24)**: every commit now
  carries the author's GitHub no-reply address (`ID+USERNAME@users.noreply.github.com`,
  the format GitHub documents for accounts created after July 2017), and
  `Importat_to_to.md` and an early gauge test page were removed from all commits.
  Verified: no work e-mail and neither file in any commit. The old history exists only
  in a local bundle outside the repo (`../floodwatch-history-backup.bundle`) - never
  push it. New commits must use the local git identity set in this repo.

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
the permissions note), wait for written replies, store them under `permissions/`,
then enable the layer publicly and decide whether gauge classes may raise a
municipality's level.

Phase 3 - alerts: new Telegram bot and channels (per municipality or fewer -
undecided; FireWatch's provisioning hit platform limits), de-duplication store
for sent alerts, `FIREWATCH_`-style secrets. **Never trigger real alerts as a side
effect of testing.**

## Map UI (mirrors FireWatch's)

`mapgen.py` + `floodwatch/ui.css`. The stylesheet is **FireWatch's `<style>` block copied
once** (lines 68-420 of its `mapgen.py` on 2026-10-24) with the accent changed to blue
and the fire colours to flood colours; the markup keeps its ids (`#side`, `#hrange`,
`#timebar`, `#langsw`, `#muniinfo`, `#drawer-btn`...). It is a copy, not an import:
the two projects must not depend on each other. FireWatch's Esri satellite and
OpenTopoMap basemaps were **not** carried over - their terms are unverified and
only OpenStreetMap's tile policy has been read. FireWatch's measure tool, clock/"show
all" toggle, date picker, splash and Telegram button have no flood counterpart yet.
Day chips replace the time ranges, and the bottom bar steps through forecast days.
Verified 2026-10-24 in headless Chrome: no console errors, all controls exercised by
script (chips, cards, language, drawer, layers, play, legend, eye), desktop and 500 px.
Landmine: the browser's `bs` locale can be missing, so dates are formatted by hand.
Click behaviour: a river dot/line/card calls `openMuni(m, at, r)` and shows that river alone with
a "{n} more rivers in {m}" link; the municipality polygon calls it without `r` and lists all.
Untested suspicion: `drawMap` merges dots at the same place and level (`seen`), so where two
municipalities share a river point only the first gets a dot to click.

## Full-length rivers (`rivers.layout`, `scripts/build_lines.py`)

Requirement (user, 2026-10-24): every river shown must be drawn 100% along its course. Two gaps
existed: the vertex lost at each municipality border (a line was clipped to vertices strictly
inside), and whole stretches inside municipalities with no point for that river (Spreča through
Kalesija 16 km and Osmaci 10 km, Bosna at Samac 4 km). `rivers.layout()` fixes both: own stretches
extend one vertex into the neighbour; stretches in a municipality without a point become **fill**
(`data/bih/river_fill.json`, name -> [{ref, lines}]) drawn in the level of the nearest drawn
stretch of the same river (`ref`), and the popup says so (`fillNote`). Landmine: **only ways
connected to the shown river are used** (`_components`, ends within 0.5 km), because different
rivers share a name (Bistrica, Ribnica); using every way of that name would draw the wrong rivers.
A vertex within 1.5 km of a municipality still counts as inside BiH, which catches border rivers
(Una, Sava, Drina) whose line lies just outside the traced polygons. Result: 120 fill stretches on
22 rivers; Bosna, Spreca, Una, Vrbas, Drina, Neretva, Sava, Krivaja all 100% of their in-BiH
vertices. `build_points.py` calls `layout()` so a rebuild keeps it (verified: identical output).
`build_lines.py` redoes it offline (no API calls, ~2 min). Rivers with no point at all (Gostovic) are
still not drawn - that is the unapproved "rivers without a forecast" layer.

## Charts, summary sentence, day strip (2026-10-25)

(The day strip is in the river dialog only. It was removed from the list cards on request: the list has no
date control; the day is chosen with the header chips or the bottom bar.)

`chart()`, `summary()` and `strip()` in `mapgen.py`. The poll now asks for
`river_discharge` plus `_min/_p25/_median/_p75/_max` (`glofas.DAILY_STATS`) and stores them per
river as `band`, **blanked for days before today** (`poller.band`; tested). Verified in Open-Meteo's
docs: these are "statistical analysis from ensemble members" and "only available for forecasts";
ensemble size is not stated. **Levels still use the main `river_discharge`**, the spread is shown
beside it - the worst member can cross a threshold the main line does not. A threshold is drawn
only when the data is within reach (watch from 35% of it, warning from 80% of watch, severe from
80% of warning); scaling every chart up to its watch level made a river at 4% of it look flat.
Landmine: the first CSS patch used `str.replace` on an anchor (`.gsq{width:12px`) that an earlier edit
had changed, so it silently inserted nothing and the strip rendered as plain white buttons - assert
that an anchor exists before replacing. `#muniinfo` has `max-width:280px` in the shared stylesheet;
the chart popup overrides it (430px). Poll weight: 6 variables x ~150 cells x 10 days.

## One overlay at a time

`closeOverlays(except)` in `mapgen.py` closes the municipality dialog (`#muniinfo`), Leaflet's popup
(gauges), the layers menu, the legend and the tooltip; every opener calls it (`openMuni`, the
`popupopen` event, the layers and legend buttons, `drawer`). The day-change re-render of an open
dialog goes through `openMuni` too and is safe, because opening anything else already closed the
dialog. Testing landmine: Leaflet keeps a closed popup in the DOM until its fade finishes and keeps
`map._popup` set, so "is a popup open" must be `map._popup && map.hasLayer(map._popup)`; my first
two tests reported failures that were this artefact, not a bug.

## Review before the second push (2026-10-25)

All unpushed work was reviewed, partly by an independent read-only agent given only the diff. Found
and fixed, each confirmed before fixing: (1) **script injection** - `json.dumps` leaves `</script>` intact,
so an OSM river name containing it ended the page's script block (a hostile name made 4 `</script>`
instead of 2); all four embedded blobs now go through `mapgen._js()` which escapes `< > &` and U+2028/9;
(2) `rivers.layout` pooled anchors **by name** - real rivers named "Una" and "Ricina" each have two
unrelated rivers with points - now per connected river (regression test + mutation-checked; on real
data only one point changed, so it was latent); (3) the open dialog lost its expansion, scroll and note
language on every day change, play step or language switch - now re-rendered in place (`openMuni(...,
keep=true)`); (4) null-safety: all-null ensemble stats printed "-Infinity%", a null peak or all-null
flows broke cards/charts; (5) `String.replace` with a replacement string mangles `$&` - function
replacers for names. Also: coverage numbers in the docs were wrong (see the recount above), a
leftover FireWatch env var was removed from the workflow, and `tests_rivers.py` now runs in CI.
Not fixed on purpose: `_components` is O(ways^2) per name (the whole offline build takes minutes, it
never runs in the page); the English plural for 21 ("1 more river") cannot occur (n <= 4); chart hit
areas are pointer-only (no keyboard tooltip); Leaflet loads from unpkg without a subresource-integrity
hash (as in FireWatch). **Open decisions, not code:** the repo has no README or LICENSE, and it
publishes OSM-derived data files (boundaries, rivers) whose ODbL terms (attribution, share-alike for
derived databases) have not been read in this project.

## Grouped pins (2026-10-25)

Calm river dots (`dotsC`) and calm gauges (`gaugesC`) are `L.markerClusterGroup`s from
Leaflet.markercluster 1.5.3 (MIT, loaded from unpkg with SRI hashes; if the script is blocked,
`mkCluster()` falls back to a plain layer group and the pins are drawn ungrouped - tested by
corrupting the hash). **Pins on alert are never grouped** (`dotsA`, `gaugesA` are plain groups): a river at
watch or above for the selected day, or a gauge whose class is not N, must stay visible. Grouping
stops from zoom 11 (`disableClusteringAtZoom`). `dots` and `gl` stay as container layer groups
holding both, so the eye button and the layer checkbox still work; never call `dots.clearLayers()`
(it would remove the cluster groups themselves) - clear `dotsC`/`dotsA`. Testing landmines: a
`layer.fire("click")` stays on the marker unless propagated (`fire(type, data, true)`, which is what a
real DOM click does), and zoom animations never finish under headless virtual time, so set
`map.options.zoomAnimation=false` and `map._zoomAnimated=false` before asserting a zoom change.

## Documentation

`docs/floodwatch-documentation.html` is the system documentation, same idea as
FireWatch's `docs/`: a self-contained page in **artifact-body form** (opens with
`<title>`, no doctype or viewport, so it can also be published as a Claude artifact;
a publishing step would wrap it in a real skeleton, as FireWatch's
`deploy/build-site.py` does). Its stylesheet is FireWatch's with a flood palette
(indigo accent, never the fire orange). **Update it when behaviour changes** -
especially the field notes and the licences section, which go stale invisibly. There
is no generator: edit the HTML directly. Checked on 2026-10-24: every nav anchor has
a target, tags balance, desktop renders in light/dark; a phone-width render could not
be verified (headless Chrome will not go below its minimum window width), though the
CSS is the same as FireWatch's.

## Repo conventions

`from __future__ import annotations`, a module docstring that explains *why*,
comments only for non-obvious decisions and measured facts. Commit messages end
with the Co-Authored-By line used in this session.
