"""Check a deployed site: the API answers, buses carry people and move.

    python bin/smoke.py https://dxxxx.cloudfront.net/
"""

import json
import sys
import time
from urllib.request import urlopen


def snapshot(base: str) -> dict:
    with urlopen(base.rstrip("/") + "/live/snapshot.json", timeout=15) as r:
        return json.load(r)


def main() -> int:
    base = sys.argv[1]
    first = snapshot(base)
    time.sleep(20)  # a few snapshot periods
    second = snapshot(base)
    before = {b["id"]: (b["lat"], b["lon"]) for b in first["buses"]}
    moved = sum(1 for b in second["buses"] if before.get(b["id"]) not in (None, (b["lat"], b["lon"])))
    passengers = sum(b["passengers"] for b in second["buses"])
    checks = {
        "buses reported": len(second["buses"]) > 0,
        "people on board": passengers > 0,
        "buses moving": moved > len(second["buses"]) // 2,
        "people waiting at stops": bool(second["waiting"]),
    }
    print(f"{len(second['buses'])} buses, {passengers} on board, {moved} moved, "
          f"{sum(second['waiting'].values())} waiting")
    for name, ok in checks.items():
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
