# MCP Server Integration Tests

This document describes the integration tests for the deployed MCP server on AWS ECS.

## Overview

The integration test suite (`scripts/test_mcp_integration.py`) performs comprehensive end-to-end testing of the MCP server deployed on ECS, validating:

1. **MCP Server Connectivity** - Tests that the MCP server is reachable via HTTP API Gateway
2. **Authentication** - Verifies API key validation with AWS Secrets Manager
3. **MCP Tools** - Tests all five MCP tools against deployed Timestream database
4. **Data Consistency** - Compares MCP server responses with REST API responses
5. **Error Handling** - Validates error responses and CloudWatch logging

## Requirements Validated

- **14.7**: MCP server deployed on AWS ECS
- **14.8**: MCP server validates API keys from Secrets Manager
- **14.10**: Valid API key processes requests successfully
- **14.11**: Invalid API key returns authentication error

## Prerequisites

### Required Tools

- Python 3.11+
- AWS CLI configured with credentials
- Terraform (for retrieving outputs)
- boto3 library: `pip install boto3`

### Required Infrastructure

The following must be deployed before running integration tests:

- ECS cluster with MCP server service running
- HTTP API Gateway endpoint for MCP server
- AWS Secrets Manager secret with API key (`bus-simulator/api-key`)
- Timestream database with data (people_count, sensor_data, bus_position tables)
- REST API Gateway endpoints (for data consistency tests)

## Usage

### Basic Usage

```bash
python scripts/test_mcp_integration.py --region eu-west-1
```

### Verbose Mode

```bash
python scripts/test_mcp_integration.py --region eu-west-1 --verbose
```

Verbose mode shows:
- Full request/response payloads
- Detailed comparison data
- Recent CloudWatch log events
- Additional diagnostic information

## Test Suite Details

### Test 1: MCP Server Connectivity on ECS

**Purpose**: Verify the MCP server is running and reachable

**Steps**:
1. Retrieve MCP API endpoint from Terraform outputs
2. Check ECS service status (running tasks, desired count)
3. Make HTTP request to MCP endpoint
4. Verify server responds (even with error for invalid request)

**Success Criteria**:
- ECS service status is ACTIVE
- At least 1 task is running
- HTTP endpoint is reachable

**Example Output**:
```
Test 1: MCP Server Connectivity on ECS
================================================================================

ℹ MCP API Endpoint: https://abc123.execute-api.eu-west-1.amazonaws.com
ℹ ECS Cluster: bus-simulator-cluster
ℹ ECS Service: mcp-server
ℹ Service Status: ACTIVE
ℹ Running Tasks: 1/1
✓ MCP server service is running on ECS
✓ MCP server is reachable (HTTP 400 is expected)
```

### Test 2: MCP Server Authentication

**Purpose**: Verify API key authentication with Secrets Manager

**Steps**:
1. Test request without API key (should fail)
2. Test request with invalid API key (should fail)
3. Test request with valid API key from Secrets Manager (should succeed)

**Success Criteria**:
- Requests without API key are rejected
- Requests with invalid API key are rejected
- Requests with valid API key from Secrets Manager succeed

**Example Output**:
```
Test 2: MCP Server Authentication
================================================================================

Test 2.1: Request without API key
✓ Request correctly rejected: Authentication failed: Missing x-api-key header

Test 2.2: Request with invalid API key
✓ Request correctly rejected: Authentication failed: Invalid API key

Test 2.3: Request with valid API key from Secrets Manager
ℹ Using API key: abc12345...
✓ Request succeeded with valid API key
✓ Authentication with Secrets Manager API key is working correctly
```

### Test 3: MCP Tools Against Deployed Timestream

**Purpose**: Test all five MCP tools with real Timestream data

**Tools Tested**:

1. **query_people_count**
   - Parameters: `stop_id`, `mode=latest`
   - Validates: Returns people count data from Timestream

2. **query_sensor_data**
   - Parameters: `entity_id`, `entity_type`, `mode=latest`
   - Validates: Returns sensor readings from Timestream

3. **query_bus_position**
   - Parameters: `bus_id`, `mode=latest`
   - Validates: Returns bus position data from Timestream

