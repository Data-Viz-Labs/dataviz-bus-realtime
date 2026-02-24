# Unified API Key Management via Secrets Manager

This document describes the unified API key management approach using AWS Secrets Manager and Custom Authorizers.

## Overview

The Madrid Bus Real-Time Simulator uses a unified API key management system that:
- Generates a single API key during Terraform deployment
- Stores the key securely in AWS Secrets Manager
- Validates requests using Custom Authorizer Lambda functions
- Requires group name identification for request tracking

This approach replaces the previous API Gateway API key and usage plan system with a more centralized and secure solution.

## Architecture

### Components

1. **Secrets Manager**: Stores the single API key as JSON: `{"api_key": "value"}`
2. **REST API Custom Authorizer**: Validates `x-api-key` and `x-group-name` headers
3. **WebSocket Custom Authorizer**: Validates `api_key` and `group_name` query parameters
4. **Lambda Functions**: Log group names for request tracking

### Authentication Flow

#### REST API
```
1. Client sends request with headers:
   - x-api-key: <api-key>
   - x-group-name: <team-name>

2. API Gateway invokes REST Custom Authorizer

3. Authorizer:
   - Retrieves API key from Secrets Manager
   - Validates x-api-key header
   - Validates x-group-name header presence
   - Returns IAM policy (Allow/Deny)

4. If authorized, request reaches Lambda function
   - Lambda extracts group_name from authorizer context
   - Lambda logs group_name for tracking
```

#### WebSocket API
```
1. Client connects with query parameters:
   - api_key=<api-key>
   - group_name=<team-name>

2. API Gateway invokes WebSocket Custom Authorizer

3. Authorizer:
   - Retrieves API key from Secrets Manager
   - Validates api_key parameter
   - Validates group_name parameter presence
   - Returns IAM policy (Allow/Deny)

4. If authorized, connection is established
   - Lambda stores connection with group_name
   - Lambda logs group_name for tracking
```

## Deployment

### Terraform Resources

The following Terraform resources are created:

```hcl
# Generate API key
resource "random_password" "api_key" {
  length  = 32
  special = false
}

# Store in Secrets Manager
resource "aws_secretsmanager_secret" "api_key" {
  name = "bus-simulator/api-key"
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id = aws_secretsmanager_secret.api_key.id
  secret_string = jsonencode({
    api_key = random_password.api_key.result
  })
}

# REST Custom Authorizer
resource "aws_lambda_function" "rest_authorizer" {
  filename      = "build/rest_authorizer.zip"
  function_name = "bus-simulator-rest-authorizer"
  handler       = "authorizer_rest.lambda_handler"
  # ... IAM role with Secrets Manager access
}

# WebSocket Custom Authorizer
resource "aws_lambda_function" "websocket_authorizer_v2" {
  filename      = "build/websocket_authorizer_v2.zip"
  function_name = "bus-simulator-websocket-authorizer-v2"
  handler       = "authorizer_websocket.lambda_handler"
  # ... IAM role with Secrets Manager access
}
```

### Deployment Steps

1. **Package Custom Authorizers**:
   ```bash
   bash scripts/package_lambda.sh authorizer_rest
   bash scripts/package_lambda.sh authorizer_websocket
   cp build/authorizer_rest.zip build/rest_authorizer.zip
   cp build/authorizer_websocket.zip build/websocket_authorizer_v2.zip
   ```

2. **Deploy Infrastructure**:
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

3. **Export API Key**:
   ```bash
   python scripts/export_api_keys.py --region eu-west-1 --output api_keys.txt
   ```

## API Key Export

The `export_api_keys.py` script retrieves the API key from Secrets Manager and generates a distribution file for hackathon participants.

### Usage

```bash
# Export to text file (default)
python scripts/export_api_keys.py --region eu-west-1 --output api_keys.txt

# Export to JSON
python scripts/export_api_keys.py --region eu-west-1 --output api_keys.json --format json

# Use Terraform outputs (alternative)
python scripts/export_api_keys.py --region eu-west-1 --use-terraform
```

### Output Format

The script generates a file with:
- API key value
- API endpoints (REST and WebSocket)
- Usage instructions with examples
- Group name requirements

## Usage Examples

### REST API

```bash
# Get latest people count
curl -H "x-api-key: YOUR_API_KEY" \
     -H "x-group-name: team-alpha" \
     "https://api.example.com/people-count/S001?mode=latest"

# Get sensor data
curl -H "x-api-key: YOUR_API_KEY" \
     -H "x-group-name: team-alpha" \
     "https://api.example.com/sensors/bus/B001?mode=latest"

# Get bus position
curl -H "x-api-key: YOUR_API_KEY" \
     -H "x-group-name: team-alpha" \
     "https://api.example.com/bus-position/B001?mode=latest"
```

### WebSocket API

