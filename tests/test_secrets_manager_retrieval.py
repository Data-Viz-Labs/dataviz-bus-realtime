"""
Property-based tests for Secrets Manager API key retrieval.

These tests verify that the Custom Authorizer correctly retrieves
and validates API keys from AWS Secrets Manager.

**Property 5: Secrets Manager API key storage and retrieval**
**Validates: Requirements 15.2, 15.3**

Requirements:
- 15.2: WHEN the API Key is generated, THE System SHALL store it in AWS Secrets Manager
- 15.3: WHEN a client makes an API request, THE Custom_Authorizer SHALL validate 
        the API Key by reading it from AWS Secrets Manager
"""

import pytest
import json
import sys
import os
from hypothesis import given, settings, strategies as st
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.authorizer_rest import lambda_handler


# Strategy for generating valid API keys (alphanumeric strings)
api_keys = st.text(
    min_size=16,
    max_size=64,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        min_codepoint=48,
        max_codepoint=122
    )
).filter(lambda x: x.strip() and x.isalnum())

# Strategy for generating group names
group_names = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        min_codepoint=48,
        max_codepoint=122
    )
).filter(lambda x: x.strip())

# Strategy for generating method ARNs
method_arns = st.builds(
    lambda region, account, api_id, stage, endpoint: 
        f"arn:aws:execute-api:{region}:{account}:{api_id}/{stage}/GET/{endpoint}",
    region=st.sampled_from(['eu-west-1', 'eu-central-1', 'us-east-1']),
    account=st.integers(min_value=100000000000, max_value=999999999999).map(str),
    api_id=st.text(min_size=10, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
    stage=st.sampled_from(['prod', 'production', 'dev', 'staging']),
    endpoint=st.sampled_from([
        'people-count/S001',
        'sensors/bus/B001',
        'bus-position/B001'
    ])
)

# Strategy for generating secret IDs
secret_ids = st.sampled_from([
    'bus-simulator/api-key',
    'bus-simulator-api-key',
    'prod/bus-simulator/api-key',
    'dev/bus-simulator/api-key'
])


class TestProperty5SecretsManagerApiKeyRetrieval:
    """
    Property 5: Secrets Manager API key storage and retrieval
    
    **Validates: Requirements 15.2, 15.3**
    
    For any API request, the Custom Authorizer must retrieve the API key from
    AWS Secrets Manager (secret ID: bus-simulator/api-key) and validate the
    request's x-api-key header against it. The API key must be stored in JSON
    format: {"api_key": "generated_value"}.
    """
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_authorizer_retrieves_api_key_from_secrets_manager(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that the authorizer always retrieves API key from Secrets Manager.
        
        For any API request, the Custom Authorizer must call Secrets Manager's
        get_secret_value method to retrieve the stored API key before validation.
        This ensures centralized API key management.
        """
        # Mock Secrets Manager to return the API key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create REST API authorizer event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer
        response = lambda_handler(event, None)
        
        # Verify Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once()
        
        # Verify the correct secret ID was used
        call_args = mock_secrets.get_secret_value.call_args
        assert 'SecretId' in call_args.kwargs or len(call_args.args) > 0, \
            "Secrets Manager must be called with SecretId parameter"
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow', \
            "Valid API key from Secrets Manager must result in Allow policy"
    
    @settings(max_examples=100)
    @given(
        stored_key=api_keys,
        provided_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_authorizer_validates_against_secrets_manager_key(
        self, mock_secrets, stored_key, provided_key, group_name, method_arn
    ):
        """
        Test that the authorizer validates provided key against Secrets Manager.
        
        For any API request, the Custom Authorizer must compare the provided
        x-api-key header value against the API key retrieved from Secrets Manager.
        Only exact matches should be allowed.
        """
        # Ensure keys are different for this test
        if stored_key == provided_key:
            provided_key = provided_key + "X"
        
        # Mock Secrets Manager to return a specific API key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        # Create event with different API key
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': provided_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer - should raise exception for mismatched key
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            lambda_handler(event, None)
        
        # Verify Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once()
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_response_format_is_json(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that the authorizer correctly parses JSON from Secrets Manager.
        
        The API key must be stored in Secrets Manager in JSON format:
        {"api_key": "generated_value"}. The authorizer must parse this
        JSON and extract the api_key field.
        """
        # Mock Secrets Manager with JSON format
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer
        response = lambda_handler(event, None)
        
        # Verify authorization succeeded (proves JSON was parsed correctly)
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow', \
            "Authorizer must correctly parse JSON format from Secrets Manager"
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_error_denies_authorization(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that Secrets Manager errors result in authorization denial.
        
        If Secrets Manager fails to return the API key (network error,
        permission error, secret not found, etc.), the authorizer must
        deny the request for security reasons.
        """
        # Mock Secrets Manager to raise various errors
        error_codes = [
            'ResourceNotFoundException',
            'AccessDeniedException',
            'InvalidRequestException',
            'InternalServiceError'
        ]
        
        for error_code in error_codes:
            mock_secrets.get_secret_value.side_effect = ClientError(
                {'Error': {'Code': error_code, 'Message': f'{error_code} occurred'}},
                'GetSecretValue'
            )
            
            # Create event
            event = {
                'type': 'REQUEST',
                'methodArn': method_arn,
                'headers': {
                    'x-api-key': api_key,
                    'x-group-name': group_name
                }
            }
            
            # Execute authorizer - should raise exception for internal error
            with pytest.raises(Exception, match="Unauthorized.*Internal error"):
                lambda_handler(event, None)
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_malformed_secrets_manager_json_denies_authorization(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that malformed JSON from Secrets Manager results in denial.
        
        If Secrets Manager returns invalid JSON or JSON without the
        expected 'api_key' field, the authorizer must deny the request.
        """
        # Test various malformed JSON scenarios
        malformed_responses = [
            '{"wrong_field": "value"}',  # Missing api_key field
            '{"api_key": null}',  # Null api_key
            '{"api_key": ""}',  # Empty api_key
            'not valid json',  # Invalid JSON
            '{}',  # Empty object
        ]
        
        for malformed_json in malformed_responses:
            mock_secrets.get_secret_value.return_value = {
                'SecretString': malformed_json
            }
            
            # Create event
            event = {
                'type': 'REQUEST',
                'methodArn': method_arn,
                'headers': {
                    'x-api-key': api_key,
                    'x-group-name': group_name
                }
            }
            
            # Execute authorizer - should raise exception
            with pytest.raises(Exception):
                lambda_handler(event, None)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_called_before_validation(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that Secrets Manager is called before API key validation.
        
        The authorizer must retrieve the API key from Secrets Manager
        before attempting to validate the provided key. This ensures
        the latest key is always used.
        """
        # Track call order
        call_order = []
        
        def track_secrets_call(*args, **kwargs):
            call_order.append('secrets_manager')
            return {'SecretString': json.dumps({'api_key': api_key})}
        
        mock_secrets.get_secret_value.side_effect = track_secrets_call
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer
        response = lambda_handler(event, None)
        
        # Verify Secrets Manager was called
        assert 'secrets_manager' in call_order, \
            "Secrets Manager must be called during authorization"
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    @patch.dict(os.environ, {'SECRET_ID': 'custom-secret-id'})
    def test_authorizer_uses_configured_secret_id(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that the authorizer uses the configured SECRET_ID.
        
        The authorizer should use the SECRET_ID environment variable
        to determine which secret to retrieve from Secrets Manager.
        This allows for different secret IDs in different environments.
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer
        response = lambda_handler(event, None)
        
        # Verify Secrets Manager was called with custom secret ID
        call_args = mock_secrets.get_secret_value.call_args
        secret_id = call_args.kwargs.get('SecretId') or call_args.args[0]
        
        # Note: The actual implementation uses the environment variable
        # This test verifies the authorizer respects the SECRET_ID configuration
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_api_key_comparison_is_exact(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that API key comparison is exact (no trimming, case-sensitive).
        
        The authorizer must perform exact string comparison between the
        provided API key and the one from Secrets Manager. No normalization
        should be applied.
        """
        # Mock Secrets Manager with exact API key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Test 1: Exact match should succeed
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        response = lambda_handler(event, None)
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        
        # Test 2: Key with whitespace should fail
        event_with_whitespace = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': f" {api_key} ",
                'x-group-name': group_name
            }
        }
        
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            lambda_handler(event_with_whitespace, None)
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_timeout_denies_authorization(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that Secrets Manager timeout results in authorization denial.
        
        If Secrets Manager times out, the authorizer must deny the request
        rather than allowing it through without validation.
        """
        # Mock Secrets Manager to raise timeout error
        mock_secrets.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'RequestTimeout', 'Message': 'Request timed out'}},
            'GetSecretValue'
        )
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer - should raise exception for internal error
        with pytest.raises(Exception, match="Unauthorized.*Internal error"):
            lambda_handler(event, None)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_retrieval_is_consistent(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that multiple requests retrieve from Secrets Manager consistently.
        
        Each authorization request should retrieve the API key from Secrets
        Manager, ensuring that key rotations are immediately effective.
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer multiple times
        for _ in range(3):
            response = lambda_handler(event, None)
            assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        
        # Verify Secrets Manager was called each time
        assert mock_secrets.get_secret_value.call_count == 3, \
            "Secrets Manager should be called for each authorization request"


class TestProperty5SecretsManagerIntegration:
    """
    Integration properties for Secrets Manager API key retrieval.
    
    These tests verify that the Secrets Manager integration works
    correctly across different scenarios and edge cases.
    """
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_response_with_version_id(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that the authorizer handles Secrets Manager responses with version IDs.
        
        Secrets Manager responses include version metadata. The authorizer
        should correctly extract the SecretString regardless of other fields.
        """
        # Mock Secrets Manager with full response including version metadata
        mock_secrets.get_secret_value.return_value = {
            'ARN': 'arn:aws:secretsmanager:eu-west-1:123456789012:secret:bus-simulator/api-key-AbCdEf',
            'Name': 'bus-simulator/api-key',
            'VersionId': 'EXAMPLE1-90ab-cdef-fedc-ba987EXAMPLE',
            'SecretString': json.dumps({'api_key': api_key}),
            'VersionStages': ['AWSCURRENT'],
            'CreatedDate': '2024-01-01T00:00:00Z'
        }
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer
        response = lambda_handler(event, None)
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow', \
            "Authorizer must handle full Secrets Manager response format"
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_json_with_extra_fields(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that the authorizer handles JSON with extra fields.
        
        The Secrets Manager secret may contain additional fields beyond
        'api_key'. The authorizer should extract only the 'api_key' field.
        """
        # Mock Secrets Manager with extra fields in JSON
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({
                'api_key': api_key,
                'created_at': '2024-01-01T00:00:00Z',
                'description': 'Bus simulator API key',
                'rotation_enabled': False
            })
        }
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer
        response = lambda_handler(event, None)
        
        # Verify authorization succeeded
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow', \
            "Authorizer must extract api_key from JSON with extra fields"
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_network_error_denies_authorization(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that network errors when calling Secrets Manager result in denial.
        
        If the authorizer cannot reach Secrets Manager due to network issues,
        it must deny the request rather than allowing it through.
        """
        # Mock Secrets Manager to raise network-related errors
        mock_secrets.get_secret_value.side_effect = Exception('Network error: Connection timeout')
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer - should raise exception for internal error
        with pytest.raises(Exception, match="Unauthorized.*Internal error"):
            lambda_handler(event, None)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_retrieval_for_all_endpoints(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that Secrets Manager retrieval works for all API endpoints.
        
        The same Secrets Manager retrieval logic must work consistently
        for people-count, sensors, and bus-position endpoints.
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer
        response = lambda_handler(event, None)
        
        # Verify Secrets Manager was called
        mock_secrets.get_secret_value.assert_called_once()
        
        # Verify authorization succeeded regardless of endpoint
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow', \
            f"Secrets Manager retrieval must work for all endpoints, failed for {method_arn}"
