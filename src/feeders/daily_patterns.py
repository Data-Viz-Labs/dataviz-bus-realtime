"""
Daily pattern logic for the Madrid Bus Real-Time Simulator.

This module provides functions to calculate time-based multipliers for passenger
arrival rates and to simulate realistic arrival patterns using Poisson distribution.
"""

import random
from typing import Dict


def get_time_multiplier(hour: int) -> float:
    """
    Get the passenger arrival rate multiplier for a given hour of the day.
    
    The multipliers reflect typical daily patterns in Madrid:
    - Morning rush (06:00-09:00): 1.5x
    - Mid-morning lull (09:00-12:00): 0.6x
    - Lunch period (12:00-15:00): 1.2x
    - Afternoon (15:00-18:00): 0.8x
    - Evening rush (18:00-21:00): 1.4x
    - Night (21:00-06:00): 0.2x
    
    Args:
        hour: Hour of the day (0-23)
    
    Returns:
        Multiplier to apply to base arrival rate
    
    Raises:
        ValueError: If hour is not in range 0-23
    
    Examples:
        >>> get_time_multiplier(7)  # Morning rush
        1.5
        >>> get_time_multiplier(10)  # Mid-morning
        0.6
        >>> get_time_multiplier(23)  # Night
        0.2
    """
    if not (0 <= hour <= 23):
        raise ValueError(f"hour must be between 0 and 23, got {hour}")
    
    # Morning rush: 06:00-09:00
    if 6 <= hour < 9:
        return 1.5
    
    # Mid-morning lull: 09:00-12:00
    if 9 <= hour < 12:
        return 0.6
    
    # Lunch period: 12:00-15:00
    if 12 <= hour < 15:
        return 1.2
    
    # Afternoon: 15:00-18:00
    if 15 <= hour < 18:
        return 0.8
    
    # Evening rush: 18:00-21:00
    if 18 <= hour < 21:
        return 1.4
    
    # Night: 21:00-06:00
    return 0.2


def get_base_arrival_rate(stop_id: str, stops_config: Dict[str, float]) -> float:
    """
    Get the base arrival rate for a specific bus stop.
    
    Args:
        stop_id: Unique identifier for the bus stop
        stops_config: Dictionary mapping stop_id to base_arrival_rate
    
    Returns:
        Base arrival rate in people per minute
    
    Raises:
        ValueError: If stop_id is not found in configuration
    
    Examples:
        >>> config = {"S001": 2.5, "S002": 1.8}
        >>> get_base_arrival_rate("S001", config)
        2.5
    """
    if stop_id not in stops_config:
        raise ValueError(f"Stop {stop_id} not found in configuration")
    
    return stops_config[stop_id]


def poisson_sample(lambda_param: float) -> int:
    """
    Generate a random sample from a Poisson distribution.
    
    The Poisson distribution models the number of events occurring in a fixed
    interval when events occur independently at a constant average rate.
    This is ideal for simulating passenger arrivals at bus stops.
    
    Args:
        lambda_param: Expected value (mean) of the distribution
    
    Returns:
        Random integer from Poisson distribution
    
    Raises:
        ValueError: If lambda_param is negative
    
    Examples:
        >>> random.seed(42)
        >>> poisson_sample(3.0)  # Expected ~3 arrivals
        2
    """
    if lambda_param < 0:
        raise ValueError(f"lambda_param must be non-negative, got {lambda_param}")
    
    # Handle edge case: if lambda is 0, always return 0
    if lambda_param == 0:
        return 0
    
    # Use Knuth's algorithm for Poisson sampling
    # This is efficient for small to moderate lambda values
    L = 2.718281828459045 ** (-lambda_param)  # e^(-lambda)
    k = 0
    p = 1.0
    
    while p > L:
        k += 1
        p *= random.random()
    
    return k - 1

