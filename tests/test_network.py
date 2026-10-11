import pytest

from sim.config import load_network
from sim.network import Leg, Polyline, build_line, distance_m
from tests.conftest import MINI_YAML, make_stops


def calls(line):
    return [(v.stop.stop_id, v.direction, v.terminal, v.board_direction) for v in line.visits]


def test_distance_matches_haversine_at_city_scale():
    # Plaza de Castilla -> Atocha, ~6.5 km by haversine
    assert distance_m((40.4657, -3.6886), (40.4068, -3.6920)) == pytest.approx(6556, rel=0.005)


def test_polyline_interpolates_and_clamps():
    line = Polyline([(40.0, -3.0), (40.01, -3.0)])
    assert line.point_at(-5) == (40.0, -3.0)
    assert line.point_at(line.length + 5) == (40.01, -3.0)
    assert line.point_at(line.length / 2) == pytest.approx((40.005, -3.0))


def test_reversed_inbound_merges_terminal_calls():
    line = build_line("L", "L", make_stops(4))
    assert calls(line) == [
        ("S0", 1, True, 0),  # end of inbound = start of outbound, at offset 0
        ("S1", 0, False, 0), ("S2", 0, False, 0),
        ("S3", 0, True, 1),
        ("S2", 1, False, 1), ("S1", 1, False, 1),
    ]
    assert [v.remaining_in_leg for v in line.visits] == [1, 3, 2, 1, 3, 2]
    offsets = [v.offset_m for v in line.visits]
    assert offsets == sorted(offsets) and len(set(offsets)) == len(offsets)
    assert line.length == pytest.approx(2 * offsets[3])


def test_inbound_on_other_side_of_the_street_keeps_both_stops():
    lines, _, _ = load_network(MINI_YAML)
    b = lines["B"]
    assert [c[0] for c in calls(b)] == ["B1", "B2o", "C2", "B3", "C2", "B2i"]
    assert {s.stop_id for s in b.stops} == {"B1", "B2o", "C2", "B3", "B2i"}


def test_circular_line_has_one_terminal_and_one_direction():
    lines, _, _ = load_network(MINI_YAML)
    c = lines["C"]
    assert c.is_loop
    assert calls(c) == [("L1", 0, True, 0), ("L2", 0, False, 0), ("L3", 0, False, 0), ("L4", 0, False, 0)]
    assert c.position(0) == c.position(c.length)


def test_terminal_at_end_of_circuit_is_offset_zero_despite_float_rounding():
    """Summed segment lengths can overshoot the circuit length by 1 ulp; the terminal must still be found."""
    lines, _, _ = load_network(MINI_YAML)
    for line in lines.values():
        assert line.visits[0].offset_m == 0.0 and line.visits[0].terminal
        assert all(0 <= v.offset_m < line.length for v in line.visits)


def test_first_visit_from_includes_exact_offset():
    line = build_line("L", "L", make_stops(3))
    assert line.first_visit_from(0.0) == 0
    assert line.first_visit_from(1.0) == 1
    assert line.first_visit_from(line.length - 1) == 0  # wraps to the inbound terminus


def test_street_geometry_is_used_for_positions_and_offsets():
    stops = make_stops(2)
    detour = [(stops[0].lat, stops[0].lon), (40.445, -3.68), (stops[1].lat, stops[1].lon)]
    out = Leg(0, stops, detour, [0.0, Polyline(detour).length])
    line = build_line("L", "L", out)
    assert line.visits[1].offset_m == pytest.approx(Polyline(detour).length)
    assert line.position(Polyline(detour).cumulative[1]) == pytest.approx((40.445, -3.68))


def test_geometry_without_offsets_is_rejected():
    stops = make_stops(3)
    with pytest.raises(ValueError, match="one offset per stop"):
        build_line("L", "L", Leg(0, stops, [(s.lat, s.lon) for s in stops], None))
