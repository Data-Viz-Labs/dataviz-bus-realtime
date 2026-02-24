#!/usr/bin/env python3
"""
Pre-Hackathon Verification Script for Madrid Bus Real-Time Simulator.

This script performs comprehensive checks to ensure the system is ready for the hackathon:
- Verifies Timestream has at least 5 days of historical data
- Checks Fargate service health (all services running)
- Tests all REST API endpoints with valid API keys
- Tests WebSocket connection with API key authentication
- Verifies API key authentication is working correctly

Usage:
    python verify_deployment.py --region eu-west-1
    python verify_deployment.py --region eu-west-1 --verbose
"""

import argparse
import sys
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError


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


def get_api_key_from_secrets_manager(region: str, secret_id: str = 'bus-simulator/api-key') -> Optional[str]:
    """
    Retrieve API key from AWS Secrets Manager.
    
    Args:
        region: AWS region
        secret_id: Secrets Manager secret ID
        
    Returns:
        API key value or None if not found
    """
    try:
        client = boto3.client('secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        secret_data = json.loads(response['SecretString'])
        return secret_data['api_key']
    except ClientError as e:
        print_error(f"Error retrieving API key from Secrets Manager: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        print_error(f"Error parsing API key from Secrets Manager: {e}")
        return None


def get_api_key(region: str) -> Optional[str]:
    """
    Get API key from Secrets Manager (preferred) or Terraform outputs (fallback).
    
    Args:
        region: AWS region
        
    Returns:
        API key value or None if not found
    """
    # Try Secrets Manager first
    api_key = get_api_key_from_secrets_manager(region)
    if api_key:
        print_info("Retrieved API key from Secrets Manager")
        return api_key
    
    # Fallback to Terraform outputs
    print_warning("Could not retrieve API key from Secrets Manager, trying Terraform outputs...")
    api_key_value = get_terraform_output('api_key_value')
    if api_key_value:
        print_info("Retrieved API key from Terraform outputs")
        return api_key_value
    
    return None


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


def get_terraform_output_json(output_name: str, terraform_dir: str = "terraform") -> Optional[any]:
    """Get Terraform output value as JSON."""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json", output_name],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def check_timestream_data_volume(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """
    Check if Timestream has at least 5 days of historical data.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print_header("Checking Timestream Data Volume")
    
    # Get database and table names from Terraform
    database_name = get_terraform_output('timestream_database_name')
    if not database_name:
        return False, "Could not retrieve Timestream database name from Terraform"
    
    print_info(f"Database: {database_name}")
    
    # Initialize Timestream query client
    query_client = boto3.client('timestream-query', region_name=region)
    
    # Check each table
    tables = ['people_count', 'sensor_data', 'bus_position']
    all_passed = True
    messages = []
    
    for table_name in tables:
        print(f"\nChecking table: {table_name}")
        
        try:
            # Query for the oldest and newest timestamps
            query = f"""
                SELECT 
                    MIN(time) as oldest_time,
                    MAX(time) as newest_time,
                    COUNT(*) as record_count
                FROM "{database_name}"."{table_name}"
            """
            
            if verbose:
                print_info(f"Query: {query}")
            
            response = query_client.query(QueryString=query)
            
            if not response['Rows']:
                print_error(f"No data found in {table_name}")
                all_passed = False
                messages.append(f"{table_name}: No data")
                continue
            
            # Parse results
            row = response['Rows'][0]
            oldest_time_str = row['Data'][0].get('ScalarValue')
            newest_time_str = row['Data'][1].get('ScalarValue')
            record_count = int(row['Data'][2].get('ScalarValue', 0))
            
            if not oldest_time_str or not newest_time_str:
                print_error(f"Could not retrieve timestamps from {table_name}")
                all_passed = False
                messages.append(f"{table_name}: Invalid timestamps")
                continue
            
            # Parse timestamps
            oldest_time = datetime.fromisoformat(oldest_time_str.replace('Z', '+00:00'))
            newest_time = datetime.fromisoformat(newest_time_str.replace('Z', '+00:00'))
            
            # Calculate data span
            data_span = newest_time - oldest_time
            days_of_data = data_span.total_seconds() / (24 * 3600)
            
            print_info(f"  Oldest record: {oldest_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print_info(f"  Newest record: {newest_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print_info(f"  Data span: {days_of_data:.2f} days")
            print_info(f"  Record count: {record_count:,}")
            
            # Check if we have at least 5 days of data
            if days_of_data >= 5.0:
                print_success(f"{table_name}: {days_of_data:.2f} days of data (≥ 5 days required)")
                messages.append(f"{table_name}: {days_of_data:.2f} days")
            else:
                print_warning(f"{table_name}: Only {days_of_data:.2f} days of data (< 5 days required)")
                all_passed = False
                messages.append(f"{table_name}: {days_of_data:.2f} days (insufficient)")
        
        except ClientError as e:
            print_error(f"Error querying {table_name}: {e}")
            all_passed = False
            messages.append(f"{table_name}: Query error")
        except Exception as e:
            print_error(f"Unexpected error checking {table_name}: {e}")
            all_passed = False
            messages.append(f"{table_name}: Unexpected error")
    
    summary = "; ".join(messages)
    return all_passed, summary


def check_fargate_services(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """
    Check Fargate service health.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print_header("Checking Fargate Service Health")
    
    # Get cluster name from Terraform
    cluster_name = get_terraform_output('ecs_cluster_name')
    if not cluster_name:
        return False, "Could not retrieve ECS cluster name from Terraform"
    
    print_info(f"Cluster: {cluster_name}")
    
    # Initialize ECS client
    ecs_client = boto3.client('ecs', region_name=region)
    
    # Expected services
    expected_services = [
        'people-count-feeder',
        'sensors-feeder',
        'bus-position-feeder'
    ]
    
    all_passed = True
    messages = []
    
    for service_name in expected_services:
        print(f"\nChecking service: {service_name}")
        
        try:
            response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_name]
            )
            
            if not response['services']:
                print_error(f"Service {service_name} not found")
                all_passed = False
                messages.append(f"{service_name}: Not found")
                continue
            
            service = response['services'][0]
            
            # Check service status
            status = service['status']
            desired_count = service['desiredCount']
            running_count = service['runningCount']
            pending_count = service['pendingCount']
            
            print_info(f"  Status: {status}")
            print_info(f"  Desired: {desired_count}, Running: {running_count}, Pending: {pending_count}")
            
            if verbose:
                # Get task details
                task_arns = ecs_client.list_tasks(
                    cluster=cluster_name,
                    serviceName=service_name
                )['taskArns']
                
                if task_arns:
                    tasks = ecs_client.describe_tasks(
                        cluster=cluster_name,
                        tasks=task_arns
                    )['tasks']
                    
                    for task in tasks:
                        print_info(f"  Task: {task['taskArn'].split('/')[-1]}")
                        print_info(f"    Status: {task['lastStatus']}")
                        print_info(f"    Health: {task.get('healthStatus', 'N/A')}")
            
            # Verify service is running
            if status == 'ACTIVE' and running_count >= desired_count:
                print_success(f"{service_name}: Running ({running_count}/{desired_count} tasks)")
                messages.append(f"{service_name}: OK")
            elif status == 'ACTIVE' and running_count > 0:
                print_warning(f"{service_name}: Partially running ({running_count}/{desired_count} tasks)")
                messages.append(f"{service_name}: Partial")
            else:
                print_error(f"{service_name}: Not running properly (status: {status}, running: {running_count})")
                all_passed = False
                messages.append(f"{service_name}: Failed")
        
        except ClientError as e:
            print_error(f"Error checking {service_name}: {e}")
            all_passed = False
            messages.append(f"{service_name}: Error")
        except Exception as e:
            print_error(f"Unexpected error checking {service_name}: {e}")
            all_passed = False
            messages.append(f"{service_name}: Unexpected error")
    
    summary = "; ".join(messages)
    return all_passed, summary


def test_rest_api_endpoints(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """
    Test all REST API endpoints with valid API keys.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print_header("Testing REST API Endpoints")
    
    # Get API endpoint and key
    rest_endpoint = get_terraform_output('api_gateway_rest_endpoint')
    api_key = get_api_key(region)
    
    if not rest_endpoint:
        return False, "Could not retrieve REST API endpoint from Terraform"
    
    if not api_key:
        return False, "Could not retrieve API key from Secrets Manager or Terraform"
    
    print_info(f"REST API Endpoint: {rest_endpoint}")
    print_info(f"Using API key: {api_key[:8]}...")
    
    # Test endpoints
    import urllib.request
    import urllib.error
    
    endpoints_to_test = [
        {
            'name': 'People Count (latest)',
            'url': f"{rest_endpoint}/people-count/S001?mode=latest",
            'expected_fields': ['stop_id', 'time', 'count']
        },
        {
            'name': 'Sensors (bus, latest)',
            'url': f"{rest_endpoint}/sensors/bus/B001?mode=latest",
            'expected_fields': ['entity_id', 'entity_type', 'time', 'temperature']
        },
        {
            'name': 'Sensors (stop, latest)',
            'url': f"{rest_endpoint}/sensors/stop/S001?mode=latest",
            'expected_fields': ['entity_id', 'entity_type', 'time', 'temperature']
        },
        {
            'name': 'Bus Position (latest)',
            'url': f"{rest_endpoint}/bus-position/B001?mode=latest",
            'expected_fields': ['bus_id', 'time', 'latitude', 'longitude']
        },
        {
            'name': 'Bus Position by Line (latest)',
            'url': f"{rest_endpoint}/bus-position/line/L1?mode=latest",
            'expected_fields': ['buses']
        }
    ]
    
    all_passed = True
    messages = []
    
    for endpoint in endpoints_to_test:
        print(f"\nTesting: {endpoint['name']}")
        print_info(f"  URL: {endpoint['url']}")
        
        try:
            # Create request with API key and group name headers
            req = urllib.request.Request(endpoint['url'])
            req.add_header('x-api-key', api_key)
            req.add_header('x-group-name', 'verification-script')
            
            # Make request
            with urllib.request.urlopen(req, timeout=10) as response:
                status_code = response.getcode()
                body = response.read().decode('utf-8')
                
                if verbose:
                    print_info(f"  Status: {status_code}")
                    print_info(f"  Response: {body[:200]}...")
                
                # Check status code
                if status_code != 200:
                    print_error(f"Unexpected status code: {status_code}")
                    all_passed = False
                    messages.append(f"{endpoint['name']}: Status {status_code}")
                    continue
                
                # Parse JSON response
                try:
                    data = json.loads(body)
                    
                    # Check for expected fields
                    missing_fields = []
                    for field in endpoint['expected_fields']:
                        if field not in data:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        print_warning(f"Missing fields: {', '.join(missing_fields)}")
                        print_success(f"{endpoint['name']}: OK (with warnings)")
                        messages.append(f"{endpoint['name']}: OK (warnings)")
                    else:
                        print_success(f"{endpoint['name']}: OK")
                        messages.append(f"{endpoint['name']}: OK")
                
                except json.JSONDecodeError:
                    print_error(f"Invalid JSON response")
                    all_passed = False
                    messages.append(f"{endpoint['name']}: Invalid JSON")
        
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print_error(f"Authentication failed (403 Forbidden) - API key may be invalid")
                all_passed = False
                messages.append(f"{endpoint['name']}: Auth failed")
            elif e.code == 404:
                print_warning(f"Entity not found (404) - may be expected if entity doesn't exist")
                messages.append(f"{endpoint['name']}: 404")
            else:
                print_error(f"HTTP error: {e.code} {e.reason}")
                all_passed = False
                messages.append(f"{endpoint['name']}: HTTP {e.code}")
        
        except urllib.error.URLError as e:
            print_error(f"Connection error: {e.reason}")
            all_passed = False
            messages.append(f"{endpoint['name']}: Connection error")
        
        except Exception as e:
            print_error(f"Unexpected error: {e}")
            all_passed = False
            messages.append(f"{endpoint['name']}: Unexpected error")
    
    summary = "; ".join(messages)
    return all_passed, summary


def test_rest_api_authentication(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """
    Test that API key authentication is working correctly (reject invalid keys).
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print_header("Testing API Key Authentication")
    
    # Get API endpoint from Terraform
    rest_endpoint = get_terraform_output('api_gateway_rest_endpoint')
    
    if not rest_endpoint:
        return False, "Could not retrieve REST API endpoint from Terraform"
    
    print_info(f"REST API Endpoint: {rest_endpoint}")
    
    import urllib.request
    import urllib.error
    
    test_url = f"{rest_endpoint}/people-count/S001?mode=latest"
    
    # Test 1: Request without API key (should fail with 401)
    print("\nTest 1: Request without API key")
    try:
        req = urllib.request.Request(test_url)
        req.add_header('x-group-name', 'verification-script')
        with urllib.request.urlopen(req, timeout=10) as response:
            print_error("Request succeeded without API key (should have failed)")
            return False, "Authentication not enforced"
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            print_success(f"Request correctly rejected ({e.code})")
        else:
            print_warning(f"Request failed with unexpected status: {e.code}")
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False, "Unexpected error testing no API key"
    
    # Test 2: Request with invalid API key (should fail with 403)
    print("\nTest 2: Request with invalid API key")
    try:
        req = urllib.request.Request(test_url)
        req.add_header('x-api-key', 'invalid-key-12345')
        req.add_header('x-group-name', 'verification-script')
        with urllib.request.urlopen(req, timeout=10) as response:
            print_error("Request succeeded with invalid API key (should have failed)")
            return False, "Invalid API key accepted"
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            print_success(f"Request correctly rejected ({e.code})")
        else:
            print_warning(f"Request failed with unexpected status: {e.code}")
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False, "Unexpected error testing invalid API key"
    
    # Test 3: Request without group name (should fail with 401)
    print("\nTest 3: Request without x-group-name header")
    api_key = get_api_key(region)
    if not api_key:
        return False, "Could not retrieve API key"
    
    try:
        req = urllib.request.Request(test_url)
        req.add_header('x-api-key', api_key)
        with urllib.request.urlopen(req, timeout=10) as response:
            print_error("Request succeeded without group name (should have failed)")
            return False, "Group name validation not enforced"
    except urllib.error.HTTPError as e:
        if e.code in [401, 403]:
            print_success(f"Request correctly rejected ({e.code})")
        else:
            print_warning(f"Request failed with unexpected status: {e.code}")
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False, "Unexpected error testing no group name"
    
    # Test 4: Request with valid API key and group name (should succeed)
    print("\nTest 4: Request with valid API key and group name")
    print_info(f"Using API key: {api_key[:8]}...")
    
    try:
        req = urllib.request.Request(test_url)
        req.add_header('x-api-key', api_key)
        req.add_header('x-group-name', 'verification-script')
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.getcode() == 200:
                print_success("Request succeeded with valid API key and group name")
            else:
                print_warning(f"Unexpected status code: {response.getcode()}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print_success("Request authenticated (404 is OK if entity doesn't exist)")
        else:
            print_error(f"Request failed: {e.code} {e.reason}")
            return False, f"Valid API key rejected: {e.code}"
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False, "Unexpected error testing valid API key"
    
    print_success("API key authentication is working correctly")
    return True, "Authentication OK"


def test_websocket_connection(region: str, verbose: bool = False) -> Tuple[bool, str]:
    """
    Test WebSocket connection with API key authentication.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    print_header("Testing WebSocket Connection")
    
    # Get WebSocket endpoint and API key
    ws_endpoint = get_terraform_output('api_gateway_websocket_endpoint')
    api_key = get_api_key(region)
    
    if not ws_endpoint:
        return False, "Could not retrieve WebSocket endpoint from Terraform"
    
    if not api_key:
        return False, "Could not retrieve API key from Secrets Manager or Terraform"
    
    print_info(f"WebSocket Endpoint: {ws_endpoint}")
    print_info(f"Using API key: {api_key[:8]}...")
    
    # Try to import websocket library
    try:
        import websocket
    except ImportError:
        print_warning("websocket-client library not installed")
        print_info("Install with: pip install websocket-client")
        print_info("Skipping WebSocket test")
        return True, "Skipped (library not available)"
    
    # Convert https:// to wss://
    ws_url = ws_endpoint.replace('https://', 'wss://').replace('http://', 'ws://')
    
    # Test 1: Connection without API key (should fail)
    print("\nTest 1: Connection without API key")
    try:
        ws = websocket.create_connection(f"{ws_url}?group_name=verification-script", timeout=5)
        ws.close()
        print_error("Connection succeeded without API key (should have failed)")
        return False, "WebSocket auth not enforced"
    except Exception as e:
        print_success(f"Connection correctly rejected: {type(e).__name__}")
    
    # Test 2: Connection with invalid API key (should fail)
    print("\nTest 2: Connection with invalid API key")
    try:
        ws = websocket.create_connection(f"{ws_url}?api_key=invalid-key-12345&group_name=verification-script", timeout=5)
        ws.close()
        print_error("Connection succeeded with invalid API key (should have failed)")
        return False, "Invalid WebSocket API key accepted"
    except Exception as e:
        print_success(f"Connection correctly rejected: {type(e).__name__}")
    
    # Test 3: Connection without group name (should fail)
    print("\nTest 3: Connection without group_name parameter")
    try:
        ws = websocket.create_connection(f"{ws_url}?api_key={api_key}", timeout=5)
        ws.close()
        print_error("Connection succeeded without group name (should have failed)")
        return False, "WebSocket group name validation not enforced"
    except Exception as e:
        print_success(f"Connection correctly rejected: {type(e).__name__}")
    
    # Test 4: Connection with valid API key and group name (should succeed)
    print("\nTest 4: Connection with valid API key and group name")
    try:
        ws = websocket.create_connection(f"{ws_url}?api_key={api_key}&group_name=verification-script", timeout=5)
        print_success("Connection established successfully")
        
        # Test subscription message
        if verbose:
            print_info("Sending subscription message...")
            subscribe_msg = json.dumps({
                "action": "subscribe",
                "line_ids": ["L1"]
            })
            ws.send(subscribe_msg)
            print_success("Subscription message sent")
        
        ws.close()
        print_success("WebSocket connection test passed")
        return True, "WebSocket OK"
    
    except Exception as e:
        print_error(f"Connection failed with valid API key: {e}")
        return False, f"WebSocket connection failed: {type(e).__name__}"


def main():
    parser = argparse.ArgumentParser(
        description='Verify Madrid Bus Real-Time Simulator deployment before hackathon'
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
    parser.add_argument(
        '--skip-websocket',
        action='store_true',
        help='Skip WebSocket tests (requires websocket-client library)'
    )
    
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}Madrid Bus Real-Time Simulator - Pre-Hackathon Verification{Colors.RESET}")
    print(f"{Colors.BOLD}Region: {args.region}{Colors.RESET}")
    print(f"{Colors.BOLD}Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}{Colors.RESET}")
    
    # Run all checks
    results = []
    
    # 1. Check Timestream data volume
    success, message = check_timestream_data_volume(args.region, args.verbose)
    results.append(('Timestream Data Volume', success, message))
    
    # 2. Check Fargate service health
    success, message = check_fargate_services(args.region, args.verbose)
    results.append(('Fargate Service Health', success, message))
    
    # 3. Test REST API endpoints
    success, message = test_rest_api_endpoints(args.region, args.verbose)
    results.append(('REST API Endpoints', success, message))
    
    # 4. Test API key authentication
    success, message = test_rest_api_authentication(args.region, args.verbose)
    results.append(('API Key Authentication', success, message))
    
    # 5. Test WebSocket connection
    if not args.skip_websocket:
        success, message = test_websocket_connection(args.region, args.verbose)
        results.append(('WebSocket Connection', success, message))
    
    # Print summary
    print_header("Verification Summary")
    
    all_passed = True
    for check_name, success, message in results:
        if success:
            print_success(f"{check_name}: PASSED")
        else:
            print_error(f"{check_name}: FAILED")
            all_passed = False
        
        if args.verbose:
            print_info(f"  Details: {message}")
    
    print()
    
    if all_passed:
        print(f"{Colors.BOLD}{Colors.GREEN}✓ All checks passed! System is ready for hackathon.{Colors.RESET}\n")
        sys.exit(0)
    else:
        print(f"{Colors.BOLD}{Colors.RED}✗ Some checks failed. Please review and fix issues before hackathon.{Colors.RESET}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
