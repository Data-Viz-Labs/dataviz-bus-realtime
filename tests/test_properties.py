"""
Property-based tests for the Madrid Bus Real-Time Simulator.

These tests use the Hypothesis library to verify universal properties
across randomized inputs, ensuring correctness at scale.
"""

import pytest
import math
from datetime import datetime, timedelta
from hypothesis import given, settings, strategies as st
from src.common.models import (
    PeopleCountDataPoint,
    BusPositionDataPoint,
    BusState,
    BusArrival,
    Route,
    Stop,
)


# Strategy for generating valid stop IDs
stop_ids = st.text(min_size=1, max_size=10, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    min_codepoint=48, max_codepoint=122
)).filter(lambda x: x.strip())

# Strategy for generating valid line IDs
line_ids = st.lists(
    st.text(min_size=1, max_size=5, alphabet=st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        min_codepoint=48, max_codepoint=122
    )).filter(lambda x: x.strip()),
    min_size=1,
    max_size=5
)

# Strategy for generating valid bus/entity IDs
entity_ids = st.text(min_size=1, max_size=10, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    min_codepoint=48, max_codepoint=122
)).filter(lambda x: x.strip())

# Strategy for generating timestamps
timestamps = st.datetimes(
    min_value=datetime(2024, 1, 1),
    max_value=datetime(2025, 12, 31)
)

# Strategy for generating passenger counts (non-negative integers)
passenger_counts = st.integers(min_value=0, max_value=200)

# Strategy for generating coordinates
latitudes = st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False)
longitudes = st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False)


class TestProperty17NonNegativePassengerCounts:
    """
    Property 17: Non-negative passenger counts
    
    **Validates: Requirements 4.3**
    
    For all generated data points (people count at stops, passenger count on buses),
    the count values should be greater than or equal to zero.
    """
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        timestamp=timestamps,
        count=passenger_counts,
        lines=line_ids
    )
    def test_people_count_non_negative(self, stop_id, timestamp, count, lines):
        """
        Test that PeopleCountDataPoint enforces non-negative counts.
        
        For any valid stop ID, timestamp, and line IDs, the count must be >= 0.
        """
        # Create a people count data point
        data_point = PeopleCountDataPoint(
            stop_id=stop_id,
            timestamp=timestamp,
            count=count,
            line_ids=lines
        )
        
        # Validate the data point
        data_point.validate()
        
        # Assert the count is non-negative
        assert data_point.count >= 0, f"People count must be non-negative, got {data_point.count}"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps,
        latitude=latitudes,
        longitude=longitudes,
        passenger_count=passenger_counts,
        next_stop_id=entity_ids,
        distance=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        speed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_bus_position_passenger_count_non_negative(
        self, bus_id, line_id, timestamp, latitude, longitude,
        passenger_count, next_stop_id, distance, speed
    ):
        """
        Test that BusPositionDataPoint enforces non-negative passenger counts.
        
        For any valid bus position data, the passenger_count must be >= 0.
        """
        # Create a bus position data point
        data_point = BusPositionDataPoint(
            bus_id=bus_id,
            line_id=line_id,
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude,
            passenger_count=passenger_count,
            next_stop_id=next_stop_id,
            distance_to_next_stop=distance,
            speed=speed
        )
        
        # Validate the data point
        data_point.validate()
        
        # Assert the passenger count is non-negative
        assert data_point.passenger_count >= 0, \
            f"Bus passenger count must be non-negative, got {data_point.passenger_count}"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        capacity=st.integers(min_value=1, max_value=200),
        passenger_count=st.integers(min_value=0, max_value=200),
        position=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        speed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_bus_state_passenger_count_non_negative(
        self, bus_id, line_id, capacity, passenger_count, position, speed
    ):
        """
        Test that BusState enforces non-negative passenger counts.
        
        For any valid bus state, the passenger_count must be >= 0.
        """
        # Ensure passenger count doesn't exceed capacity
        actual_passenger_count = min(passenger_count, capacity)
        
        # Create a bus state
        state = BusState(
            bus_id=bus_id,
            line_id=line_id,
            capacity=capacity,
            passenger_count=actual_passenger_count,
            position_on_route=position,
            speed=speed
        )
        
        # Validate the state
        state.validate()
        
        # Assert the passenger count is non-negative
        assert state.passenger_count >= 0, \
            f"Bus state passenger count must be non-negative, got {state.passenger_count}"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        stop_id=entity_ids,
        timestamp=timestamps,
        boarding=passenger_counts,
        alighting=passenger_counts
    )
    def test_bus_arrival_passenger_counts_non_negative(
        self, bus_id, stop_id, timestamp, boarding, alighting
    ):
        """
        Test that BusArrival enforces non-negative passenger counts.
        
        For any bus arrival event, both boarding and alighting counts must be >= 0.
        """
        # Create a bus arrival event
        arrival = BusArrival(
            bus_id=bus_id,
            stop_id=stop_id,
            timestamp=timestamp,
            passengers_boarding=boarding,
            passengers_alighting=alighting
        )
        
        # Validate the arrival
        arrival.validate()
        
        # Assert both counts are non-negative
        assert arrival.passengers_boarding >= 0, \
            f"Boarding count must be non-negative, got {arrival.passengers_boarding}"
        assert arrival.passengers_alighting >= 0, \
            f"Alighting count must be non-negative, got {arrival.passengers_alighting}"
    
    @settings(max_examples=50)
    @given(
        stop_id=stop_ids,
        timestamp=timestamps,
        count=st.integers(min_value=-100, max_value=-1),  # Intentionally negative
        lines=line_ids
    )
    def test_negative_people_count_raises_error(self, stop_id, timestamp, count, lines):
        """
        Test that negative people counts are rejected during validation.
        
        This verifies that the validation logic properly catches negative values.
        """
        # Create a people count data point with negative count
        data_point = PeopleCountDataPoint(
            stop_id=stop_id,
            timestamp=timestamp,
            count=count,
            line_ids=lines
        )
        
        # Validation should raise ValueError
        with pytest.raises(ValueError, match="count must be non-negative"):
            data_point.validate()
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps,
        latitude=latitudes,
        longitude=longitudes,
        passenger_count=st.integers(min_value=-100, max_value=-1),  # Intentionally negative
        next_stop_id=entity_ids,
        distance=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        speed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_negative_bus_passenger_count_raises_error(
        self, bus_id, line_id, timestamp, latitude, longitude,
        passenger_count, next_stop_id, distance, speed
    ):
        """
        Test that negative bus passenger counts are rejected during validation.
        """
        # Create a bus position data point with negative passenger count
        data_point = BusPositionDataPoint(
            bus_id=bus_id,
            line_id=line_id,
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude,
            passenger_count=passenger_count,
            next_stop_id=next_stop_id,
            distance_to_next_stop=distance,
            speed=speed
        )
        
        # Validation should raise ValueError
        with pytest.raises(ValueError, match="passenger_count must be non-negative"):
            data_point.validate()


class TestProperty10DailyPatternAdherence:
    """
    Property 10: Daily pattern adherence
    
    **Validates: Requirements 1.4**
    
    For any bus stop and any 24-hour period of generated data, the average passenger
    count during morning rush hours (06:00-09:00) should be higher than the average
    during mid-morning hours (09:00-12:00), and the average during evening rush hours
    (18:00-21:00) should be higher than the average during night hours (21:00-06:00).
    """
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        base_arrival_rate=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
        time_interval_minutes=st.integers(min_value=1, max_value=10)
    )
    def test_morning_rush_higher_than_mid_morning(self, stop_id, base_arrival_rate, time_interval_minutes):
        """
        Test that morning rush hours have higher average passenger counts than mid-morning.
        
        For any bus stop with a given base arrival rate, when simulating a full day
        of passenger arrivals, the average count during morning rush (06:00-09:00)
        should be higher than mid-morning (09:00-12:00).
        """
        from src.feeders.daily_patterns import get_time_multiplier, poisson_sample
        
        # Simulate morning rush hours (06:00-09:00)
        morning_rush_counts = []
        for hour in range(6, 9):
            multiplier = get_time_multiplier(hour)
            # Simulate multiple intervals per hour
            for _ in range(12):  # 12 five-minute intervals per hour
                expected = base_arrival_rate * multiplier * time_interval_minutes
                actual = poisson_sample(expected)
                morning_rush_counts.append(actual)
        
        # Simulate mid-morning hours (09:00-12:00)
        mid_morning_counts = []
        for hour in range(9, 12):
            multiplier = get_time_multiplier(hour)
            for _ in range(12):
                expected = base_arrival_rate * multiplier * time_interval_minutes
                actual = poisson_sample(expected)
                mid_morning_counts.append(actual)
        
        # Calculate averages
        avg_morning_rush = sum(morning_rush_counts) / len(morning_rush_counts)
        avg_mid_morning = sum(mid_morning_counts) / len(mid_morning_counts)
        
        # Morning rush should have higher average than mid-morning
        # The multipliers are 1.5x vs 0.6x, so morning rush should be ~2.5x higher
        assert avg_morning_rush > avg_mid_morning, \
            f"Morning rush average ({avg_morning_rush:.2f}) should be higher than " \
            f"mid-morning average ({avg_mid_morning:.2f}) for stop {stop_id}"
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        base_arrival_rate=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
        time_interval_minutes=st.integers(min_value=1, max_value=10)
    )
    def test_evening_rush_higher_than_night(self, stop_id, base_arrival_rate, time_interval_minutes):
        """
        Test that evening rush hours have higher average passenger counts than night hours.
        
        For any bus stop with a given base arrival rate, when simulating a full day
        of passenger arrivals, the average count during evening rush (18:00-21:00)
        should be higher than night hours (21:00-06:00).
        """
        from src.feeders.daily_patterns import get_time_multiplier, poisson_sample
        
        # Simulate evening rush hours (18:00-21:00)
        evening_rush_counts = []
        for hour in range(18, 21):
            multiplier = get_time_multiplier(hour)
            # Simulate multiple intervals per hour
            for _ in range(12):  # 12 five-minute intervals per hour
                expected = base_arrival_rate * multiplier * time_interval_minutes
                actual = poisson_sample(expected)
                evening_rush_counts.append(actual)
        
        # Simulate night hours (21:00-06:00)
        night_counts = []
        for hour in list(range(21, 24)) + list(range(0, 6)):
            multiplier = get_time_multiplier(hour)
            for _ in range(12):
                expected = base_arrival_rate * multiplier * time_interval_minutes
                actual = poisson_sample(expected)
                night_counts.append(actual)
        
        # Calculate averages
        avg_evening_rush = sum(evening_rush_counts) / len(evening_rush_counts)
        avg_night = sum(night_counts) / len(night_counts)
        
        # Evening rush should have higher average than night
        # The multipliers are 1.4x vs 0.2x, so evening rush should be ~7x higher
        assert avg_evening_rush > avg_night, \
            f"Evening rush average ({avg_evening_rush:.2f}) should be higher than " \
            f"night average ({avg_night:.2f}) for stop {stop_id}"
    
    @settings(max_examples=50)
    @given(
        stop_id=stop_ids,
        base_arrival_rate=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
        time_interval_minutes=st.integers(min_value=1, max_value=10)
    )
    def test_full_day_pattern_consistency(self, stop_id, base_arrival_rate, time_interval_minutes):
        """
        Test that the full 24-hour pattern shows expected relationships between all periods.
        
        This comprehensive test verifies that:
        1. Morning rush > Mid-morning
        2. Evening rush > Night
        3. Rush hours (morning + evening) > Non-rush hours (mid-morning + afternoon + night)
        """
        from src.feeders.daily_patterns import get_time_multiplier, poisson_sample
        
        # Define time periods
        periods = {
            'morning_rush': range(6, 9),      # 06:00-09:00, multiplier 1.5x
            'mid_morning': range(9, 12),      # 09:00-12:00, multiplier 0.6x
            'lunch': range(12, 15),           # 12:00-15:00, multiplier 1.2x
            'afternoon': range(15, 18),       # 15:00-18:00, multiplier 0.8x
            'evening_rush': range(18, 21),    # 18:00-21:00, multiplier 1.4x
            'night': list(range(21, 24)) + list(range(0, 6))  # 21:00-06:00, multiplier 0.2x
        }
        
        # Simulate each period
        period_averages = {}
        for period_name, hours in periods.items():
            counts = []
            for hour in hours:
                multiplier = get_time_multiplier(hour)
                # Simulate multiple intervals per hour
                for _ in range(12):  # 12 five-minute intervals per hour
                    expected = base_arrival_rate * multiplier * time_interval_minutes
                    actual = poisson_sample(expected)
                    counts.append(actual)
            period_averages[period_name] = sum(counts) / len(counts)
        
        # Verify key relationships
        assert period_averages['morning_rush'] > period_averages['mid_morning'], \
            f"Morning rush ({period_averages['morning_rush']:.2f}) should be higher than " \
            f"mid-morning ({period_averages['mid_morning']:.2f})"
        
        assert period_averages['evening_rush'] > period_averages['night'], \
            f"Evening rush ({period_averages['evening_rush']:.2f}) should be higher than " \
            f"night ({period_averages['night']:.2f})"
        
        # Additional verification: rush hours should be higher than low-activity periods
        assert period_averages['morning_rush'] > period_averages['afternoon'], \
            f"Morning rush ({period_averages['morning_rush']:.2f}) should be higher than " \
            f"afternoon ({period_averages['afternoon']:.2f})"
        
        assert period_averages['evening_rush'] > period_averages['mid_morning'], \
            f"Evening rush ({period_averages['evening_rush']:.2f}) should be higher than " \
            f"mid-morning ({period_averages['mid_morning']:.2f})"


