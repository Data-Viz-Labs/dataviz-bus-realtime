# Feeder Services

This directory contains the three main feeder services for the Madrid Bus Real-Time Simulator. Each service runs continuously as a Fargate container, generating simulated data and writing it to AWS Timestream.

## Services Overview

1. **People Count Feeder** - Generates people count data at bus stops
2. **Sensor Data Feeder** - Generates sensor readings for buses and stops
3. **Bus Position Feeder** - Simulates bus movement and publishes position updates

---

# People Count Feeder Service

The People Count Feeder Service generates realistic people count data at bus stops and writes it to AWS Timestream.

## Overview

This service:
- Loads bus line and stop configuration from a YAML file
- Maintains state for each bus stop (current people count)
- Generates realistic people counts based on daily patterns
- Writes data to AWS Timestream at regular intervals
- Handles errors gracefully with automatic retry logic
- Runs continuously as a Fargate container

## Configuration

The service is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `TIMESTREAM_DATABASE` | Name of the Timestream database | `bus_simulator` |
| `TIMESTREAM_TABLE` | Name of the Timestream table | `people_count` |
| `CONFIG_FILE` | Path to lines.yaml configuration file | `data/lines.yaml` |
| `TIME_INTERVAL` | Time interval between updates in seconds | `60` |
| `AWS_REGION` | AWS region for Timestream | `eu-west-1` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

## Usage

### Running Locally

```bash
# With default settings
python src/feeders/people_count_feeder.py

# With custom configuration
export TIMESTREAM_DATABASE=my_database
export TIMESTREAM_TABLE=my_table
export CONFIG_FILE=/path/to/lines.yaml
export TIME_INTERVAL=30
export LOG_LEVEL=DEBUG
python src/feeders/people_count_feeder.py
```

### Running in Docker

```bash
# Build the Docker image
docker build -t people-count-feeder -f docker/Dockerfile.people_count .

# Run the container
docker run -e TIMESTREAM_DATABASE=bus_simulator \
           -e TIMESTREAM_TABLE=people_count \
           -e AWS_REGION=eu-west-1 \
           -e AWS_ACCESS_KEY_ID=your_key \
           -e AWS_SECRET_ACCESS_KEY=your_secret \
           people-count-feeder
```

### Running in AWS Fargate

The service is designed to run as a Fargate task. See the Terraform configuration in `terraform/modules/fargate/` for deployment details.

## Data Model

The service writes records to Timestream with the following structure:

**Dimensions:**
- `stop_id`: Unique identifier for the bus stop
- `line_ids`: Comma-separated list of line IDs that serve this stop

**Measures:**
- `count`: Number of people at the stop (BIGINT)

**Time:**
- Timestamp in milliseconds since epoch

## Algorithm

The service uses the following algorithm to generate people counts:

1. **Daily Patterns**: Applies time-of-day multipliers to base arrival rates:
   - Morning rush (06:00-09:00): 1.5x
   - Mid-morning (09:00-12:00): 0.6x
   - Lunch period (12:00-15:00): 1.2x
   - Afternoon (15:00-18:00): 0.8x
   - Evening rush (18:00-21:00): 1.4x
   - Night (21:00-06:00): 0.2x

2. **Natural Arrivals**: Uses Poisson distribution to simulate realistic passenger arrivals

3. **Bus Boarding**: Coordinates with bus arrival events to decrease counts when people board (future enhancement)

4. **Non-negativity**: Ensures counts never go below zero

## Error Handling

The service handles errors gracefully:

- **Configuration errors**: Fatal - service exits with error code 1
- **Timestream initialization errors**: Fatal - service exits with error code 1
- **Write failures**: Non-fatal - logs error and retries on next iteration
- **Data generation errors**: Non-fatal - logs error and continues with other stops

## Logging

The service logs to stdout with structured messages:

```
2024-01-15 10:30:00 - feeders.people_count_feeder - INFO - Starting People Count Feeder Service
2024-01-15 10:30:00 - feeders.people_count_feeder - INFO - Loading configuration from data/lines.yaml
2024-01-15 10:30:00 - feeders.people_count_feeder - INFO - Configuration loaded successfully: 3 lines, 18 stops
2024-01-15 10:30:00 - feeders.people_count_feeder - INFO - Initializing Timestream client
2024-01-15 10:30:00 - feeders.people_count_feeder - INFO - Service initialized successfully. Starting continuous generation loop (interval: 60s)
2024-01-15 10:30:00 - feeders.people_count_feeder - INFO - Starting iteration 1
2024-01-15 10:30:01 - feeders.people_count_feeder - INFO - Successfully wrote 18 people count records to Timestream
```

