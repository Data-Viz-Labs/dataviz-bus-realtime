"""System-level invariants: run whole worlds for many ticks and check what must always hold.

They guard against the failure modes that matter for a transit simulation: buses running
empty, buses parked at a terminus, stops that are never served, people appearing or vanishing.
"""

from datetime import datetime
import random

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
import pytest
from sim.config import build_world
from sim.engine import Bus, World
from sim.network import Stop, build_line
from sim.report import Summary

from tests.conftest import LINES_YAML, MINI_YAML

TICK_S = 5.0


def run(world: World, hours: float):
    return [world.step(TICK_S) for _ in range(int(hours * 3600 / TICK_S))]


def check_invariants(world: World, results) -> None:
    boarded = sum(c.boarded for r in results for c in r.calls)
    alighted = sum(c.alighted for r in results for c in r.calls)
    on_board = sum(b.passengers for b in world.buses.values())
    assert boarded - alighted == on_board, "passengers created or lost"  # buses start empty

    arrived = sum(r.arrivals for r in results)
    assert arrived - boarded == sum(world.queues.values()), "people at stops created or lost"

    for r in results:
        for b in r.buses:
            assert 0 <= b.passengers <= b.capacity
        for c in r.calls:
            if c.terminal:
                assert c.passengers_after == c.boarded, "someone stayed on board at a terminal"
    assert all(n >= 0 for n in world.queues.values())


def check_every_bus_moves_and_every_stop_is_served(world: World, results) -> None:
    served = {c.stop_id for r in results for c in r.calls}
    all_stops = {s.stop_id for line in world.lines.values() for s in line.stops}
    assert served == all_stops
    called_by = {c.bus_id for r in results for c in r.calls}
    assert called_by == set(world.buses)


@pytest.mark.parametrize("hour", [7, 10, 23])
@pytest.mark.parametrize("seed", [1, 2])
def test_mixed_network_invariants(hour, seed):
    world = build_world(MINI_YAML, None, start=datetime(2026, 10, 12, hour), seed=seed)
    results = run(world, hours=1.5)
    check_invariants(world, results)
    check_every_bus_moves_and_every_stop_is_served(world, results)


@pytest.mark.parametrize("hour", [8])
def test_madrid_network_invariants(hour):
    world = build_world(LINES_YAML, None, start=datetime(2026, 10, 12, hour), seed=3)
    results = run(world, hours=2)
    check_invariants(world, results)
    check_every_bus_moves_and_every_stop_is_served(world, results)


def test_rush_hour_buses_actually_carry_people():
    """Buses must fill up at rush hour and stay loaded, not decay towards empty."""
    world = build_world(LINES_YAML, None, start=datetime(2026, 10, 12, 7), seed=7)
    summary = Summary(world)
    for r in run(world, hours=2):
        summary.add(r)
    assert 0.25 <= summary.mean_occupancy <= 0.85
    assert summary.healthy()
    # occupancy must not decay to zero late in the run either
    assert sum(b.passengers for b in run(world, hours=0.5)[-1].buses) > 0


@st.composite
def random_world(draw):
    n_stops = draw(st.integers(2, 8))
    lat0, lon0 = 40.40, -3.70
    stops = [
        Stop(
            f"S{i}", f"S{i}",
            lat0 + draw(st.floats(-0.03, 0.03)), lon0 + draw(st.floats(-0.03, 0.03)),
            draw(st.floats(0.0, 6.0)),
        )
        for i in range(n_stops)
    ]
    # Distinct stop coordinates; co-located stops are a config error, not a sim case.
    if len({(s.lat, s.lon) for s in stops}) < n_stops:
        stops = [Stop(s.stop_id, s.name, s.lat + i * 1e-3, s.lon, s.base_arrival_rate) for i, s in enumerate(stops)]
    line = build_line("L", "L", stops, speed_kmh=draw(st.floats(10, 60)))
    n_buses = draw(st.integers(1, 4))
    buses = {
        f"B{i}": Bus(f"B{i}", "L", draw(st.integers(1, 100)), offset, line.first_visit_from(offset))
        for i in range(n_buses)
        for offset in [draw(st.floats(0, line.length, exclude_max=True))]
    }
    hour = draw(st.integers(0, 23))
    return World({"L": line}, buses, datetime(2026, 10, 12, hour), random.Random(draw(st.integers(0, 2**16))))


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(random_world())
def test_random_networks_keep_invariants(world):
    line = world.lines["L"]
    circuit_s = line.length / (line.speed_kmh / 3.6) + world.dwell.layover_s * 2 + 60 * len(line.visits)
    results = [world.step(TICK_S) for _ in range(int(2 * circuit_s / TICK_S) + 1)]
    check_invariants(world, results)
    check_every_bus_moves_and_every_stop_is_served(world, results)
