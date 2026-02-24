"""
REST API Custom Authorizer for Madrid Bus Simulator
Validates API key from x-api-key header against Secrets Manager
Validates presence of x-group-name header
Returns IAM policy allowing or denying the request
"""

import json
import os
import boto3
from typing import Dict, Any

# Initialize Secrets Manager client
secrets_client = boto3.client('secretsmanager')

# Get secret ID from environment variable
SECRET_ID = os.environ.get('SECRET_ID', 'bus-simulator/api-key')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Custom authorizer for REST API Gateway.
    Validates API key from x-api-key header against Secrets Manager.
    Validates presence of x-group-name header.
    Returns IAM policy allowing or denying the request.
    
    Args:
        event: API Gateway authorizer event
        context: Lambda context
        
    Returns:
        IAM policy document allowing or denying the request
    """
    print(f"Authorizer event: {json.dumps(event)}")
    
    # Extract headers (case-insensitive)
    headers = event.get('headers', {})
    
    # Normalize header keys to lowercase for case-insensitive lookup
    headers_lower = {k.lower(): v for k, v in headers.items()}
    
    api_key = headers_lower.get('x-api-key', '')
    group_name = headers_lower.get('x-group-name', '')
    
    # Get method ARN for policy generation
    method_arn = event['methodArn']
    
    # Validate x-group-name header presence
    if not group_name:
        print("Missing x-group-name header")
        raise Exception('Unauthorized: Missing x-group-name header')
    
    # Retrieve API key from Secrets Manager
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_ID)
        secret_data = json.loads(response['SecretString'])
        stored_api_key = secret_data['api_key']
    except Exception as e:
        print(f"Error retrieving API key from Secrets Manager: {e}")
        raise Exception('Unauthorized: Internal error')
    
    # Validate API key
    if api_key != stored_api_key:
        print(f"Invalid API key provided")
        raise Exception('Unauthorized: Invalid API key')
    
    print(f"Authorization successful for group: {group_name}")
    
    # Generate IAM policy allowing the request
    policy = generate_policy('user', 'Allow', method_arn, group_name)
    return policy


def generate_policy(principal_id: str, effect: str, resource: str, group_name: str) -> Dict[str, Any]:
    """
    Generate IAM policy for API Gateway.
    Include group_name in context for downstream Lambda functions.
    
    The policy allows access to all resources in the API (using wildcard)
    to support caching across different endpoints.
    
    Args:
        principal_id: Principal identifier
        effect: Allow or Deny
        resource: Method ARN (used to extract API ARN)
        group_name: Group name from header
        
    Returns:
        IAM policy document
    """
    # Extract the API ARN and create a wildcard resource
    # resource format: arn:aws:execute-api:region:account:api-id/stage/method/path
    # We want: arn:aws:execute-api:region:account:api-id/*
    resource_parts = resource.split('/')
    api_arn = '/'.join(resource_parts[:2]) + '/*'
    
    auth_response = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': api_arn
            }]
        },
        'context': {
            'group_name': group_name
        }
    }
    
    return auth_response
