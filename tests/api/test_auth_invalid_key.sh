#!/bin/bash

# Test Authentication - Invalid API Key
# This script tests that requests with invalid API keys are rejected

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Authentication (Invalid API Key)"

# Test endpoints with invalid API key
endpoints=(
    "/people-count/S001?mode=latest"
    "/sensors/bus/B001?mode=latest"
    "/bus-position/B001?mode=latest"
)
all_passed=true

for endpoint in "${endpoints[@]}"; do
    log_test "Request to $endpoint with invalid API key (should return 401)"
    
    # Make request with invalid API key
    response=$(make_request_invalid_key "GET" "$endpoint")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for $endpoint"
        all_passed=false
        continue
    fi
    
    # Check if response contains error field indicating unauthorized
    if echo "$response" | jq -e '.error' &> /dev/null; then
        error_type=$(echo "$response" | jq -r '.error')
        echo "$response" | format_json
        
        if [[ "$error_type" == "Unauthorized" ]] || [[ "$error_type" == "Forbidden" ]]; then
            log_success "Correctly rejected request with invalid API key"
        else
            log_warning "Got error but not Unauthorized: $error_type"
        fi
    else
        echo "$response" | format_json
        log_error "Expected 401 Unauthorized, but request succeeded"
        all_passed=false
    fi
    
    echo ""
done

# Summary
echo "========================================"
if [ "$all_passed" = true ]; then
    log_success "All tests passed!"
    log_info "Invalid API keys are correctly rejected"
    exit 0
else
    log_error "Some tests failed"
    log_error "Invalid API keys may not be properly rejected"
    exit 1
fi
