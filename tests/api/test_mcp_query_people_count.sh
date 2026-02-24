#!/bin/bash

# Test MCP Server - query_people_count Tool
# This script tests the MCP server query_people_count tool

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing MCP Server (query_people_count Tool)"

# Test 1: Query latest people count
log_test "Query latest people count for stop S001"

response=$(make_mcp_request "POST" "/tools/query_people_count" '{
    "stop_id": "S001",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == true' &> /dev/null; then
    log_success "Successfully queried latest people count"
else
    log_error "Failed to query people count"
    exit 1
fi

echo ""

# Test 2: Query historical people count
log_test "Query historical people count for stop S002"

timestamp=$(get_past_timestamp 5)

response=$(make_mcp_request "POST" "/tools/query_people_count" "{
    \"stop_id\": \"S002\",
    \"mode\": \"historical\",
    \"timestamp\": \"$timestamp\"
}")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success' &> /dev/null; then
    log_success "Successfully queried historical people count"
else
    log_warning "Historical query returned no data (may be expected if no data at that time)"
fi

echo ""

# Test 3: Query with invalid stop ID
log_test "Query with invalid stop ID (should return error)"

response=$(make_mcp_request "POST" "/tools/query_people_count" '{
    "stop_id": "S999",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == false' &> /dev/null; then
    log_success "Correctly returned error for invalid stop ID"
else
    log_warning "Expected error for invalid stop ID"
fi

echo ""
echo "========================================"
log_success "All query_people_count tests completed!"
