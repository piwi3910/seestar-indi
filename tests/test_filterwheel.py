#!/usr/bin/env python3

"""
Unit tests for Seestar filter wheel driver
"""

import unittest
from unittest.mock import Mock, patch
import PyIndi
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor
from seestar_filterwheel import SeestarFilterWheel

class TestSeestarFilterWheel(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock(spec=SeestarAPI)
        self.mock_monitor = Mock(spec=DeviceMonitor)
        
        # Setup monitor state
        self.mock_monitor.state.filter_position = 0
        self.mock_monitor.state.filter_moving = False
        self.mock_monitor.state.error = None
        
        self.filterwheel = SeestarFilterWheel(self.mock_api, self.mock_monitor)
        self.filterwheel.initProperties()
        
    def test_init_properties(self):
        """Test property initialization"""
        # Check filter slot property
        self.assertEqual(self.filterwheel.filterSlotProp.np[0].min, 1)
        self.assertEqual(self.filterwheel.filterSlotProp.np[0].max, 2)  # Clear and LP filters
        
        # Check filter names property
        self.assertEqual(self.filterwheel.filterNamesProp.tp[0].text, "Clear")
        self.assertEqual(self.filterwheel.filterNamesProp.tp[1].text, "LP")
        
    def test_filter_movement(self):
        """Test filter movement control"""
        # Setup mock monitor
        self.mock_monitor.move_filter.return_value = True
        
        # Create mock values for filter position
        values = Mock()
        names = ["FILTER_SLOT_VALUE"]
        position_value = Mock()
        position_value.value = 2  # Move to LP filter
        
        # Simulate finding position value
        with patch.object(self.filterwheel, 'IUFindNumber', return_value=position_value):
            result = self.filterwheel.ISNewNumber(None, "FILTER_SLOT", values, names)
            
        self.assertTrue(result)
        self.mock_monitor.move_filter.assert_called_once_with(1)  # 0-based index
        self.assertEqual(self.filterwheel.filterSlotProp.s, PyIndi.IPS_BUSY)
        
    def test_filter_names(self):
        """Test filter name setting"""
        # Create mock values for filter names
        texts = Mock()
        names = ["FILTER_NAME_1", "FILTER_NAME_2"]
        
        # Create mock text values
        def mock_find_text(texts, name):
            mock_text = Mock()
            mock_text.text = "Test Filter" if name == "FILTER_NAME_1" else "LP Filter"
            return mock_text
            
        # Simulate setting filter names
        with patch.object(self.filterwheel, 'IUFindText', side_effect=mock_find_text):
            result = self.filterwheel.ISNewText(None, "FILTER_NAME", texts, names)
            
        self.assertTrue(result)
        self.assertEqual(self.filterwheel.filter_names[0], "Test Filter")
        self.assertEqual(self.filterwheel.filter_names[1], "LP Filter")
        
    def test_invalid_position(self):
        """Test handling of invalid filter positions"""
        # Create mock values for position
        values = Mock()
        names = ["FILTER_SLOT_VALUE"]
        position_value = Mock()
        position_value.value = 3  # Invalid position
        
        # Simulate finding position value
        with patch.object(self.filterwheel, 'IUFindNumber', return_value=position_value):
            result = self.filterwheel.ISNewNumber(None, "FILTER_SLOT", values, names)
            
        self.assertFalse(result)
        self.mock_monitor.move_filter.assert_not_called()
        
    def test_movement_while_moving(self):
        """Test starting movement while already moving"""
        # Set filter wheel as moving
        self.mock_monitor.state.filter_moving = True
        
        # Create mock values for position
        values = Mock()
        names = ["FILTER_SLOT_VALUE"]
        position_value = Mock()
        position_value.value = 2
        
        # Simulate finding position value
        with patch.object(self.filterwheel, 'IUFindNumber', return_value=position_value):
            result = self.filterwheel.ISNewNumber(None, "FILTER_SLOT", values, names)
            
        self.assertFalse(result)
        self.mock_monitor.move_filter.assert_not_called()
        
    def test_state_change_handling(self):
        """Test state change event handling"""
        # Test position change
        event = {
            "property": "filter_position",
            "new_value": 1
        }
        self.filterwheel._handle_state_change(event)
        self.assertEqual(self.filterwheel.filterSlotProp.np[0].value, 2)  # 1-based index
        
        # Test movement state change
        event = {
            "property": "filter_moving",
            "new_value": True
        }
        self.filterwheel._handle_state_change(event)
        self.assertEqual(self.filterwheel.filterSlotProp.s, PyIndi.IPS_BUSY)
        
        event["new_value"] = False
        self.filterwheel._handle_state_change(event)
        self.assertEqual(self.filterwheel.filterSlotProp.s, PyIndi.IPS_OK)
        
    def test_error_handling(self):
        """Test error state handling"""
        event = {
            "property": "error",
            "new_value": "Test error"
        }
        self.filterwheel._handle_state_change(event)
        self.assertEqual(self.filterwheel.filterSlotProp.s, PyIndi.IPS_ALERT)
        
    def test_connection_control(self):
        """Test connection control"""
        # Create mock values for connection
        states = Mock()
        names = ["CONNECT", "DISCONNECT"]
        connect_switch = Mock()
        connect_switch.s = PyIndi.ISS_ON
        
        # Simulate finding connect switch
        with patch.object(self.filterwheel, 'IUFindSwitch', return_value=connect_switch):
            result = self.filterwheel.ISNewSwitch(None, "CONNECTION", states, names)
            
        self.assertTrue(result)
        self.assertEqual(self.filterwheel.connectProp.s, PyIndi.IPS_OK)
        
    def test_property_updates(self):
        """Test property updates on connection changes"""
        # Test connected state
        with patch.object(self.filterwheel, 'isConnected', return_value=True):
            self.filterwheel.updateProperties()
            # Properties should be defined
            
        # Test disconnected state
        with patch.object(self.filterwheel, 'isConnected', return_value=False):
            self.filterwheel.updateProperties()
            # Properties should be deleted
            
    def test_filter_name_validation(self):
        """Test filter name validation"""
        # Create mock values with empty name
        texts = Mock()
        names = ["FILTER_NAME_1"]
        
        def mock_find_text(texts, name):
            mock_text = Mock()
            mock_text.text = ""  # Empty name
            return mock_text
            
        # Simulate setting empty filter name
        with patch.object(self.filterwheel, 'IUFindText', side_effect=mock_find_text):
            result = self.filterwheel.ISNewText(None, "FILTER_NAME", texts, names)
            
        self.assertFalse(result)
        self.assertEqual(self.filterwheel.filter_names[0], "Clear")  # Name should not change

if __name__ == '__main__':
    unittest.main()
