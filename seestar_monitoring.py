#!/usr/bin/env python3

"""
Monitoring system for Seestar INDI driver
Handles metrics, health checks, and performance profiling
"""

import time
import psutil
import cProfile
import pstats
import io
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from prometheus_client import (
    Counter, Gauge, Histogram,
    start_http_server as start_metrics_server
)

from seestar_logging import get_logger
from seestar_config import config_manager

logger = get_logger("SeestarMonitoring")

# Metrics definitions
METRICS = {
    # API metrics
    'api_requests_total': Counter(
        'seestar_api_requests_total',
        'Total number of API requests',
        ['method']
    ),
    'api_request_duration_seconds': Histogram(
        'seestar_api_request_duration_seconds',
        'API request duration in seconds',
        ['method']
    ),
    'api_errors_total': Counter(
        'seestar_api_errors_total',
        'Total number of API errors',
        ['method', 'error_type']
    ),
    
    # Device metrics
    'device_temperature_celsius': Gauge(
        'seestar_device_temperature_celsius',
        'Device temperature in Celsius'
    ),
    'device_focus_position': Gauge(
        'seestar_device_focus_position',
        'Current focus position'
    ),
    'device_filter_position': Gauge(
        'seestar_device_filter_position',
        'Current filter position'
    ),
    
    # Performance metrics
    'cache_hits_total': Counter(
        'seestar_cache_hits_total',
        'Total number of cache hits'
    ),
    'cache_misses_total': Counter(
        'seestar_cache_misses_total',
        'Total number of cache misses'
    ),
    'batch_size': Histogram(
        'seestar_batch_size',
        'Request batch sizes'
    ),
    
    # System metrics
    'cpu_usage_percent': Gauge(
        'seestar_cpu_usage_percent',
        'CPU usage percentage'
    ),
    'memory_usage_bytes': Gauge(
        'seestar_memory_usage_bytes',
        'Memory usage in bytes'
    ),
    'disk_usage_percent': Gauge(
        'seestar_disk_usage_percent',
        'Disk usage percentage'
    )
}

@dataclass
class HealthStatus:
    """Health check status"""
    component: str
    status: str  # "healthy", "degraded", "unhealthy"
    details: Dict[str, Any]
    timestamp: datetime

class HealthChecker:
    """System health checker"""
    def __init__(self, api, monitor, performance_optimizer):
        self.api = api
        self.monitor = monitor
        self.optimizer = performance_optimizer
        self.health_history: List[HealthStatus] = []
        self.max_history = 100
        
    def check_health(self) -> Dict[str, HealthStatus]:
        """Perform health checks on all components"""
        checks = {
            "api": self._check_api_health(),
            "device": self._check_device_health(),
            "performance": self._check_performance_health(),
            "system": self._check_system_health()
        }
        
        # Update history
        for status in checks.values():
            self.health_history.append(status)
            if len(self.health_history) > self.max_history:
                self.health_history.pop(0)
                
        return checks
        
    def _check_api_health(self) -> HealthStatus:
        """Check API health"""
        try:
            # Test API connection
            start = time.time()
            result = self.api.send_command("test_connection", {})
            response_time = time.time() - start
            
            status = "healthy"
            details = {
                "connected": True,
                "response_time": response_time
            }
            
            if response_time > 1.0:
                status = "degraded"
                details["warning"] = "High latency"
                
        except Exception as e:
            status = "unhealthy"
            details = {
                "connected": False,
                "error": str(e)
            }
            
        return HealthStatus("api", status, details, datetime.now())
        
    def _check_device_health(self) -> HealthStatus:
        """Check device health"""
        state = self.monitor.get_state()
        
        status = "healthy"
        details = {
            "connected": state.connected,
            "temperature": state.focus_temperature,
            "error": state.error
        }
        
        if not state.connected:
            status = "unhealthy"
        elif state.error:
            status = "degraded"
            
        return HealthStatus("device", status, details, datetime.now())
        
    def _check_performance_health(self) -> HealthStatus:
        """Check performance health"""
        stats = self.optimizer.get_performance_stats()
        cache_stats = stats["cache_stats"]
        
        status = "healthy"
        details = {
            "cache_hit_rate": cache_stats["hit_rate"],
            "batch_queue_size": stats["batch_queue_size"]
        }
        
        if cache_stats["hit_rate"] < 0.5:
            status = "degraded"
            details["warning"] = "Low cache hit rate"
            
        return HealthStatus("performance", status, details, datetime.now())
        
    def _check_system_health(self) -> HealthStatus:
        """Check system health"""
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        status = "healthy"
        details = {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent
        }
        
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
            status = "degraded"
            details["warning"] = "High resource usage"
            
        return HealthStatus("system", status, details, datetime.now())

