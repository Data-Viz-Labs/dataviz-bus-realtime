"""
Unit tests for the Bus Position API Lambda function.

Tests the Lambda handler, query functions, and error handling.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

# Import the Lambda handler module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.bus_position_api import (
    lambda_handler,
    query_latest_bus_position,
    query_bus_position_at_time,
    query_line_buses,
    format_bus_position_response,
    parse_iso8601,
    success_response,
    error_response
)


class TestLambdaHandler:
    """Test the main Lambda handler function."""
    
    def test_missing_bus_id(self):
        """Test error response when bus_id is missing."""
        event = {
            'pathParameters': {},
            'path': '/bus-position/',
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'bus_id' in body['message']
    
    def test_missing_query_parameters(self):
        """Test error response when query parameters are missing."""
        event = {
            'pathParameters': {'bus_id': 'B001'},
            'path': '/bus-position/B001',
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'mode' in body['message'] or 'timestamp' in body['message']
    
    @patch('lambdas.bus_position_api.query_latest_bus_position')
    def test_latest_query_success(self, mock_query):
        """Test successful latest query for single bus."""
        mock_query.return_value = {
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
        
        event = {
            'pathParameters': {'bus_id': 'B001'},
            'path': '/bus-position/B001',
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['bus_id'] == 'B001'
        assert body['line_id'] == 'L1'
        assert body['passenger_count'] == 25
        mock_query.assert_called_once_with('B001')
    
    @patch('lambdas.bus_position_api.query_bus_position_at_time')
    def test_historical_query_success(self, mock_query):
        """Test successful historical query."""
        mock_query.return_value = {
            'bus_id': 'B001',
            'line_id': 'L1',
            'timestamp': '2024-01-15T10:30:00Z',
            'latitude': 40.4165,
            'longitude': -3.7026,
            'passenger_count': 20,
            'next_stop_id': 'S002',
            'distance_to_next_stop': 200.0,
            'speed': 30.0
        }
        
        event = {
            'pathParameters': {'bus_id': 'B001'},
            'path': '/bus-position/B001',
            'queryStringParameters': {'timestamp': '2024-01-15T10:30:00Z'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['bus_id'] == 'B001'
        assert body['passenger_count'] == 20
        mock_query.assert_called_once()
    
    @patch('lambdas.bus_position_api.query_line_buses')
    def test_line_query_success(self, mock_query):
        """Test successful query for all buses on a line."""
        mock_query.return_value = [
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
                'timestamp': '2024-01-15T10:30:00Z',
                'latitude': 40.4200,
                'longitude': -3.7050,
                'passenger_count': 30,
                'next_stop_id': 'S005',
                'distance_to_next_stop': 300.0,
                'speed': 40.0
            }
        ]
        
        event = {
            'pathParameters': {'line_id': 'L1'},
            'path': '/bus-position/line/L1',
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'buses' in body
        assert len(body['buses']) == 2
        assert body['buses'][0]['bus_id'] == 'B001'
        assert body['buses'][1]['bus_id'] == 'B002'
        mock_query.assert_called_once_with('L1')
    
    def test_line_query_without_latest_mode(self):
        """Test error when line query doesn't use latest mode."""
        event = {
            'pathParameters': {'line_id': 'L1'},
            'path': '/bus-position/line/L1',
            'queryStringParameters': {'timestamp': '2024-01-15T10:30:00Z'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'latest' in body['message'].lower()
    
    @patch('lambdas.bus_position_api.query_latest_bus_position')
    def test_no_data_found(self, mock_query):
        """Test 404 response when no data is found."""
        mock_query.return_value = None
        
        event = {
            'pathParameters': {'bus_id': 'B999'},
            'path': '/bus-position/B999',
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'B999' in body['message']


class TestQueryFunctions:
    """Test the query functions."""
    
    @patch('lambdas.bus_position_api.get_timestream_client')
    def test_query_latest_bus_position(self, mock_get_client):
        """Test querying latest bus position."""
        mock_client = Mock()
        mock_client.query_latest.return_value = {
            'rows': [{
                'bus_id': 'B001',
                'line_id': 'L1',
                'time': '2024-01-15T10:30:00Z',
                'latitude': '40.4165',
                'longitude': '-3.7026',
                'passenger_count': '25',
                'next_stop_id': 'S003',
                'distance_to_next_stop': '450.5',
                'speed': '35.2'
            }]
        }
        mock_get_client.return_value = mock_client
        
        result = query_latest_bus_position('B001')
        
        assert result is not None
        assert result['bus_id'] == 'B001'
        assert result['line_id'] == 'L1'
        assert result['latitude'] == 40.4165
        assert result['longitude'] == -3.7026
        assert result['passenger_count'] == 25
        assert result['next_stop_id'] == 'S003'
        assert result['distance_to_next_stop'] == 450.5
        assert result['speed'] == 35.2
        mock_client.query_latest.assert_called_once_with(
            table_name='bus_position',
            dimensions={'bus_id': 'B001'},
            limit=1
        )
    
    @patch('lambdas.bus_position_api.get_timestream_client')
    def test_query_latest_no_data(self, mock_get_client):
        """Test querying latest when no data exists."""
        mock_client = Mock()
        mock_client.query_latest.return_value = None
        mock_get_client.return_value = mock_client
        
        result = query_latest_bus_position('B999')
        
        assert result is None
    
    @patch('lambdas.bus_position_api.get_timestream_client')
    def test_query_bus_position_at_time(self, mock_get_client):
        """Test querying bus position at specific time."""
        mock_client = Mock()
        mock_client.query_at_time.return_value = {
            'rows': [{
                'bus_id': 'B001',
                'line_id': 'L1',
                'time': '2024-01-15T10:30:00Z',
                'latitude': '40.4165',
                'longitude': '-3.7026',
                'passenger_count': '20',
                'next_stop_id': 'S002',
                'distance_to_next_stop': '200.0',
                'speed': '30.0'
            }]
        }
        mock_get_client.return_value = mock_client
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = query_bus_position_at_time('B001', timestamp)
        
        assert result is not None
        assert result['bus_id'] == 'B001'
        assert result['passenger_count'] == 20
        mock_client.query_at_time.assert_called_once_with(
            table_name='bus_position',
            dimensions={'bus_id': 'B001'},
            timestamp=timestamp,
            limit=1
        )
    
    @patch('lambdas.bus_position_api.get_timestream_client')
    def test_query_line_buses(self, mock_get_client):
        """Test querying all buses on a line."""
        mock_client = Mock()
        mock_client._execute_query.return_value = {
            'rows': [
                {
                    'bus_id': 'B001',
                    'line_id': 'L1',
                    'time': '2024-01-15T10:30:00Z',
                    'latitude': '40.4165',
                    'longitude': '-3.7026',
                    'passenger_count': '25',
                    'next_stop_id': 'S003',
                    'distance_to_next_stop': '450.5',
                    'speed': '35.2'
                },
                {
                    'bus_id': 'B002',
                    'line_id': 'L1',
                    'time': '2024-01-15T10:30:00Z',
                    'latitude': '40.4200',
                    'longitude': '-3.7050',
                    'passenger_count': '30',
                    'next_stop_id': 'S005',
                    'distance_to_next_stop': '300.0',
                    'speed': '40.0'
                },
                # Older data for B001 (should be filtered out)
                {
                    'bus_id': 'B001',
                    'line_id': 'L1',
                    'time': '2024-01-15T10:29:00Z',
                    'latitude': '40.4160',
                    'longitude': '-3.7020',
                    'passenger_count': '24',
                    'next_stop_id': 'S003',
                    'distance_to_next_stop': '500.0',
                    'speed': '34.0'
                }
            ]
        }
        mock_get_client.return_value = mock_client
        
        result = query_line_buses('L1')
        
        assert result is not None
        assert len(result) == 2
        assert result[0]['bus_id'] == 'B001'
        assert result[0]['passenger_count'] == 25  # Latest data
        assert result[1]['bus_id'] == 'B002'
    
    @patch('lambdas.bus_position_api.get_timestream_client')
    def test_query_line_buses_no_data(self, mock_get_client):
        """Test querying line when no buses exist."""
        mock_client = Mock()
        mock_client._execute_query.return_value = None
        mock_get_client.return_value = mock_client
        
        result = query_line_buses('L999')
        
        assert result is None


class TestFormatResponse:
    """Test response formatting functions."""
    
    def test_format_bus_position_response(self):
        """Test formatting bus position response."""
        row = {
            'bus_id': 'B001',
            'line_id': 'L1',
            'time': '2024-01-15T10:30:00Z',
            'latitude': '40.4165',
            'longitude': '-3.7026',
            'passenger_count': '25',
            'next_stop_id': 'S003',
            'distance_to_next_stop': '450.5',
            'speed': '35.2'
        }
        
        result = format_bus_position_response(row)
        
        assert result['bus_id'] == 'B001'
        assert result['line_id'] == 'L1'
        assert result['timestamp'] == '2024-01-15T10:30:00Z'
        assert result['latitude'] == 40.4165
        assert result['longitude'] == -3.7026
        assert result['passenger_count'] == 25
        assert result['next_stop_id'] == 'S003'
        assert result['distance_to_next_stop'] == 450.5
        assert result['speed'] == 35.2
    
    def test_format_bus_position_response_with_none_values(self):
        """Test formatting response with None values."""
        row = {
            'bus_id': 'B001',
            'line_id': 'L1',
            'time': '2024-01-15T10:30:00Z',
            'passenger_count': '0'
        }
        
        result = format_bus_position_response(row)
        
        assert result['bus_id'] == 'B001'
        assert result['latitude'] is None
        assert result['longitude'] is None
        assert result['passenger_count'] == 0
        assert result['distance_to_next_stop'] is None
        assert result['speed'] is None


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
    
    def test_parse_iso8601_invalid_format(self):
        """Test parsing invalid ISO8601 format."""
        with pytest.raises(ValueError) as exc_info:
            parse_iso8601('invalid-timestamp')
        
        assert 'Invalid ISO8601' in str(exc_info.value)


class TestResponseHelpers:
    """Test response helper functions."""
    
    def test_success_response(self):
        """Test success response generation."""
        data = {'bus_id': 'B001', 'passenger_count': 25}
        
        response = success_response(data)
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body['bus_id'] == 'B001'
        assert body['passenger_count'] == 25
    
    def test_error_response(self):
        """Test error response generation."""
        response = error_response(404, 'Bus not found')
        
        assert response['statusCode'] == 404
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body['error'] is True
        assert body['message'] == 'Bus not found'
        assert 'timestamp' in body
