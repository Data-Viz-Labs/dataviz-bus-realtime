"""
Unit tests for the WebSocket Handler Lambda function.

Tests the Lambda handler, connection management, subscription logic, and EventBridge integration.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Import the Lambda handler module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lambdas.websocket_handler import (
    lambda_handler,
    handle_websocket_connect,
    handle_websocket_disconnect,
    handle_websocket_message,
    store_connection,
    remove_connection,
    update_subscription,
    remove_subscriptions,
    get_subscribed_connections,
    eventbridge_handler
)


class TestLambdaHandler:
    """Test the main Lambda handler function."""
    
    @patch('lambdas.websocket_handler.handle_websocket_connect')
    def test_connect_event(self, mock_connect):
        """Test routing of CONNECT event."""
        mock_connect.return_value = {'statusCode': 200}
        
        event = {
            'requestContext': {
                'eventType': 'CONNECT',
                'connectionId': 'abc123'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        mock_connect.assert_called_once_with(event, None)
    
    @patch('lambdas.websocket_handler.handle_websocket_disconnect')
    def test_disconnect_event(self, mock_disconnect):
        """Test routing of DISCONNECT event."""
        mock_disconnect.return_value = {'statusCode': 200}
        
        event = {
            'requestContext': {
                'eventType': 'DISCONNECT',
                'connectionId': 'abc123'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        mock_disconnect.assert_called_once_with(event, None)
    
    @patch('lambdas.websocket_handler.handle_websocket_message')
    def test_message_event(self, mock_message):
        """Test routing of MESSAGE event."""
        mock_message.return_value = {'statusCode': 200}
        
        event = {
            'requestContext': {
                'eventType': 'MESSAGE',
                'connectionId': 'abc123'
            },
            'body': '{"action": "subscribe", "line_ids": ["L1"]}'
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        mock_message.assert_called_once_with(event, None)
    
    @patch('lambdas.websocket_handler.handle_websocket_connect')
    def test_connect_route_key(self, mock_connect):
        """Test routing using $connect route key."""
        mock_connect.return_value = {'statusCode': 200}
        
        event = {
            'requestContext': {
                'routeKey': '$connect',
                'connectionId': 'abc123'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 200
        mock_connect.assert_called_once()
    
    def test_unknown_event_type(self):
        """Test handling of unknown event type."""
        event = {
            'requestContext': {
                'eventType': 'UNKNOWN',
                'connectionId': 'abc123'
            }
        }
        
        response = lambda_handler(event, None)
        
        assert response['statusCode'] == 400


class TestConnectionHandlers:
    """Test WebSocket connection lifecycle handlers."""
    
    @patch('lambdas.websocket_handler.store_connection')
    def test_handle_connect_success(self, mock_store):
        """Test successful connection handling."""
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            }
        }
        
        response = handle_websocket_connect(event, None)
        
        assert response['statusCode'] == 200
        mock_store.assert_called_once_with('abc123')
    
    @patch('lambdas.websocket_handler.store_connection')
    def test_handle_connect_error(self, mock_store):
        """Test connection handling with storage error."""
        mock_store.side_effect = Exception("DynamoDB error")
        
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            }
        }
        
        response = handle_websocket_connect(event, None)
        
        assert response['statusCode'] == 500
    
    @patch('lambdas.websocket_handler.remove_connection')
    def test_handle_disconnect_success(self, mock_remove):
        """Test successful disconnection handling."""
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            }
        }
        
        response = handle_websocket_disconnect(event, None)
        
        assert response['statusCode'] == 200
        mock_remove.assert_called_once_with('abc123')
    
    @patch('lambdas.websocket_handler.remove_connection')
    def test_handle_disconnect_error(self, mock_remove):
        """Test disconnection handling with removal error."""
        mock_remove.side_effect = Exception("DynamoDB error")
        
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            }
        }
        
        response = handle_websocket_disconnect(event, None)
        
        assert response['statusCode'] == 500


class TestMessageHandler:
    """Test WebSocket message handling."""
    
    @patch('lambdas.websocket_handler.update_subscription')
    def test_subscribe_action(self, mock_update):
        """Test subscription message handling."""
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            },
            'body': json.dumps({
                'action': 'subscribe',
                'line_ids': ['L1', 'L2']
            })
        }
        
        response = handle_websocket_message(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'Subscribed' in body['message']
        assert body['line_ids'] == ['L1', 'L2']
        mock_update.assert_called_once_with('abc123', ['L1', 'L2'])
    
    @patch('lambdas.websocket_handler.remove_subscriptions')
    def test_unsubscribe_action(self, mock_remove):
        """Test unsubscription message handling."""
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            },
            'body': json.dumps({
                'action': 'unsubscribe',
                'line_ids': ['L1']
            })
        }
        
        response = handle_websocket_message(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert 'Unsubscribed' in body['message']
        mock_remove.assert_called_once_with('abc123', ['L1'])
    
    def test_invalid_json(self):
        """Test handling of invalid JSON in message."""
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            },
            'body': 'invalid json'
        }
        
        response = handle_websocket_message(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Invalid JSON' in body['error']
    
    def test_unknown_action(self):
        """Test handling of unknown action."""
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            },
            'body': json.dumps({
                'action': 'unknown_action'
            })
        }
        
        response = handle_websocket_message(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'Unknown action' in body['error']
    
    def test_invalid_line_ids_type(self):
        """Test handling of invalid line_ids type."""
        event = {
            'requestContext': {
                'connectionId': 'abc123'
            },
            'body': json.dumps({
                'action': 'subscribe',
                'line_ids': 'not_a_list'
            })
        }
        
        response = handle_websocket_message(event, None)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert 'must be a list' in body['error']


class TestDynamoDBOperations:
    """Test DynamoDB operations for connection management."""
    
    @patch('lambdas.websocket_handler.connections_table')
    def test_store_connection(self, mock_table):
        """Test storing a new connection."""
        store_connection('abc123')
        
        mock_table.put_item.assert_called_once()
        call_args = mock_table.put_item.call_args
        item = call_args[1]['Item']
        
        assert item['connection_id'] == 'abc123'
        assert 'connected_at' in item
        assert item['subscribed_lines'] == []
        assert 'ttl' in item
    
    @patch('lambdas.websocket_handler.connections_table')
    def test_remove_connection(self, mock_table):
        """Test removing a connection."""
        remove_connection('abc123')
        
        mock_table.delete_item.assert_called_once_with(
            Key={'connection_id': 'abc123'}
        )
    
    @patch('lambdas.websocket_handler.connections_table')
    def test_update_subscription(self, mock_table):
        """Test updating line subscriptions."""
        update_subscription('abc123', ['L1', 'L2'])
        
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        
        assert call_args[1]['Key'] == {'connection_id': 'abc123'}
        assert call_args[1]['ExpressionAttributeValues'][':lines'] == ['L1', 'L2']
    
    @patch('lambdas.websocket_handler.connections_table')
    def test_remove_subscriptions(self, mock_table):
        """Test removing specific line subscriptions."""
        # Mock get_item to return current subscriptions
        mock_table.get_item.return_value = {
            'Item': {
                'connection_id': 'abc123',
                'subscribed_lines': ['L1', 'L2', 'L3']
            }
        }
        
        remove_subscriptions('abc123', ['L2'])
        
        # Verify get_item was called
        mock_table.get_item.assert_called_once_with(
            Key={'connection_id': 'abc123'}
        )
        
        # Verify update_item was called with remaining lines
        mock_table.update_item.assert_called_once()
        call_args = mock_table.update_item.call_args
        updated_lines = call_args[1]['ExpressionAttributeValues'][':lines']
        
        assert 'L1' in updated_lines
        assert 'L3' in updated_lines
        assert 'L2' not in updated_lines
    
    @patch('lambdas.websocket_handler.connections_table')
    def test_remove_subscriptions_connection_not_found(self, mock_table):
        """Test removing subscriptions when connection doesn't exist."""
        mock_table.get_item.return_value = {}
        
        # Should not raise an exception
        remove_subscriptions('abc123', ['L1'])
        
        # update_item should not be called
        mock_table.update_item.assert_not_called()
    
    @patch('lambdas.websocket_handler.connections_table')
    def test_get_subscribed_connections(self, mock_table):
        """Test getting connections subscribed to a line."""
        mock_table.scan.return_value = {
            'Items': [
                {'connection_id': 'conn1', 'subscribed_lines': ['L1', 'L2']},
                {'connection_id': 'conn2', 'subscribed_lines': ['L1']},
                {'connection_id': 'conn3', 'subscribed_lines': ['L2']}
            ]
        }
        
        connections = get_subscribed_connections('L1')
        
        assert len(connections) == 3
        assert 'conn1' in connections
        assert 'conn2' in connections
        assert 'conn3' in connections
    
    @patch('lambdas.websocket_handler.connections_table')
    def test_get_subscribed_connections_empty(self, mock_table):
        """Test getting connections when none are subscribed."""
        mock_table.scan.return_value = {'Items': []}
        
        connections = get_subscribed_connections('L1')
        
        assert connections == []


