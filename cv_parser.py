"""
CV Parser module for extracting structured information from CV documents.
"""

import os
import json
import base64
import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dotenv import load_dotenv
from location_service import LocationService
from file_tracker import track_file
from unified_logger import log_info, log_error, log_warning, log_debug, log_operation_success
import tempfile
from datetime import datetime
import firebase_admin
from firebase_admin import storage
from firebase_admin import firestore
from firebase_admin import credentials

# Load environment variables
load_dotenv('config.env')

# Configuration constants
PARSER_API_URL = os.environ.get("PARSER_API_URL", "https://cvparser.ai/api/v4/parse")
PARSER_API_KEY = os.environ.get("PARSER_API_KEY", "")
CVPARSER_TIMEOUT = int(os.getenv('CVPARSER_TIMEOUT_SECONDS', '45'))

print(f"Debug - API URL: {PARSER_API_URL}")
print(f"Debug - API Key loaded: {'Yes' if PARSER_API_KEY else 'No'} (Length: {len(PARSER_API_KEY)})")

# Define paths
PATHS = {
    'UPLOADS': Path('uploads'),
    'PARSED_JSON': Path('parsed_jsons'),
    'OUTPUTS': Path('outputs')
}

# Ensure directories exist
for path in PATHS.values():
    path.mkdir(exist_ok=True)

