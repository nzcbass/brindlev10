import os
from datetime import datetime
from pathlib import Path
import traceback
import sys
import time
import threading
import json

# Global variables
PROD_LOG_FILE = None
DEBUG_LOG_FILE = None
LOG_LOCK = threading.Lock()

def setup_logger():
    """Set up the logger with file handlers."""
    global PROD_LOG_FILE, DEBUG_LOG_FILE
    
    # Get the absolute path of the project directory
    PROJECT_DIR = Path('/Users/claytonbadland/flask_project')
    LOGS_DIR = PROJECT_DIR / 'logs'

    try:
        # Create logs directory with explicit permissions
        LOGS_DIR.mkdir(mode=0o755, exist_ok=True)
        print(f"Logs directory created/verified at: {LOGS_DIR}")
    except Exception as e:
        print(f"Error creating logs directory: {e}")
        sys.exit(1)

    # Create log file paths with absolute paths and include timestamp
    current_date = datetime.now().strftime("%Y%m%d")
    PROD_LOG_FILE = LOGS_DIR / f'cv_generator_{current_date}.log'
    DEBUG_LOG_FILE = LOGS_DIR / f'cv_generator_debug_{current_date}.log'

    print(f"Setting up new log files:")
    print(f"Production log path: {PROD_LOG_FILE}")
    print(f"Debug log path: {DEBUG_LOG_FILE}")

    # Create empty log files if they don't exist and set permissions
    for log_file in [PROD_LOG_FILE, DEBUG_LOG_FILE]:
        try:
            # Open file in append mode to ensure we don't overwrite existing logs
            with open(log_file, 'a', encoding='utf-8', buffering=1) as f:
                f.write(f"\n=== Log file initialized at {datetime.now().isoformat()} ===\n")
                f.flush()
                os.fsync(f.fileno())
            os.chmod(log_file, 0o644)
            print(f"Created/verified log file: {log_file}")
        except Exception as e:
            print(f"Error creating log file {log_file}: {e}")
            sys.exit(1)

    return {'prod': PROD_LOG_FILE, 'debug': DEBUG_LOG_FILE}

def write_log(level: str, message: str, extra_context: dict = None):
    """Write a log entry directly to the appropriate file."""
    global PROD_LOG_FILE, DEBUG_LOG_FILE, LOG_LOCK
    
    if not PROD_LOG_FILE or not DEBUG_LOG_FILE:
        print("ERROR: Logger not initialized")
        return

    timestamp = datetime.now().isoformat()
    log_entry = {
        'timestamp': timestamp,
        'level': level,
        'message': message,
        'context': extra_context or {}
    }

    # Format the log entry
    formatted_entry = f"{timestamp} - {level} - {message}"
    if extra_context:
        formatted_entry += f" - Context: {json.dumps(extra_context)}"
    formatted_entry += "\n"

    with LOG_LOCK:
        try:
            # Write to production log for INFO and above
            if level in ['INFO', 'WARNING', 'ERROR']:
                with open(PROD_LOG_FILE, 'a', encoding='utf-8', buffering=1) as f:
                    f.write(formatted_entry)
                    f.flush()
                    os.fsync(f.fileno())

            # Write to debug log for all levels
            with open(DEBUG_LOG_FILE, 'a', encoding='utf-8', buffering=1) as f:
                f.write(formatted_entry)
                f.flush()
                os.fsync(f.fileno())

        except Exception as e:
            print(f"Error writing to log file: {e}")

def log_error(error_message: str, error: Exception = None, context: dict = None):
    """Log an error message and optionally the exception details."""
    try:
        if error:
            error_details = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            full_message = f"{error_message}:\n{error_details}"
        else:
            full_message = error_message

        write_log('ERROR', full_message, context)
    except Exception as e:
        print(f"Error logging message: {e}")

def log_info(message: str, context: dict = None):
    """Log an info message."""
    try:
        write_log('INFO', message, context)
    except Exception as e:
        print(f"Error logging message: {e}")

def log_warning(message: str, context: dict = None):
    """Log a warning message."""
    try:
        write_log('WARNING', message, context)
    except Exception as e:
        print(f"Error logging message: {e}")

def log_debug(message: str, extra_context: dict = None):
    """Log a debug message with optional extra context."""
    try:
        write_log('DEBUG', message, extra_context)
    except Exception as e:
        print(f"Error logging debug message: {e}")

def log_operation_success(operation_type: str, details: str, context: dict = None):
    """Log successful operations for audit and monitoring."""
    message = f"{operation_type} Success: {details}"
    write_log('INFO', message, context)

def log_command_execution(command: str, output: str = None, error: str = None, exit_code: int = None):
    """Log command execution details including output and errors."""
    try:
        context = {
            'command': command,
            'output': output,
            'error': error,
            'exit_code': exit_code
        }
        write_log('INFO', f"Command Execution: {command}", context)
    except Exception as e:
        print(f"Error logging command execution: {e}")

def capture_terminal_output(func):
    """Decorator to capture terminal output of a function."""
    def wrapper(*args, **kwargs):
        output = []
        error = []
        
        def write_output(text):
            output.append(text)
            sys.stdout.write(text)
            sys.stdout.flush()
            
        def write_error(text):
            error.append(text)
            sys.stderr.write(text)
            sys.stderr.flush()
        
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            sys.stdout.write = write_output
            sys.stderr.write = write_error
            
            result = func(*args, **kwargs)
            
            if output:
                write_log('DEBUG', f"Captured output from {func.__name__}:\n{''.join(output)}")
            if error:
                write_log('ERROR', f"Captured error from {func.__name__}:\n{''.join(error)}")
            
            return result
            
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
    
    return wrapper

def get_log_files():
    """Return the current log file paths"""
    return {'prod': PROD_LOG_FILE, 'debug': DEBUG_LOG_FILE}

# Initialize the logger
setup_logger()

if __name__ == "__main__":
    print("\n=== Testing Unified Logger Configuration ===\n")
    
    # Test basic logging
    print("1. Testing basic logging...")
    log_info("Test info message")
    log_warning("Test warning message")
    log_debug("Test debug message")
    
    # Test error logging with exception
    print("\n2. Testing error logging with exception...")
    try:
        raise ValueError("Test error")
    except Exception as e:
        log_error("Test error message", e)
    
    # Test context logging
    print("\n3. Testing context logging...")
    log_info("Processing file", {"filename": "test.pdf", "size": "1.2MB"})
    
    # Test operation success logging
    print("\n4. Testing operation success logging...")
    log_operation_success("Test Operation", "Operation completed", {"duration": "2.5s"})
    
    # Display log file locations
    print("\n5. Checking log file locations...")
    log_files = get_log_files()
    if log_files:
        print(f"Log files are written to:")
        print(f"Production log: {log_files['prod']}")
        print(f"Debug log: {log_files['debug']}")
    
    print("\n=== Test Complete ===\n")
    print("Please check both log files for the test entries.") 