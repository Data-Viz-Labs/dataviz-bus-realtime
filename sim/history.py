"""Historical dataset: table schemas, S3 layout and the hourly aggregator.

Four tables, Parquet in the data bucket under ``history/``, catalogued in Glue and queried with
Athena (partition projection, so new partitions need no crawler):

    line_hourly    one row per (date, hour, line, direction)   partition month=YYYY-MM   years
    stop_hourly    one row per (date, hour, stop)               partition month=YYYY-MM   years
    stop_calls     one row per bus call at a stop               partition dt=YYYY-MM-DD   last days + live
    bus_positions  one row per bus every 30 s                   partition dt=YYYY-MM-DD   last days + live

``SCHEMAS`` is the single source of truth: the writer, Terraform (via ``tools/export_schemas.py``)
and the API documentation are generated from it.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sim.engine import TickResult

# Column types are Athena/Glue types.
SCHEMAS: dict[str, list[tuple[str, str, str]]] = {
    "line_hourly": [
        ("date", "date", "Service date (local time, Europe/Madrid)"),
        ("hour", "tinyint", "Hour of day 0-23 (local time)"),
        ("line_id", "string", "EMT line id"),
        ("direction", "tinyint", "0 outbound, 1 inbound"),
        ("trips", "int", "Trips that reached the end of the leg in this hour"),
        ("boardings", "int", "Passengers who boarded"),
        ("alightings", "int", "Passengers who got off"),
        ("avg_load", "double", "Mean passengers / nominal capacity over buses in service (can exceed 1)"),
        ("max_load", "double", "Highest passengers / nominal capacity seen"),
        ("avg_trip_minutes", "double", "Mean duration of the trips counted in `trips` (null if none)"),
        ("avg_wait_minutes", "double", "Estimated mean wait at stops (half the observed headway)"),
    ],
    "stop_hourly": [
        ("date", "date", "Service date (local time)"),
        ("hour", "tinyint", "Hour of day 0-23 (local time)"),
        ("stop_id", "string", "EMT stop code"),
        ("boardings", "int", "Passengers who boarded at the stop, all lines"),
        ("alightings", "int", "Passengers who got off at the stop, all lines"),
        ("avg_waiting", "double", "Mean people waiting at the stop"),
        ("max_waiting", "int", "Most people waiting at the stop"),
        ("bus_calls", "int", "Bus calls at the stop"),
    ],
    "stop_calls": [
        ("ts", "timestamp", "Time the bus reached the stop (local time)"),
        ("bus_id", "string", "Bus id: <line>-<n>"),
        ("line_id", "string", "EMT line id"),
        ("direction", "tinyint", "Leg the bus was on when arriving: 0 outbound, 1 inbound"),
        ("stop_id", "string", "EMT stop code"),
        ("terminal", "boolean", "End of a leg: everyone got off"),
        ("alighted", "int", "Passengers who got off"),
        ("boarded", "int", "Passengers who boarded"),
        ("passengers_after", "int", "Passengers on board when leaving"),
        ("left_behind", "int", "People still waiting for this line and direction (bus full)"),
    ],
    "bus_positions": [
        ("ts", "timestamp", "Sample time (local time)"),
        ("bus_id", "string", "Bus id"),
        ("line_id", "string", "EMT line id"),
        ("direction", "tinyint", "0 outbound, 1 inbound"),
        ("lat", "double", "Latitude (WGS84)"),
        ("lon", "double", "Longitude (WGS84)"),
        ("passengers", "int", "Passengers on board"),
        ("state", "string", "driving or dwelling"),
        ("next_stop_id", "string", "Next stop the bus will call at"),
    ],
}

PARTITION = {"line_hourly": "month", "stop_hourly": "month", "stop_calls": "dt", "bus_positions": "dt"}
PREFIX = "history"
POSITION_SAMPLE_S = 30


def partition_value(table: str, day) -> str:
    return day.strftime("%Y-%m") if PARTITION[table] == "month" else day.strftime("%Y-%m-%d")


def object_key(table: str, day, part: str) -> str:
    """history/<table>/<month|dt>=<value>/<part>.parquet"""
    return f"{PREFIX}/{table}/{PARTITION[table]}={partition_value(table, day)}/{part}.parquet"


# --- Parquet ----------------------------------------------------------------------------------

def _arrow_type(athena_type: str):
    import pyarrow as pa

    return {
        "date": pa.date32(), "tinyint": pa.int8(), "int": pa.int32(), "double": pa.float64(),
        "string": pa.string(), "boolean": pa.bool_(), "timestamp": pa.timestamp("ms"),
    }[athena_type]


def _arrow_table(table: str, rows: list[dict]):
    import pyarrow as pa

    schema = pa.schema([(name, _arrow_type(t)) for name, t, _ in SCHEMAS[table]])
    return pa.table({name: [r.get(name) for r in rows] for name in schema.names}, schema=schema)


def to_parquet(table: str, rows: list[dict]) -> bytes:
    """Serialise rows (dicts keyed by column name) with the table's exact schema."""
    stream = ParquetStream(table)
    stream.write(rows)
    return stream.close()


