def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by replacing hyphens with underscores.
    
    Args:
        filename (str): The original filename.
        
    Returns:
        str: The sanitized filename.
    """
    return filename.replace('-', '_')
