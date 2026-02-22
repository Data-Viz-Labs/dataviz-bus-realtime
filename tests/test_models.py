"""
Unit tests for data models.

Tests validation logic and data integrity checks for all model classes.
"""

import pytest
from datetime import datetime
from src.common.models import (
    PeopleCountDataPoint,
    SensorDataPoint,
    BusPositionDataPoint,
    Stop,
    Route,
    BusState,
    BusArrival,
)


class TestPeopleCountDataPoint:
    """Tests for PeopleCountDataPoint model."""
    
    def test_valid_people_count(self):
        """Test creating a valid people count data point."""
        data_point = PeopleCountDataPoint(
            stop_id="S001",
            timestamp=datetime.now(),
            count=15,
            line_ids=["L1", "L2"]
        )
        data_point.validate()  # Should not raise
    
    def test_negative_count_raises_error(self):
        """Test that negative count raises ValueError."""
        data_point = PeopleCountDataPoint(
            stop_id="S001",
            timestamp=datetime.now(),
            count=-5,
            line_ids=["L1"]
        )
        with pytest.raises(ValueError, match="count must be non-negative"):
            data_point.validate()
    
    def test_empty_stop_id_raises_error(self):
        """Test that empty stop_id raises ValueError."""
        data_point = PeopleCountDataPoint(
            stop_id="",
            timestamp=datetime.now(),
            count=10,
            line_ids=["L1"]
        )
        with pytest.raises(ValueError, match="stop_id cannot be empty"):
            data_point.validate()
    
    def test_empty_line_ids_raises_error(self):
        """Test that empty line_ids raises ValueError."""
        data_point = PeopleCountDataPoint(
            stop_id="S001",
            timestamp=datetime.now(),
            count=10,
            line_ids=[]
        )
        with pytest.raises(ValueError, match="line_ids cannot be empty"):
            data_point.validate()
    
    def test_zero_count_is_valid(self):
        """Test that zero count is valid (boundary case)."""
        data_point = PeopleCountDataPoint(
            stop_id="S001",
            timestamp=datetime.now(),
            count=0,
            line_ids=["L1"]
        )
        data_point.validate()  # Should not raise


class TestSensorDataPoint:
    """Tests for SensorDataPoint model."""
    
    def test_valid_bus_sensor_data(self):
        """Test creating valid bus sensor data."""
        data_point = SensorDataPoint(
            entity_id="B001",
            entity_type="bus",
            timestamp=datetime.now(),
            temperature=22.5,
            humidity=65.0,
            co2_level=800,
            door_status="closed"
        )
        data_point.validate()  # Should not raise
    
    def test_valid_stop_sensor_data(self):
        """Test creating valid stop sensor data."""
        data_point = SensorDataPoint(
            entity_id="S001",
            entity_type="stop",
            timestamp=datetime.now(),
            temperature=18.0,
            humidity=70.0
        )
        data_point.validate()  # Should not raise
    
    def test_invalid_entity_type_raises_error(self):
        """Test that invalid entity_type raises ValueError."""
        data_point = SensorDataPoint(
            entity_id="X001",
            entity_type="invalid",
            timestamp=datetime.now(),
            temperature=20.0,
            humidity=60.0
        )
        with pytest.raises(ValueError, match="entity_type must be 'bus' or 'stop'"):
            data_point.validate()
    
    def test_temperature_out_of_range_raises_error(self):
        """Test that temperature out of range raises ValueError."""
        data_point = SensorDataPoint(
            entity_id="S001",
            entity_type="stop",
            timestamp=datetime.now(),
            temperature=100.0,
            humidity=60.0
        )
        with pytest.raises(ValueError, match="temperature must be between"):
            data_point.validate()
    
    def test_humidity_out_of_range_raises_error(self):
        """Test that humidity out of range raises ValueError."""
        data_point = SensorDataPoint(
            entity_id="S001",
            entity_type="stop",
            timestamp=datetime.now(),
            temperature=20.0,
            humidity=150.0
        )
        with pytest.raises(ValueError, match="humidity must be between"):
            data_point.validate()
    
    def test_invalid_door_status_raises_error(self):
        """Test that invalid door_status raises ValueError."""
        data_point = SensorDataPoint(
            entity_id="B001",
            entity_type="bus",
            timestamp=datetime.now(),
            temperature=20.0,
            humidity=60.0,
            door_status="partially_open"
        )
        with pytest.raises(ValueError, match="door_status must be 'open' or 'closed'"):
            data_point.validate()
    
    def test_stop_with_co2_raises_error(self):
        """Test that stop with CO2 level raises ValueError."""
        data_point = SensorDataPoint(
            entity_id="S001",
            entity_type="stop",
            timestamp=datetime.now(),
            temperature=20.0,
            humidity=60.0,
            co2_level=400
        )
        with pytest.raises(ValueError, match="co2_level should be None for stops"):
            data_point.validate()


