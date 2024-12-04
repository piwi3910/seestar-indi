#!/usr/bin/env python3

"""
Unit tests for Seestar monitoring system
"""

import unittest
import time
import threading
from unittest.mock import Mock, patch
from datetime import datetime

from seestar_monitoring import (
    HealthChecker,
    HealthStatus,
    PerformanceProfiler,
    MonitoringSystem,
    METRICS
)

class TestHealthChecker(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.mock_monitor = Mock()
        self.mock_optimizer = Mock()
        
        self.health_checker = HealthChecker(
            self.mock_api,
            self.mock_monitor,
            self.mock_optimizer
        )
        
    def test_api_health_check(self):
        """Test API health checking"""
        # Test healthy API
        self.mock_api.send_command.return_value = {"status": "ok"}
        status = self.health_checker._check_api_health()
        self.assertEqual(status.status, "healthy")
        
        # Test degraded API (high latency)
        def slow_response(*args):
            time.sleep(1.1)
            return {"status": "ok"}
        self.mock_api.send_command.side_effect = slow_response
        status = self.health_checker._check_api_health()
        self.assertEqual(status.status, "degraded")
        
        # Test unhealthy API
        self.mock_api.send_command.side_effect = Exception("Connection failed")
        status = self.health_checker._check_api_health()
        self.assertEqual(status.status, "unhealthy")
        
    def test_device_health_check(self):
        """Test device health checking"""
        # Setup mock state
        mock_state = Mock()
        self.mock_monitor.get_state.return_value = mock_state
        
        # Test healthy device
        mock_state.connected = True
        mock_state.error = None
        mock_state.focus_temperature = 20.0
        status = self.health_checker._check_device_health()
        self.assertEqual(status.status, "healthy")
        
        # Test degraded device
        mock_state.error = "Minor issue"
        status = self.health_checker._check_device_health()
        self.assertEqual(status.status, "degraded")
        
        # Test unhealthy device
        mock_state.connected = False
        status = self.health_checker._check_device_health()
        self.assertEqual(status.status, "unhealthy")
        
    def test_performance_health_check(self):
        """Test performance health checking"""
        # Setup mock stats
        self.mock_optimizer.get_performance_stats.return_value = {
            "cache_stats": {
                "hit_rate": 0.8,
                "hits": 80,
                "misses": 20
            },
            "batch_queue_size": 5
        }
        
        # Test healthy performance
        status = self.health_checker._check_performance_health()
        self.assertEqual(status.status, "healthy")
        
        # Test degraded performance
        self.mock_optimizer.get_performance_stats.return_value = {
            "cache_stats": {
                "hit_rate": 0.3,
                "hits": 30,
                "misses": 70
            },
            "batch_queue_size": 5
        }
        status = self.health_checker._check_performance_health()
        self.assertEqual(status.status, "degraded")
        
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    def test_system_health_check(self, mock_disk, mock_memory, mock_cpu):
        """Test system health checking"""
        # Setup mock system stats
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0)
        mock_disk.return_value = Mock(percent=70.0)
        
        # Test healthy system
        status = self.health_checker._check_system_health()
        self.assertEqual(status.status, "healthy")
        
        # Test degraded system
        mock_cpu.return_value = 95.0
        mock_memory.return_value = Mock(percent=95.0)
        mock_disk.return_value = Mock(percent=95.0)
        
        status = self.health_checker._check_system_health()
        self.assertEqual(status.status, "degraded")

class TestPerformanceProfiler(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.profiler = PerformanceProfiler()
        
    def test_profiling_session(self):
        """Test profiling session"""
        # Start profiling
        self.profiler.start_profiling("test_profile")
        self.assertTrue(self.profiler.active)
        
        # Do some work
        for i in range(1000):
            _ = i ** 2
            
        # Stop profiling
        self.profiler.stop_profiling("test_profile")
        self.assertFalse(self.profiler.active)
        
        # Get profile results
        results = self.profiler.get_profile("test_profile")
        self.assertIsNotNone(results)
        self.assertIn("test_profile", self.profiler.profiles)
        
    def test_multiple_profiles(self):
        """Test multiple profiling sessions"""
        # Create two profiles
        for name in ["profile1", "profile2"]:
            self.profiler.start_profiling(name)
            for i in range(100):
                _ = i ** 2
            self.profiler.stop_profiling(name)
            
        # Verify both profiles exist
        self.assertEqual(len(self.profiler.profiles), 2)
        self.assertIsNotNone(self.profiler.get_profile("profile1"))
        self.assertIsNotNone(self.profiler.get_profile("profile2"))

class TestMonitoringSystem(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.mock_monitor = Mock()
        self.mock_optimizer = Mock()
        
        self.monitoring = MonitoringSystem(
            self.mock_api,
            self.mock_monitor,
            self.mock_optimizer
        )
        
    @patch('prometheus_client.start_http_server')
    def test_monitoring_startup(self, mock_start_server):
        """Test monitoring system startup"""
        self.monitoring.start(metrics_port=9090)
        mock_start_server.assert_called_once_with(9090)
        self.assertTrue(self.monitoring.running)
        
        self.monitoring.stop()
        self.assertFalse(self.monitoring.running)
        
    def test_metric_updates(self):
        """Test metric updates"""
        # Setup mock state
        mock_state = Mock()
        mock_state.focus_temperature = 20.0
        mock_state.focus_position = 1000
        mock_state.filter_position = 1
        self.mock_monitor.get_state.return_value = mock_state
        
        # Setup mock performance stats
        self.mock_optimizer.get_performance_stats.return_value = {
            "cache_stats": {
                "hits": 80,
                "misses": 20
            },
            "current_batch_size": 5
        }
        
        # Update metrics
        self.monitoring._update_metrics()
        
        # Verify metric values
        self.assertEqual(
            METRICS['device_temperature_celsius']._value.get(),
            20.0
        )
        self.assertEqual(
            METRICS['device_focus_position']._value.get(),
            1000
        )
        self.assertEqual(
            METRICS['device_filter_position']._value.get(),
            1
        )
        
    def test_health_reporting(self):
        """Test health reporting"""
        # Get health report
        report = self.monitoring.get_health_report()
        
        # Verify report structure
        self.assertIn('timestamp', report)
        self.assertIn('overall_status', report)
        self.assertIn('components', report)
        self.assertIn('metrics', report)
        
        # Verify components
        components = report['components']
        self.assertIn('api', components)
        self.assertIn('device', components)
        self.assertIn('performance', components)
        self.assertIn('system', components)
        
    def test_profiling_integration(self):
        """Test profiling integration"""
        # Start profile
        self.monitoring.start_profile("test")
        
        # Do some work
        for i in range(1000):
            _ = i ** 2
            
        # Stop and get results
        results = self.monitoring.stop_profile("test")
        self.assertIsNotNone(results)
        self.assertIn("test", self.monitoring.profiler.profiles)

if __name__ == '__main__':
    unittest.main()
