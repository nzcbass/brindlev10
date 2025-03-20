#!/usr/bin/env python3
import basic_logger as log
import time
import os

print("=== Testing Logger ===")
print(f"Log file: {log.LOG_FILE}")
print(f"Log exists: {os.path.exists(log.LOG_FILE)}")
print(f"Log directory exists: {os.path.exists(log.LOG_DIR)}")
print(f"Current production mode: {log.PRODUCTION_MODE}")
print(f"Current log level: {log.LOG_LEVEL}")
print(f"Stdout capture enabled: {log.CAPTURE_STDOUT}")

log.info("Starting logger test")
log.debug("This is a debug message")
log.warning("This is a warning message")
log.error("This is an error message")

# Test with context data
log.info("Testing with context", {"test": "data", "number": 123})

# Test direct print
print("This is a direct print statement that should be captured in the log")

# Test command capture
log.info("Testing command capture")
stdout, stderr, exit_code = log.capture_command_output("ls -la")
print(f"Command exit code: {exit_code}")

# Wait a moment to ensure all writes complete
time.sleep(1)

# Verify log file content
try:
    with open(log.LOG_FILE, "r") as f:
        content = f.read()
        print(f"\nLog file size: {len(content)} bytes")
        print(f"Log file line count: {len(content.splitlines())}")
        print("\nLast 5 lines of log:")
        for line in content.splitlines()[-5:]:
            print(f"  {line}")
except Exception as e:
    print(f"Error reading log file: {e}")

# Test production mode
print("\n=== Testing Production Mode ===")
log.set_production_mode(True)
print(f"Production mode: {log.PRODUCTION_MODE}")
print(f"Log level: {log.LOG_LEVEL}")
print(f"Stdout capture: {log.CAPTURE_STDOUT}")

log.debug("This debug message should NOT appear in logs")
log.info("This info message should appear in logs")
print("This print should NOT be captured in logs")

# Switch back to development mode
log.set_production_mode(False)
print(f"\nProduction mode: {log.PRODUCTION_MODE}")
print(f"Log level: {log.LOG_LEVEL}")
print(f"Stdout capture: {log.CAPTURE_STDOUT}")

log.debug("Back to development mode - debug messages appear again")
print("Terminal capture should be working again")

print("\n=== Test Complete ===")
log.info("Test completed successfully") 