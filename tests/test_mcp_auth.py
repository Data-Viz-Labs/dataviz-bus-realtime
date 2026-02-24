"""
Unit tests for MCP Server Authentication Middleware.

Tests authentication logic, API key validation, and error handling.

Validates: Requirements 14.8, 14.9, 14.14
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError

from mcp_server.auth import (
    AuthenticationMiddleware,
    AuthenticationError,
    require_authentication,
    get_auth_middleware
)


@pytest.fixture
def mock_secrets_client():
    """Create a mock Secrets Manager client."""
    with patch('mcp_server.auth.boto3.client') as mock_client:
        mock_secrets = MagicMock()
        mock_client.return_value = mock_secrets
        yield mock_secrets


@pytest.fixture
def auth_middleware(mock_secrets_client):
    """Create an AuthenticationMiddleware instance with mocked Secrets Manager."""
    middleware = AuthenticationMiddleware(
        secret_id='test-secret',
        region='us-east-1'
    )
    return middleware


def test_initialization(auth_middleware):
    """Test middleware initialization with custom parameters."""
    assert auth_middleware.secret_id == 'test-secret'
    assert auth_middleware.region == 'us-east-1'
    assert auth_middleware._cached_api_key is None


def test_initialization_with_defaults(mock_secrets_client):
    """Test middleware initialization with default parameters."""
    with patch.dict('os.environ', {
        'SECRET_ID': 'env-secret',
        'AWS_REGION': 'eu-west-1'
    }):
        middleware = AuthenticationMiddleware()
        assert middleware.secret_id == 'env-secret'
        assert middleware.region == 'eu-west-1'


def test_get_api_key_success(auth_middleware, mock_secrets_client):
    """Test successful API key retrieval from Secrets Manager."""
    # Mock successful response
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({'api_key': 'test-api-key-123'})
    }
    
    api_key = auth_middleware.get_api_key()
    
    assert api_key == 'test-api-key-123'
    assert auth_middleware._cached_api_key == 'test-api-key-123'
    mock_secrets_client.get_secret_value.assert_called_once_with(
        SecretId='test-secret'
    )


def test_get_api_key_uses_cache(auth_middleware, mock_secrets_client):
    """Test that cached API key is used on subsequent calls."""
    # Set up cache
    auth_middleware._cached_api_key = 'cached-key'
    
    api_key = auth_middleware.get_api_key()
    
    assert api_key == 'cached-key'
    # Should not call Secrets Manager
    mock_secrets_client.get_secret_value.assert_not_called()


def test_get_api_key_missing_in_secret(auth_middleware, mock_secrets_client):
    """Test error when API key is missing from secret data."""
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({'other_field': 'value'})
    }
    
    with pytest.raises(AuthenticationError, match="API key not found in Secrets Manager"):
        auth_middleware.get_api_key()


def test_get_api_key_resource_not_found(auth_middleware, mock_secrets_client):
    """Test error when secret does not exist."""
    mock_secrets_client.get_secret_value.side_effect = ClientError(
        {'Error': {'Code': 'ResourceNotFoundException', 'Message': 'Secret not found'}},
        'GetSecretValue'
    )
    
    with pytest.raises(AuthenticationError, match="Secret not found"):
        auth_middleware.get_api_key()


def test_get_api_key_access_denied(auth_middleware, mock_secrets_client):
    """Test error when access to Secrets Manager is denied."""
    mock_secrets_client.get_secret_value.side_effect = ClientError(
        {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
        'GetSecretValue'
    )
    
    with pytest.raises(AuthenticationError, match="Access denied to Secrets Manager"):
        auth_middleware.get_api_key()


def test_get_api_key_invalid_json(auth_middleware, mock_secrets_client):
    """Test error when secret contains invalid JSON."""
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': 'invalid-json{'
    }
    
    with pytest.raises(AuthenticationError, match="Invalid secret format"):
        auth_middleware.get_api_key()


def test_validate_api_key_success(auth_middleware, mock_secrets_client):
    """Test successful API key validation."""
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({'api_key': 'correct-key'})
    }
    
    is_valid = auth_middleware.validate_api_key('correct-key')
    
    assert is_valid is True


def test_validate_api_key_failure(auth_middleware, mock_secrets_client):
    """Test API key validation failure with wrong key."""
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({'api_key': 'correct-key'})
    }
    
    is_valid = auth_middleware.validate_api_key('wrong-key')
    
    assert is_valid is False


def test_validate_api_key_secrets_error(auth_middleware, mock_secrets_client):
    """Test API key validation when Secrets Manager fails."""
    mock_secrets_client.get_secret_value.side_effect = ClientError(
        {'Error': {'Code': 'InternalError', 'Message': 'Internal error'}},
        'GetSecretValue'
    )
    
    is_valid = auth_middleware.validate_api_key('any-key')
    
    assert is_valid is False


def test_extract_api_key_present(auth_middleware):
    """Test extracting API key from headers when present."""
    headers = {'x-api-key': 'test-key-123'}
    
    api_key = auth_middleware.extract_api_key(headers)
    
    assert api_key == 'test-key-123'


def test_extract_api_key_case_insensitive(auth_middleware):
    """Test extracting API key with different case headers."""
    headers = {'X-API-KEY': 'test-key-123'}
    
    api_key = auth_middleware.extract_api_key(headers)
    
    assert api_key == 'test-key-123'


def test_extract_api_key_missing(auth_middleware):
    """Test extracting API key when not present in headers."""
    headers = {'other-header': 'value'}
    
    api_key = auth_middleware.extract_api_key(headers)
    
    assert api_key is None


def test_authenticate_request_success(auth_middleware, mock_secrets_client):
    """Test successful request authentication."""
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({'api_key': 'valid-key'})
    }
    headers = {'x-api-key': 'valid-key'}
    
    # Should not raise exception
    auth_middleware.authenticate_request(headers)


def test_authenticate_request_missing_key(auth_middleware):
    """Test authentication failure when API key is missing."""
    headers = {}
    
    with pytest.raises(AuthenticationError, match="Missing x-api-key header"):
        auth_middleware.authenticate_request(headers)


def test_authenticate_request_invalid_key(auth_middleware, mock_secrets_client):
    """Test authentication failure with invalid API key."""
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({'api_key': 'valid-key'})
    }
    headers = {'x-api-key': 'invalid-key'}
    
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        auth_middleware.authenticate_request(headers)


def test_invalidate_cache(auth_middleware):
    """Test cache invalidation."""
    auth_middleware._cached_api_key = 'cached-key'
    
    auth_middleware.invalidate_cache()
    
    assert auth_middleware._cached_api_key is None


@pytest.mark.asyncio
async def test_decorator_success():
    """Test decorator allows request with valid authentication."""
    mock_middleware = Mock(spec=AuthenticationMiddleware)
    mock_middleware.authenticate_request.return_value = None
    
    @require_authentication(mock_middleware)
    async def test_handler(headers=None, **kwargs):
        return {"success": True, "data": "test"}
    
    result = await test_handler(headers={'x-api-key': 'valid-key'})
    
    assert result == {"success": True, "data": "test"}
    mock_middleware.authenticate_request.assert_called_once()


@pytest.mark.asyncio
async def test_decorator_authentication_failure():
    """Test decorator rejects request with invalid authentication."""
    mock_middleware = Mock(spec=AuthenticationMiddleware)
    mock_middleware.authenticate_request.side_effect = AuthenticationError("Invalid key")
    
    @require_authentication(mock_middleware)
    async def test_handler(headers=None, **kwargs):
        return {"success": True, "data": "test"}
    
    result = await test_handler(headers={'x-api-key': 'invalid-key'})
    
    assert result["success"] is False
    assert "Authentication failed" in result["error"]
    assert result["status_code"] == 401


def test_get_auth_middleware_creates_instance():
    """Test that get_auth_middleware creates a new instance."""
    with patch('mcp_server.auth.boto3.client'):
        # Reset global instance
        import mcp_server.auth
        mcp_server.auth._global_middleware = None
        
        middleware = get_auth_middleware('test-secret', 'us-east-1')
        
        assert middleware is not None
        assert isinstance(middleware, AuthenticationMiddleware)


def test_get_auth_middleware_returns_same_instance():
    """Test that get_auth_middleware returns the same instance on subsequent calls."""
    with patch('mcp_server.auth.boto3.client'):
        # Reset global instance
        import mcp_server.auth
        mcp_server.auth._global_middleware = None
        
        middleware1 = get_auth_middleware('test-secret', 'us-east-1')
        middleware2 = get_auth_middleware('test-secret', 'us-east-1')
        
        assert middleware1 is middleware2


@pytest.mark.asyncio
async def test_end_to_end_authentication_flow():
    """Test complete authentication flow from request to validation."""
    with patch('mcp_server.auth.boto3.client') as mock_client:
        # Setup mock Secrets Manager
        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'integration-test-key'})
        }
        mock_client.return_value = mock_secrets
        
        # Create middleware
        middleware = AuthenticationMiddleware(
            secret_id='integration-secret',
            region='us-east-1'
        )
        
        # Test valid authentication
        headers = {'x-api-key': 'integration-test-key'}
        middleware.authenticate_request(headers)  # Should not raise
        
        # Test invalid authentication
        invalid_headers = {'x-api-key': 'wrong-key'}
        with pytest.raises(AuthenticationError):
            middleware.authenticate_request(invalid_headers)


def test_api_key_consistency_with_rest_apis():
    """Test that MCP server uses the same API key as REST APIs."""
    with patch('mcp_server.auth.boto3.client') as mock_client:
        # Setup mock Secrets Manager
        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.return_value = {
            'SecretString': json.dumps({'api_key': 'shared-api-key'})
        }
        mock_client.return_value = mock_secrets
        
        # Create middleware with same secret ID as REST APIs
        middleware = AuthenticationMiddleware(
            secret_id='bus-simulator/api-key',
            region='eu-west-1'
        )
        
        # Retrieve API key
        api_key = middleware.get_api_key()
        
        # Verify it's the shared key
        assert api_key == 'shared-api-key'
        
        # Verify secret ID matches REST API configuration
        assert middleware.secret_id == 'bus-simulator/api-key'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
