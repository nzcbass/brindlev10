import os
import sys
import json
import traceback
import logging  # Added logging import
import re  # Add re module for regex operations
from pathlib import Path
from typing import Dict, Any, Optional
from docx import Document
from docxtpl import DocxTemplate
from location_service import LocationService
from spellchecker import SpellChecker

# Ensure the project directory is in the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import sanitize_filename  # Import the utility function

# Define paths
TEMPLATES_DIR = 'templates'
CURRENT_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), TEMPLATES_DIR, 'Current_template.docx')
OUTPUTS_DIR = 'outputs'

# Global settings
ENABLE_SPELL_CHECK = False  # Default to False

# Create necessary directories
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize spell checker with industry-specific words
def initialize_spell_checker():
    spell = SpellChecker()
    # Add common industry-specific terms and job titles
    industry_terms = {
        # Job Titles
        'foreman', 'supervisor', 'technician', 'operator', 'mechanic', 'electrician',
        'plumber', 'welder', 'carpenter', 'builder', 'fitter', 'turner', 'machinist',
        'rigger', 'scaffolder', 'painter', 'laborer', 'labourer', 'apprentice',
        'trainee', 'installer', 'assembler', 'driver', 'operator', 'storeman',
        'storeperson', 'yardman', 'tradesman', 'tradie', 'handyman', 'ductman',
        
        # Equipment and Skills
        'hvac', 'forklift', 'excavator', 'bobcat', 'scissorlift', 'crane',
        'bulldozer', 'grader', 'loader', 'digger', 'telehandler', 'manlift',
        'mig', 'tig', 'gmaw', 'smaw', 'fcaw', 'stick', 'plasma',
        
        # Certifications and Standards
        'ohs', 'whs', 'iso', 'haccp', 'tafe', 'cert', 'ppe', 'swms', 'sop',
        'msds', 'sds', 'jsa', 'jha', 'asme', 'osha', 'confined',
        
        # Common Industry Words
        'warehousing', 'logistics', 'dispatch', 'receiving', 'shipping',
        'maintenance', 'repair', 'installation', 'construction', 'fabrication',
        'assembly', 'production', 'manufacturing', 'industrial', 'commercial',
        'residential', 'mechanical', 'electrical', 'hydraulic', 'pneumatic'
    }
    spell.word_frequency.load_words(industry_terms)
    return spell

def debug_spell_correction(original: str, corrected: str, word_type: str = "word"):
    """Log debug information about spell corrections."""
    if original != corrected:
        logging.debug(f"Original {word_type}: '{original}'")
        logging.debug(f"Corrected {word_type}: '{corrected}'")
        logging.debug(f"Changed: {'Yes' if original != corrected else 'No'}")

def auto_correct_text(text: str, spell: SpellChecker, word_type: str = "text") -> str:
    """
    Automatically correct obvious spelling mistakes while preserving case and formatting.
    Added debugging output for corrections.
    """
    if not text:
        return text
        
    # Split into words while preserving punctuation
    def split_with_punctuation(s):
        import re
        return re.findall(r"[\w']+|[.,!?;]", s)
        
    words = split_with_punctuation(text)
    corrected_words = []
    any_corrections = False
    
    for word in words:
        # Skip punctuation, numbers, and short words
        if not word.isalpha() or word.isnumeric() or len(word) <= 2:
            corrected_words.append(word)
            continue
            
        # Skip words with all caps (likely acronyms)
        if word.isupper():
            corrected_words.append(word)
            continue
            
        # Check if word is misspelled
        word_lower = word.lower()
        if not spell.known([word_lower]):
            correction = spell.correction(word_lower)
            if correction and correction != word_lower:
                # Preserve original capitalization
                if word.istitle():
                    correction = correction.title()
                elif word.isupper():
                    correction = correction.upper()
                debug_spell_correction(word, correction)
                any_corrections = True
                word = correction
        
        corrected_words.append(word)
    
    # Reconstruct text with proper spacing
    result = ""
    for i, word in enumerate(corrected_words):
        if i > 0 and word not in ".,!?;":
            result += " "
        result += word
    
    if any_corrections:
        debug_spell_correction(text, result, word_type)
    
    return result

