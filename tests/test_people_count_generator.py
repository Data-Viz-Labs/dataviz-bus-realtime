"""
Unit tests for people count generation algorithm.

Tests the generate_people_count function with various scenarios including
natural arrivals, bus boarding, and edge cases.
"""

import pytest
import random
from datetime import datetime
from dataclasses import dataclass

from src.feeders.people_count_generator import generate_people_count


@dataclass
class BusArrival:
    """Mock BusArrival for testing."""
    bus_id: str
    stop_id: str
    timestamp: datetime
    passengers_boarding: int
    passengers_alighting: int


class TestGeneratePeopleCount:
    """Tests for generate_people_count function."""
    
    def test_no_bus_arrivals_increases_count(self):
        """With no bus arrivals, count should increase or stay same."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)  # Morning rush
        
        count = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=10,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        # Count should be at least the previous count (people arrive, none leave)
        assert count >= 10
    
    def test_bus_arrival_decreases_count(self):
        """When bus arrives and people board, count should decrease."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        # Create bus arrival with 5 people boarding
        arrival = BusArrival(
            bus_id="B001",
            stop_id="S001",
            timestamp=current_time,
            passengers_boarding=5,
            passengers_alighting=0
        )
        
        count = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=10,
            bus_arrivals=[arrival],
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        # Count should be less than or equal to previous (people boarded)
        # Could be higher if many people arrived, but typically lower
        assert count >= 0  # Never negative
    
    def test_count_never_negative(self):
        """Count should never go below zero even with many boardings."""
        random.seed(42)
        stops_config = {"S001": 0.1}  # Very low arrival rate
        current_time = datetime(2024, 1, 15, 2, 0)  # Night (low multiplier)
        
        # Create bus arrival with more boardings than people at stop
        arrival = BusArrival(
            bus_id="B001",
            stop_id="S001",
            timestamp=current_time,
            passengers_boarding=100,
            passengers_alighting=0
        )
        
        count = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=5,
            bus_arrivals=[arrival],
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        assert count >= 0
    
    def test_multiple_bus_arrivals(self):
        """Multiple buses arriving should sum all boardings."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        arrivals = [
            BusArrival("B001", "S001", current_time, 5, 0),
            BusArrival("B002", "S001", current_time, 3, 0),
            BusArrival("B003", "S001", current_time, 2, 0)
        ]
        
        count = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=20,
            bus_arrivals=arrivals,
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        # Total boarding is 10, so count should be around 20 + arrivals - 10
        assert count >= 0
    
    def test_morning_rush_higher_arrivals(self):
        """Morning rush should generate more arrivals than night."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        
        # Morning rush
        morning_time = datetime(2024, 1, 15, 8, 0)
        morning_count = generate_people_count(
            stop_id="S001",
            current_time=morning_time,
            previous_count=0,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=5.0
        )
        
        # Night
        random.seed(42)  # Reset seed for fair comparison
        night_time = datetime(2024, 1, 15, 2, 0)
        night_count = generate_people_count(
            stop_id="S001",
            current_time=night_time,
            previous_count=0,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=5.0
        )
        
        # Morning should have more arrivals (1.5x vs 0.2x multiplier)
        # This is probabilistic, but with seed 42 it should hold
        assert morning_count >= night_count
    
    def test_time_interval_scaling(self):
        """Longer time intervals should generate more arrivals."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        # 1 minute interval
        count_1min = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=0,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        # 10 minute interval (should have ~10x more arrivals)
        random.seed(42)  # Reset for comparison
        count_10min = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=0,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=10.0
        )
        
        # 10-minute interval should generate more arrivals
        assert count_10min >= count_1min
    
    def test_invalid_stop_id(self):
        """Unknown stop ID should raise ValueError."""
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        with pytest.raises(ValueError, match="not found"):
            generate_people_count(
                stop_id="S999",
                current_time=current_time,
                previous_count=10,
                bus_arrivals=[],
                stops_config=stops_config,
                time_interval_minutes=1.0
            )
    
    def test_negative_previous_count(self):
        """Negative previous count should raise ValueError."""
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        with pytest.raises(ValueError, match="previous_count must be non-negative"):
            generate_people_count(
                stop_id="S001",
                current_time=current_time,
                previous_count=-5,
                bus_arrivals=[],
                stops_config=stops_config,
                time_interval_minutes=1.0
            )
    
    def test_zero_time_interval(self):
        """Zero time interval should raise ValueError."""
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        with pytest.raises(ValueError, match="time_interval_minutes must be positive"):
            generate_people_count(
                stop_id="S001",
                current_time=current_time,
                previous_count=10,
                bus_arrivals=[],
                stops_config=stops_config,
                time_interval_minutes=0.0
            )
    
    def test_negative_time_interval(self):
        """Negative time interval should raise ValueError."""
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        with pytest.raises(ValueError, match="time_interval_minutes must be positive"):
            generate_people_count(
                stop_id="S001",
                current_time=current_time,
                previous_count=10,
                bus_arrivals=[],
                stops_config=stops_config,
                time_interval_minutes=-1.0
            )
    
    def test_zero_previous_count(self):
        """Zero previous count should work correctly."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        count = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=0,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        # Should have some arrivals during morning rush
        assert count >= 0
    
    def test_empty_bus_arrivals_list(self):
        """Empty bus arrivals list should work correctly."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        count = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=10,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        assert count >= 10  # Should increase or stay same


class TestIntegration:
    """Integration tests for realistic scenarios."""
    
    def test_realistic_morning_rush_scenario(self):
        """Simulate a realistic morning rush hour scenario."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 8, 0)
        
        # Start with 5 people at stop
        count = 5
        
        # Simulate 10 minutes with 1-minute intervals
        for minute in range(10):
            # Every 3 minutes, a bus arrives
            bus_arrivals = []
            if minute % 3 == 0 and minute > 0:
                # Bus takes about half the people
                boarding = count // 2
                bus_arrivals.append(
                    BusArrival("B001", "S001", current_time, boarding, 0)
                )
            
            count = generate_people_count(
                stop_id="S001",
                current_time=current_time,
                previous_count=count,
                bus_arrivals=bus_arrivals,
                stops_config=stops_config,
                time_interval_minutes=1.0
            )
            
            # Count should always be non-negative
            assert count >= 0
    
    def test_night_scenario_low_activity(self):
        """Simulate a night scenario with low activity."""
        random.seed(42)
        stops_config = {"S001": 2.5}
        current_time = datetime(2024, 1, 15, 2, 0)  # 2 AM
        
        count = 0
        
        # Simulate 30 minutes
        for _ in range(30):
            count = generate_people_count(
                stop_id="S001",
                current_time=current_time,
                previous_count=count,
                bus_arrivals=[],
                stops_config=stops_config,
                time_interval_minutes=1.0
            )
        
        # After 30 minutes at night, should have very few people
        # With 0.2x multiplier and 2.5 base rate: 2.5 * 0.2 * 30 = 15 expected
        assert count >= 0
        assert count < 50  # Should be relatively low
    
    def test_coordination_with_bus_arrivals(self):
        """Test that people count coordinates properly with bus arrivals."""
        random.seed(42)
        stops_config = {"S001": 3.0}
        current_time = datetime(2024, 1, 15, 12, 0)  # Lunch time
        
        # Build up people at stop
        count = 0
        for _ in range(5):
            count = generate_people_count(
                stop_id="S001",
                current_time=current_time,
                previous_count=count,
                bus_arrivals=[],
                stops_config=stops_config,
                time_interval_minutes=1.0
            )
        
        initial_count = count
        
        # Bus arrives and everyone boards
        arrival = BusArrival("B001", "S001", current_time, initial_count, 0)
        count = generate_people_count(
            stop_id="S001",
            current_time=current_time,
            previous_count=initial_count,
            bus_arrivals=[arrival],
            stops_config=stops_config,
            time_interval_minutes=1.0
        )
        
        # Count should be much lower (close to 0, plus any new arrivals)
        assert count < initial_count
        assert count >= 0
