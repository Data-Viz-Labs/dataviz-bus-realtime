# MCP Server Testing Guide

This guide explains how to test the Madrid Bus Simulator MCP Server container locally using Podman.

## Prerequisites

- **Podman** installed and configured
- **AWS CLI** installed (for authentication tests)
- **LocalStack** (optional, for local AWS simulation)
- Python 3.11+ (for running test scripts)

## Test Scripts

### 1. Basic Container Tests (`scripts/test_mcp_server.sh`)

This script performs comprehensive tests of the MCP server container:

- Builds the container image with Podman
- Tests Python module imports
- Validates authentication module functionality
- Tests server initialization
- Optionally tests with LocalStack

**Usage:**

```bash
./scripts/test_mcp_server.sh
```

**What it tests:**

1. **Container Build**: Verifies the Dockerfile builds successfully
2. **Module Imports**: Ensures all Python modules load correctly
3. **Authentication Module**: Tests the authentication middleware
4. **Authentication Logic**: Validates header extraction and validation
5. **Server Initialization**: Confirms the MCP server initializes properly
6. **LocalStack Integration** (optional): Tests with LocalStack if available

**Expected Output:**

```
==========================================
MCP Server Container Test Suite
==========================================

Step 1: Building MCP server container image...
✓ Container image built successfully

Step 2: Testing basic container startup...
✓ MCP Server imports successfully

Step 3: Testing authentication module...
✓ Authentication module imports successfully

Step 4: Testing with LocalStack (optional)...
⚠ LocalStack not found, skipping LocalStack tests

Step 5: Testing authentication logic...
✓ Authentication logic tests passed

Step 6: Testing MCP server initialization...
✓ MCP server initialization test passed

==========================================
✓ All MCP Server container tests passed!
==========================================
```

### 2. Authentication Tests (`scripts/test_mcp_auth.sh`)

This script tests authentication with AWS Secrets Manager using valid and invalid API keys.

**Usage with LocalStack:**

```bash
# Start LocalStack first
localstack start -d

# Run tests with LocalStack
./scripts/test_mcp_auth.sh --localstack
```

**Usage with Real AWS Account:**

```bash
# Ensure AWS credentials are configured
aws configure

# Run tests with real AWS
./scripts/test_mcp_auth.sh
```

**What it tests:**

1. **Valid API Key**: Verifies authentication succeeds with correct API key
2. **Invalid API Key**: Confirms authentication fails with wrong API key
3. **Missing API Key**: Ensures missing `x-api-key` header is rejected
4. **Missing Group Name**: Validates missing `x-group-name` header is rejected

**Expected Output:**

```
==========================================
MCP Server Authentication Test Suite
==========================================

Step 1: Setting up AWS Secrets Manager...
✓ Secret created/updated successfully

Step 2: Testing authentication with valid API key...
✓ Valid API key test passed

Step 3: Testing authentication with invalid API key...
✓ Invalid API key test passed

Step 4: Testing missing API key...
✓ Missing API key test passed

Step 5: Testing missing group name...
✓ Missing group name test passed

==========================================
✓ All authentication tests passed!
==========================================
```

## Manual Testing

### Build the Container Image

```bash
cd mcp_server
podman build -t bus-simulator-mcp-server:latest .
```

### Run the Container

**With test credentials:**

```bash
podman run -it --rm \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  -e TIMESTREAM_DATABASE=bus_simulator \
  -e SECRET_ID=bus-simulator/api-key \
  bus-simulator-mcp-server:latest
```

**With real AWS credentials:**

```bash
podman run -it --rm \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_REGION=eu-west-1 \
  -e TIMESTREAM_DATABASE=bus_simulator \
  -e SECRET_ID=bus-simulator/api-key \
  bus-simulator-mcp-server:latest
```

**With LocalStack:**

```bash
podman run -it --rm \
  --network host \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  -e TIMESTREAM_DATABASE=bus_simulator \
  -e SECRET_ID=bus-simulator/api-key \
  -e AWS_ENDPOINT_URL=http://localhost:4566 \
  bus-simulator-mcp-server:latest
```

### Test Authentication Module

```bash
podman run --rm \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  bus-simulator-mcp-server:latest \
  python -c "from mcp_server.auth import AuthenticationMiddleware; print('✓ Auth module works')"
```

### Test Server Initialization

```bash
podman run --rm \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  bus-simulator-mcp-server:latest \
  python -c "from mcp_server.server import BusSimulatorMCPServer; s = BusSimulatorMCPServer('bus_simulator', 'eu-west-1'); print('✓ Server initialized')"
```

## Testing with LocalStack

LocalStack provides a local AWS cloud stack for testing without incurring AWS charges.

### Install LocalStack

```bash
pip install localstack
```

### Start LocalStack

```bash
localstack start -d
```

### Create Test Secret

```bash
aws --endpoint-url=http://localhost:4566 \
    secretsmanager create-secret \
    --name bus-simulator/api-key \
    --secret-string '{"api_key":"test-api-key-12345"}' \
    --region eu-west-1
```

### Run Container with LocalStack

```bash
podman run -d \
  --name mcp-server-test \
  --network host \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  -e TIMESTREAM_DATABASE=bus_simulator \
  -e SECRET_ID=bus-simulator/api-key \
  -e AWS_ENDPOINT_URL=http://localhost:4566 \
  bus-simulator-mcp-server:latest
```

### Check Container Logs

```bash
podman logs mcp-server-test
```

### Stop and Remove Container

```bash
podman stop mcp-server-test
podman rm mcp-server-test
```

## Troubleshooting

### Container Fails to Start

**Check logs:**

```bash
podman logs <container-id>
```

**Common issues:**

- Missing environment variables
- AWS credentials not configured
- Secrets Manager secret not found

### Authentication Fails

**Verify secret exists:**

```bash
aws secretsmanager get-secret-value \
    --secret-id bus-simulator/api-key \
    --region eu-west-1
```

**Check secret format:**

The secret must be a JSON string with an `api_key` field:

```json
{
  "api_key": "your-api-key-here"
}
```

### Import Errors

**Verify Python path:**

```bash
podman run --rm bus-simulator-mcp-server:latest \
  python -c "import sys; print(sys.path)"
```

**Check module structure:**

```bash
podman run --rm bus-simulator-mcp-server:latest \
  ls -la /app/mcp_server/
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `TIMESTREAM_DATABASE` | Timestream database name | `bus_simulator` | Yes |
| `AWS_REGION` | AWS region | `eu-west-1` | Yes |
| `SECRET_ID` | Secrets Manager secret ID | `bus-simulator/api-key` | Yes |
| `AWS_ACCESS_KEY_ID` | AWS access key | - | Yes (or use IAM role) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | - | Yes (or use IAM role) |
| `AWS_ENDPOINT_URL` | AWS endpoint (for LocalStack) | - | No |

## Next Steps

After successful local testing:

1. **Push to ECR**: Push the container image to AWS ECR
2. **Deploy to ECS**: Use Terraform to deploy the MCP server to ECS
3. **Test with Real Data**: Connect to the deployed Timestream database
4. **MCP Client Testing**: Test with MCP clients (AI assistants, IDEs)

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Podman Documentation](https://docs.podman.io/)
- [LocalStack Documentation](https://docs.localstack.cloud/)