class TestProperty11PassengerCountMonotonicity:
    """
    Property 11: Passenger count monotonicity between bus arrivals
    
    **Validates: Requirements 1.5**
    
    For any sequence of people count data points at a stop where no bus arrivals occur,
    the passenger count should be non-decreasing (stable or gradually increasing).
    """
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        initial_count=passenger_counts,
        base_arrival_rate=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
        num_intervals=st.integers(min_value=2, max_value=20),
        time_interval_minutes=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
        hour=st.integers(min_value=0, max_value=23)
    )
    def test_count_non_decreasing_without_bus_arrivals(
        self, stop_id, initial_count, base_arrival_rate, num_intervals, 
        time_interval_minutes, hour
    ):
        """
        Test that passenger count is non-decreasing when no buses arrive.
        
        For any stop with a given base arrival rate, when simulating multiple
        time intervals without any bus arrivals, the passenger count should
        never decrease (it should stay the same or increase).
        """
        from src.feeders.people_count_generator import generate_people_count
        
        # Create stops configuration
        stops_config = {stop_id: base_arrival_rate}
        
        # Simulate multiple intervals without bus arrivals
        current_count = initial_count
        current_time = datetime(2024, 1, 15, hour, 0)
        
        for i in range(num_intervals):
            # Generate new count with no bus arrivals (empty list)
            new_count = generate_people_count(
                stop_id=stop_id,
                current_time=current_time,
                previous_count=current_count,
                bus_arrivals=[],  # No bus arrivals
                stops_config=stops_config,
                time_interval_minutes=time_interval_minutes
            )
            
            # Assert that count is non-decreasing
            assert new_count >= current_count, \
                f"Passenger count decreased from {current_count} to {new_count} " \
                f"at interval {i} without any bus arrivals (stop: {stop_id}, hour: {hour})"
            
            # Update for next iteration
            current_count = new_count
            current_time = current_time.replace(minute=(current_time.minute + int(time_interval_minutes)) % 60)
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        initial_count=passenger_counts,
        base_arrival_rate=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
        time_interval_minutes=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
        hour=st.integers(min_value=0, max_value=23)
    )
    def test_single_interval_non_decreasing(
        self, stop_id, initial_count, base_arrival_rate, time_interval_minutes, hour
    ):
        """
        Test that a single time interval without bus arrivals never decreases count.
        
        This is a simpler version of the above test focusing on a single interval.
        """
        from src.feeders.people_count_generator import generate_people_count
        
        stops_config = {stop_id: base_arrival_rate}
        current_time = datetime(2024, 1, 15, hour, 0)
        
        new_count = generate_people_count(
            stop_id=stop_id,
            current_time=current_time,
            previous_count=initial_count,
            bus_arrivals=[],
            stops_config=stops_config,
            time_interval_minutes=time_interval_minutes
        )
        
        assert new_count >= initial_count, \
            f"Count decreased from {initial_count} to {new_count} without bus arrivals"
    
    @settings(max_examples=50)
    @given(
        stop_id=stop_ids,
        initial_count=passenger_counts,
        base_arrival_rate=st.floats(min_value=2.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        num_intervals=st.integers(min_value=5, max_value=15),
        time_interval_minutes=st.floats(min_value=1.0, max_value=3.0, allow_nan=False, allow_infinity=False)
    )
    def test_count_increases_over_time_during_rush_hour(
        self, stop_id, initial_count, base_arrival_rate, num_intervals, time_interval_minutes
    ):
        """
        Test that passenger count generally increases during rush hour without bus arrivals.
        
        During morning rush hour (high arrival rate), over multiple intervals,
        the count should increase (though individual intervals might stay the same
        due to Poisson sampling).
        """
        from src.feeders.people_count_generator import generate_people_count
        
        stops_config = {stop_id: base_arrival_rate}
        
        # Use morning rush hour (8 AM) for high arrival rate
        current_time = datetime(2024, 1, 15, 8, 0)
        
        current_count = initial_count
        for _ in range(num_intervals):
            new_count = generate_people_count(
                stop_id=stop_id,
                current_time=current_time,
                previous_count=current_count,
                bus_arrivals=[],
                stops_config=stops_config,
                time_interval_minutes=time_interval_minutes
            )
            
            # Should never decrease
            assert new_count >= current_count, \
                f"Count decreased during rush hour without bus arrivals"
            
            current_count = new_count
            current_time = current_time.replace(minute=(current_time.minute + int(time_interval_minutes)) % 60)
        
        # After multiple intervals during rush hour, count should have increased
        # (with very high probability given the high arrival rate)
        assert current_count > initial_count, \
            f"Count did not increase after {num_intervals} intervals during rush hour " \
            f"(initial: {initial_count}, final: {current_count})"


class TestProperty12BoardingDecreasesStopCount:
    """
    Property 12: Boarding decreases stop count
    
    **Validates: Requirements 1.6, 4.2**
    
    For any bus arrival event at a stop, the stop's passenger count immediately after
    the arrival should equal the count before the arrival minus the number of passengers
    boarding (or zero if the result would be negative).
    """
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        bus_id=entity_ids,
        previous_count=passenger_counts,
        passengers_boarding=st.integers(min_value=0, max_value=50),
        base_arrival_rate=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
        time_interval_minutes=st.floats(min_value=0.5, max_value=5.0, allow_nan=False, allow_infinity=False),
        hour=st.integers(min_value=0, max_value=23)
    )
    def test_boarding_decreases_count(
        self, stop_id, bus_id, previous_count, passengers_boarding,
        base_arrival_rate, time_interval_minutes, hour
    ):
        """
        Test that passenger boarding decreases the stop count appropriately.
        
        For any bus arrival with a given number of boarding passengers,
        the new count should equal: max(0, previous_count + arrivals - boarding).
        """
        from src.feeders.people_count_generator import generate_people_count
        
        stops_config = {stop_id: base_arrival_rate}
        current_time = datetime(2024, 1, 15, hour, 0)
        
        # Create a bus arrival event
        arrival = BusArrival(
            bus_id=bus_id,
            stop_id=stop_id,
            timestamp=current_time,
            passengers_boarding=passengers_boarding,
            passengers_alighting=0  # Not relevant for this property
        )
        
        # Generate new count with the bus arrival
        new_count = generate_people_count(
            stop_id=stop_id,
            current_time=current_time,
            previous_count=previous_count,
            bus_arrivals=[arrival],
            stops_config=stops_config,
            time_interval_minutes=time_interval_minutes
        )
        
        # The new count should be at most previous_count + natural_arrivals - boarding
        # Since natural arrivals are random (Poisson), we can't predict the exact value,
        # but we can verify that:
        # 1. If boarding >= previous_count + max_possible_arrivals, new_count should be 0
        # 2. new_count should always be >= 0
        # 3. If boarding > previous_count and no arrivals, new_count should be 0
        
        assert new_count >= 0, \
            f"Count became negative after boarding: {new_count}"
        
        # If many people board and previous count was low, count should decrease or be zero
        if passengers_boarding > previous_count:
            # Count should have decreased (unless natural arrivals compensated)
            # At minimum, it should not have increased by more than reasonable arrivals
            max_reasonable_arrivals = base_arrival_rate * 2.0 * time_interval_minutes * 5  # 5x multiplier max
            assert new_count <= previous_count + max_reasonable_arrivals, \
                f"Count increased too much despite boarding: " \
                f"previous={previous_count}, boarding={passengers_boarding}, new={new_count}"
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        bus_id=entity_ids,
        previous_count=st.integers(min_value=10, max_value=100),
        passengers_boarding=st.integers(min_value=0, max_value=50),
        hour=st.integers(min_value=21, max_value=23)  # Night hours with minimal arrivals
    )
    def test_boarding_effect_during_low_activity(
        self, stop_id, bus_id, previous_count, passengers_boarding, hour
    ):
        """
        Test boarding effect during night hours when natural arrivals are minimal.
        
        During night hours (low arrival rate), the effect of boarding should be
        more clearly visible since natural arrivals are minimal.
        """
        from src.feeders.people_count_generator import generate_people_count
        
        # Use low base arrival rate
        base_arrival_rate = 0.2
        stops_config = {stop_id: base_arrival_rate}
        current_time = datetime(2024, 1, 15, hour, 0)
        time_interval_minutes = 1.0
        
        # Create a bus arrival event
        arrival = BusArrival(
            bus_id=bus_id,
            stop_id=stop_id,
            timestamp=current_time,
            passengers_boarding=passengers_boarding,
            passengers_alighting=0
        )
        
        # Generate new count with the bus arrival
        new_count = generate_people_count(
            stop_id=stop_id,
            current_time=current_time,
            previous_count=previous_count,
            bus_arrivals=[arrival],
            stops_config=stops_config,
            time_interval_minutes=time_interval_minutes
        )
        
        # During night hours with low arrival rate, the count should decrease
        # (or stay roughly the same if boarding is 0)
        assert new_count >= 0, "Count must be non-negative"
        
        # If boarding > 0, count should have decreased or stayed same
        # (very unlikely to increase enough to compensate during night)
        if passengers_boarding > 0:
            # Maximum expected arrivals during night: 0.2 * 0.2 * 1.0 * 5 (generous) = 0.2
            # So count should be less than previous in most cases
            assert new_count <= previous_count, \
                f"Count should decrease or stay same when people board during night: " \
                f"previous={previous_count}, boarding={passengers_boarding}, new={new_count}"
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        previous_count=st.integers(min_value=0, max_value=20),
        passengers_boarding=st.integers(min_value=30, max_value=100),
        hour=st.integers(min_value=21, max_value=23)
    )
    def test_boarding_more_than_available_results_in_zero_or_low_count(
        self, stop_id, previous_count, passengers_boarding, hour
    ):
        """
        Test that when more people board than are waiting, count goes to zero or near-zero.
        
        If passengers_boarding >> previous_count and it's night time (low arrivals),
        the new count should be zero or very low.
        """
        from src.feeders.people_count_generator import generate_people_count
        
        # Use very low base arrival rate for night
        base_arrival_rate = 0.1
        stops_config = {stop_id: base_arrival_rate}
        current_time = datetime(2024, 1, 15, hour, 0)
        time_interval_minutes = 1.0
        
        # Create a bus arrival with many boarding passengers
        arrival = BusArrival(
            bus_id="B001",
            stop_id=stop_id,
            timestamp=current_time,
            passengers_boarding=passengers_boarding,
            passengers_alighting=0
        )
        
        # Generate new count
        new_count = generate_people_count(
            stop_id=stop_id,
            current_time=current_time,
            previous_count=previous_count,
            bus_arrivals=[arrival],
            stops_config=stops_config,
            time_interval_minutes=time_interval_minutes
        )
        
        # Count should be zero or very low (at most a few natural arrivals)
        # Max expected arrivals: 0.1 * 0.2 * 1.0 * 10 (very generous) = 0.2
        assert new_count <= 5, \
            f"When boarding ({passengers_boarding}) >> previous count ({previous_count}), " \
            f"new count should be near zero, got {new_count}"
    
    @settings(max_examples=100)
    @given(
        stop_id=stop_ids,
        previous_count=passenger_counts,
        num_buses=st.integers(min_value=2, max_value=5),
        boarding_per_bus=st.integers(min_value=5, max_value=20),
        hour=st.integers(min_value=0, max_value=23)
    )
    def test_multiple_bus_arrivals_cumulative_effect(
        self, stop_id, previous_count, num_buses, boarding_per_bus, hour
    ):
        """
        Test that multiple bus arrivals have cumulative boarding effect.
        
        When multiple buses arrive in the same interval, the total boarding
        should be the sum of all boarding passengers.
        """
        from src.feeders.people_count_generator import generate_people_count
        
        base_arrival_rate = 1.0
        stops_config = {stop_id: base_arrival_rate}
        current_time = datetime(2024, 1, 15, hour, 0)
        time_interval_minutes = 1.0
        
        # Create multiple bus arrivals
        arrivals = [
            BusArrival(
                bus_id=f"B{i:03d}",
                stop_id=stop_id,
                timestamp=current_time,
                passengers_boarding=boarding_per_bus,
                passengers_alighting=0
            )
            for i in range(num_buses)
        ]
        
        total_boarding = num_buses * boarding_per_bus
        
        # Generate new count with multiple arrivals
        new_count = generate_people_count(
            stop_id=stop_id,
            current_time=current_time,
            previous_count=previous_count,
            bus_arrivals=arrivals,
            stops_config=stops_config,
            time_interval_minutes=time_interval_minutes
        )
        
        # Count should be non-negative
        assert new_count >= 0, "Count must be non-negative"
        
        # If total boarding is much larger than previous count, new count should be low
        if total_boarding > previous_count + 10:  # 10 is generous buffer for arrivals
            assert new_count <= previous_count, \
                f"With {num_buses} buses boarding {boarding_per_bus} each (total {total_boarding}), " \
                f"count should decrease from {previous_count}, got {new_count}"