class TestBusPositionDataPoint:
    """Tests for BusPositionDataPoint model."""
    
    def test_valid_bus_position(self):
        """Test creating a valid bus position data point."""
        data_point = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4165,
            longitude=-3.7026,
            passenger_count=25,
            next_stop_id="S002",
            distance_to_next_stop=350.5,
            speed=35.0
        )
        data_point.validate()  # Should not raise
    
    def test_negative_passenger_count_raises_error(self):
        """Test that negative passenger count raises ValueError."""
        data_point = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4165,
            longitude=-3.7026,
            passenger_count=-5,
            next_stop_id="S002",
            distance_to_next_stop=350.5,
            speed=35.0
        )
        with pytest.raises(ValueError, match="passenger_count must be non-negative"):
            data_point.validate()
    
    def test_invalid_latitude_raises_error(self):
        """Test that invalid latitude raises ValueError."""
        data_point = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=95.0,
            longitude=-3.7026,
            passenger_count=25,
            next_stop_id="S002",
            distance_to_next_stop=350.5,
            speed=35.0
        )
        with pytest.raises(ValueError, match="latitude must be between"):
            data_point.validate()
    
    def test_invalid_longitude_raises_error(self):
        """Test that invalid longitude raises ValueError."""
        data_point = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4165,
            longitude=-200.0,
            passenger_count=25,
            next_stop_id="S002",
            distance_to_next_stop=350.5,
            speed=35.0
        )
        with pytest.raises(ValueError, match="longitude must be between"):
            data_point.validate()
    
    def test_negative_speed_raises_error(self):
        """Test that negative speed raises ValueError."""
        data_point = BusPositionDataPoint(
            bus_id="B001",
            line_id="L1",
            timestamp=datetime.now(),
            latitude=40.4165,
            longitude=-3.7026,
            passenger_count=25,
            next_stop_id="S002",
            distance_to_next_stop=350.5,
            speed=-10.0
        )
        with pytest.raises(ValueError, match="speed must be non-negative"):
            data_point.validate()


class TestStop:
    """Tests for Stop configuration model."""
    
    def test_valid_stop(self):
        """Test creating a valid stop."""
        stop = Stop(
            stop_id="S001",
            name="Plaza de Castilla",
            latitude=40.4657,
            longitude=-3.6886,
            is_terminal=True,
            base_arrival_rate=2.5
        )
        stop.validate()  # Should not raise
    
    def test_empty_stop_id_raises_error(self):
        """Test that empty stop_id raises ValueError."""
        stop = Stop(
            stop_id="",
            name="Plaza de Castilla",
            latitude=40.4657,
            longitude=-3.6886,
            is_terminal=True,
            base_arrival_rate=2.5
        )
        with pytest.raises(ValueError, match="stop_id cannot be empty"):
            stop.validate()
    
    def test_negative_arrival_rate_raises_error(self):
        """Test that negative arrival rate raises ValueError."""
        stop = Stop(
            stop_id="S001",
            name="Plaza de Castilla",
            latitude=40.4657,
            longitude=-3.6886,
            is_terminal=True,
            base_arrival_rate=-1.0
        )
        with pytest.raises(ValueError, match="base_arrival_rate must be non-negative"):
            stop.validate()


