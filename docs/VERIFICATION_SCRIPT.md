# Pre-Hackathon Verification Script

## Overview

The `verify_deployment.py` script performs comprehensive checks to ensure the Madrid Bus Real-Time Simulator is ready for the hackathon. It validates that all system components are functioning correctly and that the required historical data has been accumulated.

## Purpose

This script is designed to be run **before the hackathon** (ideally on Day -1) to verify:

1. **Timestream Data Volume**: At least 5 days of historical data exists in all tables
2. **Fargate Service Health**: All three feeder services are running properly
3. **REST API Endpoints**: All API endpoints respond correctly with valid API keys
4. **API Key Authentication**: Authentication is properly enforced (rejects invalid/missing keys)
5. **WebSocket Connection**: WebSocket connections work with API key authentication

## Requirements

### Python Dependencies

```bash
pip install boto3 pyyaml
```

### Optional Dependencies

For WebSocket testing (optional):
```bash
pip install websocket-client
```

If `websocket-client` is not installed, the WebSocket tests will be skipped gracefully.

### AWS Credentials

The script requires AWS credentials with permissions to:
- Query Timestream (`timestream-query:Query`)
- Describe ECS services (`ecs:DescribeServices`, `ecs:ListTasks`, `ecs:DescribeTasks`)
- Access API Gateway (for testing endpoints)

### Terraform State

The script retrieves configuration from Terraform outputs, so you must run it from a directory where Terraform has been applied and the state is accessible.

## Usage

### Basic Usage

```bash
python scripts/verify_deployment.py --region eu-west-1
```

### Verbose Mode

For detailed output including query details and task information:

```bash
python scripts/verify_deployment.py --region eu-west-1 --verbose
```

### Skip WebSocket Tests

If you don't have the `websocket-client` library installed:

```bash
python scripts/verify_deployment.py --region eu-west-1 --skip-websocket
```

## Output

The script provides color-coded output:

- ✓ **Green**: Check passed successfully
- ✗ **Red**: Check failed
- ⚠ **Yellow**: Warning (partial success or expected failure)
- ℹ **Blue**: Informational message

### Example Output

```
================================================================================
Madrid Bus Real-Time Simulator - Pre-Hackathon Verification
================================================================================
Region: eu-west-1
Time: 2024-01-15 10:00:00 UTC

================================================================================
Checking Timestream Data Volume
================================================================================

ℹ Database: bus_simulator

Checking table: people_count
ℹ   Oldest record: 2024-01-10 10:00:00 UTC
ℹ   Newest record: 2024-01-15 10:00:00 UTC
ℹ   Data span: 5.00 days
ℹ   Record count: 432,000
✓ people_count: 5.00 days of data (≥ 5 days required)

Checking table: sensor_data
ℹ   Oldest record: 2024-01-10 10:00:00 UTC
ℹ   Newest record: 2024-01-15 10:00:00 UTC
ℹ   Data span: 5.00 days
ℹ   Record count: 864,000
✓ sensor_data: 5.00 days of data (≥ 5 days required)

Checking table: bus_position
ℹ   Oldest record: 2024-01-10 10:00:00 UTC
ℹ   Newest record: 2024-01-15 10:00:00 UTC
ℹ   Data span: 5.00 days
ℹ   Record count: 216,000
✓ bus_position: 5.00 days of data (≥ 5 days required)

================================================================================
Checking Fargate Service Health
================================================================================

ℹ Cluster: bus-simulator-cluster

Checking service: people-count-feeder
ℹ   Status: ACTIVE
ℹ   Desired: 1, Running: 1, Pending: 0
✓ people-count-feeder: Running (1/1 tasks)

Checking service: sensors-feeder
ℹ   Status: ACTIVE
ℹ   Desired: 1, Running: 1, Pending: 0
✓ sensors-feeder: Running (1/1 tasks)

Checking service: bus-position-feeder
ℹ   Status: ACTIVE
ℹ   Desired: 1, Running: 1, Pending: 0
✓ bus-position-feeder: Running (1/1 tasks)

================================================================================
Testing REST API Endpoints
================================================================================

ℹ REST API Endpoint: https://abc123.execute-api.eu-west-1.amazonaws.com/prod
ℹ Using API key: 12345678...

Testing: People Count (latest)
ℹ   URL: https://abc123.execute-api.eu-west-1.amazonaws.com/prod/people-count/S001?mode=latest
✓ People Count (latest): OK

Testing: Sensors (bus, latest)
ℹ   URL: https://abc123.execute-api.eu-west-1.amazonaws.com/prod/sensors/bus/B001?mode=latest
✓ Sensors (bus, latest): OK

Testing: Sensors (stop, latest)
ℹ   URL: https://abc123.execute-api.eu-west-1.amazonaws.com/prod/sensors/stop/S001?mode=latest
✓ Sensors (stop, latest): OK

Testing: Bus Position (latest)
ℹ   URL: https://abc123.execute-api.eu-west-1.amazonaws.com/prod/bus-position/B001?mode=latest
✓ Bus Position (latest): OK

Testing: Bus Position by Line (latest)
ℹ   URL: https://abc123.execute-api.eu-west-1.amazonaws.com/prod/bus-position/line/L1?mode=latest
✓ Bus Position by Line (latest): OK

================================================================================
Testing API Key Authentication
================================================================================

ℹ REST API Endpoint: https://abc123.execute-api.eu-west-1.amazonaws.com/prod

Test 1: Request without API key
✓ Request correctly rejected (403 Forbidden)

Test 2: Request with invalid API key
✓ Request correctly rejected (403 Forbidden)

Test 3: Request with valid API key
ℹ Using API key: 12345678...
✓ Request succeeded with valid API key

✓ API key authentication is working correctly

================================================================================
Testing WebSocket Connection
================================================================================

ℹ WebSocket Endpoint: https://xyz789.execute-api.eu-west-1.amazonaws.com/prod
ℹ Using API key: 12345678...

Test 1: Connection without API key
✓ Connection correctly rejected: WebSocketBadStatusException

Test 2: Connection with invalid API key
✓ Connection correctly rejected: WebSocketBadStatusException

Test 3: Connection with valid API key
✓ Connection established successfully
✓ WebSocket connection test passed

================================================================================
Verification Summary
================================================================================

✓ Timestream Data Volume: PASSED
✓ Fargate Service Health: PASSED
✓ REST API Endpoints: PASSED
✓ API Key Authentication: PASSED
✓ WebSocket Connection: PASSED

✓ All checks passed! System is ready for hackathon.
```

