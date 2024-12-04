#!/usr/bin/env python3

"""
Unit tests for Seestar error recovery system
"""

import unittest
import time
import queue
import threading
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from seestar_recovery import (
    Command,
    TransactionLog,
    CommandQueue,
    ConnectionManager,
    Watchdog
)

class TestCommand(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.command = Command(
            method="test_method",
            params={"param1": "value1"},
            timestamp=time.time()
        )
        
    def test_command_creation(self):
        """Test command creation"""
        self.assertEqual(self.command.method, "test_method")
        self.assertEqual(self.command.params["param1"], "value1")
        self.assertEqual(self.command.retries, 0)
        self.assertEqual(self.command.max_retries, 3)
        
    def test_command_timeout(self):
        """Test command timeout"""
        old_command = Command(
            method="old_method",
            params={},
            timestamp=time.time() - 20,
            timeout=10
        )
        self.assertTrue(time.time() - old_command.timestamp > old_command.timeout)

class TestTransactionLog(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.log = TransactionLog()
        self.mock_api = Mock()
        
    def test_transaction_logging(self):
        """Test transaction logging"""
        command = Command("test_method", {}, time.time())
        result = {"status": "success"}
        
        self.log.add(command, result)
        self.assertEqual(len(self.log.commands), 1)
        self.assertEqual(len(self.log.results), 1)
        
    def test_rollback_goto(self):
        """Test rollback of goto command"""
        command = Command(
            "goto_target",
            {"ra": 10.0, "dec": 45.0},
            time.time()
        )
        result = {"previous_ra": 5.0, "previous_dec": 30.0}
        
        self.log.add(command, result)
        self.log.rollback(self.mock_api)
        
        # Verify rollback command
        self.mock_api.send_command.assert_called_once()
        args = self.mock_api.send_command.call_args[0]
        self.assertEqual(args[0], "goto_target")
        self.assertEqual(args[1]["ra"], 5.0)
        self.assertEqual(args[1]["dec"], 30.0)
        
    def test_clear_log(self):
        """Test log clearing"""
        command = Command("test_method", {}, time.time())
        result = {"status": "success"}
        
        self.log.add(command, result)
        self.log.clear()
        
        self.assertEqual(len(self.log.commands), 0)
        self.assertEqual(len(self.log.results), 0)

class TestCommandQueue(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.queue = CommandQueue(self.mock_api)
        
    def test_command_addition(self):
        """Test adding commands to queue"""
        command = Command("test_method", {}, time.time())
        self.queue.add_command(command, priority=1)
        
        self.assertEqual(self.queue.queue.qsize(), 1)
        priority, queued_command = self.queue.queue.get()
        self.assertEqual(priority, 1)
        self.assertEqual(queued_command.method, command.method)
        
    def test_command_processing(self):
        """Test command processing"""
        # Setup success callback
        callback_called = threading.Event()
        def success_callback(result):
            callback_called.set()
            
        # Create command
        command = Command(
            "test_method",
            {},
            time.time(),
            callback=success_callback
        )
        
        # Setup API response
        self.mock_api.send_command.return_value = {"status": "success"}
        
        # Start queue and add command
        self.queue.start()
        self.queue.add_command(command)
        
        # Wait for callback
        callback_called.wait(timeout=1.0)
        self.assertTrue(callback_called.is_set())
        
        # Stop queue
        self.queue.stop()
        
    def test_command_retry(self):
        """Test command retry on failure"""
        command = Command(
            "test_method",
            {},
            time.time(),
            max_retries=2
        )
        
        # Setup API to fail then succeed
        self.mock_api.send_command.side_effect = [None, None, {"status": "success"}]
        
        # Start queue and add command
        self.queue.start()
        self.queue.add_command(command)
        
        # Wait for retries
        time.sleep(1)
        
        # Verify retry count
        self.assertEqual(self.mock_api.send_command.call_count, 3)
        
        # Stop queue
        self.queue.stop()

class TestConnectionManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.manager = ConnectionManager(self.mock_api)
        
    def test_connection_attempt(self):
        """Test connection attempt"""
        # Setup API response
        self.mock_api.send_command.return_value = {"status": "connected"}
        
        # Attempt connection
        self.manager._attempt_connection()
        
        # Verify connection attempt
        self.mock_api.send_command.assert_called_with("connect", {})
        self.assertTrue(self.manager.connected)
        self.assertEqual(self.manager.connection_attempts, 0)
        
    def test_connection_failure(self):
        """Test connection failure handling"""
        # Setup API to fail
        self.mock_api.send_command.return_value = None
        
        # Attempt connections
        for _ in range(3):
            self.manager._attempt_connection()
            time.sleep(self.manager.min_backoff)
            
        # Verify backoff
        self.assertEqual(self.manager.connection_attempts, 3)
        self.assertFalse(self.manager.connected)
        
    def test_connection_recovery(self):
        """Test connection recovery"""
        # Setup API responses
        self.mock_api.send_command.side_effect = [
            None,  # First attempt fails
            None,  # Second attempt fails
            {"status": "connected"}  # Third attempt succeeds
        ]
        
        # Start connection management
        self.manager.start()
        
        # Wait for recovery
        time.sleep(5)
        
        # Verify recovery
        self.assertTrue(self.manager.connected)
        self.assertEqual(self.manager.connection_attempts, 0)

class TestWatchdog(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.mock_monitor = Mock()
        self.watchdog = Watchdog(self.mock_api, self.mock_monitor)
        
    def test_state_monitoring(self):
        """Test state monitoring"""
        # Start watchdog
        self.watchdog.start()
        
        # Simulate state change
        self.watchdog._handle_state_change({"type": "test_change"})
        initial_time = self.watchdog.last_state_change
        
        # Verify state update
        self.assertGreater(initial_time, time.time() - 1)
        
        # Stop watchdog
        self.watchdog.stop()
        
    def test_recovery_attempt(self):
        """Test recovery attempt"""
        self.watchdog._attempt_recovery()
        
        # Verify recovery commands
        expected_calls = [
            ("stop_slew", {}),
            ("stop_exposure", {}),
            ("disconnect", {}),
            ("connect", {})
        ]
        
        for (method, params) in expected_calls:
            self.mock_api.send_command.assert_any_call(method, params)
            
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_resource_monitoring(self, mock_disk, mock_memory, mock_cpu):
        """Test resource monitoring"""
        # Setup mocks
        mock_cpu.return_value = 95
        mock_memory.return_value = Mock(percent=95)
        mock_disk.return_value = Mock(percent=95, free=5*1024**3)
        
        # Check resources
        self.watchdog._check_resources()
        
        # Verify all checks were made
        mock_cpu.assert_called_once()
        mock_memory.assert_called_once()
        mock_disk.assert_called_once()

if __name__ == '__main__':
    unittest.main()
