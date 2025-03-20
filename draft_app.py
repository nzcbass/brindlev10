from flask import Flask, request, jsonify, send_from_directory, render_template, send_file
import os
from pathlib import Path
from werkzeug.utils import secure_filename
import argparse
import sys

# Parse command line arguments first
def parse_args():
    parser = argparse.ArgumentParser(description='CV Generator Application')
    parser.add_argument('--production', action='store_true', 
                        help='Run in production mode (disables verbose logging and terminal capture)')
    parser.add_argument('--log-level', choices=['debug', 'info', 'warning', 'error'],
                        default='debug', help='Set the logging level')
    parser.add_argument('--disable-terminal-capture', action='store_true',
                        help='Disable capturing terminal output in logs')
    return parser.parse_args()

# Process command line arguments
args = parse_args()

# Import and configure logger before anything else
# This is important to set production mode before the logger is initialized
from basic_logger import set_production_mode, set_log_level, enable_stdout_capture

# Configure logger based on arguments
if args.production:
    set_production_mode(True)
    print("***STARTUP*** Running in PRODUCTION mode")
else:
    set_log_level(args.log_level.upper())
    print(f"***STARTUP*** Running in DEVELOPMENT mode with log level: {args.log_level.upper()}")

if args.disable_terminal_capture:
    enable_stdout_capture(False)
    print("***STARTUP*** Terminal output capture disabled")

# Now import the rest of the modules
import basic_logger as log
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
import tempfile
import shutil
import json
import time
from typing import Dict, Any, Tuple, Optional
import subprocess
from datetime import datetime

# Verify logger is properly set up
print("***STARTUP*** Verifying logger configuration")
print(f"***STARTUP*** Log file path: {log.LOG_FILE}")
print(f"***STARTUP*** Checking if logs directory exists: {os.path.exists(log.LOG_DIR)}")

# Test log file write access
try:
    with open(log.LOG_FILE, "a") as f:
        f.write(f"***MANUAL TEST ENTRY*** Application starting at {datetime.now().isoformat()}\n")
        f.flush()
        os.fsync(f.fileno())
    print(f"***STARTUP*** Successfully wrote to log file: {log.LOG_FILE}")
except Exception as e:
    print(f"***STARTUP*** ERROR: Could not write to log file: {str(e)}")

# Initialize Flask app
app = Flask(__name__)

# Initialize the logger at startup
print("***STARTUP*** Application Starting")
log.info("=== Application Starting ===")
log.info(f"Application starting. Log file at: {log.LOG_FILE}")
log.debug("Debug logging enabled")

# Verify logging is working by reading the log file
try:
    with open(log.LOG_FILE, "r") as f:
        log_content = f.read()
        print(f"***STARTUP*** Current log file content length: {len(log_content)} bytes")
        log_lines = log_content.splitlines()
        print(f"***STARTUP*** Number of log lines: {len(log_lines)}")
        if len(log_lines) > 0:
            print(f"***STARTUP*** Last log line: {log_lines[-1]}")
except Exception as e:
    print(f"***STARTUP*** ERROR: Could not read log file: {str(e)}")

firebase_config = FirebaseConfig()

# Create required directories
for path in ['uploads', 'parsed_jsons', 'outputs']:
    Path(path).mkdir(exist_ok=True)
    log.debug(f"Created directory: {path}")

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'txt'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Log application configuration
log.info("Application Configuration", {
    "upload_folder": UPLOAD_FOLDER,
    "output_folder": OUTPUT_FOLDER,
    "max_upload_size": f"{app.config['MAX_CONTENT_LENGTH'] / (1024*1024):.1f}MB",
    "allowed_extensions": ALLOWED_EXTENSIONS
})

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_system_command(command: str) -> Tuple[str, str, int]:
    """
    Run a system command and capture its output.
    
    Args:
        command (str): The command to run
        
    Returns:
        Tuple[str, str, int]: (output, error, exit_code)
    """
    # Use the new command capture function from basic_logger
    return log.capture_command_output(command)

