"""
Unit tests for the REST API Custom Authorizer Lambda function.

Tests the custom authorizer for REST API endpoints, including API key
validation from x-api-key header and x-group-name header validation.

Requirements: 3.7
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

# Import the Lambda authorizer module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.authorizer_rest import (
    lambda_handler,
    generate_policy
)


class TestLambdaHandler:
    """Test the main Lambda authorizer handler function."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_valid_api_key_acceptance(self, mock_secrets):
        """Test that valid API key results in Allow policy."""
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-api-key-12345'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'valid-api-key-12345',
                'x-group-name': 'team-alpha'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        assert response['policyDocument']['Version'] == '2012-10-17'
        assert len(response['policyDocument']['Statement']) == 1
        
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Allow'
        assert statement['Action'] == 'execute-api:Invoke'
        
        # Verify group name is in context
        assert 'context' in response
        assert response['context']['group_name'] == 'team-alpha'
        
        mock_secrets.get_secret_value.assert_called_once_with(SecretId='bus-simulator/api-key')
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_invalid_api_key_rejection(self, mock_secrets):
        """Test that invalid API key results in exception."""
        # Mock Secrets Manager response with different key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'correct-api-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'wrong-api-key',
                'x-group-name': 'team-alpha'
            }
        }
        
        with pytest.raises(Exception, match='Unauthorized.*Invalid API key'):
            lambda_handler(event, None)
        
        mock_secrets.get_secret_value.assert_called_once()
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_missing_api_key_handling(self, mock_secrets):
        """Test that missing API key results in exception."""
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-api-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-group-name': 'team-alpha'
                # Missing x-api-key header
            }
        }
        
        with pytest.raises(Exception, match='Unauthorized.*Invalid API key'):
            lambda_handler(event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_empty_api_key_handling(self, mock_secrets):
        """Test that empty API key string results in exception."""
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-api-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': '',
                'x-group-name': 'team-alpha'
            }
        }
        
        with pytest.raises(Exception, match='Unauthorized.*Invalid API key'):
            lambda_handler(event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_missing_group_name_header(self, mock_secrets):
        """Test that missing x-group-name header results in exception."""
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-api-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'valid-api-key'
                # Missing x-group-name header
            }
        }
        
        with pytest.raises(Exception, match='Unauthorized.*Missing x-group-name'):
            lambda_handler(event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_empty_group_name_header(self, mock_secrets):
        """Test that empty x-group-name header results in exception."""
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-api-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'valid-api-key',
                'x-group-name': ''
            }
        }
        
        with pytest.raises(Exception, match='Unauthorized.*Missing x-group-name'):
            lambda_handler(event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_case_insensitive_headers(self, mock_secrets):
        """Test that headers are case-insensitive."""
        # Mock Secrets Manager response
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-api-key-12345'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'X-API-KEY': 'valid-api-key-12345',  # Uppercase
                'X-Group-Name': 'team-alpha'  # Mixed case
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['principalId'] == 'user'
        statement = response['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Allow'
        assert response['context']['group_name'] == 'team-alpha'
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_error_handling(self, mock_secrets):
        """Test handling of Secrets Manager errors."""
        # Mock Secrets Manager to raise an error
        mock_secrets.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetSecretValue'
        )
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'valid-api-key',
                'x-group-name': 'team-alpha'
            }
        }
        
        with pytest.raises(Exception, match='Unauthorized.*Internal error'):
            lambda_handler(event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_null_headers(self, mock_secrets):
        """Test handling when headers is None."""
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': None
        }
        
        with pytest.raises(Exception):
            lambda_handler(event, None)