## Testing

Run the unit tests:

```bash
python -m pytest tests/test_people_count_feeder.py -v
```

Run the integration tests:

```bash
python -m pytest tests/test_feeder_integration.py -v
```

## Future Enhancements

- Coordinate with Bus Position Feeder to handle bus arrival events
- Support for multiple configuration file formats (CSV, JSON)
- Metrics export to CloudWatch
- Health check endpoint for container orchestration
- Graceful shutdown handling


---

# Bus Position Feeder Service

The Bus Position Feeder Service simulates bus movement along routes, handles passenger boarding/alighting, writes position data to AWS Timestream, and publishes events to EventBridge.

## Overview

This service:
- Loads bus line, stop, and bus configuration from a YAML file
- Maintains state for all buses (position, passenger count, speed)
- Simulates realistic bus movement along routes
- Handles passenger boarding and alighting at stops
- Writes position data to AWS Timestream at regular intervals
- Publishes position update events to EventBridge
- Publishes coordinated arrival events when buses reach stops
- Handles errors gracefully with automatic retry logic
- Runs continuously as a Fargate container

## Configuration

The service is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `TIMESTREAM_DATABASE` | Name of the Timestream database | `bus_simulator` |
| `TIMESTREAM_TABLE` | Name of the Timestream table | `bus_position` |
| `CONFIG_FILE` | Path to lines.yaml configuration file | `data/lines.yaml` |
| `TIME_INTERVAL` | Time interval between updates in seconds | `30` |
| `AWS_REGION` | AWS region for Timestream and EventBridge | `eu-west-1` |
| `EVENT_BUS_NAME` | Name of the EventBridge event bus | `bus-simulator-events` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

## Usage

### Running Locally

```bash
# With default settings
python src/feeders/bus_position_feeder.py

# With custom configuration
export TIMESTREAM_DATABASE=my_database
export TIMESTREAM_TABLE=bus_position
export CONFIG_FILE=/path/to/lines.yaml
export TIME_INTERVAL=30
export EVENT_BUS_NAME=my-event-bus
export LOG_LEVEL=DEBUG
python src/feeders/bus_position_feeder.py
```

### Running in Docker

```bash
# Build the Docker image
docker build -t bus-position-feeder -f docker/Dockerfile.bus_position .

# Run the container
docker run -e TIMESTREAM_DATABASE=bus_simulator \
           -e TIMESTREAM_TABLE=bus_position \
           -e EVENT_BUS_NAME=bus-simulator-events \
           -e AWS_REGION=eu-west-1 \
           -e AWS_ACCESS_KEY_ID=your_key \
           -e AWS_SECRET_ACCESS_KEY=your_secret \
           bus-position-feeder
```

### Running in AWS Fargate

The service is designed to run as a Fargate task. See the Terraform configuration in `terraform/modules/fargate/` for deployment details.

## Data Model

### Timestream Records

The service writes position records to Timestream with the following structure:

**Dimensions:**
- `bus_id`: Unique identifier for the bus
- `line_id`: Bus line this bus operates on
- `next_stop_id`: Next stop on the route

**Measures:**
- `latitude`: Current latitude (DOUBLE)
- `longitude`: Current longitude (DOUBLE)
- `passenger_count`: Current number of passengers (BIGINT)
- `distance_to_next_stop`: Distance to next stop in meters (DOUBLE)
- `speed`: Current speed in km/h (DOUBLE)

**Time:**
- Timestamp in milliseconds since epoch

### EventBridge Events

The service publishes two types of events:

**1. Bus Position Update Event**
```json
{
  "source": "bus-simulator",
  "detail-type": "bus.position.updated",
  "detail": {
    "bus_id": "B001",
    "line_id": "L1",
    "timestamp": "2024-01-15T10:30:00Z",
    "latitude": 40.4657,
    "longitude": -3.6886,
    "passenger_count": 25,
    "next_stop_id": "S002",
    "distance_to_next_stop": 500.0,
    "speed": 30.0
  }
}
```

