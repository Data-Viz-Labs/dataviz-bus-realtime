# API Documentation - User Interface Layer

This document provides comprehensive documentation for all consumption layers of the Madrid Bus Real-Time Simulator: REST API, WebSocket API, and MCP Server.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [REST API](#rest-api)
4. [WebSocket API](#websocket-api)
5. [MCP Server](#mcp-server)
6. [Error Handling](#error-handling)
7. [Rate Limits](#rate-limits)
8. [Examples](#examples)

---

## Overview

The Madrid Bus Real-Time Simulator provides three consumption layers:

### REST API
- **Purpose**: Query latest and historical data
- **Protocol**: HTTPS
- **Authentication**: API key via headers
- **Use Cases**: Dashboard displays, historical analysis, batch queries

### WebSocket API
- **Purpose**: Real-time streaming updates
- **Protocol**: WSS (WebSocket Secure)
- **Authentication**: API key via query parameters
- **Use Cases**: Live tracking, real-time dashboards, event-driven applications

### MCP Server
- **Purpose**: Programmatic access via Model Context Protocol
- **Protocol**: HTTPS (via API Gateway)
- **Authentication**: API key via headers
- **Use Cases**: AI agents, automated workflows, batch processing

---

## Authentication

All APIs require authentication using an API key and group name.

### Getting Your Credentials

1. **API Key**: Retrieved from AWS Secrets Manager
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id bus-simulator/api-key \
     --query SecretString --output text | jq -r '.api_key'
   ```

2. **Group Name**: Your team/group identifier (any string value)

### REST API Authentication

Include these headers in every request:

```http
x-api-key: your-api-key-here
x-group-name: your-group-name
```

**Example:**
```bash
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: team-alpha" \
     "$API_URL/people-count/S001?mode=latest"
```

### WebSocket Authentication

Include authentication as query parameters:

```
wss://{endpoint}?api_key=your-api-key&group_name=your-group-name
```

**Example:**
```javascript
const ws = new WebSocket(
  `wss://${endpoint}?api_key=${apiKey}&group_name=${groupName}`
);
```

### MCP Server Authentication

Same as REST API - include headers in every request:

```bash
curl -X POST "$MCP_ENDPOINT/mcp/call-tool" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json" \
  -d '{"tool": "query_people_count", "arguments": {...}}'
```

---

## REST API

### Base URL

```
https://{api-id}.execute-api.{region}.amazonaws.com
```

Get from Terraform outputs:
```bash
cd terraform
terraform output http_api_endpoint
```

### Endpoints

#### 1. People Count API

Query the number of people waiting at bus stops.

**Get Latest People Count**

```http
GET /people-count/{stop_id}?mode=latest
```

**Parameters:**
- `stop_id` (path, required): Bus stop identifier (e.g., "S001")
- `mode` (query, required): Must be "latest"

**Response:**
```json
{
  "stop_id": "S001",
  "time": "2026-02-22T10:30:00Z",
  "count": 15,
  "line_ids": "L1,L2"
}
```

**Get Historical People Count**

```http
GET /people-count/{stop_id}?timestamp={ISO8601}
```

**Parameters:**
- `stop_id` (path, required): Bus stop identifier
- `timestamp` (query, required): ISO 8601 timestamp (e.g., "2026-02-22T10:00:00Z")

**Example:**
```bash
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: team-alpha" \
     "$API_URL/people-count/S001?timestamp=2026-02-22T10:00:00Z"
```

#### 2. Sensors API

Query sensor readings from buses and stops.

**Get Latest Sensor Data**

```http
GET /sensors/{entity_type}/{entity_id}?mode=latest
```

**Parameters:**
- `entity_type` (path, required): "bus" or "stop"
- `entity_id` (path, required): Bus ID (e.g., "B001") or Stop ID (e.g., "S001")
- `mode` (query, required): Must be "latest"

**Response (Bus):**
```json
{
  "entity_id": "B001",
  "entity_type": "bus",
  "time": "2026-02-22T10:30:00Z",
  "temperature": 22.5,
  "humidity": 65.0,
  "co2_level": 850,
  "door_status": "closed"
}
```

**Response (Stop):**
```json
{
  "entity_id": "S001",
  "entity_type": "stop",
  "time": "2026-02-22T10:30:00Z",
  "temperature": 18.3,
  "humidity": 70.2
}
```

**Get Historical Sensor Data**

```http
GET /sensors/{entity_type}/{entity_id}?timestamp={ISO8601}
```

**Example:**
```bash
# Bus sensors
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: team-alpha" \
     "$API_URL/sensors/bus/B001?mode=latest"

# Stop sensors
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: team-alpha" \
     "$API_URL/sensors/stop/S001?mode=latest"
```

#### 3. Bus Position API

Query real-time and historical bus positions.

**Get Latest Bus Position**

```http
GET /bus-position/{bus_id}?mode=latest
```

**Parameters:**
- `bus_id` (path, required): Bus identifier (e.g., "B001")
- `mode` (query, required): Must be "latest"

**Response:**
```json
{
  "bus_id": "B001",
  "line_id": "L1",
  "time": "2026-02-22T10:30:00Z",
  "latitude": 40.4657,
  "longitude": -3.6886,
  "passenger_count": 35,
  "next_stop_id": "S002",
  "distance_to_next_stop": 250.5,
  "speed": 25.0,
  "direction": 0
}
```

**Get Historical Bus Position**

```http
GET /bus-position/{bus_id}?timestamp={ISO8601}
```

**Get All Buses on a Line**

```http
GET /bus-position/line/{line_id}?mode=latest
```

**Parameters:**
- `line_id` (path, required): Line identifier (e.g., "L1")
- `mode` (query, required): Must be "latest"

**Response:**
```json
{
  "line_id": "L1",
  "buses": [
    {
      "bus_id": "B001",
      "time": "2026-02-22T10:30:00Z",
      "latitude": 40.4657,
      "longitude": -3.6886,
      "passenger_count": 35,
      "next_stop_id": "S002",
      "distance_to_next_stop": 250.5,
      "speed": 25.0,
      "direction": 0
    }
  ]
}
```

**Example:**
```bash
# Single bus
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: team-alpha" \
     "$API_URL/bus-position/B001?mode=latest"

# All buses on line
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: team-alpha" \
     "$API_URL/bus-position/line/L1?mode=latest"
```

---

## WebSocket API

### Connection URL

```
wss://{api-id}.execute-api.{region}.amazonaws.com/production
```

Get from Terraform outputs:
```bash
cd terraform
terraform output websocket_api_endpoint
```

### Connection Lifecycle

#### 1. Connect

Establish WebSocket connection with authentication:

```javascript
const apiKey = 'your-api-key';
const groupName = 'your-group';
const wsUrl = `wss://${endpoint}/production?api_key=${apiKey}&group_name=${groupName}`;

const ws = new WebSocket(wsUrl);

ws.onopen = () => {
  console.log('Connected to bus position stream');
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = (event) => {
  console.log('WebSocket closed:', event.code, event.reason);
};
```

#### 2. Subscribe to Lines

After connecting, subscribe to specific bus lines:

```javascript
ws.send(JSON.stringify({
  action: 'subscribe',
  line_ids: ['L1', 'L2']
}));
```

#### 3. Receive Updates

Handle incoming position updates:

```javascript
ws.onmessage = (event) => {
  const position = JSON.parse(event.data);
  console.log('Bus position update:', position);
  // position structure same as REST API response
};
```

#### 4. Unsubscribe

Stop receiving updates for specific lines:

```javascript
ws.send(JSON.stringify({
  action: 'unsubscribe',
  line_ids: ['L1']
}));
```

#### 5. Close Connection

```javascript
ws.close();
```

### Message Formats

**Subscribe Message:**
```json
{
  "action": "subscribe",
  "line_ids": ["L1", "L2", "L3"]
}
```

**Unsubscribe Message:**
```json
{
  "action": "unsubscribe",
  "line_ids": ["L1"]
}
```

**Position Update (Server to Client):**
```json
{
  "bus_id": "B001",
  "line_id": "L1",
  "time": "2026-02-22T10:30:00Z",
  "latitude": 40.4657,
  "longitude": -3.6886,
  "passenger_count": 35,
  "next_stop_id": "S002",
  "distance_to_next_stop": 250.5,
  "speed": 25.0,
  "direction": 0
}
```

### Python Example

```python
import websocket
import json

api_key = 'your-api-key'
group_name = 'your-group'
ws_url = f'wss://{endpoint}/production?api_key={api_key}&group_name={group_name}'

def on_open(ws):
    print('Connected')
    ws.send(json.dumps({
        'action': 'subscribe',
        'line_ids': ['L1', 'L2']
    }))

def on_message(ws, message):
    data = json.loads(message)
    print('Position update:', data)

def on_error(ws, error):
    print('Error:', error)

def on_close(ws, close_status_code, close_msg):
    print('Connection closed')

ws = websocket.WebSocketApp(ws_url,
                            on_open=on_open,
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)

ws.run_forever()
```

---

## MCP Server

### Overview

The MCP (Model Context Protocol) server provides programmatic access to Timestream data with five tools for querying bus system information.

### Base URL

```
https://{api-id}.execute-api.{region}.amazonaws.com/prod
```

Get from Terraform outputs:
```bash
cd terraform
terraform output mcp_api_endpoint
```

### Available Tools

#### 1. query_people_count

Query people count at a bus stop.

**Request:**
```bash
curl -X POST "$MCP_ENDPOINT/mcp/call-tool" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "query_people_count",
    "arguments": {
      "stop_id": "S001",
      "mode": "latest"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "count": 1,
  "data": [
    {
      "stop_id": "S001",
      "time": "2026-02-22T10:30:00.000Z",
      "count": "15",
      "line_ids": "L1,L2"
    }
  ],
  "timestamp": "2026-02-22T10:30:05.123Z"
}
```

#### 2. query_sensor_data

Query sensor data for a bus or stop.

**Request:**
```bash
curl -X POST "$MCP_ENDPOINT/mcp/call-tool" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "query_sensor_data",
    "arguments": {
      "entity_id": "B001",
      "entity_type": "bus",
      "mode": "latest"
    }
  }'
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
      "time": "2026-02-22T10:30:00.000Z",
      "temperature": "22.5",
      "humidity": "65.0",
      "co2_level": "800",
      "door_status": "closed"
    }
  ],
  "timestamp": "2026-02-22T10:30:05.123Z"
}
```

#### 3. query_bus_position

Query bus position on route.

**Request:**
```bash
curl -X POST "$MCP_ENDPOINT/mcp/call-tool" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "query_bus_position",
    "arguments": {
      "bus_id": "B001",
      "mode": "latest"
    }
  }'
```

#### 4. query_line_buses

Query all buses on a specific line.

**Request:**
```bash
curl -X POST "$MCP_ENDPOINT/mcp/call-tool" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "query_line_buses",
    "arguments": {
      "line_id": "L1",
      "mode": "latest"
    }
  }'
```

#### 5. query_time_range

Query time series data over a time range.

**Request:**
```bash
curl -X POST "$MCP_ENDPOINT/mcp/call-tool" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "query_time_range",
    "arguments": {
      "data_type": "people_count",
      "entity_id": "S001",
      "start_time": "2026-02-22T08:00:00Z",
      "end_time": "2026-02-22T12:00:00Z"
    }
  }'
