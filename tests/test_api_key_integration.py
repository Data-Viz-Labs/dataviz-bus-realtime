"""
Integration tests for unified API key management.

These tests verify the end-to-end authentication flow including:
- Custom Authorizer validation against Secrets Manager
- Missing x-group-name header rejection
- Invalid API key rejection
- Group name logging in CloudWatch
- Authorization caching behavior

Requirements:
- 15.3: Custom Authorizer validates API key from Secrets Manager
- 15.4: Lambda functions validate API key from Secrets Manager
- 15.6: Custom Authorizer requires x-group-name header
- 15.7: Lambda functions log group name
- 15.8: Group names appear in CloudWatch logs
"""

import pytest
import json
import sys
import os
import time
from unittest.mock import Mock, patch, MagicMock, call
from botocore.exceptions import ClientError

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.authorizer_rest import lambda_handler as rest_authorizer_handler
from lambdas.authorizer_websocket import lambda_handler as websocket_authorizer_handler


class TestEndToEndAuthenticationFlow:
    """Test complete authentication flow from request to authorization."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_api_complete_authentication_flow(self, mock_secrets):
        """
        Test end-to-end REST API authentication flow.
        
        Validates Requirements 15.3, 15.6:
        - Custom Authorizer retrieves API key from Secrets Manager
        - Custom Authorizer validates x-api-key header
        - Custom Authorizer validates x-group-name header
        - Returns Allow policy on success
        """
        # Arrange
        api_key = 'integration-test-key-12345'
        group_name = 'integration-test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count/S001'
        
        # Mock Secrets Manager to return the API key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create REST API request event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Act
        response = rest_authorizer_handler(event, None)
        
        # Assert - Verify complete flow
        # 1. Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once_with(SecretId='bus-simulator/api-key')
        
        # 2. Authorization succeeded
        assert response['principalId'] == 'user'
        assert response['policyDocument']['Version'] == '2012-10-17'
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['policyDocument']['Statement'][0]['Action'] == 'execute-api:Invoke'
        
        # 3. Group name is passed in context
        assert response['context']['group_name'] == group_name
        
        # 4. Policy resource uses wildcard for caching
        assert response['policyDocument']['Statement'][0]['Resource'].endswith('/*')
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_websocket_complete_authentication_flow(self, mock_secrets):
        """
        Test end-to-end WebSocket authentication flow.
        
        Validates Requirements 15.3, 15.6:
        - Custom Authorizer retrieves API key from Secrets Manager
        - Custom Authorizer validates api_key query parameter
        - Custom Authorizer validates group_name query parameter
        - Returns Allow policy on success
        """
        # Arrange
        api_key = 'websocket-test-key-67890'
        group_name = 'websocket-test-group'
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect'
        connection_id = 'test-connection-123'
        
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create WebSocket connection event
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
        response = websocket_authorizer_handler(event, None)
        
        # Assert - Verify complete flow
        # 1. Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once_with(SecretId='bus-simulator/api-key')
        
        # 2. Authorization succeeded
        assert response['principalId'] == 'user'
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        
        # 3. Group name is passed in context
        assert response['context']['group_name'] == group_name


class TestSecretsManagerValidation:
    """Test Custom Authorizer validates against Secrets Manager."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_authorizer_retrieves_from_secrets_manager(self, mock_secrets):
        """
        Test that REST authorizer retrieves API key from Secrets Manager.
        
        Validates Requirement 15.3:
        - Custom Authorizer SHALL validate API key by reading from Secrets Manager
        """
        # Arrange
        api_key = 'secrets-manager-key'
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
        
        # Act
        response = rest_authorizer_handler(event, None)
        
        # Assert
        # Verify Secrets Manager was called with correct secret ID
        mock_secrets.get_secret_value.assert_called_once()
        call_args = mock_secrets.get_secret_value.call_args
        assert call_args.kwargs['SecretId'] == 'bus-simulator/api-key'
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_websocket_authorizer_retrieves_from_secrets_manager(self, mock_secrets):
        """
        Test that WebSocket authorizer retrieves API key from Secrets Manager.
        
        Validates Requirement 15.3:
        - Custom Authorizer SHALL validate API key by reading from Secrets Manager
        """
        # Arrange
        api_key = 'websocket-secrets-key'
        group_name = 'websocket-group'
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
        response = websocket_authorizer_handler(event, None)
        
        # Assert
        # Verify Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once()
        call_args = mock_secrets.get_secret_value.call_args
        assert call_args.kwargs['SecretId'] == 'bus-simulator/api-key'
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_authorizer_validates_against_secrets_manager_key(self, mock_secrets):
        """
        Test that authorizer validates provided key against Secrets Manager.
        
        Validates Requirement 15.3:
        - API key validation must use the key from Secrets Manager
        """
        # Arrange
        stored_key = 'correct-secrets-manager-key'
        provided_key = 'wrong-key'
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
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            rest_authorizer_handler(event, None)
        
        # Verify Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once()


class TestMissingGroupNameRejection:
    """Test missing x-group-name header rejection."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_api_rejects_missing_group_name(self, mock_secrets):
        """
        Test that REST API rejects requests without x-group-name header.
        
        Validates Requirement 15.6:
        - API Gateway SHALL require x-group-name header
        """
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
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing x-group-name header' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_api_rejects_empty_group_name(self, mock_secrets):
        """
        Test that REST API rejects requests with empty x-group-name header.
        
        Validates Requirement 15.6:
        - x-group-name header must have a value
        """
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
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing x-group-name header' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_websocket_rejects_missing_group_name(self, mock_secrets):
        """
        Test that WebSocket rejects connections without group_name parameter.
        
        Validates Requirement 15.6:
        - WebSocket SHALL require group_name query parameter
        """
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
            websocket_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing group_name parameter' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_websocket_rejects_empty_group_name(self, mock_secrets):
        """
        Test that WebSocket rejects connections with empty group_name.
        
        Validates Requirement 15.6:
        - group_name parameter must have a value
        """
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
            websocket_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Missing group_name parameter' in str(exc_info.value)


class TestInvalidApiKeyRejection:
    """Test invalid API key rejection."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_api_rejects_invalid_api_key(self, mock_secrets):
        """
        Test that REST API rejects requests with invalid API key.
        
        Validates Requirement 15.3:
        - Invalid API keys must be rejected
        """
        # Arrange
        stored_key = 'correct-api-key-12345'
        provided_key = 'invalid-api-key-67890'
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
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
        
        # Verify Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once()
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_api_rejects_missing_api_key(self, mock_secrets):
        """
        Test that REST API rejects requests without x-api-key header.
        
        Validates Requirement 15.3:
        - API key header is required
        """
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
                # Missing x-api-key
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_websocket_rejects_invalid_api_key(self, mock_secrets):
        """
        Test that WebSocket rejects connections with invalid API key.
        
        Validates Requirement 15.3:
        - Invalid API keys must be rejected
        """
        # Arrange
        stored_key = 'correct-websocket-key'
        provided_key = 'invalid-websocket-key'
        group_name = 'websocket-group'
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
            websocket_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)
        
        # Verify Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once()
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_api_rejects_empty_api_key(self, mock_secrets):
        """
        Test that REST API rejects requests with empty API key.
        
        Validates Requirement 15.3:
        - Empty API keys must be rejected
        """
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
                'x-api-key': '',  # Empty string
                'x-group-name': group_name
            }
        }
        
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Invalid API key' in str(exc_info.value)


class TestGroupNameLogging:
    """Test that group names appear in logs."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    @patch('lambdas.authorizer_rest.print')
    def test_rest_authorizer_logs_group_name(self, mock_print, mock_secrets):
        """
        Test that REST authorizer logs group name.
        
        Validates Requirements 15.7, 15.8:
        - Group name SHALL be logged for request tracking
        - Group names SHALL appear in CloudWatch logs
        """
        # Arrange
        api_key = 'test-api-key'
        group_name = 'test-group-for-logging'
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
        response = rest_authorizer_handler(event, None)
        
        # Assert
        # Verify group name appears in logs
        log_calls = [str(call) for call in mock_print.call_args_list]
        group_name_logged = any(group_name in str(call) for call in log_calls)
        assert group_name_logged, f"Group name '{group_name}' should appear in logs"
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['context']['group_name'] == group_name
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    @patch('lambdas.authorizer_websocket.print')
    def test_websocket_authorizer_logs_group_name(self, mock_print, mock_secrets):
        """
        Test that WebSocket authorizer logs group name.
        
        Validates Requirements 15.7, 15.8:
        - Group name SHALL be logged for request tracking
        - Group names SHALL appear in CloudWatch logs
        """
        # Arrange
        api_key = 'websocket-test-key'
        group_name = 'websocket-group-for-logging'
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
        response = websocket_authorizer_handler(event, None)
        
        # Assert
        # Verify group name appears in logs
        log_calls = [str(call) for call in mock_print.call_args_list]
        group_name_logged = any(group_name in str(call) for call in log_calls)
        assert group_name_logged, f"Group name '{group_name}' should appear in logs"
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['context']['group_name'] == group_name


class TestAuthorizationCaching:
    """Test authorization caching behavior."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_rest_authorizer_policy_supports_caching(self, mock_secrets):
        """
        Test that REST authorizer policy supports caching.
        
        Validates Requirement 15.8:
        - Authorization results are cached for 5 minutes
        - Policy resource uses wildcard to enable caching
        """
        # Arrange
        api_key = 'cache-test-key'
        group_name = 'cache-test-group'
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
        response = rest_authorizer_handler(event, None)
        
        # Assert
        # Verify policy uses wildcard resource for caching
        resource = response['policyDocument']['Statement'][0]['Resource']
        assert resource.endswith('/*'), "Policy resource must use wildcard for caching"
        
        # Verify resource is derived from method ARN
        expected_prefix = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod'
        assert resource.startswith(expected_prefix), "Resource must be derived from method ARN"
    
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_websocket_authorizer_policy_supports_caching(self, mock_secrets):
        """
        Test that WebSocket authorizer policy supports caching.
        
        Validates Requirement 15.8:
        - Authorization results are cached for 5 minutes
        - Policy resource uses wildcard to enable caching
        """
        # Arrange
        api_key = 'websocket-cache-key'
        group_name = 'websocket-cache-group'
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
        response = websocket_authorizer_handler(event, None)
        
        # Assert
        # Verify policy uses wildcard resource for caching
        resource = response['policyDocument']['Statement'][0]['Resource']
        assert resource.endswith('/*'), "Policy resource must use wildcard for caching"
        
        # Verify resource is derived from method ARN
        expected_prefix = 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod'
        assert resource.startswith(expected_prefix), "Resource must be derived from method ARN"
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_multiple_requests_same_credentials_consistent(self, mock_secrets):
        """
        Test that multiple requests with same credentials produce consistent results.
        
        Validates Requirement 15.8:
        - Caching behavior should be consistent
        """
        # Arrange
        api_key = 'consistent-key'
        group_name = 'consistent-group'
        
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Test different endpoints with same credentials
        endpoints = [
            'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count/S001',
            'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors/bus/B001',
            'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/bus-position/B001'
        ]
        
        responses = []
        for method_arn in endpoints:
            event = {
                'type': 'REQUEST',
                'methodArn': method_arn,
                'headers': {
                    'x-api-key': api_key,
                    'x-group-name': group_name
                }
            }
            
            response = rest_authorizer_handler(event, None)
            responses.append(response)
        
        # Assert
        # All responses should have same structure
        for response in responses:
            assert response['principalId'] == 'user'
            assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
            assert response['context']['group_name'] == group_name
            assert response['policyDocument']['Statement'][0]['Resource'].endswith('/*')


class TestSecretsManagerErrorHandling:
    """Test error handling for Secrets Manager failures."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_access_denied_denies_authorization(self, mock_secrets):
        """
        Test that Secrets Manager access denied results in authorization denial.
        
        Validates Requirement 15.3:
        - Secrets Manager errors must result in denial
        """
        # Arrange
        api_key = 'test-key'
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
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_not_found_denies_authorization(self, mock_secrets):
        """
        Test that Secrets Manager secret not found results in denial.
        
        Validates Requirement 15.3:
        - Missing secrets must result in denial
        """
        # Arrange
        api_key = 'test-key'
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
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_invalid_json_denies_authorization(self, mock_secrets):
        """
        Test that invalid JSON from Secrets Manager results in denial.
        
        Validates Requirement 15.3:
        - Malformed secrets must result in denial
        """
        # Arrange
        api_key = 'test-key'
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
            rest_authorizer_handler(event, None)
        
        assert 'Unauthorized' in str(exc_info.value)
        assert 'Internal error' in str(exc_info.value)


class TestCrossAuthorizerConsistency:
    """Test consistency between REST and WebSocket authorizers."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_both_authorizers_use_same_secret(self, mock_ws_secrets, mock_rest_secrets):
        """
        Test that both authorizers use the same Secrets Manager secret.
        
        Validates Requirement 15.3:
        - Both authorizers must validate against the same API key
        """
        # Arrange
        api_key = 'unified-api-key'
        group_name = 'unified-group'
        
        mock_rest_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        mock_ws_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # REST event
        rest_event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/people-count',
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # WebSocket event
        ws_event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect',
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act
        rest_response = rest_authorizer_handler(rest_event, None)
        ws_response = websocket_authorizer_handler(ws_event, None)
        
        # Assert
        # Both should use the same secret ID
        mock_rest_secrets.get_secret_value.assert_called_once_with(SecretId='bus-simulator/api-key')
        mock_ws_secrets.get_secret_value.assert_called_once_with(SecretId='bus-simulator/api-key')
        
        # Both should succeed
        assert rest_response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert ws_response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    
    @patch('lambdas.authorizer_rest.secrets_client')
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_both_authorizers_reject_same_invalid_key(self, mock_ws_secrets, mock_rest_secrets):
        """
        Test that both authorizers reject the same invalid key.
        
        Validates Requirement 15.3:
        - Validation logic must be consistent across authorizers
        """
        # Arrange
        stored_key = 'correct-key'
        invalid_key = 'invalid-key'
        group_name = 'test-group'
        
        mock_rest_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        mock_ws_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        # REST event with invalid key
        rest_event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/sensors',
            'headers': {
                'x-api-key': invalid_key,
                'x-group-name': group_name
            }
        }
        
        # WebSocket event with invalid key
        ws_event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect',
            'queryStringParameters': {
                'api_key': invalid_key,
                'group_name': group_name
            }
        }
        
        # Act & Assert
        # Both should reject the invalid key
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            rest_authorizer_handler(rest_event, None)
        
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            websocket_authorizer_handler(ws_event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    @patch('lambdas.authorizer_websocket.secrets_client')
    def test_both_authorizers_pass_group_name_in_context(self, mock_ws_secrets, mock_rest_secrets):
        """
        Test that both authorizers pass group name in context.
        
        Validates Requirements 15.7, 15.8:
        - Group name must be available to downstream Lambda functions
        """
        # Arrange
        api_key = 'test-key'
        group_name = 'context-test-group'
        
        mock_rest_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        mock_ws_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # REST event
        rest_event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/GET/bus-position',
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # WebSocket event
        ws_event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:abc123/prod/$connect',
            'queryStringParameters': {
                'api_key': api_key,
                'group_name': group_name
            }
        }
        
        # Act
        rest_response = rest_authorizer_handler(rest_event, None)
        ws_response = websocket_authorizer_handler(ws_event, None)
        
        # Assert
        # Both should include group name in context
        assert rest_response['context']['group_name'] == group_name
        assert ws_response['context']['group_name'] == group_name
