# Madrid Bus Simulator MCP Server

Model Context Protocol (MCP) server for programmatic access to Madrid Bus Simulator time series data stored in AWS Timestream.

## Overview

The MCP server provides five tools for querying bus system data:

1. **query_people_count** - Query passenger counts at bus stops
2. **query_sensor_data** - Query sensor readings from buses and stops
3. **query_bus_position** - Query bus positions on routes
4. **query_line_buses** - Query all buses on a specific line
5. **query_time_range** - Query time series data over a time range

## Installation

### Prerequisites

- Python 3.9 or higher
- AWS credentials configured (IAM role or credentials file)
- Access to the Timestream database

### Install Dependencies

```bash
cd mcp_server
pip install -r requirements.txt
```

### Install as Package

```bash
cd mcp_server
pip install -e .
```

## Configuration

The MCP server uses environment variables for configuration:

- `TIMESTREAM_DATABASE`: Name of the Timestream database (default: `bus_simulator`)
- `AWS_REGION`: AWS region for Timestream (default: `eu-west-1`)

### MCP Client Configuration

Add the following to your MCP client configuration file (e.g., `~/.config/mcp/config.json`):

```json
{
  "mcpServers": {
    "madrid-bus-simulator": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "TIMESTREAM_DATABASE": "bus_simulator",
        "AWS_REGION": "eu-west-1"
      }
    }
  }
}
```

## Usage

### Running the Server

```bash
# Run directly
python -m mcp_server.server

# Or use the installed command
madrid-bus-mcp
```

### Tool Descriptions

#### 1. query_people_count

Query people count at a bus stop.

**Parameters:**
- `stop_id` (required): Bus stop ID (e.g., "S001")
- `mode` (optional): Set to "latest" for most recent data
- `timestamp` (optional): ISO8601 timestamp for historical query

**Example:**
```json
{
  "tool": "query_people_count",
  "arguments": {
    "stop_id": "S001",
    "mode": "latest"
  }
}
```

**Response:**
```json
{
  "success": true,
  "count": 1,
  "data": [
    {
      "stop_id": "S001",
      "time": "2024-01-15T10:30:00.000Z",
      "count": "15",
      "line_ids": "L1,L2"
    }
  ],
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

#### 2. query_sensor_data

Query sensor data for a bus or stop.

**Parameters:**
- `entity_id` (required): Bus ID (e.g., "B001") or Stop ID (e.g., "S001")
- `entity_type` (required): "bus" or "stop"
- `mode` (optional): Set to "latest" for most recent data
- `timestamp` (optional): ISO8601 timestamp for historical query

**Example:**
```json
{
  "tool": "query_sensor_data",
  "arguments": {
    "entity_id": "B001",
    "entity_type": "bus",
    "mode": "latest"
  }
}
```

**Response:**
```json
{
  "success": true,
  "count": 1,
  "data": [
    {
      "entity_id": "B001",
      "entity_type": "bus",
      "time": "2024-01-15T10:30:00.000Z",
      "temperature": "22.5",
      "humidity": "65.0",
      "co2_level": "800",
      "door_status": "closed"
    }
  ],
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

#### 3. query_bus_position

Query bus position on route.

**Parameters:**
- `bus_id` (required): Bus ID (e.g., "B001")
- `mode` (optional): Set to "latest" for most recent data
- `timestamp` (optional): ISO8601 timestamp for historical query

**Example:**
```json
{
  "tool": "query_bus_position",
  "arguments": {
    "bus_id": "B001",
    "mode": "latest"
  }
}
```

**Response:**
```json
{
  "success": true,
  "count": 1,
  "data": [
    {
      "bus_id": "B001",
      "line_id": "L1",
      "time": "2024-01-15T10:30:00.000Z",
      "latitude": "40.4657",
      "longitude": "-3.6886",
      "passenger_count": "25",
      "next_stop_id": "S002",
      "distance_to_next_stop": "350.5",
      "speed": "30.0",
      "direction": "0"
    }
  ],
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

#### 4. query_line_buses

Query all buses currently operating on a specific line.

**Parameters:**
- `line_id` (required): Bus line ID (e.g., "L1")
- `mode` (optional): Set to "latest" for most recent data

**Example:**
```json
{
  "tool": "query_line_buses",
  "arguments": {
    "line_id": "L1",
    "mode": "latest"
  }
}
```

**Response:**
```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "bus_id": "B001",
      "line_id": "L1",
      "time": "2024-01-15T10:30:00.000Z",
      "latitude": "40.4657",
      "longitude": "-3.6886",
      "passenger_count": "25",
      "next_stop_id": "S002",
      "distance_to_next_stop": "350.5",
      "speed": "30.0",
      "direction": "0"
    },
    {
      "bus_id": "B002",
      "line_id": "L1",
      "time": "2024-01-15T10:30:00.000Z",
      "latitude": "40.4500",
      "longitude": "-3.6900",
      "passenger_count": "18",
      "next_stop_id": "S005",
      "distance_to_next_stop": "120.0",
      "speed": "25.0",
      "direction": "1"
    }
  ],
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

