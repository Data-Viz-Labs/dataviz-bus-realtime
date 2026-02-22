"""
Lambda handler for the Sensors API.

This module provides REST API endpoints for querying sensor data from buses and stops.
Supports both latest data queries and historical queries at specific timestamps.

Endpoints:
    - GET /sensors/{entity_type}/{entity_id}?mode=latest
    - GET /sensors/{entity_type}/{entity_id}?timestamp=<ISO8601>

Requirements: 2.1, 2.2, 2.4
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Import TimestreamClient from common module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.timestream_client import TimestreamClient

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Timestream client (reused across Lambda invocations)
TIMESTREAM_DATABASE = os.environ.get('TIMESTREAM_DATABASE', 'bus_simulator')
TIMESTREAM_TABLE = os.environ.get('TIMESTREAM_TABLE', 'sensor_data')
AWS_REGION = os.environ.get('AWS_REGION', 'eu-west-1')

timestream_client = None


def get_timestream_client() -> TimestreamClient:
    """
    Get or create Timestream client instance.
    
    Returns:
        TimestreamClient instance
    """
    global timestream_client
    if timestream_client is None:
        timestream_client = TimestreamClient(
            database_name=TIMESTREAM_DATABASE,
            region_name=AWS_REGION
        )
    return timestream_client


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle Sensors API requests.
    
    Routes requests to appropriate query function based on query parameters.
    Supports both latest data queries and historical queries at specific timestamps.
    
    Args:
        event: API Gateway event containing path parameters and query string
        context: Lambda context object
    
    Returns:
        API Gateway response with status code, headers, and body
    
    Example event:
        {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {'mode': 'latest'}
        }
    """
    try:
        # Extract entity_type and entity_id from path parameters
        path_params = event.get('pathParameters', {})
        if not path_params or 'entity_type' not in path_params or 'entity_id' not in path_params:
            return error_response(400, "Missing required path parameters: entity_type and entity_id")
        
        entity_type = path_params['entity_type']
        entity_id = path_params['entity_id']
        
        # Validate entity_type
        if entity_type not in ['bus', 'stop']:
            return error_response(400, f"Invalid entity_type: {entity_type}. Must be 'bus' or 'stop'")
        
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Determine query type and execute
        if 'latest' in query_params or query_params.get('mode') == 'latest':
            result = query_latest_sensor_data(entity_type, entity_id)
        elif 'timestamp' in query_params:
            try:
                timestamp = parse_iso8601(query_params['timestamp'])
                result = query_sensor_data_at_time(entity_type, entity_id, timestamp)
            except ValueError as e:
                return error_response(400, f"Invalid timestamp format: {str(e)}")
        else:
            return error_response(
                400,
                "Must specify 'mode=latest' or 'timestamp' parameter"
            )
        
        # Check if data was found
        if result is None:
            return error_response(404, f"No data found for {entity_type} {entity_id}")
        
        return success_response(result)
    
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}", exc_info=True)
        return error_response(500, "Internal server error")


def query_latest_sensor_data(entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
    """
    Query Timestream for the latest sensor data for a bus or stop.
    
    Args:
        entity_type: Type of entity ('bus' or 'stop')
        entity_id: Entity identifier (bus ID or stop ID)
    
    Returns:
        Dictionary with sensor data or None if not found
    
    Example response:
        {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 45.2,
            'co2_level': 650,
            'door_status': 'closed'
        }
    """
    try:
        client = get_timestream_client()
        
        # Query latest data for this entity
        result = client.query_latest(
            table_name=TIMESTREAM_TABLE,
            dimensions={'entity_id': entity_id, 'entity_type': entity_type},
            limit=1
        )
        
        if not result or not result.get('rows'):
            logger.info(f"No data found for {entity_type} {entity_id}")
            return None
        
        # Parse the first row
        row = result['rows'][0]
        
        return format_sensor_response(row)
    
    except Exception as e:
        logger.error(f"Error querying latest sensor data for {entity_type} {entity_id}: {str(e)}")
        raise


def query_sensor_data_at_time(
    entity_type: str,
    entity_id: str,
    timestamp: datetime
) -> Optional[Dict[str, Any]]:
    """
    Query Timestream for sensor data at a specific time.
    
    Retrieves the most recent data point at or before the specified timestamp.
    
    Args:
        entity_type: Type of entity ('bus' or 'stop')
        entity_id: Entity identifier (bus ID or stop ID)
        timestamp: Query for data at or before this time
    
    Returns:
        Dictionary with sensor data or None if not found
    
    Example response:
        {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 45.2,
            'co2_level': 650,
            'door_status': 'closed'
        }
    """
    try:
        client = get_timestream_client()
        
        # Query data at or before the specified timestamp
        result = client.query_at_time(
            table_name=TIMESTREAM_TABLE,
            dimensions={'entity_id': entity_id, 'entity_type': entity_type},
            timestamp=timestamp,
            limit=1
        )
        
        if not result or not result.get('rows'):
            logger.info(
                f"No data found for {entity_type} {entity_id} at time {timestamp.isoformat()}"
            )
            return None
        
        # Parse the first row
        row = result['rows'][0]
        
        return format_sensor_response(row)
    
    except Exception as e:
        logger.error(
            f"Error querying sensor data for {entity_type} {entity_id} "
            f"at time {timestamp.isoformat()}: {str(e)}"
        )
        raise


def format_sensor_response(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format Timestream query result into API response format.
    
    Args:
        row: Raw row data from Timestream query
    
    Returns:
        Formatted response dictionary
    """
    # Extract fields from row
    # Note: Timestream returns all values as strings, so we need to convert types
    response = {
        'entity_id': row.get('entity_id'),
        'entity_type': row.get('entity_type'),
        'timestamp': row.get('time'),
        'temperature': float(row.get('temperature', 0)) if row.get('temperature') else None,
        'humidity': float(row.get('humidity', 0)) if row.get('humidity') else None
    }
    
    # Add bus-specific fields if entity_type is 'bus'
    if row.get('entity_type') == 'bus':
        co2_level = row.get('co2_level')
        response['co2_level'] = int(co2_level) if co2_level else None
        response['door_status'] = row.get('door_status')
    
    return response


def parse_iso8601(timestamp_str: str) -> datetime:
    """
    Parse ISO8601 timestamp string to datetime object.
    
    Args:
        timestamp_str: ISO8601 formatted timestamp string
    
    Returns:
        datetime object
    
    Raises:
        ValueError: If timestamp format is invalid
    
    Examples:
        - "2024-01-15T10:30:00Z"
        - "2024-01-15T10:30:00+00:00"
        - "2024-01-15T10:30:00.123Z"
    """
    try:
        # Try parsing with timezone
        if timestamp_str.endswith('Z'):
            # Replace Z with +00:00 for Python's fromisoformat
            timestamp_str = timestamp_str[:-1] + '+00:00'
        
        return datetime.fromisoformat(timestamp_str)
    
    except ValueError:
        # Try alternative formats
        try:
            # Try without timezone
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            raise ValueError(
                f"Invalid ISO8601 timestamp format: {timestamp_str}. "
                "Expected format: YYYY-MM-DDTHH:MM:SS[.mmm][Z|±HH:MM]"
            )


def success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate standardized success response.
    
    Args:
        data: Response data to return
    
    Returns:
        API Gateway response dictionary
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(data)
    }


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Generate standardized error response.
    
    Args:
        status_code: HTTP status code (400, 404, 500, etc.)
        message: Error message to return
    
    Returns:
        API Gateway response dictionary
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps({
            'error': True,
            'message': message,
            'timestamp': datetime.now().astimezone().isoformat()
        })
    }
