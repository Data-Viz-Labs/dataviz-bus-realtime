"""
Unit tests for the WebSocket Authorizer Lambda function.

Tests the custom authorizer for WebSocket API connections, including API key
validation and IAM policy generation.

Requirements: 3.7
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Import the Lambda authorizer module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.websocket_authorizer import (
    lambda_handler,
    validate_api_key,
    generate_policy
)


class TestLambdaHandler:
    """Test the main Lambda authorizer handler function."""
    
    @patch('lambdas.websocket_authorizer.validate_api_key')
    def test_valid_api_key_acceptance(self, mock_validate):
        """Test that valid API key results in Allow policy."""
        mock_validate.return_value = True
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'abc123',
                'apiId': 'api123',
                'stage': 'production'
            },
            'queryStringParameters': {
                'api_key': 'valid-api-key-12345'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        assert response['policyDocument']['Version'] == '2012-10-17'
        assert len(response['policyDocument']['Statement']) == 1
        
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Allow'
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Resource'] == event['methodArn']
        
        mock_validate.assert_called_once_with('valid-api-key-12345')
    
    @patch('lambdas.websocket_authorizer.validate_api_key')
    def test_invalid_api_key_rejection(self, mock_validate):
        """Test that invalid API key results in Deny policy."""
        mock_validate.return_value = False
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'abc123',
                'apiId': 'api123',
                'stage': 'production'
            },
            'queryStringParameters': {
                'api_key': 'invalid-api-key'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
        
        mock_validate.assert_called_once_with('invalid-api-key')
    
    def test_missing_api_key_handling(self):
        """Test that missing API key results in Deny policy."""
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'abc123',
                'apiId': 'api123',
                'stage': 'production'
            },
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
    
    def test_null_query_parameters(self):
        """Test handling when queryStringParameters is None."""
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'abc123'
            },
            'queryStringParameters': None
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
    
    def test_empty_api_key(self):
        """Test that empty API key string results in Deny policy."""
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'abc123'
            },
            'queryStringParameters': {
                'api_key': ''
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
    
    @patch('lambdas.websocket_authorizer.validate_api_key')
    def test_exception_handling(self, mock_validate):
        """Test that exceptions result in Deny policy for security."""
        mock_validate.side_effect = Exception("Unexpected error")
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'abc123'
            },
            'queryStringParameters': {
                'api_key': 'some-key'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
    
    def test_missing_method_arn(self):
        """Test handling when methodArn is missing."""
        event = {
            'type': 'REQUEST',
            'requestContext': {
                'connectionId': 'abc123'
            },
            'queryStringParameters': {
                'api_key': 'some-key'
            }
        }
        
        response = lambda_handler(event, None)
        
        # Should still return a policy, even with wildcard resource
        assert 'policyDocument' in response
        assert response['principalId'] == 'user'


class TestValidateApiKey:
    """Test API key validation logic."""
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_valid_enabled_api_key(self, mock_client):
        """Test validation of a valid and enabled API key."""
        # Mock get_api_keys response
        mock_client.get_api_keys.return_value = {
            'Items': [
                {
                    'ApiKeyId': 'key123',
                    'Name': 'participant-1'
                }
            ]
        }
        
        # Mock get_api_key response
        mock_client.get_api_key.return_value = {
            'ApiKeyId': 'key123',
            'Value': 'valid-api-key-12345',
            'Enabled': True,
            'Name': 'participant-1'
        }
        
        result = validate_api_key('valid-api-key-12345')
        
        assert result is True
        mock_client.get_api_keys.assert_called_once()
        mock_client.get_api_key.assert_called_once_with(ApiKey='key123')
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_disabled_api_key(self, mock_client):
        """Test that disabled API key is rejected."""
        mock_client.get_api_keys.return_value = {
            'Items': [
                {
                    'ApiKeyId': 'key123',
                    'Name': 'participant-1'
                }
            ]
        }
        
        # API key exists but is disabled
        mock_client.get_api_key.return_value = {
            'ApiKeyId': 'key123',
            'Value': 'disabled-api-key',
            'Enabled': False,
            'Name': 'participant-1'
        }
        
        result = validate_api_key('disabled-api-key')
        
        assert result is False
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_nonexistent_api_key(self, mock_client):
        """Test that non-existent API key is rejected."""
        mock_client.get_api_keys.return_value = {
            'Items': [
                {
                    'ApiKeyId': 'key123',
                    'Name': 'participant-1'
                }
            ]
        }
        
        # API key value doesn't match
        mock_client.get_api_key.return_value = {
            'ApiKeyId': 'key123',
            'Value': 'different-key',
            'Enabled': True,
            'Name': 'participant-1'
        }
        
        result = validate_api_key('nonexistent-key')
        
        assert result is False
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_multiple_api_keys_match_found(self, mock_client):
        """Test validation with multiple API keys, finding a match."""
        mock_client.get_api_keys.return_value = {
            'Items': [
                {'ApiKeyId': 'key1', 'Name': 'participant-1'},
                {'ApiKeyId': 'key2', 'Name': 'participant-2'},
                {'ApiKeyId': 'key3', 'Name': 'participant-3'}
            ]
        }
        
        # Mock get_api_key to return different values
        def get_api_key_side_effect(ApiKey):
            if ApiKey == 'key1':
                return {'Value': 'key-value-1', 'Enabled': True}
            elif ApiKey == 'key2':
                return {'Value': 'target-key-value', 'Enabled': True}
            elif ApiKey == 'key3':
                return {'Value': 'key-value-3', 'Enabled': True}
        
        mock_client.get_api_key.side_effect = get_api_key_side_effect
        
        result = validate_api_key('target-key-value')
        
        assert result is True
        # Should have called get_api_key at least twice (until match found)
        assert mock_client.get_api_key.call_count >= 2
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_empty_api_keys_list(self, mock_client):
        """Test validation when no API keys exist."""
        mock_client.get_api_keys.return_value = {
            'Items': []
        }
        
        result = validate_api_key('any-key')
        
        assert result is False
        mock_client.get_api_key.assert_not_called()
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_get_api_keys_client_error(self, mock_client):
        """Test handling of ClientError when getting API keys."""
        mock_client.get_api_keys.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetApiKeys'
        )
        
        result = validate_api_key('any-key')
        
        assert result is False
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_get_api_key_client_error(self, mock_client):
        """Test handling of ClientError when getting individual API key."""
        mock_client.get_api_keys.return_value = {
            'Items': [
                {'ApiKeyId': 'key1', 'Name': 'participant-1'},
                {'ApiKeyId': 'key2', 'Name': 'participant-2'}
            ]
        }
        
        # First call fails, second succeeds
        def get_api_key_side_effect(ApiKey):
            if ApiKey == 'key1':
                raise ClientError(
                    {'Error': {'Code': 'NotFoundException', 'Message': 'Not found'}},
                    'GetApiKey'
                )
            elif ApiKey == 'key2':
                return {'Value': 'valid-key', 'Enabled': True}
        
        mock_client.get_api_key.side_effect = get_api_key_side_effect
        
        result = validate_api_key('valid-key')
        
        # Should continue checking other keys after error
        assert result is True
        assert mock_client.get_api_key.call_count == 2
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_unexpected_exception(self, mock_client):
        """Test handling of unexpected exceptions."""
        mock_client.get_api_keys.side_effect = Exception("Unexpected error")
        
        result = validate_api_key('any-key')
        
        assert result is False
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_api_key_missing_enabled_field(self, mock_client):
        """Test handling when API key response is missing Enabled field."""
        mock_client.get_api_keys.return_value = {
            'Items': [
                {'ApiKeyId': 'key123', 'Name': 'participant-1'}
            ]
        }
        
        # Response missing 'Enabled' field (defaults to False)
        mock_client.get_api_key.return_value = {
            'ApiKeyId': 'key123',
            'Value': 'test-key'
            # Missing 'Enabled' field
        }
        
        result = validate_api_key('test-key')
        
        # Should be rejected because Enabled defaults to False
        assert result is False


class TestGeneratePolicy:
    """Test IAM policy generation."""
    
    def test_generate_allow_policy(self):
        """Test generation of Allow policy."""
        policy = generate_policy(
            'user123',
            'Allow',
            'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect'
        )
        
        assert policy['principalId'] == 'user123'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1
        
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Effect'] == 'Allow'
        assert statement['Resource'] == 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect'
    
    def test_generate_deny_policy(self):
        """Test generation of Deny policy."""
        policy = generate_policy(
            'user456',
            'Deny',
            'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect'
        )
        
        assert policy['principalId'] == 'user456'
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
    
    def test_policy_structure(self):
        """Test that generated policy has correct structure."""
        policy = generate_policy('user', 'Allow', 'resource-arn')
        
        # Verify top-level structure
        assert 'principalId' in policy
        assert 'policyDocument' in policy
        
        # Verify policy document structure
        policy_doc = policy['policyDocument']
        assert 'Version' in policy_doc
        assert 'Statement' in policy_doc
        assert isinstance(policy_doc['Statement'], list)
        
        # Verify statement structure
        statement = policy_doc['Statement'][0]
        assert 'Action' in statement
        assert 'Effect' in statement
        assert 'Resource' in statement
    
    def test_wildcard_resource(self):
        """Test policy generation with wildcard resource."""
        policy = generate_policy('user', 'Deny', '*')
        
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Resource'] == '*'


class TestIntegration:
    """Integration tests for the authorizer."""
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_full_authorization_flow_success(self, mock_client):
        """Test complete authorization flow with valid API key."""
        # Setup mock responses
        mock_client.get_api_keys.return_value = {
            'Items': [
                {'ApiKeyId': 'key123', 'Name': 'hackathon-participant-1'}
            ]
        }
        
        mock_client.get_api_key.return_value = {
            'ApiKeyId': 'key123',
            'Value': 'hackathon-key-abc123',
            'Enabled': True,
            'Name': 'hackathon-participant-1'
        }
        
        # Create authorization event
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'test-connection-123',
                'apiId': 'api123',
                'stage': 'production'
            },
            'queryStringParameters': {
                'api_key': 'hackathon-key-abc123'
            }
        }
        
        # Execute authorization
        response = lambda_handler(event, None)
        
        # Verify Allow policy is returned
        assert response['principalId'] == 'user'
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['policyDocument']['Statement'][0]['Resource'] == event['methodArn']
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_full_authorization_flow_failure(self, mock_client):
        """Test complete authorization flow with invalid API key."""
        # Setup mock responses
        mock_client.get_api_keys.return_value = {
            'Items': [
                {'ApiKeyId': 'key123', 'Name': 'hackathon-participant-1'}
            ]
        }
        
        mock_client.get_api_key.return_value = {
            'ApiKeyId': 'key123',
            'Value': 'valid-key',
            'Enabled': True,
            'Name': 'hackathon-participant-1'
        }
        
        # Create authorization event with wrong key
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'requestContext': {
                'connectionId': 'test-connection-123'
            },
            'queryStringParameters': {
                'api_key': 'wrong-key'
            }
        }
        
        # Execute authorization
        response = lambda_handler(event, None)
        
        # Verify Deny policy is returned
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    
    @patch('lambdas.websocket_authorizer.apigateway_client')
    def test_authorization_with_multiple_participants(self, mock_client):
        """Test authorization with multiple hackathon participants."""
        # Setup mock responses for multiple participants
        mock_client.get_api_keys.return_value = {
            'Items': [
                {'ApiKeyId': 'key1', 'Name': 'participant-1'},
                {'ApiKeyId': 'key2', 'Name': 'participant-2'},
                {'ApiKeyId': 'key3', 'Name': 'participant-3'}
            ]
        }
        
        # Mock get_api_key to return different values
        def get_api_key_side_effect(ApiKey):
            keys = {
                'key1': {'Value': 'participant-1-key', 'Enabled': True},
                'key2': {'Value': 'participant-2-key', 'Enabled': True},
                'key3': {'Value': 'participant-3-key', 'Enabled': False}
            }
            return keys.get(ApiKey, {})
        
        mock_client.get_api_key.side_effect = get_api_key_side_effect
        
        # Test participant 2's key
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'queryStringParameters': {
                'api_key': 'participant-2-key'
            }
        }
        
        response = lambda_handler(event, None)
        
        # Should be allowed
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        
        # Test participant 3's disabled key
        event['queryStringParameters']['api_key'] = 'participant-3-key'
        response = lambda_handler(event, None)
        
        # Should be denied (disabled)
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Deny'


class TestSecurityScenarios:
    """Test security-related scenarios."""
    
    def test_sql_injection_attempt(self):
        """Test that SQL injection attempts are safely handled."""
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'queryStringParameters': {
                'api_key': "'; DROP TABLE api_keys; --"
            }
        }
        
        # Should not raise exception and should deny
        response = lambda_handler(event, None)
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    
    def test_extremely_long_api_key(self):
        """Test handling of extremely long API key strings."""
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'queryStringParameters': {
                'api_key': 'a' * 10000  # Very long string
            }
        }
        
        # Should handle gracefully and deny
        response = lambda_handler(event, None)
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Deny'
    
    def test_special_characters_in_api_key(self):
        """Test handling of special characters in API key."""
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/production/$connect',
            'queryStringParameters': {
                'api_key': '!@#$%^&*()_+-=[]{}|;:,.<>?'
            }
        }
        
        # Should handle gracefully and deny
        response = lambda_handler(event, None)
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Deny'
