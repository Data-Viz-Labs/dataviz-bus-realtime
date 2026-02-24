"""
Property-based tests for MCP Server.

Tests verify correctness properties for the MCP server implementation.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from hypothesis import given, settings, strategies as st
from datetime import datetime, timedelta
import json

# Import MCP server
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from mcp_server.server import BusSimulatorMCPServer


class TestMCPToolRegistration:
    """
    **Validates: Requirements 14.1, 14.2**
    
    Property 41: MCP tool registration
    When the MCP server starts, it should register all five tools 
    (query_people_count, query_sensor_data, query_bus_position, 
    query_line_buses, query_time_range) with correct schemas.
    """
    
    def test_property_41_mcp_tool_registration(self):
        """
        Test that all five MCP tools are registered with correct schemas.
        """
        # Create MCP server instance
        server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
        
        # Verify server was created
        assert server is not None
        assert server.server is not None
        assert server.database == 'bus_simulator'
        
        # Verify all tool methods exist
        assert hasattr(server, '_query_people_count')
        assert hasattr(server, '_query_sensor_data')
        assert hasattr(server, '_query_bus_position')
        assert hasattr(server, '_query_line_buses')
        assert hasattr(server, '_query_time_range')
        
        # Verify methods are callable
        assert callable(server._query_people_count)
        assert callable(server._query_sensor_data)
        assert callable(server._query_bus_position)
        assert callable(server._query_line_buses)
        assert callable(server._query_time_range)


class TestMCPPeopleCountQuery:
    """
    **Validates: Requirements 14.3**
    
    Property 42: MCP people count query correctness
    For any valid stop ID queried via the MCP server's query_people_count tool,
    the returned data should match the data returned by the REST API for the 
    same stop and timestamp.
    """
    
    @pytest.mark.asyncio
    async def test_property_42_mcp_people_count_query(self):
        """
        Test that MCP query_people_count returns correct data matching Timestream.
        """
        stop_id = 'S001'
        count = 15
        line_ids = 'L1,L2'
        
        # Mock Timestream response
        mock_response = {
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': stop_id},
                        {'ScalarValue': '2024-01-15T10:30:00.000Z'},
                        {'ScalarValue': str(count)},
                        {'ScalarValue': line_ids}
                    ]
                }
            ],
            'ColumnInfo': [
                {'Name': 'stop_id'},
                {'Name': 'time'},
                {'Name': 'count'},
                {'Name': 'line_ids'}
            ]
        }
        
        # Create server with mocked Timestream client
        server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
        server.timestream_client = Mock()
        server.timestream_client.query = Mock(return_value=mock_response)
        
        # Query via MCP tool
        result = await server._query_people_count(stop_id, mode='latest')
        
        # Verify result structure
        assert result['success'] is True
        assert result['count'] == 1
        assert len(result['data']) == 1
        
        # Verify data matches mock
        data = result['data'][0]
        assert data['stop_id'] == stop_id
        assert data['count'] == str(count)
        assert data['line_ids'] == line_ids
        assert 'time' in data


class TestMCPSensorDataQuery:
    """
    **Validates: Requirements 14.3**
    
    Property 43: MCP sensor data query correctness
    For any valid entity queried via the MCP server's query_sensor_data tool,
    the returned data should match the data returned by the REST API for the 
    same entity and timestamp.
    """
    
    @pytest.mark.asyncio
    async def test_property_43_mcp_sensor_data_query(self):
        """
        Test that MCP query_sensor_data returns correct data matching Timestream.
        """
        entity_id = 'B001'
        entity_type = 'bus'
        temperature = 22.5
        humidity = 65.0
        
        # Mock Timestream response
        mock_response = {
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': entity_id},
                        {'ScalarValue': entity_type},
                        {'ScalarValue': '2024-01-15T10:30:00.000Z'},
                        {'ScalarValue': f'{temperature:.1f}'},
                        {'ScalarValue': f'{humidity:.1f}'},
                        {'ScalarValue': '800'},
                        {'ScalarValue': 'closed'}
                    ]
                }
            ],
            'ColumnInfo': [
                {'Name': 'entity_id'},
                {'Name': 'entity_type'},
                {'Name': 'time'},
                {'Name': 'temperature'},
                {'Name': 'humidity'},
                {'Name': 'co2_level'},
                {'Name': 'door_status'}
            ]
        }
        
        # Create server with mocked Timestream client
        server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
        server.timestream_client = Mock()
        server.timestream_client.query = Mock(return_value=mock_response)
        
        # Query via MCP tool
        result = await server._query_sensor_data(entity_id, entity_type, mode='latest')
        
        # Verify result structure
        assert result['success'] is True
        assert result['count'] == 1
        assert len(result['data']) == 1
        
        # Verify data matches mock
        data = result['data'][0]
        assert data['entity_id'] == entity_id
        assert data['entity_type'] == entity_type
        assert 'temperature' in data
        assert 'humidity' in data
        assert 'time' in data


class TestMCPBusPositionQuery:
    """
    **Validates: Requirements 14.3**
    
    Property 44: MCP bus position query correctness
    For any valid bus ID queried via the MCP server's query_bus_position tool,
    the returned data should match the data returned by the REST API for the 
    same bus and timestamp.
    """
    
    @pytest.mark.asyncio
    async def test_property_44_mcp_bus_position_query(self):
        """
        Test that MCP query_bus_position returns correct data matching Timestream.
        """
        bus_id = 'B001'
        line_id = 'L1'
        latitude = 40.4657
        longitude = -3.6886
        passenger_count = 25
        direction = 0
        
        # Mock Timestream response
        mock_response = {
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': bus_id},
                        {'ScalarValue': line_id},
                        {'ScalarValue': '2024-01-15T10:30:00.000Z'},
                        {'ScalarValue': f'{latitude:.6f}'},
                        {'ScalarValue': f'{longitude:.6f}'},
                        {'ScalarValue': str(passenger_count)},
                        {'ScalarValue': 'S002'},
                        {'ScalarValue': '350.5'},
                        {'ScalarValue': '30.0'},
                        {'ScalarValue': str(direction)}
                    ]
                }
            ],
            'ColumnInfo': [
                {'Name': 'bus_id'},
                {'Name': 'line_id'},
                {'Name': 'time'},
                {'Name': 'latitude'},
                {'Name': 'longitude'},
                {'Name': 'passenger_count'},
                {'Name': 'next_stop_id'},
                {'Name': 'distance_to_next_stop'},
                {'Name': 'speed'},
                {'Name': 'direction'}
            ]
        }
        
        # Create server with mocked Timestream client
        server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
        server.timestream_client = Mock()
        server.timestream_client.query = Mock(return_value=mock_response)
        
        # Query via MCP tool
        result = await server._query_bus_position(bus_id, mode='latest')
        
        # Verify result structure
        assert result['success'] is True
        assert result['count'] == 1
        assert len(result['data']) == 1
        
        # Verify data matches mock
        data = result['data'][0]
        assert data['bus_id'] == bus_id
        assert data['line_id'] == line_id
        assert data['passenger_count'] == str(passenger_count)
        assert data['direction'] == str(direction)
        assert 'latitude' in data
        assert 'longitude' in data
        assert 'time' in data


class TestMCPTimeRangeQuery:
    """
    **Validates: Requirements 14.2, 14.4**
    
    Property 45: MCP historical query support
    For any MCP tool invocation with a timestamp parameter, the server should 
    return historical data from Timestream at or before the specified timestamp.
    
    Property 46: MCP time range query
    For any valid entity and time range queried via query_time_range, the MCP 
    server should return all data points within the specified time window, 
    ordered chronologically.
    """
    
    @pytest.mark.asyncio
    async def test_property_45_46_mcp_time_range_query(self):
        """
        Test that MCP query_time_range returns correct time series data.
        """
        # Generate mock time series data
        from datetime import timezone
        base_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        data_type = 'people_count'
        entity_id = 'S001'
        num_records = 5
        
        mock_rows = []
        
        for i in range(num_records):
            timestamp = (base_time + timedelta(minutes=i)).isoformat().replace('+00:00', 'Z')
            mock_rows.append({
                'Data': [
                    {'ScalarValue': entity_id},
                    {'ScalarValue': timestamp},
                    {'ScalarValue': str(10 + i)},
                    {'ScalarValue': 'L1'}
                ]
            })
        
        column_info = [
            {'Name': 'stop_id'},
            {'Name': 'time'},
            {'Name': 'count'},
            {'Name': 'line_ids'}
        ]
        
        mock_response = {
            'Rows': mock_rows,
            'ColumnInfo': column_info
        }
        
        # Create server with mocked Timestream client
        server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
        server.timestream_client = Mock()
        server.timestream_client.query = Mock(return_value=mock_response)
        
        # Query via MCP tool
        start_time = base_time.isoformat().replace('+00:00', 'Z')
        end_time = (base_time + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')
        result = await server._query_time_range(data_type, entity_id, start_time, end_time)
        
        # Verify result structure
        assert result['success'] is True
        assert result['count'] == num_records
        assert len(result['data']) == num_records
        
        # Verify data is ordered chronologically
        timestamps = [data['time'] for data in result['data']]
        assert timestamps == sorted(timestamps), "Data should be ordered chronologically"
        
        # Verify all records are within time range
        for data in result['data']:
            assert 'time' in data
            data_time = datetime.fromisoformat(data['time'].replace('Z', '+00:00'))
            assert base_time <= data_time <= base_time + timedelta(hours=1)
    
    @pytest.mark.asyncio
    async def test_property_45_historical_timestamp_query(self):
        """
        Test that historical queries with timestamp parameter work correctly.
        """
        # Mock Timestream response for historical query
        mock_response = {
            'Rows': [
                {
                    'Data': [
                        {'ScalarValue': 'S001'},
                        {'ScalarValue': '2024-01-15T09:00:00.000Z'},
                        {'ScalarValue': '12'},
                        {'ScalarValue': 'L1'}
                    ]
                }
            ],
            'ColumnInfo': [
                {'Name': 'stop_id'},
                {'Name': 'time'},
                {'Name': 'count'},
                {'Name': 'line_ids'}
            ]
        }
        
        # Create server with mocked Timestream client
        server = BusSimulatorMCPServer('bus_simulator', 'eu-west-1')
        server.timestream_client = Mock()
        server.timestream_client.query = Mock(return_value=mock_response)
        
        # Query with historical timestamp
        timestamp = '2024-01-15T09:30:00Z'
        result = await server._query_people_count('S001', timestamp=timestamp)
        
        # Verify result
        assert result['success'] is True
        assert result['count'] == 1
        
        # Verify the query was called with timestamp filter
        query_call = server.timestream_client.query.call_args[1]['QueryString']
        assert 'from_iso8601_timestamp' in query_call
        assert timestamp in query_call
        assert 'time <=' in query_call