class ParquetStream:
    """Appends batches of rows to one in-memory Parquet file, so big outputs never sit in memory
    as Python objects (a simulated day has ~1.5 million position rows)."""

    def __init__(self, table: str):
        import io

        self.table, self.buf, self.writer, self.rows = table, io.BytesIO(), None, 0

    def write(self, rows: list[dict]) -> None:
        import pyarrow.parquet as pq

        if not rows:
            return
        batch = _arrow_table(self.table, rows)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.buf, batch.schema, compression="zstd")
        self.writer.write_table(batch)
        self.rows += len(rows)

    def close(self) -> bytes:
        if self.writer is None:  # no rows at all: still a valid, empty file
            import pyarrow.parquet as pq

            pq.write_table(_arrow_table(self.table, []), self.buf, compression="zstd")
        else:
            self.writer.close()
        return self.buf.getvalue()


# --- Aggregation of simulated ticks -----------------------------------------------------------

@dataclass
class _LineHour:
    trips: int = 0
    boardings: int = 0
    alightings: int = 0
    load_sum: float = 0.0
    load_n: int = 0
    max_load: float = 0.0
    trip_minutes: list[float] = field(default_factory=list)
    call_times: dict[str, list[datetime]] = field(default_factory=lambda: defaultdict(list))


@dataclass
class _StopHour:
    boardings: int = 0
    alightings: int = 0
    waiting_sum: int = 0
    waiting_n: int = 0
    max_waiting: int = 0
    bus_calls: int = 0


