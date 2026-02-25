# Madrid Bus Real-Time Simulator

⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️
⚠️ WARNING!!! LEARNING MATERIAL NOT SUITABLE FOR PRODUCTION ⚠️
⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️

A cloud-native system that generates and serves temporally consistent simulated data for Madrid Centro's EMT bus system.

## Overview

The Madrid Bus Real-Time Simulator is designed for hackathons and educational purposes, providing realistic bus operation data through REST and WebSocket APIs. The system continuously generates data for bus positions, passenger counts, and sensor readings, storing it in AWS Timestream for historical queries.

## Key Features

- **Real-time bus positions**: Track buses along their routes with GPS coordinates
- **Bidirectional routes**: Buses travel outbound and return on inbound routes with automatic direction changes at terminals
- **Passenger counts**: Monitor people waiting at stops and riding on buses
- **Sensor data**: Temperature, humidity, CO2 levels, and door status
- **Historical queries**: Access up to 30 days of historical data
- **WebSocket streaming**: Real-time position updates for subscribed bus lines
- **Daily patterns**: Realistic passenger flow based on time of day
- **Temporal consistency**: Coordinated updates across all data types

## Architecture

### High-Level Overview

The system follows a producer-consumer pattern with three main layers:

1. **Data Generation Layer (Fargate)**: Three feeder services continuously generate realistic bus operation data
2. **Event & Storage Layer**: AWS Timestream stores time series data, EventBridge handles real-time events
3. **API Layer (Lambda + API Gateway)**: REST and WebSocket APIs serve data to clients

### Key Components

**API Gateway:**
- REST API with API key authentication for historical/latest queries
- WebSocket API with custom authorizer for real-time updates

**Lambda Functions:**
- People Count API: Query passenger counts at bus stops
- Sensors API: Query temperature, humidity, CO2, door status
- Bus Position API: Query bus locations and passenger counts
- WebSocket Handler: Manage real-time subscriptions and broadcasts
- WebSocket Authorizer: Validate API keys for WebSocket connections

**MCP Server (ECS Fargate):**
- Programmatic access to Timestream data via Model Context Protocol
- Deployed on ECS in private subnets with API Gateway HTTP API access
- Five tools for querying people count, sensors, bus positions, and time ranges
- Authentication via x-api-key and x-group-name headers (same as REST APIs)
- CloudWatch Logs at `/ecs/mcp-server`

**Fargate Services:**
- People Count Feeder: Generates passenger arrival/departure data
- Sensors Feeder: Generates environmental sensor readings
- Bus Position Feeder: Simulates bus movement along routes

**Storage:**
- Timestream: Time series database (24h memory + 30d magnetic)
- DynamoDB: WebSocket connection tracking
- S3: Configuration storage (lines.yaml)

**Event Processing:**
- EventBridge: Routes real-time bus position events to WebSocket clients

### Bidirectional Route System

The simulator implements realistic bidirectional bus routes:

- **Outbound (Direction = 0)**: Buses travel from first stop to last stop
- **Terminal Stop Behavior**: When reaching a terminal stop:
  - All passengers alight (get off)
  - New passengers board
  - Direction toggles (0 → 1 or 1 → 0)
  - Position resets to 0.0 for return journey
- **Inbound (Direction = 1)**: Buses travel the return route back to origin
- **Direction Consistency**: Direction value remains constant between terminal stops

## Prerequisites

- AWS Account with appropriate permissions
- Terraform >= 1.0
- Podman (for building container images)
- Python 3.11+
- AWS CLI configured

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd dataviz-bus-realtime
```

### 2. Build Container Images

```bash
make build-feeders
```

### 3. Deploy Infrastructure

```bash
# Initialize Terraform
make init

# Review deployment plan
make plan

# Deploy (builds images, pushes to ECR, applies Terraform, loads config)
make deploy AWS_REGION=eu-west-1
```

### 4. Get API Endpoints

```bash
cd terraform
terraform output http_api_endpoint
terraform output websocket_api_endpoint
terraform output mcp_api_endpoint
```

### 5. Test the APIs

```bash
# Get API key
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString --output text | jq -r '.api_key')

