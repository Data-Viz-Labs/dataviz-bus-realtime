"""
Integration test for the People Count Feeder Service.

This test verifies that the service can be started and run for a short period
with mocked AWS services.
"""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import threading
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from feeders.people_count_feeder import PeopleCountFeederService


class TestPeopleCountFeederIntegration(unittest.TestCase):
    """Integration tests for PeopleCountFeederService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_file = str(Path(__file__).parent.parent / 'data' / 'lines.yaml')
        self.database_name = 'test_db'
        self.table_name = 'test_table'
        self.time_interval = 1  # Short interval for testing
        self.region_name = 'eu-west-1'
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_service_runs_multiple_iterations(self, mock_timestream_class):
        """Test that service can run multiple iterations successfully."""
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_timestream_class.return_value = mock_client
        
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Run service in a separate thread
        service_thread = threading.Thread(target=service.run, daemon=True)
        service_thread.start()
        
        # Let it run for a few seconds (should complete 2-3 iterations)
        time.sleep(3)
        
        # Verify write_records was called multiple times
        self.assertGreater(
            mock_client.write_records.call_count,
            1,
            "Service should have written data multiple times"
        )
        
        # Verify all calls had the correct table name
        for call in mock_client.write_records.call_args_list:
            self.assertEqual(call.kwargs['table_name'], self.table_name)
            self.assertGreater(len(call.kwargs['records']), 0)
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_service_handles_write_failures(self, mock_timestream_class):
        """Test that service continues running even if writes fail."""
        # Set up mock Timestream client that fails on first call, succeeds on second
        mock_client = MagicMock()
        mock_client.write_records.side_effect = [
            Exception("First write fails"),
            None,  # Second write succeeds
            None   # Third write succeeds
        ]
        mock_timestream_class.return_value = mock_client
        
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Run service in a separate thread
        service_thread = threading.Thread(target=service.run, daemon=True)
        service_thread.start()
        
        # Let it run for a few seconds
        time.sleep(3)
        
        # Verify write_records was called multiple times despite the failure
        self.assertGreaterEqual(
            mock_client.write_records.call_count,
            2,
            "Service should continue running after write failure"
        )
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_service_generates_increasing_counts(self, mock_timestream_class):
        """Test that people counts generally increase over time (no bus arrivals)."""
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_timestream_class.return_value = mock_client
        
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Run service in a separate thread
        service_thread = threading.Thread(target=service.run, daemon=True)
        service_thread.start()
        
        # Let it run for a few seconds
        time.sleep(3)
        
        # Get all the records that were written
        all_records = []
        for call in mock_client.write_records.call_args_list:
            all_records.extend(call.kwargs['records'])
        
        # Verify we have records
        self.assertGreater(len(all_records), 0)
        
        # Group records by stop_id
        records_by_stop = {}
        for record in all_records:
            dimensions = {d['Name']: d['Value'] for d in record['Dimensions']}
            stop_id = dimensions['stop_id']
            count = int(record['MeasureValue'])
            
            if stop_id not in records_by_stop:
                records_by_stop[stop_id] = []
            records_by_stop[stop_id].append(count)
        
        # Verify that at least some stops have increasing counts
        # (Since we're using Poisson distribution, not all stops will increase every time)
        stops_with_increases = 0
        for stop_id, counts in records_by_stop.items():
            if len(counts) >= 2:
                # Check if the last count is >= the first count
                if counts[-1] >= counts[0]:
                    stops_with_increases += 1
        
        # At least half of the stops should show non-decreasing counts
        self.assertGreater(
            stops_with_increases,
            len(records_by_stop) // 2,
            "Most stops should have non-decreasing counts over time"
        )


if __name__ == '__main__':
    unittest.main()
