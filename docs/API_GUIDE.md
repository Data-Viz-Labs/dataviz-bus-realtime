# Madrid Bus Real-Time Simulator - API Guide

## Overview

This guide provides comprehensive information about accessing the Madrid Bus Real-Time Simulator APIs. The system provides three REST APIs and one WebSocket API for querying simulated bus operation data.

## Quick Start

### 1. Get Your Credentials

You need two pieces of information to access the APIs:

- **API Key**: Provided by system administrators (stored in AWS Secrets Manager)
- **Group Name**: Your team/group identifier for tracking purposes

### 2. Get the API Endpoints

After deployment, the API endpoints are available in the Terraform outputs:

```bash
cd terraform
terraform output rest_api_url
terraform output websocket_api_url
```

### 3. Make Your First Request

```bash
# Set your credentials
export API_KEY="your-api-key-here"
export GROUP_NAME="your-group-name"
export API_URL="https://your-api-id.execute-api.eu-west-1.amazonaws.com"

# Get latest people count at stop S001
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: $GROUP_NAME" \
     "$API_URL/people-count/S001?mode=latest"
```

## Base URL Format

### REST API

```
https://{api-id}.execute-api.{region}.amazonaws.com
```

**Components:**
- `{api-id}`: Your API Gateway ID (from Terraform output `rest_api_url`)
- `{region}`: AWS region where deployed (typically `eu-west-1` or `eu-central-1`)

**Example:**
```
https://abc123xyz.execute-api.eu-west-1.amazonaws.com
```

### WebSocket API

```
wss://{api-id}.execute-api.{region}.amazonaws.com/production
```

**Components:**
- `{api-id}`: Your WebSocket API Gateway ID (from Terraform output `websocket_api_url`)
- `{region}`: AWS region where deployed
- `/production`: Stage name (always "production")

**Example:**
```
wss://def456uvw.execute-api.eu-west-1.amazonaws.com/production
```

## Authentication

All API requests require authentication using two headers (REST) or query parameters (WebSocket).

### REST API Authentication

Include these headers in every request:

```http
x-api-key: your-api-key-here
x-group-name: your-group-name
```

**Example with curl:**

```bash
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: $GROUP_NAME" \
     "$API_URL/people-count/S001?mode=latest"
```

**Example with Python:**

```python
import requests

headers = {
    'x-api-key': 'your-api-key-here',
    'x-group-name': 'your-group-name'
}

response = requests.get(
    'https://your-api-id.execute-api.eu-west-1.amazonaws.com/people-count/S001',
    headers=headers,
    params={'mode': 'latest'}
)

print(response.json())
```

**Example with JavaScript:**

```javascript
const headers = {
  'x-api-key': 'your-api-key-here',
  'x-group-name': 'your-group-name'
};

fetch('https://your-api-id.execute-api.eu-west-1.amazonaws.com/people-count/S001?mode=latest', {
  headers: headers
})
  .then(response => response.json())
  .then(data => console.log(data))
  .catch(error => console.error('Error:', error));
```

### WebSocket Authentication

Include authentication as query parameters in the connection URL:

```
wss://{api-id}.execute-api.{region}.amazonaws.com/production?api_key=your-api-key&group_name=your-group-name
```

**Example with JavaScript:**

```javascript
const apiKey = 'your-api-key-here';
const groupName = 'your-group-name';
const wsUrl = `wss://your-api-id.execute-api.eu-west-1.amazonaws.com/production?api_key=${apiKey}&group_name=${groupName}`;