class TestRoute:
    """Tests for Route configuration model."""
    
    def test_valid_route(self):
        """Test creating a valid route."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(
            line_id="L1",
            name="Test Line",
            stops=stops
        )
        route.validate()  # Should not raise
    
    def test_route_with_one_stop_raises_error(self):
        """Test that route with only one stop raises ValueError."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
        ]
        route = Route(
            line_id="L1",
            name="Test Line",
            stops=stops
        )
        with pytest.raises(ValueError, match="route must have at least 2 stops"):
            route.validate()
    
    def test_route_without_terminal_raises_error(self):
        """Test that route without terminal stop raises ValueError."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, False, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(
            line_id="L1",
            name="Test Line",
            stops=stops
        )
        with pytest.raises(ValueError, match="route must have at least one terminal stop"):
            route.validate()
    
    def test_route_with_duplicate_stops_raises_error(self):
        """Test that route with duplicate stop IDs raises ValueError."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S001", "Stop 1 Duplicate", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(
            line_id="L1",
            name="Test Line",
            stops=stops
        )
        with pytest.raises(ValueError, match="route contains duplicate stop IDs"):
            route.validate()
    
    def test_get_total_distance(self):
        """Test calculating total route distance."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        total_distance = route.get_total_distance()
        
        # Should be positive and reasonable (a few km for 3 stops)
        assert total_distance > 0
        assert total_distance < 10000  # Less than 10km
    
    def test_advance_position(self):
        """Test advancing position along route."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Start at beginning
        new_position = route.advance_position(0.0, 500.0)
        
        # Should have moved forward
        assert new_position > 0.0
        assert new_position <= 1.0
    
    def test_advance_position_caps_at_one(self):
        """Test that advancing past the end caps at 1.0."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Advance by a huge distance
        new_position = route.advance_position(0.0, 1000000.0)
        
        # Should cap at 1.0
        assert new_position == 1.0
    
    def test_get_coordinates_at_start(self):
        """Test getting coordinates at start of route."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        lat, lon = route.get_coordinates(0.0)
        
        # Should be at first stop
        assert lat == 40.4657
        assert lon == -3.6886
    
    def test_get_coordinates_at_end(self):
        """Test getting coordinates at end of route."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        lat, lon = route.get_coordinates(1.0)
        
        # Should be at last stop
        assert lat == 40.4500
        assert lon == -3.6900
    
    def test_get_coordinates_midway(self):
        """Test getting coordinates midway through route."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        lat, lon = route.get_coordinates(0.5)
        
        # Should be between the two stops
        assert 40.4500 < lat < 40.4657
        assert -3.6900 < lon < -3.6886
    
    def test_get_stops_between(self):
        """Test getting stops between two positions."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Get stops between start and midway
        stops_reached = route.get_stops_between(0.0, 0.6)
        
        # Should include at least one stop
        assert len(stops_reached) >= 1
        assert all(isinstance(s, Stop) for s in stops_reached)
    
    def test_get_stops_between_no_stops(self):
        """Test getting stops when no stops are between positions."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Get stops in a very small range at the start
        stops_reached = route.get_stops_between(0.0, 0.01)
        
        # Should be empty or minimal
        assert isinstance(stops_reached, list)
    
    def test_get_next_stop(self):
        """Test getting next stop from a position."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Get next stop from start
        next_stop = route.get_next_stop(0.0)
        
        # Should return a stop
        assert next_stop is not None
        assert isinstance(next_stop, Stop)
    
    def test_get_next_stop_at_end(self):
        """Test getting next stop when at end of route."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Get next stop from end
        next_stop = route.get_next_stop(1.0)
        
        # Should return None
        assert next_stop is None
    
    def test_distance_to_stop(self):
        """Test calculating distance to a specific stop."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Calculate distance from start to second stop
        distance = route.distance_to_stop(0.0, stops[1])
        
        # Should be positive
        assert distance > 0
    
    def test_distance_to_stop_behind_returns_negative(self):
        """Test that distance to stop behind current position returns -1."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
            Stop("S003", "Stop 3", 40.4400, -3.6950, True, 2.0),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Calculate distance from end to first stop (behind us)
        distance = route.distance_to_stop(1.0, stops[0])
        
        # Should be -1
        assert distance == -1.0
    
    def test_distance_to_nonexistent_stop_returns_negative(self):
        """Test that distance to non-existent stop returns -1."""
        stops = [
            Stop("S001", "Stop 1", 40.4657, -3.6886, True, 2.5),
            Stop("S002", "Stop 2", 40.4500, -3.6900, False, 1.8),
        ]
        route = Route(line_id="L1", name="Test Line", stops=stops)
        
        # Create a stop not in the route
        other_stop = Stop("S999", "Other Stop", 40.5000, -3.7000, False, 1.0)
        
        # Calculate distance to non-existent stop
        distance = route.distance_to_stop(0.0, other_stop)
        
        # Should be -1
        assert distance == -1.0