```

### List Available Tools

```bash
curl -X POST "$MCP_ENDPOINT/mcp/list-tools" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json"
```

---

## Error Handling

### Common Error Responses

**401 Unauthorized - Missing API Key:**
```json
{
  "message": "Unauthorized: Missing x-api-key header"
}
```

**401 Unauthorized - Missing Group Name:**
```json
{
  "message": "Unauthorized: Missing x-group-name header"
}
```

**403 Forbidden - Invalid API Key:**
```json
{
  "message": "Unauthorized: Invalid API key"
}
```

**404 Not Found - Resource Not Found:**
```json
{
  "error": "NotFound",
  "message": "Stop S999 not found"
}
```

**400 Bad Request - Invalid Parameters:**
```json
{
  "error": "BadRequest",
  "message": "Must specify 'mode=latest' or 'timestamp' parameter"
}
```

**500 Internal Server Error:**
```json
{
  "error": "InternalServerError",
  "message": "An unexpected error occurred. Please try again later."
}
```

---

## Rate Limits

Current limits (configurable in Terraform):

- **Requests per second**: 50 per API key
- **Requests per day**: 10,000 per API key
- **WebSocket connections**: 100 concurrent per API key
- **WebSocket subscriptions**: 50 lines per connection

---

## Examples

### Complete REST API Example (Python)

```python
import requests
from datetime import datetime

