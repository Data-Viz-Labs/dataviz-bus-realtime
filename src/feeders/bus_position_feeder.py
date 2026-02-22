#!/usr/bin/env python3
"""
Bus Position Feeder Service for the Madrid Bus Real-Time Simulator.

This service runs continuously as a Fargate container, simulating bus movement
along routes, handling passenger boarding/alighting, writing position data to
AWS Timestream, and publishing events to EventBridge.

Environment Variables:
    TIMESTREAM_DATABASE: Name of the Timestream database (default: bus_simulator)
    TIMESTREAM_TABLE: Name of the Timestream table (default: bus_position)
    CONFIG_FILE: Path to lines.yaml configuration file (default: data/lines.yaml)
    TIME_INTERVAL: Time interval between updates in seconds (default: 30)
    AWS_REGION: AWS region for Timestream (default: eu-west-1)
    EVENT_BUS_NAME: Name of the EventBridge event bus (default: bus-simulator-events)
    LOG_LEVEL: Logging level (default: INFO)

Usage:
    # Run with default settings
    python bus_position_feeder.py
    
    # Run with custom configuration
    TIMESTREAM_DATABASE=my_db CONFIG_FILE=/config/lines.yaml python bus_position_feeder.py
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config_loader import load_configuration, ConfigurationError
from common.timestream_client import TimestreamClient
from common.eventbridge_client import EventBridgeClient
from common.models import Route, BusState, BusArrival
from feeders.bus_movement_simulator import (
    simulate_bus_movement,
    calculate_alighting,
    calculate_boarding
)


# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class BusPositionFeederService:
    """
    Main service class for the Bus Position Feeder.
    
    This service maintains state for all buses and continuously simulates
    their movement along routes, handles passenger boarding/alighting,
    writes position data to Timestream, and publishes events to EventBridge.
    """
    
    def __init__(
        self,
        config_file: str,
        database_name: str,
        table_name: str,
        time_interval: int,
        event_bus_name: str,
        region_name: str = "eu-west-1"
    ):
        """
        Initialize the Bus Position Feeder Service.
        
        Args:
            config_file: Path to lines.yaml configuration file
            database_name: Timestream database name
            table_name: Timestream table name
            time_interval: Time interval between updates in seconds
            event_bus_name: EventBridge event bus name
            region_name: AWS region name
        """
        self.config_file = config_file
        self.database_name = database_name
        self.table_name = table_name
        self.time_interval = time_interval
        self.event_bus_name = event_bus_name
        self.region_name = region_name
        
        # State management
        self.routes: Dict[str, Route] = {}  # line_id -> Route
        self.buses: Dict[str, BusState] = {}  # bus_id -> BusState
        self.stop_counts: Dict[str, int] = {}  # stop_id -> current people count
        
        # Clients
        self.timestream_client: TimestreamClient = None
        self.eventbridge_client: EventBridgeClient = None
        
        logger.info(
            f"Initializing Bus Position Feeder Service: "
            f"database={database_name}, table={table_name}, "
            f"interval={time_interval}s, event_bus={event_bus_name}, region={region_name}"
        )
    
    def load_configuration(self) -> None:
        """
        Load bus lines, stops, and buses configuration from YAML file.
        
        Raises:
            ConfigurationError: If configuration loading fails
        """
        logger.info(f"Loading configuration from {self.config_file}")
        
        try:
            routes, buses = load_configuration(self.config_file)
            
            # Build route index by line_id
            for route in routes:
                self.routes[route.line_id] = route
            
            # Store bus states
            self.buses = buses
            
            # Initialize stop counts (for tracking people at stops)
            # In a full implementation, this would be shared with people_count_feeder
            # For now, we initialize with reasonable values
            for route in routes:
                for stop in route.stops:
                    if stop.stop_id not in self.stop_counts:
                        # Initialize with a reasonable count based on arrival rate
                        self.stop_counts[stop.stop_id] = int(stop.base_arrival_rate * 5)
            
            logger.info(
                f"Configuration loaded successfully: "
                f"{len(self.routes)} lines, {len(self.buses)} buses, {len(self.stop_counts)} stops"
            )
            
        except ConfigurationError as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")
    
    def initialize_clients(self) -> None:
        """
        Initialize Timestream and EventBridge clients.
        
        Raises:
            Exception: If client initialization fails
        """
        logger.info("Initializing Timestream and EventBridge clients")
        
        try:
            self.timestream_client = TimestreamClient(
                database_name=self.database_name,
                region_name=self.region_name,
                max_retries=3
            )
            
            self.eventbridge_client = EventBridgeClient(
                event_bus_name=self.event_bus_name,
                region_name=self.region_name,
                max_retries=3
            )
            
            logger.info("Clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise
    
    def simulate_and_write_data(self) -> None:
        """
        Simulate bus movement for all buses and write data to Timestream.
        
        This method:
        1. Simulates movement for each bus using simulate_bus_movement
        2. Handles arrivals at stops (boarding/alighting)
        3. Updates bus and stop state
        4. Writes position data to Timestream
        5. Publishes events to EventBridge
        """
        current_time = datetime.now()
        time_delta = timedelta(seconds=self.time_interval)
        
        logger.debug(f"Simulating bus movement at {current_time}")
        
        # Collect all position records for batch write
        position_records = []
        
        # Process each bus
        for bus_id, bus in self.buses.items():
            try:
                # Get the route for this bus
                route = self.routes.get(bus.line_id)
                if not route:
                    logger.error(f"Route not found for bus {bus_id} (line {bus.line_id})")
                    continue
                
                # Simulate bus movement
                position_data, stops_reached = simulate_bus_movement(
                    bus=bus,
                    route=route,
                    time_delta=time_delta
                )
                
                # Handle arrivals at stops
                arrivals: List[BusArrival] = []
                
                for stop in stops_reached:
                    # Get current people count at stop
                    people_at_stop = self.stop_counts.get(stop.stop_id, 0)
                    
                    # Calculate alighting (people getting off)
                    people_alighting = calculate_alighting(
                        passenger_count=bus.passenger_count,
                        is_terminal=stop.is_terminal
                    )
                    
                    # Calculate available capacity after alighting
                    available_capacity = bus.capacity - (bus.passenger_count - people_alighting)
                    
                    # Calculate boarding (people getting on)
                    people_boarding = calculate_boarding(
                        people_at_stop=people_at_stop,
                        available_capacity=available_capacity
                    )
                    
                    # Update bus passenger count
                    bus.passenger_count = bus.passenger_count - people_alighting + people_boarding
                    
                    # Update stop people count
                    self.stop_counts[stop.stop_id] = max(0, people_at_stop - people_boarding)
                    
                    # Create arrival event
                    arrival = BusArrival(
                        bus_id=bus_id,
                        stop_id=stop.stop_id,
                        timestamp=current_time,
                        passengers_boarding=people_boarding,
                        passengers_alighting=people_alighting
                    )
                    arrivals.append(arrival)
                    
                    logger.debug(
                        f"Bus {bus_id} arrived at stop {stop.stop_id}: "
                        f"{people_alighting} alighted, {people_boarding} boarded, "
                        f"now {bus.passenger_count} passengers"
                    )
                    
                    # Publish coordinated arrival event to EventBridge
                    try:
                        self.eventbridge_client.publish_bus_arrival_events(
                            bus_id=bus_id,
                            line_id=bus.line_id,
                            stop_id=stop.stop_id,
                            timestamp=current_time,
                            passengers_boarding=people_boarding,
                            passengers_alighting=people_alighting,
                            bus_passenger_count=bus.passenger_count,
                            stop_people_count=self.stop_counts[stop.stop_id]
                        )
                    except Exception as e:
                        logger.warning(f"Failed to publish arrival event: {e}")
                        # Continue - event publishing is non-critical
                
                # Update position data with current passenger count
                position_data.passenger_count = bus.passenger_count
                
                # Create Timestream record for position
                timestamp_ms = int(current_time.timestamp() * 1000)
                
                record = {
                    'Dimensions': [
                        {'Name': 'bus_id', 'Value': position_data.bus_id},
                        {'Name': 'line_id', 'Value': position_data.line_id},
                        {'Name': 'next_stop_id', 'Value': position_data.next_stop_id}
                    ],
                    'MeasureName': 'metrics',
                    'MeasureValueType': 'MULTI',
                    'MeasureValues': [
                        {
                            'Name': 'latitude',
                            'Value': str(position_data.latitude),
                            'Type': 'DOUBLE'
                        },
                        {
                            'Name': 'longitude',
                            'Value': str(position_data.longitude),
                            'Type': 'DOUBLE'
                        },
                        {
                            'Name': 'passenger_count',
                            'Value': str(position_data.passenger_count),
                            'Type': 'BIGINT'
                        },
                        {
                            'Name': 'distance_to_next_stop',
                            'Value': str(position_data.distance_to_next_stop),
                            'Type': 'DOUBLE'
                        },
                        {
                            'Name': 'speed',
                            'Value': str(position_data.speed),
                            'Type': 'DOUBLE'
                        }
                    ],
                    'Time': str(timestamp_ms),
                    'TimeUnit': 'MILLISECONDS'
                }
                
                position_records.append(record)
                
                # Publish position update event to EventBridge
                try:
                    self.eventbridge_client.publish_bus_position_event(
                        bus_id=position_data.bus_id,
                        line_id=position_data.line_id,
                        timestamp=current_time,
                        latitude=position_data.latitude,
                        longitude=position_data.longitude,
                        passenger_count=position_data.passenger_count,
                        next_stop_id=position_data.next_stop_id,
                        distance_to_next_stop=position_data.distance_to_next_stop,
                        speed=position_data.speed
                    )
                except Exception as e:
                    logger.warning(f"Failed to publish position event: {e}")
                    # Continue - event publishing is non-critical
                
                logger.debug(
                    f"Bus {bus_id} position: ({position_data.latitude:.6f}, {position_data.longitude:.6f}), "
                    f"passengers: {position_data.passenger_count}, "
                    f"next stop: {position_data.next_stop_id} ({position_data.distance_to_next_stop:.0f}m)"
                )
                
            except Exception as e:
                logger.error(f"Error simulating bus {bus_id}: {e}", exc_info=True)
                # Continue with other buses
                continue
        
        # Write all position records to Timestream
        if position_records:
            try:
                self.timestream_client.write_records(
                    table_name=self.table_name,
                    records=position_records
                )
                logger.info(
                    f"Successfully wrote {len(position_records)} bus position records to Timestream"
                )
            except Exception as e:
                logger.error(f"Failed to write records to Timestream: {e}")
                # Don't raise - we'll try again on the next iteration
        else:
            logger.warning("No position records generated to write")
    
    def run(self) -> None:
        """
        Main service loop - runs continuously until interrupted.
        
        This method:
        1. Loads configuration
        2. Initializes clients
        3. Runs an infinite loop simulating bus movement at regular intervals
        4. Handles errors gracefully with logging
        """
        logger.info("Starting Bus Position Feeder Service")
        
        try:
            # Initialize
            self.load_configuration()
            self.initialize_clients()
            
            logger.info(
                f"Service initialized successfully. "
                f"Starting continuous simulation loop (interval: {self.time_interval}s)"
            )
            
            # Main loop
            iteration = 0
            while True:
                iteration += 1
                loop_start = time.time()
                
                try:
                    logger.info(f"Starting iteration {iteration}")
                    self.simulate_and_write_data()
                    
                    # Calculate how long to sleep
                    elapsed = time.time() - loop_start
                    sleep_time = max(0, self.time_interval - elapsed)
                    
                    if sleep_time > 0:
                        logger.debug(
                            f"Iteration {iteration} completed in {elapsed:.2f}s. "
                            f"Sleeping for {sleep_time:.2f}s"
                        )
                        time.sleep(sleep_time)
                    else:
                        logger.warning(
                            f"Iteration {iteration} took {elapsed:.2f}s, "
                            f"which exceeds the configured interval of {self.time_interval}s"
                        )
                
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, shutting down gracefully")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop iteration {iteration}: {e}", exc_info=True)
                    # Sleep before retrying
                    logger.info(f"Sleeping for {self.time_interval}s before retry")
                    time.sleep(self.time_interval)
        
        except Exception as e:
            logger.critical(f"Fatal error during service initialization: {e}", exc_info=True)
            sys.exit(1)
        
        logger.info("Bus Position Feeder Service stopped")


def main():
    """
    Main entry point for the Bus Position Feeder Service.
    
    Reads configuration from environment variables and starts the service.
    """
    # Read configuration from environment variables
    database_name = os.getenv('TIMESTREAM_DATABASE', 'bus_simulator')
    table_name = os.getenv('TIMESTREAM_TABLE', 'bus_position')
    config_file = os.getenv('CONFIG_FILE', 'data/lines.yaml')
    time_interval = int(os.getenv('TIME_INTERVAL', '30'))
    event_bus_name = os.getenv('EVENT_BUS_NAME', 'bus-simulator-events')
    region_name = os.getenv('AWS_REGION', 'eu-west-1')
    
    # Validate configuration
    if not os.path.exists(config_file):
        logger.error(f"Configuration file not found: {config_file}")
        sys.exit(1)
    
    if time_interval <= 0:
        logger.error(f"TIME_INTERVAL must be positive, got {time_interval}")
        sys.exit(1)
    
    # Create and run service
    service = BusPositionFeederService(
        config_file=config_file,
        database_name=database_name,
        table_name=table_name,
        time_interval=time_interval,
        event_bus_name=event_bus_name,
        region_name=region_name
    )
    
    service.run()


if __name__ == '__main__':
    main()
