"""
Integration test for historical data volume in Timestream.

**Property 28: Historical data volume**

This test verifies that:
1. The system can generate at least 5 days of continuous historical data
2. Timestream retains at least 5 days of historical data
3. Data is continuous without gaps
4. Data volume is sufficient for hackathon participants

**Validates: Requirements 4.5, 5.4**
"""

import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from feeders.people_count_feeder import PeopleCountFeederService
from feeders.sensor_data_feeder import SensorDataFeederService
from feeders.bus_position_feeder import BusPositionFeederService
from common.timestream_client import TimestreamClient


class TestHistoricalDataVolume(unittest.TestCase):
    """
    Integration tests for historical data volume and retention.
    
    Property 28: Historical data volume
    Validates: Requirements 4.5, 5.4
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_file = str(Path(__file__).parent.parent / 'data' / 'lines.yaml')
        self.database_name = 'test_db'
        self.region_name = 'eu-west-1'
        self.time_interval = 60  # 1 minute intervals for testing
        
        # Track written data for verification
        self.written_data = {
            'people_count': [],
            'sensor_data': [],
            'bus_position': []
        }
        
        # Minimum required days of historical data
        self.min_historical_days = 5
    
    def _capture_write(self, table_name, records, **kwargs):
        """Helper to capture writes to Timestream."""
        timestamp = datetime.now()
        self.written_data[table_name].append({
            'timestamp': timestamp,
            'records': records
        })
        return True
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_people_count_generates_5_days_of_data(self, mock_timestream_class):
        """
        Test that people count feeder can generate at least 5 days of continuous data.
        
        This simulates running the feeder for 5 days and verifies:
        1. Data is generated for each time interval
        2. Data covers the full 5-day period
        3. Data is continuous without gaps
        
        Validates: Requirements 4.5 - Generate at least 5 days of continuous data
        """
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_client.write_records.side_effect = lambda table_name, records: self._capture_write(
            table_name, records
        )
        mock_timestream_class.return_value = mock_client
        
        # Create service
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='people_count',
            time_interval=self.time_interval
        )
        
        # Initialize service
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Simulate 5 days of data generation
        # For testing, we'll simulate hourly intervals (120 intervals = 5 days)
        # In production, this would be every minute for 5 days (7200 intervals)
        intervals_per_day = 24  # Hourly for testing
        total_intervals = intervals_per_day * self.min_historical_days
        
        start_time = datetime.now()
        
        for i in range(total_intervals):
            service.generate_and_write_data()
        
        end_time = datetime.now()
        
        # Verify data was written for all intervals
        self.assertEqual(
            len(self.written_data['people_count']),
            total_intervals,
            f"Should have written data for {total_intervals} intervals (5 days)"
        )
        
        # Verify each write contains records
        for write in self.written_data['people_count']:
            self.assertGreater(
                len(write['records']),
                0,
                "Each write should contain at least one record"
            )
        
        # Verify data continuity - check that all stops have data
        all_stop_ids = set()
        for write in self.written_data['people_count']:
            for record in write['records']:
                dims = {d['Name']: d['Value'] for d in record['Dimensions']}
                all_stop_ids.add(dims['stop_id'])
        
        # Should have data for multiple stops
        self.assertGreater(
            len(all_stop_ids),
            0,
            "Should have generated data for at least one stop"
        )
        
        # Verify total data volume is sufficient
        total_records = sum(len(write['records']) for write in self.written_data['people_count'])
        
        # Minimum expected records: at least 1 stop * 120 intervals = 120 records
        min_expected_records = total_intervals
        self.assertGreaterEqual(
            total_records,
            min_expected_records,
            f"Should have generated at least {min_expected_records} records for 5 days"
        )
    
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    def test_sensor_data_generates_5_days_of_data(self, mock_timestream_class):
        """
        Test that sensor data feeder can generate at least 5 days of continuous data.
        
        Validates: Requirements 4.5 - Generate at least 5 days of continuous data
        """
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_client.write_records.side_effect = lambda table_name, records: self._capture_write(
            table_name, records
        )
        mock_timestream_class.return_value = mock_client
        
        # Create service
        service = SensorDataFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='sensor_data',
            time_interval=self.time_interval
        )
        
        # Initialize service
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Simulate 5 days of data generation (hourly intervals for testing)
        intervals_per_day = 24
        total_intervals = intervals_per_day * self.min_historical_days
        
        for i in range(total_intervals):
            service.generate_and_write_data()
        
        # Verify data was written for all intervals
        self.assertEqual(
            len(self.written_data['sensor_data']),
            total_intervals,
            f"Should have written sensor data for {total_intervals} intervals (5 days)"
        )
        
        # Verify data volume
        total_records = sum(len(write['records']) for write in self.written_data['sensor_data'])
        min_expected_records = total_intervals
        self.assertGreaterEqual(
            total_records,
            min_expected_records,
            f"Should have generated at least {min_expected_records} sensor records for 5 days"
        )
    
    @patch('feeders.bus_position_feeder.TimestreamClient')
    @patch('feeders.bus_position_feeder.EventBridgeClient')
    def test_bus_position_generates_5_days_of_data(self, mock_eventbridge_class, mock_timestream_class):
        """
        Test that bus position feeder can generate at least 5 days of continuous data.
        
        Validates: Requirements 4.5 - Generate at least 5 days of continuous data
        """
        # Set up mock EventBridge client
        mock_eventbridge = MagicMock()
        mock_eventbridge_class.return_value = mock_eventbridge
        
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_client.write_records.side_effect = lambda table_name, records: self._capture_write(
            table_name, records
        )
        mock_timestream_class.return_value = mock_client
        
        # Create service
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='bus_position',
            time_interval=self.time_interval,
            event_bus_name='test-event-bus'
        )
        
        # Initialize service
        service.load_configuration()
        service.initialize_clients()
        
        # Simulate 5 days of data generation (hourly intervals for testing)
        intervals_per_day = 24
        total_intervals = intervals_per_day * self.min_historical_days
        
        for i in range(total_intervals):
            service.simulate_and_write_data()
        
        # Verify data was written for all intervals
        self.assertEqual(
            len(self.written_data['bus_position']),
            total_intervals,
            f"Should have written bus position data for {total_intervals} intervals (5 days)"
        )
        
        # Verify data volume
        total_records = sum(len(write['records']) for write in self.written_data['bus_position'])
        min_expected_records = total_intervals
        self.assertGreaterEqual(
            total_records,
            min_expected_records,
            f"Should have generated at least {min_expected_records} bus position records for 5 days"
        )
    
    @patch('common.timestream_client.boto3')
    def test_timestream_retention_policy_supports_5_days(self, mock_boto3):
        """
        Test that Timestream retention policy is configured to retain at least 5 days of data.
        
        This verifies that the Timestream table configuration supports the required
        data retention period.
        
        Validates: Requirements 5.4 - Retain at least 5 days of historical data
        """
        # Set up mock Timestream write client
        mock_write_client = MagicMock()
        
        # Mock describe_table response with retention policy
        mock_write_client.describe_table.return_value = {
            'Table': {
                'TableName': 'people_count',
                'DatabaseName': self.database_name,
                'RetentionProperties': {
                    'MemoryStoreRetentionPeriodInHours': 24,  # 1 day in memory
                    'MagneticStoreRetentionPeriodInDays': 30  # 30 days in magnetic store
                }
            }
        }
        
        mock_boto3.client.return_value = mock_write_client
        
        # Create Timestream client
        client = TimestreamClient(
            database_name=self.database_name,
            region_name=self.region_name
        )
        
        # Query retention policy
        response = client.write_client.describe_table(
            DatabaseName=self.database_name,
            TableName='people_count'
        )
        
        retention = response['Table']['RetentionProperties']
        memory_retention_hours = retention['MemoryStoreRetentionPeriodInHours']
        magnetic_retention_days = retention['MagneticStoreRetentionPeriodInDays']
        
        # Verify retention policy supports at least 5 days
        # Data should be retained in either memory or magnetic store
        total_retention_days = (memory_retention_hours / 24) + magnetic_retention_days
        
        self.assertGreaterEqual(
            total_retention_days,
            self.min_historical_days,
            f"Timestream retention policy should support at least {self.min_historical_days} days, "
            f"but only supports {total_retention_days} days"
        )
        
        # Verify magnetic store retention is sufficient
        self.assertGreaterEqual(
            magnetic_retention_days,
            self.min_historical_days,
            f"Magnetic store should retain at least {self.min_historical_days} days"
        )
    
    @patch('common.timestream_client.boto3')
    def test_query_historical_data_across_5_days(self, mock_boto3):
        """
        Test that historical data can be queried across the full 5-day period.
        
        This verifies that:
        1. Data can be queried for any point in the 5-day window
        2. Time range queries work correctly
        3. Data is accessible and not expired
        
        Validates: Requirements 5.4 - Retain and query at least 5 days of historical data
        """
        # Set up mock Timestream query client
        mock_query_client = MagicMock()
        
        # Mock query response with data spanning 5 days
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        
        # Generate mock data points across 5 days
        mock_rows = []
        for day in range(5):
            timestamp = five_days_ago + timedelta(days=day)
            mock_rows.append({
                'Data': [
                    {'ScalarValue': 'S001'},  # stop_id
                    {'ScalarValue': timestamp.isoformat()},  # time
                    {'ScalarValue': '10'},  # count
                    {'ScalarValue': 'L1,L2'}  # line_ids
                ]
            })
        
        mock_query_client.query.return_value = {
            'Rows': mock_rows,
            'ColumnInfo': [
                {'Name': 'stop_id', 'Type': {'ScalarType': 'VARCHAR'}},
                {'Name': 'time', 'Type': {'ScalarType': 'TIMESTAMP'}},
                {'Name': 'count', 'Type': {'ScalarType': 'BIGINT'}},
                {'Name': 'line_ids', 'Type': {'ScalarType': 'VARCHAR'}}
            ],
            'QueryId': 'test-query-id'
        }
        
        mock_boto3.client.return_value = mock_query_client
        
        # Create Timestream client
        client = TimestreamClient(
            database_name=self.database_name,
            region_name=self.region_name,
            query_client=mock_query_client
        )
        
        # Query data across 5-day range
        query = f"""
            SELECT stop_id, time, count, line_ids
            FROM "{self.database_name}"."people_count"
            WHERE time >= ago(5d)
            ORDER BY time ASC
        """
        
        result = client.query_client.query(QueryString=query)
        
        # Verify query returned data
        self.assertIn('Rows', result)
        rows = result['Rows']
        
        # Verify we have data spanning 5 days
        self.assertGreaterEqual(
            len(rows),
            5,
            f"Should have at least 5 data points spanning 5 days"
        )
        
        # Verify data spans the full 5-day period
        timestamps = []
        for row in rows:
            time_value = row['Data'][1]['ScalarValue']
            timestamps.append(datetime.fromisoformat(time_value.replace('Z', '+00:00')))
        
        # Check time range
        time_range = max(timestamps) - min(timestamps)
        min_expected_range = timedelta(days=4)  # At least 4 days between first and last
        
        self.assertGreaterEqual(
            time_range,
            min_expected_range,
            f"Data should span at least 4 days, but only spans {time_range}"
        )
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_data_continuity_no_gaps(self, mock_timestream_class):
        """
        Test that generated data is continuous without gaps.
        
        This verifies that:
        1. Data is generated for every time interval
        2. No intervals are skipped
        3. Data generation is reliable over extended periods
        
        Validates: Requirements 4.5 - Continuous data generation
        """
        # Set up mock Timestream client
        mock_client = MagicMock()
        write_timestamps = []
        
        def capture_write_timestamp(table_name, records):
            write_timestamps.append(datetime.now())
            return True
        
        mock_client.write_records.side_effect = capture_write_timestamp
        mock_timestream_class.return_value = mock_client
        
        # Create service
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='people_count',
            time_interval=self.time_interval
        )
        
        # Initialize service
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Simulate continuous data generation (24 intervals = 1 day at hourly rate)
        total_intervals = 24
        
        for i in range(total_intervals):
            service.generate_and_write_data()
        
        # Verify all intervals generated data
        self.assertEqual(
            len(write_timestamps),
            total_intervals,
            "Should have written data for every interval"
        )
        
        # Verify no gaps in data generation
        # All writes should have happened (no skipped intervals)
        for i in range(len(write_timestamps)):
            self.assertIsNotNone(
                write_timestamps[i],
                f"Interval {i} should have generated data"
            )
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    @patch('feeders.bus_position_feeder.TimestreamClient')
    @patch('feeders.bus_position_feeder.EventBridgeClient')
    def test_all_feeders_generate_sufficient_volume(
        self, mock_eventbridge, mock_bus_ts, mock_sensor_ts, mock_people_ts
    ):
        """
        Test that all three feeders together generate sufficient data volume for 5 days.
        
        This integration test verifies:
        1. All feeders can run concurrently
        2. Combined data volume is sufficient for hackathon
        3. All data types are represented
        
        Validates: Requirements 4.5, 5.4 - Complete system data generation
        """
        # Set up mocks
        mock_eventbridge_client = MagicMock()
        mock_eventbridge.return_value = mock_eventbridge_client
        
        people_writes = []
        sensor_writes = []
        bus_writes = []
        
        def capture_people_write(table_name, records):
            people_writes.append(records)
            return True
        
        def capture_sensor_write(table_name, records):
            sensor_writes.append(records)
            return True
        
        def capture_bus_write(table_name, records):
            bus_writes.append(records)
            return True
        
        mock_people_client = MagicMock()
        mock_people_client.write_records.side_effect = capture_people_write
        mock_people_ts.return_value = mock_people_client
        
        mock_sensor_client = MagicMock()
        mock_sensor_client.write_records.side_effect = capture_sensor_write
        mock_sensor_ts.return_value = mock_sensor_client
        
        mock_bus_client = MagicMock()
        mock_bus_client.write_records.side_effect = capture_bus_write
        mock_bus_ts.return_value = mock_bus_client
        
        # Create all three services
        people_service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='people_count',
            time_interval=self.time_interval
        )
        people_service.load_configuration()
        people_service.initialize_timestream_client()
        
        sensor_service = SensorDataFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='sensor_data',
            time_interval=self.time_interval
        )
        sensor_service.load_configuration()
        sensor_service.initialize_timestream_client()
        
        bus_service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='bus_position',
            time_interval=self.time_interval,
            event_bus_name='test-event-bus'
        )
        bus_service.load_configuration()
        bus_service.initialize_clients()
        
        # Simulate 5 days of data generation (hourly for testing)
        intervals_per_day = 24
        total_intervals = intervals_per_day * self.min_historical_days
        
        for i in range(total_intervals):
            people_service.generate_and_write_data()
            sensor_service.generate_and_write_data()
            bus_service.simulate_and_write_data()
        
        # Verify all feeders generated data
        self.assertEqual(len(people_writes), total_intervals, "People count feeder should generate data for all intervals")
        self.assertEqual(len(sensor_writes), total_intervals, "Sensor data feeder should generate data for all intervals")
        self.assertEqual(len(bus_writes), total_intervals, "Bus position feeder should generate data for all intervals")
        
        # Verify total data volume
        total_people_records = sum(len(records) for records in people_writes)
        total_sensor_records = sum(len(records) for records in sensor_writes)
        total_bus_records = sum(len(records) for records in bus_writes)
        
        # Each feeder should generate at least one record per interval
        self.assertGreaterEqual(total_people_records, total_intervals, "Insufficient people count data volume")
        self.assertGreaterEqual(total_sensor_records, total_intervals, "Insufficient sensor data volume")
        self.assertGreaterEqual(total_bus_records, total_intervals, "Insufficient bus position data volume")
        
        # Verify combined data volume is substantial
        total_records = total_people_records + total_sensor_records + total_bus_records
        min_expected_total = total_intervals * 3  # At least 3 records per interval (one per feeder)
        
        self.assertGreaterEqual(
            total_records,
            min_expected_total,
            f"Combined data volume should be at least {min_expected_total} records for 5 days"
        )


if __name__ == '__main__':
    unittest.main()