class TestProperty13SensorConsistencyWithBusState:
    """
    Property 13: Sensor data consistency with bus state
    
    **Validates: Requirements 2.3, 4.4**
    
    For any bus sensor data point where the bus is at a stop (at_stop is True),
    the door_status should be "open". When the bus is en route (at_stop is False),
    door_status should be "closed".
    """
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        capacity=st.integers(min_value=1, max_value=200),
        passenger_count=st.integers(min_value=0, max_value=200),
        position=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        speed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        at_stop=st.booleans(),
        timestamp=timestamps
    )
    def test_door_status_matches_at_stop_state(
        self, bus_id, line_id, capacity, passenger_count, position, speed, at_stop, timestamp
    ):
        """
        Test that door_status correctly reflects whether the bus is at a stop.
        
        For any bus state, when at_stop is True, the generated sensor data should
        have door_status "open". When at_stop is False, door_status should be "closed".
        """
        from src.feeders.sensor_data_generator import generate_sensor_data
        
        # Ensure passenger count doesn't exceed capacity
        actual_passenger_count = min(passenger_count, capacity)
        
        # Create a bus state
        bus_state = BusState(
            bus_id=bus_id,
            line_id=line_id,
            capacity=capacity,
            passenger_count=actual_passenger_count,
            position_on_route=position,
            speed=speed,
            at_stop=at_stop
        )
        
        # Generate sensor data for this bus
        sensor_data = generate_sensor_data(
            entity_id=bus_id,
            entity_type="bus",
            current_time=timestamp,
            bus_state=bus_state
        )
        
        # Verify door status matches at_stop state
        if at_stop:
            assert sensor_data.door_status == "open", \
                f"When bus is at stop (at_stop=True), door_status should be 'open', got '{sensor_data.door_status}'"
        else:
            assert sensor_data.door_status == "closed", \
                f"When bus is en route (at_stop=False), door_status should be 'closed', got '{sensor_data.door_status}'"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        capacity=st.integers(min_value=1, max_value=200),
        passenger_count=st.integers(min_value=0, max_value=200),
        timestamp=timestamps
    )
    def test_door_open_when_at_stop(
        self, bus_id, line_id, capacity, passenger_count, timestamp
    ):
        """
        Test that doors are always open when bus is at a stop.
        
        This is a focused test specifically for the at_stop=True case.
        """
        from src.feeders.sensor_data_generator import generate_sensor_data
        
        # Ensure passenger count doesn't exceed capacity
        actual_passenger_count = min(passenger_count, capacity)
        
        # Create a bus state at a stop
        bus_state = BusState(
            bus_id=bus_id,
            line_id=line_id,
            capacity=capacity,
            passenger_count=actual_passenger_count,
            at_stop=True  # Explicitly at stop
        )
        
        # Generate sensor data
        sensor_data = generate_sensor_data(
            entity_id=bus_id,
            entity_type="bus",
            current_time=timestamp,
            bus_state=bus_state
        )
        
        # Doors must be open
        assert sensor_data.door_status == "open", \
            f"Doors should be open when bus is at stop, got '{sensor_data.door_status}'"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        capacity=st.integers(min_value=1, max_value=200),
        passenger_count=st.integers(min_value=0, max_value=200),
        timestamp=timestamps
    )
    def test_door_closed_when_en_route(
        self, bus_id, line_id, capacity, passenger_count, timestamp
    ):
        """
        Test that doors are always closed when bus is en route.
        
        This is a focused test specifically for the at_stop=False case.
        """
        from src.feeders.sensor_data_generator import generate_sensor_data
        
        # Ensure passenger count doesn't exceed capacity
        actual_passenger_count = min(passenger_count, capacity)
        
        # Create a bus state en route (not at stop)
        bus_state = BusState(
            bus_id=bus_id,
            line_id=line_id,
            capacity=capacity,
            passenger_count=actual_passenger_count,
            at_stop=False  # Explicitly not at stop
        )
        
        # Generate sensor data
        sensor_data = generate_sensor_data(
            entity_id=bus_id,
            entity_type="bus",
            current_time=timestamp,
            bus_state=bus_state
        )
        
        # Doors must be closed
        assert sensor_data.door_status == "closed", \
            f"Doors should be closed when bus is en route, got '{sensor_data.door_status}'"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps
    )
    def test_door_status_consistency_across_multiple_readings(
        self, bus_id, line_id, timestamp
    ):
        """
        Test that door status remains consistent for the same bus state.
        
        For any bus state, generating sensor data multiple times should
        always produce the same door_status value.
        """
        from src.feeders.sensor_data_generator import generate_sensor_data
        
        # Create a bus state at a stop
        bus_state_at_stop = BusState(
            bus_id=bus_id,
            line_id=line_id,
            capacity=80,
            passenger_count=30,
            at_stop=True
        )
        
        # Generate sensor data multiple times
        for _ in range(5):
            sensor_data = generate_sensor_data(
                entity_id=bus_id,
                entity_type="bus",
                current_time=timestamp,
                bus_state=bus_state_at_stop
            )
            assert sensor_data.door_status == "open", \
                "Door status should consistently be 'open' for bus at stop"
        
        # Create a bus state en route
        bus_state_en_route = BusState(
            bus_id=bus_id,
            line_id=line_id,
            capacity=80,
            passenger_count=30,
            at_stop=False
        )
        
        # Generate sensor data multiple times
        for _ in range(5):
            sensor_data = generate_sensor_data(
                entity_id=bus_id,
                entity_type="bus",
                current_time=timestamp,
                bus_state=bus_state_en_route
            )
            assert sensor_data.door_status == "closed", \
                "Door status should consistently be 'closed' for bus en route"


class TestProperty14BusPositionsFollowRoutes:
    """
    Property 14: Bus positions follow defined routes
    
    **Validates: Requirements 3.5**
    
    For any generated bus position, the coordinates (latitude, longitude) should be
    within 50 meters of the corresponding route geometry stored in Amazon Location.
    
    Since we use linear interpolation between stops to define route geometry,
    this test verifies that get_coordinates() returns points that lie on or very
    close to the line segments connecting consecutive stops.
    """
    
    @staticmethod
    def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
    
    @staticmethod
    def _distance_to_line_segment(point_lat: float, point_lon: float,
                                   seg_start_lat: float, seg_start_lon: float,
                                   seg_end_lat: float, seg_end_lon: float) -> float:
        """
        Calculate the minimum distance from a point to a line segment.
        
        This uses the perpendicular distance to the line, or the distance to
        the nearest endpoint if the perpendicular falls outside the segment.
        
        Args:
            point_lat: Latitude of the point
            point_lon: Longitude of the point
            seg_start_lat: Latitude of segment start
            seg_start_lon: Longitude of segment start
            seg_end_lat: Latitude of segment end
            seg_end_lon: Longitude of segment end
        
        Returns:
            Minimum distance in meters
        """
        # For small distances, we can approximate using Euclidean distance
        # with latitude/longitude scaled appropriately
        # This is accurate enough for distances < 100km
        
        # Convert to approximate meters (at Madrid's latitude ~40°)
        lat_to_meters = 111320  # meters per degree latitude
        lon_to_meters = 85390   # meters per degree longitude at 40° latitude
        
        # Convert all points to meters relative to segment start
        px = (point_lon - seg_start_lon) * lon_to_meters
        py = (point_lat - seg_start_lat) * lat_to_meters
        
        dx = (seg_end_lon - seg_start_lon) * lon_to_meters
        dy = (seg_end_lat - seg_start_lat) * lat_to_meters
        
        # Calculate segment length squared
        segment_length_sq = dx * dx + dy * dy
        
        # If segment has zero length, return distance to the point
        if segment_length_sq == 0:
            return math.sqrt(px * px + py * py)
        
        # Calculate projection parameter t
        # t = 0 means closest to start, t = 1 means closest to end
        t = max(0, min(1, (px * dx + py * dy) / segment_length_sq))
        
        # Calculate closest point on segment
        closest_x = t * dx
        closest_y = t * dy
        
        # Calculate distance from point to closest point
        dist_x = px - closest_x
        dist_y = py - closest_y
        
        return math.sqrt(dist_x * dist_x + dist_y * dist_y)
    
    @staticmethod
    def _create_test_route() -> Route:
        """Create a test route with realistic Madrid coordinates."""
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
        return Route(line_id="L1", name="Test Route", stops=stops)
    
    @settings(max_examples=100)
    @given(
        position=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_coordinates_within_50m_of_route(self, position):
        """
        Test that coordinates returned by get_coordinates() are within 50m of route geometry.
        
        For any position on the route (0.0 to 1.0), the coordinates should lie on or
        very close to the line segments connecting consecutive stops.
        """
        route = self._create_test_route()
        
        # Get coordinates at this position
        lat, lon = route.get_coordinates(position)
        
        # Find the minimum distance to any segment of the route
        min_distance = float('inf')
        
        for i in range(len(route.stops) - 1):
            seg_start = route.stops[i]
            seg_end = route.stops[i + 1]
            
            distance = self._distance_to_line_segment(
                lat, lon,
                seg_start.latitude, seg_start.longitude,
                seg_end.latitude, seg_end.longitude
            )
            
            min_distance = min(min_distance, distance)
        
        # Assert that the point is within 50 meters of the route
        assert min_distance <= 50.0, \
            f"Position {position:.4f} generated coordinates ({lat:.6f}, {lon:.6f}) " \
            f"that are {min_distance:.2f}m from the route (max allowed: 50m)"
    
    @settings(max_examples=100)
    @given(
        start_position=st.floats(min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False),
        distance_meters=st.floats(min_value=0.0, max_value=5000.0, allow_nan=False, allow_infinity=False)
    )
    def test_advanced_position_stays_on_route(self, start_position, distance_meters):
        """
        Test that advancing position along a route keeps the bus on the route.
        
        For any starting position and distance traveled, the new position should
        still generate coordinates within 50m of the route geometry.
        """
        route = self._create_test_route()
        
        # Advance position
        new_position = route.advance_position(start_position, distance_meters)
        
        # Get coordinates at new position
        lat, lon = route.get_coordinates(new_position)
        
        # Find the minimum distance to any segment of the route
        min_distance = float('inf')
        
        for i in range(len(route.stops) - 1):
            seg_start = route.stops[i]
            seg_end = route.stops[i + 1]
            
            distance = self._distance_to_line_segment(
                lat, lon,
                seg_start.latitude, seg_start.longitude,
                seg_end.latitude, seg_end.longitude
            )
            
            min_distance = min(min_distance, distance)
        
        # Assert that the point is within 50 meters of the route
        assert min_distance <= 50.0, \
            f"After advancing from {start_position:.4f} by {distance_meters:.2f}m to {new_position:.4f}, " \
            f"coordinates ({lat:.6f}, {lon:.6f}) are {min_distance:.2f}m from route (max: 50m)"
    
    @settings(max_examples=50)
    @given(
        position=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    def test_coordinates_match_stops_at_exact_positions(self, position):
        """
        Test that coordinates at stop positions match the stop coordinates exactly.
        
        When the position corresponds exactly to a stop location, the returned
        coordinates should match the stop's coordinates (within floating point precision).
        """
        route = self._create_test_route()
        
        # Calculate the exact position of each stop
        route._ensure_distances_calculated()
        total_distance = route.get_total_distance()
        
        accumulated_distance = 0.0
        for i, stop in enumerate(route.stops):
            stop_position = accumulated_distance / total_distance if total_distance > 0 else 0.0
            
            # Get coordinates at this exact stop position
            lat, lon = route.get_coordinates(stop_position)
            
            # Calculate distance from returned coordinates to stop coordinates
            distance = self._calculate_distance(lat, lon, stop.latitude, stop.longitude)
            
            # Should be very close (within 1 meter due to floating point precision)
            assert distance < 1.0, \
                f"At stop {stop.name} (position {stop_position:.4f}), " \
                f"coordinates ({lat:.6f}, {lon:.6f}) are {distance:.2f}m from " \
                f"stop coordinates ({stop.latitude:.6f}, {stop.longitude:.6f})"
            
            # Move to next segment
            if i < len(route._segment_distances):
                accumulated_distance += route._segment_distances[i]
    
    def test_edge_cases_start_and_end(self):
        """
        Test that positions at the start (0.0) and end (1.0) return correct coordinates.
        """
        route = self._create_test_route()
        
        # Test start position
        lat_start, lon_start = route.get_coordinates(0.0)
        first_stop = route.stops[0]
        distance_start = self._calculate_distance(
            lat_start, lon_start,
            first_stop.latitude, first_stop.longitude
        )
        assert distance_start < 1.0, \
            f"Start position (0.0) should match first stop, but is {distance_start:.2f}m away"
        
        # Test end position
        lat_end, lon_end = route.get_coordinates(1.0)
        last_stop = route.stops[-1]
        distance_end = self._calculate_distance(
            lat_end, lon_end,
            last_stop.latitude, last_stop.longitude
        )
        assert distance_end < 1.0, \
            f"End position (1.0) should match last stop, but is {distance_end:.2f}m away"



class TestProperty15TerminalStopPassengerReset:
    """
    Property 15: Terminal stop passenger reset
    
    **Validates: Requirements 3.6**
    
    For any bus reaching a terminal stop (is_terminal = true), the passenger count
    in the next position data point should equal only the number of new passengers
    boarding (previous passengers should have alighted).
    """
    
    @staticmethod
    def _create_test_route_with_terminal() -> Route:
        """Create a test route with a terminal stop at the end."""
        stops = [
            Stop(
                stop_id="S001",
                name="Start Station",
                latitude=40.4657,
                longitude=-3.6886,
                is_terminal=True,
                base_arrival_rate=2.5
            ),
            Stop(
                stop_id="S002",
                name="Middle Station",
                latitude=40.4500,
                longitude=-3.6900,
                is_terminal=False,
                base_arrival_rate=1.8
            ),
            Stop(
                stop_id="S003",
                name="Terminal Station",
                latitude=40.4400,
                longitude=-3.6950,
                is_terminal=True,
                base_arrival_rate=2.0
            ),
        ]
        return Route(line_id="L1", name="Test Route", stops=stops)
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        initial_passengers=st.integers(min_value=1, max_value=80),
        people_at_terminal=st.integers(min_value=0, max_value=50),
        capacity=st.integers(min_value=50, max_value=100)
    )
    def test_terminal_stop_resets_passenger_count(
        self, bus_id, initial_passengers, people_at_terminal, capacity
    ):
        """
        Test that reaching a terminal stop resets passenger count to only new boarders.
        
        For any bus with passengers arriving at a terminal stop, after the stop:
        - All previous passengers should have alighted
        - Only new passengers who board should be on the bus
        """
        from src.feeders.bus_movement_simulator import calculate_alighting, calculate_boarding
        
        route = self._create_test_route_with_terminal()
        terminal_stop = route.stops[2]  # The terminal stop
        
        # Verify it's a terminal stop
        assert terminal_stop.is_terminal, "Test setup error: stop should be terminal"
        
        # Calculate alighting at terminal stop
        alighting = calculate_alighting(initial_passengers, is_terminal=True)
        
        # At terminal stops, everyone must get off
        assert alighting == initial_passengers, \
            f"At terminal stop, all {initial_passengers} passengers should alight, got {alighting}"
        
        # Calculate boarding
        available_capacity = capacity  # Full capacity available after everyone alights
        boarding = calculate_boarding(people_at_terminal, available_capacity)
        
        # New passenger count should equal only the boarding passengers
        new_passenger_count = initial_passengers - alighting + boarding
        
        assert new_passenger_count == boarding, \
            f"After terminal stop, passenger count should equal boarding ({boarding}), " \
            f"got {new_passenger_count} (initial: {initial_passengers}, alighting: {alighting})"
        
        # Verify the count is non-negative
        assert new_passenger_count >= 0, \
            f"Passenger count must be non-negative, got {new_passenger_count}"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        initial_passengers=st.integers(min_value=10, max_value=80),
        people_at_terminal=st.integers(min_value=0, max_value=20)
    )
    def test_terminal_stop_everyone_alights(self, bus_id, initial_passengers, people_at_terminal):
        """
        Test that at terminal stops, the alighting count equals the passenger count.
        
        This is a focused test on the alighting behavior at terminal stops.
        """
        from src.feeders.bus_movement_simulator import calculate_alighting
        
        # Calculate alighting at terminal stop
        alighting = calculate_alighting(initial_passengers, is_terminal=True)
        
        # Everyone must alight at terminal
        assert alighting == initial_passengers, \
            f"At terminal stop with {initial_passengers} passengers, " \
            f"all should alight, but got {alighting}"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        initial_passengers=st.integers(min_value=1, max_value=80),
        capacity=st.integers(min_value=50, max_value=100)
    )
    def test_terminal_stop_with_no_waiting_passengers(
        self, bus_id, initial_passengers, capacity
    ):
        """
        Test terminal stop behavior when no passengers are waiting.
        
        If no one is waiting at the terminal, the bus should be empty after the stop.
        """
        from src.feeders.bus_movement_simulator import calculate_alighting, calculate_boarding
        
        people_at_terminal = 0  # No one waiting
        
        # Calculate alighting and boarding
        alighting = calculate_alighting(initial_passengers, is_terminal=True)
        boarding = calculate_boarding(people_at_terminal, capacity)
        
        # New count should be zero (everyone alights, no one boards)
        new_passenger_count = initial_passengers - alighting + boarding
        
        assert new_passenger_count == 0, \
            f"With no waiting passengers at terminal, bus should be empty, got {new_passenger_count}"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        initial_passengers=st.integers(min_value=20, max_value=80),
        people_at_terminal=st.integers(min_value=10, max_value=30),
        capacity=st.integers(min_value=50, max_value=100)
    )
    def test_terminal_vs_regular_stop_alighting_difference(
        self, bus_id, initial_passengers, people_at_terminal, capacity
    ):
        """
        Test that terminal stops have different alighting behavior than regular stops.
        
        At terminal stops, everyone alights. At regular stops, only a percentage alights.
        """
        from src.feeders.bus_movement_simulator import calculate_alighting
        
        # Calculate alighting at terminal stop
        terminal_alighting = calculate_alighting(initial_passengers, is_terminal=True)
        
        # Calculate alighting at regular stop (run multiple times due to randomness)
        regular_alighting_counts = []
        for _ in range(10):
            regular_alighting = calculate_alighting(initial_passengers, is_terminal=False)
            regular_alighting_counts.append(regular_alighting)
        
        avg_regular_alighting = sum(regular_alighting_counts) / len(regular_alighting_counts)
        
        # Terminal should have everyone alight
        assert terminal_alighting == initial_passengers, \
            f"Terminal stop should have all passengers alight"
        
        # Regular stops should have fewer people alight (on average)
        # Regular stops use 20-40% alighting rate
        assert avg_regular_alighting < initial_passengers, \
            f"Regular stops should have fewer passengers alight than terminal stops"
        
        # Regular alighting should be roughly 20-40% of passengers
        expected_range_low = initial_passengers * 0.15  # Allow some variance
        expected_range_high = initial_passengers * 0.45
        assert expected_range_low <= avg_regular_alighting <= expected_range_high, \
            f"Regular stop alighting ({avg_regular_alighting:.1f}) should be 20-40% of " \
            f"passengers ({initial_passengers}), expected range: {expected_range_low:.1f}-{expected_range_high:.1f}"


