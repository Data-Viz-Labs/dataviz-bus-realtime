"""Load ``lines.yaml`` (+ optional ``network.json`` street geometry) into a ``World``.

``lines.yaml``::

    demand_scale: 1.0                  # optional global multiplier on arrival rates
    stops:
      "72": {name: Cibeles, lat: 40.4198, lon: -3.6935, base_arrival_rate: 1.2}
    lines:
      - line_id: "27"
        name: Embajadores - Plaza de Castilla
        color: "#1d6bb3"               # optional
        speed_kmh: 19.5                # cruising speed; dwell time is simulated separately
        outbound: ["1234", "5678"]
        inbound: ["5679", "1235"]      # [] for a circular line
        buses: {count: 14, capacity: 90}

``network.json`` (written by ``bin/build_network.py``)::

    {"27": {"outbound": {"geometry": [[lat, lon], ...], "offsets": [m per stop]}, "inbound": {...}}}
"""

from datetime import datetime
import json
from pathlib import Path
import random

import yaml

from sim.engine import Bus, World
from sim.network import Leg, Line, Stop, build_line


class ConfigError(ValueError):
    pass


def _leg(direction: int, ids: list, stops: dict[str, Stop], geo: dict | None, line_id: str) -> Leg:
    missing = [str(i) for i in ids if str(i) not in stops]
    if missing:
        raise ConfigError(f"line {line_id}: unknown stops {missing}")
    geometry = [tuple(p) for p in geo["geometry"]] if geo else None
    return Leg(direction, [stops[str(i)] for i in ids], geometry, geo.get("offsets") if geo else None)


def load_network(
    lines_path: str | Path,
    network_path: str | Path | None = None,
    only_lines: set[str] | None = None,
) -> tuple[dict[str, Line], dict, float]:
    """Return (lines by id, raw line entries by id, demand_scale)."""
    raw = yaml.safe_load(Path(lines_path).read_text()) or {}
    if not raw.get("lines") or not raw.get("stops"):
        raise ConfigError(f"{lines_path}: 'stops' and 'lines' are required")
    network_file = Path(network_path) if network_path else None
    geometry = json.loads(network_file.read_text()) if network_file and network_file.exists() else {}

    try:
        stops = {
            str(sid): Stop(str(sid), s["name"], float(s["lat"]), float(s["lon"]), float(s["base_arrival_rate"]))
            for sid, s in raw["stops"].items()
        }
    except (KeyError, TypeError, ValueError) as e:
        raise ConfigError(f"{lines_path}: invalid stop: {e!r}") from e

    lines: dict[str, Line] = {}
    entries: dict[str, dict] = {}
    for entry in raw["lines"]:
        line_id = str(entry.get("line_id", ""))
        if not line_id or "outbound" not in entry:
            raise ConfigError(f"{lines_path}: every line needs line_id and outbound")
        if only_lines and line_id not in only_lines:
            continue
        if line_id in lines:
            raise ConfigError(f"duplicate line_id {line_id}")
        geo = geometry.get(line_id, {})
        inbound = entry.get("inbound")
        try:
            lines[line_id] = build_line(
                line_id,
                entry.get("name", line_id),
                _leg(0, entry["outbound"], stops, geo.get("outbound"), line_id),
                None if inbound is None else _leg(1, inbound, stops, geo.get("inbound") if inbound else None, line_id),
                speed_kmh=float(entry.get("speed_kmh", 20.0)),
                color=entry.get("color"),
            )
        except ValueError as e:
            raise ConfigError(str(e)) from e
        entries[line_id] = entry
    if only_lines and (unknown := only_lines - set(lines)):
        raise ConfigError(f"unknown lines requested: {sorted(unknown)}")
    return lines, entries, float(raw.get("demand_scale", 1.0))


def build_world(
    lines_path: str | Path,
    network_path: str | Path | None = None,
    start: datetime | None = None,
    seed: int | None = None,
    only_lines: set[str] | None = None,
) -> World:
    lines, entries, demand_scale = load_network(lines_path, network_path, only_lines)
    buses: dict[str, Bus] = {}
    for line_id, entry in entries.items():
        line = lines[line_id]
        fleet = entry.get("buses") or {}
        count, capacity = int(fleet.get("count", 1)), int(fleet.get("capacity", 90))
        if count < 1 or capacity < 1:
            raise ConfigError(f"line {line_id}: buses.count and buses.capacity must be positive")
        for n in range(count):
            # Evenly spaced around the circuit, so headways start regular.
            offset = line.length * n / count
            nxt = line.first_visit_from(offset)
            bus_id = f"{line_id}-{n + 1:02d}"
            buses[bus_id] = Bus(bus_id, line_id, capacity, offset, nxt, direction=line.visits[nxt].direction)
    return World(
        lines, buses, start or datetime.now().replace(microsecond=0), random.Random(seed),
        demand_scale=demand_scale,
    )
