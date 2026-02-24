#!/bin/bash

# Test Sensors API - Historical Data Query
# This script tests querying historical sensor data with timestamps

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Sensors API (Historical)"

# Test cases with different timestamps
test_cases=(
    "bus:B001:5"    # Bus B001, 5 minutes ago
    "bus:B002:10"   # Bus B002, 10 minutes ago
    "stop:S001:15"  # Stop S001, 15 minutes ago
    "stop:S002:20"  # Stop S002, 20 minutes ago
)
all_passed=true

for test_case in "${test_cases[@]}"; do
    IFS=':' read -r entity_type entity_id minutes_ago <<< "$test_case"
    
    # Get timestamp from N minutes ago
    timestamp=$(get_past_timestamp "$minutes_ago")
    
    log_test "Get sensor data for $entity_type $entity_id at $timestamp"
    
    # Make request
    response=$(make_request "GET" "/sensors/${entity_type}/${entity_id}?timestamp=${timestamp}")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for $entity_type $entity_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields
    if [ "$entity_type" = "bus" ]; then
        # Bus should have CO2 and door status
        if echo "$response" | jq -e '.entity_id and .entity_type and .time and .temperature and .humidity and .co2_level and .door_status' &> /dev/null; then
            echo "$response" | format_json
            log_success "Successfully retrieved historical data for $entity_type $entity_id"
        else
            echo "$response" | format_json
            log_error "Response missing required fields for $entity_type $entity_id"
            all_passed=false
        fi
    else
        # Stop should not have CO2 and door status
        if echo "$response" | jq -e '.entity_id and .entity_type and .time and .temperature and .humidity' &> /dev/null; then
            echo "$response" | format_json
            log_success "Successfully retrieved historical data for $entity_type $entity_id"
        else
            echo "$response" | format_json
            log_error "Response missing required fields for $entity_type $entity_id"
            all_passed=false
        fi
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
