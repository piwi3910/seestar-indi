#!/usr/bin/env python3

"""
Status monitoring system for Seestar telescope
Handles device state tracking and event notifications
"""

import threading
import time
import logging
from typing import Dict, Any, Optional, Callable
from queue import Queue
from dataclasses import dataclass
from seestar_api import SeestarAPI

@dataclass
class DeviceState:
    """Current state of a device"""
    connected: bool = False
    error: Optional[str] = None
    last_update: float = 0.0
    
    # Mount state
    ra: float = 0.0
    dec: float = 0.0
    slewing: bool = False
    tracking: bool = True
    
    # Camera state
    exposing: bool = False
    exposure_time: float = 0.0
    exposure_start: float = 0.0
    gain: int = 1
    
    # Filter wheel state
    filter_position: int = 0
    filter_moving: bool = False
    
    # Focuser state
    focus_position: int = 0
    focus_moving: bool = False
    focus_temperature: float = 20.0
    auto_focusing: bool = False

class DeviceMonitor:
    def __init__(self, api: SeestarAPI):
        self.logger = logging.getLogger("SeestarMonitor")
        self.api = api
        
        # Device state
        self.state = DeviceState()
        self.state_lock = threading.Lock()
        
        # Event handling
        self.event_queue: Queue = Queue()
        self.event_callbacks: Dict[str, list[Callable]] = {}
        
        # Monitoring threads
        self.monitor_thread: Optional[threading.Thread] = None
        self.event_thread: Optional[threading.Thread] = None
        self.running = False
        
    def start(self):
        """Start monitoring threads"""
        if self.running:
            return
            
        self.running = True
        
        # Start monitor thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="SeestarMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        # Start event thread
        self.event_thread = threading.Thread(
            target=self._event_loop,
            name="SeestarEvents",
            daemon=True
        )
        self.event_thread.start()
        
    def stop(self):
        """Stop monitoring threads"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join()
        if self.event_thread:
            self.event_thread.join()
            
    def add_event_callback(self, event_type: str, callback: Callable):
        """Add callback for specific event type"""
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)
        
    def remove_event_callback(self, event_type: str, callback: Callable):
        """Remove callback for specific event type"""
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].remove(callback)
            
    def _update_state(self, updates: Dict[str, Any]):
        """Update device state with new values"""
        with self.state_lock:
            for key, value in updates.items():
                if hasattr(self.state, key):
                    old_value = getattr(self.state, key)
                    if old_value != value:
                        setattr(self.state, key, value)
                        # Queue state change event
                        self.event_queue.put({
                            "type": "state_change",
                            "property": key,
                            "old_value": old_value,
                            "new_value": value
                        })
                        
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Update mount status
                coords = self.api.get_coordinates()
                if coords:
                    self._update_state({
                        "ra": coords.get("ra", 0.0),
                        "dec": coords.get("dec", 0.0),
                        "connected": True,
                        "error": None
                    })
                    
                # Check if slewing
                slewing = self.api.is_slewing()
                self._update_state({"slewing": slewing})
                
                # Update temperature
                temp = self.api.get_temperature()
                if temp is not None:
                    self._update_state({"focus_temperature": temp})
                    
                # Update exposure status if exposing
                if self.state.exposing:
                    elapsed = time.time() - self.state.exposure_start
                    if elapsed >= self.state.exposure_time:
                        self._update_state({"exposing": False})
                        self.event_queue.put({
                            "type": "exposure_complete"
                        })
                        
                # Brief delay between updates
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Monitor error: {str(e)}")
                self._update_state({
                    "connected": False,
                    "error": str(e)
                })
                time.sleep(5)  # Longer delay after error
                
    def _event_loop(self):
        """Event processing loop"""
        while self.running:
            try:
                # Get next event
                event = self.event_queue.get(timeout=1.0)
                
                # Call registered callbacks
                event_type = event["type"]
                if event_type in self.event_callbacks:
                    for callback in self.event_callbacks[event_type]:
                        try:
                            callback(event)
                        except Exception as e:
                            self.logger.error(f"Event callback error: {str(e)}")
                            
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    self.logger.error(f"Event processing error: {str(e)}")
                    
    def get_state(self) -> DeviceState:
        """Get current device state"""
        with self.state_lock:
            return self.state
            
    def start_exposure(self, duration: float, gain: int = 1) -> bool:
        """Start camera exposure"""
        if self.api.start_exposure(duration, gain):
            self._update_state({
                "exposing": True,
                "exposure_time": duration,
                "exposure_start": time.time(),
                "gain": gain
            })
            return True
        return False
        
    def abort_exposure(self) -> bool:
        """Abort current exposure"""
        if self.api.abort_exposure():
            self._update_state({
                "exposing": False
            })
            return True
        return False
        
    def start_autofocus(self) -> bool:
        """Start auto focus sequence"""
        if self.api.start_autofocus():
            self._update_state({
                "auto_focusing": True
            })
            return True
        return False
        
    def move_filter(self, position: int) -> bool:
        """Move filter wheel to position"""
        if self.api.move_filter(position):
            self._update_state({
                "filter_position": position,
                "filter_moving": True
            })
            return True
        return False