class TestProperty16PassengerCountInvariantDuringTransit:
    """
    Property 16: Passenger count invariant during transit
    
    **Validates: Requirements 4.1**
    
    For any sequence of bus position data points where the bus is between stops
    (next_stop_id remains constant and distance_to_next_stop is decreasing),
    the passenger_count should remain constant.
    """
    
    @staticmethod
    def _create_test_route() -> Route:
        """Create a test route for transit testing."""
        stops = [
            Stop(
                stop_id="S001",
                name="Start",
                latitude=40.4657,
                longitude=-3.6886,
                is_terminal=True,
                base_arrival_rate=2.5
            ),
            Stop(
                stop_id="S002",
                name="Middle",
                latitude=40.4500,
                longitude=-3.6900,
                is_terminal=False,
                base_arrival_rate=1.8
            ),
            Stop(
                stop_id="S003",
                name="End",
                latitude=40.4400,
                longitude=-3.6950,
                is_terminal=True,
                base_arrival_rate=2.0
            ),
        ]
        return Route(line_id="L1", name="Test Route", stops=stops)
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        initial_passengers=st.integers(min_value=0, max_value=80),
        speed_kmh=st.floats(min_value=10.0, max_value=60.0, allow_nan=False, allow_infinity=False),
        num_movements=st.integers(min_value=2, max_value=10),
        time_interval_seconds=st.integers(min_value=5, max_value=30)
    )
    def test_passenger_count_constant_between_stops(
        self, bus_id, initial_passengers, speed_kmh, num_movements, time_interval_seconds
    ):
        """
        Test that passenger count remains constant while traveling between stops.
        
        For any bus traveling between stops (not reaching any stops), the passenger
        count should remain unchanged across multiple position updates.
        """
        from src.feeders.bus_movement_simulator import simulate_bus_movement
        
        route = self._create_test_route()
        
        # Create bus state starting at position 0.1 (after first stop)
        # This ensures we have room to move without hitting the next stop immediately
        bus = BusState(
            bus_id=bus_id,
            line_id=route.line_id,
            capacity=100,
            passenger_count=initial_passengers,
            position_on_route=0.1,
            speed=speed_kmh,
            at_stop=False
        )
        
        # Track passenger count across movements
        passenger_counts = [bus.passenger_count]
        previous_next_stop_id = None
        
        # Simulate multiple movements
        for i in range(num_movements):
            time_delta = timedelta(seconds=time_interval_seconds)
            
            # Simulate movement
            position_data, stops_reached = simulate_bus_movement(bus, route, time_delta)
            
            # If we reached any stops, this test doesn't apply (we're testing transit only)
            if stops_reached:
                # Skip this iteration - we reached a stop
                continue
            
            # Track the next stop ID
            current_next_stop_id = position_data.next_stop_id
            
            # If next_stop_id changed, we passed a stop (shouldn't happen if stops_reached is empty)
            if previous_next_stop_id is not None and current_next_stop_id != previous_next_stop_id:
                # Stop changed, skip this test case
                continue
            
            previous_next_stop_id = current_next_stop_id
            
            # Record passenger count
            passenger_counts.append(position_data.passenger_count)
            
            # Verify passenger count hasn't changed
            assert position_data.passenger_count == initial_passengers, \
                f"Passenger count changed from {initial_passengers} to {position_data.passenger_count} " \
                f"during transit (movement {i+1}, no stops reached)"
        
        # Verify all passenger counts are the same
        if len(passenger_counts) > 1:
            assert all(count == initial_passengers for count in passenger_counts), \
                f"Passenger count varied during transit: {passenger_counts}, expected constant {initial_passengers}"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        initial_passengers=st.integers(min_value=0, max_value=80),
        speed_kmh=st.floats(min_value=20.0, max_value=50.0, allow_nan=False, allow_infinity=False)
    )
    def test_single_movement_preserves_passenger_count(
        self, bus_id, initial_passengers, speed_kmh
    ):
        """
        Test that a single movement without reaching a stop preserves passenger count.
        
        This is a simpler version focusing on a single movement step.
        """
        from src.feeders.bus_movement_simulator import simulate_bus_movement
        
        route = self._create_test_route()
        
        # Create bus state at position 0.15 (well between stops)
        bus = BusState(
            bus_id=bus_id,
            line_id=route.line_id,
            capacity=100,
            passenger_count=initial_passengers,
            position_on_route=0.15,
            speed=speed_kmh,
            at_stop=False
        )
        
        # Simulate a short movement (10 seconds)
        time_delta = timedelta(seconds=10)
        position_data, stops_reached = simulate_bus_movement(bus, route, time_delta)
        
        # If no stops were reached, passenger count should be unchanged
        if not stops_reached:
            assert position_data.passenger_count == initial_passengers, \
                f"Passenger count changed from {initial_passengers} to {position_data.passenger_count} " \
                f"without reaching any stops"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        initial_passengers=st.integers(min_value=10, max_value=80),
        speed_kmh=st.floats(min_value=30.0, max_value=60.0, allow_nan=False, allow_infinity=False)
    )
    def test_distance_decreases_while_passenger_count_constant(
        self, bus_id, initial_passengers, speed_kmh
    ):
        """
        Test that as distance to next stop decreases, passenger count stays constant.
        
        This verifies the core property: while approaching a stop (distance decreasing),
        passengers don't change.
        """
        from src.feeders.bus_movement_simulator import simulate_bus_movement
        
        route = self._create_test_route()
        
        # Start at position 0.2
        bus = BusState(
            bus_id=bus_id,
            line_id=route.line_id,
            capacity=100,
            passenger_count=initial_passengers,
            position_on_route=0.2,
            speed=speed_kmh,
            at_stop=False
        )
        
        # Simulate first movement
        time_delta = timedelta(seconds=15)
        position_data_1, stops_1 = simulate_bus_movement(bus, route, time_delta)
        
        # If we reached a stop, skip this test
        if stops_1:
            return
        
        distance_1 = position_data_1.distance_to_next_stop
        passengers_1 = position_data_1.passenger_count
        
        # Simulate second movement
        position_data_2, stops_2 = simulate_bus_movement(bus, route, time_delta)
        
        # If we reached a stop, skip this test
        if stops_2:
            return
        
        distance_2 = position_data_2.distance_to_next_stop
        passengers_2 = position_data_2.passenger_count
        
        # If next_stop_id changed, we passed a stop somehow, skip
        if position_data_1.next_stop_id != position_data_2.next_stop_id:
            return
        
        # Distance should have decreased (we're getting closer)
        assert distance_2 < distance_1, \
            f"Distance should decrease as bus approaches stop, " \
            f"got {distance_1:.2f}m -> {distance_2:.2f}m"
        
        # Passenger count should remain constant
        assert passengers_1 == passengers_2 == initial_passengers, \
            f"Passenger count should remain constant ({initial_passengers}) while approaching stop, " \
            f"got {passengers_1} -> {passengers_2}"


