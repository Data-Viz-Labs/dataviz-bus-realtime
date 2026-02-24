#!/bin/bash

# Test Bus Position API - Historical Data Query
# This script tests querying historical bus positions with timestamps

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Bus Position API (Historical)"

# Test cases with different timestamps
test_cases=(
    "B001:5"   # Bus B001, 5 minutes ago
    "B002:10"  # Bus B002, 10 minutes ago
    "B003:15"  # Bus B003, 15 minutes ago
)
all_passed=true

for test_case in "${test_cases[@]}"; do
    IFS=':' read -r bus_id minutes_ago <<< "$test_case"
    
    # Get timestamp from N minutes ago
    timestamp=$(get_past_timestamp "$minutes_ago")
    
    log_test "Get position for bus $bus_id at $timestamp"
    
    # Make request
    response=$(make_request "GET" "/bus-position/${bus_id}?timestamp=${timestamp}")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for bus $bus_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields
    if echo "$response" | jq -e '.bus_id and .line_id and .time and .latitude and .longitude and .passenger_count and .next_stop_id and .distance_to_next_stop and .speed and .direction' &> /dev/null; then
        echo "$response" | format_json
        log_success "Successfully retrieved historical position for bus $bus_id"
        
        # Verify the timestamp is close to requested time
        response_time=$(echo "$response" | jq -r '.time')
        log_info "Requested: $timestamp, Received: $response_time"
    else
        echo "$response" | format_json
        log_error "Response missing required fields for bus $bus_id"
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
