#!/bin/bash

# Test Bus Position API - Latest Data Query
# This script tests querying the latest bus positions

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print header
print_header "Testing Bus Position API (Latest)"

# Test individual bus positions
log_info "Testing individual bus positions..."
bus_tests=("B001" "B002" "B003")
all_passed=true

for bus_id in "${bus_tests[@]}"; do
    log_test "Get latest position for bus $bus_id"
    
    # Make request
    response=$(make_request "GET" "/bus-position/${bus_id}?mode=latest")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for bus $bus_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields
    if echo "$response" | jq -e '.bus_id and .line_id and .time and .latitude and .longitude and .passenger_count and .next_stop_id and .distance_to_next_stop and .speed and .direction' &> /dev/null; then
        echo "$response" | format_json
        log_success "Successfully retrieved position for bus $bus_id"
    else
        echo "$response" | format_json
        log_error "Response missing required fields for bus $bus_id"
        all_passed=false
    fi
    
    echo ""
done

# Test line queries (all buses on a line)
log_info "Testing line queries (all buses on a line)..."
line_tests=("L1" "L2")

for line_id in "${line_tests[@]}"; do
    log_test "Get all buses on line $line_id"
    
    # Make request
    response=$(make_request "GET" "/bus-position/line/${line_id}?mode=latest")
    
    # Validate JSON
    if ! validate_json "$response"; then
        log_error "Invalid JSON response for line $line_id"
        all_passed=false
        continue
    fi
    
    # Check if response contains expected fields
    if echo "$response" | jq -e '.line_id and .buses' &> /dev/null; then
        echo "$response" | format_json
        
        # Count buses
        bus_count=$(echo "$response" | jq '.buses | length')
        log_success "Successfully retrieved $bus_count buses on line $line_id"
    else
        echo "$response" | format_json
        log_error "Response missing required fields for line $line_id"
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
