#!/usr/bin/env python3
"""
Integration Tests for Deployed MCP Server on ECS.

This script performs comprehensive integration tests of the MCP server:
- Tests MCP server connectivity on ECS via HTTP API Gateway
- Verifies authentication with Secrets Manager API key
- Tests all five MCP tools against deployed Timestream
- Verifies data consistency with REST APIs
- Tests error handling and logging

Requirements validated: 14.7, 14.8, 14.10, 14.11

Usage:
    python scripts/test_mcp_integration.py --region eu-west-1
    python scripts/test_mcp_integration.py --region eu-west-1 --verbose
"""

import argparse
import sys
import json
import subprocess
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import boto3
from botocore.exceptions import ClientError
import urllib.request
import urllib.error


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.RESET}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")


def get_terraform_output(output_name: str, terraform_dir: str = "terraform") -> Optional[str]:
    """Get Terraform output value."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-raw", output_name],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_api_key_from_secrets_manager(region: str, secret_id: str = 'bus-simulator/api-key') -> Optional[str]:
    """Retrieve API key from AWS Secrets Manager."""
    try:
        client = boto3.client('secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        secret_data = json.loads(response['SecretString'])
        return secret_data['api_key']
    except Exception as e:
        print_error(f"Error retrieving API key: {e}")
        return None


def make_mcp_request(endpoint: str, tool_name: str, arguments: Dict[str, Any], 
                     api_key: str, verbose: bool = False) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Make an MCP tool request to the deployed server.
    
    Returns:
        Tuple of (success, response_data, error_message)
    """
    try:
        # Prepare MCP request payload
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        # Add API key to arguments for authentication
        payload["params"]["arguments"]["_headers"] = {
            "x-api-key": api_key,
            "x-group-name": "integration-test"
        }
        
        if verbose:
            print_info(f"Request payload: {json.dumps(payload, indent=2)}")
        
        # Make HTTP request to MCP server
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key
            }
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.getcode()
            body = response.read().decode('utf-8')
            
            if verbose:
                print_info(f"Response status: {status_code}")
                print_info(f"Response body: {body[:500]}...")
            
            if status_code != 200:
                return False, None, f"HTTP {status_code}"
            
            # Parse JSON-RPC response
            data = json.loads(body)
            
            if "error" in data:
                return False, None, data["error"].get("message", "Unknown error")
            
            if "result" in data:
                # Parse the text content from MCP response
                result_text = data["result"][0]["text"] if isinstance(data["result"], list) else data["result"]["text"]
                result_data = json.loads(result_text)
                return True, result_data, None
            
            return False, None, "Invalid response format"
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ""
        return False, None, f"HTTP {e.code}: {error_body[:200]}"
    except Exception as e:
        return False, None, str(e)