4. **query_line_buses**
   - Parameters: `line_id`, `mode=latest`
   - Validates: Returns all buses on a line from Timestream

5. **query_time_range**
   - Parameters: `data_type`, `entity_id`, `start_time`, `end_time`
   - Validates: Returns time series data over a range

**Success Criteria**:
- All tools return successful responses
- Data is retrieved from Timestream
- Response format matches expected schema

**Example Output**:
```
Test 3: MCP Tools Against Deployed Timestream
================================================================================

Test 3.1: query_people_count tool
✓ query_people_count: OK (returned 1 records)

Test 3.2: query_sensor_data tool
✓ query_sensor_data: OK (returned 1 records)

Test 3.3: query_bus_position tool
✓ query_bus_position: OK (returned 1 records)

Test 3.4: query_line_buses tool
✓ query_line_buses: OK (returned 3 records)

Test 3.5: query_time_range tool
✓ query_time_range: OK (returned 45 records)
```

### Test 4: Data Consistency with REST APIs

**Purpose**: Verify MCP server returns consistent data with REST APIs

**Comparisons**:

1. **People Count Data**
   - Queries same stop from MCP and REST API
   - Compares timestamps (should be within 1 minute)
   - Compares counts (should match)

2. **Bus Position Data**
   - Queries same bus from MCP and REST API
   - Compares coordinates (should be within ~100m)
   - Compares timestamps

**Success Criteria**:
- Timestamps are within 60 seconds
- Coordinates are within 0.001 degrees (~100m)
- Data values match between sources

**Example Output**:
```
Test 4: Data Consistency with REST APIs
================================================================================

ℹ MCP Endpoint: https://mcp-api.example.com
ℹ REST Endpoint: https://rest-api.example.com

Test 4.1: Compare people count data
ℹ MCP time: 2025-01-15T14:30:00Z, count: 12
ℹ REST time: 2025-01-15T14:30:05Z, count: 12
✓ People count data is consistent (time diff: 5.0s)

Test 4.2: Compare bus position data
ℹ MCP position: (40.4657, -3.6886)
ℹ REST position: (40.4658, -3.6885)
✓ Bus position data is consistent
```

### Test 5: Error Handling and Logging

**Purpose**: Validate error responses and CloudWatch logging

**Error Scenarios Tested**:

1. **Non-existent Entity**
   - Query with invalid stop/bus ID
   - Should return empty results or error

2. **Invalid Entity Type**
   - Query with invalid entity_type parameter
   - Should reject with error

3. **Missing Required Parameter**
   - Query without required parameter
   - Should reject with error

4. **Invalid Timestamp Format**
   - Query with malformed timestamp
   - Should reject with error

5. **CloudWatch Logs**
   - Verify log group exists
   - Check for recent log events
   - Validate logging is working

**Success Criteria**:
- Invalid requests are rejected with appropriate errors
- CloudWatch log group contains recent events
- Error messages are descriptive

**Example Output**:
```
Test 5: Error Handling and Logging
================================================================================

Test 5.1: Query with non-existent stop ID
✓ Non-existent stop handled correctly (empty results)

Test 5.2: Query with invalid entity type
✓ Invalid entity type rejected: Invalid entity_type: invalid

Test 5.3: Query with missing required parameter
✓ Missing parameter rejected: Missing required parameter: stop_id

Test 5.4: Query with invalid timestamp format
✓ Invalid timestamp rejected: Invalid timestamp format

Test 5.5: Check CloudWatch logs for MCP server
ℹ Log group: /ecs/mcp-server
✓ Found 3 log streams
✓ Found 10 recent log events
```

## Test Results Interpretation

### All Tests Passed

```
Test Summary
================================================================================

✓ MCP Server Connectivity: PASSED
✓ MCP Authentication: PASSED
✓ MCP Tools: PASSED
✓ Data Consistency: PASSED
✓ Error Handling: PASSED

✓ All integration tests passed!
```

**Meaning**: The MCP server is fully functional and ready for use.

### Some Tests Failed

```
Test Summary
================================================================================

✓ MCP Server Connectivity: PASSED
✗ MCP Authentication: FAILED
✓ MCP Tools: PASSED
✗ Data Consistency: FAILED
✓ Error Handling: PASSED

✗ Some tests failed. Please review and fix issues.
```

