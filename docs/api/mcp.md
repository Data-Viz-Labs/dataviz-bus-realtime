# MCP server: the Madrid bus data for AI agents

The API also speaks the [Model Context Protocol](https://modelcontextprotocol.io) (MCP), so an
AI agent (Claude Code, Claude Desktop, Cursor, VS Code, your own agent) can explore the network,
look at the live buses and query years of history by itself, then help you build a story from it.

| | |
|---|---|
| URL | `<api_url>/mcp` (`terraform output mcp_url`) |
| Transport | Streamable HTTP, stateless, JSON responses (no SSE stream; `GET /mcp` returns 405) |
| Protocol versions | `2025-06-18` (preferred), `2025-03-26` |
| Auth | Your group key: `x-api-key: <key>` or `Authorization: Bearer <key>` |
| Server name | `madrid-bus` |
| Capabilities | `tools` (11 read-only tools, below) |

The tools call exactly the same code as the REST API (`openapi.yaml`): same data, same limits,
same errors. Tool errors (unknown line, invalid SQL, query timeout) come back as a result with
`isError: true` and a readable message, so the agent can correct itself. Tool results carry the
data both as `structuredContent` and as JSON text in `content[0].text`. Tabular results are capped
at 2,000 rows per call: ask the agent to aggregate in SQL instead of pulling raw rows.

## Connect a client

Replace `MCP_URL` with `terraform output -raw mcp_url` and `KEY` with your group key.

**Claude Code**

```bash
claude mcp add --transport http madrid-bus MCP_URL --header "x-api-key: KEY"
claude mcp list          # madrid-bus: ... - Connected
```

**Cursor** (`~/.cursor/mcp.json`) and other clients that accept a URL with headers:

```json
{
  "mcpServers": {
    "madrid-bus": {
      "url": "MCP_URL",
      "headers": { "x-api-key": "KEY" }
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "madrid-bus": {
      "type": "http",
      "url": "MCP_URL",
      "headers": { "x-api-key": "KEY" }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`) through the `mcp-remote` bridge (needs Node.js):

```json
{
  "mcpServers": {
    "madrid-bus": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "MCP_URL", "--header", "x-api-key:${MADRID_BUS_KEY}"],
      "env": { "MADRID_BUS_KEY": "KEY" }
    }
  }
}
```

`examples/mcp_config.json` holds the generic form.

**By hand** (to check your key):

```bash
curl -s MCP_URL -H "x-api-key: KEY" -H "content-type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"live_line","arguments":{"line_id":"27"}}}'
```

## Data in one paragraph

40 real EMT Madrid lines (ids such as `"27"`, `"C1"`), 1,723 real stops (codes are strings such
as `"86"`), about 700 buses (ids `<line>-<n>`). Direction `0` is outbound, `1` inbound (circular
lines only have `0`). Load = passengers / nominal capacity (90 for line 27), above 1 when crowded.
Times are Madrid local time. History: `line_hourly` and `stop_hourly` (years, partition
`month='YYYY-MM'`), `stop_calls` and `bus_positions` (last days, partition `dt='YYYY-MM-DD'`).
The data is simulated from the real network and a daily demand profile.

## Example prompts

- "Which 5 lines are the most crowded at 8 am on weekdays this year? Show average and max load."
- "Tell the story of line 27 on a typical Monday: when do buses fill up, where do people wait the
  longest, and how long does a trip take at rush hour compared with midday?"
- "Compare September with July for all lines: which lines lose the most riders in summer?"
- "Find yesterday's stop calls where people were left behind because the bus was full. Which stops
  and hours? Draft a short headline and three bullet points for a news piece."
- "Right now, which stop of line 27 has the most people waiting, and how far is the next bus?"
- "Build a weekly table of boardings at stop 86 for the last year and describe the trend."

Tip: ask the agent to call `describe_datasets` first and to always filter `month`/`dt`.

## Tools

<!-- tools:start -->

### `list_lines`

