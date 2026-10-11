"""The world: buses driving circuits and passengers queueing at stops, advanced in fixed ticks.

One ``World`` owns every bus and every queue, so a person who arrives at a stop is exactly
the person a bus later picks up. Each tick:

1. passengers arrive at every (stop, line, direction) queue (Poisson, time-of-day rate;
   a stop's rate is shared by all the queues at that stop);
2. each bus spends the tick's time budget driving, dwelling or laying over, possibly
   calling at several stops in one tick; calls alight then board passengers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
import random

from sim.demand import binomial, poisson, time_multiplier
from sim.network import Line, Visit

QueueKey = tuple[str, str, int]  # (stop_id, line_id, direction)


class BusState(StrEnum):
    DRIVING = "driving"
    DWELLING = "dwelling"


@dataclass(frozen=True)
class DwellModel:
    base_s: float = 10.0
    per_boarding_s: float = 2.0
    per_alighting_s: float = 1.0
    layover_s: float = 120.0  # minimum stand time at a terminal

    def dwell(self, boarded: int, alighted: int, terminal: bool) -> float:
        t = self.base_s + self.per_boarding_s * boarded + self.per_alighting_s * alighted
        return max(t, self.layover_s) if terminal else t


@dataclass
class Bus:
    bus_id: str
    line_id: str
    capacity: int
    offset_m: float
    next_visit: int
    passengers: int = 0
    state: BusState = BusState.DRIVING
    dwell_left_s: float = 0.0
    direction: int = 0


@dataclass(frozen=True)
class StopCall:
    time: datetime
    bus_id: str
    line_id: str
    stop_id: str
    direction: int
    terminal: bool
    lat: float
    lon: float
    alighted: int
    boarded: int
    passengers_after: int
    left_behind: int


@dataclass(frozen=True)
class BusSnapshot:
    bus_id: str
    line_id: str
    lat: float
    lon: float
    passengers: int
    capacity: int
    state: str
    direction: int
    next_stop_id: str
    distance_to_next_stop_m: float


@dataclass(frozen=True)
class TickResult:
    time: datetime
    buses: list[BusSnapshot]
    waiting: dict[str, int]  # stop_id -> people waiting, all lines and directions
    calls: list[StopCall]
    arrivals: int  # people who reached a stop this tick


@dataclass
class World:
    lines: dict[str, Line]
    buses: dict[str, Bus]
    clock: datetime
    rng: random.Random
    dwell: DwellModel = field(default_factory=DwellModel)
    demand_scale: float = 1.0
    queues: dict[QueueKey, int] = field(default_factory=dict)

    def __post_init__(self):
        # Only queues a bus actually loads from: a terminus has riders for the departing leg only.
        self._queue_rate: dict[QueueKey, float] = {}
        per_stop: dict[str, list[QueueKey]] = {}
        stops = {}
        for line in self.lines.values():
            for v in line.visits:
                key = (v.stop.stop_id, line.line_id, v.board_direction)
                if key not in self.queues:
                    self.queues[key] = 0
                if key not in per_stop.setdefault(v.stop.stop_id, []):
                    per_stop[v.stop.stop_id].append(key)
                stops[v.stop.stop_id] = v.stop
        for stop_id, keys in per_stop.items():
            for key in keys:
                self._queue_rate[key] = stops[stop_id].base_arrival_rate / len(keys)

    def step(self, dt_s: float) -> TickResult:
        if dt_s <= 0:
            raise ValueError(f"dt_s must be positive, got {dt_s}")
        arrivals = self._generate_arrivals(dt_s)
        calls: list[StopCall] = []
        for bus in self.buses.values():
            self._advance(bus, dt_s, calls)
        self.clock += timedelta(seconds=dt_s)
        return TickResult(self.clock, self.snapshots(), self.waiting_by_stop(), calls, arrivals)

    def _generate_arrivals(self, dt_s: float) -> int:
        factor = time_multiplier(self.clock.hour) * self.demand_scale * dt_s / 60
        total = 0
        for key, rate in self._queue_rate.items():
            n = poisson(self.rng, rate * factor)
            self.queues[key] += n
            total += n
        return total

    def _advance(self, bus: Bus, budget_s: float, calls: list[StopCall]) -> None:
        line = self.lines[bus.line_id]
        speed_ms = line.speed_kmh / 3.6
        elapsed_s = 0.0
        while elapsed_s < budget_s - 1e-9:
            left_s = budget_s - elapsed_s
            if bus.state is BusState.DWELLING:
                used = min(bus.dwell_left_s, left_s)
                bus.dwell_left_s -= used
                elapsed_s += used
                if bus.dwell_left_s <= 1e-9:
                    bus.state = BusState.DRIVING
                continue
            visit = line.visits[bus.next_visit]
            gap_m = line.distance_between(bus.offset_m, visit.offset_m)
            reach_s = gap_m / speed_ms
            if reach_s > left_s:
                bus.offset_m = (bus.offset_m + speed_ms * left_s) % line.length
                return
            elapsed_s += reach_s
            bus.offset_m = visit.offset_m
            bus.next_visit = (bus.next_visit + 1) % len(line.visits)
            calls.append(self._call(bus, line, visit, self.clock + timedelta(seconds=elapsed_s)))

    def _call(self, bus: Bus, line: Line, visit: Visit, at: datetime) -> StopCall:
        alighted = binomial(self.rng, bus.passengers, 1 / visit.remaining_in_leg)
        bus.passengers -= alighted
        # At a terminal the bus turns round and loads riders for the next leg.
        bus.direction = visit.board_direction
        key = (visit.stop.stop_id, line.line_id, bus.direction)
        boarded = min(self.queues[key], bus.capacity - bus.passengers)
        self.queues[key] -= boarded
        bus.passengers += boarded
        bus.state = BusState.DWELLING
        bus.dwell_left_s = self.dwell.dwell(boarded, alighted, visit.terminal)
        return StopCall(
            time=at,
            bus_id=bus.bus_id,
            line_id=line.line_id,
            stop_id=visit.stop.stop_id,
            direction=visit.direction,
            terminal=visit.terminal,
            lat=visit.stop.lat,
            lon=visit.stop.lon,
            alighted=alighted,
            boarded=boarded,
            passengers_after=bus.passengers,
            left_behind=self.queues[key],
        )

    def snapshots(self) -> list[BusSnapshot]:
        out = []
        for bus in self.buses.values():
            line = self.lines[bus.line_id]
            lat, lon = line.position(bus.offset_m)
            visit = line.visits[bus.next_visit]
            out.append(
                BusSnapshot(
                    bus.bus_id, bus.line_id, lat, lon, bus.passengers, bus.capacity,
                    bus.state.value, bus.direction, visit.stop.stop_id,
                    line.distance_between(bus.offset_m, visit.offset_m),
                )
            )
        return out

    def waiting_by_stop(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for (stop_id, _, _), n in self.queues.items():
            totals[stop_id] = totals.get(stop_id, 0) + n
        return totals

    # --- persistence: enough state to resume after a container restart -------------------

    def to_state(self) -> dict:
        return {
            "clock": self.clock.isoformat(),
            "buses": {
                b.bus_id: [round(b.offset_m, 2), b.next_visit, b.passengers, b.state.value,
                           round(b.dwell_left_s, 2), b.direction]
                for b in self.buses.values()
            },
            "queues": {"|".join(map(str, k)): n for k, n in self.queues.items() if n},
        }

    def restore(self, state: dict) -> None:
        """Apply a saved state; buses or queues no longer in the network are ignored."""
        for bus_id, (offset, nxt, pax, st, dwell, direction) in state.get("buses", {}).items():
            bus = self.buses.get(bus_id)
            if bus is None or nxt >= len(self.lines[bus.line_id].visits):
                continue
            bus.offset_m, bus.next_visit, bus.passengers = offset, nxt, min(pax, bus.capacity)
            bus.state, bus.dwell_left_s, bus.direction = BusState(st), dwell, direction
        for raw, n in state.get("queues", {}).items():
            stop_id, line_id, direction = raw.split("|")
            key = (stop_id, line_id, int(direction))
            if key in self.queues:
                self.queues[key] = n
