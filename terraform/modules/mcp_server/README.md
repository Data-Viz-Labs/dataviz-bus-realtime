# MCP Server Terraform Module

This module creates an ECS Fargate service for the Madrid Bus Simulator MCP (Model Context Protocol) server with API Gateway HTTP API for external access.

## Overview

The MCP server provides programmatic access to Timestream data via the Model Context Protocol, enabling AI assistants and developers to query bus simulation data. The server is exposed externally through an API Gateway HTTP API with VPC Link integration.

## Resources Created

- **ECS Task Definition**: Defines the MCP server container configuration
- **ECS Service**: Runs the MCP server as a Fargate service
- **IAM Task Role**: Grants permissions for Timestream, Secrets Manager, and CloudWatch Logs
- **IAM Policies**: Scoped policies for secure access to AWS services
- **Service Discovery**: Private DNS namespace and service for internal routing
- **VPC Link**: Connects API Gateway to ECS service in private subnet
- **HTTP API Gateway**: Public endpoint with custom authorizer
- **API Routes**: Health check and MCP protocol endpoints
- **CloudWatch Log Groups**: Stores MCP server and API Gateway logs

## Architecture

```
Client → API Gateway HTTP API → Custom Authorizer → VPC Link → Service Discovery → ECS Service
```

See [API_GATEWAY.md](./API_GATEWAY.md) for detailed architecture documentation.

## Features

- **External API Access**: HTTP API Gateway with VPC Link for secure external access
- **Custom Authorization**: Validates x-api-key and x-group-name headers
- **IAM Task Role**: Automatically created with least-privilege permissions
- **Service Discovery**: Internal DNS resolution for ECS tasks
- **CORS Support**: Configurable CORS for web applications
- **Timestream Access**: Configured with environment variables for database access
- **Secrets Manager Integration**: API key validation using AWS Secrets Manager
- **CloudWatch Logging**: Structured logging with configurable log levels
- **Health Checks**: Container health monitoring for automatic recovery
- **Auto-restart**: Automatic service restart on failure
- **Secure Networking**: Deployed in private subnets with security group controls

## Configuration

### CPU and Memory

The module uses appropriate resource limits for MCP workload:
- **Default CPU**: 512 units (0.5 vCPU)
- **Default Memory**: 1024 MB (1 GB)

These defaults are suitable for moderate query loads. Adjust based on your usage patterns:
- Light usage (< 10 queries/min): 256 CPU, 512 MB memory
- Moderate usage (10-50 queries/min): 512 CPU, 1024 MB memory (default)
- Heavy usage (> 50 queries/min): 1024 CPU, 2048 MB memory

### Environment Variables

The task definition configures the following environment variables:
- `TIMESTREAM_DATABASE`: Name of the Timestream database
- `AWS_REGION`: AWS region for service endpoints
- `SECRET_ID`: Secrets Manager secret ID for API key validation
- `LOG_LEVEL`: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `PORT`: Container port for MCP server (default: 8080)

## Usage Example

```hcl
module "mcp_server" {
  source = "./modules/mcp_server"

  # ECS configuration
  ecs_cluster_id          = module.fargate.cluster_id
  ecs_execution_role_arn  = module.iam.ecs_execution_role_arn

  # Container image
  ecr_repository_url = module.fargate.ecr_repository_url

  # Timestream and Secrets Manager
  timestream_database_name = module.timestream.database_name
  api_key_secret_id        = module.api_gateway.api_key_secret_id

  # Networking
  private_subnet_ids         = module.supporting.private_subnet_ids
  security_group_id          = module.supporting.mcp_security_group_id
  vpc_id                     = module.supporting.vpc_id
  vpc_link_security_group_id = module.supporting.vpc_link_security_group_id

  # API Gateway and Authorization
  rest_authorizer_invoke_arn    = module.api_gateway.rest_authorizer_arn
  rest_authorizer_function_name = "bus-simulator-rest-authorizer"
  cors_allowed_origins          = ["*"]

  # Resource limits (optional)
  cpu    = "512"
  memory = "1024"

  # Logging (optional)
  log_level = "INFO"

  # Tags
  tags = {
    Project     = "Madrid Bus Simulator"
    Environment = "production"
    Component   = "mcp-server"
  }
}
```

**Note**: The module automatically creates an IAM task role with the necessary permissions for Timestream, Secrets Manager, and CloudWatch Logs. You no longer need to pass `ecs_task_role_arn` as an input.
```

## API Usage

```bash
# Get API endpoint
MCP_ENDPOINT=$(terraform output -raw mcp_api_endpoint)

# Get API key
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString --output text | jq -r '.api_key')

# Call MCP server
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-api-key: ${API_KEY}" \
  -H "x-group-name: group1" \
  -H "Content-Type: application/json"