**Meaning**: There are issues that need to be addressed before the MCP server is production-ready.

## Troubleshooting

### Test 1 Fails: MCP Server Connectivity

**Symptoms**:
- Cannot retrieve MCP API endpoint
- ECS service not running
- HTTP connection fails

**Solutions**:
1. Check Terraform deployment: `cd terraform && terraform output`
2. Verify ECS service: `aws ecs describe-services --cluster <cluster> --services mcp-server`
3. Check ECS task logs: `aws logs tail /ecs/mcp-server --follow`
4. Verify API Gateway: `aws apigatewayv2 get-apis`

### Test 2 Fails: Authentication

**Symptoms**:
- Cannot retrieve API key from Secrets Manager
- Valid API key is rejected
- Invalid API key is accepted

**Solutions**:
1. Check secret exists: `aws secretsmanager get-secret-value --secret-id bus-simulator/api-key`
2. Verify secret format: Should be `{"api_key": "value"}`
3. Check IAM permissions for ECS task role
4. Review authentication middleware logs in CloudWatch

### Test 3 Fails: MCP Tools

**Symptoms**:
- Tools return errors
- No data returned from Timestream
- Timestream query fails

**Solutions**:
1. Verify Timestream database exists: `aws timestream-query describe-database --database-name bus_simulator`
2. Check Timestream tables have data: Run queries manually
3. Verify ECS task has Timestream permissions
4. Check feeder services are running and generating data

### Test 4 Fails: Data Consistency

**Symptoms**:
- Timestamps differ significantly
- Data values don't match
- Cannot retrieve data from REST API

**Solutions**:
1. Check if feeder services are running continuously
2. Verify both MCP and REST APIs query the same Timestream database
3. Check for clock skew issues
4. Review data generation logic in feeder services

### Test 5 Fails: Error Handling

**Symptoms**:
- Invalid requests are accepted
- No CloudWatch logs
- Error messages are unclear

**Solutions**:
1. Review error handling in MCP server code
2. Check CloudWatch log group permissions
3. Verify logging configuration in ECS task definition
4. Test error scenarios manually

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: MCP Server Integration Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install boto3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-west-1
      
      - name: Run MCP integration tests
        run: python scripts/test_mcp_integration.py --region eu-west-1
```

### Pre-Deployment Validation

Run integration tests before deploying to production:

```bash
# Deploy infrastructure
cd terraform
terraform apply

# Wait for services to stabilize
sleep 60

# Run integration tests
cd ..
python scripts/test_mcp_integration.py --region eu-west-1

# If tests pass, proceed with deployment
if [ $? -eq 0 ]; then
    echo "Integration tests passed. Deployment successful."
else
    echo "Integration tests failed. Rolling back..."
    cd terraform
    terraform destroy -auto-approve
    exit 1
fi
```

## Manual Testing

For manual testing of individual tools, use the MCP client directly:

```python
import json
import urllib.request

# Configuration
mcp_endpoint = "https://your-mcp-endpoint.execute-api.eu-west-1.amazonaws.com"
api_key = "your-api-key"

# Prepare request
payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "query_people_count",
        "arguments": {
            "stop_id": "S001",
            "mode": "latest",
            "_headers": {
                "x-api-key": api_key,
                "x-group-name": "manual-test"
            }
        }
    }
}

# Make request
req = urllib.request.Request(
    mcp_endpoint,
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json', 'x-api-key': api_key}
)

with urllib.request.urlopen(req) as response:
    result = json.loads(response.read().decode('utf-8'))
    print(json.dumps(result, indent=2))
```

## Related Documentation

- [MCP Server Testing Guide](TESTING.md) - Local container testing
- [MCP Server Test Results](TEST_RESULTS.md) - Container test results
- [MCP Server README](README.md) - General MCP server documentation
- [Design Document](../.kiro/specs/madrid-bus-realtime-simulator/design.md) - System architecture

## Support

For issues or questions about integration tests:

1. Check CloudWatch logs: `/ecs/mcp-server`
2. Review ECS task status and events
3. Verify Terraform outputs are correct
4. Run tests in verbose mode for detailed diagnostics