def spell_check_context(context: Dict[str, Any], spell: SpellChecker) -> Dict[str, Any]:
    """
    Apply spell checking focused on job titles and employers.
    """
    logging.info("Starting spell check")
    
    # Focus only on employment-related fields
    employer_fields = ['nzemployers', 'internationalemployers']
    position_fields = ['nzpositions', 'internationalpositions']
    
    # Process employer lists
    for field in employer_fields:
        if field in context and isinstance(context[field], str):
            if context[field] != "None":
                logging.info(f"Checking employers in {field}:")
                lines = context[field].split('\n')
                corrected_lines = []
                for line in lines:
                    if line.startswith('• '):
                        original = line[2:].strip()
                        corrected = auto_correct_text(original, spell, "employer name")
                        corrected_lines.append(f"• {corrected}")
                    else:
                        corrected_lines.append(line)
                context[field] = '\n'.join(corrected_lines)
    
    # Process position/job title lists
    for field in position_fields:
        if field in context and isinstance(context[field], str):
            if context[field] != "None":
                logging.info(f"Checking job titles in {field}:")
                lines = context[field].split('\n')
                corrected_lines = []
                for line in lines:
                    if line.startswith('• '):
                        original = line[2:].trip()
                        corrected = auto_correct_text(original, spell, "job title")
                        corrected_lines.append(f"• {corrected}")
                    else:
                        corrected_lines.append(line)
                context[field] = '\n'.join(corrected_lines)
    
    logging.info("Spell check complete")
    return context

def format_name(name_str: str) -> str:
    """
    Format name strings with proper capitalization.
    Each word in the name will have its first letter capitalized.
    
    Args:
        name_str (str): The name string to format
        
    Returns:
        str: The formatted name with proper capitalization
    """
    if not name_str:
        return ""
        
    # Split the string into words and capitalize each word
    words = name_str.split()
    formatted_words = []
    
    for word in words:
        # Handle hyphenated words
        if '-' in word:
            formatted_word = '-'.join(part.capitalize() for part in word.split('-'))
            formatted_words.append(formatted_word)
        else:
            formatted_words.append(word.capitalize())
            
    return ' '.join(formatted_words)

def extract_city_from_address(address: str) -> str:
    """
    Extract location from an address string by checking against nz_locations.json.
    If a match is found in nz_locations.json, return that location name.
    Otherwise, return the original address.
    """
    if not address:
        return ""
        
    # Convert to lowercase for matching
    address_lower = address.lower()
    
    # Initialize LocationService
    location_service = LocationService()
    
    # Check if any part of the address matches a known NZ location
    if location_service.is_nz_location(address_lower):
        # Find which part matched
        for nz_loc in location_service.nz_locations:
            if nz_loc in address_lower:
                return nz_loc.title()
    
    # If no match found in nz_locations.json, return the original address
    return address

def load_company_suffixes():
    """Load company suffixes from company_status.json file."""
    try:
        with open('/Users/claytonbadland/flask_project/data/company_status.json', 'r') as f:
            data = json.load(f)
            
        # Create a mapping of lowercase variations to preferred format
        suffixes = {}
        
        # Process all entries except 'status_words'
        for key, _ in data.items():
            if key != 'status_words':
                # Remove dots and convert to lowercase for matching
                clean_key = key.replace('.', '').lower()
                # Use the most formal version (typically the one starting with uppercase)
                if clean_key in suffixes:
                    if key[0].isupper():
                        suffixes[clean_key] = key
                else:
                    suffixes[clean_key] = key
        
        # Add common variations with dots
        suffixes.update({
            'w.i.i': 'W.I.I',
            'l.l.c': 'LLC',
            'p.l.c': 'PLC',
            's.a': 'SA',
            'n.v': 'NV',
            'a.g': 'AG',
            'g.m.b.h': 'GmbH'
        })
        
        return suffixes
    except Exception as e:
        logging.error(f"Error loading company suffixes: {e}")
        # Return default suffixes as fallback
        return {
            'lp': 'LP', 'llc': 'LLC', 'ltd': 'Ltd', 'inc': 'Inc',
            'corp': 'Corp', 'plc': 'PLC', 'gmbh': 'GmbH', 'ag': 'AG',
            'nv': 'NV', 'sa': 'SA', 'pty': 'Pty', 'co': 'Co',
            'w.i.i': 'W.I.I', 'l.l.c': 'LLC', 'p.l.c': 'PLC'
        }

# Cache for company suffixes
_COMPANY_SUFFIXES = None

# Global cache for short words
_SHORT_WORDS = None

def load_short_words():
    """Load short words from short_words.json file."""
    try:
        with open('/Users/claytonbadland/flask_project/data/short_words.json', 'r') as f:
            return set(json.load(f))
    except Exception as e:
        logging.error(f"Error loading short words: {e}")
        return set()

# Load short words during initialization
_SHORT_WORDS = load_short_words()

