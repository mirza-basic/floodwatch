"""Assemble the published site: the live map at /, the documentation at /docs/.

A Pages deploy replaces the whole site, so the map and the docs must go up together
(same reason as FireWatch's build-site.py). The pages in docs/ are written in
artifact-body form - they open with <title> and have no doctype or viewport - so
each is wrapped in a real skeleton here; served unwrapped they would render at
desktop width on a phone and in quirks mode.

    python3 deploy/build-site.py public
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKELETON = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '{head}\n</head>\n<body>\n{body}\n</body>\n</html>\n')


def wrap(src: str) -> str:
    """Split artifact-body form at the end of <style>: everything before is head."""
    m = re.search(r"</style>\s*", src)
    if not m:
        raise SystemExit("doc has no </style>; artifact-body form expected")
    return SKELETON.format(head=src[:m.end()], body=src[m.end():])


def main(out: Path) -> None:
    page = ROOT / "state" / "floodmap.html"
    if not page.exists():
        raise SystemExit("state/floodmap.html missing - run `python3 -m floodwatch poll` first")
    if out.exists():
        shutil.rmtree(out)
    (out / "docs").mkdir(parents=True)
    shutil.copy(page, out / "index.html")
    for doc in sorted((ROOT / "docs").glob("*.html")):
        (out / "docs" / doc.name).write_text(wrap(doc.read_text(encoding="utf8")), encoding="utf8")
    print(f"site: index.html + {len(list((out / 'docs').glob('*.html')))} doc page(s) -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "public"))
