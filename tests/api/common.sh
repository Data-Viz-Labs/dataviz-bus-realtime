#!/bin/bash

# Common utilities for API testing scripts

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if required dependencies are installed
check_dependencies() {
    local missing_deps=()
    
    if ! command -v curl &> /dev/null; then
        missing_deps+=("curl")
    fi
    
    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}Warning: jq not found. JSON output will not be formatted.${NC}"
        echo "Install jq: brew install jq (macOS) or sudo apt-get install jq (Ubuntu)"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo -e "${RED}Error: Missing required dependencies: ${missing_deps[*]}${NC}"
        echo "Please install the missing dependencies and try again."
        exit 1
    fi
}

# Get API key from environment or AWS Secrets Manager
get_api_key() {
    if [ -n "$API_KEY" ]; then
        echo "$API_KEY"
        return 0
    fi
    
    # Try to get from Secrets Manager
    if command -v aws &> /dev/null; then
        local region=$(get_aws_region)
        local key=$(aws secretsmanager get-secret-value \
            --secret-id bus-simulator/api-key \
            --region "$region" \
            --query SecretString \
            --output text 2>/dev/null | jq -r '.api_key' 2>/dev/null)
        
        if [ -n "$key" ] && [ "$key" != "null" ]; then
            echo "$key"
            return 0
        fi
    fi
    
    echo -e "${RED}Error: API_KEY not set and could not retrieve from Secrets Manager${NC}"
    echo "Make sure:"
    echo "  1. AWS CLI is configured (aws configure)"
    echo "  2. Infrastructure is deployed (cd ../../terraform && terraform apply)"
    echo "  3. You have permissions to access Secrets Manager"
    exit 1
}

# Get AWS region from Terraform or environment
get_aws_region() {
    # Try environment variable first
    if [ -n "$AWS_REGION" ]; then
        echo "$AWS_REGION"
        return 0
    fi
    
    # Try AWS CLI default region
    if command -v aws &> /dev/null; then
        local region=$(aws configure get region 2>/dev/null)
        if [ -n "$region" ]; then
            echo "$region"
            return 0
        fi
    fi
    
    # Try Terraform outputs
    if [ -f "../../terraform/terraform.tfstate" ]; then
        local region=$(cd ../../terraform && terraform output -raw aws_region 2>/dev/null)
        if [ -n "$region" ] && [ "$region" != "null" ]; then
            echo "$region"
            return 0
        fi
    fi
    
    # Default to eu-west-1
    echo "eu-west-1"
}

# Get API URL from environment or Terraform outputs
get_api_url() {
    if [ -n "$API_URL" ]; then
        echo "$API_URL"
        return 0
    fi
    
    # Try to get from Terraform outputs
    if [ -f "../../terraform/terraform.tfstate" ]; then
        local url=$(cd ../../terraform && terraform output -raw rest_api_url 2>/dev/null)
        if [ -n "$url" ] && [ "$url" != "null" ]; then
            echo "$url"
            return 0
        fi
    fi
    
    echo -e "${RED}Error: API_URL not set and could not retrieve from Terraform${NC}"
    echo "Make sure infrastructure is deployed: cd ../../terraform && terraform apply"
    exit 1
}

# Get WebSocket URL from environment or Terraform outputs
get_ws_url() {
    if [ -n "$WS_URL" ]; then
        echo "$WS_URL"
        return 0
    fi
    
    # Try to get from Terraform outputs
    if [ -f "../../terraform/terraform.tfstate" ]; then
        local url=$(cd ../../terraform && terraform output -raw websocket_api_url 2>/dev/null)
        if [ -n "$url" ] && [ "$url" != "null" ]; then
            echo "$url"
            return 0
        fi
    fi
    
    echo -e "${RED}Error: WS_URL not set and could not retrieve from Terraform${NC}"
    echo "Make sure infrastructure is deployed: cd ../../terraform && terraform apply"
    exit 1
}

# Get MCP API URL from environment or Terraform outputs
get_mcp_url() {
    if [ -n "$MCP_URL" ]; then
        echo "$MCP_URL"
        return 0
    fi
    
    # Try to get from Terraform outputs
    if [ -f "../../terraform/terraform.tfstate" ]; then
        local url=$(cd ../../terraform && terraform output -raw mcp_api_endpoint 2>/dev/null)
        if [ -n "$url" ] && [ "$url" != "null" ]; then
            echo "$url"
            return 0
        fi
    fi
    
    echo -e "${RED}Error: MCP_URL not set and could not retrieve from Terraform${NC}"
    echo "Make sure infrastructure is deployed: cd ../../terraform && terraform apply"
    exit 1
}

# Get group name from environment or use default
get_group_name() {
    if [ -n "$GROUP_NAME" ]; then
        echo "$GROUP_NAME"
        return 0
    fi
    
    # Use default group name for testing
    echo "test-group"
}

# Format JSON output if jq is available
format_json() {
    if command -v jq &> /dev/null; then
        jq '.'
    else
        cat
    fi
}

# Make an authenticated HTTP request
make_request() {
    local method="$1"
    local endpoint="$2"
    local api_key=$(get_api_key)
    local group_name=$(get_group_name)
    local api_url=$(get_api_url)
    
    curl -s -X "$method" \
        -H "x-api-key: $api_key" \
        -H "x-group-name: $group_name" \
        "${api_url}${endpoint}"
}

