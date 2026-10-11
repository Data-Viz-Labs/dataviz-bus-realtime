"""Snap every line to real streets with Amazon Location Routes and write data/network.json.

For each line and direction, the stops are sent as waypoints to geo-routes CalculateRoutes
(TravelMode=Car, Simple geometry). Each returned leg runs from one stop to the next, so the
stop offsets are the cumulative leg lengths. Segments the router cannot match sensibly
(longer than MAX_DETOUR x the straight distance) fall back to a straight line.

    python bin/build_network.py [--lines data/lines.yaml] [--out data/network.json] [--only 27,C1]

Needs AWS credentials with geo-routes:CalculateRoutes. Run it again only when lines.yaml
changes; the simulator works without network.json (straight stop-to-stop segments).
"""

import argparse
import json
from pathlib import Path
import sys

import boto3
from sim.config import load_network
from sim.network import Polyline, Stop, distance_m

MAX_POSITIONS = 25  # origin + waypoints + destination per request
MAX_DETOUR = 3.0


def route_segments(client, stops: list[Stop]) -> list[list[tuple[float, float]]]:
    """Street geometry between each pair of consecutive stops, as (lat, lon) lists."""
    segments: list[list[tuple[float, float]]] = []
    start = 0
    while start < len(stops) - 1:
        window = stops[start:start + MAX_POSITIONS]
        resp = client.calculate_routes(
            Origin=[window[0].lon, window[0].lat],
            Destination=[window[-1].lon, window[-1].lat],
            Waypoints=[{"Position": [s.lon, s.lat]} for s in window[1:-1]],
            TravelMode="Car",
            LegGeometryFormat="Simple",
        )
        legs = resp["Routes"][0]["Legs"] if resp.get("Routes") else []
        for i, (a, b) in enumerate(zip(window, window[1:], strict=False)):
            straight = [(a.lat, a.lon), (b.lat, b.lon)]
            line = legs[i]["Geometry"].get("LineString") if i < len(legs) else None
            if line and len(line) >= 2:
                points = [straight[0], *[(lat, lon) for lon, lat in line], straight[1]]
                if Polyline(points).length <= MAX_DETOUR * max(distance_m(*straight), 50.0):
                    segments.append(points)
                    continue
            segments.append(straight)
        start += len(window) - 1
    return segments


def leg_geometry(client, stops: list[Stop]) -> dict:
    points: list[tuple[float, float]] = []
    offsets = [0.0]
    for seg in route_segments(client, stops):
        seg = [(round(lat, 6), round(lon, 6)) for lat, lon in seg]  # offsets must match the stored points
        points = points + seg[1:] if points else seg
        offsets.append(Polyline(points).length)
    return {"geometry": [list(p) for p in points], "offsets": offsets}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--lines", default="data/lines.yaml")
    p.add_argument("--out", default="data/network.json")
    p.add_argument("--only", help="comma-separated line ids to (re)build; others are kept from --out")
    args = p.parse_args(argv)

    only = {x.strip() for x in args.only.split(",")} if args.only else None
    lines, _, _ = load_network(args.lines, None, only)
    out = Path(args.out)
    network = json.loads(out.read_text()) if only and out.exists() else {}
    client = boto3.client("geo-routes")
    for line_id, line in lines.items():
        network[line_id] = {
            ("outbound" if leg.direction == 0 else "inbound"): leg_geometry(client, leg.stops)
            for leg in line.legs
        }
        print(f"{line_id:>5}  {line.name}: {sum(len(v['geometry']) for v in network[line_id].values())} points")
    out.write_text(json.dumps(network, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
