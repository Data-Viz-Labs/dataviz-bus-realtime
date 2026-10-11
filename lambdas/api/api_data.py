"""Data behind the REST routes and the MCP tools.

Every public function takes the request parameters (path + query string, or tool arguments) as a
dict of strings and returns a JSON-serialisable dict, or raises ``ApiError``.

Sources: ``network.json`` and ``live/snapshot.json`` in the site bucket, the Glue/Athena history
tables and their Parquet files in the data bucket (``history/<table>/<month|dt>=<value>/``).
"""

from datetime import UTC, date, datetime, timedelta
import json
import os
import re
import time

import api_athena as queries
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# --- AWS clients and caches -------------------------------------------------------------------

clients: dict = {}  # tests put stubbed clients here
_cache: dict[str, tuple[float, object]] = {}


def client(name: str):
    if name not in clients:
        extra = {"signature_version": "s3v4"} if name == "s3" else {}
        clients[name] = boto3.client(name, config=Config(retries={"max_attempts": 3, "mode": "standard"}, **extra))
    return clients[name]


def cached(key: str, ttl_s: float, load):
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl_s:
        return hit[1]
    value = load()
    _cache[key] = (now, value)
    return value


def env(name: str) -> str:
    return os.environ.get(name, "")


def _get_json(bucket: str, key: str) -> dict:
    try:
        return json.loads(client("s3").get_object(Bucket=bucket, Key=key)["Body"].read())
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404", "AccessDenied", "403"):
            raise ApiError(503, "unavailable", f"{key} is not available yet") from e
        raise


def network() -> dict:
    return cached("network", 3600, lambda: _get_json(env("SITE_BUCKET"), "network.json"))


def snapshot() -> dict:
    return cached("snapshot", 2, lambda: _get_json(env("SITE_BUCKET"), "live/snapshot.json"))


# --- Parameter validation ---------------------------------------------------------------------

ID = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
BUS_ID = re.compile(r"^[A-Za-z0-9_.]{1,16}-\d{1,4}$")


def _id(p: dict, name: str, pattern: re.Pattern = ID, required: bool = True) -> str | None:
    value = (p.get(name) or "").strip()
    if not value:
        if required:
            raise ApiError(400, "bad_request", f"parameter '{name}' is required")
        return None
    if not pattern.match(value):
        raise ApiError(400, "bad_request", f"invalid {name}: {value!r}")
    return value


def _line(p: dict, name: str = "line_id", required: bool = True) -> str | None:
    line_id = _id(p, name, required=required)
    if line_id is not None and line_id not in network()["lines"]:
        raise ApiError(404, "not_found", f"line {line_id} does not exist (GET /v1/lines lists them)")
    return line_id


def _stop(p: dict, name: str = "stop_id", required: bool = True) -> str | None:
    stop_id = _id(p, name, required=required)
    if stop_id is not None and stop_id not in network()["stops"]:
        raise ApiError(404, "not_found", f"stop {stop_id} does not exist")
    return stop_id


def _int(p: dict, name: str, default: int | None, lo: int, hi: int) -> int | None:
    raw = (p.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, "bad_request", f"{name} must be an integer") from None
    if not lo <= value <= hi:
        raise ApiError(400, "bad_request", f"{name} must be between {lo} and {hi}")
    return value


def _bool(p: dict, name: str, default: bool) -> bool:
    raw = (p.get(name) or "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes")


def _date(p: dict, name: str) -> date:
    raw = (p.get(name) or "").strip()
    if not raw:
        raise ApiError(400, "bad_request", f"parameter '{name}' is required (YYYY-MM-DD)")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ApiError(400, "bad_request", f"{name} must be a date YYYY-MM-DD, got {raw!r}") from None


