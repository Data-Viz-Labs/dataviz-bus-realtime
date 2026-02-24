# MCP Server API Gateway HTTP API with VPC Link

This document describes the API Gateway HTTP API implementation for exposing the MCP server externally with VPC Link integration.

## Architecture Overview

```
Client Request (with x-api-key & x-group-name headers)
    ↓
API Gateway HTTP API (Public)
    ↓
Custom Authorizer Lambda (validates headers)
    ↓
VPC Link (connects to private subnet)
    ↓
Service Discovery (mcp-server.mcp.local)
    ↓
ECS Service (MCP Server in private subnet)
```

## Components

### 1. Service Discovery

**Namespace**: `mcp.local` (Private DNS namespace)
- Provides internal DNS resolution within the VPC
- Enables service-to-service communication

**Service**: `mcp-server`
- DNS name: `mcp-server.mcp.local`
- Health check: Custom health check with failure threshold of 1
- Routing policy: MULTIVALUE (distributes traffic across healthy tasks)

### 2. VPC Link

**Purpose**: Connects API Gateway (public) to ECS service (private subnet)

**Configuration**:
- Security group: Allows outbound traffic to VPC CIDR
- Subnets: Deployed in private subnets
- Connection: Enables HTTP_PROXY integration

### 3. HTTP API Gateway

**Protocol**: HTTP API (API Gateway v2)
- More cost-effective than REST API
- Native support for HTTP_PROXY integration
- Built-in CORS support

**CORS Configuration**:
- Allowed origins: Configurable (default: `*`)
- Allowed methods: GET, POST, PUT, DELETE, OPTIONS
- Allowed headers: content-type, x-api-key, x-group-name, authorization
- Max age: 300 seconds

### 4. Custom Authorizer

**Type**: REQUEST authorizer
- Reuses existing REST API authorizer Lambda
- Validates both `x-api-key` and `x-group-name` headers
- Caches authorization results for 5 minutes
- Payload format version: 2.0

**Authentication Flow**:
1. Client sends request with headers:
   - `x-api-key`: API key from Secrets Manager
   - `x-group-name`: Group identifier
2. API Gateway invokes Custom Authorizer Lambda
3. Authorizer validates both headers:
   - Checks API key against Secrets Manager
   - Requires x-group-name header presence
4. If valid, request is forwarded to MCP server via VPC Link
5. MCP server processes the request

### 5. Routes

**Health Check** (No authorization):
- `GET /health` - Public health check endpoint

**MCP Protocol Routes** (With authorization):
- `POST /mcp/list-tools` - List available MCP tools
- `POST /mcp/call-tool` - Execute an MCP tool
- `POST /mcp/query` - Query MCP server

**Default Route** (With authorization):
- `$default` - Catch-all route for other paths

### 6. Integration

**Type**: HTTP_PROXY
- Forwards all requests to backend without modification
- Preserves headers, query parameters, and body
- Uses Service Discovery DNS name: `http://mcp-server.mcp.local:8080`

**Timeout**: 30 seconds (maximum for HTTP APIs)

### 7. Stage

**Name**: `prod`
- Auto-deploy: Enabled (automatic deployment on changes)
- Access logs: CloudWatch Logs with detailed request information
- Throttling:
  - Burst limit: 100 requests
  - Rate limit: 50 requests/second

## Security

### Network Security

**VPC Link Security Group**:
- Egress: Allows traffic to VPC CIDR (10.0.0.0/16)

**MCP Server Security Group**:
- Ingress: Allows traffic from VPC Link security group on port 8080
- Ingress: Allows traffic from VPC CIDR on port 8080
- Egress: Allows all outbound traffic (for AWS service access)

### Authentication

**Unified Authentication**:
- Same API key as REST and WebSocket APIs
- Stored in AWS Secrets Manager
- Validated by Custom Authorizer Lambda

**Required Headers**:
- `x-api-key`: API key value
- `x-group-name`: Group identifier (e.g., "group1", "group2")

**Authorization Caching**:
- Results cached for 5 minutes
- Cache key: Combination of x-api-key and x-group-name
- Reduces Secrets Manager API calls

## Usage

### Example Request

