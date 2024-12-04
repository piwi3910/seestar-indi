#!/usr/bin/env python3

"""
Unit tests for Seestar camera driver
"""

import unittest
from unittest.mock import Mock, patch
import PyIndi
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor
from seestar_camera import SeestarCamera

class TestSeestarCamera(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock(spec=SeestarAPI)
        self.mock_monitor = Mock(spec=DeviceMonitor)
        
        # Setup monitor state
        self.mock_monitor.state.exposing = False
        self.mock_monitor.state.error = None
        
        self.camera = SeestarCamera(self.mock_api, self.mock_monitor)
        self.camera.initProperties()
        
    def test_init_properties(self):
        """Test property initialization"""
        # Check CCD info properties
        self.assertEqual(self.camera.ccdInfoProp.np[0].value, 1920)  # width
        self.assertEqual(self.camera.ccdInfoProp.np[1].value, 1080)  # height
        self.assertEqual(self.camera.ccdInfoProp.np[2].value, 3.75)  # pixel size
        self.assertEqual(self.camera.ccdInfoProp.np[3].value, 12)    # bit depth
        
        # Check exposure property
        self.assertEqual(self.camera.exposureProp.np[0].min, 0.001)
        self.assertEqual(self.camera.exposureProp.np[0].max, 3600)
        
        # Check gain property
        self.assertEqual(self.camera.gainProp.np[0].min, 0)
        self.assertEqual(self.camera.gainProp.np[0].max, 100)
        
    def test_exposure_control(self):
        """Test exposure control"""
        # Setup mock monitor
        self.mock_monitor.start_exposure.return_value = True
        
        # Create mock values for exposure
        values = Mock()
        names = ["CCD_EXPOSURE_VALUE"]
        exposure_value = Mock()
        exposure_value.value = 2.0
        
        # Simulate finding exposure value
        with patch.object(self.camera, 'IUFindNumber', return_value=exposure_value):
            result = self.camera.ISNewNumber(None, "CCD_EXPOSURE", values, names)
            
        self.assertTrue(result)
        self.mock_monitor.start_exposure.assert_called_once_with(2.0, 1)
        self.assertEqual(self.camera.exposureProp.s, PyIndi.IPS_BUSY)
        
    def test_gain_control(self):
        """Test gain control"""
        # Create mock values for gain
        values = Mock()
        names = ["GAIN"]
        gain_value = Mock()
        gain_value.value = 50
        
        # Simulate finding gain value
        with patch.object(self.camera, 'IUFindNumber', return_value=gain_value):
            result = self.camera.ISNewNumber(None, "CCD_GAIN", values, names)
            
        self.assertTrue(result)
        self.assertEqual(self.camera.gainProp.np[0].value, 50)
        self.assertEqual(self.camera.gainProp.s, PyIndi.IPS_OK)
        
    def test_frame_type_control(self):
        """Test frame type switching"""
        # Create mock values for frame type
        states = Mock()
        names = ["FRAME_LIGHT", "FRAME_DARK", "FRAME_BIAS", "FRAME_FLAT"]
        
        # Simulate frame type switch
        with patch.object(self.camera, 'IUUpdateSwitch') as mock_update:
            result = self.camera.ISNewSwitch(None, "CCD_FRAME_TYPE", states, names)
            
        self.assertTrue(result)
        mock_update.assert_called_once()
        
    def test_exposure_while_busy(self):
        """Test starting exposure while already exposing"""
        # Set camera as exposing
        self.mock_monitor.state.exposing = True
        
        # Create mock values for exposure
        values = Mock()
        names = ["CCD_EXPOSURE_VALUE"]
        exposure_value = Mock()
        exposure_value.value = 2.0
        
        # Simulate finding exposure value
        with patch.object(self.camera, 'IUFindNumber', return_value=exposure_value):
            result = self.camera.ISNewNumber(None, "CCD_EXPOSURE", values, names)
            
        self.assertFalse(result)
        self.mock_monitor.start_exposure.assert_not_called()
        
    def test_exposure_complete_callback(self):
        """Test exposure complete event handling"""
        # Create exposure complete event
        event = {"type": "exposure_complete"}
        
        # Handle event
        self.camera._handle_exposure_complete(event)
        
        # Check state updates
        self.assertEqual(self.camera.exposureProp.s, PyIndi.IPS_OK)
        
    def test_error_handling(self):
        """Test error state handling"""
        # Create error state change event
        event = {
            "property": "error",
            "new_value": "Test error"
        }
        
        # Handle event
        self.camera._handle_state_change(event)
        
        # Check error handling
        self.assertEqual(self.camera.exposureProp.s, PyIndi.IPS_ALERT)
        
    def test_connection_control(self):
        """Test connection control"""
        # Create mock values for connection
        states = Mock()
        names = ["CONNECT", "DISCONNECT"]
        connect_switch = Mock()
        connect_switch.s = PyIndi.ISS_ON
        
        # Simulate finding connect switch
        with patch.object(self.camera, 'IUFindSwitch', return_value=connect_switch):
            result = self.camera.ISNewSwitch(None, "CONNECTION", states, names)
            
        self.assertTrue(result)
        self.assertEqual(self.camera.connectProp.s, PyIndi.IPS_OK)
        
    def test_invalid_exposure_value(self):
        """Test handling of invalid exposure values"""
        # Create mock values for exposure
        values = Mock()
        names = ["CCD_EXPOSURE_VALUE"]
        exposure_value = Mock()
        exposure_value.value = -1.0  # Invalid value
        
        # Simulate finding exposure value
        with patch.object(self.camera, 'IUFindNumber', return_value=exposure_value):
            result = self.camera.ISNewNumber(None, "CCD_EXPOSURE", values, names)
            
        self.assertFalse(result)
        self.mock_monitor.start_exposure.assert_not_called()
        
    def test_invalid_gain_value(self):
        """Test handling of invalid gain values"""
        # Create mock values for gain
        values = Mock()
        names = ["GAIN"]
        gain_value = Mock()
        gain_value.value = 150  # Invalid value
        
        # Simulate finding gain value
        with patch.object(self.camera, 'IUFindNumber', return_value=gain_value):
            result = self.camera.ISNewNumber(None, "CCD_GAIN", values, names)
            
        self.assertFalse(result)
        
    def test_property_updates(self):
        """Test property updates on connection changes"""
        # Test connected state
        with patch.object(self.camera, 'isConnected', return_value=True):
            self.camera.updateProperties()
            # Properties should be defined
            
        # Test disconnected state
        with patch.object(self.camera, 'isConnected', return_value=False):
            self.camera.updateProperties()
            # Properties should be deleted

if __name__ == '__main__':
    unittest.main()