def _date_range(p: dict, max_days: int) -> tuple[date, date]:
    """Inclusive ``from``..``to`` (``to`` defaults to ``from``)."""
    start = _date(p, "from")
    end = _date(p, "to") if p.get("to") else start
    if end < start:
        raise ApiError(400, "bad_request", "'to' is before 'from'")
    if (end - start).days + 1 > max_days:
        raise ApiError(400, "bad_request", f"the range is limited to {max_days} days")
    return start, end


def _datetime(p: dict, name: str) -> datetime:
    raw = (p.get(name) or "").strip()
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(400, "bad_request", f"{name} must be an ISO date-time, e.g. 2026-10-11T08:00:00") from None
    if value.tzinfo is not None:  # the dataset is in Madrid local time, without offset
        try:
            from zoneinfo import ZoneInfo

            value = value.astimezone(ZoneInfo("Europe/Madrid"))
        except (ImportError, KeyError, ValueError):  # no tz database: keep the wall-clock time
            pass
        value = value.replace(tzinfo=None)
    return value


def _months(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _days(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def _in(column: str, values: list[str]) -> tuple[str, list[str]]:
    """``column IN (?, ?)`` with its ExecutionParameters (partition pruning)."""
    return f"{column} IN ({', '.join('?' * len(values))})", [queries.quote(v) for v in values]


def _athena(sql: str, params: list[str], max_rows: int = queries.MAX_SQL_ROWS) -> dict:
    try:
        return queries.run(client("athena"), sql, database=env("GLUE_DATABASE"), workgroup=env("ATHENA_WORKGROUP"),
                           params=params, max_rows=max_rows)
    except queries.QueryFailed as e:
        raise ApiError(400, "query_failed", str(e)) from None
    except queries.QueryTimeout:
        raise ApiError(504, "timeout", "the query took more than 50 s: narrow the range or aggregate more") from None
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidRequestException":
            raise ApiError(400, "query_failed", e.response["Error"].get("Message", "invalid query")) from None
        raise


# --- Network ----------------------------------------------------------------------------------

def health(p: dict) -> dict:
    return {"status": "ok", "time": datetime.now(UTC).isoformat(timespec="seconds")}


def _stop_brief(stop_id: str) -> dict:
    s = network()["stops"][stop_id]
    return {"id": stop_id, "name": s["name"], "lat": s["lat"], "lon": s["lon"]}


def list_lines(p: dict) -> dict:
    return {"lines": [
        {"id": line_id, "name": li["name"], "color": li["color"], "capacity": li["capacity"], "buses": li["buses"],
         "stops_outbound": len(li["outbound"]), "stops_inbound": len(li["inbound"]), "circular": not li["inbound"]}
        for line_id, li in network()["lines"].items()
    ]}


def get_line(p: dict) -> dict:
    line_id = _line(p)
    li = network()["lines"][line_id]
    out = {"id": line_id, "name": li["name"], "color": li["color"], "capacity": li["capacity"], "buses": li["buses"],
           "circular": not li["inbound"],
           "outbound": [_stop_brief(s) for s in li["outbound"]],
           "inbound": [_stop_brief(s) for s in li["inbound"]]}
    if _bool(p, "include_path", True):
        out["path"] = li["path"]
    return out


def list_stops(p: dict) -> dict:
    line_id = _line(p, "line", required=False)
    stops = network()["stops"]
    if line_id:
        li = network()["lines"][line_id]
        ids = list(dict.fromkeys(li["outbound"] + li["inbound"]))
    else:
        ids = list(stops)
    return {"stops": [{**_stop_brief(s), "lines": stops[s]["lines"]} for s in ids]}


def get_stop(p: dict) -> dict:
    stop_id = _stop(p)
    lines = network()["lines"]
    served = []
    for line_id in network()["stops"][stop_id]["lines"]:
        li = lines[line_id]
        dirs = [d for d, leg in ((0, li["outbound"]), (1, li["inbound"])) if stop_id in leg]
        served.append({"id": line_id, "name": li["name"], "color": li["color"], "directions": dirs})
    return {**_stop_brief(stop_id), "lines": served}


# --- Live -------------------------------------------------------------------------------------

def _bus(b: dict) -> dict:
    capacity = network()["lines"].get(b.get("line"), {}).get("capacity")
    return {**b, "load": round(b["passengers"] / capacity, 3) if capacity else None}


def live_buses(p: dict) -> dict:
    line_id = _line(p, "line", required=False)
    snap = snapshot()
    buses = [_bus(b) for b in snap["buses"] if line_id is None or b["line"] == line_id]
    return {"time": snap["time"], "count": len(buses), "buses": buses}


def live_line(p: dict) -> dict:
    line_id = _line(p)
    li, snap = network()["lines"][line_id], snapshot()
    waiting = snap.get("waiting", {})
    buses = [_bus(b) for b in snap["buses"] if b["line"] == line_id]
    legs = {"outbound": li["outbound"], "inbound": li["inbound"]}
    stops = {leg: [{**_stop_brief(s), "waiting": waiting.get(s, 0)} for s in ids] for leg, ids in legs.items()}
    return {
        "time": snap["time"], "line_id": line_id, "name": li["name"], "capacity": li["capacity"],
        "buses_in_service": len(buses), "passengers": sum(b["passengers"] for b in buses),
        "waiting": sum(waiting.get(s, 0) for s in dict.fromkeys(li["outbound"] + li["inbound"])),
        "buses": buses, "stops": stops,
    }


def live_stop(p: dict) -> dict:
    stop_id = _stop(p)
    snap = snapshot()
    approaching = [_bus(b) for b in snap["buses"] if (b.get("next_stop_id") or b.get("next_stop")) == stop_id]
    return {"time": snap["time"], **_stop_brief(stop_id), "lines": network()["stops"][stop_id]["lines"],
            "waiting": snap.get("waiting", {}).get(stop_id, 0), "approaching": approaching}


# --- History (Athena) -------------------------------------------------------------------------

LINE_HOURLY_COLUMNS = ("date, hour, line_id, direction, trips, boardings, alightings, avg_load, max_load, "
                       "avg_trip_minutes, avg_wait_minutes")
STOP_HOURLY_COLUMNS = "date, hour, stop_id, boardings, alightings, avg_waiting, max_waiting, bus_calls"
STOP_CALLS_COLUMNS = ("ts, bus_id, line_id, direction, stop_id, terminal, alighted, boarded, passengers_after, "
                      "left_behind")
BUS_POSITIONS_COLUMNS = "ts, bus_id, line_id, direction, lat, lon, passengers, state, next_stop_id"
MAX_HOURLY_DAYS, MAX_CALL_DAYS = 400, 7


def line_hourly(p: dict) -> dict:
    line_id = _line(p)
    start, end = _date_range(p, MAX_HOURLY_DAYS)
    direction = _int(p, "direction", None, 0, 1)
    part, params = _in("month", _months(start, end))
    sql = (f"SELECT {LINE_HOURLY_COLUMNS} FROM line_hourly WHERE {part} "
           "AND date BETWEEN CAST(? AS date) AND CAST(? AS date) AND line_id = ?")
    params += [queries.quote(start.isoformat()), queries.quote(end.isoformat()), queries.quote(line_id)]
    if direction is not None:
        sql += " AND direction = ?"
        params.append(str(direction))
    sql += " ORDER BY date, hour, direction"
    return {"line_id": line_id, "from": start.isoformat(), "to": end.isoformat(),
            **_athena(sql, params, max_rows=MAX_HOURLY_DAYS * 24 * 2)}


def stop_hourly(p: dict) -> dict:
    stop_id = _stop(p)
    start, end = _date_range(p, MAX_HOURLY_DAYS)
    part, params = _in("month", _months(start, end))
    sql = (f"SELECT {STOP_HOURLY_COLUMNS} FROM stop_hourly WHERE {part} "
           "AND date BETWEEN CAST(? AS date) AND CAST(? AS date) AND stop_id = ? ORDER BY date, hour")
    params += [queries.quote(start.isoformat()), queries.quote(end.isoformat()), queries.quote(stop_id)]
    return {"stop_id": stop_id, "from": start.isoformat(), "to": end.isoformat(),
            **_athena(sql, params, max_rows=MAX_HOURLY_DAYS * 24)}


def stop_calls(p: dict, default_limit: int = 10_000, max_limit: int = 50_000) -> dict:
    start, end = _date_range(p, MAX_CALL_DAYS)
    limit = _int(p, "limit", default_limit, 1, max_limit)
    part, params = _in("dt", _days(start, end))
    sql = f"SELECT {STOP_CALLS_COLUMNS} FROM stop_calls WHERE {part}"
    filters = {"line_id": _line(p, "line", required=False), "stop_id": _stop(p, "stop", required=False),
               "bus_id": _id(p, "bus", BUS_ID, required=False)}
    for column, value in filters.items():
        if value is not None:
            sql += f" AND {column} = ?"
            params.append(queries.quote(value))
    sql += f" ORDER BY ts, bus_id LIMIT {limit}"  # limit is a validated int
    return {"from": start.isoformat(), "to": end.isoformat(), **_athena(sql, params, max_rows=limit)}


def positions(p: dict) -> dict:
    bus_id = _id(p, "bus", BUS_ID)
    start, end = _datetime(p, "from"), _datetime(p, "to")
    if end <= start:
        raise ApiError(400, "bad_request", "'to' must be after 'from'")
    if end - start > timedelta(days=1):
        raise ApiError(400, "bad_request", "the range is limited to 1 day")
    part, params = _in("dt", _days(start.date(), end.date()))
    sql = (f"SELECT {BUS_POSITIONS_COLUMNS} FROM bus_positions WHERE {part} AND bus_id = ? "
           "AND ts BETWEEN CAST(? AS timestamp) AND CAST(? AS timestamp) ORDER BY ts")
    params += [queries.quote(bus_id), queries.quote(start.isoformat(sep=" ")), queries.quote(end.isoformat(sep=" "))]
    return {"bus_id": bus_id, "from": start.isoformat(), "to": end.isoformat(), **_athena(sql, params)}


def run_sql(p: dict) -> dict:
    try:
        sql = queries.guard_sql(p.get("query") or "")
    except queries.SqlError as e:
        status = 413 if len(p.get("query") or "") > queries.MAX_SQL_CHARS else 400
        raise ApiError(status, "invalid_sql", str(e)) from None
    return {"query": sql, **_athena(sql, [])}


# --- Datasets ---------------------------------------------------------------------------------

TABLES = {
    "line_hourly": ("One row per (date, hour, line, direction). Years of data.", "month"),
    "stop_hourly": ("One row per (date, hour, stop), all lines together. Years of data.", "month"),
    "stop_calls": ("One row per bus call at a stop. Last days only.", "dt"),
    "bus_positions": ("One row per bus every 30 s. Last days only.", "dt"),
}
SQL_NOTES = [
    "Athena (Trino) SQL on database {db}; one SELECT/WITH statement, at most 10000 rows returned.",
    "Always filter the partition column: WHERE month BETWEEN '2026-01' AND '2026-03' (line_hourly, stop_hourly) or "
    "WHERE dt = '2026-10-11' (stop_calls, bus_positions). Partition columns are strings; without the filter "
    "Athena scans every file and may hit the 2 GiB per-query scan limit.",
    "Times are Madrid local time without offset; date is a DATE, ts a TIMESTAMP.",
]
SQL_EXAMPLES = [
    "SELECT hour, avg(avg_load) AS load FROM line_hourly WHERE month = '2026-09' AND line_id = '27' "
    "GROUP BY hour ORDER BY hour",
    "SELECT stop_id, sum(boardings) AS boardings FROM stop_hourly WHERE month BETWEEN '2026-01' AND '2026-06' "
    "GROUP BY stop_id ORDER BY boardings DESC LIMIT 20",
    "SELECT line_id, count(*) AS full_calls FROM stop_calls WHERE dt = '2026-10-10' AND left_behind > 0 "
    "GROUP BY line_id ORDER BY full_calls DESC",
]


def _glue_tables() -> dict:
    def load() -> dict:
        out = {}
        for page in client("glue").get_paginator("get_tables").paginate(DatabaseName=env("GLUE_DATABASE")):
            for t in page["TableList"]:
                out[t["Name"]] = [
                    {"name": c["Name"], "type": c["Type"], "description": c.get("Comment", "")}
                    for c in t.get("StorageDescriptor", {}).get("Columns", [])
                ]
        return out

    return cached("glue_tables", 3600, load)


def _partitions(table: str) -> list[str]:
    def load() -> list[str]:
        prefix, values = f"history/{table}/", []
        pages = client("s3").get_paginator("list_objects_v2").paginate(
            Bucket=env("DATA_BUCKET"), Prefix=prefix, Delimiter="/")
        for page in pages:
            for cp in page.get("CommonPrefixes", []):
                values.append(cp["Prefix"][len(prefix):].rstrip("/").split("=", 1)[-1])
        return sorted(values)

    return cached(f"partitions/{table}", 300, load)


def datasets(p: dict) -> dict:
    columns = _glue_tables()
    tables = []
    for name, (description, key) in TABLES.items():
        parts = _partitions(name)
        tables.append({
            "name": name, "description": description, "partition_key": key,
            "partition_format": "YYYY-MM" if key == "month" else "YYYY-MM-DD",
            "partitions": {"count": len(parts), "first": parts[0] if parts else None,
                           "last": parts[-1] if parts else None, "values": parts},
            "columns": columns.get(name, []),
        })
    db = env("GLUE_DATABASE")
    return {"database": db, "tables": tables, "sql_notes": [n.format(db=db) for n in SQL_NOTES],
            "sql_examples": SQL_EXAMPLES}


MAX_FILES, URL_TTL_S = 500, 3600


def _objects(bucket: str, prefix: str, start_after: str):
    """S3 objects under ``prefix`` in key order, fetched page by page as they are consumed."""
    pages = client("s3").get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix, StartAfter=start_after)
    for page in pages:
        yield from page.get("Contents", [])


def dataset_files(p: dict) -> dict:
    table = p.get("table", "")
    if table not in TABLES:
        raise ApiError(404, "not_found", f"unknown table {table!r}: one of {', '.join(TABLES)}")
    key_name = TABLES[table][1]
    start, end = _date_range(p, 100 * 366)
    width = 7 if key_name == "month" else 10  # YYYY-MM or YYYY-MM-DD
    lo, hi = start.isoformat()[:width], end.isoformat()[:width]
    prefix, bucket = f"history/{table}/", env("DATA_BUCKET")
    files, truncated = [], False
    for obj in _objects(bucket, prefix, start_after=f"{prefix}{key_name}={lo}"):
        part = obj["Key"][len(prefix):].split("/", 1)[0].split("=", 1)[-1]
        if part > hi:
            break
        if part < lo or not obj["Key"].endswith(".parquet"):
            continue
        if len(files) == MAX_FILES:
            truncated = True
            break
        files.append({
            "key": obj["Key"], "partition": part, "size": obj["Size"],
            "last_modified": obj["LastModified"].isoformat(),
            "url": client("s3").generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": obj["Key"]}, ExpiresIn=URL_TTL_S),
        })
    return {"table": table, "from": start.isoformat(), "to": end.isoformat(), "expires_in": URL_TTL_S,
            "count": len(files), "truncated": truncated, "files": files}