```

## Accessing CloudWatch Logs

The MCP server logs all requests and operations to CloudWatch Logs at `/ecs/mcp-server`.

**View logs in real-time:**
```bash
aws logs tail /ecs/mcp-server --follow --region eu-west-1
```

**Filter logs by group name:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/mcp-server \
  --filter-pattern "group1" \
  --region eu-west-1
```

**Get logs from the last hour:**
```bash
aws logs tail /ecs/mcp-server --since 1h --region eu-west-1
```

**Search for authentication errors:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/mcp-server \
  --filter-pattern "401" \
  --region eu-west-1
```

**Log Format:**
```
[timestamp] [level] [component] message
```

Example log entries:
```
2024-01-15T10:30:00.123Z INFO auth API key validated for group: group1
2024-01-15T10:30:00.456Z INFO tools Executing query_people_count for stop S001
2024-01-15T10:30:00.789Z ERROR auth Authentication failed: Missing x-api-key header
```

## IAM Permissions

The module automatically creates an IAM task role with the following permissions:

### Timestream Query Access
- `timestream:DescribeEndpoints` - Discover Timestream service endpoints
- `timestream:Select` - Execute SELECT queries on time series data
- `timestream:DescribeTable` - Get table metadata
- `timestream:ListMeasures` - List available measures in tables

**Resources**: Scoped to the specified Timestream database and its tables

### Secrets Manager Access
- `secretsmanager:GetSecretValue` - Read API key for authentication
- `secretsmanager:DescribeSecret` - Get secret metadata

**Resources**: Scoped to `bus-simulator/api-key` secret only

### CloudWatch Logs Access
- `logs:CreateLogStream` - Create new log streams
- `logs:PutLogEvents` - Write log events

**Resources**: Scoped to the MCP server log group only

All policies follow the principle of least privilege, granting only the minimum permissions required for the MCP server to function.
```

## Networking Requirements

- **VPC**: Must have private subnets with NAT gateway for outbound connectivity
- **Security Group**: Should allow:
  - Outbound HTTPS (443) to AWS services (Timestream, Secrets Manager)
  - Inbound traffic on container port (8080) if accessed from within VPC

## Monitoring

### CloudWatch Logs

Logs are stored in `/ecs/mcp-server` log group with 30-day retention. Log format:
```
[timestamp] [level] [component] message
```

### Health Checks

The container includes a TCP health check on the configured port:
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Retries**: 3
- **Start Period**: 60 seconds

### Metrics

Monitor these CloudWatch metrics:
- `CPUUtilization`: Should stay below 70% for optimal performance
- `MemoryUtilization`: Should stay below 80%
- `HealthyTaskCount`: Should equal desired count
- `RunningTaskCount`: Should equal desired count

## Troubleshooting

### Task Fails to Start

1. Check CloudWatch logs for startup errors:
   ```bash
   aws logs tail /ecs/mcp-server --follow --region eu-west-1
   ```

2. Verify IAM role permissions for Timestream and Secrets Manager:
   ```bash
   aws iam get-role-policy \
     --role-name bus-simulator-mcp-task-role \
     --policy-name timestream-access \
     --region eu-west-1
   ```

3. Ensure ECR image exists and is accessible:
   ```bash
   aws ecr describe-images \
     --repository-name bus-simulator \
     --region eu-west-1
   ```

4. Check security group allows outbound HTTPS:
   ```bash
   aws ec2 describe-security-groups \
     --group-ids $(terraform output -raw mcp_security_group_id) \
     --region eu-west-1
   ```

### API Gateway Returns 502 Bad Gateway

1. Verify ECS service is running:
   ```bash
   aws ecs describe-services \
     --cluster bus-simulator-cluster \
     --services mcp-server \
     --query 'services[0].runningCount' \
     --region eu-west-1
   ```

2. Check VPC Link status (should be AVAILABLE):
   ```bash
   aws apigatewayv2 get-vpc-link \
     --vpc-link-id $(terraform output -raw mcp_vpc_link_id) \
     --region eu-west-1
   ```

3. Verify security group allows traffic from VPC Link to ECS:
   ```bash
   aws ec2 describe-security-groups \
     --group-ids $(terraform output -raw mcp_security_group_id) \
     --query 'SecurityGroups[0].IpPermissions' \
     --region eu-west-1
   ```

4. Check Service Discovery health:
   ```bash
   aws servicediscovery list-instances \
     --service-id $(terraform output -raw service_discovery_service_id) \
     --region eu-west-1
   ```

### Authentication Errors (401 Unauthorized)

