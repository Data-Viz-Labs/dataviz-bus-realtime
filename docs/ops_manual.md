# Operations Manual

This document provides comprehensive operational procedures for the Madrid Bus Real-Time Simulator.

## Table of Contents

1. [System Monitoring](#system-monitoring)
2. [Testing Procedures](#testing-procedures)
3. [Troubleshooting](#troubleshooting)
4. [Maintenance](#maintenance)
5. [Cost Management](#cost-management)
6. [Security Operations](#security-operations)
7. [Incident Response](#incident-response)

---

## System Monitoring

### CloudWatch Dashboards

Monitor system health through CloudWatch metrics:

#### Feeder Services Metrics
- CPU utilization
- Memory utilization
- Task count (running, pending, stopped)
- Network throughput

**View metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=people-count-feeder Name=ClusterName,Value=bus-simulator-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region eu-west-1
```

#### API Gateway Metrics
- Request count
- Latency (p50, p90, p99)
- 4xx and 5xx errors
- Integration latency

**View API metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value=madrid-bus-simulator-http \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region eu-west-1
```

#### Lambda Metrics
- Invocations
- Duration
- Errors
- Throttles
- Concurrent executions

**View Lambda metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=bus-simulator-people-count \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region eu-west-1
```

#### Timestream Metrics
- Write throughput
- Query latency
- Storage utilization

#### MCP Server Metrics
- CPU and memory utilization
- Task count
- Health check status
- Request count and latency

### CloudWatch Logs

All services log to CloudWatch Logs with the following log groups:

#### Lambda Functions
- `/aws/lambda/bus-simulator-people-count`
- `/aws/lambda/bus-simulator-sensors`
- `/aws/lambda/bus-simulator-bus-position`
- `/aws/lambda/bus-simulator-websocket-handler`
- `/aws/lambda/bus-simulator-rest-authorizer`
- `/aws/lambda/bus-simulator-websocket-authorizer-v2`

**Tail logs:**
```bash
aws logs tail /aws/lambda/bus-simulator-people-count --follow --region eu-west-1
```

**Filter logs:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/bus-simulator-people-count \
  --filter-pattern "ERROR" \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --region eu-west-1
```

#### Fargate Services
- `/ecs/people-count-feeder`
- `/ecs/sensors-feeder`
- `/ecs/bus-position-feeder`
- `/ecs/mcp-server`

**Tail feeder logs:**
```bash
aws logs tail /ecs/people-count-feeder --follow --region eu-west-1
```

**Filter by group name:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/mcp-server \
  --filter-pattern "team-alpha" \
  --region eu-west-1
```

### Health Checks

#### Check Fargate Service Health

```bash
aws ecs describe-services \
  --cluster bus-simulator-cluster \
  --services people-count-feeder sensors-feeder bus-position-feeder mcp-server \
  --region eu-west-1 \
  --query 'services[*].[serviceName,status,runningCount,desiredCount]' \
  --output table
```

#### Check Lambda Function Health

```bash
# Get recent invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=bus-simulator-people-count \
  --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Sum \
  --region eu-west-1
```

#### Check Timestream Data Volume

```bash
aws timestream-query query \
  --query-string "SELECT COUNT(*) as count FROM bus_simulator.people_count WHERE time > ago(1h)" \
  --region eu-west-1
```

#### Check API Gateway Health

```bash
# Test REST API
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: health-check" \
     "$API_URL/people-count/S001?mode=latest"

# Test MCP Server
curl -X POST "$MCP_ENDPOINT/mcp/list-tools" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: health-check" \
  -H "Content-Type: application/json"
```

---

## Testing Procedures

### Test Pyramid

The project follows a three-level test pyramid:

```
        /\
       /  \
      / E2E \      ← End-to-End Tests (Shell Scripts)
     /------\
    /  INT   \     ← Integration Tests (Python + AWS)
   /----------\
  /   UNIT     \   ← Unit Tests (Python, Local)
 /--------------\
```

### 1. Unit Tests

**Purpose**: Test individual components in isolation

**Execution Time**: < 1 minute

**Requirements**: None (runs locally)

**Run tests:**
```bash
make test-unit
```

**Or directly:**
```bash
pytest tests/ -m "not integration and not e2e" -v
```

**Coverage report:**
```bash
pytest tests/ -m "not integration and not e2e" --cov=src --cov-report=html
```

### 2. Integration Tests

**Purpose**: Test components interacting with AWS services

**Execution Time**: 5-10 minutes

**Requirements**:
- AWS credentials configured
- Infrastructure deployed
- IAM permissions for Timestream, Secrets Manager, Lambda, ECS

**Run tests:**
```bash
make test-int
```

**Or directly:**
```bash
pytest tests/ -m integration -v
```

**Test specific integration:**
```bash
# Test Timestream integration
pytest tests/test_timestream_integration.py -v

# Test MCP server
pytest tests/test_mcp_*.py -v

# Test authentication
pytest tests/test_auth_integration.py -v
```

### 3. End-to-End Tests

**Purpose**: Test complete user workflows through public APIs

**Execution Time**: 10-15 minutes

**Requirements**:
- AWS credentials configured
- Infrastructure deployed
- curl and jq installed

**Run all E2E tests:**
```bash
make test-e2e
```

**Run specific E2E tests:**
```bash
cd tests/api

# Test REST APIs
./test_people_count_latest.sh
./test_sensors_latest.sh
./test_bus_position_latest.sh

# Test WebSocket
./test_websocket.sh

# Test MCP server
./test_mcp_health.sh
./test_mcp_auth.sh
./test_mcp_tools.sh

# Test authentication
./test_auth.sh
```

### Pre-Hackathon Verification

Run comprehensive verification before hackathon:

```bash
make verify AWS_REGION=eu-west-1
```

**Or with verbose output:**
```bash
python scripts/verify_deployment.py --region eu-west-1 --verbose
```

**Verification checks:**
- ✓ Timestream has at least 5 days of historical data
- ✓ All Fargate services are running
- ✓ REST API endpoints respond correctly
- ✓ API key authentication is enforced
- ✓ WebSocket connections work properly

### Continuous Testing

Set up automated testing:

```bash
# Install pre-commit hooks
make setup-hooks

# Run all tests before commit
pre-commit run --all-files
```

---

## Troubleshooting

### Common Issues

#### 1. Feeder Services Not Starting

**Symptoms:**
- ECS tasks in STOPPED state
- No data being written to Timestream
- CloudWatch logs show errors

**Diagnosis:**
```bash
# Check service status
aws ecs describe-services \
  --cluster bus-simulator-cluster \
  --services people-count-feeder \
  --region eu-west-1

# Check stopped tasks
aws ecs list-tasks \
  --cluster bus-simulator-cluster \
  --service-name people-count-feeder \
  --desired-status STOPPED \
  --region eu-west-1

# Get task details
aws ecs describe-tasks \
  --cluster bus-simulator-cluster \
  --tasks <task-arn> \
  --region eu-west-1
```

**Common causes:**
- IAM role missing Timestream permissions
- Configuration file (lines.yaml) not loaded in S3
- Container image build errors
- Resource constraints (CPU/memory)

**Solutions:**
```bash
# Check IAM role permissions
aws iam get-role-policy \
  --role-name bus-simulator-feeder-task-role \
  --policy-name timestream-access \
  --region eu-west-1

# Verify S3 configuration
aws s3 ls s3://bus-simulator-config-<account-id>/

# Check CloudWatch logs
aws logs tail /ecs/people-count-feeder --follow --region eu-west-1

# Restart service
aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service people-count-feeder \
  --force-new-deployment \
  --region eu-west-1
```

#### 2. API Returning 404 Errors

**Symptoms:**
- REST API returns "No data found"
- Queries return empty results

**Diagnosis:**
```bash
# Check if Timestream has data
aws timestream-query query \
  --query-string "SELECT COUNT(*) FROM bus_simulator.people_count" \
  --region eu-west-1

# Check data age
aws timestream-query query \
  --query-string "SELECT MIN(time) as oldest, MAX(time) as newest FROM bus_simulator.people_count" \
  --region eu-west-1

# Verify entity IDs exist
aws timestream-query query \
  --query-string "SELECT DISTINCT stop_id FROM bus_simulator.people_count" \
  --region eu-west-1
```

**Common causes:**
- Feeder services not running
- Querying non-existent entity IDs
- Timestamp out of data retention range
- Data not yet generated

**Solutions:**
- Verify feeder services are running
- Check entity IDs in `data/lines.yaml`
- Use `mode=latest` instead of historical timestamps
- Wait for data generation (feeders run every 30-60 seconds)

#### 3. Lambda Timeout Errors

**Symptoms:**
- API returns 504 Gateway Timeout
- Lambda logs show "Task timed out"

**Diagnosis:**
```bash
# Check Lambda duration metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=bus-simulator-people-count \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum \
  --region eu-west-1

# Check Lambda logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/bus-simulator-people-count \
  --filter-pattern "Task timed out" \
  --region eu-west-1
```

**Common causes:**
- Timestream query taking too long
- Large result sets
- Cold start delays
- Insufficient memory allocation

**Solutions:**
```bash
# Increase Lambda timeout (via Terraform)
# Edit terraform/modules/api-gateway/main.tf
resource "aws_lambda_function" "people_count_api" {
  timeout = 60  # Increase from 30
  memory_size = 512  # Increase if needed
}

# Apply changes
cd terraform
terraform apply

# Optimize Timestream queries
# Add time range filters
# Limit result set size
```

#### 4. WebSocket Connection Failures

**Symptoms:**
- WebSocket connection immediately closes
- 401 Unauthorized errors
- No messages received

**Diagnosis:**
```bash
# Test WebSocket connection
wscat -c "wss://$WS_ENDPOINT/production?api_key=$API_KEY&group_name=test"

# Check authorizer logs
aws logs tail /aws/lambda/bus-simulator-websocket-authorizer-v2 --follow --region eu-west-1

# Check WebSocket handler logs
aws logs tail /aws/lambda/bus-simulator-websocket-handler --follow --region eu-west-1

# Check DynamoDB connections table
aws dynamodb scan \
  --table-name bus-simulator-websocket-connections \
  --region eu-west-1
```

**Common causes:**
- Missing or invalid API key
- Missing group_name parameter
- Authorizer Lambda errors
- DynamoDB table issues

**Solutions:**
- Verify API key from Secrets Manager
- Include both api_key and group_name parameters
- Check authorizer Lambda has Secrets Manager permissions
- Verify DynamoDB table exists and is accessible

#### 5. MCP Server Issues

**Symptoms:**
- MCP server returns 502 Bad Gateway
- 401 Unauthorized errors
- Slow response times

**Diagnosis:**
```bash
# Check ECS service status
aws ecs describe-services \
  --cluster bus-simulator-cluster \
  --services mcp-server \
  --region eu-west-1

# Check task health
aws ecs describe-tasks \
  --cluster bus-simulator-cluster \
  --tasks $(aws ecs list-tasks --cluster bus-simulator-cluster --service-name mcp-server --query 'taskArns[0]' --output text) \
  --region eu-west-1

# View MCP server logs
aws logs tail /ecs/mcp-server --follow --region eu-west-1

# Check VPC Link status
aws apigatewayv2 get-vpc-link \
  --vpc-link-id $(cd terraform && terraform output -raw mcp_vpc_link_id) \
  --region eu-west-1

# Test MCP endpoint
curl -X POST "$MCP_ENDPOINT/mcp/list-tools" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: test" \
  -H "Content-Type: application/json"
```

**Common causes:**
- ECS task not running
- VPC Link not available
- Security group blocking traffic
- Authentication errors
- High memory/CPU usage

**Solutions:**
```bash
# Restart ECS service
aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service mcp-server \
  --force-new-deployment \
  --region eu-west-1

# Verify security group rules
aws ec2 describe-security-groups \
  --group-ids $(cd terraform && terraform output -raw mcp_security_group_id) \
  --region eu-west-1

# Check API key
aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --region eu-west-1

# Scale up if needed (via Terraform)
# Edit terraform/modules/mcp-server/main.tf
resource "aws_ecs_service" "mcp_server" {
  desired_count = 2  # Increase from 1
}
```

#### 6. Authentication Errors

**Symptoms:**
- 401 Unauthorized responses
- "Missing x-api-key header" errors
- "Invalid API key" errors

**Diagnosis:**
```bash
# Verify API key exists
aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString \
  --output text \
  --region eu-west-1

# Check authorizer logs
aws logs tail /aws/lambda/bus-simulator-rest-authorizer --follow --region eu-west-1

# Test with invalid key (should fail)
curl -H "x-api-key: invalid-key" \
     -H "x-group-name: test" \
     "$API_URL/people-count/S001?mode=latest"

# Test without group name (should fail)
curl -H "x-api-key: $API_KEY" \
     "$API_URL/people-count/S001?mode=latest"
```

**Common causes:**
- API key not retrieved correctly
- Missing x-group-name header
- Authorizer Lambda errors
- Secrets Manager permissions issues

**Solutions:**
- Verify both headers are included in requests
- Check authorizer Lambda has Secrets Manager read permissions
- Verify API key value matches Secrets Manager
- Check CloudWatch logs for authorizer errors

---

## Maintenance

### Regular Maintenance Tasks

#### Daily
- Monitor CloudWatch dashboards
- Check feeder service health
- Review error logs
- Verify data generation

#### Weekly
- Review cost metrics
- Check Timestream storage utilization
- Analyze API usage patterns
- Review security logs

#### Monthly
- Update dependencies
- Review and optimize queries
- Analyze performance metrics
- Update documentation

### Data Retention

**Timestream Retention Policies:**
- Memory store: 24 hours (fast queries)
- Magnetic store: 30 days (historical queries)

**Modify retention:**
```bash
# Via Terraform
# Edit terraform/modules/timestream/main.tf
resource "aws_timestreamwrite_table" "people_count" {
  retention_properties {
    memory_store_retention_period_in_hours  = 24
    magnetic_store_retention_period_in_days = 30
  }
}

# Apply changes
cd terraform
terraform apply
```

### Configuration Updates

**Update bus lines configuration:**

1. Edit `data/lines.yaml`
2. Reload configuration:
   ```bash
   make load-config AWS_REGION=eu-west-1
   ```
3. Restart feeder services:
   ```bash
   aws ecs update-service \
     --cluster bus-simulator-cluster \
     --service people-count-feeder \
     --force-new-deployment \
     --region eu-west-1
   
   aws ecs update-service \
     --cluster bus-simulator-cluster \
     --service sensors-feeder \
     --force-new-deployment \
     --region eu-west-1
   
   aws ecs update-service \
     --cluster bus-simulator-cluster \
     --service bus-position-feeder \
     --force-new-deployment \
     --region eu-west-1
   ```

### Lambda Function Updates

**Update Lambda function code:**

1. Package Lambda:
   ```bash
   make package-lambda LAMBDA=people_count_api
   ```

2. Deploy via Terraform:
   ```bash
   cd terraform
   terraform apply
   ```

3. Verify deployment:
   ```bash
   aws lambda get-function \
     --function-name bus-simulator-people-count \
     --region eu-west-1
   ```

### Container Image Updates

**Update feeder container images:**

1. Build new images:
   ```bash
   make build-feeders
   ```

2. Push to ECR:
   ```bash
   make push-images AWS_REGION=eu-west-1
   ```

3. Update ECS services:
   ```bash
   aws ecs update-service \
     --cluster bus-simulator-cluster \
     --service people-count-feeder \
     --force-new-deployment \
     --region eu-west-1
   ```

---

## Cost Management

### Budget Monitoring

**Check current costs:**
```bash
make check-costs AWS_REGION=eu-west-1
```

**Or directly:**
```bash
python scripts/check_costs.py --region eu-west-1
```

**View budget status:**
```bash
aws budgets describe-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget-name bus-simulator-monthly-budget
```

### Cost Optimization

**Reduce Fargate costs:**
- Scale down feeder services during low-usage periods
- Use smaller CPU/memory configurations
- Reduce task count if acceptable

**Reduce Timestream costs:**
- Adjust retention policies
- Optimize query patterns
- Use memory store for recent data

**Reduce Lambda costs:**
- Optimize function memory allocation
- Reduce timeout values
- Use reserved concurrency

**Reduce API Gateway costs:**
- Enable caching
- Implement request throttling
- Use WebSocket for real-time updates instead of polling

### Cost Estimation

**Run Infracost:**
```bash
make infracost-check
```

**Or directly:**
```bash
cd terraform
infracost breakdown --path=. --format=table
```

---

## Security Operations

### API Key Management

**Rotate API key:**

1. Generate new key:
   ```bash
   NEW_KEY=$(openssl rand -base64 32)
   ```

2. Update Secrets Manager:
   ```bash
   aws secretsmanager update-secret \
     --secret-id bus-simulator/api-key \
     --secret-string "{\"api_key\":\"$NEW_KEY\"}" \
     --region eu-west-1
   ```

3. Distribute new key to participants

4. Wait for authorization cache to expire (5 minutes for REST API)

**Export API keys:**
```bash
python scripts/export_api_keys.py --region eu-west-1 --output api_keys.txt
```

### Security Auditing

**Review CloudTrail logs:**
```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::SecretsManager::Secret \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --region eu-west-1
```

**Check IAM permissions:**
```bash
# List all IAM roles
aws iam list-roles --query 'Roles[?contains(RoleName, `bus-simulator`)].RoleName' --output table

# Get role policies
aws iam list-role-policies --role-name bus-simulator-feeder-task-role
```

**Review security groups:**
```bash
aws ec2 describe-security-groups \
  --filters "Name=tag:Project,Values=Madrid-Bus-Simulator" \
  --region eu-west-1
```

### Compliance

**Enable AWS Config:**
- Track configuration changes
- Monitor compliance rules
- Audit resource configurations

**Enable GuardDuty:**
- Detect suspicious activity
- Monitor for threats
- Alert on security findings

---

## Incident Response

### Incident Classification

**Severity Levels:**

- **P1 (Critical)**: Complete system outage, all APIs down
- **P2 (High)**: Major functionality impaired, some APIs down
- **P3 (Medium)**: Minor functionality impaired, degraded performance
- **P4 (Low)**: Cosmetic issues, no functional impact

### Incident Response Procedures

#### P1: Complete System Outage

1. **Immediate Actions:**
   - Check AWS Service Health Dashboard
   - Verify all feeder services are running
   - Check API Gateway status
   - Review CloudWatch alarms

2. **Diagnosis:**
   ```bash
   # Check all services
   aws ecs describe-services \
     --cluster bus-simulator-cluster \
     --services people-count-feeder sensors-feeder bus-position-feeder mcp-server \
     --region eu-west-1
   
   # Check API Gateway
   aws apigatewayv2 get-apis \
     --query 'Items[?Name==`madrid-bus-simulator-http`]' \
     --region eu-west-1
   
   # Check Lambda functions
   aws lambda list-functions \
     --query 'Functions[?starts_with(FunctionName, `bus-simulator`)]' \
     --region eu-west-1
   ```

3. **Resolution:**
   - Restart failed services
   - Redeploy if necessary
   - Verify data flow restored

4. **Communication:**
   - Notify stakeholders
   - Provide status updates
   - Document incident

#### P2: Major Functionality Impaired

1. **Immediate Actions:**
   - Identify affected components
   - Check CloudWatch logs
   - Review recent changes

2. **Diagnosis:**
   - Isolate failing component
   - Review error logs
   - Check dependencies

3. **Resolution:**
   - Apply targeted fix
   - Monitor recovery
   - Verify functionality

#### P3/P4: Minor Issues

1. **Standard troubleshooting procedures**
2. **Schedule fix during maintenance window**
3. **Document for future reference**

### Post-Incident Review

After resolving incidents:

1. **Document incident:**
   - Timeline of events
   - Root cause analysis
   - Resolution steps
   - Lessons learned

2. **Implement improvements:**
   - Update monitoring
   - Add automated checks
   - Improve documentation
   - Enhance alerting

3. **Share knowledge:**
   - Update runbooks
   - Train team members
   - Update documentation

---

## Additional Resources

- [API Documentation](./UI.md)
- [Deployment Manual](./deployment_manual.md)
- [Main README](../README.md)
- [Testing Strategy](./TESTING_STRATEGY.md)
- [Cost Management](./COST_MANAGEMENT.md)

## Support Contacts

For operational support:
- Check CloudWatch logs first
- Review this operations manual
- Consult troubleshooting section
- Open GitHub issue if needed
