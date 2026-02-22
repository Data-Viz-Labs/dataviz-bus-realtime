"""
Data models for the Madrid Bus Real-Time Simulator.

This module contains dataclasses for time series data points and configuration classes
for bus system entities. All models include validation methods to ensure data integrity.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple
import math


# Time Series Data Point Models

@dataclass
class PeopleCountDataPoint:
    """
    Represents a people count measurement at a bus stop.
    
    Attributes:
        stop_id: Unique identifier for the bus stop
        timestamp: Time when the count was recorded
        count: Number of people at the stop
        line_ids: List of bus lines that serve this stop
    """
    stop_id: str
    timestamp: datetime
    count: int
    line_ids: List[str]
    
    def validate(self) -> None:
        """
        Validate data integrity.
        
        Raises:
            ValueError: If validation fails
        """
        if not self.stop_id:
            raise ValueError("stop_id cannot be empty")
        if self.count < 0:
            raise ValueError(f"count must be non-negative, got {self.count}")
        if not self.line_ids:
            raise ValueError("line_ids cannot be empty")
        if not all(isinstance(line_id, str) and line_id for line_id in self.line_ids):
            raise ValueError("All line_ids must be non-empty strings")


@dataclass
class SensorDataPoint:
    """
    Represents sensor readings from a bus or stop.
    
    Attributes:
        entity_id: Bus ID or stop ID
        entity_type: "bus" or "stop"
        timestamp: Time when the reading was recorded
        temperature: Temperature in Celsius
        humidity: Humidity percentage (0-100)
        co2_level: CO2 level in ppm (buses only, None for stops)
        door_status: "open" or "closed" (buses only, None for stops)
    """
    entity_id: str
    entity_type: str
    timestamp: datetime
    temperature: float
    humidity: float
    co2_level: Optional[int] = None
    door_status: Optional[str] = None
    
    def validate(self) -> None:
        """
        Validate data integrity.
        
        Raises:
            ValueError: If validation fails
        """
        if not self.entity_id:
            raise ValueError("entity_id cannot be empty")
        if self.entity_type not in ("bus", "stop"):
            raise ValueError(f"entity_type must be 'bus' or 'stop', got '{self.entity_type}'")
        if not (-50 <= self.temperature <= 60):
            raise ValueError(f"temperature must be between -50 and 60°C, got {self.temperature}")
        if not (0 <= self.humidity <= 100):
            raise ValueError(f"humidity must be between 0 and 100%, got {self.humidity}")
        
        # Bus-specific validations
        if self.entity_type == "bus":
            if self.co2_level is not None and self.co2_level < 0:
                raise ValueError(f"co2_level must be non-negative, got {self.co2_level}")
            if self.door_status is not None and self.door_status not in ("open", "closed"):
                raise ValueError(f"door_status must be 'open' or 'closed', got '{self.door_status}'")
        
        # Stop-specific validations
        if self.entity_type == "stop":
            if self.co2_level is not None:
                raise ValueError("co2_level should be None for stops")
            if self.door_status is not None:
                raise ValueError("door_status should be None for stops")


@dataclass
class BusPositionDataPoint:
    """
    Represents a bus position on its route.
    
    Attributes:
        bus_id: Unique identifier for the bus
        line_id: Bus line this bus operates on
        timestamp: Time when the position was recorded
        latitude: Current latitude
        longitude: Current longitude
        passenger_count: Current number of passengers on the bus
        next_stop_id: Next stop on the route
        distance_to_next_stop: Distance to next stop in meters
        speed: Current speed in km/h
        direction: Route direction (0 = outbound, 1 = inbound/return)
    """
    bus_id: str
    line_id: str
    timestamp: datetime
    latitude: float
    longitude: float
    passenger_count: int
    next_stop_id: str
    distance_to_next_stop: float
    speed: float
    direction: int = 0
    
    def validate(self) -> None:
        """
        Validate data integrity.
        
        Raises:
            ValueError: If validation fails
        """
        if not self.bus_id:
            raise ValueError("bus_id cannot be empty")
        if not self.line_id:
            raise ValueError("line_id cannot be empty")
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"latitude must be between -90 and 90, got {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"longitude must be between -180 and 180, got {self.longitude}")
        if self.passenger_count < 0:
            raise ValueError(f"passenger_count must be non-negative, got {self.passenger_count}")
        if not self.next_stop_id:
            raise ValueError("next_stop_id cannot be empty")
        if self.distance_to_next_stop < 0:
            raise ValueError(f"distance_to_next_stop must be non-negative, got {self.distance_to_next_stop}")
        if self.speed < 0:
            raise ValueError(f"speed must be non-negative, got {self.speed}")
        if self.direction not in (0, 1):
            raise ValueError(f"direction must be 0 (outbound) or 1 (inbound), got {self.direction}")


# Configuration and State Models

@dataclass
class Stop:
    """
    Represents a bus stop configuration.
    
    Attributes:
        stop_id: Unique identifier for the stop
        name: Human-readable name of the stop
        latitude: Stop latitude
        longitude: Stop longitude
        is_terminal: Whether this is a terminal stop
        base_arrival_rate: Base rate of people arriving per minute
    """
    stop_id: str
    name: str
    latitude: float
    longitude: float
    is_terminal: bool
    base_arrival_rate: float
    
    def validate(self) -> None:
        """
        Validate stop configuration.
        
        Raises:
            ValueError: If validation fails
        """
        if not self.stop_id:
            raise ValueError("stop_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"latitude must be between -90 and 90, got {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"longitude must be between -180 and 180, got {self.longitude}")
        if self.base_arrival_rate < 0:
            raise ValueError(f"base_arrival_rate must be non-negative, got {self.base_arrival_rate}")


@dataclass
class Route:
    """
    Represents a bus line route with stops.
    
    Attributes:
        line_id: Unique identifier for the line
        name: Human-readable name of the line
        stops: List of stops on this route in order
    """
    line_id: str
    name: str
    stops: List[Stop]
    _total_distance: Optional[float] = field(default=None, init=False, repr=False)
    _segment_distances: Optional[List[float]] = field(default=None, init=False, repr=False)
    
    def validate(self) -> None:
        """
        Validate route configuration.
        
        Raises:
            ValueError: If validation fails
        """
        if not self.line_id:
            raise ValueError("line_id cannot be empty")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.stops:
            raise ValueError("stops cannot be empty")
        if len(self.stops) < 2:
            raise ValueError(f"route must have at least 2 stops, got {len(self.stops)}")
        
        # Validate all stops
        for stop in self.stops:
            stop.validate()
        
        # Check for duplicate stop IDs
        stop_ids = [stop.stop_id for stop in self.stops]
        if len(stop_ids) != len(set(stop_ids)):
            raise ValueError("route contains duplicate stop IDs")
        
        # Ensure at least one terminal stop
        if not any(stop.is_terminal for stop in self.stops):
            raise ValueError("route must have at least one terminal stop")
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two coordinates using Haversine formula.
        
        Args:
            lat1: Latitude of first point
            lon1: Longitude of first point
            lat2: Latitude of second point
            lon2: Longitude of second point
        
        Returns:
            Distance in meters
        """
        # Earth radius in meters
        R = 6371000
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = math.sin(delta_lat / 2) ** 2 + \
            math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def _ensure_distances_calculated(self) -> None:
        """Calculate and cache segment distances if not already done."""
        if self._segment_distances is None:
            self._segment_distances = []
            for i in range(len(self.stops) - 1):
                distance = self._calculate_distance(
                    self.stops[i].latitude,
                    self.stops[i].longitude,
                    self.stops[i + 1].latitude,
                    self.stops[i + 1].longitude
                )
                self._segment_distances.append(distance)
            self._total_distance = sum(self._segment_distances)
    
    def get_total_distance(self) -> float:
        """
        Get the total distance of the route in meters.
        
        Returns:
            Total route distance in meters
        """
        self._ensure_distances_calculated()
        return self._total_distance
    
    def advance_position(self, current_position: float, distance_meters: float, direction: int = 0) -> float:
        """
        Calculate new position after moving a distance along the route.
        
        Args:
            current_position: Current position (0.0 = start, 1.0 = end)
            distance_meters: Distance to travel in meters
            direction: Route direction (0 = outbound, 1 = inbound/return)
        
        Returns:
            New position (0.0 to 1.0), capped at 1.0
        """
        self._ensure_distances_calculated()
        
        # Convert position to absolute distance
        current_distance = current_position * self._total_distance
        
        # Add the distance traveled (direction doesn't affect distance calculation)
        new_distance = current_distance + distance_meters
        
        # Convert back to normalized position, capped at 1.0
        new_position = min(1.0, new_distance / self._total_distance)
        
        return new_position
    
    def get_coordinates(self, position: float, direction: int = 0) -> Tuple[float, float]:
        """
        Get latitude and longitude for a position on the route.
        
        Args:
            position: Position on route (0.0 = start, 1.0 = end)
            direction: Route direction (0 = outbound, 1 = inbound/return)
        
        Returns:
            Tuple of (latitude, longitude)
        """
        self._ensure_distances_calculated()
        
        # For inbound direction, reverse the stop order conceptually
        # Position 0.0 in inbound = last stop, position 1.0 = first stop
        if direction == 1:
            # Invert position for return route
            position = 1.0 - position
        
        # Handle edge cases
        if position <= 0.0:
            return (self.stops[0].latitude, self.stops[0].longitude)
        if position >= 1.0:
            return (self.stops[-1].latitude, self.stops[-1].longitude)
        
        # Convert position to absolute distance
        target_distance = position * self._total_distance
        
        # Find which segment we're in
        accumulated_distance = 0.0
        for i, segment_distance in enumerate(self._segment_distances):
            if accumulated_distance + segment_distance >= target_distance:
                # We're in this segment
                distance_into_segment = target_distance - accumulated_distance
                fraction = distance_into_segment / segment_distance
                
                # Linear interpolation between stops
                lat1, lon1 = self.stops[i].latitude, self.stops[i].longitude
                lat2, lon2 = self.stops[i + 1].latitude, self.stops[i + 1].longitude
                
                lat = lat1 + (lat2 - lat1) * fraction
                lon = lon1 + (lon2 - lon1) * fraction
                
                return (lat, lon)
            
            accumulated_distance += segment_distance
        
        # Fallback (shouldn't reach here)
        return (self.stops[-1].latitude, self.stops[-1].longitude)
    
    def get_stops_between(self, start_position: float, end_position: float, direction: int = 0) -> List[Stop]:
        """
        Get all stops that were passed between two positions.
        
        Args:
            start_position: Starting position (0.0 to 1.0)
            end_position: Ending position (0.0 to 1.0)
            direction: Route direction (0 = outbound, 1 = inbound/return)
        
        Returns:
            List of stops that were reached (in order)
        """
        self._ensure_distances_calculated()
        
        # Convert positions to absolute distances
        start_distance = start_position * self._total_distance
        end_distance = end_position * self._total_distance
        
        stops_reached = []
        accumulated_distance = 0.0
        
        # Check each stop
        for i, stop in enumerate(self.stops):
            # Distance to this stop
            stop_distance = accumulated_distance
            
            # Check if this stop is between start and end
            if start_distance < stop_distance <= end_distance:
                stops_reached.append(stop)
            
            # Add segment distance for next iteration
            if i < len(self._segment_distances):
                accumulated_distance += self._segment_distances[i]
        
        # For inbound direction, reverse the order of stops
        if direction == 1:
            stops_reached.reverse()
        
        return stops_reached
    
    def get_next_stop(self, position: float, direction: int = 0) -> Optional[Stop]:
        """
        Get the next stop ahead of the current position.
        
        Args:
            position: Current position (0.0 to 1.0)
            direction: Route direction (0 = outbound, 1 = inbound/return)
        
        Returns:
            Next stop, or None if at the end of the route
        """
        self._ensure_distances_calculated()
        
        # Convert position to absolute distance
        current_distance = position * self._total_distance
        
        accumulated_distance = 0.0
        
        if direction == 0:
            # Outbound: iterate forward through stops
            for i, stop in enumerate(self.stops):
                stop_distance = accumulated_distance
                
                # Find first stop ahead of current position
                if stop_distance > current_distance:
                    return stop
                
                # Add segment distance for next iteration
                if i < len(self._segment_distances):
                    accumulated_distance += self._segment_distances[i]
        else:
            # Inbound: iterate backward through stops
            # Build reverse accumulated distances
            for i in range(len(self.stops) - 1, -1, -1):
                stop_distance = accumulated_distance
                
                # Find first stop ahead of current position (in reverse)
                if stop_distance > current_distance:
                    return self.stops[i]
                
                # Add segment distance for next iteration (going backwards)
                if i > 0:
                    accumulated_distance += self._segment_distances[i - 1]
        
        # If we're past all stops, return None
        return None
    
    def distance_to_stop(self, position: float, stop: Stop, direction: int = 0) -> float:
        """
        Calculate distance from current position to a specific stop.
        
        Args:
            position: Current position (0.0 to 1.0)
            stop: Target stop
            direction: Route direction (0 = outbound, 1 = inbound/return)
        
        Returns:
            Distance in meters, or -1 if stop is not found or behind current position
        """
        self._ensure_distances_calculated()
        
        # Find the stop in the route
        try:
            stop_index = next(i for i, s in enumerate(self.stops) if s.stop_id == stop.stop_id)
        except StopIteration:
            return -1.0
        
        # Calculate distance to the stop
        current_distance = position * self._total_distance
        
        if direction == 0:
            # Outbound: calculate forward distance
            accumulated_distance = 0.0
            for i in range(stop_index):
                if i < len(self._segment_distances):
                    accumulated_distance += self._segment_distances[i]
            
            stop_distance = accumulated_distance
            
            # If stop is behind us, return -1
            if stop_distance <= current_distance:
                return -1.0
            
            return stop_distance - current_distance
        else:
            # Inbound: calculate backward distance
            # For inbound, we need to calculate distance from current position to stop going backwards
            accumulated_distance = 0.0
            for i in range(len(self.stops) - 1, stop_index, -1):
                if i > 0:
                    accumulated_distance += self._segment_distances[i - 1]
            
            stop_distance = accumulated_distance
            
            # If stop is behind us (in inbound direction), return -1
            if stop_distance <= current_distance:
                return -1.0
            
            return stop_distance - current_distance


