"""python3 -m floodwatch poll | map"""
from __future__ import annotations

import json
import sys
import webbrowser

from . import config, mapgen, poller

MAP = config.STATE_DIR / "floodmap.html"


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "map"
    if cmd == "poll":
        snap = poller.cycle()
    elif cmd == "map" and poller.SNAPSHOT.exists():
        snap = json.loads(poller.SNAPSHOT.read_text())
    elif cmd == "map":
        snap = poller.cycle()
    else:
        print(__doc__)
        return 2
    MAP.write_text(mapgen.render(snap))
    by = {}
    for m in snap["municipalities"]:
        by[m["level"]] = by.get(m["level"], 0) + 1
    print(f"{MAP}  levels: {by}")
    if cmd == "map":
        webbrowser.open(MAP.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
