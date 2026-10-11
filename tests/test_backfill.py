from datetime import date, datetime, timedelta
import io
import json

import pyarrow.parquet as pq
import pytest

from sim import backfill
from sim.config import build_world
from sim.history import SCHEMAS, LiveHistory, Recorder, object_key
from tests.conftest import MINI_YAML


def read(sink: backfill.LocalSink, key: str) -> list[dict]:
    return pq.read_table(io.BytesIO(sink.get(key))).to_pylist()


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    sink = backfill.LocalSink(tmp_path_factory.mktemp("history"))
    until = datetime(2026, 10, 9, 15)
    scenario = backfill.run(str(MINI_YAML), None, sink, years=0.2, detail_days=1, until=until, seed=5, workers=2)
    return sink, scenario, until


def test_every_table_is_written_with_its_schema(generated):
    sink, _, _ = generated
    files = {p.relative_to(sink.root).as_posix() for p in sink.root.rglob("*.parquet")}
    for table in SCHEMAS:
        assert any(f.startswith(f"history/{table}/") for f in files), table
    for f in files:
        table = f.split("/")[1]
        cols = pq.read_schema(sink.root / f).names
        assert cols == [c for c, _, _ in SCHEMAS[table]]


def test_private_answer_key_and_history_end(generated):
    sink, scenario, until = generated
    assert json.loads(sink.get(backfill.SCENARIO_KEY))["seed"] == scenario.seed
    assert json.loads(sink.get(backfill.UNTIL_KEY)) == {"until": until.isoformat()}


def test_hourly_model_and_microsimulation_cover_the_range_without_gaps(generated):
    sink, _, until = generated
    rows = []
    for p in sink.root.glob("history/line_hourly/*/*.parquet"):
        rows += pq.read_table(p).to_pylist()
    dates = sorted({r["date"] for r in rows})
    assert dates[-1] == until.date()
    assert all((b - a) == timedelta(days=1) for a, b in zip(dates, dates[1:], strict=False))
    assert {r["hour"] for r in rows} <= set(range(6, 24))
    assert all(r["avg_load"] <= 1.2 + 1e-9 for r in rows)


def test_detailed_days_have_raw_events_in_service_hours(generated):
    sink, _, until = generated
    calls = read(sink, object_key("stop_calls", until.date(), f"sim-{until.date()}"))
    assert calls and all(6 <= r["ts"].hour < until.hour for r in calls)
    positions = read(sink, object_key("bus_positions", until.date(), f"sim-{until.date()}"))
    assert {r["bus_id"] for r in positions} == {"A-01", "A-02", "A-03", "B-01", "B-02", "C-01", "C-02"}


def test_recorder_balances_boardings_with_stop_calls():
    world = build_world(MINI_YAML, None, start=datetime(2026, 10, 12, 7, 50), seed=1)
    rec = Recorder({b.bus_id: b.capacity for b in world.buses.values()})
    while world.clock < datetime(2026, 10, 12, 9):
        rec.add(world.step(5))
    rows = rec.drain()
    hour8_calls = [r for r in rows["stop_calls"] if r["ts"].hour == 8]
    line8 = [r for r in rows["line_hourly"] if r["hour"] == 8]
    stop8 = [r for r in rows["stop_hourly"] if r["hour"] == 8]
    boarded = sum(r["boarded"] for r in hour8_calls)
    assert boarded > 0
    assert sum(r["boardings"] for r in line8) == boarded == sum(r["boardings"] for r in stop8)
    assert {r["hour"] for r in rows["line_hourly"]} == {7, 8}  # 09:00 not closed yet


def test_live_history_only_continues_after_the_generated_history():
    written = {}
    world = build_world(MINI_YAML, None, start=datetime(2026, 10, 12, 7, 0), seed=1)
    live = LiveHistory(lambda k, v: written.__setitem__(k, v), {b.bus_id: b.capacity for b in world.buses.values()})
    for _ in range(int(1.5 * 3600 / 5)):
        live.add(world.step(5))
    assert live.flush(None, world.clock) == 0 and not written  # no backfill yet: nothing recorded
    for _ in range(int(0.5 * 3600 / 5)):
        live.add(world.step(5))
    until = datetime(2026, 10, 12, 8)
    assert live.flush(until, world.clock, final=True) > 0
    calls = pq.read_table(io.BytesIO(next(v for k, v in written.items() if "stop_calls" in k))).to_pylist()
    assert min(r["ts"] for r in calls) >= until
    assert all(k.startswith("history/") and "live-" in k for k in written)


def test_reference_day_is_a_school_tuesday(generated):
    _, scenario, _ = generated
    d = backfill.reference_day(scenario)
    assert d.weekday() == 1 and scenario.school_day(d) and d >= date(d.year, 10, 15)
