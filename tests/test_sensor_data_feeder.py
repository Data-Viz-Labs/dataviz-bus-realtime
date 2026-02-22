"""
Unit tests for the Sensor Data Feeder Service.

These tests verify that the service can be initialized, load configuration,
and generate sensor data correctly for both buses and stops.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from feeders.sensor_data_feeder import SensorDataFeederService
from common.config_loader import ConfigurationError


class TestSensorDataFeederService(unittest.TestCase):
    """Test cases for SensorDataFeederService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_file = str(Path(__file__).parent.parent / 'data' / 'lines.yaml')
        self.database_name = 'test_db'
        self.table_name = 'test_table'
        self.time_interval = 60
        self.region_name = 'eu-west-1'
    
    def test_initialization(self):
        """Test that service can be initialized with valid parameters."""
        service = SensorDataFeederService(
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
        self.assertEqual(len(service.buses), 0)
        self.assertEqual(len(service.stops), 0)
    
    def test_load_configuration(self):
        """Test that configuration can be loaded successfully."""
        service = SensorDataFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        service.load_configuration()
        
        # Verify routes were loaded
        self.assertGreater(len(service.routes), 0)
        
        # Verify buses were loaded
        self.assertGreater(len(service.buses), 0)
        
        # Verify stops were loaded
        self.assertGreater(len(service.stops), 0)
        
        # Verify all buses have valid state
        for bus_id, bus_state in service.buses.items():
            self.assertIsNotNone(bus_state)
            self.assertEqual(bus_state.bus_id, bus_id)
            self.assertGreaterEqual(bus_state.passenger_count, 0)
            self.assertGreater(bus_state.capacity, 0)
        
        # Verify all stops have valid data
        for stop_id, stop in service.stops.items():
            self.assertIsNotNone(stop)
            self.assertEqual(stop.stop_id, stop_id)
            self.assertGreater(stop.base_arrival_rate, 0)
    
    def test_load_configuration_invalid_file(self):
        """Test that loading invalid configuration raises error."""
        service = SensorDataFeederService(
            config_file='nonexistent.yaml',
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        with self.assertRaises(ConfigurationError):
            service.load_configuration()
    
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    def test_initialize_timestream_client(self, mock_timestream_class):
        """Test that Timestream client can be initialized."""
        service = SensorDataFeederService(
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
    
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    def test_generate_and_write_data(self, mock_timestream_class):
        """Test that data generation and writing works correctly."""
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_timestream_class.return_value = mock_client
        
        service = SensorDataFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Load configuration and initialize client
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Store counts
        bus_count = len(service.buses)
        stop_count = len(service.stops)
        expected_records = bus_count + stop_count
        
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
        
        # Verify records were generated for all buses and stops
        self.assertEqual(len(records), expected_records)
        
        # Verify record structure
        bus_records = 0
        stop_records = 0
        
        for record in records:
            self.assertIn('Dimensions', record)
            self.assertIn('MeasureName', record)
            self.assertIn('MeasureValueType', record)
            self.assertIn('MeasureValues', record)
            self.assertIn('Time', record)
            self.assertIn('TimeUnit', record)
            
            # Verify dimensions
            dimensions = {d['Name']: d['Value'] for d in record['Dimensions']}
            self.assertIn('entity_id', dimensions)
            self.assertIn('entity_type', dimensions)
            
            entity_type = dimensions['entity_type']
            self.assertIn(entity_type, ['bus', 'stop'])
            
            # Verify measure
            self.assertEqual(record['MeasureName'], 'metrics')
            self.assertEqual(record['MeasureValueType'], 'MULTI')
            self.assertEqual(record['TimeUnit'], 'MILLISECONDS')
            
            # Verify measure values
            measure_values = {m['Name']: m for m in record['MeasureValues']}
            self.assertIn('temperature', measure_values)
            self.assertIn('humidity', measure_values)
            
            # Verify temperature and humidity are valid
            temp = float(measure_values['temperature']['Value'])
            humidity = float(measure_values['humidity']['Value'])
            self.assertGreaterEqual(temp, -50)
            self.assertLessEqual(temp, 60)
            self.assertGreaterEqual(humidity, 0)
            self.assertLessEqual(humidity, 100)
            
            # Bus-specific checks
            if entity_type == 'bus':
                bus_records += 1
                self.assertIn('co2_level', measure_values)
                self.assertIn('door_status', measure_values)
                
                co2 = int(measure_values['co2_level']['Value'])
                door_status = measure_values['door_status']['Value']
                
                self.assertGreaterEqual(co2, 0)
                self.assertIn(door_status, ['open', 'closed'])
            else:
                stop_records += 1
                # Stops should only have temperature and humidity
                self.assertEqual(len(measure_values), 2)
        
        # Verify we got the right number of each type
        self.assertEqual(bus_records, bus_count)
        self.assertEqual(stop_records, stop_count)
    
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    def test_generate_and_write_data_handles_errors(self, mock_timestream_class):
        """Test that errors during data generation are handled gracefully."""
        # Set up mock Timestream client that raises an error
        mock_client = MagicMock()
        mock_client.write_records.side_effect = Exception("Timestream error")
        mock_timestream_class.return_value = mock_client
        
        service = SensorDataFeederService(
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
    
    @patch('feeders.sensor_data_feeder.TimestreamClient')
    def test_sensor_data_consistency(self, mock_timestream_class):
        """Test that sensor data is consistent with bus state."""
        # Set up mock Timestream client
        mock_client = MagicMock()
        mock_timestream_class.return_value = mock_client
        
        service = SensorDataFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval
        )
        
        # Load configuration and initialize client
        service.load_configuration()
        service.initialize_timestream_client()
        
        # Set a bus to be at a stop
        if service.buses:
            first_bus_id = list(service.buses.keys())[0]
            service.buses[first_bus_id].at_stop = True
            service.buses[first_bus_id].passenger_count = 30
        
        # Generate data
        service.generate_and_write_data()
        
        # Get the records
        call_args = mock_client.write_records.call_args
        records = call_args.kwargs['records']
        
        # Find the bus record
        for record in records:
            dimensions = {d['Name']: d['Value'] for d in record['Dimensions']}
            if dimensions['entity_type'] == 'bus' and dimensions['entity_id'] == first_bus_id:
                measure_values = {m['Name']: m for m in record['MeasureValues']}
                door_status = measure_values['door_status']['Value']
                
                # Door should be open when at stop
                self.assertEqual(door_status, 'open')
                
                # CO2 should be elevated with passengers
                co2 = int(measure_values['co2_level']['Value'])
                self.assertGreater(co2, 400)  # Base CO2 is 400 ppm
                break


if __name__ == '__main__':
    unittest.main()