class TestGeneratePolicy:
    """Test IAM policy generation."""
    
    def test_generate_allow_policy(self):
        """Test generation of Allow policy."""
        policy = generate_policy(
            'user123',
            'Allow',
            'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'team-alpha'
        )
        
        assert policy['principalId'] == 'user123'
        assert policy['policyDocument']['Version'] == '2012-10-17'
        assert len(policy['policyDocument']['Statement']) == 1
        
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Action'] == 'execute-api:Invoke'
        assert statement['Effect'] == 'Allow'
        
        # Verify wildcard resource for caching
        assert statement['Resource'].endswith('/*')
        
        # Verify context
        assert policy['context']['group_name'] == 'team-alpha'
    
    def test_generate_deny_policy(self):
        """Test generation of Deny policy."""
        policy = generate_policy(
            'user456',
            'Deny',
            'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/sensors/bus/B001',
            'team-beta'
        )
        
        assert policy['principalId'] == 'user456'
        statement = policy['policyDocument']['Statement'][0]
        assert statement['Effect'] == 'Deny'
        assert policy['context']['group_name'] == 'team-beta'
    
    def test_policy_structure(self):
        """Test that generated policy has correct structure."""
        policy = generate_policy('user', 'Allow', 'resource-arn', 'test-group')
        
        # Verify top-level structure
        assert 'principalId' in policy
        assert 'policyDocument' in policy
        assert 'context' in policy
        
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
        
        # Verify context
        assert 'group_name' in policy['context']
    
    def test_wildcard_resource_for_caching(self):
        """Test that policy uses wildcard resource for caching."""
        method_arn = 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001'
        policy = generate_policy('user', 'Allow', method_arn, 'test-group')
        
        statement = policy['policyDocument']['Statement'][0]
        resource = statement['Resource']
        
        # Should be wildcard for caching
        assert resource.endswith('/*')
        
        # Should be derived from method ARN
        assert 'arn:aws:execute-api:eu-west-1:123456789012:api123' in resource


class TestIntegration:
    """Integration tests for the REST authorizer."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_full_authorization_flow_success(self, mock_secrets):
        """Test complete authorization flow with valid credentials."""
        # Setup mock
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'hackathon-key-abc123'})
        }
        
        # Create authorization event
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'hackathon-key-abc123',
                'x-group-name': 'hackathon-team-1'
            }
        }
        
        # Execute authorization
        response = lambda_handler(event, None)
        
        # Verify Allow policy is returned
        assert response['principalId'] == 'user'
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['context']['group_name'] == 'hackathon-team-1'
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_full_authorization_flow_failure(self, mock_secrets):
        """Test complete authorization flow with invalid API key."""
        # Setup mock
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'correct-key'})
        }
        
        # Create authorization event with wrong key
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'wrong-key',
                'x-group-name': 'hackathon-team-1'
            }
        }
        
        # Execute authorization - should raise exception
        with pytest.raises(Exception, match='Unauthorized.*Invalid API key'):
            lambda_handler(event, None)


class TestSecurityScenarios:
    """Test security-related scenarios."""
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_sql_injection_attempt(self, mock_secrets):
        """Test that SQL injection attempts are safely handled."""
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': "'; DROP TABLE api_keys; --",
                'x-group-name': 'test-group'
            }
        }
        
        # Should not raise exception and should deny
        with pytest.raises(Exception, match='Unauthorized.*Invalid API key'):
            lambda_handler(event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_extremely_long_api_key(self, mock_secrets):
        """Test handling of extremely long API key strings."""
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': 'a' * 10000,  # Very long string
                'x-group-name': 'test-group'
            }
        }
        
        # Should handle gracefully and deny
        with pytest.raises(Exception, match='Unauthorized.*Invalid API key'):
            lambda_handler(event, None)
    
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_special_characters_in_api_key(self, mock_secrets):
        """Test handling of special characters in API key."""
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'valid-key'})
        }
        
        event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:eu-west-1:123456789012:api123/prod/GET/people-count/S001',
            'headers': {
                'x-api-key': '!@#$%^&*()_+-=[]{}|;:,.<>?',
                'x-group-name': 'test-group'
            }
        }
        
        # Should handle gracefully and deny
        with pytest.raises(Exception, match='Unauthorized.*Invalid API key'):
            lambda_handler(event, None)
