"""Build data/lines.yaml for the bus simulator from the official EMT Madrid GTFS feed.

Source: https://servicios.emtmadrid.es:8443/gtfs/transitemt.zip
        (EMT Madrid open data, https://opendata.emtmadrid.es)

Per selected line and direction (direction_id 0 -> outbound, 1 -> inbound) the most
common stop pattern on a regular weekday (--date, default a Wednesday) is used.

Formulas:
  base_arrival_rate = round(0.35 * n_selected_lines_at_stop * (1.5 if terminal else 1.0), 2)
  speed_kmh  = pattern distance / (median 08-09 runtime - 20 s * intermediate stops),
               both directions combined, clamped to [12, 30]. Distance is the GTFS
               shape_dist_traveled when consistent with haversine, else haversine.
  headway    = 60 / trips departing in direction 0 between 08:00 and 09:00
  buses      = ceil((runtime_out + runtime_in + 2*4 min) / headway), clamped to [2, 25]
  capacity   = 150 if the route name/desc says articulated, else 90.
A pattern whose first and last stop are < 300 m apart is a loop: inbound = [].

Usage: python3 tools/import_gtfs.py --gtfs transitemt.zip --out data/lines.yaml --lines 1,2,27,...
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import io
import json
import math
import os
import re
import statistics
import zipfile

SOURCE = "https://servicios.emtmadrid.es:8443/gtfs/transitemt.zip"
LAYOVER_MIN, DWELL_S, LOOP_M = 4, 20, 300


def open_table(gtfs, name):
    if os.path.isdir(gtfs):
        return open(os.path.join(gtfs, name), encoding="utf-8-sig", newline="")
    return io.TextIOWrapper(zipfile.ZipFile(gtfs).open(name), encoding="utf-8-sig", newline="")


def rows(gtfs, name):
    with open_table(gtfs, name) as f:
        yield from csv.DictReader(f)


def secs(t):
    h, m, s = (int(x) for x in t.strip().split(":"))
    return h * 3600 + m * 60 + s


def haversine(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2, dl = math.radians(la1), math.radians(la2), math.radians(lo2 - lo1)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def active_services(gtfs, day):
    ds, wd = day.strftime("%Y%m%d"), day.strftime("%A").lower()
    on = {r["service_id"] for r in rows(gtfs, "calendar.txt")
          if r[wd] == "1" and r["start_date"] <= ds <= r["end_date"]}
    for r in rows(gtfs, "calendar_dates.txt"):
        if r["date"] == ds:
            (on.add if r["exception_type"] == "1" else on.discard)(r["service_id"])
    return on


def clean_name(s):
    s = re.sub(r"\s*-\s*$", "", s.strip())
    s = re.sub(r"[/|](\w)", lambda m: "/" + m.group(1).upper(), s)
    return s[:1].upper() + s[1:]


def sort_key(line_id):
    m = re.match(r"(\d+)(.*)", line_id)
    return (0, int(m.group(1)), m.group(2)) if m else (1, 0, line_id)


def load(gtfs, wanted, day):
    routes = {r["route_id"]: r for r in rows(gtfs, "routes.txt") if r["route_short_name"] in wanted}
    services = active_services(gtfs, day)
    trips = {t["trip_id"]: (t["route_id"], int(t["direction_id"])) for t in rows(gtfs, "trips.txt")
             if t["route_id"] in routes and t["service_id"] in services}
    st = defaultdict(list)
    for r in rows(gtfs, "stop_times.txt"):
        if r["trip_id"] in trips:
            st[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"], secs(r["arrival_time"]),
                                     secs(r["departure_time"]), float(r["shape_dist_traveled"] or 0)))
    stops = {s["stop_id"]: s for s in rows(gtfs, "stops.txt")}
    return routes, trips, st, stops


def build_direction(trip_ids, st, coords):
    """Return pattern, runtime (s), distance (m), trips 08-09 for one route direction."""
    if not trip_ids:
        return None
    seqs = {t: sorted(st[t]) for t in trip_ids if st[t]}
    pattern = Counter(tuple(x[1] for x in s) for s in seqs.values()).most_common(1)[0][0]
    same = [s for s in seqs.values() if tuple(x[1] for x in s) == pattern]
    peak = [s for s in same if 8 * 3600 <= s[0][3] < 9 * 3600] or same
    runtime = statistics.median(s[-1][2] - s[0][3] for s in peak)
    hav = sum(haversine(coords[a], coords[b]) for a, b in zip(pattern, pattern[1:], strict=False))
    sd = same[0][-1][4] - same[0][0][4]
    dist = sd if hav and 1.0 <= sd / hav <= 1.8 else hav
    n_peak = sum(1 for s in seqs.values() if 8 * 3600 <= s[0][3] < 9 * 3600)
    return {"pattern": list(pattern), "runtime": runtime, "dist": dist, "peak_trips": n_peak}


def build(gtfs, wanted, day):
    routes, trips, st, stops = load(gtfs, wanted, day)
    coords = {k: (float(s["stop_lat"]), float(s["stop_lon"])) for k, s in stops.items()}
    by_dir = defaultdict(list)
    for tid, key in trips.items():
        by_dir[key].append(tid)
    lines, dropped = [], {}
    for rid, r in routes.items():
        lid = r["route_short_name"]
        out, inb = (build_direction(by_dir[(rid, d)], st, coords) for d in (0, 1))
        if not out or out["peak_trips"] == 0 or len(out["pattern"]) < 2:
            dropped[lid] = "no weekday 08-09 service in direction 0"
            continue
        loop = haversine(coords[out["pattern"][0]], coords[out["pattern"][-1]]) < LOOP_M
        dirs = [out] if loop or not inb else [out, inb]
        moving = sum(d["runtime"] - DWELL_S * (len(d["pattern"]) - 2) for d in dirs)
        speed = min(30.0, max(12.0, sum(d["dist"] for d in dirs) / moving * 3.6))
        headway = 60 / out["peak_trips"]
        cycle = sum(d["runtime"] for d in dirs) / 60 + 2 * LAYOVER_MIN
        art = re.search(r"articulad", (r["route_long_name"] + r.get("route_desc", "")), re.I)
        lines.append({
            "line_id": lid, "name": clean_name(r["route_long_name"]),
            "color": "#" + r["route_color"].lower() if r.get("route_color") else None,
            "speed_kmh": round(speed, 1), "outbound": out["pattern"],
            "inbound": [] if loop or not inb else inb["pattern"], "loop": loop,
            "circular": r["route_long_name"].lower().startswith("circular"),
            "count": min(25, max(2, math.ceil(cycle / headway))), "capacity": 150 if art else 90,
            "peak_trips": out["peak_trips"],
            "terminal_gap_m": None if loop or not inb else round(max(
                haversine(coords[out["pattern"][-1]], coords[inb["pattern"][0]]),
                haversine(coords[inb["pattern"][-1]], coords[out["pattern"][0]]))),
        })
    for lid in wanted - {ln["line_id"] for ln in lines} - set(dropped):
        dropped[lid] = "not in feed / no service on date"
    lines.sort(key=lambda ln: sort_key(ln["line_id"]))
    return lines, dropped, stops


def code(stops, sid):
    return stops[sid].get("stop_code") or sid


def write_yaml(path, lines, stops, feed_date, demand_scale):
    serving, terminals = defaultdict(set), set()
    for ln in lines:
        for d in ("outbound", "inbound"):
            for s in ln[d]:
                serving[s].add(ln["line_id"])
            if ln[d]:
                terminals.update((ln[d][0], ln[d][-1]))
    q = json.dumps
    out = [f"# Source: {SOURCE}  (EMT Madrid GTFS, feed date {feed_date}). Generated by tools/import_gtfs.py",
           "# demand_scale is calibrated so rush-hour mean occupancy is ~30% (python -m sim --start 07:30).",
           f"demand_scale: {demand_scale}",
           "stops:"]
    for sid in sorted(serving, key=lambda s: (len(code(stops, s)), code(stops, s))):
        s = stops[sid]
        rate = round(0.35 * len(serving[sid]) * (1.5 if sid in terminals else 1.0), 2)
        out += [f"  {q(code(stops, sid))}:", f"    name: {q(s['stop_name'].strip(), ensure_ascii=False)}",
                f"    lat: {float(s['stop_lat']):.5f}", f"    lon: {float(s['stop_lon']):.5f}",
                f"    base_arrival_rate: {rate}"]
    out.append("lines:")
    for ln in lines:
        def codes(p):
            return "[" + ", ".join(q(code(stops, s)) for s in p) + "]"
        out.append(f"  - line_id: {q(ln['line_id'])}")
        out.append(f"    name: {q(ln['name'], ensure_ascii=False)}")
        if ln["color"]:
            out.append(f"    color: {q(ln['color'])}")
        out.append(f"    speed_kmh: {ln['speed_kmh']}")
        out.append(f"    outbound: {codes(ln['outbound'])}")
        note = ("  # circular line: outbound pattern is a closed loop" if ln["loop"] else
                "  # circular line: GTFS splits the loop into two halves" if ln["circular"] else "")
        out.append(f"    inbound: {codes(ln['inbound'])}{note}")
        out.append(f"    buses: {{count: {ln['count']}, capacity: {ln['capacity']}}}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gtfs", required=True, help="GTFS zip or extracted directory")
    ap.add_argument("--out", default="data/lines.yaml")
    ap.add_argument("--lines", required=True, help="comma-separated route_short_name list")
    ap.add_argument("--date", default="2026-10-14", help="regular weekday YYYY-MM-DD")
    ap.add_argument("--demand-scale", type=float, default=1.3, help="global multiplier on arrival rates")
    a = ap.parse_args()
    wanted = {x.strip() for x in a.lines.split(",") if x.strip()}
    lines, dropped, stops = build(a.gtfs, wanted, date.fromisoformat(a.date))
    starts = [r["start_date"] for r in rows(a.gtfs, "calendar.txt")]
    m = min(starts)  # no feed_info.txt: use earliest calendar start_date
    feed_date = date(int(m[:4]), int(m[4:6]), int(m[6:]))
    write_yaml(a.out, lines, stops, feed_date.isoformat(), a.demand_scale)
    for ln in lines:
        gap = ln["terminal_gap_m"]
        print(f"{ln['line_id']:>4} {ln['peak_trips']:>3} trips/h  {ln['speed_kmh']:>4} km/h  buses {ln['count']:>2}"
              f"  stops {len(ln['outbound'])}/{len(ln['inbound'])}  gap {gap}m  {ln['name']}")
    for lid, why in sorted(dropped.items()):
        print(f"DROPPED {lid}: {why}")


if __name__ == "__main__":
    main()
