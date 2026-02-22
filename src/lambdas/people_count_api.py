"""
Lambda handler for the People Count API.

This module provides REST API endpoints for querying people count data at bus stops.
Supports both latest data queries and historical queries at specific timestamps.

Endpoints:
    - GET /people-count/{stop_id}?mode=latest
    - GET /people-count/{stop_id}?timestamp=<ISO8601>

Requirements: 1.1, 1.2, 1.3
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
TIMESTREAM_TABLE = os.environ.get('TIMESTREAM_TABLE', 'people_count')
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
    Handle People Count API requests.
    
    Routes requests to appropriate query function based on query parameters.
    Supports both latest data queries and historical queries at specific timestamps.
    
    Args:
        event: API Gateway event containing path parameters and query string
        context: Lambda context object
    
    Returns:
        API Gateway response with status code, headers, and body
    
    Example event:
        {
            'pathParameters': {'stop_id': 'S001'},
            'queryStringParameters': {'mode': 'latest'}
        }
    """
    try:
        # Extract stop_id from path parameters
        path_params = event.get('pathParameters', {})
        if not path_params or 'stop_id' not in path_params:
            return error_response(400, "Missing required path parameter: stop_id")
        
        stop_id = path_params['stop_id']
        
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        
        # Determine query type and execute
        if 'latest' in query_params or query_params.get('mode') == 'latest':
            result = query_latest_people_count(stop_id)
        elif 'timestamp' in query_params:
            try:
                timestamp = parse_iso8601(query_params['timestamp'])
                result = query_people_count_at_time(stop_id, timestamp)
            except ValueError as e:
                return error_response(400, f"Invalid timestamp format: {str(e)}")
        else:
            return error_response(
                400,
                "Must specify 'mode=latest' or 'timestamp' parameter"
            )
        
        # Check if data was found
        if result is None:
            return error_response(404, f"No data found for stop {stop_id}")
        
        return success_response(result)
    
    except Exception as e:
        logger.error(f"Unexpected error in lambda_handler: {str(e)}", exc_info=True)
        return error_response(500, "Internal server error")


def query_latest_people_count(stop_id: str) -> Optional[Dict[str, Any]]:
    """
    Query Timestream for the latest people count at a stop.
    
    Args:
        stop_id: Bus stop identifier
    
    Returns:
        Dictionary with people count data or None if not found
    
    Example response:
        {
            'stop_id': 'S001',
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 15,
            'line_ids': ['L1', 'L2']
        }
    """
    try:
        client = get_timestream_client()
        
        # Query latest data for this stop
        result = client.query_latest(
            table_name=TIMESTREAM_TABLE,
            dimensions={'stop_id': stop_id},
            limit=1
        )
        
        if not result or not result.get('rows'):
            logger.info(f"No data found for stop {stop_id}")
            return None
        
        # Parse the first row
        row = result['rows'][0]
        
        return format_people_count_response(row)
    
    except Exception as e:
        logger.error(f"Error querying latest people count for stop {stop_id}: {str(e)}")
        raise


def query_people_count_at_time(stop_id: str, timestamp: datetime) -> Optional[Dict[str, Any]]:
    """
    Query Timestream for people count at a specific time.
    
    Retrieves the most recent data point at or before the specified timestamp.
    
    Args:
        stop_id: Bus stop identifier
        timestamp: Query for data at or before this time
    
    Returns:
        Dictionary with people count data or None if not found
    
    Example response:
        {
            'stop_id': 'S001',
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 15,
            'line_ids': ['L1', 'L2']
        }
    """
    try:
        client = get_timestream_client()
        
        # Query data at or before the specified timestamp
        result = client.query_at_time(
            table_name=TIMESTREAM_TABLE,
            dimensions={'stop_id': stop_id},
            timestamp=timestamp,
            limit=1
        )
        
        if not result or not result.get('rows'):
            logger.info(f"No data found for stop {stop_id} at time {timestamp.isoformat()}")
            return None
        
        # Parse the first row
        row = result['rows'][0]
        
        return format_people_count_response(row)
    
    except Exception as e:
        logger.error(
            f"Error querying people count for stop {stop_id} at time {timestamp.isoformat()}: {str(e)}"
        )
        raise


def format_people_count_response(row: Dict[str, Any]) -> Dict[str, Any]:
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
        'stop_id': row.get('stop_id'),
        'timestamp': row.get('time'),
        'count': int(row.get('count', 0)) if row.get('count') else 0
    }
    
    # Parse line_ids if present (may be stored as comma-separated string or array)
    line_ids = row.get('line_ids')
    if line_ids:
        if isinstance(line_ids, str):
            # If stored as comma-separated string
            response['line_ids'] = [lid.strip() for lid in line_ids.split(',')]
        else:
            response['line_ids'] = line_ids
    else:
        response['line_ids'] = []
    
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
