import os
import sys
from datetime import datetime
import threading
import time

# Log file path
LOG_FILE = None
LOG_LOCK = threading.Lock()

def init_logger():
    """Initialize the logger with a basic file handler."""
    global LOG_FILE
    
    # Create logs directory
    logs_dir = os.path.join(os.getcwd(), 'simple_logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    LOG_FILE = os.path.join(logs_dir, f'app_log_{timestamp}.txt')
    
    # Create empty file
    try:
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"=== Log file created at {datetime.now().isoformat()} ===\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"Error creating log file: {e}")
        # Fall back to a simple named log file in the current directory
        LOG_FILE = os.path.join(os.getcwd(), f'app_log.txt')
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(f"=== Log file created at {datetime.now().isoformat()} ===\n")
    
    print(f"Simple logger initialized. Log file: {LOG_FILE}")
    
    # Start a thread that periodically checks if the log file is writable
    def check_log_file():
        while True:
            try:
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(f"=== Log file check at {datetime.now().isoformat()} ===\n")
                    f.flush()
                    os.fsync(f.fileno())
            except Exception as e:
                print(f"Error checking log file: {e}")
            time.sleep(60)  # Check every minute
    
    checker_thread = threading.Thread(target=check_log_file, daemon=True)
    checker_thread.start()
    
    return LOG_FILE

def log(message, level="INFO"):
    """Log a message to the file."""
    global LOG_FILE, LOG_LOCK
    
    # Initialize logger if not already done
    if LOG_FILE is None:
        init_logger()
    
    timestamp = datetime.now().isoformat()
    log_message = f"{timestamp} - {level} - {message}\n"
    
    # Write to file with lock to prevent concurrent access issues
    with LOG_LOCK:
        try:
            # Use a small timeout to prevent hanging
            for attempt in range(3):
                try:
                    with open(LOG_FILE, 'a', encoding='utf-8') as f:
                        f.write(log_message)
                        f.flush()
                        os.fsync(f.fileno())
                    break
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        print(f"Error writing to log file (attempt {attempt+1}): {e}")
                    time.sleep(0.1)  # Small delay before retry
            
            # Also print to console
            print(f"{level}: {message}")
        except Exception as e:
            print(f"Error writing to log file: {e}")

def log_info(message):
    """Log an info message."""
    log(message, "INFO")

def log_error(message, error=None):
    """Log an error message."""
    if error:
        message = f"{message}: {str(error)}"
    log(message, "ERROR")

def log_warning(message):
    """Log a warning message."""
    log(message, "WARNING")

def log_debug(message):
    """Log a debug message."""
    log(message, "DEBUG")

def get_log_file_path():
    """Return the current log file path."""
    global LOG_FILE
    if LOG_FILE is None:
        init_logger()
    return LOG_FILE

if __name__ == "__main__":
    # Test the logger
    init_logger()
    log_info("This is an info message")
    log_warning("This is a warning message")
    log_error("This is an error message")
    log_debug("This is a debug message")
    
    try:
        x = 1 / 0
    except Exception as e:
        log_error("Division by zero error", e)
        
    print(f"Log file is at: {get_log_file_path()}") 