# Make a request without authentication (for testing auth failures)
make_request_no_auth() {
    local method="$1"
    local endpoint="$2"
    local api_url=$(get_api_url)
    
    curl -s -X "$method" "${api_url}${endpoint}"
}

# Make a request with invalid API key
make_request_invalid_key() {
    local method="$1"
    local endpoint="$2"
    local group_name=$(get_group_name)
    local api_url=$(get_api_url)
    
    curl -s -X "$method" \
        -H "x-api-key: invalid-key-12345" \
        -H "x-group-name: $group_name" \
        "${api_url}${endpoint}"
}

# Make a request without group name header
make_request_no_group() {
    local method="$1"
    local endpoint="$2"
    local api_key=$(get_api_key)
    local api_url=$(get_api_url)
    
    curl -s -X "$method" \
        -H "x-api-key: $api_key" \
        "${api_url}${endpoint}"
}

# Make an authenticated HTTP request to MCP server
make_mcp_request() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local api_key=$(get_api_key)
    local group_name=$(get_group_name)
    local mcp_url=$(get_mcp_url)
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -H "x-api-key: $api_key" \
            -H "x-group-name: $group_name" \
            -d "$data" \
            "${mcp_url}${endpoint}"
    else
        curl -s -X "$method" \
            -H "x-api-key: $api_key" \
            -H "x-group-name: $group_name" \
            "${mcp_url}${endpoint}"
    fi
}

# Make a request to MCP server without authentication
make_mcp_request_no_auth() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local mcp_url=$(get_mcp_url)
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "${mcp_url}${endpoint}"
    else
        curl -s -X "$method" "${mcp_url}${endpoint}"
    fi
}

# Make a request to MCP server with invalid API key
make_mcp_request_invalid_key() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local group_name=$(get_group_name)
    local mcp_url=$(get_mcp_url)
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -H "x-api-key: invalid-key-12345" \
            -H "x-group-name: $group_name" \
            -d "$data" \
            "${mcp_url}${endpoint}"
    else
        curl -s -X "$method" \
            -H "x-api-key: invalid-key-12345" \
            -H "x-group-name: $group_name" \
            "${mcp_url}${endpoint}"
    fi
}

# Make a request to MCP server without group name header
make_mcp_request_no_group() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    local api_key=$(get_api_key)
    local mcp_url=$(get_mcp_url)
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -H "x-api-key: $api_key" \
            -d "$data" \
            "${mcp_url}${endpoint}"
    else
        curl -s -X "$method" \
            -H "x-api-key: $api_key" \
            "${mcp_url}${endpoint}"
    fi
}

# Log test execution
log_test() {
    local test_name="$1"
    echo -e "${BLUE}Testing: $test_name${NC}"
}

# Log success
log_success() {
    local message="$1"
    echo -e "${GREEN}✓ $message${NC}"
}

# Log error
log_error() {
    local message="$1"
    echo -e "${RED}✗ $message${NC}"
}

# Log warning
log_warning() {
    local message="$1"
    echo -e "${YELLOW}⚠ $message${NC}"
}

# Log info
log_info() {
    local message="$1"
    echo -e "${BLUE}ℹ $message${NC}"
}

# Print section header
print_header() {
    local title="$1"
    echo ""
    echo "========================================"
    echo "$title"
    echo "========================================"
    echo ""
}

# Check HTTP response status
check_status() {
    local response="$1"
    local expected_status="$2"
    
    # Extract status code from response (if curl -w option was used)
    # For now, we check if response contains error field
    if echo "$response" | jq -e '.error' &> /dev/null; then
        return 1
    else
        return 0
    fi
}

# Validate JSON response
validate_json() {
    local response="$1"
    
    if echo "$response" | jq empty 2>/dev/null; then
        return 0
    else
        log_error "Invalid JSON response"
        return 1
    fi
}

# Get current timestamp in ISO 8601 format
get_timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Get timestamp from N minutes ago
get_past_timestamp() {
    local minutes_ago="$1"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        date -u -v-${minutes_ago}M +"%Y-%m-%dT%H:%M:%SZ"
    else
        # Linux
        date -u -d "$minutes_ago minutes ago" +"%Y-%m-%dT%H:%M:%SZ"
    fi
}

# Wait for a few seconds (useful between tests)
wait_seconds() {
    local seconds="$1"
    sleep "$seconds"
}

# Export functions for use in other scripts
export -f check_dependencies
export -f get_aws_region
export -f get_api_key
export -f get_api_url
export -f get_ws_url
export -f get_mcp_url
export -f get_group_name
export -f format_json
export -f make_request
export -f make_request_no_auth
export -f make_request_invalid_key
export -f make_request_no_group
export -f make_mcp_request
export -f make_mcp_request_no_auth
export -f make_mcp_request_invalid_key
export -f make_mcp_request_no_group
export -f log_test
export -f log_success
export -f log_error
export -f log_warning
export -f log_info
export -f print_header
export -f check_status
export -f validate_json
export -f get_timestamp
export -f get_past_timestamp
export -f wait_seconds