class TestBusState:
    """Tests for BusState model."""
    
    def test_valid_bus_state(self):
        """Test creating a valid bus state."""
        state = BusState(
            bus_id="B001",
            line_id="L1",
            capacity=80,
            passenger_count=25,
            position_on_route=0.5,
            speed=30.0,
            at_stop=False
        )
        state.validate()  # Should not raise
    
    def test_passenger_count_exceeds_capacity_raises_error(self):
        """Test that passenger count exceeding capacity raises ValueError."""
        state = BusState(
            bus_id="B001",
            line_id="L1",
            capacity=80,
            passenger_count=100
        )
        with pytest.raises(ValueError, match="passenger_count .* exceeds capacity"):
            state.validate()
    
    def test_invalid_position_raises_error(self):
        """Test that position outside [0, 1] raises ValueError."""
        state = BusState(
            bus_id="B001",
            line_id="L1",
            capacity=80,
            position_on_route=1.5
        )
        with pytest.raises(ValueError, match="position_on_route must be between 0.0 and 1.0"):
            state.validate()
    
    def test_negative_capacity_raises_error(self):
        """Test that negative capacity raises ValueError."""
        state = BusState(
            bus_id="B001",
            line_id="L1",
            capacity=-10
        )
        with pytest.raises(ValueError, match="capacity must be positive"):
            state.validate()


class TestBusArrival:
    """Tests for BusArrival event model."""
    
    def test_valid_bus_arrival(self):
        """Test creating a valid bus arrival event."""
        arrival = BusArrival(
            bus_id="B001",
            stop_id="S002",
            timestamp=datetime.now(),
            passengers_boarding=10,
            passengers_alighting=5
        )
        arrival.validate()  # Should not raise
    
    def test_negative_boarding_raises_error(self):
        """Test that negative boarding count raises ValueError."""
        arrival = BusArrival(
            bus_id="B001",
            stop_id="S002",
            timestamp=datetime.now(),
            passengers_boarding=-5,
            passengers_alighting=5
        )
        with pytest.raises(ValueError, match="passengers_boarding must be non-negative"):
            arrival.validate()
    
    def test_negative_alighting_raises_error(self):
        """Test that negative alighting count raises ValueError."""
        arrival = BusArrival(
            bus_id="B001",
            stop_id="S002",
            timestamp=datetime.now(),
            passengers_boarding=10,
            passengers_alighting=-3
        )
        with pytest.raises(ValueError, match="passengers_alighting must be non-negative"):
            arrival.validate()
    
    def test_zero_passengers_is_valid(self):
        """Test that zero passengers boarding/alighting is valid."""
        arrival = BusArrival(
            bus_id="B001",
            stop_id="S002",
            timestamp=datetime.now(),
            passengers_boarding=0,
            passengers_alighting=0
        )
        arrival.validate()  # Should not raise
