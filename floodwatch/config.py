"""Paths and tunables for FloodWatch: constants only, no network access."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "bih"
STATE_DIR = ROOT / "state"
POINTS_FILE = DATA_DIR / "river_points.json"

FLOOD_API = "https://flood-api.open-meteo.com/v1/flood"
HTTP_TIMEOUT = 60

# GloFAS grid spacing in degrees; cell centres lie at 0.025 + k * 0.05.
GRID_DEG = 0.05

# First day of the discharge history used to derive thresholds; the history ends on
# 31 December of the last full year.
HISTORY_START = "1993-01-01"

# Minimum mean discharge, in m3/s, for a cell to count as a river.
MIN_RIVER_M3S = 1.0

# Number of locations sent per API call.
BATCH = 50

# Maximum number of rivers shown per municipality.
MAX_RIVERS = 5

# Measured gauge readings from the agencies; read only when FLOODWATCH_GAUGES=1.
GAUGES_ENABLED = os.environ.get("FLOODWATCH_GAUGES") == "1"

# Maximum distance, in km, outside a municipality at which a model cell still counts for it.
NEAR_KM = 8.0


def ensure_state_dir() -> Path:
    """Create the state directory if it is missing and return its path."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR
