"""
Unit tests for REST API Custom Authorizer.

These tests verify specific examples and edge cases for the REST API
Custom Authorizer that validates x-api-key and x-group-name headers.

Requirements:
- 15.3: Custom Authorizer validates API key from Secrets Manager
- 15.6: Custom Authorizer requires x-group-name header
- 15.8: Group names are logged for request tracking
"""

import pytest
import json
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.authorizer_rest import lambda_handler, generate_policy


class TestValidApiKeyAcceptance:
    """Test that valid API keys are accepted."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_valid_api_key_returns_allow_policy(self, mock_secrets):
        """Test that a valid API key results in an Allow policy."""
        # Arrange
        api_key = 'test-api-key-12345'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['context']['group_name'] == group_name
        assert response['principalId'] == 'user'
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_case_insensitive_header_names(self, mock_secrets):
        """Test that header names are case-insensitive."""
        # Arrange
        api_key = 'test-api-key-67890'
        group_name = 'another-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Test with different case variations
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'X-API-KEY': api_key,  # Uppercase
                'X-Group-Name': group_name  # Mixed case
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['context']['group_name'] == group_name
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_policy_resource_uses_wildcard(self, mock_secrets):
        """Test that the policy resource uses wildcard for caching."""
        # Arrange
        api_key = 'test-api-key-wildcard'
        group_name = 'wildcard-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/bus-position/B001'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        resource = response['policyDocument']['Statement'][0]['Resource']
        assert resource.endswith('/*'), f"Expected wildcard resource, got {resource}"
        assert 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/*' == resource


class TestInvalidApiKeyRejection:
    """Test that invalid API keys are rejected."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_wrong_api_key_raises_exception(self, mock_secrets):
        """Test that an incorrect API key raises an exception."""
        # Arrange
        stored_key = 'correct-api-key'
        provided_key = 'wrong-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': provided_key,
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_empty_api_key_raises_exception(self, mock_secrets):
        """Test that an empty API key raises an exception."""
        # Arrange
        stored_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': '',  # Empty string
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_missing_api_key_header_raises_exception(self, mock_secrets):
        """Test that a missing x-api-key header raises an exception."""
        # Arrange
        stored_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/bus-position'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                # Missing x-api-key
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_api_key_with_whitespace_rejected(self, mock_secrets):
        """Test that API keys with extra whitespace are rejected."""
        # Arrange
        stored_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': f'  {stored_key}  ',  # Whitespace padding
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)


class TestMissingGroupNameRejection:
    """Test that missing x-group-name header is rejected."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_missing_group_name_header_raises_exception(self, mock_secrets):
        """Test that a missing x-group-name header raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key
                # Missing x-group-name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing x-group-name header' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_empty_group_name_raises_exception(self, mock_secrets):
        """Test that an empty x-group-name header raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': ''  # Empty string
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing x-group-name header' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_null_headers_raises_exception(self, mock_secrets):
        """Test that null headers object raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/bus-position'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': None  # Null headers
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing x-group-name header' in str(exc_info.value)


class TestSecretsManagerErrorHandling:
    """Test error handling for Secrets Manager failures."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_access_denied_raises_exception(self, mock_secrets):
        """Test that Secrets Manager access denied error raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count'
        
        mock_secrets.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetSecretValue'
        )
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_not_found_raises_exception(self, mock_secrets):
        """Test that Secrets Manager secret not found error raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors'
        
        mock_secrets.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}},
            'GetSecretValue'
        )
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_invalid_json_raises_exception(self, mock_secrets):
        """Test that invalid JSON from Secrets Manager raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/bus-position'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': 'not-valid-json'
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_missing_api_key_field_raises_exception(self, mock_secrets):
        """Test that missing api_key field in JSON raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'wrong_field': 'value'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_network_error_raises_exception(self, mock_secrets):
        """Test that network errors from Secrets Manager raise an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors'
        
        mock_secrets.get_secret_value.side_effect = Exception('Network timeout')
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)


class TestCachingBehavior:
    """Test caching behavior of the authorizer."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_policy_resource_supports_caching(self, mock_secrets):
        """Test that the policy resource uses wildcard to support caching."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count/S001'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        resource = response['policyDocument']['Statement'][0]['Resource']
        # Should use wildcard for caching across all endpoints
        assert resource.endswith('/*')
        # Should be derived from the method ARN
        assert 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/*' == resource
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_multiple_requests_same_key_consistent(self, mock_secrets):
        """Test that multiple requests with the same key produce consistent results."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act - Execute multiple times
        responses = [lambda_handler(event, None) for _ in range(3)]
        
        # Assert - All responses should be identical
        for response in responses:
            assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
            assert response['context']['group_name'] == group_name
            assert response['principalId'] == 'user'


class TestGeneratePolicyFunction:
    """Test the generate_policy helper function."""
    
    def test_generate_allow_policy(self):
        """Test generating an Allow policy."""
        # Arrange
        principal_id = 'user'
        effect = 'Allow'
        resource = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count'
        group_name = 'test-group'
        
        # Act
        policy = generate_policy(principal_id, effect, resource, group_name)
        
        # Assert
        assert policy['principalId'] == principal_id
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert policy['policyDocument']['Statement'][0]['Effect'] == effect
        assert policy['policyDocument']['Statement'][0]['Action'] == 'execute-api:Invoke'
        assert policy['policyDocument']['Statement'][0]['Resource'].endswith('/*')
        assert policy['context']['group_name'] == group_name
    
    def test_generate_deny_policy(self):
        """Test generating a Deny policy."""
        # Arrange
        principal_id = 'user'
        effect = 'Deny'
        resource = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors'
        group_name = 'denied-group'
        
        # Act
        policy = generate_policy(principal_id, effect, resource, group_name)
        
        # Assert
        assert policy['principalId'] == principal_id
        assert policy['policyDocument']['Statement'][0]['Effect'] == effect
        assert policy['context']['group_name'] == group_name
    
    def test_policy_resource_wildcard_extraction(self):
        """Test that the resource wildcard is correctly extracted from method ARN."""
        # Arrange
        resource = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/bus-position/B001'
        
        # Act
        policy = generate_policy('user', 'Allow', resource, 'test-group')
        
        # Assert
        policy_resource = policy['policyDocument']['Statement'][0]['Resource']
        assert policy_resource == 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/*'
