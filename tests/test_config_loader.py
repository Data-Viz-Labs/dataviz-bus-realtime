"""
Unit tests for the configuration loader.

Tests cover YAML parsing, validation, error handling, and integration with
the existing lines.yaml configuration file.
"""

import pytest
import tempfile
import os
from pathlib import Path
from src.common.config_loader import ConfigLoader, ConfigurationError, load_configuration
from src.common.models import Route, Stop, BusState


class TestConfigLoader:
    """Test suite for ConfigLoader class."""
    
    def test_load_nonexistent_file(self):
        """Test that loading a non-existent file raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            ConfigLoader("/nonexistent/path/to/file.yaml")
    
    def test_load_empty_file(self):
        """Test that loading an empty file raises ConfigurationError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ConfigurationError, match="Configuration file is empty"):
                loader.load()
        finally:
            os.unlink(temp_path)
    
    def test_load_invalid_yaml(self):
        """Test that loading invalid YAML raises ConfigurationError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [[[")
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ConfigurationError, match="Failed to parse YAML"):
                loader.load()
        finally:
            os.unlink(temp_path)
    
    def test_load_missing_lines_key(self):
        """Test that configuration without 'lines' key raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("other_key: value\n")
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ConfigurationError, match="must contain 'lines' key"):
                loader.load()
        finally:
            os.unlink(temp_path)
    
    def test_load_empty_lines_list(self):
        """Test that configuration with empty lines list raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("lines: []\n")
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ConfigurationError, match="must contain at least one line"):
                loader.load()
        finally:
            os.unlink(temp_path)
    
    def test_parse_routes_before_load(self):
        """Test that parsing routes before loading raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("lines: []\n")
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            with pytest.raises(ConfigurationError, match="Configuration not loaded"):
                loader.parse_routes()
        finally:
            os.unlink(temp_path)
    
    def test_parse_route_missing_line_id(self):
        """Test that route without line_id raises error."""
        config = """
lines:
  - name: "Test Line"
    stops: []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            with pytest.raises(ConfigurationError, match="missing 'line_id' field"):
                loader.parse_routes()
        finally:
            os.unlink(temp_path)
    
    def test_parse_route_missing_name(self):
        """Test that route without name raises error."""
        config = """
