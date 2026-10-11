"""Generate the history that precedes the live simulation.

    python -m sim.backfill --years 3 [--detail-days 7] [--out .cache/history | --bucket NAME]

1. A scenario is drawn from a fresh secret seed (``sim.scenario``): line targets, the overloaded
   peripheral line and every event. It is written to ``private/scenario.json`` only.
2. Calibration: the microsimulation runs a calm weekday rush on the real network and adjusts one
   demand factor per line until each line's mean load reaches its target. That run is also the
   reference the hourly model scales from.
3. Years of hourly rows (``line_hourly``, ``stop_hourly``, 06:00-23:59) come from the hourly
   model: reference x scenario factors x noise. Fast: about a minute per year.
4. The last ``detail-days`` days (and today up to ``--until``) are fully simulated, one process
   per day, producing every table including ``stop_calls`` and ``bus_positions``.
5. ``private/history_until.json`` tells the live service from when to record.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import json
import logging
import multiprocessing
import os
from pathlib import Path
import random
import sys
from zoneinfo import ZoneInfo

from sim.config import build_world, load_network
from sim.history import SCHEMAS, ParquetStream, Recorder, object_key
from sim.scenario import Scenario, generate, summary

log = logging.getLogger("sim.backfill")
SERVICE_HOURS = range(6, 24)
SCENARIO_KEY = "private/scenario.json"
UNTIL_KEY = "private/history_until.json"
TICK_S = 5.0


# --- output -----------------------------------------------------------------------------------

class LocalSink:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.spec = ("local", str(self.root))

    def put(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes | None:
        path = self.root / key
        return path.read_bytes() if path.exists() else None


class S3Sink:
    def __init__(self, client, bucket: str):
        self.client, self.bucket = client, bucket
        self.spec = ("s3", bucket)

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None


# --- calibration ------------------------------------------------------------------------------

@dataclass
class Reference:
    """Microsimulated weekday 08:00-09:00 with calibrated line factors."""

    day: date
    line_rows: dict[tuple[str, int], dict]
    stop_rows: dict[str, dict]
    x0: dict[str, float]  # city x line demand at the reference instant
    speed0: dict[str, float]


def calm_copy(s: Scenario) -> Scenario:
    calm = Scenario(s.seed, s.start, s.end, s.line_target, s.line_max_load, s.overloaded_line, [],
                    dict(s.line_factor), [])
    calm._by_day = {}
    return calm


def reference_day(s: Scenario) -> date:
    """A regular school Tuesday."""
    d = date(s.start.year, 10, 15)
    while not (d.weekday() == 1 and s.school_day(d)):
        d += timedelta(days=1)
    return d


def _run(lines_path, network_path, scenario, start, end, seed, only=None) -> Recorder:
    world = build_world(lines_path, network_path, start=start, seed=seed, only_lines=only)
    world.conditions = scenario
    rec = Recorder({b.bus_id: b.capacity for b in world.buses.values()})
    while world.clock < end:
        rec.add(world.step(TICK_S))
    rec.flush_hour()
    return rec


def calibrate(lines_path, network_path, scenario: Scenario, rounds: int = 3) -> Reference:
    calm = calm_copy(scenario)
    calm.line_factor = {lid: 1.0 for lid in scenario.line_target}
    day = reference_day(scenario)
    start, end = datetime.combine(day, time(6)), datetime.combine(day, time(9))
    for n in range(rounds):
        calm._days = {}
        rows = _run(lines_path, network_path, calm, start, end, seed=n).drain()
        load: dict[str, list[float]] = {}
        for r in rows["line_hourly"]:
            if r["hour"] == 8:
                load.setdefault(r["line_id"], []).append(r["avg_load"])
        for lid, target in scenario.line_target.items():
            measured = sum(load.get(lid, [0])) / max(1, len(load.get(lid, [])))
            ratio = target / measured if measured > 0 else 2.0
            calm.line_factor[lid] = round(calm.line_factor[lid] * min(4.0, max(0.25, ratio)), 4)
        log.info("calibration round %d done", n + 1)
    scenario.line_factor = dict(calm.line_factor)
    calm._days = {}
    rows = _run(lines_path, network_path, calm, start, end, seed=rounds).drain()
    f = calm.factors(datetime.combine(day, time(8, 30)))
    return Reference(
        day,
        {(r["line_id"], r["direction"]): r for r in rows["line_hourly"] if r["hour"] == 8},
        {r["stop_id"]: r for r in rows["stop_hourly"] if r["hour"] == 8},
        {lid: f.city * f.line_demand[lid] for lid in scenario.line_factor},
        dict(f.line_speed),
    )


# --- hourly model -----------------------------------------------------------------------------

def _softcap(x, cap):
    """Smooth min(x, cap): loads saturate near the line's maximum."""
    return x / (1 + (x / cap) ** 6) ** (1 / 6)