#### 5. query_time_range

Query time series data for a specific entity over a time range.

**Parameters:**
- `data_type` (required): "people_count", "sensors", or "bus_position"
- `entity_id` (required): Entity ID (stop, bus, or line)
- `start_time` (required): ISO8601 start timestamp
- `end_time` (required): ISO8601 end timestamp

**Example:**
```json
{
  "tool": "query_time_range",
  "arguments": {
    "data_type": "people_count",
    "entity_id": "S001",
    "start_time": "2024-01-15T08:00:00Z",
    "end_time": "2024-01-15T12:00:00Z"
  }
}
```

**Response:**
```json
{
  "success": true,
  "count": 240,
  "data": [
    {
      "stop_id": "S001",
      "time": "2024-01-15T08:00:00.000Z",
      "count": "5",
      "line_ids": "L1,L2"
    },
    {
      "stop_id": "S001",
      "time": "2024-01-15T08:01:00.000Z",
      "count": "7",
      "line_ids": "L1,L2"
    }
  ],
  "timestamp": "2024-01-15T12:00:05.123Z"
}
```

## Error Handling

All tools return structured error responses when errors occur:

```json
{
  "success": false,
  "error": "Error message describing what went wrong",
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

Common errors:
- Invalid entity ID (stop, bus, or line not found)
- Invalid timestamp format (must be ISO8601)
- Invalid data_type parameter
- Timestream query errors
- AWS authentication errors

## AWS Permissions

The MCP server requires the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "timestream:DescribeEndpoints",
        "timestream:Select"
      ],
      "Resource": "*"
    }
  ]
}
```

## Development

### Running Tests

```bash
cd dataviz-bus-realtime
pytest tests/test_mcp_*.py -v
```

### Testing with Mock Data

For local development without AWS access, you can mock the Timestream client:

```python
from unittest.mock import Mock
import asyncio

# Mock Timestream client
mock_client = Mock()
mock_client.query.return_value = {
    'Rows': [
        {
            'Data': [
                {'ScalarValue': 'S001'},
                {'ScalarValue': '2024-01-15T10:30:00.000Z'},
                {'ScalarValue': '15'},
                {'ScalarValue': 'L1,L2'}
            ]
        }
    ],
    'ColumnInfo': [
        {'Name': 'stop_id'},
        {'Name': 'time'},
        {'Name': 'count'},
        {'Name': 'line_ids'}
    ]
}

# Use mock in server
server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
server.timestream_client = mock_client
```

## Troubleshooting

### Server won't start

1. Check AWS credentials are configured:
   ```bash
   aws sts get-caller-identity
   ```

2. Verify Timestream database exists:
   ```bash
   aws timestream-query describe-database --database-name bus_simulator
   ```

3. Check Python version:
   ```bash
   python --version  # Should be 3.9+
   ```

### Queries return no data

1. Verify data exists in Timestream:
   ```bash
   aws timestream-query query --query-string "SELECT * FROM bus_simulator.people_count LIMIT 1"
   ```

2. Check entity IDs match configuration in `data/lines.yaml`

3. Verify timestamp format is ISO8601 (e.g., "2024-01-15T10:30:00Z")

### Permission errors

Ensure your AWS credentials have the required Timestream permissions. Check IAM policy attached to your user/role.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
