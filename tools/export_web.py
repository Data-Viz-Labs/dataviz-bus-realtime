"""Write web/network.json: the static part of the map (line paths, stops, fleet capacity).

    python tools/export_web.py [--lines data/lines.yaml] [--network data/network.json] [--out web/network.json]
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sim.config import load_network  # noqa: E402


def export(lines_path: str, network_path: str | None) -> dict:
    lines, entries, _ = load_network(lines_path, network_path)
    stops = {}
    out_lines = {}
    for line_id, line in lines.items():
        out_lines[line_id] = {
            "name": line.name,
            "color": line.color,
            "capacity": int((entries[line_id].get("buses") or {}).get("capacity", 90)),
            "path": [[round(lon, 5), round(lat, 5)] for lat, lon in line.path.points],
        }
        for s in line.stops:
            stops.setdefault(s.stop_id, {"name": s.name, "lon": s.lon, "lat": s.lat, "lines": []})
            stops[s.stop_id]["lines"].append(line_id)
    return {"lines": out_lines, "stops": stops}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--lines", default="data/lines.yaml")
    p.add_argument("--network", default="data/network.json")
    p.add_argument("--out", default="web/network.json")
    args = p.parse_args(argv)
    Path(args.out).write_text(json.dumps(export(args.lines, args.network), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