def format_company_name(name: str) -> str:
    """
    Format company names with special handling for acronyms, parentheses, and company suffixes.
    Ensures proper spacing outside parentheses and removes spaces inside parentheses, including before the closing parenthesis.
    Handles words of 3 letters or less based on a predefined list.
    """
    if not name:
        return ""
    
    # Load company suffixes if not already loaded
    global _COMPANY_SUFFIXES
    if _COMPANY_SUFFIXES is None:
        _COMPANY_SUFFIXES = load_company_suffixes()
    
    # Common words that should be lowercase unless at start
    common_words = {
        'and', 'of', 'the', 'in', 'on', 'at', 'to', 'for', 'with', 'by',
        'de', 'van', 'der', 'den', 'von', 'und', 'les', 'la', 'el'
    }
    
    # Ensure there is a space after hyphens
    name = name.replace('-', '- ')
    
    # Remove incomplete brackets (e.g., "(stellar" -> "")
    name = re.sub(r'\([^\)]*$', '', name)
    
    def is_acronym(word: str) -> bool:
        """
        Check if a word is an acronym (including those with dots).
        
        Rules:
        1. Known business acronyms are always preserved
        2. 2-3 letter words in caps are considered acronyms
        3. Words with dots between letters are acronyms
        4. Common last name words are never acronyms
        """
        # Remove dots and check if it's all uppercase
        clean_word = word.replace('.', '')
        
        # Common business acronyms to preserve
        known_acronyms = {
            'AE', 'IBM', 'ANZ', 'BNZ', 'MSS', 'LLC', 'LTD', 'INC', 'PTY',
            'GmbH', 'AG', 'NV', 'SA', 'PLC', 'CO', 'W.I.I', 'UAE', 'KSA'
        }
        
        # Common last name words that should never be treated as acronyms
        common_last_names = {
            'SMITH', 'JONES', 'BROWN', 'WILSON', 'TAYLOR', 'JOHNSON',
            'WHITE', 'MARTIN', 'ANDERSON', 'THOMPSON', 'WOOD'
        }
        
        # Terms that should NOT be treated as acronyms despite being uppercase
        not_acronyms = {
            'CONT', 'SITE', 'GULF', 'GENERAL', 'EAST', 'WEST', 'NORTH', 'SOUTH'
        }
        
        # If it's in the not_acronyms list, it's definitely not an acronym
        if clean_word.upper() in not_acronyms:
            return False
        
        # If it's a known acronym, preserve it
        if clean_word in known_acronyms:
            return True
        
        # If it's a common last name, it's not an acronym
        if clean_word in common_last_names:
            return False
        
        # Check for dots between letters (like W.I.I)
        if '.' in word and all(c.isupper() or c == '.' for c in word):
            return True
        
        # For 2-3 letter words, they must be known acronyms to be preserved
        if len(clean_word) <= 3:
            return clean_word in known_acronyms
        
        # For longer words, they must be in known_acronyms to be considered acronyms
        return clean_word in known_acronyms
    
    def format_part(text: str, is_in_parentheses: bool = False) -> str:
        if not text:
            return ""
            
        # Ensure proper spacing around hyphens
        text = text.replace('-', ' - ').replace('  ', ' ')
        words = [w for w in text.split() if w]
        formatted_words = []
        
        i = 0
        while i < len(words):
            word = words[i]
            word_lower = word.lower()
            word_no_dots = word_lower.replace('.', '')
            
            # Handle hyphen to ensure next word is capitalized
            if word == '-' and i + 1 < len(words):
                formatted_words.append(word)
                i += 1
                # Get the next word and capitalize it regardless of other rules
                next_word = words[i]
                # Special case for country acronyms after hyphen
                if next_word.lower() == "ksa":
                    formatted_words.append("KSA")
                # Special handling for known acronyms after hyphen
                elif is_acronym(next_word):
                    formatted_words.append(next_word)
                else:
                    formatted_words.append(next_word.capitalize())
                i += 1
                continue
            
            # Special handling for country acronyms
            if word_lower == "ksa":
                formatted_words.append("KSA")
                i += 1
                continue
                
            # Special handling for "CONT." and similar terms
            if word.upper() == "CONT" or word.upper() == "CONT.":
                formatted_words.append("Cont" + ("." if word.endswith(".") else ""))
                i += 1
                continue
            
            # Keep hyphen as is
            if word == '-':
                formatted_words.append(word)
                i += 1
                continue
            
            # Check for multi-word company suffixes (like "W.I.I")
            found_suffix = False
            for j in range(min(3, len(words) - i), 0, -1):
                potential_suffix = ' '.join(words[i:i+j]).lower()
                potential_suffix_no_dots = potential_suffix.replace('.', '')
                if potential_suffix in _COMPANY_SUFFIXES or potential_suffix_no_dots in _COMPANY_SUFFIXES:
                    suffix_key = potential_suffix if potential_suffix in _COMPANY_SUFFIXES else potential_suffix_no_dots
                    formatted_words.append(_COMPANY_SUFFIXES[suffix_key])
                    i += j
                    found_suffix = True
                    break
            
            if found_suffix:
                continue
                
            # Handle words of 3 letters or less
            if len(word) <= 3:
                if any(word_lower == w.lower() for w in _SHORT_WORDS):  # Normalize case for comparison
                    formatted_words.append(word)  # Preserve original capitalization
                else:
                    formatted_words.append(word.upper())  # Capitalize entirely
            # Check if word is an acronym
            elif is_acronym(word):
                formatted_words.append(word)
            # Handle common words (lowercase unless at start)
            elif word_lower in common_words and formatted_words:
                formatted_words.append(word_lower)
            # Regular capitalization for other words
            else:
                formatted_words.append(word.capitalize())
            
            i += 1
            
        return ' '.join(formatted_words)
    
    # Ensure proper spacing around parentheses
    name = name.replace('(', ' (').replace(')', ') ')
    
    # Split the name into parts based on parentheses
    parts = []
    current = []
    in_parentheses = False
    
    for char in name:
        if char == '(':
            if current:
                parts.append(''.join(current).strip())
                current = []
            in_parentheses = True
            current.append('(')  # Keep parentheses without extra spaces
        elif char == ')':
            if current:
                parts.append(''.join(current).strip())
                current = []
            in_parentheses = False
            current.append(')')
        else:
            current.append(char)
    
    if current:
        parts.append(''.join(current).strip())
    
    # Format each part
    formatted_parts = []
    for part in parts:
        if part.startswith('(') and part.endswith(')'):
            # Format content inside parentheses and remove spaces
            inner_content = part[1:-1].strip().replace(' ', '')
            formatted_inner = format_part(inner_content, True)
            formatted_parts.append(f"({formatted_inner})")
        else:
            formatted_parts.append(format_part(part))
    
    # Join parts and ensure proper spacing
    formatted_name = ' '.join(formatted_parts).replace('  ', ' ').replace(' )', ')').strip()
    formatted_name = re.sub(r'\([^)]*$', '', formatted_name)  # Remove any remaining incomplete brackets
    logging.debug(f"Formatted company name: {formatted_name}")
    return formatted_name

