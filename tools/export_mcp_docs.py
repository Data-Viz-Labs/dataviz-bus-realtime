"""Regenerate the tool reference of docs/api/mcp.md from the MCP server's tool definitions.

    python tools/export_mcp_docs.py [--check]

Rewrites the text between the ``<!-- tools:start -->`` and ``<!-- tools:end -->`` markers.
With ``--check`` it only exits 1 when the file is out of date.
"""

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "api" / "mcp.md"
START, END = "<!-- tools:start -->", "<!-- tools:end -->"

# Example arguments and an abridged, illustrative result per tool.
EXAMPLES: dict[str, tuple[dict, dict]] = {
    "list_lines": ({}, {"lines": [{"id": "27", "name": "Glorieta de Embajadores - Plaza de Castilla",
                                   "color": "#0178bc", "capacity": 90, "buses": 25, "stops_outbound": 27,
                                   "stops_inbound": 27, "circular": False}, "..."]}),
    "get_line": ({"line_id": "27"}, {"id": "27", "name": "Glorieta de Embajadores - Plaza de Castilla",
                                     "capacity": 90, "buses": 25, "circular": False,
                                     "outbound": [{"id": "86", "name": "Embajadores", "lat": 40.40539,
                                                   "lon": -3.70242}, "..."], "inbound": ["..."]}),
    "list_stops": ({"line": "27"}, {"stops": [{"id": "86", "name": "Embajadores", "lat": 40.40539,
                                               "lon": -3.70242, "lines": ["27"]}, "..."]}),
    "get_stop": ({"stop_id": "86"}, {"id": "86", "name": "Embajadores", "lat": 40.40539, "lon": -3.70242,
                                     "lines": [{"id": "27", "name": "Glorieta de Embajadores - Plaza de Castilla",
                                                "color": "#0178bc", "directions": [0, 1]}]}),
    "live_line": ({"line_id": "27"}, {"time": "2026-10-11T08:00:05+02:00", "line_id": "27", "capacity": 90,
                                      "buses_in_service": 25, "passengers": 1240, "waiting": 310,
                                      "buses": [{"id": "27-3", "line": "27", "lat": 40.41234, "lon": -3.69321,
                                                 "passengers": 54, "direction": 0, "load": 0.6}, "..."],
                                      "stops": {"outbound": [{"id": "86", "name": "Embajadores",
                                                              "waiting": 12}, "..."], "inbound": ["..."]}}),
    "live_stop": ({"stop_id": "86"}, {"time": "2026-10-11T08:00:05+02:00", "id": "86", "name": "Embajadores",
                                      "lines": ["27"], "waiting": 12, "approaching": ["..."]}),
    "line_hourly": ({"line_id": "27", "from": "2026-10-01", "to": "2026-10-07", "direction": 0},
                    {"line_id": "27", "columns": ["date", "hour", "line_id", "direction", "trips", "boardings",
                                                  "alightings", "avg_load", "max_load", "avg_trip_minutes",
                                                  "avg_wait_minutes"],
                     "rows": [["2026-10-01", 8, "27", 0, 11, 1843, 1790, 0.62, 1.04, 47.5, 2.4], "..."],
                     "row_count": 168, "truncated": False}),
    "stop_hourly": ({"stop_id": "86", "from": "2026-10-01"},
                    {"stop_id": "86", "columns": ["date", "hour", "stop_id", "boardings", "alightings",
                                                  "avg_waiting", "max_waiting", "bus_calls"],
                     "rows": [["2026-10-01", 8, "86", 412, 95, 9.3, 31, 24], "..."], "row_count": 24}),
    "stop_calls": ({"from": "2026-10-10", "line": "27", "stop": "86", "limit": 100},
                   {"columns": ["ts", "bus_id", "line_id", "direction", "stop_id", "terminal", "alighted",
                                "boarded", "passengers_after", "left_behind"],
                    "rows": [["2026-10-10 08:01:12.000", "27-3", "27", 0, "86", False, 0, 38, 38, 0], "..."]}),
    "describe_datasets": ({}, {"database": "madrid_bus_history", "tables": [
        {"name": "line_hourly", "partition_key": "month",
         "partitions": {"count": 37, "first": "2023-10", "last": "2026-10"},
         "columns": [{"name": "avg_load", "type": "double",
                      "description": "Mean passengers / nominal capacity over buses in service (can exceed 1)"},
                     "..."]}, "..."]}),
    "run_sql": ({"query": "SELECT hour, round(avg(avg_load), 3) AS load FROM line_hourly "
                          "WHERE month BETWEEN '2026-01' AND '2026-06' AND line_id = '27' GROUP BY hour ORDER BY hour"},
                {"query": "... LIMIT 10000", "columns": ["hour", "load"], "types": ["tinyint", "double"],
                 "rows": [[7, 0.41], [8, 0.66], "..."], "row_count": 24}),
}


def load_tools() -> list:
    sys.path.insert(0, str(REPO / "lambdas" / "api"))
    import api_mcp

    return api_mcp.TOOLS


def render(tools: list) -> str:
    out = []
    for tool in tools:
        args, result = EXAMPLES.get(tool.name, ({}, {}))
        call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": tool.name, "arguments": args}}
        out += [
            f"### `{tool.name}`", "", tool.description, "",
            "<details><summary>Input schema</summary>", "",
            "```json", json.dumps(tool.input_schema, indent=2, ensure_ascii=False), "```", "", "</details>", "",
            "Call:", "", "```json", json.dumps(call, ensure_ascii=False), "```", "",
            "Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):", "",
            "```json", json.dumps(result, ensure_ascii=False), "```", "",
        ]
    return "\n".join(out)


def update(text: str, tools: list) -> str:
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n\n{render(tools)}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--check", action="store_true", help="exit 1 if docs/api/mcp.md is out of date")
    args = p.parse_args(argv)
    text = DOC.read_text()
    new = update(text, load_tools())
    if args.check:
        return int(new != text)
    DOC.write_text(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
