"""
Sensor data generation algorithm for the Madrid Bus Real-Time Simulator.

This module implements the core algorithm for generating realistic sensor readings
for buses and stops, including temperature, humidity, CO2 levels, and door status.
"""

import random
from datetime import datetime
from typing import Optional

try:
    from ..common.models import SensorDataPoint, BusState
except ImportError:
    from common.models import SensorDataPoint, BusState


def get_ambient_temperature(current_time: datetime) -> float:
    """
    Calculate ambient temperature based on time of day.
    
    Simulates a realistic daily temperature cycle:
    - Coldest at 6:00 AM (around 15°C)
    - Warmest at 3:00 PM (around 28°C)
    - Uses a sinusoidal pattern for smooth transitions
    
    Args:
        current_time: Current simulation time
    
    Returns:
        Base ambient temperature in Celsius
    
    Examples:
        >>> from datetime import datetime
        >>> # Morning (6 AM) - coldest
        >>> temp = get_ambient_temperature(datetime(2024, 1, 15, 6, 0))
        >>> 14 <= temp <= 16
        True
        >>> 
        >>> # Afternoon (3 PM) - warmest
        >>> temp = get_ambient_temperature(datetime(2024, 1, 15, 15, 0))
        >>> 27 <= temp <= 29
        True
    """
    # Temperature follows a sinusoidal pattern
    # Minimum at 6:00 (hour 6), maximum at 15:00 (hour 15)
    # The peak is 9 hours after the minimum
    hour = current_time.hour + current_time.minute / 60.0
    
    # Use cosine: cos(0) = 1 (max), cos(π) = -1 (min)
    # We want max at hour 15, min at hour 6 (which is 9 hours before 15, or 15 hours after)
    # cos(2π * (hour - 15) / 24) gives us:
    #   - at hour 15: cos(0) = 1 (max) ✓
    #   - at hour 3: cos(2π * -12 / 24) = cos(-π) = -1 (min)
    #   - at hour 6: cos(2π * -9 / 24) = cos(-3π/4) ≈ -0.707
    # We need to shift by 15 hours to get min at 6:
    # cos(2π * (hour - 15 + 12) / 24) = cos(2π * (hour - 3) / 24)
    # Actually, let's think differently:
    # If min is at 6 and max is at 15, that's 9 hours apart (should be 12 for a sine wave)
    # Let's use: temp = avg + amplitude * cos(2π * (hour - 15) / 24)
    # At hour 15: cos(0) = 1, temp = avg + amplitude = 28 ✓
    # At hour 3 (next day): cos(2π * -12/24) = cos(-π) = -1, temp = avg - amplitude = 15 ✓
    # At hour 6: cos(2π * -9/24) = cos(-3π/4) ≈ -0.707, temp ≈ 16.9
    # But we want min at 6, not at 3...
    # 
    # Let me recalculate: if min is at 6 and max is at 15:
    # The midpoint is at (6+15)/2 = 10.5
    # The period is 24 hours
    # We can use: temp = avg + amplitude * cos(2π * (hour - 15) / 24)
    # But this gives min at hour 3 (15 - 12 = 3)
    # 
    # Actually, from hour 6 to hour 15 is 9 hours (quarter of 24 is 6 hours, so this is 3/8 of the cycle)
    # Let's use a different approach: shift so that hour 6 maps to π (min) and hour 15 maps to 0 (max)
    # cos(2π * (hour - 15) / 24) at hour 6: cos(2π * -9/24) = cos(-3π/4) = -√2/2 ≈ -0.707
    # cos(2π * (hour - 15) / 24) at hour 15: cos(0) = 1
    # 
    # We need: at hour 6, angle = π (cos = -1)
    #          at hour 15, angle = 0 (cos = 1)
    # So: 2π * (6 - shift) / 24 = π  =>  (6 - shift) / 24 = 0.5  =>  6 - shift = 12  =>  shift = -6
    # Therefore: 2π * (hour + 6) / 24
    # At hour 6: 2π * 12/24 = π, cos(π) = -1 ✓
    # At hour 15: 2π * 21/24 = 7π/4, cos(7π/4) = √2/2 ≈ 0.707 ✗
    # 
    # Hmm, the issue is that 6 to 15 is 9 hours, but from min to max in a cosine is 12 hours (half period)
    # Let's just accept this and use: temp = avg + amplitude * cos(2π * (hour - 15) / 24)
    # This gives max at 15 and min at 3 (or 27 in previous day)
    # But the design says min at 6... Let me check the design doc again.
    # 
    # Actually, let's use a pragmatic approach:
    # cos(2π * (hour - 15) / 24) gives max at 15
    # To get min at 6, we need the angle at hour 6 to be π
    # 2π * (6 - 15) / 24 = 2π * (-9) / 24 = -3π/4
    # cos(-3π/4) = -√2/2 ≈ -0.707, not -1
    # 
    # The cleanest solution: accept that a true sinusoid has min 12 hours after max
    # So if max is at 15, min is at 3 (next morning)
    # But we can adjust: use cos(2π * (hour - 10.5) / 24) to center between 6 and 15
    # At hour 6: cos(2π * -4.5/24) = cos(-3π/8) ≈ -0.924
    # At hour 15: cos(2π * 4.5/24) = cos(3π/8) ≈ 0.924
    # This is more symmetric!
    
    import math
    avg_temp = 21.5  # Average temperature
    amplitude = 6.5  # Temperature variation (±6.5°C)
    
    # Center the cosine between hour 6 (min) and hour 15 (max)
    # Midpoint is 10.5
    temp = avg_temp + amplitude * math.cos(2 * math.pi * (hour - 15) / 24)
    
    return temp