class HourlyModel:
    """Scales the reference hour by the scenario's factors, with noise."""

    def __init__(self, lines, scenario: Scenario, ref: Reference):
        import numpy as np

        self.np, self.s, self.ref = np, scenario, ref
        self.keys = sorted(ref.line_rows)
        self.line_of_key = [k[0] for k in self.keys]
        self.stops = sorted(ref.stop_rows)
        stop_index = {sid: i for i, sid in enumerate(self.stops)}
        # weight of each stop in its line's boardings, for event areas
        self.serving: dict[str, list[str]] = {}
        self.weights: dict[str, list[tuple[int, float]]] = {}
        for lid, line in lines.items():
            ids = [s.stop_id for s in line.stops if s.stop_id in stop_index]
            total = sum(ref.stop_rows[s]["boardings"] for s in ids) or 1
            self.weights[lid] = [(stop_index[s], ref.stop_rows[s]["boardings"] / total) for s in ids]
            for s in ids:
                self.serving.setdefault(s, []).append(lid)
        get = lambda field, default=0.0: np.array([  # noqa: E731
            ref.line_rows[k][field] if ref.line_rows[k][field] is not None else default for k in self.keys], float)
        self.B, self.L, self.T = get("boardings"), get("avg_load"), get("trips")
        self.A = get("alightings")
        self.R = np.array([self._trip_minutes(lines, k) for k in self.keys])
        self.W = get("avg_wait_minutes", 6.0)
        self.cap = np.array([scenario.line_max_load[k[0]] for k in self.keys])
        sget = lambda field: np.array([ref.stop_rows[s][field] for s in self.stops], float)  # noqa: E731
        self.SB, self.SA = sget("boardings"), sget("alightings")
        self.SW, self.SC = sget("avg_waiting"), sget("bus_calls")
        self.x0 = np.array([ref.x0[k[0]] for k in self.keys])
        self.v0 = np.array([ref.speed0[k[0]] for k in self.keys])

    def _trip_minutes(self, lines, key) -> float:
        r = self.ref.line_rows[key]["avg_trip_minutes"]
        if r:
            return r
        line = lines[key[0]]
        leg = line.legs[min(key[1], len(line.legs) - 1)]
        return len(leg.stops) * 0.4 + (line.length / len(line.legs)) / (line.speed_kmh * 1000 / 60)

    def hour(self, t: datetime, rng) -> tuple[dict, dict]:
        np = self.np
        f = self.s.factors(t + timedelta(minutes=30))
        x = np.array([f.city * f.line_demand.get(lid, 1.0) for lid in self.line_of_key])
        area = np.ones(len(self.keys))
        if f.stop_demand:
            stop_index = {sid: i for i, sid in enumerate(self.stops)}
            boost = {stop_index[s]: d - 1 for s, d in f.stop_demand.items() if s in stop_index}
            for i, lid in enumerate(self.line_of_key):
                area[i] += sum(w * boost.get(si, 0.0) for si, w in self.weights[lid])
        v = np.array([f.line_speed.get(lid, 1.0) for lid in self.line_of_key]) / self.v0
        live = np.array([lid not in f.suspended for lid in self.line_of_key], float)
        base = x / self.x0 * live
        ratio = base * area
        noise = lambda sigma, n: rng.lognormal(0.0, sigma, n)  # noqa: E731
        n = len(self.keys)
        boardings = np.rint(self.B * ratio * noise(0.08, n))
        load = _softcap(self.L * ratio / np.maximum(v, 0.2) * noise(0.06, n), self.cap) * live
        peak = np.minimum(load * rng.uniform(1.3, 1.8, n), self.cap)
        trips = np.rint(self.T * np.minimum(v, 1.3) * live * noise(0.1, n))
        trip_min = self.R / np.maximum(v, 0.2) * (1 + 0.08 * np.maximum(load - 0.6, 0)) * noise(0.05, n)
        wait = self.W / np.maximum(v, 0.2) * noise(0.1, n)
        lines = {
            "line_id": self.line_of_key, "direction": [k[1] for k in self.keys], "trips": trips.astype(int),
            "boardings": boardings.astype(int),
            "alightings": np.rint(boardings * rng.uniform(0.93, 1.07, n)).astype(int),
            "avg_load": np.round(load, 4), "max_load": np.round(peak, 4),
            "avg_trip_minutes": [round(m, 2) if t_ > 0 else None for m, t_ in zip(trip_min, trips, strict=True)],
            "avg_wait_minutes": [round(w, 2) if live_ else None for w, live_ in zip(wait, live, strict=True)],
        }
        # stops: the mean ratio of the lines that serve them, times their own event factor
        by_line = dict(zip(self.line_of_key, base, strict=False))
        speed_line = dict(zip(self.line_of_key, v, strict=False))
        m = len(self.stops)
        rs = np.array([np.mean([by_line[lid] for lid in self.serving.get(s, [])] or [0]) * f.stop_demand.get(s, 1.0)
                       for s in self.stops])
        vs = np.array([np.mean([speed_line[lid] for lid in self.serving.get(s, [])] or [1]) for s in self.stops])
        worst = {}
        for i, lid in enumerate(self.line_of_key):
            worst[lid] = max(worst.get(lid, 0.0), load[i])
        crowd = np.array([1 + 2 * max(0.0, max(worst[lid] for lid in self.serving[s]) - 0.95) for s in self.stops])
        waiting = self.SW * rs / np.maximum(vs, 0.2) * crowd * noise(0.1, m)
        stops = {
            "stop_id": self.stops,
            "boardings": np.rint(self.SB * rs * noise(0.1, m)).astype(int),
            "alightings": np.rint(self.SA * rs * noise(0.1, m)).astype(int),
            "avg_waiting": np.round(waiting, 2),
            "max_waiting": np.rint(waiting * rng.uniform(1.4, 2.1, m)).astype(int),
            "bus_calls": np.rint(self.SC * np.minimum(vs, 1.3) * (rs > 0) * noise(0.05, m)).astype(int),
        }
        return lines, stops