```bash
# Get API endpoint from Terraform output
MCP_ENDPOINT=$(terraform output -raw mcp_api_endpoint)

# Get API key from Secrets Manager
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString --output text | jq -r '.api_key')

# Call MCP server
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-api-key: ${API_KEY}" \
  -H "x-group-name: group1" \
  -H "Content-Type: application/json"
```

### Health Check

```bash
# Health check (no authentication required)
curl "${MCP_ENDPOINT}/health"
```

## Monitoring

### CloudWatch Logs

**API Gateway Access Logs**: `/aws/apigateway/mcp-server`
- Request ID
- Source IP
- Request time
- HTTP method and route
- Status code
- Response length
- Error messages
- Authorizer errors

**ECS Service Logs**: `/ecs/mcp-server`
- Application logs from MCP server
- Container health check results

### Metrics

**API Gateway Metrics**:
- Request count
- Latency (integration, total)
- 4xx/5xx errors
- Authorizer errors

**ECS Service Metrics**:
- CPU utilization
- Memory utilization
- Task count
- Health check status

## Troubleshooting

### Common Issues

**1. 401 Unauthorized**
- Check that both `x-api-key` and `x-group-name` headers are present
- Verify API key matches value in Secrets Manager
- Check authorizer Lambda logs in CloudWatch

**2. 504 Gateway Timeout**
- Check ECS service health in ECS console
- Verify Service Discovery registration
- Check VPC Link status
- Review MCP server logs for slow responses

**3. 503 Service Unavailable**
- Verify ECS service has running tasks
- Check security group rules allow traffic
- Verify Service Discovery DNS resolution

**4. CORS Errors**
- Check CORS configuration in API Gateway
- Verify allowed origins include your domain
- Ensure preflight OPTIONS requests succeed

### Debugging Steps

1. **Check API Gateway**:
   ```bash
   aws apigatewayv2 get-api --api-id <api-id>
   aws apigatewayv2 get-vpc-links
   ```

2. **Check ECS Service**:
   ```bash
   aws ecs describe-services --cluster <cluster-name> --services mcp-server
   aws ecs list-tasks --cluster <cluster-name> --service-name mcp-server
   ```

3. **Check Service Discovery**:
   ```bash
   aws servicediscovery list-services --filters Name=NAMESPACE_ID,Values=<namespace-id>
   aws servicediscovery discover-instances --namespace-name mcp.local --service-name mcp-server
   ```

4. **Check Logs**:
   ```bash
   # API Gateway logs
   aws logs tail /aws/apigateway/mcp-server --follow
   
   # MCP server logs
   aws logs tail /ecs/mcp-server --follow
   ```

## Cost Optimization

**HTTP API vs REST API**:
- HTTP API: ~$1.00 per million requests
- REST API: ~$3.50 per million requests
- Savings: ~70% cost reduction

**Authorizer Caching**:
- Reduces Lambda invocations by caching results
- Cache TTL: 5 minutes
- Reduces Secrets Manager API calls

**VPC Link**:
- Charged per hour: ~$0.025/hour (~$18/month)
- No data transfer charges within same AZ

## Terraform Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `vpc_id` | VPC ID for Service Discovery | Required |
| `vpc_link_security_group_id` | Security group for VPC Link | Required |
| `rest_authorizer_invoke_arn` | Authorizer Lambda invoke ARN | Required |
| `rest_authorizer_function_name` | Authorizer Lambda function name | Required |
| `cors_allowed_origins` | Allowed origins for CORS | `["*"]` |
| `throttling_burst_limit` | Burst limit for throttling | `100` |
| `throttling_rate_limit` | Rate limit (req/sec) | `50` |

## Outputs

| Output | Description |
|--------|-------------|
| `api_endpoint` | HTTP API Gateway endpoint URL |
| `api_id` | HTTP API Gateway ID |
| `vpc_link_id` | VPC Link ID |
| `service_discovery_namespace_id` | Service Discovery namespace ID |
| `service_discovery_service_arn` | Service Discovery service ARN |

## References

- [API Gateway HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api.html)
- [VPC Links](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-vpc-links.html)
- [AWS Cloud Map Service Discovery](https://docs.aws.amazon.com/cloud-map/latest/dg/what-is-cloud-map.html)
- [Custom Authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-lambda-authorizer.html)
