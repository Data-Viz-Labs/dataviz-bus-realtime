"""Road network: each line is a closed circuit (outbound leg + inbound leg) measured in metres.

Positions are absolute metres along the circuit, never normalised fractions, and stops are
identified by their index in ``Line.visits``. Arrival detection therefore compares indices,
not floats. A circular line has a single leg that ends where it started.
"""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from itertools import pairwise
import math

EARTH_RADIUS_M = 6_371_000.0
CLOSE_M = 0.5  # a stop this close to the end of the circuit is at its start

LatLon = tuple[float, float]


def distance_m(a: LatLon, b: LatLon) -> float:
    """Equirectangular distance; accurate to <0.1% at city scale and cheap to invert."""
    mean_lat = math.radians((a[0] + b[0]) / 2)
    dx = math.radians(b[1] - a[1]) * math.cos(mean_lat)
    dy = math.radians(b[0] - a[0])
    return EARTH_RADIUS_M * math.hypot(dx, dy)


@dataclass(frozen=True)
class Stop:
    stop_id: str
    name: str
    lat: float
    lon: float
    base_arrival_rate: float  # people per minute, all lines and directions combined


@dataclass(frozen=True)
class Visit:
    """One scheduled call at a stop along the circuit."""

    stop: Stop
    offset_m: float
    direction: int  # leg the bus is finishing or travelling on: 0 outbound, 1 inbound
    terminal: bool  # end of a leg: everyone alights, then the bus lays over
    board_direction: int  # riders picked up here travel on this leg
    remaining_in_leg: int  # calls left in this leg including this one (1 at a terminal)


@dataclass(frozen=True)
class Leg:
    direction: int
    stops: list[Stop]
    geometry: list[LatLon] | None = None  # street polyline; defaults to straight stop-to-stop
    offsets: list[float] | None = None  # distance of each stop along ``geometry``


class Polyline:
    def __init__(self, points: list[LatLon]):
        if len(points) < 2:
            raise ValueError("a polyline needs at least 2 points")
        self.points = points
        self.cumulative = [0.0]
        for a, b in pairwise(points):
            self.cumulative.append(self.cumulative[-1] + distance_m(a, b))

    @property
    def length(self) -> float:
        return self.cumulative[-1]

    def point_at(self, offset_m: float) -> LatLon:
        offset_m = min(max(offset_m, 0.0), self.length)
        i = min(bisect_right(self.cumulative, offset_m) - 1, len(self.points) - 2)
        seg = self.cumulative[i + 1] - self.cumulative[i]
        f = 0.0 if seg == 0 else (offset_m - self.cumulative[i]) / seg
        (lat1, lon1), (lat2, lon2) = self.points[i], self.points[i + 1]
        return (lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f)


@dataclass
class Line:
    line_id: str
    name: str
    legs: list[Leg]
    path: Polyline  # full circuit, ending where it started
    visits: list[Visit]  # sorted by offset_m
    speed_kmh: float = 30.0
    color: str | None = None

    @property
    def length(self) -> float:
        return self.path.length

    @property
    def stops(self) -> list[Stop]:
        """Distinct stops served by the line, in circuit order."""
        seen: dict[str, Stop] = {}
        for leg in self.legs:
            for s in leg.stops:
                seen.setdefault(s.stop_id, s)
        return list(seen.values())

    @property
    def is_loop(self) -> bool:
        return len(self.legs) == 1

    def position(self, offset_m: float) -> LatLon:
        return self.path.point_at(offset_m % self.length)

    def distance_between(self, from_m: float, to_m: float) -> float:
        """Forward distance along the circuit, in [0, length)."""
        return (to_m - from_m) % self.length

    def first_visit_from(self, offset_m: float) -> int:
        """Index of the first visit at or ahead of ``offset_m`` (wrapping)."""
        offsets = [v.offset_m for v in self.visits]
        return bisect_left(offsets, offset_m % self.length) % len(self.visits)


def build_line(
    line_id: str,
    name: str,
    outbound: Leg | list[Stop],
    inbound: Leg | list[Stop] | None = None,
    speed_kmh: float = 30.0,
    color: str | None = None,
) -> Line:
    """Build a circuit from its legs.

    ``inbound=None`` means "the outbound stops in reverse"; an empty inbound list means a
    circular line, whose single leg is closed back to its first stop. When a leg starts at
    the stop where the previous leg ended, both are one call: alight everyone, then board.
    """
    out = outbound if isinstance(outbound, Leg) else Leg(0, outbound)
    if len(out.stops) < 2:
        raise ValueError(f"line {line_id} needs at least 2 stops")
    back = Leg(1, out.stops[::-1]) if inbound is None else inbound if isinstance(inbound, Leg) else Leg(1, inbound)
    if back.stops:
        legs = [out, back]
    else:
        first = out.stops[0]
        if out.stops[-1].stop_id == first.stop_id:
            stops = out.stops
            geometry, offsets = out.geometry, out.offsets
        else:
            stops = [*out.stops, first]
            geometry, offsets = out.geometry, out.offsets
            if geometry and offsets and len(offsets) == len(out.stops):  # not yet closed: go straight home
                geometry = [*geometry, (first.lat, first.lon)]
                offsets = [*offsets, Polyline(geometry).length]
        legs = [Leg(0, stops, geometry, offsets)]

    points: list[LatLon] = []
    visits: list[Visit] = []
    for k, leg in enumerate(legs):
        geometry = leg.geometry or [(s.lat, s.lon) for s in leg.stops]
        offsets = leg.offsets if leg.offsets is not None else None if leg.geometry else Polyline(geometry).cumulative
        if offsets is None or len(offsets) != len(leg.stops):
            raise ValueError(f"line {line_id}: one offset per stop is required in each direction")
        start = Polyline([*points, geometry[0]]).length if points else 0.0
        points.extend(geometry)
        prev_leg = legs[k - 1]
        next_dir = legs[(k + 1) % len(legs)].direction
        n = len(leg.stops)
        for i, stop in enumerate(leg.stops):
            if i == 0 and prev_leg.stops[-1].stop_id == stop.stop_id:
                continue  # merged into the previous leg's terminal call
            terminal = i == n - 1
            visits.append(Visit(
                stop, start + offsets[i], leg.direction, terminal,
                board_direction=next_dir if terminal else leg.direction,
                remaining_in_leg=n - i,
            ))
    path = Polyline(points + [points[0]] if points[-1] != points[0] else points)
    # The final terminal sits at the end of the circuit, which is offset 0. Rounded street
    # geometry can leave it a few centimetres short of the end, hence the tolerance.
    visits = [
        Visit(v.stop, 0.0 if v.offset_m >= path.length - CLOSE_M else v.offset_m,
              v.direction, v.terminal, v.board_direction, v.remaining_in_leg)
        for v in visits
    ]
    visits.sort(key=lambda v: (v.offset_m, not v.terminal))
    return Line(line_id, name, legs, path, visits, speed_kmh, color)
