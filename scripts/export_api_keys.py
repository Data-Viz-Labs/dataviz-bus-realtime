#!/usr/bin/env python3
"""
API Key Export Script for Madrid Bus Real-Time Simulator.

This script retrieves API keys from API Gateway and generates a participant
distribution file with usage instructions and example commands.

Usage:
    python export_api_keys.py --region eu-west-1 --output api_keys.txt
    python export_api_keys.py --region eu-west-1 --output api_keys.json --format json
"""

import argparse
import sys
import json
import subprocess
from typing import List, Dict, Optional
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError


def get_terraform_output(output_name: str, terraform_dir: str = "terraform") -> str:
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
    except subprocess.CalledProcessError as e:
        print(f"Error getting Terraform output '{output_name}': {e.stderr}")
        sys.exit(1)


def get_terraform_output_json(output_name: str, terraform_dir: str = "terraform") -> any:
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
    except subprocess.CalledProcessError as e:
        print(f"Error getting Terraform output '{output_name}': {e.stderr}")
        sys.exit(1)


def get_api_key_from_secrets_manager(region: str, secret_id: str = 'bus-simulator/api-key') -> str:
    """
    Retrieve API key from AWS Secrets Manager.
    
    Args:
        region: AWS region
        secret_id: Secrets Manager secret ID
        
    Returns:
        API key value
    """
    print(f"Retrieving API key from Secrets Manager (secret: {secret_id})...")
    
    try:
        client = boto3.client('secretsmanager', region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        secret_data = json.loads(response['SecretString'])
        api_key = secret_data['api_key']
        
        print(f"✓ Retrieved API key from Secrets Manager")
        return api_key
    except ClientError as e:
        print(f"Error retrieving API key from Secrets Manager: {e}")
        sys.exit(1)


def get_api_key_from_terraform(region: str) -> str:
    """
    Retrieve API key from Terraform outputs (alternative method).
    
    Returns:
        API key value
    """
    print("Retrieving API key from Terraform outputs...")
    
    try:
        api_key = get_terraform_output('api_key_value')
        print(f"✓ Retrieved API key from Terraform")
        return api_key
    except Exception as e:
        print(f"Warning: Could not retrieve API key from Terraform: {e}")
        print("Falling back to Secrets Manager...")
        return None


def get_api_endpoints(region: str) -> Dict[str, str]:
    """
    Get API Gateway endpoints from Terraform outputs.
    
    Returns:
        Dictionary with 'rest' and 'websocket' endpoint URLs
    """
    print("Retrieving API endpoints from Terraform outputs...")
    
    rest_endpoint = get_terraform_output('api_gateway_rest_endpoint')
    websocket_endpoint = get_terraform_output('api_gateway_websocket_endpoint')
    
    print(f"✓ REST API endpoint: {rest_endpoint}")
    print(f"✓ WebSocket endpoint: {websocket_endpoint}")
    
    return {
        'rest': rest_endpoint,
        'websocket': websocket_endpoint
    }


def generate_text_output(api_key: str, endpoints: Dict[str, str]) -> str:
    """Generate text format output for API key distribution."""
    output = []
    output.append("=" * 80)
    output.append("Madrid Bus Real-Time Simulator - API Key for Hackathon Participants")
    output.append("=" * 80)
    output.append("")
    output.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    output.append("")
    
    # API Endpoints
    output.append("-" * 80)
    output.append("API ENDPOINTS")
    output.append("-" * 80)
    output.append("")
    output.append(f"REST API:      {endpoints['rest']}")
    output.append(f"WebSocket API: {endpoints['websocket']}")
    output.append("")
    
    # API Key
    output.append("-" * 80)
    output.append("API KEY")
    output.append("-" * 80)
    output.append("")
    output.append(f"API Key: {api_key}")
    output.append("")
    output.append("IMPORTANT: This is a shared API key for all hackathon participants.")
    output.append("Please use it responsibly and do not share it publicly.")
    output.append("")
    
    # Usage Instructions
    output.append("-" * 80)
    output.append("USAGE INSTRUCTIONS")
    output.append("-" * 80)
    output.append("")
    output.append("All API requests require authentication using the API key above.")
    output.append("")
    output.append("REST API:")
    output.append("  - Include 'x-api-key' header with the API key")
    output.append("  - Include 'x-group-name' header with your team name")
    output.append("")
    output.append("WebSocket API:")
    output.append("  - Include 'api_key' query parameter with the API key")
    output.append("  - Include 'group_name' query parameter with your team name")
    output.append("")
    
    # REST API Examples
    output.append("-" * 80)
    output.append("REST API EXAMPLES")
    output.append("-" * 80)
    output.append("")
    
    rest_base = endpoints['rest']
    
    output.append("1. Get latest people count at a bus stop:")
    output.append(f"   curl -H 'x-api-key: {api_key}' \\")
    output.append(f"        -H 'x-group-name: YOUR_TEAM_NAME' \\")
    output.append(f"        '{rest_base}/people-count/S001?mode=latest'")
    output.append("")
    
    output.append("2. Get historical people count at a specific time:")
    output.append(f"   curl -H 'x-api-key: {api_key}' \\")
    output.append(f"        -H 'x-group-name: YOUR_TEAM_NAME' \\")
    output.append(f"        '{rest_base}/people-count/S001?timestamp=2024-01-15T10:30:00Z'")
    output.append("")
    
    output.append("3. Get latest sensor data for a bus:")
    output.append(f"   curl -H 'x-api-key: {api_key}' \\")
    output.append(f"        -H 'x-group-name: YOUR_TEAM_NAME' \\")
    output.append(f"        '{rest_base}/sensors/bus/B001?mode=latest'")
    output.append("")
    
    output.append("4. Get latest sensor data for a stop:")
    output.append(f"   curl -H 'x-api-key: {api_key}' \\")
    output.append(f"        -H 'x-group-name: YOUR_TEAM_NAME' \\")
    output.append(f"        '{rest_base}/sensors/stop/S001?mode=latest'")
    output.append("")
    
    output.append("5. Get latest bus position:")
    output.append(f"   curl -H 'x-api-key: {api_key}' \\")
    output.append(f"        -H 'x-group-name: YOUR_TEAM_NAME' \\")
    output.append(f"        '{rest_base}/bus-position/B001?mode=latest'")
    output.append("")
    
    output.append("6. Get all buses on a line:")
    output.append(f"   curl -H 'x-api-key: {api_key}' \\")
    output.append(f"        -H 'x-group-name: YOUR_TEAM_NAME' \\")
    output.append(f"        '{rest_base}/bus-position/line/L1?mode=latest'")
    output.append("")
    
    # WebSocket Examples
    output.append("-" * 80)
    output.append("WEBSOCKET EXAMPLES")
    output.append("-" * 80)
    output.append("")
    output.append("Connect to the WebSocket API for real-time bus position updates.")
    output.append("Include the API key and your team name as query parameters.")
    output.append("")
    
    ws_base = endpoints['websocket'].replace('https://', 'wss://')
    
    output.append("1. Connect using wscat (Node.js):")
    output.append(f"   wscat -c '{ws_base}?api_key={api_key}&group_name=YOUR_TEAM_NAME'")
    output.append("")
    
    output.append("2. Subscribe to specific bus lines:")
    output.append('   Send message: {"action": "subscribe", "line_ids": ["L1", "L2"]}')
    output.append("")
    
    output.append("3. Python example:")
    output.append("   import websocket")
    output.append("   import json")
    output.append("")
    output.append(f"   ws_url = '{ws_base}?api_key={api_key}&group_name=YOUR_TEAM_NAME'")
    output.append("   ws = websocket.create_connection(ws_url)")
    output.append('   ws.send(json.dumps({"action": "subscribe", "line_ids": ["L1"]}))')
    output.append("   ")
    output.append("   while True:")
    output.append("       result = ws.recv()")
    output.append("       print(result)")
    output.append("")
    
    # Additional Information
    output.append("-" * 80)
    output.append("ADDITIONAL INFORMATION")
    output.append("-" * 80)
    output.append("")
    output.append("For complete API documentation, see:")
    output.append("  https://github.com/your-repo/docs/API_DOCUMENTATION.md")
    output.append("")
    output.append("For support during the hackathon, contact:")
    output.append("  Email: support@example.com")
    output.append("  Slack: #bus-simulator-support")
    output.append("")
    output.append("=" * 80)
    
    return "\n".join(output)


def generate_json_output(api_key: str, endpoints: Dict[str, str]) -> str:
    """Generate JSON format output for API key distribution."""
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "rest_api": endpoints['rest'],
            "websocket_api": endpoints['websocket']
        },
        "api_key": api_key,
        "usage_instructions": {
            "rest_api": {
                "headers": {
                    "x-api-key": api_key,
                    "x-group-name": "YOUR_TEAM_NAME"
                }
            },
            "websocket": {
                "query_parameters": {
                    "api_key": api_key,
                    "group_name": "YOUR_TEAM_NAME"
                }
            }
        },
        "usage_examples": {
            "rest_api": {
                "latest_people_count": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/people-count/{{stop_id}}?mode=latest",
                    "headers": {
                        "x-api-key": api_key,
                        "x-group-name": "YOUR_TEAM_NAME"
                    }
                },
                "historical_people_count": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/people-count/{{stop_id}}?timestamp={{ISO8601_TIMESTAMP}}",
                    "headers": {
                        "x-api-key": api_key,
                        "x-group-name": "YOUR_TEAM_NAME"
                    }
                },
                "latest_sensor_data": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/sensors/{{entity_type}}/{{entity_id}}?mode=latest",
                    "headers": {
                        "x-api-key": api_key,
                        "x-group-name": "YOUR_TEAM_NAME"
                    }
                },
                "latest_bus_position": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/bus-position/{{bus_id}}?mode=latest",
                    "headers": {
                        "x-api-key": api_key,
                        "x-group-name": "YOUR_TEAM_NAME"
                    }
                },
                "line_buses": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/bus-position/line/{{line_id}}?mode=latest",
                    "headers": {
                        "x-api-key": api_key,
                        "x-group-name": "YOUR_TEAM_NAME"
                    }
                }
            },
            "websocket": {
                "connection_url": f"{endpoints['websocket'].replace('https://', 'wss://')}?api_key={api_key}&group_name=YOUR_TEAM_NAME",
                "subscribe_message": {
                    "action": "subscribe",
                    "line_ids": ["L1", "L2"]
                }
            }
        }
    }
    
    return json.dumps(data, indent=2)


