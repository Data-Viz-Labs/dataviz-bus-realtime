"""
Unit tests for the Sensors API Lambda function.

Tests the Lambda handler, query functions, and error handling.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import the Lambda handler module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.sensors_api import (
    lambda_handler,
    query_latest_sensor_data,
    query_sensor_data_at_time,
    format_sensor_response,
    parse_iso8601,
    success_response,
    error_response
)


class TestLambdaHandler:
    """Test the main Lambda handler function."""
    
    def test_missing_entity_type(self):
        """Test error response when entity_type is missing."""
        event = {
            'pathParameters': {'entity_id': 'B001'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'entity_type' in body['message']
    
    def test_missing_entity_id(self):
        """Test error response when entity_id is missing."""
        event = {
            'pathParameters': {'entity_type': 'bus'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'entity_id' in body['message']
    
    def test_invalid_entity_type(self):
        """Test error response for invalid entity_type."""
        event = {
            'pathParameters': {'entity_type': 'invalid', 'entity_id': 'B001'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'entity_type' in body['message'].lower()
    
    def test_missing_query_parameters(self):
        """Test error response when query parameters are missing."""
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'mode' in body['message'] or 'timestamp' in body['message']
    
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    def test_latest_query_success_for_bus(self, mock_query):
        """Test successful latest query for a bus."""
        mock_query.return_value = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 45.2,
            'co2_level': 650,
            'door_status': 'closed'
        }
        
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['entity_id'] == 'B001'
        assert body['entity_type'] == 'bus'
        assert body['temperature'] == 22.5
        assert body['co2_level'] == 650
        mock_query.assert_called_once_with('bus', 'B001')
    
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    def test_latest_query_success_for_stop(self, mock_query):
        """Test successful latest query for a stop."""
        mock_query.return_value = {
            'entity_id': 'S001',
            'entity_type': 'stop',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 20.0,
            'humidity': 50.0
        }
        
        event = {
            'pathParameters': {'entity_type': 'stop', 'entity_id': 'S001'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['entity_id'] == 'S001'
        assert body['entity_type'] == 'stop'
        assert body['temperature'] == 20.0
        assert 'co2_level' not in body or body['co2_level'] is None
        mock_query.assert_called_once_with('stop', 'S001')
    
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    def test_latest_query_with_latest_param(self, mock_query):
        """Test latest query with 'latest' parameter instead of mode."""
        mock_query.return_value = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 45.2,
            'co2_level': 650,
            'door_status': 'closed'
        }
        
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {'latest': ''}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        mock_query.assert_called_once_with('bus', 'B001')
    
    @patch('lambdas.sensors_api.query_sensor_data_at_time')
    def test_historical_query_success(self, mock_query):
        """Test successful historical query."""
        mock_query.return_value = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 45.2,
            'co2_level': 650,
            'door_status': 'open'
        }
        
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {'timestamp': '2024-01-15T10:30:00Z'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['entity_id'] == 'B001'
        assert body['temperature'] == 22.5
        mock_query.assert_called_once()
    
    def test_invalid_timestamp_format(self):
        """Test error response for invalid timestamp format."""
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {'timestamp': 'invalid-timestamp'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'timestamp' in body['message'].lower()
    
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    def test_no_data_found(self, mock_query):
        """Test 404 response when no data is found."""
        mock_query.return_value = None
        
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B999'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'B999' in body['message']


class TestQueryFunctions:
    """Test the query functions."""
    
    @patch('lambdas.sensors_api.get_timestream_client')
    def test_query_latest_sensor_data_for_bus(self, mock_get_client):
        """Test querying latest sensor data for a bus."""
        mock_client = Mock()
        mock_client.query_latest.return_value = {
            'rows': [{
                'entity_id': 'B001',
                'entity_type': 'bus',
                'time': '2024-01-15T10:30:00Z',
                'temperature': '22.5',
                'humidity': '45.2',
                'co2_level': '650',
                'door_status': 'closed'
            }]
        }
        mock_get_client.return_value = mock_client
        
        result = query_latest_sensor_data('bus', 'B001')
        
        assert result is not None
        assert result['entity_id'] == 'B001'
        assert result['entity_type'] == 'bus'
        assert result['temperature'] == 22.5
        assert result['humidity'] == 45.2
        assert result['co2_level'] == 650
        assert result['door_status'] == 'closed'
        mock_client.query_latest.assert_called_once_with(
            table_name='sensor_data',
            dimensions={'entity_id': 'B001', 'entity_type': 'bus'},
            limit=1
        )
    
    @patch('lambdas.sensors_api.get_timestream_client')
    def test_query_latest_sensor_data_for_stop(self, mock_get_client):
        """Test querying latest sensor data for a stop."""
        mock_client = Mock()
        mock_client.query_latest.return_value = {
            'rows': [{
                'entity_id': 'S001',
                'entity_type': 'stop',
                'time': '2024-01-15T10:30:00Z',
                'temperature': '20.0',
                'humidity': '50.0'
            }]
        }
        mock_get_client.return_value = mock_client
        
        result = query_latest_sensor_data('stop', 'S001')
        
        assert result is not None
        assert result['entity_id'] == 'S001'
        assert result['entity_type'] == 'stop'
        assert result['temperature'] == 20.0
        assert result['humidity'] == 50.0
        assert result['co2_level'] is None
        assert result['door_status'] is None
        mock_client.query_latest.assert_called_once_with(
            table_name='sensor_data',
            dimensions={'entity_id': 'S001', 'entity_type': 'stop'},
            limit=1
        )
    
    @patch('lambdas.sensors_api.get_timestream_client')
    def test_query_latest_no_data(self, mock_get_client):
        """Test querying latest when no data exists."""
        mock_client = Mock()
        mock_client.query_latest.return_value = None
        mock_get_client.return_value = mock_client
        
        result = query_latest_sensor_data('bus', 'B999')
        
        assert result is None
    
    @patch('lambdas.sensors_api.get_timestream_client')
    def test_query_sensor_data_at_time_for_bus(self, mock_get_client):
        """Test querying sensor data at specific time for a bus."""
        mock_client = Mock()
        mock_client.query_at_time.return_value = {
            'rows': [{
                'entity_id': 'B001',
                'entity_type': 'bus',
                'time': '2024-01-15T10:30:00Z',
                'temperature': '22.5',
                'humidity': '45.2',
                'co2_level': '650',
                'door_status': 'open'
            }]
        }
        mock_get_client.return_value = mock_client
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = query_sensor_data_at_time('bus', 'B001', timestamp)
        
        assert result is not None
        assert result['entity_id'] == 'B001'
        assert result['entity_type'] == 'bus'
        assert result['temperature'] == 22.5
        assert result['co2_level'] == 650
        assert result['door_status'] == 'open'
        mock_client.query_at_time.assert_called_once_with(
            table_name='sensor_data',
            dimensions={'entity_id': 'B001', 'entity_type': 'bus'},
            timestamp=timestamp,
            limit=1
        )
    
    @patch('lambdas.sensors_api.get_timestream_client')
    def test_query_sensor_data_at_time_for_stop(self, mock_get_client):
        """Test querying sensor data at specific time for a stop."""
        mock_client = Mock()
        mock_client.query_at_time.return_value = {
            'rows': [{
                'entity_id': 'S001',
                'entity_type': 'stop',
                'time': '2024-01-15T10:30:00Z',
                'temperature': '20.0',
                'humidity': '50.0'
            }]
        }
        mock_get_client.return_value = mock_client
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = query_sensor_data_at_time('stop', 'S001', timestamp)
        
        assert result is not None
        assert result['entity_id'] == 'S001'
        assert result['entity_type'] == 'stop'
        assert result['temperature'] == 20.0
        assert result['humidity'] == 50.0
        mock_client.query_at_time.assert_called_once_with(
            table_name='sensor_data',
            dimensions={'entity_id': 'S001', 'entity_type': 'stop'},
            timestamp=timestamp,
            limit=1
        )


class TestFormatResponse:
    """Test response formatting functions."""
    
    def test_format_sensor_response_for_bus(self):
        """Test formatting response for bus sensor data."""
        row = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'time': '2024-01-15T10:30:00Z',
            'temperature': '22.5',
            'humidity': '45.2',
            'co2_level': '650',
            'door_status': 'closed'
        }
        
        result = format_sensor_response(row)
        
        assert result['entity_id'] == 'B001'
        assert result['entity_type'] == 'bus'
        assert result['timestamp'] == '2024-01-15T10:30:00Z'
        assert result['temperature'] == 22.5
        assert result['humidity'] == 45.2
        assert result['co2_level'] == 650
        assert result['door_status'] == 'closed'
    
    def test_format_sensor_response_for_stop(self):
        """Test formatting response for stop sensor data."""
        row = {
            'entity_id': 'S001',
            'entity_type': 'stop',
            'time': '2024-01-15T10:30:00Z',
            'temperature': '20.0',
            'humidity': '50.0'
        }
        
        result = format_sensor_response(row)
        
        assert result['entity_id'] == 'S001'
        assert result['entity_type'] == 'stop'
        assert result['timestamp'] == '2024-01-15T10:30:00Z'
        assert result['temperature'] == 20.0
        assert result['humidity'] == 50.0
        assert result['co2_level'] is None
        assert result['door_status'] is None
    
    def test_format_sensor_response_with_missing_fields(self):
        """Test formatting response with missing optional fields."""
        row = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'time': '2024-01-15T10:30:00Z',
            'temperature': '22.5',
            'humidity': '45.2'
        }
        
        result = format_sensor_response(row)
        
        assert result['entity_id'] == 'B001'
        assert result['temperature'] == 22.5
        assert result['co2_level'] is None
        assert result['door_status'] is None
    
    def test_format_sensor_response_with_zero_values(self):
        """Test formatting response with zero values."""
        row = {
            'entity_id': 'S001',
            'entity_type': 'stop',
            'time': '2024-01-15T10:30:00Z',
            'temperature': '0.0',
            'humidity': '0.0'
        }
        
        result = format_sensor_response(row)
        
        assert result['temperature'] == 0.0
        assert result['humidity'] == 0.0


class TestParseISO8601:
    """Test ISO8601 timestamp parsing."""
    
    def test_parse_iso8601_with_z(self):
        """Test parsing ISO8601 with Z timezone."""
        timestamp = parse_iso8601('2024-01-15T10:30:00Z')
        
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 15
        assert timestamp.hour == 10
        assert timestamp.minute == 30
        assert timestamp.second == 0
    
    def test_parse_iso8601_with_offset(self):
        """Test parsing ISO8601 with timezone offset."""
        timestamp = parse_iso8601('2024-01-15T10:30:00+00:00')
        
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 15
    
    def test_parse_iso8601_with_milliseconds(self):
        """Test parsing ISO8601 with milliseconds."""
        timestamp = parse_iso8601('2024-01-15T10:30:00.123Z')
        
        assert timestamp.year == 2024
        assert timestamp.microsecond == 123000
    
    def test_parse_iso8601_invalid_format(self):
        """Test parsing invalid ISO8601 format."""
        with pytest.raises(ValueError) as exc_info:
            parse_iso8601('invalid-timestamp')
        
        assert 'Invalid ISO8601' in str(exc_info.value)


class TestResponseHelpers:
    """Test response helper functions."""
    
    def test_success_response(self):
        """Test success response generation."""
        data = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'temperature': 22.5
        }
        
        response = success_response(data)
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body['entity_id'] == 'B001'
        assert body['temperature'] == 22.5
    
    def test_error_response(self):
        """Test error response generation."""
        response = error_response(404, 'Not found')
        
        assert response['statusCode'] == 404
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body['error'] is True
        assert body['message'] == 'Not found'
        assert 'timestamp' in body


class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    def test_bus_with_extreme_temperature(self, mock_query):
        """Test handling of extreme temperature values."""
        mock_query.return_value = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 45.0,  # Extreme heat
            'humidity': 10.0,
            'co2_level': 1500,
            'door_status': 'open'
        }
        
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['temperature'] == 45.0
    
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    def test_bus_with_high_co2_level(self, mock_query):
        """Test handling of high CO2 levels."""
        mock_query.return_value = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 25.0,
            'humidity': 60.0,
            'co2_level': 2000,  # High CO2
            'door_status': 'closed'
        }
        
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['co2_level'] == 2000
    
    def test_empty_path_parameters(self):
        """Test handling of empty path parameters."""
        event = {
            'pathParameters': {},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
    
    def test_none_path_parameters(self):
        """Test handling of None path parameters."""
        event = {
            'pathParameters': None,
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
    
    def test_none_query_parameters(self):
        """Test handling of None query parameters."""
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': 'B001'},
            'queryStringParameters': None
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
