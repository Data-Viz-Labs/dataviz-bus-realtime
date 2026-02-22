"""
Example usage of the daily patterns module.

This script demonstrates how to use the daily pattern functions to calculate
realistic passenger arrival rates at different times of day.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.feeders.daily_patterns import (
    get_time_multiplier,
    get_base_arrival_rate,
    poisson_sample
)


def main():
    """Demonstrate daily pattern calculations."""
    
    # Example stop configuration
    stops_config = {
        "S001": 2.5,  # Plaza de Castilla - high traffic
        "S002": 1.8,  # Paseo de la Castellana - medium traffic
        "S003": 1.2,  # Residential area - lower traffic
    }
    
    print("=" * 70)
    print("Madrid Bus Real-Time Simulator - Daily Patterns Example")
    print("=" * 70)
    print()
    
    # Example 1: Time multipliers throughout the day
    print("1. Time Multipliers Throughout the Day")
    print("-" * 70)
    time_periods = [
        (7, "Morning Rush"),
        (10, "Mid-Morning"),
        (13, "Lunch Period"),
        (16, "Afternoon"),
        (19, "Evening Rush"),
        (23, "Night"),
    ]
    
    for hour, period_name in time_periods:
        multiplier = get_time_multiplier(hour)
        print(f"  {hour:02d}:00 ({period_name:15s}): {multiplier}x multiplier")
    print()
    
    # Example 2: Base arrival rates for different stops
    print("2. Base Arrival Rates by Stop")
    print("-" * 70)
    for stop_id, rate in stops_config.items():
        print(f"  {stop_id}: {rate} people/minute")
    print()
    
    # Example 3: Calculate expected arrivals for a 5-minute interval
    print("3. Expected Arrivals (5-minute interval)")
    print("-" * 70)
    time_interval_minutes = 5
    
    for stop_id in stops_config.keys():
        print(f"\n  Stop {stop_id}:")
        base_rate = get_base_arrival_rate(stop_id, stops_config)
        
        for hour, period_name in time_periods:
            multiplier = get_time_multiplier(hour)
            expected = base_rate * multiplier * time_interval_minutes
            print(f"    {hour:02d}:00 ({period_name:15s}): {expected:5.1f} people expected")
    print()
    
    # Example 4: Simulate actual arrivals using Poisson distribution
    print("4. Simulated Actual Arrivals (Poisson Distribution)")
    print("-" * 70)
    print("  Simulating 10 intervals at Plaza de Castilla during morning rush:")
    print()
    
    stop_id = "S001"
    hour = 7  # Morning rush
    base_rate = get_base_arrival_rate(stop_id, stops_config)
    multiplier = get_time_multiplier(hour)
    expected = base_rate * multiplier * time_interval_minutes
    
    print(f"  Expected arrivals per interval: {expected:.1f}")
    print(f"  Actual arrivals (10 samples):")
    
    import random
    random.seed(42)  # For reproducibility
    
    total_arrivals = 0
    for i in range(10):
        actual = poisson_sample(expected)
        total_arrivals += actual
        print(f"    Interval {i+1:2d}: {actual:2d} people")
    
    avg_arrivals = total_arrivals / 10
    print(f"\n  Average: {avg_arrivals:.1f} people per interval")
    print(f"  (Close to expected: {expected:.1f})")
    print()
    
    # Example 5: Full day simulation for one stop
    print("5. Full Day Simulation (hourly totals)")
    print("-" * 70)
    print(f"  Stop: S001 (Plaza de Castilla)")
    print(f"  Base rate: {stops_config['S001']} people/minute")
    print()
    
    random.seed(42)
    daily_total = 0
    
    for hour in range(24):
        multiplier = get_time_multiplier(hour)
        # Simulate 12 five-minute intervals per hour
        hourly_total = 0
        for _ in range(12):
            expected = stops_config['S001'] * multiplier * 5
            actual = poisson_sample(expected)
            hourly_total += actual
        
        daily_total += hourly_total
        print(f"  {hour:02d}:00-{hour+1:02d}:00: {hourly_total:4d} people (multiplier: {multiplier}x)")
    
    print(f"\n  Daily Total: {daily_total} people")
    print()
    
    print("=" * 70)
    print("Example complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()

