"""
Integration test for configuration loading script.

**Property 33: Configuration data loading**

This test verifies that the load_config.py script correctly:
1. Parses lines.yaml configuration file
2. Uploads configuration to S3 bucket
3. Stores route waypoints for Amazon Location usage

**Validates: Requirements 7.4**
"""

import unittest
from unittest.mock import patch, MagicMock, call
import tempfile
import json
import yaml
from pathlib import Path
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from load_config import (
    load_lines_config,
    upload_to_s3,
    store_route_waypoints
)


class TestConfigurationLoadingIntegration(unittest.TestCase):
    """
    Integration tests for configuration loading script.
    
    Property 33: Configuration data loading
    Validates: Requirements 7.4
    """
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_config = {
            'lines': [
                {
                    'line_id': 'L1',
                    'name': 'Test Line 1',
                    'stops': [
                        {
                            'stop_id': 'S1',
                            'name': 'Stop 1',
                            'latitude': 40.4168,
                            'longitude': -3.7038,
                            'is_terminal': True,
                            'base_arrival_rate': 2.5
                        },
                        {
                            'stop_id': 'S2',
                            'name': 'Stop 2',
                            'latitude': 40.4200,
                            'longitude': -3.7050,
                            'is_terminal': False,
                            'base_arrival_rate': 1.8
                        }
                    ]
                },
                {
                    'line_id': 'L2',
                    'name': 'Test Line 2',
                    'stops': [
                        {
                            'stop_id': 'S3',
                            'name': 'Stop 3',
                            'latitude': 40.4300,
                            'longitude': -3.7100,
                            'is_terminal': True,
                            'base_arrival_rate': 2.0
                        },
                        {
                            'stop_id': 'S4',
                            'name': 'Stop 4',
                            'latitude': 40.4350,
                            'longitude': -3.7150,
                            'is_terminal': False,
                            'base_arrival_rate': 1.5
                        }
                    ]
                }
            ]
        }
        
        self.bucket_name = 'test-config-bucket'
        self.region = 'eu-west-1'
    
    def test_load_lines_config_parses_yaml_correctly(self):
        """Test that load_lines_config correctly parses YAML file."""
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.test_config, f)
            temp_path = f.name
        
        try:
            # Load configuration
            config = load_lines_config(temp_path)
            
            # Verify structure
            self.assertIn('lines', config)
            self.assertEqual(len(config['lines']), 2)
            
            # Verify first line
            line1 = config['lines'][0]
            self.assertEqual(line1['line_id'], 'L1')
            self.assertEqual(line1['name'], 'Test Line 1')
            self.assertEqual(len(line1['stops']), 2)
            
            # Verify first stop
            stop1 = line1['stops'][0]
            self.assertEqual(stop1['stop_id'], 'S1')
            self.assertEqual(stop1['name'], 'Stop 1')
            self.assertEqual(stop1['latitude'], 40.4168)
            self.assertEqual(stop1['longitude'], -3.7038)
            self.assertTrue(stop1['is_terminal'])
            self.assertEqual(stop1['base_arrival_rate'], 2.5)
            
        finally:
            Path(temp_path).unlink()
    
    @patch('load_config.boto3.client')
    def test_upload_to_s3_uploads_yaml_configuration(self, mock_boto3_client):
        """Test that upload_to_s3 correctly uploads YAML configuration."""
        # Set up mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Upload configuration
        upload_to_s3(self.test_config, self.bucket_name, self.region)
        
        # Verify boto3 client was created with correct region
        mock_boto3_client.assert_called_once_with('s3', region_name=self.region)
        
        # Verify put_object was called
        mock_s3.put_object.assert_called_once()
        
        # Verify call arguments
        call_args = mock_s3.put_object.call_args
        self.assertEqual(call_args.kwargs['Bucket'], self.bucket_name)
        self.assertEqual(call_args.kwargs['Key'], 'config/lines.yaml')
        self.assertEqual(call_args.kwargs['ContentType'], 'application/x-yaml')
        
        # Verify uploaded content is valid YAML
        uploaded_yaml = call_args.kwargs['Body']
        parsed_config = yaml.safe_load(uploaded_yaml)
        self.assertEqual(parsed_config, self.test_config)
    
    @patch('load_config.boto3.client')
    def test_store_route_waypoints_creates_correct_json(self, mock_boto3_client):
        """Test that store_route_waypoints correctly stores route data as JSON."""
        # Set up mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Store route waypoints
        store_route_waypoints(self.test_config, self.bucket_name, self.region)
        
        # Verify boto3 client was created with correct region
        mock_boto3_client.assert_called_once_with('s3', region_name=self.region)
        
        # Verify put_object was called
        mock_s3.put_object.assert_called_once()
        
        # Verify call arguments
        call_args = mock_s3.put_object.call_args
        self.assertEqual(call_args.kwargs['Bucket'], self.bucket_name)
        self.assertEqual(call_args.kwargs['Key'], 'config/routes.json')
        self.assertEqual(call_args.kwargs['ContentType'], 'application/json')
        
        # Verify uploaded content is valid JSON with correct structure
        uploaded_json = call_args.kwargs['Body']
        routes_data = json.loads(uploaded_json)
        
        # Verify L1 route data
        self.assertIn('L1', routes_data)
        l1_data = routes_data['L1']
        self.assertEqual(l1_data['line_name'], 'Test Line 1')
        self.assertEqual(len(l1_data['waypoints']), 2)
        
        # Verify L1 first waypoint
        waypoint1 = l1_data['waypoints'][0]
        self.assertEqual(waypoint1['stop_id'], 'S1')
        self.assertEqual(waypoint1['name'], 'Stop 1')
        self.assertEqual(waypoint1['latitude'], 40.4168)
        self.assertEqual(waypoint1['longitude'], -3.7038)
        self.assertTrue(waypoint1['is_terminal'])
        
        # Verify L2 route data
        self.assertIn('L2', routes_data)
        l2_data = routes_data['L2']
        self.assertEqual(l2_data['line_name'], 'Test Line 2')
        self.assertEqual(len(l2_data['waypoints']), 2)
    
    @patch('load_config.boto3.client')
    def test_end_to_end_configuration_loading(self, mock_boto3_client):
        """
        Test end-to-end configuration loading process.
        
        This test verifies the complete workflow:
        1. Parse lines.yaml
        2. Upload YAML to S3
        3. Store route waypoints as JSON
        """
        # Set up mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Create temporary YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.test_config, f)
            temp_path = f.name
        
        try:
            # Step 1: Load configuration
            config = load_lines_config(temp_path)
            self.assertIsNotNone(config)
            self.assertIn('lines', config)
            
            # Step 2: Upload to S3
            upload_to_s3(config, self.bucket_name, self.region)
            
            # Step 3: Store route waypoints
            store_route_waypoints(config, self.bucket_name, self.region)
            
            # Verify both S3 uploads occurred
            self.assertEqual(mock_s3.put_object.call_count, 2)
            
            # Verify first call was for YAML
            yaml_call = mock_s3.put_object.call_args_list[0]
            self.assertEqual(yaml_call.kwargs['Key'], 'config/lines.yaml')
            self.assertEqual(yaml_call.kwargs['ContentType'], 'application/x-yaml')
            
            # Verify second call was for JSON
            json_call = mock_s3.put_object.call_args_list[1]
            self.assertEqual(json_call.kwargs['Key'], 'config/routes.json')
            self.assertEqual(json_call.kwargs['ContentType'], 'application/json')
            
        finally:
            Path(temp_path).unlink()
    
    def test_load_real_lines_yaml_file(self):
        """Test loading the actual data/lines.yaml file from the repository."""
        config_path = Path(__file__).parent.parent / 'data' / 'lines.yaml'
        
        if not config_path.exists():
            self.skipTest("data/lines.yaml not found")
        
        # Load the real configuration
        config = load_lines_config(str(config_path))
        
        # Verify basic structure
        self.assertIn('lines', config)
        self.assertGreater(len(config['lines']), 0)
        
        # Verify each line has required fields
        for line in config['lines']:
            self.assertIn('line_id', line)
            self.assertIn('name', line)
            self.assertIn('stops', line)
            self.assertGreater(len(line['stops']), 0)
            
            # Verify each stop has required fields
            for stop in line['stops']:
                self.assertIn('stop_id', stop)
                self.assertIn('name', stop)
                self.assertIn('latitude', stop)
                self.assertIn('longitude', stop)
                self.assertIn('is_terminal', stop)
                self.assertIn('base_arrival_rate', stop)
    
    @patch('load_config.boto3.client')
    def test_all_stops_accessible_after_loading(self, mock_boto3_client):
        """
        Test that all bus stops defined in configuration are accessible after loading.
        
        This verifies that the configuration loading process preserves all stop data
        and makes it available for API queries.
        """
        # Set up mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Load and upload configuration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.test_config, f)
            temp_path = f.name
        
        try:
            config = load_lines_config(temp_path)
            upload_to_s3(config, self.bucket_name, self.region)
            store_route_waypoints(config, self.bucket_name, self.region)
            
            # Extract uploaded routes data
            json_call = mock_s3.put_object.call_args_list[1]
            routes_json = json_call.kwargs['Body']
            routes_data = json.loads(routes_json)
            
            # Verify all stops from original config are in routes data
            original_stops = set()
            for line in self.test_config['lines']:
                for stop in line['stops']:
                    original_stops.add(stop['stop_id'])
            
            uploaded_stops = set()
            for line_id, line_data in routes_data.items():
                for waypoint in line_data['waypoints']:
                    uploaded_stops.add(waypoint['stop_id'])
            
            # All original stops should be in uploaded data
            self.assertEqual(original_stops, uploaded_stops)
            
        finally:
            Path(temp_path).unlink()
    
    @patch('load_config.boto3.client')
    def test_all_lines_accessible_after_loading(self, mock_boto3_client):
        """
        Test that all bus lines defined in configuration are accessible after loading.
        
        This verifies that the configuration loading process preserves all line data
        and makes it available for API queries.
        """
        # Set up mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Load and upload configuration
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.test_config, f)
            temp_path = f.name
        
        try:
            config = load_lines_config(temp_path)
            upload_to_s3(config, self.bucket_name, self.region)
            store_route_waypoints(config, self.bucket_name, self.region)
            
            # Extract uploaded routes data
            json_call = mock_s3.put_object.call_args_list[1]
            routes_json = json_call.kwargs['Body']
            routes_data = json.loads(routes_json)
            
            # Verify all lines from original config are in routes data
            original_lines = {line['line_id'] for line in self.test_config['lines']}
            uploaded_lines = set(routes_data.keys())
            
            # All original lines should be in uploaded data
            self.assertEqual(original_lines, uploaded_lines)
            
        finally:
            Path(temp_path).unlink()
    
    @patch('load_config.boto3.client')
    def test_route_waypoints_preserve_stop_order(self, mock_boto3_client):
        """
        Test that route waypoints preserve the order of stops from configuration.
        
        This is important for route geometry calculations and bus movement simulation.
        """
        # Set up mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Store route waypoints
        store_route_waypoints(self.test_config, self.bucket_name, self.region)
        
        # Extract uploaded routes data
        call_args = mock_s3.put_object.call_args
        routes_json = call_args.kwargs['Body']
        routes_data = json.loads(routes_json)
        
        # Verify stop order for L1
        l1_waypoints = routes_data['L1']['waypoints']
        self.assertEqual(l1_waypoints[0]['stop_id'], 'S1')
        self.assertEqual(l1_waypoints[1]['stop_id'], 'S2')
        
        # Verify stop order for L2
        l2_waypoints = routes_data['L2']['waypoints']
        self.assertEqual(l2_waypoints[0]['stop_id'], 'S3')
        self.assertEqual(l2_waypoints[1]['stop_id'], 'S4')
    
    @patch('load_config.boto3.client')
    def test_terminal_stops_marked_correctly(self, mock_boto3_client):
        """
        Test that terminal stops are correctly marked in route waypoints.
        
        This is critical for bus movement simulation and passenger reset logic.
        """
        # Set up mock S3 client
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        
        # Store route waypoints
        store_route_waypoints(self.test_config, self.bucket_name, self.region)
        
        # Extract uploaded routes data
        call_args = mock_s3.put_object.call_args
        routes_json = call_args.kwargs['Body']
        routes_data = json.loads(routes_json)
        
        # Verify terminal stops for L1
        l1_waypoints = routes_data['L1']['waypoints']
        self.assertTrue(l1_waypoints[0]['is_terminal'])  # S1 is terminal
        self.assertFalse(l1_waypoints[1]['is_terminal'])  # S2 is not terminal
        
        # Verify terminal stops for L2
        l2_waypoints = routes_data['L2']['waypoints']
        self.assertTrue(l2_waypoints[0]['is_terminal'])  # S3 is terminal
        self.assertFalse(l2_waypoints[1]['is_terminal'])  # S4 is not terminal


if __name__ == '__main__':
    unittest.main()
