import json

import pytest
from sim.config import ConfigError, build_world, load_network

from tests.conftest import MINI_YAML

BASE = """
stops:
  A: {name: A, lat: 40.40, lon: -3.70, base_arrival_rate: 1}
  B: {name: B, lat: 40.41, lon: -3.70, base_arrival_rate: 1}
lines:
  - line_id: "L"
    name: Test
    outbound: %s
    buses: {count: 4, capacity: 50}
"""


def write(tmp_path, text):
    path = tmp_path / "lines.yaml"
    path.write_text(text)
    return path


def test_fleet_is_spread_evenly_around_each_circuit(mini_world):
    assert len(mini_world.buses) == 7
    a = sorted(b.offset_m for b in mini_world.buses.values() if b.line_id == "A")
    length = mini_world.lines["A"].length
    assert a == pytest.approx([0, length / 3, 2 * length / 3])
    assert set(mini_world.buses) >= {"A-01", "A-02", "A-03", "C-02"}


def test_only_lines_filters_network():
    world = build_world(MINI_YAML, None, only_lines={"C"})
    assert set(world.lines) == {"C"} and {b.line_id for b in world.buses.values()} == {"C"}
    with pytest.raises(ConfigError, match="unknown lines"):
        build_world(MINI_YAML, None, only_lines={"C", "nope"})


def test_unknown_stop_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="unknown stops"):
        load_network(write(tmp_path, BASE % '["A", "Z"]'))


def test_missing_sections_are_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_network(write(tmp_path, "lines: []\n"))


def test_network_geometry_overrides_straight_segments(tmp_path):
    cfg = write(tmp_path, BASE % '["A", "B"]')
    detour = [[40.40, -3.70], [40.405, -3.69], [40.41, -3.70]]
    network = tmp_path / "network.json"
    network.write_text(json.dumps({"L": {
        "outbound": {"geometry": detour, "offsets": [0.0, 1700.0]},
        "inbound": {"geometry": detour[::-1], "offsets": [0.0, 1700.0]},
    }}))
    straight, _, _ = load_network(cfg)
    curved, _, _ = load_network(cfg, network)
    assert curved["L"].length > straight["L"].length
    assert curved["L"].visits[1].offset_m == 1700.0


def test_demand_scale_is_read(tmp_path):
    world = build_world(write(tmp_path, "demand_scale: 0.5\n" + BASE % '["A", "B"]'), None)
    assert world.demand_scale == 0.5
