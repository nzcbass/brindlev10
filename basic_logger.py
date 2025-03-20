#!/usr/bin/env python3
import os
import sys
import time
import json
import traceback
from datetime import datetime
import io
import threading

# Use project logs folder
LOG_DIR = '/Users/claytonbadland/flask_project/logs'
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOG_DIR, f"flask_log_{timestamp}.txt")
DEBUG_LOG_FILE = os.path.join(LOG_DIR, f"debug_log_{timestamp}.txt")

# Create logs directory if it doesn't exist
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Original stdout and stderr for restoration
ORIGINAL_STDOUT = sys.stdout
ORIGINAL_STDERR = sys.stderr

# Lock for thread-safe writing
LOG_LOCK = threading.Lock()

# Global settings - these can be set before calling initialize()
PRODUCTION_MODE = False
CAPTURE_STDOUT = True
LOG_LEVEL = "DEBUG"  # Default to debug level in development
ALWAYS_LOG_DEBUG_TO_FILE = True  # Always log debug to debug log file, even in production

# Flag to track if logger is initialized
_LOGGER_INITIALIZED = False

class LoggingStream(io.TextIOBase):
    """A stream that writes to both the original stream and the log file."""
    
    def __init__(self, original_stream, stream_name):
        self.original_stream = original_stream
        self.stream_name = stream_name
    
    def write(self, text):
        if text and text.strip():  # Only log non-empty content
            # Write to original stream
            self.original_stream.write(text)
            
            # Write to log file if stdout capture is enabled
            if CAPTURE_STDOUT and _LOGGER_INITIALIZED:
                with LOG_LOCK:
                    try:
                        with open(LOG_FILE, "a", encoding="utf-8") as f:
                            timestamp = datetime.now().isoformat()
                            f.write(f"{timestamp} [TERMINAL:{self.stream_name}] {text.rstrip()}\n")
                            f.flush()
                            os.fsync(f.fileno())
                        
                        # Also write terminal output to debug log if enabled
                        if ALWAYS_LOG_DEBUG_TO_FILE:
                            with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
                                timestamp = datetime.now().isoformat()
                                f.write(f"{timestamp} [TERMINAL:{self.stream_name}] {text.rstrip()}\n")
                                f.flush()
                                os.fsync(f.fileno())
                    except Exception as e:
                        # Don't use logging here to avoid recursion
                        print(f"Error writing terminal output to log: {e}")
        
        return len(text) if text else 0
    
    def flush(self):
        self.original_stream.flush()

def format_context(context):
    """Format context data for better readability in logs."""
    if not context:
        return ""
        
    if isinstance(context, dict):
        try:
            # For small dicts, format inline
            if len(context) <= 3 and all(len(str(v)) < 50 for v in context.values()):
                return " - " + ", ".join(f"{k}={v}" for k, v in context.items())
            # For larger or complex dicts, format with indentation
            else:
                formatted = json.dumps(context, indent=4, default=str)
                # Add indentation to each line for better readability
                return "\n    " + "\n    ".join(formatted.split("\n"))
        except:
            # Fallback if JSON serialization fails
            return " - " + str(context)
    elif isinstance(context, (list, tuple)):
        try:
            formatted = json.dumps(context, indent=4, default=str)
            return "\n    " + "\n    ".join(formatted.split("\n"))
        except:
            return " - " + str(context)
    else:
        return " - " + str(context)

def write_log(level, message, context=None):
    """Write a log message directly to the file."""
    if not _LOGGER_INITIALIZED:
        initialize()
        
    # Format the message with context
    timestamp = datetime.now().isoformat()
    formatted_context = format_context(context)
    if formatted_context and not formatted_context.startswith("\n"):
        log_message = f"{timestamp} [{level}] {message}{formatted_context}\n"
    elif formatted_context:
        log_message = f"{timestamp} [{level}] {message}{formatted_context}\n"
    else:
        log_message = f"{timestamp} [{level}] {message}\n"
    
    with LOG_LOCK:
        try:
            # Always write DEBUG messages to debug log file if enabled
            if level == "DEBUG" and ALWAYS_LOG_DEBUG_TO_FILE:
                with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(log_message)
                    f.flush()
                    os.fsync(f.fileno())
            
            # Skip logging to main log if the level is below the current log level
            if not should_log(level):
                # Still print to console if appropriate
                if should_log_to_console(level):
                    console_msg = message
                    if context and isinstance(context, dict) and len(context) <= 2:
                        # Show context in console for small dicts
                        console_msg += format_context(context)
                    print(f"{level}: {console_msg}")
                return
            
            # Write to main log file
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_message)
                f.flush()
                os.fsync(f.fileno())
            
            # Print to console with truncation for very long messages
            if should_log_to_console(level):
                console_msg = message
                if context and isinstance(context, dict) and len(context) <= 2:
                    # Show context in console for small dicts
                    console_msg += format_context(context)
                print(f"{level}: {console_msg}")
        except Exception as e:
            print(f"ERROR writing to log: {e}")

