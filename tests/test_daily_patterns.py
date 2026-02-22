"""
Unit tests for daily pattern logic.

Tests the time multiplier function, base arrival rate lookup, and Poisson sampling.
"""

import pytest
import random
from src.feeders.daily_patterns import (
    get_time_multiplier,
    get_base_arrival_rate,
    poisson_sample
)


class TestGetTimeMultiplier:
    """Tests for get_time_multiplier function."""
    
    def test_morning_rush_hours(self):
        """Morning rush (06:00-09:00) should return 1.5x multiplier."""
        assert get_time_multiplier(6) == 1.5
        assert get_time_multiplier(7) == 1.5
        assert get_time_multiplier(8) == 1.5
    
    def test_mid_morning_lull(self):
        """Mid-morning lull (09:00-12:00) should return 0.6x multiplier."""
        assert get_time_multiplier(9) == 0.6
        assert get_time_multiplier(10) == 0.6
        assert get_time_multiplier(11) == 0.6
    
    def test_lunch_period(self):
        """Lunch period (12:00-15:00) should return 1.2x multiplier."""
        assert get_time_multiplier(12) == 1.2
        assert get_time_multiplier(13) == 1.2
        assert get_time_multiplier(14) == 1.2
    
    def test_afternoon(self):
        """Afternoon (15:00-18:00) should return 0.8x multiplier."""
        assert get_time_multiplier(15) == 0.8
        assert get_time_multiplier(16) == 0.8
        assert get_time_multiplier(17) == 0.8
    
    def test_evening_rush(self):
        """Evening rush (18:00-21:00) should return 1.4x multiplier."""
        assert get_time_multiplier(18) == 1.4
        assert get_time_multiplier(19) == 1.4
        assert get_time_multiplier(20) == 1.4
    
    def test_night_hours(self):
        """Night hours (21:00-06:00) should return 0.2x multiplier."""
        assert get_time_multiplier(21) == 0.2
        assert get_time_multiplier(22) == 0.2
        assert get_time_multiplier(23) == 0.2
        assert get_time_multiplier(0) == 0.2
        assert get_time_multiplier(1) == 0.2
        assert get_time_multiplier(2) == 0.2
        assert get_time_multiplier(3) == 0.2
        assert get_time_multiplier(4) == 0.2
        assert get_time_multiplier(5) == 0.2
    
    def test_invalid_hour_negative(self):
        """Negative hour should raise ValueError."""
        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            get_time_multiplier(-1)
    
    def test_invalid_hour_too_large(self):
        """Hour > 23 should raise ValueError."""
        with pytest.raises(ValueError, match="hour must be between 0 and 23"):
            get_time_multiplier(24)


class TestGetBaseArrivalRate:
    """Tests for get_base_arrival_rate function."""
    
    def test_valid_stop_id(self):
        """Should return correct base arrival rate for valid stop."""
        config = {
            "S001": 2.5,
            "S002": 1.8,
            "S003": 3.2
        }
        assert get_base_arrival_rate("S001", config) == 2.5
        assert get_base_arrival_rate("S002", config) == 1.8
        assert get_base_arrival_rate("S003", config) == 3.2
    
    def test_invalid_stop_id(self):
        """Should raise ValueError for unknown stop ID."""
        config = {"S001": 2.5}
        with pytest.raises(ValueError, match="Stop S999 not found"):
            get_base_arrival_rate("S999", config)
    
    def test_empty_config(self):
        """Should raise ValueError when config is empty."""
        config = {}
        with pytest.raises(ValueError, match="not found"):
            get_base_arrival_rate("S001", config)


class TestPoissonSample:
    """Tests for poisson_sample function."""
    
    def test_zero_lambda(self):
        """Lambda = 0 should always return 0."""
        for _ in range(10):
            assert poisson_sample(0.0) == 0
    
    def test_negative_lambda(self):
        """Negative lambda should raise ValueError."""
        with pytest.raises(ValueError, match="lambda_param must be non-negative"):
            poisson_sample(-1.0)
    
    def test_small_lambda(self):
        """Small lambda values should produce small integers."""
        random.seed(42)
        samples = [poisson_sample(1.0) for _ in range(100)]
        
        # All samples should be non-negative
        assert all(s >= 0 for s in samples)
        
        # Mean should be close to lambda (within reasonable tolerance)
        mean = sum(samples) / len(samples)
        assert 0.5 <= mean <= 1.5  # Allow some variance
    
    def test_moderate_lambda(self):
        """Moderate lambda values should produce appropriate distribution."""
        random.seed(42)
        samples = [poisson_sample(5.0) for _ in range(100)]
        
        # All samples should be non-negative
        assert all(s >= 0 for s in samples)
        
        # Mean should be close to lambda
        mean = sum(samples) / len(samples)
        assert 3.5 <= mean <= 6.5  # Allow some variance
    
    def test_returns_integer(self):
        """Should always return an integer."""
        random.seed(42)
        for lambda_val in [0.5, 1.0, 2.5, 5.0]:
            result = poisson_sample(lambda_val)
            assert isinstance(result, int)
    
    def test_statistical_properties(self):
        """Verify Poisson distribution properties over many samples."""
        random.seed(42)
        lambda_val = 3.0
        samples = [poisson_sample(lambda_val) for _ in range(1000)]
        
        # Mean should be close to lambda
        mean = sum(samples) / len(samples)
        assert 2.7 <= mean <= 3.3
        
        # Variance should be close to lambda (property of Poisson)
        variance = sum((s - mean) ** 2 for s in samples) / len(samples)
        assert 2.5 <= variance <= 3.5


class TestIntegration:
    """Integration tests combining multiple functions."""
    
    def test_calculate_expected_arrivals(self):
        """Test calculating expected arrivals for different times and stops."""
        config = {"S001": 2.0}  # 2 people per minute base rate
        time_interval_minutes = 5
        
        # Morning rush: 2.0 * 1.5 * 5 = 15 expected arrivals
        base_rate = get_base_arrival_rate("S001", config)
        multiplier = get_time_multiplier(7)
        expected = base_rate * multiplier * time_interval_minutes
        assert expected == 15.0
        
        # Night: 2.0 * 0.2 * 5 = 2 expected arrivals
        multiplier = get_time_multiplier(23)
        expected = base_rate * multiplier * time_interval_minutes
        assert expected == 2.0
    
    def test_realistic_arrival_simulation(self):
        """Test simulating arrivals with realistic parameters."""
        random.seed(42)
        config = {"S001": 2.5}
        
        # Simulate 10 intervals during morning rush
        arrivals = []
        for _ in range(10):
            base_rate = get_base_arrival_rate("S001", config)
            multiplier = get_time_multiplier(7)
            expected = base_rate * multiplier * 5  # 5-minute intervals
            actual = poisson_sample(expected)
            arrivals.append(actual)
        
        # All arrivals should be non-negative
        assert all(a >= 0 for a in arrivals)
        
        # Average should be reasonably close to expected (18.75)
        avg = sum(arrivals) / len(arrivals)
        assert 10 <= avg <= 27  # Allow variance for small sample

