"""Paths and tunables for FloodWatch.

Kept flat and import-cheap: every other module reads constants from here, and
nothing here touches the network or the disk beyond resolving paths.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "bih"
STATE_DIR = ROOT / "state"
POINTS_FILE = DATA_DIR / "river_points.json"

FLOOD_API = "https://flood-api.open-meteo.com/v1/flood"
HTTP_TIMEOUT = 60

# GloFAS v4 grid: 0.05 degrees, cell centres at 0.025 + k*0.05. The API snaps
# any requested coordinate to its nearest centre, so asking for a centre is
# asking for exactly one cell and the answer is reproducible.
GRID_DEG = 0.05

# Archive depth used to derive return-period thresholds. The reanalysis starts
# in 1984; stopping at the last full year keeps a partial year's lower maximum
# out of the annual-maxima sample.
HISTORY_START = "1993-01-01"

# A cell whose mean discharge is below this is a hillside, not a river: GloFAS
# returns 0.0 for non-river cells rather than an error.
MIN_RIVER_M3S = 1.0

# Open-Meteo accepts many comma-separated locations per call; stay well under
# the documented ceiling.
BATCH = 50

# Distinct rivers shown per municipality (Bosna and Krivaja both reach Zavidovici).
MAX_RIVERS = 3

# Measured gauges from the agencies. Local use only until written permission is on file
# (Importat_to_to.md): nothing here is wired to alerts or public output.
GAUGES_ENABLED = True
