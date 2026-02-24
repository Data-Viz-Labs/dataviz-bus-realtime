#!/bin/bash

# Test Authentication - Missing Group Name
# This script tests that requests without x-group-name header are rejected

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Authentication (Missing Group Name)"

# Test endpoints without group name header
endpoints=(
    "/people-count/S001?mode=latest"
    "/sensors/bus/B001?mode=latest"
    "/bus-position/B001?mode=latest"
)
all_passed=true

for endpoint in "${endpoints[@]}"; do
    log_test "Request to $endpoint without x-group-name header (should return 401)"
    
    # Make request without group name
    response=$(make_request_no_group "GET" "$endpoint")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for $endpoint"
        all_passed=false
        continue
    fi
    
    # Check if response contains error field indicating unauthorized
    if echo "$response" | jq -e '.error' &> /dev/null; then
        error_type=$(echo "$response" | jq -r '.error')
        error_message=$(echo "$response" | jq -r '.message')
        echo "$response" | format_json
        
        if [[ "$error_type" == "Unauthorized" ]] || [[ "$error_message" == *"group"* ]]; then
            log_success "Correctly rejected request without group name"
        else
            log_warning "Got error but not related to missing group name: $error_type"
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
    log_info "Requests without x-group-name header are correctly rejected"
    exit 0
else
    log_error "Some tests failed"
    log_error "Requests without x-group-name header may not be properly rejected"
    exit 1
fi
