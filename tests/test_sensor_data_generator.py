"""
Unit tests for sensor data generation algorithm.
"""

import pytest
from datetime import datetime

from src.feeders.sensor_data_generator import (
    get_ambient_temperature,
    generate_sensor_data
)
from src.common.models import BusState, SensorDataPoint


class TestGetAmbientTemperature:
    """Test ambient temperature calculation."""
    
    def test_afternoon_warmest(self):
        """Temperature should be warmest around 3 PM."""
        temp = get_ambient_temperature(datetime(2024, 1, 15, 15, 0))
        assert 27 <= temp <= 29, f"Expected ~28°C at 3 PM, got {temp}"
    
    def test_early_morning_coldest(self):
        """Temperature should be coldest in early morning (around 3-6 AM)."""
        # Due to sinusoidal pattern with max at 15:00, min is at 3:00 (12 hours later)
        temp_3am = get_ambient_temperature(datetime(2024, 1, 15, 3, 0))
        temp_6am = get_ambient_temperature(datetime(2024, 1, 15, 6, 0))
        # Both should be cold, 3 AM coldest
        assert 14 <= temp_3am <= 16, f"Expected ~15°C at 3 AM, got {temp_3am}"
        assert 15 <= temp_6am <= 18, f"Expected ~16-17°C at 6 AM, got {temp_6am}"
    
    def test_midnight_moderate(self):
        """Temperature should be moderate at midnight."""
        temp = get_ambient_temperature(datetime(2024, 1, 15, 0, 0))
        assert 16 <= temp <= 20, f"Expected ~17-18°C at midnight, got {temp}"
    
    def test_noon_warm(self):
        """Temperature should be warm at noon."""
        temp = get_ambient_temperature(datetime(2024, 1, 15, 12, 0))
        assert 23 <= temp <= 27, f"Expected ~25-26°C at noon, got {temp}"


class TestGenerateSensorData:
    """Test sensor data generation."""
    
    def test_stop_sensor_data(self):
        """Generate sensor data for a stop."""
        sensor = generate_sensor_data("S001", "stop", datetime(2024, 1, 15, 12, 0))
        
        assert sensor.entity_id == "S001"
        assert sensor.entity_type == "stop"
        assert sensor.timestamp == datetime(2024, 1, 15, 12, 0)
        assert -50 <= sensor.temperature <= 60
        assert 0 <= sensor.humidity <= 100
        assert sensor.co2_level is None
        assert sensor.door_status is None
    
    def test_bus_sensor_data_at_stop(self):
        """Generate sensor data for a bus at a stop."""
        bus = BusState("B001", "L1", 80, passenger_count=30, at_stop=True)
        sensor = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus)
        
        assert sensor.entity_id == "B001"
        assert sensor.entity_type == "bus"
        assert sensor.timestamp == datetime(2024, 1, 15, 12, 0)
        assert -50 <= sensor.temperature <= 60
        assert 0 <= sensor.humidity <= 100
        assert sensor.co2_level is not None
        assert sensor.co2_level >= 0
        assert sensor.door_status == "open"
    
    def test_bus_sensor_data_en_route(self):
        """Generate sensor data for a bus en route."""
        bus = BusState("B001", "L1", 80, passenger_count=30, at_stop=False)
        sensor = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus)
        
        assert sensor.entity_id == "B001"
        assert sensor.entity_type == "bus"
        assert sensor.door_status == "closed"
    
    def test_co2_increases_with_passengers(self):
        """CO2 level should increase with passenger count."""
        # Empty bus
        bus_empty = BusState("B001", "L1", 80, passenger_count=0, at_stop=False)
        sensor_empty = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus_empty)
        
        # Full bus
        bus_full = BusState("B001", "L1", 80, passenger_count=80, at_stop=False)
        sensor_full = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus_full)
        
        # Full bus should have significantly higher CO2 (allowing for noise)
        # Expected difference: 80 passengers * 50 ppm = 4000 ppm
        # With noise (std dev 50), we expect at least 3500 ppm difference most of the time
        assert sensor_full.co2_level > sensor_empty.co2_level + 3000
    
    def test_humidity_inverse_temperature(self):
        """Humidity should generally vary inversely with temperature."""
        # Generate multiple samples and check the trend
        samples = []
        for hour in range(24):
            sensor = generate_sensor_data("S001", "stop", datetime(2024, 1, 15, hour, 0))
            samples.append((sensor.temperature, sensor.humidity))
        
        # Check that on average, higher temperature correlates with lower humidity
        # Sort by temperature
        samples.sort(key=lambda x: x[0])
        
        # Average humidity of coldest third vs warmest third
        coldest_third = samples[:8]
        warmest_third = samples[-8:]
        
        avg_humidity_cold = sum(h for _, h in coldest_third) / len(coldest_third)
        avg_humidity_warm = sum(h for _, h in warmest_third) / len(warmest_third)
        
        assert avg_humidity_cold > avg_humidity_warm, \
            "Colder temperatures should have higher humidity on average"
    
    def test_invalid_entity_type(self):
        """Should raise ValueError for invalid entity type."""
        with pytest.raises(ValueError, match="entity_type must be 'bus' or 'stop'"):
            generate_sensor_data("X001", "invalid", datetime(2024, 1, 15, 12, 0))
    
    def test_bus_without_state(self):
        """Should raise ValueError when bus_state is None for bus entity."""
        with pytest.raises(ValueError, match="bus_state is required"):
            generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), None)
    
    def test_sensor_data_validation(self):
        """Generated sensor data should pass validation."""
        # Test stop
        sensor_stop = generate_sensor_data("S001", "stop", datetime(2024, 1, 15, 12, 0))
        sensor_stop.validate()  # Should not raise
        
        # Test bus
        bus = BusState("B001", "L1", 80, passenger_count=30, at_stop=True)
        sensor_bus = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus)
        sensor_bus.validate()  # Should not raise
    
    def test_temperature_has_noise(self):
        """Temperature should vary due to random noise."""
        # Generate multiple samples at the same time
        temps = []
        for _ in range(20):
            sensor = generate_sensor_data("S001", "stop", datetime(2024, 1, 15, 12, 0))
            temps.append(sensor.temperature)
        
        # Check that we have variation (not all the same)
        assert len(set(temps)) > 1, "Temperature should vary due to noise"
        
        # Check that variation is reasonable (within ~3 standard deviations = 4.5°C)
        temp_range = max(temps) - min(temps)
        assert temp_range < 10, f"Temperature variation too large: {temp_range}°C"
    
    def test_humidity_clamped(self):
        """Humidity should be clamped to [20, 90] range."""
        # Generate many samples to potentially hit edge cases
        for hour in range(24):
            for _ in range(10):
                sensor = generate_sensor_data("S001", "stop", datetime(2024, 1, 15, hour, 0))
                assert 20 <= sensor.humidity <= 90, \
                    f"Humidity {sensor.humidity} outside valid range [20, 90]"
    
    def test_co2_non_negative(self):
        """CO2 level should never be negative."""
        # Test with empty bus (edge case)
        bus = BusState("B001", "L1", 80, passenger_count=0, at_stop=False)
        for _ in range(20):
            sensor = generate_sensor_data("B001", "bus", datetime(2024, 1, 15, 12, 0), bus)
            assert sensor.co2_level >= 0, f"CO2 level should be non-negative, got {sensor.co2_level}"
