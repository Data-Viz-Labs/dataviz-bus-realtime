"""
Lambda handler for the Bus Position API.

This module provides REST API endpoints for querying bus position data.
Supports both latest data queries and historical queries at specific timestamps.
Also supports querying all buses on a specific line.

Endpoints:
    - GET /bus-position/{bus_id}?mode=latest
    - GET /bus-position/{bus_id}?timestamp=<ISO8601>
    - GET /bus-position/line/{line_id}?mode=latest

Requirements: 3.3, 3.4
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

# Import TimestreamClient from common module
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from common.timestream_client import TimestreamClient

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Timestream client (reused across Lambda invocations)
TIMESTREAM_DATABASE = os.environ.get('TIMESTREAM_DATABASE', 'bus_simulator')
TIMESTREAM_TABLE = os.environ.get('TIMESTREAM_TABLE', 'bus_position')
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
    Handle Bus Position API requests.
    
    Routes requests to appropriate query function based on path and query parameters.
    Supports both latest data queries and historical queries at specific timestamps.
    Also supports querying all buses on a specific line.
    
    Args:
        event: API Gateway event containing path parameters and query string
        context: Lambda context object
    
    Returns:
        API Gateway response with status code, headers, and body
    
    Example events:
        Single bus latest:
            {
                'pathParameters': {'bus_id': 'B001'},
                'queryStringParameters': {'mode': 'latest'}
            }
        
        Single bus historical:
            {
                'pathParameters': {'bus_id': 'B001'},
                'queryStringParameters': {'timestamp': '2024-01-15T10:30:00Z'}
            }
        
        All buses on a line:
            {
                'pathParameters': {'line_id': 'L1'},
                'path': '/bus-position/line/L1',
                'queryStringParameters': {'mode': 'latest'}
            }
    """
    try:
        # Extract path parameters
        path_params = event.get('pathParameters', {})
        path = event.get('path', '')
        
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Determine if this is a line query or single bus query
        if '/line/' in path and 'line_id' in path_params:
            # Query all buses on a line
            line_id = path_params['line_id']
            
            if 'latest' in query_params or query_params.get('mode') == 'latest':
                result = query_line_buses(line_id)
            else:
                return error_response(
                    400,
                    "Line queries only support 'mode=latest' parameter"
                )
            
            if result is None or not result:
                return error_response(404, f"No buses found for line {line_id}")
            
            return success_response({'buses': result})
        
        else:
            # Query single bus
            if not path_params or 'bus_id' not in path_params:
                return error_response(400, "Missing required path parameter: bus_id")
            
            bus_id = path_params['bus_id']
            
            # Determine query type and execute
            if 'latest' in query_params or query_params.get('mode') == 'latest':
                result = query_latest_bus_position(bus_id)
            elif 'timestamp' in query_params:
                try:
                    timestamp = parse_iso8601(query_params['timestamp'])
                    result = query_bus_position_at_time(bus_id, timestamp)
                except ValueError as e:
                    return error_response(400, f"Invalid timestamp format: {str(e)}")
            else:
                return error_response(
                    400,
                    "Must specify 'mode=latest' or 'timestamp' parameter"
                )
            
            # Check if data was found
            if result is None:
                return error_response(404, f"No data found for bus {bus_id}")
            
            return success_response(result)
    
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}", exc_info=True)
        return error_response(500, "Internal server error")


def query_latest_bus_position(bus_id: str) -> Optional[Dict[str, Any]]:
    """
    Query Timestream for the latest bus position.
    
    Args:
        bus_id: Bus identifier
    
    Returns:
        Dictionary with bus position data or None if not found
    
    Example response:
        {
            'bus_id': 'B001',
            'line_id': 'L1',
            'timestamp': '2024-01-15T10:30:00Z',
            'latitude': 40.4165,
            'longitude': -3.7026,
            'passenger_count': 25,
            'next_stop_id': 'S003',
            'distance_to_next_stop': 450.5,
            'speed': 35.2
        }
    """
    try:
        client = get_timestream_client()
        
        # Query latest data for this bus
        result = client.query_latest(
            table_name=TIMESTREAM_TABLE,
            dimensions={'bus_id': bus_id},
            limit=1
        )
        
        if not result or not result.get('rows'):
            logger.info(f"No data found for bus {bus_id}")
            return None
        
        # Parse the first row
        row = result['rows'][0]
        
        return format_bus_position_response(row)
    
    except Exception as e:
        logger.error(f"Error querying latest bus position for bus {bus_id}: {str(e)}")
        raise


