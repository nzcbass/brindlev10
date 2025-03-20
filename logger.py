import os
import json
from pathlib import Path
from typing import Any, Dict, Union  # Add Union to imports
from dotenv import load_dotenv
from anthropic import Anthropic
import ast
import re
import time
from firebase_utils import upload_file
from template_formatter import format_name
import requests
import logging  # Add logging import for error messages

# Environment and constants
PROJECT_ROOT = Path(__file__).parent
env_path = PROJECT_ROOT / 'config.env'
load_dotenv(env_path)

# Ensure required paths exist
PATHS = {
    'PARSED_JSON': PROJECT_ROOT / 'parsed_jsons',
    'OUTPUT': PROJECT_ROOT / 'outputs'
}
for path in PATHS.values():
    path.mkdir(parents=True, exist_ok=True)

# Get the API key; abort if not set
CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY not found in environment variables.")

# Initialize Anthropic client
client = Anthropic(api_key=CLAUDE_API_KEY)

def transform_rchilli_to_enriched(data: Any) -> Any:
    """Transform data from rChilli format to the enriched format expected downstream."""
    enriched = data.copy() if isinstance(data, dict) else data
    if not isinstance(enriched, dict) or "data" not in enriched:
        enriched = {"data": {"profile": {"basics": {}, "professional_experiences": []}}}
    return enriched

def process_claude_response(response: Any) -> str:
    """Extract and process the text from Claude's response."""
    print("DEBUG: Raw Claude response:", response)
    try:
        if hasattr(response, "content") and isinstance(response.content, list):
            return response.content[0].text.strip()
        return str(response).strip()
    except Exception as e:
        print(f"DEBUG: Error processing response: {e}")
        return "No career summary available."

def populate_name(resume_data: dict) -> dict:
    """Populate the full name in the resume data by combining first and last names."""
    try:
        basics = resume_data.get("data", {}).get("profile", {}).get("basics", {})
        first = basics.get("FirstName") or basics.get("first_name", "")
        last = basics.get("LastName") or basics.get("last_name", "")
        full_name = f"{first} {last}".strip()
        resume_data["data"]["profile"]["basics"]["FormattedName"] = full_name
        return resume_data
    except Exception as e:
        print(f"Error populating name: {e}")
        return resume_data

