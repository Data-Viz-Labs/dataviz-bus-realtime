"""MCP server over Streamable HTTP: stateless, JSON responses only (no SSE stream).

Each tool calls the same function as its REST route, with its arguments as parameters.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
import json
import logging

import api_data as service

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")
SERVER_INFO = {"name": "madrid-bus", "title": "Madrid bus simulator", "version": "1.0.0"}
MAX_ROWS = 2000  # rows handed to a model in one tool result
INSTRUCTIONS = (
    "Simulated EMT Madrid bus network: 40 real lines, 1,723 real stops, about 700 buses, simulated in real "
    "time. Static network: list_lines, get_line, list_stops, get_stop. Live state (refreshed every 5 s): "
    "live_line, live_stop. History: line_hourly and stop_hourly (years of hourly aggregates), stop_calls "
    "(every bus call at a stop, last days only). For anything else call describe_datasets, then run_sql "
    "(Athena SQL, aggregate in SQL rather than fetching raw rows, always filter month= or dt= partitions). "
    "Times are Madrid local time. Load = passengers / nominal capacity."
)

log = logging.getLogger(__name__)

DATE = {"type": "string", "format": "date", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
LINE_ID = {"type": "string", "description": "EMT line id, e.g. \"27\" or \"C1\" (list_lines)"}
STOP_ID = {"type": "string", "description": "EMT stop code as a string, e.g. \"86\""}


def _obj(properties: dict, required: tuple[str, ...] = ()) -> dict:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


@dataclass
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict
    fn: Callable[[dict], dict]
    fixed: dict = field(default_factory=dict)  # parameters added to every call

    def definition(self) -> dict:
        return {"name": self.name, "title": self.title, "description": self.description,
                "inputSchema": self.input_schema, "annotations": {"readOnlyHint": True, "openWorldHint": False}}


TOOLS = [
    Tool("list_lines", "List lines",
         "All bus lines: id, name (terminus - terminus), colour, nominal bus capacity (passengers), fleet size and "
         "number of stops per direction.",
         _obj({}), service.list_lines),
    Tool("get_line", "Get line",
         "One line with its ordered stops: outbound (direction 0) and inbound (direction 1, empty for circular "
         "lines), each with id, name and coordinates.",
         _obj({"line_id": LINE_ID}, ("line_id",)), service.get_line, {"include_path": "false"}),
    Tool("list_stops", "List stops",
         "Stops with coordinates and the lines serving them. Pass line to get only that line's stops, in route "
         "order (1,723 stops otherwise).",
         _obj({"line": LINE_ID}), service.list_stops),
    Tool("get_stop", "Get stop",
         "One stop: name, coordinates and the lines (and directions) that call at it.",
         _obj({"stop_id": STOP_ID}, ("stop_id",)), service.get_stop),
    Tool("live_line", "Live line",
         "Live state of a line now: every bus in service (position, direction, passengers, load) and people "
         "waiting at each of its stops (all lines at that stop), plus totals.",
         _obj({"line_id": LINE_ID}, ("line_id",)), service.live_line),
    Tool("live_stop", "Live stop",
         "Live state of a stop now: people waiting and the buses heading to it next.",
         _obj({"stop_id": STOP_ID}, ("stop_id",)), service.live_stop),
    Tool("line_hourly", "Line hourly history",
         "Hourly aggregates of a line between two dates (inclusive, max 400 days): trips, boardings, alightings, "
         "avg/max load (passengers / capacity, can exceed 1), average trip and wait minutes. Result: columns + "
         f"rows. At most {MAX_ROWS} rows are returned: for long ranges aggregate with run_sql.",
         _obj({"line_id": LINE_ID, "from": {**DATE, "description": "First day YYYY-MM-DD"},
               "to": {**DATE, "description": "Last day YYYY-MM-DD (default: from)"},
               "direction": {"type": "integer", "enum": [0, 1], "description": "0 outbound, 1 inbound (default both)"}},
              ("line_id", "from")),
         service.line_hourly),
    Tool("stop_hourly", "Stop hourly history",
         "Hourly aggregates of a stop (all lines) between two dates (inclusive, max 400 days): boardings, "
         "alightings, mean and max people waiting, bus calls.",
         _obj({"stop_id": STOP_ID, "from": {**DATE, "description": "First day YYYY-MM-DD"},
               "to": {**DATE, "description": "Last day YYYY-MM-DD (default: from)"}}, ("stop_id", "from")),
         service.stop_hourly),
    Tool("stop_calls", "Stop calls",
         "Raw bus calls at stops (only the last days are kept; max 7 days per call): time, bus, line, direction, "
         "stop, alighted, boarded, passengers after, left_behind (people who could not board a full bus). Filter "
         "by line, stop and/or bus.",
         _obj({"from": {**DATE, "description": "First day YYYY-MM-DD"},
               "to": {**DATE, "description": "Last day YYYY-MM-DD (default: from)"},
               "line": LINE_ID, "stop": STOP_ID,
               "bus": {"type": "string", "description": "Bus id <line>-<n>, e.g. \"27-3\""},
               "limit": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS, "default": 500}},
              ("from",)),
         lambda p: service.stop_calls(p, default_limit=500, max_limit=MAX_ROWS)),
    Tool("describe_datasets", "Describe datasets",
         "Tables available to run_sql: columns with types and meaning, partition key and the partitions that "
         "exist (date coverage), SQL notes and examples. Call this before writing SQL.",
         _obj({}), service.datasets),
    Tool("run_sql", "Run SQL",
         "Run one read-only Athena (Trino) SELECT or WITH query on the history tables (line_hourly, stop_hourly, "
         "stop_calls, bus_positions). Filter partitions (month = 'YYYY-MM' or dt = 'YYYY-MM-DD') to keep it fast; "
         f"aggregate in SQL. A LIMIT of 10000 is enforced and at most {MAX_ROWS} rows are returned here.",
         _obj({"query": {"type": "string", "description": "SQL query"}}, ("query",)), service.run_sql),
]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def _arg(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def call_tool(name: str, arguments: dict) -> dict:
    tool = TOOLS_BY_NAME[name]
    params = {k: _arg(v) for k, v in arguments.items() if v is not None}
    try:
        result = tool.fn({**params, **tool.fixed})
    except service.ApiError as e:
        return {"content": [{"type": "text", "text": f"{e.code}: {e.message}"}], "isError": True}
    except Exception:
        log.exception("tool %s failed", name)
        return {"content": [{"type": "text", "text": "internal error, try again later"}], "isError": True}
    if len(result.get("rows", [])) > MAX_ROWS:
        result = {**result, "rows": result["rows"][:MAX_ROWS], "row_count": MAX_ROWS, "truncated": True}
    return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, separators=(",", ":"))}],
            "structuredContent": result}


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _dispatch(msg) -> tuple[dict | None, str]:
    """Answer one JSON-RPC message: (response or None for notifications, label for the log)."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        return _error(None, -32600, "invalid JSON-RPC 2.0 message"), "invalid"
    method, msg_id = msg.get("method"), msg.get("id")
    if "id" not in msg or method is None:  # notification, or a response to a server request
        return None, method or "response"
    params = msg.get("params") or {}
    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return {"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": version, "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS,
        }}, method
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}, method
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": [t.definition() for t in TOOLS]}}, method
    if method == "tools/call":
        name, arguments = params.get("name"), params.get("arguments") or {}
        if name not in TOOLS_BY_NAME:
            return _error(msg_id, -32602, f"unknown tool: {name}"), method
        if not isinstance(arguments, dict):
            return _error(msg_id, -32602, "arguments must be an object"), method
        return {"jsonrpc": "2.0", "id": msg_id, "result": call_tool(name, arguments)}, f"{method}:{name}"
    return _error(msg_id, -32601, f"method not found: {method}"), method


def handle(body: str, headers: dict) -> tuple[int, dict | list | None, str]:
    """One HTTP POST: (status, JSON body or None for 202, label for the log)."""
    try:
        message = json.loads(body or "")
    except ValueError:
        return 400, _error(None, -32700, "parse error: body must be JSON"), "parse-error"
    version = headers.get("mcp-protocol-version")
    initializing = isinstance(message, dict) and message.get("method") == "initialize"
    if version and version not in PROTOCOL_VERSIONS and not initializing:
        return 400, _error(None, -32600, f"unsupported MCP-Protocol-Version {version}"), "bad-version"
    if isinstance(message, list):  # JSON-RPC batch (protocol 2025-03-26)
        if not message:
            return 400, _error(None, -32600, "empty batch"), "invalid"
        answers = [_dispatch(m) for m in message]
        responses = [r for r, _ in answers if r is not None]
        return (200, responses, "batch") if responses else (202, None, "batch")
    response, label = _dispatch(message)
    return (202, None, label) if response is None else (200, response, label)
