"""
MCP Server Authentication Middleware for Madrid Bus Simulator.

This module implements authentication middleware that validates API keys
from request headers against AWS Secrets Manager. It uses the same API key
as the REST APIs for unified authentication.

Validates: Requirements 14.8, 14.9, 14.14
"""

import json
import logging
import os
from typing import Dict, Any, Optional, Callable, Awaitable
from functools import wraps
import boto3
from botocore.exceptions import ClientError


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthenticationMiddleware:
    """
    Authentication middleware for MCP server.
    
    Validates API keys from request headers against AWS Secrets Manager.
    Uses the same API key as REST APIs for unified authentication.
    """
    
    def __init__(self, secret_id: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize authentication middleware.
        
        Args:
            secret_id: AWS Secrets Manager secret ID (default: bus-simulator/api-key)
            region: AWS region for Secrets Manager (default: from env or eu-west-1)
        """
        self.secret_id = secret_id or os.getenv('SECRET_ID', 'bus-simulator/api-key')
        self.region = region or os.getenv('AWS_REGION', 'eu-west-1')
        
        # Initialize Secrets Manager client
        self.secrets_client = boto3.client('secretsmanager', region_name=self.region)
        
        # Cache for API key (to reduce Secrets Manager calls)
        self._cached_api_key: Optional[str] = None
        
        logger.info(f"Authentication middleware initialized with secret_id: {self.secret_id}")
    
    def get_api_key(self) -> str:
        """
        Retrieve API key from AWS Secrets Manager.
        
        Uses caching to reduce API calls. Cache is invalidated on errors.
        
        Returns:
            The API key string
            
        Raises:
            AuthenticationError: If unable to retrieve API key
        """
        # Return cached key if available
        if self._cached_api_key:
            return self._cached_api_key
        
        try:
            logger.info(f"Retrieving API key from Secrets Manager: {self.secret_id}")
            response = self.secrets_client.get_secret_value(SecretId=self.secret_id)
            secret_data = json.loads(response['SecretString'])
            api_key = secret_data.get('api_key')
            
            if not api_key:
                logger.error("API key not found in secret data")
                raise AuthenticationError("API key not found in Secrets Manager")
            
            # Cache the API key
            self._cached_api_key = api_key
            logger.info("API key retrieved and cached successfully")
            
            return api_key
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"Secrets Manager error ({error_code}): {e}")
            
            if error_code == 'ResourceNotFoundException':
                raise AuthenticationError(f"Secret not found: {self.secret_id}")
            elif error_code == 'AccessDeniedException':
                raise AuthenticationError("Access denied to Secrets Manager")
            else:
                raise AuthenticationError(f"Failed to retrieve API key: {error_code}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in secret: {e}")
            raise AuthenticationError("Invalid secret format")
            
        except Exception as e:
            logger.error(f"Unexpected error retrieving API key: {e}")
            raise AuthenticationError(f"Internal authentication error: {str(e)}")
    
    def validate_api_key(self, provided_key: str) -> bool:
        """
        Validate provided API key against stored key.
        
        Args:
            provided_key: API key from request header
            
        Returns:
            True if valid, False otherwise
        """
        try:
            stored_key = self.get_api_key()
            is_valid = provided_key == stored_key
            
            if is_valid:
                logger.info("API key validation successful")
            else:
                logger.warning("API key validation failed: key mismatch")
            
            return is_valid
            
        except AuthenticationError as e:
            logger.error(f"API key validation failed: {e}")
            return False
    
    def extract_api_key(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extract API key from request headers.
        
        Looks for 'x-api-key' header (case-insensitive).
        
        Args:
            headers: Request headers dictionary
            
        Returns:
            API key string or None if not found
        """
        # Normalize headers to lowercase for case-insensitive lookup
        headers_lower = {k.lower(): v for k, v in headers.items()}
        api_key = headers_lower.get('x-api-key')
        
        if api_key:
            logger.debug("API key found in request headers")
        else:
            logger.warning("API key not found in request headers")
        
        return api_key
    
    def extract_group_name(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extract group name from request headers.
        
        Looks for 'x-group-name' header (case-insensitive).
        
        Args:
            headers: Request headers dictionary
            
        Returns:
            Group name string or None if not found
        """
        # Normalize headers to lowercase for case-insensitive lookup
        headers_lower = {k.lower(): v for k, v in headers.items()}
        group_name = headers_lower.get('x-group-name')
        
        if group_name:
            logger.debug(f"Group name found in request headers: {group_name}")
        else:
            logger.warning("Group name not found in request headers")
        
        return group_name
    
    def authenticate_request(self, headers: Dict[str, str]) -> None:
        """
        Authenticate a request by validating API key and group name from headers.
        
        Args:
            headers: Request headers dictionary
            
        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("Authenticating request")
        
        # Extract API key from headers
        api_key = self.extract_api_key(headers)
        
        if not api_key:
            logger.warning("Authentication failed: Missing API key")
            raise AuthenticationError("Missing x-api-key header")
        
        # Extract group name from headers
        group_name = self.extract_group_name(headers)
        
        if not group_name:
            logger.warning("Authentication failed: Missing group name")
            raise AuthenticationError("Missing x-group-name header")
        
        # Validate API key
        if not self.validate_api_key(api_key):
            logger.warning("Authentication failed: Invalid API key")
            raise AuthenticationError("Invalid API key")
        
        logger.info(f"Request authenticated successfully for group: {group_name}")
    
    def invalidate_cache(self) -> None:
        """
        Invalidate the cached API key.
        
        Useful for testing or when key rotation is detected.
        """
        logger.info("Invalidating API key cache")
        self._cached_api_key = None


def require_authentication(middleware: AuthenticationMiddleware):
    """
    Decorator to require authentication for MCP tool handlers.
    
    Usage:
        @require_authentication(auth_middleware)
        async def my_tool_handler(headers: Dict, **kwargs):
            # Tool implementation
            pass
    
    Args:
        middleware: AuthenticationMiddleware instance
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract headers from kwargs (expected to be passed by caller)
            headers = kwargs.get('headers', {})
            
            try:
                # Authenticate the request
                middleware.authenticate_request(headers)
                
                # Call the original function
                return await func(*args, **kwargs)
                
            except AuthenticationError as e:
                # Log authentication failure
                logger.error(f"Authentication failed: {e}")
                
                # Return error response
                return {
                    "success": False,
                    "error": f"Authentication failed: {str(e)}",
                    "status_code": 401
                }
        
        return wrapper
    return decorator


# Global middleware instance (can be initialized once and reused)
_global_middleware: Optional[AuthenticationMiddleware] = None


def get_auth_middleware(secret_id: Optional[str] = None, 
                       region: Optional[str] = None) -> AuthenticationMiddleware:
    """
    Get or create global authentication middleware instance.
    
    Args:
        secret_id: AWS Secrets Manager secret ID
        region: AWS region
        
    Returns:
        AuthenticationMiddleware instance
    """
    global _global_middleware
    
    if _global_middleware is None:
        _global_middleware = AuthenticationMiddleware(secret_id, region)
    
    return _global_middleware