lines:
  - line_id: "L1"
    stops: []
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            with pytest.raises(ConfigurationError, match="missing 'name' field"):
                loader.parse_routes()
        finally:
            os.unlink(temp_path)
    
    def test_parse_route_duplicate_line_id(self):
        """Test that duplicate line IDs raise error."""
        config = """
lines:
  - line_id: "L1"
    name: "Line 1"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
  - line_id: "L1"
    name: "Line 1 Duplicate"
    stops:
      - stop_id: "S3"
        name: "Stop 3"
        latitude: 40.2
        longitude: -3.2
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S4"
        name: "Stop 4"
        latitude: 40.3
        longitude: -3.3
        is_terminal: false
        base_arrival_rate: 1.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            with pytest.raises(ConfigurationError, match="Duplicate line_id: L1"):
                loader.parse_routes()
        finally:
            os.unlink(temp_path)
    
    def test_parse_stop_missing_required_field(self):
        """Test that stop missing required fields raises error."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        # Missing longitude, is_terminal, base_arrival_rate
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            with pytest.raises(ConfigurationError, match="missing required field"):
                loader.parse_routes()
        finally:
            os.unlink(temp_path)
    
    def test_parse_stop_invalid_latitude(self):
        """Test that stop with invalid latitude raises error."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 100.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.0
        longitude: -3.0
        is_terminal: false
        base_arrival_rate: 1.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            with pytest.raises(ConfigurationError, match="latitude must be between -90 and 90"):
                loader.parse_routes()
        finally:
            os.unlink(temp_path)
    
    def test_parse_stop_negative_arrival_rate(self):
        """Test that stop with negative arrival rate raises error."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: -1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.0
        longitude: -3.0
        is_terminal: false
        base_arrival_rate: 1.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            with pytest.raises(ConfigurationError, match="base_arrival_rate must be non-negative"):
                loader.parse_routes()
        finally:
            os.unlink(temp_path)
    
    def test_parse_valid_route(self):
        """Test parsing a valid route configuration."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 2.5
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.8
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            routes = loader.parse_routes()
            
            assert len(routes) == 1
            assert routes[0].line_id == "L1"
            assert routes[0].name == "Test Line"
            assert len(routes[0].stops) == 2
            assert routes[0].stops[0].stop_id == "S1"
            assert routes[0].stops[0].is_terminal is True
            assert routes[0].stops[1].stop_id == "S2"
            assert routes[0].stops[1].is_terminal is False
        finally:
            os.unlink(temp_path)
    
    def test_parse_buses_before_routes(self):
        """Test that parsing buses before routes raises error."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
    buses:
      - bus_id: "B1"
        capacity: 80
        initial_position: 0.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            with pytest.raises(ConfigurationError, match="Routes not parsed"):
                loader.parse_buses()
        finally:
            os.unlink(temp_path)
    
    def test_parse_bus_missing_required_field(self):
        """Test that bus missing required fields raises error."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
    buses:
      - bus_id: "B1"
        # Missing capacity and initial_position
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            loader.parse_routes()
            with pytest.raises(ConfigurationError, match="missing 'capacity' field"):
                loader.parse_buses()
        finally:
            os.unlink(temp_path)
    
    def test_parse_bus_duplicate_id(self):
        """Test that duplicate bus IDs raise error."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
    buses:
      - bus_id: "B1"
        capacity: 80
        initial_position: 0.0
      - bus_id: "B1"
        capacity: 80
        initial_position: 0.5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            loader.parse_routes()
            with pytest.raises(ConfigurationError, match="Duplicate bus_id: B1"):
                loader.parse_buses()
        finally:
            os.unlink(temp_path)
    
    def test_parse_valid_buses(self):
        """Test parsing valid bus configuration."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
    buses:
      - bus_id: "B1"
        capacity: 80
        initial_position: 0.0
      - bus_id: "B2"
        capacity: 80
        initial_position: 0.5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            loader.parse_routes()
            buses = loader.parse_buses()
            
            assert len(buses) == 2
            assert "B1" in buses
            assert "B2" in buses
            assert buses["B1"].line_id == "L1"
            assert buses["B1"].capacity == 80
            assert buses["B1"].position_on_route == 0.0
            assert buses["B2"].position_on_route == 0.5
        finally:
            os.unlink(temp_path)
    
    def test_get_route_by_id(self):
        """Test retrieving a route by line ID."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line 1"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
  - line_id: "L2"
    name: "Test Line 2"
    stops:
      - stop_id: "S3"
        name: "Stop 3"
        latitude: 40.2
        longitude: -3.2
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S4"
        name: "Stop 4"
        latitude: 40.3
        longitude: -3.3
        is_terminal: false
        base_arrival_rate: 1.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            loader.parse_routes()
            
            route = loader.get_route_by_id("L2")
            assert route.line_id == "L2"
            assert route.name == "Test Line 2"
            
            with pytest.raises(ConfigurationError, match="Route not found: L3"):
                loader.get_route_by_id("L3")
        finally:
            os.unlink(temp_path)
    
    def test_validate_completeness_success(self):
        """Test successful completeness validation."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
    buses:
      - bus_id: "B1"
        capacity: 80
        initial_position: 0.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            loader.parse_routes()
            loader.parse_buses()
            loader.validate_completeness()  # Should not raise
        finally:
            os.unlink(temp_path)
    
    def test_validate_completeness_no_buses_for_line(self):
        """Test that validation fails when a line has no buses."""
        # This is tricky to test since parse_buses validates buses exist
        # We'll test the validation logic by manipulating internal state
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
    buses:
      - bus_id: "B1"
        capacity: 80
        initial_position: 0.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            loader.load()
            loader.parse_routes()
            loader.parse_buses()
            
            # Manually add a route without buses to test validation
            from src.common.models import Route, Stop
            extra_route = Route(
                line_id="L2",
                name="Line without buses",
                stops=[
                    Stop("S10", "Stop 10", 40.0, -3.0, True, 1.0),
                    Stop("S11", "Stop 11", 40.1, -3.1, False, 1.0)
                ]
            )
            loader._routes.append(extra_route)
            
            with pytest.raises(ConfigurationError, match="Line L2 has no buses assigned"):
                loader.validate_completeness()
        finally:
            os.unlink(temp_path)


class TestLoadConfigurationFunction:
    """Test suite for the convenience load_configuration function."""
    
    def test_load_configuration_success(self):
        """Test successful configuration loading with convenience function."""
        config = """
