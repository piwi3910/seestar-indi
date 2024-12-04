#!/usr/bin/env python3

"""
Unit tests for Seestar API client
"""

import unittest
from unittest.mock import Mock, patch
import json
import requests
from seestar_api import SeestarAPI

class TestSeestarAPI(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.api = SeestarAPI(host="localhost", port=5555, device_num=1)
        
    @patch('requests.Session.put')
    def test_send_command_success(self, mock_put):
        """Test successful command sending"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"Value": {"result": {"ra": 10.5, "dec": 45.0}}}
        mock_put.return_value = mock_response
        
        result = self.api.send_command(
            "method_sync",
            {"method": "scope_get_equ_coord"}
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result["Value"]["result"]["ra"], 10.5)
        self.assertEqual(result["Value"]["result"]["dec"], 45.0)
        
    @patch('requests.Session.put')
    def test_send_command_network_error(self, mock_put):
        """Test handling of network errors"""
        mock_put.side_effect = requests.exceptions.ConnectionError()
        
        result = self.api.send_command(
            "method_sync",
            {"method": "scope_get_equ_coord"}
        )
        
        self.assertIsNone(result)
        
    @patch('requests.Session.put')
    def test_send_command_invalid_json(self, mock_put):
        """Test handling of invalid JSON responses"""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_put.return_value = mock_response
        
        result = self.api.send_command(
            "method_sync",
            {"method": "scope_get_equ_coord"}
        )
        
        self.assertIsNone(result)
        
    def test_get_coordinates(self):
        """Test coordinate retrieval"""
        with patch.object(self.api, 'send_command') as mock_send:
            mock_send.return_value = {
                "Value": {
                    "result": {
                        "ra": 15.5,
                        "dec": -30.0
                    }
                }
            }
            
            coords = self.api.get_coordinates()
            
            self.assertIsNotNone(coords)
            self.assertEqual(coords["ra"], 15.5)
            self.assertEqual(coords["dec"], -30.0)
            
    def test_goto_target(self):
        """Test goto command"""
        with patch.object(self.api, 'send_command') as mock_send:
            mock_send.return_value = {"Value": {"result": "success"}}
            
            result = self.api.goto_target(
                ra="12:00:00",
                dec="+45:00:00",
                target_name="Test Target"
            )
            
            self.assertTrue(result)
            mock_send.assert_called_once()
            
    def test_sync_position(self):
        """Test position syncing"""
        with patch.object(self.api, 'send_command') as mock_send:
            mock_send.return_value = {"Value": {"result": "success"}}
            
            result = self.api.sync_position(ra=12.5, dec=45.0)
            
            self.assertTrue(result)
            mock_send.assert_called_once()
            
    def test_response_caching(self):
        """Test response caching functionality"""
        with patch.object(self.api, 'send_command') as mock_send:
            mock_send.return_value = {
                "Value": {
                    "result": {
                        "ra": 15.5,
                        "dec": -30.0
                    }
                }
            }
            
            # First call should hit the API
            coords1 = self.api.get_coordinates()
            
            # Second call within cache timeout should use cached value
            coords2 = self.api.get_coordinates()
            
            self.assertEqual(coords1, coords2)
            mock_send.assert_called_once()  # Should only be called once due to caching

if __name__ == '__main__':
    unittest.main()
