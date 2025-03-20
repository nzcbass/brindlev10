import json
import re
from pathlib import Path
from firebase_utils import download_file, upload_file

def extract_projects_from_json(json_path: str) -> dict:
    try:
        filename = Path(json_path).name
        file_data = download_file(filename)
        if not file_data:
            raise FileNotFoundError(f"File not found in Firebase Storage: {json_path}")

        # Decode the downloaded bytes and load JSON.
        json_str = file_data.decode("utf-8")
        data = json.loads(json_str)

                
        projects_by_location = {"NZ": {}, "International": {}}
        experiences = data.get("ResumeParserData", {}).get("SegregatedExperience", [])

        # -----------------------------------------------------------------------------
        # REGEX EXPLANATION:
        #
        # We removed (^|\n) so that "Work Project:" (or "Project Accomplishment:")
        # can appear *anywhere* in the text, not necessarily at a new line start.
        #
        # 1) (?i) = case-insensitive
        #    We removed (?m) because we no longer need line starts for matching.
        #
        # 2) (?:work\s+)? optionally matches "work " (with one or more spaces),
        #    so we match either "Project" or "Work Project".
        #
        # 3) (?:project|projects?) = "Project" or "Projects"
        #
        # 4) (?:accomplishment(s?)?|completed)? optionally matches words like
        #    "accomplishment", "accomplishments", "completed."
        #
        # 5) \s*[;:.\-]? optionally matches punctuation like ';', ':', '.', or '-'
        #    plus any surrounding spaces.
        #
        # 6) (.*?) lazily captures the project text until the next recognized heading.
        #
        # 7) LOOKAHEAD:
        #    (?=\n\s*(?:company|position|duration|location|date|projects?|project
        #             |duty|duties|responsibil\w*|work\s+(?:project|projects?)|$))
        #    means we stop capturing as soon as we see a new line followed by
        #    any of these headings (company, position, etc.) or end-of-string.
        #
        # This should handle lines like:
        #    "Work Project : Dubai Airport"
        #    "Project Accomplishment\nKing Abdullah University..."
        #
        # EVEN if they're not on a brand-new line at the text's start.
        # -----------------------------------------------------------------------------
        project_pattern = re.compile(
            r'(?i)'  # case-insensitive
            r'(?:work\s+)?(?:project|projects?)\s*'      # "Work Project" or "Project/Projects"
            r'(?:accomplishment(s?)?|completed)?\s*'     # optional "accomplishment/completed"
            r'[;:.\-]?\s*'                               # optional punctuation + spaces
            r'(.*?)'                                     # capture text lazily
            r'(?=\n\s*(?:company|position|duration|location|date|projects?|project|'
            r'duty|duties|responsibil\w*|work\s+(?:project|projects?)|$))',
            re.DOTALL
        )

        for job in experiences:
            # Get employer name
            employer_val = job.get("Employer", "Unknown")
            if isinstance(employer_val, dict):
                employer = employer_val.get("EmployerName", str(employer_val))
            else:
                employer = str(employer_val)
            
            # Run the updated regex on each job description
            description = job.get("JobDescription", "")
            matches = project_pattern.findall(description)

            extracted_projects = []
            for block in matches:
                # 'block' is the captured text for that "Project" segment
                # Split on newlines, tabs, bullet/dash characters
                lines = re.split(r'[\n\t\-–•]+', block)
                lines = [proj.strip() for proj in lines if proj.strip()]
                extracted_projects.extend(lines)

            if extracted_projects:
                # Determine location grouping
                is_nz = job.get("Location", {}).get("is_nz", False)
                loc_key = "NZ" if is_nz else "International"
                if employer in projects_by_location[loc_key]:
                    projects_by_location[loc_key][employer].extend(extracted_projects)
                else:
                    projects_by_location[loc_key][employer] = extracted_projects

        # Flatten projects grouped by location
        nz_projects = []
        intl_projects = []
        for employer, projects in projects_by_location.get("NZ", {}).items():
            nz_projects.extend(projects)
        for employer, projects in projects_by_location.get("International", {}).items():
            intl_projects.extend(projects)

        return {
            "{NZProjects}": "\n• " + "\n• ".join(nz_projects) if nz_projects else "None",
            "{InternationalProjects}": "\n• " + "\n• ".join(intl_projects) if intl_projects else "None"
        }
    except Exception as e:
        print(f"Error extracting projects: {e}")
        return {"ProjectsGroupedByLocation": {}}

def extract_project_summary() -> str:
    """
    Create a summary for project extraction and upload it to Firebase Storage.
    
    Instead of saving the summary locally, this function encodes the summary,
    uploads it to Firebase Storage, and returns the public URL.
    """
    summary = "Project extraction completed successfully."
    data = summary.encode("utf-8")
    public_url = upload_file("project_summary.txt", data)
    return public_url

# Example usage:
if __name__ == "__main__":
    json_file = "/Users/claytonbadland/flask_project/parsed_jsons/enrichedBP_.json"  # Adjust if needed.
    result = extract_projects_from_json(json_file)
    print("Extracted Projects:")
    print("{NZProjects}:", result.get("{NZProjects}", "None"))
    print("{InternationalProjects}:", result.get("{InternationalProjects}", "None"))

    summary_url = extract_project_summary()
    print("Project summary available at:", summary_url)