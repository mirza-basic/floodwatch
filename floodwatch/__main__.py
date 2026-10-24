"""python3 -m floodwatch poll | map [port]

`map` serves the page on http://127.0.0.1:<port>/ (default 8765) instead of opening
the file: OpenStreetMap's tile servers answer a request with no Referer by sending
back a "403 Access blocked - app is not following the tile usage policy" image, and
a page opened from file:// sends none. Served over http the browser sends
`Referer: http://127.0.0.1:<port>/`, which the tile server accepts (checked
2026-10-24). Only floodmap.html is served - not the rest of state/.
"""
from __future__ import annotations

import json
import sys
import http.server
import webbrowser

from . import config, mapgen, poller

MAP = config.STATE_DIR / "floodmap.html"


def main(argv: list[str]) -> int:
    config.ensure_state_dir()
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
        serve(int(argv[1]) if len(argv) > 1 else 8765)
    return 0


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] not in ("/", "/floodmap.html"):
            self.send_error(404)
            return
        body = MAP.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the terminal quiet
        pass


def serve(port: int) -> None:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)  # loopback only
    url = f"http://127.0.0.1:{port}/"
    print(f"serving {url}  (Ctrl-C to stop)")
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
