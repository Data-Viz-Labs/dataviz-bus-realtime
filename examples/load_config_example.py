"""
Example script demonstrating how to use the configuration loader.

This script loads the lines.yaml configuration file and displays
information about the loaded routes and buses.
"""

import sys
from pathlib import Path

# Add parent directory to path to import src module
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.common.config_loader import load_configuration, ConfigurationError


def main():
    """Load and display configuration information."""
    # Get path to configuration file
    config_path = Path(__file__).parent.parent / "data" / "lines.yaml"
    
    print(f"Loading configuration from: {config_path}")
    print("-" * 60)
    
    try:
        # Load configuration
        routes, buses = load_configuration(str(config_path))
        
        print(f"\n✓ Successfully loaded {len(routes)} routes and {len(buses)} buses\n")
        
        # Display route information
        print("ROUTES:")
        print("=" * 60)
        for route in routes:
            print(f"\nLine {route.line_id}: {route.name}")
            print(f"  Stops: {len(route.stops)}")
            
            # Show terminal stops
            terminal_stops = [s for s in route.stops if s.is_terminal]
            print(f"  Terminal stops: {', '.join(s.name for s in terminal_stops)}")
            
            # Show all stops
            print(f"  Route:")
            for i, stop in enumerate(route.stops, 1):
                terminal_marker = " [TERMINAL]" if stop.is_terminal else ""
                print(f"    {i}. {stop.name}{terminal_marker}")
                print(f"       Location: ({stop.latitude:.4f}, {stop.longitude:.4f})")
                print(f"       Base arrival rate: {stop.base_arrival_rate} people/min")
        
        # Display bus information
        print("\n\nBUSES:")
        print("=" * 60)
        
        # Group buses by line
        buses_by_line = {}
        for bus_id, bus in buses.items():
            if bus.line_id not in buses_by_line:
                buses_by_line[bus.line_id] = []
            buses_by_line[bus.line_id].append(bus)
        
        for line_id in sorted(buses_by_line.keys()):
            line_buses = buses_by_line[line_id]
            print(f"\nLine {line_id}: {len(line_buses)} buses")
            for bus in sorted(line_buses, key=lambda b: b.bus_id):
                print(f"  {bus.bus_id}:")
                print(f"    Capacity: {bus.capacity} passengers")
                print(f"    Initial position: {bus.position_on_route:.2%} along route")
                print(f"    Speed: {bus.speed} km/h")
        
        # Summary statistics
        print("\n\nSUMMARY:")
        print("=" * 60)
        total_stops = sum(len(route.stops) for route in routes)
        total_capacity = sum(bus.capacity for bus in buses.values())
        avg_stops_per_line = total_stops / len(routes)
        avg_buses_per_line = len(buses) / len(routes)
        
        print(f"Total lines: {len(routes)}")
        print(f"Total stops: {total_stops}")
        print(f"Total buses: {len(buses)}")
        print(f"Total capacity: {total_capacity} passengers")
        print(f"Average stops per line: {avg_stops_per_line:.1f}")
        print(f"Average buses per line: {avg_buses_per_line:.1f}")
        
    except ConfigurationError as e:
        print(f"\n✗ Configuration error: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
