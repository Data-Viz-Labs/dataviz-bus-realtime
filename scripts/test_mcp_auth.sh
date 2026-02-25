#!/bin/bash
# Script to test MCP Server authentication with AWS Secrets Manager
# This script tests authentication with valid and invalid API keys
# Can be used with LocalStack or real AWS account

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="bus-simulator-mcp-server"
IMAGE_TAG="latest"
CONTAINER_NAME="mcp-server-auth-test"
SECRET_NAME="bus-simulator/api-key"
VALID_API_KEY="test-api-key-12345"
INVALID_API_KEY="invalid-key-67890"

# Check if using LocalStack or real AWS
USE_LOCALSTACK=false
AWS_ENDPOINT=""
AWS_ENDPOINT_URL=""

if [ "$1" == "--localstack" ]; then
    USE_LOCALSTACK=true
    AWS_ENDPOINT="--endpoint-url=http://localhost:4566"
    AWS_ENDPOINT_URL="http://localhost:4566"
    echo -e "${BLUE}Using LocalStack for testing${NC}"
else
    echo -e "${BLUE}Using real AWS account for testing${NC}"
    echo -e "${YELLOW}Note: This will use your AWS credentials and may incur charges${NC}"
fi

echo "=========================================="
echo "MCP Server Authentication Test Suite"
echo "=========================================="
echo ""

# Step 1: Setup AWS Secrets Manager
echo -e "${YELLOW}Step 1: Setting up AWS Secrets Manager...${NC}"

if [ "$USE_LOCALSTACK" = true ]; then
    # Check if LocalStack is running
    if ! curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
        echo -e "${RED}✗ LocalStack is not running${NC}"
        echo "Start LocalStack with: localstack start -d"
        exit 1
    fi
    echo "✓ LocalStack is running"
fi

# Create or update the secret
echo "Creating/updating secret: ${SECRET_NAME}"
aws ${AWS_ENDPOINT} secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --secret-string "{\"api_key\":\"${VALID_API_KEY}\"}" \
    --region eu-west-1 2>/dev/null || \
aws ${AWS_ENDPOINT} secretsmanager update-secret \
    --secret-id "${SECRET_NAME}" \
    --secret-string "{\"api_key\":\"${VALID_API_KEY}\"}" \
    --region eu-west-1

echo -e "${GREEN}✓ Secret created/updated successfully${NC}"
echo ""

# Step 2: Test authentication with valid API key
echo -e "${YELLOW}Step 2: Testing authentication with valid API key...${NC}"

cat > /tmp/test_valid_auth.py << EOF
import os
from mcp_server.auth import AuthenticationMiddleware, AuthenticationError

# Initialize middleware
middleware = AuthenticationMiddleware(
    secret_id='${SECRET_NAME}',
    region='eu-west-1'
)

# Test with valid API key
headers = {
    'x-api-key': '${VALID_API_KEY}',
    'x-group-name': 'test-group'
}

try:
    middleware.authenticate_request(headers)
    print("✓ Valid API key authenticated successfully")
except AuthenticationError as e:
    print(f"✗ Valid API key failed: {e}")
    exit(1)
EOF

if [ "$USE_LOCALSTACK" = true ]; then
    podman run --rm \
      --network host \
      -v /tmp/test_valid_auth.py:/tmp/test_valid_auth.py:ro \
      -e AWS_ACCESS_KEY_ID=test \
      -e AWS_SECRET_ACCESS_KEY=test \
      -e AWS_REGION=eu-west-1 \
      -e AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL}" \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_valid_auth.py || {
        echo -e "${RED}✗ Valid API key test failed${NC}"
        rm /tmp/test_valid_auth.py
        exit 1
    }
else
    # Use host AWS credentials
    podman run --rm \
      -v /tmp/test_valid_auth.py:/tmp/test_valid_auth.py:ro \
      -v ~/.aws:/root/.aws:ro \
      -e AWS_REGION=eu-west-1 \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_valid_auth.py || {
        echo -e "${RED}✗ Valid API key test failed${NC}"
        rm /tmp/test_valid_auth.py
        exit 1
    }
fi

rm /tmp/test_valid_auth.py
echo -e "${GREEN}✓ Valid API key test passed${NC}"
echo ""

# Step 3: Test authentication with invalid API key
echo -e "${YELLOW}Step 3: Testing authentication with invalid API key...${NC}"

cat > /tmp/test_invalid_auth.py << EOF
from mcp_server.auth import AuthenticationMiddleware, AuthenticationError

# Initialize middleware
middleware = AuthenticationMiddleware(
    secret_id='${SECRET_NAME}',
    region='eu-west-1'
)

# Test with invalid API key
headers = {
    'x-api-key': '${INVALID_API_KEY}',
    'x-group-name': 'test-group'
}

try:
    middleware.authenticate_request(headers)
    print("✗ Invalid API key should have been rejected")
    exit(1)
except AuthenticationError as e:
    if 'Invalid API key' in str(e) or 'key' in str(e).lower():
        print("✓ Invalid API key rejected correctly")
    else:
        print(f"✗ Unexpected error: {e}")
        exit(1)
EOF

if [ "$USE_LOCALSTACK" = true ]; then
    podman run --rm \
      --network host \
      -v /tmp/test_invalid_auth.py:/tmp/test_invalid_auth.py:ro \
      -e AWS_ACCESS_KEY_ID=test \
      -e AWS_SECRET_ACCESS_KEY=test \
      -e AWS_REGION=eu-west-1 \
      -e AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL}" \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_invalid_auth.py || {
        echo -e "${RED}✗ Invalid API key test failed${NC}"
        rm /tmp/test_invalid_auth.py
        exit 1
    }
