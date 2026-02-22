"""
Unit tests for EventBridge client.

Tests cover event publishing, retry logic, error handling, and event structure validation.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
from botocore.exceptions import ClientError

from src.common.eventbridge_client import EventBridgeClient


class TestEventBridgeClientInitialization:
    """Test EventBridge client initialization."""
    
    def test_init_with_default_parameters(self):
        """Test initialization with default parameters."""
        mock_client = Mock()
        client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        assert client.event_bus_name == 'test-bus'
        assert client.region_name == 'eu-west-1'
        assert client.max_retries == 3
        assert client.client == mock_client
    
    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        mock_client = Mock()
        client = EventBridgeClient(
            event_bus_name='custom-bus',
            region_name='us-east-1',
            max_retries=5,
            client=mock_client
        )
        
        assert client.event_bus_name == 'custom-bus'
        assert client.region_name == 'us-east-1'
        assert client.max_retries == 5
    
    def test_init_without_boto3_raises_error(self):
        """Test that initialization without boto3 raises ImportError."""
        with patch('src.common.eventbridge_client.boto3', None):
            with pytest.raises(ImportError, match="boto3 is required"):
                EventBridgeClient(event_bus_name='test-bus')


class TestPublishBusPositionEvent:
    """Test publishing bus position update events."""
    
    def test_publish_bus_position_event_success(self):
        """Test successful bus position event publication."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = client.publish_bus_position_event(
            bus_id='B001',
            line_id='L1',
            timestamp=timestamp,
            latitude=40.4657,
            longitude=-3.6886,
            passenger_count=25,
            next_stop_id='S002',
            distance_to_next_stop=500.0,
            speed=30.0
        )
        
        assert result is True
        
        # Verify put_events was called with correct parameters
        mock_client.put_events.assert_called_once()
        call_args = mock_client.put_events.call_args[1]
        entries = call_args['Entries']
        
        assert len(entries) == 1
        entry = entries[0]
        
        assert entry['Source'] == 'bus-simulator'
        assert entry['DetailType'] == 'bus.position.updated'
        assert entry['EventBusName'] == 'test-bus'
        
        # Verify detail structure
        detail = json.loads(entry['Detail'])
        assert detail['bus_id'] == 'B001'
        assert detail['line_id'] == 'L1'
        assert detail['timestamp'] == '2024-01-15T10:30:00'
        assert detail['latitude'] == 40.4657
        assert detail['longitude'] == -3.6886
        assert detail['passenger_count'] == 25
        assert detail['next_stop_id'] == 'S002'
        assert detail['distance_to_next_stop'] == 500.0
        assert detail['speed'] == 30.0
    
    def test_publish_bus_position_event_with_failed_entry(self):
        """Test handling of failed entry in response."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 1,
            'Entries': [
                {'ErrorMessage': 'Event size exceeded limit'}
            ]
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            max_retries=1,
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = client.publish_bus_position_event(
            bus_id='B001',
            line_id='L1',
            timestamp=timestamp,
            latitude=40.4657,
            longitude=-3.6886,
            passenger_count=25,
            next_stop_id='S002',
            distance_to_next_stop=500.0,
            speed=30.0
        )
        
        # Should return False after retries exhausted
        assert result is False
        # Should have attempted max_retries times
        assert mock_client.put_events.call_count == 1


class TestPublishBusArrivalEvents:
    """Test publishing bus arrival events."""
    
    def test_publish_bus_arrival_events_success(self):
        """Test successful bus arrival event publication."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 35, 0)
        result = client.publish_bus_arrival_events(
            bus_id='B001',
            line_id='L1',
            stop_id='S002',
            timestamp=timestamp,
            passengers_boarding=5,
            passengers_alighting=3,
            bus_passenger_count=27,
            stop_people_count=10
        )
        
        assert result is True
        
        # Verify put_events was called with correct parameters
        mock_client.put_events.assert_called_once()
        call_args = mock_client.put_events.call_args[1]
        entries = call_args['Entries']
        
        assert len(entries) == 1
        entry = entries[0]
        
        assert entry['Source'] == 'bus-simulator'
        assert entry['DetailType'] == 'bus.arrival'
        assert entry['EventBusName'] == 'test-bus'
        
        # Verify detail structure
        detail = json.loads(entry['Detail'])
        assert detail['bus_id'] == 'B001'
        assert detail['line_id'] == 'L1'
        assert detail['stop_id'] == 'S002'
        assert detail['timestamp'] == '2024-01-15T10:35:00'
        assert detail['passengers_boarding'] == 5
        assert detail['passengers_alighting'] == 3
        assert detail['bus_passenger_count'] == 27
        assert detail['stop_people_count'] == 10


