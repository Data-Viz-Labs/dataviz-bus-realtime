"""
Lambda handler for WebSocket connections.

This module provides WebSocket endpoints for real-time bus position updates.
Clients can connect, subscribe to specific bus lines, and receive real-time
position updates via EventBridge integration.

Endpoints:
    - $connect: Establish WebSocket connection
    - $disconnect: Close WebSocket connection
    - $default: Handle subscription messages

EventBridge Handler:
    - Receives bus position events and broadcasts to subscribed clients

Requirements: 3.1, 3.2, 6.2
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE', 'bus_simulator_connections')
AWS_REGION = os.environ.get('AWS_REGION', 'eu-west-1')
API_GATEWAY_ENDPOINT = os.environ.get('API_GATEWAY_ENDPOINT', '')

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
connections_table = dynamodb.Table(DYNAMODB_TABLE)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WebSocket connection events.
    
    Routes WebSocket events to appropriate handlers based on event type:
    - CONNECT: Store new connection
    - DISCONNECT: Remove connection
    - MESSAGE: Handle subscription requests
    
    Args:
        event: API Gateway WebSocket event
        context: Lambda context object
    
    Returns:
        API Gateway response with status code
    
    Example events:
        Connect:
            {
                'requestContext': {
                    'eventType': 'CONNECT',
                    'connectionId': 'abc123'
                }
            }
        
        Message:
            {
                'requestContext': {
                    'eventType': 'MESSAGE',
                    'connectionId': 'abc123'
                },
                'body': '{"action": "subscribe", "line_ids": ["L1", "L2"]}'
            }
        
        Disconnect:
            {
                'requestContext': {
                    'eventType': 'DISCONNECT',
                    'connectionId': 'abc123'
                }
            }
    """
    try:
        request_context = event.get('requestContext', {})
        event_type = request_context.get('eventType')
        route_key = request_context.get('routeKey')
        
        logger.info(f"WebSocket event: type={event_type}, route={route_key}")
        
        # Route based on event type or route key
        if event_type == 'CONNECT' or route_key == '$connect':
            return handle_websocket_connect(event, context)
        elif event_type == 'DISCONNECT' or route_key == '$disconnect':
            return handle_websocket_disconnect(event, context)
        elif event_type == 'MESSAGE' or route_key == '$default':
            return handle_websocket_message(event, context)
        else:
            logger.warning(f"Unknown event type: {event_type}, route: {route_key}")
            return {'statusCode': 400, 'body': 'Unknown event type'}
    
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': 'Internal server error'}