def save_to_file(content: str, filename: str):
    """Save content to a file."""
    with open(filename, 'w') as f:
        f.write(content)
    print(f"\n✓ API keys exported to: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description='Export API key for Madrid Bus Real-Time Simulator hackathon participants'
    )
    parser.add_argument(
        '--region',
        required=True,
        help='AWS region where the infrastructure is deployed'
    )
    parser.add_argument(
        '--output',
        default='api_keys.txt',
        help='Output file for API key (default: api_keys.txt)'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format: text or json (default: text)'
    )
    parser.add_argument(
        '--secret-id',
        default='bus-simulator/api-key',
        help='Secrets Manager secret ID (default: bus-simulator/api-key)'
    )
    parser.add_argument(
        '--use-terraform',
        action='store_true',
        help='Try to get API key from Terraform outputs first'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Madrid Bus Real-Time Simulator - API Key Export")
    print("=" * 80)
    print("")
    
    # Get API key
    api_key = None
    if args.use_terraform:
        api_key = get_api_key_from_terraform(args.region)
    
    if not api_key:
        api_key = get_api_key_from_secrets_manager(args.region, args.secret_id)
    
    # Get API endpoints
    endpoints = get_api_endpoints(args.region)
    
    # Generate output
    print(f"\nGenerating {args.format.upper()} output...")
    if args.format == 'json':
        content = generate_json_output(api_key, endpoints)
    else:
        content = generate_text_output(api_key, endpoints)
    
    # Save to file
    save_to_file(content, args.output)
    
    print("\n✓ Export completed successfully!")
    print(f"  - Format: {args.format.upper()}")
    print(f"  - Output file: {args.output}")
    print("")
    print("Distribute this file to hackathon participants securely.")
    print("")


if __name__ == '__main__':
    main()
