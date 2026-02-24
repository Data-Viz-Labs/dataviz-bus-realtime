# API Testing Scripts

This directory contains shell scripts for testing all Madrid Bus Real-Time Simulator API endpoints. These scripts demonstrate how to interact with the APIs and can be used for validation, debugging, and as examples for hackathon participants.

## Prerequisites

- `curl` - Command-line HTTP client
- `jq` - JSON processor for formatting output (optional but recommended)
- `wscat` - WebSocket client for testing WebSocket connections (install with `npm install -g wscat`)

### Install jq

```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq

# CentOS/RHEL
sudo yum install jq
```

### Install wscat

```bash
npm install -g wscat
```

## Configuration

Before running the test scripts, you need to set up your environment variables:

### Method 1: Environment Variables

```bash
export API_KEY="your-api-key-here"
export GROUP_NAME="your-group-name"
export API_URL="https://your-api-id.execute-api.eu-west-1.amazonaws.com"
export WS_URL="wss://your-api-id.execute-api.eu-west-1.amazonaws.com/production"
export MCP_URL="https://your-mcp-api-id.execute-api.eu-west-1.amazonaws.com/prod"
```

### Method 2: Get from AWS Secrets Manager

```bash
# Get API key from Secrets Manager
export API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString \
  --output text | jq -r '.api_key')

# Get API URLs from Terraform outputs
cd ../../terraform
export API_URL=$(terraform output -raw rest_api_url)
export WS_URL=$(terraform output -raw websocket_api_url)
export MCP_URL=$(terraform output -raw mcp_api_endpoint)
cd ../tests/api

# Set your group name
export GROUP_NAME="your-group-name"
```

### Method 3: Source Configuration File

Create a file `config.sh` (not tracked in git):

```bash
#!/bin/bash
export API_KEY="your-api-key-here"
export GROUP_NAME="your-group-name"
export API_URL="https://your-api-id.execute-api.eu-west-1.amazonaws.com"
export WS_URL="wss://your-api-id.execute-api.eu-west-1.amazonaws.com/production"
```

Then source it:

```bash
source config.sh
```

## Running Tests

### Quick Start (Zero Configuration)

Simply run any test script - all configuration is automatic:

```bash
cd tests/api

# Run individual tests
./test_people_count_latest.sh
./test_mcp_health.sh
./test_mcp_auth.sh

# Run all tests
./run_all_tests.sh
```

The scripts will automatically:
- Retrieve API key from Secrets Manager
- Get API endpoints from Terraform outputs
- Use appropriate AWS region
- Use default group name for testing

### Run Specific Test Categories

```bash
# People Count API tests
./test_people_count_latest.sh
./test_people_count_historical.sh
./test_people_count_invalid.sh

# Sensors API tests
./test_sensors_latest.sh
./test_sensors_historical.sh
./test_sensors_invalid.sh

# Bus Position API tests
./test_bus_position_latest.sh
./test_bus_position_historical.sh
./test_bus_position_websocket.sh

# Authentication tests
./test_auth_invalid_key.sh
./test_auth_missing_key.sh
./test_auth_missing_group.sh

# MCP Server tests
./test_mcp_health.sh
./test_mcp_query_people_count.sh
./test_mcp_query_sensor_data.sh
./test_mcp_query_bus_position.sh
./test_mcp_auth.sh
```

## Test Scripts

### People Count API

- **test_people_count_latest.sh** - Query latest people count at a stop
- **test_people_count_historical.sh** - Query historical people count with timestamp
- **test_people_count_invalid.sh** - Test error handling for non-existent stop

### Sensors API

- **test_sensors_latest.sh** - Query latest sensor data for bus and stop
- **test_sensors_historical.sh** - Query historical sensor data with timestamp
- **test_sensors_invalid.sh** - Test error handling for non-existent entity

### Bus Position API

- **test_bus_position_latest.sh** - Query latest bus position
- **test_bus_position_historical.sh** - Query historical bus position with timestamp
- **test_bus_position_websocket.sh** - Test WebSocket subscription and real-time updates

### Authentication Tests

- **test_auth_invalid_key.sh** - Verify rejection of invalid API key
- **test_auth_missing_key.sh** - Verify rejection when API key is missing
- **test_auth_missing_group.sh** - Verify rejection when group name is missing

### MCP Server Tests

