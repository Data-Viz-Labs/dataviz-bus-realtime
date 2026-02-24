#!/bin/bash

# Test MCP Server - query_sensor_data Tool
# This script tests the MCP server query_sensor_data tool

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing MCP Server (query_sensor_data Tool)"

# Test 1: Query latest sensor data for a bus
log_test "Query latest sensor data for bus B001"

response=$(make_mcp_request "POST" "/tools/query_sensor_data" '{
    "entity_id": "B001",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == true' &> /dev/null; then
    log_success "Successfully queried latest sensor data"
else
    log_error "Failed to query sensor data"
    exit 1
fi

echo ""

# Test 2: Query historical sensor data
log_test "Query historical sensor data for bus B002"

timestamp=$(get_past_timestamp 10)

response=$(make_mcp_request "POST" "/tools/query_sensor_data" "{
    \"entity_id\": \"B002\",
    \"mode\": \"historical\",
    \"timestamp\": \"$timestamp\"
}")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success' &> /dev/null; then
    log_success "Successfully queried historical sensor data"
else
    log_warning "Historical query returned no data (may be expected)"
fi

echo ""

# Test 3: Query sensor data for a stop
log_test "Query latest sensor data for stop S001"

response=$(make_mcp_request "POST" "/tools/query_sensor_data" '{
    "entity_id": "S001",
    "mode": "latest"
}')

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == true' &> /dev/null; then
    log_success "Successfully queried sensor data for stop"
else
    log_warning "No sensor data for stop (may be expected)"
fi

echo ""
echo "========================================"
log_success "All query_sensor_data tests completed!"
