"""
Lambda authorizer for WebSocket API connections.

This module provides custom authorization for WebSocket connections by validating
API keys passed as query parameters. The authorizer checks the API key against
valid keys managed by API Gateway and returns an IAM policy allowing or denying
the connection.

Requirements: 3.7
"""

import json
import logging
import os
from typing import Dict, Any

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
AWS_REGION = os.environ.get('AWS_REGION', 'eu-west-1')
API_GATEWAY_ID = os.environ.get('API_GATEWAY_ID', '')

# Initialize AWS clients
apigateway_client = boto3.client('apigatewayv2', region_name=AWS_REGION)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Authorize WebSocket connection based on API key.
    
    This authorizer is invoked when a client attempts to connect to the WebSocket API.
    It validates the API key provided in the query string parameter and returns an
    IAM policy document that either allows or denies the connection.
    
    Args:
        event: API Gateway authorizer event containing connection details
        context: Lambda context object
    
    Returns:
        IAM policy document allowing or denying the connection
    
    Example event:
        {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:region:account:api-id/stage/$connect',
            'requestContext': {
                'connectionId': 'abc123',
                'apiId': 'api-id',
                'stage': 'production'
            },
            'queryStringParameters': {
                'api_key': 'user-provided-api-key'
            }
        }
    
    Example response (allow):
        {
            'principalId': 'user',
            'policyDocument': {
                'Version': '2012-10-17',
                'Statement': [{
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Allow',
                    'Resource': 'arn:aws:execute-api:region:account:api-id/stage/$connect'
                }]
            }
        }
    """
    try:
        # Extract API key from query parameters
        query_params = event.get('queryStringParameters') or {}
        api_key = query_params.get('api_key', '')
        
        # Extract method ARN for policy generation
        method_arn = event.get('methodArn', '')
        
        # Log authorization attempt
        logger.info(f"Authorization attempt for WebSocket connection")
        logger.debug(f"Method ARN: {method_arn}")
        
        if not api_key:
            logger.warning("Authorization failed: No API key provided")
            return generate_policy('user', 'Deny', method_arn)
        
        # Validate API key
        is_valid = validate_api_key(api_key)
        
        if is_valid:
            logger.info("Authorization successful: Valid API key")
            return generate_policy('user', 'Allow', method_arn)
        else:
            logger.warning("Authorization failed: Invalid API key")
            return generate_policy('user', 'Deny', method_arn)
    
    except Exception as e:
        logger.error(f"Error in authorizer: {str(e)}", exc_info=True)
        # Deny access on error for security
        return generate_policy('user', 'Deny', event.get('methodArn', '*'))


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key against API Gateway.
    
    This function checks if the provided API key exists and is enabled in
    API Gateway. It queries the API Gateway service to verify the key's validity.
    
    Args:
        api_key: The API key to validate
    
    Returns:
        True if the API key is valid and enabled, False otherwise
    """
    try:
        # Get all API keys from API Gateway
        response = apigateway_client.get_api_keys()
        
        api_keys = response.get('Items', [])
        
        # Check if the provided key matches any valid API key
        for key_info in api_keys:
            # Get the actual key value
            try:
                key_response = apigateway_client.get_api_key(
                    ApiKey=key_info['ApiKeyId']
                )
                
                # Check if key matches and is enabled
                if key_response.get('Value') == api_key and key_response.get('Enabled', False):
                    logger.info(f"Valid API key found: {key_info.get('Name', 'unknown')}")
                    return True
            
            except ClientError as e:
                logger.warning(f"Error retrieving API key details: {str(e)}")
                continue
        
        logger.warning("API key not found or disabled")
        return False
    
    except ClientError as e:
        logger.error(f"Error validating API key: {str(e)}")
        return False
    
    except Exception as e:
        logger.error(f"Unexpected error validating API key: {str(e)}")
        return False


def generate_policy(principal_id: str, effect: str, resource: str) -> Dict[str, Any]:
    """
    Generate IAM policy document for API Gateway.
    
    Creates a policy document that either allows or denies access to the
    WebSocket API based on the authorization result.
    
    Args:
        principal_id: Identifier for the principal (user)
        effect: 'Allow' or 'Deny'
        resource: The method ARN to apply the policy to
    
    Returns:
        IAM policy document in API Gateway authorizer format
    """
    policy_document = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }
        ]
    }
    
    auth_response = {
        'principalId': principal_id,
        'policyDocument': policy_document
    }
    
    logger.debug(f"Generated policy: {json.dumps(auth_response)}")
    
    return auth_response
