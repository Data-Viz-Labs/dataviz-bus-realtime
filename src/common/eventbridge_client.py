"""
EventBridge client wrapper for the Madrid Bus Real-Time Simulator.

This module provides a wrapper around the AWS EventBridge client
with retry logic, exponential backoff, and convenience methods for publishing
bus position and arrival events.
"""

import time
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    # Allow module to be imported for testing without boto3
    boto3 = None
    ClientError = Exception


logger = logging.getLogger(__name__)


class EventBridgeClient:
    """
    Wrapper for AWS EventBridge operations with retry logic.
    
    This client provides methods for publishing bus position updates and
    arrival events with automatic retry on failures.
    """
    
    def __init__(
        self,
        event_bus_name: str,
        region_name: str = "eu-west-1",
        max_retries: int = 3,
        client: Optional[Any] = None
    ):
        """
        Initialize EventBridge client.
        
        Args:
            event_bus_name: Name of the EventBridge event bus
            region_name: AWS region name
            max_retries: Maximum number of retry attempts for failed publishes
            client: Optional boto3 client (for testing)
        
        Raises:
            ImportError: If boto3 is not installed
        """
        if boto3 is None and client is None:
            raise ImportError("boto3 is required but not installed")
        
        self.event_bus_name = event_bus_name
        self.region_name = region_name
        self.max_retries = max_retries
        
        # Use provided client or create new one
        self.client = client or boto3.client(
            'events',
            region_name=region_name
        )
    
    def publish_bus_position_event(
        self,
        bus_id: str,
        line_id: str,
        timestamp: datetime,
        latitude: float,
        longitude: float,
        passenger_count: int,
        next_stop_id: str,
        distance_to_next_stop: float,
        speed: float
    ) -> bool:
        """
        Publish a bus position update event to EventBridge.
        
        Args:
            bus_id: Unique identifier for the bus
            line_id: Bus line this bus operates on
            timestamp: Timestamp of the position update
            latitude: Current latitude
            longitude: Current longitude
            passenger_count: Current number of passengers
            next_stop_id: Next stop on the route
            distance_to_next_stop: Distance to next stop in meters
            speed: Current speed in km/h
        
        Returns:
            True if publish succeeded, False otherwise
        
        Example:
            client.publish_bus_position_event(
                bus_id='B001',
                line_id='L1',
                timestamp=datetime.now(),
                latitude=40.4657,
                longitude=-3.6886,
                passenger_count=25,
                next_stop_id='S002',
                distance_to_next_stop=500.0,
                speed=30.0
            )
        """
        detail = {
            'bus_id': bus_id,
            'line_id': line_id,
            'timestamp': timestamp.isoformat(),
            'latitude': latitude,
            'longitude': longitude,
            'passenger_count': passenger_count,
            'next_stop_id': next_stop_id,
            'distance_to_next_stop': distance_to_next_stop,
            'speed': speed
        }
        
        return self._publish_event(
            source='bus-simulator',
            detail_type='bus.position.updated',
            detail=detail
        )
    
    def publish_bus_arrival_events(
        self,
        bus_id: str,
        line_id: str,
        stop_id: str,
        timestamp: datetime,
        passengers_boarding: int,
        passengers_alighting: int,
        bus_passenger_count: int,
        stop_people_count: int
    ) -> bool:
        """
        Publish coordinated bus arrival events (bus + stop state changes).
        
        This method publishes a single event that contains both bus and stop
        information for coordinated arrival processing.
        
        Args:
            bus_id: Unique identifier for the bus
            line_id: Bus line this bus operates on
            stop_id: Stop where the bus arrived
            timestamp: Timestamp of the arrival
            passengers_boarding: Number of passengers boarding
            passengers_alighting: Number of passengers alighting
            bus_passenger_count: Passenger count on bus after arrival
            stop_people_count: People count at stop after arrival
        
        Returns:
            True if publish succeeded, False otherwise
        
        Example:
            client.publish_bus_arrival_events(
                bus_id='B001',
                line_id='L1',
                stop_id='S002',
                timestamp=datetime.now(),
                passengers_boarding=5,
                passengers_alighting=3,
                bus_passenger_count=27,
                stop_people_count=10
            )
        """
        detail = {
            'bus_id': bus_id,
            'line_id': line_id,
            'stop_id': stop_id,
            'timestamp': timestamp.isoformat(),
            'passengers_boarding': passengers_boarding,
            'passengers_alighting': passengers_alighting,
            'bus_passenger_count': bus_passenger_count,
            'stop_people_count': stop_people_count
        }
        
        return self._publish_event(
            source='bus-simulator',
            detail_type='bus.arrival',
            detail=detail
        )
    
    def _publish_event(
        self,
        source: str,
        detail_type: str,
        detail: Dict[str, Any]
    ) -> bool:
        """
        Publish an event to EventBridge with exponential backoff retry logic.
        
        Args:
            source: Event source identifier
            detail_type: Type of event
            detail: Event detail dictionary
        
        Returns:
            True if publish succeeded, False otherwise
        """
        for attempt in range(self.max_retries):
            try:
                entry = {
                    'Source': source,
                    'DetailType': detail_type,
                    'Detail': json.dumps(detail),
                    'EventBusName': self.event_bus_name
                }
                
                response = self.client.put_events(Entries=[entry])
                
                # Check for failed entries
                failed_count = response.get('FailedEntryCount', 0)
                if failed_count > 0:
                    failed_entries = response.get('Entries', [])
                    error_msg = failed_entries[0].get('ErrorMessage', 'Unknown error') if failed_entries else 'Unknown error'
                    raise Exception(f"Failed to publish event: {error_msg}")
                
                logger.info(
                    f"Successfully published event to EventBridge: "
                    f"source={source}, detail_type={detail_type}"
                )
                return True
                
            except (ClientError, Exception) as e:
                if attempt == self.max_retries - 1:
                    # Log warning and continue (non-critical failure)
                    logger.warning(
                        f"Failed to publish event to EventBridge after {self.max_retries} attempts: "
                        f"{str(e)}. Continuing without event publication."
                    )
                    return False
                
                # Calculate exponential backoff wait time
                wait_time = 2 ** attempt
                
                logger.warning(
                    f"EventBridge publish failed (attempt {attempt + 1}/{self.max_retries}): "
                    f"{str(e)}. Retrying in {wait_time}s..."
                )
                
                time.sleep(wait_time)
        
        return False