class PerformanceProfiler:
    """System performance profiler"""
    def __init__(self):
        self.profiler = cProfile.Profile()
        self.active = False
        self.profiles: Dict[str, pstats.Stats] = {}
        
    def start_profiling(self, name: str):
        """Start profiling session"""
        if self.active:
            return
            
        self.active = True
        self.profiler.enable()
        
    def stop_profiling(self, name: str):
        """Stop profiling session and save results"""
        if not self.active:
            return
            
        self.profiler.disable()
        self.active = False
        
        # Save profile
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
        ps.print_stats()
        self.profiles[name] = ps
        
        # Clear profiler
        self.profiler = cProfile.Profile()
        
    def get_profile(self, name: str) -> Optional[str]:
        """Get profile results"""
        if name not in self.profiles:
            return None
            
        s = io.StringIO()
        self.profiles[name].stream = s
        self.profiles[name].print_stats()
        return s.getvalue()

class MonitoringSystem:
    """Main monitoring system"""
    def __init__(self, api, device_monitor, performance_optimizer):
        self.api = api
        self.device_monitor = device_monitor
        self.optimizer = performance_optimizer
        
        # Initialize components
        self.health_checker = HealthChecker(
            api,
            device_monitor,
            performance_optimizer
        )
        self.profiler = PerformanceProfiler()
        
        # Monitoring state
        self.running = False
        self._lock = threading.Lock()
        
    def start(self, metrics_port: int = 9090):
        """Start monitoring system"""
        self.running = True
        
        # Start metrics server
        start_metrics_server(metrics_port)
        
        # Start monitoring thread
        threading.Thread(
            target=self._monitor_loop,
            name="MonitoringSystem",
            daemon=True
        ).start()
        
        logger.info(f"Monitoring system started (metrics on port {metrics_port})")
        
    def stop(self):
        """Stop monitoring system"""
        self.running = False
        
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Update metrics
                self._update_metrics()
                
                # Perform health checks
                health = self.health_checker.check_health()
                
                # Log issues
                self._log_health_issues(health)
                
                # Wait before next update
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(5)
                
    def _update_metrics(self):
        """Update all metrics"""
        try:
            # Update device metrics
            state = self.device_monitor.get_state()
            METRICS['device_temperature_celsius'].set(state.focus_temperature)
            METRICS['device_focus_position'].set(state.focus_position)
            METRICS['device_filter_position'].set(state.filter_position)
            
            # Update performance metrics
            stats = self.optimizer.get_performance_stats()
            cache_stats = stats["cache_stats"]
            METRICS['cache_hits_total'].inc(cache_stats["hits"])
            METRICS['cache_misses_total'].inc(cache_stats["misses"])
            METRICS['batch_size'].observe(stats["current_batch_size"])
            
            # Update system metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            METRICS['cpu_usage_percent'].set(cpu_percent)
            METRICS['memory_usage_bytes'].set(memory.used)
            METRICS['disk_usage_percent'].set(disk.percent)
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            
    def _log_health_issues(self, health: Dict[str, HealthStatus]):
        """Log health check issues"""
        for component, status in health.items():
            if status.status != "healthy":
                logger.warning(
                    f"Health issue in {component}: {status.status}"
                    f" - {status.details}"
                )
                
    def start_profile(self, name: str):
        """Start performance profiling"""
        self.profiler.start_profiling(name)
        
    def stop_profile(self, name: str) -> Optional[str]:
        """Stop profiling and get results"""
        self.profiler.stop_profiling(name)
        return self.profiler.get_profile(name)
        
    def get_health_report(self) -> Dict[str, Any]:
        """Get complete health report"""
        health = self.health_checker.check_health()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": min(s.status for s in health.values()),
            "components": {
                name: {
                    "status": status.status,
                    "details": status.details
                }
                for name, status in health.items()
            },
            "metrics": {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent
            }
        }
