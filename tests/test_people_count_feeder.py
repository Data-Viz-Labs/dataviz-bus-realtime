"""
Unit tests for the People Count Feeder Service.

These tests verify that the service can be initialized, load configuration,
and generate data correctly.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from feeders.people_count_feeder import PeopleCountFeederService
from common.config_loader import ConfigurationError


class TestPeopleCountFeederService(unittest.TestCase):
    """Test cases for PeopleCountFeederService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_file = str(Path(__file__).parent.parent / 'data' / 'lines.yaml')
        self.database_name = 'test_db'
        self.table_name = 'test_table'
        self.time_interval = 60
        self.region_name = 'eu-west-1'
    
    def test_initialization(self):
        """Test that service can be initialized with valid parameters."""
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            region_name=self.region_name
        )
        
        self.assertEqual(service.config_file, self.config_file)
        self.assertEqual(service.database_name, self.database_name)
        self.assertEqual(service.table_name, self.table_name)
        self.assertEqual(service.time_interval, self.time_interval)
        self.assertEqual(service.region_name, self.region_name)
        self.assertEqual(len(service.routes), 0)
        self.assertEqual(len(service.stop_counts), 0)
    
    def test_load_configuration(self):
        """Test that configuration can be loaded successfully."""
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        service.load_configuration()
        
        # Verify routes were loaded
        self.assertGreater(len(service.routes), 0)
        
        # Verify stops were initialized
        self.assertGreater(len(service.stop_counts), 0)
        self.assertGreater(len(service.stop_to_lines), 0)
        self.assertGreater(len(service.stops_config), 0)
        
        # Verify all stops have initial count of 0
        for stop_id, count in service.stop_counts.items():
            self.assertEqual(count, 0, f"Stop {stop_id} should start with count 0")
        
        # Verify stop_to_lines mapping is correct
        for stop_id, line_ids in service.stop_to_lines.items():
            self.assertIsInstance(line_ids, list)
            self.assertGreater(len(line_ids), 0)
        
        # Verify stops_config has base arrival rates
        for stop_id, rate in service.stops_config.items():
            self.assertGreater(rate, 0, f"Stop {stop_id} should have positive arrival rate")
    
    def test_load_configuration_invalid_file(self):
        """Test that loading invalid configuration raises error."""
        service = PeopleCountFeederService(
            config_file='nonexistent.yaml',
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        with self.assertRaises(ConfigurationError):
            service.load_configuration()
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_initialize_timestream_client(self, mock_timestream_class):
        """Test that Timestream client can be initialized."""
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            region_name=self.region_name
        )
        
        service.initialize_timestream_client()
        
        # Verify TimestreamClient was instantiated with correct parameters
        mock_timestream_class.assert_called_once_with(
            database_name=self.database_name,
            region_name=self.region_name,
            max_retries=3
        )
        
        self.assertIsNotNone(service.timestream_client)
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_generate_and_write_data(self, mock_timestream_class):
        """Test that data generation and writing works correctly."""
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_timestream_class.return_value = mock_client
        
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Load configuration and initialize client
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Store initial counts
        initial_stop_count = len(service.stop_counts)
        
        # Generate and write data
        service.generate_and_write_data()
        
        # Verify write_records was called
        mock_client.write_records.assert_called_once()
        
        # Get the call arguments
        call_args = mock_client.write_records.call_args
        table_name = call_args.kwargs['table_name']
        records = call_args.kwargs['records']
        
        # Verify correct table name
        self.assertEqual(table_name, self.table_name)
        
        # Verify records were generated for all stops
        self.assertEqual(len(records), initial_stop_count)
        
        # Verify record structure
        for record in records:
            self.assertIn('Dimensions', record)
            self.assertIn('MeasureName', record)
            self.assertIn('MeasureValue', record)
            self.assertIn('MeasureValueType', record)
            self.assertIn('Time', record)
            self.assertIn('TimeUnit', record)
            
            # Verify dimensions
            dimensions = {d['Name']: d['Value'] for d in record['Dimensions']}
            self.assertIn('stop_id', dimensions)
            self.assertIn('line_ids', dimensions)
            
            # Verify measure
            self.assertEqual(record['MeasureName'], 'count')
            self.assertEqual(record['MeasureValueType'], 'BIGINT')
            self.assertEqual(record['TimeUnit'], 'MILLISECONDS')
            
            # Verify count is non-negative
            count = int(record['MeasureValue'])
            self.assertGreaterEqual(count, 0)
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_generate_and_write_data_updates_state(self, mock_timestream_class):
        """Test that data generation updates internal state correctly."""
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_timestream_class.return_value = mock_client
        
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Load configuration and initialize client
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Store initial counts (should all be 0)
        initial_counts = dict(service.stop_counts)
        
        # Generate data
        service.generate_and_write_data()
        
        # Verify counts were updated (should be >= 0, likely > 0 for at least some stops)
        for stop_id, new_count in service.stop_counts.items():
            self.assertGreaterEqual(new_count, 0)
            # Count should have changed for at least some stops (due to arrivals)
            # But we can't guarantee this for every stop in every run
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_generate_and_write_data_handles_errors(self, mock_timestream_class):
        """Test that errors during data generation are handled gracefully."""
        # Set up mock Timestream client that raises an error
        mock_client = MagicMock()
        mock_client.write_records.side_effect = Exception("Timestream error")
        mock_timestream_class.return_value = mock_client
        
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Load configuration and initialize client
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Generate and write data - should not raise exception
        try:
            service.generate_and_write_data()
        except Exception as e:
            self.fail(f"generate_and_write_data should handle errors gracefully, but raised: {e}")


if __name__ == '__main__':
    unittest.main()
