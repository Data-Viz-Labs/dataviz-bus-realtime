# API Key Export Script

## Overview

The `export_api_keys.py` script retrieves API keys from AWS API Gateway (via Terraform outputs) and generates a participant distribution file for hackathon participants. The script supports both text and JSON output formats.

## Prerequisites

- Terraform infrastructure must be deployed
- AWS credentials configured
- Python 3.11+ with boto3 installed

## Usage

### Basic Usage (Text Format)

```bash
python scripts/export_api_keys.py --region eu-west-1
```

This will create an `api_keys.txt` file with all API keys and usage instructions.

### JSON Format

```bash
python scripts/export_api_keys.py --region eu-west-1 --output api_keys.json --format json
```

### Using Makefile

```bash
# Export keys in text format (default)
make export-keys

# Export keys in JSON format
make export-keys FORMAT=json OUTPUT=keys.json

# Specify AWS region
make export-keys AWS_REGION=eu-central-1
```

## Output Formats

### Text Format

The text format includes:
- API Gateway endpoints (REST and WebSocket)
- List of all API keys with participant names
- Usage instructions
- REST API examples with curl commands
- WebSocket connection examples
- Rate limit information
- Additional resources and support information

Example output:
```
================================================================================
Madrid Bus Real-Time Simulator - API Keys for Hackathon Participants
================================================================================

Generated: 2024-01-15 10:30:00 UTC

--------------------------------------------------------------------------------
API ENDPOINTS
--------------------------------------------------------------------------------

REST API:      https://api123.execute-api.eu-west-1.amazonaws.com/prod
WebSocket API: https://ws456.execute-api.eu-west-1.amazonaws.com/prod

--------------------------------------------------------------------------------
API KEYS
--------------------------------------------------------------------------------

participant-1: abcdef1234567890
participant-2: 1234567890abcdef
...
```

### JSON Format

The JSON format provides structured data including:
- Timestamp of generation
- API endpoints
- Array of API keys with participant names
- Rate limit configuration
- Usage examples for all endpoints

Example output:
```json
{
  "generated_at": "2024-01-15T10:30:00+00:00",
  "endpoints": {
    "rest_api": "https://api123.execute-api.eu-west-1.amazonaws.com/prod",
    "websocket_api": "https://ws456.execute-api.eu-west-1.amazonaws.com/prod"
  },
  "api_keys": [
    {
      "participant": "participant-1",
      "api_key": "abcdef1234567890"
    }
  ],
  "rate_limits": {
    "requests_per_second": 50,
    "burst_limit": 100,
    "requests_per_day": 10000
  },
  "usage_examples": {
    "rest_api": { ... },
    "websocket": { ... }
  }
}
```

## API Key Information

The script retrieves the following information:

1. **API Keys**: Retrieved from Terraform outputs (`api_key_values`)
2. **REST API Endpoint**: Retrieved from Terraform output (`api_gateway_rest_endpoint`)
3. **WebSocket Endpoint**: Retrieved from Terraform output (`api_gateway_websocket_endpoint`)

## Usage Examples Included

The generated file includes examples for:

### REST API
- Get latest people count at a bus stop
- Get historical people count at a specific time
- Get latest sensor data for a bus or stop
- Get latest bus position
- Get all buses on a line

### WebSocket API
- Connect using wscat (Node.js)
- Connect using Python websocket library
- Subscribe to specific bus lines
- Receive real-time bus position updates

## Rate Limits

Each API key has the following limits (configured in Terraform):
- **50 requests per second** (burst: 100)
- **10,000 requests per day**

## Distribution

The generated file should be distributed securely to hackathon participants. Consider:

1. **Secure Distribution**: Use encrypted channels (email with password-protected attachment, secure file sharing)
2. **Individual Keys**: Each participant gets their own API key for tracking and rate limiting
3. **Pre-Hackathon**: Distribute keys 1-2 days before the hackathon starts
4. **Support**: Include support contact information in the distribution

## Security Considerations

- API keys are sensitive credentials and should be treated as secrets
- The script marks Terraform outputs as sensitive
- Store the generated file securely
- Consider rotating keys after the hackathon
- Monitor API usage during the event

## Troubleshooting

### Error: "Error getting Terraform output"

**Cause**: Terraform state is not available or infrastructure not deployed

**Solution**: 
```bash
cd terraform
terraform init
terraform apply
```

### Error: "No API keys found"

**Cause**: API keys not created in Terraform

**Solution**: Check that `participant_count` variable is set in Terraform:
```bash
cd terraform
terraform plan -var="participant_count=10"
terraform apply -var="participant_count=10"
```

### Empty API key values

**Cause**: Terraform outputs are marked as sensitive and may not be accessible

**Solution**: Ensure you have proper AWS credentials and Terraform state access

## Related Documentation

- [API Documentation](./API_DOCUMENTATION.md) - Complete API reference
- [API Key Authentication](../terraform/API_KEY_AUTHENTICATION.md) - Authentication implementation details
- [README](../README.md) - Project overview and setup

## Example Workflow

Pre-hackathon preparation:

```bash
# 1. Deploy infrastructure (7 days before hackathon)
make deploy

# 2. Wait for data accumulation (5 days)
# Feeders run continuously generating historical data

# 3. Export API keys (1-2 days before hackathon)
make export-keys

# 4. Verify keys work
API_KEY=$(grep "participant-1:" api_keys.txt | cut -d' ' -f2)
curl -H "x-api-key: $API_KEY" \
     "$(terraform output -raw api_gateway_rest_endpoint)/people-count/S001?mode=latest"

# 5. Distribute api_keys.txt to participants securely
```
