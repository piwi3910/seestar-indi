#!/usr/bin/env python3

"""
Unit tests for Seestar focuser driver
"""

import unittest
from unittest.mock import Mock, patch
import PyIndi
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor
from seestar_focuser import SeestarFocuser

class TestSeestarFocuser(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock(spec=SeestarAPI)
        self.mock_monitor = Mock(spec=DeviceMonitor)
        
        # Setup monitor state
        self.mock_monitor.state.focus_position = 50000
        self.mock_monitor.state.focus_moving = False
        self.mock_monitor.state.auto_focusing = False
        self.mock_monitor.state.focus_temperature = 20.0
        self.mock_monitor.state.error = None
        
        self.focuser = SeestarFocuser(self.mock_api, self.mock_monitor)
        self.focuser.initProperties()
        
    def test_init_properties(self):
        """Test property initialization"""
        # Check absolute position property
        self.assertEqual(self.focuser.positionProp.np[0].min, 0)
        self.assertEqual(self.focuser.positionProp.np[0].max, 100000)
        self.assertEqual(self.focuser.positionProp.np[0].value, 50000)
        
        # Check relative position property
        self.assertEqual(self.focuser.relativeProp.np[0].min, -50000)
        self.assertEqual(self.focuser.relativeProp.np[0].max, 50000)
        
        # Check temperature property
        self.assertEqual(self.focuser.temperatureProp.np[0].value, 20.0)
        
    def test_absolute_movement(self):
        """Test absolute position movement"""
        # Setup mock API
        self.mock_api.send_command.return_value = {"Value": {"result": "success"}}
        
        # Create mock values for position
        values = Mock()
        names = ["FOCUS_ABSOLUTE_POSITION"]
        position_value = Mock()
        position_value.value = 75000
        
        # Simulate finding position value
        with patch.object(self.focuser, 'IUFindNumber', return_value=position_value):
            result = self.focuser.ISNewNumber(None, "ABS_FOCUS_POSITION", values, names)
            
        self.assertTrue(result)
        self.mock_api.send_command.assert_called_once()
        self.assertEqual(self.focuser.positionProp.s, PyIndi.IPS_BUSY)
        
    def test_relative_movement(self):
        """Test relative position movement"""
        # Setup mock API
        self.mock_api.send_command.return_value = {"Value": {"result": "success"}}
        
        # Create mock values for position
        values = Mock()
        names = ["FOCUS_RELATIVE_POSITION"]
        position_value = Mock()
        position_value.value = 1000  # Move 1000 steps
        
        # Simulate finding position value
        with patch.object(self.focuser, 'IUFindNumber', return_value=position_value):
            result = self.focuser.ISNewNumber(None, "REL_FOCUS_POSITION", values, names)
            
        self.assertTrue(result)
        self.mock_api.send_command.assert_called_once()
        self.assertEqual(self.focuser.positionProp.s, PyIndi.IPS_BUSY)
        
    def test_auto_focus(self):
        """Test auto focus control"""
        # Setup mock monitor
        self.mock_monitor.start_autofocus.return_value = True
        
        # Create mock values for auto focus
        states = Mock()
        names = ["FOCUS_AUTO_TOGGLE"]
        auto_switch = Mock()
        auto_switch.s = PyIndi.ISS_ON
        
        # Simulate finding auto focus switch
        with patch.object(self.focuser, 'IUFindSwitch', return_value=auto_switch):
            result = self.focuser.ISNewSwitch(None, "FOCUS_AUTO", states, names)
            
        self.assertTrue(result)
        self.mock_monitor.start_autofocus.assert_called_once()
        self.assertEqual(self.focuser.autoFocusProp.s, PyIndi.IPS_BUSY)
        
    def test_invalid_absolute_position(self):
        """Test handling of invalid absolute positions"""
        # Create mock values for position
        values = Mock()
        names = ["FOCUS_ABSOLUTE_POSITION"]
        position_value = Mock()
        position_value.value = 150000  # Beyond max position
        
        # Simulate finding position value
        with patch.object(self.focuser, 'IUFindNumber', return_value=position_value):
            result = self.focuser.ISNewNumber(None, "ABS_FOCUS_POSITION", values, names)
            
        self.assertFalse(result)
        self.mock_api.send_command.assert_not_called()
        
    def test_invalid_relative_position(self):
        """Test handling of invalid relative positions"""
        # Create mock values for position
        values = Mock()
        names = ["FOCUS_RELATIVE_POSITION"]
        position_value = Mock()
        position_value.value = 60000  # Would move beyond max position
        
        # Simulate finding position value
        with patch.object(self.focuser, 'IUFindNumber', return_value=position_value):
            result = self.focuser.ISNewNumber(None, "REL_FOCUS_POSITION", values, names)
            
        self.assertFalse(result)
        self.mock_api.send_command.assert_not_called()
        
    def test_movement_while_moving(self):
        """Test starting movement while already moving"""
        # Set focuser as moving
        self.mock_monitor.state.focus_moving = True
        
        # Create mock values for position
        values = Mock()
        names = ["FOCUS_ABSOLUTE_POSITION"]
        position_value = Mock()
        position_value.value = 60000
        
        # Simulate finding position value
        with patch.object(self.focuser, 'IUFindNumber', return_value=position_value):
            result = self.focuser.ISNewNumber(None, "ABS_FOCUS_POSITION", values, names)
            
        self.assertFalse(result)
        self.mock_api.send_command.assert_not_called()
        
    def test_auto_focus_while_moving(self):
        """Test starting auto focus while moving"""
        # Set focuser as moving
        self.mock_monitor.state.focus_moving = True
        
        # Create mock values for auto focus
        states = Mock()
        names = ["FOCUS_AUTO_TOGGLE"]
        auto_switch = Mock()
        auto_switch.s = PyIndi.ISS_ON
        
        # Simulate finding auto focus switch
        with patch.object(self.focuser, 'IUFindSwitch', return_value=auto_switch):
            result = self.focuser.ISNewSwitch(None, "FOCUS_AUTO", states, names)
            
        self.assertFalse(result)
        self.mock_monitor.start_autofocus.assert_not_called()
        
    def test_state_change_handling(self):
        """Test state change event handling"""
        # Test position change
        event = {
            "property": "focus_position",
            "new_value": 60000
        }
        self.focuser._handle_state_change(event)
        self.assertEqual(self.focuser.positionProp.np[0].value, 60000)
        
        # Test movement state change
        event = {
            "property": "focus_moving",
            "new_value": True
        }
        self.focuser._handle_state_change(event)
        self.assertEqual(self.focuser.positionProp.s, PyIndi.IPS_BUSY)
        
        event["new_value"] = False
        self.focuser._handle_state_change(event)
        self.assertEqual(self.focuser.positionProp.s, PyIndi.IPS_OK)
        
        # Test temperature change
        event = {
            "property": "focus_temperature",
            "new_value": 22.5
        }
        self.focuser._handle_state_change(event)
        self.assertEqual(self.focuser.temperatureProp.np[0].value, 22.5)
        
    def test_error_handling(self):
        """Test error state handling"""
        event = {
            "property": "error",
            "new_value": "Test error"
        }
        self.focuser._handle_state_change(event)
        self.assertEqual(self.focuser.positionProp.s, PyIndi.IPS_ALERT)
        
    def test_connection_control(self):
        """Test connection control"""
        # Create mock values for connection
        states = Mock()
        names = ["CONNECT", "DISCONNECT"]
        connect_switch = Mock()
        connect_switch.s = PyIndi.ISS_ON
        
        # Simulate finding connect switch
        with patch.object(self.focuser, 'IUFindSwitch', return_value=connect_switch):
            result = self.focuser.ISNewSwitch(None, "CONNECTION", states, names)
            
        self.assertTrue(result)
        self.assertEqual(self.focuser.connectProp.s, PyIndi.IPS_OK)
        
    def test_property_updates(self):
        """Test property updates on connection changes"""
        # Test connected state
        with patch.object(self.focuser, 'isConnected', return_value=True):
            self.focuser.updateProperties()
            # Properties should be defined
            
        # Test disconnected state
        with patch.object(self.focuser, 'isConnected', return_value=False):
            self.focuser.updateProperties()
            # Properties should be deleted

if __name__ == '__main__':
    unittest.main()