```bash
# Connect using wscat
wscat -c "wss://ws.example.com?api_key=YOUR_API_KEY&group_name=team-alpha"

# Python example
import websocket
import json

ws_url = "wss://ws.example.com?api_key=YOUR_API_KEY&group_name=team-alpha"
ws = websocket.create_connection(ws_url)
ws.send(json.dumps({"action": "subscribe", "line_ids": ["L1"]}))

while True:
    result = ws.recv()
    print(result)
```

## Authorization Caching

**REST API Only**: Custom Authorizers cache authorization results for 5 minutes (300 seconds) to improve performance and reduce Secrets Manager API calls.

**Note**: Authorization caching is only supported for REST APIs. WebSocket APIs do not support the `authorizer_result_ttl_in_seconds` parameter, so each WebSocket connection will trigger a fresh authorization check.

Cache key includes:
- API key value
- Group name value

This means (for REST API):
- Same API key + group name = cached result (no Secrets Manager call)
- Different group name = new authorization check
- Cache expires after 5 minutes

For WebSocket connections:
- Each connection triggers a new authorization check
- No caching is applied
- Authorization happens once at connection time

## Error Responses

### Missing x-api-key Header (REST)
```json
{
  "message": "Unauthorized: Missing x-api-key header"
}
```
HTTP Status: 401

### Missing x-group-name Header (REST)
```json
{
  "message": "Unauthorized: Missing x-group-name header"
}
```
HTTP Status: 401

### Invalid API Key
```json
{
  "message": "Unauthorized: Invalid API key"
}
```
HTTP Status: 403

### Missing api_key Parameter (WebSocket)
```json
{
  "message": "Unauthorized: Invalid API key"
}
```
Connection rejected

### Missing group_name Parameter (WebSocket)
```json
{
  "message": "Unauthorized: Missing group_name parameter"
}
```
Connection rejected

## Group Name Logging

All Lambda functions log the group name for request tracking:

```python
# Extract group name from authorizer context
authorizer_context = event['requestContext'].get('authorizer', {})
group_name = authorizer_context.get('group_name', 'unknown')

# Log for tracking
logger.info(f"Request from group: {group_name}, resource: {resource_id}")
```

This enables:
- Request tracking by team
- Usage analytics per group
- Debugging and support

## Security Considerations

1. **Single API Key**: All participants share the same API key
   - Simplifies distribution
   - Reduces management overhead
   - Group names provide tracking

2. **Secrets Manager**: Centralized key storage
   - Secure storage with encryption
   - Access control via IAM
   - Audit logging via CloudTrail

3. **Custom Authorizers**: Validation before Lambda execution
   - Reduces Lambda invocations for unauthorized requests
   - Consistent validation logic
   - Caching for performance

4. **Group Name Requirement**: Mandatory identification
   - Tracks usage by team
   - Enables support and debugging
   - Provides accountability

## Monitoring

### CloudWatch Logs

Custom Authorizer logs:
- `/aws/lambda/bus-simulator-rest-authorizer`
- `/aws/lambda/bus-simulator-websocket-authorizer-v2`

Lambda function logs:
- `/aws/lambda/bus-simulator-people-count`
- `/aws/lambda/bus-simulator-sensors`
- `/aws/lambda/bus-simulator-bus-position`
- `/aws/lambda/bus-simulator-websocket-handler`

### Metrics

Monitor:
- Authorizer invocations
- Authorization failures (401/403 errors)
- Group name distribution
- Request patterns by group

## Troubleshooting

### API Key Not Working

1. Verify API key value:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id bus-simulator/api-key \
     --region eu-west-1 \
     --query SecretString \
     --output text | jq -r '.api_key'
   ```

2. Check Custom Authorizer logs:
   ```bash
   aws logs tail /aws/lambda/bus-simulator-rest-authorizer --follow
   ```

3. Verify IAM permissions for Custom Authorizer

### Missing Group Name

Ensure requests include:
- REST: `x-group-name` header
- WebSocket: `group_name` query parameter

### Authorization Caching Issues

If API key is rotated, wait 5 minutes for cache to expire or:
1. Update secret in Secrets Manager
2. Wait for cache TTL (300 seconds)
3. Or restart API Gateway stage

## Migration from API Gateway API Keys

The previous system used API Gateway API keys and usage plans. This has been replaced with:

| Old System | New System |
|------------|------------|
| Multiple API keys (one per participant) | Single API key (shared) |
| API Gateway API key resource | Secrets Manager secret |
| Usage plans for rate limiting | No rate limiting (removed) |
| API key in x-api-key header | API key in x-api-key header (same) |
| No group identification | x-group-name header required |

### Benefits of New System

1. **Simplified Management**: Single key instead of multiple
2. **Centralized Storage**: Secrets Manager instead of API Gateway
3. **Better Tracking**: Group names for request attribution
4. **Consistent Validation**: Custom Authorizers for both REST and WebSocket
5. **Easier Distribution**: One key for all participants

## References

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [API Gateway Custom Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html)
- [Lambda Authorizer Caching](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-output.html)
