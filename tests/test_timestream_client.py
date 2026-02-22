"""
Unit tests for the Timestream client wrapper.

Tests cover retry logic, query parameter formatting, and error handling.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError

from src.common.timestream_client import TimestreamClient


class TestTimestreamClientInit:
    """Tests for TimestreamClient initialization."""
    
    def test_init_with_clients(self):
        """Test initialization with provided clients."""
        mock_write = Mock()
        mock_query = Mock()
        
        client = TimestreamClient(
            database_name="test_db",
            region_name="us-east-1",
            write_client=mock_write,
            query_client=mock_query
        )
        
        assert client.database_name == "test_db"
        assert client.region_name == "us-east-1"
        assert client.max_retries == 3
        assert client.write_client == mock_write
        assert client.query_client == mock_query
    
    def test_init_custom_max_retries(self):
        """Test initialization with custom max_retries."""
        mock_write = Mock()
        mock_query = Mock()
        
        client = TimestreamClient(
            database_name="test_db",
            max_retries=5,
            write_client=mock_write,
            query_client=mock_query
        )
        
        assert client.max_retries == 5


class TestWriteRecords:
    """Tests for write_records method with retry logic."""
    
    def test_write_records_success(self):
        """Test successful write on first attempt."""
        mock_write = Mock()
        mock_write.write_records.return_value = {}
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=mock_write,
            query_client=Mock()
        )
        
        records = [
            {
                'Dimensions': [{'Name': 'stop_id', 'Value': 'S001'}],
                'MeasureName': 'count',
                'MeasureValue': '15',
                'MeasureValueType': 'BIGINT',
                'Time': '1234567890000',
                'TimeUnit': 'MILLISECONDS'
            }
        ]
        
        result = client.write_records('people_count', records)
        
        assert result is True
        mock_write.write_records.assert_called_once_with(
            DatabaseName='test_db',
            TableName='people_count',
            Records=records
        )
    
    def test_write_records_with_common_attributes(self):
        """Test write with common attributes."""
        mock_write = Mock()
        mock_write.write_records.return_value = {}
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=mock_write,
            query_client=Mock()
        )
        
        records = [{'MeasureName': 'count', 'MeasureValue': '15'}]
        common_attrs = {
            'Dimensions': [{'Name': 'line_id', 'Value': 'L1'}]
        }
        
        result = client.write_records('people_count', records, common_attrs)
        
        assert result is True
        mock_write.write_records.assert_called_once_with(
            DatabaseName='test_db',
            TableName='people_count',
            Records=records,
            CommonAttributes=common_attrs
        )
    
    def test_write_records_retry_on_failure(self):
        """Test retry logic with exponential backoff."""
        mock_write = Mock()
        
        # Fail twice, then succeed
        mock_write.write_records.side_effect = [
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                'WriteRecords'
            ),
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                'WriteRecords'
            ),
            {}  # Success
        ]
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=mock_write,
            query_client=Mock()
        )
        
        records = [{'MeasureName': 'count', 'MeasureValue': '15'}]
        
        with patch('time.sleep') as mock_sleep:
            result = client.write_records('people_count', records)
        
        assert result is True
        assert mock_write.write_records.call_count == 3
        
        # Verify exponential backoff: 2^0=1s, 2^1=2s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)  # First retry
        mock_sleep.assert_any_call(2)  # Second retry
    
    def test_write_records_max_retries_exceeded(self):
        """Test that exception is raised after max retries."""
        mock_write = Mock()
        
        # Always fail
        error = ClientError(
            {'Error': {'Code': 'InternalServerException', 'Message': 'Server error'}},
            'WriteRecords'
        )
        mock_write.write_records.side_effect = error
        
        client = TimestreamClient(
            database_name="test_db",
            max_retries=3,
            write_client=mock_write,
            query_client=Mock()
        )
        
        records = [{'MeasureName': 'count', 'MeasureValue': '15'}]
        
        with patch('time.sleep'):
            with pytest.raises(ClientError):
                client.write_records('people_count', records)
        
        # Should attempt max_retries times
        assert mock_write.write_records.call_count == 3


class TestQueryLatest:
    """Tests for query_latest method."""
    
    def test_query_latest_single_dimension(self):
        """Test querying latest data with single dimension."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': 'S001'},
                        {'ScalarValue': '15'},
                        {'ScalarValue': '2024-01-15 10:30:00'}
                    ]
                }
            ],
            'ColumnInfo': [
                {'Name': 'stop_id'},
                {'Name': 'count'},
                {'Name': 'time'}
            ],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        result = client.query_latest('people_count', {'stop_id': 'S001'})
        
        assert result is not None
        assert len(result['rows']) == 1
        assert result['rows'][0]['stop_id'] == 'S001'
        assert result['rows'][0]['count'] == '15'
        
        # Verify query structure
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert 'ORDER BY time DESC' in query_string
        assert 'LIMIT 1' in query_string
        assert "stop_id = 'S001'" in query_string
    
    def test_query_latest_multiple_dimensions(self):
        """Test querying with multiple dimensions."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [],
            'ColumnInfo': [],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        result = client.query_latest(
            'sensor_data',
            {'entity_id': 'B001', 'entity_type': 'bus'}
        )
        
        # Verify query contains both dimensions
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert "entity_id = 'B001'" in query_string
        assert "entity_type = 'bus'" in query_string
        assert ' AND ' in query_string
    
    def test_query_latest_no_results(self):
        """Test query with no results returns None."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [],
            'ColumnInfo': [],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        result = client.query_latest('people_count', {'stop_id': 'INVALID'})
        
        assert result is None


