#!/bin/bash

# Test Automatic Configuration
# This script demonstrates the automatic configuration capabilities

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Print header
print_header "Testing Automatic Configuration"

echo "This script demonstrates automatic configuration retrieval."
echo "No environment variables need to be set manually!"
echo ""

# Test AWS Region detection
log_test "Detecting AWS Region"
region=$(get_aws_region)
log_success "AWS Region: $region"
echo ""

# Test API Key retrieval
log_test "Retrieving API Key from Secrets Manager"
api_key=$(get_api_key)
if [ -n "$api_key" ]; then
    # Mask the API key for security
    masked_key="${api_key:0:8}...${api_key: -4}"
    log_success "API Key retrieved: $masked_key"
else
    log_error "Failed to retrieve API key"
fi
echo ""

# Test REST API URL retrieval
log_test "Retrieving REST API URL from Terraform"
api_url=$(get_api_url)
log_success "REST API URL: $api_url"
echo ""

# Test WebSocket URL retrieval
log_test "Retrieving WebSocket URL from Terraform"
ws_url=$(get_ws_url)
log_success "WebSocket URL: $ws_url"
echo ""

# Test MCP API URL retrieval
log_test "Retrieving MCP API URL from Terraform"
mcp_url=$(get_mcp_url)
log_success "MCP API URL: $mcp_url"
echo ""

# Test Group Name
log_test "Getting Group Name"
group_name=$(get_group_name)
log_success "Group Name: $group_name"
echo ""

# Summary
echo "========================================"
log_success "All configuration retrieved successfully!"
echo ""
echo "You can now run any test script without manual configuration:"
echo "  ./test_people_count_latest.sh"
echo "  ./test_mcp_health.sh"
echo "  ./test_mcp_auth.sh"
echo ""
echo "To override any value, set environment variables:"
echo "  export API_KEY=\"your-key\""
echo "  export GROUP_NAME=\"your-group\""
echo "  export AWS_REGION=\"eu-west-1\""
