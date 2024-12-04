#!/usr/bin/env python3

"""
Unit tests for Seestar device monitor
"""

import unittest
from unittest.mock import Mock, patch
import threading
import time
from queue import Queue
from seestar_api import SeestarAPI
from seestar_monitor import DeviceMonitor, DeviceState

class TestDeviceMonitor(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock(spec=SeestarAPI)
        self.monitor = DeviceMonitor(self.mock_api)
        
    def tearDown(self):
        """Clean up after tests"""
        if self.monitor.running:
            self.monitor.stop()
            
    def test_initial_state(self):
        """Test initial device state"""
        state = self.monitor.get_state()
        
        self.assertIsInstance(state, DeviceState)
        self.assertFalse(state.connected)
        self.assertIsNone(state.error)
        self.assertEqual(state.ra, 0.0)
        self.assertEqual(state.dec, 0.0)
        
    def test_state_update(self):
        """Test state update mechanism"""
        updates = {
            "ra": 15.5,
            "dec": -30.0,
            "connected": True
        }
        
        self.monitor._update_state(updates)
        state = self.monitor.get_state()
        
        self.assertEqual(state.ra, 15.5)
        self.assertEqual(state.dec, -30.0)
        self.assertTrue(state.connected)
        
    def test_event_callbacks(self):
        """Test event callback system"""
        callback_called = threading.Event()
        received_event = {}
        
        def test_callback(event):
            nonlocal received_event
            received_event = event
            callback_called.set()
            
        # Register callback
        self.monitor.add_event_callback("state_change", test_callback)
        
        # Trigger state change
        self.monitor._update_state({"ra": 12.0})
        
        # Wait for callback
        callback_called.wait(timeout=1.0)
        
        self.assertTrue(callback_called.is_set())
        self.assertEqual(received_event["type"], "state_change")
        self.assertEqual(received_event["property"], "ra")
        self.assertEqual(received_event["new_value"], 12.0)
        
    def test_monitor_loop(self):
        """Test monitoring loop functionality"""
        # Mock API responses
        self.mock_api.get_coordinates.return_value = {
            "ra": 10.0,
            "dec": 45.0
        }
        self.mock_api.is_slewing.return_value = False
        self.mock_api.get_temperature.return_value = 20.0
        
        # Start monitor
        self.monitor.start()
        
        # Give monitor time to update
        time.sleep(1)
        
        # Check state
        state = self.monitor.get_state()
        self.assertEqual(state.ra, 10.0)
        self.assertEqual(state.dec, 45.0)
        self.assertEqual(state.focus_temperature, 20.0)
        
        # Stop monitor
        self.monitor.stop()
        
    def test_exposure_tracking(self):
        """Test exposure state tracking"""
        # Start a mock exposure
        self.monitor.start_exposure(duration=2.0, gain=1)
        
        # Check initial state
        state = self.monitor.get_state()
        self.assertTrue(state.exposing)
        self.assertEqual(state.exposure_time, 2.0)
        self.assertEqual(state.gain, 1)
        
        # Wait for exposure to complete
        time.sleep(2.5)
        
        # Check final state
        state = self.monitor.get_state()
        self.assertFalse(state.exposing)
        
    def test_error_handling(self):
        """Test error state handling"""
        # Simulate API error
        self.mock_api.get_coordinates.side_effect = Exception("Test error")
        
        # Start monitor
        self.monitor.start()
        
        # Give monitor time to handle error
        time.sleep(1)
        
        # Check error state
        state = self.monitor.get_state()
        self.assertFalse(state.connected)
        self.assertIsNotNone(state.error)
        self.assertEqual(state.error, "Test error")
        
        # Stop monitor
        self.monitor.stop()
        
    def test_concurrent_access(self):
        """Test thread safety of state access"""
        def update_thread():
            for i in range(100):
                self.monitor._update_state({"ra": float(i)})
                
        def read_thread():
            for _ in range(100):
                state = self.monitor.get_state()
                self.assertIsInstance(state.ra, float)
                
        # Create threads
        update_thread = threading.Thread(target=update_thread)
        read_thread = threading.Thread(target=read_thread)
        
        # Start threads
        update_thread.start()
        read_thread.start()
        
        # Wait for completion
        update_thread.join()
        read_thread.join()
        
    def test_event_queue_overflow(self):
        """Test event queue overflow handling"""
        # Fill event queue
        for i in range(25):  # More than queue size
            self.monitor.event_queue.put({
                "type": "test_event",
                "value": i
            })
            
        # Queue should not exceed max size
        self.assertLessEqual(self.monitor.event_queue.qsize(), 20)
        
    def test_callback_error_handling(self):
        """Test error handling in callbacks"""
        def bad_callback(event):
            raise Exception("Callback error")
            
        # Register bad callback
        self.monitor.add_event_callback("state_change", bad_callback)
        
        # Trigger state change
        self.monitor._update_state({"ra": 12.0})
        
        # Monitor should continue running despite callback error
        self.assertTrue(self.monitor.running)
        
    def test_remove_callback(self):
        """Test callback removal"""
        callback_called = False
        
        def test_callback(event):
            nonlocal callback_called
            callback_called = True
            
        # Register and then remove callback
        self.monitor.add_event_callback("state_change", test_callback)
        self.monitor.remove_event_callback("state_change", test_callback)
        
        # Trigger state change
        self.monitor._update_state({"ra": 12.0})
        
        # Callback should not be called
        self.assertFalse(callback_called)

if __name__ == '__main__':
    unittest.main()
