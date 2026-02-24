#!/bin/bash

# Test MCP Server - Health Check
# This script tests the MCP server health endpoint

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing MCP Server (Health Check)"

# Test health endpoint (no authentication required)
log_test "Health check endpoint (public)"

response=$(make_mcp_request_no_auth "GET" "/health")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.status == "healthy"' &> /dev/null; then
    log_success "MCP server is healthy"
else
    log_warning "MCP server health status unclear"
fi

echo ""
echo "========================================"
log_success "Health check test completed!"