class TestProperty20EventBridgePublicationForPositionUpdates:
    """
    Property 20: EventBridge publication for position updates
    
    **Validates: Requirements 6.1**
    
    For any bus position update generated by the Bus Position Feeder, an event
    with matching bus_id, timestamp, and coordinates should be published to
    EventBridge within 2 seconds.
    """
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps,
        latitude=latitudes,
        longitude=longitudes,
        passenger_count=passenger_counts,
        next_stop_id=entity_ids,
        distance=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        speed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_position_update_publishes_event(
        self, bus_id, line_id, timestamp, latitude, longitude,
        passenger_count, next_stop_id, distance, speed
    ):
        """
        Test that bus position updates result in EventBridge event publication.
        
        For any bus position update, an event should be published to EventBridge
        with matching data fields.
        """
        from unittest.mock import Mock, patch
        from src.common.eventbridge_client import EventBridgeClient
        
        # Create a mock EventBridge client
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        # Publish bus position event
        result = eb_client.publish_bus_position_event(
            bus_id=bus_id,
            line_id=line_id,
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude,
            passenger_count=passenger_count,
            next_stop_id=next_stop_id,
            distance_to_next_stop=distance,
            speed=speed
        )
        
        # Verify the event was published successfully
        assert result is True, "Event publication should succeed"
        
        # Verify put_events was called
        assert mock_client.put_events.called, "put_events should be called"
        
        # Get the call arguments
        call_args = mock_client.put_events.call_args
        entries = call_args[1]['Entries']
        
        # Verify event structure
        assert len(entries) == 1, "Should publish exactly one event"
        
        entry = entries[0]
        assert entry['Source'] == 'bus-simulator', "Event source should be 'bus-simulator'"
        assert entry['DetailType'] == 'bus.position.updated', "Event type should be 'bus.position.updated'"
        assert entry['EventBusName'] == 'test-bus', "Event bus name should match"
        
        # Parse and verify event detail
        import json
        detail = json.loads(entry['Detail'])
        
        assert detail['bus_id'] == bus_id, f"bus_id should match: expected {bus_id}, got {detail['bus_id']}"
        assert detail['line_id'] == line_id, f"line_id should match"
        assert detail['timestamp'] == timestamp.isoformat(), f"timestamp should match"
        assert detail['latitude'] == latitude, f"latitude should match"
        assert detail['longitude'] == longitude, f"longitude should match"
        assert detail['passenger_count'] == passenger_count, f"passenger_count should match"
        assert detail['next_stop_id'] == next_stop_id, f"next_stop_id should match"
        assert detail['distance_to_next_stop'] == distance, f"distance_to_next_stop should match"
        assert detail['speed'] == speed, f"speed should match"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps,
        latitude=latitudes,
        longitude=longitudes,
        passenger_count=passenger_counts,
        next_stop_id=entity_ids,
        distance=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        speed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_position_update_retry_on_failure(
        self, bus_id, line_id, timestamp, latitude, longitude,
        passenger_count, next_stop_id, distance, speed
    ):
        """
        Test that EventBridge client retries on failure with exponential backoff.
        
        The client should retry up to max_retries times before giving up.
        """
        from unittest.mock import Mock, patch
        from src.common.eventbridge_client import EventBridgeClient
        from botocore.exceptions import ClientError
        
        # Create a mock client that fails twice then succeeds
        mock_client = Mock()
        mock_client.put_events.side_effect = [
            ClientError({'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}}, 'PutEvents'),
            ClientError({'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}}, 'PutEvents'),
            {'FailedEntryCount': 0, 'Entries': []}
        ]
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client,
            max_retries=3
        )
        
        # Publish bus position event
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = eb_client.publish_bus_position_event(
                bus_id=bus_id,
                line_id=line_id,
                timestamp=timestamp,
                latitude=latitude,
                longitude=longitude,
                passenger_count=passenger_count,
                next_stop_id=next_stop_id,
                distance_to_next_stop=distance,
                speed=speed
            )
        
        # Verify the event was eventually published successfully
        assert result is True, "Event publication should succeed after retries"
        
        # Verify put_events was called 3 times (2 failures + 1 success)
        assert mock_client.put_events.call_count == 3, \
            f"put_events should be called 3 times, was called {mock_client.put_events.call_count} times"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps,
        latitude=latitudes,
        longitude=longitudes,
        passenger_count=passenger_counts,
        next_stop_id=entity_ids,
        distance=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
        speed=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    def test_position_update_fails_after_max_retries(
        self, bus_id, line_id, timestamp, latitude, longitude,
        passenger_count, next_stop_id, distance, speed
    ):
        """
        Test that EventBridge client gives up after max_retries failures.
        
        After max_retries attempts, the client should return False and log a warning.
        """
        from unittest.mock import Mock, patch
        from src.common.eventbridge_client import EventBridgeClient
        from botocore.exceptions import ClientError
        
        # Create a mock client that always fails
        mock_client = Mock()
        mock_client.put_events.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}},
            'PutEvents'
        )
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client,
            max_retries=3
        )
        
        # Publish bus position event
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = eb_client.publish_bus_position_event(
                bus_id=bus_id,
                line_id=line_id,
                timestamp=timestamp,
                latitude=latitude,
                longitude=longitude,
                passenger_count=passenger_count,
                next_stop_id=next_stop_id,
                distance_to_next_stop=distance,
                speed=speed
            )
        
        # Verify the event publication failed
        assert result is False, "Event publication should fail after max retries"
        
        # Verify put_events was called max_retries times
        assert mock_client.put_events.call_count == 3, \
            f"put_events should be called 3 times, was called {mock_client.put_events.call_count} times"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps
    )
    def test_multiple_position_updates_publish_separately(
        self, bus_id, line_id, timestamp
    ):
        """
        Test that multiple position updates result in separate event publications.
        
        Each position update should generate its own event.
        """
        from unittest.mock import Mock
        from src.common.eventbridge_client import EventBridgeClient
        
        # Create a mock EventBridge client
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        # Publish multiple position events
        num_updates = 5
        for i in range(num_updates):
            eb_client.publish_bus_position_event(
                bus_id=bus_id,
                line_id=line_id,
                timestamp=timestamp,
                latitude=40.4657 + i * 0.001,
                longitude=-3.6886 + i * 0.001,
                passenger_count=20 + i,
                next_stop_id=f"S{i:03d}",
                distance_to_next_stop=1000.0 - i * 100,
                speed=30.0
            )
        
        # Verify put_events was called for each update
        assert mock_client.put_events.call_count == num_updates, \
            f"put_events should be called {num_updates} times, was called {mock_client.put_events.call_count} times"


class TestProperty22CoordinatedEventsAtBusArrivals:
    """
    Property 22: Coordinated events at bus arrivals
    
    **Validates: Requirements 6.3**
    
    For any bus arrival at a stop, both a bus position update event and a people
    count update event should be published to EventBridge within 2 seconds of each other.
    """
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        stop_id=entity_ids,
        timestamp=timestamps,
        passengers_boarding=st.integers(min_value=0, max_value=50),
        passengers_alighting=st.integers(min_value=0, max_value=50),
        bus_passenger_count=passenger_counts,
        stop_people_count=passenger_counts
    )
    def test_arrival_publishes_coordinated_event(
        self, bus_id, line_id, stop_id, timestamp,
        passengers_boarding, passengers_alighting,
        bus_passenger_count, stop_people_count
    ):
        """
        Test that bus arrivals publish coordinated events with both bus and stop data.
        
        For any bus arrival, a single coordinated event should be published containing
        both bus and stop state information.
        """
        from unittest.mock import Mock
        from src.common.eventbridge_client import EventBridgeClient
        
        # Create a mock EventBridge client
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        # Publish bus arrival event
        result = eb_client.publish_bus_arrival_events(
            bus_id=bus_id,
            line_id=line_id,
            stop_id=stop_id,
            timestamp=timestamp,
            passengers_boarding=passengers_boarding,
            passengers_alighting=passengers_alighting,
            bus_passenger_count=bus_passenger_count,
            stop_people_count=stop_people_count
        )
        
        # Verify the event was published successfully
        assert result is True, "Event publication should succeed"
        
        # Verify put_events was called
        assert mock_client.put_events.called, "put_events should be called"
        
        # Get the call arguments
        call_args = mock_client.put_events.call_args
        entries = call_args[1]['Entries']
        
        # Verify event structure
        assert len(entries) == 1, "Should publish exactly one coordinated event"
        
        entry = entries[0]
        assert entry['Source'] == 'bus-simulator', "Event source should be 'bus-simulator'"
        assert entry['DetailType'] == 'bus.arrival', "Event type should be 'bus.arrival'"
        assert entry['EventBusName'] == 'test-bus', "Event bus name should match"
        
        # Parse and verify event detail
        import json
        detail = json.loads(entry['Detail'])
        
        # Verify bus-related fields
        assert detail['bus_id'] == bus_id, f"bus_id should match"
        assert detail['line_id'] == line_id, f"line_id should match"
        assert detail['timestamp'] == timestamp.isoformat(), f"timestamp should match"
        assert detail['passengers_boarding'] == passengers_boarding, f"passengers_boarding should match"
        assert detail['passengers_alighting'] == passengers_alighting, f"passengers_alighting should match"
        assert detail['bus_passenger_count'] == bus_passenger_count, f"bus_passenger_count should match"
        
        # Verify stop-related fields
        assert detail['stop_id'] == stop_id, f"stop_id should match"
        assert detail['stop_people_count'] == stop_people_count, f"stop_people_count should match"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        stop_id=entity_ids,
        timestamp=timestamps,
        passengers_boarding=st.integers(min_value=0, max_value=50),
        passengers_alighting=st.integers(min_value=0, max_value=50),
        bus_passenger_count=passenger_counts,
        stop_people_count=passenger_counts
    )
    def test_arrival_event_contains_both_bus_and_stop_data(
        self, bus_id, line_id, stop_id, timestamp,
        passengers_boarding, passengers_alighting,
        bus_passenger_count, stop_people_count
    ):
        """
        Test that arrival events contain complete data for both bus and stop.
        
        The coordinated event should include all necessary fields to update
        both bus position and stop people count.
        """
        from unittest.mock import Mock
        from src.common.eventbridge_client import EventBridgeClient
        import json
        
        # Create a mock EventBridge client
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        # Publish bus arrival event
        eb_client.publish_bus_arrival_events(
            bus_id=bus_id,
            line_id=line_id,
            stop_id=stop_id,
            timestamp=timestamp,
            passengers_boarding=passengers_boarding,
            passengers_alighting=passengers_alighting,
            bus_passenger_count=bus_passenger_count,
            stop_people_count=stop_people_count
        )
        
        # Get the published event
        call_args = mock_client.put_events.call_args
        entries = call_args[1]['Entries']
        entry = entries[0]
        detail = json.loads(entry['Detail'])
        
        # Verify all required fields are present
        required_fields = [
            'bus_id', 'line_id', 'stop_id', 'timestamp',
            'passengers_boarding', 'passengers_alighting',
            'bus_passenger_count', 'stop_people_count'
        ]
        
        for field in required_fields:
            assert field in detail, f"Event detail should contain '{field}' field"
        
        # Verify field types
        assert isinstance(detail['bus_id'], str), "bus_id should be string"
        assert isinstance(detail['line_id'], str), "line_id should be string"
        assert isinstance(detail['stop_id'], str), "stop_id should be string"
        assert isinstance(detail['timestamp'], str), "timestamp should be ISO string"
        assert isinstance(detail['passengers_boarding'], int), "passengers_boarding should be int"
        assert isinstance(detail['passengers_alighting'], int), "passengers_alighting should be int"
        assert isinstance(detail['bus_passenger_count'], int), "bus_passenger_count should be int"
        assert isinstance(detail['stop_people_count'], int), "stop_people_count should be int"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        stop_id=entity_ids,
        timestamp=timestamps,
        passengers_boarding=st.integers(min_value=0, max_value=50),
        passengers_alighting=st.integers(min_value=0, max_value=50),
        bus_passenger_count=passenger_counts,
        stop_people_count=passenger_counts
    )
    def test_arrival_event_retry_on_failure(
        self, bus_id, line_id, stop_id, timestamp,
        passengers_boarding, passengers_alighting,
        bus_passenger_count, stop_people_count
    ):
        """
        Test that arrival event publication retries on failure.
        
        The client should retry failed publications with exponential backoff.
        """
        from unittest.mock import Mock, patch
        from src.common.eventbridge_client import EventBridgeClient
        from botocore.exceptions import ClientError
        
        # Create a mock client that fails once then succeeds
        mock_client = Mock()
        mock_client.put_events.side_effect = [
            ClientError({'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}}, 'PutEvents'),
            {'FailedEntryCount': 0, 'Entries': []}
        ]
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client,
            max_retries=3
        )
        
        # Publish bus arrival event
        with patch('time.sleep'):  # Mock sleep to speed up test
            result = eb_client.publish_bus_arrival_events(
                bus_id=bus_id,
                line_id=line_id,
                stop_id=stop_id,
                timestamp=timestamp,
                passengers_boarding=passengers_boarding,
                passengers_alighting=passengers_alighting,
                bus_passenger_count=bus_passenger_count,
                stop_people_count=stop_people_count
            )
        
        # Verify the event was eventually published successfully
        assert result is True, "Event publication should succeed after retry"
        
        # Verify put_events was called twice (1 failure + 1 success)
        assert mock_client.put_events.call_count == 2, \
            f"put_events should be called 2 times, was called {mock_client.put_events.call_count} times"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        timestamp=timestamps
    )
    def test_multiple_arrivals_publish_separately(
        self, bus_id, line_id, timestamp
    ):
        """
        Test that multiple bus arrivals result in separate event publications.
        
        Each arrival should generate its own coordinated event.
        """
        from unittest.mock import Mock
        from src.common.eventbridge_client import EventBridgeClient
        
        # Create a mock EventBridge client
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        # Publish multiple arrival events
        num_arrivals = 5
        for i in range(num_arrivals):
            eb_client.publish_bus_arrival_events(
                bus_id=bus_id,
                line_id=line_id,
                stop_id=f"S{i:03d}",
                timestamp=timestamp,
                passengers_boarding=5 + i,
                passengers_alighting=3 + i,
                bus_passenger_count=20 + i,
                stop_people_count=10 - i
            )
        
        # Verify put_events was called for each arrival
        assert mock_client.put_events.call_count == num_arrivals, \
            f"put_events should be called {num_arrivals} times, was called {mock_client.put_events.call_count} times"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        line_id=entity_ids,
        stop_id=entity_ids,
        timestamp=timestamps,
        passengers_boarding=st.integers(min_value=0, max_value=50),
        passengers_alighting=st.integers(min_value=0, max_value=50),
        bus_passenger_count=passenger_counts,
        stop_people_count=passenger_counts
    )
    def test_arrival_event_timestamp_consistency(
        self, bus_id, line_id, stop_id, timestamp,
        passengers_boarding, passengers_alighting,
        bus_passenger_count, stop_people_count
    ):
        """
        Test that arrival events use consistent timestamps.
        
        The timestamp in the event should match the provided timestamp,
        ensuring coordination between bus and stop updates.
        """
        from unittest.mock import Mock
        from src.common.eventbridge_client import EventBridgeClient
        import json
        from datetime import datetime
        
        # Create a mock EventBridge client
        mock_client = Mock()
        mock_client.put_events.return_value = {
            'FailedEntryCount': 0,
            'Entries': []
        }
        
        # Create EventBridge client with mock
        eb_client = EventBridgeClient(
            event_bus_name='test-bus',
            client=mock_client
        )
        
        # Publish bus arrival event
        eb_client.publish_bus_arrival_events(
            bus_id=bus_id,
            line_id=line_id,
            stop_id=stop_id,
            timestamp=timestamp,
            passengers_boarding=passengers_boarding,
            passengers_alighting=passengers_alighting,
            bus_passenger_count=bus_passenger_count,
            stop_people_count=stop_people_count
        )
        
        # Get the published event
        call_args = mock_client.put_events.call_args
        entries = call_args[1]['Entries']
        entry = entries[0]
        detail = json.loads(entry['Detail'])
        
        # Verify timestamp matches
        event_timestamp = datetime.fromisoformat(detail['timestamp'])
        
        # Timestamps should be identical (within microsecond precision)
        time_diff = abs((event_timestamp - timestamp).total_seconds())
        assert time_diff < 0.001, \
            f"Event timestamp should match provided timestamp within 1ms, " \
            f"difference: {time_diff}s"


