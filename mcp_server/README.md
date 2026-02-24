# Madrid Bus Simulator MCP Server

Model Context Protocol (MCP) server for programmatic access to Madrid Bus Simulator time series data stored in AWS Timestream.

## Overview

The MCP server provides five tools for querying bus system data:

1. **query_people_count** - Query passenger counts at bus stops
2. **query_sensor_data** - Query sensor readings from buses and stops
3. **query_bus_position** - Query bus positions on routes
4. **query_line_buses** - Query all buses on a specific line
5. **query_time_range** - Query time series data over a time range

## Authentication

**All tool requests require authentication via API key.**

The MCP server validates API keys from the `x-api-key` header against AWS Secrets Manager, using the same API key as the REST APIs for unified authentication.

### API Key Requirements

- API key must be provided in the `x-api-key` header for all tool requests
- The API key is stored in AWS Secrets Manager (secret ID: `bus-simulator/api-key`)
- Invalid or missing API keys will result in a 401 authentication error
- Authentication attempts are logged to CloudWatch Logs

## Deployment Options

The MCP server can be deployed in two ways:

1. **AWS ECS Fargate (Production)**: Deployed as a containerized service with API Gateway access
2. **Local Installation (Development)**: Run locally for testing and development

### Production Deployment (AWS ECS)

The MCP server is deployed on AWS ECS Fargate in private subnets with external access via API Gateway HTTP API.

**Architecture:**
- **ECS Service**: Runs in private subnets with auto-restart on failure
- **API Gateway**: HTTP API with VPC Link for secure access to ECS
- **Authentication**: Custom authorizer validates x-api-key and x-group-name headers
- **Networking**: Private subnets with NAT gateway for AWS service access
- **Monitoring**: CloudWatch Logs at `/ecs/mcp-server`

**Accessing the Deployed MCP Server:**

```bash
# Get the API endpoint from Terraform outputs
cd terraform
MCP_ENDPOINT=$(terraform output -raw mcp_api_endpoint)

# Get the API key from Secrets Manager
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString --output text | jq -r '.api_key')

# Call the MCP server
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-api-key: ${API_KEY}" \
  -H "x-group-name: your-group-name" \
  -H "Content-Type: application/json"
```

**Authentication Requirements:**
- `x-api-key`: API key from AWS Secrets Manager (secret ID: `bus-simulator/api-key`)
- `x-group-name`: Group identifier for request tracking (any string value)

Both headers are required for all requests. Missing or invalid headers will result in 401 Unauthorized.

**CloudWatch Logs:**

View MCP server logs:
```bash
aws logs tail /ecs/mcp-server --follow --region eu-west-1
```

Filter by group name:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/mcp-server \
  --filter-pattern "your-group-name" \
  --region eu-west-1
```

### Local Installation (Development)

For local development and testing:

**Prerequisites:**
- Python 3.9 or higher
- AWS credentials configured (IAM role or credentials file)
- Access to the Timestream database
- Valid API key (stored in AWS Secrets Manager)
- IAM permissions to read from Secrets Manager

**Install Dependencies:**

```bash
cd mcp_server
pip install -r requirements.txt
```

**Install as Package:**

```bash
cd mcp_server
pip install -e .
```

**Configuration:**

The MCP server uses environment variables for configuration:

- `TIMESTREAM_DATABASE`: Name of the Timestream database (default: `bus_simulator`)
- `AWS_REGION`: AWS region for Timestream (default: `eu-west-1`)

**MCP Client Configuration:**

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

### Authentication Headers

All tool requests must include the `x-api-key` header with a valid API key:

```json
{
  "tool": "query_people_count",
  "arguments": {
    "stop_id": "S001",
    "mode": "latest",
    "_headers": {
      "x-api-key": "your-api-key-here"
    }
  }
}
```

**Note:** The `_headers` field is a special argument that contains authentication headers. It is not passed to the tool handler itself.

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
    "mode": "latest",
    "_headers": {
      "x-api-key": "your-api-key-here"
    }
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

### Authentication Errors

When authentication fails, the response includes a 401 status code:

```json
{
  "success": false,
  "error": "Authentication failed: Missing x-api-key header",
  "status_code": 401,
  "timestamp": "2024-01-15T10:30:05.123Z"
}
```

Common authentication errors:
- Missing x-api-key header
- Invalid API key
- Unable to retrieve API key from Secrets Manager
- Access denied to Secrets Manager

### Other Common Errors

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
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:*:*:secret:bus-simulator/api-key-*"
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

For local development without AWS access, you can mock the Timestream client and authentication:

```python
from unittest.mock import Mock, patch
import asyncio

