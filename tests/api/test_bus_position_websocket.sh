#!/bin/bash

# Test Bus Position API - WebSocket Subscription
# This script tests WebSocket connection and real-time updates

# Source common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Check dependencies
check_dependencies

# Check if wscat is installed
if ! command -v wscat &> /dev/null; then
    log_error "wscat not found. Install with: npm install -g wscat"
    exit 1
fi

# Print header
print_header "Testing Bus Position API (WebSocket)"

# Get credentials
api_key=$(get_api_key)
group_name=$(get_group_name)
ws_url=$(get_ws_url)

# Build WebSocket URL with authentication
ws_auth_url="${ws_url}?api_key=${api_key}&group_name=${group_name}"

log_info "WebSocket URL: ${ws_url}"
log_info "Connecting with API key and group name..."
echo ""

# Test 1: Connection test
log_test "Test 1: Establish WebSocket connection"
echo ""

# Create a temporary file for the subscription message
temp_file=$(mktemp)
cat > "$temp_file" << 'EOF'
{"action":"subscribe","line_ids":["L1","L2"]}
EOF

log_info "Connecting to WebSocket and subscribing to lines L1 and L2..."
log_info "Will listen for 10 seconds to receive position updates..."
echo ""
echo "Expected output: Bus position updates in JSON format"
echo "Press Ctrl+C to stop early if needed"
echo ""
echo "========================================"

# Connect and send subscription, then listen for 10 seconds
timeout 10s wscat -c "$ws_auth_url" -x "$(cat $temp_file)" 2>&1 || true

echo ""
echo "========================================"
echo ""

# Clean up
rm -f "$temp_file"

# Test 2: Connection with invalid credentials (should fail)
log_test "Test 2: Connection with invalid API key (should fail)"
echo ""

invalid_ws_url="${ws_url}?api_key=invalid-key-12345&group_name=${group_name}"

log_info "Attempting connection with invalid API key..."
log_info "Expected: Connection should be rejected (401 Unauthorized)"
echo ""

# Try to connect with invalid key (should fail quickly)
timeout 5s wscat -c "$invalid_ws_url" 2>&1 | head -n 5 || true

echo ""
echo "========================================"
echo ""

# Summary
log_info "WebSocket tests completed"
echo ""
log_info "Manual verification checklist:"
echo "  1. Connection established successfully with valid credentials"
echo "  2. Received bus position updates in JSON format"
echo "  3. Updates contain bus_id, line_id, latitude, longitude, etc."
echo "  4. Connection rejected with invalid API key"
echo ""
log_warning "Note: This test requires manual verification of the output"
log_warning "Automated WebSocket testing requires more complex tooling"
echo ""

exit 0