1. Verify API key exists in Secrets Manager:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id bus-simulator/api-key \
     --region eu-west-1
   ```

2. Ensure both required headers are present:
   - `x-api-key`: Must match the key in Secrets Manager
   - `x-group-name`: Must be present (any string value)

3. Check authorizer Lambda logs:
   ```bash
   aws logs tail /aws/lambda/bus-simulator-rest-authorizer --follow --region eu-west-1
   ```

4. Verify authorizer is attached to API Gateway routes:
   ```bash
   aws apigatewayv2 get-routes \
     --api-id $(terraform output -raw mcp_api_id) \
     --region eu-west-1
   ```

### High Memory Usage

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

2. Review query patterns in logs for expensive operations:
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/mcp-server \
     --filter-pattern "query_time_range" \
     --region eu-west-1
   ```

3. Consider increasing memory allocation in Terraform:
   ```hcl
   module "mcp_server" {
     cpu    = "1024"  # Increase from 512
     memory = "2048"  # Increase from 1024
     ...
   }
   ```

### Connection Timeouts

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

3. Review security group rules for outbound HTTPS (443):
   ```bash
   aws ec2 describe-security-groups \
     --group-ids $(terraform output -raw mcp_security_group_id) \
     --query 'SecurityGroups[0].IpPermissionsEgress' \
     --region eu-west-1
   ```

4. Test connectivity from within the VPC:
   ```bash
   # Enable ECS Exec first (set enable_execute_command = true in Terraform)
   aws ecs execute-command \
     --cluster bus-simulator-cluster \
     --task $(aws ecs list-tasks --cluster bus-simulator-cluster --service-name mcp-server --query 'taskArns[0]' --output text) \
     --container mcp-server \
     --interactive \
     --command "/bin/sh"
   ```

### No Data Returned from Queries

1. Verify Timestream has data:
   ```bash
   aws timestream-query query \
     --query-string "SELECT COUNT(*) FROM bus_simulator.people_count" \
     --region eu-west-1
   ```

2. Check entity IDs match configuration:
   ```bash
   aws timestream-query query \
     --query-string "SELECT DISTINCT stop_id FROM bus_simulator.people_count LIMIT 10" \
     --region eu-west-1
   ```

3. Review MCP server logs for query errors:
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/mcp-server \
     --filter-pattern "ERROR" \
     --region eu-west-1
   ```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| ecs_cluster_id | ID of the ECS cluster | string | - | yes |
| ecs_execution_role_arn | ARN of ECS execution role | string | - | yes |
| ecr_repository_url | URL of ECR repository | string | - | yes |
| timestream_database_name | Timestream database name | string | - | yes |
| api_key_secret_id | Secrets Manager secret ID | string | - | yes |
| private_subnet_ids | Private subnet IDs | list(string) | - | yes |
| security_group_id | Security group ID | string | - | yes |
| vpc_id | VPC ID for Service Discovery | string | - | yes |
| vpc_link_security_group_id | Security group for VPC Link | string | - | yes |
| rest_authorizer_invoke_arn | Authorizer Lambda invoke ARN | string | - | yes |
| rest_authorizer_function_name | Authorizer Lambda function name | string | - | yes |
| log_group_name | CloudWatch log group name | string | - | yes |
| cors_allowed_origins | Allowed origins for CORS | list(string) | ["*"] | no |
| cpu | CPU units | string | "512" | no |
| memory | Memory in MB | string | "1024" | no |
| container_port | Container port | number | 8080 | no |
| desired_count | Desired task count | number | 1 | no |
| log_level | Log level | string | "INFO" | no |
| throttling_burst_limit | API throttling burst limit | number | 100 | no |
| throttling_rate_limit | API throttling rate limit | number | 50 | no |
| enable_execute_command | Enable ECS Exec | bool | false | no |
| tags | Resource tags | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| task_definition_arn | ARN of the task definition |
| service_name | Name of the ECS service |
| service_id | ID of the ECS service |
| task_role_arn | ARN of the IAM task role |
| task_role_name | Name of the IAM task role |
| api_endpoint | HTTP API Gateway endpoint URL |
| api_id | HTTP API Gateway ID |
| vpc_link_id | VPC Link ID |
| service_discovery_namespace_id | Service Discovery namespace ID |
| service_discovery_service_arn | Service Discovery service ARN |

## Requirements Validation

This module validates the following requirements:
- **14.7**: MCP server deployed on AWS ECS as containerized service
- **14.8**: MCP server validates API Key by reading from Secrets Manager (IAM role grants access)
- **14.12**: ECS cluster, task definition, and service provisioned via Terraform
- **14.13**: Task definition includes environment variables for Secrets Manager and Timestream access
- **14.15**: ECS service networking configured for secure communication with Timestream and Secrets Manager

## Related Modules

- `iam`: Provides execution and task role ARNs
- `fargate`: Provides ECS cluster and ECR repository
- `timestream`: Provides database name
- `api_gateway`: Provides Secrets Manager secret ID
- `supporting`: Provides VPC networking resources
