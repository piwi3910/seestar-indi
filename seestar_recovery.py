#!/usr/bin/env python3

"""
Error recovery system for Seestar INDI driver
Handles reconnection, state recovery, and command retries
"""

import time
import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from seestar_logging import get_logger
from seestar_config import config_manager

logger = get_logger("SeestarRecovery")

@dataclass
class Command:
    """Command to be executed"""
    method: str
    params: Dict[str, Any]
    timestamp: float
    retries: int = 0
    max_retries: int = 3
    timeout: float = 10.0
    callback: Optional[Callable] = None

class TransactionLog:
    """Log of executed commands for rollback"""
    def __init__(self):
        self.commands: List[Command] = []
        self.results: List[Any] = []
        
    def add(self, command: Command, result: Any):
        """Add command and result to log"""
        self.commands.append(command)
        self.results.append(result)
        
    def clear(self):
        """Clear transaction log"""
        self.commands.clear()
        self.results.clear()
        
    def rollback(self, api) -> bool:
        """
        Rollback transaction by executing inverse commands
        Returns True if rollback was successful
        """
        success = True
        for command, result in reversed(list(zip(self.commands, self.results))):
            try:
                inverse = self._get_inverse_command(command, result)
                if inverse:
                    api.send_command(inverse.method, inverse.params)
            except Exception as e:
                logger.error(f"Rollback failed for {command.method}: {e}")
                success = False
        return success
        
    def _get_inverse_command(self, command: Command, result: Any) -> Optional[Command]:
        """Get inverse command for rollback"""
        if command.method == "goto_target":
            # Return to previous position
            return Command(
                method="goto_target",
                params={"ra": result["previous_ra"], "dec": result["previous_dec"]},
                timestamp=time.time()
            )
        elif command.method == "start_exposure":
            # Stop exposure
            return Command(
                method="stop_exposure",
                params={},
                timestamp=time.time()
            )
        elif command.method == "move_filter":
            # Return to previous position
            return Command(
                method="move_filter",
                params={"position": result["previous_position"]},
                timestamp=time.time()
            )
        return None

class CommandQueue:
    """Queue for commands with retry logic"""
    def __init__(self, api):
        self.api = api
        self.queue: queue.PriorityQueue = queue.PriorityQueue()
        self.processing = False
        self.current_transaction = TransactionLog()
        self._lock = threading.Lock()
        
    def start(self):
        """Start command processing"""
        self.processing = True
        threading.Thread(
            target=self._process_commands,
            name="CommandProcessor",
            daemon=True
        ).start()
        
    def stop(self):
        """Stop command processing"""
        self.processing = False
        
    def add_command(self, command: Command, priority: int = 1):
        """Add command to queue with priority (lower is higher priority)"""
        self.queue.put((priority, command))
        
    def _process_commands(self):
        """Process commands from queue"""
        while self.processing:
            try:
                # Get next command
                priority, command = self.queue.get(timeout=1.0)
                
                # Skip expired commands
                if time.time() - command.timestamp > command.timeout:
                    logger.warning(f"Command {command.method} expired")
                    continue
                    
                # Execute command
                try:
                    previous_state = self._get_relevant_state(command)
                    result = self.api.send_command(command.method, command.params)
                    
                    if result:
                        # Add to transaction log
                        result["previous_state"] = previous_state
                        with self._lock:
                            self.current_transaction.add(command, result)
                            
                        # Call callback if provided
                        if command.callback:
                            command.callback(result)
                    else:
                        self._handle_failure(command, priority)
                        
                except Exception as e:
                    logger.error(f"Command execution failed: {e}")
                    self._handle_failure(command, priority)
                    
            except queue.Empty:
                continue
                
    def _handle_failure(self, command: Command, priority: int):
        """Handle command failure"""
        if command.retries < command.max_retries:
            # Requeue command with increased priority
            command.retries += 1
            new_priority = max(0, priority - 1)  # Increase priority
            self.queue.put((new_priority, command))
            logger.info(f"Retrying {command.method} (attempt {command.retries + 1})")
        else:
            logger.error(f"Command {command.method} failed after {command.max_retries} retries")
            # Rollback transaction if needed
            with self._lock:
                if self.current_transaction.commands:
                    if self.current_transaction.rollback(self.api):
                        logger.info("Transaction rolled back successfully")
                    else:
                        logger.error("Transaction rollback failed")
                    self.current_transaction.clear()
                    
    def _get_relevant_state(self, command: Command) -> Dict[str, Any]:
        """Get relevant state for command rollback"""
        if command.method == "goto_target":
            return {
                "previous_ra": self.api.get_coordinates()["ra"],
                "previous_dec": self.api.get_coordinates()["dec"]
            }
        elif command.method == "move_filter":
            return {
                "previous_position": self.api.get_filter_position()
            }
        return {}

