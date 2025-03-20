import os
import platform
import shutil
from pathlib import Path
from typing import Optional, Union
import io

def get_downloads_folder() -> Path:
    """Get the user's downloads folder path based on the operating system."""
    if platform.system() == "Windows":
        return Path(os.path.expanduser("~")) / "Downloads"
    elif platform.system() == "Darwin":  # macOS
        return Path(os.path.expanduser("~")) / "Downloads"
    else:  # Linux and other Unix
        return Path(os.path.expanduser("~")) / "Downloads"  # Most Linux distros use this

def save_output_to_downloads(output_file_path: Union[str, Path], 
                             new_filename: Optional[str] = None) -> Optional[Path]:
    """
    Save the processed output file to the user's Downloads folder.
    
    Args:
        output_file_path: Path to the output file in the project directory.
        new_filename: Optional new name for the file. If None, keeps original name.
        
    Returns:
        Path to the saved file in Downloads folder or None if operation failed.
    """
    try:
        # Convert to Path object if it's a string
        output_path = Path(output_file_path)
        
        # Handle relative paths by resolving against current working directory
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
            
        print(f"Looking for file at: {output_path}")

        # Verify source file exists and is not empty
        if not output_path.exists():
            raise FileNotFoundError(f"Source file not found: {output_path}")
        
        if output_path.stat().st_size == 0:
            raise ValueError(f"Source file is empty: {output_path}")
            
        # Get the user's downloads folder
        downloads_folder = get_downloads_folder()
        
        # Create downloads folder if it doesn't exist
        if not downloads_folder.exists():
            downloads_folder.mkdir(parents=True, exist_ok=True)
        
        # Use the same filename as the source
        dest_path = downloads_folder / output_path.name
        
        # Avoid overwriting by appending a counter if needed
        counter = 1
        original_stem = dest_path.stem
        while dest_path.exists():
            dest_path = downloads_folder / f"{original_stem}_{counter}{dest_path.suffix}"
            counter += 1
        
        # Copy the file to the downloads folder
        shutil.copy2(output_path, dest_path)
        
        # Verify the copied file
        if not dest_path.exists():
            raise FileNotFoundError(f"Failed to copy file to: {dest_path}")
        
        if dest_path.stat().st_size == 0:
            raise ValueError(f"Copied file is empty: {dest_path}")
            
        print(f"File saved to Downloads: {dest_path}")
        print(f"File size: {dest_path.stat().st_size} bytes")
        return dest_path
        
    except Exception as e:
        print(f"Error saving file to Downloads: {e}")
        return None