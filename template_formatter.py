from firebase_utils import FirebaseConfig

# Instantiate FirebaseConfig so we can call its methods.
firebase_config = FirebaseConfig()

def format_company_and_position_placeholders(placeholder_mapping: dict) -> dict:
    """
    Formats placeholders for consistent capitalization and formatting:
    - List items: Converts to bullet points with proper capitalization
    - Text fields: Ensures proper capitalization (first letter uppercase, rest lowercase)
    
    Args:
        placeholder_mapping (dict): Dictionary containing placeholder mappings
        
    Returns:
        dict: Formatted placeholder mappings
    """
    # Country acronyms to preserve
    country_acronyms = {'UAE', 'KSA', 'USA', 'UK'}
    
    # Words that should remain lowercase (unless at start)
    lowercase_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in',
        'of', 'on', 'or', 'the', 'to', 'with'
    }
    
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
        # Skip formatting if the value is empty or 'None'
        if not value or value.strip().lower() == "none":
            continue

        # Split the string on semicolons
        items = [item.strip() for item in value.split(";") if item.strip()]
        deduped = []
        seen = set()
        for item in items:
            # Format each word in the item
            words = item.split()
            formatted_words = []
            for word in words:
                # Check if word is a country acronym
                if word.upper() in country_acronyms:
                    formatted_words.append(word.upper())
                # Handle hyphenated words
                elif '-' in word:
                    formatted_word = '-'.join(part.capitalize() for part in word.split('-'))
                    formatted_words.append(formatted_word)
                else:
                    formatted_words.append(word.capitalize())
            formatted_item = ' '.join(formatted_words)
            
            # Remove duplicates (case-insensitive)
            if formatted_item.lower() not in seen:
                deduped.append(formatted_item)
                seen.add(formatted_item.lower())
                
        # Join items as a bullet list
        bullet_list = "\n".join(["• " + item for item in deduped])
        placeholder_mapping[key] = bullet_list if bullet_list else "None"
    
    # Format simple text fields with proper capitalization
    keys_to_capitalize = [
        "{FullName}",
        "{CurrentLocation}"
    ]
    
    for key in keys_to_capitalize:
        value = placeholder_mapping.get(key, "")
        if not value or value.strip().lower() == "none":
            continue
            
        # Format each word in the value
        words = value.split()
        formatted_words = []
        for word in words:
            # Check if word is a country acronym
            if word.upper() in country_acronyms:
                formatted_words.append(word.upper())
            # Handle hyphenated words
            elif '-' in word:
                formatted_word = '-'.join(part.capitalize() for part in word.split('-'))
                formatted_words.append(formatted_word)
            else:
                formatted_words.append(word.capitalize())
        placeholder_mapping[key] = ' '.join(formatted_words)
    
    # Special handling for position titles
    if "{Position}" in placeholder_mapping:
        value = placeholder_mapping["{Position}"]
        if value and value.strip().lower() != "none":
            words = value.split()
            formatted_words = []
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
            placeholder_mapping["{Position}"] = ' '.join(formatted_words)
        
    return placeholder_mapping

# Example testing
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