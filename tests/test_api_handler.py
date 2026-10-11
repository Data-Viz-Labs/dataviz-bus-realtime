import base64
from datetime import UTC, datetime
import hashlib
import importlib
import importlib.util
import io
import json
import sys
import time

import boto3
from botocore.config import Config
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber
import pytest

from tests.conftest import REPO

API = REPO / "lambdas" / "api"


def load_api():
    """The Lambda's modules, imported the way the Lambda runtime does (its folder on sys.path)."""
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    spec = importlib.util.spec_from_file_location("api_handler", API / "handler.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, importlib.import_module("api_data"), importlib.import_module("api_athena"), \
        importlib.import_module("api_mcp")


handler, data, athena, mcp = load_api()

KEY = "secret-key-of-group-a"
NETWORK = {
    "lines": {
        "27": {"name": "Glorieta de Embajadores - Plaza de Castilla", "color": "#0178bc", "capacity": 90, "buses": 25,
               "outbound": ["86", "85"], "inbound": ["85", "86"], "path": [[-3.70242, 40.40539], [-3.69, 40.42]]},
        "C1": {"name": "Circular", "color": "#e60003", "capacity": 80, "buses": 10,
               "outbound": ["86", "90"], "inbound": [], "path": [[-3.70242, 40.40539]]},
    },
    "stops": {
        "86": {"name": "Embajadores", "lat": 40.40539, "lon": -3.70242, "lines": ["27", "C1"]},
        "85": {"name": "Atocha", "lat": 40.41, "lon": -3.69, "lines": ["27"]},
        "90": {"name": "Sol", "lat": 40.417, "lon": -3.703, "lines": ["C1"]},
    },
}
SNAPSHOT = {
    "time": "2026-10-11T08:00:00+02:00",
    "buses": [
        {"id": "27-1", "line": "27", "lat": 40.41, "lon": -3.69, "passengers": 45, "direction": 0,
         "next_stop_id": "85"},
        {"id": "27-2", "line": "27", "lat": 40.42, "lon": -3.69, "passengers": 9, "direction": 1,
         "next_stop_id": "86"},
        {"id": "C1-1", "line": "C1", "lat": 40.41, "lon": -3.70, "passengers": 20, "direction": 0,
         "next_stop_id": "90"},
    ],
    "waiting": {"86": 5, "85": 2},
}


def aws(name):
    config = Config(signature_version="s3v4") if name == "s3" else None
    return boto3.client(name, region_name="eu-west-1", aws_access_key_id="x", aws_secret_access_key="x", config=config)


@pytest.fixture(autouse=True)
def api_env(monkeypatch):
    monkeypatch.setenv("DATA_BUCKET", "data-bucket")
    monkeypatch.setenv("SITE_BUCKET", "site-bucket")
    monkeypatch.setenv("GLUE_DATABASE", "bus_history")
    monkeypatch.setenv("ATHENA_WORKGROUP", "bus-history")
    monkeypatch.setenv("KEY_HASHES", json.dumps({hashlib.sha256(KEY.encode()).hexdigest(): "group-a"}))
    monkeypatch.setattr(athena.time, "sleep", lambda s: None)
    data._cache.clear()
    data.clients.clear()
    now = time.monotonic()
    data._cache["network"] = (now, NETWORK)
    data._cache["snapshot"] = (now, SNAPSHOT)
    yield
    data._cache.clear()
    data.clients.clear()


@pytest.fixture
def stubs():
    """Stubbed s3, athena and glue clients; every queued response must be consumed."""
    out = {}
    for name in ("s3", "athena", "glue"):
        c = aws(name)
        data.clients[name] = c
        out[name] = Stubber(c)
        out[name].activate()
    yield out
    for s in out.values():
        s.assert_no_pending_responses()
        s.deactivate()


def event(method, path, query=None, body=None, key=KEY, headers=None, b64=False):
    h = {"x-api-key": key} if key else {}
    h.update(headers or {})
    raw = body if body is None or isinstance(body, str) else json.dumps(body)
    if raw is not None and b64:
        raw = base64.b64encode(raw.encode()).decode()
    return {"version": "2.0", "rawPath": path, "rawQueryString": "", "queryStringParameters": query, "headers": h,
            "requestContext": {"http": {"method": method}}, "body": raw, "isBase64Encoded": b64}


def call(*args, **kwargs):
    r = handler.lambda_handler(event(*args, **kwargs))
    return r["statusCode"], json.loads(r["body"]) if r.get("body") else None


# --- Athena stubbing --------------------------------------------------------------------------

def stub_query(stub, columns, rows, params=None, running=1, page_size=None):
    """Queue start -> `running` RUNNING polls -> SUCCEEDED -> result pages (header row first)."""
    expected = {"QueryString": ANY, "WorkGroup": "bus-history", "QueryExecutionContext": {"Database": "bus_history"}}
    if params is not None:
        expected["ExecutionParameters"] = params
    stub.add_response("start_query_execution", {"QueryExecutionId": "q1"}, expected)
    for _ in range(running):
        stub.add_response("get_query_execution", {"QueryExecution": {"QueryExecutionId": "q1",
                                                                     "Status": {"State": "RUNNING"}}})
    stub.add_response("get_query_execution", {"QueryExecution": {
        "QueryExecutionId": "q1", "Status": {"State": "SUCCEEDED"},
        "Statistics": {"DataScannedInBytes": 1234, "TotalExecutionTimeInMillis": 800}}})
    info = [{"Name": n, "Type": t} for n, t in columns]
    all_rows = [[{"VarCharValue": n} for n, _ in columns]] + [
        [{} if v is None else {"VarCharValue": v} for v in r] for r in rows]
    size = page_size or len(all_rows)
    chunks = [all_rows[i:i + size] for i in range(0, len(all_rows), size)]
    for i, chunk in enumerate(chunks):
        page = {"ResultSet": {"Rows": [{"Data": r} for r in chunk], "ResultSetMetadata": {"ColumnInfo": info}}}
        if i < len(chunks) - 1:
            page["NextToken"] = f"t{i}"
        stub.add_response("get_query_results", page)


def captured_sql(client) -> list[str]:
    seen = []
    client.meta.events.register("provide-client-params.athena.StartQueryExecution",
                                lambda params, **_: seen.append(params["QueryString"]))
    return seen


# --- Auth and routing -------------------------------------------------------------------------

def test_health_needs_no_key():
    status, body = call("GET", "/v1/health", key=None)
    assert status == 200 and body["status"] == "ok"


@pytest.mark.parametrize("headers", [{}, {"x-api-key": "wrong"}, {"authorization": "Bearer wrong"},
                                     {"authorization": f"Basic {KEY}"}])
def test_missing_or_wrong_key_is_401(headers):
    status, body = call("GET", "/v1/lines", key=None, headers=headers)
    assert status == 401 and body["error"]["code"] == "unauthorized"


def test_bearer_token_is_accepted(caplog):
    caplog.set_level("INFO")
    status, _ = call("GET", "/v1/lines", key=None, headers={"authorization": f"Bearer {KEY}"})
    assert status == 200
    logged = json.loads(caplog.records[-1].getMessage())
    assert logged["group"] == "group-a" and logged["route"] == "GET /v1/lines"


def test_options_needs_no_key():
    assert handler.lambda_handler(event("OPTIONS", "/v1/lines", key=None))["statusCode"] == 204


def test_unknown_route_404_and_wrong_method_405():
    assert call("GET", "/v1/nope")[0] == 404
    status, body = call("DELETE", "/v1/lines")
    assert status == 405 and body["error"]["code"] == "method_not_allowed"


# --- Network and live -------------------------------------------------------------------------

def test_lines_and_line_detail():
    _, body = call("GET", "/v1/lines")
    assert [li["id"] for li in body["lines"]] == ["27", "C1"]
    assert body["lines"][1]["circular"] is True
    status, line = call("GET", "/v1/lines/27")
    assert status == 200
    assert [s["id"] for s in line["outbound"]] == ["86", "85"] and line["inbound"][0]["name"] == "Atocha"
    assert "path" in line
    assert call("GET", "/v1/lines/99")[0] == 404
    assert call("GET", "/v1/lines/bad%20id")[0] == 400


def test_stops_filtered_by_line_and_detail():
    _, body = call("GET", "/v1/stops", {"line": "C1"})
    assert [s["id"] for s in body["stops"]] == ["86", "90"]
    _, stop = call("GET", "/v1/stops/86")
    assert {li["id"]: li["directions"] for li in stop["lines"]} == {"27": [0, 1], "C1": [0]}


def test_live_endpoints():
    _, body = call("GET", "/v1/live/buses", {"line": "27"})
    assert body["count"] == 2 and body["buses"][0]["load"] == 0.5
    _, line = call("GET", "/v1/live/lines/27")
    assert line["buses_in_service"] == 2 and line["passengers"] == 54 and line["waiting"] == 7
    assert line["stops"]["outbound"][0] == {"id": "86", "name": "Embajadores", "lat": 40.40539, "lon": -3.70242,
                                            "waiting": 5}
    _, stop = call("GET", "/v1/live/stops/86")
    assert stop["waiting"] == 5 and [b["id"] for b in stop["approaching"]] == ["27-2"]


def test_network_is_read_from_the_site_bucket(stubs):
    data._cache.pop("network")
    raw = json.dumps(NETWORK).encode()
    stubs["s3"].add_response("get_object", {"Body": StreamingBody(io.BytesIO(raw), len(raw))},
                             {"Bucket": "site-bucket", "Key": "network.json"})
    assert call("GET", "/v1/lines")[0] == 200
    assert call("GET", "/v1/lines")[0] == 200  # cached: no second get_object


def test_missing_snapshot_is_503(stubs):
    data._cache.pop("snapshot")
    stubs["s3"].add_client_error("get_object", "NoSuchKey", http_status_code=404)
    assert call("GET", "/v1/live/buses")[0] == 503


# --- History ----------------------------------------------------------------------------------

LINE_COLUMNS = [("date", "date"), ("hour", "tinyint"), ("line_id", "varchar"), ("direction", "tinyint"),
                ("trips", "integer"), ("avg_load", "double"), ("avg_trip_minutes", "double")]


def test_line_hourly_uses_parameters_partitions_and_converts_types(stubs):
    sql = captured_sql(data.clients["athena"])
    params = ["'2026-09'", "'2026-10'", "'2026-09-30'", "'2026-10-01'", "'27'", "1"]
    stub_query(stubs["athena"], LINE_COLUMNS, [
        ["2026-09-30", "23", "27", "1", "4", "0.41", None],
        ["2026-10-01", "0", "27", "1", "2", "0.12", "38.5"],
    ], params=params, running=2, page_size=2)
    status, body = call("GET", "/v1/history/lines/27/hourly", {"from": "2026-09-30", "to": "2026-10-01",
                                                               "direction": "1"})
    assert status == 200, body
    assert "month IN (?, ?)" in sql[0] and "line_id = ?" in sql[0] and "'27'" not in sql[0]
    assert body["columns"] == ["date", "hour", "line_id", "direction", "trips", "avg_load", "avg_trip_minutes"]
    assert body["rows"] == [["2026-09-30", 23, "27", 1, 4, 0.41, None], ["2026-10-01", 0, "27", 1, 2, 0.12, 38.5]]
    assert body["stats"] == {"data_scanned_bytes": 1234, "execution_ms": 800}


@pytest.mark.parametrize("query, message", [
    ({}, "required"),
    ({"from": "2026-13-01"}, "YYYY-MM-DD"),
    ({"from": "2026-10-02", "to": "2026-10-01"}, "before"),
    ({"from": "2025-01-01", "to": "2026-10-01"}, "400 days"),
    ({"from": "2026-10-01", "direction": "2"}, "between 0 and 1"),
])
def test_history_validation(query, message):
    status, body = call("GET", "/v1/history/lines/27/hourly", query)
    assert status == 400 and message in body["error"]["message"]


def test_stop_hourly(stubs):
    stub_query(stubs["athena"], [("stop_id", "varchar"), ("max_waiting", "integer")], [["86", "12"]],
               params=["'2026-10'", "'2026-10-01'", "'2026-10-01'", "'86'"], running=0)
    _, body = call("GET", "/v1/history/stops/86/hourly", {"from": "2026-10-01"})
    assert body["rows"] == [["86", 12]]


def test_stop_calls_filters_limit_and_range(stubs):
    sql = captured_sql(data.clients["athena"])
    stub_query(stubs["athena"], [("ts", "timestamp"), ("terminal", "boolean"), ("left_behind", "integer")],
               [["2026-10-10 08:00:01.000", "true", "3"], ["2026-10-10 08:00:02.000", "false", "0"]],
               params=["'2026-10-09'", "'2026-10-10'", "'27'", "'27-3'"], running=0)
    _, body = call("GET", "/v1/history/stop-calls", {"from": "2026-10-09", "to": "2026-10-10", "line": "27",
                                                     "bus": "27-3", "limit": "1"})
    assert sql[0].endswith("LIMIT 1")
    assert body["rows"] == [["2026-10-10 08:00:01.000", True, 3]] and body["truncated"] is True
    assert call("GET", "/v1/history/stop-calls", {"from": "2026-10-01", "to": "2026-10-08"})[0] == 400
    assert call("GET", "/v1/history/stop-calls", {"from": "2026-10-01", "limit": "50001"})[0] == 400


def test_positions_range_is_one_day(stubs):
    stub_query(stubs["athena"], [("lat", "double")], [["40.4"]],
               params=["'2026-10-10'", "'2026-10-11'", "'27-1'", "'2026-10-10 22:00:00'", "'2026-10-11 02:00:00'"],
               running=0)
    status, body = call("GET", "/v1/history/positions", {"bus": "27-1", "from": "2026-10-10T22:00:00",
                                                         "to": "2026-10-11T02:00:00"})
    assert status == 200 and body["rows"] == [[40.4]]
    assert call("GET", "/v1/history/positions", {"bus": "27-1", "from": "2026-10-10T00:00:00",
                                                 "to": "2026-10-11T00:00:01"})[0] == 400
    assert call("GET", "/v1/history/positions", {"bus": "x';--", "from": "2026-10-10T00:00:00",
                                                 "to": "2026-10-10T01:00:00"})[0] == 400


def test_query_timeout_stops_the_query_and_returns_504(stubs, monkeypatch):
    monkeypatch.setattr(athena, "TIMEOUT_S", 0)
    stubs["athena"].add_response("start_query_execution", {"QueryExecutionId": "q1"})
    stubs["athena"].add_response("get_query_execution", {"QueryExecution": {"QueryExecutionId": "q1",
                                                                            "Status": {"State": "RUNNING"}}})
    stubs["athena"].add_response("stop_query_execution", {}, {"QueryExecutionId": "q1"})
    status, body = call("GET", "/v1/history/stops/86/hourly", {"from": "2026-10-01"})
    assert status == 504 and body["error"]["code"] == "timeout"


def test_failed_query_is_400_with_athena_reason(stubs):
    stubs["athena"].add_response("start_query_execution", {"QueryExecutionId": "q1"})
    stubs["athena"].add_response("get_query_execution", {"QueryExecution": {
        "QueryExecutionId": "q1", "Status": {"State": "FAILED", "StateChangeReason": "COLUMN_NOT_FOUND: x"}}})
    status, body = call("POST", "/v1/sql", body={"query": "SELECT x FROM line_hourly"})
    assert status == 400 and "COLUMN_NOT_FOUND" in body["error"]["message"]


# --- SQL --------------------------------------------------------------------------------------

@pytest.mark.parametrize("query, expected", [
    ("SELECT 1", "SELECT 1\nLIMIT 10000"),
    ("select * from line_hourly limit 50;", "select * from line_hourly LIMIT 50"),
    ("SELECT * FROM t LIMIT 999999", "SELECT * FROM t LIMIT 10000"),
    ("SELECT * FROM t LIMIT ALL", "SELECT * FROM t LIMIT 10000"),
    ("WITH a AS (SELECT 1 AS x) SELECT x FROM a", "WITH a AS (SELECT 1 AS x) SELECT x FROM a\nLIMIT 10000"),
    ("SELECT 'drop; delete' AS s -- LIMIT 5", "SELECT 'drop; delete' AS s\nLIMIT 10000"),
    ("SELECT \"update\" FROM t /* drop */ LIMIT 3", "SELECT \"update\" FROM t   LIMIT 3"),
    ("SELECT * FROM (SELECT * FROM t LIMIT 5)", "SELECT * FROM (SELECT * FROM t LIMIT 5)\nLIMIT 10000"),
])
def test_sql_guard_accepts_reads_and_enforces_limit(query, expected):
    assert athena.guard_sql(query) == expected


@pytest.mark.parametrize("query", [
    "", "DROP TABLE line_hourly", "SELECT 1; SELECT 2", "SELECT 1; DROP TABLE t",
    "INSERT INTO t SELECT 1", "WITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a",
    "SHOW TABLES", "SELECT * FROM t FETCH FIRST 5 ROWS ONLY", "SELECT 'unterminated",
    "CREATE TABLE x AS SELECT 1", "UNLOAD (SELECT 1) TO 's3://x/'", "/* hi */ DELETE FROM t",
    "SELECT 1 /* unterminated",
])
def test_sql_guard_rejects(query):
    with pytest.raises(athena.SqlError):
        athena.guard_sql(query)


def test_sql_endpoint_runs_guarded_query(stubs):
    sql = captured_sql(data.clients["athena"])
    stub_query(stubs["athena"], [("n", "bigint")], [["42"]], running=0)
    query = "SELECT count(*) AS n FROM stop_calls WHERE dt = '2026-10-10'"
    status, body = call("POST", "/v1/sql", body={"query": query}, b64=True)
    assert status == 200 and body["rows"] == [[42]] and sql[0].endswith("LIMIT 10000")
    assert call("POST", "/v1/sql", body={"query": "DROP TABLE t"})[0] == 400
    assert call("POST", "/v1/sql", body="not json")[0] == 400
    assert call("POST", "/v1/sql", body={"query": "SELECT " + "1" * 30000})[0] == 413


# --- Datasets ---------------------------------------------------------------------------------

def test_datasets_lists_columns_and_partitions(stubs):
    stubs["glue"].add_response("get_tables", {"TableList": [{"Name": "line_hourly", "StorageDescriptor": {
        "Columns": [{"Name": "date", "Type": "date", "Comment": "Service date"}]}}]}, {"DatabaseName": "bus_history"})
    for table, key, values in [("line_hourly", "month", ["2026-09", "2026-10"]), ("stop_hourly", "month", []),
                               ("stop_calls", "dt", ["2026-10-10"]), ("bus_positions", "dt", [])]:
        stubs["s3"].add_response("list_objects_v2", {
            "CommonPrefixes": [{"Prefix": f"history/{table}/{key}={v}/"} for v in values]},
            {"Bucket": "data-bucket", "Prefix": f"history/{table}/", "Delimiter": "/"})
    status, body = call("GET", "/v1/datasets")
    assert status == 200
    lh = body["tables"][0]
    assert lh["columns"] == [{"name": "date", "type": "date", "description": "Service date"}]
    assert lh["partitions"]["first"] == "2026-09" and lh["partitions"]["count"] == 2
    assert body["tables"][1]["partitions"]["first"] is None


def test_dataset_files_are_presigned_and_limited_to_the_range(stubs):
    stamp = datetime(2026, 10, 11, tzinfo=UTC)
    keys = ["history/stop_calls/dt=2026-10-09/a.parquet", "history/stop_calls/dt=2026-10-10/b.parquet",
            "history/stop_calls/dt=2026-10-10/_tmp", "history/stop_calls/dt=2026-10-12/c.parquet"]
    stubs["s3"].add_response("list_objects_v2", {"Contents": [
        {"Key": k, "Size": 10, "LastModified": stamp} for k in keys]},
        {"Bucket": "data-bucket", "Prefix": "history/stop_calls/", "StartAfter": "history/stop_calls/dt=2026-10-09"})
    status, body = call("GET", "/v1/datasets/stop_calls/files", {"from": "2026-10-09", "to": "2026-10-11"})
    assert status == 200 and body["count"] == 2
    assert body["files"][1]["partition"] == "2026-10-10"
    assert "/history/stop_calls/dt%3D2026-10-10/b.parquet?" in body["files"][1]["url"]
    assert "X-Amz-Expires=3600" in body["files"][0]["url"]
    assert call("GET", "/v1/datasets/nope/files", {"from": "2026-10-09"})[0] == 404


# --- MCP --------------------------------------------------------------------------------------

def rpc(method, params=None, msg_id=1, headers=None, key=KEY):
    msg = {"jsonrpc": "2.0", "method": method}
    if msg_id is not None:
        msg["id"] = msg_id
    if params is not None:
        msg["params"] = params
    return handler.lambda_handler(event("POST", "/mcp", body=msg, key=key, headers=headers))


def test_mcp_initialize_and_version_negotiation():
    r = rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                           "clientInfo": {"name": "t", "version": "1"}})
    result = json.loads(r["body"])["result"]
    assert result["protocolVersion"] == "2025-03-26" and result["serverInfo"]["name"] == "madrid-bus"
    assert "tools" in result["capabilities"]
    r = rpc("initialize", {"protocolVersion": "1999-01-01"})
    assert json.loads(r["body"])["result"]["protocolVersion"] == "2025-06-18"
    assert rpc("ping", headers={"mcp-protocol-version": "1999-01-01"})["statusCode"] == 400


