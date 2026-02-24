#!/bin/bash

# Master Test Runner - Run All API Tests
# This script runs all API test scripts in sequence

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Print main header
echo ""
echo "###############################################"
echo "#  Madrid Bus Simulator - API Test Suite     #"
echo "###############################################"
echo ""

# Verify environment is configured
log_info "Verifying environment configuration..."
get_api_key > /dev/null || exit 1
get_group_name > /dev/null || exit 1
get_api_url > /dev/null || exit 1
log_success "Environment configured correctly"
echo ""

# Track test results
total_tests=0
passed_tests=0
failed_tests=0

# Function to run a test script
run_test() {
    local test_script="$1"
    local test_name="$2"
    
    total_tests=$((total_tests + 1))
    
    echo ""
    echo "-----------------------------------------------"
    log_info "Running: $test_name"
    echo "-----------------------------------------------"
    
    if bash "$SCRIPT_DIR/$test_script"; then
        passed_tests=$((passed_tests + 1))
        log_success "$test_name PASSED"
    else
        failed_tests=$((failed_tests + 1))
        log_error "$test_name FAILED"
    fi
    
    echo ""
}

# Run all test scripts
echo "==============================================="
echo "PEOPLE COUNT API TESTS"
echo "==============================================="

run_test "test_people_count_latest.sh" "People Count - Latest"
run_test "test_people_count_historical.sh" "People Count - Historical"
run_test "test_people_count_invalid.sh" "People Count - Error Handling"

echo ""
echo "==============================================="
echo "SENSORS API TESTS"
echo "==============================================="

run_test "test_sensors_latest.sh" "Sensors - Latest"
run_test "test_sensors_historical.sh" "Sensors - Historical"
run_test "test_sensors_invalid.sh" "Sensors - Error Handling"

echo ""
echo "==============================================="
echo "BUS POSITION API TESTS"
echo "==============================================="

run_test "test_bus_position_latest.sh" "Bus Position - Latest"
run_test "test_bus_position_historical.sh" "Bus Position - Historical"

# WebSocket test (optional, requires wscat)
if command -v wscat &> /dev/null; then
    run_test "test_bus_position_websocket.sh" "Bus Position - WebSocket"
else
    log_warning "Skipping WebSocket test (wscat not installed)"
    log_info "Install wscat: npm install -g wscat"
fi

echo ""
echo "==============================================="
echo "AUTHENTICATION TESTS"
echo "==============================================="

run_test "test_auth_invalid_key.sh" "Authentication - Invalid Key"
run_test "test_auth_missing_key.sh" "Authentication - Missing Key"
run_test "test_auth_missing_group.sh" "Authentication - Missing Group"

# Print summary
echo ""
echo "###############################################"
echo "#  TEST SUMMARY                               #"
echo "###############################################"
echo ""
echo "Total Tests:  $total_tests"
echo "Passed:       $passed_tests"
echo "Failed:       $failed_tests"
echo ""

if [ $failed_tests -eq 0 ]; then
    log_success "ALL TESTS PASSED! ✓"
    echo ""
    exit 0
else
    log_error "SOME TESTS FAILED! ✗"
    echo ""
    exit 1
fi
