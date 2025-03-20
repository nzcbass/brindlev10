import os
import re
from pathlib import Path
from typing import Optional, Set, Dict
from dotenv import load_dotenv
from logger import log_warning, log_error

# Load environment variables
load_dotenv('config.env')

class SecurityConfig:
    # Maximum file size (16MB)
    MAX_FILE_SIZE = 16 * 1024 * 1024
    
    # Allowed file extensions and their corresponding MIME types
    ALLOWED_EXTENSIONS = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'doc': 'application/msword',
        'txt': 'text/plain'
    }
    
    # Allowed characters in filenames
    FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-. ]+$')
    
    @classmethod
    def get_api_key(cls, key_name: str) -> Optional[str]:
        """
        Safely retrieve API keys from environment variables.
        
        Args:
            key_name: Name of the API key to retrieve
            
        Returns:
            The API key if found, None otherwise
        """
        api_key = os.getenv(key_name)
        if not api_key:
            log_warning(f"Missing API key: {key_name}")
            return None
        return api_key
    
    @classmethod
    def validate_file(cls, filename: str, filesize: int) -> Dict[str, bool | str]:
        """
        Validate file attributes for security.
        
        Args:
            filename: Name of the file to validate
            filesize: Size of the file in bytes
            
        Returns:
            Dictionary containing validation results and any error message
        """
        result = {"valid": True, "message": ""}
        
        # Check file size
        if filesize > cls.MAX_FILE_SIZE:
            result["valid"] = False
            result["message"] = f"File size exceeds maximum allowed size of {cls.MAX_FILE_SIZE // (1024*1024)}MB"
            return result
            
        # Check file extension
        if '.' not in filename:
            result["valid"] = False
            result["message"] = "No file extension found"
            return result
            
        extension = filename.rsplit('.', 1)[1].lower()
        if extension not in cls.ALLOWED_EXTENSIONS:
            result["valid"] = False
            result["message"] = f"File type not allowed. Allowed types: {', '.join(cls.ALLOWED_EXTENSIONS.keys())}"
            return result
            
        # Validate filename characters
        if not cls.FILENAME_PATTERN.match(filename):
            result["valid"] = False
            result["message"] = "Invalid characters in filename"
            return result
            
        return result
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """
        Sanitize filename to prevent directory traversal and other attacks.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove any directory components
        filename = os.path.basename(filename)
        
        # Replace potentially dangerous characters
        filename = re.sub(r'[^a-zA-Z0-9_\-. ]', '', filename)
        
        return filename
    
    @classmethod
    def validate_json_data(cls, data: dict) -> Dict[str, bool | str]:
        """
        Validate JSON data structure.
        
        Args:
            data: JSON data to validate
            
        Returns:
            Dictionary containing validation results and any error message
        """
        result = {"valid": True, "message": ""}
        
        required_fields = ['data', 'profile', 'basics']
        
        try:
            # Check for required fields
            if 'data' not in data:
                result["valid"] = False
                result["message"] = "Missing 'data' field in JSON"
                return result
                
            if 'profile' not in data['data']:
                result["valid"] = False
                result["message"] = "Missing 'profile' field in JSON"
                return result
                
            if 'basics' not in data['data']['profile']:
                result["valid"] = False
                result["message"] = "Missing 'basics' field in JSON"
                return result
                
            # Validate basics fields
            basics = data['data']['profile']['basics']
            if not basics.get('first_name') and not basics.get('last_name'):
                result["valid"] = False
                result["message"] = "Missing required name fields"
                return result
                
        except Exception as e:
            result["valid"] = False
            result["message"] = f"Error validating JSON structure: {str(e)}"
            
        return result
    
    @classmethod
    def create_secure_temp_file(cls) -> Path:
        """
        Create a secure temporary file with proper permissions.
        
        Returns:
            Path to the secure temporary file
        """
        import tempfile
        
        # Create temp file with restricted permissions
        temp_fd, temp_path = tempfile.mkstemp(prefix='cv_', suffix='.tmp')
        
        # Set file permissions to owner read/write only
        os.chmod(temp_path, 0o600)
        
        # Close the file descriptor
        os.close(temp_fd)
        
        return Path(temp_path)

# Example usage
if __name__ == "__main__":
    # Test API key retrieval
    api_key = SecurityConfig.get_api_key('ANTHROPIC_API_KEY')
    print(f"API key found: {'Yes' if api_key else 'No'}")
    
    # Test file validation
    test_file = {
        'name': 'test.pdf',
        'size': 1024 * 1024  # 1MB
    }
    validation = SecurityConfig.validate_file(test_file['name'], test_file['size'])
    print(f"File validation: {validation}")
    
    # Test filename sanitization
    unsafe_name = '../../../etc/passwd'
    safe_name = SecurityConfig.sanitize_filename(unsafe_name)
    print(f"Sanitized filename: {safe_name}") 