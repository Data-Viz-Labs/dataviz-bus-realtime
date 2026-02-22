# Configuration Loader Usage Guide

## Overview

The configuration loader (`src/common/config_loader.py`) provides functionality to load bus system configuration from YAML files and convert them into Route and BusState objects.

## Quick Start

```python
from src.common.config_loader import load_configuration

# Load configuration in one call
routes, buses = load_configuration("data/lines.yaml")

# Access routes
for route in routes:
    print(f"Line {route.line_id}: {route.name}")
    print(f"  Stops: {len(route.stops)}")

# Access buses
for bus_id, bus in buses.items():
    print(f"Bus {bus_id} on line {bus.line_id}")
```

## Detailed Usage

### Using ConfigLoader Class

For more control over the loading process:

```python
from src.common.config_loader import ConfigLoader

# Initialize loader
loader = ConfigLoader("data/lines.yaml")

# Load and parse configuration
loader.load()
routes = loader.parse_routes()
buses = loader.parse_buses()

# Validate completeness
loader.validate_completeness()

# Access specific routes
route = loader.get_route_by_id("L1")
```

## Configuration File Format

The YAML configuration file must follow this structure:

```yaml
lines:
  - line_id: "L1"
    name: "Line Name"
    stops:
      - stop_id: "S001"
        name: "Stop Name"
        latitude: 40.4657
        longitude: -3.6886
        is_terminal: true
        base_arrival_rate: 2.5
      # ... more stops
    buses:
      - bus_id: "B001"
        capacity: 80
        initial_position: 0.0
      # ... more buses
  # ... more lines
```

## Validation Rules

The configuration loader validates:

1. **File existence and format**: YAML file must exist and be valid
2. **Required fields**: All required fields must be present
3. **Unique IDs**: Line IDs, stop IDs (per line), and bus IDs must be unique
4. **Data types**: Numeric fields must be valid numbers
5. **Value ranges**:
   - Latitude: -90 to 90
   - Longitude: -180 to 180
   - Base arrival rate: >= 0
   - Capacity: > 0
   - Initial position: 0.0 to 1.0
6. **Route requirements**:
   - At least 2 stops per route
   - At least 1 terminal stop per route
   - At least 1 bus per line
7. **Completeness**: All buses must reference existing lines

## Error Handling

All errors are raised as `ConfigurationError` with descriptive messages:

```python
from src.common.config_loader import ConfigurationError

try:
    routes, buses = load_configuration("data/lines.yaml")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

## Data Models

The loader creates instances of:

- **Route**: Contains line_id, name, and list of Stop objects
- **Stop**: Contains stop_id, name, coordinates, terminal flag, and arrival rate
- **BusState**: Contains bus_id, line_id, capacity, and initial state

All models include validation methods to ensure data integrity.

## Example

See `examples/load_config_example.py` for a complete working example that:
- Loads the configuration
- Displays route information
- Shows bus assignments
- Provides summary statistics

Run it with:
```bash
python examples/load_config_example.py
```

## Testing

Comprehensive tests are available in `tests/test_config_loader.py`:
- Unit tests for all validation rules
- Integration tests with the real lines.yaml file
- Error handling tests

Run tests with:
```bash
python -m pytest tests/test_config_loader.py -v
```
