#!/usr/bin/env python3

"""
Performance optimization system for Seestar INDI driver
Handles connection pooling, request batching, and caching
"""

import time
import gzip
import json
import queue
import threading
import requests
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib3 import PoolManager, HTTPConnectionPool
from cachetools import TTLCache, LRUCache

from seestar_logging import get_logger
from seestar_config import config_manager

logger = get_logger("SeestarPerformance")

@dataclass
class BatchRequest:
    """Batch request container"""
    method: str
    params: Dict[str, Any]
    callback: Optional[callable] = None
    timestamp: float = time.time()

class ConnectionPool:
    """Connection pool for API requests"""
    def __init__(self, host: str, port: int, max_size: int = 10):
        self.host = host
        self.port = port
        self.pool = PoolManager(
            maxsize=max_size,
            retries=False,  # We handle retries separately
            timeout=5.0
        )
        self.connection_pool = HTTPConnectionPool(
            host=host,
            port=port,
            maxsize=max_size,
            retries=False
        )
        
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make request using connection pool"""
        return self.pool.request(method, url, **kwargs)
        
    def close(self):
        """Close connection pool"""
        self.pool.clear()
        self.connection_pool.close()

class RequestBatcher:
    """Batches requests for efficient processing"""
    def __init__(self, api, batch_size: int = 10, batch_timeout: float = 0.1):
        self.api = api
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batch_queue: queue.Queue = queue.Queue()
        self.current_batch: List[BatchRequest] = []
        self.last_batch_time = time.time()
        self.running = False
        self._lock = threading.Lock()
        
    def start(self):
        """Start request batching"""
        self.running = True
        threading.Thread(
            target=self._process_batches,
            name="RequestBatcher",
            daemon=True
        ).start()
        
    def stop(self):
        """Stop request batching"""
        self.running = False
        
    def add_request(self, request: BatchRequest):
        """Add request to batch queue"""
        self.batch_queue.put(request)
        
    def _process_batches(self):
        """Process batched requests"""
        while self.running:
            try:
                # Get next request
                request = self.batch_queue.get(timeout=self.batch_timeout)
                
                with self._lock:
                    self.current_batch.append(request)
                    
                    # Check if we should process batch
                    should_process = (
                        len(self.current_batch) >= self.batch_size or
                        time.time() - self.last_batch_time >= self.batch_timeout
                    )
                    
                if should_process:
                    self._send_batch()
                    
            except queue.Empty:
                # Process partial batch on timeout
                with self._lock:
                    if self.current_batch:
                        self._send_batch()
                        
    def _send_batch(self):
        """Send batch of requests"""
        with self._lock:
            if not self.current_batch:
                return
                
            # Prepare batch request
            batch_params = {
                "requests": [
                    {
                        "method": req.method,
                        "params": req.params
                    }
                    for req in self.current_batch
                ]
            }
            
            # Store callbacks
            callbacks = [req.callback for req in self.current_batch]
            
            # Clear current batch
            self.current_batch = []
            self.last_batch_time = time.time()
            
        try:
            # Send batch request
            response = self.api.send_command("batch", batch_params)
            
            # Handle responses
            if response and "results" in response:
                for callback, result in zip(callbacks, response["results"]):
                    if callback:
                        callback(result)
                        
        except Exception as e:
            logger.error(f"Batch request failed: {e}")

class ResponseCompressor:
    """Handles response compression"""
    def __init__(self, compression_threshold: int = 1024):
        self.compression_threshold = compression_threshold
        
    def compress(self, data: bytes) -> Tuple[bytes, bool]:
        """
        Compress data if beneficial
        Returns (compressed_data, is_compressed)
        """
        if len(data) < self.compression_threshold:
            return data, False
            
        try:
            compressed = gzip.compress(data)
            if len(compressed) < len(data):
                return compressed, True
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            
        return data, False
        
    def decompress(self, data: bytes, is_compressed: bool) -> bytes:
        """Decompress data if needed"""
        if not is_compressed:
            return data
            
        try:
            return gzip.decompress(data)
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            return data

class CacheManager:
    """Manages response caching"""
    def __init__(self):
        # Cache for API responses
        self.response_cache = TTLCache(
            maxsize=1000,
            ttl=60  # 1 minute TTL
        )
        
        # Cache for static resources
        self.static_cache = LRUCache(
            maxsize=100  # Maximum 100 items
        )
        
        # Set of cacheable methods
        self.cacheable_methods = {
            "get_coordinates",
            "get_filter_position",
            "get_focus_position",
            "get_temperature"
        }
        
        # Cache statistics
        self.hits = 0
        self.misses = 0
        
    def get_cached_response(self, method: str, params: Dict[str, Any]) -> Optional[Any]:
        """Get cached response if available"""
        if method not in self.cacheable_methods:
            return None
            
        cache_key = self._make_cache_key(method, params)
        
        if cache_key in self.response_cache:
            self.hits += 1
            return self.response_cache[cache_key]
            
        self.misses += 1
        return None
        
    def cache_response(self, method: str, params: Dict[str, Any], response: Any):
        """Cache API response"""
        if method not in self.cacheable_methods:
            return
            
        cache_key = self._make_cache_key(method, params)
        self.response_cache[cache_key] = response
        
    def cache_static(self, key: str, data: Any):
        """Cache static resource"""
        self.static_cache[key] = data
        
    def get_static(self, key: str) -> Optional[Any]:
        """Get cached static resource"""
        return self.static_cache.get(key)
        
    def _make_cache_key(self, method: str, params: Dict[str, Any]) -> str:
        """Create cache key from method and parameters"""
        return f"{method}:{json.dumps(params, sort_keys=True)}"
        
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "response_cache_size": len(self.response_cache),
            "static_cache_size": len(self.static_cache)
        }
        
    def clear(self):
        """Clear all caches"""
        self.response_cache.clear()
        self.static_cache.clear()
        self.hits = 0
        self.misses = 0

class PerformanceOptimizer:
    """Main performance optimization system"""
    def __init__(self, api):
        self.api = api
        
        # Initialize components
        self.connection_pool = ConnectionPool(
            host=config_manager.config.api.host,
            port=config_manager.config.api.port
        )
        
        self.request_batcher = RequestBatcher(api)
        self.compressor = ResponseCompressor()
        self.cache_manager = CacheManager()
        
    def start(self):
        """Start performance optimization"""
        self.request_batcher.start()
        
    def stop(self):
        """Stop performance optimization"""
        self.request_batcher.stop()
        self.connection_pool.close()
        
    def send_request(self, method: str, params: Dict[str, Any],
                    callback: Optional[callable] = None) -> Optional[Any]:
        """Send optimized request"""
        # Check cache first
        cached = self.cache_manager.get_cached_response(method, params)
        if cached is not None:
            if callback:
                callback(cached)
            return cached
            
        # Create batch request
        request = BatchRequest(method, params, callback)
        
        # Add to batch queue
        self.request_batcher.add_request(request)
        
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        return {
            "cache_stats": self.cache_manager.get_stats(),
            "batch_queue_size": self.request_batcher.batch_queue.qsize(),
            "current_batch_size": len(self.request_batcher.current_batch)
        }