def format_bullet_list(items: set) -> str:
    """Format a set of items as a bullet-pointed list without leading newline."""
    if not items:
        return 'None'
    
    # Sort items after formatting company names
    formatted_items = sorted(format_company_name(item) for item in items)
    
    # Join items with bullet points
    bullet_list = "• " + "\n• ".join(formatted_items)
    
    # Ensure KSA is properly capitalized in bullet list items
    bullet_list = bullet_list.replace(" ksa", " KSA").replace(" Ksa", " KSA")
    bullet_list = bullet_list.replace('(ksa)', '(KSA)')  # Inside parentheses
    bullet_list = bullet_list.replace('(Ksa)', '(KSA)')  # With first letter capitalized
    
    return bullet_list

def format_years_experience(years: int, location: str) -> str:
    """Format years of experience into a sentence with proper pluralization."""
    if years == 0:
        return f"No work experience in {location}"
    year_word = "year" if years == 1 else "years"
    return f"{years} {year_word} work experience in {location}"

def round_up_years(months: int) -> int:
    """
    Convert months to years, rounding up.
    For example: 11 months = 1 year, 13 months = 2 years
    """
    return (months + 11) // 12

class DocGenerator:
    """Document generator for CV documents."""
    
    def __init__(self, template_path: str, enable_spell_check: bool = ENABLE_SPELL_CHECK):
        """
        Initialize the document generator with the template path.
        
        Args:
            template_path: Path to the template file
            enable_spell_check: Whether to enable spell checking (default: False)
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template file not found at: {template_path}")
        self.template_path = template_path
        self.location_service = LocationService()
        self.enable_spell_check = enable_spell_check
        self.spell = initialize_spell_checker() if enable_spell_check else None

    def prepare_context(self, cv_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a context dictionary for placeholder replacement.
        """
        context = {}
        profile = cv_data.get('data', {}).get('profile', {})
        basics = profile.get('basics', {})
        
        # Basic Information for Personal Profile section
        context['name'] = format_name(f"{basics.get('first_name', '')} {basics.get('last_name', '')}")
        
        # Format position with proper capitalization
        raw_position = basics.get('profession', '')
        words = raw_position.split()
        formatted_words = []
        
        # Words that should remain lowercase (unless at start)
        lowercase_words = {
            'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in',
            'of', 'on', 'or', 'the', 'to', 'with'
        }
        
        # Format each word
        for i, word in enumerate(words):
            # First word is always capitalized
            if i == 0:
                if '-' in word:
                    formatted_word = '-'.join(part.capitalize() for part in word.split('-'))
                    formatted_words.append(formatted_word)
                else:
                    formatted_words.append(word.capitalize())
            # Handle subsequent words
            else:
                # Check if word should be lowercase
                if word.lower() in lowercase_words:
                    formatted_words.append(word.lower())
                # Handle hyphenated words
                elif '-' in word:
                    formatted_word = '-'.join(part.capitalize() for part in word.split('-'))
                    formatted_words.append(formatted_word)
                else:
                    formatted_words.append(word.capitalize())
        
        context['position'] = ' '.join(formatted_words)
        
        # Get blurb directly from profile, not from basics
        blurb = profile.get('blurb', '')
        logging.debug(f"Raw blurb from profile: {blurb}")
        context['blurb'] = blurb
        logging.debug(f"Final blurb in context: {context['blurb']}")
        
        # Extract city from address
        full_address = basics.get('address', '')
        city = extract_city_from_address(full_address)
        context['location'] = city
        logging.info(f"Full address: {full_address}")
        logging.info(f"Extracted city: {city}")
        
        # Professional Experience - Split into NZ and International using is_nz flag
        experiences = profile.get('professional_experiences', [])
        nz_experiences = []
        international_experiences = []
        nz_months = 0
        international_months = 0
        total_months = 0
        
        # Lists to collect unique employers and positions
        nz_employers = set()
        international_employers = set()
        nz_positions = set()
        international_positions = set()
        
        logging.info("Experience duration debug")
        
        # Process each experience entry
        for exp in experiences:
            company_name = format_company_name(exp.get('company', ''))
            formatted_exp = {
                'company': company_name,
                'position': exp.get('title', ''),  # Use title consistently
                'start_date': exp.get('start_date', ''),
                'end_date': exp.get('end_date', 'Present'),
                'description': exp.get('description', ''),
                'highlights': exp.get('highlights', []),
                'location': exp.get('location', '')
            }
            
            # Get duration in months from JSON with better error handling
            try:
                duration_months = exp.get('duration_in_months')
                if duration_months is None:
                    logging.warning(f"No duration_in_months for {formatted_exp['company']}, defaulting to 0")
                    duration_months = 0
                elif isinstance(duration_months, str):
                    duration_months = int(duration_months)
                elif not isinstance(duration_months, int):
                    logging.warning(f"Invalid duration_in_months type for {formatted_exp['company']}: {type(duration_months)}")
                    duration_months = 0
            except (ValueError, TypeError) as e:
                logging.error(f"Could not parse duration for {formatted_exp['company']}: {e}")
                duration_months = 0
                    
            logging.info(f"Experience at {formatted_exp['company']}: {duration_months} months")
            
            # Add duration to appropriate category based on is_nz flag
            if exp.get('is_nz', False):
                nz_months += duration_months
                nz_experiences.append(formatted_exp)
                if formatted_exp['company']:
                    nz_employers.add(formatted_exp['company'])
                if formatted_exp['position']:
                    nz_positions.add(formatted_exp['position'])
            else:
                international_months += duration_months
                international_experiences.append(formatted_exp)
                if formatted_exp['company']:
                    international_employers.add(formatted_exp['company'])
                if formatted_exp['position']:
                    international_positions.add(formatted_exp['position'])
            
            total_months += duration_months
        
        # Convert months to years (rounded up)
        total_years = round_up_years(total_months)
        nz_years = round_up_years(nz_months)
        initial_international_years = round_up_years(international_months)
        
        # Adjust international years to ensure total adds up correctly
        international_years = total_years - nz_years
        if international_years < initial_international_years:
            international_years = initial_international_years
            total_years = nz_years + international_years
        
        # Update total years in the JSON structure
        logging.info(f"Total months: {total_months} (rounded up to {total_years} years)")
        logging.info(f"NZ months: {nz_months} (rounded up to {nz_years} years)")
        logging.info(f"International months: {international_months} (initial round up to {initial_international_years} years, adjusted to {international_years} years)")
        logging.info(f"Final total years (NZ + International): {total_years}")
        
        # Update the JSON structure with calculated years
        if 'data' in cv_data:
            cv_data['data']['profile']['basics']['total_experience_in_years'] = total_years
        else:
            cv_data['profile']['basics']['total_experience_in_years'] = total_years
            
        # Save the updated JSON back to file
        json_path = os.path.join('parsed_jsons', f"{Path(self.template_path).stem}_enriched.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(cv_data, f, indent=4)
        
        # Format years of experience as sentences
        context['nzyears'] = format_years_experience(nz_years, "New Zealand")
        context['internationalyears'] = format_years_experience(international_years, "international markets")
        
        # Format employers and positions as bullet-pointed lists without leading newline
        context['nzemployers'] = format_bullet_list(nz_employers)
        context['internationalemployers'] = format_bullet_list(international_employers)
        context['nzpositions'] = format_bullet_list(nz_positions)
        context['internationalpositions'] = format_bullet_list(international_positions)

        # Add qualifications from trainings_and_certifications
        qualifications = []
        trainings = profile.get('trainings_and_certifications', [])
        
        for training in trainings:
            qual_lines = []
            
            # Add description with proper formatting
            if description := training.get('description'):
                qual_lines.append(format_qualification_text(description))
                
            # Add issuing organization with proper formatting
            if org := training.get('issuing_organization'):
                formatted_org = format_qualification_text(org)
                qual_lines.append(f"Issued by {formatted_org}")
                
            # Remove the year/completion date line
            # if year := training.get('year'):
            #     qual_lines.append(f"Completed {year}")
                
            # Only add if we have any lines
            if qual_lines:
                qualifications.append("\n".join(qual_lines))
        
        # Join qualifications with double newline for spacing, or use default text if none found
        context['qualifications'] = "\n\n".join(qualifications) if qualifications else "No qualifications listed in CV"
        
        # Apply spell checking to the context only if enabled
        if self.enable_spell_check:
            logging.info("Spell check enabled")
            context = spell_check_context(context, self.spell)
        else:
            logging.info("Spell check disabled")
        
        logging.info("Context preparation complete")
        return context

    def generate_cv_document(self, json_path: str, projects_data: Optional[Dict] = None) -> str:
        """
        Generate a formatted CV document from the provided JSON data.
        """
        try:
            logging.info("Starting document generation")
            # 1. Template Verification
            logging.info(f"Template path: {self.template_path}")
            logging.info(f"Template exists: {os.path.exists(self.template_path)}")
            template_size = os.path.getsize(self.template_path) if os.path.exists(self.template_path) else 'N/A'
            logging.info(f"Template size: {template_size} bytes")
            
            if not os.path.exists(self.template_path):
                raise FileNotFoundError(f"Template file not found at: {self.template_path}")
            
            # 2. JSON Data Loading
            logging.info(f"JSON path: {json_path}")
            logging.info(f"JSON exists: {os.path.exists(json_path)}")
            with open(json_path, 'r', encoding='utf-8') as f:
                cv_data = json.load(f)
            logging.info("JSON data loaded successfully")
            
            # 3. Context Preparation
            logging.info("Context preparation")
            context = self.prepare_context(cv_data)
            if projects_data:
                context.update(projects_data)
                logging.info("Projects data added to context")
            
            # Apply post-processing to fix slash spacing
            context = process_context_for_slashes(context)
            logging.info("Applied slash spacing fixes to context")
            
            # DIRECT FIX: Force capitalize position fields
            position_fields = ['nzpositions', 'internationalpositions']
            for field in position_fields:
                if field in context and isinstance(context[field], str):
                    # Force capitalization of all words in position titles
                    lines = context[field].split('\n')
                    formatted_lines = []
                    for line in lines:
                        if line.startswith('• '):
                            # Extract, format, and reconstruct the line
                            content = line[2:].replace('/', '/ ').replace('  ', ' ')
                            words = content.split()
                            capitalized = ' '.join(word.capitalize() for word in words)
                            formatted_lines.append(f'• {capitalized}')
                        else:
                            formatted_lines.append(line)
                    context[field] = '\n'.join(formatted_lines)
                    logging.info(f"Force capitalized {field}: {context[field]}")
            
            logging.info(f"Context keys: {list(context.keys())}")
            
            # Print the position values for debugging
            if 'nzpositions' in context:
                logging.info(f"NZ Positions (after processing): {context['nzpositions']}")
            
            if 'internationalpositions' in context:
                logging.info(f"International Positions (after processing): {context['internationalpositions']}")
            
            # 4. Template Loading
            logging.info("Template loading")
            try:
                doc = DocxTemplate(self.template_path)
                logging.info("Template loaded successfully")
                
                # Safety check before accessing docx attributes - prevents AttributeError
                if doc.docx is not None and hasattr(doc.docx, 'part'):
                    try:
                        # Hack: Directly modify the document's XML to add spaces after slashes
                        if hasattr(doc.docx.part, 'package') and hasattr(doc.docx.part.package, 'parts'):
                            for part in doc.docx.part.package.parts:
                                if part.content_type.startswith('application/vnd.openxmlformats-officedocument.wordprocessingml'):
                                    try:
                                        content = part.blob.decode('utf-8')
                                        if '/' in content:
                                            modified_content = content.replace('/', '/ ')
                                            part.blob = modified_content.encode('utf-8')
                                            logging.info(f"Modified XML content to add spaces after slashes")
                                    except Exception as xml_error:
                                        logging.warning(f"Error modifying XML content: {xml_error}")
                        else:
                            logging.warning("Template structure doesn't have expected attributes")
                    except Exception as struct_error:
                        logging.warning(f"Error accessing template structure: {struct_error}")
                else:
                    logging.warning("Template loaded, but docx attribute is missing required properties")
                
                # Check template variables
                try:
                    variables = doc.get_undeclared_template_variables()
                    logging.info(f"Template variables found: {variables}")
                    
                    # Check for required variables in context
                    missing_vars = [var for var in variables if var not in context]
                    if missing_vars:
                        logging.warning(f"Missing context for variables: {missing_vars}")
                except Exception as var_error:
                    logging.warning(f"Unable to process template variables: {var_error}")
                
            except Exception as template_error:
                logging.error(f"Template loading error: {template_error}")
                raise
            
            # 5. Document Generation
            logging.info("Document generation")
            try:
                doc.render(context)
                logging.info("Template rendering completed")
                
                # Generate only one output file
                base_name = Path(json_path).stem
                if (base_name.endswith('_enriched')):
                    base_name = base_name[:-9]
                
                # Sanitize the base name
                sanitized_base_name = sanitize_filename(base_name)
                
                # Use the sanitized name for the output path
                output_path = os.path.join(OUTPUTS_DIR, f"{sanitized_base_name}_CV.docx")
                
                # Save document
                logging.info(f"Saving document to: {output_path}")
                doc.save(output_path)
                
                # Verify output
                if os.path.exists(output_path):
                    output_size = os.path.getsize(output_path)
                    logging.info(f"Output file created successfully. Size: {output_size} bytes")
                    if output_size == 0:
                        raise ValueError("Generated file is empty")
                    
                    # Track the file creation
                    from file_tracker import track_file
                    track_file(output_path, "generate", "created", "Final document generated")
                    
                    logging.info("Document generated successfully")
                    return output_path
                else:
                    raise FileNotFoundError("Output file was not created")
                
            except Exception as render_error:
                logging.error(f"Document generation error: {render_error}")
                raise
                
        except Exception as e:
            logging.error(f"Error during document generation: {e}")
            traceback.print_exc()
            raise

def generate_cv_document(json_path: str, template_path: str, projects_data: Optional[Dict] = None, enable_spell_check: bool = ENABLE_SPELL_CHECK) -> str:
    """
    Standalone wrapper for generating a CV document.
    
    Args:
        json_path: Path to the JSON data file
        template_path: Path to the template file
        projects_data: Optional dictionary containing additional project data
        enable_spell_check: Whether to enable spell checking (default: False)
        
    Returns:
        str: Path to the generated CV document
    """
    generator = DocGenerator(template_path, enable_spell_check=enable_spell_check)
    return generator.generate_cv_document(json_path, projects_data)

def fix_slash_spacing(text: str) -> str:
    """
    Ensure there is a space after every slash in the text.
    This is a post-processor to fix formatting issues.
    """
    if isinstance(text, str) and '/' in text:
        # Replace all instances of "/" with "/ " but avoid double spaces
        result = text.replace('/', '/ ').replace('  ', ' ')
        logging.debug(f"SLASH FIX: '{text}' -> '{result}'")
        return result
    return text

def process_context_for_slashes(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process all string values in the context dictionary to ensure proper spacing after slashes
    and fix "AND" to "and".
    """
    for key, value in context.items():
        if isinstance(value, str):
            # Fix slash spacing
            if '/' in value:
                context[key] = fix_slash_spacing(value)
                logging.info(f"Fixed slash spacing in {key}")
            
            # Hard fix for "AND" -> "and" when not at the start of a line or sentence
            if " AND " in value.upper():
                # Process line by line to avoid changing "AND" at the start of a line
                lines = value.split('\n')
                processed_lines = []
                for line in lines:
                    # For bullet points, preserve the bullet and process the rest
                    if line.startswith('• '):
                        bullet_content = line[2:]
                        # Don't change "AND" at the start, only in the middle
                        words = bullet_content.split()
                        if len(words) > 1:
                            # Keep first word as is
                            processed_words = [words[0]]
                            # Process remaining words
                            for word in words[1:]:
                                if word.upper() == "AND":
                                    processed_words.append("and")
                                else:
                                    processed_words.append(word)
                            processed_line = '• ' + ' '.join(processed_words)
                        else:
                            processed_line = line
                    else:
                        # For regular text, replace "AND" with "and" but not at the start
                        processed_line = line.replace(" AND ", " and ")
                    
                    processed_lines.append(processed_line)
                
                context[key] = '\n'.join(processed_lines)
                logging.info(f"Fixed 'AND' -> 'and' in {key}")
        
        elif isinstance(value, list):
            context[key] = [fix_slash_spacing(item) if isinstance(item, str) else item for item in value]
    
    return context

def format_qualification_text(text: str) -> str:
    """Format qualification text with proper capitalization."""
    if not text:
        return ""
    
    # Common acronyms that should stay uppercase - expanded list
    common_acronyms = {
        'HSE', 'CAD', 'IT', 'OSHA', 'CPD', 'IOSH', 'NEBOSH', 'NZQA',
        'MMJV', 'ISO', 'AWS', 'API', 'ASME', 'ANSI', 'ASTM', 'PMP', 'PMI',
        'AWS', 'CWI', 'NDT', 'NDE', 'QA', 'QC', 'GIS', 'GPS', 'ERP', 'SAP',
        'EWP', 'MEWP', 'AEWV', 'WTR', 'BSC', 'B.SC',    
    }
    
    # Words that should be lowercase (unless at start)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in',
        'of', 'on', 'or', 'the', 'to', 'with', 'from'
    }
    
    # First, handle any text inside parentheses or brackets
    # Use regex to find content inside parentheses or brackets and capitalize the first word
    def capitalize_in_brackets(match):
        bracket_content = match.group(1)
        words = bracket_content.split()
        if words:
            words[0] = words[0].capitalize()
            return f"({' '.join(words)})"
        return match.group(0)
    
    # Apply the regex substitution to handle text in parentheses
    text = re.sub(r'\(([^)]+)\)', capitalize_in_brackets, text)
    
    # Also handle square brackets if they exist
    text = re.sub(r'\[([^]]+)\]', lambda m: f"[{m.group(1).capitalize()}]", text)
    
    # Split by spaces for the main text processing
    words = text.split()
    result = []
    
    # Process each word
    for i, word in enumerate(words):
        # Skip words inside parentheses as we've already processed them
        if word.startswith('(') and word.endswith(')'):
            result.append(word)
            continue
            
        # Check if it's a known acronym
        if word.upper() in common_acronyms:
            result.append(word.upper())
        # First word always capitalized
        elif i == 0:
            result.append(word.capitalize())
        # Handle hyphenated words
        elif '-' in word:
            hyphen_parts = word.split('-')
            formatted_parts = [p.capitalize() for p in hyphen_parts]
            result.append('-'.join(formatted_parts))
        # Common words that should be lowercase
        elif word.lower() in lowercase_words:
            result.append(word.lower())
        # IMPORTANT: Words like "SITE" should be properly capitalized, not kept uppercase
        elif word.isupper():
            result.append(word.capitalize())  # Change from uppercase to proper case
        # Default: capitalize first letter only
        else:
            result.append(word.capitalize())
            
    return ' '.join(result)

if __name__ == "__main__":
    # Example usage:
    logging.info("Starting main execution")
    test_json_path = "parsed_jsons/test_data_enriched.json"
    template_path = os.path.join(TEMPLATES_DIR, 'Current_template.docx')
    
    if os.path.exists(test_json_path):
        try:
            output_path = generate_cv_document(test_json_path, template_path)
            logging.info(f"Document generated successfully at: {output_path}")
        except Exception as e:
            logging.error(f"Failed to generate document: {e}")
    else:
        logging.error(f"Test file not found: {test_json_path}")