- **test_mcp_health.sh** - Test MCP server health endpoint (no auth required)
- **test_mcp_query_people_count.sh** - Test query_people_count MCP tool
- **test_mcp_query_sensor_data.sh** - Test query_sensor_data MCP tool
- **test_mcp_query_bus_position.sh** - Test query_bus_position MCP tool
- **test_mcp_query_line_buses.sh** - Test query_line_buses MCP tool
- **test_mcp_query_time_range.sh** - Test query_time_range MCP tool for historical data
- **test_mcp_auth.sh** - Test MCP server authentication requirements

## Helper Utilities

The `common.sh` file provides shared functions used by all test scripts:

### Automatic Configuration Functions
- `get_aws_region()` - Auto-detect AWS region from CLI config or Terraform
- `get_api_key()` - Auto-retrieve API key from Secrets Manager
- `get_api_url()` - Auto-retrieve REST API URL from Terraform outputs
- `get_ws_url()` - Auto-retrieve WebSocket URL from Terraform outputs
- `get_mcp_url()` - Auto-retrieve MCP API URL from Terraform outputs
- `get_group_name()` - Use default "test-group" or environment variable

### Request Functions
- `make_request()` - Make authenticated HTTP request
- `make_mcp_request()` - Make authenticated MCP request
- `make_request_no_auth()` - Make unauthenticated request (for auth tests)

### Utility Functions
- `check_dependencies()` - Verify required tools are installed
- `format_json()` - Pretty-print JSON responses
- `validate_json()` - Validate JSON response
- `log_test()` - Log test execution and results
- `log_success()`, `log_error()`, `log_warning()` - Colored output

## Expected Responses

### Successful Query

```json
{
  "stop_id": "S001",
  "time": "2026-02-22T10:30:00Z",
  "count": 15,
  "line_ids": "L1,L2"
}
```

### Error Response

```json
{
  "error": "NotFound",
  "message": "Stop S999 not found"
}
```

### Authentication Error

```json
{
  "error": "Unauthorized",
  "message": "Invalid API key"
}
```

## Troubleshooting

### "Could not retrieve from Secrets Manager"

**Cause**: AWS CLI not configured or no permissions

**Solution**:
```bash
# Configure AWS CLI
aws configure

# Verify access to Secrets Manager
aws secretsmanager get-secret-value --secret-id bus-simulator/api-key

# Or set API key manually
export API_KEY="your-api-key"
```

### "Could not retrieve from Terraform"

**Cause**: Infrastructure not deployed or terraform.tfstate not found

**Solution**:
```bash
# Deploy infrastructure
cd ../../terraform
terraform apply

# Verify outputs exist
terraform output

# Or set URLs manually
export API_URL="https://your-api-id.execute-api.eu-west-1.amazonaws.com"
export MCP_URL="https://your-mcp-api-id.execute-api.eu-west-1.amazonaws.com/prod"
```

### "AWS CLI not configured"

**Solution**:
```bash
aws configure
# Enter your AWS Access Key ID, Secret Access Key, and region
```

### "jq: command not found"

Install jq or the scripts will output raw JSON:

```bash
brew install jq  # macOS
sudo apt-get install jq  # Ubuntu
```

### "wscat: command not found"

Install wscat for WebSocket testing:

```bash
npm install -g wscat
```

### "401 Unauthorized"

- Verify your API key is correct
- Ensure you're setting the x-group-name header
- Check that the API key hasn't been rotated

### "404 Not Found"

- Verify the entity ID (stop, bus, line) exists in the system
- Check the data/lines.yaml file for valid IDs

### Connection Timeout

- Verify the API URL is correct
- Check that the API Gateway is deployed and accessible
- Ensure your network allows HTTPS/WSS connections

## Example Output

```bash
$ ./test_people_count_latest.sh

=== Testing People Count API (Latest) ===

Testing stop S001...
{
  "stop_id": "S001",
  "time": "2026-02-22T10:30:00Z",
  "count": 15,
  "line_ids": "L1,L2"
}
✓ Success

Testing stop S002...
{
  "stop_id": "S002",
  "time": "2026-02-22T10:30:15Z",
  "count": 8,
  "line_ids": "L1"
}
✓ Success

All tests passed!
```

## Contributing

When adding new test scripts:

1. Follow the naming convention: `test_<api>_<scenario>.sh`
2. Use the common.sh helper functions
3. Include clear output messages
4. Test both success and error cases
5. Update this README with the new script

## Support

For issues or questions:
- Check the main [API Documentation](../../docs/API_GUIDE.md)
- Review the [OpenAPI Specification](../../docs/openapi.yaml)
- Review the [MCP Server Documentation](../../mcp_server/README.md)
- Open an issue on the GitHub repository
