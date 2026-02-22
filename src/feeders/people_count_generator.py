"""
People count generation algorithm for the Madrid Bus Real-Time Simulator.

This module implements the core algorithm for generating realistic people counts
at bus stops, coordinating natural arrivals with bus boarding events.
"""

from datetime import datetime
from typing import List

from .daily_patterns import get_time_multiplier, get_base_arrival_rate, poisson_sample


def generate_people_count(
    stop_id: str,
    current_time: datetime,
    previous_count: int,
    bus_arrivals: List['BusArrival'],
    stops_config: dict,
    time_interval_minutes: float = 1.0
) -> int:
    """
    Generate people count based on time of day and bus arrivals.
    
    This function implements the core algorithm for simulating realistic passenger
    counts at bus stops. It combines:
    1. Natural arrivals using daily patterns and Poisson distribution
    2. Departures when buses arrive (people boarding)
    3. Non-negativity constraint (counts never go below zero)
    
    The algorithm follows these steps:
    - Calculate expected arrivals based on time of day and stop characteristics
    - Sample actual arrivals from Poisson distribution for realism
    - Subtract people boarding buses
    - Ensure the result is never negative
    
    Daily pattern multipliers:
    - 06:00-09:00: 1.5x (morning rush)
    - 09:00-12:00: 0.6x (mid-morning lull)
    - 12:00-15:00: 1.2x (lunch period)
    - 15:00-18:00: 0.8x (afternoon)
    - 18:00-21:00: 1.4x (evening rush)
    - 21:00-06:00: 0.2x (night)
    
    Args:
        stop_id: Unique identifier for the bus stop
        current_time: Current simulation time
        previous_count: Number of people at the stop before this update
        bus_arrivals: List of bus arrival events at this stop during the interval
        stops_config: Dictionary mapping stop_id to base_arrival_rate
        time_interval_minutes: Time interval in minutes since last update (default: 1.0)
    
    Returns:
        New people count at the stop (always >= 0)
    
    Raises:
        ValueError: If stop_id is not found in configuration
        ValueError: If previous_count is negative
        ValueError: If time_interval_minutes is not positive
    
    Examples:
        >>> from datetime import datetime
        >>> from dataclasses import dataclass
        >>> 
        >>> @dataclass
        ... class BusArrival:
        ...     bus_id: str
        ...     stop_id: str
        ...     timestamp: datetime
        ...     passengers_boarding: int
        ...     passengers_alighting: int
        >>> 
        >>> stops_config = {"S001": 2.5}
        >>> current_time = datetime(2024, 1, 15, 8, 0)  # Morning rush
        >>> 
        >>> # No bus arrivals - count should increase
        >>> count = generate_people_count("S001", current_time, 5, [], stops_config)
        >>> count >= 5  # Should be at least the previous count
        True
        >>> 
        >>> # Bus arrives and people board
        >>> arrival = BusArrival("B001", "S001", current_time, 10, 0)
        >>> count = generate_people_count("S001", current_time, 15, [arrival], stops_config)
        >>> count >= 0  # Should never be negative
        True
        >>> count <= 15  # Should be less than or equal to previous (people boarded)
        True
    """
    # Validate inputs
    if previous_count < 0:
        raise ValueError(f"previous_count must be non-negative, got {previous_count}")
    
    if time_interval_minutes <= 0:
        raise ValueError(f"time_interval_minutes must be positive, got {time_interval_minutes}")
    
    # Get base arrival rate for this stop (raises ValueError if stop not found)
    base_arrival_rate = get_base_arrival_rate(stop_id, stops_config)
    
    # Get time-of-day multiplier
    time_multiplier = get_time_multiplier(current_time.hour)
    
    # Calculate expected arrivals during this time interval
    # base_arrival_rate is in people per minute
    expected_arrivals = base_arrival_rate * time_multiplier * time_interval_minutes
    
    # Sample actual arrivals from Poisson distribution for realism
    actual_arrivals = poisson_sample(expected_arrivals)
    
    # Calculate total people boarding buses during this interval
    people_boarding = sum(arrival.passengers_boarding for arrival in bus_arrivals)
    
    # Calculate new count: previous + arrivals - boarding
    # Ensure it never goes negative (max with 0)
    new_count = max(0, previous_count + actual_arrivals - people_boarding)
    
    return new_count
