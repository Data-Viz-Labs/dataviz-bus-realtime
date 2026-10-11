import random

import pytest

from sim.config import build_world
from sim.demand import binomial, poisson, time_multiplier
from sim.engine import Bus, BusState
from tests.conftest import MINI_YAML, make_world


def test_bus_parked_on_a_terminal_calls_there_immediately():
    world = make_world()
    world.queues[("S0", "L", 0)] = 7
    result = world.step(1)
    assert [(c.stop_id, c.terminal, c.boarded) for c in result.calls] == [("S0", True, 7)]
    assert world.buses["B1"].direction == 0


def test_several_stops_in_one_tick_are_called_in_order_with_dwell():
    world = make_world()
    world.dwell = world.dwell.__class__(base_s=0, per_boarding_s=0, per_alighting_s=0, layover_s=0)
    result = world.step(3600)  # far longer than a full circuit at 30 km/h
    stops = [c.stop_id for c in result.calls]
    assert stops[:7] == ["S0", "S1", "S2", "S3", "S2", "S1", "S0"]
    times = [c.time for c in result.calls]
    assert times == sorted(times)


def test_dwell_consumes_time_and_residual_is_used_for_driving():
    world = make_world()
    bus = world.buses["B1"]
    world.step(60)  # 120 s layover at S0 still running
    assert bus.state is BusState.DWELLING and bus.offset_m == 0
    world.step(70)  # 60 s left of layover, then 10 s of driving at 30 km/h
    assert bus.state is BusState.DRIVING
    assert bus.offset_m == pytest.approx(10 * 30 / 3.6)


def test_terminal_empties_bus_and_loads_the_other_direction():
    world = make_world()
    line = world.lines["L"]
    terminus = line.visits[3]
    bus = world.buses["B1"]
    bus.offset_m, bus.next_visit, bus.passengers, bus.direction = terminus.offset_m - 1, 3, 30, 0
    world.queues[("S3", "L", 1)] = 5
    assert ("S3", "L", 0) not in world.queues  # nobody can ride outbound past the end
    call = world.step(1).calls[0]
    assert (call.stop_id, call.alighted, call.boarded, call.passengers_after) == ("S3", 30, 5, 5)
    assert bus.direction == 1


def test_boarding_never_exceeds_capacity_and_leaves_the_rest_waiting():
    world = make_world(buses=[Bus("B1", "L", 10, 0.0, 0)])
    world.queues[("S0", "L", 0)] = 25
    call = world.step(1).calls[0]
    assert (call.boarded, call.left_behind) == (10, 15)


def test_terminals_only_get_riders_for_the_departing_direction():
    world = make_world(rate=50)
    world.step(60)
    assert set(world.queues) == {
        ("S0", "L", 0), ("S1", "L", 0), ("S2", "L", 0), ("S3", "L", 1), ("S2", "L", 1), ("S1", "L", 1),
    }
    assert all(n > 0 for n in world.queues.values())


def test_shared_stop_rate_is_split_between_lines(mini_world):
    # C2 (2/min) is served by A and B in both directions: four queues of 0.5/min each.
    shared = {k: r for k, r in mini_world._queue_rate.items() if k[0] == "C2"}
    assert len(shared) == 4 and all(r == 0.5 for r in shared.values())


def test_state_round_trip_resumes_the_same_world(mini_world):
    for _ in range(100):
        mini_world.step(5)
    state = mini_world.to_state()
    clone = build_world(MINI_YAML, None, start=mini_world.clock, seed=1)
    clone.restore(state)
    assert clone.to_state() == state


def test_step_rejects_non_positive_dt():
    with pytest.raises(ValueError):
        make_world().step(0)


@pytest.mark.parametrize(
    "hour, expected",
    [(0, 0.2), (5, 0.2), (6, 1.5), (9, 0.6), (12, 1.2), (15, 0.8), (18, 1.4), (21, 0.2), (23, 0.2)],
)
def test_time_multiplier_profile(hour, expected):
    assert time_multiplier(hour) == expected


def test_poisson_mean_is_lambda_for_small_and_large_lambda():
    rng = random.Random(1)
    for lam in (0.5, 4.0, 80.0):
        mean = sum(poisson(rng, lam) for _ in range(4000)) / 4000
        assert mean == pytest.approx(lam, rel=0.08)


def test_binomial_edges():
    rng = random.Random(1)
    assert binomial(rng, 12, 1.0) == 12
    assert binomial(rng, 12, 0.0) == 0
