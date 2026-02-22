"""
Timestream client wrapper for the Madrid Bus Real-Time Simulator.

This module provides a wrapper around the AWS Timestream Write and Query clients
with retry logic, exponential backoff, and convenience methods for common operations.
"""

import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    # Allow module to be imported for testing without boto3
    boto3 = None
    ClientError = Exception


logger = logging.getLogger(__name__)


class TimestreamClient:
    """
    Wrapper for AWS Timestream operations with retry logic.
    
    This client provides methods for writing time series data and querying
    both latest and historical data points with automatic retry on failures.
    """
    
    def __init__(
        self,
        database_name: str,
        region_name: str = "eu-west-1",
        max_retries: int = 3,
        write_client: Optional[Any] = None,
        query_client: Optional[Any] = None
    ):
        """
        Initialize Timestream client.
        
        Args:
            database_name: Name of the Timestream database
            region_name: AWS region name
            max_retries: Maximum number of retry attempts for failed writes
            write_client: Optional boto3 write client (for testing)
            query_client: Optional boto3 query client (for testing)
        
        Raises:
            ImportError: If boto3 is not installed
        """
        if boto3 is None and (write_client is None or query_client is None):
            raise ImportError("boto3 is required but not installed")
        
        self.database_name = database_name
        self.region_name = region_name
        self.max_retries = max_retries
        
        # Use provided clients or create new ones
        self.write_client = write_client or boto3.client(
            'timestream-write',
            region_name=region_name
        )
        self.query_client = query_client or boto3.client(
            'timestream-query',
            region_name=region_name
        )
    
    def write_records(
        self,
        table_name: str,
        records: List[Dict[str, Any]],
        common_attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Write records to Timestream with exponential backoff retry logic.
        
        Args:
            table_name: Name of the Timestream table
            records: List of record dictionaries with dimensions, measures, and time
            common_attributes: Optional common attributes for all records
        
        Returns:
            True if write succeeded, False otherwise
        
        Raises:
            ClientError: If all retry attempts fail
        
        Example:
            records = [
                {
                    'Dimensions': [
                        {'Name': 'stop_id', 'Value': 'S001'},
                        {'Name': 'line_id', 'Value': 'L1'}
                    ],
                    'MeasureName': 'count',
                    'MeasureValue': '15',
                    'MeasureValueType': 'BIGINT',
                    'Time': str(int(datetime.now().timestamp() * 1000)),
                    'TimeUnit': 'MILLISECONDS'
                }
            ]
            client.write_records('people_count', records)
        """
        for attempt in range(self.max_retries):
            try:
                params = {
                    'DatabaseName': self.database_name,
                    'TableName': table_name,
                    'Records': records
                }
                
                if common_attributes:
                    params['CommonAttributes'] = common_attributes
                
                self.write_client.write_records(**params)
                
                logger.info(
                    f"Successfully wrote {len(records)} records to "
                    f"{self.database_name}.{table_name}"
                )
                return True
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                
                if attempt == self.max_retries - 1:
                    logger.error(
                        f"Failed to write to Timestream after {self.max_retries} attempts: "
                        f"{error_code} - {str(e)}"
                    )
                    raise
                
                # Calculate exponential backoff wait time
                wait_time = 2 ** attempt
                
                logger.warning(
                    f"Timestream write failed (attempt {attempt + 1}/{self.max_retries}): "
                    f"{error_code} - {str(e)}. Retrying in {wait_time}s..."
                )
                
                time.sleep(wait_time)
        
        return False
    
    def query_latest(
        self,
        table_name: str,
        dimensions: Dict[str, str],
        limit: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Query the most recent data point from Timestream.
        
        Args:
            table_name: Name of the Timestream table
            dimensions: Dictionary of dimension names and values to filter by
            limit: Maximum number of results to return (default: 1)
        
        Returns:
            Dictionary with query results or None if no data found
        
        Example:
            result = client.query_latest(
                'people_count',
                {'stop_id': 'S001'}
            )
        """
        # Build WHERE clause from dimensions
        where_clauses = [
            f"{key} = '{value}'" for key, value in dimensions.items()
        ]
        where_clause = " AND ".join(where_clauses)
        
        query = f"""
            SELECT *
            FROM "{self.database_name}"."{table_name}"
            WHERE {where_clause}
            ORDER BY time DESC
            LIMIT {limit}
        """
        
        return self._execute_query(query)
    
    def query_at_time(
        self,
        table_name: str,
        dimensions: Dict[str, str],
        timestamp: datetime,
        limit: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Query data at or before a specific timestamp.
        
        Args:
            table_name: Name of the Timestream table
            dimensions: Dictionary of dimension names and values to filter by
            timestamp: Query for data at or before this time
            limit: Maximum number of results to return (default: 1)
        
        Returns:
            Dictionary with query results or None if no data found
        
        Example:
            result = client.query_at_time(
                'people_count',
                {'stop_id': 'S001'},
                datetime(2024, 1, 15, 10, 30)
            )
        """
        # Build WHERE clause from dimensions
        where_clauses = [
            f"{key} = '{value}'" for key, value in dimensions.items()
        ]
        where_clause = " AND ".join(where_clauses)
        
        # Convert timestamp to ISO8601 format
        timestamp_iso = timestamp.isoformat()
        
        query = f"""
            SELECT *
            FROM "{self.database_name}"."{table_name}"
            WHERE {where_clause}
            AND time <= from_iso8601_timestamp('{timestamp_iso}')
            ORDER BY time DESC
            LIMIT {limit}
        """
        
        return self._execute_query(query)
    
    def query_time_range(
        self,
        table_name: str,
        dimensions: Dict[str, str],
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Query data within a time range.
        
        Args:
            table_name: Name of the Timestream table
            dimensions: Dictionary of dimension names and values to filter by
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Optional maximum number of results to return
        
        Returns:
            Dictionary with query results or None if no data found
        
        Example:
            result = client.query_time_range(
                'people_count',
                {'stop_id': 'S001'},
                datetime(2024, 1, 15, 10, 0),
                datetime(2024, 1, 15, 11, 0)
            )
        """
        # Build WHERE clause from dimensions
        where_clauses = [
            f"{key} = '{value}'" for key, value in dimensions.items()
        ]
        where_clause = " AND ".join(where_clauses)
        
        # Convert timestamps to ISO8601 format
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()
        
        query = f"""
            SELECT *
            FROM "{self.database_name}"."{table_name}"
            WHERE {where_clause}
            AND time >= from_iso8601_timestamp('{start_iso}')
            AND time <= from_iso8601_timestamp('{end_iso}')
            ORDER BY time DESC
        """
        
        if limit:
            query += f"\nLIMIT {limit}"
        
        return self._execute_query(query)
    
    def _execute_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Execute a Timestream query and return results.
        
        Args:
            query: SQL query string
        
        Returns:
            Dictionary with query results or None if no data found
        
        Raises:
            ClientError: If query execution fails
        """
        try:
            logger.debug(f"Executing Timestream query: {query}")
            
            response = self.query_client.query(QueryString=query)
            
            rows = response.get('Rows', [])
            if not rows:
                logger.info("Query returned no results")
                return None
            
            # Parse column metadata
            columns = response.get('ColumnInfo', [])
            column_names = [col['Name'] for col in columns]
            
            # Parse rows into dictionaries
            results = []
            for row in rows:
                row_data = {}
                for i, data in enumerate(row.get('Data', [])):
                    column_name = column_names[i]
                    # Extract scalar value
                    row_data[column_name] = data.get('ScalarValue')
                results.append(row_data)
            
            logger.info(f"Query returned {len(results)} results")
            
            return {
                'rows': results,
                'column_info': columns,
                'query_id': response.get('QueryId')
            }
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"Timestream query failed: {error_code} - {str(e)}")
            raise