class ConnectionManager:
    """Manages device connection with automatic reconnection"""
    def __init__(self, api):
        self.api = api
        self.connected = False
        self.last_connection_attempt = 0
        self.connection_attempts = 0
        self.max_attempts = 5
        self.backoff_factor = 1.5
        self.min_backoff = 1.0
        self.max_backoff = 30.0
        self._lock = threading.Lock()
        
    def start(self):
        """Start connection management"""
        threading.Thread(
            target=self._manage_connection,
            name="ConnectionManager",
            daemon=True
        ).start()
        
    def _manage_connection(self):
        """Monitor and manage connection"""
        while True:
            try:
                if not self.connected:
                    self._attempt_connection()
                else:
                    # Check connection health
                    try:
                        self.api.send_command("test_connection", {})
                    except Exception:
                        logger.warning("Connection check failed")
                        with self._lock:
                            self.connected = False
                            
                # Wait before next check
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Connection management error: {e}")
                time.sleep(5)
                
    def _attempt_connection(self):
        """Attempt to connect with exponential backoff"""
        now = time.time()
        
        # Check if we should attempt connection
        with self._lock:
            if self.connection_attempts >= self.max_attempts:
                # Reset attempts after a long wait
                if now - self.last_connection_attempt > self.max_backoff:
                    self.connection_attempts = 0
                else:
                    return
                    
            # Calculate backoff time
            backoff = min(
                self.max_backoff,
                self.min_backoff * (self.backoff_factor ** self.connection_attempts)
            )
            
            # Check if enough time has passed
            if now - self.last_connection_attempt < backoff:
                return
                
            self.connection_attempts += 1
            self.last_connection_attempt = now
            
        try:
            # Attempt connection
            result = self.api.send_command("connect", {})
            
            with self._lock:
                if result:
                    self.connected = True
                    self.connection_attempts = 0
                    logger.info("Connection established")
                else:
                    logger.warning("Connection attempt failed")
                    
        except Exception as e:
            logger.error(f"Connection attempt failed: {e}")

class Watchdog:
    """System watchdog for monitoring and recovery"""
    def __init__(self, api, monitor):
        self.api = api
        self.monitor = monitor
        self.running = False
        self.last_state_change = time.time()
        self.state_timeout = 60.0  # Maximum time without state change
        
    def start(self):
        """Start watchdog"""
        self.running = True
        threading.Thread(
            target=self._monitor_system,
            name="Watchdog",
            daemon=True
        ).start()
        
        # Register state change callback
        self.monitor.add_event_callback("state_change", self._handle_state_change)
        
    def stop(self):
        """Stop watchdog"""
        self.running = False
        
    def _handle_state_change(self, event):
        """Handle state change event"""
        self.last_state_change = time.time()
        
    def _monitor_system(self):
        """Monitor system health"""
        while self.running:
            try:
                # Check for system freeze
                if time.time() - self.last_state_change > self.state_timeout:
                    logger.warning("System may be frozen, attempting recovery")
                    self._attempt_recovery()
                    
                # Check system resources
                self._check_resources()
                
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
                time.sleep(5)
                
    def _attempt_recovery(self):
        """Attempt system recovery"""
        try:
            # Stop any ongoing operations
            self.api.send_command("stop_slew", {})
            self.api.send_command("stop_exposure", {})
            
            # Reset connection
            self.api.send_command("disconnect", {})
            time.sleep(5)
            self.api.send_command("connect", {})
            
            self.last_state_change = time.time()
            logger.info("Recovery attempt completed")
            
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            
    def _check_resources(self):
        """Check system resources"""
        import psutil
        
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            logger.warning(f"High CPU usage: {cpu_percent}%")
            
        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            logger.warning(f"High memory usage: {memory.percent}%")
            
        # Check disk space
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            logger.warning(f"Low disk space: {disk.free / (1024**3):.1f}GB free")
