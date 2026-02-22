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


def get_api_keys_from_terraform(region: str) -> List[Dict]:
    """
    Retrieve API keys from Terraform outputs.
    
    Returns:
        List of dictionaries with 'name' and 'key' fields
    """
    print("Retrieving API keys from Terraform outputs...")
    
    # Get API key values from Terraform
    api_key_values = get_terraform_output_json('api_key_values')
    
    # API keys are created with names like "participant-1", "participant-2", etc.
    keys_with_names = []
    for idx, key_value in enumerate(api_key_values, start=1):
        keys_with_names.append({
            'name': f'participant-{idx}',
            'key': key_value
        })
    
    print(f"✓ Retrieved {len(keys_with_names)} API keys")
    return keys_with_names


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


def generate_text_output(keys: List[Dict], endpoints: Dict[str, str]) -> str:
    """Generate text format output for API keys distribution."""
    output = []
    output.append("=" * 80)
    output.append("Madrid Bus Real-Time Simulator - API Keys for Hackathon Participants")
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
    
    # API Keys
    output.append("-" * 80)
    output.append("API KEYS")
    output.append("-" * 80)
    output.append("")
    for key_info in keys:
        output.append(f"{key_info['name']}: {key_info['key']}")
    output.append("")
    
    # Usage Instructions
    output.append("-" * 80)
    output.append("USAGE INSTRUCTIONS")
    output.append("-" * 80)
    output.append("")
    output.append("All API requests require authentication using your assigned API key.")
    output.append("Include the API key in the 'x-api-key' header for REST API requests.")
    output.append("For WebSocket connections, include the API key as a query parameter.")
    output.append("")
    
    # REST API Examples
    output.append("-" * 80)
    output.append("REST API EXAMPLES")
    output.append("-" * 80)
    output.append("")
    output.append("Replace YOUR_API_KEY with your assigned API key from above.")
    output.append("")
    
    rest_base = endpoints['rest']
    
    output.append("1. Get latest people count at a bus stop:")
    output.append(f"   curl -H 'x-api-key: YOUR_API_KEY' \\")
    output.append(f"        '{rest_base}/people-count/S001?mode=latest'")
    output.append("")
    
    output.append("2. Get historical people count at a specific time:")
    output.append(f"   curl -H 'x-api-key: YOUR_API_KEY' \\")
    output.append(f"        '{rest_base}/people-count/S001?timestamp=2024-01-15T10:30:00Z'")
    output.append("")
    
    output.append("3. Get latest sensor data for a bus:")
    output.append(f"   curl -H 'x-api-key: YOUR_API_KEY' \\")
    output.append(f"        '{rest_base}/sensors/bus/B001?mode=latest'")
    output.append("")
    
    output.append("4. Get latest sensor data for a stop:")
    output.append(f"   curl -H 'x-api-key: YOUR_API_KEY' \\")
    output.append(f"        '{rest_base}/sensors/stop/S001?mode=latest'")
    output.append("")
    
    output.append("5. Get latest bus position:")
    output.append(f"   curl -H 'x-api-key: YOUR_API_KEY' \\")
    output.append(f"        '{rest_base}/bus-position/B001?mode=latest'")
    output.append("")
    
    output.append("6. Get all buses on a line:")
    output.append(f"   curl -H 'x-api-key: YOUR_API_KEY' \\")
    output.append(f"        '{rest_base}/bus-position/line/L1?mode=latest'")
    output.append("")
    
    # WebSocket Examples
    output.append("-" * 80)
    output.append("WEBSOCKET EXAMPLES")
    output.append("-" * 80)
    output.append("")
    output.append("Connect to the WebSocket API for real-time bus position updates.")
    output.append("Include your API key as a query parameter in the connection URL.")
    output.append("")
    
    ws_base = endpoints['websocket'].replace('https://', 'wss://')
    
    output.append("1. Connect using wscat (Node.js):")
    output.append(f"   wscat -c '{ws_base}?api_key=YOUR_API_KEY'")
    output.append("")
    
    output.append("2. Subscribe to specific bus lines:")
    output.append('   Send message: {"action": "subscribe", "line_ids": ["L1", "L2"]}')
    output.append("")
    
    output.append("3. Python example:")
    output.append("   import websocket")
    output.append("   import json")
    output.append("")
    output.append(f"   ws_url = '{ws_base}?api_key=YOUR_API_KEY'")
    output.append("   ws = websocket.create_connection(ws_url)")
    output.append('   ws.send(json.dumps({"action": "subscribe", "line_ids": ["L1"]}))')
    output.append("   ")
    output.append("   while True:")
    output.append("       result = ws.recv()")
    output.append("       print(result)")
    output.append("")
    
    # Rate Limits
    output.append("-" * 80)
    output.append("RATE LIMITS")
    output.append("-" * 80)
    output.append("")
    output.append("Each API key has the following limits:")
    output.append("  - 50 requests per second (burst: 100)")
    output.append("  - 10,000 requests per day")
    output.append("")
    output.append("If you exceed these limits, you will receive a 429 Too Many Requests error.")
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


