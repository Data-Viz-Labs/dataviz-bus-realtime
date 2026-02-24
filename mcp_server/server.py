"""
MCP Server for Madrid Bus Simulator Time Series Data Access.

This module implements the Model Context Protocol server that provides
programmatic access to Timestream time series data.
"""

import asyncio
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import boto3
from mcp.server import Server
from mcp.types import Tool, TextContent


class BusSimulatorMCPServer:
    """MCP Server for Madrid Bus Simulator time series data."""
    
    def __init__(self, timestream_database: str, timestream_region: str):
        """
        Initialize the MCP server.
        
        Args:
            timestream_database: Name of the Timestream database
            timestream_region: AWS region for Timestream
        """
        self.server = Server("madrid-bus-simulator")
        self.timestream_client = boto3.client('timestream-query', region_name=timestream_region)
        self.database = timestream_database
        
        # Register tools
        self._register_tools()
    
    def _register_tools(self):
        """Register all available MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools."""
            return [
                Tool(
                    name="query_people_count",
                    description="Query people count at a bus stop. Use mode='latest' for current count or provide timestamp for historical data.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "stop_id": {
                                "type": "string",
                                "description": "Bus stop ID (e.g., S001)"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["latest"],
                                "description": "Query mode for latest data"
                            },
                            "timestamp": {
                                "type": "string",
                                "description": "ISO8601 timestamp for historical query"
                            }
                        },
                        "required": ["stop_id"]
                    }
                ),
                Tool(
                    name="query_sensor_data",
                    description="Query sensor data for a bus or stop. Returns temperature, humidity, and for buses: CO2 level and door status.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entity_id": {
                                "type": "string",
                                "description": "Bus ID (e.g., B001) or Stop ID (e.g., S001)"
                            },
                            "entity_type": {
                                "type": "string",
                                "enum": ["bus", "stop"],
                                "description": "Type of entity"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["latest"],
                                "description": "Query mode for latest data"
                            },
                            "timestamp": {
                                "type": "string",
                                "description": "ISO8601 timestamp for historical query"
                            }
                        },
                        "required": ["entity_id", "entity_type"]
                    }
                ),
                Tool(
                    name="query_bus_position",
                    description="Query bus position on route. Returns coordinates, passenger count, direction, and next stop.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "bus_id": {
                                "type": "string",
                                "description": "Bus ID (e.g., B001)"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["latest"],
                                "description": "Query mode for latest data"
                            },
                            "timestamp": {
                                "type": "string",
                                "description": "ISO8601 timestamp for historical query"
                            }
                        },
                        "required": ["bus_id"]
                    }
                ),
                Tool(
                    name="query_line_buses",
                    description="Query all buses currently operating on a specific line.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "line_id": {
                                "type": "string",
                                "description": "Bus line ID (e.g., L1)"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["latest"],
                                "description": "Query mode for latest data"
                            }
                        },
                        "required": ["line_id"]
                    }
                ),
                Tool(
                    name="query_time_range",
                    description="Query time series data for a specific entity over a time range.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "data_type": {
                                "type": "string",
                                "enum": ["people_count", "sensors", "bus_position"],
                                "description": "Type of data to query"
                            },
                            "entity_id": {
                                "type": "string",
                                "description": "Entity ID (stop, bus, or line)"
                            },
                            "start_time": {
                                "type": "string",
                                "description": "ISO8601 start timestamp"
                            },
                            "end_time": {
                                "type": "string",
                                "description": "ISO8601 end timestamp"
                            }
                        },
                        "required": ["data_type", "entity_id", "start_time", "end_time"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool invocation."""
            try:
                if name == "query_people_count":
                    result = await self._query_people_count(**arguments)
                elif name == "query_sensor_data":
                    result = await self._query_sensor_data(**arguments)
                elif name == "query_bus_position":
                    result = await self._query_bus_position(**arguments)
                elif name == "query_line_buses":
                    result = await self._query_line_buses(**arguments)
                elif name == "query_time_range":
                    result = await self._query_time_range(**arguments)
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
                
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                error_result = {
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    async def _query_people_count(self, stop_id: str, mode: Optional[str] = None, 
                                  timestamp: Optional[str] = None) -> Dict:
        """Query people count from Timestream."""
        if mode == "latest" or (not mode and not timestamp):
            query = f"""
                SELECT stop_id, time, count, line_ids
                FROM "{self.database}"."people_count"
                WHERE stop_id = '{stop_id}'
                ORDER BY time DESC
                LIMIT 1
            """
        elif timestamp:
            query = f"""
                SELECT stop_id, time, count, line_ids
                FROM "{self.database}"."people_count"
                WHERE stop_id = '{stop_id}'
                AND time <= from_iso8601_timestamp('{timestamp}')
                ORDER BY time DESC
                LIMIT 1
            """
        else:
            raise ValueError("Must specify mode='latest' or provide timestamp")
        
        return await self._execute_query(query)
    
    async def _query_sensor_data(self, entity_id: str, entity_type: str,
                                mode: Optional[str] = None, 
                                timestamp: Optional[str] = None) -> Dict:
        """Query sensor data from Timestream."""
        if mode == "latest" or (not mode and not timestamp):
            query = f"""
                SELECT entity_id, entity_type, time, temperature, humidity, co2_level, door_status
                FROM "{self.database}"."sensor_data"
                WHERE entity_id = '{entity_id}' AND entity_type = '{entity_type}'
                ORDER BY time DESC
                LIMIT 1
            """
        elif timestamp:
            query = f"""
                SELECT entity_id, entity_type, time, temperature, humidity, co2_level, door_status
                FROM "{self.database}"."sensor_data"
                WHERE entity_id = '{entity_id}' AND entity_type = '{entity_type}'
                AND time <= from_iso8601_timestamp('{timestamp}')
                ORDER BY time DESC
                LIMIT 1
            """
        else:
            raise ValueError("Must specify mode='latest' or provide timestamp")
        
        return await self._execute_query(query)
    
    async def _query_bus_position(self, bus_id: str, mode: Optional[str] = None,
                                  timestamp: Optional[str] = None) -> Dict:
        """Query bus position from Timestream."""
        if mode == "latest" or (not mode and not timestamp):
            query = f"""
                SELECT bus_id, line_id, time, latitude, longitude, passenger_count,
                       next_stop_id, distance_to_next_stop, speed, direction
                FROM "{self.database}"."bus_position"
                WHERE bus_id = '{bus_id}'
                ORDER BY time DESC
                LIMIT 1
            """
        elif timestamp:
            query = f"""
                SELECT bus_id, line_id, time, latitude, longitude, passenger_count,
                       next_stop_id, distance_to_next_stop, speed, direction
                FROM "{self.database}"."bus_position"
                WHERE bus_id = '{bus_id}'
                AND time <= from_iso8601_timestamp('{timestamp}')
                ORDER BY time DESC
                LIMIT 1
            """
        else:
            raise ValueError("Must specify mode='latest' or provide timestamp")
        
        return await self._execute_query(query)
    
    async def _query_line_buses(self, line_id: str, mode: Optional[str] = "latest") -> Dict:
        """Query all buses on a line from Timestream."""
        query = f"""
            SELECT bus_id, line_id, time, latitude, longitude, passenger_count,
                   next_stop_id, distance_to_next_stop, speed, direction
            FROM "{self.database}"."bus_position"
            WHERE line_id = '{line_id}'
            AND time > ago(1m)
            ORDER BY time DESC
        """
        return await self._execute_query(query)
    
    async def _query_time_range(self, data_type: str, entity_id: str,
                               start_time: str, end_time: str) -> Dict:
        """Query time range data from Timestream."""
        table_map = {
            "people_count": "people_count",
            "sensors": "sensor_data",
            "bus_position": "bus_position"
        }
        
        table = table_map.get(data_type)
        if not table:
            raise ValueError(f"Invalid data_type: {data_type}")
        
        # Determine the appropriate ID column
        if data_type == "people_count":
            id_column = "stop_id"
        elif data_type == "sensors":
            id_column = "entity_id"
        else:
            id_column = "bus_id"
        
        query = f"""
            SELECT *
            FROM "{self.database}"."{table}"
            WHERE {id_column} = '{entity_id}'
            AND time BETWEEN from_iso8601_timestamp('{start_time}') 
                        AND from_iso8601_timestamp('{end_time}')
            ORDER BY time ASC
        """
        return await self._execute_query(query)
    
    async def _execute_query(self, query: str) -> Dict:
        """Execute Timestream query and return results."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.timestream_client.query(QueryString=query)
        )
        
        # Parse Timestream response
        rows = response.get('Rows', [])
        column_info = response.get('ColumnInfo', [])
        
        results = []
        for row in rows:
            result = {}
            for i, col in enumerate(column_info):
                col_name = col['Name']
                data = row['Data'][i]
                result[col_name] = data.get('ScalarValue', None)
            results.append(result)
        
        return {
            "success": True,
            "count": len(results),
            "data": results,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def run(self):
        """Run the MCP server."""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Entry point for the MCP server."""
    database = os.getenv('TIMESTREAM_DATABASE', 'bus_simulator')
    region = os.getenv('AWS_REGION', 'eu-west-1')
    
    server = BusSimulatorMCPServer(database, region)
    await server.run()


if __name__ == '__main__':
    asyncio.run(main())
