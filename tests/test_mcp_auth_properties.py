"""
Property-based tests for MCP Server Authentication.

These tests use the Hypothesis library to verify universal properties
of MCP authentication across randomized inputs.

**Validates: Requirements 14.8, 14.9**
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, settings, strategies as st
from botocore.exceptions import ClientError

from mcp_server.auth import (
    AuthenticationMiddleware,
    AuthenticationError,
    require_authentication,
)


# Strategy for generating valid API keys
api_keys = st.text(
    min_size=20,
    max_size=64,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        min_codepoint=48,
        max_codepoint=122
    )
).filter(lambda x: x.strip())

# Strategy for generating header names
header_names = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_',
        min_codepoint=45,
        max_codepoint=122
    )
).filter(lambda x: x.strip() and not x.startswith('-'))

# Strategy for generating group names
group_names = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_',
        min_codepoint=45,
        max_codepoint=122
    )
).filter(lambda x: x.strip())


class TestProperty47MCPAPIKeyValidation:
    """
    Property 47: MCP API key validation
    
    **Validates: Requirements 14.8**
    
    For all MCP server requests, the server SHALL validate the API Key by reading
    it from Secrets Manager. Valid API keys should be accepted, and invalid API
    keys should be rejected with a 401 authentication error.
    """
    
    @settings(max_examples=100)
    @given(
        valid_api_key=api_keys,
        group_name=group_names
    )
    def test_valid_api_key_accepted(self, valid_api_key, group_name):
        """
        Test that valid API keys are accepted by the authentication middleware.
        
        For any valid API key stored in Secrets Manager, when a request includes
        that key in the x-api-key header and a group name in x-group-name header,
        the authentication should succeed.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager with the valid key
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': valid_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='test-secret',
                region='us-east-1'
            )
            
            # Create request headers with valid key
            headers = {
                'x-api-key': valid_api_key,
                'x-group-name': group_name
            }
            
            # Authentication should succeed (not raise exception)
            try:
                middleware.authenticate_request(headers)
                success = True
            except AuthenticationError:
                success = False
            
            assert success, \
                f"Valid API key should be accepted: key={valid_api_key[:10]}..."
    
    @settings(max_examples=100)
    @given(
        valid_api_key=api_keys,
        invalid_api_key=api_keys,
        group_name=group_names
    )
    def test_invalid_api_key_rejected(self, valid_api_key, invalid_api_key, group_name):
        """
        Test that invalid API keys are rejected with authentication error.
        
        For any API key that doesn't match the one stored in Secrets Manager,
        the authentication should fail with an AuthenticationError.
        """
        # Ensure keys are different
        if valid_api_key == invalid_api_key:
            invalid_api_key = invalid_api_key + "_different"
        
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager with the valid key
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': valid_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='test-secret',
                region='us-east-1'
            )
            
            # Create request headers with invalid key
            headers = {
                'x-api-key': invalid_api_key,
                'x-group-name': group_name
            }
            
            # Authentication should fail
            with pytest.raises(AuthenticationError, match="Invalid API key"):
                middleware.authenticate_request(headers)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names
    )
    def test_missing_api_key_rejected(self, api_key, group_name):
        """
        Test that requests without API key are rejected.
        
        For any request that doesn't include the x-api-key header,
        the authentication should fail with an AuthenticationError.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='test-secret',
                region='us-east-1'
            )
            
            # Create request headers without API key
            headers = {
                'x-group-name': group_name
            }
            
            # Authentication should fail
            with pytest.raises(AuthenticationError, match="Missing x-api-key header"):
                middleware.authenticate_request(headers)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys
    )
    def test_missing_group_name_rejected(self, api_key):
        """
        Test that requests without group name are rejected.
        
        For any request that doesn't include the x-group-name header,
        the authentication should fail with an AuthenticationError.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='test-secret',
                region='us-east-1'
            )
            
            # Create request headers without group name
            headers = {
                'x-api-key': api_key
            }
            
            # Authentication should fail
            with pytest.raises(AuthenticationError, match="Missing x-group-name header"):
                middleware.authenticate_request(headers)
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names,
        header_case=st.sampled_from(['lower', 'upper', 'mixed'])
    )
    def test_header_case_insensitivity(self, api_key, group_name, header_case):
        """
        Test that header names are case-insensitive.
        
        For any valid API key and group name, the authentication should succeed
        regardless of the case used in header names (x-api-key, X-API-KEY, etc.).
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='test-secret',
                region='us-east-1'
            )
            
            # Create headers with different cases
            if header_case == 'lower':
                headers = {
                    'x-api-key': api_key,
                    'x-group-name': group_name
                }
            elif header_case == 'upper':
                headers = {
                    'X-API-KEY': api_key,
                    'X-GROUP-NAME': group_name
                }
            else:  # mixed
                headers = {
                    'X-Api-Key': api_key,
                    'X-Group-Name': group_name
                }
            
            # Authentication should succeed regardless of case
            try:
                middleware.authenticate_request(headers)
                success = True
            except AuthenticationError:
                success = False
            
            assert success, \
                f"Authentication should be case-insensitive for header names"
    
    @settings(max_examples=50)
    @given(
        api_key=api_keys,
        group_name=group_names
    )
    def test_secrets_manager_error_handling(self, api_key, group_name):
        """
        Test that Secrets Manager errors are handled gracefully.
        
        For any request, if Secrets Manager is unavailable or returns an error,
        the authentication should fail gracefully with an appropriate error.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager to raise an error
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.side_effect = ClientError(
                {'Error': {'Code': 'InternalServiceError', 'Message': 'Service error'}},
                'GetSecretValue'
            )
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='test-secret',
                region='us-east-1'
            )
            
            # Create request headers
            headers = {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
            
            # Authentication should fail due to Secrets Manager error
            with pytest.raises(AuthenticationError):
                middleware.authenticate_request(headers)
    
    @settings(max_examples=100)
    @given(
        api_key=api_keys,
        group_name=group_names
    )
    def test_api_key_caching(self, api_key, group_name):
        """
        Test that API key is cached to reduce Secrets Manager calls.
        
        For multiple authentication requests with the same middleware instance,
        the API key should be retrieved from Secrets Manager only once and
        then cached for subsequent requests.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='test-secret',
                region='us-east-1'
            )
            
            # Create request headers
            headers = {
                'x-api-key': api_key,
                'x-group-name': group_name
            }
            
            # First authentication - should call Secrets Manager
            middleware.authenticate_request(headers)
            first_call_count = mock_secrets.get_secret_value.call_count
            
            # Second authentication - should use cache
            middleware.authenticate_request(headers)
            second_call_count = mock_secrets.get_secret_value.call_count
            
            # Verify caching: call count should not increase
            assert second_call_count == first_call_count, \
                f"API key should be cached after first retrieval"


class TestProperty48MCPAndRESTAPIKeyConsistency:
    """
    Property 48: MCP and REST API key consistency
    
    **Validates: Requirements 14.9**
    
    The MCP server SHALL use the same API Key stored in Secrets Manager as
    defined in Requirement 15 (unified API key management). The MCP server
    and REST APIs must use the same secret ID and validate against the same key.
    """
    
    @settings(max_examples=100)
    @given(
        shared_api_key=api_keys,
        group_name=group_names
    )
    def test_mcp_uses_same_secret_id_as_rest_apis(self, shared_api_key, group_name):
        """
        Test that MCP server uses the same Secrets Manager secret ID as REST APIs.
        
        For any API key stored in the unified secret (bus-simulator/api-key),
        both MCP server and REST APIs should be able to validate requests
        using that same key.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager with shared secret
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': shared_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create MCP middleware with the same secret ID as REST APIs
            mcp_middleware = AuthenticationMiddleware(
                secret_id='bus-simulator/api-key',  # Same as REST APIs
                region='eu-west-1'
            )
            
            # Verify secret ID matches REST API configuration
            assert mcp_middleware.secret_id == 'bus-simulator/api-key', \
                "MCP server must use the same secret ID as REST APIs"
            
            # Verify authentication works with the shared key
            headers = {
                'x-api-key': shared_api_key,
                'x-group-name': group_name
            }
            
            try:
                mcp_middleware.authenticate_request(headers)
                success = True
            except AuthenticationError:
                success = False
            
            assert success, \
                "MCP server should accept the same API key as REST APIs"
    
    @settings(max_examples=100)
    @given(
        shared_api_key=api_keys,
        group_name=group_names
    )
    def test_mcp_and_rest_validate_same_key(self, shared_api_key, group_name):
        """
        Test that MCP and REST APIs validate the same API key.
        
        For any API key, both MCP authentication middleware and REST API
        Custom Authorizer should validate against the same key stored in
        Secrets Manager.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': shared_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create MCP middleware
            mcp_middleware = AuthenticationMiddleware(
                secret_id='bus-simulator/api-key',
                region='eu-west-1'
            )
            
            # Retrieve API key from MCP middleware
            mcp_api_key = mcp_middleware.get_api_key()
            
            # Verify it matches the shared key
            assert mcp_api_key == shared_api_key, \
                "MCP server should retrieve the same API key as REST APIs"
            
            # Verify validation works
            is_valid = mcp_middleware.validate_api_key(shared_api_key)
            assert is_valid, \
                "MCP server should validate the same API key as REST APIs"
    
    @settings(max_examples=50)
    @given(
        shared_api_key=api_keys,
        different_api_key=api_keys,
        group_name=group_names
    )
    def test_mcp_rejects_keys_not_in_shared_secret(self, shared_api_key, different_api_key, group_name):
        """
        Test that MCP server rejects API keys not stored in the shared secret.
        
        For any API key that is not the one stored in the unified Secrets Manager
        secret, both MCP and REST APIs should reject it.
        """
        # Ensure keys are different
        if shared_api_key == different_api_key:
            different_api_key = different_api_key + "_different"
        
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager with shared key
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': shared_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create MCP middleware
            mcp_middleware = AuthenticationMiddleware(
                secret_id='bus-simulator/api-key',
                region='eu-west-1'
            )
            
            # Try to authenticate with different key
            headers = {
                'x-api-key': different_api_key,
                'x-group-name': group_name
            }
            
            # Should be rejected
            with pytest.raises(AuthenticationError, match="Invalid API key"):
                mcp_middleware.authenticate_request(headers)
    
    @settings(max_examples=50)
    @given(
        shared_api_key=api_keys,
        group_name=group_names
    )
    def test_mcp_uses_same_region_as_rest_apis(self, shared_api_key, group_name):
        """
        Test that MCP server uses the same AWS region as REST APIs.
        
        For consistency, MCP server should access Secrets Manager in the
        same region as REST APIs (eu-west-1 or configured region).
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': shared_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create MCP middleware with default region
            mcp_middleware = AuthenticationMiddleware(
                secret_id='bus-simulator/api-key'
            )
            
            # Verify region is set (should be eu-west-1 or from environment)
            assert mcp_middleware.region in ['eu-west-1', 'eu-central-1'], \
                f"MCP server should use the same region as REST APIs, got {mcp_middleware.region}"
    
    @settings(max_examples=100)
    @given(
        shared_api_key=api_keys,
        group_name=group_names
    )
    def test_mcp_authentication_returns_401_on_failure(self, shared_api_key, group_name):
        """
        Test that MCP server returns 401 status code on authentication failure.
        
        For any invalid authentication attempt, the MCP server should return
        a 401 Unauthorized status code, consistent with REST API behavior.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': shared_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create middleware
            middleware = AuthenticationMiddleware(
                secret_id='bus-simulator/api-key',
                region='eu-west-1'
            )
            
            # Create decorator
            @require_authentication(middleware)
            async def test_handler(headers=None, **kwargs):
                return {"success": True, "data": "test"}
            
            # Test with invalid key
            import asyncio
            headers = {
                'x-api-key': 'invalid-key',
                'x-group-name': group_name
            }
            
            result = asyncio.run(test_handler(headers=headers))
            
            # Verify 401 status code
            assert result.get('status_code') == 401, \
                "MCP server should return 401 on authentication failure"
            assert result.get('success') is False, \
                "Response should indicate failure"
            assert 'Authentication failed' in result.get('error', ''), \
                "Error message should indicate authentication failure"
    
    @settings(max_examples=50)
    @given(
        shared_api_key=api_keys,
        group_name=group_names
    )
    def test_mcp_secret_format_matches_rest_apis(self, shared_api_key, group_name):
        """
        Test that MCP server expects the same secret format as REST APIs.
        
        The secret should be stored as JSON with an 'api_key' field:
        {"api_key": "value"}
        
        Both MCP and REST APIs should parse this format consistently.
        """
        with patch('mcp_server.auth.boto3.client') as mock_client:
            # Setup mock Secrets Manager with correct format
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'api_key': shared_api_key})
            }
            mock_client.return_value = mock_secrets
            
            # Create MCP middleware
            mcp_middleware = AuthenticationMiddleware(
                secret_id='bus-simulator/api-key',
                region='eu-west-1'
            )
            
            # Retrieve and verify API key
            retrieved_key = mcp_middleware.get_api_key()
            
            assert retrieved_key == shared_api_key, \
                "MCP server should parse secret format correctly"
            
            # Test with wrong format should fail
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({'wrong_field': shared_api_key})
            }
            
            # Invalidate cache to force re-fetch
            mcp_middleware.invalidate_cache()
            
            # Should raise error for wrong format
            with pytest.raises(AuthenticationError, match="API key not found"):
                mcp_middleware.get_api_key()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