def should_log(level):
    """Determine if a message at the given level should be logged based on the current log level."""
    level_hierarchy = {
        "DEBUG": 0,
        "INFO": 1,
        "WARNING": 2,
        "ERROR": 3
    }
    
    # Default to showing everything if level not recognized
    current_level = level_hierarchy.get(LOG_LEVEL, 0)
    message_level = level_hierarchy.get(level, 0)
    
    return message_level >= current_level

def should_log_to_console(level):
    """Determine if a message should be shown in the console."""
    # Same as should_log but separated for clarity
    return should_log(level)

def initialize():
    """Create the log file with header info."""
    global _LOGGER_INITIALIZED
    
    if _LOGGER_INITIALIZED:
        return True
        
    try:
        print(f"*** LOGGING TO: {LOG_FILE} ***")
        if ALWAYS_LOG_DEBUG_TO_FILE:
            print(f"*** DEBUG LOGGING TO: {DEBUG_LOG_FILE} ***")
        
        # Initialize main log file
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"=== LOG STARTED AT {datetime.now().isoformat()} ===\n")
            f.write(f"=== PID: {os.getpid()} ===\n")
            f.write(f"=== USER: {os.getlogin()} ===\n")
            f.write(f"=== CWD: {os.getcwd()} ===\n")
            f.write(f"=== PYTHON: {sys.version} ===\n")
            f.write(f"=== PRODUCTION MODE: {PRODUCTION_MODE} ===\n")
            f.write(f"=== LOG LEVEL: {LOG_LEVEL} ===\n")
            f.write(f"=== TERMINAL CAPTURE: {CAPTURE_STDOUT} ===\n")
            f.write(f"=== SEPARATE DEBUG LOG: {ALWAYS_LOG_DEBUG_TO_FILE} ===\n")
            
            # Include more system information
            try:
                import platform
                f.write(f"=== PLATFORM: {platform.platform()} ===\n")
                f.write(f"=== SYSTEM: {platform.system()} {platform.release()} ===\n")
            except ImportError:
                pass
                
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
            
        # Initialize debug log file if enabled
        if ALWAYS_LOG_DEBUG_TO_FILE:
            with open(DEBUG_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(f"=== DEBUG LOG STARTED AT {datetime.now().isoformat()} ===\n")
                f.write(f"=== PID: {os.getpid()} ===\n")
                f.write(f"=== USER: {os.getlogin()} ===\n")
                f.write(f"=== CWD: {os.getcwd()} ===\n")
                f.write(f"=== PYTHON: {sys.version} ===\n")
                f.write(f"=== PRODUCTION MODE: {PRODUCTION_MODE} ===\n")
                f.write(f"=== LOG LEVEL: {LOG_LEVEL} ===\n")
                f.write(f"=== TERMINAL CAPTURE: {CAPTURE_STDOUT} ===\n")
                
                # Include more system information
                try:
                    import platform
                    f.write(f"=== PLATFORM: {platform.platform()} ===\n")
                    f.write(f"=== SYSTEM: {platform.system()} {platform.release()} ===\n")
                except ImportError:
                    pass
                    
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
        
        _LOGGER_INITIALIZED = True
        
        # Setup stdout capture based on production mode
        if CAPTURE_STDOUT:
            enable_stdout_capture(True)
            
        return True
    except Exception as e:
        print(f"ERROR initializing log: {e}")
        return False

def info(message, context=None):
    """Log info message with optional context data."""
    write_log("INFO", message, context)

def debug(message, context=None):
    """Log debug message with detailed context data."""
    write_log("DEBUG", message, context)

def warning(message, context=None):
    """Log warning with context."""
    write_log("WARNING", message, context)

def error(message, exc=None, context=None):
    """Log error with exception details and context."""
    if exc:
        # Include stack trace for exceptions
        exc_details = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # Format exception details with indentation
        formatted_exc = "\n    " + "\n    ".join(exc_details.split("\n"))
        message = f"{message}{formatted_exc}"
    
    write_log("ERROR", message, context)

def log_terminal_output(output_text, source="command"):
    """Directly log terminal output with a special format."""
    if not _LOGGER_INITIALIZED:
        return
        
    timestamp = datetime.now().isoformat()
    
    with LOG_LOCK:
        try:
            # Always write to debug log if enabled
            if ALWAYS_LOG_DEBUG_TO_FILE:
                with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
                    # Split by lines to ensure proper formatting
                    for line in output_text.splitlines():
                        if line.strip():  # Skip empty lines
                            f.write(f"{timestamp} [TERMINAL:{source}] {line}\n")
                    f.flush()
                    os.fsync(f.fileno())
            
            # Skip main log if terminal capture is disabled
            if not CAPTURE_STDOUT:
                return
                
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                # Split by lines to ensure proper formatting
                for line in output_text.splitlines():
                    if line.strip():  # Skip empty lines
                        f.write(f"{timestamp} [TERMINAL:{source}] {line}\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"ERROR writing terminal output to log: {e}")

def capture_command_output(command):
    """Execute a command and capture its output to the log."""
    import subprocess
    
    info(f"Executing command: {command}")
    
    try:
        # Run the command and capture output
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        exit_code = process.returncode
        
        # Log standard output
        if stdout:
            log_terminal_output(stdout, "stdout")
        
        # Log standard error
        if stderr:
            log_terminal_output(stderr, "stderr")
        
        info(f"Command completed with exit code: {exit_code}")
        return stdout, stderr, exit_code
    
    except Exception as e:
        error(f"Error executing command: {command}", e)
        return "", str(e), -1

def enable_stdout_capture(enabled=True):
    """Redirect stdout and stderr to also write to the log file."""
    global CAPTURE_STDOUT
    CAPTURE_STDOUT = enabled
    
    if enabled:
        # Replace stdout and stderr with our logging streams
        sys.stdout = LoggingStream(ORIGINAL_STDOUT, "stdout")
        sys.stderr = LoggingStream(ORIGINAL_STDERR, "stderr")
        if _LOGGER_INITIALIZED:
            debug("Terminal output capture enabled - stdout and stderr will be logged")
    else:
        # Restore original stdout and stderr
        sys.stdout = ORIGINAL_STDOUT
        sys.stderr = ORIGINAL_STDERR
        if _LOGGER_INITIALIZED:
            debug("Terminal output capture disabled")

def set_production_mode(enabled=True):
    """Configure the logger for production mode with reduced verbosity."""
    global PRODUCTION_MODE, LOG_LEVEL, CAPTURE_STDOUT
    
    PRODUCTION_MODE = enabled
    
    if enabled:
        # In production mode, set higher log level and disable terminal output capture
        LOG_LEVEL = "INFO"  # Only log INFO and above in production
        CAPTURE_STDOUT = False  # Disable terminal output capture
        
        # Ensure stdout is restored
        sys.stdout = ORIGINAL_STDOUT
        sys.stderr = ORIGINAL_STDERR
        
        if _LOGGER_INITIALIZED:
            info("Logger set to PRODUCTION mode - reduced verbosity, terminal capture disabled")
            # Add a note about debug log
            if ALWAYS_LOG_DEBUG_TO_FILE:
                info(f"Debug messages still being logged to {DEBUG_LOG_FILE}")
    else:
        # In development mode, enable all logging
        LOG_LEVEL = "DEBUG"
        CAPTURE_STDOUT = True
        
        # Enable terminal capture
        sys.stdout = LoggingStream(ORIGINAL_STDOUT, "stdout")
        sys.stderr = LoggingStream(ORIGINAL_STDERR, "stderr")
        
        if _LOGGER_INITIALIZED:
            debug("Logger set to DEVELOPMENT mode - full verbosity, terminal capture enabled")

def set_log_level(level):
    """Set the minimum log level (DEBUG, INFO, WARNING, ERROR)."""
    global LOG_LEVEL
    
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    if level.upper() in valid_levels:
        LOG_LEVEL = level.upper()
        if _LOGGER_INITIALIZED:
            info(f"Log level set to {LOG_LEVEL}")
    else:
        if _LOGGER_INITIALIZED:
            warning(f"Invalid log level: {level}. Using current level: {LOG_LEVEL}")

def set_debug_log_mode(enabled=True):
    """Enable or disable separate debug logging."""
    global ALWAYS_LOG_DEBUG_TO_FILE
    ALWAYS_LOG_DEBUG_TO_FILE = enabled
    
    if _LOGGER_INITIALIZED:
        if enabled:
            info(f"Separate debug logging enabled to {DEBUG_LOG_FILE}")
        else:
            info("Separate debug logging disabled")

if __name__ == "__main__":
    # Initialize the logger
    initialize()
    
    info("Testing basic logger")
    debug("This is a debug message")
    warning("This is a warning")
    
    # Test with context data
    debug("Processing file", {"filename": "example.docx", "size": 1024, "type": "application/docx"})
    
    # Test with complex context
    debug("API response", {
        "status": "success", 
        "data": {
            "id": 12345,
            "name": "Example",
            "metadata": {"created": "2025-03-19", "author": "John Doe"}
        }
    })
    
    # Test error logging
    try:
        x = 1 / 0
    except Exception as e:
        error("Caught an exception", e, {"operation": "division", "value": 0})
    
    # Test direct terminal output
    print("This is a direct print statement that will be captured in logs")
    sys.stderr.write("This is stderr output that will be captured in logs\n")
    
    # Test command capture
    stdout, stderr, exit_code = capture_command_output("ls -la")
    print(f"Command output captured and logged. Exit code: {exit_code}")
    
    # Test production mode
    print("\n--- Testing production mode ---")
    set_production_mode(True)
    debug("This debug message should NOT appear in console when in production mode but will be in debug log")
    info("This info message SHOULD appear in logs even in production mode")
    error("Errors are always logged regardless of mode")
    
    # Test production mode terminal capture
    print("This print statement should NOT be captured in main logs in production mode but will be in debug log")
    
    # Switch back to development mode
    set_production_mode(False)
    debug("Back to development mode - debug messages appear again")
    print("Terminal capture should be working again")
        
    print(f"Log file is at: {LOG_FILE}")
    print(f"Debug log file is at: {DEBUG_LOG_FILE}")
    
    # Write some test entries
    for i in range(3):
        info(f"Test log entry #{i+1}")
        time.sleep(1) 