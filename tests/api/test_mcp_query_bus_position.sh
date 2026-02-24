#!/bin/bash

# Test MCP Server - query_bus_position Tool
# This script tests the MCP server query_bus_position tool

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing MCP Server (query_bus_position Tool)"

# Test 1: Query latest bus position
log_test "Query latest position for bus B001"

response=$(make_mcp_request "POST" "/tools/query_bus_position" '{
    "bus_id": "B001",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == true' &> /dev/null; then
    log_success "Successfully queried latest bus position"
    
    # Extract and display key fields
    latitude=$(echo "$response" | jq -r '.data.latitude // "N/A"')
    longitude=$(echo "$response" | jq -r '.data.longitude // "N/A"')
    speed=$(echo "$response" | jq -r '.data.speed // "N/A"')
    
    log_info "Position: ($latitude, $longitude), Speed: $speed km/h"
else
    log_error "Failed to query bus position"
    exit 1
fi

echo ""

# Test 2: Query historical bus position
log_test "Query historical position for bus B002"

timestamp=$(get_past_timestamp 15)

response=$(make_mcp_request "POST" "/tools/query_bus_position" "{
    \"bus_id\": \"B002\",
    \"mode\": \"historical\",
    \"timestamp\": \"$timestamp\"
}")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success' &> /dev/null; then
    log_success "Successfully queried historical bus position"
else
    log_warning "Historical query returned no data (may be expected)"
fi

echo ""

# Test 3: Query with invalid bus ID
log_test "Query with invalid bus ID (should return error)"

response=$(make_mcp_request "POST" "/tools/query_bus_position" '{
    "bus_id": "B999",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == false' &> /dev/null; then
    log_success "Correctly returned error for invalid bus ID"
else
    log_warning "Expected error for invalid bus ID"
fi

echo ""
echo "========================================"
log_success "All query_bus_position tests completed!"