## Exit Codes

- **0**: All checks passed successfully
- **1**: One or more checks failed

## Integration with Makefile

The verification script is integrated into the Makefile:

```bash
make verify
```

This target runs the verification script with the configured AWS region.

## Troubleshooting

### Timestream Data Volume Check Fails

**Problem**: Less than 5 days of data in one or more tables

**Solutions**:
1. Check when the system was deployed (should be at least 5 days ago)
2. Verify Fargate services are running and generating data
3. Check CloudWatch logs for feeder services to identify issues
4. Query Timestream directly to inspect data:
   ```bash
   aws timestream-query query \
     --query-string "SELECT COUNT(*) FROM bus_simulator.people_count WHERE time > ago(5d)"
   ```

### Fargate Service Health Check Fails

**Problem**: One or more feeder services not running

**Solutions**:
1. Check ECS service status:
   ```bash
   aws ecs describe-services \
     --cluster bus-simulator-cluster \
     --services people-count-feeder sensors-feeder bus-position-feeder
   ```
2. Check task logs in CloudWatch:
   ```bash
   aws logs tail /ecs/people-count-feeder --follow
   ```
3. Verify IAM roles have correct permissions
4. Check if tasks are failing due to resource constraints

### REST API Endpoint Tests Fail

**Problem**: API endpoints return errors or unexpected responses

**Solutions**:
1. Verify Lambda functions are deployed correctly
2. Check Lambda function logs in CloudWatch
3. Test endpoints manually with curl:
   ```bash
   curl -H "x-api-key: YOUR_API_KEY" \
     "https://your-api-endpoint/people-count/S001?mode=latest"
   ```
4. Verify API Gateway configuration and integrations
5. Check if Timestream has data for the requested entities

### API Key Authentication Check Fails

**Problem**: API accepts requests without valid API keys

**Solutions**:
1. Verify API Gateway usage plan is configured correctly
2. Check that routes have `api_key_required = true`
3. Verify API keys are associated with the usage plan
4. Test authentication manually:
   ```bash
   # Should fail with 403
   curl "https://your-api-endpoint/people-count/S001?mode=latest"
   
   # Should succeed
   curl -H "x-api-key: YOUR_API_KEY" \
     "https://your-api-endpoint/people-count/S001?mode=latest"
   ```

### WebSocket Connection Test Fails

**Problem**: WebSocket connections fail or authentication not working

**Solutions**:
1. Verify WebSocket API Gateway is deployed
2. Check custom authorizer Lambda function logs
3. Test WebSocket connection manually:
   ```bash
   # Install wscat if needed
   npm install -g wscat
   
   # Test connection
   wscat -c "wss://your-ws-endpoint?api_key=YOUR_API_KEY"
   ```
4. Verify authorizer is configured correctly in API Gateway
5. Check DynamoDB table for connection tracking exists

## Best Practices

1. **Run Early**: Execute the verification script at least 24 hours before the hackathon to allow time for fixes
2. **Run Multiple Times**: Run the script periodically during the pre-hackathon period to catch issues early
3. **Save Output**: Redirect output to a file for documentation:
   ```bash
   python scripts/verify_deployment.py --region eu-west-1 --verbose > verification_report.txt 2>&1
   ```
4. **Automate**: Consider setting up a cron job or CloudWatch Event to run verification daily
5. **Monitor**: Use CloudWatch dashboards to monitor system health continuously

## Related Documentation

- [API Documentation](API_DOCUMENTATION.md)
- [Export API Keys](EXPORT_API_KEYS.md)
- [Lambda Deployment](LAMBDA_DEPLOYMENT.md)
- [README](../README.md)

## Support

For issues or questions about the verification script:
1. Check the troubleshooting section above
2. Review CloudWatch logs for detailed error messages
3. Consult the main README for system architecture details
4. Contact the development team
