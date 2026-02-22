#!/usr/bin/env python3
"""
Sensor Data Feeder Service for the Madrid Bus Real-Time Simulator.

This service runs continuously as a Fargate container, generating realistic
sensor data for buses and stops and writing it to AWS Timestream. It generates
temperature, humidity, CO2 levels, and door status readings.

Environment Variables:
    TIMESTREAM_DATABASE: Name of the Timestream database (default: bus_simulator)
    TIMESTREAM_TABLE: Name of the Timestream table (default: sensor_data)
    CONFIG_FILE: Path to lines.yaml configuration file (default: data/lines.yaml)
    TIME_INTERVAL: Time interval between updates in seconds (default: 60)
    AWS_REGION: AWS region for Timestream (default: eu-west-1)
    LOG_LEVEL: Logging level (default: INFO)

Usage:
    # Run with default settings
    python sensor_data_feeder.py
    
    # Run with custom configuration
    TIMESTREAM_DATABASE=my_db CONFIG_FILE=/config/lines.yaml python sensor_data_feeder.py
"""

import os
import sys
import time
import logging
from datetime import datetime
from typing import Dict, List
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config_loader import load_configuration, ConfigurationError
from common.timestream_client import TimestreamClient
from common.models import Route, BusState, Stop
from feeders.sensor_data_generator import generate_sensor_data


# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class SensorDataFeederService:
    """
    Main service class for the Sensor Data Feeder.
    
    This service generates realistic sensor data for all buses and stops,
    including temperature, humidity, CO2 levels (buses only), and door status (buses only).
    """
    
    def __init__(
        self,
        config_file: str,
        database_name: str,
        table_name: str,
        time_interval: int,
        region_name: str = "eu-west-1"
    ):
        """
        Initialize the Sensor Data Feeder Service.
        
        Args:
            config_file: Path to lines.yaml configuration file
            database_name: Timestream database name
            table_name: Timestream table name
            time_interval: Time interval between updates in seconds
            region_name: AWS region name
        """
        self.config_file = config_file
        self.database_name = database_name
        self.table_name = table_name
        self.time_interval = time_interval
        self.region_name = region_name
        
        # State management
        self.routes: List[Route] = []
        self.buses: Dict[str, BusState] = {}  # bus_id -> BusState
        self.stops: Dict[str, Stop] = {}  # stop_id -> Stop
        
        # Timestream client
        self.timestream_client: TimestreamClient = None
        
        logger.info(
            f"Initializing Sensor Data Feeder Service: "
            f"database={database_name}, table={table_name}, "
            f"interval={time_interval}s, region={region_name}"
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
            self.routes = routes
            self.buses = buses
            
            # Build stop index for easy lookup
            for route in routes:
                for stop in route.stops:
                    if stop.stop_id not in self.stops:
                        self.stops[stop.stop_id] = stop
            
            logger.info(
                f"Configuration loaded successfully: "
                f"{len(self.routes)} lines, {len(self.buses)} buses, {len(self.stops)} stops"
            )
            
        except ConfigurationError as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise ConfigurationError(f"Configuration loading failed: {e}")
    
    def initialize_timestream_client(self) -> None:
        """
        Initialize the Timestream client for writing data.
        
        Raises:
            Exception: If client initialization fails
        """
        logger.info("Initializing Timestream client")
        
        try:
            self.timestream_client = TimestreamClient(
                database_name=self.database_name,
                region_name=self.region_name,
                max_retries=3
            )
            logger.info("Timestream client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Timestream client: {e}")
            raise
    
    def generate_and_write_data(self) -> None:
        """
        Generate sensor data for all buses and stops and write to Timestream.
        
        This method:
        1. Gets the current time
        2. Generates sensor data for each bus (with current bus state)
        3. Generates sensor data for each stop
        4. Writes all data points to Timestream in a single batch
        """
        current_time = datetime.now()
        
        logger.debug(f"Generating sensor data at {current_time}")
        
        # Generate data for all entities
        records = []
        
        # Generate sensor data for all buses
        for bus_id, bus_state in self.buses.items():
            try:
                sensor_data = generate_sensor_data(
                    entity_id=bus_id,
                    entity_type="bus",
                    current_time=current_time,
                    bus_state=bus_state
                )
                
                # Create Timestream record
                timestamp_ms = int(current_time.timestamp() * 1000)
                
                record = {
                    'Dimensions': [
                        {'Name': 'entity_id', 'Value': sensor_data.entity_id},
                        {'Name': 'entity_type', 'Value': sensor_data.entity_type}
                    ],
                    'MeasureName': 'metrics',
                    'MeasureValueType': 'MULTI',
                    'MeasureValues': [
                        {
                            'Name': 'temperature',
                            'Value': str(sensor_data.temperature),
                            'Type': 'DOUBLE'
                        },
                        {
                            'Name': 'humidity',
                            'Value': str(sensor_data.humidity),
                            'Type': 'DOUBLE'
                        },
                        {
                            'Name': 'co2_level',
                            'Value': str(sensor_data.co2_level),
                            'Type': 'BIGINT'
                        },
                        {
                            'Name': 'door_status',
                            'Value': sensor_data.door_status,
                            'Type': 'VARCHAR'
                        }
                    ],
                    'Time': str(timestamp_ms),
                    'TimeUnit': 'MILLISECONDS'
                }
                
                records.append(record)
                
                logger.debug(
                    f"Bus {bus_id}: temp={sensor_data.temperature:.1f}°C, "
                    f"humidity={sensor_data.humidity:.1f}%, "
                    f"CO2={sensor_data.co2_level}ppm, door={sensor_data.door_status}"
                )
                
            except Exception as e:
                logger.error(f"Error generating sensor data for bus {bus_id}: {e}")
                # Continue with other buses
                continue
        
        # Generate sensor data for all stops
        for stop_id, stop in self.stops.items():
            try:
                sensor_data = generate_sensor_data(
                    entity_id=stop_id,
                    entity_type="stop",
                    current_time=current_time,
                    bus_state=None
                )
                
                # Create Timestream record
                timestamp_ms = int(current_time.timestamp() * 1000)
                
                record = {
                    'Dimensions': [
                        {'Name': 'entity_id', 'Value': sensor_data.entity_id},
                        {'Name': 'entity_type', 'Value': sensor_data.entity_type}
                    ],
                    'MeasureName': 'metrics',
                    'MeasureValueType': 'MULTI',
                    'MeasureValues': [
                        {
                            'Name': 'temperature',
                            'Value': str(sensor_data.temperature),
                            'Type': 'DOUBLE'
                        },
                        {
                            'Name': 'humidity',
                            'Value': str(sensor_data.humidity),
                            'Type': 'DOUBLE'
                        }
                    ],
                    'Time': str(timestamp_ms),
                    'TimeUnit': 'MILLISECONDS'
                }
                
                records.append(record)
                
                logger.debug(
                    f"Stop {stop_id}: temp={sensor_data.temperature:.1f}°C, "
                    f"humidity={sensor_data.humidity:.1f}%"
                )
                
            except Exception as e:
                logger.error(f"Error generating sensor data for stop {stop_id}: {e}")
                # Continue with other stops
                continue
        
        # Write all records to Timestream
        if records:
            try:
                self.timestream_client.write_records(
                    table_name=self.table_name,
                    records=records
                )
                logger.info(
                    f"Successfully wrote {len(records)} sensor data records to Timestream "
                    f"({len(self.buses)} buses, {len(self.stops)} stops)"
                )
            except Exception as e:
                logger.error(f"Failed to write records to Timestream: {e}")
                # Don't raise - we'll try again on the next iteration
        else:
            logger.warning("No records generated to write")
    
    def run(self) -> None:
        """
        Main service loop - runs continuously until interrupted.
        
        This method:
        1. Loads configuration
        2. Initializes Timestream client
        3. Runs an infinite loop generating and writing data at regular intervals
        4. Handles errors gracefully with logging
        """
        logger.info("Starting Sensor Data Feeder Service")
        
        try:
            # Initialize
            self.load_configuration()
            self.initialize_timestream_client()
            
            logger.info(
                f"Service initialized successfully. "
                f"Starting continuous generation loop (interval: {self.time_interval}s)"
            )
            
            # Main loop
            iteration = 0
            while True:
                iteration += 1
                loop_start = time.time()
                
                try:
                    logger.info(f"Starting iteration {iteration}")
                    self.generate_and_write_data()
                    
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
        
        logger.info("Sensor Data Feeder Service stopped")


def main():
    """
    Main entry point for the Sensor Data Feeder Service.
    
    Reads configuration from environment variables and starts the service.
    """
    # Read configuration from environment variables
    database_name = os.getenv('TIMESTREAM_DATABASE', 'bus_simulator')
    table_name = os.getenv('TIMESTREAM_TABLE', 'sensor_data')
    config_file = os.getenv('CONFIG_FILE', 'data/lines.yaml')
    time_interval = int(os.getenv('TIME_INTERVAL', '60'))
    region_name = os.getenv('AWS_REGION', 'eu-west-1')
    
    # Validate configuration
    if not os.path.exists(config_file):
        logger.error(f"Configuration file not found: {config_file}")
        sys.exit(1)
    
    if time_interval <= 0:
        logger.error(f"TIME_INTERVAL must be positive, got {time_interval}")
        sys.exit(1)
    
    # Create and run service
    service = SensorDataFeederService(
        config_file=config_file,
        database_name=database_name,
        table_name=table_name,
        time_interval=time_interval,
        region_name=region_name
    )
    
    service.run()


if __name__ == '__main__':
    main()
