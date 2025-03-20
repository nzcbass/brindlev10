from firebase_utils import FirebaseConfig

# Instantiate FirebaseConfig so we can call its methods.
firebase_config = FirebaseConfig()

def emergency_debug_text_processor(text: str) -> str:
    """
    Emergency debug function to ensure slash spacing works.
    Add this to any text function that processes output.
    """
    if not isinstance(text, str):
        return text
        
    # Explicitly handle slashes for debugging
    if '/' in text:
        print(f"EMERGENCY DEBUG - Found slash in: {text}")
        fixed = text.replace('/', '/ ')
        print(f"EMERGENCY DEBUG - Fixed to: {fixed}")
        return fixed
    return text

def force_capitalize_positions(text: str) -> str:
    """
    Direct and forceful capitalization of position titles and words after slashes.
    """
    if not text or "• " not in text:
        return text
    
    # Process each line individually
    lines = text.split("\n")
    result_lines = []
    
    print(f"FORCE CAPITALIZE - Input: {text}")
    
    for line in lines:
        if line.startswith("• "):
            # Extract the content after the bullet
            position_text = line[2:].replace('/', '/ ').replace('  ', ' ')
            
            # Now capitalize each word, including after slashes
            words = position_text.split()
            capitalized_words = []
            
            # First word is always capitalized
            if words:
                capitalized_words.append(words[0].capitalize())
                
            # For remaining words, check if "AND" and handle specially
            for i in range(1, len(words)):
                word = words[i]
                if word.upper() == "AND":
                    capitalized_words.append("and")  # Hard fix for "AND" -> "and"
                else:
                    capitalized_words.append(word.capitalize())
            
            capitalized_position = ' '.join(capitalized_words)
            result_lines.append(f"• {capitalized_position}")
            print(f"FORCE CAPITALIZE - Processed line: '• {capitalized_position}'")
        else:
            result_lines.append(line)
    
    result = '\n'.join(result_lines)
    print(f"FORCE CAPITALIZE - Result: {result}")
    return result

def format_company_and_position_placeholders(placeholder_mapping: dict) -> dict:
    """
    Formats placeholders for consistent capitalization and formatting:
    - List items: Converts to bullet points with proper formatting
    - Text fields: Ensures proper capitalization for specific fields
    
    Args:
        placeholder_mapping (dict): Dictionary containing placeholder mappings
        
    Returns:
        dict: Formatted placeholder mappings
    """
    # Country acronyms to preserve
    country_acronyms = {'UAE', 'KSA', 'USA', 'UK'}
    
    # Format bullet-pointed lists
    keys_to_format = [
        "{InternationalEmployers}",
        "{NZEmployers}",
        "{NZPositions}",
        "{InternationalPositions}",
        "{Qualifications}"
    ]
    
    for key in keys_to_format:
        value = placeholder_mapping.get(key, "")
        if not value or value.strip().lower() == "none":
            continue

        # Split the string on semicolons
        items = [item.strip() for item in value.split(";") if item.strip()]
        formatted_items = []
        seen = set()
        
        for item in items:
            # For positions, apply specific formatting with all words capitalized
            if key in ["{NZPositions}", "{InternationalPositions}"]:
                # First add space after slash
                item_with_space = item.replace('/', '/ ').replace('  ', ' ')
                # Then capitalize all words and apply hard fix for "AND"
                words = item_with_space.split()
                formatted_words = []
                
                # First word is always capitalized
                if words:
                    formatted_words.append(words[0].capitalize())
                
                # For remaining words, check if "AND" and handle specially
                for i in range(1, len(words)):
                    word = words[i]
                    if word.upper() == "AND":
                        formatted_words.append("and")  # Hard fix for "AND" -> "and"
                    else:
                        formatted_words.append(word.capitalize())
                
                formatted_item = ' '.join(formatted_words)
            else:
                # For non-position items, use standard capitalization with AND fix
                words = item.split()
                formatted_words = []
                
                # First word is always capitalized
                if words:
                    formatted_words.append(words[0].capitalize())
                
                # For remaining words, check if "AND" and handle specially
                for i in range(1, len(words)):
                    word = words[i]
                    if word.upper() == "AND":
                        formatted_words.append("and")  # Hard fix for "AND" -> "and"
                    else:
                        formatted_words.append(word.capitalize())
                
                formatted_item = ' '.join(formatted_words)
                
                # Add spaces after slashes
                if '/' in formatted_item:
                    formatted_item = formatted_item.replace('/', '/ ').replace('  ', ' ')
            
            # Preserve country acronyms
            for acronym in country_acronyms:
                acronym_pattern = f"\\b{acronym.lower().capitalize()}\\b"
                formatted_item = formatted_item.replace(acronym.lower().capitalize(), acronym)
            
            # Remove duplicates (case-insensitive)
            if formatted_item.lower() not in seen:
                formatted_items.append(formatted_item)
                seen.add(formatted_item.lower())
        
        # Join items as a bullet list
        bullet_list = "\n".join(["• " + item for item in formatted_items])
        placeholder_mapping[key] = bullet_list
        
        # Apply special capitalization for position lists
        if key in ["{NZPositions}", "{InternationalPositions}"]:
            placeholder_mapping[key] = force_capitalize_positions(placeholder_mapping[key])
        
        # Print debug info - keep this for troubleshooting
        print(f"DEBUG - {key}: {placeholder_mapping[key]}")
    
    # Apply emergency debug processor as a final step
    for key in placeholder_mapping:
        if isinstance(placeholder_mapping[key], str):
            placeholder_mapping[key] = emergency_debug_text_processor(placeholder_mapping[key])
    
    return placeholder_mapping

def format_name(name_str):
    """
    Format a name string: First letter of each word capitalized, rest lowercase.
    """
    if not name_str:
        return ""
    return name_str.title()

def format_template(template_data: str) -> str:
    """
    Format the template data and upload the formatted result to Firebase Storage.
    
    In this example, we simply transform the text to uppercase,
    encode it as bytes, and upload it with the filename 'formatted_template.txt'.
    The function returns the public URL of the uploaded file.
    """
    formatted_data = template_data.upper().encode("utf-8")
    public_url = firebase_config.upload_file(destination_blob_name="formatted_template.txt", data=formatted_data)
    return public_url


if __name__ == "__main__":
    sample_mapping = {
        "{InternationalEmployers}": "ABC Company; abc company; XYZ Corp; xyz corp",
        "{NZEmployers}": "KEANGMAN, ENTERPRISES LTD.; NZ Company; nz company; ABC",
        "{NZPositions}": "Senior Developer; Senior Developer; Lead Engineer",
        "{InternationalPositions}": "Manager; Manager; Director",
        "{FullName}": "JOHN DOE",
        "{Position}": "SOFTWARE ENGINEER",
        "{CurrentLocation}": "SYDNEY, AUSTRALIA",
        "{Qualifications}": "BACHELOR OF SCIENCE; MASTER OF SCIENCE"
    }
    formatted_mapping = format_company_and_position_placeholders(sample_mapping)
    print("Formatted mapping:")
    for k, v in formatted_mapping.items():
        print(f"{k}:\n{v}\n")
    
    # -----------------------------------------------------------
    # Example testing for template formatting and upload to Firebase Storage.
    # -----------------------------------------------------------
    sample_template = "Hello, this is a template."
    template_url = format_template(sample_template)
    print("Formatted template available at:", template_url)
