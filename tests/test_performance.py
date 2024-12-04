#!/usr/bin/env python3

"""
Unit tests for Seestar performance optimization system
"""

import unittest
import time
import json
import gzip
import threading
from unittest.mock import Mock, patch
from queue import Queue

from seestar_performance import (
    ConnectionPool,
    RequestBatcher,
    ResponseCompressor,
    CacheManager,
    PerformanceOptimizer,
    BatchRequest
)

class TestConnectionPool(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.pool = ConnectionPool("localhost", 5555)
        
    def tearDown(self):
        """Clean up test environment"""
        self.pool.close()
        
    @patch('urllib3.PoolManager.request')
    def test_request_pooling(self, mock_request):
        """Test connection pooling"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status = 200
        mock_request.return_value = mock_response
        
        # Make multiple requests
        for _ in range(5):
            response = self.pool.request(
                'PUT',
                'http://localhost:5555/api/v1/telescope/1/action'
            )
            self.assertEqual(response.status, 200)
            
        # Verify connection reuse
        self.assertEqual(mock_request.call_count, 5)
        
    def test_pool_limits(self):
        """Test pool size limits"""
        small_pool = ConnectionPool("localhost", 5555, max_size=2)
        
        # Create more connections than pool size
        connections = []
        for _ in range(5):
            conn = small_pool.connection_pool._get_conn()
            connections.append(conn)
            
        # Verify pool size limit
        self.assertEqual(len(small_pool.connection_pool.pool), 2)
        
        # Clean up
        small_pool.close()

class TestRequestBatcher(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.batcher = RequestBatcher(
            self.mock_api,
            batch_size=3,
            batch_timeout=0.1
        )
        
    def test_request_batching(self):
        """Test request batching"""
        # Setup callback tracking
        callback_results = []
        def callback(result):
            callback_results.append(result)
            
        # Create test requests
        requests = [
            BatchRequest("method1", {"param": 1}, callback),
            BatchRequest("method2", {"param": 2}, callback),
            BatchRequest("method3", {"param": 3}, callback)
        ]
        
        # Setup API response
        self.mock_api.send_command.return_value = {
            "results": [
                {"result": 1},
                {"result": 2},
                {"result": 3}
            ]
        }
        
        # Start batcher and add requests
        self.batcher.start()
        for request in requests:
            self.batcher.add_request(request)
            
        # Wait for processing
        time.sleep(0.2)
        
        # Verify batch was sent
        self.mock_api.send_command.assert_called_once()
        self.assertEqual(len(callback_results), 3)
        
        # Stop batcher
        self.batcher.stop()
        
    def test_batch_timeout(self):
        """Test batch timeout processing"""
        # Create single request
        callback_called = threading.Event()
        def callback(result):
            callback_called.set()
            
        request = BatchRequest("test_method", {}, callback)
        
        # Start batcher and add request
        self.batcher.start()
        self.batcher.add_request(request)
        
        # Wait for timeout processing
        callback_called.wait(timeout=0.2)
        self.assertTrue(callback_called.is_set())
        
        # Stop batcher
        self.batcher.stop()

class TestResponseCompressor(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.compressor = ResponseCompressor(compression_threshold=10)
        
    def test_compression_threshold(self):
        """Test compression threshold"""
        # Small data shouldn't be compressed
        small_data = b"small"
        compressed, is_compressed = self.compressor.compress(small_data)
        self.assertEqual(compressed, small_data)
        self.assertFalse(is_compressed)
        
        # Large data should be compressed
        large_data = b"x" * 1000
        compressed, is_compressed = self.compressor.compress(large_data)
        self.assertTrue(is_compressed)
        self.assertLess(len(compressed), len(large_data))
        
    def test_compression_roundtrip(self):
        """Test compression and decompression"""
        original = b"test data" * 100
        compressed, is_compressed = self.compressor.compress(original)
        decompressed = self.compressor.decompress(compressed, is_compressed)
        self.assertEqual(original, decompressed)

class TestCacheManager(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.cache = CacheManager()
        
    def test_response_caching(self):
        """Test response caching"""
        method = "get_coordinates"
        params = {"param": "value"}
        response = {"ra": 10.0, "dec": 45.0}
        
        # Initially not cached
        self.assertIsNone(self.cache.get_cached_response(method, params))
        
        # Cache response
        self.cache.cache_response(method, params, response)
        
        # Verify cached response
        cached = self.cache.get_cached_response(method, params)
        self.assertEqual(cached, response)
        
    def test_cache_stats(self):
        """Test cache statistics"""
        method = "get_coordinates"
        params = {"param": "value"}
        response = {"data": "test"}
        
        # Get non-existent (miss)
        self.cache.get_cached_response(method, params)
        
        # Cache and get (hit)
        self.cache.cache_response(method, params, response)
        self.cache.get_cached_response(method, params)
        
        # Check stats
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 0.5)
        
    def test_static_cache(self):
        """Test static resource caching"""
        key = "test_resource"
        data = {"large": "data"}
        
        # Cache static resource
        self.cache.cache_static(key, data)
        
        # Verify cached data
        cached = self.cache.get_static(key)
        self.assertEqual(cached, data)
        
    def test_cache_clear(self):
        """Test cache clearing"""
        # Add some cached data
        self.cache.cache_response("method", {}, "response")
        self.cache.cache_static("key", "data")
        
        # Clear cache
        self.cache.clear()
        
        # Verify cache is empty
        self.assertEqual(len(self.cache.response_cache), 0)
        self.assertEqual(len(self.cache.static_cache), 0)
        self.assertEqual(self.cache.hits, 0)
        self.assertEqual(self.cache.misses, 0)

class TestPerformanceOptimizer(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.mock_api = Mock()
        self.optimizer = PerformanceOptimizer(self.mock_api)
        
    def test_optimized_request(self):
        """Test optimized request handling"""
        # Setup callback tracking
        callback_called = threading.Event()
        def callback(result):
            callback_called.set()
            
        # Start optimizer
        self.optimizer.start()
        
        # Send request
        self.optimizer.send_request(
            "test_method",
            {"param": "value"},
            callback
        )
        
        # Wait for processing
        callback_called.wait(timeout=0.2)
        self.assertTrue(callback_called.is_set())
        
        # Stop optimizer
        self.optimizer.stop()
        
    def test_performance_stats(self):
        """Test performance statistics"""
        # Get initial stats
        stats = self.optimizer.get_performance_stats()
        
        # Verify stats structure
        self.assertIn("cache_stats", stats)
        self.assertIn("batch_queue_size", stats)
        self.assertIn("current_batch_size", stats)
        
        # Verify cache stats
        cache_stats = stats["cache_stats"]
        self.assertEqual(cache_stats["hits"], 0)
        self.assertEqual(cache_stats["misses"], 0)

if __name__ == '__main__':
    unittest.main()
