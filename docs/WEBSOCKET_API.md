# WebSocket API Documentation

## Overview

The WebSocket API provides real-time bus position updates. Clients can subscribe to specific bus lines and receive position updates as buses move along their routes.

## Connection

### Endpoint

```
wss://{api-id}.execute-api.{region}.amazonaws.com/production
```

Replace `{api-id}` and `{region}` with your deployment values.

### Authentication

WebSocket connections require authentication via query parameters:

- `api_key`: Your API key (provided by administrators)
- `group_name`: Your group/team identifier for tracking

### Connection Example

```javascript
const apiKey = 'your-api-key-here';
const groupName = 'your-group-name';
const wsUrl = `wss://{api-id}.execute-api.{region}.amazonaws.com/production?api_key=${apiKey}&group_name=${groupName}`;

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

### Python Example

```python
import websocket
import json

api_key = 'your-api-key-here'
group_name = 'your-group-name'
ws_url = f'wss://{{api-id}}.execute-api.{{region}}.amazonaws.com/production?api_key={api_key}&group_name={group_name}'

def on_open(ws):
    print('Connected to bus position stream')
    # Subscribe to lines
    ws.send(json.dumps({
        'action': 'subscribe',
        'line_ids': ['L1', 'L2']
    }))

def on_message(ws, message):
    data = json.loads(message)
    print('Bus position update:', data)

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

## Message Protocol

### Client to Server Messages

#### Subscribe to Line Updates

Subscribe to receive position updates for specific bus lines.

**Message Format:**

```json
{
  "action": "subscribe",
  "line_ids": ["L1", "L2", "L3"]
}
```

**Fields:**
- `action` (string, required): Must be "subscribe"
- `line_ids` (array of strings, required): List of line IDs to subscribe to

**Example:**

```javascript
ws.send(JSON.stringify({
  action: 'subscribe',
  line_ids: ['L1', 'L2']
}));
```

#### Unsubscribe from Line Updates

Stop receiving updates for specific bus lines.

**Message Format:**

```json
{
  "action": "unsubscribe",
  "line_ids": ["L1"]
}
```

**Fields:**
- `action` (string, required): Must be "unsubscribe"
- `line_ids` (array of strings, required): List of line IDs to unsubscribe from

**Example:**

```javascript
ws.send(JSON.stringify({
  action: 'unsubscribe',
  line_ids: ['L1']
}));
```

### Server to Client Messages

#### Bus Position Update

Sent automatically when a subscribed bus position changes.

**Message Format:**

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

**Fields:**
- `bus_id` (string): Bus identifier
- `line_id` (string): Line identifier
- `time` (string): ISO 8601 timestamp
- `latitude` (number): Latitude coordinate
- `longitude` (number): Longitude coordinate
- `passenger_count` (integer): Current passenger count
- `next_stop_id` (string): Next stop identifier
- `distance_to_next_stop` (number): Distance to next stop in meters
- `speed` (number): Current speed in km/h
- `direction` (integer): Route direction (0=outbound, 1=inbound)

**Example Handler:**

```javascript
ws.onmessage = (event) => {
  const position = JSON.parse(event.data);
  
  console.log(`Bus ${position.bus_id} on line ${position.line_id}`);
  console.log(`Position: ${position.latitude}, ${position.longitude}`);
  console.log(`Passengers: ${position.passenger_count}`);
  console.log(`Next stop: ${position.next_stop_id} (${position.distance_to_next_stop}m away)`);
  console.log(`Speed: ${position.speed} km/h`);
  console.log(`Direction: ${position.direction === 0 ? 'outbound' : 'inbound'}`);
};
```

## Connection Lifecycle

### 1. Connect

Establish WebSocket connection with authentication parameters.

```javascript
const ws = new WebSocket(wsUrl);
```

### 2. Wait for Connection

```javascript
ws.onopen = () => {
  console.log('Connected');
  // Now you can send subscription messages
};
```

### 3. Subscribe to Lines

```javascript
ws.send(JSON.stringify({
  action: 'subscribe',
  line_ids: ['L1', 'L2']
}));
```

### 4. Receive Updates

```javascript
ws.onmessage = (event) => {
  const position = JSON.parse(event.data);
  // Process position update
};
```

### 5. Manage Subscriptions

```javascript
// Add more lines
ws.send(JSON.stringify({
  action: 'subscribe',
  line_ids: ['L3']
}));