def query_bus_position_at_time(bus_id: str, timestamp: datetime) -> Optional[Dict[str, Any]]:
    """
    Query Timestream for bus position at a specific time.
    
    Retrieves the most recent data point at or before the specified timestamp.
    
    Args:
        bus_id: Bus identifier
        timestamp: Query for data at or before this time
    
    Returns:
        Dictionary with bus position data or None if not found
    
    Example response:
        {
            'bus_id': 'B001',
            'line_id': 'L1',
            'timestamp': '2024-01-15T10:30:00Z',
            'latitude': 40.4165,
            'longitude': -3.7026,
            'passenger_count': 25,
            'next_stop_id': 'S003',
            'distance_to_next_stop': 450.5,
            'speed': 35.2
        }
    """
    try:
        client = get_timestream_client()
        
        # Query data at or before the specified timestamp
        result = client.query_at_time(
            table_name=TIMESTREAM_TABLE,
            dimensions={'bus_id': bus_id},
            timestamp=timestamp,
            limit=1
        )
        
        if not result or not result.get('rows'):
            logger.info(f"No data found for bus {bus_id} at time {timestamp.isoformat()}")
            return None
        
        # Parse the first row
        row = result['rows'][0]
        
        return format_bus_position_response(row)
    
    except Exception as e:
        logger.error(
            f"Error querying bus position for bus {bus_id} at time {timestamp.isoformat()}: {str(e)}"
        )
        raise


def query_line_buses(line_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Query Timestream for all buses on a specific line.
    
    Returns the latest position for each bus operating on the specified line.
    
    Args:
        line_id: Line identifier
    
    Returns:
        List of dictionaries with bus position data or None if not found
    
    Example response:
        [
            {
                'bus_id': 'B001',
                'line_id': 'L1',
                'timestamp': '2024-01-15T10:30:00Z',
                'latitude': 40.4165,
                'longitude': -3.7026,
                'passenger_count': 25,
                'next_stop_id': 'S003',
                'distance_to_next_stop': 450.5,
                'speed': 35.2
            },
            {
                'bus_id': 'B002',
                'line_id': 'L1',
                ...
            }
        ]
    """
    try:
        client = get_timestream_client()
        
        # Query for all buses on this line
        # We need to get the latest position for each bus
        query = f"""
            SELECT *
            FROM "{TIMESTREAM_DATABASE}"."{TIMESTREAM_TABLE}"
            WHERE line_id = '{line_id}'
            AND time >= ago(5m)
            ORDER BY time DESC
        """
        
        logger.debug(f"Executing query for line {line_id}: {query}")
        
        result = client._execute_query(query)
        
        if not result or not result.get('rows'):
            logger.info(f"No buses found for line {line_id}")
            return None
        
        # Group by bus_id and get the latest position for each
        buses_by_id = {}
        for row in result['rows']:
            bus_id = row.get('bus_id')
            if bus_id and bus_id not in buses_by_id:
                buses_by_id[bus_id] = format_bus_position_response(row)
        
        # Return list of bus positions
        bus_list = list(buses_by_id.values())
        
        logger.info(f"Found {len(bus_list)} buses for line {line_id}")
        
        return bus_list if bus_list else None
    
    except Exception as e:
        logger.error(f"Error querying buses for line {line_id}: {str(e)}")
        raise


def format_bus_position_response(row: Dict[str, Any]) -> Dict[str, Any]:
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
        'bus_id': row.get('bus_id'),
        'line_id': row.get('line_id'),
        'timestamp': row.get('time'),
        'latitude': float(row.get('latitude', 0)) if row.get('latitude') else None,
        'longitude': float(row.get('longitude', 0)) if row.get('longitude') else None,
        'passenger_count': int(row.get('passenger_count', 0)) if row.get('passenger_count') else 0,
        'next_stop_id': row.get('next_stop_id'),
        'distance_to_next_stop': float(row.get('distance_to_next_stop', 0)) if row.get('distance_to_next_stop') else None,
        'speed': float(row.get('speed', 0)) if row.get('speed') else None,
        'direction': int(row.get('direction', 0)) if row.get('direction') is not None else 0
    }
    
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