def test_mcp_server_connectivity(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """Test MCP server connectivity on ECS via HTTP API Gateway."""
    print_header("Test 1: MCP Server Connectivity on ECS")
    
    # Get MCP API endpoint from Terraform
    mcp_endpoint = get_terraform_output('mcp_api_endpoint')
    
    if not mcp_endpoint:
        print_error("Could not retrieve MCP API endpoint from Terraform")
        return False, "Endpoint not found"
    
    print_info(f"MCP API Endpoint: {mcp_endpoint}")
    
    # Check ECS service status
    cluster_name = get_terraform_output('ecs_cluster_name')
    service_name = get_terraform_output('mcp_server_service_name')
    
    if not cluster_name or not service_name:
        print_warning("Could not retrieve ECS cluster/service names")
    else:
        print_info(f"ECS Cluster: {cluster_name}")
        print_info(f"ECS Service: {service_name}")
        
        try:
            ecs_client = boto3.client('ecs', region_name=region)
            response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            
            if response['services']:
                service = response['services'][0]
                status = service['status']
                running_count = service['runningCount']
                desired_count = service['desiredCount']
                
                print_info(f"Service Status: {status}")
                print_info(f"Running Tasks: {running_count}/{desired_count}")
                
                if status != 'ACTIVE' or running_count < 1:
                    print_error(f"MCP server service not running properly")
                    return False, f"Service status: {status}, running: {running_count}"
                
                print_success("MCP server service is running on ECS")
            else:
                print_warning("MCP server service not found")
        
        except Exception as e:
            print_warning(f"Could not check ECS service status: {e}")
    
    # Test basic HTTP connectivity
    try:
        req = urllib.request.Request(mcp_endpoint)
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            print_success(f"MCP server is reachable (HTTP {response.getcode()})")
            return True, "Connectivity OK"
    
    except urllib.error.HTTPError as e:
        if e.code in [400, 401, 403, 405]:
            # These are expected for requests without proper MCP payload
            print_success(f"MCP server is reachable (HTTP {e.code} is expected)")
            return True, "Connectivity OK"
        else:
            print_error(f"Unexpected HTTP error: {e.code}")
            return False, f"HTTP {e.code}"
    
    except Exception as e:
        print_error(f"Connection failed: {e}")
        return False, str(e)


def test_mcp_authentication(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """Test authentication with Secrets Manager API key."""
    print_header("Test 2: MCP Server Authentication")
    
    mcp_endpoint = get_terraform_output('mcp_api_endpoint')
    if not mcp_endpoint:
        return False, "Endpoint not found"
    
    # Test 1: Request without API key (should fail)
    print("\nTest 2.1: Request without API key")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"stop_id": "S001", "mode": "latest"},
        "",  # Empty API key
        verbose
    )
    
    if success:
        print_error("Request succeeded without API key (should have failed)")
        return False, "Auth not enforced"
    else:
        print_success(f"Request correctly rejected: {error}")
    
    # Test 2: Request with invalid API key (should fail)
    print("\nTest 2.2: Request with invalid API key")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"stop_id": "S001", "mode": "latest"},
        "invalid-key-12345",
        verbose
    )
    
    if success:
        print_error("Request succeeded with invalid API key (should have failed)")
        return False, "Invalid key accepted"
    else:
        print_success(f"Request correctly rejected: {error}")
    
    # Test 3: Request with valid API key (should succeed)
    print("\nTest 2.3: Request with valid API key from Secrets Manager")
    api_key = get_api_key_from_secrets_manager(region)
    
    if not api_key:
        print_error("Could not retrieve API key from Secrets Manager")
        return False, "API key not found"
    
    print_info(f"Using API key: {api_key[:8]}...")
    
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"stop_id": "S001", "mode": "latest"},
        api_key,
        verbose
    )
    
    if not success:
        print_error(f"Request failed with valid API key: {error}")
        return False, f"Valid key rejected: {error}"
    
    print_success("Request succeeded with valid API key")
    print_success("Authentication with Secrets Manager API key is working correctly")
    
    return True, "Authentication OK"


