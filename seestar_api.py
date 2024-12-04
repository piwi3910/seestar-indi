#!/usr/bin/env python3

"""
Shared API client for Seestar telescope communication
Handles HTTP requests, retries, and error handling
"""

import requests
import time
import json
import logging
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class SeestarAPI:
    def __init__(self, host: str = "localhost", port: int = 5555, device_num: int = 1):
        self.logger = logging.getLogger("SeestarAPI")
        self.base_url = f"http://{host}:{port}/api/v1/telescope/{device_num}/action"
        
        # Default headers
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        # Configure session with retries
        self.session = requests.Session()
        retries = Retry(
            total=3,  # Number of retries
            backoff_factor=0.5,  # Wait 0.5, 1, 2 seconds between retries
            status_forcelist=[500, 502, 503, 504]  # HTTP status codes to retry on
        )
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        
        # Response cache
        self._cache: Dict[str, Any] = {}
        self._cache_timeout = 0.5  # seconds
        self._last_cache_time: Dict[str, float] = {}
        
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached value is still valid"""
        if cache_key not in self._last_cache_time:
            return False
        return time.time() - self._last_cache_time[cache_key] < self._cache_timeout
        
    def _update_cache(self, cache_key: str, value: Any):
        """Update cache with new value"""
        self._cache[cache_key] = value
        self._last_cache_time[cache_key] = time.time()
        
    def send_command(self, 
                     action: str, 
                     parameters: Dict[str, Any], 
                     use_cache: bool = False,
                     timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Send command to telescope with proper error handling and caching
        
        Args:
            action: API action to perform
            parameters: Command parameters
            use_cache: Whether to use cached response if available
            timeout: Request timeout in seconds
            
        Returns:
            API response as dictionary or None if request failed
        """
        cache_key = f"{action}:{json.dumps(parameters, sort_keys=True)}"
        
        # Check cache if enabled
        if use_cache and self._is_cache_valid(cache_key):
            self.logger.debug(f"Using cached response for {action}")
            return self._cache[cache_key]
            
        # Prepare request payload
        payload = {
            "Action": action,
            "Parameters": json.dumps(parameters),
            "ClientID": "1",
            "ClientTransactionID": str(int(time.time()))
        }
        
        try:
            # Send request with timeout
            response = self.session.put(
                self.base_url,
                data=payload,
                headers=self.headers,
                timeout=timeout
            )
            
            # Raise error for bad status codes
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            
            # Update cache
            if use_cache:
                self._update_cache(cache_key, result)
                
            return result
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Request timed out for action {action}")
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed for action {action}: {str(e)}")
            return None
            
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse response for action {action}")
            return None
            
    def get_coordinates(self) -> Optional[Dict[str, float]]:
        """Get current telescope coordinates"""
        response = self.send_command(
            "method_sync",
            {"method": "scope_get_equ_coord"},
            use_cache=True  # Cache coordinates briefly
        )
        
        if response and 'Value' in response:
            return response['Value']['result']
        return None
        
    def goto_target(self, ra: str, dec: str, target_name: str = "Target") -> bool:
        """
        Slew telescope to target coordinates
        
        Args:
            ra: Right ascension in HH:MM:SS format
            dec: Declination in DD:MM:SS format
            target_name: Name for the target
            
        Returns:
            True if command was sent successfully
        """
        response = self.send_command(
            "goto_target",
            {
                "target_name": target_name,
                "ra": ra,
                "dec": dec,
                "is_j2000": False
            }
        )
        return response is not None
        
    def sync_position(self, ra: float, dec: float) -> bool:
        """
        Sync telescope position
        
        Args:
            ra: Right ascension in hours
            dec: Declination in degrees
            
        Returns:
            True if sync was successful
        """
        response = self.send_command(
            "method_sync",
            {
                "method": "scope_sync",
                "params": [ra, dec]
            }
        )
        return response is not None
        
    def stop_slew(self) -> bool:
        """Stop current slew operation"""
        response = self.send_command(
            "method_sync",
            {
                "method": "iscope_stop_view",
                "params": {"stage": "AutoGoto"}
            }
        )
        return response is not None
        
    def is_slewing(self) -> bool:
        """Check if telescope is currently slewing"""
        response = self.send_command(
            "method_sync",
            {"method": "get_view_state"},
            use_cache=True
        )
        
        if response and 'Value' in response:
            return response['Value']['result']['View']['stage'] == 'AutoGoto'
        return False
        
    def get_temperature(self) -> Optional[float]:
        """Get current temperature"""
        response = self.send_command(
            "method_sync",
            {"method": "get_device_state"},
            use_cache=True
        )
        
        if response and 'Value' in response:
            return response['Value']['result'].get('temperature')
        return None
        
    def start_exposure(self, duration: float, gain: int = 1) -> bool:
        """Start camera exposure"""
        response = self.send_command(
            "method_sync",
            {
                "method": "start_exposure",
                "params": {
                    "exposure_ms": int(duration * 1000),
                    "gain": gain
                }
            }
        )
        return response is not None
        
    def abort_exposure(self) -> bool:
        """Abort current exposure"""
        response = self.send_command(
            "method_sync",
            {"method": "stop_exposure"}
        )
        return response is not None
        
    def start_autofocus(self) -> bool:
        """Start auto focus sequence"""
        response = self.send_command(
            "method_sync",
            {"method": "start_auto_focuse"}  # Note: API spelling
        )
        return response is not None
        
    def move_filter(self, position: int) -> bool:
        """Move filter wheel to position"""
        response = self.send_command(
            "method_sync",
            {
                "method": "set_setting",
                "params": {"stack_lenhance": bool(position)}  # Maps filter position to LP filter
            }
        )
        return response is not None
