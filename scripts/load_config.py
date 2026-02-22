#!/usr/bin/env python3
"""
Configuration loading script for Madrid Bus Real-Time Simulator.

This script loads the bus lines configuration from YAML and uploads it to S3
for Fargate services to access. It also stores route waypoints for Amazon Location usage.

Usage:
    python load_config.py --file data/lines.yaml --region eu-west-1
"""

import argparse
import sys
import json
import yaml
import boto3
from typing import Dict, List
from pathlib import Path


def load_lines_config(file_path: str) -> Dict:
    """Load bus lines configuration from YAML file."""
    print(f"Loading configuration from {file_path}...")
    
    with open(file_path, 'r') as f:
        config = yaml.safe_load(f)
    
    print(f"Loaded {len(config.get('lines', []))} bus lines")
    return config


def get_terraform_output(output_name: str, terraform_dir: str = "terraform") -> str:
    """Get Terraform output value."""
    import subprocess
    
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


def upload_to_s3(config: Dict, bucket: str, region: str):
    """Upload configuration to S3 for Fargate services to access."""
    print(f"Uploading configuration to S3 bucket: {bucket}")
    
    s3_client = boto3.client('s3', region_name=region)
    
    # Upload YAML configuration
    yaml_content = yaml.dump(config)
    s3_client.put_object(
        Bucket=bucket,
        Key='config/lines.yaml',
        Body=yaml_content,
        ContentType='application/x-yaml'
    )
    
    print(f"✓ Configuration uploaded to s3://{bucket}/config/lines.yaml")


def store_route_waypoints(config: Dict, bucket: str, region: str):
    """Store route waypoints for Amazon Location usage."""
    print("Storing route waypoints...")
    
    s3_client = boto3.client('s3', region_name=region)
    
    routes_data = {}
    
    for line in config.get('lines', []):
        line_id = line['line_id']
        waypoints = []
        
        for stop in line.get('stops', []):
            waypoints.append({
                'stop_id': stop['stop_id'],
                'name': stop['name'],
                'latitude': stop['latitude'],
                'longitude': stop['longitude'],
                'is_terminal': stop.get('is_terminal', False)
            })
        
        routes_data[line_id] = {
            'line_name': line['name'],
            'waypoints': waypoints
        }
    
    # Upload routes data as JSON
    routes_json = json.dumps(routes_data, indent=2)
    s3_client.put_object(
        Bucket=bucket,
        Key='config/routes.json',
        Body=routes_json,
        ContentType='application/json'
    )
    
    print(f"✓ Route waypoints stored to s3://{bucket}/config/routes.json")


def main():
    parser = argparse.ArgumentParser(
        description='Load configuration data for Madrid Bus Real-Time Simulator'
    )
    parser.add_argument(
        '--file',
        required=True,
        help='Path to lines.yaml configuration file'
    )
    parser.add_argument(
        '--region',
        required=True,
        help='AWS region'
    )
    parser.add_argument(
        '--bucket',
        help='S3 bucket name (if not provided, will get from Terraform output)'
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    if not Path(args.file).exists():
        print(f"Error: Configuration file not found: {args.file}")
        sys.exit(1)
    
    # Load configuration
    config = load_lines_config(args.file)
    
    # Get S3 bucket name
    if args.bucket:
        bucket_name = args.bucket
    else:
        print("Getting S3 bucket name from Terraform outputs...")
        bucket_name = get_terraform_output('config_bucket_name')
    
    print(f"Using S3 bucket: {bucket_name}")
    
    # Upload configuration
    upload_to_s3(config, bucket_name, args.region)
    
    # Store route waypoints
    store_route_waypoints(config, bucket_name, args.region)
    
    print("\n✓ Configuration loading completed successfully!")
    print(f"  - {len(config.get('lines', []))} bus lines")
    print(f"  - Configuration uploaded to S3")
    print(f"  - Route waypoints stored")


if __name__ == '__main__':
    main()