def handle_websocket_connect(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WebSocket connection establishment.
    
    Stores the connection ID in DynamoDB for future broadcasts.
    Initializes with empty subscription list.
    
    Args:
        event: API Gateway WebSocket CONNECT event
        context: Lambda context object
    
    Returns:
        Success response with status code 200
    """
    try:
        connection_id = event['requestContext']['connectionId']
        
        logger.info(f"New WebSocket connection: {connection_id}")
        
        # Store connection in DynamoDB
        store_connection(connection_id)
        
        return {'statusCode': 200}
    
    except Exception as e:
        logger.error(f"Error handling WebSocket connect: {str(e)}", exc_info=True)
        return {'statusCode': 500}


def handle_websocket_disconnect(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WebSocket disconnection.
    
    Removes the connection ID from DynamoDB.
    
    Args:
        event: API Gateway WebSocket DISCONNECT event
        context: Lambda context object
    
    Returns:
        Success response with status code 200
    """
    try:
        connection_id = event['requestContext']['connectionId']
        
        logger.info(f"WebSocket disconnection: {connection_id}")
        
        # Remove connection from DynamoDB
        remove_connection(connection_id)
        
        return {'statusCode': 200}
    
    except Exception as e:
        logger.error(f"Error handling WebSocket disconnect: {str(e)}", exc_info=True)
        return {'statusCode': 500}


def handle_websocket_message(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle WebSocket messages from clients.
    
    Supports subscription management:
    - action: "subscribe" - Subscribe to specific bus lines
    - action: "unsubscribe" - Unsubscribe from bus lines
    
    Args:
        event: API Gateway WebSocket MESSAGE event
        context: Lambda context object
    
    Returns:
        Success response with status code 200
    
    Example message:
        {
            "action": "subscribe",
            "line_ids": ["L1", "L2"]
        }
    """
    try:
        connection_id = event['requestContext']['connectionId']
        body = event.get('body', '{}')
        
        logger.info(f"WebSocket message from {connection_id}: {body}")
        
        # Parse message body
        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in message: {body}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid JSON'})
            }
        
        action = message.get('action')
        
        if action == 'subscribe':
            line_ids = message.get('line_ids', [])
            if not isinstance(line_ids, list):
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'line_ids must be a list'})
                }
            
            update_subscription(connection_id, line_ids)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Subscribed to {len(line_ids)} lines',
                    'line_ids': line_ids
                })
            }
        
        elif action == 'unsubscribe':
            line_ids = message.get('line_ids', [])
            if not isinstance(line_ids, list):
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'line_ids must be a list'})
                }
            
            remove_subscriptions(connection_id, line_ids)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Unsubscribed from {len(line_ids)} lines',
                    'line_ids': line_ids
                })
            }
        
        else:
            logger.warning(f"Unknown action: {action}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown action: {action}'})
            }
    
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {str(e)}", exc_info=True)
        return {'statusCode': 500}


def store_connection(connection_id: str) -> None:
    """
    Store a new WebSocket connection in DynamoDB.
    
    Args:
        connection_id: WebSocket connection ID
    """
    try:
        # Calculate TTL (24 hours from now)
        ttl = int((datetime.now() + timedelta(hours=24)).timestamp())
        
        connections_table.put_item(
            Item={
                'connection_id': connection_id,
                'connected_at': datetime.now().isoformat(),
                'subscribed_lines': [],
                'ttl': ttl
            }
        )
        
        logger.info(f"Stored connection: {connection_id}")
    
    except Exception as e:
        logger.error(f"Error storing connection {connection_id}: {str(e)}")
        raise


def remove_connection(connection_id: str) -> None:
    """
    Remove a WebSocket connection from DynamoDB.
    
    Args:
        connection_id: WebSocket connection ID
    """
    try:
        connections_table.delete_item(
            Key={'connection_id': connection_id}
        )
        
        logger.info(f"Removed connection: {connection_id}")
    
    except Exception as e:
        logger.error(f"Error removing connection {connection_id}: {str(e)}")
        raise


def update_subscription(connection_id: str, line_ids: List[str]) -> None:
    """
    Update the line subscriptions for a connection.
    
    Args:
        connection_id: WebSocket connection ID
        line_ids: List of bus line IDs to subscribe to
    """
    try:
        connections_table.update_item(
            Key={'connection_id': connection_id},
            UpdateExpression='SET subscribed_lines = :lines',
            ExpressionAttributeValues={
                ':lines': line_ids
            }
        )
        
        logger.info(f"Updated subscriptions for {connection_id}: {line_ids}")
    
    except Exception as e:
        logger.error(f"Error updating subscription for {connection_id}: {str(e)}")
        raise


def remove_subscriptions(connection_id: str, line_ids: List[str]) -> None:
    """
    Remove specific line subscriptions for a connection.
    
    Args:
        connection_id: WebSocket connection ID
        line_ids: List of bus line IDs to unsubscribe from
    """
    try:
        # Get current subscriptions
        response = connections_table.get_item(
            Key={'connection_id': connection_id}
        )
        
        if 'Item' not in response:
            logger.warning(f"Connection not found: {connection_id}")
            return
        
        current_lines = response['Item'].get('subscribed_lines', [])
        
        # Remove specified lines
        updated_lines = [line for line in current_lines if line not in line_ids]
        
        # Update in DynamoDB
        connections_table.update_item(
            Key={'connection_id': connection_id},
            UpdateExpression='SET subscribed_lines = :lines',
            ExpressionAttributeValues={
                ':lines': updated_lines
            }
        )
        
        logger.info(f"Removed subscriptions for {connection_id}: {line_ids}")
    
    except Exception as e:
        logger.error(f"Error removing subscriptions for {connection_id}: {str(e)}")
        raise


def get_subscribed_connections(line_id: str) -> List[str]:
    """
    Get all connection IDs subscribed to a specific bus line.
    
    Args:
        line_id: Bus line ID
    
    Returns:
        List of connection IDs subscribed to the line
    """
    try:
        # Scan DynamoDB for connections subscribed to this line
        response = connections_table.scan(
            FilterExpression='contains(subscribed_lines, :line_id)',
            ExpressionAttributeValues={
                ':line_id': line_id
            }
        )
        
        connection_ids = [item['connection_id'] for item in response.get('Items', [])]
        
        logger.info(f"Found {len(connection_ids)} connections subscribed to line {line_id}")
        
        return connection_ids
    
    except Exception as e:
        logger.error(f"Error getting subscribed connections for line {line_id}: {str(e)}")
        return []


def eventbridge_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle bus position events from EventBridge and broadcast to WebSocket clients.
    
    This handler is invoked by EventBridge when a bus position update event occurs.
    It queries DynamoDB for connections subscribed to the bus's line and broadcasts
    the position data to all subscribed clients.
    
    Args:
        event: EventBridge event containing bus position data
        context: Lambda context object
    
    Returns:
        Success response with broadcast statistics
    
    Example event:
        {
            'detail-type': 'Bus Position Update',
            'detail': {
                'bus_id': 'B001',
                'line_id': 'L1',
                'timestamp': '2024-01-15T10:30:00Z',
                'latitude': 40.4165,
                'longitude': -3.7026,
                'passenger_count': 25,
                'next_stop_id': 'S003',
                'distance_to_next_stop': 450.5,
                'speed': 35.2
            }
        }
    """
    try:
        bus_position = event.get('detail', {})
        line_id = bus_position.get('line_id')
        
        if not line_id:
            logger.warning("No line_id in bus position event")
            return {'statusCode': 400, 'body': 'Missing line_id'}
        
        logger.info(f"Broadcasting bus position for line {line_id}")
        
        # Get all connections subscribed to this line
        connections = get_subscribed_connections(line_id)
        
        if not connections:
            logger.info(f"No connections subscribed to line {line_id}")
            return {'statusCode': 200, 'body': 'No subscribers'}
        
        # Broadcast to all subscribed clients
        success_count = 0
        failed_count = 0
        stale_connections = []
        
        # Initialize API Gateway Management API client
        # Note: The endpoint URL is constructed from the API Gateway domain
        if API_GATEWAY_ENDPOINT:
            api_gateway_management = boto3.client(
                'apigatewaymanagementapi',
                endpoint_url=API_GATEWAY_ENDPOINT,
                region_name=AWS_REGION
            )
        else:
            logger.warning("API_GATEWAY_ENDPOINT not set, cannot broadcast")
            return {'statusCode': 500, 'body': 'API Gateway endpoint not configured'}
        
        message_data = json.dumps(bus_position).encode('utf-8')
        
        for connection_id in connections:
            try:
                api_gateway_management.post_to_connection(
                    ConnectionId=connection_id,
                    Data=message_data
                )
                success_count += 1
                logger.debug(f"Broadcast to connection {connection_id}")
            
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'GoneException':
                    # Connection is stale, mark for removal
                    logger.info(f"Stale connection detected: {connection_id}")
                    stale_connections.append(connection_id)
                    failed_count += 1
                else:
                    logger.error(f"Error broadcasting to {connection_id}: {error_code}")
                    failed_count += 1
            
            except Exception as e:
                logger.error(f"Unexpected error broadcasting to {connection_id}: {str(e)}")
                failed_count += 1
        
        # Remove stale connections
        for connection_id in stale_connections:
            try:
                remove_connection(connection_id)
            except Exception as e:
                logger.error(f"Error removing stale connection {connection_id}: {str(e)}")
        
        logger.info(
            f"Broadcast complete: {success_count} success, {failed_count} failed, "
            f"{len(stale_connections)} stale removed"
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'line_id': line_id,
                'total_connections': len(connections),
                'success': success_count,
                'failed': failed_count,
                'stale_removed': len(stale_connections)
            })
        }
    
    except Exception as e:
        logger.error(f"Error in eventbridge_handler: {str(e)}", exc_info=True)
        return {'statusCode': 500, 'body': 'Internal server error'}