class TestProperty18CrossEntityConsistencyAtBusArrivals:
    """
    Property 18: Cross-entity consistency at bus arrivals
    
    **Validates: Requirements 4.2, 4.4**
    
    For any bus arrival event, the sum of passengers alighting and the stop's
    passenger count before arrival should equal or exceed the number of passengers
    boarding (cannot board more than available capacity and waiting passengers).
    """
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        stop_id=entity_ids,
        people_at_stop=st.integers(min_value=0, max_value=100),
        bus_capacity=st.integers(min_value=50, max_value=100),
        current_passengers=st.integers(min_value=0, max_value=80),
        is_terminal=st.booleans()
    )
    def test_boarding_cannot_exceed_available_resources(
        self, bus_id, stop_id, people_at_stop, bus_capacity, current_passengers, is_terminal
    ):
        """
        Test that boarding passengers cannot exceed available capacity and waiting passengers.
        
        For any bus arrival, the number of passengers boarding should be:
        - At most the number of people waiting at the stop
        - At most the available capacity on the bus (after alighting)
        """
        from src.feeders.bus_movement_simulator import calculate_alighting, calculate_boarding
        
        # Ensure current passengers doesn't exceed capacity
        current_passengers = min(current_passengers, bus_capacity)
        
        # Calculate alighting
        alighting = calculate_alighting(current_passengers, is_terminal)
        
        # Calculate available capacity after alighting
        available_capacity = bus_capacity - (current_passengers - alighting)
        
        # Calculate boarding
        boarding = calculate_boarding(people_at_stop, available_capacity)
        
        # Verify boarding constraints
        assert boarding <= people_at_stop, \
            f"Cannot board more passengers ({boarding}) than are waiting at stop ({people_at_stop})"
        
        assert boarding <= available_capacity, \
            f"Cannot board more passengers ({boarding}) than available capacity ({available_capacity})"
        
        # Verify the mathematical consistency
        # After arrival: passengers = current - alighting + boarding
        new_passenger_count = current_passengers - alighting + boarding
        
        assert new_passenger_count <= bus_capacity, \
            f"After arrival, passenger count ({new_passenger_count}) exceeds capacity ({bus_capacity})"
        
        assert new_passenger_count >= 0, \
            f"After arrival, passenger count must be non-negative, got {new_passenger_count}"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        stop_id=entity_ids,
        people_at_stop=st.integers(min_value=50, max_value=100),
        bus_capacity=st.integers(min_value=50, max_value=100),
        current_passengers=st.integers(min_value=40, max_value=80)
    )
    def test_boarding_limited_by_capacity(
        self, bus_id, stop_id, people_at_stop, bus_capacity, current_passengers
    ):
        """
        Test that boarding is limited by bus capacity even when many people are waiting.
        
        When many people are waiting but the bus has limited capacity, boarding
        should be capped at the available capacity.
        """
        from src.feeders.bus_movement_simulator import calculate_alighting, calculate_boarding
        
        # Ensure current passengers doesn't exceed capacity
        current_passengers = min(current_passengers, bus_capacity)
        
        # Use regular stop (not terminal) for this test
        alighting = calculate_alighting(current_passengers, is_terminal=False)
        
        # Calculate available capacity
        available_capacity = bus_capacity - (current_passengers - alighting)
        
        # Calculate boarding
        boarding = calculate_boarding(people_at_stop, available_capacity)
        
        # Boarding should not exceed available capacity
        assert boarding <= available_capacity, \
            f"Boarding ({boarding}) should not exceed available capacity ({available_capacity})"
        
        # Verify final count doesn't exceed capacity
        final_count = current_passengers - alighting + boarding
        assert final_count <= bus_capacity, \
            f"Final passenger count ({final_count}) exceeds capacity ({bus_capacity})"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        stop_id=entity_ids,
        people_at_stop=st.integers(min_value=0, max_value=20),
        bus_capacity=st.integers(min_value=50, max_value=100),
        current_passengers=st.integers(min_value=0, max_value=30)
    )
    def test_boarding_limited_by_waiting_passengers(
        self, bus_id, stop_id, people_at_stop, bus_capacity, current_passengers
    ):
        """
        Test that boarding is limited by the number of waiting passengers.
        
        When the bus has plenty of capacity but few people are waiting, boarding
        should be capped at the number of waiting passengers.
        """
        from src.feeders.bus_movement_simulator import calculate_alighting, calculate_boarding
        
        # Ensure current passengers doesn't exceed capacity
        current_passengers = min(current_passengers, bus_capacity)
        
        # Use regular stop
        alighting = calculate_alighting(current_passengers, is_terminal=False)
        
        # Calculate available capacity (should be large)
        available_capacity = bus_capacity - (current_passengers - alighting)
        
        # Calculate boarding
        boarding = calculate_boarding(people_at_stop, available_capacity)
        
        # Boarding should not exceed people waiting
        assert boarding <= people_at_stop, \
            f"Boarding ({boarding}) should not exceed people waiting ({people_at_stop})"
    
    @settings(max_examples=100)
    @given(
        bus_id=entity_ids,
        stop_id=entity_ids,
        people_at_stop=st.integers(min_value=10, max_value=50),
        bus_capacity=st.integers(min_value=50, max_value=100),
        current_passengers=st.integers(min_value=30, max_value=80)
    )
    def test_stop_count_decreases_by_boarding_amount(
        self, bus_id, stop_id, people_at_stop, bus_capacity, current_passengers
    ):
        """
        Test that the stop's passenger count decreases by the boarding amount.
        
        This verifies cross-entity consistency: passengers boarding the bus
        should leave the stop.
        """
        from src.feeders.bus_movement_simulator import calculate_alighting, calculate_boarding
        
        # Ensure current passengers doesn't exceed capacity
        current_passengers = min(current_passengers, bus_capacity)
        
        # Calculate alighting and boarding
        alighting = calculate_alighting(current_passengers, is_terminal=False)
        available_capacity = bus_capacity - (current_passengers - alighting)
        boarding = calculate_boarding(people_at_stop, available_capacity)
        
        # New stop count should be: previous count - boarding
        # (assuming no new arrivals during the boarding process)
        new_stop_count = people_at_stop - boarding
        
        # Verify consistency
        assert new_stop_count >= 0, \
            f"Stop count after boarding must be non-negative, got {new_stop_count}"
        
        assert new_stop_count == people_at_stop - boarding, \
            f"Stop count should decrease by boarding amount: " \
            f"{people_at_stop} - {boarding} = {new_stop_count}"
    
    @settings(max_examples=50)
    @given(
        bus_id=entity_ids,
        stop_id=entity_ids,
        people_at_stop=st.integers(min_value=0, max_value=100),
        bus_capacity=st.integers(min_value=50, max_value=100),
        current_passengers=st.integers(min_value=0, max_value=80)
    )
    def test_arrival_event_consistency(
        self, bus_id, stop_id, people_at_stop, bus_capacity, current_passengers
    ):
        """
        Test that a complete bus arrival event maintains consistency.
        
        This is a comprehensive test that verifies all aspects of the arrival:
        - Alighting is valid
        - Boarding is valid and constrained
        - Final passenger count is valid
        - Stop count change is valid
        """
        from src.feeders.bus_movement_simulator import calculate_alighting, calculate_boarding
        
        # Ensure current passengers doesn't exceed capacity
        current_passengers = min(current_passengers, bus_capacity)
        
        # Simulate arrival at regular stop
        is_terminal = False
        
        # Calculate alighting
        alighting = calculate_alighting(current_passengers, is_terminal)
        assert 0 <= alighting <= current_passengers, \
            f"Alighting ({alighting}) must be between 0 and current passengers ({current_passengers})"
        
        # Calculate available capacity
        available_capacity = bus_capacity - (current_passengers - alighting)
        assert available_capacity >= 0, \
            f"Available capacity must be non-negative, got {available_capacity}"
        
        # Calculate boarding
        boarding = calculate_boarding(people_at_stop, available_capacity)
        assert boarding >= 0, f"Boarding must be non-negative, got {boarding}"
        assert boarding <= people_at_stop, \
            f"Boarding ({boarding}) cannot exceed waiting passengers ({people_at_stop})"
        assert boarding <= available_capacity, \
            f"Boarding ({boarding}) cannot exceed available capacity ({available_capacity})"
        
        # Calculate final states
        final_bus_count = current_passengers - alighting + boarding
        final_stop_count = people_at_stop - boarding
        
        # Verify final states
        assert 0 <= final_bus_count <= bus_capacity, \
            f"Final bus count ({final_bus_count}) must be between 0 and capacity ({bus_capacity})"
        assert final_stop_count >= 0, \
            f"Final stop count must be non-negative, got {final_stop_count}"
        
        # Verify conservation: total people before = total people after
        # (alighting passengers are not counted as they left the system at this stop)
        total_before = current_passengers + people_at_stop
        total_after = final_bus_count + final_stop_count + alighting
        assert total_before == total_after, \
            f"Total people should be conserved: before={total_before}, after={total_after}"


class TestProperty1LatestPeopleCountQueryCorrectness:
    """
    Property 1: Latest people count query correctness
    
    **Validates: Requirements 1.1, 5.2**
    
    For any valid bus stop ID, querying the people count API with mode=latest should
    return the most recent passenger count data point from Timestream, with timestamp,
    count, and line IDs matching the stored data.
    """
    
    # Valid stop IDs from configuration
    VALID_STOP_IDS = [
        'S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007',  # Line L1
        'S101', 'S102', 'S103', 'S104', 'S105', 'S106',          # Line L2
        'S201', 'S202', 'S203', 'S204', 'S205'                   # Line L3
    ]
    
    @settings(max_examples=100)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS),
        count=passenger_counts,
        line_ids_list=st.lists(
            st.sampled_from(['L1', 'L2', 'L3']),
            min_size=1,
            max_size=3,
            unique=True
        ),
        timestamp=timestamps
    )
    def test_latest_query_returns_most_recent_data(
        self, stop_id, count, line_ids_list, timestamp
    ):
        """
        Test that latest query returns the most recent data point from Timestream.
        
        For any valid stop ID, when data exists in Timestream, the API should return
        the most recent data point with all fields matching the stored data.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Mock Timestream response with the most recent data
        mock_timestream_response = {
            'rows': [{
                'stop_id': stop_id,
                'time': timestamp.isoformat(),
                'count': str(count),
                'line_ids': ','.join(line_ids_list)
            }]
        }
        
        # Create API Gateway event for latest query
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify the response
            assert response['statusCode'] == 200, \
                f"Expected status 200, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify all fields match the stored data
            assert body['stop_id'] == stop_id, \
                f"Expected stop_id {stop_id}, got {body['stop_id']}"
            assert body['count'] == count, \
                f"Expected count {count}, got {body['count']}"
            assert body['timestamp'] == timestamp.isoformat(), \
                f"Expected timestamp {timestamp.isoformat()}, got {body['timestamp']}"
            assert set(body['line_ids']) == set(line_ids_list), \
                f"Expected line_ids {line_ids_list}, got {body['line_ids']}"
            
            # Verify Timestream was queried correctly
            mock_client.query_latest.assert_called_once()
            call_args = mock_client.query_latest.call_args
            assert call_args[1]['dimensions']['stop_id'] == stop_id, \
                "Timestream query should use the correct stop_id"
    
    @settings(max_examples=100)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS),
        count=passenger_counts,
        timestamp=timestamps
    )
    def test_latest_query_with_latest_parameter(self, stop_id, count, timestamp):
        """
        Test that latest query works with 'latest' query parameter.
        
        The API should accept both 'mode=latest' and 'latest' as query parameters.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Mock Timestream response
        mock_timestream_response = {
            'rows': [{
                'stop_id': stop_id,
                'time': timestamp.isoformat(),
                'count': str(count),
                'line_ids': 'L1'
            }]
        }
        
        # Create API Gateway event with 'latest' parameter
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'latest': ''}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify success
            assert response['statusCode'] == 200, \
                f"Latest query with 'latest' parameter should succeed"
    
    @settings(max_examples=50)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS)
    )
    def test_latest_query_with_no_data_returns_404(self, stop_id):
        """
        Test that latest query returns 404 when no data exists.
        
        When Timestream returns no data for a valid stop, the API should return 404.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Mock Timestream response with no data
        mock_timestream_response = {'rows': []}
        
        # Create API Gateway event
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 404 response
            assert response['statusCode'] == 404, \
                f"Expected status 404 when no data exists, got {response['statusCode']}"
            
            # Verify error message
            import json
            body = json.loads(response['body'])
            assert 'error' in body and body['error'] is True, \
                "Response should indicate an error"
            assert stop_id in body['message'], \
                f"Error message should mention the stop_id {stop_id}"


class TestProperty2HistoricalPeopleCountQueryCorrectness:
    """
    Property 2: Historical people count query correctness
    
    **Validates: Requirements 1.2, 5.3**
    
    For any valid bus stop ID and any timestamp in the past, querying the people count
    API with that timestamp should return the passenger count data point with the largest
    timestamp less than or equal to the query timestamp.
    """
    
    # Valid stop IDs from configuration
    VALID_STOP_IDS = [
        'S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007',  # Line L1
        'S101', 'S102', 'S103', 'S104', 'S105', 'S106',          # Line L2
        'S201', 'S202', 'S203', 'S204', 'S205'                   # Line L3
    ]
    
    @settings(max_examples=100)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS),
        query_timestamp=timestamps,
        data_timestamp=timestamps,
        count=passenger_counts,
        line_ids_list=st.lists(
            st.sampled_from(['L1', 'L2', 'L3']),
            min_size=1,
            max_size=3,
            unique=True
        )
    )
    def test_historical_query_returns_data_at_or_before_timestamp(
        self, stop_id, query_timestamp, data_timestamp, count, line_ids_list
    ):
        """
        Test that historical query returns data at or before the query timestamp.
        
        For any valid stop ID and timestamp, the API should return the most recent
        data point at or before that timestamp.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Ensure data timestamp is at or before query timestamp
        if data_timestamp > query_timestamp:
            data_timestamp, query_timestamp = query_timestamp, data_timestamp
        
        # Mock Timestream response with historical data
        mock_timestream_response = {
            'rows': [{
                'stop_id': stop_id,
                'time': data_timestamp.isoformat(),
                'count': str(count),
                'line_ids': ','.join(line_ids_list)
            }]
        }
        
        # Create API Gateway event for historical query
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {
                'timestamp': query_timestamp.isoformat()
            }
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_at_time.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify the response
            assert response['statusCode'] == 200, \
                f"Expected status 200, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify all fields match the stored data
            assert body['stop_id'] == stop_id, \
                f"Expected stop_id {stop_id}, got {body['stop_id']}"
            assert body['count'] == count, \
                f"Expected count {count}, got {body['count']}"
            assert body['timestamp'] == data_timestamp.isoformat(), \
                f"Expected timestamp {data_timestamp.isoformat()}, got {body['timestamp']}"
            assert set(body['line_ids']) == set(line_ids_list), \
                f"Expected line_ids {line_ids_list}, got {body['line_ids']}"
            
            # Verify Timestream was queried correctly
            mock_client.query_at_time.assert_called_once()
            call_args = mock_client.query_at_time.call_args
            assert call_args[1]['dimensions']['stop_id'] == stop_id, \
                "Timestream query should use the correct stop_id"
            assert call_args[1]['timestamp'] == query_timestamp, \
                "Timestream query should use the correct timestamp"
    
    @settings(max_examples=100)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS),
        query_timestamp=timestamps,
        count=passenger_counts
    )
    def test_historical_query_timestamp_parsing(
        self, stop_id, query_timestamp, count
    ):
        """
        Test that historical query correctly parses ISO8601 timestamps.
        
        The API should accept various ISO8601 formats including with/without timezone.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Mock Timestream response
        mock_timestream_response = {
            'rows': [{
                'stop_id': stop_id,
                'time': query_timestamp.isoformat(),
                'count': str(count),
                'line_ids': 'L1'
            }]
        }
        
        # Test with Z suffix (UTC)
        timestamp_str = query_timestamp.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'
        
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'timestamp': timestamp_str}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_at_time.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify success
            assert response['statusCode'] == 200, \
                f"Historical query should parse ISO8601 timestamp correctly"
    
    @settings(max_examples=50)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS),
        query_timestamp=timestamps
    )
    def test_historical_query_with_no_data_returns_404(
        self, stop_id, query_timestamp
    ):
        """
        Test that historical query returns 404 when no data exists at that time.
        
        When Timestream returns no data for a valid stop at the query time,
        the API should return 404.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Mock Timestream response with no data
        mock_timestream_response = {'rows': []}
        
        # Create API Gateway event
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {
                'timestamp': query_timestamp.isoformat()
            }
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_at_time.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 404 response
            assert response['statusCode'] == 404, \
                f"Expected status 404 when no data exists, got {response['statusCode']}"
    
    @settings(max_examples=50)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS)
    )
    def test_historical_query_with_invalid_timestamp_returns_400(self, stop_id):
        """
        Test that historical query returns 400 for invalid timestamp format.
        
        When an invalid timestamp is provided, the API should return 400 Bad Request.
        """
        from unittest.mock import patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Create API Gateway event with invalid timestamp
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'timestamp': 'invalid-timestamp'}
        }
        
        # Mock the Timestream client (shouldn't be called)
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 400 response
            assert response['statusCode'] == 400, \
                f"Expected status 400 for invalid timestamp, got {response['statusCode']}"
            
            # Verify error message mentions timestamp
            import json
            body = json.loads(response['body'])
            assert 'timestamp' in body['message'].lower(), \
                "Error message should mention timestamp issue"


