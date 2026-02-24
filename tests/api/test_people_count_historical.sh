#!/bin/bash

# Test People Count API - Historical Data Query
# This script tests querying historical people count with timestamps

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing People Count API (Historical)"

# Test cases with different timestamps
test_cases=(
    "S001:5"   # Stop S001, 5 minutes ago
    "S002:10"  # Stop S002, 10 minutes ago
    "S003:15"  # Stop S003, 15 minutes ago
)
all_passed=true

for test_case in "${test_cases[@]}"; do
    IFS=':' read -r stop_id minutes_ago <<< "$test_case"
    
    # Get timestamp from N minutes ago
    timestamp=$(get_past_timestamp "$minutes_ago")
    
    log_test "Get people count for stop $stop_id at $timestamp"
    
    # Make request
    response=$(make_request "GET" "/people-count/${stop_id}?timestamp=${timestamp}")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for stop $stop_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields
    if echo "$response" | jq -e '.stop_id and .time and .count and .line_ids' &> /dev/null; then
        echo "$response" | format_json
        log_success "Successfully retrieved historical data for stop $stop_id"
    else
        echo "$response" | format_json
        log_error "Response missing required fields for stop $stop_id"
        all_passed=false
    fi
    
    echo ""
done

# Summary
echo "========================================"
if [ "$all_passed" = true ]; then
    log_success "All tests passed!"
    exit 0
else
    log_error "Some tests failed"
    exit 1
fi
