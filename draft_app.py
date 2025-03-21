from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
import os
from pathlib import Path
from werkzeug.utils import secure_filename
from firebase_utils import FirebaseConfig
from validators import validate_json
from cv_parser import CVParser, send_to_cv_parser
from claude_utils import generate_blurb_with_claude
from doc_generator import DocGenerator
from location_service import LocationService
from d_projects_to_enriched import ProjectExtractor
from direct_download import save_output_to_downloads
from datetime import timedelta
from file_tracker import track_file, print_summary
import logging  # Added logging import
import tempfile
import shutil
import json
import time
from typing import Dict, Any, Tuple, Optional
from utils import sanitize_filename  # Import the utility function

app = Flask(__name__)
firebase_config = FirebaseConfig()

# Create required directories
for path in ['uploads', 'parsed_jsons', 'outputs']:
    Path(path).mkdir(exist_ok=True)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    logging.info("Accessing index page")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file_route():
    temp_file = None
    try:
        if 'file' not in request.files:
            logging.warning("No file part in the request")
            return jsonify({"success": False, "message": "No file uploaded. Please select a file."})
        
        file = request.files['file']
        if file.filename == '':
            logging.warning("No selected file")
            return jsonify({"success": False, "message": "No selected file"})
        
        if not allowed_file(file.filename):
            logging.warning(f"File type not allowed: {file.filename}")
            return jsonify({"success": False, "message": "File type not allowed. Please upload a PDF or DOCX file."})
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)
        
        # Check file size
        file_size = os.path.getsize(temp_file.name)
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({"success": False, "message": "File too large. Maximum size is 16MB."})
        
        logging.info(f"Processing file: {file.filename} (Size: {file_size/1024/1024:.2f}MB)")
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        logging.info(f"Saving uploaded file: {filename}")
        shutil.copy2(temp_file.name, file_path)
        track_file(file_path, "upload", "saved", "File uploaded by user")

        # Process the file
        logging.info(f"Processing file: {filename}")
        response = process_cv_pipeline(file_path, filename)
        
        return jsonify(response)

    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        return jsonify({"success": False, "message": "An error occurred while processing the file."})
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logging.error(f"Error cleaning up temporary file: {str(e)}")

def retry_firebase_upload(file_path: str, filename: str) -> Optional[str]:
    """
    Retry Firebase upload with specific timing requirements.
    Returns firebase_path or None if all retries fail
    """
    max_retries = 3
    base_wait = 5  # Base wait time in seconds
    
    for attempt in range(max_retries):
        try:
            logging.info(f"Firebase upload attempt {attempt + 1} for {filename}")
            firebase_path = firebase_config.upload_file(file_path, filename)
            
            if (firebase_path):
                logging.info(f"Firebase upload successful on attempt {attempt + 1}, path: {firebase_path}")
                return firebase_path
                
            logging.warning(f"Firebase upload attempt {attempt + 1} failed - No path returned for file: {filename}")
            
        except Exception as e:
            logging.error(f"Firebase upload error on attempt {attempt + 1} for {filename}: {e}")
        
        if attempt < max_retries - 1:
            wait_time = base_wait + (attempt * 1) if attempt > 0 else base_wait
            logging.info(f"Waiting {wait_time} seconds before retry attempt {attempt + 2} for {filename}...")
            time.sleep(wait_time)
        else:
            logging.error(f"Firebase upload failed after all {max_retries} attempts for {filename}")
    
    return None