class TestEventBridgeHandler:
    """Test EventBridge event handling and broadcasting."""
    
    @patch('lambdas.websocket_handler.get_subscribed_connections')
    @patch('lambdas.websocket_handler.boto3.client')
    @patch('lambdas.websocket_handler.API_GATEWAY_ENDPOINT', 'https://test.execute-api.eu-west-1.amazonaws.com')
    def test_eventbridge_handler_success(self, mock_boto_client, mock_get_connections):
        """Test successful EventBridge event handling and broadcast."""
        # Mock subscribed connections
        mock_get_connections.return_value = ['conn1', 'conn2']
        
        # Mock API Gateway Management API client
        mock_api_client = Mock()
        mock_boto_client.return_value = mock_api_client
        
        event = {
            'detail-type': 'Bus Position Update',
            'detail': {
                'bus_id': 'B001',
                'line_id': 'L1',
                'timestamp': '2024-01-15T10:30:00Z',
                'latitude': 40.4165,
                'longitude': -3.7026,
                'passenger_count': 25
            }
        }
        
        response = eventbridge_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['line_id'] == 'L1'
        assert body['success'] == 2
        assert body['failed'] == 0
        
        # Verify post_to_connection was called for each connection
        assert mock_api_client.post_to_connection.call_count == 2
    
    @patch('lambdas.websocket_handler.get_subscribed_connections')
    def test_eventbridge_handler_no_subscribers(self, mock_get_connections):
        """Test EventBridge handler when no connections are subscribed."""
        mock_get_connections.return_value = []
        
        event = {
            'detail': {
                'bus_id': 'B001',
                'line_id': 'L1'
            }
        }
        
        response = eventbridge_handler(event, None)
        
        assert response['statusCode'] == 200
        assert 'No subscribers' in response['body']
    
    def test_eventbridge_handler_missing_line_id(self):
        """Test EventBridge handler with missing line_id."""
        event = {
            'detail': {
                'bus_id': 'B001'
                # Missing line_id
            }
        }
        
        response = eventbridge_handler(event, None)
        
        assert response['statusCode'] == 400
        assert 'Missing line_id' in response['body']
    
    @patch('lambdas.websocket_handler.get_subscribed_connections')
    @patch('lambdas.websocket_handler.boto3.client')
    @patch('lambdas.websocket_handler.remove_connection')
    @patch('lambdas.websocket_handler.API_GATEWAY_ENDPOINT', 'https://test.execute-api.eu-west-1.amazonaws.com')
    def test_eventbridge_handler_stale_connection(
        self, mock_remove, mock_boto_client, mock_get_connections
    ):
        """Test handling of stale connections during broadcast."""
        from botocore.exceptions import ClientError
        
        mock_get_connections.return_value = ['conn1', 'conn2']
        
        # Mock API Gateway client with GoneException for conn1
        mock_api_client = Mock()
        
        def post_side_effect(ConnectionId, Data):
            if ConnectionId == 'conn1':
                raise ClientError(
                    {'Error': {'Code': 'GoneException'}},
                    'PostToConnection'
                )
        
        mock_api_client.post_to_connection.side_effect = post_side_effect
        mock_boto_client.return_value = mock_api_client
        
        event = {
            'detail': {
                'bus_id': 'B001',
                'line_id': 'L1',
                'timestamp': '2024-01-15T10:30:00Z'
            }
        }
        
        response = eventbridge_handler(event, None)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] == 1  # conn2 succeeded
        assert body['failed'] == 1   # conn1 failed
        assert body['stale_removed'] == 1
        
        # Verify stale connection was removed
        mock_remove.assert_called_once_with('conn1')
    
    @patch('lambdas.websocket_handler.get_subscribed_connections')
    def test_eventbridge_handler_no_endpoint(self, mock_get_connections):
        """Test EventBridge handler when API Gateway endpoint is not configured."""
        mock_get_connections.return_value = ['conn1']
        
        with patch.dict(os.environ, {'API_GATEWAY_ENDPOINT': ''}):
            event = {
                'detail': {
                    'bus_id': 'B001',
                    'line_id': 'L1'
                }
            }
            
            response = eventbridge_handler(event, None)
        
        assert response['statusCode'] == 500
        assert 'not configured' in response['body']


