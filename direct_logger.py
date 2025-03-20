#!/usr/bin/env python3
import os
import sys
import time
from datetime import datetime

# Direct file path - use desktop for visibility
HOME_DIR = os.path.expanduser("~")
DESKTOP_DIR = os.path.join(HOME_DIR, "Desktop")
LOG_FILE = os.path.join(DESKTOP_DIR, "flask_direct_log.txt")

def log_message(message, level="INFO"):
    """Write a message directly to the log file."""
    timestamp = datetime.now().isoformat()
    formatted_message = f"{timestamp} - {level} - {message}\n"
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_message)
            f.flush()
            os.fsync(f.fileno())
        print(f"{level}: {message}")
    except Exception as e:
        print(f"ERROR writing to log file: {e}")

def info(message):
    log_message(message, "INFO")

def debug(message):
    log_message(message, "DEBUG")

def warning(message):
    log_message(message, "WARNING")

def error(message, exception=None):
    if exception:
        message = f"{message}: {str(exception)}"
    log_message(message, "ERROR")

def init():
    """Initialize the log file."""
    try:
        # Create a header in the log file
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"=== Log started at {datetime.now().isoformat()} ===\n")
            f.write(f"=== PID: {os.getpid()} ===\n")
            f.write(f"=== CWD: {os.getcwd()} ===\n")
            f.write(f"=== Python: {sys.version} ===\n")
            f.write(f"{'='*50}\n\n")
            f.flush()
            os.fsync(f.fileno())
        return True
    except Exception as e:
        print(f"ERROR initializing log file: {e}")
        return False

if __name__ == "__main__":
    # Test the logger
    init()
    info("This is an info message")
    debug("This is a debug message")
    warning("This is a warning message")
    
    try:
        x = 1 / 0
    except Exception as e:
        error("Error in calculation", e)
    
    print(f"Log file is at: {LOG_FILE}")
    
    # Write some messages in a loop
    for i in range(5):
        info(f"Test message #{i}")
        time.sleep(1) 