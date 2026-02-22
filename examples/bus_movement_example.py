"""
Example demonstrating bus movement simulation.

This example shows how to use the bus movement simulator to:
- Simulate bus movement along a route over time
- Detect when buses reach stops
- Track position, speed, and passenger count
"""

import sys
from pathlib import Path
from datetime import timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.common.models import Route, Stop, BusState
from src.feeders.bus_movement_simulator import (
    simulate_bus_movement,
    calculate_alighting,
    calculate_boarding
)


def main():
    """Demonstrate bus movement simulation."""
    
    # Create a route with 4 stops
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
            name="Gran Vía",
            latitude=40.4400,
            longitude=-3.6950,
            is_terminal=False,
            base_arrival_rate=2.2
        ),
        Stop(
            stop_id="S004",
            name="Atocha",
            latitude=40.4300,
            longitude=-3.7000,
            is_terminal=True,
            base_arrival_rate=2.0
        ),
    ]
    
    route = Route(
        line_id="L1",
        name="Plaza de Castilla - Atocha",
        stops=stops
    )
    
    # Create a bus starting at the beginning
    bus = BusState(
        bus_id="B001",
        line_id="L1",
        capacity=80,
        passenger_count=15,
        position_on_route=0.0,
        speed=30.0,  # 30 km/h average speed
        at_stop=False
    )
    
    print("=" * 70)
    print("Bus Movement Simulation Example")
    print("=" * 70)
    print(f"\nRoute: {route.name} ({route.line_id})")
    print(f"Total distance: {route.get_total_distance():.2f} meters")
    print(f"\nBus: {bus.bus_id}")
    print(f"Speed: {bus.speed} km/h")
    print(f"Initial passengers: {bus.passenger_count}")
    print(f"Capacity: {bus.capacity}")
    
    print("\n" + "-" * 70)
    print("Simulating bus movement (1-minute intervals):")
    print("-" * 70)
    
    # Simulate movement for 20 minutes
    time_interval = timedelta(minutes=1)
    
    for minute in range(20):
        # Simulate movement
        position_data, stops_reached = simulate_bus_movement(
            bus,
            route,
            time_interval
        )
        
        # Display current state
        print(f"\nMinute {minute + 1}:")
        print(f"  Position: {bus.position_on_route:.3f} ({bus.position_on_route * 100:.1f}%)")
        print(f"  Coordinates: ({position_data.latitude:.4f}, {position_data.longitude:.4f})")
        print(f"  Passengers: {position_data.passenger_count}")
        print(f"  Next stop: {position_data.next_stop_id}")
        print(f"  Distance to next stop: {position_data.distance_to_next_stop:.2f}m")
        
        # Check if we reached any stops
        if stops_reached:
            print(f"  ** ARRIVED AT: {', '.join(s.name for s in stops_reached)} **")
            
            # Demonstrate boarding/alighting logic
            for stop in stops_reached:
                # Simulate people waiting at stop (for demonstration)
                people_at_stop = 15 if not stop.is_terminal else 25
                
                # Calculate alighting
                alighting = calculate_alighting(bus.passenger_count, stop.is_terminal)
                print(f"     - Passengers alighting: {alighting}")
                
                # Update passenger count after alighting
                bus.passenger_count -= alighting
                
                # Calculate available capacity
                available_capacity = bus.capacity - bus.passenger_count
                
                # Calculate boarding
                boarding = calculate_boarding(people_at_stop, available_capacity)
                print(f"     - People at stop: {people_at_stop}")
                print(f"     - Passengers boarding: {boarding}")
                
                # Update passenger count after boarding
                bus.passenger_count += boarding
                
                print(f"     - New passenger count: {bus.passenger_count}")
        
        # Check if we reached the end
        if bus.position_on_route >= 1.0:
            print(f"\n  Reached terminal stop: {route.stops[-1].name}")
            print(f"  Total travel time: {minute + 1} minutes")
            break
    
    print("\n" + "=" * 70)
    print("Simulation complete!")
    print("=" * 70)
    
    # Summary
    print("\nSummary:")
    print(f"  Final position: {bus.position_on_route:.3f}")
    print(f"  Distance traveled: {bus.position_on_route * route.get_total_distance():.2f}m")
    print(f"  Average speed: {bus.speed} km/h")


if __name__ == "__main__":
    main()
