#!/bin/bash

# Test Sensors API - Error Handling
# This script tests error handling for non-existent entities

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Sensors API (Error Handling)"

# Test cases with invalid entity IDs
invalid_entities=(
    "bus:B999"
    "bus:INVALID"
    "stop:S999"
    "stop:INVALID"
)
all_passed=true

for test_case in "${invalid_entities[@]}"; do
    IFS=':' read -r entity_type entity_id <<< "$test_case"
    
    log_test "Query non-existent $entity_type $entity_id (should return 404)"
    
    # Make request
    response=$(make_request "GET" "/sensors/${entity_type}/${entity_id}?mode=latest")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for $entity_type $entity_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains error field
    if echo "$response" | jq -e '.error' &> /dev/null; then
        echo "$response" | format_json
        log_success "Correctly returned error for non-existent $entity_type $entity_id"
    else
        echo "$response" | format_json
        log_error "Expected error response for $entity_type $entity_id, but got success"
        all_passed=false
    fi
    
    echo ""
done

# Test invalid entity type
log_test "Query with invalid entity type (should return 404 or 400)"
response=$(make_request "GET" "/sensors/invalid_type/E001?mode=latest")

if ! validate_json "$response"; then
    log_error "Invalid JSON response"
    all_passed=false
else
    if echo "$response" | jq -e '.error' &> /dev/null; then
        echo "$response" | format_json
        log_success "Correctly returned error for invalid entity type"
    else
        echo "$response" | format_json
        log_warning "Expected error for invalid entity type"
    fi
fi

echo ""

# Test missing parameters
log_test "Query without mode or timestamp parameter (should return 400)"
response=$(make_request "GET" "/sensors/bus/B001")

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
