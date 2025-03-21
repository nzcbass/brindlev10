import logging
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
import traceback

# Create logs directory if it doesn't exist
LOGS_DIR = Path('logs')
LOGS_DIR.mkdir(exist_ok=True)

# Create a logger
logger = logging.getLogger('cv_generator')
logger.setLevel(logging.INFO)

# Prevent duplicate logs
if not logger.handlers:
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')

    # Create and configure rotating file handler (10MB max size, keep 5 backup files)
    log_file = LOGS_DIR / f'cv_generator_{datetime.now().strftime("%Y%m%d")}.log'
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    # Create and configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def log_error(error_message: str, error: Exception = None):
    """
    Log an error message and optionally the exception details.
    
    Args:
        error_message (str): The main error message to log
        error (Exception, optional): The exception object for additional details
    """
    if error:
        error_details = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        logger.error(f"{error_message}:\n{error_details}")
    else:
        logger.error(error_message)

def log_info(message: str):
    """
    Log an info message.
    
    Args:
        message (str): The information message to log
    """
    logger.info(message)

def log_warning(message: str):
    """
    Log a warning message.
    
    Args:
        message (str): The warning message to log
    """
    logger.warning(message)

def log_debug(message: str):
    """
    Log a debug message (only visible when debug level is enabled).
    
    Args:
        message (str): The debug message to log
    """
    logger.debug(message)

def set_debug_mode(enable: bool = True):
    """
    Enable or disable debug logging.
    
    Args:
        enable (bool): True to enable debug logging, False to disable
    """
    logger.setLevel(logging.DEBUG if enable else logging.INFO)
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG if enable else logging.INFO)

# Example usage
if __name__ == "__main__":
    log_info("Testing info message")
    log_warning("Testing warning message")
    try:
        raise ValueError("Test error")
    except Exception as e:
        log_error("An error occurred during testing", e)

    # New debug logging capability
    set_debug_mode(True)  # Enable during development
    log_debug("Detailed debugging information")

    # Example of exception logging with full traceback
    try:
        x = 1 / 0  # Deliberate error for testing
    except Exception as e:
        log_error("Operation failed", e) 
