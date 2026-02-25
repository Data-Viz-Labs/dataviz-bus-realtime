"""
Property-based tests for the REST API Custom Authorizer.

These tests use the Hypothesis library to verify universal properties
of API key validation for REST endpoints across randomized inputs.

**Property 1: API key validation for REST endpoints**
**Validates: Requirements 1.7, 2.5, 3.7**

Requirements:
- 1.7: WHEN a client requests any endpoint an API Key will be required (People Count API)
- 2.5: WHEN a client requests any endpoint an API Key will be required (Sensors API)
- 3.7: WHEN a client requests any endpoint an API Key will be required (Bus Position API)
"""

import pytest
import json
import sys
import os
from hypothesis import given, settings, strategies as st
from unittest.mock import patch
from botocore.exceptions import ClientError

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.authorizer_rest import (
    lambda_handler,
    generate_policy
)


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

# Strategy for generating method ARNs for different APIs
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
        'bus-position/B001',
        'bus-position/line/L1'
    ])
)


class TestProperty1ApiKeyValidationForRestEndpoints:
    """
    Property 1: API key validation for REST endpoints
    
    **Validates: Requirements 1.7, 2.5, 3.7**
    
    For all REST API requests (people-count, sensors, bus-position), the Custom
    Authorizer must validate the API key from x-api-key header against the stored
    key in Secrets Manager. Valid keys result in Allow policies, invalid keys
    result in Deny policies (exceptions).
    """
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_valid_api_key_always_allows_request(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that any valid API key results in an Allow policy.
        
        For any API key that matches the stored key in Secrets Manager,
        the authorizer must return an Allow policy with proper structure.
        This applies to all REST endpoints: people-count, sensors, bus-position.
        """
        # Mock Secrets Manager to return the same API key
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
        
        # Verify Allow policy is returned
        assert 'policyDocument' in response, "Response must contain policyDocument"
        assert 'principalId' in response, "Response must contain principalId"
        
        policy_doc = response['policyDocument']
        assert policy_doc['Version'] == '2012-10-17', "Policy version must be 2012-10-17"
        assert len(policy_doc['Statement']) > 0, "Policy must have at least one statement"
        
        statement = policy_doc['Statement'][0]
        assert statement['Effect'] == 'Allow', \
            f"Valid API key must result in Allow policy, got {statement['Effect']}"
        assert statement['Action'] == 'execute-api:Invoke', \
            "Policy action must be execute-api:Invoke"
        
        # Verify group name is passed in context
        assert 'context' in response, "Response must contain context"
        assert response['context']['group_name'] == group_name, \
            f"Group name must be preserved in context"
    
    @settings(max_examples=100)
    @given(
        stored_key=api_keys,
        provided_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_invalid_api_key_always_denies_request(
        self, mock_secrets, stored_key, provided_key, group_name, method_arn
    ):
        """
        Test that any invalid API key results in a Deny policy.
        
        For any API key that does NOT match the stored key in Secrets Manager,
        the authorizer must return a Deny policy (or raise an exception).
        This applies to all REST endpoints.
        """
        # Ensure keys are different
        if stored_key == provided_key:
            provided_key = provided_key + "X"  # Make them different
        
        # Mock Secrets Manager to return a different API key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        # Create REST API authorizer event with wrong API key
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': provided_key,
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer - should raise exception for invalid key
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            lambda_handler(event, None)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_missing_group_name_always_denies(
        self, mock_secrets, api_key, method_arn
    ):
        """
        Test that missing x-group-name header always results in denial.
        
        Even with a valid API key, if x-group-name is missing, the authorizer
        must deny the request. This applies to all REST endpoints.
        """
        # Mock Secrets Manager to return the API key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event without x-group-name
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key
                # Missing x-group-name
            }
        }
        
        # Execute authorizer - should raise exception for missing group_name
        with pytest.raises(Exception, match="Unauthorized.*Missing x-group-name"):
            lambda_handler(event, None)
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_secrets_manager_error_denies_request(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that Secrets Manager errors result in denial.
        
        If Secrets Manager fails to return the API key (network error, permission
        error, etc.), the authorizer must deny the request for security.
        """
        # Mock Secrets Manager to raise an error
        mock_secrets.get_secret_value.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetSecretValue'
        )
        
        # Create REST API authorizer event
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
    def test_policy_resource_matches_method_arn(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that the policy resource is derived from the method ARN.
        
        The generated policy should allow access to all routes in the API
        (using wildcard) to support caching across different routes.
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
        
        # Extract the API ARN (should be wildcard for caching)
        statement = response['policyDocument']['Statement'][0]
        resource = statement['Resource']
        
        # Resource should be a wildcard version of the method ARN
        # Format: arn:aws:execute-api:region:account:api-id/*
        assert resource.endswith('/*'), \
            f"Policy resource should use wildcard for caching, got {resource}"
        
        # Verify it's derived from the method ARN
        method_arn_parts = method_arn.split('/')
        expected_prefix = '/'.join(method_arn_parts[:2])
        assert resource.startswith(expected_prefix), \
            f"Policy resource should be derived from method ARN"
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_empty_api_key_denies_request(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that empty API key string results in denial.
        
        Even if x-group-name is provided, an empty API key must be rejected.
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event with empty API key
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': '',  # Empty string
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer - should raise exception for invalid key
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            lambda_handler(event, None)
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_null_headers_denies_request(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that null headers results in denial.
        
        If the headers are None or missing, the authorizer must deny.
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event with null headers
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': None  # Null
        }
        
        # Execute authorizer - should raise exception for missing group_name
        with pytest.raises(Exception, match="Unauthorized.*Missing x-group-name"):
            lambda_handler(event, None)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    def test_policy_structure_is_always_valid(
        self, api_key, group_name, method_arn
    ):
        """
        Test that generated policies always have valid structure.
        
        Regardless of input, the policy document must conform to IAM policy format.
        """
        # Generate policy directly
        policy = generate_policy('user', 'Allow', method_arn, group_name)
        
        # Verify structure
        assert 'principalId' in policy, "Policy must have principalId"
        assert 'policyDocument' in policy, "Policy must have policyDocument"
        assert 'context' in policy, "Policy must have context"
        
        policy_doc = policy['policyDocument']
        assert 'Version' in policy_doc, "Policy document must have Version"
        assert policy_doc['Version'] == '2012-10-17', "Version must be 2012-10-17"
        assert 'Statement' in policy_doc, "Policy document must have Statement"
        assert isinstance(policy_doc['Statement'], list), "Statement must be a list"
        assert len(policy_doc['Statement']) > 0, "Statement must not be empty"
        
        statement = policy_doc['Statement'][0]
        assert 'Action' in statement, "Statement must have Action"
        assert 'Effect' in statement, "Statement must have Effect"
        assert 'Resource' in statement, "Statement must have Resource"
        assert statement['Effect'] in ['Allow', 'Deny'], "Effect must be Allow or Deny"
        
        # Verify context
        assert policy['context']['group_name'] == group_name, \
            "Context must contain group_name"
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=st.text(min_size=0, max_size=0),  # Empty string
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_empty_group_name_denies_request(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that empty x-group-name string results in denial.
        
        Even with a valid API key, an empty x-group-name must be rejected.
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event with empty x-group-name
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key,
                'x-group-name': ''  # Empty string
            }
        }
        
        # Execute authorizer - should raise exception for missing group_name
        with pytest.raises(Exception, match="Unauthorized.*Missing x-group-name"):
            lambda_handler(event, None)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_header_case_insensitivity(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that header names are case-insensitive.
        
        The authorizer should accept headers with different casing
        (X-Api-Key, X-GROUP-NAME, etc.) as per HTTP standards.
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event with mixed-case headers
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'X-Api-Key': api_key,  # Mixed case
                'X-GROUP-NAME': group_name  # Upper case
            }
        }
        
        # Execute authorizer - should succeed
        response = lambda_handler(event, None)
        
        # Verify Allow policy is returned
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow'
        assert response['context']['group_name'] == group_name


