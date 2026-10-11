from datetime import datetime
from pathlib import Path
import random

import pytest

from sim.config import build_world
from sim.engine import Bus, World
from sim.network import Stop, build_line

REPO = Path(__file__).resolve().parents[1]
LINES_YAML = REPO / "data" / "lines.yaml"
MINI_YAML = Path(__file__).parent / "fixtures" / "mini.yaml"
RUSH_HOUR = datetime(2026, 10, 12, 8, 0)


def make_stops(n: int = 4, rate: float = 1.0) -> list[Stop]:
    # ~1.1 km apart going south through Madrid
    return [Stop(f"S{i}", f"Stop {i}", 40.45 - 0.01 * i, -3.69, rate) for i in range(n)]


def make_world(stops=None, buses=None, rate=1.0, seed=0, clock=RUSH_HOUR) -> World:
    line = build_line("L", "Test line", stops or make_stops(rate=rate))
    buses = buses or [Bus("B1", "L", 50, 0.0, 0)]
    return World({"L": line}, {b.bus_id: b for b in buses}, clock, random.Random(seed))


@pytest.fixture
def mini_world():
    return build_world(MINI_YAML, None, start=RUSH_HOUR, seed=42)