lines:
  - line_id: "L1"
    name: "Test Line"
    stops:
      - stop_id: "S1"
        name: "Stop 1"
        latitude: 40.0
        longitude: -3.0
        is_terminal: true
        base_arrival_rate: 1.0
      - stop_id: "S2"
        name: "Stop 2"
        latitude: 40.1
        longitude: -3.1
        is_terminal: false
        base_arrival_rate: 1.0
    buses:
      - bus_id: "B1"
        capacity: 80
        initial_position: 0.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config)
            temp_path = f.name
        
        try:
            routes, buses = load_configuration(temp_path)
            
            assert len(routes) == 1
            assert len(buses) == 1
            assert routes[0].line_id == "L1"
            assert "B1" in buses
        finally:
            os.unlink(temp_path)


class TestRealConfigurationFile:
    """Test suite for the actual lines.yaml configuration file."""
    
    def test_load_real_lines_yaml(self):
        """Test loading the actual data/lines.yaml file."""
        config_path = Path(__file__).parent.parent / "data" / "lines.yaml"
        
        if not config_path.exists():
            pytest.skip("data/lines.yaml not found")
        
        routes, buses = load_configuration(str(config_path))
        
        # Verify we loaded 3 lines as specified in the file
        assert len(routes) == 3
        
        # Verify line IDs
        line_ids = {route.line_id for route in routes}
        assert line_ids == {"L1", "L2", "L3"}
        
        # Verify L1 has 7 stops
        l1_route = next(r for r in routes if r.line_id == "L1")
        assert len(l1_route.stops) == 7
        assert l1_route.name == "Plaza de Castilla - Atocha"
        
        # Verify L1 has 3 buses
        l1_buses = [b for b in buses.values() if b.line_id == "L1"]
        assert len(l1_buses) == 3
        
        # Verify L2 has 6 stops
        l2_route = next(r for r in routes if r.line_id == "L2")
        assert len(l2_route.stops) == 6
        assert l2_route.name == "Moncloa - Puerta del Sol"
        
        # Verify L2 has 4 buses
        l2_buses = [b for b in buses.values() if b.line_id == "L2"]
        assert len(l2_buses) == 4
        
        # Verify L3 has 5 stops
        l3_route = next(r for r in routes if r.line_id == "L3")
        assert len(l3_route.stops) == 5
        assert l3_route.name == "Retiro - Opera"
        
        # Verify L3 has 3 buses
        l3_buses = [b for b in buses.values() if b.line_id == "L3"]
        assert len(l3_buses) == 3
        
        # Verify total buses
        assert len(buses) == 10
        
        # Verify terminal stops exist
        for route in routes:
            terminal_stops = [s for s in route.stops if s.is_terminal]
            assert len(terminal_stops) >= 1, f"Route {route.line_id} has no terminal stops"
        
        # Verify all coordinates are in Madrid area (roughly)
        for route in routes:
            for stop in route.stops:
                assert 40.3 <= stop.latitude <= 40.5, f"Stop {stop.stop_id} latitude out of Madrid range"
                assert -3.8 <= stop.longitude <= -3.6, f"Stop {stop.stop_id} longitude out of Madrid range"