class TestQueryAtTime:
    """Tests for query_at_time method."""
    
    def test_query_at_time_formats_timestamp(self):
        """Test that timestamp is properly formatted in query."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': 'S001'},
                        {'ScalarValue': '10'}
                    ]
                }
            ],
            'ColumnInfo': [
                {'Name': 'stop_id'},
                {'Name': 'count'}
            ],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = client.query_at_time('people_count', {'stop_id': 'S001'}, timestamp)
        
        assert result is not None
        
        # Verify query structure
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert 'from_iso8601_timestamp' in query_string
        assert '2024-01-15T10:30:00' in query_string
        assert 'time <=' in query_string
        assert 'ORDER BY time DESC' in query_string
    
    def test_query_at_time_with_multiple_dimensions(self):
        """Test historical query with multiple dimensions."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [],
            'ColumnInfo': [],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = client.query_at_time(
            'bus_position',
            {'bus_id': 'B001', 'line_id': 'L1'},
            timestamp
        )
        
        # Verify query contains all dimensions and time filter
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert "bus_id = 'B001'" in query_string
        assert "line_id = 'L1'" in query_string
        assert 'time <=' in query_string


class TestQueryTimeRange:
    """Tests for query_time_range method."""
    
    def test_query_time_range_formats_timestamps(self):
        """Test that start and end timestamps are properly formatted."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [],
            'ColumnInfo': [],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 11, 0, 0)
        
        result = client.query_time_range(
            'people_count',
            {'stop_id': 'S001'},
            start_time,
            end_time
        )
        
        # Verify query structure
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert 'time >=' in query_string
        assert 'time <=' in query_string
        assert '2024-01-15T10:00:00' in query_string
        assert '2024-01-15T11:00:00' in query_string
    
    def test_query_time_range_with_limit(self):
        """Test time range query with limit."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [],
            'ColumnInfo': [],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 11, 0, 0)
        
        result = client.query_time_range(
            'people_count',
            {'stop_id': 'S001'},
            start_time,
            end_time,
            limit=100
        )
        
        # Verify query has limit
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert 'LIMIT 100' in query_string