def process_cv_pipeline(file_path: str, filename: str) -> dict:
    """Process the CV through the complete pipeline with error handling."""
    try:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Sanitize the base name
        sanitized_base_name = sanitize_filename(base_name)
        
        logging.info(f"Starting CV pipeline for: {filename} (base name: {sanitized_base_name})")
        track_file(file_path, "pipeline", "starting", f"Processing CV: {sanitized_base_name}")
        
        # Stage 1 - Upload to Firebase with retries
        logging.info(f"Stage 1 - Uploading {filename} to Firebase")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        temp_file.close()
        
        shutil.copy2(file_path, temp_file.name)
        firebase_path = retry_firebase_upload(temp_file.name, f"{sanitized_base_name}.docx")
        
        if not firebase_path:
            logging.error(f"Firebase upload failed completely for {filename}")
            return {
                "success": False,
                "message": "Sorry, we're having some issues connecting to our cloud storage, please wait a couple of minutes and try again. If issues persist beyond this point, wait 15 minutes before trying again as Google is clearly having some issues :).",
                "status": "error"
            }
            
        track_file(firebase_path, "firebase", "uploaded", "File uploaded to Firebase")
        logging.info(f"Firebase upload completed successfully for {filename}")
        
        # Stage 2 - Parse CV
        logging.info(f"Stage 2 - Parsing CV for {filename}")
        cv_parser = CVParser()
        parsed_result = cv_parser.send_to_cv_parser(firebase_path)
        
        # If parsing failed, it might be due to timeout
        if not parsed_result:
            logging.warning(f"CV parsing failed for {filename} - Complex file structure detected")
            return {
                "success": False,
                "message": "Complex file structure found, please save this resume as a PDF then upload again, this should solve the problem.",
                "status": "warning",  # Indicates it's a warning, not a critical error
                "retry_as_pdf": True
            }
            
        # Get the path where the parsed data was saved
        parsed_json_path = parsed_result.get('path')
        if not parsed_json_path:
            logging.error(f"No parsed JSON path returned for {filename}")
            raise Exception("No path returned from CV parser")
        
        logging.info(f"CV parsing completed successfully for {filename}")
        
        # Stage 3 - Generate blurb
        logging.info(f"Stage 3 - Generating blurb for {filename}")
        enriched_json_result = generate_blurb_with_claude(parsed_json_path)

        # Check if the blurb generation was successful
        if isinstance(enriched_json_result, dict):
            enriched_json_path = enriched_json_result.get('path', '')
            if not enriched_json_path:
                # Check for a specific error message
                if enriched_json_result.get('status') == 'error':
                    logging.error(f"Failed to generate blurb for {filename}: {enriched_json_result.get('message')}")
                    return enriched_json_result  # Return the error message directly
                else:
                    logging.error(f"Failed to generate blurb for {filename}")
                    raise Exception("Failed to generate blurb")
        else:
            enriched_json_path = enriched_json_result

        track_file(enriched_json_path, "blurb", "generated", "Blurb generated and added to JSON")
        logging.info(f"Blurb generation completed for {filename}")
        
        # Stage 4 - Classify locations
        logging.info(f"Stage 4 - Classifying locations for {filename}")
        location_service = LocationService()
        with open(enriched_json_path, 'r') as file:
            enriched_data = json.load(file)
        enriched_data = location_service.enrich_experience_locations(enriched_data)
        logging.info(f"Location classification completed for {filename}")
        
        # Stage 5 - Save enriched JSON
        logging.info(f"Stage 5 - Saving enriched JSON for {filename}")
        enriched_json_path = os.path.join('parsed_jsons', f"{sanitized_base_name}_enriched.json")
        with open(enriched_json_path, 'w') as file:
            json.dump(enriched_data, file, indent=4)
        track_file(enriched_json_path, "enrich", "saved", "Enriched JSON saved")
        logging.info(f"Enriched JSON saved successfully for {filename}")
        
        # Stage 6 - Generate document
        logging.info(f"Stage 6 - Generating document for {filename}")
        template_path = '/Users/claytonbadland/flask_project/templates/Current_template.docx'
        generator = DocGenerator(template_path)
        output_path = generator.generate_cv_document(enriched_json_path)
        if not output_path:
            logging.error(f"Failed to generate CV document for {filename}")
            raise Exception("Failed to generate CV document")
        
        # Do not save to Downloads folder here
        logging.info(f"CV processing completed successfully for: {filename}")
        return {
            'success': True,
            'message': f'CV processed successfully: {sanitized_base_name}',
            'download_file': os.path.basename(output_path),
            'download_url': f"/download/{os.path.basename(output_path)}"
        }
        
    except Exception as e:
        logging.error(f"Error processing CV: {filename}: {e}")
        return {
            "success": False,
            "message": f"Error processing CV: {str(e)}",
            "status": "error"  # Indicates it's a critical error
        }

@app.route('/download/<filename>')
def download_file(filename):
    """Serve the file for download and save it to the Downloads folder."""
    try:
        logging.info(f"Initiating download request for: {filename}")
        file_path = os.path.join(app.root_path, 'outputs', filename)
        
        if not os.path.exists(file_path):
            logging.warning(f"Download failed - File not found: {filename}")
            raise FileNotFoundError(f"File not found: {filename}")
        
        # Extract the base name without file extension
        base_name = Path(filename).stem
        if base_name.endswith('_CV'):
            base_name = base_name[:-3]  # Remove "_CV" suffix
            
        # Create a clean filename with underscore format
        clean_filename = f"{sanitize_filename(base_name)}_CV{Path(filename).suffix}"
        
        # Only serve the file directly - DO NOT save to Downloads
        # The browser will handle saving to Downloads folder
        logging.info(f"Serving file: {filename}")
        
        # Return the file as an attachment with the clean filename
        return send_from_directory(
            os.path.join(app.root_path, 'outputs'),
            filename, 
            as_attachment=True,
            download_name=clean_filename  # Use this name for the downloaded file
        )
        
    except Exception as e:
        logging.error(f"Error downloading file: {filename}: {e}")
        return jsonify({
            "success": False,
            "message": "Error downloading file. Please try again."
        })

@app.errorhandler(413)
def request_entity_too_large(error):
    logging.warning("File too large uploaded")
    return jsonify({
        "success": False,
        "message": "File too large. Maximum size is 16MB."
    }), 413

@app.errorhandler(500)
def internal_server_error(error):
    logging.error("Internal server error: %s", error)
    return jsonify({
        "success": False,
        "message": "An internal server error occurred. Please try again later."
    }), 500

if __name__ == '__main__':
    logging.info("Starting CV Generator application")
    app.run(debug=True)

    # List files used during execution
    import sys
    print("Files used during execution:")
    for module in sys.modules.values():
        if hasattr(module, '__file__') and module.__file__:
            print(module.__file__)