@dataclass
class BusState:
    """
    Represents the current state of a bus during simulation.
    
    Attributes:
        bus_id: Unique identifier for the bus
        line_id: Line this bus operates on
        capacity: Maximum passenger capacity
        passenger_count: Current number of passengers
        position_on_route: Current position (0.0 = start, 1.0 = end)
        speed: Current speed in km/h
        at_stop: Whether the bus is currently at a stop
        direction: Route direction (0 = outbound, 1 = inbound/return)
    """
    bus_id: str
    line_id: str
    capacity: int
    passenger_count: int = 0
    position_on_route: float = 0.0
    speed: float = 30.0
    at_stop: bool = False
    direction: int = 0
    
    def validate(self) -> None:
        """
        Validate bus state.
        
        Raises:
            ValueError: If validation fails
        """
        if not self.bus_id:
            raise ValueError("bus_id cannot be empty")
        if not self.line_id:
            raise ValueError("line_id cannot be empty")
        if self.capacity <= 0:
            raise ValueError(f"capacity must be positive, got {self.capacity}")
        if self.passenger_count < 0:
            raise ValueError(f"passenger_count must be non-negative, got {self.passenger_count}")
        if self.passenger_count > self.capacity:
            raise ValueError(f"passenger_count ({self.passenger_count}) exceeds capacity ({self.capacity})")
        if not (0.0 <= self.position_on_route <= 1.0):
            raise ValueError(f"position_on_route must be between 0.0 and 1.0, got {self.position_on_route}")
        if self.speed < 0:
            raise ValueError(f"speed must be non-negative, got {self.speed}")
        if self.direction not in (0, 1):
            raise ValueError(f"direction must be 0 (outbound) or 1 (inbound), got {self.direction}")


@dataclass
class BusArrival:
    """
    Represents a bus arrival event at a stop.
    
    Attributes:
        bus_id: Unique identifier for the bus
        stop_id: Stop where the bus arrived
        timestamp: Time of arrival
        passengers_boarding: Number of passengers who boarded
        passengers_alighting: Number of passengers who alighted
    """
    bus_id: str
    stop_id: str
    timestamp: datetime
    passengers_boarding: int
    passengers_alighting: int
    
    def validate(self) -> None:
        """
        Validate bus arrival event.
        
        Raises:
            ValueError: If validation fails
        """
        if not self.bus_id:
            raise ValueError("bus_id cannot be empty")
        if not self.stop_id:
            raise ValueError("stop_id cannot be empty")
        if self.passengers_boarding < 0:
            raise ValueError(f"passengers_boarding must be non-negative, got {self.passengers_boarding}")
        if self.passengers_alighting < 0:
            raise ValueError(f"passengers_alighting must be non-negative, got {self.passengers_alighting}")
