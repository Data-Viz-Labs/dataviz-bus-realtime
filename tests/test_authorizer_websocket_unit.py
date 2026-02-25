"""
Unit tests for WebSocket API Custom Authorizer.

These tests verify specific examples and edge cases for the WebSocket API
Custom Authorizer that validates api_key and group_name query parameters.

Requirements:
- 15.3: Custom Authorizer validates API key from Secrets Manager
- 15.6: Custom Authorizer requires group_name parameter
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

from lambdas.authorizer_websocket import lambda_handler, generate_policy


class TestValidApiKeyAcceptance:
    """Test that valid API keys are accepted."""
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_valid_api_key_returns_allow_policy(self, mock_secrets):
        """Test that a valid API key results in an Allow policy."""
        # Arrange
        api_key = 'test-api-key-12345'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        connection_id = 'test-connection-123'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'requestContext': {
                'connectionId': connection_id
            },
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['context']['group_name'] == group_name
        assert response['principalId'] == 'user'
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_policy_resource_uses_wildcard(self, mock_secrets):
        """Test that the policy resource uses wildcard for caching."""
        # Arrange
        api_key = 'test-api-key-wildcard'
        group_name = 'wildcard-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        resource = response['policyDocument']['Statement'][0]['Resource']
        assert resource.endswith('/*'), f"Expected wildcard resource, got {resource}"
        assert 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/*' == resource
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_different_connection_ids_accepted(self, mock_secrets):
        """Test that different connection IDs are accepted with valid API key."""
        # Arrange
        api_key = 'test-api-key-connections'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        connection_ids = ['conn-001', 'conn-002', 'conn-003']
        
        for conn_id in connection_ids:
            event = {
                'type': 'REQUEST',
                'methodArn': method_arn,
                'requestContext': {
                    'connectionId': conn_id
                },
                'queryStringParameters': {
                    'api_key': api_key,
                    'group_name': group_name
                }
            }
            
            # Act
            response = lambda_handler(event, None)
            
            # Assert
            assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'


class TestInvalidApiKeyRejection:
    """Test that invalid API keys are rejected."""
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_wrong_api_key_raises_exception(self, mock_secrets):
        """Test that an incorrect API key raises an exception."""
        # Arrange
        stored_key = 'correct-api-key'
        provided_key = 'wrong-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': provided_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_empty_api_key_raises_exception(self, mock_secrets):
        """Test that an empty API key raises an exception."""
        # Arrange
        stored_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': '',  # Empty string
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_missing_api_key_parameter_raises_exception(self, mock_secrets):
        """Test that a missing api_key parameter raises an exception."""
        # Arrange
        stored_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                # Missing api_key
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_api_key_case_sensitive(self, mock_secrets):
        """Test that API key validation is case-sensitive."""
        # Arrange
        stored_key = 'ValidApiKey123'
        provided_key = 'validapikey123'  # Different case
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': provided_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)


class TestMissingGroupNameRejection:
    """Test that missing group_name parameter is rejected."""
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_missing_group_name_parameter_raises_exception(self, mock_secrets):
        """Test that a missing group_name parameter raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key
                # Missing group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing group_name parameter' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_empty_group_name_raises_exception(self, mock_secrets):
        """Test that an empty group_name parameter raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': ''  # Empty string
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing group_name parameter' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_null_query_parameters_raises_exception(self, mock_secrets):
        """Test that null queryStringParameters raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': None  # Null
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing group_name parameter' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_missing_query_parameters_raises_exception(self, mock_secrets):
        """Test that missing queryStringParameters key raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn
            # Missing queryStringParameters
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing group_name parameter' in str(exc_info.value)


class TestSecretsManagerErrorHandling:
    """Test error handling for Secrets Manager failures."""
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_secrets_manager_access_denied_raises_exception(self, mock_secrets):
        """Test that Secrets Manager access denied error raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetSecretValue'
        )
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_secrets_manager_not_found_raises_exception(self, mock_secrets):
        """Test that Secrets Manager secret not found error raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}},
            'GetSecretValue'
        )
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_secrets_manager_invalid_json_raises_exception(self, mock_secrets):
        """Test that invalid JSON from Secrets Manager raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': 'not-valid-json'
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_secrets_manager_missing_api_key_field_raises_exception(self, mock_secrets):
        """Test that missing api_key field in JSON raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'wrong_field': 'value'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_secrets_manager_timeout_raises_exception(self, mock_secrets):
        """Test that Secrets Manager timeout raises an exception."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.side_effect = Exception('Connection timeout')
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            lambda_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)


class TestCachingBehavior:
    """Test caching behavior of the authorizer."""
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_policy_resource_supports_caching(self, mock_secrets):
        """Test that the policy resource uses wildcard to support caching."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act
        response = lambda_handler(event, None)
        
        # Assert
        resource = response['policyDocument']['Statement'][0]['Resource']
        # Should use wildcard for caching across all routes
        assert resource.endswith('/*')
        # Should be derived from the method ARN
        assert 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/*' == resource
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_multiple_connections_same_key_consistent(self, mock_secrets):
        """Test that multiple connections with the same key produce consistent results."""
        # Arrange
        api_key = 'valid-api-key'
        group_name = 'test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Test with different connection IDs
        connection_ids = ['conn-001', 'conn-002', 'conn-003']
        responses = []
        
        for conn_id in connection_ids:
            event = {
                'type': 'REQUEST',
                'methodArn': method_arn,
                'requestContext': {
                    'connectionId': conn_id
                },
                'queryStringParameters': {
                    'api_key': api_key,
                    'group_name': group_name
                }
            }
            
            # Act
            response = lambda_handler(event, None)
            responses.append(response)
        
        # Assert - All responses should have same structure
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
        resource = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
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
        resource = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
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
        resource = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        
        # Act
        policy = generate_policy('user', 'Allow', resource, 'test-group')
        
        # Assert
        policy_resource = policy['policyDocument']['Statement'][0]['Resource']
        assert policy_resource == 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/*'
    
    def test_policy_structure_valid(self):
        """Test that generated policy has valid IAM policy structure."""
        # Arrange
        resource = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$default'
        
        # Act
        policy = generate_policy('user', 'Allow', resource, 'test-group')
        
        # Assert
        assert 'principalId' in policy
        assert 'policyDocument' in policy
        assert 'context' in policy
        
        policy_doc = policy['policyDocument']
        assert 'Version' in policy_doc
        assert policy_doc['Version'] == '2012-10-17'
        assert 'Statement' in policy_doc
        assert isinstance(policy_doc['Statement'], list)
        assert len(policy_doc['Statement']) > 0
        
        statement = policy_doc['Statement'][0]
        assert 'Action' in statement
        assert 'Effect' in statement
        assert 'Resource' in statement
        assert statement['Action'] == 'execute-api:Invoke'
