# Madrid Bus Real-Time Simulator

A cloud-native system that generates and serves temporally consistent simulated data for Madrid Centro's EMT bus system.

## Overview

This system simulates real-time bus operations through three APIs:
- **People Count API**: Query passenger counts at bus stops
- **Sensors API**: Access internal sensor data from buses and stops
- **Bus Position API**: Track real-time bus positions (REST + WebSocket)

## Architecture

The system uses AWS services:
- **Fargate**: Runs feeder services that generate simulated data
- **Timestream**: Stores time series data
- **API Gateway**: Exposes REST and WebSocket APIs
- **Lambda**: Processes API requests
- **EventBridge**: Routes real-time events
- **Amazon Location**: Manages bus routes

## Prerequisites

- AWS Account
- Terraform >= 1.0
- Docker >= 20.10
- Python >= 3.11
- Make

## Quick Start

1. Configure AWS credentials:
```bash
aws configure
```

2. Package Lambda functions:
```bash
make package-all-lambdas
```

3. Deploy the system:
```bash
make deploy
```

4. Destroy the system:
```bash
make destroy
```

## Development

### Packaging Lambda Functions

Package a specific Lambda function:
```bash
make package-lambda LAMBDA=people_count_api
```

Package all Lambda functions:
```bash
make package-all-lambdas
```

The ZIP files will be created in the `build/` directory. See [docs/LAMBDA_DEPLOYMENT.md](docs/LAMBDA_DEPLOYMENT.md) for detailed packaging and deployment instructions.

## Project Structure

```
dataviz-bus-realtime/
├── src/                    # Python source code
│   ├── feeders/           # Fargate feeder services
│   ├── lambdas/           # Lambda function handlers
│   └── common/            # Shared utilities and models
├── terraform/             # Infrastructure as code
├── docker/                # Dockerfiles for feeders
├── data/                  # Configuration data
├── scripts/               # Deployment and utility scripts
└── tests/                 # Unit and property-based tests
```

## Configuration

Edit `data/lines.yaml` to configure bus lines, stops, and buses.

## API Documentation

See [API.md](API.md) for detailed API documentation.

## License

See [LICENSE](LICENSE) for details.