All bus lines: id, name (terminus - terminus), colour, nominal bus capacity (passengers), fleet size and number of stops per direction.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_lines", "arguments": {}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"lines": [{"id": "27", "name": "Glorieta de Embajadores - Plaza de Castilla", "color": "#0178bc", "capacity": 90, "buses": 25, "stops_outbound": 27, "stops_inbound": 27, "circular": false}, "..."]}
```

### `get_line`

One line with its ordered stops: outbound (direction 0) and inbound (direction 1, empty for circular lines), each with id, name and coordinates.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "line_id": {
      "type": "string",
      "description": "EMT line id, e.g. \"27\" or \"C1\" (list_lines)"
    }
  },
  "required": [
    "line_id"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_line", "arguments": {"line_id": "27"}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"id": "27", "name": "Glorieta de Embajadores - Plaza de Castilla", "capacity": 90, "buses": 25, "circular": false, "outbound": [{"id": "86", "name": "Embajadores", "lat": 40.40539, "lon": -3.70242}, "..."], "inbound": ["..."]}
```

### `list_stops`

Stops with coordinates and the lines serving them. Pass line to get only that line's stops, in route order (1,723 stops otherwise).

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "line": {
      "type": "string",
      "description": "EMT line id, e.g. \"27\" or \"C1\" (list_lines)"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_stops", "arguments": {"line": "27"}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"stops": [{"id": "86", "name": "Embajadores", "lat": 40.40539, "lon": -3.70242, "lines": ["27"]}, "..."]}
```

### `get_stop`

One stop: name, coordinates and the lines (and directions) that call at it.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "stop_id": {
      "type": "string",
      "description": "EMT stop code as a string, e.g. \"86\""
    }
  },
  "required": [
    "stop_id"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "get_stop", "arguments": {"stop_id": "86"}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"id": "86", "name": "Embajadores", "lat": 40.40539, "lon": -3.70242, "lines": [{"id": "27", "name": "Glorieta de Embajadores - Plaza de Castilla", "color": "#0178bc", "directions": [0, 1]}]}
```

### `live_line`

Live state of a line now: every bus in service (position, direction, passengers, load) and people waiting at each of its stops (all lines at that stop), plus totals.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "line_id": {
      "type": "string",
      "description": "EMT line id, e.g. \"27\" or \"C1\" (list_lines)"
    }
  },
  "required": [
    "line_id"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "live_line", "arguments": {"line_id": "27"}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"time": "2026-10-11T08:00:05+02:00", "line_id": "27", "capacity": 90, "buses_in_service": 25, "passengers": 1240, "waiting": 310, "buses": [{"id": "27-3", "line": "27", "lat": 40.41234, "lon": -3.69321, "passengers": 54, "direction": 0, "load": 0.6}, "..."], "stops": {"outbound": [{"id": "86", "name": "Embajadores", "waiting": 12}, "..."], "inbound": ["..."]}}
```

### `live_stop`

Live state of a stop now: people waiting and the buses heading to it next.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "stop_id": {
      "type": "string",
      "description": "EMT stop code as a string, e.g. \"86\""
    }
  },
  "required": [
    "stop_id"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "live_stop", "arguments": {"stop_id": "86"}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"time": "2026-10-11T08:00:05+02:00", "id": "86", "name": "Embajadores", "lines": ["27"], "waiting": 12, "approaching": ["..."]}
```

### `line_hourly`

Hourly aggregates of a line between two dates (inclusive, max 400 days): trips, boardings, alightings, avg/max load (passengers / capacity, can exceed 1), average trip and wait minutes. Result: columns + rows. At most 2000 rows are returned: for long ranges aggregate with run_sql.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "line_id": {
      "type": "string",
      "description": "EMT line id, e.g. \"27\" or \"C1\" (list_lines)"
    },
    "from": {
      "type": "string",
      "format": "date",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "description": "First day YYYY-MM-DD"
    },
    "to": {
      "type": "string",
      "format": "date",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "description": "Last day YYYY-MM-DD (default: from)"
    },
    "direction": {
      "type": "integer",
      "enum": [
        0,
        1
      ],
      "description": "0 outbound, 1 inbound (default both)"
    }
  },
  "required": [
    "line_id",
    "from"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "line_hourly", "arguments": {"line_id": "27", "from": "2026-10-01", "to": "2026-10-07", "direction": 0}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"line_id": "27", "columns": ["date", "hour", "line_id", "direction", "trips", "boardings", "alightings", "avg_load", "max_load", "avg_trip_minutes", "avg_wait_minutes"], "rows": [["2026-10-01", 8, "27", 0, 11, 1843, 1790, 0.62, 1.04, 47.5, 2.4], "..."], "row_count": 168, "truncated": false}
