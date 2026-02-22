#!/usr/bin/env python3
"""
People Count Feeder Service for the Madrid Bus Real-Time Simulator.

This service runs continuously as a Fargate container, generating realistic
people count data at bus stops and writing it to AWS Timestream. It maintains
state for each stop and coordinates with bus arrival events.

Environment Variables:
    TIMESTREAM_DATABASE: Name of the Timestream database (default: bus_simulator)
    TIMESTREAM_TABLE: Name of the Timestream table (default: people_count)
    CONFIG_FILE: Path to lines.yaml configuration file (default: data/lines.yaml)
    TIME_INTERVAL: Time interval between updates in seconds (default: 60)
    AWS_REGION: AWS region for Timestream (default: eu-west-1)
    LOG_LEVEL: Logging level (default: INFO)

Usage:
    # Run with default settings
    python people_count_feeder.py
    
    # Run with custom configuration
    TIMESTREAM_DATABASE=my_db CONFIG_FILE=/config/lines.yaml python people_count_feeder.py
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
from common.models import Route, BusArrival
from feeders.people_count_generator import generate_people_count


# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class PeopleCountFeederService:
    """
    Main service class for the People Count Feeder.
    
    This service maintains state for each bus stop and continuously generates
    realistic people count data based on daily patterns and bus arrivals.
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
        Initialize the People Count Feeder Service.
        
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
        self.stop_counts: Dict[str, int] = {}  # stop_id -> current count
        self.stop_to_lines: Dict[str, List[str]] = {}  # stop_id -> [line_ids]
        self.stops_config: Dict[str, float] = {}  # stop_id -> base_arrival_rate
        
        # Timestream client
        self.timestream_client: TimestreamClient = None
        
        logger.info(
            f"Initializing People Count Feeder Service: "
            f"database={database_name}, table={table_name}, "
            f"interval={time_interval}s, region={region_name}"
        )
    
    def load_configuration(self) -> None:
        """
        Load bus lines and stops configuration from YAML file.
        
        Raises:
            ConfigurationError: If configuration loading fails
        """
        logger.info(f"Loading configuration from {self.config_file}")
        
        try:
            routes, _ = load_configuration(self.config_file)
            self.routes = routes
            
            # Initialize state for each stop
            for route in routes:
                for stop in route.stops:
                    # Initialize count to 0 if not already set
                    if stop.stop_id not in self.stop_counts:
                        self.stop_counts[stop.stop_id] = 0
                    
                    # Track which lines serve this stop
                    if stop.stop_id not in self.stop_to_lines:
                        self.stop_to_lines[stop.stop_id] = []
                    self.stop_to_lines[stop.stop_id].append(route.line_id)
                    
                    # Store base arrival rate for this stop
                    self.stops_config[stop.stop_id] = stop.base_arrival_rate
            
            logger.info(
                f"Configuration loaded successfully: "
                f"{len(self.routes)} lines, {len(self.stop_counts)} stops"
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
        Generate people count data for all stops and write to Timestream.
        
        This method:
        1. Gets the current time
        2. Generates people count for each stop (no bus arrivals in this simple version)
        3. Writes all data points to Timestream in a single batch
        4. Updates internal state
        """
        current_time = datetime.now()
        time_interval_minutes = self.time_interval / 60.0
        
        logger.debug(f"Generating people count data at {current_time}")
        
        # Generate data for all stops
        records = []
        
        for stop_id, previous_count in self.stop_counts.items():
            try:
                # For now, we don't have bus arrival events
                # In a full implementation, this would coordinate with bus position feeder
                bus_arrivals: List[BusArrival] = []
                
                # Generate new count
                new_count = generate_people_count(
                    stop_id=stop_id,
                    current_time=current_time,
                    previous_count=previous_count,
                    bus_arrivals=bus_arrivals,
                    stops_config=self.stops_config,
                    time_interval_minutes=time_interval_minutes
                )
                
                # Update state
                self.stop_counts[stop_id] = new_count
                
                # Get line IDs for this stop
                line_ids = self.stop_to_lines.get(stop_id, [])
                
                # Create Timestream record
                # Note: Timestream expects time in milliseconds since epoch
                timestamp_ms = int(current_time.timestamp() * 1000)
                
                record = {
                    'Dimensions': [
                        {'Name': 'stop_id', 'Value': stop_id},
                        {'Name': 'line_ids', 'Value': ','.join(line_ids)}
                    ],
                    'MeasureName': 'count',
                    'MeasureValue': str(new_count),
                    'MeasureValueType': 'BIGINT',
                    'Time': str(timestamp_ms),
                    'TimeUnit': 'MILLISECONDS'
                }
                
                records.append(record)
                
                logger.debug(
                    f"Stop {stop_id}: {previous_count} -> {new_count} people "
                    f"(lines: {', '.join(line_ids)})"
                )
                
            except Exception as e:
                logger.error(f"Error generating data for stop {stop_id}: {e}")
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
                    f"Successfully wrote {len(records)} people count records to Timestream"
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
        logger.info("Starting People Count Feeder Service")
        
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
        
        logger.info("People Count Feeder Service stopped")


def main():
    """
    Main entry point for the People Count Feeder Service.
    
    Reads configuration from environment variables and starts the service.
    """
    # Read configuration from environment variables
    database_name = os.getenv('TIMESTREAM_DATABASE', 'bus_simulator')
    table_name = os.getenv('TIMESTREAM_TABLE', 'people_count')
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
    service = PeopleCountFeederService(
        config_file=config_file,
        database_name=database_name,
        table_name=table_name,
        time_interval=time_interval,
        region_name=region_name
    )
    
    service.run()


if __name__ == '__main__':
    main()