**2. Bus Arrival Event**
```json
{
  "source": "bus-simulator",
  "detail-type": "bus.arrival",
  "detail": {
    "bus_id": "B001",
    "line_id": "L1",
    "stop_id": "S002",
    "timestamp": "2024-01-15T10:30:00Z",
    "passengers_boarding": 5,
    "passengers_alighting": 3,
    "bus_passenger_count": 27,
    "stop_people_count": 10
  }
}
```

## Algorithm

The service uses the following algorithm for each bus:

1. **Movement Simulation**:
   - Calculate distance traveled based on speed and time interval
   - Update position along route using route geometry
   - Detect stops reached during movement

2. **Arrival Handling** (for each stop reached):
   - Calculate passengers alighting (20-40% at regular stops, 100% at terminals)
   - Calculate passengers boarding (up to available capacity)
   - Update bus passenger count
   - Update stop people count
   - Create arrival event

3. **Data Writing**:
   - Write position data to Timestream
   - Publish position update event to EventBridge
   - Publish arrival events to EventBridge

4. **State Management**:
   - Maintain bus position on route (0.0 to 1.0)
   - Track passenger count for each bus
   - Track people count at each stop

## Integration Points

The Bus Position Feeder integrates with:

1. **Bus Movement Simulator** (`bus_movement_simulator.py`):
   - `simulate_bus_movement()` - Calculates new position and detects stops
   - `calculate_alighting()` - Determines passengers getting off
   - `calculate_boarding()` - Determines passengers getting on

2. **Timestream Client** (`common/timestream_client.py`):
   - Writes position data with retry logic

3. **EventBridge Client** (`common/eventbridge_client.py`):
   - Publishes position update events
   - Publishes coordinated arrival events

4. **Configuration Loader** (`common/config_loader.py`):
   - Loads routes, stops, and buses from YAML

## Error Handling

The service handles errors gracefully:

- **Configuration errors**: Fatal - service exits with error code 1
- **Client initialization errors**: Fatal - service exits with error code 1
- **Timestream write failures**: Non-fatal - logs error and retries on next iteration
- **EventBridge publish failures**: Non-fatal - logs warning and continues (non-critical)
- **Bus simulation errors**: Non-fatal - logs error and continues with other buses

## Logging

The service logs to stdout with structured messages:

```
2024-01-15 10:30:00 - feeders.bus_position_feeder - INFO - Starting Bus Position Feeder Service
2024-01-15 10:30:00 - feeders.bus_position_feeder - INFO - Loading configuration from data/lines.yaml
2024-01-15 10:30:00 - feeders.bus_position_feeder - INFO - Configuration loaded successfully: 3 lines, 6 buses, 18 stops
2024-01-15 10:30:00 - feeders.bus_position_feeder - INFO - Initializing Timestream and EventBridge clients
2024-01-15 10:30:00 - feeders.bus_position_feeder - INFO - Service initialized successfully. Starting continuous simulation loop (interval: 30s)
2024-01-15 10:30:00 - feeders.bus_position_feeder - INFO - Starting iteration 1
2024-01-15 10:30:00 - feeders.bus_position_feeder - DEBUG - Bus B001 arrived at stop S002: 5 alighted, 8 boarded, now 28 passengers
2024-01-15 10:30:01 - feeders.bus_position_feeder - INFO - Successfully wrote 6 bus position records to Timestream
```

## Testing

Run the unit tests:

```bash
python -m pytest tests/test_bus_position_feeder.py -v
```

The test suite covers:
- Service initialization
- Configuration loading
- Bus movement simulation integration
- Arrival handling (boarding/alighting)
- Terminal stop logic
- Multiple bus handling
- Timestream record formatting
- EventBridge event publishing
- Error handling and recovery

## Performance Considerations

- **Time Interval**: Default 30 seconds provides good balance between data granularity and system load
- **Batch Writes**: All bus positions are written to Timestream in a single batch
- **Event Publishing**: Events are published asynchronously and failures don't block processing
- **State Management**: In-memory state for all buses and stops (minimal memory footprint)

## Future Enhancements

- Coordinate with People Count Feeder for shared stop state
- Add traffic congestion simulation affecting bus speeds
- Add bus breakdown/delay simulation
- Support for multiple routes per bus (route changes)
- Metrics export to CloudWatch
- Health check endpoint for container orchestration
- Graceful shutdown handling with state persistence