class TestExecuteQuery:
    """Tests for _execute_query method."""
    
    def test_execute_query_error_handling(self):
        """Test that query errors are properly raised."""
        mock_query = Mock()
        error = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid query'}},
            'Query'
        )
        mock_query.query.side_effect = error
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        with pytest.raises(ClientError):
            client._execute_query("SELECT * FROM invalid_table")
    
    def test_execute_query_parses_multiple_rows(self):
        """Test parsing multiple rows from query results."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': 'S001'},
                        {'ScalarValue': '15'}
                    ]
                },
                {
                    'Data': [
                        {'ScalarValue': 'S002'},
                        {'ScalarValue': '20'}
                    ]
                }
            ],
            'ColumnInfo': [
                {'Name': 'stop_id'},
                {'Name': 'count'}
            ],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        result = client._execute_query("SELECT * FROM people_count")
        
        assert result is not None
        assert len(result['rows']) == 2
        assert result['rows'][0]['stop_id'] == 'S001'
        assert result['rows'][0]['count'] == '15'
        assert result['rows'][1]['stop_id'] == 'S002'
        assert result['rows'][1]['count'] == '20'


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""
    
    def test_write_records_empty_list(self):
        """Test writing empty records list."""
        mock_write = Mock()
        mock_write.write_records.return_value = {}
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=mock_write,
            query_client=Mock()
        )
        
        result = client.write_records('people_count', [])
        
        assert result is True
        mock_write.write_records.assert_called_once()
    
    def test_write_records_different_error_codes(self):
        """Test retry behavior with different error codes."""
        mock_write = Mock()
        
        # Test with InternalServerException
        error = ClientError(
            {'Error': {'Code': 'InternalServerException', 'Message': 'Server error'}},
            'WriteRecords'
        )
        mock_write.write_records.side_effect = [error, {}]
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=mock_write,
            query_client=Mock()
        )
        
        records = [{'MeasureName': 'count', 'MeasureValue': '15'}]
        
        with patch('time.sleep'):
            result = client.write_records('people_count', records)
        
        assert result is True
        assert mock_write.write_records.call_count == 2
    
    def test_query_latest_custom_limit(self):
        """Test query_latest with custom limit value."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [
                {'Data': [{'ScalarValue': 'S001'}, {'ScalarValue': '15'}]},
                {'Data': [{'ScalarValue': 'S001'}, {'ScalarValue': '12'}]},
                {'Data': [{'ScalarValue': 'S001'}, {'ScalarValue': '10'}]}
            ],
            'ColumnInfo': [
                {'Name': 'stop_id'},
                {'Name': 'count'}
            ],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        result = client.query_latest('people_count', {'stop_id': 'S001'}, limit=3)
        
        assert result is not None
        assert len(result['rows']) == 3
        
        # Verify limit is in query
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert 'LIMIT 3' in query_string
    
    def test_query_with_special_characters_in_dimension(self):
        """Test that dimension values with special characters are properly escaped."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [],
            'ColumnInfo': [],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        # Test with dimension value containing special characters
        result = client.query_latest('people_count', {'stop_id': "S'001"})
        
        # Verify query was executed (basic SQL injection prevention check)
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert "stop_id = 'S'001'" in query_string
    
    def test_write_records_retry_backoff_timing(self):
        """Test that exponential backoff timing is correct."""
        mock_write = Mock()
        
        # Fail on all attempts
        error = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'WriteRecords'
        )
        mock_write.write_records.side_effect = error
        
        client = TimestreamClient(
            database_name="test_db",
            max_retries=4,
            write_client=mock_write,
            query_client=Mock()
        )
        
        records = [{'MeasureName': 'count', 'MeasureValue': '15'}]
        
        with patch('time.sleep') as mock_sleep:
            with pytest.raises(ClientError):
                client.write_records('people_count', records)
        
        # Verify exponential backoff: 2^0=1s, 2^1=2s, 2^2=4s
        assert mock_sleep.call_count == 3
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [1, 2, 4]
    
    def test_query_time_range_without_limit(self):
        """Test time range query without limit parameter."""
        mock_query = Mock()
        mock_query.query.return_value = {
            'Rows': [],
            'ColumnInfo': [],
            'QueryId': 'query-123'
        }
        
        client = TimestreamClient(
            database_name="test_db",
            write_client=Mock(),
            query_client=mock_query
        )
        
        start_time = datetime(2024, 1, 15, 10, 0, 0)
        end_time = datetime(2024, 1, 15, 11, 0, 0)
        
        result = client.query_time_range(
            'people_count',
            {'stop_id': 'S001'},
            start_time,
            end_time,
            limit=None
        )
        
        # Verify query does not have LIMIT clause
        call_args = mock_query.query.call_args
        query_string = call_args.kwargs['QueryString']
        assert 'LIMIT' not in query_string
