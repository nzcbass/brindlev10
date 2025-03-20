import os
from pathlib import Path

def cleanup_hyphen_files(directory: str):
    """
    Remove files with hyphens in their names from the specified directory.
    
    Args:
        directory (str): The directory to scan for files with hyphens.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Directory does not exist: {directory}")
        return
    
    for file in dir_path.iterdir():
        if file.is_file() and '-' in file.name:
            print(f"Removing file with hyphen: {file.name}")
            file.unlink()

if __name__ == "__main__":
    outputs_dir = "outputs"
    cleanup_hyphen_files(outputs_dir)
