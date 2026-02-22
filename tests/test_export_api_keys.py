"""
Unit tests for the export_api_keys.py script.

Tests the API key export functionality including:
- Retrieving API keys from Terraform outputs
- Generating text and JSON output formats
- Including REST and WebSocket endpoints
- Providing usage instructions and examples
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import export_api_keys


class TestExportApiKeys(unittest.TestCase):
    """Test suite for API key export functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_keys = [
            {'name': 'participant-1', 'key': 'test-key-1234567890abcdef'},
            {'name': 'participant-2', 'key': 'test-key-0987654321fedcba'},
            {'name': 'participant-3', 'key': 'test-key-abcdef1234567890'}
        ]
        
        self.sample_endpoints = {
            'rest': 'https://api123.execute-api.eu-west-1.amazonaws.com/prod',
            'websocket': 'https://ws456.execute-api.eu-west-1.amazonaws.com/prod'
        }
    
    @patch('export_api_keys.subprocess.run')
    def test_get_terraform_output(self, mock_run):
        """Test retrieving Terraform output values."""
        mock_run.return_value = MagicMock(
            stdout='test-output-value',
            returncode=0
        )
        
        result = export_api_keys.get_terraform_output('test_output')
        
        self.assertEqual(result, 'test-output-value')
        mock_run.assert_called_once()
    
    @patch('export_api_keys.subprocess.run')
    def test_get_terraform_output_json(self, mock_run):
        """Test retrieving Terraform output as JSON."""
        test_data = ['key1', 'key2', 'key3']
        mock_run.return_value = MagicMock(
            stdout=json.dumps(test_data),
            returncode=0
        )
        
        result = export_api_keys.get_terraform_output_json('test_output')
        
        self.assertEqual(result, test_data)
        mock_run.assert_called_once()
    
    @patch('export_api_keys.get_terraform_output_json')
    def test_get_api_keys_from_terraform(self, mock_get_output):
        """Test retrieving API keys from Terraform."""
        mock_get_output.return_value = [
            'test-key-1234567890abcdef',
            'test-key-0987654321fedcba'
        ]
        
        result = export_api_keys.get_api_keys_from_terraform('eu-west-1')
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'participant-1')
        self.assertEqual(result[0]['key'], 'test-key-1234567890abcdef')
        self.assertEqual(result[1]['name'], 'participant-2')
        self.assertEqual(result[1]['key'], 'test-key-0987654321fedcba')
    
    @patch('export_api_keys.get_terraform_output')
    def test_get_api_endpoints(self, mock_get_output):
        """Test retrieving API endpoints from Terraform."""
        def side_effect(output_name, *args, **kwargs):
            if output_name == 'api_gateway_rest_endpoint':
                return self.sample_endpoints['rest']
            elif output_name == 'api_gateway_websocket_endpoint':
                return self.sample_endpoints['websocket']
        
        mock_get_output.side_effect = side_effect
        
        result = export_api_keys.get_api_endpoints('eu-west-1')
        
        self.assertEqual(result['rest'], self.sample_endpoints['rest'])
        self.assertEqual(result['websocket'], self.sample_endpoints['websocket'])
    
    def test_generate_text_output(self):
        """Test generating text format output."""
        result = export_api_keys.generate_text_output(
            self.sample_keys,
            self.sample_endpoints
        )
        
        # Check that output contains key elements
        self.assertIn('Madrid Bus Real-Time Simulator', result)
        self.assertIn('API KEYS', result)
        self.assertIn('participant-1: test-key-1234567890abcdef', result)
        self.assertIn('participant-2: test-key-0987654321fedcba', result)
        self.assertIn('participant-3: test-key-abcdef1234567890', result)
        
        # Check REST API endpoint
        self.assertIn(self.sample_endpoints['rest'], result)
        
        # Check WebSocket endpoint
        self.assertIn(self.sample_endpoints['websocket'], result)
        
        # Check usage instructions
        self.assertIn('USAGE INSTRUCTIONS', result)
        self.assertIn('x-api-key', result)
        
        # Check REST API examples
        self.assertIn('REST API EXAMPLES', result)
        self.assertIn('people-count', result)
        self.assertIn('sensors', result)
        self.assertIn('bus-position', result)
        self.assertIn('curl', result)
        
        # Check WebSocket examples
        self.assertIn('WEBSOCKET EXAMPLES', result)
        self.assertIn('wscat', result)
        self.assertIn('subscribe', result)
        
        # Check rate limits
        self.assertIn('RATE LIMITS', result)
        self.assertIn('50 requests per second', result)
        self.assertIn('10,000 requests per day', result)
    
    def test_generate_json_output(self):
        """Test generating JSON format output."""
        result = export_api_keys.generate_json_output(
            self.sample_keys,
            self.sample_endpoints
        )
        
        # Parse JSON
        data = json.loads(result)
        
        # Check structure
        self.assertIn('generated_at', data)
        self.assertIn('endpoints', data)
        self.assertIn('api_keys', data)
        self.assertIn('rate_limits', data)
        self.assertIn('usage_examples', data)
        
        # Check endpoints
        self.assertEqual(data['endpoints']['rest_api'], self.sample_endpoints['rest'])
        self.assertEqual(data['endpoints']['websocket_api'], self.sample_endpoints['websocket'])
        
        # Check API keys
        self.assertEqual(len(data['api_keys']), 3)
        self.assertEqual(data['api_keys'][0]['participant'], 'participant-1')
        self.assertEqual(data['api_keys'][0]['api_key'], 'test-key-1234567890abcdef')
        
        # Check rate limits
        self.assertEqual(data['rate_limits']['requests_per_second'], 50)
        self.assertEqual(data['rate_limits']['burst_limit'], 100)
        self.assertEqual(data['rate_limits']['requests_per_day'], 10000)
        
        # Check usage examples
        self.assertIn('rest_api', data['usage_examples'])
        self.assertIn('websocket', data['usage_examples'])
        self.assertIn('latest_people_count', data['usage_examples']['rest_api'])
        self.assertIn('latest_sensor_data', data['usage_examples']['rest_api'])
        self.assertIn('latest_bus_position', data['usage_examples']['rest_api'])
        
        # Check WebSocket example
        ws_url = data['usage_examples']['websocket']['connection_url']
        self.assertIn('wss://', ws_url)
        self.assertIn('api_key=YOUR_API_KEY', ws_url)
    
    def test_generate_json_output_valid_json(self):
        """Test that generated JSON output is valid JSON."""
        result = export_api_keys.generate_json_output(
            self.sample_keys,
            self.sample_endpoints
        )
        
        # Should not raise exception
        data = json.loads(result)
        self.assertIsInstance(data, dict)
    
    def test_text_output_includes_all_api_keys(self):
        """Test that text output includes all API keys."""
        result = export_api_keys.generate_text_output(
            self.sample_keys,
            self.sample_endpoints
        )
        
        for key_info in self.sample_keys:
            self.assertIn(key_info['name'], result)
            self.assertIn(key_info['key'], result)
    
    def test_json_output_includes_all_api_keys(self):
        """Test that JSON output includes all API keys."""
        result = export_api_keys.generate_json_output(
            self.sample_keys,
            self.sample_endpoints
        )
        
        data = json.loads(result)
        
        self.assertEqual(len(data['api_keys']), len(self.sample_keys))
        
        for i, key_info in enumerate(self.sample_keys):
            self.assertEqual(data['api_keys'][i]['participant'], key_info['name'])
            self.assertEqual(data['api_keys'][i]['api_key'], key_info['key'])
    
    def test_text_output_includes_curl_examples(self):
        """Test that text output includes curl command examples."""
        result = export_api_keys.generate_text_output(
            self.sample_keys,
            self.sample_endpoints
        )
        
        # Check for curl commands
        self.assertIn('curl -H', result)
        self.assertIn("'x-api-key: YOUR_API_KEY'", result)
        
        # Check for different endpoint examples
        self.assertIn('/people-count/', result)
        self.assertIn('/sensors/', result)
        self.assertIn('/bus-position/', result)
        self.assertIn('?mode=latest', result)
        self.assertIn('?timestamp=', result)
    
    def test_websocket_url_conversion(self):
        """Test that WebSocket URL is correctly converted from https to wss."""
        result = export_api_keys.generate_json_output(
            self.sample_keys,
            self.sample_endpoints
        )
        
        data = json.loads(result)
        ws_url = data['usage_examples']['websocket']['connection_url']
        
        # Should convert https:// to wss://
        self.assertTrue(ws_url.startswith('wss://'))
        self.assertNotIn('https://', ws_url)


if __name__ == '__main__':
    unittest.main()