def _columns_parquet(table: str, columns: dict) -> bytes:
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    from sim.history import _arrow_type

    schema = pa.schema([(name, _arrow_type(t)) for name, t, _ in SCHEMAS[table]])
    arrays = [pa.array(list(columns[name]) if not hasattr(columns[name], "tolist") else columns[name].tolist(),
                       type=schema.field(name).type) for name in schema.names]
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), buf, compression="zstd")
    return buf.getvalue()


def model_month(model: HourlyModel, first: date, last: date, seed: int) -> dict[str, bytes]:
    """Hourly rows for first..last (inclusive), as Parquet bytes per table."""
    import numpy as np

    rng = np.random.default_rng([seed, first.toordinal()])
    acc = {"line_hourly": {}, "stop_hourly": {}}
    d = first
    while d <= last:
        for h in SERVICE_HOURS:
            lines, stops = model.hour(datetime.combine(d, time(h)), rng)
            for table, cols in (("line_hourly", lines), ("stop_hourly", stops)):
                n = len(cols["boardings"])
                cols = {**cols, "date": [d] * n, "hour": [h] * n}
                for k, v in cols.items():
                    acc[table].setdefault(k, []).extend(v.tolist() if hasattr(v, "tolist") else v)
        d += timedelta(days=1)
    return {table: _columns_parquet(table, cols) for table, cols in acc.items()}


# --- detailed days ----------------------------------------------------------------------------

def simulate_day(args: tuple) -> int:
    """Microsimulate one service day (05:00 warm-up, records from 06:00) up to ``end`` and write
    its parts to the sink. Rows are streamed to Parquet every simulated hour to bound memory."""
    lines_path, network_path, scenario_json, day_iso, end_iso, seed, sink_spec = args
    lines, _, _ = load_network(lines_path, network_path)
    scenario = Scenario.from_json(scenario_json, lines)
    day = date.fromisoformat(day_iso)
    end = datetime.fromisoformat(end_iso)
    world = build_world(lines_path, network_path, start=datetime.combine(day, time(5)), seed=seed)
    world.conditions = scenario
    rec = Recorder({b.bus_id: b.capacity for b in world.buses.values()})
    streams = {table: ParquetStream(table) for table in SCHEMAS}

    def drain() -> None:
        for table, rows in rec.drain().items():
            streams[table].write([r for r in rows if (r["ts"].hour if "ts" in r else r["hour"]) >= 6])

    next_drain = world.clock + timedelta(hours=1)
    while world.clock < end:
        rec.add(world.step(TICK_S))
        if world.clock >= next_drain:
            drain()
            next_drain += timedelta(hours=1)
    rec.flush_hour()
    drain()
    sink = open_sink(sink_spec)
    rows = 0
    for table, stream in streams.items():
        if stream.rows:
            rows += stream.rows
            sink.put(object_key(table, day, f"sim-{day.isoformat()}"), stream.close())
    return rows