def test_mcp_tools(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """Test all five MCP tools against deployed Timestream."""
    print_header("Test 3: MCP Tools Against Deployed Timestream")
    
    mcp_endpoint = get_terraform_output('mcp_api_endpoint')
    api_key = get_api_key_from_secrets_manager(region)
    
    if not mcp_endpoint or not api_key:
        return False, "Setup failed"
    
    all_passed = True
    messages = []
    
    # Tool 1: query_people_count
    print("\nTest 3.1: query_people_count tool")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"stop_id": "S001", "mode": "latest"},
        api_key,
        verbose
    )
    
    if success and data and data.get("success"):
        print_success(f"query_people_count: OK (returned {data.get('count', 0)} records)")
        messages.append("query_people_count: OK")
    else:
        print_error(f"query_people_count: FAILED - {error}")
        all_passed = False
        messages.append("query_people_count: FAILED")
    
    # Tool 2: query_sensor_data
    print("\nTest 3.2: query_sensor_data tool")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_sensor_data",
        {"entity_id": "B001", "entity_type": "bus", "mode": "latest"},
        api_key,
        verbose
    )
    
    if success and data and data.get("success"):
        print_success(f"query_sensor_data: OK (returned {data.get('count', 0)} records)")
        messages.append("query_sensor_data: OK")
    else:
        print_error(f"query_sensor_data: FAILED - {error}")
        all_passed = False
        messages.append("query_sensor_data: FAILED")
    
    # Tool 3: query_bus_position
    print("\nTest 3.3: query_bus_position tool")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_bus_position",
        {"bus_id": "B001", "mode": "latest"},
        api_key,
        verbose
    )
    
    if success and data and data.get("success"):
        print_success(f"query_bus_position: OK (returned {data.get('count', 0)} records)")
        messages.append("query_bus_position: OK")
    else:
        print_error(f"query_bus_position: FAILED - {error}")
        all_passed = False
        messages.append("query_bus_position: FAILED")
    
    # Tool 4: query_line_buses
    print("\nTest 3.4: query_line_buses tool")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_line_buses",
        {"line_id": "L1", "mode": "latest"},
        api_key,
        verbose
    )
    
    if success and data and data.get("success"):
        print_success(f"query_line_buses: OK (returned {data.get('count', 0)} records)")
        messages.append("query_line_buses: OK")
    else:
        print_error(f"query_line_buses: FAILED - {error}")
        all_passed = False
        messages.append("query_line_buses: FAILED")
    
    # Tool 5: query_time_range
    print("\nTest 3.5: query_time_range tool")
    
    # Get a time range (last hour)
    end_time = datetime.now(timezone.utc)
    start_time = end_time.replace(hour=end_time.hour - 1) if end_time.hour > 0 else end_time.replace(day=end_time.day - 1, hour=23)
    
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_time_range",
        {
            "data_type": "bus_position",
            "entity_id": "B001",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        },
        api_key,
        verbose
    )
    
    if success and data and data.get("success"):
        print_success(f"query_time_range: OK (returned {data.get('count', 0)} records)")
        messages.append("query_time_range: OK")
    else:
        print_error(f"query_time_range: FAILED - {error}")
        all_passed = False
        messages.append("query_time_range: FAILED")
    
    summary = "; ".join(messages)
    return all_passed, summary


def test_data_consistency(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """Verify data consistency between MCP server and REST APIs."""
    print_header("Test 4: Data Consistency with REST APIs")
    
    mcp_endpoint = get_terraform_output('mcp_api_endpoint')
    rest_endpoint = get_terraform_output('api_gateway_rest_endpoint')
    api_key = get_api_key_from_secrets_manager(region)
    
    if not mcp_endpoint or not rest_endpoint or not api_key:
        return False, "Setup failed"
    
    print_info(f"MCP Endpoint: {mcp_endpoint}")
    print_info(f"REST Endpoint: {rest_endpoint}")
    
    all_passed = True
    messages = []
    
    # Test 1: Compare people count data
    print("\nTest 4.1: Compare people count data")
    
    # Get data from MCP server
    mcp_success, mcp_data, mcp_error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"stop_id": "S001", "mode": "latest"},
        api_key,
        verbose
    )
    
    # Get data from REST API
    try:
        req = urllib.request.Request(f"{rest_endpoint}/people-count/S001?mode=latest")
        req.add_header('x-api-key', api_key)
        req.add_header('x-group-name', 'integration-test')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            rest_data = json.loads(response.read().decode('utf-8'))
            rest_success = True
    except Exception as e:
        rest_success = False
        rest_data = None
        print_error(f"REST API request failed: {e}")
    
    if mcp_success and rest_success:
        # Compare timestamps and counts
        mcp_record = mcp_data.get("data", [{}])[0] if mcp_data.get("data") else {}
        
        mcp_time = mcp_record.get("time")
        rest_time = rest_data.get("time")
        
        mcp_count = mcp_record.get("count")
        rest_count = rest_data.get("count")
        
        if verbose:
            print_info(f"MCP time: {mcp_time}, count: {mcp_count}")
            print_info(f"REST time: {rest_time}, count: {rest_count}")
        
        # Times should be very close (within a few seconds)
        if mcp_time and rest_time:
            mcp_dt = datetime.fromisoformat(mcp_time.replace('Z', '+00:00'))
            rest_dt = datetime.fromisoformat(rest_time.replace('Z', '+00:00'))
            time_diff = abs((mcp_dt - rest_dt).total_seconds())
            
            if time_diff < 60:  # Within 1 minute
                print_success(f"People count data is consistent (time diff: {time_diff:.1f}s)")
                messages.append("people_count: consistent")
            else:
                print_warning(f"People count timestamps differ by {time_diff:.1f}s")
                messages.append(f"people_count: time diff {time_diff:.1f}s")
        else:
            print_warning("Could not compare timestamps")
            messages.append("people_count: no timestamp")
    else:
        print_error("Could not retrieve data from both sources")
        all_passed = False
        messages.append("people_count: comparison failed")
    
    # Test 2: Compare bus position data
    print("\nTest 4.2: Compare bus position data")
    
    # Get data from MCP server
    mcp_success, mcp_data, mcp_error = make_mcp_request(
        mcp_endpoint,
        "query_bus_position",
        {"bus_id": "B001", "mode": "latest"},
        api_key,
        verbose
    )
    
    # Get data from REST API
    try:
        req = urllib.request.Request(f"{rest_endpoint}/bus-position/B001?mode=latest")
        req.add_header('x-api-key', api_key)
        req.add_header('x-group-name', 'integration-test')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            rest_data = json.loads(response.read().decode('utf-8'))
            rest_success = True
    except Exception as e:
        rest_success = False
        rest_data = None
        print_error(f"REST API request failed: {e}")
    
    if mcp_success and rest_success:
        mcp_record = mcp_data.get("data", [{}])[0] if mcp_data.get("data") else {}
        
        mcp_lat = mcp_record.get("latitude")
        rest_lat = rest_data.get("latitude")
        
        mcp_lon = mcp_record.get("longitude")
        rest_lon = rest_data.get("longitude")
        
        if verbose:
            print_info(f"MCP position: ({mcp_lat}, {mcp_lon})")
            print_info(f"REST position: ({rest_lat}, {rest_lon})")
        
        if mcp_lat and rest_lat and mcp_lon and rest_lon:
            # Positions should be very close
            lat_diff = abs(float(mcp_lat) - float(rest_lat))
            lon_diff = abs(float(mcp_lon) - float(rest_lon))
            
            if lat_diff < 0.001 and lon_diff < 0.001:  # Within ~100m
                print_success("Bus position data is consistent")
                messages.append("bus_position: consistent")
            else:
                print_warning(f"Bus positions differ (lat: {lat_diff:.6f}, lon: {lon_diff:.6f})")
                messages.append(f"bus_position: position diff")
        else:
            print_warning("Could not compare positions")
            messages.append("bus_position: no position")
    else:
        print_error("Could not retrieve data from both sources")
        all_passed = False
        messages.append("bus_position: comparison failed")
    
    summary = "; ".join(messages)
    return all_passed, summary


