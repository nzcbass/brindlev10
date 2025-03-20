from typing import Dict, Any, Optional, List, Tuple
import re
from pathlib import Path
import json
from datetime import datetime
import os

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class DataValidator:
    """Handles validation and sanitization of input data"""
    
    # Regex patterns for validation
    PATTERNS = {
        'name': r'^[A-Za-z\s\-\'\.]+$',
        'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'phone': r'^\+?[\d\s\-\(\)]+$',
        'date': r'^\d{4}-\d{2}-\d{2}$'
    }
    
    @staticmethod
    def validate_cv_data(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validates the structure and content of CV data.
        
        Args:
            data: Dictionary containing CV data
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        try:
            # Check basic structure
            if not isinstance(data, dict):
                errors.append("Invalid data format: expected dictionary")
                return False, errors
                
            if 'data' not in data:
                errors.append("Missing 'data' section")
                return False, errors
            
            profile = data.get('data', {}).get('profile', {})
            if not profile:
                errors.append("Missing profile information")
                return False, errors
            
            # Validate basics section
            basics = profile.get('basics', {})
            if not basics:
                errors.append("Missing basic information")
            else:
                # Validate name fields
                if not basics.get('first_name'):
                    errors.append("Missing first name")
                elif not re.match(DataValidator.PATTERNS['name'], basics['first_name']):
                    errors.append("Invalid first name format")
                    
                if not basics.get('last_name'):
                    errors.append("Missing last name")
                elif not re.match(DataValidator.PATTERNS['name'], basics['last_name']):
                    errors.append("Invalid last name format")
                    
                # Validate contact information if present
                if 'email' in basics and not re.match(DataValidator.PATTERNS['email'], basics['email']):
                    errors.append("Invalid email format")
                    
                if 'phone' in basics and not re.match(DataValidator.PATTERNS['phone'], basics['phone']):
                    errors.append("Invalid phone number format")
            
            # Validate professional experiences
            experiences = profile.get('professional_experiences', [])
            if not experiences:
                errors.append("No professional experiences found")
            else:
                for i, exp in enumerate(experiences, 1):
                    if not exp.get('company'):
                        errors.append(f"Missing company name in experience {i}")
                    if not exp.get('title'):
                        errors.append(f"Missing job title in experience {i}")
                    if not exp.get('start_date'):
                        errors.append(f"Missing start date in experience {i}")
                    elif not re.match(DataValidator.PATTERNS['date'], exp['start_date']):
                        errors.append(f"Invalid start date format in experience {i}")
                        
                    # Validate end date if not current position
                    if not exp.get('is_current', False):
                        if not exp.get('end_date'):
                            errors.append(f"Missing end date in experience {i}")
                        elif not re.match(DataValidator.PATTERNS['date'], exp['end_date']):
                            errors.append(f"Invalid end date format in experience {i}")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors

    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Sanitizes text input by removing potentially harmful characters.
        
        Args:
            text: Input text to sanitize
            
        Returns:
            Sanitized text
        """
        if not text:
            return ""
            
        # Remove control characters and non-printable characters
        text = ''.join(char for char in text if ord(char) >= 32)
        
        # Convert special quotes to regular quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        
        # Remove multiple spaces
        text = ' '.join(text.split())
        
        return text.strip()

    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Sanitizes text that might contain HTML by removing all HTML tags.
        
        Args:
            text: Input text that might contain HTML
            
        Returns:
            Sanitized text without HTML
        """
        if not text:
            return ""
            
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', text)
        
        # Handle HTML entities
        clean_text = clean_text.replace('&nbsp;', ' ')
        clean_text = clean_text.replace('&amp;', '&')
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')
        clean_text = clean_text.replace('&quot;', '"')
        
        return DataValidator.sanitize_text(clean_text)

    @staticmethod
    def validate_date_range(start_date: str, end_date: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validates a date range to ensure start_date is before end_date and dates are valid.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: Optional end date in YYYY-MM-DD format
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            
            # If no end date, only validate start date format
            if not end_date:
                return True, ""
                
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Ensure start date is before end date
            if start > end:
                return False, "Start date must be before end date"
                
            # Ensure dates are not in the future
            today = datetime.now()
            if start > today or end > today:
                return False, "Dates cannot be in the future"
                
            return True, ""
            
        except ValueError as e:
            return False, f"Invalid date format: {str(e)}"

    @staticmethod
    def validate_file_path(file_path: str) -> Tuple[bool, str]:
        """
        Validates a file path to ensure it exists and is accessible.
        
        Args:
            file_path: Path to the file to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            path = Path(file_path)
            
            # Check if path exists
            if not path.exists():
                return False, "File does not exist"
                
            # Check if path is a file
            if not path.is_file():
                return False, "Path is not a file"
                
            # Check if file is readable
            if not os.access(path, os.R_OK):
                return False, "File is not readable"
                
            return True, ""
            
        except Exception as e:
            return False, f"Invalid file path: {str(e)}"

def validate_json(data, schema_path=None):
    """
    Validate a JSON data structure against a schema.
    
    Args:
        data: The JSON data to validate
        schema_path: Optional path to a schema file
        
    Returns:
        (bool, str): A tuple containing (is_valid, error_message)
    """
    # Basic validation
    try:
        if not isinstance(data, dict):
            return False, "Data must be a JSON object"
        
        # Check for required fields
        if 'name' not in data:
            return False, "Name field is required"
            
        if 'contact' not in data:
            return False, "Contact section is required"
            
        # Validate known structure
        if not isinstance(data.get('experience', []), list):
            return False, "Experience must be a list"
            
        if not isinstance(data.get('education', []), list):
            return False, "Education must be a list"
            
        # Schema validation if provided
        if schema_path:
            import jsonschema
            import json
            
            with open(schema_path, 'r') as f:
                schema = json.load(f)
                
            try:
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.exceptions.ValidationError as e:
                return False, f"Schema validation error: {str(e)}"
                
        return True, ""
        
    except Exception as e:
        return False, f"Validation error: {str(e)}" 