#!/bin/bash
# Script to test container images locally with Podman
# This script verifies that the images can start and load the Python code correctly

set -e

echo "Testing People Count Feeder image..."
podman run --rm \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  bus-simulator-people-count:latest \
  python -c "import sys; sys.path.insert(0, '/app'); from src.feeders.people_count_feeder import PeopleCountFeederService; print('✓ People Count Feeder imports successfully')" || echo "✗ People Count Feeder failed"

echo ""
echo "Testing Sensors Feeder image..."
podman run --rm \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  bus-simulator-sensors:latest \
  python -c "import sys; sys.path.insert(0, '/app'); from src.feeders.sensor_data_feeder import SensorDataFeederService; print('✓ Sensors Feeder imports successfully')" || echo "✗ Sensors Feeder failed"

echo ""
echo "Testing Bus Position Feeder image..."
podman run --rm \
  -e AWS_ACCESS_KEY_ID=test \
  -e AWS_SECRET_ACCESS_KEY=test \
  -e AWS_REGION=eu-west-1 \
  bus-simulator-bus-position:latest \
  python -c "import sys; sys.path.insert(0, '/app'); from src.feeders.bus_position_feeder import BusPositionFeederService; print('✓ Bus Position Feeder imports successfully')" || echo "✗ Bus Position Feeder failed"

echo ""
echo "All image tests completed!"