class Recorder:
    """Turns a stream of ``TickResult`` into history rows.

    Raw rows (stop calls, sampled positions) are available immediately; hourly rows are emitted
    once an hour is complete. ``drain()`` returns everything ready, keyed by table.
    """

    def __init__(self, capacities: dict[str, int], position_sample_s: int = POSITION_SAMPLE_S):
        self.capacities = capacities  # bus_id -> nominal capacity
        self.position_sample = timedelta(seconds=position_sample_s)
        self._next_sample: datetime | None = None
        self._hour: datetime | None = None
        self._lines: dict[tuple[str, int], _LineHour] = defaultdict(_LineHour)
        self._stops: dict[str, _StopHour] = defaultdict(_StopHour)
        self._ready: dict[str, list[dict]] = defaultdict(list)

    def add(self, r: TickResult) -> None:
        hour = r.time.replace(minute=0, second=0, microsecond=0)
        if self._hour is not None and hour != self._hour:
            self._close_hour()
        self._hour = hour

        for c in r.calls:
            self._ready["stop_calls"].append({
                "ts": c.time.replace(tzinfo=None), "bus_id": c.bus_id, "line_id": c.line_id,
                "direction": c.direction, "stop_id": c.stop_id, "terminal": c.terminal, "alighted": c.alighted,
                "boarded": c.boarded, "passengers_after": c.passengers_after, "left_behind": c.left_behind,
            })
            lh = self._lines[(c.line_id, c.direction)]
            lh.boardings += c.boarded
            lh.alightings += c.alighted
            lh.call_times[c.stop_id].append(c.time)
            if c.terminal:
                lh.trips += 1
                if c.leg_minutes is not None:
                    lh.trip_minutes.append(c.leg_minutes)
            sh = self._stops[c.stop_id]
            sh.boardings += c.boarded
            sh.alightings += c.alighted
            sh.bus_calls += 1

        for b in r.buses:
            load = b.passengers / self.capacities[b.bus_id]
            lh = self._lines[(b.line_id, b.direction)]
            lh.load_sum += load
            lh.load_n += 1
            lh.max_load = max(lh.max_load, load)
        for stop_id, n in r.waiting.items():
            sh = self._stops[stop_id]
            sh.waiting_sum += n
            sh.waiting_n += 1
            sh.max_waiting = max(sh.max_waiting, n)

        if self._next_sample is None or r.time >= self._next_sample:
            self._next_sample = r.time + self.position_sample
            ts = r.time.replace(tzinfo=None)
            self._ready["bus_positions"].extend(
                {"ts": ts, "bus_id": b.bus_id, "line_id": b.line_id, "direction": b.direction,
                 "lat": round(b.lat, 6), "lon": round(b.lon, 6), "passengers": b.passengers, "state": b.state,
                 "next_stop_id": b.next_stop_id}
                for b in r.buses
            )

    def _close_hour(self) -> None:
        day, hour = self._hour.date(), self._hour.hour
        for (line_id, direction), lh in self._lines.items():
            gaps = [
                (b - a).total_seconds() / 60
                for times in lh.call_times.values()
                for a, b in zip(times, times[1:], strict=False)
            ]
            self._ready["line_hourly"].append({
                "date": day, "hour": hour, "line_id": line_id, "direction": direction, "trips": lh.trips,
                "boardings": lh.boardings, "alightings": lh.alightings,
                "avg_load": round(lh.load_sum / lh.load_n, 4) if lh.load_n else 0.0,
                "max_load": round(lh.max_load, 4),
                "avg_trip_minutes": round(sum(lh.trip_minutes) / len(lh.trip_minutes), 2) if lh.trip_minutes else None,
                "avg_wait_minutes": round(sum(gaps) / len(gaps) / 2, 2) if gaps else None,
            })
        for stop_id, sh in self._stops.items():
            self._ready["stop_hourly"].append({
                "date": day, "hour": hour, "stop_id": stop_id, "boardings": sh.boardings,
                "alightings": sh.alightings,
                "avg_waiting": round(sh.waiting_sum / sh.waiting_n, 2) if sh.waiting_n else 0.0,
                "max_waiting": sh.max_waiting, "bus_calls": sh.bus_calls,
            })
        self._lines.clear()
        self._stops.clear()

    def flush_hour(self) -> None:
        """Close the current (possibly partial) hour, e.g. on shutdown."""
        if self._hour is not None:
            self._close_hour()

    def drain(self) -> dict[str, list[dict]]:
        ready, self._ready = dict(self._ready), defaultdict(list)
        return ready


class LiveHistory:
    """Records the live simulation into the same tables, after the generated history ends.

    Rows before ``until`` (already covered by ``sim.backfill``) or outside service hours
    (06:00-23:59) are dropped; ``flush`` writes one Parquet part per table and partition.
    """

    def __init__(self, put, capacities: dict[str, int]):
        self.put = put  # put(key, bytes)
        self.recorder = Recorder(capacities)

    def add(self, r: TickResult) -> None:
        self.recorder.add(r)

    def flush(self, until: datetime | None, stamp: datetime, final: bool = False) -> int:
        if final:
            self.recorder.flush_hour()
        rows = self.recorder.drain()
        if until is None:  # no generated history yet: nothing to continue
            return 0

        def keep(r: dict) -> bool:
            t = r["ts"] if "ts" in r else datetime.combine(r["date"], datetime.min.time()).replace(hour=r["hour"])
            return t >= until and t.hour >= 6

        written = 0
        for table, table_rows in rows.items():
            parts: dict = defaultdict(list)
            for r in filter(keep, table_rows):
                parts[r["ts"].date() if "ts" in r else r["date"]].append(r)
            for day, part in parts.items():
                self.put(object_key(table, day, f"live-{stamp:%Y%m%dT%H%M%S}"), to_parquet(table, part))
                written += len(part)
        return written