def test_mcp_notifications_get_and_auth():
    r = rpc("notifications/initialized", msg_id=None)
    assert r["statusCode"] == 202 and "body" not in r
    assert json.loads(rpc("ping")["body"])["result"] == {}
    assert handler.lambda_handler(event("GET", "/mcp"))["statusCode"] == 405
    assert rpc("ping", key="wrong")["statusCode"] == 401
    bad = handler.lambda_handler(event("POST", "/mcp", body="{"))
    assert bad["statusCode"] == 400 and json.loads(bad["body"])["error"]["code"] == -32700
    assert json.loads(rpc("resources/list")["body"])["error"]["code"] == -32601


def test_mcp_tools_list_has_every_tool_with_a_schema():
    tools = json.loads(rpc("tools/list")["body"])["result"]["tools"]
    assert [t["name"] for t in tools] == [
        "list_lines", "get_line", "list_stops", "get_stop", "live_line", "live_stop", "line_hourly", "stop_hourly",
        "stop_calls", "describe_datasets", "run_sql"]
    for t in tools:
        assert t["inputSchema"]["type"] == "object" and len(t["description"]) > 40


def test_mcp_tools_call_reuses_rest_functions():
    r = json.loads(rpc("tools/call", {"name": "get_line", "arguments": {"line_id": "27"}})["body"])["result"]
    assert r["structuredContent"]["name"].startswith("Glorieta") and "path" not in r["structuredContent"]
    assert json.loads(r["content"][0]["text"]) == r["structuredContent"]
    r = json.loads(rpc("tools/call", {"name": "live_stop", "arguments": {"stop_id": "999"}})["body"])["result"]
    assert r["isError"] is True and "not_found" in r["content"][0]["text"]
    r = json.loads(rpc("tools/call", {"name": "nope", "arguments": {}})["body"])
    assert r["error"]["code"] == -32602