# Valid stop IDs from configuration (module level for use in filters)
_VALID_STOP_IDS_FOR_PROPERTY3 = [
    'S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007',  # Line L1
    'S101', 'S102', 'S103', 'S104', 'S105', 'S106',          # Line L2
    'S201', 'S202', 'S203', 'S204', 'S205'                   # Line L3
]


class TestProperty3InvalidStopErrorHandling:
    """
    Property 3: Invalid stop error handling
    
    **Validates: Requirements 1.3**
    
    For any stop ID that does not exist in the system configuration, querying the
    people count API should return a 404 error with a descriptive message.
    """
    
    # Valid stop IDs from configuration
    VALID_STOP_IDS = _VALID_STOP_IDS_FOR_PROPERTY3
    
    @settings(max_examples=100)
    @given(
        invalid_stop_id=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'),
                min_codepoint=48,
                max_codepoint=122
            )
        ).filter(lambda x: x not in _VALID_STOP_IDS_FOR_PROPERTY3 and x.strip())
    )
    def test_invalid_stop_returns_404_for_latest_query(self, invalid_stop_id):
        """
        Test that querying an invalid stop ID returns 404 for latest query.
        
        For any stop ID that doesn't exist in the configuration, the API should
        return 404 with a descriptive error message.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Mock Timestream response with no data (stop doesn't exist)
        mock_timestream_response = {'rows': []}
        
        # Create API Gateway event for latest query
        event = {
            'pathParameters': {'stop_id': invalid_stop_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 404 response
            assert response['statusCode'] == 404, \
                f"Expected status 404 for invalid stop, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify error structure
            assert 'error' in body and body['error'] is True, \
                "Response should indicate an error"
            assert 'message' in body, \
                "Response should include an error message"
            assert invalid_stop_id in body['message'], \
                f"Error message should mention the invalid stop_id {invalid_stop_id}"
    
    @settings(max_examples=100)
    @given(
        invalid_stop_id=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=('Lu', 'Ll', 'Nd'),
                min_codepoint=48,
                max_codepoint=122
            )
        ).filter(lambda x: x not in _VALID_STOP_IDS_FOR_PROPERTY3 and x.strip()),
        query_timestamp=timestamps
    )
    def test_invalid_stop_returns_404_for_historical_query(
        self, invalid_stop_id, query_timestamp
    ):
        """
        Test that querying an invalid stop ID returns 404 for historical query.
        
        For any stop ID that doesn't exist and any timestamp, the API should
        return 404 with a descriptive error message.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.people_count_api import lambda_handler
        
        # Mock Timestream response with no data (stop doesn't exist)
        mock_timestream_response = {'rows': []}
        
        # Create API Gateway event for historical query
        event = {
            'pathParameters': {'stop_id': invalid_stop_id},
            'queryStringParameters': {
                'timestamp': query_timestamp.isoformat()
            }
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.people_count_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_at_time.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 404 response
            assert response['statusCode'] == 404, \
                f"Expected status 404 for invalid stop, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify error structure
            assert 'error' in body and body['error'] is True, \
                "Response should indicate an error"
            assert invalid_stop_id in body['message'], \
                f"Error message should mention the invalid stop_id {invalid_stop_id}"
    
    @settings(max_examples=50)
    @given(
        query_mode=st.sampled_from(['latest', 'historical'])
    )
    def test_missing_stop_id_returns_400(self, query_mode):
        """
        Test that missing stop_id parameter returns 400 Bad Request.
        
        When the stop_id path parameter is missing, the API should return 400.
        """
        from src.lambdas.people_count_api import lambda_handler
        
        # Create API Gateway event without stop_id
        if query_mode == 'latest':
            event = {
                'pathParameters': {},
                'queryStringParameters': {'mode': 'latest'}
            }
        else:
            event = {
                'pathParameters': {},
                'queryStringParameters': {
                    'timestamp': '2024-01-15T10:00:00Z'
                }
            }
        
        # Call the Lambda handler
        response = lambda_handler(event, None)
        
        # Verify 400 response
        assert response['statusCode'] == 400, \
            f"Expected status 400 for missing stop_id, got {response['statusCode']}"
        
        # Verify error message
        import json
        body = json.loads(response['body'])
        assert 'stop_id' in body['message'].lower(), \
            "Error message should mention missing stop_id"
    
    @settings(max_examples=50)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS)
    )
    def test_missing_query_parameters_returns_400(self, stop_id):
        """
        Test that missing query parameters returns 400 Bad Request.
        
        When neither 'mode=latest' nor 'timestamp' is provided, the API should return 400.
        """
        from src.lambdas.people_count_api import lambda_handler
        
        # Create API Gateway event without query parameters
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {}
        }
        
        # Call the Lambda handler
        response = lambda_handler(event, None)
        
        # Verify 400 response
        assert response['statusCode'] == 400, \
            f"Expected status 400 for missing query parameters, got {response['statusCode']}"
        
        # Verify error message
        import json
        body = json.loads(response['body'])
        assert 'mode' in body['message'].lower() or 'timestamp' in body['message'].lower(), \
            "Error message should mention required query parameters"


