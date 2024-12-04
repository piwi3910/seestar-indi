#!/usr/bin/env python3

"""
Command-line interface for Seestar INDI driver
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

from seestar_api import SeestarAPI
from seestar_config import config_manager, Config
from seestar_logging import get_logger
from seestar_monitor import DeviceMonitor

class SeestarCLI:
    """Command-line interface for Seestar control"""
    
    def __init__(self):
        self.logger = get_logger("SeestarCLI")
        self.api = SeestarAPI(
            host=config_manager.config.api.host,
            port=config_manager.config.api.port
        )
        self.monitor = DeviceMonitor(self.api)
        
    def connect(self) -> bool:
        """Connect to device"""
        try:
            self.monitor.start()
            return True
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from device"""
        self.monitor.stop()
        
    def get_status(self) -> dict:
        """Get device status"""
        state = self.monitor.get_state()
        return {
            "connected": state.connected,
            "ra": state.ra,
            "dec": state.dec,
            "slewing": state.slewing,
            "tracking": state.tracking,
            "exposing": state.exposing,
            "filter_position": state.filter_position,
            "focus_position": state.focus_position,
            "temperature": state.focus_temperature,
            "error": state.error
        }
        
    def goto(self, ra: float, dec: float) -> bool:
        """Slew to coordinates"""
        return self.api.goto_target(str(ra), str(dec))
        
    def sync(self, ra: float, dec: float) -> bool:
        """Sync to coordinates"""
        return self.api.sync_position(ra, dec)
        
    def stop(self) -> bool:
        """Stop all movement"""
        return self.api.stop_slew()
        
    def expose(self, duration: float, gain: Optional[int] = None) -> bool:
        """Start exposure"""
        if gain is None:
            gain = config_manager.config.camera.min_gain
        return self.monitor.start_exposure(duration, gain)
        
    def move_filter(self, position: int) -> bool:
        """Move filter wheel"""
        return self.monitor.move_filter(position)
        
    def focus(self, position: Optional[int] = None, relative: Optional[int] = None) -> bool:
        """Control focuser"""
        if position is not None:
            return self.api.send_command("method_sync", {
                "method": "set_focus_position",
                "params": {"position": position}
            }) is not None
        elif relative is not None:
            current = self.monitor.state.focus_position
            return self.api.send_command("method_sync", {
                "method": "set_focus_position",
                "params": {"position": current + relative}
            }) is not None
        return False
        
    def auto_focus(self) -> bool:
        """Start auto focus"""
        return self.monitor.start_autofocus()

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Seestar INDI Driver CLI")
    
    # Global options
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--log-dir", help="Log directory")
    
    # Commands
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Status command
    subparsers.add_parser("status", help="Get device status")
    
    # Config commands
    config_parser = subparsers.add_parser("config", help="Configuration commands")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    
    # Show config
    config_subparsers.add_parser("show", help="Show current configuration")
    
    # Save default config
    save_default_parser = config_subparsers.add_parser("save-default", help="Save default configuration")
    save_default_parser.add_argument("path", help="Output path")
    
    # Update config
    update_parser = config_subparsers.add_parser("update", help="Update configuration")
    update_parser.add_argument("section", choices=["camera", "focuser", "filterwheel", "api"])
    update_parser.add_argument("key", help="Configuration key")
    update_parser.add_argument("value", help="New value")
    
    # Mount commands
    goto_parser = subparsers.add_parser("goto", help="Slew to coordinates")
    goto_parser.add_argument("ra", type=float, help="Right ascension (hours)")
    goto_parser.add_argument("dec", type=float, help="Declination (degrees)")
    
    sync_parser = subparsers.add_parser("sync", help="Sync coordinates")
    sync_parser.add_argument("ra", type=float, help="Right ascension (hours)")
    sync_parser.add_argument("dec", type=float, help="Declination (degrees)")
    
    subparsers.add_parser("stop", help="Stop all movement")
    
    # Camera commands
    expose_parser = subparsers.add_parser("expose", help="Take exposure")
    expose_parser.add_argument("duration", type=float, help="Exposure duration (seconds)")
    expose_parser.add_argument("--gain", type=int, help="Gain setting")
    
    # Filter wheel commands
    filter_parser = subparsers.add_parser("filter", help="Control filter wheel")
    filter_parser.add_argument("position", type=int, choices=[0, 1], help="Filter position")
    
    # Focuser commands
    focus_parser = subparsers.add_parser("focus", help="Control focuser")
    focus_group = focus_parser.add_mutually_exclusive_group(required=True)
    focus_group.add_argument("--position", type=int, help="Absolute position")
    focus_group.add_argument("--relative", type=int, help="Relative movement")
    focus_group.add_argument("--auto", action="store_true", help="Start auto focus")
    
    args = parser.parse_args()
    
    # Handle configuration file
    if args.config:
        config_manager = ConfigManager(args.config)
        
    # Setup CLI
    cli = SeestarCLI()
    
    # Handle commands
    if args.command == "status":
        if not cli.connect():
            sys.exit(1)
        status = cli.get_status()
        for key, value in status.items():
            print(f"{key}: {value}")
            
    elif args.command == "config":
        if args.config_command == "show":
            print(config_manager.get_default_config())
        elif args.config_command == "save-default":
            with open(args.path, "w") as f:
                f.write(config_manager.get_default_config())
            print(f"Default configuration saved to {args.path}")
        elif args.config_command == "update":
            config_manager.update_config(args.section, {args.key: args.value})
            print(f"Configuration updated: {args.section}.{args.key} = {args.value}")
            
    elif args.command == "goto":
        if not cli.connect():
            sys.exit(1)
        if cli.goto(args.ra, args.dec):
            print("Slew started")
        else:
            print("Slew failed")
            sys.exit(1)
            
    elif args.command == "sync":
        if not cli.connect():
            sys.exit(1)
        if cli.sync(args.ra, args.dec):
            print("Position synced")
        else:
            print("Sync failed")
            sys.exit(1)
            
    elif args.command == "stop":
        if not cli.connect():
            sys.exit(1)
        if cli.stop():
            print("Movement stopped")
        else:
            print("Stop command failed")
            sys.exit(1)
            
    elif args.command == "expose":
        if not cli.connect():
            sys.exit(1)
        if cli.expose(args.duration, args.gain):
            print("Exposure started")
            while cli.monitor.state.exposing:
                time.sleep(0.1)
            print("Exposure complete")
        else:
            print("Exposure failed")
            sys.exit(1)
            
    elif args.command == "filter":
        if not cli.connect():
            sys.exit(1)
        if cli.move_filter(args.position):
            print(f"Filter moved to position {args.position}")
        else:
            print("Filter movement failed")
            sys.exit(1)
            
    elif args.command == "focus":
        if not cli.connect():
            sys.exit(1)
        if args.position is not None:
            if cli.focus(position=args.position):
                print(f"Moving to position {args.position}")
            else:
                print("Focus movement failed")
                sys.exit(1)
        elif args.relative is not None:
            if cli.focus(relative=args.relative):
                print(f"Moving {args.relative} steps")
            else:
                print("Focus movement failed")
                sys.exit(1)
        elif args.auto:
            if cli.auto_focus():
                print("Auto focus started")
                while cli.monitor.state.auto_focusing:
                    time.sleep(0.1)
                print("Auto focus complete")
            else:
                print("Auto focus failed")
                sys.exit(1)
                
    cli.disconnect()

if __name__ == "__main__":
    main()
