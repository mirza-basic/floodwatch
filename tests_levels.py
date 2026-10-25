"""Plain linear script, same shape as fire-detection's tests: exits non-zero on failure."""
from __future__ import annotations

import sys

from floodwatch import levels, thresholds

fails = 0


def check(name, ok):
    global fails
    print(("ok   " if ok else "FAIL ") + name)
    fails += 0 if ok else 1


th = {"watch": 10.0, "warning": 20.0, "severe": 40.0}
check("below watch is normal", levels.classify(9.9, th) == "normal")
check("at watch", levels.classify(10.0, th) == "watch")
check("between warning and severe", levels.classify(25, th) == "warning")
check("above severe", levels.classify(99, th) == "severe")
check("no thresholds is normal", levels.classify(99, None) == "normal")
check("missing flow is normal", levels.classify(None, th) == "normal")

days = ["2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"]
a = levels.assess(days, [90, 5, 8, 22, 12], th, "2026-10-23")
check("past crest ignored", a["level"] == "warning" and a["peak_day"] == "2026-10-24")
check("now taken from today", a["now"] == 8)
check("all past is normal", levels.assess(days[:2], [90, 90], th, "2026-10-23")["level"] == "normal")

# Gumbel on a known sample: thresholds must rise with return period.
g = thresholds.gumbel([float(x) for x in range(10, 60, 2)])
check("gumbel ordered", g and g["watch"] < g["warning"] < g["severe"])
check("gumbel needs 20 years", thresholds.gumbel([1.0] * 10) is None)
# ensemble spread: past days blanked (statistics exist for forecast days only), missing stats tolerated
from floodwatch import poller
d = {"time": ["2026-10-23", "2026-10-24", "2026-10-25"], "river_discharge": [1, 2, 3]}
for k in ("min", "p25", "median", "p75", "max"):
    d[f"river_discharge_{k}"] = [9.123, 8.456, 7.789]
b = poller.band(d, "2026-10-24")
check("band blanks the past and rounds", b["max"] == [None, 8.46, 7.79] and b["min"][0] is None)
check("band tolerates a response without statistics", poller.band({"time": ["2026-10-24"], "river_discharge": [1]}, "2026-10-24") is None)
sys.exit(1 if fails else 0)
