# MCP Server Authentication Implementation

## Overview

This document describes the authentication middleware implementation for the MCP server, which validates API keys from request headers against AWS Secrets Manager.

## Implementation Details

### File: `mcp_server/auth.py`

The authentication middleware provides the following functionality:

#### 1. AuthenticationMiddleware Class

**Purpose**: Validates API keys from request headers against AWS Secrets Manager.

**Key Features**:
- Retrieves API key from AWS Secrets Manager (secret ID: `bus-simulator/api-key`)
- Caches API key to reduce Secrets Manager API calls
- Validates API keys from request headers (x-api-key header)
- Case-insensitive header extraction
- Comprehensive error handling and logging

**Methods**:
- `get_api_key()`: Retrieves API key from Secrets Manager with caching
- `validate_api_key(provided_key)`: Validates provided key against stored key
- `extract_api_key(headers)`: Extracts API key from request headers (case-insensitive)
- `authenticate_request(headers)`: Authenticates a request by validating API key
- `invalidate_cache()`: Invalidates cached API key

#### 2. Authentication Decorator

**Function**: `require_authentication(middleware)`

**Purpose**: Decorator to require authentication for MCP tool handlers.

**Usage**:
```python
@require_authentication(auth_middleware)
async def my_tool_handler(headers: Dict, **kwargs):
    # Tool implementation
    pass
```

#### 3. Global Middleware Instance

**Function**: `get_auth_middleware(secret_id, region)`

**Purpose**: Get or create global authentication middleware instance (singleton pattern).

## Integration with MCP Server

The authentication middleware is integrated into the MCP server (`mcp_server/server.py`):

1. **Initialization**: AuthenticationMiddleware is initialized when the MCP server starts
2. **Request Validation**: All tool requests are authenticated before processing
3. **Error Handling**: Authentication failures return 401 status with descriptive error messages

### Authentication Flow

```
1. Client sends MCP tool request with x-api-key header
2. MCP server extracts headers from request
3. AuthenticationMiddleware.authenticate_request(headers) is called
4. Middleware extracts API key from headers
5. Middleware retrieves stored API key from Secrets Manager (or cache)
6. Middleware compares provided key with stored key
7. If valid: Request proceeds to tool handler
8. If invalid: 401 error response is returned
```

## Error Handling

The middleware handles the following error scenarios:

- **Missing API Key**: Returns "Missing x-api-key header" error
- **Invalid API Key**: Returns "Invalid API key" error
- **Secrets Manager Errors**:
  - ResourceNotFoundException: "Secret not found"
  - AccessDeniedException: "Access denied to Secrets Manager"
  - Other errors: "Failed to retrieve API key"
- **Invalid Secret Format**: "Invalid secret format" (JSON parsing error)

## Logging

The middleware logs the following events:

- Authentication middleware initialization
- API key retrieval from Secrets Manager
- API key caching
- Authentication attempts (success/failure)
- Header extraction (success/failure)
- Secrets Manager errors

## API Key Consistency

The MCP server uses the **same API key** as the REST APIs:

- **Secret ID**: `bus-simulator/api-key`
- **Secret Format**: `{"api_key": "<key-value>"}`
- **Region**: Configurable (default: `eu-west-1`)

This ensures unified authentication across all APIs (REST and MCP).

## Requirements Validated

This implementation validates the following requirements:

- **Requirement 14.8**: MCP server validates API Key by reading it from Secrets_Manager
- **Requirement 14.9**: MCP server uses the same API Key stored in Secrets_Manager as defined in Requirement 15
- **Requirement 14.14**: MCP server implements authentication middleware that validates the API Key before processing any tool requests

## Testing

The authentication middleware has been tested with the following scenarios:

1. ✓ Initialization with custom and default parameters
2. ✓ API key retrieval from Secrets Manager
3. ✓ API key caching
4. ✓ API key validation (valid and invalid keys)
5. ✓ Header extraction (present, missing, case-insensitive)
6. ✓ Request authentication (valid, invalid, missing key)
7. ✓ Cache invalidation
8. ✓ Error handling (Secrets Manager errors, invalid JSON)
9. ✓ Decorator functionality
10. ✓ End-to-end authentication flow
11. ✓ API key consistency with REST APIs

All tests passed successfully.

## Security Considerations

1. **API Key Storage**: API keys are stored securely in AWS Secrets Manager
2. **Caching**: API keys are cached in memory to reduce API calls, but can be invalidated
3. **Logging**: Authentication failures are logged for security monitoring
4. **Error Messages**: Error messages are descriptive but don't leak sensitive information
5. **Case-Insensitive Headers**: Header extraction is case-insensitive for compatibility

## Future Enhancements

Potential improvements for future versions:

1. **Key Rotation**: Automatic detection and handling of API key rotation
2. **Rate Limiting**: Add rate limiting for authentication attempts
3. **Audit Logging**: Enhanced audit logging for compliance
4. **Multiple Keys**: Support for multiple API keys with different permissions
5. **Token Expiration**: Add support for time-limited tokens

## Conclusion

The MCP server authentication middleware is fully implemented and tested. It provides secure, unified authentication using AWS Secrets Manager, ensuring consistency with REST APIs and meeting all specified requirements.