const ws = new WebSocket(wsUrl);
```

## Available APIs

### 1. People Count API

Query the number of people waiting at bus stops.

**Endpoints:**
- `GET /people-count/{stop_id}?mode=latest` - Get current people count
- `GET /people-count/{stop_id}?timestamp={ISO8601}` - Get historical people count

**Documentation:** See [OpenAPI Specification](./openapi.yaml) or [Interactive API Docs](./api.html)

### 2. Sensors API

Query sensor data from buses and stops (temperature, humidity, CO2, door status).

**Endpoints:**
- `GET /sensors/{entity_type}/{entity_id}?mode=latest` - Get current sensor data
- `GET /sensors/{entity_type}/{entity_id}?timestamp={ISO8601}` - Get historical sensor data

**Documentation:** See [OpenAPI Specification](./openapi.yaml) or [Interactive API Docs](./api.html)

### 3. Bus Position API

Query bus positions on routes.

**Endpoints:**
- `GET /bus-position/{bus_id}?mode=latest` - Get current bus position
- `GET /bus-position/{bus_id}?timestamp={ISO8601}` - Get historical bus position
- `GET /bus-position/line/{line_id}?mode=latest` - Get all buses on a line

**Documentation:** See [OpenAPI Specification](./openapi.yaml) or [Interactive API Docs](./api.html)

### 4. WebSocket API

Real-time bus position updates via WebSocket.

**Endpoint:**
- `WSS /production` - WebSocket connection for real-time updates

**Documentation:** See [WebSocket API Documentation](./WEBSOCKET_API.md)

## Documentation Resources

### Interactive API Explorer

Open `docs/api.html` in your browser to access an interactive API explorer powered by Swagger UI. You can:
- Browse all endpoints and their parameters
- See request/response examples
- Try out API calls directly from the browser
- View detailed schema definitions

### OpenAPI Specification

The complete API specification is available in `docs/openapi.yaml`. This machine-readable format can be used with:
- API client generators (OpenAPI Generator, Swagger Codegen)
- API testing tools (Postman, Insomnia)
- Documentation generators
- Mock servers

### WebSocket Documentation

Detailed WebSocket protocol documentation is available in `docs/WEBSOCKET_API.md`, including:
- Connection lifecycle
- Message formats
- Subscription management
- Error handling
- Complete code examples

## Regional Endpoints

The system can be deployed in multiple AWS regions. Common deployments:

### Ireland (eu-west-1)

```
REST API: https://{api-id}.execute-api.eu-west-1.amazonaws.com
WebSocket: wss://{api-id}.execute-api.eu-west-1.amazonaws.com/production
```

### Frankfurt (eu-central-1)

```
REST API: https://{api-id}.execute-api.eu-central-1.amazonaws.com
WebSocket: wss://{api-id}.execute-api.eu-central-1.amazonaws.com/production
```

Check your Terraform outputs to determine which region your deployment uses.

## Getting API Endpoints from Deployment

### Method 1: Terraform Outputs

```bash
cd terraform
terraform output rest_api_url
terraform output websocket_api_url
```

### Method 2: AWS Console

1. Go to AWS API Gateway console
2. Find "madrid-bus-simulator-http" (REST API)
3. Find "madrid-bus-simulator-websocket" (WebSocket API)
4. Copy the invoke URLs

### Method 3: Export Script

The deployment includes a script to export API information:

```bash
cd scripts
python export_api_keys.py
```

This creates `api_keys.txt` with:
- API key
- REST API endpoint
- WebSocket endpoint
- Example curl commands

## Rate Limits and Quotas

Current limits (configurable in Terraform):

- **Requests per second**: 50 per API key
- **Requests per day**: 10,000 per API key
- **WebSocket connections**: 100 concurrent per API key
- **WebSocket subscriptions**: 50 lines per connection

## Data Retention

- **Memory store**: 24 hours (fast queries for recent data)
- **Magnetic store**: 30 days (historical queries)

## Error Responses

All APIs return consistent error responses:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message"
}
```

**Common Error Codes:**

- `400 Bad Request`: Invalid parameters or missing required fields
- `401 Unauthorized`: Missing or invalid API key or group name
- `404 Not Found`: Requested resource (stop, bus, entity) doesn't exist
- `500 Internal Server Error`: Unexpected server error

## Testing Scripts

The repository includes shell scripts for testing all API endpoints. See [API Testing Scripts](../tests/api/README.md) for details.

## Support and Troubleshooting

### Check API Key

```bash
# Verify your API key is valid
aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString \
  --output text
```

### Test Authentication

```bash
# Test with invalid key (should return 401)
curl -H "x-api-key: invalid-key" \
     -H "x-group-name: test" \
     "$API_URL/people-count/S001?mode=latest"

# Test without group name (should return 401)
curl -H "x-api-key: $API_KEY" \
     "$API_URL/people-count/S001?mode=latest"
```

### Check API Gateway Status

```bash
# Get API Gateway details
aws apigatewayv2 get-apis --query 'Items[?Name==`madrid-bus-simulator-http`]'
```

### View Logs

```bash
# View Lambda function logs
aws logs tail /aws/lambda/people-count-api --follow

# View authorizer logs
aws logs tail /aws/lambda/rest-authorizer --follow
```

## Additional Resources

- [README.md](../README.md) - Project overview and setup
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - Detailed API reference
- [SECRETS_MANAGER_AUTH.md](./SECRETS_MANAGER_AUTH.md) - Authentication details
- [OpenAPI Specification](./openapi.yaml) - Machine-readable API spec
- [WebSocket API](./WEBSOCKET_API.md) - WebSocket protocol documentation
- [Interactive API Docs](./api.html) - Swagger UI interface

## Quick Reference

### Environment Variables

```bash
# Set these for easy testing
export API_KEY="your-api-key-here"
export GROUP_NAME="your-group-name"
export API_URL="https://your-api-id.execute-api.eu-west-1.amazonaws.com"
export WS_URL="wss://your-api-id.execute-api.eu-west-1.amazonaws.com/production"
```

### Common Requests

```bash
# People count
curl -H "x-api-key: $API_KEY" -H "x-group-name: $GROUP_NAME" \
  "$API_URL/people-count/S001?mode=latest"

# Sensor data
curl -H "x-api-key: $API_KEY" -H "x-group-name: $GROUP_NAME" \
  "$API_URL/sensors/bus/B001?mode=latest"

# Bus position
curl -H "x-api-key: $API_KEY" -H "x-group-name: $GROUP_NAME" \
  "$API_URL/bus-position/B001?mode=latest"

# All buses on a line
curl -H "x-api-key: $API_KEY" -H "x-group-name: $GROUP_NAME" \
  "$API_URL/bus-position/line/L1?mode=latest"
```

### WebSocket Connection

```javascript
const ws = new WebSocket(`${WS_URL}?api_key=${API_KEY}&group_name=${GROUP_NAME}`);

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'subscribe',
    line_ids: ['L1', 'L2']
  }));
};

ws.onmessage = (event) => {
  console.log('Position update:', JSON.parse(event.data));
};
```

## License

This project is licensed under the MIT License. See [LICENSE](../LICENSE) for details.