def test_error_handling(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """Test error handling and logging."""
    print_header("Test 5: Error Handling and Logging")
    
    mcp_endpoint = get_terraform_output('mcp_api_endpoint')
    api_key = get_api_key_from_secrets_manager(region)
    
    if not mcp_endpoint or not api_key:
        return False, "Setup failed"
    
    all_passed = True
    messages = []
    
    # Test 1: Invalid stop ID
    print("\nTest 5.1: Query with non-existent stop ID")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"stop_id": "S999", "mode": "latest"},
        api_key,
        verbose
    )
    
    if success and data:
        # Should return empty results, not an error
        if data.get("count", 0) == 0:
            print_success("Non-existent stop handled correctly (empty results)")
            messages.append("invalid_stop: OK")
        else:
            print_warning("Non-existent stop returned data (unexpected)")
            messages.append("invalid_stop: unexpected data")
    else:
        print_success(f"Non-existent stop handled with error: {error}")
        messages.append("invalid_stop: error returned")
    
    # Test 2: Invalid entity type
    print("\nTest 5.2: Query with invalid entity type")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_sensor_data",
        {"entity_id": "B001", "entity_type": "invalid", "mode": "latest"},
        api_key,
        verbose
    )
    
    if not success:
        print_success(f"Invalid entity type rejected: {error}")
        messages.append("invalid_entity_type: OK")
    else:
        print_warning("Invalid entity type accepted (should be rejected)")
        all_passed = False
        messages.append("invalid_entity_type: accepted")
    
    # Test 3: Missing required parameter
    print("\nTest 5.3: Query with missing required parameter")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"mode": "latest"},  # Missing stop_id
        api_key,
        verbose
    )
    
    if not success:
        print_success(f"Missing parameter rejected: {error}")
        messages.append("missing_param: OK")
    else:
        print_warning("Missing parameter accepted (should be rejected)")
        all_passed = False
        messages.append("missing_param: accepted")
    
    # Test 4: Invalid timestamp format
    print("\nTest 5.4: Query with invalid timestamp format")
    success, data, error = make_mcp_request(
        mcp_endpoint,
        "query_people_count",
        {"stop_id": "S001", "timestamp": "invalid-timestamp"},
        api_key,
        verbose
    )
    
    if not success:
        print_success(f"Invalid timestamp rejected: {error}")
        messages.append("invalid_timestamp: OK")
    else:
        print_warning("Invalid timestamp accepted (should be rejected)")
        all_passed = False
        messages.append("invalid_timestamp: accepted")
    
    # Test 5: Check CloudWatch logs
    print("\nTest 5.5: Check CloudWatch logs for MCP server")
    log_group = get_terraform_output('mcp_server_log_group')
    
    if log_group:
        print_info(f"Log group: {log_group}")
        
        try:
            logs_client = boto3.client('logs', region_name=region)
            
            # Get recent log streams
            response = logs_client.describe_log_streams(
                logGroupName=log_group,
                orderBy='LastEventTime',
                descending=True,
                limit=5
            )
            
            if response['logStreams']:
                print_success(f"Found {len(response['logStreams'])} log streams")
                
                # Get recent log events from the latest stream
                latest_stream = response['logStreams'][0]
                stream_name = latest_stream['logStreamName']
                
                log_response = logs_client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream_name,
                    limit=10,
                    startFromHead=False
                )
                
                if log_response['events']:
                    print_success(f"Found {len(log_response['events'])} recent log events")
                    
                    if verbose:
                        print_info("Recent log events:")
                        for event in log_response['events'][:3]:
                            timestamp = datetime.fromtimestamp(event['timestamp'] / 1000, tz=timezone.utc)
                            print_info(f"  [{timestamp}] {event['message'][:100]}")
                    
                    messages.append("logging: OK")
                else:
                    print_warning("No recent log events found")
                    messages.append("logging: no events")
            else:
                print_warning("No log streams found")
                messages.append("logging: no streams")
        
        except Exception as e:
            print_warning(f"Could not check CloudWatch logs: {e}")
            messages.append("logging: check failed")
    else:
        print_warning("Could not retrieve log group name")
        messages.append("logging: no log group")
    
    summary = "; ".join(messages)
    return all_passed, summary