@app.route('/')
def index():
    log.info("Accessing index page")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file_route():
    temp_file = None
    try:
        if 'file' not in request.files:
            log.warning("No file part in the request")
            return jsonify({"success": False, "message": "No file uploaded. Please select a file."})
        
        file = request.files['file']
        if file.filename == '':
            log.warning("No selected file")
            return jsonify({"success": False, "message": "No selected file"})
        
        if not allowed_file(file.filename):
            log.warning(f"File type not allowed: {file.filename}")
            return jsonify({"success": False, "message": "File type not allowed. Please upload a PDF or DOCX file."})
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)
        
        # Check file size
        file_size = os.path.getsize(temp_file.name)
        if file_size > app.config['MAX_CONTENT_LENGTH']:
            return jsonify({"success": False, "message": "File too large. Maximum size is 16MB."})
        
        log.info(f"Processing file: {file.filename}", {"size_mb": f"{file_size/1024/1024:.2f}MB"})
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        log.info(f"Saving uploaded file: {filename}")
        shutil.copy2(temp_file.name, file_path)
        track_file(file_path, "upload", "saved", "File uploaded by user")

        # Process the file
        log.info(f"Processing file: {filename}")
        response = process_cv_pipeline(file_path, filename)
        
        return jsonify(response)

    except Exception as e:
        log.error(f"Error processing file", e)
        return jsonify({"success": False, "message": "An error occurred while processing the file."})
    
    finally:
        # Clean up temporary file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                log.error(f"Error cleaning up temporary file", e)

def retry_firebase_upload(file_path: str, filename: str) -> Optional[str]:
    """
    Retry Firebase upload with specific timing requirements.
    Returns firebase_path or None if all retries fail
    """
    max_retries = 3
    base_wait = 5  # Base wait time in seconds
    
    for attempt in range(max_retries):
        try:
            log.info(f"Firebase upload attempt {attempt + 1} for {filename}")
            firebase_path = firebase_config.upload_file(file_path, filename)
            
            if firebase_path:
                log.info(f"Firebase upload successful on attempt {attempt + 1}", {"path": firebase_path})
                return firebase_path
                
            # More detailed logging for failed attempts
            log.warning(f"Firebase upload attempt {attempt + 1} failed - No path returned for file: {filename}")
            
        except Exception as e:
            log.error(f"Firebase upload error on attempt {attempt + 1} for {filename}", e)
        
        # Don't wait after the last attempt
        if attempt < max_retries - 1:
            wait_time = base_wait + (attempt * 1) if attempt > 0 else base_wait
            log.info(f"Waiting {wait_time} seconds before retry attempt {attempt + 2} for {filename}...")
            time.sleep(wait_time)
        else:
            log.error(f"Firebase upload failed after all {max_retries} attempts for {filename}")
    
    return None

