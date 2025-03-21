import os
from pathlib import Path
import logging
import shutil
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def cleanup_duplicate_files(directory: str, user_downloads_dir: str = None):
    """
    Remove duplicate CV files from the outputs directory and optionally from the 
    user's Downloads folder.
    
    Args:
        directory (str): The outputs directory to clean
        user_downloads_dir (str, optional): User's Downloads directory to clean
    """
    # Clean app outputs directory
    cleanup_directory(directory)
    
    # Clean user's Downloads directory if provided
    if user_downloads_dir and os.path.exists(user_downloads_dir):
        cleanup_directory(user_downloads_dir)

def cleanup_directory(directory: str):
    """
    Remove duplicate CV files from a directory, keeping only the most recent for each base name.
    
    Args:
        directory (str): Directory to clean
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        logging.warning(f"Directory does not exist: {directory}")
        return
    
    # Group files by base name (without _CV suffix and numbers)
    file_groups = {}
    for file in dir_path.iterdir():
        if not file.is_file() or not file.name.endswith('.docx'):
            continue
            
        # Get the base name without _CV suffix and counters
        base_name = file.stem
        if '_CV' in base_name:
            base_name = base_name.split('_CV')[0]
        
        # Remove any trailing numbers from the base name
        import re
        base_name = re.sub(r'_\d+$', '', base_name)
        
        if base_name not in file_groups:
            file_groups[base_name] = []
            
        file_groups[base_name].append(file)
    
    # For each group, keep only the most recent file
    for base_name, files in file_groups.items():
        if len(files) <= 1:
            continue
            
        # Sort by modification time (most recent first)
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        
        # Keep the most recent file, delete the rest
        logging.info(f"Keeping most recent file: {files[0].name}")
        for file_to_delete in files[1:]:
            logging.info(f"Removing duplicate file: {file_to_delete.name}")
            try:
                file_to_delete.unlink()
            except Exception as e:
                logging.error(f"Failed to delete {file_to_delete}: {e}")

def cleanup_outputs_periodically(interval=3600):  # Run every hour
    """Run cleanup periodically in background"""
    while True:
        cleanup_duplicate_files('outputs')
        time.sleep(interval)

if __name__ == "__main__":
    # Run a one-time cleanup of the outputs directory
    outputs_dir = "outputs"
    
    # Get user's Downloads folder (platform-specific)
    from direct_download import get_downloads_folder
    downloads_dir = str(get_downloads_folder())
    
    cleanup_duplicate_files(outputs_dir, downloads_dir)
    
    logging.info(f"Cleaned outputs directory: {outputs_dir}")
    logging.info(f"Cleaned downloads directory: {downloads_dir}")