```

### `stop_hourly`

Hourly aggregates of a stop (all lines) between two dates (inclusive, max 400 days): boardings, alightings, mean and max people waiting, bus calls.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "stop_id": {
      "type": "string",
      "description": "EMT stop code as a string, e.g. \"86\""
    },
    "from": {
      "type": "string",
      "format": "date",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "description": "First day YYYY-MM-DD"
    },
    "to": {
      "type": "string",
      "format": "date",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "description": "Last day YYYY-MM-DD (default: from)"
    }
  },
  "required": [
    "stop_id",
    "from"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "stop_hourly", "arguments": {"stop_id": "86", "from": "2026-10-01"}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"stop_id": "86", "columns": ["date", "hour", "stop_id", "boardings", "alightings", "avg_waiting", "max_waiting", "bus_calls"], "rows": [["2026-10-01", 8, "86", 412, 95, 9.3, 31, 24], "..."], "row_count": 24}
```

### `stop_calls`

Raw bus calls at stops (only the last days are kept; max 7 days per call): time, bus, line, direction, stop, alighted, boarded, passengers after, left_behind (people who could not board a full bus). Filter by line, stop and/or bus.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "from": {
      "type": "string",
      "format": "date",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "description": "First day YYYY-MM-DD"
    },
    "to": {
      "type": "string",
      "format": "date",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "description": "Last day YYYY-MM-DD (default: from)"
    },
    "line": {
      "type": "string",
      "description": "EMT line id, e.g. \"27\" or \"C1\" (list_lines)"
    },
    "stop": {
      "type": "string",
      "description": "EMT stop code as a string, e.g. \"86\""
    },
    "bus": {
      "type": "string",
      "description": "Bus id <line>-<n>, e.g. \"27-3\""
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 2000,
      "default": 500
    }
  },
  "required": [
    "from"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "stop_calls", "arguments": {"from": "2026-10-10", "line": "27", "stop": "86", "limit": 100}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"columns": ["ts", "bus_id", "line_id", "direction", "stop_id", "terminal", "alighted", "boarded", "passengers_after", "left_behind"], "rows": [["2026-10-10 08:01:12.000", "27-3", "27", 0, "86", false, 0, 38, 38, 0], "..."]}
```

### `describe_datasets`

Tables available to run_sql: columns with types and meaning, partition key and the partitions that exist (date coverage), SQL notes and examples. Call this before writing SQL.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "describe_datasets", "arguments": {}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"database": "madrid_bus_history", "tables": [{"name": "line_hourly", "partition_key": "month", "partitions": {"count": 37, "first": "2023-10", "last": "2026-10"}, "columns": [{"name": "avg_load", "type": "double", "description": "Mean passengers / nominal capacity over buses in service (can exceed 1)"}, "..."]}, "..."]}
```

### `run_sql`

Run one read-only Athena (Trino) SELECT or WITH query on the history tables (line_hourly, stop_hourly, stop_calls, bus_positions). Filter partitions (month = 'YYYY-MM' or dt = 'YYYY-MM-DD') to keep it fast; aggregate in SQL. A LIMIT of 10000 is enforced and at most 2000 rows are returned here.

<details><summary>Input schema</summary>

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "SQL query"
    }
  },
  "required": [
    "query"
  ],
  "additionalProperties": false
}
```

</details>

Call:

```json
{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "run_sql", "arguments": {"query": "SELECT hour, round(avg(avg_load), 3) AS load FROM line_hourly WHERE month BETWEEN '2026-01' AND '2026-06' AND line_id = '27' GROUP BY hour ORDER BY hour"}}}
```

Result (`structuredContent`, abridged; `content[0].text` holds the same JSON):

```json
{"query": "... LIMIT 10000", "columns": ["hour", "load"], "types": ["tinyint", "double"], "rows": [[7, 0.41], [8, 0.66], "..."], "row_count": 24}
```

<!-- tools:end -->