def process_cv_pipeline(file_path: str, filename: str) -> dict:
    """Process the CV through the complete pipeline with error handling."""
    try:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        log.info(f"Starting CV pipeline for: {filename} (base name: {base_name})")
        log.debug("Pipeline initiated", {
            "filename": filename,
            "base_name": base_name,
            "file_size": os.path.getsize(file_path),
            "file_path": file_path
        })
        track_file(file_path, "pipeline", "starting", f"Processing CV: {base_name}")
        
        # Stage 1 - Upload to Firebase with retries
        log.info(f"Stage 1 - Uploading {filename} to Firebase")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        temp_file.close()
        
        shutil.copy2(file_path, temp_file.name)
        log.debug("Created temporary file for Firebase upload", {
            "temp_file": temp_file.name,
            "original_file": file_path,
            "temp_file_size": os.path.getsize(temp_file.name)
        })
        
        firebase_path = retry_firebase_upload(temp_file.name, f"{base_name}.docx")
        
        if not firebase_path:
            log.error(f"Firebase upload failed completely for {filename}")
            return {
                "success": False,
                "message": "Sorry, we're having some issues connecting to our cloud storage, please wait a couple of minutes and try again. If issues persist beyond this point, wait 15 minutes before trying again as Google is clearly having some issues :).",
                "status": "error"
            }
            
        track_file(firebase_path, "firebase", "uploaded", "File uploaded to Firebase")
        log.info(f"Firebase upload completed successfully for {filename}")
        log.debug("Firebase upload details", {
            "firebase_path": firebase_path,
            "attempts_needed": 1,
            "file_type": "docx"
        })
        
        # Stage 2 - Parse CV
        log.info(f"Stage 2 - Parsing CV for {filename}")
        start_time = time.time()
        cv_parser = CVParser()
        log.debug("Starting CV parsing", {
            "parser_initialized": True,
            "start_time": start_time
        })
        
        parsed_result = cv_parser.send_to_cv_parser(firebase_path)
        parse_time = time.time() - start_time
        
        # If parsing failed, it might be due to timeout
        if not parsed_result:
            log.warning(f"CV parsing failed for {filename} - Complex file structure detected")
            log.debug("CV parsing failure details", {
                "parse_time": parse_time,
                "firebase_path": firebase_path
            })
            return {
                "success": False,
                "message": "Complex file structure found, please save this resume as a PDF then upload again, this should solve the problem.",
                "status": "warning",
                "retry_as_pdf": True
            }
            
        # Get the path where the parsed data was saved
        parsed_json_path = parsed_result.get('path')
        if not parsed_json_path:
            log.error(f"No parsed JSON path returned for {filename}")
            raise Exception("No path returned from CV parser")
        
        log.info(f"CV parsing completed successfully for {filename}")
        log.debug("CV parsing details", {
            "parse_time": parse_time,
            "json_path": parsed_json_path,
            "json_size": os.path.getsize(parsed_json_path) if os.path.exists(parsed_json_path) else 0
        })
        
        # Stage 3 - Generate blurb
        log.info(f"Stage 3 - Generating blurb for {filename}")
        start_time = time.time()
        log.debug("Starting blurb generation", {
            "input_json": parsed_json_path,
            "start_time": start_time
        })
        
        enriched_json_result = generate_blurb_with_claude(parsed_json_path)
        blurb_time = time.time() - start_time

        # Check if the blurb generation was successful
        if isinstance(enriched_json_result, dict):
            enriched_json_path = enriched_json_result.get('path', '')
            if not enriched_json_path:
                # Check for a specific error message
                if enriched_json_result.get('status') == 'error':
                    error_msg = enriched_json_result.get('message')
                    log.error(f"Failed to generate blurb for {filename}: {error_msg}")
                    log.debug("Blurb generation failure details", {
                        "error": error_msg,
                        "time_taken": blurb_time,
                        "input_json": parsed_json_path
                    })
                    return enriched_json_result
                else:
                    log.error(f"Failed to generate blurb for {filename}")
                    raise Exception("Failed to generate blurb")
        else:
            enriched_json_path = enriched_json_result

        track_file(enriched_json_path, "blurb", "generated", "Blurb generated and added to JSON")
        log.info(f"Blurb generation completed for {filename}")
        log.debug("Blurb generation details", {
            "time_taken": blurb_time,
            "output_path": enriched_json_path,
            "output_size": os.path.getsize(enriched_json_path) if os.path.exists(enriched_json_path) else 0
        })
        
        # Stage 4 - Classify locations
        log.info(f"Stage 4 - Classifying locations for {filename}")
        start_time = time.time()
        log.debug("Starting location classification", {
            "input_json": enriched_json_path,
            "start_time": start_time
        })
        
        location_service = LocationService()
        with open(enriched_json_path, 'r') as file:
            enriched_data = json.load(file)
        enriched_data = location_service.enrich_experience_locations(enriched_data)
        location_time = time.time() - start_time
        
        log.info(f"Location classification completed for {filename}")
        log.debug("Location classification details", {
            "time_taken": location_time,
            "locations_processed": len(enriched_data.get('experience', [])),
            "total_experience_entries": len(enriched_data.get('experience', []))
        })
        
        # Stage 5 - Save enriched JSON
        log.info(f"Stage 5 - Saving enriched JSON for {filename}")
        enriched_json_path = os.path.join('parsed_jsons', f"{base_name}_enriched.json")
        log.debug("Saving enriched JSON", {
            "target_path": enriched_json_path,
            "data_size": len(json.dumps(enriched_data))
        })
        
        with open(enriched_json_path, 'w') as file:
            json.dump(enriched_data, file, indent=4)
        track_file(enriched_json_path, "enrich", "saved", "Enriched JSON saved")
        log.info(f"Enriched JSON saved successfully for {filename}")
        log.debug("Enriched JSON details", {
            "path": enriched_json_path,
            "size": os.path.getsize(enriched_json_path)
        })
        
        # Stage 6 - Generate document
        log.info(f"Stage 6 - Generating document for {filename}")
        start_time = time.time()
        template_path = '/Users/claytonbadland/flask_project/templates/Current_template.docx'
        log.debug("Starting document generation", {
            "template_path": template_path,
            "input_json": enriched_json_path,
            "start_time": start_time
        })
        
        generator = DocGenerator(template_path)
        output_path = generator.generate_cv_document(enriched_json_path)
        doc_time = time.time() - start_time
        
        if not output_path:
            log.error(f"Failed to generate CV document for {filename}")
            log.debug("Document generation failure", {
                "time_taken": doc_time,
                "template_path": template_path,
                "input_json": enriched_json_path
            })
            raise Exception("Failed to generate CV document")
        
        # Final step: Save document to Downloads folder
        log.info(f"Saving document to Downloads folder for {filename}")
        if os.path.exists(output_path):
            download_path = save_output_to_downloads(output_path)
            if not download_path:
                log.error(f"Failed to save file to Downloads folder for {filename}")
                raise Exception("Failed to save file to Downloads folder")
            track_file(download_path, "download", "saved", "File saved to Downloads folder")
            download_url = f"/download/{os.path.basename(output_path)}"
            log.info(f"File saved successfully to Downloads folder for {filename}")
            log.debug("Final document details", {
                "output_path": output_path,
                "download_path": download_path,
                "size": os.path.getsize(output_path),
                "generation_time": doc_time
            })
        else:
            log.error(f"Generated file not found at {output_path} for {filename}")
            raise FileNotFoundError(f"Generated file not found at {output_path}")

        log.info(f"CV processing completed successfully for: {filename}")
        log.debug("Pipeline completion details", {
            "total_time": time.time() - start_time,
            "final_size": os.path.getsize(output_path),
            "stages_completed": 6
        })
        
        return {
            'success': True,
            'message': f'CV processed successfully: {filename}',
            'download_file': os.path.basename(output_path),
            'download_url': download_url
        }
        
    except Exception as e:
        log.error(f"Error processing CV: {filename}", e, {
            "stage": "unknown",
            "filename": filename
        })
        return {
            "success": False,
            "message": f"Error processing CV: {str(e)}",
            "status": "error"
        }

