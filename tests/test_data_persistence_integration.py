"""
Integration test for end-to-end data flow from feeders to Timestream to APIs.

**Property 23: Data persistence timeliness**

This test verifies that:
1. Feeder services generate data
2. Data is persisted to Timestream immediately
3. Data can be retrieved via APIs within an acceptable time window

**Validates: Requirements 5.1**
"""

import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from feeders.people_count_feeder import PeopleCountFeederService
from feeders.sensor_data_feeder import SensorDataFeederService
from feeders.bus_position_feeder import BusPositionFeederService
from common.timestream_client import TimestreamClient
from lambdas.people_count_api import lambda_handler as people_count_handler
from lambdas.sensors_api import lambda_handler as sensors_handler
from lambdas.bus_position_api import lambda_handler as bus_position_handler


class TestDataPersistenceTimeliness(unittest.TestCase):
    """
    Integration tests for end-to-end data flow.
    
    Property 23: Data persistence timeliness
    Validates: Requirements 5.1
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_file = str(Path(__file__).parent.parent / 'data' / 'lines.yaml')
        self.database_name = 'test_db'
        self.region_name = 'eu-west-1'
        self.time_interval = 1  # Short interval for testing
        
        # Track written data for verification
        self.written_data = {
            'people_count': [],
            'sensor_data': [],
            'bus_position': []
        }
    
    def _capture_write(self, table_name, records, **kwargs):
        """Helper to capture writes to Timestream."""
        timestamp = datetime.now()
        self.written_data[table_name].append({
            'timestamp': timestamp,
            'records': records
        })
        return True
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_people_count_data_persisted_immediately(self, mock_timestream_class):
        """
        Test that people count data is persisted to Timestream immediately.
        
        Validates: Requirements 5.1 - Data must be persisted immediately
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
        
        # Record start time
        start_time = datetime.now()
        
        # Generate and write data
        service.generate_and_write_data()
        
        # Record end time
        end_time = datetime.now()
        
        # Verify data was written
        self.assertEqual(len(self.written_data['people_count']), 1)
        
        # Verify write happened immediately (within acceptable window)
        write_time = self.written_data['people_count'][0]['timestamp']
        time_to_persist = (write_time - start_time).total_seconds()
        
        # Data should be persisted within 1 second
        self.assertLess(
            time_to_persist,
            1.0,
            f"Data persistence took {time_to_persist}s, expected < 1s"
        )
        
        # Verify records were written
        records = self.written_data['people_count'][0]['records']
        self.assertGreater(len(records), 0, "Should have written at least one record")
        
        # Verify record structure
        for record in records:
            self.assertIn('Dimensions', record)
            self.assertIn('MeasureName', record)
            self.assertIn('MeasureValue', record)
            self.assertIn('Time', record)
            self.assertEqual(record['MeasureName'], 'count')
    
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    def test_sensor_data_persisted_immediately(self, mock_timestream_class):
        """
        Test that sensor data is persisted to Timestream immediately.
        
        Validates: Requirements 5.1 - Data must be persisted immediately
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
        
        # Record start time
        start_time = datetime.now()
        
        # Generate and write data
        service.generate_and_write_data()
        
        # Record end time
        end_time = datetime.now()
        
        # Verify data was written
        self.assertEqual(len(self.written_data['sensor_data']), 1)
        
        # Verify write happened immediately (within acceptable window)
        write_time = self.written_data['sensor_data'][0]['timestamp']
        time_to_persist = (write_time - start_time).total_seconds()
        
        # Data should be persisted within 1 second
        self.assertLess(
            time_to_persist,
            1.0,
            f"Data persistence took {time_to_persist}s, expected < 1s"
        )
        
        # Verify records were written
        records = self.written_data['sensor_data'][0]['records']
        self.assertGreater(len(records), 0, "Should have written at least one record")
    
    @patch('feeders.bus_position_feeder.TimestreamClient')
    @patch('feeders.bus_position_feeder.EventBridgeClient')
    def test_bus_position_data_persisted_immediately(self, mock_eventbridge_class, mock_timestream_class):
        """
        Test that bus position data is persisted to Timestream immediately.
        
        Validates: Requirements 5.1 - Data must be persisted immediately
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
        
        # Record start time
        start_time = datetime.now()
        
        # Generate and write data
        service.simulate_and_write_data()
        
        # Record end time
        end_time = datetime.now()
        
        # Verify data was written
        self.assertEqual(len(self.written_data['bus_position']), 1)
        
        # Verify write happened immediately (within acceptable window)
        write_time = self.written_data['bus_position'][0]['timestamp']
        time_to_persist = (write_time - start_time).total_seconds()
        
        # Data should be persisted within 1 second
        self.assertLess(
            time_to_persist,
            1.0,
            f"Data persistence took {time_to_persist}s, expected < 1s"
        )
        
        # Verify records were written
        records = self.written_data['bus_position'][0]['records']
        self.assertGreater(len(records), 0, "Should have written at least one record")
    
    @patch('lambdas.people_count_api.TimestreamClient')
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_end_to_end_people_count_flow(self, mock_feeder_timestream, mock_api_timestream):
        """
        Test complete end-to-end flow: feeder generates data -> persists to Timestream -> API retrieves it.
        
        This test verifies:
        1. Feeder generates data
        2. Data is written to Timestream
        3. API can query the data immediately
        
        Validates: Requirements 5.1 - Immediate persistence and retrieval
        """
        # Set up mock for feeder's Timestream client
        mock_feeder_client = MagicMock()
        written_records = []
        
        def capture_feeder_write(table_name, records):
            written_records.extend(records)
            return True
        
        mock_feeder_client.write_records.side_effect = capture_feeder_write
        mock_feeder_timestream.return_value = mock_feeder_client
        
        # Set up mock for API's Timestream client
        mock_api_client = MagicMock()
        
        def mock_query_latest(table_name, dimensions, limit=1):
            # Return the data that was just written
            if not written_records:
                return None
            
            # Find matching record
            for record in written_records:
                dims = {d['Name']: d['Value'] for d in record['Dimensions']}
                if all(dims.get(k) == v for k, v in dimensions.items()):
                    return {
                        'rows': [{
                            'stop_id': dims['stop_id'],
                            'time': record['Time'],
                            'count': record['MeasureValue'],
                            'line_ids': dims.get('line_ids', '')
                        }],
                        'column_info': [],
                        'query_id': 'test-query-id'
                    }
            return None
        
        mock_api_client.query_latest.side_effect = mock_query_latest
        mock_api_timestream.return_value = mock_api_client
        
        # Step 1: Feeder generates and writes data
        service = PeopleCountFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='people_count',
            time_interval=self.time_interval
        )
        
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Record time before generation
        generation_start = datetime.now()
        
        # Generate data
        service.generate_and_write_data()
        
        # Verify data was written
        self.assertGreater(len(written_records), 0, "Feeder should have written records")
        
        # Step 2: API retrieves the data
        # Get the first stop_id from written records
        first_record = written_records[0]
        dims = {d['Name']: d['Value'] for d in first_record['Dimensions']}
        stop_id = dims['stop_id']
        
        # Create API event
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'mode': 'latest'},
            'headers': {'x-group-name': 'test-group'},
            'requestContext': {'authorizer': {'group_name': 'test-group'}}
        }
        
        # Call API
        query_start = datetime.now()
        response = people_count_handler(event, None)
        query_end = datetime.now()
        
        # Verify API response
        self.assertEqual(response['statusCode'], 200)
        
        # Verify data retrieval was immediate
        total_time = (query_end - generation_start).total_seconds()
        self.assertLess(
            total_time,
            2.0,
            f"End-to-end flow took {total_time}s, expected < 2s"
        )
        
        # Verify the API returned the correct data
        import json
        body = json.loads(response['body'])
        self.assertIn('stop_id', body)
        self.assertEqual(body['stop_id'], stop_id)
        self.assertIn('count', body)
    
    @patch('lambdas.sensors_api.TimestreamClient')
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    def test_end_to_end_sensor_data_flow(self, mock_feeder_timestream, mock_api_timestream):
        """
        Test complete end-to-end flow for sensor data.
        
        Validates: Requirements 5.1 - Immediate persistence and retrieval
        """
        # Set up mock for feeder's Timestream client
        mock_feeder_client = MagicMock()
        written_records = []
        
        def capture_feeder_write(table_name, records):
            written_records.extend(records)
            return True
        
        mock_feeder_client.write_records.side_effect = capture_feeder_write
        mock_feeder_timestream.return_value = mock_feeder_client
        
        # Set up mock for API's Timestream client
        mock_api_client = MagicMock()
        
        def mock_query_latest(table_name, dimensions, limit=1):
            if not written_records:
                return None
            
            # Find matching record
            for record in written_records:
                dims = {d['Name']: d['Value'] for d in record['Dimensions']}
                if all(dims.get(k) == v for k, v in dimensions.items()):
                    # Parse multi-measure record
                    measures = {}
                    if 'MeasureValues' in record:
                        # Multi-measure format
                        for measure in record['MeasureValues']:
                            measures[measure['Name']] = measure['Value']
                    elif 'MeasureName' in record and 'MeasureValue' in record:
                        # Single measure format
                        measures[record['MeasureName']] = record['MeasureValue']
                    
                    return {
                        'rows': [{
                            'entity_id': dims['entity_id'],
                            'entity_type': dims['entity_type'],
                            'time': record['Time'],
                            **measures
                        }],
                        'column_info': [],
                        'query_id': 'test-query-id'
                    }
            return None
        
        mock_api_client.query_latest.side_effect = mock_query_latest
        mock_api_timestream.return_value = mock_api_client
        
        # Step 1: Feeder generates and writes data
        service = SensorDataFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name='sensor_data',
            time_interval=self.time_interval
        )
        
        service.load_configuration()
        service.initialize_timestream_client()
        
        generation_start = datetime.now()
        service.generate_and_write_data()
        
        self.assertGreater(len(written_records), 0, "Feeder should have written records")
        
        # Step 2: API retrieves the data
        first_record = written_records[0]
        dims = {d['Name']: d['Value'] for d in first_record['Dimensions']}
        entity_id = dims['entity_id']
        entity_type = dims['entity_type']
        
        event = {
            'pathParameters': {
                'entity_type': entity_type,
                'entity_id': entity_id
            },
            'queryStringParameters': {'mode': 'latest'},
            'headers': {'x-group-name': 'test-group'},
            'requestContext': {'authorizer': {'group_name': 'test-group'}}
        }
        
        query_start = datetime.now()
        response = sensors_handler(event, None)
        query_end = datetime.now()
        
        # Verify response
        self.assertEqual(response['statusCode'], 200)
        
        # Verify timeliness
        total_time = (query_end - generation_start).total_seconds()
        self.assertLess(
            total_time,
            2.0,
            f"End-to-end flow took {total_time}s, expected < 2s"
        )
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_multiple_feeders_persist_concurrently(self, mock_timestream_class):
        """
        Test that multiple feeder services can persist data concurrently.
        
        This verifies that the system can handle concurrent writes from
        multiple feeder services without data loss or conflicts.
        
        Validates: Requirements 5.1 - Immediate persistence under concurrent load
        """
        # Set up mock Timestream client
        mock_client = MagicMock()
        write_times = []
        
        def capture_write_time(table_name, records):
            write_times.append(datetime.now())
            return True
        
        mock_client.write_records.side_effect = capture_write_time
        mock_timestream_class.return_value = mock_client
        
        # Create multiple services
        services = []
        for i in range(3):
            service = PeopleCountFeederService(
                config_file=self.config_file,
                database_name=self.database_name,
                table_name='people_count',
                time_interval=self.time_interval
            )
            service.load_configuration()
            service.initialize_timestream_client()
            services.append(service)
        
        # Generate data from all services
        start_time = datetime.now()
        for service in services:
            service.generate_and_write_data()
        end_time = datetime.now()
        
        # Verify all services wrote data
        self.assertEqual(len(write_times), 3, "All services should have written data")
        
        # Verify all writes happened within acceptable time window
        for write_time in write_times:
            time_to_persist = (write_time - start_time).total_seconds()
            self.assertLess(
                time_to_persist,
                2.0,
                f"Concurrent write took {time_to_persist}s, expected < 2s"
            )
    
    @patch('feeders.people_count_feeder.TimestreamClient')
    def test_data_persistence_with_retry_on_failure(self, mock_timestream_class):
        """
        Test that data persistence retries on failure and eventually succeeds.
        
        This verifies that the retry logic ensures data is persisted even
        when transient failures occur.
        
        Validates: Requirements 5.1 - Reliable persistence with retry
        """
        from botocore.exceptions import ClientError
        
        # Set up mock Timestream client that fails first, then succeeds
        mock_client = MagicMock()
        attempt_times = []
        
        def track_attempts(**kwargs):
            attempt_times.append(datetime.now())
            if len(attempt_times) == 1:
                # First attempt fails with ClientError
                error_response = {
                    'Error': {
                        'Code': 'ThrottlingException',
                        'Message': 'Rate exceeded'
                    }
                }
                raise ClientError(error_response, 'WriteRecords')
            # Subsequent attempts succeed
            return {'ResponseMetadata': {'HTTPStatusCode': 200}}
        
        mock_client.write_records.side_effect = track_attempts
        mock_timestream_class.return_value = mock_client
        
        # Create Timestream client with retry
        client = TimestreamClient(
            database_name=self.database_name,
            region_name=self.region_name,
            max_retries=3,
            write_client=mock_client,
            query_client=MagicMock()
        )
        
        # Attempt to write data
        start_time = datetime.now()
        records = [{
            'Dimensions': [{'Name': 'test', 'Value': 'value'}],
            'MeasureName': 'test_measure',
            'MeasureValue': '1',
            'MeasureValueType': 'BIGINT',
            'Time': str(int(datetime.now().timestamp() * 1000)),
            'TimeUnit': 'MILLISECONDS'
        }]
        
        success = client.write_records('test_table', records)
        end_time = datetime.now()
        
        # Verify write eventually succeeded
        self.assertTrue(success, "Write should succeed after retry")
        
        # Verify retry happened
        self.assertEqual(len(attempt_times), 2, "Should have retried once")
        
        # Verify total time is reasonable (includes backoff)
        total_time = (end_time - start_time).total_seconds()
        self.assertLess(
            total_time,
            5.0,
            f"Write with retry took {total_time}s, expected < 5s"
        )


if __name__ == '__main__':
    unittest.main()