class TestRetryLogic:
    """Test retry logic with exponential backoff."""
    
    def test_retry_on_client_error(self):
        """Test retry logic when ClientError is raised."""
        mock_client = Mock()
        
        # First two calls fail, third succeeds
        mock_client.put_events.side_effect = [
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                'PutEvents'
            ),
            ClientError(
                {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
                'PutEvents'
            ),
            {'FailedEntryCount': 0, 'Entries': []}
        ]
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            max_retries=3,
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = client.publish_bus_position_event(
                bus_id='B001',
                line_id='L1',
                timestamp=timestamp,
                latitude=40.4657,
                longitude=-3.6886,
                passenger_count=25,
                next_stop_id='S002',
                distance_to_next_stop=500.0,
                speed=30.0
            )
        
        assert result is True
        assert mock_client.put_events.call_count == 3
    
    def test_retry_exhaustion_returns_false(self):
        """Test that exhausting retries returns False (non-critical failure)."""
        mock_client = Mock()
        
        # All calls fail
        mock_client.put_events.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'PutEvents'
        )
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            max_retries=3,
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = client.publish_bus_position_event(
                bus_id='B001',
                line_id='L1',
                timestamp=timestamp,
                latitude=40.4657,
                longitude=-3.6886,
                passenger_count=25,
                next_stop_id='S002',
                distance_to_next_stop=500.0,
                speed=30.0
            )
        
        # Should return False (log warning and continue)
        assert result is False
        assert mock_client.put_events.call_count == 3
    
    def test_exponential_backoff_timing(self):
        """Test that exponential backoff uses correct wait times."""
        mock_client = Mock()
        mock_client.put_events.side_effect = ClientError(
            {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}},
            'PutEvents'
        )
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            max_retries=3,
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        with patch('time.sleep') as mock_sleep:
            result = client.publish_bus_position_event(
                bus_id='B001',
                line_id='L1',
                timestamp=timestamp,
                latitude=40.4657,
                longitude=-3.6886,
                passenger_count=25,
                next_stop_id='S002',
                distance_to_next_stop=500.0,
                speed=30.0
            )
        
        # Verify exponential backoff: 2^0=1, 2^1=2
        assert mock_sleep.call_count == 2
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert sleep_calls == [1, 2]


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_handles_missing_error_message_in_failed_entry(self):
        """Test handling of failed entry without error message."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 1,
            'Entries': [{}]  # No ErrorMessage field
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            max_retries=1,
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = client.publish_bus_position_event(
            bus_id='B001',
            line_id='L1',
            timestamp=timestamp,
            latitude=40.4657,
            longitude=-3.6886,
            passenger_count=25,
            next_stop_id='S002',
            distance_to_next_stop=500.0,
            speed=30.0
        )
        
        # Should handle gracefully and return False
        assert result is False
    
    def test_handles_empty_failed_entries_list(self):
        """Test handling of failed entry count without entries list."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 1,
            'Entries': []  # Empty list
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            max_retries=1,
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        result = client.publish_bus_position_event(
            bus_id='B001',
            line_id='L1',
            timestamp=timestamp,
            latitude=40.4657,
            longitude=-3.6886,
            passenger_count=25,
            next_stop_id='S002',
            distance_to_next_stop=500.0,
            speed=30.0
        )
        
        # Should handle gracefully and return False
        assert result is False
    
    def test_handles_generic_exception(self):
        """Test handling of generic exceptions."""
        mock_client = Mock()
        mock_client.put_events.side_effect = Exception("Unexpected error")
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            max_retries=2,
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        
        with patch('time.sleep'):
            result = client.publish_bus_position_event(
                bus_id='B001',
                line_id='L1',
                timestamp=timestamp,
                latitude=40.4657,
                longitude=-3.6886,
                passenger_count=25,
                next_stop_id='S002',
                distance_to_next_stop=500.0,
                speed=30.0
            )
        
        # Should handle gracefully and return False
        assert result is False
        assert mock_client.put_events.call_count == 2


class TestEventStructureValidation:
    """Test that event structures match expected format."""
    
    def test_bus_position_event_has_all_required_fields(self):
        """Test that bus position events contain all required fields."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        client.publish_bus_position_event(
            bus_id='B001',
            line_id='L1',
            timestamp=timestamp,
            latitude=40.4657,
            longitude=-3.6886,
            passenger_count=25,
            next_stop_id='S002',
            distance_to_next_stop=500.0,
            speed=30.0
        )
        
        call_args = mock_client.put_events.call_args[1]
        entry = call_args['Entries'][0]
        detail = json.loads(entry['Detail'])
        
        required_fields = [
            'bus_id', 'line_id', 'timestamp', 'latitude', 'longitude',
            'passenger_count', 'next_stop_id', 'distance_to_next_stop', 'speed'
        ]
        
        for field in required_fields:
            assert field in detail, f"Missing required field: {field}"
    
    def test_bus_arrival_event_has_all_required_fields(self):
        """Test that bus arrival events contain all required fields."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 35, 0)
        client.publish_bus_arrival_events(
            bus_id='B001',
            line_id='L1',
            stop_id='S002',
            timestamp=timestamp,
            passengers_boarding=5,
            passengers_alighting=3,
            bus_passenger_count=27,
            stop_people_count=10
        )
        
        call_args = mock_client.put_events.call_args[1]
        entry = call_args['Entries'][0]
        detail = json.loads(entry['Detail'])
        
        required_fields = [
            'bus_id', 'line_id', 'stop_id', 'timestamp',
            'passengers_boarding', 'passengers_alighting',
            'bus_passenger_count', 'stop_people_count'
        ]
        
        for field in required_fields:
            assert field in detail, f"Missing required field: {field}"
    
    def test_timestamp_format_is_iso8601(self):
        """Test that timestamps are formatted as ISO8601 strings."""
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        timestamp = datetime(2024, 1, 15, 10, 30, 45)
        client.publish_bus_position_event(
            bus_id='B001',
            line_id='L1',
            timestamp=timestamp,
            latitude=40.4657,
            longitude=-3.6886,
            passenger_count=25,
            next_stop_id='S002',
            distance_to_next_stop=500.0,
            speed=30.0
        )
        
        call_args = mock_client.put_events.call_args[1]
        entry = call_args['Entries'][0]
        detail = json.loads(entry['Detail'])
        
        # Verify ISO8601 format
        assert detail['timestamp'] == '2024-01-15T10:30:45'
        
        # Verify it can be parsed back
        parsed = datetime.fromisoformat(detail['timestamp'])
        assert parsed == timestamp