# Get latest people count at stop S001
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: test-group" \
     "$(terraform output -raw http_api_endpoint)/people-count/S001?mode=latest"

# Get latest bus position
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: test-group" \
     "$(terraform output -raw http_api_endpoint)/bus-position/B001?mode=latest"
```

## Configuration

### Bus Lines Configuration

Edit `data/lines.yaml` to configure bus lines, stops, and buses:

```yaml
lines:
  - line_id: "L1"
    name: "Plaza de Castilla - Atocha"
    stops:
      - stop_id: "S001"
        name: "Plaza de Castilla"
        latitude: 40.4657
        longitude: -3.6886
        is_terminal: true
        base_arrival_rate: 2.5  # people per minute
      - stop_id: "S002"
        name: "Paseo de la Castellana"
        latitude: 40.4500
        longitude: -3.6900
        is_terminal: false
        base_arrival_rate: 1.8
    buses:
      - bus_id: "B001"
        capacity: 80
        initial_position: 0.0
```

After modifying the configuration, reload it:

```bash
make load-config AWS_REGION=eu-west-1
```

## API Documentation

See [docs/UI.md](docs/UI.md) for complete API reference.

### Quick Examples

**REST API:**
```bash
# Latest people count
curl -H "x-api-key: $API_KEY" -H "x-group-name: team-alpha" \
  "{api-endpoint}/people-count/S001?mode=latest"

# Historical sensor data
curl -H "x-api-key: $API_KEY" -H "x-group-name: team-alpha" \
  "{api-endpoint}/sensors/bus/B001?timestamp=2026-02-22T10:00:00Z"

# All buses on a line
curl -H "x-api-key: $API_KEY" -H "x-group-name: team-alpha" \
  "{api-endpoint}/bus-position/line/L1?mode=latest"
```

**WebSocket API:**
```javascript
const ws = new WebSocket('wss://{websocket-endpoint}?api_key=YOUR_KEY&group_name=team-alpha');
ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'subscribe',
    line_ids: ['L1', 'L2']
  }));
};
ws.onmessage = (event) => {
  console.log('Position update:', JSON.parse(event.data));
};
```

**MCP Server:**
```bash
# Get API endpoint and key
cd terraform
MCP_ENDPOINT=$(terraform output -raw mcp_api_endpoint)
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString --output text | jq -r '.api_key')

# List available tools
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-api-key: ${API_KEY}" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json"

# Query people count
curl -X POST "${MCP_ENDPOINT}/mcp/call-tool" \
  -H "x-api-key: ${API_KEY}" \
  -H "x-group-name: your-group" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "query_people_count",
    "arguments": {
      "stop_id": "S001",
      "mode": "latest"
    }
  }'
```

## Testing

The project includes three levels of testing following the test pyramid approach:

### Quick Start

```bash
# Run all tests
make test-all

# Run specific test level
make test-unit      # Unit tests (local, no AWS)
make test-int       # Integration tests (Python + AWS)
make test-e2e       # End-to-end tests (API shell scripts)
```

### Test Levels

**1. Unit Tests (Local, No AWS)**
- Fast execution (< 1 minute)
- Tests business logic, data models, utilities
- No AWS credentials required
- Uses mocks for external dependencies

**2. Integration Tests (Python + AWS)**
- Moderate execution (5-10 minutes)
- Tests AWS service interactions
- Requires AWS credentials and deployed infrastructure
- Tests Timestream, Secrets Manager, Lambda, MCP server

**3. End-to-End Tests (Shell Scripts)**
- Complete user workflows (10-15 minutes)
- Tests all public APIs via curl
- Automatic configuration from Terraform outputs
- Tests REST APIs, WebSocket, MCP server, authentication

See [docs/ops_manual.md](docs/ops_manual.md) for detailed testing documentation.

## Deployment Timeline

For hackathon preparation:

1. **Day -7**: Deploy infrastructure (`make deploy`)
2. **Day -7 to Day -2**: Feeders run continuously, accumulating 5 days of data
3. **Day -1**: Verify system readiness (`make verify`)
4. **Day -1**: Export and distribute API keys (`make export-keys`)
5. **Day 0**: Hackathon begins, system continues running

### Pre-Hackathon Verification

Before the hackathon, run the verification script to ensure everything is working:

```bash
# Run verification checks
make verify AWS_REGION=eu-west-1