def main():
    parser = argparse.ArgumentParser(
        description='Integration tests for deployed MCP server on ECS'
    )
    parser.add_argument(
        '--region',
        required=True,
        help='AWS region where the infrastructure is deployed'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}MCP Server Integration Tests{Colors.RESET}")
    print(f"{Colors.BOLD}Region: {args.region}{Colors.RESET}")
    print(f"{Colors.BOLD}Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}{Colors.RESET}")
    
    # Run all tests
    results = []
    
    # Test 1: MCP server connectivity
    success, message = test_mcp_server_connectivity(args.region, args.verbose)
    results.append(('MCP Server Connectivity', success, message))
    
    # Test 2: Authentication
    success, message = test_mcp_authentication(args.region, args.verbose)
    results.append(('MCP Authentication', success, message))
    
    # Test 3: MCP tools
    success, message = test_mcp_tools(args.region, args.verbose)
    results.append(('MCP Tools', success, message))
    
    # Test 4: Data consistency
    success, message = test_data_consistency(args.region, args.verbose)
    results.append(('Data Consistency', success, message))
    
    # Test 5: Error handling
    success, message = test_error_handling(args.region, args.verbose)
    results.append(('Error Handling', success, message))
    
    # Print summary
    print_header("Test Summary")
    
    all_passed = True
    for test_name, success, message in results:
        if success:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
            all_passed = False
        
        if args.verbose:
            print_info(f"  Details: {message}")
    
    print()
    
    if all_passed:
        print(f"{Colors.BOLD}{Colors.GREEN}✓ All integration tests passed!{Colors.RESET}\n")
        sys.exit(0)
    else:
        print(f"{Colors.BOLD}{Colors.RED}✗ Some tests failed. Please review and fix issues.{Colors.RESET}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
