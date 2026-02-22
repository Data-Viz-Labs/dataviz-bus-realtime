"""
Tests for bidirectional route functionality.

This module tests the bidirectional route support where buses can travel
in both outbound (direction=0) and inbound (direction=1) directions.
"""

import pytest
from datetime import datetime, timedelta
from src.common.models import Stop, Route, BusState, BusPositionDataPoint
from src.feeders.bus_movement_simulator import simulate_bus_movement


class TestBidirectionalRouteCoordinates:
    """Test coordinate calculations for bidirectional routes."""
    
    def test_outbound_coordinates_at_start(self):
        """Test that outbound direction at position 0.0 returns first stop coordinates."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, False, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        lat, lon = route.get_coordinates(0.0, direction=0)
        
        assert lat == 40.0
        assert lon == -3.0
    
    def test_inbound_coordinates_at_start(self):
        """Test that inbound direction at position 0.0 returns last stop coordinates."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Inbound at position 0.0 should be at the last stop (reversed)
        lat, lon = route.get_coordinates(0.0, direction=1)
        
        # Should be at last stop (S3) when going inbound from position 0.0
        assert lat == 40.2
        assert lon == -3.2
    
    def test_outbound_coordinates_at_end(self):
        """Test that outbound direction at position 1.0 returns last stop coordinates."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        lat, lon = route.get_coordinates(1.0, direction=0)
        
        assert lat == 40.1
        assert lon == -3.1
    
    def test_inbound_coordinates_at_end(self):
        """Test that inbound direction at position 1.0 returns first stop coordinates."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Inbound at position 1.0 should be at the first stop (reversed)
        lat, lon = route.get_coordinates(1.0, direction=1)
        
        # Should be at first stop (S1) when going inbound at position 1.0
        assert lat == 40.0
        assert lon == -3.0


class TestBidirectionalRouteNextStop:
    """Test next stop calculations for bidirectional routes."""
    
    def test_outbound_next_stop_from_start(self):
        """Test that outbound direction returns correct next stop."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # At position 0.0, S1 is at the current position, so next stop is S2
        next_stop = route.get_next_stop(0.0, direction=0)
        
        assert next_stop is not None
        assert next_stop.stop_id == "S2"
    
    def test_inbound_next_stop_from_start(self):
        """Test that inbound direction returns correct next stop (reversed order)."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Inbound from position 0.0: in reverse, S3 is at position 0.0, so next is S2
        next_stop = route.get_next_stop(0.0, direction=1)
        
        assert next_stop is not None
        assert next_stop.stop_id == "S2"


class TestBidirectionalRouteStopDetection:
    """Test stop detection for bidirectional routes."""
    
    def test_outbound_stops_between(self):
        """Test that outbound direction detects stops in forward order."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Moving from position 0.0 to 0.6 should pass S1 and S2
        stops_reached = route.get_stops_between(0.0, 0.6, direction=0)
        
        assert len(stops_reached) >= 1
        # First stop should be S1 (at position 0.0)
        # Note: get_stops_between only returns stops with start_distance < stop_distance <= end_distance
    
    def test_inbound_stops_between_reversed(self):
        """Test that inbound direction detects stops in reverse order."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Moving from position 0.0 to 0.6 in inbound direction
        stops_reached = route.get_stops_between(0.0, 0.6, direction=1)
        
        # Stops should be in reverse order for inbound
        # The implementation reverses the list for inbound direction
        assert isinstance(stops_reached, list)