API_KEY = "your-api-key"
GROUP_NAME = "team-alpha"
API_URL = "https://your-api-id.execute-api.eu-west-1.amazonaws.com"

headers = {
    'x-api-key': API_KEY,
    'x-group-name': GROUP_NAME
}

# Get latest people count
response = requests.get(
    f'{API_URL}/people-count/S001',
    headers=headers,
    params={'mode': 'latest'}
)
print('People count:', response.json())

# Get historical sensor data
timestamp = datetime(2026, 2, 22, 10, 0, 0).isoformat() + 'Z'
response = requests.get(
    f'{API_URL}/sensors/bus/B001',
    headers=headers,
    params={'timestamp': timestamp}
)
print('Sensor data:', response.json())

# Get all buses on line
response = requests.get(
    f'{API_URL}/bus-position/line/L1',
    headers=headers,
    params={'mode': 'latest'}
)
print('Line buses:', response.json())
```

### Complete WebSocket Example (JavaScript)

```javascript
class BusPositionStream {
  constructor(apiKey, groupName, endpoint) {
    this.wsUrl = `wss://${endpoint}/production?api_key=${apiKey}&group_name=${groupName}`;
    this.ws = null;
    this.subscribedLines = new Set();
  }
  
  connect() {
    this.ws = new WebSocket(this.wsUrl);
    
    this.ws.onopen = () => {
      console.log('Connected');
      if (this.subscribedLines.size > 0) {
        this.subscribe([...this.subscribedLines]);
      }
    };
    
    this.ws.onmessage = (event) => {
      const position = JSON.parse(event.data);
      this.onPositionUpdate(position);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    this.ws.onclose = () => {
      console.log('Connection closed, reconnecting...');
      setTimeout(() => this.connect(), 5000);
    };
  }
  
  subscribe(lineIds) {
    lineIds.forEach(id => this.subscribedLines.add(id));
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'subscribe',
        line_ids: lineIds
      }));
    }
  }
  
  unsubscribe(lineIds) {
    lineIds.forEach(id => this.subscribedLines.delete(id));
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        action: 'unsubscribe',
        line_ids: lineIds
      }));
    }
  }
  
  onPositionUpdate(position) {
    console.log('Bus position update:', position);
  }
  
  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const stream = new BusPositionStream(
  'your-api-key',
  'team-alpha',
  'your-api-id.execute-api.eu-west-1.amazonaws.com'
);

