"""
Configuration loader for the Madrid Bus Real-Time Simulator.

This module provides functionality to load bus lines, stops, and buses from YAML
configuration files and convert them into Route objects.
"""

import yaml
from pathlib import Path
from typing import Dict, List
from .models import Route, Stop, BusState


class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""
    pass


class ConfigLoader:
    """
    Loads and validates bus system configuration from YAML files.
    
    The loader parses lines.yaml files containing bus lines, stops, and buses,
    validates the configuration completeness, and creates Route and BusState objects.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the configuration loader.
        
        Args:
            config_path: Path to the YAML configuration file
            
        Raises:
            ConfigurationError: If the file doesn't exist or can't be read
        """
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        self._raw_config: Dict = {}
        self._routes: List[Route] = []
        self._buses: Dict[str, BusState] = {}
    
    def load(self) -> None:
        """
        Load and parse the YAML configuration file.
        
        Raises:
            ConfigurationError: If the file can't be parsed or is invalid
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._raw_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse YAML: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to read configuration file: {e}")
        
        if not self._raw_config:
            raise ConfigurationError("Configuration file is empty")
        
        if 'lines' not in self._raw_config:
            raise ConfigurationError("Configuration must contain 'lines' key")
        
        if not isinstance(self._raw_config['lines'], list):
            raise ConfigurationError("'lines' must be a list")
        
        if not self._raw_config['lines']:
            raise ConfigurationError("Configuration must contain at least one line")
    
    def parse_routes(self) -> List[Route]:
        """
        Parse routes from the loaded configuration.
        
        Returns:
            List of Route objects
            
        Raises:
            ConfigurationError: If route data is invalid
        """
        if not self._raw_config:
            raise ConfigurationError("Configuration not loaded. Call load() first.")
        
        routes = []
        line_ids_seen = set()
        
        for line_data in self._raw_config['lines']:
            try:
                # Validate required fields
                if 'line_id' not in line_data:
                    raise ConfigurationError("Line missing 'line_id' field")
                if 'name' not in line_data:
                    raise ConfigurationError(f"Line {line_data.get('line_id')} missing 'name' field")
                if 'stops' not in line_data:
                    raise ConfigurationError(f"Line {line_data['line_id']} missing 'stops' field")
                
                line_id = line_data['line_id']
                
                # Check for duplicate line IDs
                if line_id in line_ids_seen:
                    raise ConfigurationError(f"Duplicate line_id: {line_id}")
                line_ids_seen.add(line_id)
                
                # Parse stops
                stops = self._parse_stops(line_data['stops'], line_id)
                
                # Create Route object
                route = Route(
                    line_id=line_id,
                    name=line_data['name'],
                    stops=stops
                )
                
                # Validate the route
                route.validate()
                
                routes.append(route)
                
            except (KeyError, ValueError, TypeError) as e:
                raise ConfigurationError(f"Error parsing line {line_data.get('line_id', 'unknown')}: {e}")
        
        self._routes = routes
        return routes
    
    def _parse_stops(self, stops_data: List[Dict], line_id: str) -> List[Stop]:
        """
        Parse stops from line configuration.
        
        Args:
            stops_data: List of stop dictionaries
            line_id: ID of the line (for error messages)
            
        Returns:
            List of Stop objects
            
        Raises:
            ConfigurationError: If stop data is invalid
        """
        if not isinstance(stops_data, list):
            raise ConfigurationError(f"Line {line_id}: 'stops' must be a list")
        
        if not stops_data:
            raise ConfigurationError(f"Line {line_id}: must have at least one stop")
        
        stops = []
        stop_ids_seen = set()
        
        for stop_data in stops_data:
            # Validate required fields
            required_fields = ['stop_id', 'name', 'latitude', 'longitude', 'is_terminal', 'base_arrival_rate']
            for field in required_fields:
                if field not in stop_data:
                    raise ConfigurationError(
                        f"Line {line_id}: Stop missing required field '{field}'"
                    )
            
            stop_id = stop_data['stop_id']
            
            # Check for duplicate stop IDs within this line
            if stop_id in stop_ids_seen:
                raise ConfigurationError(f"Line {line_id}: Duplicate stop_id: {stop_id}")
            stop_ids_seen.add(stop_id)
            
            # Create Stop object
            try:
                stop = Stop(
                    stop_id=stop_id,
                    name=stop_data['name'],
                    latitude=float(stop_data['latitude']),
                    longitude=float(stop_data['longitude']),
                    is_terminal=bool(stop_data['is_terminal']),
                    base_arrival_rate=float(stop_data['base_arrival_rate'])
                )
                
                # Validate the stop
                stop.validate()
                
                stops.append(stop)
                
            except (ValueError, TypeError) as e:
                raise ConfigurationError(
                    f"Line {line_id}, Stop {stop_id}: Invalid data - {e}"
                )
        
        return stops
    
    def parse_buses(self) -> Dict[str, BusState]:
        """
        Parse buses from the loaded configuration.
        
        Returns:
            Dictionary mapping bus_id to BusState objects
            
        Raises:
            ConfigurationError: If bus data is invalid or routes not parsed yet
        """
        if not self._raw_config:
            raise ConfigurationError("Configuration not loaded. Call load() first.")
        
        if not self._routes:
            raise ConfigurationError("Routes not parsed. Call parse_routes() first.")
        
        buses = {}
        bus_ids_seen = set()
        
        for line_data in self._raw_config['lines']:
            line_id = line_data['line_id']
            
            if 'buses' not in line_data:
                raise ConfigurationError(f"Line {line_id} missing 'buses' field")
            
            if not isinstance(line_data['buses'], list):
                raise ConfigurationError(f"Line {line_id}: 'buses' must be a list")
            
            if not line_data['buses']:
                raise ConfigurationError(f"Line {line_id}: must have at least one bus")
            
            for bus_data in line_data['buses']:
                try:
                    # Validate required fields
                    if 'bus_id' not in bus_data:
                        raise ConfigurationError(f"Line {line_id}: Bus missing 'bus_id' field")
                    if 'capacity' not in bus_data:
                        raise ConfigurationError(f"Line {line_id}: Bus missing 'capacity' field")
                    if 'initial_position' not in bus_data:
                        raise ConfigurationError(f"Line {line_id}: Bus missing 'initial_position' field")
                    
                    bus_id = bus_data['bus_id']
                    
                    # Check for duplicate bus IDs
                    if bus_id in bus_ids_seen:
                        raise ConfigurationError(f"Duplicate bus_id: {bus_id}")
                    bus_ids_seen.add(bus_id)
                    
                    # Create BusState object
                    bus_state = BusState(
                        bus_id=bus_id,
                        line_id=line_id,
                        capacity=int(bus_data['capacity']),
                        passenger_count=0,
                        position_on_route=float(bus_data['initial_position']),
                        speed=30.0,  # Default speed
                        at_stop=False
                    )
                    
                    # Validate the bus state
                    bus_state.validate()
                    
                    buses[bus_id] = bus_state
                    
                except (ValueError, TypeError) as e:
                    raise ConfigurationError(
                        f"Line {line_id}, Bus {bus_data.get('bus_id', 'unknown')}: Invalid data - {e}"
                    )
        
        self._buses = buses
        return buses
    
    def get_routes(self) -> List[Route]:
        """
        Get the parsed routes.
        
        Returns:
            List of Route objects
            
        Raises:
            ConfigurationError: If routes haven't been parsed yet
        """
        if not self._routes:
            raise ConfigurationError("Routes not parsed. Call parse_routes() first.")
        return self._routes
    
    def get_buses(self) -> Dict[str, BusState]:
        """
        Get the parsed buses.
        
        Returns:
            Dictionary mapping bus_id to BusState objects
            
        Raises:
            ConfigurationError: If buses haven't been parsed yet
        """
        if not self._buses:
            raise ConfigurationError("Buses not parsed. Call parse_buses() first.")
        return self._buses
    
    def get_route_by_id(self, line_id: str) -> Route:
        """
        Get a specific route by line ID.
        
        Args:
            line_id: The line ID to search for
            
        Returns:
            The Route object
            
        Raises:
            ConfigurationError: If route not found or routes not parsed
        """
        if not self._routes:
            raise ConfigurationError("Routes not parsed. Call parse_routes() first.")
        
        for route in self._routes:
            if route.line_id == line_id:
                return route
        
        raise ConfigurationError(f"Route not found: {line_id}")
    
    def validate_completeness(self) -> None:
        """
        Validate that the configuration is complete and consistent.
        
        Raises:
            ConfigurationError: If validation fails
        """
        if not self._routes:
            raise ConfigurationError("No routes loaded")
        
        if not self._buses:
            raise ConfigurationError("No buses loaded")
        
        # Verify each line has at least one bus
        line_ids = {route.line_id for route in self._routes}
        buses_per_line = {}
        
        for bus in self._buses.values():
            if bus.line_id not in line_ids:
                raise ConfigurationError(
                    f"Bus {bus.bus_id} references non-existent line: {bus.line_id}"
                )
            buses_per_line[bus.line_id] = buses_per_line.get(bus.line_id, 0) + 1
        
        for line_id in line_ids:
            if line_id not in buses_per_line:
                raise ConfigurationError(f"Line {line_id} has no buses assigned")
        
        # Verify each route has at least one terminal stop
        for route in self._routes:
            if not any(stop.is_terminal for stop in route.stops):
                raise ConfigurationError(f"Line {route.line_id} has no terminal stops")


def load_configuration(config_path: str) -> tuple[List[Route], Dict[str, BusState]]:
    """
    Convenience function to load and parse configuration in one call.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        Tuple of (routes, buses)
        
    Raises:
        ConfigurationError: If loading or validation fails
    """
    loader = ConfigLoader(config_path)
    loader.load()
    routes = loader.parse_routes()
    buses = loader.parse_buses()
    loader.validate_completeness()
    
    return routes, buses