# Mock Timestream client
mock_timestream = Mock()
mock_timestream.query.return_value = {
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

# Mock Secrets Manager client
mock_secrets = Mock()
mock_secrets.get_secret_value.return_value = {
    'SecretString': '{"api_key": "test-api-key-123"}'
}

# Use mocks in server
with patch('boto3.client') as mock_boto:
    def client_factory(service, **kwargs):
        if service == 'timestream-query':
            return mock_timestream
        elif service == 'secretsmanager':
            return mock_secrets
        return Mock()
    
    mock_boto.side_effect = client_factory
    
    server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
    # Test with valid API key
    headers = {'x-api-key': 'test-api-key-123'}
    # ... test tool calls
```

## Troubleshooting

### ECS Deployment Issues

#### ECS Service Not Starting

1. Check ECS service status:
   ```bash
   aws ecs describe-services \
     --cluster bus-simulator-cluster \
     --services mcp-server \
     --region eu-west-1
   ```

2. Check task status and stopped reason:
   ```bash
   aws ecs describe-tasks \
     --cluster bus-simulator-cluster \
     --tasks $(aws ecs list-tasks --cluster bus-simulator-cluster --service-name mcp-server --query 'taskArns[0]' --output text) \
     --region eu-west-1
   ```

3. View container logs:
   ```bash
   aws logs tail /ecs/mcp-server --follow --region eu-west-1
   ```

#### API Gateway Returns 502 Bad Gateway

1. Verify ECS service is running:
   ```bash
   aws ecs describe-services \
     --cluster bus-simulator-cluster \
     --services mcp-server \
     --query 'services[0].runningCount' \
     --region eu-west-1
   ```

2. Check VPC Link status:
   ```bash
   aws apigatewayv2 get-vpc-link \
     --vpc-link-id $(terraform output -raw mcp_vpc_link_id) \
     --region eu-west-1
   ```

3. Verify security group allows traffic from VPC Link to ECS:
   ```bash
   # Check security group rules
   aws ec2 describe-security-groups \
     --group-ids $(terraform output -raw mcp_security_group_id) \
     --region eu-west-1
   ```

#### Authentication Fails (401 Unauthorized)

1. Verify API key exists in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id bus-simulator/api-key --region eu-west-1
   ```

2. Check both headers are present:
   - `x-api-key`: Must match the key in Secrets Manager
   - `x-group-name`: Must be present (any string value)

3. Check authorizer Lambda logs:
   ```bash
   aws logs tail /aws/lambda/bus-simulator-rest-authorizer --follow --region eu-west-1
   ```

#### High Memory or CPU Usage

1. Check CloudWatch metrics:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ECS \
     --metric-name MemoryUtilization \
     --dimensions Name=ServiceName,Value=mcp-server Name=ClusterName,Value=bus-simulator-cluster \
     --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Average \
     --region eu-west-1
   ```

2. Review query patterns in logs for expensive operations

3. Consider increasing CPU/memory in Terraform configuration:
   ```hcl
   module "mcp_server" {
     cpu    = "1024"  # Increase from 512
     memory = "2048"  # Increase from 1024
     ...
   }
   ```

#### Network Connectivity Issues

1. Verify NAT gateway is functioning:
   ```bash
   aws ec2 describe-nat-gateways \
     --filter "Name=vpc-id,Values=$(terraform output -raw vpc_id)" \
     --region eu-west-1
   ```

2. Check VPC endpoints for Timestream and Secrets Manager:
   ```bash
   aws ec2 describe-vpc-endpoints \
     --filters "Name=vpc-id,Values=$(terraform output -raw vpc_id)" \
     --region eu-west-1
   ```

3. Verify security group allows outbound HTTPS (443):
   ```bash
   aws ec2 describe-security-groups \
     --group-ids $(terraform output -raw mcp_security_group_id) \
     --query 'SecurityGroups[0].IpPermissionsEgress' \
     --region eu-west-1
   ```

### Local Development Issues

#### Server won't start

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

4. Verify Secrets Manager access:
   ```bash
   aws secretsmanager get-secret-value --secret-id bus-simulator/api-key
   ```

### Common Issues

#### Authentication errors

1. Verify API key exists in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value --secret-id bus-simulator/api-key
   ```

2. Check IAM permissions for Secrets Manager access

3. Ensure x-api-key header is included in all tool requests

4. Verify the API key matches the one stored in Secrets Manager

5. Ensure x-group-name header is present (required for all requests)

#### Queries return no data

1. Verify data exists in Timestream:
   ```bash
   aws timestream-query query --query-string "SELECT * FROM bus_simulator.people_count LIMIT 1"
   ```

2. Check entity IDs match configuration in `data/lines.yaml`

3. Verify timestamp format is ISO8601 (e.g., "2024-01-15T10:30:00Z")

#### Permission errors

Ensure your AWS credentials have the required Timestream and Secrets Manager permissions. Check IAM policy attached to your user/role.

For ECS deployment, verify the task role has the correct permissions:
```bash
aws iam get-role-policy \
  --role-name bus-simulator-mcp-task-role \
  --policy-name timestream-access \
  --region eu-west-1
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
