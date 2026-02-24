#!/bin/bash

# Test People Count API - Latest Data Query
# This script tests querying the latest people count at bus stops

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing People Count API (Latest)"

# Test cases
test_stops=("S001" "S002" "S003")
all_passed=true

for stop_id in "${test_stops[@]}"; do
    log_test "Get latest people count for stop $stop_id"
    
    # Make request
    response=$(make_request "GET" "/people-count/${stop_id}?mode=latest")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for stop $stop_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields
    if echo "$response" | jq -e '.stop_id and .time and .count and .line_ids' &> /dev/null; then
        echo "$response" | format_json
        log_success "Successfully retrieved people count for stop $stop_id"
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