# Run with verbose output
make verify AWS_REGION=eu-west-1 VERBOSE=true
```

The verification script checks:
- ✓ Timestream has at least 5 days of historical data
- ✓ All Fargate services are running
- ✓ REST API endpoints respond correctly
- ✓ API key authentication is enforced
- ✓ WebSocket connections work properly

## Monitoring

### CloudWatch Dashboards

Monitor system health through CloudWatch:
- Feeder service metrics (CPU, memory, task count)
- API Gateway metrics (requests, latency, errors)
- Lambda metrics (invocations, duration, errors)
- Timestream metrics (write throughput, query latency)
- MCP server metrics (CPU, memory, task count, health checks)

### Logs

All services log to CloudWatch Logs:
- Lambda functions: `/aws/lambda/bus-simulator-*`
- Fargate services: `/ecs/*-feeder`
- MCP server: `/ecs/mcp-server`

**View MCP server logs:**
```bash
# Tail logs in real-time
aws logs tail /ecs/mcp-server --follow --region eu-west-1

# Filter by group name
aws logs filter-log-events \
  --log-group-name /ecs/mcp-server \
  --filter-pattern "your-group-name" \
  --region eu-west-1
```

## Cost Estimation

Approximate monthly costs for 7-day operation (5 days pre-hackathon + 2 days hackathon):

- API Gateway: $10-20
- Lambda: $5-10
- Timestream: $50-100
- Fargate (feeders): $30-50
- Fargate (MCP server): $10-15
- EventBridge: $5-10
- Amazon Location: $5

**Total: ~$115-210 for 7 days**

**Note:** MCP server costs depend on usage. The estimate assumes moderate query load (10-50 queries/min).

## Cleanup

To destroy all infrastructure:

```bash
make destroy AWS_REGION=eu-west-1
```

## Project Structure

```
dataviz-bus-realtime/
├── data/                    # Configuration files
│   └── lines.yaml          # Bus lines configuration
├── dataviz/                # Visualization examples
│   ├── samples-001.py      # Example 1: People Count
│   ├── samples-002.py      # Example 2: Bus Sensors
│   ├── samples-003.py      # Example 3: Bus Positions
│   ├── samples-004.py      # Example 4: Real-time Dashboard
│   ├── samples-005.py      # Example 5: Sensor Comparison
│   ├── samples-006.py      # Example 6: WebSocket
│   └── README.md           # Examples documentation
├── docker/                  # Dockerfiles for Fargate services
├── docs/                    # Documentation
│   ├── UI.md               # API documentation (REST, WebSocket, MCP)
│   ├── ops_manual.md       # Operations manual
│   └── deployment_manual.md # Deployment manual
├── mcp_server/             # MCP server
├── scripts/                 # Deployment and utility scripts
├── src/
│   ├── common/             # Shared utilities
│   ├── feeders/            # Data generation services
│   └── lambdas/            # API Lambda functions
├── terraform/              # Infrastructure as Code
│   └── modules/            # Terraform modules
├── tests/                  # Unit and property tests
├── Makefile               # Deployment automation
└── README.md              # This file
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built for educational and hackathon purposes
- Uses AWS Timestream for time series data storage
- Implements property-based testing with Hypothesis
- Infrastructure as Code with Terraform

## Support

For issues or questions:
- Open an issue on GitHub
- Check the [API Documentation](docs/UI.md)
- Review CloudWatch logs for debugging
- See [Operations Manual](docs/ops_manual.md)
- See [Deployment Manual](docs/deployment_manual.md)
