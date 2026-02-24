# IAM Role Implementation for MCP Server

## Overview

This document describes the IAM role and policies created for the MCP server ECS task as part of Task 31.23.

## Implementation Summary

The IAM role grants the MCP server container the necessary permissions to:
1. Read API keys from AWS Secrets Manager for authentication
2. Query time series data from AWS Timestream database
3. Write logs to AWS CloudWatch Logs

## Resources Created

### IAM Role: `mcp-server-task-role`

**Purpose**: Allows the MCP server ECS task to access AWS services

**Trust Policy**: Allows ECS tasks service to assume this role

**Attached Policies**:
- `mcp-server-secrets-manager-read`
- `mcp-server-timestream-query`
- `mcp-server-cloudwatch-logs-write`

## Policy Details

### 1. Secrets Manager Read Policy

**Policy Name**: `mcp-server-secrets-manager-read`

**Purpose**: Allows reading the API key from Secrets Manager for authentication

**Permissions**:
- `secretsmanager:GetSecretValue` - Retrieve the secret value
- `secretsmanager:DescribeSecret` - Get secret metadata

**Resource Scope**: 
```
arn:aws:secretsmanager:{region}:{account}:secret:bus-simulator/api-key-*
```

**Requirement**: 14.8 - MCP server validates API Key by reading from Secrets Manager

### 2. Timestream Query Policy

**Policy Name**: `mcp-server-timestream-query`

**Purpose**: Allows querying time series data from Timestream database

**Permissions**:
- `timestream:DescribeEndpoints` - Discover Timestream service endpoints
- `timestream:Select` - Execute SELECT queries on time series data
- `timestream:DescribeTable` - Get table metadata
- `timestream:ListMeasures` - List available measures in tables

**Resource Scope**:
```
arn:aws:timestream:{region}:{account}:database/{database_name}
arn:aws:timestream:{region}:{account}:database/{database_name}/table/*
```

**Note**: `DescribeEndpoints` requires wildcard resource (`*`) as per AWS requirements

**Requirement**: 14.13 - Task definition includes environment variables for accessing Timestream_DB

### 3. CloudWatch Logs Write Policy

**Policy Name**: `mcp-server-cloudwatch-logs-write`

**Purpose**: Allows writing application logs to CloudWatch Logs

**Permissions**:
- `logs:CreateLogStream` - Create new log streams
- `logs:PutLogEvents` - Write log events to streams

**Resource Scope**:
```
arn:aws:logs:{region}:{account}:log-group:{log_group_name}:*
```

**Requirement**: 14.13 - Task definition includes environment variables for accessing CloudWatch

## Security Considerations

### Least Privilege Principle

All policies follow the principle of least privilege:
- Secrets Manager access is scoped to only the `bus-simulator/api-key` secret
- Timestream access is scoped to the specific database and its tables
- CloudWatch Logs access is scoped to the MCP server log group only

### Resource-Based Scoping

All policies use specific resource ARNs rather than wildcards where possible:
- Secrets Manager: Scoped to specific secret name pattern
- Timestream: Scoped to specific database and tables
- CloudWatch Logs: Scoped to specific log group

### No Write Access to Timestream

The MCP server has read-only access to Timestream:
- Only `Select` and `Describe` operations are allowed
- No `Write`, `Update`, or `Delete` permissions

## Integration with ECS Task Definition

The IAM role is automatically attached to the ECS task definition in `main.tf`:

```hcl
resource "aws_ecs_task_definition" "mcp_server" {
  # ...
  task_role_arn = aws_iam_role.mcp_task_role.arn
  # ...
}
```

## Environment Variables

The task definition configures these environment variables for the MCP server:

- `SECRET_ID`: `bus-simulator/api-key` - Used to retrieve API key from Secrets Manager
- `TIMESTREAM_DATABASE`: Database name - Used to query Timestream
- `AWS_REGION`: AWS region - Used for service endpoints

## Validation

The IAM role implementation validates the following requirements:

- **Requirement 14.8**: MCP server validates API Key by reading from Secrets Manager
  - ✅ IAM role grants `secretsmanager:GetSecretValue` permission
  - ✅ Access scoped to `bus-simulator/api-key` secret

- **Requirement 14.13**: Task definition includes environment variables for accessing Secrets Manager and Timestream
  - ✅ IAM role grants Timestream query permissions
  - ✅ IAM role grants Secrets Manager read permissions
  - ✅ Environment variables configured in task definition

- **Requirement 14.15**: ECS service networking configured for secure communication
  - ✅ IAM role allows secure API-based access to AWS services
  - ✅ No public internet access required for AWS service communication

## Module Changes

### Files Created
- `iam.tf` - IAM role and policy definitions

### Files Modified
- `main.tf` - Updated to use locally created IAM role
- `variables.tf` - Removed `ecs_task_role_arn` variable (now created internally)
- `outputs.tf` - Added `task_role_arn` and `task_role_name` outputs
- `README.md` - Updated documentation to reflect IAM role creation

## Usage

The module now automatically creates the IAM role. Users no longer need to pass `ecs_task_role_arn`:

```hcl
module "mcp_server" {
  source = "./modules/mcp_server"

  # ECS configuration
  ecs_cluster_id         = module.fargate.cluster_id
  ecs_execution_role_arn = module.iam.ecs_execution_role_arn
  # ecs_task_role_arn is no longer required - created automatically

  # ... other variables
}
```

## Testing

To validate the IAM role configuration:

1. **Terraform Validation**:
   ```bash
   cd terraform/modules/mcp_server
   terraform init -backend=false
   terraform validate
   ```

2. **Policy Simulation** (after deployment):
   ```bash
   aws iam simulate-principal-policy \
     --policy-source-arn arn:aws:iam::ACCOUNT:role/mcp-server-task-role \
     --action-names secretsmanager:GetSecretValue \
     --resource-arns arn:aws:secretsmanager:REGION:ACCOUNT:secret:bus-simulator/api-key-*
   ```

3. **Runtime Verification**:
   - Deploy the MCP server
   - Check CloudWatch Logs for successful API key retrieval
   - Verify Timestream queries execute successfully
   - Confirm logs are written to CloudWatch

## Troubleshooting

### Access Denied Errors

If the MCP server encounters access denied errors:

1. **Secrets Manager**: Verify the secret name matches `bus-simulator/api-key`
2. **Timestream**: Verify the database name matches the configured value
3. **CloudWatch Logs**: Verify the log group exists and name matches

### Policy Updates

If additional permissions are needed:

1. Update the relevant policy document in `iam.tf`
2. Run `terraform plan` to review changes
3. Run `terraform apply` to update the policy
4. ECS will automatically use the updated policy (no task restart required)

## References

- [AWS ECS Task IAM Roles](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)
- [AWS Secrets Manager IAM Policies](https://docs.aws.amazon.com/secretsmanager/latest/userguide/auth-and-access_identity-based-policies.html)
- [AWS Timestream IAM Policies](https://docs.aws.amazon.com/timestream/latest/developerguide/security_iam_service-with-iam.html)
- [AWS CloudWatch Logs IAM Policies](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/permissions-reference-cwl.html)
