#!/bin/bash

# Test MCP Server - query_line_buses Tool
# This script tests the MCP server query_line_buses tool

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing MCP Server (query_line_buses Tool)"

# Test 1: Query all buses on a line
log_test "Query all buses on line L001"

response=$(make_mcp_request "POST" "/tools/query_line_buses" '{
    "line_id": "L001",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == true' &> /dev/null; then
    log_success "Successfully queried buses on line"
    
    # Count buses
    bus_count=$(echo "$response" | jq -r '.data | length // 0')
    log_info "Found $bus_count buses on line L001"
else
    log_error "Failed to query line buses"
    exit 1
fi

echo ""

# Test 2: Query with invalid line ID
log_test "Query with invalid line ID (should return error or empty)"

response=$(make_mcp_request "POST" "/tools/query_line_buses" '{
    "line_id": "L999",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == false or (.data | length == 0)' &> /dev/null; then
    log_success "Correctly handled invalid line ID"
else
    log_warning "Unexpected response for invalid line ID"
fi

echo ""
echo "========================================"
log_success "All query_line_buses tests completed!"