def open_sink(spec: tuple):
    kind, target = spec
    if kind == "s3":
        import boto3

        return S3Sink(boto3.client("s3"), target)
    return LocalSink(target)


# --- driver -----------------------------------------------------------------------------------

def run(lines_path: str, network_path: str | None, sink, years: float, detail_days: int, until: datetime,
        seed: int | None = None, workers: int | None = None) -> Scenario:
    lines, _, _ = load_network(lines_path, network_path)
    first = (until - timedelta(days=round(365.25 * years))).date()
    detail_start = until.date() - timedelta(days=detail_days)
    scenario = generate(lines, first, until.date() + timedelta(days=3), seed)
    log.info(summary(scenario))
    ref = calibrate(lines_path, network_path, scenario)
    sink.put(SCENARIO_KEY, json.dumps(scenario.to_json(), indent=1).encode())
    log.info("calibrated %d lines; overloaded line target %.2f", len(scenario.line_factor),
             scenario.line_target[scenario.overloaded_line])

    model = HourlyModel(lines, scenario, ref)
    month = date(first.year, first.month, 1)
    while month < detail_start:
        nxt = date(month.year + month.month // 12, month.month % 12 + 1, 1)
        lo, hi = max(month, first), min(nxt - timedelta(days=1), detail_start - timedelta(days=1))
        for table, data in model_month(model, lo, hi, scenario.seed).items():
            sink.put(object_key(table, lo, "model"), data)
        log.info("hourly model %s", month.strftime("%Y-%m"))
        month = nxt

    jobs = []
    d = detail_start
    while d <= until.date():
        end = min(datetime.combine(d + timedelta(days=1), time()), until)
        if end > datetime.combine(d, time(6)):
            jobs.append((lines_path, network_path, scenario.to_json(), d.isoformat(), end.isoformat(),
                         random.Random(f"{scenario.seed}:{d}").randrange(2**32), sink.spec))
        d += timedelta(days=1)
    spawn = multiprocessing.get_context("spawn")  # fork is unsafe in a threaded process
    # ~400 MB per worker on the full network
    with ProcessPoolExecutor(max_workers=workers or min(4, os.cpu_count() or 1), mp_context=spawn) as pool:
        for job, rows in zip(jobs, pool.map(simulate_day, jobs), strict=True):
            log.info("simulated %s (%d rows)", job[3], rows)
    sink.put(UNTIL_KEY, json.dumps({"until": until.isoformat()}).encode())
    return scenario


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m sim.backfill", description=__doc__.splitlines()[0])
    p.add_argument("--lines", default=os.environ.get("LINES_FILE", "data/lines.yaml"))
    p.add_argument("--network", default=os.environ.get("NETWORK_FILE", "data/network.json"))
    p.add_argument("--years", type=float, default=1.0)
    p.add_argument("--detail-days", type=int, default=7)
    p.add_argument("--until", help="end of history, local ISO time (default: now, floored to the hour)")
    p.add_argument("--out", help="local directory (default .cache/history unless --bucket)")
    p.add_argument("--bucket", default=os.environ.get("DATA_BUCKET"), help="S3 data bucket")
    p.add_argument("--seed", type=int, help="fix the scenario (tests); omit for a secret random one")
    p.add_argument("--workers", type=int)
    p.add_argument("--timezone", default=os.environ.get("TIMEZONE", "Europe/Madrid"))
    args = p.parse_args(argv)
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")

    if args.until:
        until = datetime.fromisoformat(args.until)
    else:
        until = datetime.now(ZoneInfo(args.timezone)).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    if args.bucket and not args.out:
        import boto3

        sink = S3Sink(boto3.client("s3"), args.bucket)
    else:
        sink = LocalSink(args.out or ".cache/history")
    run(args.lines, args.network, sink, args.years, args.detail_days, until, args.seed, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
