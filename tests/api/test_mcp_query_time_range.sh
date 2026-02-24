#!/bin/bash

# Test MCP Server - query_time_range Tool
# This script tests the MCP server query_time_range tool

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing MCP Server (query_time_range Tool)"

# Test 1: Query time range for bus position
log_test "Query bus position time range (last 30 minutes)"

start_time=$(get_past_timestamp 30)
end_time=$(get_timestamp)

response=$(make_mcp_request "POST" "/tools/query_time_range" "{
    \"entity_id\": \"B001\",
    \"entity_type\": \"bus_position\",
    \"start_time\": \"$start_time\",
    \"end_time\": \"$end_time\"
}")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == true' &> /dev/null; then
    log_success "Successfully queried time range data"
    
    # Count data points
    data_count=$(echo "$response" | jq -r '.data | length // 0')
    log_info "Found $data_count data points in time range"
else
    log_error "Failed to query time range"
    exit 1
fi

echo ""

# Test 2: Query time range for people count
log_test "Query people count time range (last 60 minutes)"

start_time=$(get_past_timestamp 60)
end_time=$(get_timestamp)

response=$(make_mcp_request "POST" "/tools/query_time_range" "{
    \"entity_id\": \"S001\",
    \"entity_type\": \"people_count\",
    \"start_time\": \"$start_time\",
    \"end_time\": \"$end_time\"
}")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success' &> /dev/null; then
    data_count=$(echo "$response" | jq -r '.data | length // 0')
    log_success "Successfully queried people count time range ($data_count points)"
else
    log_warning "Time range query returned no data (may be expected)"
fi

echo ""

# Test 3: Query with invalid time range (end before start)
log_test "Query with invalid time range (should return error)"

start_time=$(get_timestamp)
end_time=$(get_past_timestamp 10)

response=$(make_mcp_request "POST" "/tools/query_time_range" "{
    \"entity_id\": \"B001\",
    \"entity_type\": \"bus_position\",
    \"start_time\": \"$start_time\",
    \"end_time\": \"$end_time\"
}")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    exit 1
fi

echo "$response" | format_json

if echo "$response" | jq -e '.success == false' &> /dev/null; then
    log_success "Correctly returned error for invalid time range"
else
    log_warning "Expected error for invalid time range"
fi

echo ""
echo "========================================"
log_success "All query_time_range tests completed!"
