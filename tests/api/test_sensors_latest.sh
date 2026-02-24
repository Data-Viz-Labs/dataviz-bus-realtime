#!/bin/bash

# Test Sensors API - Latest Data Query
# This script tests querying the latest sensor data from buses and stops

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Sensors API (Latest)"

# Test cases for buses
log_info "Testing bus sensors..."
bus_tests=("B001" "B002" "B003")
all_passed=true

for bus_id in "${bus_tests[@]}"; do
    log_test "Get latest sensor data for bus $bus_id"
    
    # Make request
    response=$(make_request "GET" "/sensors/bus/${bus_id}?mode=latest")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for bus $bus_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields for bus
    if echo "$response" | jq -e '.entity_id and .entity_type and .time and .temperature and .humidity and .co2_level and .door_status' &> /dev/null; then
        echo "$response" | format_json
        log_success "Successfully retrieved sensor data for bus $bus_id"
    else
        echo "$response" | format_json
        log_error "Response missing required fields for bus $bus_id"
        all_passed=false
    fi
    
    echo ""
done

# Test cases for stops
log_info "Testing stop sensors..."
stop_tests=("S001" "S002" "S003")

for stop_id in "${stop_tests[@]}"; do
    log_test "Get latest sensor data for stop $stop_id"
    
    # Make request
    response=$(make_request "GET" "/sensors/stop/${stop_id}?mode=latest")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for stop $stop_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields for stop (no CO2 or door status)
    if echo "$response" | jq -e '.entity_id and .entity_type and .time and .temperature and .humidity' &> /dev/null; then
        echo "$response" | format_json
        log_success "Successfully retrieved sensor data for stop $stop_id"
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