else
    podman run --rm \
      -v /tmp/test_invalid_auth.py:/tmp/test_invalid_auth.py:ro \
      -v ~/.aws:/root/.aws:ro \
      -e AWS_REGION=eu-west-1 \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_invalid_auth.py || {
        echo -e "${RED}✗ Invalid API key test failed${NC}"
        rm /tmp/test_invalid_auth.py
        exit 1
    }
fi

rm /tmp/test_invalid_auth.py
echo -e "${GREEN}✓ Invalid API key test passed${NC}"
echo ""

# Step 4: Test missing API key
echo -e "${YELLOW}Step 4: Testing missing API key...${NC}"

cat > /tmp/test_missing_key.py << EOF
from mcp_server.auth import AuthenticationMiddleware, AuthenticationError

# Initialize middleware
middleware = AuthenticationMiddleware(
    secret_id='${SECRET_NAME}',
    region='eu-west-1'
)

# Test with missing API key
headers = {
    'x-group-name': 'test-group'
}

try:
    middleware.authenticate_request(headers)
    print("✗ Missing API key should have been rejected")
    exit(1)
except AuthenticationError as e:
    if 'x-api-key' in str(e).lower():
        print("✓ Missing API key rejected correctly")
    else:
        print(f"✗ Unexpected error: {e}")
        exit(1)
EOF

if [ "$USE_LOCALSTACK" = true ]; then
    podman run --rm \
      --network host \
      -v /tmp/test_missing_key.py:/tmp/test_missing_key.py:ro \
      -e AWS_ACCESS_KEY_ID=test \
      -e AWS_SECRET_ACCESS_KEY=test \
      -e AWS_REGION=eu-west-1 \
      -e AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL}" \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_missing_key.py || {
        echo -e "${RED}✗ Missing API key test failed${NC}"
        rm /tmp/test_missing_key.py
        exit 1
    }
else
    podman run --rm \
      -v /tmp/test_missing_key.py:/tmp/test_missing_key.py:ro \
      -v ~/.aws:/root/.aws:ro \
      -e AWS_REGION=eu-west-1 \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_missing_key.py || {
        echo -e "${RED}✗ Missing API key test failed${NC}"
        rm /tmp/test_missing_key.py
        exit 1
    }
fi

rm /tmp/test_missing_key.py
echo -e "${GREEN}✓ Missing API key test passed${NC}"
echo ""

# Step 5: Test missing group name
echo -e "${YELLOW}Step 5: Testing missing group name...${NC}"

cat > /tmp/test_missing_group.py << EOF
from mcp_server.auth import AuthenticationMiddleware, AuthenticationError

# Initialize middleware
middleware = AuthenticationMiddleware(
    secret_id='${SECRET_NAME}',
    region='eu-west-1'
)

# Test with missing group name
headers = {
    'x-api-key': '${VALID_API_KEY}'
}

try:
    middleware.authenticate_request(headers)
    print("✗ Missing group name should have been rejected")
    exit(1)
except AuthenticationError as e:
    if 'x-group-name' in str(e).lower():
        print("✓ Missing group name rejected correctly")
    else:
        print(f"✗ Unexpected error: {e}")
        exit(1)
EOF

if [ "$USE_LOCALSTACK" = true ]; then
    podman run --rm \
      --network host \
      -v /tmp/test_missing_group.py:/tmp/test_missing_group.py:ro \
      -e AWS_ACCESS_KEY_ID=test \
      -e AWS_SECRET_ACCESS_KEY=test \
      -e AWS_REGION=eu-west-1 \
      -e AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL}" \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_missing_group.py || {
        echo -e "${RED}✗ Missing group name test failed${NC}"
        rm /tmp/test_missing_group.py
        exit 1
    }
else
    podman run --rm \
      -v /tmp/test_missing_group.py:/tmp/test_missing_group.py:ro \
      -v ~/.aws:/root/.aws:ro \
      -e AWS_REGION=eu-west-1 \
      ${IMAGE_NAME}:${IMAGE_TAG} \
      python /tmp/test_missing_group.py || {
        echo -e "${RED}✗ Missing group name test failed${NC}"
        rm /tmp/test_missing_group.py
        exit 1
    }
fi

rm /tmp/test_missing_group.py
echo -e "${GREEN}✓ Missing group name test passed${NC}"
echo ""

# Cleanup
if [ "$USE_LOCALSTACK" = true ]; then
    echo -e "${YELLOW}Cleaning up LocalStack resources...${NC}"
    aws ${AWS_ENDPOINT} secretsmanager delete-secret \
        --secret-id "${SECRET_NAME}" \
        --force-delete-without-recovery \
        --region eu-west-1 2>/dev/null || true
    echo "✓ Cleanup complete"
else
    echo -e "${YELLOW}Note: Secret '${SECRET_NAME}' was created in your AWS account${NC}"
    echo "To delete it, run:"
    echo "  aws secretsmanager delete-secret --secret-id ${SECRET_NAME} --force-delete-without-recovery --region eu-west-1"
fi
echo ""

# Summary
echo "=========================================="
echo -e "${GREEN}✓ All authentication tests passed!${NC}"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ Valid API key authenticated successfully"
echo "  ✓ Invalid API key rejected correctly"
echo "  ✓ Missing API key rejected correctly"
echo "  ✓ Missing group name rejected correctly"
echo ""
echo "The MCP server authentication is working as expected!"
echo ""