def test_mcp_run_sql_and_stop_calls_limits(stubs):
    stub_query(stubs["athena"], [("x", "integer")], [[str(i)] for i in range(2500)], running=0, page_size=1000)
    r = json.loads(rpc("tools/call", {"name": "run_sql", "arguments": {"query": "SELECT x FROM t"}})["body"])
    result = r["result"]["structuredContent"]
    assert result["row_count"] == mcp.MAX_ROWS and result["truncated"] is True
    r = json.loads(rpc("tools/call", {"name": "run_sql", "arguments": {"query": "DELETE FROM t"}})["body"])
    assert r["result"]["isError"] is True
    args = {"from": "2026-10-10", "limit": 5000}
    r = json.loads(rpc("tools/call", {"name": "stop_calls", "arguments": args})["body"])
    assert r["result"]["isError"] is True and "between 1 and 2000" in r["result"]["content"][0]["text"]


def test_columns_used_by_the_api_match_the_simulator_schemas():
    from sim.history import SCHEMAS

    for table, columns in [("line_hourly", data.LINE_HOURLY_COLUMNS), ("stop_hourly", data.STOP_HOURLY_COLUMNS),
                           ("stop_calls", data.STOP_CALLS_COLUMNS), ("bus_positions", data.BUS_POSITIONS_COLUMNS)]:
        assert columns.split(", ") == [name for name, _, _ in SCHEMAS[table]]
    assert set(data.TABLES) == set(SCHEMAS)
