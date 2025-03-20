from pathlib import Path
import json
import re
from firebase_utils import upload_file

class LocationService:
    def __init__(self, locations_file: str = 'data/nz_locations.json'):
        self.locations_file = Path(locations_file)
        
        # Load NZ locations
        try:
            with open(self.locations_file) as f:
                data = json.load(f)
                # If the file is a dict, use its keys; otherwise, fall back to expecting a 'locations' key.
                if isinstance(data, dict):
                    self.nz_locations = {loc.lower() for loc in data.keys()}
                else:
                    self.nz_locations = {loc.lower() for loc in data.get('locations', [])}
        except Exception as e:
            print(f"Error loading NZ locations: {e}")
            self.nz_locations = set()

    def _clean_location(self, location: str) -> str:
        """Clean location string for comparison."""
        if not location:
            return ""
        # Remove common punctuation and convert to lowercase
        return location.lower().replace(',', ' ').replace('.', ' ').strip()

    def is_nz_location(self, location_str: str) -> bool:
        """
        Determine if a location is in NZ using word boundary matching.
        """
        if not location_str:
            return False
            
        # Optionally, you could clean the location string using _clean_location.
        location_lower = self._clean_location(location_str)
        print(f"DEBUG: Checking location: '{location_lower}'")
        
        # Check NZ locations with word boundaries
        for nz_loc in self.nz_locations:
            nz_loc_pattern = r'\b' + re.escape(nz_loc) + r'\b'
            if re.search(nz_loc_pattern, location_lower):
                print(f"Found NZ location {nz_loc} in location {location_lower}")
                return True

        # Default to international if no matches found
        print(f"No location matches found for {location_lower}, defaulting to international")
        return False

    def enrich_experience_locations(self, parsed_json: dict) -> dict:
        """
        Enrich each job experience with a Boolean 'is_nz' flag.
        Unwraps JSON if nested under "data", then iterates through professional_experiences.
        """
        try:
            if "data" in parsed_json and "profile" in parsed_json["data"]:
                data_section = parsed_json["data"]
            else:
                data_section = parsed_json
                
            profile = data_section.get("profile", {})
            experiences = profile.get("professional_experiences", [])
            
            for job in experiences:
                location_str = job.get("location", "").strip()
                if not location_str:
                    # If location is blank, use the company field as fallback
                    location_str = job.get("company", "").strip()
                job["is_nz"] = self.is_nz_location(location_str)
            
            profile["professional_experiences"] = experiences
            data_section["profile"] = profile
            
            if "data" in parsed_json:
                parsed_json["data"] = data_section
            else:
                parsed_json = data_section
                
            return parsed_json

        except Exception as e:
            print(f"Error enriching locations: {e}")
            return parsed_json

def process_location_data(location_info: str) -> str:
    """
    Process location info (for example, perform any transformation) and upload the result to Firebase Storage.
    
    In this example, the location info is simply converted to uppercase, encoded,
    and then uploaded using the Firebase upload_file function. The function returns
    the public URL for the uploaded data.
    """
    processed_data = location_info.upper().encode("utf-8")
    public_url = upload_file("location_data.txt", processed_data)
    return public_url

# Example usage:
if __name__ == "__main__":
    # Test the LocationService functionality.
    loc_service = LocationService()
    sample_location = "Auckland, New Zealand"
    is_nz = loc_service.is_nz_location(sample_location)
    print(f"Is '{sample_location}' a NZ location? {is_nz}")
    
    # Test enriching experience locations (if you have a sample JSON, adjust path accordingly)
    # sample_json_path = "sample_parsed.json"
    # with open(sample_json_path, "r", encoding="utf-8") as f:
    #     sample_json = json.load(f)
    # enriched = loc_service.enrich_experience_locations(sample_json)
    # print("Enriched JSON:", enriched)
    
    # Test the new process_location_data function.
    sample_location_info = "Sample location data for processing."
    url = process_location_data(sample_location_info)
    print("Processed location data available at:", url)