class TestProperty1SecurityProperties:
    """
    Additional security properties for REST API key validation.
    
    These tests verify that the authorizer handles edge cases and
    security scenarios correctly across all REST endpoints.
    """
    
    @settings(max_examples=50)
    @given(
        stored_key=api_keys,
        method_arn=method_arns,
        malicious_input=st.text(min_size=1, max_size=1000)
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_malicious_input_safely_handled(
        self, mock_secrets, stored_key, method_arn, malicious_input
    ):
        """
        Test that malicious input is safely handled without crashes.
        
        The authorizer should handle any string input without raising
        unexpected exceptions (only authorization exceptions are expected).
        """
        # Mock Secrets Manager
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': stored_key})
        }
        
        # Create event with malicious input
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': malicious_input,
                'x-group-name': malicious_input
            }
        }
        
        # Execute authorizer - should either raise authorization exception or return policy
        try:
            response = lambda_handler(event, None)
            # If it returns, it should be a valid policy structure
            assert 'policyDocument' in response
            assert 'principalId' in response
        except Exception as e:
            # Should only raise authorization-related exceptions
            assert 'Unauthorized' in str(e), \
                f"Should only raise authorization exceptions, got: {str(e)}"
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_case_sensitive_api_key_validation(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that API key validation is case-sensitive.
        
        API keys with different casing should not match.
        """
        # Skip if API key is all same case
        if api_key.lower() == api_key or api_key.upper() == api_key:
            return
        
        # Mock Secrets Manager with lowercase key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key.lower()})
        }
        
        # Create event with uppercase key
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': api_key.upper(),
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer - should raise exception for invalid key
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            lambda_handler(event, None)
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_whitespace_in_api_key_not_ignored(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that whitespace in API keys is significant.
        
        API keys with leading/trailing whitespace should not match trimmed keys.
        """
        # Mock Secrets Manager with trimmed key
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': api_key})
        }
        
        # Create event with whitespace-padded key
        event = {
            'type': 'REQUEST',
            'methodArn': method_arn,
            'headers': {
                'x-api-key': f"  {api_key}  ",  # Add whitespace
                'x-group-name': group_name
            }
        }
        
        # Execute authorizer - should raise exception for invalid key
        with pytest.raises(Exception, match="Unauthorized.*Invalid API key"):
            lambda_handler(event, None)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names,
        method_arn=method_arns
    )
    @patch('lambdas.authorizer_rest.secrets_client')
    def test_authorization_applies_to_all_rest_endpoints(
        self, mock_secrets, api_key, group_name, method_arn
    ):
        """
        Test that authorization works consistently across all REST endpoints.
        
        The same authorization logic must apply to people-count, sensors,
        and bus-position endpoints (Requirements 1.7, 2.5, 3.7).
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
        
        # Verify Allow policy regardless of endpoint
        assert response['policyDocument']['Statement'][0]['Effect'] == 'Allow', \
            f"Authorization must work for all endpoints, failed for {method_arn}"
        
        # Verify the policy allows access to the API
        resource = response['policyDocument']['Statement'][0]['Resource']
        assert '/*' in resource, \
            "Policy must allow access to all routes in the API"
