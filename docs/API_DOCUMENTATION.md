# API Documentation - Madrid Bus Real-Time Simulator

## Overview

The Madrid Bus Real-Time Simulator provides three REST APIs and one WebSocket API for accessing simulated bus operation data.

## Base URLs

- **HTTP API**: `https://{api-id}.execute-api.{region}.amazonaws.com`
- **WebSocket API**: `wss://{api-id}.execute-api.{region}.amazonaws.com/production`

Replace `{api-id}` and `{region}` with your deployment values (available in Terraform outputs).

## Authentication

Currently, the APIs are open for hackathon use. No authentication is required.

## REST APIs

### 1. People Count API

Get the number of people waiting at bus stops.

#### Get Latest People Count

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

#### Get Historical People Count

```http
GET /people-count/{stop_id}?timestamp={ISO8601}
```

**Parameters:**
- `stop_id` (path, required): Bus stop identifier
- `timestamp` (query, required): ISO 8601 timestamp (e.g., "2026-02-22T10:00:00Z")

**Response:** Same as latest query

**Error Responses:**
- `404 Not Found`: Stop ID does not exist
- `400 Bad Request`: Invalid parameters

### 2. Sensors API

Get sensor readings from buses and stops (temperature, humidity, CO2, door status).

#### Get Latest Sensor Data

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

#### Get Historical Sensor Data

```http
GET /sensors/{entity_type}/{entity_id}?timestamp={ISO8601}
```

**Parameters:** Same as latest query, with `timestamp` instead of `mode`

**Error Responses:**
- `404 Not Found`: Entity ID does not exist
- `400 Bad Request`: Invalid parameters

### 3. Bus Position API

Get real-time and historical bus positions.

#### Get Latest Bus Position

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
  "speed": 25.0
}
```

#### Get Historical Bus Position

```http
GET /bus-position/{bus_id}?timestamp={ISO8601}
```

**Parameters:** Same as latest query, with `timestamp` instead of `mode`

#### Get All Buses on a Line

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
      "speed": 25.0
    },
    {
      "bus_id": "B002",
      "time": "2026-02-22T10:30:00Z",
      "latitude": 40.4500,
      "longitude": -3.6900,
      "passenger_count": 42,
      "next_stop_id": "S005",
      "distance_to_next_stop": 180.0,
      "speed": 30.0
    }
  ]
}
```

**Error Responses:**
- `404 Not Found`: Bus ID or Line ID does not exist
- `400 Bad Request`: Invalid parameters

## WebSocket API

Real-time bus position updates via WebSocket connection.

### Connection

```javascript
const ws = new WebSocket('wss://{api-id}.execute-api.{region}.amazonaws.com/production');

ws.onopen = () => {
  console.log('Connected to bus position stream');
};
```

### Subscribe to Line Updates

After connecting, send a subscription message:

```javascript
ws.send(JSON.stringify({
  action: 'subscribe',
  line_ids: ['L1', 'L2']
}));
```

### Receive Position Updates

```javascript
ws.onmessage = (event) => {
  const position = JSON.parse(event.data);
  console.log('Bus position update:', position);
  // position structure same as REST API response
};
```

### Unsubscribe

```javascript
ws.send(JSON.stringify({
  action: 'unsubscribe',
  line_ids: ['L1']
}));
```

### Close Connection

```javascript
ws.close();
```

## Example Usage

### cURL Examples

```bash
# Get latest people count at stop S001
curl "https://{api-id}.execute-api.eu-west-1.amazonaws.com/people-count/S001?mode=latest"

# Get historical sensor data for bus B001
curl "https://{api-id}.execute-api.eu-west-1.amazonaws.com/sensors/bus/B001?timestamp=2026-02-22T10:00:00Z"

# Get all buses on line L1
curl "https://{api-id}.execute-api.eu-west-1.amazonaws.com/bus-position/line/L1?mode=latest"
```

### JavaScript Example

```javascript
// Fetch latest bus position
fetch('https://{api-id}.execute-api.eu-west-1.amazonaws.com/bus-position/B001?mode=latest')
  .then(response => response.json())
  .then(data => console.log('Bus position:', data))
  .catch(error => console.error('Error:', error));

// WebSocket connection for real-time updates
const ws = new WebSocket('wss://{api-id}.execute-api.eu-west-1.amazonaws.com/production');

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'subscribe',
    line_ids: ['L1', 'L2']
  }));
};

ws.onmessage = (event) => {
  const position = JSON.parse(event.data);
  console.log('Real-time update:', position);
};
```

### Python Example

```python
import requests
from datetime import datetime

# Get latest people count
response = requests.get(
    'https://{api-id}.execute-api.eu-west-1.amazonaws.com/people-count/S001',
    params={'mode': 'latest'}
)
print(response.json())

# Get historical data
timestamp = datetime(2026, 2, 22, 10, 0, 0).isoformat() + 'Z'
response = requests.get(
    f'https://{{api-id}}.execute-api.eu-west-1.amazonaws.com/sensors/bus/B001',
    params={'timestamp': timestamp}
)
print(response.json())
```

## Rate Limits

No rate limits are currently enforced for hackathon use.

## Data Retention

- Memory store: 24 hours (fast queries)
- Magnetic store: 30 days (historical queries)

## Support

For issues or questions, please open an issue on the GitHub repository.
