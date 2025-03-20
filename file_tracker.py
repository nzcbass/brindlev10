import os
from datetime import datetime

# Simple dict to track files
tracked_files = {}

def track_file(file_path, stage, action="created", details=""):
    """Track a file operation in the pipeline"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    file_exists = os.path.exists(file_path)
    file_size = os.path.getsize(file_path) if file_exists else 0
    
    print(f"[{timestamp}] FILE: {action.upper()} {os.path.basename(file_path)} at {stage} ({file_size} bytes) {details}")
    
    # Store tracking info
    if file_path not in tracked_files:
        tracked_files[file_path] = []
    tracked_files[file_path].append({
        'timestamp': timestamp,
        'stage': stage,
        'action': action,
        'size': file_size
    })

def print_summary(base_name=None):
    """Print summary of tracked files"""
    print("\n===== FILE TRACKING SUMMARY =====")
    for path, history in tracked_files.items():
        filename = os.path.basename(path)
        if base_name and base_name not in filename:
            continue
        print(f"{filename}: {len(history)} operations")
    print("=================================\n")