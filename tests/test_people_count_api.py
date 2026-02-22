"""
Unit tests for the People Count API Lambda function.

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

from lambdas.people_count_api import (
    lambda_handler,
    query_latest_people_count,
    query_people_count_at_time,
    format_people_count_response,
    parse_iso8601,
    success_response,
    error_response
)


class TestLambdaHandler:
    """Test the main Lambda handler function."""
    
    def test_missing_stop_id(self):
        """Test error response when stop_id is missing."""
        event = {
            'pathParameters': {},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'stop_id' in body['message']
    
    def test_missing_query_parameters(self):
        """Test error response when query parameters are missing."""
        event = {
            'pathParameters': {'stop_id': 'S001'},
            'queryStringParameters': {}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'mode' in body['message'] or 'timestamp' in body['message']
    
    @patch('lambdas.people_count_api.query_latest_people_count')
    def test_latest_query_success(self, mock_query):
        """Test successful latest query."""
        mock_query.return_value = {
            'stop_id': 'S001',
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 15,
            'line_ids': ['L1', 'L2']
        }
        
        event = {
            'pathParameters': {'stop_id': 'S001'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['stop_id'] == 'S001'
        assert body['count'] == 15
        mock_query.assert_called_once_with('S001')
    
    @patch('lambdas.people_count_api.query_latest_people_count')
    def test_latest_query_with_latest_param(self, mock_query):
        """Test latest query with 'latest' parameter instead of mode."""
        mock_query.return_value = {
            'stop_id': 'S001',
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 15,
            'line_ids': ['L1']
        }
        
        event = {
            'pathParameters': {'stop_id': 'S001'},
            'queryStringParameters': {'latest': ''}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        mock_query.assert_called_once_with('S001')
    
    @patch('lambdas.people_count_api.query_people_count_at_time')
    def test_historical_query_success(self, mock_query):
        """Test successful historical query."""
        mock_query.return_value = {
            'stop_id': 'S001',
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 12,
            'line_ids': ['L1']
        }
        
        event = {
            'pathParameters': {'stop_id': 'S001'},
            'queryStringParameters': {'timestamp': '2024-01-15T10:30:00Z'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['stop_id'] == 'S001'
        assert body['count'] == 12
        mock_query.assert_called_once()
    
    def test_invalid_timestamp_format(self):
        """Test error response for invalid timestamp format."""
        event = {
            'pathParameters': {'stop_id': 'S001'},
            'queryStringParameters': {'timestamp': 'invalid-timestamp'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'timestamp' in body['message'].lower()
    
    @patch('lambdas.people_count_api.query_latest_people_count')
    def test_no_data_found(self, mock_query):
        """Test 404 response when no data is found."""
        mock_query.return_value = None
        
        event = {
            'pathParameters': {'stop_id': 'S999'},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 404
        body = json.loads(response['body'])
        assert body['error'] is True
        assert 'S999' in body['message']


class TestQueryFunctions:
    """Test the query functions."""
    
    @patch('lambdas.people_count_api.get_timestream_client')
    def test_query_latest_people_count(self, mock_get_client):
        """Test querying latest people count."""
        mock_client = Mock()
        mock_client.query_latest.return_value = {
            'rows': [{
                'stop_id': 'S001',
                'time': '2024-01-15T10:30:00Z',
                'count': '15',
                'line_ids': 'L1,L2'
            }]
        }
        mock_get_client.return_value = mock_client
        
        result = query_latest_people_count('S001')
        
        assert result is not None
        assert result['stop_id'] == 'S001'
        assert result['count'] == 15
        assert result['line_ids'] == ['L1', 'L2']
        mock_client.query_latest.assert_called_once_with(
            table_name='people_count',
            dimensions={'stop_id': 'S001'},
            limit=1
        )
    
    @patch('lambdas.people_count_api.get_timestream_client')
    def test_query_latest_no_data(self, mock_get_client):
        """Test querying latest when no data exists."""
        mock_client = Mock()
        mock_client.query_latest.return_value = None
        mock_get_client.return_value = mock_client
        
        result = query_latest_people_count('S999')
        
        assert result is None
    
    @patch('lambdas.people_count_api.get_timestream_client')
    def test_query_people_count_at_time(self, mock_get_client):
        """Test querying people count at specific time."""
        mock_client = Mock()
        mock_client.query_at_time.return_value = {
            'rows': [{
                'stop_id': 'S001',
                'time': '2024-01-15T10:30:00Z',
                'count': '12',
                'line_ids': 'L1'
            }]
        }
        mock_get_client.return_value = mock_client
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = query_people_count_at_time('S001', timestamp)
        
        assert result is not None
        assert result['stop_id'] == 'S001'
        assert result['count'] == 12
        assert result['line_ids'] == ['L1']
        mock_client.query_at_time.assert_called_once_with(
            table_name='people_count',
            dimensions={'stop_id': 'S001'},
            timestamp=timestamp,
            limit=1
        )


class TestFormatResponse:
    """Test response formatting functions."""
    
    def test_format_people_count_response_with_comma_separated_lines(self):
        """Test formatting response with comma-separated line IDs."""
        row = {
            'stop_id': 'S001',
            'time': '2024-01-15T10:30:00Z',
            'count': '15',
            'line_ids': 'L1,L2,L3'
        }
        
        result = format_people_count_response(row)
        
        assert result['stop_id'] == 'S001'
        assert result['timestamp'] == '2024-01-15T10:30:00Z'
        assert result['count'] == 15
        assert result['line_ids'] == ['L1', 'L2', 'L3']
    
    def test_format_people_count_response_with_array_lines(self):
        """Test formatting response with array line IDs."""
        row = {
            'stop_id': 'S001',
            'time': '2024-01-15T10:30:00Z',
            'count': '15',
            'line_ids': ['L1', 'L2']
        }
        
        result = format_people_count_response(row)
        
        assert result['line_ids'] == ['L1', 'L2']
    
    def test_format_people_count_response_no_lines(self):
        """Test formatting response with no line IDs."""
        row = {
            'stop_id': 'S001',
            'time': '2024-01-15T10:30:00Z',
            'count': '15'
        }
        
        result = format_people_count_response(row)
        
        assert result['line_ids'] == []
    
    def test_format_people_count_response_zero_count(self):
        """Test formatting response with zero count."""
        row = {
            'stop_id': 'S001',
            'time': '2024-01-15T10:30:00Z',
            'count': '0',
            'line_ids': 'L1'
        }
        
        result = format_people_count_response(row)
        
        assert result['count'] == 0


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
        data = {'stop_id': 'S001', 'count': 15}
        
        response = success_response(data)
        
        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'application/json'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
        
        body = json.loads(response['body'])
        assert body['stop_id'] == 'S001'
        assert body['count'] == 15
    
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