stream.onPositionUpdate = (position) => {
  console.log(`Bus ${position.bus_id}: ${position.latitude}, ${position.longitude}`);
};

stream.connect();
stream.subscribe(['L1', 'L2']);
```

### Complete MCP Server Example (Python)

```python
import requests
import json

API_KEY = "your-api-key"
GROUP_NAME = "team-alpha"
MCP_ENDPOINT = "https://your-mcp-api-id.execute-api.eu-west-1.amazonaws.com/prod"

headers = {
    'x-api-key': API_KEY,
    'x-group-name': GROUP_NAME,
    'Content-Type': 'application/json'
}

# List available tools
response = requests.post(
    f'{MCP_ENDPOINT}/mcp/list-tools',
    headers=headers
)
print('Available tools:', response.json())

# Query people count
response = requests.post(
    f'{MCP_ENDPOINT}/mcp/call-tool',
    headers=headers,
    json={
        'tool': 'query_people_count',
        'arguments': {
            'stop_id': 'S001',
            'mode': 'latest'
        }
    }
)
print('People count:', response.json())

# Query time range
response = requests.post(
    f'{MCP_ENDPOINT}/mcp/call-tool',
    headers=headers,
    json={
        'tool': 'query_time_range',
        'arguments': {
            'data_type': 'bus_position',
            'entity_id': 'B001',
            'start_time': '2026-02-22T08:00:00Z',
            'end_time': '2026-02-22T12:00:00Z'
        }
    }
)
print('Time range data:', response.json())
```

---

## Additional Resources

- [OpenAPI Specification](./openapi.yaml) - Machine-readable API spec
- [Interactive API Docs](./api.html) - Swagger UI interface
- [Operations Manual](./ops_manual.md) - Operational procedures
- [Deployment Manual](./deployment_manual.md) - Deployment guide
- [Main README](../README.md) - Project overview

## Support

For issues or questions:
- Open an issue on GitHub
- Check CloudWatch logs for debugging
- Review the operations manual for troubleshooting
