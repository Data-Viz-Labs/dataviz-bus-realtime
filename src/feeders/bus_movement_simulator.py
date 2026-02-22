"""
Bus movement simulation for the Madrid Bus Real-Time Simulator.

This module implements the core algorithm for simulating bus movement along routes.
It calculates distance traveled, updates position, and detects stops reached during movement.
"""

import random
from datetime import datetime, timedelta
from typing import List, Tuple

from src.common.models import BusState, Route, BusPositionDataPoint, BusArrival, Stop


def simulate_bus_movement(
    bus: BusState,
    route: Route,
    time_delta: timedelta
) -> Tuple[BusPositionDataPoint, List[BusArrival]]:
    """
    Simulate bus movement along route and generate arrivals.
    
    This function implements the core bus movement algorithm:
    1. Calculate distance traveled based on speed and time
    2. Update position along route using Route.advance_position
    3. Detect stops reached during movement using Route.get_stops_between
    4. Return updated position data and list of stops reached
    
    Args:
        bus: Current bus state
        route: Route the bus is traveling on
        time_delta: Time elapsed since last update
    
    Returns:
        Tuple containing:
        - Updated BusPositionDataPoint with new position and coordinates
        - List of BusArrival events (empty if no stops were reached)
    
    Raises:
        ValueError: If bus state or route is invalid
    """
    # Validate inputs
    bus.validate()
    route.validate()
    
    if bus.line_id != route.line_id:
        raise ValueError(f"Bus line_id ({bus.line_id}) does not match route line_id ({route.line_id})")
    
    # Calculate distance traveled in meters
    # speed is in km/h, time_delta is in seconds
    hours_elapsed = time_delta.total_seconds() / 3600
    distance_traveled_meters = bus.speed * 1000 * hours_elapsed
    
    # Store old position to detect stops
    old_position = bus.position_on_route
    
    # Update position along route (capped at 1.0)
    new_position = route.advance_position(old_position, distance_traveled_meters)
    
    # Detect stops reached during movement
    stops_reached = route.get_stops_between(old_position, new_position)
    
    # Create arrival events for stops reached (will be populated by caller)
    # This function only detects which stops were reached, not passenger boarding/alighting
    arrivals: List[BusArrival] = []
    
    # Update bus state
    bus.position_on_route = new_position
    
    # Get current coordinates
    latitude, longitude = route.get_coordinates(new_position)
    
    # Get next stop and distance to it
    next_stop = route.get_next_stop(new_position)
    if next_stop:
        distance_to_next_stop = route.distance_to_stop(new_position, next_stop)
        next_stop_id = next_stop.stop_id
    else:
        # At the end of the route
        distance_to_next_stop = 0.0
        next_stop_id = route.stops[-1].stop_id
    
    # Create position data point
    position_data = BusPositionDataPoint(
        bus_id=bus.bus_id,
        line_id=bus.line_id,
        timestamp=datetime.now(),
        latitude=latitude,
        longitude=longitude,
        passenger_count=bus.passenger_count,
        next_stop_id=next_stop_id,
        distance_to_next_stop=distance_to_next_stop,
        speed=bus.speed
    )
    
    return position_data, stops_reached


def calculate_distance_traveled(speed_kmh: float, time_delta: timedelta) -> float:
    """
    Calculate distance traveled based on speed and time.
    
    Args:
        speed_kmh: Speed in kilometers per hour
        time_delta: Time elapsed
    
    Returns:
        Distance traveled in meters
    
    Raises:
        ValueError: If speed is negative
    """
    if speed_kmh < 0:
        raise ValueError(f"speed_kmh must be non-negative, got {speed_kmh}")
    
    hours_elapsed = time_delta.total_seconds() / 3600
    distance_meters = speed_kmh * 1000 * hours_elapsed
    
    return distance_meters


def calculate_alighting(passenger_count: int, is_terminal: bool) -> int:
    """
    Calculate how many passengers get off the bus at a stop.
    
    At terminal stops, all passengers must alight (everyone gets off).
    At regular stops, a percentage of passengers get off (20-40%).
    
    Args:
        passenger_count: Current number of passengers on the bus
        is_terminal: Whether this is a terminal stop
    
    Returns:
        Number of passengers alighting (getting off)
    
    Raises:
        ValueError: If passenger_count is negative
    """
    if passenger_count < 0:
        raise ValueError(f"passenger_count must be non-negative, got {passenger_count}")
    
    if is_terminal:
        # At terminal stops, everyone gets off
        return passenger_count
    else:
        # At regular stops, 20-40% of passengers get off
        alighting_percentage = random.uniform(0.20, 0.40)
        alighting_count = int(passenger_count * alighting_percentage)
        return alighting_count


def calculate_boarding(people_at_stop: int, available_capacity: int) -> int:
    """
    Calculate how many passengers board the bus at a stop.
    
    Passengers board up to the available capacity of the bus.
    Cannot board more than the number of people waiting at the stop.
    
    Args:
        people_at_stop: Number of people waiting at the stop
        available_capacity: Available space on the bus (capacity - current passengers)
    
    Returns:
        Number of passengers boarding (getting on)
    
    Raises:
        ValueError: If people_at_stop or available_capacity is negative
    """
    if people_at_stop < 0:
        raise ValueError(f"people_at_stop must be non-negative, got {people_at_stop}")
    
    if available_capacity < 0:
        raise ValueError(f"available_capacity must be non-negative, got {available_capacity}")
    
    # Board as many as possible up to available capacity
    # Cannot board more than people waiting at stop
    boarding_count = min(people_at_stop, available_capacity)
    
    return boarding_count
