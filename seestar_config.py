#!/usr/bin/env python3

"""
Configuration management for Seestar INDI driver
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import tomli
import tomli_w
from dataclasses import dataclass, asdict

@dataclass
class CameraConfig:
    """Camera configuration"""
    image_width: int = 1920
    image_height: int = 1080
    pixel_size: float = 3.75
    bit_depth: int = 12
    min_exposure: float = 0.001
    max_exposure: float = 3600.0
    min_gain: int = 0
    max_gain: int = 100
    
@dataclass
class FocuserConfig:
    """Focuser configuration"""
    max_position: int = 100000
    step_size: float = 1.0
    backlash: int = 0
    temperature_compensation: bool = True
    
@dataclass
class FilterWheelConfig:
    """Filter wheel configuration"""
    filter_names: list[str] = None
    
    def __post_init__(self):
        if self.filter_names is None:
            self.filter_names = ["Clear", "LP"]
            
@dataclass
class APIConfig:
    """API configuration"""
    host: str = "localhost"
    port: int = 5555
    timeout: float = 10.0
    retry_count: int = 3
    retry_delay: float = 0.5
    cache_timeout: float = 0.5
    
@dataclass
class Config:
    """Main configuration"""
    camera: CameraConfig = None
    focuser: FocuserConfig = None
    filterwheel: FilterWheelConfig = None
    api: APIConfig = None
    
    def __post_init__(self):
        if self.camera is None:
            self.camera = CameraConfig()
        if self.focuser is None:
            self.focuser = FocuserConfig()
        if self.filterwheel is None:
            self.filterwheel = FilterWheelConfig()
        if self.api is None:
            self.api = APIConfig()

class ConfigManager:
    """Configuration manager"""
    
    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.environ.get(
                "SEESTAR_CONFIG_DIR",
                str(Path.home() / ".config" / "seestar")
            )
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.toml"
        self.config = self.load_config()
        
    def load_config(self) -> Config:
        """Load configuration from file"""
        # Create default config
        config = Config()
        
        # Load from file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, "rb") as f:
                    data = tomli.load(f)
                    
                # Update camera config
                if "camera" in data:
                    config.camera = CameraConfig(**data["camera"])
                    
                # Update focuser config
                if "focuser" in data:
                    config.focuser = FocuserConfig(**data["focuser"])
                    
                # Update filter wheel config
                if "filterwheel" in data:
                    config.filterwheel = FilterWheelConfig(**data["filterwheel"])
                    
                # Update API config
                if "api" in data:
                    config.api = APIConfig(**data["api"])
                    
            except Exception as e:
                print(f"Error loading config: {e}")
                print("Using default configuration")
                
        return config
        
    def save_config(self):
        """Save configuration to file"""
        # Create config directory if needed
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert config to dictionary
        data = {
            "camera": asdict(self.config.camera),
            "focuser": asdict(self.config.focuser),
            "filterwheel": asdict(self.config.filterwheel),
            "api": asdict(self.config.api)
        }
        
        # Save to file
        try:
            with open(self.config_file, "wb") as f:
                tomli_w.dump(data, f)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    def get_default_config(self) -> str:
        """Get default configuration as TOML string"""
        config = Config()
        data = {
            "camera": asdict(config.camera),
            "focuser": asdict(config.focuser),
            "filterwheel": asdict(config.filterwheel),
            "api": asdict(config.api)
        }
        return tomli_w.dumps(data)
        
    def update_config(self, section: str, updates: Dict[str, Any]):
        """
        Update configuration section
        
        Args:
            section: Configuration section (camera, focuser, filterwheel, api)
            updates: Dictionary of updates
        """
        if not hasattr(self.config, section):
            raise ValueError(f"Invalid config section: {section}")
            
        current = getattr(self.config, section)
        for key, value in updates.items():
            if not hasattr(current, key):
                raise ValueError(f"Invalid config key: {key}")
            setattr(current, key, value)
            
        self.save_config()

# Global configuration instance
config_manager = ConfigManager()
config = config_manager.config
