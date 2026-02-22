"""
Example demonstrating route geometry calculations.

This example shows how to use the Route class to:
- Calculate total route distance
- Advance position along a route
- Get coordinates at any position
- Detect stops between positions
- Find the next stop
- Calculate distance to a stop
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.common.models import Route, Stop


def main():
    """Demonstrate route geometry calculations."""
    
    # Create a simple route with 3 stops
    stops = [
        Stop(
            stop_id="S001",
            name="Plaza de Castilla",
            latitude=40.4657,
            longitude=-3.6886,
            is_terminal=True,
            base_arrival_rate=2.5
        ),
        Stop(
            stop_id="S002",
            name="Paseo de la Castellana",
            latitude=40.4500,
            longitude=-3.6900,
            is_terminal=False,
            base_arrival_rate=1.8
        ),
        Stop(
            stop_id="S003",
            name="Atocha",
            latitude=40.4400,
            longitude=-3.6950,
            is_terminal=True,
            base_arrival_rate=2.0
        ),
    ]
    
    route = Route(
        line_id="L1",
        name="Plaza de Castilla - Atocha",
        stops=stops
    )
    
    print("=" * 60)
    print("Route Geometry Example")
    print("=" * 60)
    print(f"\nRoute: {route.name} ({route.line_id})")
    print(f"Stops: {len(route.stops)}")
    
    # Calculate total distance
    total_distance = route.get_total_distance()
    print(f"\nTotal route distance: {total_distance:.2f} meters ({total_distance/1000:.2f} km)")
    
    # Simulate bus movement
    print("\n" + "-" * 60)
    print("Simulating bus movement:")
    print("-" * 60)
    
    current_position = 0.0
    bus_speed_kmh = 30.0  # km/h
    time_interval_seconds = 60  # 1 minute
    
    for minute in range(10):
        # Calculate distance traveled in this interval
        distance_traveled = (bus_speed_kmh * 1000 / 3600) * time_interval_seconds
        
        # Get current coordinates
        lat, lon = route.get_coordinates(current_position)
        
        # Get next stop
        next_stop = route.get_next_stop(current_position)
        
        # Calculate distance to next stop
        if next_stop:
            distance_to_next = route.distance_to_stop(current_position, next_stop)
            print(f"\nMinute {minute}: Position {current_position:.3f}")
            print(f"  Coordinates: ({lat:.4f}, {lon:.4f})")
            print(f"  Next stop: {next_stop.name} ({distance_to_next:.2f}m away)")
        else:
            print(f"\nMinute {minute}: Position {current_position:.3f}")
            print(f"  Coordinates: ({lat:.4f}, {lon:.4f})")
            print(f"  Reached end of route!")
            break
        
        # Advance position
        old_position = current_position
        current_position = route.advance_position(current_position, distance_traveled)
        
        # Check if we passed any stops
        stops_reached = route.get_stops_between(old_position, current_position)
        if stops_reached:
            print(f"  ** Arrived at: {', '.join(s.name for s in stops_reached)} **")
        
        # Stop if we reached the end
        if current_position >= 1.0:
            print(f"\n  Reached terminal stop: {route.stops[-1].name}")
            break
    
    print("\n" + "=" * 60)
    print("Example complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
