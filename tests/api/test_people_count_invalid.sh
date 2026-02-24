#!/bin/bash

# Test People Count API - Error Handling
# This script tests error handling for non-existent stops

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing People Count API (Error Handling)"

# Test cases with invalid stop IDs
invalid_stops=("S999" "INVALID" "S000")
all_passed=true

for stop_id in "${invalid_stops[@]}"; do
    log_test "Query non-existent stop $stop_id (should return 404)"
    
    # Make request
    response=$(make_request "GET" "/people-count/${stop_id}?mode=latest")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for stop $stop_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains error field
    if echo "$response" | jq -e '.error' &> /dev/null; then
        echo "$response" | format_json
        log_success "Correctly returned error for non-existent stop $stop_id"
    else
        echo "$response" | format_json
        log_error "Expected error response for stop $stop_id, but got success"
        all_passed=false
    fi
    
    echo ""
done

# Test missing parameters
log_test "Query without mode or timestamp parameter (should return 400)"
response=$(make_request "GET" "/people-count/S001")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    all_passed=false
else
    if echo "$response" | jq -e '.error' &> /dev/null; then
        echo "$response" | format_json
        log_success "Correctly returned error for missing parameters"
    else
        echo "$response" | format_json
        log_warning "Expected error for missing parameters"
    fi
fi

echo ""

# Summary
echo "========================================"
if [ "$all_passed" = true ]; then
    log_success "All tests passed!"
    exit 0
else
    log_error "Some tests failed"
    exit 1
fi
