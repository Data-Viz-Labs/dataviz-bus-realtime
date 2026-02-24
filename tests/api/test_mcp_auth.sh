#!/bin/bash

# Test MCP Server - Authentication
# This script tests MCP server authentication requirements

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing MCP Server (Authentication)"

all_passed=true

# Test 1: Request without API key
log_test "Request without API key (should return 401)"

response=$(make_mcp_request_no_auth "POST" "/tools/query_people_count" '{
    "stop_id": "S001",
    "mode": "latest"
}')

# Check if we got 401 or error response
if echo "$response" | grep -q "Unauthorized\|401\|Missing.*api.*key" || \
   echo "$response" | jq -e '.message' 2>/dev/null | grep -qi "unauthorized\|missing.*key"; then
    log_success "Correctly rejected request without API key"
else
    echo "$response" | format_json
    log_error "Expected 401 Unauthorized"
    all_passed=false
fi

echo ""

# Test 2: Request with invalid API key
log_test "Request with invalid API key (should return 401)"

response=$(make_mcp_request_invalid_key "POST" "/tools/query_people_count" '{
    "stop_id": "S001",
    "mode": "latest"
}')

if echo "$response" | grep -q "Unauthorized\|401\|Invalid.*api.*key" || \
   echo "$response" | jq -e '.message' 2>/dev/null | grep -qi "unauthorized\|invalid.*key"; then
    log_success "Correctly rejected request with invalid API key"
else
    echo "$response" | format_json
    log_error "Expected 401 Unauthorized"
    all_passed=false
fi

echo ""

# Test 3: Request without group name header
log_test "Request without x-group-name header (should return 401)"

response=$(make_mcp_request_no_group "POST" "/tools/query_people_count" '{
    "stop_id": "S001",
    "mode": "latest"
}')

if echo "$response" | grep -q "Unauthorized\|401\|Missing.*group" || \
   echo "$response" | jq -e '.message' 2>/dev/null | grep -qi "unauthorized\|missing.*group"; then
    log_success "Correctly rejected request without group name"
else
    echo "$response" | format_json
    log_error "Expected 401 Unauthorized"
    all_passed=false
fi

echo ""

# Test 4: Valid authenticated request
log_test "Valid authenticated request (should succeed)"

response=$(make_mcp_request "POST" "/tools/query_people_count" '{
    "stop_id": "S001",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    all_passed=false
else
    if echo "$response" | jq -e '.success' &> /dev/null; then
        log_success "Successfully authenticated and processed request"
    else
        echo "$response" | format_json
        log_error "Expected successful response"
        all_passed=false
    fi
fi

echo ""

# Summary
echo "========================================"
if [ "$all_passed" = true ]; then
    log_success "All authentication tests passed!"
    exit 0
else
    log_error "Some authentication tests failed"
    exit 1
fi