class TestProperty4LatestSensorDataQueryCorrectness:
    """
    Property 4: Latest sensor data query correctness
    
    **Validates: Requirements 2.1, 2.2**
    
    For any valid entity (bus or stop), querying the sensors API with mode=latest should
    return the most recent sensor readings from Timestream, with all sensor values
    matching the stored data.
    """
    
    # Valid bus IDs from configuration
    VALID_BUS_IDS = [
        'B001', 'B002', 'B003',  # Line L1
        'B101', 'B102', 'B103', 'B104',  # Line L2
        'B201', 'B202', 'B203'  # Line L3
    ]
    
    # Valid stop IDs from configuration
    VALID_STOP_IDS = [
        'S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007',  # Line L1
        'S101', 'S102', 'S103', 'S104', 'S105', 'S106',          # Line L2
        'S201', 'S202', 'S203', 'S204', 'S205'                   # Line L3
    ]
    
    @settings(max_examples=100)
    @given(
        bus_id=st.sampled_from(VALID_BUS_IDS),
        temperature=st.floats(min_value=10.0, max_value=35.0, allow_nan=False, allow_infinity=False),
        humidity=st.floats(min_value=20.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        co2_level=st.integers(min_value=400, max_value=2000),
        door_status=st.sampled_from(['open', 'closed']),
        timestamp=timestamps
    )
    def test_latest_query_returns_most_recent_bus_sensor_data(
        self, bus_id, temperature, humidity, co2_level, door_status, timestamp
    ):
        """
        Test that latest query returns the most recent sensor data for a bus.
        
        For any valid bus ID, when data exists in Timestream, the API should return
        the most recent sensor data with all fields matching the stored data.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Mock Timestream response with the most recent data
        mock_timestream_response = {
            'rows': [{
                'entity_id': bus_id,
                'entity_type': 'bus',
                'time': timestamp.isoformat(),
                'temperature': str(temperature),
                'humidity': str(humidity),
                'co2_level': str(co2_level),
                'door_status': door_status
            }]
        }
        
        # Create API Gateway event for latest query
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': bus_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify the response
            assert response['statusCode'] == 200, \
                f"Expected status 200, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify all fields match the stored data
            assert body['entity_id'] == bus_id, \
                f"Expected entity_id {bus_id}, got {body['entity_id']}"
            assert body['entity_type'] == 'bus', \
                f"Expected entity_type 'bus', got {body['entity_type']}"
            assert abs(body['temperature'] - temperature) < 0.01, \
                f"Expected temperature {temperature}, got {body['temperature']}"
            assert abs(body['humidity'] - humidity) < 0.01, \
                f"Expected humidity {humidity}, got {body['humidity']}"
            assert body['co2_level'] == co2_level, \
                f"Expected co2_level {co2_level}, got {body['co2_level']}"
            assert body['door_status'] == door_status, \
                f"Expected door_status {door_status}, got {body['door_status']}"
            assert body['timestamp'] == timestamp.isoformat(), \
                f"Expected timestamp {timestamp.isoformat()}, got {body['timestamp']}"
            
            # Verify Timestream was queried correctly
            mock_client.query_latest.assert_called_once()
            call_args = mock_client.query_latest.call_args
            assert call_args[1]['dimensions']['entity_id'] == bus_id, \
                "Timestream query should use the correct entity_id"
            assert call_args[1]['dimensions']['entity_type'] == 'bus', \
                "Timestream query should use the correct entity_type"
    
    @settings(max_examples=100)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS),
        temperature=st.floats(min_value=10.0, max_value=35.0, allow_nan=False, allow_infinity=False),
        humidity=st.floats(min_value=20.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        timestamp=timestamps
    )
    def test_latest_query_returns_most_recent_stop_sensor_data(
        self, stop_id, temperature, humidity, timestamp
    ):
        """
        Test that latest query returns the most recent sensor data for a stop.
        
        For any valid stop ID, when data exists in Timestream, the API should return
        the most recent sensor data. Stops don't have CO2 or door status.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Mock Timestream response with the most recent data
        mock_timestream_response = {
            'rows': [{
                'entity_id': stop_id,
                'entity_type': 'stop',
                'time': timestamp.isoformat(),
                'temperature': str(temperature),
                'humidity': str(humidity)
            }]
        }
        
        # Create API Gateway event for latest query
        event = {
            'pathParameters': {'entity_type': 'stop', 'entity_id': stop_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify the response
            assert response['statusCode'] == 200, \
                f"Expected status 200, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify all fields match the stored data
            assert body['entity_id'] == stop_id, \
                f"Expected entity_id {stop_id}, got {body['entity_id']}"
            assert body['entity_type'] == 'stop', \
                f"Expected entity_type 'stop', got {body['entity_type']}"
            assert abs(body['temperature'] - temperature) < 0.01, \
                f"Expected temperature {temperature}, got {body['temperature']}"
            assert abs(body['humidity'] - humidity) < 0.01, \
                f"Expected humidity {humidity}, got {body['humidity']}"
            assert body['timestamp'] == timestamp.isoformat(), \
                f"Expected timestamp {timestamp.isoformat()}, got {body['timestamp']}"
            
            # Verify stop sensor data doesn't have bus-specific fields
            assert 'co2_level' not in body or body['co2_level'] is None, \
                "Stop sensor data should not have co2_level"
            assert 'door_status' not in body or body['door_status'] is None, \
                "Stop sensor data should not have door_status"
            
            # Verify Timestream was queried correctly
            mock_client.query_latest.assert_called_once()
            call_args = mock_client.query_latest.call_args
            assert call_args[1]['dimensions']['entity_id'] == stop_id, \
                "Timestream query should use the correct entity_id"
            assert call_args[1]['dimensions']['entity_type'] == 'stop', \
                "Timestream query should use the correct entity_type"
    
    @settings(max_examples=100)
    @given(
        entity_type=st.sampled_from(['bus', 'stop']),
        entity_id=st.sampled_from(VALID_BUS_IDS + VALID_STOP_IDS),
        temperature=st.floats(min_value=10.0, max_value=35.0, allow_nan=False, allow_infinity=False),
        timestamp=timestamps
    )
    def test_latest_query_with_latest_parameter(
        self, entity_type, entity_id, temperature, timestamp
    ):
        """
        Test that latest query works with 'latest' query parameter.
        
        The API should accept both 'mode=latest' and 'latest' as query parameters.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Mock Timestream response
        mock_timestream_response = {
            'rows': [{
                'entity_id': entity_id,
                'entity_type': entity_type,
                'time': timestamp.isoformat(),
                'temperature': str(temperature),
                'humidity': '50.0'
            }]
        }
        
        # Create API Gateway event with 'latest' parameter
        event = {
            'pathParameters': {'entity_type': entity_type, 'entity_id': entity_id},
            'queryStringParameters': {'latest': ''}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify success
            assert response['statusCode'] == 200, \
                f"Latest query with 'latest' parameter should succeed"
    
    @settings(max_examples=50)
    @given(
        entity_type=st.sampled_from(['bus', 'stop']),
        entity_id=st.sampled_from(VALID_BUS_IDS + VALID_STOP_IDS)
    )
    def test_latest_query_with_no_data_returns_404(self, entity_type, entity_id):
        """
        Test that latest query returns 404 when no data exists.
        
        When Timestream returns no data for a valid entity, the API should return 404.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Mock Timestream response with no data
        mock_timestream_response = {'rows': []}
        
        # Create API Gateway event
        event = {
            'pathParameters': {'entity_type': entity_type, 'entity_id': entity_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 404 response
            assert response['statusCode'] == 404, \
                f"Expected status 404 when no data exists, got {response['statusCode']}"
            
            # Verify error message
            import json
            body = json.loads(response['body'])
            assert 'error' in body and body['error'] is True, \
                "Response should indicate an error"
            assert entity_id in body['message'], \
                f"Error message should mention the entity_id {entity_id}"


class TestProperty5HistoricalSensorDataQueryCorrectness:
    """
    Property 5: Historical sensor data query correctness
    
    **Validates: Requirements 2.2**
    
    For any valid entity and any timestamp in the past, querying the sensors API with
    that timestamp should return the sensor readings with the largest timestamp less
    than or equal to the query timestamp.
    """
    
    # Valid bus IDs from configuration
    VALID_BUS_IDS = [
        'B001', 'B002', 'B003',  # Line L1
        'B101', 'B102', 'B103', 'B104',  # Line L2
        'B201', 'B202', 'B203'  # Line L3
    ]
    
    # Valid stop IDs from configuration
    VALID_STOP_IDS = [
        'S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007',  # Line L1
        'S101', 'S102', 'S103', 'S104', 'S105', 'S106',          # Line L2
        'S201', 'S202', 'S203', 'S204', 'S205'                   # Line L3
    ]
    
    @settings(max_examples=100)
    @given(
        bus_id=st.sampled_from(VALID_BUS_IDS),
        query_timestamp=timestamps,
        data_timestamp=timestamps,
        temperature=st.floats(min_value=10.0, max_value=35.0, allow_nan=False, allow_infinity=False),
        humidity=st.floats(min_value=20.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        co2_level=st.integers(min_value=400, max_value=2000),
        door_status=st.sampled_from(['open', 'closed'])
    )
    def test_historical_query_returns_bus_data_at_or_before_timestamp(
        self, bus_id, query_timestamp, data_timestamp, temperature, humidity, co2_level, door_status
    ):
        """
        Test that historical query returns bus sensor data at or before the query timestamp.
        
        For any valid bus ID and timestamp, the API should return the most recent
        sensor data at or before that timestamp.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Ensure data timestamp is at or before query timestamp
        if data_timestamp > query_timestamp:
            data_timestamp, query_timestamp = query_timestamp, data_timestamp
        
        # Mock Timestream response with historical data
        mock_timestream_response = {
            'rows': [{
                'entity_id': bus_id,
                'entity_type': 'bus',
                'time': data_timestamp.isoformat(),
                'temperature': str(temperature),
                'humidity': str(humidity),
                'co2_level': str(co2_level),
                'door_status': door_status
            }]
        }
        
        # Create API Gateway event for historical query
        event = {
            'pathParameters': {'entity_type': 'bus', 'entity_id': bus_id},
            'queryStringParameters': {
                'timestamp': query_timestamp.isoformat()
            }
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_at_time.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify the response
            assert response['statusCode'] == 200, \
                f"Expected status 200, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify all fields match the stored data
            assert body['entity_id'] == bus_id, \
                f"Expected entity_id {bus_id}, got {body['entity_id']}"
            assert body['entity_type'] == 'bus', \
                f"Expected entity_type 'bus', got {body['entity_type']}"
            assert abs(body['temperature'] - temperature) < 0.01, \
                f"Expected temperature {temperature}, got {body['temperature']}"
            assert abs(body['humidity'] - humidity) < 0.01, \
                f"Expected humidity {humidity}, got {body['humidity']}"
            assert body['co2_level'] == co2_level, \
                f"Expected co2_level {co2_level}, got {body['co2_level']}"
            assert body['door_status'] == door_status, \
                f"Expected door_status {door_status}, got {body['door_status']}"
            assert body['timestamp'] == data_timestamp.isoformat(), \
                f"Expected timestamp {data_timestamp.isoformat()}, got {body['timestamp']}"
            
            # Verify Timestream was queried correctly
            mock_client.query_at_time.assert_called_once()
            call_args = mock_client.query_at_time.call_args
            assert call_args[1]['dimensions']['entity_id'] == bus_id, \
                "Timestream query should use the correct entity_id"
            assert call_args[1]['dimensions']['entity_type'] == 'bus', \
                "Timestream query should use the correct entity_type"
            assert call_args[1]['timestamp'] == query_timestamp, \
                "Timestream query should use the correct timestamp"
    
    @settings(max_examples=100)
    @given(
        stop_id=st.sampled_from(VALID_STOP_IDS),
        query_timestamp=timestamps,
        data_timestamp=timestamps,
        temperature=st.floats(min_value=10.0, max_value=35.0, allow_nan=False, allow_infinity=False),
        humidity=st.floats(min_value=20.0, max_value=90.0, allow_nan=False, allow_infinity=False)
    )
    def test_historical_query_returns_stop_data_at_or_before_timestamp(
        self, stop_id, query_timestamp, data_timestamp, temperature, humidity
    ):
        """
        Test that historical query returns stop sensor data at or before the query timestamp.
        
        For any valid stop ID and timestamp, the API should return the most recent
        sensor data at or before that timestamp.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Ensure data timestamp is at or before query timestamp
        if data_timestamp > query_timestamp:
            data_timestamp, query_timestamp = query_timestamp, data_timestamp
        
        # Mock Timestream response with historical data
        mock_timestream_response = {
            'rows': [{
                'entity_id': stop_id,
                'entity_type': 'stop',
                'time': data_timestamp.isoformat(),
                'temperature': str(temperature),
                'humidity': str(humidity)
            }]
        }
        
        # Create API Gateway event for historical query
        event = {
            'pathParameters': {'entity_type': 'stop', 'entity_id': stop_id},
            'queryStringParameters': {
                'timestamp': query_timestamp.isoformat()
            }
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_at_time.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify the response
            assert response['statusCode'] == 200, \
                f"Expected status 200, got {response['statusCode']}"
            
            # Parse response body
            import json
            body = json.loads(response['body'])
            
            # Verify all fields match the stored data
            assert body['entity_id'] == stop_id, \
                f"Expected entity_id {stop_id}, got {body['entity_id']}"
            assert body['entity_type'] == 'stop', \
                f"Expected entity_type 'stop', got {body['entity_type']}"
            assert abs(body['temperature'] - temperature) < 0.01, \
                f"Expected temperature {temperature}, got {body['temperature']}"
            assert abs(body['humidity'] - humidity) < 0.01, \
                f"Expected humidity {humidity}, got {body['humidity']}"
            assert body['timestamp'] == data_timestamp.isoformat(), \
                f"Expected timestamp {data_timestamp.isoformat()}, got {body['timestamp']}"
            
            # Verify Timestream was queried correctly
            mock_client.query_at_time.assert_called_once()
            call_args = mock_client.query_at_time.call_args
            assert call_args[1]['dimensions']['entity_id'] == stop_id, \
                "Timestream query should use the correct entity_id"
            assert call_args[1]['dimensions']['entity_type'] == 'stop', \
                "Timestream query should use the correct entity_type"
            assert call_args[1]['timestamp'] == query_timestamp, \
                "Timestream query should use the correct timestamp"
    
    @settings(max_examples=50)
    @given(
        entity_type=st.sampled_from(['bus', 'stop']),
        entity_id=st.sampled_from(VALID_BUS_IDS + VALID_STOP_IDS),
        query_timestamp=timestamps
    )
    def test_historical_query_with_no_data_returns_404(
        self, entity_type, entity_id, query_timestamp
    ):
        """
        Test that historical query returns 404 when no data exists at that time.
        
        When Timestream returns no data for a valid entity at the query time,
        the API should return 404.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Mock Timestream response with no data
        mock_timestream_response = {'rows': []}
        
        # Create API Gateway event
        event = {
            'pathParameters': {'entity_type': entity_type, 'entity_id': entity_id},
            'queryStringParameters': {
                'timestamp': query_timestamp.isoformat()
            }
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_at_time.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 404 response
            assert response['statusCode'] == 404, \
                f"Expected status 404 when no data exists, got {response['statusCode']}"
            
            # Verify error message
            import json
            body = json.loads(response['body'])
            assert 'error' in body and body['error'] is True, \
                "Response should indicate an error"


class TestProperty6InvalidEntityErrorHandling:
    """
    Property 6: Invalid entity error handling
    
    **Validates: Requirements 2.4**
    
    For any entity ID that does not exist in the system configuration, querying the
    sensors API should return a 404 error with a descriptive message.
    """
    
    @settings(max_examples=100)
    @given(
        entity_type=st.sampled_from(['bus', 'stop']),
        invalid_entity_id=st.text(min_size=1, max_size=20, alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd'),
            min_codepoint=48, max_codepoint=122
        )).filter(lambda x: x not in [
            'B001', 'B002', 'B003', 'B101', 'B102', 'B103', 'B104', 'B201', 'B202', 'B203',
            'S001', 'S002', 'S003', 'S004', 'S005', 'S006', 'S007',
            'S101', 'S102', 'S103', 'S104', 'S105', 'S106',
            'S201', 'S202', 'S203', 'S204', 'S205'
        ])
    )
    def test_invalid_entity_returns_404(self, entity_type, invalid_entity_id):
        """
        Test that querying with an invalid entity ID returns 404.
        
        For any entity ID that doesn't exist in the configuration, the API should
        return a 404 error with a descriptive message.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Mock Timestream response with no data (entity doesn't exist)
        mock_timestream_response = {'rows': []}
        
        # Create API Gateway event
        event = {
            'pathParameters': {'entity_type': entity_type, 'entity_id': invalid_entity_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Mock the Timestream client
        with patch('src.lambdas.sensors_api.get_timestream_client') as mock_get_client:
            mock_client = Mock()
            mock_client.query_latest.return_value = mock_timestream_response
            mock_get_client.return_value = mock_client
            
            # Call the Lambda handler
            response = lambda_handler(event, None)
            
            # Verify 404 response
            assert response['statusCode'] == 404, \
                f"Expected status 404 for invalid entity, got {response['statusCode']}"
            
            # Verify error message
            import json
            body = json.loads(response['body'])
            assert 'error' in body and body['error'] is True, \
                "Response should indicate an error"
            assert invalid_entity_id in body['message'], \
                f"Error message should mention the invalid entity_id {invalid_entity_id}"
    
    @settings(max_examples=50)
    @given(
        invalid_entity_type=st.text(min_size=1, max_size=10).filter(
            lambda x: x not in ['bus', 'stop']
        ),
        entity_id=st.text(min_size=1, max_size=10)
    )
    def test_invalid_entity_type_returns_400(self, invalid_entity_type, entity_id):
        """
        Test that querying with an invalid entity type returns 400.
        
        The API should only accept 'bus' or 'stop' as entity types.
        """
        from unittest.mock import Mock, patch
        from src.lambdas.sensors_api import lambda_handler
        
        # Create API Gateway event with invalid entity type
        event = {
            'pathParameters': {'entity_type': invalid_entity_type, 'entity_id': entity_id},
            'queryStringParameters': {'mode': 'latest'}
        }
        
        # Call the Lambda handler (no need to mock Timestream as validation happens first)
        response = lambda_handler(event, None)
        
        # Verify 400 response
        assert response['statusCode'] == 400, \
            f"Expected status 400 for invalid entity_type, got {response['statusCode']}"
        
        # Verify error message
        import json
        body = json.loads(response['body'])
        assert 'error' in body and body['error'] is True, \
            "Response should indicate an error"
        assert 'entity_type' in body['message'].lower(), \
            "Error message should mention entity_type"
