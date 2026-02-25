# Testing Strategy

This document describes the testing strategy for the Madrid Bus Real-Time Simulator project.

## Test Pyramid

The project follows a test pyramid approach with three levels of testing:

```
        /\
       /  \
      / E2E \      ← End-to-End Tests (Shell Scripts)
     /------\
    /  INT   \     ← Integration Tests (Python + AWS)
   /----------\
  /   UNIT     \   ← Unit Tests (Python, Local)
 /--------------\
```

## Test Levels

### 1. Unit Tests (Local, No AWS)

**Purpose**: Test individual components in isolation without external dependencies.

**Technology**: Python + pytest

**Location**: `tests/` directory

**Run with**: `make test-unit`

**Characteristics**:
- Fast execution (< 1 minute)
- No AWS credentials required
- No network calls
- Uses mocks for external dependencies
- Tests business logic, data models, utilities

**Examples**:
- Data model validation
- Route calculations
- Time-based patterns
- Configuration parsing
- Property-based tests (Hypothesis)

**Command**:
```bash
make test-unit
```

### 2. Integration Tests (Python + AWS)

**Purpose**: Test components interacting with real AWS services.

**Technology**: Python + pytest + boto3

**Location**: `tests/` directory (marked with `@pytest.mark.integration`)

**Run with**: `make test-int`

**Characteristics**:
- Moderate execution time (5-10 minutes)
- Requires AWS credentials
- Tests against real AWS services
- May incur small AWS costs
- Tests data persistence, API integration, service communication

**Examples**:
- Timestream write/query operations
- Secrets Manager access
- Lambda function invocations
- DynamoDB operations
- EventBridge event publishing
- MCP server functionality

**Prerequisites**:
- AWS CLI configured (`aws configure`)
- Infrastructure deployed
- Appropriate IAM permissions

**Command**:
```bash
make test-int
```

### 3. End-to-End Tests (Shell Scripts)

**Purpose**: Test complete user workflows through public APIs.

**Technology**: Bash + curl + jq

**Location**: `tests/api/` directory

**Run with**: `make test-e2e`

**Characteristics**:
- Slow execution (10-15 minutes)
- Tests deployed infrastructure
- Simulates real user interactions
- Validates API contracts
- Tests authentication and authorization
- Automatic configuration from Terraform

**Examples**:
- REST API queries (People Count, Sensors, Bus Position)
- WebSocket subscriptions
- MCP server tools
- Authentication flows
- Error handling
- API key validation

**Prerequisites**:
- AWS CLI configured
- Infrastructure deployed
- curl and jq installed

**Command**:
```bash
make test-e2e
```

## Running Tests

### Quick Start

```bash
# Run all tests
make test-all

# Run specific test level
make test-unit      # Unit tests only
make test-int       # Integration tests only
make test-e2e       # End-to-end tests only
```

### Development Workflow

1. **During Development** - Run unit tests frequently:
   ```bash
   make test-unit
   ```

2. **Before Commit** - Run unit + integration tests:
   ```bash
   make test-unit && make test-int
   ```

3. **Before Deployment** - Run all tests:
   ```bash
   make test-all
   ```

4. **After Deployment** - Run E2E tests to verify:
   ```bash
   make test-e2e
   ```

## Test Configuration

### Unit Tests

No configuration needed - tests run locally.

### Integration Tests

Requires AWS credentials:
```bash
aws configure
```

### End-to-End Tests

**Automatic Configuration** (Recommended):
- API key retrieved from Secrets Manager
- API URLs retrieved from Terraform outputs
- AWS region auto-detected

**Manual Override** (Optional):
```bash
export API_KEY="your-api-key"
export GROUP_NAME="your-group"
export AWS_REGION="eu-west-1"
```

## Test Markers (pytest)

Tests can be marked with pytest markers:

```python
import pytest

# Unit test (default)
def test_route_calculation():
    pass

# Integration test
@pytest.mark.integration
def test_timestream_write():
    pass

# End-to-end test
@pytest.mark.e2e
def test_api_endpoint():
    pass
```

Run specific markers:
```bash
pytest -m "integration"        # Integration tests only
pytest -m "not integration"    # Exclude integration tests
```

## Continuous Integration

### Pre-commit Hooks

Install pre-commit hooks:
```bash
make setup-hooks
```

Hooks run automatically before each commit:
- Terraform formatting
- Infracost cost estimation
- Python linting (if configured)

### CI/CD Pipeline

Recommended pipeline stages:

1. **Build Stage**:
   - Package Lambda functions
   - Build container images
   - Run unit tests

2. **Test Stage**:
   - Deploy to test environment
   - Run integration tests
   - Run E2E tests

3. **Deploy Stage**:
   - Deploy to production
   - Run smoke tests
   - Monitor metrics

## Test Coverage

### Current Coverage

- **Unit Tests**: Core business logic, data models, utilities
- **Integration Tests**: AWS service interactions, MCP server
- **E2E Tests**: All public APIs, authentication, error handling

### Coverage Goals

- Unit tests: > 80% code coverage
- Integration tests: All AWS service interactions
- E2E tests: All API endpoints and user workflows

## Troubleshooting

### Unit Tests Failing

**Issue**: Import errors or missing dependencies

**Solution**:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Integration Tests Failing

**Issue**: AWS credentials not configured

**Solution**:
```bash
aws configure
aws sts get-caller-identity  # Verify credentials
```

**Issue**: Infrastructure not deployed

**Solution**:
```bash
cd terraform
terraform apply
```

### E2E Tests Failing

**Issue**: Could not retrieve API key

**Solution**:
```bash
# Verify Secrets Manager access
aws secretsmanager get-secret-value --secret-id bus-simulator/api-key

# Or set manually
export API_KEY="your-api-key"
```

**Issue**: Could not retrieve API URLs

**Solution**:
```bash
# Verify Terraform outputs
cd terraform
terraform output

# Or set manually
export API_URL="https://your-api-id.execute-api.eu-west-1.amazonaws.com"
export MCP_URL="https://your-mcp-api-id.execute-api.eu-west-1.amazonaws.com/prod"
```

**Issue**: curl or jq not found

**Solution**:
```bash
# macOS
brew install curl jq

# Ubuntu
sudo apt-get install curl jq
```

## Best Practices

### Writing Unit Tests

- Test one thing per test
- Use descriptive test names
- Mock external dependencies
- Keep tests fast (< 100ms each)
- Use property-based testing for complex logic

### Writing Integration Tests

- Clean up resources after tests
- Use unique identifiers to avoid conflicts
- Handle eventual consistency
- Set appropriate timeouts
- Mark tests with `@pytest.mark.integration`

### Writing E2E Tests

- Test realistic user scenarios
- Include both success and error cases
- Use automatic configuration
- Provide clear error messages
- Make tests idempotent

## Performance Benchmarks

Expected test execution times:

- **Unit Tests**: < 1 minute
- **Integration Tests**: 5-10 minutes
- **E2E Tests**: 10-15 minutes
- **All Tests**: 15-25 minutes

## Cost Considerations

### Unit Tests
- **Cost**: $0 (runs locally)

### Integration Tests
- **Cost**: < $0.10 per run
- Timestream queries, Lambda invocations, API calls

### E2E Tests
- **Cost**: < $0.05 per run
- API Gateway requests, Lambda invocations

### Total Testing Cost
- **Per day**: < $1 (assuming 10 test runs)
- **Per month**: < $30

## References

- [pytest Documentation](https://docs.pytest.org/)
- [Hypothesis (Property Testing)](https://hypothesis.readthedocs.io/)
- [AWS Testing Best Practices](https://docs.aws.amazon.com/wellarchitected/latest/framework/test-validate.html)
- [Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