class TestIntegration:
    """Integration tests for WebSocket handler."""
    
    @patch('lambdas.websocket_handler.connections_table')
    @patch('lambdas.websocket_handler.update_subscription')
    def test_full_connection_lifecycle(self, mock_update, mock_table):
        """Test complete connection lifecycle: connect, subscribe, disconnect."""
        connection_id = 'test_conn_123'
        
        # 1. Connect
        connect_event = {
            'requestContext': {
                'eventType': 'CONNECT',
                'connectionId': connection_id
            }
        }
        
        response = handle_websocket_connect(connect_event, None)
        assert response['statusCode'] == 200
        
        # 2. Subscribe
        subscribe_event = {
            'requestContext': {
                'connectionId': connection_id
            },
            'body': json.dumps({
                'action': 'subscribe',
                'line_ids': ['L1', 'L2']
            })
        }
        
        response = handle_websocket_message(subscribe_event, None)
        assert response['statusCode'] == 200
        mock_update.assert_called_with(connection_id, ['L1', 'L2'])
        
        # 3. Disconnect
        disconnect_event = {
            'requestContext': {
                'eventType': 'DISCONNECT',
                'connectionId': connection_id
            }
        }
        
        response = handle_websocket_disconnect(disconnect_event, None)
        assert response['statusCode'] == 200
