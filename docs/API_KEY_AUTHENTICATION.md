# API Gateway API Key Authentication Configuration

## Overview

This document describes the API key authentication implementation for the Madrid Bus Real-Time Simulator REST API.

## Architecture Change

**Important**: The API Gateway has been converted from **HTTP API (v2)** to **REST API (v1)** to support API key authentication with usage plans.

### Why REST API instead of HTTP API?

API Gateway v2 (HTTP API) does **not support**:
- API keys (`aws_api_gateway_api_key`)
- Usage plans (`aws_api_gateway_usage_plan`)
- Built-in rate limiting and quotas per API key
- `api_key_required` parameter on routes

These features are **only available in API Gateway v1 (REST API)**.

## Implementation Details

### 1. API Keys

- **Resource**: `aws_api_gateway_api_key`
- **Count**: Configurable via `participant_count` variable (default: 50)
- **Naming**: `participant-1`, `participant-2`, etc.
- **Purpose**: Authenticate hackathon participants

### 2. Usage Plan

- **Resource**: `aws_api_gateway_usage_plan`
- **Name**: `hackathon-usage-plan`
- **Rate Limiting**: 50 requests/second per API key
- **Burst Limit**: 100 requests
- **Daily Quota**: 10,000 requests per day per API key

### 3. API Key Association

- **Resource**: `aws_api_gateway_usage_plan_key`
- **Purpose**: Associates each API key with the usage plan
- **Effect**: Enforces rate limits and quotas on all API keys

### 4. Protected Routes

All REST API routes require API keys:

- `GET /people-count/{stop_id}` - `api_key_required = true`
- `GET /sensors/{entity_type}/{entity_id}` - `api_key_required = true`
- `GET /bus-position/{bus_id}` - `api_key_required = true`
- `GET /bus-position/line/{line_id}` - `api_key_required = true`

## Configuration

### Variables

```hcl
variable "participant_count" {
  description = "Number of API keys to generate for hackathon participants"
  type        = number
  default     = 50
}
```

### Outputs

```hcl
output "api_keys" {
  description = "List of API key IDs"
  value       = module.api_gateway.api_keys
  sensitive   = true
}

output "api_key_values" {
  description = "List of API key values for distribution"
  value       = module.api_gateway.api_key_values
  sensitive   = true
}

output "usage_plan_id" {
  description = "Usage plan ID"
  value       = module.api_gateway.usage_plan_id
}
```

## Usage

### Deploying with Custom Participant Count

```bash
terraform apply -var="participant_count=100"
```

### Retrieving API Keys

```bash
# Get API key values (sensitive output)
terraform output -json api_key_values

# Get specific API key value
terraform output -json api_key_values | jq -r '.[0]'
```

### Testing API with API Key

```bash
# Set API key
API_KEY="your-api-key-here"

# Test people count endpoint
curl -H "x-api-key: $API_KEY" \
  "https://your-api-id.execute-api.eu-west-1.amazonaws.com/prod/people-count/S001?mode=latest"

# Test sensors endpoint
curl -H "x-api-key: $API_KEY" \
  "https://your-api-id.execute-api.eu-west-1.amazonaws.com/prod/sensors/bus/B001?mode=latest"

# Test bus position endpoint
curl -H "x-api-key: $API_KEY" \
  "https://your-api-id.execute-api.eu-west-1.amazonaws.com/prod/bus-position/B001?mode=latest"
```

### Error Responses

**Missing API Key (403 Forbidden)**:
```json
{
  "message": "Forbidden"
}
```

**Invalid API Key (403 Forbidden)**:
```json
{
  "message": "Forbidden"
}
```

**Rate Limit Exceeded (429 Too Many Requests)**:
```json
{
  "message": "Too Many Requests"
}
```

**Quota Exceeded (429 Too Many Requests)**:
```json
{
  "message": "Limit Exceeded"
}
```

## Rate Limiting Details

### Throttle Settings

- **Rate Limit**: 50 requests/second (steady state)
- **Burst Limit**: 100 requests (allows short bursts)

### Quota Settings

- **Limit**: 10,000 requests
- **Period**: DAY (resets at midnight UTC)

### How It Works

1. **Token Bucket Algorithm**: API Gateway uses a token bucket algorithm for rate limiting
2. **Per-Key Enforcement**: Each API key has its own rate limit and quota
3. **Automatic Reset**: Quotas reset automatically at midnight UTC
4. **Burst Handling**: Burst limit allows temporary spikes above the rate limit

## CORS Configuration

CORS is enabled via Gateway Responses:

- **Allowed Origins**: `*` (all origins)
- **Allowed Methods**: `GET, OPTIONS`
- **Allowed Headers**: `*` (all headers, including `x-api-key`)

## Security Considerations

1. **API Keys are Sensitive**: Store and distribute securely
2. **HTTPS Only**: API Gateway enforces TLS 1.2+
3. **Rate Limiting**: Prevents abuse and ensures fair usage
4. **Quota Management**: Limits daily usage per participant
5. **No Authorization**: API keys provide authentication only, not authorization

## Migration Notes

### Changes from HTTP API to REST API

1. **Endpoint Format**: 
   - HTTP API: `https://{api-id}.execute-api.{region}.amazonaws.com/{path}`
   - REST API: `https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/{path}`

2. **Stage Name**: REST API requires explicit stage (`prod`)

3. **Integration Type**: Both use `AWS_PROXY` integration

4. **Lambda Event Format**: REST API uses v1 event format (different from HTTP API v2)

### Lambda Function Compatibility

Lambda functions should handle both event formats or be updated to handle REST API v1 format:

```python
def lambda_handler(event, context):
    # REST API v1 format
    path_parameters = event.get('pathParameters', {})
    query_parameters = event.get('queryStringParameters', {})
    
    # API key is validated by API Gateway, not Lambda
    # No need to check for API key in Lambda code
```

## Troubleshooting

### API Key Not Working

1. Check API key is associated with usage plan
2. Verify API key is enabled
3. Ensure `x-api-key` header is included in request
4. Check API key value is correct (no extra spaces)

### Rate Limit Issues

1. Check current usage in CloudWatch metrics
2. Verify throttle settings in usage plan
3. Consider increasing rate limit if needed
4. Implement exponential backoff in client

### Quota Exceeded

1. Wait for quota reset (midnight UTC)
2. Request quota increase if needed
3. Optimize client to reduce request count
4. Implement caching on client side

## References

- [AWS API Gateway REST API Documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html)
- [API Gateway API Keys](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-key-source.html)
- [Usage Plans](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html)
- [Throttling](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