def load_company_status(file_path: str) -> dict:
    """Load a JSON file and attempt to fix formatting issues if necessary."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            fixed_dict = ast.literal_eval(content)
            return json.loads(json.dumps(fixed_dict))
        except Exception:
            try:
                fixed_content = re.sub(r"(?<!\\)'", r"\"", content)
                return json.loads(fixed_content)
            except Exception:
                print("Error: Cannot fix company status file format.")
                return {}

def make_claude_api_call(prompt: str, max_retries: int = 5, initial_delay: float = 1.0) -> Any:
    """
    Make a Claude API call with retry logic and exponential backoff.
    
    Args:
        prompt: The prompt to send to Claude
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds between retries
        
    Returns:
        The API response or raises the last encountered error
    """
    delay = initial_delay
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            return response
        except Exception as e:
            last_error = e
            if hasattr(e, 'status_code') and e.status_code == 529:
                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    sleep_time = delay * (2 ** attempt)  # Exponential backoff
                    print(f"Claude API overloaded. Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                    continue
            else:
                # For other errors, raise immediately
                raise e
    
    # If we've exhausted all retries
    raise last_error

def generate_blurb_with_claude(parsed_json_path: str) -> dict:
    """
    Calls Claude AI to generate a career blurb summarizing the CV.
    """
    resume_data = {}
    try:
        # Ensure parsed_json_path is not empty
        if not parsed_json_path:
            raise FileNotFoundError("Parsed JSON path is empty")
        
        # Load the parsed JSON data
        with open(parsed_json_path, 'r') as file:
            resume_data = json.load(file)
        
        # Extract candidate's first name and format it properly
        basics = resume_data.get("data", {}).get("profile", {}).get("basics", {})
        raw_first_name = basics.get("first_name", "The candidate")
        first_name = format_name(raw_first_name)
        
        # Calculate total years from professional experiences
        experiences = resume_data.get("data", {}).get("profile", {}).get("professional_experiences", [])
        nz_months = 0
        international_months = 0
        
        for exp in experiences:
            try:
                duration_months = exp.get('duration_in_months')
                if duration_months is None:
                    continue
                if isinstance(duration_months, str):
                    duration_months = int(duration_months)
                if not isinstance(duration_months, int):
                    continue
                
                if exp.get('is_nz', False):
                    nz_months += duration_months
                else:
                    international_months += duration_months
            except (ValueError, TypeError):
                continue
        
        # Round up years individually and sum them
        def round_up_years(months):
            return (months + 11) // 12
            
        nz_years = round_up_years(nz_months)
        international_years = round_up_years(international_months)
        total_years = nz_years + international_years
        
        print(f"DEBUG: Calculated years - NZ: {nz_years}, International: {international_years}, Total: {total_years}")
       
        # Initialize prompt variable so that it's available in the if statement
        prompt = None

        # Create a simpler prompt without focusing so much on the exact years
        if not prompt:
            profession = format_name(basics.get("profession", "professional"))
            location = format_name(basics.get("address", ""))
            
            cv_context = f"""
            Name: {first_name}
            Professional Title: {profession}
            Current Location: {location}
            Total Years Experience: {total_years}
            """
            
            prompt = (
                f"Write a professional career summary for {first_name}, "
                f"a {profession} with {total_years} years of experience, currently based in {location}. "
                f"Structure this as exactly two paragraphs with a blank line between them:\n\n"
                f"Paragraph 1: Focus on their overall experience and expertise (2-3 sentences).\n\n"
                f"Paragraph 2: Highlight their key strengths and notable professional achievements (2-3 sentences).\n\n"
                f"Use UK English and write in third person. Total length should be approximately 150 words."
            )
        
        # Make API call with retry logic
        max_retries = 5
        initial_delay = 1.0
        delay = initial_delay
        response = None

        for attempt in range(max_retries):
            try:
                response = make_claude_api_call(prompt)
                if response:
                    break
            except requests.exceptions.RequestException as e:
                print(f"Request to Claude API failed: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                    delay *= 2
                else:
                    print("Failed to generate blurb after multiple attempts")
                    return {
                        "success": False,
                        "message": "Our AI is having some problems, please wait a couple of minutes and then try uploading your CV again. If this problem persists, wait half an hour and hopefully Claude will have fixed itself by then :)",
                        "status": "error"
                    }
        
        # Process the response
        blurb = process_claude_response(response)
        print(f"Generated raw blurb with Claude: {blurb}")
        
        # POST-PROCESSING: Fix years of experience in the blurb
        corrected_blurb = fix_years_of_experience(blurb, first_name, total_years)
        print(f"Corrected blurb: {corrected_blurb}")
        
        # Insert the corrected blurb into resume data
        resume_data["data"]["profile"]["blurb"] = corrected_blurb
        
        # Save the enriched JSON to a new file
        enriched_json_path = parsed_json_path.replace(".json", "_enriched.json")
        with open(enriched_json_path, 'w') as file:
            json.dump(resume_data, file, indent=4)

        # Return the enriched file path so downstream code can use it
        return {"path": enriched_json_path}
       
    except Exception as e:
        print(f"Error generating blurb with Claude: {e}")
        return {"path": ""}

def fix_years_of_experience(blurb: str, name: str, correct_years: int) -> str:
    """
    Fix mentions of years of experience in the blurb by creating a standardized
    first sentence with the correct years and maintaining paragraph structure.
    """
    if not blurb:
        return blurb
        
    # Split into paragraphs
    paragraphs = [p.strip() for p in blurb.split('\n\n')]
    if not paragraphs:
        return blurb
        
    # Process first paragraph
    cleaned = paragraphs[0]
    if cleaned.strip():
        # Create standardized first sentence
        first_sentence = f"{name} is a seasoned professional with {correct_years} years of experience."
        
        # Find the first sentence end in the original paragraph
        sentence_end = cleaned.find('.')
        if sentence_end != -1:
            # Replace first sentence and keep rest of paragraph
            cleaned = first_sentence + cleaned[sentence_end + 1:]
        else:
            # If no sentence end found, use the standardized sentence
            cleaned = first_sentence
            
        paragraphs[0] = cleaned.strip()
    
    # Rejoin paragraphs with double newlines
    return '\n\n'.join(p for p in paragraphs if p.strip())

if __name__ == "__main__":
    sample_data = {
        "data": {
            "profile": {
                "basics": {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "address": "Auckland, New Zealand",
                    "profession": "Software Engineer"
                },
                "professional_experiences": [
                    {"title": "Developer", "location": "Auckland", "is_current": True}
                ]
            }
        }
    }

    # Populate name and generate blurb
    sample_data = populate_name(sample_data)
    sample_data = generate_blurb_with_claude(sample_data)

    print("\nFinal Enriched Data:\n", json.dumps(sample_data, indent=2))
