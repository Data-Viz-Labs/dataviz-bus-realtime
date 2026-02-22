"""
Unit tests for the Bus Position Feeder Service.

Tests cover:
- Service initialization
- Configuration loading
- Main loop iteration with mocked clients
- Bus movement simulation integration
- Arrival handling (boarding/alighting)
- Timestream writes
- EventBridge event publishing
- Error handling and recovery
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from feeders.bus_position_feeder import BusPositionFeederService
from common.models import Route, Stop, BusState, BusPositionDataPoint


class TestBusPositionFeederService(unittest.TestCase):
    """Test cases for BusPositionFeederService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config_file = "data/lines.yaml"
        self.database_name = "test_db"
        self.table_name = "test_table"
        self.time_interval = 30
        self.event_bus_name = "test-event-bus"
        self.region_name = "eu-west-1"
        
        # Create test route
        self.test_stops = [
            Stop(
                stop_id="S001",
                name="Stop 1",
                latitude=40.4657,
                longitude=-3.6886,
                is_terminal=True,
                base_arrival_rate=2.5
            ),
            Stop(
                stop_id="S002",
                name="Stop 2",
                latitude=40.4700,
                longitude=-3.6900,
                is_terminal=False,
                base_arrival_rate=1.8
            ),
            Stop(
                stop_id="S003",
                name="Stop 3",
                latitude=40.4750,
                longitude=-3.6950,
                is_terminal=True,
                base_arrival_rate=2.0
            )
        ]
        
        self.test_route = Route(
            line_id="L1",
            name="Test Line",
            stops=self.test_stops
        )
        
        # Create test bus
        self.test_bus = BusState(
            bus_id="B001",
            line_id="L1",
            capacity=80,
            passenger_count=25,
            position_on_route=0.1,
            speed=30.0,
            at_stop=False
        )
    
    def test_service_initialization(self):
        """Test that service initializes with correct parameters."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        self.assertEqual(service.config_file, self.config_file)
        self.assertEqual(service.database_name, self.database_name)
        self.assertEqual(service.table_name, self.table_name)
        self.assertEqual(service.time_interval, self.time_interval)
        self.assertEqual(service.event_bus_name, self.event_bus_name)
        self.assertEqual(service.region_name, self.region_name)
        self.assertIsNone(service.timestream_client)
        self.assertIsNone(service.eventbridge_client)
        self.assertEqual(len(service.routes), 0)
        self.assertEqual(len(service.buses), 0)
    
    @patch('feeders.bus_position_feeder.load_configuration')
    def test_load_configuration_success(self, mock_load_config):
        """Test successful configuration loading."""
        # Mock configuration loading
        mock_load_config.return_value = (
            [self.test_route],
            {"B001": self.test_bus}
        )
        
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        service.load_configuration()
        
        # Verify configuration was loaded
        self.assertEqual(len(service.routes), 1)
        self.assertIn("L1", service.routes)
        self.assertEqual(len(service.buses), 1)
        self.assertIn("B001", service.buses)
        self.assertEqual(len(service.stop_counts), 3)
        
        # Verify stops were initialized with reasonable counts
        for stop in self.test_stops:
            self.assertIn(stop.stop_id, service.stop_counts)
            self.assertGreater(service.stop_counts[stop.stop_id], 0)
    
    @patch('feeders.bus_position_feeder.EventBridgeClient')
    @patch('feeders.bus_position_feeder.TimestreamClient')
    def test_initialize_clients(self, mock_timestream, mock_eventbridge):
        """Test client initialization."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        service.initialize_clients()
        
        # Verify clients were created with correct parameters
        mock_timestream.assert_called_once_with(
            database_name=self.database_name,
            region_name=self.region_name,
            max_retries=3
        )
        
        mock_eventbridge.assert_called_once_with(
            event_bus_name=self.event_bus_name,
            region_name=self.region_name,
            max_retries=3
        )
        
        self.assertIsNotNone(service.timestream_client)
        self.assertIsNotNone(service.eventbridge_client)
    
    @patch('feeders.bus_position_feeder.simulate_bus_movement')
    def test_simulate_and_write_data_no_stops_reached(self, mock_simulate):
        """Test simulation when bus doesn't reach any stops."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        # Set up service state
        service.routes = {"L1": self.test_route}
        service.buses = {"B001": self.test_bus}
        service.stop_counts = {"S001": 10, "S002": 15, "S003": 8}
        
        # Mock clients
        service.timestream_client = Mock()
        service.eventbridge_client = Mock()
        
        # Mock bus movement - no stops reached
        position_data = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4680,
            longitude=-3.6890,
            passenger_count=25,
            next_stop_id="S002",
            distance_to_next_stop=300.0,
            speed=30.0
        )
        mock_simulate.return_value = (position_data, [])
        
        # Run simulation
        service.simulate_and_write_data()
        
        # Verify simulate_bus_movement was called
        mock_simulate.assert_called_once()
        
        # Verify Timestream write was called
        service.timestream_client.write_records.assert_called_once()
        call_args = service.timestream_client.write_records.call_args
        self.assertEqual(call_args[1]['table_name'], self.table_name)
        records = call_args[1]['records']
        self.assertEqual(len(records), 1)
        
        # Verify position event was published
        service.eventbridge_client.publish_bus_position_event.assert_called_once()
        
        # Verify no arrival events were published (no stops reached)
        service.eventbridge_client.publish_bus_arrival_events.assert_not_called()
        
        # Verify passenger count unchanged (no boarding/alighting)
        self.assertEqual(service.buses["B001"].passenger_count, 25)
    
    @patch('feeders.bus_position_feeder.calculate_boarding')
    @patch('feeders.bus_position_feeder.calculate_alighting')
    @patch('feeders.bus_position_feeder.simulate_bus_movement')
    def test_simulate_and_write_data_with_stop_arrival(
        self, mock_simulate, mock_alighting, mock_boarding
    ):
        """Test simulation when bus reaches a stop."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        # Set up service state
        service.routes = {"L1": self.test_route}
        service.buses = {"B001": self.test_bus}
        service.stop_counts = {"S001": 10, "S002": 15, "S003": 8}
        
        # Mock clients
        service.timestream_client = Mock()
        service.eventbridge_client = Mock()
        
        # Mock bus movement - reaches S002
        position_data = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4700,
            longitude=-3.6900,
            passenger_count=25,  # Will be updated after boarding/alighting
            next_stop_id="S003",
            distance_to_next_stop=500.0,
            speed=30.0
        )
        mock_simulate.return_value = (position_data, [self.test_stops[1]])  # S002
        
        # Mock boarding/alighting calculations
        mock_alighting.return_value = 5  # 5 people get off
        mock_boarding.return_value = 8   # 8 people get on
        
        # Run simulation
        service.simulate_and_write_data()
        
        # Verify boarding/alighting calculations were called
        mock_alighting.assert_called_once_with(
            passenger_count=25,
            is_terminal=False
        )
        mock_boarding.assert_called_once_with(
            people_at_stop=15,
            available_capacity=60  # 80 capacity - (25 - 5 alighting)
        )
        
        # Verify bus passenger count was updated
        expected_passengers = 25 - 5 + 8  # 28
        self.assertEqual(service.buses["B001"].passenger_count, expected_passengers)
        
        # Verify stop count was updated
        expected_stop_count = 15 - 8  # 7
        self.assertEqual(service.stop_counts["S002"], expected_stop_count)
        
        # Verify arrival event was published
        service.eventbridge_client.publish_bus_arrival_events.assert_called_once()
        call_args = service.eventbridge_client.publish_bus_arrival_events.call_args[1]
        self.assertEqual(call_args['bus_id'], "B001")
        self.assertEqual(call_args['stop_id'], "S002")
        self.assertEqual(call_args['passengers_boarding'], 8)
        self.assertEqual(call_args['passengers_alighting'], 5)
        self.assertEqual(call_args['bus_passenger_count'], expected_passengers)
        self.assertEqual(call_args['stop_people_count'], expected_stop_count)
        
        # Verify position event was published
        service.eventbridge_client.publish_bus_position_event.assert_called_once()
    
    @patch('feeders.bus_position_feeder.calculate_boarding')
    @patch('feeders.bus_position_feeder.calculate_alighting')
    @patch('feeders.bus_position_feeder.simulate_bus_movement')
    def test_simulate_and_write_data_terminal_stop(
        self, mock_simulate, mock_alighting, mock_boarding
    ):
        """Test simulation when bus reaches a terminal stop."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        # Set up service state
        service.routes = {"L1": self.test_route}
        service.buses = {"B001": self.test_bus}
        service.stop_counts = {"S001": 10, "S002": 15, "S003": 8}
        
        # Mock clients
        service.timestream_client = Mock()
        service.eventbridge_client = Mock()
        
        # Mock bus movement - reaches terminal S003
        position_data = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4750,
            longitude=-3.6950,
            passenger_count=25,
            next_stop_id="S003",
            distance_to_next_stop=0.0,
            speed=30.0
        )
        mock_simulate.return_value = (position_data, [self.test_stops[2]])  # S003 (terminal)
        
        # Mock boarding/alighting - everyone gets off at terminal
        mock_alighting.return_value = 25  # All passengers get off
        mock_boarding.return_value = 5    # New passengers board
        
        # Run simulation
        service.simulate_and_write_data()
        
        # Verify alighting was called with is_terminal=True
        mock_alighting.assert_called_once_with(
            passenger_count=25,
            is_terminal=True
        )
        
        # Verify bus passenger count reflects terminal logic
        expected_passengers = 25 - 25 + 5  # 5 (only new boarders)
        self.assertEqual(service.buses["B001"].passenger_count, expected_passengers)
    
    @patch('feeders.bus_position_feeder.simulate_bus_movement')
    def test_simulate_and_write_data_multiple_buses(self, mock_simulate):
        """Test simulation with multiple buses."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        # Add second bus
        bus2 = BusState(
            bus_id="B002",
            line_id="L1",
            capacity=80,
            passenger_count=30,
            position_on_route=0.5,
            speed=25.0,
            at_stop=False
        )
        
        # Set up service state
        service.routes = {"L1": self.test_route}
        service.buses = {"B001": self.test_bus, "B002": bus2}
        service.stop_counts = {"S001": 10, "S002": 15, "S003": 8}
        
        # Mock clients
        service.timestream_client = Mock()
        service.eventbridge_client = Mock()
        
        # Mock bus movement for both buses
        def simulate_side_effect(bus, route, time_delta):
            position_data = BusPositionDataPoint(
                bus_id=bus.bus_id,
                line_id=bus.line_id,
                timestamp=datetime.now(),
                latitude=40.4680,
                longitude=-3.6890,
                passenger_count=bus.passenger_count,
                next_stop_id="S002",
                distance_to_next_stop=300.0,
                speed=bus.speed
            )
            return (position_data, [])
        
        mock_simulate.side_effect = simulate_side_effect
        
        # Run simulation
        service.simulate_and_write_data()
        
        # Verify simulate_bus_movement was called for both buses
        self.assertEqual(mock_simulate.call_count, 2)
        
        # Verify Timestream write includes both buses
        call_args = service.timestream_client.write_records.call_args
        records = call_args[1]['records']
        self.assertEqual(len(records), 2)
        
        # Verify position events were published for both buses
        self.assertEqual(service.eventbridge_client.publish_bus_position_event.call_count, 2)
    
    @patch('feeders.bus_position_feeder.simulate_bus_movement')
    def test_simulate_and_write_data_timestream_failure(self, mock_simulate):
        """Test error handling when Timestream write fails."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        # Set up service state
        service.routes = {"L1": self.test_route}
        service.buses = {"B001": self.test_bus}
        service.stop_counts = {"S001": 10, "S002": 15, "S003": 8}
        
        # Mock clients
        service.timestream_client = Mock()
        service.timestream_client.write_records.side_effect = Exception("Timestream error")
        service.eventbridge_client = Mock()
        
        # Mock bus movement
        position_data = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4680,
            longitude=-3.6890,
            passenger_count=25,
            next_stop_id="S002",
            distance_to_next_stop=300.0,
            speed=30.0
        )
        mock_simulate.return_value = (position_data, [])
        
        # Run simulation - should not raise exception
        try:
            service.simulate_and_write_data()
        except Exception as e:
            self.fail(f"simulate_and_write_data raised exception: {e}")
        
        # Verify Timestream write was attempted
        service.timestream_client.write_records.assert_called_once()
    
    @patch('feeders.bus_position_feeder.simulate_bus_movement')
    def test_simulate_and_write_data_eventbridge_failure(self, mock_simulate):
        """Test that EventBridge failures don't stop processing."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        # Set up service state
        service.routes = {"L1": self.test_route}
        service.buses = {"B001": self.test_bus}
        service.stop_counts = {"S001": 10, "S002": 15, "S003": 8}
        
        # Mock clients
        service.timestream_client = Mock()
        service.eventbridge_client = Mock()
        service.eventbridge_client.publish_bus_position_event.side_effect = Exception("EventBridge error")
        
        # Mock bus movement
        position_data = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4680,
            longitude=-3.6890,
            passenger_count=25,
            next_stop_id="S002",
            distance_to_next_stop=300.0,
            speed=30.0
        )
        mock_simulate.return_value = (position_data, [])
        
        # Run simulation - should not raise exception
        try:
            service.simulate_and_write_data()
        except Exception as e:
            self.fail(f"simulate_and_write_data raised exception: {e}")
        
        # Verify Timestream write still succeeded
        service.timestream_client.write_records.assert_called_once()
    
    def test_timestream_record_format(self):
        """Test that Timestream records are formatted correctly."""
        service = BusPositionFeederService(
            config_file=self.config_file,
            database_name=self.database_name,
            table_name=self.table_name,
            time_interval=self.time_interval,
            event_bus_name=self.event_bus_name,
            region_name=self.region_name
        )
        
        # Set up service state
        service.routes = {"L1": self.test_route}
        service.buses = {"B001": self.test_bus}
        service.stop_counts = {"S001": 10, "S002": 15, "S003": 8}
        
        # Mock clients
        service.timestream_client = Mock()
        service.eventbridge_client = Mock()
        
        # Mock bus movement
        with patch('feeders.bus_position_feeder.simulate_bus_movement') as mock_simulate:
            position_data = BusPositionDataPoint(
                bus_id="B001",
                line_id="L1",
                timestamp=datetime.now(),
                latitude=40.4680,
                longitude=-3.6890,
                passenger_count=25,
                next_stop_id="S002",
                distance_to_next_stop=300.0,
                speed=30.0
            )
            mock_simulate.return_value = (position_data, [])
            
            # Run simulation
            service.simulate_and_write_data()
            
            # Get the record that was written
            call_args = service.timestream_client.write_records.call_args
            records = call_args[1]['records']
            record = records[0]
            
            # Verify record structure
            self.assertIn('Dimensions', record)
            self.assertIn('MeasureName', record)
            self.assertIn('MeasureValueType', record)
            self.assertIn('MeasureValues', record)
            self.assertIn('Time', record)
            self.assertIn('TimeUnit', record)
            
            # Verify dimensions
            dimensions = {d['Name']: d['Value'] for d in record['Dimensions']}
            self.assertEqual(dimensions['bus_id'], 'B001')
            self.assertEqual(dimensions['line_id'], 'L1')
            self.assertEqual(dimensions['next_stop_id'], 'S002')
            
            # Verify measure type
            self.assertEqual(record['MeasureValueType'], 'MULTI')
            
            # Verify measure values
            measures = {m['Name']: m for m in record['MeasureValues']}
            self.assertIn('latitude', measures)
            self.assertIn('longitude', measures)
            self.assertIn('passenger_count', measures)
            self.assertIn('distance_to_next_stop', measures)
            self.assertIn('speed', measures)
            
            # Verify types
            self.assertEqual(measures['latitude']['Type'], 'DOUBLE')
            self.assertEqual(measures['longitude']['Type'], 'DOUBLE')
            self.assertEqual(measures['passenger_count']['Type'], 'BIGINT')
            self.assertEqual(measures['distance_to_next_stop']['Type'], 'DOUBLE')
            self.assertEqual(measures['speed']['Type'], 'DOUBLE')


if __name__ == '__main__':
    unittest.main()