def generate_json_output(keys: List[Dict], endpoints: Dict[str, str]) -> str:
    """Generate JSON format output for API keys distribution."""
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "rest_api": endpoints['rest'],
            "websocket_api": endpoints['websocket']
        },
        "api_keys": [
            {
                "participant": key_info['name'],
                "api_key": key_info['key']
            }
            for key_info in keys
        ],
        "rate_limits": {
            "requests_per_second": 50,
            "burst_limit": 100,
            "requests_per_day": 10000
        },
        "usage_examples": {
            "rest_api": {
                "latest_people_count": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/people-count/{{stop_id}}?mode=latest",
                    "headers": {
                        "x-api-key": "YOUR_API_KEY"
                    }
                },
                "historical_people_count": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/people-count/{{stop_id}}?timestamp={{ISO8601_TIMESTAMP}}",
                    "headers": {
                        "x-api-key": "YOUR_API_KEY"
                    }
                },
                "latest_sensor_data": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/sensors/{{entity_type}}/{{entity_id}}?mode=latest",
                    "headers": {
                        "x-api-key": "YOUR_API_KEY"
                    }
                },
                "latest_bus_position": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/bus-position/{{bus_id}}?mode=latest",
                    "headers": {
                        "x-api-key": "YOUR_API_KEY"
                    }
                },
                "line_buses": {
                    "method": "GET",
                    "url": f"{endpoints['rest']}/bus-position/line/{{line_id}}?mode=latest",
                    "headers": {
                        "x-api-key": "YOUR_API_KEY"
                    }
                }
            },
            "websocket": {
                "connection_url": f"{endpoints['websocket'].replace('https://', 'wss://')}?api_key=YOUR_API_KEY",
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
        description='Export API keys for Madrid Bus Real-Time Simulator hackathon participants'
    )
    parser.add_argument(
        '--region',
        required=True,
        help='AWS region where the infrastructure is deployed'
    )
    parser.add_argument(
        '--output',
        default='api_keys.txt',
        help='Output file for API keys (default: api_keys.txt)'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format: text or json (default: text)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Madrid Bus Real-Time Simulator - API Key Export")
    print("=" * 80)
    print("")
    
    # Get API keys from Terraform
    keys = get_api_keys_from_terraform(args.region)
    
    # Get API endpoints
    endpoints = get_api_endpoints(args.region)
    
    # Generate output
    print(f"\nGenerating {args.format.upper()} output...")
    if args.format == 'json':
        content = generate_json_output(keys, endpoints)
    else:
        content = generate_text_output(keys, endpoints)
    
    # Save to file
    save_to_file(content, args.output)
    
    print("\n✓ Export completed successfully!")
    print(f"  - {len(keys)} API keys exported")
    print(f"  - Format: {args.format.upper()}")
    print(f"  - Output file: {args.output}")
    print("")
    print("Distribute this file to hackathon participants securely.")
    print("")


if __name__ == '__main__':
    main()