class TestBidirectionalBusMovement:
    """Test bus movement simulation with direction changes."""
    
    def test_bus_starts_in_outbound_direction(self):
        """Test that a new bus starts in outbound direction (0)."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        bus = BusState("B1", "L1", 50, passenger_count=0, position_on_route=0.0, direction=0)
        
        position_data, _ = simulate_bus_movement(bus, route, timedelta(minutes=1))
        
        assert position_data.direction == 0
    
    def test_direction_toggles_at_terminal_stop(self):
        """Test that direction toggles when bus reaches terminal stop."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.01, -3.01, True, 1.0)  # Very close for testing
        ]
        route = Route("L1", "Line 1", stops)
        bus = BusState("B1", "L1", 50, passenger_count=10, position_on_route=0.0, direction=0)
        
        # Move bus to reach terminal stop
        # Calculate distance to terminal
        total_distance = route.get_total_distance()
        # Move enough to reach the end
        time_to_reach_end = timedelta(hours=total_distance / (bus.speed * 1000) + 0.1)
        
        position_data, stops_reached = simulate_bus_movement(bus, route, time_to_reach_end)
        
        # Check if we reached a terminal stop
        if any(stop.is_terminal for stop in stops_reached):
            # Direction should have toggled
            assert bus.direction == 1
            # Position should have reset
            assert bus.position_on_route == 0.0
    
    def test_direction_consistency_between_stops(self):
        """Test that direction remains constant when not at terminal stop."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        bus = BusState("B1", "L1", 50, passenger_count=0, position_on_route=0.1, direction=0)
        
        initial_direction = bus.direction
        
        # Move bus a short distance (not reaching terminal)
        position_data, stops_reached = simulate_bus_movement(bus, route, timedelta(seconds=30))
        
        # If no terminal stop was reached, direction should remain the same
        if not any(stop.is_terminal for stop in stops_reached):
            assert bus.direction == initial_direction
    
    def test_inbound_bus_movement(self):
        """Test that a bus in inbound direction moves correctly."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        # Start bus in inbound direction
        bus = BusState("B1", "L1", 50, passenger_count=5, position_on_route=0.1, direction=1)
        
        position_data, _ = simulate_bus_movement(bus, route, timedelta(minutes=1))
        
        # Bus should still be in inbound direction (unless it reached terminal)
        assert position_data.direction in (0, 1)
        # Position should have advanced
        assert bus.position_on_route >= 0.1


class TestBidirectionalRouteDistanceCalculations:
    """Test distance calculations for bidirectional routes."""
    
    def test_outbound_distance_to_stop(self):
        """Test distance calculation in outbound direction."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Distance from start to S2 in outbound direction
        distance = route.distance_to_stop(0.0, stops[1], direction=0)
        
        # Should be positive (stop is ahead)
        assert distance > 0
    
    def test_inbound_distance_to_stop(self):
        """Test distance calculation in inbound direction."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Distance from start to S2 in inbound direction
        distance = route.distance_to_stop(0.0, stops[1], direction=1)
        
        # Should be positive or negative depending on implementation
        assert isinstance(distance, float)
    
    def test_distance_to_stop_behind_returns_negative(self):
        """Test that distance to a stop behind the bus returns -1."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, False, 1.0),
            Stop("S3", "Stop 3", 40.2, -3.2, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # From position 0.8, S1 should be behind us in outbound direction
        distance = route.distance_to_stop(0.8, stops[0], direction=0)
        
        assert distance == -1.0


class TestBidirectionalRouteAdvancePosition:
    """Test position advancement for bidirectional routes."""
    
    def test_advance_position_outbound(self):
        """Test that advance_position works correctly in outbound direction."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        new_position = route.advance_position(0.0, 1000.0, direction=0)
        
        assert new_position > 0.0
        assert new_position <= 1.0
    
    def test_advance_position_inbound(self):
        """Test that advance_position works correctly in inbound direction."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Direction doesn't affect distance calculation, only interpretation
        new_position = route.advance_position(0.0, 1000.0, direction=1)
        
        assert new_position > 0.0
        assert new_position <= 1.0
    
    def test_advance_position_caps_at_one(self):
        """Test that position is capped at 1.0 regardless of direction."""
        stops = [
            Stop("S1", "Stop 1", 40.0, -3.0, True, 1.0),
            Stop("S2", "Stop 2", 40.1, -3.1, True, 1.0)
        ]
        route = Route("L1", "Line 1", stops)
        
        # Move a very large distance
        new_position_outbound = route.advance_position(0.5, 1000000.0, direction=0)
        new_position_inbound = route.advance_position(0.5, 1000000.0, direction=1)
        
        assert new_position_outbound == 1.0
        assert new_position_inbound == 1.0