// Remove lines
ws.send(JSON.stringify({
  action: 'unsubscribe',
  line_ids: ['L1']
}));
```

### 6. Close Connection

```javascript
ws.close();
```

## Error Handling

### Connection Errors

**401 Unauthorized**: Missing or invalid API key or group name

```javascript
ws.onerror = (error) => {
  console.error('Connection error:', error);
  // Check your api_key and group_name parameters
};
```

### Message Errors

Invalid message format or unknown action will be silently ignored. Ensure your messages follow the correct format.

## Update Frequency

Bus position updates are sent approximately every 10-30 seconds, depending on bus movement and system load.

## Connection Limits

- Maximum concurrent connections per API key: 100
- Maximum subscriptions per connection: 50 lines
- Connection timeout: 2 hours of inactivity

## Best Practices

### 1. Handle Reconnection

```javascript
function connect() {
  const ws = new WebSocket(wsUrl);
  
  ws.onopen = () => {
    console.log('Connected');
    // Resubscribe to your lines
    ws.send(JSON.stringify({
      action: 'subscribe',
      line_ids: ['L1', 'L2']
    }));
  };
  
  ws.onclose = () => {
    console.log('Disconnected, reconnecting in 5 seconds...');
    setTimeout(connect, 5000);
  };
  
  ws.onerror = (error) => {
    console.error('Error:', error);
  };
  
  ws.onmessage = (event) => {
    const position = JSON.parse(event.data);
    // Process update
  };
}

connect();
```

### 2. Subscribe Only to Needed Lines

Only subscribe to lines you're actively monitoring to reduce bandwidth and processing.

```javascript
// Good: Subscribe to specific lines
ws.send(JSON.stringify({
  action: 'subscribe',
  line_ids: ['L1', 'L2']
}));

// Avoid: Don't subscribe to all lines if you don't need them
```

### 3. Handle Stale Data

Check the `time` field to ensure you're working with recent data.

```javascript
ws.onmessage = (event) => {
  const position = JSON.parse(event.data);
  const updateTime = new Date(position.time);
  const now = new Date();
  const ageSeconds = (now - updateTime) / 1000;
  
  if (ageSeconds > 60) {
    console.warn('Received stale data (>60 seconds old)');
  }
};
```

### 4. Graceful Shutdown

Always close the connection when done.

```javascript
window.addEventListener('beforeunload', () => {
  ws.close();
});
```

## Complete Example

```javascript
class BusPositionStream {
  constructor(apiKey, groupName, apiId, region) {
    this.wsUrl = `wss://${apiId}.execute-api.${region}.amazonaws.com/production?api_key=${apiKey}&group_name=${groupName}`;
    this.ws = null;
    this.subscribedLines = new Set();
    this.reconnectDelay = 5000;
  }
  
  connect() {
    this.ws = new WebSocket(this.wsUrl);
    
    this.ws.onopen = () => {
      console.log('Connected to bus position stream');
      // Resubscribe to previously subscribed lines
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
      setTimeout(() => this.connect(), this.reconnectDelay);
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
    // Override this method to handle position updates
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
  'your-group-name',
  'your-api-id',
  'eu-west-1'
);

stream.onPositionUpdate = (position) => {
  console.log(`Bus ${position.bus_id}: ${position.latitude}, ${position.longitude}`);
};

stream.connect();
stream.subscribe(['L1', 'L2']);

// Later...
stream.unsubscribe(['L1']);
stream.close();
```

## Troubleshooting

### Connection Fails Immediately

- Verify your `api_key` and `group_name` are correct
- Check that the WebSocket URL includes the query parameters
- Ensure you're using `wss://` (not `ws://`)

### No Messages Received

- Verify you've sent a subscribe message after connecting
- Check that the line IDs you subscribed to exist and have active buses
- Ensure the WebSocket connection is still open (`ws.readyState === WebSocket.OPEN`)

### Connection Drops Frequently

- Implement automatic reconnection (see Best Practices)
- Check your network stability
- Verify you're not exceeding connection limits

### Invalid Message Format

- Ensure you're using `JSON.stringify()` when sending messages
- Verify the `action` field is exactly "subscribe" or "unsubscribe"
- Check that `line_ids` is an array of strings

## Support

For issues or questions, please open an issue on the GitHub repository or contact the system administrators.
