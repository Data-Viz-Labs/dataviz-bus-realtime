#!/bin/bash

# Test Authentication - Missing API Key
# This script tests that requests without API keys are rejected

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Authentication (Missing API Key)"

# Test endpoints without API key
endpoints=(
    "/people-count/S001?mode=latest"
    "/sensors/bus/B001?mode=latest"
    "/bus-position/B001?mode=latest"
)
all_passed=true

for endpoint in "${endpoints[@]}"; do
    log_test "Request to $endpoint without API key (should return 401)"
    
    # Make request without authentication
    response=$(make_request_no_auth "GET" "$endpoint")
    
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
            log_success "Correctly rejected request without API key"
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
    log_info "Requests without API keys are correctly rejected"
    exit 0
else
    log_error "Some tests failed"
    log_error "Requests without API keys may not be properly rejected"
    exit 1
fi
