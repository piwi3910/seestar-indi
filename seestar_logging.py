#!/usr/bin/env python3

"""
Logging configuration for Seestar INDI driver
"""

import logging
import logging.handlers
import os
from pathlib import Path

def setup_logging(name: str, level: str = "INFO", log_dir: str = None) -> logging.Logger:
    """
    Setup logging configuration
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files, defaults to ./logs
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_dir is None:
        log_dir = Path(__file__).parent / "logs"
    else:
        log_dir = Path(log_dir)
        
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"{name.lower()}.log"
    
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=5
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with standard configuration
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if logger doesn't have handlers
    if not logger.handlers:
        # Get log level from environment or default to INFO
        level = os.environ.get("SEESTAR_LOG_LEVEL", "INFO")
        log_dir = os.environ.get("SEESTAR_LOG_DIR")
        logger = setup_logging(name, level, log_dir)
        
    return logger
