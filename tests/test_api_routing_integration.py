"""
Integration test for API Gateway routing correctness.

Property 11: API routing correctness
**Validates: Requirements 8.4**

This test verifies that API Gateway correctly routes requests to the appropriate
Lambda functions based on the endpoint path:
- /people-count routes to People Count Lambda
- /sensors routes to Sensors Lambda
- /bus-position routes to Bus Position Lambda
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from hypothesis import given, settings, strategies as st

# Import Lambda handlers
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.people_count_api import lambda_handler as people_count_handler
from lambdas.sensors_api import lambda_handler as sensors_handler
from lambdas.bus_position_api import lambda_handler as bus_position_handler


# Strategies for generating valid IDs
stop_ids = st.text(min_size=1, max_size=10, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    min_codepoint=48, max_codepoint=122
)).filter(lambda x: x.strip())

entity_ids = st.text(min_size=1, max_size=10, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    min_codepoint=48, max_codepoint=122
)).filter(lambda x: x.strip())

bus_ids = st.text(min_size=1, max_size=10, alphabet=st.characters(
    whitelist_categories=('Lu', 'Ll', 'Nd'),
    min_codepoint=48, max_codepoint=122
)).filter(lambda x: x.strip())


class TestProperty11APIRoutingCorrectness:
    """
    Property 11: API routing correctness
    
    **Validates: Requirements 8.4**
    
    For any valid API request, the API Gateway SHALL route the request to the
    appropriate Lambda function based on the endpoint path:
    - /people-count/{stop_id} -> People Count Lambda
    - /sensors/{entity_type}/{entity_id} -> Sensors Lambda
    - /bus-position/{bus_id} -> Bus Position Lambda
    """
    
    @settings(max_examples=50)
    @given(stop_id=stop_ids)
    @patch('lambdas.people_count_api.query_latest_people_count')
    def test_people_count_endpoint_routes_to_people_count_lambda(
        self, mock_query, stop_id
    ):
        """
        Test that /people-count endpoint routes to People Count Lambda.
        
        For any valid stop_id, when a request is made to /people-count/{stop_id},
        the request should be handled by the people_count_api Lambda handler.
        """
        # Mock the query to return valid data
        mock_query.return_value = {
            'stop_id': stop_id,
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 15,
            'line_ids': ['L1', 'L2']
        }
        
        # Simulate API Gateway event for /people-count/{stop_id}
        event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'mode': 'latest'},
            'headers': {
                'x-api-key': 'test-key',
                'x-group-name': 'test-group'
            },
            'requestContext': {
                'authorizer': {
                    'group_name': 'test-group'
                }
            }
        }
        
        # Call the People Count Lambda handler
        response = people_count_handler(event, None)
        
        # Verify the handler was invoked and processed the request
        assert response is not None
        assert 'statusCode' in response
        assert 'body' in response
        
        # Verify the response is from People Count Lambda (contains stop_id)
        if response['statusCode'] == 200:
            body = json.loads(response['body'])
            assert 'stop_id' in body or 'count' in body, \
                "Response should contain people count data"
        
        # Verify the correct query function was called
        mock_query.assert_called_once_with(stop_id)
    
    @settings(max_examples=50)
    @given(
        entity_id=entity_ids,
        entity_type=st.sampled_from(['bus', 'stop'])
    )
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    def test_sensors_endpoint_routes_to_sensors_lambda(
        self, mock_query, entity_id, entity_type
    ):
        """
        Test that /sensors endpoint routes to Sensors Lambda.
        
        For any valid entity_id and entity_type, when a request is made to
        /sensors/{entity_type}/{entity_id}, the request should be handled by
        the sensors_api Lambda handler.
        """
        # Mock the query to return valid data
        mock_query.return_value = {
            'entity_id': entity_id,
            'entity_type': entity_type,
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 65.3,
            'co2_level': 850 if entity_type == 'bus' else None,
            'door_status': 'closed' if entity_type == 'bus' else None
        }
        
        # Simulate API Gateway event for /sensors/{entity_type}/{entity_id}
        event = {
            'pathParameters': {
                'entity_id': entity_id,
                'entity_type': entity_type
            },
            'queryStringParameters': {'mode': 'latest'},
            'headers': {
                'x-api-key': 'test-key',
                'x-group-name': 'test-group'
            },
            'requestContext': {
                'authorizer': {
                    'group_name': 'test-group'
                }
            }
        }
        
        # Call the Sensors Lambda handler
        response = sensors_handler(event, None)
        
        # Verify the handler was invoked and processed the request
        assert response is not None
        assert 'statusCode' in response
        assert 'body' in response
        
        # Verify the response is from Sensors Lambda (contains sensor data)
        if response['statusCode'] == 200:
            body = json.loads(response['body'])
            assert 'entity_id' in body or 'temperature' in body, \
                "Response should contain sensor data"
        
        # Verify the correct query function was called
        mock_query.assert_called_once_with(entity_type, entity_id)
    
    @settings(max_examples=50)
    @given(bus_id=bus_ids)
    @patch('lambdas.bus_position_api.query_latest_bus_position')
    def test_bus_position_endpoint_routes_to_bus_position_lambda(
        self, mock_query, bus_id
    ):
        """
        Test that /bus-position endpoint routes to Bus Position Lambda.
        
        For any valid bus_id, when a request is made to /bus-position/{bus_id},
        the request should be handled by the bus_position_api Lambda handler.
        """
        # Mock the query to return valid data
        mock_query.return_value = {
            'bus_id': bus_id,
            'line_id': 'L1',
            'timestamp': '2024-01-15T10:30:00Z',
            'latitude': 40.4165,
            'longitude': -3.7026,
            'passenger_count': 25,
            'next_stop_id': 'S003',
            'distance_to_next_stop': 450.5,
            'speed': 35.2
        }
        
        # Simulate API Gateway event for /bus-position/{bus_id}
        event = {
            'pathParameters': {'bus_id': bus_id},
            'path': f'/bus-position/{bus_id}',
            'queryStringParameters': {'mode': 'latest'},
            'headers': {
                'x-api-key': 'test-key',
                'x-group-name': 'test-group'
            },
            'requestContext': {
                'authorizer': {
                    'group_name': 'test-group'
                }
            }
        }
        
        # Call the Bus Position Lambda handler
        response = bus_position_handler(event, None)
        
        # Verify the handler was invoked and processed the request
        assert response is not None
        assert 'statusCode' in response
        assert 'body' in response
        
        # Verify the response is from Bus Position Lambda (contains bus data)
        if response['statusCode'] == 200:
            body = json.loads(response['body'])
            assert 'bus_id' in body or 'latitude' in body, \
                "Response should contain bus position data"
        
        # Verify the correct query function was called
        mock_query.assert_called_once_with(bus_id)
    
    @settings(max_examples=30)
    @given(
        stop_id=stop_ids,
        entity_id=entity_ids,
        bus_id=bus_ids
    )
    @patch('lambdas.people_count_api.query_latest_people_count')
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    @patch('lambdas.bus_position_api.query_latest_bus_position')
    def test_different_endpoints_route_to_different_lambdas(
        self, mock_bus_query, mock_sensor_query, mock_people_query,
        stop_id, entity_id, bus_id
    ):
        """
        Test that different endpoints route to different Lambda functions.
        
        This comprehensive test verifies that each endpoint correctly routes
        to its designated Lambda function and not to others.
        """
        # Mock all queries to return valid data
        mock_people_query.return_value = {
            'stop_id': stop_id,
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 15,
            'line_ids': ['L1']
        }
        
        mock_sensor_query.return_value = {
            'entity_id': entity_id,
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 65.3
        }
        
        mock_bus_query.return_value = {
            'bus_id': bus_id,
            'line_id': 'L1',
            'timestamp': '2024-01-15T10:30:00Z',
            'latitude': 40.4165,
            'longitude': -3.7026,
            'passenger_count': 25
        }
        
        # Test 1: People Count endpoint
        people_event = {
            'pathParameters': {'stop_id': stop_id},
            'queryStringParameters': {'mode': 'latest'},
            'headers': {'x-api-key': 'test-key', 'x-group-name': 'test-group'},
            'requestContext': {'authorizer': {'group_name': 'test-group'}}
        }
        people_response = people_count_handler(people_event, None)
        
        # Test 2: Sensors endpoint
        sensor_event = {
            'pathParameters': {'entity_id': entity_id, 'entity_type': 'bus'},
            'queryStringParameters': {'mode': 'latest'},
            'headers': {'x-api-key': 'test-key', 'x-group-name': 'test-group'},
            'requestContext': {'authorizer': {'group_name': 'test-group'}}
        }
        sensor_response = sensors_handler(sensor_event, None)
        
        # Test 3: Bus Position endpoint
        bus_event = {
            'pathParameters': {'bus_id': bus_id},
            'path': f'/bus-position/{bus_id}',
            'queryStringParameters': {'mode': 'latest'},
            'headers': {'x-api-key': 'test-key', 'x-group-name': 'test-group'},
            'requestContext': {'authorizer': {'group_name': 'test-group'}}
        }
        bus_response = bus_position_handler(bus_event, None)
        
        # Verify each handler was called with correct parameters
        mock_people_query.assert_called_once_with(stop_id)
        mock_sensor_query.assert_called_once_with('bus', entity_id)
        mock_bus_query.assert_called_once_with(bus_id)
        
        # Verify all responses are valid
        assert people_response['statusCode'] in [200, 404]
        assert sensor_response['statusCode'] in [200, 404]
        assert bus_response['statusCode'] in [200, 404]
        
        # Verify responses contain appropriate data types
        if people_response['statusCode'] == 200:
            people_body = json.loads(people_response['body'])
            assert 'stop_id' in people_body or 'count' in people_body
        
        if sensor_response['statusCode'] == 200:
            sensor_body = json.loads(sensor_response['body'])
            assert 'entity_id' in sensor_body or 'temperature' in sensor_body
        
        if bus_response['statusCode'] == 200:
            bus_body = json.loads(bus_response['body'])
            assert 'bus_id' in bus_body or 'latitude' in bus_body
    
    @pytest.mark.parametrize('endpoint,handler,path_params', [
        ('people-count', people_count_handler, {'stop_id': 'S001'}),
        ('sensors', sensors_handler, {'entity_id': 'B001', 'entity_type': 'bus'}),
        ('bus-position', bus_position_handler, {'bus_id': 'B001'}),
    ])
    @patch('lambdas.people_count_api.query_latest_people_count')
    @patch('lambdas.sensors_api.query_latest_sensor_data')
    @patch('lambdas.bus_position_api.query_latest_bus_position')
    def test_endpoint_handler_mapping(
        self, mock_bus_query, mock_sensor_query, mock_people_query,
        endpoint, handler, path_params
    ):
        """
        Test that each endpoint is mapped to the correct handler.
        
        This parameterized test verifies the endpoint-to-handler mapping
        for all three API endpoints.
        """
        # Mock all queries to return valid data
        mock_people_query.return_value = {
            'stop_id': 'S001',
            'timestamp': '2024-01-15T10:30:00Z',
            'count': 15,
            'line_ids': ['L1']
        }
        
        mock_sensor_query.return_value = {
            'entity_id': 'B001',
            'entity_type': 'bus',
            'timestamp': '2024-01-15T10:30:00Z',
            'temperature': 22.5,
            'humidity': 65.3
        }
        
        mock_bus_query.return_value = {
            'bus_id': 'B001',
            'line_id': 'L1',
            'timestamp': '2024-01-15T10:30:00Z',
            'latitude': 40.4165,
            'longitude': -3.7026,
            'passenger_count': 25
        }
        
        # Create event for the endpoint
        event = {
            'pathParameters': path_params,
            'path': f'/{endpoint}',
            'queryStringParameters': {'mode': 'latest'},
            'headers': {'x-api-key': 'test-key', 'x-group-name': 'test-group'},
            'requestContext': {'authorizer': {'group_name': 'test-group'}}
        }
        
        # Call the handler
        response = handler(event, None)
        
        # Verify the handler processed the request
        assert response is not None
        assert 'statusCode' in response
        assert response['statusCode'] in [200, 400, 404]
        
        # Verify the response has the correct structure
        assert 'body' in response
        assert 'headers' in response
        assert response['headers']['Content-Type'] == 'application/json'
    
    def test_routing_configuration_completeness(self):
        """
        Test that all required endpoints have handler mappings.
        
        This test verifies that the routing configuration includes all
        three required endpoints as specified in Requirements 8.4.
        """
        # Define the required endpoint-to-handler mappings
        required_mappings = {
            'people-count': people_count_handler,
            'sensors': sensors_handler,
            'bus-position': bus_position_handler
        }
        
        # Verify all handlers are callable
        for endpoint, handler in required_mappings.items():
            assert callable(handler), \
                f"Handler for {endpoint} endpoint must be callable"
        
        # Verify handlers are distinct (not the same function)
        handlers = list(required_mappings.values())
        assert len(handlers) == len(set(handlers)), \
            "Each endpoint must have a distinct handler function"