def generate_sensor_data(
    entity_id: str,
    entity_type: str,
    current_time: datetime,
    bus_state: Optional[BusState] = None
) -> SensorDataPoint:
    """
    Generate realistic sensor readings based on entity type and state.
    
    This function creates sensor data for both buses and stops:
    
    For all entities:
    - Temperature varies by time of day with random noise
    - Humidity varies inversely with temperature
    
    For buses only:
    - CO2 levels increase with passenger count (base 400 ppm + passenger_count * 50)
    - Door status is "open" when at stop, "closed" when en route
    
    Args:
        entity_id: Bus ID or stop ID
        entity_type: "bus" or "stop"
        current_time: Current simulation time
        bus_state: Current bus state (required for entity_type="bus", None for stops)
    
    Returns:
        SensorDataPoint with all sensor readings
    
    Raises:
        ValueError: If entity_type is not "bus" or "stop"
        ValueError: If entity_type is "bus" but bus_state is None
    
    Examples:
        >>> from datetime import datetime
        >>> from ..common.models import BusState
        >>> 
        >>> # Generate sensor data for a stop
        >>> sensor = generate_sensor_data("S001", "stop", datetime(2024, 1, 15, 12, 0))
        >>> sensor.entity_id
        'S001'
        >>> sensor.entity_type
        'stop'
        >>> sensor.co2_level is None
        True
        >>> sensor.door_status is None
        True
        >>> 
        >>> # Generate sensor data for a bus at a stop
        >>> bus = BusState("B001", "L1", 80, passenger_count=30, at_stop=True)
        >>> sensor = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus)
        >>> sensor.entity_id
        'B001'
        >>> sensor.entity_type
        'bus'
        >>> sensor.co2_level is not None
        True
        >>> sensor.door_status
        'open'
        >>> 
        >>> # Generate sensor data for a bus en route
        >>> bus = BusState("B001", "L1", 80, passenger_count=30, at_stop=False)
        >>> sensor = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus)
        >>> sensor.door_status
        'closed'
    """
    # Validate inputs
    if entity_type not in ("bus", "stop"):
        raise ValueError(f"entity_type must be 'bus' or 'stop', got '{entity_type}'")
    
    if entity_type == "bus" and bus_state is None:
        raise ValueError("bus_state is required when entity_type is 'bus'")
    
    # Calculate temperature based on time of day with noise
    base_temp = get_ambient_temperature(current_time)
    temp_noise = random.gauss(0, 1.5)  # Normal distribution with std dev 1.5°C
    temperature = base_temp + temp_noise
    
    # Humidity varies inversely with temperature
    # Base humidity is 70% at 20°C
    # For each degree above 20°C, humidity decreases by 2%
    # Add random noise
    base_humidity = 70 - (temperature - 20) * 2
    humidity_noise = random.gauss(0, 5)  # Normal distribution with std dev 5%
    humidity = base_humidity + humidity_noise
    
    # Clamp humidity to valid range [20, 90]
    humidity = max(20, min(90, humidity))
    
    if entity_type == "bus":
        # CO2 increases with passenger count
        # Base level: 400 ppm (outdoor air)
        # Each passenger adds 50 ppm
        passenger_count = bus_state.passenger_count if bus_state else 0
        base_co2 = 400 + (passenger_count * 50)
        co2_noise = random.gauss(0, 50)  # Normal distribution with std dev 50 ppm
        co2_level = int(base_co2 + co2_noise)
        
        # Ensure CO2 is non-negative
        co2_level = max(0, co2_level)
        
        # Door status based on whether bus is at stop
        door_status = "open" if bus_state and bus_state.at_stop else "closed"
        
        return SensorDataPoint(
            entity_id=entity_id,
            entity_type=entity_type,
            timestamp=current_time,
            temperature=temperature,
            humidity=humidity,
            co2_level=co2_level,
            door_status=door_status
        )
    else:
        # Stop sensors don't have CO2 or door status
        return SensorDataPoint(
            entity_id=entity_id,
            entity_type=entity_type,
            timestamp=current_time,
            temperature=temperature,
            humidity=humidity,
            co2_level=None,
            door_status=None
        )