@app.route('/download/<filename>')
def download_file(filename):
    """Serve the file for download with error handling."""
    try:
        log.info(f"Initiating download request for: {filename}")
        file_path = os.path.join(app.root_path, 'outputs', filename)
        
        if not os.path.exists(file_path):
            log.warning(f"Download failed - File not found: {filename}")
            raise FileNotFoundError(f"File not found: {filename}")
            
        log.info(f"File found, initiating download: {filename}")
        result = send_from_directory(
            os.path.join(app.root_path, 'outputs'),
            filename, 
            as_attachment=True
        )
        log.info(f"Download completed successfully: {filename}")
        return result
        
    except Exception as e:
        log.error(f"Error downloading file: {filename}", e)
        return jsonify({
            "success": False,
            "message": "Error downloading file. Please try again."
        })

@app.errorhandler(413)
def request_entity_too_large(error):
    log.warning("File too large uploaded")
    return jsonify({
        "success": False,
        "message": "File too large. Maximum size is 16MB."
    }), 413

@app.errorhandler(500)
def internal_server_error(error):
    log.error("Internal server error", error)
    return jsonify({
        "success": False,
        "message": "An internal server error occurred. Please try again later."
    }), 500

if __name__ == '__main__':
    # Test logging
    log.info("Starting CV Generator application")
    log.debug("Debug mode enabled")
    log.info("Startup: Application initialized successfully")
    
    # Run system checks
    log.info("Running system checks...")
    output, error, exit_code = run_system_command("python3 --version")
    log.info(f"Python version: {output.strip()}")
    
    output, error, exit_code = run_system_command("pip3 list")
    log.debug("Installed packages", {"packages": output})
    
    output, error, exit_code = run_system_command("df -h")
    log.info("Disk space", {"info": output})
    
    # Start the Flask app
    app.run(debug=not args.production, port=5001)