def make_parser_api_call(url: str, headers: Dict[str, str], payload: Dict[str, Any], 
                        max_retries: int = 5, initial_delay: float = 1.0) -> Optional[Dict[str, Any]]:
    """
    Make a CV parser API call with retry logic and exponential backoff.
    
    Args:
        url: The API endpoint URL
        headers: Request headers
        payload: Request payload
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds between retries
        
    Returns:
        The API response as a dictionary or None if all retries fail
    """
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=CVPARSER_TIMEOUT
            )
            
            # If successful, return the parsed JSON
            if response.status_code == 200:
                return response.json()
                
            # If the error is retryable (server errors 5xx)
            if 500 <= response.status_code < 600:
                if attempt < max_retries - 1:
                    sleep_time = delay * (2 ** attempt)  # Exponential backoff
                    print(f"Parser API error {response.status_code}. Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                    continue
            
            # For other error codes, log and return None
            print(f"Parser API error: {response.status_code} - {response.text}")
            return None
            
        except requests.Timeout:
            # For timeouts, immediately return None - no retries
            print(f"Parser API request timed out after {CVPARSER_TIMEOUT} seconds")
            return None
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                sleep_time = delay * (2 ** attempt)
                print(f"Parser API request failed: {str(e)}. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
                continue
            print(f"Parser API request failed after {max_retries} attempts: {str(e)}")
            return None
    
    return None

class CVParser:
    """Parser class for CV documents"""
    
    def __init__(self):
        """Initialize the CV parser with LocationService"""
        self.location_service = LocationService()
    
    def send_to_cv_parser(self, file_url: str) -> Optional[Dict[str, Any]]:
        """
        Send a CV to the parsing service with timeout handling.
        
        Args:
            file_url: URL to the CV file in Firebase
        
        Returns:
            Optional[Dict]: Parsed data or None if error occurs
        """
        try:
            # Track the start of the parsing process
            track_file(file_url, "parse", "starting", "Beginning CV parsing process")
            
            # 1. Download PDF content from file_url
            response = requests.get(file_url)
            if response.status_code != 200:
                print(f"Error downloading PDF: {response.status_code}")
                track_file(file_url, "parse", "failed", f"Error downloading PDF: {response.status_code}")
                return None

            pdf_content = response.content
            base64_pdf = base64.b64encode(pdf_content).decode('utf-8')
            track_file(file_url, "parse", "downloaded", "PDF downloaded successfully")

            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': PARSER_API_KEY
            }

            payload = {
                'base64': base64_pdf,
                'filename': 'cv.pdf',
                'wait': True
            }

            print("Sending to parser API...")
            track_file(file_url, "parse", "requesting", "Sending PDF to parser API")
            
            try:
                # Use the retry mechanism with configurable timeout
                parsed_data = make_parser_api_call(PARSER_API_URL, headers, payload)
                if not parsed_data:
                    track_file(file_url, "parse", "failed", "Parser API call failed or timed out")
                    return None

                track_file(file_url, "parse", "received", "Received parsed data from API")

                # Add location classification to each experience
                for exp in parsed_data.get('data', {}).get('profile', {}).get('professional_experiences', []):
                    location = exp.get('location', '')
                    exp['is_nz'] = self.location_service.is_nz_location(location)
                    print(f"Location '{location}' classified as {'NZ' if exp['is_nz'] else 'International'}")
                    
                    # If location is empty, try using company name
                    if not location and 'company' in exp:
                        company = exp.get('company', '')
                        exp['is_nz'] = self.location_service.is_nz_location(company)
                        print(f"Company '{company}' classified as {'NZ' if exp['is_nz'] else 'International'}")

                # Save and track the parsed data
                saved_result = self.save_parsed_data(parsed_data, file_url)
                
                # Extract file path for tracking
                base_name = Path(file_url).stem
                json_path = PATHS['PARSED_JSON'] / f"parsed_{base_name}.json"
                track_file(str(json_path), "parse", "saved", "Parsed data saved to JSON")

                return saved_result

            except requests.Timeout:
                msg = "Complex file structure found, please save this resume as a PDF then upload again, this should solve the problem."
                track_file(file_url, "parse", "timeout", f"Parser API request timed out after {CVPARSER_TIMEOUT} seconds")  # Add the timeout value
                print(f"Parser API timed out after {CVPARSER_TIMEOUT} seconds")  # Update to use CVPARSER_TIMEOUT variable
                return None
                
        except Exception as e:
            print(f"Parser error: {e}")
            track_file(file_url, "parse", "error", f"Parser error: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def parse_cv(self, file_path: str) -> str:
        """
        Bridge method that works with the local file path passed from draft_app.py.
        This is needed to maintain compatibility with the existing pipeline.
        
        Args:
            file_path: Path to the local CV file
            
        Returns:
            str: Path to the generated JSON file
        """
        try:
            # Get basename for consistent file naming
            base_name = Path(file_path).stem
            
            # Create file URL (this may need adjustment based on how Firebase works in your setup)
            file_url = f"file://{file_path}"  # This is a placeholder - your implementation may differ
            
            # Use existing send_to_cv_parser method
            parsed_data = self.send_to_cv_parser(file_url)
            
            if not parsed_data:
                print("Failed to parse CV")
                return ""
                
            # Return path to the JSON file that would have been created
            json_path = str(PATHS['PARSED_JSON'] / f"parsed_{base_name}.json")
            return json_path
            
        except Exception as e:
            print(f"Error in parse_cv: {str(e)}")
            import traceback
            traceback.print_exc()
            return ""
    
    def save_parsed_data(self, parsed_data: Dict[str, Any], file_url: str) -> Dict[str, Any]:
        """
        Save parsed CV data to a JSON file.
        
        Args:
            parsed_data: The parsed CV data
            file_url: URL of the original file
            
        Returns:
            Dict: A dictionary with the key "path" that points to the saved JSON file.
        """
        try:
            # Generate output filename from the URL
            base_name = Path(os.path.basename(file_url)).stem
            json_path = PATHS['PARSED_JSON'] / f"parsed_{base_name}.json"
            
            track_file(str(json_path), "parse", "saving", "Saving parsed data to JSON")
            
            # Ensure the directory exists
            json_path.parent.mkdir(exist_ok=True)
            
            # Write the parsed data to a JSON file
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, indent=2, ensure_ascii=False)
                
            print(f"Parsed data saved to {json_path}")
            track_file(str(json_path), "parse", "saved", "Parsed data saved successfully")
            
            return {"path": str(json_path)}
        except Exception as e:
            print(f"Error saving parsed data: {str(e)}")
            return {"path": ""}
    
    def extract_location_from_text(self, text: str) -> Optional[str]:
        """
        Extract location information from text.
        This is a placeholder - implement your location extraction logic here.
        
        Args:
            text: Text to extract location from
            
        Returns:
            str or None: Extracted location if found
        """
        # Placeholder for location extraction logic
        return None

# Create singleton instance
parser = CVParser()
send_to_cv_parser = parser.send_to_cv_parser
